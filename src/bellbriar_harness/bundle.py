"""Evidence bundles.

A bundle is a dated, verifiable record of one evaluation: input hashes,
layer coverage, results, the rulebook's version and digest, timestamps.
Anyone can make one, and anyone holding a key can sign one: every
signature this release makes is self-signed (decision D5).

ATTESTATION SEMANTICS — the authoritative text is the ATTESTATION constant
below, which is embedded verbatim in every bundle and travels with the
evidence. Read that, not this docstring, and keep the two from drifting: a
signature covers a signed *statement* binding the digest to the bundle
format, domain, fetched host, pack, pack version, pack digest, rulebook
version and rulebook digest, not a bare digest. `verify` says what a valid
signature means in its own words, so a forger's attestation text changes
nothing it says.

WHAT IS NOT BUILT (do not describe these in the present tense anywhere):
  * A signing service. `ATTESTED_SUBMISSION` and `ATTESTED_EXECUTION` are
    reserved class names, issued by nothing: remote signing and its
    reference server live outside the package (tools/reference_signer.py)
    until a production signer exists (the ship list's L2, L5).
  * The append-only chain. Bundles carry no `prev_digest`, there is no
    store, and there is no service command that walks a chain.
  * Any coverage or guarantee semantics. A bundle is evidence of a
    measurement and nothing more.

Verification is offline and third-party: `bellbriar-evidence verify
bundle.json --public-key <hex>`. Opposing counsel being able to verify a
bundle is the point.
"""
from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
import os
import re
import unicodedata
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path, PurePath

try:
    from cryptography.hazmat.primitives.asymmetric import ed25519
    HAVE_ED25519 = True
except ImportError:  # pragma: no cover
    HAVE_ED25519 = False

BUNDLE_FORMAT = "bellbriar-evidence/1"
STATEMENT_FORMAT = "bellbriar-signature/1"


class VerificationUnavailable(RuntimeError):
    """Verification could not be carried out (e.g. `cryptography` missing).

    Deliberately not an INVALID verdict: a genuine bundle checked on a machine
    without the Ed25519 library is not a forged bundle, and reporting it as
    INVALID told readers the opposite of the truth.
    """

#: Signing contexts, per docs/CANONICALIZATION.md §4. They prevent a
#: signature made over one artifact type being replayed as a signature over
#: another. Each verifier fixes the context from the kind of artifact it is
#: checking — bundle statements only ever under STATEMENT_FORMAT, pack
#: manifests only ever under "bellbriar-pack/1" — and never lets a field
#: of the presented object choose it: whoever presents a signature writes
#: those fields.
SIGNING_CONTEXTS = {
    STATEMENT_FORMAT: b"bellbriar-signature/1\x00",
    "bellbriar-pack/1": b"bellbriar-pack/1\x00",
}

#: Fields of the bundle that a signature statement binds itself to. At verify
#: time each is compared for strict equality against the bundle's own value;
#: any mismatch invalidates the signature. This is what stops a subscriber
#: obtaining a signature for one domain and attaching it to a bundle for
#: another. `host` is the host a URL run actually fetched (fetch.host), so a
#: run against staging.example.com can never read as example.com itself.
BOUND_FIELDS = ("bundle_format", "domain", "host", "pack", "pack_version",
                "pack_sha256", "rulebook_version", "rulebook_sha256")

#: The members of a signature block (docs/CANONICALIZATION.md §5), all
#: required, no others (N10). Nothing in the block but the statement and
#: the signature bytes is signed, so a member a reader could take for part
#: of the evidence ("verified_by") could be added by anyone, after signing,
#: without breaking the signature.
SIGNATURE_MEMBERS = ("alg", "context", "key_id", "statement", "signature_b64")
SIGNATURE_ALG = "Ed25519"


def normalize_host(value: str) -> str:
    """A host name as evidence records it (docs/CANONICALIZATION.md §5):
    lowercase ASCII with IDNA A-labels, so look-alike Unicode names cannot
    pass for each other; no trailing dot; an IP address in the form a browser
    writes it, IPv6 without brackets. Accepts a URL and takes its host.
    Raises ValueError, with a reason a person can act on, for anything that
    is not a host."""
    text = (value or "").strip()
    if "//" in text:
        try:
            text = urllib.parse.urlparse(text).hostname or ""
        except ValueError:              # e.g. an unclosed [IPv6 literal
            text = ""
    text = _LABEL_DOTS.sub(".", text.lower())
    if text.endswith("."):
        text = text[:-1]                # the root: example.com. is example.com
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
    if text and "%" not in text:        # no zone ids: browsers refuse them
        try:
            address = ipaddress.ip_address(text)
        except ValueError:
            address = None
        if address is not None:
            return (str(address) if address.version == 4
                    else _ipv6_text(address))
    if not text or not _HOST_CHARS.fullmatch(text):
        raise ValueError(f"{value!r} is not a host name such as example.com "
                         "or a URL such as https://example.com/")
    if "" in text.split("."):
        raise ValueError(f"{value!r} has an empty label")
    if any(ch in _IDNA_DEVIATIONS for ch in text):
        # IDNA 2003 (Python's codec) maps these away; IDNA 2008 (browsers)
        # keeps them, so the two name different hosts.
        raise ValueError(f"{value!r} contains a character (ß, ς or a "
                         "zero-width joiner) that the IDNA standards spell "
                         "two ways; pass the name's ASCII xn-- form instead")
    try:
        ascii_host = text.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        hint = ("" if text.isascii() else "; for an internationalized name, "
                "pass its ASCII xn-- form")
        raise ValueError(f"{value!r} is not a valid host name "
                         f"({exc}){hint}") from None
    labels = ascii_host.split(".")
    if not _LDH.fullmatch(ascii_host):
        raise ValueError(f"{value!r} is not a host name such as example.com "
                         "or a URL such as https://example.com/")
    for label in labels:
        if label.startswith("xn--") and not _valid_a_label(label):
            # Python's codec passes ASCII labels through unchecked; a browser
            # decodes them and refuses one that is not a real A-label, so no
            # page could ever be fetched from this name.
            raise ValueError(f"{value!r} has a label, {label!r}, that is not "
                             "a valid internationalized (xn--) label")
    if _NUMERIC_LABEL.fullmatch(labels[-1]):
        # A browser reads a name ending in a number as an IPv4 address.
        raise ValueError(f"{value!r} is neither a host name nor an IPv4 "
                         "address written as four decimal numbers, such as "
                         "192.0.2.1")
    return ascii_host


def _valid_a_label(label: str) -> bool:
    """Could an xn-- label be a real IDNA A-label? Its Punycode must decode
    to text that is not plain ASCII, is in NFC and holds no control
    character, surrogate, private-use code point, noncharacter or space, and
    must re-encode to the same label. Fixed code point ranges, not Unicode
    categories: the answer must not depend on the Unicode version of the
    Python that runs it. Best effort: it refuses what no browser accepts and
    does not check everything a browser does."""
    body = label[4:]
    try:
        text = body.encode("ascii").decode("punycode")
    except (UnicodeError, ValueError):
        return False
    if (not text or text.isascii()
            or text.encode("punycode").decode("ascii") != body
            or unicodedata.normalize("NFC", text) != text):
        return False
    return not any(_refused_code_point(ord(ch)) for ch in text)


def _refused_code_point(cp: int) -> bool:
    return (cp <= 0x1F or 0x7F <= cp <= 0x9F            # controls
            or 0xD800 <= cp <= 0xDFFF                    # surrogates
            or 0xE000 <= cp <= 0xF8FF or cp >= 0xF0000   # private use
            or 0xFDD0 <= cp <= 0xFDEF or cp & 0xFFFE == 0xFFFE
            or cp in _SPACES)


_SPACES = frozenset({0xA0, 0x1680, *range(0x2000, 0x200B), 0x2028, 0x2029,
                     0x202F, 0x205F, 0x3000})
_HOST_CHARS = re.compile(r"[^\s/:@?#\[\]\\%]+")
_LDH = re.compile(r"[a-z0-9_-]+(?:\.[a-z0-9_-]+)*")
_NUMERIC_LABEL = re.compile(r"[0-9]+|0x[0-9a-f]*")
_IDNA_DEVIATIONS = frozenset(map(chr, (0xDF, 0x3C2, 0x200C, 0x200D)))
#: Label separators in IDNA: the full stop and its ideographic, fullwidth
#: and halfwidth forms.
_LABEL_DOTS = re.compile("[.%s]" % "".join(map(chr, (0x3002, 0xFF0E, 0xFF61))))


def url_host(url) -> str | None:
    """The host a verifier reads from fetch.final_url (docs/CANONICALIZATION.md
    §5), or None when the value gives no host. Plain string steps, so that a
    verifier in any language reads the same host, and strict enough that no
    URL parser reads a different one: printable ASCII; an http(s) scheme;
    the authority runs from "//" to the first "/", "?" or "#" and holds no
    backslash and no "@" (the harness records no user name, and
    `https://bank.example@site.example/` reads as the bank to a person);
    the host is made of letters, digits, "-", "_" and "." (inside
    brackets: hex digits, ":" and "."); a port is digits; letters are
    lowercased and one trailing dot removed."""
    if not isinstance(url, str) or not _PRINTABLE_ASCII.fullmatch(url):
        return None
    m = _URL_AUTHORITY.match(url)
    if not m or "\\" in m.group(1) or "@" in m.group(1):
        # Browsers end the authority at a backslash; other parsers do not.
        # A user name before "@" is no part of the host (PR3-4).
        return None
    hostport = m.group(1)
    if hostport.startswith("["):
        end = hostport.find("]")
        if end < 0:
            return None
        host, port = hostport[1:end], hostport[end + 1:]
        if not _IPV6_CHARS.fullmatch(host):
            return None
        if port and not (port[0] == ":" and _PORT.fullmatch(port[1:])):
            return None
    else:
        host, colon, port = hostport.partition(":")
        if not _NAME_CHARS.fullmatch(host):
            return None
        if colon and not _PORT.fullmatch(port):
            return None
    host = host.lower()
    if host.endswith("."):
        host = host[:-1]
    return host or None


_PRINTABLE_ASCII = re.compile(r"[!-~]+")        # 0x21 to 0x7e
_URL_AUTHORITY = re.compile(r"https?://([^/?#]*)", re.IGNORECASE)
_NAME_CHARS = re.compile(r"[A-Za-z0-9._-]+")
_IPV6_CHARS = re.compile(r"[0-9A-Fa-f:.]+")
_PORT = re.compile(r"[0-9]*")


def _ipv6_text(address: ipaddress.IPv6Address) -> str:
    """An IPv6 address as the WHATWG URL standard writes it: lowercase hex
    groups without leading zeros, the first longest run of two or more zero
    groups written as "::". Python's own text for IPv4-mapped addresses
    differs between releases, and a recorded host needs one spelling."""
    packed = address.packed
    groups = [int.from_bytes(packed[i:i + 2], "big") for i in range(0, 16, 2)]
    start, length, i = -1, 0, 0
    while i < 8:
        j = i
        while j < 8 and groups[j] == 0:
            j += 1
        if j - i > length:
            start, length = i, j - i
        i = max(j, i + 1)
    if length < 2:
        return ":".join(f"{g:x}" for g in groups)
    head = ":".join(f"{g:x}" for g in groups[:start])
    tail = ":".join(f"{g:x}" for g in groups[start + length:])
    return f"{head}::{tail}"


def _site(name: str) -> str:
    """www.example.com and example.com name one site (§6 step 6). A name
    with nothing after "www." but a single label (www.com) is its own site."""
    rest = name[4:] if name.startswith("www.") else name
    return rest if "." in rest else name


