"""Part R, stage 1: fixes from the two independent reviews (R1A-*, R1B-*).

R1A: signing, keys and verification — no key in any message (R1A-1), "T1
clean" only on rules that can fail and applied (R1A-2), keygen --force by
rename (R1A-3), a malformed public key is "could not verify" (R1A-4), the
HTML badge says why (R1A-7), unverified claims are labeled (R1A-8),
secrets stay out of the browser (R1A-9), a closed statement (R1A-11),
bounded reasons (R1A-12) and the example tool (R1A-13).

R1B: hosts, versions and routes — the peer of the response that answered
(R1B-1), verify reports a name's recorded class (R1B-2), a snapshot re-run
records the axe-core that decided it (R1B-4), padded tokens and twice-
encoded routes are redacted (R1B-5, R1B-6), the recorded host decides the
class (R1B-8), the host table follows IANA (R1B-9: test_part_r1), the
fetchers' own records (R1B-10), the HTML report's versions (R1B-11) and
no redirect of a route URL to itself (R1B-12).
"""
import base64
import contextlib
import http.server
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bellbriar_harness import bundle as B                      # noqa: E402
from tests.bundle_body import BODY  # noqa: E402
from bellbriar_harness import cli, evidence_cli                # noqa: E402
from bellbriar_harness import engine as E                      # noqa: E402
from bellbriar_harness import fetch as F                       # noqa: E402
from bellbriar_harness.redact import redact_url, secret_values  # noqa: E402
from bellbriar_harness.scoring import score_site               # noqa: E402

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


