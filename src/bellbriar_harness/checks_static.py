"""Deterministic DOM rules (the D-layer).

Every rule binds to rulebook.json for its SC mapping, tier, and citations.
Design constraints:

- fail only what markup alone can prove; anything needing judgment or a
  rendered/interactive context is `needs_review` or another layer's job;
- Tier 1 mirrors the pled complaint boilerplate (see docs/METHODOLOGY.md);
- accessible-name checks use accname.static_accname (presence only).
"""
from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass, field

from bs4 import BeautifulSoup
from bs4.element import NavigableString, PreformattedString, Tag

from . import encoding, html5, xhtml
from .accname import (aria_hidden, chromium_cut, static_accname,
                      subtree_text, _embedded, _norm, _first_summary,
                      _axe_why, _label_for_control)
from .redact import (REDACTED, WITHHELD_MESSAGE, has_run_secrets,
                     holds_password, redact_markup, scrub_for_hash,
                     scrub_secrets, secret_reach)
from .aria import (ARIA_ATTRS, CONTROL_NAME_ROLES, FORM_FIELD_ROLES,
                   ID_REF_ATTRS, IMG_ROLES, NAME_FROM_CONTENT_ROLES,
                   NAME_REQUIRED_ROLES, PROGRESS_ROLES, ROLES,
                   WIDGET_NAME_ROLES)
from .langtags import (GRANDFATHERED, ISO_639_2_TWO_LETTER,
                       PRIMARY_LANGUAGE_SUBTAGS, REGISTRY_DATE)
from .shadow import DECLARATIVE as _DECLARATIVE
from .shadow import WRAPPER as _WRAPPER
from .shadow import is_wrapper as _is_wrapper
from .shadow import mark_capture as _mark_capture
from .shadow import materialize as _materialize_shadow_roots
from .shadow import tree_scopes as _tree_scopes
from .shadow import valid_host as _valid_host  # noqa: F401
from .model import (BLOCKER, CURRENT_PAGE, FAIL, HIDDEN_VIEW,  # noqa: F401
                    MINOR, MODERATE, NEEDS_REVIEW, PROVENANCE_ATTR, SERIOUS,
                    Finding, RuleResult, hidden_attr, muted_attr,
                    view_hidden_attr)
# Inline-style reading lives in style.py (accname needs it too); the
# names stay importable from here.
from .style import (  # noqa: F401
    _CSS_ESCAPE_RE, _CSS_WIDE, _DISPLAY_INNER, _DISPLAY_ONE, _DISPLAY_OUTER,
    _IMPORTANT_RE, _STYLE_COMMENT_RE, _STYLE_VALUES, PageStyles,
    _css_unescape, _display_multi, _inline_style, _style_hides,
    _valid_style_value, author_display_shows, cascade_decides, css_urls,
    display_later, namespace_of, skips_content, ua_hidden as _ua_hidden,
    ua_invisible as _ua_invisible, until_found as _until_found,
    visibility_later)

DOC_EXTS = (".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx")
LANG_RE = re.compile(r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{1,8})*$")
#: The name of a skip link: "Skip to main content", "Skip navigation",
#: "Jump to content", "Go to main content". A first in-page link named
#: anything else ("Back to top", "Main menu") is not a skip link.
SKIP_TEXT_RE = re.compile(
    r"\b(skip|jump)\b|\bmain\s+content\b|\bto\s+(the\s+)?(main|content)\b",
    re.I)


#: How PageContext.parse reads markup: as a page's own HTML, as a
#: browser's serialization of a live DOM, or as an XML document.
READERS = ("html", "dom", "xml")


class IdScopes(dict):
    """The page's element ids as getElementById finds them in each tree.
    As a dict: the document's (the first element with each id, outside
    <template> and <noscript>), which is what a fragment (`#main`) reaches.
    within(el): the ids of the tree `el` is in, the document or the shadow
    root it belongs to, which is all an aria-labelledby or a <label for>
    there can reach (OR-2): two instances of one component may each hold
    an id "f", and a light-DOM label cannot name a control inside one."""

    def __init__(self, soup=None, scopes=None):
        super().__init__()
        #: {id(element): its shadow root's wrapper, or None}; {} without
        #: shadow roots (shadow.tree_scopes).
        self.scopes = scopes or {}
        self._trees: dict = {}
        #: {(tree key, id): how many elements carry it}; key 0 is the
        #: document, else id() of the root's wrapper.
        self.counts: dict = {}
        if soup is None:
            return
        for el in soup.find_all(attrs={"id": True}):
            if _inert_content(el):
                continue        # not in the document: no reference finds it
            i = el.get("id")
            key = self.key(el)
            self.counts[(key, i)] = self.counts.get((key, i), 0) + 1
            (self if key == 0 else self._trees.setdefault(key, {})) \
                .setdefault(i, el)

    def scope_of(self, el):
        """The wrapper of the shadow root `el` is in, or None (the
        document)."""
        return self.scopes.get(id(el)) if self.scopes else None

    def key(self, el) -> int:
        tree = self.scope_of(el)
        return 0 if tree is None else id(tree)

    def within(self, el) -> dict:
        if not self.scopes:
            return self
        key = self.key(el)
        return self if key == 0 else self._trees.get(key, {})


#: How many element-to-ancestor steps a page may hold in all (the sum of
#: every element's depth). The rules walk up from elements, so their work
#: grows with it: 40 million is a few seconds of rules, past the largest
#: real pages measured (a 31 MB server-rendered page holds about 18 million),
#: and 50,000 nested elements (1.25 billion) took two minutes and would take
#: hours at 3 MB (OR2-3).
MAX_DEPTH_WORK = 40_000_000


class TooDeeplyNested(ValueError):
    """The page's elements sit too deep to evaluate in reasonable time: it
    is reported as not evaluated, never as a pass."""


def too_deep(soup) -> None:
    """Raise TooDeeplyNested when the soup's elements hold more than
    MAX_DEPTH_WORK ancestor steps in all. One pass, no recursion."""
    total = 0
    stack = [(soup, 0)]
    while stack:
        node, depth = stack.pop()
        for child in node.contents:
            if isinstance(child, Tag):
                total += depth + 1
                stack.append((child, depth + 1))
        if total > MAX_DEPTH_WORK:
            raise TooDeeplyNested(
                f"its elements are nested so deep (more than "
                f"{MAX_DEPTH_WORK:,} steps from element to ancestor in all) "
                "that the rules would take hours; the harness reads no "
                "further")


def ids_within(ids, el) -> dict:
    """The ids `el`'s own tree holds: IdScopes.within, or `ids` itself when
    it is a plain {id: element} map."""
    return ids.within(el) if isinstance(ids, IdScopes) else ids


def scope_of(ids, el):
    return ids.scope_of(el) if isinstance(ids, IdScopes) else None


@dataclass
class PageContext:
    path: str
    soup: BeautifulSoup
    ids: dict[str, Tag] = field(default_factory=dict)
    id_counts: dict[str, int] = field(default_factory=dict)
    #: The attribute the harness's own rendered capture wrote provenance
    #: into, or None. Findings are attributed only when this is set.
    provenance_attr: str | None = None
    #: How the markup was read (READERS).
    reader: str = "html"
    #: What the page's own <style> elements say about display and
    #: visibility (style.PageStyles), read once, when a rule first asks.
    _styles: PageStyles | None = None
    #: Did a rendered capture record what this page hides, at each width it
    #: took a record at (_hiding_recorded; model.HIDDEN_VIEW)?
    _recorded: dict = field(default_factory=dict)
    #: The page's element locators (locator.Locators), built when a finding
    #: first needs one.
    _locators: object | None = None
    #: The rendered capture's axe-core records (checks_rendered.axe_state),
    #: read when a rendered rule first asks.
    _axe: tuple | None = None
    #: The page's <html> and <body> with aria-hidden="true"
    #: (checks_rendered.root_hidden), found when a rendered rule first asks.
    _root_hidden: list | None = None
    #: The element each finding made while the rules read the narrow record
    #: is about (by the finding's id), so engine.merge_views can tell
    #: whether the page changed it after the capture.
    narrow_elements: dict = field(default_factory=dict)

    def locator(self, el) -> list | None:
        """The locator for `el` (locator.py): CSS selectors, one per tree."""
        if self._locators is None:
            from .locator import Locators
            scopes = self.ids.scopes if isinstance(self.ids, IdScopes) else {}
            self._locators = Locators(
                self.soup, scopes, ("template",) if self.reader == "xml"
                else ("template", "noscript"))
        return self._locators.of(el)

    def styles(self) -> PageStyles:
        if self._styles is None:
            # Each <style> applies within its own tree: a shadow root's
            # styles never reach the document, nor the document's a shadow
            # root (OR-5).
            self._styles = PageStyles(self.soup, inert=_inert_content,
                                      scope=lambda el: scope_of(self.ids, el))
        return self._styles

    @property
    def hiding_recorded(self) -> bool:
        """Did the capture record what the page hides, at the width the
        rules read now (model.HIDDEN_VIEW)?"""
        view = HIDDEN_VIEW.get()
        if view not in self._recorded:
            attr = self.provenance_attr or PROVENANCE_ATTR.get()
            root = self.soup.find("html")
            self._recorded[view] = bool(attr) and isinstance(root, Tag) and \
                root.get(view_hidden_attr(attr)) == "recorded"
        return self._recorded[view]

    @classmethod
    def parse(cls, html: str | bytes, path: str = "<inline>",
              provenance_attr: str | None = None,
              reader: str | None = None) -> "PageContext":
        """Read one page. `html` is its text, or a file's bytes, which are
        decoded as Chromium decodes a local file (encoding.sniff).

        `reader` says what the markup is (READERS):

        * "html": a page's own markup (a file, or what a server sent),
          parsed as a browser parses it (html5.parse); the declarative
          shadow roots the parser attaches become <bb-shadow-root>.
        * "dom": a browser's serialization of a live DOM (a rendered
          capture, or a snapshot of one), read with html.parser, which keeps
          the nesting the live page had.
        * "xml": an XML document (a local .xhtml file, a page served as
          application/xhtml+xml), which a browser parses as XML: names keep
          their case, `<div/>` closes itself, no implied elements, no
          declarative shadow root (xhtml.parse). One that is not
          well-formed, or not XHTML, is not evaluated.

        By default: "dom" when `provenance_attr` is given (a re-run of an
        instrumented capture's snapshot, whatever its name); "xml" for a
        local .xhtml, .xht or .xhtm file; "html" otherwise.

        A page whose elements sit so deep that the rules' walks up the tree
        would take hours is not evaluated (too_deep): html5.parse caps the
        depth at 512 as Chromium does, but an XML document or a captured DOM
        has no such cap.
        """
        if reader is None:
            reader = ("dom" if provenance_attr is not None else
                      "xml" if _xml_path(path) else "html")
        if reader not in READERS:
            raise ValueError(f"reader must be one of {READERS}, not {reader!r}")
        if isinstance(html, (bytes, bytearray)):
            # Bytes are a file read from disk, where Chromium also detects
            # UTF-8 (fetch.decode_html decodes what a server sent).
            html = encoding.sniff(bytes(html), local_file=True,
                                  xml=reader == "xml").text
        if reader == "html":
            soup = html5.parse(html)
            # Declarative roots nest without the parser's depth cap, so the
            # depth budget is checked before anything walks them (PR2-2).
            too_deep(soup)
            # The templates the parser attached as shadow roots (html5).
            _materialize_shadow_roots(
                soup, lambda t: t.__dict__.get(_DECLARATIVE) is True)
        elif reader == "xml":
            soup = xhtml.parse(html)
        else:
            # A browser keeps the first of two attributes with the same name
            # (`<img alt="" alt="Logo">` has an empty alt); html.parser's
            # default keeps the last. BeautifulSoup warns that the capture
            # of an XHTML page looks like XML: html.parser is the right
            # reader for any serialized DOM, so the warning is silenced.
            import warnings
            from bs4 import XMLParsedAsHTMLWarning
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
                soup = html5.BudgetSoup(html, "html.parser",
                                        on_duplicate_attribute="ignore")
            if reader == "dom" and provenance_attr:
                # The wrappers and slotted nodes the capture made: told
                # apart from page markup by the capture's secret stamp.
                _mark_capture(soup, provenance_attr)
        too_deep(soup)
        ids = IdScopes(soup, _tree_scopes(soup))
        counts = {i: n for (key, i), n in ids.counts.items() if key == 0}
        return cls(path=path, soup=soup, ids=ids, id_counts=counts,
                   provenance_attr=provenance_attr, reader=reader)


#: Attribute name used by the rendered fetch in builds before per-capture
#: attribute names; kept for reference only. Pages can write it themselves,
#: so it is never trusted on its own.
ORIGIN_ATTR = "data-bb-origin"

#: PROVENANCE_ATTR (model.py) is the provenance attribute to honor while
#: run_page evaluates one page; None for files and server HTML. It is
#: defined beside the data model so accname reads the capture's records too.


def _origin_of(el: Tag | None) -> tuple[str, str]:
    """Nearest ancestor attribution written by the harness's rendered fetch.

    Unattributed ("") on local-file and server-HTML runs, and whenever no
    trusted provenance attribute is set; those findings are scored, because
    a gap in provenance must never quietly shrink a customer's score.
    """
    attr = PROVENANCE_ATTR.get()
    if not attr:
        return "", ""
    node = el
    while isinstance(node, Tag):
        v = node.get(attr)
        if v:
            v = v.strip()
            if v.startswith("third-party:"):
                return "third-party", v.split(":", 1)[1]
            if v.startswith("cross-origin:"):
                # Cross-origin code that is not a known vendor: usually the
                # site's own CDN or a library it loads. Scored.
                return "cross-origin", v.split(":", 1)[1]
            return v, ""
        node = node.parent
    return "", ""


def _without_capture_attrs(markup: str) -> str:
    """The page's markup without the records a rendered capture wrote into
    it (provenance, and the derived muted, hidden, slotted and axe-core
    attributes, all named from the capture's secret: the name, or the name
    and a suffix). They are the harness's, not the page's, so a snippet
    leaves them out. A file run trusts no such attribute and strips
    nothing: there, every attribute is the page's own."""
    attr = PROVENANCE_ATTR.get()
    if not attr:
        return markup
    return re.sub(r"\s" + re.escape(attr) + r"""(?:-[a-z]+)*(?:="[^"]*"|='[^']*')?(?=[\s/>])""",
                  "", markup)


def _markup(el: Tag) -> str:
    """`el`'s markup as the page wrote it (OR-19). str() would rewrite a
    <meta charset="koi8-r"> to utf-8, as BeautifulSoup does when it writes
    a document out; and a shadow root the harness wrapped shows as the
    <template shadowrootmode> the page or the capture wrote, not as the
    harness's <bb-shadow-root> (its light DOM stays in the slot that shows
    it)."""
    page = CURRENT_PAGE.get()
    wrappers = []
    if page is not None and isinstance(page.ids, IdScopes) and page.ids.scopes:
        wrappers = [w for w in [el, *el.find_all(_WRAPPER)] if _is_wrapper(w)]
    saved = [(w, w.name, w.attrs) for w in wrappers]
    for w in wrappers:
        w.name = "template"
        w.attrs = {"shadowrootmode": w.attrs.get("data-mode") or "open"}
    try:
        return el.decode(eventual_encoding=None)
    finally:
        for w, name, attrs in saved:
            w.name, w.attrs = name, attrs


#: Elements whose identity is their own tag alone (element_identity): their
#: text and descendants are the whole page's, which change with it.
_DOCUMENT_ELEMENTS = frozenset({"html", "head", "body"})
#: How much of an element's text its identity reads.
_IDENTITY_TEXT = 200
#: How many of an element's descendant elements its identity reads.
_IDENTITY_INSIDE = 20


def _volatile(el: Tag, name: str) -> bool:
    """An attribute a page changes on every request by design, which an
    element's identity leaves out (R3D-5): `nonce` (a browser also hides
    its value from the DOM a capture serializes), and the value of an
    <input type=hidden> (CSRF tokens, ASP.NET view state)."""
    if name == "nonce":
        return True
    return (name == "value" and str(el.name or "").lower() == "input"
            and str(el.get("type") or "").strip().lower() == "hidden")


def _tag_identity(el: Tag, capture) -> list:
    """`el` as [name, [[attribute, value], ...]], the same whichever reader
    read the page: names lowercased (an HTML parser writes SVG's `viewBox`,
    a browser's serialization read back with html.parser `viewbox`),
    attributes sorted by name (a capture's serialization does not keep the
    page's order), each value with its whitespace collapsed (a class list
    reads "icon big"), and the capture's own records and the attributes
    _volatile names left out, by name (`capture` matches the records; None
    on a file run, where every attribute is the page's). Values stay
    values, so no attribute can pass for two (R3C-1, R3C-2, R3C-7). A
    shadow-root wrapper the harness made reads as the `<template
    shadowrootmode>` it was, its mode lowercased as a browser writes it."""
    if _is_wrapper(el):
        return ["template", [["shadowrootmode",
                              str(el.attrs.get("data-mode") or "open")
                              .lower()]]]
    attrs = []
    for name, value in el.attrs.items():
        name = str(name).lower()
        if (capture is not None and capture.fullmatch(name)) \
                or _volatile(el, name):
            continue
        if isinstance(value, (list, tuple)):
            value = " ".join(str(v) for v in value)
        attrs.append([name, " ".join(str(value).split())])
    attrs.sort()
    return [str(el.name or "").lower(), attrs]


def _identity_walk(el: Tag):
    """`el`'s descendants in document order, as its identity reads them:
    elements, and the strings el.get_text() reads (inside most elements,
    not script, style or template text, nor comments). What a <noscript>
    holds is left out: an HTML parser with scripting on reads it as text,
    which a browser's serialization writes out unescaped and html.parser
    then reads as elements, so the two readers would disagree (R3D-1)."""
    types = el.interesting_string_types
    if types is None:
        types = Tag.MAIN_CONTENT_STRING_TYPES
    if isinstance(types, type):
        types = (types,)
    stack = list(reversed(el.contents))
    while stack:
        node = stack.pop()
        if isinstance(node, Tag):
            yield node
            if str(node.name or "").lower() != "noscript":
                stack.extend(reversed(node.contents))
        elif type(node) in types:
            yield node


def element_identity(el: Tag | None) -> str:
    """What a finding about `el` is about, the same on any page and in any
    run while the element is (Finding.about): the first 32 hex digits of the
    SHA-256 of the JSON array [tag, text, inside], written with ASCII
    escapes and no spaces, where `tag` is the element as _tag_identity
    gives it, `text` the first 200 characters of its text (its text nodes,
    joined by a space, white space collapsed), and `inside` the `tag` of
    each of its first 20 descendant elements, in document order (three
    icon buttons that differ only in their <svg> are three elements), both
    as _identity_walk reads them. For <html>, <head> and <body>, whose text
    and descendants are the whole page's, `text` is "" and `inside` [].
    "" for no element. docs/REPORT.md documents this construction."""
    import hashlib
    import json
    if not isinstance(el, Tag):
        return ""
    attr = PROVENANCE_ATTR.get()
    capture = (re.compile(re.escape(attr.lower()) + r"(?:-[a-z]+)*")
               if attr else None)
    # In a URL run, the run's secrets and its --http-user password are
    # replaced by REDACTED in every name, value and text first (the text
    # read far enough past its cut that none is cut in two): a hash of
    # them as they were would let a reader of the report test a guess
    # offline (R5R).
    secrets = has_run_secrets()
    reach = _IDENTITY_TEXT + (secret_reach() if secrets else 0)
    text, inside = "", []
    if str(el.name or "").lower() not in _DOCUMENT_ELEMENTS:
        words, size = [], 0
        for node in _identity_walk(el):
            if isinstance(node, Tag):
                if len(inside) < _IDENTITY_INSIDE:
                    inside.append(_tag_identity(node, capture))
            elif size <= reach:
                piece = node.split()
                words.extend(piece)
                size += sum(len(w) + 1 for w in piece)
            if size > reach and len(inside) >= _IDENTITY_INSIDE:
                break           # nothing further can change either part
        text = " ".join(words)
        if secrets:
            text = scrub_for_hash(text)
        text = text[:_IDENTITY_TEXT]
    tag = _tag_identity(el, capture)
    if secrets:
        tag, inside = _for_hash(tag), _for_hash(inside)
    data = json.dumps([tag, text, inside], ensure_ascii=True,
                      separators=(",", ":"))
    return hashlib.sha256(data.encode("ascii")).hexdigest()[:32]


def _for_hash(item):
    """`item` (element_identity's parts) with redact.scrub_for_hash applied
    to every string in it."""
    if isinstance(item, str):
        return scrub_for_hash(item)
    return [_for_hash(i) for i in item]


_WHITE_RUN = re.compile(r"\s{2,}")


def _squeezed(markup: str) -> str:
    """`markup` with each run of white space one character: a tab, where
    the run is tabs and line breaks only (a browser ignores those in a URL,
    and so does redact_markup), else a space."""
    return _WHITE_RUN.sub(lambda m: "\t" if not m.group().strip("\t\n\r")
                          else " ", markup)


#: How much of an element's markup a snippet's URL redaction reads: the
#: 180 characters a snippet keeps come from its start.
_SNIPPET_READ = 20_000


def _f(rule_id: str, verdict: str, impact: str, msg: str, el: Tag | None = None,
       limit: int | None = None) -> Finding:
    """A finding. `limit`: the message's length at most, cut only after
    the run's secrets are replaced in it and its URLs redacted (axe-core's
    texts: R5L-2)."""
    line = getattr(el, "sourceline", None) if el is not None else None
    snippet = ""
    if el is not None:
        snippet = _without_capture_attrs(_markup(el))
        # The URLs in it as a recorded URL has them: a page's markup can
        # hold a presigned address or a session token, and reports and
        # bundles quote the snippet (R5B-5). On the markup as written, so
        # a tab or a line break in a URL is read as a browser reads it
        # (R5E-1). Runs of white space are one character first (R5H-1).
        # The run's secrets are replaced in the whole markup, before any
        # cut: redacting the URLs before the cut shortens what comes before
        # it, which would bring a secret's cut-off rest into the 180
        # characters kept (R5J-1).
        squeezed = _squeezed(snippet)
        # One that holds the run's password anywhere is withheld whole: a
        # word left around where it was replaced could give it away
        # (R5H-6), and which characters are kept is known only once the
        # URLs before them are redacted (R5J-1).
        if holds_password(squeezed):
            snippet = REDACTED
        else:
            kept = scrub_secrets(squeezed)
            if len(kept) > _SNIPPET_READ:
                # Cut where a tag starts, so no URL or value is cut short
                # (R5E-3, R5L-6): before the limit, or after the first tag
                # where that alone is longer.
                at = kept.rfind("<", 0, _SNIPPET_READ)
                if at <= 0:
                    at = kept.find("<", _SNIPPET_READ)
                kept = kept[:at] if at > 0 else kept
            snippet = " ".join(redact_markup(kept).split())[:180]
    # A message that quotes the element's markup holds the password as
    # the markup did, white space perhaps made one space (R5N-2), which
    # holds_password reads; one that does not quote it keeps its words
    # (R5P-1). Read before any cut (`limit`).
    msg = WITHHELD_MESSAGE if holds_password(msg) else redact_markup(msg)
    if limit:
        msg = " ".join(msg.split())
        if len(msg) > limit:
            msg = msg[:limit - 1] + "…"
    origin, detail = _origin_of(el)
    page = CURRENT_PAGE.get()
    selector = (page.locator(el) if el is not None and page is not None
                and hasattr(page, "locator") else None)
    if selector and any(holds_password(step) for step in selector):
        selector = [REDACTED]
    f = Finding(rule_id=rule_id, verdict=verdict, impact=impact,
                message=msg, line=line, snippet=snippet,
                origin=origin, origin_detail=detail, selector=selector,
                about=element_identity(el))
    if HIDDEN_VIEW.get() == "narrow" and isinstance(page, PageContext):
        page.narrow_elements[id(f)] = el
    return f


_LANDMARK_BOUNDARY = {"html", "body", "header", "nav", "main", "footer",
                      "aside", "section", "form"}


