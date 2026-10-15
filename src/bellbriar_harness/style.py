"""Inline `style` attributes, read as a browser reads them.

Shared by the static rules (checks_static) and accessible-name computation
(accname): markup alone proves an element hidden when its own style, or an
ancestor's, says display:none, visibility:hidden or content-visibility:hidden.
Stylesheets are invisible here; a rendered capture records their effect
(model.hidden_attr).
"""
from __future__ import annotations

import bisect
import functools
import re
import types

_STYLE_COMMENT_RE = re.compile(r"/\*.*?(?:\*/|$)", re.S)
_CSS_ESCAPE_RE = re.compile(
    r"\\(?:([0-9a-fA-F]{1,6})(?:\r\n|[ \t\n\r\f])?|(.))", re.S)
#: CSS's white space (not all Python's str.strip() and \s take: a no-break
#: space or a vertical tab is none, and a rule's or a declaration's parts
#: are trimmed of CSS's alone: R6D-6).
_CSS_WS = " \t\n\r\f"
#: A token of a list HTML splits at ASCII white space (`class`: R6X-2).
_HTML_TOKENS = re.compile(r"[^\t\n\f\r ]+")
_CSS_SPACE = re.compile(r"[ \t\n\r\f]*")
#: An escape: up to six hex digits (and one white space after them), or a
#: character; written so that a regex cannot read one two ways, which
#: made a failed match take exponential time.
_CSS_ESCAPE = (r"\\(?:[0-9a-fA-F]{6}[ \t\n\r\f]?"
               r"|[0-9a-fA-F]{1,5}(?![0-9a-fA-F])[ \t\n\r\f]?"
               r"|[^\n\r\f0-9a-fA-F])")
#: A CSS name (an ident), escapes and all.
_CSS_NAME = (r"(?:--|-?(?:[a-zA-Z_\u0080-\U0010ffff]|" + _CSS_ESCAPE
             + r"))(?:[-\w\u0080-\U0010ffff]|" + _CSS_ESCAPE + r")*")
_CSS_IDENT = re.compile(_CSS_NAME)
#: A name read whole, as CSS reads one: an escape's white space is its
#: (`\\61 \\62` is one name), never given back, so no pattern can split a
#: run of escapes two ways (exponential time on a near miss: R6J-1).
_NAME = "(?>" + _CSS_NAME + ")"
#: A declaration's `!important`: "!", then a name (important, its escapes
#: read, in any case: _important), CSS white space and comments
#: (_COMMENT) around it.
_IMPORTANT_RE = re.compile(r"![ \t\n\r\f\x00]*(" + _CSS_NAME
                           + r")[ \t\n\r\f\x00]*\Z")
#: A word of a declaration's value: up to CSS white space no escape holds
#: (`none\9` is one word, an escaped tab its last character: R6D-6), or
#: a comment (_COMMENT), which no escape takes as its white space
#: (`\6e/**/one` is two words: R6F-7).
_WORD_RE = re.compile(r"(?:[^ \t\n\r\f\\\x00]+"
                      r"|\\[0-9a-fA-F]{1,6}(?:\r\n|[ \t\n\r\f])?"
                      r"|\\[^0-9a-fA-F\n\r\f]|\\(?=[\n\r\f]|\Z))+")
#: An escape, as CSS consumes one: up to six hex digits and one white
#: space after them, or any other character but a line break.
_ESCAPE_ONE = re.compile(r"\\(?:[0-9a-fA-F]{1,6}(?:\r\n|[ \t\n\r\f])?"
                         r"|[^\n\r\f])")
#: Where style_rules has dropped a comment: CSS reads a comment as no
#: token, so one separates what is on its either side, but is no white
#: space (`(width >/**/= 1px)` is `>=`: R6D-5). CSS reads no U+0000 in a
#: stylesheet (it makes one U+FFFD), so none is mistaken for one.
_COMMENT = "\x00"
#: Where a url( may open: the name url, any of its letters escaped or not
#: (`\75 rl(`, `\url(`), then "(" (R6D-7); _url_token says whether a url
#: token starts there.
_ESC_WS = r"(?:\r\n|[ \t\n\r\f])?"
_URL_OPEN = (r"(?:[uU]|\\(?:[uU]|0{0,4}[57]5" + _ESC_WS + r"))"
             r"(?:[rR]|\\(?:[rR]|0{0,4}[57]2" + _ESC_WS + r"))"
             r"(?:[lL]|\\(?:[lL]|0{0,4}[46][cC]" + _ESC_WS + r"))\(")
#: What a url token may not hold: CSS's non-printable code points.
_NON_PRINTABLE = frozenset(map(chr, (*range(0x00, 0x09), 0x0B,
                                     *range(0x0E, 0x20), 0x7F)))
#: A url token's characters that need no second look.
_URL_PLAIN = re.compile(r"[^)\\\"'( \t\n\r\f\x00-\x08\x0b\x0e-\x1f\x7f]+")
#: ASCII's capitals and their small letters: CSS matches names and
#: keywords ASCII case-insensitively (str.lower() makes the Kelvin sign a
#: "k": `display: bloc\u212a` is no display Chromium takes).
_ASCII_LOWER = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ",
                             "abcdefghijklmnopqrstuvwxyz")
_CSS_WIDE = {"inherit", "initial", "unset", "revert", "revert-layer"}
#: The display values Chromium accepts (checked against Chromium 141:
#: `run-in`, `inline-list-item`, `ruby-base` and the ruby containers are
#: dropped, so an earlier `display:none` stands).
_DISPLAY_ONE = {"none", "contents", "block", "inline", "flow", "flow-root",
                "table", "flex", "grid", "ruby", "math", "list-item",
                "inline-block", "inline-table", "inline-flex", "inline-grid",
                "table-row-group", "table-header-group", "table-footer-group",
                "table-row", "table-cell", "table-column-group",
                "table-column", "table-caption", "ruby-text", "-webkit-box",
                "-webkit-inline-box", "-webkit-flex", "-webkit-inline-flex"}
#: Multi-keyword display, as Chromium 141 reads it (all 1,872 two- and
#: three-word orderings of these and run-in/contents/none checked): an
#: outer and an inner keyword in either order (`inline flex`), or
#: list-item with at most one outer keyword and at most one of flow and
#: flow-root (`inline flow-root list-item`). Anything else (`inline block`,
#: `flex grid`, run-in) is dropped, so an earlier display:none stands.
_DISPLAY_OUTER = {"block", "inline"}
_DISPLAY_INNER = {"flow", "flow-root", "table", "flex", "grid", "ruby", "math"}


def _display_multi(words: list[str]) -> bool:
    if len(set(words)) != len(words) or not 2 <= len(words) <= 3:
        return False
    if "list-item" in words:
        rest = [w for w in words if w != "list-item"]
        return (sum(w in _DISPLAY_OUTER for w in rest) <= 1
                and sum(w in ("flow", "flow-root") for w in rest) <= 1
                and all(w in _DISPLAY_OUTER or w in ("flow", "flow-root")
                        for w in rest))
    return (len(words) == 2
            and sum(w in _DISPLAY_OUTER for w in words) == 1
            and sum(w in _DISPLAY_INNER for w in words) == 1)
#: The values a browser accepts for the other properties markup can hide
#: with. A declaration with any other value is dropped, so an earlier one
#: stands (`display:none; display:nonsense` stays hidden).
_STYLE_VALUES = {
    "visibility": {"visible", "hidden", "collapse"},
    "content-visibility": {"visible", "hidden", "auto"},
}


def _lower(text: str) -> str:
    """`text` lowercased as CSS compares names: ASCII's letters only."""
    return text.translate(_ASCII_LOWER)


def _css_unescape(text: str) -> str:
    def one(m: re.Match) -> str:
        if m.group(1):
            cp = int(m.group(1), 16)
            ok = 0 < cp <= 0x10FFFF and not 0xD800 <= cp <= 0xDFFF
            return chr(cp) if ok else chr(0xFFFD)
        return m.group(2)
    return _CSS_ESCAPE_RE.sub(one, text)


def _valid_style_value(name: str, value: str,
                       words: list | None = None) -> bool:
    """Does `name` take `value` (lowercased, its escapes read; `words`: its
    words as CSS reads them, _value_words, else white space splits it)?"""
    if words is None:
        words = value.split()
    if (len(words) == 1 and words[0] in _CSS_WIDE) \
            or re.search(r"\b(?:var|env|attr)\(", value):
        return True       # settled later; it still replaces an earlier one
    if name == "display":
        if len(words) == 1:
            return words[0] in _DISPLAY_ONE
        return _display_multi(words)
    allowed = _STYLE_VALUES.get(name)
    return allowed is None or (len(words) == 1 and words[0] in allowed)


def _value_words(value: str) -> list[str]:
    """The words of a declaration's value (split at CSS white space no
    escape holds, and where a comment was: _COMMENT), each with its
    escapes read and lowercased: `none\\9` is the one word "none" and a
    tab, which no property takes (an old hack for one browser: R6D-6),
    and `\\6e/**/one` the words "n" and "one" (R6F-7). A string is split
    as any other text: no value read here holds one."""
    return [_lower(_css_unescape(w)) for w in _WORD_RE.findall(value)]


def _escaped(text: str, i: int) -> bool:
    """Is text[i] the character an escape writes (after an odd number of
    backslashes)?"""
    k = i
    while k > 0 and text[k - 1] == "\\":
        k -= 1
    return (i - k) % 2 == 1


def _important(value: str) -> tuple[str, bool]:
    """(`value` without CSS white space around it, nor a `!important` at
    its end; whether it had one), as CSS reads one: `! IMPORTANT` and
    `!\\69mportant` are, `\\!important` and `!\\u00a0important` are not
    (R6D-6)."""
    value = value.strip(_CSS_WS + _COMMENT)
    m = _IMPORTANT_RE.search(value)
    if m is None or _lower(_css_unescape(m.group(1))) != "important" \
            or _escaped(value, m.start()):
        return value, False
    return value[:m.start()].rstrip(_CSS_WS + _COMMENT), True


def _inline_style(style: str | None) -> dict[str, str]:
    """The declarations an inline style attribute sets, read as a browser
    reads them: comments dropped, escapes read, a declaration with a value
    the property does not take dropped (`display:none; display:nonsense`
    stays hidden), and the last declaration of a property wins unless an
    earlier one is !important (`display:none; display:block` shows the
    element). Property names and values lowercased, without `!important`.
    Read once per text (a page's walks ask for one element's again and
    again: R6B-2); what it returns is read only."""
    if not style:
        return _NO_DECLARATIONS
    return _inline_style_of(style)


@functools.lru_cache(maxsize=4096)
def _inline_style_of(style: str):
    return types.MappingProxyType(
        {k: v for k, (v, _) in _declarations(style).items()})


#: No declarations, read only.
_NO_DECLARATIONS = types.MappingProxyType({})


def _declarations(style: str | None, marked: bool = False):
    """_inline_style's declarations, each with whether it is !important,
    read once per text and read only. `marked`: `style` is a rule's
    declarations as style_rules gives them, each comment marked
    (_COMMENT); else a style attribute, comments and all."""
    if not style:
        return _NO_DECLARATIONS
    return _declarations_of(style, marked)


@functools.lru_cache(maxsize=4096)
def _declarations_of(style: str, marked: bool = False):
    out: dict[str, tuple[str, bool]] = {}
    if not marked:
        # A comment separates what is on its either side, and is no white
        # space an escape takes (`\6e/**/one` is no `none`: R6F-7).
        style = _without_comments(style.replace("\x00", "\ufffd"),
                                  _COMMENT)
    for decl in _split_declarations(style):
        name, sep, value = decl.partition(":")
        name = _lower(_css_unescape(name.strip(_CSS_WS + _COMMENT)))
        if not sep or not name or _COMMENT in name:
            continue                    # `\64/**/isplay` names nothing
        value, important = _important(value)
        words = _value_words(value)
        value = " ".join(words)
        if not value or not _valid_style_value(name, value, words):
            continue
        prev = out.get(name)
        if prev is not None and prev[1] and not important:
            continue
        out[name] = (value, important)
    return types.MappingProxyType(out)


def _style_hides(style: str | None) -> bool:
    """Inline display:none, visibility:hidden or collapse (collapse hides
    anything that is not a table row or column), or
    content-visibility:hidden."""
    decls = _inline_style(style)
    return (decls.get("display") == "none"
            or decls.get("visibility") in ("hidden", "collapse")
            or decls.get("content-visibility") == "hidden")


#: Display values that leave a browser's own `display:none` standing:
#: `none`, and `revert` and `revert-layer`, which may fall back to it (for
#: a closed <dialog> or a popover; the hidden attribute, Chromium 141
#: reverts: _decide reads that with the element). Anything else an author
#: sets shows the element; a value only known later (var()) is read as
#: showing it, so markup can never hide its own content from the rules
#: that way.
_LEAVES_UA_HIDDEN = {"none", "revert", "revert-layer"}


def author_display_shows(value: str | None) -> bool:
    """Does an author `display` value surely override a browser's
    display:none, whatever the element?"""
    return value is not None and value not in _LEAVES_UA_HIDDEN


#: What the comment and url() scanners read as more than a character: a
#: url( (R6D-7), a string, an escape, and a comment's start.
_COMMENT_SCAN = re.compile("(?P<url>" + _URL_OPEN + r")|[\"'\\]|/\*")


def _without_comments(css: str, sep: str = " ") -> str:
    """`css` with each comment `sep` (a space, or _COMMENT where a reader
    tells the two apart), as CSS reads one: not inside a string (`content:
    "/*"` opens none: R5K-12), nor inside a url token, which runs to its
    ")" (`url(/img/*.png)`: R5M-13)."""
    if "/*" not in css:
        return css
    out, i, start, n = [], 0, 0, len(css)
    while True:
        m = _COMMENT_SCAN.search(css, i)
        if m is None:
            break
        i = m.start()
        if m.group("url") is not None:
            got = _url_token(css, i, m.end())
            i = got[0] if got is not None else m.end()
            continue
        ch = css[i]
        if ch in "\"'":
            i = _skip_string(css, i)
        elif ch == "\\":
            i += 2
        else:
            out.append(css[start:i])
            out.append(sep)
            end = css.find("*/", i + 2)
            i = start = n if end < 0 else end + 2
    out.append(css[start:])
    return "".join(out)


def css_urls(text: str) -> list[str]:
    """What each url() in CSS text names, as CSS reads it: a url token's,
    or a url( function's string; not one in a comment, a string, or the
    end of a longer name (R5K-13, R6D-7)."""
    out: list[str] = []
    text = _without_comments(text)
    i, n = 0, len(text)
    while True:
        m = _COMMENT_SCAN.search(text, i)
        if m is None:
            break
        i = m.start()
        if m.group("url") is not None:
            got = _url_token(text, i, m.end())
            if got is not None:
                end = got[0] - 1 if text[got[0] - 1:got[0]] == ")" \
                    else got[0]
                out.append(text[m.end():end].strip(_CSS_WS))
                i = got[0]
                continue
            k = _CSS_SPACE.match(text, m.end()).end()
            if not (i and _ends_name(text, i)) and k < n \
                    and text[k] in "\"'":
                end = _skip_string(text, k)
                closed = end - 1 > k and text[end - 1] == text[k]
                out.append(text[k + 1:end - 1 if closed else end])
                i = end
            else:
                i = m.end()
            continue
        if text[i] == "\\":
            i += 2
        else:
            i = _skip_string(text, i)
    return out


def style_rules(css: str, budget: list | None = None,
                namespaces: dict | None = None) -> list[tuple[str, str,
                                                             bool, bool]]:
    """The style rules of a stylesheet: (selector list, declarations,
    whether a condition a file run cannot settle holds them, whether they
    are in a cascade layer). A rule in a block every screen applies
    (@layer; @media with no query, `all` or `screen`, `not print`, or one
    no screen fails, such as `not print and (…)`; an @supports Chromium 141
    passes, _supports) is read as a top-level one; one in @media with
    features, an @supports the run cannot settle, @container, or @scope
    with a limit or no root, is conditional, and PageStyles reads only
    what it shows (R5G-6, R5K-4). @scope (root) with no limit is read as
    the root's own rules: its rules hold below the root, `:scope` and `&`
    being the root. A rule in a block no screen applies (print, tv, `not
    screen`, an @media query a browser drops, as `only` alone; an
    @supports Chromium fails) and the blocks of other at-rules
    (@keyframes, @font-face, @page) are left out.
    Nested rules are read with their parents' selectors (CSS nesting), up
    to _MAX_NESTED characters of them for a rule and _MAX_NESTED_TOTAL in
    all (`budget`: PageStyles shares one over a page's stylesheets);
    braces inside strings are text (R5I-2), and so are comment marks
    (R5K-12). A comment separates what is on its either side, but is no
    white space, so where one was is marked (_COMMENT), in declarations
    too: `.a/**/.b` is `.a.b`, and `\\6e/**/one` no `none` (R6F-7). A list
    of rules (a stylesheet's, and a block's of @media, @supports, @layer
    or @container outside a style rule) holds no declarations: a ";" ends
    an at-rule with no block, but a style rule's prelude holds it, as one
    holds a "}" that closes nothing, and the rule is invalid (`.a{}; .b{}`
    drops `.b`); a stylesheet's "<!--" and "-->" are no part of a rule
    (R6F-2). A selector list Chromium 141 does not read drops its rule
    and the rules nested in it: one with an empty member, a pseudo-class
    or a pseudo-element it does not have, or one in a form or with an
    argument it does not take, or a namespace prefix no @namespace it
    reads declares (style_namespaces, or `namespaces` where the caller has
    read them), and an @scope's root or limit so (R6F-3, R6H-2, R6H-5,
    R6H-8). So does one with a member soupsieve does not read, each
    pseudo-class, pseudo-element and `&` in it read as a simple selector
    (`.a..b`, `#2:hover`: _members_read, R6T-2): a nested rule, and a
    top-level one that holds rules nested in it, here; a top-level one
    that holds none, PageStyles._add (R6V-6, R6X-8)."""
    if namespaces is None:
        namespaces = style_namespaces(css)
    prefixes = frozenset(k for k in namespaces if k)
    css = _without_comments(css.replace("\x00", "\ufffd"), _COMMENT)
    out: list[tuple[str, str, bool, bool]] = []
    _style_walk(css, None, False, False, 0, out, namespaces=prefixes,
                budget=budget)
    return out


#: How deep blocks are read inside each other.
_MAX_AT_NESTING = 8
#: How many characters nested rules' selectors written out with their
#: parents' (_nested) may add in all, over a page's stylesheets: past it,
#: a nested rule, and those nested in it, are not read (a long parent
#: list repeated for each of many nested rules took a minute to read).
_MAX_NESTED_TOTAL = 200_000
#: How much a nested rule's selectors may grow when written out with its
#: parents' (_nested): each level repeats its parent's for each selector
#: of its own, so a few hundred bytes of nesting would grow past memory
#: (R5K-7). A rule that would grow more, and those nested in it, are not
#: read; nothing is written out first (R5M-12), and a rule at the top level
#: is read whatever its length (R5M-3).
_MAX_NESTED = 20_000
#: An at-rule's name, as CSS reads one (`@media\u00a0screen` is no
#: @media; `@\6d edia` is).
_AT_NAME_RE = re.compile("@(" + _CSS_NAME + ")")
#: A cascade layer's name: names joined by "." (`a.b`), no white space.
_LAYER_NAME = re.compile(_CSS_NAME + r"(?:\." + _CSS_NAME + ")*")


def _string_end(text: str, i: int) -> tuple[int, bool]:
    """(the index after the CSS string that starts at `text[i]` (a quote),
    whether it is a bad string: one a line break ends, before which it
    ends), as CSS reads it; an escaped line break goes on."""
    quote, i, n = text[i], i + 1, len(text)
    while i < n:
        ch = text[i]
        if ch == "\\":
            i += 3 if text.startswith("\r\n", i + 1) else 2
            continue
        if ch == quote:
            return i + 1, False
        if ch in "\n\r\f":
            return i, True
        i += 1
    return n, False


def _skip_string(text: str, i: int) -> int:
    """The index after the CSS string that starts at `text[i]` (a quote),
    a bad one too (_string_end)."""
    return _string_end(text, i)[0]


#: The closer of each bracket CSS reads as a block.
_CLOSERS = {"(": ")", "[": "]", "{": "}"}
#: What CSS reads as more than a character: a url( (R6B-1, R6D-7), a
#: string, an escape, a bracket and a ";". The scanners jump from one to
#: the next (R6B-2); a url( is tried first, as one may start with an
#: escape.
_CSS_SPECIAL = re.compile("(?P<url>" + _URL_OPEN + r")|[\"'\\()\[\]{};]")


def _ends_name(text: str, i: int) -> bool:
    """Does what is before text[i] (i > 0) make what starts there part of
    a longer name, a hash or an at-keyword, as CSS reads them: a name's
    character (ASCII's letters, digits, "-", "_", any code point from
    U+0080), "#", "@", or an escape that ends there (`\\31 url(`)?"""
    c = text[i - 1]
    if c in "-_#@" or ("0" <= c <= "9") or ("a" <= c <= "z") \
            or ("A" <= c <= "Z") or c >= "\x80":
        return True
    for k in range(i - 1, max(-1, i - 10), -1):
        if text[k] == "\\":
            m = _ESCAPE_ONE.match(text, k)
            if m is not None and m.end() == i:
                return not _escaped(text, k)
    return False


def _url_token(text: str, start: int, open_end: int) -> tuple | None:
    """(the index after the url token whose url( is text[start:open_end]:
    after its first ")" not escaped, or the end; whether it is a bad url,
    which a quote, a "(", a character CSS does not print, white space
    inside it or a backslash before a line break make), as CSS reads one
    (a bad one still runs to its ")"); None where no url token starts
    there: the URL is quoted (a function holding a string), or url ends
    a longer name, a hash or an at-keyword (`xurl(`, `\\31 url(`, `#url(`,
    `\\u00b7url(`: R6D-7)."""
    if start and _ends_name(text, start):
        return None
    n = len(text)
    k = _CSS_SPACE.match(text, open_end).end()
    if k < n and text[k] in "\"'":
        return None
    bad = False
    while k < n:
        m = _URL_PLAIN.match(text, k)
        if m is not None:
            k = m.end()
            if k >= n:
                break
        c = text[k]
        if c == ")":
            return k + 1, bad
        if c == "\\":
            m = _ESCAPE_ONE.match(text, k)
            if m is None:               # before a line break: no escape
                bad = True
                k += 1
            else:
                k = m.end()
            continue
        if c in _CSS_WS:
            k = _CSS_SPACE.match(text, k).end()
            if k < n and text[k] != ")":
                bad = True
            continue
        if c in "\"'(" or c in _NON_PRINTABLE:
            bad = True
        k += 1
    return n, bad


def _block_end(text: str, i: int) -> tuple[int, int]:
    """(where the block opened at `text[i]` ends, where what it holds ends)
    as CSS reads it: strings, escapes and unquoted url()s skipped, and a
    bracket inside it a block of its own, closed by its own closer only
    (`(})` holds a brace, and closes nothing). An unclosed block runs to
    the end."""
    stack = [_CLOSERS[text[i]]]
    k, n = i + 1, len(text)
    while True:
        m = _CSS_SPECIAL.search(text, k)
        if m is None:
            return n, n
        k = m.start()
        if m.group("url") is not None:
            got = _url_token(text, k, m.end())
            if got is not None:
                k = got[0]
                continue
            k = m.end() - 1             # its "(" opens a block
        c = text[k]
        if c in "\"'":
            k = _skip_string(text, k)
            continue
        if c == "\\":
            k += 2
            continue
        if c in _CLOSERS:
            stack.append(_CLOSERS[c])
        elif c == stack[-1]:
            stack.pop()
            if not stack:
                return k + 1, k
        k += 1


