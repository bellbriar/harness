"""N1 — credentials and access tokens never reach a report, a log or a bundle.

A `--url` such as https://user:pass@staging.example.com/, or a preview URL
carrying ?x-vercel-protection-bypass=…, used to be recorded verbatim: in the
signed bundle (fetch.requested_url, final_url, redirects, inputs[].path,
pages[].path), in the reports, and on stderr, which in CI is a build log.
Chromium keeps the password in every URL Playwright reports, and
Playwright's error text quotes the URL, so in auto mode the token also
became the recorded fallback_reason. A signed bundle cannot be redacted
afterwards without breaking its signature.

The contracts:
  * a URL with a user name or password is refused with directions, and the
    message never repeats the password;
  * credentials go in through --http-user, with the password from the
    environment or a file; they are offered only to the --url origin, only
    when it asks with a 401, and are never recorded;
  * every recorded URL loses its userinfo and its parameter values, except
    the ones named with --record-query, and keeps its host exactly;
  * no secret appears in the bundle, the JSON or HTML report, or stderr.
"""
import base64
import contextlib
import http.server
import io
import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bellbriar_harness import bundle as B                       # noqa: E402
from tests.bundle_body import BODY  # noqa: E402
from bellbriar_harness import cli                               # noqa: E402
from bellbriar_harness import fetch as F                        # noqa: E402
from bellbriar_harness.redact import (REDACTED, redact_text,    # noqa: E402
                                      redact_url, secret_values)

HAVE_BROWSER, _WHY = F.playwright_available()
if HAVE_BROWSER:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as _p:
            _b = _p.chromium.launch(args=["--no-sandbox"]); _b.close()
    except Exception as exc:                                    # noqa: BLE001
        HAVE_BROWSER, _WHY = False, f"no chromium binary: {exc}"

USER = "ci-user"
PASSWORD = "pw-N1secret-7f3a"
TOKEN = "tok-N1secret-91bd"
SECRETS = (PASSWORD, TOKEN)
PAGE = ('<!doctype html><html lang="en"><head><title>Staging</title></head>'
        '<body><main><h1>Staging</h1><p>Protected page.</p></main></body>'
        '</html>')


def _basic(user=USER, password=PASSWORD) -> str:
    return "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()


class _Site:
    """A loopback site behind HTTP Basic auth that records every request.

    /public* is served without a login; paths in `redirects` answer 302;
    everything else needs the credentials and otherwise answers 401 with
    `challenge` (no WWW-Authenticate header at all when it is None)."""

    def __init__(self, challenge='Basic realm="staging"', redirects=None,
                 body=PAGE):
        self.seen: list[tuple[str, str | None]] = []
        self.redirects = redirects or {}
        site = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a, **k):
                pass

            def _send(self, code, body=b"", headers=()):
                self.send_response(code)
                for k, v in headers:
                    self.send_header(k, v)
                self.send_header("content-type", "text/html")
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                auth = self.headers.get("Authorization")
                site.seen.append((self.path, auth))
                path = self.path.split("?")[0]
                if path in site.redirects:
                    return self._send(302, headers=[
                        ("Location", site.redirects[path])])
                if path.startswith("/public") or auth == _basic():
                    return self._send(200, body.encode())
                hdrs = [("WWW-Authenticate", challenge)] if challenge else []
                return self._send(401, b"<p>login required</p>", hdrs)

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def auth_headers(self) -> list:
        return [a for _, a in self.seen if a]

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def _no_secret(test, text, where):
    for s in SECRETS:
        test.assertNotIn(s, text, f"{s!r} leaked into {where}")


# ---------------------------------------------------------------- redaction

