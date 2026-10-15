"""N3 and N6: hosts evidence can and cannot stand behind.

N3 — `verify` names a recorded host that is not a public site (localhost,
a loopback, private or link-local address), so no reader takes a run
against a developer machine or an internal network for a public site. The
verdict does not change (docs/CANONICALIZATION.md §6 step 6).

N6 — a name with an `xn--` label that is not a real A-label is refused
(no browser fetches it), and a --url whose host evidence cannot record is
refused before the run, not after it.
"""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bellbriar_harness import bundle as B                        # noqa: E402
from tests.bundle_body import BODY  # noqa: E402
from bellbriar_harness import cli                                # noqa: E402
from bellbriar_harness import fetch as F                         # noqa: E402
from bellbriar_harness.evidence_cli import main as evidence_main  # noqa: E402

NOTES = {
    "127.0.0.1": "a loopback address", "127.8.9.1": "a loopback address",
    "::1": "a loopback address", "::ffff:7f00:1": "a loopback address",
    "10.1.2.3": "a private address", "172.31.0.1": "a private address",
    "192.168.1.1": "a private address", "fd12::1": "a private address",
    "169.254.1.1": "a link-local address", "fe80::1": "a link-local address",
    "localhost": "a loopback name", "app.localhost": "a loopback name",
    "127.1": "a loopback address", "2130706433": "a loopback address",
    "0x7f.0.0.1": "a loopback address", "0177.0.0.1": "a loopback address",
    "10.258": "a private address", "1.2.3.4.5": None, "08.0.0.1": None,
    # 2001:db8::/32 is IPv6 documentation space: one table with the
    # capture record's class (N13, Part R1).
    "172.32.0.1": None, "93.184.216.34": None,
    "2001:db8::1": "a documentation address",
    "example.com": None, "localhost.example.com": None, None: None,
}


def signed(final_url: str, domain=None):
    priv, pub, _ = B.generate_keypair()
    body = {**BODY, "bundle_format": B.BUNDLE_FORMAT, "domain": domain,
            "fetch": {"final_url": final_url, "pages": 0}, "pack": None,
            "rulebook_version": "0.3.0", "signature": None}
    return B.sign_bundle_local(body, priv), pub


def quiet(fn, *args):
    err = io.StringIO()
    with contextlib.redirect_stdout(io.StringIO()) as out, \
            contextlib.redirect_stderr(err):
        code = fn(*args)
    return code, out.getvalue(), err.getvalue()


@unittest.skipUnless(B.HAVE_ED25519, "needs cryptography")
class TestN3PrivateHostsAreNamed(unittest.TestCase):
    def test_host_notes(self):
        for host, note in NOTES.items():
            with self.subTest(host=host):
                self.assertEqual(B.host_note(host), note)

    def test_verify_names_them_and_keeps_the_verdict(self):
        cases = [("http://127.0.0.1:8000/", None, "'127.0.0.1' (a loopback "
                  "address, not a public site); no domain is stated"),
                 ("http://[::1]/", None, "'::1' (a loopback address"),
                 ("http://10.0.0.5/", "10.0.0.5", "'10.0.0.5' (a private "
                  "address, not a public site); the bundle records "
                  "rulebook"),
                 ("http://app.localhost/", "localhost", "'app.localhost' (a "
                  "loopback name, not a public site), a subdomain of "
                  "'localhost'"),
                 ("http://169.254.1.1/", None, "(a link-local address")]
        for url, domain, words in cases:
            with self.subTest(url=url):
                ok, reason = B.verify_bundle(*signed(url, domain))
                self.assertTrue(ok, reason)
                self.assertIn(words, reason)
        ok, reason = B.verify_bundle(*signed("https://www.example.com/",
                                             "example.com"))
        self.assertTrue(ok)
        self.assertNotIn("not a public site", reason)

    def test_inspect_names_them(self):
        bundle, _ = signed("http://192.168.1.20/")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "b.json"
            path.write_text(json.dumps(bundle), encoding="utf-8")
            code, out, _ = quiet(evidence_main, ["inspect", str(path)])
        self.assertIn("192.168.1.20 (a private address, not a public site)",
                      out)


class TestN6HostsEvidenceCannotRecord(unittest.TestCase):
    BOGUS = ("xn--zz.com", "xn--abc.com", "xn--abc-.com", "xn--a.com",
             "www.xn--.com", "xn--bcher-kva-.de",
             "xn--9ca.xn--0y0c.com")     # a private-use code point

    def test_bogus_a_labels_are_refused(self):
        for name in self.BOGUS:
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, "not a valid "
                                            "internationalized"):
                    B.normalize_host(name)

    def test_real_a_labels_still_pass(self):
        for name, want in (("xn--bcher-kva.de", "xn--bcher-kva.de"),
                           ("bücher.de", "xn--bcher-kva.de"),
                           ("XN--BCHER-KVA.DE", "xn--bcher-kva.de"),
                           ("xn--0zwm56d.com", "xn--0zwm56d.com"),
                           ("xn--ls8h.la", "xn--ls8h.la"),
                           # ZWNJ and ZWJ (Persian, Sinhala, Devanagari)
                           ("xn--mgbn2ecje63gr19l.ir",
                            "xn--mgbn2ecje63gr19l.ir"),
                           ("xn--10cl1a0b660p.lk", "xn--10cl1a0b660p.lk"),
                           ("xn--11b2ezcw70k.in", "xn--11b2ezcw70k.in"),
                           # Cherokee capitals; Unicode 15 characters,
                           # whatever the Python's Unicode version
                           ("xn--f9dt7l.com", "xn--f9dt7l.com"),
                           ("xn--1z9h.la", "xn--1z9h.la"),
                           ("xn--8o8n.com", "xn--8o8n.com")):
            with self.subTest(name=name):
                self.assertEqual(B.normalize_host(name), want)

    def test_domain_option_refuses_them(self):
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp) / "p.html"
            page.write_text("<!doctype html><title>t</title>", "utf-8")
            code, _, err = quiet(cli.main, [str(page), "--domain",
                                            "xn--zz.com"])
        self.assertEqual(code, 2)
        self.assertIn("not a valid internationalized", err)

    def test_an_unrecordable_url_host_is_refused_before_the_run(self):
        fetched = []

        def no_fetch(*args, **kwargs):
            fetched.append(args[0] if args else kwargs.get("url"))
            raise RuntimeError("probe: no network")
        real, F.fetch = F.fetch, no_fetch
        try:
            for url, words in (("http://a!b.com/", "which no DNS name has"),
                               ("http://a%21b.com:8080/x",
                                "which no DNS name has"),
                               ("https://xn--zz.com/page",
                                "not a valid internationalized")):
                with self.subTest(url=url), tempfile.TemporaryDirectory() as t:
                    code, _, err = quiet(cli.main, [
                        "--url", url, "--bundle", str(Path(t) / "b.json")])
                    self.assertEqual(code, 2)
                    self.assertIn(words, err)
                    self.assertFalse(Path(t, "b.json").exists())
            self.assertEqual(fetched, [])
            # A browser may still turn these into a recordable host: they
            # are fetched, and judged on the final URL after the run.
            for url in ("http://127.1:8000/", "https://ex%61mple.com/",
                        "http://faß.de/", "https://xn--hqbpi0jcw.mv/"):
                with self.subTest(url=url), tempfile.TemporaryDirectory() as t:
                    quiet(cli.main, ["--url", url, "--bundle",
                                     str(Path(t) / "b.json")])
            self.assertEqual(len(fetched), 4)
        finally:
            F.fetch = real


if __name__ == "__main__":
    unittest.main()
