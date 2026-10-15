"""CLI inputs and outputs (review findings P1-04 to P1-07, and the first
half of P4-08).

  * P1-04: a directory walk read only `*.html`, so `page.htm`, `INDEX.HTML`
    and `.xhtml` exports were silently left out of the gate.
  * P1-05: a report or bundle that could not be written raised a
    traceback, which exits 1 — the code for "the gate failed".
  * P1-06: the JSON report left out a URL run's capture record.
  * P1-07: the snapshot was written in text mode; on Windows "\\n" becomes
    "\\r\\n" and the file no longer matches the hash the bundle records.
  * P4-08 (first half): a bundle recorded input paths as passed, so an
    absolute path put the operator's home directory into signed evidence.
    Two different files are never recorded under one name.
  * N17 (review of Part L): a browser launch error quoted its executable's
    path, home directory and all, into the bundle's fetch block.
"""
import contextlib
import hashlib
import io
import json
import os
import pathlib
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bellbriar_harness import bundle as B, cli                  # noqa: E402
from tests.test_fetch import _Server                            # noqa: E402

GOOD = ROOT / "fixtures" / "good.html"
BAD = ROOT / "fixtures" / "bad.html"


def run(*argv: str, cwd: Path | None = None) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    here = os.getcwd()
    if cwd is not None:
        os.chdir(cwd)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = cli.main(list(argv))
            except SystemExit as exc:            # argparse
                code = exc.code
    finally:
        os.chdir(here)
    return code, out.getvalue(), err.getvalue()


class TestCollect(unittest.TestCase):                         # P1-04
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bb-collect-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_htm_and_upper_case_html_are_evaluated(self):
        site = self.tmp / "site"
        site.mkdir()
        shutil.copy(BAD, site / "bad.htm")
        shutil.copy(BAD, site / "BAD.HTML")
        code, _, err = run(str(site), "--fail-on", "tier1")
        self.assertEqual(code, 1)
        self.assertIn("evaluated 2 file(s)", err)

    def test_what_a_walk_takes_and_in_what_order(self):
        site = self.tmp / "site"
        (site / "sub").mkdir(parents=True)
        for name in ("b.html", "sub/c.Htm", "notes.txt", "style.css",
                     "x.html.bak"):
            shutil.copy(GOOD, site / name)
        # Read as XML, as a browser reads it: a well-formed XHTML page.
        (site / "a.XHTML").write_text(
            '<html xmlns="http://www.w3.org/1999/xhtml" lang="en"><head>'
            '<title>A</title></head><body><main><h1>A</h1><p>Hello.</p>'
            '</main></body></html>', encoding="utf-8")
        got = [str(p.relative_to(site)) for p, _ in cli._collect([str(site)])]
        self.assertEqual(got, sorted(["b.html", "a.XHTML",
                                      str(Path("sub") / "c.Htm")]))
        code, _, err = run(str(site), "--fail-on", "tier1")
        self.assertEqual(code, 0)
        self.assertIn("evaluated 3 file(s)", err)

    def test_a_named_file_is_taken_whatever_it_is_called(self):
        page = self.tmp / "page.php"
        shutil.copy(BAD, page)
        self.assertEqual(run(str(page), "--fail-on", "tier1")[0], 1)

    def test_a_missing_path_is_an_error(self):
        code, _, err = run(str(self.tmp / "nope"), "--fail-on", "never")
        self.assertEqual(code, 2)
        self.assertIn("nope", err)


class TestWriteErrors(unittest.TestCase):                     # P1-05
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bb-write-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_a_missing_directory_is_a_run_error_not_a_gate_failure(self):
        missing = self.tmp / "missing"
        for flag in ("--json", "--html", "--bundle"):
            for policy in ("tier1", "never"):
                with self.subTest(flag=flag, policy=policy):
                    code, _, err = run(str(GOOD), flag, str(missing / "r.out"),
                                       "--fail-on", policy)
                    self.assertEqual(code, 2)
                    self.assertIn(f"cannot write {missing / 'r.out'}", err)
                    self.assertNotIn("Traceback", err)
        self.assertFalse(missing.exists())

    def test_a_write_that_fails_after_the_run(self):
        # Past the check made before the run: the file is a directory by
        # the time the report is written.
        target = self.tmp / "r.json"
        target.mkdir()
        with mock.patch.object(cli, "_unwritable", return_value=None):
            for flag in ("--json", "--html", "--bundle"):
                with self.subTest(flag=flag):
                    code, _, err = run(str(GOOD), flag, str(target),
                                       "--fail-on", "never")
                    self.assertEqual(code, 2)
                    self.assertIn(f"cannot write {target}:", err)

    def test_reports_still_write(self):
        out = self.tmp / "r.json"
        code, stdout, _ = run(str(GOOD), "--json", str(out))
        self.assertEqual(code, 0)
        self.assertIn(f"json report: {out}", stdout)
        self.assertIsNone(json.loads(out.read_text(encoding="utf-8"))["fetch"])


