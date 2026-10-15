"""Decode a page's bytes as Chromium 141 decodes them.

The order, as measured against Chromium 141 (document.characterSet, over
HTTP and from local files):

1. a byte-order mark (UTF-8, UTF-16LE, UTF-16BE): certain;
2. the charset the transport declares (HTTP Content-Type), when it names an
   encoding a browser supports: certain;
3. the first `<meta charset>`, or `<meta http-equiv="Content-Type"
   content="...charset=...">`, that names one, found the way Chromium's
   meta-charset scan finds it (meta_charset): with a tokenizer, so markup
   inside a comment, an attribute value, <script>, <style>, <title> or
   another element read as text is not a <meta>; anywhere while only
   head-section tags have been seen (a long head still counts), and
   otherwise only within the first 1024 bytes. A meta in the body, in a
   <template> or <svg> past that point is ignored, as Chromium ignores it;
4. an XML declaration's encoding (`<?xml ... encoding="...">` at the very
   start);
5. for a local file, UTF-8 when its first 256 KiB read as UTF-8: all of
   their non-ASCII bytes, or most of them among at least ten UTF-8
   characters (Chromium's detector is statistical; this follows what it was
   measured to do, and errs on a page with fewer UTF-8 characters and stray
   bytes). Chromium detects UTF-8 in files, never on the web: a page served
   without a charset decodes as windows-1252 however UTF-8 its bytes are;
6. windows-1252, the default for most locales.

Labels are the Encoding Standard's, exactly (encodings_data.py, generated
from the standard): `latin1` and `us-ascii` mean windows-1252, `x-sjis`
Shift_JIS; a label no browser knows (utf-7, utf-32, base64, ebcdic) is not
an encoding. Single-byte encodings decode by the standard's indexes, which
Python's codecs do not always match (windows-1252 maps 0x81 to U+0081).

Chromium also guesses legacy encodings (Shift_JIS, GBK, windows-1257, ...)
from the text of a page that declares none; this module does not, so such
a page decodes as windows-1252 here and its text is garbled. Python's
ISO-2022-JP decoder does not resynchronise after a malformed byte as
Chromium's does, so a broken ISO-2022-JP page can lose the markup after the
fault.
"""
from __future__ import annotations

import codecs
import re
from dataclasses import dataclass

from .encodings_data import LABELS, SINGLE_BYTE

_ASCII_WS = b"\t\n\x0c\r "
_ASCII_WS_STR = "\t\n\x0c\r "

#: Python codecs for the multi-byte encodings, as close to the standard's
#: decoders as Python has: its GBK decoder is gb18030's, its Big5 includes
#: HKSCS, its Shift_JIS and EUC-KR are Microsoft's supersets.
_CODECS = {
    "UTF-8": "utf-8", "UTF-16BE": "utf-16-be", "UTF-16LE": "utf-16-le",
    "GBK": "gb18030", "gb18030": "gb18030", "Big5": "big5hkscs",
    "EUC-JP": "euc_jp", "ISO-2022-JP": "iso2022_jp", "Shift_JIS": "cp932",
    "EUC-KR": "cp949",
}
_UTF16 = ("UTF-16BE", "UTF-16LE")
_CHARMAPS: dict[str, str] = {}


@dataclass(frozen=True)
class Decoded:
    """A page's text and how its encoding was chosen."""
    text: str
    encoding: str          # the Encoding Standard's name, e.g. "windows-1252"
    confidence: str        # "certain" or "tentative"
    source: str            # bom, transport, meta, xml-declaration,
                           # utf-8-detected or default


def get_encoding(label) -> str | None:
    """The Encoding Standard's "get an encoding": the encoding a label
    names, or None. Leading and trailing ASCII whitespace is ignored and
    case does not matter; nothing else is forgiven."""
    if isinstance(label, (bytes, bytearray)):
        label = bytes(label).decode("latin-1")
    if not isinstance(label, str) or not label.isascii():
        return None             # str.lower() would fold U+212A to "k"
    return LABELS.get(label.strip(_ASCII_WS_STR).lower())


