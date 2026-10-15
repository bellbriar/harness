"""Rules the browser decides, read from the capture (decision D2).

A rendered capture runs axe-core in an isolated world of its own and writes
its results into the snapshot, under names derived from the capture's
secret provenance attribute (axe.py, fetch._AxeSession): the run's record on
the root element (the axe-core version, which rules applied, how many of
each rule's results no element carries, and how many elements axe-core did
not check), and each reported element's results on that element. The checks
here read those records and nothing else, so:

* a re-run of the snapshot with --provenance-attr reproduces them;
* a page cannot write such a record about itself (it does not know the
  names before the capture is serialized, and the capture removes anything
  under them first);
* a file or server-HTML run carries no record, and there no check here
  runs at all: it returns None, the rule is not evaluated on that page, and
  the run's coverage says so (engine.layer_records). That is never a pass.

Each check reports one axe-core rule under its Bellbriar rule
(axe.AXE_RULES): axe-core's violations as FAIL, the results it could not
decide as needs_review at minor impact. A result the capture could not
attach to an element (the page removed or moved the element first, or there
were too many to record) is reported about the page, so a rule never passes
on results that were left out. Where axe-core did not check part of the
snapshot (inside closed shadow roots it was not given), a rule that found no
failure is not evaluated on the page. The rulebook's verdict_basis then
holds each rule to what a FAIL from it means (engine.run_page), as it does
for Bellbriar's own checks.
"""
from __future__ import annotations

import json
import re
import urllib.parse

from bs4.element import Tag

from .accname import document_root
from .axe import (AXE_RULES, AXE_VERSION, MAX_ELEMENTS, MAX_MESSAGE,
                  read_mark, read_run)
from .checks_static import PageContext, _f
from .langtags import PRIMARY_LANGUAGE_SUBTAGS
from .model import (FAIL, MINOR, MODERATE, NEEDS_REVIEW, PROVENANCE_ATTR,
                    SERIOUS, RuleResult, axe_attr, axe_run_attr, reflow_attr,
                    reflow_run_attr)
from .redact import holds_password, scrub_secrets


def axe_state(page: PageContext) -> tuple[dict | None, dict]:
    """(The capture's axe-core run record, or None when it recorded none;
    {axe-core rule: [(element, result), …]}), read once per page."""
    cached = page._axe
    if cached is None:
        cached = page._axe = _read(page)
    return cached


def _read(page: PageContext) -> tuple[dict | None, dict]:
    attr = page.provenance_attr or PROVENANCE_ATTR.get()
    if not attr:
        return None, {}
    root = page.soup.find("html")
    run = (read_run(root.get(axe_run_attr(attr)))
           if isinstance(root, Tag) and root.has_attr(axe_run_attr(attr))
           else None)
    if run is None:
        return None, {}
    name = axe_attr(attr)
    by_rule: dict[str, list] = {}
    for el in page.soup.find_all(attrs={name: True}):
        for res in read_mark(el.get(name)):
            by_rule.setdefault(res["r"], []).append((el, res))
    return run, by_rule


def root_hidden(page: PageContext) -> list:
    """The page's <html> and <body> that carry aria-hidden="true", as the
    harness's own rules read the attribute (any case, white space around
    it). Current browsers ignore it there and expose the page
    (accname.document_root); an older one may hide all of it: a review
    (bb-aria-hidden-body)."""
    if page._root_hidden is None:
        found = []
        html = page.soup.find("html")
        if isinstance(html, Tag) and document_root(html):
            body = html.find("body", recursive=False)
            found = [el for el in (html, body) if isinstance(el, Tag)
                     and (el.get("aria-hidden") or "").strip().lower()
                     == "true"]
        page._root_hidden = found
    return page._root_hidden


def axe_skipped(page: PageContext) -> bool:
    """Did axe-core skip content of this page as hidden from assistive
    technology: is aria-hidden exactly "true" on its <html> or <body>, as
    axe-core compares it? Then a rule of axe-core's that found nothing
    may have checked nothing; what it found still stands (R5G-1, R5I-7:
    color-contrast, which reads what is seen, still checks the page)."""
    return any(el.get("aria-hidden") == "true" for el in root_hidden(page))