def _evidence(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = evidence_cli.main(argv)
    return code, out.getvalue(), err.getvalue()


def _letter_key():
    """A key pair whose private hex starts with a letter, so it is also a
    well-formed environment variable name."""
    while True:
        priv, pub, kid = B.generate_keypair()
        if priv[0] in "abcdef":
            return priv, pub, kid


def _key_forms(priv: str, pub: str) -> dict:
    raw = bytes.fromhex(priv)
    return {"secret-key form": priv + pub, "0x": "0x" + priv,
            "base64": base64.b64encode(raw).decode(),
            "base64url, unpadded": base64.urlsafe_b64encode(raw).decode()
            .rstrip("="),
            "a stray character": priv + "x", "one short": priv[:-1]}


def _leaks(priv: str, text: str) -> bool:
    """Whether any 16 characters of the key, in hex or in Base64, appear."""
    raw = bytes.fromhex(priv)
    spellings = (priv, priv.upper(), base64.b64encode(raw).decode(),
                 base64.urlsafe_b64encode(raw).decode())
    return any(s[i:i + 16] in text for s in spellings
               for i in range(0, len(s) - 16))


@NEEDS_CRYPTO
class TestNoKeyInAnyMessage(unittest.TestCase):
    """R1A-1: what --sign-key, --sign-key-env and the tools' --private-key
    are given is never repeated, in whatever form a key was typed."""

    def test_sign_key_given_a_key_in_any_form(self):
        priv, pub, _ = B.generate_keypair()
        with tempfile.TemporaryDirectory() as tmp:
            for form, value in _key_forms(priv, pub).items():
                with self.subTest(form=form):
                    code, out, err = _run([str(FIXTURES / "good.html"),
                                           "--bundle", str(Path(tmp) / "b"),
                                           "--sign-key", value])
                    self.assertEqual(code, 2)
                    self.assertFalse(_leaks(priv, out + err), err)
                    self.assertNotIn(value, out + err)

    def test_sign_key_env_given_the_value_instead_of_the_name(self):
        priv, pub, _ = _letter_key()
        forms = dict(_key_forms(priv, pub), **{"the key itself": priv})
        for form, value in forms.items():
            with self.subTest(form=form):
                code, out, err = _run([str(FIXTURES / "good.html"),
                                       "--bundle", "b.json",
                                       "--sign-key-env", value])
                self.assertEqual(code, 2)
                self.assertFalse(_leaks(priv, out + err), err)
                self.assertNotIn(value, out + err)

    def test_the_value_as_a_name_says_what_to_pass(self):
        priv, _, _ = _letter_key()
        code, _, err = _run([str(FIXTURES / "good.html"), "--bundle",
                             "b.json", "--sign-key-env", priv])
        self.assertEqual(code, 2)
        self.assertIn("NAME of an environment variable", err)
        self.assertIn("treat it as exposed", err)

    def test_an_unset_variable_is_named_only_when_it_is_the_default(self):
        code, _, err = _run([str(FIXTURES / "good.html"), "--bundle",
                             "b.json", "--sign-key-env", "MY_CUSTOM_KEY_VAR"],
                            env={"MY_CUSTOM_KEY_VAR": ""})
        # Set but empty: no key in it, and the name is not repeated.
        self.assertEqual(code, 2)
        self.assertNotIn("MY_CUSTOM_KEY_VAR", err)
        self.assertIn("does not hold an Ed25519 private key", err)
        old = os.environ.pop(cli.SIGN_KEY_ENV, None)
        try:
            code, _, err = _run([str(FIXTURES / "good.html"), "--bundle",
                                 "b.json", "--sign-key-env", cli.SIGN_KEY_ENV])
        finally:
            if old is not None:
                os.environ[cli.SIGN_KEY_ENV] = old
        self.assertEqual(code, 2)
        self.assertIn(f"{cli.SIGN_KEY_ENV} is not set", err)

    def test_a_missing_file_is_not_named(self):
        code, _, err = _run([str(FIXTURES / "good.html"), "--bundle",
                             "b.json", "--sign-key", "/no/such/dir/sign.key"])
        self.assertEqual(code, 2)
        self.assertIn("no such file", err)
        self.assertNotIn("/no/such/dir", err)

    def _tool(self, *argv):
        return subprocess.run([sys.executable, *map(str, argv)],
                              capture_output=True, text=True, timeout=120)

    def test_the_example_tool(self):
        priv, pub, _ = B.generate_keypair()
        tool = ROOT / "tools" / "make_example_bundle.py"
        with tempfile.TemporaryDirectory() as tmp:
            cases = [("--private-key", value) for value in
                     _key_forms(priv, pub).values()]
            cases += [("--private-key", tmp), ("--new-key", priv)]
            if Path("/proc/self/mem").exists():
                cases.append(("--private-key", "/proc/self/mem"))
            for flag, value in cases:
                with self.subTest(flag=flag, value=value[:14]):
                    proc = self._tool(tool, flag, value)
                    said = proc.stdout + proc.stderr
                    self.assertNotEqual(proc.returncode, 0)
                    self.assertNotIn("Traceback", said)
                    self.assertFalse(_leaks(priv, said), said)
            proc = self._tool(tool, "--private-key", tmp)
            self.assertIn("not a regular file", proc.stdout + proc.stderr)

    def test_the_reference_signer(self):
        priv, _, _ = B.generate_keypair()
        with tempfile.TemporaryDirectory() as tmp:
            keys = Path(tmp) / "keys.json"
            keys.write_text(json.dumps({"api_keys": {}}))
            proc = self._tool(ROOT / "tools" / "reference_signer.py",
                              "--keys", keys, "--private-key", priv)
        said = proc.stdout + proc.stderr
        self.assertEqual(proc.returncode, 2, said)
        self.assertNotIn("Traceback", said)
        self.assertFalse(_leaks(priv, said), said)
        self.assertIn("not the key itself", said)


def _rulebook(keep_tier1) -> dict:
    """The shipped rulebook with every Tier-1 rule for which
    keep_tier1(rule) is false moved to Tier 2."""
    rb = E.load_rulebook()
    for r in rb["rules"]:
        if r.get("tier") == 1 and not keep_tier1(r):
            r["tier"] = 2
    return rb


class TestTier1CleanRestsOnRulesThatCanFail(unittest.TestCase):
    """R1A-2: "T1 clean" and the gate count only Tier-1 rules that can
    fail and applied to the page."""

    def _write(self, folder, rb, name):
        path = Path(folder) / name
        path.write_text(json.dumps(rb))
        return path

    @NEEDS_CRYPTO
    def test_only_rules_that_never_fail(self):
        rb = _rulebook(lambda r: r.get("verdict_basis") in E.NEVER_FAIL_BASES)
        kept = [r["id"] for r in rb["rules"] if r.get("tier") == 1]
        self.assertTrue(kept)
        with tempfile.TemporaryDirectory() as tmp:
            custom = self._write(tmp, rb, "never-fail.json")
            report, html = Path(tmp) / "r.json", Path(tmp) / "r.html"
            out = Path(tmp) / "b.json"
            key = Path(tmp) / "k.key"
            key.write_text(B.generate_keypair()[0])
            key.chmod(0o600)
            code, stdout, err = _run([str(FIXTURES / "bad.html"), "--rulebook",
                                      str(custom), "--json", str(report),
                                      "--html", str(html), "--bundle",
                                      str(out), "--sign-key", str(key)])
            self.assertEqual(code, 2, stdout + err)
            self.assertNotIn("T1 clean [", stdout)
            self.assertIn("T1 UNDECIDED", stdout)
            self.assertIn("none of them can fail", stdout)
            self.assertIn("no Tier-1 rule that can fail applied", err)
            data = json.loads(report.read_text())
            self.assertIsNone(data["pages"][0]["score"]["tier1_clean"])
            self.assertEqual(data["pages"][0]["score"]
                             ["tier1_rules_applicable"], 0)
            self.assertIsNone(data["site"]["pct_pages_tier1_clean"])
            self.assertIn("Tier-1 undecided — no Tier-1 rule that can fail "
                          "applied to this page", html.read_text())
            self.assertNotIn("Tier-1 clean (", html.read_text())
            # Exit 2 before any bundle is written: a signed bundle of a run
            # that cannot pass would read as a measurement (R5B-15).
            self.assertFalse(out.exists())
            self.assertIn("No evidence bundle was written", err)
            code, _, _ = _run([str(FIXTURES / "bad.html"), "--rulebook",
                               str(custom), "--fail-on", "never"])
            self.assertEqual(code, 0)

    def test_a_rule_that_does_not_apply(self):
        rb = _rulebook(lambda r: r["id"] == "bb-marquee-blink")
        with tempfile.TemporaryDirectory() as tmp:
            custom = self._write(tmp, rb, "marquee.json")
            code, stdout, err = _run([str(FIXTURES / "good.html"),
                                      "--rulebook", str(custom)])
            self.assertEqual(code, 2, stdout + err)
            self.assertIn("T1 UNDECIDED [1/1]", stdout)
            self.assertNotIn("T1 clean [", stdout)
            page = Path(tmp) / "m.html"
            page.write_text('<!doctype html><html lang="en"><head><title>M'
                            '</title></head><body><main><marquee>news'
                            '</marquee></main></body></html>')
            code, stdout, _ = _run([str(page), "--rulebook", str(custom)])
            self.assertEqual(code, 1, stdout)
            self.assertIn("T1 FAIL", stdout)

    def test_the_shipped_rulebook_still_decides(self):
        code, stdout, _ = _run([str(FIXTURES / "good.html")])
        self.assertEqual(code, 0)
        self.assertIn("T1 clean", stdout)
        run = E.run_paths([FIXTURES / "good.html"])
        page = score_site(run["pages"], run["rulebook"])["pages"][0]
        self.assertTrue(page["tier1_clean"])
        self.assertGreater(page["tier1_rules_applicable"], 0)
        self.assertLessEqual(page["tier1_rules_applicable"],
                             page["tier1_rules_executed"])

    def test_the_html_badge_for_no_tier1_rule(self):
        rb = _rulebook(lambda r: False)
        with tempfile.TemporaryDirectory() as tmp:
            custom = self._write(tmp, rb, "none.json")
            html = Path(tmp) / "r.html"
            _run([str(FIXTURES / "good.html"), "--rulebook", str(custom),
                  "--html", str(html), "--fail-on", "never"])
            text = html.read_text()
            self.assertIn("Tier-1 undecided — no Tier-1 rule ran on this page",
                          text)
            self.assertNotIn("Not evaluated — <", text)


@NEEDS_CRYPTO
@unittest.skipUnless(os.name == "posix", "POSIX file types and modes")
class TestKeygenReplacesByRenaming(unittest.TestCase):
    """R1A-3: --force never rewrites the old file in place, and replaces
    only regular files, both checked before anything is written."""

    def _keygen(self, *argv):
        return _evidence(["keygen", *argv])

    def test_a_fifo_is_refused_without_blocking(self):
        with tempfile.TemporaryDirectory() as tmp:
            prefix = str(Path(tmp) / "f")
            os.mkfifo(prefix + ".key")
            code, out, _ = self._keygen("--out-prefix", prefix, "--force")
            self.assertEqual(code, 2)
            self.assertIn("not a regular file", out)
            self.assertTrue(stat.S_ISFIFO(os.lstat(prefix + ".key").st_mode))
            self.assertFalse(os.path.exists(prefix + ".pub"))

    def test_a_directory_at_the_public_key_leaves_the_old_pair(self):
        with tempfile.TemporaryDirectory() as tmp:
            prefix = str(Path(tmp) / "d")
            Path(prefix + ".key").write_text("old private\n")
            os.mkdir(prefix + ".pub")
            code, out, _ = self._keygen("--out-prefix", prefix, "--force")
            self.assertEqual(code, 2)
            self.assertIn("not a regular file", out)
            self.assertEqual(Path(prefix + ".key").read_text(), "old private\n")
            self.assertEqual(sorted(os.listdir(tmp)), ["d.key", "d.pub"])

    def test_a_descriptor_opened_earlier_keeps_the_old_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            prefix = str(Path(tmp) / "k")
            self.assertEqual(self._keygen("--out-prefix", prefix)[0], 0)
            old = Path(prefix + ".key").read_text()
            os.chmod(prefix + ".key", 0o644)
            with open(prefix + ".key") as early:
                code, _, _ = self._keygen("--out-prefix", prefix, "--force")
                self.assertEqual(code, 0)
                self.assertEqual(early.read(), old)
            new = Path(prefix + ".key").read_text()
            self.assertNotEqual(new, old)
            self.assertEqual(stat.S_IMODE(os.stat(prefix + ".key").st_mode),
                             0o600)
            kind, pub = B.parse_key_text(Path(prefix + ".pub").read_text())
            self.assertEqual(kind, "public")
            kind, seed = B.parse_key_text(new)
            self.assertEqual(kind, "private")
            derived = B.ed25519.Ed25519PrivateKey.from_private_bytes(
                bytes.fromhex(seed)).public_key().public_bytes_raw()
            self.assertEqual(derived.hex(), pub)
            self.assertEqual(sorted(os.listdir(tmp)), ["k.key", "k.pub"])

    def test_inside_a_git_checkout_it_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.mkdir(Path(tmp) / ".git")
            code, _, err = self._keygen("--out-prefix", str(Path(tmp) / "k"))
            self.assertEqual(code, 0)
            self.assertIn("inside a git checkout", err)


@NEEDS_CRYPTO
class TestAMalformedPublicKeyIsNoVerdict(unittest.TestCase):
    """R1A-4: a key that is not one is "could not verify" (2), never
    INVALID (1), and a private key passed as the public one is named."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        priv, cls.pub, _ = B.generate_keypair()
        cls.priv = priv
        run = E.run_paths([FIXTURES / "good.html"])
        site = score_site(run["pages"], run["rulebook"])
        bundle = B.sign_bundle_local(
            B.build_bundle(run, site, [FIXTURES / "good.html"]), priv)
        cls.path = Path(cls.tmp.name) / "b.json"
        cls.path.write_text(json.dumps(bundle))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_shapes(self):
        for key in ("", self.pub[:62], self.pub + "00", "zz" * 32, " "):
            with self.subTest(key=key[:8]):
                code, out, _ = _evidence(["verify", str(self.path),
                                          "--public-key", key])
                self.assertEqual(code, 2, out)
                self.assertIn("CANNOT VERIFY", out)
        code, out, _ = _evidence(["verify", str(self.path), "--public-key",
                                  self.pub.upper()])
        self.assertEqual(code, 0, out)
        with self.assertRaises(ValueError):
            B.verify_bundle(B.read_bundle(self.path), "")

    def test_the_private_key_file_by_mistake(self):
        key = Path(self.tmp.name) / "k.key"
        key.write_text(self.priv + "\n")
        code, out, _ = _evidence(["verify", str(self.path), "--public-key",
                                  str(key)])
        self.assertEqual(code, 2, out)
        self.assertIn("PRIVATE half", out)
        self.assertFalse(_leaks(self.priv, out))


def _self_signed(bundle, cls=B.SELF_SIGNED):
    priv, pub, kid = B.generate_keypair()
    key = B.ed25519.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(priv))
    stmt = B.build_statement(B.bundle_bound_values(bundle), kid, "someone",
                             cls, B.bundle_digest(bundle))
    bundle["signature"] = {"alg": "Ed25519", "context": B.STATEMENT_FORMAT,
                           "key_id": kid, "statement": stmt,
                           "signature_b64": B._sign_statement(stmt, key)}
    return bundle, pub


def _file_bundle():
    run = E.run_paths([FIXTURES / "good.html"])
    site = score_site(run["pages"], run["rulebook"])
    return B.build_bundle(run, site, [FIXTURES / "good.html"])


@NEEDS_CRYPTO
class TestClaimsAreLabeled(unittest.TestCase):
    """R1A-8: a pack, judged results and a reserved class are the bundle
    maker's word, and inspect and verify say so."""

    def test_inspect_and_verify(self):
        bundle = _file_bundle()
        bundle["pack"] = {"name": "wcag", "version": "1.0.0",
                          "manifest_sha256": "0" * 64, "files": 1,
                          "signature_verified": True}
        bundle["judged"] = {"summary": {"provider": "bellbriar-hosted",
                                        "model": "calibrated-judge-v1",
                                        "calibrated": True,
                                        "judged_pass_rate": 1.0},
                            "pages": []}
        bundle, pub = _self_signed(bundle, B.ATTESTED_EXECUTION)
        ok, reason = B.verify_bundle(bundle, pub)
        self.assertTrue(ok, reason)
        self.assertIn("no hosted runner exists", reason)
        self.assertNotIn("no signing service exists", reason)
        self.assertIn("it carries pack 'wcag' and judged results, which "
                      "this release never writes", reason)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "b.json"
            path.write_text(json.dumps(bundle))
            code, out, _ = _evidence(["inspect", str(path)])
        self.assertEqual(code, 0)
        for line in ("pack        wcag@1.0.0", "judged      bellbriar-hosted"):
            shown = next(l for l in out.splitlines() if l.startswith(line))
            self.assertIn("the bundle's own claim", shown)
        self.assertIn("verify reads it as no more than self-signed", out)

    def test_a_submission_names_the_signing_service(self):
        bundle, pub = _self_signed(_file_bundle(), B.ATTESTED_SUBMISSION)
        ok, reason = B.verify_bundle(bundle, pub)
        self.assertTrue(ok)
        self.assertIn("no signing service exists", reason)
        self.assertNotIn("it carries", reason)


class TestSecretsStayOutOfTheBrowser(unittest.TestCase):
    """R1A-9: the render child, and the Chromium under it, inherit no
    secret this process read."""

    def test_the_child_environment(self):
        seen = {}

        class Stop(Exception):
            pass

        def popen(*args, **kw):
            seen.update(kw.get("env") or {})
            raise Stop

        F.WITHHELD_ENV.add("MY_SIGNING_SECRET")
        env = {"BELLBRIAR_SIGN_KEY": "k" * 64,
               "BELLBRIAR_HTTP_PASSWORD": "pw-secret",
               "MY_SIGNING_SECRET": "s" * 64, "KEEP_ME": "yes"}
        with mock.patch.dict(os.environ, env), \
                mock.patch("subprocess.Popen", popen):
            with self.assertRaises(Stop):
                F._fetch_rendered_isolated("http://127.0.0.1:9/", 5.0)
        self.assertEqual(seen.get("KEEP_ME"), "yes")
        for name in env:
            if name != "KEEP_ME":
                self.assertNotIn(name, seen)

    @NEEDS_CRYPTO
    def test_the_cli_withholds_the_variable_it_read(self):
        priv, _, _ = B.generate_keypair()
        with tempfile.TemporaryDirectory() as tmp:
            code, _, err = _run([str(FIXTURES / "good.html"), "--bundle",
                                 str(Path(tmp) / "b.json"), "--sign-key-env",
                                 "CI_SIGNING_KEY_R1A9"],
                                env={"CI_SIGNING_KEY_R1A9": priv})
        self.assertEqual(code, 0, err)
        self.assertIn("CI_SIGNING_KEY_R1A9", F.WITHHELD_ENV)


@NEEDS_CRYPTO
class TestTheStatementIsClosed(unittest.TestCase):
    """R1A-11: a statement member the format does not define is
    malformed; a null signature is an unsigned bundle."""

    def test_an_extra_member(self):
        bundle, pub = _self_signed(_file_bundle())
        bundle["signature"]["statement"]["certified"] = "WCAG 2.1 AA"
        with self.assertRaises(B.MalformedBundle):
            B.verify_bundle(bundle, pub)

    def test_a_null_signature_is_unsigned(self):
        bundle = _file_bundle()
        self.assertIsNone(bundle["signature"])
        _priv, pub, _kid = B.generate_keypair()
        self.assertEqual(B.verify_bundle(bundle, pub),
                         (False, "bundle is unsigned"))


@NEEDS_CRYPTO
class TestBoundedReasons(unittest.TestCase):
    """R1A-12: verify and inspect quote a bundle's values short."""

    def test_a_long_value_on_either_side(self):
        bundle = _file_bundle()
        bundle["rulebook_version"] = "9" * 200_000
        bundle, pub = _self_signed(bundle)
        mutated = json.loads(json.dumps(bundle))
        mutated["signature"]["statement"]["rulebook_version"] = "8" * 200_000
        ok, reason = B.verify_bundle(mutated, pub)
        self.assertFalse(ok)
        self.assertLess(len(reason), 1000)
        mutated["signature"]["statement"]["statement_format"] = "x" * 200_000
        ok, reason = B.verify_bundle(mutated, pub)
        self.assertFalse(ok)
        self.assertLess(len(reason), 1000)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "b.json"
            path.write_text(json.dumps(bundle))
            code, out, _ = _evidence(["inspect", str(path)])
        self.assertEqual(code, 0)
        self.assertLess(max(map(len, out.splitlines())), 1000)


class _Servers:
    """A site on 127.0.0.1 and a forward proxy on 127.0.0.1."""

    def __init__(self, site_handler):
        self.site = http.server.ThreadingHTTPServer(("127.0.0.1", 0),
                                                    site_handler)

        class Proxy(http.server.BaseHTTPRequestHandler):
            seen = []

            def do_GET(self):                         # noqa: N802
                Proxy.seen.append(self.path)
                body = b"<!doctype html><html lang=en><title>P</title><p>p"
                self.send_response(200)
                self.send_header("content-type", "text/html")
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass
        self.proxy_seen = Proxy.seen
        self.proxy = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Proxy)
        for srv in (self.site, self.proxy):
            threading.Thread(target=srv.serve_forever, daemon=True).start()

    def close(self):
        for srv in (self.site, self.proxy):
            srv.shutdown()
            srv.server_close()


