"""Part R, stage 4: install, CI and hygiene.

  P1-14  A missing path says "path not found" (tests/test_part_r3.py).
  N27    A run whose every page was empty says why for how it was read: a
         run that rendered them is not told to render them.
  D9     --require-sandbox refuses a run whose Chromium cannot start its
         sandbox, rather than running the browser without it.
  L27    The browser runs unsandboxed only after the errors Chromium gives
         when its sandbox cannot start, not after any error that names it.
  L21    The scroll and settle steps run in an isolated world of the
         harness's own (tests/test_fetch_hardening.py, in a browser).
  N28    bellbriar-eval --install-browser.
  P1-09  The package's metadata (PEP 639 license expression and files,
         URLs, classifiers), MANIFEST.in, and tools/check_dist.py.
  Intel Macs  cryptography stays below 49 there, where 49 has no wheel.
  H1     LICENSE is the verbatim Apache-2.0 text; NOTICE holds the
         copyright and axe-core's attribution.
  H3     SECURITY.md, CODEOWNERS, CONTRIBUTING.md with DCO sign-off.
  H5     tools/repo_guard.py: no key, golden set or pack in the repository.
  A11    The release workflow (Trusted Publishing), the container image and
         the Action.
  CI     The test workflow's matrix: Linux, macOS (Intel too), Windows,
         Python 3.11 to 3.14 (3.10 until Part S, which requires 3.11).
  H7     The README leads with the install paths and what is checked.
  A9     bellbriar-lint --format sarif.
  A10    --baseline: the gate counts only findings an earlier report does
         not list; the reports and bundles list every finding and record
         the baseline.

And the fixes from the two independent reviews of this stage: R4A
(release, packaging, CI: the classes above and TestReviewOfR4Guard) and
R4B (runtime: TestReviewOfR4Baseline, TestSettling, and the classes
above).
"""
import contextlib
import copy
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from bellbriar_harness import baseline as BL                       # noqa: E402
from bellbriar_harness import cli                                  # noqa: E402
from bellbriar_harness import fetch as F                           # noqa: E402
from bellbriar_harness import lint as L                            # noqa: E402
from bellbriar_harness.engine import load_rulebook, run_page       # noqa: E402
from tests.test_fetch_hardening import HAVE_BROWSER, _WHY          # noqa: E402

FIXTURES = ROOT / "fixtures"
_AXE = (ROOT / "src" / "bellbriar_harness" / "vendor" / "axe-core"
        / "axe.min.js")
PAGE = ('<!doctype html><html lang="en"><head><title>T</title></head><body>'
        '<main><h1>T</h1>{}</main></body></html>')


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = cli.main([str(a) for a in argv])
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


def tmpdir(test) -> Path:
    d = Path(tempfile.mkdtemp(prefix="bb-r4-"))
    test.addCleanup(shutil.rmtree, d, True)
    return d


# ---------------------------------------------------------------------------
# N27, D9, L27, N28
# ---------------------------------------------------------------------------

class TestNoPageWhy(unittest.TestCase):
    """N27: what to do when every page was empty, by how it was read."""

    @staticmethod
    def pages(*modes):
        return [SimpleNamespace(fetch={"mode": m} if m else None)
                for m in modes]

    def args(self, **kw):
        return SimpleNamespace(**{"render": False, "no_render": False, **kw})

    def test_each_way_of_reading(self):
        why = cli._no_page_why(self.pages("rendered", "rendered"),
                               self.args(), url_run=True)
        self.assertIn("empty when captured, after its scripts ran", why)
        self.assertNotIn("--render", why)
        why = cli._no_page_why(self.pages("server"), self.args(render=True),
                               url_run=False)
        self.assertIn("it could not be rendered, so this run read it as a "
                      "file", why)
        why = cli._no_page_why(self.pages("server", "server"),
                               self.args(render=True), url_run=False)
        self.assertIn("none of them could be rendered, so this run read "
                      "them as files", why)
        why = cli._no_page_why(self.pages("server"),
                               self.args(no_render=True), url_run=True)
        self.assertIn("run it without --no-render", why)
        why = cli._no_page_why(self.pages("server"), self.args(),
                               url_run=True)
        self.assertIn("--install-browser", why)
        self.assertIn("as the HTML the server sent", why)
        why = cli._no_page_why(self.pages(None), self.args(), url_run=False)
        self.assertIn("bellbriar-eval <folder> --render", why)

    def test_what_the_review_found(self):
        """R4B-14: a run that rendered some pages is not told it could
        render none; a page that navigated away is not blamed on the
        browser; a saved capture is not told to render the build."""
        why = cli._no_page_why(self.pages("rendered", "server"),
                               self.args(render=True), url_run=False)
        # "its" for one page (R4E-4).
        self.assertIn("1 of them was rendered and still empty after its "
                      "scripts ran, and the other 1 was read as a file", why)
        self.assertNotIn("none of them could be rendered", why)
        self.assertIn("a page that went to another document when rendered "
                      "is read as the file it is", why)
        for kw in ({"provenance_attr": "data-bb-x"}, {"read_as": "dom"}):
            why = cli._no_page_why(self.pages(None), self.args(**kw),
                                   url_run=False)
            self.assertIn("captures a browser made earlier", why)
            self.assertNotIn("--render", why)


class _FakeChromium:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def launch(self, chromium_sandbox):
        self.calls.append(chromium_sandbox)
        if chromium_sandbox and self.error:
            raise RuntimeError(self.error)
        return "browser"


class TestRequireSandbox(unittest.TestCase):
    """D9 and L27."""

    def launch(self, error=None, root=False, require=False):
        p = SimpleNamespace(chromium=_FakeChromium(error))
        with mock.patch.object(os, "geteuid", create=True,
                               return_value=0 if root else 1000):
            return F._launch_chromium(p, require), p.chromium.calls

    def test_as_root(self):
        (browser, why), calls = self.launch(root=True)
        self.assertEqual(calls, [False])
        self.assertIn("running as root", why)
        with self.assertRaisesRegex(F.SandboxRefused, "--require-sandbox"):
            self.launch(root=True, require=True)

    #: What Chromium prints when its sandbox cannot start (L27), each as
    #: Playwright's launch error carries it.
    MESSAGES = (
        "[FATAL:zygote_host_impl_linux.cc(127)] No usable sandbox! If you "
        "are running on Ubuntu 23.10+ or another Linux distro that has "
        "disabled unprivileged user namespaces with AppArmor, see …",
        # AppArmor's restriction, where the namespace is made but the user
        # cannot be mapped into it (R4B-6), in two Chromium versions.
        "[1007/101010.000:FATAL:sandbox/linux/services/credentials.cc:131] "
        "Check failed: . : Permission denied (13)",
        "[0101/000000.000:FATAL:credentials.cc(126)] Check failed: . : "
        "Permission denied (13)",
        "Failed to move to new namespace: PID namespaces supported, Network "
        "namespace supported, but failed: errno = Operation not permitted",
        "[FATAL:setuid_sandbox_host.cc(158)] The SUID sandbox helper binary "
        "was found, but is not configured correctly.",
        "[FATAL:zygote_host_impl_linux.cc(90)] Running as root without "
        "--no-sandbox is not supported. See https://crbug.com/638180.",
    )

    def test_the_errors_chromium_gives(self):
        for said in self.MESSAGES:
            with self.subTest(said=said[:40]):
                (browser, note), calls = self.launch(
                    error=f"BrowserType.launch: Target page, context or "
                          f"browser has been closed\n{said}\n")
                self.assertEqual(calls, [True, False])
                self.assertTrue(note.startswith("it could not start here: "),
                                note)
                with self.assertRaises(F.SandboxRefused):
                    self.launch(error=said, require=True)
        # Every pattern is one of these.
        for pattern, _why in F._SANDBOX_ERRORS:
            self.assertTrue(any(pattern.search(m) for m in self.MESSAGES),
                            pattern.pattern)
        # The reason does not blame the host when a container's profile
        # refused the namespaces (R4A-2).
        self.assertIn("container's security profile",
                      F._sandbox_failure(RuntimeError(self.MESSAGES[1])))
        # Another failure in that file is not a sandbox one.
        self.assertEqual(F._sandbox_failure(RuntimeError(
            "credentials.cc is mentioned")), "")

    def test_another_error_is_not_a_reason_to_drop_the_sandbox(self):
        """L27: it fell back after any error naming the sandbox."""
        with self.assertRaisesRegex(RuntimeError, "sandbox_policy"):
            self.launch(error="BrowserType.launch: invalid sandbox_policy "
                              "flag in the profile")

    def test_a_refusal_is_never_a_fallback(self):
        """With render=None a failed capture reads the server's HTML; a
        refusal must not."""
        with mock.patch.object(F, "playwright_available",
                               return_value=(True, "")), \
                mock.patch.object(F, "_fetch_rendered_isolated",
                                  side_effect=F._ChildError(
                                      "SandboxRefused", "--require-sandbox: "
                                      "no sandbox")), \
                mock.patch.object(F, "fetch_server") as server:
            with self.assertRaisesRegex(F.SandboxRefused, "no sandbox"):
                F.fetch("http://127.0.0.1:9/", require_sandbox=True)
            server.assert_not_called()

    @unittest.skipUnless(HAVE_BROWSER, _WHY)
    @unittest.skipUnless(hasattr(os, "geteuid") and os.geteuid() == 0,
                         "Chromium's sandbox can start here")
    def test_the_cli_refuses_the_run(self):
        d = tmpdir(self)
        (d / "p.html").write_text(PAGE.format("<p>x</p>"), encoding="utf-8")
        code, _out, err = run(d / "p.html", "--render", "--require-sandbox")
        self.assertEqual(code, 2, err)
        self.assertIn("--require-sandbox", err)
        self.assertIn("running as root", err)


#: Pages that keep changing for 6 s after they load, each where a watch on
#: the first root element alone does not see it (R4B-7).
_STILL_CHANGING = {
    "swap": "document.replaceChild(document.documentElement.cloneNode(true),"
            " document.documentElement);",
    "rewrite": "document.open(); document.write('<!doctype html><html "
               "lang=\"en\"><head><title>W</title></head><body><main><h1>W"
               "</h1></main></body></html>'); document.close();",
    "shadow": "window.bbRoot = document.getElementById('host')"
              ".attachShadow({mode: 'open'});",
}


def _changing_page(how: str) -> bytes:
    return ('<!doctype html><html lang="en"><head><title>T</title></head>'
            '<body><main><h1>T</h1><div id="host"></div></main><script>'
            'addEventListener("load", () => setTimeout(() => {'
            + _STILL_CHANGING[how] +
            'const t0 = Date.now(); const tick = setInterval(() => {'
            'const p = document.createElement("p"); p.textContent = "t" + '
            '(Date.now() - t0); (window.bbRoot || document.body).appendChild(p);'
            'if (Date.now() - t0 > 6000) clearInterval(tick); }, 30);'
            '}, 300));</script></body></html>').encode()


@unittest.skipUnless(HAVE_BROWSER, _WHY)
class TestSettling(unittest.TestCase):
    """R4B-7: a page that replaces its root, rewrites itself or changes
    inside an open shadow root does not look settled while it changes."""

    def test_a_page_still_changing_is_not_settled(self):
        from tests.test_fetch_hardening import _Site, send
        for how in _STILL_CHANGING:
            with self.subTest(how=how):
                site = _Site({"/": send(_changing_page(how))})
                self.addCleanup(site.stop)
                r = F.fetch_rendered(site.base + "/", settle_cap_ms=2000,
                                     axe=False, narrow=False)
                self.assertFalse(r.wait.get("settled"), r.wait)
                self.assertTrue(any("still mutating" in n
                                    for n in r.notes), r.notes)

    def test_a_page_that_removes_its_root_does_not_break_the_step(self):
        """R4B-8: the step's script no longer fails on a page with no root
        element, so the page is not said to have crashed."""
        from tests.test_fetch_hardening import _Site, send
        page = (b'<!doctype html><html lang="en"><head><title>T</title>'
                b'</head><body><main><h1>T</h1></main><script>'
                b'addEventListener("load", () => setTimeout(() => {'
                b'const r = document.documentElement; r.remove();'
                b'setTimeout(() => document.appendChild(r), 1500); }, 50));'
                b'</script></body></html>')
        site = _Site({"/": send(page)})
        self.addCleanup(site.stop)
        r = F.fetch(site.base + "/")
        self.assertNotIn("crashed", r.fallback_reason or "")


