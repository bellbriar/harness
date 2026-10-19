"""bellbriar-lint — source-level accessibility lint for agent-generated code.

Mechanizes the deterministically-greppable slice of the WCAG pack's
failure-signature table. Runs on *source* (JSX/TSX/Vue/HTML/CSS) before
build; the eval gate (`bellbriar-eval`) runs on built DOM after. They
overlap on purpose: lint catches the habit at the line where the agent
typed it, the gate proves the output.

Honesty model, same as the harness: `error` findings are patterns that
are wrong essentially always; `warn` findings need a human or the gate
to confirm. Regex has limits — this tool asserts nothing it can't see,
and a clean lint is not a clean gate.

Suppressions (each one belongs in the delivery notes):
    // bellbriar-lint-disable-next-line bl-rule-id
    <div onClick={…}>            {/* bellbriar-lint-disable-line */}
"""
from __future__ import annotations

import argparse
import bisect
import functools
import json
import os
import re
import stat
import subprocess
import sys
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

ERROR = "error"
WARN = "warn"

CODE_EXTS = {".jsx", ".tsx", ".js", ".ts", ".mjs", ".vue", ".svelte"}
MARKUP_EXTS = {".html", ".htm"} | CODE_EXTS
CSS_EXTS = {".css", ".scss", ".less"}
ALL_EXTS = MARKUP_EXTS | CSS_EXTS
#: Folders a scan of a directory never enters: dependencies, build output
#: and caches of the common front-end tools, and Python environments. A
#: folder named on the command line is scanned whatever its name.
SKIP_DIRS = {"node_modules", ".git", "dist", "build", ".next", "out",
             ".nuxt", "coverage", "vendor", "__pycache__",
             ".svelte-kit", ".output", ".vercel", ".netlify", ".astro",
             ".angular", ".docusaurus", ".expo", ".wrangler", ".turbo",
             ".nx", ".cache", ".parcel-cache", "storybook-static", "_site",
             "bower_components", "jspm_packages", ".yarn", ".pnpm-store",
             ".venv", "venv"}

DISABLE_LINE = "bellbriar-lint-disable-line"
DISABLE_NEXT = "bellbriar-lint-disable-next-line"


@dataclass
class Finding:
    rule_id: str
    severity: str
    path: str
    line: int
    message: str
    ref: str
    snippet: str


def _line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def _snippet(text: str, pos: int) -> str:
    start = text.rfind("\n", 0, pos) + 1
    end = text.find("\n", pos)
    if end == -1:
        end = len(text)
    return text[start:end].strip()[:160]


# ---------------------------------------------------------------------------
# Pattern rules: (id, severity, exts, compiled regex, message, pack ref)
# ---------------------------------------------------------------------------

_P = [
    ("bl-zoom-block", ERROR, ALL_EXTS,
     re.compile(r'user-scalable\s*=\s*(no|0)\b'
                r'|maximum-scale\s*=\s*(0(\.\d+)?|1(\.\d+)?)\b'
                r'|userScalable\s*:\s*(false|0)\b'
                r'|maximumScale\s*:\s*(0(\.\d+)?|1(\.\d+)?)\b'),
     "Viewport blocks or caps zoom below 200% — a pled barrier and an "
     "instant gate failure. Remove the cap entirely.", "STR-1"),
    # A warning, as the eval gate treats it (rulebook 0.3.0): WCAG fails a
    # positive tabindex only when the order loses meaning (F44).
    ("bl-positive-tabindex", WARN, MARKUP_EXTS,
     re.compile(r'tab[Ii]ndex\s*=\s*["\'{]?\s*[1-9]'),
     "Positive tabindex overrides focus order; check the order still "
     "makes sense and prefer DOM order with tabindex 0/-1 — a best "
     "practice; not a WCAG failure on its own.", "AGT-1"),
    ("bl-marquee-blink", ERROR, MARKUP_EXTS,
     re.compile(r'<\s*marquee\b', re.I),
     "Auto-moving content with no pause control.", "VIS-8"),
    # W3C made its failure for <blink> (F47) obsolete: no current browser
    # makes the element blink, so it moves nothing.
    ("bl-marquee-blink", WARN, MARKUP_EXTS,
     re.compile(r'<\s*blink\b', re.I),
     "<blink> is obsolete and no current browser makes it blink, so it is "
     "plain text — remove it.", "VIS-8"),
    ("bl-junk-alt-src", ERROR, MARKUP_EXTS,
     re.compile(r'alt\s*=\s*["\'][^"\']*\.(jpe?g|png|gif|webp|avif)\b'
                r'|alt\s*=\s*\{[^}]*\.\s*(src|image|img|file(?:name)?)\s*[})]'),
     "alt is a filename or an image-path expression — write the text "
     "alternative from the page's purpose (or alt=\"\" if decorative).",
     "IMG-1"),
    ("bl-css-order", WARN, CSS_EXTS,
     re.compile(r'\border\s*:\s*-?\d'
                r'|flex-direction\s*:\s*(row|column)-reverse'),
     "CSS re-ordering detected — if this re-sequences content (not pure "
     "decoration), reading and tab order break: author the DOM in "
     "reading order instead.", "STR-5"),
    ("bl-carousel-autoplay", WARN, CODE_EXTS,
     re.compile(r'\bautoplay\s*[:=]\s*[{\[]?\s*(true|\{|\d)', re.I),
     "Carousel/slider autoplay config — pack default is no auto-rotation; "
     "if the client insists, the conforming variant applies (pause first "
     "in tab order, stops on hover/focus, off under reduced motion).",
     "WGT-6"),
    ("bl-dangerous-html", WARN, CODE_EXTS,
     re.compile(r'dangerouslySetInnerHTML|v-html\s*='),
     "Injected HTML is outside compile-time control — run the eval gate "
     "against the rendered output, not just source.", "SPA-5"),
    ("bl-autofocus", WARN, MARKUP_EXTS,
     re.compile(r'\bautoFocus\b|<[^>]{0,200}\bautofocus\b', re.S),
     "autofocus skips the skip link and disorients screen-reader users; "
     "reserve for true single-purpose views.", "SPA-5"),
    ("bl-doc-link", WARN, MARKUP_EXTS,
     re.compile(r'href\s*=\s*["\'][^"\']*\.(pdf|docx?|xlsx?|pptx?)["\']', re.I),
     "Links to a document file — essential content ships as HTML; the "
     "file is outside evaluation scope and needs manual remediation.", "EXC-2"),
]

# bl-conditional-live-region and bl-meta-refresh read attribute values, so
# they run on scanned tags (below) rather than as line patterns.


# ---------------------------------------------------------------------------
# Tag scanning (attribute-aware, multi-line tags)
# ---------------------------------------------------------------------------

_TAG_OPEN = re.compile(r'<(?P<name>[A-Za-z][\w.-]*)\b')
_TAG_STOP = re.compile(r'[\\"\'`{}<>/]')
_TAG_SIMPLE = re.compile(r'<(?P<name>[A-Za-z][\w.-]*)\b(?P<attrs>[^>]{0,600})>',
                         re.S)
#: Longest start tag the scanner follows, in characters.
_TAG_LIMIT = 4000
#: What may come right before an attribute name: whitespace, the end of a
#: quoted value or {…} expression, or a Vue/Svelte/Angular binding prefix.
_ATTR_START = r'(?:^|(?<=[\s{}"\':@\[(]))'
_WORDISH = re.compile(r'[\w$)\]]')
#: A JSX spread in attribute position: {...props}.
_SPREAD = re.compile(r'(?:^|\s)\{\s*\.\.\.')


@dataclass
class _Tag:
    name: str
    start: int   # offset of the '<'
    end: int     # offset just past the closing '>'
    attrs: str   # raw text between the name and the closing '>'
    names: str   # attrs with every quoted value and {…} expression blanked

    @property
    def self_closing(self) -> bool:
        return self.attrs.rstrip().endswith("/")


def _blank(attrs: str, spans: list) -> str:
    chars = list(attrs)
    for a, b in spans:
        chars[a:b] = " " * (b - a)
    return "".join(chars)


def _after_equals(text: str, j: int, begin: int) -> bool:
    k = j - 1
    while k >= begin and text[k] in " \t\r\n":
        k -= 1
    return k >= begin and text[k] == "="


def _scan_tag(text: str, m: re.Match):
    """Follow one start tag to its real end.

    A JSX attribute can hold any expression: an arrow function (`=>`), a
    comparison, a nested element. So the first '>' is not the end of the
    tag. The scanner tracks quotes, template literals, comments and brace
    depth, and the tag ends at the first '>' outside all of them.

    Returns None when this '<' does not start a tag (another '<' turns up at
    tag level: a comparison or a type argument), and False when the tag does
    not close within _TAG_LIMIT characters.
    """
    begin = i = m.end()
    stop = min(len(text), begin + _TAG_LIMIT)
    stack: list[str] = []              # open contexts: '{', '"', "'", '`'
    spans: list[tuple[int, int]] = []  # tag-level values, relative to begin
    opened = begin
    while True:
        s = _TAG_STOP.search(text, i, stop)
        if s is None:
            return False
        j = s.start()
        c = text[j]
        top = stack[-1] if stack else ""
        if top in ('"', "'"):
            if c == "\\" and len(stack) > 1:   # escapes exist in JS only
                i = j + 2
                continue
            if c == top:
                stack.pop()
                if not stack:
                    spans.append((opened + 1 - begin, j - begin))
            i = j + 1
            continue
        if top == "`":
            if c == "\\":
                i = j + 2
                continue
            if c == "`":
                stack.pop()
            elif c == "{" and text[j - 1] == "$":
                stack.append("{")
            i = j + 1
            continue
        # At tag level, or inside a {…} expression.
        if c == "/" and top == "{" and text.startswith(("//", "/*"), j):
            if text.startswith("/*", j):
                k = text.find("*/", j + 2, stop)
                i = stop if k == -1 else k + 2
            else:
                k = text.find("\n", j + 2, stop)
                i = stop if k == -1 else k + 1
            continue
        if c in "\"'":
            if top == "{":
                # Right after a word character a quote is an apostrophe in
                # JSX text ("Don't"), not the start of a JS string.
                if not _WORDISH.match(text, j - 1):
                    stack.append(c)
            elif _after_equals(text, j, begin):
                opened = j
                stack.append(c)
        elif c == "`":
            if top == "{":
                stack.append(c)
        elif c == "{":
            if not stack:
                opened = j
            stack.append(c)
        elif c == "}":
            if top == "{":
                stack.pop()
                if not stack:
                    spans.append((opened + 1 - begin, j - begin))
        elif c == ">" and not stack:
            attrs = text[begin:j]
            return _Tag(m.group("name"), m.start(), j + 1, attrs,
                        _blank(attrs, spans))
        elif c == "<" and not stack:
            return None
        i = j + 1


def _simple_tag(text: str, start: int):
    """The old reading, to the first '>'. Used only when a tag never closes,
    so a tag the scanner cannot follow still gets checked."""
    m = _TAG_SIMPLE.match(text, start)
    if m is None:
        return None
    attrs = m.group("attrs")
    spans = [(x.start() + 1, x.end() - 1) for x in
             re.finditer(r'"[^"]*"|\'[^\']*\'|\{[^{}]*\}', attrs)]
    return _Tag(m.group("name"), m.start(), m.end(), attrs,
                _blank(attrs, spans))


def _iter_tags(text: str):
    for m in _TAG_OPEN.finditer(text):
        t = _scan_tag(text, m)
        if t is False:
            t = _simple_tag(text, m.start())
        if t is not None:
            yield t


def _has(t: _Tag, attr: str, flags: int = 0) -> bool:
    """Does the tag carry this attribute? `attr` is a regex over attribute
    names; values are blank in t.names, so text inside them never matches."""
    return re.search(_ATTR_START + r'(?:' + attr + r')(?=[\s=/>]|$)',
                     t.names, flags) is not None


def _attr(t: _Tag, attr: str, flags: int = 0):
    """The attribute's value as (kind, text). kind is "str" for a quoted
    value or a string literal in braces, "expr" for any other {…} expression
    (text without the braces), "bare" for an unquoted value. None when the
    attribute is absent or has no value."""
    m = re.search(_ATTR_START + r'(?:' + attr + r')\s*=\s*', t.names, flags)
    if m is None or m.end() >= len(t.names):
        return None
    return _value_at(t, m.end())


def _value_at(t: _Tag, i: int):
    """The value starting at offset i of t.attrs, as _attr returns it. A
    Lit binding, `x=${…}` or `x="${…}"`, is an expression."""
    c = t.names[i]
    if c == "$" and t.names.startswith("{", i + 1):
        j = t.names.find("}", i + 2)
        return ("expr", t.attrs[i + 2:j if j != -1 else len(t.attrs)].strip())
    if c in "\"'":
        j = t.names.find(c, i + 1)
        text = t.attrs[i + 1:j if j != -1 else len(t.attrs)]
        lit = re.fullmatch(r'\s*\$\{(.*)\}\s*', text, re.S)
        if lit and "${" not in lit.group(1):
            return ("expr", lit.group(1).strip())
        return ("str", text)
    if c == "{":
        j = t.names.find("}", i + 1)
        inner = t.attrs[i + 1:j if j != -1 else len(t.attrs)].strip()
        lit = re.fullmatch(r'(["\'`])(.*)\1', inner, re.S)
        if lit and not (lit.group(1) == "`" and "${" in inner):
            return ("str", lit.group(2))
        return ("expr", inner)
    return ("bare", re.match(r'[^\s/>]*', t.attrs[i:]).group(0))


