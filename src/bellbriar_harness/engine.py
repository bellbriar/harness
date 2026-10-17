"""Run pages through the rulebook and declare layer coverage honestly."""
from __future__ import annotations

import hashlib
import json
from importlib import resources
from pathlib import Path

from . import __version__
from .bundle import bundled_rulebook_digest, rulebook_digest
from .checks_static import (CHECKS, PROVENANCE_ATTR, PageContext,
                            detect_app_shell)
from .checks_rendered import RENDERED_CHECKS
from .model import (BLOCKER, CURRENT_PAGE, FAIL, HIDDEN_VIEW, MINOR,
                    MODERATE, NEEDS_REVIEW, SERIOUS, PageResult, RuleResult,
                    hidden_attr, narrow_changed_attr, narrow_hidden_attr)

# The texts a run writes about its own coverage, and the patterns a
# verifier knows them by (L93), are coverage_text's.
from .coverage_text import (  # noqa: E402,F401 (re-exported)
    COVERAGE_SENTENCE, LAYERS, NOTHING_READ_LAYER_NOTE,
    NOTHING_READ_SENTENCE, RENDERED_COVERAGE_SENTENCE,
    RENDERED_LAYER_ENDING, RENDERED_SENTENCE, SERVER_ONLY_SENTENCE)

#: The rendered rule Bellbriar checks itself (checks_rendered.check_reflow);
#: the others are axe-core's.
REFLOW_RULE = "bb-reflow-320"


def _axe_results(page) -> int:
    """How many of axe-core's rules have a result on `page`."""
    return sum(1 for r in page.results
               if r.rule_id in RENDERED_CHECKS and r.rule_id != REFLOW_RULE)


def _rendered_pages(pages) -> tuple[list, list, list]:
    """(the pages the rules read; those of them axe-core's rules ran on;
    those reflow was checked on). A rendered rule has a result only where
    the capture recorded its run (checks_rendered)."""
    read = [p for p in pages if not getattr(p, "parse_error", "")]
    axe = [p for p in read if _axe_results(p)]
    reflow = [p for p in read if any(r.rule_id == REFLOW_RULE
                                     for r in p.results)]
    return read, axe, reflow


def _no_narrow(pages) -> list:
    """The pages a browser checked (axe-core's rules or reflow have a
    result) whose rules were not also run with what the page hides at 320
    CSS pixels (PageResult.narrow): the narrow record could not be taken
    or kept there, and the capture's notes say why."""
    _read, axe, reflow = _rendered_pages(pages)
    seen = {id(p) for p in axe} | {id(p) for p in reflow}
    return [p for p in pages if id(p) in seen
            and not getattr(p, "narrow", False)]


def _axe_versions(pages) -> str:
    versions = sorted({p.axe_version for p in pages
                       if getattr(p, "axe_version", "")})
    return " and ".join(versions) or "?"


def _from_snapshot(pages) -> list:
    """Pages whose axe-core results this run read from a snapshot the
    harness captured earlier (a re-run with --provenance-attr, run_paths):
    no browser ran for them now (R1B-4)."""
    return [p for p in pages if getattr(p, "axe_from_snapshot", False)]


def _on(some: list, read: list) -> str:
    """Where a partial check ran, and that it did not run anywhere else."""
    if len(some) == len(read):
        return ""
    rest = len(read) - len(some)
    return (f" on {len(some)} of the {len(read)} pages it read (NOT "
            f"evaluated on the "
            f"{'other' if rest == 1 else f'other {rest}'})")


def layer_records(pages) -> list[dict]:
    """The run's layer records (LAYERS), with the rendered layer as these
    pages make it: "executed" when the rendered rules ran on every page the
    rules read, "partial" on some, "skipped" on none."""
    read, axe, reflow = _rendered_pages(pages)
    n = len(RENDERED_CHECKS) - 1
    # Pages where axe-core ran but some of its rules have no result: the
    # capture's notes say why (a part of the run it ran out of time for,
    # content it did not check).
    short = [p for p in axe if _axe_results(p) < n]
    unnarrowed = _no_narrow(pages)
    out = []
    for layer, status, note in LAYERS:
        if layer == "static-dom" and pages and not read:
            # No page could be read: no rule ran on anything (R3A-5).
            status, note = "skipped", NOTHING_READ_LAYER_NOTE
        if layer == "rendered" and (axe or reflow):
            full = (len(axe) == len(read) and len(reflow) == len(read)
                    and not short and not unnarrowed)
            status = "executed" if full else "partial"
            parts = []
            if axe and len(_from_snapshot(axe)) == len(axe):
                # A re-run: axe-core ran when the snapshot was captured,
                # not in this run (R1B-4).
                parts.append(
                    f"the snapshot records what axe-core {_axe_versions(axe)} "
                    f"found in the browser when it was captured, on "
                    f"{len(axe)} of {len(read)} page(s), for the {n} WCAG "
                    "A/AA rules Bellbriar does not implement itself "
                    f"(contrast, target size and {n - 2} more)"
                    + (f", though not for every rule on {len(short)} of them"
                       if short else ""))
            elif axe:
                parts.append(
                    f"axe-core {_axe_versions(axe)} checked {len(axe)} of "
                    f"{len(read)} page(s) in the browser, for the {n} WCAG "
                    "A/AA rules Bellbriar does not implement itself "
                    f"(contrast, target size and {n - 2} more)"
                    + (f", though not every rule on {len(short)} of them "
                       "(each page's capture notes say why)" if short else ""))
            if reflow:
                parts.append(f"Bellbriar checked reflow at 320 CSS pixels "
                             f"on {len(reflow)} of {len(read)}")
            if unnarrowed:
                parts.append(f"what {len(unnarrowed)} of them hide at 320 CSS "
                             "pixels was not recorded, so their rules ran "
                             "with what they hide at the capture's own width "
                             "only (each page's capture notes say why)")
            note = "; ".join(parts) + RENDERED_LAYER_ENDING
        out.append({"layer": layer, "status": status, "note": note})
    return out


