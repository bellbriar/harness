import json
import sys
import threading
import unittest
import urllib.request
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
# The reference signing service and its client are not part of the
# installed package (D3, L2): they live in tools/.
sys.path.insert(0, str(ROOT / "tools"))
import reference_signer as R                                  # noqa: E402

from bellbriar_harness import bundle as B                     # noqa: E402
from tests.bundle_body import BODY  # noqa: E402
from bellbriar_harness import pack as P                       # noqa: E402
from bellbriar_harness.checks_static import (                 # noqa: E402
    PageContext, check_alt_junk, check_generic_link_text)
from bellbriar_harness.engine import load_rulebook, run_paths  # noqa: E402
from bellbriar_harness.judged import (                        # noqa: E402
    JUDGED, VotingJudge, extract_alt_items, run_judged)
from bellbriar_harness.model import FAIL, NEEDS_REVIEW        # noqa: E402
from bellbriar_harness.scoring import score_site              # noqa: E402

FIXTURES = ROOT / "fixtures"


class ScriptedJudge:
    """Test provider: fixed verdict per rubric, optionally a sequence."""

    def __init__(self, verdicts):
        self.name = "scripted"
        self.model = "scripted-0"
        self.calibrated = False
        self.verdicts = dict(verdicts)
        self.calls = 0

    def judge(self, rubric_id, payload):
        from bellbriar_harness.judge import JudgeResult
        self.calls += 1
        v = self.verdicts.get(rubric_id, "pass")
        if isinstance(v, list):
            v = v[(self.calls - 1) % len(v)]
        return JudgeResult(rubric_id, v, f"scripted {v}", self.model)


class TestCanonical(unittest.TestCase):
    def test_key_order_irrelevant(self):
        a = {"b": 1, "a": [1, 2], "c": {"y": 2, "x": 1}}
        b = {"c": {"x": 1, "y": 2}, "a": [1, 2], "b": 1}
        self.assertEqual(B.canonical_bytes(a), B.canonical_bytes(b))

    def test_digest_changes_on_tamper(self):
        base = {"bundle_format": "x", "site": {"rate": 0.9}, "signature": None}
        d1 = B.bundle_digest(base)
        base["site"]["rate"] = 0.91
        self.assertNotEqual(d1, B.bundle_digest(base))

    def test_signature_field_excluded_from_digest(self):
        base = {"bundle_format": "x", "signature": None}
        d1 = B.bundle_digest(base)
        base["signature"] = {"anything": "here"}
        self.assertEqual(d1, B.bundle_digest(base))


@unittest.skipUnless(B.HAVE_ED25519, "cryptography not installed")
class TestSigning(unittest.TestCase):
    def setUp(self):
        self.priv, self.pub, self.kid = B.generate_keypair()
        self.bundle = {**BODY, "bundle_format": B.BUNDLE_FORMAT, "domain": "example.com",
                       "site": {"rate": 1.0}, "attestation": B.ATTESTATION,
                       "signature": None}

    def test_roundtrip(self):
        signed = B.sign_bundle_local(dict(self.bundle), self.priv)
        ok, reason = B.verify_bundle(signed, self.pub)
        self.assertTrue(ok, reason)
        self.assertEqual(signed["signature"]["key_id"], self.kid)

    def test_tamper_detected(self):
        signed = B.sign_bundle_local(dict(self.bundle), self.priv)
        signed["site"]["rate"] = 0.5
        ok, reason = B.verify_bundle(signed, self.pub)
        self.assertFalse(ok)
        self.assertIn("altered", reason)

    def test_wrong_key_rejected(self):
        signed = B.sign_bundle_local(dict(self.bundle), self.priv)
        _, other_pub, _ = B.generate_keypair()
        ok, reason = B.verify_bundle(signed, other_pub)
        self.assertFalse(ok)
        self.assertIn("key_id", reason)

    def test_unsigned_rejected(self):
        ok, reason = B.verify_bundle(dict(self.bundle), self.pub)
        self.assertFalse(ok)
        self.assertIn("unsigned", reason)