class TestReviewOfR4Round2(unittest.TestCase):
    """The review of the R4 fixes, runtime side (R4C)."""

    @staticmethod
    def site(bad: set):
        from tests.test_fetch_hardening import _Site
        import urllib.parse as up

        def page(h):
            q = up.parse_qs(up.urlsplit(h.path).query)
            body = PAGE.format('<img src="a.png">' if q.get("id", [""])[0]
                               in bad else "<p>ok</p>").encode()
            h.send_response(200)
            h.send_header("Content-Type", "text/html")
            h.send_header("Content-Length", str(len(body)))
            h.end_headers()
            h.wfile.write(body)
        return _Site({"/p": page, "/": page})

    def test_a_page_listed_twice_keeps_its_number(self):
        """R4C-1: a page listed twice with two fragments is numbered by
        the least of its URLs, not by the one the list names first."""
        d = tmpdir(self)
        bad = {"1"}
        site = self.site(bad)
        self.addCleanup(site.stop)
        u = site.base + "/p?id={}&t=SECRET{}#{}"
        other = u.format(2, "B", "c")

        def rank(url):
            return hashlib.sha256(F.canonical_url(url).encode()).hexdigest()
        # Two fragments of page 1 that rank either side of page 2, so the
        # one the list names first decides page 1's number unless the fix
        # holds.
        low = next(u.format(1, "A", f"f{i}") for i in range(10000)
                   if rank(u.format(1, "A", f"f{i}")) < rank(other))
        high = next(u.format(1, "A", f"f{i}") for i in range(10000)
                    if rank(u.format(1, "A", f"f{i}")) > rank(other))
        (d / "a.txt").write_text("\n".join([low, other, high]))
        (d / "b.txt").write_text("\n".join([high, other, low]))
        code, _out, err = run("--urls", d / "a.txt", "--no-render", "--json",
                              d / "base.json", "--fail-on", "never")
        self.assertEqual(code, 0, err)
        code, out, err = run("--urls", d / "b.txt", "--no-render",
                             "--baseline", d / "base.json")
        self.assertEqual(code, 0, out + err)          # nothing changed
        bad.clear()
        bad.add("2")
        code, out, err = run("--urls", d / "b.txt", "--no-render",
                             "--baseline", d / "base.json")
        self.assertEqual(code, 1, out + err)          # a new failure

    @unittest.skipUnless(HAVE_BROWSER, _WHY)
    def test_a_removed_shadow_host_does_not_keep_the_page_busy(self):
        """R4C-2: an open shadow root whose host left the document."""
        from tests.test_fetch_hardening import _Site, send
        page = (b'<!doctype html><html lang="en"><head><title>T</title>'
                b'</head><body><main><h1>T</h1><div id="host"></div></main>'
                b'<script>addEventListener("load", () => {'
                b'const host = document.getElementById("host");'
                b'const root = host.attachShadow({mode: "open"});'
                b'const p = document.createElement("p"); root.appendChild(p);'
                b'let n = 0; setInterval(() => { p.textContent = "t" + n++; }, 30);'
                b'setTimeout(() => host.remove(), 300); });</script>'
                b'</body></html>')
        site = _Site({"/": send(page)})
        self.addCleanup(site.stop)
        r = F.fetch_rendered(site.base + "/", settle_cap_ms=4000, axe=False,
                             narrow=False)
        self.assertTrue(r.wait.get("settled"), r.wait)

    @unittest.skipUnless(HAVE_BROWSER, _WHY)
    def test_a_page_cannot_word_a_refusal(self):
        """R4C-3: with --require-render, the browser's error text (which a
        page can write) reaches the console, never the report."""
        from tests.test_fetch_hardening import _Site, send
        claim = "FORGED-RECORD-TEXT 7f3e"
        page = ('<!doctype html><html lang="en"><head><title>T</title>'
                '</head><body><main><h1>T</h1></main><script>'
                'const boom = {get() { throw new Error("' + claim + '"); }};'
                'for (const n of ["documentElement", "body", "head", '
                '"querySelectorAll", "createTreeWalker"]) { try { '
                'Object.defineProperty(document, n, boom); } catch (e) {} }'
                '</script></body></html>').encode()
        site = _Site({"/": send(page)})
        self.addCleanup(site.stop)
        d = tmpdir(self)
        code, out, err = run("--url", site.base + "/", "--require-render",
                             "--json", d / "r.json", "--fail-on", "never")
        report = (d / "r.json").read_text(encoding="utf-8") \
            if (d / "r.json").exists() else ""
        self.assertNotIn(claim, report)
        if code == 2:
            self.assertIn("rendered fetch failed", err)

    def test_the_step_code_is_not_a_browser_error(self):
        """R4C-9: StepFailed's code is the harness's, not the browser's."""
        with mock.patch.object(F, "playwright_available",
                               return_value=(True, "")), \
                mock.patch.object(F, "_fetch_rendered_isolated",
                                  side_effect=F._ChildError("StepFailed",
                                                            "page")), \
                mock.patch.object(F, "fetch_server") as server:
            server.return_value = F.FetchResult(
                url="http://127.0.0.1:9/", final_url="http://127.0.0.1:9/",
                mode="server", html="<p>x</p>", status=200)
            r = F.fetch("http://127.0.0.1:9/")
        self.assertIn("navigated away while it was scrolled",
                      r.fallback_reason)
        self.assertIsNone(r.fallback_detail)
        with mock.patch.object(F, "playwright_available",
                               return_value=(True, "")), \
                mock.patch.object(F, "_fetch_rendered_isolated",
                                  side_effect=F._ChildError("StepFailed",
                                                            "script")):
            with self.assertRaises(F.FetchError) as caught:
                F.fetch("http://127.0.0.1:9/", render=True)
        self.assertNotIn("(script)", str(caught.exception))
        self.assertFalse(getattr(caught.exception, "detail", ""))

    def test_what_is_printed_is_escaped(self):
        """R4C-7: soft hyphens, tag characters and backslashes too."""
        from bellbriar_harness.evidence_cli import _printable
        text = "a\u00adb\U000e0041c\u202ed\\e\n"
        self.assertEqual(cli._shown(text),
                         "a\\u00adb\\U000e0041c\\u202ed\\\\e\\u000a")
        self.assertEqual(_printable(text),
                         "a\\u00adb\\U000e0041c\\u202ed\\e\\u000a")
        # A name's undecodable bytes are escaped, not an error to print.
        self.assertEqual(cli._shown("x\udce9"), "x\\udce9")

    def test_an_app_shell_read_as_a_file_says_how(self):
        """R4C-6: a --render run's page that was not rendered is not told
        to run --render."""
        d = tmpdir(self)
        (d / "app").mkdir()
        (d / "app" / "a.html").write_text(
            '<!doctype html><html lang="en"><head><title>A</title></head>'
            '<body><div id="root"></div><script src="app.js"></script>'
            '</body></html>')
        fr = SimpleNamespace(mode="server", fallback_reason="when rendered, it "
                             "navigated to /x, so the browser showed another "
                             "page; read as the file it is")
        page = run_page((d / "app" / "a.html").read_bytes(), "app/a.html",
                        load_rulebook())
        self.assertFalse(page.evaluable)
        self.assertIn("--render", page.not_evaluable_reason)
        cli._shell_reason(page, fr, build=True)
        self.assertNotIn("--render", page.not_evaluable_reason)
        self.assertIn("this run read it as the file it is without running it "
                      "(when rendered, it navigated", page.not_evaluable_reason)
        why = cli._no_page_why([SimpleNamespace(fetch={"mode": "rendered"}),
                                SimpleNamespace(fetch={"mode": "server"})],
                               SimpleNamespace(render=True, no_render=False),
                               False)
        self.assertIn("the other 1 was read as a file.", why)

    def test_install_browser_takes_no_other_option_at_any_value(self):
        """R4C-11: an option given at its default value is still refused;
        --require-sandbox, abbreviated or not, is not."""
        for extra in (["--fail-on", "tier1"], ["--max-pages", "50"],
                      ["--fail-on=never"]):
            with self.subTest(extra=extra):
                code, _out, err = run("--install-browser", *extra)
                self.assertEqual(code, 2)
                self.assertIn("installs the browser and exits", err)
        with mock.patch("subprocess.call", return_value=0), \
                mock.patch.object(cli, "_browser_starts",
                                  return_value=("", "")):
            for argv in (["--install-browser", "--require-sandbox"],
                         ["--install-b", "--require-s"]):
                code, _out, err = run(*argv)
                self.assertEqual(code, 0, err)

    def test_a_lint_that_linted_nothing_is_not_clean(self):
        """R4C-10."""
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(L, "lint_text",
                               side_effect=OSError(5, "Input/output error")), \
                contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(err):
            code = L.main([str(FIXTURES / "lint-good.jsx")])
        self.assertEqual(code, 2, err.getvalue())
        self.assertIn("could be linted", err.getvalue())

    def test_inspect_a_baseline_that_is_not_a_record(self):
        """R4C-11."""
        from bellbriar_harness import evidence_cli
        d = tmpdir(self)
        (d / "b.json").write_text(json.dumps({"bundle_format": "x",
                                              "baseline": False}))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            evidence_cli.main(["inspect", str(d / "b.json")])
        # A value that is no object is said to be none (R5D-15); an
        # object without the members this release writes is its maker's.
        self.assertIn("baseline    NOT a record (the bundle has a number or "
                      "a boolean there)", out.getvalue())


class TestReviewOfR4Round3(unittest.TestCase):
    """The review of the round-3 fixes, runtime side (R4E)."""

    def test_the_page_kept_does_not_follow_the_list(self):
        """R4E-1: a page listed under two fragments, or spelled two ways,
        is recorded the same whichever the list names first."""
        d = tmpdir(self)
        bad = {"2"}
        site = TestReviewOfR4Round2.site(bad)
        self.addCleanup(site.stop)
        root = site.base
        for lists in (
                # Fragment variants of one page.
                ([f"{root}/p?id=2", f"{root}/p?id=1", f"{root}/p?id=2#x"],
                 [f"{root}/p?id=2#x", f"{root}/p?id=1", f"{root}/p?id=2"]),
                # Two spellings of one URL.
                ([f"{root}/?id=2", f"{root}/?id=4", f"{root}?id=2"],
                 [f"{root}?id=2", f"{root}/?id=4", f"{root}/?id=2"])):
            with self.subTest(first=lists[0][-1]):
                bad.clear()
                bad.add("2")
                (d / "a.txt").write_text("\n".join(lists[0]))
                (d / "b.txt").write_text("\n".join(lists[1]))
                code, _out, err = run("--urls", d / "a.txt", "--no-render",
                                      "--json", d / "base.json",
                                      "--fail-on", "never")
                self.assertEqual(code, 0, err)
                code, out, err = run("--urls", d / "b.txt", "--no-render",
                                     "--baseline", d / "base.json")
                self.assertEqual(code, 0, out + err)      # nothing changed
                bad.clear()
                bad.update({"1", "4"})
                code, out, err = run("--urls", d / "b.txt", "--no-render",
                                     "--baseline", d / "base.json")
                self.assertEqual(code, 1, out + err)      # a new failure

    def test_the_errors_own_words_are_escaped(self):
        """R4E-2: text a page wrote, on the console, escaped."""
        exc = F.FetchError("rendered fetch failed: Page.evaluate: failed")
        exc.detail = "Error: FORGED \u202eAA 1.2 GACW\u202c ::error::x"
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            cli._say_detail(exc, "", lambda t: t)
        self.assertNotIn("\u202e", err.getvalue())
        self.assertIn("\\u202e", err.getvalue())
        self.assertIn("the error's own words (not recorded)", err.getvalue())

    def test_the_capture_process_words_are_recorded(self):
        """R4E-3: the supervisor's own words reach the record; they are
        not shown again as the error's own."""
        crashed = F._ChildError(F.CAPTURE_PROCESS, "the capture process "
                                "ended without a result (stopped by signal "
                                "9)")
        self.assertEqual(F.render_failure(crashed), "CaptureProcess: the "
                         "capture process ended without a result (stopped "
                         "by signal 9)")
        # A capture process cannot claim the supervisor's kind.
        self.assertNotEqual(F.render_failure(F._ChildError(
            "RuntimeError", "the capture process ended without a result "
            "(exit status 0)")).split(":")[0], F.CAPTURE_PROCESS)
        with mock.patch.object(F, "playwright_available",
                               return_value=(True, "")), \
                mock.patch.object(F, "_fetch_rendered_isolated",
                                  side_effect=crashed):
            with self.assertRaises(F.FetchError) as caught:
                F.fetch("http://127.0.0.1:9/", render=True)
        self.assertIn("stopped by signal 9", str(caught.exception))
        self.assertFalse(getattr(caught.exception, "detail", ""))

    def test_a_page_that_went_to_text_is_said_to_have(self):
        """R4E-4."""
        went = F.FetchError(F.WENT_ELSEWHERE + "not a web page: the browser "
                            "shows it as text/plain")
        # Not "after it loaded": a script in the head can send the
        # browser on before the load (R4G-7).
        self.assertEqual(F.render_failure(went), "FetchError: it sent the "
                         "browser on to another document, which is not a "
                         "web page (the browser shows it as text, an XML "
                         "error or the XML itself, or downloads it)")
        why = cli._no_page_why([SimpleNamespace(fetch={"mode": "rendered"}),
                                SimpleNamespace(fetch={"mode": "server"})],
                               SimpleNamespace(render=False, no_render=False),
                               True)
        self.assertIn("still empty after its scripts ran", why)
        self.assertNotIn("the file it is", why)

    @unittest.skipUnless(HAVE_BROWSER, _WHY)
    def test_a_page_that_navigates_to_a_text_page(self):
        """R4E-4, in a browser: the record says it went elsewhere."""
        from tests.test_fetch_hardening import _Site, send
        page = (b'<!doctype html><html lang="en"><head><title>T</title>'
                b'</head><body><main><h1>T</h1></main><script>'
                b'location.replace("/missing");</script></body></html>')
        site = _Site({"/": send(page), "/missing": send(
            b"not found", ctype="text/plain", status=404)})
        self.addCleanup(site.stop)
        # A 404 it goes to is refused, whatever its type (R4I-3).
        with self.assertRaises(F.FetchError) as caught:
            F.fetch(site.base + "/")
        self.assertIn("sent the browser on to another document, which "
                      "answered HTTP 404", str(caught.exception))
        self.assertNotIn("not a web page", str(caught.exception))

    def test_a_file_named_twice_is_linted_once(self):
        """R4E-5."""
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(L, "lint_text",
                               side_effect=OSError(5, "Input/output error")), \
                contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(err):
            code = L.main([str(FIXTURES / "lint-good.jsx"),
                           str(FIXTURES / "lint-good.jsx"),
                           str(FIXTURES)])
        self.assertEqual(code, 2, err.getvalue())
        files = L.collect([str(FIXTURES / "lint-good.jsx"), str(FIXTURES)])
        self.assertEqual(len(files), len(set(map(os.path.abspath, files))))

    def test_inspect_an_incomplete_baseline(self):
        from bellbriar_harness import evidence_cli
        d = tmpdir(self)
        (d / "b.json").write_text(json.dumps({"bundle_format": "x",
                                              "baseline": {}}))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            evidence_cli.main(["inspect", str(d / "b.json")])
        self.assertIn("baseline    a record without the members this "
                      "release writes", out.getvalue())


