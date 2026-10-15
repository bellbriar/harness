"""Read an XHTML document as a browser's XML parser reads it, into
BeautifulSoup.

A page served as application/xhtml+xml, or saved as .xhtml, .xht or .xhtm,
is XML to a browser, not HTML: names keep their case (`<A href>` is not a
link, `ALT` is not alt), `<x/>` closes itself, a CDATA section is text,
`xml:lang` sets the language, there are no implied elements and no
declarative shadow roots, and a document that is not well-formed is an error
page. html.parser, which read these before, did none of that (OR2-4).

The reader is the standard library's expat, with namespaces, so each
element carries its namespace (XHTML, SVG, MathML) as html5.parse gives it;
an element of another vocabulary keeps its prefix, so no rule takes an RDF
block's `<dc:title>` for the page's <title>. Elements are charged to the
page's element budget (html5.Budget), as html5.parse charges them.
As in Chromium 141 (measured):

* HTML's named character references (`&nbsp;`) are known only in a document
  whose DOCTYPE has one of the XHTML public identifiers Chromium
  recognizes, in text and in attribute values alike (the internal subset's
  own entities first, and whatever the XML declaration says of
  standalone); any other undeclared entity is an error, as XML says, and
  an external entity's text is left out, as Chromium loads none;
* a document whose root is not XHTML's <html> (an SVG image, an RSS feed,
  an XHTML page without its namespace) is not an HTML page: a browser shows
  it as XML;
* a document that is not well-formed shows an XML error in its place.

The last two are reported as pages the harness could not evaluate
(NotAPage, NotWellFormed), never as passes. Chromium shows the part before
an error under its error message; the harness does not evaluate that part.
"""
from __future__ import annotations

import re
import xml.parsers.expat as _expat
from html.entities import html5 as _NAMED

from bs4 import BeautifulSoup
from bs4.builder import HTMLTreeBuilder
from bs4.element import Comment, Doctype, ProcessingInstruction

from .html5 import AsciiTokenLists, Budget

XHTML_NS = "http://www.w3.org/1999/xhtml"
_PREFIXES = {"http://www.w3.org/XML/1998/namespace": "xml",
             "http://www.w3.org/1999/xlink": "xlink",
             "http://www.w3.org/2000/xmlns/": "xmlns"}
#: The public identifiers for which Chromium's XML parser knows HTML's named
#: character references (it reads no DTD).
XHTML_PUBLIC_IDS = frozenset((
    "-//W3C//DTD XHTML 1.0 Transitional//EN", "-//W3C//DTD XHTML 1.1//EN",
    "-//W3C//DTD XHTML 1.0 Strict//EN", "-//W3C//DTD XHTML 1.0 Frameset//EN",
    "-//W3C//DTD XHTML Basic 1.0//EN",
    "-//W3C//DTD XHTML 1.1 plus MathML 2.0//EN",
    "-//W3C//DTD XHTML 1.1 plus MathML 2.0 plus SVG 1.1//EN",
    "-//W3C//DTD MathML 2.0//EN", "-//WAPFORUM//DTD XHTML Mobile 1.0//EN",
    "-//WAPFORUM//DTD XHTML Mobile 1.1//EN",
    "-//WAPFORUM//DTD XHTML Mobile 1.2//EN"))


#: XML's own entities, known in every document.
_PREDEFINED = frozenset(("lt", "gt", "amp", "apos", "quot"))
#: An entity reference (not a character reference) in raw markup.
_REF = re.compile(rb"&([^#;&\s<>\"']+);")
_DTD: bytes | None = None
#: `standalone="yes"` in the XML declaration: expat then refuses entities
#: the (external) subset declares, which Chromium resolves under an XHTML
#: DOCTYPE whatever the declaration says. Rewritten to "no " in place, so
#: every offset after it stays.
_STANDALONE = re.compile(rb"""\A(<\?xml\s[^>]*?\bstandalone\s*=\s*)(["'])yes\2""")


