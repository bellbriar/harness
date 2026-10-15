"""Part R, stage 6: the freeze. The fixes from the reviews of R5's last
round.

Round 1, the reviews of R5's round 9:
  R6A     the run's credentials as the Authorization header carries them;
          a quoted value scrubbed before it is cut; the password escaped
          twice; a drawing's and MathML's hidden parts marked; a search
          bounded inside long runs of white space; no locator step named
          for the password; the other case of a letter, encoded.
  R6B     url() one token in every scanner; a style attribute read once;
          media queries as Chromium 141 reads them: each value's type,
          ranges, escapes, comments and CSS white space, three-valued
          logic, any depth in linear time, math functions as CSS types
          them; HTML's elements by their namespace; a visibility only
          known later on focusable content; inherit inside <details> and
          <marquee>; a stray closer in @supports.

Round 2, the reviews of round 1:
  R6C     the Authorization header in any spelling, and a redirect to it;
          a "+" beside white space and a long run in a password; a
          locator step in lower case; "&" and "%" written again as
          references; the capital sharp s; a drawing's and MathML's parts
          that are not rendered, read as Chromium 141 reads them.
  R6D     a visibility only known later reviewed; a drawing's xlink:href;
          media queries with escaped keywords, names and units, comments
          that separate, a bad string or url, a closer in another block,
          round()'s arguments, in place; CSS's own white space trimming a
          rule's parts; `none\\9` and `!important` as CSS reads them;
          url( escaped, and not after a name, a hash or an at-keyword.

Round 3, the reviews of round 2:
  R6E     the header as a script escapes it, and JSON in JSON; a form's
          encoding beside a "+"; searches linear and quick over many
          secrets; console lines redacted; inside a drawing's parts that
          are not rendered, visibility as computed, a <g> with no box,
          conditions in a box; what a drawing never renders takes no focus.
  R6F     a drawing's link named by its xlink:title; a rule list's ";"
          and "}", a stylesheet's "<!--" and "-->", an @layer's one name;
          a selector list with an empty member or a pseudo Chromium does
          not have; bad tokens in @supports; what a drawing never renders,
          from markup; a var() visibility on the element; comments in
          declarations; XHTML's xlink under any prefix.

Round 4, the reviews of round 3 (R6G's secrets findings are open: L111):
  R6G     links a drawing boxes but never paints (<defs>, a clip path, a
          mask, a pattern, a marker, a <g> with display:none) in the
          accessibility tree; a <mphantom> invisible; an <a> in an <a>, a
          text part outside a <text>, the conditions a <switch> reads,
          ASCII white space in requiredExtensions; an <a> that is no
          link, with no box, names nothing.
  R6H     pseudo-classes' and pseudo-elements' arguments; a display var()
          reviewed; the measured names and orders; an @scope's root and
          limit; nested rules soupsieve does not read; a <title> of white
          space; @namespace where it counts, prefix by prefix; escapes
          before comments and in @supports; forgiving lists read once; a
          page's nested selectors bounded.

Round 5, the reviews of round 4:
  R6I     an element's own failing conditions; HTML and a drawing in a
          <foreignObject> where nothing paints; an outermost <svg>'s
          <title> of white space; a part with no box, and what stands
          between, by the role Chromium resolves; a <mphantom> invisible
          for the tree and focus; a var() display where its fallback or a
          concrete display decides.
  R6J     names in arguments read in linear time; prefixed type selectors
          matched; a var() display under a condition, and its fallback; no
          :has() in a list a :has() holds; members' combinators and
          pseudo-elements in every list; block at-rules Chromium drops
          before @namespace; the measured followers, escaped prefixes,
          comments in An+B and brackets, escaped flags in nested rules,
          @scope's lists.

Round 6, the reviews of round 5:
  R6K     requiredExtensions with white space after it; a box that never
          paints, whose conditions pass, in the tree; an XHTML attribute's
          case; region and form with no name; <mphantom>'s revert;
          aria-labelledby and content made visible again; a var() level
          with a hide, and custom properties registered, escaped or with a
          comment before the colon; the guide's names from content.
  R6L     view transitions' white space; :not() after ::part(); no :has()
          in :host() or ::slotted(); pseudo-elements in an `of` list inside
          a function; an escaped :nth-child() and `to`; @font-feature-values'
          families, @container's default, @function's one type; the
          README's nesting limits.

Round 7, the reviews of round 6:
  R6M     an aria-labelledby target that is hidden read whole, and one
          shown read past a part whose role is group; region and form by
          the names Chromium reads; a drawing's parts Chromium never reads,
          in a file run; conditions from the capture in a rendered run; an
          <?xml-stylesheet?>; the notes' names from content.
  R6N     a var()'s fallback level with a hide, under a condition or a
          revert, reviewed, and shown for names; @font-feature-values'
          keywords, @function's types, view transitions' names, @container's
          names, `of` in lower case; pseudo-elements in nested `of` lists;
          :not() after any pseudo-element; escaped hyphens in a custom
          property; a comment before "("; the README's @container.

Round 8, the reviews of round 7:
  R6O     labels on deep pages read in time; a drawing's <desc> through
          aria-labelledby; a <g> in an <a> in a <text>; an <svg> named
          from its content by its role; the notes' <svg> sentence.
  R6P     custom properties found in time; a visibility var() that
          inherits, level with a hide, reviewed; a "(" that opens no
          function; combinators in a :not() after a pseudo-element;
          ::view-transition-group-children(); comments in An+B; the
          README's dropped @container.

Round 9, the decision on L92 and L115:
          a link or a button named only by what Chromium 141 does not
          read (an <article>, a <figure>, a <table> of data, role=img,
          MathML, an <object>) reviewed; an <iframe>'s fallback text.

Round 10, the reviews of rounds 8 and 9:
  R6Q     the review's impact by what axe-core reads; a table's border
          and bgcolor left to styles; no title of a <span>, a <div>, an
          <i>; a hidden <legend> or <caption>; a label's content; the
          <g>s Chromium keeps; a stray <tspan> in a hidden target; a <g>
          in an <a> in a <text>, rendered.
  R6R     a var()'s fallback revert level with a show; a ")" that closes
          nothing, a "]" outside an attribute selector; a comment between
          a "+" and a digit in An+B.

Round 11, the reviews of round 10:
  R6S     a button's <label> in place of its own name; the titles
          Chromium reads where an element takes focus, is a link, a
          custom element or draggable; no title axe-core reads in white
          space or of role none; an icon font's glyph; a <table>'s
          summary beside a <caption>; a hostile page in time.
  R6T     a member that names a pseudo-class and holds what Chromium
          does not read drops its rule and those nested in it; a
          visibility var() level with a show; a <dialog open popover>.

Round 12, the reviews of round 11:
  R6U     titles of elements HTML does not have; what axe-core reads of a
          title past embedded and hidden content; labels Chromium leaves
          out; a button input's empty value; a <caption>'s own name; a
          deep page in time.
  R6V     a nested selector that starts with a combinator and holds `&`;
          a visibility var() above a show; C1 characters; an @scope's
          root; a long member; a top-level `&`.

Round 13, the reviews of round 12:
  R6W     the reason a moderate review gives; a <label> past a closed
          <details>' summary; a <legend>'s title; a <label for> axe-core
          does not see; more generic elements; a drawing's <text>.
  R6X     `&` and `:scope` in an @scope with a limit, a bare one, a
          shadow root's stylesheet; class lists split at ASCII white
          space; a syntax error past soupsieve's limit; escapes; `>
          :scope` and siblings in @scope.

Round 14, the reviews of round 13 (R6Y, R6Z): a <label> in a closed
          <details>' summary; a drawing's text parts; the reasons; a nested
          @scope's root; :scope by compound; @scope's subjects; class lists
          in every reader; escapes of zero and surrogates.
"""
import base64
import json
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bellbriar_harness import cli                                  # noqa: E402
from bellbriar_harness import redact as R                          # noqa: E402
from bellbriar_harness import style as ST                          # noqa: E402
from bellbriar_harness.engine import load_rulebook, run_page       # noqa: E402
from bellbriar_harness.model import FAIL, NEEDS_REVIEW             # noqa: E402
from tests.test_fetch_hardening import HAVE_BROWSER, _WHY          # noqa: E402
from tests.test_part_r5 import (PAGE, TestRulesRound2,             # noqa: E402
                                TestRulesRound3, _echo_site, run, tmpdir)

RB = load_rulebook()


def page(body, head=""):
    return TestRulesRound2.page(None, f"<main><h1>x</h1>{body}</main>",
                                head=head)


#: A link named by text a rule may hide (`.lbl`).
LINK = '<a href="/x"><span class="lbl">Cart</span></a>'


def link_fails(css):
    """Does bb-link-name fail LINK under the page's own `css`?"""
    got = TestRulesRound2.found(page(LINK, head=f"<style>{css}</style>"),
                                "bb-link-name")
    return got == (True, [(FAIL, "blocker")])


# ---------------------------------------------------------------------------
# R6A: the runtime, recording and guard side
# ---------------------------------------------------------------------------

class TestSecretsR6Round1(unittest.TestCase):
    """R6A-1 to R6A-3, R6A-5 to R6A-7."""

    PASSWORD = "Zephyr!Quill.4471"

    def test_the_authorization_header(self):
        """R6A-1: base64 of "user:password" and of the password alone, in
        either alphabet, padded or not."""
        got = R.basic_auth_tokens("u", "Zephyr!Quill.4471~")
        for raw in (b"u:Zephyr!Quill.4471~", b"Zephyr!Quill.4471~"):
            for enc in (base64.b64encode(raw), base64.urlsafe_b64encode(raw)):
                token = enc.decode()
                with self.subTest(token=token):
                    self.assertIn(token, got)
                    self.assertIn(token.rstrip("="), got)

    def test_an_echoed_authorization_header(self):
        """R6A-1, end to end: a page that echoes the request's headers
        quotes the header; nothing the run records holds its base64."""
        from tests.test_fetch_hardening import _Site

        def hdr(h):
            sent = h.headers.get("Authorization")
            if not sent:
                h.send_response(401)
                h.send_header("WWW-Authenticate", 'Basic realm="t"')
                h.send_header("Content-Length", "0")
                h.end_headers()
                return
            body = PAGE.format('<p>Authorization <input readonly value="'
                               + sent + '"></p>').encode()
            h.send_response(200)
            h.send_header("Content-Type", "text/html")
            h.send_header("Content-Length", str(len(body)))
            h.end_headers()
            h.wfile.write(body)
        site = _Site({"/hdr": hdr})
        self.addCleanup(site.stop)
        d = tmpdir(self)
        (d / "pw").write_text(self.PASSWORD, encoding="utf-8")
        code, out, err = run("--url", f"{site.base}/hdr", "--no-render",
                             "--http-user", "u", "--http-password-file",
                             d / "pw", "--json", d / "r.json", "--fail-on",
                             "never")
        self.assertEqual(code, 0, err)
        text = (d / "r.json").read_text() + out + err
        token = base64.b64encode(b"u:" + self.PASSWORD.encode()).decode()
        self.assertNotIn(token.rstrip("="), text)
        self.assertIn("Basic REDACTED", text)

    def test_a_quoted_value_is_scrubbed_before_it_is_cut(self):
        """R6A-2: a rendered-run message quotes a value cut to 40
        characters only after the run's secrets are replaced in it."""
        from bellbriar_harness import checks_rendered as CR
        secret = "tok_9f8e7d6c5b4a39281706f5e4d3c2b1a0"
        token = R.set_run_secrets(secrets=[secret])
        try:
            got = CR._quoted("zz-CA-" + secret, 40)
        finally:
            R.reset_run_secrets(token)
        self.assertEqual(got, "zz-CA-REDACTED")

    def test_the_password_escaped_twice(self):
        """R6A-3: "%" or "&" escaped again, as a redirect or a page that
        escapes twice writes it."""
        for text in ("http://h/ok/Kq7%2520vX!p2$Lm9/",
                     "Kq7 vX&amp;#33;p2$Lm9", "Kq7&amp;nbsp;vX!p2$Lm9",
                     "Kq7%2520vX%2521p2%2524Lm9"):
            with self.subTest(text=text):
                self.assertTrue(cli._password_in("Kq7 vX!p2$Lm9", [text]))

    def test_a_redirect_to_the_password_encoded_twice(self):
        """R6A-3, end to end: refused, and nothing records or prints it."""
        from tests.test_fetch_hardening import _Site, send

        def moved(h):
            h.send_response(302)
            h.send_header("Location", "/ok/Kq7%2520vX!p2$Lm9/")
            h.send_header("Content-Length", "0")
            h.end_headers()
        site = _Site({"/r": moved, "/ok/Kq7%2520vX!p2$Lm9/": send(
            PAGE.format("<p>x</p>").encode())})
        self.addCleanup(site.stop)
        d = tmpdir(self)
        (d / "pw").write_text("Kq7 vX!p2$Lm9", encoding="utf-8")
        code, out, err = run("--url", f"{site.base}/r", "--no-render",
                             "--http-user", "u", "--http-password-file",
                             d / "pw", "--json", d / "r.json", "--bundle",
                             d / "b.json", "--fail-on", "never")
        self.assertEqual(code, 2, err)
        self.assertIn("holds the --http-user password", err)
        self.assertFalse((d / "b.json").exists())
        report = (d / "r.json").read_text() if (d / "r.json").exists() else ""
        self.assertNotIn("p2$lm9", (report + out + err).lower())

    def test_long_runs_of_white_space_stay_linear(self):
        """R6A-5: a password whose first word a run of encoded white space
        can hold, then an inner run."""
        for password, run_of in (("a quick brown fox 4471", "%0a"),
                                 ("0 Zephyr-Quill-4471", "%20"),
                                 ("+ Zephyr-Quill-4471", "+"),
                                 ("p Zephyr-Quill-4471", "&nbsp")):
            with self.subTest(password=password):
                pattern = R.password_pattern(password)
                start = time.monotonic()
                pattern.search('<a href="/x' + run_of * 20000 + 'y">')
                self.assertLess(time.monotonic() - start, 5)

    def test_no_locator_step_is_named_for_the_password(self):
        """R6A-6: an element whose name holds it is written by its place,
        as an id holding it is."""
        token = R.set_run_secrets(passwords=[self.PASSWORD])
        try:
            got = run_page(page('<zephyr!quill.4471><a href="/cart"></a>'
                                '</zephyr!quill.4471>'), "t.html", RB)
        finally:
            R.reset_run_secrets(token)
        steps = [s for r in got.results if r.rule_id == "bb-link-name"
                 for f in r.findings for s in f.selector or ()]
        self.assertTrue(steps)
        self.assertNotIn("quill", " ".join(steps).lower())

    def test_the_other_case_of_a_letter_encoded(self):
        """R6A-7: a letter outside ASCII, in the other case, as a URL or
        markup encodes it."""
        for text in ("P%C3%84SSWORT!2026X", "P%C4SSWORT!2026X",
                     "P&#196;SSWORT!2026X", "P&#xC4;sswort!2026x",
                     "P&Auml;SSWORT!2026X"):
            with self.subTest(text=text):
                self.assertTrue(cli._password_in("P\u00e4sswort!2026x",
                                                 [text]))


@unittest.skipUnless(HAVE_BROWSER, _WHY)
class TestDrawingMarksR6Round1(unittest.TestCase):
    """R6A-4: a drawing's and MathML's parts carry every mark but a
    drawing's <title> and <desc> (each case checked in Chromium 141)."""

    def test_hidden_parts_name_nothing(self):
        site = _echo_site(self, lambda t: PAGE.format(
            "<style>.cvh{content-visibility:hidden}.vh{visibility:hidden}"
            ".vv{visibility:visible}.dn{display:none}</style>"
            # Chromium names each of these nothing.
            '<button id="c1" aria-labelledby="c1t"></button><svg width="80" '
            'height="20"><g id="c1t" class="cvh vh"><text y="15">Save</text>'
            '</g></svg><button id="c2" aria-labelledby="c2s"></button><svg '
            'id="c2s" width="80" height="20"><g class="cvh vh"><text y="15" '
            'class="vv">Save</text></g></svg><button id="c3" aria-labelledby='
            '"c3s"></button><svg id="c3s" width="80" height="20"><g class='
            '"vh"><text y="15">Save</text></g></svg><button id="c4" '
            'aria-labelledby="c4m"></button><math id="c4m"><mtext class="cvh">'
            'Save</mtext></math><button id="c6" aria-labelledby="c6t">'
            '</button><svg width="80" height="20"><text id="c6t" y="15" '
            'class="cvh vh">'
            'Save</text></svg><button id="d6" aria-labelledby="d6s"></button>'
            '<svg id="d6s" width="80" height="20"><text y="15" class="dn">'
            'Save</text></svg>'
            # And these "Save", "Save Go" or "Go".
            '<button id="ok" aria-labelledby="oks"></button><svg id="oks" '
            'width="80" height="20"><text y="15">Save</text></svg><button '
            'id="d1" aria-labelledby="d1t"></button><svg width="80" height='
            '"20"><defs><text id="d1t" y="15">Save</text></defs></svg><button'
            ' id="d5" aria-labelledby="d5s"></button><svg id="d5s" width="80"'
            ' height="20"><g class="dn"><text y="15">Save</text></g><text '
            'y="15">Go</text></svg><button id="d7"><svg role="img" width="20"'
            ' height="20"><title>Save</title><rect width="5" height="5"/>'
            '</svg></button><button id="d24" aria-labelledby="d24s"></button>'
            '<svg id="d24s" width="80" height="20"><g class="dn"><title>Save'
            '</title></g></svg><button id="d30"><svg width="20" height="20" '
            'role="img"><title class="dn">Save</title></svg></button>'))
        d = tmpdir(self)
        code, _out, err = run("--url", f"{site.base}/p", "--json",
                              d / "r.json", "--fail-on", "never")
        self.assertEqual(code, 0, err)
        report = json.loads((d / "r.json").read_text())
        failed = " ".join(f["snippet"] for p in report["pages"]
                          for f in p["findings"] if f["verdict"] == "fail"
                          and f["rule_id"] == "bb-button-name")
        for b in ("c1", "c2", "c3", "c4", "c6", "d6"):
            self.assertIn(f'id="{b}"', failed)
        for b in ("ok", "d1", "d5", "d7", "d24", "d30"):
            self.assertNotIn(f'id="{b}"', failed)


# ---------------------------------------------------------------------------
# R6B: the rules and claims side
# ---------------------------------------------------------------------------

class TestOwnStyleR6Round1(unittest.TestCase):
    """R6B-1 to R6B-6, R6B-10: the page's own <style> as Chromium 141 reads
    it (each case checked there, at 1280 pixels)."""

    def test_url_is_one_token(self):
        """R6B-1: a quote or a bracket in an unquoted url() is a character
        of the URL, in a style attribute and in a stylesheet."""
        for attr in ('"background:url(it\'s.png);display:none"',
                     '"background:url(a[1.png);display:none"',
                     '"background:url(a(1.png);display:none"',
                     "'background:url(a\"b.png);display:none'"):
            with self.subTest(style=attr):
                self.assertEqual(TestRulesRound2.found(page(
                    f'<a href="/x"><span style={attr}>Cart</span></a>'),
                    "bb-link-name"), (True, [(FAIL, "blocker")]))
        for css in (".lbl{background:url(a[1.png);display:none}",
                    ".z{background:url(a[1.png)} .lbl{display:none}",
                    ".z{background:url(a(1.png)} .lbl{display:none}",
                    ".z{background:url(it's.png)} .lbl{display:none}",
                    ".z{background:url(a{1.png)} .lbl{display:none}"):
            with self.subTest(css=css):
                self.assertTrue(link_fails(css))

    def test_a_long_style_attribute_is_read_once(self):
        """R6B-2: a hero image's 40 KB data: URL, read for each of 300
        links inside it."""
        hero = ('<section style="background-image:url(data:image/jpeg;base64,'
                + "A" * 40000 + ');background-size:cover"><div><div><ul>'
                + "".join(f'<li><a href="/p{i}">Product {i}</a> <button>Add'
                          "</button></li>" for i in range(300))
                + "</ul></div></div></section>")
        start = time.monotonic()
        got = run_page(page(hero), "t.html", RB)
        self.assertLess(time.monotonic() - start, 8)
        self.assertFalse([r.rule_id for r in got.results if r.errored])

    #: Media queries measured in Chromium 141: known (the query holds or
    #: its `not` does) or not.
    KNOWN = (
        '(width)', '(width: 1px)', '(width: 0)', '(width: -1px)',
        '(width: 1PX)', '(width: 1\\70x)', '(width: .5px)', '(width: 1e1px)',
        '(width: 1px/**/)', '(width/**/: 1px)', '(WIDTH: 1PX)',
        '(\\77idth: 1px)', '(hover: hover)', '(orientation: LANDSCAPE)',
        '(prefers-color-scheme: Dark)', '(color)', '(color: -1)',
        '(color: +1)', '(color: calc(1.5))', '(min-color: 2)', '(grid: 1.0)',
        '(grid: -0)', '(resolution: 96dpi)', '(resolution: -0dppx)',
        '(resolution: calc(-1dppx))', '(-webkit-min-device-pixel-ratio: 2)',
        '(-webkit-device-pixel-ratio)', '(-webkit-device-pixel-ratio: 1.5)',
        '(-webkit-device-pixel-ratio >= 1)',
        '(-webkit-min-device-pixel-ratio >= 1)', '(aspect-ratio: 16/9)',
        '(aspect-ratio: 16 / 9)', '(aspect-ratio: 1px)',
        '(aspect-ratio: 1/-0)', '(aspect-ratio: 1px/1)',
        '(aspect-ratio: calc(1px / 1px))', '(min-aspect-ratio: 16/9)',
        '(dynamic-range: high)', '(horizontal-viewport-segments > 0)',
        '(width > 1px)', '(width > 0)', '(width = 1px)',
        '(1px < width < 2000px)', '(2000px > width > 1px)', '(hover = hover)',
        '(orientation > landscape)', '(\\77idth > 1px)',
        '(calc(1px) < width)', '(width: calc(1px))',
        '(width: calc(1px + 1px))', '(width: calc(2 * 1px))',
        '(width: calc(1px * 1px / 1px))', '(width: calc(1px - 1px))',
        '(width: min(1px, 2px))', '(width: max(1px))',
        '(width: clamp(1px, 2px, 3px))',
        '(width: round(nearest, 1.4px, 1px))',
        '(width: calc(sign(1px) * 1px))', '(width: calc(sin(1) * 1px))',
        '(width: calc(asin(1) / 1deg * 1px))', '(width: calc(e * 1px))',
        '(width: calc(progress(1px, 0px, 2px) * 1px))',
        '(width: -webkit-calc(1px + 1px))', '(width: CALC(1PX))',
        '(width: calc(1\\70x))', '(width: calc(1px)', '(width: min(1px, 2px)',
        '(color: calc(1px / 1px))', '(color: calc(50% / 1%))',
        '(resolution: calc(1x / 1x * 1x))', '(resolution: 2dppx)',
        '(min-resolution: 2dppx)',
    )
    UNKNOWN = (
        '(min-width: 40 em)', '(max-width: 50%)', '(min-width: 0\\0)',
        '(min-width: 1px\\9)', '(min-width: "1px")',
        '(min-width: 1px !important)', '(min-width: $screen-md)',
        '(min-width: @screen-md)', '(min-width: {{bp}})',
        '(min-width: calc (1px))', '(width:)', '(width: \\31px)',
        '(width: 5.px)', '(width: 1px;)', '(width: 1px,)', '(hover: banana)',
        '(orientation: portait)', '(orientation: l\\andscape)',
        '(prefers-color-scheme: darkk)', '(color: 1.0)', '(color: 1e0)',
        '(grid: 0.5)', '(resolution: -1dppx)', '(resolution: 1px)',
        '(-webkit-min-device-pixel-ratio)',
        '(min--webkit-device-pixel-ratio: abs(-1px))', '(aspect-ratio: 1deg)',
        '(aspect-ratio: 1foo)', '(aspect-ratio: 50%)', '(aspect-ratio: -1/2)',
        '(aspect-ratio: 1 / 1 / 1)', '(aspect-ratio: 1px\\9)',
        '(aspect-ratio: calc(1deg))', '(dynamic-range)',
        '(min-horizontal-viewport-segments: 1)', '(width > 10)',
        '(width > red)', '(width => 1px)', '(1px < width > 2px)',
        '(width >= 1px >= 0)', '(1px < = width)', '(min-width > 1px)',
        '(width: calc(1))', '(width: calc(1dppx))', '(width: calc(50%))',
        '(width: calc(1px + 50%))', '(width: calc(1px * 2px))',
        '(width: calc(1px / 0px))', '(width: calc(1px+1px))',
        '(width: calc(1px -1px))', '(width: calc(1px + 0))',
        '(width: calc((1px)+(1px)))', '(width: min(1px, 2))',
        '(width: clamp(1px, 2px))', '(width: clamp(none, 1px, 2px))',
        '(width: round(1.4px))', '(width: round(down, 1.4px))',
        '(width: round(foo, 1px, 1px))', '(width: sign(1px))',
        '(width: abs(1))', '(width: calc(sin(1px) * 1px))',
        '(width: calc(pow(2px, 2)))', '(width: sqrt(4px))',
        '(width: exp(1px))', '(width: calc(1px * -pi))',
        '(width: calc(1px * +infinity))',
        '(width: calc(progress(1px from 0px to 2px) * 1px))',
        '(width: hypot(3px, 4))', '(width: mod(5px, 2))',
        '(width: -webkit-min(1px, 2px))', '(width: var(--x))',
        '(width: env(safe-area-inset-left, 1px))',
        '(width: calc(sibling-index() * 1px))', '(width: random(1px, 2px))',
        '(color: calc(1%))', '(resolution: abs(-1px))', '(max-width: 768)',
        '(aspect-ratio: 1/1px)',
    )

    def test_media_queries_as_measured(self):
        """R6B-3, R6B-4: a feature with a value of the type it takes, by
        name alone where that holds, compared in a range; anything else
        unknown, which holds nowhere, its `not` neither. A math function
        by the type it computes."""
        for query in self.KNOWN + self.UNKNOWN:
            for text in (query, "not " + query, "screen and " + query):
                with self.subTest(query=text):
                    got = ST._media_kind(text)
                    if query in self.KNOWN:
                        self.assertIn(got, ("conditional", "always"))
                    else:
                        self.assertIsNone(got)

    def test_a_math_function_by_its_type_not_its_value(self):
        """Where Chromium 141 checks the value a math function computes as
        it reads the query, the type alone is read (style._math_type):
        `(width: calc(0))` is known there, a number here; `(grid:
        calc(2))` and `(aspect-ratio: calc(-1))` are not known there."""
        self.assertIsNone(ST._media_kind("(width: calc(0))"))
        self.assertEqual(ST._media_kind("(grid: calc(2))"), "conditional")
        self.assertEqual(ST._media_kind("(aspect-ratio: calc(-1))"),
                         "conditional")

    def test_the_value_end_to_end(self):
        """R6B-3: a unitless width, an IE hack."""
        for at in ("@media screen and (max-width: 768)",
                   "@media screen and (min-width:0\\0)",
                   "@media (hover: banana)",
                   "@media (-webkit-min-device-pixel-ratio)"):
            with self.subTest(at=at):
                self.assertTrue(link_fails(
                    f".lbl{{display:none}} {at}{{.lbl{{display:inline}}}}"))
        self.assertFalse(link_fails(
            ".lbl{display:none} @media (-webkit-device-pixel-ratio >= 1)"
            "{.lbl{display:inline}}"))

    def test_three_valued_logic(self):
        """R6B-5: false and unknown is false, true or unknown is true; a
        `not` of unknown is unknown (checked in Chromium 141 at 1280 and 0
        pixels wide)."""
        for query, kind in (
                ("not ((max-width: 1px) and (min-width: var(--bp)))",
                 "conditional"),
                ("not ((min-width: 2000px) and (foo: 1))", "conditional"),
                ("not ((foo: 1) and (max-width: 1px))", "conditional"),
                ("not ((max-width: 1px) and (bar(1)))", "conditional"),
                ("screen and (not ((min-width: 2000px) and (foo: 1)))",
                 "conditional"),
                ("not ((min-width:1px) and foo(1))", "conditional"),
                ("not ((min-width: 2000px) or (foo: 1))", None),
                ("not ((min-width: 1px) or (foo: 1))", None),
                ("(min-width: 1px) and (foo: 1)", None),
                ("(min-width: 1px) or (foo: 1)", "conditional"),
                ("not (foo: 1)", None),
                ("not print and (foo: 1)", "always"),
                ("print and (min-width: 1px)", None)):
            with self.subTest(query=query):
                self.assertEqual(ST._media_kind(query), kind)
        self.assertFalse(link_fails(
            ":root{--bp:10px} .lbl{display:none} @media not ((max-width: "
            "1px) and (min-width: var(--bp))){.lbl{display:inline}}"))

    def test_any_depth_in_linear_time(self):
        """R6B-6: parentheses nested 400 deep, in a stylesheet and in a
        <style media>, hold as Chromium 141 has them; hostile queries are
        read in linear time; a math function nests 100 deep at most, as
        there."""
        deep = "(" * 400 + "min-width:1px" + ")" * 400
        self.assertFalse(link_fails(
            f".lbl{{display:none}} @media {deep}{{.lbl{{display:inline}}}}"))
        got = run_page(page(LINK, head=(
            f'<style>.lbl{{display:none}}</style><style media="{deep}">'
            ".lbl{display:inline}</style>")), "t.html", RB)
        self.assertFalse([r.rule_id for r in got.results if r.errored])
        for query in ("(" * 300 + "min-width:1px" + " " * 1_000_000
                      + ")" * 300, "(" * 100_000,
                      " and ".join(["(min-width:1px)"] * 50_000),
                      "(width: " + "calc(" * 50_000 + "1px" + ")" * 50_000
                      + ")", "foo(" * 100_000, "(" + "\\77" * 100_000
                      + "idth: 1px)"):
            start = time.monotonic()
            ST._media_kind(query)
            self.assertLess(time.monotonic() - start, 5, query[:40])
        for depth, kind in ((99, "conditional"), (100, None)):
            self.assertEqual(ST._media_kind(
                "(width: calc(" + "(" * depth + "1px" + ")" * depth + "))"),
                kind)
        for depth, kind in ((100, "conditional"), (101, None)):
            self.assertEqual(ST._media_kind(
                "(width: " + "calc(" * depth + "1px" + ")" * depth + ")"),
                kind)

    def test_names_comments_and_white_space(self):
        """A name may be escaped, a comment separates what is on its either
        side (R6D-5), and white space is CSS's own: a no-break space or a
        vertical tab is none."""
        for query, kind in (("scr\\65 en", "always"),
                            ("\\6eot print", "always"),
                            ("not pr\\69 nt", "always"),
                            ("not print and f\\6fo()", "always"),
                            ("\u00a0screen", None), ("screen\u00a0", None),
                            ("not\u00a0print", None), ("not\x0bprint", None),
                            ("/**/screen", "always"),
                            ("not/**/print", "always"),
                            ("(width: 1px/**/)", "conditional")):
            with self.subTest(query=query):
                self.assertEqual(ST._media_kind(query), kind)
        self.assertTrue(link_fails(
            ".lbl{display:none} @media \u00a0screen{.lbl{display:inline}}"))
        self.assertTrue(link_fails(
            ".lbl{display:none} @media\u00a0screen{.lbl{display:inline}}"))
        self.assertFalse(link_fails(
            ".lbl{display:none} @\\6d edia screen{.lbl{display:inline}}"))

    def test_a_stray_closer_in_supports(self):
        """R6B-10: a "]" that closes nothing makes a custom property's
        value invalid; brackets that close pass."""
        for test, fails in (("(--x: ])", True), ("(--x:)", False),
                            ("(--x: {;})", False), ("(--x: [!])", False)):
            with self.subTest(test=test):
                self.assertEqual(link_fails(
                    f".lbl{{display:none}} @supports {test}"
                    "{.lbl{display:inline}}"), fails)