def coverage_sentence(pages) -> str:
    """COVERAGE_SENTENCE, or, when rendered checks ran, the sentence that
    says which, and on how many of the run's pages; NOTHING_READ_SENTENCE
    when no page could be read."""
    read, axe, reflow = _rendered_pages(pages)
    if pages and not read:
        return NOTHING_READ_SENTENCE
    if not (axe or reflow):
        return COVERAGE_SENTENCE
    n = len(RENDERED_CHECKS) - 1
    what = []
    if axe:
        when = ("checked in the browser when the snapshot was captured"
                if len(_from_snapshot(axe)) == len(axe) else
                "checks in the browser")
        # Pages where some of them have no result say so here too, not
        # only in the layer record (H6-6); and why on a page aria-hidden
        # at its root, which a re-run of a snapshot records nowhere else
        # (R5I-12).
        short = [p for p in axe if _axe_results(p) < n]
        hidden = [p for p in short if getattr(p, "axe_unread", "")]
        why = ([f"on {len(hidden)} of them aria-hidden=\"true\" on the "
                "page's <html> or <body> made axe-core skip what it takes as "
                "hidden"] if hidden else []) + (
            [] if len(_from_snapshot(axe)) == len(axe)
            else ["each page's capture notes say why"])
        what.append(f"the {n} rules axe-core {_axe_versions(axe)} {when} "
                    f"(contrast, target size and {n - 2} more "
                    f"WCAG A/AA rules){_on(axe, read)}"
                    + (f", though not every one of them on {len(short)} of "
                       "those pages" + (f" ({'; '.join(why)})" if why else "")
                       if short else ""))
    if reflow:
        what.append(f"reflow at 320 CSS pixels{_on(reflow, read)}")
    # axe-core's scrollable-region-focusable (bb-scrollable-region) is the
    # one part of keyboard operability a rendered run checks (H6-24).
    missing = ["Keyboard operability" + (
        " (beyond whether scrollable regions can take focus)" if axe else ""),
        "focus visibility"]
    if not axe:
        missing.append("contrast")
    if not reflow:
        missing.append("reflow")
    unnarrowed = _no_narrow(pages)
    if unnarrowed:
        missing.append(f"what {len(unnarrowed)} of its pages hide at 320 CSS "
                       "pixels")
    missing += ["screen-reader announcements", "content adequacy"]
    return RENDERED_COVERAGE_SENTENCE.format(
        what=" and ".join(what),
        missing=", ".join(missing[:-1]) + ", and " + missing[-1])


def load_rulebook(path: str | Path | None = None) -> dict:
    if path is not None:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    with resources.files("bellbriar_harness").joinpath("rulebook.json").open(
            "r", encoding="utf-8") as fh:
        return json.load(fh)


