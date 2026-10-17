"""Part S5: what the review of 1.0.0rc1 for an adopting organization found.

  S5-1   Claims in signed text: a pass is "not sufficient" (a heuristic
         FAIL can fire on a conforming page, so it is not "necessary");
         the static layer is ACT-mapped where an ACT rule exists; WCAG
         2.2's additions are reported for review, not graded; no rule name
         or message speaks of an undistributed pack as though the reader
         had it.
  S5-2   Security: reports and bundles are never written through a
         symbolic link; a run that starts on a public site reads no page
         on a private network, and a server fetch follows only http and
         https; the build server answers only to its own address and never
         sends a key, a state file or a database; the browser inherits no
         variable whose name reads as a secret's; the Action mounts .git
         read-only, has shared memory of its own, and can require the
         sandbox.
  S5-3   What a run reads: a shell that shows only a loading indicator is
         not evaluated; a capture waits for the page's data requests too,
         and a page still loading at the cap is not evaluated unless
         --wait-for names what it shows once loaded; --render never falls
         back to the files, and a browser that is missing is tried once;
         a focusable element with a handler and no role fails (F59); a
         named file must be an HTML file; the console, the help, the
         report's tables at phone width and its lines of a captured page.
  S5-4   bellbriar-lint --exclude; the style rules tried on an element are
         narrowed by attributes and one-compound :is() and :where(), and a
         sibling list is walked once per `A ~ B` rule; a page's analysis
         has a budget (--page-budget); a run says when its libraries are
         versions outside the ranges this release declares (L134); the
         WHATWG Encoding Standard's notice and license ship with its data.
  S5-5   The release builds each image on its own architecture with no
         cache, runs the pushed image there, tags the version on the two
         that ran, and attests the files and the image; CI runs the image
         on ARM64 too; the build records its times and tools; the Action
         takes a pre-release's version.
  S5-6   The documents: personal data, a CI checklist, the capture's wait
         record, each finding's verdict basis in a bundle, one stability
         promise, the signer as the signer's own words, the metadata and
         the Action's README.
"""
from __future__ import annotations

import contextlib
import http.server
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bellbriar_harness import cli                                  # noqa: E402
from bellbriar_harness import coverage_text                        # noqa: E402
from bellbriar_harness import fetch as F                           # noqa: E402
from bellbriar_harness import serve                                # noqa: E402
from tests.test_fetch_hardening import HAVE_BROWSER, _WHY          # noqa: E402

GOOD = ROOT / "fixtures" / "good.html"


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _flat(path: str) -> str:
    return re.sub(r"\s+", " ", _text(path))


def _comments(path: str) -> str:
    """A file's text with each line's leading spaces and "#" dropped, so a
    comment that wraps reads as one sentence."""
    return re.sub(r"\s+", " ", " ".join(
        re.sub(r"^\s*#?\s?", "", line) for line in
        _text(path).splitlines()))


def _finding_messages(html: str) -> dict:
    """{rule_id: [messages]} of a file run on `html`."""
    d = Path(tempfile.mkdtemp(prefix="bb-s5-"))
    try:
        (d / "p.html").write_text(html, encoding="utf-8")
        run(d / "p.html", "--json", d / "r.json", "--fail-on", "never")
        report = json.loads((d / "r.json").read_text(encoding="utf-8"))
    finally:
        shutil.rmtree(d, True)
    out: dict = {}
    for page in report["pages"]:
        for f in page["findings"]:
            out.setdefault(f["rule_id"], []).append(f["message"])
    return out


def run(*argv, cwd=None):
    out, err = io.StringIO(), io.StringIO()
    here = os.getcwd()
    if cwd is not None:
        os.chdir(cwd)
    try:
        with contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(err):
            try:
                code = cli.main([str(a) for a in argv])
            except SystemExit as exc:
                code = exc.code
    finally:
        os.chdir(here)
    return code, out.getvalue(), err.getvalue()


def tmpdir(test) -> Path:
    d = Path(tempfile.mkdtemp(prefix="bb-s5-"))
    test.addCleanup(shutil.rmtree, d, True)
    return d


# ---------------------------------------------------------------------------
# S5-1
# ---------------------------------------------------------------------------

class TestTheClaims(unittest.TestCase):
    """S5-1."""

    def test_a_pass_is_not_called_necessary(self):
        for sentence in (coverage_text.COVERAGE_SENTENCE,
                         coverage_text.RENDERED_COVERAGE_SENTENCE):
            self.assertNotIn("necessary", sentence)
            self.assertIn("A passing result here is not sufficient, and is "
                          "not a determination of WCAG conformance or legal "
                          "compliance.", re.sub(r"\s+", " ", sentence))
        for rel in ("src/bellbriar_harness/cli.py", "README.md",
                    "docs/MEASUREMENT-AND-EVIDENCE-GUIDE.md"):
            with self.subTest(rel=rel):
                self.assertNotIn("necessary, not sufficient", _flat(rel))

    def test_the_static_layer_note(self):
        note = dict((n, w) for n, _s, w in coverage_text.LAYERS)[
            "static-dom"]
        self.assertEqual(note, "Deterministic DOM rules on parsed markup "
                               "(ACT-mapped where an ACT rule exists).")
        rules = json.loads(_text("src/bellbriar_harness/rulebook.json"))[
            "rules"]
        static = [r for r in rules if r.get("layer") == "static-dom"
                  and r.get("status") == "implemented"]
        # Some cite none, so "ACT-mapped" alone would claim too much.
        self.assertTrue([r for r in static if not r.get("act_rules")])

    def test_the_rulebook_speaks_plainly(self):
        rb = json.loads(_text("src/bellbriar_harness/rulebook.json"))
        self.assertNotIn("graded separately", rb["conformance_target"])
        self.assertIn("reports for review and is not graded",
                      rb["conformance_target"])
        names = " ".join(r["name"] for r in rb["rules"])
        for jargon in ("exclusion 10.2", "settlement furniture"):
            self.assertNotIn(jargon, names)
            self.assertNotIn(jargon, _text("docs/RULES.md"))
            self.assertNotIn(jargon, _text("docs/METHODOLOGY.md"))

    def test_no_message_offers_the_pack(self):
        text = _text("src/bellbriar_harness/checks_static.py")
        self.assertNotIn("the pack ships", text)
        messages = _finding_messages(
            '<!doctype html><html lang="en"><head><title>T</title></head>'
            '<body><main><h1>T</h1><a href="/x">Home</a></main></body>'
            '</html>')["bb-a11y-statement"]
        self.assertEqual(messages, [
            "No link to an accessibility statement found. A statement with "
            "a feedback channel recurs in DOJ and private settlements."])
        lint = _text("src/bellbriar_harness/lint.py")
        self.assertNotIn("(pack: ", lint)
        self.assertNotIn("the pack bans", lint)
        self.assertIn("not distributed with the harness",
                      _flat("README.md"))

    def test_the_template_says_what_the_gate_does(self):
        text = _comments("examples/ci/bellbriar-eval.yml")
        self.assertIn("Each third-party action is pinned to a commit", text)
        self.assertIn("The gate fails on Tier-1 WCAG failures (and probable "
                      "ones); give --fail-on any to fail on those of every "
                      "tier.", text)


# ---------------------------------------------------------------------------
# S5-2: outputs
# ---------------------------------------------------------------------------

@unittest.skipUnless(hasattr(os, "symlink") and os.name == "posix",
                     "symbolic links")
class TestOutputsAreNeverWrittenThroughALink(unittest.TestCase):
    """S5-2: a checkout that plants a link at an output's name, or among
    the folders on its way, cannot make a run write anywhere else."""

    def setUp(self):
        self.d = tmpdir(self)
        self.repo = self.d / "repo"
        self.outside = self.d / "outside"
        self.repo.mkdir()
        self.outside.mkdir()
        shutil.copy(GOOD, self.repo / "index.html")
        (self.outside / "victim.txt").write_text("victim\n")

    def check(self, option, name):
        code, _out, err = run("index.html", option, name, "--fail-on",
                              "never", cwd=self.repo)
        self.assertEqual(code, 2, err)
        self.assertIn(f"cannot write {name} ({option})", err)
        self.assertEqual((self.outside / "victim.txt").read_text(),
                         "victim\n")
        self.assertEqual(sorted(p.name for p in self.outside.iterdir()),
                         ["victim.txt"])
        return err

    def test_a_link_to_a_file(self):
        os.symlink(self.outside / "victim.txt", self.repo / "r.html")
        for option in ("--html", "--json", "--bundle"):
            with self.subTest(option=option):
                self.assertIn("it is a symbolic link",
                              self.check(option, "r.html"))

    def test_a_dangling_link(self):
        os.symlink(self.outside / "new.json", self.repo / "r.json")
        self.check("--json", "r.json")

    def test_a_linked_folder(self):
        os.symlink(self.outside, self.repo / "out")
        err = self.check("--json", "out/r.json")
        self.assertIn("on its way is a symbolic link", err)

    def test_a_snapshot_folder_that_is_a_link(self):
        why = cli._write_fresh(str(self.repo / "x.html"), b"x")
        self.assertIsNone(why)
        os.symlink(self.outside, self.repo / "snaps")
        here = os.getcwd()
        os.chdir(self.repo)
        try:
            why = cli._write_fresh("snaps/a.html", b"x")
        finally:
            os.chdir(here)
        self.assertIn("on its way is a symbolic link", why)
        self.assertFalse((self.outside / "a.html").exists())

    def test_a_regular_file_is_replaced_and_a_real_folder_is_used(self):
        (self.repo / "out").mkdir()
        (self.repo / "r.json").write_text("old")
        code, _out, err = run("index.html", "--json", "r.json", "--html",
                              "out/r.html", "--fail-on", "never",
                              cwd=self.repo)
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads((self.repo / "r.json").read_text())[
            "format"], "bellbriar-report/1")
        self.assertTrue((self.repo / "out" / "r.html").is_file())

    def test_a_link_above_reached_by_dotdot_is_the_users(self):
        """S5 re-review: `../reports`, a link beside the current folder, is
        the user's, not a checkout's."""
        (self.d / "real-reports").mkdir()
        os.symlink(self.d / "real-reports", self.d / "reports")
        code, _out, err = run("index.html", "--json", "../reports/r.json",
                              "--fail-on", "never", cwd=self.repo)
        self.assertEqual(code, 0, err)
        self.assertTrue((self.d / "real-reports" / "r.json").is_file())

    def test_an_alias_then_a_planted_link(self):
        """S5 re-review: through a folder the user reaches the workspace by,
        a link the checkout planted is refused all the same."""
        os.symlink(self.repo, self.d / "alias")
        os.symlink(self.outside, self.repo / "out")
        err = self.check("--json", str(self.d / "alias" / "out" / "r.json"))
        self.assertIn("on its way is a symbolic link", err)

    def test_a_folder_above_the_current_one_is_the_users(self):
        """A link above the current folder (macOS's /var, a home folder
        reached through one) is the user's choice, not a checkout's."""
        os.symlink(self.repo, self.d / "alias")
        out = self.d / "alias" / "r.json"
        code, _out, err = run(str(GOOD), "--json", out, "--fail-on",
                              "never", cwd=self.outside)
        self.assertEqual(code, 0, err)
        self.assertTrue((self.repo / "r.json").is_file())


# ---------------------------------------------------------------------------
# S5-2: private networks and schemes
# ---------------------------------------------------------------------------

def _no_dns(*_a, **_k):
    raise OSError("no resolver in this test")