#: What a stylesheet discards before each of its rules: CSS's white
#: space, comments (_COMMENT), and the "<!--" and "-->" an HTML comment
#: around a stylesheet leaves (CDO and CDC tokens: R6F-2).
_RULE_START = re.compile(r"(?:[ \t\n\r\f\x00]|<!--|-->)*")


def _prelude(text: str, start: int, end: int, top: bool) -> str:
    """text[start:end], a rule's prelude, without the white space and
    comments around it (and, `top`, what a stylesheet discards before
    it)."""
    if top:
        start = _RULE_START.match(text, start, end).end()
    return text[start:end].strip(_CSS_WS + _COMMENT)


def _starts_at_rule(text: str, start: int, end: int, top: bool) -> bool:
    """Does the rule whose prelude text[start:end] begins start with an
    at-keyword?"""
    k = (_RULE_START if top else _MQ_SPACE).match(text, start, end).end()
    return _AT_NAME_RE.match(text, k, end) is not None


def _css_blocks(text: str, rules: bool = False,
                top: bool = False) -> tuple[list[tuple[str, str]], str]:
    """([(prelude, body)] of the blocks at `text`'s own level, in order;
    the declarations between them, joined by ";"). Strings, escapes,
    unquoted url()s and brackets are read as CSS reads them, so a brace or
    a ";" in a string, a url() or parentheses (`@supports (--x: {a})`)
    opens or ends nothing (R6B-1).

    `rules`: `text` is a list of rules, which holds no declarations: a
    ";" ends an at-rule with no block (`@import url(a.css);`), but a
    style rule's prelude holds it, as one holds a "}" that closes
    nothing, and the rule is invalid: its prelude is "" (`.a{}; .b{}` and
    `.a{}} .b{}` drop `.b`). An at-rule's prelude holds such a "}" too
    (`@media screen, }` is `screen` and a query dropped). `top`: `text` is
    a stylesheet, which discards a "<!--" or "-->" before a rule
    (measured in Chromium 141: R6F-2)."""
    blocks: list[tuple[str, str]] = []
    loose: list[str] = []
    i, n, start = 0, len(text), 0
    at = None           # does the rule being read start with "@"?
    bad = False         # does its prelude hold a ";" or a "}"?
    while True:
        m = _CSS_SPECIAL.search(text, i)
        if m is None:
            break
        i = m.start()
        if m.group("url") is not None:
            got = _url_token(text, i, m.end())
            i = got[0] if got is not None \
                else _block_end(text, m.end() - 1)[0]
            continue
        ch = text[i]
        if ch in "\"'":
            i = _skip_string(text, i)
        elif ch == "\\":
            i += 2
        elif rules and ch in ";}":
            if at is None:
                at = _starts_at_rule(text, start, i, top)
            if ch == ";" and at:
                start, at, bad = i + 1, None, False     # an at-rule ends
            elif ch == ";" or not at:
                bad = True
            i += 1
        elif ch == ";":
            loose.append(text[start:i])
            i = start = i + 1
        elif ch == "}":                 # a stray close: nothing is open
            i = start = i + 1
        elif ch == "{":
            k, end = _block_end(text, i)
            blocks.append(("" if bad else _prelude(text, start, i, top),
                           text[i + 1:end]))
            i = start = k
            at, bad = None, False
        elif ch in "([":
            i = _block_end(text, i)[0]  # part of what it is in
        else:
            i += 1                      # a stray ")" or "]"
    loose.append(text[start:])
    return blocks, ";".join(loose)


#: What a declaration list may hold a ";" inside of: a string, an escape,
#: a bracket (a url() among them).
_DECLARATION_SCAN = re.compile(r"[\"'\\(\[{]")


def _split_declarations(text: str) -> list[str]:
    """`text` split at each ";" outside its strings, escapes, unquoted
    url()s and brackets, as CSS reads a declaration list (`content: "a;b"`
    is one: R6B-1)."""
    if not _DECLARATION_SCAN.search(text):
        return text.split(";")
    parts, i, start = [], 0, 0
    while True:
        m = _CSS_SPECIAL.search(text, i)
        if m is None:
            break
        i = m.start()
        if m.group("url") is not None:
            got = _url_token(text, i, m.end())
            i = got[0] if got is not None \
                else _block_end(text, m.end() - 1)[0]
            continue
        ch = text[i]
        if ch in "\"'":
            i = _skip_string(text, i)
        elif ch == "\\":
            i += 2
        elif ch in _CLOSERS:
            i = _block_end(text, i)[0]
        elif ch == ";":
            parts.append(text[start:i])
            i = start = i + 1
        else:
            i += 1
    parts.append(text[start:])
    return parts


def _style_walk(text: str, selectors: str | None, conditional: bool,
                layered: bool, nesting: int, out: list,
                scope: str | None = None, block: bool = False,
                nested: bool = False,
                namespaces: frozenset = frozenset(),
                own: bool = True, budget: list | None = None,
                bare: bool = False) -> None:
    """style_rules' rules of `text` into `out`. `block`: `text` is a
    block's contents (a style rule's, an @scope's, and a block's of a rule
    inside a style rule), which holds declarations, of `selectors` (but
    with `own` false, an @scope's with no root, whose declarations are
    its root's, which the run does not read); else a list of rules
    (R6F-2). `nested`: `text` is inside a style rule's block, nearer than
    an @scope's (whose block holds lists of rules again: measured in
    Chromium 141). `namespaces`: the prefixes the stylesheet declares
    (style_namespaces, _selector_check). `budget`: [how many characters
    nested selectors written out may still add] (_grows). `bare`: `text`
    is inside an @scope with no root, whose root (the <style>'s parent)
    no selector names: `&` and `:scope` there match nothing (R6X-1), but
    in one nested in a style rule or a rooted @scope, which is read
    against the outer selector (L127). An @scope with a root and a limit
    is read as one with the root alone, its rules under a condition
    (R6X-1)."""
    if budget is None:
        budget = [_MAX_NESTED_TOTAL]
    blocks, loose = _css_blocks(text, rules=not block, top=nesting == 0)
    if block and own and selectors is not None \
            and loose.strip(_CSS_WS + _COMMENT):
        out.append((selectors, loose, conditional, layered))
    if nesting >= _MAX_AT_NESTING:
        return
    for prelude, body in blocks:
        if prelude.startswith("@"):
            kind = _at_rule_kind(prelude, namespaces,
                                 bool(selectors) or bare)
            at = _AT_NAME_RE.match(prelude)
            in_scope = at is not None and _lower(
                _css_unescape(at.group(1))) == "scope"
            start = (_scope_start(_selectors_without_comments(prelude[
                at.end():]) or "") if in_scope and kind else None)
            if kind == "scope" or start:
                # Its rules hold below its root, as rules nested in the
                # root's would; `:scope` is the root (R5K-12); with a
                # limit, under a condition (R6X-1).
                inner = start
                if scope and selectors == scope:
                    # Directly in a rooted @scope, its `:scope` is the
                    # outer root, as `&` is: _nested writes it once
                    # (R6Z-1); a root outside the outer scope, none
                    # (_in_scope: R6Z-3).
                    inner = _in_scope(inner)
                    if inner is None:
                        continue
                    inner = _scope_as(inner, "&")
                elif scope:
                    if not _grows(budget, _scope_growth(inner, scope)):
                        continue
                    inner = _scope_as(inner, f":is({scope})")
                if selectors:
                    if not _grows(budget, _nested_growth(selectors, inner)):
                        continue
                    inner = _nested(selectors, inner)
                _style_walk(body, inner, conditional or kind != "scope",
                            layered, nesting + 1, out, scope=inner,
                            block=True, namespaces=namespaces, budget=budget)
            elif kind is not None:
                _style_walk(body, selectors,
                            conditional or kind == "conditional",
                            layered or kind == "layer", nesting + 1, out,
                            scope, block=nested or in_scope,
                            nested=nested and not in_scope,
                            namespaces=namespaces, own=not in_scope,
                            budget=budget, bare=bare or in_scope)
        elif prelude:
            prelude = _selectors_without_comments(prelude)
            # A top-level rule's members PageStyles._add reads again: here
            # only where rules nest in it, which an invalid one drops too.
            read = (prelude is not None
                    and _selectors_valid(prelude, namespaces)
                    and (not (selectors or "{" in body)
                         or _members_read(prelude, bool(selectors))))
            if not read:
                continue                # an invalid selector: no rule
            if bare and not selectors:
                prelude = _amp_as(_scope_as(prelude, ":not(*)"), ":not(*)")
            if scope:
                # In @scope, `:scope` is the root: a rule of the root's own
                # that names it is not also below it. A selector that
                # names it twice, or that starts with `+` or `~` (a
                # sibling of the root), matches nothing in it (R6X-5).
                if selectors == scope:
                    prelude = _in_scope(prelude)
                    if prelude is None:
                        continue
                    prelude = _scope_as(prelude, "&")
                elif not _grows(budget, _scope_growth(prelude, scope)):
                    continue
                else:
                    prelude = _scope_as(prelude, f":is({scope})")
            if selectors:
                if not _grows(budget, _nested_growth(selectors, prelude)):
                    continue
                inner = _nested(selectors, prelude)
                if scope and selectors == scope:
                    # What a rule in @scope styles is the root or below it
                    # (`:scope + .c` is outside: R6Z-3).
                    inside = f":where({scope}, {scope} *)"
                    parts = split_selectors(inner)
                    if not _grows(budget, len(parts) * (len(inside) + 5)):
                        continue
                    inner = ", ".join(f":is({m}){inside}" for m in parts)
            else:
                inner = prelude
            _style_walk(body, inner, conditional, layered, nesting + 1,
                        out, scope, block=True, nested=True,
                        namespaces=namespaces, budget=budget, bare=bare)


def _in_scope(selectors: str) -> str | None:
    """The members of `selectors`, a rule's directly in a rooted @scope,
    that may match there: not one that names `:scope` in two compounds
    (outside a function's argument: _scope_compounds), a relative one
    (`> :scope`) in one, nor one that starts with `+` or `~`, a sibling of
    the root, outside the scope (measured: R6X-5, R6Z-2); None where none
    may."""
    keep = []
    for member in split_selectors(selectors):
        lead = member[:1]
        times = _scope_compounds(member) + (lead in _COMBINATORS)
        if (lead and lead in "+~") or times > 1:
            continue
        keep.append(member)
    return ", ".join(keep) if keep else None


def _scope_compounds(member: str) -> int:
    """How many compounds of `member` name `:scope` outside a function's
    argument (`:not(:scope)` is no such one; `:scope:scope` one): R6Z-2."""
    marked = _scope_as(member, "\x00")
    count, seen, depth, i, n = 0, False, 0, 0, len(marked)
    while i < n:
        ch = marked[i]
        if ch == "\\":
            i = _skip_escape(marked, i)
            continue
        if ch in "\"'":
            i = _skip_string(marked, i)
            continue
        if ch == "[":
            i = _block_end(marked, i)[0]
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(depth - 1, 0)
        elif depth == 0 and (ch in _CSS_WS or ch in _COMBINATORS):
            seen = False
        elif depth == 0 and ch == "\x00" and not seen:
            count, seen = count + 1, True
        i += 1
    return count


def _grows(budget: list, growth: int) -> bool:
    """May a nested rule's selectors grow by `growth` characters as they
    are written out with its parents' (_nested): no more than _MAX_NESTED,
    nor than what `budget` (a page's stylesheets' in all) has left, which
    it then has less of?"""
    if growth > _MAX_NESTED or growth > budget[0]:
        return False
    budget[0] -= max(growth, 0)
    return True


def _members_read(selectors: str, relative: bool = True) -> bool:
    """Does soupsieve read each member of the selector list `selectors`
    (a style rule's, an @scope's root or limit) as _without_pseudos
    writes it, after `*` where it starts with a combinator and `relative`
    (a nested rule's, one in @scope)? One it does not read (`.a..b`,
    `#2:hover`, `.2col:focus`) Chromium 141 does not either, and drops
    the rule and the rules nested in it, as PageStyles._add drops a rule
    (R6H-6, R6T-2)."""
    for member in split_selectors(selectors):
        pieces = _without_pseudos(member)
        if relative and pieces and pieces[0][:1] in _COMBINATORS:
            pieces[0] = "* " + pieces[0]
        if not _pieces_read(pieces):
            return False        # an escaped flag read plainly (R6J-7)
    return True


def _name_character(ch: str) -> bool:
    """Can `ch` be part of a CSS name: an ASCII letter or digit, "-",
    "_", or any code point from U+0080?"""
    return bool(ch) and (ch in "-_" or "0" <= ch <= "9" or "a" <= ch <= "z"
                         or "A" <= ch <= "Z" or ch >= "\x80")


def _selectors_without_comments(text: str) -> str | None:
    """A selector list with each comment style_rules marked (_COMMENT)
    gone, as CSS reads one: no white space, so `.a/**/.b` is `.a.b`; None
    where one stands between two names (`di/**/v`, `.a/**/span`, and
    `.\\61 /**/b`, where the white space ends an escape of the name before:
    R6H-9), which makes the selector, and so the rule, invalid (measured
    in Chromium 141), but between :nth-child()'s or :nth-last-child()'s
    An+B and its `of`, which it separates (`2n/**/of .a`: R6J-7). In an
    attribute selector's brackets one separates as white space does
    (`[x=a/**/i]` is `[x=a i]`: R6H-4), white space no escape before it
    takes (`[x=\\61/**/i]` is `[x="a" i]`: R6J-7)."""
    if _COMMENT not in text:
        return text
    spans = _bracket_spans(text)
    starts = [a for a, _b in spans]
    out, last = [], 0
    for m in re.finditer(_COMMENT + "+", text):
        at = m.start()
        after = text[m.end()] if m.end() < len(text) else ""
        j = bisect.bisect_right(starts, at) - 1
        if j >= 0 and at < spans[j][1]:
            out += [text[last:at], "  "]
        elif at and _ends_name(text, at) and (_name_character(after)
                                               or after == "\\"):
            k = text.rfind("(", 0, at)
            head = _nth_open(text, k)
            if head is None or _lower(_css_unescape(head)) not in (
                    "nth-child", "nth-last-child") \
                    or not _ANB_ONLY.fullmatch(text, k + 1, at):
                return None
            out += [text[last:at], " "]
        elif at and after == "(" and _ends_name(text, at):
            # A name, then "(": no function (`to/**/(.b)`, `:not/**/(`), as
            # white space would make it (R6N-11).
            out += [text[last:at], " "]
        elif at and text[at - 1] == "+" and "0" <= after <= "9":
            # A "+", then a digit: two tokens, as white space would make
            # them (`:nth-child(+/**/1)` takes no An+B, `2n+/**/1` does:
            # measured, R6R-3).
            out += [text[last:at], " "]
        else:
            out.append(text[last:at])
        last = m.end()
    out.append(text[last:])
    return "".join(out)


def _nth_open(text: str, k: int) -> str | None:
    """The name of the pseudo-class whose argument opens at text[k], a "("
    (`:nth-child(`, escapes and all: R6L-10), or None: read from the last
    ":" before it, so a selector costs its length (R6N-10)."""
    colon = text.rfind(":", 0, k) if k >= 0 else -1
    m = _NTH_OPEN.match(text, colon) if colon >= 0 else None
    return m.group(1) if m is not None and m.end() == k + 1 else None


#: Where a pseudo-class's argument opens (`:nth-child(`, its name's
#: escapes read: R6L-10), and an An+B alone in it, or as far as a sign
#: before its B: a comment after one separates it from its `of`
#: (_selectors_without_comments), or the sign from the B. Comments (marked
#: _COMMENT) stand where white space may, and between a "+" and its `n`
#: (`+/**/n`; not `-/**/n` nor `2/**/n`, nor `+/**/1`, where the "+" is
#: no sign of the number: measured, R6P-6, R6R-3).
_NTH_OPEN = re.compile(":(" + _NAME + r")\(")
_ANB_ONLY = re.compile(
    "[ \t\n\r\f\x00]*(?:odd|even|(?:\\+\x00+n|[+-]?[0-9]*n)(?:"
    "[ \t\n\r\f\x00]*[+-](?:[ \t\n\r\f\x00]*[0-9]+)?)?|[+-]?[0-9]+)",
    re.I)


def _bracket_spans(text: str) -> list[tuple[int, int]]:
    """Where each attribute selector's brackets in `text` open and end
    (strings and escapes skipped), in order."""
    spans, k = [], 0
    while True:
        m = _CSS_SPECIAL.search(text, k)
        if m is None:
            return spans
        k = m.start()
        ch = text[k]
        if m.group("url") is not None:
            k = m.end()
        elif ch in "\"'":
            k = _skip_string(text, k)
        elif ch == "\\":
            k += 2
        elif ch == "[":
            end = _block_end(text, k)[0]
            spans.append((k, end))
            k = end
        else:
            k += 1


def _scope_growth(selector: str, scope: str) -> int:
    """How much longer `:scope` written as `:is(scope)` makes `selector`."""
    return selector.lower().count(":scope") * (len(scope) - 1)


def _nested(parent: str, child: str) -> str:
    """A nested rule's selector list as one that stands alone: `&` (not
    one in a string, an escape or an attribute selector: _amps) is the
    parent, and a selector without one, or one that starts with a
    combinator, comes after it, as CSS makes a relative selector absolute
    (`> &` is `& > &`: R6V-1)."""
    wrapped = f":is({parent})"
    out = []
    for c in split_selectors(child):
        amps = _amps(c)
        whole = _amp_as(c, wrapped, amps) if amps else c
        if not amps or c[:1] in _COMBINATORS:
            whole = f"{wrapped} {whole}"
        out.append(whole)
    return ", ".join(out)


def _amps(selector: str) -> list[int]:
    """Where each `&`, the nesting selector, stands in `selector`: not one
    in a string, an escape or an attribute selector."""
    if "&" not in selector:
        return []
    out, i, n = [], 0, len(selector)
    while i < n:
        ch = selector[i]
        if ch == "\\":
            i = _skip_escape(selector, i)
        elif ch in "\"'":
            i = _skip_string(selector, i)
        elif ch == "[":
            i = _block_end(selector, i)[0]
        else:
            if ch == "&":
                out.append(i)
            i += 1
    return out


def _amp_as(selector: str, repl: str, amps: list[int] | None = None) -> str:
    """`selector` with each `&` (_amps) written as `repl`."""
    if amps is None:
        amps = _amps(selector)
    if not amps:
        return selector
    out, last = [], 0
    for i in amps:
        out += [selector[last:i], repl]
        last = i + 1
    out.append(selector[last:])
    return "".join(out)


def _nested_growth(parent: str, child: str) -> int:
    """How much longer _nested(parent, child) would be than `child`,
    without writing it out."""
    wrapped = len(parent) + 5              # ":is(" parent ")"
    parts = split_selectors(child)
    total = 2 * max(0, len(parts) - 1)
    for c in parts:
        k = len(_amps(c))
        total += len(c) + k * (wrapped - 1)
        if not k or c[:1] in _COMBINATORS:
            total += wrapped + 1
    return total - len(child)


def _parens(text: str, i: int) -> int:
    """The index after the parenthesis that closes the one at text[i];
    len(text) + 1 when none does."""
    depth, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch in "\"'":
            i = _skip_string(text, i)
            continue
        if ch == "\\":
            i += 2
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return n + 1


#: `not`, `and` and `or` are words only with white space or a comment
#: (_COMMENT) after them: `not(` is a function, which CSS reads as false
#: (R5M-6); `not/**/(` is `not` (measured).
_SUPPORTS_WORD = re.compile(
    r"[ \t\n\r\f\x00]*(not|and|or)(?=[ \t\n\r\f\x00])", re.I)
_SUPPORTS_FUNCTION = re.compile(r"[ \t\n\r\f\x00]*([-\w]+)\(")
#: The tests @supports has as functions; any other function is false.
_SUPPORTS_FUNCTIONS = ("selector", "font-tech", "font-format")
#: A test of a declaration: its property's name, escapes and all
#: (`\64 isplay` is display: R6H-11), and its value.
_SUPPORTS_DECLARATION = re.compile(
    r"[ \t\n\r\f\x00]*(" + _NAME + r")[ \t\n\r\f\x00]*:(.*)\Z", re.S)


class _NoCondition(ValueError):
    """Not an @supports condition: a browser drops the rule (false)."""


def _supports(condition: str) -> bool | None:
    """Whether an @supports condition holds in Chromium 141: True, False,
    or None where the run cannot tell. A property Chromium does not have
    (css_properties.PROPERTIES: `foo`, `-moz-appearance`,
    `-webkit-touch-callout`) fails its test; one it has passes with a
    CSS-wide value or a var(), and display with a value Chromium takes
    (_valid_style_value) or not; any other value, selector() and the font
    tests cannot be told, nor a condition the run does not parse. `not`,
    `and` and `or` combine those as unknowns combine (R5K-4). A condition
    holding a "]", ")" or "}" that closes nothing, a bad string or a bad
    url anywhere drops its rule: False (measured: R6F-4). Its comments
    are marked (_COMMENT), as style_rules marks them."""
    if _top_level(condition, ""):
        return False
    try:
        held, rest = _supports_condition(condition, 0)
        if condition[rest:].strip(_CSS_WS + _COMMENT):
            raise _NoCondition("trailing")
    except _NoCondition:
        return False        # a condition CSS does not parse never holds
    except (ValueError, IndexError, RecursionError):
        return None
    return held


def _supports_condition(text: str, i: int, depth: int = 0):
    """(what the condition at text[i:] holds, where it ends)."""
    if depth > 32:
        raise ValueError("too deep")
    m = _SUPPORTS_WORD.match(text, i)
    if m and m.group(1).lower() == "not":
        held, i = _supports_in_parens(text, m.end(), depth)
        return (None if held is None else not held), i
    held, i = _supports_in_parens(text, i, depth)
    joined = None
    while True:
        m = _SUPPORTS_WORD.match(text, i)
        if not m or m.group(1).lower() == "not":
            return held, i
        word = m.group(1).lower()
        if joined not in (None, word):
            raise _NoCondition("and with or")   # invalid without parentheses
        joined = word
        other, i = _supports_in_parens(text, m.end(), depth)
        if word == "and":
            held = (False if held is False or other is False else
                    None if held is None or other is None else True)
        else:
            held = (True if held is True or other is True else
                    None if held is None or other is None else False)


def _supports_in_parens(text: str, i: int, depth: int):
    while i < len(text) and text[i] in " \t\n\r\f\x00":
        i += 1
    m = _SUPPORTS_FUNCTION.match(text, i)
    if m:
        end = _parens(text, m.end() - 1)
        if end > len(text):
            raise _NoCondition("unclosed")
        # selector(), font-tech() and font-format() cannot be told; any
        # other function is general-enclosed: false (`not(` included).
        return (None if m.group(1).lower() in _SUPPORTS_FUNCTIONS
                else False), end
    if i >= len(text) or text[i] != "(":
        raise _NoCondition("not a test")
    end = _parens(text, i)
    if end > len(text):
        raise _NoCondition("unclosed")
    inside = text[i + 1:end - 1]
    stripped = inside.strip(_CSS_WS + _COMMENT)
    if stripped.startswith("(") or _SUPPORTS_WORD.match(inside) \
            or _SUPPORTS_FUNCTION.match(inside):
        try:
            held, k = _supports_condition(inside, 0, depth + 1)
            if inside[k:].strip(_CSS_WS + _COMMENT):
                raise _NoCondition("trailing")
        except _NoCondition:
            return False, end   # general-enclosed: false, as CSS reads it
        return held, end
    decl = _SUPPORTS_DECLARATION.match(inside)
    if decl is None:
        return False, end       # general-enclosed: false, as CSS reads it
    return _supports_declaration(decl.group(1), decl.group(2)), end


