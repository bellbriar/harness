"""Keeping credentials and access tokens out of everything the harness records.

A URL run writes URLs where other people read them: the evidence bundle,
which is signed and handed to third parties; the reports; and the
console, which in CI is a build log. A signed bundle cannot be redacted
afterwards without breaking its signature, because its digest covers
every URL in it. A secret recorded at capture time would leave a bad
choice later: hand over a live secret, or hand over evidence that no
longer verifies.

Protected staging and preview pages are reached with exactly such
secrets: a password in the URL (https://user:pass@host/) or an access
token in the query (?token=…, ?x-vercel-protection-bypass=…). So every
URL the harness records passes through redact_url first:

* a user name and password are removed;
* every parameter value in the query and in the fragment is replaced with
  REDACTED, unless the operator named that parameter with --record-query.
  A parameter written without "=" is all value and replaced whole:
  `?<token>` is a token. So is one with nothing but "=" after a name that
  looks like a credential (eight characters or more, not a plain
  lowercase word): a padded Base64 token `?<token>=` (R1B-5). An ordinary
  empty parameter (`?q=`) is kept as written;
* a fragment that is a client route (`#/about`, `#!/about`) keeps its
  path, as a URL keeps its own, so two routes of one app stay apart in a
  report (L39); a query written after it (`#/search?q=…`) is redacted as
  a query is. A route holding "=", "&", ";", "#" or "?" before its query,
  spelled out or percent-encoded (once or more), is read as parameters
  instead: that is how a token handed back to a hash-routed app looks
  (`#/access_token=…`). So is one holding a space or a character outside
  printable ASCII, which a browser reports percent-encoded;
* scheme, host, port, path and parameter names are kept as written. A
  token in a path, or in a route's path, is recorded with it: nothing
  tells it from a page's name.

Redaction never changes the host a verifier reads (bundle.url_host), so it
cannot alter what a bundle binds: the host and port are not touched, and
userinfo is cut at its last "@", where browsers and url_host both cut it.
A URL that read no host only because a removed part held a character
url_host refuses (a space in a fragment, a non-ASCII query value) reads
one afterwards: the host every parser read from it all along, and the
value a browser-reported URL records anyway, since a browser
percent-encodes those characters. A URL whose authority holds a
backslash, where parsers disagree about the host, is withheld whole. What
was measured is identified by the snapshot hash, not by the URL.
"""
from __future__ import annotations

import contextlib
import contextvars
import functools
import html
import os
import re
import sys
import unicodedata
import urllib.parse
from html.entities import html5 as _HTML5_REFERENCES

REDACTED = "REDACTED"

#: The secrets of the run being evaluated (set_run_secrets), longest
#: first: a URL run's credential-like parameter values, its --http-user
#: password and the Authorization header that carries it
#: (basic_auth_tokens). They are found in the spellings text, markup, a
#: URL, JSON, a script or CSS write (_secrets_regex: R6C-1, R6G-5).
#: Every snippet and message a finding records has them replaced before
#: it is cut (R6A-2), and no locator anchors on an id that holds one
#: (R5E-1 to R5E-3, H6-1).
_RUN_SECRETS: contextvars.ContextVar[tuple] = contextvars.ContextVar(
    "bellbriar_run_secrets", default=())
#: The --http-user password, as patterns that find it (password_pattern).
#: A password can be an ordinary word ("name", "test"), which the
#: harness's own words and any markup may hold, and a word left around
#: where it was replaced gives it away (`data-REDACTEDid`): a finding's
#: snippet, locator or message that holds it is withheld whole (WITHHELD,
#: R5H-6).
_RUN_PASSWORDS: contextvars.ContextVar[tuple] = contextvars.ContextVar(
    "bellbriar_run_passwords", default=())
#: A password shorter than this is not looked for: it would match ordinary
#: text everywhere (R5E-10).
MIN_PASSWORD_SCRUB = 4
#: What a finding's message says in place of one that held the run's
#: --http-user password (R5H-6).
WITHHELD_MESSAGE = ("(withheld: this finding's message held the run's "
                    "--http-user password)")


#: Every white-space character (str.isspace: ASCII's, the no-break space,
#: the ideographic space, the typographic spaces), as a password's run of
#: white space is found in any of them, whatever its own (R5R-1, R6A-7).
_WHITE = tuple(chr(c) for c in range(0x3001) if chr(c).isspace())
#: The most white-space characters, in any spelling, an inner run of a
#: password's white space is found as: a bound that keeps a search linear
#: on a hostile run of encoded white space (R6A-5).
_MAX_SPACE_RUN = 32
#: The backslashes a backslash escape starts with (`\u0041`, `\41 `): one
#: or more, as a string escaped again any number of times writes them
#: (JSON in JSON: `\\u0041`), taken whole from the first backslash of a
#: run. A search tries a run of backslashes once, not once from each of
#: its backslashes, which made a search over a long run quadratic (R6G-2).
_BS = r"(?<!\\)\\++"
#: The backslashes an escape starts with just after a run of a secret's
#: own backslashes (_backslash_run), which takes its own first: one to
#: four, as JSON escaped up to three times more writes them.
_BS_AFTER_RUN = r"\\{1,4}"
#: What CSS reads as the end of a hex escape: one white-space character,
#: CR LF counting as one.
_CSS_SPACE = r"(?:\r\n|[ \t\n\r\f])"
#: No hex digit or white space after an escape's digits, and no white
#: space after six: CSS would read either as part of it.
_CSS_ENDED = r"(?![0-9a-fA-F \t\n\r\f])"
_NO_CSS_SPACE = r"(?![ \t\n\r\f])"


def _amp(bs: str, ignore_case: bool = False) -> str:
    """An ampersand, as a page writes it when it escapes what was already
    escaped, once or more, or not: "&" written again as `&amp;` or `&#38;`
    (R6A-3, R6C-8), or as a script's or JSON's escape after the
    backslashes `bs` (`\\u0026#43;`, Go's JSON of `&#43;`: R6E-1). With
    `ignore_case`, for a pattern that ignores case, no two of its
    alternatives read the same text, or a long run of `amp;` could be read
    in exponentially many ways (R6E-7)."""
    again = ("(?:amp;|#0*38;|#x0*26;)" if ignore_case
             else "(?:amp;|AMP;|#0*38;|#[xX]0*26;)")
    return f"(?:&|{bs}u0026|{bs}x26){again}*"


def _pct(bs: str, ignore_case: bool = False) -> str:
    """A percent sign, escaped again once or more, or not: "%" as `%25`
    (`%2520`), as a character reference (`&#37;20`, `&percnt;`, its "&"
    as _amp writes it: `&amp;#37;`), or as a script's or JSON's escape
    after the backslashes `bs` (R6A-3, R6C-8, R6E-1)."""
    x = "x" if ignore_case else "[xX]"
    return (f"(?:%|{bs}u0025|{bs}x25|{_amp(bs, ignore_case)}"
            f"(?:#0*37;|#{x}0*25;|percnt;))(?:25)*")


@functools.lru_cache(maxsize=1)
def _references() -> dict:
    """{character: (its names, other numbers)}: the names HTML gives it
    (html5's, with ";", and the legacy ones a browser reads without it
    too: `&eacute`), and the numbers below 160 HTML reads as it rather
    than as their own code point (Windows-1252's: `&#128;` is the euro
    sign)."""
    got: dict = {}
    for name, value in _HTML5_REFERENCES.items():
        if len(value) == 1:
            got.setdefault(value, ([], []))[0].append(name)
    for n in range(0x80, 0xA0):
        try:
            ch = bytes((n,)).decode("cp1252")
        except UnicodeDecodeError:
            continue        # read as its own code point
        got.setdefault(ch, ([], []))[1].append(n)
    return got


def _numbers(ch: str) -> list:
    """The numbers a character reference gives `ch` by, as HTML reads them:
    its code point (but one of 128 to 159 HTML reads as Windows-1252's
    character), and Windows-1252's number for it."""
    own = ord(ch)
    out = [] if 0x80 <= own < 0xA0 and _cp1252(own) else [own]
    return out + list(_references().get(ch, ((), ()))[1])


def _cp1252(n: int) -> bool:
    try:
        bytes((n,)).decode("cp1252")
    except UnicodeDecodeError:
        return False
    return True


def _named(name: str) -> str:
    """A pattern for a reference by `name`: with ";", or a legacy name with
    none after it (one with ";" is matched as the other name)."""
    return re.escape(name) + ("" if name.endswith(";") else "(?!;)")