class TestPrivateHops(unittest.TestCase):
    """S5-2: the decision, apart from any fetch."""

    def test_public_to_private_is_refused(self):
        with mock.patch("socket.getaddrinfo", _no_dns):
            for hop, peer in (("http://10.0.0.1/admin", None),
                              ("http://localhost:8080/", None),
                              ("http://127.1/", None),
                              ("http://intranet.example/", "192.168.1.5"),
                              ("http://[::1]:9/", None)):
                with self.subTest(hop=hop):
                    with self.assertRaises(F.FetchError) as caught:
                        F.refuse_private_hops("https://shop.example/",
                                              None, [(hop, peer)])
                    self.assertIn("reads no page on a private network",
                                  str(caught.exception))

    def test_a_private_start_goes_anywhere(self):
        with mock.patch("socket.getaddrinfo", _no_dns):
            F.refuse_private_hops("http://10.0.0.2/", None,
                                  [("http://10.0.0.1/", None)])
            F.refuse_private_hops("http://127.0.0.1:8000/", None,
                                  [("http://localhost:3000/", None)])
            F.refuse_private_hops("https://shop.example/", "10.1.1.1",
                                  [("http://10.0.0.1/", None)])

    def test_a_name_that_resolves_privately(self):
        def resolver(host, *_a, **_k):
            if host == "intranet.example":
                return [(2, 1, 6, "", ("10.9.9.9", 0))]
            raise OSError("unknown")
        with mock.patch("socket.getaddrinfo", resolver):
            with self.assertRaises(F.FetchError):
                F.refuse_private_hops("https://shop.example/", None,
                                      [("http://intranet.example/", None)])
            F.refuse_private_hops("http://intranet.example/", None,
                                  [("http://10.0.0.1/", None)])

    def test_a_public_hop_is_followed(self):
        with mock.patch("socket.getaddrinfo", _no_dns):
            F.refuse_private_hops("https://shop.example/", None,
                                  [("https://www.shop.example/", None),
                                   ("https://cdn.example/", "93.184.216.34")])

    def test_only_http_and_https(self):
        opener = urllib.request.build_opener(
            F._NoFTP(), F._NoFile(), F._NoData())
        for url in ("ftp://127.0.0.1/", "file:///etc/hostname",
                    "data:text/html,hi"):
            with self.subTest(url=url):
                with self.assertRaises(F._RefusedHop):
                    opener.open(url, timeout=5)


class _Redirector:
    """127.0.0.1, sending /go to `target`, and /page as a small page."""

    def __init__(self, target_of):
        outer = self

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):                     # noqa: N802
                outer.paths.append(self.path)
                if self.path == "/go":
                    self.send_response(302)
                    self.send_header("Location", target_of(outer))
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                body = GOOD.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        self.paths: list = []
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def _public_loopback(real):
    """_private_kind that takes 127.0.0.1 for a public site (the test's
    stand-in for one) and keeps every other answer."""
    def kind(host, peer=None):
        if host == "127.0.0.1":
            return None
        return real(host, peer)
    return kind


class TestServerFetchHops(unittest.TestCase):
    """S5-2, through urllib: refused before connecting, by scheme or by
    network."""

    def serve(self, target_of):
        server = _Redirector(target_of)
        self.addCleanup(server.stop)
        return server

    def test_a_redirect_into_a_private_network(self):
        server = self.serve(lambda s: f"http://localhost:{s.port}/page")
        with mock.patch.object(F, "_private_kind",
                               _public_loopback(F._private_kind)):
            with self.assertRaises(F.FetchError) as caught:
                F.fetch_server(f"http://127.0.0.1:{server.port}/go")
        self.assertIn("reads no page on a private network",
                      str(caught.exception))
        # Refused before it connects: the private page was never asked for
        # (S5 re-review).
        self.assertEqual(server.paths, ["/go"])

    def test_a_redirect_to_ftp(self):
        server = self.serve(lambda s: "ftp://127.0.0.1:1/")
        with self.assertRaises(F.FetchError) as caught:
            F.fetch_server(f"http://127.0.0.1:{server.port}/go")
        self.assertIn("not http or https is not followed",
                      str(caught.exception))

    def test_a_loopback_start_follows_loopback(self):
        server = self.serve(lambda s: f"http://localhost:{s.port}/page")
        got = F.fetch_server(f"http://127.0.0.1:{server.port}/go")
        self.assertEqual(got.status, 200)
        self.assertEqual(server.paths, ["/go", "/page"])


@unittest.skipUnless(HAVE_BROWSER, _WHY)
class TestRenderedHops(unittest.TestCase):
    """S5-2, in the browser: the capture is refused, and nothing falls
    back to the server's HTML."""

    def test_a_redirect_into_a_private_network(self):
        server = _Redirector(lambda s: f"http://localhost:{s.port}/page")
        self.addCleanup(server.stop)
        with mock.patch.object(F, "_private_kind",
                               _public_loopback(F._private_kind)):
            with self.assertRaises(F.FetchError) as caught:
                F.fetch(f"http://127.0.0.1:{server.port}/go", render=None)
        self.assertIn("reads no page on a private network",
                      str(caught.exception))


class TestTheAddressConnectedTo(unittest.TestCase):
    """S5 re-review: a rendered capture was judged by the names on its way,
    resolved again after it; a name can resolve elsewhere by then (DNS
    rebinding), so the addresses the browser connected to for the document
    it read, and the redirects on its way there, are judged as they were."""

    @staticmethod
    def _public_now(host, port=None, *a, **kw):
        import socket
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "",
                 ("93.184.216.34", 0))]

    def result(self, peers):
        return F.FetchResult(
            url="https://public.example/", mode="rendered", html="",
            final_url="https://public.example/next", status=200,
            redirects=[], document_peers=peers)

    def test_an_address_connected_to_is_judged(self):
        with mock.patch("socket.getaddrinfo", self._public_now):
            F._refuse_private_page("https://public.example/", self.result([
                ("https://public.example/next", "93.184.216.34")]))
            for peer in ("127.0.0.1", "10.1.2.3", "[::1]", "::ffff:7f00:1"):
                with self.subTest(peer=peer), self.assertRaises(
                        F.FetchError) as caught:
                    F._refuse_private_page(
                        "https://public.example/", self.result([
                            ("https://public.example/go", "93.184.216.34"),
                            ("https://public.example/next", peer)]))
                self.assertIn("reads no page on a private network",
                              str(caught.exception))

    def test_the_tracker_records_each_response_address(self):
        docs = object.__new__(F._Documents)
        docs.peers, docs.own_peer, docs.responses = {}, {}, {}
        docs.worker, docs.pending, docs._main = set(), None, "M"
        docs._request({"type": "Document", "loaderId": "L", "frameId": "M",
                       "redirectResponse": {"url": "https://a.example/go",
                                            "remoteIPAddress": "1.2.3.4"}})
        docs._request({"type": "Script", "loaderId": "L",
                       "redirectResponse": {"url": "https://a.example/s.js",
                                            "remoteIPAddress": "5.6.7.8"}})
        docs._response({"type": "Document", "loaderId": "L", "response": {
            "url": "https://a.example/page", "remoteIPAddress": "127.0.0.1",
            "status": 200, "headers": {}}})
        self.assertEqual(docs.peers["L"], [
            ("https://a.example/go", "1.2.3.4"),
            ("https://a.example/page", "127.0.0.1")])
        self.assertEqual(docs.own_peer["L"],
                         ("https://a.example/page", "127.0.0.1"))

    @unittest.skipUnless(HAVE_BROWSER, _WHY)
    def test_a_capture_records_them(self):
        server = _Redirector(lambda s: f"http://127.0.0.1:{s.port}/page")
        self.addCleanup(server.stop)
        got = F.fetch(f"http://127.0.0.1:{server.port}/go", render=True)
        self.assertEqual(got.document_peers, [
            (f"http://127.0.0.1:{server.port}/go", "127.0.0.1"),
            (f"http://127.0.0.1:{server.port}/page", "127.0.0.1")])
        self.assertEqual((got.address_class, got.address_basis),
                         ("loopback", "address"))
        written = json.dumps([got.fetch_block(), got.manifest_entry()])
        self.assertNotIn("document_peers", written)


_HANG = (b'<!doctype html><html lang="en"><head><title>T</title></head>'
         b'<body><main><h1>T</h1></main><script>'
         b'setTimeout(function () { while (true) {} }, 50);</script>'
         b'</body></html>')


class _Page:
    """127.0.0.1, answering every GET with `body`."""

    def __init__(self, body: bytes):
        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):                     # noqa: N802
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                with contextlib.suppress(OSError):
                    self.wfile.write(body)
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.httpd.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}/"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()


class TestTheNamesFilesAreRecordedBy(unittest.TestCase):
    """S5 re-review: docs/EVIDENCE.md said a file is recorded by its path
    inside the folder the run was given; a relative path is recorded as
    typed, and one typed through a home directory named its user."""

    def test_as_the_documents_say(self):
        from bellbriar_harness import bundle as B
        here = os.getcwd()
        self.addCleanup(os.chdir, here)
        d = tmpdir(self)
        (d / "home" / "alice" / "site").mkdir(parents=True)
        os.chdir(d)
        self.assertEqual(B.recorded_path("home/alice/site/index.html",
                                         "home/alice/site"),
                         "site/index.html")
        os.chdir(d / "home")
        self.assertEqual(B.recorded_path("alice/site/index.html",
                                         "alice/site"), "site/index.html")
        os.chdir(d / "home" / "alice")
        self.assertEqual(B.recorded_path("site/index.html", "site"),
                         "site/index.html")
        self.assertEqual(B.recorded_path("site/./a/b.html", "site"),
                         "site/a/b.html")
        os.chdir(d)
        self.assertEqual(B.recorded_path("srv/www/index.html", "srv"),
                         "srv/www/index.html")
        evidence = re.sub(r"\s+", " ", _text("docs/EVIDENCE.md"))
        self.assertIn("as the command line named it, when that path is "
                      "relative and has no `..`", evidence)


