"""Shadow roots as markup the static rules read.

A shadow root reaches the rules as a `<template shadowrootmode>` inside its
host: a rendered capture serializes every shadow root, open or closed, that
way, and a page's own markup can declare one (declarative shadow DOM, which
Lit's server rendering writes). The rules treat <template> as inert, so each
shadow root becomes a `<bb-shadow-root>` element, and the host's light-DOM
children move into the <slot> that renders them (unassigned ones are
dropped, as the browser drops them). Without slotting,
`<button><slot></slot></button>` with a slotted label would fail as an
unnamed button.

Which templates are shadow roots depends on where the markup came from:

* a rendered capture stamps every element in the document with its
  provenance attribute, and the templates it writes for shadow roots carry
  none, so a template that carries the stamp is an inert template in the
  page (one set by innerHTML, which never attaches a root);
* in a page's own markup, the HTML parser attaches a template with
  shadowrootmode open or closed to the element it was opened in, when that
  element may host one and has none yet; html5.parse decides it there, as
  the parser meets the template, and marks it; a .xhtml file is XML, where
  none attaches.

A page can write a `<bb-shadow-root>` element of its own (it is a valid
custom element name), so the harness never goes by the name: the wrappers it
makes are marked on the element objects (is_wrapper), and in a capture's
snapshot by the absence of the capture's stamp (mark_capture). Each
element belongs to one tree, the document or a shadow root (tree_scopes):
ids, <label for> and styles reach only within it (checks_static).
"""
from __future__ import annotations

import json
import re

from bs4.element import NavigableString, PreformattedString, Tag, TemplateString

WRAPPER = "bb-shadow-root"

#: Elements that may host a declarative shadow root, besides autonomous
#: custom elements.
_SHADOW_HOSTS = {"article", "aside", "blockquote", "body", "div", "footer",
                 "h1", "h2", "h3", "h4", "h5", "h6", "header", "main", "nav",
                 "p", "section", "span"}
#: HTML's valid custom element name (PotentialCustomElementName). `x-$`
#: and `x-y:z` are not: Chromium attaches no declarative root to them.
_PCEN_RANGES = ((0xB7, 0xB7), (0xC0, 0xD6), (0xD8, 0xF6), (0xF8, 0x37D),
                (0x37F, 0x1FFF), (0x200C, 0x200D), (0x203F, 0x2040),
                (0x2070, 0x218F), (0x2C00, 0x2FEF), (0x3001, 0xD7FF),
                (0xF900, 0xFDCF), (0xFDF0, 0xFFFD), (0x10000, 0xEFFFF))
_PCEN_CHAR = ("[-._0-9a-z" + "".join(f"{chr(a)}-{chr(b)}"
                                      for a, b in _PCEN_RANGES) + "]")
_CUSTOM_NAME_RE = re.compile(f"[a-z]{_PCEN_CHAR}*-{_PCEN_CHAR}*")
#: Hyphenated names that are not valid custom element names.
_RESERVED_NAMES = {"annotation-xml", "color-profile", "font-face",
                   "font-face-src", "font-face-uri", "font-face-format",
                   "font-face-name", "missing-glyph"}
_HTML_NS = "http://www.w3.org/1999/xhtml"

#: Keys in an element object's __dict__ (never attributes a page could
#: write): a wrapper the harness made, a light-DOM node it moved into a
#: slot, and a template the parser attached as a shadow root.
_ROOT = "_bb_shadow_root"
_ASSIGNED = "_bb_assigned"
DECLARATIVE = "_bb_declarative_root"
#: A slotted node's place among its host's element children in the DOM
#: (1-based), which its place in the slot does not show (locator.py).
LIGHT_INDEX = "_bb_light_index"
#: On a wrapper: what materialize left out of the host's tree (light-DOM
#: children no slot shows) and out of the root's own (a slot's fallback
#: content), as (ids, names), both ASCII-lowercased: the tree as the rules
#: read it lacks them, and a locator must not count on their absence.
LEFT_HOST = "_bb_left_host"
LEFT_ROOT = "_bb_left_root"
#: On a <slot> whose fallback content materialize removed (the host's
#: light DOM shows instead): that content held a labelable element, which a
#: <label> around the slot labels though it is not rendered (R5M-10).
LABELABLE_FALLBACK = "_bb_labelable_fallback"
_LABELABLE_NAMES = ("button", "input", "meter", "output", "progress",
                    "select", "textarea")