class TestNamespacesR6Round1(unittest.TestCase):
    """R6B-7: a drawing's or MathML's element named as one of HTML's is
    none of HTML's (each case checked in Chromium 141)."""

    def test_no_html_element_by_its_name_alone(self):
        for body, rule in (
                ('<svg width="50" height="20"><button></button></svg>',
                 "bb-button-name"),
                ("<math><button></button></math>", "bb-button-name"),
                ('<div aria-hidden="true"><svg width="50" height="20"><button>'
                 "</button></svg></div>", "bb-aria-hidden-focus"),
                ('<div aria-hidden="true"><math><input></input></math></div>',
                 "bb-aria-hidden-focus"),
                ('<math><input type="image" src="a.png"></input></math>',
                 "bb-img-alt"),
                ('<svg width="50" height="20"><area href="/x"></area></svg>',
                 "bb-img-alt"),
                ('<form><math><input type="email"></input></math></form>',
                 "bb-autocomplete")):
            with self.subTest(body=body):
                applicable, got = TestRulesRound2.found(page(body), rule)
                self.assertEqual(got, [])

    def test_names(self):
        got = TestRulesRound3.names(None, page(
            '<math><input id="m" type="submit"></input></math>'
            '<input id="h" type="submit">'), "m", "h")
        self.assertEqual(got, {"m": "", "h": "Submit"})


class TestVisibilityLaterR6Round1(unittest.TestCase):
    """R6B-8: a visibility only known later on focusable content inside
    invisible content may show it: reviewed (R6D-1)."""

    def test_focusable_content_shown_by_a_custom_property(self):
        self.assertEqual(TestRulesRound2.found(page(
            '<div aria-hidden="true" style="visibility:hidden;--v:visible">'
            '<button style="visibility:var(--v)">Go</button></div>'),
            "bb-aria-hidden-focus"), (True, [(NEEDS_REVIEW, "moderate")]))
        # A rule that hides the container is still reviewed.
        self.assertEqual(TestRulesRound2.found(page(
            '<div aria-hidden="true" class="m"><button>Go</button></div>',
            head="<style>.m{display:none}</style>"),
            "bb-aria-hidden-focus"), (True, [(NEEDS_REVIEW, "moderate")]))


class TestDisplayInheritR6Round1(unittest.TestCase):
    """R6B-9: inherit inside a <details> or a <marquee> takes the display
    of the slot the element is in (measured in Chromium 141)."""

    def test_inherit_in_details_and_marquee(self):
        from bellbriar_harness.checks_static import PageContext
        from bellbriar_harness.model import CURRENT_PAGE
        for body, el_id, display, skips in (
                ('<details open style="display:flex"><summary>S</summary>'
                 '<span id="t" style="display:inherit" hidden="until-found">'
                 "<i>c</i></span></details>", "t", "block", True),
                ('<details open style="display:inline"><summary>S</summary>'
                 '<span id="t" style="display:inherit" hidden="until-found">'
                 "<i>c</i></span></details>", "t", "block", True),
                ('<details open style="display:flex"><summary id="t" '
                 'style="display:inherit" hidden="until-found"><i>c</i>'
                 "</summary></details>", "t", "contents", False),
                ('<marquee style="display:flex"><span id="t" style="display:'
                 'inherit" hidden="until-found"><i>c</i></span></marquee>',
                 "t", "contents", False)):
            with self.subTest(body=body):
                ctx = PageContext.parse(page(body), path="t.html")
                token = CURRENT_PAGE.set(ctx)
                try:
                    el = ctx.soup.find(id=el_id)
                    self.assertEqual(ST._display_of(el), display)
                    self.assertEqual(ST.skips_content(el), skips)
                finally:
                    CURRENT_PAGE.reset(token)


# ---------------------------------------------------------------------------
# Round 2, R6C: the runtime, recording and guard side
# ---------------------------------------------------------------------------

class TestSecretsR6Round2(unittest.TestCase):
    """R6C-1, R6C-2, R6C-4 to R6C-6, R6C-8."""

    PASSWORD = "rKB6id>Yx?ET"
    #: base64 of "u:" and the password: a "+", a "/" and a "=" in it.
    TOKEN = "dTpyS0I2aWQ+WXg/RVQ="

    def test_the_header_in_any_spelling(self):
        """R6C-1: as JSON writes it, percent-encoded in either case (a "+"
        for a space), as a character reference, escaped again."""
        self.assertEqual(base64.b64encode(
            b"u:" + self.PASSWORD.encode()).decode(), self.TOKEN)
        token = R.set_run_secrets(tokens=R.basic_auth_tokens(
            "u", self.PASSWORD))
        try:
            for text in ('{"Authorization": "Basic dTpyS0I2aWQ+WXg\\/RVQ="}',
                         "Basic+dTpyS0I2aWQ%2bWXg%2fRVQ%3d",
                         "Basic%20dTpyS0I2aWQ%2BWXg/RVQ%3D",
                         "dTpyS0I2aWQ+WXg&#47;RVQ=",
                         "dTpyS0I2aWQ+WXg\\u002fRVQ=",
                         "dTpyS0I2aWQ&#43;WXg/RVQ=",
                         "dTpyS0I2aWQ%252BWXg%252FRVQ%253D"):
                with self.subTest(text=text):
                    got = R.scrub_secrets(text)
                    self.assertIn("REDACTED", got)
                    self.assertNotIn("dTpyS0I2", got)
                    self.assertNotIn("RVQ", got)
        finally:
            R.reset_run_secrets(token)

    def test_the_header_end_to_end(self):
        """R6C-1, end to end: a page that writes the header as PHP's
        json_encode, .NET's UrlEncode and Python's quote() write it."""
        import re
        import urllib.parse
        from tests.test_fetch_hardening import _Site

        def hdr(h):
            sent = h.headers.get("Authorization")
            if not sent:
                h.send_response(401)
                h.send_header("WWW-Authenticate", 'Basic realm="t"')
                h.send_header("Content-Length", "0")
                h.end_headers()
                return
            php = json.dumps({"Authorization": sent}).replace("/", "\\/")
            net = re.sub("%[0-9A-F]{2}", lambda m: m.group(0).lower(),
                         urllib.parse.quote_plus(sent))
            body = PAGE.format(
                "<p><input readonly value='" + php + "'><input readonly "
                'value="' + net + '"><input readonly value="'
                + urllib.parse.quote(sent, safe="/") + '"></p>').encode()
            h.send_response(200)
            h.send_header("Content-Type", "text/html")
            h.send_header("Content-Length", str(len(body)))
            h.end_headers()
            h.wfile.write(body)
        site = _Site({"/hdr": hdr})
        self.addCleanup(site.stop)
        d = tmpdir(self)
        (d / "pw").write_text(self.PASSWORD, encoding="utf-8")
        code, out, err = run("--url", f"{site.base}/hdr", "--no-render",
                             "--http-user", "u", "--http-password-file",
                             d / "pw", "--json", d / "r.json", "--bundle",
                             d / "b.json", "--fail-on", "never")
        self.assertEqual(code, 0, err)
        text = ((d / "r.json").read_text() + (d / "b.json").read_text()
                + out + err)
        self.assertNotIn("dTpyS0I2", text)
        self.assertIn("REDACTED", text)

    def test_a_redirect_to_the_header(self):
        """R6C-2: a server that sends the run to a URL holding the header's
        base64, as written or percent-encoded: the page is refused, and
        nothing records or prints where it went."""
        from tests.test_fetch_hardening import _Site, send
        quoted = "dTpyS0I2aWQ%2BWXg%2FRVQ%3D"

        def moved(to):
            def go(h):
                h.send_response(302)
                h.send_header("Location", to)
                h.send_header("Content-Length", "0")
                h.end_headers()
            return go
        ok = send(PAGE.format("<p>x</p>").encode())
        site = _Site({"/r": moved(f"/ok/{self.TOKEN}/"),
                      "/rq": moved(f"/ok/{quoted}/"),
                      f"/ok/{self.TOKEN}/": ok, f"/ok/{quoted}/": ok})
        self.addCleanup(site.stop)
        d = tmpdir(self)
        (d / "pw").write_text(self.PASSWORD, encoding="utf-8")
        code, out, err = run("--url", f"{site.base}/r", "--url",
                             f"{site.base}/rq", "--no-render", "--http-user",
                             "u", "--http-password-file", d / "pw", "--json",
                             d / "r.json", "--bundle", d / "b.json",
                             "--fail-on", "never")
        self.assertEqual(code, 2, err)
        for path in ("/r", "/rq"):
            self.assertIn(f"{site.base}{path}: what its record would say of "
                          "it (where it went, or a note on it) holds the "
                          "Authorization header", err)
        self.assertFalse((d / "b.json").exists())
        report = (d / "r.json").read_text() if (d / "r.json").exists() else ""
        self.assertNotIn("dTpyS0I2", report + out + err)

    def test_a_plus_beside_white_space_stays_linear(self):
        """R6C-4: the password's own "+" between runs of white space, and
        a page with a long run of "+"."""
        pattern = R.password_pattern("Qz" + " +" * 5 + " Wy")
        start = time.monotonic()
        self.assertIsNone(pattern.search("Qz" + "+" * 200))
        self.assertLess(time.monotonic() - start, 2)
        self.assertTrue(cli._password_in("Qz + + + + + Wy",
                                         ["Qz%20+%20+ + &nbsp;+ + Wy"]))

    def test_a_long_inner_run_of_white_space(self):
        """R6C-5: a run longer than the bound on encoded white space is
        found, as itself and encoded."""
        password = "Zephyr" + " " * 33 + "Quill4471"
        for run_of in (" ", "&nbsp;", "%20"):
            with self.subTest(run_of=run_of):
                self.assertTrue(cli._password_in(password, [
                    "Zephyr" + run_of * 33 + "Quill4471"]))

    def test_no_locator_step_is_named_for_the_header(self):
        """R6C-6: an element named for the header's base64, which the HTML
        parser lowercased."""
        password = "Zephyr!Quill.4471"
        name = base64.b64encode(b"u:" + password.encode()).decode()
        name = name.rstrip("=")
        token = R.set_run_secrets(passwords=[password],
                                  tokens=R.basic_auth_tokens("u", password))
        try:
            got = run_page(page(f'<{name}><a href="/cart"></a></{name}>'),
                           "t.html", RB)
        finally:
            R.reset_run_secrets(token)
        steps = [s for r in got.results if r.rule_id == "bb-link-name"
                 for f in r.findings for s in f.selector or ()]
        self.assertTrue(steps)
        self.assertNotIn(name.lower(), " ".join(steps).lower())

    def test_escaped_again_and_the_capital_sharp_s(self):
        """R6C-8: "&" written again as a character reference, "%" as one;
        the capital sharp s for a password's sharp s, encoded."""
        for text in ("Kq7 vX&#38;#33;p2$Lm9", "Kq7&#38;#32;vX!p2$Lm9",
                     "Kq7 vX&#37;21p2$Lm9"):
            with self.subTest(text=text):
                self.assertTrue(cli._password_in("Kq7 vX!p2$Lm9", [text]))
        for text in ("STRA&#7838;E-QUILL-4471", "STRA%E1%BA%9EE-QUILL-4471",
                     "STRA\u1e9eE-QUILL-4471"):
            with self.subTest(text=text):
                self.assertTrue(cli._password_in("Stra\u00dfe-Quill-4471",
                                                 [text]))


#: Parts of a drawing or of MathML that are not rendered, as Chromium 141
#: names what holds them: (id, markup, named). "L": a button labelled by a
#: drawing; "A": a drawing's link; "M": a button labelled by MathML.
_UNRENDERED = (
    ("n1", "L", '<switch><text y="15">One</text><text y="15">Two</text>'
     "</switch>", True),
    ("n2", "L", "<linearGradient><text>Save</text></linearGradient>", True),
    ("n3", "L", '<g class="dn"><text y="15">Save</text></g>', True),
    ("n4", "L", '<defs><text y="15">Save</text></defs>', True),
    ("n5", "A", '<switch><foreignObject width="80" height="20" '
     'requiredFeatures="http://www.w3.org/TR/SVG11/feature#Extensibility">'
     '<div xmlns="http://www.w3.org/1999/xhtml">Node</div></foreignObject>'
     '<text y="15">Node</text></switch>', True),
    ("n6", "M", '<mspace width="10px"><mtext>Save</mtext></mspace>', True),
    ("n7", "A", '<svg><switch><text y="15">One</text><text y="15">Two</text>'
     "</switch></svg>", True),
    ("n8", "L", '<g><g class="dn"><text y="15">Save</text></g></g>', True),
    ("n9", "L", '<g class="vh"><g class="dn"><text y="15" class="vv">Save'
     "</text></g></g>", True),
    ("n10", "L", '<a href="/x"><g><text y="15">Save</text></g></a>', True),
    ("e1", "L", '<text y="15" class="dn">Save</text>', False),
    ("e2", "L", '<switch><g><rect width="5" height="5"/></g><g><text y="15">'
     "Save</text></g></switch>", False),
    ("e3", "L", "<metadata><rdf:RDF><cc:Work><dc:title>Save</dc:title>"
     "</cc:Work></rdf:RDF></metadata>", False),
    ("e4", "L", '<foo><text y="15">Save</text></foo>', False),
    ("e5", "A", '<rect width="80" height="20"/><g><switch><foreignObject '
     'width="80" height="20" requiredFeatures="http://www.w3.org/TR/SVG11/'
     'feature#Extensibility"><div xmlns="http://www.w3.org/1999/xhtml">API'
     '</div></foreignObject><text y="15">Fallback</text></switch></g>',
     False),
    ("e6", "L", "<g><linearGradient><text>Save</text></linearGradient></g>",
     False),
    ("e7", "M", '<mtext class="dn">Save</mtext>', False),
    ("e8", "L", '<text systemLanguage="xx" y="15">Save</text>', False),
    ("e9", "L", "<tspan>Save</tspan>", False),
    ("e10", "A", '<g><switch><text y="15"></text><text y="15">Two</text>'
     "</switch></g>", False),
)


def _unrendered_page(cases) -> str:
    out = []
    for i, kind, inner, _named in cases:
        if kind == "A":
            out.append(f'<svg width="80" height="20"><a id="{i}" '
                       f'xlink:href="/x">{inner}</a></svg>')
        elif kind == "M":
            out.append(f'<button id="{i}" aria-labelledby="{i}m"></button>'
                       f'<math id="{i}m">{inner}</math>')
        else:
            out.append(f'<button id="{i}" aria-labelledby="{i}s"></button>'
                       f'<svg id="{i}s" width="80" height="20">{inner}</svg>')
    return PAGE.format(
        "<style>.dn{display:none}.vh{visibility:hidden}"
        ".vv{visibility:visible}</style>" + "".join(out))


@unittest.skipUnless(HAVE_BROWSER, _WHY)
class TestDrawingMarksR6Round2(unittest.TestCase):
    """R6C-3: a part of a drawing or of MathML that is not rendered is read
    into a name as Chromium 141 reads it (each case measured there): not
    one whose own display is none (a <g> but), one Chromium does not know,
    a <metadata>'s, one whose conditions fail, a <g> a <switch> passes
    over; what a <switch> passes over, a gradient or a shape holds only
    where no <g> stands between it and where the name starts; what <defs>
    or a <g> with display:none holds, always. Content of such a <g> or of
    <defs> is not rendered: it takes no focus."""

    def test_parts_not_rendered(self):
        site = _echo_site(self, lambda t: _unrendered_page(_UNRENDERED))
        d = tmpdir(self)
        code, _out, err = run("--url", f"{site.base}/p", "--json",
                              d / "r.json", "--fail-on", "never")
        self.assertEqual(code, 0, err)
        report = json.loads((d / "r.json").read_text())
        failed = " ".join(f["snippet"] for p in report["pages"]
                          for f in p["findings"] if f["verdict"] == "fail"
                          and f["rule_id"] in ("bb-button-name",
                                               "bb-link-name"))
        for i, _kind, _inner, named in _UNRENDERED:
            with self.subTest(case=i):
                self.assertEqual(f'id="{i}"' not in failed, named)

    def test_no_focus_in_what_is_not_rendered(self):
        site = _echo_site(self, lambda t: PAGE.format(
            "<style>.dn{display:none}</style>"
            '<div aria-hidden="true"><svg width="80" height="20"><g '
            'class="dn"><a href="/x"><text y="15">x</text></a></g></svg>'
            '</div><div aria-hidden="true"><svg width="80" height="20"><defs>'
            '<a href="/y"><text y="15">y</text></a></defs></svg></div>'))
        d = tmpdir(self)
        code, _out, err = run("--url", f"{site.base}/p", "--json",
                              d / "r.json", "--fail-on", "never")
        self.assertEqual(code, 0, err)
        report = json.loads((d / "r.json").read_text())
        self.assertEqual([f for p in report["pages"] for f in p["findings"]
                          if f["rule_id"] == "bb-aria-hidden-focus"
                          and f["verdict"] == "fail"], [])


# ---------------------------------------------------------------------------
# Round 2, R6D: the rules and claims side
# ---------------------------------------------------------------------------

class TestOwnStyleR6Round2(unittest.TestCase):
    """R6D-3 to R6D-10: the page's own <style> as Chromium 141 reads it
    (each case measured there, at 1280 pixels)."""

    #: Known in Chromium 141 (the query holds or its `not` does), or not.
    KNOWN = (
        "(hover: \\68over)", "(orientation: \\6c andscape)",
        "(hover: ho\\76 er)", "(hover: \\hover)",
        "(prefers-color-scheme: d\\61rk)", "(hover: \\000068over)",
        "(hover: \\48OVER)", "(min-\\77 idth: 1px)", "(\\6d in-width: 1px)",
        "(\\77 idth > 1px)", "(1px < \\77 idth)", "(\\64 evice-width: 1px)",
        "(width: 1\\70 x)", "(width: 1p\\78)", "(width: 1\\50 X)",
        "(width >/**/= 1px)", "(width/**/>=/**/1px)",
        "(width: calc(1px /**/ + /**/ 1px))", "(width: calc(1px/**/ + 1px))",
        "(width/**/: 1px)", "(\\hover)", "(h\\over)",
        "(-webkit-device-pixel-ratio: round(1, 2))",
        "(-webkit-device-pixel-ratio: round(1))",
        "(-webkit-device-pixel-ratio: round(nearest, 1))",
    )
    UNKNOWN = (
        "(hover: hover\\ )", "(hover: \\-hover)",
        "(width: calc(1px/**/+/**/1px))", "(width: calc(1/**/px))",
        "(width: 1/**/px)", "(wid/**/th: 1px)",
        "(-webkit-device-pixel-ratio: round(1, 2, 3))",
        "(width: round(1px))", "(x: url(a))", "(url(a))", "(width < = 1px)",
        "(width: 1px\u00a0)", "(width: \u212apx)", "(hover: \u212aover)",
        "(\u212awidth: 1px)", "(scan: progre\u017f\u017five)",
    )

    def test_escapes_comments_and_math_as_measured(self):
        """R6D-3, R6D-4, R6D-5, R6D-9: a keyword, a name and a unit with
        escapes in them; a comment separates, but is no white space;
        round() takes two of one type or one number; ASCII's letters alone
        are matched in either case."""
        for query in self.KNOWN + self.UNKNOWN:
            for text in (query, "not " + query, "screen and " + query):
                with self.subTest(query=text):
                    got = ST._media_kind(text)
                    if query in self.KNOWN:
                        self.assertIn(got, ("conditional", "always"))
                    else:
                        self.assertIsNone(got)

    #: Media query lists, and whether one holds at 1280 pixels in Chromium
    #: 141.
    LISTS = (
        ("(min-width: 1px) or (x: ])", False),
        ("(min-width: 1px) or (x: })", False),
        ("(min-width: 1px) or x(])", False),
        ('(min-width: 1px) or (x: "a\nb")', False),
        ('(min-width: 1px) or (x: "a\fb")', False),
        ("(min-width: 1px) or (x: url(a b))", False),
        ("(min-width: 1px) or (x: url(it's))", False),
        ("(min-width: 1px) or (x: \\75 rl(a b))", False),
        ("(min-width: 1px) or (x: [a)])", False),
        ("(min-width: 1px) or url(a)", False),
        ("url(a) or (min-width: 1px)", False),
        ("screen ), print", False), ("\\6e ot screen", False),
        ("scre/**/en", False),
        ("(min-width: 1px) or (x: #url(a b))", True),
        ("(min-width: 1px) or (x: xurl(a b))", True),
        ("(min-width: 1px) or (x: [a])", True),
        ('print, (min-width: 1px) or (x: "a,b")', True),
        ("print, (min-width: 1px) or (x: [a,b])", True),
        ('(min-width: 1px), (x: "a\nb")', True),
        ("(min-width: 1px) or (x: (a)", True),
        ('(min-width: 1px) or (x: "a\\\nb")', True),
        ("\\6e ot print", True), ("screen \\61 nd (min-width: 1px)", True),
        ("screen/**/and/**/(min-width: 1px)", True),
    )

    def test_what_no_query_holds(self):
        """R6D-10: a closer that closes nothing (in a block of another kind
        too), a bad string or a bad url drops the query; a comma or a
        bracket in a string or a block splits nothing."""
        for query, holds in self.LISTS:
            with self.subTest(query=query):
                got = ST._media_kind(query)
                if holds:
                    self.assertIn(got, ("conditional", "always"))
                else:
                    self.assertIsNone(got)

    def test_end_to_end(self):
        """R6D-3 to R6D-6, R6D-10, as a page's rules read them."""
        for at, fails in (("@media (hover: \\68over)", False),
                          ("@media (min-\\77 idth: 1px)", False),
                          ("@media (width >/**/= 1px)", False),
                          ("@media (min-width: 1px) or (x: ])", True),
                          ("@media screen\u00a0", True),
                          ("@media (min-width: 1px)\u00a0", True),
                          ("@media screen\x0b", True),
                          ("\u00a0@media screen", True)):
            with self.subTest(at=at):
                self.assertEqual(link_fails(
                    f".lbl{{display:none}} {at}{{.lbl{{display:inline}}}}"),
                    fails)

    def test_css_white_space_and_important(self):
        """R6D-6: CSS's own white space trims a rule's parts; an escaped
        tab is part of a word (`none\\9`, an old hack, is no display);
        `!important` as CSS reads it; ASCII case alone."""
        for css, fails in (("\u00a0.lbl{display:none}", False),
                           (".lbl{display:none\\9}", False),
                           (".lbl{display:\\9 none}", False),
                           (".lbl{display:none !\u00a0important}", False),
                           (".lbl{display:none\u2003}", False),
                           (".lbl{display:none} .lbl{display:bloc\u212a}",
                            True),
                           (".lbl{display:\\6e one}", True),
                           (".lbl{display:none !IMPORTANT} "
                            ".lbl{display:inline}", True),
                           (".lbl{display:none !\\69mportant} "
                            ".lbl{display:inline}", True),
                           (".lbl{display:none \\!important} "
                            ".lbl{display:inline}", False)):
            with self.subTest(css=css):
                self.assertEqual(link_fails(css), fails)
        for style in ("display:none\\9", "display:none !\u00a0important",
                      "display\\20 :none", "display:\u00a0none"):
            with self.subTest(style=style):
                self.assertEqual(TestRulesRound2.found(page(
                    f'<a href="/x"><span style="{style}">Cart</span></a>'),
                    "bb-link-name"), (True, []))

    def test_url_tokens(self):
        """R6D-7: url( as CSS reads it: its letters escaped or not; not
        where it ends a longer name, a hash or an at-keyword (there a
        quote opens a string)."""
        for value, hides in (("background:\\75 rl(it's.png)", True),
                             ("background:\\url(it's.png)", True),
                             ("--a:u\\rl(it's.png)", True),
                             ("--a:+url(it's.png)", True),
                             ("--a:#url(it's.png)", False),
                             ("--a:@url(it's.png)", False),
                             ("--a:\u00b7url(it's.png)", False),
                             ("--a:\\31 url(it's.png)", False),
                             ("--a:x\\75 rl(it's.png)", False),
                             ("--a:\\\\url(it's.png)", False)):
            with self.subTest(value=value):
                self.assertEqual(TestRulesRound2.found(page(
                    f'<a href="/x"><span style="{value};display:none">'
                    "Cart</span></a>"), "bb-link-name"),
                    (True, [(FAIL, "blocker")] if hides else []))

    def test_ranges_in_linear_time(self):
        """R6D-8: what a pair of parentheses holds is read in place."""
        for query in ("(1px < " * 160000 + "width" + ")" * 160000,
                      "(x: " * 160000 + ")" * 160000,
                      "(aspect-ratio: " + "(1)/" * 50000 + "1)"):
            start = time.monotonic()
            ST._media_kind(query)
            self.assertLess(time.monotonic() - start, 10, query[:20])

    def test_bad_tokens_in_supports(self):
        """R6D-10: a bad url or a bad string makes a custom property's
        value invalid."""
        for test, fails in (("(--x: url(a b))", True),
                            ('(--x: "a\nb")', True),
                            ("(--x: url(it's))", True),
                            ("(--x: url( a ))", False),
                            ('(--x: "a\\\nb")', False)):
            with self.subTest(test=test):
                self.assertEqual(link_fails(
                    f".lbl{{display:none}} @supports {test}"
                    "{.lbl{display:inline}}"), fails)


class TestVisibilityLaterR6Round2(unittest.TestCase):
    """R6D-1: a visibility only known later (var()) on focusable content
    inside invisible content is reviewed: a file run does not read what a
    custom property holds. (Since round 5, one no stylesheet sets, where
    none the run does not read could set it, is read as its fallback, or
    unset: R6J-3; with a linked stylesheet it is reviewed.)"""

    def test_reviewed(self):
        linked = '<link rel="stylesheet" href="x.css">'
        for body, head in (
                ('<div aria-hidden="true" style="visibility:hidden;'
                 '--v:hidden"><button style="visibility:var(--v)">Go'
                 "</button></div>", ""),
                ('<div aria-hidden="true" style="visibility:hidden"><button '
                 'style="visibility:var(--nope)">Go</button></div>', linked),
                ('<div aria-hidden="true" class="h"><button style="'
                 'visibility:var(--v)">Go</button></div>',
                 "<style>.h{visibility:hidden;--v:hidden}</style>")):
            with self.subTest(body=body):
                self.assertEqual(TestRulesRound2.found(page(
                    body, head=head), "bb-aria-hidden-focus"),
                    (True, [(NEEDS_REVIEW, "moderate")]))


class TestDrawingsR6Round2(unittest.TestCase):
    """R6D-2, R6C-9: a drawing's <a> with xlink:href is a link; and, from
    markup, a drawing's <g> with display:none names what it holds and an
    <svg> inside a drawing is one of its parts (checked in Chromium 141)."""

    def test_xlink_href(self):
        self.assertEqual(TestRulesRound2.found(page(
            '<div aria-hidden="true"><svg width="40" height="20"><a '
            'xlink:href="/x"><text y="15">x</text></a></svg></div>'),
            "bb-aria-hidden-focus"), (True, [(FAIL, "serious")]))
        self.assertEqual(TestRulesRound2.found(page(
            '<svg width="80" height="20"><a xlink:href="/x"><rect width="80"'
            ' height="20"/></a></svg>'), "bb-link-name"),
            (True, [(FAIL, "blocker")]))
        self.assertEqual(TestRulesRound2.found(page(
            '<div aria-hidden="true"><math><a href="/x"><mi>x</mi></a>'
            "</math></div>"), "bb-aria-hidden-focus")[1], [])

    def test_names_from_markup(self):
        got = TestRulesRound3.names(None, page(
            '<button id="b" aria-labelledby="s"></button><svg id="s" '
            'width="80" height="20"><g style="display:none"><text y="15">'
            'Save</text></g></svg><button id="c" aria-labelledby="t"></button>'
            '<svg id="t" width="80" height="20"><text y="15" style="display:'
            'none">Save</text></svg><svg width="80" height="20"><a id="a" '
            'href="/x"><svg><text y="15">One</text></svg></a></svg>'),
            "b", "c", "a")
        self.assertEqual(got, {"b": "Save", "c": "", "a": "One"})