#: Spellings of an attribute in a start tag: plain (HTML, JSX, Svelte), and
#: bound — `:x`, `v-bind:x`, `x-bind:x`, Svelte `bind:x` (with modifiers
#: such as `.prop`), Angular `[x]` and `[attr.x]`, Lit `?x` and `.x`. A
#: bound value is an expression. Other directives that end in the same
#: name (Svelte `class:muted`, `style:x`) are not the attribute.
_BOOL_FORMS = (
    (r'(?:^|(?<=[\s{}"\']))(?:{a})(?=[\s=/>]|$)', False),
    (r'(?:^|(?<=[\s{}"\']))(?:v-bind|x-bind|bind)?:(?:{a})(?:\.[\w-]+)*'
     r'(?=[\s=/>]|$)', True),
    (r'(?:^|(?<=[\s{}"\']))\[(?:attr\.)?(?:{a})\](?=[\s=/>]|$)', True),
    (r'(?:^|(?<=[\s{}"\']))[?.](?:{a})(?=[\s=/>]|$)', True),
)
#: An expression that is plainly false or true: `false`, `{false}`,
#: `${false}`.
_FALSE_EXPR = re.compile(r'\$?\{\s*false\s*\}|false')
_TRUE_EXPR = re.compile(r'\$?\{\s*true\s*\}|true')
#: The state of a boolean attribute: on, off, or set by an expression the
#: linter cannot read.
ON, OFF, UNKNOWN = "on", "off", "unknown"


def _tag_braces(t: _Tag) -> list[str]:
    """The text of each {…} in attribute position that is not a value: a
    spread (`{...props}`) or a Svelte shorthand (`{muted}`)."""
    out = []
    for m in re.finditer(r'\{', t.names):
        j = m.start()
        k = j - 1
        while k >= 0 and t.names[k] in " \t\r\n":
            k -= 1
        if k >= 0 and t.names[k] in "=$":
            continue                        # a value, or Lit's ${…}
        close = t.names.find("}", j + 1)
        if close != -1:
            out.append(t.attrs[j + 1:close].strip())
    return out


def _spread(t: _Tag) -> bool:
    """Attributes the linter cannot see: a JSX or Svelte spread, Vue
    `v-bind="obj"` (with modifiers, `v-bind.prop="obj"`), Alpine
    `x-bind="obj"`, or a Vue dynamic argument (`:[name]="v"`)."""
    return (any(b.startswith("...") for b in _tag_braces(t))
            or re.search(r'(?:^|\s)(?:v-bind|x-bind)(?:\.[\w-]+)*\s*=',
                         t.names) is not None
            or re.search(r'(?:^|\s)(?:v-bind:|x-bind:|:)\[', t.names) is not None)


def _spread_after(t: _Tag, at: int) -> bool:
    """A spread that can set or replace an attribute written at offset `at`
    of t.attrs: a JSX or Svelte spread after it (a later attribute wins),
    or, anywhere, Vue's or Alpine's `v-bind="obj"`, which merges classes."""
    if re.search(r'(?:^|\s)(?:v-bind|x-bind)(?:\.[\w-]+)*\s*=', t.names) \
            or re.search(r'(?:^|\s)(?:v-bind:|x-bind:|:)\[', t.names):
        return True
    for m in re.finditer(r'\{', t.names):
        j = m.start()
        k = j - 1
        while k >= 0 and t.names[k] in " \t\r\n":
            k -= 1
        if j < at or (k >= 0 and t.names[k] in "=$"):
            continue
        close = t.names.find("}", j + 1)
        if close != -1 and t.attrs[j + 1:close].strip().startswith("..."):
            return True
    return False


def _bool_state(t: _Tag, attr: str, svelte: bool = False,
                flags: int = 0) -> str | None:
    """A boolean attribute's state: ON, OFF, UNKNOWN, or None when absent.

    Present with no value, or with a plain HTML value, it is on whatever
    the value says (`muted="false"` mutes), and so is a JSX string
    (`{"false"}`); the string "false" in a .svelte file is UNKNOWN. Plainly bound to
    false it is off — JSX or Svelte `controls={false}`, Vue
    `:controls="false"`, Angular `[controls]="false"`, Lit
    `?controls=${false}`, and in a .svelte file `controls="{false}"`. A
    plain Lit binding (`muted=${false}`) is UNKNOWN: Lit writes the text
    "false", which is on, and htm gives JSX's meaning, which is off. Any
    other expression (`bind:muted={m}`, `{!x}`), a Svelte shorthand
    (`{muted}`), or an absent attribute beside a spread (`{...props}`,
    `v-bind="$attrs"`) is UNKNOWN, so an error is never raised on a
    guess."""
    for form, bound in _BOOL_FORMS:
        m = re.search(form.replace("{a}", attr), t.names, flags)
        if m is None:
            continue
        eq = re.match(r'\s*=\s*', t.names[m.end():])
        value = None
        if eq is not None and m.end() + eq.end() < len(t.names):
            value = _value_at(t, m.end() + eq.end())
        raw = t.attrs[m.end() + eq.end():].lstrip("\"'")[:2] \
            if eq is not None else ""
        if value is None:
            state = UNKNOWN if bound else ON          # a bare attribute
        elif raw == "${" and not bound:
            # Lit sets a plain attribute to the value's text (muted="false"
            # is on) and htm gives it JSX's meaning (off): which is unknown.
            state = UNKNOWN
        else:
            kind, text = value[0], value[1].strip()
            if kind == "expr" or bound:
                state = (OFF if _FALSE_EXPR.fullmatch(text) else
                         ON if _TRUE_EXPR.fullmatch(text) or kind == "str"
                         and not bound else UNKNOWN)
            elif svelte and text.startswith("{"):
                state = (OFF if re.fullmatch(r'\{\s*false\s*\}', text) else
                         ON if re.fullmatch(r'\{\s*true\s*\}', text)
                         else UNKNOWN)
            elif svelte and text.lower() == "false":
                # What Svelte does with the string "false" on a boolean
                # media attribute depends on how it sets it: a property is
                # truthy, an attribute set after creation leaves `muted` off.
                state = UNKNOWN
            else:
                state = ON
        if state != ON and _spread(t):
            return UNKNOWN                  # a spread may set it
        return state
    if any(re.fullmatch(attr, b, flags) for b in _tag_braces(t)):
        return UNKNOWN                      # Svelte shorthand: {muted}
    return UNKNOWN if _spread(t) else None


#: An expression that plainly gives no URL: an empty string, or null or
#: undefined where the framework then leaves the attribute out (JSX,
#: Svelte braces, Vue and Alpine `:src`). A property binding (Angular
#: `[src]`, Lit `.src`) writes null as the string "null", which is a URL.
_NO_URL_EXPR = re.compile(r'\s*(?:(["\'`])\s*\1|null|undefined|void\s+0)?\s*')
_EMPTY_LITERAL = re.compile(r'\s*(?:(["\'`])\s*\1)?\s*')


def _media_source(text: str, t: _Tag) -> bool:
    """A src on the tag, or a <source> child with one, as the gate reads
    it: a bound src resolves in the built page unless it plainly gives no
    URL (_NO_URL_EXPR); a plain one that is empty (`src=""`, bare `src`)
    is no source."""
    vue = _attr(t, r'(?:v-bind|x-bind)?:src', re.I)
    if vue is not None:
        if not _NO_URL_EXPR.fullmatch(vue[1]):
            return True
    elif re.search(_ATTR_START + r'(?:(?:v-bind|x-bind|bind)?:|\[|\.)src'
                   r'\]?(?=[\s=/>]|$)', t.names, re.I):
        prop = _attr(t, r'(?:bind:|\[(?:attr\.)?|\.)src\]?', re.I)
        if prop is None or not _EMPTY_LITERAL.fullmatch(prop[1]):
            return True                     # bound
    value = _attr(t, "src", re.I) if vue is None else None
    if value is not None and (
            value[1].strip() if value[0] != "expr"
            else not _NO_URL_EXPR.fullmatch(value[1])):
        return True
    if t.self_closing:
        return False
    close = re.search(r'</\s*(?:audio|video)\s*>', text[t.end:], re.I)
    inner = text[t.end:t.end + close.start()] if close else text[t.end:]
    return re.search(r'<source\b[^>]*?(?:[\s:.\[]src\]?\s*=\s*'
                     r'(?:"\s*[^"\s]|\'\s*[^\'\s]|\{|[^\s"\'>]))', inner,
                     re.I) is not None


def _inside_inert(text: str, pos: int) -> bool:
    """In an HTML file, inside a <template> (one Alpine or petite-vue
    renders, with x-if/x-for or v-if/v-for, aside) or a <noscript>."""
    stack: list[bool] = []
    for m in re.finditer(r'<(/?)(template|noscript)\b([^>]*)>', text[:pos],
                         re.I):
        if m.group(1):
            if stack:
                stack.pop()
        else:
            stack.append(m.group(2).lower() == "noscript" or not re.search(
                r'\b(?:x|v)-(?:if|for)\b', m.group(3)))
    return any(stack)


def _spellings(attr: str) -> str:
    """A regex, for _has, over an attribute's spellings on a start tag:
    plain (HTML, JSX, Svelte) and bound — Vue `:x` and `v-bind:x`, Alpine
    `x-bind:x`, Svelte `bind:x`, Angular `[x]` and `[attr.x]`, Lit `.x`
    and `?x`."""
    return (rf'(?:(?:v-bind|x-bind|bind)?:|[.?])?(?:{attr})(?:\.[\w-]+)*'
            rf'|\[(?:attr\.)?(?:{attr})\]')


def _has_any(t: _Tag, attr: str) -> bool:
    """The attribute in any spelling (_spellings), or as a Svelte
    shorthand (`{href}`)."""
    return _has(t, _spellings(attr)) or any(
        re.fullmatch(attr, b) for b in _tag_braces(t))


def _attr_any(t: _Tag, attr: str):
    """(value, bound) for the attribute's first spelling on the tag: the
    value as _value_at gives it (None when it has none), and whether the
    spelling is bound, so its value is an expression. None when absent."""
    m = re.search(_ATTR_START + r'(?:' + _spellings(attr) + r')(?=[\s=/>]|$)',
                  t.names)
    if m is None:
        return None
    bound = re.fullmatch(attr, m.group(0)) is None   # :x, [x], x.prop …
    eq = re.match(r'\s*=\s*', t.names[m.end():])
    at = m.end() + eq.end() if eq else len(t.names)
    return (_value_at(t, at) if at < len(t.names) else None), bound


def _aria_hidden(t: _Tag):
    """Is the element aria-hidden? True, False, or None when an expression
    the linter cannot read decides it (Vue `:aria-hidden="open"`, Angular
    `[attr.aria-hidden]="!open"`, JSX `aria-hidden={!open}`). A plain
    attribute hides unless it says "false"."""
    got = _attr_any(t, "aria-hidden")
    if got is None:
        return False
    value, bound = got
    if value is None:
        return None if bound else True
    kind, text = value[0], value[1].strip()
    if not bound and kind != "expr":
        return text.lower() != "false"
    text = text.strip("'\"`")
    if _TRUE_EXPR.fullmatch(text):
        return True
    if _FALSE_EXPR.fullmatch(text):
        return False
    return None


def _event_attr(event: str, camel: str) -> str:
    """The spellings of a DOM event's handler on a start tag (P3-10): HTML
    and Svelte 5 `onclick`, JSX `onClick`, Vue, Alpine and Lit `@click`,
    `v-on:click` and `x-on:click` (with modifiers, `@click.stop`), Svelte 4
    `on:click` (with modifiers, `on:click|preventDefault`), Angular
    `(click)`."""
    return (rf'on(?:{event}|{camel})'
            rf'|(?:@|v-on:|x-on:){event}(?:\.[\w-]+)*'
            rf'|on:{event}(?:\|[\w|]+)*'
            rf'|\({event}\)')


_CLICK = _event_attr("click", "Click")
_DOWN = (_event_attr("mousedown", "MouseDown") + "|"
         + _event_attr("pointerdown", "PointerDown"))
#: Event modifiers that only stop the event or its default action.
_STOP_MODIFIERS = {"stop", "prevent", "stopPropagation", "preventDefault",
                   "stopImmediatePropagation"}
#: Modifiers that take a listener off the element: Alpine's `.outside`
#: (`.away` before Alpine 3), `.window` and `.document`, and Vue's `.right`
#: and `.middle`, which listen for contextmenu and mouseup instead.
_ELSEWHERE_MODIFIERS = {"outside", "away", "window", "document", "right",
                        "middle"}


def _modifiers(name: str) -> set:
    return set(re.split(r'[.|]', name)[1:])


#: Vue's own modifiers that move a listener (Alpine's others mean nothing
#: to Vue, which reads unknown modifiers only on key events).
_VUE_ELSEWHERE = {"right", "middle"}


def _handlers(t: _Tag, attr: str, vue: bool = False) -> list:
    """[(attribute name as written, value as _value_at gives it, or None
    when it has none)] for each handler attribute matching `attr` that
    listens on the element itself, in source order (Svelte 4 allows
    several). In a .vue file only Vue's modifiers count."""
    out = []
    elsewhere = _VUE_ELSEWHERE if vue else _ELSEWHERE_MODIFIERS
    for m in re.finditer(_ATTR_START + r'(?:' + attr + r')(?=[\s=/>]|$)',
                         t.names):
        if _modifiers(m.group(0)) & elsewhere:
            continue
        eq = re.match(r'\s*=\s*', t.names[m.end():])
        at = m.end() + eq.end() if eq else len(t.names)
        out.append((m.group(0),
                    _value_at(t, at) if at < len(t.names) else None))
    return out


_EVENT_ONLY = re.compile(
    r'(?:\s*[A-Za-z_$][\w$]*\??\.(?:stopPropagation|stopImmediatePropagation'
    r'|preventDefault)\(\)\s*[;,]?)+\s*')
_ARROW_FN = re.compile(r'\s*(?:async\s+)?(?:\([^()]*\)|[A-Za-z_$][\w$]*)\s*'
                       r'(?::[^=]*)?=>\s*(?P<body>.*)', re.S)
_PLAIN_FN = re.compile(r'\s*(?:async\s+)?function\b[^(]*\([^()]*\)\s*'
                       r'(?P<body>\{.*\})\s*', re.S)
_STOP_HELPER = re.compile(r'\s*[\w$.]*[sS]topPropagation\s*')


def _handler_only_stops(name: str, value) -> bool:
    """Is this handler attribute nothing but stopping the event? With no
    value, its modifiers say (Vue `@click.stop`, Svelte 4
    `on:click|stopPropagation`). A framework's quoted value is script
    (Vue, Alpine, Angular), so both statements and a function are read."""
    if value is None:
        return bool(_modifiers(name) & _STOP_MODIFIERS)
    kind, code = value
    if kind == "str" and not re.match(r'on[A-Za-z]', name):
        return (_EVENT_ONLY.fullmatch(code) is not None
                or _only_stops_event("expr", code))
    return _only_stops_event(kind, code)


