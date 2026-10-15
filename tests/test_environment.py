"""CI guard: the suite must not pass by skipping.

Browser, signing, JavaScript cross-check, lint-scan and workflow tests skip
when Playwright/Chromium, `cryptography`, Node.js, git or PyYAML are missing,
and a skipped suite still reports OK. That is how a green run could leave the whole
evidence layer untested. CI sets
BELLBRIAR_REQUIRE_ALL_TESTS=1, which turns a missing dependency into a
failure here; local runs without it are unaffected.
"""
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bellbriar_harness import bundle as B  # noqa: E402
from bellbriar_harness import fetch as F  # noqa: E402

REQUIRED = bool(os.environ.get("BELLBRIAR_REQUIRE_ALL_TESTS"))


@unittest.skipUnless(REQUIRED, "set BELLBRIAR_REQUIRE_ALL_TESTS=1 to enforce")
class TestFullEnvironment(unittest.TestCase):
    def test_cryptography_is_installed(self):
        self.assertTrue(B.HAVE_ED25519, "cryptography is missing: signing "
                                        "and verification tests would skip")

    def test_chromium_launches(self):
        ok, why = F.playwright_available()
        self.assertTrue(ok, why)
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            p.chromium.launch().close()

    def test_git_is_installed(self):
        """The lint scan's .gitignore tests (tests/test_part_r2.py) skip
        without git."""
        self.assertIsNotNone(shutil.which("git"), "git is missing: the "
                             "lint scan's .gitignore tests would skip")

    def test_pyyaml_is_installed(self):
        """The tests of the workflows, the Action and the policies
        (tests/test_part_r4.py) skip without PyYAML (the dev extra)."""
        try:
            import yaml  # noqa: F401
        except ImportError:
            self.fail("PyYAML is missing: the workflow tests would skip "
                      "(pip install '.[dev]')")

    def test_node_22_is_installed(self):
        """The independent JavaScript verifier (tests/test_canonicalization.py)
        skips without Node 22 or later."""
        node = shutil.which("node")
        self.assertIsNotNone(node, "node is missing: the JavaScript "
                                   "verification tests would skip")
        version = subprocess.run([node, "--version"], capture_output=True,
                                 text=True).stdout.strip().lstrip("v")
        self.assertGreaterEqual(int(version.split(".")[0]), 22,
                                f"node {version} is too old: the JavaScript "
                                "verification tests would skip")


if __name__ == "__main__":
    unittest.main(verbosity=2)
