"""Fetch hardening (Part M, item 2).

  * P3-05: every rendered run launched Chromium with its sandbox off. It is
    now on wherever it can start; off only as root or on a host without
    user namespaces, and the record says so (fetch.browser.sandbox, a note).
  * P3-06: the address class read only the URL's literal host, so a name
    that resolves to loopback (127.0.0.1.nip.io) and an address written as
    a browser reads it (0x7f000001, 127.1) were recorded as public. The host
    is read as `verify` reads it, and the address the fetch connected to
    counts when no proxy was in the way.
  * P3-07: the server fetch read every page as UTF-8, read bodies of any
    size, bounded only each read (a trickling server held the run for
    ever), and on an HTTP error recorded the requested URL as final_url.
  * N8: a failed rendered fetch put the browser's error text, which a
    script on the page can choose, into the signed fallback_reason.
  * N15: closed declarative shadow roots, closed roots made by
    setHTMLUnsafe and closed roots attached through another frame's
    attachShadow were left out of the capture, with no note.
"""
import contextlib
import http.server
import io
import os
import socket
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bellbriar_harness import fetch as F                        # noqa: E402
from bellbriar_harness.engine import load_rulebook, run_page    # noqa: E402

HAVE_BROWSER, _WHY = F.playwright_available()
NO_PROXY_ENV = {k: v for k, v in os.environ.items()
                if not k.lower().endswith("_proxy")}


class _Site:
    """A loopback server answering from a dict of path -> handler(h)."""

    def __init__(self, routes):
        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a, **k):
                pass

            def do_GET(self):
                fn = routes.get(self.path.split("?")[0])
                if fn is None:
                    self.send_response(404)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                try:
                    fn(self)
                except (BrokenPipeError, ConnectionResetError):
                    pass
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.httpd.daemon_threads = True
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    @property
    def port(self):
        return self.httpd.server_address[1]

    @property
    def base(self):
        return f"http://127.0.0.1:{self.port}"

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def send(body: bytes, ctype="text/html", status=200, headers=()):
    def fn(h):
        h.send_response(status)
        h.send_header("Content-Type", ctype)
        h.send_header("Content-Length", str(len(body)))
        for k, v in headers:
            h.send_header(k, v)
        h.end_headers()
        h.wfile.write(body)
    return fn


def redirect(to):
    def fn(h):
        h.send_response(302)
        h.send_header("Location", to)
        h.send_header("Content-Length", "0")
        h.end_headers()
    return fn


PAGE = b'<!doctype html><html lang="en"><head><title>T</title></head><body><main><h1>T</h1></main></body></html>'


class TestSandbox(unittest.TestCase):
    def fake(self, failures):
        calls = []

        class Chromium:
            def launch(self, chromium_sandbox):
                calls.append(chromium_sandbox)
                if failures:
                    raise RuntimeError(failures.pop(0))
                return "browser"

        class P:
            chromium = Chromium()
        return P(), calls

    def test_root_runs_without_the_sandbox_and_says_why(self):
        p, calls = self.fake([])
        with mock.patch.object(os, "geteuid", return_value=0):
            browser, why = F._launch_chromium(p)
        self.assertEqual(calls, [False])
        self.assertIn("root", why)

    def test_the_sandbox_is_on_when_it_starts(self):
        p, calls = self.fake([])
        with mock.patch.object(os, "geteuid", return_value=1000):
            browser, why = F._launch_chromium(p)
        self.assertEqual((calls, why), ([True], ""))

    def test_only_a_sandbox_failure_turns_it_off(self):
        p, calls = self.fake(["BrowserType.launch: [FATAL:zygote_host_impl_"
                              "linux.cc(127)] No usable sandbox! Update your "
                              "kernel"])
        with mock.patch.object(os, "geteuid", return_value=1000):
            browser, why = F._launch_chromium(p)
        self.assertEqual(calls, [True, False])
        # The record says why, in the harness's words (L27).
        self.assertEqual(why, "it could not start here: user namespaces are "
                              "not available to it here (the host, or a "
                              "container's security profile, does not allow "
                              "them)")
        # An error that only mentions the sandbox is not Chromium saying it
        # cannot start one (L27): it is raised, and nothing runs unsandboxed.
        p, calls = self.fake(["Chromium sandboxing failed!"])
        with mock.patch.object(os, "geteuid", return_value=1000):
            with self.assertRaises(RuntimeError):
                F._launch_chromium(p)
        self.assertEqual(calls, [True])
        p, calls = self.fake(["Executable doesn't exist at /x/chrome"])
        with mock.patch.object(os, "geteuid", return_value=1000):
            with self.assertRaises(RuntimeError):
                F._launch_chromium(p)
        self.assertEqual(calls, [True])

    def test_no_launch_passes_no_sandbox_by_hand(self):
        src = (ROOT / "src" / "bellbriar_harness" / "fetch.py").read_text(
            encoding="utf-8")
        self.assertNotIn('"--no-sandbox"', src)