#: Elements that take keyboard focus by themselves, and the components of
#: the common frameworks and libraries that render one: router links,
#: button and form-field components.
_FOCUSABLE_TAGS = {"a", "button", "select", "textarea", "summary", "iframe",
                   "Link", "NavLink", "RouterLink", "router-link", "NuxtLink",
                   "nuxt-link", "Button", "IconButton", "Input", "TextField",
                   "Textarea", "Select", "Checkbox", "Switch", "Radio"}


def _focusable(t: _Tag) -> bool:
    """Does this element take keyboard focus (or render one that does)? A
    link needs an href, in any spelling (`[href]`, `routerLink`, `{href}`)
    or possibly from a spread; a component given an href renders a link
    (`to` is not counted: <Teleport to="body"> takes one too). An <svg>
    <use href> is no link."""
    if t.name in ("a", "area"):
        return _has_any(t, "href|routerLink") or _spread(t)
    if t.name == "input":
        kind = _attr(t, "type")
        return not (kind and kind[0] != "expr"
                    and kind[1].strip().lower() == "hidden")
    if t.name in ("audio", "video"):
        return _has_any(t, "controls")
    if t.name in _FOCUSABLE_TAGS:
        return True
    tabindex = _attr_any(t, "tab[Ii]ndex")
    if tabindex is not None and tabindex[0] is not None \
            and not tabindex[0][1].strip().strip("'\"").startswith("-"):
        return True
    editable = _attr(t, "contentEditable|contenteditable")
    if editable is not None and editable[1].strip().lower() != "false" \
            or editable is None and _has(t, "contentEditable|contenteditable"):
        return True
    return _component(t.name) is not None and _has_any(t, "href|routerLink")


# A component inside a click-handling wrapper (N26) is followed to its
# source when the linter can find it: declared at the top level of the same
# file, or imported by a relative path or a tsconfig/jsconfig path alias
# (`@/components/…`), through re-exports. A component from a package, or
# one it cannot find (auto-imported, passed in props), renders nothing the
# linter can see.

_MODULE_EXTS = (".tsx", ".ts", ".jsx", ".js", ".mjs", ".vue", ".svelte")
#: A top-level declaration: where the previous one's source ends.
_TOP_LEVEL = re.compile(r'^(?:export\s|(?:async\s+)?function\b|const\s|let\s'
                        r'|var\s|class\s)', re.M)
#: How many components deep a wrapper's content is followed.
_COMPONENT_DEPTH = 4
#: Largest file read to follow a component, and largest tsconfig.json.
_MODULE_LIMIT = 2_000_000
_CONFIG_LIMIT = 1_000_000
_FROM = re.compile(r'from\s*(["\'])([^"\'\n]{1,500})\1')
_CLAUSE = re.compile(r'[\w$*{}\s,]+')


@functools.lru_cache(maxsize=64)
def _imports(text: str) -> dict:
    """{local name: (module specifier, imported name)}; the imported name
    is "default" for a default import and "*" for a namespace. Each
    `import` is matched to the first `from "…"` within 2,000 characters,
    so no pattern runs over the file more than once."""
    out = {}
    for m in re.finditer(r'\bimport\b', text):
        limit, k, f = m.end() + 2000, m.end(), None
        while f is None:
            k = text.find("from", k, limit)
            if k == -1:
                break
            if not (text[k - 1].isalnum() or text[k - 1] in "_$"):
                f = _FROM.match(text, k)
            k += 4
        if f is None:
            continue
        k = f.start()
        clause = text[m.end():k]
        if not _CLAUSE.fullmatch(clause) or re.match(r'\s*type\s', clause):
            continue
        spec = f.group(2)
        named = re.search(r'\{([^}]*)\}', clause)
        if named:
            for part in named.group(1).split(","):
                part = re.sub(r'^\s*type\s+', "", part).strip()
                bits = re.split(r'\s+as\s+', part)
                if re.fullmatch(r'[\w$]+', bits[-1] or "-"):
                    out[bits[-1]] = (spec, bits[0])
            clause = clause[:named.start()] + clause[named.end():]
        for part in clause.split(","):
            part = part.strip()
            ns = re.fullmatch(r'\*\s*as\s+([\w$]+)', part)
            if ns:
                out[ns.group(1)] = (spec, "*")
            elif re.fullmatch(r'[\w$]+', part):
                out[part] = (spec, "default")
    return out


_JSONC = re.compile(r'"(?:\\.|[^"\\\n])*"|//[^\n]*|/\*')


def _loose_json(text: str):
    """A tsconfig.json: JSON with comments and trailing commas. Comments
    are removed in one pass (an unclosed /* ends the file)."""
    out, i = [], 0
    while True:
        m = _JSONC.search(text, i)
        if m is None:
            out.append(text[i:])
            break
        out.append(text[i:m.start()])
        tok = m.group(0)
        if tok[0] == '"':
            out.append(tok)
            i = m.end()
        elif tok == "/*":
            j = text.find("*/", m.end())
            i = len(text) if j == -1 else j + 2
        else:
            i = m.end()
    try:
        return json.loads(re.sub(r',(\s*[}\]])', r'\1', "".join(out)))
    except (ValueError, RecursionError):
        return None


def _read_regular(path: Path, limit: int) -> str | None:
    """A regular file's text, or None for anything else (a FIFO, a device,
    a folder) or a file over `limit` bytes. Opened without blocking, so a
    FIFO in its place never stalls the run."""
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0)
                     | getattr(os, "O_BINARY", 0))
    except OSError:
        return None
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_size > limit:
            return None
        chunks, size = [], 0
        while size <= limit:
            chunk = os.read(fd, 1 << 16)
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
        if size > limit:
            return None
    except OSError:
        return None
    finally:
        os.close(fd)
    return b"".join(chunks).decode("utf-8", errors="replace")


def _stat_key(path: Path):
    """(path, modification time, size): a cache key that changes when the
    file does."""
    try:
        st = path.stat()
    except OSError:
        return None
    return str(path), st.st_mtime_ns, st.st_size


#: Files read to follow components, by _stat_key: tsconfig paths, and the
#: _Source of each module. Cleared when it grows past _CACHE_MAX.
_READ: dict = {}
_CACHE_MAX = 512


def _cached(path: Path, make, limit: int):
    key = _stat_key(path)
    if key is None:
        return None
    if key not in _READ:
        text = _read_regular(path, limit)
        if text is None:
            return None
        if len(_READ) >= _CACHE_MAX:
            _READ.clear()
        _READ[key] = make(text)
    return _READ[key]


def _local(p) -> bool:
    """A relative path: not absolute, not on a drive, not a UNC share
    (which Windows would open over the network)."""
    p = str(p)
    return not (PurePosixPath(p).is_absolute() or PureWindowsPath(p).drive
                or PureWindowsPath(p).is_absolute()
                or p.startswith(("/", "\\", "~")))


def _config_paths(text: str):
    data = _loose_json(text)
    opts = data.get("compilerOptions") if isinstance(data, dict) else None
    if not isinstance(opts, dict) or not isinstance(opts.get("paths"), dict):
        return None
    base = opts.get("baseUrl") or "."
    if not isinstance(base, str) or not _local(base):
        return None
    paths = {k: [x for x in v[:10] if isinstance(x, str) and _local(x)]
             for k, v in opts["paths"].items()
             if isinstance(k, str) and isinstance(v, list)}
    return base, paths


def _path_aliases(folder: Path) -> list:
    """[(base folder, paths)] from the tsconfig*.json and jsconfig.json files
    of the nearest folder at or above `folder` that has one (create-vue
    keeps its paths in tsconfig.app.json), looking no higher than the
    project's root (a folder with package.json or .git)."""
    for d in [folder, *folder.parents][:16]:
        try:
            found = sorted(d.glob("tsconfig*.json")) + sorted(
                d.glob("jsconfig.json"))
        except OSError:
            found = []
        if found:
            out = []
            for f in found:
                got = _cached(f, _config_paths, _CONFIG_LIMIT)
                if got:
                    out.append((d / got[0], got[1]))
            return out
        if (d / "package.json").exists() or (d / ".git").exists():
            break
    return []


def _module_file(spec: str, importer: Path) -> Path | None:
    """The source file an import names, when it is one of the project's.
    A path alias resolves as TypeScript resolves it: the matching pattern
    with the longest prefix, then its targets in order."""
    if spec.startswith(("./", "../")):
        bases = [importer.parent / spec]
    else:
        bases = []
        for base, paths in _path_aliases(importer.parent.absolute()):
            best, rest = None, ""
            for key in paths:
                if key == spec:
                    best, rest = key, ""
                    break
                if key.endswith("*") and spec.startswith(key[:-1]) and (
                        best is None or len(key) > len(best)):
                    best, rest = key, spec[len(key) - 1:]
            if best is not None:
                bases += [base / x.replace("*", rest) for x in paths[best]]
    for base in bases:
        try:
            cands = [base, *(base.with_name(base.name + e)
                             for e in _MODULE_EXTS),
                     *(base / ("index" + e) for e in _MODULE_EXTS)]
            if base.suffix in (".js", ".jsx", ".mjs"):
                # TypeScript's ESM imports name the compiled file: ./item.js
                cands += [base.with_suffix(".ts"), base.with_suffix(".tsx")]
        except ValueError:                  # no file name: "/", ".."
            continue
        for cand in cands:
            try:
                if cand.suffix.lower() in CODE_EXTS and cand.is_file():
                    return cand
            except (OSError, ValueError):
                continue
    return None


_JSX_COMMENT_OPEN = re.compile(r'\{[ \t\r\n]*/\*')
_JSX_COMMENT_CLOSE = re.compile(r'\*/[ \t\r\n]*\}')


def _comment_spans(text: str) -> list:
    """(start, end) of each comment whose markup renders nothing: <!-- … -->
    (HTML, Vue, Svelte and Angular templates) and JSX's {/* … */}. Only
    those: `//` and `/* */` are text in a template and in JSX children, and
    a /* inside a string (accept="image/*", path="/*") opens nothing."""
    opens = sorted([(m.start(), 0) for m in re.finditer(r'<!--', text)]
                   + [(m.start(), 1) for m in _JSX_COMMENT_OPEN.finditer(text)])
    out, last = [], -1
    for pos, jsx in opens:
        if pos < last:
            continue
        if not jsx:
            j = text.find("-->", pos + 4)
            end = len(text) if j == -1 else j + 3
        else:
            j = text.find("*/", text.find("/*", pos) + 2)
            m = _JSX_COMMENT_CLOSE.match(text, j) if j != -1 else None
            end = len(text) if j == -1 else (m.end() if m else j + 2)
        out.append((pos, end))
        last = end
    return out


class _Source:
    """A file's text and tags, as followed for N26: tag starts (to find
    the tags in a span) and comments (whose tags render nothing)."""

    def __init__(self, text: str, tags: list, path: str):
        self.text, self.tags, self.path = text, tags, path
        self.starts = [t.start for t in tags]
        self.comments = _comment_spans(text)
        self.comment_starts = [a for a, _b in self.comments]
        #: {component name or "export NAME": does it render focusable?}
        self.memo: dict = {}

    def commented(self, pos: int) -> bool:
        i = bisect.bisect_right(self.comment_starts, pos) - 1
        return i >= 0 and pos < self.comments[i][1]

    def tags_in(self, a: int, b: int) -> list:
        i = bisect.bisect_left(self.starts, a)
        j = bisect.bisect_left(self.starts, b)
        return [x for x in self.tags[i:j] if not self.commented(x.start)]

    def end_of(self, t: _Tag) -> int:
        return _content_end(self.text, self.tags, t)


def _module(path: Path):
    """The _Source of a module, read once while it is unchanged."""
    return _cached(path, lambda text: _Source(text, list(_iter_tags(text)),
                                              str(path)), _MODULE_LIMIT)


@functools.lru_cache(maxsize=1024)
def _definition(text: str, name: str):
    """(start, end) of a component's source in the file: a top-level
    `function Name`, `class Name` or `const Name =` (with export, default,
    async) to the next top-level declaration. A local inside another
    function (`const Icon = icons[i]`) is not a component's source."""
    n = re.escape(name)
    m = re.search(r'^(?:export\s+(?:default\s+)?)?(?:async\s+)?'
                  r'(?:function\s*\*?\s*' + n + r'\b|class\s+' + n + r'\b'
                  r'|(?:const|let|var)\s+' + n + r'\b\s*(?::[^=\n]*)?=)',
                  text, re.M)
    if m is None:
        return None
    nxt = _TOP_LEVEL.search(text, m.end())
    return m.start(), nxt.start() if nxt else len(text)


@functools.lru_cache(maxsize=256)
def _default_export(text: str):
    """(start, end) of a module's default export, or None when the module
    does not pin it to a declaration: `export default function Card …`,
    `export default Card` (or a wrapper: `memo(Card)`, `connect(map)(Card)`,
    the last capitalised name in the expression), `export { Card as
    default }`, `module.exports = Card`."""
    m = re.search(r'^export\s+default\s+', text, re.M)
    if m is not None:
        rest = text[m.end():m.end() + 300]
        if re.match(r'(?:async\s+)?(?:function\b|class\b)', rest):
            nxt = _TOP_LEVEL.search(text, m.end())
            return m.start(), nxt.start() if nxt else len(text)
        line = re.sub(r'/\*.*?\*/|//.*', "", rest.split("\n", 1)[0])
        names = re.findall(r'\b([A-Z][\w$]*)\b', line)
        return _definition(text, names[-1]) if names else None
    m = re.search(r'\bexport\s*\{[^}]*?\b([\w$]+)\s+as\s+default\b', text) \
        or re.search(r'^module\.exports\s*=\s*([\w$]+)', text, re.M)
    return _definition(text, m.group(1)) if m else None


_REEXPORT = re.compile(r'^export\s*(?:\{([^}]*)\}|(\*))\s*from\s*'
                       r'["\']([^"\'\n]+)["\']', re.M)
_LOCAL_EXPORT = re.compile(r'^export\s*\{([^}]*)\}(?!\s*from)', re.M)


