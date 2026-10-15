"""Core data model. Verdict semantics (see docs/METHODOLOGY.md):

- fail          : the rule's failure condition is met, decided
                  deterministically. A fail means WCAG is violated
                  (`verdict_basis` sc) or probably is (heuristic); rules
                  with any other basis never fail (engine.run_page).
- needs_review  : a pattern that requires human or higher-layer judgment;
                  never counted as a failure in scoring.
A rule *passes* on a page when it is applicable and produced zero `fail`
findings. A rule with `applicable=False` is excluded from the denominator.
"""
from __future__ import annotations

import contextvars
from dataclasses import dataclass, field

FAIL = "fail"
NEEDS_REVIEW = "needs_review"

BLOCKER = "blocker"
SERIOUS = "serious"
MODERATE = "moderate"
MINOR = "minor"

IMPACT_ORDER = {BLOCKER: 0, SERIOUS: 1, MODERATE: 2, MINOR: 3}


#: Who owns the markup a finding sits in (see fetch.py). Only first-party
#: findings are scored: a consent banner or chat launcher injected by a
#: vendor script is outside evaluation scope (scope-and-exclusions EXC-1)
#: and the customer cannot edit it — but it is still reported, with the
#: residual duties that remain.
FIRST_PARTY = "first-party"
THIRD_PARTY = "third-party"
#: Inserted by cross-origin code that is not a known vendor — typically the
#: site's own CDN-hosted bundle or a library loaded from a public CDN.
CROSS_ORIGIN = "cross-origin"
ORIGIN_SERVER = "server"
ORIGIN_UNKNOWN = "unknown"

#: Origins that count as the customer's own markup for scoring. Only markup
#: attributed to a known vendor ("third-party") is excluded.
OWNED = (FIRST_PARTY, CROSS_ORIGIN, ORIGIN_SERVER, ORIGIN_UNKNOWN, "")


def muted_attr(provenance_attr: str) -> str:
    """Where a rendered capture records each <audio>/<video>'s `muted`
    *property* ("true" or "false"), beside the provenance attribute and
    from the same per-capture secret, which page code cannot know before
    the capture is serialized.

    Frameworks set `muted` as a property, not an attribute (React does so
    always), so serialized markup alone shows a muted video as playing with
    sound. The property is what plays; the attribute only sets its start."""
    return provenance_attr + "-muted"


def hidden_attr(provenance_attr: str) -> str:
    """Where a rendered capture marks each element at which what the page,
    as rendered, shows changes from its parent: "display" where
    display:none (or content-visibility:hidden) takes it out of rendering,
    "visibility" where visibility:hidden or collapse hides it, and "shown"
    where content inside a visibility:hidden ancestor is made visible again
    (visibility:visible), focus included. The nearest mark on an element or
    its ancestors decides; the root element carries "recorded". "skips"
    marks a rendered element that does not render what it holds
    (content-visibility:hidden, as hidden="until-found" sets it, on a box
    whose content Chromium skips: a block, an inline block, a flex or grid
    container, a list item but an inline one, a table cell, a <button>, a
    <fieldset>, a <canvas>, an <svg>; not a table, a row, ruby, an inline
    box or a <textarea>, whose text is its value: style.RENDERING_DISPLAYS),
    "shown-skips" one that is "shown" too, "visibility-skips" one that is
    invisible (whatever its parent is): nothing it holds names anything,
    its own text included, which no mark can carry, and its child elements
    are marked "display" where they can be marked. A drawing's and
    MathML's parts carry marks too, but a drawing's <title> and <desc>,
    never rendered, whose text names and describes it (R5K-10, R5L-1,
    R5O-5, R5R-3, R6A-4). One that is not rendered is marked as Chromium
    141 reads it into names (measured, R6C-3): "display" where it leaves
    it out with what it holds (its own display none, but a drawing's <g>
    or <marker>; an element of a drawing Chromium does not know, a
    <metadata>, a <view>, what a <use> holds; a part whose conditions
    fail, where its parent is rendered or boxed, as what a <defs> holds
    is; and the like); where rendering stops at one it reads,
    "unrendered" (a drawing's <defs>, <marker>, or <g> with display:none,
    which Chromium boxes but never paints; a MathML part, as
    aria-labelledby reads it: a name from content Chromium gives from no
    MathML, where the runs read it, L92) or "unboxed" (another part of a
    drawing, as the <g> or <text> a <switch> passes over or what a
    gradient holds, which a name reads only where no part whose role is
    group, as a <g>'s, an inner <svg>'s or an <a>'s that is no link,
    stands between it and the name's start, nearer than another <a>, and
    none of what a part of it whose role is group holds:
    accname.subtree_text, R6I-4);
    "unrendered-visibility" or "unboxed-visibility" where such a part is
    invisible too, or an element inside one turns invisible, as its
    computed style has it, and "shown" where one is made visible again
    there (R6E-4, R6E-5). Canvas fallback content, which has no box but
    can take focus, is as shown as its canvas. Beside the provenance
    attribute, from the same per-capture secret.

    Stylesheets decide most hiding (a Bootstrap modal is `display:none`
    through its class), and serialized markup does not show their effect."""
    return provenance_attr + "-hidden"


