"""Part R, the end: the worked example re-signed for 1.0 (L34, Oct 14,
2026), the sample pack reworded (L59), and the soupsieve the harness
installs held to the 2.x it was tested with.

  L34   the example's PENDING lists are empty (tests/test_examples.py holds
        it to a fresh run, and the README to what verify prints).
  L59   the sample pack no longer says integrators can pin it; its manifest
        names the new file's digest.
  R7-1  soupsieve decides which of a page's CSS selectors match (what a
        stylesheet hides) and which Chromium keeps. Its 3.0 refuses
        complex selectors inside :has() by default, and pip installed it
        where Python allowed: a link whose only text such a rule hides
        passed, where Chromium 141 names it nothing (measured). 2.10
        reworked matching too. 1.0 asks for the 2.9 line, from the 2.9.2
        its suite, field sweeps and image ran.
  R7-2  the example was signed where pip had installed soupsieve 3.0.1,
        outside that range (the results are the same for its page): the
        tool that signs it now refuses libraries outside the package's
        ranges, and the release check refuses an example that records one.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bellbriar_harness.pack import pack_reference                  # noqa: E402

from tests.test_examples import (PENDING_FIELDS, PENDING_GONE,     # noqa: E402
                                 PENDING_STATEMENT_FIELDS, PENDING_VALUES)


class TestTheExampleIsCurrent(unittest.TestCase):

    def test_nothing_is_pending(self):
        """Nothing, since the re-signing for 1.0.0rc1 (PREPUBLISH.md item
        15) closed what Part S's pack digest (SA-7) had reopened."""
        self.assertEqual((PENDING_FIELDS, PENDING_GONE,
                          PENDING_STATEMENT_FIELDS, PENDING_VALUES),
                         (set(), set(), set(), {}))
        readme = re.sub(r"\s+", " ", (ROOT / "README.md").read_text(
            encoding="utf-8"))
        self.assertNotIn("Until the example is re-signed", readme)
        evidence = re.sub(r"\s+", " ", (ROOT / "docs" / "EVIDENCE.md")
                          .read_text(encoding="utf-8"))
        self.assertNotIn("predates this and still names a pack", evidence)

    def test_the_sample_pack(self):
        """L59: reworded, and its manifest names the file it holds."""
        text = (ROOT / "examples" / "pack-sample" / "SKILL.md").read_text(
            encoding="utf-8")
        self.assertNotIn("integrators can exercise", text)
        self.assertIn("Packs are not in 1.0", text)
        ref = pack_reference(ROOT / "examples" / "pack-sample")
        self.assertEqual((ref["name"], ref["version"], ref["files"]),
                         ("wcag-sample", "0.0.3", 1))


class TestSoupsieveStaysOn29(unittest.TestCase):
    """R7-1: the dependency asks for soupsieve's 2.9 line from 2.9.2, and
    the image's pin is inside that range."""

    def requirement(self):
        try:
            import tomllib
        except ImportError:                     # Python 3.10
            raise unittest.SkipTest("tomllib is Python 3.11's")
        deps = tomllib.loads((ROOT / "pyproject.toml").read_text(
            encoding="utf-8"))["project"]["dependencies"]
        found = [d for d in deps if re.match(r"soupsieve\b", d)]
        self.assertEqual(len(found), 1, deps)
        return found[0]

    def test_the_range(self):
        req = self.requirement()
        try:
            from packaging.requirements import Requirement
        except ImportError:
            self.assertEqual(req.replace(" ", ""),
                             "soupsieve>=2.9.2,<2.10")
            return
        spec = Requirement(req).specifier
        for version, allowed in (("2.9.1", False), ("2.9.2", True),
                                 ("2.9.3", True), ("2.10", False),
                                 ("3.0.0", False), ("3.0.3", False),
                                 ("3.0.0rc1", False)):
            with self.subTest(version=version):
                self.assertEqual(spec.contains(version, prereleases=True),
                                 allowed)

    def test_the_image_pins_one_inside_it(self):
        pins = dict(line.split("==") for line in (
            ROOT / "docker" / "requirements.txt").read_text(
                encoding="utf-8").splitlines()
            if line and not line.startswith("#"))
        version = tuple(int(x) for x in pins["soupsieve"].split("."))
        self.assertTrue((2, 9, 2) <= version < (2, 10), pins["soupsieve"])

    def test_has_rules_hide_as_in_chromium(self):
        """A rule whose selector holds a :has() hides the text it names, as
        in Chromium 141 (measured: each link's name is "" there), whatever
        that :has() holds: with soupsieve 3.0 the last two passed."""
        from bellbriar_harness.engine import load_rulebook, run_page
        rb = load_rulebook()
        for selector, body in (
                (".w .t", '<p><img src="x.png" alt=""></p>'),
                (".w:has(> p) .t", '<p><img src="x.png" alt=""></p>'),
                (".w:has(p img) .t", '<p><img src="x.png" alt=""></p>'),
                (".w:has(li.a + li.b) .t",
                 '<ul><li class="a">A</li><li class="b">B</li></ul>')):
            with self.subTest(selector=selector):
                page = ('<!doctype html><html lang="en"><head><title>T'
                        f'</title><style>{selector}{{display:none}}</style>'
                        '</head><body><main><h1>T</h1><div class="w">'
                        f'{body}<a href="/x"><span class="t">Hidden</span>'
                        '</a></div></main></body></html>')
                got = run_page(page, "t.html", rb)
                verdicts = [f.verdict for r in got.results
                            if r.rule_id == "bb-link-name"
                            for f in r.findings]
                self.assertEqual(verdicts, ["fail"])