class TestRedactUrl(unittest.TestCase):
    def test_userinfo_and_every_value_go_names_stay(self):
        got, what = redact_url(
            f"https://{USER}:{PASSWORD}@staging.example.com/p"
            f"?lang=fr&token={TOKEN}#section=2")
        self.assertEqual(got, "https://staging.example.com/p"
                              "?lang=REDACTED&token=REDACTED#section=REDACTED")
        self.assertEqual(what, {"userinfo", "query", "fragment"})

    def test_a_vercel_preview_bypass_is_redacted(self):
        got, _ = redact_url("https://pr-42.example.com/pricing?"
                            f"x-vercel-protection-bypass={TOKEN}"
                            "&x-vercel-set-bypass-cookie=true")
        self.assertNotIn(TOKEN, got)
        self.assertEqual(got, "https://pr-42.example.com/pricing?"
                              "x-vercel-protection-bypass=REDACTED"
                              "&x-vercel-set-bypass-cookie=REDACTED")

    def test_record_query_keeps_only_the_named_values(self):
        url = f"https://example.com/p?lang=fr&tok={TOKEN}#lang=de&k={TOKEN}"
        got, what = redact_url(url, keep={"lang"})
        self.assertEqual(got, "https://example.com/p?lang=fr&tok=REDACTED"
                              "#lang=de&k=REDACTED")
        self.assertEqual(what, {"query", "fragment"})
        # Names match as decoded, and nothing to replace means no record.
        self.assertEqual(redact_url("https://e.com/?my%20lang=fr",
                                    keep={"my lang"}),
                         ("https://e.com/?my%20lang=fr", frozenset()))

    def test_a_parameter_without_a_name_is_a_value(self):
        self.assertEqual(redact_url(f"https://e.com/reset?{TOKEN}")[0],
                         "https://e.com/reset?REDACTED")
        # A client route keeps its path (L39, Part R1); an in-page anchor
        # with no "/" is still a value.
        self.assertEqual(redact_url("https://e.com/#/pricing")[0],
                         "https://e.com/#/pricing")
        self.assertEqual(redact_url(f"https://e.com/#{TOKEN}")[0],
                         "https://e.com/#REDACTED")

    def test_semicolons_cannot_smuggle_a_value_past_a_kept_name(self):
        got, _ = redact_url(f"https://e.com/?lang=fr;token={TOKEN}",
                            keep={"lang"})
        self.assertEqual(got, "https://e.com/?lang=fr;token=REDACTED")

    def test_nothing_secret_means_nothing_changed(self):
        for url in ("https://example.com/", "https://example.com/a/b",
                    "https://example.com/?", "https://example.com/?a=&b=",
                    "http://[::1]:8080/x", "about:blank"):
            with self.subTest(url=url):
                self.assertEqual(redact_url(url), (url, frozenset()))

    def test_the_host_a_verifier_reads_never_changes(self):
        vectors = json.loads((ROOT / "docs" / "canonicalization-vectors.json")
                             .read_text(encoding="utf-8"))
        urls = [c["final_url"] for c in vectors["url_hosts"]] + [
            f"https://{USER}:{PASSWORD}@staging.example.com:8443/a?b=1#c",
            "https://a@b@example.com/x?y=@evil.test#@evil.test",
            "HTTPS://U:P@Example.COM./?Q=1",
            "http://u:p@[::ffff:7f00:1]:80/?a=b",
            "https://example.com?x=@evil.test",
            "https://example.com/?q=a b",
        ]
        for url in urls:
            with self.subTest(url=url):
                got, _ = redact_url(url)
                if B.url_host(url) is not None:
                    self.assertEqual(B.url_host(got), B.url_host(url))
                self.assertEqual(redact_url(got)[0], got)      # idempotent

    def test_text_not_written_scheme_slash_slash_is_withheld(self):
        for url in (f"https:/{USER}:{PASSWORD}@x.com/", f"https:x.com/?t={TOKEN}",
                    f"data:text/html,<a href=#{TOKEN}>"):
            with self.subTest(url=url):
                got, what = redact_url(url)
                self.assertEqual(got, REDACTED)
                self.assertTrue(what)
        self.assertEqual(redact_url("about:blank"), ("about:blank", frozenset()))

    def test_a_backslash_authority_keeps_nothing(self):
        """Parsers disagree about where such an authority ends; the result
        must not suddenly name a host either."""
        got, what = redact_url(f"https://evil.test\\@{USER}:{PASSWORD}@x.com/")
        self.assertEqual(got, REDACTED)
        self.assertIsNone(B.url_host(got))
        self.assertEqual(what, {"userinfo"})

    def test_text_quoting_a_url_is_cleaned(self):
        url = f"http://{USER}:{PASSWORD}@127.0.0.1:9/?token={TOKEN}"
        msg = (f"Page.goto: net::ERR_UNSAFE_PORT at {url}\nCall log:\n"
               f'  - navigating to "{url}", waiting until "load"')
        out = redact_text(msg)
        _no_secret(self, out, "a cleaned Playwright message")
        self.assertIn("http://127.0.0.1:9/?token=REDACTED", out)
        # A spelling the URL pattern cannot see is caught by the literal.
        escaped = url.replace("/", "\\/")
        out = redact_text(f"error: {escaped}", secret_values(url))
        _no_secret(self, out, "a JSON-escaped URL")
        # Values that read as ordinary words are not replaced in ordinary
        # text: the harness's own messages stay readable.
        for url, text in (("https://e.com/?lang=fr", "lang fr"),
                          ("https://e.com/?browser=chromium",
                           "python -m playwright install chromium"),
                          ("https://e.com/?tab=third-party",
                           "markup from third-party scripts")):
            with self.subTest(url=url):
                self.assertEqual(redact_text(text, secret_values(url)), text)

    def test_a_token_cut_short_by_a_quote_is_still_removed_whole(self):
        url = f"https://e.com/?t=abc'{TOKEN}"
        out = redact_text(f"failed at {url} (retry)", secret_values(url))
        self.assertNotIn(TOKEN, out)

    def test_scanning_page_sized_text_is_linear(self):
        """Error text can come from a page script, at any size. An
        unbounded scheme pattern made this quadratic (40 s for one run)."""
        import time
        glued = "a" * 200_000 + f"https://e.com/?t={TOKEN}"
        start = time.monotonic()
        out = redact_text(glued)
        self.assertLess(time.monotonic() - start, 2.0)
        self.assertNotIn(TOKEN, out)

    def test_a_single_name_is_not_split_into_letters(self):
        self.assertEqual(redact_url("https://e.com/?lang=fr&l=x", keep="lang")[0],
                         "https://e.com/?lang=fr&l=REDACTED")
        fr = _result(record_query="lang")
        self.assertEqual(fr.record_query, ("lang",))
        self.assertIn("lang=fr&token=REDACTED", fr.final_url)

    def test_a_host_becomes_readable_only_as_every_parser_reads_it(self):
        """A URL that read no host only because a removed part held a
        character url_host refuses reads one afterwards — the same host,
        and the same record a browser-reported URL gives."""
        for raw, as_browser_reports in (
                ("http://127.0.0.1:8080/p#Überblick",
                 "http://127.0.0.1:8080/p#%C3%9Cberblick"),
                ("https://example.com/search?q=café",
                 "https://example.com/search?q=caf%C3%A9"),
                ("https://example.com/#a b", "https://example.com/#a%20b")):
            with self.subTest(url=raw):
                self.assertIsNone(B.url_host(raw))
                got = redact_url(raw)[0]
                self.assertEqual(got, redact_url(as_browser_reports)[0])
                self.assertEqual(B.url_host(got), B.url_host(as_browser_reports))
        # Where a removed part does not explain it, nothing becomes readable.
        for raw in ("https://bücher.de/?t=1", "https://example.com/a b?t=1",
                    f"https://evil.test\\@{USER}:{PASSWORD}@example.com/"):
            with self.subTest(url=raw):
                self.assertIsNone(B.url_host(redact_url(raw)[0]))

    def test_a_vendor_origin_never_records_credentials(self):
        _, origins = F._vendor_entries(
            [f"https://{USER}:{PASSWORD}@Vendor.example:443/x",
             "http://127.0.0.1:8001"])
        # As a browser's URL.origin writes it, so it can match at all.
        self.assertEqual(origins, ["https://vendor.example",
                                   "http://127.0.0.1:8001"])