#: Why some of axe-core's rules are not evaluated on a page axe_skipped
#: finds (engine.run_page writes it into the page's capture notes).
ROOT_HIDDEN_NOTE = ("aria-hidden=\"true\" on the page's <html> or <body> makes "
                    "axe-core skip what it takes as hidden, though current "
                    "browsers ignore it there and expose the page: of "
                    "axe-core's rules, those that found a failure on this "
                    "page report it, and the others are NOT evaluated here, "
                    "but for bb-aria-hidden-body, which Bellbriar reads from "
                    "the markup itself (R5K-14)")


def _quoted(value: str, keep: int) -> str:
    """`value` as a message quotes it: whole where it holds the run's
    --http-user password, so the finding withholds the message (_f) rather
    than quote part of it (R5R-6); else the run's other secrets replaced
    in it before it is cut (a secret cut in two would no longer be found:
    R6A-2), then its first `keep` characters."""
    if holds_password(value):
        return value
    value = scrub_secrets(value)
    if len(value) <= keep:
        return value
    return value[:keep - 1] + "…"


def _root_hidden_message(el: Tag, skipped: bool) -> str:
    # The value as the page wrote it ("TRUE" is read as "true": R5K-14).
    value = _quoted(" ".join(str(el.get("aria-hidden") or "").split()), 20)
    return (f"aria-hidden=\"{value}\" on the page's <{el.name}>: Chromium, "
            "Firefox (from 139) and WebKit ignore it there and expose the "
            "page, but an older browser may hide all of it from assistive "
            "technology. Remove it."
            + (" axe-core skips what it takes as hidden, so where its other "
               "rules found no failure on this page they are not evaluated."
               if skipped else "")
            + f" [Bellbriar, after axe-core {AXE_VERSION} aria-hidden-body]")


def _unplaced(rule_id: str, axe_rule: str, entry: dict, page: PageContext
              ) -> list:
    """The findings about the page for one rule's results that no element
    in the snapshot carries (axe.AxeAnswer.lost)."""
    root = page.soup.find("html")
    root = root if isinstance(root, Tag) else None
    out = []
    why = ("the page removed or moved their elements before the capture, or "
           f"there were more than {MAX_ELEMENTS:,} elements to record")
    if entry["f"]:
        n = entry["f"]
        out.append(_f(rule_id, FAIL, entry["i"] or SERIOUS,
                      f"axe-core found {n} more violation{'s' if n > 1 else ''} "
                      "of this rule on the page that the capture could not "
                      f"attach to an element: {why}. [axe-core {AXE_VERSION} "
                      f"{axe_rule}]", root))
    if entry["r"]:
        n = entry["r"]
        out.append(_f(rule_id, NEEDS_REVIEW, MINOR,
                      f"axe-core could not decide {n} more result"
                      f"{'s' if n > 1 else ''} of this rule on the page, which "
                      "the capture could not attach to an element "
                      f"({why}); they need a person's review. [axe-core "
                      f"{AXE_VERSION} {axe_rule}]", root))
    return out


def _xml_lang_only(el: Tag, page: PageContext) -> bool:
    """Can only the element's xml:lang explain a valid-lang failure?
    axe-core reads lang and xml:lang alike, and W3C's ACT rule de46e4 tests
    lang alone: in an HTML document browsers and assistive technology
    ignore xml:lang. Yes when xml:lang is set and lang is absent, empty or
    names a registered language (Part R2 review, L60). In an XML document
    xml:lang sets the language: never."""
    if page.reader == "xml" or el.get("xml:lang") is None:
        return False
    lang = (el.get("lang") or "").strip()
    return not lang or lang.split("-")[0].lower() in PRIMARY_LANGUAGE_SUBTAGS


def _xml_lang_message(el: Tag) -> str:
    value = _quoted(" ".join(str(el.get("xml:lang")).split()), 40)
    lang = ("absent" if el.get("lang") is None
            else "valid" if el.get("lang").strip() else "empty")
    return (f"xml:lang=\"{value}\" is not a valid language tag, but in an "
            "HTML document browsers and assistive technology ignore "
            f"xml:lang, and this element's lang is {lang}: not a 3.1.2 "
            "failure (W3C's ACT rule de46e4 tests lang only). Correct or "
            f"remove it. [axe-core {AXE_VERSION} valid-lang]")


