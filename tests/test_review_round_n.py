"""Part N: rule precision (decisions D4 and the D2 groundwork, findings N19,
N21, P2-08, P2-11 and P2-13).

  * N19: a closed modal written as Bootstrap's and Flowbite's docs write it
    (`aria-hidden="true"` on a container its class hides) failed
    bb-aria-hidden-focus as a 4.1.2 violation, in file and rendered runs
    alike. Hidden content cannot take focus. A rendered capture now records
    what the page's stylesheets hide (model.hidden_attr); a file run, which
    cannot read stylesheets, reviews such a container instead of failing it.
  * P2-11: text hidden by an inline style, or (in a rendered run) by a
    stylesheet, named the link or button around it.
  * N21: an unnamed `<a href role="button">` failed twice, as an empty link
    and as an empty button. A browser exposes it as a button only.
  * D4: a field named only by its placeholder is a moderate review, pled in
    complaints, which --strict gates; it is no longer a blocker FAIL.
  * P2-13: lang="xx" passed; bb-alt-junk failed aria-hidden images; the
    aria-hidden focus rule missed media controls, editing hosts and image-map
    areas and reported nested containers twice; heading order sorted by
    source line, so on one-line HTML every role="heading" came last.
  * P2-08: DPUB-ARIA, Graphics-ARIA and ARIA 1.3 roles and attributes were
    reported as unknown.
"""
import contextlib
import functools
import http.server
import importlib.util
import io
import re
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bellbriar_harness import cli, engine as E, fetch as F          # noqa: E402
from bellbriar_harness.langtags import (PRIMARY_LANGUAGE_SUBTAGS,     # noqa: E402
                                        REGISTRY_DATE)
from bellbriar_harness.model import (FAIL, MINOR, MODERATE,           # noqa: E402
                                     NEEDS_REVIEW, hidden_attr)

HAVE_BROWSER, _WHY = F.playwright_available()


def page(body: str, lang: str = "en") -> str:
    return (f'<!doctype html><html lang="{lang}"><head><title>T</title></head>'
            f'<body><main><h1>T</h1>{body}</main></body></html>')


def findings(html: str, rule: str, provenance_attr=None) -> list:
    p = E.run_page(html, "x.html", E.load_rulebook(),
                   provenance_attr=provenance_attr)
    return [f for rr in p.results if rr.rule_id == rule for f in rr.findings]


def verdicts(html: str, rule: str, provenance_attr=None) -> list:
    return [f.verdict for f in findings(html, rule, provenance_attr)]


BOOTSTRAP_MODAL = (
    '<div class="modal fade" id="m" tabindex="-1" aria-labelledby="mt" '
    'aria-hidden="true"><div class="modal-dialog"><div class="modal-content">'
    '<h2 id="mt">Title</h2><button type="button" class="btn-close" '
    'aria-label="Close"></button><a href="/terms">Terms</a></div></div></div>')
FLOWBITE_MODAL = (
    '<div id="d" tabindex="-1" aria-hidden="true" class="hidden overflow-y-auto '
    'fixed top-0 z-50"><div><h3>Terms</h3><button type="button">Accept'
    '</button></div></div>')


class TestClosedModalsInFileRuns(unittest.TestCase):                  # N19
    def test_bootstrap_and_flowbite_closed_modals_are_reviews(self):
        for label, body in (("bootstrap", BOOTSTRAP_MODAL),
                            ("flowbite", FLOWBITE_MODAL)):
            with self.subTest(label):
                found = findings(page(body), "bb-aria-hidden-focus")
                self.assertEqual([f.verdict for f in found], [NEEDS_REVIEW])
                self.assertEqual(found[0].impact, MODERATE)
                self.assertIn("--url", found[0].message)

    def test_shown_or_visible_containers_still_fail(self):
        for label, body in (
                ("open modal", BOOTSTRAP_MODAL.replace('modal fade"', 'modal fade show"')),
                ("inline display:block", BOOTSTRAP_MODAL.replace(
                    'tabindex="-1"', 'tabindex="-1" style="display: block"')),
                ("tailwind hidden md:block", FLOWBITE_MODAL.replace(
                    'class="hidden ', 'class="hidden md:block ')),
                ("bootstrap d-none d-md-block",
                 '<div aria-hidden="true" class="d-none d-md-block"><a href="/x">X</a></div>'),
                ("navbar-collapse",
                 '<div class="collapse navbar-collapse" aria-hidden="true"><a href="/x">X</a></div>'),
                ("no hiding class", '<div aria-hidden="true"><button>Go</button></div>'),
                ("sr-only is not hidden",
                 '<div aria-hidden="true" class="sr-only"><a href="/x">X</a></div>'),
                ("one offender outside the closed part",
                 '<div aria-hidden="true"><div class="hidden"><a href="/a">A</a></div>'
                 '<a href="/b">B</a></div>')):
            with self.subTest(label):
                self.assertEqual(verdicts(page(body), "bb-aria-hidden-focus"), [FAIL])

    def test_the_review_is_not_gated_by_strict(self):
        rules = {r["id"]: r for r in E.load_rulebook()["rules"]}
        self.assertFalse(E.strict_gated(rules["bb-aria-hidden-focus"]))