@unittest.skipUnless(B.HAVE_ED25519, "cryptography not installed")
class TestPack(unittest.TestCase):
    def _make_pack(self, tmp, sign_with=None):
        import hashlib
        root = Path(tmp)
        (root / "SKILL.md").write_text("# sample pack\n")
        manifest = {"name": "wcag", "version": "0.0.1",
                    "rulebook_min": "0.1.0",
                    "files": {"SKILL.md": hashlib.sha256(
                        (root / "SKILL.md").read_bytes()).hexdigest()}}
        if sign_with:
            manifest = P.sign_manifest(manifest, sign_with)
        (root / "pack.json").write_text(json.dumps(manifest))
        return root

    def test_reference_ok_and_tamper(self):
        with TemporaryDirectory() as tmp:
            root = self._make_pack(tmp)
            ref = P.pack_reference(root)
            self.assertEqual(ref["name"], "wcag")
            self.assertFalse(ref["signature_verified"])
            (root / "SKILL.md").write_text("altered")
            with self.assertRaises(P.PackError):
                P.pack_reference(root)

    def test_signed_manifest_verifies(self):
        priv, pub, _ = B.generate_keypair()
        with TemporaryDirectory() as tmp:
            root = self._make_pack(tmp, sign_with=priv)
            ref = P.pack_reference(root, public_hex=pub)
            self.assertTrue(ref["signature_verified"])
            _, wrong_pub, _ = B.generate_keypair()
            with self.assertRaises(P.PackError):
                P.pack_reference(root, public_hex=wrong_pub)


class TestShortCircuits(unittest.TestCase):
    def test_alt_junk_fails_filenames(self):
        ctx = PageContext.parse(
            '<img src="a.jpg" alt="IMG_1234.jpg">'
            '<img src="b.jpg" alt="Sliced sourdough loaf">')
        rr = check_alt_junk(ctx)
        self.assertTrue(rr.failed)
        self.assertEqual(len([f for f in rr.findings if f.verdict == FAIL]), 1)

    def test_generic_link_review_only(self):
        ctx = PageContext.parse(
            '<p>Pricing details: <a href="/p">click here</a> and '
            '<a href="/docs">read the pricing docs</a></p>')
        rr = check_generic_link_text(ctx)
        self.assertFalse(rr.failed)  # needs_review never fails
        self.assertEqual(len(rr.findings), 1)
        self.assertEqual(rr.findings[0].verdict, NEEDS_REVIEW)

    def test_extractors_skip_deterministic_territory(self):
        ctx = PageContext.parse(
            '<img src="a.jpg" alt="IMG_1234.jpg">'       # junk → skipped
            '<img src="b.jpg">'                          # missing → skipped
            '<a href="/x"><img src="c.jpg" alt="Cart icon"></a>')
        items = extract_alt_items(ctx)
        self.assertEqual(len(items), 1)
        self.assertTrue(items[0]["functional"])


class TestJudgedRunner(unittest.TestCase):
    def test_fail_and_pass_mapping(self):
        judge = ScriptedJudge({"bb-alt-quality": "fail",
                               "bb-link-purpose": "pass",
                               "bb-headings-labels-quality": "pass"})
        run = run_judged([FIXTURES / "good.html"], judge)
        s = run.summary()
        self.assertFalse(s["calibrated"])
        self.assertIn("UNCALIBRATED", s["disclosure"])
        self.assertGreaterEqual(s["fail_findings"], 1)   # the good alt judged bad
        self.assertLess(s["judged_pass_rate"], 1.0)

    def test_all_pass(self):
        judge = ScriptedJudge({})
        run = run_judged([FIXTURES / "good.html"], judge)
        s = run.summary()
        self.assertEqual(s["fail_findings"], 0)
        self.assertEqual(s["judged_pass_rate"], 1.0)

    def test_voting_majority_and_tie(self):
        from bellbriar_harness.judge import JudgeResult

        class Seq:
            name, model = "seq", "seq-0"

            def __init__(self, seq):
                self.seq = list(seq)

            def judge(self, rid, payload):
                return JudgeResult(rid, self.seq.pop(0), "r", self.model)

        v = VotingJudge(Seq(["fail", "fail", "pass"]), n=3)
        self.assertEqual(v.judge("bb-alt-quality", {}).verdict, "fail")
        v2 = VotingJudge(Seq(["fail", "pass"]), n=2)
        self.assertEqual(v2.judge("bb-alt-quality", {}).verdict,
                         "needs_review")

    def test_rulebook_judged_registry_consistent(self):
        rb = load_rulebook()
        judged_impl = {r["id"] for r in rb["rules"]
                       if r.get("layer") == "judge"
                       and r.get("status") == "implemented"}
        self.assertEqual(judged_impl, set(JUDGED))