@functools.lru_cache(maxsize=1)
def _folded_to() -> dict:
    """{a full case folding: the characters that fold to it}, for the
    characters that fold to another ("\u1e9e" and "\u00df" to "ss")."""
    out: dict = {}
    for c in range(0x110000):
        ch = chr(c)
        folded = ch.casefold()
        if folded != ch:
            out.setdefault(folded, []).append(ch)
    return out


def _cases(ch: str) -> list:
    """`ch` in each case: itself, its lower and upper case, its full case
    folding, and every character that folds as it does (the capital
    sharp s for "\u00df": R6C-8)."""
    folded = ch.casefold()
    out = dict.fromkeys((ch, ch.lower(), ch.upper(), folded))
    if not ch.isascii():
        out.update(dict.fromkeys(_folded_to().get(folded, ())))
    return list(out)


def _hex(n: int, width: int = 0) -> str:
    """`n` in hex, as a pattern that takes either case of its letters."""
    return "".join(c if c.isdigit() else f"[{c}{c.upper()}]"
                   for c in f"{n:0{width}x}")


def _lower_hex(n: int, width: int = 0) -> str:
    """`n` in hex, for a pattern that ignores case."""
    return f"{n:0{width}x}"


def _identity(ch: str) -> bool:
    """Is `ch` one a backslash before it leaves as it is, in a script's
    strings and in CSS alike (`\\-`, `\\_`, `\\.`, `\\/`, `\\"`, `\\g`)?
    Not a hex digit, which CSS reads as a code point; not "u" or "x",
    which start a script's escapes; not "n", "r", "t" or "v", which a
    script reads as control characters; not "&", "%" or a backslash, which
    start other spellings; no white space or control character."""
    return not (ch in "0123456789abcdefABCDEFuUxXnNrRtTvV&%\\"
                or ch.isspace() or ch in "\u2028\u2029"
                or unicodedata.category(ch) in ("Cc", "Cs"))


def _octal(n: int) -> list:
    """`n` (1 to 255) as an octal escape writes it after its backslash
    (a script's legacy one, Python's, C's), as patterns: three digits, and
    fewer where a script reads them as the whole escape (`\\55`; `\\7`
    and `\\07` only where no octal digit follows)."""
    out = [f"{n:03o}"]
    if n < 0o100:
        two = f"{n:02o}"
        out.append(two if two[0] in "4567" else two + "(?![0-7])")
    if n < 0o10:
        out.append(f"{n:o}(?![0-7])")
    return out


def _css(n: int, hexa) -> list:
    """`n` as CSS's hex escape writes it after its backslash, as patterns:
    its hex digits (`hexa`), with zeros before them up to six digits in
    all, then the one white-space character CSS reads as part of the
    escape, taken where there is one, or no hex digit after fewer than six
    (`\\41 `, `\\000041`). One reading only: a run of such escapes with
    white space after each is read one way (R6G-5)."""
    digits = hexa(n)
    d = len(f"{n:x}")
    out = []
    if d < 6:
        out.append(f"0{{0,{5 - d}}}{digits}(?:{_CSS_SPACE}|{_CSS_ENDED})")
    out.append(f"0{{{6 - d}}}{digits}(?:{_CSS_SPACE}|{_NO_CSS_SPACE})")
    return out


def _escapes(ch: str, bs: str, family, ignore_case: bool,
             identity: bool = True) -> list:
    """`ch` as a backslash escape writes it after the backslashes `bs`
    (_BS), as patterns: JSON's and a script's `\\u` (each UTF-16 unit
    after its own backslashes) and, below U+0100, `\\x`; a script's
    `\\u{...}`; an octal escape below U+0100 (_octal), unless `family` is
    "C"; CSS's hex escape (_css), unless `family` is "J"; and, with
    `identity`, the character itself where a backslash leaves it as it is
    (_identity: `\\/`, `\\-`, R6G-5). Hex digits in either case."""
    hexa = _lower_hex if ignore_case else _hex
    n = ord(ch)
    units = ch.encode("utf-16-be")
    out = ["".join(bs + "u" + hexa(int.from_bytes(units[k:k + 2], "big"), 4)
                   for k in range(0, len(units), 2))]
    if n < 0x100:
        out.append(bs + "x" + hexa(n, 2))
    out.append(bs + r"u\{0*" + hexa(n) + r"\}")
    if family != "C" and 0 < n < 0x100:
        out += [bs + o for o in _octal(n)]
    if family != "J" and n and not 0xD800 <= n < 0xE000:
        out += [bs + c for c in _css(n, hexa)]
    if identity and _identity(ch):
        out.append(bs + re.escape(ch))
    return out


def _spellings(ch: str, *, bs: str = _BS, family=None, cases: bool = False,
               ignore_case: bool = False) -> list:
    """Each way text, markup, a URL, JSON, a script or CSS writes `ch`, as
    patterns: itself (with `cases`, in any case, _cases: its full case
    folding too, "\u00df" as "ss"); a character reference, decimal or hex,
    with its ";" or without where no digit follows, as a browser reads
    it, or named (_references); percent-encoded in UTF-8, and below U+0100
    in Latin-1 too; each "&" or "%" escaped again or not (_amp, _pct;
    R6A-3, R6A-7); or a backslash escape (_escapes: R6C-1, R6E-1, R6G-5).
    A space is "+" too, as a query writes it. With `ignore_case`, for a
    pattern that ignores case, no two of them read the same text ("n" and
    "N" are one: R6E-7)."""
    amp, pct = _amp(bs, ignore_case), _pct(bs, ignore_case)
    hexa = _lower_hex if ignore_case else _hex
    x = "x" if ignore_case else "[xX]"
    alts: dict = {}
    kept: list = []
    for c in (_cases(ch) if cases else (ch,)):
        new = not (ignore_case and any(
            re.fullmatch(re.escape(k), c, re.IGNORECASE)
            and re.fullmatch(re.escape(c), k, re.IGNORECASE)
            for k in kept))
        if new:
            kept.append(c)
            alts[re.escape(c)] = None
        if len(c) != 1:
            continue
        if c == " ":
            alts[r"\+"] = None
        try:
            alts["".join(pct + hexa(b, 2) for b in c.encode("utf-8"))] = None
        except UnicodeEncodeError:
            pass
        if 0x80 <= ord(c) < 0x100:
            alts[pct + hexa(ord(c), 2)] = None
        for n in _numbers(c):
            alts[amp + f"#0*{n}(?:;|(?![0-9]))"] = None
            alts[amp + f"#{x}0*{hexa(n)}(?:;|(?![0-9a-fA-F]))"] = None
        for name in _references().get(c, ((), ()))[0]:
            alts[amp + (_named(name).lower() if ignore_case
                        else _named(name))] = None
        alts.update(dict.fromkeys(_escapes(c, bs, family, ignore_case,
                                           identity=new)))
    return list(alts)


def _any_space(own, plus: bool = True) -> str:
    """One white-space character, as text, markup, a URL, JSON, a script
    or CSS writes any of _WHITE and `own`: itself (\\s), "+" (a query's
    space), percent-encoded (UTF-8, and Latin-1 below U+0100), as a
    character reference, decimal, hex or named (`&nbsp;`, `&Tab;`), with
    its ";" or without where a browser reads it so, each "%" or "&"
    escaped again or not (_pct, _amp), as a backslash escape (_escapes:
    `\\u0020`, `\\x20`, `\\u{20}`, `\\40`, `\\20 `: R6E-1), or as JSON's and
    a script's own escapes for a tab, a line feed, a carriage return and a
    form feed, and a script's for a vertical tab (`\\t`: R6G-5). Taken
    whole, one alternative only (an atomic group), so that a run of them
    is read one way (R5R-5). Without `plus`, no "+" (password_pattern:
    R6C-4, R6E-2)."""
    chars = dict.fromkeys((*_WHITE, *own))
    amp, pct = _amp(_BS, True), _pct(_BS, True)
    pcts, dec, hexa, named, bodies = {}, {}, {}, {}, {}
    for ch in chars:
        try:
            pcts[pct.join(f"{b:02x}" for b in ch.encode("utf-8"))] = None
        except UnicodeEncodeError:
            pass
        if 0x80 <= ord(ch) < 0x100:
            pcts[f"{ord(ch):02x}"] = None
        for n in _numbers(ch):
            dec[str(n)] = None
            hexa[f"{n:x}"] = None
        for name in _references().get(ch, ((), ()))[0]:
            named[_named(name).lower()] = None
        for e in _escapes(ch, _BS, None, True):
            bodies[e[len(_BS):]] = None      # each one starts with _BS
    for ch, e in (("\t", "t"), ("\n", "n"), ("\r", "r"), ("\f", "f"),
                  ("\v", "v")):
        if ch in chars:
            bodies[e] = None
    alts = [r"\s"] + ([r"\+"] if plus else []) + [
        pct + "(?:" + "|".join(pcts) + ")",
        amp + "#0*(?:" + "|".join(dec) + r")(?:;|(?![0-9]))",
        amp + "#x0*(?:" + "|".join(hexa) + r")(?:;|(?![0-9a-f]))",
        _BS + "(?:" + "|".join(bodies) + ")"]
    if named:
        alts.append(amp + "(?:" + "|".join(named) + ")")
    return "(?>" + "|".join(alts) + ")"