def tool_record(browser: bool = False, snapshot_axe: str = "",
                snapshot_browser: str = "") -> dict:
    """What made a run, as reports and bundles record it (P5-04): the
    harness, the Python it ran on, and the libraries that decide verdicts —
    the HTML parser (justhtml), the tree and selector libraries
    (beautifulsoup4, soupsieve) and the XML parser (expat, for XHTML) —
    and, when a browser captured pages, Playwright and the axe-core the
    harness ships. Each page's capture record names its own Chromium and
    axe-core versions. A library that cannot be found is null. A re-run of
    a snapshot records, as `from_snapshot`, the axe-core whose results the
    snapshot holds (`snapshot_axe`): it decided verdicts without running
    (R1B-4); and the Chromium that captured it (`snapshot_browser`,
    L53)."""
    import platform
    import pyexpat
    from importlib.metadata import PackageNotFoundError, version

    def of(name: str):
        try:
            return version(name)
        except PackageNotFoundError:
            return None
    libraries = {
        "justhtml": of("justhtml"),
        "beautifulsoup4": of("beautifulsoup4"),
        "soupsieve": of("soupsieve"),
        "expat": ".".join(map(str, pyexpat.version_info)),
    }
    if browser:
        from .axe import AXE_VERSION
        libraries["playwright"] = of("playwright")
        libraries["axe-core"] = AXE_VERSION
    tool = {"name": "bellbriar-harness", "version": __version__,
            "python": platform.python_version(), "libraries": libraries}
    held = {name: value for name, value in (("axe-core", snapshot_axe),
                                            ("chromium", snapshot_browser))
            if value}
    if held and not browser:
        tool["from_snapshot"] = held
    return tool


def run_header(rulebook: dict, browser: bool = False, pages=()) -> dict:
    """The fields every run record starts with: the tool (tool_record),
    the rulebook's version and digest, and whether it is the rulebook this
    harness ships (shown to the person running it; a verifier compares the
    digest itself)."""
    digest = rulebook_digest(rulebook)
    snap = _from_snapshot(pages)
    captured = " and ".join(sorted({p.capture_browser for p in pages
                                   if getattr(p, "capture_browser", "")}))
    return {"tool": tool_record(browser, _axe_versions(snap) if snap else "",
                                captured),
            "rulebook_version": rulebook.get("rulebook_version"),
            "rulebook_sha256": digest,
            "rulebook_bundled": digest == bundled_rulebook_digest()}


#: What a fail from a static rule means (docs/MEASUREMENT-AND-EVIDENCE-GUIDE,
#: "Which fails are violations"). Only "sc" fails are success-criterion
#: violations; every implemented static rule must declare one of these.
VERDICT_BASES = ("sc", "policy", "heuristic", "best-practice", "review")

#: A FAIL means WCAG is violated, or probably is (`sc`, `heuristic`). A rule
#: stricter than WCAG (`policy`) or about a pattern WCAG does not require
#: (`best-practice`) never FAILs: its findings are reported for review, with
#: the reason in the words customer reports use, and never count against
#: the gate, "Tier-1 clean", the score or the signed record. `--strict`
#: can still fail a build on them (cli.STRICT_MIN_IMPACT).
NOT_FAILURE_BASES = ("policy", "best-practice")
#: Bases whose rules never FAIL: the two above, and `review` (the rule only
#: asks for review). They are reported, never scored: a rule that cannot
#: fail would otherwise count as a free pass in the pass rate.
NEVER_FAIL_BASES = NOT_FAILURE_BASES + ("review",)
PLED_NOTE = "pled in complaints; not a WCAG failure on its own"
BEST_PRACTICE_NOTE = "a best practice; not a WCAG failure on its own"
#: A policy rule for a WCAG 2.2 criterion: a failure of that criterion, but
#: beyond this rulebook's target (WCAG 2.1 AA), so reported for review.
WCAG22_NOTE = ("a WCAG 2.2 criterion, beyond this rulebook's WCAG 2.1 AA "
               "target; not a WCAG 2.1 failure")


def _review_note(rule: dict) -> str:
    """The note a finding of a rule that never fails carries."""
    if rule.get("wcag_version") == "2.2":
        return WCAG22_NOTE
    return PLED_NOTE if rule.get("pled_pattern") else BEST_PRACTICE_NOTE


def strict_gated(rule: dict) -> bool:
    """Does --strict count this rule's review findings (at moderate impact
    or above, cli.STRICT_MIN_IMPACT)? Those of rules that are not WCAG
    failures on their own (policy, best-practice), and of pled rules that
    can fail (sc, heuristic), whose moderate reviews are pled patterns: a
    missing or broken skip link where a main landmark stands in, a form
    field named only by its placeholder. Every review a report marks "pled
    in complaints" or "a best practice".

    So a pled sc or heuristic rule reports any other review at minor impact
    (an unverifiable lang subtag, a dangling aria-describedby): --strict
    must not fail a build on what the report does not call pled."""
    basis = rule.get("verdict_basis")
    if rule.get("wcag_version") == "2.2":
        # Beyond this rulebook's WCAG 2.1 AA target: reported, never gated,
        # --strict or not (target size).
        return False
    return basis in NOT_FAILURE_BASES or (basis in ("sc", "heuristic")
                                          and bool(rule.get("pled_pattern")))


def verdict_basis(rulebook: dict) -> dict[str, str]:
    return {r["id"]: r.get("verdict_basis", "")
            for r in rulebook.get("rules", [])}


