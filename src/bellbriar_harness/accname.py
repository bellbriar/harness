"""Static approximation of accessible-name computation.

The normative algorithm is w3.org/TR/accname/; a faithful implementation
requires the live accessibility tree and CSS (display:none, visibility,
::before content, etc.), which belongs to the browser layer. This module
implements the subset that is decidable from markup alone, plus what a
rendered capture records about stylesheet hiding, in spec order:

  1. aria-labelledby (resolved, concatenated)
  2. aria-label
  3. host-language semantics (alt, associated <label>, control value,
     subtree contents for links/buttons, <svg><title>)
  4. title attribute

Name from content (step 2F) computes each *child's* text alternative with
the same steps, so a child's aria-labelledby, aria-label, alt, svg <title>
or title contributes — `<a href><svg aria-label="Home">` is named "Home".
Ignoring child names failed labelled icon links and buttons as empty.

Chromium 141 reads less into a name from content: of an <article>, a
<figure>, a <math> and the like, only their own name (L92, L115).
static_accname(chromium=True) reads a name so, and chromium_cut says
which element's content alone names a control that has no name there.

It is used only to assert *presence* of a name (empty vs non-empty), never
to grade name *quality* — quality is a judge-layer question.
"""
from __future__ import annotations

import re

from bs4.element import NavigableString, PreformattedString, Tag

from .model import CURRENT_PAGE, PROVENANCE_ATTR, view_hidden_attr
from .style import (cascade_decides, first_summary as _first_summary,
                    namespace_of, skips_content, ua_hidden)


def _norm(s: str | None) -> str:
    return " ".join((s or "").split())


_TEXTLESS = ("script", "style", "template", "noscript")
#: Elements the browser's own stylesheet never renders (the HTML standard's
#: rendering section), whose text is no element's name: a <datalist> or a
#: ruby <rp> inside a button, a <title> outside SVG. A capture leaves them
#: unmarked; they are hidden by what they are.
_NEVER_RENDERED = frozenset(("area", "base", "basefont", "datalist", "head",
                             "link", "meta", "noembed", "noframes", "param",
                             "rp"))

HIDDEN, INVISIBLE, SHOWN = "hidden", "invisible", "shown"


def _in_svg(node: Tag) -> bool:
    return any(isinstance(p, Tag) and p.name == "svg" for p in node.parents)


#: Where _svg_element remembers its answer for an element.
_SVG_MEMO = "_bb_svg_element"


def _svg_element(node: Tag) -> bool:
    """Is `node` an element of an SVG drawing inside the page (not the
    outermost <svg> itself, nor HTML inside its <foreignObject>)? The
    nearest <svg> or <foreignObject> above it decides. Remembered for it
    and each ancestor passed on the way, which ask the same: a deep page
    costs its depth once, not once per element (R6U-8)."""
    got = node.__dict__.get(_SVG_MEMO)
    if got is not None:
        return got
    passed = [node]
    p = node.parent
    while True:
        if not isinstance(p, Tag) or (p.name or "").lower() \
                == "foreignobject":
            got = False
            break
        if p.name == "svg":
            got = True
            break
        got = p.__dict__.get(_SVG_MEMO)
        if got is not None:
            break
        passed.append(p)
        p = p.parent
    for n in passed:
        n.__dict__[_SVG_MEMO] = got
    return got


def document_root(node: Tag) -> bool:
    """Is `node` the document's <html>, or its <body>? WAI-ARIA tells
    browsers not to expose aria-hidden on the document's root, and
    Chromium (141, tested), Firefox (from 139) and WebKit (from 2024) ignore
    it on both: the page stays in the accessibility tree (L72-4)."""
    parent = node.parent
    if node.name == "html":
        return not isinstance(parent, Tag) or parent.name == "[document]"
    return (node.name == "body" and isinstance(parent, Tag)
            and parent.name == "html" and document_root(parent))


def aria_hidden(node: Tag) -> bool:
    """aria-hidden="true" on `node`, as browsers read it: not on the
    document's <html> or <body>, where they ignore it (document_root)."""
    return ((node.get("aria-hidden") or "").strip().lower() == "true"
            and not document_root(node))


def at_state(node: Tag) -> str | None:
    """How a descendant takes part in its ancestor's name: HIDDEN (nothing
    in it is read), INVISIBLE (visibility:hidden: its own text and
    attributes are not read, but a descendant made visible again is),
    SHOWN (made visible again inside invisible content), or None (as its
    parent).

    HIDDEN, whatever the run: aria-hidden="true", `inert`, script, style,
    template and noscript content, and what a browser never renders
    (<datalist>, <rp>, <title> outside SVG, and the like), a drawing's
    <title> and <desc> (subtree_text reads a <desc> through
    aria-labelledby). In a rendered
    run that recorded what the page hides (model.hidden_attr, or the
    narrow record the rules read now: model.view_hidden_attr), that record
    decides the rest, stylesheets included: "display" is HIDDEN,
    "visibility" and "visibility-skips" INVISIBLE, "shown" and
    "shown-skips" SHOWN; "unrendered" and "unboxed", a part of a drawing
    or of MathML that is not rendered but that Chromium 141 names read
    (subtree_text reads an "unboxed" one only where no part whose role is
    group stands between it and the name's start, nearer than another
    <a>: _boxless_cut, R6C-3, and nothing a part whose role is group (a
    <g>, an <a> that is no link) with no box holds: _boxless_holds, R6I-4;
    Chromium reads MathML through aria-labelledby, and none into a name
    from content, where the runs read it: a control so named is reviewed,
    chromium_cut, L92), as their parent;
    "unrendered-visibility" and "unboxed-visibility", one that is
    invisible too, or an element invisible inside one, INVISIBLE (R6E-4).
    Elsewhere markup does: a closed <details>' content but its first
    summary is HIDDEN; so is a drawing's element Chromium 141 never
    renders nor reads into a name, as markup shows it (_drawing_left_out:
    one whose own conditions fail, R6M-7; an element it does not know, a
    <metadata>, a <use>, an animation's, a filter primitive outside a
    <filter>; a <tspan> outside a <text>; a <g> in a <text>); the
    `hidden` attribute (on an HTML element), a closed <dialog> or popover
    are HIDDEN unless the page sets a display on them; and the style
    attribute and the page's own <style> rules together, as the cascade
    orders them (style.cascade_decides: a rule's !important beats the
    attribute, R5K-5), decide the rest: display:none HIDDEN (but on a
    drawing's <g> or <marker>, whose content Chromium 141 names read:
    R6C-3, R6G-3), visibility:hidden INVISIBLE (a MathML <mphantom> too,
    as the browser's own stylesheet has it), visibility:visible SHOWN
    (H6-4). An element hidden="until-found" or content-visibility:hidden
    takes part as it is (it is rendered), and subtree_text reads nothing
    it holds where that is skipped (style.skips_content: not on a box
    Chromium 141 names from what it holds, an inline one, a table:
    R5K-10, R5O-7); a capture marks such an element "skips" (or
    "shown-skips", "visibility-skips"). accname step 2A skips hidden
    content unless it is the node directly referenced by aria-labelledby,
    which callers handle by passing that node as the root (and
    subtree_text reads what such a node holds as Chromium 141 does:
    _target_mode).

    Only descendants are tested (the root never is), so the name an element
    has when it is shown is still computed while it is hidden: a link in a
    closed menu keeps its text."""
    if aria_hidden(node) or node.has_attr("inert"):
        return HIDDEN
    return _drawn_state(node)


def _drawn_state(node: Tag) -> str | None:
    """at_state as rendering alone decides it: aria-hidden and `inert`
    aside, which _target_mode reads apart."""
    if (node.name in _TEXTLESS or node.name in _NEVER_RENDERED
            # A <title> is never content: outside SVG it is rendered
            # nowhere, and in a drawing it, or a <desc>, names or describes
            # its parent (_native_text), as SVG-AAM has it (R5I-6); through
            # aria-labelledby, subtree_text reads a <desc>'s text (R6O-2).
            or node.name == "title"
            or (node.name == "desc" and _in_svg(node))):
        return HIDDEN
    page = CURRENT_PAGE.get()
    attr = PROVENANCE_ATTR.get()
    if page is not None and page.hiding_recorded and attr:
        return _MARK_STATES.get(node.get(view_hidden_attr(attr)))
    parent = node.parent
    if (isinstance(parent, Tag) and parent.name == "details"
            and not parent.has_attr("open")
            and node is not _first_summary(parent)):
        return HIDDEN       # a closed <details>' content, as a capture has it
    if _drawing_left_out(node):
        return HIDDEN       # as a capture marks it: "display"
    # The style attribute and the page's own <style> rules, as far as a run
    # without a browser reads them (style.PageStyles): text they hide names
    # nothing, as in a rendered run (H6-4).
    styles = page.styles() if page is not None else None
    display = cascade_decides(styles, node, "display")
    if (display is False and not (node.name in ("g", "marker")
                                  and namespace_of(node) == "svg")) \
            or (ua_hidden(node) and display is not True):
        return HIDDEN
    visibility = cascade_decides(styles, node, "visibility")
    if visibility is False:
        return INVISIBLE    # a MathML <mphantom> too (style.ua_invisible)
    if visibility is True:
        return SHOWN
    return None


#: The elements of a drawing Chromium 141 knows (measured: one of any
#: other name is a plain SVGElement, which it never renders).
_SVG_KNOWN = frozenset((
    "a", "animate", "animateMotion", "animateTransform", "circle",
    "clipPath", "defs", "desc", "ellipse", "feBlend", "feColorMatrix",
    "feComponentTransfer", "feComposite", "feConvolveMatrix",
    "feDiffuseLighting", "feDisplacementMap", "feDistantLight",
    "feDropShadow", "feFlood", "feFuncA", "feFuncB", "feFuncG", "feFuncR",
    "feGaussianBlur", "feImage", "feMerge", "feMergeNode", "feMorphology",
    "feOffset", "fePointLight", "feSpecularLighting", "feSpotLight",
    "feTile", "feTurbulence", "filter", "foreignObject", "g", "image",
    "line", "linearGradient", "marker", "mask", "metadata", "mpath", "path",
    "pattern", "polygon", "polyline", "radialGradient", "rect", "script",
    "set", "stop", "style", "svg", "switch", "symbol", "text", "textPath",
    "title", "tspan", "use", "view"))