def _backslash_run(m: int, family, ignore_case: bool) -> str:
    """A run of `m` backslashes in a secret or a password, as one pattern
    taken whole (an atomic group), so that a long run is read one way
    only, not split among its backslashes in every way, which made a near
    miss exponential (R6G-6): written out, or each one doubled, four or
    eight times over, as JSON escaped once, twice or three times writes
    it, the largest count that fits first, the backslashes after it left
    to an escape that follows (_BS_AFTER_RUN); or each one spelled the
    same other way (`%5C`, `&#92;`, `&bsol;`, `\\u005c`)."""
    whole = "|".join(rf"\\{{{f * m}}}" for f in (8, 4, 2, 1))
    one = [a for a in _spellings("\\", family=family,
                                 ignore_case=ignore_case)
           if a != re.escape("\\")]
    return f"(?>{whole}|(?:{'|'.join(one)}){{{m}}})"


def _secret_pattern(secret: str, family: str, ignore_case: bool) -> str:
    """`secret` as one pattern: each character in any spelling _spellings
    reads, with the backslash escapes of `family` ("J": JSON's and a
    script's, octal ones included; "C": JSON's and CSS's); a run of its
    backslashes as _backslash_run reads it."""
    out = ""
    k = 0
    bs = _BS
    while k < len(secret):
        if secret[k] == "\\":
            end = k
            while end < len(secret) and secret[end] == "\\":
                end += 1
            out += _backslash_run(end - k, family, ignore_case)
            k, bs = end, _BS_AFTER_RUN
            continue
        out += "(?:" + "|".join(_spellings(
            secret[k], bs=bs, family=family, ignore_case=ignore_case)) + ")"
        k, bs = k + 1, _BS
    return out


#: The longest spelling, per character, the reach of a search allows for:
#: `&amp;#x10ffff;` or a four-byte character percent-encoded twice is less.
_SPELLED_PER_CHARACTER = 24
#: A secret whose characters these all are is looked for by a pre-check
#: first (_hits): ASCII's letters and digits, and "-", "_", ".", "~",
#: "=", "+" and "/", which tokens are made of.
_PLAIN_SECRET = re.compile(r"[A-Za-z0-9\-_.~=+/]+\Z")
#: The characters the pre-check reads after a backslash as themselves
#: (_identity): those of _PLAIN_SECRET a backslash leaves as they are, and
#: the quotes.
_READ_AS_THEMSELVES = "".join(
    re.escape(c) for c in ("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstu"
                           "vwxyz0123456789-_.~=+/\"'") if _identity(c))
#: The legacy names a browser reads without ";" (`&copy`), and what of a
#: secret's first characters an escape the text writes before it can take
#: with one: the rest of `\u0026` or `\x26` (_amp), before such a name.
_LEGACY_NAMES = tuple(n for n in _HTML5_REFERENCES if not n.endswith(";"))
_ESCAPED_AMP_TAILS = tuple(sorted({t[i:] for t in ("u0026", "x26")
                                   for i in range(len(t))}))
#: A secret's first characters an escape the text writes before it could
#: read as its own: hex digits, after "u" or "x" or not (`%`, `&#`,
#: `&#x`, `\u`, `\u0025`, `\x`, an octal or a CSS escape).
_LEADING_HEX = re.compile(r"[uxX]?[0-9a-fA-F]*")


@functools.lru_cache(maxsize=2)
def _reader(family: str):
    """A pattern that reads a text in one pass, left to right, a spelling
    at a time, as the search reads it with the backslash escapes of
    `family` (_secret_pattern), each spelling taken whole: a "%" or "&"
    escaped again and what follows it as one (`&amp;#37;41`, `\\u0026#65;`)
    rather than in passes, which read `&#65` with no ";" and a script's
    escape of a digit after it as one number (R6G-1). Runs of other
    characters, and a lone "&", "%" or run of backslashes, are read as
    they are (`lit`)."""
    bodies = [r"u(?P<u4>[0-9a-fA-F]{4})", r"x(?P<x2>[0-9a-fA-F]{2})",
              r"u\{0*(?P<u6>[0-9a-fA-F]{1,6})\}"]
    if family == "J":
        bodies.append(r"(?P<oct>[0-3][0-7]{0,2}|[4-7][0-7]?)")
    else:
        bodies.append(r"(?P<css>[0-9a-fA-F]{1,6})" + _CSS_SPACE + "?")
    bodies.append(f"(?P<id>[{_READ_AS_THEMSELVES}])")
    return re.compile(
        "(?P<pct>" + _pct(_BS) + ")(?P<pb>[0-9a-fA-F]{2})"
        "|" + _amp(_BS) + "(?:#0*(?P<dec>[0-9]+)(?:;|(?![0-9]))"
        "|#[xX]0*(?P<hex>[0-9a-fA-F]+)(?:;|(?![0-9a-fA-F]))"
        "|(?P<name>[A-Za-z][A-Za-z0-9]{0,31};?))"
        "|" + _BS + "(?:" + "|".join(bodies) + ")"
        r"|(?P<lit>[^&%\\]+|[&%]|\\+)")


def _read(m: re.Match) -> str:
    """The character a spelling _reader takes spells (U+FFFD for a number
    no character has, and for a percent-encoded byte outside ASCII), or
    the text it takes as it is."""
    kind = m.lastgroup
    text = m.group(kind)
    if kind in ("lit", "id"):
        return text
    if kind == "name":
        return html.unescape("&" + text)
    if kind == "oct":
        return chr(int(text, 8))
    if kind == "dec":
        text = text.lstrip("0") or "0"
        if len(text) > 8:       # int() refuses more than 4,300 digits
            return "\ufffd"
        return html.unescape(f"&#{text};")
    n = int(text, 16) if len(text.lstrip("0")) <= 8 else -1
    if kind == "pb":
        return chr(n) if n < 0x80 else "\ufffd"
    if kind == "hex":
        return html.unescape(f"&#x{n:x};") if n >= 0 else "\ufffd"
    if n <= 0 or n > 0x10FFFF or (kind != "u4" and 0xD800 <= n < 0xE000):
        return "\ufffd"
    return chr(n)


def _readings(text: str) -> tuple:
    """`text` as _reader reads it: with a script's octal escapes and with
    CSS's hex escapes, which read `\\61` as different characters ("1",
    "a"); once where it holds no backslash; as it is where it holds no
    "&", "%" or backslash."""
    if not re.search(r"[&%\\]", text):
        return (text,)
    first = _reader("J").sub(_read, text)
    if "\\" not in text:
        return (first,)
    return first, _reader("C").sub(_read, text)


@functools.lru_cache(maxsize=4096)
def _capture(secret: str) -> int:
    """How many of `secret`'s first characters an escape that starts
    before it in a text could read as its own, so that _reader reads them
    with it, not as the secret's: its first hex digits, after "u" or "x"
    or not (_LEADING_HEX); the end of a legacy name (`&co` before
    "pyright…"), or a whole one; and the rest of an escaped "&" with such
    a name after it (`\\u002` before "6copy…": R6G-1)."""
    k = _LEADING_HEX.match(secret).end()
    for name in _LEGACY_NAMES:
        for i in range(len(name)):
            if secret.startswith(name[i:]):
                k = max(k, len(name) - i)
                break
    for tail in _ESCAPED_AMP_TAILS:
        if secret.startswith(tail):
            rest = secret[len(tail):]
            k = max([k] + [len(tail) + len(n) for n in _LEGACY_NAMES
                           if rest.startswith(n)])
    return k


