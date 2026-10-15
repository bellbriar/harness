"""Parse a page's HTML as a browser does, into BeautifulSoup.

The static rules read BeautifulSoup trees. A page's own HTML (a file, or
what a server sent) is parsed here with JustHTML, which implements the
WHATWG tree construction algorithm and is tested against WPT's
tree-construction suite: omitted end tags, misnested tags, tables,
<template>, <select>, foreign content and the rest come out as a browser
builds them. Python's html.parser, which parsed them before, is not an HTML
parser in that sense: it nests what it sees, so `<li>a<li><a href=/x></a>`
put the empty link inside the first item, and a minified page that omits
optional end tags lost findings.

The tree is copied into BeautifulSoup, so the rules keep their API:

* each element carries the line and column of its start tag's "<"
  (sourceline, sourcepos), as html.parser gave them; an element no start
  tag made (an implied <tbody>) has none;
* <template> content is the template's children, as html.parser held it;
* scripting is on, so <noscript> content is text, as in a browser that
  runs scripts;
* a processing instruction (`<?php ... ?>`) becomes a comment of its text
  from the "?" to the first ">", as Chromium 141 builds it;
* past 512 open elements Chromium attaches each new element to the current
  node's parent instead (its maximum parser tree depth); so does the copy,
  so a page nested 20,000 deep reads as a browser builds it (approximately:
  Chromium decides it while parsing, the copy afterwards, so an implied
  <tbody> or an element the adoption agency moves past that depth can land
  one level off; comments are not moved);
* a declarative shadow root (`<template shadowrootmode>`) is decided as
  the parser meets the template, as Chromium decides it: it attaches to the
  element the template was opened in, if that element may host one and has
  none yet; such a template never enters the document, so markup the
  adoption agency moves later does not carry it along (shadow.materialize
  turns it into the root).

A rendered capture is not parsed here. It is the browser's serialization of
the live DOM, which html.parser reads back as it was; an HTML5 parser would
rebuild nesting the live page really had (a <div> a script put inside a
<p>). checks_static.PageContext.parse chooses the reader.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup
from bs4.builder import HTMLTreeBuilder
from bs4.element import Comment, Doctype

from .shadow import DECLARATIVE, declares_root, valid_host_name

try:
    from justhtml.dom import Template, Text
    from justhtml.parser import engine as _engine
    from justhtml.parser.engine import ParseEngine, compile_raw_engine_plan
except ImportError as exc:                       # pragma: no cover
    raise ImportError(
        "bellbriar-harness parses HTML with justhtml 3.x (>= 3.13): "
        "pip install 'justhtml>=3.13,<4'") from exc

#: Since customizable <select> (whatwg/html#10548, shipped in Chromium),
#: <select> is in the base list of "has an element in scope", so every
#: scope stops at it: a <p>, <hr>, <div> or <a> inside a select inside a
#: <p>, <a>, <button>, <dt> or <dd> stays in the select instead of closing
#: the outer element and tearing the select apart (OR-7). JustHTML 3.13
#: still has the older list; its scope checks read these module constants,
#: so they gain "select" here (measured: 409 of 410 select cases now build
#: Chromium 141's tree, against 381 before).
_SCOPES = ("_DEFAULT_SCOPE_BOUNDARIES", "_P_SCOPE_BOUNDARIES",
           "_LIST_ITEM_SCOPE_BOUNDARIES", "_DEFINITION_SCOPE_BOUNDARIES")
for _name in _SCOPES:
    if isinstance(getattr(_engine, _name, None), frozenset):
        setattr(_engine, _name, getattr(_engine, _name) | {"select"})
#: <search> is a "special" element in the spec, but not to Chromium 141's
#: parser (measured): `<a href=/x><search>Menu</a>` is one link holding the
#: search there, where the spec's adoption agency leaves an empty link and a
#: copy inside the search, and `<li>a<search><li>b` closes the first item.
#: (It still closes an open <p>, in both.)
for _name in ("SPECIAL_ELEMENTS", "_GENERAL_END_TAG_BOUNDARIES"):
    _value = getattr(_engine, _name, None)
    if isinstance(_value, (set, frozenset)) and "search" in _value:
        setattr(_engine, _name, frozenset(_value - {"search"}))

NAMESPACES = {"html": "http://www.w3.org/1999/xhtml",
              "svg": "http://www.w3.org/2000/svg",
              "math": "http://www.w3.org/1998/Math/MathML"}
HTML_NS = NAMESPACES["html"]
#: Chromium's maximum parser tree depth (kMaximumHTMLParserDOMTreeDepth):
#: an element inserted while more than this many elements are open goes
#: to the current node's parent instead.
MAX_DEPTH = 512


class _TooDeep(Exception):
    """The tree is deeper than a browser builds it."""


#: The most a page may build, in elements, each attribute counting as a
#: thirtieth of one (measured: an element takes about 1.2 KB once copied
#: into BeautifulSoup, an attribute about 42 bytes): one per byte of its
#: markup (no real markup is that dense) but at least 200,000, and never
#: more than 1.5 million, about 1.8 GB. HTML's tree construction can
#: multiply elements far beyond the markup: a 19 KB page of 1,000 open
#: <b id> elements and 1,000 paragraphs builds a million clones (16 s,
#: 1.2 GB) as the parser reopens every <b> in every paragraph, and 32 MiB
#: built that way would exhaust memory and end the run with no report
#: (OR-10); with 150 attributes on each <b>, a million clones would take
#: 10 GB (OR2-1).
MIN_ELEMENT_BUDGET = 200_000
MAX_ELEMENT_BUDGET = 1_500_000
#: How many attributes weigh as much as one element.
ATTRIBUTES_PER_ELEMENT = 30


def element_budget(html: str) -> int:
    return min(MAX_ELEMENT_BUDGET, max(MIN_ELEMENT_BUDGET, len(html)))


class TooManyElements(ValueError):
    """The page builds more elements than the harness reads
    (element_budget): it is reported as not evaluated, never as a pass."""


class Budget:
    """A page's element budget, charged as a reader builds each element: the
    HTML parser here, and the XML and DOM readers (checks_static), whose
    elements are bounded by their markup but not by the 1.5 million cap."""

    def __init__(self, text: str, why: str = ""):
        self.limit = element_budget(text)
        self.count = 0.0
        self.why = why

    def charge(self, attributes: int) -> None:
        self.count += 1 + attributes / ATTRIBUTES_PER_ELEMENT
        if self.count > self.limit:
            raise TooManyElements(
                f"its markup builds more than {self.limit:,} elements, each "
                f"{ATTRIBUTES_PER_ELEMENT} attributes counting as one more"
                f"{self.why}; the harness reads no further rather than "
                "exhaust memory")


#: The elements whose children HTML's serializer never writes (the HTML
#: fragment serialization algorithm's list), so a serialized DOM read back
#: holds nothing inside them. BeautifulSoup's html.parser list adds
#: menuitem, command, spacer, nextid, isindex and image, whose children a
#: browser does write: read as empty, those children would move out beside
#: them (PR2-7).
VOID_ELEMENTS = frozenset({
    "area", "base", "basefont", "bgsound", "br", "col", "embed", "frame",
    "hr", "img", "input", "keygen", "link", "meta", "param", "source",
    "track", "wbr"})


class BudgetSoup(BeautifulSoup):
    """A browser's serialization of a DOM (a rendered capture) read with
    html.parser, with the serializer's void elements (VOID_ELEMENTS), each
    element charged to the page's element budget: a 30 MB capture of a flat
    list would otherwise build ten million elements and exhaust memory.
    `on_duplicate_attribute` goes to html.parser."""

    def __init__(self, markup: str, features: str = "html.parser",
                 **kwargs):
        from bs4.builder import HTMLParserTreeBuilder
        if features != "html.parser":
            raise ValueError("BudgetSoup reads a serialized DOM with "
                             "html.parser")
        self._bb_budget = Budget(markup)
        builder = type("_BudgetBuilder", (AsciiTokenLists,
                                          HTMLParserTreeBuilder), {})(**{
            k: kwargs.pop(k) for k in ("on_duplicate_attribute",)
            if k in kwargs})
        builder.empty_element_tags = set(VOID_ELEMENTS)
        super().__init__(markup, builder=builder, **kwargs)

    def handle_starttag(self, name, namespace, nsprefix, attrs, *args,
                        **kwargs):
        self._bb_budget.charge(len(attrs))
        return super().handle_starttag(name, namespace, nsprefix, attrs,
                                       *args, **kwargs)


#: Why HTML can build more elements than it has tags.
_REOPENED = (" (the parser reopens formatting elements such as <b> in every "
             "block that follows them)")


class _Engine(ParseEngine):
    """JustHTML's engine, noting the element each <template> was opened in
    (the "adjusted current node" a declarative shadow root attaches to), and
    counting elements against the page's budget."""

    def _insert_raw_element(self, name, attrs, self_closing, parent, **kw):
        node = super()._insert_raw_element(name, attrs, self_closing, parent,
                                           **kw)
        d = self.__dict__
        budget = d.get("bb_budget")
        if budget is not None:
            budget.charge(len(node.attrs or ()))
        if type(node) is Template:
            d.setdefault("bb_templates", []).append((node, parent))
        return node

    def _append_raw_literal_text(self, text, source_pos=None):
        # A CDATA section starts only in foreign content proper in Chromium
        # 141: at an HTML or MathML text integration point (an SVG <title>,
        # <desc> or <foreignObject>, a MathML <mi> to <mtext>, an HTML
        # <annotation-xml>) its "<!" opens a bogus comment that ends at the
        # first ">", so `<svg><title><![CDATA[Home]]>` names nothing
        # (OR2-9). The spec, and JustHTML, read the section as text there.
        source = getattr(self, "_html_input", None)
        if (isinstance(source_pos, int) and source_pos >= 9
                and isinstance(source, str)
                and source[source_pos - 9:source_pos].lower() == "<![cdata["
                and self._stack and _integration_point(self._stack[-1])):
            head, gt, rest = text.partition(">")
            closed = source.startswith("]]>", source_pos + len(text))
            if gt:
                super()._append_comment("[CDATA[" + head, source_pos - 9)
                return super()._append_raw_literal_text(
                    rest + ("]]>" if closed else ""), source_pos + len(head) + 1)
            return super()._append_comment(
                "[CDATA[" + text + ("]]" if closed else ""), source_pos - 9)
        return super()._append_raw_literal_text(text, source_pos)

    def _find_open_index_in_current_scope(self, name):
        # A <button> start tag closes an open button only when that is "in
        # scope" (the default scope, which <select> now bounds); JustHTML
        # looks only as far as a <template>.
        if name == "button":
            return self._find_open_index_before_boundary(
                "button", _engine._DEFAULT_SCOPE_BOUNDARIES)
        return super()._find_open_index_in_current_scope(name)


