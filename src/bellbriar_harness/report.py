"""The JSON report, `bellbriar-report/1` (A8), and what the HTML report
shows from it.

docs/REPORT.md documents every field, and docs/bellbriar-report-1.schema.json
states them as a JSON Schema the test suite checks reports against. Within
`bellbriar-report/1` a field is never removed, renamed or given another
meaning or type: a release may add fields, and a script should ignore the
ones it does not know. A change that breaks that takes
`bellbriar-report/2`.

The HTML report (report_html.py) is drawn from this record, so the two never
disagree.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from .model import FAIL

#: The format string every JSON report starts with.
REPORT_FORMAT = "bellbriar-report/1"
#: What a finding's fingerprint is computed under (finding_fingerprints).
FINGERPRINT_FORMAT = "bellbriar-finding/1"
#: How a run got its pages: files read as they are, files served on this
#: machine and rendered (--render), or pages fetched from a site (--url,
#: --urls, --sitemap).
SOURCES = ("files", "render", "urls")


def _digest(value) -> str:
    """The first 32 hex digits of the SHA-256 of `value` as JSON with ASCII
    escapes and no spaces: the same bytes for the same value on every
    machine, whatever characters it holds (a file name that is not valid
    UTF-8 too, R3A-11)."""
    data = json.dumps(value, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("ascii")).hexdigest()[:32]


def finding_fingerprints(path: str, findings: list, page_n: int = 0
                         ) -> list[str]:
    """A fingerprint for each of a page's (rule id, finding) pairs, in the
    order given (docs/REPORT.md, "Fingerprints"): _digest of
    [FINGERPRINT_FORMAT, the rule, the page's path, `page_n` (the page's
    number among the run's pages recorded under the same path, page_numbers:
    0 unless two pages share one), what the finding is about
    (Finding.about: its element's tag, the start of its text and its first
    descendants, or "" for the page), and how many findings of that rule
    about the same thing came before it on the page]. The same element
    failing the same rule on the same page has the same fingerprint run
    after run, even when its line moves; a second copy of it gets the next
    one. `--baseline` matches findings by it, and by what the gate reads of
    them (baseline_key)."""
    seen: dict = {}
    out = []
    for rule_id, f in findings:
        about = getattr(f, "about", "") or ""
        n = seen.get((rule_id, about), 0)
        seen[(rule_id, about)] = n + 1
        out.append(_digest([FINGERPRINT_FORMAT, rule_id, path, page_n,
                            about, n]))
    return out


def page_numbers(pages: list) -> list[int]:
    """Each page's `n`: 0, unless pages of the run were recorded under the
    same path (URLs that differ only in values recorded as REDACTED,
    R3A-1). Those are numbered in an order fixed by the full URL the run
    was given for each (PageResult.order, which no record holds: the
    SHA-256 of it, so the numbers show nothing of the redacted values), not
    by where each stands in the run's list, so a sitemap that lists them in
    another order does not move their fingerprints onto each other
    (R4B-3)."""
    groups: dict = {}
    for i, page in enumerate(pages):
        groups.setdefault(page.path, []).append(i)
    out = [0] * len(pages)
    for members in groups.values():
        if len(members) < 2:
            continue
        ranked = sorted(members, key=lambda i: (hashlib.sha256(
            (getattr(pages[i], "order", "") or "").encode(
                "utf-8", "surrogateescape")).hexdigest(), i))
        for n, i in enumerate(ranked):
            out[i] = n
    return out


def run_fingerprints(pages: list) -> dict:
    """{id(finding): its fingerprint} for every finding of a run's pages,
    as the JSON report gives them."""
    out: dict = {}
    for page, n in zip(pages, page_numbers(pages)):
        pairs = [(rr.rule_id, f) for rr in page.results for f in rr.findings]
        for (_rid, f), fp in zip(pairs, finding_fingerprints(page.path, pairs,
                                                             n)):
            out[id(f)] = fp
    return out


def rule_tiers(rulebook: dict) -> dict:
    """{rule id: its tier, as the report's `rules` records it}."""
    return {r.get("id"): r.get("tier") for r in rulebook.get("rules", [])}


def baseline_key(fingerprint: str, verdict: str, owned: bool, tier,
                 impact) -> tuple:
    """What `--baseline` matches a finding by (A10): its fingerprint (the
    same element, rule and page) and everything the gate reads of it — its
    verdict, whether it is the site's own, its rule's tier and its impact.
    A finding the baseline lists with another of those is new to it: a
    review that became a FAIL (R4B-1), a vendor's failure that became the
    site's own (R4B-2), a rule a rulebook moved into a tier the gate counts
    (R4B-4), a review whose impact --strict now counts."""
    return (fingerprint, verdict, bool(owned), tier, impact)


def new_findings(pages: list, rulebook: dict, baseline) -> set:
    """id() of each of this run's findings `baseline` does not list
    (baseline_key)."""
    prints = run_fingerprints(pages)
    tiers = rule_tiers(rulebook)
    return {id(f) for page in pages for rr in page.results
            for f in rr.findings
            if baseline_key(prints[id(f)], f.verdict, f.owned,
                            tiers.get(rr.rule_id), f.impact)
            not in baseline.keys}


def baseline_counts(pages: list, rulebook: dict, baseline
                    ) -> tuple[int, int]:
    """(this run's findings not in `baseline`, and of them the FAIL
    findings in the site's own markup), as the `baseline` record gives
    them."""
    new = new_findings(pages, rulebook, baseline)
    new_fail = sum(1 for page in pages for rr in page.results
                   for f in rr.findings
                   if id(f) in new and f.verdict == FAIL and f.owned)
    return len(new), new_fail


def _finding_out(rule_id: str, f, basis: dict, fingerprint: str,
                 baseline=None, tier=None) -> dict:
    return {
        "rule_id": rule_id,
        "verdict": f.verdict,
        # What this finding's rule can mean: only "sc" is a success-
        # criterion violation (engine.VERDICT_BASES).
        "verdict_basis": basis.get(rule_id, ""),
        "impact": f.impact,
        "message": f.message,
        "line": f.line,
        "selector": f.selector,
        "snippet": f.snippet,
        "origin": f.origin,
        "origin_detail": f.origin_detail,
        # Is it the site's own (counted), or a vendor's (reported apart)?
        "owned": f.owned,
        "about": getattr(f, "about", "") or "",
        "fingerprint": fingerprint,
        # Whether the --baseline report lists it, with the same verdict,
        # owner, tier and impact (A10, baseline_key); null without one.
        "in_baseline": (None if baseline is None else baseline_key(
            fingerprint, f.verdict, f.owned, tier, f.impact)
            in baseline.keys),
    }


def _engine(rule_id: str) -> str:
    """Who decides the rule, from the code itself (axe.AXE_RULES), never
    from what a rulebook says (R3B-7)."""
    from .axe import AXE_RULES
    return "axe-core" if rule_id in AXE_RULES else "bellbriar"


def rule_records(pages: list, rulebook: dict, guidance: dict | None = None
                 ) -> dict:
    """{rule id: what the rule is, and how it fared in this run}, for every
    rule with a result on at least one page, in rulebook order."""
    if guidance is None:
        from .guidance import load_guidance
        guidance = load_guidance()
    ran: dict = {}
    for page in pages:
        for rr in page.results:
            t = ran.setdefault(rr.rule_id, {
                "pages_applicable": 0, "pages_failed": 0, "pages_errored": 0,
                "fail_findings": 0, "needs_review_findings": 0,
                "third_party_fail_findings": 0,
                "third_party_needs_review_findings": 0})
            if rr.errored:
                t["pages_errored"] += 1
            elif rr.applicable:
                t["pages_applicable"] += 1
                if rr.failed:
                    t["pages_failed"] += 1
            for f in rr.findings:
                key = ("fail_findings" if f.verdict == FAIL
                       else "needs_review_findings")
                t[key if f.owned else "third_party_" + key] += 1
    out = {}
    for r in rulebook.get("rules", []):
        if r.get("id") not in ran:
            continue
        g = (guidance.get("rules") or {}).get(r["id"]) or {}
        out[r["id"]] = {
            "name": r.get("name", ""),
            "sc": list(r.get("sc") or []),
            "tier": r.get("tier"),
            "layer": r.get("layer"),
            "verdict_basis": r.get("verdict_basis"),
            "engine": _engine(r["id"]),
            "understanding": r.get("understanding") or None,
            "why": g.get("why"),
            "fix": g.get("fix"),
            **ran[r["id"]],
        }
    # A result under an id the rulebook does not list (an internal check
    # that raised, such as the app-shell detector) still shows.
    for rid, t in ran.items():
        if rid not in out:
            out[rid] = {"name": rid, "sc": [], "tier": None,
                        "layer": None, "verdict_basis": None,
                        "engine": "bellbriar", "understanding": None,
                        "why": None, "fix": None, **t}
    return out


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_report(run: dict, site: dict, judged: dict | None = None,
                 generated_at: str | None = None,
                 guidance: dict | None = None, baseline=None) -> dict:
    """The JSON report for a run (`bellbriar-report/1`); `baseline` is the
    run's --baseline (baseline.Baseline), or None."""
    from . import baseline as BL
    from .engine import verdict_basis
    basis = verdict_basis(run["rulebook"])
    # Each (page, rule) that could not be evaluated, page by page: two
    # pages can share a recorded path (R3A-1).
    errors = sum(len({rid for rid, _err in page.errors()})
                 for page in run["pages"])
    pages = []
    tiers = rule_tiers(run["rulebook"])
    for page, pscore, page_n in zip(run["pages"], site["pages"],
                                    page_numbers(run["pages"])):
        pairs = [(rr.rule_id, f) for rr in page.results for f in rr.findings]
        prints = finding_fingerprints(page.path, pairs, page_n)
        pages.append({
            "path": page.path,
            # The page's own capture record (URL and --render runs); None
            # for a file read as it is, and for a page never fetched.
            "fetch": page.fetch,
            "score": pscore,
            "findings": [_finding_out(rid, f, basis, fp, baseline,
                                      tiers.get(rid))
                         for (rid, f), fp in zip(pairs, prints)],
            "not_applicable_rules": [rr.rule_id for rr in page.results
                                     if not rr.applicable
                                     and not rr.errored],
            # Rules that raised: their result here is unknown (P2-12).
            "errors": [{"rule_id": rid, "error": err}
                       for rid, err in page.errors()],
        })
    return {
        "format": REPORT_FORMAT,
        "generated_at": generated_at or _now(),
        "source": run.get("source") or "files",
        "tool": run["tool"],
        "rulebook_version": run["rulebook_version"],
        # Which rules ran, exactly (P1-08): a version names a release of
        # the rulebook, the digest names its content.
        "rulebook_sha256": run["rulebook_sha256"],
        "rulebook_bundled": run["rulebook_bundled"],
        "layers": run["layers"],
        "coverage_note": run["coverage_note"],
        # A rule or page the harness could not evaluate makes the whole run
        # incomplete: its rates leave those results out, and it carries no
        # evidence bundle (each is listed in its page's "errors").
        "incomplete": bool(errors),
        "errors": errors,
        "site": {k: v for k, v in site.items() if k != "pages"},
        "rules": rule_records(run["pages"], run["rulebook"], guidance),
        # A URL run's record of what it fetched, as the bundle carries it
        # (already redacted at capture); None for files, rendered or not,
        # and for a URL run that could fetch no page.
        "fetch": run.get("fetch"),
        # Reserved for the adequacy track, which is not in 1.0 (L4): null.
        "judged": judged,
        # The --baseline the gate compared with (A10), or null.
        "baseline": BL.record(baseline, *baseline_counts(
            run["pages"], run["rulebook"], baseline))
        if baseline is not None else None,
        "pages": pages,
    }
