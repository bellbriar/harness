"""N4 — a FAIL means WCAG is violated, or probably is (rulebook 0.3.0).

Before: any Tier-1 FAIL broke `--fail-on tier1`, cleared "T1 clean",
lowered the score and was recorded as `fail` in the signed bundle —
including FAILs from rules the rulebook itself classes as stricter than
WCAG (`policy`) or about patterns WCAG does not require (`best-practice`),
and skip-link misfires. Five conformant pages failed the build.

The contracts:
  * policy and best-practice rules never FAIL — the engine enforces it,
    whatever a check emits — and say why, in the words customer reports
    use ("pled in complaints; not a WCAG failure on its own");
  * the skip-link rule FAILs only when it can establish the failure, and
    finds the skip link by what it says, not by being an early `#` link;
  * `--strict` fails the gate on those findings again, at moderate impact
    or above, within the --fail-on tiers: everything that failed before,
    and a missing skip link even where a main landmark stands in for one;
  * rules that never fail are reported, never scored, and a rulebook that
    says a check means something it does not is refused.
"""
import contextlib
import copy
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bellbriar_harness import cli                                # noqa: E402
from bellbriar_harness import engine as E                        # noqa: E402
from bellbriar_harness.checks_static import (PageContext,        # noqa: E402
                                             check_skip_link)
from bellbriar_harness.lint import main as lint_main             # noqa: E402
from bellbriar_harness.model import FAIL, NEEDS_REVIEW           # noqa: E402
from bellbriar_harness.scoring import (_weights, score_page,     # noqa: E402
                                       score_site)

PLED = "pled in complaints; not a WCAG failure on its own"
BEST = "a best practice; not a WCAG failure on its own"
NAV = ('<header><nav><a href="/">Home</a><a href="/shop">Shop</a>'
       '<a href="/about">About</a></nav></header>')


def page(body: str) -> str:
    return ('<!doctype html><html lang="en"><head><title>Shop</title></head>'
            f'<body>{body}</body></html>')


#: Pages that conform to what these rules can see, each of which failed
#: `--fail-on tier1` before rulebook 0.3.0.
CONFORMANT = {
    "product card: image link and title link to one product": page(
        '<a href="#main">Skip to content</a>' + NAV + '<main id="main">'
        '<h1>Mugs</h1><div class="card"><a href="/p/1">'
        '<img src="m.jpg" alt="Blue mug"></a><h2><a href="/p/1">Blue mug</a>'
        '</h2></div></main>'),
    "hash-route navigation": page(
        '<header><nav><a href="#/home">Home</a><a href="#/shop">Shop</a>'
        '<a href="#/about">About</a></nav></header><main><h1>Mugs</h1></main>'),
    "no <main>, but headings (H69)": page(
        NAV + '<div><h1>Mugs</h1><h2>Blue mug</h2><p>Nice.</p></div>'),
    "tabindex=1 with a sensible order": page(
        '<a href="#main">Skip to content</a>' + NAV + '<main id="main">'
        '<h1>Mugs</h1><input aria-label="Search" tabindex="1"></main>'),
}


def run(html: str, rulebook=None):
    rb = rulebook or E.load_rulebook()
    p = E.run_page(html, "x.html", rb)
    return p, score_page(p, rb)


def skip(html: str):
    return check_skip_link(PageContext.parse(html))


def eval_cli(html: str, *argv: str) -> tuple[int, str]:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "p.html"
        path.write_text(html, encoding="utf-8")
        out = io.StringIO()
        with contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(io.StringIO()):
            code = cli.main([str(path), *argv])
    return code, out.getvalue()


