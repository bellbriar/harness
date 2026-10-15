"""Part R, stage 1: evidence, signing and keys.

D3 (remote signing, packs and the judge leave the command line), N11 with
P5-01 (every signature is self-signed, and verify says what that shows in
its own words), P1-11 (no key on the command line), P4-06 (keygen), P1-08
(the rulebook's digest, and no "T1 clean" on nothing), N13 (one host
table), L20 (what decided a host's class), P5-04 (the versions that decide
verdicts), N10 (a closed signature block: test_canonicalization) and L39
(client routes in recorded URLs).
"""
import contextlib
import hashlib
import io
import ipaddress
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bellbriar_harness import bundle as B                      # noqa: E402
from bellbriar_harness import cli, evidence_cli                # noqa: E402
from bellbriar_harness import engine as E                      # noqa: E402
from bellbriar_harness import fetch as F                       # noqa: E402
from bellbriar_harness.redact import redact_url, secret_values  # noqa: E402

FIXTURES = ROOT / "fixtures"
#: Signing and keygen need the cryptography package (a required
#: dependency; the 3.10 and 3.14 test environments lack it).
NEEDS_CRYPTO = unittest.skipUnless(B.HAVE_ED25519, "needs cryptography")


def _run(argv, env=None):
    """(exit code, stdout, stderr) of bellbriar-eval in this process."""
    out, err = io.StringIO(), io.StringIO()
    old = dict(os.environ)
    if env:
        os.environ.update(env)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = cli.main(argv)
            except SystemExit as exc:
                code = exc.code
    finally:
        os.environ.clear()
        os.environ.update(old)
    return code, out.getvalue(), err.getvalue()


def _keypair(folder: Path) -> tuple[Path, str, str]:
    """(private key file, private hex, public hex), the file mode 600."""
    priv, pub, _ = B.generate_keypair()
    path = folder / "k.key"
    path.write_text(priv + "\n")
    path.chmod(0o600)
    return path, priv, pub


class TestScopeCut(unittest.TestCase):
    """D3: --sign-url, --api-key, --pack, --pack-key and --judge are gone;
    the reference signing service is not in the installed package."""

    def test_the_flags_are_refused(self):
        for flags in (["--judge", "anthropic"], ["--pack", "x"],
                      ["--pack-key", "x"], ["--sign-url", "https://s"],
                      ["--api-key", "k"], ["--judge-model", "m"]):
            with self.subTest(flags=flags):
                code, _, err = _run([str(FIXTURES / "good.html"), *flags])
                self.assertEqual(code, 2)
                self.assertIn("unrecognized arguments", err)

    def test_no_remote_signing_in_the_package(self):
        self.assertFalse(hasattr(B, "remote_sign"))
        import importlib.util
        self.assertIsNone(importlib.util.find_spec(
            "bellbriar_harness.server_reference"))
        self.assertFalse((ROOT / "src" / "bellbriar_harness"
                          / "server_reference.py").exists())

    @NEEDS_CRYPTO
    def test_the_reference_signer_still_works_from_the_repository(self):
        """Kept for L2: its client and server still meet, and what the
        service signs reads as no more than self-signed (N11)."""
        sys.path.insert(0, str(ROOT / "tools"))
        try:
            import reference_signer as R
        finally:
            sys.path.remove(str(ROOT / "tools"))
        import threading
        priv, pub, _ = B.generate_keypair()
        with tempfile.TemporaryDirectory() as tmp:
            keys = Path(tmp) / "keys.json"
            keys.write_text(json.dumps({"api_keys": {"k": {"customer": "c"}}}))
            httpd = R.serve(str(keys), priv, port=0)
            threading.Thread(target=httpd.serve_forever, daemon=True).start()
            try:
                run = E.run_paths([FIXTURES / "good.html"])
                from bellbriar_harness.scoring import score_site
                site = score_site(run["pages"], run["rulebook"])
                bundle = B.build_bundle(run, site, [FIXTURES / "good.html"],
                                        domain="example.com")
                signed = R.remote_sign(
                    bundle, f"http://127.0.0.1:{httpd.server_address[1]}", "k")
            finally:
                httpd.shutdown()
                httpd.server_close()
        ok, reason = B.verify_bundle(signed, pub)
        self.assertTrue(ok, reason)
        self.assertEqual(signed["signature"]["statement"]["attestation_class"],
                         B.ATTESTED_SUBMISSION)
        self.assertIn("nothing issues in this release", reason)
        self.assertIn("no more than a self-signed signature", reason)

    def test_the_judge_layer_says_it_is_not_in_this_release(self):
        note = {layer: n for layer, _s, n in E.LAYERS}["judge"]
        self.assertIn("Not in this release", note)
        self.assertNotIn("bring your own", note)