def _no_proxy_env() -> dict:
    """Every proxy setting of this environment cleared."""
    return {k: "" for k in os.environ if k.lower().endswith("_proxy")}


def _proxy_env(port: int) -> dict:
    proxy = f"http://127.0.0.1:{port}"
    env = _no_proxy_env()
    env.update({"http_proxy": proxy, "HTTP_PROXY": proxy,
                "no_proxy": "127.0.0.1", "NO_PROXY": "127.0.0.1"})
    return env


class TestTheConnectionThatAnswered(unittest.TestCase):
    """R1B-1, R1B-8, R1B-10: the record's basis is "address" only for the
    connection that served the page, to the recorded host itself."""

    def _handler(self, location=None):
        class Site(http.server.BaseHTTPRequestHandler):
            def do_GET(self):                         # noqa: N802
                if location:
                    self.send_response(302)
                    self.send_header("location", location)
                    self.send_header("content-length", "0")
                    self.end_headers()
                    return
                body = b"<!doctype html><html lang=en><title>S</title><p>s"
                self.send_response(200)
                self.send_header("content-type", "text/html")
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass
        return Site

    def test_a_direct_hop_then_a_proxied_one(self):
        servers = _Servers(self._handler("http://www.public-site.example/"))
        try:
            port = servers.site.server_address[1]
            with mock.patch.dict(os.environ,
                                 _proxy_env(servers.proxy.server_address[1])):
                fr = F.fetch_server(f"http://127.0.0.1:{port}/start")
        finally:
            servers.close()
        self.assertEqual(servers.proxy_seen, ["http://www.public-site.example/"])
        self.assertEqual(fr.host, "www.public-site.example")
        self.assertEqual((fr.address_class, fr.address_basis),
                         ("public", "name"))

    def test_a_direct_fetch_of_an_address(self):
        servers = _Servers(self._handler())
        try:
            port = servers.site.server_address[1]
            with mock.patch.dict(os.environ, _no_proxy_env()):
                fr = F.fetch_server(f"http://127.0.0.1:{port}/")
        finally:
            servers.close()
        self.assertEqual((fr.address_class, fr.address_basis),
                         ("loopback", "address"))

    def test_the_fragment_does_not_change_the_basis(self):
        servers = _Servers(self._handler())
        try:
            port = servers.site.server_address[1]
            with mock.patch.dict(os.environ, _no_proxy_env()):
                got = {frag: (lambda fr: (fr.host, fr.address_class,
                                          fr.address_basis))(
                    F.fetch_server(f"http://localhost:{port}/{frag}"))
                    for frag in ("#/about", "#/café", "#/a b")}
        finally:
            servers.close()
        self.assertEqual(set(got.values()),
                         {("localhost", "loopback", "name")}, got)


