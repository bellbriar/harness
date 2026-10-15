"""The independent review of Part K's round-3 fixes (Part L, item 1a), and
one finding made while checking it.

Each case below was confirmed in Chromium before it was fixed.

  * bb-media-autoplay read markup differently from a browser and FAILed
    media that cannot play sound: an integration point of the wrong
    namespace (<mtext> inside <svg>, <desc> inside <math>, <annotation-xml>
    without an HTML encoding), width/height attributes on <audio> (which
    has none) or overridden by an inline style, a commented-out or
    overridden `display:none`, a duplicate attribute (a browser keeps the
    first, html.parser kept the last), and a declarative shadow root on a
    host that is not a valid custom element name or in an .xhtml file.
  * bellbriar-lint raised errors it could not stand behind: the string
    "false" in a .svelte file read as false, expressions it cannot read
    (a bound autoplay, a Svelte shorthand, a spread) read as on or off,
    Svelte `class:muted` read as the muted attribute, an upper-case
    attribute in HTML missed, and a bound `:class` object read as a plain
    class list.
  * N16 (found while checking the --provenance-attr help): bb-marquee-blink,
    bb-alt-junk, bb-meta-refresh, bb-viewport-zoom and bb-duplicate-id read
    the content of <template> and <noscript>, which a browser that runs
    scripts never puts in the document, and FAILed it.
"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bellbriar_harness import cli, engine as E                  # noqa: E402
from bellbriar_harness.lint import ERROR, WARN, lint_text       # noqa: E402
from bellbriar_harness.model import FAIL, NEEDS_REVIEW          # noqa: E402


def page(body: str) -> str:
    return ('<!doctype html><html lang="en"><head><title>T</title></head>'
            f'<body><main><h1>T</h1>{body}</main></body></html>')


def verdicts(html: str, rule: str, path: str = "x.html") -> str:
    p = E.run_page(html, path, E.load_rulebook())
    rr = next(r for r in p.results if r.rule_id == rule)
    if not rr.applicable:
        return "n/a"
    return ",".join(f.verdict for f in rr.findings) or "pass"


def media(body: str, path: str = "x.html") -> str:
    return verdicts(page(body), "bb-media-autoplay", path)


AUDIO = '<audio autoplay src="a.mp3"></audio>'


class TestForeignContent(unittest.TestCase):
    def test_integration_points_hold_html_only_in_their_own_namespace(self):
        for wrapper in ("<svg><mtext>{}</mtext></svg>",
                        "<svg><mi>{}</mi></svg>",
                        "<math><desc>{}</desc></math>",
                        "<math><foreignObject>{}</foreignObject></math>",
                        "<math><annotation-xml>{}</annotation-xml></math>",
                        '<math><annotation-xml encoding="image/svg+xml">{}'
                        '</annotation-xml></math>',
                        "<math><mi><svg>{}</svg></mi></math>",
                        "<svg><foreignObject><math>{}</math></foreignObject>"
                        "</svg>"):
            with self.subTest(wrapper=wrapper):
                self.assertEqual(media(wrapper.format(AUDIO)), "n/a")

    def test_html_inside_the_right_integration_point_still_plays(self):
        for wrapper in ("<svg><foreignObject>{}</foreignObject></svg>",
                        "<svg><desc>{}</desc></svg>",
                        "<math><mtext>{}</mtext></math>",
                        '<math><annotation-xml encoding="Text/HTML">{}'
                        '</annotation-xml></math>',
                        '<math><annotation-xml encoding="application/xhtml+xml">'
                        '{}</annotation-xml></math>',
                        '<svg><g><font color="red">{}</font></g></svg>',
                        "<svg><g><div>{}</div></g></svg>"):
            with self.subTest(wrapper=wrapper):
                self.assertEqual(media(wrapper.format(AUDIO)), FAIL)


class TestWhatMarkupShows(unittest.TestCase):
    def test_controls_that_render_are_a_review(self):
        for audio in (
                # <audio> has no width or height attributes.
                '<audio autoplay controls width="0" height="0" src="a.mp3">',
                # An inline style overrides the attribute.
                '<video autoplay controls width="0" height="0" style="width:'
                '640px;height:360px" src="a.mp4">',
                # A comment is not a declaration; the last declaration wins.
                '<audio autoplay controls style="/* display:none */ color:red"'
                ' src="a.mp3">',
                '<audio autoplay controls style="display:none; display:block"'
                ' src="a.mp3">',
                '<audio autoplay controls style="visibility:hidden; '
                'visibility:visible" src="a.mp3">',
                # A browser keeps the first of two attributes.
                '<audio autoplay controls style="" style="display:none" '
                'src="a.mp3">'):
            with self.subTest(audio=audio):
                self.assertEqual(media(audio + "</audio>"), NEEDS_REVIEW)

    def test_controls_markup_hides_still_fail(self):
        for audio in (
                '<video autoplay controls width="0" height="0" src="a.mp4">',
                '<video autoplay controls width="0" style="height:200px" '
                'src="a.mp4">',
                '<audio autoplay controls style="display:block; display:none"'
                ' src="a.mp3">',
                '<audio autoplay controls style="display:none !important; '
                'display:block" src="a.mp3">',
                '<audio autoplay controls style="display:none" style="" '
                'src="a.mp3">'):
            with self.subTest(audio=audio):
                self.assertEqual(media(audio + "</audio>"), FAIL)

    def test_the_first_of_two_attributes_counts(self):
        # Chromium: src="" is an error and nothing plays; a source in markup
        # is then missing, which is a minor review, not a FAIL.
        self.assertEqual(media('<audio autoplay src="" src="a.mp3"></audio>'),
                         NEEDS_REVIEW)
        self.assertEqual(media('<div><template shadowrootmode="bogus" '
                               'shadowrootmode="open">' + AUDIO
                               + '</template></div>'), "n/a")
        # The same holds for every rule: <img alt="" alt="Logo"> is empty.
        self.assertEqual(verdicts(page('<a href="/"><img src="l.png" alt="" '
                                       'alt="Acme"></a>'), "bb-link-name"),
                         FAIL)


class TestRoundTwo(unittest.TestCase):
    """The review of Part L's own changes."""

    def test_an_invalid_declaration_is_dropped(self):
        for style in ("display:none;display:undefined",
                      "display:none;display:-ms-flexbox",
                      "display:n\\one",
                      "visibility:hidden;visibility:bogus"):
            with self.subTest(style=style):
                html = page(f'<div style="{style}"><img src="a.png"><a href='
                            '"/x"></a><button></button></div>')
                for rule in ("bb-img-alt", "bb-link-name", "bb-button-name"):
                    self.assertNotEqual(verdicts(html, rule), FAIL)
        html = page('<div style="display:none;display:block flow"><img '
                    'src="a.png"></div>')
        self.assertEqual(verdicts(html, "bb-img-alt"), FAIL)

    def test_display_values_chromium_drops(self):
        # Checked against Chromium 141: these keywords are invalid there, so
        # the earlier display:none stands.
        for value in ("run-in", "inline-list-item", "ruby-base",
                      "ruby-base-container", "ruby-text-container",
                      "run-in flow"):
            with self.subTest(value=value):
                html = page(f'<div style="display:none; display:{value}">'
                            '<img src="a.png"></div>')
                self.assertNotEqual(verdicts(html, "bb-img-alt"), FAIL)
        for value in ("ruby-text", "inline flow-root", "math", "-webkit-box"):
            with self.subTest(value=value):
                html = page(f'<div style="display:none; display:{value}">'
                            '<img src="a.png"></div>')
                self.assertEqual(verdicts(html, "bb-img-alt"), FAIL)

    def test_references_inside_a_template_are_not_read(self):
        html = page('<template><label for="q">Q</label><input id="q"><button '
                    'aria-describedby="hint">Go</button><span id="hint">h'
                    '</span></template>')
        self.assertEqual(verdicts(html, "bb-aria-ref"), "n/a")

    def test_positive_tabindex_is_read_as_html_does(self):
        html = page('<a href="/x" tabindex="1.5">x</a>')
        self.assertEqual(verdicts(html, "bb-positive-tabindex"), NEEDS_REVIEW)
        html = page('<a href="/x" tabindex="abc">x</a>')
        self.assertEqual(verdicts(html, "bb-positive-tabindex"), "pass")

    def test_an_id_inside_a_template_names_nothing(self):
        html = page('<template><span id="lbl"></span></template><span id='
                    '"lbl">Search</span><button aria-labelledby="lbl"><svg>'
                    '</svg></button>')
        self.assertEqual(verdicts(html, "bb-button-name"), "pass")

    def test_mglyph_and_malignmark_stay_mathml(self):
        for wrapper in ("<math><mi><mglyph>{}</mglyph></mi></math>",
                        "<math><mtext><malignmark>{}</malignmark></mtext>"
                        "</math>"):
            with self.subTest(wrapper=wrapper):
                self.assertEqual(media(wrapper.format(AUDIO)), "n/a")
        self.assertEqual(media("<math><mtext><b>{}</b></mtext></math>"
                               .format(AUDIO)), FAIL)


