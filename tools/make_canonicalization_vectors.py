#!/usr/bin/env python3
"""Regenerate docs/canonicalization-vectors.json.

The vectors are the executable half of docs/CANONICALIZATION.md: the spec
prose says what the bytes must be, this file says what they are, and
tests/test_canonicalization.py checks that (a) the library reproduces every
value here and (b) every value here appears verbatim in the spec, so the
document cannot drift from the implementation without a test failing.

The vector key is derived from a fixed, published seed and is therefore
PUBLIC BY CONSTRUCTION. It exists only so the signatures below are
reproducible by anyone; it signs nothing that is relied upon.

    python tools/make_canonicalization_vectors.py
"""
from __future__ import annotations

import base64
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bellbriar_harness import bundle as B                       # noqa: E402
from bellbriar_harness import pack as P                         # noqa: E402

OUT = ROOT / "docs" / "canonicalization-vectors.json"
VECTOR_KEY_SEED = "bellbriar-canonicalization-vector-key/1"


def vector_key() -> tuple[str, str, str]:
    priv_hex = hashlib.sha256(VECTOR_KEY_SEED.encode("utf-8")).hexdigest()
    priv = B.ed25519.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(priv_hex))
    pub_hex = priv.public_key().public_bytes_raw().hex()
    return priv_hex, pub_hex, B.key_id_for(pub_hex)