def bom(body: bytes) -> tuple[str | None, int]:
    """BOM sniffing: the encoding a byte-order mark names, and its length."""
    if body.startswith(b"\xef\xbb\xbf"):
        return "UTF-8", 3
    if body.startswith(b"\xfe\xff"):
        return "UTF-16BE", 2
    if body.startswith(b"\xff\xfe"):
        return "UTF-16LE", 2
    return None, 0


def decode(body: bytes, encoding: str) -> str:
    """Decode with the standard's decoder for `encoding` (a name from
    get_encoding), replacing malformed input with U+FFFD."""
    if encoding == "replacement":
        return chr(0xFFFD) if body else ""
    if encoding == "x-user-defined":
        return "".join(chr(b) if b < 0x80 else chr(0xF780 + b - 0x80)
                       for b in body)
    if encoding in SINGLE_BYTE:
        table = _CHARMAPS.get(encoding)
        if table is None:
            table = _CHARMAPS[encoding] = (
                "".join(map(chr, range(128))) + SINGLE_BYTE[encoding])
        return codecs.charmap_decode(body, "replace", table)[0]
    return body.decode(_CODECS[encoding], errors="replace")


def _ascii_lower(text: str) -> str:
    return text.translate(_LOWER)


_LOWER = {c: c + 32 for c in range(0x41, 0x5B)}


def _extract_charset(value: str) -> str:
    """The charset a <meta content> names, as Chromium's ExtractCharset
    reads it ("" for none): after each "charset" (any case), control
    characters and spaces, "=", control characters and spaces; then a value
    in matching quotes (none if the quote never closes), or up to a space,
    control character, quote or ";"."""
    n = len(value)
    low = _ascii_lower(value)
    pos = 0
    while True:
        pos = low.find("charset", pos)
        if pos < 0:
            return ""
        pos += 7
        while pos < n and value[pos] <= " ":
            pos += 1
        if pos >= n or value[pos] != "=":
            continue
        pos += 1
        while pos < n and value[pos] <= " ":
            pos += 1
        quote = value[pos] if pos < n and value[pos] in "\"'" else ""
        pos += len(quote)
        if pos >= n:
            return ""
        end = pos
        if quote:
            end = value.find(quote, pos)
            if end < 0:
                return ""               # the quote never closes
        else:
            while end < n and value[end] > " " and value[end] not in "\"';":
                end += 1
        return value[pos:end]


def _attr_text(raw: bytes) -> str:
    """An attribute value as the tokenizer gives it: character references
    decoded (`&#x6b;oi8-r` is koi8-r). Bytes are read as Latin-1, as the
    scan reads them: every label is ASCII."""
    text = raw.decode("latin-1")
    if "&" in text:
        import html
        text = html.unescape(text)
    return text


def meta_encoding(attrs) -> str | None:
    """The encoding a <meta>'s attributes (lowercased names, raw values, in
    order, duplicates kept) declare, as Chromium 141 reads them: the last
    `charset` attribute decides; failing one, the last `content` whose
    value names a charset, when an `http-equiv` is "Content-Type" (any
    case). A meta always declares UTF-8 for UTF-16, and windows-1252 for
    x-user-defined."""
    got_pragma = False
    mode = ""
    charset = ""
    for name, raw in attrs:
        if name == b"http-equiv":
            if _ascii_lower(_attr_text(raw)) == "content-type":
                got_pragma = True
        elif name == b"charset":
            charset, mode = _attr_text(raw), "charset"
        elif name == b"content" and mode != "charset":
            found = _extract_charset(_attr_text(raw))
            if found:
                charset, mode = found, "pragma"
    if not (mode == "charset" or (mode == "pragma" and got_pragma)):
        return None
    enc = get_encoding(charset)
    if enc in _UTF16:
        return "UTF-8"
    return "windows-1252" if enc == "x-user-defined" else enc