class TestTargetUrl(unittest.TestCase):
    """--url is refused when it carries credentials, in every spelling a
    browser would still read credentials from."""

    def _refused(self, url):
        with self.assertRaises(F.FetchError) as cm:
            F.check_scheme(url)
        msg = str(cm.exception)
        _no_secret(self, msg, "the refusal message")
        return msg

    def test_userinfo_is_refused_with_directions(self):
        for url in (f"https://{USER}:{PASSWORD}@staging.example.com/p",
                    f"HTTPS://{USER}:{PASSWORD}@staging.example.com",
                    f"https://{USER}@staging.example.com/",
                    f"https://a@{USER}:{PASSWORD}@staging.example.com/"):
            with self.subTest(url=url):
                msg = self._refused(url)
                self.assertIn("--http-user", msg)
                self.assertIn("BELLBRIAR_HTTP_PASSWORD", msg)
                self.assertIn("https://staging.example.com", msg.lower())

    def test_spellings_that_hide_userinfo_from_a_naive_check(self):
        for url in (f"https:////{USER}:{PASSWORD}@staging.example.com/",
                    f"https:{USER}:{PASSWORD}@staging.example.com/",
                    f"https:\\\\{USER}:{PASSWORD}@staging.example.com/",
                    f"https://staging.example.com\\@{PASSWORD}.test/",
                    "https:///path"):
            with self.subTest(url=url):
                self._refused(url)

    def test_other_schemes_are_refused_without_echoing_the_url(self):
        msg = self._refused(f"ftp://{USER}:{PASSWORD}@example.test/x")
        self.assertIn("http(s) only", msg)

    def test_origin_is_written_as_a_browser_writes_it(self):
        for url, origin in (("http://127.0.0.1/", "http://127.0.0.1"),
                            ("http://127.0.0.1:80/x", "http://127.0.0.1"),
                            ("https://Staging.Example.com:0443/", "https://staging.example.com"),
                            ("https://example.com:8443/x?y#z", "https://example.com:8443"),
                            ("http://[0:0::1]:8080/", "http://[::1]:8080"),
                            ("https://bücher.de/", "https://xn--bcher-kva.de")):
            with self.subTest(url=url):
                self.assertEqual(F.url_origin(url), origin)