class TestAriaHiddenFocusables(unittest.TestCase):                    # P2-13
    def test_more_kinds_of_focusable_content(self):
        for label, inner in (
                ("video controls", '<video controls src="a.mp4"></video>'),
                ("audio controls", '<audio controls src="a.mp3"></audio>'),
                ("contenteditable", '<div contenteditable>Notes</div>'),
                ("contenteditable=true", '<div contenteditable="true">Notes</div>'),
                ("plaintext-only", '<div contenteditable="plaintext-only">N</div>'),
                ("image-map area", '<map name="m"><area href="/a" alt="A"></map>'),
                ("disabled does not apply to links", '<a href="/a" disabled>A</a>'),
                ("legend of a disabled fieldset",
                 '<fieldset disabled><legend><button>Edit</button></legend></fieldset>')):
            with self.subTest(label):
                self.assertEqual(verdicts(page(f'<div aria-hidden="true">{inner}</div>'),
                                          "bb-aria-hidden-focus"), [FAIL])

    def test_content_that_cannot_take_focus(self):
        for label, inner in (
                ("contenteditable=false", '<div contenteditable="false">N</div>'),
                ("video without controls", '<video src="a.mp4"></video>'),
                ("disabled fieldset", '<fieldset disabled><button>Off</button></fieldset>'),
                ("negative tabindex", '<a href="/a" tabindex="-1">A</a>')):
            with self.subTest(label):
                self.assertEqual(verdicts(page(f'<div aria-hidden="true">{inner}</div>'),
                                          "bb-aria-hidden-focus"), [])

    def test_nested_containers_report_once(self):
        body = ('<div aria-hidden="true"><div aria-hidden="true">'
                '<a href="/a">A</a></div></div>')
        self.assertEqual(verdicts(page(body), "bb-aria-hidden-focus"), [FAIL])


class TestHiddenTextIsNoName(unittest.TestCase):                      # P2-11
    def test_inline_hidden_text_does_not_name(self):
        for style in ("display:none", "visibility:hidden", "visibility: collapse"):
            with self.subTest(style):
                body = (f'<a href="/cart"><span style="{style}">Cart</span>'
                        '<svg aria-hidden="true"></svg></a>')
                self.assertEqual(verdicts(page(body), "bb-link-name"), [FAIL])
                btn = f'<button><span style="{style}">Save</span></button>'
                self.assertEqual(verdicts(page(btn), "bb-button-name"), [FAIL])

    def test_visible_text_beside_hidden_text_names(self):
        body = '<button><span style="display:none">x</span> Save</button>'
        self.assertEqual(verdicts(page(body), "bb-button-name"), [])

    def test_an_element_hidden_itself_keeps_its_name(self):
        """Name rules still check a hidden element (a closed menu shows it
        later); its own hiding must not empty its name."""
        body = '<nav class="menu"><a href="/a" style="visibility:hidden">About</a></nav>'
        self.assertEqual(verdicts(page(body), "bb-link-name"), [])