# -- Chromium's meta-charset scan ----------------------------------------
#
# Chromium does not run HTML's spec prescan. It runs its tokenizer over the
# bytes read as Latin-1 (Blink's HTMLMetaCharsetParser) and takes the first
# <meta> that names a valid encoding. It stops once it has read 1024 bytes
# after a tag that cannot be in the head section: one other than these
# (or the start tags <html> and <head>). Its tokenizer has no tree builder
# and no document, so it knows nothing of foreign content (an <svg> <title>
# or <style> is read as text), and runs with scripting off (<noscript>
# content is markup; <noembed> content is text). Every rule here is
# measured against Chromium 141 (tests/test_encoding.py).

_IN_HEAD = frozenset((b"script", b"noscript", b"style", b"link", b"meta",
                      b"object", b"title", b"base"))
_RCDATA_OR_RAWTEXT = frozenset((b"title", b"textarea", b"style", b"iframe",
                                b"xmp", b"noembed", b"noframes"))
#: The scan reads this many bytes whatever it meets.
SCAN_UNCONDITIONALLY = 1024
_MARKUP = re.compile(rb"<[A-Za-z!/?]")
_NAME_END = re.compile(rb"[\t\n\x0c\r />]")
_COMMENT_END = re.compile(rb"--!?>")
_ATTR_NAME_END = b"\t\n\x0c\r />="
_VALUE_END = b"\t\n\x0c\r >"


def _read_tag(data: bytes, pos: int):
    """The tag whose name starts at `pos`: (lowercased name, [(lowercased
    attribute name, raw value)], position after its `>`), or None when the
    bytes end inside it (the tokenizer drops such a tag)."""
    n = len(data)
    m = _NAME_END.search(data, pos)
    if m is None:
        return None
    name = data[pos:m.start()].lower()          # ASCII letters only
    pos = m.start()
    attrs = []
    while True:
        while pos < n and data[pos] in _ASCII_WS:
            pos += 1
        if pos >= n:
            return None
        c = data[pos]
        if c == 0x3E:                                           # >
            return name, attrs, pos + 1
        if c == 0x2F:                                           # /
            pos += 1
            if pos >= n:
                return None
            if data[pos] == 0x3E:
                return name, attrs, pos + 1
            continue
        start = pos
        pos += 1                        # a name may begin with "="
        while pos < n and data[pos] not in _ATTR_NAME_END:
            pos += 1
        attr = data[start:pos].lower()
        while pos < n and data[pos] in _ASCII_WS:
            pos += 1
        if pos >= n:
            return None
        if data[pos] != 0x3D:                                   # no value
            attrs.append((attr, b""))
            continue
        pos += 1
        while pos < n and data[pos] in _ASCII_WS:
            pos += 1
        if pos >= n:
            return None
        c = data[pos]
        if c in (0x22, 0x27):
            close = data.find(bytes((c,)), pos + 1)
            if close < 0:
                return None
            attrs.append((attr, data[pos + 1:close]))
            pos = close + 1
        elif c == 0x3E:
            attrs.append((attr, b""))
            return name, attrs, pos + 1
        else:
            start = pos
            while pos < n and data[pos] not in _VALUE_END:
                pos += 1
            if pos >= n:
                return None
            attrs.append((attr, data[start:pos]))


def _text_end(data: bytes, pos: int, name: bytes) -> int:
    """Where the text content of a <title>, <style> or kin that starts at
    `pos` ends: at its end tag (`</name` and then a space, `/` or `>`), or
    at the end of the bytes."""
    close = re.compile(rb"</" + re.escape(name) + rb"[\t\n\x0c\r />]", re.I)
    m = close.search(data, pos)
    return m.start() if m else len(data)


_SCRIPT_CLOSE = re.compile(rb"</script[\t\n\x0c\r />]", re.I)
_SCRIPT_OPEN = re.compile(rb"<script[\t\n\x0c\r />]", re.I)
_ESCAPED_STOP = re.compile(rb"-->|<")


