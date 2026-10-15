"""The independent review of Part O (OR-1 to OR-20), each reproduced against
Chromium 141, and what was fixed. Encoding (OR-1, OR-13, OR-15) is in
test_encoding.py and the parser's trees (OR-7, OR-20) in
test_html5_parsing.py; the rest is here.

  OR-2  every shadow tree shared one id space: two instances of a component
        with id "f" inside failed bb-duplicate-id, a light-DOM label or
        aria-labelledby reached into a shadow root, and a skip link to a
        <main> inside one passed;
  OR-3  int() on a 5,000-digit tabindex, aria-level or refresh raised, so
        a page could make rules error and block the site's evidence bundle;
  OR-4  a second declarative template on a host became a root too;
  OR-5  a shadow root's <style> applied to the whole document;
  OR-6  slots inside an inert template or an <svg> received light DOM, a
        page-written <bb-shadow-root> hid content, and the adoption agency
        carried a declarative root to the wrong host;
  OR-8  XHTML served as application/xhtml+xml, and .xhtm files, were parsed
        as HTML;
  OR-9  killing the harness left the capture child, its driver and Chromium
        running;
  OR-10 a page whose markup multiplies elements had no budget;
  OR-11 a snapshot re-run could not ask for the reader its run used;
  OR-12 CR-only files reported every finding on line 1;
  OR-14 escaped selectors, quoted "]" and :scope were bucketed wrongly;
  OR-17 --render-deadline took 0, -5, inf and nan;
  OR-18 gaps in how errors are reported;
  OR-19 snippets rewrote <meta charset> and showed the harness's wrappers.
"""
import io
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bellbriar_harness import checks_static as CS                # noqa: E402
from bellbriar_harness import cli                               # noqa: E402
from bellbriar_harness import fetch as F                        # noqa: E402
from bellbriar_harness import html5                             # noqa: E402
from bellbriar_harness.engine import load_rulebook, run_page    # noqa: E402
from bellbriar_harness.scoring import score_site                # noqa: E402

RB = load_rulebook()
BIG = "9" * 5000


def page(body: str, head: str = "") -> str:
    return ('<!doctype html><html lang="en"><head><title>T</title>'
            f'{head}</head><body><main><h1>T</h1>{body}</main></body></html>')


def xpage(body: str) -> str:
    """page(), as an XHTML document (the XML reader requires XHTML's
    namespace on the root, as a browser does to show a page)."""
    return ('<html xmlns="http://www.w3.org/1999/xhtml" lang="en"><head>'
            f'<title>T</title></head><body><main><h1>T</h1>{body}</main>'
            '</body></html>')


def findings(html, path="x.html", **kw):
    p = run_page(html, path, RB, **kw)
    return p, sorted((rr.rule_id, f.verdict) for rr in p.results
                     for f in rr.findings)


def fails(html, path="x.html", **kw) -> list:
    p, got = findings(html, path, **kw)
    return sorted({rid for rid, v in got if v == "fail"})


