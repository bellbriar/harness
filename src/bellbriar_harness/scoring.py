"""Scoring per the scope spec §8: honest denominators.

- A rule passes on a page when applicable with zero `fail` findings.
- Weighted pass rate = Σ w(passed) / Σ w(applicable), pooled across pages.
- Tier-1 clean = zero fail findings from tier-1 rules (the page bar).
- Policy rules (tier 0) carry weight 0: reported, never scored.
- So does every rule that never fails (verdict_basis policy, best-practice
  or review), whatever its tier: an applicable rule that cannot fail would
  be a free pass in the rate.
- needs_review is surfaced but never counted as failure.
- Findings in markup a vendor script injected are reported apart: failures
  as third_party_fail_findings, review items as
  third_party_needs_review_findings, neither in the site's own counts.
- A rule that raised (errored) is not applicable for the rates, and a page
  where a Tier-1 rule errored is not Tier-1 clean (undecided), unless a
  Tier-1 rule failed there.
- Each page says how many Tier-1 rules ran on it (tier1_rules_executed):
  a rule a page's layers could not evaluate there (a rendered rule on a
  page no browser captured) is neither passed nor counted, so "Tier-1
  clean" on that page covers only the rules it names.
- "Tier-1 clean" rests on the Tier-1 rules that can fail and applied to
  the page (tier1_rules_applicable). Where there are none — no Tier-1 rule
  ran, or only ones that never fail ran, or none of those that can fail
  applied — the page is not Tier-1 clean: it is undecided, as a pass rate
  with nothing applicable is undefined (P1-08, R1A-2).
No single number here is a compliance claim; see docs/METHODOLOGY.md.
"""
from __future__ import annotations

from .engine import NEVER_FAIL_BASES
from .model import FAIL, PageResult


def _weights(rulebook: dict) -> dict[str, int]:
    tw = {int(k): v for k, v in rulebook["tier_weights"].items()}
    return {r["id"]: (0 if r.get("verdict_basis") in NEVER_FAIL_BASES
                      else tw.get(int(r.get("tier", 3)), 1))
            for r in rulebook["rules"]}


def _tiers(rulebook: dict) -> dict[str, int]:
    return {r["id"]: int(r.get("tier", 3)) for r in rulebook["rules"]}


def _can_fail(rulebook: dict) -> set[str]:
    """The rules whose verdict basis lets them FAIL (`sc`, `heuristic`)."""
    return {r["id"] for r in rulebook["rules"]
            if r.get("verdict_basis") not in NEVER_FAIL_BASES}


def score_page(page: PageResult, rulebook: dict) -> dict:
    w = _weights(rulebook)
    tiers = _tiers(rulebook)
    can_fail = _can_fail(rulebook)
    applicable = passed = 0
    n_fail = n_review = n_third = n_third_review = 0
    failed_rules: list[str] = []
    tier1_clean = True
    tier1_errored = False
    tier1_ran = 0
    # The Tier-1 rules "clean" can rest on here: they ran to the end, they
    # can fail, and they applied. One that never fails, or that did not
    # apply, could not have found a Tier-1 failure (R1A-2).
    tier1_applicable = 0
    for rr in page.results:
        weight = w.get(rr.rule_id, 1)
        if rr.errored and tiers.get(rr.rule_id) == 1:
            tier1_errored = True
        elif tiers.get(rr.rule_id) == 1:
            tier1_ran += 1
            if rr.applicable and rr.rule_id in can_fail:
                tier1_applicable += 1
        if rr.applicable:
            applicable += weight
            if not rr.failed:
                passed += weight
            else:
                failed_rules.append(rr.rule_id)
                if tiers.get(rr.rule_id) == 1:
                    tier1_clean = False
        for f in rr.findings:
            if f.verdict == FAIL:
                if f.owned:
                    n_fail += 1
                else:
                    n_third += 1
            elif f.owned:
                n_review += 1
            else:
                n_third_review += 1
    # No applicable rules means nothing was measured. That is not a perfect
    # score — it is an undefined one, exactly as an all-errored judged run is
    # neither 0% nor 100%. A page the executed layers cannot speak to must not
    # report as clean; the docs promise we never pad scores with free passes.
    # The same holds for a page the static rules cannot evaluate at all (a
    # client-rendered app shell): its document-level rules always applied,
    # so it used to score 100% and Tier-1 clean on an empty <div id="root">.
    evaluable = getattr(page, "evaluable", True)
    rate = (round(passed / applicable, 4)
            if applicable and evaluable else None)
    if (not evaluable or tier1_errored or not tier1_applicable) \
            and tier1_clean:
        # Undefined: nothing to be clean about. Without a Tier-1 rule that
        # can fail run to the end and applied here — a rulebook that
        # demotes them all, or keeps only ones that never fail or never
        # apply, say — "clean" would be a pass on nothing (P1-08, R1A-2).
        tier1_clean = None
    return {"path": page.path, "weighted_pass_rate": rate,
            "applicable_weight": applicable, "passed_weight": passed,
            "tier1_clean": tier1_clean,
            # The Tier-1 rules that ran to the end on this page.
            "tier1_rules_executed": tier1_ran,
            # Of those, the ones that can fail and applied here: what
            # "Tier-1 clean" rests on. 0 leaves the page undecided.
            "tier1_rules_applicable": tier1_applicable,
            "evaluable": evaluable,
            "not_evaluable_reason": getattr(page, "not_evaluable_reason", ""),
            "fail_findings": n_fail,
            "needs_review_findings": n_review,
            # Reported, never scored: markup injected by a vendor script is
            # outside evaluation scope (EXC-1) and the customer cannot edit
            # it. There is exactly one score, and it is the one they can act
            # on — two numbers would invite quoting the friendlier one.
            "third_party_fail_findings": n_third,
            # Review items in vendor markup: the site's own count leaves them
            # out, as the score leaves out vendor failures (P1-13).
            "third_party_needs_review_findings": n_third_review,
            "failed_rules": failed_rules}