# ---------------------------------------------------------------------------
# §6 step 3 names the equation a verifier checks: [S]B = R + [k]A, which
# RFC 8032 §5.1.7 allows in place of the [8][S]B = [8]R + [8][k]A it states.
# The two disagree when R or the key has a part of small order (SA-1). No
# library signs so, so the vectors below are made with the curve arithmetic
# of RFC 8032 §6 itself: points in extended coordinates (X, Y, Z, T), with
# x = X/Z, y = Y/Z and xy = T/Z.
# ---------------------------------------------------------------------------
_P = 2 ** 255 - 19
_L = 2 ** 252 + 27742317777372353535851937790883648493
_D = -121665 * pow(121666, _P - 2, _P) % _P
_SQRT_M1 = pow(2, (_P - 1) // 4, _P)
_IDENTITY = (0, 1, 1, 0)


def _recover_x(y: int, sign: int) -> int | None:
    if y >= _P:
        return None
    x2 = (y * y - 1) * pow(_D * y * y + 1, _P - 2, _P) % _P
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (_P + 3) // 8, _P)
    if (x * x - x2) % _P:
        x = x * _SQRT_M1 % _P
    if (x * x - x2) % _P:
        return None
    return _P - x if (x & 1) != sign else x


def _add(p: tuple, q: tuple) -> tuple:
    a = (p[1] - p[0]) * (q[1] - q[0]) % _P
    b = (p[1] + p[0]) * (q[1] + q[0]) % _P
    c = 2 * p[3] * q[3] * _D % _P
    d = 2 * p[2] * q[2] % _P
    e, f, g, h = b - a, d - c, d + c, b + a
    return (e * f % _P, g * h % _P, f * g % _P, e * h % _P)


def _mul(n: int, p: tuple) -> tuple:
    q = _IDENTITY
    while n > 0:
        if n & 1:
            q = _add(q, p)
        p, n = _add(p, p), n >> 1
    return q


def _same(p: tuple, q: tuple) -> bool:
    return ((p[0] * q[2] - q[0] * p[2]) % _P == 0
            and (p[1] * q[2] - q[1] * p[2]) % _P == 0)


def _encode(p: tuple) -> bytes:
    zi = pow(p[2], _P - 2, _P)
    x, y = p[0] * zi % _P, p[1] * zi % _P
    return (y | (x & 1) << 255).to_bytes(32, "little")


def _decode(raw: bytes) -> tuple | None:
    y = int.from_bytes(raw, "little")
    x = _recover_x(y & ((1 << 255) - 1), y >> 255)
    y &= (1 << 255) - 1
    return None if x is None else (x, y, 1, x * y % _P)


_BASE = _decode((4 * pow(5, _P - 2, _P) % _P).to_bytes(32, "little"))
#: A point of order 8: the first y §8 lists, with its sign bit clear.
_ORDER_8 = _decode(bytes.fromhex(
    "26e8958fc2b227b045c3f489f2ef98f0d5dfac05d3c63339b13802886d53fc05"))
assert _same(_mul(8, _ORDER_8), _IDENTITY)
assert not _same(_mul(4, _ORDER_8), _IDENTITY)


def _k(r_enc: bytes, a_enc: bytes, message: bytes, reduce: bool = True) -> int:
    k = int.from_bytes(hashlib.sha512(r_enc + a_enc + message).digest(),
                       "little")
    return k % _L if reduce else k


def _sign(priv_hex: str, message: bytes, *, part_in_key: bool = False,
          part_in_r: int = 0, counter: int = 0) -> tuple[bytes, bytes]:
    """(signature, public key) as RFC 8032 §5.1.6 signs, except that with
    `part_in_key` the key has the point of order 8 added, R has
    [`part_in_r`] of that point added, and r is derived with `counter`
    appended to what the RFC hashes (when it is not 0)."""
    h = hashlib.sha512(bytes.fromhex(priv_hex)).digest()
    a = int.from_bytes(h[:32], "little") & ((1 << 254) - 8) | (1 << 254)
    key = _mul(a, _BASE)
    if part_in_key:
        key = _add(key, _ORDER_8)
    a_enc = _encode(key)
    extra = counter.to_bytes(2, "little") if counter else b""
    r = int.from_bytes(hashlib.sha512(h[32:] + message + extra).digest(),
                       "little") % _L
    r_enc = _encode(_add(_mul(r, _BASE), _mul(part_in_r, _ORDER_8)))
    s = (r + _k(r_enc, a_enc, message) * a) % _L
    return r_enc + s.to_bytes(32, "little"), a_enc


def equations(public: bytes, message: bytes, signature: bytes) -> dict:
    """Which equations hold: [S]B = R + [k]A, the one §6 step 3 names; the
    same with k not reduced modulo L; and [8][S]B = [8]R + [8][k]A."""
    key, point = _decode(public), _decode(signature[:32])
    s = int.from_bytes(signature[32:], "little")
    if key is None or point is None or s >= _L:
        return {"cofactorless": False, "cofactorless_k_not_reduced": False,
                "cofactored": False}
    left = _mul(s, _BASE)

    def right(reduce):
        return _add(point, _mul(_k(signature[:32], public, message, reduce),
                                key))
    return {"cofactorless": _same(left, right(True)),
            "cofactorless_k_not_reduced": _same(left, right(False)),
            "cofactored": _same(_mul(8, left), _mul(8, right(True)))}


def _first(priv_hex: str, message: bytes, want: dict, *, part_in_key: bool,
           parts_in_r: range) -> bytes:
    """The first signature, by counter and then by R's part, for which the
    equations that hold are `want`."""
    for counter in range(256):
        for part in parts_in_r:
            raw, public = _sign(priv_hex, message, part_in_key=part_in_key,
                                part_in_r=part, counter=counter)
            if equations(public, message, raw) == want:
                return raw
    raise AssertionError(f"no signature for {want}")


def canonical_cases() -> list[dict]:
    cases = [
        ("integer-valued float serializes as an integer", {"rate": 1.0}),
        ("negative zero serializes as 0", {"rate": -0.0}),
        ("non-integer float: shortest round-trip decimal", {"rate": 0.9375}),
        ("four-decimal rate stays in plain decimal, no exponent", {"rate": 0.0001}),
        ("four decimal places at a larger magnitude", {"rate": 12345.6789}),
        ("a long decimal from 0.0001 up prints the same in both languages",
         {"x": 0.30000000000000004}),
        ("integers unchanged", {"bytes": 1263, "n": -7}),
        ("the largest integer every verifier holds exactly: 2^53",
         {"n": 9007199254740992}),
        ("an integer-valued float up to 2^53 is an integer",
         {"n": 9007199254740992.0}),
        ("keys sorted by code point, recursively", {"b": {"y": 2, "x": 1}, "a": [3, {"d": 4, "c": 5}]}),
        ("booleans and null", {"ok": True, "no": False, "none": None}),
        ("non-ASCII string values are raw UTF-8, not \\u escapes", {"s": "천연 발효빵 — ünïcödé"}),
        ("only the mandatory string escapes", {"s": "a\"b\\c\nd\te\u0001f/g"}),
        ("empty containers", {"o": {}, "l": []}),
    ]
    return [{"description": d, "input": v,
             "canonical_utf8": B.canonical_bytes(v).decode("utf-8"),
             "canonical_hex": B.canonical_bytes(v).hex(),
             "sha256": hashlib.sha256(B.canonical_bytes(v)).hexdigest()}
            for d, v in cases]


def rejected_cases() -> list[dict]:
    """Inputs the producer must refuse. `input_json` is the same input as
    JSON text, where JSON can express it, so a verifier in any language can
    check that it treats the value as malformed too."""
    cases = [
        ("NaN is not JSON", "{'x': float('nan')}", None),
        ("Infinity is not JSON", "{'x': float('inf')}", None),
        ("non-ASCII object key", "{'ключ': 1}", '{"ключ":1}'),
        ("non-string object key", "{1: 'a'}", None),
        ("integer beyond 2^53", "{'x': 2**53 + 1}", '{"x":9007199254740993}'),
        ("integer-valued number beyond 2^53: Python prints "
         "1152921504606846976, JavaScript 1152921504606847000",
         "{'x': 2.0**60}", '{"x":1.152921504606847e+18}'),
        ("decimal smaller than 0.0001: Python prints 5e-05, "
         "JavaScript 0.00005", "{'x': 0.00005}", '{"x":5e-05}'),
        ("lone surrogate in a string", "{'s': '\\ud800'}", '{"s":"\\ud800"}'),
    ]
    return [{"description": d, "input_python": p, "input_json": j}
            for d, p, j in cases]


def malformed_texts() -> list[dict]:
    """Bundle file texts a verifier must report as malformed (§6): each
    either parses to a value §2 refuses, or can be read as a different
    value from the one a verifier checks."""
    cases = [
        ("duplicate member names", '{"domain":"a.com","domain":"b.com"}'),
        ("duplicate member names inside the signature block",
         '{"signature":{"alg":"Ed25519","alg":"Ed25519"}}'),
        ("duplicate member names, one spelled with an escape",
         '{"signature":{"statement":{},"\\u0073tatement":{}}}'),
        ("number too large for a double", '{"x":1e999}'),
        ("integer literal beyond 2^53", '{"x":9007199254740993}'),
        ("integer beyond 2^53 spelled as a decimal", '{"x":9007199254740993.0}'),
        ("more digits than a double holds", '{"x":0.67570000000000001}'),
        ("underflows to zero", '{"x":1e-400}'),
        ("underflows to zero, with an exponent beyond any decimal context",
         '{"x":1e-99999999999999999999}'),
        ("NaN is not JSON", '{"x":NaN}'),
        ("decimal smaller than 0.0001", '{"x":5e-05}'),
        ("lone surrogate", '{"s":"\\ud800"}'),
        ("non-ASCII object key", '{"ключ":1}'),
        ("not an object", '[1,2]'),
        (f"nested deeper than {B.MAX_DEPTH} levels",
         '{"a":' + "[" * B.MAX_DEPTH + "]" * B.MAX_DEPTH + "}"),
    ]
    return [{"description": d, "text": t} for d, t in cases]


def malformed_bytes() -> list[dict]:
    """File bytes a verifier must refuse before parsing (§6)."""
    cases = [("starts with a byte-order mark", b"\xef\xbb\xbf{}"),
             ("not valid UTF-8", b'{"s":"\xff"}')]
    return [{"description": d, "hex": b.hex()} for d, b in cases]


def well_formed_spellings() -> list[dict]:
    """Different spellings of canonical values that a verifier must accept:
    the file need not be canonical, only unambiguous."""
    cases = ['{"x":1.0}', '{"x":1e2}', '{"x":-0.0}', '{"x":0.67570}',
             '{"x":6.757e-1}', '{"x":0e99999999999999999999}',
             '{"s":"\\u0041"}',
             '{"a":' + "[" * (B.MAX_DEPTH - 1) + "]" * (B.MAX_DEPTH - 1) + "}"]
    return [{"text": t,
             "canonical_utf8": B.canonical_bytes(B.load_bundle(t)).decode()}
            for t in cases]


def host_relations() -> list[dict]:
    """§6 step 6 on normalized names: how the fetched host relates to the
    stated domain. "unrelated" is INVALID; "subdomain" is VALID and named."""
    cases = [
        ("example.com", "example.com", "same"),
        ("www.example.com", "example.com", "same"),
        ("example.com", "www.example.com", "same"),
        ("staging.example.com", "example.com", "subdomain"),
        ("staging.example.com", "www.example.com", "subdomain"),
        ("a.b.example.com", "example.com", "subdomain"),
        ("www.staging.example.com", "staging.example.com", "same"),
        ("example.com", "staging.example.com", "unrelated"),
        ("badexample.com", "example.com", "unrelated"),
        ("example.com.evil.test", "example.com", "unrelated"),
        ("evil.com", "www.com", "unrelated"),
        ("192.0.2.1", "192.0.2.1", "same"),
        ("192.0.2.10", "192.0.2.1", "unrelated"),
        ("::1", "::1", "same"),
        ("::1", "localhost", "unrelated"),
        (None, "example.com", "unstated"),
        ("example.com", None, "unstated"),
    ]
    for host, domain, relation in cases:
        assert B.host_scope(host, domain) == relation, (host, domain)
    return [{"host": h, "domain": d, "relation": r} for h, d, r in cases]


def url_hosts() -> list[dict]:
    """§5: the host read from fetch.final_url. `host` null means none can be
    read, and a bundle whose fetch block holds that final_url is malformed
    (§6)."""
    cases = [
        ("https://www.example.com/", "www.example.com"),
        ("HTTPS://Example.COM:8443/a?b#c", "example.com"),
        ("https://user:pw@staging.example.com/", None),
        ("https://a@b@example.com/", None),
        ("https://example.com?x=@evil.test", "example.com"),
        ("https://example.com#@evil.test", "example.com"),
        ("https://example.com./", "example.com"),
        ("http://127.0.0.1", "127.0.0.1"),
        ("http://[::1]:8080/x", "::1"),
        ("https://[::ffff:7f00:1]/", "::ffff:7f00:1"),
        ("https://xn--bcher-kva.de/", "xn--bcher-kva.de"),
        ("https://evil.test\\@example.com/", None),
        ("https://ex%61mple.com/", None),
        ("https://bücher.de/", None),
        ("https://example.com/a b", None),
        ("https://example.com:80a/", None),
        ("https://example.com:/", "example.com"),
        ("https://[::1/", None),
        ("https:///path", None),
        ("ftp://example.com/", None),
        ("example.com", None),
    ]
    for url, host in cases:
        assert B.url_host(url) == host, (url, B.url_host(url))
    return [{"final_url": u, "host": h} for u, h in cases]


def domain_spellings() -> list[dict]:
    """§5 (§9.8): a `domain` in another spelling than the one §5 gives
    makes the bundle malformed (SA-4). "fine" is the §9.2 bundle with that
    domain passing check_body; the verifier checks the spelling only."""
    cases = [
        ("example.com", "fine"),
        ("www.cornerbakery.example", "fine"),
        ("xn--bcher-kva.de", "fine"),
        ("under_score.example", "fine"),
        ("localhost", "fine"),
        ("192.0.2.1", "fine"),
        ("::1", "fine"),
        ("::ffff:7f00:1", "fine"),
        ("", "malformed"),
        ("WWW.CornerBakery.example", "malformed"),
        ("example.com.", "malformed"),
        ("a..example", "malformed"),
        ("cornerb\u0430kery.example", "malformed"),
        ("b\u00fccher.de", "malformed"),
        ("https://example.com/", "malformed"),
        ("example.com:443", "malformed"),
        ("1.2.3", "malformed"),
        ("01.2.3.4", "malformed"),
        ("example.0x1f", "malformed"),
        ("[::1]", "malformed"),
        ("0:0:0:0:0:0:0:1", "malformed"),
        ("::ffff:127.0.0.1", "malformed"),
    ]
    out = []
    base = unsigned_bundle()
    for domain, result in cases:
        try:
            B.check_body(dict(base, domain=domain))
            got = "fine"
        except B.MalformedBundle:
            got = "malformed"
        assert got == result, (domain, got)
        out.append({"domain": domain, "result": result})
    return out


#: The members §9.6 gives each of its bundles; the rest are the §9.2
#: bundle's, unsigned, with `inputs` empty and `judged` null unless a case
#: gives them.
RECORD_MEMBERS = ("fetch", "pages", "inputs", "judged")


def whole_bundle(records: dict) -> dict:
    """A §9.6 bundle: the §9.2 bundle, unsigned, with `records` in place of
    its fetch, pages, inputs and judged (R5D-4: the cases are whole
    bundles, which a verifier checks as it checks any)."""
    base = {k: v for k, v in unsigned_bundle().items()
            if k not in RECORD_MEMBERS}
    return {**base, "inputs": [], "judged": None, **records}


def page_bundle(fetch, page) -> dict:
    """The bundle a page_records host case stands for: a URL run of one page
    (`fetch` its first page's final URL, the page named by its own) or a
    run that fetched nothing (`fetch` null, a page named index.html)."""
    if fetch is None:
        return whole_bundle({"fetch": None, "pages": [
            {"path": "index.html", "fetch": page}]})
    name = page.get("final_url") if isinstance(page, dict) else fetch
    return whole_bundle({"fetch": {"final_url": fetch, "pages": 1},
                         "pages": [{"path": name, "fetch": page}]})


def page_records() -> list[dict]:
    """§5 "Pages" (§9.6). Host cases: each page's capture record names the
    host fetch.final_url gives (a URL run), or this machine (a run that
    fetched nothing, `fetch` null); `fetch` is that final_url or null and
    `page` the page's record, in the bundle page_bundle builds. Shape
    cases: a whole `bundle`, with a `description`."""
    cases = [
        ("https://www.example.com/",
         {"final_url": "https://www.example.com/about"}, "fine"),
        ("https://www.example.com/",
         {"final_url": "HTTPS://WWW.Example.com:443/x"}, "fine"),
        ("https://www.example.com/",
         {"final_url": "https://www.example.com/x", "host": "www.example.com"},
         "fine"),
        ("https://www.example.com/", None, "malformed"),
        ("https://www.example.com/",
         {"final_url": "https://example.com/"}, "malformed"),
        ("https://www.example.com/",
         {"final_url": "https://www.example.com/x", "host": "example.com"},
         "malformed"),
        ("https://www.example.com/", {"final_url": "www.example.com/x"},
         "malformed"),
        (None, {"final_url": "http://127.0.0.1:8123/index.html"}, "fine"),
        (None, {"final_url": "http://[::1]:8080/"}, "fine"),
        (None, {"final_url": "http://localhost:3000/"}, "fine"),
        (None, {"final_url": "http://app.localhost/"}, "fine"),
        (None, None, "fine"),
        (None, {"final_url": "https://www.example.com/"}, "malformed"),
        (None, {"final_url": "http://127.000.0.1/"}, "malformed"),
        (None, {"final_url": "http://10.0.0.5/"}, "malformed"),
        (None, {"final_url": "http://localhost.example.com/"}, "malformed"),
    ]
    a, b = "https://www.example.com/a", "https://www.example.com/b"
    run = {"final_url": a, "pages": 2}
    snap = {"sha256": "0" * 64, "bytes": 1, "kind": "url-snapshot"}
    loop = "http://127.0.0.1:8123/"
    shapes = [
        ("a URL run of two pages", "fine",
         {"fetch": run, "pages": [{"path": a, "fetch": {"final_url": a}},
                                  {"path": b, "fetch": {"final_url": b}}],
          "inputs": [dict(snap, path=a), dict(snap, path=b)]}),
        ("fetch.pages counts more pages than the bundle has", "malformed",
         {"fetch": dict(run, pages=3),
          "pages": [{"path": a, "fetch": {"final_url": a}},
                    {"path": b, "fetch": {"final_url": b}}]}),
        ("a URL run's fetch without pages", "malformed",
         {"fetch": {"final_url": a},
          "pages": [{"path": a, "fetch": {"final_url": a}}]}),
        ("a page of a URL run with no capture record", "malformed",
         {"fetch": run, "pages": [{"path": a, "fetch": {"final_url": a}},
                                  {"path": "https://bank.example/", "fetch":
                                   None}]}),
        ("a page named by another URL than it was fetched from", "malformed",
         {"fetch": run, "pages": [{"path": a, "fetch": {"final_url": a}},
                                  {"path": "https://bank.example/", "fetch":
                                   {"final_url": b}}]}),
        ("a snapshot input from another host", "malformed",
         {"fetch": dict(run, pages=1),
          "pages": [{"path": a, "fetch": {"final_url": a}}],
          "inputs": [dict(snap, path="https://bank.example/")]}),
        ("a snapshot input in a run that fetched nothing", "malformed",
         {"fetch": None, "pages": [{"path": "index.html", "fetch": None}],
          "inputs": [dict(snap, path=a)]}),
        ("a build rendered on this machine: every page has a record", "fine",
         {"fetch": None,
          "pages": [{"path": "dist/a.html", "fetch": {"final_url": loop + "a"}},
                    {"path": "dist/b.html", "fetch": {"final_url": loop + "b"}}],
          "inputs": [{"path": "dist/app.js", "sha256": "0" * 64, "bytes": 1,
                      "kind": "served"}]}),
        ("a run that fetched nothing, with one page record of two",
         "malformed",
         {"fetch": None,
          "pages": [{"path": "dist/a.html", "fetch": {"final_url": loop + "a"}},
                    {"path": "dist/b.html", "fetch": None}]}),
        ("inputs that are not an array of objects", "malformed",
         {"fetch": None, "pages": [], "inputs": ["dist/a.html"]}),
        ("a URL run's input that is not a page's snapshot", "malformed",
         {"fetch": dict(run, pages=1),
          "pages": [{"path": a, "fetch": {"final_url": a}}],
          "inputs": [{"path": "https://bank.example/", "sha256": "0" * 64,
                      "bytes": 1}]}),
        ("a run that fetched nothing, with an input naming a site",
         "malformed",
         {"fetch": None, "pages": [{"path": "dist/a.html", "fetch": None}],
          "inputs": [{"path": "https://bank.example/", "sha256": "0" * 64,
                      "bytes": 1, "kind": "served"}]}),
        ("a run that fetched nothing, with a page named by a site",
         "malformed",
         {"fetch": None, "pages": [{"path": "https://bank.example/",
                                    "fetch": None}]}),
        ("a judged page that is not a page of the bundle", "malformed",
         {"fetch": None, "pages": [{"path": "a.html", "fetch": None}],
          "judged": {"summary": {}, "pages": [{"path": "https://bank."
                                                       "example/"}]}}),
        ("judged pages that are pages of the bundle", "fine",
         {"fetch": None, "pages": [{"path": "a.html", "fetch": None}],
          "judged": {"summary": {}, "pages": [{"path": "a.html"}]}}),
        # The run's own record names a clean URL, so it is the page's
        # record that is refused (R5F-9).
        ("a page record whose final_url has a user name", "malformed",
         {"fetch": dict(run, pages=1),
          "pages": [{"path": "https://login.bank.example:443@www.example."
                             "com/a", "fetch": {"final_url": "https://login."
                             "bank.example:443@www.example.com/a"}}]}),
        # pages and inputs are arrays in every bundle (§5 "The body"); a
        # null judged.pages counts as absent.
        ("pages and inputs that are null", "malformed",
         {"fetch": dict(run, pages=0), "pages": None, "inputs": None}),
        ("judged pages that are null, as if absent", "fine",
         {"fetch": None, "pages": [{"path": "a.html", "fetch": None}],
          "judged": {"summary": {}, "pages": None}}),
        # Every page records its capture, or null for a file read as it is
        # (SA-4): a page without the member is not a page this format has.
        ("a page with no fetch member", "malformed",
         {"fetch": None, "pages": [{"path": "a.html"}]}),
    ]
    out = []

    def got(bundle):
        try:
            B.check_body(bundle)
            B.bundle_bound_values(bundle)
            return "fine"
        except B.MalformedBundle:
            return "malformed"
    for fetch, page, result in cases:
        bundle = page_bundle(fetch, page)
        assert got(bundle) == result, (fetch, page, got(bundle))
        out.append({"fetch": fetch, "page": page, "bundle": bundle,
                    "result": result})
    for description, result, records in shapes:
        bundle = whole_bundle(records)
        assert got(bundle) == result, (description, got(bundle))
        out.append({"description": description, "bundle": bundle,
                    "result": result})
    return out


def unsigned_bundle() -> dict:
    """The §9.2 bundle, unsigned."""
    return {
        "bundle_format": B.BUNDLE_FORMAT,
        "created_at": "2026-01-01T00:00:00+00:00",
        "tool": {"name": "bellbriar-harness", "version": "0.3.0"},
        "rulebook_version": "0.1.0",
        "rulebook_sha256": hashlib.sha256(b"a rulebook").hexdigest(),
        "domain": "example.com",
        "fetch": {"final_url": "https://www.example.com/",
                  "host": "www.example.com", "pages": 0},
        "pack": {"name": "wcag", "version": "1.0.0",
                 "manifest_sha256": "0" * 64, "files": 1,
                 "signature_verified": False},
        "inputs": [{"path": "fixtures/good.html", "sha256": "f" * 64, "bytes": 1263}],
        "layers": [],
        "coverage_note": "천연 발효빵",
        "site": {"site_weighted_pass_rate": 1.0, "pct_pages_tier1_clean": 0.5,
                 "total_fail_findings": 0},
        "pages": [],
        "judged": None,
        "attestation": "A test vector: evidence of nothing.",
        "signature": None,
    }


def bundle_vector(priv_hex: str, pub_hex: str, kid: str) -> dict:
    bundle = unsigned_bundle()
    digest = B.bundle_digest(bundle)
    stmt = B.build_statement(B.bundle_bound_values(bundle), kid,
                             "vector-signer", B.SELF_SIGNED, digest,
                             signed_at="2026-01-01T00:00:01+00:00")
    stmt_digest = B.statement_digest(stmt)
    priv = B.ed25519.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(priv_hex))
    message = B.SIGNING_CONTEXTS[B.STATEMENT_FORMAT] + bytes.fromhex(stmt_digest)
    sig_b64 = base64.b64encode(priv.sign(message)).decode("ascii")
    signed = dict(bundle)
    signed["signature"] = {"alg": "Ed25519", "context": B.STATEMENT_FORMAT,
                           "key_id": kid, "statement": stmt,
                           "signature_b64": sig_b64}
    ok, reason = B.verify_bundle(signed, pub_hex)
    assert ok, reason
    return {
        "unsigned_bundle": bundle,
        "canonical_body_utf8": B.canonical_bytes(
            {k: v for k, v in bundle.items() if k != "signature"}).decode("utf-8"),
        "bundle_digest_sha256": digest,
        "statement": stmt,
        "canonical_statement_utf8": B.canonical_bytes(stmt).decode("utf-8"),
        "statement_digest_sha256": stmt_digest,
        "signing_context_hex": B.SIGNING_CONTEXTS[B.STATEMENT_FORMAT].hex(),
        "signed_message_hex": message.hex(),
        "signature_b64": sig_b64,
        "signature_block": signed["signature"],
        "verify_result": reason,
    }