class TestDeclarativeRoots(unittest.TestCase):
    def test_only_a_valid_host_attaches_one(self):
        for host in ("x-$", "x-y:z", "annotation-xml", "font-face", "x"):
            with self.subTest(host=host):
                self.assertEqual(media(f'<{host}><template shadowrootmode='
                                       f'"open">{AUDIO}</template></{host}>'),
                                 "n/a")
        for host in ("x-y", "x-y.z", "x-y_z", "x-" + chr(0xE9), "div", "span"):
            with self.subTest(host=host):
                self.assertEqual(media(f'<{host}><template shadowrootmode='
                                       f'"open">{AUDIO}</template></{host}>'),
                                 FAIL)

    def test_an_xhtml_file_attaches_none(self):
        body = f'<div><template shadowrootmode="open">{AUDIO}</template></div>'
        self.assertEqual(media(body, "page.html"), FAIL)
        # As XHTML (XML wants the namespace, an upper-case DOCTYPE and a
        # value for autoplay).
        xhtml = page(body.replace("autoplay ", 'autoplay="" ')).replace(
            '<!doctype html><html lang="en">', '<!DOCTYPE html><html xmlns='
            '"http://www.w3.org/1999/xhtml" lang="en">')
        for path in ("page.xhtml", "/srv/site/PAGE.XHT"):
            with self.subTest(path):
                p = E.run_page(xhtml, path, E.load_rulebook())
                self.assertEqual(p.parse_error, "")
                self.assertEqual(verdicts(xhtml, "bb-media-autoplay", path),
                                 "n/a")
        self.assertEqual(verdicts(xhtml, "bb-media-autoplay", "page.html"),
                         FAIL)


