"""Part N, round 2: the independent review of fetch hardening (Part M's
item 2, never reviewed until now) and of the hidden-state record Part N
added to the capture.

  * A page chose the signed fallback_reason: render_failure read a net::
    error code or a timeout out of any error's first line, so a script that
    threw "net::ERR_ANYTHING" during scrolling put its own words in the
    record. Only a navigation's error is read for them now, and only where
    Playwright puts them.
  * address_class called carrier-grade NAT space (100.64.0.0/10, which
    Tailscale uses), site-local and multicast addresses public, 0.0.0.0
    private, and http://0/ public.
  * The rendered redirect chain recorded an iframe's redirects as the
    page's, and left out the requested and final URLs (A -> C was []).
  * The hidden-state record: content made visible again inside invisible
    content (visibility:visible under visibility:hidden) read as hidden,
    focus included; fallback content inside a <canvas>, which can take
    focus, was marked as not rendered; and a <datalist> or a <title> inside
    a button named it.
  * A capture retried after a protocol failure stamped under the names the
    first attempt may have shown the page, and kept any record the page
    wrote under them; the capture now removes such records and a retry
    takes new names. A browser that still fires DOM mutation events (they
    run page code inside each stamp) is not used for the capture.
  * decode_html crashed on charset=base64 (a codec Python has, which
    decodes no text) and decoded labels no browser does (utf-7, utf-32).
  * The note on a capture that did not run did not say what the page's
    stylesheets hide went unrecorded, and said "did not run" when it failed.
"""
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bellbriar_harness import fetch as F                        # noqa: E402
from bellbriar_harness.accname import static_accname            # noqa: E402
from bellbriar_harness.checks_static import PageContext         # noqa: E402
from bellbriar_harness.engine import load_rulebook, run_page    # noqa: E402
from bellbriar_harness.model import FAIL, hidden_attr           # noqa: E402
from tests.test_fetch_hardening import (HAVE_BROWSER, PAGE, _WHY,  # noqa: E402
                                        _Site, redirect, send)


def page(body: str) -> str:
    return ('<!doctype html><html lang="en"><head><title>T</title></head>'
            f'<body><main><h1>T</h1>{body}</main></body></html>')


def findings(html: str, rule: str, provenance_attr=None) -> list:
    p = run_page(html, "x.html", load_rulebook(),
                 provenance_attr=provenance_attr)
    return [f for rr in p.results if rr.rule_id == rule for f in rr.findings]


def name_of(html: str, selector: str) -> str:
    ctx = PageContext.parse(html)
    return static_accname(ctx.soup.select_one(selector), ctx.soup, ctx.ids)


class TestNamesFollowWhatIsShown(unittest.TestCase):
    def test_text_made_visible_again_names(self):
        html = page('<a href="/c" id="c"><span style="visibility:hidden">Old '
                    '<span style="visibility:visible">Cart</span></span></a>')
        self.assertEqual(name_of(html, "#c"), "Cart")
        self.assertEqual(findings(html, "bb-link-name"), [])

    def test_invisible_text_does_not(self):
        html = page('<a href="/c"><span style="visibility:hidden">Cart</span></a>')
        self.assertEqual([f.verdict for f in findings(html, "bb-link-name")],
                         [FAIL])

    def test_what_a_browser_never_renders_is_no_name(self):
        for body in ('<button><datalist id="d"><option value="Close">Close'
                     '</option></datalist></button>',
                     '<button><title>Close</title></button>'):
            with self.subTest(body=body):
                self.assertEqual(
                    [f.verdict for f in findings(page(body), "bb-button-name")],
                    [FAIL])
        # An SVG's <title> is its name, as before.
        self.assertEqual(findings(page('<button><svg><title>Close</title></svg>'
                                       '</button>'), "bb-button-name"), [])
        self.assertEqual(name_of(page('<a href="/k" id="k"><ruby>漢<rp>(</rp>'
                                      '<rt>kan</rt><rp>)</rp></ruby></a>'), "#k"),
                         "漢 kan")


class TestFocusFollowsWhatIsShown(unittest.TestCase):
    def verdicts(self, body):
        return [f.verdict for f in findings(page(body), "bb-aria-hidden-focus")]

    def test_a_link_made_visible_again_takes_focus(self):
        self.assertEqual(self.verdicts(
            '<div aria-hidden="true" style="visibility:hidden">'
            '<a href="/x" style="visibility:visible">Pay</a></div>'), [FAIL])
        self.assertEqual(self.verdicts(
            '<div aria-hidden="true" style="visibility:hidden">'
            '<a href="/x">Pay</a></div>'), [])

    def test_content_visibility_hides_the_contents_not_the_element(self):
        self.assertEqual(self.verdicts(
            '<div aria-hidden="true"><button style="content-visibility:hidden">'
            'x</button></div>'), [FAIL])
        self.assertEqual(self.verdicts(
            '<div aria-hidden="true" style="content-visibility:hidden">'
            '<button>x</button></div>'), [])

    def test_canvas_fallback_content_takes_focus(self):
        self.assertEqual(self.verdicts(
            '<canvas aria-hidden="true"><button>Play</button></canvas>'), [FAIL])