@functools.lru_cache(maxsize=256)
def _reexports(text: str, name: str) -> tuple:
    """((module specifier, its name there)) for a re-export of `name`:
    `export { Card } from "./card"`, `export { default as Card } from …`,
    `export * from …`."""
    out = []
    for m in _REEXPORT.finditer(text):
        if m.group(2):
            out.append((m.group(3), name))
            continue
        for part in m.group(1).split(","):
            bits = re.split(r'\s+as\s+', part.strip())
            if bits[-1] == name:
                out.append((m.group(3), bits[0]))
    return tuple(out[:20])


def _local_alias(text: str, name: str) -> str | None:
    """The declaration `export { Inner as Card }` names for Card."""
    for m in _LOCAL_EXPORT.finditer(text):
        for part in m.group(1).split(","):
            bits = re.split(r'\s+as\s+', part.strip())
            if len(bits) == 2 and bits[1] == name:
                return bits[0]
    return None


def _component(name: str) -> str | None:
    """The name a tag's component is declared under: `FilterItem` for
    `<FilterItem>`, `<filter-item>` (Vue) or `<FilterItem.Row>`."""
    head = name.split(".")[0]
    if head[:1].isupper():
        return head
    if "-" in head and head.islower():
        return "".join(p.capitalize() for p in head.split("-"))
    return None


def _renders_focusable(src: _Source, span, seen: set, depth: int) -> bool:
    """Does this span of source render an element that takes keyboard
    focus, itself or through the components it uses?"""
    inner = src.tags_in(*span)
    if any(_focusable(x) for x in inner):
        return True
    if depth >= _COMPONENT_DEPTH:
        return False
    for x in inner:
        name = _component(x.name)
        if name is None or (src.path, x.name) in seen:
            continue
        seen.add((src.path, x.name))
        if x.name in src.memo:
            if src.memo[x.name]:
                return True
            continue
        found = _definition(src.text, name)
        if found is not None:
            got = _renders_focusable(src, found, seen, depth + 1)
        else:
            imported = _imports(src.text).get(name)
            got = False
            if imported is not None:
                spec, what = imported
                if what == "*":
                    what = x.name.split(".")[1] if "." in x.name else None
                if what is not None:
                    got = _export_renders_focusable(src.path, spec, what,
                                                    seen, depth + 1)
        # A result is kept for the next wrapper when it is certain: one
        # found, or none found with the whole depth to look in.
        if got or depth == 0:
            src.memo[x.name] = got
        if got:
            return True
    return False


def _export_renders_focusable(importer: str, spec: str, name: str,
                              seen: set, depth: int) -> bool:
    """Does the export `name` ("default" for the default export) of the
    module `spec`, imported by `importer`, render a focusable element? A
    .vue or .svelte module is its default export. An export the linter
    cannot pin to a declaration, or one whose declaration holds no markup
    (`const Card = styled(Base)`), is read as the whole module: never an
    error on a guess."""
    if depth > _COMPONENT_DEPTH:
        return False
    module = _module_file(spec, Path(importer))
    msrc = _module(module) if module is not None else None
    key = "export " + name
    if msrc is None or (msrc.path, key) in seen:
        return False
    if key in msrc.memo:
        return msrc.memo[key]
    seen.add((msrc.path, key))
    whole = (0, len(msrc.text))
    if name == "default":
        span = whole if module.suffix.lower() in (".vue", ".svelte") \
            else _default_export(msrc.text)
    else:
        span = _definition(msrc.text, name)
        if span is None and _local_alias(msrc.text, name):
            span = _definition(msrc.text, _local_alias(msrc.text, name))
    if span is None and name != "default":
        sources = _reexports(msrc.text, name)
        if sources:
            got = any(_export_renders_focusable(msrc.path, s, n, seen,
                                                depth + 1)
                      for s, n in sources)
            if got or depth <= 1:
                msrc.memo[key] = got
            return got
    if span is None or not msrc.tags_in(*span):
        span = whole
    got = _renders_focusable(msrc, span, seen, depth)
    if got or depth <= 1:
        msrc.memo[key] = got
    return got


#: Content a component receives from its caller, which the linter cannot
#: see: JSX children, Svelte 5 {@render …}, Lit's dynamic <${tag}>, and
#: markup injected as HTML.
_PASSED_CONTENT = re.compile(
    r'\{\s*(?:[\w$]+\.)*children\b|\{@render\b|\{@html\b|<\$\{'
    r'|dangerouslySetInnerHTML|\bv-html\s*=|\[innerHTML\]|\.innerHTML\s*=')
#: Tags that stand for such content: Vue, Svelte 4 and web components'
#: <slot>, Angular's <ng-content>, Vue's <component :is> and Svelte's
#: <svelte:component>/<svelte:element>.
_PASSED_TAGS = {"slot", "ng-content", "component", "svelte:component",
                "svelte:element"}


def _passes_content(src: _Source, t: _Tag) -> bool:
    """Does element t's content come, in part, from its caller (a slot,
    children), so the linter cannot see whether it holds the controls?"""
    if _has(t, r'dangerouslySetInnerHTML|v-html|\[innerHTML\]|\.innerHTML'
               r'|innerHTML'):
        return True                     # its own content, injected as HTML
    end = src.end_of(t)
    if any(x.name in _PASSED_TAGS for x in src.tags_in(t.end, end)):
        return True
    for m in _PASSED_CONTENT.finditer(src.text, t.end, end):
        if not src.commented(m.start()):
            return True
    return False


def _wraps_focusable(src: _Source, t: _Tag) -> bool:
    """Does element t contain an element that takes keyboard focus, written
    there or rendered by a component the linter can follow to its source? A
    click handler on such a wrapper may only handle clicks bubbling up from
    it (a menu that closes when an item is chosen, a card whose link is the
    keyboard path): N26."""
    return _renders_focusable(src, (t.end, src.end_of(t)), set(), 0)


def _only_stops_event(kind: str, code: str) -> bool:
    """Is this click handler nothing but stopPropagation()/preventDefault()?
    Dialog content uses one so a click inside it does not reach the backdrop
    that closes the dialog. The element is not a control."""
    if kind == "str":                  # HTML inline handler: statements
        return _EVENT_ONLY.fullmatch(code) is not None
    if _STOP_HELPER.fullmatch(code):
        return True
    m = _ARROW_FN.fullmatch(code) or _PLAIN_FN.fullmatch(code)
    if m is None:
        return False
    body = m.group("body").strip()
    if body.startswith("{") and body.endswith("}"):
        body = body[1:-1]
    return _EVENT_ONLY.fullmatch(body) is not None


# ---------------------------------------------------------------------------
# Context rules and tag rules
# ---------------------------------------------------------------------------

_NAV_OPEN = re.compile(r'<nav\b', re.I)
_NAV_CLOSE = re.compile(r'</nav\s*>', re.I)
_MENU_ROLE = re.compile(r'role\s*=\s*["\'](menu|menubar|menuitem)["\']')
_STYLE_OBJ = re.compile(r'\b(style|sx|css)\s*=\s*\{\{')
_STYLE_ATTR = re.compile(r'\bstyle\s*=\s*"[^"]*"|\bstyle\s*=\s*\'[^\']*\'')
_ORDER_DECL = re.compile(r'\border\s*:\s*-?\d'
                         r'|flex-?[Dd]irection\s*:\s*["\']?(row|column)-reverse')
_ORDER_CLASS = re.compile(
    r'[\s"\'`](flex-(row|col)-reverse|order-(\d+|first|last))\b')
_ICONISH = re.compile(r'<\s*(svg|i|Icon|[A-Z]\w*Icon)\b')
_JSX_COMMENT = re.compile(r'\{\s*/\*.*?\*/\s*\}|<!--.*?-->', re.S)
#: 2.2.1's 20-hour exception, in seconds; the eval rule uses the same bound.
_TWENTY_HOURS = 72000
_REFRESH_DELAY = re.compile(r'\s*(\d+)')


def _spans(text: str, opener: re.Pattern, closer: re.Pattern) -> list:
    """(start, end) spans from each opener to the next closer."""
    out = []
    for m in opener.finditer(text):
        c = closer.search(text, m.end())
        out.append((m.start(), c.end() if c else len(text)))
    return out


def _inside(pos: int, spans: list) -> bool:
    return any(a <= pos < b for a, b in spans)


def _style_spans(text: str) -> list:
    spans = []
    for m in _STYLE_OBJ.finditer(text):
        end = text.find("}}", m.end())
        spans.append((m.start(), end if end != -1 else len(text)))
    spans += [(m.start(), m.end()) for m in _STYLE_ATTR.finditer(text)]
    return spans


def _context_findings(text: str, path: str) -> list[Finding]:
    """Rules whose verdict depends on where in the file the match sits."""
    out: list[Finding] = []

    # bl-menu-role: ERROR inside <nav> (site navigation — the pled pattern),
    # WARN elsewhere (a genuine APG menu button is legitimate; a human decides).
    navs = _spans(text, _NAV_OPEN, _NAV_CLOSE)
    for m in _MENU_ROLE.finditer(text):
        if _inside(m.start(), navs):
            out.append(Finding(
                "bl-menu-role", ERROR, path, _line_of(text, m.start()),
                "ARIA menu role inside site navigation — screen readers get "
                "a broken application menu; use the disclosure pattern "
                "(button + aria-expanded + list of links).", "NAV-1",
                _snippet(text, m.start())))
        else:
            out.append(Finding(
                "bl-menu-role", WARN, path, _line_of(text, m.start()),
                "ARIA menu role outside <nav>: fine for a real application "
                "menu that implements the APG keyboard contract; never for "
                "site navigation.", "NAV-1, WGT-1", _snippet(text, m.start())))

    # bl-css-order in code: an `order:` declaration only counts inside a
    # style object/attribute (not a sort parameter); utility classes count
    # anywhere.
    styles = _style_spans(text)
    for m in _ORDER_DECL.finditer(text):
        if _inside(m.start(), styles):
            out.append(Finding(
                "bl-css-order", WARN, path, _line_of(text, m.start()),
                "Inline style re-orders content — if this re-sequences "
                "meaning, reading and tab order break: author the DOM in "
                "reading order.", "STR-5", _snippet(text, m.start())))
    for m in _ORDER_CLASS.finditer(text):
        out.append(Finding(
            "bl-css-order", WARN, path, _line_of(text, m.start()),
            "Ordering utility class — if this re-sequences content, reading "
            "and tab order break: author the DOM in reading order.",
            "STR-5", _snippet(text, m.start())))
    return out


def _button_content_named(content: str) -> bool:
    """Is there anything in a button's content that can name it? Visible
    text, sr-only text, an aria-label on a child, an img with alt, or a JSX
    expression (dynamic text the linter cannot see through)."""
    body = _JSX_COMMENT.sub("", content)
    if re.search(r'aria-label(ledby)?\s*=', body):
        return True
    if re.search(r'<img\b[^>]*\balt\s*=\s*["\'][^"\']+', body):
        return True
    if re.search(r'\{[^{}]*\}', body):
        return True
    return bool(re.sub(r'<[^>]*>', '', body).strip())