class TestNamedControlRoles(unittest.TestCase):                      # N21
    def rules(self, body: str) -> list:
        p = E.run_page(page(body), "x.html", E.load_rulebook())
        return sorted(rr.rule_id for rr in p.results for f in rr.findings
                      if f.verdict == FAIL and rr.rule_id in
                      ("bb-link-name", "bb-button-name", "bb-img-alt",
                       "bb-widget-name", "bb-control-label"))

    def test_one_unnamed_control_is_one_finding(self):
        for body, want in (
                ('<a href="#" role="button" class="dropdown-toggle"><i class="fa fa-search"></i></a>',
                 ["bb-button-name"]),
                ('<button role="link"></button>', ["bb-link-name"]),
                ('<span role="link" tabindex="0"></span>', ["bb-link-name"]),
                ('<div role="button" tabindex="0"></div>', ["bb-button-name"]),
                ('<div role="foo button" tabindex="0"></div>', ["bb-button-name"]),
                # A role another name rule checks is that rule's (QR-13).
                ('<a href="/a" role="menuitem"></a>', ["bb-widget-name"]),
                ('<button role="tab"></button>', ["bb-widget-name"]),
                ('<button role="switch"></button>', ["bb-control-label"]),
                ('<a href="/a" role="presentation"></a>', ["bb-link-name"]),
                ('<input type="image" src="go.png">', ["bb-img-alt"]),
                ('<map name="m"><area href="/a"></map>', ["bb-img-alt"])):
            with self.subTest(body):
                self.assertEqual(self.rules(body), want)

    def test_named_controls_pass(self):
        for body in ('<a href="#" role="button" aria-label="Filters"></a>',
                     '<button role="link">Docs</button>',
                     '<span role="link" tabindex="0">Offers</span>'):
            with self.subTest(body):
                self.assertEqual(self.rules(body), [])

    def test_svg_with_aria_13_image_role_is_checked(self):
        self.assertEqual(verdicts(page('<svg role="image"></svg>'), "bb-svg-name"), [FAIL])
        self.assertEqual(verdicts(page('<svg role="image" aria-label="Map"></svg>'),
                                  "bb-svg-name"), [])


