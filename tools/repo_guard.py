#!/usr/bin/env python3
"""The repository guard (H5, PREPUBLISH items 8 and 10): fail when a
private key, a calibration golden set or a pack enters the repository.
`.gitignore` is a second line of defense, not the first.

    python tools/repo_guard.py [FOLDER]
    python tools/repo_guard.py --history [FOLDER]

It reads the files git tracks (and those it would add: everything not
ignored), and says how many files there git ignores, unread (they cannot
be committed without `git add -f`); a folder git ignores whole, or one
outside a git work tree, is read whole (every file under FOLDER but
caches and environments; default FOLDER: this repository). With
--history it reads every file in every commit HEAD reaches instead, and
every name any of them had, so a key added in one commit and removed in
the next is found too (R4A-12); a shallow clone, which lacks that
history, is refused (exit 2). It reports, and exits 1 on:

* a file named as `bellbriar-evidence keygen` names a private key
  (`*.key`), or as `.gitignore` names other key files;
* a private key file as `bellbriar-evidence keygen` writes it (its first
  line, then the key), whatever its name;
* a PEM, OpenSSH or PGP private key block in any file;
* an Ed25519 private key in PKCS#8 form (DER, either version of RFC 8410),
  raw or in hex, base64 or byte lists;
* an Ed25519 key pair written as one 64-byte value (seed then public key,
  as libsodium keeps them): its second half proves what its first is;
* the private half of a key whose public half or key id the repository
  holds. Every 32 bytes the files write are tried as an Ed25519 private
  key, and its public key and key id looked for, written any of the same
  ways (key ids in either case). The ways: hex in one run, at any offset
  in a longer run; bytes written one by one as two hex digits, with or
  without `0x`, `\\x`, `%` or `\\u00`, apart or not (white space, line
  breaks, `,` `;` `:` `.` `_` `|` `-` `+`, quotes, adjacent string
  literals), with casts such as `(byte)`, suffixes such as Rust's `u8` and
  Kotlin's `.toByte()`, and (in a text file) `//` or `/* */` comments
  between them (a C, Java, Kotlin or Rust array); hex dumps as `xxd` and `hexdump -C` write
  them; in a file of UTF-8 or UTF-16 text, Python bytes literals as
  `repr()` writes them, C strings with octal escapes, and string literals
  that read as bytes (a key decoded as Latin-1); decimal byte lists,
  signed or not, apart by commas, semicolons or spaces (`[157, 97, …]`,
  `[157 97 …]`, `[-99, 97, …]`, `157u8`); the key
  as one decimal integer; base64 or base64url, padded or not, on one
  line (one key a line, too), wrapped over several, or split over
  adjacent string literals (a JWK's `d`); a JSON file's strings as they
  read (a notebook's output); the bytes of a binary file of up to 1 KiB
  (a key, a key pair, a public key's DER); and, once more, any of these
  values that decodes to printable text of 43 bytes or more (a key's hex
  or base64 in base64, as a Kubernetes secret holds it). Text is read as UTF-8, as
  UTF-16 when it holds NUL bytes (UTF-32 when most of them are), as
  UTF-16 or UTF-32 by its byte-order mark, and byte for byte; a key id
  may be in a file's name. A zip, gzip, bzip2, xz or tar file's members
  are read too (a tar inside one of the others too, and archives inside
  archives three deep), by their own names (`/` or `\\`); one that
  cannot be read (encrypted, corrupt, past the 64 MiB or the 40,000
  members the guard unpacks from one file and the archives inside it, or
  nested deeper) is reported. A symbolic link is read as what git stores for it, the path
  it names, never through it. Within one value longer
  than 1 KiB, only 32 bytes at each multiple of 32 are tried, and within
  one longer than 64 KiB, only a PKCS#8 encoding. (Other spellings — URL
  or other encodings of whole strings, other dump formats — are not read.
  A key whose public half and key id appear nowhere reads like any other
  32 bytes, such as a digest. The demonstration key's private half is
  kept outside the repository; only the published canonicalization-vector
  key, whose private half is public by construction, is allowed.)
* a pack: a manifest (`pack.json`, or JSON with a pack manifest's
  `rulebook_min` and `files`) or a `SKILL.md`, anywhere but the sample
  pack;
* a calibration golden set or judge data (a file or folder named
  `golden…`, `calibration…` or `judge-data…`);
* a file too large to read for keys.

What it prints is escaped: a file's name cannot start a line of its own,
and no text makes a line a CI runner reads as a command.
Exit 0 when it finds nothing, 1 when it finds something, 2 when it cannot
look.
"""
from __future__ import annotations

import ast
import base64
import binascii
import bisect
import fnmatch
import gzip
import hashlib
import io
import os
import json
import re
import subprocess
import sys
import tarfile
import unicodedata
import warnings
import zipfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: The canonicalization vectors' signing key: private key = SHA-256 of a
#: published string, so anyone can derive it (docs/CANONICALIZATION.md).
PUBLIC_BY_CONSTRUCTION = {"172f109161589572"}
#: Key files, as .gitignore names them, and two more names for one.
KEY_NAMES = ("*.key", "*private-key*", "*PRIVATE-KEY*", "*DEMO-ONLY*",
             "*.key.*", "*.seed")