_SVG_KNOWN_LOWER = frozenset(n.lower() for n in _SVG_KNOWN)
#: A drawing's elements Chromium 141 never renders, with what they hold.
_SVG_UNDRAWN = frozenset(("metadata", "view", "use", "animate", "set",
                          "animatemotion", "animatetransform", "mpath"))
#: The parts of a <text> (_svg_never_read).
_SVG_TEXT_PARTS = ("text", "tspan", "textpath")


def _svg_known(node: Tag) -> bool:
    """Does Chromium 141 know `node`, a drawing's element, by its name: as
    written in an XML document, in any case elsewhere (an HTML parser
    writes it so, a capture's reader in lower case)?"""
    if getattr(CURRENT_PAGE.get(), "reader", "html") == "xml":
        return node.name in _SVG_KNOWN
    return (node.name or "").lower() in _SVG_KNOWN_LOWER


def _drawing_left_out(node: Tag) -> bool:
    """Is `node` a drawing's element (not its outermost <svg>) that Chromium
    141 never renders and reads into no name, as markup shows it (a
    rendered capture marks it "display"): one whose own conditions fail
    (checks_static._svg_fails, R6M-7), one Chromium does not know
    (_SVG_KNOWN: an <rdf:RDF> in an HTML document), a <metadata>, a
    <view>, a <use>, an animation's element, a filter primitive whose
    parent is no <filter>, and what _svg_never_read names (each measured:
    R6M round 7)? Read with what it holds where an aria-labelledby target
    is hidden, but what _svg_never_read names (_target_mode)."""
    parent = node.parent
    if namespace_of(node) != "svg" or not isinstance(parent, Tag) \
            or namespace_of(parent) != "svg":
        return False        # no drawing's part, or its outermost <svg>
    name = (node.name or "").lower()
    if not _svg_known(node) or name in _SVG_UNDRAWN or (
            name.startswith("fe") and (parent.name or "").lower()
            != "filter"):
        return True
    from .checks_static import _svg_fails
    return _svg_fails(node) or _svg_never_read(node)


def _svg_never_read(node: Tag, hidden: bool = False) -> bool:
    """Is `node` held by a drawing's element so that Chromium 141 reads it
    into no name, an aria-labelledby target hidden or not (measured: R6M
    round 7): what a <use> holds, and what a <text>'s part holds that is
    none of its own (a <g> in a <text>, in an <a> in one too: an <a> holds
    what the element that holds it may hold, R6O-3)? A <tspan> or a
    <textPath> whose parent is neither a <text>'s part nor an <a> too, but
    in a target that is hidden (`hidden`), where it is read (measured:
    R6Q-8)."""
    parent = node.parent
    if not isinstance(parent, Tag) or namespace_of(parent) != "svg":
        return False
    holder = (parent.name or "").lower()
    own = (node.name or "").lower() if namespace_of(node) == "svg" else ""
    if holder == "use":
        return True
    if own in ("tspan", "textpath"):
        return (not hidden and holder not in _SVG_TEXT_PARTS
                and holder != "a")
    if own in _SVG_TEXT_PARTS + ("a", "title", "desc"):
        return False
    while holder == "a" and isinstance(parent.parent, Tag) \
            and namespace_of(parent.parent) == "svg":
        parent = parent.parent
        holder = (parent.name or "").lower()
    return holder in _SVG_TEXT_PARTS


#: A capture's marks for an element that skips what it holds
#: (model.hidden_attr): "shown-skips" is one made visible again too,
#: "visibility-skips" one that is invisible too (R5O-5).
_SKIPS_MARKS = ("skips", "shown-skips", "visibility-skips")
#: How a capture's mark takes part in a name (at_state).
_MARK_STATES = {"display": HIDDEN, "visibility": INVISIBLE, "shown": SHOWN,
                "shown-skips": SHOWN, "visibility-skips": INVISIBLE,
                "unrendered-visibility": INVISIBLE,
                "unboxed-visibility": INVISIBLE}
#: The marks of a drawing's part that has no box (_boxless_cut).
_UNBOXED_MARKS = ("unboxed", "unboxed-visibility")


def _record_name() -> str | None:
    """The attribute the capture's record of what the page hides is read
    from now (model.view_hidden_attr), or None where there is none."""
    page = CURRENT_PAGE.get()
    attr = PROVENANCE_ATTR.get()
    return (view_hidden_attr(attr) if page is not None
            and page.hiding_recorded and attr else None)


def _skips(node: Tag, record: str | None) -> bool:
    """Does `node` skip what it holds: by the capture's record where there
    is one ("skips"), else as markup shows it (style.skips_content)? A
    <textarea>'s text is its value, never skipped, whatever an older
    capture marked (R5P-4, R5R-8)."""
    if node.name in ("textarea", "input") and namespace_of(node) == "html":
        return False
    if record:
        return node.get(record) in _SKIPS_MARKS
    return skips_content(node)


def _in_skipped(node: Tag, record: str | None) -> bool:
    """Is `node` inside what a rendered ancestor skips: one that skips what
    it holds (_skips), or a closed <details>, of which only the first
    <summary> is rendered (markup decides that, in a rendered run too)? It
    is not rendered, and Chromium 141 reads no name from it, also through
    aria-labelledby, where it reads a display:none ancestor's (R5M-1,
    R5O-2). Such an ancestor that is not rendered itself (it, or one above
    it, is display:none: _drawn_state's HIDDEN) skips nothing, and
    Chromium reads what it holds (measured: R6M round 7). What renders is
    asked only above an ancestor that skips (R6O-1)."""
    child = node
    skipped = False
    for anc in node.parents:
        if not isinstance(anc, Tag) or anc.name == "[document]":
            break
        if _skips(anc, record) or (
                anc.name == "details" and not anc.has_attr("open")
                and child is not _first_summary(anc)):
            skipped = True
        if skipped and _drawn_state(anc) == HIDDEN:
            skipped = False     # what skips at or below it is not rendered
        child = anc
    return skipped


#: How subtree_text reads an aria-labelledby target (_target_mode).
_SHOWN_TARGET, _HIDDEN_TARGET, _UNRENDERED_TARGET = 0, 1, 2


def _target_mode(target: Tag) -> int:
    """How Chromium 141 reads what an aria-labelledby target holds
    (measured: R6M-1, round 7). _UNRENDERED_TARGET where it, or an
    ancestor, is not rendered (_drawn_state's HIDDEN: display:none, the
    hidden attribute, a closed <dialog> or popover, a drawing's element
    Chromium never renders; not a drawing's <g> or <marker> with
    display:none, nor what a <defs> holds): every descendant is read,
    hidden, invisible or skipped, but what is never content
    (_never_content). _HIDDEN_TARGET where it is rendered but invisible
    (the nearest visibility set, its own or an ancestor's, is hidden or
    collapse), or it or an ancestor is aria-hidden or `inert`: so too, but
    what a descendant skips (content-visibility:hidden, a closed
    <details>) is not read. _SHOWN_TARGET elsewhere: as a name from
    content is read, but that an invisible descendant keeps what is made
    visible again inside it out (_opens_group). Where a run without a
    capture's record cannot tell whether it is rendered (it, or an
    ancestor, is a drawing's element with a systemLanguage, which the
    reader's languages decide), _UNRENDERED_TARGET, which reads the
    most. Remembered per target and record (subtree_text asks only where
    the answer matters: R6O-1)."""
    record = _record_name()
    memo = target.__dict__.setdefault("_bb_target_mode", {})
    if record not in memo:
        memo[record] = _target_mode_of(target, record is None)
    return memo[record]


def _target_mode_of(target: Tag, unread: bool) -> int:
    """_target_mode, worked out (`unread`: no capture's record)."""
    mode = _SHOWN_TARGET
    visibility = None
    for node in (target, *target.parents):
        if not isinstance(node, Tag) or node.name == "[document]":
            break
        if aria_hidden(node) or node.has_attr("inert"):
            mode = _HIDDEN_TARGET
        state = _drawn_state(node)
        if state == HIDDEN or (unread and _language_decides(node)):
            return _UNRENDERED_TARGET
        if visibility is None and state in (INVISIBLE, SHOWN):
            visibility = state
    return _HIDDEN_TARGET if visibility == INVISIBLE else mode


def _language_decides(node: Tag) -> bool:
    """Is `node` a drawing's element whose systemLanguage Chromium 141
    reads (checks_static._SVG_TESTS), which decides whether it is
    rendered?"""
    if namespace_of(node) != "svg":
        return False
    from .checks_static import _SVG_TESTS, _svg_attr
    return ((node.name or "").lower() in _SVG_TESTS
            and _svg_attr(node, "systemLanguage") is not None)


def _never_content(node: Tag) -> bool:
    """Is `node` read into no name, inside an aria-labelledby target that
    is hidden too (_target_mode): what a browser never renders (a
    <datalist>; not an <rp>, whose text is read there: measured, R6M
    round 7), a <title>, and what _svg_never_read names there (not a
    <tspan> or <textPath> outside a <text>, which is read: R6Q-8)? (A
    drawing's <desc> is read apart: subtree_text, R6O-2.)"""
    if node.name in _NEVER_RENDERED:
        return node.name != "rp"
    return node.name == "title" or (namespace_of(node) == "svg"
                                    and _svg_never_read(node, True))


def hidden_from_at(node: Tag) -> bool:
    """A descendant assistive technology does not read at all, or reads
    nothing of its own (at_state): HIDDEN or INVISIBLE."""
    return at_state(node) in (HIDDEN, INVISIBLE)


def labelledby_attr(node: Tag) -> str | None:
    """The attribute `node`'s aria-labelledby is read from: aria-labelledby,
    or, without one, aria-labeledby, which Chromium 141 reads as the same
    (R5K-15); None for neither."""
    for attr in ("aria-labelledby", "aria-labeledby"):
        if node.has_attr(attr):
            return attr
    return None


def _labelledby_ids(node: Tag) -> list[str]:
    attr = labelledby_attr(node)
    return (node.get(attr) or "").split() if attr else []


def _reach(ids, node: Tag) -> dict:
    """The ids `node`'s own tree holds (checks_static.IdScopes.within): an
    aria-labelledby or a <label for> reaches nothing in another tree, the
    document's or another shadow root's. A plain {id: element} map is the
    one tree."""
    within = getattr(ids, "within", None)
    return within(node) if within is not None else ids


def _tree_key(ids, node: Tag) -> int:
    key = getattr(ids, "key", None)
    return key(node) if key is not None else 0