# ---------------------------------------------------------------------------
# Round 3, R6E: the runtime, recording and guard side
# ---------------------------------------------------------------------------

class TestSecretsR6Round3(unittest.TestCase):
    """R6E-1, R6E-2, R6E-7 to R6E-9."""

    PASSWORD = TestSecretsR6Round2.PASSWORD
    TOKEN = TestSecretsR6Round2.TOKEN

    def test_a_scripts_escapes(self):
        """R6E-1: a script's \\xHH escapes (Laminas' escapeJs, ESAPI's
        encodeForJavaScript), JSON in JSON (its backslash escaped again),
        and "&" or "%" as a script writes them (Go's JSON of `&#43;`)."""
        token = R.set_run_secrets(tokens=R.basic_auth_tokens(
            "u", self.PASSWORD), passwords=[self.PASSWORD])
        try:
            for text in (r"dTpyS0I2aWQ\x2BWXg\x2FRVQ\x3D",
                         r"dTpyS0I2aWQ+WXg\\\/RVQ=",
                         r"dTpyS0I2aWQ\\u002bWXg\\\\u002fRVQ\\u003d",
                         r"dTpyS0I2aWQ\u0026#43;WXg/RVQ=",
                         r"dTpyS0I2aWQ\x26#43;WXg/RVQ=",
                         r"dTpyS0I2aWQ\u00252BWXg/RVQ=",
                         r"copyHeader('Basic\x20dTpyS0I2aWQ\x2BWXg\x2FRVQ"
                         r"\x3D')"):
                with self.subTest(text=text):
                    got = R.scrub_secrets(text)
                    self.assertNotIn("dTpyS0I2", got)
                    self.assertNotIn("RVQ", got)
                    self.assertTrue(R.holds_secret(text))
            for text in (r"rKB6id\x3EYx\x3FET", r"rKB6id\u003eYx\\u003fET",
                         r"rKB6id\x3eYx\\\\x3fET"):
                with self.subTest(text=text):
                    self.assertTrue(R.holds_password(text))
        finally:
            R.reset_run_secrets(token)

    def test_a_scripts_escapes_end_to_end(self):
        """R6E-1, end to end: a page that writes the header in an onclick,
        as a script escaper writes it, signs no bundle that holds it."""
        from tests.test_fetch_hardening import _Site

        def hdr(h):
            sent = h.headers.get("Authorization")
            if not sent:
                h.send_response(401)
                h.send_header("WWW-Authenticate", 'Basic realm="t"')
                h.send_header("Content-Length", "0")
                h.end_headers()
                return
            js = "".join(c if c.isalnum() else f"\\x{ord(c):02X}"
                         for c in sent)
            body = PAGE.format(
                f"<p><button onclick=\"copyHeader('{js}')\">Copy</button>"
                "</p>").encode()
            h.send_response(200)
            h.send_header("Content-Type", "text/html")
            h.send_header("Content-Length", str(len(body)))
            h.end_headers()
            h.wfile.write(body)
        site = _Site({"/hdr": hdr})
        self.addCleanup(site.stop)
        d = tmpdir(self)
        (d / "pw").write_text(self.PASSWORD, encoding="utf-8")
        code, out, err = run("--url", f"{site.base}/hdr", "--no-render",
                             "--http-user", "u", "--http-password-file",
                             d / "pw", "--json", d / "r.json", "--bundle",
                             d / "b.json", "--fail-on", "never")
        self.assertEqual(code, 0, err)
        text = ((d / "r.json").read_text() + (d / "b.json").read_text()
                + out + err)
        self.assertNotIn("dTpyS0I2", text)
        self.assertNotIn("x2BWXg", text)

    def test_a_forms_encoding_beside_a_plus(self):
        """R6E-2: a password with white space beside its own "+", as a form
        encodes it (each space a "+", its own "+" `%2B`), is found, and a
        URL holding it is refused."""
        from urllib.parse import quote, quote_plus
        password = "Correct Horse + Battery 77"
        for text in (quote_plus(password), quote(password), password,
                     password.replace(" ", "&nbsp;"),
                     "Correct+Horse+%2b+Battery+77",
                     "Correct%20Horse%20+%20Battery%2077"):
            with self.subTest(text=text):
                self.assertTrue(cli._password_in(password, [text]))
                self.assertEqual(cli._without_password(text, password),
                                 "REDACTED")
        with self.assertRaises(ValueError):
            cli._check_password_urls(
                ("u", password),
                ["https://example.test/?q=" + quote_plus(password)])

    def test_linear(self):
        """R6E-7: a password whose own characters spell white space beside
        its white space, on a page of that spelling, takes no time; nor a
        "+" beside white space on a page of "+"."""
        cases = [("Qz " + " &nbsp;" * k + " Wy", "Qz" + "&nbsp;" * 400)
                 for k in (2, 4, 8)]
        cases += [("Qz " + " %20" * 4 + " Wy", "Qz" + "%20" * 400),
                  ("Qz " + " &#32;" * 4 + " Wy", "Qz" + "&#32;" * 400),
                  ("a + b + c + d", "a" + "+" * 3000),
                  ("a + b + c + d", "a " + "+ " * 3000)]
        for password, text in cases:
            with self.subTest(password=password):
                start = time.monotonic()
                cli._password_in(password, [text])
                self.assertLess(time.monotonic() - start, 2.0)

    def test_many_secrets(self):
        """R6E-9: with a thousand secrets, a text is searched only for
        those it may hold, so neither the first search nor the next takes
        long; each one it holds is found, in any spelling, however an
        escape before it reads its first characters."""
        import random
        rnd = random.Random(7)
        alphabet = ("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
                    "0123456789-_")
        secrets = ["".join(rnd.choice(alphabet) for _ in range(24))
                   for _ in range(1000)]
        spelled = "".join(f"%{ord(c):02X}" for c in secrets[17])
        escaped = (secrets[5][:6] + "\\u%04x" % ord(secrets[5][6])
                   + secrets[5][7:])
        texts = ["x " * 24000 + secrets[3],
                 "<p>" + spelled + "</p>" + "y " * 24000,
                 "<script>var t = '" + escaped + "';</script>"]
        token = R.set_run_secrets(secrets)
        try:
            start = time.monotonic()
            got = [R.scrub_secrets(t) for t in texts]
            self.assertLess(time.monotonic() - start, 5.0)
            self.assertNotIn(secrets[3], got[0])
            self.assertNotIn(spelled, got[1])
            self.assertIn("REDACTED", got[2])
            start = time.monotonic()
            for _ in range(20):
                R.scrub_secrets(texts[0])
            self.assertLess(time.monotonic() - start, 5.0)
        finally:
            R.reset_run_secrets(token)

    def test_a_capture_before_a_secret(self):
        """R6E-9: a secret whose first characters an escape before it in
        the text could read as its own ("%" before "41…", "&#" before
        digits, "&" before a reference's name) is found, as the search over
        all of them finds it."""
        for secret, text in (
                ("41bcdefgh/ijklmn", "%41bcdefgh\\/ijklmn"),
                ("1234abcd/efghij", "&#1234abcd\\/efghij"),
                ("copyabcd/efghij", "&copyabcd\\/efghij"),
                ("u0041bcd/efghij", "\\u0041bcd\\/efghij"),
                ("2541bcdefgh/ijk", "%2541bcdefgh\\/ijk")):
            with self.subTest(secret=secret):
                token = R.set_run_secrets(tokens=[secret])
                try:
                    self.assertTrue(R.holds_secret(text))
                    self.assertNotIn("efgh", R.scrub_secrets(text))
                finally:
                    R.reset_run_secrets(token)

    def test_console_lines_redacted(self):
        """R6E-8: the console lines for a page its server does not send
        with 200, and for one that ends on another host, print its URL
        redacted, as every other line does."""
        from tests.test_fetch_hardening import _Site, redirect, send
        secret = "tok-8f2kQ7Lz91xWvB3n"
        routes = {"/ok": send(PAGE.format("<p>x</p>").encode())}
        site = _Site(routes)
        self.addCleanup(site.stop)
        routes["/away"] = redirect(
            f"http://localhost:{site.port}/ok?t={secret}")
        d = tmpdir(self)
        code, out, err = run("--url", f"{site.base}/gone?t={secret}",
                             "--no-render", "--json", d / "r.json",
                             "--fail-on", "never")
        self.assertIn("HTTP 404", err)
        self.assertNotIn(secret, out + err)
        code, out, err = run("--url", f"{site.base}/ok?t={secret}",
                             "--url", f"{site.base}/away?t={secret}",
                             "--no-render", "--json", d / "r.json",
                             "--fail-on", "never")
        self.assertIn("in a run of its own", err)
        self.assertNotIn(secret, out + err)


#: Parts of a drawing or of MathML that are not rendered, with visibility
#: and conditions, and what they hold, as Chromium 141 names a button
#: labelled by them (id, markup, named). "C": the button holds the
#: drawing; "L": it is labelled by `#{id}r`; "A": a drawing's link.
_ROUND3_NAMES = (
    ("a1", "C", '<svg><linearGradient><text style="visibility:hidden">Save'
     "</text></linearGradient></svg>", False),
    ("a2", "L", '<svg><linearGradient id="a2r"><text style="visibility:'
     'hidden">Save</text></linearGradient></svg>', False),
    ("a3", "L", '<svg><linearGradient><text id="a3r" style="visibility:'
     'hidden">Save</text></linearGradient></svg>', True),
    ("a4", "C", '<math><mspace><mrow><mtext style="visibility:hidden">Save'
     "</mtext></mrow></mspace></math>", False),
    ("a7", "L", '<svg><defs id="a7r" style="visibility:hidden"><text '
     'style="visibility:visible">Save</text></defs></svg>', True),
    ("a9", "L", '<svg><defs id="a9r"><text style="visibility:hidden">Save'
     "</text></defs></svg>", False),
    ("a10", "L", '<svg><defs id="a10r"><g style="visibility:hidden"><text '
     'style="visibility:visible">Save</text></g></defs></svg>', True),
    ("a13", "L", '<svg><g id="a13r" style="display:none;visibility:hidden">'
     '<text style="visibility:visible">Save</text></g></svg>', True),
    ("a14", "L", '<svg><symbol id="a14r"><text systemLanguage="xx">Save'
     "</text></symbol></svg>", False),
    ("a15", "L", '<svg><g id="a15r" style="display:none"><text '
     'systemLanguage="xx">Save</text></g></svg>', False),
    ("a19", "L", '<svg><linearGradient id="a19r" style="visibility:hidden">'
     '<text style="visibility:visible">Save</text></linearGradient></svg>',
     True),
    ("c1", "L", '<svg><linearGradient id="c1r"><g><text>Save</text></g>'
     "</linearGradient></svg>", False),
    ("c4", "L", '<svg><linearGradient id="c4r"><g><a href="/x"><text>Save'
     "</text></a></g></linearGradient></svg>", False),
    ("c7", "L", '<svg><rect id="c7r" width="5" height="5"><g><text>Save'
     "</text></g></rect></svg>", False),
    ("c9", "L", '<svg><linearGradient id="c9r"><svg><text>Save</text></svg>'
     "</linearGradient></svg>", True),
    ("c13", "L", '<svg><defs id="c13r"><linearGradient><g><text>Save</text>'
     "</g></linearGradient></defs></svg>", False),
    ("c14", "L", '<svg><defs id="c14r"><linearGradient><text>Save</text>'
     "</linearGradient></defs></svg>", True),
    ("d1", "L", '<svg><linearGradient><g id="d1r"><text>Save</text></g>'
     "</linearGradient></svg>", True),
    ("d12", "L", '<svg><defs id="d12r"><g><linearGradient><text>Save</text>'
     "</linearGradient></g></defs></svg>", False),
    ("f1", "A", '<svg><a id="f1" xlink:href="/x" xlink:title="Home"><path '
     'd="M0 0h9v9z"/></a></svg>', True),
    ("f3", "A", '<svg><a id="f3" href="/x" xlink:title=""><path d="M0 0h9v9z"'
     "/></a></svg>", False),
)

#: Links of a drawing in aria-hidden content, and whether Chromium 141
#: lets each take focus (measured): (id, markup, focusable).
_ROUND3_FOCUS = (
    ("b1", '<svg><switch><g requiredFeatures="http://www.w3.org/TR/SVG11/'
     'feature#Extensibility"/><a id="b1" xlink:href="https://www.drawio.com'
     '/doc/faq/svg-export-text-problems" target="_blank"><text>Text is not '
     "SVG - cannot display</text></a></switch></svg>", False),
    ("b2", '<svg><defs><a id="b2" xlink:href="/x"><path d="M0 0h10v10z"/>'
     "</a></defs></svg>", False),
    ("b3", '<svg><defs style="visibility:hidden"><a id="b3" href="/x" '
     'style="visibility:visible"><text>x</text></a></defs></svg>', False),
    ("b4", '<svg><g style="display:none;visibility:hidden"><a id="b4" '
     'href="/x" style="visibility:visible"><text>x</text></a></g></svg>',
     False),
    ("b5", '<svg><symbol><a id="b5" xlink:href="/x"><text>x</text></a>'
     "</symbol></svg>", False),
    ("b7", '<svg><a id="b7" href="/x"><text>x</text></a></svg>', True),
    ("b8", '<svg><rect width="5" height="5"><a id="b8" href="/x"><text>x'
     "</text></a></rect></svg>", False),
    ("b10", '<svg><switch><title>t</title><a id="b10" href="/x"><text>x'
     "</text></a></switch></svg>", False),
    ("b11", '<svg><switch><text systemLanguage="xx">a</text><a id="b11" '
     'href="/x"><text>x</text></a></switch></svg>', True),
    ("b17", '<svg><switch><g systemLanguage=""/><a id="b17" href="/x"><text>'
     "x</text></a></switch></svg>", True),
    ("b18", '<svg><switch><g requiredExtensions="http://www.w3.org/1999/'
     'xhtml"/><a id="b18" href="/x"><text>x</text></a></switch></svg>',
     False),
    ("e5", '<svg><switch><g requiredExtensions="foo"/><a id="e5" href="/x">'
     "<text>x</text></a></switch></svg>", True),
    ("b22", '<svg><text><a id="b22" href="/x">x</a></text></svg>', True),
    ("b25", '<svg><desc><a id="b25" href="/x">x</a></desc></svg>', False),
    ("b28", '<svg><switch><!-- c --><a id="b28" href="/x"><text>x</text>'
     "</a></switch></svg>", True),
)


def _round3_page() -> str:
    out = []
    for i, kind, inner, _named in _ROUND3_NAMES:
        if kind == "C":
            out.append(f'<button id="{i}">{inner}</button>')
        elif kind == "L":
            out.append(f'<button id="{i}" aria-labelledby="{i}r"></button>'
                       + inner)
        else:
            out.append(inner)
    out += [f'<div id="h-{i}" aria-hidden="true">{inner}</div>'
            for i, inner, _focusable in _ROUND3_FOCUS]
    return PAGE.format("".join(out))


def _check_round3(test, findings) -> None:
    """Each of _ROUND3_NAMES named, and each of _ROUND3_FOCUS focusable,
    as Chromium 141 has it, by `findings` ([(rule, verdict, snippet)])."""
    failed = " ".join(snippet for rule, verdict, snippet in findings
                      if verdict == "fail"
                      and rule in ("bb-button-name", "bb-link-name"))
    for i, _kind, _inner, named in _ROUND3_NAMES:
        with test.subTest(case=i):
            test.assertEqual(f'id="{i}"' not in failed, named)
    for i, _inner, focusable in _ROUND3_FOCUS:
        with test.subTest(case=i):
            got = [verdict for rule, verdict, snippet in findings
                   if rule == "bb-aria-hidden-focus"
                   and f'id="h-{i}"' in snippet]
            test.assertEqual(got, ["fail"] if focusable else [])


@unittest.skipUnless(HAVE_BROWSER, _WHY)
class TestDrawingMarksR6Round3(unittest.TestCase):
    """R6E-3 to R6E-6, R6F-1, rendered: inside what is not rendered,
    visibility as computed (an invisible element there names nothing, one
    made visible again inside an invisible box takes no focus); a <g> with
    no box holds nothing a name reads; a part whose conditions fail inside
    a box is left out; what a drawing never renders takes no focus (the
    <a> a <switch> passes over, as draw.io's footer); a drawing's link is
    named by its xlink:title (each case measured in Chromium 141)."""

    def test_names_and_focus(self):
        site = _echo_site(self, lambda t: _round3_page())
        d = tmpdir(self)
        code, _out, err = run("--url", f"{site.base}/p", "--json",
                              d / "r.json", "--fail-on", "never")
        self.assertEqual(code, 0, err)
        report = json.loads((d / "r.json").read_text())
        _check_round3(self, [(f["rule_id"], f["verdict"], f["snippet"])
                             for p in report["pages"]
                             for f in p["findings"]])


class TestDrawingsR6Round3(unittest.TestCase):
    """R6E-3, R6F-1, R6F-5, R6F-8, from markup: what a drawing never
    renders takes no focus (what a <defs>, a <symbol>, a gradient, a shape
    or a <desc> holds; a <switch>'s element after the one it renders,
    which the run can tell where no language decides), and what a
    <symbol> holds is in no accessibility tree (what a <defs> holds is:
    round 4, R6G-3); a drawing's link is named by its xlink:title; an
    XHTML page's xlink namespace under another prefix."""

    def test_focus(self):
        page_ = run_page(_round3_page(), "t.html", RB)
        findings = [f for r in page_.results for f in r.findings
                    if r.rule_id == "bb-aria-hidden-focus"]
        for i, _inner, focusable in _ROUND3_FOCUS:
            with self.subTest(case=i):
                got = [f.verdict for f in findings
                       if f'id="h-{i}"' in f.snippet]
                self.assertEqual(got, [FAIL] if focusable else [])

    def test_link_names(self):
        self.assertEqual(TestRulesRound2.found(page(
            '<svg width="40" height="20"><symbol><a xlink:href="/x"><path '
            'd="M0 0h9v9z"/></a></symbol></svg>'), "bb-link-name")[1], [])
        self.assertEqual(TestRulesRound2.found(page(
            '<svg width="40" height="20"><a xlink:href="/x" xlink:title='
            '"Home"><path d="M0 0h9v9z"/></a></svg>'), "bb-link-name")[1],
            [])
        got = TestRulesRound3.names(None, page(
            '<svg width="40" height="20"><a id="a" href="/x" xlink:title='
            '"Home"><text y="15">Text</text></a><a id="b" href="/x" '
            'xlink:title="Home"><title>T</title><text y="15">Text</text></a>'
            "</svg>"), "a", "b")
        self.assertEqual(got, {"a": "Home", "b": "T"})

    def test_xhtml_prefix(self):
        xhtml = ('<?xml version="1.0" encoding="UTF-8"?><html xmlns="http://'
                 'www.w3.org/1999/xhtml" xmlns:xl="http://www.w3.org/1999/'
                 'xlink" lang="en" xml:lang="en"><head><title>T</title></head>'
                 '<body><main><h1>x</h1><div aria-hidden="true"><svg xmlns="'
                 'http://www.w3.org/2000/svg" width="40" height="20"><a '
                 'xl:href="/x"><text y="15">x</text></a></svg></div></main>'
                 "</body></html>")
        self.assertEqual(TestRulesRound2.found(xhtml, "bb-aria-hidden-focus",
                                               path="t.xhtml"),
                         (True, [(FAIL, "serious")]))


# ---------------------------------------------------------------------------
# Round 3, R6F: the rules and claims side
# ---------------------------------------------------------------------------

class TestOwnStyleR6Round3(unittest.TestCase):
    """R6F-2 to R6F-4, R6F-7, as Chromium 141 reads them (each case
    measured there): a rule list holds no declarations, so a ";" or a "}"
    that closes nothing makes the next style rule invalid, and a
    stylesheet's "<!--" and "-->" are no part of a rule; an @layer takes
    one name; a selector list with an empty member, or a pseudo-class or
    pseudo-element Chromium does not have, drops its rule (a forgiving
    list drops the member); an @supports holding a bad token drops its
    rule; a comment is no white space an escape takes."""

    #: (stylesheet, whether .lbl is hidden in Chromium 141)
    LISTS = (
        (".x{color:red}; .lbl{display:none}", False),
        (".lbl{display:none} .x{color:red}; .lbl{display:inline}", True),
        (".x{color:red}} .lbl{display:none}", False),
        ("; .lbl{display:none}", False),
        ("@media screen{.x{color:red}; .lbl{display:none}}", False),
        ("@media screen{.x{color:red}}; .lbl{display:none}", False),
        ("@layer a{.x{color:red}; .lbl{display:none}}", False),
        ("@supports (display:block){.x{color:red}; .lbl{display:none}}",
         False),
        ("@scope (main){.x{color:red}; .lbl{display:none}}", True),
        ("@scope (main) { @media screen { .x{}; .lbl{display:none} } }",
         False),
        ("main { @media screen { .x{color:red}; .lbl{display:none} } }",
         True),
        ("main { @scope (a) { @media screen { .x{}; .lbl{display:none} } } }",
         False),
        ("<!-- .lbl{display:none} -->", True),
        (".a{} --> .lbl{display:none}", True),
        (".lbl <!-- {display:none}", False),
        ("@media screen{ <!-- .lbl{display:none} }", False),
        ("@media screen; .lbl{display:none}", True),
        ("@import url(x); .lbl{display:none}", True),
        ("@media screen } .lbl{display:none}", False),
        ("@media screen, } { .lbl{display:none} }", True),
        ("@foo bar } { } .lbl{display:none}", True),
        ("@media screen { } } @media screen { .lbl{display:none} }", False),
        ("@layer a b { .lbl{display:none} }", False),
        ("@layer a, b { .lbl{display:none} }", False),
        ("@layer a.b { .lbl{display:none} }", True),
        ("@layer a/**/.b { .lbl{display:none} }", True),
        ("@layer a/**/b { .lbl{display:none} }", False),
        ("@layer { .lbl{display:none} }", True),
    )
    SELECTORS = (
        (".lbl,{display:none}", False),
        (".lbl,,.x{display:none}", False),
        (".lbl, .x::-moz-selection{display:none}", False),
        (".lbl, .x:-moz-any-link{display:none}", False),
        (".lbl, .x:foo{display:none}", False),
        (".lbl, [x=a b]{display:none}", False),
        (".lbl,\x0b.x{display:none}", False),
        (".lbl, .x:local-link{display:none}", False),
        (".lbl, .x::after:hover{display:none}", False),
        (".lbl, .x::before .y{display:none}", False),
        (".lbl, .x: hover{display:none}", False),
        (".lbl, input[type=checkbox s]{display:none}", False),
        (".lbl, svg|a{display:none}", False),
        (".lbl, a || b{display:none}", False),
        (".lbl, .x::before{display:none}", True),
        (".lbl, .x:hover{display:none}", True),
        (".lbl, .x:modal{display:none}", True),
        (".lbl, .x::-webkit-scrollbar-thumb:hover{display:none}", True),
        (".lbl, .x::file-selector-button:hover{display:none}", True),
        (".lbl, .md\\:flex, .w-1\\/2{display:none}", True),
        (".lbl, .a\\,b{display:none}", True),
        (".lbl, *|a, [*|x]{display:none}", True),
        (".lbl, input[type=checkbox i]{display:none}", True),
        ("@namespace svg url(http://www.w3.org/2000/svg); .lbl, svg|a"
         "{display:none}", True),
        (":is(.lbl, .x:foo){display:none}", True),
        (":where(.lbl, .x::before){display:none}", True),
        (".lbl, :not(.lbl, .x:foo){display:none}", False),
        (".lbl, .x:has(){display:none}", False),
    )
    SUPPORTS = (
        ("@supports not (--x: url(a b)) { .lbl{display:none} }", False),
        ("@supports not (--x: ]) { .lbl{display:none} }", False),
        ("@supports not (--x: 'a\n) { .lbl{display:none} }", False),
        ("@supports (display:block) } { .lbl{display:none} }", False),
        ("@supports not (--x: a;b) { .lbl{display:none} }", True),
        ("@supports not (--x: a!b) { .lbl{display:none} }", True),
        ("@supports (display:\\6e/**/one) { .lbl{display:none} }", False),
        ("@supports not (display:\\6e/**/one) { .lbl{display:none} }", True),
        ("@supports not/**/(display:foo) { .lbl{display:none} }", True),
        ("@supports (display/**/:/**/block) { .lbl{display:none} }", True),
        ("@supports (display:inline/**/block) { .lbl{display:none} }", False),
        ("@supports (display: inline/**/ flex) { .lbl{display:none} }", True),
    )
    DECLARATIONS = (
        (".lbl{display:\\6e/**/one}", False),
        (".lbl{display:none;display:\\69/**/nline}", True),
        (".lbl{\\64/**/isplay:none}", False),
        (".lbl{visibility:\\68/**/idden}", False),
        (".lbl{display:none !\\69/**/mportant;display:inline}", False),
        (".lbl{display:none/**/!important} .lbl{display:inline}", True),
        (".lbl{display:none!/**/important} .lbl{display:inline}", True),
        (".lbl{display/**/:/**/none}", True),
        (".lbl{display:no/**/ne}", False),
        (".lbl{display:\\6e one}", True),
    )

    def test_rule_lists(self):
        for css, hidden in self.LISTS:
            with self.subTest(css=css):
                self.assertEqual(link_fails(css), hidden)

    def test_selector_lists(self):
        for css, hidden in self.SELECTORS:
            with self.subTest(css=css):
                self.assertEqual(link_fails(css), hidden)

    def test_supports(self):
        for css, hidden in self.SUPPORTS:
            with self.subTest(css=css):
                self.assertEqual(link_fails(css), hidden)

    def test_declarations(self):
        for css, hidden in self.DECLARATIONS:
            with self.subTest(css=css):
                self.assertEqual(link_fails(css), hidden)
        for style, shown in (("display:\\6e/**/one", True),
                             ("display:none;display:\\69/**/nline", False),
                             ("visibility:\\68/**/idden", True)):
            with self.subTest(style=style):
                self.assertEqual(TestRulesRound2.found(page(
                    f'<a href="/x"><span style="{style}">Cart</span></a>'),
                    "bb-link-name")[1], [] if shown else [(FAIL, "blocker")])

    def test_hostile(self):
        """None of these takes long: a stylesheet of ";", of "}", of
        "<!--", a selector list of empty members, deep :is()."""
        from bellbriar_harness.style import style_rules
        for css in (";" * 200000 + ".a{display:none}",
                    "}" * 200000 + ".a{display:none}",
                    "<!--" * 50000 + ".a{display:none}",
                    "@media x" + "}" * 200000 + "{.a{}}",
                    "," * 100000 + "{display:none}",
                    ":is(" * 3000 + ".a" + ")" * 3000 + "{display:none}",
                    ".a" + ":not(" * 20000 + ".b" + ")" * 20000
                    + "{display:none}"):
            with self.subTest(css=css[:20]):
                start = time.monotonic()
                style_rules(css)
                run_page(page("<p>x</p>", head=f"<style>{css}</style>"),
                         "t.html", RB)
                self.assertLess(time.monotonic() - start, 10)


class TestVisibilityLaterR6Round3(unittest.TestCase):
    """R6F-6: a focusable element whose own visibility, or the nearest one
    set above it, is only known later (var()) is reviewed in a file run,
    whatever is set further up."""

    def test_reviewed(self):
        for body, head in (
                ('<div aria-hidden="true" style="--v:hidden"><button style="'
                 'visibility:var(--v)">Go</button></div>', ""),
                ('<div aria-hidden="true" style="--v:hidden"><button '
                 'class="b">Go</button></div>',
                 "<style>.b{visibility:var(--v)}</style>"),
                ('<div aria-hidden="true" style="visibility:hidden;'
                 '--v:hidden"><span style="visibility:visible"><button '
                 'style="visibility:var(--v)">Go</button></span></div>', "")):
            with self.subTest(body=body):
                self.assertEqual(TestRulesRound2.found(page(
                    body, head=head), "bb-aria-hidden-focus"),
                    (True, [(NEEDS_REVIEW, "moderate")]))


# ---------------------------------------------------------------------------
# Round 4, R6G: drawings and MathML (the secrets findings are open: L111)
# ---------------------------------------------------------------------------

#: A link a drawing holds, unnamed: in the accessibility tree, a FAIL.
_R4_LINK = '<a href="/x"><rect width="5" height="5"/></a>'
#: Where a drawing holds a link, as Chromium 141 has it (measured: R6G-3,
#: R6H-1, R6G-7, R6G-8): (markup around `{A}`, in the accessibility tree,
#: takes focus).
_R4_TREE = (
    ("<defs>{A}</defs>", True, False),
    ("<defs><g>{A}</g></defs>", True, False),
    ('<clipPath id="c">{A}</clipPath>', True, False),
    ('<mask id="m">{A}</mask>', True, False),
    ('<pattern id="p">{A}</pattern>', True, False),
    ('<marker id="k">{A}</marker>', True, False),
    ('<g style="display:none">{A}</g>', True, False),
    ('<g style="display:none"><g>{A}</g></g>', True, False),
    ('<marker id="k2" style="display:none"><g>{A}</g></marker>', True,
     False),
    ('<defs><g style="display:none">{A}</g></defs>', True, False),
    ('<g style="display:none"><defs>{A}</defs></g>', True, False),
    ("<symbol>{A}</symbol>", False, False),
    ('<linearGradient id="g">{A}</linearGradient>', False, False),
    ('<filter id="f">{A}</filter>', False, False),
    ('<rect width="5" height="5">{A}</rect>', False, False),
    ("<desc>{A}</desc>", False, False),
    ('<use href="#z">{A}</use>', False, False),
    ('<defs style="display:none">{A}</defs>', False, False),
    ('<clipPath id="c2" style="display:none">{A}</clipPath>', False, False),
    ('<svg style="display:none">{A}</svg>', False, False),
    ('<text style="display:none">{A}</text>', False, False),
    ("<a>{A}</a>", False, False),
    ("<tspan>{A}</tspan>", False, False),
    ("<text><a>{A}</a></text>", False, False),
    ("<switch><g/>{A}</switch>", False, False),
    ('<switch><title systemLanguage="xx"/>{A}</switch>', False, False),
    ('<switch><clipPath id="c3" systemLanguage="xx"/>{A}</switch>', False,
     False),
    ('<switch><g systemLanguage="xx"/>{A}</switch>', True, True),
    ('<switch><animate systemLanguage="xx"/>{A}</switch>', True, True),
    ("<defs><switch><g/>{A}</switch></defs>", False, False),
    ('<switch><a><rect width="5" height="5"/><g>{A}</g></a></switch>', False,
     False),
    ('<switch><g><rect width="5" height="5"/>{A}</g></switch>', True, True),
    ("<g>{A}</g>", True, True),
    ("<a><g>{A}</g></a>", True, True),
)