def _top_level(value: str, chars: str) -> bool:
    """Does `value` hold one of `chars` outside its strings, escapes, url
    tokens and brackets, or what no declaration's value holds: a closer
    that closes no bracket it opened (`]`, `(]`), a bad string or a bad
    url (`url(a b)`) (measured: R6B-10, R6D-10)?"""
    scan = re.compile("(?P<url>" + _URL_OPEN + r")|[\"'\\()\[\]{}"
                      + re.escape(chars) + "]")
    stack: list[str] = []
    i = 0
    while True:
        m = scan.search(value, i)
        if m is None:
            return False
        i = m.start()
        if m.group("url") is not None:
            got = _url_token(value, i, m.end())
            if got is not None:
                if got[1]:
                    return True
                i = got[0]
                continue
            i = m.end() - 1             # a function's "("
        ch = value[i]
        if ch in "\"'":
            i, bad = _string_end(value, i)
            if bad:
                return True
            continue
        if ch == "\\":
            i += 2
            continue
        if ch in _CLOSERS:
            stack.append(_CLOSERS[ch])
        elif ch in ")]}":
            if not stack or ch != stack[-1]:
                return True
            stack.pop()
        elif not stack and ch in chars:
            return True
        i += 1


def _supports_declaration(name: str, value: str) -> bool | None:
    from .css_properties import PROPERTIES
    raw = _important(value)[0]
    name = _lower(_css_unescape(name))
    words = _value_words(raw)
    value = " ".join(words)
    if name.startswith("--"):
        # Any value, even none, but one with a ";" or a "!" of its own,
        # which no declaration holds: false (measured: `not (--x: a;b)`
        # holds: R6B-10). One holding a closer that closes nothing, a bad
        # string or a bad url drops the rule instead (_supports: R6F-4).
        return not _top_level(raw, ";!")
    if not value:
        return False
    if name not in PROPERTIES:
        return False
    if (len(words) == 1 and words[0] in _CSS_WIDE) \
            or re.search(r"\bvar\(", value):
        return True             # a var() is settled later: it parses
    if name == "display" and not re.search(r"\b(?:env|attr)\(", value):
        return _valid_style_value("display", value, words)
    return None


def _scope_start(rest: str) -> str | None:
    """The root selector of an @scope prelude that names a root, with a
    limit or not (`(main)`, `(main) to (.x)`), or None."""
    rest = rest.strip(_CSS_WS)
    if not rest.startswith("("):
        return None
    end = _parens(rest, 0)
    if end > len(rest):
        return None
    return rest[1:end - 1].strip(_CSS_WS) or None


def _scope_root(rest: str) -> str | None:
    """The root selector of an @scope prelude that names a root and no
    limit (`(main)`), or None (`(main) to (.x)`, or no root)."""
    rest = rest.strip(_CSS_WS)
    if not rest.startswith("("):
        return None
    depth, i, n = 0, 0, len(rest)
    while i < n:
        ch = rest[i]
        if ch in "\"'":
            i = _skip_string(rest, i)
            continue
        if ch == "\\":
            i += 2
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                inside = rest[1:i].strip(_CSS_WS)
                return inside if inside and not rest[i + 1:].strip(_CSS_WS) \
                    else None
        i += 1
    return None


#: @scope's `to`, before its limit: a name, its escapes read (R6L-10),
#: not a function's (`to(`: R6J-7).
_SCOPE_TO = re.compile(_NAME)


def _scope_valid(rest: str, namespaces: frozenset,
                 nested: bool = False) -> bool:
    """Is `rest`, an @scope's prelude, one Chromium 141 takes: nothing, or
    a root `(…)`, a limit `to (…)` or both, each a selector list it reads,
    as a function's, with no pseudo-element (_selectors_valid,
    _members_read: measured, R6H-5, R6J-7)? A root may start with a
    combinator only in a style rule (`nested`), a limit anywhere
    (measured: R6V-4)."""
    lists = []
    i = _CSS_SPACE.match(rest).end()
    n = len(rest)
    for limit in (False, True):
        if i >= n:
            break
        if limit:
            m = _SCOPE_TO.match(rest, i)
            if m is None or _lower(_css_unescape(m.group(0))) != "to" \
                    or rest.startswith("(", m.end()):
                return False
            i = _CSS_SPACE.match(rest, m.end()).end()
        elif not rest.startswith("(", i):
            continue
        if not rest.startswith("(", i):
            return False
        end = _parens(rest, i)
        if end > n:
            return False
        lists.append((rest[i + 1:end - 1], limit or nested))
        i = _CSS_SPACE.match(rest, end).end()
    return i >= n and all(_selectors_valid(x, namespaces, True)
                          and _members_read(x, relative)
                          for x, relative in lists)


def _at_rule_kind(prelude: str, namespaces: frozenset = frozenset(),
                  nested: bool = False) -> str | None:
    """How style_rules reads an at-rule's block: "always", "layer" (always,
    in a cascade layer), "conditional", "scope" (an @scope with a root and
    no limit), or None (not at all). `namespaces`: the prefixes the
    stylesheet declares; `nested`: the at-rule is in a style rule."""
    m = _AT_NAME_RE.match(prelude)
    name = _lower(_css_unescape(m.group(1))) if m else ""
    rest = prelude[m.end():] if m else ""
    if name == "layer":
        # A block's layer: none, or one name (`a.b`); any other prelude
        # (`a b`, `a, b`, `a }`) drops the rule (measured: R6F-2).
        rest = _selectors_without_comments(rest)
        rest = rest.strip(_CSS_WS) if rest is not None else "?"
        return "layer" if not rest or _LAYER_NAME.fullmatch(rest) else None
    if name == "media":
        # Where a comment was is marked, as style_rules marks it (R6D-5).
        return _media_kind(rest, raw=False)
    if name == "scope":
        # Its selectors as CSS reads them: one Chromium 141 does not take,
        # at its root or at its limit, drops it (R6H-5).
        rest = _selectors_without_comments(rest)
        if rest is None or not _scope_valid(rest, namespaces, nested):
            return None
        return "scope" if _scope_root(rest) else "conditional"
    if name == "supports":
        # As Chromium 141 settles it, as far as a property's name, or
        # display's value, settles it; else a condition (R5I-2, R5K-4).
        # Its comments stay marked: `\6e/**/one` is no `none` (R6F-7).
        held = _supports(rest.strip(_CSS_WS + _COMMENT))
        return ("always" if held is True else None if held is False
                else "conditional")
    if name == "container":
        # One Chromium 141 drops (a name it does not take, a condition it
        # does not read: _block_dropped) holds no rule (R6N-12).
        return None if _block_dropped("container", rest, "", namespaces) \
            else "conditional"
    return None


#: The media types a screen is.
_SCREEN_TYPES = ("all", "screen")



#: White space and comments (_COMMENT) around a media query's parts.
_MQ_WS = _CSS_WS + _COMMENT
_MQ_SPACE = re.compile("[ \t\n\r\f\x00]*")


def _trim(q: str, i: int, end: int) -> tuple[int, int]:
    """q[i:end]'s bounds without the white space and comments around it."""
    i = _MQ_SPACE.match(q, i, end).end()
    while end > i and q[end - 1] in _MQ_WS:
        end -= 1
    return i, end


def _ident_at(text: str, i: int, end: int) -> tuple | None:
    """(the ident at text[i:end], its escapes read, lowercased; the index
    after it), white space and comments before it skipped; None where none
    is, or it names a function (`and(`)."""
    i = _MQ_SPACE.match(text, i, end).end()
    m = _CSS_IDENT.match(text, i, end)
    if m is None or text.startswith("(", m.end(), end):
        return None
    name = m.group(0)
    if "\\" in name:
        name = _css_unescape(name)
    return _lower(name), m.end()


def _media_kind(queries: str, raw: bool = True) -> str | None:
    """"always" when one of the media queries holds on every screen (none
    at all, `all` or `screen`, with or without `only`; `not print`, or `not
    print and (…)`, which no screen fails), None when none can hold on a
    screen (a medium that is no screen, `print`, `tv`, `speech`, …; `not
    screen`, `not all`; a query a browser drops, as `only` alone, `and(`
    with no space, `or` after a medium, a "]", ")" or "}" that closes
    nothing, or anything left over), else "conditional" (R5I-2, R5K-12,
    R5M-5, R6D-10). An empty query in a list (`print, `) is one a browser
    drops; no query at all holds everywhere (R5O-8). A comment separates
    what is on its either side, as CSS reads one, and is no white space
    (R6D-5); a name or a keyword may hold escapes (`scr\\65 en`, `(hover:
    \\68over)`: R6D-3, R6D-4). `raw`: `queries` has its comments yet (a
    media attribute's), not marked as style_rules marks them."""
    if raw:
        queries = _without_comments(queries.replace(_COMMENT, "\ufffd"),
                                    _COMMENT)
    kinds = set()
    parts = (_top_level_split(queries) if queries.strip(_MQ_WS)
             else [""])
    for query in parts:
        kinds.add("never" if len(parts) > 1 and not query.strip(_MQ_WS)
                  else _MediaQuery(query.strip(_MQ_WS)).kind())
    return ("always" if "always" in kinds else
            "conditional" if "conditional" in kinds else None)


#: What a media query list's scanners read as more than a character: a
#: url token, a string, an escape, a bracket (and a comma).
_LIST_SPECIAL = re.compile("(?P<url>" + _URL_OPEN + r")|[\"'\\()\[\]{},]")
#: The same, at a declaration list's ";".
_DECLARATION_SPECIAL = re.compile("(?P<url>" + _URL_OPEN
                                  + r")|[\"'\\()\[\]{};]")
_BRACKET_SPECIAL = re.compile("(?P<url>" + _URL_OPEN + r")|[\"'\\()\[\]{}]")


def _top_level_split(text: str, sep: str = ",") -> list[str]:
    """`text` split at each "," (or ";": `sep`) outside its blocks,
    strings, escapes and url tokens, as CSS reads a comma-separated list
    (`(x: "a,b")` is one query). A closer that closes nothing is a
    character."""
    special = _LIST_SPECIAL if sep == "," else _DECLARATION_SPECIAL
    out, stack, i, start = [], [], 0, 0
    while True:
        m = special.search(text, i)
        if m is None:
            break
        i = m.start()
        if m.group("url") is not None:
            got = _url_token(text, i, m.end())
            if got is not None:
                i = got[0]
                continue
            i = m.end() - 1             # a function's "("
        ch = text[i]
        if ch in "\"'":
            i = _skip_string(text, i)
            continue
        if ch == "\\":
            i += 2
            continue
        if ch in _CLOSERS:
            stack.append(_CLOSERS[ch])
        elif ch in ")]}":
            if stack and stack[-1] == ch:
                stack.pop()
        elif not stack:
            out.append(text[start:i])
            start = i + 1
        i += 1
    out.append(text[start:])
    return out


_MEDIA_WORDS = ("not", "and", "or", "only")
_MEDIA_RESERVED = ("not", "and", "or", "only", "layer")
#: A media condition's possible values: true, false, or unknown (None).
_MAY_BE = frozenset((True, False))
_UNKNOWN = frozenset((None,))
#: A range's comparison, a comment perhaps between its "<" or ">" and its
#: "=" (R6D-5).
_RANGE_OPERATOR = re.compile("<\x00*=|>\x00*=|<|>|=")


def _paren_ends(text: str) -> tuple[dict, bool]:
    """({the index of each "(" in `text`: the index after the ")" that
    closes it, len(text) + 1 where none does}, whether `text` holds what
    no media query holds: a "]", ")" or "}" that closes nothing it opened
    (in a block of another kind too: `(x: [a)])`), a bad string or a bad
    url (measured: R6D-10)). Strings, escapes and url tokens are read as
    CSS reads them. One pass (R6B-6)."""
    ends, stack, i, broken = {}, [], 0, False
    while True:
        m = _BRACKET_SPECIAL.search(text, i)
        if m is None:
            break
        i = m.start()
        if m.group("url") is not None:
            got = _url_token(text, i, m.end())
            if got is not None:
                if got[1]:
                    broken = True
                    break
                i = got[0]
                continue
            i = m.end() - 1             # a function's "("
        ch = text[i]
        if ch in "\"'":
            i, bad = _string_end(text, i)
            if bad:
                broken = True
                break
            continue
        if ch == "\\":
            i += 2
            continue
        if ch in _CLOSERS:
            stack.append((i, _CLOSERS[ch]))
        elif not stack or stack[-1][1] != ch:
            broken = True
            break
        else:
            at, _closer = stack.pop()
            if ch == ")":
                ends[at] = i + 1
        i += 1
    for at, closer in stack:
        if closer == ")":
            ends[at] = len(text) + 1
    return ends, broken


def _kind_of(values: frozenset) -> str:
    return ("always" if values == frozenset((True,)) else
            "conditional" if True in values else "never")


def _not3(values: frozenset) -> frozenset:
    return frozenset(None if v is None else not v for v in values)


def _and3(a: frozenset, b: frozenset) -> frozenset:
    return frozenset(False if x is False or y is False else
                     None if x is None or y is None else True
                     for x in a for y in b)


def _or3(a: frozenset, b: frozenset) -> frozenset:
    return frozenset(True if x is True or y is True else
                     None if x is None or y is None else False
                     for x in a for y in b)


#: A function token: `foo(` (Media Queries 4's <general-enclosed>, which
#: a browser reads as unknown, not as an error: R5O-8).
_MEDIA_FUNCTION = re.compile(_CSS_NAME + r"\(")


def _groups(q: str, i: int, end: int, ends: dict) -> list:
    """[(where each "(" at q[i:end]'s own level is, the index after its
    ")")], what each holds passed over: one search a pair."""
    out = []
    p = q.find("(", i, end)
    while p != -1:
        close = ends.get(p)
        if close is None:               # in a string: no parenthesis
            p = q.find("(", p + 1, end)
            continue
        close = min(close, len(q))
        out.append((p, close))
        if close >= end:
            break
        p = q.find("(", close, end)
    return out


def _gaps(i: int, end: int, groups: list) -> list:
    """The stretches of q[i:end] outside `groups` (those of a stretch
    that holds it, in order)."""
    out, start = [], i
    for g0, g1 in groups:
        if g1 <= start:
            continue
        if g0 >= end:
            break
        out.append((start, g0))
        start = g1
    out.append((start, end))
    return [(a, b) for a, b in out if a < b]


def _find_outside(q: str, ch: str, i: int, end: int, groups: list):
    """The first `ch` in q[i:end] outside `groups`, or None."""
    for a, b in _gaps(i, end, groups):
        p = q.find(ch, a, b)
        if p != -1:
            return p
    return None


class _MediaQuery:
    """One media query (without white space around it), read as Media
    Queries 4 reads it on a screen. Where each of its parentheses closes
    is found once, and what each pair holds is read once, innermost
    first, without recursion, its own level only: what a pair inside it
    holds is passed over, never copied or read again (R6B-6, R6D-8)."""

    def __init__(self, q: str):
        self.q = q
        self.ends, self.broken = _paren_ends(q)
        #: {index of a "(": the values what it holds may take}
        self.held: dict[int, frozenset] = {}
        if self.broken:
            return
        n = len(q)
        for start in sorted(self.ends, key=lambda k: (self.ends[k], -k)):
            close = self.ends[start]
            self.held[start] = self.values(start + 1,
                                           close - 1 if close <= n else n)

    def kind(self) -> str:
        """"always", "conditional" or "never" (a query a browser drops,
        or one that can hold nowhere). Each part of a condition may be
        true, false or unknown (a function, or what parentheses hold that
        is no feature Chromium 141 knows with a value it takes: values());
        `not`, `and` and `or` combine them as Media Queries 4's
        three-valued logic does (false and unknown is false, so its `not`
        holds: R6B-5), and a query that ends unknown does not hold (R5Q-3,
        R5S-7)."""
        q, n = self.q, len(self.q)
        if not q:
            return "always"
        if self.broken:
            return "never"
        first = _ident_at(q, 0, n)
        word = first[0] if first and first[0] in _MEDIA_WORDS else None
        if word in ("and", "or"):
            return "never"
        rest = _MQ_SPACE.match(q, first[1]).end() if word == "not" else 0
        if q.startswith("(", rest) or _MEDIA_FUNCTION.match(q, rest):
            # A condition alone: `(…)`, `not (…)`, `(…) and (…)`, `(…) or
            # (…)`, a function among them.
            got = self.condition(0, n, allow_or=True)
            if got is None or _MQ_SPACE.match(q, got[0]).end() != n:
                return "never"
            return _kind_of(got[1])
        i = first[1] if word in ("not", "only") else 0
        medium = _ident_at(q, i, n)
        if medium is None or medium[0] in _MEDIA_RESERVED:
            return "never"
        values = frozenset((medium[0] in _SCREEN_TYPES,))
        i = _MQ_SPACE.match(q, medium[1]).end()
        if i < n:
            joint = _ident_at(q, i, n)
            if joint is None or joint[0] != "and":
                return "never"
            got = self.condition(joint[1], n, allow_or=False)
            if got is None or _MQ_SPACE.match(q, got[0]).end() != n:
                return "never"
            values = _and3(values, got[1])
        # `not` takes the whole query: no screen is print, so `not print
        # and (…)` holds on every screen, whatever the condition.
        return _kind_of(_not3(values) if word == "not" else values)

    def _word(self, i: int, end: int) -> tuple | None:
        got = _ident_at(self.q, i, end)
        return got if got and got[0] in _MEDIA_WORDS else None

    def condition(self, i: int, end: int, allow_or: bool) -> tuple | None:
        """(where the media condition at q[i:end] ends, the values it may
        take), or None when it is not one: `not (…)`, or `(…)` joined by
        `and`, or (`allow_or`) by `or`, not both (`and(` is a
        function)."""
        w = self._word(i, end)
        if w and w[0] == "not":
            got = self.in_parens(w[1], end)
            return None if got is None else (got[0], _not3(got[1]))
        got = self.in_parens(i, end)
        if got is None:
            return None
        i, values = got
        joined = None
        while True:
            w = self._word(i, end)
            if not w:
                return i, values
            if w[0] not in ("and", "or") or (w[0] == "or" and not allow_or) \
                    or joined not in (None, w[0]):
                return None
            joined = w[0]
            got = self.in_parens(w[1], end)
            if got is None:
                return None
            i = got[0]
            values = (_and3 if joined == "and" else _or3)(values, got[1])

    def in_parens(self, i: int, end: int) -> tuple | None:
        """(where `(…)` or a function `name(…)` at q[i:end] ends, the
        values it may take), or None. A function is unknown; so is what
        parentheses hold that is neither a media condition nor a feature
        Chromium 141 knows with a value it takes (values()). An unclosed
        parenthesis closes at the end, as a media attribute's does."""
        q, n = self.q, len(self.q)
        i = _MQ_SPACE.match(q, i, end).end()
        if i >= end:
            return None
        if q[i] != "(":
            f = _MEDIA_FUNCTION.match(q, i, end)
            close = None if f is None else self.ends.get(f.end() - 1)
            if close is None:           # none, or a url token
                return None
            return min(close, n), _UNKNOWN
        if i not in self.held:      # in a string: no parenthesis
            return None
        return min(self.ends[i], n), self.held[i]

    def values(self, i: int, end: int) -> frozenset:
        """The values what the parentheses around q[i:end] hold may take:
        a media condition's; a feature Chromium 141 knows, by name alone,
        with a value it takes, with min- or max- where it takes them, or
        compared in a range (true or false: a screen decides); anything
        else unknown (R5S-7, R6B-3, R6B-4). What parentheses in it hold
        has been read (held)."""
        q = self.q
        i, end = _trim(q, i, end)
        if i >= end:
            return _UNKNOWN
        w = self._word(i, end)
        if q[i] == "(" or _MEDIA_FUNCTION.match(q, i, end) \
                or (w and w[0] == "not"):
            got = self.condition(i, end, allow_or=True)
            if got and _MQ_SPACE.match(q, got[0], end).end() == end:
                return got[1]
            if q[i] == "(":
                return _UNKNOWN     # no feature or range starts so
            # No condition: a range may start with a value (calc(1px) <
            # width).
        groups = _groups(q, i, end, self.ends)
        colon = _find_outside(q, ":", i, end, groups)
        if colon is not None:
            if groups and groups[0][0] < colon:
                return _UNKNOWN     # no feature's name holds a parenthesis
            feature = _feature_name(q[i:colon])
            if feature is None:
                return _UNKNOWN
            if feature not in _MEDIA_VALUES:
                if feature[:4] not in ("min-", "max-") \
                        or feature[4:] not in _MEDIA_MIN_MAX:
                    return _UNKNOWN
                feature = feature[4:]
            return (_MAY_BE if _takes_at(feature, q, colon + 1, end,
                                         self.ends) else _UNKNOWN)
        if not groups:
            feature = _feature_name(q[i:end])
            if feature is not None:
                return (_MAY_BE if feature in _MEDIA_VALUES
                        and feature not in _MEDIA_NO_BOOLEAN else _UNKNOWN)
        return self.range_values(i, end, groups)

    def range_values(self, i: int, end: int, groups: list) -> frozenset:
        """A range at q[i:end]: `name op value`, `value op name`, or `value
        op name op value` with both operators `<`/`<=` or both `>`/`>=`;
        each value one the feature takes (min- and max- are no part of a
        range: measured). What parentheses hold is passed over."""
        q = self.q
        bounds, ops, start = [], [], i
        for a, b in _gaps(i, end, groups):
            for m in _RANGE_OPERATOR.finditer(q, a, b):
                bounds.append((start, m.start()))
                ops.append(m.group(0).replace(_COMMENT, ""))
                start = m.end()
        bounds.append((start, end))
        parts = [_trim(q, a, b) for a, b in bounds]
        if len(ops) not in (1, 2) or any(a >= b for a, b in parts):
            return _UNKNOWN

        def name(a: int, b: int) -> str | None:
            if any(a <= g0 < b for g0, _g1 in groups):
                return None
            return _feature_name(q[a:b])
        if len(ops) == 1:
            for (na, nb), (va, vb) in ((parts[0], parts[1]),
                                       (parts[1], parts[0])):
                feature = name(na, nb)
                if feature in _MEDIA_VALUES \
                        and _takes_at(feature, q, va, vb, self.ends):
                    return _MAY_BE
            return _UNKNOWN
        low, mid, high = parts
        feature = name(*mid)
        if not ({ops[0][0], ops[1][0]} <= {"<"} or {ops[0][0], ops[1][0]}
                <= {">"}) or "=" in (ops[0], ops[1]):
            return _UNKNOWN
        if feature in _MEDIA_VALUES \
                and _takes_at(feature, q, *low, self.ends) \
                and _takes_at(feature, q, *high, self.ends):
            return _MAY_BE
        return _UNKNOWN