class TestPlaceholderOnly(unittest.TestCase):                         # D4
    BODY = '<form><input type="email" placeholder="Email"><button>Go</button></form>'

    def test_a_placeholder_only_field_is_a_pled_review(self):
        found = findings(page(self.BODY), "bb-control-label")
        self.assertEqual([(f.verdict, f.impact) for f in found],
                         [(NEEDS_REVIEW, MODERATE)])
        self.assertIn("pled in complaints", found[0].message.lower())
        # ACT e086e5's note: the placeholder names the field, but 3.3.2
        # still needs a label that stays visible. The review must not say
        # it is no failure.
        self.assertIn("3.3.2", found[0].message)
        self.assertNotIn("not a WCAG failure", found[0].message)
        textarea = '<textarea placeholder="Message"></textarea>'
        self.assertEqual(verdicts(page(textarea), "bb-control-label"), [NEEDS_REVIEW])

    def test_a_field_with_no_name_still_fails(self):
        for body in ('<input type="text" name="zip">',
                     '<select name="size"><option>S</option></select>'):
            with self.subTest(body):
                self.assertEqual(verdicts(page(body), "bb-control-label"), [FAIL])

    def test_strict_gates_it_and_the_default_gate_does_not(self):
        tmp = Path(tempfile.mkdtemp(prefix="bb-n-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        f = tmp / "p.html"
        f.write_text(page(self.BODY), encoding="utf-8")

        def code(*args):
            with contextlib.redirect_stdout(io.StringIO()), \
                    contextlib.redirect_stderr(io.StringIO()):
                return cli.main([str(f), *args])
        self.assertEqual(code("--fail-on", "tier1"), 0)
        self.assertEqual(code("--fail-on", "tier1", "--strict"), 1)


class TestStrictGatesOnlyPledReviews(unittest.TestCase):
    """--strict counts the moderate reviews of pled sc and heuristic rules,
    so every such review must be one a report marks "pled in complaints"."""

    def test_on_every_fixture(self):
        rules = {r["id"]: r for r in E.load_rulebook()["rules"]}
        files = [p for p in (ROOT / "fixtures").rglob("*.html")
                 if "captured" not in p.parts]
        self.assertGreater(len(files), 40)
        for path in files:
            run = E.run_page(path.read_text(encoding="utf-8", errors="replace"),
                             str(path), E.load_rulebook())
            for rr in run.results:
                meta = rules.get(rr.rule_id, {})
                if not E.strict_gated(meta) or meta.get("verdict_basis") not in (
                        "sc", "heuristic"):
                    continue
                for f in rr.findings:
                    if f.verdict == NEEDS_REVIEW and f.impact not in (MINOR,):
                        with self.subTest(path=path.name, rule=rr.rule_id):
                            self.assertIn("pled in complaints", f.message.lower())


class TestLanguageSubtags(unittest.TestCase):                         # P2-13
    def test_registry_copy(self):
        self.assertRegex(REGISTRY_DATE, r"^\d{4}-\d{2}-\d{2}$")
        self.assertIn("en", PRIMARY_LANGUAGE_SUBTAGS)
        self.assertIn("haw", PRIMARY_LANGUAGE_SUBTAGS)
        self.assertIn("qtz", PRIMARY_LANGUAGE_SUBTAGS)       # a range, expanded
        self.assertNotIn("xx", PRIMARY_LANGUAGE_SUBTAGS)

    def test_verdicts(self):
        unknown3 = next(a + b + c for a in "zyx" for b in "zyx" for c in "zyx"
                        if a + b + c not in PRIMARY_LANGUAGE_SUBTAGS)
        for lang, want in (("en", []), ("en-US", []), ("EN", []), ("haw", []),
                           ("zh-Hant-TW", []), ("qaa", []), ("zh-yue", []),
                           # Every grandfathered tag: ACT gives none a known
                           # primary language tag.
                           ("zh-min-nan", [FAIL]), ("en-GB-oed", [FAIL]),
                           ("art-lojban", [FAIL]), ("x", [FAIL]), ("i", [FAIL]),
                           ("xx", [FAIL]), ("zz-ZZ", [FAIL]), ("en_US", [FAIL]),
                           ("english", [FAIL]), (unknown3, [NEEDS_REVIEW]),
                           # ACT bf051a Failed Examples 3 and 4: an ISO 639-2
                           # code BCP 47 writes with two letters, and an
                           # irregular grandfathered tag.
                           ("eng", [FAIL]), ("fre-CA", [FAIL]), ("DEU", [FAIL]),
                           ("i-lux", [FAIL]), ("i-klingon", [FAIL]),
                           ("x-klingon", [FAIL])):
            with self.subTest(lang=lang):
                self.assertEqual(verdicts(page("", lang=lang), "bb-html-lang"), want)
        eng = findings(page("", lang="eng"), "bb-html-lang")[0].message
        self.assertIn('Use "en"', eng)
        private = findings(page("", lang="x-klingon"), "bb-html-lang")[0].message
        self.assertIn("private-use", private)
        self.assertNotIn("not a valid", private)
        nan = findings(page("", lang="zh-min-nan"), "bb-html-lang")[0].message
        self.assertIn('grandfathered', nan)
        self.assertIn('Use "nan"', nan)
        self.assertIn("not a valid", findings(page("", lang="x"), "bb-html-lang")[0].message)
        review = findings(page("", lang=unknown3), "bb-html-lang")[0]
        self.assertEqual(review.impact, MINOR)
        self.assertIn(REGISTRY_DATE, review.message)

    def test_the_generator_reads_the_iana_format(self):
        spec = importlib.util.spec_from_file_location(
            "make_langtags", ROOT / "tools" / "make_langtags.py")
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        tmp = Path(tempfile.mkdtemp(prefix="bb-lt-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        reg = tmp / "registry"
        reg.write_text("File-Date: 2025-08-25\n%%\nType: language\nSubtag: aa\n"
                       "Description: Afar\n%%\nType: language\nSubtag: qaa..qac\n"
                       "Description: Private use\n%%\nType: grandfathered\n"
                       "Tag: i-klingon\nDescription: Klingon\n", encoding="utf-8")
        date, recs = tool.records(reg)
        self.assertEqual(date, "2025-08-25")
        self.assertEqual(tool.expand("qaa..qac"), ["qaa", "qab", "qac"])
        loc = tmp / "iso639-2.txt"       # the Library of Congress format
        loc.write_text("\ufeffeng||en|English|anglais\nfre|fra|fr|French|"
                       "français\nhaw||||Hawaiian|hawaïen\n", encoding="utf-8")
        self.assertEqual(tool.iso639_2(loc), {"eng": "en", "fre": "fr", "fra": "fr"})
        rows = tmp / "language-codes-full.csv"   # datasets/language-codes
        rows.write_text('"alpha3-b","alpha3-t","alpha2","English","French"\n'
                        '"ger","deu","de","German","allemand"\n'
                        '"haw","","","Hawaiian","hawaïen"\n', encoding="utf-8")
        self.assertEqual(tool.iso639_2(rows), {"ger": "de", "deu": "de"})
        with contextlib.redirect_stdout(io.StringIO()):
            # Far too small to be the whole registry: refused, nothing written.
            self.assertEqual(tool.main(["x", str(reg), str(loc),
                                        str(tmp / "out.py")]), 1)
        self.assertFalse((tmp / "out.py").exists())


class TestAltJunkSkipsHiddenImages(unittest.TestCase):                # P2-13
    def test(self):
        self.assertEqual(verdicts(page('<img src="a.png" alt="IMG_1234.jpg">'),
                                  "bb-alt-junk"), [FAIL])
        for body in ('<img src="a.png" alt="IMG_1234.jpg" aria-hidden="true">',
                     '<span aria-hidden="true"><img src="a.png" alt="photo.png"></span>',
                     '<img src="a.png" alt="photo.png" hidden>'):
            with self.subTest(body):
                self.assertEqual(verdicts(page(body), "bb-alt-junk"), [])


class TestHeadingOrder(unittest.TestCase):                            # P2-13
    def skips(self, body: str) -> list:
        return [f.message for f in findings(body, "bb-heading-structure")
                if "skips" in f.message]

    def test_one_line_html_keeps_document_order(self):
        html = ('<!doctype html><html lang="en"><head><title>T</title></head><body>'
                '<h1>A</h1><div role="heading" aria-level="2">B</div><h3>C</h3>'
                '</body></html>')
        self.assertEqual(self.skips(html), [])

    def test_a_role_overrides_the_heading(self):
        html = page('<h2 role="tab">Overview</h2><h2>Section</h2>')
        self.assertEqual(self.skips(html), [])
        self.assertEqual(
            [m.split(" — ")[0] for m in
             self.skips(page('<h2 role="tab">x</h2><h4>Deep</h4>'))],
            ["Heading level skips from h1 to h4"])


class TestAriaVocabulary(unittest.TestCase):                          # P2-08
    def reviews(self, body: str) -> list:
        return [f.message for rule in ("bb-aria-role", "bb-aria-attr")
                for f in findings(page(body), rule)]

    def test_dpub_graphics_and_aria_13_are_known(self):
        body = ('<a href="#fn1" role="doc-noteref">1</a>'
                '<section role="doc-endnotes"><p id="fn1">Note '
                '<a href="#r" role="doc-backlink">Back</a></p></section>'
                '<svg role="graphics-document" aria-label="Plan"></svg>'
                '<div role="comment">Nice</div><mark role="mark">x</mark>'
                '<table><tr aria-rowindex="1" aria-rowindextext="One">'
                '<td aria-colindex="1" aria-colindextext="A">a</td></tr></table>')
        self.assertEqual(self.reviews(body), [])

    def test_typos_and_abstract_roles_are_reported(self):
        self.assertEqual(len(self.reviews('<div role="docnoteref">1</div>'
                                          '<div role="widget">w</div>'
                                          '<div aria-rowindextxt="x">y</div>')), 3)


class TestSnippetsShowThePagesMarkup(unittest.TestCase):
    """A rendered capture writes its records (provenance, muted, hidden) into
    the markup it measures. A finding's snippet is what the customer reads
    to find the element in their own code: it shows the page's markup, not
    the harness's records."""
    ATTR = "data-bb-p-0123456789abcdef"

    def test_capture_records_are_left_out(self):
        a = self.ATTR
        html = page(f'<a href="/c" {a}="server"><span class="x" {a}="server" '
                    f'{a}-hidden="display">Cart</span></a>'
                    f'<video autoplay src="v.mp4" {a}="third-party:https://cdn.example" '
                    f"{a}-muted='1'></video>").replace("<main>", f'<main {a}="server">'
                    ).replace('<html lang="en">', f'<html lang="en" {a}-hidden="recorded">')
        p = E.run_page(html, "x.html", E.load_rulebook(), provenance_attr=a)
        snippets = [f.snippet for rr in p.results for f in rr.findings]
        self.assertTrue(any("/c" in s for s in snippets), snippets)
        for s in snippets:
            self.assertNotIn("data-bb-p-", s)
        link = next(s for s in snippets if 'href="/c"' in s)
        self.assertIn('<span class="x">Cart</span>', link)

    def test_a_file_run_keeps_every_attribute(self):
        # Without a capture, an attribute that looks like a record is the
        # page's own markup, and the snippet shows it.
        a = self.ATTR
        found = findings(page(f'<a href="/c" {a}="server"></a>'), "bb-link-name")
        self.assertIn(f'{a}="server"', found[0].snippet)


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args, **kwargs):
        pass


class _Server:
    def __init__(self, root: Path):
        handler = functools.partial(_Quiet, directory=str(root))
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()


@unittest.skipUnless(HAVE_BROWSER, _WHY)
class TestCaptureRecordsWhatThePageHides(unittest.TestCase):          # N19, P2-11
    STYLE = ('<style>.modal{display:none}.modal.show{display:block}'
             '.oc{visibility:hidden}.gone{display:none}.menu{display:none}'
             '.wrap{display:contents}</style>')

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="bb-n-cap-"))
        body = (BOOTSTRAP_MODAL
                + '<div class="oc" aria-hidden="true"><a href="/o">Offcanvas</a></div>'
                + '<div aria-hidden="true" id="open"><a href="/v">Visible</a></div>'
                + '<a href="/cart" id="cartlink"><span class="gone">Cart</span>'
                  '<svg aria-hidden="true"></svg></a>'
                + '<nav class="menu"><a href="/m" id="menulink">Menu item</a></nav>'
                + '<a href="/w" id="wraplink"><span class="wrap">Wrapped</span></a>')
        html = page(body).replace("<head>", "<head>" + cls.STYLE)
        (cls.tmp / "p.html").write_text(html, encoding="utf-8")
        cls.srv = _Server(cls.tmp)
        cls.fr = F.fetch(f"{cls.srv.base}/p.html", render=True)

    @classmethod
    def tearDownClass(cls):
        cls.srv.stop()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_the_capture_marks_hidden_subtrees(self):
        attr = hidden_attr(self.fr.provenance_attr)
        self.assertIn(f'{attr}="recorded"', self.fr.html)
        self.assertRegex(self.fr.html, rf'<div[^>]*class="modal fade"[^>]*{attr}="display"'
                                       rf'|<div[^>]*{attr}="display"[^>]*class="modal fade"')
        self.assertIn(f'{attr}="visibility"', self.fr.html)
        # Only where hiding starts: nothing inside the modal is marked.
        inside = self.fr.html.split('id="mt"')[1].split("</div>")[0]
        self.assertNotIn(attr, inside)

    def test_hidden_containers_hold_nothing_focusable(self):
        found = findings(self.fr.html, "bb-aria-hidden-focus",
                         provenance_attr=self.fr.provenance_attr)
        self.assertEqual([(f.verdict, 'id="open"' in f.snippet) for f in found],
                         [(FAIL, True)])

    def test_names_ignore_text_the_page_hides(self):
        found = findings(self.fr.html, "bb-link-name",
                         provenance_attr=self.fr.provenance_attr)
        ids = sorted(re.search(r'id="(\w+)"', f.snippet).group(1) for f in found)
        # The cart link's only text is hidden; the menu link is hidden with
        # its menu and keeps its name; display:contents hides nothing.
        self.assertEqual(ids, ["cartlink"])

    def test_without_the_record_a_file_run_reviews_the_modal(self):
        found = findings(self.fr.html, "bb-aria-hidden-focus")
        modal = [f for f in found if "modal" in f.snippet]
        self.assertEqual([f.verdict for f in modal], [NEEDS_REVIEW])

    def test_snippets_leave_the_records_out(self):
        p = E.run_page(self.fr.html, "x.html", E.load_rulebook(),
                       provenance_attr=self.fr.provenance_attr)
        snippets = [f.snippet for rr in p.results for f in rr.findings]
        self.assertTrue(snippets)
        for s in snippets:
            self.assertNotIn(self.fr.provenance_attr, s)

    def test_a_page_cannot_see_or_write_the_record(self):
        attr = hidden_attr(self.fr.provenance_attr)
        self.assertNotIn(attr, (self.tmp / "p.html").read_text(encoding="utf-8"))
        self.assertTrue(attr.startswith(self.fr.provenance_attr))


@unittest.skipUnless(HAVE_BROWSER, _WHY)
class TestCaptureNotesAHiddenBody(unittest.TestCase):
    def test(self):
        tmp = Path(tempfile.mkdtemp(prefix="bb-n-body-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        html = page('<div aria-hidden="true"><a href="/x">X</a></div>').replace(
            "<head>", "<head><style>body{visibility:hidden}</style>")
        (tmp / "p.html").write_text(html, encoding="utf-8")
        srv = _Server(tmp)
        try:
            fr = F.fetch(f"{srv.base}/p.html", render=True)
        finally:
            srv.stop()
        self.assertTrue(any("<body> was hidden" in n for n in fr.notes), fr.notes)
        # Read as shown: the aria-hidden link is still focusable content.
        self.assertEqual(verdicts(fr.html, "bb-aria-hidden-focus",
                                  provenance_attr=fr.provenance_attr), [FAIL])


if __name__ == "__main__":
    unittest.main()