def _r4_drawing(markup: str, link: str = _R4_LINK) -> str:
    return f'<svg width="40" height="20">{markup.format(A=link)}</svg>'


class TestDrawingTreeR6Round4(unittest.TestCase):
    """R6G-3, R6H-1, R6G-7, R6G-8, from markup: what a drawing boxes but
    never paints (a <defs>, a clip path, a mask, a pattern, a marker, a
    <g> or a <marker> with display:none) holds links in the accessibility
    tree, which take no focus and are checked for names; a <symbol>'s,
    what a <switch> passes over, an <a> in an <a>, a text part outside a
    <text> are in none; a <switch> reads the conditions of the elements
    Chromium reads them on; requiredExtensions splits at ASCII white space
    (each case measured in Chromium 141)."""

    def test_link_names(self):
        for markup, in_tree, _focusable in _R4_TREE:
            with self.subTest(markup=markup):
                self.assertEqual(TestRulesRound2.found(page(_r4_drawing(
                    markup)), "bb-link-name")[1],
                    [(FAIL, "blocker")] if in_tree else [])

    def test_focus(self):
        for markup, _in_tree, focusable in _R4_TREE:
            with self.subTest(markup=markup):
                got = TestRulesRound2.found(page(
                    '<div aria-hidden="true">' + _r4_drawing(markup)
                    + "</div>"), "bb-aria-hidden-focus")[1]
                self.assertEqual(got, [(FAIL, "serious")] if focusable
                                 else [])

    def test_html_in_a_box(self):
        """HTML a <defs> holds is in no accessibility tree."""
        self.assertEqual(TestRulesRound2.found(page(
            '<svg width="40" height="20"><defs><foreignObject width="9" '
            'height="9"><a href="/x"></a></foreignObject></defs></svg>'),
            "bb-link-name")[1], [])

    def test_more_focus(self):
        for body, focusable in (
                ('<svg><text><a><a href="/x">x</a></a></text></svg>', False),
                ('<svg><text><a><g><a href="/x">x</a></g></a></text></svg>',
                 False),
                ('<svg><a><tspan><a href="/x">Go</a></tspan></a></svg>',
                 False),
                ('<svg><switch><a href="#" requiredExtensions="http://www.w3.'
                 'org/1999/xhtml&#xA0;http://www.w3.org/1998/Math/MathML">'
                 '<text>x</text></a><a href="#"><text>y</text></a></switch>'
                 "</svg>", True)):
            with self.subTest(body=body):
                got = TestRulesRound2.found(page(
                    f'<div aria-hidden="true">{body}</div>'),
                    "bb-aria-hidden-focus")[1]
                self.assertEqual(got, [(FAIL, "serious")] if focusable
                                 else [])


#: Names Chromium 141 gives (measured: R6G-4, R6H-7): (body, rule, named).
_R4_NAMES = (
    ('<svg width="40" height="20"><a href="/x" xlink:title="XL"><title>  '
     '</title><rect width="5" height="5"/></a></svg>', "bb-link-name",
     False),
    ('<svg width="40" height="20"><a href="/x" xlink:title="XL"><title>'
     '&nbsp;</title><rect width="5" height="5"/></a></svg>', "bb-link-name",
     False),
    ('<svg width="40" height="20"><a href="/x"><title> </title><text>Body'
     "</text></a></svg>", "bb-link-name", False),
    ('<svg width="40" height="20"><a href="/x" xlink:title=" "><text>Body'
     "</text></a></svg>", "bb-link-name", False),
    ('<svg width="40" height="20"><a href="/x" xlink:title="XL"><title>'
     '</title><rect width="5" height="5"/></a></svg>', "bb-link-name", True),
    ('<span id="l1"><math><mtext>Save</mtext></math></span><a href="/a" '
     'aria-labelledby="l1"></a>', "bb-link-name", True),
    ('<span id="l2"><math><mphantom><mtext>Save</mtext></mphantom></math>'
     '</span><a href="/a" aria-labelledby="l2"></a>', "bb-link-name",
     False),
)


class TestNamesR6Round4(unittest.TestCase):
    """R6G-4, R6H-7: aria-labelledby reads MathML, a <mphantom> invisible
    (a name from content from MathML waits on L92); a drawing's <title> or
    xlink:title of white space names it nothing, and nothing after it is
    read (each measured in Chromium 141)."""

    def test_names(self):
        for body, rule, named in _R4_NAMES:
            with self.subTest(body=body):
                got = TestRulesRound2.found(page(body), rule)[1]
                self.assertEqual([v for v, _impact in got],
                                 [] if named else [FAIL])


#: A rendered run's names and tree (measured: R6G-3, R6G-4, R6G-8, R6H-7):
#: (id, markup, FAIL).
_R4_RENDERED = (
    ("d1", '<svg width="40" height="20"><defs><a id="d1" href="/x"><rect '
     'width="5" height="5"/></a></defs></svg>', True),
    ("d2", '<svg width="40" height="20"><g class="dn"><a id="d2" href="/x">'
     '<rect width="5" height="5"/></a></g></svg>', True),
    ("d3", '<svg width="80" height="20"><marker id="k" style="display:none">'
     '<a id="d3" href="/x"><text>Save</text></a></marker></svg>', False),
    ("d4", '<svg width="40" height="20"><symbol id="s"><a id="d4" href="/x">'
     '<rect width="5" height="5"/></a></symbol></svg>', False),
    ("d5", '<svg width="80" height="20"><a id="d5" href="/x"><rect width="3"'
     ' height="3"/><switch><g/><a><text>Save</text></a></switch></a></svg>',
     True),
    ("d6", '<svg width="80" height="20"><a id="d6" href="/x"><a href="/b">'
     "<text>Save</text></a></a></svg>", False),
    ("d7", '<svg width="80" height="20"><a id="d7" href="/x"><a><text>Save'
     "</text></a></a></svg>", True),
    ("d9", '<span id="d9r"><math><mphantom><mtext>Save</mtext></mphantom>'
     '</math></span><a id="d9" href="/a" aria-labelledby="d9r"></a>', True),
    ("d10", '<svg width="40" height="20"><a id="d10" href="/x" xlink:title='
     '"XL"><title> </title><rect width="5" height="5"/></a></svg>', True),
    ("d11", '<svg width="80" height="20"><a id="d11" href="/x"><switch><g/>'
     "<text>Save</text></switch></a></svg>", False),
)


@unittest.skipUnless(HAVE_BROWSER, _WHY)
class TestDrawingTreeMarksR6Round4(unittest.TestCase):
    """R6G-3, R6G-4, R6G-8, R6H-7, rendered: a link in a <defs> or a <g>
    with display:none is checked; a <marker>'s content names its link; a
    <symbol>'s link is in no tree; an <a> that is no link, with no box,
    names nothing; a <mphantom> is invisible; a <title> of white space
    names nothing (measured)."""

    def test_names(self):
        site = _echo_site(self, lambda t: PAGE.format(
            "<style>.dn{display:none}</style>"
            + "".join(m for _i, m, _f in _R4_RENDERED)))
        d = tmpdir(self)
        code, _out, err = run("--url", f"{site.base}/p", "--json",
                              d / "r.json", "--fail-on", "never")
        self.assertEqual(code, 0, err)
        report = json.loads((d / "r.json").read_text())
        failed = " ".join(f["snippet"] for p in report["pages"]
                          for f in p["findings"] if f["verdict"] == "fail"
                          and f["rule_id"] == "bb-link-name")
        for i, _markup, fails in _R4_RENDERED:
            with self.subTest(case=i):
                self.assertEqual(f'id="{i}"' in failed, fails)


# ---------------------------------------------------------------------------
# Round 4, R6H: the rules and claims side
# ---------------------------------------------------------------------------

class TestOwnStyleR6Round4(unittest.TestCase):
    """R6H-2, R6H-4 to R6H-6, R6H-8 to R6H-11: a page's own rules as
    Chromium 141 reads them, each case measured there: (css, the link's
    text hidden)."""

    #: `.lbl, X{display:none}`: the rule stands where Chromium takes X.
    SELECTORS = (
        (":lang(en)", True), (":lang(en, fr)", False), (':lang("en")', False),
        (":lang(\\*-CH)", True), (":lang(1)", False), (":dir(foo)", True),
        (':dir("rtl")', False), (":dir(rtl ltr)", False),
        (":nth-child(2n+1)", True), (":nth-child(ODD)", True),
        (":nth-child(foo)", False), (":nth-child(2n+)", False),
        (":nth-child(2n of)", False), (":nth-child(2n of .a .b)", True),
        (":nth-child(2n of .a, :foo)", False), (":nth-child(of .a)", False),
        (":nth-of-type(2n of .a)", False), (":nth-child(- n+1)", False),
        (":nth-child(2n- 1)", True), (":nth-child(2n -1)", True),
        (":nth-child(+ 5)", False), (":nth-child(2n+-1)", False),
        (":nth-child(\\32 n)", False), (":nth-child(2n of ::before)", True),
        (":has(:has(.y))", False), (":has(:is(:has(.y)))", True),
        (":has(:not(:has(.y)))", False), (":has(.a >)", False),
        (":has(.a, > .b)", True), (":has(.a,)", False),
        (":host(.a .b)", False), (":host(.a.b)", True),
        (":host(:is(.a .b))", True), (":host(.a, .b)", False),
        (":host-context(.a .b)", False), (":not(> .a)", False),
        (":not(.a,)", False), (":not(.a .b)", True), (':state("x")', False),
        (":state(--x)", True), ("[x!=y]", False), ("[x=a \\69]", True),
        ('[x="a" \\69]', True), ("[x=a/**/i]", True), ("[x i]", False),
        ('[x="a" s]', False), ("::slotted(.a .b)", False),
        ("::slotted(.a, .b)", False), ("::cue(b c)", False),
        ("::cue(b, c)", True), ("::cue(b):hover", False),
        ("::cue:hover", True), ("::scroll-button(x)", False),
        ("::scroll-button(inline-end)", True), ("::part(x)::part(y)", False),
        ("::part(x)::slotted(y)", False), ("::part(x)::before", True),
        ("::part(x y)", True), ("::part(x, y)", False),
        ("::highlight(x y)", False), ("::view-transition-group(x y)", False),
        ("::view-transition-group(*.c)", True),
        (":active-view-transition-type(x, y)", True),
        (":-webkit-any(.a .b)", False), (":-webkit-any(.a, .b)", True),
        ("::column::scroll-marker:hover", True),
        ("::slotted(b)::placeholder", True), ("::interest-hint", True),
        ("::view-transition-group-children(x)", True),
        (":-internal-relative-anchor", True), (":-internal-foo", False))
    SVG = "url(http://www.w3.org/2000/svg)"
    #: Stylesheets.
    SHEETS = (
        # @namespace where Chromium reads it, prefix by prefix (R6H-8)
        ('.y{content:"@namespace"} .lbl, svg|a{display:none}', False),
        (f".y{{}} @namespace svg {SVG}; .lbl, svg|a{{display:none}}", False),
        ("@namespace foo url(urn:x); .lbl, svg|a{display:none}", False),
        (f"@namespace svg {SVG}; .lbl, svg|a{{display:none}}", True),
        (f"@import url(x.css); @namespace svg {SVG}; .lbl, svg|a"
         "{display:none}", True),
        (f"@layer a; @namespace svg {SVG}; .lbl, svg|a{{display:none}}",
         True),
        (f"@import url(x.css); @layer x; @namespace svg {SVG}; .lbl, svg|a"
         "{display:none}", False),
        (f"@media print{{}} @namespace svg {SVG}; .lbl, svg|a"
         "{display:none}", False),
        (f"@foo; @namespace svg {SVG}; .lbl, svg|a{{display:none}}", True),
        (f".a..b{{}} @namespace svg {SVG}; .lbl, svg|a{{display:none}}",
         True),
        (f"@namespace SVG {SVG}; .lbl, svg|a{{display:none}}", False),
        (f"@namespace s\\76g {SVG}; .lbl, svg|a{{display:none}}", True),
        (".lbl, [svg|href]{display:none}", False),
        (f"@namespace svg {SVG}; .lbl, [svg|href]{{display:none}}", True),
        (".lbl, *|a{display:none}", True), (".lbl, [*|x]{display:none}", True),
        (f"@namespace {SVG}; .lbl{{display:none}}", False),
        ("@namespace url(http://www.w3.org/1999/xhtml); .lbl{display:none}",
         True),
        (f"@namespace {SVG}; *|*.lbl{{display:none}}", True),
        ("@namespace h url(http://www.w3.org/1999/xhtml); h|span.lbl"
         "{display:none}", True),
        # @scope's root and limit (R6H-5)
        ("@scope (main, :foo) { .lbl{display:none} }", False),
        ("@scope (main,) { .lbl{display:none} }", False),
        ("@scope ([x!=y]) { .lbl{display:none} }", False),
        ("@scope (main) to (.zz, :foo){.lbl{visibility:visible}} .lbl"
         "{visibility:hidden}", True),
        ("@scope (main) to (.zz){.lbl{visibility:visible}} .lbl"
         "{visibility:hidden}", False),
        ("@scope (main > a) { .lbl{display:none} }", True),
        ("@scope (:is(main, :foo)) { .lbl{display:none} }", True),
        ("@scope (main) { .lbl, .a..b {display:none} }", False),
        # nested rules soupsieve does not read (R6H-6)
        ("main{ .lbl, .a..b {display:none} }", False),
        ("main{ & .lbl, .a..b {display:none} }", False),
        ("main{ a{ .lbl, .a..b {display:none} } }", False),
        ("main{ @media screen { .lbl, .a..b {display:none} } }", False),
        ("main{ .lbl, &&.x {display:none} }", True),
        ("main{ .lbl, > .x {display:none} }", True),
        ("main{ .lbl, .x:nth-child(foo) {display:none} }", False),
        # an escape's white space before a comment (R6H-9)
        (".\\6c bl, .\\61 /**/b{display:none}", False),
        (".\\6c bl, .\\61\t/**/b{display:none}", False),
        (".lbl, .\\61\\ /**/b{display:none}", False),
        (".lbl, .\\61 /**/ b{display:none}", True),
        (".\\6c bl/**/{display:none}", True),
        # escapes in @supports' property names (R6H-11)
        (".lbl{display:none} @supports (\\64 isplay:none){.lbl"
         "{display:inline}}", False),
        (".lbl{display:none} @supports (dis\\play:none){.lbl"
         "{display:inline}}", False),
        (".lbl{display:none} @supports (\\64 isplay:n\\6f ne){.lbl"
         "{display:inline}}", False),
        (".lbl{display:none} @supports (--\\61:1){.lbl{display:inline}}",
         False),
        (".lbl{display:none} @supports (\\2d-x:1){.lbl{display:inline}}",
         False),
        (".lbl{display:none} @supports not (\\64 isplay:none){.lbl"
         "{display:inline}}", True),
        (".lbl{display:none} @supports (\\66 oo:none){.lbl"
         "{display:inline}}", True),
    )

    def test_selectors(self):
        for selector, valid in self.SELECTORS:
            css = f".lbl, {selector}{{display:none}}"
            with self.subTest(css=css):
                self.assertEqual(link_fails(css), valid)

    def test_sheets(self):
        for css, hidden in self.SHEETS:
            with self.subTest(css=css):
                self.assertEqual(link_fails(css), hidden)

    def test_namespaces(self):
        self.assertEqual(ST.style_namespaces(
            f"@charset 'x'; @namespace svg {self.SVG}; @namespace "
            "url(http://www.w3.org/1999/xhtml); .a{} @namespace z url(q);"),
            {"svg": "http://www.w3.org/2000/svg",
             "": "http://www.w3.org/1999/xhtml"})

    def test_hostile(self):
        """None of these takes long: forgiving lists nested deep, many
        unique ones (each list is read once: R6H-10), a long parent list
        repeated for many nested rules (a page's budget), many prefixes,
        long argument chains."""
        deep = [":is(" * 17 + f".a{i}" + ")" * 17 for i in range(2000)]
        parent = ", ".join(f".a{i}" for i in range(1000))
        for css in (", ".join(deep) + "{display:none}",
                    parent + "{" + "".join(f".c{i}{{display:none}}"
                                           for i in range(3000)) + "}",
                    "@namespace s url(x); " + ", ".join(
                        f"s|a{i}" for i in range(20000)) + "{display:none}",
                    ":not(" * 5000 + ".a" + ")" * 5000 + "{display:none}",
                    ":nth-child(2n of " * 3000 + ".a" + ")" * 3000
                    + "{display:none}",
                    "[x" + "/**/" * 50000 + "=a]{display:none}"):
            with self.subTest(css=css[:30]):
                start = time.monotonic()
                run_page(page("<p>x</p>", head=f"<style>{css}</style>"),
                         "t.html", RB)
                self.assertLess(time.monotonic() - start, 10)


class TestDisplayLaterR6Round4(unittest.TestCase):
    """R6H-3: a focusable element whose display, or an ancestor's, is only
    known later (var()) is reviewed in a file run, unless what hides it
    stops rendering. (Since round 5, a var() of a custom property no
    stylesheet sets, where none the run does not read could set it, is
    read as its fallback, or unset: R6J-3.)"""

    def test_reviewed(self):
        for body, head in (
                ('<div aria-hidden="true" style="--d:none"><button style="'
                 'display:var(--d)">Go</button></div>', ""),
                ('<div aria-hidden="true" class="c"><button class="b">Go'
                 "</button></div>",
                 "<style>.c{--d:none} .b{display:var(--d)}</style>"),
                ('<div aria-hidden="true" style="display:var(--d)"><button>'
                 "Go</button></div>", '<link rel="stylesheet" href="x.css">')):
            with self.subTest(body=body):
                self.assertEqual(TestRulesRound2.found(page(
                    body, head=head), "bb-aria-hidden-focus"),
                    (True, [(NEEDS_REVIEW, "moderate")]))

    def test_shown_still_fails(self):
        self.assertEqual(TestRulesRound2.found(page(
            '<div aria-hidden="true"><button style="display:block">Go'
            "</button></div>"), "bb-aria-hidden-focus"),
            (True, [(FAIL, "serious")]))


# ---------------------------------------------------------------------------
# Round 5, R6I: drawings, names and focus
# ---------------------------------------------------------------------------

#: A file run's verdicts, each measured in Chromium 141 (R6I-1, R6I-2,
#: R6I-3, R6I-5): (body, rule, the verdicts).
_R5_FILE = (
    # R6I-1: an element's own requiredExtensions fails: it renders nothing
    ('<svg width="80" height="20"><a href="/x" requiredExtensions="http://'
     'example.com/x"><rect width="5" height="5"/></a></svg>',
     "bb-link-name", []),
    ('<svg width="80" height="20"><defs><a href="/x" requiredExtensions='
     '"http://example.com/x"><rect width="5" height="5"/></a></defs></svg>',
     "bb-link-name", []),
    ('<svg width="200" height="60"><switch><foreignObject width="100" '
     'height="50" requiredExtensions="http://example.com/SVGExtensions/'
     'EmbeddedXHTML"><p>Read the <a href="/guide"><img src="x.png" alt="">'
     '</a> guide</p></foreignObject><text x="10" y="10">fallback</text>'
     "</switch></svg>", "bb-link-name", []),
    ('<div aria-hidden="true"><svg width="80" height="20"><a href="/x" '
     'requiredExtensions="http://example.com/x"><rect width="5" height="5"/>'
     "</a></svg></div>", "bb-aria-hidden-focus", []),
    # R6I-2: a drawing in a <foreignObject> where nothing paints
    ('<svg width="80" height="20"><defs><foreignObject width="9" height="9">'
     '<svg width="9" height="9"><a href="/x"><rect width="5" height="5"/>'
     "</a></svg></foreignObject></defs></svg>", "bb-link-name", []),
    ('<svg width="80" height="20"><g style="display:none"><foreignObject '
     'width="9" height="9"><svg width="9" height="9"><a href="/x"><rect '
     'width="5" height="5"/></a></svg></foreignObject></g></svg>',
     "bb-link-name", []),
    # R6I-3: an outermost <svg>'s <title> of white space names it nothing
    ('<svg id="o1" width="10" height="10"><title> </title><text>Lab</text>'
     '</svg><a href="/x" aria-labelledby="o1"></a>', "bb-link-name", [FAIL]),
    ('<span id="o4"><svg width="10" height="10"><title>&nbsp;</title><text>'
     'Lab4</text></svg></span><button aria-labelledby="o4"></button>',
     "bb-button-name", [FAIL]),
    ('<svg role="img" width="10" height="10" title="Logo"><title> </title>'
     '<rect width="5" height="5"/></svg>', "bb-svg-name", [FAIL]),
    ('<svg id="u1" width="10" height="10"><text>Lab</text></svg><a href="/x"'
     ' aria-labelledby="u1"></a>', "bb-link-name", []),
    # R6I-5: a <mphantom> is invisible, for the tree and focus too
    ('<math><mphantom><mtext><a href="/x"></a></mtext></mphantom></math>',
     "bb-link-name", []),
    ('<math><mphantom style="visibility:visible"><mtext><a href="/x"></a>'
     "</mtext></mphantom></math>", "bb-link-name", [FAIL]),
    ('<math><mphantom><mtext style="visibility:visible"><a href="/x"></a>'
     "</mtext></mphantom></math>", "bb-link-name", [FAIL]),
    ('<math><mphantom style="visibility:inherit"><mtext><a href="/x"></a>'
     "</mtext></mphantom></math>", "bb-link-name", [FAIL]),
    ('<div aria-hidden="true"><math><mphantom><mtext><a href="/x">Go</a>'
     "</mtext></mphantom></math></div>", "bb-aria-hidden-focus", []),
    ('<div aria-hidden="true"><math><mphantom class="pv"><mtext><a href="/x">'
     "Go</a></mtext></mphantom></math></div>", "bb-aria-hidden-focus",
     [FAIL]),
)


class TestDrawingsR6Round5(unittest.TestCase):
    """R6I-1: an element whose own requiredExtensions Chromium does not
    have renders nothing, in a <switch> or not; R6I-2: a drawing in a
    <foreignObject> where nothing paints is in no tree; R6I-3: an outermost
    <svg>'s <title> of white space names it nothing; R6I-5: a MathML
    <mphantom> is invisible for the tree and focus too, unless the page
    shows it (each measured in Chromium 141)."""

    def test_verdicts(self):
        for body, rule, verdicts in _R5_FILE:
            with self.subTest(body=body):
                got = TestRulesRound2.found(page(
                    body, head="<style>.pv{visibility:visible}</style>"),
                    rule)[1]
                self.assertEqual([v for v, _impact in got], verdicts)


#: A rendered run's names (measured in Chromium 141: R6I-4, R6I-5): (id,
#: markup with `{I}` for the id, FAIL).
_R5_RENDERED = (
    ("r1", '<switch><g/><g role="none"><text>Save</text></g></switch>',
     False),
    ("r2", "<switch><g/><g><text>Save</text></g></switch>", True),
    ("r3", '<switch><g/><g role="group"><text>Save</text></g></switch>',
     True),
    ("r4", '<switch><g/><g role="none" tabindex="0"><text>Save</text></g>'
     "</switch>", True),
    ("r5", '<switch><g/><g aria-label="Lbl"><text>Save</text></g></switch>',
     True),
    ("r6", '<switch><g/><g role="img" aria-label="Lbl"><text>Save</text></g>'
     "</switch>", False),
    ("r7", '<a role="none"><text>Save</text></a>', False),
    ("r8", '<switch><g/><a href="/y" role="group"><text>Save</text></a>'
     "</switch>", True),
    ("r9", '<switch><g/><a role="button"><text>Save</text></a></switch>',
     False),
    ("r10", '<g role="none"><switch><g/><text>Save</text></switch></g>',
     False),
    ("r11", "<g><switch><g/><text>Save</text></switch></g>", True),
    ("r12", "<a><switch><g/><text>Save</text></switch></a>", True),
    ("r13", '<svg role="none"><switch><g/><text>Save</text></switch></svg>',
     False),
    ("r14", "<switch><g/><svg><text>Save</text></svg></switch>", False),
    ("r15", '<switch><g/><text><a role="none" tabindex="0">Save</a></text>'
     "</switch>", False),
    ("r16", '<switch><g/><g role="generic"><text>Save</text></g></switch>',
     False),
)


@unittest.skipUnless(HAVE_BROWSER, _WHY)
class TestDrawingRolesR6Round5(unittest.TestCase):
    """R6I-4, R6I-5, rendered: a drawing's part with no box holds nothing a
    name reads where the role Chromium resolves for it is group (a <g>'s
    and an <a>'s that is no link, where no role they take says otherwise),
    and what such a part with a box holds that has none is cut too; a
    <mphantom>'s link is in no tree (each measured in Chromium 141)."""

    def test_names(self):
        parts = "".join(
            f'<svg width="80" height="20"><a id="{i}" href="/x">{m}</a></svg>'
            for i, m, _f in _R5_RENDERED)
        parts += ('<math><mphantom><mtext><a id="r17" href="/x"></a></mtext>'
                  '</mphantom></math><math><mphantom style="visibility:'
                  'visible"><mtext><a id="r18" href="/x"></a></mtext>'
                  "</mphantom></math>")
        site = _echo_site(self, lambda t: PAGE.format(parts))
        d = tmpdir(self)
        code, _out, err = run("--url", f"{site.base}/p", "--json",
                              d / "r.json", "--fail-on", "never")
        self.assertEqual(code, 0, err)
        report = json.loads((d / "r.json").read_text())
        failed = " ".join(f["snippet"] for p in report["pages"]
                          for f in p["findings"] if f["verdict"] == "fail"
                          and f["rule_id"] == "bb-link-name")
        for i, _markup, fails in (*_R5_RENDERED, ("r17", "", False),
                                  ("r18", "", True)):
            with self.subTest(case=i):
                self.assertEqual(f'id="{i}"' in failed, fails)


class TestDisplayLaterR6Round5(unittest.TestCase):
    """R6I-6, R6J-3: a var() display decides only where it beats a concrete
    one; one under a condition is reviewed; a var() of a custom property
    the page's own styles set nowhere is read as its fallback, or unset,
    where no stylesheet the run does not read could set it (each as
    Chromium 141 computes it)."""

    FA = (".fa,.fab{-moz-osx-font-smoothing:grayscale;display:var("
          "--fa-display,inline-block);font-style:normal}")
    LINKED = '<link rel="stylesheet" href="x.css">'

    def test_verdicts(self):
        for body, head, want in (
                ('<div aria-hidden="true" class="m"><button class="b">Go'
                 "</button></div>",
                 "<style>.b{display:var(--d)} .m .b{display:block}</style>",
                 FAIL),
                ('<div style="display:var(--d, block)"><div '
                 'aria-hidden="true"><button>Go</button></div></div>', "",
                 FAIL),
                ('<div aria-hidden="true"><nav class="menu"><a href="/x">x</a>'
                 "</nav></div>", "<style>:root{--m:none} .menu{display:none} "
                 "@media (min-width:1px){.menu{display:var(--m)}}</style>",
                 NEEDS_REVIEW),
                ('<div aria-hidden="true"><a class="fab fa-twitter" href="/x" '
                 'aria-label="Twitter"></a></div>',
                 f"<style>{self.FA}</style>", FAIL),
                ('<div aria-hidden="true"><a class="fab fa-twitter" href="/x" '
                 'aria-label="Twitter"></a></div>',
                 f"{self.LINKED}<style>{self.FA}</style>", NEEDS_REVIEW),
                ('<div aria-hidden="true"><button style="display:var(--zz)">Go'
                 "</button></div>", "", FAIL),
                ('<div aria-hidden="true"><button style="display:var(--zz, '
                 'none)">Go</button></div>', "", NEEDS_REVIEW),
                ('<div aria-hidden="true" style="visibility:hidden"><button '
                 'style="visibility:var(--v, visible)">Go</button></div>', "",
                 FAIL),
                ('<div aria-hidden="true" style="visibility:hidden"><button '
                 'style="visibility:var(--nope)">Go</button></div>', "",
                 None)):
            with self.subTest(body=body, head=head):
                got = TestRulesRound2.found(page(body, head=head),
                                            "bb-aria-hidden-focus")[1]
                self.assertEqual([v for v, _impact in got],
                                 [want] if want else [])


# ---------------------------------------------------------------------------
# Round 5, R6J: the rules and claims side
# ---------------------------------------------------------------------------