def _referenced_text(target: Tag, ids: dict[str, Tag] | None,
                     _seen: set | None = None) -> str:
    """Text alternative of a node reached through aria-labelledby (2B).

    The referenced node is computed from step 2C on (its own aria-label and
    native semantics count; hidden or not, it contributes), and aria-labelledby
    is not followed again inside it (no chained or circular references). One
    inside what an ancestor skips (hidden="until-found", content-visibility:
    hidden) names nothing, as in Chromium 141, and a drawing with no
    <title> is read by its content (R5M-1, R5M-4). `_seen` collects the
    elements read (subtree_text), the target among them."""
    if _in_skipped(target, _record_name()):
        return ""
    if _seen is not None:
        _seen.add(id(target))
    label = _norm(target.get("aria-label"))
    if label:
        return label
    native = _native_text(target)
    if native is not None and not (native == ""
                                   and _untitled_drawing(target)):
        return native
    return (subtree_text(target, ids, _in_labelledby=True, _seen=_seen)
            or _norm(target.get("title")))


def _native_text(node: Tag) -> str | None:
    """Host-language name for elements whose name is not their content
    (step 2D). None means "compute from content"."""
    name = node.name
    if name == "img" or (name == "input"
                         and (node.get("type") or "").lower() == "image"):
        alt = node.get("alt")
        if alt is not None:
            return _norm(alt)        # alt="" is decorative: contributes nothing
        return _norm(node.get("title"))
    if name == "area":
        return _norm(node.get("alt")) or _norm(node.get("title"))
    if _svg_element(node) and name not in ("title", "desc"):
        # A part of a drawing (an <svg> inside one too: measured, R6C-3) is
        # named by its own <title> child, if it has one; a link of it then
        # by its xlink:title (Chromium 141's title of a drawing's link:
        # measured, R6F-1); else by its content (a <text>).
        return _svg_title(node)
    if name == "svg":
        # Its own <title> child (SVG-AAM), not one of a part's: Chromium
        # 141 names <svg><g><title>G</title></g></svg> nothing. A drawing
        # that skips what it holds (content-visibility:hidden) has no
        # <title> it reads (measured). One of white space alone names it
        # nothing, and nothing after it is read (R6I-3). One given a role
        # named from its content is named by its content, then its title
        # (_svg_content_role: R6O-4).
        t = _outer_title(node)
        if t is not None:
            return _norm(t.get_text())
        if _svg_content_role(node):
            return None
        return _norm(node.get("title"))
    return None


#: The roles that make Chromium 141 name an <svg> from its content, as it
#: names a link or a button from theirs (measured, R6O-4); one with any
#: other role (img, group, graphics-document, row and the like) or none
#: gives its own name alone.
_SVG_CONTENT_ROLES = frozenset((
    "button", "caption", "cell", "checkbox", "code", "columnheader",
    "definition", "deletion", "directory", "doc-backlink", "doc-biblioref",
    "doc-glossref", "doc-noteref", "emphasis", "generic", "gridcell",
    "heading", "insertion", "link", "list", "listitem", "mark", "math",
    "menuitem", "menuitemcheckbox", "menuitemradio", "meter", "option",
    "paragraph", "radio", "rowheader", "scrollbar", "searchbox", "slider",
    "spinbutton", "strong", "subscript", "superscript", "switch", "tab",
    "term", "textbox", "time", "tooltip", "treeitem"))


def _svg_content_role(node: Tag) -> bool:
    """Does `node`, a drawing's outermost <svg>, have a role it honors
    (checks_static._role_of) that names it from its content
    (_SVG_CONTENT_ROLES)?"""
    from .checks_static import _role_of
    return _role_of(node) in _SVG_CONTENT_ROLES


def _outer_title(node: Tag) -> Tag | None:
    """A drawing's outermost <svg>'s own <title> child that holds any text,
    white space alone too (Chromium 141 takes it, and reads no further:
    R6I-3); None where it has none, or skips what it holds."""
    if _skips(node, _record_name()):
        return None
    t = node.find("title", recursive=False)
    return t if t is not None and t.get_text() != "" else None


def _svg_title(node: Tag) -> str | None:
    """A drawing's part's name by its own <title> child, then, for a link,
    by its xlink:title: the first that holds any text, white space alone
    too, which Chromium 141 takes and reads no further (an empty name:
    measured, R6H-7); None where neither does (its content names it)."""
    t = node.find("title", recursive=False)
    raw = t.get_text() if t is not None else ""
    if raw == "" and node.name == "a":
        raw = node.get("xlink:title") or ""
    return _norm(raw) if raw != "" else None


def _untitled_drawing(node: Tag) -> bool:
    """Is `node` a drawing's outermost <svg> with no <title> it takes
    (_outer_title), whose _native_text "" means no name of its own? A
    title of white space is a name, and ends it (R6I-3)."""
    return (node.name == "svg" and not _svg_element(node)
            and _outer_title(node) is None)


def _presentational(node: Tag) -> bool:
    """Does a browser honor role="none" or "presentation" on `node`
    (ARIA's presentational role conflict resolution: not on an element
    that can take focus or carries a global ARIA attribute,
    checks_static._role_of)? Then an <img> is no image in the tree, and
    its alt names nothing, nor does a drawing's <title>, in Chromium (141)
    as in AccName (R5G-4, R5I-6)."""
    from .checks_static import _role_of
    return _role_of(node) in ("none", "presentation")


#: _child_text's answer for an element named by its content, or by its
#: title when the content gives nothing (step 2I).
_CONTENT_THEN_TITLE = object()


class _TitleFallback:
    """Marks where an element with a title began in the parts collected:
    when the walk is back above it and its content gave nothing, the title
    stands in; where `cut` is the element, whose title Chromium 141 does
    not read (_reads_title), it is added to the walk's cuts instead."""
    __slots__ = ("title", "start", "cut")

    def __init__(self, title: str, start: int, cut: Tag | None = None):
        self.title, self.start, self.cut = title, start, cut


def _child_text(node: Tag, ids: dict[str, Tag] | None,
                in_labelledby: bool):
    """A child element's own text alternative when an attribute or native
    semantics decide it; None means "descend into its content", and
    _CONTENT_THEN_TITLE "descend, and use its title if that gives
    nothing"."""
    if ids is not None and not in_labelledby:
        reach = _reach(ids, node)
        refs = [reach[t] for t in _labelledby_ids(node) if t in reach]
        if refs:
            text = _norm(" ".join(_referenced_text(t, ids) for t in refs))
            if text:
                return text
    label = _norm(node.get("aria-label"))
    if label:
        return label
    if (node.name or "").lower() == "foreignobject":
        # HTML inside a drawing names nothing the drawing is in, as in
        # Chromium 141 (R5K-3); aria-labelledby reads it (R5M-4).
        return None if in_labelledby else ""
    if (node.name in ("img", "svg") or _svg_element(node)) \
            and _presentational(node):
        # No image in the tree: its alt, or a drawing's <title>, names
        # nothing (R5G-4, R5I-6); a drawing's content still does, as in
        # Chromium 141 (<svg role="presentation"><text>Home</text></svg>
        # names its link "Home").
        return "" if node.name == "img" else None
    native = _native_text(node)
    if native is not None:
        if native == "" and in_labelledby and _untitled_drawing(node):
            return None     # aria-labelledby reads its content (R5M-4)
        return native
    if node.has_attr("title"):
        # Tooltip (step 2I) applies only when the content yields nothing.
        # Decided by the caller's walk: recursing here ran out of stack on
        # a few thousand nested titled elements.
        return _CONTENT_THEN_TITLE
    return None


