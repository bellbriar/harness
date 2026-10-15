"""Judged (adequacy) checks — Layer 2.

Not in 1.0 (decision D3, the ship list's L4): nothing on the command line
reaches this code, which stays for when a calibrated judge exists. Open by
design: rubrics and the runner are public so a benchmark is reproducible
with any model.

STATUS: no judge provider is calibrated. There is no human-labeled golden
set, no calibration code, and no judge-versus-human agreement measurement,
and there is no hosted judge. `calibrated` is therefore False for every
provider, and every judged number carries the uncalibrated disclosure
below. Calibration is roadmap work; do not describe it in the present
tense anywhere.

Honesty rules enforced here:
- A judge NEVER overrides a deterministic result; items already failed
  deterministically (bb-alt-junk) are skipped, not re-graded.
- Judged results are scored on a SEPARATE track from deterministic results
  and are always labeled with provider, model, and calibration status.
  Mixing calibrated and uncalibrated judgments into one headline number is
  scoring theater; this module refuses to do it.
- Provider errors degrade to needs_review, never to pass.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from collections import Counter
from pathlib import Path
from dataclasses import dataclass, field

from .accname import static_accname, subtree_text
from .checks_static import GENERIC_LINK_RE, JUNK_ALT_RE, PageContext
from .judge import JudgeProvider, JudgeResult
from .model import (FAIL, NEEDS_REVIEW, MODERATE, PROVENANCE_ATTR, SERIOUS,
                    Finding, RuleResult)
from .redact import redact_local_paths

RUBRIC_VERSION = "0.1.0"

# Open rubrics, grounded in the W3C Understanding documents cited in the
# rulebook. Each requires a strict JSON verdict.
_JSON_INSTRUCTION = (
    'Respond with ONLY a JSON object, no prose, no code fences: '
    '{"verdict": "pass" | "fail" | "needs_review", "rationale": "<one sentence>"}'
)

RUBRICS: dict[str, str] = {
    "bb-alt-quality": (
        "You are grading a text alternative under WCAG 2.1 SC 1.1.1 "
        "(Understanding: non-text content). An alt text passes when it serves "
        "the equivalent purpose of the image in its context: for functional "
        "images (inside a link or button), it names the destination or action; "
        "for informative images, it conveys the information; it is not a "
        "filename, not redundant boilerplate like 'image of', and not a "
        "keyword dump. Mark needs_review if the image's purpose cannot be "
        "inferred from the provided context. " + _JSON_INSTRUCTION
    ),
    "bb-link-purpose": (
        "You are grading link text under WCAG 2.1 SC 2.4.4 (Understanding: "
        "link purpose in context). The link passes if its purpose can be "
        "determined from the accessible name together with its programmatic "
        "context (same sentence, paragraph, list item, or table cell). "
        "Generic text like 'click here' passes ONLY if that surrounding "
        "context makes the destination unambiguous. " + _JSON_INSTRUCTION
    ),
    "bb-headings-labels-quality": (
        "You are grading headings under WCAG 2.1 SC 2.4.6 (Understanding: "
        "headings and labels). The set of headings passes if each heading "
        "describes the topic or purpose of its section; vague or duplicated "
        "headings that would not orient a screen-reader user scanning by "
        "headings fail. " + _JSON_INSTRUCTION
    ),
}


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------

@dataclass
class ProviderInfo:
    name: str
    model: str
    calibrated: bool = False
    calibration_id: str | None = None


class AnthropicJudge:
    """Bring-your-own-model provider via the Anthropic Messages API.

    Requires ANTHROPIC_API_KEY. Uncalibrated by definition: results are
    labeled calibrated=false and never mixed into deterministic scores.
    """

    API = "https://api.anthropic.com/v1/messages"

    def __init__(self, model: str = "claude-sonnet-4-6",
                 api_key: str | None = None, timeout: int = 60):
        self.name = "anthropic"
        self.model = model
        self.timeout = timeout
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")

    def judge(self, rubric_id: str, payload: dict) -> JudgeResult:
        if not self.api_key:
            return JudgeResult(rubric_id, "needs_review",
                               "ANTHROPIC_API_KEY not set; not judged.",
                               self.model, error=True)
        body = json.dumps({
            "model": self.model,
            "max_tokens": 300,
            "messages": [{
                "role": "user",
                "content": (RUBRICS[rubric_id] + "\n\nITEM TO GRADE:\n"
                            + json.dumps(payload, ensure_ascii=False)),
            }],
        }).encode("utf-8")
        req = urllib.request.Request(
            self.API, data=body, method="POST",
            headers={"content-type": "application/json",
                     "x-api-key": self.api_key,
                     "anthropic-version": "2023-06-01"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            text = "".join(b.get("text", "") for b in data.get("content", [])
                           if b.get("type") == "text")
            return _parse_verdict(rubric_id, text, self.model)
        except Exception as exc:  # noqa: BLE001 — degrade, never crash a run
            return JudgeResult(rubric_id, "needs_review",
                               f"judge error: {exc}", self.model, error=True)


class HostedJudge:
    """Client for a Bellbriar judge endpoint (metered). POST {base}/v1/judge
    with bearer auth.

    `calibrated` is False and is set here deliberately, not left to
    `getattr(..., False)`. The endpoint returns no calibration field, and
    there is nothing behind it to report: no golden set exists. When
    calibration ships, the server must return a `calibration_id` that names
    a published agreement study, and only then may this flip — a provider
    asserting its own calibration with nothing to point at is worth less
    than an honest False.
    """

    calibrated = False
    calibration_id = None

    def __init__(self, base_url: str, api_key: str, timeout: int = 60):
        self.name = "bellbriar-hosted"
        self.model = "server-configured"
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def judge(self, rubric_id: str, payload: dict) -> JudgeResult:
        body = json.dumps({"rubric_id": rubric_id,
                           "rubric_version": RUBRIC_VERSION,
                           "payload": payload}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/v1/judge", data=body, method="POST",
            headers={"content-type": "application/json",
                     "authorization": f"Bearer {self.api_key}"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            # The response enters the signed bundle, so it gets the same
            # contract as any other provider: a known verdict or a provider
            # error, and text fields that are text.
            model = (_clean_text(data.get("model") or "hosted", 120)
                     if isinstance(data, dict) else "hosted")
            return _result_from(rubric_id, data, model)
        except Exception as exc:  # noqa: BLE001
            return JudgeResult(rubric_id, "needs_review",
                               f"hosted judge error: {exc}", "hosted",
                               error=True)


class VotingJudge:
    """n-sample majority vote (spec §7). Ties degrade to needs_review."""

    def __init__(self, inner: JudgeProvider, n: int = 3):
        self.inner = inner
        self.n = max(1, n)
        self.name = f"{inner.name}×{self.n}"
        self.model = getattr(inner, "model", "unknown")

    def judge(self, rubric_id: str, payload: dict) -> JudgeResult:
        all_votes = [self.inner.judge(rubric_id, payload)
                     for _ in range(self.n)]
        votes = [v for v in all_votes if not v.error]
        n_err = len(all_votes) - len(votes)
        if not votes:
            return JudgeResult(rubric_id, "needs_review",
                               f"all {self.n} samples failed: "
                               f"{all_votes[0].rationale if all_votes else ''}",
                               self.model, error=True)
        counts = Counter(v.verdict for v in votes)
        top = counts.most_common()
        if len(top) > 1 and top[0][1] == top[1][1]:
            return JudgeResult(rubric_id, "needs_review",
                               f"no majority across {len(votes)} valid "
                               f"samples ({dict(counts)}).", self.model)
        winner = top[0][0]
        rationale = next(v.rationale for v in votes if v.verdict == winner)
        suffix = f", {n_err} provider error(s)" if n_err else ""
        return JudgeResult(rubric_id, winner,
                           f"[{counts[winner]}/{len(votes)}{suffix}] "
                           f"{rationale}", self.model)


_VERDICTS = ("pass", "fail", "needs_review")
_SURROGATES = re.compile("[\ud800-\udfff]")


def _clean_text(value, limit: int) -> str:
    """Provider-supplied text, fit for the signed bundle: always a string,
    bounded in length, and valid Unicode (a JSON escape such as \\ud800 can
    hand Python a lone surrogate, which has no UTF-8 form)."""
    text = "" if value is None else (value if isinstance(value, str)
                                     else str(value))
    return _SURROGATES.sub("\ufffd", text)[:limit]


def _result_from(rubric_id: str, data, model: str) -> JudgeResult:
    """A provider's decoded JSON answer as a JudgeResult. Anything outside
    the rubric contract is a provider failure, not a judgment of the item."""
    if not isinstance(data, dict):
        return JudgeResult(rubric_id, "needs_review",
                           "provider answered with something other than a "
                           "JSON object", model, error=True)
    verdict = data.get("verdict", "needs_review")
    if not isinstance(verdict, str) or verdict not in _VERDICTS:
        return JudgeResult(rubric_id, "needs_review",
                           f"invalid verdict {_clean_text(verdict, 60)!r} "
                           "from provider", model, error=True)
    return JudgeResult(rubric_id, verdict,
                       _clean_text(data.get("rationale", ""), 400), model)


def _parse_verdict(rubric_id: str, text: str, model: str) -> JudgeResult:
    cleaned = re.sub(r"^```(json)?|```$", "", text.strip(),
                     flags=re.M).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return JudgeResult(rubric_id, "needs_review",
                           f"unparseable judge output: "
                           f"{_clean_text(cleaned, 120)}",
                           model, error=True)
    return _result_from(rubric_id, data, model)


# ---------------------------------------------------------------------------
# Payload extraction (static context; interaction payloads are roadmap)
# ---------------------------------------------------------------------------

def _context_text(el, limit: int = 240) -> str:
    parent = el.parent
    hops = 0
    while parent is not None and hops < 3:
        text = subtree_text(parent)
        if len(text) >= 40:
            return text[:limit]
        parent = parent.parent
        hops += 1
    return (subtree_text(el.parent) if el.parent is not None else "")[:limit]


def extract_alt_items(ctx: PageContext) -> list[dict]:
    items = []
    for img in ctx.soup.find_all("img"):
        alt = " ".join((img.get("alt") or "").split())
        if not alt or JUNK_ALT_RE.search(alt):
            continue  # missing → bb-img-alt; junk → bb-alt-junk (deterministic)
        link = img.find_parent("a")
        items.append({
            "element": "img", "alt": alt,
            "src": (img.get("src") or "")[-80:],
            "functional": link is not None,
            "link_href": (link.get("href") or "")[:120] if link else None,
            "context": _context_text(img),
            "line": getattr(img, "sourceline", None),
        })
    return items


def extract_link_items(ctx: PageContext) -> list[dict]:
    items = []
    for a in ctx.soup.select("a[href]"):
        name = static_accname(a, ctx.soup, ctx.ids)
        if not name or not GENERIC_LINK_RE.match(name):
            continue  # only generic-text links need context grading
        items.append({
            "element": "a", "accessible_name": name,
            "href": (a.get("href") or "")[:160],
            "context": _context_text(a),
            "line": getattr(a, "sourceline", None),
        })
    return items


def extract_heading_items(ctx: PageContext) -> list[dict]:
    heads = []
    for el in ctx.soup.find_all(re.compile(r"^h[1-6]$")):
        text = subtree_text(el)
        if text:
            heads.append({"level": int(el.name[1]), "text": text[:120],
                          "line": getattr(el, "sourceline", None)})
    if not heads:
        return []
    title = ctx.soup.find("title")
    return [{"page_title": (subtree_text(title) if title else "")[:120],
             "headings": heads[:40]}]


JUDGED = {
    "bb-alt-quality": (extract_alt_items, SERIOUS),
    "bb-link-purpose": (extract_link_items, MODERATE),
    "bb-headings-labels-quality": (extract_heading_items, MODERATE),
}


# ---------------------------------------------------------------------------
# Runner + separate scoring track
# ---------------------------------------------------------------------------

@dataclass
class JudgedRun:
    provider: ProviderInfo
    rubric_version: str = RUBRIC_VERSION
    pages: list[dict] = field(default_factory=list)   # per-page results
    #: (page, rule or "(the page)", error text) for each page the track
    #: could not read and each extraction that raised: never a pass, and
    #: the run is incomplete (cli refuses the bundle, exit 2).
    errors: list = field(default_factory=list)

    def summary(self) -> dict:
        """Scoring rule, and the reason for it.

        Every graded item ends in exactly one of four buckets:

            graded = passed + fails + needs_review + provider_errors

        Only ``passed`` and ``fails`` are judgments of the item. A
        ``needs_review`` verdict means the judge looked and declined to
        decide; a ``provider_error`` means the judge never answered at all.
        Neither is evidence that the item is good, so neither may sit in the
        numerator OR the denominator of a pass rate.

            decided   = graded - needs_review - provider_errors
            passed    = decided - fails
            pass_rate = passed / decided,  undefined when decided == 0

        The earlier form (``passed = graded - fails``) counted every
        undecided item as a pass, so a provider that answered nothing
        reported 100%.
        """
        items = graded = fails = reviews = errors = 0
        for page in self.pages:
            for rr in page["results"]:
                items += rr["items"]
                graded += rr["graded"]
                for f in rr["findings"]:
                    if f["verdict"] == FAIL:
                        fails += 1
                    elif f.get("error"):
                        errors += 1
                    else:
                        reviews += 1
        decided = graded - reviews - errors
        passed = decided - fails
        rate = round(passed / decided, 4) if decided > 0 else None

        notes = [
            "Judged results are a separate track from deterministic results "
            "and are only as reliable as the provider.",
            ("Calibrated against the Bellbriar golden set."
             if self.provider.calibrated else
             "UNCALIBRATED provider: no measured agreement with human "
             "experts; treat as advisory."),
        ]
        if errors:
            notes.append(
                f"{errors} of {graded} item(s) were NOT judged because the "
                "provider failed to answer; they are excluded from the pass "
                "rate rather than counted as passes.")
        if rate is None and graded:
            notes.append(
                "NO PASS RATE: no item received a decidable verdict. This is "
                "not a score of zero and it is not a score of 100% — nothing "
                "was measured.")
        return {
            "provider": self.provider.name,
            "model": self.provider.model,
            "calibrated": self.provider.calibrated,
            "calibration_id": self.provider.calibration_id,
            "rubric_version": self.rubric_version,
            "items_extracted": items,
            "items_graded": graded,
            "items_decided": decided,
            "judged_pass_rate": rate,
            "fail_findings": fails,
            "needs_review_findings": reviews,
            "provider_errors": errors,
            "disclosure": " ".join(notes),
        }


def run_judged(paths: list, provider: JudgeProvider,
               max_items_per_rule: int = 25,
               names: list | None = None, reader: str | None = None,
               provenance_attr: str | None = None) -> JudgedRun:
    """Grade adequacy questions on each page with the given provider.

    max_items_per_rule caps provider calls per rule per page (cost control);
    the cap is recorded so truncation is never silent. `names` are the page
    names to record (bundle.recorded_path); by default each path as given.
    `reader` and `provenance_attr` are the static run's (engine.run_paths),
    so both tracks read each page into the same tree.
    """
    # Everything a provider hands back ends up in the signed bundle, and the
    # provider interface is open: text is coerced to text here, once, so no
    # provider can make a bundle that fails to canonicalize.
    cal_id = getattr(provider, "calibration_id", None)
    info = ProviderInfo(
        name=_clean_text(getattr(provider, "name", "unknown"), 120),
        model=_clean_text(getattr(provider, "model", "unknown"), 120),
        calibrated=bool(getattr(provider, "calibrated", False)),
        calibration_id=None if cal_id is None else _clean_text(cal_id, 200))
    run = JudgedRun(provider=info)
    from .engine import error_text
    for i, p in enumerate(paths):
        name = names[i] if names else str(p)
        try:
            ctx = PageContext.parse(Path(p).read_bytes(), path=name,
                                    provenance_attr=provenance_attr,
                                    reader=reader)
        except Exception as exc:                        # noqa: BLE001
            # One page the track cannot read must not stop it, nor the
            # reports (OR2-5); it is recorded, never graded as passing.
            text = error_text(exc)
            run.errors.append((name, "(the page)", text))
            run.pages.append({"path": name, "results": [], "error": text})
            continue
        page_out = {"path": name, "results": []}
        for rule_id, (extract, impact) in JUDGED.items():
            token = PROVENANCE_ATTR.set(provenance_attr)
            try:
                items = extract(ctx)
            except Exception as exc:                    # noqa: BLE001
                text = error_text(exc)
                run.errors.append((name, rule_id, text))
                page_out["results"].append({
                    "rule_id": rule_id, "items": 0, "graded": 0,
                    "truncated": False, "findings": [], "error": text})
                continue
            finally:
                PROVENANCE_ATTR.reset(token)
            truncated = len(items) > max_items_per_rule
            graded_items = items[:max_items_per_rule]
            findings: list[dict] = []
            for item in graded_items:
                res = provider.judge(rule_id, item)
                # An errored result is never a pass, whatever verdict string
                # the provider happened to return.
                if res.verdict == "pass" and not res.error:
                    continue
                verdict = (FAIL if res.verdict == "fail" and not res.error
                           else NEEDS_REVIEW)
                findings.append({
                    "rule_id": rule_id, "verdict": verdict, "impact": impact,
                    # A provider's error quotes whatever failed, file paths
                    # included; home directories are scrubbed (redact.py).
                    "message": (redact_local_paths(_clean_text(res.rationale, 400))
                                if res.error else _clean_text(res.rationale, 400)),
                    "line": item.get("line"),
                    "item": {k: v for k, v in item.items() if k != "line"},
                    "model": _clean_text(res.model, 120),
                    "error": bool(res.error),
                })
            page_out["results"].append({
                "rule_id": rule_id, "items": len(items),
                "graded": len(graded_items), "truncated": truncated,
                "findings": findings,
            })
        run.pages.append(page_out)
    return run