def _integration_point(node) -> bool:
    """An HTML integration point or a MathML text integration point."""
    ns, name = getattr(node, "namespace", None), getattr(node, "name", "")
    if ns == "svg":
        return name in ("foreignObject", "desc", "title")
    if ns == "math":
        if name in ("mi", "mo", "mn", "ms", "mtext"):
            return True
        if name == "annotation-xml":
            encoding = ((getattr(node, "attrs", None) or {}).get("encoding")
                        or "").lower()
            return encoding in ("text/html", "application/xhtml+xml")
    return False


def _element(node) -> bool:
    return (node is not None and type(node) is not Text
            and not (node.name or "#").startswith(("#", "!")))


def _declarative_roots(engine, root) -> set:
    """The templates the parser attaches as shadow roots, by id: one with
    shadowrootmode open or closed, opened in an element that may host one
    (shadow.valid_host_name) and has none yet; a second such template there
    stays a template (OR-4). The template is put back in its host if the
    adoption agency later moved it into another element (OR-6), since in a
    browser it never was in the document to move. Without the engine's
    record (another JustHTML), each template's final parent stands in."""
    found = engine.__dict__.get("bb_templates")
    if found is None:
        found, stack = [], [root]
        while stack:
            node = stack.pop()
            for kid in reversed(_kids(node)):
                if type(kid) is Template:
                    found.append((kid, node))
                if _element(kid):
                    stack.append(kid)
        found.reverse()
        found.sort(key=lambda pair: (pair[0].origin_location or (0, 0)))
    roots: set = set()
    hosts: set = set()
    for tpl, host in found:
        if not declares_root((tpl.attrs or {}).get("shadowrootmode")):
            continue
        if not _element(host) or id(host) in hosts or not valid_host_name(
                host.name, host.namespace in (None, "html")):
            continue
        hosts.add(id(host))
        roots.add(id(tpl))
        if tpl.parent is not host:
            old = tpl.parent
            if old is not None:
                old.children.remove(tpl)
            host.children.insert(0, tpl)
            tpl.parent = host
    return roots