@unittest.skipUnless(B.HAVE_ED25519, "cryptography not installed")
class TestReferenceServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from reference_signer import serve
        cls.priv, cls.pub, cls.kid = B.generate_keypair()
        cls.tmp = TemporaryDirectory()
        keys = Path(cls.tmp.name) / "keys.json"
        keys.write_text(json.dumps({"api_keys": {
            "test-key-1": {"customer": "acme",
                           "domains": ["example.com"],
                           "packs": {"wcag": ">=0"}}}}))
        cls.httpd = serve(str(keys), cls.priv, host="127.0.0.1", port=0,
                          usage_log=str(Path(cls.tmp.name) / "usage.jsonl"))
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever,
                                      daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.tmp.cleanup()

    def _bundle(self, domain="example.com"):
        return {**BODY, "bundle_format": B.BUNDLE_FORMAT, "domain": domain,
                "pack": {"name": "wcag", "version": "0.0.1"},
                "site": {"rate": 1.0}, "attestation": B.ATTESTATION,
                "signature": None}

    def test_public_key_endpoint(self):
        with urllib.request.urlopen(f"{self.base}/v1/public-key") as r:
            data = json.loads(r.read())
        self.assertEqual(data["public_hex"], self.pub)
        self.assertEqual(data["key_id"], self.kid)

    def test_remote_sign_and_offline_verify(self):
        signed = R.remote_sign(self._bundle(), self.base, "test-key-1")
        ok, reason = B.verify_bundle(signed, self.pub)
        self.assertTrue(ok, reason)
        stmt = signed["signature"]["statement"]
        self.assertEqual(stmt["signer"], "bellbriar-reference")
        self.assertEqual(stmt["attestation_class"], "attested-submission")
        self.assertEqual(stmt["domain"], "example.com")

    def test_unknown_key_401(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            R.remote_sign(self._bundle(), self.base, "nope")
        self.assertEqual(cm.exception.code, 401)

    def test_wrong_domain_403(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            R.remote_sign(self._bundle(domain="other.com"),
                          self.base, "test-key-1")
        self.assertEqual(cm.exception.code, 403)

    def test_usage_metered(self):
        R.remote_sign(self._bundle(), self.base, "test-key-1")
        log = (Path(self.tmp.name) / "usage.jsonl").read_text()
        self.assertIn('"endpoint": "sign"', log)


@unittest.skipUnless(B.HAVE_ED25519, "cryptography not installed")
class TestEndToEndBundle(unittest.TestCase):
    def test_run_bundle_sign_verify(self):
        run = run_paths([FIXTURES / "good.html"])
        site = score_site(run["pages"], run["rulebook"])
        bundle = B.build_bundle(run, site, [FIXTURES / "good.html"],
                                domain="example.com")
        self.assertEqual(len(bundle["inputs"]), 1)
        self.assertEqual(len(bundle["inputs"][0]["sha256"]), 64)
        priv, pub, _ = B.generate_keypair()
        signed = B.sign_bundle_local(bundle, priv)
        ok, reason = B.verify_bundle(signed, pub)
        self.assertTrue(ok, reason)
        # attestation must survive into the signed artifact verbatim
        self.assertEqual(signed["attestation"], B.ATTESTATION)


if __name__ == "__main__":
    unittest.main(verbosity=2)