#: The impacts in order, least first.
_IMPACTS = (MINOR, MODERATE, SERIOUS, BLOCKER)


def _not_failures(result, note: str, cap: str | None = None) -> None:
    """Hold a policy or best-practice rule to its basis, whatever its check
    emitted, and say why each finding is not a failure. `cap`: the
    highest impact a finding keeps (a best practice is no blocker, whatever
    axe-core called it: R5G-10)."""
    for f in result.findings:
        if f.verdict == FAIL:
            f.verdict = NEEDS_REVIEW
        if cap and f.impact in _IMPACTS and \
                _IMPACTS.index(f.impact) > _IMPACTS.index(cap):
            f.impact = cap
        if note not in f.message:
            msg = f.message.rstrip()
            msg = msg[:-1] if msg.endswith(".") else msg
            f.message = f"{msg} — {note}."


#: The layers whose implemented rules run inside run_page: Bellbriar's own
#: checks on the markup, and the checks that read a rendered capture's
#: records (checks_rendered).
CHECKED_LAYERS = ("static-dom", "rendered")


def _meaning(rule: dict) -> dict:
    """What a rule is and what its verdicts mean, as the harness reads each
    field, so a rule that leaves a field at its default (no pled_pattern, no
    sc, no Understanding link) means what one that writes it does (R3C-8):
    its verdict basis, whether its findings are pled patterns, whether it
    is a WCAG 2.2 criterion, the criteria it cites, its name, its
    Understanding document, its layer, and the engine and axe-core rule
    that decide it."""
    sc = rule.get("sc") or []
    return {
        "verdict_basis": rule.get("verdict_basis"),
        "pled_pattern": bool(rule.get("pled_pattern")),
        "wcag_version": rule.get("wcag_version") == "2.2",
        # (A value of another type is reported by validate_rulebook.)
        "sc": list(sc) if isinstance(sc, list) else sc,
        "name": rule.get("name") or "",
        "understanding": rule.get("understanding") or None,
        "layer": rule.get("layer"),
        "engine": rule.get("engine") or "bellbriar",
        "axe_rule": rule.get("axe_rule") or None,
    }