class TestTheCapturesOwnFolder(unittest.TestCase):
    """S5 re-review: "the harness keeps nothing itself", but a capture
    stopped at its deadline left the browser's profile (its cache, cookies
    and storage) in the system's temporary folder. Each capture has a
    folder of its own, removed when it ends."""

    def test_only_its_own_folder_is_removed(self):
        d = tmpdir(self)
        other = d / "keep-me"
        other.mkdir()
        F.remove_capture_scratch(str(other))
        self.assertTrue(other.is_dir())
        mine = d / (F.CAPTURE_SCRATCH_PREFIX + "x")
        (mine / "profile").mkdir(parents=True)
        (mine / "profile" / "Cookies").write_text("x")
        link = d / (F.CAPTURE_SCRATCH_PREFIX + "link")
        link.symlink_to(other)
        F.remove_capture_scratch(str(link))
        self.assertTrue(link.is_symlink() and other.is_dir())
        F.remove_capture_scratch(str(mine))
        self.assertFalse(mine.exists())

    def test_what_a_late_process_writes_is_removed_in_turn(self):
        """S5 final check: a browser process that started as the capture
        was stopped wrote into the folder after it was removed, once in a
        full run; it is removed again until it stays gone."""
        import time
        d = tmpdir(self)
        mine = d / (F.CAPTURE_SCRATCH_PREFIX + "late")
        mine.mkdir()
        stop = threading.Event()

        def late_writer():
            until = time.monotonic() + 1.0
            while time.monotonic() < until and not stop.is_set():
                with contextlib.suppress(OSError):
                    mine.mkdir(exist_ok=True)
                    (mine / "Cookies").write_text("x")
                time.sleep(0.05)
        writer = threading.Thread(target=late_writer, daemon=True)
        writer.start()
        self.addCleanup(stop.set)
        self.assertTrue(F.remove_capture_scratch(str(mine), patience_s=5,
                                                 settle_s=0.5))
        writer.join(5)
        self.assertFalse(mine.exists())
        held = d / (F.CAPTURE_SCRATCH_PREFIX + "held")
        held.mkdir()
        with mock.patch("shutil.rmtree", lambda *a, **k: None):
            self.assertFalse(F.remove_capture_scratch(str(held),
                                                      patience_s=0.3))

    def fresh_temp(self) -> Path:
        d = tmpdir(self)
        patcher = mock.patch.object(tempfile, "tempdir", str(d))
        patcher.start()
        self.addCleanup(patcher.stop)
        return d

    @unittest.skipUnless(HAVE_BROWSER, _WHY)
    def test_a_capture_leaves_nothing(self):
        d = self.fresh_temp()
        site = _Page(GOOD.read_bytes())
        self.addCleanup(site.stop)
        F.fetch(site.url, render=True)
        self.assertEqual(list(d.iterdir()), [])

    @unittest.skipUnless(HAVE_BROWSER, _WHY)
    def test_a_capture_stopped_at_its_deadline_leaves_nothing(self):
        d = self.fresh_temp()
        site = _Page(_HANG)
        self.addCleanup(site.stop)
        with self.assertRaises(F.FetchError):
            F.fetch(site.url, render=True, deadline_s=5)
        self.assertEqual(list(d.iterdir()), [])

    @unittest.skipUnless(HAVE_BROWSER and os.name == "posix", _WHY)
    def test_a_run_killed_mid_capture_leaves_nothing(self):
        """The capture process, seeing the run gone, removes it itself."""
        import signal
        import time
        d = tmpdir(self)
        site = _Page(_HANG)
        self.addCleanup(site.stop)
        script = (f"import sys; sys.path.insert(0, {str(ROOT / 'src')!r}); "
                  "from bellbriar_harness import fetch as F; "
                  f"F.fetch({site.url!r}, render=True, deadline_s=120)")
        env = dict(os.environ, TMPDIR=str(d))
        run_ = subprocess.Popen([sys.executable, "-I", "-c", script],
                                env=env, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
        self.addCleanup(lambda: run_.poll() is None and run_.kill())
        for _ in range(100):                   # the capture has begun
            if any(p.name.startswith(F.CAPTURE_SCRATCH_PREFIX)
                   and any(p.iterdir()) for p in d.iterdir()):
                break
            time.sleep(0.1)
        else:
            self.fail("no capture folder appeared")
        time.sleep(1.5)
        os.kill(run_.pid, signal.SIGKILL)
        run_.wait(10)
        for _ in range(100):
            if not list(d.iterdir()):
                break
            time.sleep(0.2)
        self.assertEqual(list(d.iterdir()), [])


# ---------------------------------------------------------------------------
# S5-2: the build server
# ---------------------------------------------------------------------------

class TestTheBuildServer(unittest.TestCase):
    """S5-2."""

    def setUp(self):
        self.d = tmpdir(self)
        (self.d / "index.html").write_text("<p>x</p>")
        for name in ("deploy.pem", "terraform.tfstate", "app.sqlite",
                     "id_rsa", "site.key", "credentials.json"):
            (self.d / name).write_text("secret")
        (self.d / "app.js").write_text("x=1")
        self.server = serve.BuildServer(self.d).__enter__()
        self.addCleanup(self.server.__exit__, None, None, None)
        self.port = self.server._httpd.server_address[1]

    def get(self, path, host=None):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}")
        if host:
            req.add_unredirected_header("Host", host)
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}))
        try:
            with opener.open(req, timeout=10) as resp:
                return resp.status
        except urllib.error.HTTPError as exc:
            return exc.code

    def test_keys_states_and_databases_are_never_sent(self):
        for name in ("deploy.pem", "terraform.tfstate", "app.sqlite",
                     "id_rsa", "site.key", "credentials.json"):
            with self.subTest(name=name):
                self.assertEqual(self.get(f"/{name}"), 404)
        self.assertEqual(self.get("/app.js"), 200)
        self.assertEqual(self.get("/"), 200)

    def test_only_its_own_address(self):
        self.assertEqual(self.get("/", host="attacker.example"), 421)
        self.assertEqual(self.get("/", host=f"localhost:{self.port}"), 200)
        self.assertEqual(self.get("/", host=f"127.0.0.1:{self.port}"), 200)

    def test_a_source_folder_is_named(self):
        (self.d / "package.json").write_text("{}")
        code, _out, err = run(self.d, "--render", "--fail-on", "never")
        self.assertIn("looks like a source folder", err)
        # What it serves, exactly (S5 re-review): not the whole folder.
        self.assertIn("their scripts can read every one it sends, which is "
                      "all but those under a name that starts with a dot "
                      "and those a build never holds",
                      re.sub(r"\s+", " ", err))


# ---------------------------------------------------------------------------
# S5-2: the environment
# ---------------------------------------------------------------------------

class TestTheBrowsersEnvironment(unittest.TestCase):
    """S5-2: a renderer a page takes over runs as this user; it finds no
    token, cloud key or agent socket in its environment."""

    WITHHELD = ("GITHUB_TOKEN", "NPM_TOKEN", "NODE_AUTH_TOKEN",
                "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY",
                "AWS_SESSION_TOKEN", "SSH_AUTH_SOCK",
                "ACTIONS_ID_TOKEN_REQUEST_URL", "ACTIONS_RUNTIME_TOKEN",
                "TWINE_PASSWORD", "GH_PAT", "SENTRY_DSN", "DATABASE_URL",
                "GOOGLE_APPLICATION_CREDENTIALS", "STRIPE_SECRET_KEY")
    KEPT = ("PATH", "HOME", "PWD", "LANG", "LC_ALL", "HTTPS_PROXY",
            "no_proxy", "PLAYWRIGHT_BROWSERS_PATH", "SSL_CERT_FILE",
            "NODE_EXTRA_CA_CERTS", "XAUTHORITY", "GIT_AUTHOR_NAME",
            "TMPDIR", "KEYBOARD_LAYOUT", "PASSIVE_MODE")

    def test_the_names(self):
        for name in self.WITHHELD:
            with self.subTest(name=name):
                self.assertTrue(F.withheld(name))
        for name in self.KEPT:
            with self.subTest(name=name):
                self.assertFalse(F.withheld(name))

    def test_the_names_and_values_the_re_review_found(self):
        """S5 re-review: a word that ends as a secret's does, a program's
        PWD, connection strings, databases' URLs, and any value that is a
        URL with a password in it, the proxy settings' aside, which the
        browser needs as they are."""
        for name in ("MYSQL_PWD", "AZURE_STORAGE_CONNECTION_STRING",
                     "SQLCONNECTIONSTRING", "MONGO_URI", "JDBC_DATABASE_URL",
                     "REDIS_URL", "POSTGRES_DSN", "DEPLOY_APITOKEN",
                     "VAULT_PASSPHRASE", "jwt_secret", "JWTKEY",
                     "MY_DB_PASSWORDS", "SMTP_PASSWD"):
            with self.subTest(name=name):
                self.assertTrue(F.withheld(name))
        for name in ("PWD", "OLDPWD", "SITE_URL", "BASE_URI", "DB_HOST",
                     "PIP_INDEX_URL"):
            with self.subTest(name=name):
                self.assertFalse(F.withheld(name))
                self.assertFalse(F.withheld(name, "https://example.com/x"))
                self.assertTrue(F.withheld(
                    name, "https://ci:s3cr3t@pypi.example/simple"))
        for name in ("HTTPS_PROXY", "https_proxy", "ALL_PROXY"):
            with self.subTest(name=name):
                self.assertFalse(F.withheld(
                    name, "http://user:pass@proxy.example:3128"))

    def test_the_child_environment(self):
        seen = {}

        class Stop(Exception):
            pass

        def popen(*args, **kw):
            seen.update(kw.get("env") or {})
            raise Stop
        env = {name: "x" for name in self.WITHHELD + ("KEEP_ME",)}
        with mock.patch.dict(os.environ, env), \
                mock.patch("subprocess.Popen", popen):
            with self.assertRaises(Stop):
                F._fetch_rendered_isolated("http://127.0.0.1:9/", 5.0)
        self.assertEqual(seen.get("KEEP_ME"), "x")
        for name in self.WITHHELD:
            self.assertNotIn(name, seen)


# ---------------------------------------------------------------------------
# S5-2: the Action
# ---------------------------------------------------------------------------

def _action_script() -> str:
    try:
        import yaml
    except ImportError:
        raise unittest.SkipTest("PyYAML is not installed")
    return yaml.safe_load(_text("action/action.yml"))["runs"]["steps"][0][
        "run"]


@unittest.skipUnless(shutil.which("bash"), "bash")
class TestTheActionsContainer(unittest.TestCase):
    """S5-2."""

    def act(self, d, args="dist", sandbox=None, version="1"):
        env = {**os.environ, "PATH": f"{d / 'bin'}{os.pathsep}"
               f"{os.environ.get('PATH', '')}", "RUNNER_OS": "Linux",
               "GITHUB_WORKSPACE": str(d), "GITHUB_ACTION_PATH": "/act",
               "BB_ARGS": args, "BB_VERSION": version, "BB_PASS_ENV": ""}
        if sandbox is not None:
            env["BB_SANDBOX"] = sandbox
        return subprocess.run(["bash", "-c", _action_script()], env=env,
                              cwd=d, capture_output=True, text=True)

    def setUp(self):
        self.d = tmpdir(self)
        (self.d / "bin").mkdir()
        fake = self.d / "bin" / "docker"
        fake.write_text('#!/usr/bin/env bash\nfor a in "$@"; do '
                        'printf "[%s]\\n" "$a"; done\n')
        fake.chmod(0o755)

    def test_shared_memory_of_its_own(self):
        out = self.act(self.d)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("[--shm-size=2g]", out.stdout)
        self.assertNotIn("--ipc", out.stdout)

    def test_git_is_read_only(self):
        self.assertNotIn(":/work/.git:ro]", self.act(self.d).stdout)
        (self.d / ".git").mkdir()
        out = self.act(self.d)
        self.assertIn(f"[-v]\n[{self.d}/.git:/work/.git:ro]", out.stdout)
        # After the workspace, so it lies over it.
        self.assertLess(out.stdout.index(f"[{self.d}:/work]"),
                        out.stdout.index(f"[{self.d}/.git:/work/.git:ro]"))

    def test_the_sandbox_can_be_required(self):
        off = self.act(self.d, sandbox="off").stdout
        self.assertNotIn("seccomp", off)
        self.assertNotIn("--require-sandbox", off)
        on = self.act(self.d, sandbox="required")
        self.assertEqual(on.returncode, 0, on.stderr)
        self.assertIn("[--security-opt]\n[seccomp=/act/seccomp_profile.json]",
                      on.stdout)
        self.assertTrue(on.stdout.rstrip().endswith("[--require-sandbox]"))
        self.assertEqual(self.act(self.d, sandbox="yes").returncode, 2)

    def test_a_pre_release_by_its_version(self):
        """S5-5: the rehearsal's image, 1.0.0rc1, could not be named."""
        for version in ("1.0.0rc1", "1.2.3a4", "2.0.0b1"):
            with self.subTest(version=version):
                out = self.act(self.d, version=version)
                self.assertEqual(out.returncode, 0, out.stderr)
                self.assertIn(f"[ghcr.io/bellbriar/harness:{version}]",
                              out.stdout)
        for version in ("1.0rc1", "1.0.0rc", "1.0.0-rc1", "1.0.0rc1;x"):
            with self.subTest(version=version):
                self.assertEqual(self.act(self.d, version=version)
                                 .returncode, 2)

    def test_the_profile_and_license_ship_with_it(self):
        self.assertEqual(_text("action/seccomp_profile.json"),
                         _text("docker/seccomp_profile.json"))
        self.assertEqual(_text("action/LICENSE"), _text("LICENSE"))
        profile = json.loads(_text("docker/seccomp_profile.json"))
        self.assertEqual(profile["defaultAction"], "SCMP_ACT_ERRNO")
        self.assertIn("seccomp_profile.json", _flat("NOTICE"))
        # The Action's repository holds its own notice (S5 re-review).
        self.assertIn("seccomp_profile.json is Playwright's",
                      _flat("action/NOTICE"))

    def test_prepublish_names_every_file_of_the_action(self):
        """S5 re-review: item 17 named two of the folder's files; the
        Action's repository needs all of them (sandbox: required reads the
        profile beside action.yml)."""
        item = _flat("PREPUBLISH.md").split("17. **Publish the Action")[1]
        item = item.split("18. **")[0]
        listed = item.split("every file of `action/` at its root (")[1]
        named = set(re.findall(r"`([A-Za-z_.]+)`",
                               listed.split(", which")[0]))
        self.assertEqual(named, {p.name for p in (ROOT / "action").iterdir()
                                 if p.is_file()})


