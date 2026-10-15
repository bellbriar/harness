"""Judge layer interface (LLM-graded adequacy checks).

Not in 1.0 (decision D3, the ship list's L4): nothing on the command line
reaches this code, which stays for when a calibrated judge exists. Open by
design so a published benchmark can be reproduced with any model. A hosted
judge, if one is built, is meant to add what cannot be open-sourced —
calibration against a human-expert golden set and versioned rubrics. None
of that exists (see judged.py STATUS), and no hosted judge runs.

A judge NEVER overrides a deterministic result; it only grades adequacy
questions (alt-text quality, link purpose, heading descriptiveness,
error-message usefulness) that deterministic rules cannot decide.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class JudgeResult:
    rubric_id: str
    verdict: str          # "pass" | "fail" | "needs_review"
    rationale: str
    model: str
    error: bool = False   # True when the PROVIDER failed to return a verdict
    #: An errored result is not a judgment. It never counts as a pass, never
    #: counts as a genuine needs_review, and is excluded from the denominator
    #: of judged_pass_rate. See JudgedRun.summary().


class JudgeProvider(Protocol):
    name: str

    def judge(self, rubric_id: str, payload: dict) -> JudgeResult: ...


class NullJudge:
    """Default provider: marks all judged checks as not run."""

    name = "null"

    def judge(self, rubric_id: str, payload: dict) -> JudgeResult:
        return JudgeResult(
            rubric_id=rubric_id,
            verdict="needs_review",
            rationale="No judge provider configured; adequacy not evaluated.",
            model="none",
            error=True,
        )
