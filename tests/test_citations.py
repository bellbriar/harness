"""P2-14: every citation in the rulebook matches W3C's own text.

tests/data/w3c-citations.json holds the facts the rulebook cites, made by
tools/w3c_citations.py from W3C's repositories (w3c/wcag, with its
act-mapping.json, and w3c/wcag-act-rules). Each rule's success criteria,
level, Understanding link, ACT rules and failure techniques are checked
against it, so a citation that drifts from W3C's text fails here rather
than shipping (PREPUBLISH items 2 and 3). The snapshot is regenerated from
fresh clones before a release.
"""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bellbriar_harness.engine import load_rulebook               # noqa: E402

W3C = json.loads((ROOT / "tests" / "data" / "w3c-citations.json")
                 .read_text(encoding="utf-8"))
CRITERIA, ACT, FAILURES = W3C["criteria"], W3C["act_rules"], W3C["failures"]
#: The bases whose rules never FAIL; sc and heuristic rules can.
NEVER_FAIL = ("policy", "best-practice", "review")
LEVELS = {"A": 1, "AA": 2, "AAA": 3}
UNDERSTANDING = re.compile(
    r"https://www\.w3\.org/WAI/WCAG2(?P<v>[12])/Understanding/(?P<slug>[a-z0-9-]+)\.html")


def rules():
    return load_rulebook()["rules"]


def criteria_of(rule):
    """The success criteria a rule cites (two flow rules cite WCAG's
    complete-processes requirement, "process", instead)."""
    return [s for s in rule.get("sc", []) if s != "process"]


class TestCriteria(unittest.TestCase):
    def test_every_criterion_exists_and_is_current(self):
        for r in rules():
            for sc in criteria_of(r):
                with self.subTest(rule=r["id"], sc=sc):
                    self.assertIn(sc, CRITERIA, "no such success criterion")
                    self.assertFalse(CRITERIA[sc]["obsolete"],
                                     f"{sc} is obsolete")

    def test_the_level_is_one_of_the_criteria_levels(self):
        for r in rules():
            levels = {CRITERIA[s]["level"] for s in criteria_of(r)}
            if not levels:
                continue
            with self.subTest(rule=r["id"]):
                self.assertIn(r.get("level"), levels)

    def test_criteria_of_wcag_2_2_are_marked(self):
        """The rulebook targets WCAG 2.1 AA: a rule for a 2.2 criterion
        says so, and never fails (it reports for review); a rule marked 2.2
        cites one."""
        for r in rules():
            new = [s for s in criteria_of(r)
                   if CRITERIA[s]["introduced"] == "2.2"]
            with self.subTest(rule=r["id"]):
                if new:
                    self.assertEqual(r.get("wcag_version"), "2.2")
                    if r.get("status") == "implemented":
                        self.assertIn(r.get("verdict_basis"), NEVER_FAIL)
                elif r.get("wcag_version") == "2.2":
                    self.fail("marked WCAG 2.2, cites no 2.2 criterion")


class TestUnderstandingLinks(unittest.TestCase):
    def test_each_link_is_the_understanding_document_of_a_cited_criterion(self):
        """In the set the URL names: the WCAG 2.1 set has no document for a
        2.2 criterion, and calls 2.5.5's target-size."""
        for r in rules():
            url = r.get("understanding")
            if not url:          # checked below, for rules that run
                continue
            with self.subTest(rule=r["id"]):
                m = UNDERSTANDING.fullmatch(url)
                self.assertIsNotNone(m, f"not an Understanding URL: {url}")
                docs = {CRITERIA[sc]["understanding"][f"2.{m['v']}"]
                        for sc in criteria_of(r)}
                self.assertIn(m["slug"], docs - {None},
                              f"WCAG 2.{m['v']} has no {m['slug']} document "
                              f"for {criteria_of(r)}")

    def test_every_deterministic_rule_with_criteria_links_one(self):
        for r in rules():
            if r.get("status") == "implemented" and \
                    r.get("layer") in ("static-dom", "rendered") and criteria_of(r):
                with self.subTest(rule=r["id"]):
                    self.assertTrue(r.get("understanding"))