#: The media features Chromium 141 knows, each with the values it takes
#: (measured: a query on one holds, or its `not` does; on another, or with
#: a value it does not take, neither does, as Media Queries 4 has an
#: unknown feature: R5S-7, R6B-3): a type, or its keywords.
_MQ_LENGTH, _MQ_NUMBER, _MQ_INTEGER = "length", "number", "integer"
_MQ_RATIO, _MQ_RESOLUTION, _MQ_BIT = "ratio", "resolution", "bit"
_MEDIA_VALUES = {
    "width": _MQ_LENGTH, "height": _MQ_LENGTH, "device-width": _MQ_LENGTH,
    "device-height": _MQ_LENGTH, "aspect-ratio": _MQ_RATIO,
    "device-aspect-ratio": _MQ_RATIO, "resolution": _MQ_RESOLUTION,
    "color": _MQ_INTEGER, "color-index": _MQ_INTEGER,
    "monochrome": _MQ_INTEGER, "horizontal-viewport-segments": _MQ_INTEGER,
    "vertical-viewport-segments": _MQ_INTEGER,
    "-webkit-device-pixel-ratio": _MQ_NUMBER,
    "-webkit-min-device-pixel-ratio": _MQ_NUMBER,
    "-webkit-max-device-pixel-ratio": _MQ_NUMBER,
    "-webkit-transform-3d": _MQ_NUMBER, "grid": _MQ_BIT,
    "orientation": frozenset(("portrait", "landscape")),
    "scan": frozenset(("interlace", "progressive")),
    "update": frozenset(("none", "slow", "fast")),
    "overflow-block": frozenset(("none", "scroll", "paged")),
    "overflow-inline": frozenset(("none", "scroll")),
    "color-gamut": frozenset(("srgb", "p3", "rec2020")),
    "pointer": frozenset(("none", "coarse", "fine")),
    "any-pointer": frozenset(("none", "coarse", "fine")),
    "hover": frozenset(("none", "hover")),
    "any-hover": frozenset(("none", "hover")),
    "prefers-reduced-motion": frozenset(("no-preference", "reduce")),
    "prefers-reduced-transparency": frozenset(("no-preference", "reduce")),
    "prefers-contrast": frozenset(("no-preference", "more", "less",
                                   "custom")),
    "prefers-color-scheme": frozenset(("light", "dark")),
    "forced-colors": frozenset(("none", "active")),
    "dynamic-range": frozenset(("standard", "high")),
    "scripting": frozenset(("none", "initial-only", "enabled")),
    "display-mode": frozenset(("browser", "fullscreen", "minimal-ui",
                               "standalone", "window-controls-overlay",
                               "picture-in-picture", "borderless",
                               "tabbed")),
    "device-posture": frozenset(("continuous", "folded")),
}
#: Those that take min- and max-; and those a name alone does not hold
#: (measured).
_MEDIA_MIN_MAX = frozenset((
    "width", "height", "device-width", "device-height", "aspect-ratio",
    "device-aspect-ratio", "resolution", "color", "color-index",
    "monochrome"))
_MEDIA_NO_BOOLEAN = frozenset((
    "dynamic-range", "-webkit-min-device-pixel-ratio",
    "-webkit-max-device-pixel-ratio"))
#: The units of a length and of a resolution Chromium 141 takes (measured).
_LENGTH_UNITS = frozenset((
    "px", "cm", "mm", "q", "in", "pt", "pc", "em", "rem", "ex", "rex", "ch",
    "rch", "ic", "ric", "cap", "rcap", "lh", "rlh", "vw", "vh", "vi", "vb",
    "vmin", "vmax", "svw", "svh", "svi", "svb", "svmin", "svmax", "lvw",
    "lvh", "lvi", "lvb", "lvmin", "lvmax", "dvw", "dvh", "dvi", "dvb",
    "dvmin", "dvmax", "cqw", "cqh", "cqi", "cqb", "cqmin", "cqmax"))
_RESOLUTION_UNITS = frozenset(("x", "dppx", "dpi", "dpcm"))
#: A CSS number: ASCII digits only.
_NUMBER = r"[+-]?(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?"
#: A number, a dimension (its unit a CSS name, escapes and all: R6D-4) or
#: a percentage.
_NUMERIC = re.compile(r"(" + _NUMBER + r")(%|" + _CSS_NAME + r")?\Z")


def _numeric(value: str) -> tuple | None:
    """(the number, its unit lowercased, its escapes read: "" for none,
    "%") of a number, dimension or percentage, or None."""
    m = _NUMERIC.match(value)
    if not m:
        return None
    unit = m.group(2) or ""
    if "\\" in unit:
        unit = _css_unescape(unit)
    return float(m.group(1)), _lower(unit)


#: What each unit a math function may hold makes it (CSS Values 4); any
#: other unit makes the function invalid.
_UNIT_TYPES = {**dict.fromkeys(_LENGTH_UNITS, "length"),
               **dict.fromkeys(_RESOLUTION_UNITS, "resolution"),
               **dict.fromkeys(("deg", "grad", "rad", "turn"), "angle"),
               "s": "time", "ms": "time", "hz": "frequency",
               "khz": "frequency", "%": "percent"}
#: A math function's tokens, as CSS reads them; a comment (_COMMENT) is
#: none, but ends what it follows.
_CALC_TOKEN = re.compile(
    r"(?P<ws>[ \t\n\r\f]+)"
    r"|(?P<sep>\x00+)"
    r"|(?P<num>[+-]?(?:[0-9]*\.[0-9]+|[0-9]+)(?:[eE][+-]?[0-9]+)?)"
    r"(?P<unit>%|" + _CSS_NAME + r")?"
    r"|(?P<func>" + _CSS_NAME + r")\("
    r"|(?P<ident>" + _CSS_NAME + r")"
    r"|(?P<punct>[(),*/+-])")
#: The constants a math function may hold, each a number.
_CALC_CONSTANTS = frozenset(("e", "pi", "infinity", "-infinity", "nan"))
_ROUNDING = frozenset(("nearest", "up", "down", "to-zero"))
#: How deep a math function's functions and parentheses may be nested:
#: as deep as Chromium 141 reads them (measured: 100 levels, the
#: function's own included); deeper is invalid.
_MAX_CALC_DEPTH = 100
_NUMBER_TYPE = ()


def _calc_tokens(text: str, start: int = 0,
                 end: int | None = None) -> list | None:
    """text[start:end]'s tokens: ("ws",), ("num", type), ("func", name),
    ("ident", name) or a punctuation character's own; None where some
    character is none of these, a unit is no unit a math function takes,
    or parentheses nest deeper than one may (read no further)."""
    out, i = [], start
    n = len(text) if end is None else end
    depth = 0
    while i < n:
        m = _CALC_TOKEN.match(text, i, n)
        if not m:
            return None
        if m.group("ws"):
            if not out or out[-1] != ("ws",):    # white space, a comment,
                out.append(("ws",))             # white space: one
        elif m.group("sep"):
            pass
        elif m.group("num"):
            unit = m.group("unit") or ""
            if "\\" in unit:
                unit = _css_unescape(unit)
            unit = _lower(unit)
            if not unit:
                out.append(("num", _NUMBER_TYPE))
            elif unit in _UNIT_TYPES:
                out.append(("num", ((_UNIT_TYPES[unit], 1),)))
            else:
                return None
        elif m.group("func") or m.group("ident"):
            kind = "func" if m.group("func") else "ident"
            name = m.group(kind)
            if "\\" in name:
                name = _css_unescape(name)
            out.append((kind, _lower(name)))
            if kind == "func":
                depth += 1
        else:
            punct = m.group("punct")
            out.append((punct,))
            depth += punct == "("
            depth -= punct == ")"
        if depth > _MAX_CALC_DEPTH + 1:
            return None
        i = m.end()
    return out


def _skip_ws(t: list, i: int) -> int:
    while i < len(t) and t[i][0] == "ws":
        i += 1
    return i


def _type_times(a: tuple, b: tuple, divide: bool) -> tuple:
    """The type of a product (or quotient) of values of types `a`, `b`."""
    powers = dict(a)
    for base, power in b:
        powers[base] = powers.get(base, 0) + (-power if divide else power)
    return tuple(sorted((k, v) for k, v in powers.items() if v))


def _calc_sum(t: list, i: int, depth: int) -> tuple | None:
    """(type, index after) of the sum at t[i], or None: products joined by
    "+" or "-" with white space on each side, all of one type."""
    got = _calc_product(t, i, depth)
    if got is None:
        return None
    kind, i = got
    while (i + 2 < len(t) and t[i][0] == "ws" and t[i + 1][0] in "+-"
           and t[i + 2][0] == "ws"):
        got = _calc_product(t, _skip_ws(t, i + 2), depth)
        if got is None or got[0] != kind:
            return None
        i = got[1]
    return kind, i


def _calc_product(t: list, i: int, depth: int) -> tuple | None:
    """(type, index after) of the product at t[i], or None: values joined
    by "*" or "/"."""
    got = _calc_value(t, i, depth)
    if got is None:
        return None
    kind, i = got
    while True:
        j = _skip_ws(t, i)
        if j >= len(t) or t[j][0] not in ("*", "/"):
            return kind, i
        got = _calc_value(t, _skip_ws(t, j + 1), depth)
        if got is None:
            return None
        kind, i = _type_times(kind, got[0], t[j][0] == "/"), got[1]


def _calc_value(t: list, i: int, depth: int) -> tuple | None:
    """(type, index after) of the value at t[i]: a number, a dimension, a
    percentage, a constant, a sum in parentheses or a math function."""
    if i >= len(t) or depth > _MAX_CALC_DEPTH:
        return None
    kind = t[i][0]
    if kind == "num":
        return t[i][1], i + 1
    if kind == "ident":
        return (_NUMBER_TYPE, i + 1) if t[i][1] in _CALC_CONSTANTS else None
    if kind == "func":
        return _calc_function(t, i, depth + 1)
    if kind != "(":
        return None
    got = _calc_sum(t, _skip_ws(t, i + 1), depth + 1)
    if got is None:
        return None
    j = _skip_ws(t, got[1])
    if j >= len(t):
        return got[0], j                # the end closes it
    return (got[0], j + 1) if t[j][0] == ")" else None


def _same_type(args: list):
    return args[0] if all(a == args[0] for a in args) else None


_ANGLE = (("angle", 1),)
#: Each math function Chromium 141 takes in a media query, with the type
#: it computes from its arguments' (CSS Values 4; None: invalid).
_MATH_FUNCTIONS = {
    "calc": lambda a: a[0] if len(a) == 1 else None,
    "-webkit-calc": lambda a: a[0] if len(a) == 1 else None,
    "min": _same_type, "max": _same_type, "hypot": _same_type,
    "clamp": lambda a: _same_type(a) if len(a) == 3 else None,
    "mod": lambda a: _same_type(a) if len(a) == 2 else None,
    "rem": lambda a: _same_type(a) if len(a) == 2 else None,
    # Two arguments of one type, or one number (R6D-9).
    "round": lambda a: (_same_type(a) if len(a) == 2 else
                        a[0] if len(a) == 1 and a[0] == () else None),
    "abs": lambda a: a[0] if len(a) == 1 else None,
    "sign": lambda a: () if len(a) == 1 else None,
    "sin": lambda a: () if len(a) == 1 and a[0] in ((), _ANGLE) else None,
    "cos": lambda a: () if len(a) == 1 and a[0] in ((), _ANGLE) else None,
    "tan": lambda a: () if len(a) == 1 and a[0] in ((), _ANGLE) else None,
    "asin": lambda a: _ANGLE if a == [()] else None,
    "acos": lambda a: _ANGLE if a == [()] else None,
    "atan": lambda a: _ANGLE if a == [()] else None,
    "atan2": lambda a: _ANGLE if len(a) == 2 and _same_type(a) is not None
    else None,
    "pow": lambda a: () if a == [(), ()] else None,
    "sqrt": lambda a: () if a == [()] else None,
    "exp": lambda a: () if a == [()] else None,
    "log": lambda a: () if a in ([()], [(), ()]) else None,
    "progress": lambda a: () if len(a) == 3 and _same_type(a) is not None
    else None,
}


def _calc_function(t: list, i: int, depth: int) -> tuple | None:
    """(type, index after) of the math function whose name is t[i], or
    None: its arguments, separated by commas, each a sum (round() may
    start with a rounding strategy), of types the function takes."""
    of = _MATH_FUNCTIONS.get(t[i][1])
    if of is None:
        return None
    j = _skip_ws(t, i + 1)
    if t[i][1] == "round" and j < len(t) and t[j][0] == "ident" \
            and t[j][1] in _ROUNDING:
        k = _skip_ws(t, j + 1)
        if k >= len(t) or t[k][0] != ",":
            return None
        j = _skip_ws(t, k + 1)
    args = []
    while True:
        got = _calc_sum(t, j, depth)
        if got is None:
            return None
        args.append(got[0])
        j = _skip_ws(t, got[1])
        if j >= len(t):
            break                       # the end closes it
        if t[j][0] == ")":
            j += 1
            break
        if t[j][0] != ",":
            return None
        j = _skip_ws(t, j + 1)
    kind = of(args)
    return None if kind is None else (kind, j)


#: The types a media query's value may have.
_MATH_TYPE_NAMES = {(): "number", (("length", 1),): "length",
                    (("resolution", 1),): "resolution"}


def _math_type(value: str, start: int = 0,
               end: int | None = None) -> str | None:
    """The type the math function value[start:end] computes, as CSS types
    it (CSS Values 4: `calc(1px * 2)` is a length, `calc(1px / 1px)` a
    number, `min(1px, 2)` invalid): "length", "resolution" or "number";
    None for no math function, an invalid one, or one of another type (a
    percentage, which a media query has no basis for, an angle, …). Read
    in place. Its value is not computed: where Chromium 141 checks one a
    math function computes as it reads the query (a number of 0 as a
    length, `grid`'s 0 or 1, a ratio's first number not negative), the
    type alone is read."""
    start, end = _trim(value, start, len(value) if end is None else end)
    m = _MEDIA_FUNCTION.match(value, start, end)
    if m is None:
        return None
    name = m.group(0)[:-1]
    if _lower(_css_unescape(name) if "\\" in name else name) \
            not in _MATH_FUNCTIONS:
        return None
    t = _calc_tokens(value, start, end)
    got = _calc_function(t, 0, 1) if t else None
    if got is None or _skip_ws(t, got[1]) != len(t):
        return None
    return _MATH_TYPE_NAMES.get(got[0])


def _value_at(q: str, s: int, e: int, ends: dict):
    """What the value q[s:e] is, read in place: ("math", its type: a math
    function that is all of it, _math_type), ("text", the text: one that
    holds no parentheses), or None (parentheses no math function opens,
    which no media value holds: R6D-8)."""
    s, e = _trim(q, s, e)
    if s >= e:
        return None
    groups = _groups(q, s, e, ends)
    if not groups:
        return "text", q[s:e]
    if len(groups) == 1 and groups[0][1] == e \
            and _MEDIA_FUNCTION.match(q, s, groups[0][0] + 1):
        return "math", _math_type(q, s, e)
    return None


def _keyword(text: str) -> str | None:
    """The keyword `text` is, its escapes read (`\\68over`: R6D-3),
    lowercased; None for no ident."""
    if not _CSS_IDENT.fullmatch(text):
        return None
    return _lower(_css_unescape(text) if "\\" in text else text)


def _takes_at(feature: str, q: str, s: int, e: int, ends: dict) -> bool:
    """Does `feature` (a key of _MEDIA_VALUES) take the value q[s:e], as
    Chromium 141 reads it (measured)? Read in place (_value_at)."""
    kind = _MEDIA_VALUES[feature]
    if kind == _MQ_RATIO:
        # A number, or (measured) a length or a resolution, not negative;
        # then "/" and a number not negative.
        s, e = _trim(q, s, e)
        groups = _groups(q, s, e, ends)
        slash = _find_outside(q, "/", s, e, groups)
        if slash is None:
            return _ratio_first(_value_at(q, s, e, ends))
        if _find_outside(q, "/", slash + 1, e, groups) is not None:
            return False
        if not _ratio_first(_value_at(q, s, slash, ends)):
            return False
        second = _value_at(q, slash + 1, e, ends)
        if second is None:
            return False
        if second[0] == "math":
            return second[1] == "number"
        got = _numeric(second[1])
        return got is not None and got[0] >= 0 and not got[1]
    value = _value_at(q, s, e, ends)
    if value is None:
        return False
    if isinstance(kind, frozenset):
        # A keyword, in any case, its escapes read (R6D-3).
        return value[0] == "text" and _keyword(value[1]) in kind
    if value[0] == "math":
        return value[1] == {_MQ_LENGTH: "length",
                            _MQ_RESOLUTION: "resolution"}.get(kind, "number")
    text = value[1]
    got = _numeric(text)
    if got is None:
        return False
    number, unit = got
    if kind == _MQ_LENGTH:
        return unit in _LENGTH_UNITS or (not unit and number == 0)
    if kind == _MQ_RESOLUTION:
        return unit in _RESOLUTION_UNITS and number >= 0
    if unit:
        return False
    if kind == _MQ_INTEGER:
        return bool(re.fullmatch(r"[+-]?[0-9]+", text))
    if kind == _MQ_BIT:
        return number in (0, 1)
    return True                                  # a number


def _ratio_first(value) -> bool:
    """Is `value` (_value_at) a ratio's first part: a number, a length or
    a resolution, not negative (measured)?"""
    if value is None:
        return False
    if value[0] == "math":
        return value[1] is not None
    got = _numeric(value[1])
    return got is not None and got[0] >= 0 and (
        not got[1] or got[1] in _LENGTH_UNITS or got[1] in _RESOLUTION_UNITS)


def _feature_name(text: str) -> str | None:
    """The media feature `text` names, its escapes read (`\\77 idth`:
    R6D-4), lowercased, or None for no name."""
    text = text.strip(_MQ_WS)
    if not _CSS_IDENT.fullmatch(text):
        return None
    return _lower(_css_unescape(text) if "\\" in text else text)


def split_selectors(selectors: str, keep_empty: bool = False) -> list[str]:
    """A selector list split at its top-level commas (not one in brackets,
    a string or an escape: `.a\\,b` is one class); an empty member is
    left out unless `keep_empty`. A ")" closes only a "(", a "]" only a
    "[" (`:where(], .q)` is one member: R6R-2); braces and url() tokens
    in a selector are not read as blocks (L122)."""
    out, opened, start, i, n = [], [], 0, 0, len(selectors)
    while i < n:
        ch = selectors[i]
        if ch == "\\":
            i = _skip_escape(selectors, i)
            continue
        if ch in "\"'":
            i = _skip_string(selectors, i)
            continue
        if ch in "([":
            opened.append(ch)
        elif ch in ")]":
            if opened and opened[-1] == ("(" if ch == ")" else "["):
                opened.pop()
        elif ch == "," and not opened:
            out.append(selectors[start:i].strip(_CSS_WS))
            start = i + 1
        i += 1
    out.append(selectors[start:].strip(_CSS_WS))
    return out if keep_empty else [x for x in out if x]


#: The pseudo-classes Chromium 141 reads in a page's stylesheet: by name
#: alone (with the four pseudo-elements CSS 2 wrote with one colon), and
#: as functions; and its pseudo-elements: by name alone (any `::-webkit-`
#: one too) and as functions (measured: any other, as `:foo`,
#: `:-moz-any-link`, `::-moz-selection`, `:hover()` or `:is` alone, makes
#: the selector, and so its rule, invalid: R6F-3).
_PSEUDO_CLASSES = frozenset("""
    active any-link autofill checked default defined disabled empty enabled
    first-child first-of-type focus focus-visible focus-within fullscreen
    future host hover in-range indeterminate invalid last-child last-of-type
    link modal only-child only-of-type open optional out-of-range past
    picture-in-picture placeholder-shown popover-open read-only read-write
    required root scope target target-current user-invalid user-valid valid
    visited xr-overlay active-view-transition window-inactive horizontal
    vertical decrement increment start end double-button single-button
    no-button corner-present -webkit-any-link -webkit-autofill -webkit-drag
    -webkit-full-screen -webkit-full-screen-ancestor -webkit-full-page-media
    -internal-autofill-selected -internal-autofill-previewed
    -internal-dialog-in-top-layer -internal-popover-in-top-layer
    -internal-selector-fragment-anchor -internal-relative-anchor before after
    first-line first-letter
    """.split())
_PSEUDO_CLASS_FUNCTIONS = frozenset("""
    dir has host host-context is lang not nth-child nth-last-child
    nth-of-type nth-last-of-type state where active-view-transition-type
    -webkit-any""".split())
_PSEUDO_ELEMENTS = frozenset("""
    after backdrop before cue file-selector-button first-letter first-line
    grammar-error marker placeholder selection spelling-error target-text
    view-transition details-content picker-icon checkmark column
    scroll-marker scroll-marker-group interest-hint
    -internal-media-controls-overlay-cast-button""".split())
_PSEUDO_ELEMENT_FUNCTIONS = frozenset("""
    cue highlight part slotted picker scroll-button view-transition-group
    view-transition-image-pair view-transition-new view-transition-old
    view-transition-group-children""".split())
#: The pseudo-elements CSS 2 wrote with one colon.
_LEGACY_ELEMENTS = frozenset(("before", "after", "first-line",
                              "first-letter"))
#: The forgiving selector lists: a member Chromium does not read is left
#: out of one, and the selector stands.
_FORGIVING = frozenset(("is", "where"))
_NO_ARGUMENTS = re.compile(r"\([ \t\n\r\f]*\)")
#: What may follow a pseudo-element in its compound, as Chromium 141 reads
#: it (measured): :is() and :where() (not after ::slotted() or ::column),
#: and these pseudo-classes and pseudo-elements; after ::part(),
#: ::details-content and ::picker(), any that says nothing of where an
#: element stands in the tree (_TREE_STATES) but ::part(), ::slotted(),
#: ::cue() with an argument (R6J-7) and :-webkit-any() (R6N-6); a :not()
#: after any of them, holding only what may follow it (_follows);
#: after another `::-webkit-` one, those a user's action sets; after
#: ::cue() with an argument, none (R6H-2, R6H-4). Nothing else: no
#: combinator (`::before .a`), no other part of a compound (`::before.a`).
_USER_ACTION = frozenset(("hover", "active", "focus", "focus-visible",
                          "focus-within"))
_SCROLLBAR_STATES = frozenset((
    "hover", "active", "disabled", "enabled", "window-inactive",
    "horizontal", "vertical", "decrement", "increment", "start", "end",
    "double-button", "single-button", "no-button", "corner-present"))
_TREE_STATES = frozenset((
    "first-child", "last-child", "only-child", "first-of-type",
    "last-of-type", "only-of-type", "nth-child", "nth-last-child",
    "nth-of-type", "nth-last-of-type", "empty", "root", "scope", "host",
    "host-context", "has", "not", "horizontal", "vertical", "decrement",
    "increment", "start", "end", "double-button", "single-button",
    "no-button", "corner-present"))
_AFTER_ELEMENT = {
    "before": {"marker"}, "after": {"marker"},
    "selection": {"window-inactive"},
    "file-selector-button": _USER_ACTION, "cue": _USER_ACTION,
    "scroll-marker": _USER_ACTION | {"target-current"},
    "scroll-button": _USER_ACTION | {"disabled", "enabled"},
    "scroll-marker-group": {"focus-within"},
    "column": {"scroll-marker"},
    "slotted": {"marker", "before", "after", "placeholder",
                "file-selector-button", "details-content", "backdrop",
                "checkmark", "picker-icon", "picker"},
    **dict.fromkeys(("view-transition-group", "view-transition-image-pair",
                     "view-transition-new", "view-transition-old",
                     "view-transition-group-children"), {"only-child"}),
}
_ANY_STATE = frozenset(("part", "details-content", "picker"))
#: An attribute selector's namespace prefix (`[svg|href]`).
_ATTRIBUTE_PREFIX = re.compile(_NAME + r"\|(?!=)")
#: A stylesheet that declares namespaces (`@namespace svg url(…)`).
_NAMESPACE_RULE = re.compile(r"@namespace\b", re.I)


#: The at-rules Chromium 141 has that hold a block, past which an
#: @namespace is no rule (measured: R6H-8).
_BLOCK_AT_RULES = frozenset((
    "media", "supports", "container", "scope", "layer", "keyframes",
    "-webkit-keyframes", "page", "property", "font-face", "counter-style",
    "font-feature-values", "font-palette-values", "starting-style",
    "position-try", "view-transition", "function"))
_STRING_BODY = r"(?:[^{q}\\\n\r\f]|\\[\s\S])*"
#: An @namespace rule's prelude: a prefix or none, then the namespace's
#: URI as a string or a url().
_NAMESPACE_PRELUDE = re.compile(
    "[ \t\n\r\f\x00]*(?:(?P<prefix>" + _NAME + ")[ \t\n\r\f\x00]*)?(?:"
    "\"(?P<s1>" + _STRING_BODY.format(q='"') + ")\"|'(?P<s2>"
    + _STRING_BODY.format(q="'") + ")'|" + _URL_OPEN + "[ \t\n\r\f]*(?:\""
    "(?P<u1>" + _STRING_BODY.format(q='"') + ")\"|'(?P<u2>"
    + _STRING_BODY.format(q="'") + r")'|(?P<u3>[^\"'()\s\\]*))"
    r"[ \t\n\r\f]*\))[ \t\n\r\f\x00]*\Z")