def _tree(html: str):
    """JustHTML's parse of a whole document, unsanitized, with locations.

    The engine is called directly: JustHTML(track_node_locations=True) also
    tracks tag spans, which turns bogus markup (a malformed comment, a stray
    `</b test`) into text instead of what the tree construction makes of
    it. Without tag spans the tree is the plain parse's, with locations.

    `html` is decoded text: its byte-order mark, if it had one, is gone
    (encoding.sniff). A U+FEFF still at its start is a character, as in a
    browser: a page saved with two byte-order marks renders in quirks mode.

    Line breaks are normalized first, as HTML's input stream does (CRLF and
    a lone CR become LF), so a file saved with CR line endings reports the
    lines it has rather than everything on line 1.
    """
    if "\r" in html:
        html = html.replace("\r\n", "\n").replace("\r", "\n")
    engine = _Engine(html, fragment=False, scripting_enabled=True,
                     plan=compile_raw_engine_plan(False, True),
                     track_node_locations=True, track_tag_spans=False)
    engine.__dict__["bb_budget"] = Budget(html, _REOPENED)
    root = engine.parse()
    return root, _declarative_roots(engine, root), html


def _kids(node) -> list:
    if type(node) is Template and node.template_content is not None:
        return node.template_content.children
    return node.children or []