#: Addresses that are not a public site (docs/CANONICALIZATION.md §6 step
#: 4): (class, what `verify` calls it, ranges), read in order, the first
#: matching row deciding. The blocks the IANA special-purpose address
#: registries (as of their 2025-10-09 update) mark as not globally
#: reachable, multicast, and the deprecated site-local block; the
#: unspecified addresses are loopback, since connecting to one reaches
#: this machine on common systems. One table for the class a capture
#: records (fetch.address_class) and the note verify prints about a
#: recorded host (N13). Listed rather than read from Python's ipaddress
#: flags, whose ranges have moved between releases (6to4's did in 3.12):
#: neither may depend on the interpreter. Everything not listed, and every
#: address in ADDRESS_TABLE_EXCEPTIONS, is public. An address that embeds
#: an IPv4 address (IPv4-mapped, NAT64's well-known prefix, 6to4) is read
#: by that address (_embedded_v4).
ADDRESS_TABLE = (
    ("loopback", "a loopback address", ("127.0.0.0/8", "::1/128")),
    ("loopback", "an unspecified address, which connects to this machine",
     ("0.0.0.0/32", "::/128")),
    ("private", "a private address",
     ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "fc00::/7")),
    ("private", "a shared address (carrier-grade NAT, as Tailscale uses)",
     ("100.64.0.0/10",)),
    ("private", "a link-local address", ("169.254.0.0/16", "fe80::/10")),
    ("private", "a site-local address", ("fec0::/10",)),
    ("private", "a multicast address", ("224.0.0.0/4", "ff00::/8")),
    ("private", "a documentation address",
     ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24", "2001:db8::/32",
      "3fff::/20")),
    ("private", "a benchmarking address", ("198.18.0.0/15", "2001:2::/48")),
    ("private", "a reserved address", ("240.0.0.0/4",)),
    ("private", "a \"this network\" address", ("0.0.0.0/8",)),
    ("private", "a dummy address", ("192.0.0.8/32", "100:0:0:1::/64")),
    ("private", "an IETF protocol address", ("192.0.0.0/24", "2001::/23")),
    ("private", "a deprecated 6to4 relay address", ("192.88.99.0/24",)),
    ("private", "a local-use NAT64 address", ("64:ff9b:1::/48",)),
    ("private", "a discard-only address", ("100::/64",)),
    ("private", "a segment routing (SRv6) address", ("5f00::/16",)),
)
#: Addresses inside ADDRESS_TABLE's blocks that the IANA registries mark as
#: globally reachable (anycast services, AMT, AS112, ORCHIDv2, DETs): public
#: sites as far as the table goes (R1B-9).
ADDRESS_TABLE_EXCEPTIONS = (
    "192.0.0.9/32", "192.0.0.10/32", "2001:1::1/128", "2001:1::2/128",
    "2001:1::3/128", "2001:3::/32", "2001:4:112::/48", "2001:20::/28",
    "2001:30::/28")
_ADDRESS_NETWORKS = tuple((cls, note, tuple(map(ipaddress.ip_network, nets)))
                          for cls, note, nets in ADDRESS_TABLE)
_ADDRESS_EXCEPTIONS = tuple(map(ipaddress.ip_network,
                                ADDRESS_TABLE_EXCEPTIONS))
_NAT64 = ipaddress.ip_network("64:ff9b::/96")
_SIX_TO_FOUR = ipaddress.ip_network("2002::/16")


def _embedded_v4(ip):
    """The IPv4 address an IPv6 address carries, when it carries one
    (IPv4-mapped, NAT64's well-known prefix, 6to4); else `ip` itself."""
    if ip.version == 6:
        if ip.ipv4_mapped is not None:
            return ip.ipv4_mapped
        if ip in _NAT64:
            return ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
        if ip in _SIX_TO_FOUR:
            return ipaddress.IPv4Address((int(ip) >> 80) & 0xFFFFFFFF)
    return ip


def address_kind(ip) -> tuple[str, str] | None:
    """(class, note) from ADDRESS_TABLE for an address that is not a
    public site, or None for a public one."""
    ip = _embedded_v4(ip)
    if any(ip.version == n.version and ip in n for n in _ADDRESS_EXCEPTIONS):
        return None
    for cls, note, networks in _ADDRESS_NETWORKS:
        if any(ip.version == n.version and ip in n for n in networks):
            return cls, note
    return None


def host_kind(host) -> tuple[str, str] | None:
    """(class, note) for a recorded host that is not a public site:
    `localhost` or a name below it (RFC 6761), or an address in
    ADDRESS_TABLE, including one a browser reads from a shorthand such as
    `127.1` or `2130706433`. None for any other name or address: a name
    says nothing about where it points."""
    if not isinstance(host, str) or not host:
        return None
    if host == "localhost" or host.endswith(".localhost"):
        return "loopback", "a loopback name"
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        # A shorthand a browser reads as an address (127.1, 2130706433,
        # 0x7f.0.0.1): the harness never records one, a hand-built bundle
        # can.
        address = _ipv4_shorthand(host)
        if address is None:
            return None
    return address_kind(address)


def host_note(host) -> str | None:
    """What `verify` says about a recorded host that is not a public site
    (host_kind), or None."""
    kind = host_kind(host)
    return kind[1] if kind else None


def _ipv4_shorthand(host: str):
    """The IPv4 address the WHATWG URL standard reads from a host whose last
    label is a number (decimal, 0x hex or 0-led octal parts, the last part
    filling the remaining bytes), or None."""
    parts = host.split(".")
    if parts and parts[-1] == "":
        parts.pop()
    if not parts or len(parts) > 4 or not _NUMERIC_LABEL.fullmatch(
            parts[-1].lower()):
        return None
    numbers = []
    for part in parts:
        low = part.lower()
        if low.startswith("0x"):
            base, digits = 16, low[2:]
        elif len(low) > 1 and low.startswith("0"):
            base, digits = 8, low[1:]
        else:
            base, digits = 10, low
        try:
            numbers.append(int(digits, base) if digits else 0)
        except ValueError:
            return None
    if any(n > 255 for n in numbers[:-1]) or \
            numbers[-1] >= 256 ** (5 - len(numbers)):
        return None
    value = numbers[-1] + sum(n * 256 ** (3 - i)
                              for i, n in enumerate(numbers[:-1]))
    return ipaddress.IPv4Address(value)


def host_scope(host: str | None, domain: str | None) -> str:
    """How a fetched host relates to the stated domain, both normalized
    (docs/CANONICALIZATION.md §6 step 6):
      "same"      — the domain itself, or its www. form either way round;
      "subdomain" — below the domain's site (staging.example.com for
                    example.com or www.example.com);
      "unrelated" — neither; an address relates only to itself;
      "unstated"  — one of them is missing (a file run, or no --domain).
    """
    if not host or not domain:
        return "unstated"
    if host == domain:
        return "same"
    if any(":" in name or _ADDRESS.fullmatch(name) for name in (host, domain)):
        return "unrelated"            # addresses have no www. or subdomains
    if _site(host) == _site(domain):
        return "same"
    return "subdomain" if host.endswith("." + _site(domain)) else "unrelated"


#: An address, by spelling (§5): digits and dots, or anything with a colon.
_ADDRESS = re.compile(r"[0-9.]+")

#: Attestation classes (docs/CANONICALIZATION.md §5.1). This release signs
#: only SELF_SIGNED. The other two are reserved names that nothing issues:
#: a signing service that checks a subscription (L2), and a runner that
#: fetches and evaluates itself. verify_bundle reads either as no more
#: than a self-signed signature.
SELF_SIGNED = "self-signed"
ATTESTED_SUBMISSION = "attested-submission"
ATTESTED_EXECUTION = "attested-execution"
RESERVED_CLASSES = (ATTESTED_SUBMISSION, ATTESTED_EXECUTION)

ATTESTATION = (
    "A signature on this bundle covers a signed statement, not a bare "
    "digest. The statement records the bundle digest together with the "
    "bundle format, domain, fetched host, pack, pack version, pack digest, "
    "rulebook version and rulebook digest, and verification fails unless "
    "every one of them matches this bundle and, where a domain is stated, "
    "any fetched host is that domain, its www. form, or a host below the "
    "site they name. The signature's class is 'self-signed': whoever held "
    "the key signed values the client computed, and no one else checked "
    "anything. "
    "A valid signature therefore shows only that the holder of that key "
    "signed this exact statement, and that nothing in the bundle outside "
    "its signature block has changed since. It does NOT show that the "
    "evaluation was executed correctly or on the stated inputs, or that "
    "its results were not edited before signing: the client computed "
    "them. Where this bundle has a `fetch` block, or a page has its own "
    "capture record (`fetch`), that is the client's record of a capture "
    "at the recorded time, of a live page or of a build the client served "
    "itself; no signature attests that a capture took place as recorded. "
    "A page may have differed before or after, and each recorded snapshot "
    "hash identifies the bytes the client reports it evaluated. Findings "
    "in markup the "
    "client attributed to a third-party vendor's script, by the origin of "
    "the script that inserted it, are reported but do not count as "
    "failures in the score, though a rule that applies to such markup "
    "counts as applicable, and a finding about the page as a whole counts "
    "whatever markup it rests on; that attribution can be wrong. No "
    "signature is a "
    "determination of WCAG conformance, legal compliance, or fitness for "
    "any purpose."
)

#: What verify_bundle says a valid signature shows, in its own words: the
#: bundle's `attestation` text is written by whoever made the bundle.
SELF_SIGNED_MEANING = (
    "it shows that the holder of this key signed this statement and that "
    "the bundle has not changed since; not that its results are correct "
    "or unedited")

#: Key ids of the demonstration keys that have signed the repository's
#: worked example (examples/evidence/). They are in no trust path: their
#: private halves are not published, and they sign nothing but that
#: example. verify_bundle names them in its result, so the example — or
#: anything else such a key signed — cannot pass for evidence from a
#: production signer. A rotation adds the new id here
#: (tests/test_examples.py fails until it does).
DEMO_KEY_IDS = frozenset({
    "715d1ac271975e48",          # 2026-09-16 to 2026-10-01; private half lost
    "04db99f6ed92cfac",          # from 2026-10-01
})

#: Key ids whose private keys are printed in this repository's own format
#: specification, as test vectors (docs/CANONICALIZATION.md §8). Anyone can
#: sign with them, so verify_bundle says a signature under one is evidence
#: of nothing.
PUBLISHED_TEST_KEY_IDS = frozenset({"172f109161589572"})


# ---------------------------------------------------------------------------
# Canonicalization + digest
# ---------------------------------------------------------------------------

#: Integers up to this magnitude are exact in an IEEE-754 double, the number
#: type of JavaScript and of most JSON parsers.
_MAX_EXACT_INT = 2 ** 53
#: Below this magnitude Python writes a decimal in exponent form (`5e-05`)
#: while JavaScript still writes it out (`0.00005`).
_MIN_DECIMAL = 1e-4
#: Deepest nesting of objects and arrays, counting the bundle itself as 1.
#: Bundles the harness writes reach about 11. Without a fixed limit each
#: verifier stops at its own recursion depth, and they disagree.
MAX_DEPTH = 32
_SURROGATE = re.compile("[\ud800-\udfff]")
_PLAIN_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class MalformedBundle(ValueError):
    """The input is not a well-formed bundle (docs/CANONICALIZATION.md §2,
    §6). That is not a verdict: nothing can be concluded about a document
    whose bytes do not pin down one meaning."""


def _key_path(path: str, key: str) -> str:
    # JSON-escaped unless plainly an identifier, so a key cannot smuggle
    # control characters into an error message a terminal will render.
    return (f"{path}.{key}" if _PLAIN_KEY.fullmatch(key)
            else f"{path}[{json.dumps(key)}]")


