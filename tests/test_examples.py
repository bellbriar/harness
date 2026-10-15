"""The committed examples must verify with the committed public key.

This suite exists because examples/evidence/signed-bundle-example.json went
stale silently: it carried a legacy bare-digest signature that the current
verifier rejects by design, so the repo's one worked example failed the
repo's own instructions. Nothing in the previous 58 tests touched it.

An outside reader running `bellbriar-evidence verify` on a published example
is the moment the whole evidence story is either credible or not. Treat a
failure here as a release blocker, not a fixture chore: regenerate with
`python tools/make_example_bundle.py --private-key <demo key>`, the key
being kept outside the repository (see that script).
"""
import json
import os
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bellbriar_harness import __version__                      # noqa: E402
from bellbriar_harness import bundle as B                      # noqa: E402

EXAMPLES = ROOT / "examples" / "evidence"
PUB = EXAMPLES / "reference-public-key.hex"


def example_bundles():
    return sorted(p for p in EXAMPLES.glob("*.json"))


#: Bundle fields the harness writes that the signed example predates. The
#: example was re-signed for 1.0 on Oct 14, 2026 (L34), so none is: a field
#: a later change adds goes here until the example is re-signed again.
PENDING_FIELDS: set = set()

#: Bundle fields the signed example has that the harness no longer writes
#: (none since the re-signing, L34).
PENDING_GONE: set = set()

#: Statement fields the signed example's statement lacks: none since its
#: re-signing for 1.0.0rc1, which added `pack_sha256` (SA-7).
PENDING_STATEMENT_FIELDS: set = set()

#: Values the signed example carries from before a change it predates, by
#: the key the tests below name ("rulebook_version", "tool.version",
#: "layer:<name>", "attestation", "attestation_class"): none since the
#: re-signing (L34).
PENDING_VALUES: dict = {}


#: What blocks a release besides the example (PREPUBLISH.md): each is
#: fixed, with its tests, and then removed from here. None since item 18
#: (L111) was fixed in Part S.
RELEASE_BLOCKERS = ()


def unpinned_base_images(dockerfile: str) -> list:
    """The images a Dockerfile's FROM lines name without a digest, or
    ["(no FROM line)"] (SB-5): a tag can be moved to other bytes, so a
    final release names its base image by `@sha256:`."""
    images = []
    for line in re.findall(r"(?im)^[ \t]*FROM[ \t]+(.+)$", dockerfile):
        words = [w for w in line.split() if not w.startswith("--")]
        images.append(words[0] if words else "")
    if not images:
        return ["(no FROM line)"]
    return [i for i in images if not re.search(r"@sha256:[0-9a-f]{64}\Z", i)]


def _pending() -> bool:
    """Whether the example still predates anything (the PENDING lists)."""
    return bool(PENDING_FIELDS or PENDING_GONE or PENDING_STATEMENT_FIELDS
                or PENDING_VALUES)


def _current_or_pending(test, got, current, key, what):
    """`got` must be the current value, or the one PENDING_VALUES holds for
    `key` until the example is re-signed; once it is current, the pending
    entry must go."""
    pending = PENDING_VALUES.get(key)
    if pending is not None:
        test.assertNotEqual(got, current, f"the example has the current {what} "
                            f"now: remove {key!r} from PENDING_VALUES")
        test.assertEqual(got, pending, f"stale {what}: regenerate with "
                         "tools/make_example_bundle.py")
    else:
        test.assertEqual(got, current, f"stale {what}: regenerate with "
                         "tools/make_example_bundle.py")