def validate_rulebook(rulebook: dict) -> None:
    from .judged import JUDGED  # local import: judged pulls no engine code
    # Its shape first: an object whose rules are objects, each id once
    # (R3D-9): a rule listed twice would let the last entry decide its
    # tier, weight and gate unseen.
    rules = rulebook.get("rules") if isinstance(rulebook, dict) else None
    if not isinstance(rules, list) or not all(isinstance(r, dict)
                                              for r in rules):
        raise RuntimeError("The rulebook cannot be used: it must be a JSON "
                           "object whose \"rules\" is a list of objects, as "
                           "in the bundled rulebook.json")
    seen: set = set()
    again: set = set()
    for r in rules:
        rid = str(r.get("id"))
        if rid in seen:
            again.add(rid)
        seen.add(rid)
    twice = sorted(again)
    if twice:
        raise RuntimeError("The rulebook cannot be used: each rule may be "
                           f"listed once, and these are listed again: "
                           f"{', '.join(twice[:12])}")
    static_impl = {r["id"] for r in rulebook["rules"]
                   if r.get("status") == "implemented"
                   and r.get("layer") == "static-dom"}
    rendered_impl = {r["id"] for r in rulebook["rules"]
                     if r.get("status") == "implemented"
                     and r.get("layer") == "rendered"}
    no_basis = sorted(r["id"] for r in rulebook["rules"]
                      if r.get("status") == "implemented"
                      and r.get("layer") in CHECKED_LAYERS
                      and r.get("verdict_basis") not in VERDICT_BASES)
    judge_impl = {r["id"] for r in rulebook["rules"]
                  if r.get("status") == "implemented"
                  and r.get("layer") == "judge"}
    problems = []
    if static_impl - set(CHECKS):
        problems.append(f"no check fn for: {sorted(static_impl - set(CHECKS))}")
    if set(CHECKS) - static_impl:
        problems.append(f"no rulebook entry for: {sorted(set(CHECKS) - static_impl)}")
    if rendered_impl - set(RENDERED_CHECKS):
        problems.append(f"no rendered check for: "
                        f"{sorted(rendered_impl - set(RENDERED_CHECKS))}")
    if set(RENDERED_CHECKS) - rendered_impl:
        problems.append(f"no rulebook entry for rendered: "
                        f"{sorted(set(RENDERED_CHECKS) - rendered_impl)}")
    if judge_impl - set(JUDGED):
        problems.append(f"no judged rule for: {sorted(judge_impl - set(JUDGED))}")
    if set(JUDGED) - judge_impl:
        problems.append(f"no rulebook entry for judged: {sorted(set(JUDGED) - judge_impl)}")
    if no_basis:
        problems.append(f"missing or invalid verdict_basis (one of "
                        f"{', '.join(VERDICT_BASES)}) for: {no_basis}")
    # The fields the harness reads from every rule, of the types it reads
    # them as (R3A-10): a rule it cannot read the same way cannot be scored,
    # recorded or reported.
    for r in rulebook["rules"]:
        rid = r.get("id")
        if not isinstance(rid, str) or not rid:
            problems.append(f"a rule has no id: {str(r)[:60]}")
            continue
        tier = r.get("tier", 3)
        if isinstance(tier, bool) or not isinstance(tier, int) \
                or not 0 <= tier <= 3:
            problems.append(f"{rid}: tier must be 0, 1, 2 or 3, not "
                            f"{tier!r}")
        sc = r.get("sc", [])
        if not isinstance(sc, list) or not all(isinstance(c, str)
                                               for c in sc):
            problems.append(f"{rid}: sc must be a list of criteria such as "
                            f"[\"1.1.1\"], not {sc!r}")
        if not isinstance(r.get("name", ""), str):
            problems.append(f"{rid}: name must be text")
        url = r.get("understanding")
        if url not in (None, "") and not (isinstance(url, str)
                                          and url.startswith("https://")):
            problems.append(f"{rid}: understanding must be an https:// "
                            "address")
    # A rulebook may change tiers and weights; it cannot change what a
    # check's verdict means. The bases the checks implement, which of their
    # findings are pled patterns (the note a report carries, and what
    # --strict gates), and what the rule is — its name, the criteria its
    # FAIL is a failure of, its Understanding document, its layer and the
    # engine that decides it, which reports print beside its findings
    # (R3A-10, R3B-7) — are the ones the bundled rulebook declares: an
    # older or edited rulebook that says otherwise would be recorded under
    # its own version while the checks behaved as this one.
    bundled = load_rulebook()
    implements = {r["id"]: _meaning(r) for r in bundled["rules"]
                  if r.get("status") == "implemented"
                  and r.get("layer") in CHECKED_LAYERS}
    drift = []
    for r in rulebook["rules"]:
        rid = r.get("id")
        if rid in implements and r.get("status") == "implemented" \
                and r.get("layer") in CHECKED_LAYERS:
            mine = _meaning(r)
            fields = [k for k in mine if mine[k] != implements[rid][k]]
            if fields:
                drift.append(f"{rid} ({', '.join(fields)})")
    if drift:
        shown = "; ".join(drift[:12]) + (f"; and {len(drift) - 12} more"
                                         if len(drift) > 12 else "")
        problems.append(
            f"these rules say something other than what these checks "
            f"implement (the bundled rulebook "
            f"{bundled.get('rulebook_version')}), in the fields named: "
            f"{shown}. Start from the bundled rulebook.json and change only "
            f"tiers and weights")
    # The weight each tier carries in the pass rate (scoring._weights).
    weights = rulebook.get("tier_weights")
    if not (isinstance(weights, dict)
            and sorted(weights) == ["0", "1", "2", "3"]
            and all(isinstance(w, int) and not isinstance(w, bool)
                    and w >= 0 for w in weights.values())):
        try:
            given = json.dumps(weights)[:80]
        except (TypeError, ValueError):
            given = "a value JSON cannot hold"
        problems.append(
            "tier_weights must give each tier, \"0\" to \"3\", a whole "
            "number of 0 or more, written without a decimal point, such as "
            "{\"0\": 0, \"1\": 5, \"2\": 2, \"3\": 1}, not " + given)
    version = rulebook.get("rulebook_version")
    if version is not None and not isinstance(version, str):
        # Evidence bundles bind the version into signed statements, whose
        # values are strings or null (docs/CANONICALIZATION.md §5).
        raise RuntimeError(f'rulebook_version must be a string such as '
                           f'"0.2.0", not {version!r}')
    try:
        rulebook_digest(rulebook)
    except (ValueError, TypeError) as exc:
        # Reports and bundles record the rulebook's digest (P1-08): a
        # rulebook no canonical form holds cannot be identified.
        raise RuntimeError(f"the rulebook cannot be identified by a digest: "
                           f"{exc}") from None
    if problems:
        raise RuntimeError("The rulebook cannot be used with these checks: "
                           + "; ".join(problems))


