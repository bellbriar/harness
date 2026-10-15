"""Contracts for browser checks this release does not make: the
accessibility-tree and interaction layers, and what the rendered layer
does not cover yet. Interfaces and acceptance criteria are fixed here so
the roadmap (docs/ROADMAP.md) is executable; none is implemented, and
each raises NotImplementedError. What the rendered layer checks today
(axe-core's rules, reflow at 320 CSS pixels: checks_rendered) runs
elsewhere; reflow_scan and target_size_scan describe what those checks
would add.

These layers exist because the deterministic DOM layer cannot observe the
half of the complaint boilerplate that is about *operation*: denial of
keyboard access, traps, invisible focus, unpausable motion, silent status
changes. Do not ship results that imply otherwise.
"""
from __future__ import annotations

_NOT_IMPLEMENTED = (
    "Not implemented in this release: a planned check (docs/ROADMAP.md). "
    "A run's layer records say what it evaluated; see docs/METHODOLOGY.md."
)


def tab_walk(url: str) -> None:
    """Full-page keyboard walk (WCAG 2.1.1, 2.4.3, 2.4.7).

    Contract: every interactive element reachable by Tab/Shift+Tab in a
    sane order; each stop exposes a visible focus indicator (computed
    styles; outline:none without replacement fails); no stop is a trap
    (2.1.2) — forward and reverse progress always possible; Escape exits
    composite widgets per the ARIA APG keyboard contracts.
    """
    raise NotImplementedError(_NOT_IMPLEMENTED)


def modal_contract(url: str) -> None:
    """Dialog behavior per APG (2.1.2, 2.4.3, 4.1.2): focus moves in on
    open, is contained while open, Escape closes, focus returns to the
    invoker, role=dialog/aria-modal exposed, background inert."""
    raise NotImplementedError(_NOT_IMPLEMENTED)


def carousel_pause(url: str) -> None:
    """Auto-rotating content (2.2.2): motion longer than 5s has a
    pause/stop/hide control that is keyboard-operable and named."""
    raise NotImplementedError(_NOT_IMPLEMENTED)


def live_region_capture(url: str, action: str) -> None:
    """Status messages (4.1.3): perform the action (add-to-cart, filter,
    submit) and assert an accessibility-tree announcement occurred
    without focus moving."""
    raise NotImplementedError(_NOT_IMPLEMENTED)


def contrast_scan(url: str) -> None:
    """Rendered contrast (1.4.3, 1.4.11) across states: default, hover,
    focus, placeholder; includes the focus indicator itself."""
    raise NotImplementedError(_NOT_IMPLEMENTED)


def reflow_scan(url: str) -> None:
    """Reflow beyond what bb-reflow-320 checks today (a page that scrolls
    sideways at 320 CSS px, 1.4.10): 200% zoom (1.4.4), and no loss of
    content or function at either."""
    raise NotImplementedError(_NOT_IMPLEMENTED)


def target_size_scan(url: str) -> None:
    """WCAG 2.2 delta 2.5.8: targets >= 24x24 CSS px or spacing
    equivalent, checked by Bellbriar itself; axe-core's target-size runs
    today (bb-target-size)."""
    raise NotImplementedError(_NOT_IMPLEMENTED)