def _tag_findings(text: str, path: str, tags: list) -> list[Finding]:
    out: list[Finding] = []
    made: list = []
    vue = path.endswith(".vue")

    def src() -> _Source:
        if not made:
            made.append(_Source(text, tags, path))
        return made[0]

    for t in tags:
        name = t.name
        pos = t.start

        def add(rule_id, sev, msg, ref):
            out.append(Finding(rule_id, sev, path, _line_of(text, pos),
                               msg, ref, _snippet(text, pos)))

        clicks = _handlers(t, _CLICK, vue) if name in ("div", "span", "a") \
            else []
        acting = [h for h in clicks if not _handler_only_stops(*h)]
        if name in ("div", "span") and clicks:
            hidden = _aria_hidden(t)
            if not acting:
                add("bl-div-click", WARN,
                    f"<{name}> whose click handler only stops the event "
                    "(stopPropagation/preventDefault) — the dialog-content "
                    "pattern, not a control. Confirm, then suppress.",
                    "AGT-1, WGT-1")
            elif _has_any(t, "role"):
                add("bl-div-click", WARN,
                    f"<{name}> with a click handler and a role — a custom "
                    "control now owns the full keyboard contract (Enter/"
                    "Space, focusability, name); prefer <button>.",
                    "AGT-1, WGT-1")
            elif hidden is not False:
                add("bl-div-click", WARN,
                    f"{'aria-hidden' if hidden else 'possibly aria-hidden'} "
                    f"<{name}> with a click handler — fine for a modal "
                    "backdrop when Escape and a visible close button also "
                    "dismiss the dialog; never for a control.",
                    "AGT-1, WGT-1")
            elif all("self" in _modifiers(h[0]) for h in acting):
                add("bl-div-click", WARN,
                    f"<{name}> with a click handler for clicks on itself "
                    "only (the self modifier) — fine for a modal backdrop "
                    "when Escape and a visible close button also dismiss "
                    "the dialog; never for a control.", "AGT-1, WGT-1")
            elif _wraps_focusable(src(), t):
                add("bl-div-click", WARN,
                    f"<{name}> with a click handler around links, buttons or "
                    "fields — fine when it only handles clicks bubbling up "
                    "from them (closing a menu when an item is chosen); not "
                    "when it does something the keyboard cannot reach: put "
                    "that on one of them, or on a <button>.",
                    "AGT-1, WGT-1")
            elif _passes_content(src(), t):
                add("bl-div-click", WARN,
                    f"<{name}> with a click handler around content passed in "
                    "(a slot, children) that the linter cannot see — fine "
                    "when that content holds the links or buttons and the "
                    f"handler only catches their clicks; if the <{name}> is "
                    "itself the control, it needs a role, a name and "
                    "keyboard support: use <button> or <a href>.",
                    "AGT-1, WGT-1")
            elif _spread(t):
                add("bl-div-click", WARN,
                    f"<{name}> with a click handler and attributes from a "
                    "spread the linter cannot see — verify they give it a "
                    "role, a name, keyboard support and focus, or use "
                    "<button>.", "AGT-1, WGT-1")
            else:
                add("bl-div-click", ERROR,
                    f"<{name}> with a click handler: no role, no name, no "
                    "keyboard, no focus — use <button> or <a href>.",
                    "AGT-1, WGT-1")

        if name == "a":
            href = _attr(t, "href")
            has_href = _has_any(t, "href|routerLink")
            hash_href = (href is not None and href[0] != "expr"
                         and href[1].strip() == "#")
            if _has_any(t, "aria-expanded"):
                add("bl-aria-expanded-link", WARN,
                    "aria-expanded on a link — valid ARIA, but a control "
                    "that only shows and hides content is a button: for "
                    "site navigation use the disclosure pattern (<button "
                    "aria-expanded> + list of links).", "NAV-1")
            if acting and (not has_href or hash_href) and _spread(t):
                add("bl-anchor-button", WARN,
                    "Anchor with a click handler and no real href the linter "
                    "can see — a spread may supply one; if not, it is "
                    "unreachable or announced wrong: use <button>.", "AGT-1")
            elif acting and (not has_href or hash_href):
                add("bl-anchor-button", ERROR,
                    "Anchor used as a button (no real href) — it is "
                    "unreachable/announced wrong; use <button>.", "AGT-1")
            elif hash_href:
                add("bl-anchor-button", WARN,
                    'href="#" placeholder link — dead end for keyboard and '
                    "AT users; give it a destination or make it a button.",
                    "AGT-1")

        if name == "button" and not _has_any(t, "type"):
            # Exact lowercase only: a <Button> component sets its own type.
            add("bl-button-type", WARN,
                "<button> without an explicit type defaults to submit "
                'inside forms — add type="button" unless it submits.',
                "FRM-6")
        if (name in ("button", "Button")
                and not _has(t, "aria-label(?:ledby)?")):
            content = None
            if t.self_closing:
                # <button /> is empty, unless its children arrive in props
                # the linter cannot see ({...props}, children=); so is a
                # self-closing <Button /> component.
                if name == "button" and not _SPREAD.search(t.attrs) \
                        and not _has(t, "children"):
                    content = ""
            else:
                close = re.search(r'</\s*' + re.escape(name) + r'\s*>',
                                  text[t.end:t.end + 2000])
                if close is not None:
                    content = text[t.end:t.end + close.start()]
            if content is not None \
                    and (_ICONISH.search(content) or not content.strip()) \
                    and not _button_content_named(content):
                add("bl-icon-button-name", WARN,
                    "Button whose only content is an icon (or nothing) "
                    "and no aria-label — empty accessible name; add "
                    "visible or sr-only text, or aria-label the action.",
                    "AGT-1, IMG-3")

        if name in ("button", "a") and any(
                v is not None and not _handler_only_stops(n, v)
                for n, v in _handlers(t, _DOWN, vue)):
            # A down-event handler that only prevents the default (keeping
            # focus where it is) activates nothing.
            add("bl-downevent-activation", WARN,
                "Activation on the down-event — users can't cancel a slip; "
                "activate on click.", "FRM-6")

        if name == "input" and _has(t, "placeholder"):
            if not (_has(t, "aria-label(?:ledby)?") or _has(t, "id")):
                add("bl-placeholder-label", WARN,
                    "Input with placeholder and no id/aria-label — verify a "
                    "real associated <label> exists; placeholder is never "
                    "the label.", "FRM-1")

        if name in ("div", "span"):
            tabindex = _attr(t, "tab[Ii]ndex")
            # A focusable region with a role and a name (a scrolling table
            # wrapper: role="region" aria-labelledby=…) is what the rule
            # asks for, not what it warns about (1.0.1).
            if (tabindex is not None and re.match(r'\s*0\b', tabindex[1])
                    and not (_has(t, "role") and _has(t, "aria-label(?:ledby)?"))):
                add("bl-tabindex-noninteractive", WARN,
                    f"tabindex=0 on <{name}> — focusable but roleless and "
                    "nameless; use a native control or complete the custom-"
                    "control checklist.", "AGT-1, WGT-1")

        # Mirrors bb-media-autoplay: an error only where the gate fails.
        # Native controls meet 1.4.2 (ACT 4c31df) when users can see and
        # reach them, so sound with controls is a warning: the pack still
        # bans it, and the linter cannot see whether CSS hides them. What
        # the linter cannot read (a bound expression, a spread) is never an
        # error. HTML attribute names are case-insensitive.
        svelte = path.endswith(".svelte")
        html_file = path.lower().endswith((".html", ".htm"))
        flags = re.I if html_file else 0
        media = name.lower() if html_file else name
        autoplay = (_bool_state(t, "autoplay|autoPlay", svelte, flags)
                    if media in ("audio", "video") else None)
        if autoplay in (ON, UNKNOWN):
            muted = _bool_state(t, "muted", svelte, flags)
            controls = _bool_state(t, "controls", svelte, flags)
            ref = "IMG-5" if media == "audio" else "IMG-4"
            silent = (None, OFF)
            if muted == ON:
                if media == "video" and controls in silent:
                    # As bb-media-autoplay words it (R5G-11).
                    add("bl-autoplay-media", WARN,
                        "Muted autoplay video without controls: no sound, so "
                        "1.4.2 is met, but if it moves for more than five "
                        "seconds, 2.2.2 needs a way to pause, stop or hide it "
                        "(not tested here); honor reduced motion.", "IMG-4")
            elif (autoplay == ON and muted in silent and controls in silent
                    and not _media_source(text, t)):
                add("bl-autoplay-media", WARN,
                    f"<{media}> autoplays and has no source in markup — if "
                    "script adds one without a user action, sound starts at "
                    "once with no controls (1.4.2); the gate lists it for "
                    "review.", ref)
            elif (autoplay == ON and muted in silent and controls in silent
                    and html_file and _inside_inert(text, t.start)):
                add("bl-autoplay-media", WARN,
                    f"<{media}> autoplays sound with no controls, inside a "
                    "<template> or <noscript>: it plays only if a script "
                    "puts it in the page, and then fails 1.4.2.", ref)
            elif autoplay == ON and muted in silent and controls in silent:
                add("bl-autoplay-media", ERROR,
                    f"<{media}> autoplays sound with no controls — fails "
                    "1.4.2 unless it stops within 3 seconds or another "
                    "visible control pauses or mutes it.", ref)
            elif autoplay == ON and muted in silent and controls == ON:
                add("bl-autoplay-media", WARN,
                    f"<{media}> autoplays sound, with native controls — "
                    "they meet 1.4.2 when users can see and reach them, "
                    "but Bellbriar's WCAG pack bars autoplaying sound: "
                    "confirm, or remove autoplay.", ref)
            else:
                unread = [what for what, state in (
                    ("autoplays", autoplay), ("is muted", muted),
                    ("has controls", controls)) if state == UNKNOWN]
                add("bl-autoplay-media", WARN,
                    f"<{media}> may autoplay sound: the linter cannot read "
                    f"whether it {' or '.join(unread)} (a bound expression "
                    "or a spread). If it can autoplay unmuted with no "
                    "controls, the gate fails it (1.4.2); Bellbriar's WCAG "
                    "pack bars autoplaying sound either way.", ref)

        if name.lower() == "meta":
            # Same bounds as the eval rule: an instant redirect (0) and a
            # delay over 20 hours (2.2.1's exception) are fine.
            equiv = _attr(t, "http-?equiv", re.I)
            if equiv is not None and equiv[0] != "expr" \
                    and equiv[1].strip().lower() == "refresh":
                content = _attr(t, "content", re.I)
                if content is not None and content[0] == "expr":
                    add("bl-meta-refresh", WARN,
                        "meta refresh with a computed delay — any delay "
                        "from 1 second to 20 hours is a timed refresh/"
                        "redirect without user control (2.2.1); 0, an "
                        "instant redirect, is fine.", "STR-9")
                elif content is not None:
                    delay = _REFRESH_DELAY.match(content[1])
                    if delay and 0 < int(delay.group(1)) <= _TWENTY_HOURS:
                        add("bl-meta-refresh", ERROR,
                            f"Timed refresh/redirect after {delay.group(1)}s "
                            "without user control (2.2.1) — redirect "
                            "instantly (0) or on the server.", "STR-9")
    return out


_COND_ELEMENT = re.compile(r'(?:&&|\?)[\s(]*<(?=[A-Za-z])')


def _live_region_findings(text: str, path: str, tags: list) -> list[Finding]:
    """A live region rendered conditionally ({cond && <p role=…>}) mounts
    with its text already inside. role="status" is then announced by almost
    nothing: ERROR. role="alert" is announced on insertion by the major
    screen readers (React Hook Form documents the pattern), though less
    reliably than a region that is already mounted: WARN."""
    at = {t.start: t for t in tags}
    out: list[Finding] = []
    for m in _COND_ELEMENT.finditer(text):
        t = at.get(m.end() - 1)
        role = _attr(t, "role") if t is not None else None
        if role is None or role[0] == "expr":
            continue
        kind = role[1].strip().lower()
        if kind == "status":
            out.append(Finding(
                "bl-conditional-live-region", ERROR, path,
                _line_of(text, t.start),
                "Live region is conditionally rendered — it mounts with the "
                "text already inside and announces nothing. Mount one "
                "announcer at the app root and change only its text.",
                "SPA-2, WGT-2", _snippet(text, t.start)))
        elif kind == "alert":
            out.append(Finding(
                "bl-conditional-live-region", WARN, path,
                _line_of(text, t.start),
                "role=\"alert\" is conditionally rendered — screen readers "
                "generally announce an alert inserted with its text, less "
                "reliably than a mounted region; for app-wide messages, "
                "mount one announcer at the app root.",
                "SPA-2, WGT-2", _snippet(text, t.start)))
    return out


# ---------------------------------------------------------------------------
# class="…outline-none…" rule (Tailwind and friends)
# ---------------------------------------------------------------------------

#: Where a start tag gives an element classes (P3-10): a plain `class` or
#: `className`, its value a string or (JSX, Svelte) an expression; a bound
#: one, its value an expression (Vue `:class` and `v-bind:class`, Alpine
#: `x-bind:class`, Angular `[class]` and `[ngClass]`); and one class each,
#: on a condition (Svelte `class:name={…}`, Angular `[class.name]`).
_CLASS_PLAIN = re.compile(r'(?:^|(?<=[\s{}"\']))(?:class|className)\s*=\s*')
_CLASS_BOUND = re.compile(r'(?:^|(?<=[\s{}"\']))(?:(?:v-bind:|x-bind:|:)'
                          r'(?:class|className)|\[(?:class|className|ngClass)\])'
                          r'\s*=\s*')
_CLASS_ONE = re.compile(r'(?:^|(?<=[\s{}"\']))(?:class:([^\s=/>]+)'
                        r'|\[class\.([^\]\s]+)\])(?=[\s=/>]|$)')
#: Calls that build a class string from their arguments: shadcn/ui's cn,
#: clsx, classnames, emotion's cx, tailwind-merge.
_CLASS_BUILDERS = ("cn", "clsx", "classnames", "classNames", "cx", "twMerge",
                   "twJoin")
#: An identifier in a value position (an argument, an array element, an
#: interpolation, a branch of ?:, either side of + or after && and ||, a
#: spread, the whole expression) supplies classes the linter cannot read;
#: one before &&, ? or a comparison is only a condition. A TypeScript cast
#: (`as string`, `satisfies T`), a non-null `!`, an optional call (`f?.()`)
#: and an Angular pipe (`ring$ | async`) leave it a value. Object entries
#: are dropped first (their values are conditions); a computed key,
#: `[ring]: on`, stays, because its key is a class.
_CLASS_SOURCE = re.compile(
    r'(?:(?:^|[(\[,+?:]|&&|\|\||\$\{)\s*(?:\.\.\.)?|\{\s*\.\.\.)\s*'
    r'(?!(?:true|false|null|undefined)\b)[A-Za-z_$][\w$]*'
    r'(?:\s*\??\.\s*(?:[\w$]+|\([^()]*\)|\[[^\]]*\])|\s*\[[^\]]*\]'
    r'|\s*\([^()]*\)|!(?!=))*'
    r'\s*(?=[,)\]}:+|]|\?\?|(?:as|satisfies)\b|$)')
_OBJECT_ENTRY = re.compile(r'(?P<lead>[{,]\s*)(?P<key>""|\[[^\]]*\]'
                           r'|[A-Za-z_$][\w$-]*)\s*:(?!:)[^,{}]*')
#: How deeply template literals may nest inside each other before the
#: linter stops reading the expression (and so never errs on it).
_TEMPLATE_DEPTH = 32


class _Unreadable(Exception):
    """An expression nested too deeply to read."""


def _quote_end(code: str, i: int) -> int:
    """End of the '…' or "…" string starting at i (at most its line)."""
    q, j = code[i], i + 1
    while j < len(code):
        if code[j] == "\\":
            j += 2
            continue
        if code[j] in (q, "\n"):
            return j + 1
        j += 1
    return len(code)


def _interpolation_end(code: str, j: int, depth: int = 0) -> int:
    """End of a ${…} whose code starts at j: just past its closing brace."""
    if depth > _TEMPLATE_DEPTH:
        raise _Unreadable
    braces = 1
    while j < len(code):
        c = code[j]
        if c in "\"'":
            j = _quote_end(code, j)
            continue
        if c == "`":
            j = _template_end(code, j, depth + 1)
            continue
        if c == "{":
            braces += 1
        elif c == "}":
            braces -= 1
            if braces == 0:
                return j + 1
        j += 1
    return len(code)


def _template_end(code: str, i: int, depth: int = 0) -> int:
    """End of the template literal starting at i, nested ones inside its
    ${…} included."""
    if depth > _TEMPLATE_DEPTH:
        raise _Unreadable
    j = i + 1
    while j < len(code):
        c = code[j]
        if c == "\\":
            j += 2
            continue
        if c == "`":
            return j + 1
        if code.startswith("${", j):
            j = _interpolation_end(code, j + 2, depth + 1)
            continue
        j += 1
    return len(code)


def _literals(code: str) -> list:
    """(start, end) of each string and template literal at the top level of
    a JavaScript expression, and of each comment (which starts with "/")."""
    out, i = [], 0
    while i < len(code):
        c = code[i]
        if c in "\"'":
            j = _quote_end(code, i)
        elif c == "`":
            j = _template_end(code, i)
        elif code.startswith("//", i):
            k = code.find("\n", i)
            j = len(code) if k == -1 else k
        elif code.startswith("/*", i):
            k = code.find("*/", i + 2)
            j = len(code) if k == -1 else k + 2
        else:
            i += 1
            continue
        out.append((i, j))
        i = j
    return out