# ------------------------------------------------------- what gets recorded

def _result(**kw) -> F.FetchResult:
    url = f"https://staging.example.com/p?lang=fr&token={TOKEN}"
    base = dict(url=url, final_url=url, mode="server", html=PAGE, status=200,
                redirects=[url, f"https://staging.example.com/after#k={TOKEN}"],
                fetched_at="2026-10-01T00:00:00+00:00",
                notes=[f"saw {url}"],
                fallback_reason=f"rendered fetch failed (at {url})")
    base.update(kw)
    return F.FetchResult(**base)


class TestFetchResultRecordsNoSecrets(unittest.TestCase):
    def test_the_fetch_block_and_manifest_hold_no_secret(self):
        fr = _result()
        recorded = json.dumps([fr.fetch_block(), fr.manifest_entry()])
        _no_secret(self, recorded, "the fetch block")
        block = fr.fetch_block()
        self.assertEqual(block["redacted"], ["fragment", "query"])
        self.assertEqual(block["final_url"],
                         "https://staging.example.com/p"
                         "?lang=REDACTED&token=REDACTED")
        self.assertEqual(block["host"], "staging.example.com")
        self.assertEqual(block["host"], B.url_host(block["final_url"]))

    def test_record_query_is_honored(self):
        block = _result(record_query=("lang",)).fetch_block()
        self.assertIn("lang=fr&token=REDACTED", block["final_url"])
        self.assertIn("lang=fr&token=REDACTED", block["requested_url"])

    def test_a_reason_set_after_capture_is_cleaned_on_the_way_out(self):
        fr = _result()
        fr.fallback_reason = (f"rendered fetch failed (net::ERR at "
                              f"https://staging.example.com/p?token={TOKEN})")
        _no_secret(self, json.dumps(fr.fetch_block()), "a late reason")

    def test_userinfo_is_never_recorded_and_the_bundle_still_binds(self):
        url = f"https://{USER}:{PASSWORD}@staging.example.com/p"
        fr = _result(url=url, final_url=url, redirects=[], notes=[],
                     fallback_reason=None)
        self.assertEqual(fr.final_url, "https://staging.example.com/p")
        self.assertIn("userinfo", fr.redacted)
        bound = B.bundle_bound_values({**BODY, "bundle_format": B.BUNDLE_FORMAT,
                                       "fetch": fr.fetch_block(),
                                       "pages": None})
        self.assertEqual(bound["host"], "staging.example.com")


# ------------------------------------------------------ fallback and errors

