"""Part N, round 3: the independent review of Part N's rule precision.

  * A file run failed an aria-hidden dialog or menu that a rule in the
    page's own <style> hides (a11y-dialog's `[aria-hidden='true']
    {display:none}`): a file run cannot read linked stylesheets, but it can
    read those. Such a container is now a review, as a closed Bootstrap
    modal is.
  * The class heuristic accepted a closing class on any ancestor as if it
    were the container's own: an aria-hidden region inside a closed
    collapse read like a closed modal (and passed rendered), though it
    fails once the collapse opens and aria-hidden stays. Only the
    container's own classes say "closed together" now, as the frameworks
    remove aria-hidden and the class together; a closing class around or
    inside it is a review that says to check the open state (round 4).
    Tailwind variants the pattern missed (`min-[900px]:flex`, `md:!flex`,
    `dark:md:flex`, `@md:flex`) and a `visible` descendant inside
    `invisible` show it.
  * bb-html-lang passed `i-lux` and reviewed `eng` (minor): ACT bf051a fails
    both (Failed Examples 3 and 4). See test_review_round_n.
  * The placeholder-only review said it was no WCAG failure; ACT e086e5
    notes 3.3.2 still needs a visible label. See test_review_round_n.
  * A closed popover was not read as hidden; an outer disabled fieldset did
    not disable a button in an inner one's legend; role="presentation" was
    ignored only on elements in the tab order (ARIA ignores it on any
    focusable element and with global ARIA attributes); headings in closed
    or aria-hidden modals counted toward the outline; and a few thousand
    nested titled elements in a link exhausted the stack.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bellbriar_harness import fetch as F                        # noqa: E402
from bellbriar_harness.engine import load_rulebook, run_page    # noqa: E402
from bellbriar_harness.model import FAIL, MODERATE, NEEDS_REVIEW  # noqa: E402
from tests.test_fetch_hardening import HAVE_BROWSER, _WHY, _Site, send  # noqa: E402


def page(body: str, head: str = "") -> str:
    return ('<!doctype html><html lang="en"><head><title>T</title>'
            f'{head}</head><body><main><h1>T</h1>{body}</main></body></html>')


def findings(html: str, rule: str, provenance_attr=None) -> list:
    p = run_page(html, "x.html", load_rulebook(),
                 provenance_attr=provenance_attr)
    return [f for rr in p.results if rr.rule_id == rule for f in rr.findings]


def verdicts(html: str, rule: str) -> list:
    return [f.verdict for f in findings(html, rule)]


A11Y_DIALOG = ('<div class="dialog-container" id="d" aria-hidden="true" '
               'aria-labelledby="t"><div class="dialog-content" role="document">'
               '<button type="button" aria-label="Close dialog">×</button>'
               '<h2 id="t">Title</h2></div></div>')


class TestPageStyleInFileRuns(unittest.TestCase):
    def test_a_rule_in_the_page_own_style_makes_it_a_review(self):
        for label, style, body in (
                ("a11y-dialog", "<style>.dialog-container[aria-hidden='true']"
                 "{display:none}</style>", A11Y_DIALOG),
                ("an id rule", '<style>#mobile-menu[aria-hidden="true"] '
                 '{ visibility: hidden }</style>',
                 '<nav id="mobile-menu" aria-hidden="true"><a href="/">Home</a></nav>'),
                ("a selector list, a comment", "<style>/* x */ .a, [aria-hidden=true]"
                 "{display:none}</style>", A11Y_DIALOG)):
            with self.subTest(label):
                found = findings(page(body, style), "bb-aria-hidden-focus")
                self.assertEqual([(f.verdict, f.impact) for f in found],
                                 [(NEEDS_REVIEW, MODERATE)])
                self.assertIn("page's own <style>", found[0].message)

    def test_what_a_file_run_cannot_settle_still_fails(self):
        for label, style in (
                ("inside @media", "<style>@media (max-width: 600px) {"
                 ".dialog-container{display:none}}</style>"),
                ("a print stylesheet", '<style media="print">.dialog-container'
                 "{display:none}</style>"),
                ("on hover only", "<style>.dialog-container:hover{display:none}"
                 "</style>"),
                ("another element", "<style>.other{display:none}</style>"),
                ("shown, not hidden", "<style>.dialog-container{display:block}"
                 "</style>")):
            with self.subTest(label):
                self.assertEqual(verdicts(page(A11Y_DIALOG, style),
                                          "bb-aria-hidden-focus"), [FAIL])


class TestClassOnTheContainerOnly(unittest.TestCase):
    """Round 3 read only the container's own classes, so content inside a
    closed collapse around an aria-hidden region FAILed in a file run while
    a rendered run reviewed it (round 4 of the review). Content hidden now
    by a container around or inside the aria-hidden one is a review in
    both: it becomes focusable when that opens, unless the page removes
    aria-hidden too."""

    def test_a_closing_class_elsewhere_is_a_review(self):
        for label, body in (
                ("inside a closed collapse",
                 '<div class="collapse"><div aria-hidden="true"><a href="/a">x</a>'
                 '</div></div>'),
                ("under a pre-hydration wrapper",
                 '<div id="app" class="invisible"><ul aria-hidden="true"><li><a '
                 'href="/p1">Partner</a></li></ul></div>'),
                ("a closed panel inside it",
                 '<nav aria-hidden="true"><div class="offcanvas offcanvas-start">'
                 '<a href="/x">Go</a></div></nav>')):
            with self.subTest(label):
                found = findings(page(body), "bb-aria-hidden-focus")
                self.assertEqual([(f.verdict, f.impact) for f in found],
                                 [(NEEDS_REVIEW, MODERATE)])
                self.assertIn("When that container opens", found[0].message)

    def test_visible_inside_invisible_still_fails(self):
        body = ('<div aria-hidden="true" class="invisible"><a class="visible" '
                'href="/v">V</a></div>')
        self.assertEqual(verdicts(page(body), "bb-aria-hidden-focus"), [FAIL])

    def test_tailwind_variants_that_show_it(self):
        for cls in ("hidden min-[900px]:flex", "hidden md:!flex", "hidden md:flex!",
                    "hidden dark:md:flex", "hidden @md:flex",
                    "hidden group-hover/item:block"):
            with self.subTest(cls):
                body = f'<div aria-hidden="true" class="{cls}"><a href="/x">X</a></div>'
                self.assertEqual(verdicts(page(body), "bb-aria-hidden-focus"), [FAIL])

    def test_the_container_own_class_still_reviews(self):
        for cls in ("modal fade", "hidden", "invisible", "hidden max-md:block"):
            with self.subTest(cls):
                body = f'<div aria-hidden="true" class="{cls}"><a href="/x">X</a></div>'
                want = [FAIL] if cls == "hidden max-md:block" else [NEEDS_REVIEW]
                self.assertEqual(verdicts(page(body), "bb-aria-hidden-focus"), want)


class TestMarkupHiding(unittest.TestCase):
    def test_a_closed_popover(self):
        self.assertEqual(verdicts(page('<div popover aria-hidden="true"><a href="/x">'
                                       'x</a></div>'), "bb-aria-hidden-focus"), [])
        self.assertEqual(verdicts(page('<a href="/h"><span popover>Help</span></a>'),
                                  "bb-link-name"), [FAIL])

    def test_an_outer_disabled_fieldset_disables_the_inner_legend(self):
        body = ('<div aria-hidden="true"><fieldset disabled><legend>O</legend>'
                '<fieldset disabled><legend><button>B</button></legend></fieldset>'
                '</fieldset></div>')
        self.assertEqual(verdicts(page(body), "bb-aria-hidden-focus"), [])
        # In the outer fieldset's own first legend it is enabled.
        body = ('<div aria-hidden="true"><fieldset disabled><legend><button>B'
                '</button></legend></fieldset></div>')
        self.assertEqual(verdicts(page(body), "bb-aria-hidden-focus"), [FAIL])


class TestPresentationalRoleConflicts(unittest.TestCase):
    def skips(self, body):
        return [f.message for f in findings(page(body), "bb-heading-structure")
                if "skips" in f.message]

    def test_presentation_is_ignored_on_focusable_or_labelled_headings(self):
        for attrs in ('tabindex="-1"', 'aria-label="Section"',
                      'aria-describedby="x"'):
            with self.subTest(attrs):
                self.assertEqual(self.skips(f'<h2 role="presentation" {attrs}>S</h2>'
                                            '<h3>Deep</h3>'), [])
        self.assertEqual(len(self.skips('<h2 role="presentation">S</h2><h3>D</h3>')), 1)


class TestOutlineIgnoresHiddenHeadings(unittest.TestCase):
    def test_closed_modal_headings(self):
        modal = ('<div class="modal" aria-hidden="true"><h1 class="modal-title">'
                 'Book</h1><button>Close</button></div>')
        html = ('<!doctype html><html lang="en"><head><title>T</title></head><body>'
                f'<main><h2>Visible</h2>{modal}</main></body></html>')
        messages = [f.message for f in findings(html, "bb-heading-structure")]
        self.assertTrue(any(m.startswith("No h1") for m in messages), messages)
        # A modal open over the page: the dialog is what the page exposes,
        # so the outline behind it is not judged (as bb-skip-link does).
        consent = ('<!doctype html><html lang="en"><head><title>T</title></head>'
                   '<body><div aria-hidden="true" inert><main><h1>Shop</h1></main>'
                   '</div><div role="dialog" aria-modal="true" aria-label="Age">'
                   '<button>Yes</button></div></body></html>')
        self.assertEqual([f.message for f in findings(consent, "bb-heading-structure")],
                         [])
        flowbite = ('<div id="m" aria-hidden="true" class="hidden"><h3>Terms</h3>'
                    '</div>')
        self.assertEqual([f for f in findings(page(flowbite), "bb-heading-structure")
                          if "skips" in f.message], [])


class TestDeepTitles(unittest.TestCase):
    def test_nested_titled_elements_do_not_stop_the_run(self):
        # Named by its title in the accessible-name computation, by none in
        # Chromium 141, which reads no <span>'s title there: a review
        # (R6Q-5), not a FAIL, and the run goes on.
        deep = '<span title="t">' * 3000 + "</span>" * 3000
        self.assertEqual(verdicts(page(f'<a href="/x">{deep}</a>'),
                                  "bb-link-name"), [NEEDS_REVIEW])
        self.assertEqual(verdicts(page('<a href="/x"><span title=""></span></a>'),
                                  "bb-link-name"), [FAIL])


@unittest.skipUnless(HAVE_BROWSER, _WHY)
class TestRenderedContentHiddenAroundIt(unittest.TestCase):
    STYLE = ("<style>.collapse{display:none}.modal{display:none}"
             ".modal.show{display:block}</style>")

    def capture(self, body):
        site = _Site({"/": send(page(body, self.STYLE).encode())})
        self.addCleanup(site.stop)
        fr = F.fetch(site.base + "/", render=True)
        return findings(fr.html, "bb-aria-hidden-focus", fr.provenance_attr)

    def test_hidden_only_by_a_container_around_it_is_a_review(self):
        found = self.capture('<div class="collapse"><div aria-hidden="true">'
                             '<a href="/a">x</a></div></div>')
        self.assertEqual([(f.verdict, f.impact) for f in found],
                         [(NEEDS_REVIEW, MODERATE)])
        self.assertIn("container around it", found[0].message)

    def test_hidden_with_the_container_is_nothing(self):
        self.assertEqual(self.capture('<div class="modal" aria-hidden="true">'
                                      '<button>Close</button></div>'), [])


if __name__ == "__main__":
    unittest.main()