@unittest.skipUnless(B.HAVE_ED25519, "cryptography not installed")
class TestPublishedExamples(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pub = PUB.read_text().strip()
        # read_bundle, as `bellbriar-evidence verify` reads a file: a stock
        # parser would accept a duplicated key the verifier refuses.
        cls.bundles = {p.name: B.read_bundle(p) for p in example_bundles()}
        if not cls.bundles:
            raise unittest.SkipTest("no example bundles committed")

    def test_public_key_is_well_formed(self):
        self.assertEqual(len(self.pub), 64, "public key must be 64 hex chars")
        bytes.fromhex(self.pub)

    def test_every_example_verifies(self):
        for name, data in self.bundles.items():
            with self.subTest(example=name):
                ok, reason = B.verify_bundle(data, self.pub)
                self.assertTrue(ok, f"{name} does not verify: {reason}")

    def test_every_example_uses_the_statement_form(self):
        """Guards the specific way the old example rotted."""
        for name, data in self.bundles.items():
            with self.subTest(example=name):
                sig = data.get("signature") or {}
                self.assertIn("statement", sig,
                              f"{name} carries a legacy bare-digest signature")
                self.assertEqual(sig["statement"]["statement_format"],
                                 B.STATEMENT_FORMAT)

    def test_attestation_text_is_current(self):
        """The attestation travels inside the signed content, so a stale
        example publishes stale claims under a valid signature."""
        for name, data in self.bundles.items():
            with self.subTest(example=name):
                _current_or_pending(self, data.get("attestation"),
                                    B.ATTESTATION, "attestation",
                                    "attestation paragraph")

    def test_the_example_is_self_signed(self):
        """D5: every signature this release makes is self-signed. The worked
        example is too once re-signed (L34, PREPUBLISH item 13); until then
        it carries the class it was signed with, which verify must read as
        no more than self-signed (R1B-3)."""
        for name, data in self.bundles.items():
            with self.subTest(example=name):
                _current_or_pending(
                    self, data["signature"]["statement"]["attestation_class"],
                    B.SELF_SIGNED, "attestation_class", "attestation class")
                ok, reason = B.verify_bundle(data, self.pub)
                self.assertTrue(ok, reason)
                if "attestation_class" in PENDING_VALUES:
                    self.assertIn("It shows no more than a self-signed "
                                  "signature", reason)
                else:
                    self.assertIn("signature valid (self-signed: ", reason)

    def test_verify_names_the_rulebook_the_harness_ships(self):
        """R1A-6: the example's rulebook digest is the shipped rulebook's,
        and verify says so; a rulebook edit that keeps the version would
        otherwise leave the example naming a custom rulebook."""
        for name, data in self.bundles.items():
            with self.subTest(example=name):
                ok, reason = B.verify_bundle(data, self.pub)
                self.assertTrue(ok, reason)
                if "$.rulebook_sha256" in PENDING_FIELDS:
                    self.assertNotIn("rulebook_sha256", data)
                    self.assertIn("no rulebook digest", reason)
                else:
                    self.assertEqual(data["rulebook_sha256"],
                                     B.bundled_rulebook_digest())
                    self.assertIn("the digest of the one bellbriar-harness "
                                  f"{__version__} ships", reason)

    def test_inputs_are_the_committed_fixtures(self):
        """R1A-6: each input the example records is a file of this
        repository, with the bytes and hash recorded."""
        import hashlib
        for name, data in self.bundles.items():
            for entry in data["inputs"]:
                with self.subTest(example=name, path=entry["path"]):
                    path = ROOT / entry["path"]
                    self.assertTrue(path.is_file(), entry["path"])
                    raw = path.read_bytes()
                    self.assertEqual(entry["sha256"],
                                     hashlib.sha256(raw).hexdigest(),
                                     "the fixture changed since the example "
                                     "was signed: regenerate it")
                    self.assertEqual(entry["bytes"], len(raw))

    def test_results_match_a_fresh_run(self):
        """R1A-6: the example's body is what the harness writes today for
        the same input, but for its time and the interpreter it ran on: a
        stale finding, score or note would otherwise ship under a valid
        signature. Checked once nothing the body holds is pending (the
        release guard below fails a release while anything is); a field
        only the statement lacks (PENDING_STATEMENT_FIELDS) is not in the
        body."""
        if PENDING_FIELDS or PENDING_GONE or PENDING_VALUES:
            self.skipTest("the example predates this release until it is "
                          "re-signed (PREPUBLISH item 13)")
        import os
        from bellbriar_harness.engine import run_paths
        from bellbriar_harness.scoring import score_site
        here = os.getcwd()
        os.chdir(ROOT)
        try:
            pages = [Path("fixtures") / "good.html"]
            run = run_paths(pages)
            site = score_site(run["pages"], run["rulebook"])
            fresh = B.build_bundle(run, site, pages,
                                   domain="cornerbakery.example")
        finally:
            os.chdir(here)

        def body(bundle):
            return {k: v for k, v in bundle.items()
                    if k not in ("created_at", "signature", "tool")}
        for name, data in self.bundles.items():
            with self.subTest(example=name):
                self.assertEqual(body(data), body(fresh),
                                 "regenerate with tools/make_example_bundle.py")
                self.assertEqual(
                    {k: data["tool"][k] for k in ("name", "version")},
                    {k: fresh["tool"][k] for k in ("name", "version")})

    def test_the_readme_notes_a_pending_example(self):
        """The README quotes what verify prints for the re-signed example,
        with a note while it is not (R1B-3); the note goes with the
        PENDING lists."""
        readme = re.sub(r"\s+", " ", (ROOT / "README.md").read_text(
            encoding="utf-8"))
        note = "Until the example is re-signed for 1.0"
        if "attestation_class" in PENDING_VALUES:
            self.assertIn(note, readme)
        else:
            self.assertNotIn(note, readme)

    @unittest.skipUnless(os.environ.get("BELLBRIAR_RELEASE") == "1",
                         "set BELLBRIAR_RELEASE=1 for a release check")
    def test_nothing_is_pending_for_a_release(self):
        """PREPUBLISH item 13: a release ships a current example, signed
        with the libraries the package installs (R7-2); ROADMAP's "Not in
        1.0" waits on no decision (D6); no release blocker remains (item
        18); and the image's base is pinned by its digest (item 14, SB-5)."""
        self.assertFalse(_pending(), "re-sign the example "
                         "(tools/make_example_bundle.py) and empty the "
                         "PENDING lists")
        roadmap = re.sub(r"\s+", " ", (ROOT / "docs" / "ROADMAP.md")
                         .read_text(encoding="utf-8"))
        self.assertNotIn("Decision pending", roadmap,
                         "ROADMAP's \"Not in 1.0\" still waits on a "
                         "decision: say what 1.0 does")
        # R7-2: signed with the libraries the package installs.
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "make_example_bundle", ROOT / "tools" / "make_example_bundle.py")
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        for name, data in self.bundles.items():
            self.assertEqual(
                [line for line, _ in tool.libraries_outside_ranges(
                    data["tool"]["libraries"])], [],
                f"{name} was signed with libraries the package does not "
                "install: re-sign it where they are in range (item 13)")
        self.assertFalse(RELEASE_BLOCKERS, "release blockers remain "
                         "(PREPUBLISH.md item 18): "
                         + ", ".join(RELEASE_BLOCKERS))
        unpinned = unpinned_base_images((ROOT / "docker" / "Dockerfile")
                                        .read_text(encoding="utf-8"))
        self.assertFalse(unpinned, "docker/Dockerfile names its base image "
                         "by tag only: pin its digest (PREPUBLISH.md item "
                         "14): " + ", ".join(unpinned))

    def test_layer_coverage_text_is_current(self):
        """The coverage banner and layer notes are signed content too. This
        is how 'Bellbriar's calibrated hosted judge' would have shipped
        inside a signed artifact after the claim was retracted elsewhere."""
        from bellbriar_harness.engine import COVERAGE_SENTENCE, LAYERS
        current = {layer: note for layer, _status, note in LAYERS}
        for name, data in self.bundles.items():
            with self.subTest(example=name):
                self.assertEqual(data.get("coverage_note"), COVERAGE_SENTENCE)
                for layer in data.get("layers", []):
                    _current_or_pending(self, layer["note"],
                                        current[layer["layer"]],
                                        f"layer:{layer['layer']}",
                                        f"note on layer {layer['layer']!r}")

    def test_tool_version_is_current(self):
        for name, data in self.bundles.items():
            with self.subTest(example=name):
                _current_or_pending(self, data["tool"]["version"],
                                    __version__, "tool.version",
                                    "harness version")

    def test_statement_bindings_match_the_bundle(self):
        for name, data in self.bundles.items():
            with self.subTest(example=name):
                stmt = data["signature"]["statement"]
                bound = B.bundle_bound_values(data)
                for field in B.BOUND_FIELDS:
                    self.assertEqual(stmt.get(field), bound.get(field), field)

    def test_statement_has_every_current_field(self):
        """The example signed before `host` was bound carried no `host` at
        all, and still verified, because a file run binds null."""
        for name, data in self.bundles.items():
            with self.subTest(example=name):
                got = set(data["signature"]["statement"])
                self.assertEqual(got | PENDING_STATEMENT_FIELDS,
                                 set(B.STATEMENT_FIELDS))
                self.assertFalse(got & PENDING_STATEMENT_FIELDS,
                                 "the example's statement has them now: "
                                 "empty PENDING_STATEMENT_FIELDS")

    def test_rulebook_version_is_current(self):
        """The example claimed rulebook 0.1.0 while the harness shipped
        0.2.0, under a valid signature."""
        from bellbriar_harness.engine import load_rulebook
        current = load_rulebook().get("rulebook_version")
        for name, data in self.bundles.items():
            with self.subTest(example=name):
                _current_or_pending(self, data["rulebook_version"], current,
                                    "rulebook_version", "rulebook version")

    def test_shape_matches_a_bundle_built_today(self):
        """Every field the harness writes today, and no other. The example
        lacked the `evaluable` fields for weeks without any test noticing."""
        import os
        from bellbriar_harness.engine import run_paths
        from bellbriar_harness.scoring import score_site

        def shape(node, path="$"):
            out = set()
            if isinstance(node, dict):
                for k, v in node.items():
                    out.add(f"{path}.{k}")
                    out |= shape(v, f"{path}.{k}")
            elif isinstance(node, list):
                for v in node:
                    out |= shape(v, f"{path}[]")
            return out

        here = os.getcwd()
        os.chdir(ROOT)
        try:
            pages = [Path("fixtures") / "good.html"]
            run = run_paths(pages)
            site = score_site(run["pages"], run["rulebook"])
            fresh = B.build_bundle(run, site, pages,
                                   domain="cornerbakery.example")
        finally:
            os.chdir(here)
        want = shape({k: v for k, v in fresh.items() if k != "signature"})
        for name, data in self.bundles.items():
            with self.subTest(example=name):
                got = shape({k: v for k, v in data.items() if k != "signature"})
                # Fields added since the example was last signed, which the
                # regeneration in Part R (it needs the demo key) brings in.
                # Nothing else may differ, and once the example has them
                # this set must be emptied (the second assertion says so).
                self.assertEqual((got - PENDING_GONE) | PENDING_FIELDS, want,
                                 "regenerate with tools/make_example_bundle.py")
                self.assertFalse(got & PENDING_FIELDS, "the example has "
                                 "them now: empty PENDING_FIELDS")
                self.assertEqual(got & PENDING_GONE, PENDING_GONE,
                                 "the example lost them: empty PENDING_GONE")

    def test_the_example_pins_no_pack(self):
        """Packs are not in 1.0 (D3, L3): the example pins none. Until the
        re-signing (L34) it still names the committed sample pack, and
        that must be the pack the repository has."""
        from bellbriar_harness.pack import pack_reference
        ref = pack_reference(ROOT / "examples" / "pack-sample")
        for name, data in self.bundles.items():
            with self.subTest(example=name):
                rec = data.get("pack")
                if PENDING_GONE:
                    self.assertEqual(
                        (rec.get("name"), rec.get("version"),
                         rec.get("manifest_sha256")),
                        (ref["name"], ref["version"], ref["manifest_sha256"]))
                else:
                    self.assertIsNone(rec)

    def test_the_readme_quotes_what_verify_says(self):
        """PREPUBLISH item 13: README's "Verify something in thirty
        seconds" quotes what `bellbriar-evidence verify` prints for the
        worked example, word for word, so a re-signing that changes it (a
        new version, item 15) changes the quote too."""
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        section = readme.split("## Verify something in thirty seconds", 1)[1]
        block = section.split("```bash", 1)[1].split("```", 1)[0]
        quoted = " ".join(line[1:].strip() for line in block.splitlines()
                          if line.startswith("#"))
        ok, reason = B.verify_bundle(
            self.bundles["signed-bundle-example.json"], self.pub)
        self.assertTrue(ok, reason)
        self.assertEqual(quoted, "VALID: " + reason,
                         "README's 'Verify something in thirty seconds' no "
                         "longer quotes what verify prints: quote it again")

    def test_the_signing_key_is_a_labeled_demonstration_key(self):
        """A key that verify does not name as a demo key must never sign
        the published example: it could pass for a production signer."""
        self.assertIn(B.key_id_for(self.pub), B.DEMO_KEY_IDS)
        for name, data in self.bundles.items():
            with self.subTest(example=name):
                ok, reason = B.verify_bundle(data, self.pub)
                self.assertTrue(ok, reason)
                self.assertIn("DEMONSTRATION KEY", reason)
                self.assertIn("no trust path", reason)

    def test_inspect_flags_a_demo_key_claim(self):
        import contextlib
        import io
        from bellbriar_harness import evidence_cli
        for name in self.bundles:
            with self.subTest(example=name):
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    evidence_cli.main(["inspect", str(EXAMPLES / name)])
                self.assertIn("DEMONSTRATION key", out.getvalue())

    def test_the_published_test_vector_key_is_labeled(self):
        """Its private key is printed in the spec (§8): anyone can sign the
        example body with it and get a VALID that must say so."""
        vectors = json.loads((ROOT / "docs" / "canonicalization-vectors.json")
                             .read_text(encoding="utf-8"))
        key = vectors["vector_key"]
        self.assertIn(key["key_id"], B.PUBLISHED_TEST_KEY_IDS)
        data = json.loads(json.dumps(next(iter(self.bundles.values()))))
        data["signature"] = None
        signed = B.sign_bundle_local(data, key["private_hex"])
        ok, reason = B.verify_bundle(signed, key["public_hex"])
        self.assertTrue(ok, reason)
        self.assertIn("PUBLISHED TEST KEY", reason)
        self.assertIn("evidence of nothing", reason)

    def test_inspect_never_echoes_the_unsigned_signature_members(self):
        """signature.alg and friends are outside everything that is signed:
        anyone can rewrite them after signing."""
        import contextlib
        import io
        import tempfile
        from bellbriar_harness import evidence_cli
        data = json.loads(json.dumps(next(iter(self.bundles.values()))))
        data["signature"]["alg"] = "Ed25519 (site certified WCAG 2.1 AA)"
        data["signature"]["certified_by"] = "US DOJ"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "b.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                evidence_cli.main(["inspect", str(path)])
            try:
                ok, _ = B.verify_bundle(B.read_bundle(path), self.pub)
            except B.MalformedBundle:
                ok = "malformed"
        text = out.getvalue()
        self.assertNotIn("certified", text)
        self.assertNotIn("DOJ", text)
        self.assertIn("signature block: alg, 1 member(s)", text)
        self.assertIn("malformed, so verify refuses this bundle", text)
        self.assertEqual(ok, "malformed", "the signature block is closed "
                         "(§3, §5, N10)")

    def test_the_example_tool_refuses_a_key_inside_the_repository(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "make_example_bundle", ROOT / "tools" / "make_example_bundle.py")
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        with self.assertRaises(SystemExit) as cm:
            tool.read_key(str(ROOT / "README.md"))     # never read as a key
        self.assertIn("inside the repository", str(cm.exception))
        with self.assertRaises(SystemExit):
            tool.mint_key(str(ROOT / "examples" / "evidence" / "x.key"))
        self.assertFalse((ROOT / "examples" / "evidence" / "x.key").exists())

    def test_any_other_key_is_not_labeled(self):
        priv, pub, kid = B.generate_keypair()
        self.assertNotIn(kid, B.DEMO_KEY_IDS)
        data = json.loads(json.dumps(next(iter(self.bundles.values()))))
        data["signature"] = None
        signed = B.sign_bundle_local(data, priv)
        ok, reason = B.verify_bundle(signed, pub)
        self.assertTrue(ok, reason)
        self.assertNotIn("DEMONSTRATION", reason)

    def test_the_demo_private_key_is_nowhere_in_the_repository(self):
        """Its private half is kept outside the repository: anyone holding
        it could sign bundles that verify against the published demo key.
        Every 64-hex token in every text file is tried as a private key."""
        import re
        hex64 = re.compile(r"(?<![0-9a-fA-F])[0-9a-fA-F]{64}(?![0-9a-fA-F])")
        skip = {".git", "__pycache__", "node_modules"}
        for path in ROOT.rglob("*"):
            if not path.is_file() or skip & set(path.relative_to(ROOT).parts):
                continue
            if path.stat().st_size > 2_000_000:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for token in set(hex64.findall(text)):
                key = B.ed25519.Ed25519PrivateKey.from_private_bytes(
                    bytes.fromhex(token))
                self.assertNotEqual(
                    key.public_key().public_bytes_raw().hex(), self.pub,
                    f"{path.relative_to(ROOT)} holds the demo private key")

    def test_no_bundle_float_serializes_with_an_exponent(self):
        """Cross-language digest safety.

        Digests are taken over canonical JSON, so any float whose shortest
        representation differs between Python and JavaScript yields a
        different digest and a spurious INVALID from a non-Python verifier.
        Python switches to exponent notation below 1e-4, JavaScript below
        1e-6. Every float we emit is rounded to 4 decimal places, which keeps
        both sides in plain decimal — this test pins that invariant so a
        future unrounded value cannot quietly break third-party verification.
        """
        def walk(node, path="$"):
            if isinstance(node, float):
                yield path, node
            elif isinstance(node, dict):
                for k, v in node.items():
                    yield from walk(v, f"{path}.{k}")
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    yield from walk(v, f"{path}[{i}]")

        for name, data in self.bundles.items():
            for path, value in walk(data):
                with self.subTest(example=name, field=path):
                    text = json.dumps(value)
                    self.assertNotIn("e", text.lower(),
                                     f"{path}={text} serializes with an "
                                     "exponent; round it to 4 dp")
                    self.assertEqual(value, round(value, 4),
                                     f"{path} is not rounded to 4 dp")