class TestErrorsQuotingTheUrl(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.site = _Site()

    @classmethod
    def tearDownClass(cls):
        cls.site.stop()

    def test_the_recorded_fallback_reason_holds_no_token(self):
        url = f"{self.site.base}/public?token={TOKEN}"

        def boom(u, deadline_s, **kw):
            raise RuntimeError(f"Page.goto: net::ERR_FAILED at {u}\n"
                               f'Call log:\n  - navigating to "{u}"')
        # The rendered capture, as fetch() runs it (in its own process).
        with mock.patch.object(F, "playwright_available",
                               return_value=(True, "")), \
                mock.patch.object(F, "_fetch_rendered_isolated",
                                  side_effect=boom):
            fr = F.fetch(url, render=None)
        self.assertEqual(fr.mode, "server")
        self.assertIn("rendered fetch failed", fr.fallback_reason)
        _no_secret(self, fr.fallback_reason, "fallback_reason")
        _no_secret(self, json.dumps(fr.fetch_block()), "the fetch block")

    def test_a_required_render_failure_names_no_token(self):
        url = f"{self.site.base}/public?token={TOKEN}"
        with mock.patch.object(F, "playwright_available",
                               return_value=(True, "")), \
                mock.patch.object(F, "_fetch_rendered_isolated",
                                  side_effect=RuntimeError(f"at {url}")):
            with self.assertRaises(F.FetchError) as cm:
                F.fetch(url, render=True)
        _no_secret(self, str(cm.exception), "the error")
        # No chained exception, so no traceback can print the original.
        self.assertIsNone(cm.exception.__cause__)
        self.assertIsNone(cm.exception.__context__)

    def test_an_unreachable_server_names_no_token(self):
        with self.assertRaises(F.FetchError) as cm:
            F.fetch_server(f"http://127.0.0.1:9/?token={TOKEN}", timeout=5)
        _no_secret(self, str(cm.exception), "the error")
        self.assertIn("token=REDACTED", str(cm.exception))
        self.assertIn("refused", str(cm.exception).lower())
        self.assertIsNone(cm.exception.__context__)
        self.assertIsNone(cm.exception.__cause__)

    def test_a_redirect_to_a_url_with_a_password_names_no_password(self):
        """http.client quotes 'pw@host' without a scheme ("nonnumeric
        port"), which no URL pattern sees."""
        site = _Site(redirects={
            "/start": f"http://deploy:{PASSWORD}@127.0.0.1/next"})
        try:
            with self.assertRaises(F.FetchError) as cm:
                F.fetch(f"{site.base}/start", render=False)
            _no_secret(self, str(cm.exception), "the error")
            self.assertIsNone(cm.exception.__context__)
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), \
                    contextlib.redirect_stderr(err):
                code = cli.main(["--url", f"{site.base}/start",
                                 "--no-render"])
            self.assertEqual(code, 2)
            _no_secret(self, out.getvalue() + err.getvalue(), "the console")
        finally:
            site.stop()

    def test_a_huge_page_error_is_cut_in_the_record(self):
        url = f"{self.site.base}/public?token={TOKEN}"
        with mock.patch.object(F, "playwright_available",
                               return_value=(True, "")), \
                mock.patch.object(F, "_fetch_rendered_isolated",
                                  side_effect=RuntimeError(
                                      "Error: " + "x" * 100_000 + f" at {url}")):
            fr = F.fetch(url, render=None)
        self.assertLess(len(fr.fallback_reason), F.MAX_ERROR_TEXT + 100)
        _no_secret(self, json.dumps(fr.fetch_block()), "the fetch block")


# ------------------------------------------------------ credentials, server

