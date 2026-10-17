"""Part S4: what the first CI run on GitHub found, for 1.0.0rc1.

  S4-1   the test job checked out one commit, and the suite reads the
         repository's history: it fetches every commit.
  S4-2   on macOS the current folder can be /private/var/... while PATH
         names it /var/...: the lint took a git from the current folder.
         Folders are compared as real paths.
  S4-3   git 2.56 says "gitfile does not point to a valid repository"
         where 2.55 said "not a git repository": the scan read a stale
         .git file's folder with no rules at all. Both are no repository,
         and so are a .git file with no path or in no .git file's form.
  S4-4   justhtml 3.13.1 and Playwright 1.64.0 (Chromium 156) changed
         what the suite measures: the package pins the versions the image
         runs (L142, L143), and the drawing whose requiredExtensions
         starts with white space follows the browser the run uses.
  S4-5   Windows: the suite found a bundle recording a page's path with
         backslashes, and more (L141). The commands stop there and say
         so; CI, the classifiers, the Action and the documents say the
         same.
  S4-6   APFS refuses a file name that is not UTF-8: the test that needs
         one skips there, as its neighbours do.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bellbriar_harness import cli                                  # noqa: E402
from bellbriar_harness import evidence_cli                         # noqa: E402
from bellbriar_harness import lint as L                            # noqa: E402
from bellbriar_harness import support                              # noqa: E402

GIT = shutil.which("git")


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _flat(path: str) -> str:
    return re.sub(r"\s+", " ", _text(path))


def _yaml(path: str) -> dict:
    try:
        import yaml
    except ImportError:
        raise unittest.SkipTest("PyYAML is not installed")
    return yaml.safe_load(_text(path))


def _pyproject() -> dict:
    try:
        import tomllib
    except ImportError:                       # Python 3.10: no tomllib
        raise unittest.SkipTest("tomllib needs Python 3.11")
    return tomllib.loads(_text("pyproject.toml"))


class TestTheHistoryIsFetched(unittest.TestCase):
    """S4-1."""

    def test_the_test_job_fetches_every_commit(self):
        job = _yaml(".github/workflows/bellbriar-eval.yml")["jobs"]["test"]
        checkout = [s for s in job["steps"]
                    if str(s.get("uses", "")).startswith("actions/checkout@")]
        self.assertEqual(len(checkout), 1)
        self.assertEqual(checkout[0]["with"].get("fetch-depth"), 0)
        self.assertIs(checkout[0]["with"].get("persist-credentials"), False)


class TestGitFromTheCurrentFolder(unittest.TestCase):
    """S4-2."""

    @unittest.skipUnless(GIT and os.name == "posix" and hasattr(os, "symlink"),
                         "needs git and symbolic links")
    def test_a_link_to_the_current_folder_is_the_current_folder(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        real = tmp / "real"
        real.mkdir()
        fake = real / "git"
        fake.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        fake.chmod(0o755)
        alias = tmp / "alias"
        os.symlink(real, alias)
        here = os.getcwd()
        self.addCleanup(os.chdir, here)
        self.addCleanup(L._git_exe.cache_clear)
        os.chdir(real)
        path = os.pathsep.join([str(alias), os.path.dirname(GIT)])
        with mock.patch.dict(os.environ, {"PATH": path}):
            L._git_exe.cache_clear()
            found = L._git_exe()
        self.assertEqual(os.path.realpath(found), os.path.realpath(GIT))


def _refused(message: bytes):
    return subprocess.CompletedProcess([], 128, b"", message)


class TestAGitFileThatNamesNoRepository(unittest.TestCase):
    """S4-3."""

    WORDINGS = (
        b"fatal: not a git repository: /nowhere/at/all\n",
        b"fatal: gitfile does not point to a valid repository: "
        b"/w/old/.git\n",
        b"fatal: no path in gitfile: /w/old/.git\n",
        b"fatal: invalid gitfile format: /w/old/.git\n",
        b"fatal: not a git repository (or any of the parent directories):"
        b" .git\n")

    def test_each_wording_is_no_repository(self):
        for message in self.WORDINGS:
            with self.subTest(message=message):
                notes = []
                with mock.patch.object(L, "_git",
                                       return_value=_refused(message)):
                    got = L._git_ignored(ROOT, notes)
                self.assertEqual(got, L.NOT_A_REPOSITORY)
                self.assertEqual(notes, [])

    def test_another_refusal_is_said(self):
        notes = []
        with mock.patch.object(L, "_git", return_value=_refused(
                b"fatal: detected dubious ownership in repository at '/w'\n")):
            self.assertIsNone(L._git_ignored(ROOT, notes))
        self.assertEqual(len(notes), 1)
        self.assertIn("dubious ownership", notes[0])

    @unittest.skipUnless(GIT, "needs git")
    def test_git_2_56s_wording_keeps_the_outer_rules(self):
        """R2C-8h, with the words git 2.56 has for the folder's .git."""
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        subprocess.run(["git", "init", "-q", str(tmp)], check=True)
        (tmp / ".gitignore").write_text("*.gen.tsx\n", encoding="utf-8")
        for rel in ("app/App.tsx", "old/x.gen.tsx", "old/y.tsx"):
            (tmp / rel).parent.mkdir(parents=True, exist_ok=True)
            (tmp / rel).write_text("<div>x</div>\n", encoding="utf-8")
        (tmp / "old" / ".git").write_text("gitdir: /nowhere/at/all\n",
                                          encoding="utf-8")
        real = L._git

        def git(folder, *args):
            if Path(folder).name == "old" and args[:1] == ("rev-parse",):
                return _refused(b"fatal: gitfile does not point to a valid "
                                b"repository: " + os.fsencode(folder)
                                + b"/.git\n")
            return real(folder, *args)
        notes = []
        with mock.patch.object(L, "_git", side_effect=git):
            got = sorted(p.relative_to(tmp).as_posix()
                         for p in L.collect([str(tmp)], notes))
        self.assertEqual(got, ["app/App.tsx", "old/y.tsx"])
        self.assertEqual(notes, [])