def _template_parts(lit: str) -> tuple[list, list]:
    """A template literal's text pieces and the code of its ${…}."""
    texts, codes = [], []
    end = len(lit) - 1 if len(lit) > 1 and lit.endswith("`") else len(lit)
    j = start = 1
    while j < end:
        if lit[j] == "\\":
            j += 2
            continue
        if lit.startswith("${", j):
            texts.append(lit[start:j])
            k = _interpolation_end(lit, j + 2)
            codes.append(lit[j + 2:k - 1] if lit[k - 1:k] == "}"
                         else lit[j + 2:k])
            j = start = k
            continue
        j += 1
    texts.append(lit[start:end])
    return texts, codes


#: A class token: HTML splits a class list at ASCII white space alone, so
#: `focus:ring-2\u3000x` is one class (R6Y-11).
_TOKENS = re.compile(r"[^\t\n\f\r ]+")


def _expr_classes(code: str, depth: int = 0) -> tuple[list, bool]:
    """The class names a class expression can give, each with whether it
    applies only on a condition (after &&, ||, ?? or ?, as an object key),
    and whether part of the expression supplies classes the linter cannot
    read (an identifier, a call other than a class builder): `cn("x",
    className)` or `` `${base} x` ``. An expression nested too deeply to
    read is partial."""
    tokens: list = []
    partial = False
    reduced, last = [], 0
    try:
        found = _literals(code)
    except _Unreadable:
        return [], True
    for a, b in found:
        if code[a] == "/":
            # A comment: blanked, so an identifier before it stays a value.
            reduced += [code[last:a], " "]
            last = b
            continue
        before = code[:a].rstrip()
        after = code[b:].lstrip()
        cond = (before.endswith(("&&", "?", ":", "||"))
                or (after.startswith(":") and not after.startswith("::")))
        lit = code[a:b]
        if lit[0] == "`":
            try:
                texts, codes = _template_parts(lit)
            except _Unreadable:
                return tokens, True
            for part in texts:
                tokens += [(x, cond) for x in _TOKENS.findall(part)]
            for part in codes:
                if depth >= 4:
                    partial = True
                    continue
                inner, more = _expr_classes(part, depth + 1)
                tokens += [(x, cond or c) for x, c in inner]
                partial |= more
        else:
            tokens += [(x, cond) for x in _TOKENS.findall(lit[1:-1])]
        reduced += [code[last:a], '""']
        last = b
    reduced.append(code[last:])
    red = re.sub(r'\b(?:' + "|".join(_CLASS_BUILDERS) + r')\s*\(', "(",
                 "".join(reduced))
    # Vue's object syntax: an unquoted key is a class name, on a condition.
    tokens += [(m.group(1), True) for m in re.finditer(
        r'[{,]\s*([A-Za-z_$][\w$-]*)\s*:(?!:)', red)]
    values = _OBJECT_ENTRY.sub(
        lambda m: m["lead"] + (m["key"] if m["key"][0] == "[" else ""), red)
    return tokens, partial or _CLASS_SOURCE.search(values) is not None


def _string_classes(text: str, svelte: bool) -> tuple[list, bool]:
    """A quoted class value: its classes, and whether some come from an
    interpolation the linter cannot read — Svelte's `class="btn {x}"`, or
    `${…}` in a Lit template."""
    if "${" in text:
        try:
            texts, codes = _template_parts("`" + text + "`")
        except _Unreadable:
            return [], True
        tokens, partial = [], False
        for part in texts:
            tokens += [(x, False) for x in _TOKENS.findall(part)]
        for part in codes:
            more, unread = _expr_classes(part)
            tokens += more
            partial |= unread
        return tokens, partial
    if "{{" in text:
        # Angular, Handlebars, Jinja: class="btn {{ extra }}"
        parts = re.split(r'\{\{.*?\}\}', text, flags=re.S)
        return [(x, False) for part in parts
                for x in _TOKENS.findall(part)], \
            len(parts) > 1
    if svelte and "{" in text:
        tokens, partial = [], False
        for i, part in enumerate(re.split(r'\{([^{}]*)\}', text)):
            if i % 2 == 0:
                tokens += [(x, False) for x in _TOKENS.findall(part)]
            else:
                more, unread = _expr_classes(part)
                tokens += more
                partial |= unread
        return tokens, partial
    return [(x, False) for x in _TOKENS.findall(text)], False


def _tag_classes(t: _Tag, svelte: bool) -> tuple[list, bool] | None:
    """[(class name, conditional, offset in t.attrs of the attribute that
    gives it)], and whether some class comes from somewhere the linter
    cannot read (an expression, or a spread that can replace or add to
    them: `{...props}` after the class, `v-bind="$attrs"` anywhere); None
    when the tag sets no class."""
    tokens, partial, seen = [], False, False
    for m in _CLASS_PLAIN.finditer(t.names):
        if m.end() >= len(t.names):
            continue
        seen = True
        kind, text = _value_at(t, m.end())
        more, unread = (_expr_classes(text) if kind == "expr"
                        else _string_classes(text, svelte))
        tokens += [(x, c, m.start()) for x, c in more]
        partial |= unread
    for m in _CLASS_BOUND.finditer(t.names):
        if m.end() >= len(t.names):
            continue
        seen = True
        more, unread = _expr_classes(_value_at(t, m.end())[1])
        tokens += [(x, c, m.start()) for x, c in more]
        partial |= unread
    for m in _CLASS_ONE.finditer(t.names):
        seen = True
        tokens.append((m.group(1) or m.group(2), True, m.start()))
    if not seen:
        return None
    first = min(o for _x, _c, o in tokens) if tokens else 0
    return tokens, partial or _spread_after(t, first)


_CSS_OUTLINE = re.compile(r'outline\s*:\s*(none|0)\b')
_CSS_FV_REPLACEMENT = re.compile(
    r':focus-visible\b[^{}]*\{[^}]*(outline\s*:\s*[^n0]|box-shadow\s*:)', re.S)
_TOKEN_EDGE = re.compile(r'^[\'"`{}(),;:]+|[\'"`{}(),;:]+$')
#: Variants that apply only under the pointer: removing the outline there
#: leaves keyboard focus alone.
_POINTER_ONLY = {"hover", "active", "group-hover", "peer-hover",
                 "group-active", "peer-active"}
#: Utilities that change nothing a user sees.
_NON_VISUAL = ("z-", "relative", "absolute", "sticky", "fixed", "static",
               "transition", "duration-", "ease-", "delay-", "cursor-",
               "pointer-events-", "select-", "ring-offset", "ring-inset",
               "outline-offset", "underline-offset")


def _split_class(token: str) -> tuple[list, str]:
    """'md:focus-visible:!ring-2' → (['md', 'focus-visible'], 'ring-2').
    Colons inside [...] (arbitrary variants and values) do not split."""
    tok = _TOKEN_EDGE.sub("", token)
    parts, cur, depth = [], [], 0
    for ch in tok:
        if ch == "[":
            depth += 1
        elif ch == "]" and depth:
            depth -= 1
        if ch == ":" and not depth:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))
    utility = parts[-1].strip("!")
    return parts[:-1], utility[1:] if utility.startswith("-") else utility


def _focus_style(utility: str, prefix: str = "") -> str:
    """What a utility applied in a focus state does for the focus indicator:
    "indicator" (draws a ring, outline, shadow, border or underline),
    "removal" (takes one away), "neutral" (nothing visible), or "other"
    (another visible change: background, text color, size)."""
    u = utility[len(prefix):] if prefix and utility.startswith(prefix) \
        else utility
    if u.startswith(_NON_VISUAL):
        return "neutral"
    if u == "no-underline":
        return "removal"
    if u == "underline":
        return "indicator"
    family, _, rest = u.partition("-")
    if family in ("ring", "outline", "shadow", "border", "decoration"):
        if rest in ("0", "none", "hidden", "transparent") \
                or rest.endswith(("-0", "-none", "-transparent")):
            return "removal"
        if family == "border" and rest.startswith(
                ("collapse", "separate", "spacing")):
            return "neutral"
        if family == "decoration" and rest in ("clone", "slice"):
            return "neutral"
        return "indicator"
    return "other"


def _element_ends(text: str, tags: list) -> dict:
    """{start of each element: offset of the close tag that ends its
    content}, matching every element's start and close tags in one pass;
    an element never closed runs to the end of the file."""
    closes: dict = {}
    for m in re.finditer(r'</\s*([A-Za-z][\w.-]*)\s*>', text):
        closes.setdefault(m.group(1), []).append(m.start())
    opens: dict = {}
    for t in tags:
        if not t.self_closing:
            opens.setdefault(t.name, []).append(t.start)
    ends = {}
    for name, starts in opens.items():
        events = sorted([(p, 1) for p in starts]
                        + [(p, 0) for p in closes.get(name, ())])
        stack = []
        for p, is_open in events:
            if is_open:
                stack.append(p)
            elif stack:
                ends[stack.pop()] = p
        for p in stack:
            ends[p] = len(text)
    return ends


#: _element_ends of the files being linted, by id(tags); each entry holds
#: its tags and text, so the id is not reused while it is cached.
_ENDS: dict = {}


def _content_end(text: str, tags: list, t: _Tag) -> int:
    """Offset of the close tag that ends element t's content."""
    if t.self_closing:
        return t.end
    got = _ENDS.get(id(tags))
    if got is None or got[0] is not tags or got[1] is not text:
        if len(_ENDS) >= 8:
            _ENDS.clear()
        got = _ENDS[id(tags)] = (tags, text, _element_ends(text, tags))
    return got[2].get(t.start, len(text))


def _related_indicators(text: str, tags: list, lists: list):
    """Where a focus indicator is drawn for focus on another element.

    Returns a predicate over (class-list offset, parsed list): True when an
    ancestor draws one with focus-within: (or has-[:focus…]:), when the list
    carries `peer` and a later sibling draws one with peer-focus:, or when
    it carries `group` and a descendant draws one with group-focus:.
    """
    starts = [t.start for t in tags]

    def owner(pos):
        i = bisect.bisect_right(starts, pos) - 1
        for k in range(i, max(i - 50, -1), -1):
            if tags[k].end > pos:
                return tags[k]
        return None

    within, peers, groups = [], [], []
    for pos, parsed in lists:
        for variants, u in parsed:
            focus = [v for v in variants if "focus" in v]
            if not focus or _focus_style(u) != "indicator":
                continue
            if any("within" in v or v.startswith("has-") for v in focus):
                t = owner(pos)
                if t is not None:
                    within.append((t.end, _content_end(text, tags, t)))
            if any(v.startswith("peer") for v in focus):
                peers.append(pos)
            if any(v.startswith("group") for v in focus):
                groups.append(pos)

    def covered(pos, parsed) -> bool:
        if any(a <= pos < b for a, b in within):
            return True
        marks = {u.split("/")[0] for variants, u in parsed if not variants}
        if "peer" in marks and any(p > pos for p in peers):
            return True
        if "group" in marks and groups:
            t = owner(pos)
            if t is not None:
                end = _content_end(text, tags, t)
                return any(t.end <= p < end for p in groups)
        return False

    return covered


def _class_findings(text: str, path: str, tags: list) -> list[Finding]:
    svelte = path.endswith(".svelte")
    lists, extra = [], {}
    for t in tags:
        found = _tag_classes(t, svelte)
        if found is None:
            continue
        tokens, partial = found
        if not any("focus" in x or "outline-none" in x for x, _c, _o in tokens):
            continue
        # The finding points at the attribute that removes the outline.
        at = next((o for x, _c, o in tokens if "outline-none" in x),
                  tokens[0][2])
        pos = t.start + 1 + len(t.name) + at
        lists.append((pos, [_split_class(x) for x, _c, _o in tokens]))
        extra[pos] = ([c for _x, c, _o in tokens], partial)
    covered = _related_indicators(text, tags, lists)
    out: list[Finding] = []
    for pos, parsed in lists:
        conds, partial = extra[pos]
        prefix, removal = None, []
        for (variants, u), cond in zip(parsed, conds):
            if u.endswith("outline-none") and not (
                    variants and all(v in _POINTER_ONLY for v in variants)):
                if prefix is None:
                    prefix = u[:-len("outline-none")]   # Tailwind prefix
                removal.append(cond)
        if prefix is None:
            continue
        styles = {_focus_style(u, prefix) for variants, u in parsed
                  if any("focus" in v for v in variants)}
        # Each focus indicator, by whether it applies only on a condition.
        drawn = [c for (variants, u), c in zip(parsed, conds)
                 if any("focus" in v for v in variants)
                 and _focus_style(u, prefix) == "indicator"]
        if drawn and all(drawn) and not all(removal):
            sev, msg = WARN, (
                "outline-none always, its focus-state replacement only on a "
                "condition — verify a ring, outline, border or shadow shows "
                "whenever this element has focus (2.4.7).")
        elif "indicator" in styles:
            continue
        elif "other" in styles:
            sev, msg = WARN, (
                "outline-none replaced only by a focus-state color, "
                "background or size change — verify it is clearly visible "
                "(2.4.7) with 3:1 contrast against its surroundings "
                "(1.4.11), or add focus-visible:ring-2.")
        elif covered(pos, parsed):
            sev, msg = WARN, (
                "outline-none with no replacement in this class list; a "
                "related element draws the focus indicator (focus-within:, "
                "peer-focus: or group-focus:) — verify it shows whenever "
                "this element has focus (2.4.7).")
        elif partial or all(removal):
            # Never an error on a guess: a class the linter cannot read may
            # be the replacement, and a conditional removal may never apply.
            sev, msg = WARN, (
                "outline-none with no focus-state replacement among the "
                "classes the linter can read; "
                + ("others come from an expression it cannot read"
                   if partial else "it applies only on a condition")
                + " — verify a focus-visible: ring, outline, border or "
                "shadow replaces it (2.4.7).")
        else:
            sev, msg = ERROR, (
                "outline-none with no focus-state replacement in the same "
                "class list — the focus indicator is gone (2.4.7). Add a "
                "focus-visible: (or focus:) ring, outline, border or shadow, "
                "e.g. focus-visible:ring-2.")
        out.append(Finding("bl-outline-none-class", sev, path,
                           _line_of(text, pos), msg, "VIS-3, SPA-4",
                           _snippet(text, pos)))
    return out