#: The one pack the repository may hold: the sample the docs describe.
SAMPLE_PACK = "examples/pack-sample/pack.json"
SAMPLE_SKILL = "examples/pack-sample/SKILL.md"
_PEM = re.compile(r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY(?: BLOCK)?-----")
#: The first line bellbriar-evidence keygen writes in a private key file,
#: then the key: a key file by another name (R5D-15). As the harness reads
#: one (bundle.parse_key_text): blank lines and white space around a line
#: are nothing (R5E-13).
_KEYGEN_PRIVATE = re.compile(
    r"^[ \t\r]*# bellbriar-evidence private key \(Ed25519\)\. Keep it "
    r"secret; never commit it\.[ \t\r]*\n(?:[ \t\r]*\n)*[ \t\r]*"
    r"(?:0[xX])?[0-9a-fA-F]{64}[ \t\r]*$", re.MULTILINE)
#: What an Ed25519 private key's PKCS#8 encoding (RFC 8410, versions 1 and
#: 2) holds just before its 32 bytes: the algorithm (1.3.101.112), then an
#: OCTET STRING in an OCTET STRING. A public key's encoding has a BIT
#: STRING there instead.
_DER_ED25519 = bytes.fromhex("300506032b657004220420")
#: Hex in one run.
_HEX_RUN = re.compile(r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{64,}(?![0-9A-Fa-f])")
#: Bytes written one by one: two hex digits each, with or without 0x,
#: \x, % (URL-encoding) or \u00 (JSON), apart or not. A separator never
#: starts a byte, so each text parses one way and the match takes linear
#: time (R4F-4); string prefixes (the b of b"…"), casts ((byte) 0x9d),
#: suffixes (0x9du8, 0x9d.toByte()) and comments are taken out first.
_BYTE = r"(?:0[xX]|\\[xX]|%|\\u00)?[0-9A-Fa-f]{2}"
_BYTE_SEP = (r"(?:[\s,;:'\"+\-._|]|\\(?![xX][0-9A-Fa-f]{2}"
             r"|u00[0-9A-Fa-f]{2}))*")
_BYTES = re.compile(r"(?<![0-9A-Za-z])" + _BYTE
                    + "(?:" + _BYTE_SEP + _BYTE + "){31,}")
_ONE_BYTE = re.compile(r"(?:0[xX]|\\[xX]|%|\\u00)?([0-9A-Fa-f]{2})")
_PREFIX = re.compile(r"(?<=[\s,(\[{=+])[bBrRuU]{1,2}(?=[\"'])")
_CAST = re.compile(r"\(\s*(?:byte|u?int8_t|u8|i8|(?:un)?signed\s+char|char)"
                   r"\s*\)")
#: Rust's u8 and i8 suffixes (0x9du8, 157u8), Kotlin's and Scala's
#: .toByte() (0x9d.toByte()).
_SUFFIX = re.compile(r"(?<=[0-9A-Fa-f])_?(?:[ui]8\b|\.toByte\b(?:\(\))?)")
#: Decimal byte lists, signed or not, apart by commas or spaces: [157, 97,
#: …] (JSON, JavaScript), [157 97 …] (Go), [-99, 97, …] (Java).
_DECIMALS = re.compile(r"(?<![\w.])-?\d{1,3}(?:(?:\s*[,;]\s*|\s+)"
                       r"-?\d{1,3}){31,}(?![\w.])")
#: String literals that hold \x or \u00 escapes or other than ASCII: a
#: key's bytes decoded as Latin-1, then written out.
_STR_LITERAL = re.compile(r"(?<![\w'\"\\])(?:'(?:[^'\\\n]|\\.){8,}'|"
                          r"\"(?:[^\"\\\n]|\\.){8,}\")")
#: A string of 32 to 330 units (a backslash and the character after it
#: one unit, so a byte as \u00XX is five, and a key pair's 64 bytes up to
#: 320: R5R-4), from each quote on, on one line or over line breaks: PHP,
#: Ruby, Perl and shell strings may hold a raw line break, a key's 0x0A
#: (R5L-7). Each quote is tried as a start, so neither the closing quote
#: of a string before it (R5N-4, R5P-3: `"Key:", sign(data, "…")`) nor
#: an apostrophe in a comment can hide it; the match is empty, its group
#: 1 the quote and group 2 what it holds.
_STR_SPAN = re.compile(r"(['\"])(?=((?:\\.|(?!\1)[^\\]){32,330})\1)")
#: A key as one integer (Python's int.from_bytes), in decimal, its digits
#: apart by _ or not, with JavaScript's n or Python 2's L after it or not.
_BIG_INT = re.compile(r"\d(?:_?\d){69,99}[nL]?(?![\w.])")
#: C strings with octal escapes ("\235a\261…"), alone or adjacent.
_C_OCTAL = re.compile(r'(?<!\\)"(?:[^"\\\n]|\\.)*"(?:\s*"(?:[^"\\\n]|\\.)*")*')
_C_PIECE = re.compile(r'"((?:[^"\\\n]|\\.)*)"')
_OCTAL_ESCAPE = re.compile(r"\\[0-7]")
#: Hex dumps: xxd ("00000000: 9d61 b1c3  .a..") and hexdump -C
#: ("00000000  9d 61 b1 c3  |.a..|"), their offsets and text left out.
_XXD = re.compile(r"^[ \t]*[0-9A-Fa-f]{6,8}: ([0-9A-Fa-f ]+?)(?:  |$)",
                  re.M)
_HEXDUMP = re.compile(r"^[ \t]*[0-9A-Fa-f]{7,8}  "
                      r"((?:[0-9A-Fa-f]{2} {1,2}){1,16}) *\|", re.M)
#: Python bytes literals (b'\x9da\xb1…', as repr() writes them), alone or
#: adjacent.
_PYBYTES = re.compile(
    r"(?<![\w'\"])(?:[bB][rR]?|[rR][bB])(?:'(?:[^'\\\n]|\\.)*'|"
    r"\"(?:[^\"\\\n]|\\.)*\")(?:[\s\\]*(?:[bB][rR]?|[rR][bB])"
    r"(?:'(?:[^'\\\n]|\\.)*'|\"(?:[^\"\\\n]|\\.)*\"))*")
#: base64 split over adjacent string literals: "…" "…", or "…" + "…".
_STR_B64 = re.compile(r"(['\"])[A-Za-z0-9+/_\-=]{8,}\1(?:[\s+\\]*(['\"])"
                      r"[A-Za-z0-9+/_\-=]{4,}\2){1,63}")
#: base64 or base64url, padded or not, on one line…
_B64 = re.compile(r"(?<![A-Za-z0-9+/_\-])[A-Za-z0-9+/_\-]{40,}={0,2}"
                  r"(?![A-Za-z0-9+/_\-=])")
#: …or wrapped over several, each line nothing but base64 (as `base64` and
#: PEM bodies write it, or a string split over lines).
_B64_LINES = re.compile(
    r"(?:^[ \t\"']*[A-Za-z0-9+/_\-]{16,}={0,2}[\"',]*[ \t]*\r?\n){1,64}"
    r"[ \t\"']*[A-Za-z0-9+/_\-]{2,}={0,2}", re.M)
_HEX16 = re.compile(r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{16}(?![0-9A-Fa-f])")
_GOLDEN = re.compile(r"(?i)^(golden|calibration|judge[-_]?data)")
#: Outside git, what a work tree holds that is not the repository's: its
#: own top-level build output and environments, and caches anywhere. A
#: folder of these names deeper down (fixtures/dist) is read.
_SKIP_TOP = {".git", "node_modules", ".venv", "venv", "build", "dist"}
_SKIP_ANY = {".git", "__pycache__"}
#: Files larger than this cannot be read for keys, and are reported (none
#: of the repository's comes near it; a key file is 65 bytes). It bounds
#: what a zip or gzip file is unpacked to as well.
MAX_SCAN = 64 * 1024 * 1024
#: A value longer than this is tried at each multiple of 32 bytes only…
_MAX_SLIDE = 1024
#: …and one longer than this only for a PKCS#8 encoding (R4F-5).
_MAX_ALIGNED = 64 * 1024


class Shallow(RuntimeError):
    """--history in a clone that lacks part of the history."""


def files(folder: Path, everything: bool = False) -> list[Path]:
    """The files to check: git's view of the work tree (tracked, plus
    untracked ones it does not ignore), or every file under `folder` but
    caches and virtual environments. With `everything`, every file under
    it, whatever its name (an unpacked distribution, tools/check_dist.py:
    whatever is in it ships)."""
    return _listing(folder, everything)[0]


def _git_files(folder: Path, *args: str) -> list[str] | None:
    try:
        out = subprocess.run(["git", "-C", str(folder), "ls-files", "-z",
                              *args], capture_output=True, timeout=60,
                             check=True).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return [n for n in out.decode("utf-8", "surrogateescape").split("\0")
            if n]


def _listing(folder: Path, everything: bool = False) -> tuple[list, int]:
    """(files(), how many files under `folder` git ignores and so were not
    read: they cannot be committed without git add -f, R4H-14)."""
    if not everything:
        names = _git_files(folder, "--cached", "--others",
                           "--exclude-standard")
        if names is not None:
            # A symbolic link is listed whatever it names, outside the
            # folder or nothing (R5A-9).
            listed = sorted({folder / n for n in names
                             if (folder / n).is_symlink()
                             or (folder / n).is_file()})
            # A folder git ignores lists nothing, and is read whole like a
            # folder outside git, not passed as clean (R4F-6).
            if listed or not any(p.is_file() for p in folder.rglob("*")):
                ignored = _git_files(folder, "--others", "--ignored",
                                     "--exclude-standard") or []
                return listed, sum(1 for n in ignored
                                   if (folder / n).is_file())

    def skipped(parts) -> bool:
        return parts[0] in _SKIP_TOP or bool(_SKIP_ANY & set(parts))
    return sorted(p for p in folder.rglob("*")
                  if (p.is_symlink() or p.is_file()) and (
                      everything or not skipped(p.relative_to(folder).parts))
                  ), 0


def _shown(text: str) -> str:
    """`text` as a console shows it: every control or format character
    escaped, so a file's name cannot start a line of its own (a CI runner
    reads "::error" at the start of one as a command), or reorder or hide
    what is printed (R4H-9); and every "#" after another escaped, since
    runners read "##[…]", "##vso[…]" and "##teamcity[…]" anywhere in a
    line (R5A-2)."""
    out = []
    for ch in str(text):
        if unicodedata.category(ch) in ("Cc", "Cf", "Cs", "Co", "Cn", "Zl",
                                        "Zp"):
            n = ord(ch)
            out.append(f"\\u{n:04x}" if n <= 0xFFFF else f"\\U{n:08x}")
        elif ch == "#" and out and out[-1] == "#":
            out.append("\\u0023")
        else:
            out.append(ch)
    return "".join(out)


def _utf8(data: bytes) -> bool:
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def _ed25519():
    try:
        from cryptography.hazmat.primitives.asymmetric import ed25519
    except ImportError:
        return None
    return ed25519


def _texts(data: bytes) -> list[tuple[str, bool]]:
    """The ways a file can be read as text, each with whether it reads as
    text (not a binary file's bytes): by its byte-order mark; as UTF-8; as
    UTF-16 when it holds NUL bytes (ASCII in UTF-16 is valid UTF-8 too,
    NULs and all); and byte for byte, so hex or base64 inside a binary file
    is read too."""
    for bom, enc in ((b"\xef\xbb\xbf", "utf-8-sig"),
                     (b"\xff\xfe\x00\x00", "utf-32"),
                     (b"\x00\x00\xfe\xff", "utf-32"),
                     (b"\xff\xfe", "utf-16"), (b"\xfe\xff", "utf-16")):
        if data.startswith(bom):
            try:
                return [(data.decode(enc), True)]
            except UnicodeDecodeError:
                break
    out = []
    try:
        out.append((data.decode("utf-8"), True))
    except UnicodeDecodeError:
        out.append((data.decode("latin-1"), False))
    if b"\x00" in data:
        # UTF-16 or UTF-32 with no byte-order mark: text when it reads as
        # text (R4J-10).
        encodings = ["utf-16-le", "utf-16-be"]
        if data.count(b"\x00") > len(data) // 2:
            encodings += ["utf-32-le", "utf-32-be"]
        for enc in encodings:
            text = data.decode(enc, "ignore")
            out.append((text, _looks_text(text)))
    return out


def _printable_ascii(raw: bytes) -> bool:
    """Bytes that are text: printable ASCII and white space only."""
    return bool(_ASCII_TEXT.match(raw))


_ASCII_TEXT = re.compile(rb"[\x20-\x7e\t\n\r]*\Z")


#: A string literal on one line, for _looks_text to leave out: a key
#: decoded as Latin-1 and written into one holds control characters.
_QUOTED = re.compile(r"(?<!\\)\"(?:[^\"\\\n]|\\.)*\"|(?<!\\)'(?:[^'\\\n]|\\.)*'")


def _looks_text(text: str) -> bool:
    """Is it text: all but a twentieth of it, outside its string literals,
    printable or white space? A key's bytes written into a literal must
    not make a small UTF-16 file read as binary, and so go unread as
    source (R5A-3)."""
    outside = _QUOTED.sub("", text)
    if not outside.strip():
        return bool(text)
    odd = sum(1 for c in outside
              if not (c.isprintable() or c in "\n\r\t"))
    return odd * 20 <= len(outside)


def _b64(token: str) -> bytes | None:
    body = re.sub(r"[^A-Za-z0-9+/_\-]", "", token)
    url, std = any(c in body for c in "-_"), any(c in body for c in "+/")
    if url and std:
        return None
    try:
        return base64.b64decode(body + "=" * (-len(body) % 4),
                                altchars=b"-_" if url else None,
                                validate=True)
    except (binascii.Error, ValueError):
        return None


def _hex_values(run: str) -> list[bytes]:
    """A hex run as bytes, from each of its two alignments: a key can
    start at an odd digit of a longer run."""
    out = []
    for start in (0, 1):
        body = run[start:]
        body = body[:len(body) - len(body) % 2]
        if len(body) >= 64:
            out.append(bytes.fromhex(body))
    return out


def _encoded(token: str) -> bool:
    """Do these characters look like encoded bytes? Encoded bytes mix
    digits and both cases: an identifier or a path made of base64's
    letters (a long name, src/a/b) does not. Whatever its letters, a token
    as long as base64 writes a key (32 bytes), its PKCS#8 encoding (48) or
    a key pair (64) is read: about one key in 1,500 has no digit in base64
    (R5A-4)."""
    body = re.sub(r"[^A-Za-z0-9+/_\-]", "", token)
    if len(body) in _KEY_B64_LENGTHS:
        return True
    return bool(re.search(r"\d", token) and re.search(r"[a-z]", token)
                and re.search(r"[A-Z]", token))


#: How many base64 characters (padding aside) 32, 48 and 64 bytes take.
_KEY_B64_LENGTHS = (43, 64, 86)


def _literal(source: str):
    """A Python literal's value, or None; quietly (a bytes literal with an
    escape Python does not know, b'\\d', warns: R4H-8). A NUL character,
    which Python source cannot hold but a string in a file of another
    language can (a key's zero byte written as it is), is read as that
    character."""
    if "\x00" in source:
        source = source.replace("\x00", "\\x00")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            return ast.literal_eval(source)
        except (ValueError, TypeError, SyntaxError, MemoryError,
                RecursionError):
            return None


def _one_line(literal: str) -> str:
    """One string literal (its quotes and what they hold), its raw carriage
    returns and line feeds written as escapes, so it reads as one Python
    literal: a key's 0x0D or 0x0A written as it is (R5L-7). Only a single
    literal: between two, a line break is no character (R5N-1)."""
    if "\r" in literal or "\n" in literal:
        literal = literal.replace("\r", "\\r").replace("\n", "\\n")
    return literal


def _latin1(value) -> bytes | None:
    """A string that reads as bytes, as those bytes: every character
    below U+0100, and a quarter of them or more controls or past ASCII, as
    a key's bytes decoded as Latin-1 are (text in a language with accents
    is not)."""
    if not isinstance(value, str) or not 32 <= len(value) <= _MAX_SLIDE \
            or any(ord(c) > 0xFF for c in value):
        return None
    odd = sum(1 for c in value if ord(c) < 0x20 or ord(c) > 0x7E)
    return value.encode("latin-1") if odd * 4 >= len(value) else None


def _uncommented(text: str) -> str:
    """`text` without // and /* */ comments, in linear time: a C array
    may have one on each line."""
    text = re.sub(r"//[^\n]*", " ", text)
    out, at = [], 0
    while True:
        start = text.find("/*", at)
        end = text.find("*/", start + 2) if start >= 0 else -1
        if end < 0:
            break
        out += [text[at:start], " "]
        at = end + 2
    out.append(text[at:])
    return "".join(out)


def _values(text: str, source: bool = True) -> list[bytes]:
    """The byte values `text` writes that could hold a key, in every way
    the module's docstring names. The spellings of source code (string
    literals, comments) only in `source`, text a file holds as text: in a
    binary file's bytes read as Latin-1, any stretch between quotes would
    read as one, and the time goes on those."""
    out = []
    for m in _HEX_RUN.finditer(text):
        out += _hex_values(m.group())
    plain = _SUFFIX.sub("", _CAST.sub(" ", _PREFIX.sub("", text)))
    for each in dict.fromkeys((plain, _uncommented(plain) if source
                               else plain)):
        for m in _BYTES.finditer(each):
            out.append(bytes.fromhex("".join(_ONE_BYTE.findall(m.group()))))
    decimal = _SUFFIX.sub("", _CAST.sub(" ", text))
    for each in dict.fromkeys((decimal, _uncommented(decimal) if source
                               else decimal)):
        for m in _DECIMALS.finditer(each):
            numbers = [int(n) for n in re.findall(r"-?\d+", m.group())]
            if all(-128 <= n <= 255 for n in numbers):
                out.append(bytes(n & 0xFF for n in numbers))
    # (Each pass below runs only where the text has what it reads: the
    # passes are what the guard's time goes on.)
    for m in _BIG_INT.finditer(text):
        before = text[m.start() - 1:m.start()]
        digits = m.group().rstrip("nL").replace("_", "")
        if before.isalnum() or before in ("_", ".") or \
                not 70 <= len(digits) <= 78:
            continue
        n = int(digits)
        if n < 1 << 256:
            out += [n.to_bytes(32, "big"), n.to_bytes(32, "little")]
    if source and any(q in text for q in ("b'", 'b"', "B'", 'B"', "R'", 'R"',
                                          "r'", 'r"')):
        for m in _PYBYTES.finditer(text):
            if len(m.group()) <= _MAX_ALIGNED * 4:
                value = _literal("(" + m.group() + ")")
                if isinstance(value, bytes) and len(value) >= 32:
                    out.append(value)
    # Escapes as Python, JavaScript, Java, Kotlin, C# and YAML write them
    # (\x9d, \u009d), or characters past ASCII as they are (R4J-2).
    if source and ("\\x" in text or "\\u00" in text or not text.isascii()):
        for m in _STR_LITERAL.finditer(text):
            literal = m.group()
            if "\\x" in literal or "\\u00" in literal or \
                    not literal.isascii():
                raw = _latin1(_literal(_one_line(literal)))
                if raw is not None:
                    out.append(raw)
        for m in _STR_SPAN.finditer(text):
            body = m.group(2)
            if "\\x" in body or "\\u00" in body or not body.isascii():
                raw = _latin1(_literal(_one_line(m.group(1) + body
                                                 + m.group(1))))
                if raw is not None:
                    out.append(raw)
    if source and _OCTAL_ESCAPE.search(text):
        for m in _C_OCTAL.finditer(text):
            if len(m.group()) >= 34 and m.group().isascii() and \
                    _OCTAL_ESCAPE.search(m.group()):
                body = "".join(_C_PIECE.findall(m.group()))
                value = _literal('b"' + body + '"')
                if isinstance(value, bytes) and len(value) >= 32:
                    out.append(value)
    for dump in (_XXD, _HEXDUMP):
        digits = "".join(m.group(1) for m in dump.finditer(text)).replace(
            " ", "")
        if len(digits) >= 64 and len(digits) % 2 == 0:
            out.append(bytes.fromhex(digits))
    # Lines of base64 wrapped as one value: read whole. Their lines are
    # read one by one only for a key or a key pair (R4F-5): a list of keys,
    # one a line, is no wrapped value (R4H-1).
    starts, ends = [], []
    for m in _B64_LINES.finditer(text):
        if m.group().count("\n") >= 2:
            starts.append(m.start())
            ends.append(m.end())
        if _encoded(m.group()):
            raw = _b64(m.group())
            if raw is not None and len(raw) >= 32:
                out.append(raw)
    for m in _B64.finditer(text):
        if not _encoded(m.group()):
            continue
        raw = _b64(m.group())
        if raw is None or len(raw) < 32:
            continue
        at = bisect.bisect_right(starts, m.start()) - 1
        if at >= 0 and m.start() < ends[at] and len(raw) not in (32, 64):
            continue
        out.append(raw)
    for m in _STR_B64.finditer(text):
        joined = "".join(re.findall(r"['\"]([A-Za-z0-9+/_\-=]+)['\"]",
                                    m.group()))
        if _encoded(joined):
            raw = _b64(joined)
            if raw is not None and len(raw) >= 32:
                out.append(raw)
    return out


def _strings(doc) -> list[str]:
    """Every string a JSON document holds, keys too, without recursion."""
    out, todo = [], [doc]
    while todo:
        item = todo.pop()
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict):
            out += [k for k in item if isinstance(k, str)]
            todo += item.values()
        elif isinstance(item, list):
            todo += item
    return out


#: The most members of one archive the guard reads.
_MAX_MEMBERS = 10000
#: How deep archives inside archives are read; one deeper is reported.
_MAX_DEPTH = 3


def _archive_kind(data: bytes) -> str | None:
    """"zip", "gzip", "bzip2", "xz" or "tar" by the file's own signature,
    or None. A bzip2 stream's signature is checked whole (BZh, a block
    size, then a block's or the end's own mark), so text that starts "BZh"
    is text (R4H-10)."""
    if data[:4] == b"PK\x03\x04":
        return "zip"
    if data[:2] == b"\x1f\x8b":
        return "gzip"
    if data[:3] == b"BZh" and data[3:4] in b"123456789" and \
            data[4:10] in (b"1AY&SY", b"\x17rE8P\x90"):
        return "bzip2"
    if data[:6] == b"\xfd7zXZ\x00":
        return "xz"
    if data[257:262] == b"ustar" or _tar_header(data):
        return "tar"
    # A zip after something else (a self-extracting program): by its end
    # record, when zipfile reads a member from it. Those four bytes alone
    # turn up by chance in a large enough file (R4J-6).
    if b"PK\x05\x06" in data[-65557:]:
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                if z.infolist():
                    return "zip"
        except Exception:                             # noqa: BLE001
            pass
    return None


def _tar_header(data: bytes) -> bool:
    """Does `data` start with a tar header of any format, the first one
    (v7) included, which has no "ustar" mark (R4J-8): a name, then the
    checksum its header records?"""
    if len(data) < 512 or not data[:1].strip(b"\0"):
        return False
    head = data[:512]
    field = head[148:156].replace(b"\0", b" ").strip()
    if not field or not all(48 <= b <= 55 for b in field):
        return False
    stored = int(field, 8)
    rest = head[:148] + b" " * 8 + head[156:]
    return stored in (sum(rest), sum(b - 256 if b > 127 else b for b in rest))


def _tar_members(inner: bytes, out: list, unread: list,
                 budget: list | None = None) -> bool:
    """A tar's members into `out`; False when `inner` is no tar, or one
    with no member (a disk image's first block of zeros reads as an empty
    tar: R4J-3). Every member a damaged header or an end-of-archive mark
    would hide is read too: tar files joined end to end are read whole
    (R4H-7). Members are read to at most MAX_SCAN bytes in all; the rest
    are reported, by name (R4J-7)."""
    try:
        # Is it a tar at all? (Read past bad headers, anything would be.)
        with tarfile.open(fileobj=io.BytesIO(inner), mode="r:") as t:
            if t.next() is None:
                return False
    except Exception:                                 # noqa: BLE001
        return False
    try:
        budget = budget if budget is not None else _new_budget()
        with tarfile.open(fileobj=io.BytesIO(inner), mode="r:",
                          ignore_zeros=True) as t:
            count = 0
            while True:
                # One header at a time: what comes before a damaged one is
                # read and named.
                m = t.next()
                if m is None:
                    break
                count += 1
                if count > _MAX_MEMBERS:
                    unread.append(("", f"more than {_MAX_MEMBERS:,} members, "
                                   "more than the guard reads"))
                    break
                if budget[1] <= 0:
                    unread.append(("", _PAST_MEMBERS))
                    break
                budget[1] -= 1
                if not m.isfile():
                    out.append((m.name, None))      # a folder's name, a link's
                    continue
                if m.size > MAX_SCAN:
                    unread.append((m.name, "too large to read for keys"))
                    out.append((m.name, None))
                elif m.size > budget[0]:
                    unread.append((m.name, _PAST_BUDGET))
                    out.append((m.name, None))
                else:
                    budget[0] -= m.size
                    f = t.extractfile(m)
                    out.append((m.name, f.read() if f is not None else b""))
    except Exception as exc:                          # noqa: BLE001
        unread.append(("", f"a tar that cannot be read whole "
                       f"({type(exc).__name__})"))
    return True


#: Why a member is not read: what one file unpacks to is read to
#: MAX_SCAN bytes in all, the archives inside it included (R5A-11).
_PAST_BUDGET = (f"not read: past the {MAX_SCAN // 2**20} MiB the guard "
                "unpacks from one file and the archives inside it")
#: How many members the guard reads of one file and the archives inside
#: it, in all: an archive of many archives of empty members cost it a
#: minute a file (R5C-14).
_MAX_ALL_MEMBERS = 4 * _MAX_MEMBERS
_PAST_MEMBERS = (f"not read: past the {_MAX_ALL_MEMBERS:,} members the guard "
                 "reads of one file and the archives inside it")


def _new_budget() -> list:
    """[bytes, members] one file may unpack, shared by the archives in it."""
    return [MAX_SCAN, _MAX_ALL_MEMBERS]


def _unpacked(data: bytes, budget: list | None = None
              ) -> tuple[list, list]:
    """What a zip, gzip, bzip2, xz or tar file (or a tar in one of the
    others) holds: ([(member name, bytes, or None when it cannot be
    read)], [(member name, why it could not be read)]), unpacked to at most
    MAX_SCAN bytes in all; ([], []) for any other file. A member that
    cannot be read (encrypted, past what the guard reads, corrupt) is a
    problem, never silence (R4F-2, R4H-7)."""
    out: list = []
    unread: list = []
    budget = budget if budget is not None else _new_budget()
    kind = _archive_kind(data)
    if kind == "zip":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                infos = z.infolist()
                if len(infos) > _MAX_MEMBERS:
                    unread.append(("", f"{len(infos):,} members, more than "
                                   "the guard reads"))
                for info in infos[:_MAX_MEMBERS]:
                    if budget[1] <= 0:
                        unread.append(("", _PAST_MEMBERS))
                        break
                    budget[1] -= 1
                    if info.is_dir():
                        out.append((info.filename, None))   # its name
                        continue
                    if info.flag_bits & 0x1:
                        unread.append((info.filename, "encrypted, so its "
                                       "content cannot be read for keys"))
                        out.append((info.filename, None))
                    elif info.file_size > MAX_SCAN:
                        unread.append((info.filename, "too large to read "
                                       "for keys"))
                        out.append((info.filename, None))
                    elif info.file_size > budget[0]:
                        unread.append((info.filename, _PAST_BUDGET))
                        out.append((info.filename, None))
                    else:
                        budget[0] -= info.file_size
                        try:
                            out.append((info.filename, z.read(info)))
                        except Exception as exc:        # noqa: BLE001
                            unread.append((info.filename, "cannot be read "
                                           f"({type(exc).__name__})"))
                            out.append((info.filename, None))
        except Exception as exc:                        # noqa: BLE001
            unread.append(("", f"a zip file that cannot be read "
                           f"({type(exc).__name__})"))
    elif kind == "tar":
        if not _tar_members(data, out, unread, budget):
            unread.append(("", "a tar file that cannot be read"))
    elif kind is not None:
        import bz2
        import lzma
        opener = {"gzip": lambda f: gzip.GzipFile(fileobj=f),
                  "bzip2": bz2.BZ2File, "xz": lzma.LZMAFile}[kind]
        try:
            with opener(io.BytesIO(data)) as g:
                inner = g.read(budget[0] + 1)
        except Exception as exc:                        # noqa: BLE001
            unread.append(("", f"a {kind} file that cannot be read "
                           f"({type(exc).__name__})"))
            return out, unread
        if len(inner) > budget[0]:
            unread.append(("", "unpacks to more than the "
                           f"{MAX_SCAN // 2**20} MiB the guard unpacks from "
                           "one file and the archives inside it"))
            return out, unread
        budget[0] -= len(inner)
        # The tar's members' bytes are inside what was just counted; their
        # number counts against the file's.
        inside = [len(inner), budget[1]]
        if not _tar_members(inner, out, unread, inside):
            out.append(("", inner))
        budget[1] = inside[1]
    return out, unread


def _key_id(pub: bytes) -> str:
    return hashlib.sha256(pub).hexdigest()[:16]


class _Scan:
    """What the files hold, gathered file by file, then judged together:
    a private half is known for one only by the public half or key id
    another file holds."""

    def __init__(self):
        self.problems: list[str] = []
        #: 32-byte value: the first file it is in.
        self.values: dict[bytes, str] = {}
        #: 64-byte value: the first file it is in.
        self.pairs: dict[bytes, str] = {}
        self.ids: set[str] = set()

    def name(self, rel: str, path: str | None = None) -> None:
        """The checks a file's name answers, on `path` (an archive member's
        own path, R4F-2) or `rel`, reported as `rel`; a key id in it
        counts as one the repository holds (keys/<key id>.pub)."""
        # An archive written on Windows may name its members with
        # backslashes (R4H-5).
        own = rel if path is None else path.replace("\\", "/")
        self.ids.update(t.lower() for t in _HEX16.findall(own))
        name = own.rsplit("/", 1)[-1]
        if any(fnmatch.fnmatchcase(name, pat) for pat in KEY_NAMES):
            self.problems.append(f"{rel}: a key file (named as .gitignore "
                                 "names private keys)")
        if (name == "pack.json" and own != SAMPLE_PACK) or (
                name == "SKILL.md" and own != SAMPLE_SKILL):
            self.problems.append(f"{rel}: part of a pack; real packs never "
                                 "enter this repository (only the sample "
                                 "pack does)")
        for part in own.split("/"):
            if _GOLDEN.match(part):
                self.problems.append(f"{rel}: calibration or judge data "
                                     f"(named {part!r}); golden sets never "
                                     "enter this repository")
                break

    def add(self, rel: str, data: bytes, depth: int = 0,
            path: str | None = None, budget: list | None = None) -> None:
        """A file: its name, then what it holds."""
        self.name(rel, path)
        self.content(rel, data, depth, path, budget)

    def content(self, rel: str, data: bytes, depth: int = 0,
                path: str | None = None,
                budget: list | None = None) -> None:
        """The checks a file's bytes answer. `budget`: how much more the
        file this came from may unpack, shared by every archive in it."""
        if len(data) > MAX_SCAN:
            self.problems.append(f"{rel}: {len(data):,} bytes, too large to "
                                 "read for keys")
            return
        # The file's own bytes: a PKCS#8 encoding anywhere in them, and
        # every 32 bytes of a small binary file (a key, a key pair, a
        # public key's DER), R4F-3.
        small_binary = len(data) <= _MAX_SLIDE and not _utf8(data)
        self._blob(rel, data, slide=len(data) in (32, 64) or small_binary)
        own = rel if path is None else path.replace("\\", "/")
        name = own.rsplit("/", 1)[-1]
        texts = _texts(data)
        doc = None
        if texts[0][0].lstrip()[:1] in ("{", "["):
            try:
                doc = json.loads(texts[0][0])
            except (ValueError, RecursionError):
                doc = None
        if name.endswith(".json") and own != SAMPLE_PACK and \
                isinstance(doc, dict) and {"rulebook_min", "files"} <= set(doc):
            self.problems.append(f"{rel}: a pack manifest; real packs "
                                 "never enter this repository (only "
                                 "the sample pack does)")
        if doc is not None:
            # A JSON file's strings as they read (a notebook's output of a
            # key's repr(), R4H-11), and those that read as bytes.
            strings = _strings(doc)
            texts.append(("\n".join(strings), True))
            for s in strings:
                raw = _latin1(s)
                if raw is not None:
                    self._blob(rel, raw)
        pem = False
        for text, as_text in texts:
            if not pem and _PEM.search(text):
                self.problems.append(f"{rel}: holds a PEM, OpenSSH or PGP "
                                     "private key")
                pem = True
            if not pem and _KEYGEN_PRIVATE.search(text):
                self.problems.append(f"{rel}: holds a private key file as "
                                     "bellbriar-evidence keygen writes it")
                pem = True
            for raw in _values(text, source=as_text):
                self._blob(rel, raw)
                # A value that decodes to text, such as a key file's hex
                # in base64 (a Kubernetes secret) or in a dump, is read as
                # text once more (R4J-1); 43 bytes and up, a JWK's `d`
                # (R5A-13).
                if len(raw) >= 43 and _printable_ascii(raw):
                    decoded = raw.decode("ascii")
                    if not pem and _PEM.search(decoded):
                        self.problems.append(f"{rel}: holds a PEM, OpenSSH "
                                             "or PGP private key, encoded")
                        pem = True
                    for inner in _values(decoded, source=False):
                        self._blob(rel, inner)
                    self.ids.update(t.lower()
                                    for t in _HEX16.findall(decoded))
            self.ids.update(t.lower() for t in _HEX16.findall(text))
        if _archive_kind(data) is None:
            return
        if depth >= _MAX_DEPTH:
            self.problems.append(f"{rel}: an archive inside {depth} others, "
                                 "deeper than the guard reads")
            return
        budget = budget if budget is not None else _new_budget()
        members, unread = _unpacked(data, budget)
        for inner, member in members:
            label = f"{rel}!{inner}" if inner else f"{rel} (unpacked)"
            if member is None:
                self.name(label, inner)
            else:
                self.add(label, member, depth + 1, inner or None, budget)
        for inner, why in unread:
            self.problems.append(f"{rel}!{inner}: {why}" if inner
                                 else f"{rel}: {why}")

    def _blob(self, rel: str, raw: bytes, slide: bool = True) -> None:
        """Bytes that may hold a key: a PKCS#8 encoding anywhere in them,
        and (with `slide`) every 32 and 64 bytes of them, for judge()."""
        at = raw.find(_DER_ED25519)
        if at >= 0 and len(raw) >= at + len(_DER_ED25519) + 32:
            self.problems.append(f"{rel}: holds an Ed25519 private key "
                                 "(PKCS#8)")
        n = len(raw)
        if n < 32 or not slide or n > _MAX_ALIGNED:
            return
        step = 1 if n <= _MAX_SLIDE else 32
        for i in range(0, n - 31, step):
            self.values.setdefault(raw[i:i + 32], rel)
        for i in range(0, n - 63, step):
            self.pairs.setdefault(raw[i:i + 64], rel)

    def judge(self) -> list[str]:
        ed = _ed25519()
        if ed is None:
            return self.problems + ["cannot check for private keys: the "
                                    "cryptography package is not "
                                    "installed"]
        out = list(dict.fromkeys(self.problems))
        pub_of: dict[bytes, bytes] = {}

        def pub(seed: bytes) -> bytes:
            if seed not in pub_of:
                pub_of[seed] = ed.Ed25519PrivateKey.from_private_bytes(
                    seed).public_key().public_bytes_raw()
            return pub_of[seed]
        found: set[str] = set()
        for pair, rel in sorted(self.pairs.items(), key=lambda kv: kv[1]):
            if pub(pair[:32]) == pair[32:]:
                kid = _key_id(pair[32:])
                if kid not in PUBLIC_BY_CONSTRUCTION and kid not in found:
                    found.add(kid)
                    out.append(f"{rel}: holds the private key of key {kid}, "
                               "with its public key after it")
        for value, rel in sorted(self.values.items(), key=lambda kv: kv[1]):
            p = pub(value)
            kid = _key_id(p)
            if kid in PUBLIC_BY_CONSTRUCTION or kid in found:
                continue
            if p in self.values or kid in self.ids:
                found.add(kid)
                out.append(f"{rel}: holds the private half of key {kid}, "
                           "whose public half or key id the repository "
                           "also holds")
        return out


def check(folder: Path, everything: bool = False) -> list[str]:
    """Every problem found under `folder`, as one line each."""
    return _check(folder, everything)[0]


def _check(folder: Path, everything: bool = False) -> tuple[list, int]:
    """(check(), how many files git ignores there, unread)."""
    scan = _Scan()
    paths, ignored = _listing(folder, everything)
    for path in paths:
        rel = path.relative_to(folder).as_posix()
        try:
            if path.is_symlink():
                # What git stores for a link is the path it names; read
                # through it, a link to a key outside the repository read
                # as a key in it, and --history disagreed (R5A-9).
                scan.add(rel, os.fsencode(os.readlink(path)))
                continue
            if path.stat().st_size > MAX_SCAN:
                scan.name(rel)
                scan.problems.append(f"{rel}: {path.stat().st_size:,} bytes, "
                                     "too large to read for keys")
                continue
            data = path.read_bytes()
        except OSError as exc:
            scan.problems.append(f"{rel}: cannot be read "
                                 f"({exc.strerror or exc})")
            continue
        scan.add(rel, data)
    return scan.judge(), ignored


def check_history(folder: Path) -> list[str]:
    """Every problem found in any file of any commit HEAD reaches, and in
    any name a file had in one: a key removed again is still in the
    history anyone who clones the repository gets. Raises Shallow in a
    clone that lacks part of that history."""
    # The user's own settings never shape what is read: a signature
    # printed into the log, the root commit's names left out, colors
    # (R4J-4).
    git = ["git", "-C", str(folder), "-c", "log.showSignature=false",
           "-c", "log.showRoot=true", "-c", "color.ui=never"]

    def run(*args, data=None) -> bytes:
        return subprocess.run(git + list(args), input=data,
                              capture_output=True, timeout=600,
                              check=True).stdout
    if run("rev-parse", "--is-shallow-repository").strip() == b"true":
        raise Shallow("this is a shallow clone, which lacks part of the "
                      "history (git fetch --unshallow, or check out with "
                      "fetch-depth: 0)")
    scan = _Scan()
    # Every name any commit gave a file, merges included (R4D-5): a file's
    # name is checked even where its content is the same as another's.
    # -z: names as they are, not quoted (R4F-1). Each commit's record is a
    # \x01 of its own, then a line break, then its names, each ended by a
    # NUL: so a name that starts or ends with a line break keeps it (R4H-9).
    out = run("log", "-z", "-m", "--root", "--no-color", "--format=%x01",
              "--name-only", "--no-renames", "--diff-filter=AMC", "HEAD")
    names: set = set()
    after_record = False
    for token in out.split(b"\0"):
        if token == b"\x01":
            after_record = True
            continue
        if after_record and token.startswith(b"\n"):
            token = token[1:]
        after_record = False
        if token:
            names.add(token.decode("utf-8", "surrogateescape"))
    for rel in sorted(names):
        scan.name(f"{rel} (in history)", rel)
    # Objects and the first path each had. rev-list writes a path only up
    # to a line break in it; the whole name is the one the log gave
    # (R4H-9).
    listed = run("rev-list", "--objects", "HEAD").decode("utf-8",
                                                          "surrogateescape")
    paths: dict[str, str] = {}
    for line in listed.split("\n"):
        sha, _, path = line.partition(" ")
        if path and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", sha):
            paths.setdefault(sha, path)
    for sha, path in paths.items():
        if path not in names:
            whole = sorted(n for n in names if n.startswith(path + "\n"))
            if whole:
                paths[sha] = whole[0]
    kinds = run("cat-file", "--batch-check=%(objectname) %(objecttype) "
                "%(objectsize)", data="\n".join(paths).encode()
                ).decode().split("\n")
    blobs = []
    for line in kinds:
        parts = line.split()
        if len(parts) == 3 and parts[1] == "blob":
            if int(parts[2]) > MAX_SCAN:
                scan.problems.append(f"{paths[parts[0]]} (in history): "
                                     f"{int(parts[2]):,} bytes, too large to "
                                     "read for keys")
            else:
                blobs.append(parts[0])
    if blobs:
        # One blob at a time, as git writes them: the history whole would
        # be held in memory at once (R5A-10).
        for sha, data in _blobs(git, blobs):
            scan.content(f"{paths[sha]} (in history)", data, 0, paths[sha])
    return scan.judge()


def _blobs(git: list, shas: list):
    """(sha, bytes) for each blob `shas` names, read from one
    `git cat-file --batch` as it writes them; the names go in from a
    thread of their own, so neither pipe can fill and stop the other."""
    import threading
    proc = subprocess.Popen(git + ["cat-file", "--batch"],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL)

    def feed() -> None:
        try:
            proc.stdin.write("\n".join(shas).encode() + b"\n")
            proc.stdin.close()
        except OSError:
            pass
    writer = threading.Thread(target=feed, daemon=True)
    writer.start()
    try:
        for sha in shas:
            parts = proc.stdout.readline().split()
            if len(parts) != 3 or parts[1] != b"blob":
                raise subprocess.SubprocessError(
                    "git cat-file answered something other than a blob")
            size = int(parts[2])
            data = proc.stdout.read(size)
            if len(data) != size or proc.stdout.read(1) != b"\n":
                # Cut short: never read part of a blob as all of it (R5C-9).
                raise subprocess.SubprocessError(
                    "git cat-file stopped in the middle of a blob")
            yield sha, data
        proc.stdout.close()
        if proc.wait(timeout=60) != 0:
            raise subprocess.SubprocessError(
                f"git cat-file failed (exit {proc.returncode})")
    finally:
        proc.stdout.close()
        try:
            proc.wait(timeout=60)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        writer.join(timeout=60)


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    history = "--history" in args
    if history:
        args.remove("--history")
    if len(args) > 1 or (args and args[0].startswith("-")):
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    folder = Path(args[0]).resolve() if args else ROOT
    if not folder.is_dir():
        print(f"repo_guard: not a folder: {_shown(folder)}", file=sys.stderr)
        return 2
    ignored = 0
    if history:
        try:
            problems = check_history(folder)
        except Shallow as exc:
            print(f"repo_guard: cannot read the whole history of "
                  f"{_shown(folder.name)}: {exc}", file=sys.stderr)
            return 2
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            print(f"repo_guard: cannot read the history of "
                  f"{_shown(folder)}: {_shown(exc)}", file=sys.stderr)
            return 2
    else:
        problems, ignored = _check(folder)
    for p in problems:
        print(f"repo_guard: {_shown(p)}", file=sys.stderr)
    if ignored:
        print(f"repo_guard: note: {ignored} file(s) here are ignored by git "
              "and were not read (they cannot be committed without "
              "git add -f)", file=sys.stderr)
    if any(p.startswith("cannot check") for p in problems):
        return 2
    if problems:
        print(f"repo_guard: {len(problems)} problem(s): remove them from the "
              "repository (and from its history, if they were committed)",
              file=sys.stderr)
        return 1
    print(f"repo_guard: no key, golden set or pack in {_shown(folder.name)}"
          + (", in any commit HEAD reaches" if history else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