def _hits(secrets: tuple, text: str, ignore_case: bool = False) -> tuple:
    """Those of `secrets` the search (_secrets_regex) may find in `text`
    (R6E-9): each one of other characters than _PLAIN_SECRET's, or that
    `text` holds as it is, or whose characters past what an escape before
    it could take (_capture) are too few to look for or are in one of
    `text`'s readings (_readings). A secret left out is in none of the
    spellings the search reads, so a search over the others finds what
    one over all finds (R6G-1). With `ignore_case`, in any case: a text
    holding "&", "%" or a backslash may hold any of them."""
    if not secrets:
        return ()
    if ignore_case:
        if re.search(r"[&%\\]", text):
            return secrets
        folded = text.translate(_FOLDS).lower()
        return tuple(s for s in secrets if not _PLAIN_SECRET.match(s)
                     or s.lower() in folded)
    reads = None
    out = []
    for s in secrets:
        if not _PLAIN_SECRET.match(s) or s in text:
            out.append(s)
            continue
        k = _capture(s)
        if len(s) - k < 4:
            out.append(s)
            continue
        if reads is None:
            reads = _readings(text)
        if any(s[k:] in r for r in reads):
            out.append(s)
    return tuple(out)


#: The characters Python's regular expressions match an ASCII letter by,
#: in any case (U+0130 and U+0131 an "i", U+017F an "s", the Kelvin sign
#: a "k").
_FOLDS = str.maketrans({"\u0130": "i", "\u0131": "i", "\u017f": "s",
                        "\u212a": "k"})


def secrets_pattern(secrets):
    """A pattern that finds any of `secrets` in any spelling _spellings
    reads (None for none): for a check of the run's own records."""
    return _secrets_regex(tuple(sorted(
        {s for s in secrets if isinstance(s, str) and s}, key=len,
        reverse=True)))


@functools.lru_cache(maxsize=64)
def _secrets_regex(secrets: tuple, ignore_case: bool = False):
    """One pattern that finds any of `secrets` (longest first, so a padded
    token is found whole before its unpadded form) wherever text, markup,
    a URL, JSON, a script or CSS holds it, in any spelling _spellings
    reads, with the backslash escapes of a script or of CSS (both
    _secret_pattern's), not some of each: CSS reads `\\61` as "a", a
    script's octal escape as "1"; None for none."""
    if not secrets:
        return None
    return re.compile("|".join(_secret_pattern(s, family, ignore_case)
                               for s in secrets for family in ("J", "C")),
                      re.IGNORECASE if ignore_case else 0)


def basic_auth_tokens(user: str, password: str) -> set:
    """The --http-user credentials as a request's Authorization header
    carries them, base64 of "user:password", and the password alone in
    base64: the standard and URL-safe alphabets, padded or not. A page
    that echoes the request's headers (a debug page) quotes the header
    (R6A-1)."""
    import base64
    out = set()
    for raw in (f"{user}:{password}", password):
        data = raw.encode("utf-8", "replace")
        for enc in (base64.b64encode(data), base64.urlsafe_b64encode(data)):
            token = enc.decode("ascii")
            out |= {token, token.rstrip("=")}
    return {t for t in out if len(t) >= MIN_PASSWORD_SCRUB}


@functools.lru_cache(maxsize=32)
def password_pattern(password: str):
    """A pattern that finds `password` wherever text, markup, a URL, JSON,
    a script or CSS holds it, in any case: each of its characters in any
    spelling _spellings reads, in either case (its full case folding
    too), with the backslash escapes of a script and of CSS alike (a "+"
    in a query is a space too), with white space allowed between them (a
    tab or line break a browser drops from a URL, a line break a snippet
    or message makes one space: R5L-5, R5N-2); a run of its backslashes as
    _backslash_run reads it (R6G-6); a run of its own white space as a run
    of up to _MAX_SPACE_RUN white-space characters, any of them (_WHITE),
    in any spelling _any_space reads (U+00A0 as `%C2%A0` or `&nbsp;`, a tab
    as `\\t`: R5R-1, R6G-5). A browser percent-encodes only what a URL
    must (a space, not "!" or "$"), so no one spelling of the whole would
    do (R5P-2). A page's own legacy encoding (Shift_JIS, say) is not read.
    White space it starts or ends with is one character there, and an
    inner run is bounded (_MAX_SPACE_RUN, or the run's own length) and
    never gives back what it took, so a search stays linear (R5R-5,
    R6A-5, R6C-4, R6C-5, R6E-7).
    Where a run comes before a "+" of the password's own, the pattern is
    two, so that text is read one way: the run with no "+", the "+" in any
    spelling; or the run with "+" (a form's encoding), the "+" in any but
    itself (`%2B`: R6E-2). A password that holds a spelling of white space
    just after its own (`a %20b`) may be missed where its run is spelled
    so too. None for a password too short to look for
    (MIN_PASSWORD_SCRUB)."""
    if (not isinstance(password, str) or len(password) < MIN_PASSWORD_SCRUB
            or not password.strip()):
        return None
    # The password as runs: (white space?, its characters).
    runs: list[list] = []
    for ch in password:
        space = ch.isspace()
        if runs and runs[-1][0] == space:
            runs[-1][1].append(ch)
        else:
            runs.append([space, [ch]])

    def pattern(form: bool) -> str:
        out = ""
        for i, (space, chars) in enumerate(runs):
            if space:
                # Inside, a run of up to _MAX_SPACE_RUN, or its own length
                # where that is longer (R6C-5), taken whole; at either end,
                # one character. Before a "+" of the password's own, a "+"
                # in `form` only (R6C-4, R6E-2).
                plus = form or not (i + 1 < len(runs)
                                    and runs[i + 1][1][0] == "+")
                out += _any_space(chars, plus) + (
                    "{1,%d}+" % max(_MAX_SPACE_RUN, len(chars))
                    if 0 < i < len(runs) - 1 else "")
                continue
            k = 0
            bs = _BS
            while k < len(chars):
                if k:
                    out += r"\s*+"  # white space between two characters
                if chars[k] == "\\":
                    end = k
                    while end < len(chars) and chars[end] == "\\":
                        end += 1
                    out += _backslash_run(end - k, None, True)
                    k, bs = end, _BS_AFTER_RUN
                    continue
                alts = _spellings(chars[k], bs=bs, cases=True,
                                  ignore_case=True)
                if form and not k and i and chars[k] == "+":
                    alts = [a for a in alts if a != re.escape("+")]
                out += "(?:" + "|".join(alts) + ")"
                k, bs = k + 1, _BS
        return out
    plain = pattern(False)
    if any(space and i + 1 < len(runs) and runs[i + 1][1][0] == "+"
           for i, (space, _chars) in enumerate(runs)):
        plain = f"(?:{plain})|(?:{pattern(True)})"
    return re.compile(plain, re.IGNORECASE)


def set_run_secrets(secrets=(), passwords=(), keep: bool = False,
                    tokens=()):
    """Make `secrets` (values that look like credentials: _looks_secret),
    `tokens` (whatever their shape: basic_auth_tokens) and `passwords` (of
    MIN_PASSWORD_SCRUB characters or more, whatever their shape) the run's:
    replaced wherever a finding quotes them, in any spelling markup, a URL,
    JSON, a script or CSS writes (_spellings); a finding that quotes a
    password is
    withheld whole where it does (WITHHELD_MESSAGE). `keep`: add to what
    the run already has. Returns the token for reset_run_secrets."""
    held: set[str] = set(_RUN_SECRETS.get()) if keep else set()
    found: list = list(_RUN_PASSWORDS.get()) if keep else []
    held.update(s for s in secrets or () if _looks_secret(s))
    held.update(t for t in tokens or ()
                if isinstance(t, str) and len(t) >= MIN_PASSWORD_SCRUB)
    for p in passwords or ():
        pattern = password_pattern(p)
        if pattern is not None:
            held.add(p)
            if pattern not in found:
                found.append(pattern)
    held.discard("")
    return (_RUN_SECRETS.set(tuple(sorted(held, key=len, reverse=True))),
            _RUN_PASSWORDS.set(tuple(found)))


def reset_run_secrets(token) -> None:
    secrets_token, passwords_token = token
    _RUN_PASSWORDS.reset(passwords_token)
    _RUN_SECRETS.reset(secrets_token)


