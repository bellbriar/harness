"""Rendered fetch: the gap it closes, and the noise it must not create.

Two servers run on loopback so that first-party and third-party really are
different origins, which is what the provenance instrumentation keys on.
Everything here uses a real Chromium — a stubbed renderer would prove
nothing about the thing that actually breaks.

The contracts:
  * server HTML alone reports the fixture clean; the hydrated DOM does not
    (this is the understatement that made `--url` unsafe to send anyone);
  * of the eight rendered failures, seven belong to vendor scripts and are
    reported without being scored, and one is the customer's;
  * a fallback to server HTML is never silent;
  * a non-200, a domain mismatch, and an unsettled DOM are all recorded.
"""
import functools
import http.server
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bellbriar_harness import fetch as F                        # noqa: E402
from bellbriar_harness.engine import load_rulebook, run_page    # noqa: E402
from bellbriar_harness.model import FAIL                        # noqa: E402
from bellbriar_harness.scoring import score_site                # noqa: E402

SITE = ROOT / "fixtures" / "site"
FIRST = SITE / "first-party"
THIRD = SITE / "third-party"
HAVE_BROWSER, _WHY = F.playwright_available()
if HAVE_BROWSER:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as _p:
            _b = _p.chromium.launch(args=["--no-sandbox"]); _b.close()
    except Exception as exc:                                    # noqa: BLE001
        HAVE_BROWSER, _WHY = False, f"no chromium binary: {exc}"


class _Server:
    """Serve a directory on loopback. Two instances = two origins."""

    def __init__(self, directory):
        class Quiet(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *a, **k):
                pass
        handler = functools.partial(Quiet, directory=str(directory))
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    @property
    def base(self):
        return f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def stop(self):
        # shutdown() stops serve_forever; server_close() releases the socket.
        # Without the second call every fixture server leaks an fd and the
        # run ends in ResourceWarnings that bury real output.
        self.httpd.shutdown()
        self.httpd.server_close()


class TwoOriginSite:
    """The page on one loopback origin, the vendor scripts on another.

    Origin includes the port, so two loopback servers are genuinely two
    origins — which is exactly what the provenance instrumentation keys on.
    Serving everything from one port would classify the vendor scripts as
    first-party and silently make these tests meaningless.
    """

    def __init__(self):
        self.third = _Server(THIRD)
        self.tmp = tempfile.mkdtemp(prefix="bb-fixture-")
        shutil.copy(FIRST / "app.js", self.tmp)
        html = (FIRST / "hydrated.html").read_text().replace(
            "__VENDOR_BASE__", self.third.base)
        Path(self.tmp, "hydrated.html").write_text(html)
        self.first = _Server(self.tmp)
        self.url = f"{self.first.base}/hydrated.html"

    def stop(self):
        self.first.stop(); self.third.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)


def findings(html, url, verdict=FAIL, provenance_attr=None):
    page = run_page(html, url, load_rulebook(), provenance_attr=provenance_attr)
    return [f for rr in page.results for f in rr.findings if f.verdict == verdict]


class TestDomainBinding(unittest.TestCase):
    """`--domain` is a free-text claim bound into the signed statement. For a
    URL run we can check it against what was actually fetched, which closes
    the gap where a staging run could be signed as production evidence."""

    def test_exact_and_subdomain_match(self):
        self.assertTrue(F.domain_matches("https://mercy.example/a", "mercy.example")[0])
        self.assertTrue(F.domain_matches("https://www.mercy.example/a", "mercy.example")[0])

    def test_different_host_rejected(self):
        ok, why = F.domain_matches("https://staging.other.test/a", "mercy.example")
        self.assertFalse(ok)
        self.assertIn("did not measure", why)

    def test_suffix_trick_rejected(self):
        self.assertFalse(F.domain_matches("https://notmercy.example/a",
                                          "mercy.example")[0])

    def test_no_domain_stated_passes(self):
        self.assertTrue(F.domain_matches("https://anything.test/", None)[0])


class TestServerFetch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.site = TwoOriginSite()

    @classmethod
    def tearDownClass(cls):
        cls.site.stop()

    def test_server_fetch_reads_the_skeleton(self):
        r = F.fetch(self.site.url, render=False)
        self.assertEqual(r.mode, "server")
        self.assertIn("rendering disabled", r.fallback_reason)
        self.assertEqual(r.status, 200)
        self.assertEqual(len(r.sha256), 64)

    def test_missing_page_reports_its_status(self):
        r = F.fetch(f"{self.site.first.base}/nope.html", render=False)
        self.assertEqual(r.status, 404)

    def test_fallback_is_never_silent(self):
        r = F.fetch(self.site.url, render=False)
        self.assertTrue(r.fallback_reason,
                        "a server-only run must always carry its reason")