_URL_OPEN_RE = re.compile(_URL_OPEN)
#: CSS white space and comments (_COMMENT) around a prelude's parts.
_PRELUDE_WS = "[ \t\n\r\f\x00]*"
#: A prelude of one name (_block_dropped).
_ONE_NAME_PRELUDE = re.compile(_PRELUDE_WS + "(" + _NAME + ")" + _PRELUDE_WS
                               + r"\Z")
#: A prelude of one string (_block_dropped).
_ONE_STRING_PRELUDE = re.compile(
    _PRELUDE_WS + "(?:\"" + _STRING_BODY.format(q='"') + "\"|'"
    + _STRING_BODY.format(q="'") + "')" + _PRELUDE_WS + r"\Z")
#: An @page prelude: a name, a pseudo-page right after it (a comment may
#: stand between), both, or neither (_block_dropped).
_PAGE_PRELUDE = re.compile(_PRELUDE_WS + "(" + _NAME + ")?(?:\x00*:("
                           + _NAME + "))?" + _PRELUDE_WS + r"\Z")
#: The names an @counter-style may not take, in any case (measured in
#: Chromium 141: R6J-6).
_COUNTER_STYLE_RESERVED = frozenset((
    "none", "decimal", "disc", "square", "circle", "disclosure-open",
    "disclosure-closed", "default")) | _CSS_WIDE
#: The names no family name an @font-feature-values takes starts with:
#: the generic families Chromium 141 has (measured: R6L-5, R6N-3).
_GENERIC_FAMILIES = frozenset((
    "serif", "sans-serif", "cursive", "fantasy", "monospace", "system-ui",
    "math", "-webkit-body"))
#: The names no custom-ident may be, so no family name of one name, nor a
#: view transition's name or class: default and CSS's wide keywords (in
#: any case, escapes read: measured, R6N-3, R6N-7).
_NOT_IDENTS = frozenset(("default",)) | _CSS_WIDE
#: The names no @container takes as its container's (measured: R6J-6,
#: R6L-6).
_CONTAINER_NOT_NAMES = frozenset(("none", "and", "or", "not", "default")) \
    | _CSS_WIDE
#: The types an @function's `returns` names between "<" and ">", in their
#: case (with a "#" or "+" after it, or not, but <transform-list>): the
#: syntax's components (R6L-6, R6N-4).
_SYNTAX_TYPES = frozenset((
    "angle", "color", "custom-ident", "image", "integer", "length",
    "length-percentage", "number", "percentage", "resolution", "string",
    "time", "transform-function", "transform-list", "url"))
#: A part of a prelude, as _prelude_parts reads it: a function or a
#: parenthesized block (read whole), a string, a name, a comma, or any
#: other character.
_PRELUDE_PART = re.compile(
    "(?P<function>" + _NAME + r")\(|(?P<paren>\()|(?P<string>\""
    + _STRING_BODY.format(q='"') + "\"|'" + _STRING_BODY.format(q="'")
    + "')|(?P<name>" + _NAME + ")|(?P<comma>,)|(?P<other>[^ \t\n\r\f\x00])")


def _prelude_parts(prelude: str) -> list | None:
    """The parts of an at-rule's prelude, white space and comments left
    out, in linear time: (kind, its text, its name unescaped and
    lowercased for a name or a function, what a function or a block
    holds); None where a function or a block is not closed."""
    out = []
    i, n = 0, len(prelude)
    while True:
        i = _CSS_SPACE_COMMENT.match(prelude, i).end()
        if i >= n:
            return out
        m = _PRELUDE_PART.match(prelude, i)
        kind = m.lastgroup
        if kind in ("function", "paren"):
            end = _parens(prelude, m.end() - 1)
            if end > n:
                return None
            name = (_lower(_css_unescape(m.group("function")))
                    if kind == "function" else "")
            out.append((kind, prelude[i:end], name,
                        prelude[m.end():end - 1]))
            i = end
            continue
        name = (_lower(_css_unescape(m.group("name")))
                if kind == "name" else "")
        out.append((kind, m.group(0), name, ""))
        i = m.end()


_CSS_SPACE_COMMENT = re.compile(_PRELUDE_WS)


def _condition_parts(parts: list) -> bool:
    """Do `parts` make a container condition Chromium 141 takes: `not`
    and a block or a function, or blocks and functions joined by `and`
    alone or by `or` alone (measured: R6J-6)?"""
    if parts and parts[0][0] == "name" and parts[0][2] == "not":
        return len(parts) == 2 and parts[1][0] in ("function", "paren")
    joined = None
    for k, part in enumerate(parts):
        if k % 2 == 0:
            if part[0] not in ("function", "paren"):
                return False
        elif part[0] != "name" or part[2] not in ("and", "or") \
                or joined not in (None, part[2]):
            return False
        else:
            joined = part[2]
    return bool(parts) and len(parts) % 2 == 1


def _block_dropped(name: str, prelude: str, body: str,
                   namespaces: frozenset) -> bool:
    """Does Chromium 141 drop the at-rule `name` that holds a block for
    its prelude (`prelude`, comments marked: _COMMENT) or what its block
    (`body`) holds, so that it is no rule an @namespace must stand before
    (measured: R6J-6)? An @layer or an @scope it does not take
    (_at_rule_kind); an @supports whose condition it does not parse
    (`@supports foo`, not one that fails); an @font-face, an
    @starting-style or an @view-transition with a prelude; an
    @position-try or an @font-palette-values with other than one name
    starting "--"; an @counter-style with other than one name, or one it
    may not take (_COUNTER_STYLE_RESERVED); an @keyframes with other than
    one name (an @-webkit-keyframes: or one string); an @page with other
    than a name, a pseudo-page (:first, :left, :right) right after it,
    both or neither; an @container with other than a name (but none, and,
    or, not, default or a CSS-wide keyword) and a condition
    (_condition_parts), or a condition alone; an @font-feature-values with
    other than a list of family names (a string, or names), commas
    between, none starting with a generic family (_GENERIC_FAMILIES), none
    of one name that is default or a CSS-wide keyword (_NOT_IDENTS: R6N-3);
    an @function with other than a function whose parameters start "--"
    (then `returns` and one type, _one_type: R6N-4, or nothing); an
    @property with other than one name starting "--", or without a
    string's syntax, an inherits true or false, or an initial-value where
    its syntax is not "*". Whether an @property's
    initial-value is one its syntax takes, or its syntax one Chromium
    reads, is not read: such one is read as kept (L116); so is an
    @media, whatever its queries."""
    if name in ("layer", "scope"):
        return _at_rule_kind("@" + name + prelude, namespaces) is None
    if name == "supports":
        return not _supports_parses(prelude.strip(_CSS_WS + _COMMENT))
    if name in ("font-face", "starting-style", "view-transition"):
        return bool(prelude.strip(_CSS_WS + _COMMENT))
    one = _ONE_NAME_PRELUDE.match(prelude)
    own = _lower(_css_unescape(one.group(1))) if one else None
    if name in ("position-try", "font-palette-values"):
        return own is None or not own.startswith("--")
    if name == "counter-style":
        return own is None or own in _COUNTER_STYLE_RESERVED
    if name == "keyframes":
        return own is None
    if name == "-webkit-keyframes":
        return own is None and not _ONE_STRING_PRELUDE.match(prelude)
    if name == "page":
        page = _PAGE_PRELUDE.match(prelude)
        return page is None or (page.group(2) is not None and _lower(
            _css_unescape(page.group(2))) not in ("first", "left", "right"))
    if name == "property":
        return own is None or not own.startswith("--") \
            or not _property_kept(body)
    parts = _prelude_parts(prelude)
    if parts is None:
        return True
    if name == "container":
        if parts and parts[0][0] == "name" and parts[0][2] not in \
                _CONTAINER_NOT_NAMES:
            parts = parts[1:]
        return not _condition_parts(parts)
    if name == "font-feature-values":
        family: list = []
        for part in parts + [("comma", ",", "", "")]:
            if part[0] != "comma":
                family.append(part)
                continue
            if not family or (len(family) > 1 and any(
                    p[0] != "name" for p in family)) or family[0][0] not in (
                    "name", "string") or family[0][2] in _GENERIC_FAMILIES \
                    or (len(family) == 1 and family[0][2] in _NOT_IDENTS):
                return True
            family = []
        return False
    if name == "function":
        if not parts or parts[0][0] != "function":
            return True
        inner = parts[0][3]
        if inner.strip(_CSS_WS + _COMMENT) and not all(
                p.strip(_CSS_WS + _COMMENT).startswith("--")
                for p in _top_level_split(inner)):
            return True
        rest = parts[1:]
        if not rest:
            return False
        if rest[0][:1] != ("name",) or rest[0][2] != "returns":
            return True
        # What follows `returns`, white space and all (_one_type).
        at = prelude.index(parts[0][1]) + len(parts[0][1])
        at = prelude.index(rest[0][1], at) + len(rest[0][1])
        return not _one_type(prelude[at:])
    return False


#: A token of an @function's `returns` type (_type_tokens): white space,
#: a comment's mark (_COMMENT), a function (read whole: _parens), a name,
#: a string, or any other character.
_TYPE_TOKEN = re.compile(
    r"(?P<ws>[ \t\n\r\f]+)|(?P<mark>\x00+)|(?P<function>" + _NAME
    + r")\(|(?P<name>" + _NAME + ")|(?P<string>\"" + _STRING_BODY.format(
        q='"') + "\"|'" + _STRING_BODY.format(q="'") + "')|(?P<other>.)",
    re.S)


def _type_tokens(text: str) -> list | None:
    """`text` as tokens (kind, value: a name's unescaped, a function's
    unescaped and lowercased, a function's what it holds too), comments
    left out (a comment separates, but is no white space); None where a
    function is not closed."""
    out, i, n = [], 0, len(text)
    while i < n:
        m = _TYPE_TOKEN.match(text, i)
        kind = m.lastgroup
        if kind == "function":
            end = _parens(text, m.end() - 1)
            if end > n:
                return None
            out.append(("function", _lower(_css_unescape(m.group(kind))),
                        text[m.end():end - 1]))
            i = end
            continue
        if kind == "name":
            out.append(("name", _css_unescape(m.group(kind)), ""))
        elif kind != "mark":
            out.append((kind, m.group(0), ""))
        i = m.end()
    return out


def _one_type(text: str) -> bool:
    """Is `text` (after `returns`) one type as an @function's `returns`
    takes it, as Chromium 141 reads one (measured: R6L-6, R6N-4): white
    space around it; a component (_component_ok), or type() holding a
    syntax (_syntax_ok)?"""
    tokens = _type_tokens(text)
    if tokens is None:
        return False
    while tokens and tokens[0][0] == "ws":
        tokens.pop(0)
    while tokens and tokens[-1][0] == "ws":
        tokens.pop()
    if len(tokens) == 1 and tokens[0][:2] == ("function", "type"):
        return _syntax_ok(tokens[0][2])
    return _component_ok(tokens)


def _component_ok(tokens: list) -> bool:
    """Are `tokens` one syntax component: a name that may be a custom-ident
    (_NOT_IDENTS: no CSS-wide keyword, no default), or a syntax's type
    between "<" and ">" (_SYNTAX_TYPES, in its case, no white space
    inside), with a "#" or a "+" after it, no white space before (but on
    <transform-list>), or not (measured: R6N-4)?"""
    values = [(k, v) for k, v, _inner in tokens]
    if values and values[-1] in (("other", "#"), ("other", "+")):
        values.pop()
        multiplied = True
    else:
        multiplied = False
    if len(values) == 1:
        kind, value = values[0]
        return kind == "name" and _lower(value) not in _NOT_IDENTS
    return (len(values) == 3 and values[0] == ("other", "<")
            and values[2] == ("other", ">") and values[1][0] == "name"
            and values[1][1] in _SYNTAX_TYPES
            and not (multiplied and values[1][1] == "transform-list"))


def _syntax_ok(text: str) -> bool:
    """Is `text`, what an @function's type() holds, a syntax Chromium 141
    takes: `*` alone, or components (_component_ok) with `|` between,
    white space around each (measured: R6N-4)?"""
    tokens = _type_tokens(text)
    if tokens is None:
        return False
    pieces: list = [[]]
    for token in tokens:
        if token[:2] == ("other", "|"):
            pieces.append([])
        else:
            pieces[-1].append(token)
    for piece in pieces:
        while piece and piece[0][0] == "ws":
            piece.pop(0)
        while piece and piece[-1][0] == "ws":
            piece.pop()
    if len(pieces) == 1 and [t[:2] for t in pieces[0]] == [("other", "*")]:
        return True
    return all(piece and _component_ok(piece) for piece in pieces)


def _property_kept(body: str) -> bool:
    """Does an @property's block hold what Chromium 141 requires (R6J-6):
    a syntax that is one string, an inherits true or false, and an
    initial-value where the syntax is not "*"?"""
    got: dict = {}
    for decl in _top_level_split(body, ";"):
        name, colon, value = decl.partition(":")
        if colon:
            got[_lower(_css_unescape(name.strip(_CSS_WS + _COMMENT)))] = \
                value.strip(_CSS_WS + _COMMENT)
    syntax = _ONE_STRING_PRELUDE.match(got.get("syntax", ""))
    if syntax is None or _lower(got.get("inherits", "")) not in (
            "true", "false"):
        return False
    return "initial-value" in got or _css_unescape(
        got["syntax"].strip(_CSS_WS + _COMMENT)[1:-1]).strip(
            _CSS_WS) == "*"


def _supports_parses(condition: str) -> bool:
    """Does Chromium 141 parse `condition`, an @supports rule's (comments
    marked), as one, true or false (_supports)?"""
    if _top_level(condition, ""):
        return False
    try:
        _held, rest = _supports_condition(condition, 0)
    except _NoCondition:
        return False
    except (ValueError, IndexError, RecursionError):
        return True
    return not condition[rest:].strip(_CSS_WS + _COMMENT)


def _import_dropped(prelude: str) -> bool:
    """Does Chromium 141 drop the @import whose prelude (from its URL on)
    is `prelude`: one whose supports() fails (`supports(foo: bar)`) or does
    not parse (`supports(foo)`), as _supports reads it (measured: R6J-6)?"""
    for kind, _text, name, inner in _prelude_parts(prelude) or ():
        if kind == "function" and name == "supports":
            return _supports("(" + inner + ")") is False
    return False


def style_namespaces(css: str) -> dict:
    """The namespaces a stylesheet declares, as Chromium 141 reads them
    (measured: R6H-8): {a prefix, or "" for the default namespace: its
    URI}. An @namespace counts before any rule but @charset, @import, an
    @layer statement before the first @import or @namespace, an unknown
    at-rule (`@foo;`) and a rule a browser drops (`.a..b{}`, `@media;`, an
    @import whose supports() fails, an at-rule with a block whose prelude
    Chromium does not take: _block_dropped, R6J-6); a later one of a
    prefix replaces an earlier. A prefix is a name, its escapes read,
    compared case and all."""
    out: dict = {}
    if not _NAMESPACE_RULE.search(css):
        return out
    text = _without_comments(css.replace("\x00", "\ufffd"), _COMMENT)
    started = False             # past an @import or an @namespace
    i, n = 0, len(text)
    while True:
        i = _RULE_START.match(text, i).end()
        if i >= n:
            return out
        end, brace, bad = _top_rule(text, i)
        if bad:
            pass                            # a rule a browser drops
        elif text[i] == "@":
            m = _AT_NAME_RE.match(text, i)
            name = _lower(_css_unescape(m.group(1))) if m else ""
            prelude = text[m.end() if m else i + 1:
                           brace if brace >= 0 else end - 1]
            if brace >= 0:
                if name in _BLOCK_AT_RULES and not _block_dropped(
                        name, prelude, text[brace + 1:end - 1],
                        frozenset(k for k in out if k)):
                    return out
            elif name == "namespace":
                got = _NAMESPACE_PRELUDE.match(prelude)
                if got is not None:
                    uri = next((got.group(g) for g in ("s1", "s2", "u1",
                                                       "u2", "u3")
                                if got.group(g) is not None), "")
                    out[_css_unescape(got.group("prefix") or "")] = \
                        _css_unescape(uri)
                    started = True
            elif name == "import":
                lead = prelude.lstrip(_CSS_WS + _COMMENT)
                if (lead[:1] in ("\"", "'") or _URL_OPEN_RE.match(lead)) \
                        and not _import_dropped(lead):
                    started = True
            elif name == "layer" and _layer_names(prelude) and started:
                return out                  # an @layer after @import
        elif brace >= 0 and _qualified_ok(text[i:brace], out):
            return out                      # a style rule
        i = end


def _layer_names(prelude: str) -> bool:
    """Is `prelude` an @layer statement's: layer names, commas between?"""
    names = _selectors_without_comments(prelude)
    return names is not None and all(
        _LAYER_NAME.fullmatch(p.strip(_CSS_WS)) for p in names.split(","))


def _top_rule(text: str, i: int) -> tuple[int, int, bool]:
    """(where the rule that starts at text[i] in a list of rules ends,
    where its block opens (-1 for none), whether a browser drops it: a
    "}", or but in an at-rule a ";", that closes nothing before its block,
    or no block nor ";" at all: R6F-2)."""
    at = text[i] == "@"
    bad = False
    k, n = i, len(text)
    while True:
        m = _CSS_SPECIAL.search(text, k)
        if m is None:
            return n, -1, True
        k = m.start()
        if m.group("url") is not None:
            got = _url_token(text, k, m.end())
            k = got[0] if got is not None \
                else _block_end(text, m.end() - 1)[0]
            continue
        ch = text[k]
        if ch in "\"'":
            k = _skip_string(text, k)
        elif ch == "\\":
            k += 2
        elif ch == "{":
            return _block_end(text, k)[0], k, bad
        elif ch == ";" and at:
            return k + 1, -1, bad
        elif ch in ";}":
            bad = True
            k += 1
        elif ch in "([":
            k = _block_end(text, k)[0]
        else:
            k += 1


def _qualified_ok(prelude: str, namespaces: dict) -> bool:
    """Is `prelude` a style rule's that Chromium 141 reads: a selector list
    it takes (_selectors_valid), every member one soupsieve reads as
    _without_pseudos writes it (_members_read)?"""
    prelude = _selectors_without_comments(prelude)
    prefixes = frozenset(k for k in namespaces if k)
    if prelude is None or not _selectors_valid(prelude, prefixes):
        return False
    return _members_read(prelude, False)


@functools.lru_cache(maxsize=4096)
def _soupsieve_says(selector: str) -> bool | None:
    """Does soupsieve compile `selector` (_c1_escaped)? None where it has
    more parts than soupsieve takes at once (its limit, a ValueError that
    says so); False for any other error (a syntax error, an at-keyword)."""
    import soupsieve
    try:
        soupsieve.compile(_c1_escaped(selector))
    except ValueError as exc:
        return None if "limit" in str(exc) else False
    except Exception:                                  # noqa: BLE001
        return False
    return True


def _soupsieve_reads(selector: str) -> bool:
    """Does soupsieve read `selector`, a list of selectors with no
    pseudo-class (_without_pseudos)? One past its limit is read compound
    by compound, in parts it takes (_PIECES_AT_ONCE characters at once):
    what soupsieve does not read in any, Chromium 141 does not either;
    a compound past its limit alone proves nothing, and is read as one it
    does (R6V-5, R6X-3)."""
    got = _soupsieve_says(selector)
    if got is not None:
        return got
    chunk: list[str] = []
    size = 0
    for part in _compounds(selector):
        if chunk and size + len(part) > _PIECES_AT_ONCE:
            if _soupsieve_says(", ".join(chunk)) is False:
                return False
            chunk, size = [], 0
        chunk.append(part)
        size += len(part) + 2
    return not chunk or _soupsieve_says(", ".join(chunk)) is not False


def _compounds(selector: str) -> list[str]:
    """The compound selectors of `selector`, a list with no pseudo-class:
    split at its commas, combinators and white space, not those in a
    string, an escape or an attribute selector."""
    out, start, i, n = [], 0, 0, len(selector)
    while i < n:
        ch = selector[i]
        if ch == "\\":
            i = _skip_escape(selector, i)
        elif ch in "\"'":
            i = _skip_string(selector, i)
        elif ch == "[":
            i = _block_end(selector, i)[0]
        elif ch in _CSS_WS or ch in ",>+~":
            if i > start:
                out.append(selector[start:i])
            i = start = i + 1
        else:
            i += 1
    if n > start:
        out.append(selector[start:])
    return out


#: What soupsieve does not read as CSS reads it: an escape of zero, of a
#: surrogate or of a code point past U+10FFFF (CSS reads U+FFFD: R6Z-6),
#: and a C1 control character,
#: which CSS reads in a name (R6V-3); an escape is read whole, so an
#: escaped backslash before either is no escape of it (R6X-3, R6X-4).
_SOUPSIEVE_FIX = re.compile(
    r"\\([0-9a-fA-F]{1,6})[ \t\n\r\f]?|\\[\s\S]|([\x80-\x9f])")


def _c1_escaped(selector: str) -> str:
    """`selector` with each C1 control character written as an escape,
    the same character to CSS, and each escape past U+10FFFF as U+FFFD's,
    so that soupsieve reads what Chromium 141 reads (_SOUPSIEVE_FIX)."""
    if "\\" not in selector and not re.search("[\x80-\x9f]", selector):
        return selector
    return _SOUPSIEVE_FIX.sub(_soupsieve_fix, selector)


def _soupsieve_fix(m: re.Match) -> str:
    """One match of _SOUPSIEVE_FIX, as soupsieve should read it."""
    if m.group(2):
        return f"\\{ord(m.group(2)):x} "
    value = int(m.group(1), 16) if m.group(1) else None
    if value is not None and (value == 0 or value > 0x10FFFF
                              or 0xD800 <= value <= 0xDFFF):
        return "\\fffd "      # as CSS reads it (R6Z-6)
    return m.group(0)


#: What _without_pseudos writes for a pseudo-class, a pseudo-element or
#: `&`: a simple selector soupsieve reads.
_NEUTRAL = "[data-bb]"


def _without_pseudos(selector: str) -> list[str]:
    """The selectors soupsieve reads in place of `selector`, a member of
    a list _selector_check passed: the member with each pseudo-class and
    pseudo-element, its argument and all, and each `&`, written as
    _NEUTRAL; then each member of each list that a pseudo-class's or a
    pseudo-element's argument holds and that is not forgiving (:not(),
    :has(), :host(), ::slotted(), an :nth-child()'s `of` list; not :is()
    nor :where()), written so, one of a :has() that starts with a
    combinator after `*`. What soupsieve does not read there (`#2`,
    `.2col`: a name that starts with a digit; a "$", a "<") Chromium 141
    does not read either, and drops the rule (measured: R6T-2). One pass:
    it costs the selector's length."""
    out: list[str] = []
    # Each list open: its kind ("top", "relative", "list") and the parts
    # of the member read so far; or ("skip", the brackets open) for an
    # argument passed over.
    frames: list = [["top", []]]
    i, last, n = 0, 0, len(selector)
    while i < n:
        frame = frames[-1]
        ch = selector[i]
        if ch == "\\":
            i = _skip_escape(selector, i)
            continue
        if ch in "\"'":
            i = _skip_string(selector, i)
            continue
        if frame[0] == "skip":
            if ch in "([":
                frame[1].append(ch)
            elif ch in ")]" and frame[1]:
                if frame[1][-1] == ("(" if ch == ")" else "["):
                    frame[1].pop()
            elif ch == ")":
                frames.pop()                    # the argument's own ")"
                last = i + 1
            i += 1
            continue
        if ch == "[":
            i = _block_end(selector, i)[0]
        elif ch == "&":
            frame[1] += [selector[last:i], _NEUTRAL]
            i = last = i + 1
        elif ch in ",)" and len(frames) > 1:
            frame[1].append(selector[last:i])
            _member_done(frame, out)
            if ch == ")":
                frames.pop()
            i = last = i + 1
        elif ch == ":":
            element = selector.startswith(":", i + 1)
            m = _CSS_IDENT.match(selector, i + 2 if element else i + 1)
            if m is None:
                i += 1
                continue
            frame[1] += [selector[last:i], _NEUTRAL]
            i = last = m.end()
            if selector.startswith("(", i):
                name = _lower(_css_unescape(m.group(0)))
                kind = _LIST_ARGUMENT.get(name, "skip")
                i += 1
                if name in ("nth-child", "nth-last-child"):
                    nth = _NTH_OF.match(selector, i)
                    if nth is not None and nth.group(1):
                        kind, i = "list", nth.end()
                if kind != "relative":
                    kind = ("skip" if kind in ("skip", "forgiving")
                            else "list")
                frames.append([kind, []])
                last = i
        else:
            i += 1
    for frame in reversed(frames):          # an argument left open
        if frame[0] != "skip":
            frame[1].append(selector[last:])
            if frame[0] != "top":
                _member_done(frame, out)
        last = n
    out.insert(0, "".join(frames[0][1]).strip(_CSS_WS))
    return [x for x in out if x]


