"""What a run says about its own coverage, and how a verifier tells it.

Every report and bundle carries a coverage note (what the run evaluated,
and what it did NOT) and a note for each layer. They are the harness's
words, signed with everything else, so `bellbriar-evidence verify` and
`inspect` say when a bundle's are not the words this release writes: an
older or newer release's, or edited (L93). The texts live here, with the
patterns that recognize them, so that the verifier needs nothing of the
engine; engine.py and cli.py write them, and tests/test_part_r6.py holds
every text they write to these patterns.
"""
from __future__ import annotations

import re

# (layer, status, why) — printed and embedded in every report. Claims
# discipline lives here: a run must say what it did NOT evaluate.
LAYERS = (
    ("static-dom", "executed",
     "Deterministic DOM rules on parsed markup (ACT-mapped)."),
    ("accessibility-tree", "skipped",
     "Not in this release: assertions on the roles, states and names a "
     "browser's accessibility tree exposes are not built (docs/ROADMAP.md)."),
    ("interaction", "skipped",
     "Not in this release: keyboard walks, focus traps, menu and dialog "
     "behavior and live regions are not implemented (docs/ROADMAP.md)."),
    ("rendered", "skipped",
     "Not executed: contrast, target size, reflow at 320 CSS pixels and the "
     "other rules checked in the browser run only on pages a browser "
     "captured (a URL run, or --render). Focus visibility and text spacing "
     "beyond inline styles are not implemented."),
    ("judge", "skipped",
     "Not in this release: grading whether alt text and link text are "
     "adequate needs a judge calibrated against human-labeled pages, and "
     "none exists yet, so the rules of this layer are not evaluated."),
)

#: The static layer's note when no page could be read (R3A-5).
NOTHING_READ_LAYER_NOTE = ("No page could be read, so no rule ran; each "
                           "page's error says why.")

#: How the rendered layer's note ends when its rules ran on some page.
RENDERED_LAYER_ENDING = (". On any other page they were not evaluated. "
                         "Focus visibility and text spacing beyond inline "
                         "styles are not implemented.")

#: Appended when a URL run could only read the HTML the server sent. The
#: fallback is never silent: a JS-built page read as static markup reports
#: cleaner than it is, which is the failure mode this tool exists to avoid.
SERVER_ONLY_SENTENCE = (
    " This run read only the HTML the server sent; content built by "
    "JavaScript after load was NOT evaluated, so a site that renders its "
    "content client-side may have barriers this run could not see."
)

#: Appended when the hydrated DOM was captured. A rendered fetch changes the
#: INPUT the static rules read, and lets axe-core check the page as
#: rendered; it does not execute the interaction layer, and must never be
#: read as though it did (the coverage sentence says what ran).
RENDERED_SENTENCE = (
    " This run evaluated the hydrated DOM captured from a live page at the "
    "recorded time, so client-rendered content was included. The capture is "
    "a point in time: the page may differ before or after, and the recorded "
    "snapshot hash identifies exactly what was measured."
)

#: Appended when a --render run captured every page after its scripts ran.
BUILD_SENTENCE = (
    " This run served the files on this machine and evaluated each page's "
    "DOM after its scripts ran (the hydrated DOM), so content they build "
    "was included."
)
#: ... and when it could not, and read the files as they are.
BUILD_STATIC_SENTENCE = (
    " This run could not render the files and read them as they are; "
    "content their scripts build was NOT evaluated, so a client-rendered "
    "page may have barriers this run could not see."
)

COVERAGE_SENTENCE = (
    "This run covers the static DOM layer only. Keyboard operability, focus "
    "visibility, contrast, reflow, screen-reader announcements, and content "
    "adequacy were NOT evaluated. A passing result here is necessary, not "
    "sufficient, and is not a determination of WCAG conformance or legal "
    "compliance."
)

#: The coverage sentence when no page of the run could be read (R3C-4).
NOTHING_READ_SENTENCE = (
    "This run evaluated no page: none could be read, so no rule ran (each "
    "page's error says why). It is not a determination of WCAG conformance "
    "or legal compliance."
)

#: The coverage sentence when rendered checks ran (coverage_sentence):
#: {what} names them and the pages; {missing} is what was NOT evaluated.
RENDERED_COVERAGE_SENTENCE = (
    "This run covers the static DOM layer and {what}. {missing} were NOT "
    "evaluated. A passing result here is necessary, not sufficient, and is "
    "not a determination of WCAG conformance or legal compliance."
)