def autoplay_lint(src: str, path: str) -> str:
    out = [f.severity for f in lint_text(src, path)
           if f.rule_id == "bl-autoplay-media"]
    return ",".join(out) or "-"


class TestLintReadsOnlyWhatItCan(unittest.TestCase):
    def test_no_error_on_what_lint_cannot_read(self):
        cases = {
            "C.vue": ['<template><audio :src="u" :autoplay="autoplay">'
                      '</audio></template>',
                      '<template><video autoplay v-bind="$attrs" src="a.mp4">'
                      '</video></template>',
                      '<template><video autoplay :muted="isMuted" src="a.mp4">'
                      '</video></template>'],
            "A.jsx": ['const A = () => <audio src={u} autoPlay={autoPlay} />',
                      'const A = (p) => <video autoPlay {...p} src="a.mp4" />',
                      'const A = (p) => <video autoPlay muted={false} {...p} '
                      'src="a.mp4" />'],
            "A.ts": ['html`<audio ?autoplay=${this.auto} src="a.mp3"></audio>`'],
            "A.component.html": ['<audio [autoplay]="autoplay" src="a.mp3">'
                                 '</audio>'],
            "C.svelte": ['<video autoplay {muted} src="a.mp4"></video>',
                         '<video autoplay {...$$restProps} src="a.mp4"></video>',
                         '<audio autoplay controls="{showControls}" src="a.mp3">'
                         '</audio>'],
            "x.html": ['<div x-data><audio x-bind="player" autoplay src="a.mp3">'
                       '</audio></div>'],
        }
        for path, sources in cases.items():
            for src in sources:
                with self.subTest(path=path, src=src):
                    self.assertEqual(autoplay_lint(src, path), WARN)

    def test_svelte_strings_are_strings(self):
        # The string "false" is not the expression false. Whether it mutes
        # depends on how Svelte sets the attribute, so it is never an error.
        for src in ('<video autoplay muted="false" src="a.mp4"></video>',
                    '<audio autoplay controls="false" src="a.mp3"></audio>',
                    '<audio autoplay controls=false src="a.mp3"></audio>'):
            with self.subTest(src=src):
                self.assertEqual(autoplay_lint(src, "C.svelte"), WARN)
        for src in ('<audio autoplay muted={false} src="a.mp3"></audio>',
                    '<audio autoplay muted="{false}" src="a.mp3"></audio>',
                    '<audio autoplay controls={false} src="a.mp3"></audio>'):
            with self.subTest(src=src):
                self.assertEqual(autoplay_lint(src, "C.svelte"), ERROR)

    def test_errors_the_gate_would_fail_remain(self):
        for path, src in (
                ("A.jsx", 'const A = () => <audio src="a.mp3" autoPlay />'),
                ("A.jsx", 'const A = () => <audio src="a.mp3" autoPlay={true} '
                          'muted={false} />'),
                ("C.vue", '<template><audio autoplay :muted="false" '
                          'src="a.mp3"></audio></template>'),
                ("C.svelte", '<video autoplay class:muted={x} src="a.mp4">'
                             '</video>'),
                ("C.svelte", '<video autoplay style:controls={x} src="a.mp4">'
                             '</video>'),
                ("x.html", '<VIDEO AUTOPLAY SRC="a.mp4"></VIDEO>')):
            with self.subTest(path=path, src=src):
                self.assertEqual(autoplay_lint(src, path), ERROR)

    def test_what_the_gate_only_reviews_is_a_warning(self):
        # Round 2 of the review: no source in markup is a minor review in
        # the gate; markup inside <template> or <noscript> is not in the
        # page; a Vue dynamic argument or object binding cannot be read.
        for path, src in (
                ("A.jsx", 'const A = () => <video autoPlay ref={ref} '
                          'playsInline />'),
                ("x.html", '<template><video autoplay src="a.mp4"></video>'
                           '</template>'),
                ("x.html", '<noscript><audio autoplay src="a.mp3"></audio>'
                           '</noscript>'),
                ("x.html", '<audio autoplay src=""></audio>'),
                ("x.html", '<video autoplay src></video>'),
                ("A.jsx", 'const A = () => <video autoPlay src="" />'),
                ("x.html", '<video autoplay><source src=""></video>'),
                ("x.html", '<template x-if="a"></template><template><video '
                           'autoplay src="a.mp4"></video></template>'),
                ("C.vue", '<template><video autoplay v-bind:[attr]="true" '
                          'src="a.mp4"></video></template>'),
                ("C.vue", '<template><video autoplay v-bind.prop="opts" '
                          'src="a.mp4"></video></template>')):
            with self.subTest(path=path, src=src):
                self.assertEqual(autoplay_lint(src, path), WARN)
        for path, src in (
                ("A.jsx", 'const A = () => <video autoPlay playsInline>'
                          '<source src="/a.mp4" /></video>'),
                ("A.jsx", 'const A = () => <video autoPlay src={hero} />'),
                ("x.html", '<template x-if="open"><video autoplay src="a.mp4">'
                           '</video></template>'),
                ("x.html", '<template></template><video autoplay src="a.mp4">'
                           '</video>'),
                ("C.vue", '<template><video autoplay src="a.mp4"></video>'
                          '</template>')):
            with self.subTest(path=path, src=src):
                self.assertEqual(autoplay_lint(src, path), ERROR)

    def test_html_attribute_names_ignore_case(self):
        self.assertEqual(autoplay_lint(
            '<video autoplay MUTED src="a.mp4"></video>', "x.html"), WARN)
        self.assertEqual(autoplay_lint(
            '<audio autoplay Controls src="a.mp3"></audio>', "x.html"), WARN)

    def test_a_bound_class_never_errs_on_a_guess(self):
        """A bound class is an expression. Since P3-10 the linter reads its
        string literals: a removal on a condition, or beside classes it
        cannot read, is a warning; one it reads in full is an error."""
        for path, src, sev in (
                ("C.vue", '<template><button :class="{ \'outline-none\': '
                          'isMouse }">x</button></template>', WARN),
                ("C.vue", '<template><button v-bind:class="[\'outline-none\', '
                          'ring]">x</button></template>', WARN),
                ("x.component.html", '<button [class]="\'outline-none\'">x'
                                     '</button>', ERROR),
                ("x.html", '<button x-bind:class="open ? \'outline-none\' : '
                           '\'\'">x</button>', WARN)):
            with self.subTest(src=src):
                self.assertEqual([f.severity for f in lint_text(src, path)
                                  if f.rule_id == "bl-outline-none-class"],
                                 [sev])
        # A plain quoted class list is still read.
        self.assertEqual([f.severity for f in lint_text(
            '<button class="outline-none">x</button>', "x.html")
            if f.rule_id == "bl-outline-none-class"], [ERROR])


