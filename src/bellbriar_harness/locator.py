"""Element locators: where in the page a finding's element is (A4, N23).

A finding's line number points into the file the rules read, which for a
rendered run is a snapshot the customer does not have open. So every
finding about an element also carries a locator: CSS selectors a browser
resolves to that element, in the DOM the rules read (a file or server HTML
as a browser parses it; a rendered run's DOM as captured).

A locator is a list of selectors, one per tree. The first is matched in
the document (`document.querySelector`); each further one in the shadow
root of the element the one before it found (`el.shadowRoot.querySelector`),
so an element two shadow roots deep has three. `resolve` in
docs/MEASUREMENT-AND-EVIDENCE-GUIDE.md ("Finding an element") does that in
a few lines of JavaScript; a step into a closed shadow root needs the
browser's developer tools, since page scripts cannot open one.

Each selector is a chain of compound selectors joined by child combinators
(`>`), from an anchor down to the element, and matches exactly that
element in its tree, by construction:

* the anchor is the nearest element, from the element itself upward, with
  an id no other element of its tree has (compared ignoring ASCII case, as
  a quirks-mode page compares them): `#id`. Failing that, in the document,
  `body`, `head` or `html` when the document has one; at the top of a
  shadow root, the top-level element's own step, preceded by `:host >`
  (the shadow root's top level, as Chromium matches it in
  `shadowRoot.querySelector`) when that step alone could match deeper
  down; and `:root` for a document element that is not alone;
* below the anchor each step is the element's name, with `:nth-child(k)`
  when a sibling has the same name, so it picks one child of the element
  above it. As in the browser's own "Copy selector":
  `#main > ul > li:nth-child(3) > a`, `body > footer > p`.

A locator holds at most MAX_STEPS steps over all its trees; an element
deeper than that below its anchors has none (`selector` is null).

Two things the harness reads differently from the DOM are undone here: a
shadow root is a <bb-shadow-root> element in the rules' tree (shadow.py), and
the host's light-DOM children sit in the <slot> that shows them, so a
slotted element's place among its host's children is the one materialize
recorded. Materialize also leaves out what is never rendered (a host's
children no slot shows, a slot's fallback content), and records their ids
and names: no id or name among them is an anchor in their tree, since a
selector could find one of them first.
"""
from __future__ import annotations

from bs4 import BeautifulSoup
from bs4.element import Tag

from . import shadow
from .redact import holds_password, holds_secret

#: The tree key of the document; a shadow root's is id(its wrapper).
_DOCUMENT = 0
#: The most steps a locator holds, over all its trees. An element deeper
#: than that below its anchors gets none: its finding gives its line, and a
#: page of deeply nested findings cannot multiply its report's size by its
#: depth (PR2-10). The deepest page of the field sweep nests 20 levels.
MAX_STEPS = 100


def css_ident(text: str) -> str:
    """`text` as a CSS identifier (CSSOM's "serialize an identifier",
    as CSS.escape writes it)."""
    out = []
    for i, ch in enumerate(text):
        cp = ord(ch)
        if cp == 0:
            out.append("�")
        elif 0x1 <= cp <= 0x1F or cp == 0x7F or (
                i == 0 and 0x30 <= cp <= 0x39) or (
                i == 1 and 0x30 <= cp <= 0x39 and text[0] == "-"):
            out.append(f"\\{cp:x} ")
        elif i == 0 and ch == "-" and len(text) == 1:
            out.append("\\-")
        elif cp >= 0x80 or ch in "-_" or (ch.isascii() and ch.isalnum()):
            out.append(ch)
        else:
            out.append("\\" + ch)
    return "".join(out)


def _ascii_lower(text: str) -> str:
    return "".join(c.lower() if "A" <= c <= "Z" else c for c in text)


def _local_name(el: Tag) -> str:
    """The name a type selector compares, as the counts here keep it: a
    type selector matches by local name in any namespace, so in XHTML an
    `ns:a` (an <a> in no namespace) is matched by `a` too (PR3-7), and in
    HTML `o:p` is counted with `p` (needlessly, which only costs a
    position)."""
    return _ascii_lower(el.name or "").rpartition(":")[2]


def _type_selector(el: Tag) -> str:
    """The element's name as a type selector, or `*` for a name a selector
    cannot write without a namespace prefix (an XML element of another
    vocabulary, `dc:title`)."""
    name = el.name or ""
    if not name or ":" in name:
        return "*"
    return css_ident(name)