def capture(html: str, attr: str = "data-bb-p-0123456789abcdef") -> str:
    """`html` as an instrumented capture serializes it: every element of the
    page stamped, the shadow-root templates (shadowrootmode) not, then
    materialized as fetch_rendered does."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    for el in soup.find_all(True):
        if not (el.name == "template" and el.has_attr("shadowrootmode")):
            el[attr] = "server"
    # And its own record, which a re-run of it reads first (L106).
    return F.place_capture_record(
        F.materialize_shadow_roots(str(soup), attr), attr, "141.0")


ATTR = "data-bb-p-0123456789abcdef"


class TestHugeNumbers(unittest.TestCase):
    """OR-3: no page-fed number makes a rule raise."""

    def test_no_rule_errors(self):
        for body in (f'<div aria-hidden="true"><span tabindex="{BIG}">x</span>'
                     '</div>', f'<div role="heading" aria-level="{BIG}">H</div>',
                     f'<span tabindex="-{BIG}">x</span>'):
            with self.subTest(body=body[:40]):
                p, _ = findings(page(body))
                self.assertEqual(p.errors(), [])
        p, _ = findings(page("", f'<meta http-equiv="refresh" content="{BIG}">'))
        self.assertEqual(p.errors(), [])
        self.assertNotIn("bb-meta-refresh", p.failed_rules())  # past 20 hours

    def test_the_real_failure_survives_the_poison(self):
        html = page('<div aria-hidden="true"><a href="/real">x</a></div>'
                    f'<div aria-hidden="true"><span tabindex="{BIG}">x</span>'
                    '</div>')
        self.assertEqual(fails(html), ["bb-aria-hidden-focus"])

    def test_tabindex_past_32_bits_is_absent_as_in_chromium(self):
        # Measured (Chromium 141): a span with tabindex 2147483647 takes
        # focus; with 2147483648 it does not; leading zeros are read away.
        f = CS._is_focusable
        soup = html5.parse('<span id=a tabindex="2147483647"></span>'
                           '<span id=b tabindex="2147483648"></span>'
                           '<span id=c tabindex="-2147483649"></span>'
                           '<span id=d tabindex="0000000000005"></span>')
        self.assertEqual([f(soup.find(id=i)) for i in "abcd"],
                         [True, False, False, True])

    def test_aria_level_as_chromium_reads_it(self):
        # Measured in Chromium 141's accessibility tree.
        for value, div, h3 in (("0", 1, 1), ("-1", 1, 1), ("9", 9, 9),
                               ("10", 2, 3), ("abc", 1, 1), (" 3", 3, 3),
                               ("3.5", 3, 3), ("+4", 4, 4), ("", 2, 3),
                               ("2147483648", 1, 1), (BIG, 1, 1)):
            soup = html5.parse(f'<div role="heading" aria-level="{value}">x'
                               f'</div><h3 aria-level="{value}">y</h3>')
            with self.subTest(value=value[:12]):
                self.assertEqual((CS._heading_level(soup.find("div")),
                                  CS._heading_level(soup.find("h3"))),
                                 (div, h3))

    def test_a_url_port_cannot_raise_out_of_the_url_code(self):
        with self.assertRaises(F.FetchError):
            F.url_origin(f"http://a.test:{BIG}/")
        with self.assertRaises(F.FetchError):
            F.url_origin("http://a.test:65536/")
        self.assertEqual(F.url_origin("http://a.test:000080/"), "http://a.test")


class TestTreeScopes(unittest.TestCase):
    """OR-2: ids, <label for> and fragments reach only within their tree,
    in a file run and in a capture alike."""

    def both(self, body):
        html = page(body)
        return (fails(html),
                fails(capture(html), path="https://x.test/",
                      provenance_attr=ATTR, reader="dom"))

    def test_component_instances_repeat_their_ids(self):
        field = ('<my-field><template shadowrootmode="open"><label for="f">'
                 '{}</label><input id="f"></template></my-field>')
        got = self.both(field.format("First name") + field.format("Last name"))
        self.assertEqual(got, ([], []))

    def test_a_reference_into_a_shadow_root_finds_nothing(self):
        got = self.both('<my-b><template shadowrootmode="open"><span id="t">'
                        'Save</span></template></my-b><button aria-labelledby'
                        '="t"></button>')
        # The button fails bb-button-name; bb-aria-ref reports the
        # reference for review (Part R2 review: one defect, one fail).
        self.assertEqual(got, (["bb-button-name"],) * 2)

    def test_a_light_dom_label_cannot_name_a_shadow_control(self):
        got = self.both('<label for="q">Search</label><my-in><template '
                        'shadowrootmode="open"><input id="q" type="text">'
                        '</template></my-in>')
        self.assertEqual(got, (["bb-control-label"],) * 2)

    def test_a_label_around_a_slot_does_not_label_the_slotted_control(self):
        got = self.both('<my-l><template shadowrootmode="open"><label>Name '
                        '<slot></slot></label></template><input></my-l>')
        self.assertEqual(got, (["bb-control-label"],) * 2)

    def test_a_duplicate_within_one_tree_still_counts(self):
        body = ('<my-x><template shadowrootmode="open"><span id="d">a</span>'
                '<span id="d">b</span><button aria-labelledby="d"></button>'
                '</template></my-x>')
        self.assertIn("bb-duplicate-id", fails(page(body)))

    def test_a_skip_link_cannot_reach_into_a_shadow_root(self):
        # Chromium 141: the hash changes, :target stays false, focus stays.
        p, got = findings(
            '<!doctype html><html lang="en"><head><title>T</title></head><body>'
            '<my-app><template shadowrootmode="open"><a href="#main">Skip to '
            'main content</a><header><nav aria-label="Main"><a href="/a">A</a>'
            '</nav></header><main id="main"><h1>T</h1></main></template>'
            '</my-app></body></html>')
        skip = [f for rr in p.results for f in rr.findings
                if rr.rule_id == "bb-skip-link"]
        self.assertEqual([f.verdict for f in skip], ["needs_review"])
        self.assertIn("outside a shadow root", skip[0].message)


class TestShadowRoots(unittest.TestCase):
    def test_a_second_template_stays_a_template(self):
        # OR-4: its link is never rendered, even when the first root has a
        # slot.
        body = ('<div><template shadowrootmode="open"><slot></slot></template>'
                '<template shadowrootmode="open"><a href="/x"></a></template>'
                '</div>')
        self.assertEqual(fails(page(body)), [])

    def test_styles_stay_in_their_tree(self):
        # OR-5: a component's `div {display:block}` does not show the
        # page's hidden div, nor does the page's `.x {display:none}` hide
        # the component's .x.
        self.assertEqual(fails(page(
            '<my-el><template shadowrootmode="open"><style>div { display: '
            'block }</style><div>x</div></template></my-el><div hidden>'
            '<a href="/x"></a></div>')), [])
        self.assertEqual(fails(page(
            '<my-el><template shadowrootmode="open"><div class="x"><a href='
            '"/x"></a></div></template></my-el>', "<style>.x { display: none }"
            "</style>")), ["bb-link-name"])

    def test_only_a_live_html_slot_receives_light_dom(self):
        # OR-6 (a) and (b), each as Chromium 141 renders it.
        self.assertEqual(fails(page(
            '<div><template shadowrootmode="open"><template><slot></slot>'
            '</template><slot></slot></template><a href="/x"></a></div>')),
            ["bb-link-name"])
        self.assertEqual(fails(page(
            '<div><template shadowrootmode="open"><svg><slot></slot></svg>'
            '</template><a href="/x"></a></div>')), [])

    def test_a_page_written_wrapper_hides_nothing(self):
        # OR-6 (c): <bb-shadow-root> is a valid custom element name; the
        # harness never goes by the name.
        body = ('<div><template shadowrootmode="open"><bb-shadow-root><slot>'
                '</slot></bb-shadow-root></template><a href="/x"></a></div>')
        self.assertEqual(fails(page(body)), ["bb-link-name"])
        self.assertEqual(fails(capture(page(body)), path="https://x.test/",
                               provenance_attr=ATTR, reader="dom"),
                         ["bb-link-name"])

    def test_the_root_stays_with_the_host_the_parser_gave_it(self):
        # OR-6 (d): Chromium attaches the root to the <div> at the template's
        # start tag; the adoption agency later moves the div's children into
        # a clone of the <a>, which no slot renders.
        body = ('<a href="/x">Card<div><template shadowrootmode="open"><button>'
                '</button></template></a></div>')
        self.assertEqual(fails(page(body)), ["bb-button-name"])

    def test_snippets_show_the_page_markup(self):
        # OR-19: the template the page wrote, and its own <meta charset>.
        p, _ = findings(page('<my-b><template shadowrootmode="open"><a href='
                             '"/x"></a></template></my-b>'))
        from bellbriar_harness.checks_static import PageContext, _markup
        from bellbriar_harness.model import CURRENT_PAGE
        ctx = PageContext.parse(page('<my-b id="h"><template shadowrootmode='
                                     '"open"><b>x</b></template></my-b>',
                                     '<meta charset="koi8-r">'))
        token = CURRENT_PAGE.set(ctx)
        try:
            self.assertEqual(_markup(ctx.soup.find(id="h")),
                             '<my-b id="h"><template shadowrootmode="open"><b>x'
                             '</b></template></my-b>')
            self.assertIn('<meta charset="koi8-r"/>',
                          _markup(ctx.soup.find("head")))
        finally:
            CURRENT_PAGE.reset(token)
        self.assertEqual(ctx.soup.find(id="h").find("bb-shadow-root").name,
                         "bb-shadow-root")          # restored
        snippet = next(f.snippet for rr in p.results for f in rr.findings
                       if rr.rule_id == "bb-link-name")
        self.assertEqual(snippet, '<a href="/x"></a>')


class TestReaders(unittest.TestCase):
    def test_xhtml_files_by_every_name_chromium_gives_them(self):
        # OR-8: `<script/>` closes itself in XML (as HTML, the link would be
        # the script's text).
        body = xpage('<script src="a.js"/><a href="/x"></a>')
        for name in ("x.xhtml", "x.xht", "x.xhtm", "X.XHTM"):
            with self.subTest(name):
                self.assertIn("bb-link-name", fails(body, path=name))
        self.assertNotIn("bb-link-name", fails(body, path="x.html"))
        self.assertEqual(cli.HTML_SUFFIXES,
                         (".html", ".htm", ".xhtml", ".xht", ".xhtm"))

    def test_a_snapshot_rerun_reads_as_its_run_did(self):
        # OR-11: an uninstrumented capture records no provenance attribute;
        # its reader is in the fetch block, and --read-as dom reproduces it.
        snap = page('<p aria-hidden="true"><div><a href="/x"></a></div></p>'
                    '<div><template shadowrootmode="open"><button></button>'
                    '</template></div>').encode("utf-8-sig")
        self.assertEqual(fails(snap, reader="dom"), ["bb-aria-hidden-focus"])
        self.assertEqual(fails(snap), ["bb-button-name", "bb-link-name"])
        fr = F.FetchResult(url="http://x.test/", final_url="http://x.test/",
                           mode="rendered", html="<p>", reader="dom")
        self.assertEqual(fr.fetch_block()["reader"], "dom")

    def test_the_judged_track_reads_as_the_rules_do(self):
        from bellbriar_harness.judge import JudgeResult
        from bellbriar_harness.judged import PageContext, run_judged

        class Judge:
            name, model, calibrated = "stub", "stub", False

            def judge(self, rule_id, item):
                return JudgeResult(rubric_id=rule_id, verdict="pass",
                                   rationale="", model="stub")
        d = Path(tempfile.mkdtemp())
        f = d / "snap.html"
        f.write_text(page('<a href="/x">Read more</a>'), encoding="utf-8")
        real = PageContext.parse
        calls = []

        def parse(*args, **kw):
            calls.append((kw.get("reader"), kw.get("provenance_attr")))
            return real(*args, **kw)
        with mock.patch.object(PageContext, "parse", side_effect=parse):
            run_judged([f], Judge(), reader="dom", provenance_attr=ATTR)
            run_judged([f], Judge())
        self.assertEqual(calls, [("dom", ATTR), (None, None)])

    def test_the_cli_takes_read_as_and_refuses_it_with_url(self):
        d = Path(tempfile.mkdtemp())
        (d / "s.html").write_bytes(page(
            '<p aria-hidden="true"><div><a href="/x">x</a></div></p>')
            .encode("utf-8-sig"))
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main([str(d / "s.html"), "--read-as", "dom",
                             "--json", str(d / "r.json")])
        report = json.loads((d / "r.json").read_text(encoding="utf-8"))
        self.assertEqual([f["rule_id"] for p in report["pages"]
                          for f in p["findings"] if f["verdict"] == "fail"],
                         ["bb-aria-hidden-focus"])
        self.assertEqual(code, 1)
        with redirect_stdout(io.StringIO()), redirect_stderr(err), \
                self.assertRaises(SystemExit):
            cli.main(["--url", "http://x.test/", "--read-as", "dom"])

    def test_cr_line_endings_keep_their_lines(self):
        # OR-12
        html = page("\r\r\r<a href=\"/x\"></a>").replace("<main>", "\r<main>")
        p = run_page(html.encode(), "x.html", RB)
        line = next(f.line for rr in p.results for f in rr.findings
                    if rr.rule_id == "bb-link-name")
        self.assertEqual(line, 5)


class TestElementBudget(unittest.TestCase):
    def test_a_page_that_multiplies_elements_is_not_evaluated(self):
        # OR-10: 1,000 open <b id> elements and 1,000 paragraphs build a
        # million clones; the budget stops it in about a second.
        doc = ("<!doctype html><html lang=en><head><title>T</title></head>"
               "<body><p>" + "".join(f"<b id=b{i}>" for i in range(1000))
               + "</p>" + "<p>x</p>" * 1000)
        t0 = time.monotonic()
        p = run_page(doc, "x.html", RB)
        self.assertLess(time.monotonic() - t0, 10)
        self.assertFalse(p.evaluable)
        self.assertIn("TooManyElements", p.parse_error)
        self.assertIn("not a pass", p.not_evaluable_reason)
        self.assertEqual(html5.element_budget("x" * 10), 200_000)
        self.assertEqual(html5.element_budget("x" * 10_000_000), 1_500_000)


class TestStyleKeys(unittest.TestCase):
    """OR-14: each was mis-keyed, so its rule was never tried on the element
    it matches (a differential fuzz found these three classes)."""

    def test_selectors_reach_their_elements(self):
        for style, body in (
                (r"#\31 x{display:block}", '<div id="1x" hidden>'),
                (r".\32 xl\:hidden{display:block}", '<div class="2xl:hidden" '
                 'hidden>'),
                ('[data-x="].y"]{display:block}', '<div data-x="].y" hidden>')):
            with self.subTest(style):
                self.assertEqual(fails(page(body + '<a href="/x"></a></div>',
                                            f"<style>{style}</style>")),
                                 ["bb-link-name"])

    def test_scope_is_the_root(self):
        from bellbriar_harness.style import _rightmost_key, _scope_as_root
        self.assertEqual(_scope_as_root(":scope > body .x"), ":root > body .x")
        self.assertEqual(_scope_as_root('[a=":scope"]'), '[a=":scope"]')
        self.assertEqual(_rightmost_key(r"#\31 x"), ("id", "1x"))
        self.assertEqual(_rightmost_key('[data-x="].y"]'), None)
        # :scope hid every element before: only the root matches it.
        self.assertEqual(fails(page('<div><a href="/x">x</a></div>',
                                    "<style>:scope div{display:none}</style>"
                                    )), [])


class TestContentType(unittest.TestCase):
    """OR-15: the charset and type a response's Content-Type gives, as
    Chromium 141 reads them (each measured: document.characterSet and
    contentType over HTTP)."""

    CASES = (
        (["text/html; charset=koi8-r"], "KOI8-R", "text/html"),
        (["text/html;charset=koi8-r"], "KOI8-R", "text/html"),
        (['text/html; charset="koi8-r"'], "KOI8-R", "text/html"),
        (["text/html; charset='koi8-r'"], "windows-1252", "text/html"),
        (["text/html; charset = koi8-r"], "windows-1252", "text/html"),
        (["text/html; charset= koi8-r"], "KOI8-R", "text/html"),
        (["text/html; charset=koi8-r "], "KOI8-R", "text/html"),
        (["text/html; charset*=koi8-r"], "windows-1252", "text/html"),
        (["text/html; CHARSET=KOI8-R"], "KOI8-R", "text/html"),
        (["text/html; charset=koi8-r", "text/html"], "KOI8-R", "text/html"),
        (["text/html; charset=koi8-r", "text/html; charset=iso-8859-2"],
         "ISO-8859-2", "text/html"),
        (["text/html; charset=koi8-r, text/html"], "KOI8-R", "text/html"),
        (["text/html; charset=koi8-r,text/html"], "KOI8-R", "text/html"),
        (["text/html, text/html; charset=koi8-r"], "KOI8-R", "text/html"),
        (['text/html; charset="koi8-r, x"'], "windows-1252", "text/html"),
        (["text/html; charset=koi8-r; charset=iso-8859-2"], "KOI8-R",
         "text/html"),
        (["text/html; foo=bar; charset=koi8-r"], "KOI8-R", "text/html"),
        (["text/html; charset"], "windows-1252", "text/html"),
        (['text/html; charset="koi8\\-r"'], "KOI8-R", "text/html"),
        (["text/html; charset="], "windows-1252", "text/html"),
        (["text/html (comment); charset=koi8-r"], "KOI8-R", "text/html"),
        (["text/html; charset=koi8-r (comment)"], "windows-1252", "text/html"),
        (["text/html;;charset=koi8-r"], "KOI8-R", "text/html"),
        (["text/html;\tcharset=koi8-r"], "KOI8-R", "text/html"),
        (["text/html; charset=koi8-r", "text/html; foo=bar"], "KOI8-R",
         "text/html"),
        (["text/html; charset=koi8-r", "TEXT/HTML"], "KOI8-R", "text/html"),
        (["text/html; charset=koi8-r", "*/*"], "KOI8-R", "text/html"),
        (["text/html; charset=koi8-r", "nonsense"], "KOI8-R", "text/html"),
        (["text/html; charset=koi8-r", "application/xhtml+xml"], "UTF-8",
         "application/xhtml+xml"),
        (["text/html; charset=koi8-r, application/xhtml+xml"], "UTF-8",
         "application/xhtml+xml"),
        (['text/html; charset="koi8-r'], "KOI8-R", "text/html"),
        (['text/html; charset="koi8-r"x'], "KOI8-R", "text/html"),
        (["text/html ; charset=koi8-r"], "KOI8-R", "text/html"),
        (["text/html; charset=koi8-r;"], "KOI8-R", "text/html"),
    )

    def test_as_chromium_reads_it(self):
        from bellbriar_harness.encoding import sniff
        body = b"<!doctype html><title>t</title><p>\xe9"
        for values, charset, mime in self.CASES:
            with self.subTest(values=values):
                got_mime, label = F.parse_content_type(values)
                self.assertEqual(got_mime, mime)
                got = sniff(body, label or None,
                            xml=F.is_xml_type(got_mime)).encoding
                self.assertEqual(got.lower(), charset.lower())

    def test_xml_types(self):
        # Chromium 141 opens these as XML documents; it shows a feed as text
        # and downloads other +xml types (OR2-6).
        for mime in ("application/xhtml+xml", "image/svg+xml", "text/xml",
                     "application/xml", "text/xsl"):
            self.assertTrue(F.is_xml_type(mime), mime)
            self.assertEqual(F.page_reader(mime), "xml")
        for mime in ("text/html", "text/plain", "application/json",
                     "application/atom+xml", "application/rss+xml",
                     "application/mathml+xml", "+xml", "a/+xml"):
            self.assertFalse(F.is_xml_type(mime), mime)
        for mime, reader in (("text/html", "html"), ("", "html"),
                             ("*/*", "html"), ("text/plain", None),
                             ("application/json", None), ("text/css", None),
                             ("application/octet-stream", None),
                             ("application/rss+xml", None)):
            self.assertEqual(F.page_reader(mime), reader, mime)

    def test_more_headers_as_chromium_reads_them(self):
        from bellbriar_harness.encoding import sniff
        body = b"<p>\xe9"
        for values, want in ((["*/*; charset=koi8-r"], "KOI8-R"),
                             (["text/html;\r\n charset=koi8-r"], "KOI8-R"),
                             (["text/html; charset=koi8-r\x0c"], "windows-1252")):
            with self.subTest(values=values):
                _mime, label = F.parse_content_type(values)
                self.assertEqual(sniff(body, label or None).encoding, want)


class TestDeadline(unittest.TestCase):
    def test_only_a_sensible_number_of_seconds(self):
        # OR-17
        for bad in ("0", "-5", "1e-9", "4.9", "inf", "nan", "86401", "abc"):
            with self.subTest(bad), \
                    redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                cli.main(["--url", "http://127.0.0.1:9/", "--render-deadline",
                          bad])
        self.assertEqual(F.check_deadline(None), 120.0)
        self.assertEqual(F.check_deadline("5"), 5.0)


class TestErrorReporting(unittest.TestCase):
    """OR-18."""

    def boom(self, ctx):
        raise RuntimeError("x")

    def test_an_errored_rule_is_not_an_executed_one(self):
        with mock.patch.dict(CS.CHECKS, {"bb-img-alt": self.boom}):
            p = run_page(page('<img src="a.png" alt="A">'), "x.html", RB)
        site = score_site([p], RB)
        clean = score_site([run_page(page('<img src="a.png" alt="A">'),
                                     "x.html", RB)], RB)
        self.assertEqual(site["tier1_rules_executed"],
                         clean["tier1_rules_executed"] - 1)

    def test_reports_say_the_run_is_incomplete(self):
        d = Path(tempfile.mkdtemp())
        (d / "a.html").write_text(page('<img src="a.png" alt="A">'),
                                  encoding="utf-8")
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(CS.CHECKS, {"bb-img-alt": self.boom}), \
                redirect_stdout(out), redirect_stderr(err):
            code = cli.main([str(d / "a.html"), "--json", str(d / "r.json"),
                             "--html", str(d / "r.html")])
        self.assertEqual(code, 2)
        self.assertIn("T1 ERROR", out.getvalue())
        self.assertNotIn("NOT EVALUATED", out.getvalue())
        report = json.loads((d / "r.json").read_text(encoding="utf-8"))
        self.assertEqual((report["incomplete"], report["errors"]), (True, 1))
        text = (d / "r.html").read_text(encoding="utf-8")
        self.assertIn("cannot produce an evidence bundle", text)
        self.assertNotIn("no evidence bundle was written", text)

    def test_a_page_too_big_to_read_is_no_app_shell(self):
        doc = ("<!doctype html><html lang=en><head><title>T</title></head>"
               "<body><p>" + "".join(f"<b id=b{i}>" for i in range(1000))
               + "</p>" + "<p>x</p>" * 1000)
        d = Path(tempfile.mkdtemp())
        (d / "a.html").write_text(doc, encoding="utf-8")
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main([str(d / "a.html"), "--html", str(d / "r.html")])
        self.assertEqual(code, 2)
        self.assertIn("could not be evaluated (TooManyElements", err.getvalue())
        text = (d / "r.html").read_text(encoding="utf-8")
        self.assertNotIn("client-rendered app", text)


class TestSecondReview(unittest.TestCase):
    """The independent review of these fixes (OR2-1 to OR2-11)."""

    def test_attributes_weigh_on_the_budget(self):
        # OR2-1: 300 open <b> with 150 attributes each, reopened in 4,800
        # paragraphs, would take about 10 GB; now it stops within seconds.
        attrs = " ".join(f'a{j}="v"' for j in range(150))
        doc = ("<!doctype html><html lang=en><head><title>T</title></head>"
               "<body><p>" + "".join(f"<b id=b{i} {attrs}>" for i in range(300))
               + "</p>" + "<p>x</p>" * 4800)
        t0 = time.monotonic()
        p = run_page(doc, "x.html", RB)
        self.assertLess(time.monotonic() - t0, 30)
        self.assertIn("TooManyElements", p.parse_error)

    def test_a_deep_declarative_root_keeps_its_host(self):
        # OR2-2: Chromium renders both, unnamed, at 505 to 520 levels.
        for depth in (505, 510, 520):
            body = ("<div>" * depth + '<x-a><template shadowrootmode="open"><a '
                    'href="/x"></a><slot></slot></template><button></button>'
                    "</x-a>" + "</div>" * depth)
            with self.subTest(depth=depth):
                self.assertEqual(fails(page(body)),
                                 ["bb-button-name", "bb-link-name"])

    def test_nothing_leaves_an_inert_template_when_flattened(self):
        body = "<div>" * 520 + '<template><a href="/x"></a></template>' + \
            "</div>" * 520
        self.assertEqual(fails(page(body)), [])

    def test_deep_nesting_has_a_budget_in_every_reader(self):
        # OR2-3: 50,000 nested elements took 130 s in the XML reader.
        doc = ('<html xmlns="http://www.w3.org/1999/xhtml" lang="en"><head>'
               '<title>T</title></head><body>' + "<div>" * 50000 + "x"
               + "</div>" * 50000 + "</body></html>")
        for reader, path in (("xml", "x.xhtml"), ("dom", "x.html")):
            with self.subTest(reader):
                t0 = time.monotonic()
                p = run_page(doc, path, RB, reader=reader)
                self.assertLess(time.monotonic() - t0, 15)
                self.assertIn("TooDeeplyNested", p.parse_error)

    def test_every_reader_has_an_element_budget(self):
        # A flat page builds one element per tag, but a 30 MB one builds
        # millions: the budget's cap holds in the XML and DOM readers and
        # in the capture's shadow-root step too (here at a cap of 1,000).
        flat = xpage("<i>x</i>" * 1200)
        with mock.patch.object(html5, "MAX_ELEMENT_BUDGET", 1000), \
                mock.patch.object(html5, "MIN_ELEMENT_BUDGET", 1000):
            for reader in ("xml", "dom", "html"):
                with self.subTest(reader):
                    p = run_page(flat, "x.xhtml", RB, reader=reader)
                    self.assertIn("TooManyElements", p.parse_error)
            with self.assertRaises(html5.TooManyElements):
                F.materialize_shadow_roots(
                    '<div><template shadowrootmode="open"></template></div>'
                    + "<i>x</i>" * 1200)
            p = run_page(xpage("<i>x</i>" * 900), "x.xhtml", RB)
            self.assertEqual(p.parse_error, "")

    def test_xhtml_is_read_as_xml(self):
        # OR2-4, each measured in Chromium 141.
        ns = 'xmlns="http://www.w3.org/1999/xhtml"'
        strict = ('<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" '
                  '"http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">')

        def doc(body, root=f'<html {ns} xml:lang="en">', pre=""):
            return (pre + root + "<head><title>T</title></head><body><main><h1>T"
                    f"</h1>{body}</main></body></html>")
        self.assertEqual(fails(doc(""), path="x.xhtml"), [])     # xml:lang
        self.assertEqual(fails(doc('<a href="/x"><![CDATA[Home]]></a>'),
                               path="x.xhtml"), [])
        self.assertEqual(fails(doc('<A href="/x"></A><img src="a.png" ALT="L"/>'),
                               path="x.xhtml"), ["bb-img-alt"])
        p, _ = findings(doc("<p>a&nbsp;b</p>", pre=strict), path="x.xhtml")
        self.assertEqual(p.parse_error, "")
        for label, html, error in (
                ("an undefined entity", doc("<p>a&nbsp;b</p>"), "NotWellFormed"),
                ("not well-formed", doc("<b></i>"), "NotWellFormed"),
                ("no XHTML namespace", doc("", root="<html>"), "NotAPage"),
                ("an SVG image", '<svg xmlns="http://www.w3.org/2000/svg"/>',
                 "NotAPage")):
            with self.subTest(label):
                p, _ = findings(html, path="x.xhtml")
                self.assertIn(error, p.parse_error)
                self.assertFalse(p.evaluable)

    def test_xhtml_entities_as_chromium_resolves_them(self):
        # Measured in Chromium 141 (file://): HTML's named characters only
        # under an XHTML public identifier, in text and in attributes; any
        # other undeclared entity is an XML error.
        from bellbriar_harness import xhtml
        ns = 'xmlns="http://www.w3.org/1999/xhtml"'
        st = ('<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" '
              '"http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">')
        other = '<!DOCTYPE html PUBLIC "-//X//DTD Y//EN" "y.dtd">'
        system = ('<!DOCTYPE html SYSTEM '
                  '"http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">')

        def doc(body, pre=st, decl=""):
            return (decl + pre + f'<html {ns}><head><title>t</title></head>'
                    f'<body>{body}</body></html>')
        nbsp = chr(0xA0)
        for label, html, want in (
                ("attribute", doc('<p id="p" title="a&nbsp;b">x</p>'),
                 ("a" + nbsp + "b", "x")),
                ("standalone", doc('<p id="p" title="a&nbsp;b">a&nbsp;b</p>',
                                   decl='<?xml version="1.0" standalone="yes"?>'),
                 ("a" + nbsp + "b", "a" + nbsp + "b")),
                ("a literal <", doc('<p id="p" title="a&LT;b">a&LT;b&AMP;</p>'),
                 ("a<b", "a<b&")),
                ("two code points", doc('<p id="p" title="&NotEqualTilde;">x</p>'),
                 (chr(0x2242) + chr(0x338), "x")),
                ("the internal subset first",
                 doc('<p id="p" title="a&nbsp;b">a&nbsp;b</p>',
                     st[:-1] + ' [<!ENTITY nbsp "N">]>'), ("aNb", "aNb")),
                ("an external entity is left out",
                 doc('<p id="p">a&ext;b</p>',
                     '<!DOCTYPE html [<!ENTITY ext SYSTEM "ext.ent">]>'),
                 (None, "ab")),
                ("bogus in an attribute", doc('<p id="p" title="a&bogus;b">x</p>'),
                 None),
                ("bogus in text", doc('<p id="p">a&bogus;b</p>'), None),
                ("another DTD", doc('<p id="p" title="a&nbsp;b">x</p>', other),
                 None),
                ("a system id only", doc('<p id="p">a&nbsp;b</p>', system),
                 None)):
            with self.subTest(label):
                if want is None:
                    with self.assertRaises(xhtml.NotWellFormed):
                        xhtml.parse(html)
                    continue
                p = xhtml.parse(html).find(id="p")
                self.assertEqual((p.get("title"), p.get_text()), want)

    def test_a_label_further_out_still_names_the_control(self):
        # OR2-7: Chromium names the textbox "Email ".
        self.assertEqual(fails(page(
            '<label>Email <x-f><template shadowrootmode="open"><label><slot>'
            '</slot></label></template><input type="text"></x-f></label>')), [])

    def test_host_styles(self):
        # OR2-8: :host{display:block} shows a host the page marked hidden.
        self.assertEqual(fails(page(
            '<x-c hidden><template shadowrootmode="open"><style>:host{display:'
            'block}</style><a href="/x"></a></template></x-c>')),
            ["bb-link-name"])
        self.assertEqual(fails(page(
            '<x-c hidden><template shadowrootmode="open"><style>:host(.on){'
            'display:block}</style><a href="/x"></a></template></x-c>')), [])

    def test_cdata_in_an_svg_title_names_nothing(self):
        # OR2-9: Chromium makes it a comment; the link has no name.
        self.assertEqual(fails(page(
            '<a href="/home"><svg><title><![CDATA[Home]]></title><path d="M0'
            ' 0"/></svg></a>')), ["bb-link-name"])

    def test_no_helper_process_is_a_descendant(self):
        # OR2-10: `ps` listed itself, and its reaped pid was signaled.
        self.assertEqual(F._descendants(os.getpid()), [])

    def test_meta_refresh_as_html_reads_it(self):
        # OR2-11: Chromium 141 refreshes for neither of the first two.
        for content, want in (("5abc", []), ("1e0; url=/t", []),
                              ("5; url=/x", ["bb-meta-refresh"]),
                              ("5,url=/x", ["bb-meta-refresh"]),
                              ("5.5", ["bb-meta-refresh"]), (".5", []),
                              ("0; url=/x", [])):
            with self.subTest(content):
                self.assertEqual(fails(page("", f'<meta http-equiv="refresh" '
                                                f'content="{content}">')), want)

    def test_utf8_in_files_as_chromium_guesses_it(self):
        # OR2-11: Chromium reads 20 UTF-8 accents among 20 stray Latin-1
        # bytes as UTF-8, 5 among 1 as not (measured grid).
        from bellbriar_harness.encoding import sniff
        base = b"<!doctype html><title>t</title><p>" + b"Plain filler. " * 30
        e = "é".encode()
        for valid, stray, want in ((20, 20, "UTF-8"), (20, 1, "UTF-8"),
                                   (5, 1, "windows-1252"), (1, 1, "windows-1252"),
                                   (1, 0, "UTF-8"), (0, 1, "windows-1252")):
            body = base + b" ".join([b"caf" + e] * valid) + b" " + \
                b" ".join([b"a\xe9b"] * stray)
            with self.subTest(valid=valid, stray=stray):
                self.assertEqual(sniff(body, local_file=True).encoding, want)

    def test_provenance_means_a_capture_whatever_the_name(self):
        # OR2-11: --provenance-attr implies the DOM reader, .xhtml or not.
        from bellbriar_harness.checks_static import PageContext
        ctx = PageContext.parse(page("<p>x</p>"), path="snap.xhtml",
                                provenance_attr=ATTR)
        self.assertEqual(ctx.reader, "dom")
        # A capture read as anything else is refused, not half-honored.
        d = Path(tempfile.mkdtemp())
        (d / "snap.xhtml").write_text(capture(page('<a href="/x"></a>')),
                                      encoding="utf-8")
        for reader in ("html", "xml"):
            with self.subTest(reader), redirect_stderr(io.StringIO()) as err, \
                    self.assertRaises(SystemExit) as stop:
                cli.main([str(d / "snap.xhtml"), "--provenance-attr", ATTR,
                          "--read-as", reader])
            self.assertEqual(stop.exception.code, 2)
            self.assertIn("read as dom", err.getvalue())
        with redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
            code = cli.main([str(d / "snap.xhtml"), "--provenance-attr", ATTR,
                             "--json", str(d / "r.json")])
        self.assertEqual(code, 1)                     # the empty link FAILs
        report = json.loads((d / "r.json").read_text(encoding="utf-8"))
        self.assertFalse(report.get("incomplete"))

    def test_the_judged_track_survives_a_page_it_cannot_read(self):
        # OR2-5: one page over the budget stopped the judged track and both
        # reports.
        from bellbriar_harness.judge import JudgeResult
        from bellbriar_harness.judged import run_judged

        class Judge:
            name, model, calibrated = "stub", "stub", False

            def judge(self, rule_id, item):
                return JudgeResult(rubric_id=rule_id, verdict="pass",
                                   rationale="", model="stub")
        d = Path(tempfile.mkdtemp())
        (d / "a.html").write_text(page('<a href="/x">Read more</a>'),
                                  encoding="utf-8")
        (d / "b.html").write_text(
            "<!doctype html><body><p>" + "".join(f"<b id=b{i}>"
                                                 for i in range(1000))
            + "</p>" + "<p>x</p>" * 1000, encoding="utf-8")
        jr = run_judged([d / "a.html", d / "b.html"], Judge())
        self.assertEqual([e[:2] for e in jr.errors],
                         [(str(d / "b.html"), "(the page)")])
        self.assertTrue(jr.pages[0]["results"])
        self.assertIn("error", jr.pages[1])


from tests.test_fetch_hardening import HAVE_BROWSER, _WHY, _Site, send  # noqa: E402
from tests.test_review_round_o import _live_browsers                   # noqa: E402


class TestPagesAndNotPages(unittest.TestCase):
    def test_a_server_type_a_browser_shows_as_text(self):
        # OR2-6: text/plain, JSON, a feed: no page to evaluate.
        body = page('<a href="/x"></a>').encode()
        site = _Site({"/t": send(body, ctype="text/plain"),
                      "/j": send(body, ctype="application/json"),
                      "/f": send(body, ctype="application/rss+xml"),
                      "/h": send(body)})
        self.addCleanup(site.stop)
        for path in ("/t", "/j", "/f"):
            with self.subTest(path), self.assertRaisesRegex(
                    F.FetchError, "is not a web page"):
                F.fetch_server(site.base + path)
        self.assertEqual(F.fetch_server(site.base + "/h").reader, "html")

    def test_the_record_says_why_in_the_harness_words(self):
        for kind, text, want in (
                ("FetchError", "not a web page: the browser shows it as x/y",
                 "not a web page (the browser shows it as text"),
                ("TooManyElements", "its markup builds more than ...",
                 "builds more elements than the harness reads"),
                ("FetchError", "anything else", "FetchError: failed")):
            with self.subTest(kind):
                self.assertIn(want, F.render_failure(F._ChildError(kind, text)))

    @unittest.skipUnless(HAVE_BROWSER, _WHY)
    def test_a_rendered_run_agrees(self):
        # What the browser shows as text, or as an XML error over the part
        # it read, is no page in a rendered run either.
        body = page('<a href="/x"></a>').encode()
        broken = xpage('<a href="/x"></a><b></i>').encode()
        site = _Site({"/t": send(body, ctype="text/plain"),
                      "/x": send(broken, ctype="application/xhtml+xml"),
                      "/ok": send(xpage('<a href="/x"></a>').encode(),
                                  ctype="application/xhtml+xml")})
        self.addCleanup(site.stop)
        for path, why in (("/t", "shows it as text/plain"),
                          ("/x", "not well-formed XML")):
            with self.subTest(path), self.assertRaisesRegex(F.FetchError, why):
                F.fetch_rendered(site.base + path)
        # A well-formed page served as XML is read from the server, as XML
        # (PR2-3): a capture is read back as HTML.
        with self.assertRaisesRegex(F.FetchError, "an XML document"):
            F.fetch_rendered(site.base + "/ok")
        fr = F.fetch(site.base + "/ok")
        self.assertEqual(fr.reader, "xml")
        self.assertIn("bb-link-name", fails(
            fr.html, path=fr.final_url, reader=fr.reader))
        # The fallback says why, in the harness's words, and the server
        # fetch then reads the broken page as a browser does: not a page.
        fr = F.fetch(site.base + "/x")
        self.assertIn("not a web page", fr.fallback_reason)
        p = run_page(fr.html, fr.final_url, RB, reader=fr.reader)
        self.assertIn("NotWellFormed", p.parse_error)
        self.assertFalse(p.evaluable)


class TestServedXHTML(unittest.TestCase):
    def test_the_content_type_chooses_the_reader(self):
        # OR-8: Chromium parses it as XML (one link, unnamed).
        body = xpage('<script src="a.js"/><a href="/x"></a>').encode()
        site = _Site({"/p": send(body, ctype="application/xhtml+xml"),
                      "/h": send(body)})
        self.addCleanup(site.stop)
        fr = F.fetch_server(site.base + "/p")
        self.assertEqual(fr.reader, "xml")
        self.assertIn("bb-link-name", fails(fr.html, path=fr.final_url,
                                            reader=fr.reader))
        self.assertEqual(F.fetch_server(site.base + "/h").reader, "html")


def _render_children() -> list[str]:
    out = subprocess.run(["ps", "-A", "-o", "stat=,args="],
                         capture_output=True, text=True).stdout
    return [line for line in out.splitlines()
            if "_render_child" in line and not line.strip().startswith("Z")]


@unittest.skipUnless(HAVE_BROWSER, _WHY)
class TestNothingOutlivesTheHarness(unittest.TestCase):
    """OR-9: a CI job's timeout kills the harness while a capture hangs."""

    HANG = (b'<!doctype html><html lang="en"><head><title>T</title></head>'
            b'<body><main><h1>T</h1></main><script>setTimeout(function () '
            b'{ while (true) {} }, 50);</script></body></html>')

    def setUp(self):
        self.site = _Site({"/": send(self.HANG)})
        self.addCleanup(self.site.stop)

    def run_and_kill(self, sig):
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join(
            [str(ROOT / "src")] + ([env["PYTHONPATH"]]
                                   if env.get("PYTHONPATH") else []))
        proc = subprocess.Popen(
            [sys.executable, "-m", "bellbriar_harness", "--url",
             self.site.base + "/", "--render-deadline", "300"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
        for _ in range(80):                      # the capture is under way
            if _render_children() and _live_browsers():
                break
            time.sleep(0.25)
        time.sleep(1.5)
        proc.send_signal(sig)
        proc.wait(timeout=30)
        for _ in range(60):
            if not _render_children() and not _live_browsers():
                break
            time.sleep(0.25)
        self.assertEqual(_render_children(), [])
        self.assertEqual(_live_browsers(), [])

    def test_sigterm(self):
        self.run_and_kill(signal.SIGTERM)

    def test_sigkill(self):
        self.run_and_kill(signal.SIGKILL)


if __name__ == "__main__":
    unittest.main()