def valid_host_name(name: str, html_namespace: bool = True) -> bool:
    """May an element of this name host a declarative shadow root?"""
    if not html_namespace:
        return False                   # an SVG or MathML element hosts none
    name = name or ""
    return name in _SHADOW_HOSTS or (
        name not in _RESERVED_NAMES
        and _CUSTOM_NAME_RE.fullmatch(name) is not None)


def valid_host(host: Tag) -> bool:
    return valid_host_name(host.name or "", getattr(host, "namespace", None)
                           in (None, _HTML_NS))


def declares_root(mode) -> bool:
    """shadowrootmode open or closed (any case, nothing else: not trimmed;
    of two shadowrootmode attributes the first counts)."""
    return isinstance(mode, str) and mode.lower() in ("open", "closed")


def is_wrapper(node) -> bool:
    """Is `node` a shadow root's wrapper the harness made (never one a page
    wrote)?"""
    return isinstance(node, Tag) and node.__dict__.get(_ROOT) is True


def is_assigned(node) -> bool:
    """Is `node` a light-DOM child the harness moved into a slot?"""
    return isinstance(node, Tag) and node.__dict__.get(_ASSIGNED) is True


_HTML_POINTS = {"foreignobject", "desc", "title", "mi", "mo", "mn", "ms",
                "mtext", "annotation-xml"}


def _holds_labelable(slot: Tag) -> bool:
    """Does a slot's fallback content hold a labelable element of the
    slot's own tree: an HTML one (an <input> of a drawing is none: R5Q-10),
    not in a <template>'s content, nor in a shadow root a host in it has
    (R5O-10)?"""
    from .style import namespace_of
    stack = list(slot.children)
    while stack:
        node = stack.pop()
        if not isinstance(node, Tag) or node.name == "template" \
                or is_wrapper(node):
            continue
        if node.name in _LABELABLE_NAMES and not (
                node.name == "input" and str(node.get("type") or "")
                .strip().lower() == "hidden") \
                and namespace_of(node) == "html":
            return True
        stack.extend(node.children)
    return False


def _ascii_lower(text: str) -> str:
    return "".join(c.lower() if "A" <= c <= "Z" else c for c in text)


def _left_out(nodes, into: tuple, gone: set | None = None) -> None:
    """Add the ids and names of the elements in `nodes` (subtrees) to
    `into` = (ids, names), and to `gone` the ids of the slots and shadow
    roots among them: they are never rendered, so nothing is assigned to
    those slots and those roots need no reading (PR3-9)."""
    ids, names = into
    for n in nodes:
        if not isinstance(n, Tag):
            continue
        for el in (n, *n.find_all(True)):
            i = el.get("id")
            if isinstance(i, str) and i:
                ids.add(_ascii_lower(i))
            # Local names, as a type selector compares them (locator.py).
            names.add(_ascii_lower(el.name or "").rpartition(":")[2])
            if gone is not None and (el.name == "slot" or is_wrapper(el)):
                gone.add(id(el))