def scrub_secrets(text):
    """`text` with each of the run's secrets (set_run_secrets), in any
    spelling, replaced by REDACTED; a search over those it may hold
    (_hits: R6E-9)."""
    if not isinstance(text, str) or not text:
        return text
    regex = _secrets_regex(_hits(_RUN_SECRETS.get(), text))
    return regex.sub(REDACTED, text) if regex is not None else text


def has_run_secrets() -> bool:
    """Has the run any secret or password to look for (set_run_secrets)?"""
    return bool(_RUN_SECRETS.get() or _RUN_PASSWORDS.get())


def secret_reach() -> int:
    """How far past a cut text must be read for every secret of the run,
    and the password with white space between its characters, to be found
    whole: twice the longest secret, at _SPELLED_PER_CHARACTER characters
    a character."""
    return 2 * _SPELLED_PER_CHARACTER * max(
        (len(s) for s in _RUN_SECRETS.get()), default=0)


def scrub_for_hash(text):
    """`text` with the run's secrets (scrub_secrets) and its --http-user
    password, wherever password_pattern finds it, replaced by REDACTED:
    for what is hashed and never shown (checks_static.element_identity),
    so that a hash is no offline test of a guess at either."""
    text = scrub_secrets(text)
    if isinstance(text, str) and text:
        for pattern in _RUN_PASSWORDS.get():
            text = pattern.sub(REDACTED, text)
    return text


def holds_secret(text, ignore_case: bool = False) -> bool:
    """Does `text` hold one of the run's secrets, in any spelling? With
    `ignore_case`, in any case too, as a name a parser lowercases holds it
    (R6C-6)."""
    if not isinstance(text, str) or not text:
        return False
    regex = _secrets_regex(_hits(_RUN_SECRETS.get(), text, ignore_case),
                           ignore_case)
    return regex is not None and regex.search(text) is not None


def holds_password(text) -> bool:
    """Does `text` hold the run's --http-user password, in any case and in
    any spelling password_pattern reads?"""
    patterns = _RUN_PASSWORDS.get()
    if not (patterns and isinstance(text, str) and text):
        return False
    return any(p.search(text) for p in patterns)

#: Scheme and authority. The authority ends at the first "/", "?" or "#",
#: as bundle.url_host reads it. Scheme names are capped at 32 characters
#: (real ones are short): an unbounded run would make scanning text that
#: holds long runs of letters — page-controlled error text — quadratic.
_SCHEME = r"[A-Za-z][A-Za-z0-9+.\-]{0,31}://"
_SCHEME_AUTHORITY = re.compile(f"({_SCHEME})([^/?#]*)")
#: A URL inside free text, such as an error message. It runs to the next
#: whitespace or quote; a secret cut short there is caught by the literal
#: pass, which runs first.
_URL_IN_TEXT = re.compile(_SCHEME + r"[^\s\"'<>`]+")
_PARAM_SEPARATORS = re.compile(r"([&;])")


def names(keep) -> frozenset:
    """Parameter names to keep. A single name given as a string is one name,
    not one per character."""
    if not keep:
        return frozenset()
    if isinstance(keep, str):
        return frozenset({keep})
    return frozenset(keep)


#: Literal secrets are a backstop, for a message that quotes a URL in some
#: spelling the URL pattern does not see (escaped, decoded). URLs are
#: handled whole; a literal is replaced wherever it appears, so only strings
#: that look like credentials qualify: at least eight characters and not a
#: plain lowercase word. "fr" or "chromium" as a parameter value would
#: otherwise rewrite ordinary words in the harness's own messages.
_MIN_SECRET = 8
_PLAIN_WORDS = re.compile(r"[a-z]+(?:[-_.][a-z]+)*")


def _looks_secret(s) -> bool:
    return (isinstance(s, str) and len(s) >= _MIN_SECRET
            and not _PLAIN_WORDS.fullmatch(s))


def _kept(name: str, keep) -> bool:
    return bool(keep) and (name in keep
                           or urllib.parse.unquote_plus(name) in keep)


def _redact_params(text: str, keep) -> tuple[str, bool, list[str]]:
    """Replace the value of every parameter in a query or fragment.

    Parameters are separated by "&" or ";" (some servers split on either).
    Returns the new text, whether anything changed, and the replaced values.
    """
    parts = _PARAM_SEPARATORS.split(text)
    changed, values = False, []
    for i in range(0, len(parts), 2):
        item = parts[i]
        if not item:
            continue
        name, eq, value = item.partition("=")
        if eq and not value.strip("=") and _looks_secret(name):
            # Nothing but "=" after a name that looks like a credential: all
            # value, as a padded Base64 token reads (?<token>=, ?<token>==)
            # (R1B-5). An ordinary empty parameter (?q=) keeps its name.
            if _kept(name, keep):
                continue
            parts[i] = REDACTED
            values.append(item)
        elif eq:
            if not value or value == REDACTED or _kept(name, keep):
                continue
            parts[i] = f"{name}={REDACTED}"
            values.append(value)
        else:
            # A parameter with no "=" is all value: ?<token> is a token.
            if item == REDACTED or _kept(item, keep):
                continue
            parts[i] = REDACTED
            values.append(item)
        changed = True
    return "".join(parts), changed, values


#: A fragment that is a client route: "/" or "!/", then its path in
#: printable ASCII, as a browser reports it (percent-encoded), then perhaps
#: a query.
_ROUTE = re.compile(r"(!?/[!-~]*?)(\?.*)?\Z", re.DOTALL)


#: How many times a route's percent escapes are decoded. A path still
#: changing after that many passes is not read as a route at all.
_DECODE_PASSES = 8


def _decoded(text: str) -> str | None:
    """`text` with its percent escapes decoded until none is left, so a
    separator escaped twice (%253D) is seen as one escaped once (R1B-6);
    None when it still changes after _DECODE_PASSES passes."""
    for _ in range(_DECODE_PASSES):
        once = urllib.parse.unquote(text)
        if once == text:
            return text
        text = once
    return None


def _route(fragment: str):
    """(path, query or None) of a fragment that is a client route, or None
    (L39). Not a route when its path, read with its percent escapes
    decoded (_decoded), holds "=", "&", ";", "#" or "?": a token can hide
    there, and a router that decodes the fragment reads "?" as the start of
    a query. Nor when it holds a space, a control character or any
    character outside ASCII: a browser reports those percent-encoded, and a
    recorded URL must stay in printable ASCII for a verifier to read its
    host (bundle.url_host). (The path never holds a literal "?": the first
    one starts the route's query.)"""
    m = _ROUTE.match(fragment)
    if m is None:
        return None
    path, query = m.group(1), m.group(2)
    plain = _decoded(path)
    if plain is None or any(ch in plain for ch in "=&;#?"):
        return None
    return path, (query[1:] if query is not None else None)


def _redact_path_params(path: str, keep, params=None, markup: bool = False
                        ) -> tuple[str, bool, list[str]]:
    """A URL's path with the values of its path parameters replaced, as
    _redact_params replaces a query's: what follows the first ";" in a
    segment (`/shop;jsessionid=…/cart`), where servers put a session or
    a token (L79). The segment's own name is kept. `params` redacts the
    parameters (_redact_params by default; markup's for a URL in markup,
    with `markup`: _split_param).
    """
    if ";" not in path:
        return path, False, []
    redact = params or (lambda text: _redact_params(text, keep))
    segments = re.split(r"([/\\])", path)
    changed, values = False, []
    for i in range(0, len(segments), 2):
        name, semi, rest = _split_param(segments[i], markup)
        if not semi or not rest:
            continue
        rest, done, found = redact(rest)
        if done:
            segments[i] = name + semi + rest
            changed = True
            values += found
    return "".join(segments), changed, values


#: A character reference as markup writes one (&amp;, &#38;, &#x26;).
_CHAR_REF = re.compile(
    r"&(?:#[0-9]{1,10}|#[xX][0-9A-Fa-f]{1,10}|[A-Za-z][A-Za-z0-9]{0,40});")