def _author_shows(node: Tag, conditional: bool = True) -> bool:
    """Does the page set a display value on `node` that beats the browser's
    own display:none: its style attribute, or (a file run) a rule in its
    own <style> elements, as the cascade orders them (a rule's !important
    beats the attribute: R5K-5)? `conditional`: whether a show under a
    condition the run cannot settle counts. A rendered run asks the capture
    instead."""
    page = CURRENT_PAGE.get()
    return cascade_decides(page.styles() if page is not None else None,
                           node, "display", conditional) is True


def _set_by_attribute(decls: dict, prop: str) -> bool:
    """Does the style attribute set `prop` (to any value a browser takes,
    CSS-wide keywords included: style.cascade_decides orders them)?"""
    return decls.get(prop) is not None


def _display_none(el: Tag, tree: bool = False) -> bool:
    """True when the markup hides the element and nothing in the page shows
    it again: it or an ancestor carries `inert`, sits in <template>/
    <noscript>, is hidden by the browser's own stylesheet (_ua_hidden) with
    no author display overriding it, is a closed <details>'s content other
    than its first summary, or has display:none in its style attribute; an
    ancestor skips what it holds (hidden="until-found" or
    content-visibility:hidden where that applies: style.skips_content); or
    the nearest visibility set, its own or an ancestor's, is hidden or
    collapse by a style attribute, or a MathML <mphantom>'s by the
    browser's own stylesheet (style.ua_invisible: R6I-5) (a descendant's
    visibility:visible, by its style attribute or a rule, shows it again;
    inherit, unset and revert leave it to the parent). A style attribute's
    display and visibility stand as the cascade lets them: a rule of the
    page's own <style> with !important beats it (R5K-5); a rule alone
    hides nothing here.

    In a rendered run that recorded what the page hides, markup decides
    only together with that record: a stylesheet can show what markup
    hides (`<div hidden class="d-block">`, an open popover), and the
    capture saw which. Stylesheet-driven hiding itself is the record's
    (_capture_hidden), read where it decides the verdict. What a drawing
    never renders (_svg_unrendered), which no stylesheet shows, is hidden
    in either run (R6E-3, R6F-5).

    `tree`: hidden from Chromium 141's accessibility tree, for the rules
    about names (_out_of_tree). There what a drawing boxes but never paints
    is not hidden: what a <defs>, a clip path, a mask, a pattern or a
    marker holds, and a <g> or a <marker> with display:none (measured:
    R6G-3, R6H-1); a <foreignObject>, and what it holds, is hidden unless
    rendered (R6I-2). A drawing's element whose own conditions fail is
    hidden (_svg_fails): as markup shows it, and in a rendered run as the
    capture recorded it (a language, which markup cannot tell: R6I-1; a
    script's lowercase requiredextensions, no condition: R6M-6)."""
    page = CURRENT_PAGE.get()
    recorded = page is not None and page.hiding_recorded
    styles = page.styles() if page is not None else None
    child, node = el, el
    visibility = None
    hidden = False
    while isinstance(node, Tag):
        # Content of a drawing's HTML part, and its <foreignObject>, is in
        # the tree only where it is rendered: from there up, what renders
        # decides (R6I-2).
        tree = tree and namespace_of(node) == "svg" and (
            node.name or "").lower() != "foreignobject"
        if node.has_attr("inert") or node.name in ("template", "noscript"):
            return True          # not rendering: inert, or no live content
        if namespace_of(node) == "svg" and _svg_fails(node):
            return True          # its own conditions fail (R6I-1, R6M-6)
        decls = _inline_style(node.get("style"))
        if _ua_hidden(node) and (recorded or not _author_shows(node)):
            hidden = True
            break
        if node is not el and skips_content(node):
            hidden = True   # hidden="until-found", content-visibility:hidden
            break
        if (node.name == "details" and not node.has_attr("open")
                and node is not el
                and child is not _first_summary(node)):
            hidden = True
            break
        if _svg_unrendered(node, tree):
            # What a drawing never renders, which no stylesheet shows: so
            # in a rendered run too (R6E-3, R6F-5).
            return True
        if (_set_by_attribute(decls, "display") and cascade_decides(
                styles, node, "display") is False) and not (
                    tree and (node.name or "").lower()
                    in _SVG_BOXED_WHEN_NONE):
            hidden = True
            break
        if visibility is None:
            # inherit, unset or revert takes the parent's: the walk goes on
            # (None), as GSAP's autoAlpha writes it (R5O-1). A show ends it,
            # a rule's too (R5Q-4); a hide only where the style attribute
            # sets visibility (a rule alone hides nothing here).
            decided = cascade_decides(styles, node, "visibility",
                                      later_shows=True)
            if decided is True:
                visibility = "visible"
            elif decided is False and (_set_by_attribute(
                    decls, "visibility") or _ua_invisible(node)):
                visibility = "hidden"
        child, node = node, node.parent
    hidden = hidden or visibility in ("hidden", "collapse")
    if recorded:
        return hidden and _capture_hidden(el)
    return hidden


#: A drawing's elements that render what they hold (measured in Chromium
#: 141: R6E-3, R6F-5). The others render none of it: <defs>, <symbol>, a
#: clip path, a mask, a pattern, a marker, a gradient, a filter, a shape,
#: an <image>, a <use>, <metadata>, a <title>, an element Chromium does not
#: know; a <text>, a <tspan> and a <textPath> render only their text parts
#: and links; a <switch> renders one.
_SVG_RENDERS_CONTENT = frozenset(("svg", "g", "a", "switch",
                                  "foreignobject"))
_SVG_TEXT_PARTS = frozenset(("text", "tspan", "textpath"))
_SVG_IN_TEXT = frozenset(("tspan", "textpath", "a"))
#: A drawing's elements Blink boxes but never paints, with what they hold:
#: what they hold is in Chromium 141's accessibility tree (a link there is
#: a link, which takes no focus), unlike what a <symbol>, a gradient, a
#: filter, a shape or a <use> holds (measured: R6G-3, R6H-1).
_SVG_HIDDEN_BOXES = frozenset(("defs", "clippath", "mask", "pattern",
                               "marker"))
#: Those Blink boxes so where their own display is none too, what they
#: hold in the accessibility tree still (measured): a <g>, a <marker>.
_SVG_BOXED_WHEN_NONE = frozenset(("g", "marker"))
#: The extensions Chromium 141 has (requiredExtensions): HTML's and
#: MathML's namespaces, written exactly so (measured).
_SVG_EXTENSIONS = frozenset(("http://www.w3.org/1999/xhtml",
                             "http://www.w3.org/1998/Math/MathML"))
#: A drawing's elements whose conditions (systemLanguage,
#: requiredExtensions) Chromium 141 reads (measured, R6G-8). Any other
#: passes whatever it says: a <title>, a <desc>, a <symbol>, a gradient, a
#: <clipPath>, a <marker>, a filter, an element Chromium does not know.
_SVG_TESTS = frozenset(("a", "animate", "animatemotion", "animatetransform",
                        "circle", "defs", "ellipse", "foreignobject", "g",
                        "image", "line", "mask", "path", "pattern",
                        "polygon", "polyline", "rect", "set", "svg",
                        "switch", "text", "textpath", "tspan", "use"))
#: White space as Chromium splits a list of extensions by: ASCII's.
_ASCII_SPACE = " \t\n\f\r"


def _extensions_pass(value) -> bool:
    """Does Chromium 141 have every extension a requiredExtensions value
    names (_SVG_EXTENSIONS): not "", no white space before the first, the
    rest split at ASCII white space alone, white space after the last
    passed over (measured: R6G-7, R6K-2)?"""
    value = value if isinstance(value, str) else " ".join(value)
    if value == "" or value[0] in _ASCII_SPACE:
        return False
    return set(re.split("[" + _ASCII_SPACE + "]+",
                        value.rstrip(_ASCII_SPACE))) <= _SVG_EXTENSIONS


def _svg_attr(el: Tag, name: str):
    """`el`'s attribute `name`, a drawing's (requiredExtensions,
    systemLanguage), as the page's reader keeps its name: case and all in
    an XML document, where `requiredextensions` is none (R6K-11), in any
    case elsewhere (an HTML parser writes it so, a capture's reader in
    lower case); None where it has none."""
    page = CURRENT_PAGE.get()
    if getattr(page, "reader", "html") == "xml":
        return el.get(name)
    low = name.lower()
    return next((v for k, v in el.attrs.items() if k.lower() == low), None)


def _svg_conditional(el: Tag) -> bool:
    """Does `el`, a drawing's element, carry a condition Chromium 141 reads
    on it (systemLanguage, requiredExtensions: _svg_attr; _SVG_TESTS)?"""
    return (el.name or "").lower() in _SVG_TESTS and (
        _svg_attr(el, "systemLanguage") is not None
        or _svg_attr(el, "requiredExtensions") is not None)


def _svg_fails(el: Tag) -> bool:
    """Do `el`'s own conditions fail in Chromium 141, so that it renders
    nothing, in a <switch> or not? In a rendered run that recorded what
    the page hides, as the capture read them on the live element
    (_recorded_fails: a systemLanguage too, R6I-1); elsewhere as markup
    shows them: a requiredExtensions naming an extension Chromium does not
    have, or empty, or with white space before it (_extensions_pass;
    measured, R6I-1), where a systemLanguage, which the reader's languages
    decide, is not read."""
    if (el.name or "").lower() not in _SVG_TESTS:
        return False
    recorded = _recorded_fails(el)
    if recorded is not None:
        return recorded
    value = _svg_attr(el, "requiredExtensions")
    return value is not None and not _extensions_pass(value)


def _svg_passes(el: Tag) -> bool:
    """Do `el`'s conditions surely pass in Chromium 141: those of an
    element that has none (_SVG_TESTS) do; in a rendered run that recorded
    what the page hides, those the capture did not read as failing
    (_recorded_fails); elsewhere, no systemLanguage (which language passes
    markup cannot tell), and no requiredExtensions or one naming only
    extensions Chromium has (_extensions_pass: R6G-7, R6K-2;
    requiredFeatures is no condition)?"""
    if (el.name or "").lower() not in _SVG_TESTS:
        return True
    recorded = _recorded_fails(el)
    if recorded is not None:
        return not recorded
    if _svg_attr(el, "systemLanguage") is not None:
        return False
    value = _svg_attr(el, "requiredExtensions")
    return value is None or _extensions_pass(value)


def _recorded_fails(el: Tag) -> bool | None:
    """In a rendered run that recorded what the page hides, do `el`'s own
    conditions fail as the capture read them on the live element: is it
    marked "display", and does it carry a condition (_svg_conditional)?
    None in other runs. A capture's markup keeps no attribute name's case,
    so it cannot tell requiredExtensions from a lowercase
    requiredextensions a script set, which is no condition (R6M-6)."""
    page = CURRENT_PAGE.get()
    attr = PROVENANCE_ATTR.get()
    if page is None or not page.hiding_recorded or not attr:
        return None
    return (el.get(view_hidden_attr(attr)) == "display"
            and _svg_conditional(el))


def _svg_unrendered(node: Tag, tree: bool = False) -> bool:
    """Does markup show that `node`, held by a drawing's element, is never
    rendered (_SVG_RENDERS_CONTENT): held by one that renders none of what
    it holds; a <text>'s that is no text part of one; a text part outside a
    <text> (a <tspan> in a <g>); an <a> held by an <a>; or a <switch>'s
    after one it renders? An <a> holds what the element that holds it
    (the nearest that is no <a>) may hold: a text part in a <text>, and in
    a <switch> its first element alone. A <switch> renders the first of
    its elements whose conditions pass (_svg_passes); an element after ones
    whose language decides is read as rendered (measured in Chromium 141:
    R6G-8). `tree`: is `node` out of Chromium 141's accessibility tree,
    where what a <defs>, a clip path, a mask, a pattern or a marker holds
    is not (_SVG_HIDDEN_BOXES: R6G-3, R6H-1)?"""
    parent = node.parent
    if not isinstance(parent, Tag) or namespace_of(parent) != "svg":
        return False
    own = (node.name or "").lower() if namespace_of(node) == "svg" else ""
    if own == "a" and (parent.name or "").lower() == "a":
        return True             # Blink renders no <a> in an <a>
    holder = parent
    while (holder.name or "").lower() == "a" and isinstance(
            holder.parent, Tag) and namespace_of(holder.parent) == "svg":
        holder = holder.parent
    name = (holder.name or "").lower()
    if name in _SVG_TEXT_PARTS:
        return own != "" and own not in _SVG_IN_TEXT
    if own in ("tspan", "textpath"):
        return True             # a text part outside a <text>
    if name not in _SVG_RENDERS_CONTENT and not (
            tree and name in _SVG_HIDDEN_BOXES):
        return True
    if name == "switch":
        return any(isinstance(s, Tag) and namespace_of(s) == "svg"
                   and _svg_passes(s) for s in node.previous_siblings)
    return False


def _inert_content(el: Tag) -> bool:
    """Inside a <template> or a <noscript>: not in the document a browser
    that runs scripts builds. (A shadow root is a <bb-shadow-root>, not a
    template, by the time the rules run.)"""
    return any(isinstance(p, Tag) and p.name in ("template", "noscript")
               for p in el.parents)


def _excluded_from_tree(el: Tag) -> bool:
    """ACT applicability: rules about names apply to elements *included in
    the accessibility tree*. aria-hidden="true" on the element or any
    ancestor excludes it, as does not being rendered. Name rules skip such
    elements — a closed drawer's links are evaluated when the drawer is
    open, which is the interaction layer's job, not a static false fail."""
    node = el
    while isinstance(node, Tag):
        if aria_hidden(node):
            return True
        if _select_button(node):
            return True
        node = node.parent
    return _display_none(el)


def _out_of_tree(el: Tag) -> bool:
    """_excluded_from_tree, as Chromium 141's accessibility tree has it,
    for the rules about names: what a drawing boxes but never paints is in
    the tree (what a <defs>, a clip path, a mask, a pattern or a marker
    holds, and what a <g> or a <marker> with display:none holds), a link
    there a link that takes no focus (measured: R6G-3, R6H-1)."""
    node = el
    while isinstance(node, Tag):
        if aria_hidden(node) or _select_button(node):
            return True
        node = node.parent
    return _display_none(el, tree=True)


def _select_button(node: Tag) -> bool:
    """Is `node` a <select>'s first child element, a <button>? HTML makes it
    inert: a customizable select draws it in place of its own box, and the
    select is the control (its button and what the button holds are in no
    accessibility tree). A browser keeps it where it parses `<select>
    <button>`; the harness's file reader drops it, as browsers did before
    (R3D: a rendered run alone failed it for bb-button-name)."""
    parent = node.parent
    if node.name != "button" or not isinstance(parent, Tag) or \
            parent.name != "select":
        return False
    return next((c for c in parent.children if isinstance(c, Tag)),
                None) is node


def _is_focusable(el: Tag) -> bool:
    # The element's own markup first: it is cheap, and most elements are
    # not focusable, so their ancestors need not be walked (P2-12).
    return _focusable_here(el) and not _display_none(el)


#: What a rendered capture records under model.hidden_attr, where the
#: page as rendered changes what it shows: "display" where rendering stops,
#: "visibility" where content turns invisible ("visibility-skips" where it
#: skips what it holds too), "shown" where an element inside invisible
#: content is visible again ("shown-skips" where it skips what it holds
#: too), "skips" on one that skips what it holds, "unrendered" and
#: "unboxed" where rendering stops at a part of a drawing or of MathML
#: that names still read (R6C-3), "unrendered-visibility" and
#: "unboxed-visibility" where such a part is invisible too, or an element
#: inside one turns invisible (R6E-4, R6E-5). "recorded" marks the root
#: element of a capture that recorded hiding at all. Those that hide:
_CAPTURE_HIDDEN_VALUES = ("display", "visibility", "visibility-skips",
                          "unrendered", "unboxed", "unrendered-visibility",
                          "unboxed-visibility")


def _capture_hiding(el: Tag) -> Tag | None:
    """The element whose capture record hides `el` (it or an ancestor), or
    None: content made visible again inside invisible content ("shown") is
    not hidden by the invisible content, but it is by what is not rendered
    (inside a drawing's <defs> or a <g> with display:none, invisible or
    not, which the capture marks "unrendered" or "unrendered-visibility":
    R6C-3, R6E-5). Read only under the capture's own secret name, so never
    on files or server HTML, where markup could say anything about
    itself."""
    attr = PROVENANCE_ATTR.get()
    page = CURRENT_PAGE.get()
    if not attr or (page is not None and not page.hiding_recorded):
        return None
    name = view_hidden_attr(attr)
    node, shown = el, False
    while isinstance(node, Tag):
        mark = node.get(name)
        if mark in ("shown", "shown-skips"):
            shown = True
        elif mark in _CAPTURE_HIDDEN_VALUES and not (
                shown and mark in ("visibility", "visibility-skips")):
            return node
        node = node.parent
    return None


def _capture_hidden(el: Tag) -> bool:
    """A rendered capture recorded `el` as hidden by the page as rendered,
    stylesheets included (model.hidden_attr)."""
    return _capture_hiding(el) is not None


def _not_shown(el: Tag) -> bool:
    """Hidden on the page as it is shown, as far as the run can tell: in a
    rendered run that recorded what the page hides, by that record, at
    the width the rules read now (_capture_hidden); elsewhere by its
    markup or a rule of the page's own <style>, on it or an ancestor:
    anything that stops rendering, or visibility hidden where the nearest
    element that sets visibility, by its style attribute or a rule, sets
    it so (R5I-5), a MathML <mphantom> where none does
    (style.ua_invisible). Where it could be either, hidden: a show under a
    condition the run cannot settle (@media with features) does not count,
    nor for what markup hides (the hidden attribute, a popover, a closed
    <dialog>: R5K-9). What a drawing never renders is not shown in either
    run (_svg_unrendered). For what a control a person may not see stands
    in for (SCR28, R5G-3)."""
    page = CURRENT_PAGE.get()
    if page is not None and page.hiding_recorded and PROVENANCE_ATTR.get():
        return _capture_hidden(el) or any(
            _svg_unrendered(n) or (namespace_of(n) == "svg"
                                   and _svg_fails(n))
            for n in (el, *el.parents) if isinstance(n, Tag))
    styles = page.styles() if page is not None else None
    child, node = el, el
    visible = None
    while isinstance(node, Tag) and node.name != "[document]":
        if node.has_attr("inert") or node.name in ("template", "noscript"):
            return True
        if _ua_hidden(node) and not _author_shows(node, conditional=False):
            return True
        if node is not el and skips_content(node):
            return True
        if (node.name == "details" and not node.has_attr("open")
                and node is not el
                and child is not _first_summary(node)):
            return True
        if _svg_unrendered(node) or (namespace_of(node) == "svg"
                                     and _svg_fails(node)):
            return True
        # The style attribute and the page's rules together, as the
        # cascade orders them (style.PageStyles.decides).
        if cascade_decides(styles, node, "display", False) is False:
            return True
        if visible is None:
            visible = cascade_decides(styles, node, "visibility", False)
        child, node = node, node.parent
    return visible is False


def _hiding_recorded(page: "PageContext") -> bool:
    """Did the capture record what the page's stylesheets hide? It marks
    its root element when it did. Files, server HTML, a capture whose
    instrumentation failed and snapshots from builds before the record
    existed carry no mark: there, what stylesheets hide is unknown."""
    return page.hiding_recorded


#: Class names a framework's own stylesheet hides until a script opens the
#: element: Bootstrap's modal, offcanvas, collapse, dropdown menu, d-none and
#: invisible; Tailwind's hidden and invisible (Flowbite's modals);
#: Foundation's reveal; Bulma's modal and is-hidden. Each is hidden only
#: without an "open" class beside it, and only when no responsive or
#: state class shows it (Tailwind `md:block`, `dark:md:!flex`,
#: `min-[900px]:grid`, `@md:flex`; Bootstrap `d-md-flex`).
_CLOSED_CLASSES = frozenset({"modal", "offcanvas", "collapse", "dropdown-menu",
                             "d-none", "invisible", "hidden", "reveal",
                             "is-hidden"})
_OPEN_CLASSES = frozenset({"show", "showing", "in", "open", "is-open",
                           "active", "is-active"})
#: One Tailwind variant: a name (`md`, `max-lg`, `group-hover`), an
#: arbitrary value (`min-[900px]`, `[&.open]`), a container query (`@md`,
#: `@[17.5rem]`) or a named group (`group-hover/item`), then a colon.
_TW_VARIANT = r"(?:@?[a-z0-9-]*(?:\[[^\]]*\])?(?:/[\w-]+)?:)"
_SHOWN_AT_SOME_WIDTH_RE = re.compile(
    rf"^{_TW_VARIANT}+!?(?:block|inline|inline-block|flex|inline-flex|grid|"
    r"inline-grid|table|table-row|table-cell|contents|flow-root|list-item|"
    r"visible)!?$"
    r"|^d-(?:sm|md|lg|xl|xxl)-(?!none$)[a-z-]+$")


def _class_names(el: Tag) -> set:
    """`el`'s classes: the readers split the attribute at ASCII white
    space alone, as HTML splits it (html5.AsciiTokenLists), and so is a
    string here (R6X-2, R6Z-4)."""
    classes = el.get("class") or []
    return set(html5.HTML_TOKENS.findall(classes)
               if isinstance(classes, str) else classes)


def _closed_by_class(container: Tag) -> set:
    """The classes that say a framework stylesheet keeps the aria-hidden
    `container` itself hidden until a script opens it, or an empty set. The
    frameworks that write aria-hidden on a closed modal (Bootstrap,
    Flowbite, Foundation) remove it as they open the same element, so the
    two go together there; a closing class on an ancestor or descendant
    says nothing about when aria-hidden is removed. A heuristic for runs
    that cannot read the stylesheets: it turns a FAIL into a review, never
    a pass. An inline style that shows the element (Bootstrap writes
    `display: block` on an open modal) wins over the class."""
    names = _class_names(container)
    closed = names & _CLOSED_CLASSES
    if "navbar-collapse" in names:
        closed = closed - {"collapse"}   # shown at the navbar's breakpoint
    if (not closed or names & _OPEN_CLASSES
            or any(_SHOWN_AT_SOME_WIDTH_RE.match(c) for c in names)):
        return set()
    decls = _inline_style(container.get("style"))
    if (decls.get("display") not in (None, "none")
            or decls.get("visibility") == "visible"):
        return set()
    return closed


_HTML_INT_RE = re.compile(r"[\t\n\f\r ]*([+-]?)([0-9]+)")
_INT32 = 2 ** 31


def _html_int(value) -> int | None:
    """`value` as HTML's rules for parsing integers read it: leading ASCII
    whitespace skipped, an optional sign, ASCII digits up to the first
    other character (`0.5` is 0). None when there are no digits (`""`,
    `abc`) or the number does not fit in 32 bits: Chromium 141 then treats
    the attribute as absent (`tabindex="2147483648"` leaves a span
    unfocusable). Never raises, however long the digit run: Python refuses
    int() on more than 4,300 digits, and a page could use that to make a
    rule raise (OR-3)."""
    m = _HTML_INT_RE.match(value) if isinstance(value, str) else None
    if not m:
        return None
    digits = m.group(2).lstrip("0") or "0"
    if len(digits) > 10:
        return None
    n = int(m.group(1) + digits)
    return n if -_INT32 <= n < _INT32 else None


def _tabindex(el: Tag) -> int | None:
    """tabindex as HTML's rules for parsing integers read it (_html_int):
    None when it has no digits or is out of range, as if the attribute
    were absent."""
    return _html_int(el.get("tabindex"))


#: Elements `disabled` applies to. On anything else (a link, a div) it is
#: an unknown attribute and the element stays focusable.
_DISABLEABLE = ("button", "input", "select", "textarea", "optgroup", "option",
                "fieldset")
_CONTENTEDITABLE_ON = ("", "true", "plaintext-only")
#: The elements _focusable_here reads as focusable by their name (HTML's).
_FOCUSABLE_NAMES = frozenset(("a", "area", "input", "audio", "video",
                              "button", "select", "textarea", "summary",
                              "iframe"))


def _disabled(el: Tag) -> bool:
    """Disabled as HTML defines it: its own `disabled`, or inside a disabled
    <fieldset> other than in that fieldset's first <legend> (each disabled
    fieldset around it counts). HTML's elements only: a drawing's or
    MathML's <button> is none (R6B-7)."""
    if el.name not in _DISABLEABLE or namespace_of(el) != "html":
        return False
    if el.has_attr("disabled"):
        return True
    for fs in el.parents:
        if isinstance(fs, Tag) and fs.name == "fieldset" and fs.has_attr("disabled"):
            legend = fs.find("legend", recursive=False)
            if not (legend is not None and any(p is legend for p in el.parents)):
                return True     # an outer disabled fieldset still counts
    return False