class TestOwnStyleR6Round5(unittest.TestCase):
    """R6J-1 to R6J-8: a page's own rules as Chromium 141 reads them, each
    case measured there: (css, the link's text hidden)."""

    #: `.lbl, X{display:none}`: the rule stands where Chromium takes X.
    SELECTORS = (
        ("::slotted(b)::backdrop", True), ("::slotted(b)::checkmark", True),
        ("::slotted(b)::picker-icon", True),
        ("::slotted(b)::picker(select)", True),
        ("::slotted(b)::selection", False), ("::part(x)::cue(b)", False),
        ("::part(x)::cue", True), ("::picker(select)::cue", True),
        ("::details-content::cue(b)", False),
        (":nth-child(2n/**/of .a)", True),
        (":nth-child(2n+1/**/of .a)", True),
        (":nth-last-child(odd/**/of .a)", True),
        (":nth-of-type(2n/**/of .a)", False), (":not(.a >)", False),
        (":has(.a + + .b)", False), (":host(:not(.a .b))", False),
        (":nth-child(2n of ::before .a)", False),
        (":nth-child(2n of .a >)", False), (":not(.a > > .b)", False),
        (":has(> .a > > .b)", False),
        ("::view-transition-group(x .c)", True))
    SVG = "@namespace svg url(http://www.w3.org/2000/svg); "
    #: Stylesheets.
    SHEETS = (
        # :has() in a list a :has() holds (R6J-4)
        ("main:has(:is(:has(.lbl))) .lbl{display:none}", False),
        ("main:has(:where(.x, :has(.lbl))) .lbl{display:none}", False),
        ("main :is(:has(.lbl)) .lbl{display:none}", True),
        ("main:not(:has(:is(:has(.q)))) .lbl{display:none}", True),
        # a member dropped from a forgiving list alone (R6J-5)
        ("main :is(:not(.a >), .lbl){display:none}", True),
        ("main :where(:nth-child(2n of .a >), .lbl){display:none}", True),
        # prefixed type selectors (R6J-2), escaped prefixes (R6J-7)
        ("@namespace h url(http://www.w3.org/1999/xhtml); h|span"
         "{display:none}", True),
        (SVG + "svg|span{display:none}", False),
        (SVG + ".lbl, \\73 vg|a{display:none}", True),
        (SVG + ".lbl, sv\\67|a{display:none}", True),
        (SVG + ".lbl, SVG|a{display:none}", False),
        (SVG + ".lbl, :not(\\73 vg|a){display:none}", True),
        (SVG + ".lbl, .a|b{display:none}", False),
        # escaped flags in nested rules, comments in brackets (R6J-7)
        ("main{ .lbl, [x=a \\69]{display:none} }", True),
        ("main{ .lbl, [x=a \\73]{display:none} }", False),
        ("span[class=lb\\6c/**/i]{display:none}", True),
        ("span[class=LB\\4c/**/i]{display:none}", True),
        ("span[class=\\6c b\\6c /**/i]{display:none}", True),
        # @scope's lists (R6J-7)
        ("@scope (main) to(.b) { .lbl{color:red} } .lbl{display:none}", True),
        # block at-rules Chromium drops before @namespace (R6J-6)
        ("@supports foo {} " + SVG + ".lbl, svg|a{display:none}", True),
        ("@supports (foo:bar) {} " + SVG + ".lbl, svg|a{display:none}",
         False),
        ("@supports (a) and (b) or (c) {} " + SVG + ".lbl, svg|a"
         "{display:none}", True),
        ("@layer a b {} " + SVG + ".lbl, svg|a{display:none}", True),
        ("@layer a.b {} " + SVG + ".lbl, svg|a{display:none}", False),
        ("@scope (.a..b) {} " + SVG + ".lbl, svg|a{display:none}", True),
        ("@scope (.a) to (.b::before) {} " + SVG + ".lbl, svg|a"
         "{display:none}", True),
        ("@scope (.a) to(.b) {} " + SVG + ".lbl, svg|a{display:none}", True),
        ("@property --x {} " + SVG + ".lbl, svg|a{display:none}", True),
        ('@property --x {syntax:"*";inherits:false} ' + SVG + ".lbl, svg|a"
         "{display:none}", False),
        ("@counter-style none {} " + SVG + ".lbl, svg|a{display:none}", True),
        ("@counter-style Decimal {} " + SVG + ".lbl, svg|a{display:none}",
         True),
        ("@counter-style x {} " + SVG + ".lbl, svg|a{display:none}", False),
        ("@font-palette-values x {} " + SVG + ".lbl, svg|a{display:none}",
         True),
        ("@position-try --x {} " + SVG + ".lbl, svg|a{display:none}", False),
        ("@page :foo {} " + SVG + ".lbl, svg|a{display:none}", True),
        ("@page x:left {} " + SVG + ".lbl, svg|a{display:none}", False),
        ("@page x :left {} " + SVG + ".lbl, svg|a{display:none}", True),
        ("@font-face x {} " + SVG + ".lbl, svg|a{display:none}", True),
        ("@keyframes \"x\" {} " + SVG + ".lbl, svg|a{display:none}", True),
        ("@-webkit-keyframes \"x\" {} " + SVG + ".lbl, svg|a{display:none}",
         False),
        ("@keyframes none {} " + SVG + ".lbl, svg|a{display:none}", False),
        ("@container foo {} " + SVG + ".lbl, svg|a{display:none}", True),
        ("@container foo (width > 1px) {} " + SVG + ".lbl, svg|a"
         "{display:none}", False),
        ("@container (width>1px) foo {} " + SVG + ".lbl, svg|a"
         "{display:none}", True),
        ("@font-feature-values serif {} " + SVG + ".lbl, svg|a{display:none}",
         True),
        ("@font-feature-values x y {} " + SVG + ".lbl, svg|a{display:none}",
         False),
        ("@function --f(x) {} " + SVG + ".lbl, svg|a{display:none}", True),
        ("@function --f(--a) {} " + SVG + ".lbl, svg|a{display:none}", False),
        ("@import url(x.css) supports(foo:bar); @layer q; " + SVG
         + ".lbl, svg|a{display:none}", True),
        ("@import url(x.css) supports(display:block); @layer q; " + SVG
         + ".lbl, svg|a{display:none}", False),
    )

    def test_selectors(self):
        for selector, valid in self.SELECTORS:
            css = f".lbl, {selector}{{display:none}}"
            with self.subTest(css=css):
                self.assertEqual(link_fails(css), valid)

    def test_sheets(self):
        for css, hidden in self.SHEETS:
            with self.subTest(css=css):
                self.assertEqual(link_fails(css), hidden)

    def test_hostile(self):
        """None of these takes long: escapes in ::part()'s names on a near
        miss (R6J-1), many :has() under deep :not() (R6J-8), many
        :has() in :is() in :has(), comments in An+B, escaped prefixes,
        block at-rules before @namespace."""
        for css in (".a, ::part(" + "\\61 " * 40 + "!){display:none}",
                    ":not(" * 8000 + ":has(.a)" * 8000 + ")" * 8000
                    + "{display:none}",
                    ".x:has(" + ", ".join([":is(:has(.a), .b)"] * 20000)
                    + "){display:none}",
                    ", ".join(f":nth-child(2n/**/of .a{i})"
                              for i in range(5000)) + "{display:none}",
                    "@namespace svg url(x); " + ", ".join(
                        f"\\73 vg|a{i}" for i in range(5000))
                    + "{display:none}",
                    "@supports foo {}" * 20000 + "@namespace s url(x);"):
            with self.subTest(css=css[:30]):
                start = time.monotonic()
                run_page(page("<p>x</p>", head=f"<style>{css}</style>"),
                         "t.html", RB)
                self.assertLess(time.monotonic() - start, 10)


# ---------------------------------------------------------------------------
# Round 6, R6K: drawings, names and focus
# ---------------------------------------------------------------------------

_X = "http://www.w3.org/1999/xhtml"
#: A file run's verdicts, each measured in Chromium 141 (R6K-2, R6K-8,
#: R6K-9): (body, rule, the verdicts).
_R6_FILE = (
    # R6K-2: white space after the extensions passes; before them fails
    (f'<svg width="60" height="20"><a href="/x" requiredExtensions="{_X} ">'
     '<rect width="9" height="9"/></a></svg>', "bb-link-name", [FAIL]),
    (f'<svg width="60" height="20"><a href="/x" requiredExtensions="{_X}\t">'
     '<rect width="9" height="9"/></a></svg>', "bb-link-name", [FAIL]),
    (f'<svg width="60" height="20"><a href="/x" requiredExtensions=" {_X}">'
     '<rect width="9" height="9"/></a></svg>', "bb-link-name", []),
    (f'<div aria-hidden="true"><svg width="60" height="20"><a href="/x" '
     f'requiredExtensions="{_X} "><text y="15">w</text></a></svg></div>',
     "bb-aria-hidden-focus", [FAIL]),
    # R6K-8: an <mphantom>'s visibility:revert hides, as the browser's
    # own stylesheet has it
    ('<math><mphantom style="visibility:revert"><mtext><a href="/x"></a>'
     "</mtext></mphantom></math>", "bb-link-name", []),
    ('<div aria-hidden="true"><math><mphantom style="visibility:revert">'
     '<mtext><a href="/x">f2</a></mtext></mphantom></math></div>',
     "bb-aria-hidden-focus", []),
    ('<a href="/x" aria-labelledby="l8"></a><math id="l8"><mrow><mphantom '
     'style="visibility:revert"><mi>x5</mi></mphantom></mrow></math>',
     "bb-link-name", [FAIL]),
    # R6K-9: through aria-labelledby, content made visible again inside an
    # invisible HTML or MathML element or a text part is not read; inside
    # a drawing's <g> it is
    ('<a href="/x" aria-labelledby="l9"></a><div id="l9"><span style="'
     'visibility:hidden"><span style="visibility:visible">H1</span></span>'
     "</div>", "bb-link-name", [FAIL]),
    ('<a href="/x" aria-labelledby="l10"></a><math id="l10"><mrow><mphantom>'
     '<mi style="visibility:visible">x3</mi></mphantom></mrow></math>',
     "bb-link-name", [FAIL]),
    ('<a href="/x" aria-labelledby="l11"></a><svg id="l11" width="60" '
     'height="20"><text y="15" style="visibility:hidden"><tspan style="'
     'visibility:visible">S</tspan></text></svg>', "bb-link-name", [FAIL]),
    ('<a href="/x" aria-labelledby="l12"></a><svg id="l12" width="60" '
     'height="20"><g style="visibility:hidden"><text y="15" style="'
     'visibility:visible">S</text></g></svg>', "bb-link-name", []),
    ('<a href="/x" aria-labelledby="l13"></a><div id="l13" style="'
     'visibility:hidden">Q<span style="visibility:visible">W</span></div>',
     "bb-link-name", []),
    ('<a href="/x"><span style="visibility:hidden"><span style="visibility:'
     'visible">H2</span></span></a>', "bb-link-name", []),
)


class TestDrawingsR6Round6(unittest.TestCase):
    """R6K-2: a requiredExtensions with white space after it passes, one
    with white space before it fails; R6K-8: an <mphantom>'s revert hides
    it; R6K-9: through aria-labelledby, content made visible again inside
    invisible content is not read, but inside a drawing's <g>; R6K-11: in
    XHTML, `requiredextensions` is no condition (each measured in Chromium
    141)."""

    def test_verdicts(self):
        for body, rule, verdicts in _R6_FILE:
            with self.subTest(body=body):
                got = TestRulesRound2.found(page(body), rule)[1]
                self.assertEqual([v for v, _impact in got], verdicts)

    def test_xhtml_case(self):
        xhtml = ('<?xml version="1.0" encoding="UTF-8"?><html xmlns="http://'
                 'www.w3.org/1999/xhtml" lang="en" xml:lang="en"><head><title>'
                 "T</title></head><body><main><h1>x</h1><svg xmlns=\"http://"
                 'www.w3.org/2000/svg" width="40" height="20"><a href="/x" '
                 'requiredextensions="http://example.com/x"><rect width="9" '
                 'height="9"/></a></svg></main></body></html>')
        self.assertEqual(TestRulesRound2.found(xhtml, "bb-link-name",
                                               path="t.xhtml")[1],
                         [(FAIL, "blocker")])


#: A rendered run's names (measured in Chromium 141: R6K-2, R6K-3, R6K-7):
#: (id, markup with `{I}` for the link's id, FAIL).
_R6_RENDERED = (
    ("s1", f'<svg width="60" height="20"><g requiredExtensions="{_X}" '
     'style="display:none"><a id="s1" href="/x"><rect width="5" height="5"/>'
     "</a></g></svg>", True),
    ("s2", f'<svg width="60" height="20"><defs requiredExtensions="{_X}"><a '
     'id="s2" href="/x"><rect width="5" height="5"/></a></defs></svg>', True),
    ("s3", f'<svg width="60" height="20"><mask id="m3" requiredExtensions="'
     f'{_X}"><a id="s3" href="/x"><rect width="5" height="5"/></a></mask>'
     "</svg>", True),
    ("s4", '<svg width="60" height="20"><defs requiredExtensions="http://'
     'example.com/x"><a id="s4" href="/x"><rect width="5" height="5"/></a>'
     "</defs></svg>", False),
    ("s5", '<svg width="60" height="20"><clipPath id="c5" systemLanguage="xx">'
     '<a id="s5" href="/x"><rect width="5" height="5"/></a></clipPath></svg>',
     True),
    ("s6", f'<svg width="60" height="20"><a id="s6" href="/x" '
     f'requiredExtensions="{_X} "><rect width="9" height="9"/></a></svg>',
     True),
    ("s7", '<svg width="60" height="20"><a id="s7" href="/x" '
     'requiredExtensions=" http://www.w3.org/1999/xhtml"><rect width="9" '
     'height="9"/></a></svg>', False),
    ("s8", '<a id="s8" href="/x" aria-labelledby="s8l"></a><svg id="s8l" '
     'width="60" height="20"><g role="region"><switch><text></text><text>U'
     "</text></switch></g></svg>", True),
    ("s9", '<a id="s9" href="/x" aria-labelledby="s9l"></a><svg id="s9l" '
     'width="60" height="20"><g role="region" aria-label="R"><switch><text>'
     "</text><text>U</text></switch></g></svg>", False),
    ("s10", '<svg width="60" height="20"><a id="s10" href="/x"><switch><g/>'
     '<g role="form"><text>P</text></g></switch></a></svg>', True),
)


@unittest.skipUnless(HAVE_BROWSER, _WHY)
class TestDrawingCaptureR6Round6(unittest.TestCase):
    """R6K-2, R6K-3, R6K-7, rendered: a box that never paints, whose
    conditions pass, holds links in the tree; a requiredExtensions with
    white space after it passes, before it fails; a <g> with role region
    or form and no name cuts what it holds with no box as a group does
    (each measured in Chromium 141)."""

    def test_names(self):
        site = _echo_site(self, lambda t: PAGE.format(
            "".join(m for _i, m, _f in _R6_RENDERED)))
        d = tmpdir(self)
        code, _out, err = run("--url", f"{site.base}/p", "--json",
                              d / "r.json", "--fail-on", "never")
        self.assertEqual(code, 0, err)
        report = json.loads((d / "r.json").read_text())
        failed = " ".join(f["snippet"] for p in report["pages"]
                          for f in p["findings"] if f["verdict"] == "fail"
                          and f["rule_id"] == "bb-link-name")
        for i, _markup, fails in _R6_RENDERED:
            with self.subTest(case=i):
                self.assertEqual(f'id="{i}"' in failed, fails)


class TestDisplayLaterR6Round6(unittest.TestCase):
    """R6K-4, R6K-5, R6K-12, R6L-1, R6L-2: a var() display level with a
    concrete one, or a var()'s fallback level with a hide, is reviewed (the
    run reads no specificity); a custom property registered by @property,
    named with escapes or with a comment before its colon is set; one set
    in another case counts as set (as Chromium 141 computes each)."""

    def test_verdicts(self):
        linked = '<link rel="stylesheet" href="x.css">'
        for css, body, head, want in (
                (".x.y{display:none} .x{display:var(--d, inline)}",
                 '<a href="#a" class="x y">a</a>', "", NEEDS_REVIEW),
                ("#i{display:none} .x{display:var(--d, inline)}",
                 '<a id="i" class="x" href="#a">a</a>', "", NEEDS_REVIEW),
                (".y{display:block} .x{display:var(--d, none)}",
                 '<a class="x y" href="#a">a</a>', "", NEEDS_REVIEW),
                (".y{display:block} .x{display:var(--d)}",
                 '<a class="x y" href="#a">a</a>', linked, NEEDS_REVIEW),
                (":root{--closed:none} .menu a{display:block} .menu.closed a"
                 "{display:var(--closed)}",
                 '<nav class="menu closed"><a href="/x">Go</a></nav>', "",
                 NEEDS_REVIEW),
                (":root{--x:none} .menu a {display:block} @media "
                 "(min-width:1px){ .menu.closed a {display:var(--x)} }",
                 '<nav class="menu closed"><a href="/x">Go</a></nav>', "",
                 NEEDS_REVIEW),
                ("@property --d { syntax: '*'; inherits: false; "
                 "initial-value: none; } .x{display:var(--d, inline)}",
                 '<a href="#a" class="x">a</a>', "", NEEDS_REVIEW),
                (":root{--\\73 hown:none} .x{display:var(--shown, block)}",
                 '<a href="#a" class="x">a</a>', "", NEEDS_REVIEW),
                (":root{--menu/**/: none} .x{display:var(--menu, block)}",
                 '<a href="#a" class="x">a</a>', "", NEEDS_REVIEW),
                (".p{--Fa:none} .x{display:var(--fa, inline)}",
                 '<div class="p"><a href="#a" class="x">a</a></div>', "",
                 NEEDS_REVIEW),
                (".fa{display:var(--fa-display, inline-block)}",
                 '<a href="#a" class="fa" aria-label="T"></a>', "", FAIL),
                (".b{display:var(--d)} .m .b{display:block}",
                 '<div class="m"><button class="b">Go</button></div>', "",
                 FAIL)):
            with self.subTest(css=css):
                got = TestRulesRound2.found(page(
                    f'<div aria-hidden="true">{body}</div>',
                    head=f"{head}<style>{css}</style>"),
                    "bb-aria-hidden-focus")[1]
                self.assertEqual([v for v, _impact in got], [want])

    def test_registered_visibility(self):
        """An @property's initial-value is the var()'s, not its fallback."""
        css = ("@property --v { syntax: '*'; inherits: false; initial-value: "
               "hidden; } .p { visibility: hidden; } .c { visibility: "
               "var(--v, visible); }")
        got = TestRulesRound2.found(page(
            '<a href="/x"><span class="p"><span class="c">Home</span></span>'
            "</a>", head=f"<style>{css}</style>"), "bb-link-name")[1]
        self.assertEqual([v for v, _impact in got], [FAIL])


# ---------------------------------------------------------------------------
# Round 6, R6L: the rules and claims side
# ---------------------------------------------------------------------------

class TestOwnStyleR6Round6(unittest.TestCase):
    """R6L-3 to R6L-10: a page's own rules as Chromium 141 reads them, each
    case measured there: (css, the link's text hidden)."""

    #: `.lbl, X{display:none}`: the rule stands where Chromium takes X.
    SELECTORS = (
        ("::view-transition-old(* .x)", False),
        ("::view-transition-old(* .a.b)", False),
        ("::view-transition-old(*.a .b)", True),
        ("::view-transition-old(foo .a .b)", True),
        ("::view-transition-old(.a .b)", True),
        ("::view-transition-old(foo . a)", False),
        ("::part(x):not(:hover)", True),
        ("::part(x):not(:hover, :focus)", True),
        ("::part(x):not(:not(:hover))", True),
        ("::part(x):not(:is(:hover))", True),
        ("::part(x):not(:state(x))", True), ("::part(x):not(.a)", False),
        ("::part(x):not(:first-child)", False),
        ("::part(x):not(::before)", False),
        ("::part(x):not(:has(.a))", False),
        ("::part(x):not(:hover .a)", False),
        ("::part(x):not(:hover):focus", True),
        ("::details-content:not(:hover)", True),
        ("::picker(select):not(:open)", True),
        (":host(:has(.a))", False), ("::slotted(:has(.a))", False),
        (":host-context(:has(.a))", False), (":host(:not(:has(.a)))", False),
        (":host(:is(:has(.a)))", True), ("::slotted(:is(:has(.a), .b))", True),
        (":is(:nth-child(2n of ::before))", True),
        (":not(:nth-child(2n of ::before))", False),
        (":has(:nth-child(2n of ::before))", False),
        (":nth-\\63 hild(2n/**/of .a)", True))
    SVG = "@namespace svg url(http://www.w3.org/2000/svg); "
    TAIL = SVG + ".lbl, svg|a{display:none}"
    #: Stylesheets: (css, the link's text hidden).
    SHEETS = (
        ("@font-feature-values emoji {} " + TAIL, False),
        ("@font-feature-values ui-monospace {} " + TAIL, False),
        ("@font-feature-values -webkit-body {} " + TAIL, True),
        ("@font-feature-values serif x {} " + TAIL, True),
        ("@font-feature-values emoji x {} " + TAIL, False),
        ("@container default (width > 1px) {} " + TAIL, True),
        ("@container auto (width > 1px) {} " + TAIL, False),
        ("@function --foo() returns <length> garbage {} " + TAIL, True),
        ("@function --foo() returns <length> | auto {} " + TAIL, True),
        ("@function --foo() returns <length># {} " + TAIL, False),
        ("@function --foo() returns type(<length> | auto) {} " + TAIL, False),
        ("@function --foo() returns <foo> {} " + TAIL, True),
        ("@function --foo() returns auto {} " + TAIL, False),
        ("@scope (:nth-child(2n of .a::before)) {} " + TAIL, True),
        ("@scope (.a) t\\6f  (.b) {} " + TAIL, False),
    )

    def test_selectors(self):
        for selector, valid in self.SELECTORS:
            css = f".lbl, {selector}{{display:none}}"
            with self.subTest(css=css):
                self.assertEqual(link_fails(css), valid)

    def test_sheets(self):
        for css, hidden in self.SHEETS:
            with self.subTest(css=css):
                self.assertEqual(link_fails(css), hidden)

    def test_blocks_deep(self):
        """A rule inside seven blocks is read, inside eight not, as the
        README says (R6L-3)."""
        for depth, read in ((7, True), (8, False)):
            css = ("".join(f"@layer l{k}{{" for k in range(depth))
                   + ".x{display:none}" + "}" * depth)
            with self.subTest(depth=depth):
                self.assertEqual(bool(ST.style_rules(css)), read)



# ---------------------------------------------------------------------------
# Round 7, R6M: drawings, names and focus
# ---------------------------------------------------------------------------

_VH = 'style="visibility:hidden"'
_VV = 'style="visibility:visible"'
_DN = 'style="display:none"'
_SV = '<svg width="60" height="20">'
_SVL = '<svg id="L" width="60" height="20">'


def _lb(target: str) -> str:
    """A link labelled by `target`'s element whose id is "L"."""
    return '<a href="/x" aria-labelledby="L"></a>' + target


#: A file run's bb-link-name, each measured in Chromium 141 (R6M-1,
#: R6M-3, R6M-4, R6M-7, R6M-9 and round 7's): (body, it FAILs).
_R7_NAMES = (
    # R6M-1: a hidden target is read whole, what is hidden in it too
    (_lb(f'<div hidden><span id="L"><span {_VH}>Close1</span></span></div>'),
     False),
    (_lb(f'<div {_VH}><span id="L"><span {_VH}>R4<b {_VV}>W4</b></span>'
         "</span></div>"), False),
    (_lb(f'{_SV}<g id="L" {_VH}><text y="15" {_VH}>A6<tspan {_VV}>C6'
         "</tspan></text></g></svg>"), False),
    (_lb(f'<div hidden><span id="L"><span {_DN}>B</span></span></div>'),
     False),
    (_lb('<div hidden><span id="L"><span aria-hidden="true">B</span></span>'
         "</div>"), False),
    (_lb('<div hidden><span id="L"><span inert>B</span></span></div>'),
     False),
    (_lb('<div hidden><span id="L"><details><summary></summary>D</details>'
         "</span></div>"), False),
    (_lb('<div hidden><span id="L"><span hidden="until-found">B</span>'
         "</span></div>"), False),
    (_lb('<span id="L" style="display:none;content-visibility:hidden">A'
         "</span>"), False),
    (_lb('<div hidden><details><summary>s</summary><span id="L">A</span>'
         "</details></div>"), False),
    (_lb('<details><summary>s</summary><div hidden><span id="L">A</span>'
         "</div></details>"), True),
    (_lb('<div hidden><span id="L"><datalist><option value="B">B</option>'
         "</datalist></span></div>"), True),
    (_lb('<div hidden><span id="L"><ruby><rp>(</rp><rt></rt><rp>)</rp>'
         "</ruby></span></div>"), False),
    (_lb(f'<span id="L" aria-hidden="true"><span {_DN}>B</span></span>'),
     False),
    (_lb(f'<div inert><span id="L"><span {_DN}>B</span></span></div>'),
     False),
    # a target rendered but hidden: what a descendant skips stays unread
    (_lb(f'<span id="L" {_VH}><span style="display:block;'
         'content-visibility:hidden">D</span></span>'), True),
    (_lb(f'<div {_VH}><details id="L"><summary></summary>D</details>'
         "</div>"), True),
    (_lb('<span id="L" aria-hidden="true"><details><summary></summary>D'
         "</details></span>"), True),
    # a shown target: what is made visible again inside invisible content
    # is read past a part whose role is group (round 7)
    (_lb(f'<div id="L"><span role="group"><span {_VH}><span {_VV}>H</span>'
         "</span></span></div>"), False),
    (_lb(f'<div id="L"><fieldset><span {_VH}><span {_VV}>H</span></span>'
         "</fieldset></div>"), False),
    (_lb(f'<div id="L"><address><span {_VH}><span {_VV}>H</span></span>'
         "</address></div>"), False),
    (_lb(f'<div id="L"><nav><span {_VH}><span {_VV}>H</span></span></nav>'
         "</div>"), True),
    (_lb(f'<div id="L" role="group"><span {_VH}><span {_VV}>H</span>'
         "</span></div>"), True),
    (_lb(f'<div id="L"><fieldset role="none"><span {_VH}><span {_VV}>H'
         "</span></span></fieldset></div>"), True),
    (_lb(f'<div id="L"><fieldset role="region"><span {_VH}><span {_VV}>H'
         "</span></span></fieldset></div>"), False),
    (_lb(f'<div id="L"><fieldset role="region" title=""><span {_VH}><span '
         f"{_VV}>H</span></span></fieldset></div>"), True),
    (_lb(f'{_SVL}<g><text y="15" {_VH}>'
         f"<tspan {_VV}>B</tspan></text></g></svg>"), False),
    (_lb(f'{_SVL}<text y="15" {_VH}><tspan '
         f"{_VV}>B</tspan></text></svg>"), True),
    (_lb(f'{_SVL}<g><mask id="m1" {_VH}>'
         f"<text {_VV}>B</text></mask></g></svg>"), False),
    (_lb(f'{_SVL}<foreignObject width="50" '
         f'height="20"><span {_VH}><b {_VV}>B</b></span></foreignObject>'
         "</svg>"), False),
    # R6M-3: <g role="region"> or "form" is one while named
    (_lb(f'{_SV}<g id="L"><g role="region" title=""><text y="15" {_VH}>'
         f"<tspan {_VV}>B</tspan></text></g></g></svg>"), True),
    (_lb(f'{_SV}<g id="L"><g role="region" aria-labelledby="nope"><text '
         f'y="15" {_VH}><tspan {_VV}>B</tspan></text></g></g></svg>'), False),
    (_lb(f'{_SV}<g id="L"><g role="region" aria-label=""><text y="15" '
         f"{_VH}><tspan {_VV}>B</tspan></text></g></g></svg>"), False),
    (_lb(f'{_SV}<g id="L"><g role="region" aria-labelledby="E"><text '
         f'y="15" {_VH}><tspan {_VV}>B</tspan></text></g></g></svg>'
         '<span id="E"></span>'), True),
    (_lb(f'{_SV}<g id="L"><g role="form" title=" "><text y="15" {_VH}>'
         f"<tspan {_VV}>B</tspan></text></g></g></svg>"), True),
    # R6M-7 and the parts of a drawing Chromium never reads into a name
    (f'{_SV}<a href="/1"><text y="15" requiredExtensions="http://example.'
     'com/x">Alt1</text></a></svg>', True),
    (f'{_SV}<a href="/2"><g requiredExtensions=" http://www.w3.org/1999/'
     'xhtml"><text y="15">Alt2</text></g></a></svg>', True),
    (f'{_SV}<a href="/x"><metadata>M</metadata></a></svg>', True),
    (f'{_SV}<a href="/x"><foo>M</foo></a></svg>', True),
    (f'{_SV}<a href="/x"><text y="15"><g>M</g></text></a></svg>', True),
    (f'{_SV}<a href="/x"><g><tspan>M</tspan></g></a></svg>', True),
    (f'{_SV}<a href="/x"><use><text>M</text></use></a></svg>', True),
    (f'{_SV}<a href="/x"><animate><text>M</text></animate></a></svg>', True),
    (f'{_SV}<a href="/x"><feFlood><text>M</text></feFlood></a></svg>', True),
    (f'{_SV}<a href="/x"><filter><feMerge><feMergeNode><text>M</text>'
     "</feMergeNode></feMerge></filter></a></svg>", True),
    (f'{_SV}<a href="/x"><filter><feFlood><text>M</text></feFlood>'
     "</filter></a></svg>", False),
    (f'{_SV}<a href="/x"><tspan>M</tspan></a></svg>', False),
    (f'{_SV}<a href="/x"><text y="15"><text>M</text></text></a></svg>',
     False),
    (f'{_SV}<a href="/x"><text y="15"><title>M</title></text></a></svg>',
     False),
    (f'{_SV}<a href="/x"><linearGradient><stop><text>M</text></stop>'
     "</linearGradient></a></svg>", False),
    (_lb(f'<div hidden>{_SV}<g id="L"><metadata>M</metadata></g></svg>'
         "</div>"), False),
    (_lb(f'<div hidden>{_SV}<g id="L"><text requiredExtensions="http://'
         'example.com/x">M</text></g></svg></div>'), False),
    (_lb(f'<div hidden>{_SV}<g id="L"><use><text>M</text></use></g></svg>'
         "</div>"), True),
    (_lb(f'<div hidden>{_SV}<text id="L" y="15"><g>M</g></text></svg>'
         "</div>"), True),
    (_lb(f'{_SV}<text id="L" y="15" systemLanguage="xx"><tspan {_VH}>B'
         "</tspan></text></svg>"), False),
    # R6M-9: an <svg> in a link gives its own name, its <title>
    ('<a href="/x"><svg width="20" height="20"><title>Home1</title><rect '
     'width="5" height="5"/></svg></a>', False),
    ('<a href="/x"><svg width="20" height="20"><text y="15">Txt2</text>'
     "</svg></a>", True),
)
#: R6M-4: an invisible part of a drawing, the target's child, keeps what
#: is made visible again inside it out of the name; but a <g>, an <a>
#: that is no link, an inner <svg> or a <foreignObject>: (part, FAIL).
_R7_PARTS = tuple(
    (f'<{p} {_VH}><text y="15" {_VV}>B</text></{p.split()[0]}>', fails)
    for p, fails in (
        ('mask id="m"', True), ('clipPath id="c"', True),
        ('pattern id="p"', True), ('marker id="k"', True),
        ('symbol id="s"', True), ('linearGradient id="g"', True),
        ('radialGradient id="r"', True), ('filter id="f"', True),
        ("defs", True), ('rect width="5" height="5"', True),
        ('circle r="5"', True), ('image width="5" height="5"', True),
        ("switch", True), ("g", False), ("a", False), ("svg", False))) + (
    (f'<text y="15" {_VH}><tspan {_VV}>B</tspan></text>', True),
    (f'<foreignObject width="50" height="20" {_VH}><span {_VV}>B</span>'
     "</foreignObject>", False),
    ('<mask id="m2"><text>B</text></mask>', False),
    ('<rect width="5" height="5"><text>B</text></rect>', False))