@NEEDS_CRYPTO
class TestVerifyReportsANamesRecordedClass(unittest.TestCase):
    """R1B-2: for a name, verify reports what the capture records say it
    resolved to, as their word."""

    def _bundle(self, cls, basis):
        record = {"final_url": "http://intranet.corp/", "host": "intranet.corp",
                  "address_class": cls, "address_basis": basis}
        body = {**BODY, "bundle_format": B.BUNDLE_FORMAT, "domain": None,
                "fetch": {"final_url": "http://intranet.corp/",
                          "host": "intranet.corp", "pages": 1,
                          "list": {"kind": "urls", "max_pages": 1}},
                "pages": [{"path": "http://intranet.corp/", "fetch": record}],
                "pack": None, "rulebook_version": "1.0.0", "signature": None}
        return _self_signed(body)

    def test_cases(self):
        for cls, basis, said in (
                ("private", "address", "which its capture records say "
                 "resolved to a private address (not a public site)"),
                ("loopback", "address", "resolved to a loopback address"),
                ("public", "address", None), ("private", "name", None)):
            with self.subTest(cls=cls, basis=basis):
                bundle, pub = self._bundle(cls, basis)
                ok, reason = B.verify_bundle(bundle, pub)
                self.assertTrue(ok, reason)
                if said:
                    self.assertIn(said, reason)
                else:
                    self.assertNotIn("resolved to", reason)