def narrow_hidden_attr(provenance_attr: str) -> str:
    """hidden_attr's record taken at the capture's second, narrow viewport
    (fetch.NARROW_VIEWPORT, 320 by 640): what the page hides at phone width
    (L24). The root element carries "recorded" when the capture took it."""
    return provenance_attr + "-hidden-narrow"


def narrow_changed_attr(provenance_attr: str) -> str:
    """Where a rendered capture marks each element the page changed between
    the capture and the narrow record: "self" where its own attributes
    changed (other than class, style, hidden and data- ones, which only
    show or hide what the narrow record measures) or it was inserted or
    moved; "children" where only what it holds did (its child nodes, its
    text). The snapshot shows such an element as it was at the capture's
    own width, so what the narrow record shows about it, about what it
    holds, or about what is inside an element changed "self", cannot be
    confirmed (engine.merge_views)."""
    return provenance_attr + "-narrow-changed"


def reflow_attr(provenance_attr: str) -> str:
    """Where a rendered capture marks each element that, at 320 CSS pixels
    wide, reaches past the right edge of the page and makes it scroll
    sideways (JSON: how far, and what in it reaches that far: text or a
    form control, only content WCAG 1.4.10 exempts, or nothing it shows).
    bb-reflow-320 reads it."""
    return provenance_attr + "-reflow"


def reflow_run_attr(provenance_attr: str) -> str:
    """Where a rendered capture records, on its root element, its reflow
    measurement at 320 CSS pixels wide (JSON: the viewport, the page's
    scroll width and its client width, and whether the page clips what
    reaches past its edge). Without it reflow was not evaluated."""
    return provenance_attr + "-reflow-run"


#: Which record of what the page hides the rules read (L24): "" for the
#: capture's own viewport (model.hidden_attr), "narrow" for its second one
#: (narrow_hidden_attr). engine.run_page evaluates a page once per record
#: its capture took.
HIDDEN_VIEW: contextvars.ContextVar[str] = contextvars.ContextVar(
    "bellbriar_hidden_view", default="")


def view_hidden_attr(provenance_attr: str) -> str:
    """The record of what the page hides the rules read now (HIDDEN_VIEW)."""
    return (narrow_hidden_attr(provenance_attr)
            if HIDDEN_VIEW.get() == "narrow" else hidden_attr(provenance_attr))


def axe_attr(provenance_attr: str) -> str:
    """Where a rendered capture records, on each element axe-core reported,
    that element's results (JSON: rule, verdict, impact, message), beside
    the provenance attribute and from the same per-capture secret
    (axe.py)."""
    return provenance_attr + "-axe"


def axe_run_attr(provenance_attr: str) -> str:
    """Where a rendered capture records, on its root element, the axe-core
    run itself (JSON: the version; the rules that applied and did not; for
    each rule, how many of its results no element in the snapshot carries;
    and how many elements of the snapshot axe-core did not check). Without
    it no axe-core rule was evaluated on the page."""
    return provenance_attr + "-axe-run"


#: The version of what a rendered capture marks in its snapshot: the
#: records the *_attr functions here name, and their values. A capture
#: writes it on its root element (capture_attr), and a re-run of a
#: snapshot that names another, or none, is not evaluated: rules that
#: read marks they do not know can pass what a fresh capture fails
#: (L106). Raise it whenever a capture marks something new, or marks it
#: otherwise.
MARKS_VERSION = 1


def capture_attr(provenance_attr: str) -> str:
    """Where a rendered capture records, on its root element, itself
    (JSON: "browser", the version of the Chromium that captured the page,
    and "marks", MARKS_VERSION), so that a re-run of its snapshot records
    which browser captured it (L53) and reads only marks it knows
    (L106)."""
    return provenance_attr + "-capture"


#: The provenance attribute to honor while engine.run_page evaluates one
#: page. None (the default) means none: markup from a file or a server can
#: say anything about itself — `data-bb-origin="third-party:…"` on <body>
#: used to move every failure out of the score — so only what the harness's
#: own capture wrote, under a name the page could not know, is read. The
#: capture's other records (muted_attr, hidden_attr) follow the same name.
PROVENANCE_ATTR: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "bellbriar_provenance_attr", default=None)

#: The page engine.run_page is evaluating (a checks_static.PageContext), for
#: what the rules and the name computation read about the page as a whole:
#: whether a capture recorded what it hides, and its own <style> rules.
CURRENT_PAGE: contextvars.ContextVar[object | None] = contextvars.ContextVar(
    "bellbriar_current_page", default=None)