def _xhtml_dtd() -> bytes:
    """HTML's named characters as XML entity declarations: what Chromium's
    XML parser knows under an XHTML DOCTYPE (it reads no DTD, and looks the
    names up in HTML's table). Each value is escaped twice, so `&LT;` is a
    literal "<", as there, not markup."""
    global _DTD
    if _DTD is None:
        out = []
        for name, value in _NAMED.items():
            if not name.endswith(";") or name[:-1] in _PREDEFINED:
                continue
            ref = "".join(f"&#38;#x{ord(c):X};" for c in value)
            out.append(f'<!ENTITY {name[:-1]} "{ref}">')
        _DTD = "\n".join(out).encode("ascii")
    return _DTD


def _attribute_refs(data: bytes, i: int) -> list[str]:
    """The entity names referenced in the attribute values of the start tag
    at data[i] (expat drops an undeclared one there without a word)."""
    names, quote, n = [], None, len(data)
    i += 1
    while i < n:
        c = data[i]
        if quote is not None:
            if c == quote:
                quote = None
            elif c == 0x26:
                m = _REF.match(data, i)
                if m:
                    names.append(m.group(1).decode("utf-8", "replace"))
        elif c in (0x22, 0x27):
            quote = c
        elif c == 0x3E:
            break
        i += 1
    return names


#: Entity expansion a page may hold (PR2-4), as libxml2 (Chromium's XML
#: parser) allows it: a million characters, or five times the page.
EXPANSION_ALLOWANCE = 1_000_000
EXPANSION_FACTOR = 5


#: How many entities may nest in one expansion: libxml2 (Chromium) counts
#: the document as one input and stops past 40, so a 40th entity is refused.
MAX_ENTITY_DEPTH = 39


def _expanded(name: str, values: dict, memo: dict,
              depth: int = 0) -> tuple[int, int]:
    """(how many characters the internal entity `name` expands to, how many
    entities nest in that expansion, itself included). Its references to
    other declared entities are expanded too; a character reference or an
    undeclared name counts as one character. Recursion, which XML forbids
    (expat refuses it on use), counts as nothing more. Both numbers are
    kept per entity, so one expanded first near the top is still judged
    by its full nesting when reached deeper (PR3-8)."""
    if name in memo:
        return memo[name] or (0, 0)      # None: a cycle, in progress
    if depth >= MAX_ENTITY_DEPTH:
        raise _too_deep()
    memo[name] = None
    text = values[name]
    total, height, last = 0, 0, 0
    for m in _VALUE_REF.finditer(text):
        total += m.start() - last
        last = m.end()
        ref = m.group(1)
        if ref in values:
            size, h = _expanded(ref, values, memo, depth + 1)
            total += size
            height = max(height, h)
        else:
            total += 1
    total += len(text) - last
    memo[name] = (total, height + 1)
    return memo[name]


def _too_deep() -> "NotWellFormed":
    return NotWellFormed(f"its entities nest more than {MAX_ENTITY_DEPTH} "
                         "deep, which a browser refuses as an XML error")


#: Markup in which a reference is not one: comments, CDATA sections and
#: processing instructions (attribute values hold no "<").
_NOT_CONTENT = re.compile(rb"<!--.*?-->|<!\[CDATA\[.*?\]\]>|<\?.*?\?>", re.S)


#: An entity or character reference in a declared entity's text.
_VALUE_REF = re.compile(r"&#?([^;&\s]+);")


class NotWellFormed(ValueError):
    """The document is not well-formed XML: a browser shows an XML error."""


class NotAPage(ValueError):
    """The document is XML but not an XHTML page."""


def _split(name: str) -> tuple[str | None, str, str | None]:
    """expat's "uri local prefix" (namespace_prefixes on) as its parts."""
    parts = name.split(" ")
    if len(parts) == 1:
        return None, parts[0], None
    if len(parts) == 2:
        return parts[0], parts[1], None
    return parts[0], parts[1], parts[2]