def _link_href(el: Tag) -> bool:
    """Is the <a> `el` a link: HTML's with an href, a drawing's with an
    href or an xlink:href (as Chromium 141 has it: R6C-9, R6D-2)? MathML's
    is none."""
    ns = namespace_of(el)
    if ns == "html":
        return el.has_attr("href")
    return ns == "svg" and (el.has_attr("href") or el.has_attr("xlink:href"))


def _focusable_here(el: Tag) -> bool:
    """In sequential focus navigation by its own markup, rendering aside (the
    caller has ruled out hidden ancestors): links (a drawing's too, by
    its href or xlink:href: _link_href) and image-map areas with an href,
    form controls that are not disabled,
    media with native controls, editing hosts, summary, iframe, and
    anything with a tabindex of 0 or more. A drawing's or MathML's element
    named as one of HTML's is none of them (R6B-7)."""
    if _disabled(el):
        return False
    ti = _tabindex(el)
    if ti is not None:
        return ti >= 0
    if el.name == "a" and _link_href(el):
        return True
    if el.name not in _FOCUSABLE_NAMES and not el.has_attr("contenteditable"):
        return False
    if namespace_of(el) != "html":
        return False
    if el.name == "area":
        return el.has_attr("href")
    if el.name == "input":
        return (el.get("type") or "").lower() != "hidden"
    if el.name in ("audio", "video"):
        return el.has_attr("controls")
    editable = el.get("contenteditable")
    if isinstance(editable, str) and editable.strip().lower() in _CONTENTEDITABLE_ON:
        return True
    return el.name in ("button", "select", "textarea", "summary", "iframe")


# --------------------------------------------------------------------------
# Tier 1 — the complaint boilerplate
# --------------------------------------------------------------------------

def check_img_alt(page: PageContext) -> RuleResult:
    """1.1.1 — images and image controls must have text alternatives."""
    r = RuleResult("bb-img-alt", applicable=False)
    # HTML's <img>, <input> and <area> only: a drawing's or MathML's element
    # of the same name is no image (R6B-7).
    for img in page.soup.find_all("img"):
        if _excluded_from_tree(img) or namespace_of(img) != "html":
            continue
        r.applicable = True
        if img.has_attr("alt"):
            continue
        roles = (img.get("role") or "").lower().split()
        if "presentation" in roles or "none" in roles:
            continue  # decorative by role (ACT: passes as decorative)
        if static_accname(img, page.soup, page.ids):
            continue  # named via aria-label / aria-labelledby / title
        r.findings.append(_f("bb-img-alt", FAIL, BLOCKER,
                             "Image has no alt attribute and no other accessible "
                             "name. Provide alt text, or alt=\"\" only if purely "
                             "decorative.", img))
    for inp in page.soup.select('input[type="image"]'):
        if _excluded_from_tree(inp) or namespace_of(inp) != "html":
            continue
        r.applicable = True
        if not _norm(inp.get("alt")) and not static_accname(inp, page.soup, page.ids):
            r.findings.append(_f("bb-img-alt", FAIL, BLOCKER,
                                 "Image input has no alt/accessible name.", inp))
    for area in page.soup.select("area[href]"):
        if _excluded_from_tree(area) or namespace_of(area) != "html":
            continue
        r.applicable = True
        if not _norm(area.get("alt")):
            r.findings.append(_f("bb-img-alt", FAIL, SERIOUS,
                                 "Image-map area has no alt text.", area))
    return r


def check_svg_name(page: PageContext) -> RuleResult:
    """1.1.1 — svg[role=img] needs an accessible name."""
    r = RuleResult("bb-svg-name", applicable=False)
    for svg in page.soup.find_all("svg"):
        # role=img, or ARIA 1.3's synonym image, as the first role token a
        # browser knows (role="presentation img" is presentational).
        if _role_of(svg) not in ("img", "image") or _out_of_tree(svg):
            continue
        r.applicable = True
        if not static_accname(svg, page.soup, page.ids):
            r.findings.append(_f("bb-svg-name", FAIL, SERIOUS,
                                 "svg with role=img has no accessible name "
                                 "(add <title>, aria-label, or aria-labelledby).", svg))
    return r


def _named_control_candidate(el: Tag) -> bool:
    return el.name in ("a", "button", "input") or el.has_attr("role")


#: Roles another name rule checks: bb-widget-name (a menu item, a tab),
#: bb-role-img-name (an image), bb-progress-name (a progress bar) and
#: bb-control-label (a checkbox, a switch). A link or button given one of
#: them is that role's, and that rule's, so one unnamed control is one
#: finding (QR-13): ACT rules c487ae and 97a4e1 apply by the element's
#: role.
_OTHER_NAME_ROLES = WIDGET_NAME_ROLES | FORM_FIELD_ROLES


def _link_rule_owns(el: Tag) -> bool:
    """bb-link-name checks what a browser exposes as a link (ACT c487ae):
    <a href> (a drawing's <a xlink:href> too: _link_href), and anything
    with role=link. A link given role=button is a
    button, and bb-button-name checks it; one given a role another name
    rule checks (menuitem, tab, checkbox: _OTHER_NAME_ROLES) is that
    rule's. An image map's <area> is bb-img-alt's."""
    role = _role_of(el)
    if role == "link":
        return el.name != "area"
    if role == "button" or role in _OTHER_NAME_ROLES:
        return False
    return el.name == "a" and _link_href(el)


def _button_rule_owns(el: Tag) -> bool:
    """bb-button-name checks what a browser exposes as a button (ACT
    97a4e1): <button>, button-type inputs, and anything with role=button.
    A button given role=link is bb-link-name's, and one given a role
    another name rule checks (tab, menuitem, switch: _OTHER_NAME_ROLES) is
    that rule's. An image button is bb-img-alt's. A drawing's or MathML's
    <button> or <input> is no button (R6B-7)."""
    html = el.name not in ("button", "input") or namespace_of(el) == "html"
    itype = ((el.get("type") or "").lower()
             if el.name == "input" and html else "")
    if itype == "image":
        return False
    role = _role_of(el)
    if role == "button":
        return True
    if role == "link" or role in _OTHER_NAME_ROLES:
        return False
    return html and (el.name == "button"
                     or itype in ("button", "submit", "reset"))


def check_link_name(page: PageContext) -> RuleResult:
    """2.4.4 / 4.1.2 — 'empty links' from the pled boilerplate. One named
    only by what Chromium 141 does not read is reviewed (_cut_review)."""
    r = RuleResult("bb-link-name", applicable=False)
    for a in page.soup.find_all(_named_control_candidate):
        if not _link_rule_owns(a) or _out_of_tree(a):
            continue  # e.g. the aria-hidden image link of a card (H2 fix)
        r.applicable = True
        maybe: list = []
        if not static_accname(a, page.soup, page.ids, cuts=maybe):
            r.findings.append(_f("bb-link-name", FAIL, BLOCKER,
                                 "Link has no accessible name (empty link).", a))
            continue
        cut = chromium_cut(a, page.soup, page.ids) if maybe else None
        if cut is not None:
            impact, msg = _cut_review("link", a, *cut)
            r.findings.append(_f("bb-link-name", NEEDS_REVIEW, impact, msg,
                                 a))
    return r


def check_button_name(page: PageContext) -> RuleResult:
    """4.1.2 — 'empty buttons' / unlabeled controls. One named only by
    what Chromium 141 does not read is reviewed (_cut_review)."""
    r = RuleResult("bb-button-name", applicable=False)
    for el in page.soup.find_all(_named_control_candidate):
        if not _button_rule_owns(el) or _out_of_tree(el):
            continue
        r.applicable = True
        maybe: list = []
        if not static_accname(el, page.soup, page.ids, cuts=maybe):
            r.findings.append(_f("bb-button-name", FAIL, BLOCKER,
                                 "Button has no accessible name.", el))
            continue
        cut = chromium_cut(el, page.soup, page.ids) if maybe else None
        if cut is not None:
            impact, msg = _cut_review("button", el, *cut)
            r.findings.append(_f("bb-button-name", NEEDS_REVIEW, impact, msg,
                                 el))
    return r


def _cut_review(what: str, el: Tag, kind: str, cut: Tag, axe: bool,
                why: tuple | None = None,
                because: str | None = None) -> tuple[str, str]:
    """The impact and message of the review of a link or a button (`what`,
    `el`) whose only name is what Chromium 141 does not read
    (accname.chromium_cut, L92, L115, R6S-4): the text `cut` holds
    ("content": an <article>, a <figure>, a <math> and the like), its
    title ("title": a <span>, a <div>, an <i> and the like), a <label>
    that names it nothing there and takes the place of the button's own
    name ("label"), or the title of a button input whose value is empty
    ("value": R6U-3). Minor where axe-core 4.12 reads that name, or past
    the label the button's own, or passes the button by a <label> it does
    not see (`axe`), saying other checks usually pass it, but not of what
    a <label> holds, which axe-core reads its own way; moderate where it
    does not, saying why (`why`, accname._axe_why: R6Q-1, R6S-1, R6U-4,
    R6W-1, R6W-2), or as `because` says (a form field's: _field_review).
    Each measured in Chromium 141."""
    holder = _holder(cut)
    held = any(p is el for p in cut.parents)
    an = _an(holder)
    where = f"its {holder}" if held else f"{an} {holder} in its <label>"
    effect = ("in Chrome and Edge it has no accessible name, so screen "
              "readers may announce it without one, and voice control may "
              "not find it by that text.")
    head = ("Named by the accessible-name computation, but not in Chrome or "
            f"Edge (Chromium 141): this {what}")
    unread = ("it reads none of a <slot>, nor of an element that holds "
              "white space, or whose role is none or presentation")
    if kind == "value":
        return MINOR, (
            f"{head}'s only name is its title, and Chrome and Edge read no "
            f"title of a button input whose value attribute is empty. Other "
            f"checks usually pass it; {effect} Fix: give it a value that "
            f"names it, or no value attribute where its default (Submit, "
            f"Reset) names it.")
    if kind == "label":
        others = ("Other checks usually pass it" if axe else
                  f"Nor does axe-core 4.12 read the {what}'s own content "
                  f"into a name, so other checks may fail it too")
        return (MINOR if axe else MODERATE), (
            f"{head} has a <label> that names it nothing there (it is "
            f"empty or hidden, or holds only what they do not read, the "
            f"{what} itself aside), and Chrome and Edge read its <label> in "
            f"place of its own content, value and title. {others}; "
            f"{effect.replace('by that text', 'by its text')} Fix: give the "
            f"<label> the {what}'s name as its text, or remove it.")
    if kind == "title":
        only = (f"the title of {where}, and Chrome and Edge read no title "
                f"of such an element into a name")
        effect = ("in Chrome and Edge it has no accessible name (or only "
                  "an icon font's glyph, where a stylesheet draws one into "
                  "that element), so screen readers may announce it without "
                  "one, and voice control may not find it by that text.")
        fix = (f"Fix: give the {what} an aria-label, or make that text its "
               f"own (visually hidden if need be).")
    else:
        only = (f"text inside {where}, and Chrome and Edge read nothing "
                f"such an element holds")
        fix = (f"Fix: give the {what}, or its <{cut.name}>, an aria-label."
               if _embedded(cut) else
               f"Fix: give the {what} an aria-label, or move its text out "
               f"of that element.")
    if axe:
        # axe-core reads a label's content its own way (measured: it fails
        # a <label> holding an <article>, passes one holding a <figure>).
        others = "Other checks usually pass it; " if held else ""
        return MINOR, (
            f"{head}'s only name is {only}. {others}"
            f"{effect if held else effect[0].upper() + effect[1:]} {fix}")
    reason, node = (why or ("content", cut, "embedded"))[:2]
    that = "That title" if kind == "title" else "That text"
    if reason == "title":
        text = f"Nor does axe-core 4.12 read that title ({unread})"
    elif reason == "embedded" and namespace_of(node) == "math":
        text = (f"{that} is MathML, which axe-core 4.12 does not read into a "
                f"name either")
    elif reason == "embedded" and node is cut:
        text = (f"Nor does axe-core 4.12 read what {an} {holder} holds into "
                f"a name")
    elif reason == "embedded":
        outer = f"<{node.name}>"         # by its tag: what it is matters
        text = (f"{that} is inside {_an(outer)} {outer}, of which axe-core "
                f"4.12 reads only the own name")
    elif why is not None and why[2] == "title":
        text = (f"That text is a title, which axe-core 4.12 does not read "
                f"either ({unread})")
    elif why is not None and why[2] == "both":
        text = ("That text is MathML or embedded content, or a title, which "
                "axe-core 4.12 does not read either")
    else:
        text = ("That text is MathML, or inside an <object>, a <canvas> or "
                "a drawing, which axe-core 4.12 does not read into a name "
                "either")
    if because is not None:
        text = because
    return MODERATE, (
        f"{head}'s only name is {only}. {text}, so other checks may fail it "
        f"too; {effect} {fix}")


def _holder(node: Tag) -> str:
    """How a review names `node`: by the role it honors where one is
    given, else by its tag (a drawing's, MathML's)."""
    role = _role_of(node)
    if role and role in (node.get("role") or "").lower().split():
        return f'element with role="{role}"'
    return (("drawing's " if namespace_of(node) == "svg" else "")
            + f"<{node.name}>")


def _an(holder: str) -> str:
    """The article before `holder` (_holder): "an <svg>", read as
    letters, too."""
    return ("an" if holder.lstrip("<")[:1] in "aeiou"
            or holder.startswith("<svg") else "a")


def _nearest_common_ancestor(a: Tag, b: Tag) -> Tag | None:
    ancestors = {id(x) for x in a.parents}
    for anc in b.parents:
        if id(anc) in ancestors:
            return anc
    return None


def _adjacent_siblings(a: Tag, b: Tag) -> bool:
    sib = a.next_sibling
    while sib is not None and not isinstance(sib, Tag):
        if str(sib).strip():
            return False
        sib = sib.next_sibling
    return sib is b


#: hrefs a template leaves on links that have no destination yet. `#` is
#: the classic; Bootstrap themes ship `#!`; `#/` is an empty client route.
_PLACEHOLDER_HREFS = frozenset({"#", "#!", "#/"})


def check_redundant_links(page: PageContext) -> RuleResult:
    """2.4.4 (pled pattern; fix per technique H2) — adjacent links to the
    same destination.

    Adjacency is judged in document order over focusable elements, so the
    common nested shape (image link, then a heading containing the text
    link) is caught, not only literal sibling <a>s. Verdict discipline:
    duplicates are not an SC failure on their own (policy-vs-spec) — a
    product card with an image link and a title link to the same page
    conforms — so the rule never FAILS (basis `policy`; the engine enforces
    it). The unambiguous H2 shape (siblings, or a shared container below
    landmark level) is reported at moderate impact, which `--strict` gates;
    the rest (a logo link, then "Home") at minor."""
    r = RuleResult("bb-redundant-links", applicable=False)
    focusables = [el for el in page.soup.find_all(True)
                  if _is_focusable(el) and not _excluded_from_tree(el)]
    if page.soup.select_one("a[href]") is not None:
        r.applicable = True
    prev: Tag | None = None
    for el in focusables:
        if (prev is not None and prev.name == "a" and el.name == "a"
                and prev.has_attr("href") and el.has_attr("href")):
            href = _norm(prev.get("href"))
            # "#" and the template placeholders "#!" and "#/" are not
            # destinations: two links to them are unfinished, not redundant.
            if href and href not in _PLACEHOLDER_HREFS and href == _norm(el.get("href")):
                nca = _nearest_common_ancestor(prev, el)
                unambiguous = (_adjacent_siblings(prev, el)
                               or (nca is not None
                                   and nca.name not in _LANDMARK_BOUNDARY))
                if unambiguous:
                    r.findings.append(_f(
                        "bb-redundant-links", NEEDS_REVIEW, MODERATE,
                        "Adjacent links to the same destination ('redundant "
                        "links'); combining them into one link (technique H2) "
                        "removes the duplicate stop.", prev))
                else:
                    r.findings.append(_f(
                        "bb-redundant-links", NEEDS_REVIEW, MINOR,
                        "Consecutive links to the same destination across a "
                        "landmark boundary (e.g. logo, then Home); consider "
                        "whether one is redundant.", prev))
        prev = el
    return r


_NATIVE_FIELDS = ("input", "select", "textarea")


def _field_candidate(el: Tag) -> bool:
    # An <input> of a drawing or of MathML is no field (R5S-4).
    return ((el.name in _NATIVE_FIELDS and namespace_of(el) == "html")
            or el.has_attr("role"))


def _role_name(el: Tag, page: PageContext, role: str) -> str:
    """The name of an element checked for its `role`: by its author only
    (aria-labelledby, aria-label, title) unless the role takes its name
    from content (aria.NAME_FROM_CONTENT_ROLES); a native field also by its
    label."""
    return static_accname(el, page.soup, page.ids,
                          content=role in NAME_FROM_CONTENT_ROLES)


def check_control_label(page: PageContext) -> RuleResult:
    """3.3.2 / 1.3.1 / 4.1.2 — form fields must be labeled.

    The fields are those of ACT rule e086e5, chosen by role (P2-09): native
    fields (<input> other than the button and hidden types, <select>,
    <textarea>) and any element whose role is a form field's — checkbox,
    combobox, listbox, menuitemcheckbox, menuitemradio, radio, searchbox,
    slider, spinbutton, switch, textbox — such as a <div role="checkbox">.
    A field given another role (`<input role="button">`) is that role's
    rule's. Disabled fields are checked too, as e086e5 does.

    A field with no name fails. A field named only by its placeholder is a
    review (decision D4): browsers expose the placeholder as the name, so
    ACT rule e086e5 passes it for its name (Passed Example 5), but the
    rule's note says 3.3.2 still requires a visible label that does not
    disappear as the user types, and markup cannot tell whether other
    visible text labels the field. It is pled in complaints, so the review
    is moderate and `--strict` gates it (engine.strict_gated).

    Two parts of a combobox are minor reviews when unnamed, not failures:
    a role="combobox" element that wraps the text field users type in (the
    ARIA 1.1 pattern, where assistive technology names what the field
    inside is named), and the listbox a combobox controls (its popup).
    e086e5 applies to both by their roles, but its examples have neither,
    and axe-core exempts both; whether they fail is left to a person
    (L49)."""
    r = RuleResult("bb-control-label", applicable=False)
    popups = None
    for c in page.soup.find_all(_field_candidate):
        role = _role_of(c)
        if role not in FORM_FIELD_ROLES or _inert_content(c):
            continue
        if _out_of_tree(c):
            continue
        r.applicable = True
        if _role_name(c, page, role):
            review = (_field_review(c, page) if c.name in _NATIVE_FIELDS
                      else None)
            if review is not None:
                r.findings.append(_f("bb-control-label", NEEDS_REVIEW,
                                     *review, c))
            continue
        if c.name not in _NATIVE_FIELDS and not _norm(c.get("aria-placeholder")):
            if role == "combobox" and c.find(_text_field) is not None:
                r.findings.append(_f(
                    "bb-control-label", NEEDS_REVIEW, MINOR,
                    "This combobox has no accessible name, and wraps the text "
                    "field users type in (the ARIA 1.1 pattern): assistive "
                    "technology announces what that field is named, so this "
                    "may be no barrier. Give the combobox its label too "
                    "(aria-labelledby).", c))
                continue
            if role == "listbox":
                if popups is None:
                    popups = _combobox_popups(page)
                if id(c) in popups:
                    r.findings.append(_f(
                        "bb-control-label", NEEDS_REVIEW, MINOR,
                        "This listbox, the popup of a combobox, has no "
                        "accessible name: name it after the combobox "
                        "(aria-labelledby pointing at the combobox's label).",
                        c))
                    continue
            r.findings.append(_f(
                "bb-control-label", FAIL, BLOCKER,
                f"Form field (role=\"{role}\") has no accessible name: give "
                "it aria-labelledby pointing at its visible label, or "
                "aria-label.", c))
            continue
        # Browsers name a text field or a <textarea> by its placeholder
        # (a custom field by its aria-placeholder) when nothing else names
        # it, but no other field (_placeholder_names: R6AB-4).
        native = c.name in _NATIVE_FIELDS
        if (_norm(c.get("placeholder")) and _placeholder_names(c)
                if native else _norm(c.get("aria-placeholder"))):
            label = _label_cut(c, page) if native else None
            r.findings.append(_f(
                "bb-control-label", NEEDS_REVIEW, MODERATE,
                "Form field is named only by its placeholder, which "
                "disappears as the user types, so no label stays visible. The "
                "placeholder gives it a name, but unless other visible text "
                "labels the field it fails 3.3.2 Labels or Instructions (as "
                "ACT rule e086e5 notes). Pled in complaints — add a visible "
                "<label>." + (
                    " Its <label> names it nothing in Chrome and Edge "
                    "(Chromium 141): it is empty or hidden, or holds only "
                    "what they do not read, the field itself aside. They "
                    "read that <label> in place of the placeholder, so "
                    "there it has no name at all (L104)."
                    if label is not None else ""), c))
        else:
            unnamed = ""
            if native and _norm(c.get("placeholder")):
                unnamed = (
                    " Its placeholder does not name it: a placeholder names "
                    "only a text field (an <input> of type text, search, "
                    "tel, url, email, password or number) or a <textarea>, "
                    "in HTML-AAM and in Chrome and Edge (Chromium 141)"
                    + (", though axe-core 4.12 passes an <input> by its "
                       "placeholder whatever its type."
                       if c.name == "input" else "."))
            r.findings.append(_f(
                "bb-control-label", FAIL, BLOCKER,
                "Form field has no associated label or accessible name."
                + unnamed, c))
    return r


#: HTML's input types: one it does not have is in the text state.
_INPUT_TYPES = frozenset((
    "hidden", "text", "search", "tel", "url", "email", "password", "date",
    "month", "week", "time", "datetime-local", "number", "range", "color",
    "checkbox", "radio", "file", "submit", "image", "reset", "button"))
#: The input types a placeholder names (HTML-AAM; Chromium 141 alike,
#: measured: R6AB-4).
_PLACEHOLDER_TYPES = frozenset((
    "text", "search", "tel", "url", "email", "password", "number"))


def _placeholder_names(field: Tag) -> bool:
    """Does a native field's placeholder name it where nothing else does?
    A <textarea>'s, and a text field's (an <input> of a type of
    _PLACEHOLDER_TYPES, or of one HTML does not have, which is text): not
    a <select>'s, nor that of a date field, a range, a color well, a
    checkbox and the like, which Chromium 141 leaves nameless (measured:
    R6AB-4)."""
    if field.name == "textarea":
        return True
    if field.name != "input":
        return False
    kind = (field.get("type") or "text").lower()
    return kind in _PLACEHOLDER_TYPES or kind not in _INPUT_TYPES


def _field_review(field: Tag, page: PageContext) -> tuple | None:
    """The impact and message of the review of a native form field the
    accessible-name computation names and Chrome and Edge do not, which
    read its <label>s in place of its title and placeholder (L104), or
    None. Named by its title past <label>s that give it nothing either
    way: minor (_EMPTY_LABEL_REVIEW; axe-core 4.12 passes it by that
    title). Named by text in its <label> that Chromium 141 does not read
    (an <article>'s, a <math>'s, a <span>'s title: R6AB-3), a review as
    a button's (_cut_review): minor where its title, or its placeholder
    but a <select>'s, passes it in axe-core 4.12 (its label and
    select-name rules, measured); else moderate, since axe-core reads a
    <label>'s content by rules of its own, and may fail it."""
    cuts: list = []
    if static_accname(field, page.soup, page.ids, chromium=True,
                      cuts=cuts):
        return None
    if not any(kind == "label" for kind, _node in cuts):
        return None
    if not _label_for_control(field, page.ids, page.soup):
        return MINOR, _EMPTY_LABEL_REVIEW
    inner = next(((kind, node) for kind, node in cuts
                  if kind == "title" or (kind == "content"
                                         and subtree_text(node, page.ids))),
                 None)
    if inner is None:
        return MINOR, _EMPTY_LABEL_REVIEW
    title = _norm(field.get("title"))
    if title or (field.name != "select"
                 and _norm(field.get("placeholder"))):
        return _cut_review("form field", field, *inner, True)
    # axe-core 4.12 reads a title in a <label> as in a link (_axe_titles),
    # and no MathML nor embedded content (measured); what else a <label>
    # holds it reads by rules of its own (it fails one holding an
    # <article>, passes one holding a <figure>).
    kind, node = inner
    why = _axe_why(kind, node, field, page.ids)
    if why is None and kind == "title":
        return _cut_review("form field", field, kind, node, True)
    if why is not None and why[0] in ("title", "embedded"):
        return _cut_review("form field", field, kind, node, False, why)
    lacks = "title" if field.name == "select" else "title or placeholder"
    return _cut_review(
        "form field", field, kind, node, False,
        because=(f"It has no {lacks} by which axe-core 4.12 would pass "
                 f"it, and that tool reads a <label>'s content by rules "
                 f"of its own"))