class TestAddressClass(unittest.TestCase):
    def test_hosts_read_as_a_browser_reads_them(self):
        for url, want in (("http://0x7f000001/", "loopback"),
                          ("http://127.1:8080/", "loopback"),
                          ("http://2130706433/", "loopback"),
                          ("http://foo.localhost/", "loopback"),
                          ("http://10.1.2.3/", "private"),
                          # 0.0.0.0 and :: connect to this machine.
                          ("http://0.0.0.0/", "loopback"),
                          ("http://0/", "loopback"),
                          ("http://[::]/", "loopback"),
                          ("http://10.1/", "private"),
                          # Carrier-grade NAT (Tailscale), site-local,
                          # multicast: no public site.
                          ("http://100.64.0.1/", "private"),
                          ("http://100.127.255.254/", "private"),
                          ("http://[fec0::1]/", "private"),
                          ("http://224.0.0.1/", "private"),
                          ("http://100.128.0.1/", "public"),
                          ("http://example.com/", "public")):
            with self.subTest(url=url):
                self.assertEqual(F.address_class(url), want)

    def test_the_connected_address_counts_for_a_name(self):
        self.assertEqual(F.address_class("http://site.example/", "127.0.0.1"),
                         "loopback")
        self.assertEqual(F.address_class("http://site.example/", "10.0.0.7"),
                         "private")
        self.assertEqual(F.address_class("http://site.example/", "[::1]"),
                         "loopback")
        self.assertEqual(F.address_class("http://site.example/",
                                         "93.184.215.14"), "public")
        self.assertEqual(F.address_class("http://site.example/", "100.64.0.1"),
                         "private")
        # A literal loopback host stays loopback whatever the peer.
        self.assertEqual(F.address_class("http://127.0.0.1/", "93.184.215.14"),
                         "loopback")

    def test_through_a_proxy_the_connected_address_is_not_the_site(self):
        with mock.patch.dict(os.environ, {**NO_PROXY_ENV,
                                          "https_proxy": "http://10.9.9.9:3128"},
                             clear=True):
            self.assertFalse(F._direct("https://site.example/"))
            self.assertTrue(F._direct("http://site.example/"))
        with mock.patch.dict(os.environ, {**NO_PROXY_ENV,
                                          "https_proxy": "http://10.9.9.9:3128",
                                          "no_proxy": "site.example"},
                             clear=True):
            self.assertTrue(F._direct("https://site.example/"))

    def test_a_server_fetch_records_where_a_name_led(self):
        site = _Site({"/": send(PAGE)})
        self.addCleanup(site.stop)
        real = socket.getaddrinfo

        def resolve(host, *a, **k):
            return real("127.0.0.1" if host == "staging.example" else host,
                        *a, **k)
        with mock.patch.dict(os.environ, NO_PROXY_ENV, clear=True), \
                mock.patch.object(socket, "getaddrinfo", resolve):
            r = F.fetch_server(f"http://staging.example:{site.port}/")
        self.assertEqual(r.address_class, "loopback")