def _css_findings(text: str, path: str) -> list[Finding]:
    out = []
    has_replacement = _CSS_FV_REPLACEMENT.search(text) is not None
    for m in _CSS_OUTLINE.finditer(text):
        sev = WARN if has_replacement else ERROR
        note = (" A :focus-visible replacement exists in this file — "
                "verify it covers the same elements."
                if has_replacement else "")
        out.append(Finding(
            "bl-outline-none-css", sev, path, _line_of(text, m.start()),
            "outline removed — never without an equal-or-better visible "
            "focus indicator (2.4.7)." + note,
            "VIS-3", _snippet(text, m.start())))
    return out


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

def lint_text(text: str, path: str) -> list[Finding]:
    ext = Path(path).suffix.lower()
    if ext not in ALL_EXTS:
        return []
    findings: list[Finding] = []
    for rule_id, sev, exts, pattern, msg, ref in _P:
        if ext not in exts:
            continue
        for m in pattern.finditer(text):
            findings.append(Finding(rule_id, sev, path,
                                    _line_of(text, m.start()), msg, ref,
                                    _snippet(text, m.start())))
    if ext in MARKUP_EXTS:
        tags = list(_iter_tags(text))
        findings += _tag_findings(text, path, tags)
        if ext in CODE_EXTS:
            findings += _live_region_findings(text, path, tags)
        findings += _class_findings(text, path, tags)
        findings += _context_findings(text, path)
    if ext in (CSS_EXTS | {".html", ".htm", ".vue", ".svelte"}):
        findings += _css_findings(text, path)

    # Suppression comments — each use belongs in the delivery notes.
    lines = text.splitlines()
    kept = []
    for f in findings:
        cur = lines[f.line - 1] if 0 < f.line <= len(lines) else ""
        prev = lines[f.line - 2] if f.line >= 2 else ""
        if DISABLE_LINE in cur:
            continue
        if DISABLE_NEXT in prev and (f.rule_id in prev
                                     or not re.search(r'bl-[\w-]+', prev)):
            continue
        kept.append(f)
    kept.sort(key=lambda f: (f.path, f.line, f.rule_id))
    return kept


#: Git's variables that point it at a repository. They are unset for the
#: ignore lookup, so git reads the folder being linted (inside a git hook
#: they name the hook's repository).
_GIT_REPO_ENV = {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE",
                 "GIT_COMMON_DIR", "GIT_OBJECT_DIRECTORY",
                 "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_NAMESPACE",
                 "GIT_PREFIX", "GIT_IMPLICIT_WORK_TREE",
                 "GIT_CONFIG_PARAMETERS", "GIT_CONFIG_COUNT"}
#: What the lookup sets for git: no transport at all (a partial clone's
#: "lazy fetch" of a missing .gitignore would run the command a
#: repository's config names for its remote), no lazy fetch (git 2.45 and
#: later), no lock files written, no prompts, and messages in English
#: (_git_ignored reads one).
_GIT_SAFE_ENV = {"GIT_ALLOW_PROTOCOL": "none", "GIT_NO_LAZY_FETCH": "1",
                 "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0",
                 "LC_ALL": "C"}
#: How long one git call may take before the scan goes on without it.
_GIT_TIMEOUT = 20


@functools.lru_cache(maxsize=1)
def _git_exe() -> str | None:
    """git's full path, from the absolute folders on PATH that are not the
    current folder: Windows looks in the current folder first, so a git.exe
    planted in the folder being linted would run. On Windows only git.exe
    counts: a .cmd or .bat shim runs through cmd.exe, which reinterprets
    the arguments. Folders are compared as real paths: on macOS a folder
    in /private/var can be named in /var, through a symbolic link."""
    name = "git.exe" if os.name == "nt" else "git"
    here = os.path.normcase(os.path.realpath(os.getcwd()))
    for d in os.environ.get("PATH", "").split(os.pathsep):
        if not d or not os.path.isabs(d) \
                or os.path.normcase(os.path.realpath(d)) == here:
            continue
        cand = os.path.join(d, name)
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand
    return None


#: Set when one git call in this scan took too long: the scan then stops
#: asking git (a FIFO among a repository's ignore files stalls each call).
_GIT_STALLED: list = []


def _git(folder: Path, *args: str):
    """git run in folder, as a CompletedProcess (returncode -1 when it could
    not run, took over _GIT_TIMEOUT seconds, or an earlier call in this
    scan did); None when there is no git. core.fsmonitor=false stops a
    repository's own config from starting a file-system monitor (a command
    it names) for what is only a read, and _GIT_SAFE_ENV keeps it from
    fetching anything."""
    exe = _git_exe()
    if exe is None:
        return None
    if _GIT_STALLED:
        return subprocess.CompletedProcess([exe], -2, b"", b"")
    env = {k: v for k, v in os.environ.items() if k not in _GIT_REPO_ENV
           and not k.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_"))}
    env.update(_GIT_SAFE_ENV)
    argv = [exe, "-C", str(folder), "-c", "core.fsmonitor=false",
            "-c", "protocol.allow=never", *args]
    try:
        return subprocess.run(argv, stdin=subprocess.DEVNULL,
                              capture_output=True, env=env,
                              timeout=_GIT_TIMEOUT)
    except subprocess.TimeoutExpired:
        _GIT_STALLED.append(str(folder))
        why = (f"git took longer than {_GIT_TIMEOUT} seconds, so the scan "
               "stops asking it").encode()
    except (OSError, subprocess.SubprocessError) as exc:
        why = str(exc).encode(errors="replace")
    return subprocess.CompletedProcess(argv, -1, b"", why)


def _nfc(name: str) -> str:
    return unicodedata.normalize("NFC", name)


def _why(result) -> str:
    lines = [x.strip() for x in result.stderr.decode("utf-8", "replace")
             .splitlines() if x.strip()]
    return (lines[0] if lines else f"exit {result.returncode}")[:200]


#: What _git_ignored returns for a folder git says is in no repository.
NOT_A_REPOSITORY = "not a repository"
#: What git says (in English: _GIT_SAFE_ENV) for a folder in no work tree,
#: or one whose .git file makes no repository: one that names no
#: repository ("not a git repository" up to 2.55, "gitfile does not
#: point to a valid repository" from 2.56), names nothing, or is not a
#: .git file's form. git reads such a folder as part of the repository
#: around it: that one's listing of what it ignores covers the folder
#: (measured with git 2.43, and with 2.55 for a .git file that names no
#: repository).
_NO_REPOSITORY = (b"not a git repository",
                  b"does not point to a valid repository",
                  b"no path in gitfile", b"invalid gitfile format")


def _git_ignored(folder: Path, notes: list | None = None):
    """What git ignores in folder (its .gitignore files, .git/info/exclude
    and the user's excludes file): (files, folders), as paths relative to
    folder, each folder ending in "/". None when git cannot say: no git, a
    folder outside any work tree, or git refusing or failing (a note says
    so, since ignored files are then linted). None too when folder itself
    is ignored: naming a folder asks for it, as naming a file does. A work
    tree's top folder is never ignored, whatever its rules say."""
    def note(result):
        if notes is not None and result.returncode != -2:
            notes.append(f"git could not read what it ignores in {folder} "
                         f"({_why(result)}); the scan there skips only "
                         "build and dependency folders")
        return None
    top = _git(folder, "rev-parse", "--show-prefix")
    if top is None:
        return None
    if top.returncode != 0:
        return NOT_A_REPOSITORY if any(m in top.stderr
                                       for m in _NO_REPOSITORY) \
            else note(top)
    if top.stdout.strip():
        own = _git(folder, "check-ignore", "-q", "--no-index", ".")
        if own.returncode == 0:
            return None
        if own.returncode != 1:
            return note(own)
    listed = _git(folder, "ls-files", "-z", "--others", "--ignored",
                  "--exclude-standard", "--directory")
    if listed.returncode != 0:
        return note(listed)
    files, folders = set(), set()
    for raw in listed.stdout.split(b"\0"):
        if raw:
            name = _nfc(os.fsdecode(raw))
            (folders if name.endswith("/") else files).add(name)
    return files, folders


class Excludes:
    """--exclude: shell-style patterns (fnmatch: `*` matches any characters,
    "/" too) for what a folder scan leaves out. A pattern is matched against
    the path of each file and folder relative to the folder named on the
    command line, and against its name alone; a pattern ending in "/"
    matches folders only, and an absolute one is matched against the
    absolute path. A folder that matches is not entered. A file named on
    the command line is linted whatever matches it. Which patterns matched
    nothing, and how much each left out, is said (excluded())."""

    def __init__(self, patterns=()):
        self.patterns = []
        for raw in patterns:
            text = _nfc(raw)
            folders_only = text.endswith("/")
            text = text.rstrip("/")
            while text.startswith("./"):
                text = text[2:]
            if not text:
                raise ValueError(f"--exclude {raw!r} names nothing")
            self.patterns.append((raw, text, folders_only,
                                  os.path.isabs(text)))
        self.hits = {raw: 0 for raw in patterns}
        self.files = 0
        self.folders = 0

    def __bool__(self) -> bool:
        return bool(self.patterns)

    def matches(self, path: Path, root: Path, folder: bool) -> bool:
        if not self.patterns:
            return False
        import fnmatch
        rel = _nfc(path.relative_to(root).as_posix())
        name = _nfc(path.name)
        absolute = None
        matched = False
        for raw, pattern, folders_only, is_abs in self.patterns:
            if folders_only and not folder:
                continue
            if is_abs:
                if absolute is None:
                    absolute = _nfc(Path(os.path.abspath(path)).as_posix())
                hit = fnmatch.fnmatchcase(absolute, pattern)
            else:
                hit = (fnmatch.fnmatchcase(rel, pattern)
                       or fnmatch.fnmatchcase(name, pattern))
            if hit:
                self.hits[raw] += 1        # each pattern that matches it
                matched = True
        if matched:
            if folder:
                self.folders += 1
            else:
                self.files += 1
        return matched

    def said(self) -> list[str]:
        """The notes a run with --exclude adds: what was left out, and each
        pattern that matched nothing (a mistyped one excludes nothing). A
        folder left out is not entered, so its files are not counted."""
        out = []
        if self.files or self.folders:
            out.append(f"--exclude left out {self.folders} folder(s), not "
                       f"entered, and {self.files} file(s) besides")
        for raw, hits in self.hits.items():
            if not hits:
                out.append(f"--exclude {raw!r} matched nothing")
        return out


def _walk(root: Path, notes: list | None = None,
          exclude: Excludes | None = None) -> list[Path]:
    """The lintable files under root (P3-10). A scan never enters a folder
    in SKIP_DIRS below root, nor anything git ignores there, nor what
    --exclude names (Excludes); a nested repository or submodule is read
    with its own ignore rules, as git reads it. Symbolic links to folders
    are not followed. Without git, or outside a work tree, only SKIP_DIRS
    and --exclude apply."""
    exclude = exclude if exclude is not None else Excludes()
    out: list[Path] = []
    rules: dict = {}         # folder -> (base, files, folders) or None
    top = os.path.realpath(root)
    outside: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        here = Path(dirpath)
        if here == root or (here / ".git").exists():
            ignored = _git_ignored(here, notes)
            if ignored == NOT_A_REPOSITORY:
                # A .git that makes no repository (a stale worktree or
                # submodule): git reads the folder as part of the one
                # around it, and so does the scan.
                rule = rules.get(here.parent)
            else:
                rule = None if ignored is None else (here, *ignored)
        else:
            rule = rules[here.parent]
        rules[here] = rule

        def is_ignored(p: Path, folder: bool = False) -> bool:
            if rule is None:
                return False
            name = _nfc(p.relative_to(rule[0]).as_posix())
            return (name + "/" in rule[2]) if folder else (name in rule[1])

        # --exclude is read first: a pattern that names what the scan
        # skips anyway (node_modules) matched it, and is not said to have
        # matched nothing.
        dirnames[:] = [d for d in dirnames
                       if not exclude.matches(here / d, root, True)
                       and d not in SKIP_DIRS
                       and not is_ignored(here / d, folder=True)]
        for name in filenames:
            f = here / name
            if f.suffix.lower() in ALL_EXTS and \
                    not exclude.matches(f, root, False) and f.is_file() \
                    and not is_ignored(f):
                if f.is_symlink() and os.path.commonpath(
                        [top, os.path.realpath(f)]) != top:
                    # Its lines would be printed as snippets: a link out
                    # of the tree (to a secret, /proc/self/environ) is not
                    # source to lint.
                    outside.append(str(f))
                    continue
                out.append(f)
    if outside and notes is not None:
        notes.append(f"skipped {len(outside)} symbolic link(s) to files "
                     f"outside {root}: {', '.join(outside[:3])}"
                     + (" …" if len(outside) > 3 else "")
                     + "; name one on the command line to lint it")
    return sorted(out)


#: A .js, .mjs or .css file found by a folder scan that is named as
#: minified (x.min.css), or has a line this long not counting its long
#: string literals and its data: URIs (base64 or not: R5G-12), is built
#: output committed to the repository (a minified bundle), which the scan
#: skips: lint reads source. A hand-written file with one long embedded
#: image or font is still linted.
_MINIFIED_LINE = 5000
_MINIFIABLE = {".js", ".mjs", ".css"}
_DATA = re.compile(r'"(?:[^"\\\n]|\\.){200,}"|\'(?:[^\'\\\n]|\\.){200,}\''
                   r'|`[^`]{200,}`'
                   r'|data:(?:[\w.+-]+/[\w.+-]+)?(?:;[^\s"\'(),;]+)*,'
                   r'[^\s"\'()]*', re.IGNORECASE)


def _minified(path: Path, text: str) -> bool:
    """Built output: a .js, .mjs or .css file named as minified (x.min.js)
    or with a line of code over _MINIFIED_LINE characters."""
    if path.suffix.lower() not in _MINIFIABLE:
        return False
    if ".min." in path.name.lower():
        return True
    return len(text) > _MINIFIED_LINE and any(
        len(line) > _MINIFIED_LINE and len(_DATA.sub("", line)) > _MINIFIED_LINE
        for line in text.splitlines())


def collect(paths: list[str], notes: list | None = None,
            exclude: Excludes | None = None) -> list[Path]:
    """The files to lint. A file named on the command line is always
    linted; a folder is scanned for lintable files (_walk). SKIP_DIRS and
    --exclude (`exclude`) are matched only below the named folder:
    matching the whole path skipped entire checkouts that live under a
    folder named build, dist or out (Bitbucket Pipelines clones into
    .../pipelines/agent/build). What the scan could not do (read git's
    ignore rules) is added to `notes`, and so is what --exclude did."""
    _GIT_STALLED.clear()
    out: list = []                      # (file, named on the command line)
    for p in paths:
        pp = Path(p)
        if pp.is_file():
            out.append((pp, True))
        elif pp.is_dir():
            out += [(f, False) for f in _walk(pp, notes, exclude)]
        else:
            raise FileNotFoundError(p)
    if exclude and notes is not None:
        notes += exclude.said()
    # A file named twice, or named and inside a folder named too, is one
    # file, linted once (R4E-5): the same name in the same real folder,
    # however the path to that folder is spelled (R4G-6; a link to a file
    # is a name of its own, linted as its own extension says, R2C-8i),
    # under the name the command line gave it when it gave one, since a
    # named file is always linted (R4G-4).
    listings: dict = {}
    named = {file_key(f, listings) for f, given in out if given}
    seen: set = set()
    once = []
    for f, given in out:
        key = file_key(f, listings)
        if key in seen or (not given and key in named):
            continue
        seen.add(key)
        once.append(f)
    return once


def file_key(path, listings: dict | None = None) -> tuple:
    """One key for each name of a file: its folder as the file system
    identifies it (`a/link/../x.jsx` is in the folder the link's target's
    parent is), and its name as that folder lists it. A name spelled in
    another case or Unicode normalization, where the file system ignores
    the difference (macOS, Windows), is the entry it finds (R5A-14). A
    link to a file is an entry of its own. `listings` caches each folder's
    names."""
    import unicodedata
    path = os.fspath(path)
    # Not abspath first: it would read link/.. as no folder at all.
    folder = os.path.dirname(path) or "."
    try:
        st = os.stat(folder)
        # No inode (0) on some file systems (FAT): its real path instead.
        where: tuple = ((st.st_dev, st.st_ino) if st.st_ino else
                        (os.path.normcase(os.path.realpath(folder)),))
    except OSError:
        where = (os.path.normcase(os.path.realpath(folder)),)
    name = os.path.basename(path)
    names = listings.get(where) if listings is not None else None
    if names is None:
        try:
            names = set(os.listdir(folder))
        except OSError:
            names = set()
        if listings is not None:
            listings[where] = names
    if name not in names:
        def fold(n: str) -> str:
            return unicodedata.normalize("NFC", n).casefold()
        same = [n for n in names if fold(n) == fold(name)]
        if len(same) == 1:
            name = same[0]
    return where + (name,)


#: What each lint rule looks for, in a line (SARIF's rule descriptions,
#: A9). The finding's own message says what it found and what to do.
LINT_RULES = {
    "bl-zoom-block": "A viewport that blocks or caps zoom below 200%",
    "bl-positive-tabindex": "A positive tabindex, which overrides the focus "
                            "order",
    "bl-marquee-blink": "<marquee>, content that moves with no pause "
                        "control, or the obsolete <blink>",
    "bl-junk-alt-src": "alt text that is a file name or an image path",
    "bl-css-order": "CSS that may reorder content away from the reading and "
                    "tab order",
    "bl-carousel-autoplay": "A carousel or slider set to rotate by itself",
    "bl-dangerous-html": "Injected HTML, which only the rendered output "
                         "shows",
    "bl-autofocus": "autofocus, which skips the skip link and disorients "
                    "screen-reader users",
    "bl-doc-link": "A link to a document file (PDF, Word, Excel, "
                   "PowerPoint), outside evaluation",
    "bl-menu-role": "An ARIA menu role, wrong for site navigation",
    "bl-div-click": "A click handler on an element that is no control: no "
                    "role, name, keyboard support or focus",
    "bl-aria-expanded-link": "aria-expanded on a link, where a disclosure "
                             "button belongs",
    "bl-anchor-button": "A link with no real destination, used as a button",
    "bl-button-type": "A <button> with no type, which submits its form",
    "bl-icon-button-name": "A button whose only content is an icon, with no "
                           "accessible name",
    "bl-downevent-activation": "Activation on a down-event, which users "
                               "cannot cancel",
    "bl-placeholder-label": "A field whose placeholder may be its only label",
    "bl-tabindex-noninteractive": "tabindex=0 on an element with no role or "
                                  "name",
    "bl-autoplay-media": "Audio or video that plays by itself, with sound or "
                         "without a way to pause it",
    "bl-meta-refresh": "A timed refresh or redirect the user does not "
                       "control",
    "bl-conditional-live-region": "A live region mounted with its text "
                                  "already inside, which announces nothing",
    "bl-outline-none-class": "A class that removes the focus outline",
    "bl-outline-none-css": "CSS that removes the focus outline",
    "bl-lint-error": "A file bellbriar-lint could not lint; check it by hand",
}

#: SARIF 2.1.0, which GitHub code scanning reads (`--format sarif`, A9).
SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"


def sarif(findings: list, notes: list) -> dict:
    """The findings as one SARIF 2.1.0 run, for GitHub code scanning
    (A9): each finding a result on its file and line, the error and warning
    severities as SARIF's `error` and `warning` levels, and a file inside
    the folder the scan ran in as a forward-slashed path relative to it
    (any other as an absolute file: URI). Each rule the run reports is
    described (LINT_RULES). What the scan could not do is in the run's
    notifications: a file it could not lint (bl-lint-error) is one at level
    error, with its file, not a result, and makes the run's
    `executionSuccessful` false (R4B-10)."""
    import os
    import urllib.parse

    from . import __version__
    here = os.getcwd()

    def uri(path: str) -> str:
        full = os.path.abspath(path)
        if full == here or full.startswith(here.rstrip(os.sep) + os.sep):
            # A name that is not valid UTF-8 reaches here with its bytes
            # escaped (surrogateescape): those bytes, percent-encoded
            # (R4B-9).
            return urllib.parse.quote(
                os.path.relpath(full, here).replace(os.sep, "/"),
                errors="surrogateescape")
        return Path(full).as_uri()

    unlinted = [f for f in findings if f.rule_id == "bl-lint-error"]
    findings = [f for f in findings if f.rule_id != "bl-lint-error"]
    order = sorted({f.rule_id for f in findings})
    index = {rid: i for i, rid in enumerate(order)}
    rules = [{"id": rid,
              "shortDescription": {"text": LINT_RULES.get(rid, rid)},
              "properties": {"tags": ["accessibility"]}} for rid in order]
    results = [{
        "ruleId": f.rule_id,
        "ruleIndex": index[f.rule_id],
        "level": "error" if f.severity == ERROR else "warning",
        "message": {"text": f"{f.message} (WCAG pack rule {f.ref})"},
        "locations": [{"physicalLocation": {
            "artifactLocation": {"uri": uri(f.path)},
            "region": {"startLine": max(int(f.line or 1), 1)}}}],
    } for f in findings]
    return {
        "$schema": SARIF_SCHEMA,
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {
                "name": "bellbriar-lint",
                "version": __version__,
                "semanticVersion": __version__,
                "informationUri": "https://github.com/bellbriar/harness",
                "rules": rules}},
            "invocations": [{
                "executionSuccessful": not unlinted,
                "toolExecutionNotifications": [
                    {"level": "error", "message": {"text": f.message},
                     "locations": [{"physicalLocation": {
                         "artifactLocation": {"uri": uri(f.path)}}}]}
                    for f in unlinted] + [
                    {"level": "note", "message": {"text": n}}
                    for n in notes]}],
            "results": results,
        }],
    }