#: What W3C's ACT rule 8fc3b6 requires an <object> to name: one that
#: renders an image, audio or video. Read from its type, or without one
#: from its data URL: the media type a data: URL states, or a file's
#: extension (H6-2, R5G-7).
_MEDIA_TYPE = re.compile(r"\s*(?:image|audio|video)/", re.IGNORECASE)
_MEDIA_EXTENSION = re.compile(
    r"\.(?:apng|avif|bmp|cur|gif|heic|heif|ico|jfif|jpe?g|jxl|pjpeg|pjp|png"
    r"|svgz?|tiff?|webp|aac|aiff?|flac|m4a|mid|midi|mp3|oga|ogg|opus|wav"
    r"|weba|wma|3g2|3gp|avi|flv|m4v|mkv|mov|mp4|mpe?g|ogv|webm|wmv)$",
    re.IGNORECASE)


def _object_shows_media(el: Tag) -> bool:
    """Does the <object> say it renders an image, audio or video? Its
    type decides; without one, its data URL: the media type a data: URL
    states, or the file's extension."""
    kind = el.get("type")
    if isinstance(kind, str) and kind.strip():
        return bool(_MEDIA_TYPE.match(kind))
    data = el.get("data")
    if not isinstance(data, str):
        return False
    data = data.strip()
    if data[:5].lower() == "data:":
        # data:[<media type>][;base64],<data>
        return bool(_MEDIA_TYPE.match(data[5:].split(",", 1)[0]))
    try:
        path = urllib.parse.urlsplit(data).path
    except ValueError:
        return False
    return bool(_MEDIA_EXTENSION.search(path))


def _object_message(res: dict) -> str:
    return ("<object> has no accessible name, and neither its type nor its "
            "file says it shows an image, audio or video, which is what W3C's "
            "ACT rule 8fc3b6 requires a name for (1.1.1). If it shows "
            "non-text content, name it (aria-label, aria-labelledby or "
            f"title). [axe-core {AXE_VERSION} object-alt]")


def _check_for(rule_id: str, axe_rule: str):
    def check(page: PageContext) -> RuleResult | None:
        run, by_rule = axe_state(page)
        if run is None:
            return None                  # no browser run: not evaluated
        hidden = root_hidden(page)
        if hidden and axe_rule == "aria-hidden-body":
            # Said in Bellbriar's words, for <html> too, which axe-core's
            # rule does not check (R5G-1).
            r = RuleResult(rule_id, applicable=True)
            for el in hidden:
                r.findings.append(_f(rule_id, NEEDS_REVIEW, MODERATE,
                                     _root_hidden_message(
                                         el, axe_skipped(page)), el,
                                     limit=MAX_MESSAGE))
            return r
        # Part of the snapshot axe-core did not check (in closed shadow
        # roots it was not given, or what it took as hidden: R5I-7): only
        # what it found is a result there.
        blind = run["unchecked"] > 0 or axe_skipped(page)
        if axe_rule in run["inapplicable"]:
            return None if blind else RuleResult(rule_id, applicable=False)
        if axe_rule not in run["applicable"]:
            return None                  # the run did not include it
        r = RuleResult(rule_id, applicable=True)
        for el, res in by_rule.get(axe_rule, ()):
            verdict = FAIL if res["v"] == "fail" else NEEDS_REVIEW
            if (verdict == FAIL and axe_rule == "valid-lang"
                    and _xml_lang_only(el, page)):
                r.findings.append(_f(rule_id, NEEDS_REVIEW, MINOR,
                                     _xml_lang_message(el), el,
                                     limit=MAX_MESSAGE))
                continue
            if (verdict == FAIL and axe_rule == "object-alt"
                    and isinstance(el, Tag) and el.name == "object"
                    and not _object_shows_media(el)):
                # An embedded page or document is outside 8fc3b6 (H6-2).
                r.findings.append(_f(rule_id, NEEDS_REVIEW, MODERATE,
                                     _object_message(res), el))
                continue
            # Cut after the run's secrets are replaced in it (R5L-2).
            r.findings.append(_f(rule_id, verdict, res["i"], res["m"], el,
                                 limit=MAX_MESSAGE))
        entry = run["unplaced"].get(axe_rule)
        if entry:
            r.findings.extend(_unplaced(rule_id, axe_rule, entry, page))
        if blind and not any(f.verdict == FAIL for f in r.findings):
            return None
        return r
    check.__name__ = "check_" + rule_id[3:].replace("-", "_")
    check.__doc__ = (f"{rule_id}: axe-core's {axe_rule}, as the rendered "
                     "capture recorded it (checks_rendered).")
    return check


def _int(value) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) \
        and 0 <= value <= 10 ** 7 else None