class TestServerFetchCredentials(unittest.TestCase):
    def setUp(self):
        self.sites = []

    def tearDown(self):
        for s in self.sites:
            s.stop()

    def _site(self, **kw):
        s = _Site(**kw)
        self.sites.append(s)
        return s

    def test_offered_only_after_a_challenge_and_never_recorded(self):
        site = self._site()
        fr = F.fetch(f"{site.base}/p?token={TOKEN}", render=False,
                     http_credentials=(USER, PASSWORD))
        self.assertEqual(fr.status, 200)
        self.assertEqual([bool(a) for _, a in site.seen], [False, True])
        self.assertEqual(fr.redacted, ["http-credentials", "query"])
        _no_secret(self, json.dumps(fr.fetch_block()), "the fetch block")

    def test_wrong_password_is_a_401_not_a_crash(self):
        site = self._site()
        fr = F.fetch(f"{site.base}/p", render=False,
                     http_credentials=(USER, "wrong-password"))
        self.assertEqual(fr.status, 401)

    def test_other_challenges_are_reported_not_answered(self):
        site = self._site(challenge='Bearer realm="api"')
        fr = F.fetch(f"{site.base}/p", render=False,
                     http_credentials=(USER, PASSWORD))
        self.assertEqual(fr.status, 401)
        self.assertEqual(site.auth_headers(), [])

    def test_a_basic_challenge_without_a_realm_is_answered(self):
        site = self._site(challenge="Basic")
        fr = F.fetch(f"{site.base}/p", render=False,
                     http_credentials=(USER, PASSWORD))
        self.assertEqual(fr.status, 200)

    def test_another_origin_never_receives_them(self):
        other = self._site()
        site = self._site(redirects={"/go": f"{other.base}/p"})
        fr = F.fetch(f"{site.base}/go", render=False,
                     http_credentials=(USER, PASSWORD))
        self.assertEqual(fr.status, 401)
        self.assertEqual(other.auth_headers(), [])

    def test_a_token_added_by_a_redirect_is_not_recorded(self):
        site = self._site(redirects={"/start": f"/public?token={TOKEN}"})
        fr = F.fetch(f"{site.base}/start", render=False)
        self.assertEqual(fr.status, 200)
        self.assertTrue(fr.final_url.endswith("/public?token=REDACTED"))
        _no_secret(self, json.dumps(fr.fetch_block()), "the fetch block")

    def test_bad_credentials_are_refused_up_front(self):
        for creds, why in (((f"{USER}:x", PASSWORD), "':'"),
                           (("", PASSWORD), "empty"),
                           ((USER, "pw\nX-Injected: 1"), "control")):
            with self.subTest(creds=creds), \
                    self.assertRaises(F.FetchError) as cm:
                F.fetch("http://127.0.0.1:9/", render=False,
                        http_credentials=creds)
            self.assertIn(why, str(cm.exception))


# ---------------------------------------------------- credentials, rendered

@unittest.skipUnless(HAVE_BROWSER, _WHY)
class TestRenderedCredentials(unittest.TestCase):
    def test_the_browser_offers_them_to_the_page_origin_only(self):
        other = _Site()
        site = _Site(body=PAGE.replace(
            "</main>", f'<img alt="" src="{other.base}/pixel.png"></main>'),
            redirects={"/start": f"/p?token={TOKEN}"})
        try:
            fr = F.fetch(f"{site.base}/start", render=True,
                         http_credentials=(USER, PASSWORD))
        finally:
            site.stop()
            other.stop()
        self.assertEqual(fr.status, 200)
        self.assertIn(_basic(), site.auth_headers())
        self.assertTrue(any(p.startswith("/pixel") for p, _ in other.seen),
                        "the cross-origin image was requested")
        self.assertEqual(other.auth_headers(), [])
        self.assertTrue(fr.final_url.endswith("/p?token=REDACTED"))
        self.assertIn("http-credentials", fr.redacted)
        _no_secret(self, json.dumps(fr.fetch_block()), "the fetch block")


# ------------------------------------------------------------- end to end