#: The review of a form field named, as the accessible-name computation
#: reads it, by its title past a <label> that names it nothing, which
#: Chromium 141 reads in the title's place (L104, measured). axe-core 4.12
#: passes such a field by its title (its label and select-name rules), so
#: it is minor, as the same <label> on a button is (R6S-4). The <label>
#: may hold the field, or what Chromium does not read (R6AB-2).
_EMPTY_LABEL_REVIEW = (
    "Named by the accessible-name computation, but not in Chrome or Edge "
    "(Chromium 141): this form field has a <label> that names it nothing "
    "there (it is empty or hidden, or holds only what they do not read, "
    "the field itself aside), and Chrome and Edge read its <label> in "
    "place of its title and placeholder. Other checks usually pass it; in "
    "Chrome and Edge it has no accessible name, so screen readers may "
    "announce it without one, and voice control may not find it by its "
    "name. Fix: give the <label> the field's name as its text, or remove "
    "it.")


def _label_cut(field: Tag, page: PageContext) -> Tag | None:
    """The first of the <label>s of a native form field that Chromium 141
    reads in place of its title and placeholder when they name it
    nothing (accname._field_name, L104); None where Chromium names it,
    or no label labels it."""
    cuts: list = []
    if static_accname(field, page.soup, page.ids, chromium=True,
                      cuts=cuts):
        return None
    return next((node for kind, node in cuts if kind == "label"), None)


def _text_field(t) -> bool:
    """An element users type text into: a text-like <input>, a
    <textarea>, or a role=textbox or searchbox."""
    if not isinstance(t, Tag):
        return False
    if t.name == "input":
        return (t.get("type") or "text").lower() in (
            "text", "search", "email", "url", "tel", "password", "number")
    return t.name == "textarea" or _role_of(t) in ("textbox", "searchbox")


def _combobox_popups(page: PageContext) -> set:
    """The listboxes a combobox controls (by id()): the ones its
    aria-controls or aria-owns names, in its own tree, and any inside it."""
    out: set = set()
    for cb in page.soup.find_all(attrs={"role": True}):
        if _role_of(cb) != "combobox":
            continue
        ids = ids_within(page.ids, cb)
        for attr in ("aria-controls", "aria-owns"):
            for ref in (cb.get(attr) or "").split():
                target = ids.get(ref)
                if target is not None:
                    out.add(id(target))
        for inner in cb.find_all(attrs={"role": True}):
            if _role_of(inner) == "listbox":
                out.add(id(inner))
    return out


#: What an unnamed element of each role the name-by-role rules check costs.
_WIDGET_WHAT = {
    "menuitem": "menu item", "option": "option", "tab": "tab",
    "tooltip": "tooltip", "treeitem": "tree item",
    "progressbar": "progress bar", "meter": "meter",
    "img": "image", "image": "image",
}
#: Elements other rules name: an <img>, an image input or area
#: (bb-img-alt), an <svg> (bb-svg-name), an <object> (bb-object-alt).
_NAMED_ELSEWHERE = ("img", "input", "area", "svg", "object")


def _name_by_role(page: PageContext, rule_id: str, roles) -> RuleResult:
    """The elements of `roles`, chosen by explicit role (P2-09), that must
    be named: a role named by its content (a tab, a menu item) is named by
    its text; the others by aria-label, aria-labelledby or title only.
    Elements hidden when the page was captured are checked too, as
    bb-link-name and bb-button-name check them: a closed menu's items are
    named when it opens (QR-9). Images other rules name (<img>, <svg>,
    <object>, image inputs and areas) are theirs.

    An empty tooltip is a review, never a FAIL: a tooltip is not a
    control, W3C names no failure for it, and its text is often written by
    the script that shows it."""
    r = RuleResult(rule_id, applicable=False)
    recorded = page.hiding_recorded
    for el in page.soup.find_all(attrs={"role": True}):
        role = _role_of(el)
        if role not in roles or el.name in _NAMED_ELSEWHERE:
            continue
        if _inert_content(el) or _out_of_tree(el):
            continue
        r.applicable = True
        if _role_name(el, page, role):
            continue
        what = _WIDGET_WHAT[role]
        if role == "tooltip":
            shown = recorded and not _capture_hidden(el)
            r.findings.append(_f(
                rule_id, NEEDS_REVIEW, MINOR,
                "role=\"tooltip\" element is empty"
                + (" while shown: assistive technology has nothing to "
                   "announce for it. " if shown else
                   ". Its text may be written by the script that shows it; "
                   "if it stays empty when shown, it has no accessible "
                   "name. ")
                + "A tooltip is not a control, and W3C names no failure "
                  "for an empty one.", el))
            continue
        how = ("text, aria-label or aria-labelledby"
               if role in NAME_FROM_CONTENT_ROLES
               else "aria-label or aria-labelledby (its content does not "
                    "name it)")
        r.findings.append(_f(
            rule_id, FAIL, SERIOUS,
            f"{what[0].upper() + what[1:]} (role=\"{role}\") has no "
            f"accessible name: give it {how}.", el))
    return r


def check_widget_name(page: PageContext) -> RuleResult:
    """4.1.2 — a menu item, option, tab or tree item has a name: unnamed,
    it fails (W3C failure F68: a user interface control with no
    programmatically determined name; ACT rule m6b1q3 for menu items). An
    empty tooltip is a review."""
    return _name_by_role(page, "bb-widget-name", CONTROL_NAME_ROLES)


def check_role_img_name(page: PageContext) -> RuleResult:
    """1.1.1 — an image made with role="img" (a <div>, an icon font's <i>)
    has a name: aria-label, aria-labelledby or title. ACT rule 23a2a8
    applies to it by its role."""
    return _name_by_role(page, "bb-role-img-name", IMG_ROLES)


def check_progress_name(page: PageContext) -> RuleResult:
    """1.1.1 (heuristic) — a progress bar or meter has a name. WAI-ARIA
    requires one and axe-core reports it under 1.1.1, but W3C names no
    failure for it: a FAIL is a probable failure."""
    return _name_by_role(page, "bb-progress-name", PROGRESS_ROLES)


#: Elements whose own role is generic (or none): a role attribute is all
#: that can tell assistive technology what such an element is. Custom
#: elements (a name with a hyphen) are generic too.
_GENERIC_ELEMENTS = frozenset({
    "div", "span", "b", "i", "u", "s", "small", "font", "center", "big",
    "tt", "strike", "nobr", "q", "samp", "kbd", "var", "data", "bdi", "bdo",
})


def _generic(el: Tag) -> bool:
    return el.name in _GENERIC_ELEMENTS or "-" in (el.name or "")


def _roleless_control(el: Tag) -> bool:
    """A generic element made focusable (tabindex 0 or more) whose role
    attribute names no role a browser knows: it has no role at all, as
    role="buton" does (L19). If it is a control, that fails 4.1.2, as W3C
    failure F59 describes; focus alone does not show that it is one."""
    if not _generic(el):
        return False
    tokens = (el.get("role") or "").lower().split()
    if not tokens or any(t in ROLES for t in tokens):
        return False
    ti = _tabindex(el)
    return ti is not None and ti >= 0


def check_control_role(page: PageContext) -> RuleResult:
    """4.1.2 (heuristic) — a focusable custom control has a valid role
    (L19).

    Applies to generic elements (<div>, <span>, a custom element) that take
    keyboard focus (tabindex 0 or more) and carry a role attribute, or carry
    a click or key handler of their own (onclick, onkeydown, onkeyup,
    onkeypress: S5-3) and no role a control has, which makes the element
    read as the control F59 describes: no role attribute, an empty one, or
    none, presentation or generic as the first role it names (a focusable
    element keeps its own role for none and presentation, a <div>'s
    generic one: ARIA's presentational role conflict resolution). When no
    token of the role is a role a browser knows (role="buton", an abstract
    role such as "widget"), or there is none, the element has no role, and
    assistive technology
    cannot say what it is: a FAIL, probable rather than certain (Part R2
    review): W3C failure F59 names a control made with script and given no
    role, and focus alone does not show the element is a control (a
    focusable scroll container is not). ACT 674b10 does not require a valid
    role value on its own because an element's own role can stand in; here
    there is none. An unknown role on anything else is bb-aria-role's (a
    best practice)."""
    r = RuleResult("bb-control-role", applicable=False)
    for el in page.soup.find_all(attrs={"role": True}):
        if not _generic(el) or _inert_content(el):
            continue
        ti = _tabindex(el)
        if ti is None or ti < 0 or _excluded_from_tree(el):
            continue
        r.applicable = True
        if _roleless_control(el):
            token = (el.get("role") or "").split()[0]
            r.findings.append(_f(
                "bb-control-role", FAIL, SERIOUS,
                f"Focusable element has no valid role: \"{token}\" is not an "
                "ARIA role, so if it is a control, assistive technology "
                "cannot tell what it is (as W3C failure F59 describes). Use "
                "the role it was meant to have, or a native element.", el))
    # No role a control has, with a handler of its own for clicks or keys
    # (S5-3): the control F59 describes, as its markup writes it (a handler
    # a script attaches leaves no trace in markup; bellbriar-lint reads the
    # source's onClick).
    for el in page.soup.find_all(_HANDLED_GENERIC):
        if _inert_content(el) or _excluded_from_tree(el):
            continue
        ti = _tabindex(el)
        if ti is None or ti < 0:
            continue
        r.applicable = True
        handler = next(a for a in _CONTROL_HANDLERS if el.has_attr(a))
        role = el.get("role")
        said = "" if role is None else (
            f' (role="{" ".join(role.split())[:60]}" is not a control\'s '
            "role)")
        r.findings.append(_f(
            "bb-control-role", FAIL, SERIOUS,
            f"Focusable element with an {handler} handler has no role"
            f"{said}, so "
            "assistive technology cannot tell what it is (as W3C failure "
            "F59 describes). Use a native element (a <button>, or a link "
            "that goes somewhere), or give it the role it is meant to "
            "have.", el))
    return r


#: The handlers of their own that make a focusable generic element read
#: as a control (check_control_role).
_CONTROL_HANDLERS = ("onclick", "onkeydown", "onkeyup", "onkeypress")


#: First roles that give a focusable generic element no role a control has
#: (check_control_role).
_NO_CONTROL_ROLES = ("none", "presentation", "generic")


def _handled_generic(el) -> bool:
    """A generic element with a handler of its own for clicks or keys
    (_CONTROL_HANDLERS) and no role a control has: no role attribute, an
    empty one, or one whose first role a browser knows is none,
    presentation or generic (S5 re-review). An attribute naming no role a
    browser knows is the rule's other loop's."""
    if not (isinstance(el, Tag) and _generic(el)
            and any(el.has_attr(a) for a in _CONTROL_HANDLERS)):
        return False
    if not el.has_attr("role"):
        return True
    return not _roles(el) or _explicit_role(el) in _NO_CONTROL_ROLES


_HANDLED_GENERIC = _handled_generic


def check_html_lang(page: PageContext) -> RuleResult:
    """3.1.1 — page language (pled, e.g. Mejico v. Kraft Heinz).

    ACT bf051a: the tag's primary language subtag must be one the IANA
    registry lists (langtags.py), so `lang="xx"` fails though it is well
    formed, and so do `lang="eng"` (BCP 47 writes English "en"; Failed
    Example 3), a private-use tag (`x-…`) and every grandfathered tag
    (`i-lux`, Failed Example 4; ACT gives none of them a known primary
    language tag, `zh-min-nan` included). A three-letter subtag missing
    from this copy of the registry is a review: the registry adds such
    codes every year."""
    r = RuleResult("bb-html-lang", applicable=True)
    html = page.soup.find("html")
    lang = _norm(html.get("lang")) if html is not None else ""
    if (page.reader == "xml" and html is not None
            and html.get("xml:lang") is not None):
        # In an XML document xml:lang sets the language, and wins over lang
        # (HTML's "the lang and xml:lang attributes"); XHTML 1.1 allows only
        # xml:lang (OR2-4).
        lang = _norm(html.get("xml:lang"))
    if not lang:
        r.findings.append(_f("bb-html-lang", FAIL, SERIOUS,
                             "<html> has no lang attribute.", html))
        return r
    primary = lang.split("-")[0].lower()
    preferred = GRANDFATHERED.get(lang.lower())
    if preferred is not None:
        use = f' Use "{preferred}".' if preferred else ""
        r.findings.append(_f(
            "bb-html-lang", FAIL, SERIOUS,
            f"lang=\"{lang}\" is a grandfathered tag, which names no "
            "registered primary language subtag, so assistive technology may "
            f"not recognize it (ACT bf051a).{use}", html))
        return r
    if not LANG_RE.match(lang):
        if primary == "x" and "-" in lang:
            msg = (f"lang=\"{lang}\" is a private-use tag, which names no "
                   "registered language, so assistive technology cannot tell "
                   "what language the page is in.")
        else:
            msg = f"lang=\"{lang}\" is not a valid language tag."
        r.findings.append(_f("bb-html-lang", FAIL, SERIOUS, msg, html))
        return r
    if primary in PRIMARY_LANGUAGE_SUBTAGS:
        return r
    two = ISO_639_2_TWO_LETTER.get(primary)
    if two:
        r.findings.append(_f(
            "bb-html-lang", FAIL, SERIOUS,
            f"lang=\"{lang}\": \"{primary}\" is the ISO 639-2 code of a language "
            f"BCP 47 writes \"{two}\", and the IANA registry lists no "
            f"\"{primary}\", so assistive technology may not recognize it. "
            f"Use \"{two}\".", html))
    elif len(primary) == 2:
        r.findings.append(_f(
            "bb-html-lang", FAIL, SERIOUS,
            f"lang=\"{lang}\": \"{primary}\" is not a language in the IANA "
            "language subtag registry, so assistive technology cannot tell "
            "what language the page is in.", html))
    else:
        r.findings.append(_f(
            "bb-html-lang", NEEDS_REVIEW, MINOR,
            f"lang=\"{lang}\": \"{primary}\" is not in the IANA language "
            f"subtag registry as of {REGISTRY_DATE}. If it is a newer code, "
            "nothing is wrong; if not, assistive technology cannot tell what "
            "language the page is in.", html))
    return r


def check_page_title(page: PageContext) -> RuleResult:
    """2.4.2 — page has a non-empty title (descriptiveness = judge layer)."""
    r = RuleResult("bb-page-title", applicable=True)
    head = page.soup.head
    t = next((x for x in head.find_all("title") if not _inert_content(x)),
             None) if head is not None else None
    if t is None:  # tolerate a missing <head>, but never accept an SVG title
        t = next((x for x in page.soup.find_all("title")
                  if x.find_parent("svg") is None
                  and not _inert_content(x)), None)
    if t is None or not _norm(t.get_text()):
        r.findings.append(_f("bb-page-title", FAIL, SERIOUS,
                             "Document has no non-empty <title>.", t))
    return r


def _in_tree(elements) -> list:
    return [el for el in elements if not _excluded_from_tree(el)]


_SECTIONING = ("article", "aside", "main", "nav", "section")
_BESIDE_ROLES = ("navigation", "complementary", "contentinfo", "dialog",
                 "alertdialog")
#: Class or id names of the blocks beside the content on sites built without
#: landmark elements (`<div id="footer">`, `.sidebar`, `.breadcrumb`). Whole
#: names only: modifiers such as `no-sidebar`, `has-sidebar` or
#: `content-sidebar-wrap` name a layout, not the block.
_BESIDE_NAMES = frozenset({
    "footer", "site-footer", "page-footer", "global-footer", "main-footer",
    "sidebar", "site-sidebar", "left-sidebar", "right-sidebar",
    "sidebar-left", "sidebar-right", "primary-sidebar", "secondary-sidebar",
    "sidebar-primary", "sidebar-secondary", "widget-area",
    "breadcrumb", "breadcrumbs", "breadcrumb-trail"})
_HEADING_RE = re.compile(r"^h[1-6]$")
#: A control with no target to follow (a <button> that moves focus by
#: script) counts as a skip control only when its name is unmistakable.
SKIP_CONTROL_RE = re.compile(
    r"^\W*(?:(?:skip|jump)\s+to\s+(?:the\s+)?(?:main(?:\s+content)?|content"
    r"|page\s+content)|skip\s+(?:the\s+)?(?:main\s+)?(?:content|navigation"
    r"|nav|menu|links))\b", re.I)


def _roles(el: Tag) -> list[str]:
    return (el.get("role") or "").lower().split()


def _having_role(with_role: list, role: str) -> list:
    return [el for el in with_role if role in _roles(el)]


def _page_level(el: Tag) -> bool:
    """A header or footer that belongs to the page, not to an article or
    section inside it (HTML-AAM: only then is it a banner or contentinfo)."""
    return not any(isinstance(p, Tag) and p.name in _SECTIONING
                   for p in el.parents)


def _named_beside(el: Tag) -> bool:
    """Named as a footer, sidebar or breadcrumb trail, as sites without
    landmark elements do. Never the page itself."""
    if el.name in ("html", "body", "main"):
        return False
    names = list(_class_names(el))
    names.append(el.get("id") or "")
    return (any(isinstance(n, str) and n.lower() in _BESIDE_NAMES
                for n in names)
            or "breadcrumb" in (el.get("aria-label") or "").lower())


_FOOTER_NAMES = frozenset({"footer", "site-footer", "page-footer",
                           "global-footer", "main-footer"})


def _footer_block(el: Tag, in_section: bool) -> bool:
    """The page's footer: a page-level <footer>, role=contentinfo, or a
    block named footer. `in_section`: inside sectioning content."""
    if (el.name == "footer" and not in_section) or "contentinfo" in _roles(el):
        return True
    names = list(_class_names(el))
    names.append(el.get("id") or "")
    return any(isinstance(n, str) and n.lower() in _FOOTER_NAMES
               for n in names)


def _in_footer(el: Tag) -> bool:
    chain = [p for p in (el, *el.parents) if isinstance(p, Tag)
             and p.parent is not None]
    in_section = False
    for node in reversed(chain):
        if _footer_block(node, in_section):
            return True
        in_section = in_section or node.name in _SECTIONING
    return False


def _beside(el: Tag, in_section: bool | None = None) -> bool:
    """A block beside the content, by itself: navigation, an aside, the page
    footer, a dialog, or a block named footer, sidebar or breadcrumb.
    `in_section` (inside sectioning content) saves the ancestor walk."""
    if el.name in ("nav", "aside", "dialog") or any(
            r in _BESIDE_ROLES for r in _roles(el)):
        return True
    if el.name == "footer":
        page_level = _page_level(el) if in_section is None else not in_section
        if page_level:
            return True
    return _named_beside(el)


def _beside_of(el: Tag, include_self: bool = False) -> bool:
    """In a block beside the content. A navigation inside the footer, an
    aside, a sidebar or a dialog, or one named as a breadcrumb trail, is not
    the navigation a bypass has to get past; `include_self` asks the same
    of an element that is not itself a navigation."""
    if _beside(el) if include_self else _named_beside(el):
        return True
    return any(isinstance(p, Tag) and p.parent is not None and _beside(p)
               for p in el.parents)


def _in_dialog(el: Tag) -> bool:
    return any(isinstance(a, Tag) and (a.name == "dialog" or any(
        r in ("dialog", "alertdialog") for r in _roles(a)))
        for a in (el, *el.parents))


def _modal_open(page: "PageContext") -> bool:
    """Is a modal dialog open over the page (aria-modal="true" on a shown
    <dialog> or role=dialog/alertdialog)? Then the dialog is what the page
    exposes, and the page behind it is not evaluated as the page."""
    for el in page.soup.find_all(attrs={"aria-modal": True}):
        if (el.get("aria-modal") or "").strip().lower() != "true":
            continue
        if not (el.name == "dialog" or any(r in ("dialog", "alertdialog")
                                           for r in _roles(el))):
            continue
        if el.name == "dialog" and not el.has_attr("open"):
            continue
        if not _excluded_from_tree(el) and not _capture_hidden(el):
            return True
    return False


def _present(elements) -> list:
    """In the accessibility tree and part of the page: a dialog open over
    the page (a consent or region picker) is not the page."""
    return [el for el in elements
            if not _excluded_from_tree(el) and not _in_dialog(el)]


def _within(el: Tag, anc: Tag | None) -> bool:
    return anc is not None and (el is anc or any(p is anc for p in el.parents))


def _is_heading(el: Tag) -> bool:
    return bool(_HEADING_RE.match(el.name or "")) or "heading" in _roles(el)


def _root_path(href: str) -> bool:
    try:
        parts = urllib.parse.urlsplit(href.strip())
    except ValueError:
        return False
    return (parts.path in ("", "/", "./", "index.html", "/index.html")
            and not parts.query and not parts.fragment)


def _site_title(h: Tag) -> bool:
    """A heading that is only the link home: the site's name or logo set as
    a heading (`<h1><a href="/"><img alt="Acme"></a></h1>`), not content."""
    links = h.find_all("a", href=True)
    if len(links) != 1 or not _root_path(links[0].get("href") or ""):
        return False
    outside = [t for t in h.find_all(string=True)
               if type(t) is NavigableString and t.strip()
               and not _within(t.parent, links[0])]
    return not outside


#: How many of the page's first links can be a skip link recognised by its
#: position alone (in any language): a consent banner or the logo may come
#: first. One that says it skips may sit anywhere before the end of the
#: navigation.
SKIP_LINK_WINDOW = 5
#: What may sit between the repeated blocks and the heading that opens the
#: content — an eyebrow line, a breadcrumb or "Back to blog" link, a print
#: button — before that heading no longer counts as the start of it.
_OPENING_TEXT_LIMIT = 200
_OPENING_FOCUS_LIMIT = 3
#: How many links or controls of the page header and the leading
#: navigation may come before a working skip link (a logo, a utility link,
#: a search toggle) before it counts as late: a keyboard user has already
#: passed most of what it skips.
_SKIP_LATE_LIMIT = 3
#: Links and controls of any kind that may come before a working skip link
#: (a consent notice, a top bar of contact links) before it counts as late.
_SKIP_LATE_ANY = 10
#: A block is more than a single link (Understanding 2.4.1): the repeated
#: blocks a FAIL rests on hold at least this many links or controls.
_BLOCK_MIN_FOCUS = 2
_TEXTLESS = ("script", "style", "template", "noscript")
#: Text that names a control rather than being content: a language menu's
#: options, a button's label.
_CONTROL_TEXT = ("select", "datalist", "textarea", "button", "label")


#: What the first perceivable content can be besides text: embedded and
#: interactive content (Part R2 review, bb-skip-link's landmark).
_EMBEDDED = frozenset({"img", "svg", "picture", "video", "audio", "canvas",
                       "iframe", "object", "embed", "math", "input", "select",
                       "textarea", "button", "meter", "progress"})
#: A landmark named for searching ("Search", "Site search").
_SEARCH_NAME = re.compile(r"search", re.I)


def _searchy(el: Tag) -> bool:
    """A search: inside a search landmark (<search>, role=search), or
    holding a search field (type=search, role=searchbox or search)."""
    if any(isinstance(p, Tag) and (p.name == "search" or "search" in _roles(p))
           for p in (el, *el.parents)):
        return True
    return el.find(lambda t: isinstance(t, Tag) and (
        (t.name == "input" and (t.get("type") or "").strip().lower()
         == "search")
        or any(r in ("searchbox", "search") for r in _roles(t)))) is not None