class TestReviewOfR4Round4(unittest.TestCase):
    """The review of the round-4 fixes, runtime side (R4G)."""

    @staticmethod
    def site(routes):
        from tests.test_fetch_hardening import _Site
        return _Site(routes)

    @unittest.skipUnless(HAVE_BROWSER, _WHY)
    def test_where_a_page_sends_the_browser(self):
        """R4G-1, R4G-2, R4G-3: the document the tab shows is judged by its
        own response. An error page a script sends it to is refused; a
        download or a 204 replaces nothing; an XHTML page that goes on to
        an HTML one is captured as that page."""
        from tests.test_fetch_hardening import send

        def page(script=""):
            return PAGE.format(f"<p>x</p><script>{script}</script>").encode()
        go = "location.replace('{}')"
        later = "setTimeout(function () {{ location.href = '{}'; }}, 50)"
        xhtml = (b'<html xmlns="http://www.w3.org/1999/xhtml" lang="en">'
                 b'<head><title>T</title><script>location.replace("/ok")'
                 b'</script></head><body><main><h1>T</h1></main></body>'
                 b'</html>')
        site = self.site({
            "/to404": send(page(go.format("/missing"))),
            "/missing": send(page(), status=404),
            "/dl": send(page(later.format("/file.zip"))),
            "/file.zip": send(b"PK\x05\x06" + bytes(18),
                              ctype="application/zip",
                              headers=[("Content-Disposition",
                                        "attachment; filename=f.zip")]),
            "/n204": send(page(later.format("/empty"))),
            "/empty": send(b"", status=204),
            "/x": send(xhtml, ctype="application/xhtml+xml"),
            "/ok": send(page()),
        })
        self.addCleanup(site.stop)
        # Refused, as a 404 the page was sent to directly is (R4I-3).
        with self.assertRaises(F.FetchError) as caught:
            F.fetch(site.base + "/to404")
        self.assertIn("which answered HTTP 404", str(caught.exception))
        code, _out, err = run("--url", site.base + "/to404", "--fail-on",
                              "never")
        self.assertEqual(code, 2, err)
        self.assertIn("which answered HTTP 404", err)
        for path in ("/dl", "/n204"):
            with self.subTest(path=path):
                r = F.fetch(site.base + path)
                self.assertEqual(r.mode, "rendered", r.fallback_reason)
                self.assertFalse(r.navigated)
                self.assertTrue(r.final_url.endswith(path))
                self.assertFalse(any("another document" in n
                                     for n in r.notes))
        r = F.fetch(site.base + "/x")
        self.assertEqual(r.mode, "rendered", r.fallback_reason)
        self.assertTrue(r.navigated)
        self.assertTrue(r.final_url.endswith("/ok"))

    @unittest.skipUnless(HAVE_BROWSER, _WHY)
    def test_a_refresh_due_while_the_page_is_read(self):
        """A refresh due at once commits while the page is read: the
        document it went to is judged, each time, and the record says the
        page sent the browser there (R4G-7: not "after it loaded")."""
        from tests.test_fetch_hardening import send
        site = self.site({
            "/m": send(b'<!doctype html><html lang="en"><head><title>T'
                       b'</title><meta http-equiv="refresh" content="0;'
                       b'url=/t"></head><body><main><h1>T</h1></main>'
                       b'</body></html>'),
            "/t": send(b"plain", ctype="text/plain")})
        self.addCleanup(site.stop)
        for _ in range(2):
            # A URL run refuses it: the server's HTML of a page that sends
            # the browser on is not what anyone is shown (R5A-5).
            with self.assertRaises(F.FetchError) as cm:
                F.fetch(site.base + "/m")
            self.assertIn("it sent the browser on to another document, "
                          "which is not a web page", str(cm.exception))
            r = F.fetch(site.base + "/m", fallback="read as the file it is",
                        error_target="fallback")
            self.assertEqual(r.mode, "server")
            self.assertIn("it sent the browser on to another document, "
                          "which is not a web page", r.fallback_reason)

    @unittest.skipUnless(HAVE_BROWSER, _WHY)
    def test_a_built_page_that_goes_elsewhere(self):
        """R4G-1 in a --render run: a page it goes to that the build lacks
        does not make the file unread; R4G-11: one that goes to a text
        file is recorded as read as the file it is."""
        d = tmpdir(self)
        site = d / "site"
        site.mkdir()
        (site / "a.html").write_text(PAGE.format(
            "<script>location.replace('/missing.html')</script>"))
        (site / "b.html").write_text(PAGE.format(
            "<script>location.replace('/t.txt')</script>"))
        (site / "t.txt").write_text("text")
        code, _out, err = run(site, "--render", "--json", d / "r.json",
                              "--fail-on", "never")
        self.assertEqual(code, 0, err)
        report = json.loads((d / "r.json").read_text())
        reasons = {pg["path"].rsplit("/", 1)[-1]:
                   (pg["fetch"] or {}).get("fallback_reason") or ""
                   for pg in report["pages"]}
        # The build server answers a file it lacks with a text page.
        self.assertIn("another document", reasons["a.html"])
        self.assertTrue(reasons["a.html"].endswith(
            "read as the file it is"), reasons)
        self.assertTrue(reasons["b.html"].endswith(
            "read as the file it is"), reasons)
        self.assertNotIn("server HTML", reasons["b.html"])
        self.assertNotIn("the build server answered HTTP", err)

    def test_a_named_file_is_linted_whatever_else_names_it(self):
        """R4G-4: a file named on the command line is linted even when a
        folder named first holds it and it looks minified; R4G-6: names
        that lead to two files are two files."""
        d = tmpdir(self)
        (d / "src").mkdir()
        bad = "export const X = () => <div onClick={go}>open</div>;\n"
        (d / "src" / "app.min.js").write_text(bad)
        (d / "src" / "b.jsx").write_text("export const B = 1;\n")
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = L.main([str(d / "src"), str(d / "src" / "app.min.js")])
        self.assertEqual(code, 1, out.getvalue() + err.getvalue())
        self.assertIn("bl-div-click", out.getvalue())
        if hasattr(os, "symlink"):
            (d / "a" / "real" / "sub").mkdir(parents=True)
            (d / "a" / "x.jsx").write_text("export const A = 1;\n")
            (d / "a" / "real" / "x.jsx").write_text(bad)
            try:
                os.symlink("real/sub", d / "a" / "link")
            except OSError:
                return
            files = L.collect([str(d / "a" / "x.jsx"),
                               str(d / "a" / "link" / ".." / "x.jsx")])
            self.assertEqual(len(files), 2)

    def test_what_a_server_or_a_name_prints_is_escaped(self):
        """R4G-5: a server's Content-Type, and a file's name, reach the
        console, the JSON and the HTML report escaped."""
        from tests.test_fetch_hardening import send
        esc, csi = chr(27), chr(0x9b)
        site = self.site({"/c": send(
            b"x", ctype="text/" + esc + "[2J" + esc + "[31mFORGED" + csi
            + "0mevil")})
        self.addCleanup(site.stop)
        d = tmpdir(self)
        code, out, err = run("--url", site.base + "/c", "--no-render",
                             "--json", d / "r.json", "--html", d / "r.html",
                             "--fail-on", "never")
        self.assertEqual(code, 2, err)
        for text in (out, err, (d / "r.json").read_text(),
                     (d / "r.html").read_text()):
            self.assertNotIn(esc, text)
            self.assertNotIn(csi, text)
        self.assertIn("\\u001b", err)
        name = "a" + esc + "[2Jb.html"
        (d / name).write_text(PAGE.format(""))
        code, out, err = run(d / name, "--fail-on", "never")
        self.assertEqual(code, 0, err)
        self.assertNotIn(esc, out + err)

    def test_the_note_names_the_url_kept(self):
        """R4G-9: when a later URL is the least of a page's, the note says
        that one is kept."""
        site = TestReviewOfR4Round2.site({"2"})
        self.addCleanup(site.stop)
        d = tmpdir(self)
        (d / "u.txt").write_text(f"{site.base}/p?id=2#x\n{site.base}/p?id=2\n")
        code, _out, err = run("--urls", d / "u.txt", "--no-render",
                              "--fail-on", "never")
        self.assertEqual(code, 0, err)
        # Named by its place in the list: two fragments read alike once
        # redacted (R4I-4).
        self.assertIn("evaluated once, as distinct URL 2 of the 2 listed "
                      "(exact repeats dropped)\n", err)


class TestReviewOfR4Round5(unittest.TestCase):
    """The review of the round-5 fixes, runtime side (R4I)."""

    site = staticmethod(TestReviewOfR4Round4.site)

    @unittest.skipUnless(HAVE_BROWSER, _WHY)
    def test_where_no_page_or_an_error_page_is(self):
        """R4I-1: a page that sends the browser to its own error page or a
        blank page is refused, never scored as HTTP 200; R4I-3: a 404 it
        goes to is refused whatever its type; in a --render run the file
        is read as it is."""
        from tests.test_fetch_hardening import send

        def go(to):
            return send(PAGE.format(
                f"<script>location.replace('{to}')</script>").encode())
        site = self.site({
            "/neterr": go("http://127.0.0.1:9/"),
            "/blank": go("about:blank"),
            "/text404": go("/t"),
            "/t": send(b"missing", ctype="text/plain", status=404),
        })
        self.addCleanup(site.stop)
        for path, words in (("/neterr", "no server sent"),
                            ("/blank", "no server sent"),
                            ("/text404", "answered HTTP 404")):
            with self.subTest(path=path):
                code, _out, err = run("--url", site.base + path,
                                      "--fail-on", "never")
                self.assertEqual(code, 2, err)
                self.assertIn(words, err)
                self.assertIn("not the page you meant to evaluate", err)
                with self.assertRaises(F.FetchError):
                    F.fetch(site.base + path, render=True)
        d = tmpdir(self)
        (d / "a.html").write_text(PAGE.format(
            "<script>location.replace('/nowhere.html')</script>"))
        code, _out, err = run(d, "--render", "--json", d / "r.json",
                              "--fail-on", "never")
        self.assertEqual(code, 0, err)
        reason = json.loads((d / "r.json").read_text())["pages"][0][
            "fetch"]["fallback_reason"]
        self.assertIn("answered HTTP 404", reason)
        self.assertTrue(reason.endswith("read as the file it is"), reason)

    @unittest.skipUnless(HAVE_BROWSER, _WHY)
    def test_an_error_page_that_moves_on(self):
        """R4I-5: a page that answered 404 and then went on is refused
        under its own URL, and not said to be the document it went to."""
        from tests.test_fetch_hardening import send
        site = self.site({
            "/e404": send(PAGE.format(
                "<script>location.replace('/ok')</script>").encode(),
                status=404),
            "/ok": send(PAGE.format("<p>ok</p>").encode())})
        self.addCleanup(site.stop)
        r = F.fetch(site.base + "/e404")
        self.assertEqual(r.status, 404)
        self.assertTrue(r.final_url.endswith("/e404"))
        self.assertFalse(r.navigated)
        self.assertFalse(any("another document" in n for n in r.notes))

    def test_no_name_starts_a_command(self):
        """R4I-2: a line break in a file's name cannot start a line a CI
        runner reads as a command, from any command's output."""
        from bellbriar_harness.redact import escaped_console
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            with escaped_console():
                print("a\n::error title=X::pwned\n##vso[task.setvariable]1")
                sys.stdout.write(":")
                sys.stdout.write(":warning::x\n  ::notice::y\n")
                print("text :: in the middle, and # at no line's start")
        lines = out.getvalue().splitlines()
        self.assertFalse([x for x in lines
                          if x.lstrip().startswith(("::", "##"))], lines)
        self.assertIn("text :: in the middle", out.getvalue())
        d = tmpdir(self)
        try:
            (d / "a\n::error title=X::y.jsx").write_text(
                "export const A = () => <div onClick={go}>x</div>;\n")
        except OSError:
            self.skipTest("this file system refuses a line break in a name")
        out = io.StringIO()
        with contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(io.StringIO()):
            L.main([str(d)])
        self.assertNotIn("\n::error", out.getvalue())
        self.assertIn("\\u000a::error", out.getvalue())

    def test_joiners_are_text(self):
        """R4I-6: the zero-width joiner and non-joiner are printed as
        they are; bidi controls still are not."""
        from bellbriar_harness.redact import printable
        zwnj, zwj, rlo = chr(0x200C), chr(0x200D), chr(0x202E)
        self.assertEqual(printable("a" + zwnj + "b" + zwj), "a" + zwnj + "b"
                         + zwj)
        self.assertEqual(printable(rlo), "\\u202e")


class TestInstallBrowser(unittest.TestCase):
    """N28."""

    def test_it_installs_and_checks(self):
        with mock.patch("subprocess.call", return_value=0) as call, \
                mock.patch.object(cli, "_browser_starts",
                                  return_value=("", "")):
            code, _out, err = run("--install-browser")
        self.assertEqual(code, 0, err)
        self.assertEqual(call.call_args[0][0][1:],
                         ["-m", "playwright", "install", "chromium"])
        self.assertIn("installed and starts with its sandbox", err)

    def test_it_says_what_went_wrong(self):
        with mock.patch("subprocess.call", return_value=1):
            code, _out, err = run("--install-browser")
        self.assertEqual(code, 2)
        self.assertIn("installer stopped", err)
        with mock.patch("subprocess.call", return_value=0), \
                mock.patch.object(cli, "_browser_starts",
                                  return_value=("system libraries it needs "
                                                "are missing", "")):
            code, _out, err = run("--install-browser")
        self.assertEqual(code, 2)
        self.assertIn("system libraries", err)

    def test_without_playwright(self):
        with mock.patch.dict(sys.modules, {"playwright": None}):
            code, _out, err = run("--install-browser")
        self.assertEqual(code, 2)
        self.assertIn("bellbriar-harness[browser]", err)

    def test_it_runs_alone(self):
        code, _out, err = run("--install-browser", FIXTURES / "good.html")
        self.assertEqual(code, 2)
        self.assertIn("installs the browser and exits", err)
        # R4B-16: no other option is silently ignored.
        for extra in (["--json", "r.json"], ["--baseline", "b.json"],
                      ["--strict"], ["--fail-on", "never"]):
            with self.subTest(extra=extra):
                code, _out, err = run("--install-browser", *extra)
                self.assertEqual(code, 2)
                self.assertIn("installs the browser and exits", err)

    def test_it_says_whether_the_sandbox_starts(self):
        """R4B-6, R4B-16: a browser that starts only without its sandbox is
        not reported as ready for --require-sandbox."""
        off = "running as root, where Chromium's sandbox cannot start"
        with mock.patch("subprocess.call", return_value=0), \
                mock.patch.object(cli, "_browser_starts",
                                  return_value=("", off)):
            code, _out, err = run("--install-browser")
            self.assertEqual(code, 0, err)
            self.assertIn("without its sandbox (running as root", err)
            self.assertIn("--require-sandbox would refuse them", err)
            code, _out, err = run("--install-browser", "--require-sandbox")
            self.assertEqual(code, 2, err)
            self.assertIn("would be refused", err)

    def test_the_check_starts_it_as_a_run_does(self):
        """R4B-6: the check tries the sandbox first, as _launch_chromium
        does, rather than starting the browser without it."""
        import inspect
        src = inspect.getsource(cli._browser_starts)
        self.assertIn("_launch_chromium(p)", src)
        self.assertNotIn("chromium_sandbox=False", src)


# ---------------------------------------------------------------------------
# Packaging, license, hygiene
# ---------------------------------------------------------------------------

def _pyproject() -> dict:
    try:
        import tomllib
    except ImportError:                                   # Python 3.10
        raise unittest.SkipTest("tomllib needs Python 3.11")
    with open(ROOT / "pyproject.toml", "rb") as fh:
        return tomllib.load(fh)


