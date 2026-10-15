"""docs/CANONICALIZATION.md is executable.

Three layers of checking:
  1. the library reproduces every value in docs/canonicalization-vectors.json
     (canonical bytes, digests, deterministic Ed25519 signatures);
  2. every such value appears verbatim in docs/CANONICALIZATION.md, so the
     prose cannot drift from the implementation without this failing;
  3. the rules the spec relies on — number normalization, ASCII keys,
     domain separation between artifact types, legacy rejection — hold.
"""
import base64
import contextlib
import hashlib
import io
import json
import random
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bellbriar_harness import bundle as B                      # noqa: E402
from tests.bundle_body import BODY  # noqa: E402
from bellbriar_harness import pack as P                        # noqa: E402

SPEC = ROOT / "docs" / "CANONICALIZATION.md"
VECTORS = ROOT / "docs" / "canonicalization-vectors.json"


def load():
    return json.loads(VECTORS.read_text(encoding="utf-8"))


@unittest.skipUnless(B.HAVE_ED25519, "cryptography not installed")
class TestVectorKey(unittest.TestCase):
    def test_key_is_derived_from_the_published_seed(self):
        v = load()["vector_key"]
        seed = "bellbriar-canonicalization-vector-key/1"
        self.assertEqual(v["private_hex"],
                         hashlib.sha256(seed.encode()).hexdigest())
        priv = B.ed25519.Ed25519PrivateKey.from_private_bytes(
            bytes.fromhex(v["private_hex"]))
        self.assertEqual(priv.public_key().public_bytes_raw().hex(),
                         v["public_hex"])
        self.assertEqual(B.key_id_for(v["public_hex"]), v["key_id"])


class TestCanonicalizationVectors(unittest.TestCase):
    def test_library_reproduces_every_case(self):
        for case in load()["canonicalization"]:
            with self.subTest(case=case["description"]):
                got = B.canonical_bytes(case["input"])
                self.assertEqual(got.decode("utf-8"), case["canonical_utf8"])
                self.assertEqual(got.hex(), case["canonical_hex"])
                self.assertEqual(hashlib.sha256(got).hexdigest(), case["sha256"])

    def test_every_case_appears_in_the_spec(self):
        spec = SPEC.read_text(encoding="utf-8")
        for case in load()["canonicalization"]:
            with self.subTest(case=case["description"]):
                self.assertIn(case["canonical_utf8"], spec)


class TestNumberRules(unittest.TestCase):
    """§2 rule 4 — the Python/JavaScript divergence that would have made
    every 100%-pass-rate bundle unverifiable outside Python."""

    def test_integer_valued_float_is_an_integer(self):
        self.assertEqual(B.canonical_bytes({"r": 1.0}), b'{"r":1}')
        self.assertEqual(B.canonical_bytes({"r": 100.0}), b'{"r":100}')

    def test_negative_zero(self):
        self.assertEqual(B.canonical_bytes({"r": -0.0}), b'{"r":0}')

    def test_non_integer_float_is_shortest_roundtrip(self):
        self.assertEqual(B.canonical_bytes({"r": 0.1}), b'{"r":0.1}')
        self.assertEqual(B.canonical_bytes({"r": 0.6757}), b'{"r":0.6757}')

    def test_bool_is_not_normalized_to_int(self):
        self.assertEqual(B.canonical_bytes({"b": True}), b'{"b":true}')

    def test_nan_and_infinity_rejected(self):
        for bad in (float("nan"), float("inf"), float("-inf")):
            with self.assertRaises(ValueError):
                B.canonical_bytes({"x": bad})

    def test_huge_integer_rejected(self):
        with self.assertRaises(ValueError):
            B.canonical_bytes({"x": 2 ** 53 + 1})
        B.canonical_bytes({"x": 2 ** 53})  # the boundary itself is allowed

    def test_non_ascii_or_non_string_key_rejected(self):
        with self.assertRaises(ValueError):
            B.canonical_bytes({"ключ": 1})
        with self.assertRaises(ValueError):
            B.canonical_bytes({1: "a"})

    def test_non_ascii_values_are_raw_utf8(self):
        self.assertEqual(B.canonical_bytes({"s": "빵"}), '{"s":"빵"}'.encode())

    def test_digest_is_the_same_for_1_and_1_point_0(self):
        """A JavaScript verifier parses `1.0` as 1; Python must agree."""
        self.assertEqual(B.bundle_digest({"site": {"rate": 1.0}, "signature": None}),
                         B.bundle_digest({"site": {"rate": 1}, "signature": None}))

    def test_numbers_python_and_javascript_print_differently_are_rejected(self):
        """Python prints these one way and JavaScript another (5e-05 vs
        0.00005; 1152921504606846976 vs 1152921504606847000), so emitting
        them would give a digest only Python reproduces."""
        for bad in (1e-05, 5e-05, 1e-07, 2.0 ** 60, 1e21, -2.0 ** 54):
            with self.subTest(value=bad), self.assertRaises(ValueError):
                B.canonical_bytes({"x": bad})

    def test_decimals_below_0_0001_rejected(self):
        for bad in (9.999999999999999e-05, -0.00005, 1e-300, 5e-324):
            with self.subTest(value=bad), self.assertRaises(ValueError) as cm:
                B.canonical_bytes({"x": bad})
            self.assertIn("smaller than 0.0001", str(cm.exception))

    def test_long_decimals_print_the_same_and_are_accepted(self):
        """Only the exponent switch below 0.0001 and the digits above 2^53
        differ between the two languages; a long decimal does not."""
        for ok, text in ((0.1 + 0.2, b'{"x":0.30000000000000004}'),
                         (0.12345, b'{"x":0.12345}'),
                         (4503599627370495.5, b'{"x":4503599627370495.5}')):
            with self.subTest(value=ok):
                self.assertEqual(B.canonical_bytes({"x": ok}), text)

    def test_the_canonical_range_is_accepted(self):
        for ok, text in ((0.0001, b'{"x":0.0001}'), (-0.0001, b'{"x":-0.0001}'),
                         (12345.6789, b'{"x":12345.6789}'),
                         (2.0 ** 53, b'{"x":9007199254740992}'),
                         (-(2 ** 53), b'{"x":-9007199254740992}')):
            with self.subTest(value=ok):
                self.assertEqual(B.canonical_bytes({"x": ok}), text)

    def test_lone_surrogate_rejected(self):
        with self.assertRaises(ValueError) as cm:
            B.canonical_bytes({"s": "a\ud800b"})
        self.assertIn("$.s", str(cm.exception))

    def test_error_names_the_offending_path(self):
        with self.assertRaises(ValueError) as cm:
            B.canonical_bytes({"site": {"pages": [{"rate": 5e-05}]}})
        self.assertIn("$.site.pages[0].rate", str(cm.exception))