class Locators:
    """Locators for the elements of one page's tree (PageContext.locator).

    `scopes` is shadow.tree_scopes(soup): {id(element): the wrapper of its
    shadow root, or None for the document}. What is inside an element named
    in `inert_names` is no part of the DOM a script sees: a template's
    content, and the text of a <noscript> that html.parser read as
    elements. In an XML document a <noscript>'s children are elements of
    the DOM (PR2-6), so there only "template" is named."""

    def __init__(self, soup: BeautifulSoup, scopes: dict,
                 inert_names=("template", "noscript")):
        self._scopes = scopes or {}
        self._index: dict[int, int] = {}          # id(el) -> nth-child
        self._shared: set[int] = set()            # name shared by a sibling
        self._ids: dict[tuple, int] = {}          # (tree, lower id) -> count
        self._names: dict[tuple, int] = {}        # (tree, lower name) -> count
        self._nth: dict[tuple, int] = {}          # (tree, name, k) -> count
        self._any_nth: dict[tuple, int] = {}      # (tree, k) -> count
        #: {tree: (ids, names) left out of it by materialize, or None
        #: when unknown (then nothing in it is an anchor but its top)}
        self._left: dict[int, tuple | None] = {}
        self._cache: dict[int, list | None] = {}
        children: dict[int, list] = {}
        inert: set[int] = set()        # ids of elements in inert content
        for el in soup.find_all(True):
            parent = el.parent
            if id(parent) in inert or (isinstance(parent, Tag)
                                       and parent.name in inert_names
                                       and not shadow.is_wrapper(parent)):
                inert.add(id(el))
                continue
            if shadow.is_wrapper(el):
                host = el.parent
                for key, tree in ((shadow.LEFT_HOST,
                                   self._tree(host) if isinstance(host, Tag)
                                   else _DOCUMENT),
                                  (shadow.LEFT_ROOT, id(el))):
                    if key in el.__dict__:
                        self._add_left(tree, el.__dict__[key])
                continue
            tree = self._tree(el)
            if shadow.is_assigned(el):
                k = el.__dict__.get(shadow.LIGHT_INDEX)
                if isinstance(k, int) and k > 0:
                    self._index[id(el)] = k
                self._shared.add(id(el))          # its siblings are unknown
            else:
                parent = el.parent
                key = (id(parent) if isinstance(parent, Tag)
                       and not isinstance(parent, BeautifulSoup) else -1)
                children.setdefault(key, []).append(el)
            i = el.get("id")
            if isinstance(i, str) and i:
                k = (tree, _ascii_lower(i))
                self._ids[k] = self._ids.get(k, 0) + 1
            name = _local_name(el)
            self._names[(tree, name)] = self._names.get((tree, name), 0) + 1
        for kids in children.values():
            seen: dict[str, int] = {}
            for k, el in enumerate(kids, 1):
                self._index[id(el)] = k
                name = _local_name(el)
                seen[name] = seen.get(name, 0) + 1
            for el in kids:
                if seen[_local_name(el)] > 1:
                    self._shared.add(id(el))
        for el in soup.find_all(True):
            k = self._index.get(id(el))
            if k is None or shadow.is_wrapper(el):
                continue
            tree = self._tree(el)
            name = _local_name(el)
            self._nth[(tree, name, k)] = self._nth.get((tree, name, k), 0) + 1
            self._any_nth[(tree, k)] = self._any_nth.get((tree, k), 0) + 1

    def _add_left(self, tree: int, left) -> None:
        if tree in self._left and self._left[tree] is None:
            return
        if not (isinstance(left, tuple) and len(left) == 2):
            self._left[tree] = None
            return
        ids, names = self._left.get(tree) or (set(), set())
        self._left[tree] = (ids | set(left[0]), names | set(left[1]))

    def _free(self, tree: int, *, id_: str | None = None,
              name: str | None = None, any_name: bool = False) -> bool:
        """May an anchor in `tree` count on nothing left out sharing this id
        or name (or, any_name, on nothing at all having been left out)?"""
        if tree not in self._left:
            return True
        left = self._left[tree]
        if left is None or any_name:
            return False
        ids, names = left
        if id_ is not None and id_ in ids:
            return False
        return name is None or name not in names

    # -- the DOM the browser has ------------------------------------------

    def _tree(self, el) -> int:
        w = self._scopes.get(id(el)) if self._scopes else None
        return _DOCUMENT if w is None else id(w)

    def _host_of_slotted(self, el: Tag):
        """The host whose light-DOM child `el` is: the host of the shadow
        root the slot it sits in belongs to. Not the nearest root above it:
        a slot can itself be a light child of a component inside that root,
        and pass `el` on into the component's own slot (a forwarded slot),
        so `el` sits in that root, two trees away from its host."""
        slot = el.parent
        w = self._scopes.get(id(slot)) if self._scopes and slot is not None \
            else None
        if w is not None:
            return w.parent
        for p in el.parents:
            if shadow.is_wrapper(p):
                return p.parent
        return None

    def _dom_parent(self, el: Tag):
        """`el`'s parent element in the DOM, or None at the top of its tree
        (the document element, or a shadow root's top level)."""
        if shadow.is_assigned(el):
            return self._host_of_slotted(el)
        p = el.parent
        if p is None or isinstance(p, BeautifulSoup) or shadow.is_wrapper(p):
            return None
        return p

    # -- selectors ---------------------------------------------------------

    def _step(self, el: Tag) -> tuple[str, bool]:
        """(the compound selector that picks `el` among its siblings, or out
        of its whole tree; is it an anchor: does it pick `el` out of its
        whole tree on its own)."""
        tree = self._tree(el)
        i = el.get("id")
        # An id that holds one of the run's secrets (a page that wrote the
        # token it was sent into one), or the --http-user password
        # (holds_password), is no anchor: the locator goes by the element's
        # place instead (R5E-2); written as CSS escapes it, the password
        # would not be found in the step (R5R-2).
        if isinstance(i, str) and i and not holds_secret(i) \
                and not holds_password(i):
            low = _ascii_lower(i)
            if self._ids.get((tree, low)) == 1 and self._free(tree, id_=low):
                return "#" + css_ident(i), True
        name = _type_selector(el)
        low = _local_name(el)
        if holds_secret(el.name or "", ignore_case=True) \
                or holds_password(el.name or ""):
            # An element named for a secret or the password (a custom
            # element's name) is written by its place, as an id holding one
            # is: CSS escapes would hide it from the step's check (R6A-6).
            # In any case: a parser lowercases the name (R6C-6).
            name = "*"
        k = self._index.get(id(el))
        if name != "*" and id(el) not in self._shared:
            anchor = (tree == _DOCUMENT and low in ("html", "head", "body")
                      and self._names.get((tree, low)) == 1
                      and self._free(tree, name=low))
            return name, anchor
        if k is None:
            return name, False
        return f"{name}:nth-child({k})", False

    def _alone(self, el: Tag, step: str) -> bool:
        """Does `step`, `el`'s own step, match no other element of its tree
        (so a shadow root's top-level step needs no `:host >`)?"""
        tree = self._tree(el)
        low = _local_name(el)
        k = self._index.get(id(el))
        if step.startswith("#"):
            return True
        if step.startswith("*"):
            return (self._any_nth.get((tree, k)) == 1
                    and self._free(tree, any_name=True))
        if ":nth-child(" in step:
            return (self._nth.get((tree, low, k)) == 1
                    and self._free(tree, name=low))
        return self._names.get((tree, low)) == 1 and self._free(tree, name=low)

    def _within(self, el: Tag, budget: list) -> str | None:
        """The selector that finds `el` in its own tree, or None when it
        would take more steps than are left in `budget` ([steps left],
        shared by the trees of one locator)."""
        steps = []
        node = el
        while True:
            budget[0] -= 1
            if budget[0] < 0:
                return None
            step, anchor = self._step(node)
            steps.append(step)
            if anchor:
                break
            parent = self._dom_parent(node)
            if parent is None:
                if self._tree(node) == _DOCUMENT:
                    steps[-1] = ":root"     # the document element itself
                elif not self._alone(node, step):
                    steps.append(":host")   # a shadow root's top level
                    budget[0] -= 1
                break
            node = parent
        steps.reverse()
        return " > ".join(steps)

    def of(self, el) -> list[str] | None:
        """The locator for `el`, or None for anything not an element of the
        DOM (a shadow root's wrapper)."""
        if not isinstance(el, Tag) or isinstance(el, BeautifulSoup) or \
                shadow.is_wrapper(el):
            return None
        got = self._cache.get(id(el))
        if got is not None or id(el) in self._cache:
            return got
        budget = [MAX_STEPS]
        path = [self._within(el, budget)]
        w = self._scopes.get(id(el)) if self._scopes else None
        while w is not None and path[0] is not None:
            host = w.parent
            if not isinstance(host, Tag) or isinstance(host, BeautifulSoup):
                path = [None]
                break
            path.insert(0, self._within(host, budget))
            w = self._scopes.get(id(host)) if self._scopes else None
        if any(p is None for p in path):
            path = None                     # too deep to write (MAX_STEPS)
        self._cache[id(el)] = path
        return path