# ---------------------------------------------------------------------------
# S5-3
# ---------------------------------------------------------------------------

_SHELL = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
          '<title>Orders</title><script type="module" src="/assets/i.js">'
          '</script></head><body><div id="root">{}</div></body></html>')


class TestLoadingShells(unittest.TestCase):
    """S5-3: a shell showing a loading indicator was Tier-1 clean."""

    def test_a_loading_indicator_is_no_content(self):
        d = tmpdir(self)
        for i, body in enumerate((
                '<div role="status">Loading, please wait…</div>',
                '<img src="/spinner.gif" alt="Loading">',
                '<progress></progress>',
                '<div aria-busy="true"><p>Loading orders</p></div>',
                '<svg aria-label="Loading" class="spinner"></svg>')):
            with self.subTest(body=body):
                page = d / f"s{i}.html"
                page.write_text(_SHELL.format(body), encoding="utf-8")
                code, _out, err = run(page, "--fail-on", "tier1")
                self.assertEqual(code, 2, err)
                self.assertIn("beyond a loading indicator", err)

    def test_what_reads_as_a_loader(self):
        """S5 re-review: containers with a role (main, presentation, a
        region), a role named for loading, and a drawing's or an image's
        name from its <title> or aria-labelledby."""
        d = tmpdir(self)
        for i, body in enumerate((
                '<div role="main"><div role="presentation"><div '
                'role="status">Loading…</div></div></div>',
                '<div role="spinner"></div>',
                '<svg role="img"><title>Loading</title></svg>',
                '<svg aria-labelledby="t"><title id="t">Loading orders'
                '</title></svg>',
                '<img src="/x.gif" aria-labelledby="w"><span id="w" hidden>'
                'Loading</span>',
                '<div role="region" aria-label="Orders"><div '
                'role="progressbar"></div></div>')):
            with self.subTest(body=body):
                page = d / f"l{i}.html"
                page.write_text(_SHELL.format(body), encoding="utf-8")
                code, _out, err = run(page, "--fail-on", "tier1")
                self.assertEqual(code, 2, err)
                self.assertIn("beyond a loading indicator", err)

    def test_content_beside_a_status_message_is_read(self):
        page = tmpdir(self) / "p.html"
        page.write_text(_SHELL.format(
            '<main><h1>Orders</h1><a href="/o/1">Order 1</a>'
            '<p role="status">3 orders</p></main>'), encoding="utf-8")
        code, _out, err = run(page, "--fail-on", "tier1")
        self.assertEqual(code, 0, err)


class TestFocusableHandlers(unittest.TestCase):
    """S5-3: WCAG's F59, a focusable <div> or <span> with a click or key
    handler and no role."""

    def test_which_fail(self):
        d = tmpdir(self)
        (d / "p.html").write_text(
            '<!doctype html><html lang="en"><head><title>T</title></head>'
            '<body><main><h1>T</h1>'
            '<div tabindex="0" onclick="go()" id="a">Filters</div>'
            '<span tabindex="0" onkeydown="k(event)" id="b">Sort</span>'
            '<div tabindex="0" id="c">A scroll box</div>'
            '<div onclick="go()" id="d">Not focusable</div>'
            '<div role="button" tabindex="0" onclick="go()" id="e">OK</div>'
            '<my-widget tabindex="0" onclick="x()" id="f">W</my-widget>'
            '<div tabindex="-1" onclick="go()" id="g">Programmatic</div>'
            '</main></body></html>', encoding="utf-8")
        run(d / "p.html", "--json", d / "r.json", "--fail-on", "never")
        report = json.loads((d / "r.json").read_text(encoding="utf-8"))
        fails = sorted(re.search(r'id="(\w)"', f["snippet"]).group(1)
                       for page in report["pages"] for f in page["findings"]
                       if f["rule_id"] == "bb-control-role"
                       and f["verdict"] == "fail"
                       and "handler has no role" in f["message"])
        self.assertEqual(fails, ["a", "b", "f"])

    def test_a_role_that_is_none(self):
        """S5 re-review: an empty role, none, presentation or generic gives
        a focusable <div> no role a control has; an unknown role is the
        other loop's, said once."""
        d = tmpdir(self)
        (d / "p.html").write_text(
            '<!doctype html><html lang="en"><head><title>T</title></head>'
            '<body><main><h1>T</h1>'
            '<div tabindex="0" onclick="go()" role="" id="a">A</div>'
            '<div tabindex="0" onclick="go()" role="none" id="b">B</div>'
            '<div tabindex="0" onclick="go()" role="presentation" id="c">'
            'C</div>'
            '<span tabindex="0" onkeydown="k()" role="generic" id="d">D</span>'
            '<div tabindex="0" onclick="go()" role="foo none" id="e">E</div>'
            '<div tabindex="0" onclick="go()" role="buton" id="f">F</div>'
            '<div tabindex="0" onclick="go()" role="button" id="g">G</div>'
            '<div tabindex="0" onclick="go()" role="none button" id="h">'
            'H</div>'
            '<div tabindex="0" role="presentation" id="i">I</div>'
            '</main></body></html>', encoding="utf-8")
        run(d / "p.html", "--json", d / "r.json", "--fail-on", "never")
        report = json.loads((d / "r.json").read_text(encoding="utf-8"))
        fails = [(re.search(r'id="(\w)"', f["snippet"]).group(1),
                  f["message"])
                 for page in report["pages"] for f in page["findings"]
                 if f["rule_id"] == "bb-control-role"
                 and f["verdict"] == "fail"]
        self.assertEqual(sorted(i for i, _ in fails),
                         ["a", "b", "c", "d", "e", "f", "h"])
        said = dict(fails)
        self.assertIn('handler has no role (role="presentation" is not a '
                      "control's role)", said["c"])
        self.assertIn('(role="" is not', said["a"])
        self.assertIn('"buton" is not an ARIA role', said["f"])


class TestWhatARunReads(unittest.TestCase):
    """S5-3: the command line, the console and the help."""

    def test_wait_for_needs_a_browser_and_a_selector(self):
        for argv, said in (
                ((GOOD, "--wait-for", "main"), "--wait-for waits in a "
                 "browser"),
                (("--url", "http://127.0.0.1:9/", "--no-render",
                  "--wait-for", "main"), "--wait-for and --no-render "
                 "contradict each other"),
                ((GOOD, "--render", "--wait-for", "main[["),
                 "is not a CSS selector")):
            with self.subTest(argv=argv):
                code, _out, err = run(*argv)
                self.assertEqual(code, 2, err)
                self.assertIn(said, err)

    def test_the_console_counts_pages(self):
        code, out, _err = run(ROOT / "fixtures" / "bad.html", "--fail-on",
                              "never")
        self.assertEqual(code, 0)
        self.assertRegex(out, r"top failing rules, by pages failed: "
                              r"bb-[a-z-]+ \(1 page\)")

    def test_the_help_says_the_exit_statuses(self):
        code, out, _err = run("--help")
        self.assertEqual(code, 0)
        flat = re.sub(r"\s+", " ", out)
        self.assertIn("exit status: 0 when the gate passes, 1 when it fails "
                      "(--fail-on), 2 when the run could not be completed",
                      flat)
        self.assertIn("bellbriar-eval dist --render --fail-on tier1", out)
        self.assertTrue(all(len(line) <= 79 for line in out.splitlines()))
        lint = io.StringIO()
        with contextlib.redirect_stdout(lint), self.assertRaises(SystemExit):
            from bellbriar_harness import lint as L
            L._main(["--help"])
        self.assertIn("exit 2 when nothing could be read",
                      re.sub(r"\s+", " ", lint.getvalue()))

    def test_a_browser_that_does_not_start_is_the_runs(self):
        """S5 re-review: fetch() tells a browser that cannot start (every
        page would fail so) from one page's failure."""
        def failing(text):
            def capture(*_a, **_k):
                raise Exception(text)
            return capture
        with mock.patch.object(F, "playwright_available",
                               lambda: (True, "")):
            with mock.patch.object(F, "_fetch_rendered_isolated", failing(
                    "BrowserType.launch: Executable doesn't exist at /x")):
                with self.assertRaises(F.BrowserUnavailable) as caught:
                    F.fetch("http://127.0.0.1:9/", render=True,
                            browser_required=True)
                self.assertIn("is not installed", str(caught.exception))
                # Without --render's need of one, it is that page's.
                with self.assertRaises(F.FetchError) as caught:
                    F.fetch("http://127.0.0.1:9/", render=True)
                self.assertNotIsInstance(caught.exception,
                                         F.BrowserUnavailable)
            with mock.patch.object(F, "_fetch_rendered_isolated", failing(
                    "Page.goto: net::ERR_CONNECTION_REFUSED at "
                    "http://127.0.0.1:9/")):
                with self.assertRaises(F.FetchError) as caught:
                    F.fetch("http://127.0.0.1:9/", render=True,
                            browser_required=True)
                self.assertNotIsInstance(caught.exception,
                                         F.BrowserUnavailable)

    def test_wait_for_takes_what_a_browser_reads(self):
        """S5 re-review: the selector library's own pseudo-classes, which
        no browser has, are refused before the run; a selector the browser
        cannot read is said as that, not as an element that never came."""
        for value in ("p:contains(Total)", "p:-soup-contains(Total)"):
            with self.subTest(value=value):
                code, _out, err = run(GOOD, "--render", "--wait-for", value)
                self.assertEqual(code, 2)
                self.assertIn("uses a pseudo-class browsers do not have", err)
        import importlib.util
        if importlib.util.find_spec("playwright") is None:
            return
        from playwright.sync_api import TimeoutError as PlaywrightTimeout

        class Page:
            def __init__(self, exc):
                self.exc = exc

            def wait_for_selector(self, *_a, **_k):
                raise self.exc
        with self.assertRaises(F.FetchError) as caught:
            F._wait_for(Page(PlaywrightTimeout("Timeout 30000ms exceeded")),
                        "#x", 30000)
        self.assertIn("no element matched the --wait-for selector within "
                      "30 s", str(caught.exception))
        with self.assertRaises(F.FetchError) as caught:
            F._wait_for(Page(Exception("Page.wait_for_selector: Unexpected "
                                       "token while parsing selector")),
                        "#x", 30000)
        self.assertEqual(str(caught.exception), F.WAIT_FOR_UNREADABLE)
        closed = Exception("Page.wait_for_selector: Target page, context or "
                           "browser has been closed")
        with self.assertRaises(Exception) as caught:
            F._wait_for(Page(closed), "#x", 30000)
        self.assertIs(caught.exception, closed)

    def test_the_still_loading_reason_is_one(self):
        """The CLI reads a page as still loading by the reason's start."""
        self.assertTrue(F.STILL_LOADING.startswith(
            cli._STILL_LOADING_START))
        said = F.STILL_LOADING.format(n=1, cap=8000,
                                      grace=F.SETTLE_GRACE_MS)
        self.assertIn("by the end of the capture's wait (the 8000 ms settle "
                      "cap, and 2000 ms more", said)

    @unittest.skipUnless(os.path.exists("/dev/null"), "/dev/null")
    def test_a_device_is_no_report(self):
        code, _out, err = run(GOOD, "--json", "/dev/null")
        self.assertEqual(code, 2)
        self.assertIn("cannot write /dev/null (--json): it is not a regular "
                      "file (a device or a pipe): name a file; a report on "
                      "standard output would mix with the run's own lines",
                      re.sub(r"\s+", " ", err))

    def test_a_browser_that_is_missing_is_tried_once(self):
        d = tmpdir(self)
        for name in ("a.html", "b.html", "c.html"):
            shutil.copy(GOOD, d / name)
        calls = []

        def fetch(url, **kw):
            calls.append(url)
            raise F.BrowserUnavailable("rendered fetch failed: "
                                       "BrowserType.launch: no executable")
        with mock.patch.object(F, "fetch", fetch):
            code, _out, err = run(d, "--render", "--fail-on", "never",
                                  "--json", d / "r.json")
        self.assertEqual(code, 2, err)
        self.assertEqual(len(calls), 1)
        self.assertIn("so the other 2 page(s) were not tried either", err)
        # Each page's record says whether it was tried (S5 re-review).
        report = json.loads((d / "r.json").read_text(encoding="utf-8"))
        errors = [error["error"] for page in report["pages"]
                  for error in page["errors"]
                  if error["rule_id"] == "(the page)"]
        self.assertEqual(len(errors), 3)
        self.assertEqual(errors[0], "rendered fetch failed: "
                         "BrowserType.launch: no executable")
        for later in errors[1:]:
            self.assertEqual(later, "not tried: the browser --render needs "
                             "could not be used for an earlier page "
                             "(rendered fetch failed: BrowserType.launch: "
                             "no executable)")