class _Bypass:
    """Where the repeated blocks end, so the rule can tell what comes before
    the navigation, what lies beyond it, and what is inside it.

    The navigations that lead the page are the ones a user meets before the
    content — never one in the footer, an aside, a sidebar or breadcrumb
    trail, or a dialog. With a main landmark, those before <main>; if the
    page puts its navigation at the top of <main> with nothing ahead of
    <main> (`wraps`), that one, and <main> bypasses nothing. Without a main
    landmark, those before the first content heading. `nav` is the first of
    them (None if there is none), `last_nav` the last."""

    def __init__(self, page: PageContext, navs: list, mains: list,
                 with_role: list):
        soup = page.soup
        self.page = page
        self.order = {id(el): i for i, el in enumerate(soup.find_all(True))}
        self._ends: dict[int, int] = {}
        self.content_start: int | None = None
        self._in_blocks: set | None = None
        self.targets = self._fragment_targets(soup, page.ids)
        first = (lambda els: min(els, key=self.pos) if els else None)
        top = [n for n in navs if not _beside_of(n)]
        self.main = first(mains)
        self.wraps = False
        lead: list = []
        if self.main is not None:
            lead = [n for n in top if self.pos(n) < self.pos(self.main)
                    and not self.contains(self.main, n)]
            if not lead:
                inside = [n for n in top if self.contains(self.main, n)]
                start = first(inside)
                if (start is not None and self._leads(self.main, start)
                        and not self._anything_before(self.main)):
                    lead, self.wraps = [start], True
        else:
            # Without <main>, the content starts at its first heading or
            # where its text does; a navigation after that leads nothing.
            heading = self.content_heading()
            starts = [p for p in (None if heading is None else self.pos(heading),
                                  self._content_text())
                      if p is not None]
            self.content_start = min(starts) if starts else None
            lead = [n for n in top if self.content_start is None
                    or self.pos(n) < self.content_start]
        self.lead = lead
        self.nav = first(lead)
        self.last_nav = max(lead, key=self.pos) if lead else None
        self._holders = {id(p) for n in lead for p in (n, *n.parents)}
        # A header inside the page footer is not the page's banner, nor,
        # without <main>, one that comes after the content starts.
        headers = _present(h for h in soup.find_all("header")
                           if _page_level(h) and not _in_footer(h)
                           and self._before_content(h))
        self.first_header = first(headers)
        self.banners = [h for h in headers if self._banner_header(h)] + \
            _present(b for b in _having_role(with_role, "banner")
                     if self._before_content(b))
        self._holders |= {id(p) for b in self.banners for p in (b, *b.parents)}

    def _before_content(self, el: Tag) -> bool:
        return self.content_start is None or self.pos(el) < self.content_start

    def header_start(self) -> int:
        """Position of the first page header or banner (-1 if none). Without
        <main>, nothing before it — a notice's text or heading, a site name
        set as a heading — is where the content starts: content does not
        come before the banner."""
        if not hasattr(self, "_header_start"):
            soup = self.page.soup
            heads = _present(
                [h for h in soup.find_all("header")
                 if _page_level(h) and not _in_footer(h)]
                + [b for b in soup.find_all(attrs={"role": True})
                   if "banner" in _roles(b)])
            self._header_start = min((self.pos(h) for h in heads), default=-1)
        return self._header_start

    def _content_text(self) -> int | None:
        """Where the page's own text passes _OPENING_TEXT_LIMIT characters,
        outside navigation, page headers, blocks beside the content, form
        controls and hidden or inert markup: past there, without <main>, is
        content. Text before the page header (a cookie notice, a top bar)
        is never the content (header_start). The walk is in document order
        and the result is a position between elements — every element that
        starts before that text is before it — so text written straight
        into <body> or a wrapper after the header counts, and places the
        content after the header, not where <body> starts."""
        soup = self.page.soup
        start = self.header_start()
        started = start < 0
        text = 0
        last = -1                    # the last element that starts before
        stack: list = [(soup, False)]
        while stack:
            node, in_section = stack.pop()
            if isinstance(node, Tag):
                if node is not soup:
                    last = self.pos(node)
                    if not started and last >= start:
                        started = True
                    if (_hidden_here(node) or node.name in _TEXTLESS
                            or node.name in _CONTROL_TEXT
                            or node.name == "nav" or _beside(node, in_section)
                            or any(r in ("navigation", "banner")
                                   for r in _roles(node))
                            or (node.name == "header" and not in_section)):
                        last = self.end(node)
                        continue
                child_section = in_section or node.name in _SECTIONING
                stack.extend((c, child_section) for c in reversed(node.contents))
            elif (started and type(node) is NavigableString
                  and node.parent is not None):
                text += len("".join(node.split()))
                if text > _OPENING_TEXT_LIMIT:
                    return last + 1
        return None

    @staticmethod
    def _fragment_targets(soup: BeautifulSoup, page_ids=None) -> dict:
        """What `#x` scrolls to: the first element with id x, else the first
        <a name="x">, in the document tree. Content of a <template>, or of a
        <noscript> in a browser that runs scripts, is not in it, nor is a
        shadow root's: the document's getElementById does not reach into
        one, so a skip link to a <main> inside a component moves nothing
        (OR-2)."""
        ids: dict = {}
        names: dict = {}
        for el in soup.find_all(True):
            i, n = el.get("id"), el.get("name") if el.name == "a" else None
            if not (isinstance(i, str) and i not in ids) and not (
                    isinstance(n, str) and n not in names):
                continue
            if any(isinstance(p, Tag) and p.name in ("template", "noscript")
                   for p in el.parents):
                continue
            if scope_of(page_ids, el) is not None:
                continue
            if isinstance(i, str):
                ids.setdefault(i, el)
            if isinstance(n, str):
                names.setdefault(n, el)
        return {**names, **ids}

    # -- document order ------------------------------------------------------
    def pos(self, el: Tag) -> int:
        return self.order.get(id(el), -1)

    def end(self, el: Tag) -> int:
        """Position of the last element inside `el` (its own if none)."""
        if id(el) not in self._ends:
            last = el
            for d in el.descendants:
                if isinstance(d, Tag):
                    last = d
            self._ends[id(el)] = self.pos(last)
        return self._ends[id(el)]

    def contains(self, outer: Tag, el: Tag) -> bool:
        return self.pos(outer) <= self.pos(el) <= self.end(outer)

    def before_nav(self, el: Tag) -> bool:
        return self.nav is not None and self.pos(el) < self.pos(self.nav)

    def beyond_nav(self, el: Tag) -> bool:
        """After the first navigation block and outside it: where a bypass
        has to lead. Everything is, when there is no navigation block."""
        return self.nav is None or self.pos(el) > self.end(self.nav)

    # -- the regions ---------------------------------------------------------
    def _leads(self, main: Tag, nav: Tag) -> bool:
        """Does the navigation open <main> — no content heading and no more
        than a short lead-in of text before it — rather than sit in its
        content (pagination, a table of contents)?"""
        text = 0
        for node in main.descendants:
            if node is nav:
                return True
            if isinstance(node, Tag):
                if _is_heading(node) and not _site_title(node) and \
                        static_accname(node, self.page.soup, self.page.ids):
                    return False
            elif type(node) is NavigableString:
                text += len("".join(node.split()))
                if text > _OPENING_TEXT_LIMIT:
                    return False
        return False

    def _anything_before(self, main: Tag) -> bool:
        """A link or control ahead of <main>, other than an in-page link to
        an element that exists (a skip link); a hash route is a link."""
        for el in main.previous_elements:
            if (isinstance(el, Tag) and _focusable_here(el)
                    and not (el.name == "a" and (el.get("href") or "")
                             .strip().startswith("#")
                             and self.target(el) is not None)
                    and not _excluded_from_tree(el) and not _in_dialog(el)):
                return True
        return False

    def _content_heading(self) -> Tag | None:
        """The first named content heading — after the start of the page
        header (header_start: a notice's heading or a site name set as a
        heading above it is not content), outside any page header, block
        beside the content and site title — if there is one."""
        soup, page = self.page.soup, self.page
        start = self.header_start()
        for h in soup.descendants:
            if not isinstance(h, Tag) or not _is_heading(h):
                continue
            if (self.pos(h) < start
                    or _excluded_from_tree(h) or _in_dialog(h) or _beside_of(h, True)
                    or any(isinstance(p, Tag) and (
                        (p.name == "header" and _page_level(p))
                        or "banner" in _roles(p)) for p in (h, *h.parents))
                    or _site_title(h)
                    or not static_accname(h, soup, page.ids)):
                continue
            return h
        return None

    def _banner_header(self, h: Tag) -> bool:
        """Is this page-level header the page's banner (a repeated block)?
        One that holds the navigation or comes before it is; with no
        navigation, the first one is. A header after the navigation around
        a post title is content."""
        if id(h) in self._holders:
            return True
        if self.nav is not None:
            return self.pos(h) < self.pos(self.nav)
        return h is self.first_header

    def is_banner(self, el: Tag, in_section: bool) -> bool:
        return ("banner" in _roles(el)
                or (el.name == "header" and not in_section
                    and self._banner_header(el)))

    def holds_block(self, el: Tag) -> bool:
        """Does `el` hold the banner or a leading navigation?"""
        return id(el) in self._holders

    def peripheral(self, el: Tag) -> bool:
        """Beside or around the content — navigation, an aside, the page
        footer or banner, a dialog, a footer, sidebar or breadcrumb block —
        or inside one."""
        for anc in (el, *el.parents):
            if not isinstance(anc, Tag) or anc.parent is None:
                continue
            if _beside(anc) or ("banner" in _roles(anc)) or (
                    anc.name == "header" and _page_level(anc)
                    and self._banner_header(anc)):
                return True
        return False

    # -- the skip link -------------------------------------------------------
    def target(self, link: Tag) -> Tag | None:
        href = (link.get("href") or "").strip()
        return self.targets.get(urllib.parse.unquote(href[1:]))

    def leads_past(self, link: Tag, target: Tag) -> bool:
        """Does following the link land past the repeated blocks? Beyond the
        navigation when there is one; otherwise after the link, and outside
        the banner and the blocks beside the content. A dialog or panel is
        not the content."""
        if _in_dialog(target):
            return False
        if self.nav is not None:
            if self.beyond_nav(target) or self._ends_nav(link, target):
                return True
            if (self.main is not None and not self.wraps) or self.contains(
                    target, self.nav):
                return False
        if self.pos(target) <= self.pos(link) or self.peripheral(target):
            return False
        return self.nav is None or self._passes_over(link, target)

    def _ends_nav(self, link: Tag, target: Tag) -> bool:
        """G123: a link at the start of the navigation to its end — the
        target inside it, after the link, with no link or control of the
        navigation after it."""
        nav = self.nav
        if not (self.contains(nav, target) and self.pos(target) > self.pos(link)):
            return False
        stop = self.end(nav)
        for el in target.next_elements:
            if isinstance(el, Tag):
                if self.pos(el) > stop:
                    break
                if _focusable_here(el) and not _excluded_from_tree(el):
                    return False
        return True

    def _passes_over(self, link: Tag, target: Tag) -> bool:
        for el in link.next_elements:
            if el is target:
                return False
            if (isinstance(el, Tag) and not _within(el, link)
                    and _is_focusable(el) and not _excluded_from_tree(el)):
                return True
        return False

    def _by_position(self, link: Tag, target: Tag) -> bool:
        """A skip link recognised in any language: placed before the
        navigation and leading into the content past it — not to a panel
        the link opens (a search box, a cart drawer)."""
        if not self.before_nav(link):
            return False
        if (target.get("id") or None) in (link.get("aria-controls") or "").split():
            return False
        if self.main is not None and not self.wraps:
            return (self.contains(self.main, target)
                    or self.contains(target, self.main))
        return not self.peripheral(target)

    def skip_link(self) -> tuple[Tag | None, Tag | None]:
        """(skip link, the element it reaches) — the target None when the
        link leads nowhere past the repeated blocks; (None, None) when there
        is no skip link.

        Up to the end of the last navigation that leads the page, a skip
        link is an in-page link that says it skips ("Skip to main content");
        among the first few links and placed before the navigation, one that
        leads past it in any language also counts. A working one wins over
        a broken one ("Skip to navigation" before "Skip to content"). A
        button that plainly says it skips to the content counts as a skip
        control; where it moves focus is interaction-layer. A hash route
        (#/shop) names no element; "Back to top", a link after the
        navigation (a hero's "Scroll to content" arrow) or an in-page nav
        item skips nothing. A link taken out of the tab order (a negative
        tabindex) is never reached by keyboard, so it does not work.
        Without a navigation, a link beyond the first few counts only if
        its name is unmistakable ("Skip to content", SKIP_CONTROL_RE) and
        it comes before the first content heading: a cookie notice or a
        top bar of contact links may come first."""
        soup, page = self.page.soup, self.page
        if self.last_nav is not None:
            stop = self.end(self.last_nav)
        else:
            heading = self.content_heading()
            stop = self.pos(heading) - 1 if heading is not None else None
        broken = None
        links = 0
        for el in soup.descendants:
            if not isinstance(el, Tag):
                continue
            is_link = el.name == "a" and el.has_attr("href")
            if not (is_link or el.name == "button" or any(
                    r in ("button", "link") for r in _roles(el))):
                continue
            if stop is not None and self.pos(el) > stop:
                break                      # past the blocks: too late to skip
            href = (el.get("href") or "").strip() if is_link else ""
            in_page = (len(href) > 1 and href.startswith("#")
                       and not href.startswith(("#/", "#!")))
            if is_link and not in_page and links >= SKIP_LINK_WINDOW:
                continue                   # cannot be a skip link
            if _excluded_from_tree(el) or _in_dialog(el):
                continue
            if is_link:
                links += 1
            if not (in_page or not is_link):
                continue
            name = static_accname(el, soup, page.ids) or ""
            if not is_link:
                if SKIP_CONTROL_RE.search(name) and _focusable_here(el):
                    return el, el
                continue
            within = links <= SKIP_LINK_WINDOW
            says = (SKIP_TEXT_RE if within or self.nav is not None
                    else SKIP_CONTROL_RE).search(name)
            if not (within or says):
                continue
            target = self.target(el)
            reaches = (target if target is not None and _focusable_here(el)
                       and self.leads_past(el, target) else None)
            if reaches is not None and (says or (
                    within and self._by_position(el, reaches))):
                return el, reaches
            if says and broken is None:
                broken = el
        return broken, None

    # -- what there is to bypass ---------------------------------------------
    def content_heading(self) -> Tag | None:
        if not hasattr(self, "_heading"):
            self._heading = self._content_heading()
        return self._heading

    def _block_roots(self) -> list:
        """The page header, the navigations that lead the page, and a block
        beside the content that holds either (a sidebar with the logo and
        the menu)."""
        roots = [*self.lead, *self.banners]
        for b in list(roots):
            holder = next((p for p in b.parents if isinstance(p, Tag)
                           and p.parent is not None and _beside(p)), None)
            if holder is not None:
                roots.append(holder)
        return roots

    def block_focus(self, skip: Tag | None, limit: int) -> int:
        """Links and controls in the page header and the navigations that
        lead the page, other than the skip link, counted up to `limit`."""
        seen: set = set()
        for root in self._block_roots():
            for el in (root, *root.descendants):
                if (isinstance(el, Tag) and el is not skip
                        and id(el) not in seen and _focusable_here(el)
                        and not _excluded_from_tree(el)
                        and not _in_dialog(el)):
                    seen.add(id(el))
                    if len(seen) >= limit:
                        return len(seen)
        return len(seen)

    def collapsible(self, skip: Tag | None) -> Tag | None:
        """SCR28 (ACT 3e12e1, one of the ways past a block cf77f2 takes): a
        control that expands and collapses each navigation that leads the
        page. The first such control, or None. It is focusable, carries
        aria-expanded, comes before what it collapses, and names in
        aria-controls an element outside which it lies (not the page's
        <html> or <body>) that holds every link and control of the
        navigation but itself: the navigation, an element around it, or
        one inside it. The page header and the blocks beside the content
        may hold one more link or control outside what is collapsed, not
        a block of two (L72-13). Markup cannot show that the control
        collapses anything, so it makes a missing skip link a review, not
        a pass."""
        if not self.lead:
            return None
        page = self.page
        toggles = [t for t in page.soup.find_all(attrs={"aria-controls": True})
                   if t.has_attr("aria-expanded") and _focusable_here(t)
                   and not _excluded_from_tree(t) and not _inert_content(t)
                   and not _not_shown(t)]
        if not toggles:
            return None
        covered: list = []
        used: list = []
        for nav in self.lead:
            items = [d for d in nav.find_all(True)
                     if _focusable_here(d) and not _excluded_from_tree(d)]
            found = None
            for t in toggles:
                reach = ids_within(page.ids, t)
                for ref in (t.get("aria-controls") or "").split():
                    target = reach.get(ref)
                    if (not isinstance(target, Tag)
                            or target.name in ("html", "body")
                            or self.contains(target, t)
                            or self.pos(t) > self.pos(target)
                            or not (self.contains(target, nav)
                                    or self.contains(nav, target))
                            or not all(self.contains(target, d)
                                       for d in items if d is not t)):
                        continue
                    found = (t, target)
                    break
                if found is not None:
                    break
            if found is None:
                return None
            used.append(found[0])
            covered.append(found[1])
        rest: set = set()
        for root in self._block_roots():
            for el in (root, *root.descendants):
                if (isinstance(el, Tag) and el is not skip
                        and id(el) not in rest and _focusable_here(el)
                        and not _excluded_from_tree(el)
                        and not _in_dialog(el)
                        and not any(el is t for t in used)
                        and not any(self.contains(c, el) for c in covered)):
                    rest.add(id(el))
        if len(rest) >= _BLOCK_MIN_FOCUS:
            return None
        return min(used, key=self.pos)

    def blocks_end(self) -> int:
        """The last position inside the page header and the navigations
        that lead the page (-1 if there are none)."""
        return max((self.end(r) for r in self._block_roots()), default=-1)

    def focus_before(self, el: Tag) -> tuple[int, int]:
        """(links and controls before `el`, how many of them are in the
        page header or the leading navigation). Hidden ones and those in a
        dialog do not count."""
        if self._in_blocks is None:
            self._in_blocks = {id(d) for r in self._block_roots()
                               for d in (r, *r.descendants)}
        total = block = 0
        for prev in el.previous_elements:
            if (isinstance(prev, Tag) and _focusable_here(prev)
                    and not _within(el, prev)
                    and not _excluded_from_tree(prev)
                    and not _in_dialog(prev)):
                total += 1
                block += id(prev) in self._in_blocks
        return total, block

    def late(self, el: Tag) -> str:
        """Why a working bypass at `el` comes too late to spare a keyboard
        user the repeated blocks, or "". Where the markup identifies the
        blocks, only their links and controls count (an off-canvas menu
        hidden by CSS before the skip link is not one); where it does not,
        more than _SKIP_LATE_ANY of any kind do."""
        total, block = self.focus_before(el)
        identified = self.block_focus(el, _BLOCK_MIN_FOCUS) >= _BLOCK_MIN_FOCUS
        if block > _SKIP_LATE_LIMIT or (total > _SKIP_LATE_ANY
                                         and not identified):
            return (f"comes after {total} links or controls ({block} of them "
                    "in the page header and navigation), so a keyboard user "
                    "passes them before reaching it; it bypasses only what "
                    "follows it")
        return ""

    def first_content(self) -> Tag | None:
        """The page's first perceivable content past the repeated blocks:
        the element holding the first text, or the first image, field or
        other embedded content, after the leading navigation, the page
        header and the blocks beside the content that hold them, and outside
        any navigation, banner, search, block beside the content, dialog or
        hidden markup. None if there is none."""
        if not hasattr(self, "_first"):
            soup = self.page.soup
            past = self.blocks_end()
            last, found = -1, None
            stack: list = [(soup, False)]
            while stack and found is None:
                node, in_section = stack.pop()
                if isinstance(node, Tag):
                    if node is not soup:
                        last = self.pos(node)
                        if (_hidden_here(node) or node.name in _TEXTLESS
                                or node.name in ("nav", "search")
                                or (node.name == "input" and (
                                    node.get("type") or "").strip().lower()
                                    == "hidden")
                                or any(r in ("navigation", "banner", "search")
                                       for r in _roles(node))
                                or self.is_banner(node, in_section)
                                or _beside(node, in_section)):
                            last = max(last, self.end(node))
                            continue
                        if last > past and node.name in _EMBEDDED:
                            found = node
                            break
                    child_section = in_section or node.name in _SECTIONING
                    stack.extend((c, child_section)
                                 for c in reversed(node.contents))
                elif (type(node) is NavigableString and node.strip()
                      and last >= past and isinstance(node.parent, Tag)):
                    found = node.parent
            self._first = found
        return self._first

    def content_landmark(self) -> Tag | None:
        """ARIA11 (W3C's ACT rule b40fd1): a named region or form landmark
        the content starts in lets a user jump to the content by landmark.
        Its element, or None.

        The page's first perceivable content past the repeated blocks
        (first_content) must be inside it, and it must start past them: a
        landmark that follows the content (a newsletter form, a consent
        notice after the footer) does not open it, and one that wraps the
        blocks bypasses nothing. It is a region (<section>, role=region) or
        a form with an accessible name; never a search (a search landmark
        around it, a search field inside, or a name that says search), nor
        inside a page header or banner, the page footer, a block beside the
        content or a dialog (Part R2 review: one in a role=banner block, a
        second header, after the footer, or named by an empty element was
        taken)."""
        start = self.first_content()
        if start is None:
            return None
        soup, ids = self.page.soup, self.page.ids
        past = self.blocks_end()
        for el in (start, *start.parents):
            if not isinstance(el, Tag) or el.parent is None \
                    or self.pos(el) <= past:
                return None
            kind = _explicit_role(el) or {"section": "region",
                                          "form": "form"}.get(el.name, "")
            if kind not in ("region", "form") or not _present([el]):
                continue
            # A region or form is named by its author only, never by its
            # content.
            name = static_accname(el, soup, ids, content=False)
            if (not name or _SEARCH_NAME.search(name) or _searchy(el)
                    or _in_footer(el) or _beside_of(el, True)
                    or any(isinstance(p, Tag) and (
                        (p.name == "header" and _page_level(p))
                        or "banner" in _roles(p)) for p in (el, *el.parents))):
                continue
            return el
        return None

    def in_page_nav(self) -> Tag | None:
        """G124: the navigation that leads the page links only to areas of
        this page's content past the repeated blocks (a one-page site's
        menu), so each of its links is a way past them. Its first link,
        or None. No link in it is a toggle (aria-expanded, aria-haspopup, a
        button or tab role, a *toggle attribute, aria-controls naming its
        target) or out of the tab order. At least two of its links lead
        in-page to an element that exists, is not hidden or in a dialog,
        lies after the page header and every leading navigation, and is an
        area of content: a section, article or heading, or one that holds
        a heading, and no navigation or dialog. Every other link is a link
        home (`/`, `#`) or to the top of the page (`#top`, or a target at
        or before the end of the repeated blocks, such as `#page-top` on
        <body>), which goes nowhere else. And the page is a one-page site:
        no link in a leading navigation goes to another page, a link home
        aside; a hash route (#/shop) is another page."""
        if self.nav is None:
            return None
        links = [a for a in self.nav.find_all("a", href=True)
                 if not _excluded_from_tree(a)]
        past = self.blocks_end()
        areas = 0
        for a in links:
            href = (a.get("href") or "").strip()
            if (a.has_attr("aria-expanded") or a.has_attr("aria-haspopup")
                    or any(r in ("button", "tab", "menuitem", "switch")
                           for r in _roles(a))
                    or any("toggle" in k.lower() for k in a.attrs)
                    or not _focusable_here(a)):
                return None
            if _root_path(href):
                continue                          # a link home
            if not (len(href) > 1 and href.startswith("#")
                    and not href.startswith(("#/", "#!"))):
                return None
            target = self.target(a)
            if target is None:
                if href[1:].lower() == "top":
                    continue      # HTML scrolls to the top for #top
                return None
            if ((target.get("id") or None)
                    in (a.get("aria-controls") or "").split()
                    or _in_dialog(target) or _excluded_from_tree(target)):
                return None
            if self.pos(target) <= past:
                continue                          # back up to the top
            if not _content_area(target):
                return None
            areas += 1
        if areas < 2:
            return None
        # Only on a one-page site: no link in a leading navigation goes to
        # another page (a link home aside). A promotion bar of in-page links
        # above a site menu bypasses nothing; a social icon or a call to
        # action in the header is not a menu.
        for nav in self.lead:
            for a in nav.find_all("a", href=True):
                if not _excluded_from_tree(a):
                    href = (a.get("href") or "").strip()
                    if not ((href.startswith("#")
                             and not href.startswith(("#/", "#!")))
                            or _root_path(href)):
                        return None
        return links[0]


