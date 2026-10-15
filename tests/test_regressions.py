"""Adversarial tests for the two shipped blockers, plus the scoring
regression they share.

History: the first two classes were written against a HEAD where they
failed. They pass now and must keep passing. The third class covers the
same bug on the other track — an empty denominator reporting a perfect
score — which the Blocker-1 fix corrected for judged results and left
standing for deterministic ones.
"""
import json, sys, threading, unittest, urllib.request
from pathlib import Path
from tempfile import TemporaryDirectory
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
# The reference signing service and its client are not part of the
# installed package (D3, L2): they live in tools/.
sys.path.insert(0, str(ROOT / "tools"))
import reference_signer as R                                  # noqa: E402
from bellbriar_harness import bundle as B
from tests.bundle_body import BODY  # noqa: E402
from bellbriar_harness.judge import JudgeResult
from bellbriar_harness.judged import run_judged
from bellbriar_harness.judge import JudgeResult as _JR
FIXTURES = ROOT / "fixtures"

class DeadJudge:
    """Every call errors — exactly what AnthropicJudge does with a bad key.

    error=True matters: AnthropicJudge sets it on a missing key, and without
    it this fixture models a judge that *looked and declined*, which is a
    different bucket. The bug being guarded is a transport failure scoring
    as success, so the fixture has to actually be a transport failure.
    """
    name, model, calibrated = "dead", "dead-0", False
    def judge(self, rid, payload):
        return JudgeResult(rid, "needs_review", "judge error: connection refused",
                           self.model, error=True)

class TestJudgedRateExcludesReviews(unittest.TestCase):
    def test_provider_that_grades_nothing_is_not_a_perfect_score(self):
        s = run_judged([FIXTURES / "good.html"], DeadJudge()).summary()
        self.assertGreater(s["provider_errors"], 0)
        self.assertEqual(s["items_decided"], 0)
        self.assertIsNone(s["judged_pass_rate"],
            "judged_pass_rate reported a number when zero items were graded")
        self.assertIn("NO PASS RATE", s["disclosure"])


class TestEmptyDenominatorIsUndefined(unittest.TestCase):
    """The deterministic twin of the judged-track fix.

    METHODOLOGY.md and the measurement guide both promise that inapplicable
    rules leave the denominator and that scores are never padded with free
    passes. A page with nothing applicable therefore has no pass rate — not
    100%. The guide is the document a lawyer reads; the code has to mean it.
    """

    def _page(self, results=()):
        from bellbriar_harness.model import PageResult
        p = PageResult(path="synthetic")
        p.results = list(results)
        return p

    def test_page_with_no_applicable_rules_has_no_rate(self):
        from bellbriar_harness.model import RuleResult
        from bellbriar_harness.scoring import score_page
        rb = {"tier_weights": {"1": 5, "2": 2, "3": 1, "0": 0},
              "rules": [{"id": "bb-x", "tier": 1}]}
        page = self._page([RuleResult(rule_id="bb-x", applicable=False)])
        self.assertIsNone(score_page(page, rb)["weighted_pass_rate"])

    def test_site_with_no_pages_has_no_rate(self):
        from bellbriar_harness.scoring import score_site
        rb = {"tier_weights": {"1": 5}, "rules": []}
        site = score_site([], rb)
        self.assertIsNone(site["site_weighted_pass_rate"])
        self.assertIsNone(site["pct_pages_tier1_clean"])

    def test_real_page_still_scores_normally(self):
        from bellbriar_harness.engine import run_paths
        from bellbriar_harness.scoring import score_site
        run = run_paths([FIXTURES / "good.html"])
        site = score_site(run["pages"], run["rulebook"])
        self.assertEqual(site["site_weighted_pass_rate"], 1.0)

