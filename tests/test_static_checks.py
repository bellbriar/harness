import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bellbriar_harness.accname import static_accname          # noqa: E402
from bellbriar_harness.checks_static import CHECKS, PageContext  # noqa: E402
from bellbriar_harness.engine import load_rulebook, run_paths, validate_rulebook  # noqa: E402
from bellbriar_harness.model import FAIL                       # noqa: E402
from bellbriar_harness.scoring import score_site               # noqa: E402

FIXTURES = ROOT / "fixtures"

EXPECTED_BAD_FAILS = {
    "bb-img-alt", "bb-svg-name", "bb-link-name", "bb-button-name",
    "bb-control-label", "bb-html-lang",
    "bb-page-title", "bb-viewport-zoom",
    "bb-aria-hidden-focus", "bb-marquee-blink",
    "bb-table-headers", "bb-iframe-title",
    "bb-media-autoplay", "bb-meta-refresh",
}
EXPECTED_BAD_REVIEWS = {"bb-autocomplete", "bb-doc-links", "bb-a11y-statement"}
#: Found on bad.html, and reported for review rather than failed (rulebook
#: 0.3.0): patterns WCAG does not require on their own (policy and
#: best-practice rules), a missing skip link on a page whose headings can
#: satisfy 2.4.1, a reference that points nowhere (Part R2: the name
#: rule of the element it leaves unnamed fails that element), and a
#: duplicated id that only aria-describedby names (L72-3: no name depends
#: on it).
EXPECTED_BAD_NOT_FAILURES = {
    "bb-redundant-links", "bb-positive-tabindex", "bb-aria-role",
    "bb-aria-attr", "bb-heading-structure", "bb-skip-link", "bb-aria-ref",
    "bb-duplicate-id",
}


class TestRulebook(unittest.TestCase):
    def test_rulebook_matches_checks(self):
        validate_rulebook(load_rulebook())


class TestBadFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = run_paths([FIXTURES / "bad.html"])
        cls.page = cls.report["pages"][0]

    def test_expected_rules_fail(self):
        failed = set(self.page.failed_rules())
        missing = EXPECTED_BAD_FAILS - failed
        self.assertFalse(missing, f"rules did not fail: {sorted(missing)}")

    def test_expected_reviews_present(self):
        review_rules = {rr.rule_id for rr in self.page.results
                        for f in rr.findings if f.verdict != FAIL}
        missing = EXPECTED_BAD_REVIEWS - review_rules
        self.assertFalse(missing, f"missing needs_review: {sorted(missing)}")

    def test_patterns_that_are_not_failures_are_found_not_failed(self):
        reported = {rr.rule_id for rr in self.page.results if rr.findings}
        self.assertFalse(EXPECTED_BAD_NOT_FAILURES - reported,
                         "each is still detected")
        self.assertFalse(EXPECTED_BAD_NOT_FAILURES & set(self.page.failed_rules()),
                         "none of them is a FAIL")

    def test_scoring_flags_tier1(self):
        site = score_site(self.report["pages"], self.report["rulebook"])
        self.assertFalse(site["pages"][0]["tier1_clean"])
        self.assertLess(site["site_weighted_pass_rate"], 0.5)


class TestGoodFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = run_paths([FIXTURES / "good.html"])
        cls.page = cls.report["pages"][0]

    def test_no_fail_findings_at_all(self):
        fails = [(rr.rule_id, f.message) for rr in self.page.results
                 for f in rr.findings if f.verdict == FAIL]
        self.assertEqual(fails, [])

    def test_tier1_clean_and_high_rate(self):
        site = score_site(self.report["pages"], self.report["rulebook"])
        self.assertTrue(site["pages"][0]["tier1_clean"])
        self.assertEqual(site["site_weighted_pass_rate"], 1.0)


class TestAccname(unittest.TestCase):
    def _ctx(self, html):
        return PageContext.parse(html)

    def test_aria_label_wins_over_contents(self):
        ctx = self._ctx('<button aria-label="Close">X</button>')
        el = ctx.soup.find("button")
        self.assertEqual(static_accname(el, ctx.soup, ctx.ids), "Close")

    def test_labelledby_resolves(self):
        ctx = self._ctx('<span id="t">Search products</span>'
                        '<input aria-labelledby="t">')
        el = ctx.soup.find("input")
        self.assertEqual(static_accname(el, ctx.soup, ctx.ids),
                         "Search products")

    def test_img_alt_names_link(self):
        ctx = self._ctx('<a href="/x"><img src="a.png" alt="Cart"></a>')
        el = ctx.soup.find("a")
        self.assertEqual(static_accname(el, ctx.soup, ctx.ids), "Cart")

    def test_label_for_control(self):
        ctx = self._ctx('<label for="e">Email</label><input id="e">')
        el = ctx.soup.find("input")
        self.assertEqual(static_accname(el, ctx.soup, ctx.ids), "Email")

    def test_empty_link_has_no_name(self):
        ctx = self._ctx('<a href="/x"><span class="icon"></span></a>')
        el = ctx.soup.find("a")
        self.assertEqual(static_accname(el, ctx.soup, ctx.ids), "")


class TestNonRegression(unittest.TestCase):
    def test_every_check_runs_on_empty_page(self):
        ctx = PageContext.parse("<!doctype html><html></html>")
        for rule_id, fn in CHECKS.items():
            rr = fn(ctx)
            self.assertEqual(rr.rule_id, rule_id)


if __name__ == "__main__":
    unittest.main(verbosity=2)