class TestPackage(unittest.TestCase):
    """P1-09, H1 and the Intel Mac pin."""

    def test_the_metadata(self):
        meta = _pyproject()
        project = meta["project"]
        self.assertEqual(project["license"],
                         "Apache-2.0 AND MPL-2.0 AND MIT AND ISC AND "
                         "BSD-3-Clause")
        self.assertIn("tests/data/wpt-tree-construction/LICENSE.md",
                      project["license-files"])
        for f in project["license-files"]:
            self.assertTrue((ROOT / f).is_file(), f)
        self.assertIn("NOTICE", project["license-files"])
        self.assertFalse([c for c in project["classifiers"]
                          if c.startswith("License ::")])
        self.assertTrue(project["urls"]["Homepage"].startswith("https://"))
        # One version: the package's metadata and what --version prints
        # (R4F-7).
        from bellbriar_harness import __version__
        self.assertEqual(project["version"], __version__)
        self.assertEqual(project["authors"], [{"name": "Bellbriar, Inc."}])
        self.assertIn("setuptools>=77.0.3", meta["build-system"]["requires"])
        # The dev extra installs PyYAML, which the workflow tests read
        # with; without it they would skip.
        self.assertTrue([r for r in project["optional-dependencies"]["dev"]
                         if r.lower().startswith("pyyaml")])

    def test_intel_macs_keep_a_cryptography_with_wheels(self):
        """cryptography 49 and later publish no wheels for Intel Macs."""
        try:
            from packaging.markers import Marker
            from packaging.requirements import Requirement
        except ImportError:
            from setuptools._vendor.packaging.requirements import Requirement
            from setuptools._vendor.packaging.markers import Marker  # noqa
        reqs = [Requirement(r) for r in _pyproject()["project"]
                ["dependencies"] if r.startswith("cryptography")]
        for system, machine, capped in (("darwin", "x86_64", True),
                                        ("darwin", "arm64", False),
                                        ("linux", "x86_64", False),
                                        ("win32", "AMD64", False)):
            env = {"sys_platform": system, "platform_machine": machine}
            live = [r for r in reqs if r.marker.evaluate(env)]
            with self.subTest(system=system, machine=machine):
                self.assertEqual(len(live), 1)
                self.assertTrue(live[0].specifier.contains("48.0.1"))
                self.assertEqual(live[0].specifier.contains("49.0.0"),
                                 not capped)
                self.assertEqual(live[0].specifier.contains("50.0.2"),
                                 not capped)

    def test_the_license_is_the_apache_text(self):
        """H1: verbatim, so GitHub and scanners recognize it; the
        copyright is in NOTICE, and no "All Rights Reserved"."""
        data = (ROOT / "LICENSE").read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(),
                         "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb"
                         "003417bc523d30")
        notice = (ROOT / "NOTICE").read_text(encoding="utf-8")
        self.assertIn("Copyright 2026 Bellbriar, Inc.", notice)
        self.assertIn("axe-core", notice)
        self.assertIn("Mozilla Public License 2.0", notice)
        for name in ("LICENSE", "NOTICE", "README.md"):
            self.assertNotIn("All Rights Reserved",
                             (ROOT / name).read_text(encoding="utf-8"))

    def test_the_sdist_carries_what_the_tests_read(self):
        manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")
        for line in ("graft tests", "graft fixtures", "graft docs",
                     "graft examples", "graft tools", "graft .github",
                     "graft action", "graft docker", ".dockerignore",
                     "include LICENSE NOTICE"):
            self.assertIn(line, manifest)
        self.assertIn("global-exclude *.key", manifest)