#: How many characters of selectors _pieces_read gives soupsieve at once:
#: fewer than the 8,192 parts it takes in one (each part a character at
#: least).
_PIECES_AT_ONCE = 8000


def _pieces_read(pieces: list[str]) -> bool:
    """Does soupsieve read each of `pieces` (_without_pseudos), an escaped
    flag read plainly (_plain_flags)? Read as lists of up to
    _PIECES_AT_ONCE characters."""
    chunk: list[str] = []
    size = 0
    for piece in pieces:
        if chunk and size + len(piece) > _PIECES_AT_ONCE:
            if not _soupsieve_reads(_plain_flags(", ".join(chunk))):
                return False
            chunk, size = [], 0
        chunk.append(piece)
        size += len(piece) + 2
    return not chunk or _soupsieve_reads(_plain_flags(", ".join(chunk)))


def _member_done(frame: list, out: list) -> None:
    """Add the member `frame` (_without_pseudos) has read to `out`, and
    start the next."""
    member = "".join(frame[1]).strip(_CSS_WS)
    if frame[0] == "relative" and member[:1] in _COMBINATORS:
        member = "* " + member
    if member:
        out.append(member)
    frame[1] = []


def _follows(element: str, name: str) -> bool:
    """May the pseudo-class or pseudo-element `name` follow the
    pseudo-element `element` in a compound (_AFTER_ELEMENT)? Each is
    "cue()" for ::cue() with an argument. A :not() after any but that
    may, holding only what may follow that one (_Frame.states: R6L-7,
    R6N-6); no :-webkit-any() after ::part(), ::details-content or
    ::picker() (measured: R6N-6)."""
    if element == "cue()":
        return False
    if name in _FORGIVING:
        return element not in ("slotted", "column")
    if name == "not":
        return True
    if element in _ANY_STATE:
        return name not in _TREE_STATES and name not in (
            "part", "slotted", "cue()", "-webkit-any")
    if element.startswith("-webkit-"):
        return name in (_SCROLLBAR_STATES if element.startswith(
            ("-webkit-scrollbar", "-webkit-resizer")) else _USER_ACTION)
    return name in _AFTER_ELEMENT.get(element, ())


def _attribute_ok(content: str, namespaces: frozenset) -> bool:
    """May Chromium 141 read an attribute selector holding `content`: a
    namespace prefix only one the stylesheet declares (`*|` and `|` any:
    `namespaces`), one of CSS's operators (`=`, `~=`, `|=`, `^=`, `$=`,
    `*=`: no `!=`), and no flag but `i`, escaped or not (it has no `s`)
    (measured: R6F-3, R6H-2, R6H-4, R6H-8)? What soupsieve does not read
    either is left to it."""
    return _attribute_read(content, namespaces)[0]


def _plain_flags(selector: str) -> str:
    """`selector` with each attribute selector's escaped flag written
    plainly (`[x=a \\69]` as `[x=a i]`), the only way soupsieve reads
    one."""
    if "[" not in selector or "\\" not in selector:
        return selector
    out, last = [], 0
    for a, b in _bracket_spans(selector):
        content = selector[a + 1:b - 1]
        ok, flag = _attribute_read(content, frozenset(), prefixes=False)
        if ok and flag >= 0 and "\\" in content[flag:]:
            out += [selector[last:a + 1], content[:flag], " i]"]
            last = b
    out.append(selector[last:])
    return "".join(out)


def _attribute_read(content: str, namespaces: frozenset,
                    prefixes: bool = True) -> tuple[bool, int]:
    """(_attribute_ok's answer, where in `content` the flag starts, or -1
    for none); `prefixes`: whether a namespace prefix is checked."""
    k = _CSS_SPACE.match(content).end()
    m = _ATTRIBUTE_PREFIX.match(content, k)
    if m is not None:
        if prefixes and _css_unescape(content[k:m.end() - 1]) \
                not in namespaces:
            return False, -1
        k = m.end()
    elif content.startswith(("*|", "|"), k) \
            and not content.startswith("|=", k):
        k = content.index("|", k) + 1
    name = _CSS_IDENT.match(content, k)
    if name is None:
        return True, -1             # what soupsieve does not read either
    k = _CSS_SPACE.match(content, name.end()).end()
    if k == len(content):
        return True, -1
    op = content[k:k + 2] if content[k] in "~|^$*" else content[k]
    if op not in ("=", "~=", "|=", "^=", "$=", "*="):
        return False, -1            # `[x!=y]`, `[x i]`
    k = _CSS_SPACE.match(content, k + len(op)).end()
    if k < len(content) and content[k] in "\"'":
        k = _skip_string(content, k)
    else:
        value = _CSS_IDENT.match(content, k)
        if value is None:
            return True, -1         # what soupsieve does not read either
        k = value.end()
    flag = content[k:].strip(_CSS_WS)
    if flag == "":
        return True, -1
    return _lower(_css_unescape(flag)) == "i", k


def _prefix_ok(selector: str, i: int, namespaces: frozenset,
               start: int = 0) -> bool:
    """Is the namespace prefix before the "|" at selector[i] one Chromium
    141 reads: none (`|a`), `*`, or a name the stylesheet declares
    (`namespaces`), its escapes read (`\\73 vg|a`: R6J-7), case and all,
    where a compound starts (`start`, where the compound the "|" is in
    starts: R6H-8)? `.a|b` names none."""
    prefix = selector[start:i]
    if prefix in ("", "*"):
        return True
    return bool(_WHOLE_NAME.fullmatch(prefix)) \
        and _css_unescape(prefix) in namespaces


#: A name, whole.
_WHOLE_NAME = re.compile(_NAME)


#: The arguments of the pseudo-classes and pseudo-elements Chromium 141
#: takes as functions, measured (R6H-2), each up to its ")": one name
#: (`:lang(en)`, not `:lang(en, fr)` nor `:lang("en")`; `:dir(rtl)`,
#: `:state(x)`, `::highlight(x)`, `::picker(select)`); names (::part());
#: a direction (::scroll-button()); a view transition's name and classes
#: (white space between them, but none after a `*`: R6L-4);
#: names with a comma between (:active-view-transition-type()); An+B, and
#: for :nth-child() and :nth-last-child() An+B `of` a selector list. The
#: others hold selector lists (_LIST_ARGUMENT).
_ARG_SPACE = "[ \t\n\r\f]*"
_ONE_NAME = re.compile(_ARG_SPACE + "(" + _NAME + ")" + _ARG_SPACE + r"\)")
_NAMES = re.compile(_ARG_SPACE + _NAME + "(?:[ \t\n\r\f]+" + _NAME + ")*"
                    + _ARG_SPACE + r"\)")
_NAME_LIST = re.compile(_ARG_SPACE + _NAME + _ARG_SPACE + "(?:,"
                        + _ARG_SPACE + _NAME + _ARG_SPACE + r")*\)")
_SCROLL_BUTTON = re.compile(_ARG_SPACE + r"(\*|" + _NAME + ")" + _ARG_SPACE
                            + r"\)")
_TRANSITION_NAME = re.compile(
    _ARG_SPACE + r"(?:\*(?:\." + _NAME + "(?:" + _ARG_SPACE + r"\." + _NAME
    + ")*)?|(?:" + _NAME + r"|\." + _NAME + ")(?:" + _ARG_SPACE + r"\."
    + _NAME + ")*)" + _ARG_SPACE + r"\)")
_ANB = (r"(?:odd|even|[+-]?[0-9]*n(?:" + _ARG_SPACE + "[+-]" + _ARG_SPACE
        + r"[0-9]+)?|[+-]?[0-9]+)")
_NTH = re.compile(_ARG_SPACE + _ANB + _ARG_SPACE + r"\)", re.I)
#: An+B, then ")", or `of`, in lower case (R6N-11), after white space (a
#: selector list follows).
_NTH_OF = re.compile(
    _ARG_SPACE + _ANB + _ARG_SPACE
    + r"(?:\)|(?<=[ \t\n\r\f])((?-i:of))(?![-\w\u0080-\U0010ffff\\]))",
    re.I)
_SCROLL_BUTTONS = frozenset(("*", "up", "down", "left", "right",
                             "block-start", "block-end", "inline-start",
                             "inline-end"))
_ARGUMENTS = {
    **dict.fromkeys(("lang", "dir", "state", "highlight", "picker"),
                    _ONE_NAME),
    "part": _NAMES, "scroll-button": _SCROLL_BUTTON,
    "active-view-transition-type": _NAME_LIST,
    "nth-of-type": _NTH, "nth-last-of-type": _NTH,
    **dict.fromkeys(("view-transition-group", "view-transition-image-pair",
                     "view-transition-new", "view-transition-old",
                     "view-transition-group-children"), _TRANSITION_NAME),
}
#: How a function's selector list is read (_Frame.kind): a list (:not()),
#: a relative one (:has()), a forgiving one (:is(), :where()), one
#: compound selector (:host(), :host-context(), ::slotted()), compound
#: selectors (:-webkit-any(), ::cue()); "of" is :nth-child()'s list.
_LIST_ARGUMENT = {"not": "list", "has": "relative", "is": "forgiving",
                  "where": "forgiving", "host": "compound",
                  "host-context": "compound", "slotted": "compound",
                  "-webkit-any": "compounds", "cue": "compounds"}
_COMBINATORS = frozenset(">+~")
#: The functions in whose argument Chromium 141 takes no :has(), however
#: deep, a forgiving list's member left out (measured: R6J-4, R6L-7).
_NO_HAS = frozenset(("has", "host", "host-context", "slotted"))


def _argument_end(name: str, selector: str, i: int) -> int | None:
    """Where the argument of the function `name` that starts at
    selector[i] ends (its ")"), where it is one that holds no selector
    list (_ARGUMENTS); -1 where Chromium 141 does not take it (measured:
    R6H-2); None for one that holds a selector list."""
    pattern = _ARGUMENTS.get(name)
    if pattern is None:
        return None
    m = pattern.match(selector, i)
    if m is None or (name == "scroll-button" and _lower(_css_unescape(
            m.group(1))) not in _SCROLL_BUTTONS):
        return -1
    if pattern is _TRANSITION_NAME and any(
            _lower(_css_unescape(w.group(0))) in _NOT_IDENTS
            for w in _CSS_IDENT.finditer(selector, i, m.end() - 1)):
        return -1       # a name or class no custom-ident is: R6N-7
    return m.end() - 1


class _Frame:
    """A function of a selector, open while its argument is read, or the
    selector itself ("top"): what kind of list it holds (_LIST_ARGUMENT,
    "of", "top", or "" for none), its name, whether it is in a forgiving
    list, whether a :has(), a :host(), a :host-context() or a ::slotted()
    is open at it or around it, where no :has() may stand (`has`, through
    forgiving lists too: _forgiven), and of the member being read whether
    it started, its first and last character (a combinator, or "x" for
    any other), whether white space stands after what it read, whether it
    is more than a compound selector, whether two combinators stand
    together (`bad`), and the pseudo-element it ends with (`after`, with
    white space after it: `gap`). `states`: the pseudo-element a :not()
    right after it follows (`::part(x):not(:hover)`), whose members may
    hold only what may follow that one (R6L-7)."""
    __slots__ = ("kind", "name", "forgiving", "has", "started", "first",
                 "last", "space", "complex", "bad", "after", "gap", "states")

    def __init__(self, kind: str, name: str, forgiving: bool,
                 has: bool = False, states: str | None = None):
        self.kind, self.name, self.forgiving = kind, name, forgiving
        self.has, self.states = has, states
        self.reset()

    def reset(self) -> None:
        self.started = self.space = self.complex = self.bad = False
        self.first = self.last = ""
        self.after = None
        self.gap = False

    def read(self, ch: str) -> None:
        """A character of the member, directly in this function."""
        if ch in _CSS_WS:
            self.space = self.started
            self.gap = self.after is not None
            return
        if ch in _COMBINATORS:
            self.bad = self.bad or self.last in _COMBINATORS
            self.complex = True
        elif self.space:
            self.complex = True     # white space between two: a combinator
        self.space = False
        if not self.started:
            self.started, self.first = True, ch
        self.last = ch if ch in _COMBINATORS else "x"

    def member_ok(self) -> bool:
        """Does Chromium 141 take the member read so far (measured: R6H-2,
        R6J-5): none with two combinators together (`.a > > .b`); in
        :not() and the `of` list none empty, nor starting or ending with a
        combinator; in :has() none empty nor ending with one; where a
        compound selector is taken, no more than one?"""
        if self.bad:
            return False
        if self.kind in ("forgiving", "", "top"):
            return self.kind != "top" or self.last not in _COMBINATORS
        if not self.started:
            return False
        if self.kind in ("list", "of"):
            return self.first not in _COMBINATORS \
                and self.last not in _COMBINATORS
        if self.kind == "relative":
            return self.last not in _COMBINATORS
        return not self.complex     # "compound", "compounds"


def _selector_check(selector: str, namespaces: frozenset = frozenset(),
                    inner: bool = False, jumps: dict | None = None,
                    offset: int = 0, has: bool = False) -> tuple[bool, bool]:
    """(may Chromium 141 read `selector`, a member of a selector list (of
    a function's, `inner`, which holds no pseudo-element): not where it
    names, outside a forgiving list (:is(), :where()), a pseudo-class or a
    pseudo-element Chromium does not have, or one in a form it does not
    take (`:hover()`, `: hover`, `:not()`, an argument it does not take:
    `:lang(en, fr)`, `:nth-child(foo)`, `::part(x, y)`, `:host(.a .b)`,
    `:host(:not(.a .b))`, `:not(> .a)`, `:not(.a >)`, `:has(.a >)`,
    `:has(:has(.a))`, `:host(:has(.a))`: _argument_end, _Frame; a
    pseudo-element in `inner`, or inside a function but the `of` list of
    a :nth-child() in no function, or before what may not follow it:
    _AFTER_ELEMENT, R6L-8), two combinators together or one it ends
    with, a column combinator (`||`), an attribute selector it does not
    read (_attribute_ok), a ")" that closes nothing or a "]" outside an
    attribute selector (R6R-2), or a namespace prefix the stylesheet does
    not declare (`namespaces`: _prefix_ok); does it name a pseudo-class, a
    pseudo-element or `&`, which soupsieve may not read as Chromium does?)
    (measured: R6F-3, R6H-2, R6H-4, R6H-8, R6J-5). `jumps`: where each
    forgiving list's "(" in the selector `selector` is part of, `offset`
    characters before it, finds its ")": what such a list holds is passed
    over (_forgiven). `has`: a :has() (or another of _NO_HAS) holds the
    list `selector` is a member of, so it may hold none (R6J-4)."""
    top = _Frame("top", "", False, has)
    frames: list[_Frame] = []
    pseudo = False
    start = 0                       # where the compound being read starts
    i, n = 0, len(selector)
    while i < n:
        ch = selector[i]
        frame = frames[-1] if frames else top
        forgiving = frame.forgiving
        if not forgiving and frame.after is not None and (
                ch not in ":)," + _CSS_WS or (ch == ":" and frame.gap)):
            return False, True      # after a pseudo-element: a combinator
        if not forgiving and frame.states is not None \
                and ch not in ":),>+~" + _CSS_WS:
            return False, True      # `::part(x):not(.a)`: R6L-7, R6P-4
        if not forgiving and ch not in "),":
            frame.read(ch)
        if ch == "\\":
            i = _skip_escape(selector, i)
        elif ch in "\"'":
            i = _skip_string(selector, i)
        elif ch == "[":
            got = _block_end(selector, i)
            if not forgiving and not _attribute_ok(selector[i + 1:got[1]],
                                                   namespaces):
                return False, pseudo
            i = got[0]
        elif ch == "(":
            if not forgiving:
                return False, pseudo    # opens no function (R6P-3)
            frames.append(_Frame("", "", forgiving))
            i += 1
            start = i
        elif ch == ",":
            if frame is not top and not forgiving:
                if frame.kind == "compound" or not frame.member_ok():
                    return False, pseudo
                frame.reset()
            i += 1
            start = i
        elif ch == ")":
            if frame is top:
                return False, pseudo    # closes nothing (R6R-2)
            if not forgiving and not frame.member_ok():
                return False, pseudo
            frames.pop()
            i += 1
        elif ch == "]" and not forgiving:
            return False, pseudo        # outside an attribute (R6R-2)
        elif ch == "|" and not forgiving:
            if selector.startswith("|", i + 1) or not _prefix_ok(
                    selector, i, namespaces, start):
                return False, pseudo
            i += 1
        elif ch == ":":
            element = selector.startswith(":", i + 1)
            m = _CSS_IDENT.match(selector, i + 2 if element else i + 1)
            if m is None:
                return False, True
            pseudo = True
            name = _lower(_css_unescape(m.group(0)))
            function = selector.startswith("(", m.end())
            end = None              # where an argument with no list ends
            kind = _LIST_ARGUMENT.get(name, "")
            if not forgiving:
                if element:
                    known = (name in _PSEUDO_ELEMENT_FUNCTIONS if function
                             else name in _PSEUDO_ELEMENTS
                             or name.startswith("-webkit-"))
                else:
                    known = (name in _PSEUDO_CLASS_FUNCTIONS if function
                             else name in _PSEUDO_CLASSES)
                if not known or (function and name not in _FORGIVING
                                 and _NO_ARGUMENTS.match(selector, m.end())):
                    return False, True
                if function and name in ("nth-child", "nth-last-child"):
                    nth = _NTH_OF.match(selector, m.end() + 1)
                    if nth is None:
                        return False, True
                    kind = "of" if nth.group(1) else ""
                    end = nth.end() if kind else nth.end() - 1
                elif function:
                    end = _argument_end(name, selector, m.end() + 1)
                    if end == -1:
                        return False, True
                if function and name == "has" and frame.has:
                    return False, True      # no :has() in _NO_HAS
                if name == "not" and frame.kind in ("compound",
                                                    "compounds"):
                    kind = "compounds"      # :host(:not(.a .b)): R6J-5
                if frame.after is not None and not _follows(
                        frame.after, "cue()" if name == "cue" and function
                        else name):
                    return False, True
                if frame.states is not None and (element or not _follows(
                        frame.states, name)):
                    return False, True
                if element or (name in _LEGACY_ELEMENTS and not function):
                    # At the top, or in an `of` list, in `of` lists alone
                    # (R6L-8, R6N-5).
                    if inner or frame.kind not in ("top", "of") or any(
                            f.kind != "of" for f in frames):
                        return False, True
                    frame.after = "cue()" if name == "cue" and function \
                        else name
            i = m.end()
            if function:
                states = None
                if not forgiving and name == "not" and (
                        frame.after is not None or frame.states):
                    states = frame.states or frame.after
                    kind = "list"       # combinators too (R6P-4)
                frames.append(_Frame(kind, name,
                                     forgiving or name in _FORGIVING,
                                     not forgiving and (name in _NO_HAS
                                                        or frame.has),
                                     states))
                if jumps is not None and i + offset in jumps:
                    i = jumps[i + offset] - offset      # at its ")"
                else:
                    i = end if end is not None else i + 1
                start = i
        else:
            pseudo = pseudo or ch == "&"
            i += 1
            if ch in _CSS_WS or ch in _COMBINATORS:
                start = i
    if not top.member_ok():
        return False, pseudo
    return True, pseudo


def _selectors_valid(selectors: str,
                     namespaces: frozenset = frozenset(),
                     inner: bool = False) -> bool:
    """May Chromium 141 read the selector list `selectors`: none of its
    members empty (`.a,`, `.a,,.b`), and none _selector_check finds it
    does not read (R6F-3; `inner`: a list that holds no pseudo-element,
    as a function's)?"""
    parts = split_selectors(selectors, keep_empty=True)
    return all(parts) and all(_selector_check(p, namespaces, inner)[0]
                              for p in parts)


#: What _forgiven's one pass over a selector stops at.
_FORGIVING_SCAN = re.compile(r"[\\\"'\[(),:]")


@functools.lru_cache(maxsize=4096)
def _forgiven(selector: str, namespaces: frozenset = frozenset()) -> str:
    """`selector` without what Chromium 141 leaves out of a forgiving list
    (:is(), :where()) in it: a member it does not read (_selector_check)
    or an empty one; one with none left (`:is()`) matches nothing (R6F-3).
    One pass finds the lists, and each member is checked once, past the
    lists it holds, so a selector costs its length, however deep its lists
    nest (R6H-10); lists deeper than 16 are left as they are. A member of
    a list a :has(), a :host(), a :host-context() or a ::slotted() holds,
    however deep, may hold no :has() (_NO_HAS, measured: R6J-4, R6L-7)."""
    if not re.search(r":(?:is|where)\(", selector, re.I):
        return selector
    n = len(selector)
    closes: dict = {}       # "(" -> its ")" (n where none closes it)
    commas: dict = {}       # a forgiving list's "(" -> its own commas
    kids: dict = {}         # a list's "(" (-1: none) -> the lists in it
    held: dict = {}         # a forgiving list's "(" -> does _NO_HAS hold it
    opens: set = set()      # where a _NO_HAS function's "(" stands
    stack: list = []        # each "(" open: (where, its forgiving list,
    k = 0                   # does _NO_HAS hold it, or is it one's)
    while True:
        m = _FORGIVING_SCAN.search(selector, k)
        if m is None:
            break
        k = m.start()
        ch = selector[k]
        if ch == "\\":
            k = _skip_escape(selector, k)
            continue
        if ch in "\"'":
            k = _skip_string(selector, k)
            continue
        if ch == "[":
            k = _block_end(selector, k)[0]
            continue
        if ch == ":":
            name = _CSS_IDENT.match(selector, k + 1)
            if name is not None and selector.startswith("(", name.end()):
                fn = _lower(_css_unescape(name.group(0)))
                if fn in _FORGIVING:
                    p = name.end()
                    kids.setdefault(stack[-1][1] if stack else -1,
                                    []).append(p)
                    commas[p], closes[p] = [], n
                    held[p] = bool(stack) and stack[-1][2]
                    stack.append((p, p, held[p]))
                    k = p + 1
                    continue
                if fn in _NO_HAS:
                    opens.add(name.end())
        elif ch == "(":
            stack.append((k, stack[-1][1] if stack else -1,
                          k in opens or (bool(stack) and stack[-1][2])))
            closes[k] = n
        elif ch == ")":
            if stack:
                closes[stack.pop()[0]] = k
        elif ch == "," and stack and stack[-1][0] == stack[-1][1]:
            commas[stack[-1][0]].append(k)
        k += 1
    jumps = {p: closes[p] for p in commas}

    def render(start: int, end: int, lists: list, depth: int) -> str:
        out, pos = [], start
        for p in lists:
            close = min(closes[p], end)
            out.append(selector[pos:p + 1])
            if depth > 16:
                out.append(selector[p + 1:close])
            else:
                kept = []
                inner = kids.get(p, [])
                for ms, me in zip([p + 1] + [c + 1 for c in commas[p]],
                                  commas[p] + [close]):
                    text = selector[ms:me]
                    if not text.strip(_CSS_WS) or not _selector_check(
                            text, namespaces, True, jumps, ms, held[p])[0]:
                        continue
                    sub = inner[bisect.bisect_left(inner, ms):
                                bisect.bisect_left(inner, me)]
                    kept.append(render(ms, me, sub, depth + 1)
                                .strip(_CSS_WS))
                out.append(", ".join(kept))
            pos = close
        out.append(selector[pos:end])
        return "".join(out)

    return render(0, n, kids.get(-1, []), 0)