def _own_trees(soup) -> tuple[list, dict]:
    """One pass over the tree as it stands, in document order: (the
    template text to retype, {id(wrapper): the HTML slots of that root's
    own tree, in tree order}). A node's tree is its nearest wrapper's; an
    inert <template> inside it holds neither rendered text nor a slot, and
    an SVG or MathML element named slot is no slot: read from the namespace
    the parser recorded, else (a serialized DOM read with html.parser) from
    the ancestors within the root, where <svg> or <math> without an HTML
    integration point (_HTML_POINTS) between makes it foreign. Read before
    any node moves, so a slot that is a light child of a component inside
    the root (a forwarded slot) stays in the root's tree."""
    retype: list = []
    slots: dict = {}
    # (node, its tree's wrapper or None, inside an inert template, foreign)
    stack = [(soup, None, False, False)]
    while stack:
        node, owner, inert, foreign = stack.pop()
        for child in reversed(node.contents):
            if isinstance(child, Tag):
                if is_wrapper(child):
                    stack.append((child, child, False, False))
                    continue
                if child.name == "template":
                    stack.append((child, owner, True, False))
                    continue
                name = child.name or ""
                inner = (False if name in _HTML_POINTS else
                         True if name in ("svg", "math") else foreign)
                if name == "slot" and owner is not None and not inert:
                    ns = getattr(child, "namespace", None)
                    if (ns == _HTML_NS) if ns is not None else not foreign:
                        slots.setdefault(id(owner), []).append(child)
                stack.append((child, owner, inert, inner))
            elif (type(child) is TemplateString and owner is not None
                  and not inert):
                retype.append(child)
    # The stack takes children last first, so each list is in reverse
    # document order.
    retype.reverse()
    for found in slots.values():
        found.reverse()
    return retype, slots


def materialize(soup, is_root, slotted_attr: str | None = None,
                partial_attr: str | None = None) -> int:
    """Turn every <template> `is_root` accepts into a <bb-shadow-root> and
    slot its host's light-DOM children; returns how many. Every root is
    decided before any template is renamed, so a second template on a host
    is judged as the parser judged it (OR-4). Hosts are handled in document
    order, outer before inner. A template inside another template's content
    is converted too, but it stays inside that inert template, which the
    rules read as inert.

    Only an HTML <slot> of the root's own tree receives nodes: not one in
    an inert <template> inside the root, not an SVG element named slot, and
    not one inside a nested shadow root. As in the DOM, the nodes for a slot
    name go to the first slot of that name in tree order, even one inside
    another slot's fallback content: when that fallback is not shown (the
    outer slot has nodes of its own), neither are they (PR2-8). Everything
    is read in one pass (_own_trees), so nested roots cost no more than the
    nodes in them (PR2-2).

    `slotted_attr`, when given, is written on each element moved into a
    slot, its value the element's place among the host's element children
    (LIGHT_INDEX), so a capture's snapshot records which nodes are light DOM
    and where they were (mark_capture); `partial_attr` is written on a
    wrapper that left elements out, recording what (LEFT_HOST, LEFT_ROOT)
    as JSON."""
    roots = [tpl for tpl in soup.find_all("template") if is_root(tpl)]
    wrappers = []
    for tpl in roots:
        mode = tpl.get("shadowrootmode")
        tpl.name = WRAPPER
        tpl.attrs = {"data-mode": mode}
        tpl.__dict__[_ROOT] = True
        wrappers.append(tpl)
    if not wrappers:
        return 0
    retype, own_slots = _own_trees(soup)
    # The parser typed the text in a template's content as template text;
    # in a shadow root it is rendered text. Text in an inert template
    # inside the root keeps its type.
    for text in retype:
        text.replace_with(NavigableString(str(text)))
    #: ids of the slots and roots in what was left out (a cleared fallback,
    #: a light child no slot shows): never rendered.
    gone: set = set()
    for w in wrappers:
        host = w.parent
        if not isinstance(host, Tag) or id(w) in gone:
            continue
        light = [c for c in host.children if c is not w]
        index = {id(c): k for k, c in
                 enumerate((c for c in light if isinstance(c, Tag)), 1)}
        by_slot: dict[str, list] = {}
        for c in light:
            # Only elements and text are slottable: a comment (Lit's, Vue's
            # and Angular's markers) or a processing instruction is never
            # assigned, so it never hides a slot's fallback (PR3-2).
            if isinstance(c, PreformattedString) or not isinstance(
                    c, (Tag, NavigableString)):
                continue
            name = (c.get("slot") or "") if isinstance(c, Tag) else ""
            by_slot.setdefault(name, []).append(c)
        left_host: tuple = (set(), set())
        left_root: tuple = (set(), set())
        chosen: dict = {}
        for s in own_slots.get(id(w), ()):
            chosen.setdefault(s.get("name") or "", s)
        for name, s in chosen.items():
            nodes = by_slot.get(name)
            if not nodes or id(s) in gone:
                continue        # nothing for it, or never rendered: dropped
            _left_out(s.contents, left_root, gone)   # not rendered
            if _holds_labelable(s):
                s.__dict__[LABELABLE_FALLBACK] = True
            s.clear()
            for n in nodes:
                s.append(n.extract())
                if isinstance(n, Tag):
                    n.__dict__[_ASSIGNED] = True
                    n.__dict__[LIGHT_INDEX] = index[id(n)]
                    if slotted_attr:
                        n[slotted_attr] = str(index[id(n)])
        dropped = [c for c in host.children if c is not w]
        _left_out(dropped, left_host, gone)
        for c in dropped:                  # never rendered
            c.extract()
        record = {}
        for key, left, side in ((LEFT_HOST, left_host, "host"),
                                (LEFT_ROOT, left_root, "root")):
            if left[1]:
                w.__dict__[key] = left
                record[side] = [sorted(left[0]), sorted(left[1])]
        if partial_attr and record:
            w[partial_attr] = json.dumps(record, separators=(",", ":"))
    return len(wrappers)