class TestTheReportsTables(unittest.TestCase):
    """S5-3: at phone width the tables ran off the page; each now scrolls
    in a region of its own, which a keyboard can reach and which is named
    by the table's caption."""

    def test_each_table_is_in_a_named_region(self):
        d = tmpdir(self)
        run(ROOT / "fixtures" / "bad.html", ROOT / "fixtures" /
            "subtle-bad.html", "--html", d / "r.html", "--fail-on", "never")
        html = (d / "r.html").read_text(encoding="utf-8")
        tables = re.findall(
            r'<div class="table-scroll" role="region" tabindex="0" '
            r'aria-labelledby="(table-\d+)"><table><caption id="([^"]+)">',
            html)
        self.assertEqual(len(tables), html.count("<table"))
        self.assertGreaterEqual(len(tables), 3)
        ids = [region for region, _ in tables]
        self.assertEqual(ids, [caption for _, caption in tables])
        self.assertEqual(len(ids), len(set(ids)))
        css = html[html.index("<style>"):html.index("</style>")]
        self.assertIn("@media (max-width:640px){table{table-layout:auto;"
                      "min-width:600px}", css)
        self.assertTrue(css.rstrip().endswith("}"))


# ---------------------------------------------------------------------------
# S5-3: what a rendered capture waits for
# ---------------------------------------------------------------------------