class TestNamesR6Round7(unittest.TestCase):
    """R6M-1, R6M-3, R6M-4, R6M-7, R6M-9: names through aria-labelledby
    where its target is hidden (read whole) or shown (past a part whose
    role is group), region and form as named, a drawing's parts Chromium
    never reads, as a file run computes them (each measured in Chromium
    141)."""

    def test_names(self):
        for body, fails in _R7_NAMES:
            with self.subTest(body=body):
                got = TestRulesRound2.found(page(body), "bb-link-name")[1]
                self.assertEqual([v for v, _i in got],
                                 [FAIL] if fails else [])

    def test_parts(self):
        for part, fails in _R7_PARTS:
            body = _lb(f'<svg id="L" width="60" height="20">{part}</svg>')
            with self.subTest(part=part):
                got = TestRulesRound2.found(page(body), "bb-link-name")[1]
                self.assertEqual([v for v, _i in got],
                                 [FAIL] if fails else [])

    def test_tooltip(self):
        """R6M-1's t3: a tooltip hidden, its text hidden too, by rules."""
        got = TestRulesRound2.found(page(
            '<button aria-labelledby="l3"></button><span class="tip" id="l3">'
            '<span class="txt">Delete3</span></span>',
            head="<style>.tip{visibility:hidden} .tip .txt{visibility:"
                 "hidden}</style>"), "bb-button-name")[1]
        self.assertEqual(got, [])


#: A rendered run's names and focus (measured in Chromium 141: R6M-1,
#: R6M-3, R6M-6): (id, markup with `{I}` for the link's id, FAIL).
_R7_RENDERED = (
    ("u1", '<a id="u1" href="/1" aria-labelledby="u1l"></a><div hidden>'
     f'<span id="u1l"><span {_VH}>Close1</span></span></div>', False),
    ("u2", '<a id="u2" href="/2" aria-labelledby="u2l"></a><div '
     f'{_VH}><span id="u2l"><span {_DN}>B</span></span></div>', False),
    ("u3", '<a id="u3" href="/3" aria-labelledby="u3l"></a><span id="u3l" '
     f'{_VH}><span style="display:block;content-visibility:hidden">D</span>'
     "</span>", True),
    ("u4", '<a id="u4" href="/4" aria-labelledby="u4l"></a><div id="u4l">'
     f'<span role="group"><span {_VH}><span {_VV}>H</span></span></span>'
     "</div>", False),
    ("u5", '<a id="u5" href="/5" aria-labelledby="u5l"></a><svg id="u5l" '
     f'width="60" height="20"><mask id="u5m" {_VH}><text y="15" {_VV}>B'
     "</text></mask></svg>", True),
    ("u6", '<a id="u6" href="/6" aria-labelledby="u6l"></a><svg id="u6l" '
     'width="60" height="20"><g role="region" title=""><switch><text>'
     "</text><text>U1</text></switch></g></svg>", False),
    ("u7", '<a id="u7" href="/7" aria-labelledby="u7l"></a><svg id="u7l" '
     'width="60" height="20"><g role="region" aria-labelledby="nope"><switch>'
     "<text></text><text>U2</text></switch></g></svg>", True),
    ("u8", '<svg width="60" height="20"><a id="u8" href="/8"><switch><g/>'
     '<g role="form" aria-labelledby="nope"><text>P9</text></g></switch></a>'
     "</svg>", True),
    ("u9", '<svg width="60" height="20"><a id="u9" href="/9"><rect '
     'width="9" height="9"/></a></svg>', True),
)


@unittest.skipUnless(HAVE_BROWSER, _WHY)
class TestNamesCaptureR6Round7(unittest.TestCase):
    """R6M-1, R6M-3, R6M-6, rendered: a hidden aria-labelledby target read
    whole, what a rendered one skips unread; content made visible again
    read past a part whose role is group; region and form as named; a
    script's lowercase requiredextensions, no condition, read from the
    capture (each measured in Chromium 141)."""

    SCRIPT = ('<div aria-hidden="true"><svg width="40" height="20"><a id="h9" '
              'href="/z"><text y="15">w</text></a></svg></div><script>for '
              '(const i of ["u9", "h9"]) document.getElementById(i).'
              'setAttribute("requiredextensions", "http://example.com/x");'
              "</script>")

    def test_names(self):
        site = _echo_site(self, lambda t: PAGE.format(
            "".join(m for _i, m, _f in _R7_RENDERED) + self.SCRIPT))
        d = tmpdir(self)
        code, _out, err = run("--url", f"{site.base}/p", "--json",
                              d / "r.json", "--fail-on", "never")
        self.assertEqual(code, 0, err)
        report = json.loads((d / "r.json").read_text())
        found = [f for p in report["pages"] for f in p["findings"]
                 if f["verdict"] == "fail"]
        failed = " ".join(f["snippet"] for f in found
                          if f["rule_id"] == "bb-link-name")
        for i, _markup, fails in _R7_RENDERED:
            with self.subTest(case=i):
                self.assertEqual(f'id="{i}"' in failed, fails)
        self.assertTrue(any(f["rule_id"] == "bb-aria-hidden-focus"
                            for f in found))



# ---------------------------------------------------------------------------
# Round 7, R6N: the rules and claims side
# ---------------------------------------------------------------------------

class TestDisplayLaterR6Round7(unittest.TestCase):
    """R6N-1, R6N-8, R6N-9, R6M-2, R6M-5: a var()'s fallback level with a
    hide, under a condition too, or with a revert that hides, is reviewed
    for focus and read as shown for names; a custom property named with
    escaped hyphens is set; a stylesheet an <?xml-stylesheet?> names is
    one the run does not read (as Chromium 141 computes each)."""

    def test_focus(self):
        for css, body in (
                ("@media (min-width: 640px) { .nav-link { display: var("
                 "--nav-link-display, inline-flex) } } .drawer .nav-link { "
                 "display: none }", '<nav class="drawer"><a class="nav-link" '
                 'href="/pricing">Pricing</a></nav>'),
                ("@media (min-width:1px){.x{visibility:var(--v, visible)}} "
                 ".h{visibility:hidden}", '<a class="x h" href="#a">a</a>'),
                (".x{visibility:var(--v, visible)} .h{visibility:hidden}",
                 '<a class="x h" href="#a">a</a>'),
                (".x{display:var(--d, block)} dialog.y{display:revert}",
                 '<dialog class="x y"><a href="#a">x</a></dialog>'),
                (".x{visibility:var(--v, visible)} mphantom.y{visibility:"
                 'revert}', '<math><mphantom class="x y"><mtext><a href="#a">'
                 "x</a></mtext></mphantom></math>"),
                (":root{\\2d -d:none} .x{display:var(--d, inline)}",
                 '<a class="x" href="#a">a</a>'),
                (":root{-\\-d:none} .x{display:var(--d, inline)}",
                 '<a class="x" href="#a">a</a>')):
            with self.subTest(css=css):
                got = TestRulesRound2.found(page(
                    f'<div aria-hidden="true">{body}</div>',
                    head=f"<style>{css}</style>"), "bb-aria-hidden-focus")[1]
                self.assertEqual([v for v, _impact in got], [NEEDS_REVIEW])

    def test_names(self):
        """R6M-2: a later rule's var() fallback shows the text."""
        got = TestRulesRound2.found(page(
            '<a href="/x"><span class="p"><span class="a b">Home</span>'
            "</span></a>", head="<style>.p{visibility:hidden} .a{visibility:"
            "hidden} .b{visibility:var(--v, visible)}</style>"),
            "bb-link-name")[1]
        self.assertEqual(got, [])

    def test_xml_stylesheet(self):
        """R6M-5: what the linked sheet sets is not known, so a review."""
        xhtml = ('<?xml version="1.0" encoding="UTF-8"?>\n<?xml-stylesheet '
                 'type="text/css" href="xs.css"?>\n<html xmlns="http://www.w3'
                 '.org/1999/xhtml" lang="en" xml:lang="en"><head><title>T'
                 "</title><style>.x{display:var(--d, inline)}</style></head>"
                 '<body><main><h1>x</h1><div aria-hidden="true"><a class="x" '
                 'href="/x">a</a></div></main></body></html>')
        got = TestRulesRound2.found(xhtml, "bb-aria-hidden-focus",
                                    path="t.xhtml")[1]
        self.assertEqual([v for v, _impact in got], [NEEDS_REVIEW])
        plain = xhtml.replace('<?xml-stylesheet type="text/css" href="xs.css"'
                              "?>\n", "")
        got = TestRulesRound2.found(plain, "bb-aria-hidden-focus",
                                    path="t.xhtml")[1]
        self.assertEqual([v for v, _impact in got], [FAIL])


#: Rules that stand only where the @namespace before them does: where
#: what stands before it is dropped (R6J-6).
_NS_TAIL = ("@namespace svg url(http://www.w3.org/2000/svg); "
            ".lbl, svg|a{display:none}")


class TestOwnStyleR6Round7(unittest.TestCase):
    """R6N-2 to R6N-7, R6N-10 to R6N-12: a page's own rules as Chromium 141
    reads them, each case measured there: (css, the link's text
    hidden)."""

    #: `.lbl, X{display:none}`: the rule stands where Chromium takes X.
    SELECTORS = (
        (":nth-child(2n of :nth-child(2n of ::before))", True),
        (":nth-child(2n of :nth-last-child(2n of ::after), .b)", True),
        (":nth-child(2n of .a:nth-child(2n of ::before))", True),
        (".p :nth-child(2n of :nth-child(odd of ::before)) .q", True),
        (":nth-child(2n of :not(::before))", False),
        ("::file-selector-button:not(:hover)", True),
        ("::file-selector-button:not(:hover, :focus)", True),
        ("::-webkit-scrollbar-thumb:not(:hover)", True),
        ("::-webkit-scrollbar-button:not(:horizontal)", True),
        ("::selection:not(:window-inactive)", True),
        ("::view-transition-group(*):not(:only-child)", True),
        ("::scroll-marker:not(:target-current)", True),
        ("::cue:not(:hover)", True),
        ("::-webkit-search-cancel-button:not(:hover)", True),
        ("::before:not(:is(:hover))", True),
        ("::file-selector-button:not(:hover):hover", True),
        ("::file-selector-button:not(:not(:hover))", True),
        ("::selection:not(:where(.a))", True),
        ("::scroll-button(up):not(:disabled)", True),
        ("::-webkit-slider-thumb:not(:active, :focus)", True),
        ("::part(x):not(:-webkit-any(:hover))", False),
        ("::part(x):-webkit-any(:hover)", False),
        ("::before:not(:hover)", False), ("::placeholder:not(:hover)", False),
        ("::slotted(x):not(:hover)", False), ("::column:not(:hover)", False),
        ("::highlight(x):not(:hover)", False),
        ("::file-selector-button:not(.a)", False),
        ("::selection:not(:hover)", False), ("::cue(x):not(:hover)", False),
        ("::view-transition:not(:only-child)", False),
        ("::view-transition-old(initial)", False),
        ("::view-transition-old(default)", False),
        ("::view-transition-old(INITIAL)", False),
        ("::view-transition-old(\\69 nitial)", False),
        ("::view-transition-old(*.initial)", False),
        ("::view-transition-old(x.revert-layer)", False),
        ("::view-transition-group(unset)", False),
        ("::view-transition-old(none)", True),
        ("::view-transition-old(auto)", True),
        ("::view-transition-old(none.a)", True),
        (":not/**/(.a)", False), (":nth-child/**/(2n)", False),
        (":nth-child(2n OF .a)", False), (":nth-last-child(2n Of .a)", False),
        (":nth-child(ODD)", True), (":nth-child(EVEN of .a)", True))
    #: Stylesheets: (css, the link's text hidden).
    SHEETS = tuple(
        (f"@font-feature-values {f} {{}} " + _NS_TAIL, hidden)
        for f, hidden in (
            ("default x", False), ("inherit x", False),
            ("revert-layer x", False), ("x, default y", False),
            ("x serif", False), ("inherit", True), ("INHERIT", True),
            ("x, \\64 efault", True), ("x, serif y", True),
            ("x, inherit", True))) + tuple(
        (f"@function --f() returns {t} {{}} " + _NS_TAIL, hidden)
        for t, hidden in (
            ("auto#", False), ("AUTO#", False), ("foo#", False),
            ("<length>/**/#", False), ("<\\6c ength>", False),
            ("<transform-list>", False), ("type(<length> | <color>)", False),
            ("type( <length> )", False), ("type(*)", False),
            ("type(<length>#)", False), ("<length> #", True),
            ("< length>", True), ("<LENGTH>", True),
            ("<transform-list>#", True), ("type()", True),
            ("type(<foo>)", True), ("type(garbage here)", True),
            ("type(<transform-list>#)", True), ('type("<length>")', True),
            ("Initial", True), ("default", True), ("revert-layer", True),
            ("<length>+#", True), ("*", True))) + (
        ("@scope (.a) to/**/(.b) {} " + _NS_TAIL, False),
        (".lbl{display:none} @container none (width > 1px){.lbl{display:"
         "inline}}", True),
        (".lbl{display:none} @container x y (width > 1px){.lbl{display:"
         "inline}}", True),
        (".lbl{display:none} @container Initial (width > 1px){.lbl{display:"
         "inline}}", True))

    def test_selectors(self):
        for selector, valid in self.SELECTORS:
            css = f".lbl, {selector}{{display:none}}"
            with self.subTest(css=css):
                self.assertEqual(link_fails(css), valid)

    def test_sheets(self):
        for css, hidden in self.SHEETS:
            with self.subTest(css=css):
                self.assertEqual(link_fails(css), hidden)

    def test_container_blocks(self):
        """An @container is one of the README's eight blocks (R6N-2)."""
        for depth, read in ((6, True), (7, False)):
            css = ("".join(f"@layer l{k}{{" for k in range(depth))
                   + "@container (width > 1px){.x{display:block}}"
                   + "}" * depth)
            with self.subTest(depth=depth):
                self.assertEqual(bool(ST.style_rules(css)), read)

    def test_commented_nth_quick(self):
        """R6N-10: a comment in An+B costs its selector's length."""
        css = (".x" + "\\:" * 250
               + ":nth-child(2n/**/of .a){display:none}") * 2000
        start = time.monotonic()
        ST.style_rules(css)
        self.assertLess(time.monotonic() - start, 3)



# ---------------------------------------------------------------------------
# Round 8, R6O: drawings, names and focus
# ---------------------------------------------------------------------------

_P = '<path d="M0 0h5v5z"/>'
#: A file run's bb-link-name, each measured in Chromium 141 (R6O-2,
#: R6O-3, R6O-4): (body, it FAILs, or how many FAILs).
_R8_NAMES = (
    # R6O-2: through aria-labelledby, a drawing's <desc>'s own text, where
    # no part whose role is group stands between it and the target
    (_lb(f'{_SVL}<desc>D1</desc>{_P}</svg>'), False),
    (_lb(f'{_SV}<g id="L"><desc>D2</desc>{_P}</g></svg>'), False),
    (_lb(f'<span id="L">{_SV}<desc>D3</desc>{_P}</svg></span>'), False),
    (_lb(f'<span id="L" aria-hidden="true">{_SV}<desc>D4</desc></svg></span>'),
     False),
    (_lb(f'<span id="L">{_SV}<g><desc>D5</desc>{_P}</g></svg></span>'), True),
    (_lb(f'{_SVL}<g><desc>D6</desc>{_P}</g></svg>'), True),
    (_lb(f'{_SVL}<svg><desc>D13</desc></svg></svg>'), True),
    (_lb(f'{_SVL}<desc><b>D24</b></desc></svg>'), True),
    (_lb(f'{_SVL}<desc>T4<b>B4</b></desc></svg>'), False),
    (_lb(f'{_SVL}<desc aria-hidden="true">D5</desc></svg>'), False),
    # (the drawing's link /y is unnamed in Chromium too: one FAIL)
    (_lb(f'<span id="L">{_SV}<a href="/y"><desc>D9</desc>{_P}</a></svg>'
         "</span>"), 1),
    (_lb(f'<div hidden><span id="L">{_SV}<g><desc>D22</desc></g></svg>'
         "</span></div>"), True),
    (_lb(f'<div hidden>{_SV}<g id="L"><desc>D16</desc>{_P}</g></svg></div>'),
     False),
    (f'<a href="/x">{_SV}<desc>D28</desc>{_P}</svg></a>', True),
    (f'{_SV}<a href="/x"><desc>D29</desc>{_P}</a></svg>', True),
    # R6O-3: a <g> in an <a> in a <text> is none of its parts
    (f'{_SV}<text y="15"><a href="/q2"><g>N2</g></a></text></svg>', True),
    # R6O-4: an <svg> given a role named from its content, by its content
    ('<a href="/x"><svg role="link" width="20" height="20"><text y="15">'
     "LK30</text></svg></a>", False),
    ('<a href="/x"><svg role="heading" aria-level="2" width="20" height="20">'
     '<text y="15">HD32</text></svg></a>', False),
    ('<a href="/x"><svg role="graphics-symbol" width="20" height="20"><text '
     'y="15">GS34</text></svg></a>', True),
    ('<a href="/x"><svg role="row" width="20" height="20"><text y="15">RW47'
     "</text></svg></a>", True),
    ('<a href="/x"><svg role="link" width="20" height="20"><title>TL42'
     '</title><text y="15">LK42</text></svg></a>', False),
)


class TestNamesR6Round8(unittest.TestCase):
    """R6O-1 to R6O-4: a drawing's <desc> through aria-labelledby, a <g>
    in an <a> in a <text>, an <svg> named from its content by its role (as
    Chromium 141 names each); a deep page's labels read in time."""

    def test_names(self):
        for body, fails in _R8_NAMES:
            with self.subTest(body=body):
                got = TestRulesRound2.found(page(body), "bb-link-name")[1]
                self.assertEqual([v for v, _i in got], [FAIL] * int(fails))

    def test_buttons(self):
        for body, fails in (
                ('<button aria-labelledby="L"></button>' + _SVL
                 + f"<desc>Delete item</desc>{_P}</svg>", False),
                (f"<button>{_SV}<desc>D</desc></svg></button>", True),
                ('<button><svg role="presentation" width="20" height="20">'
                 "<desc>D15</desc></svg></button>", True)):
            with self.subTest(body=body):
                got = TestRulesRound2.found(page(body), "bb-button-name")[1]
                self.assertEqual([v for v, _i in got],
                                 [FAIL] if fails else [])

    def test_deep_label_quick(self):
        """R6O-1: a target 400 deep, among 300 rules with `*` at the
        right, is read without walking its ancestors (nothing in it is
        hidden)."""
        css = "".join(f"[data-a{i}] *{{visibility:visible}}"
                      for i in range(300))
        html = page("<div>" * 400 + '<span id="t1">L</span>' + "</div>" * 400
                    + '<button aria-labelledby="t1"></button>',
                    head=f"<style>{css}</style>")
        start = time.monotonic()
        got = TestRulesRound2.found(html, "bb-button-name")[1]
        self.assertLess(time.monotonic() - start, 10)
        self.assertEqual(got, [])


# ---------------------------------------------------------------------------
# Round 8, R6P: the rules and claims side
# ---------------------------------------------------------------------------

class TestDisplayLaterR6Round8(unittest.TestCase):
    """R6P-1, R6P-2: custom properties found in time on hostile text; a
    visibility var() whose fallback leaves it to the parent, level with
    a hide, is reviewed (as Chromium 141 computes it hidden)."""

    def test_focus(self):
        for css in (".menu{visibility:var(--menu-visibility)} "
                    ".menu.closed{visibility:hidden}",
                    ".menu{visibility:var(--v, inherit)} "
                    ".menu.closed{visibility:hidden}"):
            with self.subTest(css=css):
                got = TestRulesRound2.found(page(
                    '<div aria-hidden="true"><div class="menu closed"><a '
                    'href="/a">A</a></div></div>',
                    head=f"<style>{css}</style>"), "bb-aria-hidden-focus")[1]
                self.assertEqual([v for v, _impact in got], [NEEDS_REVIEW])

    def test_custom_properties_quick(self):
        for text in (".a::after{content:\"" + "\u2605" * 40000 + "\"}",
                     "\\2605 " * 20000):
            with self.subTest(size=len(text)):
                start = time.monotonic()
                ST.custom_properties([text])
                self.assertLess(time.monotonic() - start, 3)
        self.assertEqual(sorted(ST.custom_properties(
            [":root{\\2d -d:none; -\\-e: 1; --f/**/: 2} .x{color:red}"])),
            ["--d", "--e", "--f"])


class TestOwnStyleR6Round8(unittest.TestCase):
    """R6P-3 to R6P-6: a "(" that opens no function, combinators in a
    :not() after a pseudo-element, ::view-transition-group-children()'s
    followers, comments in An+B, each measured in Chromium 141: (css,
    the link's text hidden)."""

    SELECTORS = (
        (".nav:not(.x) (li)", False), (":hover (.a)", False),
        (":is(.a) (.b)", False), (":host/**/(.a)", False),
        (":hover/**/(.a)", False), (".a (b)", False),
        (":is(.a (b), .lbl)", True),
        ("::file-selector-button:not(:hover > :focus)", True),
        ("::file-selector-button:not(:hover :focus)", True),
        ("::file-selector-button:not(:hover + :focus)", True),
        ("::part(x):not(:hover :focus)", True),
        ("::-webkit-scrollbar:not(:hover > :active)", True),
        ("::file-selector-button:not(:not(:hover > :focus))", True),
        ("::file-selector-button:not(> :hover)", False),
        ("::file-selector-button:not(:hover > .a)", False),
        ("::part(x):not(:hover > div)", False),
        ("::view-transition-group-children(*):only-child", True),
        ("::view-transition-group-children(x):not(:only-child)", True),
        ("::view-transition-group-children(x):hover", False),
        (":nth-child(2n/**/+/**/1/**/of .a)", True),
        (":nth-child(/**/2n/**/of .a)", True),
        (":nth-child(2n/**/-/**/1/**/of .a)", True),
        (":nth-child(+/**/n/**/of .a)", True),
        (":nth-child(-/**/n/**/of .a)", False),
        (":nth-child(2/**/n/**/of .a)", False))

    def test_selectors(self):
        for selector, valid in self.SELECTORS:
            css = f".lbl, {selector}{{display:none}}"
            with self.subTest(css=css):
                self.assertEqual(link_fails(css), valid)


# ---------------------------------------------------------------------------
# Round 9: names Chromium 141 does not read (L92, L115); an <iframe>'s
# fallback text
# ---------------------------------------------------------------------------

_RV, _MI, _MO = NEEDS_REVIEW, "minor", "moderate"
_TD2 = "<tr><td>Save</td><td>B</td></tr><tr><td>C</td><td>D</td></tr>"
_SV8 = '<svg width="80" height="20"><a href="/x">'
#: bb-link-name, each measured in Chromium 141 and axe-core 4.12 (L92,
#: L115): (what the link holds, its findings). Where the accessible-name
#: computation names the link and Chromium does not, a review: minor
#: where axe-core names it too, moderate where it does not (MathML, an
#: <object>'s fallback).
_R9_LINKS = (
    ("<article><h3>T</h3><p>Excerpt</p></article>", [(_RV, _MI)]),
    ('<figure><img alt="Map" src="m.png"></figure>', [(_RV, _MI)]),
    ("<figure><figcaption>Fc</figcaption>Save</figure>", [(_RV, _MI)]),
    ('<figure aria-label="Fl">Save</figure>', []),
    ("<header>Save</header>", [(_RV, _MI)]),
    ("<footer>Save</footer>", []),
    ("<aside>Save</aside>", [(_RV, _MI)]),
    ("<nav>Save</nav>", [(_RV, _MI)]),
    ("<blockquote>Save</blockquote>", [(_RV, _MI)]),
    ("<dialog open>Save</dialog>", [(_RV, _MI)]),
    ("<address>Save</address>", [(_RV, _MI)]),
    ("<section>Save</section>", []),
    ('<section title="">Save</section>', []),
    ("<form>Save</form>", []),
    ('<form title="">Save</form>', [(_RV, _MI)]),
    ('<form title="Ft">Save</form>', []),
    ("<details open><summary>Sm</summary>Save</details>", []),
    ('<details role="group" open><summary>Sm</summary>Save</details>',
     [(_RV, _MI)]),
    ("<fieldset>Save</fieldset>", [(_RV, _MI)]),
    ("<fieldset>Save<legend>Lg</legend></fieldset>", []),
    ("<fieldset><legend></legend><legend>L2</legend>Save</fieldset>",
     [(_RV, _MI)]),
    ('<fieldset title="Ti"><legend></legend>Save</fieldset>', []),
    ("<output>Save</output>", [(_RV, _MI)]),
    ('<output id="o9">Save</output><label for="o9">Ol</label>', []),
    ("<marquee>Save</marquee>", []),
    ('<span role="img">\u2605\u2605</span>', [(_RV, _MI)]),
    ('<span role="img" aria-label="">\u2605</span>', [(_RV, _MI)]),
    ('<span role="img" title="Ti">\u2605</span>', []),
    ('<span role="group" tabindex="0">Save</span>', [(_RV, _MI)]),
    ('<span role="group"><span role="group" aria-label="G2">x</span></span>',
     [(_RV, _MI)]),
    ('<span role="list"><span role="listitem">Save</span></span>', []),
    ('<span role="region">Save</span>', []),
    ('<span role="form" title="">Save</span>', [(_RV, _MI)]),
    # a control's content is read as before, its value unread (L101)
    ('<span role="combobox">Save</span>', []),
    ('<article role="none">Save</article>', []),
    ('<article role="none" tabindex="0">Save</article>', [(_RV, _MI)]),
    ('<div role="card article">Save</div>', [(_RV, _MI)]),
    ('<article role="card">Save</article>', [(_RV, _MI)]),
    ('<article aria-labelledby="Y9"><span id="Y9">Yi</span>Save</article>',
     []),
    ("<article>Save</article>More", []),
    ("<article hidden>Save</article>Txt", []),
    (f"<article {_VH}><span {_VV}>Save</span></article>", []),
    ('<article style="display:contents">Save</article>', [(_RV, _MI)]),
    # a <table>: of data by its markup, else of layout
    ("<table><tr><td>Save</td></tr></table>", []),
    ("<table><tr><th>Save</th></tr></table>", []),
    ("<table><tr><th>H</th></tr><tr><td>Save</td></tr></table>",
     [(_RV, _MI)]),
    ("<table><caption>Cp</caption><tr><td>Save</td></tr></table>", []),
    ('<table summary="S"><tr><th>H</th></tr><tr><td>Save</td></tr>'
     "</table>", []),
    (f"<table><thead><tr><td>Save</td></tr></thead>{_TD2}</table>",
     [(_RV, _MI)]),
    (f"<table><colgroup></colgroup>{_TD2}</table>", [(_RV, _MI)]),
    (f'<table border="0">{_TD2}</table>', []),
    (f'<table border="0px">{_TD2}</table>', []),
    # a border, which a style may undo, is left to styles (R6Q-2, L121)
    (f'<table border="abc">{_TD2}</table>', []),
    (f'<table border="-1">{_TD2}</table>', []),
    ('<table border="1"><tr><td>Save</td></tr></table>', []),
    (f'<table rules="">{_TD2}</table>', []),
    (f'<table rules="all">{_TD2}</table>', [(_RV, _MI)]),
    ('<table><tr><td scope="row">Save</td><td>B</td></tr><tr><td>C</td>'
     "<td>D</td></tr></table>", [(_RV, _MI)]),
    ('<table><tr><td scope="">Save</td><td>B</td></tr><tr><td>C</td>'
     "<td>D</td></tr></table>", []),
    ("<table>" + "<tr><td>Save</td><td>B</td></tr>" * 20 + "</table>",
     [(_RV, _MI)]),
    ("<table>" + "<tr><td>Save</td><td>B</td></tr>" * 19 + "</table>", []),
    (f'<table role="presentation">{_TD2}</table>', []),
    ('<table><tr role="row"><td>Save</td><td>B</td></tr></table>',
     [(_RV, _MI)]),
    # MathML and an <object>: axe-core reads neither
    ("<math><mi>x</mi></math>", [(_RV, _MO)]),
    ('<math alttext="At"><mi>x</mi></math>', [(_RV, _MO)]),
    ('<math role="none"><mi>x</mi></math>', [(_RV, _MO)]),
    ('<math title="Ti"><mi>x</mi></math>', []),
    ('<math aria-label="Al"><mi>x</mi></math>', []),
    ("Save <math><mi>x</mi></math>", []),
    ('<span role="math">x</span>', []),
    ('<object width="20" height="20">Save</object>', [(_RV, _MO)]),
    ('<object title="Ti" width="20" height="20">Save</object>', []),
    # an <iframe>'s fallback text names nothing
    ("<iframe>Save</iframe>", [(FAIL, "blocker")]),
    ('<iframe title="If">Save</iframe>', []),
)
#: The same, a drawing's link: (what its <a href> holds, its findings).
_R9_DRAWN = (
    ('<g tabindex="0"><text y="15">Save</text></g>', [(_RV, _MI)]),
    ('<g aria-hidden="false"><text y="15">Save</text></g>', [(_RV, _MI)]),
    ('<g><desc>D</desc><text y="15">Save</text></g>', [(_RV, _MI)]),
    ('<g aria-label="Al"><text y="15">Save</text></g>', []),
    ('<g><title>Gt</title><text y="15">Save</text></g>', []),
    ('<g class="c" focusable="true"><text y="15">Save</text></g>', []),
    ('<g role="list"><text y="15">Save</text></g>', []),
    ('<g role="group"><text y="15">Save</text></g>', [(_RV, _MI)]),
    ('<text role="img" y="15">Save</text>', [(_RV, _MI)]),
    ('<a aria-label="Al"><text y="15">Save</text></a>', [(_RV, _MI)]),
    ('<text y="15"><a>Save</a></text>', []),
)