def small_order_parts(bv: dict, priv_hex: str, pub_hex: str) -> list[dict]:
    """§6 step 3 (§9.2): signatures on which the equations RFC 8032 allows
    disagree. The first is the vector key's over the vector statement, with
    the point of order 8 added to R. The others are under the vector key
    with that point added, a key no RFC 8032 key generation makes, over the
    vector statement naming that key: R as the RFC derives it, and R with
    the part that makes [S]B = R + [k]A hold (with k reduced modulo L, as
    §6 step 3 says, and not without)."""
    bundle = bv["unsigned_bundle"]
    plain, public = _sign(priv_hex, bytes.fromhex(bv["signed_message_hex"]))
    assert base64.b64encode(plain).decode("ascii") == bv["signature_b64"]
    assert public.hex() == pub_hex
    mixed = _sign(priv_hex, b"", part_in_key=True)[1].hex()
    B.check_public_key(mixed)                       # verify takes it
    stmt = B.build_statement(B.bundle_bound_values(bundle),
                             B.key_id_for(mixed), "vector-signer",
                             B.SELF_SIGNED, bv["bundle_digest_sha256"],
                             signed_at="2026-01-01T00:00:01+00:00")
    out = []
    for description, key_hex, statement, part_in_key, parts, want in (
            ("R with a part of order 8", pub_hex, bv["statement"], False,
             range(1, 2), (False, False, True)),
            ("a key with a part of order 8", mixed, stmt, True,
             range(0, 1), (False, False, True)),
            ("a key with a part of order 8, and R with the part that cancels "
             "it", mixed, stmt, True, range(1, 8), (True, False, True))):
        message = (B.SIGNING_CONTEXTS[B.STATEMENT_FORMAT]
                   + bytes.fromhex(B.statement_digest(statement)))
        want = dict(zip(("cofactorless", "cofactorless_k_not_reduced",
                         "cofactored"), want))
        raw = _first(priv_hex, message, want, part_in_key=part_in_key,
                     parts_in_r=parts)
        assert not B.weak_point(raw[:32])
        block = {"alg": "Ed25519", "context": B.STATEMENT_FORMAT,
                 "key_id": statement["key_id"], "statement": statement,
                 "signature_b64": base64.b64encode(raw).decode("ascii")}
        ok, reason = B.verify_bundle(dict(bundle, signature=block), key_hex)
        assert ok is want["cofactorless"], (description, reason)
        out.append({"description": description, "public_hex": key_hex,
                    "signed_message_hex": message.hex(),
                    "signature_block": block, "equations": want,
                    "result": "valid" if ok else "invalid"})
    return out