class TestUrlRunRecord(unittest.TestCase):                    # P1-06, P1-07
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bb-url-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        site = self.tmp / "site"
        site.mkdir()
        # Line breaks in the page, so a text-mode write would change bytes.
        (site / "p.html").write_bytes(GOOD.read_bytes().replace(b"\r\n", b"\n")
                                      + b"\n<!-- two\nlines -->\n")
        self.server = _Server(site)
        self.addCleanup(self.server.stop)
        self.url = f"{self.server.base}/p.html?token=tok-L-6c1e&lang=en"

    def test_the_json_report_carries_the_capture_record(self):
        out = self.tmp / "r.json"
        code, _, _ = run("--url", self.url, "--no-render", "--record-query",
                         "lang", "--json", str(out))
        self.assertEqual(code, 0)
        text = out.read_text(encoding="utf-8")
        report = json.loads(text)
        # The run's record says what it fetched; each page's, how.
        self.assertEqual(set(report["fetch"]),
                         {"final_url", "host", "pages", "list"})
        self.assertEqual(report["fetch"]["final_url"],
                         report["pages"][0]["fetch"]["final_url"])
        fetch = report["pages"][0]["fetch"]
        for key in ("final_url", "http_status", "mode", "snapshot_sha256"):
            self.assertIn(key, fetch)
        self.assertEqual(fetch["http_status"], 200)
        self.assertEqual(fetch["mode"], "server")
        self.assertNotIn("tok-L-6c1e", text)
        self.assertIn("token=REDACTED", fetch["final_url"])
        self.assertIn("lang=en", fetch["final_url"])

    def test_the_snapshot_is_the_bytes_the_hash_names(self):
        snap, out = self.tmp / "snap.html", self.tmp / "r.json"
        real = pathlib.Path.write_text

        def windows_text(self, data, encoding=None, errors=None, newline=None):
            return real(self, data, encoding=encoding, errors=errors,
                        newline="\r\n")
        # As on Windows, text-mode writes turn "\n" into "\r\n".
        with mock.patch.object(pathlib.Path, "write_text", windows_text):
            code, _, err = run("--url", self.url, "--no-render",
                               "--save-snapshot", str(snap), "--json", str(out))
        self.assertEqual(code, 0, err)
        recorded = json.loads(out.read_text(encoding="utf-8"))["pages"][0][
            "fetch"]
        self.assertIn(b"\n<!-- two\nlines -->", snap.read_bytes())
        self.assertEqual(hashlib.sha256(snap.read_bytes()).hexdigest(),
                         recorded["snapshot_sha256"])

    def test_a_snapshot_that_cannot_be_written(self):
        code, _, err = run("--url", self.url, "--no-render", "--save-snapshot",
                           str(self.tmp / "missing" / "s.html"))
        self.assertEqual(code, 2)
        self.assertIn("cannot write", err)
        self.assertNotIn("tok-L-6c1e", err)