#: The format string `--format json` output starts with: its fields are
#: documented in docs/REPORT.md, and within bellbriar-lint/1 none is
#: removed, renamed or given another meaning.
LINT_FORMAT = "bellbriar-lint/1"


def main(argv=None) -> int:
    """bellbriar-lint: _main, with everything it prints escaped as
    redact.console_text escapes it (R4G-5), ending quietly with status 2
    when the reader of its output stops reading (R5D-15). On Windows it
    stops first (support.py)."""
    from .redact import run_escaped
    from .support import refuse_unsupported
    refused = refuse_unsupported("bellbriar-lint")
    if refused is not None:
        return refused
    return run_escaped(_main, argv)


def _main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="bellbriar-lint",
        description="Source-level lint for the WCAG pack's deterministic "
                    "failure signatures. A clean lint is not a clean gate: "
                    "run bellbriar-eval on built output too.")
    ap.add_argument("paths", nargs="+", help="source files or directories")
    ap.add_argument("--fail-on", choices=[ERROR, WARN, "never"],
                    default=ERROR,
                    help="exit 1 on findings of this severity or worse: "
                         f"{ERROR} (the default: patterns that are wrong "
                         f"essentially always), {WARN} (also those a human "
                         "or the gate must confirm), or never; exit 2 when "
                         "nothing could be read")
    ap.add_argument("--format", choices=["text", "json", "sarif"],
                    default="text",
                    help="text for people; json (bellbriar-lint/1, "
                         "docs/REPORT.md) for scripts; sarif (SARIF 2.1.0) "
                         "for GitHub code scanning, which shows each finding "
                         "on its line in a pull request")
    ap.add_argument("--allow-empty", action="store_true",
                    help="exit 0 when no lintable files are found (default: "
                         "exit 2, because a clean lint over nothing is not a "
                         "clean lint)")
    ap.add_argument("--exclude", action="append", default=[],
                    metavar="PATTERN",
                    help="leave out of a folder scan each file and folder "
                         "this shell-style pattern matches (* matches any "
                         "characters, / too), by its path below the named "
                         "folder or by its name: --exclude '*.stories.tsx' "
                         "--exclude src/legacy; a pattern ending in / "
                         "matches folders only. Repeat it for more. A file "
                         "named on the command line is linted all the same; "
                         "what was left out, and a pattern that matched "
                         "nothing, is said")
    args = ap.parse_args(argv)

    notes: list[str] = []
    try:
        exclude = Excludes(args.exclude)
    except ValueError as exc:
        print(f"[bellbriar-lint] error: {exc}", file=sys.stderr)
        return 2
    try:
        files = collect(args.paths, notes, exclude)
    except FileNotFoundError as exc:
        print(f"[bellbriar-lint] not found: {exc}", file=sys.stderr)
        return 2
    for note in notes:
        print(f"[bellbriar-lint] note: {note}", file=sys.stderr)
    if not files and not args.allow_empty:
        print("[bellbriar-lint] error: no lintable files found in "
              f"{', '.join(args.paths)} (looked for "
              f"{', '.join(sorted(ALL_EXTS))}, outside build and dependency "
              "folders" + (", what git ignores and what --exclude leaves out"
                           if exclude else " and what git ignores")
              + "). Refusing to report a clean lint over nothing; pass "
              "--allow-empty if that is intended.",
              file=sys.stderr)
        return 2

    findings: list[Finding] = []
    listings: dict = {}
    named = {file_key(p, listings) for p in args.paths if Path(p).is_file()}
    minified: list[str] = []
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
            if file_key(f, listings) not in named and _minified(f, text):
                minified.append(str(f))
                continue
            findings += lint_text(text, str(f))
        except (Exception, RecursionError) as exc:  # noqa: BLE001
            # One file the linter cannot read must not end the run, or
            # hide it: it is reported, and needs a person.
            findings.append(Finding(
                "bl-lint-error", WARN, str(f), 1,
                f"bellbriar-lint could not lint this file ({type(exc).__name__}"
                f": {str(exc)[:160]}) — check it by hand.", "—", ""))

    if minified:
        shown = ", ".join(minified[:3]) + (f" and {len(minified) - 3} more"
                                           if len(minified) > 3 else "")
        notes.append(f"skipped {len(minified)} file(s) that look minified "
                     "(named as minified, or with a line of code over "
                     f"{_MINIFIED_LINE:,} characters): {shown}; name one on "
                     "the command line to lint it")
        print(f"[bellbriar-lint] note: {notes[-1]}", file=sys.stderr)
    scanned = len(files) - len(minified)
    if files and not scanned and not args.allow_empty:
        print("[bellbriar-lint] error: every file found looks minified, so "
              "nothing was linted. Refusing to report a clean lint over "
              "nothing; name the files to lint them, or pass --allow-empty.",
              file=sys.stderr)
        return 2
    unlinted = {f.path for f in findings if f.rule_id == "bl-lint-error"}
    linted = {str(f) for f in files} - set(minified)
    if linted and linted <= unlinted:
        # Every file it was to lint failed: nothing was linted, which is
        # not a clean lint (R4C-10). The findings still say why.
        nothing = True
    else:
        nothing = False
    n_err = sum(1 for f in findings if f.severity == ERROR)
    n_warn = len(findings) - n_err

    if args.format == "sarif":
        print(json.dumps(sarif(findings, notes), indent=2))
    elif args.format == "json":
        # A stable format for scripts (docs/REPORT.md, "bellbriar-lint/1").
        print(json.dumps({"format": LINT_FORMAT,
                          "files_scanned": scanned,
                          "errors": n_err, "warnings": n_warn,
                          "notes": notes,
                          "findings": [asdict(f) for f in findings]},
                         indent=2))
    else:
        from .redact import printable
        for f in findings:
            # A name or a line of source as one line of output (R4I-2).
            print(f"{printable(f.path)}:{f.line} {f.severity:5} "
                  f"{f.rule_id:28} {printable(f.message)} "
                  f"(WCAG pack rule {f.ref})")
            if f.snippet:
                print(f"    | {printable(f.snippet)}")
        print(f"\n{scanned} file(s) scanned — {n_err} error(s), "
              f"{n_warn} warning(s). Lint checks source habits; "
              f"bellbriar-eval on built output remains the gate.")

    if nothing:
        print(f"[bellbriar-lint] error: none of the {scanned} file(s) could "
              "be linted (each is reported as bl-lint-error); that is not a "
              "clean lint.", file=sys.stderr)
        return 2
    if args.fail_on == "never":
        return 0
    if args.fail_on == WARN:
        return 1 if findings else 0
    return 1 if n_err else 0


if __name__ == "__main__":
    sys.exit(main())