class TestRejectedVectors(unittest.TestCase):
    """Every input the vectors list as rejected is rejected, both as the
    Python literal and, where JSON can express it, as parsed JSON text —
    which is how a verifier meets it."""

    def test_python_literals_are_rejected(self):
        for case in load()["rejected"]:
            value = eval(case["input_python"],  # our own vector file
                         {"__builtins__": {}}, {"float": float})
            with self.subTest(case=case["description"]), \
                    self.assertRaises(ValueError):
                B.canonical_bytes(value)

    def test_json_texts_are_rejected(self):
        cases = [c for c in load()["rejected"] if c.get("input_json")]
        self.assertGreaterEqual(len(cases), 5)
        for case in cases:
            with self.subTest(case=case["description"]), \
                    self.assertRaises(ValueError):
                B.canonical_bytes(B.load_bundle(case["input_json"]))


class TestParsingRules(unittest.TestCase):
    """§6: a file whose text can be read as a different value from the one
    that gets verified is malformed. Other spellings of the same values are
    fine: the file need not be canonical, only unambiguous."""

    def test_malformed_texts_are_refused(self):
        for case in load()["malformed_texts"]:
            with self.subTest(case=case["description"]), \
                    self.assertRaises(ValueError):
                B.canonical_bytes(B.load_bundle(case["text"]))

    def test_other_spellings_are_accepted(self):
        for case in load()["well_formed_spellings"]:
            with self.subTest(text=case["text"]):
                got = B.canonical_bytes(B.load_bundle(case["text"])).decode()
                self.assertEqual(got, case["canonical_utf8"])

    def test_malformed_bytes_are_refused(self):
        for case in load()["malformed_bytes"]:
            with self.subTest(case=case["description"]), \
                    tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "b.json"
                path.write_bytes(bytes.fromhex(case["hex"]))
                with self.assertRaises(B.MalformedBundle):
                    B.read_bundle(path)

    def test_texts_appear_in_the_spec(self):
        spec = SPEC.read_text(encoding="utf-8")
        v = load()
        for case in v["malformed_texts"] + v["well_formed_spellings"]:
            with self.subTest(text=case["text"]):
                self.assertIn(case["text"], spec)
        for case in v["malformed_bytes"]:
            with self.subTest(hex=case["hex"]):
                self.assertIn(case["hex"], spec)

    def test_reasons_name_the_problem(self):
        with self.assertRaises(B.MalformedBundle) as cm:
            B.load_bundle('{"domain":"a.com","domain":"b.com"}')
        self.assertIn("duplicate member name", str(cm.exception))
        with self.assertRaises(B.MalformedBundle) as cm:
            B.load_bundle('{"x":0.67570000000000001}')
        self.assertIn("is read as 0.6757", str(cm.exception))


class TestHostRelations(unittest.TestCase):
    """§5, §6 step 6, §9.4 and §9.5: the library and the spec agree on every
    case."""

    def test_library_reproduces_every_case(self):
        for case in load()["host_relations"]:
            with self.subTest(case=case):
                self.assertEqual(B.host_scope(case["host"], case["domain"]),
                                 case["relation"])
        for case in load()["url_hosts"]:
            with self.subTest(case=case):
                self.assertEqual(B.url_host(case["final_url"]), case["host"])

    def test_every_case_appears_in_the_spec(self):
        spec = SPEC.read_text(encoding="utf-8")

        def cell(value, none="null"):
            return none if value is None else f"`{value}`"
        for case in load()["host_relations"]:
            with self.subTest(case=case):
                self.assertIn(f"| {cell(case['host'])} | {cell(case['domain'])}"
                              f" | {case['relation']} |", spec)
        for case in load()["url_hosts"]:
            with self.subTest(case=case):
                self.assertIn(f"| `{case['final_url']}` | "
                              f"{cell(case['host'], 'malformed (§6)')} |", spec)

    def test_page_records_name_the_bound_host(self):
        """§5 "Pages" and §9.6: each vector's bundle gets its result, and
        the spec's tables list every case."""
        import json as _json
        spec = SPEC.read_text(encoding="utf-8")
        vectors = load()
        # Each case is a whole bundle (R5D-4): the §9.2 bundle, unsigned,
        # with its own fetch, pages, inputs and judged.
        base = {k: v for k, v in vectors["bundle"]["unsigned_bundle"].items()
                if k not in ("fetch", "pages", "inputs", "judged")}

        def verdict(bundle):
            try:
                B.check_body(bundle)
                B.bundle_bound_values(bundle)
                return "fine"
            except B.MalformedBundle:
                return "malformed"
        for case in vectors["page_records"]:
            with self.subTest(case=case):
                bundle = case["bundle"]
                self.assertEqual({k: v for k, v in bundle.items()
                                  if k not in ("fetch", "pages", "inputs",
                                               "judged")}, base)
                self.assertEqual(verdict(bundle), case["result"])
                # And verify itself says malformed, or reaches a verdict.
                try:
                    B.verify_bundle(bundle, vectors["vector_key"]["public_hex"])
                    reached = "fine"
                except B.MalformedBundle:
                    reached = "malformed"
                self.assertEqual(reached, case["result"])
                if "description" in case:
                    self.assertIn(f"| {case['description']} | "
                                  f"{case['result']} |", spec)
                    continue
                fetch = ("null" if case["fetch"] is None
                         else f"`{case['fetch']}`")
                page = ("null" if case["page"] is None else "`" + _json.dumps(
                    case["page"], separators=(", ", ": "),
                    ensure_ascii=False) + "`")
                self.assertIn(f"| {fetch} | {page} | {case['result']} |", spec)
                # The host cases' bundles are the ones §9.6 describes.
                if case["fetch"] is None:
                    self.assertEqual(
                        {k: bundle[k] for k in ("fetch", "pages")},
                        {"fetch": None, "pages": [
                            {"path": "index.html", "fetch": case["page"]}]})
                else:
                    self.assertEqual(bundle["fetch"], {
                        "final_url": case["fetch"], "pages": 1})
                    self.assertEqual(bundle["pages"][0]["path"], (
                        case["page"] or {}).get("final_url", case["fetch"]))
        for pages in ({"pages": {"0": {}}}, {"pages": ["x"]},
                      {"pages": [{"fetch": "https://example.com/"}]}):
            with self.subTest(pages=pages), self.assertRaises(B.MalformedBundle):
                B.bundle_bound_values(pages)

    def test_a_domain_is_spelled_one_way(self):
        """SA-4, §5 and §9.8: a domain in another spelling is malformed, and
        every name the harness records is spelled so."""
        spec = SPEC.read_text(encoding="utf-8")
        vectors = load()
        base = vectors["bundle"]["unsigned_bundle"]
        for case in vectors["domain_spellings"]:
            with self.subTest(domain=case["domain"]):
                try:
                    B.check_body(dict(base, domain=case["domain"]))
                    got = "fine"
                except B.MalformedBundle:
                    got = "malformed"
                self.assertEqual(got, case["result"])
                self.assertIn(f"| `{json.dumps(case['domain'])}` | "
                              f"{case['result']} |", spec)
        for given in ("Example.COM", "https://www.Example.com/x",
                      "b\u00fccher.de",
                      "example.com.", "[::1]", "192.0.2.1", "::ffff:7f00:1",
                      "xn--bcher-kva.de", "WWW.CornerBakery.example"):
            with self.subTest(given=given):
                self.assertTrue(B.spelled_once(B.normalize_host(given)))

    def test_a_fetch_block_names_one_host(self):
        base = {**BODY, "bundle_format": B.BUNDLE_FORMAT, "domain": "example.com",
                "rulebook_version": "0.1.0", "signature": None}
        ok = dict(base, fetch={"final_url": "https://Example.com:443/x",
                               "pages": 0})
        self.assertEqual(B.bundle_bound_values(ok)["host"], "example.com")
        for fetch in ({"final_url": "https://staging.example.com/",
                       "host": "example.com"},
                      {"final_url": "https://staging.example.com/",
                       "host": None},
                      {"host": "example.com"},
                      {"final_url": "https://bücher.de/"}):
            with self.subTest(fetch=fetch), self.assertRaises(B.MalformedBundle):
                B.bundle_bound_values(dict(base, fetch=fetch))