#: A selector that holds only while scripts have not run (`.no-js .menu`,
#: `html:not(.js) .menu`): a browser that runs the page's scripts drops it,
#: so it says nothing about the page a visitor sees.
_SCRIPTLESS_RE = re.compile(r"no-js|:not\(\s*\.js\b", re.I)
#: A whole selector that styles a shadow root's host, or what its slots show.
_HOST_RE = re.compile(r"\s*:host(?:\((.+)\))?\s*", re.I | re.S)
_SLOTTED_RE = re.compile(r"\s*::slotted\((.+)\)\s*", re.I | re.S)
_STYLE_TYPES = ("", "text/css")


#: An identifier: letters, digits, "-", "_", non-ASCII, and escapes; a hex
#: escape takes up to six digits and one whitespace after them (`\31 x`
#: is "1x").
_IDENT_RE = re.compile(r"(?:\\[0-9a-fA-F]{1,6}(?:\r\n|[ \t\n\r\f])?"
                       r"|\\[^\n\r\f0-9a-fA-F]|[-\w]|[^\x00-\x7f])+")
_ESCAPE_RE = re.compile(r"\\(?:[0-9a-fA-F]{1,6}(?:\r\n|[ \t\n\r\f])?|[\s\S])")


def _skip_escape(text: str, i: int) -> int:
    """The index after the CSS escape at `text[i]` (a backslash)."""
    m = _ESCAPE_RE.match(text, i)
    return m.end() if m else i + 1


def _scope_as_root(selector: str, root: str = ":root") -> str:
    """`:scope` outside quotes, and `&` outside a rule that nests it
    (_amps), as `root`: in a document's stylesheet, outside @scope, each
    is the root element (`:root`), while soupsieve's match() would take
    either to be the element matched (OR-14, R6V-7); in a shadow root's,
    nothing (`:not(*)`: measured, R6X-1). A nested rule's `&` and one in
    @scope are their parent's or root's selector by now (_nested,
    _style_walk)."""
    return _amp_as(_scope_as(selector, root), root)


def _scope_as(selector: str, root: str) -> str:
    """`:scope` outside quotes, as `root`."""
    if ":scope" not in selector.lower():
        return selector
    out, i, quote, n = [], 0, None, len(selector)
    while i < n:
        ch = selector[i]
        if ch == "\\":
            j = _skip_escape(selector, i)
            out.append(selector[i:j])
            i = j
            continue
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif (ch == ":" and selector[i + 1:i + 6].lower() == "scope"
              and not re.match(r"[-\w]", selector[i + 6:i + 7])):
            out.append(root)
            i += 6
            continue
        out.append(ch)
        i += 1
    return "".join(out)


#: A type selector's namespace prefix: a name, `*`, or none, then "|".
_TYPE_PREFIX = re.compile(r"(?:" + _NAME + r"|\*)?\|(?![|=])")


def _rightmost_key(selector: str):
    """The id, class or tag the rightmost compound of `selector` requires,
    lowercased, as (kind, value); None when it requires none of them (`*`,
    `[aria-hidden]`, `:is(.a, .b)`). An element that lacks the key cannot
    match, so a rule is tried only on elements that have it, as a browser's
    rule hash does."""
    depth, quote, last, i = 0, None, 0, 0
    n = len(selector)
    while i < n:
        ch = selector[i]
        if ch == "\\":
            i = _skip_escape(selector, i)
            continue
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        elif depth == 0 and ch in " \t\n\r\f>+~":
            last = i + 1
        i += 1
    compound = selector[last:].strip()
    found = {"id": None, "class": None, "tag": None}
    depth = 0
    # A namespace prefix (`svg|a`, `*|a`, `|a`) is no tag: the name after
    # it is (R6J-2).
    m = _TYPE_PREFIX.match(compound)
    i = m.end() if m else 0
    if compound[i:i + 1] and compound[i] not in "#.[:*":
        m = _IDENT_RE.match(compound, i)
        if m:
            found["tag"] = _css_unescape(m.group(0)).lower()
            i = m.end()
    quote = None
    while i < len(compound):
        ch = compound[i]
        if ch == "\\":
            i = _skip_escape(compound, i)
            continue
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        elif depth == 0 and ch in "#.":
            m = _IDENT_RE.match(compound, i + 1)
            if m:
                kind = "id" if ch == "#" else "class"
                if found[kind] is None:
                    found[kind] = _css_unescape(m.group(0)).lower()
                i = m.end()
                continue
        i += 1
    for kind in ("id", "class", "tag"):
        if found[kind]:
            return kind, found[kind]
    return None


#: Where a declaration stands in the cascade (CSS Cascade 5), as far as
#: markup shows it: normal stylesheet declarations in a layer, then
#: unlayered, then the style attribute's; !important ones above every
#: normal one, unlayered below layered, the style attribute's highest.
_TIER_LAYERED, _TIER_PLAIN, _TIER_INLINE = 1, 2, 3
_TIER_IMPORTANT, _TIER_LAYERED_IMPORTANT, _TIER_INLINE_IMPORTANT = 4, 5, 6


#: What a CSS-wide keyword sets, as _marks reads it (R5M-7): display's
#: initial, unset and inherit show an element (its initial value is
#: inline), and revert shows it as the browser displays it (shown, but for
#: a closed <dialog> or popover: _decide); visibility's initial shows it,
#: its unset and inherit take the parent's (INHERIT), and so does its
#: revert but on a MathML <mphantom>, which it hides (REVERT: _decide).
#: revert-layer falls back to what the cascade sets below it: no mark. A
#: display only known later (var(): LATER) shows it, though a file run
#: reviews focusable content it decides (display_later: R6H-3); a
#: visibility so (LATER) shows it where the caller asks whether to
#: exclude an element
#: (`later_shows`: checks_static._display_none, R5Q-4); may show it where
#: it decides whether content inside invisible content is shown again
#: (checks_static._reshows, which a review then settles: R6B-8, R6D-1);
#: and is read as the parent's elsewhere: where it decides whether text
#: names anything (R5S-9), and whether a control is not shown
#: (checks_static._not_shown, where what could be either is hidden).
INHERIT, REVERT, LATER = "inherit", "revert", "later"
#: A display or visibility a var() gives where the custom property is set
#: nowhere the run could read (_shown_fallback): its fallback, which
#: shows. It shows as a value would (_decide), for names too; where a hide
#: that holds without condition stands level with it (the fallback itself
#: under a condition or not), which the run cannot order (no
#: specificity), a hide being display:none, visibility:hidden or collapse,
#: or a revert that hides (a var()'s fallback revert too: R6R-1), the
#: focusable content it decides is reviewed (display_later,
#: visibility_later: R6K-4, R6L-2, R6M-2, R6N-1, R6N-8).
FALLBACK = "fallback"
#: Such a fallback that leaves visibility to the parent (unset, inherit:
#: FALLBACK_INHERIT, read as INHERIT) or reverts it (FALLBACK_REVERT, read
#: as REVERT), reviewed as FALLBACK is where a hide stands level with it
#: (R6P-2).
FALLBACK_INHERIT, FALLBACK_REVERT = "fallback-inherit", "fallback-revert"
#: What each fallback is read as (_decide).
_FALLBACKS = {FALLBACK: True, FALLBACK_INHERIT: INHERIT,
              FALLBACK_REVERT: REVERT}


def _marks(decls: dict, layered: bool, conditional: bool,
           inline: bool = False, custom: frozenset | None = None
           ) -> frozenset:
    """(property, shows it, tier, conditional) for what `decls` (from
    _declarations) set of display and visibility: shows True, False, a
    CSS-wide keyword's INHERIT or REVERT, or a value only known later
    (LATER, a display's read as shown: _decide). A rule that may not hold
    says only what it may show: one it would hide is not read as hidden
    (R5G-6), and its revert or inherit is kept, which may show (R5O-4:
    _decide). `custom`: the custom properties the page's own styles set
    anywhere, where no other stylesheet could set one (PageStyles); a
    var() of one they set nowhere is read as its fallback, or as unset
    where it has none (`display:var(--fa-display, inline-block)`: R6J-3),
    a show so FALLBACK (a visibility left to the parent so
    FALLBACK_INHERIT, a revert FALLBACK_REVERT). Visibility's revert is REVERT,
    which a MathML <mphantom> reverts to hidden (_decide: R6K-8)."""
    out = set()
    for prop in ("display", "visibility"):
        got = decls.get(prop)
        if got is None:
            continue
        value, important = got
        fallback = False
        if "(" in value and custom is not None:
            got = _shown_fallback(prop, value, custom)
            fallback = got is not None
            value = got or value
        if prop == "display":
            shows = (False if value == "none" else
                     REVERT if value == "revert" else
                     None if value == "revert-layer" else
                     LATER if "(" in value else True)
        else:
            # A value only known later (var()): LATER (_decide).
            shows = (False if value in ("hidden", "collapse") else
                     True if value in ("visible", "initial") else
                     LATER if "(" in value else
                     REVERT if value == "revert" else
                     INHERIT if value in ("unset", "inherit")
                     else None)
        if fallback and shows is True:
            shows = FALLBACK
        elif fallback and shows in (INHERIT, REVERT):
            shows = FALLBACK_INHERIT if shows == INHERIT else FALLBACK_REVERT
        if shows is None or (conditional and shows is False):
            continue
        tier = ((_TIER_INLINE_IMPORTANT if important else _TIER_INLINE)
                if inline else
                (_TIER_LAYERED_IMPORTANT if layered else _TIER_IMPORTANT)
                if important else
                (_TIER_LAYERED if layered else _TIER_PLAIN))
        out.add((prop, shows, tier, conditional))
    return frozenset(out)


def _inline_marks(el, custom: frozenset | None = None) -> frozenset:
    """What `el`'s style attribute sets of display and visibility (_marks;
    `custom` as there)."""
    return _marks(_declarations(el.get("style")), False, False, inline=True,
                  custom=custom)


#: A value that is one var(): the custom property's name, its fallback.
_VAR_VALUE = re.compile(r"var\([ \t\n\r\f]*(--[^ \t\n\r\f,()]*)[ \t\n\r\f]*"
                        r"(?:,(.*))?\)", re.S)
#: A name, and the colon after it where a property is set: escapes in the
#: name (its hyphens too: `\2d -d`), a comment (_COMMENT) before its
#: colon; a custom property's name, unescaped, starts "--"
#: (`custom_properties`: R6N-9). Each name is read once, whether a colon
#: follows or not, so a long run of them costs its length (R6P-1).
_CUSTOM_SET = re.compile(r"(?<![-\w\\])(" + _NAME
                         + r")(?:[ \t\n\r\f\x00]*(:))?")
#: An at-rule and the name after it: `@property --name` registers a custom
#: property, whose initial value it may set (`custom_properties`).
_AT_THEN_NAME = re.compile("@(" + _NAME + ")[ \t\n\r\f\x00]*(" + _NAME
                           + ")")


def _shown_fallback(prop: str, value: str, custom: frozenset) -> str | None:
    """`value`, one var() of a custom property `custom` does not hold (none
    of the page's own styles sets it), as CSS reads it: its fallback, or
    `unset` where it has none (a var() of such another in the fallback
    read so too); None where a property the page sets decides, or where
    what it reads hides (a hide only known later stays so: R6J-3)."""
    for _ in range(8):
        m = _VAR_VALUE.fullmatch(value)
        if m is None:
            return None if "(" in value else value
        if m.group(1) in custom:
            return None
        value = (m.group(2) or "").strip(_CSS_WS) or "unset"
        if prop == "display" and value == "none" or (
                prop == "visibility" and value in ("hidden", "collapse")):
            return None
    return None


def _reads_other_sheets(soup, texts) -> bool:
    """Does the page read a stylesheet a file run does not: a <link> whose
    rel is stylesheet (or a preload of one: `as="style"`), an
    <?xml-stylesheet?> processing instruction in an XML document (the
    XHTML reader keeps one; an HTML parser makes it a comment, as
    browsers do: R6M-5), or an @import (an at-rule with an escape in its
    name read as one) in its own styles (`texts`)?"""
    for link in soup.find_all("link"):
        rel = link.get("rel") or ""
        rel = _lower(rel if isinstance(rel, str) else " ".join(rel)).split()
        if "stylesheet" in rel or ("preload" in rel and _lower(
                (link.get("as") or "").strip()) == "style"):
            return True
    from bs4.element import ProcessingInstruction
    if any(_XML_STYLESHEET.match(pi) for pi in soup.find_all(
            string=lambda s: isinstance(s, ProcessingInstruction))):
        return True
    return any(_IMPORT_LIKE.search(t or "") for t in texts)


#: An <?xml-stylesheet?> processing instruction's text (its target first).
_XML_STYLESHEET = re.compile(r"xml-stylesheet(?![^ \t\n\r])")


#: An @import, or an at-keyword with an escape that may spell one.
_IMPORT_LIKE = re.compile(r"@(?:import|\\)", re.I)


def custom_properties(texts) -> frozenset:
    """The names of the custom properties `texts` (stylesheets, style
    attributes) set or register (`@property`), escapes read, comments
    passed over, lowercased as the declarations' values are (R6L-1): a
    name set in another case counts as set, so its var() is reviewed
    rather than read as its fallback (R6K-12)."""
    out = set()
    for t in texts:
        t = _without_comments(t or "", _COMMENT)
        for m in _CUSTOM_SET.finditer(t):
            name = m.group(1)
            if m.group(2) is None:
                continue
            if name.startswith("--") or "\\" in name:
                name = _lower(_css_unescape(name))
                if name.startswith("--"):
                    out.add(name)
        if "@" in t:
            for m in _AT_THEN_NAME.finditer(t):
                name = _lower(_css_unescape(m.group(2)))
                if name.startswith("--") and _lower(_css_unescape(
                        m.group(1))) == "property":
                    out.add(name)
    return frozenset(out)


def _decide(marks, prop: str, conditional: bool = True,
            ua_sheet: bool = False, later_shows: bool = False,
            ua_invisible: bool = False) -> bool | None:
    """PageStyles.decides over `marks`. `ua_sheet`: the browser's own
    stylesheet hides the element (a closed <dialog>, a popover), which
    display:revert falls back to; the hidden attribute is no part of that
    stylesheet in Chromium 141, and revert shows an element it hides.
    `ua_invisible`: that stylesheet makes it invisible (a MathML
    <mphantom>: ua_invisible), so where nothing the page sets decides its
    visibility, or a revert does, it is hidden (R6I-5, R6K-8). A FALLBACK
    shows as a value does, a hide level with it too (where that decides,
    display_later and visibility_later review it: R6M-2); one that leaves
    visibility to the parent or reverts it is read as INHERIT or REVERT
    (_FALLBACKS).

    What holds without condition decides first. A mark under a condition
    counts only with `conditional`, and only where it may show and could
    win (as high in the cascade as what holds without one, or higher): a
    show, or a revert that shows, shows the element; visibility's inherit,
    unset or revert leaves it to the parent (None, so the caller reads on
    up: R5O-4). One that would hide, or leave a shown element to a hidden
    parent, is not read (R5G-6, R5Q-2)."""
    hide = show = inherit = 0
    could_show = could_inherit = 0
    for p, shows, t, c in marks:
        if p != prop:
            continue
        shows = _FALLBACKS.get(shows, shows)
        if shows == REVERT:
            shows = (not ua_sheet if prop == "display" else
                     False if ua_invisible else INHERIT)
        elif shows == LATER:
            shows = True if later_shows or prop == "display" else INHERIT
        if c:
            if shows is True:
                could_show = max(could_show, t)
            elif shows == INHERIT:
                could_inherit = max(could_inherit, t)
            continue
        if shows is True:
            show = max(show, t)
        elif shows is False:
            hide = max(hide, t)
        elif shows == INHERIT:
            inherit = max(inherit, t)
    top = max(hide, show, inherit)
    base = (None if not top else True if show == top else
            None if inherit == top else False)
    if not top and ua_invisible:
        base = False        # the browser's own stylesheet's (R6I-5)
    if not conditional or base is True:
        return base
    if could_show and could_show >= top:
        return True
    if could_inherit and could_inherit >= top:
        return None
    return base


def display_later(styles, el) -> bool:
    """Does a display only known later (var()) decide whether `el` is
    displayed: what sets display highest in the cascade on it (its style
    attribute, or with the page's styles a rule of its own <style>), a
    show beside it as high too (the run reads no specificity: R6K-4,
    R6L-2), or one under a condition that may hold as high (R6H-3,
    R6J-3)? A var()'s fallback (FALLBACK) is, where a hide stands level
    with it, the fallback under a condition or not (R6N-1): display:none,
    or a revert to the browser's own stylesheet that hides it (a closed
    <dialog>, a popover: R6N-8)."""
    if styles is not None:
        return styles.display_later(el)
    return _later(_inline_marks(el), "display", _ua_sheet_hidden(el))


def visibility_later(styles, el) -> bool:
    """display_later for visibility: does a visibility only known later
    (LATER: a var() whose fallback hides, or one of a custom property the
    page sets) stand as high as what else sets it, a show level with it
    or not (R6T-1), or a var()'s fallback (FALLBACK, one that leaves
    visibility to the parent or reverts it too) stand level with a hide
    that holds without condition (visibility:hidden or collapse, or a
    revert where the browser's own stylesheet makes it invisible: a
    MathML <mphantom>), as high as what else sets it (R6M-2, R6N-1,
    R6N-8, R6P-2)?"""
    marks = (styles.marks(el) if styles is not None
             else _inline_marks(el))
    return _later(marks, "visibility", ua_invisible=ua_invisible(el))


def _later(marks, prop: str, ua_sheet: bool = False,
           ua_invisible: bool = False) -> bool:
    """Does a value only known later (LATER), or a var()'s fallback
    (_FALLBACKS) where a hide that holds without condition stands level
    with it, decide `prop` among `marks`: what holds without condition
    highest, or under a condition as high or higher? A hide: False, or a
    REVERT to the browser's own stylesheet that hides (`ua_sheet` for
    display, `ua_invisible` for visibility), a var()'s fallback that
    reverts so too (FALLBACK_REVERT: R6R-1)."""
    shown = [(s, t, c) for p, s, t, c in marks if p == prop]
    reverts_hide = ua_sheet if prop == "display" else ua_invisible

    def hides(s) -> bool:
        # A var()'s fallback that reverts to a hide hides too (R6R-1).
        return s is False or (_FALLBACKS.get(s, s) == REVERT
                              and reverts_hide)
    level = {t for s, t, c in shown if not c and hides(s)}
    top = max((t for _s, t, c in shown if not c), default=0)
    return any((s == LATER
                or (s in _FALLBACKS and not hides(s) and t in level))
               and t >= top and (c or t == top) for s, t, c in shown if t)


def cascade_decides(styles, el, prop: str, conditional: bool = True,
                    later_shows: bool = False) -> bool | None:
    """PageStyles.decides with the page's styles (`styles`), or, with none
    known (None), the style attribute's alone: whether what the cascade
    sets highest for `prop` shows `el`, hides it, or neither sets it. The
    style attribute is read here and nowhere before: a rule's !important
    beats it (R5K-5). `later_shows`: a visibility only known later shows
    (_decide)."""
    if styles is not None:
        return styles.decides(el, prop, conditional, later_shows)
    return _decide(_inline_marks(el), prop, conditional, _ua_sheet_hidden(el),
                   later_shows, prop == "visibility" and ua_invisible(el))