class TestFallbackReason(unittest.TestCase):
    @unittest.skipUnless(HAVE_BROWSER, _WHY)
    def test_a_page_cannot_word_a_network_error(self):
        body = (b'<!doctype html><html lang="en"><head><title>T</title></head>'
                b'<body><main><h1>T</h1></main><script>window.scrollTo = '
                b'function () { throw new Error("net::ERR_CERTIFIED_CONFORMANT"); };'
                b'</script></body></html>')
        site = _Site({"/": send(body)})
        self.addCleanup(site.stop)
        r = F.fetch(site.base + "/")
        # The steps run in the harness's own world now (L21): the page's
        # scrollTo is not the one they call.
        self.assertEqual(r.mode, "rendered", r.fallback_reason)
        self.assertNotIn("CERTIFIED", json.dumps(r.fetch_block()))


CAFE_1252 = "caf" + chr(0xC3) + chr(0xA9)    # UTF-8 "café" read as windows-1252


class TestCharsets(unittest.TestCase):
    # Part O replaced fetch's label table with the Encoding Standard's own
    # (encoding.py). A label no browser knows still declares nothing; with
    # nothing declared, Chromium decodes what a server sends as
    # windows-1252, however UTF-8 its bytes are (it detects UTF-8 only in
    # local files), so the server fetch does too.
    def test_labels_no_browser_decodes_are_ignored(self):
        from bellbriar_harness.encoding import get_encoding
        for label in ("base64", "hex", "rot13", "utf-7", "utf-32", "cp037",
                      "idna", "nonsense"):
            with self.subTest(label=label):
                self.assertIsNone(get_encoding(label))
                self.assertEqual(F.decode_html("café".encode(), label),
                                 CAFE_1252)
                self.assertEqual(F.decode_html("café".encode("cp1252"), label),
                                 "café")
        self.assertEqual(F.decode_html(b'<meta charset="utf-7"><p>+AGE-</p>'),
                         '<meta charset="utf-7"><p>+AGE-</p>')

    def test_browser_labels_map_as_a_browser_maps_them(self):
        from bellbriar_harness.encoding import get_encoding, sniff
        for label, want in (("latin1", "windows-1252"),
                            ("us-ascii", "windows-1252"),
                            ("iso-8859-9", "windows-1254"),
                            ("windows-874", "windows-874"),
                            ("shift_jis", "Shift_JIS"), ("euc-kr", "EUC-KR"),
                            ("gb2312", "GBK"), ("big5", "Big5"),
                            ("UTF-16LE", "UTF-16LE")):
            with self.subTest(label=label):
                self.assertEqual(get_encoding(label), want)
        # HTTP allows a quoted charset parameter: the server fetch unquotes
        # it as Chromium does (fetch.parse_content_type); a label in quotes
        # is no label.
        self.assertEqual(F.parse_content_type(['text/html; charset="utf-8"']),
                         ("text/html", "utf-8"))
        self.assertEqual(F.parse_content_type(["text/html; charset='utf-8'"]),
                         ("text/html", "'utf-8'"))
        self.assertIsNone(get_encoding("'utf-8'"))
        self.assertEqual(sniff(b"<p>x", "utf-8").encoding, "UTF-8")

    def test_a_server_that_declares_base64_does_not_stop_the_run(self):
        site = _Site({"/": send("<!doctype html><p>café</p>".encode(),
                                ctype="text/html; charset=base64")})
        self.addCleanup(site.stop)
        r = F.fetch_server(site.base + "/")
        self.assertIn(CAFE_1252, r.html)       # as Chromium shows it