#: How many of the rules checked in the browser axe-core decides: every
#: rendered rule but reflow (len(checks_rendered.RENDERED_CHECKS) - 1, as
#: a test holds them).
AXE_RULES = 29

#: The longest note a run writes is far shorter: a longer one is not one.
_LONGEST = 8192

_N = r"[0-9]+"
_VERSION = r"[0-9][0-9A-Za-z.+-]*"
#: engine._axe_versions: the versions, joined by " and ", or "?".
_VERSIONS = rf"(?:\?|{_VERSION}(?: and {_VERSION})*)"
_E = re.escape


def _coverage_pattern() -> re.Pattern:
    """Every coverage note this release writes: engine.coverage_sentence,
    then what cli._coverage_note adds about how the pages were read."""
    n = AXE_RULES
    on = (rf"(?: on {_N} of the {_N} pages it read \(NOT evaluated on the "
          rf"other(?: {_N})?\))?")
    hidden = (rf"on {_N} of them aria-hidden=\"true\" on the page's <html> "
              r"or <body> made axe-core skip what it takes as hidden")
    capture = r"each page's capture notes say why"
    why = rf"(?: \((?:{hidden}(?:; {capture})?|{capture})\))?"
    short = rf"(?:, though not every one of them on {_N} of those pages{why})?"
    when = (r"(?:checked in the browser when the snapshot was captured|"
            r"checks in the browser)")
    axe = (rf"the {n} rules axe-core {_VERSIONS} {when} \(contrast, target "
           rf"size and {n - 2} more WCAG A/AA rules\){on}{short}")
    reflow = rf"reflow at 320 CSS pixels{on}"
    narrow = rf"what {_N} of its pages hide at 320 CSS pixels"
    head, rest = RENDERED_COVERAGE_SENTENCE.split("{what}")
    mid, tail = rest.split("{missing}")
    heads = [_E(COVERAGE_SENTENCE)]
    for what, has_axe, has_reflow in ((axe, True, False),
                                      (reflow, False, True),
                                      (f"{axe} and {reflow}", True, True)):
        items = ["Keyboard operability" + (
            " (beyond whether scrollable regions can take focus)"
            if has_axe else ""), "focus visibility"]
        if not has_axe:
            items.append("contrast")
        if not has_reflow:
            items.append("reflow")
        for with_narrow in (False, True):
            its = ([_E(i) for i in items] + ([narrow] if with_narrow else [])
                   + [_E("screen-reader announcements"),
                      _E("content adequacy")])
            missing = ", ".join(its[:-1]) + ", and " + its[-1]
            heads.append(_E(head) + what + _E(mid) + missing + _E(tail))
    rendered = rf"{_N} (?:was|were) captured after (?:its|their) scripts ran"
    static = (rf"{_N} (?:was|were) read (?:as files are|from the HTML the "
              r"server sent)")
    unread = rf"{_N} could not be read"
    tails = [""] + [_E(t) for t in (BUILD_SENTENCE, RENDERED_SENTENCE,
                                    BUILD_STATIC_SENTENCE,
                                    SERVER_ONLY_SENTENCE)]
    for parts in ((rendered, static), (rendered, unread), (static, unread),
                  (rendered, static, unread)):
        said = ", ".join(parts[:-1]) + " and " + parts[-1]
        end = (r": on those read without a browser, content built by "
               r"JavaScript was NOT evaluated\." if static in parts else r"\.")
        tails.append(rf" Of the run's {_N} pages, {said} \(each page's "
                     rf"record says which\){end}")
    return re.compile(rf"{_E(NOTHING_READ_SENTENCE)}|(?:{'|'.join(heads)})"
                      rf"(?:{'|'.join(tails)})")