class TestConformantPagesPassTheGate(unittest.TestCase):
    def test_no_fail_no_gate_failure_and_still_reported(self):
        for name, html in CONFORMANT.items():
            with self.subTest(page=name):
                p, s = run(html)
                self.assertEqual(s["failed_rules"], [])
                self.assertTrue(s["tier1_clean"])
                self.assertEqual(eval_cli(html, "--fail-on", "tier1")[0], 0)
                self.assertTrue(any(f.verdict == NEEDS_REVIEW
                                    for rr in p.results for f in rr.findings),
                                "the pattern is still reported")

    def test_back_to_top_is_not_taken_for_a_skip_link(self):
        """It used to satisfy the rule silently."""
        rr = skip(page('<a href="#top" id="top">Back to top</a>' + NAV
                       + '<main><h1>Mugs</h1></main>'))
        self.assertEqual([f.verdict for f in rr.findings], [NEEDS_REVIEW])
        self.assertIn("No skip link", rr.findings[0].message)


class TestSkipLinkFailsWhenItCanEstablishIt(unittest.TestCase):
    def test_nothing_bypasses_the_repeated_blocks(self):
        html = page('<header><nav>' + "".join(f'<a href="/{i}">L{i}</a>'
                                               for i in range(3))
                    + '</nav></header><div><p>Body</p></div>')
        self.assertEqual([f.verdict for f in skip(html).findings], [FAIL])
        self.assertEqual(eval_cli(html, "--fail-on", "tier1")[0], 1)

    def test_the_only_mechanism_is_a_skip_link_to_nowhere(self):
        rr = skip(page('<a href="#content">Skip to content</a>' + NAV
                       + '<div><p>Body</p></div>'))
        self.assertEqual([f.verdict for f in rr.findings], [FAIL])
        self.assertIn("'#content'", rr.findings[0].message)

    def test_a_broken_skip_link_with_a_fallback_is_reviewed(self):
        rr = skip(page('<a href="#content">Skip to content</a>' + NAV
                       + '<main><h1>Mugs</h1></main>'))
        self.assertEqual([f.verdict for f in rr.findings], [NEEDS_REVIEW])
        self.assertIn(PLED, rr.findings[0].message)

    def test_working_skip_links(self):
        for html in (
                page('<a href="#c">Skip to content</a>' + NAV
                     + '<div><a name="c"></a><p>Body</p></div>'),
                page('<a href="#main%20area">Jump to main content</a>' + NAV
                     + '<div id="main area"><p>Body</p></div>'),
                page('<a href="/">Logo</a><a href="/a">A</a><a href="/b">B</a>'
                     '<a href="/c">C</a><a href="#m">Skip navigation</a>'
                     + NAV + '<div id="m"><p>Body</p></div>')):
            with self.subTest(html=html[60:140]):
                self.assertEqual(skip(html).findings, [])

    def test_hidden_or_late_links_are_not_the_skip_link(self):
        for html in (
                page('<a href="#m" aria-hidden="true" tabindex="-1">Skip to '
                     'content</a>' + NAV + '<div id="m"><p>Body</p></div>'),
                page(NAV + '<a href="#m">Skip to content</a>'
                     '<div id="m"><p>Body</p></div>')):
            with self.subTest(html=html[60:140]):
                self.assertEqual([f.verdict for f in skip(html).findings],
                                 [FAIL], "no skip link, nothing else bypasses")