def mark_capture(soup, provenance_attr: str) -> int:
    """In a capture's snapshot read back (html.parser), find the wrappers
    the capture made and the light-DOM nodes it slotted: a <bb-shadow-root>
    without the capture's stamp is a wrapper (every element of the page's
    own carries it), and an element with the capture's slotted record was
    moved into a slot. Returns how many wrappers."""
    slotted = slotted_attr(provenance_attr)
    partial = partial_attr(provenance_attr)
    n = 0
    for el in soup.find_all(True):
        if (el.name == WRAPPER and not el.has_attr(provenance_attr)
                and not any(isinstance(p, Tag) and p.name == "template"
                            for p in el.parents)):
            # (The capture stamps no element of an inert <template>'s
            # content; a <bb-shadow-root> there is the page's, and inert.)
            el.__dict__[_ROOT] = True
            for key, left in _read_left(el.get(partial)).items():
                el.__dict__[key] = left
            n += 1
        if el.has_attr(slotted):
            el.__dict__[_ASSIGNED] = True
            k = el.get(slotted) or ""
            if k.isascii() and k.isdigit() and 0 < int(k) < 10 ** 9:
                el.__dict__[LIGHT_INDEX] = int(k)
    return n


def _read_left(value) -> dict:
    """The capture's record of what materialize left out (partial_attr),
    as {LEFT_HOST or LEFT_ROOT: (ids, names)}. Anything malformed reads as
    "something unknown was left out": no id or name can be trusted."""
    if not isinstance(value, str) or not value:
        return {}
    try:
        data = json.loads(value)
        out = {}
        for side, key in (("host", LEFT_HOST), ("root", LEFT_ROOT)):
            if side in data:
                ids, names = data[side]
                out[key] = ({str(i) for i in ids}, {str(n) for n in names})
        return out
    except (ValueError, TypeError, KeyError):
        return {LEFT_HOST: None, LEFT_ROOT: None}


def slotted_attr(provenance_attr: str) -> str:
    """The attribute a capture writes on each light-DOM element it moved
    into a slot, named from its secret provenance attribute."""
    return provenance_attr + "-slotted"


def partial_attr(provenance_attr: str) -> str:
    """The attribute a capture writes on a shadow root's wrapper that left
    elements out of a tree (materialize)."""
    return provenance_attr + "-partial"


def tree_scopes(soup) -> dict:
    """{id(element): the wrapper of the shadow root its tree is, or None
    for the document}, for every element; {} when the page has no shadow
    root, where every element is in the document. One pass in document
    order: a child of a wrapper is in that root's tree; a node moved into a
    slot is in its host's tree; anything else is in its parent's."""
    elements = soup.find_all(True)
    if not any(is_wrapper(el) for el in elements):
        return {}
    out: dict = {}
    for el in elements:
        parent = el.parent
        if is_assigned(el):
            root = out.get(id(parent))           # the slot's own tree
            host = root.parent if root is not None else None
            out[id(el)] = out.get(id(host)) if host is not None else None
        elif is_wrapper(parent):
            out[id(el)] = parent
        else:
            out[id(el)] = out.get(id(parent))
    return out