def _set_kids(node, kids: list) -> None:
    holder = (node.template_content
              if type(node) is Template and node.template_content is not None
              else node)
    holder.children = kids
    for k in kids:
        k.parent = holder


def _flatten(root, roots=frozenset()) -> None:
    """Chromium's depth limit, applied to a finished tree: an element with
    more than MAX_DEPTH element ancestors (the elements open when it was
    inserted) becomes a child of its parent's new parent, in document
    order. Text stays in the element that held it. Nothing leaves a
    <template>: its content is a fragment of its own in Chromium, whose
    children have no parent to move to (they are flattened to the content's
    top level at most), and a declarative shadow root (`roots`) stays with
    its host (OR2-2)."""
    new_kids: dict[int, list] = {}
    owner: dict[int, object] = {}          # id(element) -> its new parent
    order = []                             # every node with children
    stack = [(root, None, 0)]              # node, new parent, depth
    def element(n) -> bool:
        return type(n) is not Text and not n.name.startswith(("#", "!"))

    while stack:
        node, parent, depth = stack.pop()
        if parent is not None:
            new_kids.setdefault(id(parent), []).append(node)
        if node is not root and not element(node):
            continue
        order.append(node)
        child_depth = depth + 1 if node is not root else depth
        ceiling = type(node) is Template
        for kid in reversed(_kids(node)):
            target = node
            if element(kid):
                if (child_depth > MAX_DEPTH and id(node) in owner
                        and not ceiling and id(kid) not in roots):
                    target = owner[id(node)]
                owner[id(kid)] = target
            stack.append((kid, target, child_depth))
    for node in order:
        _set_kids(node, new_kids.get(id(node), []))


def _bogus_comment(node, source: str) -> str:
    """What Chromium 141 keeps of a processing instruction: a comment of
    everything from the "?" to the first ">" (`<?a?b>` is "?a?b"), read
    from the source where JustHTML recorded the node's offset; JustHTML's
    own target-and-data form ("a ?b") otherwise."""
    meta = getattr(node, "_metadata", None)
    start = meta[1] if isinstance(meta, list) and len(meta) > 1 else None
    if (isinstance(start, int) and source
            and source.startswith("<?", start)):
        end = source.find(">", start)
        return source[start + 1:end if end >= 0 else len(source)]
    return f"?{node.data or ''}?"