def _attr_name(name: str) -> str:
    """An attribute's name for the rules: its local name, or, in a
    namespace, the namespace's usual prefix whatever prefix the document
    gave it (`xl:href` is `xlink:href`: R6F-8), else the document's own
    (but one of those usual ones) or `ns`."""
    uri, local, prefix = _split(name)
    if uri is None:
        return local
    usual = _PREFIXES.get(uri)
    if usual is None and prefix in _PREFIXES.values():
        prefix = None
    return f"{usual or prefix or 'ns'}:{local}"


#: The namespaces whose elements the rules know by their local names.
_KNOWN = {XHTML_NS, "http://www.w3.org/2000/svg",
          "http://www.w3.org/1998/Math/MathML"}


def _element_name(name: str) -> tuple[str, str | None]:
    """An element's name for the rules, and its namespace. An element of
    another vocabulary keeps its prefix (`<dc:title>` in an RDF block is
    not a <title>), and one in another default namespace or in none
    (`<img xmlns="urn:x"/>`, `<a xmlns="">`) is given one, `ns:`, since
    to Chromium it is a plain element too: no image, no link (PR2-5)."""
    uri, local, prefix = _split(name)
    if uri not in _KNOWN:
        return f"{prefix or 'ns'}:{local}", uri
    return local, uri