class TestDocsMatchTheCode(unittest.TestCase):
    """Version strings in prose go stale silently.

    The 0.3.0 -> 0.4.0 bump left "Version 0.3.0 executes..." in the README
    and four more in the guide, all describing the shipped build. A reader
    checking whether a document is current looks at exactly these.
    Historical references ("pre-0.3.0 signatures", "normative at 0.3.0 and
    later") are correct as written and are excluded by matching only the
    status phrasings.
    """

    STATUS_PHRASES = [
        ("README.md", "Version {v} executes"),
        ("README.md", "| Layer | {v} status |"),
        ("docs/EVIDENCE.md", "Status at {v}:"),
        ("docs/MEASUREMENT-AND-EVIDENCE-GUIDE.md",
         "describes the harness at version {v}"),
        ("docs/MEASUREMENT-AND-EVIDENCE-GUIDE.md", "At harness {v} the rulebook"),
        ("docs/MEASUREMENT-AND-EVIDENCE-GUIDE.md", "at {v}, 17 of 27"),
        ("docs/MEASUREMENT-AND-EVIDENCE-GUIDE.md", "| Capability | Status at {v} |"),
        ("docs/ROADMAP.md", "**[not built]** at harness {v}"),
    ]

    @staticmethod
    def _flat(rel):
        """Prose wraps, so compare on whitespace-normalized text: a claim
        that straddles a line break is still the same claim."""
        import re
        return re.sub(r"\s+", " ", (ROOT / rel).read_text(encoding="utf-8"))

    def test_status_lines_name_the_current_version(self):
        for rel, tmpl in self.STATUS_PHRASES:
            with self.subTest(file=rel, phrase=tmpl):
                text = self._flat(rel)
                self.assertIn(tmpl.format(v=__version__), text,
                              f"{rel} does not state version {__version__} "
                              f"where it describes the shipped build")

    def test_rule_counts_in_the_guide_match_the_rulebook(self):
        import json
        rb = json.loads((ROOT / "src" / "bellbriar_harness" /
                         "rulebook.json").read_text())
        static = sum(1 for r in rb["rules"] if r.get("status") == "implemented"
                     and r.get("layer") == "static-dom")
        rendered = sum(1 for r in rb["rules"] if r.get("status") ==
                       "implemented" and r.get("layer") == "rendered")
        judged = sum(1 for r in rb["rules"] if r.get("status") == "implemented"
                     and r.get("layer") == "judge")
        planned = sum(1 for r in rb["rules"] if r.get("status") == "planned")
        t1 = sum(1 for r in rb["rules"] if r.get("tier") == 1)
        t1x = sum(1 for r in rb["rules"] if r.get("tier") == 1
                  and r.get("status") == "implemented"
                  and r.get("layer") in ("static-dom", "rendered"))
        t1s = sum(1 for r in rb["rules"] if r.get("tier") == 1
                  and r.get("status") == "implemented"
                  and r.get("layer") == "static-dom")
        guide = self._flat("docs/MEASUREMENT-AND-EVIDENCE-GUIDE.md")
        readme = self._flat("README.md")
        self.assertIn(f"the rulebook (version {rb['rulebook_version']}) holds "
                      f"{len(rb['rules'])} rules", guide)
        self.assertIn(f"{static} deterministic rules that run on the markup, "
                      f"{rendered} that run in the browser", guide)
        self.assertIn(f"{judged} judged rules", guide)
        self.assertIn(f"{planned} rules that are specified", guide)
        self.assertIn(f"{t1x} of {t1} Tier-1 rules are deterministic: {t1s} "
                      "run on the markup", guide)
        self.assertIn(f"({t1x} of {t1} today: {t1s} in a file run)", readme)
        self.assertIn(f"{static + rendered} deterministic rules that run today "
                      f"({static} on the markup, {rendered} in the browser)",
                      readme)
        self.assertIn(f"{planned} specified for the browser layers", readme)

    def test_the_guide_counts_the_rules_of_each_basis_that_fails(self):
        """R2 review of the citation fixes (R2E-9): the guide called most
        rules sc; 24 of 60 were."""
        import json
        rules = json.loads((ROOT / "src" / "bellbriar_harness" /
                            "rulebook.json").read_text())["rules"]
        det = [r for r in rules if r.get("status") == "implemented"
               and r.get("layer") in ("static-dom", "rendered")]
        guide = self._flat("docs/MEASUREMENT-AND-EVIDENCE-GUIDE.md")
        for basis in ("sc", "heuristic"):
            n = sum(1 for r in det if r.get("verdict_basis") == basis)
            with self.subTest(basis=basis):
                self.assertIn(f"{n} of the {len(det)} deterministic rules",
                              guide)
        self.assertNotIn("Most rules", guide)

    def test_citation_counts_match_the_rulebook(self):
        """README said every rule "binds" an ACT title and an Understanding
        citation; 19 of 47 carried neither (review finding P5-03)."""
        import json
        rules = json.loads((ROOT / "src" / "bellbriar_harness" /
                            "rulebook.json").read_text())["rules"]
        det = [r for r in rules if r.get("status") == "implemented"
               and r.get("layer") in ("static-dom", "rendered")]
        sc = sum(1 for r in rules if r.get("sc") and r["sc"] != ["process"])
        no_sc = sum(1 for r in rules if not r.get("sc"))
        process = sum(1 for r in rules if r.get("sc") == ["process"])
        act = sum(1 for r in det if r.get("act_rules"))
        und = sum(1 for r in det
                  if "/Understanding/" in (r.get("understanding") or ""))
        others = [r["id"] for r in rules if r not in det
                  and (r.get("act_rules") or r.get("understanding"))]
        self.assertEqual((no_sc, process, others), (2, 2, []),
                         "the README and guide name exactly two rules with "
                         "no criteria, two flow rules, and no citations "
                         "outside the deterministic rules: reword them")
        # Every citation is checked against W3C's sources (P2-14,
        # tests/test_citations.py); the docs give the counts by status.
        cites = [c for r in det for c in r.get("act_rules") or []]
        status = {s: sum(1 for c in cites if c["status"] == s)
                  for s in ("approved", "proposed", "deprecated")}
        readme = self._flat("README.md")
        guide = self._flat("docs/MEASUREMENT-AND-EVIDENCE-GUIDE.md")
        for text in (readme, guide):
            self.assertIn(f"of the {len(cites)} citations, "
                          f"{status['approved']} are approved by W3C's "
                          f"Accessibility Guidelines Working Group, "
                          f"{status['proposed']} proposed and "
                          f"{status['deprecated']} deprecated", text)
            self.assertNotIn("act_verified", text)
        self.assertIn(f"{sc} of the {len(rules)} cite WCAG success criteria",
                      readme)
        self.assertIn(f"{act} cite W3C ACT rules and {und} link a WCAG "
                      "Understanding document", readme)
        self.assertIn(f"Of the {len(det)} deterministic rules, {und} link a "
                      f"W3C Understanding document and {act} cite", guide)
        self.assertNotIn("Every rule binds", readme)