def _script_end(data: bytes, pos: int) -> int:
    """Where a <script>'s text, starting at `pos`, ends: its end tag, read
    with the tokenizer's script-data states. Inside `<!--` the text is
    escaped, and an escaped `<script>` (double escaping) hides the next
    `</script>`; `-->` returns to plain script data."""
    n = len(data)
    state = "data"
    while pos < n:
        if state == "data":
            i = data.find(b"<", pos)
            if i < 0:
                return n
            if _SCRIPT_CLOSE.match(data, i):
                return i
            if data.startswith(b"<!--", i):
                # From the dashes of "<!--", so "<!-->" ends at once.
                state, pos = "escaped", i + 2
                continue
            pos = i + 1
        else:
            # escaped / double: the next "-->" or "<" that matters
            m = _ESCAPED_STOP.search(data, pos)
            if m is None:
                return n
            i = m.start()
            if data.startswith(b"-->", i):
                state, pos = "data", i + 3
                continue
            if state == "escaped":
                if _SCRIPT_CLOSE.match(data, i):
                    return i
                if _SCRIPT_OPEN.match(data, i):
                    state = "double"
                pos = i + 1
            else:
                if _SCRIPT_CLOSE.match(data, i):
                    state = "escaped"
                pos = i + 1
    return n


def meta_charset(body: bytes) -> str | None:
    """The encoding Chromium's meta-charset scan finds in `body`, or None
    (see above): the first <meta> that names a valid encoding, while the
    scan runs."""
    n = len(body)
    pos = 0
    in_head = True
    while True:
        m = _MARKUP.search(body, pos)
        if m is None:
            return None                         # text to the end
        i = m.start()
        if i > pos and not in_head and i >= SCAN_UNCONDITIONALLY:
            return None                         # a run of text ended past it
        kind = body[i + 1]
        if kind == 0x21:                                        # <!
            if body.startswith(b"<!--", i):
                j = i + 4
                if body.startswith(b">", j):
                    end = j + 1                                 # <!-->
                elif body.startswith(b"->", j):
                    end = j + 2                                 # <!--->
                else:
                    c = _COMMENT_END.search(body, j)
                    end = c.end() if c else n
            else:                               # DOCTYPE, CDATA, bogus
                c = body.find(b">", i + 2)
                end = n if c < 0 else c + 1
        elif kind == 0x3F:                                      # <?
            c = body.find(b">", i + 2)
            end = n if c < 0 else c + 1
        elif kind == 0x2F:                                      # </
            nxt = body[i + 2:i + 3]
            if nxt == b">":
                pos = i + 3                     # "</>" makes no token
                continue
            if not nxt:
                return None
            if nxt.isalpha():
                tag = _read_tag(body, i + 2)
                if tag is None:
                    return None
                name, _attrs, end = tag
                if name not in _IN_HEAD:
                    in_head = False
            else:                               # "</ x>": a bogus comment
                c = body.find(b">", i + 2)
                end = n if c < 0 else c + 1
        else:                                                   # a start tag
            tag = _read_tag(body, i + 1)
            if tag is None:
                return None
            name, attrs, end = tag
            if name == b"meta":
                enc = meta_encoding(attrs)
                if enc is not None:
                    return enc
            if name not in _IN_HEAD and name not in (b"html", b"head"):
                in_head = False
            if name == b"plaintext":
                return None                     # the rest is text
            if name == b"script" or name in _RCDATA_OR_RAWTEXT:
                if not in_head and end >= SCAN_UNCONDITIONALLY:
                    return None
                text_end = (_script_end(body, end) if name == b"script"
                            else _text_end(body, end, name))
                if (text_end > end and not in_head
                        and text_end >= SCAN_UNCONDITIONALLY):
                    return None
                pos = text_end
                continue
        if not in_head and end >= SCAN_UNCONDITIONALLY:
            return None
        pos = end