def _split_param(segment: str, markup: bool) -> tuple[str, str, str]:
    """(name, separator, parameters) of a path segment, split at its first
    ";" (str.partition's shape). In markup, as a browser reads it once
    its character references are decoded (R6AA-3): the ";" that ends one
    is none (`/Q&amp;A/` is "/Q&A/"), but one that names a ";" (&#59;,
    &semi;) is the separator, and so is the ";" after a name HTML does
    not have (&ampx; is no reference in an attribute)."""
    if not markup:
        return segment.partition(";")
    start = 0
    while True:
        semi = segment.find(";", start)
        if semi < 0:
            return segment, "", ""
        amp = segment.rfind("&", start, semi)
        ref = (_CHAR_REF.fullmatch(segment, amp, semi + 1) if amp >= 0
               else None)
        text = _ref_text(ref.group(0)) if ref is not None else None
        if text is None:
            return segment[:semi], ";", segment[semi + 1:]
        if text == ";":
            return segment[:amp], ref.group(0), segment[semi + 1:]
        start = semi + 1


def _ref_text(ref: str) -> str | None:
    """What `ref`, a character reference (_CHAR_REF), stands for, or None
    where HTML has no reference of that name."""
    if ref[1:2] == "#":
        return html.unescape(ref)
    return _HTML5_REFERENCES.get(ref[1:])


def _redact_fragment(fragment: str, keep) -> tuple[str, bool, list[str]]:
    """A fragment as _redact_params treats a query, except that a client
    route keeps its path (_route)."""
    route = _route(fragment)
    if route is None:
        return _redact_params(fragment, keep)
    path, query = route
    if query is None:
        return fragment, False, []
    query, changed, values = _redact_params(query, keep)
    return f"{path}?{query}", changed, values


def _split(url: str):
    """(scheme, authority, path, query, fragment); query and fragment are
    None when absent. None for text that is not a hierarchical URL."""
    m = _SCHEME_AUTHORITY.match(url)
    if not m:
        return None
    rest = url[m.end():]
    path, query, fragment = rest, None, None
    hash_at = rest.find("#")
    if hash_at >= 0:
        path, fragment = rest[:hash_at], rest[hash_at + 1:]
    q_at = path.find("?")
    if q_at >= 0:
        path, query = path[:q_at], path[q_at + 1:]
    return m.group(1), m.group(2), path, query, fragment


def redact_url(url, keep=()) -> tuple:
    """`url` as it may be recorded, and the set of what was removed:
    "userinfo", "path" (path parameters' values replaced: L79), "query"
    (values replaced), "fragment" (values replaced).

    `keep` names parameters whose values are kept verbatim. Text that is not
    written scheme://… comes back unchanged when it holds no "@", "?" or "#"
    (about:blank), and as REDACTED otherwise.
    """
    if not isinstance(url, str):
        return url, frozenset()
    parts = _split(url)
    if parts is None:
        # Not written scheme://…: nothing a browser reports or the harness
        # fetches. Kept only when it cannot hold a secret (about:blank).
        held = {"userinfo": "@", "query": "?", "fragment": "#"}
        what = frozenset(k for k, ch in held.items() if ch in url)
        return (REDACTED, what) if what else (url, frozenset())
    scheme, authority, path, query, fragment = parts
    keep = names(keep)
    removed = set()
    if "@" in authority:
        if "\\" in authority:
            # Parsers disagree about where such an authority ends, and so
            # about which part is the password. Keep none of it. A verifier
            # reads no host from this URL, and reads none from the result.
            return REDACTED, frozenset({"userinfo"})
        # Everything before the last "@" is userinfo — the reading of
        # browsers and of bundle.url_host — so the host is unchanged.
        authority = authority.rpartition("@")[2]
        removed.add("userinfo")
    path, changed, _ = _redact_path_params(path, keep)
    if changed:
        removed.add("path")
    out = scheme + authority + path
    if query is not None:
        query, changed, _ = _redact_params(query, keep)
        if changed:
            removed.add("query")
        out += "?" + query
    if fragment is not None:
        fragment, changed, _ = _redact_fragment(fragment, keep)
        if changed:
            removed.add("fragment")
        out += "#" + fragment
    return out, frozenset(removed)


def secret_values(url, keep=()) -> set[str]:
    """The secrets redact_url removes from `url` that look like credentials
    (_looks_secret): the userinfo and its password, and the parameter
    values it replaces, with their decoded forms. Used to scrub messages
    that may quote the URL in some other spelling."""
    out: set[str] = set()
    if not isinstance(url, str):
        return out
    parts = _split(url)
    if parts is None:
        return out
    _, authority, path, query, fragment = parts
    keep = names(keep)
    candidates = []
    if "@" in authority:
        userinfo = authority.rpartition("@")[0]
        password = userinfo.partition(":")[2]
        candidates += [userinfo, password, urllib.parse.unquote(password)]
    for text, redact in ((path, _redact_path_params),
                         (query, _redact_params),
                         (fragment, _redact_fragment)):
        if text is not None:
            for value in redact(text, keep)[2]:
                candidates += [value, urllib.parse.unquote_plus(value)]
    return {s for s in candidates if _looks_secret(s)}


#: A home directory in a local path: /home/<user>, /Users/<user>, /root,
#: C:\\Users\\<user>, followed by a separator (a path into it), the user
#: name up to four words long (`/Users/John Smith/`). Not one inside a URL
#: (`example.com/home/x`), nor a bare `/home/products`.
_USER = r"[^/\\\s'\"<>`]+(?: [^/\\\s'\"<>`]+){0,3}"
_HOME_POSIX = re.compile(r"(?<![\w.%-])(?:/(?:home|Users)/" + _USER
                         + r"(?=/)|/root(?=[/\s'\"<>`]|$))")
_HOME_WINDOWS = re.compile(r"(?<![\w.%-])[A-Za-z]:[\\/](?:Users|Documents and Settings)"
                           r"[\\/]" + _USER + r"(?=[\\/])", re.I)


def _outside_urls(pattern: re.Pattern, text: str) -> str:
    """pattern replaced with `~` wherever it starts outside a URL other
    than file://."""
    spans = [m.span() for m in _URL_IN_TEXT.finditer(text)
             if m.group(0)[:7].lower() != "file://"]

    def one(m: re.Match) -> str:
        inside = any(a <= m.start() < b for a, b in spans)
        return m.group(0) if inside else "~"
    return pattern.sub(one, text)


def redact_local_paths(text: str) -> str:
    """A home directory in free text replaced with `~`: a browser that
    fails to launch quotes its executable's path, and the text may be
    recorded in a bundle that cannot be redacted once signed. The
    operator's own home directory wherever it appears; another one only
    where a path runs into it (/home/<user>/…). Not inside a URL other
    than file:// (`http://[::1]/home/a/b` is a site's path); a path that
    is not in a URL cannot be told from a local one, so a site path
    quoted bare (`/home/products/shoes`) is scrubbed too."""
    if not isinstance(text, str) or not text:
        return text
    homes = {h for h in (os.environ.get("HOME"), os.environ.get("USERPROFILE"),
                         os.path.expanduser("~"))
             if h and len(h.strip("/\\")) > 1}
    for h in sorted(homes, key=len, reverse=True):
        text = _outside_urls(re.compile(r"(?<![\w.%-])" + re.escape(h.rstrip("/\\"))
                                        + r"(?=[/\\\s'\"<>`]|$)"), text)
    text = _outside_urls(_HOME_WINDOWS, text)
    return _outside_urls(_HOME_POSIX, text)


def redact_text(text, secrets=(), keep=()):
    """Free text (an error message, a note) as it may be printed or
    recorded: every given secret that looks like a credential replaced with
    REDACTED, in any spelling (_secret_char), then every URL in it passed
    through redact_url, then any home directory in a local path replaced
    with `~`. The secrets go first, whole: a URL pass that stopped at a
    quote inside a token would leave the rest of it behind, no longer
    matching."""
    if not isinstance(text, str) or not text:
        return text
    keep = names(keep)
    out = text
    regex = _secrets_regex(_hits(tuple(sorted(
        {s for s in secrets or () if _looks_secret(s)}, key=len,
        reverse=True)), text))
    if regex is not None:
        out = regex.sub(REDACTED, out)
    out = _URL_IN_TEXT.sub(lambda m: redact_url(m.group(0), keep)[0], out)
    return redact_local_paths(out)


#: The attributes whose values are URLs (HTML, SVG, microdata), and those
#: that hold several: srcset's are separated by commas, each with its
#: descriptor; ping's by spaces. A meta refresh's `content` names one
#: after "url=".
_URL_ATTRS = ("href", "src", "action", "formaction", "poster", "data",
              "cite", "background", "longdesc", "ping", "srcset",
              "imagesrcset", "xlink:href", "manifest", "codebase", "archive",
              "itemid", "usemap", "content")