class TestActCitations(unittest.TestCase):
    def test_each_citation_is_a_w3c_rule_with_its_title_and_status(self):
        for r in rules():
            for cite in r.get("act_rules") or []:
                with self.subTest(rule=r["id"], act=cite.get("id")):
                    self.assertEqual(set(cite), {"id", "title", "status"})
                    self.assertIn(cite["id"], ACT, "no such ACT rule")
                    self.assertEqual(cite["title"], ACT[cite["id"]]["title"])
                    self.assertEqual(cite["status"], ACT[cite["id"]]["status"])

    def test_each_cited_rule_tests_a_criterion_the_rule_cites(self):
        """A rule that can fail cites an ACT rule only for a criterion W3C
        maps it to for conformance. A rule that never fails may also cite
        one that maps a criterion it cites as secondary ("more strict" or
        "less strict" than the ACT rule), or that maps none."""
        for r in rules():
            for cite in r.get("act_rules") or []:
                act = ACT[cite["id"]]
                cited = set(criteria_of(r))
                with self.subTest(rule=r["id"], act=cite["id"]):
                    if r.get("verdict_basis") not in NEVER_FAIL:
                        self.assertTrue(set(act["conformance"]) & cited,
                                        f"{cite['id']} requires "
                                        f"{act['conformance']} for "
                                        f"conformance, the rule cites "
                                        f"{sorted(cited)}")
                    elif act["conformance"] or act["secondary"]:
                        self.assertTrue(set(act["conformance"]
                                            + act["secondary"]) & cited)

    def test_a_deprecated_rule_supports_no_failure(self):
        """W3C deprecated it: a rule that cites one never FAILs."""
        for r in rules():
            if any(c["status"] == "deprecated" for c in r.get("act_rules") or []):
                with self.subTest(rule=r["id"]):
                    self.assertIn(r.get("verdict_basis"),
                                  ("policy", "best-practice", "review"))

    def test_only_deterministic_rules_cite_act_rules(self):
        for r in rules():
            if r.get("act_rules"):
                with self.subTest(rule=r["id"]):
                    self.assertEqual(r.get("status"), "implemented")
                    self.assertIn(r.get("layer"), ("static-dom", "rendered"))


class TestWhatSuccessCriterionFailureMeans(unittest.TestCase):
    """verdict_basis sc: a FAIL is a failure of the cited criterion that
    W3C names. R2 review (R2B-1): four sc rules rested only on proposed
    ACT rules."""

    def test_a_criterion_failure_is_one_w3c_names(self):
        for r in rules():
            if r.get("status") != "implemented" or \
                    r.get("verdict_basis") != "sc":
                continue
            cited = set(criteria_of(r))
            approved = [c["id"] for c in r.get("act_rules") or []
                        if c["status"] == "approved"
                        and set(ACT[c["id"]]["conformance"]) & cited]
            with self.subTest(rule=r["id"]):
                self.assertTrue(approved or r.get("w3c_failures"),
                                "no approved ACT rule requires a cited "
                                "criterion and no W3C failure is named: "
                                "the basis is heuristic")

    def test_each_failure_technique_fails_a_cited_criterion(self):
        for r in rules():
            for fid in r.get("w3c_failures") or []:
                with self.subTest(rule=r["id"], failure=fid):
                    self.assertIn(fid, FAILURES, "W3C lists no such failure")
                    self.assertFalse(FAILURES[fid]["obsolete"])
                    self.assertTrue(set(FAILURES[fid]["criteria"])
                                    & set(criteria_of(r)),
                                    f"{fid} fails {FAILURES[fid]['criteria']}")

    def test_the_rulebook_says_what_sc_means(self):
        note = load_rulebook()["verdict_basis_note"]
        self.assertIn("a W3C failure technique (w3c_failures), or an ACT "
                      "rule approved by W3C", note)