def _example_tool():
    spec = importlib.util.spec_from_file_location(
        "make_example_bundle", ROOT / "tools" / "make_example_bundle.py")
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    return tool


class TestTheExampleToolSignsInRange(unittest.TestCase):
    """R7-2: tools/make_example_bundle.py signs only with the libraries the
    package asks pip for."""

    @classmethod
    def setUpClass(cls):
        cls.tool = _example_tool()

    def test_it_reads_the_ranges_pip_reads(self):
        ranges = self.tool.declared_ranges()
        self.assertEqual({name: req for name, (req, _) in ranges.items()},
                         {"beautifulsoup4": "beautifulsoup4>=4.12",
                          "justhtml": "justhtml==3.13.0",
                          "soupsieve": "soupsieve>=2.9.2,<2.10"})
        try:
            import tomllib                                   # noqa: F401
        except ImportError:
            return
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertEqual(self.tool._dependency_lines_310(text),
                         self.tool._dependency_lines(text))

    def test_what_lies_outside_is_named(self):
        def outside(**libs):
            return [line for line, _ in
                    self.tool.libraries_outside_ranges(libs)]
        self.assertEqual(outside(justhtml="3.13.0", beautifulsoup4="4.15.0",
                                 soupsieve="2.9.2", expat="2.8.5"), [])
        self.assertEqual(outside(soupsieve="3.0.1"), [
            "soupsieve 3.0.1 is outside soupsieve>=2.9.2,<2.10"])
        for name, version, ok in (
                ("soupsieve", "2.9.1", False), ("soupsieve", "2.9.3", True),
                ("soupsieve", "2.10", False), ("soupsieve", "2.10.0", False),
                ("soupsieve", "2.9.2.post1", False),
                ("soupsieve", "3.0.0rc1", False), ("soupsieve", None, False),
                ("justhtml", "3.13", True), ("justhtml", "3.12.9", False),
                ("justhtml", "4", False), ("justhtml", "3.13.1", False),
                ("justhtml", "3.99.1", False),
                ("beautifulsoup4", "4.11.1", False),
                ("beautifulsoup4", "5.0", True)):
            with self.subTest(name=name, version=version):
                self.assertEqual(outside(**{name: version}) == [], ok)

    def _run(self, ranges):
        """Run the tool to sign with a new key it takes for a demonstration
        key, writing to a scratch folder: (exit, stderr, the files)."""
        B = self.tool.B
        priv, _pub, kid = B.generate_keypair()
        here = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            key = Path(tmp) / "demo.key"
            fd = os.open(key, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as fh:
                fh.write(B.key_file_text(priv, private=True))
            out = Path(tmp) / "evidence"
            err = io.StringIO()
            patches = (
                mock.patch.object(B, "DEMO_KEY_IDS", B.DEMO_KEY_IDS | {kid}),
                mock.patch.object(self.tool, "OUT_DIR", out),
                mock.patch.object(self.tool, "PUB_PATH",
                                  out / "reference-public-key.hex"),
                mock.patch.object(self.tool, "BUNDLE_PATH",
                                  out / "signed-bundle-example.json"),
                mock.patch.object(self.tool, "declared_ranges",
                                  lambda text=None: ranges),
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(err))
            try:
                with contextlib.ExitStack() as stack:
                    for patch in patches:
                        stack.enter_context(patch)
                    code = self.tool.main(["--private-key", str(key)])
            finally:
                os.chdir(here)
            files = sorted(p.name for p in out.glob("*")) if out.is_dir() \
                else []
        return code, err.getvalue(), files

    def test_it_refuses_to_sign_outside_them(self):
        code, err, files = self._run(
            {"soupsieve": ("soupsieve>=99", [(">=", (99,))])})
        self.assertEqual((code, files), (1, []))
        self.assertIn("refusing to sign the example", err)
        self.assertIn("is outside soupsieve>=99", err)
        self.assertIn('pip install --only-binary=:all: "soupsieve>=99"', err)

    def test_it_signs_inside_them(self):
        code, err, files = self._run({})
        self.assertEqual((code, err, files),
                         (0, "", ["reference-public-key.hex",
                                  "signed-bundle-example.json"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