def _hidden_here(el: Tag) -> bool:
    """Out of the accessibility tree by its own markup (ancestors are the
    caller's concern). In a rendered run that recorded what the page hides,
    that record decides instead of the `hidden` attribute and the inline
    style, which a stylesheet can override (L25): the element is hidden
    where the record marks it so."""
    if (aria_hidden(el)
            or el.has_attr("inert") or el.name in ("template", "noscript")):
        return True
    page = CURRENT_PAGE.get()
    attr = PROVENANCE_ATTR.get()
    if attr and page is not None and page.hiding_recorded:
        return el.get(view_hidden_attr(attr)) in _CAPTURE_HIDDEN_VALUES
    if el.has_attr("hidden"):
        return True
    # The style attribute's display and visibility as the cascade lets
    # them stand: a rule's !important beats it (R5K-5).
    decls = _inline_style(el.get("style"))
    styles = page.styles() if page is not None else None
    return (decls.get("content-visibility") == "hidden"
            or any(_set_by_attribute(decls, prop) and cascade_decides(
                styles, el, prop) is False
                for prop in ("display", "visibility")))


def _content_area(el: Tag) -> bool:
    """An area of content a G124 link may lead to: a section, article or
    heading, or an element holding a heading; never one holding a
    navigation or a dialog (an off-canvas menu, a search panel)."""
    def blocky(t) -> bool:
        return isinstance(t, Tag) and (
            t.name in ("nav", "dialog") or any(
                r in ("navigation", "dialog", "alertdialog")
                for r in _roles(t)))
    if blocky(el) or el.find(blocky) is not None:
        return False
    return (el.name in ("section", "article", "main") or _is_heading(el)
            or el.find(lambda t: isinstance(t, Tag) and _is_heading(t))
            is not None)


def _opening_heading(page: PageContext, where: _Bypass,
                     skip: Tag | None = None) -> Tag | None:
    """The heading that opens the content (H69), if one does.

    Headings let a user jump past repeated blocks only if one sits at the
    beginning of the content: the first named heading after the banner or
    the navigation, outside the blocks beside the content, with little a
    user would have to pass first — at most three links or controls (a
    breadcrumb trail, "Back to blog", a print button) and a short lead-in of
    text. A heading in a footer or sidebar block, or the site's name set as
    a heading, does not open the content.

    One pass in document order that stops at the first heading or as soon
    as too much precedes it, so deep or long pages stay cheap."""
    soup, ids = page.soup, page.ids
    # Counting starts after the banner or the navigation (or a block beside
    # the content that holds one), or at the top of a page with neither.
    blocks = [*where.banners, *([where.nav] if where.nav is not None else [])]
    counting = not blocks
    first_block = min(map(where.pos, blocks)) if blocks else -1
    text = focus = 0
    stack: list = [(soup, False)]
    while stack:
        node, in_section = stack.pop()
        if isinstance(node, Tag):
            if node is not soup:
                if not counting and where.pos(node) < first_block \
                        and not where.holds_block(node):
                    continue             # wholly before the repeated blocks
                if _hidden_here(node) or node is skip:
                    continue
                if (node is where.nav or where.is_banner(node, in_section)
                        or (_beside(node, in_section)
                            and where.holds_block(node))):
                    counting, text, focus = True, 0, 0
                    continue
                if _beside(node, in_section):
                    continue
                if _is_heading(node):
                    if (counting and not _site_title(node)
                            and static_accname(node, soup, ids)):
                        return node
                    continue
                if counting and _focusable_here(node):
                    focus += 1
                    if focus > _OPENING_FOCUS_LIMIT:
                        return None
            children = node.contents
            if node.name == "details" and not node.has_attr("open"):
                # Closed: its first <summary> is all that is rendered
                # (R5S-2).
                first = _first_summary(node)
                children = [first] if first is not None else []
            child_section = in_section or node.name in _SECTIONING
            stack.extend((c, child_section) for c in reversed(children))
        elif (counting and type(node) is NavigableString
              and node.parent is not None
              and node.parent.name not in _TEXTLESS):
            text += len("".join(node.split()))
            if text > _OPENING_TEXT_LIMIT:
                return None
    return None


def _enough_links(soup: BeautifulSoup, n: int = 15) -> bool:
    """At least n links outside the page footer: a page with no navigation
    element whose links may still form repeated blocks. A footer's links
    come after the content and bypass nothing; a sidebar's may come first."""
    in_footer: dict[int, bool] = {}

    def footer(el: Tag) -> bool:
        chain = []
        node, in_section = el, False
        while isinstance(node, Tag) and node.parent is not None \
                and id(node) not in in_footer:
            chain.append(node)
            node = node.parent
        known = in_footer.get(id(node), False)
        for t in reversed(chain):
            in_section = any(isinstance(p, Tag) and p.name in _SECTIONING
                             for p in t.parents) if not known else True
            known = known or _footer_block(t, in_section)
            in_footer[id(t)] = known
        return known

    count = 0
    for a in soup.find_all("a", href=True):
        if footer(a) or _excluded_from_tree(a) or _in_dialog(a):
            continue
        count += 1
        if count >= n:
            return True
    return False


_UNIDENTIFIED = (
    "; the markup marks no navigation or page header holding two or more "
    "links or controls, so the repeated blocks cannot be told from the "
    "content and this is not established as a failure")


def check_skip_link(page: PageContext) -> RuleResult:
    """2.4.1 — bypass blocks (_bypass_blocks). A finding of this rule is
    about the page's way past its blocks, which is the site's: one that
    rests on a skip link a vendor's script inserted is scored as the site's
    too, as README and the attestation say (R5I-8)."""
    r = _bypass_blocks(page)
    for f in r.findings:
        if f.origin == "third-party":
            f.origin, f.origin_detail = "", ""
            f.message = (f.message.rstrip() + " (The skip link is markup a "
                         "vendor's script inserted; the page's way past its "
                         "blocks is the site's.)")
    return r


def _bypass_blocks(page: PageContext) -> RuleResult:
    """2.4.1 — bypass blocks.

    A skip link is the pled expectation and the consent-decree definition,
    but WCAG accepts other mechanisms: a main landmark (ARIA11), headings
    that open the content (H69), a link to the end of the navigation
    (G123), or a one-page site's navigation that links to its sections
    (G124) let a user jump past repeated blocks. A heading only in the
    header, the navigation or the footer does not, nor does a <main> that
    wraps the navigation. A main landmark, a heading, G124 or a control
    that may collapse the leading navigation (SCR28) stands in for a
    missing or broken skip link, which complaints still plead, so those
    are reviews. So the rule FAILS only when it can establish the
    failure — repeated blocks the markup identifies (a leading navigation
    or page header holding two or more links or controls; a single link is
    not a block), and no skip link, no main landmark and no content
    heading, or a skip link that leads nowhere with nothing else to fall
    back on — and reports everything short of that for review: a page
    whose blocks it cannot identify, and a skip link that comes after most
    of what it skips. Only the page counts, as exposed: content hidden
    behind an open dialog is not evaluated, and the dialog is not the page.
    Whether the skip link becomes visible on focus and moves focus is
    interaction-layer.
    """
    soup = page.soup
    with_role = soup.find_all(attrs={"role": True})
    navs = _present(soup.find_all("nav")
                    + _having_role(with_role, "navigation"))
    applicable = bool(navs) or _enough_links(soup)
    r = RuleResult("bb-skip-link", applicable=applicable)
    if not applicable:
        return r
    mains = _present(soup.find_all("main") + _having_role(with_role, "main"))
    where = _Bypass(page, navs, mains, with_role)
    skip, reaches = where.skip_link()
    if reaches is not None:
        late = where.late(skip)
        if late:
            r.findings.append(_f(
                "bb-skip-link", NEEDS_REVIEW, MODERATE,
                f"The skip link {late}. A skip link that is not among the "
                "first links is pled in complaints; not a WCAG failure on "
                "its own — move it to the start of the page.", skip))
        return r
    established = where.block_focus(skip, _BLOCK_MIN_FOCUS) >= _BLOCK_MIN_FOCUS
    if where.main is not None and not where.wraps:
        fallback = "a main landmark"
    elif _opening_heading(page, where, skip) is not None:
        fallback = "a heading that opens the content"
    elif where.in_page_nav() is not None:
        fallback = ("a one-page site's navigation that links to its "
                    "sections (G124)")
    elif where.content_landmark() is not None:
        fallback = "a landmark the content starts in (ARIA11)"
    elif where.collapsible(skip) is not None:
        fallback = ("a control before the navigation that may expand and "
                    "collapse it (SCR28)")
    else:
        fallback = None
    no_main = ("the main landmark wraps the navigation" if where.wraps
               else "no main landmark")
    if skip is not None:
        href = skip.get("href").strip()
        if where.target(skip) is None:
            frag = urllib.parse.unquote(href[1:])
            shadowed = any(frag in tree for tree in page.ids._trees.values()) \
                if isinstance(page.ids, IdScopes) else False
            lead = (f"Skip link points to '{href}', but the page has no "
                    "element with that id"
                    + (" outside a shadow root, and a fragment does not reach"
                       " into one" if shadowed else ""))
        elif not _focusable_here(skip):
            lead = (f"Skip link points to '{href}', but a negative tabindex "
                    "takes it out of the tab order, so no keyboard user "
                    "reaches it")
        else:
            lead = (f"Skip link points to '{href}', which does not lead "
                    + ("past the navigation" if where.nav is not None
                       else "to the content"))
        if fallback:
            r.findings.append(_f(
                "bb-skip-link", NEEDS_REVIEW, MODERATE,
                f"{lead}; {fallback} can still satisfy 2.4.1. A broken skip "
                "link is pled in complaints; not a WCAG failure on its own — "
                "fix it.", skip))
        elif not established:
            r.findings.append(_f(
                "bb-skip-link", NEEDS_REVIEW, MODERATE,
                f"{lead}, and nothing else bypasses ({no_main}, no heading "
                f"that opens the content){_UNIDENTIFIED}. A broken skip link "
                "is pled in complaints; not a WCAG failure on its own — fix "
                "it.", skip))
        else:
            r.findings.append(_f(
                "bb-skip-link", FAIL, SERIOUS,
                f"{lead}, and nothing else bypasses the repeated blocks "
                f"({no_main}, no heading that opens the content).", skip))
        return r
    place = ("before the navigation" if where.nav is not None
             else "among the first links")
    if fallback:
        r.findings.append(_f(
            "bb-skip-link", NEEDS_REVIEW, MODERATE,
            f"No skip link found {place}; {fallback} can satisfy 2.4.1. A "
            "missing skip link is pled in complaints; not a WCAG failure on "
            "its own — add one."))
    elif not established:
        r.findings.append(_f(
            "bb-skip-link", NEEDS_REVIEW, MODERATE,
            f"No skip link found {place}, {no_main} and no heading that "
            f"opens the content{_UNIDENTIFIED}. A missing skip link is pled "
            "in complaints; not a WCAG failure on its own — add one if the "
            "page repeats blocks."))
    elif where.wraps:
        r.findings.append(_f(
            "bb-skip-link", FAIL, SERIOUS,
            f"No mechanism to bypass repeated blocks: no skip link found "
            f"{place}, no heading that opens the content, and the main "
            "landmark wraps the navigation, so it bypasses nothing."))
    else:
        r.findings.append(_f(
            "bb-skip-link", FAIL, SERIOUS,
            f"No mechanism to bypass repeated blocks: no skip link found "
            f"{place}, no main landmark and no heading that opens the "
            "content."))
    return r


def check_viewport_zoom(page: PageContext) -> RuleResult:
    """1.4.4 — user-scalable=no / maximum-scale<2 blocks zoom (pled barrier)."""
    r = RuleResult("bb-viewport-zoom", applicable=False)
    meta = next((m for m in page.soup.find_all(
        "meta", attrs={"name": re.compile(r"^viewport$", re.I)})
        if not _inert_content(m)), None)
    if meta is None:
        return r
    r.applicable = True
    content = (meta.get("content") or "").lower().replace(" ", "")
    # One element, one finding: a meta that both disables pinch-zoom and
    # caps it is one barrier, as axe-core counts it (the R5 field sweep
    # found it counted twice).
    why = []
    if "user-scalable=no" in content or "user-scalable=0" in content:
        why.append("disables pinch-zoom (user-scalable=no)")
    m = re.search(r"maximum-scale=([0-9.]+|yes|no|device-width|device-height)",
                  content)
    if m:
        # The viewport meta's keyword values stand for numbers: yes is 1
        # (ACT rule b4f0c3, Failed Example 4: maximum-scale=yes caps zoom at
        # 100%), no is below 1, device-width and device-height are 10 (the
        # CSS Device Adaptation drafts' translation). Other words are left
        # alone.
        value = _VIEWPORT_KEYWORDS.get(m.group(1), m.group(1))
        try:
            if float(value) < 2.0:
                why.append(f"caps zoom below 200% (maximum-scale={m.group(1)})")
        except ValueError:
            pass
    if why:
        r.findings.append(_f("bb-viewport-zoom", FAIL, SERIOUS,
                             "viewport meta " + " and ".join(why) + ".",
                             meta))
    return r


#: What the viewport meta's keyword values mean as numbers.
_VIEWPORT_KEYWORDS = {"yes": "1", "no": "0", "device-width": "10",
                      "device-height": "10"}


#: The global states and properties (aria-hidden aside) that make a
#: browser ignore role="none" or "presentation" on any element, as
#: focusability does (presentational role conflict resolution), as
#: Chromium 141 has them: ARIA 1.3's, with aria-description and the two
#: braille properties, and without the deprecated aria-dropeffect and
#: aria-grabbed (R5I-3).
_GLOBAL_ARIA = frozenset((
    "aria-atomic", "aria-braillelabel", "aria-brailleroledescription",
    "aria-busy", "aria-controls", "aria-current", "aria-describedby",
    "aria-description", "aria-details", "aria-flowto", "aria-keyshortcuts",
    "aria-label", "aria-labelledby", "aria-labeledby", "aria-live",
    "aria-owns", "aria-relevant", "aria-roledescription"))


def _presentation_ignored(el: Tag) -> bool:
    """Would a browser ignore role="none"/"presentation" on `el`? Yes when
    it can take focus (tabindex="-1" included) or carries a global ARIA
    attribute."""
    return ((_tabindex(el) is not None and not _disabled(el))
            or _focusable_here(el)
            or any(a in _GLOBAL_ARIA for a in el.attrs))


def _role_of(el: Tag) -> str:
    """Explicit role (first recognized token) or the implicit role of the
    native elements the name rules care about; "" when neither applies.
    none/presentation is ignored where browsers ignore it (ARIA's
    presentational role conflict resolution, _presentation_ignored):
    `<a href role="presentation">` is still a link."""
    for token in (el.get("role") or "").lower().split():
        if token in ROLES:
            if token in ("none", "presentation") and _presentation_ignored(el):
                break
            return token
    name = el.name
    if name == "a":
        return "link" if _link_href(el) else ""
    # HTML's elements have these roles; an SVG or MathML element of the
    # same name has none (R5S-4).
    if name in ("area", "button", "input", "select", "textarea", "img") \
            and namespace_of(el) != "html":
        return ""
    if name == "area":
        return "link" if el.has_attr("href") else ""
    if name == "button":
        return "button"
    if name == "input":
        itype = (el.get("type") or "text").lower()
        return {"hidden": "", "submit": "button", "reset": "button",
                "button": "button", "image": "button", "checkbox": "checkbox",
                "radio": "radio", "range": "slider", "number": "spinbutton",
                "search": "searchbox"}.get(itype, "textbox")
    if name == "select":
        return "combobox"
    if name == "textarea":
        return "textbox"
    if name == "img":
        return "img"
    return ""


def _needs_name(el: Tag) -> bool:
    """A user-interface component WCAG 4.1.2 requires to be named."""
    return (_role_of(el) in NAME_REQUIRED_ROLES
            or el.name in ("iframe", "summary", "object"))


def _name_rule(el: Tag) -> str:
    """The rule that fails `el` when it has no accessible name ("" if
    none does)."""
    if el.name in ("iframe", "summary", "object", "svg"):
        return {"iframe": "bb-iframe-title", "summary": "bb-summary-name",
                "object": "bb-object-alt", "svg": "bb-svg-name"}[el.name]
    if el.name in ("img", "area") or (
            el.name == "input" and (el.get("type") or "").lower() == "image"):
        return "bb-img-alt"
    role = _role_of(el)
    if role in IMG_ROLES:
        return "bb-role-img-name"
    if role in CONTROL_NAME_ROLES:
        return "bb-widget-name"
    if role in FORM_FIELD_ROLES:
        return "bb-control-label"
    return {"link": "bb-link-name", "button": "bb-button-name"}.get(role, "")


def check_aria_ref(page: PageContext) -> RuleResult:
    """Broken ID references ('broken ARIA'), for review: never a FAIL.

    A reference that points nowhere matters most when it costs the element
    its accessible name: every aria-labelledby id is missing, the element is
    a component that must be named, and nothing else names it. Then the
    element's own name rule fails it (_name_rule), under the criterion that
    rule cites, and this rule reports the broken reference beside it at
    moderate impact: one defect, one failure (Part R2 review, as QR-13 made
    it for the name rules). Any other reference that points nowhere leaves
    the element's name, role and value intact, and is a minor review.
    (shadcn/ui's FormControl, for one, always sets aria-describedby to a
    description id that renders only when a description exists.) W3C's
    only ACT rule on missing ID references, in6db8, is deprecated and was
    mapped to ARIA, not to WCAG."""
    r = RuleResult("bb-aria-ref", applicable=False)
    for attr in ID_REF_ATTRS:
        for el in page.soup.find_all(attrs={attr: True}):
            if _inert_content(el):
                continue        # not in the document (N16)
            if attr == "aria-labeledby" and el.has_attr("aria-labelledby"):
                continue        # not read (accname.labelledby_attr)
            r.applicable = True
            tokens = (el.get(attr) or "").split()
            # An id reference reaches only the referring element's own tree
            # (the document, or its shadow root): OR-2.
            reach = ids_within(page.ids, el)
            missing = [t for t in tokens if t not in reach]
            if not missing:
                continue
            ids_text = ", ".join(missing)
            if (attr in _NAMING_REFS and len(missing) == len(tokens)
                    and _needs_name(el) and not _out_of_tree(el)
                    and not static_accname(el, page.soup, page.ids,
                                           use_labelledby=False)):
                rule = _name_rule(el)
                where = (" in a browser run" if rule in (
                    "bb-summary-name", "bb-object-alt") else "")
                r.findings.append(_f(
                    "bb-aria-ref", NEEDS_REVIEW, MODERATE,
                    f"{attr} references only missing id(s) "
                    f"{ids_text}, and nothing else names this element: it "
                    "has no accessible name"
                    + (f", which {rule} decides{where}." if rule else ".")
                    + " Point the reference at an element that exists, or "
                      "name the element another way.", el))
            elif attr == "aria-controls" and (
                    (el.get("aria-expanded") or "").lower() == "false"
                    or el.has_attr("aria-haspopup")):
                # A collapsed disclosure may render its panel on open; the
                # reference is only checkable in that state (axe: incomplete).
                r.findings.append(_f(
                    "bb-aria-ref", NEEDS_REVIEW, MINOR,
                    f"aria-controls references missing id(s) {ids_text} "
                    "while collapsed — verify the panel exists when "
                    "expanded.", el))
            else:
                r.findings.append(_f(
                    "bb-aria-ref", NEEDS_REVIEW, MINOR,
                    f"{attr} references missing id(s): {ids_text}. The "
                    "element's name, role and value do not depend on it; "
                    "confirm nothing the user needs was meant to be "
                    "referenced.", el))
    for lab in page.soup.find_all("label", attrs={"for": True}):
        if _inert_content(lab):
            continue
        r.applicable = True
        if lab.get("for") not in ids_within(page.ids, lab):
            # The control it was meant for, if it exists unlabeled, fails
            # bb-control-label; failing here as well double-counted one defect.
            r.findings.append(_f("bb-aria-ref", NEEDS_REVIEW, MINOR,
                                 f"label for=\"{lab.get('for')}\" matches no "
                                 "element id.", lab))
    return r


def _aria_hidden_true(el: Tag) -> bool:
    """aria-hidden="true", where browsers read it: not on the document's
    <html> or <body> (accname.aria_hidden)."""
    return aria_hidden(el)


#: Closing classes whose stylesheet hides with visibility:hidden, which a
#: descendant's visibility:visible undoes (Bootstrap 5's offcanvas,
#: Bootstrap's and Tailwind's invisible).
_VISIBILITY_CLASSES = frozenset({"invisible", "offcanvas"})


def _file_hider(node: Tag) -> str:
    """"display" or "visibility" when, as far as a file run can tell, the
    page hides `node`: a framework class says it is closed
    (_closed_by_class), or a rule in the page's own <style> hides it;
    else ""."""
    closed = _closed_by_class(node)
    if closed:
        return "display" if closed - _VISIBILITY_CLASSES else "visibility"
    page = CURRENT_PAGE.get()
    return page.styles().hides(node) if page is not None else ""


def _reshows(node: Tag) -> bool | None:
    """visibility:visible on `node` (True): Bootstrap's or Tailwind's
    `visible` class, its inline style, or a rule in the page's own
    <style>; None where only a visibility known later (var()) may show it
    or stands as high as what shows it, or where a var()'s fallback stands
    level with a hide (style.visibility_later), which a file run cannot
    settle (R6B-8, R6D-1, R6N-1, R6P-2, R6T-1); else False."""
    page = CURRENT_PAGE.get()
    styles = page.styles() if page is not None else None
    if visibility_later(styles, node):
        # What the run cannot order: before the shortcuts below, as a
        # var() may stand above them (R6P-2, R6T-1, R6V-2).
        return None
    if "visible" in _class_names(node):
        return True
    if _inline_style(node.get("style")).get("visibility") == "visible":
        return True
    if styles is None:
        return False
    if styles.shows_visibility(node):
        return True
    return None if styles.shows_visibility(node, later_shows=True) else False


#: _file_closer's answer where a display or a visibility only known later
#: (var()) decides whether content is shown (R6D-1, R6F-6, R6H-3).
_MAY_BE_SHOWN = object()


def _file_closer(el: Tag):
    """The nearest element, `el` or an ancestor up to <body>, that a file
    run can tell the page hides (_file_hider); visibility:visible below a
    visibility:hidden one shows it again. Where the nearest visibility set,
    `el`'s own or an ancestor's, or the display set on it or one above it,
    is only known later (var(): style.display_later), it may be either
    (_MAY_BE_SHOWN: R6D-1, R6F-6, R6H-3), unless what hides it stops
    rendering."""
    page = CURRENT_PAGE.get()
    styles = page.styles() if page is not None else None
    reshown = False         # the nearest visibility set: shown, or None
    later = False           # a display only known later, on it or above
    node = el
    while isinstance(node, Tag) and node.name not in ("body", "html"):
        kind = _file_hider(node)
        if kind == "display" or (kind == "visibility" and reshown is False):
            return node
        if reshown is False:
            again = _reshows(node)
            if again is True:
                reshown = True
            elif again is None:
                reshown = None
        later = later or display_later(styles, node)
        node = node.parent
    return _MAY_BE_SHOWN if reshown is None or later else None


def _never_rendered(el: Tag) -> bool:
    """Does the capture's record say that `el` is never rendered: it or an
    ancestor is a part of a drawing with no box ("unboxed"), or one
    Chromium boxes but never paints, but a <g> with display:none, which a
    script may show (<defs>, <symbol>, a MathML part: "unrendered"),
    invisible or not (R6E-3, R6E-5)?"""
    name = view_hidden_attr(PROVENANCE_ATTR.get())
    for node in (el, *el.parents):
        if not isinstance(node, Tag):
            break
        mark = node.get(name)
        if mark in ("unboxed", "unboxed-visibility") or (
                mark in ("unrendered", "unrendered-visibility")
                and not ((node.name or "").lower() == "g"
                         and namespace_of(node) == "svg")):
            return True
    return False