class TestRecordedPaths(unittest.TestCase):                   # P4-08a
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bb-home-u-client-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        dist = self.tmp / "client" / "dist"
        (dist / "blog").mkdir(parents=True)
        shutil.copy(GOOD, dist / "index.html")
        shutil.copy(GOOD, dist / "blog" / "post.html")
        (self.tmp / "work").mkdir()

    def bundle(self, *args: str, cwd: Path | None = None) -> tuple[dict, str]:
        out = self.tmp / "b.json"
        code, stdout, err = run(*args, "--bundle", str(out), cwd=cwd)
        self.assertEqual(code, 0, err)
        text = out.read_text(encoding="utf-8")
        # The console's page lines name pages as the bundle does.
        listed = "\n".join(line for line in stdout.splitlines()
                           if line.startswith("T1 "))
        return json.loads(text), text + listed

    def test_the_rule(self):
        cases = [
            ("dist/index.html", None, "dist/index.html"),
            ("index.html", None, "index.html"),
            ("/home/u/client/dist/index.html", "/home/u/client/dist",
             "dist/index.html"),
            ("/home/u/client/dist/index.html", "/home/u/client/dist/index.html",
             "index.html"),
            ("/home/u/client/dist/index.html", None, "index.html"),
            ("../site/index.html", "../site/index.html", "index.html"),
            ("../site/a/b.html", "../site", "site/a/b.html"),
        ]
        for path, arg, want in cases:
            with self.subTest(path=path, arg=arg):
                self.assertEqual(B.recorded_path(path, arg), want)

    def test_an_absolute_directory(self):
        dist = self.tmp / "client" / "dist"
        data, text = self.bundle(str(dist))
        self.assertEqual([i["path"] for i in data["inputs"]],
                         ["dist/blog/post.html", "dist/index.html"])
        self.assertEqual([p["path"] for p in data["pages"]],
                         ["dist/blog/post.html", "dist/index.html"])
        self.assertNotIn(str(self.tmp), text)
        self.assertNotIn("bb-home-u-client", text)

    def test_an_absolute_file_and_a_dotdot_path(self):
        data, text = self.bundle(str(self.tmp / "client" / "dist" / "index.html"))
        self.assertEqual(data["inputs"][0]["path"], "index.html")
        self.assertNotIn(str(self.tmp), text)
        work = self.tmp / "work"
        data, text = self.bundle("../client/dist", cwd=work)
        self.assertEqual([i["path"] for i in data["inputs"]],
                         ["dist/blog/post.html", "dist/index.html"])
        self.assertNotIn("..", json.dumps(data["inputs"]))
        self.assertNotIn(str(self.tmp), text)

    def test_a_relative_path_is_recorded_as_given(self):
        data, _ = self.bundle("client/dist/index.html", cwd=self.tmp)
        self.assertEqual(data["inputs"][0]["path"], "client/dist/index.html")
        self.assertEqual(data["pages"][0]["path"], "client/dist/index.html")

    def test_two_files_never_share_a_name(self):
        dist = self.tmp / "client" / "dist"
        # The same file named twice is one page, evaluated once (R3A-2:
        # it was evaluated twice, its findings and totals doubled).
        data, _ = self.bundle(str(dist / "index.html"),
                              str(dist / "blog" / "post.html"),
                              str(dist / "index.html"))
        self.assertEqual([i["path"] for i in data["inputs"]],
                         ["index.html", "post.html"])
        (dist / "blog" / "index.html").write_bytes(GOOD.read_bytes())
        data, text = self.bundle(str(dist / "index.html"),
                                 str(dist / "blog" / "index.html"))
        self.assertEqual([i["path"] for i in data["inputs"]],
                         ["dist/index.html", "blog/index.html"])
        self.assertEqual([p["path"] for p in data["pages"]],
                         ["dist/index.html", "blog/index.html"])
        self.assertNotIn(str(self.tmp), text)

    def test_a_home_directory_is_never_added_to_tell_files_apart(self):
        for user in ("alice", "bob"):
            d = self.tmp / "home" / user / "site"
            d.mkdir(parents=True)
            shutil.copy(GOOD, d / "index.html")
        data, text = self.bundle(
            str(self.tmp / "home" / "alice" / "site" / "index.html"),
            str(self.tmp / "home" / "bob" / "site" / "index.html"))
        self.assertEqual([i["path"] for i in data["inputs"]],
                         ["~1/site/index.html", "~2/site/index.html"])
        self.assertNotIn("alice", text)
        self.assertNotIn("bob", text)

    def test_a_relative_path_keeps_its_name_when_told_apart(self):
        (self.tmp / "work" / "dist").mkdir(parents=True)
        shutil.copy(GOOD, self.tmp / "work" / "dist" / "index.html")
        data, _ = self.bundle("dist/index.html", str(self.tmp / "client" / "dist"),
                              cwd=self.tmp / "work")
        self.assertEqual([i["path"] for i in data["inputs"]],
                         ["dist/index.html", "dist/blog/post.html",
                          "client/dist/index.html"])   # only the clash grows

    def test_build_bundle_never_records_an_absolute_path(self):
        from bellbriar_harness.engine import run_paths
        from bellbriar_harness.scoring import score_site
        page = self.tmp / "client" / "dist" / "index.html"
        r = run_paths([page])
        bundle = B.build_bundle(r, score_site(r["pages"], r["rulebook"]), [page])
        self.assertEqual(bundle["inputs"][0]["path"], "index.html")
        self.assertEqual(bundle["pages"][0]["path"], "index.html")