def _reflow_run(page: PageContext) -> dict | None:
    """The capture's reflow measurement at its narrow viewport, from the
    root element (model.reflow_run_attr), or None."""
    attr = page.provenance_attr or PROVENANCE_ATTR.get()
    root = page.soup.find("html") if attr else None
    if not (isinstance(root, Tag) and root.has_attr(reflow_run_attr(attr))):
        return None
    try:
        run = json.loads(root.get(reflow_run_attr(attr)))
    except (TypeError, ValueError):
        return None
    if not isinstance(run, dict) or not isinstance(run.get("clipped"), bool):
        return None
    out = {k: _int(run.get(k)) for k in ("width", "height", "scroll_width",
                                         "client_width")}
    if not (all(v is not None for v in out.values())
            and out["client_width"] > 0):
        return None
    out["clipped"] = run["clipped"]
    return out


def check_reflow(page: PageContext) -> RuleResult | None:
    """1.4.10 — at 320 CSS pixels wide the page reflows: nothing makes it
    scroll sideways (L24). After the capture the page is narrowed to that
    width (fetch.NARROW_VIEWPORT), and the capture records the page's
    scroll width and each outermost element that reaches past its right
    edge, outside any element that clips or scrolls sideways and not fixed
    to the viewport, with what in it reaches that far:

    * text or a form control: a FAIL, as a probable failure (heuristic);
    * only content that needs two dimensions, which WCAG 1.4.10 exempts (a
      table, an image, a map, code): a review;
    * nothing it shows, only its box (empty space, a background): a minor
      review.

    A page that hides what reaches past its edge (overflow-x: hidden or
    clip on the root element or the body, which the viewport takes) cannot
    scroll sideways, and is not reported: content cut off there is not
    detected (L45). No record, no result: the rule was not evaluated (a
    file run, or a capture that could not narrow the page)."""
    run = _reflow_run(page)
    if run is None:
        return None
    r = RuleResult("bb-reflow-320", applicable=True)
    sw, cw = run["scroll_width"], run["client_width"]
    if run["clipped"] or sw <= cw + 1:
        return r
    attr = page.provenance_attr or PROVENANCE_ATTR.get()
    name = reflow_attr(attr)
    width = run["width"]
    for el in page.soup.find_all(attrs={name: True}):
        try:
            mark = json.loads(el.get(name))
        except (TypeError, ValueError):
            continue
        if not isinstance(mark, dict) or mark.get("k") not in ("c", "x", "e"):
            continue
        right = _int(mark.get("r"))
        reach = (f"reaches {right} px across, past the page's {cw} px"
                 if right is not None else f"reaches past the page's {cw} px")
        if mark["k"] == "x":
            r.findings.append(_f(
                "bb-reflow-320", NEEDS_REVIEW, MODERATE,
                f"At {width} CSS pixels wide this element {reach}, so the "
                "page scrolls sideways, and what reaches that far is a "
                "table, image, map or code, which may need two dimensions: "
                "WCAG 1.4.10 exempts content that does. Check that it does, "
                "and that everything else reflows.", el))
        elif mark["k"] == "e":
            r.findings.append(_f(
                "bb-reflow-320", NEEDS_REVIEW, MINOR,
                f"At {width} CSS pixels wide this element {reach}, so the "
                "page scrolls sideways, though no text or control in it "
                "reaches that far: check what does (a background, empty "
                "space), and make the element fit.", el))
        else:
            r.findings.append(_f(
                "bb-reflow-320", FAIL, SERIOUS,
                f"At {width} CSS pixels wide this element {reach}, and text "
                "or a control in it reaches that far, so the page scrolls "
                "sideways: content must reflow to fit without scrolling in "
                "two directions (WCAG 1.4.10).", el))
    if not r.findings:
        root = page.soup.find("html")
        r.findings.append(_f(
            "bb-reflow-320", FAIL, SERIOUS,
            f"At {width} CSS pixels wide the page is {sw} px wide, "
            f"{sw - cw} px more than fits, so it scrolls sideways (WCAG "
            "1.4.10); the element that makes it so could not be located "
            "(text, a pseudo-element, or more than the 50 recorded).",
            root if isinstance(root, Tag) else None))
    return r


#: The checks that read a rendered capture's records, by rule id: one per
#: axe-core rule a capture runs (axe.AXE_RULES), and Bellbriar's own
#: reflow check (bb-reflow-320).
RENDERED_CHECKS = {rule_id: _check_for(rule_id, axe_rule)
                   for rule_id, axe_rule in AXE_RULES.items()}
RENDERED_CHECKS["bb-reflow-320"] = check_reflow