_ATTR_VALUE = re.compile(
    r"(?<![\w:-])(" + "|".join(re.escape(a) for a in _URL_ATTRS) + r")"
    r"(\s*=\s*)(?:\"([^\"]*)(\"|$)|'([^']*)('|$)|([^\s\"'>]+))",
    re.IGNORECASE)
#: A meta refresh's URL: everything after "url=", as HTML reads it (a
#: quoted one ends at its quote).
_REFRESH_URL = re.compile(r"(\burl\s*=\s*)(.+)", re.IGNORECASE | re.DOTALL)
#: A fragment kept whole in quoted markup: an element's id, as a skip link
#: or an in-page link names it. One holding "=", "&", ";" or "?", or longer
#: than this, is read as parameters (#access_token=…); a client route
#: (#/path, #!/path) keeps its path and has its query read so, as a
#: recorded URL's has (R5D-9).
_PLAIN_FRAGMENT = re.compile(r"[^=&;?]{0,64}")
#: The schemes WHATWG's URL parser calls special: after one, any run of
#: "/" or "\" starts the authority, and a "\" ends it ("https:\\u:p@h",
#: "https:u:p@h" and "https:/\t/u:p@h" are all https://u:p@h to a
#: browser: R5C-4).
_SPECIAL = frozenset(("http", "https", "ws", "wss", "ftp", "file"))
_SCHEME_NAME = re.compile(r"([A-Za-z][A-Za-z0-9+.\-]{0,31}):")
#: What a browser removes from a URL before it reads it: ASCII tabs and
#: line breaks anywhere.
_TAB_NEWLINE = re.compile(r"[\t\n\r]")
#: Parameters in markup: a serialized "&" is "&amp;", which splits as one
#: separator, not as "&" and ";" (R5C-13).
_MARKUP_SEPARATORS = re.compile(r"(&amp;|&|;)")
#: A query value inside code (a javascript: URL, a data: URL's text):
#: after "?", "&" or ";", a name and "=", up to the next separator,
#: quote, bracket or space (R5D-2).
_CODE_PARAM = re.compile(r"(?<=[?&;])([A-Za-z0-9_.~%\[\]\-]{1,100}=)"
                         r"([^&;#'\"\s<>(){}\[\],\\`]+)")
#: User name and password after "//" inside code.
_CODE_USERINFO = re.compile(r"(?<=[/\\]{2})[^/\\\s'\"<>@`]{1,200}@")


def _redact_markup_params(text: str) -> str:
    """A query's (or a fragment's) parameter values as markup holds them,
    replaced with REDACTED, as _redact_params replaces them."""
    parts = _MARKUP_SEPARATORS.split(text)
    for i in range(0, len(parts), 2):
        if parts[i]:
            parts[i] = _redact_params(parts[i], ())[0]
    return "".join(parts)


def _redact_markup_fragment(fragment: str) -> str:
    """A fragment in markup, read as a recorded URL's is: with its percent
    escapes decoded (_decoded) before it is judged, so an escaped "=" or
    "?" (#access_token%3D…, #/route%3Ftoken%3D…) is a separator too
    (R5E-9). A client route keeps its path; an element's id is kept."""
    plain = _decoded(fragment.replace("&amp;", "&"))
    if plain is None:
        return REDACTED
    if fragment[:1] == "/" or fragment[:2] == "!/":
        path, q, query = fragment.partition("?")
        if q:
            plain_path = _decoded(path)
            if plain_path is not None and not any(
                    ch in plain_path for ch in "=&;#?"):
                return path + q + _redact_markup_params(query)
        elif not any(ch in plain for ch in "=&;#?"):
            return fragment
        return _redact_markup_params(fragment)
    if _PLAIN_FRAGMENT.fullmatch(fragment) and \
            _PLAIN_FRAGMENT.fullmatch(plain):
        return fragment
    return _redact_markup_params(fragment)


def _redact_code(value: str) -> str:
    """A javascript: or data: value with the query values written in it,
    and any user name and password after "//", replaced (R5D-2)."""
    value = _CODE_USERINFO.sub("", value)
    return _CODE_PARAM.sub(lambda m: m.group(1) + REDACTED, value)


def _redact_one(url: str) -> str:
    """One URL from markup a run records (an attribute value, or a URL in
    text), as the browser reads it, with its user name and password
    removed and its query values, its path parameters' (L79, R6AA-3), and
    a fragment that holds parameters, replaced with REDACTED (R5B-5): an
    element's id after "#" is kept, and a client route keeps its path. The
    authority is found as a browser finds it: after a special scheme and
    any slashes or backslashes, or after "//" or "\\\\" in a relative URL
    (R5C-4, R5D-2); tabs and line
    breaks inside are ignored, as a browser ignores them. A javascript: or
    data: value is code or content: the query values and credentials
    written in it are replaced (_redact_code). Unchanged when nothing in it
    needs redacting."""
    lead = url[:len(url) - len(url.lstrip())]
    body = url.strip()
    trail = url[len(lead) + len(body):]
    clean = _TAB_NEWLINE.sub("", body)
    m = _SCHEME_NAME.match(clean)
    scheme = m.group(1).lower() if m else None
    if scheme in ("javascript", "data", "vbscript"):
        out = _redact_code(clean)
        return url if out == clean else lead + out + trail
    if scheme is not None and scheme not in _SPECIAL and \
            not clean[m.end():].startswith("//") and len(scheme) == 1:
        scheme = None            # "c:\\x" is a path, not a scheme
    prefix, rest = (clean[:m.end()], clean[m.end():]) if scheme else ("", clean)
    if scheme in _SPECIAL:
        slashes = re.match(r"[/\\]*", rest).group(0)
        authority_follows = True
    elif scheme is not None:
        slashes = "//" if rest.startswith("//") else ""
        authority_follows = bool(slashes)
    else:
        slashes = re.match(r"[/\\]*", rest).group(0)
        authority_follows = len(slashes) >= 2
    out = prefix
    if authority_follows:
        after = rest[len(slashes):]
        end = re.search(r"[/\\?#]", after)
        authority = after[:end.start()] if end else after
        if "@" in authority:
            authority = authority.rpartition("@")[2]
        out += slashes + authority
        rest = after[len(after[:end.start()] if end else after):]
    path, h, fragment = rest.partition("#")
    path, q, query = path.partition("?")
    out += _redact_path_params(
        path, (), lambda text: (_redact_markup_params(text),
                                _redact_markup_params(text) != text,
                                []), markup=True)[0]
    if q:
        out += "?" + _redact_markup_params(query)
    if h:
        out += "#" + _redact_markup_fragment(fragment)
    return url if out == clean else lead + out + trail


def _srcset(value: str) -> str:
    """A srcset's URLs redacted, its candidates read as HTML reads them: a
    URL runs to the next white space, and only commas at its end, or
    after its descriptors, separate candidates (a URL may hold commas:
    "?fields=a,b", R5C-4)."""
    out, i, n = [], 0, len(value)
    while i < n:
        j = i
        while j < n and (value[j].isspace() or value[j] == ","):
            j += 1
        out.append(value[i:j])
        if j >= n:
            break
        k = j
        while k < n and not value[k].isspace():
            k += 1
        url = value[j:k]
        bare = url.rstrip(",")
        out.append(_redact_one(bare) + url[len(bare):])
        i = k
        if bare != url:
            continue
        d = k
        while d < n and value[d] != ",":
            d += 1
        out.append(value[k:d])
        i = d
    return "".join(out)


def _refresh(value: str) -> str:
    """A meta refresh's content with the URL after "url=" redacted, read
    to the end of the value (or to its closing quote)."""
    def one(m: re.Match) -> str:
        rest = m.group(2)
        if rest[:1] in ("'", '"'):
            close = rest.find(rest[0], 1)
            if close > 0:
                return (m.group(1) + rest[0] + _redact_one(rest[1:close])
                        + rest[close:])
        return m.group(1) + _redact_one(rest)
    return _REFRESH_URL.sub(one, value, count=1)


def _redact_value(attr: str, value: str) -> str:
    attr = attr.lower()
    if attr in ("srcset", "imagesrcset"):
        return _srcset(value)
    if attr == "ping":
        return " ".join(_redact_one(u) if u else u for u in value.split(" "))
    if attr == "content":
        return _refresh(value)
    return _redact_one(value)