class TestCheckDist(unittest.TestCase):
    """tools/check_dist.py, on distributions made here by hand."""

    def setUp(self):
        # The hand-made sdist holds only what check_dist names; whether it
        # holds every file git tracks is tested below.
        import check_dist as CD
        patcher = mock.patch.object(CD, "tracked", return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def make(self, folder: Path, extra_wheel=(), extra_sdist=(),
             metadata=None) -> None:
        import check_dist as CD
        version = CD._version()
        meta = metadata if metadata is not None else "\n".join(
            [f"Metadata-Version: 2.4", f"Name: bellbriar-harness",
             f"Version: {version}",
             f"License-Expression: {CD.LICENSE_EXPRESSION}"]
            + [f"License-File: {f}" for f in CD.LICENSE_FILES]
            + ['Requires-Dist: cryptography<49,>=42; sys_platform == '
               '"darwin" and platform_machine == "x86_64"'])
        info = f"bellbriar_harness-{version}.dist-info"
        with zipfile.ZipFile(folder / f"bellbriar_harness-{version}-py3-"
                             "none-any.whl", "w") as z:
            z.writestr(f"{info}/METADATA", meta)
            for f in CD.LICENSE_FILES:
                z.writestr(f"{info}/licenses/{f}", "text")
            for f in CD.WHEEL_NEEDS:
                # axe-core as the package pins it (SB-4); the rest stubs.
                z.writestr(f, _AXE.read_bytes() if f.endswith("axe.min.js")
                           else "x")
            for name, data in extra_wheel:
                z.writestr(name, data)
        top = f"bellbriar_harness-{version}"
        with tarfile.open(folder / f"{top}.tar.gz", "w:gz") as t:
            for name in [*CD.SDIST_NEEDS, *[n for n, _ in extra_sdist]]:
                data = dict(extra_sdist).get(name, b"x")
                info_t = tarfile.TarInfo(f"{top}/{name}")
                info_t.size = len(data)
                t.addfile(info_t, io.BytesIO(data))

    def test_a_good_pair_passes_and_a_key_does_not(self):
        import check_dist as CD
        good = tmpdir(self)
        self.make(good)
        self.assertEqual(CD.check(good), [])
        bad = tmpdir(self)
        self.make(bad, extra_wheel=[("bellbriar_harness/demo.key", "00")],
                  extra_sdist=[("tools/x.key", b"00")])
        problems = CD.check(bad)
        self.assertTrue(any("demo.key" in p for p in problems), problems)
        self.assertTrue(any("x.key" in p for p in problems), problems)

    def test_missing_metadata_is_named(self):
        import check_dist as CD
        d = tmpdir(self)
        self.make(d, metadata="Metadata-Version: 2.4\nName: x\n")
        problems = " ".join(CD.check(d))
        self.assertIn("License-Expression", problems)
        self.assertIn("Intel", problems)

    def test_every_tracked_file_ships(self):
        """R4A-1: the sdist left out the image and the Action, which the
        suite reads, and nothing noticed."""
        import check_dist as CD
        for need in (".dockerignore", "docker/Dockerfile",
                     "action/action.yml", "action/README.md"):
            self.assertIn(need, CD.SDIST_NEEDS)
        d = tmpdir(self)
        self.make(d)
        with mock.patch.object(CD, "tracked", return_value=[
                *CD.SDIST_NEEDS, "docs/NEW.md"]):
            problems = CD.check(d)
        self.assertTrue(any("leaves out 1 file(s) git tracks (docs/NEW.md)"
                            in p for p in problems), problems)
        with mock.patch.object(CD, "tracked",
                               return_value=list(CD.SDIST_NEEDS)):
            self.assertEqual(CD.check(d), [])

    def test_a_key_in_a_folder_named_dist_is_found(self):
        """R4A-12: an unpacked distribution is read whole."""
        import check_dist as CD
        from cryptography.hazmat.primitives.asymmetric import ed25519
        key = ed25519.Ed25519PrivateKey.generate()
        d = tmpdir(self)
        self.make(d, extra_sdist=[
            ("fixtures/dist/a.txt", key.private_bytes_raw().hex().encode()),
            ("fixtures/a.pub",
             key.public_key().public_bytes_raw().hex().encode())])
        self.assertTrue(any("private half" in p for p in CD.check(d)))


class TestRepositoryGuard(unittest.TestCase):
    """H5."""

    def guard(self, folder: Path) -> list:
        import repo_guard
        return repo_guard.check(folder)

    def test_the_repository_is_clean(self):
        self.assertEqual(self.guard(ROOT), [])

    def test_what_it_catches(self):
        from cryptography.hazmat.primitives.asymmetric import ed25519
        priv = ed25519.Ed25519PrivateKey.generate()
        priv_hex = priv.private_bytes_raw().hex()
        pub_hex = priv.public_key().public_bytes_raw().hex()
        key_id = hashlib.sha256(bytes.fromhex(pub_hex)).hexdigest()[:16]
        cases = {
            "signer.key": ("signer.key", "aa"),
            # Spelled in pieces, so this file holds no such header itself.
            "PEM": ("notes.txt", "-----BEGIN " + "PRIVATE KEY-----\nMC4C\n"),
            "OpenSSH": ("id.txt", "-----BEGIN OPENSSH " + "PRIVATE KEY-----\n"),
            "pack": ("packs/real/pack.json", "{}"),
            "golden": ("golden-set/a.json", "{}"),
            "calibration": ("data/calibration_2026.csv", "x"),
        }
        for label, (name, text) in cases.items():
            with self.subTest(label=label):
                d = tmpdir(self)
                (d / name).parent.mkdir(parents=True, exist_ok=True)
                (d / name).write_text(text, encoding="utf-8")
                self.assertTrue(self.guard(d), label)
        for label, other in (("its public half", pub_hex),
                             ("its key id", f'"key_id": "{key_id}"')):
            with self.subTest(label=label):
                d = tmpdir(self)
                (d / "a.txt").write_text(f"seed {priv_hex}\n",
                                         encoding="utf-8")
                (d / "b.json").write_text(other, encoding="utf-8")
                self.assertTrue(any("private half" in p
                                    for p in self.guard(d)))
        # A digest is not a key: nothing in the repository holds the public
        # half of a key whose private half is this file's digest.
        d = tmpdir(self)
        (d / "a.txt").write_text(hashlib.sha256(b"x").hexdigest(),
                                 encoding="utf-8")
        self.assertEqual(self.guard(d), [])

    def test_the_vector_key_is_public_by_construction(self):
        vectors = json.loads((ROOT / "docs" / "canonicalization-vectors.json")
                             .read_text(encoding="utf-8"))["vector_key"]
        d = tmpdir(self)
        (d / "v.json").write_text(json.dumps(vectors), encoding="utf-8")
        self.assertEqual(self.guard(d), [])

    def test_the_sample_pack_is_allowed(self):
        d = tmpdir(self)
        (d / "examples" / "pack-sample").mkdir(parents=True)
        (d / "examples" / "pack-sample" / "pack.json").write_text("{}")
        self.assertEqual(self.guard(d), [])


class TestReviewOfR4Guard(unittest.TestCase):
    """R4A-12: the ways a private key can be written that the guard read
    past, and a key that is only in the history."""

    def setUp(self):
        from cryptography.hazmat.primitives.asymmetric import ed25519
        key = ed25519.Ed25519PrivateKey.generate()
        self.key = key
        self.priv = key.private_bytes_raw()
        self.pub = key.public_key().public_bytes_raw()
        self.kid = hashlib.sha256(self.pub).hexdigest()[:16]

    def guard(self, files: dict, everything=False) -> list:
        import repo_guard
        d = tmpdir(self)
        for rel, data in files.items():
            (d / rel).parent.mkdir(parents=True, exist_ok=True)
            (d / rel).write_bytes(data if isinstance(data, bytes)
                                  else data.encode("utf-8"))
        return repo_guard.check(d, everything)

    def test_every_spelling_of_a_key(self):
        import base64 as b64
        from cryptography.hazmat.primitives import serialization
        priv, pub = self.priv, self.pub
        der = self.key.private_bytes(serialization.Encoding.DER,
                                     serialization.PrivateFormat.PKCS8,
                                     serialization.NoEncryption())
        known = {"a.pub": pub.hex()}
        cases = {
            "0x, upper case": {"a.txt": "0x" + priv.hex().upper(), **known},
            "seed then public key, in hex": {"a.txt": (priv + pub).hex()},
            "seed then public key, in base64": {
                "a.txt": b64.b64encode(priv + pub).decode()},
            "base64": {"a.txt": b64.b64encode(priv).decode(), **known},
            "two lines": {"a.txt": priv.hex()[:32] + "\n" + priv.hex()[32:],
                          **known},
            "colons": {"a.txt": ":".join(priv.hex()[i:i + 2]
                                         for i in range(0, 64, 2)), **known},
            "a 32-byte file": {"key.bin": priv, **known},
            "PKCS#8": {"key.der": der},
            "PKCS#8 in hex": {"key.txt": der.hex()},
            "an upper-case key id": {"a.txt": priv.hex(),
                                     "id.txt": "key_id " + self.kid.upper()},
            "UTF-16": {"a.txt": priv.hex().encode("utf-16"), **known},
            "a JWK": {"k.json": json.dumps({
                "kty": "OKP", "crv": "Ed25519",
                "d": b64.urlsafe_b64encode(priv).decode().rstrip("="),
                "x": b64.urlsafe_b64encode(pub).decode().rstrip("=")})},
            "a PGP block": {"k.asc": "-----BEGIN PGP " + "PRIVATE KEY "
                            "BLOCK-----\n\nlQ\n"},
            "past 4 MB": {"big.txt": "x" * 4_000_001 + "\n" + priv.hex(),
                          **known},
            "under a folder named dist": {"fixtures/dist/a.txt": priv.hex(),
                                          **known},
            "a file named as a key": {"signing.key.txt": "x"},
            "a pack by another name": {"packs/acme/SKILL.md": "# pack",
                                       "packs/acme/manifest.json": json.dumps(
                                           {"rulebook_min": "0.1.0",
                                            "files": {}})},
        }
        for label, files in cases.items():
            with self.subTest(label=label):
                self.assertTrue(self.guard(files), label)
        # Nothing here is a key: digests, a public key alone, the sample
        # pack.
        self.assertEqual(self.guard({
            "a.txt": hashlib.sha256(b"x").hexdigest() + "\n" + pub.hex(),
            "b.txt": b64.b64encode(hashlib.sha512(b"y").digest()).decode(),
            "examples/pack-sample/pack.json": "{}",
            "examples/pack-sample/SKILL.md": "# sample"}), [])

    def test_the_spellings_the_second_review_found(self):
        """R4D-3: test vectors and encodings the guard read past."""
        import base64 as b64
        import gzip as gz
        from cryptography.hazmat.primitives import serialization
        priv, pub, h = self.priv, self.pub, self.priv.hex()
        known = {"a.pub": pub.hex()}
        der2 = self.key.private_bytes(serialization.Encoding.DER,
                                      serialization.PrivateFormat.PKCS8,
                                      serialization.NoEncryption())
        # Version 2 (RFC 8410's OneAsymmetricKey with the public key), as
        # BouncyCastle writes it.
        der2 = (bytes.fromhex("3051020101300506032b657004220420") + priv
                + bytes.fromhex("8121") + b"\x00" + pub)
        zipped = io.BytesIO()
        with zipfile.ZipFile(zipped, "w") as z:
            z.writestr("inner/seed.txt", h)
        wrapped = b64.b64encode(priv + pub).decode()
        cases = {
            "0x before each byte": {"k.txt": " ".join(
                f"0x{b:02x}" for b in priv), **known},
            "a C array": {"k.c": "static const uint8_t sk[32] = {"
                          + ", ".join(f"0x{b:02x}" for b in priv) + "};",
                          **known},
            "Python bytes escapes": {"k.py": "SK = b\"" + "".join(
                f"\\x{b:02x}" for b in priv[:16]) + "\"\\\n     b\"" + "".join(
                f"\\x{b:02x}" for b in priv[16:]) + "\"\n", **known},
            "adjacent string literals": {"k.py": f'SEED = ("{h[:32]}"\n'
                                         f'        "{h[32:]}")\n', **known},
            "a decimal byte list": {"v.json": json.dumps(
                {"sk": list(priv), "pk": list(pub)})},
            "commas and dashes": {"k.txt": "-".join(
                h[i:i + 2] for i in range(0, 64, 2)), **known},
            "inside a longer hex run": {"k.txt": "0a20" + h + "1234",
                                        **known},
            "at an odd digit of a run": {"k.txt": "a" + h + "b", **known},
            "base64 wrapped over lines": {"k.txt": wrapped[:40] + "\n"
                                          + wrapped[40:]},
            "PKCS#8 version 2": {"key.der": der2},
            "PKCS#8 version 2 in base64": {"k.txt": b64.b64encode(
                der2).decode()},
            "UTF-16 without a byte-order mark": {
                "k.txt": h.encode("utf-16-le"), **known},
            "UTF-32 without a byte-order mark": {
                "k.txt": h.encode("utf-32-le"), **known},
            "the key id only in a file name": {
                "a.txt": h, f"keys/{self.kid}.pub": "x"},
            "in a zip file": {"bundle.zip": zipped.getvalue(), **known},
            "in a gzip file": {"k.txt.gz": gz.compress(h.encode()),
                               **known},
        }
        for label, files in cases.items():
            with self.subTest(label=label):
                self.assertTrue(self.guard(files), label)

    def test_history_reads_every_name_and_refuses_a_shallow_clone(self):
        """R4D-4, R4D-5."""
        import repo_guard
        d = tmpdir(self)
        git = ["git", "-C", str(d), "-c", "user.name=t",
               "-c", "user.email=t@example.invalid", "-c",
               "commit.gpgsign=false"]
        if subprocess.run(git[:3] + ["init", "-q"]).returncode != 0:
            self.skipTest("git is not available")
        (d / "settings.json").write_text("{}")
        subprocess.run(git + ["add", "-A"], check=True)
        subprocess.run(git + ["commit", "-qm", "one"], check=True)
        (d / "packs" / "acme").mkdir(parents=True)
        (d / "packs" / "acme" / "pack.json").write_text("{}")   # same blob
        subprocess.run(git + ["add", "-A"], check=True)
        subprocess.run(git + ["commit", "-qm", "two"], check=True)
        subprocess.run(git + ["rm", "-rq", "packs"], check=True)
        subprocess.run(git + ["commit", "-qm", "three"], check=True)
        found = repo_guard.check_history(d)
        self.assertTrue(any(p.startswith("packs/acme/pack.json (in history)")
                            for p in found), found)
        shallow = tmpdir(self) / "s"
        subprocess.run(["git", "clone", "-q", "--depth", "1",
                        d.as_uri(), str(shallow)], check=True)
        with self.assertRaises(repo_guard.Shallow):
            repo_guard.check_history(shallow)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(repo_guard.main(["--history", str(shallow)]), 2)
        self.assertIn("shallow clone", err.getvalue())

    def test_what_the_third_review_found(self):
        """R4F-2, R4F-3, R4F-6: archives, more spellings, an ignored
        folder."""
        import base64 as b64
        import gzip as gz
        import repo_guard
        priv, pub = self.priv, self.pub
        known = {"a.pub": pub.hex()}
        spki = bytes.fromhex("302a300506032b6570032100") + pub

        def zipped(members, password=False):
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as z:
                for name, data in members.items():
                    z.writestr(name, data)
            raw = bytearray(buf.getvalue())
            if password:
                # Mark every member encrypted, as a password zip does.
                for sig in (b"PK\x03\x04", b"PK\x01\x02"):
                    at = raw.find(sig)
                    while at >= 0:
                        flag = at + (6 if sig == b"PK\x03\x04" else 8)
                        raw[flag] |= 1
                        at = raw.find(sig, at + 4)
            return bytes(raw)
        b64key = b64.b64encode(priv).decode()
        cases = {
            "a golden set inside a zip": {"data.zip": zipped(
                {"golden-set/labels.json": "{}"})},
            "a SKILL.md inside a zip": {"acme.zip": zipped(
                {"SKILL.md": "# pack"})},
            "an encrypted member": {"k.zip": zipped({"seed.txt": "x"},
                                                    password=True)},
            "a truncated gzip": {"s.gz": gz.compress(b"x" * 1000)[:20]},
            "repr() of bytes": {"t.py": f"SEED = {priv!r}\n", **known},
            "a Go byte slice": {"o.txt": "[" + " ".join(map(str, priv))
                                + "]", **known},
            "a Java signed array": {"o.txt": str([b - 256 if b > 127 else b
                                                  for b in priv]), **known},
            "Java (byte) casts": {"K.java": "byte[] k = {" + ", ".join(
                f"(byte) 0x{b:02x}" for b in priv) + "};", **known},
            "base64 over adjacent literals": {"t.py": (
                f'SEED = ("{b64key[:20]}"\n        "{b64key[20:]}")\n'),
                **known},
            "the public key only as a DER file": {"seed.txt": priv.hex(),
                                                  "pub.der": spki},
            "in a bzip2 file": {"s.bz2": __import__("bz2").compress(
                priv.hex().encode()), **known},
            "in an xz file": {"s.xz": __import__("lzma").compress(
                priv.hex().encode()), **known},
        }
        for label, files in cases.items():
            with self.subTest(label=label):
                self.assertTrue(self.guard(files), label)
        # A folder git ignores is read, not passed as clean (R4F-6).
        d = tmpdir(self)
        if subprocess.run(["git", "-C", str(d), "init", "-q"]).returncode:
            self.skipTest("git is not available")
        (d / ".gitignore").write_text("dist/\n")
        (d / "dist").mkdir()
        (d / "dist" / "keys.txt").write_text(priv.hex() + "\n" + pub.hex())
        self.assertTrue(repo_guard.check(d / "dist"))

    def test_no_line_makes_it_backtrack(self):
        """R4F-4: a crafted line took exponential time."""
        import time
        import repo_guard
        start = time.monotonic()
        repo_guard._values('bb" ' * 40 + "z")
        self.assertLess(time.monotonic() - start, 2)

    def test_history_reads_names_git_would_quote(self):
        """R4F-1: --history matched names git printed quoted."""
        import repo_guard
        d = tmpdir(self)
        git = ["git", "-C", str(d), "-c", "user.name=t",
               "-c", "user.email=t@example.invalid", "-c",
               "commit.gpgsign=false"]
        if subprocess.run(git[:3] + ["init", "-q"]).returncode != 0:
            self.skipTest("git is not available")
        (d / "x").write_text("x")
        try:
            (d / "packs" / "café").mkdir(parents=True)
            (d / "packs" / "café" / "pack.json").write_text('{"a": 1}')
            (d / "golden-sé").mkdir()
            (d / "golden-sé" / "l.json").write_text('{"b": 2}')
        except (OSError, UnicodeError):
            self.skipTest("this file system takes only ASCII names")
        subprocess.run(git + ["add", "-A"], check=True)
        subprocess.run(git + ["commit", "-qm", "one"], check=True)
        subprocess.run(git + ["rm", "-rq", "packs", "golden-sé"],
                       check=True)
        subprocess.run(git + ["commit", "-qm", "two"], check=True)
        found = " ".join(repo_guard.check_history(d))
        self.assertIn("packs/café/pack.json (in history)", found)
        self.assertIn("golden-sé/l.json (in history)", found)

    def test_a_distribution_is_read_whole(self):
        files = {"dist/a.txt": self.priv.hex(), "a.pub": self.pub.hex()}
        self.assertEqual(self.guard(files), [])        # a work tree's own
        self.assertTrue(self.guard(files, everything=True))

    def test_a_key_in_the_history(self):
        import repo_guard
        d = tmpdir(self)
        git = ["git", "-C", str(d), "-c", "user.name=t",
               "-c", "user.email=t@example.invalid", "-c",
               "commit.gpgsign=false"]
        if subprocess.run(git[:3] + ["init", "-q"]).returncode != 0:
            self.skipTest("git is not available")
        (d / "a.pub").write_text(self.pub.hex())
        (d / "seed.txt").write_text(self.priv.hex())
        subprocess.run(git + ["add", "-A"], check=True)
        subprocess.run(git + ["commit", "-qm", "one"], check=True)
        (d / "seed.txt").unlink()
        subprocess.run(git + ["add", "-A"], check=True)
        subprocess.run(git + ["commit", "-qm", "two"], check=True)
        self.assertEqual(repo_guard.check(d), [])
        found = repo_guard.check_history(d)
        self.assertTrue(any(p.startswith("seed.txt (in history):")
                            and self.kid in p for p in found), found)
        out = io.StringIO()
        with contextlib.redirect_stderr(out):
            self.assertEqual(repo_guard.main(["--history", str(d)]), 1)

    def test_the_history_of_this_repository(self):
        import repo_guard
        if not (ROOT / ".git").exists():
            self.skipTest("not a git checkout")
        try:
            self.assertEqual(repo_guard.check_history(ROOT), [])
        except subprocess.CalledProcessError as exc:
            self.skipTest(f"git cannot read the history here: {exc}")


class TestReviewOfR4GuardRound4(unittest.TestCase):
    """The review of the round-4 guard (R4H)."""

    setUp = TestReviewOfR4Guard.setUp
    guard = TestReviewOfR4Guard.guard

    def test_keys_listed_one_a_line(self):
        """R4H-1: base64 keys listed one a line are no wrapped value."""
        import base64 as b64
        from cryptography.hazmat.primitives.asymmetric import ed25519
        others = [ed25519.Ed25519PrivateKey.generate().private_bytes_raw()
                  for _ in range(3)]
        for at in range(3):
            keys = others[:at] + [self.priv] + others[at:]
            lines = [b64.b64encode(k).decode() for k in keys]
            for form in ("\n".join(lines),
                         "[\n" + ",\n".join(f'  "{x}"' for x in lines)
                         + "\n]\n",
                         "\n".join(b64.urlsafe_b64encode(k).decode()
                                   .rstrip("=") for k in keys)):
                with self.subTest(at=at, form=form[:12]):
                    self.assertTrue(self.guard({"keys.txt": form,
                                                "a.pub": self.pub.hex()}))
        # Two key pairs, one a line.
        pairs = "\n".join(b64.b64encode(k + ed25519.Ed25519PrivateKey
                                        .from_private_bytes(k).public_key()
                                        .public_bytes_raw()).decode()
                          for k in [*others, self.priv])
        self.assertTrue(self.guard({"pairs.txt": pairs}))

    def test_archives_the_round_found(self):
        """R4H-5, R4H-6, R4H-7, R4H-10."""
        def zipped(members: dict) -> bytes:
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as z:
                for name, data in members.items():
                    z.writestr(name, data)
            return buf.getvalue()

        def tarred(members: dict, mode="w") -> bytes:
            buf = io.BytesIO()
            with tarfile.open(fileobj=buf, mode=mode) as tf:
                for name, data in members.items():
                    info = tarfile.TarInfo(name)
                    info.size = len(data)
                    tf.addfile(info, io.BytesIO(data))
            return buf.getvalue()
        cases = {
            "backslashes": {"a.zip": zipped({
                "data\\golden-set\\labels.json": "{}"})},
            "a pack, backslashes": {"a.zip": zipped({
                "packs\\acme\\pack.json": "{}"})},
            "a plain tar": {"a.tar": tarred({"golden-set/x.json": b"{}"})},
            "a key named in a plain tar": {"a.tar": tarred({
                "keys/demo.key": b"x"})},
            "a seed in a plain tar": {"a.tar": tarred({"s.bin": self.priv}),
                                      "a.pub": self.pub.hex()},
            "tars end to end": {"a.tar.gz": __import__("gzip").compress(
                tarred({"a.txt": b"x"}) + tarred({"SKILL.md": b"# p"}))},
            "deeper than read": {"a.zip": zipped({"b.zip": zipped({
                "c.zip": zipped({"d.zip": zipped({"e.txt": "x"})})})})},
        }
        for label, files in cases.items():
            with self.subTest(label=label):
                self.assertTrue(self.guard(files), label)
        # A zip whose member uses a method Python cannot read: reported,
        # not a crash.
        raw = bytearray(zipped({"m.txt": "x" * 100}))
        for sig in (b"PK\x03\x04", b"PK\x01\x02"):
            at = raw.find(sig)
            off = 8 if sig == b"PK\x03\x04" else 10
            raw[at + off:at + off + 2] = (99).to_bytes(2, "little")
        problems = self.guard({"odd.zip": bytes(raw)})
        self.assertTrue(any("cannot be read" in p for p in problems),
                        problems)
        # Text that starts with BZh is text (R4H-10).
        self.assertEqual(self.guard({"notes.txt": "BZh is a prefix\n"}), [])

    def test_quiet_and_escaped(self):
        """R4H-8: no warning on an ordinary bytes literal; R4H-9: what it
        prints is escaped, and a name keeps its line breaks."""
        import repo_guard
        err = io.StringIO()
        d = tmpdir(self)
        (d / "rx.py").write_text("import re\nP = re.compile(b'\\d+')\n")
        with contextlib.redirect_stderr(err), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(repo_guard.main([str(d)]), 0)
        self.assertNotIn("Warning", err.getvalue())
        e = tmpdir(self)
        name = "innocent.txt\n::error file=README.md::all clear"
        try:
            (e / name).write_text(self.priv.hex())
        except OSError:
            self.skipTest("this file system refuses a line break in a name")
        (e / "a.pub").write_text(self.pub.hex())
        err = io.StringIO()
        with contextlib.redirect_stderr(err), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(repo_guard.main([str(e)]), 1)
        self.assertNotIn("\n::error", err.getvalue())
        self.assertIn("innocent.txt\\u000a::error", err.getvalue())
        # In the history, a name that starts with a line break keeps it.
        git = ["git", "-C", str(e), "-c", "user.name=t", "-c",
               "user.email=t@example.invalid", "-c", "commit.gpgsign=false"]
        if subprocess.run(git[:3] + ["init", "-q"]).returncode != 0:
            self.skipTest("git")
        os.remove(e / name)
        (e / "\nkeys.key").write_text("x")
        subprocess.run(git + ["add", "-A"], check=True)
        subprocess.run(git + ["commit", "-qm", "x"], check=True)
        problems = repo_guard.check_history(e)
        self.assertTrue(any(p.startswith("\nkeys.key (in history):")
                            for p in problems), problems)

    def test_more_spellings(self):
        """R4H-11."""
        priv, pub, h = self.priv, self.pub, self.priv.hex()
        known = {"a.pub": pub.hex()}
        pairs = [h[i:i + 2] for i in range(0, 64, 2)]
        xxd = "".join(f"{i * 16:08x}: " + " ".join(
            "".join(pairs[i * 16 + j:i * 16 + j + 2])
            for j in range(0, 16, 2)) + "  ................\n"
            for i in range(2))
        cases = {
            "a C array with comments": "".join(
                f"0x{b},  // byte {i}\n" for i, b in enumerate(pairs)),
            "Rust u8": ", ".join(f"0x{b}u8" for b in pairs),
            "Kotlin toByte": ", ".join(f"0x{b}.toByte()" for b in pairs),
            "decimals with semicolons": "; ".join(str(b) for b in priv),
            "pipes": "|".join(pairs),
            "URL-encoded": "".join(f"%{b}" for b in pairs),
            "JSON escapes": json.dumps({"s": priv.decode("latin-1")}),
            "xxd": xxd,
            "a Python int": str(int.from_bytes(priv, "big")),
            "a notebook": json.dumps({"cells": [{"outputs": [{"data": {
                "text/plain": [repr(priv)]}}]}]}),
            "octal": '"' + "".join(f"\\{b:03o}" for b in priv) + '"',
        }
        for label, text in cases.items():
            with self.subTest(label=label):
                self.assertTrue(self.guard({"k.txt": text, **known}), label)

    def test_ignored_files_are_counted(self):
        """R4H-14: files git ignores are not read, and the guard says how
        many there are."""
        import repo_guard
        d = tmpdir(self)
        if subprocess.run(["git", "-C", str(d), "init", "-q"]).returncode:
            self.skipTest("git")
        (d / ".gitignore").write_text("out/\n")
        (d / "out").mkdir()
        (d / "out" / "k.txt").write_text(self.priv.hex())
        err, out = io.StringIO(), io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
            self.assertEqual(repo_guard.main([str(d)]), 0)
        self.assertIn("1 file(s) here are ignored by git", err.getvalue())


class TestReviewOfR4GuardRound5(unittest.TestCase):
    """The review of the round-5 guard and release (R4J)."""

    setUp = TestReviewOfR4Guard.setUp
    guard = TestReviewOfR4Guard.guard

    def test_a_key_files_text_encoded(self):
        """R4J-1: a key file (64 hex digits) in base64, as a Kubernetes
        secret holds it, or dumped with xxd; R4J-2: \\u00 escapes."""
        import base64 as b64
        keyfile = (self.priv.hex() + "\n").encode()
        enc = b64.b64encode(keyfile).decode()
        dump = "".join(
            f"{i:08x}: " + " ".join(keyfile[i + j:i + j + 2].hex()
                                    for j in range(0, 16, 2))
            + "  ................\n" for i in range(0, len(keyfile), 16))
        latin = self.priv.decode("latin-1")
        escaped = "".join(f"\\u{ord(c):04x}" if not 32 <= ord(c) < 127
                          or c in "\\\"" else c for c in latin)
        known = {"a.pub": self.pub.hex()}
        for label, files in {
                "a secret": {"secret.yaml": "data:\n  demo.key: " + enc},
                "an env file": {".env.example": "KEY=" + enc},
                "xxd of the key file": {"KEY.md": "```\n" + dump + "```\n"},
                "Java": {"K.java": f'String K = "{escaped}";'},
                "YAML": {"k.yaml": f'k: "{escaped}"'}}.items():
            with self.subTest(label=label):
                self.assertTrue(self.guard({**files, **known}), label)

    def test_archives_of_round_5(self):
        """R4J-3: a stream that starts with a block of zeros; R4J-6: four
        bytes of a zip's end record by chance; R4J-7: a tar member larger
        than the guard reads; R4J-8: a tar of the first format."""
        import gzip as gz
        problems = self.guard({"dump.bin.gz": gz.compress(
            bytes(512) + self.priv.hex().encode()), "a.pub": self.pub.hex()})
        self.assertTrue(problems)
        png = b"\x89PNG\r\n\x1a\n" + bytes(100) + b"PK\x05\x06" + bytes(40)
        self.assertEqual(self.guard({"logo.png": png}), [])
        # A member whose header says 70 MiB (as a sparse file's says its
        # whole size) in a tar of a few KiB.
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w",
                          format=tarfile.USTAR_FORMAT) as tf:
            info = tarfile.TarInfo("big.bin")
            info.size = 0
            tf.addfile(info, io.BytesIO(b""))
        big = bytearray(buf.getvalue())
        big[124:136] = f"{70 * 2**20:011o}\0".encode()
        big[148:156] = b"        "
        big[148:155] = f"{sum(big[:512]):06o}\0".encode()
        problems = self.guard({"data.tar": bytes(big)})
        self.assertTrue(any("big.bin" in p for p in problems), problems)
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w",
                          format=tarfile.USTAR_FORMAT) as tf:
            info = tarfile.TarInfo("data/golden-set/x.json")
            info.size = 2
            tf.addfile(info, io.BytesIO(b"{}"))
        v7 = bytearray(buf.getvalue())
        v7[257:265] = bytes(8)                  # no "ustar" mark
        v7[148:156] = b"        "
        v7[148:155] = f"{sum(v7[:512]):06o}\0".encode()
        self.assertTrue(self.guard({"a.tar": bytes(v7)}))

    def test_the_users_git_settings(self):
        """R4J-4: --history reads the same whatever the user's git config
        (a signature printed into the log, the root commit left out)."""
        import repo_guard
        d = tmpdir(self)
        git = ["git", "-C", str(d), "-c", "user.name=t", "-c",
               "user.email=t@example.invalid", "-c", "commit.gpgsign=false"]
        if subprocess.run(git[:3] + ["init", "-q"]).returncode:
            self.skipTest("git")
        (d / "pack.json").write_text("{}")
        subprocess.run(git + ["add", "-A"], check=True)
        subprocess.run(git + ["commit", "-qm", "x"], check=True)
        cfg = d.parent / (d.name + "-gitconfig")
        cfg.write_text("[log]\n\tshowRoot = false\n[color]\n\tui = always\n")
        self.addCleanup(cfg.unlink)
        with mock.patch.dict(os.environ, {"GIT_CONFIG_GLOBAL": str(cfg)}):
            problems = repo_guard.check_history(d)
        self.assertTrue(any(p.startswith("pack.json (in history)")
                            for p in problems), problems)

    def test_more_spellings_of_round_5(self):
        """R4J-9: Rust's _u8, a big integer with separators or a suffix,
        an indented dump; and a Java (byte) list, an octal string split."""
        priv, pub = self.priv, self.pub
        pairs = [priv.hex()[i:i + 2] for i in range(0, 64, 2)]
        n = int.from_bytes(priv, "big")
        grouped = f"{n:_}"
        xxd = "".join("    " + f"{i * 16:08x}: " + " ".join(
            "".join(pairs[i * 16 + j:i * 16 + j + 2]) for j in range(0, 16, 2))
            + "  ................\n" for i in range(2))
        octal = "".join(f"\\{b:03o}" for b in priv)
        cases = {
            "Rust _u8": ", ".join(f"0x{b}_u8" for b in pairs),
            "Rust dec _u8": ", ".join(f"{b}_u8" for b in priv),
            "BigInt": f"const K = {n}n;",
            "digit groups": f"K = {grouped}",
            "an indented dump": xxd,
            "Java (byte) decimals": ", ".join(f"(byte) {b}" for b in priv),
            "an octal string split": f'char k[] = "{octal[:64]}"\n  "{octal[64:]}";',
        }
        for label, text in cases.items():
            with self.subTest(label=label):
                self.assertTrue(self.guard({"k.txt": text,
                                            "a.pub": pub.hex()}), label)

    def test_pypi_simple_index(self):
        """R4J-11: PyPI's versions from its simple index as JSON (PEP
        691), a yanked file aside."""
        import release_tags as RT
        doc = {"files": [
            {"filename": "bellbriar_harness-1.0.0-py3-none-any.whl"},
            {"filename": "bellbriar_harness-1.1.0.tar.gz", "yanked": False},
            {"filename": "bellbriar_harness-1.2.0-py3-none-any.whl",
             "yanked": "broken"}]}
        self.assertEqual(RT.pypi_versions(doc), ["v1.0.0", "v1.1.0"])
        wf = (ROOT / ".github" / "workflows" / "release.yml").read_text()
        self.assertIn("application/vnd.pypi.simple.v1+json", wf)