@unittest.skipUnless(HAVE_BROWSER, _WHY)
class TestRenderedRedirects(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        frame = b'<iframe title="ad" src="/fa"></iframe>'
        cls.site = _Site({
            "/a": redirect("/b"), "/b": redirect("/c"), "/s": redirect("/c"),
            "/c": send(PAGE.replace(b"</main>", frame + b"</main>")),
            "/fa": redirect("/fb"), "/fb": send(PAGE)})

    @classmethod
    def tearDownClass(cls):
        cls.site.stop()

    def test_the_chain_is_the_page_own_from_request_to_final(self):
        b = self.site.base
        self.assertEqual(F.fetch(b + "/a", render=True).redirects,
                         [b + "/a", b + "/b", b + "/c"])
        self.assertEqual(F.fetch(b + "/s", render=True).redirects,
                         [b + "/s", b + "/c"])
        self.assertEqual(F.fetch(b + "/c", render=True).redirects, [])


@unittest.skipUnless(HAVE_BROWSER, _WHY)
class TestHiddenRecord(unittest.TestCase):
    STYLE = '<style>.vh{visibility:hidden}.vv{visibility:visible}</style>'
    BODY = ('<div aria-hidden="true" class="vh" id="vh"><a href="/x" class="vv" '
            'id="pay">Pay</a></div>'
            '<a href="/c" id="cart"><span class="vh">Old <span class="vv">Cart'
            '</span></span></a>'
            '<canvas aria-hidden="true" id="cv"><button id="play">Play</button>'
            '</canvas>')

    @classmethod
    def setUpClass(cls):
        html = page(cls.BODY).replace("<head>", "<head>" + cls.STYLE)
        cls.site = _Site({"/": send(html.encode())})
        cls.fr = F.fetch(cls.site.base + "/", render=True)

    @classmethod
    def tearDownClass(cls):
        cls.site.stop()

    def test_content_made_visible_again_is_recorded_as_shown(self):
        attr = hidden_attr(self.fr.provenance_attr)
        self.assertRegex(self.fr.html, rf'id="pay"[^>]*{attr}="shown"'
                                       rf'|{attr}="shown"[^>]*id="pay"')
        self.assertNotRegex(self.fr.html, rf'<button[^>]*{attr}=')

    def test_rules_read_it(self):
        attr = self.fr.provenance_attr
        failed = sorted(f.snippet.split('id="')[1].split('"')[0]
                        for f in findings(self.fr.html, "bb-aria-hidden-focus",
                                          attr) if f.verdict == FAIL)
        self.assertEqual(failed, ["cv", "vh"])
        self.assertEqual(findings(self.fr.html, "bb-link-name", attr), [])


@unittest.skipUnless(HAVE_BROWSER, _WHY)
class TestCaptureKeepsNoRecordThePageWrote(unittest.TestCase):
    """A record under the capture's names can only be the page's if it
    learned them; the capture removes whatever is there before it writes."""

    def test_planted_records_are_removed(self):
        from playwright.sync_api import sync_playwright
        names = "data-bb-p-0123456789abcdef"
        plant = ('<div aria-hidden="true" id="box"><a href="/x">Pay</a></div>'
                 '<script>var b = document.getElementById("box");'
                 f'b.setAttribute("{names}-hidden", "display");'
                 f'b.setAttribute("{names}", "third-party:https://cdn.example");'
                 '</script>')
        site = _Site({"/": send(page(plant).encode())})
        self.addCleanup(site.stop)
        prop = "__bb_capture_test"
        with sync_playwright() as p:
            browser, _ = F._launch_chromium(p)
            try:
                ctx = browser.new_context()
                pg = ctx.new_page()
                pg.add_init_script(F.instrumentation_script(
                    prop, capture_token="ef" * 16))
                pg.goto(site.base + "/")
                cdp = ctx.new_cdp_session(pg)
                res = cdp.send("Runtime.evaluate", {
                    "expression": f"window[{json.dumps(prop)}]"
                                  f"({F._capture_args('ef' * 16, names)})",
                    "returnByValue": True})
            finally:
                browser.close()
        html = res["result"]["value"]["html"]
        box = html.split('id="box"')[0].rsplit("<div", 1)[1] + html.split(
            'id="box"')[1].split(">", 1)[0]
        self.assertNotIn(f'{names}-hidden="display"', box)
        self.assertNotIn("third-party", box)
        self.assertEqual([f.verdict for f in findings(html, "bb-aria-hidden-focus",
                                                      names)], [FAIL])


@unittest.skipUnless(HAVE_BROWSER, _WHY)
class TestCaptureNotes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.site = _Site({"/": send(PAGE)})

    @classmethod
    def tearDownClass(cls):
        cls.site.stop()

    def notes(self, returned):
        # The capture runs in a child process (N18), so the stand-in for the
        # capture call goes there: tests/data/child-patch/sitecustomize.py,
        # put on the child's path, returns `returned`. The notes then come
        # back through the child's answer and the restricted unpickler, as
        # in a real run (OR-20).
        import json
        import os
        helper = str(Path(__file__).resolve().parent / "data" / "child-patch")
        env = {"BELLBRIAR_TEST_CAPTURE_RESULT": json.dumps(list(returned)),
               "PYTHONPATH": os.pathsep.join(
                   [helper] + ([os.environ["PYTHONPATH"]]
                               if os.environ.get("PYTHONPATH") else []))}
        with mock.patch.dict(os.environ, env):
            fr = F.fetch(self.site.base + "/", render=True)
        self.assertEqual(fr.mode, "rendered")
        return " ".join(fr.notes)

    def test_a_capture_that_did_not_run(self):
        n = self.notes((None, "", "data-bb-p-0"))
        self.assertIn("the capture did not run", n)
        self.assertIn("What the page's stylesheets hide was not recorded", n)

    def test_a_capture_that_failed_says_why(self):
        n = self.notes(({"html": None, "note": "this browser fires DOM mutation "
                         "events, which would run the page's code while the "
                         "capture stamped it, so the capture was not used"},
                        "", "data-bb-p-0"))
        self.assertIn("the capture failed (this browser fires DOM mutation", n)


if __name__ == "__main__":
    unittest.main()