def _rendered_layer_pattern() -> re.Pattern:
    """The rendered layer's note when its rules ran on some page
    (engine.layer_records)."""
    n = AXE_RULES
    rules = (rf"for the {n} WCAG A/AA rules Bellbriar does not implement "
             rf"itself \(contrast, target size and {n - 2} more\)")
    snapshot = (rf"the snapshot records what axe-core {_VERSIONS} found in "
                rf"the browser when it was captured, on {_N} of {_N} "
                rf"page\(s\), {rules}(?:, though not for every rule on {_N} "
                r"of them)?")
    live = (rf"axe-core {_VERSIONS} checked {_N} of {_N} page\(s\) in the "
            rf"browser, {rules}(?:, though not every rule on {_N} of them "
            r"\(each page's capture notes say why\))?")
    reflow = rf"Bellbriar checked reflow at 320 CSS pixels on {_N} of {_N}"
    narrow = (rf"what {_N} of them hide at 320 CSS pixels was not recorded, "
              r"so their rules ran with what they hide at the capture's own "
              r"width only \(each page's capture notes say why\)")
    notes = []
    for first in ([f"(?:{snapshot}|{live})"], [reflow],
                  [f"(?:{snapshot}|{live})", reflow]):
        for parts in (first, first + [narrow]):
            notes.append("; ".join(parts))
    return re.compile(rf"(?:{'|'.join(notes)}){_E(RENDERED_LAYER_ENDING)}")


_COVERAGE = _coverage_pattern()
_RENDERED_LAYER = _rendered_layer_pattern()
LAYER_NAMES = tuple(name for name, _status, _note in LAYERS)


def coverage_note_known(note) -> bool:
    """Is `note` a coverage note this release writes?"""
    return (isinstance(note, str) and len(note) <= _LONGEST
            and _COVERAGE.fullmatch(note) is not None)


#: The rendered note's parts that name every page read: axe-core's (on
#: a snapshot, or live) and reflow's.
_AXE_ALL = re.compile(r"(?:when it was captured, on|checked) ([0-9]+) of "
                      r"\1 page\(s\)")
_REFLOW_ALL = re.compile(r"reflow at 320 CSS pixels on ([0-9]+) of "
                         r"\1(?![0-9])")


def _rendered_status(note: str) -> str:
    """The status engine.layer_records writes beside `note`, a rendered
    layer's note (_RENDERED_LAYER): "executed" where axe-core and reflow
    each covered every page read (N of N, the same N), no page lacks a
    rule's results and every page's narrow view was recorded; "partial"
    otherwise (R6AA-2)."""
    axe = _AXE_ALL.search(note)
    reflow = _REFLOW_ALL.search(note)
    full = (axe is not None and reflow is not None
            and axe.group(1) == reflow.group(1)
            and ", though not " not in note
            and "hide at 320 CSS pixels was not recorded" not in note)
    return "executed" if full else "partial"


def _layer_known(name: str, status, note) -> bool:
    if not isinstance(note, str) or len(note) > _LONGEST:
        return False
    own = {layer: (st, text) for layer, st, text in LAYERS}[name]
    if (status, note) == own:
        return True
    if name == "static-dom":
        return (status, note) == ("skipped", NOTHING_READ_LAYER_NOTE)
    if name == "rendered":
        return (_RENDERED_LAYER.fullmatch(note) is not None
                and status == _rendered_status(note))
    return False


def layer_problems(layers) -> list[str]:
    """What, of a bundle's or report's layer records, this release does not
    write: a record whose status and note are not this release's for its
    layer (the status the note's counts make it too: _rendered_status), a
    layer recorded more than once (R6AA-2), a layer it does not have
    (counted, never named: the name is the maker's), and a list without a
    layer this release records."""
    if not isinstance(layers, list):
        return []
    out, seen, unknown, other, twice = [], set(), 0, [], []
    for rec in layers:
        name = rec.get("layer") if isinstance(rec, dict) else None
        if name not in LAYER_NAMES:
            unknown += 1
            continue
        if name in seen and name not in twice:
            twice.append(name)
        seen.add(name)
        if not _layer_known(name, rec.get("status"), rec.get("note")) \
                and name not in other:
            other.append(name)
    if other:
        out.append(("the records of its " if len(other) > 1 else
                    "the record of its ") + _join(other)
                   + (" layers" if len(other) > 1 else " layer"))
    if twice:
        out.append("more than one record of its " + _join(twice)
                   + (" layers" if len(twice) > 1 else " layer"))
    if unknown:
        out.append(f"{unknown} layer record{'s' if unknown != 1 else ''} "
                   "of no layer this release has")
    missing = [name for name in LAYER_NAMES if name not in seen]
    if missing:
        out.append("a list of layers without the " + _join(missing)
                   + " layer" + ("s" if len(missing) > 1 else ""))
    return out


def _join(items: list) -> str:
    return (items[0] if len(items) == 1 else
            ", ".join(items[:-1]) + " and " + items[-1])