class TestPolicies(unittest.TestCase):
    """H3."""

    def test_the_files(self):
        security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
        self.assertIn("Report a vulnerability", security)
        self.assertIn("--require-sandbox", security)
        contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
        self.assertIn("git commit -s", contributing)
        self.assertIn("developercertificate.org", contributing)
        self.assertIn("tools/repo_guard.py", contributing)
        # R4H-4: a branch whose commits were re-signed is pushed again.
        self.assertIn("git push --force-with-lease", contributing)
        self.assertIn("git remote add -f upstream", contributing)
        # R4H-3, R4J-5: the rehearsal's steps, item 13 first.
        prepublish = (ROOT / "PREPUBLISH.md").read_text(encoding="utf-8")
        item15 = prepublish[prepublish.index("15. **Rehearse"):]
        for step in ("make_canonicalization_vectors.py", "__version__",
                     "STATUS_PHRASES", "Item 13 is done", "1.0.0rc1"):
            self.assertIn(step, item15)
        owners = (ROOT / ".github" / "CODEOWNERS").read_text(encoding="utf-8")
        self.assertRegex(owners, r"(?m)^\* @\S+")
        dco = _yaml(ROOT / ".github" / "dco.yml")
        self.assertTrue(dco["require"]["members"])


# ---------------------------------------------------------------------------
# A11 and the CI matrix
# ---------------------------------------------------------------------------