_ORDERS = b"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Orders</title></head><body>%s<main><div id="root">
<p role="status">Loading orders...</p></div></main><script>
fetch('/api').then(r => r.json()).then(d => {
  document.getElementById('root').innerHTML =
    '<div id="content"><h1>Orders</h1><a href="/o/1"></a></div>';
});
</script></body></html>"""
#: What the page shows before its data arrives, besides the indicator.
_HEADER = b'<header><a href="/">Home</a> <a href="/help">Help</a></header>'


class _SlowAPI:
    """A page that builds its content from /api, which answers after
    `delay` seconds; `header`, what it shows before then besides its
    loading indicator."""

    def __init__(self, delay: float, header: bytes = b""):
        outer = self

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                if self.path == "/api":
                    outer.stop_event.wait(delay)
                    body, kind = b'{"ok": true}', "application/json"
                else:
                    body = _ORDERS % header
                    kind = "text/html; charset=utf-8"
                self.send_response(200)
                self.send_header("Content-Type", kind)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                with contextlib.suppress(OSError):
                    self.wfile.write(body)
        self.stop_event = threading.Event()
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever,
                         daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/"

    def stop(self):
        self.stop_event.set()
        self.server.shutdown()
        self.server.server_close()


class TestTheSettleGrace(unittest.TestCase):
    """S5 re-review: the requests open at the settle cap get
    SETTLE_GRACE_MS more, and so do those they lead to: one that answers
    then is waited for, and the DOM after it; one chained on still, or
    held open, is open at the end, and counted. On a clock of the test's
    own, so it takes no time."""

    def settle(self, open_at):
        """_settle over a page whose data requests open at time t (seconds
        from the start) are open_at(t)."""
        now = [1000.0]
        start = now[0]

        class Data:
            seen = 0

            def __init__(self):
                self.pending, self.last = {}, start

            def _look(self):
                n = open_at(now[0] - start)
                self.pending = dict.fromkeys(range(n))
                if n:
                    self.last = now[0]
                    self.seen = max(self.seen, n)

            def in_flight(self):
                self._look()
                return len(self.pending)

            def quiet_for_ms(self):
                self._look()
                return 0 if self.pending else int(
                    (now[0] - self.last) * 1000)

        class Page:
            def wait_for_timeout(self, ms):
                now[0] += ms / 1000

        doms = []

        def dom(_ctx, _page, _js, args):
            doms.append(round(now[0] - start, 2))
            return {"settled": True}
        with mock.patch("time.monotonic", lambda: now[0]), \
                mock.patch.object(F, "_in_own_world", dom):
            got = F._settle(None, Page(), 500, 8000, Data())
        return got, doms

    def test_an_answer_within_the_grace_is_waited_for(self):
        got, doms = self.settle(lambda t: 1 if t < 8.5 else 0)
        self.assertEqual(got["in_flight"], 0)
        self.assertGreaterEqual(got["waited"], 8900)
        self.assertLess(got["waited"], 10000)
        self.assertGreater(doms[-1], 8.9)        # the DOM, after the answer

    def test_one_chained_on_still_is_counted(self):
        got, _ = self.settle(lambda t: 0 if 8.5 <= t < 8.6 else 1)
        self.assertEqual(got["in_flight"], 1)
        self.assertGreaterEqual(got["waited"], 9950)

    def test_one_held_open_is_counted(self):
        got, _ = self.settle(lambda t: 1)
        self.assertEqual(got["in_flight"], 1)
        self.assertLessEqual(got["waited"], 10100)

    def test_an_answer_before_the_cap_needs_no_grace(self):
        got, _ = self.settle(lambda t: 1 if t < 3 else 0)
        self.assertEqual(got["in_flight"], 0)
        self.assertLess(got["waited"], 4000)


@unittest.skipUnless(HAVE_BROWSER, _WHY)
class TestTheDataRequests(unittest.TestCase):
    """S5-3: a capture waited only for the DOM to stop changing, so a page
    that showed "Loading" while its data was on the way was read as that,
    and passed."""

    def capture(self, delay, *extra, header=b""):
        site = _SlowAPI(delay, header)
        self.addCleanup(site.stop)
        d = tmpdir(self)
        code, _out, err = run("--url", site.url, "--json", d / "r.json",
                              "--fail-on", "tier1", *extra)
        report = json.loads((d / "r.json").read_text(encoding="utf-8"))
        return code, err, report["pages"][0]

    def test_an_answer_within_the_cap_is_waited_for(self):
        code, err, page = self.capture(1.5)
        self.assertEqual(code, 1, err)
        self.assertIn("bb-link-name", [f["rule_id"] for f in page["findings"]
                                       if f["verdict"] == "fail"])
        wait = page["fetch"]["wait"]
        self.assertEqual(wait["strategy"], "load+scroll+dom-and-data-settle")
        self.assertGreaterEqual(wait["data_requests"], 1)
        self.assertEqual(wait["data_requests_open"], 0)
        self.assertGreaterEqual(wait["waited_ms"], 1400)

    def test_a_page_still_loading_is_not_evaluated(self):
        code, err, page = self.capture(15, header=_HEADER)
        self.assertEqual(code, 2, err)
        self.assertIn("still loading when captured: 1 of the page's data "
                      "requests (fetch or XHR) had not answered", err)
        self.assertEqual(page["fetch"]["wait"]["data_requests_open"], 1)
        self.assertIs(page["score"]["evaluable"], False)
        self.assertIn("still loading when captured",
                      page["score"]["not_evaluable_reason"])

    def test_a_shell_still_loading_is_empty_and_says_why(self):
        code, err, page = self.capture(15)
        self.assertEqual(code, 2, err)
        self.assertIn("empty when captured", err)
        self.assertIn("note: 1 of the page's data requests (fetch or XHR) "
                      "had not answered when it was captured", err)

    def test_wait_for_names_what_it_shows_once_loaded(self):
        code, err, page = self.capture(12, "--wait-for", "#content")
        self.assertEqual(code, 1, err)
        self.assertEqual(page["fetch"]["wait"]["wait_for"], "#content")
        self.assertIn("bb-link-name", [f["rule_id"] for f in page["findings"]
                                       if f["verdict"] == "fail"])

    def test_a_line_of_the_captured_page_says_so(self):
        site = _SlowAPI(0)
        self.addCleanup(site.stop)
        d = tmpdir(self)
        run("--url", site.url, "--html", d / "r.html", "--fail-on", "never")
        html = (d / "r.html").read_text(encoding="utf-8")
        self.assertRegex(html, r"line \d+ of the captured page")


# ---------------------------------------------------------------------------
# S5-4
# ---------------------------------------------------------------------------

class TestLintExclude(unittest.TestCase):
    """S5-4: --exclude, what a folder scan leaves out."""

    BAD = 'export const A = () => <a href="#" onClick={go}>x</a>;\n'

    def setUp(self):
        from bellbriar_harness import lint
        self.lint = lint
        self.d = tmpdir(self)
        for rel in ("src/app/a.tsx", "src/app/a.stories.tsx",
                    "src/legacy/b.tsx", "src/__tests__/c.tsx",
                    "other/legacy.tsx"):
            (self.d / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.d / rel).write_text(self.BAD, encoding="utf-8")

    def lint_json(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = self.lint.main([str(a) for a in argv])
        data = json.loads(out.getvalue()) if out.getvalue().strip() \
            .startswith("{") else None
        return code, data, err.getvalue()

    def linted(self, data):
        return sorted(Path(f["path"]).relative_to(self.d).as_posix()
                      for f in data["findings"])

    def test_by_name_by_path_and_folders_only(self):
        code, data, err = self.lint_json(
            self.d, "--format", "json", "--fail-on", "never",
            "--exclude", "*.stories.tsx", "--exclude", "src/legacy",
            "--exclude", "__tests__/")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.linted(data), ["other/legacy.tsx",
                                             "src/app/a.tsx"])
        self.assertIn("--exclude left out 2 folder(s), not entered, and 1 "
                      "file(s) besides", data["notes"])

    def test_every_pattern_that_matches_is_credited(self):
        """S5 re-review: two patterns that both match a folder were said to
        have matched nothing but the first; and a build folder named was
        skipped before the pattern was read."""
        (self.d / "node_modules" / "x").mkdir(parents=True)
        (self.d / "node_modules" / "x" / "y.tsx").write_text(
            self.BAD, encoding="utf-8")
        code, data, err = self.lint_json(
            self.d, "--format", "json", "--fail-on", "never",
            "--exclude", "src/legacy", "--exclude", "legacy",
            "--exclude", "node_modules")
        self.assertEqual(code, 0, err)
        self.assertNotIn("matched nothing", err)
        self.assertFalse([n for n in data["notes"]
                          if "matched nothing" in n])
        self.assertIn("--exclude left out 2 folder(s), not entered, and 0 "
                      "file(s) besides", data["notes"])
        self.assertNotIn("src/legacy/b.tsx", self.linted(data))

    def test_a_pattern_that_matched_nothing_is_said(self):
        code, data, err = self.lint_json(
            self.d, "--format", "json", "--fail-on", "never", "--exclude",
            "srcc/legacy")
        self.assertIn("--exclude 'srcc/legacy' matched nothing", data["notes"])
        self.assertIn("matched nothing", err)

    def test_absolute_and_named(self):
        named = self.d / "src" / "legacy" / "b.tsx"
        code, data, err = self.lint_json(
            named, self.d, "--format", "json", "--fail-on", "never",
            "--exclude", str(self.d / "src"))
        # The named file is linted all the same.
        self.assertEqual(self.linted(data), ["other/legacy.tsx",
                                             "src/legacy/b.tsx"])

    def test_nothing_left_and_an_empty_pattern(self):
        code, _data, err = self.lint_json(self.d, "--exclude", "*")
        self.assertEqual(code, 2)
        self.assertIn("what --exclude leaves out", err)
        code, _data, err = self.lint_json(self.d, "--exclude", "")
        self.assertEqual(code, 2)
        self.assertIn("names nothing", err)


class TestTheRuleIndex(unittest.TestCase):
    """S5-4: a page's own style rules are tried on an element only when it
    has what their rightmost compound requires: attributes and one-compound
    :is() and :where() too now; and a sibling list is walked once per
    `A ~ B` rule, not once per element."""

    def test_keys(self):
        from bellbriar_harness.style import _rightmost_key as key
        for sel, want in (
                ("[data-x='3']", ("attr", "data-x")),
                ("[lang|=en]", ("attr", "lang")),
                ("[ns|href]", None), ("[*|href]", None), ("[|href]", None),
                ("a[href]", ("tag", "a")), ("[x].b", ("class", "b")),
                (":where(h1)", ("tag", "h1")), (":IS(.Btn)", ("class", "btn")),
                ('.prose :where(h1):not(:where([class~="not-prose"] *))',
                 ("tag", "h1")),
                (":is(h1, h2)", None), (":where(a b)", None),
                (":not(.a)", None), ("*", None)):
            with self.subTest(sel=sel):
                self.assertEqual(key(sel), want)

    def test_a_key_is_looked_for_one_deep(self):
        """S5 final check (R6H-10): a key inside nested :is() cost a scan
        per level, and 8,000 rules nested 17 deep took 6 s; past one level
        a rule has no key, and is tried on every element."""
        from bellbriar_harness.style import _rightmost_key as key
        self.assertEqual(key(".prose :WHERE(h1)"), ("tag", "h1"))
        self.assertEqual(key(":is(.a)"), ("class", "a"))
        self.assertIsNone(key(":is(:where(.a))"))
        self.assertIsNone(key(":is(" * 17 + ".a" + ")" * 17))
        from bellbriar_harness import html5
        from bellbriar_harness.style import PageStyles
        soup = html5.parse(
            '<!doctype html><html lang="en"><head><title>x</title><style>'
            + ":is(" * 6 + ".a" + ")" * 6 + '{display:none}</style></head>'
            '<body><p class="a" id="p">x</p><p id="q">y</p></body></html>')
        styles = PageStyles(soup)
        self.assertNotEqual(styles._keys(soup.find(id="p")), frozenset())
        self.assertEqual(styles._keys(soup.find(id="q")), frozenset())

    def test_the_split(self):
        from bellbriar_harness.style import _last_sibling_split as split
        self.assertEqual(split(".s > :not([hidden]) ~ :not([hidden])"),
                         (".s > :not([hidden])", ":not([hidden])"))
        self.assertEqual(split("a b ~ c"), ("a b", "c"))
        for sel in ("a ~ b c", ":is(a ~ b) c", "a + b", "& ~ b",
                    ":scope ~ b", "[x='~'] b"):
            with self.subTest(sel=sel):
                self.assertIsNone(split(sel))

    def test_an_escaped_scope_and_a_no_break_space(self):
        """S5 re-review: `:\\73 cope` is :scope to CSS, the root in a
        document's stylesheet, so no `~` rule is split at it; and U+00A0 is
        a name's character in CSS, not white space, as is an escaped
        space, so neither is stripped from a selector's ends."""
        from bellbriar_harness.style import (_last_sibling_split as split,
                                             _rightmost_key as key,
                                             _scope_as)
        for sel in (":\\73 cope ~ b", ":SC\\4f PE ~ b", ":sc\\ope ~ b"):
            with self.subTest(sel=sel):
                self.assertIsNone(split(sel))
                self.assertEqual(_scope_as(sel, ":root"), ":root ~ b")
        self.assertEqual(_scope_as("a::scope", ":root"), "a::scope")
        self.assertEqual(split(".lede\u00a0~ .cta"), (".lede\u00a0", ".cta"))
        self.assertEqual(split("#tip\\  ~ .cta"), ("#tip\\ ", ".cta"))
        self.assertEqual(key(":where(#label\u00a0)"), ("id", "label\u00a0"))
        self.assertEqual(key(".lede\u00a0"), ("class", "lede\u00a0"))

    def _document(self):
        from bellbriar_harness import html5
        rows = "".join(
            f'<li class="c{i % 7}"{" hidden" if i % 11 == 0 else ""}>{i}'
            '</li>' for i in range(400))
        return html5.parse('<!doctype html><html lang="en"><head><title>x'
                           f'</title></head><body><ul class="s">{rows}</ul>'
                           '<p class="c1">x</p><div class="c2">y</div>'
                           '</body></html>')

    def test_as_soupsieve_matches(self):
        import soupsieve
        from bellbriar_harness.style import (_SiblingPattern,
                                             _last_sibling_split)
        soup = self._document()
        elements = soup.find_all(True)
        for sel in (".s > :not([hidden]) ~ :not([hidden])", "li ~ li",
                    ".c3 ~ *", "[hidden] ~ .c1", "ul li.c5 ~ li:not(.c6)",
                    "li:nth-child(3n) ~ li", "p ~ div", "ul ~ p",
                    ":not(li) ~ div", "li:has(+ [hidden]) ~ li"):
            with self.subTest(sel=sel):
                left, right = _last_sibling_split(sel)
                mine = _SiblingPattern(soupsieve.compile(left),
                                       soupsieve.compile(right))
                theirs = soupsieve.compile(sel)
                # In reverse order too: the memo must not depend on it.
                for el in elements[::-1] + elements:
                    self.assertEqual(mine.match(el), theirs.match(el),
                                     (sel, el.name, el.get("class")))

    def test_a_long_list_is_walked_once(self):
        import soupsieve
        from bellbriar_harness.style import _SiblingPattern
        soup = self._document()
        tried = []
        left = soupsieve.compile(".nothing")

        class Counting:
            def match(self, el):
                tried.append(el)
                return left.match(el)
        pattern = _SiblingPattern(Counting(), soupsieve.compile("li"))
        items = soup.find_all("li")
        self.assertFalse(any(pattern.match(el) for el in items))
        self.assertLessEqual(len(tried), len(items))      # not 400 * 399 / 2

    def test_what_it_keeps_is_one_number_for_each_parent(self):
        """S5 re-review: the memo held an entry for every element, for
        each rule; it holds one for each parent tried, and the places,
        shared by a page's rules, one set for each parent."""
        import soupsieve
        from bellbriar_harness.style import _Places, _SiblingPattern
        soup = self._document()
        places = _Places()
        patterns = [_SiblingPattern(soupsieve.compile(left),
                                    soupsieve.compile(":not([hidden])"),
                                    places)
                    for left in (".c1", ".c2", ".nothing", "li", "p")]
        elements = soup.find_all(True)
        for pattern in patterns:
            for el in elements:
                pattern.match(el)
        parents = {id(el.parent) for el in elements}
        for pattern in patterns:
            self.assertLessEqual(len(pattern._first), len(parents))
        self.assertEqual(len(places._known), len(parents))
        self.assertTrue(all(isinstance(v, int)
                            for p in patterns for v in p._first.values()))

    def test_a_page_with_rules_on_siblings(self):
        """The page's index matches as soupsieve does, its rules sharing
        the places."""
        from bellbriar_harness import html5
        from bellbriar_harness.style import PageStyles
        soup = html5.parse(
            '<!doctype html><html lang="en"><head><title>x</title><style>'
            '.a ~ .b{display:none}.c ~ li{visibility:hidden}'
            '.a ~ :not([hidden]){display:none}</style></head><body><ul>'
            '<li class="b" id="one">1</li><li class="a">2</li>'
            '<li class="b" id="three">3</li><li class="c">4</li>'
            '<li id="five">5</li></ul></body></html>')
        styles = PageStyles(soup)
        marks = {el["id"]: styles._keys(el) for el in soup.find_all("li")
                 if el.has_attr("id")}
        self.assertEqual(marks["one"], frozenset())
        self.assertNotEqual(marks["three"], frozenset())
        self.assertNotEqual(marks["five"], frozenset())
        self.assertEqual(len(styles._places._known), 1)