class TestClaimsMatchTheCode(unittest.TestCase):
    """Sentences review finding P5-03 found false, each tied to the code
    that now makes the corrected sentence true."""

    _flat = staticmethod(TestDocsMatchTheCode._flat)

    def test_generic_link_text_is_not_called_a_short_circuit(self):
        from bellbriar_harness.checks_static import (PageContext,
                                                     check_alt_junk,
                                                     check_generic_link_text)
        from bellbriar_harness.judged import (extract_alt_items,
                                              extract_link_items)
        ev = self._flat("docs/EVIDENCE.md")
        self.assertNotIn("short-circuits (`bb-alt-junk`, "
                         "`bb-generic-link-text`)", ev)
        # The judge is not in 1.0 (D3, L4): the page describes it only as
        # such. The judged code it would run stays, and still grades only
        # the links the rule flags (below).
        self.assertIn("adequacy grading by a judge model (`--judge`)", ev)
        self.assertNotIn("Judged results are scored", ev)
        ctx = PageContext.parse(
            '<main><a href="/a">Read more</a><a href="/b">click here</a>'
            '<a href="/c">Pricing</a><img src="x.png" alt="IMG_1234">'
            '<img src="y.png" alt="A blue mug"></main>')
        flagged = {f.snippet for f in check_generic_link_text(ctx).findings}
        judged = {i["href"] for i in extract_link_items(ctx)}
        # The links the rule flags are exactly the ones the judge grades.
        self.assertEqual(len(flagged), 2)
        self.assertEqual(judged, {"/a", "/b"})
        # Junk alt fails here and is never sent to the judge.
        self.assertEqual(len(check_alt_junk(ctx).findings), 1)
        self.assertEqual([i["alt"] for i in extract_alt_items(ctx)],
                         ["A blue mug"])

    def test_sample_pack_claims_no_distribution(self):
        text = (ROOT / "examples" / "pack-sample" / "SKILL.md").read_text(
            encoding="utf-8")
        self.assertNotIn("distributed to subscribers", text)
        self.assertIn("No production pack is distributed yet", text)

    def test_readme_lint_limits_are_still_limits(self):
        """README names handler and class spellings bellbriar-lint does not
        read. When one is supported, this fails: update the README."""
        from bellbriar_harness.lint import lint_text
        readme = self._flat("README.md")
        for spelling, src, path, rule in (
                ("(`addEventListener`)", '<div id="m">x</div><script>'
                 'm.addEventListener("click", go)</script>', "a.html",
                 "bl-div-click"),
                ('(Vue `v-on="handlers"`)', '<template><div v-on="{ click: '
                 'go }">x</div></template>', "C.vue", "bl-div-click"),
                ("classes held in a variable", 'const c = "outline-none";\n'
                 'const B = () => <button type="button" className={c}>x'
                 '</button>;', "C.tsx", "bl-outline-none-class"),
                ("or a CSS module are not", '<button type="button" '
                 'className={styles.plain}>x</button>', "C.tsx",
                 "bl-outline-none-class"),
                # Not clicks on the element, and links with an href.
                ("Alpine's `.outside`, `.window` and `.document`",
                 '<div @click.outside="open = false">x</div>', "a.html",
                 "bl-div-click"),
                ("Angular `[href]`", '<a [href]="url" (click)="track()">x</a>',
                 "a.component.html", "bl-anchor-button"),
                ("`routerLink`", '<a routerLink="/x" (click)="t()">x</a>',
                 "a.component.html", "bl-anchor-button"),
                ("Svelte `{href}`", '<a {href} on:click={t}>x</a>', "C.svelte",
                 "bl-anchor-button")):
            with self.subTest(spelling=spelling):
                self.assertIn(spelling, readme)
                self.assertEqual([f for f in lint_text(src, path)
                                  if f.rule_id == rule], [],
                                 f"{spelling} is linted now; update the README")
        # And the spellings it says it reads, it reads.
        for spelling, src, path, rule in (
                ("`onClick` (JSX)", '<div onClick={go}>x</div>', "C.jsx",
                 "bl-div-click"),
                ("`onclick` (HTML, Svelte 5)", '<div onclick="go()">x</div>',
                 "a.html", "bl-div-click"),
                ("`onclick` (HTML, Svelte 5)", '<div onclick={go}>x</div>',
                 "C.svelte", "bl-div-click"),
                ("Vue `@click`", '<template><div @click="go">x</div>'
                 '</template>', "C.vue", "bl-div-click"),
                ("`v-on:click`", '<template><div v-on:click="go">x</div>'
                 '</template>', "C.vue", "bl-div-click"),
                ("Alpine `x-on:click`", '<div x-on:click="go">x</div>',
                 "a.html", "bl-div-click"),
                ("Svelte 4 `on:click`", '<div on:click={go}>x</div>',
                 "C.svelte", "bl-div-click"),
                ("Angular `(click)`", '<div (click)="go()">x</div>',
                 "a.html", "bl-div-click"),
                ("a class builder (`cn()`", '<button type="button" '
                 'className={cn("outline-none")}>x</button>', "C.tsx",
                 "bl-outline-none-class"),
                ("`clsx()`", '<button type="button" className={clsx('
                 '"outline-none")}>x</button>', "C.tsx",
                 "bl-outline-none-class"),
                ("a template literal", '<button type="button" className={'
                 '`outline-none`}>x</button>', "C.tsx",
                 "bl-outline-none-class"),
                ("Vue `:class`", '<template><button type="button" '
                 ':class="[\'outline-none\']">x</button></template>',
                 "C.vue", "bl-outline-none-class"),
                ("Svelte `class:name`", '<button type="button" '
                 'class:outline-none={flat}>x</button>', "C.svelte",
                 "bl-outline-none-class"),
                ("Angular `[class]`", '<button type="button" [class]="'
                 '\'outline-none\'">x</button>', "a.html",
                 "bl-outline-none-class"),
                ("`[ngClass]`", '<button type="button" [ngClass]="'
                 '{\'outline-none\': flat}">x</button>', "a.html",
                 "bl-outline-none-class"),
                ("`[class.name]`", '<button type="button" '
                 '[class.outline-none]="flat">x</button>', "a.html",
                 "bl-outline-none-class")):
            with self.subTest(spelling=spelling, src=src):
                self.assertIn(spelling, readme)
                self.assertTrue(any(f.rule_id == rule
                                    for f in lint_text(src, path)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