class TestNotFailuresAreEnforcedByTheEngine(unittest.TestCase):
    def test_a_policy_rule_never_fails_whatever_its_check_says(self):
        rb = copy.deepcopy(E.load_rulebook())
        for r in rb["rules"]:
            if r["id"] == "bb-img-alt":           # an `sc` rule, relabeled
                r["verdict_basis"], r["pled_pattern"] = "policy", True
        p, s = run(page('<main><h1>x</h1><img src="a.png"></main>'), rb)
        alt = next(rr for rr in p.results if rr.rule_id == "bb-img-alt")
        self.assertTrue(alt.findings)
        self.assertEqual({f.verdict for f in alt.findings}, {NEEDS_REVIEW})
        self.assertTrue(all(f.message.endswith(PLED + ".") for f in alt.findings))
        self.assertNotIn("bb-img-alt", s["failed_rules"])

    def test_every_finding_says_why_it_is_not_a_failure(self):
        html = page('<a href="#main">Skip to content</a>' + NAV
                    + '<main id="main"><h1>T</h1><h2></h2>'
                    '<div role="buton" aria-labeledby="x">b</div>'
                    '<input aria-label="q" tabindex="2"></main>')
        p, _ = run(html)
        rb = {r["id"]: r for r in E.load_rulebook()["rules"]}
        seen = set()
        for rr in p.results:
            meta = rb[rr.rule_id]
            if meta.get("verdict_basis") not in E.NOT_FAILURE_BASES:
                continue
            for f in rr.findings:
                seen.add(rr.rule_id)
                self.assertEqual(f.verdict, NEEDS_REVIEW)
                self.assertIn(PLED if meta.get("pled_pattern") else BEST,
                              f.message)
        self.assertEqual(seen, {"bb-heading-structure", "bb-aria-role",
                                "bb-aria-attr", "bb-positive-tabindex"})

    def test_positive_tabindex_is_a_best_practice(self):
        rb = {r["id"]: r for r in E.load_rulebook()["rules"]}
        self.assertEqual(rb["bb-positive-tabindex"]["verdict_basis"],
                         "best-practice")
        # 0.3.0 made it one; the version has moved on since (Part Q added
        # the rendered rules), never back.
        self.assertGreaterEqual(
            tuple(map(int, E.load_rulebook()["rulebook_version"].split("."))),
            (0, 3, 0))


class TestStrict(unittest.TestCase):
    CARD = CONFORMANT["product card: image link and title link to one product"]

    def test_strict_fails_the_gate_on_what_failed_before(self):
        self.assertEqual(eval_cli(self.CARD)[0], 0)
        self.assertEqual(eval_cli(self.CARD, "--strict")[0], 1)
        tab = CONFORMANT["tabindex=1 with a sensible order"]
        self.assertEqual(eval_cli(tab, "--strict")[0], 1)

    def test_minor_findings_stay_informational_even_under_strict(self):
        logo_home = page('<a href="#main">Skip to main content</a>'
                         '<header><a href="/"><img src="l.svg" alt="Acme"></a>'
                         '<nav><a href="/">Home</a><a href="/x">X</a></nav>'
                         '</header><main id="main"><h1>T</h1><h3>Deep</h3>'
                         '</main>')
        p, _ = run(logo_home)
        self.assertTrue(any(rr.findings for rr in p.results
                            if rr.rule_id in ("bb-redundant-links",
                                              "bb-heading-structure")))
        self.assertEqual(eval_cli(logo_home, "--strict", "--fail-on", "any")[0], 0)

    def test_strict_respects_the_fail_on_tiers(self):
        role = page('<a href="#main">Skip to content</a>' + NAV
                    + '<main id="main"><h1>T</h1><div role="buton">b</div></main>')
        self.assertEqual(eval_cli(role, "--strict", "--fail-on", "tier1")[0], 0)
        self.assertEqual(eval_cli(role, "--strict", "--fail-on", "tier2")[0], 1)
        self.assertEqual(eval_cli(self.CARD, "--strict", "--fail-on", "never")[0], 0)

    def test_vendor_markup_never_gates(self):
        attr = "data-bb-p-test"
        html = page('<a href="#main">Skip to content</a>' + NAV
                    + f'<main id="main"><h1>Mugs</h1><div {attr}="third-party:'
                    'https://widget.example"><a href="/p/1"><img src="m.jpg" '
                    'alt="Blue mug"></a><a href="/p/1">Blue mug</a></div></main>')
        rb = E.load_rulebook()
        p = E.run_page(html, "x.html", rb, provenance_attr=attr)
        self.assertTrue(any(rr.findings for rr in p.results
                            if rr.rule_id == "bb-redundant-links"))
        self.assertEqual(cli._strict_findings([p], rb, "tier1"), [])

    def test_the_console_says_what_strict_would_do(self):
        code, out = eval_cli(self.CARD)
        self.assertIn("not WCAG failures on their own: 1 finding(s)", out)
        self.assertIn("--strict fails the gate on them", out)
        code, out = eval_cli(self.CARD, "--strict")
        self.assertIn("failing the gate (--strict)", out)