class _XMLReplay(AsciiTokenLists, HTMLTreeBuilder):
    """A BeautifulSoup tree builder that feeds expat's events to the soup.
    (An HTML tree builder, so attributes such as class read as they do from
    html5.parse; names and namespaces are XML's.)"""

    NAME = "bellbriar-xhtml"
    features = [NAME, "xml", "xhtml"]
    TRACKS_LINE_NUMBERS = True

    def __init__(self, text: str):
        super().__init__()
        self._text = text

    def prepare_markup(self, markup, user_specified_encoding=None,
                       document_declared_encoding=None,
                       exclude_encodings=None):
        yield (markup, None, None, False)

    def feed(self, markup) -> None:
        soup = self.soup
        data = _STANDALONE.sub(lambda m: m.group(1) + m.group(2) + b"no"
                               + m.group(2) + b" ",
                               self._text.encode("utf-8", "surrogatepass"),
                               count=1)
        p = _expat.ParserCreate(encoding="utf-8", namespace_separator=" ")
        p.namespace_prefixes = True
        p.ordered_attributes = True
        p.buffer_text = True
        # The DOCTYPE's external subset is offered to `external`, which
        # reads none from the network: under an XHTML DOCTYPE it declares
        # HTML's named characters, as Chromium knows them there.
        p.SetParamEntityParsing(_expat.XML_PARAM_ENTITY_PARSING_ALWAYS)
        state = {"public": None, "root": None, "external": False,
                 "delivered": 0}
        declared = set(_PREDEFINED)
        budget = Budget(self._text)
        # Characters the entities a page declares may add (PR2-4): past a
        # million, and past five times the page, a browser stops with an
        # XML error (libxml2's amplification limit), and the harness stops
        # before they fill memory.
        allowance = max(EXPANSION_ALLOWANCE,
                        EXPANSION_FACTOR * len(self._text))

        def amplified() -> NotWellFormed:
            return NotWellFormed(
                f"its own entities add more than {allowance:,} characters "
                f"to it (a million, or {EXPANSION_FACTOR} times its size), "
                "which a browser refuses as an XML error")

        def deliver(count: int) -> None:
            state["delivered"] += count
            if state["delivered"] - len(self._text) > allowance:
                raise amplified()

        def undefined(name: str) -> NotWellFormed:
            return NotWellFormed(
                f"line {p.CurrentLineNumber}: the entity &{name}; is not "
                "defined (a browser knows HTML's named characters only "
                "under an XHTML DOCTYPE)")

        def start(name, attrs):
            budget.charge(len(attrs) // 2)
            if state["external"]:
                # With an external subset expat drops an undeclared entity
                # in an attribute value; Chromium shows an XML error.
                at = p.CurrentByteIndex
                if 0 <= at < len(data) and data[at] == 0x3C:
                    for ref in _attribute_refs(data, at):
                        if ref not in declared:
                            raise undefined(ref)
            local, uri = _element_name(name)
            if state["root"] is None:
                state["root"] = (uri, _split(name)[1])
            values = {}
            for i in range(0, len(attrs), 2):
                values.setdefault(_attr_name(attrs[i]), attrs[i + 1])
                deliver(len(attrs[i + 1]))
            soup.handle_starttag(local, uri, None, values,
                                 sourceline=p.CurrentLineNumber,
                                 sourcepos=p.CurrentColumnNumber)

        def end(name):
            soup.handle_endtag(_element_name(name)[0])

        def text(chars):
            deliver(len(chars))
            soup.handle_data(chars)

        def comment(chars):
            soup.endData()
            soup.handle_data(chars)
            soup.endData(Comment)

        def pi(target, chars):
            soup.endData()
            soup.handle_data(f"{target} {chars}" if chars else target)
            soup.endData(ProcessingInstruction)

        def doctype(name, system_id, public_id, has_internal_subset):
            state["public"] = public_id
            state["external"] = bool(system_id or public_id)
            soup.endData()
            soup.handle_data(Doctype.for_name_and_ids(name or "", public_id,
                                                      system_id))
            soup.endData(Doctype)

        values: dict = {}           # a declared internal entity's text

        def entity(name, is_parameter_entity, value=None, *_rest):
            if not is_parameter_entity:
                declared.add(name)
                if value is not None:      # the first declaration binds
                    values.setdefault(name, value)

        def end_doctype():
            # Before any content is read: what the page's own entities
            # would expand it to, so an attribute cannot be blown up before
            # deliver() sees it (PR2-4). References in comments, CDATA and
            # processing instructions are none (PR3-8).
            if not values:
                return
            at = max(p.CurrentByteIndex, 0)
            grow = 0
            memo: dict = {}
            for m in _REF.finditer(_NOT_CONTENT.sub(b"", data[at:])):
                name = m.group(1).decode("utf-8", "replace")
                if name in values:
                    size, height = _expanded(name, values, memo)
                    if height > MAX_ENTITY_DEPTH:
                        raise _too_deep()
                    grow += size - len(m.group(0))
                    if grow > allowance:
                        raise amplified()

        def external(context, base, system_id, public_id):
            # The DOCTYPE's subset (context None) is the only external
            # entity read, and only HTML's table: Chromium loads none (an
            # external general entity's text is left out, without error).
            if context is None and state["public"] in XHTML_PUBLIC_IDS:
                sub = p.ExternalEntityParserCreate(None)
                sub.Parse(_xhtml_dtd(), True)
            return 1

        def skipped(name, is_parameter_entity):
            # An undeclared entity in content, under an external subset.
            if not is_parameter_entity:
                raise undefined(name)

        p.StartElementHandler = start
        p.EndElementHandler = end
        p.CharacterDataHandler = text
        p.CommentHandler = comment
        p.ProcessingInstructionHandler = pi
        p.StartDoctypeDeclHandler = doctype
        p.EntityDeclHandler = entity
        p.EndDoctypeDeclHandler = end_doctype
        p.ExternalEntityRefHandler = external
        p.SkippedEntityHandler = skipped
        try:
            p.Parse(data, True)
        except _expat.ExpatError as exc:
            raise NotWellFormed(
                f"line {exc.lineno}, column {exc.offset + 1}: "
                f"{_expat.ErrorString(exc.code)}") from None
        soup.endData()
        uri, local = state["root"] or (None, "")
        if (uri, local) != (XHTML_NS, "html"):
            where = f"in namespace {uri}" if uri else "in no namespace"
            raise NotAPage(f"its root element is <{local}> {where}, not "
                           "XHTML's <html>: a browser shows it as XML, not "
                           "as an HTML page")


def parse(text: str) -> BeautifulSoup:
    """The XHTML document `text` (decoded), as BeautifulSoup. Raises
    NotWellFormed or NotAPage (module docstring), or html5.TooManyElements
    past the page's element budget."""
    return BeautifulSoup("", builder=_XMLReplay(text))