def subtree_text(el: Tag, ids: dict[str, Tag] | None = None,
                 _in_labelledby: bool = False, _seen: set | None = None,
                 _skip: Tag | None = None, _chromium: bool = False,
                 _cuts: list | None = None, _axe: bool = False) -> str:
    """Text a screen reader would use from a subtree: text nodes, and each
    descendant element's own text alternative (its aria-labelledby when
    `ids` is given, aria-label, img alt, svg <title>, or title as a last
    resort). The root is always included (a directly referenced
    aria-labelledby target counts even when hidden); hidden descendants,
    comments, and script/style content are not.

    What an element skips (hidden="until-found", content-visibility:hidden:
    _skips), the root included, is not read; nor is a closed <details>'
    content but its first <summary>, loose text included (R5M-1). `_seen`
    collects the ids of the elements the walk reads, into or by their own
    name (R5O-9). Through aria-labelledby (`_in_labelledby`), the root,
    shown or not, is read, and what it holds as _target_mode says Chromium
    141 reads it: where the root is hidden, everything (R6M-1); where it is
    shown, nothing an invisible descendant holds, what is made visible
    again inside it neither, but where the descendant, or one between it
    and the root, has the role group (_opens_group: R6K-9, R6M round 7).

    With `_chromium`, not through aria-labelledby, a descendant whose
    content Chromium 141 reads into no name (_cuts_content: an <article>,
    a <figure>, a <math> and the like) gives only its own name (_cut_name),
    and one whose title it does not read (_reads_title: a <span>, a <div>,
    an <i>) no title; each that gave the accessible-name computation's
    walk what Chromium does not is added to `_cuts`, ("content", element)
    or ("title", element) (L92, L115). Without `_chromium`, `_cuts`
    collects ("maybe", element) for each element the walk meets that
    Chromium may read so, a first test. With `_axe`, MathML, an <object>,
    a <canvas>, a drawing and the like give only their own name, as
    axe-core 4.12 reads them (_embedded).

    This is the fix for a whole class of silent misses: a Material-Icons
    ligature in an aria-hidden <i>, or an HTML comment, used to become the
    control's "name" and a genuinely empty button passed as named.

    Iterative, so a pathologically deep subtree cannot exhaust Python's
    recursion limit and abort the whole run.
    """
    parts: list[str] = []
    # A capture's record says what is rendered (at_state), and which
    # elements skip what they hold ("skips": model.hidden_attr).
    record = _record_name()
    # How an aria-labelledby target is read (_target_mode): where it is
    # hidden, every descendant (and, where it is not rendered, what one
    # skips too); where it is shown, an invisible one keeps what is made
    # visible again inside it out, but past a part whose role is group.
    # Asked only where hidden content makes it matter (R6O-1).
    mode: list = [None]

    def target_mode() -> int:
        if mode[0] is None:
            mode[0] = _target_mode(el) if _in_labelledby else _SHOWN_TARGET
        return mode[0]
    # (node, is it the root, is it inside invisible content, is it inside
    # a drawing's part with no box: _UNBOXED_MARKS, is a part whose role is
    # group between it and the root: _opens_group)
    stack: list[tuple] = [(el, True, False, _in_unboxed(el, record), False)]
    while stack:
        node, is_root, invisible, boxless, grouped = stack.pop()
        if isinstance(node, _TitleFallback):
            if not _norm(" ".join(parts[node.start:])):
                del parts[node.start:]
                if node.cut is not None:
                    if node.title and _cuts is not None:
                        _cuts.append(("title", node.cut))
                elif node.title:
                    parts.append(node.title)
            continue
        if isinstance(node, Tag):
            if node.name in _TEXTLESS or node is _skip:
                continue
            unboxed = record is not None and node.get(record) in \
                _UNBOXED_MARKS
            if not is_root:
                if _in_labelledby and node.name == "desc" \
                        and namespace_of(node) == "svg":
                    # Through aria-labelledby, Chromium 141 reads the text a
                    # drawing's <desc> holds itself, hidden or not, where
                    # no part whose role is group stands between it and
                    # the target (measured: R6O-2).
                    if not grouped:
                        parts.extend(_own_text(node))
                    continue
                state = at_state(node)
                if state in (HIDDEN, INVISIBLE) and _in_labelledby \
                        and target_mode() != _SHOWN_TARGET:
                    # A hidden target: what is hidden is read too, but
                    # what is never content (measured: R6M-1, round 7).
                    if _never_content(node):
                        continue
                    state = None
                if state == HIDDEN \
                        or (unboxed and _boxless_cut(node, el, ids)) \
                        or ((boxless or unboxed)
                            and _boxless_holds(node, ids)):
                    # A drawing's part whose role is group (a <g>, an <a>
                    # that is no link), with no box, holds nothing a name
                    # reads, whatever it holds (measured: R6E-4, R6G-8,
                    # R6I-4).
                    continue
                if _in_labelledby and not grouped:
                    grouped = _opens_group(node, ids)
                if state == INVISIBLE:
                    if _in_labelledby and not grouped:
                        # Through aria-labelledby into a shown target,
                        # Chromium 141 reads nothing such invisible content
                        # holds, what is made visible again inside it
                        # neither, but past a part whose role is group
                        # (R6K-9, round 7).
                        continue
                    invisible = True
                elif state == SHOWN:
                    invisible = False
                if not invisible:
                    cuts = (not _in_labelledby
                            and (_chromium or _axe or _cuts is not None)
                            and (_embedded(node) if _axe
                                 else _cuts_content(node, ids)))
                    if cuts and (_chromium or _axe):
                        # Chromium 141 reads its own name alone (measured:
                        # L92, L115); axe-core 4.12 an embedded one's.
                        if _cuts is not None and _chromium:
                            _cuts.append(("content", node))
                        if _seen is not None:
                            _seen.add(id(node))
                        parts.append(_cut_name(node, ids))
                        continue
                    if cuts and _cuts is not None:
                        _cuts.append(("maybe", node))
                    own = _child_text(node, ids, _in_labelledby)
                    if own is _CONTENT_THEN_TITLE:
                        untitled = (not _in_labelledby and not _axe
                                    and (_chromium or _cuts is not None)
                                    and not _reads_title(node))
                        if untitled and not _chromium:
                            _cuts.append(("maybe", node))
                        title = ("" if _axe and not _axe_titles(node)
                                 else _norm(node.get("title")))
                        stack.append((_TitleFallback(
                            title, len(parts),
                            node if untitled and _chromium else None),
                            False, False, False, False))
                    elif own is not None:
                        if _seen is not None:
                            # Read, by its own name: an inner label the
                            # walk reached is read here once (R5O-9).
                            _seen.add(id(node))
                        parts.append(own)
                        continue
            else:
                native = _native_text(node)
                if native is not None and not (
                        native == "" and _in_labelledby
                        and _untitled_drawing(node)):
                    parts.append(native)
                    continue
            if _seen is not None:
                _seen.add(id(node))
            skips = _skips(node, record)
            closed = (not skips and node.name == "details"
                      and not node.has_attr("open"))
            if (skips or closed) and target_mode() == _UNRENDERED_TARGET:
                skips = closed = False      # nothing renders: all is read
            if skips:
                continue    # rendered, what it holds not (R5K-10, R5M-1)
            if node.name == "iframe" and namespace_of(node) == "html":
                # What an <iframe> holds is never rendered: its fallback
                # text names nothing, it neither (Chromium 141, axe-core
                # 4.12: measured, R6 round 9).
                continue
            if closed:
                # Closed: its first <summary> is all that is rendered.
                summary = _first_summary(node)
                if summary is not None:
                    stack.append((summary, False, invisible, boxless,
                                  grouped))
                continue
            # Inside invisible content only a descendant made visible again
            # (visibility:visible) is read, so the walk goes on.
            inside = boxless or unboxed
            for child in reversed(list(node.children)):
                stack.append((child, False, invisible, inside, grouped))
        elif isinstance(node, NavigableString) and not isinstance(
                node, PreformattedString):   # excludes Comment, CData, Doctype…
            if not invisible:
                parts.append(str(node))
    return _norm(" ".join(parts))


def _own_text(node: Tag) -> list:
    """The text nodes `node` holds itself (not its elements'), comments and
    CDATA aside."""
    return [str(c) for c in node.children if isinstance(c, NavigableString)
            and not isinstance(c, PreformattedString)]


#: The roles of an element of which Chromium 141 reads only its own name
#: into a name from content, none of what it holds (measured, each role in
#: a link and with an aria-label: L115): the landmarks, the documents and
#: the containers of other content (form only where named: _resolved_role).
#: A control's (combobox, listbox, progressbar, separator) reads none
#: either, but its value may name it, which the runs do not read (L101):
#: what it holds is read, as before.
_CUT_ROLES = frozenset((
    "alert", "alertdialog", "application", "article", "banner",
    "blockquote", "comment", "complementary", "contentinfo", "dialog",
    "document", "feed", "figure", "form", "grid", "group", "image", "img",
    "log", "main", "marquee", "menu", "menubar", "navigation", "note",
    "radiogroup", "row", "rowgroup", "search", "sectionfooter",
    "sectionheader", "status", "suggestion", "table", "tablist",
    "tabpanel", "timer", "toolbar", "tree", "treegrid",
    "graphics-document", "graphics-object", "graphics-symbol",
    "doc-abstract", "doc-acknowledgments", "doc-afterword",
    "doc-appendix", "doc-biblioentry", "doc-bibliography", "doc-chapter",
    "doc-colophon", "doc-conclusion", "doc-cover", "doc-credit",
    "doc-credits", "doc-dedication", "doc-endnote", "doc-endnotes",
    "doc-epigraph", "doc-epilogue", "doc-errata", "doc-example",
    "doc-footnote", "doc-foreword", "doc-glossary", "doc-index",
    "doc-introduction", "doc-notice", "doc-pagebreak", "doc-pagefooter",
    "doc-pageheader", "doc-pagelist", "doc-part", "doc-preface",
    "doc-prologue", "doc-pullquote", "doc-qna", "doc-subtitle", "doc-tip",
    "doc-toc"))

#: HTML's elements of which, with no role of their own given, Chromium 141
#: reads only the own name into a name from content (measured: L115): a
#: <header> wherever it is, an <aside> named or not, wherever it is, an
#: <object> (its fallback content neither, rendered or not). A <footer>, a
#: <section>, a <details> and a <marquee> are read; a <form> is not where
#: it is named, a <table> where it holds data (_cuts_content).
_CUT_ELEMENTS = frozenset(("address", "article", "aside", "blockquote",
                           "dialog", "fieldset", "figure", "header",
                           "hgroup", "main", "nav", "object", "output",
                           "search"))
#: The roles of an element whose title Chromium 141 does not read into a
#: name from content, its content empty (measured, each role in a link:
#: R6Q-5): text-level roles, generic and none, and a text field's (its
#: value names it).
_NO_TITLE_ROLES = frozenset((
    "caption", "code", "definition", "deletion", "emphasis", "generic",
    "insertion", "mark", "none", "paragraph", "presentation", "searchbox",
    "strong", "suggestion", "term", "textbox"))
#: HTML's elements whose title it does not read so, with no role of their
#: own given (measured, each in a link: R6Q-5, R6S-3, R6U-6): a <span>, a
#: <div>, an <i>, a <p>, a <font> and the like, an <a> with no href, a
#: <summary> outside a <details>, a <br>, the obsolete ones that are
#: generic (a <marquee>, an <acronym>, a <listing>); a <select> (its value
#: names it). An element HTML does not have (_HTML_ELEMENTS) is generic too.
_NO_TITLE_ELEMENTS = frozenset((
    "a", "acronym", "applet", "b", "bdi", "bdo", "bgsound", "big", "blink",
    "br", "caption", "center", "cite", "code", "data", "dd", "del", "dfn",
    "div", "dt", "em", "font", "frame", "i", "ins", "isindex", "kbd",
    "keygen", "listing", "map", "mark", "marquee", "menuitem", "multicol",
    "nextid", "nobr", "noembed", "p", "picture", "pre", "rb", "rtc", "s",
    "samp", "select", "selectedcontent", "slot", "small", "source", "spacer",
    "span", "strike", "strong", "summary", "tbody", "tfoot", "thead",
    "track", "tt", "u", "var", "xmp"))
#: Of those, the ones a draggable attribute, of any value, makes Chromium
#: read the title of, as an element HTML does not have (measured, each:
#: R6S-3, R6U-6); not an <a> with no href, a <p>, an <s>, a <code>, an
#: <em>, a <strong>, a <mark>, a <dfn>, a <dd>, a <slot>, a <map>.
_GENERIC_ELEMENTS = frozenset((
    "acronym", "applet", "b", "bdi", "bdo", "bgsound", "big", "blink",
    "center", "cite", "data", "div", "font", "i", "isindex", "kbd", "keygen",
    "listing", "marquee", "menuitem", "multicol", "nextid", "nobr",
    "picture", "pre", "rb", "rtc", "samp", "selectedcontent", "small",
    "source", "spacer", "span", "strike", "tt", "track", "u", "var", "xmp"))