def _emit(soup: BeautifulSoup, root, depth_limit: bool,
          roots: set = frozenset(), source: str = "") -> None:
    """Replay the tree into BeautifulSoup as parser events, marking the
    templates in `roots` (ids) as declarative shadow roots. `source` is the
    text parsed, for processing instructions (_bogus_comment)."""
    start = soup.handle_starttag
    end = soup.handle_endtag
    data = soup.handle_data
    end_data = soup.endData
    stack = [(None, iter(_kids(root)))]
    while stack:
        el, it = stack[-1]
        for node in it:
            if type(node) is Text:
                data(node.data)
                continue
            name = node.name
            if name == "#comment":
                end_data()
                data(node.data or "")
                end_data(Comment)
                continue
            if name == "#processing-instruction":
                end_data()
                data(_bogus_comment(node, source))
                end_data(Comment)
                continue
            if name == "!doctype":
                d = node.data
                end_data()
                data(Doctype.for_name_and_ids(d.name or "", d.public_id,
                                              d.system_id)
                     if d is not None else "")
                end_data(Doctype)
                continue
            if depth_limit and len(stack) > MAX_DEPTH + 1:
                raise _TooDeep
            loc = node.origin_location
            attrs = {k: "" if v is None else v
                     for k, v in (node.attrs or {}).items()}
            tag = start(name, NAMESPACES.get(node.namespace, HTML_NS), None,
                        attrs, sourceline=loc[0] if loc else None,
                        sourcepos=loc[1] - 1 if loc else None)
            if roots and id(node) in roots:
                tag.__dict__[DECLARATIVE] = True
            stack.append((node, iter(_kids(node))))
            break
        else:
            stack.pop()
            if el is not None:
                end(el.name)


#: A token of a list HTML splits at ASCII white space (`class`).
HTML_TOKENS = re.compile(r"[^\t\n\f\r ]+")


class AsciiTokenLists:
    """A BeautifulSoup tree builder's mixin: a token list (`class`, `rel`)
    splits at ASCII white space alone, as HTML splits one:
    `class="a\u3000b"` is one class, as Chromium 141 has it, in every
    reader (R6X-2, R6Z-4)."""

    def _replace_cdata_list_attribute_values(self, tag_name, attrs):
        if not attrs or not self.cdata_list_attributes:
            return attrs
        universal = self.cdata_list_attributes.get("*", set())
        specific = self.cdata_list_attributes.get(tag_name.lower(), set())
        for attr in list(attrs.keys()):
            value = attrs[attr]
            if (attr in universal or attr in specific) \
                    and isinstance(value, str):
                attrs[attr] = self.attribute_value_list_class(
                    HTML_TOKENS.findall(value))
        return attrs


class _Replay(AsciiTokenLists, HTMLTreeBuilder):
    """A BeautifulSoup tree builder that replays a finished JustHTML tree."""

    NAME = "bellbriar-html5"
    features = [NAME, "html", "html5"]
    TRACKS_LINE_NUMBERS = True

    def __init__(self, root, depth_limit: bool = True, roots=frozenset(),
                 source: str = ""):
        super().__init__()
        self._root = root
        self._depth_limit = depth_limit
        self._roots = roots
        self._source = source

    def prepare_markup(self, markup, user_specified_encoding=None,
                       document_declared_encoding=None,
                       exclude_encodings=None):
        yield (markup, None, None, False)


    def feed(self, markup) -> None:
        _emit(self.soup, self._root, self._depth_limit, self._roots,
              self._source)


def parse(html: str) -> BeautifulSoup:
    """The document a browser builds from `html`, as BeautifulSoup. The
    templates the parser attaches as declarative shadow roots are marked
    (shadow.DECLARATIVE) for shadow.materialize."""
    root, roots, source = _tree(html)
    try:
        return BeautifulSoup("", builder=_Replay(root, roots=roots,
                                                 source=source))
    except _TooDeep:
        _flatten(root, roots)
        return BeautifulSoup("", builder=_Replay(root, depth_limit=False,
                                                 roots=roots, source=source))