class PageStyles:
    """What the page's own <style> elements say about display and
    visibility, read as far as a file run can: top-level rules, nested
    ones, and those in a block every screen applies (@layer, @media
    screen, an @supports Chromium 141 passes, @scope with a root and no
    limit); of a rule under a condition (@media with features, an
    @supports the run cannot settle, @container, another @scope), only
    what it shows (style_rules). For the screen (a <style media> no screen
    matches is not read), with selectors the matcher reads (one that names
    :modal or ::before is skipped); a selector list Chromium 141 reads no
    part of (style_rules: one with an empty member, a pseudo-class or a
    pseudo-element Chromium does not have or an argument it does not take,
    or a selector neither Chromium nor the matcher reads, with what names
    a pseudo-class or a pseudo-element read as a simple selector:
    `#2:hover`, R6T-2) drops its rule, and the rules nested in it (R6F-3,
    R6H-2), and the namespaces a stylesheet declares are its
    selectors' (style_namespaces: R6H-8). Linked stylesheets are not
    read.

    Without specificity: of what the rules and the style attribute set on
    an element, the one highest in the cascade decides (layers and
    !important as CSS orders them: _marks), and where a rule that hides it
    and one that shows it stand level, it is read as shown: an element
    both hidden and shown by the page's rules (`.menu` and `.menu.is-open`)
    is read as shown. A conditional show counts where it could win
    (R5I-2).

    Rules are matched against an element when a rule asks about it, and
    only the rules whose rightmost id, class or tag the element has
    (_rightmost_key): a page with 2,000 rules and 8,000 elements no longer
    runs every rule over every element (P2-12).

    `scope(el)` names the tree an element is in (the document, or a shadow
    root): a <style> applies only to elements of its own tree, as a shadow
    root's styles do (OR-5), with two exceptions a shadow root's style has:
    `:host` or `:host(<compound>)` styles its host, and `::slotted(<compound>)`
    the light-DOM elements its slots show (OR2-8: `:host{display:block}`
    shows a host the page marked `hidden`). `:scope`, and `&` outside a
    rule that nests it, are the root element in a document's stylesheet
    outside @scope, and match nothing in a shadow root's (R6X-1, R6Z-8)."""

    def __init__(self, soup, inert=None, scope=None):
        import soupsieve
        self._by: dict[tuple[str, str], list] = {}
        self._any: list = []
        self._cache: dict[int, frozenset] = {}
        self._scope = scope or (lambda el: None)
        self._host: dict[int, list] = {}        # id(root wrapper) -> rules
        self._slotted: dict[int, list] = {}
        budget = [_MAX_NESTED_TOTAL]        # the page's, all its sheets'
        # The custom properties the page's own styles set anywhere (_marks);
        # none where a stylesheet the run does not read could set one
        # (_reads_other_sheets): a var() then stays only known later.
        own = [st.get_text() for st in soup.find_all("style")]
        self._custom = None if _reads_other_sheets(soup, own) else \
            custom_properties(own + [el.get("style")
                                     for el in soup.find_all(style=True)])
        for st in soup.find_all("style"):
            if inert is not None and inert(st):
                continue
            tree = self._scope(st)
            media = _media_kind(st.get("media") or "")
            kind = (st.get("type") or "").strip().lower()
            if media is None or kind not in _STYLE_TYPES:
                continue
            text = st.get_text()
            namespaces = style_namespaces(text)
            for selectors, body, conditional, layered in style_rules(
                    text, budget, namespaces):
                keys = _marks(_declarations(body, marked=True), layered,
                              conditional or media == "conditional",
                              custom=self._custom)
                if keys:
                    self._add(soupsieve, selectors, keys, tree, namespaces)

    def _add(self, soupsieve, selectors: str, keys, tree,
             namespaces: dict) -> None:
        """Read a rule's selector list, unless Chromium 141 drops the rule
        (R6F-3): a member it does not read (_selector_check), or one
        soupsieve does not read even with each pseudo-class, pseudo-element
        and `&` in it written as a simple selector it reads
        (_without_pseudos), which Chromium does not read either (`#2:hover`:
        R6T-2). A member soupsieve reads only so is skipped, as one that
        holds only with no script (_SCRIPTLESS_RE); what Chromium leaves
        out of a forgiving list is left out (_forgiven). Matched
        with the namespaces the stylesheet declares (style_namespaces: a
        default one too, which a selector with no prefix is in: R6H-8)."""
        parts = split_selectors(selectors, keep_empty=True)
        if not all(parts):
            return
        prefixes = frozenset(k for k in namespaces if k)
        found = []
        for sel in parts:
            readable, pseudo = _selector_check(sel, prefixes)
            if not readable:
                return
            if _SCRIPTLESS_RE.search(sel):
                if not _pieces_read(_without_pseudos(sel)):
                    return
                continue
            special = _HOST_RE.fullmatch(sel) or _SLOTTED_RE.fullmatch(sel)
            if special and tree is not None:
                inner = special.group(1)
                try:
                    pattern = (soupsieve.compile(
                        inner.strip(), namespaces=namespaces or None)
                               if inner and inner.strip() else None)
                except Exception:                      # noqa: BLE001
                    if _pieces_read(_without_pseudos(sel)):
                        continue
                    return
                table = (self._host if sel.lstrip().startswith(":host")
                         else self._slotted)
                found.append((table, id(tree), (pattern, keys)))
                continue
            sel = _c1_escaped(_plain_flags(_forgiven(_scope_as_root(
                sel, ":root" if tree is None else ":not(*)"), prefixes)))
            try:
                pattern = soupsieve.compile(sel,
                                            namespaces=namespaces or None)
            except Exception:                          # noqa: BLE001
                if pseudo and _pieces_read(_without_pseudos(sel)):
                    continue
                return
            key = _rightmost_key(sel)
            found.append((self._any if key is None else self._by, key,
                          (pattern, keys, tree)))
        for table, key, entry in found:
            if table is self._any:
                table.append(entry)
            else:
                table.setdefault(key, []).append(entry)

    def _keys(self, el) -> frozenset:
        """What the page's rules set on `el` (_marks)."""
        i = id(el)
        got = self._cache.get(i)
        if got is not None:
            return got
        candidates = list(self._any)
        if self._by:
            eid = el.get("id")
            if isinstance(eid, str):
                candidates += self._by.get(("id", eid.lower()), ())
            classes = el.get("class") or ()
            if isinstance(classes, str):
                classes = _HTML_TOKENS.findall(classes)     # R6X-2
            for c in set(c.lower() for c in classes):
                candidates += self._by.get(("class", c), ())
            if el.name:
                candidates += self._by.get(("tag", el.name.lower()), ())
        out = set()
        tree = self._scope(el)
        for pattern, keys, where in candidates:
            if keys <= out or where is not tree:
                continue
            try:
                if pattern.match(el):
                    out |= keys
            except Exception:                          # noqa: BLE001
                continue
        for pattern, keys in self._shadow_rules(el):
            try:
                if pattern is None or pattern.match(el):
                    out |= keys
            except Exception:                          # noqa: BLE001
                continue
        got = self._cache[i] = frozenset(out)
        return got

    def _shadow_rules(self, el) -> list:
        """The :host rules of `el`'s own shadow root, if it hosts one, and
        the ::slotted rules of the shadow root whose slot shows it."""
        if not (self._host or self._slotted):
            return []
        from .shadow import is_assigned, is_wrapper
        found = []
        if self._host:
            for child in el.children:
                if is_wrapper(child):
                    found += self._host.get(id(child), [])
                    break
        if self._slotted and is_assigned(el) and el.parent is not None:
            root = self._scope(el.parent)
            if root is not None:
                found += self._slotted.get(id(root), [])
        return found

    def decides(self, el, prop: str, conditional: bool = True,
                later_shows: bool = False) -> bool | None:
        """Whether what is set highest in the cascade shows `el` (True) or
        hides it (False) for `prop`, rules and style attribute together;
        None when neither sets it. A hide and a show at one level show it.
        `conditional`: whether a show under a condition counts;
        `later_shows`: whether a visibility only known later does."""
        marks = set(self._keys(el)) | _inline_marks(el, self._custom)
        return _decide(marks, prop, conditional, _ua_sheet_hidden(el),
                       later_shows, prop == "visibility" and ua_invisible(el))

    def hides(self, el, conditional: bool = True) -> str:
        """"display" or "visibility" when what the page's rules and the
        style attribute set highest on `el` hides it; else "".
        `conditional=False`: a show under a condition does not count."""
        if self.decides(el, "display", conditional) is False:
            return "display"
        if self.decides(el, "visibility", conditional) is False:
            return "visibility"
        return ""

    def shows_display(self, el) -> bool:
        return self.decides(el, "display") is True

    def marks(self, el) -> frozenset:
        """What the page's rules and `el`'s style attribute set on it of
        display and visibility (_marks)."""
        return frozenset(self._keys(el)) | _inline_marks(el, self._custom)

    def display_later(self, el) -> bool:
        """display_later, with the page's rules."""
        return _later(self.marks(el), "display", _ua_sheet_hidden(el))

    def shows_visibility(self, el, later_shows: bool = False) -> bool:
        return self.decides(el, "visibility", later_shows=later_shows) \
            is True


def ua_hidden(node) -> bool:
    """Hidden by the browser's own stylesheet alone: the `hidden` attribute
    (until-found aside), a <dialog> without `open`, a popover (closed until
    a script or an invoker opens it; not a <dialog open>: R6T-3). That
    stylesheet styles HTML elements only: `<svg hidden>` and a MathML
    element marked so are shown, as in Chromium 141 (R5O-11). A display
    the page sets overrides each of them, but none and revert-layer, and
    revert for a <dialog> or a popover (_decide)."""
    if node.has_attr("hidden"):
        if ((node.get("hidden") or "").lower() != "until-found"
                and namespace_of(node) == "html"):
            return True
    return _ua_sheet_hidden(node)


def ua_invisible(node) -> bool:
    """Does the browser's own stylesheet make `node` invisible
    (visibility:hidden): a MathML <mphantom>, as in Chromium 141, where a
    visibility the page sets overrides it, inherit and unset too
    (measured: R6I-5)?"""
    return getattr(node, "name", None) == "mphantom" and \
        namespace_of(node) == "math"


def _ua_sheet_hidden(node) -> bool:
    """A closed <dialog>, or a popover but an open <dialog> (the browser's
    own stylesheet hides `[popover]:not(:popover-open):not(dialog[open])`:
    R6T-3): what display:revert leaves hidden (HTML elements only, as
    ua_hidden)."""
    if not hasattr(node, "has_attr"):
        return False
    dialog = node.name == "dialog"
    if (dialog and not node.has_attr("open")) or (
            node.has_attr("popover") and not dialog):
        return namespace_of(node) == "html"
    return False


def until_found(node) -> bool:
    """hidden="until-found" (its value as written, in any case: a padded
    one is the plain hidden attribute, R5O-7) on an HTML element: the
    element is rendered, its content is not (content-visibility:hidden)
    until a find or a fragment reveals it."""
    return (node.has_attr("hidden")
            and (node.get("hidden") or "").lower() == "until-found"
            and namespace_of(node) == "html")


_NS_URIS = {"http://www.w3.org/1999/xhtml": "html",
            "http://www.w3.org/2000/svg": "svg",
            "http://www.w3.org/1998/Math/MathML": "math"}
#: SVG elements whose content is HTML, and MathML elements whose child
#: elements are (but <mglyph> and <malignmark>).
_SVG_HTML_POINTS = frozenset(("foreignobject", "desc", "title"))
_MATHML_TEXT_POINTS = frozenset(("mi", "mo", "mn", "ms", "mtext"))
#: <annotation-xml> holds HTML only with one of these encodings (any case).
_HTML_ENCODINGS = frozenset(("text/html", "application/xhtml+xml"))
#: Start tags at which the HTML parser leaves SVG or MathML content (and
#: <font> with color, face or size).
_BREAKOUT = frozenset((
    "b", "big", "blockquote", "body", "br", "center", "code", "dd", "div",
    "dl", "dt", "em", "embed", "h1", "h2", "h3", "h4", "h5", "h6", "head",
    "hr", "i", "img", "li", "listing", "menu", "meta", "nobr", "ol", "p",
    "pre", "ruby", "s", "small", "span", "strong", "strike", "sub", "sup",
    "table", "tt", "u", "ul", "var"))
_NS_MEMO = "_bb_namespace"


def namespace_of(el) -> str:
    """"html", "svg" or "math": the namespace of `el`. A page's own markup
    is parsed as a browser parses it (html5), and an XML document as XML
    (xhtml), both of which record each element's namespace. html.parser,
    which reads a rendered capture's serialization, records none, so there
    it is read from the root down as an HTML parser would: <svg> and
    <math> enter foreign content; an integration point of the right
    namespace, or a start tag that breaks out, returns to HTML (inside a
    MathML text integration point, <mglyph> and <malignmark> stay MathML).
    Each element read remembers what it found, so a deep page is read
    once."""
    recorded = getattr(el, "namespace", None)
    if recorded is not None:
        return _NS_URIS.get(recorded, "html")
    memo = getattr(el, "__dict__", {}).get(_NS_MEMO)
    if memo is not None:
        return memo[0]
    path = []
    node = el
    while (getattr(node, "parent", None) is not None
           and _NS_MEMO not in node.__dict__
           and getattr(node, "namespace", None) is None):
        path.append(node)
        node = node.parent
    if node is not el and getattr(node, "parent", None) is not None:
        # A remembered ancestor, or one the parser recorded.
        state = node.__dict__.get(_NS_MEMO) or _ns_state(
            node, _NS_URIS.get(node.namespace, "html"))
    else:
        state = ("html", "html", False, False)   # the document
    for node in reversed(path):
        _own, ctx, in_annotation, in_text_point = state
        name = (node.name or "").lower()
        if ctx == "html" and in_text_point and name in ("mglyph",
                                                         "malignmark"):
            own = "math"                    # these stay MathML there
        elif ctx == "html":
            own = name if name in ("svg", "math") else "html"
        elif name in _BREAKOUT or (name == "font" and any(
                node.has_attr(a) for a in ("color", "face", "size"))):
            own = "html"
        elif in_annotation and name == "svg":
            own = "svg"
        else:
            own = ctx
        state = node.__dict__[_NS_MEMO] = _ns_state(node, own)
    return state[0] if path else "html"


def _ns_state(node, own: str) -> tuple:
    """(namespace of `node`, of the elements it holds by default, inside
    an annotation-xml that holds no HTML?, inside a MathML text
    integration point?)"""
    name = (node.name or "").lower()
    if own == "svg":
        return own, "html" if name in _SVG_HTML_POINTS else "svg", False, False
    if own == "math":
        if name in _MATHML_TEXT_POINTS:
            return own, "html", False, True
        if name == "annotation-xml":
            inside = (node.get("encoding") or "").lower() in _HTML_ENCODINGS
            return own, "html" if inside else "math", not inside, False
        return own, "math", False, False
    return own, "html", False, False


#: The displays whose box Chromium 141 names from what it holds under
#: content-visibility:hidden (measured, R5M-2, R5N-6, R5O-7): an inline
#: box, an inline list item, a table and its parts but a cell (its columns
#: too), ruby and its text, contents. Every other box skips what it holds:
#: a block, an inline block, a flex or grid container, a list item (an
#: inline flow-root one too), a table cell, block ruby, MathML.
RENDERING_DISPLAYS = frozenset((
    "inline", "inline list-item", "table", "inline-table", "table-row-group",
    "table-header-group", "table-footer-group", "table-row",
    "table-column-group", "table-column", "table-caption", "ruby",
    "ruby-text", "contents", "none"))
#: HTML elements whose box skips what it holds whatever display they
#: compute (a <button> or a <fieldset> displayed inline, as a table row or
#: as ruby; a <canvas>, which computes inline: measured, R5Q-7).
_BOXED = frozenset(("button", "canvas", "fieldset"))
#: HTML elements whose content is their value, which content-visibility
#: does not hide from a name (Chromium 141 names a link holding a hidden
#: <textarea> by its text: measured, R5P-4).
_VALUE_CONTROLS = frozenset(("textarea", "input"))
#: How HTML's own stylesheet displays an element, where it is not inline:
#: as a block (its blocks, and what a form or a page holds), an inline
#: block (controls), or a part of a table or ruby. An image, a canvas, an
#: <svg>, an <iframe> or an <object> computes inline.
_DEFAULT_DISPLAY = dict(
    {tag: "block" for tag in (
        "address", "article", "aside", "blockquote", "body", "center",
        "dd", "details", "dialog", "dir", "div", "dl", "dt", "fieldset",
        "figcaption", "figure", "footer", "form", "frameset", "h1", "h2",
        "h3", "h4", "h5", "h6", "header", "hgroup", "hr", "html", "legend",
        "listing", "main", "menu", "nav", "ol", "optgroup", "option", "p",
        "plaintext", "pre", "search", "section", "ul", "xmp")},
    **{tag: "inline-block" for tag in (
        "button", "input", "marquee", "meter", "progress", "select",
        "textarea")},
    li="list-item", summary="list-item", td="table-cell", th="table-cell",
    table="table", tr="table-row", tbody="table-row-group",
    thead="table-header-group", tfoot="table-footer-group",
    caption="table-caption", col="table-column",
    colgroup="table-column-group", ruby="ruby", rt="ruby-text",
    slot="contents")
#: Two keywords as one value, as Chromium 141 computes them (an outer and
#: an inner display; `math` on an element that is not MathML is flow).
_DISPLAY_PAIRS = {
    ("block", "flow"): "block", ("inline", "flow"): "inline",
    ("block", "flow-root"): "flow-root", ("inline", "flow-root"): "inline-block",
    ("block", "flex"): "flex", ("inline", "flex"): "inline-flex",
    ("block", "grid"): "grid", ("inline", "grid"): "inline-grid",
    ("block", "table"): "table", ("inline", "table"): "inline-table",
    ("block", "ruby"): "block ruby", ("inline", "ruby"): "ruby",
    ("block", "math"): "block math", ("inline", "math"): "math"}
_DISPLAY_ALIASES = {"flow": "block", "-webkit-flex": "flex",
                    "-webkit-inline-flex": "inline-flex"}
#: What a box displayed so becomes when it is blockified (a float, an
#: absolutely positioned box, a flex or grid item): a part of a table or
#: of ruby becomes a block.
_BLOCKIFIED = dict(
    {d: "block" for d in (
        "inline", "inline-block", "table-row-group", "table-header-group",
        "table-footer-group", "table-row", "table-cell", "table-column-group",
        "table-column", "table-caption", "ruby-text")},
    **{"inline-flex": "flex", "inline-grid": "grid", "inline-table": "table",
       "inline list-item": "list-item",
       "inline flow-root list-item": "flow-root list-item",
       "ruby": "block ruby", "math": "block math",
       "-webkit-inline-box": "-webkit-box"})
#: Displays whose children are flex or grid items (a -webkit-box's are
#: not, in Chromium 141: R5O-7), as _keywords_display writes them.
_ITEM_PARENTS = frozenset(("flex", "inline-flex", "grid", "inline-grid"))
#: Where an element remembers its display and its box's (_display_of), and
#: whether it skips what it holds (skips_content): read once per element,
#: so a deep page costs no more than a shallow one (R5Q-1).
_DISPLAY_MEMO, _SKIPS_MEMO = "_bb_display", "_bb_skips"
#: A display only known later (var()), as remembered.
_LATER = "(later)"
#: Where a <details> remembers its first <summary> (first_summary).
_SUMMARY_MEMO = "_bb_first_summary"


def first_summary(details):
    """A <details>' first <summary> child: what it shows when closed, and
    the one child its own display places (_display_of). Found once per
    <details>: walks ask it for each child (R5S-1)."""
    got = details.__dict__.get(_SUMMARY_MEMO)
    if got is None:
        got = details.__dict__[_SUMMARY_MEMO] = (next(
            (c for c in details.children
             if getattr(c, "name", None) == "summary"), None),)
    return got[0]


def _html_display(node) -> str:
    """How the browser's own stylesheet displays `node`: by its HTML tag,
    or, in MathML, <math> as math and the rest as block math (an element
    of a drawing is never asked about: skips_content)."""
    ns = namespace_of(node)
    if ns == "math":
        return "math" if (node.name or "").lower() == "math" else "block math"
    if ns == "svg":
        return "inline"
    return _DEFAULT_DISPLAY.get(str(node.name or "").lower(), "inline")


def _keywords_display(value: str, node) -> str:
    """A display value the style attribute holds (one a browser takes,
    style._valid_style_value), as Chromium 141 computes it for `node`."""
    words = value.split()
    mathml = namespace_of(node) == "math"
    if len(words) == 1:
        word = _DISPLAY_ALIASES.get(words[0], words[0])
        return ("inline" if word == "math" and not mathml else word)
    seen = set(words)
    if "list-item" in seen:
        return (("inline " if "inline" in seen else "")
                + ("flow-root " if "flow-root" in seen else "") + "list-item")
    outer = "inline" if "inline" in seen else "block"
    inner = next(iter(seen - _DISPLAY_OUTER), "flow")
    got = _DISPLAY_PAIRS.get((outer, inner), outer)
    if inner == "math" and not mathml:
        return outer
    return got


def _own_display(node, decls: dict) -> str | None:
    """`node`'s display before it is blockified: its style attribute's,
    a CSS-wide keyword resolved (initial and unset are inline, revert and
    revert-layer HTML's own; inherit is _display_of's), else HTML's own.
    None where it is only known later (var())."""
    value = decls.get("display")
    if value is None or value in ("revert", "revert-layer"):
        return _html_display(node)
    if value in ("initial", "unset"):
        return "inline"
    if "(" in value:
        return None
    return _keywords_display(value, node)


def _display_parent(node):
    """`node`'s parent as display and inheritance read it (the flat tree):
    a shadow root's host for what the root holds at its top; None at the
    document."""
    from .shadow import is_wrapper
    parent = getattr(node, "parent", None)
    if is_wrapper(parent):
        parent = parent.parent
    if parent is None or not hasattr(parent, "get") \
            or parent.name == "[document]":
        return None
    return parent


def _computed_display(node, parent: tuple) -> tuple:
    """(`node`'s display, the display of the box its children are placed
    in) given its parent's, as _display_of remembers them."""
    parent_display, parent_box = parent
    decls = _inline_style(node.get("style"))
    if decls.get("display") == "inherit":
        own = parent_display
    else:
        own = _own_display(node, decls)
    if own not in ("contents", "none") and (
            decls.get("float") in ("left", "right", "inline-start",
                                   "inline-end")
            or decls.get("position") in ("absolute", "fixed")
            # A flex or grid item; one in a box only known later (var())
            # is read as one, as a box that skips is most often found to.
            or parent_box is None or parent_box in _ITEM_PARENTS
            # A <legend> is a block wherever it is (measured).
            or ((node.name or "").lower() == "legend"
                and namespace_of(node) == "html")):
        own = _BLOCKIFIED.get(own, own) if own is not None else None
    if (own != "none" and (node.name or "").lower() in ("details", "marquee")
            and namespace_of(node) == "html"):
        # What a <details> holds, but its first <summary>, and what a
        # <marquee> holds sit in a block box the element makes inside it,
        # whatever its display, contents too (measured: R5S-8). The first
        # summary is placed by the <details>' own display (_display_of).
        return own, "block"
    if own == "contents":
        return own, parent_box
    return own, own


def _display_memo(node) -> tuple:
    """(display, box) as `node` remembers them (_display_of)."""
    if _DISPLAY_MEMO not in node.__dict__:
        _display_of(node)
    return node.__dict__[_DISPLAY_MEMO]


def _summary_box(details) -> str:
    """The box a <details>' first <summary> is placed in: the <details>'
    own, or, where it is displayed as contents, the one it is in."""
    own = _display_memo(details)[0]
    if own != "contents":
        return own
    up = _display_parent(details)
    return _display_memo(up)[1] if up is not None else "block"


def _display_of(node) -> str | None:
    """`node`'s display as Chromium 141 computes it, as far as style
    attributes and HTML say (a stylesheet's display is not read: L98): its
    style attribute's (_own_display; inherit takes its parent's computed
    display, or for what a <details> or a <marquee> holds, the display of
    the slot it is in: block, or contents for the first <summary> and a
    <marquee>'s: R6B-9), else HTML's own, blockified where its style
    attribute floats it or positions it absolutely, where its parent's box
    (through any element displayed as contents, a <slot> by default, and
    up from a shadow root to its host) makes it a flex or grid item, and
    for a <legend>. What a <details> or a <marquee> holds is in a block box the
    element makes inside, never an item, but a <details>' first <summary>,
    which its display places (R5S-8). None where it is only known later
    (var()). Each element remembers its own, so the walk is once per
    element (R5Q-1)."""
    # Up to the nearest element that remembers its display, or the top:
    # no cap, so nothing is remembered from a guess (R5S-3); a page's
    # depth is bounded where it is read (checks_static.too_deep).
    path = []
    cur = node
    while cur is not None and _DISPLAY_MEMO not in cur.__dict__:
        path.append(cur)
        cur = _display_parent(cur)
    # Above the walk: what an element is in at the top of a page.
    parent = (cur.__dict__[_DISPLAY_MEMO] if cur is not None
              else ("inline", "block"))
    for el in reversed(path):
        parent_display, parent_box = parent
        up = _display_parent(el)
        holder = (up.name or "").lower() if up is not None else ""
        if holder not in ("details", "marquee") \
                or namespace_of(up) != "html":
            holder = ""
        if holder == "details" and first_summary(up) is el:
            parent_box = _summary_box(up)
        if holder in ("details", "marquee"):
            # inherit takes the display of the slot of the element's own
            # shadow tree it is placed in: a block for what a <details>
            # holds, contents for its first <summary> and for what a
            # <marquee> holds (measured: R6B-9).
            parent_display = ("block" if holder == "details"
                              and first_summary(up) is not el
                              else "contents")
        own, box = _computed_display(el, (
            None if parent_display == _LATER else parent_display,
            None if parent_box == _LATER else parent_box))
        parent = el.__dict__[_DISPLAY_MEMO] = (
            _LATER if own is None else own, _LATER if box is None else box)
    got = node.__dict__[_DISPLAY_MEMO][0]
    return None if got == _LATER else got


def skips_content(node) -> bool:
    """Is `node` rendered while what it holds is not: hidden="until-found"
    (an HTML element's), or content-visibility:hidden in its style
    attribute, on a box Chromium 141 skips the content of (not
    RENDERING_DISPLAYS, by the display _display_of reads; a <button>, a
    <fieldset> or a <canvas> whatever its display, and every element of a
    drawing, the <svg> and its <foreignObject> included: measured)? A
    <span hidden="until-found"> renders what it holds, and a <table> or a
    <tr> does too; a <div>, a <button> or a <td> does not (R5K-10, R5M-2,
    R5O-7, R5Q-6, R5Q-7). The text of a <textarea> is its value, which
    stays (R5P-4). A display only known later (var()) is read as one that
    skips, as most do. A display or content-visibility a stylesheet sets
    is not read here (L98). Remembered per element."""
    got = node.__dict__.get(_SKIPS_MEMO)
    if got is None:
        got = node.__dict__[_SKIPS_MEMO] = _skips_content(node)
    return got


def _skips_content(node) -> bool:
    decls = _inline_style(node.get("style"))
    if not (decls.get("content-visibility") == "hidden" or until_found(node)):
        return False
    ns = namespace_of(node)
    name = (node.name or "").lower()
    if ns == "html" and name in _VALUE_CONTROLS:
        return False
    display = _display_of(node)
    if display in ("none", "contents"):
        return False
    if ns == "svg" or (ns == "html" and name in _BOXED):
        return True
    return display not in RENDERING_DISPLAYS