#: The elements HTML has, and those Chromium 141 still knows (an <image>
#: the parser makes an <img>): an element of any other name, and of no
#: custom element's (_custom_element), is one Chromium reads as generic.
_HTML_ELEMENTS = frozenset("""
    a abbr acronym address applet area article aside audio b base basefont
    bdi bdo bgsound big blink blockquote body br button canvas caption
    center cite code col colgroup data datalist dd del details dfn dialog
    dir div dl dt em embed fencedframe fieldset figcaption figure font
    footer form frame frameset h1 h2 h3 h4 h5 h6 head header hgroup hr html
    i iframe img input ins isindex kbd keygen label legend li link listing
    main map mark marquee menu menuitem meta meter multicol nav nextid nobr
    noembed noframes noscript object ol optgroup option output p param
    picture plaintext pre progress q rb rp rt rtc ruby s samp script search
    section select selectedcontent slot small source spacer span strike
    strong style sub summary sup table tbody td template textarea tfoot th
    thead time title tr track tt u ul var video wbr xmp""".split())
#: Names with a hyphen that are no custom element's (HTML).
_NOT_CUSTOM = frozenset((
    "annotation-xml", "color-profile", "font-face", "font-face-src",
    "font-face-uri", "font-face-format", "font-face-name", "missing-glyph"))


#: A valid custom element name's characters past its first (HTML's
#: PCENChar).
_PCEN = ("-._0-9a-z\u00b7\u00c0-\u00d6\u00d8-\u00f6\u00f8-\u037d"
         "\u037f-\u1fff\u200c\u200d\u203f\u2040\u2070-\u218f"
         "\u2c00-\u2fef\u3001-\ud7ff\uf900-\ufdcf\ufdf0-\ufffd"
         "\U00010000-\U000effff")
_CUSTOM_NAME = re.compile(f"[a-z][{_PCEN}]*")


def _custom_element(name: str) -> bool:
    """Is `name` a custom element's, as HTML makes a valid one: a
    lower-case ASCII letter first, a hyphen, nothing but HTML's PCENChar
    (R6W-7), and not one of _NOT_CUSTOM?"""
    return ("-" in name and bool(_CUSTOM_NAME.fullmatch(name))
            and name not in _NOT_CUSTOM)     # linear: R6Y-4


#: What axe-core 4.12 counts embedded content, named only by its own name
#: in a name from content: MathML's <math>; HTML's <object>, <canvas>,
#: <iframe>, <video>, <audio> and <embed>; a drawing's <svg>.
_EMBEDDED = {"math": ("math",), "svg": ("svg",),
             "html": ("object", "canvas", "iframe", "video", "audio",
                      "embed")}
#: Their names, which a walk up a deep page tests first.
_EMBEDDED_NAMES = frozenset(n for names in _EMBEDDED.values() for n in names)


def _cuts_content(node: Tag, ids=None) -> bool:
    """Does Chromium 141 read none of what `node`, inside an element named
    from its content, holds into that name, but only its own (_cut_name;
    each measured, L92, L115)? A MathML <math>, whatever its role; an
    element whose role (one Chromium honors: _resolved_role) is one of
    _CUT_ROLES; with no such role, an HTML element of _CUT_ELEMENTS, a
    <form> that is named (_role_named), a <table> that holds data
    (_data_table), a drawing's <a> that is no link, outside a <text>
    (_group_role), or a <g> Chromium keeps (_kept_group). Not an HTML
    <img>, whose own name is its alt either way."""
    ns = namespace_of(node)
    if ns == "math":
        return node.name == "math"
    name = node.name or ""
    if ns == "html" and name == "img":
        return False
    role = _resolved_role(node, ids)
    if role:
        return role in _CUT_ROLES
    if ns == "html":
        if name in _CUT_ELEMENTS:
            return True
        if name == "form":
            return _role_named(node, ids)
        return name == "table" and _data_table(node)
    if ns == "svg":
        name = name.lower()
        if name == "a":
            return _group_role(node, True, ids)
        return name == "g" and _kept_group(node)
    return False


def _reads_title(node: Tag) -> bool:
    """Does Chromium 141 read the title of `node`, an element inside one
    named from its content, where its content gives nothing (measured: an
    empty element of each role and of HTML's elements in a link, R6Q-5,
    R6S-3, R6U-6)? It does where `node` has a tabindex Chromium parses
    (whatever its role), is a link (an <a> with an href), or is a custom
    element (_custom_element) whose role is not none or presentation; not
    where the role it honors (checks_static._role_of) is one of
    _NO_TITLE_ROLES, or, with no role given, an HTML element is one of
    _NO_TITLE_ELEMENTS or one HTML does not have (_HTML_ELEMENTS), which
    is generic (a <summary> only outside a <details>; one of
    _GENERIC_ELEMENTS, or one HTML does not have, only without a
    draggable attribute); else it does, a drawing's and MathML's elements'
    too, as the accessible-name computation does. Through
    aria-labelledby, it reads every title."""
    ns = namespace_of(node)
    from .checks_static import _role_of, _tabindex
    if ns != "html":
        # A drawing's text part only with a tabindex, a draggable
        # attribute or a role of its own (measured: R6W-8, R6Y-2, R6Y-3).
        if ns != "svg" or node.name not in ("text", "tspan", "textPath"):
            return True
        role = _role_of(node)
        return (_tabindex(node) is not None or node.has_attr("draggable")
                or (bool(role) and role in (node.get("role") or "").lower()
                    .split() and role not in _NO_TITLE_ROLES))
    name = node.name or ""
    if _tabindex(node) is not None or (name == "a"
                                       and node.has_attr("href")):
        return True
    role = _role_of(node)
    if _custom_element(name):
        return role not in ("none", "presentation")
    if role and role in (node.get("role") or "").lower().split():
        return role not in _NO_TITLE_ROLES
    if name == "summary":
        return isinstance(node.parent, Tag) and node.parent.name == "details"
    known = name in _HTML_ELEMENTS
    if (name in _GENERIC_ELEMENTS or not known) \
            and node.has_attr("draggable"):
        return True
    return known and name not in _NO_TITLE_ELEMENTS


def _embedded(node: Tag) -> bool:
    """Is `node` content axe-core 4.12 calls embedded (_EMBEDDED)?"""
    return (node.name or "").lower() in _EMBEDDED.get(namespace_of(node), ())


def _axe_titles(node: Tag) -> bool:
    """Does axe-core 4.12 read `node`'s title where its content gives no
    name (measured: R6S-1, R6U-1)? Not where the role it honors is none or
    presentation, nor where it holds a text node, of white space too
    (pretty-printed markup), that axe-core reads: not one that a hidden
    element holds, nor an invisible one (but where shown again), nor one
    inside embedded content (_embedded), of which it reads only the own
    name (an <svg>'s, a <canvas>'s). Nor that of a <slot> (measured:
    R6U-6)."""
    from .checks_static import _role_of
    if node.name == "slot" or _role_of(node) in ("none", "presentation"):
        return False
    stack = [(child, False) for child in node.children]
    while stack:
        child, invisible = stack.pop()
        if isinstance(child, Tag):
            state = at_state(child)
            if state == HIDDEN or _embedded(child):
                continue
            invisible = (invisible or state == INVISIBLE) and state != SHOWN
            stack.extend((c, invisible) for c in child.children)
        elif isinstance(child, NavigableString) and not isinstance(
                child, PreformattedString) and not invisible:
            return False
    return True


def _kept_group(node: Tag) -> bool:
    """Does Chromium 141 keep `node`, a drawing's <g> no role decides, in
    its tree as a group, whose content it reads into no name from content
    (measured: L115, R6Q-4)? Where the <g> can take focus (any tabindex),
    has an onclick, onmousedown or onmouseup, a lang, any aria-* attribute
    (aria-hidden="true" hides it), a <desc> child or a <title> child (an
    empty one too: one with text names it, its own name); not for its
    class, style, transform, id, `focusable`, xml:lang or onkeydown."""
    from .checks_static import _tabindex
    if _tabindex(node) is not None or any(
            a in ("onclick", "onmousedown", "onmouseup", "lang")
            or a.startswith("aria-") for a in node.attrs):
        return True
    return any(isinstance(c, Tag) and (c.name or "").lower() in ("desc",
                                                                 "title")
               and namespace_of(c) == "svg" for c in node.children)


def _data_table(table: Tag) -> bool:
    """Does Chromium 141 take `table`, an HTML <table> no role decides,
    for one of data, by its markup (each measured: L115)? In its order:
    where it has a summary or rules that is not empty, a <caption>,
    <thead>, <tfoot>, <col> or <colgroup> child, or twenty rows or more;
    not where it has no row, or one row of one cell; else where a cell
    (its rows' <td>s and <th>s) is a <th> or has headers, abbr, axis or
    scope that is not empty (a headers of white space alone, which the
    reader splits to nothing, is read as empty). What makes it one of data
    by its cells' borders and colors, which Chromium weighs too and a
    page's styles decide (a border or a bgcolor attribute among them,
    which a style may undo: R6Q-2), is not read: such a table is read as
    one of layout, whose content is read (L121)."""
    if table.get("summary") or table.get("rules"):
        return True
    rows = []
    for child in table.children:
        if not isinstance(child, Tag) or namespace_of(child) != "html":
            continue
        if child.name in ("caption", "thead", "tfoot", "col", "colgroup"):
            return True
        if child.name == "tr":
            rows.append(child)
        elif child.name == "tbody":
            rows.extend(r for r in child.children
                        if isinstance(r, Tag) and r.name == "tr")
    if len(rows) >= 20:
        return True
    cells = [[c for c in r.children if isinstance(c, Tag)
              and c.name in ("td", "th")] for r in rows]
    if not rows or (len(rows) == 1 and len(cells[0]) == 1):
        return False
    return any(cell.name == "th" or any(cell.get(a) for a in (
        "headers", "abbr", "axis", "scope")) for row in cells for cell in row)


def _cut_name(node: Tag, ids=None) -> str:
    """The own name Chromium 141 reads of `node`, an element whose content
    it reads into no name from content (_cuts_content; measured: L92,
    L115): its aria-labelledby, its aria-label, the name its markup gives
    it (an image's alt, a drawing's <title>; a <fieldset>'s first <legend>
    child, a <table>'s first <caption> child then its summary, an
    <output>'s <label>: _markup_name), then its title. Not a <figure>'s
    <figcaption>, a <math>'s alttext, nor any name of a drawing's <a> that
    is no link (its aria-label neither). axe-core 4.12 reads an embedded
    element's (_embedded) so too."""
    ns = namespace_of(node)
    if ns == "svg" and (node.name or "").lower() == "a":
        return ""
    own = _child_text(node, ids, False)
    if isinstance(own, str):
        return own
    if ns == "html":
        markup = _markup_name(node, ids)
        if markup:
            return markup
    return _norm(node.get("title"))