@NEEDS_CRYPTO
class TestSelfSignedOnly(unittest.TestCase):
    """N11, P5-01, D5: signed text is exactly what the code makes true."""

    def _signed(self, cls=B.SELF_SIGNED, attestation=None):
        run = E.run_paths([FIXTURES / "good.html"])
        from bellbriar_harness.scoring import score_site
        site = score_site(run["pages"], run["rulebook"])
        bundle = B.build_bundle(run, site, [FIXTURES / "good.html"])
        if attestation is not None:
            bundle["attestation"] = attestation
        priv, pub, kid = B.generate_keypair()
        key = B.ed25519.Ed25519PrivateKey.from_private_bytes(
            bytes.fromhex(priv))
        stmt = B.build_statement(B.bundle_bound_values(bundle), kid, "me",
                                 cls, B.bundle_digest(bundle))
        bundle["signature"] = {"alg": "Ed25519", "context": B.STATEMENT_FORMAT,
                               "key_id": kid, "statement": stmt,
                               "signature_b64": B._sign_statement(stmt, key)}
        return bundle, pub

    def test_the_attestation_describes_self_signed_only(self):
        self.assertIn("'self-signed'", B.ATTESTATION)
        self.assertIn("no one else checked anything", B.ATTESTATION)
        self.assertIn("edited before signing", B.ATTESTATION)
        for claim in ("subscription in good standing", "attested-submission",
                      "hosted runner"):
            self.assertNotIn(claim, B.ATTESTATION)

    def test_verify_says_what_self_signed_shows_in_its_own_words(self):
        bundle, pub = self._signed()
        ok, reason = B.verify_bundle(bundle, pub)
        self.assertTrue(ok, reason)
        self.assertIn(B.SELF_SIGNED_MEANING, reason)
        # Its own words, not the bundle's attestation (R1A-15: this used to
        # assert the absence of a string nothing could print).
        self.assertNotIn(bundle["attestation"][:60], reason)

    def test_a_forged_attestation_changes_nothing_verify_says(self):
        forged = ("Certified WCAG 2.1 AA conformant by Bellbriar's "
                  "production signer.")
        bundle, pub = self._signed(attestation=forged)
        ok, reason = B.verify_bundle(bundle, pub)
        self.assertTrue(ok, reason)
        self.assertNotIn("Certified", reason)
        self.assertIn(B.SELF_SIGNED_MEANING, reason)

    def test_a_reserved_or_unknown_class_shows_no_more(self):
        for cls, said in ((B.ATTESTED_SUBMISSION, "nothing issues"),
                          (B.ATTESTED_EXECUTION, "nothing issues"),
                          ("gold-certified", "does not define"),
                          (None, "states no class")):
            with self.subTest(cls=cls):
                bundle, pub = self._signed(cls=cls)
                ok, reason = B.verify_bundle(bundle, pub)
                self.assertTrue(ok, reason)
                self.assertIn(said, reason)
                self.assertIn("no more than a self-signed signature", reason)

    def test_the_cli_signs_self_signed(self):
        with tempfile.TemporaryDirectory() as tmp:
            key, _, pub = _keypair(Path(tmp))
            out = Path(tmp) / "b.json"
            code, stdout, _ = _run([str(FIXTURES / "good.html"), "--bundle",
                                    str(out), "--sign-key", str(key)])
            self.assertEqual(code, 0)
            data = B.read_bundle(out)
            self.assertEqual(data["signature"]["statement"]
                             ["attestation_class"], B.SELF_SIGNED)
            self.assertTrue(B.verify_bundle(data, pub)[0])
            self.assertIsNone(data["pack"])
            self.assertIsNone(data["judged"])

    def test_the_guide_says_a_customer_can_forge(self):
        guide = (ROOT / "docs" / "MEASUREMENT-AND-EVIDENCE-GUIDE.md").read_text()
        start = guide.index('**"Couldn\'t the customer forge a bundle?"**')
        answer = guide[start:start + 400]
        self.assertIn("forge a bundle?\"** Yes.", answer)
        self.assertIn("self-signed", answer)