@unittest.skipUnless(HAVE_BROWSER, _WHY)
class TestRenderedFetch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.site = TwoOriginSite()
        cls.url = cls.site.url
        # The fixture's vendor scripts come from a second loopback origin,
        # which is on no vendor list; name it, as an operator would.
        cls.rendered = F.fetch(cls.url, render=True,
                               third_party_origins=[cls.site.third.base])
        cls.server = F.fetch(cls.url, render=False)

    @classmethod
    def tearDownClass(cls):
        cls.site.stop()

    # --- the gap ---------------------------------------------------------

    def test_server_html_reports_the_page_clean(self):
        run = run_page(self.server.html, self.url, load_rulebook())
        site = score_site([run], load_rulebook())
        self.assertTrue(site["pages"][0]["tier1_clean"],
                        "fixture premise: server HTML looks clean")

    def test_rendered_dom_finds_what_server_html_missed(self):
        run = run_page(self.rendered.html, self.url, load_rulebook(),
                       provenance_attr=self.rendered.provenance_attr)
        site = score_site([run], load_rulebook())
        self.assertFalse(site["pages"][0]["tier1_clean"])
        self.assertGreaterEqual(site["pages"][0]["fail_findings"], 1)

    # --- the noise -------------------------------------------------------

    def test_third_party_findings_are_attributed_not_scored(self):
        run = run_page(self.rendered.html, self.url, load_rulebook(),
                       provenance_attr=self.rendered.provenance_attr)
        site = score_site([run], load_rulebook())
        s = site["pages"][0]
        self.assertGreaterEqual(s["third_party_fail_findings"], 5,
                                "vendor widgets must be attributed away")
        self.assertLessEqual(s["fail_findings"], 2,
                             "the customer owns one defect in this fixture")

    def test_the_customer_defect_is_the_scored_one(self):
        scored = [f for f in findings(self.rendered.html, self.url,
                                      provenance_attr=self.rendered.provenance_attr)
                  if f.owned]
        self.assertTrue(any("dr.jpg" in f.snippet for f in scored))
        self.assertFalse(any("cookie.png" in f.snippet or "avatar.png" in f.snippet
                             for f in scored),
                         "vendor markup must not be scored against the customer")

    def test_third_party_findings_name_the_responsible_origin(self):
        third = [f for f in findings(self.rendered.html, self.url,
                                     provenance_attr=self.rendered.provenance_attr)
                 if not f.owned]
        self.assertTrue(third)
        for f in third:
            with self.subTest(rule=f.rule_id):
                self.assertEqual(f.origin, "third-party")
                self.assertTrue(f.origin_detail.startswith("http"),
                                f"unattributed: {f.origin_detail!r}")

    def test_server_rendered_delta_is_available_as_provenance(self):
        origins = {f.origin for f in findings(
            self.rendered.html, self.url,
            provenance_attr=self.rendered.provenance_attr)}
        self.assertIn("first-party", origins)
        self.assertIn("third-party", origins)

    def test_every_element_is_attributed(self):
        """An unattributed element is scored against the customer, so gaps in
        provenance are safe but not free — they should stay rare."""
        import re
        attr = self.rendered.provenance_attr
        self.assertTrue(attr)
        vals = set(re.findall(rf'{re.escape(attr)}="([^"]*)"', self.rendered.html))
        self.assertIn("server", vals)
        self.assertIn("first-party", vals)
        self.assertTrue(any(v.startswith("third-party:") for v in vals))
        self.assertNotIn("unknown", vals)

    # --- the capture record ---------------------------------------------

    def test_capture_is_fully_described(self):
        r = self.rendered
        self.assertEqual(r.mode, "rendered")
        self.assertEqual(r.status, 200)
        self.assertTrue(r.instrumented)
        self.assertEqual(r.browser["name"], "chromium")
        self.assertTrue(r.browser["version"])
        self.assertEqual(r.viewport, F.DEFAULT_VIEWPORT)
        self.assertEqual(r.wait["strategy"], "load+scroll+dom-settle")
        self.assertEqual(r.attribution["policy"], "vendor-list")
        self.assertIn(self.site.third.base, r.attribution["extra_third_party"])
        self.assertIsInstance(r.wait["waited_ms"], int)
        self.assertIsNone(r.fallback_reason)

    def test_snapshot_hash_covers_what_was_evaluated(self):
        import hashlib
        # The snapshot is saved as UTF-8 with a byte-order mark (Part O),
        # so a re-run decodes it as captured; the hash covers those bytes.
        self.assertEqual(self.rendered.snapshot_bytes,
                         b"\xef\xbb\xbf" + self.rendered.html.encode())
        self.assertEqual(
            self.rendered.sha256,
            hashlib.sha256(self.rendered.snapshot_bytes).hexdigest())
        entry = self.rendered.manifest_entry()
        self.assertEqual(entry["kind"], "url-snapshot")
        self.assertEqual(entry["fetch_mode"], "rendered")
        self.assertEqual(entry["sha256"], self.rendered.sha256)

    def test_polling_page_does_not_hang_the_wait(self):
        """The fixture polls every 300 ms. `networkidle` times out on that;
        load-plus-settle must not."""
        self.assertLess(self.rendered.wait["waited_ms"],
                        F.DEFAULT_SETTLE_CAP_MS + 1000)

    def test_fetch_block_is_json_safe(self):
        import json
        json.loads(json.dumps(self.rendered.fetch_block()))

    # --- failure handling ------------------------------------------------

    def test_require_render_raises_rather_than_degrading(self):
        with self.assertRaises(F.FetchError):
            F.fetch("http://127.0.0.1:1/nothing", render=True)

    def test_unreachable_host_in_auto_mode_raises_not_lies(self):
        """Auto mode falls back to server HTML — but if that fails too there
        is nothing to report, and inventing a clean result is the one
        unacceptable outcome."""
        with self.assertRaises(F.FetchError):
            F.fetch("http://127.0.0.1:1/nothing", render=None)