def _markup_name(node: Tag, ids=None) -> str:
    """The name an HTML <fieldset>, <table> or <output> has by its markup
    (_cut_name), "" where it has none: a <legend> or a <caption> as the
    accessible-name computation reads it, its aria-labelledby or
    aria-label first (measured: R6U-10), a <legend>'s title last (not a
    <caption>'s: R6W-4), but not one that is hidden or invisible (R6Q-6);
    a <table>'s summary where it has no <caption> (an empty or hidden one
    too: R6S-5); an <output>'s labels."""
    if node.name in ("fieldset", "table"):
        part = _first_child(node, "legend" if node.name == "fieldset"
                            else "caption")
        if part is not None:
            if at_state(part) in (HIDDEN, INVISIBLE):
                return ""
            return ((_labelledby_text(part, ids) if ids is not None
                     else "") or _norm(part.get("aria-label"))
                    or subtree_text(part, ids)
                    or (_norm(part.get("title"))
                        if part.name == "legend" else ""))
        return _norm(node.get("summary")) if node.name == "table" else ""
    if node.name == "output" and ids is not None:
        top = node
        while top.parent is not None:
            top = top.parent
        return _label_for_control(node, ids, top)
    return ""


def _first_child(node: Tag, name: str) -> Tag | None:
    """`node`'s first child element of HTML's named `name`, or None."""
    return next((c for c in node.children if isinstance(c, Tag)
                 and c.name == name and namespace_of(c) == "html"), None)


def chromium_cut(el: Tag, soup, ids) -> tuple | None:
    """For a control static_accname names: where Chromium 141 names it
    nothing (static_accname with chromium=True: it reads only the own name
    of an <article>, a <figure>, a <math> and the like, and no title of a
    <span>, a <div>, an <i> and the like), (kind, element, axe, why): the
    first such element whose content ("content"), or title ("title"), the
    accessible-name computation reads, a <label> Chromium reads in a
    button's place that names it nothing ("label": R6S-4), or a button
    input whose value is empty, after which Chromium reads no title
    ("value": R6U-3); whether axe-core 4.12 reads one of those, or passes
    the control by a <label for> it does not see on screen (_axe_why,
    _axe_label_pass: L92, L115, R6Q-1, R6W-5); and, where it does not,
    why (_axe_why); else None. Callers ask only where the computation's
    walk met such an element (static_accname's `cuts`)."""
    cuts: list = []
    if static_accname(el, soup, ids, chromium=True, cuts=cuts):
        return None
    first, why = None, None
    passed = _axe_label_pass(el, soup, ids)
    for kind, node in cuts:
        if first is None:
            if kind == "content" and not subtree_text(node, ids):
                continue
            first = (kind, node)
            if passed:
                break
        got = _axe_why(kind, node, el, ids)
        if got is None:
            why = None
            break           # one is enough (R6S-7)
        if why is None:
            why = got
    if first is None:
        return None
    axe = passed or why is None
    return (*first, axe, None if axe else why)


def _axe_label_pass(el: Tag, soup, ids) -> bool:
    """Does axe-core 4.12 pass `el`, a button, by a <label for> that names
    it and that it does not see on screen (_off_screen), or that is inside
    what a rendered ancestor skips (_in_skipped), whatever else names it
    (measured: R6U-5, R6W-5)? Not by one in a <template>, which is in no
    document."""
    el_id = el.get("id")
    if not el_id or el.name not in ("button", "input"):
        return False
    record = _record_name()
    key = (_tree_key(ids, el), el_id, record)
    memo = soup.__dict__.setdefault("_bb_axe_label_pass", {})
    if key not in memo:         # once per id: R6Y-5
        by_for, _order = _label_index(soup, ids)
        memo[key] = any(
            not any(isinstance(a, Tag) and a.name == "template"
                    for a in lab.parents)
            and (_off_screen(lab) or _in_skipped(lab, record))
            for lab in by_for.get(key[:2], ()))
    return memo[key]


def _axe_why(kind: str, node: Tag, el: Tag, ids) -> tuple | None:
    """Why axe-core 4.12 does not read into `el`'s name the text, or the
    title (`kind`), of `node`, an element chromium_cut found; None where
    it does. ("embedded", E): `node`, or an element E between it and
    `el` or the <label> of `el` that holds it (R6U-7), is embedded content
    (_embedded), of which it reads only the own name, or MathML, of which
    it reads none (R6Q-1, R6S-6, R6W-1); ("title", `node`): a title it
    reads none of (_axe_titles: R6S-1); ("content", `node`, what): what
    `node` holds gives it nothing, for the MathML or embedded content
    ("embedded"), or the titles ("title"), or both ("both") in it
    (_lost: R6W-2); ("own", `el`): past a <label> Chromium reads in a
    button's place ("label"), the button's own value, content or title,
    which it reads (R6S-4), gives it nothing. A button input named by a
    title after an empty value ("value") it names by that title
    (R6U-3)."""
    if kind == "value":
        return None
    if kind == "label":
        if el.name == "input" or _norm(el.get("title")) or subtree_text(
                el, ids, _axe=True):
            return None
        return ("own", el)
    for anc in node.parents:
        if anc is el or not isinstance(anc, Tag):
            break
        name = anc.name
        if name == "label" and not any(p is el for p in anc.parents):
            break               # the control's <label>, not one it holds
        if name in _EMBEDDED_NAMES and _embedded(anc):
            return ("embedded", anc)
    if kind == "title":
        return None if _axe_titles(node) else ("title", node)
    if _embedded(node):
        return ("embedded", node)
    # Remembered per element and record: nested controls share what they
    # hold (R6S-7).
    memo = node.__dict__.setdefault("_bb_axe_reads", {})
    record = _record_name()
    if record not in memo:
        memo[record] = bool(subtree_text(node, ids, _axe=True))
    return None if memo[record] else ("content", node, _lost(node, ids))


def _lost(node: Tag, ids) -> str:
    """What in `node` the accessible-name computation reads and axe-core
    4.12 does not: MathML or embedded content that holds text
    ("embedded"), a title of an element whose content gives none that
    axe-core reads none of (_axe_titles: "title"), or both ("both");
    "embedded" where neither is found."""
    embedded = titled = False
    record = _record_name()
    stack = list(node.children)
    while stack:
        child = stack.pop()
        if not isinstance(child, Tag) or at_state(child) in (HIDDEN,
                                                             INVISIBLE):
            continue
        if namespace_of(child) == "math" or _embedded(child):
            # What it holds, read in place (a drawing of role
            # presentation by its content too: R6Y-6).
            embedded = embedded or bool(_norm(" ".join(
                t for t in child.find_all(string=True)
                if not isinstance(t, PreformattedString))))
            continue
        if _skips(child, record):
            continue
        if (not titled and _norm(child.get("title"))
                and not _axe_titles(child)
                and not subtree_text(child, ids)):
            titled = True
        stack.extend(child.children)
    if embedded and titled:
        return "both"
    return "title" if titled else "embedded"


def _off_screen(node: Tag) -> bool:
    """Is `node` not shown on screen, as rendering decides it (not
    aria-hidden): it or an ancestor is not rendered (_drawn_state's
    HIDDEN: the hidden attribute, display:none, a closed <dialog>), or it
    is invisible (visibility:hidden or collapse, inherited)?"""
    state = None
    for anc in (node, *node.parents):
        if not isinstance(anc, Tag) or anc.name == "[document]":
            break
        got = _drawn_state(anc)
        if got == HIDDEN:
            return True
        if state is None and got in (INVISIBLE, SHOWN):
            state = got
    return state == INVISIBLE


#: HTML's elements whose own role is group, as Chromium 141 has them
#: (measured: R6M round 7; a <details>'s is its own).
_HTML_GROUPS = frozenset(("fieldset", "address", "hgroup"))


def _opens_group(node: Tag, ids=None) -> bool:
    """Through aria-labelledby, is `node` one past which Chromium 141 reads
    what is made visible again inside invisible content, as a name from
    content reads it (measured: R6K-9, R6M round 7): one whose role is
    group, by a role attribute it honors (checks_static._role_of: the
    first role it knows; region or form only where named, _role_named,
    else its own role) or by its own, an HTML <fieldset>, <address> or
    <hgroup>, or a drawing's <g>, <a> that is no link outside a <text>,
    inner <svg> (_group_role) or <foreignObject>? The root is not one
    (subtree_text reads from below it)."""
    if namespace_of(node) == "svg":
        if _group_role(node, True, ids):
            return True
        return (not _resolved_role(node, ids)
                and (node.name or "").lower() == "foreignobject")
    role = _resolved_role(node, ids)
    if role:
        return role == "group"
    return namespace_of(node) == "html" and node.name in _HTML_GROUPS


def _in_unboxed(el: Tag, record: str | None) -> bool:
    """Is `el` inside a drawing's part with no box (_UNBOXED_MARKS), in a
    capture's record (`record`), where nothing it holds has a box?"""
    return record is not None and any(
        isinstance(n, Tag) and n.get(record) in _UNBOXED_MARKS
        for n in el.parents)


def _boxless_holds(node: Tag, ids=None) -> bool:
    """Is `node` a drawing's element whose role is group (_group_role), one
    that, with no box (_UNBOXED_MARKS, or inside such a part), holds
    nothing Chromium 141 reads into a name, its aria-label neither
    (measured: R6E-4; an <a> a <switch> passes over or one in an <a>,
    R6G-8; by its role, R6I-4)?"""
    return namespace_of(node) == "svg" and _group_role(node, False, ids)


def _resolved_role(node: Tag, ids=None) -> str:
    """The role a role attribute gives `node` where Chromium 141 honors it
    (checks_static._role_of: the first role it knows; not role="none" or
    "presentation" on an element that can take focus or carries a global
    ARIA attribute), or the native role _role_of knows; "" where neither
    does, or where the role is region or form and the element has no name
    that keeps it (_role_named), which leaves it its own role (R6K-7,
    R6M-3)."""
    from .checks_static import _role_of
    role = _role_of(node)
    if role in ("region", "form") and not _role_named(node, ids):
        return ""
    return role