class TestThePins(unittest.TestCase):
    """S4-4."""

    def test_the_package_asks_for_what_the_image_runs(self):
        project = _pyproject()["project"]
        self.assertIn("justhtml==3.13.0", project["dependencies"])
        self.assertEqual(project["optional-dependencies"]["browser"],
                         ["playwright==1.63.0"])
        image = re.findall(r"^\S+==\S+", _text("docker/requirements.txt"),
                           re.M)
        self.assertIn("justhtml==3.13.0", image)
        self.assertIn("playwright==1.63.0", image)
        self.assertIn("v1.63.0-noble@sha256:", _text("docker/Dockerfile"))

    def test_the_example_was_made_with_the_pinned_justhtml(self):
        example = json.loads(_text(
            "examples/evidence/signed-bundle-example.json"))
        self.assertEqual(example["tool"]["libraries"]["justhtml"], "3.13.0")

    def test_s7_follows_the_browser(self):
        text = _text("tests/test_part_r6.py")
        self.assertIn('if i == "s7":\n                fails = '
                      "_chromium_draws(markup, i)", text)

    def test_the_come_back_rows(self):
        roadmap = _text("docs/ROADMAP.md")
        for row in ("L141", "L142", "L143"):
            with self.subTest(row=row):
                self.assertIn(f"- **{row}.** ", roadmap)


class TestWindows(unittest.TestCase):
    """S4-5."""

    def test_the_reason(self):
        why = support.unsupported("nt")
        self.assertIn("does not run on Windows", why)
        self.assertIn("WSL", why)
        self.assertIn("ghcr.io/bellbriar/harness", why)
        self.assertIsNone(support.unsupported("posix"))
        self.assertEqual(support.unsupported() is None, os.name != "nt")

    def test_each_command_stops_first(self):
        for module, prog in ((cli, "bellbriar-eval"),
                             (L, "bellbriar-lint"),
                             (evidence_cli, "bellbriar-evidence")):
            with self.subTest(prog=prog):
                err = io.StringIO()
                with mock.patch.object(support, "unsupported",
                                       return_value="the reason."), \
                        mock.patch.object(module, "_main",
                                          side_effect=AssertionError), \
                        contextlib.redirect_stderr(err), \
                        contextlib.redirect_stdout(io.StringIO()):
                    code = module.main(["--version"])
                self.assertEqual(code, 2)
                self.assertEqual(err.getvalue(), f"{prog}: the reason.\n")

    def test_the_commands_are_those_mains(self):
        self.assertEqual(_pyproject()["project"]["scripts"], {
            "bellbriar-eval": "bellbriar_harness.cli:main",
            "bellbriar-evidence": "bellbriar_harness.evidence_cli:main",
            "bellbriar-lint": "bellbriar_harness.lint:main"})
        self.assertIn("from .cli import main",
                      _text("src/bellbriar_harness/__main__.py"))

    def test_ci_and_the_classifiers(self):
        matrix = _yaml(".github/workflows/bellbriar-eval.yml")[
            "jobs"]["test"]["strategy"]["matrix"]
        self.assertNotIn("windows-latest", matrix["os"])
        classifiers = _pyproject()["project"]["classifiers"]
        self.assertIn("Operating System :: MacOS", classifiers)
        self.assertIn("Operating System :: POSIX :: Linux", classifiers)
        self.assertNotIn("Operating System :: OS Independent", classifiers)
        self.assertFalse([c for c in classifiers if "Windows" in c])

    def test_the_documents(self):
        self.assertIn("It runs on Linux and macOS; on Windows the commands "
                      "stop and say so, and it runs in WSL (the Windows "
                      "Subsystem for Linux) or from the container image "
                      "below.", _flat("README.md"))
        self.assertIn("runs on Linux and macOS: on Windows the three "
                      "commands stop and say so", _flat("CHANGELOG.md"))
        self.assertIn("The harness does not run on Windows.",
                      _flat("action/README.md"))
        self.assertNotIn("On macOS or Windows", _flat("action/README.md"))
        self.assertNotIn("on Windows, compared", _flat("docs/EVIDENCE.md"))
        action = _text("action/action.yml")
        self.assertIn('if [ "$RUNNER_OS" = "Windows" ]; then', action)
        self.assertIn("run the job on a Linux runner", action)


class TestANameThatIsNotUTF8(unittest.TestCase):
    """S4-6."""

    def test_the_test_skips_where_the_name_is_refused(self):
        text = _text("tests/test_part_r3.py")
        body = text[text.index("def test_a_file_name_that_is_not_utf8"):]
        body = body[:body.index("\n    def ")]
        self.assertIn("except (OSError, ValueError):", body)
        self.assertIn('self.skipTest("this file system refuses names that '
                      'are not UTF-8")', body)


if __name__ == "__main__":
    unittest.main()