class TestSchemeAndAddress(unittest.TestCase):
    """`--url` means a web page, and the bundle should say what kind of
    address it reached."""

    def test_non_http_schemes_refused(self):
        for url in ("file:///tmp/x.html", "ftp://example.test/x",
                    "data:text/html,<h1>x</h1>"):
            with self.subTest(url=url), self.assertRaises(F.FetchError) as cm:
                F.fetch(url)
            self.assertIn("http(s) only", str(cm.exception))

    def test_local_files_have_their_own_path(self):
        """A file:// URL used to fetch, carry no host and no HTTP status, slip
        past the non-200 gate, and produce a bundle whose final_url was a
        local path."""
        with self.assertRaises(F.FetchError):
            F.fetch_server("file:///etc/hosts")

    def test_address_classification(self):
        for url, want in [("http://127.0.0.1:8000/x", "loopback"),
                          ("http://localhost/x", "loopback"),
                          ("http://10.0.0.5/x", "private"),
                          ("http://192.168.1.1/x", "private"),
                          ("http://169.254.169.254/latest/meta-data/", "private"),
                          ("https://mercy.example/x", "public")]:
            with self.subTest(url=url):
                self.assertEqual(F.address_class(url), want)

    def test_loopback_runs_are_marked_in_the_fetch_block(self):
        srv = _Server(FIRST)
        try:
            r = F.fetch(f"{srv.base}/hydrated.html", render=False)
            self.assertEqual(r.address_class, "loopback")
            self.assertEqual(r.fetch_block()["address_class"], "loopback")
        finally:
            srv.stop()


@unittest.skipUnless(HAVE_BROWSER, _WHY)
class TestInstrumentationSafety(unittest.TestCase):
    """The instrumentation wraps DOM entry points on a customer's live page.
    It must not change what the page does."""

    @classmethod
    def setUpClass(cls):
        cls.site = TwoOriginSite()

    @classmethod
    def tearDownClass(cls):
        cls.site.stop()

    def test_page_content_is_unchanged_apart_from_origin_attributes(self):
        url = self.site.url
        with sync_playwright() as p:
            b = p.chromium.launch(args=["--no-sandbox"])
            plain = b.new_page()
            plain.goto(url, wait_until="load"); plain.wait_for_timeout(600)
            baseline = plain.content()
            b.close()
        fr = F.fetch(url, render=True)
        instrumented = fr.html
        import re
        # The harness's attributes: provenance, the media muted record, the
        # record of what the page hides and axe-core's (the name, or the name
        # and a suffix).
        stripped = re.sub(
            rf'\s*{re.escape(fr.provenance_attr)}(?:-[a-z]+)*="[^"]*"',
            "", instrumented)
        def norm(h):
            return re.sub(r"\s+", " ", h).strip()
        self.assertEqual(norm(stripped), norm(baseline),
                         "instrumentation altered the page beyond its own "
                         "attributes")

    def test_dom_methods_still_return_their_values(self):
        """appendChild returns the node; insertAdjacentHTML returns undefined.
        A wrapper that swallows return values breaks real sites."""
        with sync_playwright() as p:
            b = p.chromium.launch(args=["--no-sandbox"])
            pg = b.new_page()
            pg.add_init_script(F.instrumentation_script("__bb_capture_test"))
            # Init scripts run on navigation; set_content on the initial
            # blank page would test the uninstrumented DOM and pass vacuously.
            pg.goto("data:text/html,<div id='h'></div>")
            out = pg.evaluate("""() => {
                const d = document.createElement('span'); d.id = 'x';
                const r = document.getElementById('h').appendChild(d);
                return {same: r === d, id: r.id,
                        parent: document.getElementById('x') !== null,
                        instrumented: typeof window.__bb_capture_test === 'function'};
            }""")
            self.assertTrue(out["instrumented"], "instrumentation did not run")
            b.close()
        self.assertTrue(out["same"]); self.assertEqual(out["id"], "x")
        self.assertTrue(out["parent"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