#: A URL written whole in text: a scheme and "//", or a special scheme
#: and any slashes or backslashes ("https:\\host", R5C-4), or none before
#: a user name ("https:user:pass@host", which a browser reads as
#: https://user:pass@host: R5E-14).
_URL_IN_MARKUP = re.compile(
    r"(?<![A-Za-z0-9+.\-])(?:" + _SCHEME + r"|(?:https?|wss?|ftp):"
    r"(?:[/\\]+|(?=[^\s\"'<>`/\\@]{1,200}@)))"
    r"[^\s\"'<>`]+", re.IGNORECASE)


def redact_markup(text):
    """Markup a run records (a finding's snippet or message) with the URLs
    in it as a recorded URL has them (_redact_one): no user name or
    password, and every query value and path parameter's value replaced
    with REDACTED, as are fragments that hold parameters; an element's id
    after "#" is kept, which is what a skip link names. A page's markup
    can hold a presigned image address or a session's token in a link,
    and a signed bundle cannot be redacted afterwards (R5B-5). URLs in the
    attributes HTML and SVG define for them, and any URL written whole, in
    any text. Then the run's own secrets (set_run_secrets), wherever the
    text holds them."""
    if not isinstance(text, str) or not text:
        return text
    # Nothing to redact without one of these: a query, a fragment, a user
    # name, or a path parameter (R6AA-1).
    if not any(ch in text for ch in "?#@;"):
        return scrub_secrets(text)

    def attr(m: re.Match) -> str:
        name, eq = m.group(1), m.group(2)
        if m.group(3) is not None:
            return f'{name}{eq}"{_redact_value(name, m.group(3))}{m.group(4)}'
        if m.group(5) is not None:
            return f"{name}{eq}'{_redact_value(name, m.group(5))}{m.group(6)}"
        return f"{name}{eq}{_redact_value(name, m.group(7))}"
    out = _ATTR_VALUE.sub(attr, text)
    out = _URL_IN_MARKUP.sub(lambda m: _redact_one(m.group(0)), out)
    return scrub_secrets(out)


#: Unicode categories never printed as they are: controls, format
#: characters (bidi overrides and isolates, zero-width marks, the soft
#: hyphen, tag characters), line and paragraph separators, surrogates (a
#: name's undecodable bytes), private-use and unassigned code points.
_UNSHOWN = frozenset(("Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"))
#: …but for the zero-width non-joiner and joiner, which Persian, the
#: scripts of India and emoji need (R4I-6). They cannot reorder text or
#: start a line, but they are invisible: a name with one prints like the
#: name without it (R5A-16, L89).
_SHOWN_FORMAT = frozenset((chr(0x200C), chr(0x200D)))


def printable(text, backslash: bool = False) -> str:
    """`text` as a console may show it: every character of those
    categories escaped as \\uXXXX (\\UXXXXXXXX past the BMP), so text from a
    file or a bundle cannot start a line of its own, reorder or hide what
    is printed, or rewrite the terminal. With `backslash`, a backslash is
    escaped too, so the escapes cannot be confused with text that spells
    one (R4C-7)."""
    out = []
    for ch in str(text):
        if ch == "\\" and backslash:
            out.append("\\\\")
        elif unicodedata.category(ch) in _UNSHOWN and \
                ch not in _SHOWN_FORMAT:
            n = ord(ch)
            out.append(f"\\u{n:04x}" if n <= 0xFFFF else f"\\U{n:08x}")
        else:
            out.append(ch)
    return "".join(out)


#: Text a console shows as it is: printable ASCII, line breaks and tabs.
_PLAIN_CONSOLE = re.compile(r"[\x20-\x7e\n\t]*\Z")


def console_text(text) -> str:
    """`text` as printable() shows it, line breaks and tabs kept."""
    text = str(text)
    if _PLAIN_CONSOLE.match(text):
        return text
    return "".join(ch if ch in "\n\t" else printable(ch) for ch in text)


#: What makes a CI runner read a line as a command (R4I-2, R5A-2):
#: GitHub's "::" at the start of a line, after any white space (its runner
#: trims every Unicode space first), and "##" anywhere in a line: GitHub's
#: older "##[command]", Azure Pipelines' "##vso[…]" and TeamCity's
#: "##teamcity[…]" are found wherever they appear.
_COLON, _HASH = ":", "#"
_ESCAPED_COLON, _ESCAPED_HASH = "\\u003a", "\\u0023"


class _EscapingStream:
    """A console stream that writes what console_text() shows, with every
    second "#" of "##" escaped wherever it is, and the second ":" of a line
    that would start "::" after any white space: no file's name, server's
    or page's words can make a line a CI runner reads as a command, also
    when they arrive in pieces (R4I-2, R5A-2)."""

    def __init__(self, stream):
        self._stream = stream
        #: The line so far: "" at its start, "blank" while only white
        #: space, ":" when one colon follows that, "text" after anything
        #: else.
        self._line = ""
        #: Whether the last character written was an unescaped "#".
        self._hash = False

    def write(self, text) -> int:
        self._stream.write(self._unmarked(console_text(text)))
        return len(text)

    def _unmarked(self, text: str) -> str:
        if not text:
            return text
        out = []
        for part in _SPLIT.split(text):
            if not part:
                continue
            if part == "\n":
                self._line, self._hash = "", False
                out.append(part)
                continue
            if part[0] == _HASH and self._hash:
                part = _ESCAPED_HASH + part[1:]      # "#" then "#…" (R5A-2)
            part = _HASHES.sub(lambda m: _escape_hashes(m.group(0)), part)
            self._hash = part.endswith(_HASH)
            if self._line != "text":
                part = self._line_start(part)
            out.append(part)
        return "".join(out)

    def _line_start(self, part: str) -> str:
        """`part`, the next piece of a line still at its start: its "::"
        escaped if it starts one, the line's state updated."""
        i = 0
        while i < len(part):
            ch = part[i]
            if self._line in ("", "blank"):
                if ch.isspace():
                    self._line = "blank"
                elif ch == _COLON:
                    self._line = _COLON
                else:
                    self._line = "text"
                    break
            else:                                    # one ":" so far
                if ch == _COLON:
                    part = part[:i] + _ESCAPED_COLON + part[i + 1:]
                self._line = "text"
                break
            i += 1
        return part

    def writelines(self, lines) -> None:
        for line in lines:
            self.write(line)

    def __getattr__(self, name):
        return getattr(self._stream, name)


#: Lines, and runs of "#" within them.
_SPLIT = re.compile(r"(\n)")
_HASHES = re.compile(r"##+")


def _escape_hashes(run: str) -> str:
    """A run of two or more "#", every one after the first escaped."""
    return _HASH + _ESCAPED_HASH * (len(run) - 1)


@contextlib.contextmanager
def escaped_console():
    """While it lasts, everything a command prints is escaped as
    console_text() escapes it, every "##" has its second mark escaped, and
    so does a line that would start "::" after white space: a file's name,
    a server's or a page's words quoted in an error, cannot rewrite the
    terminal, reorder or hide a line, or make one that a CI runner reads
    as a command, whichever line prints it (R4G-5, R4I-2, R5A-2)."""
    out, err = sys.stdout, sys.stderr
    for stream in (out, err):
        # A console whose encoding lacks a character ("→" on cp1252, which
        # Windows uses for redirected output) shows it escaped rather than
        # stopping the command with a traceback (R5B-12).
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(errors="backslashreplace")
            except (ValueError, OSError, TypeError):
                pass
    if out is not None:
        sys.stdout = _EscapingStream(out)
    if err is not None:
        sys.stderr = _EscapingStream(err)
    try:
        yield
    finally:
        sys.stdout, sys.stderr = out, err


def run_escaped(main, argv) -> int:
    """main(argv) inside escaped_console(), its output flushed before the
    status is returned. When whoever reads the output stops reading
    (`bellbriar-evidence inspect b.json | head`), the command ends with
    status 2, that of a command that could not finish, and no traceback:
    its output is pointed at the null device, so the flush at exit cannot
    fail again (R5D-15). Files it wrote before then stay."""
    try:
        with escaped_console():
            status = main(argv)
            sys.stdout.flush()
        return status
    except BrokenPipeError:
        try:
            devnull = os.open(os.devnull, os.O_WRONLY)
            try:
                os.dup2(devnull, sys.stdout.fileno())
            finally:
                os.close(devnull)
        except (OSError, ValueError, AttributeError):
            pass
        return 2