@unittest.skipUnless(B.HAVE_ED25519, "cryptography not installed")
class TestSignatureBlocks(unittest.TestCase):
    """§5 "The signature block" and §9.7 (N10): a block of exactly five
    members, `alg` and `context` fixed; anything else is malformed, since
    only the statement inside it is signed."""

    def test_library_gives_each_case_its_result(self):
        v = load()
        for case in v["signature_blocks"]:
            with self.subTest(case=case["description"]):
                bundle = dict(v["bundle"]["unsigned_bundle"],
                              signature=case["signature_block"])
                try:
                    ok, _ = B.verify_bundle(bundle,
                                            v["vector_key"]["public_hex"])
                    got = "valid" if ok else "invalid"
                except B.MalformedBundle:
                    got = "malformed"
                self.assertEqual(got, case["result"])

    def test_every_case_appears_in_the_spec(self):
        spec = SPEC.read_text(encoding="utf-8")
        for case in load()["signature_blocks"]:
            with self.subTest(case=case["description"]):
                self.assertIn(f"| {case['description']} | {case['result']} |",
                              spec)

    def test_an_unsigned_member_cannot_ride_along(self):
        """What the closed block is for: a member added after signing,
        which a reader would take for part of the evidence."""
        v = load()
        block = dict(v["bundle"]["signature_block"],
                     verified_by="Bellbriar (production signer)")
        with self.assertRaises(B.MalformedBundle) as cm:
            B.verify_bundle(dict(v["bundle"]["unsigned_bundle"],
                                 signature=block),
                            v["vector_key"]["public_hex"])
        self.assertIn("verified_by", str(cm.exception))


class TestProducerConforms(unittest.TestCase):
    """build_bundle rounds to the canonical precision instead of handing
    canonical_bytes a value it would refuse."""

    def test_conform_rounds_and_repairs(self):
        body = B.conform({"rate": 0.123456, "t": [1e-05, 2.5, 3.0],
                          "s": "ok\ud800", "n": 7, "b": True})
        self.assertEqual(body, {"rate": 0.1235, "t": [0.0, 2.5, 3.0],
                                "s": "ok\ufffd", "n": 7, "b": True})
        B.canonical_bytes(body)   # and the result canonicalizes

    def test_conform_leaves_nan_for_canonical_bytes_to_refuse(self):
        body = B.conform({"x": float("nan")})
        with self.assertRaises(ValueError):
            B.canonical_bytes(body)