def signature_blocks(bv: dict, pub_hex: str) -> list[dict]:
    """§5 "The signature block" (§9.7): the bundle vector's own signature
    block, and variations of it. A block has exactly the five members, with
    `alg` "Ed25519" and `context` "bellbriar-signature/1"; anything else is
    malformed (N10), since only the statement inside it is signed."""
    good = bv["signature_block"]
    legacy = {"alg": "Ed25519", "key_id": good["key_id"],
              "digest_sha256": bv["bundle_digest_sha256"],
              "signature_b64": good["signature_b64"]}
    cases = [
        ("the vector's own block", good, "valid"),
        ("an extra member", dict(good, verified_by="Bellbriar"), "malformed"),
        ("an extra member that is null", dict(good, log=None), "malformed"),
        ("alg that is not Ed25519", dict(good, alg="RS256"), "malformed"),
        ("context that is the pack format",
         dict(good, context="bellbriar-pack/1"), "malformed"),
        ("no alg", {k: v for k, v in good.items() if k != "alg"},
         "malformed"),
        ("no context", {k: v for k, v in good.items() if k != "context"},
         "malformed"),
        ("key_id that is a number", dict(good, key_id=172), "malformed"),
        ("signature_b64 that is null", dict(good, signature_b64=None),
         "malformed"),
        ("statement that is a string", dict(good, statement="signed"),
         "malformed"),
        ("statement that is null", dict(good, statement=None), "malformed"),
        ("a __proto__ member", {**good, "__proto__": {"alg": "Ed25519"}},
         "malformed"),
        ("a statement with a member the format does not define",
         dict(good, statement=dict(good["statement"], certified="WCAG AA")),
         "malformed"),
        ("a statement with a __proto__ member",
         dict(good, statement={**good["statement"], "__proto__": None}),
         "malformed"),
        ("the pre-0.3.0 bare-digest form", legacy, "malformed"),
        ("signature_b64 without its padding",
         dict(good, signature_b64=good["signature_b64"].rstrip("=")),
         "invalid"),
        ("key_id of another key", dict(good, key_id="0" * 16), "invalid"),
    ]
    out = []
    for description, block, result in cases:
        bundle = dict(bv["unsigned_bundle"], signature=block)
        try:
            ok, _ = B.verify_bundle(bundle, pub_hex)
            got = "valid" if ok else "invalid"
        except B.MalformedBundle:
            got = "malformed"
        assert got == result, (description, got)
        out.append({"description": description, "signature_block": block,
                    "result": result})
    return out