def _canonical_value(v, path="$", depth=0):
    """Normalize a value so its canonical serialization is language-neutral.

    The trap this exists for: Python and JavaScript print some numbers
    differently. Python's json emits `1.0` for an integer-valued float where
    JavaScript's JSON.stringify emits `1` — and every bundle with a 100% pass
    rate contains `1.0`. Below 0.0001 Python switches to exponent form
    (`5e-05`) where JavaScript does not (`0.00005`), and above 2^53 the two
    print different digits for the same double. A verifier in the other
    language would parse the file, re-serialize, and get a different digest.

    So a canonical number is an integer of magnitude at most 2^53 (integer-
    valued floats become integers), or a non-integer of magnitude at least
    0.0001; in that range both languages print identical bytes. Anything
    else is refused, never serialized: a digest that only Python reproduces
    is worse than an error. See docs/CANONICALIZATION.md §2.
    """
    if v is None or isinstance(v, bool):
        return v
    if isinstance(v, str):
        if not v.isascii() and _SURROGATE.search(v):
            raise ValueError(f"{path}: string contains a lone surrogate, "
                             "which has no UTF-8 encoding")
        return v
    if isinstance(v, int):
        if abs(v) > _MAX_EXACT_INT:
            raise ValueError(f"{path}: integer exceeds 2^53; not exactly "
                             "representable by every verifier")
        return v
    if isinstance(v, float):
        if v != v or v in (float("inf"), float("-inf")):
            raise ValueError(f"{path}: NaN/Infinity are not JSON")
        if v == int(v):
            if abs(v) > _MAX_EXACT_INT:
                raise ValueError(
                    f"{path}: {v!r} exceeds 2^53, where Python and "
                    "JavaScript print different digits for the same number")
            return int(v)          # 1.0 -> 1, -0.0 -> 0 (matches JavaScript)
        if abs(v) < _MIN_DECIMAL:
            raise ValueError(
                f"{path}: {v!r} is smaller than 0.0001, where Python prints "
                "an exponent and JavaScript does not; round it (producers "
                "round every decimal to four places)")
        return v
    if isinstance(v, (dict, list, tuple)) and depth >= MAX_DEPTH:
        raise ValueError(f"{path}: nested deeper than {MAX_DEPTH} levels")
    if isinstance(v, dict):
        out = {}
        for k, x in v.items():
            if not isinstance(k, str) or not k.isascii():
                raise ValueError(f"{path}: object keys must be ASCII strings "
                                 "so that sort order is unambiguous")
            out[k] = _canonical_value(x, _key_path(path, k), depth + 1)
        return out
    if isinstance(v, (list, tuple)):
        return [_canonical_value(x, f"{path}[{i}]", depth + 1)
                for i, x in enumerate(v)]
    raise TypeError(f"{path}: {type(v).__name__} is not a JSON type")