class TestHomeDirectoryInErrors(unittest.TestCase):           # N17
    """A browser that fails to launch quotes its executable's path; the
    reason was recorded in the bundle's fetch block (and now the JSON
    report), home directory included."""

    def test_launch_failure_records_no_home_directory(self):
        try:
            import playwright  # noqa: F401
        except ImportError:
            self.skipTest("playwright not installed")
        import subprocess
        tmp = Path(tempfile.mkdtemp(prefix="bb-launch-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        (tmp / "p.html").write_bytes(GOOD.read_bytes())
        server = _Server(tmp)
        self.addCleanup(server.stop)
        fake = "/home/jdoe-bb-l/.cache/ms-playwright"
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"),
                   PLAYWRIGHT_BROWSERS_PATH=fake)
        out = subprocess.run(
            [sys.executable, "-m", "bellbriar_harness", "--url",
             f"{server.base}/p.html", "--bundle", str(tmp / "b.json"),
             "--json", str(tmp / "r.json")],
            capture_output=True, text=True, env=env, timeout=120)
        self.assertEqual(out.returncode, 0, out.stderr)
        reason = json.loads((tmp / "b.json").read_text())["pages"][0][
            "fetch"]["fallback_reason"]
        self.assertIn("rendered fetch failed", reason)
        for text in ((tmp / "b.json").read_text(), (tmp / "r.json").read_text(),
                     out.stderr, out.stdout):
            self.assertNotIn("jdoe-bb-l", text)
        # The record names the failure in the harness's words (N8); the
        # browser's own text, scrubbed, is on the console only.
        self.assertIn("BrowserType.launch: the Chromium build Playwright "
                      "uses is not installed", reason)
        self.assertNotIn("ms-playwright", reason)
        self.assertIn("~/.cache/ms-playwright", out.stderr)


class TestRedactLocalPaths(unittest.TestCase):
    def test_home_directories(self):
        from bellbriar_harness.redact import redact_text
        for raw, want in (
                ("at /home/ann/.cache/x", "at ~/.cache/x"),
                ("at /Users/ann/Library/x", "at ~/Library/x"),
                ("at C:\\Users\\Ann\\AppData\\x", "at ~\\AppData\\x"),
                ("at C:/Users/Ann/x", "at ~/x"),
                ("see https://example.com/home/ann/x", "see https://example.com/home/ann/x"),
                ("/rootfs/x", "/rootfs/x"),
                # Round 3: a name with spaces goes whole; a site path stays.
                ("at C:\\Users\\John Smith\\AppData\\x", "at ~\\AppData\\x"),
                ("at /Users/John Smith/Library/x", "at ~/Library/x"),
                ("HTTP 404 for /home/products", "HTTP 404 for /home/products"),
                ("copied /home/products and /home/x/y", "copied /home/products and ~/y")):
            with self.subTest(raw=raw):
                self.assertEqual(redact_text(raw), want)

    def test_a_judge_error_quotes_no_home_directory(self):
        from bellbriar_harness.judge import JudgeResult
        from bellbriar_harness.judged import run_judged

        class Broken:
            name, model, calibrated = "broken", "none", False

            def judge(self, rubric_id, item):
                return JudgeResult(rubric_id, "needs_review",
                                   "judge error: [Errno 2] No such file: "
                                   "'/home/ann-bb/.config/judge/key.txt'",
                                   "none", error=True)
        tmp = Path(tempfile.mkdtemp(prefix="bb-judge-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        page = tmp / "p.html"
        page.write_text('<!doctype html><html lang="en"><head><title>T</title>'
                        '</head><body><main><h1>T</h1><img src="a.png" alt='
                        '"Photo of our team"></main></body></html>')
        jr = run_judged([page], Broken())
        text = json.dumps(jr.pages)
        self.assertIn("judge error", text)
        self.assertNotIn("ann-bb", text)


if __name__ == "__main__":
    unittest.main()