@dataclass
class Finding:
    rule_id: str
    verdict: str          # FAIL | NEEDS_REVIEW
    impact: str           # BLOCKER | SERIOUS | MODERATE | MINOR
    message: str
    line: int | None = None
    snippet: str = ""
    #: "" on a server-HTML or local-file run (nothing to attribute against),
    #: otherwise "server", "first-party", "third-party", or "unknown".
    origin: str = ""
    #: For third-party findings, the script origin responsible.
    origin_detail: str = ""
    #: Where the element is: CSS selectors, one per tree, the first matched
    #: in the document and each further one in the shadow root of the
    #: element before it (locator.py); None for a finding about the page.
    selector: list | None = None
    #: What the finding is about, the same on any page and in any run while
    #: the element is: 32 hex digits of the SHA-256 of its tag (name and
    #: every attribute), the start of its text and its first descendants
    #: (checks_static.element_identity); "" for a finding about the page.
    #: Report fingerprints are made from it.
    about: str = ""

    @property
    def owned(self) -> bool:
        """Is this the customer's to fix? Everything but markup a known
        vendor's script inserted: unattributed findings, and any origin the
        harness does not know (a re-run of an edited snapshot), count as
        owned, because silence about provenance must never shrink the
        score."""
        return self.origin != THIRD_PARTY


@dataclass
class RuleResult:
    rule_id: str
    applicable: bool
    findings: list[Finding] = field(default_factory=list)
    #: The rule raised instead of returning ("TypeError: ..."): its result
    #: on this page is unknown. Never a pass; the run reports it and exits 2.
    errored: str = ""

    @property
    def failed(self) -> bool:
        """Scored failure: a first-party fail finding. Third-party findings
        are reported and excluded from the score (see Finding.owned)."""
        return self.applicable and any(f.verdict == FAIL and f.owned
                                       for f in self.findings)

    @property
    def failed_any(self) -> bool:
        """Including third-party — for the reported total, not the score."""
        return self.applicable and any(f.verdict == FAIL for f in self.findings)


@dataclass
class PageResult:
    path: str
    results: list[RuleResult] = field(default_factory=list)
    #: False when the static rules cannot meaningfully evaluate the markup
    #: (a client-rendered app shell; see checks_static.detect_app_shell).
    #: Such a page has no pass rate and is never "Tier-1 clean"; any fail it
    #: does produce is still real and still counts.
    evaluable: bool = True
    not_evaluable_reason: str = ""
    #: The page could not be fetched or parsed ("ValueError: ..."): no rule
    #: ran on it.
    parse_error: str = ""
    #: The page's capture record (fetch.FetchResult.fetch_block) in a URL
    #: or --render run; None for a file read as it is.
    fetch: dict | None = None
    #: The axe-core version the capture's records name, when they show
    #: axe-core checked the page in the browser (checks_rendered); "" when
    #: no rendered rule ran on it.
    axe_version: str = ""
    #: Were those records read from a snapshot captured earlier (a file run
    #: of a saved snapshot, engine.run_paths)? Then axe-core did not run in
    #: this run (R1B-4).
    axe_from_snapshot: bool = False
    #: The version of the Chromium that captured the page, as the capture
    #: record of a snapshot re-run names it (model.capture_attr, L53); ""
    #: elsewhere: a fresh capture names its own in its capture record.
    capture_browser: str = ""
    #: Why some of axe-core's rules are not evaluated on the page, though
    #: it ran (checks_rendered.ROOT_HIDDEN_NOTE); "" when none is left out
    #: for that. Added to the page's capture notes (cli), and said by the
    #: coverage sentence (engine.coverage_sentence).
    axe_unread: str = ""
    #: Were the rules also run with what the page hides at phone width
    #: (engine.merge_views, L24)?
    narrow: bool = False
    #: In memory only, never written anywhere: the URL a URL run was given
    #: for the page, query values and all. It fixes the order of pages
    #: recorded under the same path (report.page_numbers, R4B-3); "" for a
    #: file.
    order: str = ""
    #: (sha256, bytes) of the file a file or --render run evaluated the
    #: page from, as it was read (or served) then: a bundle's input
    #: manifest records these, not a second reading (R5B-10). None for a
    #: URL run's page, whose snapshot is its input.
    input_digest: tuple | None = None

    def failed_rules(self) -> list[str]:
        return [r.rule_id for r in self.results if r.failed]

    def errors(self) -> list[tuple[str, str]]:
        """(rule id, error) for every rule that raised on this page; the
        page itself when it could not be parsed."""
        out = [("(the page)", self.parse_error)] if self.parse_error else []
        return out + [(r.rule_id, r.errored) for r in self.results
                      if r.errored]