def run_page(html: str | bytes, path: str, rulebook: dict,
             provenance_attr: str | None = None,
             reader: str | None = None,
             snapshot: bool = False) -> PageResult:
    """Run every static rule over one page.

    `html` is the page's text, or a file's bytes (decoded as a browser
    decodes them). `provenance_attr` is the attribute the harness's own
    rendered capture wrote first/third-party attribution into. Leave it None
    for files and server HTML: attribution found in such markup was written
    by the page, and a page must not be able to move its own failures out of
    the score. `reader` says what the markup is: "html" (a page's own
    markup), "dom" (a browser's serialization of a live DOM: a rendered
    capture, instrumented or not) or "xml"; by default from the path and
    `provenance_attr` (PageContext.parse). `snapshot`: `html` is a saved
    snapshot re-run under `provenance_attr`, whose capture record
    (model.capture_attr) must name this release's marks, or no rule runs
    on it (L106); the Chromium it names is the page's capture_browser
    (L53).
    """
    from . import budget
    page = PageResult(path=path)
    clock = budget.begin()
    try:
        done = _run_page(page, html, path, rulebook, provenance_attr,
                         reader, snapshot)
        # Work after the last look at the clock counts too: a page whose
        # analysis ran past its budget is stopped, whenever that was seen.
        budget.check()
        return done
    except budget.Exceeded as exc:
        # Stopped: what ran is not kept, as a page cut short is not one
        # whose rules all ran, and the run is incomplete, as it is for a
        # page that could not be read (S5-4).
        page.results = []
        page.evaluable = False
        page.parse_error = str(exc)
        page.not_evaluable_reason = exc.reason
        return page
    finally:
        budget.end(clock)


def _run_page(page, html, path, rulebook, provenance_attr, reader,
              snapshot) -> PageResult:
    """run_page, inside the page's analysis budget (budget.py)."""
    try:
        ctx = PageContext.parse(html, path=path,
                                provenance_attr=provenance_attr,
                                reader=reader)
    except Exception as exc:                            # noqa: BLE001
        # One page the harness cannot read must not stop a site run, and
        # must not read as a pass: it is reported, and the run exits 2.
        page.parse_error = error_text(exc)
        page.evaluable = False
        page.not_evaluable_reason = (
            f"the harness could not parse this page ({page.parse_error}); "
            "no rule ran on it, and that is not a pass")
        return page
    if snapshot and provenance_attr:
        refused = _snapshot_refused(ctx, provenance_attr, page)
        if refused:
            page.parse_error = refused
            page.evaluable = False
            page.not_evaluable_reason = (
                f"{refused}: no rule ran on it, and that is not a pass; "
                "capture the page again")
            return page
    token = PROVENANCE_ATTR.set(provenance_attr)
    page_token = CURRENT_PAGE.set(ctx)
    try:
        narrow = _took_narrow_record(ctx)
        page.narrow = narrow
        # Where the narrow record hides nothing the capture's own does not,
        # and the reverse, the rules read the same page twice: once is
        # enough (QR-12).
        differs = narrow and _views_differ(ctx)
        unconfirmed = _unconfirmed_check(ctx) if differs else None
        for rule_id, fn in CHECKS.items():
            result = _run_check(rule_id, fn, ctx)
            if differs:
                # The same rule with what the page hides at phone width
                # (L24): a control shown, or named, only there.
                view = HIDDEN_VIEW.set("narrow")
                try:
                    result = merge_views(result, _run_check(rule_id, fn, ctx),
                                         unconfirmed)
                finally:
                    HIDDEN_VIEW.reset(view)
                    ctx.narrow_elements.clear()
            page.results.append(result)
        for rule_id, fn in RENDERED_CHECKS.items():
            result = _run_check(rule_id, fn, ctx)
            # None: a rendered rule on a page no browser captured with its
            # records (a file, server HTML). Not evaluated, so no result:
            # neither a pass nor "not applicable" (layer_records says so).
            if result is not None:
                page.results.append(result)
        try:
            reason = detect_app_shell(ctx)
        except Exception as exc:                        # noqa: BLE001
            reason = ""
            page.results.append(RuleResult(rule_id="(app-shell check)",
                                           applicable=False,
                                           errored=error_text(exc)))
        try:
            from .checks_rendered import ROOT_HIDDEN_NOTE, axe_skipped, axe_state
            run_record = axe_state(ctx)[0]
            page.axe_version = run_record["version"] if run_record else ""
            # Why some of axe-core's rules are not evaluated on the page,
            # for its capture notes (R5G-1, R5I-7).
            page.axe_unread = (ROOT_HIDDEN_NOTE if run_record
                               and axe_skipped(ctx) else "")
        except Exception:                               # noqa: BLE001
            page.axe_version = ""
    finally:
        CURRENT_PAGE.reset(page_token)
        PROVENANCE_ATTR.reset(token)
    rules = {r.get("id"): r for r in (rulebook or {}).get("rules", [])}
    for result in page.results:
        meta = rules.get(result.rule_id) or {}
        if meta.get("verdict_basis") in NOT_FAILURE_BASES:
            _not_failures(result, _review_note(meta),
                          MODERATE if meta.get("verdict_basis")
                          == "best-practice" else None)
        elif meta.get("verdict_basis") in NEVER_FAIL_BASES:
            for f in result.findings:        # `review`: asks, never fails
                if f.verdict == FAIL:
                    f.verdict = NEEDS_REVIEW
    if reason:
        page.evaluable = False
        page.not_evaluable_reason = reason
    return page