def fail_problems(rule) -> list:
    """What is wrong with what a rule that can FAIL cites. A report prints
    every criterion a rule cites beside its FAIL (R2 review of the citation
    fixes, R2E-1 and R2E-7: bb-control-label named 3.3.2 and 1.3.1, which
    its ACT rule does not require; a rule could cite a level-AAA criterion).
    So each is at level A or AA, the rulebook's target, and, for an sc
    rule, one W3C names a failure of: an approved ACT rule the rule cites
    requires it for conformance, or a failure technique in w3c_failures
    fails it. For a heuristic rule which criteria a probable failure
    concerns is a judgment these tests cannot check."""
    basis = rule.get("verdict_basis")
    if rule.get("status") != "implemented" or not basis or basis in NEVER_FAIL:
        return []
    out = []
    for sc in criteria_of(rule):
        level = CRITERIA.get(sc, {}).get("level")
        if LEVELS.get(level, 9) > LEVELS["AA"]:
            out.append(f"{sc} is level {level}, beyond the A/AA target")
        if basis == "sc":
            acts = [c["id"] for c in rule.get("act_rules") or []
                    if c["status"] == "approved"
                    and sc in ACT.get(c["id"], {}).get("conformance", [])]
            techniques = [f for f in rule.get("w3c_failures") or []
                          if f in FAILURES and not FAILURES[f]["obsolete"]
                          and sc in FAILURES[f]["criteria"]]
            if not (acts or techniques):
                out.append(f"W3C names no failure of {sc} this rule cites")
    return out


class TestWhatAFailIsNamedFor(unittest.TestCase):
    def test_every_criterion_a_rule_that_can_fail_cites(self):
        for r in rules():
            with self.subTest(rule=r["id"]):
                self.assertEqual(fail_problems(r), [])

    def test_the_wrong_citations_the_review_built_are_caught(self):
        by_id = {r["id"]: r for r in rules()}

        def changed(rid, **fields):
            rule = json.loads(json.dumps(by_id[rid]))
            rule.update(fields)
            return rule
        for rule in (changed("bb-page-title", sc=["2.4.2", "1.3.1"]),
                     changed("bb-control-label",
                             sc=["3.3.2", "1.3.1", "4.1.2"]),
                     changed("bb-control-role", sc=["4.1.2", "2.4.9"],
                             w3c_failures=["F59", "F89"]),
                     changed("bb-link-in-text", sc=["2.4.9"], level="AAA",
                             w3c_failures=["F89"])):
            with self.subTest(rule=rule["id"], sc=rule["sc"]):
                self.assertTrue(fail_problems(rule))


class TestTheRecord(unittest.TestCase):
    def test_the_rulebook_names_the_sources_it_was_checked_against(self):
        rb = load_rulebook()
        record = rb["citations_checked"]
        wcag, act = W3C["sources"]["wcag"], W3C["sources"]["act_rules"]
        self.assertIn(wcag["commit"][:12], record["wcag"])
        self.assertIn(act["commit"][:12], record["act_rules"])
        self.assertNotIn("act_verified", json.dumps(rb),
                         "every citation is checked: no per-rule flag")

    def test_the_snapshot_holds_what_the_checks_read(self):
        self.assertGreaterEqual(len(CRITERIA), 87)
        self.assertEqual(CRITERIA["1.4.10"]["level"], "AA")
        self.assertTrue(CRITERIA["4.1.1"]["obsolete"])
        self.assertEqual(CRITERIA["2.5.5"]["understanding"],
                         {"2.1": "target-size", "2.2": "target-size-enhanced"})
        self.assertIsNone(CRITERIA["2.5.8"]["understanding"]["2.1"])
        self.assertEqual(ACT["23a2a8"]["title"],
                         "Image has non-empty accessible name")
        self.assertEqual({v["status"] for v in ACT.values()},
                         {"approved", "proposed", "deprecated"})
        self.assertEqual(ACT["c5a4ea"]["conformance"], ["1.2.3"])
        self.assertIn("1.2.5", ACT["c5a4ea"]["secondary"])
        self.assertEqual(FAILURES["F16"], {"criteria": ["2.2.2"],
                                           "obsolete": False})
        self.assertNotIn("F47", FAILURES, "obsolete: no document lists it")


if __name__ == "__main__":
    unittest.main(verbosity=2)