class TestTokensThatLookLikeOtherThings(unittest.TestCase):
    """R1B-5, R1B-6: a padded Base64 token, and a separator escaped twice
    or written as an encoded "?", do not survive in a recorded URL."""

    T = "czNjcmV0LXJlc2V0LXRva2VuLTAxMg"

    def test_cases(self):
        for url, want in (
                (f"https://e.x/reset?{self.T}==", "https://e.x/reset?REDACTED"),
                (f"https://e.x/reset?{self.T}=", "https://e.x/reset?REDACTED"),
                (f"https://e.x/#{self.T}==", "https://e.x/#REDACTED"),
                (f"https://e.x/#/cb&{self.T}=", "https://e.x/#REDACTED&REDACTED"),
                ("https://e.x/#/access_token%253Dsecret9Value",
                 "https://e.x/#REDACTED"),
                ("https://e.x/#/cb%2526access_token%253Dsecret9Value",
                 "https://e.x/#REDACTED"),
                ("https://e.x/#/cb%3Fsecret9Value", "https://e.x/#REDACTED"),
                ("https://e.x/?a=&b=", "https://e.x/?a=&b="),
                ("https://e.x/?q=&lang=fr", "https://e.x/?q=&lang=REDACTED"),
                ("https://e.x/#/about", "https://e.x/#/about"),
                ("https://e.x/#/caf%C3%A9", "https://e.x/#/caf%C3%A9")):
            with self.subTest(url=url):
                self.assertEqual(redact_url(url)[0], want)
                for secret in (self.T, "secret9Value"):
                    self.assertNotIn(secret, redact_url(url)[0])
        self.assertIn(f"{self.T}==", secret_values(f"https://e.x/?{self.T}=="))
        self.assertEqual(redact_url("https://e.x/?SESSIONTOKEN=",
                                    keep=["SESSIONTOKEN"])[0],
                         "https://e.x/?SESSIONTOKEN=")