class TestCliNeverPrintsSecrets(unittest.TestCase):
    def setUp(self):
        self.site = _Site()
        self.tmp = Path(tempfile.mkdtemp(prefix="bb-n1-"))

    def tearDown(self):
        self.site.stop()
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, *argv, env=None):
        out, err = io.StringIO(), io.StringIO()
        environ = {k: v for k, v in os.environ.items()
                   if k != cli.HTTP_PASSWORD_ENV}
        environ.update(env or {})
        with mock.patch.dict(os.environ, environ, clear=True), \
                contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(err):
            code = cli.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_a_url_with_a_password_is_refused_with_directions(self):
        bundle = self.tmp / "b.json"
        url = f"http://{USER}:{PASSWORD}@{self.site.base[7:]}/p"
        code, out, err = self._run("--url", url, "--no-render",
                                   "--bundle", str(bundle))
        self.assertEqual(code, 2)
        self.assertIn("--http-user", err)
        _no_secret(self, out + err, "the console")
        self.assertFalse(bundle.exists())
        self.assertEqual(self.site.seen, [], "nothing was fetched")

    def test_password_sources(self):
        url = f"{self.site.base}/p"
        code, _, err = self._run("--url", url, "--no-render",
                                 "--http-user", USER)
        self.assertEqual(code, 2)
        self.assertIn("BELLBRIAR_HTTP_PASSWORD", err)
        code, _, err = self._run("--url", url, "--no-render",
                                 "--http-user", USER,
                                 env={cli.HTTP_PASSWORD_ENV: ""})
        self.assertEqual(code, 2)
        self.assertIn("empty", err)
        code, _, err = self._run("--url", url, "--no-render",
                                 "--http-password-file", "x")
        self.assertEqual(code, 2)
        self.assertIn("needs --http-user", err)
        code, _, err = self._run("--url", url, "--no-render",
                                 "--http-user", USER, "--http-password-file",
                                 str(self.tmp / "missing"))
        self.assertEqual(code, 2)
        pw = self.tmp / "pw"
        pw.write_text(PASSWORD + "\n", encoding="utf-8")
        code, out, err = self._run("--url", url, "--no-render",
                                   "--fail-on", "never", "--http-user", USER,
                                   "--http-password-file", str(pw))
        self.assertEqual(code, 0, err)
        _no_secret(self, out + err, "the console")

    def test_a_login_page_says_how_to_log_in(self):
        code, _, err = self._run("--url", f"{self.site.base}/p",
                                 "--no-render")
        self.assertEqual(code, 2)
        self.assertIn("HTTP 401", err)
        self.assertIn("--http-user", err)
        code, out, err = self._run("--url", f"{self.site.base}/p",
                                   "--no-render", "--http-user", USER,
                                   env={cli.HTTP_PASSWORD_ENV: "wrong-pw"})
        self.assertEqual(code, 2)
        self.assertIn("did not accept", err)
        self.assertNotIn("wrong-pw", out + err)

    def test_nothing_written_or_printed_holds_a_secret(self):
        priv, pub, _ = B.generate_keypair() if B.HAVE_ED25519 else (None,) * 3
        paths = {k: self.tmp / n for k, n in (("json", "r.json"),
                                              ("html", "r.html"),
                                              ("bundle", "b.json"),
                                              ("snap", "s.html"))}
        argv = ["--url", f"{self.site.base}/p?lang=fr&token={TOKEN}",
                "--no-render", "--fail-on", "never",
                "--http-user", USER, "--record-query", "lang",
                "--json", str(paths["json"]), "--html", str(paths["html"]),
                "--bundle", str(paths["bundle"]),
                "--save-snapshot", str(paths["snap"])]
        if priv:
            key = self.tmp / "k.key"            # a key file, never argv
            key.write_text(priv)
            key.chmod(0o600)
            argv += ["--sign-key", str(key)]
        code, out, err = self._run(*argv,
                                   env={cli.HTTP_PASSWORD_ENV: PASSWORD})
        self.assertEqual(code, 0, err)
        _no_secret(self, out + err, "the console")
        for name, path in paths.items():
            _no_secret(self, path.read_text(encoding="utf-8"), name)
        bundle = json.loads(paths["bundle"].read_text(encoding="utf-8"))
        fetch = bundle["pages"][0]["fetch"]
        self.assertEqual(bundle["fetch"]["final_url"], fetch["final_url"])
        self.assertEqual(fetch["redacted"], ["http-credentials", "query"])
        self.assertTrue(fetch["final_url"].endswith("/p?lang=fr&token=REDACTED"))
        self.assertEqual(bundle["inputs"][0]["path"], fetch["final_url"])
        self.assertEqual(bundle["pages"][0]["path"], fetch["final_url"])
        self.assertIn("offered only to http://127.0.0.1:", err)
        self.assertIn("recorded as REDACTED", err)
        if priv:
            ok, why = B.verify_bundle(B.read_bundle(paths["bundle"]), pub)
            self.assertTrue(ok, why)


if __name__ == "__main__":
    unittest.main()