def check_aria_hidden_focus(page: PageContext) -> RuleResult:
    """4.1.2 / 1.3.1 — aria-hidden content must not contain focusable UI
    (ACT 6cfa84: content in sequential focus navigation).

    Content that is not rendered cannot take focus. Markup can show that
    (`hidden`, an inline display:none, a closed <dialog> or popover, each
    unless an author style shows it), and a rendered capture records what
    the stylesheets hide (model.hidden_attr). Each focusable descendant is
    placed by what hides it now:
      * nothing: it takes focus inside aria-hidden content, a FAIL;
      * the aria-hidden container itself: a closed Bootstrap or Flowbite
        modal, whose framework removes aria-hidden as it shows it. A
        rendered run reports nothing; a run that cannot read the linked
        stylesheets (a file, server HTML) reviews it, when the container's
        own classes say it is closed or a rule in the page's own <style>
        hides it (N19);
      * a container around or inside the aria-hidden one (a closed menu,
        tab or panel): it becomes focusable when that opens, while
        aria-hidden may stay, so it is reviewed.
    Each offender is reported once, under its outermost aria-hidden
    container."""
    r = RuleResult("bb-aria-hidden-focus", applicable=False)
    recorded = _hiding_recorded(page)
    for el in page.soup.find_all(attrs={"aria-hidden": True}):
        if not _aria_hidden_true(el) or _inert_content(el):
            continue
        if any(isinstance(p, Tag) and _aria_hidden_true(p) for p in el.parents):
            continue        # inside another aria-hidden container, which reports
        r.applicable = True
        shown, together, around, inside, maybe = [], [], [], [], []
        for d in (el, *el.find_all(True)):
            if not _is_focusable(d):
                continue
            hider = _capture_hiding(d) if recorded else _file_closer(d)
            if recorded and hider is not None and _never_rendered(d):
                continue        # it never takes focus
            if hider is None:
                shown.append(d)
            elif hider is _MAY_BE_SHOWN:
                maybe.append(d)
            elif hider is el:
                together.append(d)
            elif any(p is el for p in hider.parents):
                inside.append(d)
            else:
                around.append(d)
        if shown:
            r.findings.append(_f("bb-aria-hidden-focus", FAIL, SERIOUS,
                                 "aria-hidden=\"true\" element is/contains focusable "
                                 "content — keyboard users reach UI that assistive "
                                 "tech cannot perceive.", el))
        elif maybe:
            r.findings.append(_f(
                "bb-aria-hidden-focus", NEEDS_REVIEW, MODERATE,
                "aria-hidden=\"true\" element contains focusable content "
                "whose display or visibility a custom property (var()) "
                "decides, which this run cannot settle: it reads neither "
                "what a custom property holds nor which of two rules that "
                "set it wins. If it is shown, keyboard users reach content "
                "assistive technology cannot perceive: check that it stays "
                "hidden while it is aria-hidden.", el))
        elif around or inside:
            where = "around" if around else "inside"
            when = ("when the page was captured" if recorded
                    else "as its classes or the page's own <style> say")
            r.findings.append(_f(
                "bb-aria-hidden-focus", NEEDS_REVIEW, MODERATE,
                f"aria-hidden=\"true\" element contains focusable content "
                f"that a container {where} it kept hidden {when} (a closed "
                "menu, tab or panel). When that container opens, keyboard "
                "users reach content assistive technology cannot perceive, "
                "unless the page removes aria-hidden too: check that state.",
                el))
        elif together and not recorded:
            closed = _closed_by_class(el)
            why = (f"its class \"{sorted(closed)[0]}\" is one a framework "
                   "stylesheet hides until a script opens it (a closed modal "
                   "or menu)" if closed
                   else "its style attribute or a rule in the page's own "
                   "<style> hides it")
            r.findings.append(_f(
                "bb-aria-hidden-focus", NEEDS_REVIEW, MODERATE,
                f"aria-hidden=\"true\" element contains focusable content, "
                f"but {why}, and hidden content cannot take focus. This run "
                "cannot read the page's linked stylesheets: confirm the "
                "content is hidden whenever it is aria-hidden, or run --url, "
                "which records what the page hides.", el))
    return r


def check_positive_tabindex(page: PageContext) -> RuleResult:
    """2.4.3 — positive tabindex overrides the focus order. WCAG fails it
    only when the resulting order loses meaning or operability (F44), which
    markup alone cannot show, and axe-core classes it as a best practice:
    basis `best-practice`, never FAIL (the engine enforces it)."""
    r = RuleResult("bb-positive-tabindex", applicable=False)
    for el in page.soup.find_all(attrs={"tabindex": True}):
        r.applicable = True
        try:
            if (_tabindex(el) or 0) > 0:
                r.findings.append(_f(
                    "bb-positive-tabindex", NEEDS_REVIEW, SERIOUS,
                    f"tabindex={el.get('tabindex')} overrides the natural "
                    "focus order; check that the order still makes sense "
                    "(F44), and prefer DOM order with tabindex 0 or -1.", el))
        except (TypeError, ValueError):
            continue
    return r


#: An inline handler that stops something: a marquee's `this.stop()`, a
#: Pause button's `document.getElementById('m').stop()`.
_STOPS_RE = re.compile(r"\.\s*stop\s*\(", re.I)


def _page_stops_something(page: PageContext) -> bool:
    """Does an inline event handler on the page (an on… attribute) call
    stop()? It may be the control that pauses a marquee."""
    for el in page.soup.find_all(True):
        for name, value in el.attrs.items():
            if (name.lower().startswith("on") and isinstance(value, str)
                    and _STOPS_RE.search(value) and not _inert_content(el)):
                return True
    return False


def check_marquee_blink(page: PageContext) -> RuleResult:
    """2.2.2 (heuristic) — moving content without pause.

    A <marquee> that moves is a probable failure: W3C failure F16 names
    scrolling content with no mechanism to pause and restart it, and markup
    cannot show that none exists (Part R2 review). One that does not render
    (hidden by markup, or recorded as hidden by a rendered capture) or does
    not move (scrollamount="0") moves nothing, and is not checked. One that
    may stop by itself (behavior="slide", a loop count) or that a handler
    on the page stops (an on… attribute calling stop()) is a review: 2.2.2
    fails only moving content that lasts more than five seconds with no way
    to pause, stop or hide it. No current browser makes <blink> blink, and
    W3C made its failure (F47) obsolete: it moves nothing, so it is
    reported for review as obsolete markup."""
    r = RuleResult("bb-marquee-blink", applicable=False)
    stops = None
    for el in page.soup.find_all(["marquee", "blink"]):
        if _inert_content(el):
            continue
        if el.name == "blink":
            r.applicable = True
            r.findings.append(_f("bb-marquee-blink", NEEDS_REVIEW, MINOR,
                                 "<blink> is obsolete: no current browser "
                                 "makes it blink, so it is plain text; "
                                 "remove it.", el))
            continue
        if _display_none(el) or _capture_hidden(el) \
                or _html_int(el.get("scrollamount")) == 0:
            continue
        r.applicable = True
        loops = _html_int(el.get("loop"))
        if (el.get("behavior") or "").strip().lower() == "slide":
            why = ('behavior="slide" stops it once its content has slid '
                   'in')
        elif loops is not None and loops > 0:
            why = f'loop="{loops}" stops it after {loops} ' + (
                "passes" if loops > 1 else "pass")
        else:
            if stops is None:
                stops = _page_stops_something(page)
            why = ("a handler on this page calls stop(), which may be a "
                   "control that pauses it") if stops else ""
        if why:
            r.findings.append(_f(
                "bb-marquee-blink", NEEDS_REVIEW, MODERATE,
                f"<marquee> moves its content, but {why}. It fails 2.2.2 "
                "if it moves for more than five seconds with no way to "
                "pause, stop or hide it. A marquee is pled in complaints "
                "whether or not it stops.", el))
        else:
            r.findings.append(_f(
                "bb-marquee-blink", FAIL, SERIOUS,
                "<marquee> moves its content with no pause, stop or hide "
                "control in the markup: probably a failure of 2.2.2 (as W3C "
                "failure F16 describes).", el))
    return r


# --------------------------------------------------------------------------
# Tier 2
# --------------------------------------------------------------------------

def check_aria_role(page: PageContext) -> RuleResult:
    """4.1.2 — role values must exist in ARIA (misapplied ARIA lint). The
    ACT rule says a valid role value is not itself a conformance
    requirement: basis `best-practice`, never FAIL."""
    r = RuleResult("bb-aria-role", applicable=False)
    for el in page.soup.find_all(attrs={"role": True}):
        r.applicable = True
        tokens = (el.get("role") or "").split()
        if _roleless_control(el) and not _excluded_from_tree(el):
            continue             # bb-control-role fails it: one finding
        if tokens and not any(t.lower() in ROLES for t in tokens):
            r.findings.append(_f(
                "bb-aria-role", NEEDS_REVIEW, MODERATE,
                f"Unknown ARIA role \"{tokens[0]}\": assistive technology "
                "ignores it. If the element is a control, it needs a valid "
                "role (4.1.2).", el))
    return r


def check_aria_attr(page: PageContext) -> RuleResult:
    """4.1.2 — aria-* attributes must exist in ARIA."""
    r = RuleResult("bb-aria-attr", applicable=False)
    for el in page.soup.find_all(True):
        bad = [a for a in el.attrs if a.startswith("aria-") and a not in ARIA_ATTRS]
        if any(a.startswith("aria-") for a in el.attrs):
            r.applicable = True
        for a in bad:
            if a == "aria-labeledby" and not el.has_attr("aria-labelledby"):
                # Chromium 141 reads it as aria-labelledby; ARIA does not
                # define it, and other browsers may not (R5K-15).
                r.findings.append(_f(
                    "bb-aria-attr", NEEDS_REVIEW, MODERATE,
                    "\"aria-labeledby\" is not an ARIA attribute: Chromium "
                    "reads it as aria-labelledby, which ARIA defines and "
                    "other browsers may need. Spell it aria-labelledby.",
                    el))
                continue
            r.findings.append(_f(
                "bb-aria-attr", NEEDS_REVIEW, MODERATE,
                f"Unknown ARIA attribute \"{a}\" (typo?): it has no effect.",
                el))
    return r


#: The references whose target names an element: a duplicated id one of
#: them names can name a control from the wrong element (L72-3).
#: aria-labeledby is read as aria-labelledby where that is absent, as
#: Chromium 141 reads it (R5K-15).
_NAMING_REFS = ("aria-labelledby", "aria-labeledby")
#: The other id references: a relationship, not a name. HTML's own too:
#: the popover or command a button invokes, an input's datalist, a form
#: control's form owner, what an <output> is the result of (R5G-8).
_RELATION_REFS = tuple(a for a in ID_REF_ATTRS if a not in _NAMING_REFS) \
    + ("headers", "popovertarget", "commandfor", "list", "form")
#: The SVG elements whose href, or xlink:href, names an element to draw.
_SVG_HREF_ELEMENTS = frozenset(("use", "textpath", "feimage", "mpath",
                                "tref"))


def check_duplicate_id(page: PageContext) -> RuleResult:
    """4.1.2 / 1.3.1 (heuristic) — a duplicated id that a name depends on.

    4.1.1 Parsing is always satisfied for HTML (WCAG 2.1 erratum, 18 April
    2023) and gone from WCAG 2.2, so a duplicated id fails nothing on its
    own (L72-2, L72-7). References resolve to the first element with the
    id in their tree, so:
      * one a <label for> or aria-labelledby names: the control may be
        named from the wrong element, or left unnamed: a FAIL, a probable
        failure (4.1.2, and 1.3.1 for a label's relationship);
      * one another reference names (aria-describedby, aria-controls,
        aria-owns, aria-activedescendant, aria-errormessage, aria-details,
        aria-flowto, a cell's headers): the relationship may reach the
        wrong element, a review (L72-3, L72-14);
      * one only an in-page link names, or nothing: a minor review; a link
        goes to the first.
    Applies to pages with ids (H6-10). Ids inside <template> or <noscript>
    are not in the document, and each tree has ids of its own (OR-2)."""
    ids = page.ids if isinstance(page.ids, IdScopes) else IdScopes(page.soup)
    key = ids.key
    counts: dict[tuple, int] = {}
    first: dict[tuple, Tag] = {}
    for el in page.soup.find_all(attrs={"id": True}):
        if _inert_content(el):
            continue
        k = (key(el), el.get("id"))
        counts[k] = counts.get(k, 0) + 1
        first.setdefault(k, el)
    r = RuleResult("bb-duplicate-id", applicable=bool(counts))
    dups = {k for k, n in counts.items() if n > 1}
    if not dups:
        return r
    naming: set[tuple] = set()
    relating: set[tuple] = set()
    linked: set[tuple] = set()
    for lab in page.soup.find_all("label", attrs={"for": True}):
        if not _inert_content(lab):
            naming.add((key(lab), lab.get("for")))
    for attrs, into in ((_NAMING_REFS, naming), (_RELATION_REFS, relating)):
        for attr in attrs:
            for el in page.soup.find_all(attrs={attr: True}):
                if _inert_content(el) or (attr == "aria-labeledby"
                                          and el.has_attr("aria-labelledby")):
                    continue
                value = el.get(attr)
                # The parser splits some attributes (a cell's headers) into
                # a list of tokens already.
                tokens = (value if isinstance(value, list)
                          else (value or "").split())
                into.update((key(el), t) for t in tokens)
    for out in page.soup.find_all("output", attrs={"for": True}):
        if not _inert_content(out):
            value = out.get("for")
            # The parser may split it into tokens already (R5I-11).
            relating.update((key(out), t) for t in (
                value if isinstance(value, list) else str(value or "")
                .split()))
    for a in page.soup.select('a[href^="#"]'):
        # A fragment scrolls the document: it reaches the document's ids.
        linked.add((0, urllib.parse.unquote((a.get("href") or "#")[1:])))
    drawn: set[tuple] = set()
    wanted = {k[1] for k in dups}
    for el in page.soup.find_all(True):
        refs = [u[1:] for value in el.attrs.values()
                if isinstance(value, str) and "url(" in value.lower()
                for u in css_urls(value) if u.startswith("#")]
        if (el.name or "").lower() in _SVG_HREF_ELEMENTS:
            refs += [v[1:] for v in (el.get("href"), el.get("xlink:href"))
                     if isinstance(v, str) and v.startswith("#")]
        if el.name == "style":
            # A rule's fill: url(#g) reaches an id of the style's own tree;
            # one in a comment or another string reaches none (R5K-13).
            refs += [u[1:] for u in css_urls(el.get_text())
                     if u.startswith("#")]
        refs = [t for t in refs if t in wanted]
        if refs and not _inert_content(el):
            drawn.update((key(el), t) for t in refs)
    order = {id(el): n for n, el in enumerate(page.soup.find_all(True))}
    for k in sorted(dups, key=lambda k: (k[1], order.get(id(first[k]), 0))):
        i, el = k[1], first.get(k)
        if k in naming:
            r.findings.append(_f(
                "bb-duplicate-id", FAIL, SERIOUS,
                f"id \"{i}\" is duplicated, and a <label for> or "
                "aria-labelledby (or aria-labeledby, which Chromium reads "
                "so) names it: the reference reaches only the first element "
                "with the id, so a control may be named from the wrong "
                "element, or left unnamed.", el))
        elif k in relating:
            r.findings.append(_f(
                "bb-duplicate-id", NEEDS_REVIEW, MODERATE,
                f"id \"{i}\" is duplicated, and an id reference (such as "
                "aria-describedby, aria-controls, a cell's headers, a "
                "popovertarget or an input's list) names it: it reaches only "
                "the first element with the id. Check that this is the "
                "element meant.", el))
        else:
            r.findings.append(_f(
                "bb-duplicate-id", NEEDS_REVIEW, MINOR,
                f"id \"{i}\" is duplicated"
                + (" (an in-page link to it goes to the first)."
                   if k in linked else
                   " (a drawing's reference to it, such as fill=\"url(#…)\" "
                   "or <use href>, reaches the first)." if k in drawn else
                   " (no label, ARIA, headers, popover, form or drawing "
                   "reference names it)."), el))
    return r


def _heading_level(el: Tag) -> int | None:
    """The level a browser exposes for a heading, or None for anything
    else: role="heading" (2 by default), or h1-h6 that no other role
    overrides (`<h2 role="tab">` is a tab). aria-level sets the level as
    Chromium 141 reads it: 1-9 is the level; above 9 is ignored (the
    tag's own level, or 2); a value that is not a positive integer it can
    read (`abc`, `0`, `-1`, one past 32 bits) makes level 1."""
    explicit = ""
    for token in (el.get("role") or "").lower().split():
        if token in ROLES:
            explicit = token
            break
    native = bool(_HEADING_RE.match(el.name or ""))
    if explicit and explicit != "heading":
        if not (explicit in ("none", "presentation")
                and _presentation_ignored(el)):
            return None
        explicit = ""
    if explicit != "heading" and not native:
        return None
    raw = el.get("aria-level")
    if isinstance(raw, str) and raw:
        level = _html_int(raw)
        if level is None or level < 1:
            return 1
        if level <= 9:
            return level
    return int(el.name[1]) if native else 2


def check_heading_structure(page: PageContext) -> RuleResult:
    """1.3.1 / 2.4.6 — empty headings, h1 absence and level skips. The ACT
    rules do not make any of them a conformance requirement on its own:
    basis `best-practice`, never FAIL. An empty heading is reported at
    serious impact, which `--strict` gates; the others at minor."""
    r = RuleResult("bb-heading-structure", applicable=False)
    # One pass in document order. Sorting by source line put every
    # role="heading" after every h1-h6 on one-line (minified) HTML.
    headings: list[tuple[int, Tag]] = []
    for el in page.soup.find_all(True):
        lvl = _heading_level(el)
        if lvl is not None:
            headings.append((lvl, el))
    if not headings:
        return r
    r.applicable = True
    for lvl, el in headings:
        if _excluded_from_tree(el):
            continue
        # The heading's accessible name, not just its text: aria-label,
        # aria-labelledby and labelled children (an svg with aria-label)
        # all name a heading.
        if not static_accname(el, page.soup, page.ids):
            r.findings.append(_f("bb-heading-structure", NEEDS_REVIEW,
                                 SERIOUS, "Empty heading.", el))
    # The outline is what the page shows: headings in a closed or
    # aria-hidden modal neither stand in for an h1 nor make a skip. With a
    # modal open over the page, the dialog is what the page exposes and the
    # page's outline is not judged (as bb-skip-link does).
    if _modal_open(page):
        return r
    shown = [(lvl, el) for lvl, el in headings
             if not _excluded_from_tree(el) and not _capture_hidden(el)]
    if not any(lvl == 1 for lvl, _ in shown):
        r.findings.append(_f("bb-heading-structure", NEEDS_REVIEW, MINOR,
                             "No h1 on the page."))
    prev = None
    for lvl, el in shown:
        if prev is not None and lvl > prev + 1:
            r.findings.append(_f("bb-heading-structure", NEEDS_REVIEW, MINOR,
                                 f"Heading level skips from h{prev} to h{lvl}.", el))
        prev = lvl
    return r


def _table_rows(table: Tag) -> list:
    """The table's own rows (<tr>), each with its own cells (<td>, <th>):
    not those of a table inside one of its cells (R5G-9)."""
    rows = []
    stack = list(reversed(list(table.children)))
    while stack:
        node = stack.pop()
        if not isinstance(node, Tag) or node.name == "table":
            continue
        if node.name == "tr":
            rows.append((node, node.find_all(["td", "th"], recursive=False)))
            continue
        stack.extend(reversed(list(node.children)))
    return rows


def check_table_headers(page: PageContext) -> RuleResult:
    """1.3.1 (heuristic) — data tables need header cells: <th>, a cell
    whose role is columnheader or rowheader (as W3C failure F91 allows:
    L72-12), or scope or headers attributes. Only the table's own cells
    count: a header role on something inside a cell, or a nested table's
    header, is none of this table's (R5G-9)."""
    r = RuleResult("bb-table-headers", applicable=False)
    for table in page.soup.find_all("table"):
        roles = (table.get("role") or "").lower().split()
        if "presentation" in roles or "none" in roles:
            continue
        if _excluded_from_tree(table):
            continue
        rows = _table_rows(table)
        if len(rows) < 2:
            continue
        max_cells = max((len(cells) for _row, cells in rows), default=0)
        if max_cells < 2:
            continue
        r.applicable = True
        cells = [c for _row, row_cells in rows for c in row_cells]
        has_th = any(c.name == "th" for c in cells)
        has_scope = any(c.has_attr("scope") for c in cells)
        has_headers = any(c.has_attr("headers") for c in cells)
        has_role = any(_explicit_role(c) in ("columnheader", "rowheader")
                       for c in cells)
        if has_th or has_scope or has_headers or has_role:
            continue
        if len(rows) >= 3 and max_cells >= 3:
            # Large enough that a data table without marked-up headers is the
            # near-certain reading (F91); layout tables of this size should
            # carry role="presentation".
            r.findings.append(_f("bb-table-headers", FAIL, MODERATE,
                                 f"{len(rows)}x{max_cells} table has no header "
                                 "cells (th, role columnheader or rowheader, "
                                 "scope, headers). If it is a data table, "
                                 "mark the headers; if layout, add "
                                 "role=\"presentation\".", table))
        else:
            r.findings.append(_f("bb-table-headers", NEEDS_REVIEW, MINOR,
                                 "Small table without header cells — a key/"
                                 "value pair table may not need them; a data "
                                 "table does.", table))
    return r


def _zero_size(el: Tag) -> bool:
    """A width or height attribute of 0 that sets the rendered size: an
    inline style that sets the same dimension overrides the attribute, and
    <audio> has no width or height attributes (its controls render at
    their own size)."""
    if el.name == "audio":
        return False
    decls = _inline_style(el.get("style"))
    return any(dim not in decls and _norm(el.get(dim)).rstrip("px") == "0"
               for dim in ("width", "height"))


def _explicit_role(el: Tag) -> str:
    """The explicit role: the first token of the role attribute a browser
    knows ("" if none is). role="foo none" is none."""
    return next((t for t in _roles(el) if t in ROLES), "")


def check_iframe_title(page: PageContext) -> RuleResult:
    """4.1.2 (heuristic) — iframes need names; also the third-party-
    exclusion residual duty. As W3C's ACT rule cae760 reads it: an iframe
    out of the tab order (a negative tabindex) or marked as decorative (an
    explicit role of none or presentation, even with a tabindex that puts
    it in the tab order: Inapplicable Example 4) needs none."""
    r = RuleResult("bb-iframe-title", applicable=False)
    for fr in page.soup.find_all("iframe"):
        if _excluded_from_tree(fr) or _zero_size(fr):
            continue  # tag-manager/tracking frames: no user ever meets them
        tabindex = _tabindex(fr)
        if (tabindex is not None and tabindex < 0) or \
                _explicit_role(fr) in ("none", "presentation"):
            continue
        r.applicable = True
        if not static_accname(fr, page.soup, page.ids):
            r.findings.append(_f("bb-iframe-title", FAIL, MODERATE,
                                 "iframe has no title/accessible name. (Embed "
                                 "internals are outside evaluation scope; the "
                                 "boundary markup is not.)", fr))
    return r


def _media_muted(el: Tag, page: PageContext) -> bool:
    """Is this <audio>/<video> muted? A rendered capture records the `muted`
    property, which is what plays (React sets only the property; script can
    also unmute after load); that record is read only under the capture's
    own secret name. Elsewhere, the markup's `muted` attribute decides."""
    if page.provenance_attr:
        state = el.get(muted_attr(page.provenance_attr))
        if state in ("true", "false"):
            return state == "true"
    return el.has_attr("muted")


def _foreign(el: Tag) -> bool:
    """Is `el` an SVG or MathML element (style.namespace_of: the namespace
    the parser recorded, or, for html.parser's tree, as a browser's parser
    would have made it)?"""
    return namespace_of(el) != "html"