class TestThePageBudget(unittest.TestCase):
    """S5-4: a page whose analysis runs past its budget is stopped, and is
    NOT EVALUATED, not held for as long as it takes."""

    def test_one_page_of_a_run_past_its_budget(self):
        """S5 re-review: as for a page that could not be read, the run
        exits 2 and writes no evidence bundle; the other page is read."""
        import time
        from bellbriar_harness import budget
        d = tmpdir(self)
        shutil.copy(GOOD, d / "a.html")
        shutil.copy(GOOD, d / "b.html")
        real, calls = budget.begin, []

        def begin():
            calls.append(1)
            if len(calls) == 2:                  # the second page's clock
                return budget._DEADLINE.set((time.monotonic() - 1, 120))
            return real()
        with mock.patch.object(budget, "begin", begin):
            code, _out, err = run(d, "--fail-on", "never", "--bundle",
                                  d / "b.json", "--json", d / "r.json")
        self.assertEqual(code, 2, err)
        self.assertFalse((d / "b.json").exists())
        self.assertIn("ran past the 120-second budget for one page", err)
        report = json.loads((d / "r.json").read_text(encoding="utf-8"))
        evaluable = {page["path"]: page["score"]["evaluable"]
                     for page in report["pages"]}
        self.assertEqual(sorted(evaluable.values()), [False, True])

    def test_a_page_past_its_budget(self):
        from bellbriar_harness import budget, engine
        token = budget.SECONDS.set(0.0)
        try:
            page = engine.run_page(GOOD.read_bytes(), "good.html",
                                   engine.load_rulebook())
        finally:
            budget.SECONDS.reset(token)
        self.assertFalse(page.evaluable)
        self.assertEqual(page.results, [])
        self.assertIn("ran past the 0-second budget for one page "
                      "(--page-budget)", page.not_evaluable_reason)
        self.assertIn("that is not a pass", page.not_evaluable_reason)

    def test_within_it_nothing_changes(self):
        from bellbriar_harness import engine
        rulebook = engine.load_rulebook()
        first = engine.run_page(GOOD.read_bytes(), "good.html", rulebook)
        self.assertTrue(first.evaluable)
        self.assertTrue(first.results)

    def test_the_option(self):
        for value in ("5", "0", "nan", "inf", "-1", "x", "90000"):
            with self.subTest(value=value):
                code, _out, err = run(GOOD, "--page-budget", value)
                self.assertEqual(code, 2, err)
                self.assertIn("--page-budget", err)
        code, _out, err = run(GOOD, "--page-budget", "10", "--fail-on",
                              "tier1")
        self.assertEqual(code, 0, err)

    def test_the_cascade_looks_at_the_clock(self):
        text = _text("src/bellbriar_harness/style.py")
        body = text[text.index("    def _keys(self, el)"):]
        body = body[:body.index("\n    def ")]
        self.assertIn("check()", body)
        engine = _text("src/bellbriar_harness/engine.py")
        body = engine[engine.index("def _run_check("):]
        self.assertIn("check()", body[:body.index("\ndef ")])


class TestUntestedLibraries(unittest.TestCase):
    """S5-4 (L134): a run with library versions outside the ranges this
    release declares says so before it starts, comparing versions as pip
    does (S5 re-review)."""

    def test_the_ranges_are_the_packages(self):
        sys.path.insert(0, str(ROOT / "tools"))
        self.addCleanup(sys.path.remove, str(ROOT / "tools"))
        import make_example_bundle as M
        from bellbriar_harness import support
        declared = M.declared_ranges()
        for name, clauses in support.LIBRARY_RANGES.items():
            with self.subTest(name=name):
                self.assertEqual(list(clauses), declared[name][1])
        self.assertEqual(set(support.LIBRARY_RANGES),
                         {"beautifulsoup4", "justhtml", "soupsieve"})
        self.assertIn('browser = ["playwright==1.63.0"]',
                      _text("pyproject.toml"))
        self.assertEqual(support.BROWSER_RANGES,
                         {"playwright": (("==", (1, 63, 0)),)})

    def test_what_is_said(self):
        from bellbriar_harness.support import untested_libraries as u
        self.assertEqual(u({"justhtml": "3.13.0", "soupsieve": "2.9.2",
                            "beautifulsoup4": "4.15.0", "expat": "2.7.1"}),
                         [])
        self.assertEqual(u({"soupsieve": "2.10", "justhtml": None,
                            "playwright": "1.56.0"}), [
            "justhtml: not found (declared ==3.13.0)",
            "soupsieve 2.10 (declared >=2.9.2,<2.10)"])
        self.assertEqual(u({"playwright": "1.64.0"}, browser=True),
                         ["playwright 1.64.0 (declared ==1.63.0)"])
        self.assertEqual(u({"soupsieve": "3.0.0rc1"}),
                         ["soupsieve 3.0.0rc1 (declared >=2.9.2,<2.10)"])
        self.assertEqual(u({"beautifulsoup4": "5.0.0"}),
                         ["beautifulsoup4 5.0.0 (declared >=4.12,<5)"])

    def test_versions_are_read_as_pip_reads_them(self):
        """A post-release or a local label is the release pip takes it for;
        a pre-release of the upper bound is below it, but outside it as pip
        reads `<` (PEP 440); `==` takes the release alone."""
        from bellbriar_harness.support import untested_libraries as u
        for version in ("2.9.2", "2.9.2.post1", "2.9.2+ubuntu1", "2.9.7"):
            with self.subTest(version=version):
                self.assertEqual(u({"soupsieve": version}), [])
        for version in ("2.9.1", "2.9.2rc1", "2.10.0rc1", "2.10.0.dev1",
                        "2.10", "3.0.1", "two"):
            with self.subTest(version=version):
                self.assertEqual(len(u({"soupsieve": version})), 1)
        self.assertEqual(u({"justhtml": "3.13.0+local"}), [])
        for version in ("3.13.0.post1", "3.13.0rc1", "3.13.1"):
            with self.subTest(version=version):
                self.assertEqual(len(u({"justhtml": version})), 1)

    def test_no_playwright_is_not_a_warning(self):
        """Playwright is the browser extra's: a run without it says so on
        its own (a URL run reads the server's HTML), not as a version."""
        from bellbriar_harness.support import untested_libraries as u
        self.assertEqual(u({"playwright": None}, browser=True), [])
        self.assertEqual(u({"playwright": "1.63.0"}, browser=True), [])

    def test_a_run_says_so(self):
        from bellbriar_harness import engine
        real = engine.tool_record

        def record(*args, **kw):
            tool = real(*args, **kw)
            tool["libraries"]["soupsieve"] = "3.0.1"
            return tool
        with mock.patch.object(engine, "tool_record", record):
            code, _out, err = run(GOOD, "--fail-on", "tier1")
        self.assertEqual(code, 0, err)
        self.assertIn("WARNING: this run uses library versions outside the "
                      "ranges bellbriar-harness", err)
        self.assertIn("soupsieve 3.0.1 (declared >=2.9.2,<2.10)", err)
        from bellbriar_harness import __version__
        self.assertIn("pip install --force-reinstall 'bellbriar-harness=="
                      f"{__version__}'", err)
        code, _out, err = run(GOOD, "--fail-on", "tier1")
        self.assertNotIn("library versions", err)


class TestTheWHATWGNotice(unittest.TestCase):
    """S5-4: the Encoding Standard's labels and indexes shipped without
    their copyright notice and license."""

    def test_the_notice_travels_with_the_data(self):
        data = _text("src/bellbriar_harness/encodings_data.py")
        self.assertTrue(data.startswith(
            "# The labels and indexes in this module are the WHATWG "
            "Encoding Standard's"))
        head = data[:data.index('"""')]
        self.assertIn("# Copyright \u00a9 WHATWG (Apple, Google, Mozilla, "
                      "Microsoft).", head)
        self.assertIn("# 3. Neither the name of the copyright holder", head)
        license_text = _text("src/bellbriar_harness/"
                             "LICENSE-whatwg-encoding.txt")
        self.assertTrue(license_text.startswith(
            "Copyright \u00a9 WHATWG (Apple, Google, Mozilla, Microsoft)."))
        self.assertIn("BSD 3-Clause License", license_text)
        notice = _flat("NOTICE")
        self.assertIn("WHATWG Encoding Standard", notice)
        self.assertIn("src/bellbriar_harness/LICENSE-whatwg-encoding.txt",
                      notice)
        pyproject = _text("pyproject.toml")
        self.assertIn('"src/bellbriar_harness/LICENSE-whatwg-encoding.txt"',
                      pyproject)
        self.assertIn('"LICENSE-whatwg-encoding.txt"]', pyproject)
        self.assertIn("LICENSE-whatwg-encoding.txt", _flat("README.md"))
        self.assertIn(LICENSE_HEADER_FIRST, _text("tools/make_encodings.py"))


LICENSE_HEADER_FIRST = ("# The labels and indexes in this module are the "
                        "WHATWG Encoding Standard's")


# ---------------------------------------------------------------------------
# S5-5
# ---------------------------------------------------------------------------

def _workflow(name: str) -> dict:
    try:
        import yaml
    except ImportError:
        raise unittest.SkipTest("PyYAML is not installed")
    return yaml.safe_load(_text(f".github/workflows/{name}"))