def _snapshot_refused(ctx, provenance_attr: str, page) -> str:
    """Why a saved snapshot is not read under `provenance_attr`: its root
    element holds no capture record of the marks this release reads
    (model.capture_attr, MARKS_VERSION); "" when it does, the Chromium the
    record names then being the page's capture_browser (L53, L106)."""
    from .model import MARKS_VERSION, capture_attr
    root = ctx.soup.find(True)
    value = root.get(capture_attr(provenance_attr)) if root is not None \
        else None
    try:
        record = json.loads(value) if isinstance(value, str) else None
    except ValueError:
        record = None
    if not isinstance(record, dict):
        return ("the snapshot holds no capture record under the name "
                "given (--provenance-attr): a build before 1.0 captured "
                "it, or the name is not the one its run recorded "
                "(fetch.provenance_attr)")
    marks = record.get("marks")
    if type(marks) is not int or marks != MARKS_VERSION:
        return (f"the snapshot was captured with marks of version "
                f"{marks!r}, and this release reads version "
                f"{MARKS_VERSION}")
    browser = record.get("browser")
    page.capture_browser = browser if isinstance(browser, str) else ""
    return ""


def _run_check(rule_id: str, fn, ctx) -> RuleResult | None:
    from .budget import check
    check()
    try:
        return fn(ctx)
    except Exception as exc:                            # noqa: BLE001
        # A rule that raises is errored, never passed: not applicable for
        # the rates, and reported (P2-12).
        return RuleResult(rule_id=rule_id, applicable=False,
                          errored=error_text(exc))


def _took_narrow_record(ctx) -> bool:
    """Did the capture record what the page hides at its narrow viewport
    too (model.narrow_hidden_attr)? Only under the capture's own secret."""
    from bs4.element import Tag
    attr = ctx.provenance_attr
    root = ctx.soup.find("html") if attr else None
    return isinstance(root, Tag) and \
        root.get(narrow_hidden_attr(attr)) == "recorded"


def _views_differ(ctx) -> bool:
    """Does the narrow record hide or show anything differently from the
    capture's own (model.hidden_attr, model.narrow_hidden_attr)? Where it
    does not, the rules find the same with either."""
    attr = ctx.provenance_attr
    main, narrow = hidden_attr(attr), narrow_hidden_attr(attr)
    for el in ctx.soup.find_all(lambda t: t.has_attr(main)
                                or t.has_attr(narrow)):
        if el.get(main) != el.get(narrow):
            return True
    return False


def _unconfirmed_check(ctx):
    """A test for merge_views: is a finding the narrow record makes about
    something the page changed after the capture (model.narrow_changed_attr)?
    The snapshot shows that as it was at the capture's own width. It is,
    when the page changed the finding's element or anything it holds, or
    the element sits inside one whose own attributes changed, or that was
    moved; a finding about the page, when the page changed anything. None
    when the page changed nothing."""
    from bs4.element import Tag
    name = narrow_changed_attr(ctx.provenance_attr)
    if ctx.soup.find(attrs={name: True}) is None:
        return None

    def unconfirmed(f) -> bool:
        el = ctx.narrow_elements.get(id(f))
        if not isinstance(el, Tag):
            return True              # about the page: something changed
        if el.has_attr(name) or el.find(attrs={name: True}) is not None:
            return True
        node = el.parent
        while isinstance(node, Tag):
            if node.get(name) == "self":
                return True
            node = node.parent
        return False
    return unconfirmed


#: Appended to a finding only the narrow record shows (merge_views).
NARROW_NOTE = "Found with the page 320 CSS pixels wide, as on a phone."
#: Appended to such a finding when the page changed what it is about after
#: the capture, which the snapshot cannot show (merge_views).
UNCONFIRMED_NOTE = ("The page changed this part of itself at that width, "
                    "which the capture does not show, so this could not be "
                    "confirmed: check it at that width.")


def _at_narrow(f, unconfirmed: bool = False):
    import dataclasses
    msg = f.message.rstrip()
    if not unconfirmed:
        return dataclasses.replace(f, message=f"{msg} ({NARROW_NOTE})")
    return dataclasses.replace(
        f, verdict=NEEDS_REVIEW, impact=MINOR,
        message=f"{msg} ({NARROW_NOTE} {UNCONFIRMED_NOTE})")


