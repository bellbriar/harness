"""`--baseline report.json` (A10): a gate that fails only on findings an
earlier run did not have, so a team can add the gate to a site that already
has failures without a red build forever, and still not let a new one in.

The baseline is an earlier run's JSON report (`bellbriar-report/1`).
Findings are matched by fingerprint (docs/REPORT.md, "`about` and
fingerprints"): the same element failing the same rule on the same page,
and by what the gate reads of each — its verdict, whether it is the site's
own, its rule's tier and its impact (report.baseline_key). A finding that
changed in any of those is new: the baseline accepted what it was, not
what it became.
The baseline changes only what the gate counts. The reports and any
evidence bundle still list every finding, and record the baseline's
SHA-256, so nobody reading them can mistake a gated run for a clean one.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from .model import FAIL, NEEDS_REVIEW

#: The largest baseline read: a report of 1,000 pages with a thousand
#: findings each is well under this.
MAX_BASELINE_BYTES = 512 * 1024 * 1024
_FINGERPRINT = re.compile(r"[0-9a-f]{32}")


class BaselineError(ValueError):
    """A baseline that cannot be used; its text says why, for the console."""


@dataclass(frozen=True)
class Baseline:
    """What a run takes from its baseline."""
    #: The file as named on the command line.
    path: str
    #: SHA-256 of the file's bytes: which baseline, exactly.
    sha256: str
    #: When the baseline report was made (its `generated_at`).
    generated_at: str | None
    #: report.baseline_key of every finding it lists.
    keys: frozenset
    #: How many findings it lists.
    findings: int
    #: The rulebook it was made with (`rulebook_sha256`).
    rulebook_sha256: str | None
    #: The pages it was made from, as recorded (`pages[i].path`).
    paths: tuple

    @property
    def fingerprints(self) -> frozenset:
        return frozenset(k[0] for k in self.keys)


def load(path: str) -> Baseline:
    """Read a baseline report, or raise BaselineError saying why it cannot
    be one."""
    p = Path(path)
    try:
        size = p.stat().st_size
        if size > MAX_BASELINE_BYTES:
            raise BaselineError(f"--baseline {path}: {size:,} bytes, more "
                                "than a report this harness writes")
        data = p.read_bytes()
    except OSError as exc:
        raise BaselineError(f"--baseline {path}: "
                            f"{exc.strerror or exc}") from None
    try:
        report = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError):
        # RecursionError: arrays nested past what the parser follows
        # (R4B-11); no report this harness writes is.
        raise BaselineError(f"--baseline {path}: not a JSON file; give the "
                            "JSON report of an earlier run (--json)") from None
    if not isinstance(report, dict) or \
            report.get("format") != "bellbriar-report/1":
        raise BaselineError(f"--baseline {path}: not a bellbriar-report/1 "
                            "report; give the JSON report of an earlier run "
                            "(--json)")
    pages = report.get("pages")
    if not isinstance(pages, list):
        raise BaselineError(f"--baseline {path}: the report lists no pages")
    rules = report.get("rules")
    if not isinstance(rules, dict):
        rules = {}
    from .report import baseline_key
    keys: set = set()
    count = 0
    paths = []
    for i, page in enumerate(pages):
        findings = page.get("findings") if isinstance(page, dict) else None
        if not isinstance(findings, list):
            raise BaselineError(f"--baseline {path}: page {i + 1} lists no "
                                "findings")
        paths.append(str(page.get("path")))
        for f in findings:
            fp = f.get("fingerprint") if isinstance(f, dict) else None
            if not (isinstance(fp, str) and _FINGERPRINT.fullmatch(fp)):
                raise BaselineError(
                    f"--baseline {path}: a finding on page {i + 1} has no "
                    "fingerprint (32 hex digits); make the baseline with "
                    "this version of the harness")
            rule_id = f.get("rule_id")
            rule = rules.get(rule_id) if isinstance(rule_id, str) else None
            tier = rule.get("tier") if isinstance(rule, dict) else None
            verdict, owned, impact = (f.get("verdict"), f.get("owned"),
                                      f.get("impact"))
            if not isinstance(rule_id, str) or \
                    verdict not in (FAIL, NEEDS_REVIEW) or \
                    not isinstance(owned, bool) or \
                    not isinstance(impact, str) or \
                    not (tier is None or type(tier) is int):
                raise BaselineError(
                    f"--baseline {path}: a finding on page {i + 1} does not "
                    "say its rule, verdict, owner, impact and rule tier as a "
                    "bellbriar-report/1 report does; make the baseline with "
                    "this version of the harness")
            keys.add(baseline_key(fp, verdict, owned, tier, impact))
            count += 1
    rb = report.get("rulebook_sha256")
    made = report.get("generated_at")
    return Baseline(path=path, sha256=hashlib.sha256(data).hexdigest(),
                    generated_at=made if isinstance(made, str) else None,
                    keys=frozenset(keys), findings=count,
                    rulebook_sha256=rb if isinstance(rb, str) else None,
                    paths=tuple(paths))


def record(baseline: Baseline | None, new: int, new_fail: int) -> dict | None:
    """The `baseline` record reports and bundles carry: which baseline (its
    SHA-256 and when it was made), how many findings it lists, and how many
    of this run's findings, and FAIL findings in the site's own markup, are
    not in it. None for a run without one."""
    if baseline is None:
        return None
    return {"sha256": baseline.sha256,
            "generated_at": baseline.generated_at,
            "findings": baseline.findings,
            "new_findings": new,
            "new_fail_findings": new_fail}