@unittest.skipUnless(B.HAVE_ED25519, "cryptography not installed")
class TestBundleVector(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        v = load()
        cls.key = v["vector_key"]
        cls.v = v["bundle"]
        cls.spec = SPEC.read_text(encoding="utf-8")

    def test_canonical_body_and_digest(self):
        body = {k: x for k, x in self.v["unsigned_bundle"].items()
                if k != "signature"}
        self.assertEqual(B.canonical_bytes(body).decode(), self.v["canonical_body_utf8"])
        self.assertEqual(B.bundle_digest(self.v["unsigned_bundle"]),
                         self.v["bundle_digest_sha256"])

    def test_statement_and_message(self):
        stmt = self.v["statement"]
        self.assertEqual(B.canonical_bytes(stmt).decode(),
                         self.v["canonical_statement_utf8"])
        self.assertEqual(B.statement_digest(stmt), self.v["statement_digest_sha256"])
        ctx = B.SIGNING_CONTEXTS[B.STATEMENT_FORMAT]
        self.assertEqual(ctx.hex(), self.v["signing_context_hex"])
        self.assertEqual((ctx + bytes.fromhex(self.v["statement_digest_sha256"])).hex(),
                         self.v["signed_message_hex"])

    def test_signature_is_reproduced_byte_for_byte(self):
        """Ed25519 is deterministic: re-signing must give the same bytes."""
        priv = B.ed25519.Ed25519PrivateKey.from_private_bytes(
            bytes.fromhex(self.key["private_hex"]))
        self.assertEqual(B._sign_statement(self.v["statement"], priv),
                         self.v["signature_b64"])

    def test_vector_bundle_verifies(self):
        signed = dict(self.v["unsigned_bundle"])
        signed["signature"] = self.v["signature_block"]
        ok, reason = B.verify_bundle(signed, self.key["public_hex"])
        self.assertTrue(ok, reason)
        self.assertEqual(reason, self.v["verify_result"])

    def test_values_appear_in_the_spec(self):
        for key in ("canonical_body_utf8", "bundle_digest_sha256",
                    "canonical_statement_utf8", "statement_digest_sha256",
                    "signing_context_hex", "signed_message_hex", "signature_b64"):
            with self.subTest(field=key):
                self.assertIn(self.v[key], self.spec)
        for key in ("private_hex", "public_hex", "key_id"):
            with self.subTest(field=key):
                self.assertIn(self.key[key], self.spec)


@unittest.skipUnless(B.HAVE_ED25519, "cryptography not installed")
class TestSmallOrderParts(unittest.TestCase):
    """SA-1, §6 step 3 and §9.2: a verifier checks [S]B = R + [k]A, with k
    reduced modulo L, and not the cofactored equation RFC 8032 states. On
    these vectors the equations disagree, and verify follows the first."""

    @classmethod
    def setUpClass(cls):
        v = load()
        cls.key = v["vector_key"]
        cls.bv = v["bundle"]
        cls.cases = v["small_order_parts"]
        cls.spec = SPEC.read_text(encoding="utf-8")
        cls.tool = vectors_tool()

    def test_the_arithmetic_signs_as_the_library_does(self):
        message = bytes.fromhex(self.bv["signed_message_hex"])
        raw, public = self.tool._sign(self.key["private_hex"], message)
        self.assertEqual(base64.b64encode(raw).decode(),
                         self.bv["signature_b64"])
        self.assertEqual(public.hex(), self.key["public_hex"])
        self.assertEqual(self.tool.equations(public, message, raw), {
                "cofactorless": True, "cofactorless_k_not_reduced": True,
                "cofactored": True})

    def test_the_equations_disagree_as_recorded(self):
        self.assertEqual(
            [(c["description"], c["result"]) for c in self.cases],
            [("R with a part of order 8", "invalid"),
             ("a key with a part of order 8", "invalid"),
             ("a key with a part of order 8, and R with the part that "
              "cancels it", "valid")])
        for c in self.cases:
            with self.subTest(case=c["description"]):
                message = bytes.fromhex(c["signed_message_hex"])
                raw = base64.b64decode(c["signature_block"]["signature_b64"])
                statement = c["signature_block"]["statement"]
                self.assertEqual(
                    message, B.SIGNING_CONTEXTS[B.STATEMENT_FORMAT]
                    + bytes.fromhex(B.statement_digest(statement)))
                self.assertEqual(
                    self.tool.equations(bytes.fromhex(c["public_hex"]),
                                        message, raw), c["equations"])
                self.assertTrue(c["equations"]["cofactored"])
                self.assertFalse(c["equations"]["cofactorless_k_not_reduced"])
                self.assertEqual(c["equations"]["cofactorless"],
                                 c["result"] == "valid")
                self.assertFalse(B.weak_point(raw[:32]))

    def test_verify_follows_the_equation_it_names(self):
        for c in self.cases:
            with self.subTest(case=c["description"]):
                bundle = dict(self.bv["unsigned_bundle"],
                              signature=c["signature_block"])
                ok, reason = B.verify_bundle(bundle, c["public_hex"])
                self.assertEqual(ok, c["result"] == "valid", reason)
                if not ok:
                    self.assertIn("[S]B = R + [k]A fails", reason)

    def test_values_appear_in_the_spec(self):
        for c in self.cases:
            with self.subTest(case=c["description"]):
                self.assertIn(c["signature_block"]["signature_b64"], self.spec)
                self.assertIn(c["public_hex"], self.spec)
                self.assertIn(c["signature_block"]["key_id"], self.spec)


@unittest.skipUnless(B.HAVE_ED25519, "cryptography not installed")
class TestPackVector(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        v = load()
        cls.key = v["vector_key"]
        cls.v = v["pack"]
        cls.spec = SPEC.read_text(encoding="utf-8")

    def test_body_digest_and_message(self):
        body = self.v["manifest_body"]
        self.assertEqual(B.canonical_bytes(body).decode(), self.v["canonical_body_utf8"])
        self.assertEqual(hashlib.sha256(B.canonical_bytes(body)).hexdigest(),
                         self.v["body_digest_sha256"])
        self.assertEqual(B.SIGNING_CONTEXTS[P.PACK_FORMAT].hex(),
                         self.v["signing_context_hex"])
        self.assertEqual(P.pack_message(body).hex(), self.v["signed_message_hex"])

    def test_signature_reproduced_and_verifies(self):
        signed = P.sign_manifest(dict(self.v["manifest_body"]), self.key["private_hex"])
        self.assertEqual(signed["signature"], self.v["signature_block"])
        self.assertTrue(P.verify_signature(signed, self.key["public_hex"]))

    def test_values_appear_in_the_spec(self):
        for key in ("canonical_body_utf8", "body_digest_sha256",
                    "signing_context_hex", "signed_message_hex"):
            with self.subTest(field=key):
                self.assertIn(self.v[key], self.spec)
        self.assertIn(self.v["signature_block"]["signature_b64"], self.spec)


@unittest.skipUnless(B.HAVE_ED25519, "cryptography not installed")
class TestDomainSeparation(unittest.TestCase):
    """§4 — a signature over one artifact type is not a signature over
    another, even under a shared key and an identical inner digest."""

    def setUp(self):
        self.priv_hex, self.pub_hex, self.kid = B.generate_keypair()
        self.priv = B.ed25519.Ed25519PrivateKey.from_private_bytes(
            bytes.fromhex(self.priv_hex))

    def test_pack_and_statement_signatures_differ_for_the_same_digest(self):
        digest = hashlib.sha256(b"same").digest()
        pack_sig = self.priv.sign(B.SIGNING_CONTEXTS[P.PACK_FORMAT] + digest)
        stmt_sig = self.priv.sign(B.SIGNING_CONTEXTS[B.STATEMENT_FORMAT] + digest)
        self.assertNotEqual(pack_sig, stmt_sig)

    def test_pack_signature_cannot_be_presented_as_a_statement_signature(self):
        bundle = {**BODY, "bundle_format": B.BUNDLE_FORMAT, "domain": "x.com",
                  "rulebook_version": "0.1.0", "signature": None}
        signed = B.sign_bundle_local(dict(bundle), self.priv_hex)
        stmt = signed["signature"]["statement"]
        # Sign the statement digest under the PACK context instead.
        wrong = self.priv.sign(B.SIGNING_CONTEXTS[P.PACK_FORMAT]
                               + bytes.fromhex(B.statement_digest(stmt)))
        signed["signature"]["signature_b64"] = base64.b64encode(wrong).decode()
        ok, reason = B.verify_bundle(signed, self.pub_hex)
        self.assertFalse(ok)
        self.assertIn("signature invalid", reason)

    def test_statement_naming_the_pack_format_is_rejected(self):
        """The case the tests above miss: the statement itself names the
        pack format and carries a genuine pack-context signature. The
        verifier, not the statement, chooses the context."""
        bundle = {**BODY, "bundle_format": B.BUNDLE_FORMAT, "domain": "x.com",
                  "rulebook_version": "0.1.0", "signature": None}
        stmt = B.build_statement(B.bundle_bound_values(bundle), self.kid, "x",
                                 B.ATTESTED_SUBMISSION, B.bundle_digest(bundle))
        stmt["statement_format"] = P.PACK_FORMAT
        sig = self.priv.sign(P.pack_message(stmt))
        bundle["signature"] = {"alg": "Ed25519", "context": B.STATEMENT_FORMAT,
                               "key_id": self.kid, "statement": stmt,
                               "signature_b64": base64.b64encode(sig).decode()}
        ok, reason = B.verify_bundle(bundle, self.pub_hex)
        self.assertFalse(ok)
        self.assertIn("pack-manifest format", reason)

    def test_each_signer_signs_only_its_own_artifact(self):
        stmt = B.build_statement({}, self.kid, "x", B.SELF_SIGNED, "0" * 64)
        with self.assertRaises(P.PackError):
            P.sign_manifest(dict(stmt), self.priv_hex)
        with self.assertRaises(P.PackError):
            P.sign_manifest({"name": "wcag"}, self.priv_hex)   # not a manifest
        stmt["statement_format"] = P.PACK_FORMAT
        with self.assertRaises(ValueError):
            B._sign_statement(stmt, self.priv)

    def test_legacy_contextless_pack_signature_is_rejected(self):
        manifest = {"name": "wcag", "version": "1.0.0", "files": {}}
        body = P.manifest_body(manifest)
        legacy = self.priv.sign(hashlib.sha256(B.canonical_bytes(body)).digest())
        manifest["signature"] = {"alg": "Ed25519", "key_id": self.kid,
                                 "signature_b64": base64.b64encode(legacy).decode()}
        with self.assertRaises(P.PackError) as cm:
            P.verify_signature(manifest, self.pub_hex)
        self.assertIn("legacy", str(cm.exception))

    def test_signed_manifest_records_its_context(self):
        signed = P.sign_manifest({"name": "wcag", "version": "1.0.0",
                                  "files": {}}, self.priv_hex)
        self.assertEqual(signed["signature"]["context"], P.PACK_FORMAT)


def _random_canonical_objects(seed: int, count: int) -> list:
    """Objects inside §2: ASCII keys, integers up to 2^53, decimals from
    0.0001 up at every magnitude and precision, strings with every escape
    class, non-ASCII and astral characters, nesting."""
    rng = random.Random(seed)
    alphabet = ([chr(c) for c in range(0x20)] + list("\"\\/ azAZ09_-.") +
                ["\u007f", " ", "é", "빵", "\U0001f600", "﻿"])

    def number():
        kind = rng.randrange(5)
        if kind == 0:
            return rng.randint(-2 ** 53, 2 ** 53)
        if kind == 1:
            return float(rng.randint(-2 ** rng.randrange(54), 2 ** rng.randrange(54)))
        if kind == 2:   # four places, the producer's precision
            whole = rng.randint(0, 2 ** rng.randrange(53))
            value = float(f"{whole}.{rng.randrange(10000):04d}")
        elif kind == 3:  # full double precision, any exponent in range
            value = rng.random() * 10.0 ** rng.randint(-4, 15)
        else:            # an arbitrary bit pattern
            value = struct.unpack("<d", rng.getrandbits(64).to_bytes(8, "little"))[0]
        value *= rng.choice((1, -1))
        try:
            B.canonical_bytes({"v": value})
            return value
        except ValueError:
            return round(value, 2) if abs(value) < 2 ** 50 else 0.5

    def value(depth):
        kind = rng.randrange(7 if depth < 3 else 5)
        if kind == 0:
            return number()
        if kind == 1:
            return "".join(rng.choice(alphabet) for _ in range(rng.randrange(12)))
        if kind == 2:
            return rng.choice((True, False, None))
        if kind in (3, 4):
            return number()
        if kind == 5:
            return [value(depth + 1) for _ in range(rng.randrange(4))]
        keys = ["a", "B", "_", "10", "9", "a-b", "Z", "aa", ""]
        return {rng.choice(keys) + str(rng.randrange(3)): value(depth + 1)
                for _ in range(rng.randrange(5))}

    return [{"k" + str(i): value(0), "n": number()} for i in range(count)]


NODE = shutil.which("node")
JS_CHECK = ROOT / "tests" / "js" / "canonical_check.mjs"
EXAMPLE = ROOT / "examples" / "evidence" / "signed-bundle-example.json"
EXAMPLE_KEY = ROOT / "examples" / "evidence" / "reference-public-key.hex"
VALID, INVALID, MALFORMED = 0, 1, 2      # bellbriar-evidence verify exit codes


def _verification_cases() -> list[tuple]:
    """(name, file text, public key hex, verdict, fools a naive verifier).

    The naive verifier is what §2 alone would suggest: parse with a stock
    JSON parser, canonicalize, check the signature. The cases marked True
    verify under it while the file shows a reader something other than
    what was signed; §6's parsing rules are what catch them.
    """
    example = EXAMPLE.read_text(encoding="utf-8")
    example_pub = EXAMPLE_KEY.read_text().strip()

    def swap(old, new):
        assert example.count(old) == 1, old
        return example.replace(old, new)

    sig_b64 = json.loads(example)["signature"]["signature_b64"]
    alphabet = ("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
                "0123456789+/")
    assert sig_b64.endswith("==")
    last = alphabet.index(sig_b64[-3])       # 2 data bits, 4 unused bits
    lenient = sig_b64[:-3] + alphabet[(last & 0b110000) | ((last + 1) & 0b1111)] + "=="

    cases = [
        ("example", example, example_pub, VALID, False),
        ("the same signature in non-canonical Base64",
         swap(sig_b64, lenient), example_pub, INVALID, False),
        ("another spelling of the same number",
         swap('"site_weighted_pass_rate": 1.0', '"site_weighted_pass_rate": 1e0'),
         example_pub, VALID, False),
        ("body altered",
         swap('"total_fail_findings": 0', '"total_fail_findings": 1'),
         example_pub, INVALID, False),
        # A naive parser reads 1e999 as Infinity, which serializes as null;
        # every null the example holds is now checked for its type too
        # (judged: PR3-4), so the naive verifier refuses it as well.
        ("null replaced by 1e999",
         swap('"judged": null', '"judged": 1e999'), example_pub, MALFORMED,
         False),
        ("a number with more digits than a double holds",
         swap('"tier1_rules_total": 27', '"tier1_rules_total": 27.000000000000001'),
         example_pub, MALFORMED, True),
        ("a duplicate member name shown first",
         swap('\n  "domain": "cornerbakery.example",',
              '\n  "domain": "someone-else.example",'
              '\n  "domain": "cornerbakery.example",'),
         example_pub, MALFORMED, True),
    ]
    if not B.HAVE_ED25519:
        return cases

    # More, signed with a key of these tests' own: `bellbriar-evidence
    # verify` refuses the published vector key outright (R5B-17).
    v = load()
    seed = hashlib.sha256(b"bellbriar-verification-cases/1").digest()
    priv = B.ed25519.Ed25519PrivateKey.from_private_bytes(seed)
    case_pub = priv.public_key().public_bytes_raw().hex()
    key = {"public_hex": case_pub, "key_id": B.key_id_for(case_pub)}
    base = dict(v["bundle"]["unsigned_bundle"])
    at = "2026-09-30T00:00:00+00:00"

    stmt = B.build_statement(B.bundle_bound_values(base), key["key_id"], "x",
                             B.ATTESTED_SUBMISSION, B.bundle_digest(base), at)
    stmt["statement_format"] = P.PACK_FORMAT       # P4-01
    exploit = dict(base, signature={
        "alg": "Ed25519", "context": B.STATEMENT_FORMAT,
        "key_id": key["key_id"], "statement": stmt,
        "signature_b64": base64.b64encode(
            priv.sign(P.pack_message(stmt))).decode()})
    cases.append(("statement naming the pack format",
                  json.dumps(exploit, ensure_ascii=False), key["public_hex"],
                  INVALID, False))

    stringy = dict(base, pack="wcag@1.0.0 (signature verified)")
    bound = dict(B.bundle_bound_values(base), pack=None, pack_version=None)
    stmt = B.build_statement(bound, key["key_id"], "x", B.ATTESTED_SUBMISSION,
                             B.bundle_digest(stringy), at)
    stringy["signature"] = {"alg": "Ed25519", "context": B.STATEMENT_FORMAT,
                            "key_id": key["key_id"], "statement": stmt,
                            "signature_b64": B._sign_statement(stmt, priv)}
    cases.append(("pack given as a string", json.dumps(stringy, ensure_ascii=False),
                  key["public_hex"], MALFORMED, False))

    def signed(bundle: dict) -> dict:
        # The depth limit is lifted while signing, so a case can be signed
        # as a verifier without the limit would compute it (deep nesting).
        with mock.patch.object(B, "MAX_DEPTH", 10 ** 6):
            digest = B.bundle_digest(bundle)
        stmt = B.build_statement(B.bundle_bound_values(bundle), key["key_id"],
                                 "x", B.ATTESTED_SUBMISSION, digest, at)
        return dict(bundle, signature={
            "alg": "Ed25519", "context": B.STATEMENT_FORMAT,
            "key_id": key["key_id"], "statement": stmt,
            "signature_b64": B._sign_statement(stmt, priv)})

    # A genuine U+FFFD (the producer writes one for every lone surrogate) and
    # the same file with its three bytes swapped for one invalid byte, which
    # a lenient decoder turns back into U+FFFD.
    genuine = json.dumps(signed(dict(base, coverage_note="bad � byte")),
                         ensure_ascii=False).encode("utf-8")
    cases.append(("a replacement character, genuine", genuine,
                  key["public_hex"], VALID, False))
    cases.append(("an invalid UTF-8 byte a lenient decoder reads as U+FFFD",
                  genuine.replace("�".encode("utf-8"), b"\xff"),
                  key["public_hex"], MALFORMED, True))

    deep = [["leaf"]]
    for _ in range(B.MAX_DEPTH):
        deep = [deep]
    cases.append(("nested deeper than every verifier agrees to read",
                  json.dumps(signed(dict(base, layers=deep)), ensure_ascii=False),
                  key["public_hex"], MALFORMED, True))

    # §6 step 6: a run measured on a subdomain verifies (and is named); a
    # statement whose host is another site does not, however it was signed.
    def fetched(host):
        return dict(base, fetch={"final_url": f"https://{host}/", "host": host,
                                 "pages": 0})
    cases.append(("measured on a subdomain of the stated domain",
                  json.dumps(signed(fetched("staging.example.com")),
                             ensure_ascii=False),
                  key["public_hex"], VALID, False))
    cases.append(("measured on another site than the stated domain",
                  json.dumps(signed(fetched("example.net")), ensure_ascii=False),
                  key["public_hex"], INVALID, False))

    # The host is read from final_url: a fetch block may not name another,
    # and a statement that binds none does not cover a URL run.
    two_hosts = signed(fetched("staging.example.com"))
    two_hosts["fetch"] = dict(two_hosts["fetch"], host="example.com")
    cases.append(("a fetch block naming a host its final_url does not",
                  json.dumps(two_hosts, ensure_ascii=False),
                  key["public_hex"], MALFORMED, False))
    # §5 "Pages": a page record names the bound host, or (a file run) this
    # machine.
    def paged(host, page_host):
        page_url = f"http://{page_host}/a"
        return dict(base, fetch=(None if host is None else
                                 {"final_url": f"https://{host}/",
                                  "host": host, "pages": 1}),
                    pages=[{"path": page_url if host else "a.html",
                            "fetch": {"final_url": page_url}}])
    cases.append(("a URL run whose pages name its host",
                  json.dumps(signed(paged("www.example.com", "www.example.com")),
                             ensure_ascii=False),
                  key["public_hex"], VALID, False))
    def signed_as(bundle: dict, host) -> dict:
        # Signed for the values the client states (the signer never sees
        # the body), as a forger would: the verifier must catch the body.
        bound = {"bundle_format": bundle.get("bundle_format"),
                 "domain": bundle.get("domain"), "host": host,
                 "pack": None, "pack_version": None,
                 "rulebook_version": bundle.get("rulebook_version")}
        stmt = B.build_statement(bound, key["key_id"], "x",
                                 B.ATTESTED_SUBMISSION,
                                 B.bundle_digest(bundle), at)
        return dict(bundle, signature={
            "alg": "Ed25519", "context": B.STATEMENT_FORMAT,
            "key_id": key["key_id"], "statement": stmt,
            "signature_b64": B._sign_statement(stmt, priv)})
    cases.append(("a URL run with a page from another host",
                  json.dumps(signed_as(paged("www.example.com", "evil.test"),
                                       "www.example.com"), ensure_ascii=False),
                  key["public_hex"], MALFORMED, False))
    # PR1-2: a page of a URL run with its record taken away and its name
    # changed to another site, re-signed for the bound values.
    forged = paged("www.example.com", "www.example.com")
    forged["pages"] = forged["pages"] + [{"path": "https://bank.example/",
                                          "fetch": None}]
    forged["fetch"] = dict(forged["fetch"], pages=2)
    cases.append(("a URL run with a page that has no capture record",
                  json.dumps(signed_as(forged, "www.example.com"),
                             ensure_ascii=False),
                  key["public_hex"], MALFORMED, False))
    renamed = paged("www.example.com", "www.example.com")
    renamed["pages"][0]["path"] = "https://bank.example/"
    cases.append(("a URL run page named by another URL than its own",
                  json.dumps(signed_as(renamed, "www.example.com"),
                             ensure_ascii=False),
                  key["public_hex"], MALFORMED, False))
    cases.append(("a rendered build served from this machine",
                  json.dumps(signed(paged(None, "127.0.0.1:8123")),
                             ensure_ascii=False),
                  key["public_hex"], VALID, False))
    cases.append(("a file run whose page claims a public site",
                  json.dumps(signed_as(paged(None, "www.example.com"), None),
                             ensure_ascii=False),
                  key["public_hex"], MALFORMED, False))
    # L96: a file's name that only looks like a site's is no name a run
    # records (a run writes "./" before a first part holding a colon or a
    # character outside ASCII); written so, it verifies.
    for label, path, verdict in (
            ("a file run page named U+3164 and https://",
             "\u3164https://bank.example/", MALFORMED),
            ("a file run page named with a full-width colon",
             "https\uff1a//bank.example/", MALFORMED),
            ("a file run page named with a Cyrillic letter",
             "\u04bbttps://bank.example/", MALFORMED),
            ("a file run page so named, after ./",
             "./\u04bbttps:/bank.example/a.html", VALID)):
        lookalike = dict(base, fetch=None,
                         pages=[{"path": path, "fetch": None}])
        # Signed for its own values where they can be read, else as a
        # forger would sign it.
        cases.append((label, json.dumps(
            signed(lookalike) if verdict == VALID else
            signed_as(lookalike, None), ensure_ascii=False),
            key["public_hex"], verdict, False))
    braille = dict(base, fetch=None, inputs=[
        {"path": "\u2800https://bank.example/", "sha256": "0" * 64,
         "bytes": 1}])
    cases.append(("a file input named U+2800 and https://",
                  json.dumps(signed_as(braille, None), ensure_ascii=False),
                  key["public_hex"], MALFORMED, False))
    unbound = dict(fetched("staging.example.com"))
    stmt = B.build_statement(B.bundle_bound_values(unbound), key["key_id"],
                             "x", B.ATTESTED_SUBMISSION,
                             B.bundle_digest(unbound), at)
    del stmt["host"]                         # as statements were before P3-03
    unbound["signature"] = {"alg": "Ed25519", "context": B.STATEMENT_FORMAT,
                            "key_id": key["key_id"], "statement": stmt,
                            "signature_b64": B._sign_statement(stmt, priv)}
    cases.append(("a URL run whose statement binds no host",
                  json.dumps(unbound, ensure_ascii=False),
                  key["public_hex"], INVALID, False))

    # R5B-1, §8: under a public key of small order a "signature" needs no
    # private key (under the identity, R the identity and S zero verifies
    # any statement); such a key, one that is no point of the curve
    # (R5D-15), and an R of small order or an S not reduced, mean nothing.
    identity = "01" + "00" * 31
    for label, weak in (("the identity", identity),
                        ("a point of order 2", "ec" + "ff" * 30 + "7f"),
                        ("y written above the field prime",
                         "ee" + "ff" * 30 + "7f"),
                        ("no point of the curve (y = 2)", "02" + "00" * 31)):
        weak_kid = B.key_id_for(weak)
        anyone = dict(base)
        stmt = B.build_statement(B.bundle_bound_values(anyone), weak_kid, "x",
                                 B.SELF_SIGNED, B.bundle_digest(anyone), at)
        anyone["signature"] = {
            "alg": "Ed25519", "context": B.STATEMENT_FORMAT,
            "key_id": weak_kid, "statement": stmt,
            "signature_b64": base64.b64encode(
                bytes.fromhex(identity) + bytes(32)).decode()}
        cases.append((f"signed under a public key that is {label}",
                      json.dumps(anyone, ensure_ascii=False), weak,
                      MALFORMED, False))
    no_key = signed(dict(base))
    no_key["signature"] = dict(no_key["signature"], signature_b64=base64.b64encode(
        bytes.fromhex(identity) + bytes(32)).decode())
    cases.append(("R the identity and S zero, under a real key",
                  json.dumps(no_key, ensure_ascii=False), key["public_hex"],
                  INVALID, False))
    unreduced = signed(dict(base))
    raw = base64.b64decode(unreduced["signature"]["signature_b64"])
    s = int.from_bytes(raw[32:], "little") + B._ED_L
    unreduced["signature"] = dict(unreduced["signature"], signature_b64=(
        base64.b64encode(raw[:32] + s.to_bytes(32, "little")).decode()))
    cases.append(("S not reduced modulo the group order",
                  json.dumps(unreduced, ensure_ascii=False), key["public_hex"],
                  INVALID, False))
    # R5D-11, §8: only ASCII space, tab, CR and LF may surround a key; a
    # language's own idea of white space differs from another's.
    good = json.dumps(signed(dict(base)), ensure_ascii=False)
    for label, given, verdict in (
            ("ASCII white space around the key",
             " \t" + key["public_hex"] + "\r\n", VALID),
            ("U+001C after the key", key["public_hex"] + "\x1c", MALFORMED),
            ("U+0085 after the key", key["public_hex"] + "\x85", MALFORMED),
            ("U+00A0 before the key", "\xa0" + key["public_hex"], MALFORMED),
            ("a byte order mark before the key",
             "﻿" + key["public_hex"], MALFORMED)):
        cases.append((label, good, given, verdict, False))
    # R5B-4: the body is closed and of this format.
    cases.append(("a member the format does not define, signed",
                  json.dumps(signed(dict(
                      base, certification="WCAG 2.1 AA conformant")),
                      ensure_ascii=False), key["public_hex"], MALFORMED,
                  False))
    cases.append(("another bundle format, signed",
                  json.dumps(signed(dict(
                      base, bundle_format="bellbriar-evidence/2")),
                      ensure_ascii=False), key["public_hex"], MALFORMED,
                  False))
    cases.append(("a member every bundle has, missing, signed",
                  json.dumps(signed({k: v for k, v in base.items()
                                     if k != "attestation"}),
                             ensure_ascii=False), key["public_hex"],
                  MALFORMED, False))
    cases.append(("a member of the wrong type, signed",
                  json.dumps(signed(dict(base, layers={})),
                             ensure_ascii=False), key["public_hex"],
                  MALFORMED, False))
    cases.append(("its attestation rewritten, signed",
                  json.dumps(signed(dict(
                      base, attestation="Certified WCAG 2.1 AA conformant.")),
                      ensure_ascii=False), key["public_hex"], VALID, False))
    # R5B-3: a statement naming another domain, under no valid signature.
    claimed = signed(dict(base))
    claimed["signature"] = dict(claimed["signature"], statement=dict(
        claimed["signature"]["statement"], domain="acquired-by-evil.example"))
    cases.append(("a statement changed after signing",
                  json.dumps(claimed, ensure_ascii=False), key["public_hex"],
                  INVALID, False))
    # SA-1, §6 step 3: the equation is [S]B = R + [k]A, with k reduced
    # modulo L. The cofactored one RFC 8032 states accepts all three of
    # these: R with a point of order 8 added; a key with one added (no key
    # generation makes such a key; verify takes it as given); and that key
    # with R holding the part that cancels it, which verifies.
    tool = vectors_tool()
    def ctx_message(stmt):
        return (B.SIGNING_CONTEXTS[B.STATEMENT_FORMAT]
                + bytes.fromhex(B.statement_digest(stmt)))
    def want(cofactorless, not_reduced):
        return {"cofactorless": cofactorless,
                "cofactorless_k_not_reduced": not_reduced, "cofactored": True}
    part_in_r = signed(dict(base))
    raw = tool._first(seed.hex(),
                      ctx_message(part_in_r["signature"]["statement"]),
                      want(False, False), part_in_key=False,
                      parts_in_r=range(1, 8))
    part_in_r["signature"] = dict(part_in_r["signature"],
                                  signature_b64=base64.b64encode(raw).decode())
    cases.append(("R with a part of order 8",
                  json.dumps(part_in_r, ensure_ascii=False), key["public_hex"],
                  INVALID, False))
    mixed = tool._sign(seed.hex(), b"", part_in_key=True)[1].hex()
    stmt = B.build_statement(B.bundle_bound_values(base), B.key_id_for(mixed),
                             "x", B.SELF_SIGNED, B.bundle_digest(base), at)
    for label, parts, holds, verdict in (
            ("a key with a part of order 8", range(0, 1), False, INVALID),
            ("a key with a part of order 8, and R with the part that "
             "cancels it", range(1, 8), True, VALID)):
        raw = tool._first(seed.hex(), ctx_message(stmt), want(holds, False),
                          part_in_key=True, parts_in_r=parts)
        cases.append((label, json.dumps(dict(base, signature={
            "alg": "Ed25519", "context": B.STATEMENT_FORMAT,
            "key_id": B.key_id_for(mixed), "statement": stmt,
            "signature_b64": base64.b64encode(raw).decode()}),
            ensure_ascii=False), mixed, verdict, False))
    return cases


def vectors_tool():
    """tools/make_canonicalization_vectors.py, for its RFC 8032 arithmetic."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "make_canonicalization_vectors",
        ROOT / "tools" / "make_canonicalization_vectors.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(B.HAVE_ED25519, "cryptography not installed")
class TestVerificationCases(unittest.TestCase):
    """`bellbriar-evidence verify` on genuine, altered and ambiguous files."""

    def test_each_case_gets_its_verdict(self):
        from bellbriar_harness import evidence_cli
        for name, text, pub, verdict, _ in _verification_cases():
            with self.subTest(case=name), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "bundle.json"
                if isinstance(text, bytes):
                    path.write_bytes(text)
                else:
                    path.write_text(text, encoding="utf-8")
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    code = evidence_cli.main(["verify", str(path),
                                              "--public-key", pub])
                self.assertEqual(code, verdict, out.getvalue())


@unittest.skipUnless(NODE, "node is not installed")
class TestJavaScriptAgreement(unittest.TestCase):
    """§2 says the canonical form is JSON.stringify with sorted keys (RFC
    8785) for everything it admits, and §6 says a verifier can be built in
    any language from the spec. tests/js/canonical_check.mjs is such a
    verifier, sharing no code with this package. It must reproduce every
    vector, refuse every rejected and malformed input, reach the same
    verdict as `bellbriar-evidence verify` on every case above, and
    round-trip thousands of random canonical objects byte for byte."""

    @classmethod
    def setUpClass(cls):
        version = subprocess.run([NODE, "--version"], capture_output=True,
                                 text=True).stdout.strip().lstrip("v")
        if int(version.split(".")[0] or 0) < 22:
            raise unittest.SkipTest(f"node {version} is older than 22 "
                                    "(JSON.parse source text is needed)")
        texts = [B.canonical_bytes(o).decode("utf-8")
                 for o in _random_canonical_objects(seed=20260930, count=3000)]
        cls.cases = _verification_cases()
        payload = {"bundles": [
            {"name": n, "public_hex": k,
             **({"bytes_b64": base64.b64encode(t).decode()}
                if isinstance(t, bytes) else {"text": t})}
            for n, t, k, _, _ in cls.cases], "roundtrip": texts}
        with tempfile.TemporaryDirectory() as tmp:
            cases = Path(tmp) / "cases.json"
            cases.write_text(json.dumps(payload, ensure_ascii=False),
                             encoding="utf-8")
            proc = subprocess.run([NODE, str(JS_CHECK), str(VECTORS), str(cases)],
                                  capture_output=True, text=True, timeout=180)
        if proc.returncode != 0:
            raise AssertionError(f"node failed: {proc.stderr[-2000:]}")
        cls.result = json.loads(proc.stdout)
        cls.expected_roundtrips = len(texts)

    def test_every_vector_canonicalizes_identically(self):
        self.assertEqual(self.result["canonical_mismatches"], [])

    def test_every_rejected_and_malformed_input_is_refused(self):
        self.assertEqual(self.result["rejected_accepted"], [])
        self.assertEqual(self.result["malformed_accepted"], [])
        self.assertEqual(self.result["malformed_bytes_accepted"], [])

    def test_other_spellings_are_accepted(self):
        self.assertEqual(self.result["well_formed_mismatches"], [])

    def test_host_relations_agree(self):
        self.assertEqual(self.result["host_relation_mismatches"], [])
        self.assertEqual(self.result["url_host_mismatches"], [])
        self.assertEqual(self.result["page_record_mismatches"], [])
        self.assertEqual(self.result["domain_spelling_mismatches"], [])

    def test_signature_blocks_agree(self):
        self.assertEqual(self.result["signature_block_mismatches"], [])

    def test_small_order_parts_agree(self):
        self.assertEqual(self.result["small_order_mismatches"], [])

    def test_bundle_and_pack_vectors_verify(self):
        self.assertTrue(self.result["bundle_vector_body"])
        self.assertTrue(self.result["bundle_vector_digest"])
        self.assertEqual(self.result["bundle_vector"], "VALID")
        self.assertEqual(self.result["pack_vector"], "VALID")

    def test_same_verdicts_as_the_python_verifier(self):
        word = {VALID: "VALID", INVALID: "INVALID", MALFORMED: "MALFORMED"}
        for name, _, _, verdict, _ in self.cases:
            with self.subTest(case=name):
                got = self.result["bundles"][name]["strict"]
                self.assertEqual(got.split(":")[0], word[verdict], got)

    def test_the_parsing_rules_are_what_catch_the_ambiguous_files(self):
        """Not vacuous: without §6's parsing rules each of these verifies."""
        for name, _, _, _, fools_naive in self.cases:
            if fools_naive:
                with self.subTest(case=name):
                    self.assertEqual(self.result["bundles"][name]["naive"], "VALID")

    def test_random_canonical_objects_round_trip(self):
        self.assertEqual(self.result["roundtrip_checked"], self.expected_roundtrips)
        self.assertEqual(self.result["roundtrip_mismatches"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