class TestNeverFailRulesAreReportedNotScored(unittest.TestCase):
    """A rule that cannot fail would be a free pass in the rate: weight 0,
    whatever its tier."""

    def test_they_weigh_nothing(self):
        rb = E.load_rulebook()
        w = _weights(rb)
        never = [r["id"] for r in rb["rules"]
                 if r.get("verdict_basis") in E.NEVER_FAIL_BASES]
        self.assertIn("bb-redundant-links", never)
        self.assertIn("bb-positive-tabindex", never)
        self.assertIn("bb-media-captions", never)        # basis `review`
        for rid in never:
            self.assertEqual(w[rid], 0, rid)
        self.assertEqual(w["bb-img-alt"], 5)

    def test_the_rate_counts_only_rules_that_can_fail(self):
        rb = E.load_rulebook()
        basis = E.verdict_basis(rb)
        tier = {r["id"]: str(r["tier"]) for r in rb["rules"]}
        p, s = run(page('<a href="#main">Skip to content</a>' + NAV
                        + '<main id="main"><h1>Mugs</h1><img src="a.png">'
                        '<input aria-label="q" tabindex="1"></main>'), rb)
        applicable = {rr.rule_id for rr in p.results if rr.applicable}
        self.assertLessEqual({"bb-redundant-links", "bb-positive-tabindex",
                              "bb-img-alt"}, applicable)
        self.assertEqual(s["applicable_weight"],
                         sum(rb["tier_weights"][tier[rid]] for rid in applicable
                             if basis[rid] not in E.NEVER_FAIL_BASES))
        self.assertLess(s["weighted_pass_rate"], 1)

    def test_tier1_coverage_says_how_many_rules_never_fail(self):
        rb = E.load_rulebook()
        want = sum(1 for r in rb["rules"] if r["tier"] == 1
                   and r.get("layer") == "static-dom"
                   and r.get("status") == "implemented"
                   and r.get("verdict_basis") in E.NEVER_FAIL_BASES)
        html = TestStrict.CARD
        site = score_site([E.run_page(html, "x.html", rb)], rb)
        self.assertEqual(site["tier1_rules_review_only"], want)
        code, out = eval_cli(html)
        self.assertIn(f"; {want} of them never fail, they list findings for "
                      "review. 'T1 clean' means no failure among the "
                      f"{site['tier1_rules_executed'] - want} that can fail.",
                      out)
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "r.html"
            path = Path(tmp) / "p.html"
            path.write_text(html, encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()), \
                    contextlib.redirect_stderr(io.StringIO()):
                cli.main([str(path), "--html", str(report)])
            text = report.read_text(encoding="utf-8")
        t1 = f"{site['tier1_rules_executed']} of {site['tier1_rules_total']}"
        # Each page names the Tier-1 rules that ran on it (QR-8); the run's
        # summary says how many of those never fail.
        ran_here = site["pages"][0]["tier1_rules_executed"]
        self.assertIn(f"Tier-1 clean ({ran_here} of "
                      f"{site['tier1_rules_total']} Tier-1 rules executed on "
                      "this page)", text)
        self.assertIn(f"({t1} executed; {want} of those never fail)", text)