def _role_named(node: Tag, ids=None) -> bool:
    """Has `node` what keeps role region or form on it in Chromium 141: an
    aria-label of more than white space, a title attribute of any value,
    or an aria-labelledby naming an element of its tree, an empty one too
    (measured: R6M-3)? `ids` as subtree_text's; with none, the document's
    first element with each id."""
    if _norm(node.get("aria-label")) or node.has_attr("title"):
        return True
    wanted = _labelledby_ids(node)
    if not wanted:
        return False
    reach = _reach(ids, node) if ids is not None else _document_ids(node)
    return any(t in reach for t in wanted)


def _document_ids(node: Tag) -> dict:
    """{id: the first element with it} in `node`'s document, built once."""
    top = node
    while top.parent is not None:
        top = top.parent
    found = top.__dict__.get("_bb_any_ids")
    if found is None:
        found = {}
        for el in top.find_all(id=True):
            found.setdefault(el.get("id"), el)
        top.__dict__["_bb_any_ids"] = found
    return found


def _group_role(node: Tag, boxed: bool, ids=None) -> bool:
    """Is group the role Chromium 141 resolves for `node`, a drawing's
    element: the one its role attribute gives it where honored
    (_resolved_role: region or form only where named, R6K-7, R6M-3), else
    its own: a <g>'s, an <a>'s that is no link (no href, no xlink:href)
    outside a <text>, and where it has a box (`boxed`) an inner <svg>'s
    (measured: R6I-4)?"""
    role = _resolved_role(node, ids)
    if role:
        return role == "group"
    name = (node.name or "").lower()
    if name == "g":
        return True
    if name == "svg":
        return boxed and _svg_element(node)
    if name != "a":
        return False
    holder = node.parent
    while isinstance(holder, Tag) and holder.name == "a" \
            and namespace_of(holder) == "svg":
        holder = holder.parent
    return not (isinstance(holder, Tag) and namespace_of(holder) == "svg"
                and (holder.name or "").lower() in ("text", "tspan",
                                                    "textpath"))


def _boxless_cut(node: Tag, root: Tag, ids=None) -> bool:
    """Does Chromium 141 leave a part of a drawing that has no box
    ("unboxed", "unboxed-visibility": model.hidden_attr) out of the name
    of `root`, which holds it? It does where a part whose role is group
    (_group_role: a <g>, an inner <svg> or an <a> that is no link, where
    no role they take says otherwise, or one given role="group") stands
    between them, nearer than any other <a> of the drawing (measured: what
    a <switch> passes over, a shape or a gradient holds, R6C-3; by role,
    R6I-4)."""
    for anc in node.parents:
        if anc is root or not isinstance(anc, Tag):
            return False
        if namespace_of(anc) != "svg":
            continue
        if _group_role(anc, True, ids):
            return True
        if anc.name == "a":
            return False
    return False


def _labelledby_text(el: Tag, ids: dict[str, Tag],
                     _seen: set | None = None) -> str:
    reach = _reach(ids, el)
    out = [_referenced_text(reach[t], ids, _seen) for t in _labelledby_ids(el)
           if t in reach]
    return _norm(" ".join(out))


def _label_index(soup, ids=None) -> tuple[dict, dict]:
    """({(tree, `for` value): [its <label>s, in document order]}, {id of a
    <label>: its place in document order}), built once per document
    (looking a control's labels up per control was quadratic: P2-12). A
    label names a control of its own tree only."""
    cache = soup.__dict__.get("_bb_labels")
    if cache is None:
        by_for: dict = {}
        order: dict = {}
        for i, lab in enumerate(soup.find_all("label")):
            order[id(lab)] = i
            target = lab.get("for")
            if target is not None:
                by_for.setdefault((_tree_key(ids, lab), target), []).append(lab)
        cache = soup.__dict__["_bb_labels"] = (by_for, order)
    return cache


#: The elements HTML makes labelable (an <input> unless its type is
#: hidden). A form-associated custom element is too, which markup cannot
#: show.
_LABELABLE = frozenset(("button", "input", "meter", "output", "progress",
                        "select", "textarea"))


def _labelable(node) -> bool:
    """A labelable element: an HTML one (an <input> of a drawing is none,
    R5Q-10), an <input> unless its type is hidden."""
    return (isinstance(node, Tag) and node.name in _LABELABLE
            and not (node.name == "input" and (node.get("type") or "")
                     .strip().lower() == "hidden")
            and namespace_of(node) == "html")


def _light_children(node: Tag) -> list:
    """`node`'s children in its own tree, in DOM order. A shadow host's
    light-DOM children are not where materialize left them, inside its
    root's slots in slot order: they are the nodes assigned to it, in
    their place among its children (shadow.LIGHT_INDEX). The root's own
    content is another tree, and none of them; nor are the nodes a slot
    shows, which are the host's (R5K-2)."""
    from .shadow import LIGHT_INDEX, is_assigned, is_wrapper
    wrapper = next((c for c in node.children if is_wrapper(c)), None)
    if wrapper is None:
        return [c for c in node.children if not is_assigned(c)]
    assigned = []
    for n in wrapper.descendants:
        if not is_assigned(n):
            continue
        up = n.parent
        while isinstance(up, Tag) and not is_wrapper(up):
            up = up.parent
        if up is wrapper:          # this host's, not a nested host's
            assigned.append(n)
    assigned.sort(key=lambda n: n.__dict__.get(LIGHT_INDEX, 0))
    return [c for c in node.children if c is not wrapper] + assigned


def _first_labelable(soup, label: Tag):
    """The element a <label> without `for` labels (HTML): its first
    labelable descendant in tree order, in the label's own tree (a shadow
    root's content is another, and a host's light-DOM children come in
    their DOM order, not their slots': _light_children, R5I-1). Found once
    per label."""
    cache = soup.__dict__.setdefault("_bb_first_labelable", {})
    if id(label) in cache:
        return cache[id(label)]
    from .shadow import LABELABLE_FALLBACK
    found = None
    stack = list(reversed(_light_children(label)))
    while stack:
        node = stack.pop()
        if not isinstance(node, Tag) or node.name == "template":
            continue
        if _labelable(node):
            found = node
            break
        if node.__dict__.get(LABELABLE_FALLBACK):
            break   # a slot's fallback held it, which a slot shows not
        stack.extend(reversed(_light_children(node)))
    cache[id(label)] = found
    return found


#: _label_state's answers: what keeps a label's text from naming its
#: control.
_GONE, _INVISIBLE, _VISIBLE = "gone", "invisible", "visible"


def _label_state(node: Tag, aria: bool = True) -> str | None:
    """How a label, or an ancestor of one, takes part in naming, as
    Chromium 141 computes it: _GONE when it is not rendered or is hidden
    from assistive technology (aria-hidden, where `aria`, the hidden
    attribute, a closed <dialog> or popover, display:none, a closed
    <details>' content, or a rendered capture's record of display),
    _INVISIBLE or _VISIBLE when it sets visibility, None when it does
    neither; display and visibility as the cascade orders the style
    attribute and the page's rules (R5K-5).
    `inert` leaves a label's text naming its control (R5I-4), and so do
    content-visibility:hidden and hidden="until-found" where they skip
    nothing (an inline label); a label whose content they skip names its
    control only by its aria-labelledby, aria-label or title, and one
    inside what they skip names nothing (_label_hidden, R5M-1, R5S-6)."""
    if (aria and aria_hidden(node)) or node.name in _TEXTLESS:
        return _GONE
    parent = node.parent
    if (isinstance(parent, Tag) and parent.name == "details"
            and not parent.has_attr("open")
            and node is not _first_summary(parent)):
        return _GONE
    page = CURRENT_PAGE.get()
    attr = PROVENANCE_ATTR.get()
    if page is not None and page.hiding_recorded and attr:
        return {"display": _GONE, "visibility": _INVISIBLE,
                "shown": _VISIBLE, "shown-skips": _VISIBLE,
                "visibility-skips": _INVISIBLE,
                "unrendered-visibility": _INVISIBLE,
                "unboxed-visibility": _INVISIBLE}.get(
                    node.get(view_hidden_attr(attr)))
    styles = page.styles() if page is not None else None
    display = cascade_decides(styles, node, "display")
    if display is False or (ua_hidden(node) and display is not True):
        return _GONE
    visibility = cascade_decides(styles, node, "visibility")
    if visibility is False:
        return _INVISIBLE
    if visibility is True:
        return _VISIBLE
    return None


def _visibility(node: Tag) -> str | None:
    """`node`'s visibility as inherited: the nearest it or an ancestor
    sets (_label_state), or None."""
    while isinstance(node, Tag) and node.name != "[document]":
        state = _label_state(node)
        if state in (_INVISIBLE, _VISIBLE):
            return state
        node = node.parent
    return None


def _label_hidden(label: Tag, control: Tag, above: set,
                  chromium: bool = False) -> bool:
    """Does `label` name nothing because it is hidden, as Chromium 141
    computes it (R5G-2, R5I-4)? When it, or an ancestor that does not hold
    its control too (`above`: the ids of the control's ancestors), is not
    rendered or is hidden from assistive technology (_label_state _GONE);
    and when it is invisible, visibility being inherited from any
    ancestor, while its control is not. A label hidden with its control (a
    form in a closed menu) names it as it will be named when shown. A label
    inside what such an ancestor skips (hidden="until-found",
    content-visibility:hidden on a box that skips) is not rendered, and
    names nothing (R5M-1); one that skips what it holds itself names its
    control only by its aria-labelledby, aria-label or title (_label_text,
    R5S-6). With `chromium`, an aria-hidden ancestor hides it not: Chromium
    141 reads a <label> inside one, and hides only one aria-hidden itself
    (measured: R6AB-1); the accessible-name computation, and axe-core
    4.12, read none (a field named by such a label alone fails: L128)."""
    record = _record_name()
    node = label
    while isinstance(node, Tag) and node.name != "[document]" \
            and id(node) not in above:
        aria = not chromium or node is label
        if _label_state(node, aria) == _GONE or (
                node is not label and _skips(node, record)):
            return True
        node = node.parent
    return (_visibility(label) == _INVISIBLE
            and _visibility(control) != _INVISIBLE)