class TestNamesR6Round9(unittest.TestCase):
    """L92, L115: a link or a button named only by what an element holds
    that Chromium 141 reads only the own name of (an <article>, a
    <figure>, a <table> of data, role=img, MathML, an <object>) is a
    review; an <iframe>'s fallback text names nothing (each measured)."""

    def test_links(self):
        for inner, want in _R9_LINKS:
            body = f'<a href="/x">{inner}</a>'
            with self.subTest(body=body):
                got = TestRulesRound2.found(page(body), "bb-link-name")[1]
                self.assertEqual(got, want)

    def test_drawn_links(self):
        for inner, want in _R9_DRAWN:
            body = f"{_SV8}{inner}</a></svg>"
            with self.subTest(body=body):
                got = TestRulesRound2.found(page(body), "bb-link-name")[1]
                self.assertEqual(got, want)

    def test_named_otherwise(self):
        """aria-labelledby, aria-label and a title on the link name it,
        whatever it holds."""
        for body in ('<a href="/x" aria-labelledby="L9"></a><span id="L9">'
                     "<article>Save</article></span>",
                     '<a href="/x" aria-label="Go"><article>Save</article>'
                     "</a>",
                     '<a href="/x" title="T"><article>Save</article></a>'):
            with self.subTest(body=body):
                self.assertEqual(
                    TestRulesRound2.found(page(body), "bb-link-name")[1], [])

    def test_buttons(self):
        for body, want in (
                ("<button><figure>Save</figure></button>", [(_RV, _MI)]),
                ('<button><span role="img">\U0001F50D</span></button>',
                 [(_RV, _MI)]),
                ("<button><math><mi>x</mi></math></button>", [(_RV, _MO)]),
                ('<div role="button" tabindex="0"><article>Save</article>'
                 "</div>", [(_RV, _MI)]),
                ('<a href="/x" role="button"><article>Save</article></a>',
                 [(_RV, _MI)]),
                ("<button><fieldset><legend>Lg</legend>Save</fieldset>"
                 "</button>", []),
                ('<button><span role="group" aria-label="G">Save</span>'
                 "</button>", [])):
            with self.subTest(body=body):
                got = TestRulesRound2.found(page(body), "bb-button-name")[1]
                self.assertEqual(got, want)

    def test_messages(self):
        for body, words in (
                ('<a href="/x"><article>Save</article></a>',
                 ("only name is text inside its <article>",
                  "Other checks usually pass it", "Chrome and Edge",
                  "give the link an aria-label")),
                ('<a href="/x"><span role="img">\u2605</span></a>',
                 ('its element with role="img"',)),
                ('<a href="/x"><math><mi>x</mi></math></a>',
                 ("text inside its <math>", "That text is MathML",
                  "or its <math>, an aria-label")),
                ('<a href="/x"><object>Save</object></a>',
                 ("text inside its <object>",)),
                (f"{_SV8}<g tabindex=\"0\"><text>S</text></g></a></svg>",
                 ("its drawing's <g>",))):
            with self.subTest(body=body):
                found = run_page(page(body), "t.html", RB)
                msgs = [f.message for r in found.results
                        if r.rule_id == "bb-link-name" for f in r.findings]
                self.assertEqual(len(msgs), 1)
                for w in words:
                    self.assertIn(w, msgs[0])

    def test_iframe_fallback(self):
        """What an <iframe> holds names it nothing, as in Chromium 141 and
        axe-core 4.12's frame-title (measured)."""
        for body, want in (
                ('<iframe src="about:blank">Your browser does not support '
                 "iframes.</iframe>", [FAIL]),
                ('<iframe src="about:blank"><p>Fallback</p></iframe>', [FAIL]),
                ('<iframe src="about:blank" title="Map">Fallback</iframe>',
                 [])):
            with self.subTest(body=body):
                got = TestRulesRound2.found(page(body), "bb-iframe-title")[1]
                self.assertEqual([v for v, _i in got], want)

    def test_deep_quick(self):
        """A link that holds 3,000 nested <article>s, or 3,000 of them in a
        row, is read in time."""
        for inner in ("<article>" * 3000 + "Save" + "</article>" * 3000,
                      "<article>Save</article>" * 3000):
            html = page(f'<a href="/x">{inner}</a>')
            start = time.monotonic()
            got = TestRulesRound2.found(html, "bb-link-name")[1]
            self.assertLess(time.monotonic() - start, 20)
            self.assertEqual(got, [(_RV, _MI)])


# ---------------------------------------------------------------------------
# Round 10, R6Q: names Chromium 141 does not read, and what axe-core reads
# ---------------------------------------------------------------------------

#: bb-link-name, each measured in Chromium 141 and axe-core 4.12 (R6Q-1,
#: R6Q-2, R6Q-5, R6Q-6): (what the link holds, its findings).
_R10_LINKS = (
    # R6Q-1: minor where axe-core reads the name, moderate where it does not
    ("<figure><math><mi>x</mi></math></figure>", [(_RV, _MO)]),
    ("<figure><canvas>Chart</canvas></figure>", [(_RV, _MO)]),
    ('<figure><object data="nope.svg">Chart</object></figure>', [(_RV, _MO)]),
    ('<math><mi>x</mi></math><span role="img">\u2605</span>', [(_RV, _MI)]),
    ('<svg role="heading" width="20" height="20"><g tabindex="0"><text '
     'y="15">C</text></g></svg>', [(_RV, _MO)]),
    ("<figure><svg><title>St</title></svg></figure>", [(_RV, _MI)]),
    ('<figure><img alt="Im" src="data:,"></figure>', [(_RV, _MI)]),
    # R6Q-2: a border or a bgcolor, which a style may undo, is not read
    (f'<table border="1">{_TD2}</table>', []),
    ('<table><tr><td bgcolor="#eeeeee">Save</td><td bgcolor="#eeeeee">B</td>'
     "</tr><tr><td>C</td><td>D</td></tr></table>", []),
    # R6Q-6: a hidden <caption> names nothing
    (f"<table><caption hidden>Cp</caption>{_TD2}</table>", [(_RV, _MI)]),
    (f"<table><caption {_VH}>Cp</caption>{_TD2}</table>", [(_RV, _MI)]),
    # R6Q-5: no title of a <span>, a <div>, an <i> and the like is read
    ('<i class="fa fa-home" title="T"></i>', [(_RV, _MI)]),
    ('<span title="T"></span>', [(_RV, _MI)]),
    ('<div title="T"></div>', [(_RV, _MI)]),
    ('<p title="T"></p>', [(_RV, _MI)]),
    ('<span role="paragraph" title="T"></span>', [(_RV, _MI)]),
    ('<span title="T"><i aria-hidden="true">x</i></span>', [(_RV, _MI)]),
    ('<div title="T"><article>Save</article></div>', [(_RV, _MI)]),
    ('<abbr title="T"></abbr>', []),
    ('<label title="T"></label>', []),
    ('<h2 title="T"></h2>', []),
    ('<span role="button" title="T"></span>', []),
    ('<x-icon title="T"></x-icon>', []),
    ('<img title="T" src="data:,">', []),
    ('<span title="T">Save</span>', []),
)
#: The same, a drawing's link (R6Q-4): (what its <a href> holds, findings).
_R10_DRAWN = (
    ('<g aria-expanded="false"><text y="15">Save</text></g>', [(_RV, _MI)]),
    ('<g aria-foo="x"><text y="15">Save</text></g>', [(_RV, _MI)]),
    ('<g onmousedown="void 0"><text y="15">Save</text></g>', [(_RV, _MI)]),
    ('<g lang="en"><text y="15">Save</text></g>', [(_RV, _MI)]),
    ('<g><title></title><text y="15">Save</text></g>', [(_RV, _MI)]),
    ('<g onkeydown="void 0"><text y="15">Save</text></g>', []),
    ('<g xml:lang="en"><text y="15">Save</text></g>', []),
    ('<g id="g10"><text y="15">Save</text></g>', []),
    ('<g role="foo"><text y="15">Save</text></g>', []),
)
#: bb-button-name (R6Q-6, R6Q-7): (body, its findings).
_R10_BUTTONS = (
    ('<label for="b10"><figure>Save</figure></label><button id="b10">'
     "</button>", [(_RV, _MI)]),
    ('<label for="b10"><span role="img">\u2605</span></label><button '
     'id="b10"></button>', [(_RV, _MI)]),
    ('<label for="b10"><math><mi>x</mi></math></label><button id="b10">'
     "</button>", [(_RV, _MO)]),
    ('<label for="b10"><span title="T"></span></label><button id="b10">'
     "</button>", [(_RV, _MI)]),
    ('<label for="b10">Save</label><button id="b10"></button>', []),
    ("<label><figure>Save</figure><button></button></label>", [(_RV, _MI)]),
    ('<button><fieldset><legend style="display:none">Lg</legend>Save'
     "</fieldset></button>", [(_RV, _MI)]),
    ('<button><fieldset><legend aria-hidden="true">Lg</legend>Save'
     "</fieldset></button>", [(_RV, _MI)]),
    ("<button><fieldset><legend hidden>Lg</legend>Save</fieldset></button>",
     [(_RV, _MI)]),
    (f"<button><fieldset><legend {_VH}>Lg</legend>Save</fieldset></button>",
     [(_RV, _MI)]),
    ('<button><fieldset><legend style="position:absolute;width:1px;'
     'height:1px;overflow:hidden;clip:rect(0 0 0 0)">Lg</legend>Save'
     "</fieldset></button>", []),
    ('<button><i class="fa" title="T"></i></button>', [(_RV, _MI)]),
)
_HSV = '<div hidden><span id="Lx"><svg width="20" height="20">'
#: An aria-labelledby target's stray <tspan>, a <g> in an <a> in a <text>
#: (R6Q-3, R6Q-8): (the target, the button FAILs).
_R10_LABELLED = (
    (f"{_HSV}<tspan>Stray</tspan></svg></span></div>", False),
    (f"{_HSV}<rect><tspan>Stray</tspan></rect></svg></span></div>", False),
    (f"{_HSV}<switch><tspan>Stray</tspan></switch></svg></span></div>",
     False),
    (f"{_HSV}<defs><tspan>Stray</tspan></defs></svg></span></div>", False),
    (f"{_HSV}<textPath>Stray</textPath></svg></span></div>", False),
    ('<span id="Lx" aria-hidden="true"><svg width="20" height="20"><tspan>'
     "Stray</tspan></svg></span>", False),
    (f'<span id="Lx" {_VH}><svg width="20" height="20"><tspan>Stray</tspan>'
     "</svg></span>", False),
    ('<span id="Lx"><svg width="20" height="20"><tspan>Stray</tspan></svg>'
     "</span>", True),
    ('<div hidden><svg id="Lx" width="20" height="20"><tspan>Stray</tspan>'
     "</svg></div>", False),
    (f'{_HSV}<text y="15"><a href="/q"><g>Gina</g></a></text></svg></span>'
     "</div>", True),
)


class TestNamesR6Round10(unittest.TestCase):
    """R6Q-1 to R6Q-10: the review's impact by what axe-core reads; a
    table's border and bgcolor left to styles; no title of a <span>, a
    <div>, an <i> and the like; a hidden <legend> or <caption>; a label's
    content; the <g>s Chromium keeps; a stray <tspan> in a hidden target;
    each measured in Chromium 141 and axe-core 4.12."""

    def test_links(self):
        for inner, want in _R10_LINKS:
            body = f'<a href="/x">{inner}</a>'
            with self.subTest(body=body):
                got = TestRulesRound2.found(page(body), "bb-link-name")[1]
                self.assertEqual(got, want)

    def test_drawn_links(self):
        for inner, want in _R10_DRAWN:
            body = f"{_SV8}{inner}</a></svg>"
            with self.subTest(body=body):
                got = TestRulesRound2.found(page(body), "bb-link-name")[1]
                self.assertEqual(got, want)

    def test_buttons(self):
        for body, want in _R10_BUTTONS:
            with self.subTest(body=body):
                got = TestRulesRound2.found(page(body), "bb-button-name")[1]
                self.assertEqual(got, want)

    def test_labelled(self):
        for target, fails in _R10_LABELLED:
            body = '<button aria-labelledby="Lx"></button>' + target
            with self.subTest(body=body):
                got = TestRulesRound2.found(page(body), "bb-button-name")[1]
                self.assertEqual([v for v, _i in got], [FAIL] if fails else [])

    def test_messages(self):
        for body, words in (
                ('<a href="/x"><i class="fa" title="Home"></i></a>',
                 ("only name is the title of its <i>",
                  "read no title of such an element",
                  "Other checks usually pass it")),
                ('<a href="/x"><figure><math><mi>x</mi></math></figure></a>',
                 ("text inside its <figure>", "That text is MathML",
                  "axe-core 4.12 does not read")),
                ('<label for="b10"><figure>Save</figure></label><button '
                 'id="b10"></button>', ("a <figure> in its <label>",)),
                ('<a href="/x"><object>Save</object></a>',
                 ("text inside its <object>",))):
            with self.subTest(body=body):
                found = run_page(page(body), "t.html", RB)
                msgs = [f.message for r in found.results
                        if r.rule_id in ("bb-link-name", "bb-button-name")
                        for f in r.findings]
                self.assertEqual(len(msgs), 1)
                for w in words:
                    self.assertIn(w, msgs[0])
        rules = (ROOT / "src" / "bellbriar_harness" / "rulebook.json"
                 ).read_text(encoding="utf-8")
        self.assertNotIn("a <object>", rules)

    def test_nested_quick(self):
        """R6Q-9: 300 nested role=link elements are read once each."""
        html = page('<span role="link" tabindex="0">' * 300 + "Save"
                    + "</span>" * 300)
        start = time.monotonic()
        TestRulesRound2.found(html, "bb-link-name")
        self.assertLess(time.monotonic() - start, 20)


@unittest.skipUnless(HAVE_BROWSER, _WHY)
class TestNamesCaptureR6Round10(unittest.TestCase):
    """R6Q-3, R6Q-8 and the reviews, rendered: a <g> in an <a> in a <text>
    in a hidden target names nothing, a stray <tspan> there does; a card
    link and a titled icon are reviewed (each measured in Chromium 141)."""

    def test_names(self):
        body = ('<button id="c1" aria-labelledby="c1l"></button>'
                + _R10_LABELLED[-1][0].replace('"Lx"', '"c1l"')
                + '<button id="c2" aria-labelledby="c2l"></button>'
                + _R10_LABELLED[0][0].replace('"Lx"', '"c2l"')
                + '<a id="c3" href="/x"><article>Save</article></a>'
                + '<a id="c4" href="/y"><i title="Home"></i></a>')
        site = _echo_site(self, lambda t: PAGE.format(body))
        d = tmpdir(self)
        code, _out, err = run("--url", f"{site.base}/p", "--json",
                              d / "r.json", "--fail-on", "never")
        self.assertEqual(code, 0, err)
        report = json.loads((d / "r.json").read_text())
        got = sorted((f["rule_id"], f["verdict"], f["impact"], i)
                     for p in report["pages"] for f in p["findings"]
                     if f["rule_id"] in ("bb-link-name", "bb-button-name")
                     for i in ("c1", "c2", "c3", "c4")
                     if f'id="{i}"' in f["snippet"])
        self.assertEqual(got, [
            ("bb-button-name", "fail", "blocker", "c1"),
            ("bb-link-name", "needs_review", "minor", "c3"),
            ("bb-link-name", "needs_review", "minor", "c4")])


# ---------------------------------------------------------------------------
# Round 10, R6R: the rules and claims side
# ---------------------------------------------------------------------------

class TestOwnStyleR6Round10(unittest.TestCase):
    """R6R-1 to R6R-4: a var()'s fallback revert level with a show; a ")"
    that closes nothing and a "]" outside an attribute selector; a comment
    between a "+" and a digit in An+B (each measured in Chromium 141)."""

    SELECTORS = (
        (".lbl{display:none} .lbl:hover), .lbl{display:inline}", True),
        (".lbl, li:not(:last-child)) {display:none}", False),
        (".lbl, :hover]{display:none}", False),
        (".lbl, :is(.q) ]{display:none}", False),
        (".lbl, :is(.q, ]){display:none}", True),
        (".lbl, :where(], .q){display:none}", True),
        (".lbl, :is(.q)){display:none}", False),
        (".lbl, .a){display:none}", False),
        (".lbl, .a]{display:none}", False),
        ('.lbl, [x="a]"]{display:none}', True),
        (".lbl, .a\\]{display:none}", True),
        (".lbl, :nth-child(+/**/1){display:none}", False),
        (".lbl, :nth-child(+/**/2n){display:none}", False),
        (".lbl, :nth-of-type(+/**/2){display:none}", False),
        (".lbl, :nth-child(+/**/n){display:none}", True),
        (".lbl, :nth-child(2n+/**/1){display:none}", True),
        (".lbl, :nth-child(-n+/**/3){display:none}", True),
        (".lbl, :is(.x, :nth-child(+/**/1)){display:none}", True))

    def test_selectors(self):
        for css, hidden in self.SELECTORS:
            with self.subTest(css=css):
                self.assertEqual(link_fails(css), hidden)

    def test_focus(self):
        """R6R-1: a popover or a closed <dialog> a var()'s fallback revert
        hides, level with a var()'s fallback that shows it, is reviewed;
        the message says what the run cannot settle (R6R-4)."""
        for tag in ("div popover", "dialog"):
            html = page(f'<{tag} aria-hidden="true" class="a b"><a href="/a">'
                        f"A</a></{tag.split()[0]}>",
                        head="<style>.a{display:var(--x, block)} "
                             ".b{display:var(--y, revert)}</style>")
            with self.subTest(tag=tag):
                found = run_page(html, "t.html", RB)
                got = [(f.verdict, f.message) for r in found.results
                       if r.rule_id == "bb-aria-hidden-focus"
                       for f in r.findings]
                self.assertEqual([v for v, _m in got], [NEEDS_REVIEW])
                self.assertIn("cannot settle", got[0][1])



# ---------------------------------------------------------------------------
# Round 11, R6S: a button's <label>, the titles Chromium 141 reads, what
# axe-core reads of a title
# ---------------------------------------------------------------------------

_B11 = '<label for="b11"></label><button id="b11"'
#: bb-link-name, each measured in Chromium 141 and axe-core 4.12 (R6S-1,
#: R6S-3, R6S-5): (what the link holds, its findings).
_R11_LINKS = (
    # R6S-3: a title Chromium reads where the element takes focus, is a
    # custom element or, as a <span> or an <i>, draggable; and not
    ('<span tabindex="0" title="T"></span>', []),
    ('<em tabindex="-1" title="T"></em>', []),
    ('<span role="none" tabindex="0" title="T"></span>', []),
    ('<span draggable="true" title="T"></span>', []),
    ('<span draggable="x" title="T"></span>', []),
    ('<i draggable="true" title="T"></i>', []),
    ('<pre draggable="true" title="T"></pre>', []),
    ('<x-icon role="mark" title="T"></x-icon>', []),
    ('<figcaption title="T"></figcaption>', []),
    ('<i role="img" title="T"></i>', []),
    ('<p draggable="true" title="T"></p>', [(_RV, _MI)]),
    ('<em draggable="true" title="T"></em>', [(_RV, _MI)]),
    ('<s draggable="true" title="T"></s>', [(_RV, _MI)]),
    ('<div role="paragraph" draggable="true" title="T"></div>', [(_RV, _MI)]),
    ('<span tabindex="x" title="T"></span>', [(_RV, _MI)]),
    ('<span contenteditable="true" title="T"></span>', [(_RV, _MI)]),
    ('<acronym title="T"></acronym>', [(_RV, _MI)]),
    ('<summary title="T"></summary>', [(_RV, _MI)]),
    ('<br title="T">', [(_RV, _MI)]),
    ('<x-icon role="none" title="T"></x-icon>', [(_RV, _MO)]),
    # R6S-1: axe-core reads no title of an element that holds white space,
    # or whose role is none or presentation
    ('<span title="Cart">\n  </span>', [(_RV, _MO)]),
    ('<span title="H">\n  <svg aria-hidden="true" width="9" height="9">'
     "</svg>\n</span>", [(_RV, _MO)]),
    ('<span title="H"><svg aria-hidden="true" width="9" height="9"></svg>'
     "</span>", [(_RV, _MI)]),
    ('<i role="presentation" title="Close"></i>', [(_RV, _MO)]),
    ('<span title="T"><!-- c --></span>', [(_RV, _MI)]),
    ('<div title="T"><span>\n</span></div>', [(_RV, _MO)]),
    ('<div tabindex="-1" title="T">\n</div>', []),
    # R6S-5: a <table>'s summary only where it has no <caption>
    ('<table summary="Sm"><caption hidden>Cp</caption><tr><th>A</th><th>B'
     "</th></tr></table>", [(_RV, _MI)]),
    ('<table summary="Sm"><caption></caption><tr><th>A</th><th>B</th></tr>'
     "</table>", [(_RV, _MI)]),
    ('<table summary="Sm"><tr><th>A</th><th>B</th></tr></table>', []),
)
#: bb-button-name (R6S-3, R6S-4, R6S-6): (body, its findings).
_R11_BUTTONS = (
    # R6S-4: a button's <label> takes the place of its content, value and
    # title, an empty or a hidden one too, or one that holds it alone
    (f"{_B11}>Save</button>", [(_RV, _MI)]),
    ('<label for="b11"> </label><button id="b11">Save</button>',
     [(_RV, _MI)]),
    ('<label for="b11" hidden>X</label><button id="b11">Save</button>',
     [(_RV, _MI)]),
    ('<label for="b11" style="display:none">X</label><button id="b11">'
     "Save</button>", [(_RV, _MI)]),
    ('<label for="b11" aria-hidden="true">X</label><button id="b11">Save'
     "</button>", [(_RV, _MI)]),
    (f'<label for="b11" {_VH}>X</label><button id="b11">Save</button>',
     [(_RV, _MI)]),
    ('<label for="b11"><span aria-hidden="true">x</span></label><button '
     'id="b11">Save</button>', [(_RV, _MI)]),
    (f'{_B11} title="T"></button>', [(_RV, _MI)]),
    (f"{_B11} disabled>Save</button>", [(_RV, _MI)]),
    ('<label for="b11"></label><div><button id="b11">Save</button></div>',
     [(_RV, _MI)]),
    ('<label><button id="b11">Save</button></label>', [(_RV, _MI)]),
    ('<label for="b11"></label><input type="submit" id="b11" value="Send">',
     [(_RV, _MI)]),
    ('<label for="b11"></label><input type="submit" id="b11">',
     [(_RV, _MI)]),
    ('<label for="b11"></label><input type="reset" id="b11">', [(_RV, _MI)]),
    ('<label for="b11"></label><input type="button" id="b11" value="Go">',
     [(_RV, _MI)]),
    ('<label><input type="submit" id="b11" value="Send"></label>',
     [(_RV, _MI)]),
    ('<label for="b11"><figure>Lab</figure></label><button id="b11">Go'
     "</button>", [(_RV, _MI)]),
    # moderate where axe-core does not read the button's own name either
    (f"{_B11}><math><mi>x</mi></math></button>", [(_RV, _MO)]),
    (f"{_B11}><object>Obj</object></button>", [(_RV, _MO)]),
    (f'{_B11}><span title="Close"> </span></button>', [(_RV, _MO)]),
    (f'{_B11}><span title="Close"></span></button>', [(_RV, _MI)]),
    (f"{_B11}><figure>Fig</figure></button>", [(_RV, _MI)]),
    # what names it there
    ('<label for="b11" title="Lt"></label><button id="b11">Save</button>',
     []),
    (f'{_B11} aria-label="Al">Save</button>', []),
    (f'{_B11} aria-labelledby="L11">Save</button><span id="L11">Lb</span>',
     []),
    ('<label for="b11">Lb</label><input type="submit" id="b11" value="S">',
     []),
    ('<label>Lt <button id="b11">Save</button></label>', []),
    ('<label><button id="b11">Save</button> Lt</label>', []),
    ('<label for="b11"></label><label for="b11">L2</label><button '
     'id="b11">Save</button>', []),
    ('<label for="zz11"></label><button id="b11">Save</button>', []),
    ('<label><button id="b11">One</button><button>Two</button></label>', []),
    ('<label for="b11" inert>X</label><button id="b11">Save</button>', []),
    # R6S-3: a title Chromium reads
    ('<button><span tabindex="-1" title="Close"></span></button>', []),
    ('<div role="button" tabindex="0"><a href="/h" title="Help"></a></div>',
     []),
    # R6S-6: a title in a <label> in a <canvas>, which axe-core reads
    ('<canvas><label for="b11"><span title="Save"></span></label><button '
     'id="b11"></button></canvas>', [(_RV, _MI)]),
)


class TestNamesR6Round11(unittest.TestCase):
    """R6S-1 to R6S-8: a button's <label> in place of its own name; the
    titles Chromium reads (focus, a link, a custom element, draggable);
    what axe-core reads of a title; a <table>'s summary beside a
    <caption>; each measured in Chromium 141 and axe-core 4.12."""

    def test_links(self):
        for inner, want in _R11_LINKS:
            body = f'<a href="/x">{inner}</a>'
            with self.subTest(body=body):
                got = TestRulesRound2.found(page(body), "bb-link-name")[1]
                self.assertEqual(got, want)

    def test_link_roles(self):
        """R6S-3: an <a> with no href in a role=link: no title read."""
        body = ('<span role="link" tabindex="0"><a title="T"></a></span>'
                '<span role="link" tabindex="0"><a href="/h" title="T">'
                "</a></span>")
        got = TestRulesRound2.found(page(body), "bb-link-name")[1]
        self.assertEqual(got, [(_RV, _MI)])

    def test_buttons(self):
        for body, want in _R11_BUTTONS:
            with self.subTest(body=body):
                got = TestRulesRound2.found(page(body), "bb-button-name")[1]
                self.assertEqual(got, want)

    def test_messages(self):
        """R6S-1, R6S-2, R6S-4, R6S-6: what each review says."""
        for body, words, absent in (
                ('<a href="/x"><i class="fa" title="Home"></i></a>',
                 ("or only an icon font's glyph",
                  "Other checks usually pass it"), ()),
                (f"{_B11}>Save</button>",
                 ("has a <label> that names it nothing there",
                  "in place of its own content, value and title",
                  "Other checks usually pass it",
                  "Fix: give the <label> the button's name"), ()),
                (f"{_B11}><math><mi>x</mi></math></button>",
                 ("Nor does axe-core 4.12 read the button's own content",
                  "other checks may fail it too"), ("usually pass",)),
                ('<a href="/x"><span title="Cart">\n  </span></a>',
                 ("Nor does axe-core 4.12 read that title",
                  "holds white space"), ("usually pass",)),
                ('<canvas><label for="b11"><span title="Save"></span></label>'
                 '<button id="b11"></button></canvas>',
                 ("the title of a <span> in its <label>",),
                 ("usually pass", "may fail"))):
            with self.subTest(body=body):
                found = run_page(page(body), "t.html", RB)
                msgs = [f.message for r in found.results
                        if r.rule_id in ("bb-link-name", "bb-button-name")
                        for f in r.findings]
                self.assertEqual(len(msgs), 1)
                for w in words:
                    self.assertIn(w, msgs[0])
                for w in absent:
                    self.assertNotIn(w, msgs[0])

    def test_nested_quick(self):
        """R6S-7: 100 nested role=link elements holding 100 cards of
        MathML, which axe-core reads none of, are read in time."""
        html = page('<span role="link" tabindex="0">' * 100
                    + "<figure><math><mi>x</mi></math></figure>" * 100
                    + "</span>" * 100)
        start = time.monotonic()
        got = TestRulesRound2.found(html, "bb-link-name")[1]
        self.assertLess(time.monotonic() - start, 30)
        self.assertEqual(got, [(_RV, _MO)] * 100)