@unittest.skipUnless(B.HAVE_ED25519, "cryptography not installed")
class TestSignatureBindsToBundle(unittest.TestCase):
    """The signer never sees the bundle body, so the client states the
    domain and pack. The signature must therefore bind what was authorized
    to what the bundle claims, or a subscriber can get a signature for one
    domain and attach it to a bundle for another."""

    def setUp(self):
        from reference_signer import serve
        self.priv, self.pub, _ = B.generate_keypair()
        self.tmp = TemporaryDirectory()
        keys = Path(self.tmp.name) / "k.json"
        keys.write_text(json.dumps({"api_keys": {"k1": {
            "customer": "acme", "domains": ["subscribed.com"],
            "packs": {"wcag": ">=1.0.0"}}}}))
        self.httpd = serve(str(keys), self.priv, host="127.0.0.1", port=0)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def tearDown(self):
        self.httpd.shutdown(); self.httpd.server_close(); self.tmp.cleanup()

    def _bundle(self, domain, pack="wcag", version="1.0.0"):
        return {**BODY, "bundle_format": B.BUNDLE_FORMAT, "domain": domain,
                "pack": {"name": pack, "version": version},
                "rulebook_version": "0.1.0", "site": {"rate": "1.0000"},
                "attestation": B.ATTESTATION, "signature": None}

    def _raw_sign(self, digest, **claims):
        """Post to /v1/sign directly — what an attacker does to bypass
        remote_sign()'s honest field forwarding."""
        req = urllib.request.Request(
            f"{self.base}/v1/sign",
            data=json.dumps({"digest_sha256": digest, **claims}).encode(),
            method="POST", headers={"content-type": "application/json",
                                    "authorization": "Bearer k1"})
        return json.loads(urllib.request.urlopen(req).read())

    def test_signer_authz_is_bound_to_bundle_contents(self):
        # Lowercase: a domain in another spelling is malformed before
        # any binding is compared (SA-4).
        bundle = self._bundle("not-subscribed.org", pack="ghost",
                              version="9.9.9")
        r = self._raw_sign(B.bundle_digest(bundle), bundle_format=B.BUNDLE_FORMAT,
                           domain="subscribed.com", pack="wcag",
                           pack_version="1.0.0", rulebook_version="0.1.0")
        bundle["signature"] = {"alg": "Ed25519",
                               "context": r["statement"]["statement_format"],
                               "key_id": r["key_id"],
                               "statement": r["statement"],
                               "signature_b64": r["signature_b64"]}
        ok, why = B.verify_bundle(bundle, self.pub)
        self.assertFalse(ok, "a bundle for an unsubscribed domain verified")
        self.assertIn("binding mismatch", why)

    def test_honest_path_still_verifies(self):
        signed = R.remote_sign(self._bundle("subscribed.com"), self.base, "k1")
        ok, why = B.verify_bundle(signed, self.pub)
        self.assertTrue(ok, why)
        self.assertEqual(signed["signature"]["statement"]["domain"],
                         "subscribed.com")

    def test_remote_sign_refuses_a_mismatched_statement(self):
        """If the signer returns a statement for other values, the client
        refuses to attach it rather than shipping a broken bundle."""
        class Liar(dict):
            pass
        bundle = self._bundle("subscribed.com")
        real = R.remote_sign(dict(bundle), self.base, "k1")
        tampered = dict(real["signature"]["statement"])
        tampered["domain"] = "elsewhere.com"
        bundle["signature"] = {"alg": "Ed25519", "context": tampered["statement_format"],
                               "key_id": tampered["key_id"], "statement": tampered,
                               "signature_b64": real["signature"]["signature_b64"]}
        ok, why = B.verify_bundle(bundle, self.pub)
        self.assertFalse(ok)

    def test_legacy_bare_digest_signature_rejected(self):
        bundle = self._bundle("subscribed.com")
        bundle["signature"] = {"alg": "Ed25519", "key_id": "deadbeefdeadbeef",
                               "digest_sha256": B.bundle_digest(bundle),
                               "signature_b64": "AA==", "signer": "old"}
        # Malformed since the signature block closed (N10, Part R1): it
        # cannot be verified at all, which is not a verdict.
        with self.assertRaises(B.MalformedBundle) as cm:
            B.verify_bundle(bundle, self.pub)
        self.assertIn("bare-digest", str(cm.exception))

    def test_pack_version_constraint_enforced(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            R.remote_sign(self._bundle("subscribed.com", version="0.9.0"),
                          self.base, "k1")
        self.assertEqual(cm.exception.code, 403)

    def test_missing_pack_version_refused_when_constrained(self):
        b = self._bundle("subscribed.com")
        b["pack"] = {"name": "wcag"}
        with self.assertRaises(urllib.error.HTTPError) as cm:
            R.remote_sign(b, self.base, "k1")
        self.assertEqual(cm.exception.code, 403)

    def test_unpinned_pack_refused_when_subscription_scopes_packs(self):
        b = self._bundle("subscribed.com"); b["pack"] = None
        with self.assertRaises(urllib.error.HTTPError) as cm:
            R.remote_sign(b, self.base, "k1")
        self.assertEqual(cm.exception.code, 403)


class TestVersionConstraints(unittest.TestCase):
    def test_satisfies(self):
        from reference_signer import satisfies as sat
        for ver, con, want in [
            ("1.0.0", ">=1.0.0", True),  ("0.9.9", ">=1.0.0", False),
            ("1.5.0", ">=1.0.0,<2.0.0", True),
            ("2.0.0", ">=1.0.0,<2.0.0", False),
            ("1.0.0", "*", True),        (None, "*", True),
            (None, ">=1.0.0", False),    ("v1.2", ">=1.1", True),
            ("1.0.0-rc1", ">=1.0.0", True), ("1.0.0", "1.0.0", True),
            ("1.0.1", "1.0.0", False),   ("0.0.1", ">=0", True),
        ]:
            self.assertEqual(sat(ver, con)[0], want, f"{ver} vs {con}")


class TestProviderErrorAccounting(unittest.TestCase):
    """provider_errors must be distinct from genuine needs_review."""

    class _Judge:
        name, model, calibrated = "mix", "mix-0", False
        def __init__(self, seq): self.seq = list(seq); self.i = -1
        def judge(self, rid, payload):
            self.i += 1
            kind = self.seq[self.i % len(self.seq)]
            if kind == "err":
                return JudgeResult(rid, "needs_review", "judge error: 500",
                                   self.model, error=True)
            if kind == "review":
                return JudgeResult(rid, "needs_review", "cannot tell", self.model)
            return JudgeResult(rid, kind, "scripted", self.model)

    def _summary(self, seq):
        return run_judged([FIXTURES / "good.html"], self._Judge(seq)).summary()

    def test_error_and_review_counted_separately(self):
        s = self._summary(["err", "review"])
        self.assertEqual(s["provider_errors"], 1)
        self.assertEqual(s["needs_review_findings"], 1)
        self.assertEqual(s["items_decided"], 0)
        self.assertIsNone(s["judged_pass_rate"])

    def test_buckets_sum_to_graded(self):
        s = self._summary(["pass", "fail", "err", "review"])
        passed = s["items_decided"] - s["fail_findings"]
        self.assertEqual(passed + s["fail_findings"]
                         + s["needs_review_findings"] + s["provider_errors"],
                         s["items_graded"])

    def test_all_errors_is_not_a_perfect_score(self):
        s = self._summary(["err"])
        self.assertIsNone(s["judged_pass_rate"])
        self.assertIn("NO PASS RATE", s["disclosure"])

    def test_errored_pass_string_is_not_a_pass(self):
        class Liar:
            name, model, calibrated = "liar", "liar-0", False
            def judge(self, rid, payload):
                return JudgeResult(rid, "pass", "but it errored",
                                   self.model, error=True)
        s = run_judged([FIXTURES / "good.html"], Liar()).summary()
        self.assertEqual(s["items_decided"], 0)
        self.assertIsNone(s["judged_pass_rate"])

    def test_voting_ignores_errored_votes(self):
        from bellbriar_harness.judged import VotingJudge
        class Seq:
            name, model = "seq", "seq-0"
            def __init__(self, s): self.s = list(s)
            def judge(self, rid, p):
                k = self.s.pop(0)
                return (JudgeResult(rid, "needs_review", "e", self.model, error=True)
                        if k == "err" else JudgeResult(rid, k, "r", self.model))
        r = VotingJudge(Seq(["err", "fail", "fail"]), n=3).judge("bb-alt-quality", {})
        self.assertEqual(r.verdict, "fail")
        self.assertFalse(r.error)
        r2 = VotingJudge(Seq(["err", "err"]), n=2).judge("bb-alt-quality", {})
        self.assertTrue(r2.error)