def _yaml(path: Path) -> dict:
    try:
        import yaml
    except ImportError:
        raise unittest.SkipTest("PyYAML is not installed")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class TestWorkflows(unittest.TestCase):

    def test_the_test_matrix(self):
        wf = _yaml(ROOT / ".github" / "workflows" / "bellbriar-eval.yml")
        matrix = wf["jobs"]["test"]["strategy"]["matrix"]
        # Not Windows, where the commands stop (L141).
        self.assertEqual(set(matrix["os"]), {"ubuntu-latest", "macos-latest"})
        self.assertEqual(matrix["python-version"],
                         ["3.11", "3.12", "3.13", "3.14"])
        self.assertIn({"os": "macos-15-intel", "python-version": "3.13"},
                      matrix["include"])
        steps = json.dumps(wf["jobs"]["test"]["steps"])
        self.assertIn("BELLBRIAR_REQUIRE_ALL_TESTS", steps)
        self.assertIn("playwright install --with-deps chromium", steps)
        self.assertIn("tools/repo_guard.py", json.dumps(wf["jobs"]["guard"]))
        self.assertIn("tools/check_dist.py", json.dumps(wf["jobs"]["dist"]))
        # R4A-12: the guard reads every commit.
        guard = json.dumps(wf["jobs"]["guard"])
        self.assertIn("repo_guard.py --history", guard)
        self.assertIn('"fetch-depth": 0', guard)
        # R4A-1: the suite runs whole, and strict, from the sdist.
        dist = json.dumps(wf["jobs"]["dist"])
        self.assertIn("BELLBRIAR_REQUIRE_ALL_TESTS", dist)
        self.assertNotIn("tail -n", dist)
        # R4A-4: the image the release ships is built and run on the
        # fixtures on every change.
        self.assertIn("tools/image_check.py", json.dumps(wf["jobs"]["image"]))

    def test_the_release(self):
        wf = _yaml(ROOT / ".github" / "workflows" / "release.yml")
        on = wf.get("on", wf.get(True))
        self.assertEqual(on, {"push": {"tags": ["v*"]}})
        self.assertEqual(wf["permissions"], {"contents": "read"})
        jobs = wf["jobs"]
        pypi = jobs["pypi"]
        # contents: read for the checkout of tools/pypi_files.py (SB-2).
        self.assertEqual(pypi["permissions"],
                         {"contents": "read", "id-token": "write"})
        self.assertEqual(pypi["environment"]["name"], "pypi")
        self.assertIn("pypa/gh-action-pypi-publish@", json.dumps(pypi["steps"]))
        # Only the publishing job may mint an identity token.
        others = [n for n, j in jobs.items() if n != "pypi"
                  and "id-token" in json.dumps(j.get("permissions", {}))]
        self.assertEqual(others, [])
        # R4A-5, R4A-6: the whole suite, and the image built and run, before
        # PyPI, which cannot be undone.
        self.assertEqual(jobs["tests"]["uses"],
                         "./.github/workflows/bellbriar-eval.yml")
        self.assertEqual(set(pypi["needs"]),
                         {"tests", "build", "smoke", "image-test"})
        self.assertIn("tools/image_check.py",
                      json.dumps(jobs["image-test"]["steps"]))
        self.assertIn("tools/check_dist.py", json.dumps(jobs["build"]))
        build = json.dumps(jobs["build"]["steps"])
        self.assertIn("merge-base --is-ancestor", build)
        self.assertIn("tools/release_notes.py", build)
        self.assertEqual(jobs["image"]["permissions"]["packages"], "write")
        self.assertEqual(set(jobs["image"]["needs"]), {"build", "pypi"})
        image = json.dumps(jobs["image"]["steps"])
        self.assertIn("linux/amd64,linux/arm64", image)             # R4A-11
        # R4D-6: the image holds software under many licenses.
        self.assertIn("org.opencontainers.image.licenses=NOASSERTION", image)
        # R4D-2: both architectures build before PyPI; the version tag
        # alone is pushed, and the floating tags follow the run of the
        # pushed image (R4A-13).
        self.assertIn("linux/amd64,linux/arm64",
                      json.dumps(jobs["image-test"]["steps"]))
        self.assertIn("ghcr.io/bellbriar/harness:${{ needs.build.outputs."
                      "version }}", image)
        self.assertEqual(set(jobs["tags"]["needs"]),
                         {"build", "image", "public"})
        self.assertIn("tools/release_tags.py",
                      json.dumps(jobs["tags"]["steps"]))
        # R4F-11: floating tags from published releases, not every v* tag:
        # every GitHub release, and PyPI's versions (R4H-2), one run at a
        # time.
        tags = json.dumps(jobs["tags"]["steps"])
        self.assertIn("gh api --paginate", tags)
        self.assertIn("--released released.txt --pypi pypi.json", tags)
        self.assertEqual(wf["concurrency"], {"group": "release",
                                             "cancel-in-progress": False})
        # R4H-12: the published image's labels and annotations are read
        # before PyPI too.
        meta = [[s for s in jobs[j]["steps"] if s.get("id") == "meta"]
                for j in ("image-test", "image")]
        self.assertEqual(meta[0], meta[1])
        self.assertTrue(meta[0])
        self.assertIn("steps.meta.outputs.annotations",
                      json.dumps(jobs["image-test"]["steps"]))
        # R4F-8: the version label is the release's, on the index too.
        self.assertIn("org.opencontainers.image.version=${{ needs.build."
                      "outputs.version }}", image)
        self.assertIn("steps.meta.outputs.annotations", image)
        self.assertIn("imagetools create", json.dumps(jobs["tags"]["steps"]))
        # R4D-1: a version the image steps would refuse is refused first.
        self.assertIn("release_tags.py --check", build)
        # R4D-9: a re-run after a partial upload.
        self.assertIn('"skip-existing": true', json.dumps(pypi["steps"]))
        # R4A-3: pulled back with no credentials before the release.
        self.assertIn("--pull", json.dumps(jobs["public"]["steps"]))
        self.assertTrue({"public", "tags"} <= set(jobs["release"]["needs"]))
        release = json.dumps(jobs["release"]["steps"])
        self.assertIn("--notes-file", release)
        self.assertIn("--latest=false", release)                    # R4D-8
        self.assertIn("DIGEST", release)                            # R4D-7
        text = (ROOT / ".github" / "workflows" / "release.yml").read_text()
        self.assertNotIn("password: ${{ secrets.PYPI", text)
        self.assertNotIn("CHANGELOG.md. PyPI", text)
        # The test workflow can be called, and a tag push does not run it a
        # second time.
        tests = _yaml(ROOT / ".github" / "workflows" / "bellbriar-eval.yml")
        on = tests.get("on", tests.get(True))
        self.assertIn("workflow_call", on)
        self.assertEqual(on["push"], {"branches": ["**"]})

    def test_every_job_has_a_time_limit(self):
        """R4F-4: a job that hangs (a crafted line for the guard, a stuck
        browser) stops at its limit, not at GitHub's six hours. A job that
        calls another workflow takes the limits of that one's jobs."""
        for name in ("bellbriar-eval.yml", "release.yml"):
            wf = _yaml(ROOT / ".github" / "workflows" / name)
            for job_name, job in wf["jobs"].items():
                with self.subTest(workflow=name, job=job_name):
                    if "uses" in job:
                        continue
                    self.assertIsInstance(job.get("timeout-minutes"), int)
                    self.assertLessEqual(job["timeout-minutes"], 60)

    def test_every_action_is_pinned_to_a_commit(self):
        """R4A-7: a tag or a branch can be moved under a job that holds
        an identity token or a package write."""
        import re
        texts = {p: p.read_text(encoding="utf-8") for p in [
            *(ROOT / ".github" / "workflows").glob("*.yml"),
            ROOT / "examples" / "ci" / "bellbriar-eval.yml",
            ROOT / "action" / "README.md"]}
        seen = 0
        for path, text in texts.items():
            for m in re.finditer(r"uses: ([^\s#]+)(?:\s*#\s*(\S+))?", text):
                ref, comment = m.group(1), m.group(2)
                if ref.startswith("./") or ref.startswith(
                        "bellbriar/eval-action@"):
                    continue
                seen += 1
                with self.subTest(path=path.name, ref=ref):
                    self.assertRegex(ref, r"@[0-9a-f]{40}$")
                    self.assertRegex(comment or "", r"^v\d+\.\d+\.\d+$")
        self.assertGreater(seen, 20)
        dependabot = _yaml(ROOT / ".github" / "dependabot.yml")
        self.assertEqual({u["package-ecosystem"] for u in
                          dependabot["updates"]},
                         {"github-actions", "docker", "pip"})

    def test_the_release_helpers(self):
        """R4A-13: floating tags follow the newest release they cover;
        R4A-14: no release without its notes."""
        import release_notes as RN
        import release_tags as RT
        img = "ghcr.io/x/y"
        releases = [(1, 0, 0), (1, 1, 0)]
        self.assertEqual(RT.tags_for("1.0.5", img, releases),
                         [f"{img}:1.0.5", f"{img}:1.0"])
        self.assertEqual(RT.tags_for("1.1.1", img, releases),
                         [f"{img}:1.1.1", f"{img}:1.1", f"{img}:1",
                          f"{img}:latest"])
        self.assertEqual(RT.tags_for("2.0.0rc1", img, releases),
                         [f"{img}:2.0.0rc1"])
        # R4F-11: the releases a file lists.
        d = tmpdir(self)
        (d / "rel.txt").write_text("v1.0.0\nv1.1.0\n")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(RT.main(["1.0.5", img, "--released",
                                      str(d / "rel.txt")]), 0)
        self.assertEqual(out.getvalue(), f"floating={img}:1.0\nlatest=false\n")
        # R4H-2: a version on PyPI is released, its GitHub release or not;
        # a yanked one is not.
        (d / "pypi.json").write_text(json.dumps({"releases": {
            "1.0.0": [{"yanked": False}], "1.1.0": [{"yanked": False}],
            "1.2.0": [{"yanked": True}], "1.3.0": []}}))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(RT.main(["1.1.1", img, "--released",
                                      str(d / "rel.txt"), "--pypi",
                                      str(d / "pypi.json")]), 0)
        self.assertEqual(out.getvalue(), f"floating={img}:1.1,{img}:1,"
                         f"{img}:latest\nlatest=true\n")
        (d / "rel.txt").write_text("v1.0.0\n")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            RT.main(["1.0.5", img, "--released", str(d / "rel.txt"),
                     "--pypi", str(d / "pypi.json")])
        self.assertEqual(out.getvalue(), f"floating={img}:1.0\nlatest=false\n")
        # R4D-1: what --check refuses before PyPI.
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            for v in ("1.0.0.post1", "1.1.0.dev1", "1.2", "v1.0.0"):
                self.assertEqual(RT.main(["--check", v]), 2, v)
        for v in ("1.0.0", "1.1.0rc1", "2.0.0b3"):
            self.assertEqual(RT.main(["--check", v]), 0, v)
        self.assertEqual(RT.released(["v1.0.0", "v1.1.0rc1", "x", "v2"]),
                         [(1, 0, 0)])
        with self.assertRaises(ValueError):
            RT.tags_for("1.0", img, releases)
        log = ("# Changelog\n\n## 1.1.0 — 2026-11-02\n\n- A fix.\n\n"
               "## 1.0.0 — 2026-10-30\n\nThe first.\n")
        self.assertEqual(RN.notes(log, "1.1.0"),
                         "## 1.1.0 — 2026-11-02\n\n- A fix.\n")
        self.assertEqual(RN.notes(log, "1.0.0"),
                         "## 1.0.0 — 2026-10-30\n\nThe first.\n")
        for version, text in (("1.2.0", log),
                              ("1.0.0", "## 1.0.0 — unreleased\n"),
                              # R4D-12: another version's section.
                              ("1.0.0", "## 1.0.0-beta.1 — x\n\nBeta.\n")):
            with self.assertRaises(ValueError):
                RN.notes(text, version)
        self.assertEqual(RN.notes("## [1.0.0] - 2026-10-30\n\nOne.\n",
                                  "1.0.0"),
                         "## [1.0.0] - 2026-10-30\n\nOne.\n")
        # This checkout's CHANGELOG.md has its section for the next version.
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn("## 1.0.0", changelog)

    def test_the_image(self):
        docker = (ROOT / "docker" / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("USER pwuser", docker)
        self.assertIn('ENTRYPOINT ["bellbriar-eval"]', docker)
        import re
        base = re.search(r"^FROM mcr\.microsoft\.com/playwright/python:"
                         r"v(\d+\.\d+\.\d+)-noble(@sha256:[0-9a-f]{64})?$",
                         docker, re.M)
        self.assertIsNotNone(base, "the base image is Playwright's")
        pins = dict(line.split("==") for line in (
            ROOT / "docker" / "requirements.txt").read_text(
                encoding="utf-8").splitlines()
            if line and not line.startswith("#"))
        # The Playwright package is the base image's, whose browsers it
        # holds (R4A-4).
        self.assertEqual(pins["playwright"], base.group(1))
        self.assertIn("--constraint /tmp/requirements.txt", docker)
        for name in ("beautifulsoup4", "justhtml", "cryptography",
                     "soupsieve"):
            self.assertIn(name, pins)
        ignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
        self.assertIn("!dist/*.whl", ignore)
        self.assertIn("!docker/requirements.txt", ignore)

    def test_the_action(self):
        action = _yaml(ROOT / "action" / "action.yml")
        self.assertEqual(action["runs"]["using"], "composite")
        step = action["runs"]["steps"][0]
        self.assertEqual(step["shell"], "bash")
        # Inputs reach the script through the environment only, never
        # pasted into it (script injection).
        self.assertNotIn("${{", step["run"])
        self.assertEqual(set(step["env"]), {"BB_ARGS", "BB_VERSION",
                                            "BB_PASS_ENV"})

    @unittest.skipUnless(shutil.which("bash"), "bash")
    def test_the_actions_arguments_are_never_a_shell(self):
        d = tmpdir(self)
        (d / "bin").mkdir()
        fake = d / "bin" / "docker"
        fake.write_text('#!/usr/bin/env bash\nfor a in "$@"; do '
                        'printf "[%s]\\n" "$a"; done\n')
        fake.chmod(0o755)
        script = _yaml(ROOT / "action" / "action.yml")["runs"]["steps"][0][
            "run"]

        def act(args, version="1", pass_env=""):
            env = {**os.environ, "PATH": f"{d / 'bin'}{os.pathsep}"
                   f"{os.environ.get('PATH', '')}", "RUNNER_OS": "Linux",
                   "GITHUB_WORKSPACE": str(d), "BB_ARGS": args,
                   "BB_VERSION": version, "BB_PASS_ENV": pass_env}
            return subprocess.run(["bash", "-c", script], env=env, cwd=d,
                                  capture_output=True, text=True)
        out = act("dist --render $(touch PWNED) *")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("[ghcr.io/bellbriar/harness:1]\n[dist]\n[--render]\n"
                      "[$(touch]\n[PWNED)]\n[*]", out.stdout)
        self.assertFalse((d / "PWNED").exists())
        out = act("my dist\n--html\nr e.html")
        self.assertIn("[my dist]\n[--html]\n[r e.html]", out.stdout)
        self.assertEqual(act("x", version="1;rm -rf /").returncode, 2)
        self.assertEqual(act("x", pass_env="A=b").returncode, 2)
        # R4A-10: no arguments is not a pass.
        for empty in ("", "  ", "\n\n", " \r\n"):
            out = act(empty)
            self.assertEqual(out.returncode, 2, repr(empty))
            self.assertIn("args is empty", out.stdout + out.stderr)
            self.assertNotIn("ghcr.io", out.stdout)
        # R4A-18: a folded `args: >` is one line, split at spaces; a line's
        # trailing spaces and carriage return are dropped.
        out = act("dist --render --fail-on tier1\n")
        self.assertIn("[dist]\n[--render]\n[--fail-on]\n[tier1]",
                      out.stdout)
        out = act("dist \r\n--html  \r\nr e.html\r\n")
        self.assertIn("[dist]\n[--html]\n[r e.html]\n", out.stdout)
        # R4A-13: an image pinned by digest, pulled when missing; a version
        # asks the registry each time.
        digest = "sha256:" + "a" * 64
        out = act("dist", version=digest)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn(f"[ghcr.io/bellbriar/harness@{digest}]", out.stdout)
        self.assertIn("[--pull]\n[missing]", out.stdout)
        self.assertIn("[--pull]\n[always]", act("dist").stdout)
        self.assertEqual(act("dist", version="sha256:xyz").returncode, 2)

    def test_the_customer_template(self):
        wf = _yaml(ROOT / "examples" / "ci" / "bellbriar-eval.yml")
        steps = json.dumps(wf["jobs"]["eval"]["steps"])
        self.assertIn("bellbriar/eval-action@v1", steps)
        self.assertNotIn(">=0.4", steps)


class TestReadme(unittest.TestCase):
    """H7 and N20."""

    def test_it_leads_with_the_install_paths(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        heads = [ln for ln in text.splitlines() if ln.startswith("## ")]
        self.assertEqual(heads[:4], ["## Install", "## Quickstart",
                                     "## What it checks, and what it does not",
                                     "## What this is not"])
        install = text.split("## Install", 1)[1].split("## Quickstart")[0]
        for needle in ("bellbriar/eval-action@v1", "pipx install",
                       "uv tool install", "ghcr.io/bellbriar/harness",
                       "--install-browser"):
            self.assertIn(needle, install)
        self.assertNotIn("pip install .", text)
        self.assertIn("Lighthouse", text.split("## What this is not")[0])


# ---------------------------------------------------------------------------
# A9: SARIF
# ---------------------------------------------------------------------------

class TestSarif(unittest.TestCase):

    def sarif(self, *paths) -> dict:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(io.StringIO()):
            L.main([*map(str, paths), "--format", "sarif",
                    "--fail-on", "never"])
        return json.loads(out.getvalue())

    def test_a_sarif_run(self):
        here = os.getcwd()
        os.chdir(ROOT)
        try:
            doc = self.sarif("fixtures/lint-bad.jsx")
        finally:
            os.chdir(here)
        self.assertEqual(doc["version"], "2.1.0")
        self.assertEqual(doc["$schema"], L.SARIF_SCHEMA)
        run_ = doc["runs"][0]
        driver = run_["tool"]["driver"]
        self.assertEqual(driver["name"], "bellbriar-lint")
        ids = [r["id"] for r in driver["rules"]]
        self.assertTrue(run_["results"])
        for res in run_["results"]:
            self.assertEqual(ids[res["ruleIndex"]], res["ruleId"])
            self.assertIn(res["level"], ("error", "warning"))
            loc = res["locations"][0]["physicalLocation"]
            self.assertEqual(loc["artifactLocation"]["uri"],
                             "fixtures/lint-bad.jsx")
            self.assertGreaterEqual(loc["region"]["startLine"], 1)
            self.assertTrue(res["message"]["text"])

    def test_every_rule_is_described(self):
        import re
        source = (ROOT / "src" / "bellbriar_harness" / "lint.py").read_text(
            encoding="utf-8")
        emitted = set(re.findall(r'"(bl-[a-z0-9-]+)"', source))
        self.assertEqual(emitted - set(L.LINT_RULES), set())

    def test_what_the_review_found(self):
        """R4B-9: a file name that is not UTF-8 crashed the SARIF output;
        R4B-10: a file the linter could not read was a result, and the run
        said it succeeded."""
        d = tmpdir(self)
        try:
            (Path(os.fsdecode(bytes(d / "src") + b"/lat\xe9.jsx"))
             .parent.mkdir())
            Path(os.fsdecode(bytes(d / "src") + b"/lat\xe9.jsx")).write_text(
                "<div onClick={go}>x</div>\n")
        except (OSError, UnicodeError, TypeError, ValueError):
            self.skipTest("this file system takes only UTF-8 names")
        here = os.getcwd()
        os.chdir(d)
        try:
            doc = self.sarif("src")
        finally:
            os.chdir(here)
        run_ = doc["runs"][0]
        self.assertEqual(run_["results"][0]["locations"][0][
            "physicalLocation"]["artifactLocation"]["uri"], "src/lat%E9.jsx")
        self.assertTrue(run_["invocations"][0]["executionSuccessful"])
        with mock.patch.object(L, "lint_text",
                               side_effect=OSError(5, "Input/output error")):
            doc = self.sarif(FIXTURES / "lint-good.jsx")
        run_ = doc["runs"][0]
        self.assertEqual(run_["results"], [])
        inv = run_["invocations"][0]
        self.assertIs(inv["executionSuccessful"], False)
        [note] = [n for n in inv["toolExecutionNotifications"]
                  if n["level"] == "error"]
        self.assertIn("could not lint this file", note["message"]["text"])
        self.assertTrue(note["locations"][0]["physicalLocation"][
            "artifactLocation"]["uri"].endswith("lint-good.jsx"))

    def test_a_path_outside_the_scan_folder_is_a_file_uri(self):
        d = tmpdir(self)
        (d / "a.jsx").write_text("<div onClick={go}>x</div>\n")
        doc = self.sarif(d / "a.jsx")
        uri = doc["runs"][0]["results"][0]["locations"][0][
            "physicalLocation"]["artifactLocation"]["uri"]
        self.assertTrue(uri.startswith("file:") or not uri.startswith("/"),
                        uri)


# ---------------------------------------------------------------------------
# A10: --baseline
# ---------------------------------------------------------------------------

class TestBaseline(unittest.TestCase):

    def setUp(self):
        self.d = tmpdir(self)
        self.page = self.d / "site" / "index.html"
        self.page.parent.mkdir()
        self.page.write_text(PAGE.format('<img src="a.png"><a href="/x"></a>'),
                             encoding="utf-8")
        code, _out, err = run(self.page.parent, "--json", self.d / "base.json",
                              "--fail-on", "never")
        self.assertEqual(code, 0, err)

    def gate(self, *extra):
        return run(self.page.parent, "--baseline", self.d / "base.json",
                   "--fail-on", "tier1", "--json", self.d / "r.json",
                   "--html", self.d / "r.html", *extra)

    def test_known_failures_pass_and_new_ones_fail(self):
        code, out, err = self.gate()
        self.assertEqual(code, 0, err)
        self.assertIn("0 of this run's", out)
        report = json.loads((self.d / "r.json").read_text())
        self.assertEqual(report["baseline"]["new_findings"], 0)
        self.assertTrue(all(f["in_baseline"] is True
                            for p in report["pages"] for f in p["findings"]))
        # Every finding is still listed and counted.
        self.assertGreater(report["site"]["total_fail_findings"], 0)
        # A new failure fails the gate.
        self.page.write_text(PAGE.format('<img src="a.png"><a href="/x"></a>'
                                         '<button></button>'),
                             encoding="utf-8")
        code, out, err = self.gate("--bundle", self.d / "b.json")
        self.assertEqual(code, 1, err)
        report = json.loads((self.d / "r.json").read_text())
        new = [f["rule_id"] for p in report["pages"] for f in p["findings"]
               if f["in_baseline"] is False]
        self.assertEqual(new, ["bb-button-name"])
        self.assertEqual(report["baseline"]["new_fail_findings"], 1)
        self.assertEqual(report["baseline"]["sha256"], hashlib.sha256(
            (self.d / "base.json").read_bytes()).hexdigest())
        bundle = json.loads((self.d / "b.json").read_text())
        self.assertEqual(bundle["baseline"], report["baseline"] | {
            "generated_at": report["baseline"]["generated_at"]})
        html = (self.d / "r.html").read_text()
        self.assertIn("Compared with a baseline.", html)
        self.assertIn("FAIL · new", html)

    def test_the_report_with_a_baseline_fits_its_schema(self):
        from tests.test_part_r3 import SCHEMA, validate
        self.gate()
        report = json.loads((self.d / "r.json").read_text())
        self.assertEqual(validate(report, SCHEMA), [])
        code, _out, _err = run(self.page.parent, "--json", self.d / "n.json",
                               "--fail-on", "never")
        plain = json.loads((self.d / "n.json").read_text())
        self.assertIsNone(plain["baseline"])
        self.assertTrue(all(f["in_baseline"] is None for p in plain["pages"]
                            for f in p["findings"]))
        self.assertEqual(validate(plain, SCHEMA), [])

    def test_a_baseline_it_cannot_use(self):
        for name, content, said in (
                ("x.json", "not json", "not a JSON file"),
                ("y.json", '{"format": "bellbriar-evidence/1"}',
                 "not a bellbriar-report/1 report"),
                ("z.json", json.dumps({"format": "bellbriar-report/1",
                                       "pages": [{"path": "a", "findings":
                                                  [{"rule_id": "r"}]}]}),
                 "no fingerprint")):
            with self.subTest(name=name):
                (self.d / name).write_text(content, encoding="utf-8")
                code, _out, err = run(self.page.parent, "--baseline",
                                      self.d / name)
                self.assertEqual(code, 2)
                self.assertIn(said, err)
        code, _out, err = run(self.page.parent, "--baseline",
                              self.d / "missing.json")
        self.assertEqual(code, 2)

    def test_a_baseline_of_other_pages_is_said_to_be(self):
        moved = self.d / "renamed"
        shutil.copytree(self.page.parent, moved)
        code, _out, err = run(moved, "--baseline", self.d / "base.json",
                              "--fail-on", "tier1")
        self.assertEqual(code, 1)
        self.assertIn("none of this run's findings is in the baseline", err)

    def test_strict_counts_only_new_reviews(self):
        self.page.write_text(PAGE.format('<a href="/a">Shop</a><a href="/a">'
                                         'Shop</a>'), encoding="utf-8")
        run(self.page.parent, "--json", self.d / "base.json", "--fail-on",
            "never")
        code, _out, err = self.gate("--strict")
        self.assertEqual(code, 0, err)
        code, _out, err = run(self.page.parent, "--fail-on", "tier1",
                              "--strict")
        self.assertEqual(code, 1, err)

    def test_the_counts(self):
        baseline = BL.load(str(self.d / "base.json"))
        rulebook = load_rulebook()
        page = run_page(self.page.read_bytes(), "site/index.html", rulebook)
        from bellbriar_harness.report import baseline_counts
        self.assertEqual(baseline_counts([page], rulebook, baseline), (0, 0))
        record = BL.record(baseline, 2, 1)
        self.assertEqual(set(record), {"sha256", "generated_at", "findings",
                                       "new_findings", "new_fail_findings"})
        self.assertIsNone(BL.record(None, 0, 0))


NAV = ('<!doctype html><html lang="en"><head><title>Home</title></head>'
       '<body><nav><a href="/a">Alpha</a> <a href="/b">Beta</a> '
       '<a href="/c">Gamma</a></nav>{}</body></html>')


class TestReviewOfR4Baseline(unittest.TestCase):
    """The R4 review of --baseline (R4B-1 to R4B-5, R4B-11, R4B-12)."""

    def setUp(self):
        self.d = tmpdir(self)
        self.site = self.d / "site"
        self.site.mkdir()

    def page(self, html):
        (self.site / "index.html").write_text(html, encoding="utf-8")

    def baseline(self, *extra):
        code, _out, err = run(self.site, "--json", self.d / "base.json",
                              "--fail-on", "never", *extra)
        self.assertEqual(code, 0, err)

    def gate(self, *extra):
        return run(self.site, "--baseline", self.d / "base.json",
                   "--json", self.d / "gate.json", *extra)

    def findings(self, rule):
        report = json.loads((self.d / "gate.json").read_text())
        return [f for p in report["pages"] for f in p["findings"]
                if f["rule_id"] == rule]

    def test_a_review_that_became_a_failure_is_new(self):
        # R4B-1: the page-level skip-link review and the FAIL it became
        # share a fingerprint; the verdict tells them apart.
        self.page(NAV.format("<main><p>Hello world.</p></main>"))
        self.baseline()
        self.page(NAV.format("<div><p>Hello world.</p></div>"))
        code, out, err = self.gate()
        self.assertEqual(code, 1, out + err)
        [f] = self.findings("bb-skip-link")
        self.assertEqual((f["verdict"], f["in_baseline"]), ("fail", False))
        report = json.loads((self.d / "gate.json").read_text())
        self.assertEqual(report["baseline"]["new_fail_findings"], 1)
        self.assertIn("the gate counts 1 failure(s)", out)

    def test_a_vendors_failure_that_became_the_sites_own_is_new(self):
        # R4B-2: a baseline that recorded the failure in a vendor's markup
        # does not cover it once it is the site's own.
        self.page(PAGE.format('<img src="badge.png">'))
        self.baseline()
        base = json.loads((self.d / "base.json").read_text())
        for p in base["pages"]:
            for f in p["findings"]:
                if f["rule_id"] == "bb-img-alt":
                    f.update(origin="third-party", owned=False,
                             origin_detail="https://vendor.example")
        (self.d / "vendor.json").write_text(json.dumps(base))
        code, out, err = run(self.site, "--baseline", self.d / "vendor.json",
                             "--json", self.d / "gate.json")
        self.assertEqual(code, 1, out + err)
        [f] = self.findings("bb-img-alt")
        self.assertIs(f["in_baseline"], False)
        # The same baseline, as the run recorded it, covers it.
        code, out, err = self.gate()
        self.assertEqual(code, 0, out + err)

    def test_a_rule_moved_into_a_counted_tier_is_new(self):
        # R4B-4: the note said so, and now it is so.
        self.page(PAGE.format('<iframe src="x.html"></iframe>'))
        self.baseline()
        code, out, err = self.gate()
        self.assertEqual(code, 0, out + err)
        rulebook = json.loads((ROOT / "src" / "bellbriar_harness" /
                               "rulebook.json").read_text(encoding="utf-8"))
        for r in rulebook["rules"]:
            if r["id"] == "bb-iframe-title":
                self.assertEqual(r["tier"], 2)
                r["tier"] = 1
        (self.d / "rb.json").write_text(json.dumps(rulebook))
        code, out, err = self.gate("--rulebook", self.d / "rb.json")
        self.assertEqual(code, 1, out + err)
        self.assertIn("a rule whose tier changed read as new", err)
        [f] = self.findings("bb-iframe-title")
        self.assertIs(f["in_baseline"], False)

    def test_the_console_counts_what_the_gate_counts(self):
        # R4B-5: a new tier-2 failure under --fail-on tier1.
        self.page(PAGE.format('<p>Hello</p>'))
        self.baseline()
        self.page(PAGE.format('<p>Hello</p><iframe src="x.html"></iframe>'))
        code, out, err = self.gate("--fail-on", "tier1")
        self.assertEqual(code, 0, out + err)
        self.assertIn("1 of them failures in the site's own markup", out)
        self.assertIn("the gate counts 0 failure(s) in the tiers --fail-on "
                      "tier1 counts", out)
        code, out, err = self.gate("--fail-on", "tier2")
        self.assertEqual(code, 1, out + err)
        self.assertIn("the gate counts 1 failure(s)", out)

    def test_strict_says_what_it_counts(self):
        # R4B-5: --strict with a baseline that lists the reviews.
        self.page(PAGE.format('<a href="/a">Shop</a><a href="/a">Shop</a>'))
        self.baseline()
        code, out, err = self.gate("--fail-on", "tier1", "--strict")
        self.assertEqual(code, 0, out + err)
        self.assertNotIn("failing the gate (--strict)", out)
        self.assertIn("0 of them not in the baseline", out)
        self.assertIn("and 0 --strict finding(s)", out)
        # And the reverse: a new strict review the console counted as none.
        self.page(NAV.format("<main><p>Hello world.</p></main>"))
        code, out, err = self.gate("--fail-on", "tier1", "--strict")
        self.assertEqual(code, 1, out + err)
        self.assertRegex(out, r"and [1-9]\d* --strict finding\(s\)")

    def test_pages_that_share_a_path_keep_their_numbers(self):
        # R4B-3: two pages recorded under one path are numbered by their
        # own URLs, not by where the list puts them.
        from bellbriar_harness.model import Finding, PageResult, RuleResult
        from bellbriar_harness.report import page_numbers, run_fingerprints

        def page(url):
            p = PageResult(path="https://example.com/p?id=REDACTED",
                           order=url)
            p.results.append(RuleResult("bb-img-alt", True, [Finding(
                "bb-img-alt", "fail", "serious", "no alt", 1)]))
            return p
        a, b = page("https://example.com/p?id=1"), page(
            "https://example.com/p?id=2")
        forward = run_fingerprints([a, b])
        a2, b2 = page("https://example.com/p?id=1"), page(
            "https://example.com/p?id=2")
        backward = run_fingerprints([b2, a2])
        fa = forward[id(a.results[0].findings[0])]
        fb = forward[id(b.results[0].findings[0])]
        self.assertNotEqual(fa, fb)
        self.assertEqual(backward[id(a2.results[0].findings[0])], fa)
        self.assertEqual(backward[id(b2.results[0].findings[0])], fb)
        self.assertEqual(sorted(page_numbers([a, b])), [0, 1])
        # A path no other page has is 0, whatever its URL.
        solo = PageResult(path="https://example.com/q", order="x")
        self.assertEqual(page_numbers([solo, a, b])[0], 0)

    def test_a_deep_baseline_is_not_json_it_can_read(self):
        # R4B-11
        (self.d / "deep.json").write_text(
            '{"format":"bellbriar-report/1","pages":' + "[" * 200000
            + "]" * 200000 + "}")
        self.page(PAGE.format("<p>x</p>"))
        code, _out, err = run(self.site, "--baseline", self.d / "deep.json")
        self.assertEqual(code, 2)
        self.assertIn("not a JSON file", err)

    def test_a_baselines_paths_cannot_write_to_the_console(self):
        # R4B-12: a path that would start a line of its own.
        self.page(PAGE.format('<img src="a.png">'))
        self.baseline()
        base = json.loads((self.d / "base.json").read_text())
        base["pages"][0]["path"] = ("x\n::error file=a::Forged\x1b[2J"
                                    "\u202e")
        for f in base["pages"][0]["findings"]:
            f["fingerprint"] = "0" * 32
        (self.d / "evil.json").write_text(json.dumps(base))
        code, out, err = run(self.d / "site", "--baseline",
                             self.d / "evil.json")
        self.assertIn("none of this run's findings is in the baseline", err)
        for line in (out + err).splitlines():
            self.assertFalse(line.startswith("::"), line)
        self.assertNotIn("\x1b", out + err)
        self.assertNotIn("\u202e", out + err)
        self.assertIn("x\\u000a::error", err)

    def test_the_html_banner_says_what_the_baseline_covers(self):
        # R4B-15: no double negative when nothing is new, and the rows a
        # table leaves out say how many of them are new.
        self.page(PAGE.format('<img src="a.png">'))
        self.baseline()
        self.gate("--html", self.d / "r.html")
        html = (self.d / "r.html").read_text(encoding="utf-8")
        self.assertIn("it lists every finding of this run, so none is "
                      "marked “new”", html)
        self.assertNotIn("are not in it", html)
        self.page(PAGE.format("".join(f'<img src="i{i}.png">'
                                      for i in range(105))))
        self.gate("--html", self.d / "r.html")
        html = (self.d / "r.html").read_text(encoding="utf-8")
        self.assertIn("105 of this run's findings are not in it", html)
        self.assertRegex(html, r"more findings of this rule here, \d+ of "
                         r"them failures and \d+ of them new, are not shown")

    def test_inspect_shows_the_baseline(self):
        # R4B-16: a bundle's reader sees that its gate had a baseline.
        from bellbriar_harness import evidence_cli
        self.page(PAGE.format('<img src="a.png">'))
        self.baseline()
        self.gate("--bundle", self.d / "b.json")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = evidence_cli.main(["inspect", str(self.d / "b.json")])
        self.assertEqual(code, 0)
        self.assertRegex(out.getvalue(), r"baseline    sha256=[0-9a-f]{64} "
                         r"made=\S+ findings=\d+: 0 of the run's findings "
                         r"not in it")
        run(self.site, "--bundle", self.d / "plain.json")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            evidence_cli.main(["inspect", str(self.d / "plain.json")])
        self.assertIn("baseline    none", out.getvalue())

    def test_a_baseline_without_what_the_match_needs(self):
        self.page(PAGE.format('<img src="a.png">'))
        self.baseline()
        base = json.loads((self.d / "base.json").read_text())
        del base["pages"][0]["findings"][0]["owned"]
        (self.d / "old.json").write_text(json.dumps(base))
        code, _out, err = run(self.site, "--baseline", self.d / "old.json")
        self.assertEqual(code, 2)
        self.assertIn("does not say its rule, verdict, owner, impact and "
                      "rule tier", err)
        # R4C-4: a rule id that is not text.
        base = json.loads((self.d / "base.json").read_text())
        base["pages"][0]["findings"][0]["rule_id"] = ["x"]
        (self.d / "odd.json").write_text(json.dumps(base))
        code, _out, err = run(self.site, "--baseline", self.d / "odd.json")
        self.assertEqual(code, 2, err)


if __name__ == "__main__":
    unittest.main()