@unittest.skipUnless(HAVE_BROWSER, _WHY)
class TestNamesCaptureR6Round11(unittest.TestCase):
    """R6S-1, R6S-3, R6S-4, rendered: a button's empty <label>, a title
    in white space, a title on an element that takes focus (each measured
    in Chromium 141)."""

    def test_names(self):
        body = ('<label for="c1"></label><button id="c1">Save</button>'
                '<a id="c2" href="/x"><span title="Cart">\n  </span></a>'
                '<a id="c3" href="/y"><span tabindex="0" title="T"></span>'
                "</a>")
        site = _echo_site(self, lambda t: PAGE.format(body))
        d = tmpdir(self)
        code, _out, err = run("--url", f"{site.base}/p", "--json",
                              d / "r.json", "--fail-on", "never")
        self.assertEqual(code, 0, err)
        report = json.loads((d / "r.json").read_text())
        got = sorted((f["rule_id"], f["verdict"], f["impact"], i)
                     for p in report["pages"] for f in p["findings"]
                     if f["rule_id"] in ("bb-link-name", "bb-button-name")
                     for i in ("c1", "c2", "c3")
                     if f'id="{i}"' in f["snippet"])
        self.assertEqual(got, [
            ("bb-button-name", "needs_review", "minor", "c1"),
            ("bb-link-name", "needs_review", "moderate", "c2")])


# ---------------------------------------------------------------------------
# Round 11, R6T: the rules and claims side
# ---------------------------------------------------------------------------

class TestOwnStyleR6Round11(unittest.TestCase):
    """R6T-1 to R6T-3: a member that names a pseudo-class and holds what
    Chromium does not read drops the rule and the rules nested in it; a
    visibility var() level with a show; a <dialog open popover> (each
    measured in Chromium 141)."""

    SELECTORS = (
        ("#2:focus, .lbl{display:none}", False),
        (".lbl{display:none} #1:hover, .lbl{display:inline}", True),
        (".2col:hover, .lbl{display:none}", False),
        ("> li:hover, .lbl{display:none}", False),
        ('.a:hover "x", .lbl{display:none}', False),
        (".a:hover$, .lbl{display:none}", False),
        (".btn-<%= c %>:hover, .lbl{display:none}", False),
        (".lbl, #2:focus{display:none}", False),
        (":not(.2col), .lbl{display:none}", False),
        (":has(> .2col), .lbl{display:none}", False),
        (":nth-child(2 of .2col), .lbl{display:none}", False),
        ("::slotted(.2col), .lbl{display:none}", False),
        (":-webkit-any(.2col), .lbl{display:none}", False),
        (":is(.2col), .lbl{display:none}", True),
        (":not(:is(.2col)), .lbl{display:none}", True),
        (".a:hover, .lbl{display:none}", True),
        (":has(> .a, + .b), .lbl{display:none}", True),
        (":nth-child(2n+1 of .a, .b), .lbl{display:none}", True),
        (":modal, .lbl{display:none}", True),
        (':not([x=")"]):hover, .lbl{display:none}', True),
        (".no-js .2col, .lbl{display:none}", False),
        (".no-js .a, .lbl{display:none}", True),
        ("main { #2:focus, & .lbl {display:none} }", False),
        ("main { > a .lbl:not(.q), .q {display:none} }", True),
        ("main { > a .lbl:not(.2q), .q {display:none} }", False),
        ("#2:focus, main { .lbl {display:none} }", False),
        (".2col, main { .lbl {display:none} }", False),
        ("main:hover, main { .lbl {display:none} }", True),
        ("@scope (main) { #2:hover, .lbl {display:none} }", False),
        ("#2:focus{} @namespace x url(http://x); x|span, .lbl{display:none}",
         True),
        (".q{} @namespace x url(http://x); x|span, .lbl{display:none}",
         False))

    def test_selectors(self):
        for css, hidden in self.SELECTORS:
            with self.subTest(css=css):
                self.assertEqual(link_fails(css), hidden)

    def test_shadow(self):
        """R6T-2 in a shadow root's own stylesheet (measured)."""
        for css, hidden in ((":host(.2col), .lbl{display:none}", False),
                            (":host(.a), .lbl{display:none}", True),
                            ("::slotted(.2col), .lbl{display:none}", False),
                            (":host(#2:hover), .lbl{display:none}", False)):
            body = ('<div class="a"><template shadowrootmode="open"><style>'
                    f"{css}</style>{LINK}</template></div>")
            with self.subTest(css=css):
                got = TestRulesRound2.found(page(body), "bb-link-name")
                self.assertEqual(got == (True, [(FAIL, "blocker")]), hidden)

    def test_wide(self):
        """R6T-2: a :not() of 9,000 members, read in parts soupsieve
        takes (it reads no more than 8,192 at once), keeps its rule."""
        css = (".lbl, :not(" + ", ".join(f".a{i}" for i in range(9000))
               + "):popover-open{display:none}")
        start = time.monotonic()
        self.assertTrue(link_fails(css))
        self.assertLess(time.monotonic() - start, 30)

    def test_visibility(self):
        """R6T-1: a visibility var() whose fallback hides, or of a custom
        property the page sets, level with a show: Chromium hides the
        content, or shows it with the rules swapped, so a file run
        reviews it."""
        for css in (".a{visibility:var(--x, visible)} "
                    ".b{visibility:var(--y, hidden)}",
                    ".a{visibility:var(--x, visible)} "
                    ".b{visibility:var(--y, collapse)}",
                    ":root{--y:hidden} .a{visibility:visible} "
                    ".b{visibility:var(--y)}"):
            html = page('<div aria-hidden="true"><div class="a b"><a '
                        'href="/a">A</a></div></div>',
                        head=f"<style>{css}</style>")
            with self.subTest(css=css):
                got = TestRulesRound2.found(html, "bb-aria-hidden-focus")[1]
                self.assertEqual(got, [(NEEDS_REVIEW, "moderate")])

    def test_dialog(self):
        """R6T-3: a <dialog open popover> is shown, a revert too."""
        for head in ("", "<style>.b{display:var(--y, revert)}</style>"):
            html = page('<div aria-hidden="true"><dialog open popover '
                        'class="b"><a href="/a">A</a></dialog></div>',
                        head=head)
            with self.subTest(head=head):
                got = TestRulesRound2.found(html, "bb-aria-hidden-focus")[1]
                self.assertEqual([v for v, _i in got], [FAIL])


# ---------------------------------------------------------------------------
# Round 12, R6U: titles of elements HTML does not have, what axe-core reads
# of a title, labels Chromium leaves out, a button input's empty value
# ---------------------------------------------------------------------------

_SVW = '<svg width="16" height="16">\n<path d="M0 0h16v16H0z"/>\n</svg>'
_TH2 = "<tr><th>A</th><th>B</th></tr>"
#: bb-link-name, each measured in Chromium 141 and axe-core 4.12 (R6U-1,
#: R6U-4, R6U-6, R6U-7, R6U-10): (what the link holds, its findings).
_R12_LINKS = (
    # R6U-6: an element HTML does not have, or an obsolete one, is generic
    ('<icon title="T"></icon>', [(_RV, _MI)]),
    ('<foo title="T"></foo>', [(_RV, _MI)]),
    ('<font-face title="T"></font-face>', [(_RV, _MI)]),
    ('<marquee title="T"></marquee>', [(_RV, _MI)]),
    ('<icon draggable="true" title="T"></icon>', []),
    ('<marquee draggable="true" title="T"></marquee>', []),
    ('<acronym draggable="true" title="T"></acronym>', []),
    ('<listing draggable="true" title="T"></listing>', []),
    ('<map draggable="true" title="T"></map>', [(_RV, _MI)]),
    ('<slot title="T"></slot>', [(_RV, _MO)]),
    ('<x-y title="T"></x-y>', []),
    ('<menu title="T"></menu>', []),
    # R6U-1: axe-core reads a title past embedded and hidden content
    (f'<span title="Cart">{_SVW}</span>', [(_RV, _MI)]),
    ('<span title="Cart"><canvas>\n</canvas></span>', [(_RV, _MI)]),
    ('<span title="Cart"><object>\n</object></span>', [(_RV, _MI)]),
    ('<span title="Cart"><math>\n<mi></mi>\n</math></span>', [(_RV, _MI)]),
    ('<span title="Cart"><span style="visibility:hidden">x</span></span>',
     [(_RV, _MI)]),
    ('<span title="Cart"><span style="display:none">x</span></span>',
     [(_RV, _MI)]),
    # R6U-4: moderate for a title axe-core reads none of, said so
    ('<figure><span title="Map">\n</span></figure>', [(_RV, _MO)]),
    ('<article><i role="presentation" title="Map"></i></article>',
     [(_RV, _MO)]),
    # R6U-7: a <label> the link holds is no stop
    ('<canvas width="9" height="9"><label><span title="Save"></span>'
     "</label></canvas>", [(_RV, _MO)]),
    # R6U-10: a <caption>'s own name
    (f'<table summary="Sm"><caption aria-label="Al"></caption>{_TH2}'
     "</table>", []),
    (f'<table><caption title="Ct"></caption>{_TH2}</table>', [(_RV, _MI)]),
)
_B12 = '<button id="b12">'
#: bb-button-name (R6U-2, R6U-3, R6U-5, R6U-10): (body, its findings).
_R12_BUTTONS = (
    # R6U-3: an empty value names a button input nothing, with no default;
    # Chromium reads no title after it
    ('<input type="submit" value="">', [(FAIL, "blocker")]),
    ('<input type="submit" value=" ">', [(FAIL, "blocker")]),
    ('<input type="reset" value="">', [(FAIL, "blocker")]),
    ('<input type="submit" value="" title="T">', [(_RV, _MI)]),
    ('<input type="reset" value="" title="T">', [(_RV, _MI)]),
    ('<input type="button" value="" title="T">', [(_RV, _MI)]),
    ('<input type="submit" title="T">', []),
    ('<input type="button" title="T">', []),
    ('<input type="submit" value="" aria-label="Al">', []),
    # R6U-2: a <label> Chromium leaves out
    (f'<template><label for="b12"></label></template>{_B12}Save</button>',
     []),
    (f'<template><label for="b12">Lab</label></template>{_B12}Save'
     "</button>", []),
    ('<details><summary>More</summary><label for="b12"></label></details>'
     f"{_B12}Save</button>", []),
    ('<details><summary>More</summary><label for="b12">Lab</label>'
     f"</details>{_B12}Save</button>", []),
    ('<div hidden="until-found"><label for="b12">Lab</label></div>'
     f"{_B12}Save</button>", []),
    ('<div style="content-visibility:hidden"><label for="b12">Lab</label>'
     f"</div>{_B12}Save</button>", []),
    ('<label for="b12" hidden="until-found">Lab</label>'
     f"{_B12}Save</button>", []),
    ('<details><summary><label for="b12"></label>More</summary></details>'
     f"{_B12}Save</button>", [(_RV, _MI)]),
    (f'<dialog><label for="b12">Lab</label></dialog>{_B12}Save</button>',
     [(_RV, _MI)]),
    (f'<div hidden><label for="b12">Lab</label></div>{_B12}Save</button>',
     [(_RV, _MI)]),
    # R6U-5: axe-core passes a button whose <label for> is not on screen
    (f'<label for="b12" hidden>X</label>{_B12}<math><mi>x</mi></math>'
     "</button>", [(_RV, _MI)]),
    (f'<label for="b12" {_VH}>X</label>{_B12}<math><mi>x</mi></math>'
     "</button>", [(_RV, _MI)]),
    ('<label for="b12" style="display:none">X</label>'
     f"{_B12}<math><mi>x</mi></math></button>", [(_RV, _MI)]),
    ('<label for="b12" aria-hidden="true">X</label>'
     f"{_B12}<math><mi>x</mi></math></button>", [(_RV, _MO)]),
    (f'<label for="b12"></label>{_B12}<math><mi>x</mi></math></button>',
     [(_RV, _MO)]),
    # R6U-10: a <legend>'s own name
    ('<button><fieldset><legend aria-label="Al"></legend>Save</fieldset>'
     "</button>", []),
)


class TestNamesR6Round12(unittest.TestCase):
    """R6U-1 to R6U-10: the titles of elements HTML does not have; what
    axe-core reads of a title past embedded and hidden content; labels
    Chromium leaves out; a button input's empty value; a <caption>'s and a
    <legend>'s own name; each measured in Chromium 141 and axe-core 4.12."""

    def test_links(self):
        for inner, want in _R12_LINKS:
            body = f'<a href="/x">{inner}</a>'
            with self.subTest(body=body):
                got = TestRulesRound2.found(page(body), "bb-link-name")[1]
                self.assertEqual(got, want)

    def test_buttons(self):
        for body, want in _R12_BUTTONS:
            with self.subTest(body=body):
                got = TestRulesRound2.found(page(body), "bb-button-name")[1]
                self.assertEqual(got, want)

    def test_link_inputs(self):
        """R6U-3: a button input given role=link, with an empty value."""
        for attrs, want in (('value=""', [(FAIL, "blocker")]),
                            ('value="" title="T"', [(_RV, _MI)])):
            body = f'<input type="submit" role="link" {attrs}>'
            with self.subTest(body=body):
                got = TestRulesRound2.found(page(body), "bb-link-name")[1]
                self.assertEqual(got, want)

    def test_caption_labelledby(self):
        """R6U-10: a <caption>'s aria-labelledby names its table."""
        body = (f'<a href="/x"><table><caption aria-labelledby="c12">'
                f"</caption>{_TH2}</table></a><span id=\"c12\">Lb</span>")
        self.assertEqual(
            TestRulesRound2.found(page(body), "bb-link-name")[1], [])

    def test_messages(self):
        """R6U-3, R6U-4, R6U-9: what each review says."""
        for body, words, absent in (
                ('<input type="submit" value="" title="T">',
                 ("Chrome and Edge read no title of a button input whose "
                  "value attribute is empty", "Other checks usually pass "
                  "it"), ()),
                ('<a href="/x"><figure><span title="Map">\n</span></figure>'
                 "</a>", ("That text is a title, which axe-core 4.12 does "
                          "not read either",), ("MathML",)),
                ('<label for="b12"></label><button role="link" id="b12">'
                 "Save</button>", ("read its <label> in place of",),
                 ("a link's <label>",))):
            with self.subTest(body=body):
                found = run_page(page(body), "t.html", RB)
                msgs = [f.message for r in found.results
                        if r.rule_id in ("bb-link-name", "bb-button-name")
                        for f in r.findings]
                self.assertEqual(len(msgs), 1)
                for w in words:
                    self.assertIn(w, msgs[0])
                for w in absent:
                    self.assertNotIn(w, msgs[0])

    def test_deep_quick(self):
        """R6U-8: 300 nested links holding 300 cards of MathML."""
        html = page('<span role="link" tabindex="0">' * 300
                    + "<figure><math><mi>x</mi></math></figure>" * 300
                    + "</span>" * 300)
        start = time.monotonic()
        got = TestRulesRound2.found(html, "bb-link-name")[1]
        self.assertLess(time.monotonic() - start, 60)
        self.assertEqual(len(got), 300)


# ---------------------------------------------------------------------------
# Round 12, R6V: the rules and claims side
# ---------------------------------------------------------------------------

class TestOwnStyleR6Round12(unittest.TestCase):
    """R6V-1 to R6V-7: a nested selector that starts with a combinator
    and holds `&`; a visibility var() above a show; C1 characters in a
    name; an @scope's root; a long member; a top-level `&` (each measured
    in Chromium 141)."""

    SELECTORS = (
        ("main { > &, .lbl {display:none} }", True),
        ("main { + &, .lbl {display:none} }", True),
        ("main { ~ & .q, .lbl {display:none} }", True),
        ("@scope (main) { > :scope, .lbl {display:none} }", True),
        ("@scope (main) { > &.x, .lbl {display:none} }", True),
        ('main { [data-x="&"], .lbl {display:none} }', True),
        ("a { > & .lbl {display:none} }", False),
        ("a { > .lbl {display:none} }", True),
        ("& .lbl {display:none}", True),
        ("&.lbl {display:none}", False),
        (".lbl { & {display:none} }", True),
        (".a:hover \x85a, .lbl {display:none}", True),
        (".a\x85b, .lbl {display:none}", True),
        ("@scope (> main) { .lbl {display:none} }", False),
        ("body { @scope (> main) { .lbl {display:none} } }", True),
        ("@scope (> .r) { .q{color:red} } @namespace x url(http://x); "
         "x|span, .lbl{display:none}", True),
        (".x:not(" + " ".join(["a"] * 9000) + "), .lbl{display:none}", True))

    def test_selectors(self):
        for css, hidden in self.SELECTORS:
            with self.subTest(css=css[:80]):
                self.assertEqual(link_fails(css), hidden)

    def test_reshown(self):
        """R6V-2: a visibility var() that stands above the `visible` class
        or the style attribute's show is reviewed, not failed."""
        for head, body in (
                (":root{--v:hidden} .invisible{visibility:hidden} "
                 ".visible{visibility:visible}",
                 '<div class="invisible" aria-hidden="true"><a href="/x" '
                 'class="visible" style="visibility:var(--v)">Go</a></div>'),
                (":root{--v:hidden} .box{visibility:hidden} "
                 ".lnk{visibility:var(--v) !important}",
                 '<div class="box" aria-hidden="true"><a href="/x" '
                 'class="lnk" style="visibility:visible">Go</a></div>')):
            html = page(body, head=f"<style>{head}</style>")
            with self.subTest(head=head):
                got = TestRulesRound2.found(html, "bb-aria-hidden-focus")[1]
                self.assertEqual(got, [(NEEDS_REVIEW, "moderate")])

# ---------------------------------------------------------------------------
# Round 13, R6W: why axe-core misses a name; labels in a closed <details>;
# a <legend>'s title; more generic elements
# ---------------------------------------------------------------------------

_CV9 = '<canvas width="9" height="9">'
_SVP = '<svg role="presentation" width="90" height="20">'
#: Each measured in Chromium 141 and axe-core 4.12 (R6W-1 to R6W-8): (body,
#: rule, its findings, words its message holds).
_R13_CASES = (
    (f'<a href="/x">{_CV9}<figure>Home</figure></canvas></a>',
     "bb-link-name", [(_RV, _MO)], "That text is inside a <canvas>"),
    (f'<a href="/x">{_CV9}<article>Home</article></canvas></a>',
     "bb-link-name", [(_RV, _MO)], "That text is inside a <canvas>"),
    (f'<a href="/x">{_SVP}<g role="group"><text x="0" y="15">Home</text>'
     "</g></svg></a>", "bb-link-name", [(_RV, _MO)],
     "That text is inside an <svg>"),
    ('<a href="/x"><figure><svg aria-hidden="true" width="9" height="9">'
     '<path d="M0 0h9v9H0z"/></svg><span title="Map"> </span></figure></a>',
     "bb-link-name", [(_RV, _MO)], "That text is a title"),
    (f'<a href="/x">{_CV9}<i title="Home"></i></canvas></a>',
     "bb-link-name", [(_RV, _MO)], "That title is inside a <canvas>"),
    ('<a href="/x"><slot title="T"></slot></a>', "bb-link-name",
     [(_RV, _MO)], "it reads none of a <slot>"),
    ('<a href="/x"><svg role="presentation" width="16" height="16"><text '
     'title="Home"></text></svg></a>', "bb-link-name", [(_RV, _MO)],
     "That title is inside an <svg>"),
    ('<details><summary>Shipping <button id="b13">Edit</button></summary>'
     '<label for="b13">Change shipping</label></details>', "bb-button-name",
     [], ""),
    ('<details><summary>Shipping <button id="b13">Edit</button></summary>'
     '<label for="b13"></label></details>', "bb-button-name", [], ""),
    ('<button><fieldset><legend title="Lt"></legend>Save</fieldset>'
     "</button>", "bb-button-name", [], ""),
    ('<a href="/x"><fieldset><legend title="Lt"></legend></fieldset></a>',
     "bb-link-name", [], ""),
    ('<details><summary>S</summary><label for="b13"></label></details>'
     '<button id="b13"><math><mi>x</mi></math></button>', "bb-button-name",
     [(_RV, _MI)], "Other checks usually pass it"),
    ('<div hidden="until-found"><label for="b13"></label></div><button '
     'id="b13"><span title="Save"> </span></button>', "bb-button-name",
     [(_RV, _MI)], "Other checks usually pass it"),
    ('<a href="/x"><source title="T"></a>', "bb-link-name", [(_RV, _MI)],
     ""),
    ('<a href="/x"><track title="T"></a>', "bb-link-name", [(_RV, _MI)], ""),
    ('<a href="/x"><selectedcontent title="T"></selectedcontent></a>',
     "bb-link-name", [(_RV, _MI)], ""),
    ('<a href="/x"><x-$ title="T"></x-$></a>', "bb-link-name",
     [(_RV, _MI)], ""),
)


class TestNamesR6Round13(unittest.TestCase):
    """R6W-1 to R6W-8: the reason a moderate review gives; a <label> in a
    closed <details> whose summary holds the button; a <legend>'s title;
    a <label for> axe-core does not see; <source>, <track>,
    <selectedcontent> and invalid custom names; a drawing's <text>; each
    measured in Chromium 141 and axe-core 4.12."""

    def test_cases(self):
        for body, rule, want, words in _R13_CASES:
            with self.subTest(body=body):
                found = run_page(page(body), "t.html", RB)
                got = [(f.verdict, f.impact, f.message) for r in found.results
                       if r.rule_id == rule for f in r.findings]
                self.assertEqual([(v, i) for v, i, _m in got], want)
                if words:
                    self.assertIn(words, got[0][2])
                if want and want[0][1] == _MO:
                    self.assertNotIn("usually pass", got[0][2])


# ---------------------------------------------------------------------------
# Round 13, R6X: the rules and claims side
# ---------------------------------------------------------------------------

_BIG = " ".join(["a"] * 9000)
_RR = ('<div class="r"><div class="r"><a href="/x"><span class="lbl">Cart'
       "</span></a></div></div>")
_SHR = ('<div><template shadowrootmode="open"><style>{}</style><a href="/x">'
        '<span class="lbl">Cart</span></a></template></div>')


class TestOwnStyleR6Round13(unittest.TestCase):
    """R6X-1 to R6X-8: `&` and `:scope` in an @scope with a limit, and in a
    shadow root's stylesheet; class lists split at ASCII white space; a
    syntax error past soupsieve's limit; escapes; `> :scope` and siblings
    in @scope; an @scope's root inside another (each measured in Chromium
    141): (css, body or None for LINK, the link's text hidden)."""

    CASES = (
        (".lbl{display:none} @scope (.lbl) to (.x) { & {display:inline} }",
         None, False),
        (".lbl{display:none} @scope (.lbl) to (.x) { :scope "
         "{display:inline} }", None, False),
        ("@scope (a) to (.x) { & > .lbl {display:inline} } "
         ".lbl{display:none}", None, False),
        ("", _SHR.format("& .lbl{display:none}"), False),
        ("", _SHR.format(":scope .lbl{display:none}"), False),
        (".x:not(" + _BIG + " .2bad), .lbl{display:none}", None, False),
        (".x:not(" + _BIG + " #2), .lbl{display:none}", None, False),
        ("main { .x:not(" + _BIG + " .2bad), .lbl{display:none} }", None,
         False),
        (".a\\110000, .lbl{display:none}", None, True),
        (".a\\\\\x85b, .lbl{display:none}", None, True),
        ("@scope (.r) { > :scope .lbl {display:none} }", _RR, False),
        ("@scope (div) { > :scope {display:none} }", _RR, False),
        ("@scope (.r) { + .c {display:none} }",
         '<div class="r"></div><a href="/x" class="c"><span class="lbl">'
         "Cart</span></a>", False),
        ("@scope (main) to (.x) { @scope (> a) { .lbl{display:inline} } } "
         ".lbl{display:none}", None, False),
        (".hidden{display:none}", '<a href="/x"><span class="lbl hidden'
         '\u3000x">Cart</span></a>', False),
        (".q\x85r{display:none}", '<a href="/x"><span class="lbl q\x85r">'
         "Cart</span></a>", True),
        ('[class~="q\x85r"]{display:none}', '<a href="/x"><span class="lbl '
         'q\x85r">Cart</span></a>', True))

    def test_cases(self):
        for css, body, hidden in self.CASES:
            html = page(body or LINK, head=f"<style>{css}</style>")
            with self.subTest(css=css[:80], body=body):
                got = TestRulesRound2.found(html, "bb-link-name")
                self.assertEqual(got == (True, [(FAIL, "blocker")]), hidden)

# ---------------------------------------------------------------------------
# Round 14, R6Y and R6Z: labels in a closed <details>' summary, a drawing's
# text parts, @scope's roots and subjects, class lists in every reader
# ---------------------------------------------------------------------------

_SV60 = '<svg role="presentation" width="60" height="20">'
#: Each measured in Chromium 141 and axe-core 4.12 (R6Y-1 to R6Y-6):
#: (body, rule, its findings).
_R14_NAMES = (
    ('<details><summary><button id="b14">Edit</button><label for="b14">'
     "</label></summary></details>", "bb-button-name", [(_RV, _MI)]),
    ("<details><summary><label><button>Edit</button></label></summary>"
     "</details>", "bb-button-name", [(_RV, _MI)]),
    ('<details><summary>S <label><button><svg role="presentation" '
     'width="30" height="12"><text y="10">Edit</text></svg></button>'
     "</label></summary><p>P</p></details>", "bb-button-name", [(_RV, _MO)]),
    (f'<a href="/x">{_SV60}<text y="12" tabindex="-1" title="H"></text>'
     "</svg></a>", "bb-link-name", []),
    (f'<a href="/x">{_SV60}<text y="12" draggable="true" title="H"></text>'
     "</svg></a>", "bb-link-name", []),
    (f'<a href="/x">{_SV60}<text y="12" role="heading" title="H"></text>'
     "</svg></a>", "bb-link-name", []),
    (f'<a href="/x">{_SV60}<text y="12"><tspan title="H"></tspan></text>'
     "</svg></a>", "bb-link-name", [(_RV, _MO)]),
)
_SIB = ('<div class="r"></div><a href="/x" class="c"><span class="lbl">Cart'
        "</span></a>")
_PSC = ('<div class="parent-scope"><div class="child-scope"><a href="/x">'
        '<span class="content lbl">Cart</span></a></div></div>')
_CRD = ('<div class="card"><a href="/x"><span class="title lbl">Cart</span>'
        "</a></div>")


class TestR6Round14(unittest.TestCase):
    """R6Y-1 to R6Y-11, R6Z-1 to R6Z-8, each measured in Chromium 141 and
    axe-core 4.12."""

    def test_names(self):
        for body, rule, want in _R14_NAMES:
            with self.subTest(body=body):
                got = TestRulesRound2.found(page(body), rule)[1]
                self.assertEqual(got, want)

    def test_reasons(self):
        """R6Y-6: the reason a moderate review gives."""
        for body, words in (
                ('<a href="/x"><figure><svg role="presentation" width="20" '
                 'height="9"><text y="9">Go</text></svg><span title="Map"> '
                 "</span></figure></a>", "MathML or embedded content, or a "
                 "title"),
                ('<a href="/x"><figure><span style="visibility:hidden">'
                 '<canvas>X</canvas></span><span title="Map"> </span>'
                 "</figure></a>", "That text is a title")):
            with self.subTest(body=body):
                found = run_page(page(body), "t.html", RB)
                msgs = [f.message for r in found.results
                        if r.rule_id == "bb-link-name" for f in r.findings]
                self.assertEqual(len(msgs), 1)
                self.assertIn(words, msgs[0])

    def test_scope(self):
        """R6Z-1 to R6Z-3, R6Z-6, R6Z-7: (css, body, the .lbl hidden)."""
        for css, body, hidden in (
                ("@scope (.parent-scope) { @scope (:scope > .child-scope) "
                 "{ .content { display:none } } }", _PSC, True),
                (".content{display:none} @scope (.parent-scope) { @scope "
                 "(:scope > .child-scope) to (:scope .limit) { :scope "
                 ".content { display:inline } } }", _PSC, False),
                ("@scope (.card) { :scope .title:not(:scope .card .title) "
                 "{ display:none } }", _CRD, True),
                ("@scope (.card) { :scope:scope .lbl { display:none } }",
                 _CRD, True),
                ("@scope (.r) { :scope + .c .lbl { display:none } }", _SIB,
                 False),
                ("@scope (.r) { & ~ .c .lbl { display:none } }", _SIB,
                 False),
                ("@scope (.r) { @scope (+ .c) { .lbl {display:none} } }",
                 _SIB, False),
                ("@scope (.r) { + .c .lbl {display:none} }", _SIB, False),
                ("@scope (div) { > :scope .lbl {display:none} }",
                 '<div><div><a href="/x"><span class="lbl">Cart</span></a>'
                 "</div></div>", False),
                ("@scope (.card) { .lbl:not(:scope) { display:none } }",
                 LINK, False),
                (".x\\d800 { display:none }", '<a href="/x"><span class="lbl '
                 'x\ufffd">Cart</span></a>', True)):
            html = page(body, head=f"<style>{css}</style>")
            with self.subTest(css=css):
                got = TestRulesRound2.found(html, "bb-link-name")
                self.assertEqual(got == (True, [(FAIL, "blocker")]), hidden)

    def test_class_lists(self):
        """R6Z-4: the XML reader and a capture's reader split a class list
        at ASCII white space alone, as the HTML reader does."""
        from bellbriar_harness import html5, xhtml
        cls = "lbl hidden\u3000x"
        soup = html5.BudgetSoup(f'<span class="{cls}">x</span>')
        self.assertEqual(soup.find("span")["class"], ["lbl", "hidden\u3000x"])
        doc = xhtml.parse('<html xmlns="http://www.w3.org/1999/xhtml"><body>'
                          f'<span class="{cls}">x</span></body></html>')
        self.assertEqual(doc.find("span")["class"], ["lbl", "hidden\u3000x"])

if __name__ == "__main__":
    unittest.main()
