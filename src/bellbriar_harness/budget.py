"""The time one page's analysis may take (--page-budget, S5-4).

The static rules match the page's own style rules against its elements,
and a page can hold enough of both to take minutes: a run that stopped
there would hold a CI job until its own timeout, saying nothing of why. A
page whose analysis runs past its budget is stopped where the harness next
looks at the clock (before each rule, while it matches style rules, and
once the rules have run), and is NOT EVALUATED: no rule's result is kept,
the reason names the budget, and, as for a page that could not be read,
the run exits 2 and writes no evidence bundle. Within the budget, what a
page's analysis finds does not depend on it.
"""
from __future__ import annotations

import contextvars
import time

#: Seconds, by default: about four times what the slowest page measured
#: took (335 KB, with 3,000 style rules, many of them on attributes and
#: siblings, and 6,000 elements: 31 s, S5-4).
DEFAULT_S = 120
LOW_S, HIGH_S = 10, 86400

#: The run's budget for each page (cli: --page-budget).
SECONDS: contextvars.ContextVar = contextvars.ContextVar(
    "bellbriar_page_budget", default=DEFAULT_S)
_DEADLINE: contextvars.ContextVar = contextvars.ContextVar(
    "bellbriar_page_deadline", default=None)


class Exceeded(BaseException):
    """A page's analysis ran past its budget. A BaseException, as a
    cancellation is: a rule's own `except Exception` (a rule that raises is
    errored, not passed) must not take it for that rule's error."""

    def __init__(self, seconds: float):
        super().__init__(f"its analysis ran past the {written(seconds)}-"
                         "second budget for one page (--page-budget)")
        self.seconds = seconds

    @property
    def reason(self) -> str:
        """Why the page is not evaluated, as a page's record says it."""
        return (f"{self}, so the harness stopped it: no rule's result is "
                "kept, and that is not a pass. A larger --page-budget gives "
                "the page more time")


def written(seconds: float) -> str:
    """A number of seconds as it was given: 120, 12345.678."""
    return str(int(seconds)) if float(seconds).is_integer() else repr(
        float(seconds))


def begin():
    """Start the page's clock; the token is end()'s."""
    seconds = SECONDS.get()
    return _DEADLINE.set((time.monotonic() + seconds, seconds))


def end(token) -> None:
    _DEADLINE.reset(token)


def check() -> None:
    """Raise Exceeded when the page's analysis is past its budget."""
    deadline = _DEADLINE.get()
    if deadline is not None and time.monotonic() > deadline[0]:
        raise Exceeded(deadline[1])


def parse_seconds(text: str) -> float:
    """--page-budget: LOW_S to HIGH_S seconds; 0, -5, inf and nan are
    refused, not quietly read."""
    try:
        value = float(text)
    except ValueError:
        raise ValueError(f"not a number of seconds: {text!r}") from None
    if not LOW_S <= value <= HIGH_S:          # nan fails both comparisons
        raise ValueError(f"must be {LOW_S} to {HIGH_S} seconds, not {text}")
    return value