class TestRulebookMustMatchTheChecks(unittest.TestCase):
    """A rulebook may change tiers and weights. It may not say a check means
    something it does not: a 0.2.0 rulebook would run 0.3.0 checks and be
    recorded as 0.2.0 in the signed bundle."""

    @staticmethod
    def rulebook_0_2_0() -> dict:
        rb = copy.deepcopy(E.load_rulebook())
        rb["rulebook_version"] = "0.2.0"
        for r in rb["rules"]:
            if r["id"] == "bb-positive-tabindex":
                r["verdict_basis"] = "heuristic"      # what 0.2.0 said
        return rb

    def test_an_older_rulebook_is_refused(self):
        with self.assertRaisesRegex(RuntimeError,
                                    r"say something other than what these "
                                    r"checks implement.*bb-positive-tabindex"
                                    r" \(verdict_basis\)"):
            E.validate_rulebook(self.rulebook_0_2_0())

    def test_the_cli_refuses_it_for_files_and_urls(self):
        with tempfile.TemporaryDirectory() as tmp:
            rb = Path(tmp) / "rb.json"
            rb.write_text(json.dumps(self.rulebook_0_2_0()), encoding="utf-8")
            html = Path(tmp) / "p.html"
            html.write_text(TestStrict.CARD, encoding="utf-8")
            for target in ([str(html)], ["--url", "http://127.0.0.1:9/"]):
                err = io.StringIO()
                with contextlib.redirect_stdout(io.StringIO()), \
                        contextlib.redirect_stderr(err):
                    code = cli.main([*target, "--rulebook", str(rb)])
                with self.subTest(target=target[-1]):
                    self.assertEqual(code, 2)
                    self.assertIn("say something other than what these "
                                  "checks implement", err.getvalue())

    def test_nor_which_findings_are_pled(self):
        """--strict gates a skip-link review because the rule is pled."""
        rb = copy.deepcopy(E.load_rulebook())
        for r in rb["rules"]:
            if r["id"] == "bb-skip-link":
                r["pled_pattern"] = False
        with self.assertRaisesRegex(RuntimeError, "bb-skip-link"):
            E.validate_rulebook(rb)

    def test_tiers_and_weights_may_still_change(self):
        rb = copy.deepcopy(E.load_rulebook())
        rb["tier_weights"]["1"] = 7
        for r in rb["rules"]:
            if r["id"] == "bb-alt-junk":
                r["tier"] = 2
        E.validate_rulebook(rb)


class TestStrictCountsOnlyWhatReportsMark(unittest.TestCase):
    def test_every_finding_strict_counts_says_it_is_not_a_failure(self):
        from tests.test_bypass_blocks import REVIEW_CASES, SHAPES
        bodies = ([b for b, *_ in SHAPES.values()]
                  + [b for b, *_ in REVIEW_CASES.values()])
        html = list(CONFORMANT.values()) + [page(b) for b in bodies]
        rb = E.load_rulebook()
        pages = [E.run_page(h, f"{i}.html", rb) for i, h in enumerate(html)]
        held = cli._strict_findings(pages, rb, "any")
        self.assertGreater(len({f.rule_id for f in held}), 3)
        for f in held:
            self.assertTrue(PLED in f.message or BEST in f.message, f.message)
        gated = {r["id"] for r in rb["rules"] if E.strict_gated(r)}
        for p in pages:
            for rr in p.results:
                if rr.rule_id in gated:
                    for f in rr.findings:
                        if f.verdict == NEEDS_REVIEW:
                            self.assertTrue(PLED in f.message
                                            or BEST in f.message, f.message)


class TestLintAgrees(unittest.TestCase):
    def test_positive_tabindex_warns_and_does_not_fail_an_error_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "Search.jsx"
            src.write_text('export const S = () => <input aria-label="q" '
                           'tabIndex={1} />;\n', encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(lint_main([str(src), "--fail-on", "error"]), 0)
                self.assertEqual(lint_main([str(src), "--fail-on", "warn"]), 1)
            self.assertIn("not a WCAG failure on its own", out.getvalue())


if __name__ == "__main__":
    unittest.main()