class TestInertContentNeverFails(unittest.TestCase):
    """N16. A browser that runs scripts never puts <template> or <noscript>
    content in the document, so nothing inside either can fail a rule
    (a declarative shadow root aside, which bb-media-autoplay reads)."""

    @staticmethod
    def fails(html: str) -> list:
        p = E.run_page(html, "x.html", E.load_rulebook())
        return sorted({r.rule_id for r in p.results for f in r.findings
                       if f.verdict == FAIL})

    def test_the_bad_fixture_inside_a_template_or_noscript(self):
        html = (ROOT / "fixtures" / "bad.html").read_text(encoding="utf-8")
        m = re.search(r"<body[^>]*>(.*)</body>", html, re.S)
        # (bad.html's duplicated id is named only by aria-describedby: a
        # review since R5, L72-3.)
        body_fails = {"bb-aria-hidden-focus", "bb-button-name",
                      "bb-control-label", "bb-iframe-title",
                      "bb-img-alt", "bb-link-name", "bb-marquee-blink",
                      "bb-media-autoplay", "bb-svg-name", "bb-table-headers"}
        self.assertTrue(body_fails <= set(self.fails(html)))   # control
        for tag in ("template", "noscript"):
            with self.subTest(tag=tag):
                wrapped = (html[:m.start(1)] + "<main><h1>X</h1></main>"
                           f"<{tag}>{m.group(1)}</{tag}>" + html[m.end(1):])
                self.assertEqual(set(self.fails(wrapped)) & body_fails, set())

    def test_head_patterns_inside_noscript(self):
        for meta in ('<meta http-equiv="refresh" content="5">',
                     '<meta name="viewport" content="user-scalable=no">'):
            with self.subTest(meta=meta):
                html = ('<!doctype html><html lang="en"><head><title>T</title>'
                        f'<noscript>{meta}</noscript></head><body><main><h1>T'
                        '</h1></main></body></html>')
                self.assertEqual(self.fails(html), [])
                self.assertNotEqual(self.fails(html.replace(
                    "<noscript>", "").replace("</noscript>", "")), [])

    def test_ids_inside_a_template_are_not_duplicates(self):
        body = ('<div id="a">x</div><a href="#a">to a</a><template><div id="a">'
                'y</div></template><img src="i.png" alt="image"><template>'
                '<img src="j.png" alt="image"><marquee>m</marquee></template>')
        got = self.fails(page(body))
        self.assertNotIn("bb-duplicate-id", got)
        self.assertNotIn("bb-marquee-blink", got)
        self.assertIn("bb-alt-junk", got)       # the image outside fails

    def test_the_provenance_attr_help_says_so(self):
        import argparse
        import contextlib
        import io
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit):
            cli.main(["--help"])
        text = " ".join(out.getvalue().split())
        # Part O: a file run attaches declarative shadow roots for every
        # rule, as a browser parsing the file does; a template left in a
        # capture is inert. --read-as says how a snapshot is read.
        self.assertIn("dom for a rendered capture, the browser's "
                      "serialization of the live DOM, any <template> in it "
                      "inert", text)
        self.assertIn("html for server HTML, parsed as a browser parses a "
                      "page, its declarative shadow roots attached", text)
        del argparse


if __name__ == "__main__":
    unittest.main()