def pack_vector(priv_hex: str, pub_hex: str, kid: str) -> dict:
    manifest = {"name": "wcag", "version": "1.0.0", "rulebook_min": "0.1.0",
                "files": {"SKILL.md": hashlib.sha256(b"# wcag\n").hexdigest()}}
    body = P.manifest_body(manifest)
    signed = P.sign_manifest(dict(manifest), priv_hex)
    assert P.verify_signature(signed, pub_hex)
    return {
        "manifest_body": body,
        "canonical_body_utf8": B.canonical_bytes(body).decode("utf-8"),
        "body_digest_sha256": hashlib.sha256(B.canonical_bytes(body)).hexdigest(),
        "signing_context_hex": B.SIGNING_CONTEXTS[P.PACK_FORMAT].hex(),
        "signed_message_hex": P.pack_message(body).hex(),
        "signature_block": signed["signature"],
    }


def main() -> int:
    priv_hex, pub_hex, kid = vector_key()
    vectors = {
        "spec": "docs/CANONICALIZATION.md",
        "vector_key": {
            "derivation": f'private key = SHA-256("{VECTOR_KEY_SEED}") — public by construction',
            "private_hex": priv_hex, "public_hex": pub_hex, "key_id": kid,
        },
        "canonicalization": canonical_cases(),
        "rejected": rejected_cases(),
        "malformed_texts": malformed_texts(),
        "malformed_bytes": malformed_bytes(),
        "well_formed_spellings": well_formed_spellings(),
        "url_hosts": url_hosts(),
        "host_relations": host_relations(),
        "page_records": page_records(),
        "domain_spellings": domain_spellings(),
        "bundle": bundle_vector(priv_hex, pub_hex, kid),
        "pack": pack_vector(priv_hex, pub_hex, kid),
    }
    vectors["signature_blocks"] = signature_blocks(vectors["bundle"], pub_hex)
    vectors["small_order_parts"] = small_order_parts(vectors["bundle"],
                                                     priv_hex, pub_hex)
    OUT.write_text(json.dumps(vectors, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}  key_id={kid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