def _finding_key(f) -> tuple:
    """What a finding is about, as findings show it: its element, or, for
    a finding about the page, what it says. Its element's identity too
    (Finding.about), the same in both views: findings withheld for quoting
    the run's password show the same snippet and locator, REDACTED, on any
    element (R5J-5). A finding about the page whose message is withheld
    keeps its verdict and impact apart: those are what it still shows."""
    from .redact import WITHHELD_MESSAGE
    about_page = f.selector is None and f.line is None and not f.snippet
    said = f.message if about_page else ""
    if about_page and str(f.message).startswith(WITHHELD_MESSAGE):
        said = (WITHHELD_MESSAGE, f.verdict, f.impact)
    return (f.line, f.snippet, tuple(f.selector or ()),
            getattr(f, "about", "") or "", said)


def merge_views(main: RuleResult, narrow: RuleResult,
                unconfirmed=None) -> RuleResult:
    """One rule's result on a page evaluated with each record of what it
    hides (L24): applicable where either is; the findings of the capture's
    own viewport, and each one the narrow record adds, marked as such
    (NARROW_NOTE). Where both report the same thing, the main finding
    stands, unless only the narrow one FAILs: the element fails on a
    phone. A finding the narrow record adds about something the page
    changed after the capture (`unconfirmed`, _unconfirmed_check) is a
    minor review: the snapshot shows it as it was at the capture's own
    width (UNCONFIRMED_NOTE).

    A rule that raised under the capture's own record is errored: its
    result is unknown. One that raised only under the narrow record is
    errored too, and keeps what the capture's own record found, which it
    still reports: where that is a failure the rule fails on the page
    whatever the narrow record would have added (QR2-1); otherwise its
    result there is unknown, and it is no pass."""
    if main.errored:
        return main
    if narrow.errored:
        return RuleResult(main.rule_id, applicable=main.failed,
                          findings=list(main.findings),
                          errored=f"{narrow.errored} (with the page 320 CSS "
                                  "pixels wide)")
    out = RuleResult(main.rule_id, applicable=main.applicable or
                     narrow.applicable, findings=list(main.findings))
    at: dict = {}
    for i, f in enumerate(out.findings):
        at.setdefault(_finding_key(f), i)
    for f in narrow.findings:
        key = _finding_key(f)
        i = at.get(key)
        if i is not None and not (f.verdict == FAIL
                                  and out.findings[i].verdict != FAIL):
            continue                 # the capture's own finding stands
        g = _at_narrow(f, bool(unconfirmed and unconfirmed(f)))
        if i is None:
            at[key] = len(out.findings)
            out.findings.append(g)
        elif g.verdict == FAIL:
            out.findings[i] = g
    return out


def error_text(exc: BaseException) -> str:
    """An exception as one recordable line: its type and the start of its
    message, home directories replaced (redact.redact_local_paths). A rule
    that raises may quote the page in its message, so the run's secrets
    are replaced in it before it is cut, and one that holds the run's
    --http-user password is withheld (redact.holds_password)."""
    from .redact import holds_password, redact_local_paths, scrub_secrets
    text = " ".join(str(exc).split())
    if holds_password(text):
        text = "(message withheld: it held the run's --http-user password)"
    text = scrub_secrets(text)
    text = f"{type(exc).__name__}: {text}" if text else type(exc).__name__
    return redact_local_paths(text[:300])


def run_paths(paths: list[Path], rulebook: dict | None = None,
              provenance_attr: str | None = None,
              names: list[str] | None = None,
              reader: str | None = None) -> dict:
    """Evaluate local files. `provenance_attr` is only for re-running a
    snapshot the harness itself captured: pass the name recorded in that
    run's fetch block. Never derive it from the files themselves. `reader`
    is for re-running a snapshot too: pass the fetch block's `reader`; by
    default each file is read by its name (PageContext.parse). `names`
    are the page names to report (bundle.recorded_path); by default each
    path as given."""
    rulebook = rulebook or load_rulebook()
    validate_rulebook(rulebook)
    pages = []
    for i, p in enumerate(paths):
        # Bytes: the page is decoded as Chromium decodes a local file
        # (byte-order mark, <meta charset>, else UTF-8 when it is UTF-8).
        data = Path(p).read_bytes()
        page = run_page(data, names[i] if names else str(p), rulebook,
                        provenance_attr=provenance_attr, reader=reader,
                        snapshot=provenance_attr is not None)
        page.input_digest = (hashlib.sha256(data).hexdigest(), len(data))
        # A file holds no browser: axe-core results on it were recorded
        # when the snapshot was captured.
        page.axe_from_snapshot = bool(page.axe_version)
        pages.append(page)
    return {
        **run_header(rulebook, pages=pages),
        "source": "files",
        # A file run renders nothing, but a snapshot re-run with its
        # --provenance-attr carries the capture's axe-core records.
        "layers": layer_records(pages),
        "coverage_note": coverage_sentence(pages),
        "pages": pages,
        "rulebook": rulebook,
    }