@NEEDS_CRYPTO
class TestKeysNeverOnTheCommandLine(unittest.TestCase):
    """P1-11."""

    def test_a_key_itself_is_refused_and_not_echoed(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, priv, _ = _keypair(Path(tmp))
            code, out, err = _run([str(FIXTURES / "good.html"), "--bundle",
                                   str(Path(tmp) / "b.json"), "--sign-key",
                                   priv])
            self.assertEqual(code, 2)
            self.assertIn("not the key itself", err)
            self.assertNotIn(priv, err + out)
            self.assertFalse((Path(tmp) / "b.json").exists())

    def test_a_missing_or_malformed_key_file_costs_no_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.key"
            bad.write_text("not a key at all but a secret-ish line\n")
            for arg, said in ((str(Path(tmp) / "nope.key"), "no such file"),
                              (str(bad), "does not hold an Ed25519")):
                with self.subTest(arg=arg):
                    code, out, err = _run([str(FIXTURES / "good.html"),
                                           "--bundle", str(Path(tmp) / "b"),
                                           "--sign-key", arg])
                    self.assertEqual(code, 2)
                    self.assertIn(said, err)
                    self.assertNotIn("secret-ish", err)
                    self.assertNotIn("evaluated", err)   # no run spent

    def test_a_file_that_cannot_be_a_key_is_not_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            big = Path(tmp) / "big.key"
            big.write_bytes(b"0" * 10_000)
            code, _, err = _run([str(FIXTURES / "good.html"), "--bundle",
                                 str(Path(tmp) / "b"), "--sign-key", str(big)])
            self.assertEqual(code, 2)
            self.assertIn("too large to be a key file", err)
            code, _, err = _run([str(FIXTURES / "good.html"), "--bundle",
                                 str(Path(tmp) / "b"), "--sign-key", tmp])
            self.assertEqual(code, 2)
            self.assertIn("not a regular file", err)

    def test_the_key_from_an_environment_variable(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, priv, pub = _keypair(Path(tmp))
            out = Path(tmp) / "b.json"
            code, _, err = _run([str(FIXTURES / "good.html"), "--bundle",
                                 str(out), "--sign-key-env", "MY_KEY"],
                                env={"MY_KEY": priv})
            self.assertEqual(code, 0, err)
            self.assertTrue(B.verify_bundle(B.read_bundle(out), pub)[0])
            code, _, err = _run([str(FIXTURES / "good.html"), "--bundle",
                                 str(out), "--sign-key-env", "UNSET_KEY_VAR"])
            self.assertEqual(code, 2)
            self.assertIn("not set", err)

    def test_both_or_neither_bundle(self):
        code, _, err = _run([str(FIXTURES / "good.html"), "--sign-key", "x"])
        self.assertEqual(code, 2)
        self.assertIn("--bundle", err)

    @unittest.skipUnless(os.name == "posix", "file modes")
    def test_a_key_others_can_read_is_warned_about(self):
        with tempfile.TemporaryDirectory() as tmp:
            key, _, _ = _keypair(Path(tmp))
            key.chmod(0o644)
            code, _, err = _run([str(FIXTURES / "good.html"), "--bundle",
                                 str(Path(tmp) / "b.json"), "--sign-key",
                                 str(key)])
            self.assertEqual(code, 0)
            self.assertIn("readable by other users", err)

    def test_the_example_tool_takes_a_file_only(self):
        tool = ROOT / "tools" / "make_example_bundle.py"
        priv, _, _ = B.generate_keypair()
        for arg, said in ((priv, "not the key itself"),
                          ("/no/such/demo.key", "no such file")):
            with self.subTest(arg=arg[:12]):
                proc = subprocess.run([sys.executable, str(tool),
                                       "--private-key", arg],
                                      capture_output=True, text=True,
                                      timeout=120)
                self.assertNotEqual(proc.returncode, 0)
                self.assertIn(said, proc.stderr + proc.stdout)
                self.assertNotIn("Traceback", proc.stderr)
                # What was given is never repeated (R1A-1, R1A-15).
                self.assertNotIn(arg, proc.stderr + proc.stdout)


@NEEDS_CRYPTO
class TestKeygen(unittest.TestCase):
    """P4-06: a private key readable by its owner only, never written over
    an existing one without --force."""

    def _keygen(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = evidence_cli.main(["keygen", *argv])
        return code, out.getvalue()

    @unittest.skipUnless(os.name == "posix", "file modes")
    def test_mode_600_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            prefix = str(Path(tmp) / "k")
            old = os.umask(0o022)
            try:
                code, _ = self._keygen("--out-prefix", prefix)
            finally:
                os.umask(old)
            self.assertEqual(code, 0)
            key = Path(prefix + ".key")
            self.assertEqual(stat.S_IMODE(key.stat().st_mode), 0o600)
            first = key.read_text()
            code, said = self._keygen("--out-prefix", prefix)
            self.assertEqual(code, 2)
            self.assertIn("refusing", said)
            self.assertEqual(key.read_text(), first)
            key.chmod(0o644)
            code, _ = self._keygen("--out-prefix", prefix, "--force")
            self.assertEqual(code, 0)
            self.assertNotEqual(key.read_text(), first)
            self.assertEqual(stat.S_IMODE(key.stat().st_mode), 0o600)

    @unittest.skipUnless(hasattr(os, "symlink"), "symbolic links")
    def test_never_through_a_symbolic_link(self):
        """Not even one that points nowhere, and not with --force: both
        paths are checked before either file is written."""
        with tempfile.TemporaryDirectory() as tmp:
            prefix = str(Path(tmp) / "k")
            target = Path(tmp) / "elsewhere"
            os.symlink(target, prefix + ".pub")
            for argv in (["--out-prefix", prefix],
                         ["--out-prefix", prefix, "--force"]):
                with self.subTest(argv=argv):
                    code, _ = self._keygen(*argv)
                    self.assertEqual(code, 2)
                    self.assertFalse(target.exists())
                    self.assertFalse(Path(prefix + ".key").exists())

    def test_an_existing_public_key_alone_is_kept_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            prefix = str(Path(tmp) / "k")
            Path(prefix + ".pub").write_text("published\n")
            code, _ = self._keygen("--out-prefix", prefix)
            self.assertEqual(code, 2)
            self.assertFalse(Path(prefix + ".key").exists())


class TestRulebookDigest(unittest.TestCase):
    """P1-08: the rules themselves are recorded and bound, and nothing
    Tier-1 run is never "T1 clean"."""

    def test_the_digest_ignores_formatting(self):
        rb = E.load_rulebook()
        with tempfile.TemporaryDirectory() as tmp:
            again = Path(tmp) / "rb.json"
            again.write_text(json.dumps(rb, indent=7, sort_keys=True)
                             .replace("\n", "\r\n"))
            self.assertEqual(E.rulebook_digest(E.load_rulebook(again)),
                             E.bundled_rulebook_digest())
        changed = json.loads(json.dumps(rb))
        changed["tier_weights"]["1"] = 4
        self.assertNotEqual(E.rulebook_digest(changed),
                            E.bundled_rulebook_digest())

    @NEEDS_CRYPTO
    def test_reports_and_bundles_record_it_and_statements_bind_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            key, priv, pub = _keypair(Path(tmp))
            report, out = Path(tmp) / "r.json", Path(tmp) / "b.json"
            code, stdout, _ = _run([str(FIXTURES / "good.html"), "--json",
                                    str(report), "--bundle", str(out),
                                    "--sign-key", str(key)])
            self.assertEqual(code, 0)
            digest = E.bundled_rulebook_digest()
            data = json.loads(report.read_text())
            self.assertEqual(data["rulebook_sha256"], digest)
            self.assertTrue(data["rulebook_bundled"])
            self.assertIn(f"sha256 {digest[:16]}", stdout)
            bundle = B.read_bundle(out)
            self.assertEqual(bundle["rulebook_sha256"], digest)
            self.assertEqual(bundle["signature"]["statement"]
                             ["rulebook_sha256"], digest)
            self.assertIn("rulebook_sha256", B.BOUND_FIELDS)
            ok, reason = B.verify_bundle(bundle, pub)
            self.assertTrue(ok)
            self.assertIn("the one bellbriar-harness", reason)
            # A signature cannot be kept over another rulebook's claim.
            bundle["rulebook_sha256"] = "0" * 64
            key_obj = B.ed25519.Ed25519PrivateKey.from_private_bytes(
                bytes.fromhex(priv))
            stmt = dict(bundle["signature"]["statement"],
                        bundle_digest_sha256=B.bundle_digest(bundle))
            bundle["signature"] = dict(bundle["signature"], statement=stmt,
                                       signature_b64=B._sign_statement(
                                           stmt, key_obj))
            ok, reason = B.verify_bundle(bundle, pub)
            self.assertFalse(ok)
            self.assertIn("binding mismatch on 'rulebook_sha256'", reason)

    @NEEDS_CRYPTO
    def test_a_rulebook_that_demotes_every_tier_1_rule(self):
        rb = E.load_rulebook()
        for r in rb["rules"]:
            if r.get("tier") == 1:
                r["tier"] = 2
        with tempfile.TemporaryDirectory() as tmp:
            custom = Path(tmp) / "demoted.json"
            custom.write_text(json.dumps(rb))
            key, _, pub = _keypair(Path(tmp))
            out = Path(tmp) / "b.json"
            code, stdout, err = _run([str(FIXTURES / "bad.html"),
                                      "--rulebook", str(custom), "--bundle",
                                      str(out), "--sign-key", str(key)])
            self.assertEqual(code, 2)
            self.assertNotIn("T1 clean", stdout)
            self.assertIn("NO T1 RULE RAN [0/0]", stdout)
            self.assertIn("not the rulebook this harness ships", stdout)
            self.assertIn("executed no Tier-1 rule", err)
            # Exit 2 before any bundle is written (R5B-15).
            self.assertFalse(out.exists())
            self.assertIn("No evidence bundle was written", err)
            # --fail-on never asked for no gate, and gets none; its bundle
            # names the rulebook as not this harness's.
            code, _, _ = _run([str(FIXTURES / "bad.html"), "--rulebook",
                               str(custom), "--fail-on", "never", "--bundle",
                               str(out), "--sign-key", str(key)])
            self.assertEqual(code, 0)
            bundle = B.read_bundle(out)
            self.assertIsNone(bundle["pages"][0]["score"]["tier1_clean"])
            ok, reason = B.verify_bundle(bundle, pub)
            self.assertTrue(ok)
            self.assertIn("NOT the digest of the one bellbriar-harness", reason)

    def test_a_rulebook_no_digest_identifies_is_refused(self):
        rb = E.load_rulebook()
        rb["note"] = float("nan")
        with self.assertRaises(RuntimeError) as cm:
            E.validate_rulebook(rb)
        self.assertIn("digest", str(cm.exception))

    def test_an_older_bundle_without_a_digest_says_so(self):
        said = B._rulebook_said({"rulebook_version": "0.3.0",
                                 "rulebook_sha256": None})
        self.assertIn("rests on the version alone", said)


class TestOneHostTable(unittest.TestCase):
    """N13: the capture's class and verify's note come from one table."""

    def test_every_range_gets_one_class_and_note_everywhere(self):
        earlier = [ipaddress.ip_network(n) for n in
                   B.ADDRESS_TABLE_EXCEPTIONS]
        for cls, note, nets in B.ADDRESS_TABLE:
            for net in nets:
                block = ipaddress.ip_network(net)
                # An address of this block that no earlier row (and no
                # exception) claims: rows are read in order.
                sample = next(a for a in (block[0], block[-1])
                              if not any(a.version == e.version and a in e
                                         for e in earlier))
                host = (str(sample) if sample.version == 4
                        else B._ipv6_text(sample))
                url = (f"http://{host}/" if sample.version == 4
                       else f"http://[{host}]/")
                with self.subTest(net=net):
                    self.assertEqual(F.address_record(url), (cls, "address"))
                    self.assertEqual(B.host_note(host), note)
            earlier += [ipaddress.ip_network(n) for n in nets]

    def test_globally_reachable_addresses_inside_the_blocks_are_public(self):
        """R1B-9: IANA marks these globally reachable, inside blocks that
        are not (192.0.0.0/24, 2001::/23)."""
        spec = re.sub(r"\s+", " ", (ROOT / "docs" / "CANONICALIZATION.md")
                      .read_text())
        for net in B.ADDRESS_TABLE_EXCEPTIONS:
            block = ipaddress.ip_network(net)
            for a in {block[0], block[-1]}:
                host = str(a) if a.version == 4 else B._ipv6_text(a)
                url = (f"http://{host}/" if a.version == 4
                       else f"http://[{host}]/")
                with self.subTest(address=host):
                    self.assertIsNone(B.host_note(host))
                    self.assertEqual(F.address_record(url),
                                     ("public", "address"))
            self.assertIn(f"`{net}`", spec)

    def test_only_the_unspecified_address_is_loopback(self):
        """R1B-9: 0.0.0.0 connects to this machine; the rest of 0.0.0.0/8
        is "this network", which no connection reaches."""
        self.assertEqual(B.host_kind("0.0.0.0")[0], "loopback")
        self.assertEqual(B.host_kind("0.1.2.3"),
                         ("private", 'a "this network" address'))
        self.assertEqual(B.host_note("192.0.0.8"), "a dummy address")
        self.assertEqual(B.host_note("2001:2::1"), "a benchmarking address")

    def test_zero_address_and_shared_space_are_named_by_verify(self):
        self.assertEqual(B.host_note("0.0.0.0"),
                         "an unspecified address, which connects to this "
                         "machine")
        self.assertIn("carrier-grade NAT", B.host_note("100.64.1.2"))
        self.assertIsNone(B.host_note("93.184.215.14"))
        self.assertEqual(B.host_note("::ffff:10.0.0.1"), "a private address")
        self.assertEqual(B.host_note("64:ff9b::a00:1"), "a private address")

    def test_the_spec_lists_the_table(self):
        spec = (ROOT / "docs" / "CANONICALIZATION.md").read_text()
        for cls, note, nets in B.ADDRESS_TABLE:
            with self.subTest(note=note):
                row = (" | " + ", ".join(f"`{n}`" for n in nets)
                       + f" | {cls} | {note} |")
                self.assertIn(row, spec)


class TestAddressBasis(unittest.TestCase):
    """L20: a capture record says what decided its address class."""

    def test_cases(self):
        for url, peer, want in (
                ("http://localhost:8000/", None, ("loopback", "name")),
                ("http://127.0.0.1/", None, ("loopback", "address")),
                ("http://site.example/", None, ("public", "name")),
                ("http://site.example/", "10.0.0.7", ("private", "address")),
                ("http://site.example/", "93.184.215.14",
                 ("public", "address")),
                ("http://127.1/", None, ("loopback", "address"))):
            with self.subTest(url=url, peer=peer):
                self.assertEqual(F.address_record(url, peer), want)

    def test_the_record_carries_it(self):
        fr = F.FetchResult(url="http://site.example/",
                           final_url="http://site.example/", mode="server",
                           html="<p>x</p>")
        self.assertEqual(fr.fetch_block()["address_basis"], "name")


class TestRecordedVersions(unittest.TestCase):
    """P5-04: the versions that decide verdicts travel with them."""

    def test_a_file_run_records_python_and_the_parsers(self):
        from importlib.metadata import version
        import platform
        from importlib.metadata import PackageNotFoundError
        tool = E.run_paths([FIXTURES / "good.html"])["tool"]
        self.assertEqual(tool["python"], platform.python_version())
        for lib in ("justhtml", "beautifulsoup4", "soupsieve"):
            try:
                want = version(lib)
            except PackageNotFoundError:     # copied in without metadata
                want = None
            self.assertEqual(tool["libraries"][lib], want)
        self.assertIn("expat", tool["libraries"])
        self.assertNotIn("playwright", tool["libraries"])

    def test_a_browser_run_records_playwright_and_axe_core(self):
        from bellbriar_harness.axe import AXE_VERSION
        libs = E.tool_record(browser=True)["libraries"]
        self.assertEqual(libs["axe-core"], AXE_VERSION)
        self.assertIn("playwright", libs)


class TestClientRoutes(unittest.TestCase):
    """L39: a client route keeps its path; a token cannot hide there."""

    def test_routes_are_kept(self):
        for frag in ("/about", "!/about/team", "/", "/caf%C3%A9"):
            with self.subTest(frag=frag):
                url = f"https://app.example/#{frag}"
                self.assertEqual(redact_url(url), (url, frozenset()))

    def test_a_route_a_browser_would_encode_is_redacted(self):
        """A recorded URL stays printable ASCII, so a verifier can read its
        host (bundle.url_host): a route with a space or a non-ASCII
        character is redacted, as a browser would have encoded it."""
        for frag in ("/a b", "/caf" + chr(0xE9), "/x" + chr(0x7F)):
            with self.subTest(frag=frag):
                got, _ = redact_url(f"https://app.example/#{frag}")
                self.assertEqual(got, "https://app.example/#REDACTED")
                self.assertEqual(B.url_host(got), "app.example")

    def test_a_route_query_is_redacted(self):
        got, removed = redact_url("https://app.example/#/search?q=shoes&p=2",
                                  keep=("p",))
        self.assertEqual(got, "https://app.example/#/search?q=REDACTED&p=2")
        self.assertEqual(removed, frozenset({"fragment"}))

    def test_tokens_cannot_hide_in_a_route(self):
        token = "eyJhbGciOiJIUzI1NiJ9.e30.c2lnbmF0dXJl"
        for frag in (f"/access_token={token}&token_type=Bearer",
                     f"/callback#access_token={token}",
                     f"/%61ccess_token%3D{token}",
                     f"/cb;token={token}",
                     f"access_token={token}",
                     f"/cb?code={token}"):
            with self.subTest(frag=frag[:24]):
                url = f"https://app.example/#{frag}"
                got, removed = redact_url(url)
                self.assertNotIn(token, got)
                self.assertIn("fragment", removed)
                # Messages that quote the URL are scrubbed of it too (the
                # escaped spelling is scrubbed as the whole value).
                values = secret_values(url)
                self.assertTrue(any(token in v for v in values), values)


if __name__ == "__main__":
    unittest.main(verbosity=2)