class TestTheReleaseAndCI(unittest.TestCase):
    """S5-5: the ARM64 image was built under emulation and never run, the
    image published was a second build from a cache, and nothing attested
    the files or the image."""

    def test_ci_runs_the_image_on_each_architecture(self):
        job = _workflow("bellbriar-eval.yml")["jobs"]["image"]
        self.assertEqual(job["strategy"]["matrix"]["runner"],
                         ["ubuntu-latest", "ubuntu-24.04-arm"])
        runs = [s.get("run", "") for s in job["steps"]]
        sysctl = next(i for i, r in enumerate(runs)
                      if "apparmor_restrict_unprivileged_userns=0" in r)
        check = next(i for i, r in enumerate(runs) if "image_check.py" in r)
        self.assertLess(sysctl, check)

    def test_the_build_records_its_times_and_tools(self):
        steps = _workflow("release.yml")["jobs"]["build"]["steps"]
        runs = "\n".join(s.get("run", "") for s in steps)
        self.assertIn('echo "SOURCE_DATE_EPOCH=$epoch" >> "$GITHUB_ENV"',
                      runs)
        self.assertIn('git ls-files -z | xargs -0 touch -h -d "@$epoch"',
                      runs)
        for line in ("python -VV", "python -m pip freeze --all",
                     "sha256sum dist/*"):
            self.assertIn(line, runs)
        order = [s.get("run", "") for s in steps]
        self.assertLess(
            next(i for i, r in enumerate(order) if "SOURCE_DATE_EPOCH" in r),
            next(i for i, r in enumerate(order) if r == "python -m build"))
        # What the comment says, exactly (S5 re-review): the sdist's
        # folders, generated files and gzip header keep the build's clock,
        # and the isolated build environment is not printed.
        text = re.sub(r"\s*#\s*", " ", _text(".github/workflows/release.yml"))
        self.assertIn("its folders, the files the build writes into it "
                      "(PKG-INFO, the egg-info) and its gzip header keep "
                      "this machine's clock", text)
        self.assertIn("builds in an isolated environment of its own, which "
                      "is not printed", text)

    def test_the_attestations(self):
        jobs = _workflow("release.yml")["jobs"]
        attest = jobs["attest"]
        self.assertEqual(set(attest["needs"]),
                         {"build", "pypi", "image", "public"})
        self.assertIn("attest", jobs["release"]["needs"])
        steps = [s for s in attest["steps"]
                 if "attest-build-provenance" in s.get("uses", "")]
        self.assertEqual([s["with"] for s in steps], [
            {"subject-path": "dist/*"},
            {"subject-name": "ghcr.io/bellbriar/harness",
             "subject-digest": "${{ needs.image.outputs.digest }}",
             "push-to-registry": True, "create-storage-record": False}])
        self.assertIn("gh attestation verify",
                      json.dumps(jobs["release"]["steps"]))

    def test_the_hashes_tool(self):
        """S5-5: tools/hash_requirements.py writes a hash for each file the
        image's pip would install, on both architectures, under each pin,
        and keeps the pins and the comments above them."""
        sys.path.insert(0, str(ROOT / "tools"))
        self.addCleanup(sys.path.remove, str(ROOT / "tools"))
        import hash_requirements as H
        d = tmpdir(self)
        text = _text("docker/requirements.txt")
        (d / "r.txt").write_text(text, encoding="utf-8")
        header, pins = H.read_pins(text)
        self.assertIn(("playwright", "1.63.0"), pins)
        seen = []

        def download(pins, arch, dest):
            seen.append(arch)
            for name, version in pins:
                tag = (f"cp312-cp312-manylinux_2_28_{arch}"
                       if name in ("cffi", "greenlet") else "py3-none-any")
                (dest / f"{name}-{version}-{tag}.whl").write_bytes(
                    f"{name} {version} {tag}".encode())
            return 0
        with mock.patch.object(H, "download", download), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(H.main([str(d / "r.txt")]), 0)
        self.assertEqual(seen, ["x86_64", "aarch64"])
        out = (d / "r.txt").read_text(encoding="utf-8")
        again_header, again = H.read_pins(out)
        self.assertEqual((again_header, again), (header, pins))
        block = out[out.index("cffi=="):out.index("cryptography==")]
        self.assertEqual(block.count("--hash=sha256:"), 2)     # two arches
        block = out[out.index("soupsieve=="):out.index("typing_extensions")]
        self.assertEqual(block.count("--hash=sha256:"), 1)     # one wheel
        self.assertIn("manylinux1_x86_64", H.platforms("x86_64"))

        def missing(pins, arch, dest):
            return 0
        with mock.patch.object(H, "download", missing), \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(H.main([str(d / "r.txt")]), 1)

    def test_the_hashes_tool_names_every_platform_pip_takes(self):
        """S5 re-review: `pip download --platform` takes each tag as given,
        and the list left out most manylinux_2_N tags (2_37, 2_33, ...), so
        a pin whose wheel was tagged so stopped the tool. Every one from
        glibc 2.39 down, as pip's packaging lists them."""
        sys.path.insert(0, str(ROOT / "tools"))
        self.addCleanup(sys.path.remove, str(ROOT / "tools"))
        import hash_requirements as H
        x86, arm = H.platforms("x86_64"), H.platforms("aarch64")
        self.assertEqual(x86[:2], ["manylinux_2_39_x86_64",
                                   "manylinux_2_38_x86_64"])
        self.assertEqual(
            [t for t in x86 if not t.startswith("manylinux_2_")],
            ["manylinux2014_x86_64", "manylinux2010_x86_64",
             "manylinux1_x86_64", "linux_x86_64"])
        self.assertEqual(len(x86), 35 + 4)          # 2_39 .. 2_5, and four
        self.assertEqual(x86.index("manylinux2014_x86_64"),
                         x86.index("manylinux_2_17_x86_64") + 1)
        self.assertEqual(arm[-3:], ["manylinux_2_17_aarch64",
                                    "manylinux2014_aarch64", "linux_aarch64"])
        self.assertEqual(len(arm), 23 + 2)          # 2_39 .. 2_17, and two
        try:
            from pip._vendor.packaging import _manylinux as M
        except ImportError:                          # pragma: no cover
            return
        with mock.patch.object(M, "_get_glibc_version", lambda: (2, 39)), \
                mock.patch.object(M, "_is_compatible", lambda *a: True):
            for arch, mine in (("x86_64", x86), ("aarch64", arm)):
                try:                 # its signature is pip's own to change
                    theirs = list(M.platform_tags(f"linux_{arch}", arch))
                except TypeError:                    # pragma: no cover
                    return
                with self.subTest(arch=arch):
                    self.assertEqual(theirs + [f"linux_{arch}"], mine)

    def test_the_images_are_tagged_from_the_ones_that_ran(self):
        jobs = _workflow("release.yml")["jobs"]
        run = next(s["run"] for s in jobs["image"]["steps"]
                   if s.get("id") == "index")
        self.assertIn('[ "${#refs[@]}" -eq 2 ]', run)
        self.assertIn("imagetools create", run)
        self.assertNotIn("build-push-action",
                         json.dumps(jobs["image"]["steps"]))


# ---------------------------------------------------------------------------
# S5-6
# ---------------------------------------------------------------------------

class TestTheDocuments(unittest.TestCase):
    """S5-6: what an adopting organization asked the documents."""


    def test_the_sandbox_is_said_as_shown(self):
        """S5 re-review: README said the sandbox starts under the profile,
        which CI has yet to show (L81); and the image holds no profile:
        the repository and the Action ship it."""
        self.assertIn("the sandbox can start, though this project's CI has "
                      "yet to show it starting so (docs/ROADMAP.md, L81)",
                      _flat("README.md"))
        self.assertIn("The harness's CI has yet to show the sandbox starting "
                      "so", _flat("action/README.md"))
        roadmap = _flat("docs/ROADMAP.md")
        self.assertIn("the repository and the Action ship Playwright's "
                      "seccomp profile", roadmap)
        self.assertNotIn("the image and the Action ship", roadmap)
    def test_personal_data(self):
        evidence = _flat("docs/EVIDENCE.md")
        self.assertIn("## Personal data in what a run writes", evidence)
        for words in ("Findings quote the page.", "Snapshots are whole "
                      "pages.", "URLs keep their paths.", "Credentials are "
                      "not recorded.", "Neither the `--http-user` user name "
                      "nor its password is written anywhere"):
            self.assertIn(words, evidence)
        self.assertIn('"Personal data in what a run writes"',
                      _flat("README.md"))

    def test_the_run_never_records_the_http_user(self):
        server = _BasicAuth()
        self.addCleanup(server.stop)
        d = tmpdir(self)
        with mock.patch.dict(os.environ,
                             {"BELLBRIAR_HTTP_PASSWORD": "s3cretpw-s5"}):
            code, _out, err = run("--url", server.url, "--no-render",
                                  "--http-user", "alice-s5-user", "--json",
                                  d / "r.json", "--bundle", d / "b.json",
                                  "--html", d / "r.html", "--fail-on",
                                  "never")
        self.assertEqual(code, 0, err)
        for name in ("r.json", "b.json", "r.html"):
            text = (d / name).read_text(encoding="utf-8")
            self.assertNotIn("alice-s5-user", text)
            self.assertNotIn("s3cretpw-s5", text)
        report = json.loads((d / "r.json").read_text(encoding="utf-8"))
        self.assertIn("http-credentials",
                      report["pages"][0]["fetch"]["redacted"])

    def test_in_ci(self):
        readme = _flat("README.md")
        self.assertIn("**In CI.** The gate (`--fail-on`, `tier1` by "
                      "default) counts the FAIL findings in the site's own "
                      "markup", readme)
        for words in ("`--require-render` makes that exit 2",
                      "`--wait-for SELECTOR` waits up to 30 seconds",
                      "`--page-budget` seconds (120 by default)",
                      "`--render-deadline` seconds (120 by default)"):
            self.assertIn(words, readme)
        self.assertIn("Source, documents and issues: "
                      "https://github.com/bellbriar/harness", readme)

    def test_the_wait_record_is_documented_member_by_member(self):
        from bellbriar_harness.bundle import RECORD_MEMBERS
        text = _text("docs/REPORT.md")
        table = text[text.index("The capture's `wait`"):]
        table = table[:table.index("\n\n", table.index("|"))]
        fields = set(re.findall(r"^\| `([a-z_]+)` \|", table, re.M))
        self.assertEqual(fields, RECORD_MEMBERS["pages[].fetch.wait"])
        from bellbriar_harness import fetch
        self.assertIn(f"`quiet_ms` | integer | How long the page must stay "
                      f"still: {fetch.DEFAULT_SETTLE_MS}", table)
        self.assertIn(f"`cap_ms` | integer | The longest that wait lasts: "
                      f"{fetch.DEFAULT_SETTLE_CAP_MS}", table)
        self.assertIn(f"{fetch.SETTLE_GRACE_MS} ms more", table)

    def test_a_bundle_says_each_findings_basis(self):
        from bellbriar_harness.bundle import RECORD_MEMBERS
        self.assertIn("verdict_basis", RECORD_MEMBERS["pages[].findings[]"])
        d = tmpdir(self)
        run(ROOT / "fixtures" / "bad.html", "--bundle", d / "b.json",
            "--json", d / "r.json", "--fail-on", "never")
        bundle = json.loads((d / "b.json").read_text(encoding="utf-8"))
        report = json.loads((d / "r.json").read_text(encoding="utf-8"))
        got = [f["verdict_basis"] for p in bundle["pages"]
               for f in p["findings"]]
        want = [f["verdict_basis"] for p in report["pages"]
                for f in p["findings"]]
        self.assertEqual(got, want)
        self.assertLessEqual({"sc", "heuristic"}, set(got))
        # The report's members, as EVIDENCE.md gives them.
        shown = set(report["pages"][0]["findings"][0])
        self.assertEqual(RECORD_MEMBERS["pages[].findings[]"],
                         (shown - {"owned", "about", "fingerprint",
                                   "in_baseline"}) | {"scored"})
        self.assertIn("with `scored` in place of the report's `owned` and "
                      "without `about`, `fingerprint` and `in_baseline`",
                      _flat("docs/EVIDENCE.md"))

    def test_the_stability_promise_is_said_once(self):
        self.assertIn("A minor release (1.1.0: CHANGELOG.md, \"Versions\") "
                      "may add fields", _flat("docs/REPORT.md"))
        self.assertIn("A minor release (1.1.0) may add options, fields",
                      _flat("CHANGELOG.md"))

    def test_the_signer_is_the_signers_word(self):
        from bellbriar_harness import evidence_cli
        out = io.StringIO()
        with contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(io.StringIO()):
            evidence_cli.main(["inspect", str(
                ROOT / "examples" / "evidence" /
                "signed-bundle-example.json")])
        self.assertIn("(the signer's own words, not checked)",
                      out.getvalue())
        self.assertIn("The library's `bundle.verify_bundle`, which checks "
                      "the specification's test vectors, accepts the test "
                      "key", _flat("docs/MEASUREMENT-AND-EVIDENCE-GUIDE.md"))

    def test_the_metadata(self):
        try:
            import tomllib
        except ImportError:
            raise unittest.SkipTest("tomllib needs Python 3.11")
        project = tomllib.loads(_text("pyproject.toml"))["project"]
        status = [c for c in project["classifiers"]
                  if c.startswith("Development Status ::")]
        pre = re.search(r"(a|b|rc)\d+$", project["version"])
        self.assertEqual(status, ["Development Status :: 4 - Beta"] if pre
                         else ["Development Status :: 5 - Production/Stable"])
        self.assertEqual(project["urls"]["Changelog"],
                         "https://github.com/bellbriar/harness/blob/main/"
                         "CHANGELOG.md")
        self.assertIn("Programming Language :: Python :: 3.15",
                      project["classifiers"])

    def test_the_actions_readme(self):
        text = _flat("action/README.md")
        for words in ("`pipx install 'bellbriar-harness[browser]'`",
                      "then `bellbriar-eval --install-browser`",
                      "a pre-release such as `1.0.0rc1`, which `1` never "
                      "follows", "- `sandbox`: `off` (the default) or "
                      "`required`.", "pins both: the Action by its commit",
                      "(`--network host`)", "its `.git` read-only"):
            self.assertIn(words, text)


class _BasicAuth:
    """A page behind HTTP Basic authentication."""

    PAGE = (b'<!doctype html><html lang="en"><head><title>Acct</title>'
            b'</head><body><main><h1>Account</h1><img src="/p.png">'
            b'</main></body></html>')

    def __init__(self):
        import base64
        want = "Basic " + base64.b64encode(
            b"alice-s5-user:s3cretpw-s5").decode()
        page = self.PAGE

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                if self.headers.get("Authorization") != want:
                    self.send_response(401)
                    self.send_header("WWW-Authenticate", 'Basic realm="x"')
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(page)))
                self.end_headers()
                self.wfile.write(page)
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever,
                         daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/acct"

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


if __name__ == "__main__":
    unittest.main()