def xml_declaration(body: bytes) -> str | None:
    """The encoding an XML declaration at the very start names
    (`<?xml version="1.0" encoding="koi8-r"?>`), as Chromium reads it:
    "encoding" before the declaration's first `>`, then "=" and a quoted
    label, spaces and control characters allowed around the "=". UTF-16
    there means UTF-8."""
    if not body.startswith(b"<?xml"):
        return None
    end = body.find(b">")
    if end < 0:
        return None
    i = body.find(b"encoding", 0, end)
    if i < 0:
        return None
    i += 8
    while i < end and body[i] <= 0x20:
        i += 1
    if i >= end or body[i] != 0x3D:
        return None
    i += 1
    while i < end and body[i] <= 0x20:
        i += 1
    if i >= end or body[i] not in (0x22, 0x27):
        return None
    close = body.find(bytes((body[i],)), i + 1, end)
    if close < 0:
        return None
    label = body[i + 1:close]
    if any(b <= 0x20 for b in label):
        return None
    enc = get_encoding(label)
    return "UTF-8" if enc in _UTF16 else enc


#: How much of a local file Chromium examines to detect UTF-8: the first
#: 256 KiB (measured: a lone é at byte 262,104 makes the file UTF-8, one at
#: 262,184 leaves it windows-1252).
UTF8_DETECTION_BYTES = 256 * 1024
#: Chromium's detector is statistical; measured on a grid of pages, it reads
#: a file as UTF-8 when its non-ASCII bytes are all UTF-8, or when there
#: are at least this many UTF-8 characters and no more bytes that are not
#: (20 accents among 20 stray Latin-1 bytes is UTF-8; 5 among 1 is not).
UTF8_MAJORITY = 10


def _looks_utf8(body: bytes) -> bool:
    head = body[:UTF8_DETECTION_BYTES]
    if head.isascii():
        return False
    text = head.decode("utf-8", errors="surrogateescape")
    if len(body) > len(head):
        # A character cut in two at the window's edge is not an error.
        cut = len(text) - len(text.rstrip("".join(
            chr(c) for c in range(0xDC80, 0xDD00))))
        text = text[:len(text) - min(cut, 3)]
    invalid = sum(1 for ch in text if 0xDC80 <= ord(ch) <= 0xDCFF)
    valid = sum(1 for ch in text if ord(ch) >= 0x80) - invalid
    if invalid == 0:
        return valid > 0
    return valid >= UTF8_MAJORITY and invalid <= valid


def sniff(body: bytes, transport: str | None = None,
          local_file: bool = False, xml: bool = False) -> Decoded:
    """The page's text, decoded as Chromium 141 decodes it (see the module
    docstring). `transport` is the charset the HTTP Content-Type declared,
    if any; `local_file` says the bytes are a file read from disk, where
    Chromium detects UTF-8. An `xml` document (an XHTML file, a page
    served as application/xhtml+xml) is decoded as XML is: no <meta>
    counts, and UTF-8 is the default."""
    enc, skip = bom(body)
    if enc is not None:
        return Decoded(decode(body[skip:], enc), enc, "certain", "bom")
    if transport:
        # As Chromium reads the HTTP charset: exactly as the header gives it
        # (fetch.parse_content_type trims its spaces and tabs); a form feed
        # or newline left in it makes it no label.
        enc = (LABELS.get(transport.lower()) if transport.isascii()
               else None)
        if enc is not None:
            return Decoded(decode(body, enc), enc, "certain", "transport")
    if body.startswith(b"<\x00?\x00x\x00"):
        return Decoded(decode(body, "UTF-16LE"), "UTF-16LE", "certain",
                       "xml-declaration")
    if body.startswith(b"\x00<\x00?\x00x"):
        return Decoded(decode(body, "UTF-16BE"), "UTF-16BE", "certain",
                       "xml-declaration")
    enc = None if xml else meta_charset(body)
    if enc is not None:
        return Decoded(decode(body, enc), enc, "tentative", "meta")
    enc = xml_declaration(body)
    if enc is not None:
        return Decoded(decode(body, enc), enc, "tentative", "xml-declaration")
    if xml:
        return Decoded(decode(body, "UTF-8"), "UTF-8", "tentative", "default")
    if local_file and _looks_utf8(body):
        return Decoded(body.decode("utf-8", errors="replace"), "UTF-8",
                       "tentative", "utf-8-detected")
    return Decoded(decode(body, "windows-1252"), "windows-1252", "tentative",
                   "default")