def _ran(pages: list[PageResult]) -> set:
    """Rules that ran to the end on at least one page: one that raised
    everywhere was not executed (OR-18)."""
    return {rr.rule_id for p in pages for rr in p.results if not rr.errored}


def tier1_coverage(pages: list[PageResult], rulebook: dict) -> tuple[int, int]:
    """(executed, total) Tier-1 rules. `tier1_clean` means "no failure among
    the executed Tier-1 rules"; these two numbers say how many that is, so
    the boolean can never be read as more than it measures."""
    tiers = _tiers(rulebook)
    total = sum(1 for t in tiers.values() if t == 1)
    ran = _ran(pages)
    executed = sum(1 for rid, t in tiers.items() if t == 1 and rid in ran)
    return executed, total


def tier1_review_only(pages: list[PageResult], rulebook: dict) -> int:
    """How many of the executed Tier-1 rules never fail (they list findings
    for review): "clean" says nothing about them."""
    ran = _ran(pages)
    return sum(1 for r in rulebook["rules"]
               if int(r.get("tier", 3)) == 1 and r["id"] in ran
               and r.get("verdict_basis") in NEVER_FAIL_BASES)


def score_site(pages: list[PageResult], rulebook: dict) -> dict:
    page_scores = [score_page(p, rulebook) for p in pages]
    t1_executed, t1_total = tier1_coverage(pages, rulebook)
    # Rates pool only pages the rules could evaluate; the Tier-1 page bar
    # counts only pages whose Tier-1 status is decided (a shell with a real
    # Tier-1 fail is decided — it failed).
    evaluable = [s for s in page_scores if s["evaluable"]]
    decided = [s for s in page_scores if s["tier1_clean"] is not None]
    tot_app = sum(s["applicable_weight"] for s in evaluable)
    tot_pass = sum(s["passed_weight"] for s in evaluable)
    clean = sum(1 for s in decided if s["tier1_clean"])
    rule_fail_totals: dict[str, int] = {}
    for s in page_scores:
        for rid in s["failed_rules"]:
            rule_fail_totals[rid] = rule_fail_totals.get(rid, 0) + 1
    third = sum(s["third_party_fail_findings"] for s in page_scores)
    return {
        "pages": page_scores,
        "site_weighted_pass_rate": (round(tot_pass / tot_app, 4)
                                    if tot_app else None),
        "pct_pages_tier1_clean": (round(clean / len(decided), 4)
                                  if decided else None),
        "pages_not_evaluable": len(page_scores) - len(evaluable),
        "tier1_rules_executed": t1_executed,
        "tier1_rules_total": t1_total,
        "tier1_rules_review_only": tier1_review_only(pages, rulebook),
        "total_fail_findings": sum(s["fail_findings"] for s in page_scores),
        "total_needs_review": sum(s["needs_review_findings"] for s in page_scores),
        "total_third_party_fail_findings": third,
        "total_third_party_needs_review": sum(
            s["third_party_needs_review_findings"] for s in page_scores),
        "rule_fail_totals": dict(sorted(rule_fail_totals.items(),
                                        key=lambda kv: -kv[1])),
    }