def canonical_bytes(obj: dict) -> bytes:
    """Deterministic JSON per docs/CANONICALIZATION.md §2: keys sorted by
    code point, no whitespace, UTF-8 with non-ASCII emitted raw, integer-
    valued floats serialized as integers; NaN/Infinity, numbers outside the
    canonical range (§2 rule 4) and lone surrogates rejected."""
    return json.dumps(_canonical_value(obj), sort_keys=True,
                      separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def conform(v):
    """Bring a value the harness produced inside the canonical rules, so a
    bundle it builds can always be canonicalized: every non-integer number
    rounded to four decimal places (the precision the spec promises, which
    also keeps every decimal clear of the 0.0001 floor) and any lone
    surrogate in a string replaced with U+FFFD. Values that rounding cannot
    repair (NaN, Infinity, integers beyond 2^53) are left for canonical_bytes
    to refuse, and the CLI reports that as an error instead of writing a
    bundle nobody can verify.
    """
    if isinstance(v, float):
        if v == v and v not in (float("inf"), float("-inf")) and v != int(v):
            return round(v, 4)
        return v
    if isinstance(v, str):
        return _SURROGATE.sub("�", v) if not v.isascii() else v
    if isinstance(v, dict):
        return {k: conform(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [conform(x) for x in v]
    return v


def _number_text(v: float) -> str:
    """How §2 writes a finite double (exact for the integer case)."""
    return str(int(v)) if v == int(v) else repr(v)


_NUMBER = re.compile(r"(-?)(\d+)(?:\.(\d+))?(?:[eE]([+-]?\d+))?")


def _decimal_key(literal: str) -> tuple:
    """A JSON number literal as (sign, significant digits, exponent), so two
    spellings of one decimal value compare equal: "1.0" and "1", "1e2" and
    "100", "0e99999999999999999999" and "0". Exact at any exponent, which a
    Decimal context is not."""
    m = _NUMBER.fullmatch(literal)
    if m is None:
        raise MalformedBundle(f"{_short(literal)} is not a JSON number")
    sign, whole, frac, exp = m.group(1), m.group(2), m.group(3) or "", m.group(4)
    digits = (whole + frac).lstrip("0")
    if not digits:
        return ("", "0", 0)
    try:
        exponent = int(exp or 0)
    except ValueError:   # longer than Python converts; far outside a double
        raise MalformedBundle(f"number {_short(literal)} is outside the "
                              "range of a double") from None
    stripped = digits.rstrip("0")
    return (sign, stripped,
            exponent - len(frac) + len(digits) - len(stripped))


def _short(literal: str, limit: int = 40) -> str:
    return literal if len(literal) <= limit else literal[:limit - 3] + "…"


def load_bundle(text: str) -> dict:
    """Parse a bundle file's text the way docs/CANONICALIZATION.md §6 asks.

    This is the text half of §6. It refuses a file that can be read two
    ways, which no check on the parsed value can catch afterwards:
      * duplicate member names — parsers disagree on which one wins, and a
        reader sees the first while the digest covers the last;
      * a number literal that is not exactly the §2 text of the double it
        parses to (`1e999`, `0.67570000000000001`); other spellings of the
        same number (`1.0`, `1e2`) are fine;
      * NaN and Infinity, a byte-order mark, and anything that is not a
        JSON object.
    The value half — §2 anywhere in the file, types, nesting depth — is
    checked by verify_bundle(). Raises MalformedBundle.
    """
    def pairs(items):
        obj = {}
        for k, v in items:
            if k in obj:
                raise MalformedBundle(
                    f"duplicate member name {json.dumps(k)}: parsers "
                    "disagree about which value it has")
            obj[k] = v
        return obj

    def number(literal: str) -> float:
        v = float(literal)
        if v != v or v in (float("inf"), float("-inf")):
            raise MalformedBundle(
                f"number {_short(literal)} does not fit in a double")
        if v == int(v) and abs(v) > _MAX_EXACT_INT:
            raise MalformedBundle(f"number {_short(literal)} exceeds 2^53")
        if _decimal_key(literal) != _decimal_key(_number_text(v)):
            raise MalformedBundle(
                f"number {_short(literal)} is read as {_number_text(v)}: a "
                "double cannot hold it exactly as written")
        return v

    def constant(name: str):
        raise MalformedBundle(f"{name} is not JSON")

    if text.startswith("﻿"):
        raise MalformedBundle("the file starts with a byte-order mark")
    try:
        obj = json.loads(text, object_pairs_hook=pairs, parse_float=number,
                         parse_constant=constant)
    except MalformedBundle:
        raise
    except (ValueError, RecursionError, ArithmeticError) as exc:
        raise MalformedBundle(f"not valid JSON: {exc}") from None
    if not isinstance(obj, dict):
        raise MalformedBundle("a bundle is a JSON object")
    return obj


#: The largest file verify and inspect read as a bundle (R5B-11). A run of
#: the most pages a run takes, with hundreds of findings on each, stays far
#: below it; a larger file is refused rather than read into memory.
MAX_BUNDLE_FILE = 256 * 1024 * 1024


class UnreadableBundle(MalformedBundle):
    """A file that cannot be read as a bundle at all: not a regular file,
    too large, or unreadable. Nothing is concluded about it."""


def read_bundle_bytes(path) -> bytes:
    """The bytes of the file `path` names, read only if it is a regular
    file of at most MAX_BUNDLE_FILE bytes: a FIFO would block verify for
    ever, and a device or a huge file would fill memory (R5B-11). The
    descriptor is checked, not the name. Raises UnreadableBundle."""
    import stat as _stat
    flags = (os.O_RDONLY | getattr(os, "O_NONBLOCK", 0)
             | getattr(os, "O_NOCTTY", 0) | getattr(os, "O_BINARY", 0))
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise UnreadableBundle(f"cannot open it ({exc.strerror or 'error'})"
                               ) from None
    try:
        st = os.fstat(fd)
        if not _stat.S_ISREG(st.st_mode):
            raise UnreadableBundle("it is not a regular file (a directory, "
                                   "FIFO or device)")
        if st.st_size > MAX_BUNDLE_FILE:
            raise UnreadableBundle(f"it is {st.st_size} bytes, more than the "
                                   f"{MAX_BUNDLE_FILE} a bundle may be")
        chunks, size = [], 0
        while True:
            chunk = os.read(fd, 1 << 20)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_BUNDLE_FILE:
                raise UnreadableBundle(f"it is more than the "
                                       f"{MAX_BUNDLE_FILE} bytes a bundle "
                                       "may be")
            chunks.append(chunk)
    except OSError as exc:
        raise UnreadableBundle(f"cannot read it ({exc.strerror or 'error'})"
                               ) from None
    finally:
        os.close(fd)
    return b"".join(chunks)


def read_bundle(path) -> dict:
    """load_bundle() on a file (read_bundle_bytes), decoded as strict UTF-8
    (§6). A lenient decoder turns a stray byte into U+FFFD, and would verify
    a file whose bytes were never signed."""
    try:
        text = read_bundle_bytes(path).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MalformedBundle(f"not valid UTF-8 ({exc.reason} at byte "
                              f"{exc.start})") from None
    return load_bundle(text)


def bundle_digest(bundle: dict) -> str:
    body = {k: v for k, v in bundle.items() if k != "signature"}
    return hashlib.sha256(canonical_bytes(body)).hexdigest()


def recorded_path(path, arg=None) -> str:
    """The name a run records for an input file: never an absolute path or
    one with `..`, which would put a home directory or a client's folder
    layout into evidence that cannot be redacted once signed. A relative
    path without `..` is recorded as given; anything else, relative to the
    parent of the argument it came from (`arg`, the file or directory as
    passed; the file itself by default), so `/home/u/client/dist` gives
    `dist/index.html`. Always with forward slashes. A path with a drive or
    a root (`/x`, `C:x`, and on Windows `\\x`) is never "relative". Either
    way, a home directory the name would hold is left out, with what is
    above it (`home/alice/site`, typed in `/`, gives `site/index.html`:
    S5 re-review)."""
    p = PurePath(path)
    if not p.anchor and ".." not in p.parts:
        rel = p.parts
        parts = PurePath(os.path.abspath(path)).parts
        for j in range(max(len(parts) - len(rel), 1), len(parts) - 1):
            if home_folder(parts, j):
                rel = parts[j + 1:]
        return name_escaped(_not_a_site(PurePath(*rel).as_posix()))
    base = os.path.dirname(os.path.abspath(arg if arg is not None else path))
    parts = PurePath(os.path.abspath(path)).parts
    rel = PurePath(os.path.relpath(os.path.abspath(path), base)).parts
    # A home directory inside the name would put a user's name into
    # evidence (`bellbriar-eval ~` recorded "alice/site/index.html"): the
    # name starts below it (R5B-22).
    first = len(parts) - len(rel)
    for j in range(max(first, 1), len(parts) - 1):
        if home_folder(parts, j):
            rel = parts[j + 1:]
    return name_escaped(_not_a_site(PurePath(*rel).as_posix()))


def home_folder(parts: tuple, j: int) -> bool:
    """Is parts[j] (of an absolute path's parts) a home directory:
    /home/<user>, /Users/<user>, C:\\Users\\<user>, /root, or the
    operator's own?"""
    if j >= 1 and parts[j - 1].lower() in ("home", "users",
                                            "documents and settings"):
        return True
    if j == 1 and parts[j] == "root":
        return True
    home = os.path.expanduser("~")
    return (len(home.strip("/\\")) > 1
            and os.path.normcase(str(PurePath(*parts[:j + 1])))
            == os.path.normcase(os.path.abspath(home)))


def name_escaped(name: str) -> str:
    """A recorded name, one to one with the file's own: each undecodable
    byte of the name (a lone surrogate, as Python reads a name that is not
    UTF-8) written %XX, and each "%" written %25. A bundle replaces a lone
    surrogate with U+FFFD, so two names that differ only there would read
    as one (R5B-9); and "a%80.html" must not read as the file whose name
    holds the byte 0x80, which made two files one name (R5D-1)."""
    if "%" not in name and (name.isascii() or not _SURROGATE.search(name)):
        return name

    def one(m: re.Match) -> str:
        ch = m.group(0)
        if ch == "%":
            return "%25"
        n = ord(ch)
        return f"%{n - 0xDC00:02X}" if 0xDC80 <= n <= 0xDCFF else "\ufffd"
    return _ESCAPED_IN_NAME.sub(one, name)


_ESCAPED_IN_NAME = re.compile("[%\ud800-\udfff]")


def input_manifest(paths: list, names: list | None = None,
                   digests: list | None = None) -> list[dict]:
    """`names`: what to record for each path (recorded_path), as the CLI
    worked them out from its arguments; by default each file's own.
    `digests`: for each path, the (sha256, bytes) of what the run read
    when it evaluated it, or None to read the file now. A file read again
    for the manifest could have changed since it was evaluated (R5B-10)."""
    out = []
    for i, p in enumerate(paths):
        known = digests[i] if digests else None
        if known is None:
            data = Path(p).read_bytes()
            known = (hashlib.sha256(data).hexdigest(), len(data))
        out.append({"path": names[i] if names else recorded_path(p),
                    "sha256": known[0], "bytes": known[1]})
    return out


def build_bundle(run: dict, site: dict, paths: list,
                 judged_summary: dict | None = None,
                 judged_pages: list | None = None,
                 pack: dict | None = None,
                 domain: str | None = None,
                 fetch_result=None, names: list | None = None,
                 inputs: list | None = None,
                 baseline: dict | None = None) -> dict:
    """Assemble an unsigned evidence bundle from a completed run.

    `inputs` is the manifest of what was measured, as the CLI worked it
    out: for a URL run, each page's snapshot (its hash is over the exact
    bytes the rules ran on, so the evidence identifies what was measured
    rather than naming a URL whose content has since moved on); for a file
    run, each file under recorded_path (`names`), and for a --render run
    also every other file its server sent. By default: the files in
    `paths`, or the one capture `fetch_result` (a URL run of one page).

    `run["fetch"]` is the run's record of what it fetched (a URL run; None
    for files, rendered or not) and each page's own capture record is its
    `fetch`.

    `baseline` is the record of the --baseline the run's gate compared
    with (baseline.record: its SHA-256, and how many of the run's findings
    it did not list), or None (A10). The bundle lists every finding either
    way.
    """
    if inputs is None:
        inputs = ([fetch_result.manifest_entry()] if fetch_result is not None
                  else input_manifest(paths, names))
    rename = ({} if fetch_result is not None else
              {str(p): rec["path"] for p, rec in zip(paths, inputs)})
    if judged_pages:
        judged_pages = [{**jp, "path": rename.get(jp.get("path"), jp.get("path"))}
                        if isinstance(jp, dict) else jp for jp in judged_pages]
    if "fetch" in run:
        fetch = run["fetch"]
    elif fetch_result is not None:
        fetch = {"final_url": fetch_result.final_url,
                 "host": fetch_result.host, "pages": 1,
                 "list": {"kind": "urls", "max_pages": 1}}
    else:
        fetch = None
    # What kind of verdict each rule gives (the rulebook's verdict_basis:
    # sc, heuristic, policy, best-practice, review), in each finding, so
    # the bundle says it without the rulebook beside it (S5-6).
    from .engine import verdict_basis
    basis = verdict_basis(run.get("rulebook") or {})
    pages = []
    for page, pscore in zip(run["pages"], site["pages"]):
        record = getattr(page, "fetch", None)
        if record is None and fetch_result is not None and len(run["pages"]) == 1:
            record = fetch_result.fetch_block()
        pages.append({
            "path": rename.get(page.path, page.path),
            "fetch": record,
            "score": pscore,
            "findings": [{
                "rule_id": f.rule_id, "verdict": f.verdict,
                "impact": f.impact, "message": f.message,
                "line": f.line, "snippet": f.snippet,
                "selector": f.selector,
                "origin": f.origin, "origin_detail": f.origin_detail,
                "scored": f.owned,
                "verdict_basis": basis.get(f.rule_id, ""),
            } for rr in page.results for f in rr.findings],
            "not_applicable_rules": [rr.rule_id for rr in page.results
                                     if not rr.applicable],
        })
    return conform({
        "bundle_format": BUNDLE_FORMAT,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tool": run["tool"],
        "rulebook_version": run["rulebook_version"],
        # The rules themselves, not only their release (P1-08): bound into
        # a signature beside the version.
        "rulebook_sha256": run.get("rulebook_sha256"),
        "domain": domain,
        "pack": pack,          # from pack.pack_reference(); None = unpinned
        "inputs": inputs,
        "fetch": fetch,
        "layers": run["layers"],
        "coverage_note": run["coverage_note"],
        "site": {k: v for k, v in site.items() if k != "pages"},
        "pages": pages,
        "judged": ({"summary": judged_summary, "pages": judged_pages}
                   if judged_summary else None),
        "baseline": baseline,
        "attestation": ATTESTATION,
        "signature": None,
    })


# ---------------------------------------------------------------------------
# Signature statements
# ---------------------------------------------------------------------------

def bundle_bound_values(bundle: dict) -> dict:
    """The bundle's own values for every field a statement binds to."""
    pack = bundle.get("pack")
    if pack is None:
        pack = {}
    elif not isinstance(pack, dict):
        # A string such as "wcag@1.0.0" would bind as an unpinned pack while
        # showing a reader a pack nobody authorized.
        raise MalformedBundle("pack must be an object or null")
    fetch = bundle.get("fetch")
    if fetch is None:
        host = None                     # a file run: nothing was fetched
    elif not isinstance(fetch, dict):
        raise MalformedBundle("fetch must be an object or null")
    else:
        # The host is read from final_url, the capture's own record, so the
        # file cannot name one host to a reader and bind another (§5, §6).
        host = url_host(fetch.get("final_url"))
        if host is None:
            raise MalformedBundle("fetch.final_url is not an http(s) URL in "
                                  "printable ASCII with a host")
        if "host" in fetch and fetch["host"] != host:
            raise MalformedBundle(
                f"fetch.host is {_short(repr(fetch['host']))} but "
                f"fetch.final_url names {host!r}")
    _check_page_records(bundle.get("pages"), fetch, host)
    _check_inputs(bundle.get("inputs"), fetch, host)
    _check_judged(bundle.get("judged"), bundle.get("pages"))
    return {
        "bundle_format": bundle.get("bundle_format"),
        "domain": bundle.get("domain"),
        "host": host,
        "pack": pack.get("name"),
        "pack_version": pack.get("version"),
        # The pack's content, as the rulebook's digest is the rulebook's: a
        # version names a release, and a signer that authorizes packs can
        # name the content it authorized (SA-7).
        "pack_sha256": pack.get("manifest_sha256"),
        "rulebook_version": bundle.get("rulebook_version"),
        "rulebook_sha256": bundle.get("rulebook_sha256"),
    }


_LOOPBACK_V4 = re.compile(r"127(?:\.(?:25[0-5]|2[0-4][0-9]|1[0-9][0-9]|"
                          r"[1-9]?[0-9])){3}")


def loopback_host(host: str) -> bool:
    """Is `host`, as url_host reads it, this machine: `localhost` or a name
    below it, a canonical dotted-quad 127.x.x.x, or `::1` (§5)?"""
    return (host == "localhost" or host.endswith(".localhost")
            or host == "::1" or _LOOPBACK_V4.fullmatch(host) is not None)


def _check_page_records(pages, fetch, host) -> None:
    """The pages a bundle shows were fetched where its statement says (§5
    "Pages", §6). In a URL run (`fetch` is the run's record, `host` read
    from its final_url) every page has its own capture record
    (`pages[i].fetch`), is named by the URL it was fetched from, and names
    `host`, and `fetch.pages` counts the pages. In a run that fetched
    nothing (`fetch` null) either no page has a record (files read as they
    are) or every page has one naming this machine (a build rendered on
    loopback). A file that shows one host and binds another is
    malformed."""
    if pages is None:
        return
    if not isinstance(pages, list):
        raise MalformedBundle("pages must be an array")
    records = []
    for i, page in enumerate(pages):
        if not isinstance(page, dict):
            raise MalformedBundle(f"pages[{i}] is not an object")
        if "fetch" not in page:
            raise MalformedBundle(
                f"pages[{i}] has no fetch member: every page records its "
                "capture, or null for a file read as it is (SA-4)")
        record = page.get("fetch")
        if record is not None and not isinstance(record, dict):
            raise MalformedBundle(f"pages[{i}].fetch must be an object or "
                                  "null")
        records.append(record)
    if fetch is not None:
        count = fetch.get("pages")
        # A number, as JSON has them: 2 and 2.0 are one value (§2).
        if isinstance(count, bool) or not isinstance(count, (int, float)) \
                or count != len(pages):
            raise MalformedBundle(
                f"fetch.pages is {_short(repr(count))}, but the bundle has "
                f"{len(pages)} page(s): a URL run counts the pages it shows")
    elif any(r is not None for r in records) and None in records:
        raise MalformedBundle(
            "some pages have a capture record (fetch) and some do not: a run "
            "that fetched nothing has none (files read as they are) or one "
            "for every page (a build rendered on this machine)")
    for i, (page, record) in enumerate(zip(pages, records)):
        if record is None:
            if fetch is not None:
                raise MalformedBundle(
                    f"pages[{i}] has no capture record (fetch): every page of "
                    "a URL run has one")
            continue
        page_host = url_host(record.get("final_url"))
        if page_host is None:
            raise MalformedBundle(f"pages[{i}].fetch.final_url is not an "
                                  "http(s) URL in printable ASCII with a host")
        if "host" in record and record["host"] != page_host:
            raise MalformedBundle(
                f"pages[{i}].fetch.host is {_short(repr(record['host']))} but "
                f"its final_url names {page_host!r}")
        if host is not None and page_host != host:
            raise MalformedBundle(
                f"pages[{i}] was fetched from {page_host!r}, not "
                f"{host!r} (fetch.final_url): a run binds one host")
        if host is None and not loopback_host(page_host):
            raise MalformedBundle(
                f"pages[{i}].fetch names {page_host!r}, but the bundle "
                "records no fetch: a page of a file run can only have been "
                "served from this machine (loopback)")
        if fetch is not None and page.get("path") != record.get("final_url"):
            raise MalformedBundle(
                f"pages[{i}].path is not its fetch.final_url: a URL run's "
                "page is named by the URL it was fetched from")
    if fetch is None:
        for i, page in enumerate(pages):
            if _names_site(page.get("path")):
                raise MalformedBundle(
                    f"pages[{i}].path names a site, but the bundle records "
                    "no fetch: a run that fetched nothing names its pages by "
                    "their files")
            if _not_as_recorded(page.get("path")):
                raise MalformedBundle(
                    f"pages[{i}].path is no name a run records for a file: "
                    + _AS_RECORDED)


def _names_site(path) -> bool:
    """Does a recorded path name a site rather than a file: begin, after
    any control, format, space or separator characters, with "http:" or
    "https:" in any case and then a slash or a backslash? A person reads
    " https://x", "\u200bhttps://x" or "https:/x" as a URL too, and a
    browser corrects the last (§5 "Pages", R5B-18)."""
    if not isinstance(path, str):
        return False
    i = 0
    while i < len(path) and unicodedata.category(path[i]) in _LEADING:
        i += 1
    return _SITE_URL.match(path, i) is not None


_SITE_URL = re.compile(r"https?:[/\\]", re.IGNORECASE)
_LEADING = frozenset(("Cc", "Cf", "Zs", "Zl", "Zp"))


def _not_as_recorded(path) -> bool:
    """Is `path`, a name a bundle gives a file, one no run records: its
    first part holds a colon or a character outside ASCII with no "./"
    before it (_not_a_site)? A person can read such a name as a site
    (U+3164 or U+2800 before "https://", "https\uff1a//", Cyrillic
    "\u04bbttps://"), so a verifier refuses it rather than list the
    characters that look like others (L96)."""
    return isinstance(path, str) and _not_a_site(path) != path


_AS_RECORDED = ("its first part holds a colon or a character outside "
                "ASCII, which a run writes after \"./\" so that no one "
                "reads the name as a site")


def _not_a_site(name: str) -> str:
    """A recorded file name written "./" first when its first part holds a
    colon or any character outside ASCII (a folder named "https:",
    "\u3164https:", "https\uff1a" or "\u04bbttps:"), so that neither a
    verifier (_names_site) nor a person reads it as a site. Not a list of
    the characters that look like a colon or a letter: no list of them is
    whole (R5B-18, R5D-12, R5F-1)."""
    first = name.split("/", 1)[0]
    if ":" in first or not first.isascii() or _names_site(name):
        return "./" + name
    return name


def _check_inputs(inputs, fetch, host) -> None:
    """`inputs` is an array of objects, and one that names a site is the
    snapshot of a page (`kind` "url-snapshot") on the host the statement
    binds: a URL run's inputs are its pages, and a run that fetched nothing
    has no such input (§5 "Pages")."""
    if inputs is None:
        return
    if not isinstance(inputs, list):
        raise MalformedBundle("inputs must be an array")
    for i, entry in enumerate(inputs):
        if not isinstance(entry, dict):
            raise MalformedBundle(f"inputs[{i}] is not an object")
        path = entry.get("path")
        snapshot = entry.get("kind") == "url-snapshot"
        if not (_names_site(path) or snapshot):
            if _not_as_recorded(path):
                raise MalformedBundle(
                    f"inputs[{i}].path is no name a run records for a "
                    "file: " + _AS_RECORDED)
            continue                                 # a file
        if fetch is None:
            raise MalformedBundle(
                f"inputs[{i}] names a site, but the bundle records no fetch: "
                "a run that fetched nothing lists files")
        if not snapshot or url_host(path) != host:
            raise MalformedBundle(
                f"inputs[{i}] is not a snapshot of a page on {host!r}: a URL "
                "run's inputs are its pages")


def _check_judged(judged, pages) -> None:
    """The judged track's pages are pages of the bundle (§5 "Pages")."""
    if judged is None:
        return
    if not isinstance(judged, dict):
        raise MalformedBundle("judged must be an object or null")
    listed = judged.get("pages")
    if listed is None:
        return
    if not isinstance(listed, list):
        raise MalformedBundle("judged.pages must be an array")
    names = {p["path"] for p in pages if isinstance(p, dict)
             and isinstance(p.get("path"), str)} \
        if isinstance(pages, list) else set()
    for i, entry in enumerate(listed):
        if not isinstance(entry, dict) or not isinstance(
                entry.get("path"), str) or entry["path"] not in names:
            raise MalformedBundle(
                f"judged.pages[{i}] is not one of the bundle's pages")


def build_statement(bound: dict, key_id: str, signer: str,
                    attestation_class: str, digest: str,
                    signed_at: str | None = None) -> dict:
    """The object that actually gets signed.

    The signer never sees the bundle body — that is deliberate, so a
    customer's HTML never leaves their machine. The client therefore states
    the domain and pack. What makes that safe is this statement: the signer
    records the values it authorized *inside the signed object*, so a client
    that told the signer one thing and put another in the bundle produces a
    statement that no longer matches, and verification fails.
    """
    stmt = {
        "statement_format": STATEMENT_FORMAT,
        "bundle_digest_sha256": digest,
        "attestation_class": attestation_class,
        "key_id": key_id,
        "signer": signer,
        "signed_at": signed_at or datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
    }
    for field in BOUND_FIELDS:
        stmt[field] = bound.get(field)
    for field, value in stmt.items():
        # §5: every statement value is a string or null. Checked here so a
        # bad value fails at signing, not later as an unverifiable bundle.
        if value is not None and not isinstance(value, str):
            raise ValueError(f"statement field {field!r} must be a string "
                             f"or null, not {type(value).__name__}")
    return stmt


def statement_digest(statement: dict) -> str:
    return hashlib.sha256(canonical_bytes(statement)).hexdigest()


def _sign_statement(statement: dict, priv) -> str:
    """Sign a bundle statement. Only a statement is ever signed here, and
    only under the statement context: this function is not a general
    signer that takes its context from the object it is handed."""
    if statement.get("statement_format") != STATEMENT_FORMAT:
        raise ValueError(
            f"refusing to sign: statement_format is "
            f"{statement.get('statement_format')!r}, not {STATEMENT_FORMAT!r}")
    msg = SIGNING_CONTEXTS[STATEMENT_FORMAT] + bytes.fromhex(
        statement_digest(statement))
    return base64.b64encode(priv.sign(msg)).decode("ascii")


# ---------------------------------------------------------------------------
# Keys and local signing (dev / service side)
# ---------------------------------------------------------------------------

def generate_keypair() -> tuple[str, str, str]:
    """Return (private_hex, public_hex, key_id). Raw Ed25519, hex-encoded."""
    if not HAVE_ED25519:
        raise RuntimeError("cryptography package required for signing")
    priv = ed25519.Ed25519PrivateKey.generate()
    priv_hex = priv.private_bytes_raw().hex()
    pub_hex = priv.public_key().public_bytes_raw().hex()
    return priv_hex, pub_hex, key_id_for(pub_hex)


def key_id_for(public_hex: str) -> str:
    return hashlib.sha256(bytes.fromhex(public_hex)).hexdigest()[:16]


#: Ed25519's field prime and the order of its base point (RFC 8032).
_ED_P = 2 ** 255 - 19
_ED_L = 2 ** 252 + 27742317777372353535851937790883648493
#: The y-coordinates of the eight points of small order on Ed25519's curve
#: (orders 1, 2, 4 and 8; libsodium's list). Under a public key that is one
#: of them a "signature" needs no private key: with S zero and R a point of
#: small order it verifies whenever the statement's hash puts [k]A at -R,
#: which is every statement under the identity key and one in at most
#: eight under the others, so a forger varies the statement until one does
#: (R5B-1). No one holds such a key. Read with the sign bit masked, as an
#: encoding of either sign of x is one of them.
_SMALL_ORDER_Y = frozenset({
    0, 1, _ED_P - 1,
    int.from_bytes(bytes.fromhex("26e8958fc2b227b045c3f489f2ef98f0"
                                 "d5dfac05d3c63339b13802886d53fc05"), "little"),
    int.from_bytes(bytes.fromhex("c7176a703d4dd84fba3c0b760d10670f"
                                 "2a2053fa2c39ccc64ec7fd7792ac037a"), "little"),
})


def weak_point(encoded: bytes) -> bool:
    """Whether a 32-byte Ed25519 point encoding is a point of small order,
    or spells its y at or above the field prime, which no encoder writes
    and some decoders read as one of those points (§8)."""
    y = int.from_bytes(encoded, "little") & ((1 << 255) - 1)
    return y >= _ED_P or y in _SMALL_ORDER_Y


#: Ed25519's curve constant d = -121665/121666 (RFC 8032 §5.1).
_ED_D = -121665 * pow(121666, _ED_P - 2, _ED_P) % _ED_P


def off_curve(encoded: bytes) -> bool:
    """Whether a 32-byte encoding names no point of the curve: y at or
    above the field prime, no x with x^2 = (y^2 - 1) / (d y^2 + 1), or x
    zero with the sign bit set (RFC 8032 §5.1.3). No private key has such
    a public key, so a signature under it means nothing (R5D-15)."""
    y = int.from_bytes(encoded, "little") & ((1 << 255) - 1)
    if y >= _ED_P:
        return True
    u = (y * y - 1) % _ED_P
    v = (_ED_D * y * y + 1) % _ED_P          # never 0: -1/d is no square
    x2 = u * pow(v, _ED_P - 2, _ED_P) % _ED_P
    if x2 == 0:
        return bool(encoded[31] & 0x80)
    return pow(x2, (_ED_P - 1) // 2, _ED_P) != 1


def check_public_key(public_hex: str) -> str:
    """`public_hex` in lowercase, if it is an Ed25519 public key a
    signature can mean something under: 64 hex characters, with nothing
    around them but KEY_SPACE, encoding a point of the curve that is not of
    small order and is written canonically. ValueError otherwise ("could
    not verify", never INVALID): under a small-order key anyone can sign
    anything, no private key involved (R5B-1), and a key that is no point
    has no holder at all (R5D-15). Never quotes the value: a private key
    passed by mistake must not reach a log."""
    if not isinstance(public_hex, str) or \
            not HEX_KEY_RE.fullmatch(public_hex.strip(KEY_SPACE)):
        raise ValueError("the public key is not an Ed25519 public key (32 "
                         "bytes: 64 hex characters)")
    public_hex = public_hex.strip(KEY_SPACE).lower()
    if weak_point(bytes.fromhex(public_hex)):
        raise ValueError(
            "the public key is a point of small order, or one written in a "
            "form no key generator writes: no one holds a private key for "
            "it, and a signature under it can be made without one, so it "
            "shows nothing about who signed")
    if off_curve(bytes.fromhex(public_hex)):
        raise ValueError(
            "the public key is no point of Ed25519's curve: no private key "
            "has it, so no signature under it shows anything")
    return public_hex


#: What may surround a key, given or in a file: ASCII spaces, tabs, CRs
#: and LFs, as §6 says. Not Python's idea of white space, which takes
#: U+001C or U+0085 too, where another language's trim() does not
#: (R5D-11).
KEY_SPACE = " \t\r\n"

#: A key as `bellbriar-evidence keygen` writes either half: 64 hex
#: characters (32 bytes).
HEX_KEY_RE = re.compile(r"[0-9a-fA-F]{64}")
#: A key file holds 64 hex characters and a line end; anything much larger
#: is not one, and is not read into memory.
MAX_KEY_FILE = 4096
#: Spellings of an Ed25519 key (hex with or without 0x, the 128-hex secret
#: key form, base64 of either), to tell someone who typed a key where a
#: path or a name goes that it is now in their shell history.
_KEYLIKE = re.compile(r"(?:0[xX])?(?:[0-9a-fA-F]{64}){1,2}"
                      r"|[A-Za-z0-9+/_-]{43}=?|[A-Za-z0-9+/_-]{86}(?:==)?")


#: The first line `bellbriar-evidence keygen` writes in each file of a
#: pair, so the halves cannot be taken for each other: both are 64 hex
#: characters, and a .pub file given as the signing key signed with a key
#: anyone could derive from the published half (R5B-2). A file without a
#: first line of its own, as keygen wrote them before 1.0, is read as
#: before; one with another first line is not a key file.
PRIVATE_KEY_MARK = ("# bellbriar-evidence private key (Ed25519). Keep it "
                    "secret; never commit it.")
PUBLIC_KEY_MARK = "# bellbriar-evidence public key (Ed25519). Publish it."


def key_file_text(hex_key: str, private: bool) -> str:
    """What keygen writes in a key file: the half's mark, then the key."""
    return (PRIVATE_KEY_MARK if private else PUBLIC_KEY_MARK) + "\n" \
        + hex_key + "\n"


def parse_key_text(text: str) -> tuple[str | None, str | None]:
    """(kind, key) from a key file's text: kind "private" or "public" by
    the file's first line, None for a file without one (a pair written
    before 1.0), "other" for a first line that is neither mark; key the 64
    hex characters in lowercase, or None when the rest is not exactly
    one key."""
    lines = [line.strip(KEY_SPACE) for line in text.split("\n")
             if line.strip(KEY_SPACE)]
    kind = None
    if lines and lines[0].startswith("#"):
        mark = lines.pop(0)
        kind = {PRIVATE_KEY_MARK: "private",
                PUBLIC_KEY_MARK: "public"}.get(mark, "other")
    if len(lines) != 1 or not HEX_KEY_RE.fullmatch(lines[0]):
        return kind, None
    return kind, lines[0].lower()


class KeyFileError(ValueError):
    """A key file that cannot be used. The reason never quotes the value
    given for the file, nor anything read from it (R1A-1)."""


def looks_like_key(value: str) -> bool:
    """Whether `value` is spelled as a key is (_KEYLIKE), and not as a path
    starts ("/", ".", "~")."""
    value = value.strip()
    return value[:1] not in ("/", ".", "~") and bool(_KEYLIKE.fullmatch(value))


def read_private_key_file(value: str) -> tuple[str, int]:
    """(private_hex in lowercase, the file's mode) from the file `value`
    names: a regular file of at most MAX_KEY_FILE bytes holding 64 hex
    characters after PRIVATE_KEY_MARK, as keygen writes it, or alone, as
    keygen wrote it before 1.0. A .pub file, or one marked as a public
    key, is refused: both halves are 64 hex characters (R5B-2).

    `value` is never repeated in a reason: given where a path was expected,
    a key would reach a CI log with the message (R1A-1). Nothing read from
    the file is either: it may be most of a key. A FIFO, a device or a
    directory is refused without being read, also when it replaces the file
    between the checks (the descriptor is checked, not the name)."""
    import stat as _stat
    try:
        # RuntimeError: "~user" naming no user (R5B-13).
        path = Path(value).expanduser()
        st = path.stat()
    except (OSError, ValueError, RuntimeError):
        if looks_like_key(value):
            raise KeyFileError(
                "takes the path of a file holding the key, not the key "
                "itself: a key on the command line lands in shell history, "
                "process listings and CI logs. Put it in a file (mode 600). "
                "If what was given is a key in use, treat it as exposed"
                ) from None
        raise KeyFileError("no such file (what was given is not repeated "
                           "here, in case it was a key)") from None
    if not _stat.S_ISREG(st.st_mode):
        raise KeyFileError("not a regular file" + (
            " (a directory)" if _stat.S_ISDIR(st.st_mode) else ""))
    try:
        real = Path(os.path.realpath(path))
    except (OSError, ValueError):
        real = path
    if any(p.suffix.lower() == ".pub" for p in [*_link_names(path), real]):
        # The public half, which its owner publishes: signed with it, a
        # bundle would carry a key anyone can derive (R5B-2). A link named
        # .key that leads to one, through other links or not, is refused
        # too (R5D-13, R5F-5).
        raise KeyFileError(
            "names a .pub file, the PUBLIC half of a key pair, or a link to "
            "one: its owner publishes it, so a bundle signed with it could "
            "be signed by anyone. Give the private .key file")
    if st.st_size > MAX_KEY_FILE:
        raise KeyFileError(f"{st.st_size} bytes, too large to be a key file")
    flags = (os.O_RDONLY | getattr(os, "O_NONBLOCK", 0)
             | getattr(os, "O_NOCTTY", 0))
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise KeyFileError(f"cannot read it ({exc.strerror or 'error'})"
                           ) from None
    try:
        st = os.fstat(fd)
        if not _stat.S_ISREG(st.st_mode):
            raise KeyFileError("not a regular file")
        data = b""
        while len(data) <= MAX_KEY_FILE:
            chunk = os.read(fd, MAX_KEY_FILE + 1 - len(data))
            if not chunk:
                break
            data += chunk
    except OSError as exc:
        raise KeyFileError(f"cannot read it ({exc.strerror or 'error'})"
                           ) from None
    finally:
        os.close(fd)
    if len(data) > MAX_KEY_FILE:
        raise KeyFileError("too large to be a key file")
    try:
        kind, key = parse_key_text(data.decode("ascii"))
    except UnicodeDecodeError:
        kind, key = "other", None
    if kind == "public":
        raise KeyFileError(
            "holds a PUBLIC key (its first line says so), which its owner "
            "publishes: a bundle signed with it could be signed by anyone. "
            "Give the private .key file")
    if key is None or kind == "other":
        raise KeyFileError("does not hold an Ed25519 private key (as "
                           "bellbriar-evidence keygen writes it: its first "
                           "line, then 64 hex characters)")
    if kind is None and st.st_nlink > 1:
        # A file with no first line could be either half, and one with
        # another name too (a hard link) could be a .pub file under it
        # (R5F-5).
        raise KeyFileError(
            "holds a key alone, as keygen wrote both halves before 1.0, and "
            "has another name too (a hard link): it may be a public key "
            "file under that name, so it is not read as a private key. Copy "
            "it to a file of its own, or make a new pair with keygen")
    return key, st.st_mode


def _link_names(path: Path) -> list:
    """`path`, then each name a symbolic link at it leads to in turn, as
    the system follows them (at most 40)."""
    names = [path]
    for _ in range(40):
        try:
            if not path.is_symlink():
                break
            target = Path(os.readlink(path))
        except (OSError, ValueError):
            break
        path = target if target.is_absolute() else path.parent / target
        names.append(path)
    return names


def sign_bundle_local(bundle: dict, private_hex: str,
                      signer: str = "local") -> dict:
    """Sign in-process with a key the caller holds: the only signing this
    release does (D5).

    Produces a `self-signed` statement: the bound fields are copied straight
    from the bundle and nothing else was checked, because no one else took
    part. It shows who held the key and that the bundle has not changed
    since; whoever holds the key could have edited the results first.

    It signs whatever body it is given. bellbriar-eval runs check_body()
    and bundle_bound_values() first and signs nothing they refuse; a
    caller that skips them can sign a bundle verify_bundle() refuses as
    malformed (R5D-6).
    """
    if not HAVE_ED25519:
        raise RuntimeError("cryptography package required for signing")
    priv = ed25519.Ed25519PrivateKey.from_private_bytes(
        bytes.fromhex(private_hex))
    pub_hex = priv.public_key().public_bytes_raw().hex()
    kid = key_id_for(pub_hex)
    statement = build_statement(bundle_bound_values(bundle), kid, signer,
                                SELF_SIGNED, bundle_digest(bundle))
    bundle["signature"] = {
        "alg": "Ed25519",
        "context": STATEMENT_FORMAT,
        "key_id": kid,
        "statement": statement,
        "signature_b64": _sign_statement(statement, priv),
    }
    return bundle


# ---------------------------------------------------------------------------
# Verification (offline, third-party)
# ---------------------------------------------------------------------------

def _check_signature_block(sig) -> None:
    """A signature block is an object with exactly SIGNATURE_MEMBERS: `alg`
    "Ed25519", `context` "bellbriar-signature/1", `key_id` and
    `signature_b64` strings, and `statement` an object (§5, N10). Anything
    else is malformed: the block is outside the digest and only its
    statement is signed, so another member, or another `alg` or `context`
    than the ones a verifier uses (§4), would show a reader what no
    signature covers. Raises MalformedBundle."""
    if not isinstance(sig, dict):
        raise MalformedBundle("the signature block is not an object")
    if "statement" not in sig and "digest_sha256" in sig:
        raise MalformedBundle(
            "the signature block is the pre-0.3.0 bare-digest form "
            "(digest_sha256), which binds nothing to the domain or pack and "
            "cannot be verified; re-sign the bundle with a current harness")
    extra = sorted(set(sig) - set(SIGNATURE_MEMBERS))
    if extra:
        names = ", ".join(_short(json.dumps(m)) for m in extra[:5])
        raise MalformedBundle(
            f"the signature block has {len(extra)} member(s) this format "
            f"does not define ({names}): only its statement is signed, so "
            "anyone could have added them after signing")
    missing = [m for m in SIGNATURE_MEMBERS if m not in sig]
    if missing:
        raise MalformedBundle("the signature block lacks "
                              + ", ".join(missing))
    for member, want in (("alg", SIGNATURE_ALG), ("context", STATEMENT_FORMAT)):
        if sig[member] != want:
            raise MalformedBundle(
                f"signature.{member} is {_short(json.dumps(sig[member]))}, "
                f"not {json.dumps(want)}: a verifier uses {want} whatever the "
                "block says (§4), so a block that says otherwise misleads")
    if not isinstance(sig["statement"], dict):
        raise MalformedBundle("the signature statement is not an object")
    for member in ("key_id", "signature_b64"):
        if not isinstance(sig[member], str):
            raise MalformedBundle(f"signature.{member} is not a string")
    # The statement is closed too (§5, R1A-11): a member the format does
    # not define would be signed, and read by someone as a claim (a
    # "certified" member, say) that no verifier checks.
    extra = sorted(set(sig["statement"]) - set(STATEMENT_FIELDS))
    if extra:
        names = ", ".join(_short(json.dumps(m)) for m in extra[:5])
        raise MalformedBundle(
            f"the signature statement has {len(extra)} member(s) this format "
            f"does not define ({names})")


def rulebook_digest(rulebook: dict) -> str:
    """The SHA-256 of a rulebook in canonical form (§2): what reports and
    bundles record as `rulebook_sha256` (P1-08). The rules themselves,
    whatever the file's spacing, key order or line endings. Raises
    ValueError or TypeError for a value no canonical form holds."""
    return hashlib.sha256(canonical_bytes(rulebook)).hexdigest()


_BUNDLED_RULEBOOK_DIGEST: list = []


def bundled_rulebook_digest() -> str:
    """rulebook_digest of the rulebook this harness ships."""
    if not _BUNDLED_RULEBOOK_DIGEST:
        from importlib import resources
        with resources.files("bellbriar_harness").joinpath(
                "rulebook.json").open("r", encoding="utf-8") as fh:
            _BUNDLED_RULEBOOK_DIGEST.append(rulebook_digest(json.load(fh)))
    return _BUNDLED_RULEBOOK_DIGEST[0]


def _recorded_classes(bundle: dict) -> list[str]:
    """The classes other than public that the bundle's capture records give
    their host by the address the client connected to (`address_basis`
    "address"), in table order: what a name alone cannot tell a verifier."""
    found = set()
    for page in bundle.get("pages") or ():
        rec = page.get("fetch") if isinstance(page, dict) else None
        if isinstance(rec, dict) and rec.get("address_basis") == "address" \
                and rec.get("address_class") in ("loopback", "private"):
            found.add(rec["address_class"])
    return [c for c in ("loopback", "private") if c in found]


def _rulebook_said(bound: dict) -> str:
    """What verify says about the rulebook a bundle names (P1-08): which
    rules ran rests on its digest, and a digest that is not the rulebook
    this harness ships is a custom rulebook or another release's."""
    from . import __version__
    version, digest = bound.get("rulebook_version"), bound.get(
        "rulebook_sha256")
    # "records": the digest is what the signer wrote down, as the host is
    # (R1A-5). Whoever holds the key can write any digest.
    if not isinstance(digest, str):
        if not isinstance(version, str):
            # R5B-20.
            return ("the bundle records no rulebook version and no rulebook "
                    "digest, so it does not record which rules ran")
        return (f"the bundle records rulebook {_short(repr(version))} and no "
                "rulebook digest, so which rules ran rests on the version "
                "alone")
    head = (f"the bundle records rulebook {_short(repr(version))} "
            f"(sha256 {_short(digest)[:16]}…)")
    if digest == bundled_rulebook_digest():
        return (f"{head}, the digest of the one bellbriar-harness "
                f"{__version__} ships")
    return (f"{head}, NOT the digest of the one bellbriar-harness "
            f"{__version__} ships: a custom rulebook or another release's, "
            "whose tiers and rules may differ")


#: Every field of a signature statement (docs/CANONICALIZATION.md §5).
STATEMENT_FIELDS = ("statement_format", "bundle_digest_sha256",
                    "attestation_class", "key_id", "signer",
                    "signed_at") + BOUND_FIELDS

_NULL = type(None)
#: The members of a bundle (docs/CANONICALIZATION.md §5 "The body") and
#: the JSON types each may have. The body is closed at its top level, as
#: the signature block and the statement are: the signature covers every
#: member, so one this list does not hold ("certification": "WCAG 2.1 AA
#: conformant") would be signed and read as a claim no verifier checks
#: (R5B-4). The records inside it are not closed (R5D-3): verify checks in
#: them only what §6 lists. Those in BODY_REQUIRED must be present; the
#: other three (rulebook_sha256 and baseline, which bundles made before 1.0
#: lack, and signature) may be absent, which reads as null.
BODY_MEMBERS = {
    "bundle_format": (str,), "created_at": (str,), "tool": (dict,),
    "rulebook_version": (str,), "rulebook_sha256": (str, _NULL),
    "domain": (str, _NULL), "pack": (dict, _NULL), "inputs": (list,),
    "fetch": (dict, _NULL), "layers": (list,), "coverage_note": (str,),
    "site": (dict,), "pages": (list,), "judged": (dict, _NULL),
    "baseline": (dict, _NULL), "attestation": (str,),
    "signature": (dict, _NULL),
}
BODY_REQUIRED = ("bundle_format", "created_at", "tool", "rulebook_version",
                 "domain", "pack", "inputs", "fetch", "layers",
                 "coverage_note", "site", "pages", "judged", "attestation")
_JSON_TYPE = {str: "a string", dict: "an object", list: "an array",
              _NULL: "null"}


def check_body(bundle: dict) -> None:
    """The bundle is of this format, closed, and its members have their
    types (§5 "The body", R5B-4). Raises MalformedBundle: a format this
    verifier does not know cannot be read, and a member it does not define
    would be signed without meaning anything a verifier checks."""
    fmt = bundle.get("bundle_format")
    if "bundle_format" not in bundle:
        raise MalformedBundle(
            f"the bundle has no bundle_format (this verifier reads "
            f"{json.dumps(BUNDLE_FORMAT)}): not a bundle of a format it reads")
    if fmt != BUNDLE_FORMAT:
        raise MalformedBundle(
            f"bundle_format is {_short(json.dumps(fmt))}, not "
            f"{json.dumps(BUNDLE_FORMAT)}: not a format this verifier reads")
    extra = sorted(set(bundle) - set(BODY_MEMBERS))
    if extra:
        names = ", ".join(_short(json.dumps(m)) for m in extra[:5])
        raise MalformedBundle(
            f"the bundle has {len(extra)} member(s) this format does not "
            f"define ({names}): the signature would cover them, and a reader "
            "could take them for claims no verifier checks")
    missing = [m for m in BODY_REQUIRED if m not in bundle]
    if missing:
        raise MalformedBundle("the bundle lacks " + ", ".join(missing)
                              + ": every bundle records them")
    for member, types in BODY_MEMBERS.items():
        if member in bundle and not isinstance(bundle[member], types):
            want = " or ".join(_JSON_TYPE[t] for t in types)
            raise MalformedBundle(f"{member} is not {want}")
    domain = bundle.get("domain")
    if isinstance(domain, str) and not spelled_once(domain):
        raise MalformedBundle(
            f"domain {_short(json.dumps(domain))} is not a host in the one "
            "spelling the format gives (lowercase ASCII, an internationalized "
            "name in its xn-- form, no trailing dot; §5): a verifier would "
            "compare another spelling with the host as another name")


def spelled_once(domain: str) -> bool:
    """Is `domain` a host in the one spelling §5 gives, by its spelling
    alone (SA-4)? Lowercase ASCII letters, digits, "-", "_" and ".", with
    no empty label and no trailing dot, not ending in a label a browser
    reads as a number, unless it is an IPv4 address written as four
    decimal numbers without leading zeros; or an IPv6 address as the WHATWG
    URL standard writes it, without brackets. An xn-- label is not
    decoded (a harness checks that when it records the name)."""
    if not domain or not domain.isascii():
        return False
    if ":" in domain:
        try:
            return _ipv6_text(ipaddress.IPv6Address(domain)) == domain
        except ValueError:
            return False
    if not _LDH.fullmatch(domain):
        return False
    if _ADDRESS.fullmatch(domain):
        try:
            return str(ipaddress.IPv4Address(domain)) == domain
        except ValueError:
            return False
    return not _NUMERIC_LABEL.fullmatch(domain.rsplit(".", 1)[-1])


#: The members this release writes in each record inside a bundle's body,
#: by the record's place (§5): verify and inspect count a member beyond
#: these and say where, never what it says, since its name is the maker's
#: words too (L93, R5F-7). What the members hold is the run's record.
RECORD_MEMBERS = {
    "tool": frozenset(("name", "version", "python", "libraries",
                       "from_snapshot")),
    "tool.libraries": frozenset(("justhtml", "beautifulsoup4", "soupsieve",
                                 "expat", "playwright", "axe-core")),
    "tool.from_snapshot": frozenset(("axe-core", "chromium")),
    "inputs[]": frozenset(("path", "sha256", "bytes", "kind", "fetch_mode")),
    "fetch": frozenset(("final_url", "host", "pages", "list")),
    "fetch.list": frozenset(("kind", "url", "listed", "complete",
                             "max_pages")),
    "layers[]": frozenset(("layer", "status", "note")),
    "site": frozenset((
        "site_weighted_pass_rate", "pct_pages_tier1_clean",
        "pages_not_evaluable", "tier1_rules_executed", "tier1_rules_total",
        "tier1_rules_review_only", "total_fail_findings",
        "total_needs_review", "total_third_party_fail_findings",
        "total_third_party_needs_review", "rule_fail_totals")),
    "pages[]": frozenset(("path", "fetch", "score", "findings",
                          "not_applicable_rules")),
    "pages[].score": frozenset((
        "path", "weighted_pass_rate", "applicable_weight", "passed_weight",
        "tier1_clean", "tier1_rules_executed", "tier1_rules_applicable",
        "evaluable", "not_evaluable_reason", "fail_findings",
        "needs_review_findings", "third_party_fail_findings",
        "third_party_needs_review_findings", "failed_rules")),
    "pages[].fetch": frozenset((
        "requested_url", "final_url", "host", "mode", "http_status",
        "redirects", "redacted", "fetched_at", "browser", "viewport", "wait",
        "instrumented", "provenance_attr", "attribution", "shadow_roots",
        "axe", "narrow", "reader", "address_class", "address_basis",
        "snapshot_sha256", "fallback_reason", "notes")),
    # The records a rendered capture writes inside its own (SA-2).
    "pages[].fetch.browser": frozenset(("name", "version", "sandbox")),
    "pages[].fetch.viewport": frozenset(("width", "height")),
    "pages[].fetch.wait": frozenset((
        "strategy", "quiet_ms", "cap_ms", "waited_ms", "settled",
        "data_requests", "data_requests_open", "wait_for", "scroll_steps")),
    "pages[].fetch.attribution": frozenset((
        "policy", "vendor_list_version", "extra_third_party")),
    "pages[].fetch.axe": frozenset((
        "engine", "version", "sha256", "ran", "reason", "rules", "not_run",
        "elements", "not_located", "unchecked", "added")),
    "pages[].fetch.narrow": frozenset((
        "viewport", "settled", "hiding_recorded", "changed", "changed_all",
        "reflow_recorded", "scroll_width", "client_width", "clipped",
        "overflowing")),
    "pages[].fetch.narrow.viewport": frozenset(("width", "height")),
    "pages[].findings[]": frozenset((
        "rule_id", "verdict", "impact", "message", "line", "snippet",
        "selector", "origin", "origin_detail", "scored", "verdict_basis")),
    "baseline": frozenset(("sha256", "generated_at", "findings",
                           "new_findings", "new_fail_findings")),
}


def foreign_members(bundle: dict) -> tuple[int, list]:
    """(how many members the records inside `bundle` hold beyond
    RECORD_MEMBERS, the places that hold them, in order). The pack and
    judged records are the maker's whole (verify_bundle names them)."""
    places: list = []
    count = 0

    def check(obj, kind: str, place: str) -> None:
        nonlocal count
        if isinstance(obj, dict):
            extra = sum(1 for k in obj if k not in RECORD_MEMBERS[kind])
            if extra:
                count += extra
                places.append(place)

    def each(value):
        return enumerate(value) if isinstance(value, list) else ()

    tool = bundle.get("tool")
    check(tool, "tool", "tool")
    if isinstance(tool, dict):
        check(tool.get("libraries"), "tool.libraries", "tool.libraries")
        check(tool.get("from_snapshot"), "tool.from_snapshot",
              "tool.from_snapshot")
    for i, entry in each(bundle.get("inputs")):
        check(entry, "inputs[]", f"inputs[{i}]")
    fetch = bundle.get("fetch")
    check(fetch, "fetch", "fetch")
    if isinstance(fetch, dict):
        check(fetch.get("list"), "fetch.list", "fetch.list")
    for i, entry in each(bundle.get("layers")):
        check(entry, "layers[]", f"layers[{i}]")
    check(bundle.get("site"), "site", "site")
    for i, page in each(bundle.get("pages")):
        check(page, "pages[]", f"pages[{i}]")
        if isinstance(page, dict):
            check(page.get("score"), "pages[].score", f"pages[{i}].score")
            record = page.get("fetch")
            check(record, "pages[].fetch", f"pages[{i}].fetch")
            if isinstance(record, dict):
                for part in ("browser", "viewport", "wait", "attribution",
                             "axe", "narrow"):
                    check(record.get(part), f"pages[].fetch.{part}",
                          f"pages[{i}].fetch.{part}")
                narrow = record.get("narrow")
                if isinstance(narrow, dict):
                    check(narrow.get("viewport"),
                          "pages[].fetch.narrow.viewport",
                          f"pages[{i}].fetch.narrow.viewport")
            for j, finding in each(page.get("findings")):
                check(finding, "pages[].findings[]",
                      f"pages[{i}].findings[{j}]")
    check(bundle.get("baseline"), "baseline", "baseline")
    return count, places


def not_this_release(bundle: dict) -> list[str]:
    """What, of the records and texts inside `bundle`, this release does not
    write (L93): members beyond RECORD_MEMBERS, counted, with where; a
    coverage note, or a layer record, that is not one of this release's
    (coverage_text). Empty for a bundle this release made. None of it
    changes a verdict: it says whose words a reader is looking at."""
    from .coverage_text import coverage_note_known, layer_problems
    out = []
    count, places = foreign_members(bundle)
    if count:
        shown = places[:5] + ([f"{len(places) - 5} more places"]
                              if len(places) > 5 else [])
        out.append(f"{count} member{'s' if count != 1 else ''} it does not "
                   f"define (in {_and(shown)})")
    if not coverage_note_known(bundle.get("coverage_note")):
        out.append("its coverage note")
    out += layer_problems(bundle.get("layers"))
    return out


def _and(items: list) -> str:
    return (items[0] if len(items) == 1 else
            ", ".join(items[:-1]) + " and " + items[-1])


def _release_said(bundle: dict) -> str | None:
    """What verify and inspect say of what not_this_release finds."""
    from . import __version__
    found = not_this_release(bundle)
    if not found:
        return None
    return (f"it holds what bellbriar-harness {__version__} does not write "
            "(another release's, or added or edited), which is the word "
            f"of whoever made the bundle: {_and(found)}")


def _attestation_said(bundle: dict) -> str:
    """What verify says about the bundle's `attestation` text: whether it
    is the text this release writes, which a reader may take as the
    harness's words, or another (an older release's, or anyone's), which
    is its maker's (§5.1, R5B-4)."""
    from . import __version__
    if bundle.get("attestation") == ATTESTATION:
        return (f"its attestation text is the one bellbriar-harness "
                f"{__version__} writes")
    return (f"its attestation text is NOT the one bellbriar-harness "
            f"{__version__} writes (another release's, or edited): read it "
            "as the words of whoever made the bundle")


def _check_statement(sig) -> None:
    """MalformedBundle unless `sig` is a well-formed signature block whose
    statement's fields are strings or null (N10)."""
    _check_signature_block(sig)
    for field in STATEMENT_FIELDS:
        value = sig["statement"].get(field)
        if value is not None and not isinstance(value, str):
            raise MalformedBundle(f"statement field {field!r} is not a "
                                  "string or null")


def _signature_problem(sig: dict, public_hex: str) -> str | None:
    """Steps 1 to 3 of verify_bundle for a well-formed signature block
    (_check_statement): why its signature does not cover a bundle
    statement under `public_hex` (checked: check_public_key), or None when
    it does. Raises VerificationUnavailable without Ed25519."""
    statement = sig["statement"]
    # 1. The context comes from what is being verified — a bundle
    # statement — never from the statement itself. Taking it from
    # statement_format let a signature made under the pack context verify
    # as a bundle signature.
    fmt = statement.get("statement_format")
    if fmt != STATEMENT_FORMAT:
        what = ("the pack-manifest format" if fmt in SIGNING_CONTEXTS
                else "not a statement format this verifier knows")
        return (f"statement_format {_short(repr(fmt), 100)} is {what}; a "
                f"bundle is signed only under {STATEMENT_FORMAT!r}, so this "
                "signature does not cover a bundle")
    ctx = SIGNING_CONTEXTS[STATEMENT_FORMAT]
    signed_digest = bytes.fromhex(statement_digest(statement))

    # 2. The key.
    kid = key_id_for(public_hex)
    if sig.get("key_id") != kid or statement.get("key_id") != kid:
        return ("key_id does not match the supplied public key: the bundle "
                "says it was signed with another key")
    # 3. The signature.
    if not HAVE_ED25519:
        raise VerificationUnavailable(
            "the cryptography package is required to check Ed25519 "
            "signatures (pip install cryptography); nothing was concluded "
            "about this bundle")
    encoded = sig.get("signature_b64")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (TypeError, ValueError):
        raw = b""
    if len(raw) != 64 or base64.b64encode(raw).decode("ascii") != encoded:
        # One encoding per signature (§4), so verifiers cannot disagree
        # about a Base64 string one of them decodes leniently.
        return ("signature invalid: signature_b64 is not 64 bytes in "
                "canonical Base64")
    if weak_point(raw[:32]):
        # Only a signature that needs no private key has such an R
        # (R5B-1); no signer writes one (§4).
        return ("signature invalid: its R is a point of small order, or "
                "written in a form no signer writes")
    if int.from_bytes(raw[32:], "little") >= _ED_L:
        return ("signature invalid: its S is not reduced modulo the group "
                "order, as RFC 8032 requires")
    try:
        pub = ed25519.Ed25519PublicKey.from_public_bytes(
            bytes.fromhex(public_hex))
        pub.verify(raw, ctx + signed_digest)
    except Exception as exc:  # noqa: BLE001 — invalid signature/key
        # OpenSSL checks [S]B = R + [k]A, the equation §6 step 3 names
        # (SA-1), and no other: a cofactored check accepts more.
        return (f"signature invalid ({type(exc).__name__}): the statement "
                "was changed after signing, or was not signed with this "
                "key's private key as RFC 8032 signs ([S]B = R + [k]A "
                "fails)")
    return None


def statement_signed_by(sig, public_hex: str) -> bool:
    """Does the signature block `sig` hold a bundle statement signed with
    the private key of `public_hex` (verify_bundle's steps 1 to 3)? What
    the bundle around it says is not read: its digest, its bindings, its
    body. False for anything malformed, or without Ed25519."""
    try:
        _check_statement(sig)
        return _signature_problem(sig, check_public_key(public_hex)) is None
    except Exception:  # noqa: BLE001 — malformed, or no cryptography
        return False


def verify_bundle(bundle: dict, public_hex: str) -> tuple[bool, str]:
    """Verify integrity, field binding, and signature. Returns (ok, reason).

    Raises MalformedBundle when the input is not a well-formed bundle and
    VerificationUnavailable when the signature cannot be checked on this
    machine; both mean "could not verify", never "invalid". A public key
    that is not one a signature can mean anything under (not hex, or a
    point of small order: check_public_key) raises ValueError. To verify a
    file, parse it with load_bundle(), which refuses text that can be read
    two ways.

    Steps, in order, per docs/CANONICALIZATION.md §6:
      1. a signature with a statement is present, and the statement's
         format is exactly STATEMENT_FORMAT (wrong types are malformed)
      2. the key_id matches the public key supplied
      3. the Ed25519 signature over the statement context ‖ statement
         digest is valid
      4. the statement's digest matches this bundle's recomputed digest
      5. every bound field in the statement equals the bundle's own value
      6. the fetched host is the stated domain, its www. form or a
         subdomain of it (a subdomain is named in the VALID reason)
    The signature is checked before what the statement says is compared
    with the bundle, so a reason never calls a signature genuine, or
    attributes a statement to the key's holder, before that is known
    (R5B-3).
    """
    # A key that is not one is "could not verify", never INVALID: an empty
    # one, from an unset shell variable, used to read as a forged bundle
    # (R1A-4). Checked before anything else, and never quoted.
    public_hex = check_public_key(public_hex)
    # Every malformed condition is checked before any verdict, so a file
    # broken in two ways gets the same answer from every conformant
    # verifier. Wrong types or values outside §2 are a broken document, not
    # a failed signature; a well-formed bundle its signature does not cover
    # is INVALID.
    if not isinstance(bundle, dict):
        raise MalformedBundle("a bundle is a JSON object")
    try:
        _canonical_value(bundle)            # the whole file, signature too
        recomputed = bundle_digest(bundle)
    except (ValueError, TypeError, RecursionError) as exc:
        raise MalformedBundle(f"not in canonical form: {exc}") from None
    check_body(bundle)                      # closed, its own format (R5B-4)
    bound = bundle_bound_values(bundle)     # MalformedBundle: pack, fetch

    sig = bundle.get("signature")
    if sig is None:
        return False, "bundle is unsigned"
    _check_statement(sig)                   # MalformedBundle (N10)
    statement = sig["statement"]
    problem = _signature_problem(sig, public_hex)       # steps 1 to 3
    if problem:
        return False, problem

    # From here the statement is known to be the key holder's.
    # 4. The digest.
    if statement.get("bundle_digest_sha256") != recomputed:
        return False, ("digest mismatch: the bundle was altered after it was "
                       "signed (the key's holder signed a statement about "
                       "other contents), or the signature was taken from "
                       "another bundle")

    # 5. The binding.
    for field in BOUND_FIELDS:
        signed, own = statement.get(field), bound.get(field)
        if type(signed) is not type(own) or signed != own:   # strict: 1 ≠ true
            if field == "host" and field not in statement:
                return False, (
                    f"this statement predates host binding: it does not "
                    f"record where the page was fetched, and this bundle is "
                    f"a URL run fetched from {_short(repr(own), 100)}, so the "
                    f"signature does not cover it. Re-sign the bundle with a "
                    f"current harness.")
            # Quoted short: either side can be any length (R1A-12). A
            # statement without the field names nothing there; it reads as
            # null (pack_sha256 is bound since Part S, SA-7).
            named = (f"naming {_short(repr(signed), 100)}"
                     if field in statement
                     else "without it, which reads as None")
            return False, (
                f"binding mismatch on {field!r}: the key's holder signed a "
                f"statement {named}, but this bundle states "
                f"{_short(repr(own), 100)}, so the signature does not cover "
                f"this bundle's claims")

    # 6. A statement whose measured host is not the stated domain, its www.
    # form or a subdomain of it says two things that cannot both be true.
    domain, host = statement.get("domain"), statement.get("host")
    scope = host_scope(host, domain)
    if scope == "unrelated":
        return False, (f"the statement names domain {domain!r} but records "
                       f"the page as fetched from {host!r}, which is neither "
                       "that domain nor a subdomain of it")

    # The verifier says what the signature shows in its own words: the
    # bundle's attestation text, and its class, are written by whoever
    # made it (N11, P5-01).
    cls = statement.get("attestation_class")
    if cls == SELF_SIGNED:
        what = f"self-signed: {SELF_SIGNED_MEANING}"
    elif cls in RESERVED_CLASSES:
        # The class names what would have checked the bundle: a signing
        # service for a submission, a hosted runner for an execution
        # (R1A-8). Neither exists in this release.
        issuer = ("no signing service exists" if cls == ATTESTED_SUBMISSION
                  else "no hosted runner exists")
        what = (f"the statement claims class {cls!r}, which nothing issues "
                f"in this release: {issuer}, so no one but the key's holder "
                "checked anything. It shows no more than a self-signed "
                f"signature: {SELF_SIGNED_MEANING}")
    else:
        claim = (f"claims class {_short(repr(cls))}, which this format does "
                 "not define" if cls else "states no class")
        what = (f"the statement {claim}. It shows no more than a "
                f"self-signed signature: {SELF_SIGNED_MEANING}")
    # Names are quoted: they are signed claims, and a quoted name cannot run
    # on into the verdict text around it. The fetch is the client's record
    # (see ATTESTATION), so the verdict says what the bundle records, never
    # that a fetch happened.
    # A loopback or private host is named as such: a run against a
    # developer machine or an internal network is not a public site.
    note = host_note(host)
    shown = f"{host!r}" + (f" ({note}, not a public site)" if note else "")
    recorded = _recorded_classes(bundle) if host and not note else []
    if recorded:
        # A name says nothing about where it pointed; the capture records
        # can, by the address the client connected to (L20). Reported as
        # what they are, the client's record (R1B-2).
        shown += (", which its capture records say resolved to a "
                  + " or ".join(recorded) + " address (not a public site)")
    if not host and domain:
        # A file run fetched nothing: its domain is the operator's word
        # (R5B-7).
        measured = (f"no fetched host is recorded: the domain {domain!r} is "
                    "the operator's statement, and nothing was fetched "
                    "from it")
    elif not host:
        measured = "no fetched host is recorded"
    elif not domain:
        measured = (f"the bundle records the page as fetched from {shown}; "
                    "no domain is stated")
    elif scope == "subdomain":
        measured = (f"the bundle records the page as fetched from {shown}, "
                    f"a subdomain of {_site(domain)!r} and not {domain!r} "
                    "itself")
    else:
        measured = f"the bundle records the page as fetched from {shown}"
    reason = (f"signature valid ({what}); every bound field matches; "
              f"{measured}; {_rulebook_said(bound)}; {_attestation_said(bundle)}")
    # This release pins no pack and runs no judge (D3): a bundle carrying
    # either carries its maker's word for it, signed or not (R1A-8).
    # Any pack record counts, named or not: one without a name is still the
    # maker's claim of a pack (R5D-15).
    claims = [w for w, present in (
        (f"pack {_short(repr(bound.get('pack')), 60)}"
         if bound.get("pack") is not None else "a pack record with no name",
         bundle.get("pack") is not None),
        ("judged results", bundle.get("judged") is not None)) if present]
    if claims:
        reason += (f"; it carries {' and '.join(claims)}, which this release "
                   "never writes: the claim of whoever made the bundle")
    # Members and texts this release does not write: their maker's too
    # (L93). Said, never refused: the signature covers them, and a
    # newer release's bundle still verifies here.
    foreign = _release_said(bundle)
    if foreign:
        reason += "; " + foreign
    kid = key_id_for(public_hex)
    if kid in PUBLISHED_TEST_KEY_IDS:
        reason += (". PUBLISHED TEST KEY: its private key is printed in the "
                   "format specification, so anyone can sign with it; this "
                   "signature is evidence of nothing")
    elif kid in DEMO_KEY_IDS:
        reason += (". DEMONSTRATION KEY: it signs only the harness's worked "
                   "example and is in no trust path; this signature is not "
                   "evidence from any production signer")
    return True, reason