#: Local files Chromium opens as application/xhtml+xml, and so parses as
#: XML (measured: .xhtml, .xht and .xhtm).
XML_SUFFIXES = (".xhtml", ".xht", ".xhtm")


def _xml_path(path: str) -> bool:
    """A local XHTML file, which a browser parses as XML: no implied
    elements, `<div/>` closes itself, and no declarative shadow root
    attaches."""
    path = (path or "").lower()
    return "://" not in path and path.endswith(XML_SUFFIXES)


def _never_plays(el: Tag, page: PageContext) -> bool:
    """Media no browser that runs scripts plays: inside <noscript>, or an
    inert <template>; or a `video`/`audio` element in SVG or MathML, which
    is not an HTML media element. (A shadow root is a <bb-shadow-root> by
    now, in every kind of run: shadow.materialize.)"""
    for node in el.parents:
        if not isinstance(node, Tag):
            break
        if node.name in ("noscript", "template"):
            return True
    return _foreign(el)


def _has_media_source(el: Tag) -> bool:
    """A src, or a child <source> with one. Without either nothing plays on
    load. A src set by script reflects into a rendered capture's markup; a
    srcObject (a live stream) does not."""
    if _norm(el.get("src")):
        return True
    return any(_norm(s.get("src"))
               for s in el.find_all("source", recursive=False))


def _controls_unusable(el: Tag) -> str:
    """Why markup shows the element's native controls are not a control
    users can see and assistive technology exposes (ACT 4c31df), or "".
    Inline styles are read as a browser reads them (_inline_style:
    comments ignored, the last declaration wins). Inline visibility follows
    CSS: the nearest declaration wins, so visibility:visible on the element
    undoes visibility:hidden on an ancestor; display:none cannot be undone.
    In a rendered run that recorded what the page hides, that record
    decides whether the element is hidden, stylesheets included, instead of
    the markup a stylesheet can override (L25); inert and aria-hidden are
    still read from markup."""
    page = CURRENT_PAGE.get()
    if page is not None and page.hiding_recorded and PROVENANCE_ATTR.get():
        node = el
        while isinstance(node, Tag):
            if node.has_attr("inert"):
                return "inert"
            if aria_hidden(node):
                return "aria-hidden"
            node = node.parent
        if _capture_hidden(el):
            return "hidden"
        return "zero-size" if _zero_size(el) else ""
    visibility = None
    child, node = None, el
    while isinstance(node, Tag):
        if node.has_attr("inert"):
            return "inert"
        if aria_hidden(node):
            return "aria-hidden"
        if node.has_attr("hidden"):
            return "hidden"
        if node.name == "dialog" and not node.has_attr("open"):
            return "hidden"
        if (node.name == "details" and not node.has_attr("open")
                and node is not el
                and child is not _first_summary(node)):
            return "hidden"
        decls = _inline_style(node.get("style"))
        if decls.get("display") == "none":
            return "hidden"
        if visibility is None:
            v = decls.get("visibility")
            if v in ("visible", "hidden", "collapse"):
                visibility = v
            elif v in ("initial", "revert", "revert-layer"):
                visibility = "visible"         # its initial value
            # inherit, unset or none: the ancestors decide
        child, node = node, node.parent
    if visibility in ("hidden", "collapse"):
        return "hidden"
    if _zero_size(el):
        return "zero-size"
    return ""


_UNUSABLE = {
    "inert": "inside inert content, which no one can operate and assistive "
             "technology does not expose",
    "aria-hidden": "inside aria-hidden content, which assistive technology "
                   "does not expose",
    "hidden": "hidden",
    "zero-size": "zero-size, so no one can see them",
}


def check_media_autoplay(page: PageContext) -> RuleResult:
    """1.4.2 — sound that plays automatically with nothing to stop it. W3C
    failure F93 and ACT rule 80f0bf test it under 1.4.2; 2.2.2 is about
    moving visual content (L72-1), which only the review of a muted video
    below asks about.

    ACT 80f0bf passes autoplaying sound that has a visible control to pause
    it or turn it off; native `controls` are that control (4c31df, Passed
    Example 1) unless markup shows them hidden or kept from assistive
    technology. ACT notes native controls are not keyboard-operable in some
    browser and assistive-technology combinations, and a stylesheet can
    hide them, so they turn the FAIL into a review, never a pass. The FAIL
    stays heuristic: markup cannot show that the sound lasts over 3
    seconds, or a control elsewhere. Muted media plays no sound (ACT: not
    applicable); a muted video can still be moving content (2.2.2). Media
    that never plays (_never_plays) is not applicable. Sound with no source
    in markup is a minor review: script may add one on a user action, which
    is fine, or without one (lazy loading), which plays at once."""
    r = RuleResult("bb-media-autoplay", applicable=False)
    for el in page.soup.find_all(["audio", "video"]):
        if _never_plays(el, page):
            continue
        r.applicable = True
        if not el.has_attr("autoplay"):
            continue
        kind = "Audio" if el.name == "audio" else "Video"
        if _media_muted(el, page):
            if el.name == "video" and not el.has_attr("controls"):
                r.findings.append(_f("bb-media-autoplay", NEEDS_REVIEW, MODERATE,
                                     "Muted autoplay video without controls: "
                                     "no sound, so 1.4.2 is met, but if it "
                                     "moves for more than five seconds, 2.2.2 "
                                     "needs a way to pause, stop or hide it "
                                     "(not tested here). Verify one exists.",
                                     el))
            continue
        if not _has_media_source(el):
            r.findings.append(_f("bb-media-autoplay", NEEDS_REVIEW, MINOR,
                                 f"{kind} has autoplay and no source in markup. "
                                 "If script adds one on a user action, that is "
                                 "fine; if it adds one without (lazy loading), "
                                 "sound starts at once (1.4.2). A rendered run "
                                 "(--url) shows which.", el))
            continue
        if not el.has_attr("controls"):
            r.findings.append(_f("bb-media-autoplay", FAIL, SERIOUS,
                                 f"{kind} plays sound automatically with no "
                                 "controls. Unless the sound stops within 3 "
                                 "seconds or a visible control on the page "
                                 "pauses or mutes it, this fails 1.4.2.", el))
            continue
        unusable = _controls_unusable(el)
        if unusable:
            r.findings.append(_f("bb-media-autoplay", FAIL, SERIOUS,
                                 f"{kind} plays sound automatically and its "
                                 f"native controls are {_UNUSABLE[unusable]}. "
                                 "ACT 4c31df requires a control that is "
                                 "visible and exposed to assistive technology: "
                                 "unless the sound stops within 3 seconds or "
                                 "another such control on the page pauses or "
                                 "mutes it, this fails 1.4.2.", el))
            continue
        r.findings.append(_f("bb-media-autoplay", NEEDS_REVIEW, MINOR,
                             f"{kind} plays sound automatically, with native "
                             "controls, which meet 1.4.2 when users can see "
                             "and reach them (ACT 4c31df). Confirm no "
                             "stylesheet hides them and that they work by "
                             "keyboard in the browsers you support; ACT notes "
                             "native controls do not in some. Better: do not "
                             "autoplay sound.", el))
    return r


_VIDEO_EMBED_RE = re.compile(
    r"youtube\.com|youtu\.be|youtube-nocookie\.com|vimeo\.com|wistia\.(?:com|net)"
    r"|brightcove|vidyard\.com|loom\.com|kaltura\.com", re.I)


def check_media_captions(page: PageContext) -> RuleResult:
    """1.2.1 / 1.2.2 / 1.2.5 — prerecorded media needs captions (A) and, at
    AA, audio description. Markup can show whether a captions track exists;
    it cannot show whether the video has speech or whether its visuals carry
    information the audio does not, so every finding here is needs_review.
    The point of the rule is that no video passes silently: hospital and
    university video libraries are large, and this is a real AA hole."""
    r = RuleResult("bb-media-captions", applicable=False)
    for v in page.soup.find_all("video"):
        if _excluded_from_tree(v):
            continue
        r.applicable = True
        tracks = [t for t in v.find_all("track")
                  if (t.get("kind") or "subtitles").lower() in ("captions",
                                                                  "subtitles")]
        if not tracks:
            r.findings.append(_f("bb-media-captions", NEEDS_REVIEW, SERIOUS,
                                 "Video has no captions track. If it has speech "
                                 "or meaningful sound, captions are required "
                                 "(1.2.2, A): add <track kind=\"captions\">. At "
                                 "AA it also needs an audio-described version "
                                 "when the visuals carry information the audio "
                                 "does not (1.2.5); a transcript is not a "
                                 "substitute.", v))
        else:
            r.findings.append(_f("bb-media-captions", NEEDS_REVIEW, MINOR,
                                 "Captioned video: confirm an audio-described "
                                 "version exists, or that the visuals convey "
                                 "nothing beyond the audio (1.2.5, AA).", v))
    for a in page.soup.find_all("audio"):
        if _excluded_from_tree(a):
            continue
        r.applicable = True
        r.findings.append(_f("bb-media-captions", NEEDS_REVIEW, MODERATE,
                             "Audio content: a transcript must be available "
                             "adjacent to the player (1.2.1).", a))
    for fr in page.soup.find_all("iframe"):
        if _excluded_from_tree(fr) or _zero_size(fr):
            continue
        if _VIDEO_EMBED_RE.search(fr.get("src") or ""):
            r.applicable = True
            r.findings.append(_f("bb-media-captions", NEEDS_REVIEW, SERIOUS,
                                 "Embedded video player: verify the source is "
                                 "captioned (1.2.2) and, at AA, audio-described "
                                 "where the visuals carry information (1.2.5). "
                                 "Embed only captioned sources.", fr))
    return r


def check_autocomplete(page: PageContext) -> RuleResult:
    """1.3.5 — common user-data fields should carry autocomplete tokens."""
    r = RuleResult("bb-autocomplete", applicable=False)
    for inp in page.soup.find_all("input"):
        itype = (inp.get("type") or "").lower()
        if itype not in ("email", "tel") or namespace_of(inp) != "html":
            continue
        if inp.find_parent("form") is None:
            continue
        r.applicable = True
        if not inp.has_attr("autocomplete"):
            token = "email" if itype == "email" else "tel"
            r.findings.append(_f("bb-autocomplete", NEEDS_REVIEW, MODERATE,
                                 f"Input type={itype} lacks autocomplete=\"{token}\" "
                                 "(1.3.5 applies when collecting the user's own data "
                                 "— confirm and add).", inp))
    return r


# --------------------------------------------------------------------------
# Tier 3 + policy rules
# --------------------------------------------------------------------------

#: 2.2.1's 20-hour exception, in seconds (ACT bc659a passes delays above it).
_TWENTY_HOURS = 72000


def _refresh_seconds(content: str) -> int | None:
    """The delay a <meta http-equiv=refresh> content gives, read with HTML's
    shared declarative refresh steps: ASCII whitespace, then ASCII digits
    (Python's \\d and \\s would take other scripts' digits and spaces), then
    any digits and dots; what follows must be the end, ";", "," or
    whitespace, or there is no refresh (`5abc` and `1e0; url=/t` refresh
    nothing in Chromium 141). A run of more than 9 digits is far past the
    20 hours, and int() would refuse one of more than 4,300 (OR-3)."""
    m = re.match(r"[\t\n\f\r ]*([0-9]*)", content)
    digits, pos = m.group(1), m.end()
    if not digits and not content.startswith(".", pos):
        return None
    while pos < len(content) and content[pos] in "0123456789.":
        pos += 1
    if pos < len(content) and content[pos] not in ";,\t\n\f\r ":
        return None
    digits = digits.lstrip("0")
    return int(digits or "0") if len(digits) <= 9 else _TWENTY_HOURS + 1


def check_meta_refresh(page: PageContext) -> RuleResult:
    """2.2.1 — timed meta refresh (F40/F41). Instant (0s) redirects and
    delays over 20 hours (2.2.1's exception) are exempt."""
    r = RuleResult("bb-meta-refresh", applicable=False)
    metas = [m for m in page.soup.find_all(
        "meta", attrs={"http-equiv": re.compile(r"^refresh$", re.I)})
        if not _inert_content(m)]
    if not metas:
        return r
    r.applicable = True
    # Chromium schedules each refresh it can read (one with no content, or
    # content it cannot read, is skipped: PR2-9) and keeps the soonest; of
    # two equally soon, the later (PR3-3, measured).
    meta, seconds = None, None
    for m in metas:
        s = _refresh_seconds(m.get("content") or "")
        if s is not None and (seconds is None or s <= seconds):
            meta, seconds = m, s
    if seconds is not None and 0 < seconds <= _TWENTY_HOURS:
        r.findings.append(_f("bb-meta-refresh", FAIL, MODERATE,
                             f"Timed refresh/redirect after {seconds}s with no "
                             "user control (2.2.1, F41).", meta))
    return r


def check_doc_links(page: PageContext) -> RuleResult:
    """Policy (exclusion EXC-2) — document internals are outside evaluation scope."""
    r = RuleResult("bb-doc-links", applicable=False)
    for a in page.soup.select("a[href]"):
        href = (a.get("href") or "").split("?")[0].split("#")[0].lower()
        if href.endswith(DOC_EXTS):
            r.applicable = True
            ext = href.rsplit(".", 1)[-1]
            r.findings.append(_f("bb-doc-links", NEEDS_REVIEW, MODERATE,
                                 f"Links to a document file (.{ext}). Document "
                                 "internals are outside evaluation scope: "
                                 "publish the content as HTML, or route the file "
                                 "to manual remediation.", a))
    return r


def check_a11y_statement(page: PageContext) -> RuleResult:
    """Policy (settlement-shaped) — accessibility statement + feedback route."""
    r = RuleResult("bb-a11y-statement", applicable=True)
    for a in page.soup.select("a[href]"):
        text = subtree_text(a).lower()
        href = (a.get("href") or "").lower()
        if "accessibility" in text or "accessibility" in href:
            return r
    r.findings.append(_f("bb-a11y-statement", NEEDS_REVIEW, MINOR,
                         "No link to an accessibility statement found. A "
                         "statement with a feedback channel recurs in DOJ and "
                         "private settlements."))
    return r


# --------------------------------------------------------------------------
# Deterministic pre-passes for judged questions (run always, cost nothing).
# bb-alt-junk decides junk alt text, and the judge skips it; bb-generic-link-
# text only flags generic links, which are the ones the judge then grades.
# --------------------------------------------------------------------------

JUNK_ALT_RE = re.compile(
    r"(\.(jpe?g|png|gif|webp|svg|avif|bmp|tiff?)$)"
    r"|(^(img|image|photo|picture|pic|graphic|icon|logo|banner|untitled|"
    r"screenshot|dsc|placeholder)[\s_\-]*\d*$)"
    r"|(^(img|dsc|dcim|screen\s?shot)[\s_\-]?\d+)", re.I)

GENERIC_LINK_RE = re.compile(
    r"^(click\s+here|here|read\s+more|learn\s+more|more|link|this|"
    r"details|continue|go|view|see\s+more)[.!»>›\s]*$", re.I)


def check_alt_junk(page: PageContext) -> RuleResult:
    """1.1.1 — alt text that is present but junk (filename, 'IMG_1234').

    The deterministic pre-pass of the alt-quality question: obvious junk
    fails with no judge call; genuine adequacy grading is the judge layer
    (bb-alt-quality). This is the pattern DOJ-adjacent audits mock —
    'alt=image123.jpg' passes scanners and fails users."""
    r = RuleResult("bb-alt-junk", applicable=False)
    for img in page.soup.find_all("img"):
        alt = _norm(img.get("alt"))
        if not alt or _excluded_from_tree(img) or namespace_of(img) != "html":
            continue        # an image hidden from assistive tech is never read
        if _role_of(img) in ("none", "presentation"):
            # Presentational where the browser honors the role: no image in
            # the tree, its alt never read (H6-3; ACT qt1vmo applies to
            # images with a name).
            continue
        r.applicable = True
        if JUNK_ALT_RE.search(alt):
            r.findings.append(_f("bb-alt-junk", FAIL, SERIOUS,
                                 f"alt=\"{alt}\" is a filename/placeholder, not a "
                                 "text alternative.", img))
    return r


def check_generic_link_text(page: PageContext) -> RuleResult:
    """2.4.4 — generic link text ('click here'). Deterministically only a
    review flag: 2.4.4 allows the programmatic context to supply purpose,
    which is the judge-layer question (bb-link-purpose)."""
    r = RuleResult("bb-generic-link-text", applicable=False)
    for a in page.soup.select("a[href]"):
        name = static_accname(a, page.soup, page.ids)
        if not name:
            continue  # empty links are bb-link-name's fail
        r.applicable = True
        if GENERIC_LINK_RE.match(name):
            r.findings.append(_f("bb-generic-link-text", NEEDS_REVIEW, MODERATE,
                                 f"Generic link text \"{name}\" — purpose must be "
                                 "determinable from context (judge layer grades "
                                 "this; prefer descriptive text).", a))
    return r


# --------------------------------------------------------------------------
# Evaluability: client-rendered app shells
# --------------------------------------------------------------------------

#: Elements some static rule reads. A page with none of them outside
#: script/template/noscript gives the rules nothing to evaluate.
_RULE_TARGETS = {"a", "img", "button", "input", "select", "textarea", "h1",
                 "h2", "h3", "h4", "h5", "h6", "iframe", "video", "audio",
                 "table", "area", "marquee", "blink", "form", "label",
                 "summary", "details", "dialog", "object", "embed"}
_INERT_CONTAINERS = ("script", "style", "template", "noscript")
_SHELL_TEXT_MAX = 80


#: What a page shows while it loads, or when its scripts fail: a live
#: region of one of these roles (a status message, an alert, a progress
#: bar), a region marked busy, a <progress>, or an image or drawing named
#: or classed as a spinner. A page whose markup holds nothing else is
#: still a shell (S5-3): a loading message is not the page's content.
_LOADING_ROLES = frozenset(("status", "progressbar", "alert", "log",
                            "timer", "marquee"))
_LOADING_WORDS = re.compile(r"\b(?:loading|please wait|spinner|spin|"
                            r"spinning|loader|initiali[sz]ing)\b",
                            re.IGNORECASE)
#: Roles that alone put nothing a rule reads on a page: a landmark, a group
#: or a box with no role of its own. A loading shell's mount node often
#: carries one (`<div id="root" role="main">`): that is no content (S5-3).
_CONTAINER_ROLES = frozenset((
    "none", "presentation", "generic", "main", "region", "group",
    "document", "application", "banner", "contentinfo", "complementary",
    "navigation", "search", "form", "article", "section"))


def _container_only(tag: Tag) -> bool:
    """Does `tag`'s role (none, or only _CONTAINER_ROLES) make it no
    content of its own?"""
    roles = (tag.get("role") or "").strip().lower().split()
    return all(r in _CONTAINER_ROLES for r in roles)


def _loading_indicator(tag: Tag) -> bool:
    """Is `tag` what a page shows while it loads (_LOADING_ROLES, aria-busy,
    a progress bar, or a drawing or an image whose words, class or name,
    its <title> and what aria-labelledby names included, say it loads)?"""
    roles = (tag.get("role") or "").strip().lower().split()
    if roles and (roles[0] in _LOADING_ROLES or _LOADING_WORDS.search(
            re.sub(r"[-_]", " ", " ".join(roles)))):
        return True               # role="spinner" is no role, and loads
    if (tag.get("aria-busy") or "").strip().lower() == "true":
        return True
    if tag.name == "progress":
        return True
    if tag.name in ("img", "svg"):
        classes = tag.get("class")
        classes = (" ".join(classes) if isinstance(classes, list)
                   else str(classes or ""))
        said = [str(tag.get(a) or "") for a in
                ("alt", "aria-label", "title", "src", "id")]
        title = tag.find("title")
        if isinstance(title, Tag):
            said.append(title.get_text(" "))
        ids = str(tag.get("aria-labelledby") or "").split()
        if ids:
            root = tag
            while root.parent is not None:
                root = root.parent
            for ref in ids[:8]:
                named = root.find(id=ref)
                if isinstance(named, Tag):
                    said.append(named.get_text(" ")[:200])
        return bool(_LOADING_WORDS.search(
            re.sub(r"[-_]", " ", f"{' '.join(said)} {classes}")))
    return False


def detect_app_shell(page: PageContext) -> str:
    """Why this markup cannot be evaluated by the static rules, or "".

    A client-rendered build (Vite, CRA, Angular) ships an index.html whose
    body is an empty mount node plus scripts. Evaluated as-is, only the
    document-level rules applied and it scored 100% and "Tier-1 clean" —
    the free pass the methodology forbids, on exactly the output most AI app
    builders produce. A page is treated as a shell when it loads script and,
    outside script/template/noscript, holds no element any rule reads and at
    most a loading message of text. A loading indicator (_LOADING_ROLES:
    a status or alert region, a progress bar, a spinner image) and what it
    holds count as such a message, not as content (S5-3). A page with no
    script is never a shell: an empty static page is simply empty, and
    fails on its own terms.
    """
    soup = page.soup
    if soup.find("script") is None:
        return ""
    body = soup.body or soup
    text_len = 0
    loaders: set = set()
    for node in body.descendants:
        parents = [p for p in node.parents if isinstance(p, Tag)]
        if any(p.name in _INERT_CONTAINERS for p in parents):
            continue
        in_loader = any(id(p) in loaders for p in parents)
        if isinstance(node, Tag):
            if node.name in _INERT_CONTAINERS or in_loader:
                continue
            if node.name == "input" and (node.get("type") or "").lower() == "hidden":
                continue
            if _loading_indicator(node):
                loaders.add(id(node))
                continue
            if node.name in _RULE_TARGETS or not _container_only(node):
                return ""
        elif isinstance(node, NavigableString) and not isinstance(
                node, PreformattedString):          # comments are not content
            text_len += len(_norm(str(node)))
            if text_len > _SHELL_TEXT_MAX:
                return ""
    beyond = (" beyond a loading indicator (a status or alert message, a "
              "progress bar or a spinner)" if loaders else "")
    if page.reader == "dom":
        # Captured after its scripts ran, and still empty (N27): telling
        # this run to render the page would send it in a circle.
        return ("empty when captured: the page's scripts had built no links, "
                "images, controls, headings or other content the static "
                f"rules read{beyond} ({text_len} characters of text). This "
                "is not a pass: the page may not have finished rendering "
                "(give --wait-for an element it shows once it has loaded), "
                "its scripts may have failed (open it in a browser and check "
                "the console), or, with --render, the build may expect to be "
                "served under another path (--render-base).")
    return ("client-rendered app shell: outside its scripts the markup has "
            "no links, images, controls, headings or other content the "
            f"static rules read{beyond} ({text_len} characters of text). Its "
            "content is built by JavaScript, so this file cannot show "
            "whether the page is accessible. Evaluate the rendered page "
            "instead: bellbriar-eval <folder> --render, or --url against a "
            "server.")


CHECKS = {
    "bb-img-alt": check_img_alt,
    "bb-svg-name": check_svg_name,
    "bb-link-name": check_link_name,
    "bb-button-name": check_button_name,
    "bb-redundant-links": check_redundant_links,
    "bb-control-label": check_control_label,
    "bb-widget-name": check_widget_name,
    "bb-role-img-name": check_role_img_name,
    "bb-progress-name": check_progress_name,
    "bb-control-role": check_control_role,
    "bb-html-lang": check_html_lang,
    "bb-page-title": check_page_title,
    "bb-skip-link": check_skip_link,
    "bb-viewport-zoom": check_viewport_zoom,
    "bb-aria-ref": check_aria_ref,
    "bb-aria-hidden-focus": check_aria_hidden_focus,
    "bb-positive-tabindex": check_positive_tabindex,
    "bb-marquee-blink": check_marquee_blink,
    "bb-aria-role": check_aria_role,
    "bb-aria-attr": check_aria_attr,
    "bb-duplicate-id": check_duplicate_id,
    "bb-heading-structure": check_heading_structure,
    "bb-table-headers": check_table_headers,
    "bb-iframe-title": check_iframe_title,
    "bb-media-autoplay": check_media_autoplay,
    "bb-media-captions": check_media_captions,
    "bb-autocomplete": check_autocomplete,
    "bb-meta-refresh": check_meta_refresh,
    "bb-doc-links": check_doc_links,
    "bb-a11y-statement": check_a11y_statement,
    "bb-alt-junk": check_alt_junk,
    "bb-generic-link-text": check_generic_link_text,
}