class TestServerFetch(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, NO_PROXY_ENV, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def fetch(self, routes, path="/", **kw):
        site = _Site(routes)
        self.addCleanup(site.stop)
        return F.fetch_server(site.base + path, **kw), site

    def test_the_declared_charset_is_honored(self):
        text = "<p>Café crème</p>"
        r, _ = self.fetch({"/": send(text.encode("cp1252"),
                                     "text/html; charset=windows-1252")})
        self.assertIn("Café crème", r.html)
        r, _ = self.fetch({"/": send(b'<meta charset="iso-8859-1">'
                                     + text.encode("cp1252"))})
        self.assertIn("Café crème", r.html)
        r, _ = self.fetch({"/": send(b"\xff\xfe" + text.encode("utf-16-le"))})
        self.assertIn("Café crème", r.html)
        r, _ = self.fetch({"/": send(text.encode("cp1252"))})   # undeclared
        self.assertIn("Café crème", r.html)
        # Undeclared UTF-8 from a server: Chromium 141 shows it as
        # windows-1252 (it detects UTF-8 only in local files), and so does
        # the server fetch, so a name is what a visitor sees.
        r, _ = self.fetch({"/": send(text.encode("utf-8"))})
        self.assertIn("Caf" + chr(0xC3) + chr(0xA9) + " cr" + chr(0xC3)
                      + chr(0xA8) + "me", r.html)
        r, _ = self.fetch({"/": send(text.encode("utf-8"),
                                     "text/html; charset=utf-8")})
        self.assertIn("Café crème", r.html)

    def test_a_body_over_the_cap_is_refused_not_cut(self):
        with mock.patch.object(F, "MAX_PAGE_BYTES", 1000):
            with self.assertRaisesRegex(F.FetchError, "larger than"):
                self.fetch({"/": send(PAGE * 20)})

    def test_a_trickling_server_cannot_hold_the_run(self):
        def trickle(h):
            h.send_response(200)
            h.send_header("Content-Type", "text/html")
            h.end_headers()
            for _ in range(200):
                h.wfile.write(b" ")
                h.wfile.flush()
                time.sleep(0.05)
        started = time.monotonic()
        with self.assertRaisesRegex(F.FetchError, "no complete response within 1 s"):
            self.fetch({"/": trickle}, timeout=1)
        self.assertLess(time.monotonic() - started, 5)

    def test_an_error_after_redirects_keeps_the_url_it_came_from(self):
        r, site = self.fetch({"/a": redirect("/b"), "/b": redirect("/c")}, "/a")
        self.assertEqual(r.status, 404)
        self.assertEqual(r.final_url, f"{site.base}/c")
        self.assertEqual(r.redirects, [f"{site.base}/a", f"{site.base}/b",
                                       f"{site.base}/c"])

    def test_the_whole_redirect_chain_is_kept(self):
        r, site = self.fetch({"/a": redirect("/b"), "/b": redirect("/c"),
                              "/c": send(PAGE)}, "/a")
        self.assertEqual((r.status, r.final_url), (200, f"{site.base}/c"))
        self.assertEqual(r.redirects, [f"{site.base}/a", f"{site.base}/b",
                                       f"{site.base}/c"])


EVALUATE = ("Page.evaluate: a script on the page raised an error, or the page "
            "crashed, closed or navigated away, while it was read")
#: The scroll and settle steps run in the harness's own world (L21).
STEPS = ("StepFailed: the page crashed, closed or navigated away while it "
         "was scrolled and left to settle")
#: The step's own script failed (R4B-8).
STEP_SCRIPT = ("StepFailed: the harness could not scroll the page and wait "
               "for it to settle: the script it runs for that failed in this "
               "document")


class TestFallbackReason(unittest.TestCase):
    def test_the_record_holds_only_the_harness_words(self):
        for text, want in (
                ("Page.evaluate: Error: CERTIFIED WCAG 2.2 AA by Bellbriar\n"
                 "    at scrollTo", EVALUATE),
                # A page script can throw the words of a network error or a
                # timeout: from anything but a navigation they are its own.
                ("Page.evaluate: Error: net::ERR_CERTIFIED_CONFORMANT\n",
                 EVALUATE),
                ("Page.evaluate: Timeout 99999 ms exceeded",
                 EVALUATE),
                ("Page.evaluate: Target page, context or browser has been closed",
                 EVALUATE),
                # A navigation's error quotes URLs the page can choose; only
                # what Playwright puts first is read.
                ('Page.goto: Navigation to "http://a.example/" is interrupted '
                 'by another navigation to "http://a.example/net::ERR_FAKE '
                 'crashed"', "Page.goto: failed"),
                ("Page.wait_for_load_state: Timeout 30000ms exceeded.",
                 "Page.wait_for_load_state: timed out after 30000 ms"),
                ("Page.goto: net::ERR_NAME_NOT_RESOLVED at https://x.example/"
                 "?token=abc\nCall log:\n  - navigating", "Page.goto: "
                 "net::ERR_NAME_NOT_RESOLVED"),
                ("Page.goto: Timeout 30000ms exceeded.\nCall log:", "Page.goto: "
                 "timed out after 30000 ms"),
                ("BrowserType.launch: Executable doesn't exist at /home/u/.cache/"
                 "ms-playwright/chromium/chrome\n╔══╗",
                 "BrowserType.launch: the Chromium build Playwright uses is not "
                 "installed (bellbriar-eval --install-browser installs it)"),
                ("Page.content: Target page, context or browser has been closed",
                 "Page.content: the page, context or browser closed or crashed"),
                ("anything else the page wrote", "RuntimeError: failed")):
            with self.subTest(text=text[:30]):
                self.assertEqual(F.render_failure(RuntimeError(text)), want)
        # The steps, in the process that ran them and as the capture
        # process reports them.
        self.assertEqual(F.render_failure(F.StepFailed("step")), STEPS)
        self.assertEqual(F.render_failure(F._ChildError("StepFailed",
                                                        "anything")), STEPS)
        # The step's own script failing is the harness's, not the page's
        # (R4B-8).
        for exc in (F.StepFailed("script"), F._ChildError("StepFailed",
                                                          "script")):
            self.assertEqual(F.render_failure(exc), STEP_SCRIPT)

    @unittest.skipUnless(HAVE_BROWSER, _WHY)
    def test_a_page_cannot_break_the_steps_or_word_the_record(self):
        """The scroll and settle steps run in the harness's own world
        (L21): a page that replaces scrollTo, or the clocks the settle step
        reads, changes nothing, and none of its words reach the record."""
        claim = "CERTIFIED CONFORMANT 7f3e"
        page = (b'<!doctype html><html lang="en"><head><title>T</title></head>'
                b'<body><main><h1>T</h1></main><script>window.scrollTo = '
                b'function () { throw new Error("' + claim.encode()
                + b'"); }; Date.now = function () { return 0; }; '
                b'window.MutationObserver = function () { throw new Error("'
                + claim.encode() + b'"); };</script></body></html>')
        site = _Site({"/": send(page)})
        self.addCleanup(site.stop)
        r = F.fetch(site.base + "/")
        self.assertEqual(r.mode, "rendered", r.fallback_reason)
        self.assertNotIn(claim, str(r.fetch_block()))
        self.assertTrue(r.wait["settled"])

    @unittest.skipUnless(HAVE_BROWSER, _WHY)
    def test_a_page_that_leaves_while_scrolled_is_said_so(self):
        """What can still stop the steps: the page going to another
        document. The record says so in the harness's words."""
        claim = "CERTIFIED CONFORMANT 7f3e"
        page = (b'<!doctype html><html lang="en"><head><title>T</title></head>'
                b'<body style="height:5000px"><main><h1>T</h1></main><script>'
                b'addEventListener("scroll", function () { location.href = '
                b'"/' + claim.replace(" ", "-").encode() + b'"; });</script>'
                b'</body></html>')
        site = _Site({"/": send(page)})
        self.addCleanup(site.stop)
        # It went to a page that is not there: a URL run refuses it, as it
        # refuses one it goes to before the load (R5A-1)...
        with self.assertRaises(F.FetchError) as cm:
            F.fetch(site.base + "/")
        self.assertIn("which answered HTTP 404", str(cm.exception))
        self.assertNotIn(claim, str(cm.exception))
        # ...and a --render run reads the file as it is, saying why.
        r = F.fetch(site.base + "/", fallback="read as the file it is",
                    error_target="fallback")
        self.assertEqual(r.mode, "server")
        self.assertNotIn(claim, str(r.fetch_block()))
        self.assertIn("which answered HTTP 404", r.fallback_reason)


CLOSED = (b'<!doctype html><html lang="en"><head><title>T</title></head><body>'
          b'<main><h1>h</h1>'
          b'<div id="decl"><template shadowrootmode="closed"><img src="a.png" '
          b'id="in-decl"><x-n><template shadowrootmode="closed"><button '
          b'id="in-nested"></button></template></x-n></template></div>'
          b'<div id="frame-host"></div><div id="set"></div>'
          b'<template><img id="inert-img" src="t.png"></template>'
          b'</main><script>'
          b'const f = document.createElement("iframe"); f.title = "x";'
          b'document.body.append(f);'
          b'f.contentWindow.Element.prototype.attachShadow.call('
          b'document.getElementById("frame-host"), {mode: "closed"})'
          b'.innerHTML = \'<input id="in-frame">\';'
          b'document.getElementById("set").setHTMLUnsafe(\'<span><template '
          b'shadowrootmode="closed"><img id="in-set"></template></span>\');'
          b'</script></body></html>')


@unittest.skipUnless(HAVE_BROWSER, _WHY)
class TestClosedShadowRoots(unittest.TestCase):
    def rendered(self, body: bytes):
        site = _Site({"/": send(body)})
        self.addCleanup(site.stop)
        return F.fetch_rendered(site.base + "/")

    def fails(self, fr):
        page = run_page(fr.html, "p.html", load_rulebook(),
                        provenance_attr=fr.provenance_attr)
        return {(rr.rule_id, f.snippet.split(' id="')[1].split('"')[0])
                for rr in page.results for f in rr.findings
                if f.verdict == "fail" and ' id="' in f.snippet}

    def test_every_closed_root_is_captured(self):
        fr = self.rendered(CLOSED)
        self.assertTrue(fr.instrumented)
        self.assertEqual(fr.shadow_roots, 4)
        self.assertEqual(self.fails(fr), {
            ("bb-img-alt", "in-decl"), ("bb-button-name", "in-nested"),
            ("bb-control-label", "in-frame"), ("bb-img-alt", "in-set")})
        self.assertFalse([n for n in fr.notes if "shadow" in n])

    def test_a_closed_root_deep_in_the_page_is_found(self):
        deep = (b'<!doctype html><html lang="en"><head><title>T</title></head>'
                b'<body><main><h1>h</h1><div id="d"></div></main><script>'
                b'let e = document.getElementById("d");'
                b'for (let i = 0; i < 400; i++) { const c = document.createElement'
                b'("div"); e.appendChild(c); e = c; }'
                b'e.setHTMLUnsafe(\'<p><template shadowrootmode="closed"><img '
                b'id="deep-img"></template></p>\');</script></body></html>')
        fr = self.rendered(deep)
        self.assertEqual(fr.shadow_roots, 1)
        self.assertIn('id="deep-img"', fr.html)
        self.assertFalse([n for n in fr.notes if "shadow" in n], fr.notes)

    def test_a_component_too_deep_to_search_is_noted(self):
        deep = (b'<!doctype html><html lang="en"><head><title>T</title></head>'
                b'<body><main><h1>h</h1><div id="d"></div></main><script>'
                b'let e = document.getElementById("d").attachShadow({mode: '
                b'"closed"}); e.innerHTML = "<b>x</b>";'
                b'for (let i = 0; i < 160; i++) { const c = document.createElement'
                b'("div"); e.appendChild(c); e = c; }'
                b'e.attachShadow({mode: "closed"}).innerHTML = "<i>y</i>";'
                b'</script></body></html>')
        fr = self.rendered(deep)
        self.assertTrue(any("nests more than 140 levels" in n for n in fr.notes),
                        fr.notes)

    def test_the_number_of_hosts_looked_into_is_capped(self):
        many = (b'<!doctype html><html lang="en"><head><title>T</title></head>'
                b'<body><main><h1>h</h1>' + b''.join(
                    b'<p><template shadowrootmode="closed"><img id="m%d">'
                    b'</template></p>' % i for i in range(5))
                + b'</main></body></html>')
        with mock.patch.object(F, "MAX_CLOSED_ROOT_HOSTS", 3):
            fr = self.rendered(many)
        self.assertEqual(fr.shadow_roots, 3)
        self.assertTrue(any("more than 3 hosts" in n and "2 were not" in n
                            for n in fr.notes), fr.notes)

    def test_page_code_cannot_rewrite_a_capture_that_passes_closed_roots(self):
        # The N14 hooks, on a page with a closed root, so the capture goes
        # through Runtime.callFunctionOn: a `then` getter that would rewrite
        # the returned snapshot, and a localName getter that would forge
        # attribution after the stamps are written.
        hooks = (
            b'Object.defineProperty(Object.prototype, "then", {configurable:'
            b' true, get: function () { if (this && typeof this.html === '
            b'"string") this.html = this.html.replace(/in-decl/g, "gone");'
            b' return undefined; }});',
            b'var lg = Object.getOwnPropertyDescriptor(Element.prototype,'
            b' "localName").get; Object.defineProperty(Element.prototype,'
            b' "localName", {configurable: true, get: function () {'
            b' document.querySelectorAll("*").forEach(function (e) {'
            b' e.getAttributeNames().forEach(function (a) {'
            b' if (a.indexOf("data-bb-p-") === 0) e.setAttribute(a,'
            b' "third-party:cdn.example"); }); }); return lg.call(this); }});')
        for js in hooks:
            with self.subTest(hook=js[:40]):
                fr = self.rendered(CLOSED.replace(
                    b"</body>", b"<script>" + js + b"</script></body>"))
                self.assertTrue(fr.instrumented)
                self.assertIn('id="in-decl"', fr.html)
                page = run_page(fr.html, "p.html", load_rulebook(),
                                provenance_attr=fr.provenance_attr)
                alt = [f for rr in page.results if rr.rule_id == "bb-img-alt"
                       for f in rr.findings if 'id="in-decl"' in f.snippet]
                self.assertEqual([f.verdict for f in alt], ["fail"])
                self.assertNotEqual(alt[0].origin, "third-party")


if __name__ == "__main__":
    unittest.main(verbosity=2)