def _label_ignored(label: Tag, above: set) -> bool:
    """Does Chromium 141 leave `label` out of its control's name, so that
    the control keeps its own (measured: R6U-2): one in a <template>'s
    content, or one inside what a rendered ancestor that does not hold the
    control too (`above`, as _label_hidden's) skips: a closed <details>'
    content but its first summary, hidden="until-found",
    content-visibility:hidden (_in_skipped), or a closed <details>'
    content where the control is in its first summary (R6W-3)? A hidden
    one (the hidden
    attribute, display:none, visibility:hidden, aria-hidden, a closed
    <dialog>) is not left out: it names its control nothing."""
    record = _record_name()
    child, skipped = label, False
    for anc in label.parents:
        if not isinstance(anc, Tag) or anc.name == "[document]":
            break
        if anc.name == "template":
            return True
        if id(anc) in above:
            # A closed <details> that holds the control in its first
            # summary, the label past it, skips the label alone (R6W-3).
            if (anc.name == "details" and not anc.has_attr("open")
                    and child is not _first_summary(anc)
                    and id(_first_summary(anc)) in above):
                return True
            child = anc         # R6Y-1
            continue
        if _skips(anc, record) or (
                anc.name == "details" and not anc.has_attr("open")
                and child is not _first_summary(anc)):
            skipped = True
        if skipped and _drawn_state(anc) == HIDDEN:
            skipped = False     # what skips at or below it is not rendered
        child = anc
    return skipped


def _label_for_control(el: Tag, ids: dict[str, Tag], soup,
                       chromium: bool = False, cuts: list | None = None,
                       found: list | None = None) -> str:
    """The text of the labels that label `el`, as HTML makes a label's
    labeled control: a label whose `for` names `el`'s id (`el` being the
    first element of its tree with that id), and a label without `for`
    whose first labelable descendant `el` is; not one that only holds
    `el` (R5G-2). Every such label counts, in document order, as Chromium
    joins them, except one that is hidden (_label_hidden). `chromium` and
    `cuts` as static_accname's: Chromium 141 reads a label's content as it
    reads a name from content (measured: R6Q-7). `found` collects every
    label that labels `el` and that Chromium does not leave out
    (_label_ignored), a hidden one too."""
    by_for, order = _label_index(soup, ids)
    key = _tree_key(ids, el)
    labels = []
    el_id = el.get("id")
    # The label's for reaches this control only if no other element of the
    # tree holds the id first.
    if el_id and _reach(ids, el).get(el_id, el) is el:
        labels.extend(by_for.get((key, el_id), ()))
    anc = el.parent
    while anc is not None and isinstance(anc, Tag):
        # A <label> in another tree (one wrapped around a slot in a shadow
        # root) does not label what the slot shows; one further out, in the
        # control's own tree, still can (OR2-7).
        if (anc.name == "label" and _tree_key(ids, anc) == key
                and not anc.has_attr("for")
                and _first_labelable(soup, anc) is el):
            labels.append(anc)
        anc = anc.parent
    if not labels:
        return ""
    labels = sorted({id(lab): lab for lab in labels}.values(),
                    key=lambda lab: order.get(id(lab), 0))
    above = {id(a) for a in el.parents}
    if found is not None:
        found.extend(lab for lab in labels if not _label_ignored(lab, above))
    read = [lab for lab in labels
            if not _label_hidden(lab, el, above, chromium)]
    # A label inside another that labels it too is read once, in the outer
    # one's text, where that reads it, as Chromium 141 reads it (R5I-13);
    # one inside a hidden label, or one the outer label's text never
    # reaches (its aria-label, a part named for itself), is read on its own
    # (R5K-1, R5M-9). Document order puts the outer label first.
    seen: set = set()
    texts = []
    for lab in read:
        if id(lab) not in seen:
            texts.append(_label_text(lab, ids, seen, el, chromium, cuts))
    return _norm(" ".join(texts))


def _label_text(label: Tag, ids, seen: set, control: Tag | None = None,
                chromium: bool = False, cuts: list | None = None) -> str:
    """A label's text, as Chromium 141 reads a label naming its control:
    its aria-labelledby, else its aria-label, else its content, else its
    title (R5M-8; measured). Its content leaves out the control it names:
    a <select>'s options, a <textarea>'s text, a <button>'s words are not
    their own label (R5S-5). An inner label it reads, through its
    aria-labelledby too, goes in `seen`: it is read once (R5O-9,
    R5Q-11)."""
    if ids is not None:
        by = _labelledby_text(label, ids, seen)
        if by:
            return by
    own = _norm(label.get("aria-label"))
    if own:
        return own
    return (subtree_text(label, ids, _seen=seen, _skip=control,
                         _chromium=chromium, _cuts=cuts)
            or _norm(label.get("title")))


def _labelled(name: str, labels: list, chromium: bool,
              cuts: list | None) -> str | None:
    """A <button>'s, a button input's or a form field's name where
    `labels` label it (_label_for_control): Chromium 141 reads them in
    place of its content, value, title and placeholder, so with
    `chromium` it is their text (`name`), "" too, which goes into `cuts`
    as ("label", the first): an empty one, a hidden one, one wrapped
    around the control alone (measured: R6S-4, L104). Without it, None
    (read on), the first going into `cuts` as ("maybe", ...) where their
    text is empty."""
    if chromium:
        if not name and cuts is not None:
            cuts.append(("label", labels[0]))
        return name
    if not name and cuts is not None:
        cuts.append(("maybe", labels[0]))
    return None


def _field_name(el: Tag, ids, soup, chromium: bool,
                cuts: list | None) -> str | None:
    """A form field's name from its <label>s (_label_for_control). With
    `chromium`, None where labels label it and name it nothing: Chromium
    141 reads them in place of its title and placeholder, an empty or a
    hidden one too, as it does a button's (measured: L104), and the
    first goes into `cuts` as ("label", it); without it, their text,
    and ("maybe", the first) where it is empty (_labelled)."""
    labels: list = []
    name = _label_for_control(el, ids, soup, chromium, cuts, labels)
    if labels and (chromium or cuts is not None):
        got = _labelled(name, labels, chromium, cuts)
        if got is not None and not got:
            return None
    return name


#: HTML's elements static_accname names by their own markup (alt, value,
#: label); an element of a drawing or of MathML of the same name is named
#: as other elements are.
_NATIVE_NAMED = frozenset(("img", "area", "input", "select", "textarea",
                           "button", "meter", "output", "progress"))


def static_accname(el: Tag, soup, ids: dict[str, Tag],
                   use_labelledby: bool = True, content: bool = True,
                   chromium: bool = False, cuts: list | None = None) -> str:
    """Best-effort static accessible name. Empty string == no name found.

    `use_labelledby=False` computes the name the element would have without
    its aria-labelledby, which is how bb-aria-ref tells a harmless dangling
    reference from one that leaves the element unnamed. `content=False`
    leaves out the name from content of an element other than the native
    ones handled here: for a role named by its author only
    (aria.NAME_FROM_CONTENT_ROLES), such as a role=textbox, whose text is
    its value. `chromium=True` reads a name from content, and a label's
    content, as Chromium 141 reads them: of an <article>, a <figure>, a
    <math> and the like, only their own name, and no title of a <span>, a
    <div>, an <i> and the like (subtree_text's `_chromium`, which adds
    them to `cuts`: L92, L115). Without it, `cuts` collects the elements
    met that Chromium may read so (chromium_cut's first test)."""
    if use_labelledby:
        name = _labelledby_text(el, ids)
        if name:
            return name

    name = _norm(el.get("aria-label"))
    if name:
        return name

    tag = el.name
    if tag in _NATIVE_NAMED and namespace_of(el) != "html":
        tag = ""        # a drawing's or MathML's <input> is none (R6B-7)
    if tag in ("img", "area"):
        name = _norm(el.get("alt"))
    elif tag == "input":
        itype = (el.get("type") or "text").lower()
        if itype == "image":
            name = _norm(el.get("alt"))
        elif itype in ("submit", "reset", "button"):
            # Its <label>, then its value (HTML-AAM); browsers supply
            # implicit values for submit and reset where it has no value
            # attribute. One that is empty names it nothing, and Chromium
            # 141 reads no title after it (measured: R6U-3).
            labels: list = []
            name = _label_for_control(el, ids, soup, chromium, cuts, labels)
            if labels and (chromium or cuts is not None):
                got = _labelled(name, labels, chromium, cuts)
                if got is not None:
                    return got
            value = el.get("value")
            if name:
                pass
            elif value is None:
                name = ("Submit" if itype == "submit"
                        else "Reset" if itype == "reset" else "")
            else:
                name = _norm(value)
                if not name and _norm(el.get("title")):
                    if cuts is not None:
                        cuts.append(("value" if chromium else "maybe", el))
                    if chromium:
                        return ""
        else:
            name = _field_name(el, ids, soup, chromium, cuts)
            if name is None:
                return ""
    elif tag in ("select", "textarea"):
        name = _field_name(el, ids, soup, chromium, cuts)
        if name is None:
            return ""
    elif tag in ("button", "meter", "output", "progress"):
        # Labelable too (HTML): a <label> names them before their content,
        # as HTML-AAM says and Chromium computes it (L72-11).
        labels = []
        name = _label_for_control(el, ids, soup, chromium, cuts, labels)
        if tag == "button" and labels and (chromium or cuts is not None):
            got = _labelled(name, labels, chromium, cuts)
            if got is not None:
                return got
        if not name and content:
            name = subtree_text(el, ids, _chromium=chromium, _cuts=cuts)
    elif tag == "svg":
        # Its own <title> child, not a part's (R5K-11), as _native_text;
        # none where it skips what it holds; one of white space alone
        # names it nothing, and nothing after it is read (R6I-3); one
        # given a role named from its content by that (R6O-4).
        t = _outer_title(el)
        if t is not None:
            return subtree_text(t, ids)
        name = (subtree_text(el, ids, _chromium=chromium, _cuts=cuts)
                if content and _svg_content_role(el) else "")
    elif _svg_element(el) and tag not in ("title", "desc"):
        # An element of a drawing (a <g role="img">) is named by its own
        # <title> child (SVG-AAM), a link then by its xlink:title; by one
        # of white space alone, nothing, and nothing after it is read
        # (_svg_title: R6H-7); else, where its role allows, by its content
        # (QR-10).
        titled = _svg_title(el)
        if titled is not None:
            return titled
        name = (subtree_text(el, ids, _chromium=chromium, _cuts=cuts)
                if content else "")
    elif content:  # a, button, summary, headings, role-bearing containers
        name = subtree_text(el, ids, _chromium=chromium, _cuts=cuts)
    if name:
        return name

    return _norm(el.get("title"))