class TestTheHtmlReportNamesTheVersions(unittest.TestCase):
    """R1B-11."""

    def test_versions(self):
        with tempfile.TemporaryDirectory() as tmp:
            html = Path(tmp) / "r.html"
            code, _, _ = _run([str(FIXTURES / "good.html"), "--html",
                               str(html)])
            self.assertEqual(code, 0)
            text = html.read_text()
        import platform
        self.assertIn(f"verdicts read with Python {platform.python_version()}",
                      text)
        self.assertIn("justhtml ", text)


@unittest.skipUnless(F.playwright_available()[0], "needs playwright")
class TestARenderedCaptureAndItsReRun(unittest.TestCase):
    """R1B-10, R1B-12, R1B-4: what a rendered capture records, and what a
    re-run of its snapshot records."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        site = Path(cls.tmp.name) / "site"
        site.mkdir()
        (site / "index.html").write_text(
            '<!doctype html><html lang="en"><head><title>Home</title></head>'
            '<body><main><h1>Home</h1><p>Some text.</p></main></body></html>')
        handler = lambda *a, **kw: http.server.SimpleHTTPRequestHandler(  # noqa: E731
            *a, directory=str(site), **kw)
        cls.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.url = (f"http://127.0.0.1:{cls.httpd.server_address[1]}"
                   "/index.html#/about")
        cls.report = Path(cls.tmp.name) / "r.json"
        cls.snap = Path(cls.tmp.name) / "snap.html"
        with mock.patch.object(http.server.SimpleHTTPRequestHandler,
                               "log_message", lambda *a: None):
            cls.code, cls.out, cls.err = _run(
                ["--url", cls.url, "--require-render", "--json",
                 str(cls.report), "--save-snapshot", str(cls.snap)])

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.tmp.cleanup()

    def test_the_capture_record(self):
        self.assertEqual(self.code, 0, self.out + self.err)
        data = json.loads(self.report.read_text())
        rec = data["pages"][0]["fetch"]
        self.assertEqual(rec["mode"], "rendered")
        # No redirect of a route URL to itself (R1B-12).
        self.assertEqual(rec["redirects"], [])
        self.assertEqual((rec["address_class"], rec["address_basis"]),
                         ("loopback", "address"))
        libraries = data["tool"]["libraries"]
        for name in ("playwright", "axe-core", "justhtml"):
            self.assertIsInstance(libraries.get(name), str, name)

    def test_the_re_run_records_the_axe_core_that_decided_it(self):
        data = json.loads(self.report.read_text())
        rec = data["pages"][0]["fetch"]
        report = Path(self.tmp.name) / "rerun.json"
        code, out, err = _run([str(self.snap), "--provenance-attr",
                               rec["provenance_attr"], "--read-as", "dom",
                               "--json", str(report)])
        self.assertEqual(code, 0, out + err)
        again = json.loads(report.read_text())
        from bellbriar_harness.axe import AXE_VERSION
        # L53: and the Chromium that captured the snapshot.
        self.assertEqual(again["tool"]["from_snapshot"],
                         {"axe-core": AXE_VERSION,
                          "chromium": rec["browser"]["version"]})
        self.assertNotIn("axe-core", again["tool"]["libraries"])
        note = {l["layer"]: l["note"] for l in again["layers"]}["rendered"]
        self.assertIn("the snapshot records what axe-core", note)
        self.assertIn("when the snapshot was captured",
                      again["coverage_note"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
