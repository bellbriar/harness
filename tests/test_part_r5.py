"""Part R, stage 5: the fixes from the reviews of the 1.0 changes.

R5A, the review of R4's sixth round (runtime, guard, release):
  R5A-1   A page that goes to another document while it is read, or after
          it was captured, is judged by that document: an error page, a
          document no server sent, is refused, never scored.
  R5A-2   No text makes a line a CI runner reads as a command: "##"
          anywhere in a line, "::" after any white space at its start.
  R5A-3   A key in a string literal of a small UTF-16 file is read.
  R5A-4   A key whose base64 has no digit is read.
  R5A-5   A URL run refuses a page that sends the browser to a document
          that is not a web page, or is XML.
  R5A-6   A status of more than three digits is a status.
  R5A-7   A blob: document came from no server.
  R5A-8   A head script that sends the tab to a 204 or a download leaves
          the page captured, not a false fallback.
  R5A-9   A committed symbolic link is read as what git stores: its path.
  R5A-10  --history reads one blob at a time.
  R5A-11  One unpacking budget for a file and every archive inside it.
  R5A-12  No regex the guard runs takes quadratic time.
  R5A-13  Base64 of a JWK's `d` (43 bytes) is read again as text.
  R5A-14  The lint dedupe finds the entry a folder lists, whatever the
          case or Unicode normalization of the name given.
  R5A-15  release_tags stops on a release it cannot order.
  R5A-17  A 203 page is not called "an error page".
  R5A-18  A refusal says where the page went.

R5B, the review of the evidence layer:
  R5B-1   A public key of small order, or an R of small order, or an S not
          reduced, verifies nothing.
  R5B-2   The halves of a key pair are marked; a .pub file, or one marked
          public, never signs.
  R5B-3   The signature is checked before what the statement says.
  R5B-4   The body is closed, of this format, and its members typed; the
          attestation is reported as the harness's text or not.
  R5B-5   URLs in snippets and messages are recorded as URLs are.
  R5B-7   A file run's domain is said to be the operator's statement.
  R5B-8   On Windows, withheld variables are matched ignoring case.
  R5B-9   Undecodable bytes in a name are recorded as %XX.
  R5B-10  The input manifest hashes what was evaluated.
  R5B-11  verify and inspect read only a regular file of bounded size.
  R5B-12  A console that cannot encode a character shows it escaped.
  R5B-13  "~nosuchuser" is a refusal, not a traceback.
  R5B-14  Two outputs may not share a file.
  R5B-15  A run that exits 2 writes no bundle.
  R5B-16  inspect names the pages not evaluated.
  R5B-17  The published test key is CANNOT VERIFY, exit 2.
  R5B-18  "Names a site" past leading invisible characters, with one slash
          or a backslash; a folder named "https:" is recorded as "./".
  R5B-19  inspect's wording on odd bundles.
  R5B-20  No rulebook version is said to be none.
  R5B-22  A home directory never puts a user's name in the evidence.

And a rule fix from the R5 field sweep: a viewport meta that disables
pinch-zoom and caps it is one finding. (Its other, a name rule's failure
on an element a rendered page hides by a stylesheet made a review, was
reverted in round 2: R5C-1.) And R3D's reader
difference: a customizable select's button is inert, no button of its
own.

Round 2, the reviews of round 1:
  R5C     a javascript: URL's document and a service worker's answer are
          refused; a page that never finishes loading, or keeps going, is
          refused in words of its own; snippet URLs are read as a browser
          reads them (//, backslashes, tabs, &amp;, srcset, refresh); the
          guard reads escaped literals, whole blobs, and members against
          one budget.
  R5D     names end distinct; snippets lose javascript:, data: and
          fragment secrets; the body is said to be closed at its top
          level; a forged key_id is INVALID, not a private half; no bundle
          its verifier refuses is signed or written; outputs never replace
          evidence; only ASCII white space surrounds a key; a key that is
          no point of the curve cannot verify; a .key link to a .pub file
          never signs; inspect's words on odd bundles; a reader that stops
          reading ends the command quietly.
  L72     the heuristic rules' criteria: autoplaying sound is 1.4.2's; a
          duplicated id fails only where a name depends on it; aria-hidden
          on <html> or <body> hides nothing; labels name every labelable
          element; header cells by role; SCR28.
  H6      the docs' claims: echoed tokens, objects showing no media,
          presentational images, a page's own <style> in names, coverage,
          --strict, denominators, layer notes.

Round 3, the reviews of round 2:
  R5E     no finding quotes a run secret, cut, in a locator, or as a word;
          a page gone to that never loads, or never arrives (a navigation
          that never commits holds every DevTools call to the page), is
          refused in words of its own, before the render deadline; workers
          are bypassed; a javascript: document judged by where it settles;
          outputs never replace served files or snapshots.
  R5F     "./" before any first part outside ASCII; the private half named
          from the statement alone; links to .pub files and hard-linked
          bare keys never sign; older bundles named; inspect warns where
          verify refuses; a vector that tests what it says.
  R5G     axe-core's results unread on a page aria-hidden at its root; a
          label names its labeled control only; SCR28's toggle shown;
          presentational images name nothing; at-rules in the page's own
          <style>; objects by their data; ids by HTML's references; a
          table's own cells; best practices at most moderate; lint words.

Round 4, the reviews of round 3:
  R5H     white space squeezed before a snippet's long cut; a pending
          navigation ends on a 204, a download or a failed request; the
          went-to URL cut after it is scrubbed; every exit 2 names an older
          bundle; snapshots keep permissions and refuse what is not a
          regular file; a field that holds a word password is withheld
          whole; inspect names what it points to.
  R5I     a label's own tree in DOM order, hidden as Chromium hides it,
          nested labels read once; the page's own <style> in the cascade's
          order, media as screens match them, strings and nesting as CSS
          reads them; the global ARIA attributes Chromium has; drawings'
          titles as SVG-AAM has them; what axe-core still found under a
          hidden root kept; a vendor's skip link scored; references and
          notes.

Round 5, the reviews of round 4:
  R5J     secrets replaced before any cut; a download the page starts ends
          no navigation; argparse's refusals name an older bundle; a
          password the harness's words or the run's URLs hold is refused;
          withheld findings stay apart and are all counted; the note said
          once, never of a folder.
  R5K     labels hidden or shown inside each other, and around slots; HTML
          in a drawing names nothing; @supports settled as Chromium 141
          has it; the style attribute in the cascade; nesting that stops
          growing; toggles hidden by markup; until-found as it renders;
          drawings' own titles; @media, @scope and comments as CSS reads
          them; url() in comments; aria-hidden as written; aria-labeledby.

Round 6, the reviews of round 5:
  R5L     what a box skips, marked as Chromium skips it; axe-core messages
          cut after they are scrubbed; axe-core's words and a page's
          redirect in the password refusal; a password split by a line
          break; a long cut where a tag starts; the guard's CR and LF.
  R5M     skipped roots, labels and references; display as Chromium
          blockifies it; long top-level rules kept; aria-labelledby into
          drawings; media and @supports tokens; CSS-wide keywords in the
          cascade; a label's own name; nested labels a traversal reaches;
          a slot's fallback; hostile stylesheets bounded.

Round 7, the reviews of round 6:
  R5N     the guard reads a key over two lines and after a short string;
          a message withheld with its markup; the console never shows the
          password; the refusal ignores case; every display Chromium
          skips is marked; --baseline alone keeps --bundle.
  R5O     visibility keywords that take the parent's; closed <details>
          through aria-labelledby; the label note scoped; CSS-wide keywords
          under a condition; invisible and skipping; displays as Chromium
          computes them; empty and function media queries; an inner label
          read once; a template in a slot's fallback; the hidden attribute
          on HTML elements only.

Round 8, the reviews of round 7:
  R5P     a message keeps its words unless it quotes the password; the
          password found as a URL writes it; the guard reads a key after a
          short string on one line; a textarea's value.
  R5Q     displays read once per element; a conditional keyword never
          hides; functions in media queries unknown; a rule's show on an
          ancestor; blockification through inherit, slots and shadow
          roots; drawings, fieldsets and legends; a closed details' first
          summary; labels in drawings, through aria-labelledby, by title.

Round 9, the reviews of round 8:
  R5R     the password's white space, Latin-1 and named spellings; no
          locator anchors on it; linear at its ends; quoted values cut
          after the search; the harness's own escaped words; a drawing's
          parts marked; the guard's escaped key pairs; a password that is
          not UTF-8; an error's message and an element's hash hold neither
          secrets nor the password.
  R5S     a closed details' first summary found once and in every walk;
          no cap on the display walk; fields of other namespaces; a label
          leaves its own control out; a label's title in the docstrings;
          features and var() in media queries; details and marquee hold a
          block; var() visibility in names read as the parent's.
  And, found measuring them: function values and custom properties in
          media and @supports tests; a ";" or a brace inside a string or
          brackets in CSS.
"""
import base64
import contextlib
import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import unicodedata
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import tests.test_part_r4 as R4                                    # noqa: E402
from bellbriar_harness import bundle as B                          # noqa: E402
from bellbriar_harness import cli                                  # noqa: E402
from bellbriar_harness import evidence_cli                         # noqa: E402
from bellbriar_harness import fetch as F                           # noqa: E402
from bellbriar_harness import lint as L                            # noqa: E402
from bellbriar_harness.engine import load_rulebook, run_page       # noqa: E402
from bellbriar_harness.model import FAIL, MINOR, NEEDS_REVIEW      # noqa: E402
from tests.bundle_body import BODY                                 # noqa: E402
from tests.test_fetch_hardening import HAVE_BROWSER, _WHY          # noqa: E402

FIXTURES = ROOT / "fixtures"
VECTORS = ROOT / "docs" / "canonicalization-vectors.json"
PAGE = R4.PAGE
RB = load_rulebook()
NEEDS_CRYPTO = unittest.skipUnless(B.HAVE_ED25519, "needs cryptography")
run, tmpdir = R4.run, R4.tmpdir


def evidence(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = evidence_cli.main([str(a) for a in argv])
    return code, out.getvalue(), err.getvalue()


def keypair(test, name="k") -> tuple[Path, Path]:
    d = tmpdir(test)
    code, out, err = evidence("keygen", "--out-prefix", d / name)
    test.assertEqual(code, 0, out + err)
    return d / f"{name}.key", d / f"{name}.pub"


def signed_run(test, *extra, page=None) -> tuple[Path, Path]:
    """(bundle, public key file) of a signed file run."""
    key, pub = keypair(test)
    out = key.parent / "b.json"
    code, _out, err = run(page or FIXTURES / "good.html", "--bundle", out,
                          "--sign-key", key, "--fail-on", "never", *extra)
    test.assertEqual(code, 0, err)
    return out, pub


def resign(bundle: dict, priv_hex: str) -> dict:
    bundle = dict(bundle, signature=None)
    return B.sign_bundle_local(bundle, priv_hex)


# ---------------------------------------------------------------------------
# R5A: runtime
# ---------------------------------------------------------------------------

@unittest.skipUnless(HAVE_BROWSER, _WHY)
class TestWhereAPageGoesWhileItIsRead(unittest.TestCase):
    """R5A-1, R5A-5, R5A-6, R5A-7, R5A-8, R5A-18."""

    site = staticmethod(R4.TestReviewOfR4Round4.site)

    @staticmethod
    def page(script="", body="<p>x</p>"):
        return PAGE.format(f"{body}<script>{script}</script>").encode()

    def setUp(self):
        from tests.test_fetch_hardening import send
        tall = '<div style="height:6000px">tall</div>'
        self.site_ = self.site({
            # Goes when it is scrolled: during the harness's scroll step.
            "/on-scroll": send(self.page(
                "addEventListener('scroll', function () {"
                " location.replace('/e404'); }, {once: true});", tall)),
            # Goes when it is narrowed: after it was captured.
            "/on-resize": send(self.page(
                "addEventListener('resize', function () {"
                " location.replace('/e404'); }, {once: true});")),
            "/on-resize-ok": send(self.page(
                "addEventListener('resize', function () {"
                " location.replace('/ok'); }, {once: true});")),
            "/e404": send(self.page(), status=404),
            "/ok": send(self.page()),
            "/to-text": send(self.page("location.replace('/t')")),
            "/t": send(b"plain", ctype="text/plain"),
            "/to-svg": send(self.page("location.replace('/s.svg')")),
            "/s.svg": send(b'<svg xmlns="http://www.w3.org/2000/svg"/>',
                           ctype="image/svg+xml"),
            "/to-xhtml": send(self.page("location.replace('/x')")),
            "/x": send(b'<html xmlns="http://www.w3.org/1999/xhtml" '
                       b'lang="en"><head><title>X</title></head><body><main>'
                       b'<h1>X</h1></main></body></html>',
                       ctype="application/xhtml+xml"),
            "/to-2000": send(self.page("location.replace('/s2000')")),
            "/s2000": send(self.page(), status=2000),
            "/blob": send(self.page(
                "location.replace(URL.createObjectURL(new Blob(["
                "'<!doctype html><html lang=en><title>b</title><main><h1>"
                "made by script</h1></main>'], {type: 'text/html'})))")),
            "/to-204": send(PAGE.format("").replace(
                "</title>", "</title><script>location.replace('/n')"
                "</script>").encode()),
            "/n": send(b"", status=204),
            # Goes, once loaded, to a page whose head script sends the tab
            # to a 204: that page's load event never comes.
            "/to-b204": send(self.page(
                "onload = function () { setTimeout(function () {"
                " location.replace('/to-204'); }, 100); };")),
            # A script makes the document in the page's place (R5C-2).
            "/js-after": send(self.page(
                "onload = function () { setTimeout(function () { location.href"
                " = \"javascript:'<!doctype html><title>x</title><h1>made</h1>"
                "'\"; }, 300); };")),
            "/js-head": send(PAGE.format("").replace(
                "</title>", "</title><script>location.href = \"javascript:'"
                "<!doctype html><title>x</title><h1>made</h1>'\";</script>")
                .encode()),
            # A service worker would answer /as200 with the server's 404
            # page as 200 (R5C-3): workers are blocked.
            "/sw-page": send(self.page(
                "navigator.serviceWorker.register('/sw.js').then(function () {"
                " return navigator.serviceWorker.ready; }).then(function () {"
                " location.replace('/as200'); }).catch(function () {});")),
            "/sw.js": send(b"self.addEventListener('install', e => "
                           b"self.skipWaiting()); self.addEventListener("
                           b"'activate', e => e.waitUntil(clients.claim()));"
                           b" self.addEventListener('fetch', e => { if "
                           b"(new URL(e.request.url).pathname === '/as200') "
                           b"e.respondWith(new Response('<!doctype html>"
                           b"<title>t</title><h1>forged</h1>', {status: 200,"
                           b" headers: {'Content-Type': 'text/html'}})); });",
                           ctype="text/javascript"),
            # A chain that settles: A, then B, then C, each a 200 page.
            "/chain-a": send(self.page(
                "onload = function () { setTimeout(function () {"
                " location.replace('/chain-b'); }, 300); };")),
            "/chain-b": send(self.page(
                "onload = function () { setTimeout(function () {"
                " location.replace('/ok'); }, 100); };")),
            # Two pages that send the browser to each other once loaded.
            "/hop-a": send(self.page(
                "onload = function () { setTimeout(function () {"
                " location.replace('/hop-b'); }, 150); };")),
            "/hop-b": send(self.page(
                "onload = function () { setTimeout(function () {"
                " location.replace('/hop-a'); }, 150); };")),
        })
        self.addCleanup(self.site_.stop)

    def url_run(self, path):
        return run("--url", self.site_.base + path, "--fail-on", "never")

    def test_an_error_page_it_goes_to_while_it_is_read(self):
        """R5A-1: during the scroll and settle steps, or after the capture
        (the narrow step), an error page is refused, and the console says
        where it went (R5A-18)."""
        for path in ("/on-scroll", "/on-resize"):
            with self.subTest(path=path):
                code, _out, err = self.url_run(path)
                self.assertEqual(code, 2, err)
                self.assertIn("which answered HTTP 404", err)
                self.assertIn("not the page you meant to evaluate", err)
                self.assertIn("it went to (not recorded): "
                              + self.site_.base + "/e404", err)
                self.assertNotIn("T1 clean", err)

    def test_a_page_it_goes_to_after_the_capture(self):
        """R5A-1: a page a server sent with 200, gone to after the
        capture, leaves the capture as it was, with a note."""
        r = F.fetch(self.site_.base + "/on-resize-ok")
        self.assertEqual(r.mode, "rendered", r.fallback_reason)
        self.assertTrue(r.final_url.endswith("/on-resize-ok"), r.final_url)
        self.assertFalse(r.navigated)
        self.assertTrue(any(n.startswith("after the capture") for n in r.notes),
                        r.notes)

    def test_a_document_that_is_no_web_page(self):
        """R5A-5: a URL run refuses it, never scoring the server's HTML of
        the page that went there; a --render run reads the file."""
        for path, words in (("/to-text", "which is not a web page"),
                            ("/to-svg", "which is not a web page"),
                            ("/to-xhtml", "which is an XML document")):
            with self.subTest(path=path):
                code, _out, err = self.url_run(path)
                self.assertEqual(code, 2, err)
                self.assertIn(words, err)
                self.assertNotIn("server HTML", err)
                r = F.fetch(self.site_.base + path, error_target="fallback",
                            fallback="read as the file it is")
                self.assertEqual(r.mode, "server")

    def test_a_page_it_goes_to_whose_load_event_never_comes(self):
        """L88 for the page gone to while the first is read: it is read
        once it is loaded, not after the whole load timeout."""
        start = time.monotonic()
        r = F.fetch(self.site_.base + "/to-b204", timeout_ms=30_000)
        self.assertLess(time.monotonic() - start, 20)
        self.assertEqual(r.mode, "rendered", r.fallback_reason)
        self.assertTrue(r.navigated)
        self.assertTrue(r.final_url.endswith("/to-204"), r.final_url)

    def test_a_document_a_script_made(self):
        """R5C-2: a javascript: URL replaces the page with no commit: no
        server sent what it shows, before or after the page loaded."""
        for path in ("/js-after", "/js-head"):
            with self.subTest(path=path):
                code, _out, err = self.url_run(path)
                self.assertEqual(code, 2, err)
                self.assertIn("a script on the page made in its place", err)
                self.assertNotIn("server HTML", err)

    def test_service_workers_are_blocked(self):
        """R5C-3: no worker answers a navigation in the server's place."""
        r = F.fetch(self.site_.base + "/sw-page")
        self.assertEqual(r.mode, "rendered", r.fallback_reason)
        self.assertFalse(r.navigated)
        self.assertNotIn("forged", r.html)

    def test_a_chain_that_settles(self):
        """R5C-8: A goes to B, B to C while it is read: C is captured, and
        the note says it went there (not "ended on")."""
        r = F.fetch(self.site_.base + "/chain-a")
        self.assertEqual(r.mode, "rendered", r.fallback_reason)
        self.assertTrue(r.navigated)
        self.assertTrue(r.final_url.endswith("/ok"), r.final_url)
        self.assertFalse(any("ended on" in n for n in r.notes), r.notes)

    def test_a_page_gone_to_that_never_loads(self):
        """R5C-7: refused, never captured half loaded."""
        import socket
        import threading
        from tests.test_fetch_hardening import send
        hold = socket.socket()
        hold.bind(("127.0.0.1", 0))
        hold.listen(8)
        held = []

        def accept():
            while True:
                try:
                    conn, _ = hold.accept()
                except OSError:
                    return
                held.append(conn)
        threading.Thread(target=accept, daemon=True).start()

        def close():
            hold.close()
            for c in held:
                c.close()
        self.addCleanup(close)
        port = hold.getsockname()[1]
        site = self.site({
            "/a": send(self.page(
                "onload = function () { setTimeout(function () {"
                " location.replace('/b'); }, 100); };")),
            "/b": send(self.page(
                "", f'<img src="http://127.0.0.1:{port}/x.png" alt="">'))})
        self.addCleanup(site.stop)
        with self.assertRaises(F.FetchError) as cm:
            F.fetch(site.base + "/a", timeout_ms=4000)
        self.assertIn("did not finish loading", str(cm.exception))

    def test_a_page_that_stays_on_no_document(self):
        """A page that goes on again while the one it went to is read is
        refused, in its own words (not "not a web page")."""
        code, _out, err = self.url_run("/hop-a")
        self.assertEqual(code, 2, err)
        self.assertIn("sent it on again, and again", err)
        self.assertIn("a page that stays on no one document cannot be "
                      "evaluated", err)
        self.assertNotIn("is not a web page", err)

    def test_a_status_of_more_than_three_digits(self):
        """R5A-6."""
        code, _out, err = self.url_run("/to-2000")
        self.assertEqual(code, 2, err)
        self.assertIn("which answered HTTP 2000", err)

    def test_a_blob_document(self):
        """R5A-7: no server sent it, whatever status Chromium gives it."""
        code, _out, err = self.url_run("/blob")
        self.assertEqual(code, 2, err)
        self.assertIn("which no server sent", err)
        self.assertNotIn("made by script", err)

    def test_a_204_from_a_head_script(self):
        """R5A-8, L88: the page stays, and is captured, without waiting out
        the load timeout for a load event that never comes; no fallback
        says the page timed out."""
        start = time.monotonic()
        r = F.fetch(self.site_.base + "/to-204", timeout_ms=30_000)
        self.assertLess(time.monotonic() - start, 20)
        self.assertEqual(r.mode, "rendered", r.fallback_reason)
        self.assertEqual(r.status, 200)
        self.assertFalse(r.navigated)


class TestWords(unittest.TestCase):
    """R5A-17, R5A-18."""

    def test_a_203_page_is_not_an_error_page(self):
        from tests.test_fetch_hardening import _Site, send
        site = _Site({"/p": send(PAGE.format("").encode(), status=203)})
        self.addCleanup(site.stop)
        code, _out, err = run("--url", site.base + "/p", "--no-render",
                              "--fail-on", "never")
        self.assertEqual(code, 2, err)
        self.assertIn("returned HTTP 203; the harness evaluates only a page "
                      "its server sends with HTTP 200", err)
        self.assertNotIn("an error page", err)

    def test_render_failure_reads_only_the_kind(self):
        """Where the page went is for the console: the recorded reason
        holds the kind alone (R4E-4), with a status of any length."""
        exc = F.FetchError(F.WENT_ELSEWHERE + "HTTP 2000" + F.WENT_TO
                           + "https://x.example/?t=REDACTED")
        self.assertEqual(F.render_failure(exc),
                         "FetchError: " + F.WENT_ON + "answered HTTP 2000")
        exc = F.FetchError(F.WENT_ELSEWHERE + F.NO_SERVER + F.WENT_TO
                           + "blob:…")
        self.assertIn("no server sent", F.render_failure(exc))
        self.assertEqual(F._at("blob:http://127.0.0.1/abc"), F.WENT_TO
                         + "blob:…")
        self.assertEqual(F._at("https://u:p@x.example/a?t=1#f=2"),
                         F.WENT_TO + "https://x.example/a?t=REDACTED"
                         "#f=REDACTED")


class TestNoTextMakesACommand(unittest.TestCase):
    """R5A-2: GitHub's runner reads "::" at a line's start after trimming
    every Unicode space, and its older "##[" anywhere; Azure Pipelines'
    "##vso[" and TeamCity's "##teamcity[" are read anywhere in a line."""

    LINES = ("x ##vso[task.setvariable variable=PWNED]1",
             "y ##[error]Forged",
             "z ##teamcity[message text='x']",
             " ::error file=README.md,line=1::F",
             "　::warning::F2",
             "  ::notice::F3")

    def assert_no_command(self, text: str) -> None:
        self.assertNotIn("##", text)
        for line in text.splitlines():
            # str.lstrip() strips every Unicode white space, as the runner
            # trims it.
            self.assertFalse(line.lstrip().startswith("::"), repr(line))

    def test_the_console(self):
        from bellbriar_harness.redact import escaped_console
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            with escaped_console():
                for line in self.LINES:
                    print(line)
                # In pieces, as a name and the words around it are.
                sys.stdout.write("a #")
                sys.stdout.write("#vso[task.complete result=Succeeded]\n")
                sys.stdout.write(" ")
                sys.stdout.write(":")
                sys.stdout.write(":error::split\n")
                print("C# and a : and :: mid-line, kept")
        self.assert_no_command(out.getvalue())
        self.assertIn("C# and a : and :: mid-line, kept", out.getvalue())
        self.assertIn("#\\u0023vso[", out.getvalue())

    def test_the_guard(self):
        import repo_guard
        for line in self.LINES:
            self.assertNotIn("##", repo_guard._shown(line + " ###"))

    def test_names_and_bundles(self):
        d = tmpdir(self)
        try:
            (d / "x ##vso[task.setvariable variable=PWNED]1.jsx").write_text(
                "export const A = () => <div onClick={go}>x</div>;\n")
            (d / "p ##[error]Forged.html").write_text(PAGE.format(""))
        except OSError:
            self.skipTest("this file system refuses the names")
        out = io.StringIO()
        with contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(io.StringIO()):
            L.main([str(d)])
        self.assert_no_command(out.getvalue())
        self.assertIn("bl-div-click", out.getvalue())
        code, out, err = run(d / "p ##[error]Forged.html", "--fail-on",
                             "never")
        self.assertEqual(code, 0, err)
        self.assert_no_command(out + err)
        b = d / "b.json"
        b.write_text(json.dumps(dict(
            BODY, domain="example.com ##vso[task.setvariable variable=GATE]"
            "passed")))
        code, out, err = evidence("inspect", b)
        self.assert_no_command(out + err)
        self.assertIn("example.com #\\u0023vso[", out)


class TestGuardOfRound6(unittest.TestCase):
    """R5A-3, R5A-4, R5A-9 to R5A-13."""

    setUp = R4.TestReviewOfR4Guard.setUp
    guard = R4.TestReviewOfR4Guard.guard

    def test_a_key_in_a_string_literal_of_a_small_utf16_file(self):
        """R5A-3: the key's own control characters made the file read as
        binary, and its string literals went unread."""
        from cryptography.hazmat.primitives.asymmetric import ed25519
        while True:
            key = ed25519.Ed25519PrivateKey.generate()
            seed = key.private_bytes_raw()
            if not any(b in seed for b in b'"\\\r\n'):
                break
        pub = key.public_key().public_bytes_raw()
        kid = hashlib.sha256(pub).hexdigest()[:16]
        source = ('KEY = "' + seed.decode("latin-1") + '"\n')
        for label, data in (("UTF-16", source.encode("utf-16-le")),
                            ("UTF-8", source.encode("utf-8"))):
            with self.subTest(encoding=label):
                problems = self.guard({f"keys/{kid}.pub": pub.hex(),
                                       "k.py": data})
                self.assertTrue(any("private half" in p for p in problems),
                                problems)

    def test_base64_with_no_digit(self):
        """R5A-4: about one key in 1,500 has none."""
        from cryptography.hazmat.primitives.asymmetric import ed25519
        while True:
            seed = os.urandom(32)
            enc = base64.b64encode(seed).decode()
            if not re.search(r"\d", enc):
                break
        pub = ed25519.Ed25519PrivateKey.from_private_bytes(
            seed).public_key().public_bytes_raw()
        kid = hashlib.sha256(pub).hexdigest()[:16]
        problems = self.guard({"secret.txt": f"seed: {enc}\n",
                               f"keys/{kid}.pub": pub.hex()})
        self.assertTrue(problems)
        # A path or a name made of base64's letters is still no key.
        self.assertEqual(self.guard({
            "a.txt": "src/components/CheckoutPage/PaymentForm/Fields/A/B.js"}),
            [])

    def test_base64_of_a_jwk_d(self):
        """R5A-13: a JWK's `d` is 43 characters, in base64 itself."""
        d = base64.urlsafe_b64encode(self.priv).decode().rstrip("=")
        self.assertEqual(len(d), 43)
        problems = self.guard({"x.txt": base64.b64encode(d.encode()).decode(),
                               "a.pub": self.pub.hex()})
        self.assertTrue(problems)

    def git_repo(self) -> tuple[Path, list]:
        d = tmpdir(self)
        git = ["git", "-C", str(d / "r"), "-c", "user.name=t", "-c",
               "user.email=t@example.invalid", "-c", "commit.gpgsign=false"]
        (d / "r").mkdir()
        if subprocess.run(git[:3] + ["init", "-q"]).returncode:
            self.skipTest("git")
        return d, git

    @unittest.skipUnless(hasattr(os, "symlink"), "no symbolic links")
    def test_a_committed_symbolic_link(self):
        """R5A-9: read as git stores it, the path it names: a link to a key
        outside the repository is no key in it, and a link whose path is a
        key is read."""
        import repo_guard
        d, git = self.git_repo()
        (d / "outside").mkdir()
        (d / "outside" / "id_scratch").write_text(
            "-----BEGIN OPENSSH " + "PRIVATE KEY-----\nAAAA\n-----END "
            "OPENSSH " + "PRIVATE KEY-----\n")
        os.symlink("../outside/id_scratch", d / "r" / "deploy_key_link")
        (d / "r" / "README").write_text("x\n")
        subprocess.run(git + ["add", "-A"], check=True)
        subprocess.run(git + ["commit", "-qm", "x"], check=True)
        self.assertEqual(repo_guard.check(d / "r"), [])
        self.assertEqual(repo_guard.check_history(d / "r"), [])
        os.symlink(self.priv.hex(), d / "r" / "odd_link")
        (d / "r" / "a.pub").write_text(self.pub.hex())
        problems = repo_guard.check(d / "r")
        self.assertTrue(any("private half" in p for p in problems), problems)

    def test_history_is_read_one_blob_at_a_time(self):
        """R5A-10: the blobs come from one cat-file --batch, read as it
        writes them."""
        import repo_guard
        d, git = self.git_repo()
        (d / "r" / "a.txt").write_bytes(b"a" * 70_000)
        (d / "r" / "b.txt").write_bytes(b"\n")
        subprocess.run(git + ["add", "-A"], check=True)
        subprocess.run(git + ["commit", "-qm", "x"], check=True)
        shas = [subprocess.run(git + ["rev-parse", f"HEAD:{n}"],
                               capture_output=True, text=True,
                               check=True).stdout.strip()
                for n in ("a.txt", "b.txt")]
        got = list(repo_guard._blobs(git, shas))
        self.assertEqual(got, [(shas[0], b"a" * 70_000), (shas[1], b"\n")])

    def test_one_budget_for_a_file_and_its_archives(self):
        """R5A-11: archives inside an archive share its budget; each had
        one of its own, and a file of a few hundred bytes kept the guard
        unpacking for days."""
        import lzma
        import repo_guard
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tf:
            for i in range(4):
                member = lzma.compress(bytes(400_000))
                info = tarfile.TarInfo(f"m{i}.xz")
                info.size = len(member)
                tf.addfile(info, io.BytesIO(member))
        outer = lzma.compress(buf.getvalue())
        self.assertLess(len(outer), 2000)
        with mock.patch.object(repo_guard, "MAX_SCAN", 1_000_000):
            problems = self.guard({"a.tar.xz": outer})
        self.assertTrue(any("the guard unpacks from one file and the "
                            "archives inside it" in p for p in problems),
                        problems)

    def test_no_quadratic_regex(self):
        """R5A-12: a file of escaped quotes and no closing one took 25 s
        for 80 KB."""
        text = "\\0 " + '\\"' * 40_000
        start = time.monotonic()
        self.guard({"a.c": text})
        self.assertLess(time.monotonic() - start, 5.0)


class TestLintNames(unittest.TestCase):
    """R5A-14: one entry, however the name given spells it, where the file
    system ignores case or normalization; two where it tells them apart."""

    def test_the_entry_the_folder_lists(self):
        d = tmpdir(self)
        (d / "App.jsx").write_text("export const A = 1;\n")
        self.assertEqual(L.file_key(d / "APP.jsx", {}),
                         L.file_key(d / "App.jsx", {}))
        nfc = unicodedata.normalize("NFC", "café.jsx")
        nfd = unicodedata.normalize("NFD", "café.jsx")
        (d / nfc).write_text("export const C = 1;\n")
        self.assertEqual(L.file_key(d / nfd, {}), L.file_key(d / nfc, {}))
        (d / "b.jsx").write_text("export const B = 1;\n")
        (d / "B.jsx").write_text("export const B2 = 1;\n")
        if len({p.name for p in d.iterdir()} & {"b.jsx", "B.jsx"}) == 2:
            self.assertNotEqual(L.file_key(d / "b.jsx", {}),
                                L.file_key(d / "B.jsx", {}))


class TestReleaseTags(unittest.TestCase):
    """R5A-15."""

    def test_a_release_it_cannot_order(self):
        import release_tags as RT
        for odd in ("v1.1.0.post1", "v1.1", "v2.0.0.dev1"):
            with self.subTest(tag=odd):
                with self.assertRaises(ValueError):
                    RT.released(["v1.0.0", odd], strict=True)
        # git's own tags: one this project never made is no release.
        self.assertEqual(RT.released(["v1.0.0", "v1.1.0.post1", "vnext"]),
                         [(1, 0, 0)])
        d = tmpdir(self)
        (d / "pypi.json").write_text(json.dumps({"files": [
            {"filename": "bellbriar_harness-1.1.0.post1-py3-none-any.whl"}]}))
        err = io.StringIO()
        with contextlib.redirect_stderr(err), \
                contextlib.redirect_stdout(io.StringIO()):
            code = RT.main(["1.0.1", "img", "--pypi", str(d / "pypi.json")])
        self.assertEqual(code, 2)
        self.assertIn("1.1.0.post1", err.getvalue())


# ---------------------------------------------------------------------------
# R5B: the evidence layer
# ---------------------------------------------------------------------------

@NEEDS_CRYPTO
class TestKeysThatProveNothing(unittest.TestCase):
    """R5B-1."""

    WEAK = ("01" + "00" * 31,                       # the identity
            "00" * 32,                              # y = 0: order 4
            "ec" + "ff" * 30 + "7f",                # y = p - 1: order 2
            "26e8958fc2b227b045c3f489f2ef98f0d5dfac05d3c63339b13802886d53fc05",
            "c7176a703d4dd84fba3c0b760d10670f2a2053fa2c39ccc64ec7fd7792ac037a",
            "ed" + "ff" * 30 + "7f",                # y = p
            "01" + "00" * 30 + "80",                # the identity, x "negative"
            "ff" * 32)                              # y above p, sign bit set

    def test_a_public_key_of_small_order(self):
        for weak in self.WEAK:
            with self.subTest(key=weak[:8]):
                self.assertTrue(B.weak_point(bytes.fromhex(weak)))
                with self.assertRaises(ValueError):
                    B.check_public_key(weak)
        _priv, pub, _kid = B.generate_keypair()
        self.assertEqual(B.check_public_key(pub.upper()), pub)

    def test_anyone_signs_under_it_and_verify_says_so(self):
        identity = "01" + "00" * 31
        bundle = dict(BODY, domain="victim.example")
        kid = B.key_id_for(identity)
        st = B.build_statement(B.bundle_bound_values(bundle), kid,
                               "Victim Corp", B.SELF_SIGNED,
                               B.bundle_digest(bundle))
        bundle["signature"] = {
            "alg": "Ed25519", "context": B.STATEMENT_FORMAT, "key_id": kid,
            "statement": st, "signature_b64": base64.b64encode(
                bytes.fromhex(identity) + bytes(32)).decode()}
        with self.assertRaises(ValueError):
            B.verify_bundle(bundle, identity)
        d = tmpdir(self)
        (d / "b.json").write_text(json.dumps(bundle))
        code, out, _err = evidence("verify", d / "b.json", "--public-key",
                                   identity)
        self.assertEqual(code, 2, out)
        self.assertIn("CANNOT VERIFY", out)
        self.assertIn("small order", out)
        self.assertNotIn("VALID", out.replace("CANNOT VERIFY", ""))

    def test_r_of_small_order_and_s_not_reduced(self):
        priv, pub, _ = B.generate_keypair()
        bundle = B.sign_bundle_local(dict(BODY, domain="example.com"), priv)
        ok, why = B.verify_bundle(bundle, pub)
        self.assertTrue(ok, why)
        sig = bundle["signature"]
        raw = base64.b64decode(sig["signature_b64"])
        no_key = dict(bundle, signature=dict(sig, signature_b64=base64.b64encode(
            bytes.fromhex("01" + "00" * 31) + bytes(32)).decode()))
        ok, why = B.verify_bundle(no_key, pub)
        self.assertFalse(ok)
        self.assertIn("its R is a point of small order", why)
        s = int.from_bytes(raw[32:], "little") + B._ED_L
        unreduced = dict(bundle, signature=dict(sig, signature_b64=(
            base64.b64encode(raw[:32] + s.to_bytes(32, "little")).decode())))
        ok, why = B.verify_bundle(unreduced, pub)
        self.assertFalse(ok)
        self.assertIn("its S is not reduced", why)


@NEEDS_CRYPTO
class TestKeyFiles(unittest.TestCase):
    """R5B-2: the halves of a pair cannot be taken for each other."""

    def test_keygen_marks_each_half(self):
        key, pub = keypair(self)
        k_lines = key.read_text().splitlines()
        p_lines = pub.read_text().splitlines()
        self.assertEqual(k_lines[0], B.PRIVATE_KEY_MARK)
        self.assertEqual(p_lines[0], B.PUBLIC_KEY_MARK)
        self.assertEqual(B.parse_key_text(key.read_text())[0], "private")
        self.assertEqual(B.parse_key_text(pub.read_text())[0], "public")
        self.assertEqual(len(k_lines), 2)
        if os.name != "nt":
            self.assertEqual(stat.S_IMODE(key.stat().st_mode), 0o600)

    def test_the_public_half_never_signs(self):
        key, pub = keypair(self)
        d = key.parent
        code, _out, err = run(FIXTURES / "good.html", "--bundle", d / "b.json",
                              "--sign-key", pub)
        self.assertEqual(code, 2, err)
        self.assertIn("names a .pub file, the PUBLIC half", err)
        self.assertFalse((d / "b.json").exists())
        renamed = d / "other.key"
        renamed.write_text(pub.read_text())
        os.chmod(renamed, 0o600)
        code, _out, err = run(FIXTURES / "good.html", "--bundle", d / "b.json",
                              "--sign-key", renamed)
        self.assertEqual(code, 2, err)
        self.assertIn("holds a PUBLIC key", err)
        with mock.patch.dict(os.environ, {"BB_R5_KEY": pub.read_text()}):
            code, _out, err = run(FIXTURES / "good.html", "--bundle",
                                  d / "b.json", "--sign-key-env", "BB_R5_KEY")
        self.assertEqual(code, 2, err)
        self.assertIn("holds a PUBLIC key", err)
        with mock.patch.dict(os.environ, {"BB_R5_KEY": key.read_text()}):
            code, _out, err = run(FIXTURES / "good.html", "--bundle",
                                  d / "b.json", "--sign-key-env", "BB_R5_KEY",
                                  "--fail-on", "never")
        self.assertEqual(code, 0, err)
        code, out, _err = evidence("verify", d / "b.json", "--public-key", pub)
        self.assertEqual(code, 0, out)

    def test_pairs_made_before_the_marks(self):
        priv, pub, _ = B.generate_keypair()
        d = tmpdir(self)
        (d / "old.key").write_text(priv + "\n")
        os.chmod(d / "old.key", 0o600)
        (d / "old.pub").write_text(pub + "\n")
        code, _out, err = run(FIXTURES / "good.html", "--bundle", d / "b.json",
                              "--sign-key", d / "old.key", "--fail-on",
                              "never")
        self.assertEqual(code, 0, err)
        code, out, _err = evidence("verify", d / "b.json", "--public-key",
                                   d / "old.pub")
        self.assertEqual(code, 0, out)

    def test_verify_given_a_private_half(self):
        key, pub = keypair(self)
        bundle, pub = signed_run(self)
        code, out, _err = evidence("verify", bundle, "--public-key", key)
        self.assertEqual(code, 2, out)
        self.assertIn("names a PRIVATE key file", out)

    def test_a_bundle_signed_with_a_public_key_as_its_seed(self):
        """What verify says when the published half is the seed: the
        signing key is public."""
        _priv, pub, _ = B.generate_keypair()
        bundle = B.sign_bundle_local(dict(BODY), pub)
        d = tmpdir(self)
        (d / "b.json").write_text(json.dumps(bundle))
        (d / "k.pub").write_text(B.key_file_text(pub, private=False))
        code, out, _err = evidence("verify", d / "b.json", "--public-key",
                                   d / "k.pub")
        self.assertEqual(code, 2, out)
        self.assertIn("If it is the signer's published public key, the "
                      "bundle was signed with that public key as its private "
                      "key", out)

    def test_another_first_line_is_no_key_file(self):
        priv, _pub, _ = B.generate_keypair()
        self.assertEqual(B.parse_key_text("# my key\n" + priv),
                         ("other", priv))
        d = tmpdir(self)
        (d / "x.key").write_text("# my key\n" + priv + "\n")
        os.chmod(d / "x.key", 0o600)
        with self.assertRaises(B.KeyFileError) as cm:
            B.read_private_key_file(str(d / "x.key"))
        self.assertNotIn(priv, str(cm.exception))


@NEEDS_CRYPTO
class TestVerifyOrderAndBody(unittest.TestCase):
    """R5B-3, R5B-4, R5B-7, R5B-20."""

    def setUp(self):
        self.priv, self.pub, _ = B.generate_keypair()

    def test_no_reason_calls_an_unchecked_signature_genuine(self):
        bundle = B.sign_bundle_local(dict(BODY, domain="example.com"),
                                     self.priv)
        sig = bundle["signature"]
        claimed = dict(bundle, signature=dict(sig, statement=dict(
            sig["statement"], domain="acquired-by-evil.example")))
        ok, why = B.verify_bundle(claimed, self.pub)
        self.assertFalse(ok)
        self.assertTrue(why.startswith("signature invalid"), why)
        self.assertNotIn("genuine", why)
        self.assertNotIn("acquired-by-evil", why)
        zeros = dict(claimed, signature=dict(claimed["signature"],
                                             signature_b64=base64.b64encode(
                                                 bytes(64)).decode()))
        ok, why = B.verify_bundle(zeros, self.pub)
        self.assertFalse(ok)
        self.assertTrue(why.startswith("signature invalid"), why)
        # A body changed after a genuine signature.
        altered = dict(bundle, coverage_note="changed")
        ok, why = B.verify_bundle(altered, self.pub)
        self.assertFalse(ok)
        self.assertTrue(why.startswith("digest mismatch: the bundle was "
                                       "altered after it was signed"), why)

    def test_the_body_is_closed(self):
        for label, body in (
                ("a member it does not define",
                 dict(BODY, certification="WCAG 2.1 AA conformant")),
                ("another format", dict(BODY, bundle_format="bellbriar-"
                                        "evidence/2")),
                ("no format", {k: v for k, v in BODY.items()
                               if k != "bundle_format"}),
                ("a member missing", {k: v for k, v in BODY.items()
                                      if k != "pages"}),
                ("a member of another type", dict(BODY, site=[])),
                ("only a signature", {"signature": None})):
            with self.subTest(label):
                signed = B.sign_bundle_local(dict(body), self.priv) \
                    if "bundle_format" in body and body["bundle_format"] \
                    == B.BUNDLE_FORMAT else dict(body)
                with self.assertRaises(B.MalformedBundle):
                    B.verify_bundle(signed, self.pub)

    def test_the_attestation_is_said_to_be_the_harnesss_or_not(self):
        from bellbriar_harness import __version__
        ours = B.sign_bundle_local(dict(BODY, attestation=B.ATTESTATION),
                                   self.priv)
        ok, why = B.verify_bundle(ours, self.pub)
        self.assertTrue(ok, why)
        self.assertIn(f"its attestation text is the one bellbriar-harness "
                      f"{__version__} writes", why)
        theirs = B.sign_bundle_local(dict(
            BODY, attestation="Certified WCAG 2.1 AA conformant."), self.priv)
        ok, why = B.verify_bundle(theirs, self.pub)
        self.assertTrue(ok, why)
        self.assertIn("its attestation text is NOT the one", why)
        self.assertIn("read it as the words of whoever made the bundle", why)

    def test_a_file_runs_domain(self):
        """R5B-7."""
        bundle, pub = signed_run(self, "--domain", "example.com")
        code, out, _err = evidence("verify", bundle, "--public-key", pub)
        self.assertEqual(code, 0, out)
        self.assertIn("no fetched host is recorded: the domain 'example.com' "
                      "is the operator's statement, and nothing was fetched "
                      "from it", out)

    def test_no_rulebook_version(self):
        """R5B-20."""
        said = B._rulebook_said({"rulebook_version": None,
                                 "rulebook_sha256": None})
        self.assertIn("records no rulebook version", said)
        self.assertNotIn("None", said)


class TestRecordedValues(unittest.TestCase):
    """R5B-5, R5B-9, R5B-10, R5B-18, R5B-22."""

    SECRETS = ("hunter2", "SECRETTOKEN123456", "SIGNATURESECRET999",
               "SRCSETSECRET", "REFRESHSECRET", "FRAGSECRET")
    MARKUP = ('<a href="https://user:hunter2@api.example/cb?access_token='
              'SECRETTOKEN123456"></a>'
              '<img src="https://cdn.example/i.png?sig=SIGNATURESECRET999">'
              '<img srcset="/a.png?k=SRCSETSECRET 1x, /b.png 2x">'
              '<a href="/cb#access_token=FRAGSECRET"></a>'
              '<a href="#main"></a>')

    def test_snippets_and_messages_hold_no_secret(self):
        """R5B-5: as a recorded URL has them: no user name or password,
        every query value REDACTED, a fragment of parameters too; an
        element's id after "#" kept."""
        page = run_page(PAGE.format(self.MARKUP).replace(
            "</title>", '</title><meta http-equiv="refresh" content="5; '
            'url=https://x.example/?t=REFRESHSECRET">').encode(), "p.html", RB)
        texts = [f.snippet + " " + f.message for r in page.results
                 for f in r.findings]
        self.assertTrue(texts)
        joined = "\n".join(texts)
        for secret in self.SECRETS:
            self.assertNotIn(secret, joined)
        self.assertIn("access_token=REDACTED", joined)
        d = tmpdir(self)
        (d / "p.html").write_text(PAGE.format(self.MARKUP))
        code, _out, err = run(d / "p.html", "--bundle", d / "b.json",
                              "--json", d / "r.json", "--fail-on", "never")
        self.assertEqual(code, 0, err)
        for out in ("b.json", "r.json"):
            text = (d / out).read_text()
            for secret in self.SECRETS:
                self.assertNotIn(secret, text, out)

    def test_redact_markup(self):
        from bellbriar_harness.redact import redact_markup as r
        self.assertEqual(r('<a href="#main">'), '<a href="#main">')
        self.assertEqual(r('<a href="/p?q=1#top">'),
                         '<a href="/p?q=REDACTED#top">')
        self.assertEqual(r('<img srcset="/a.png?k=1 1x, /b.png?k=2 2x">'),
                         '<img srcset="/a.png?k=REDACTED 1x, '
                         '/b.png?k=REDACTED 2x">')
        self.assertEqual(r("<a href=https://u:p@x.example/?t=1>"),
                         "<a href=https://x.example/?t=REDACTED>")
        self.assertEqual(r("see https://x.example/?token=1 there"),
                         "see https://x.example/?token=REDACTED there")
        # A "?" in text that is no URL: kept as it is.
        for kept in ('<a title="why?" href="/a">', '<a href="#main">'):
            self.assertEqual(r(kept), kept)
        # Query values written inside javascript: and data: values are
        # replaced too (R5D-2).
        self.assertEqual(r('<a href="javascript:go(\'?x=1\')">'),
                         '<a href="javascript:go(\'?x=REDACTED\')">')
        self.assertEqual(r('<img src="data:image/png;base64,AAAA?x=1">'),
                         '<img src="data:image/png;base64,AAAA?x=REDACTED">')

    def test_undecodable_names(self):
        """R5B-9: two names that differ only in bytes that are not UTF-8
        are two names in the evidence."""
        d = tmpdir(self)
        site = d / "u8"
        site.mkdir()
        try:
            with open(os.path.join(os.fsencode(site), b"\xff.html"), "wb") as fh:
                fh.write(PAGE.format("<img src=a.png>").encode())
            with open(os.path.join(os.fsencode(site), b"\xfe.html"), "wb") as fh:
                fh.write(PAGE.format("").encode())
        except (OSError, ValueError):
            self.skipTest("this file system refuses names that are not UTF-8")
        code, _out, err = run(site, "--bundle", d / "b.json", "--fail-on",
                              "never")
        self.assertEqual(code, 0, err)
        bundle = json.loads((d / "b.json").read_text(encoding="utf-8"))
        names = sorted(e["path"] for e in bundle["inputs"])
        self.assertEqual(names, ["u8/%FE.html", "u8/%FF.html"])
        self.assertEqual(sorted(p["path"] for p in bundle["pages"]), names)
        self.assertEqual(B.name_escaped("a\udcff\udc80b"), "a%FF%80b")

    def test_the_manifest_hashes_what_was_evaluated(self):
        """R5B-10: a file changed after it was read is recorded as it was
        read, not as it is when the bundle is written."""
        from bellbriar_harness import engine as E
        d = tmpdir(self)
        page = d / "p.html"
        first = PAGE.format("<img src=a.png>").encode()
        page.write_bytes(first)
        real = E.run_page

        def then_changed(*a, **k):
            result = real(*a, **k)
            page.write_bytes(PAGE.format("").encode())
            return result
        with mock.patch.object(E, "run_page", then_changed):
            code, _out, err = run(page, "--bundle", d / "b.json",
                                  "--fail-on", "never")
        self.assertEqual(code, 0, err)
        entry = json.loads((d / "b.json").read_text())["inputs"][0]
        self.assertEqual(entry["sha256"], hashlib.sha256(first).hexdigest())
        self.assertEqual(entry["bytes"], len(first))

    def test_names_a_site(self):
        """R5B-18."""
        for name in (" https://www.victim.example/pricing",
                     "​https://www.victim.example/",
                     " http://x.example/", "https:/www.victim.example/",
                     "HTTPS:\\\\x.example\\", "\nhttp://x.example/"):
            with self.subTest(name=name):
                self.assertTrue(B._names_site(name))
        for name in ("./https:/a.html", "site/https:/a.html", "https.html",
                     "http-notes/a.html"):
            with self.subTest(name=name):
                self.assertFalse(B._names_site(name))
        self.assertEqual(B.recorded_path("https:/a.html"), "./https:/a.html")

    def test_a_home_directory_is_never_recorded(self):
        """R5B-22: `bellbriar-eval ~` recorded "alice/site/index.html"."""
        self.assertEqual(B.recorded_path("/home/alice/site/index.html",
                                         "/home/alice"), "site/index.html")
        self.assertEqual(B.recorded_path("/Users/alice/site/index.html",
                                         "/Users/alice"), "site/index.html")
        self.assertEqual(B.recorded_path("/root/site/index.html", "/root"),
                         "site/index.html")
        self.assertEqual(B.recorded_path("/srv/www/site/index.html",
                                         "/srv/www/site"), "site/index.html")


class TestWithheld(unittest.TestCase):
    """R5B-8: on Windows os.environ holds names in upper case, so a name
    given in lower case must match it."""

    def test_names_ignoring_case_on_windows(self):
        # A set of its own: other tests add the names they pass.
        with mock.patch.object(F, "WITHHELD_ENV", {
                "BELLBRIAR_SIGN_KEY", "BELLBRIAR_HTTP_PASSWORD",
                "bb_r5_lower_key"}):
            with mock.patch("os.name", "nt"):
                self.assertTrue(F.withheld("BB_R5_LOWER_KEY"))
                self.assertTrue(F.withheld("bellbriar_sign_key"))
                self.assertFalse(F.withheld("PATH"))
            if os.name != "nt":
                self.assertFalse(F.withheld("BB_R5_LOWER_KEY"))
                self.assertTrue(F.withheld("bb_r5_lower_key"))


class TestReadingBundles(unittest.TestCase):
    """R5B-11, R5B-12, R5B-13, R5B-14, R5B-15, R5B-16, R5B-17, R5B-19."""

    @unittest.skipUnless(hasattr(os, "mkfifo"), "no FIFOs")
    def test_a_fifo_or_a_device(self):
        d = tmpdir(self)
        os.mkfifo(d / "f")
        _priv, pub, _ = B.generate_keypair()
        for path in (d / "f", "/dev/zero", d):
            if not os.path.exists(path):
                continue
            with self.subTest(path=str(path)):
                start = time.monotonic()
                code, out, _err = evidence("verify", path, "--public-key", pub)
                self.assertEqual(code, 2, out)
                self.assertIn("cannot be read as a bundle", out)
                code, out, _err = evidence("inspect", path)
                self.assertEqual(code, 2, out)
                self.assertLess(time.monotonic() - start, 10)

    def test_a_file_too_large(self):
        d = tmpdir(self)
        (d / "b.json").write_text(json.dumps(BODY))
        _priv, pub, _ = B.generate_keypair()
        with mock.patch.object(B, "MAX_BUNDLE_FILE", 100):
            code, out, _err = evidence("verify", d / "b.json", "--public-key",
                                       pub)
        self.assertEqual(code, 2, out)
        self.assertIn("more than the 100", out)

    @NEEDS_CRYPTO
    def test_a_console_that_cannot_encode(self):
        """R5B-12: cp1252, which Windows uses for redirected output, has no
        "→"; ascii has no "…"."""
        bundle, pub = signed_run(self)
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"),
                   PYTHONDONTWRITEBYTECODE="1")
        script = ("import sys; from bellbriar_harness import evidence_cli as "
                  "e; sys.exit(e.main(sys.argv[1:]))")
        for encoding in ("ascii", "cp1252"):
            with self.subTest(encoding=encoding):
                env["PYTHONIOENCODING"] = encoding
                d = tmpdir(self)
                proc = subprocess.run(
                    [sys.executable, "-c", script, "keygen", "--out-prefix",
                     str(d / "k")], env=env, capture_output=True, timeout=120)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertNotIn(b"Traceback", proc.stderr)
                proc = subprocess.run(
                    [sys.executable, "-c", script, "verify", str(bundle),
                     "--public-key", str(pub)], env=env, capture_output=True,
                    timeout=120)
                self.assertEqual(proc.returncode, 0, proc.stdout)
                self.assertNotIn(b"Traceback", proc.stderr)

    @NEEDS_CRYPTO
    def test_no_such_user(self):
        """R5B-13."""
        d = tmpdir(self)
        code, _out, err = run(FIXTURES / "good.html", "--bundle", d / "b.json",
                              "--sign-key", "~bb_no_such_user_r5x/k.key")
        self.assertEqual(code, 2, err)
        self.assertNotIn("Traceback", err)
        self.assertFalse((d / "b.json").exists())

    def test_two_outputs_in_one_file(self):
        """R5B-14."""
        d = tmpdir(self)
        (d / "sub").mkdir()
        page = FIXTURES / "good.html"
        for argv in ((page, "--json", d / "x", "--bundle", d / "x"),
                     (page, "--html", d / "y", "--json",
                      d / "sub" / ".." / "y"),
                     ("--url", "http://127.0.0.1:9/p", "--save-snapshots",
                      d / "s", "--json", d / "s")):
            with self.subTest(argv=argv):
                code, _out, err = run(*argv)
                self.assertEqual(code, 2, err)
                self.assertTrue("name the same file" in err or
                                "names a file in the --save-snapshots "
                                "folder" in err, err)
        if hasattr(os, "symlink"):
            os.symlink(d / "real.json", d / "alias.json")
            code, _out, err = run(FIXTURES / "good.html", "--json",
                                  d / "real.json", "--bundle",
                                  d / "alias.json")
            self.assertEqual(code, 2, err)
            self.assertIn("name the same file", err)

    def test_no_bundle_from_a_run_that_exits_2(self):
        """R5B-15: no page could be evaluated."""
        d = tmpdir(self)
        shell = ('<!doctype html><html lang="en"><head><title>App</title>'
                 '<script src="app.js"></script></head><body><div id="root">'
                 '</div></body></html>')
        (d / "app.html").write_text(shell)
        code, _out, err = run(d / "app.html", "--bundle", d / "b.json")
        self.assertEqual(code, 2, err)
        self.assertIn("This is not a pass. No evidence bundle was written to",
                      err)
        self.assertFalse((d / "b.json").exists())
        # A gate that failed is evidence of the failure: its bundle stays.
        code, _out, err = run(FIXTURES / "bad.html", "--bundle", d / "b.json")
        self.assertEqual(code, 1, err)
        self.assertTrue((d / "b.json").exists())

    def test_inspect_names_the_pages_not_evaluated(self):
        """R5B-16."""
        d = tmpdir(self)
        (d / "app.html").write_text(
            '<!doctype html><html lang="en"><head><title>App</title><script '
            'src="app.js"></script></head><body><div id="root"></div>'
            '</body></html>')
        shutil.copy(FIXTURES / "good.html", d / "index.html")
        code, _out, err = run(d / "index.html", d / "app.html", "--bundle",
                              d / "b.json", "--fail-on", "never")
        self.assertEqual(code, 0, err)
        code, out, _err = evidence("inspect", d / "b.json")
        self.assertEqual(code, 0, out)
        self.assertIn("pages listed 2, of which NOT evaluated: 1", out)

    @NEEDS_CRYPTO
    def test_the_published_test_key(self):
        """R5B-17: anyone can sign with it: CANNOT VERIFY, exit 2."""
        v = json.loads(VECTORS.read_text(encoding="utf-8"))
        bundle = dict(v["bundle"]["unsigned_bundle"],
                      signature=v["bundle"]["signature_block"])
        ok, why = B.verify_bundle(bundle, v["vector_key"]["public_hex"])
        self.assertTrue(ok, why)           # the library: the signature holds
        d = tmpdir(self)
        (d / "b.json").write_text(json.dumps(bundle, ensure_ascii=False),
                                  encoding="utf-8")
        code, out, _err = evidence("verify", d / "b.json", "--public-key",
                                   v["vector_key"]["public_hex"])
        self.assertEqual(code, 2, out)
        self.assertIn("PUBLISHED TEST KEY", out)
        self.assertNotIn("VALID", out.replace("CANNOT VERIFY", ""))

    def test_inspect_on_odd_bundles(self):
        """R5B-19."""
        d = tmpdir(self)

        def inspect(bundle) -> str:
            path = d / "b.json"
            if isinstance(bundle, bytes):
                path.write_bytes(bundle)
            else:
                path.write_text(json.dumps(bundle))
            return evidence("inspect", path)[1]
        out = inspect(dict(BODY, signature="VALID - verified by Bellbriar"))
        self.assertIn("signature   NOT a signature block (the bundle has a "
                      "string there)", out)
        self.assertIn("WARNING     malformed bundle", out)
        out = inspect({k: v for k, v in BODY.items() if k != "fetch"})
        self.assertIn("fetched     ? (the bundle has no fetch record: "
                      "malformed)", out)
        self.assertNotIn("a file run", out)
        out = inspect(dict(BODY))
        self.assertIn("fetched     nothing: a file run", out)
        self.assertNotIn("WARNING", out)
        out = inspect(dict(BODY, baseline={"x": 1}))
        self.assertIn("its maker's own", out)
        self.assertNotIn("the bundle is malformed there", out)
        out = inspect(json.dumps(dict(BODY, coverage_note="aéb"),
                                 ensure_ascii=False).encode("utf-8")
                      .replace("é".encode(), b"\xff"))
        self.assertIn("not valid UTF-8", out)
        self.assertIn("digest      none (malformed)", out)
        out = inspect(dict(BODY, inputs=[
            {"path": "a.html", "sha256": "0" * 64, "bytes": 1},
            {"kind": "url-snapshot", "path": "https://x.example/",
             "sha256": "0" * 64, "bytes": 1}]))
        self.assertIn("inputs      2: 1 file(s), 1 page snapshot(s)", out)


# ---------------------------------------------------------------------------
# The R5 field sweep
# ---------------------------------------------------------------------------

class TestFieldSweepFixes(unittest.TestCase):

    def test_a_name_failure_on_a_hidden_element_stays_a_failure(self):
        """R5C-1: a rendered run fails an unnamed link or image a
        stylesheet hides when captured, as a file run does: the page shows
        it later (a menu opened), or at a width the capture did not record
        (a tablet's), with no name. R5's first round made it a review,
        which passed real failures; reverted."""
        from tests.test_rendered_rules import P, attr, findings, rerun, snapshot
        body = (f'<nav{attr(P + "-hidden", "display")}><a href="/x?t=SECRET">'
                '<img src="a.png"></a></nav>')
        rendered = rerun(snapshot(body, root=attr(P + "-hidden",
                                                  "recorded")))
        plain = run_page(snapshot(body), "f.html", RB)
        for rule in ("bb-link-name", "bb-img-alt"):
            with self.subTest(rule=rule):
                seen = findings(rendered, rule)
                self.assertEqual([f.verdict for f in seen], [FAIL])
                self.assertNotIn("SECRET", seen[0].snippet)
                self.assertEqual([f.verdict for f in findings(plain, rule)],
                                 [FAIL])

    def test_a_customizable_selects_button(self):
        """R3D: a <select>'s first child <button> is inert (HTML): the
        select is the control. A rendered run, where Chromium draws a
        select of the default appearance without it (its content hidden),
        failed it for bb-button-name; a file run did not."""
        from tests.test_rendered_rules import P, attr, findings, rerun, snapshot
        body = ('<label for="s">Size</label><select id="s"><button>'
                f'<selectedcontent{attr(P + "-hidden", "display")}>Small'
                '</selectedcontent></button><option>Small</option>'
                '<option>Large</option></select>')
        rendered = rerun(snapshot(body, root=attr(P + "-hidden", "recorded")))
        plain = run_page(snapshot(body), "f.html", RB)
        for page in (rendered, plain):
            self.assertEqual(findings(page, "bb-button-name"), [])
        # A button after the first child is a button of its own.
        body = ('<select aria-label="Size"><option>Small</option></select>'
                '<div><button></button></div>')
        self.assertEqual([f.verdict for f in findings(
            run_page(snapshot(body), "f.html", RB), "bb-button-name")], [FAIL])

    def test_one_viewport_meta_is_one_finding(self):
        page = run_page(PAGE.replace(
            "</title>", '</title><meta name="viewport" content="width=device-'
            'width, user-scalable=no, maximum-scale=1.0">').format("")
            .encode(), "v.html", RB)
        found = [f for r in page.results if r.rule_id == "bb-viewport-zoom"
                 for f in r.findings]
        self.assertEqual(len(found), 1, found)
        self.assertEqual(found[0].message, "viewport meta disables pinch-zoom "
                         "(user-scalable=no) and caps zoom below 200% "
                         "(maximum-scale=1.0).")


# ---------------------------------------------------------------------------
# Round 2: the reviews of round 1 (R5C, R5D, L72, H6)
# ---------------------------------------------------------------------------

class TestMarkupRedactionRound2(unittest.TestCase):
    """R5C-4, R5C-13, R5D-2, R5D-9: a URL in a snippet is read as a browser
    reads it, and every query value in it, a javascript: or data: value's
    included, is replaced."""

    CASES = (
        ('<a href="//deploy:SECRETPW@staging.example/admin">',
         '<a href="//staging.example/admin">'),
        ('<a href="https:\\\\admin:SECRETPW@host/x">',
         '<a href="https:\\\\host/x">'),
        ('<a href="https:/\t/u:SECRETPW@h/x">', '<a href="https://h/x">'),
        ('<a href="https:user:SECRETPW@h/x">', '<a href="https:h/x">'),
        ('<a href="https:\n//u:SECRETPW@h/">', '<a href="https://h/">'),
        ('<form action="HTTPS://U:SECRETPW@H.example:8443/p?x=1">',
         '<form action="HTTPS://H.example:8443/p?x=REDACTED">'),
        ('<img srcset="/a.png?fields=a,b&token=SECRETTOK 1x, /b.png 2x">',
         '<img srcset="/a.png?fields=REDACTED&token=REDACTED 1x, '
         '/b.png 2x">'),
        ('<meta http-equiv="refresh" content="0; url=/a b?t=SECRETREF">',
         '<meta http-equiv="refresh" content="0; url=/a b?t=REDACTED">'),
        ('<a href="/s?q=shoes&amp;page=2">',
         '<a href="/s?q=REDACTED&amp;page=REDACTED">'),
        ('<a href="javascript:location=\'/reset?token=SECRETJS\'">',
         '<a href="javascript:location=\'/reset?token=REDACTED\'">'),
        ('<a href="javascript:fetch(\'https://u:SECRETPW@h/\')">',
         '<a href="javascript:fetch(\'https://h/\')">'),
        ('<a href="data:text/html,<a href=/x?t=SECRETD>">',
         '<a href="data:text/html,<a href=/x?t=REDACTED>">'),
        ('<a href="#/reset?SECRETQ">', '<a href="#/reset?REDACTED">'),
        ('<a href="#tok=SECRETF">', '<a href="#tok=REDACTED">'),
        ('<a href="#' + "x" * 70 + '">', '<a href="#REDACTED">'),
        ('<a href="#main">', '<a href="#main">'),
    )

    def test_each_case(self):
        from bellbriar_harness.redact import redact_markup
        for given, want in self.CASES:
            with self.subTest(given=given):
                self.assertEqual(redact_markup(given), want)
                self.assertNotIn("SECRET", redact_markup(given))


class TestTheRunsOwnSecrets(unittest.TestCase):
    """H6-1: a token a URL run was given, which the page writes into its
    own markup outside a URL attribute, reaches no report or bundle."""

    TOKEN = "TOKENabc1234567890xyz"

    def test_a_page_that_writes_its_token(self):
        from tests.test_fetch_hardening import _Site

        def echo(h):
            token = h.path.split("token=", 1)[-1]
            body = PAGE.format(f'<a href="/x" data-next="/next?token={token}">'
                               f'</a><p title="{token}">t</p>').encode()
            h.send_response(200)
            h.send_header("Content-Type", "text/html")
            h.send_header("Content-Length", str(len(body)))
            h.end_headers()
            h.wfile.write(body)
        site = _Site({"/p": echo})
        self.addCleanup(site.stop)
        d = tmpdir(self)
        code, out, err = run("--url", f"{site.base}/p?token={self.TOKEN}",
                             "--no-render", "--json", d / "r.json", "--html",
                             d / "r.html", "--bundle", d / "b.json",
                             "--fail-on", "never")
        self.assertEqual(code, 0, err)
        report = json.loads((d / "r.json").read_text())
        snippets = [f["snippet"] for p in report["pages"]
                    for f in p["findings"]]
        self.assertTrue(any("data-next" in s for s in snippets), snippets)
        for name in ("r.json", "r.html", "b.json"):
            self.assertNotIn(self.TOKEN, (d / name).read_text(), name)
        self.assertNotIn(self.TOKEN, out + err)

    def test_escaped_as_markup_too(self):
        from types import SimpleNamespace
        f = SimpleNamespace(snippet='<p title="a&amp;bTOKEN1234567890">',
                            message="a&bTOKEN1234567890 here")
        page = SimpleNamespace(results=[SimpleNamespace(findings=[f])])
        cli._scrub_findings([page], ["a&bTOKEN1234567890", "short"])
        self.assertEqual(f.snippet, '<p title="REDACTED">')
        self.assertEqual(f.message, "REDACTED here")


class TestNamesRound2(unittest.TestCase):
    """R5D-1, R5D-10, R5D-12."""

    def test_names_are_escaped_one_to_one(self):
        self.assertEqual(B.name_escaped("a%80.html"), "a%2580.html")
        self.assertEqual(B.name_escaped("a\udc80.html"), "a%80.html")
        self.assertEqual(B.name_escaped("plain.html"), "plain.html")

    def test_two_names_one_escape_apart(self):
        """R5D-1: "a%80.html" and a name whose byte 0x80 is not UTF-8 were
        both recorded "a%80.html", and naming them ran forever."""
        d = tmpdir(self)
        site = d / "u"
        site.mkdir()
        (site / "a%80.html").write_text(PAGE.format(""))
        try:
            with open(os.path.join(os.fsencode(site), b"a\x80.html"),
                      "wb") as fh:
                fh.write(PAGE.format("<img src=a.png>").encode())
        except (OSError, ValueError):
            self.skipTest("this file system refuses names that are not UTF-8")
        code, _out, err = run(site, "--bundle", d / "b.json", "--fail-on",
                              "never")
        self.assertEqual(code, 0, err)
        bundle = json.loads((d / "b.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(p["path"] for p in bundle["pages"]),
                         ["u/a%2580.html", "u/a%80.html"])

    def test_naming_always_ends(self):
        """Files told apart only by a home folder are numbered; files that
        keep their names (a --render run's pages) are never renamed, and a
        served file that clashes with one grows instead (R5D-10)."""
        pairs = [(Path("/home/a/site/index.html"), "site/index.html"),
                 (Path("/home/b/site/index.html"), "site/index.html")]
        got = [n for _, n in cli._distinct(pairs)]
        self.assertEqual(len(set(got)), 2, got)
        self.assertTrue(all(n.endswith("site/index.html") for n in got))
        pairs = [(Path("/r1/dist/assets/app.js"), "dist/assets/app.js"),
                 (Path("/r2/dist/assets/app.js"), "dist/assets/app.js")]
        got = [n for _, n in cli._distinct(pairs, fixed=1)]
        self.assertEqual(got, ["dist/assets/app.js", "r2/dist/assets/app.js"])
        # The same file named twice keeps one name.
        same = [(Path("/r1/a.html"), "a.html"), (Path("/r1/a.html"), "a.html")]
        self.assertEqual([n for _, n in cli._distinct(same)],
                         ["a.html", "a.html"])

    def test_a_first_part_holding_a_colon_or_a_lookalike(self):
        """R5D-12: "./" goes before it, so no reader takes it for a URL."""
        for name in ("ㅤhttps:/x.html", "⠀https:/a.html", "https：/a.html",
                     "һttps:/a.html", "notes:x/a.html"):
            with self.subTest(name=name):
                self.assertTrue(B.recorded_path(name).startswith("./"))
        for name in ("dir/https:/a.html", "a.html", "https.html"):
            with self.subTest(name=name):
                self.assertFalse(B.recorded_path(name).startswith("./"))


class TestServedAsEvaluated(unittest.TestCase):
    """R5D-7: a page read again as the file it is (a server-HTML reading
    of a --render run) is hashed as last sent, not as first sent."""

    def test_first_and_last_sending(self):
        import urllib.request
        from bellbriar_harness.serve import BuildServer
        d = tmpdir(self)
        page = d / "a.html"
        page.write_text("first")
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with BuildServer(d) as server:
            url = server.url_for(page)
            self.assertEqual(opener.open(url, timeout=10).read(), b"first")
            page.write_text("second!")
            self.assertEqual(opener.open(url, timeout=10).read(), b"second!")
            first = (hashlib.sha256(b"first").hexdigest(), 5)
            last = (hashlib.sha256(b"second!").hexdigest(), 7)
            self.assertEqual(cli._served_digest(server, page), first)
            self.assertEqual(cli._served_digest(server, page, last=True),
                             last)


@NEEDS_CRYPTO
class TestEvidenceRound2(unittest.TestCase):
    """R5D-5, R5D-6, R5D-13, R5D-14, R5D-15."""

    def test_a_forged_key_id_is_not_said_to_be_a_private_half(self):
        """R5D-5: verify called a bundle "signed with that public key as
        its private key" on the bundle's word, its key_id; the library and
        the JavaScript verifier said INVALID."""
        priv, pub, _kid = B.generate_keypair()
        derived = B.ed25519.Ed25519PrivateKey.from_private_bytes(
            bytes.fromhex(pub)).public_key().public_bytes_raw().hex()
        kid = B.key_id_for(derived)
        bundle = B.sign_bundle_local(dict(BODY), priv)
        sig = bundle["signature"]
        sig["key_id"] = kid
        sig["statement"]["key_id"] = kid
        sig["signature_b64"] = base64.b64encode(bytes(64)).decode()
        d = tmpdir(self)
        (d / "b.json").write_text(json.dumps(bundle))
        code, out, _err = evidence("verify", d / "b.json", "--public-key", pub)
        self.assertEqual(code, 1, out)
        self.assertNotIn("PRIVATE half", out)

    def test_no_bundle_its_verifier_refuses(self):
        """R5D-6: a rulebook without rulebook_version made a bundle the
        harness signed and its own verifier refused."""
        d = tmpdir(self)
        rulebook = json.loads((ROOT / "src" / "bellbriar_harness" /
                               "rulebook.json").read_text(encoding="utf-8"))
        del rulebook["rulebook_version"]
        (d / "rb.json").write_text(json.dumps(rulebook))
        key, _pub = keypair(self)
        code, _out, err = run(FIXTURES / "good.html", "--rulebook",
                              d / "rb.json", "--bundle", d / "b.json",
                              "--sign-key", key, "--fail-on", "never")
        self.assertEqual(code, 2, err)
        self.assertIn("the rulebook gives no rulebook_version", err)
        self.assertFalse((d / "b.json").exists())
        code, _out, err = run(FIXTURES / "good.html", "--rulebook",
                              d / "rb.json", "--fail-on", "never")
        self.assertEqual(code, 0, err)          # a run without a bundle

    def test_a_bundle_larger_than_a_verifier_reads(self):
        """R5D-14: the producer refuses what verify would refuse."""
        d = tmpdir(self)
        with mock.patch.object(B, "MAX_BUNDLE_FILE", 100):
            code, _out, err = run(FIXTURES / "good.html", "--bundle",
                                  d / "b.json", "--fail-on", "never")
        self.assertEqual(code, 2, err)
        self.assertIn("more than the 100 bellbriar-evidence verify reads", err)
        self.assertFalse((d / "b.json").exists())

    @unittest.skipUnless(hasattr(os, "symlink"), "no symbolic links")
    def test_a_link_to_the_public_half_never_signs(self):
        """R5D-13."""
        key, pub = keypair(self)
        link = key.parent / "other.key"
        os.symlink(pub, link)
        code, _out, err = run(FIXTURES / "good.html", "--bundle",
                              key.parent / "b.json", "--sign-key", link)
        self.assertEqual(code, 2, err)
        self.assertIn("or a link to one", err)

    def test_what_verify_and_inspect_say(self):
        """R5D-15."""
        d = tmpdir(self)

        def inspect(bundle) -> str:
            (d / "i.json").write_text(json.dumps(bundle))
            return evidence("inspect", d / "i.json")[1]
        out = inspect(dict(BODY, signature={}))
        self.assertIn("signature   an EMPTY signature block: malformed", out)
        self.assertNotIn("UNSIGNED", out)
        out = inspect(dict(BODY, judged={}))
        self.assertIn("the bundle's own claim: this release runs no judge",
                      out)
        self.assertNotIn("judged      not run", out)
        out = inspect(dict(BODY, baseline="none"))
        self.assertIn("baseline    NOT a record (the bundle has a string "
                      "there)", out)
        with self.assertRaises(B.MalformedBundle) as cm:
            B.check_body({k: v for k, v in BODY.items()
                          if k != "bundle_format"})
        self.assertIn("has no bundle_format", str(cm.exception))
        priv, pub, _ = B.generate_keypair()
        ok, why = B.verify_bundle(B.sign_bundle_local(dict(BODY, pack={}),
                                                      priv), pub)
        self.assertTrue(ok, why)
        self.assertIn("it carries a pack record with no name", why)
        (d / "bom.pub").write_bytes(b"\xef\xbb\xbf"
                                    + B.key_file_text(pub, False).encode())
        (d / "s.json").write_text(json.dumps(
            B.sign_bundle_local(dict(BODY), priv)))
        code, out, _err = evidence("verify", d / "s.json", "--public-key",
                                   d / "bom.pub")
        self.assertEqual(code, 2, out)
        self.assertIn("names a file that holds no Ed25519 public key", out)

    def test_a_key_that_is_no_point(self):
        """R5D-15: y = 2 has no x on the curve: no private key has it, and
        no signature under it shows anything. CANNOT VERIFY, exit 2."""
        with self.assertRaises(ValueError) as cm:
            B.check_public_key("02" + "00" * 31)
        self.assertIn("no point of Ed25519's curve", str(cm.exception))
        self.assertTrue(B.off_curve(bytes.fromhex("02" + "00" * 31)))
        for _ in range(50):
            _priv, pub, _kid = B.generate_keypair()
            self.assertEqual(B.check_public_key(pub), pub)

    def test_only_ascii_white_space_around_a_key(self):
        """R5D-11."""
        _priv, pub, _ = B.generate_keypair()
        self.assertEqual(B.check_public_key(" \t" + pub + "\r\n"), pub)
        for odd in ("\x1c", "\x85", "\xa0", " "):
            with self.subTest(char=repr(odd)), self.assertRaises(ValueError):
                B.check_public_key(pub + odd)
        self.assertEqual(B.parse_key_text(pub + "\x85\n"), (None, None))

    def test_a_reader_that_stops_reading(self):
        """R5D-15: `inspect … | head` ended in a BrokenPipeError
        traceback; now in status 2 and nothing more."""
        from bellbriar_harness.redact import run_escaped

        def main(argv):
            print("one line")
            raise BrokenPipeError(32, "Broken pipe")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(run_escaped(main, []), 2)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(run_escaped(lambda argv: 0, []), 0)


class TestOutputsRound2(unittest.TestCase):
    """R5D-8: an output never replaces evidence: no output in the
    --save-snapshots folder, none over an input, none twice under two
    names (a hard link)."""

    def test_an_output_in_the_snapshot_folder(self):
        d = tmpdir(self)
        (d / "s").mkdir()
        code, _out, err = run("--url", "http://127.0.0.1:9/p",
                              "--save-snapshots", d / "s", "--bundle",
                              d / "s" / "001-p.html")
        self.assertEqual(code, 2, err)
        self.assertIn("names a file in the --save-snapshots folder", err)

    def test_an_output_over_an_input(self):
        d = tmpdir(self)
        shutil.copy(FIXTURES / "good.html", d / "p.html")
        before = (d / "p.html").read_bytes()
        code, _out, err = run(d / "p.html", "--bundle", d / "p.html")
        self.assertEqual(code, 2, err)
        self.assertIn("names a file this run evaluates", err)
        self.assertEqual((d / "p.html").read_bytes(), before)

    @unittest.skipUnless(hasattr(os, "link"), "no hard links")
    def test_two_names_of_one_file(self):
        d = tmpdir(self)
        (d / "a.json").write_text("{}")
        try:
            os.link(d / "a.json", d / "hl.json")
        except OSError:
            self.skipTest("this file system refuses hard links")
        code, _out, err = run(FIXTURES / "good.html", "--json", d / "a.json",
                              "--bundle", d / "hl.json")
        self.assertEqual(code, 2, err)
        self.assertIn("name the same file", err)


class TestGuardRound2(unittest.TestCase):
    """R5C-5, R5C-9, R5C-14, R5D-15."""

    setUp = R4.TestReviewOfR4Guard.setUp
    guard = R4.TestReviewOfR4Guard.guard

    def test_a_keygen_private_key_file_by_any_name(self):
        """R5D-15: a key file keygen wrote, renamed (not *.key)."""
        text = B.key_file_text(self.priv.hex(), True)
        problems = self.guard({"notes/backup.txt": text})
        self.assertTrue(any("holds a private key file as bellbriar-evidence "
                            "keygen writes it" in p for p in problems),
                        problems)
        self.assertEqual(self.guard({"keys/x.pub": B.key_file_text(
            self.pub.hex(), False)}), [])

    def test_a_key_in_a_literal_with_an_escaped_quote(self):
        """R5C-5: a seed holding byte 0x22, written \\" in a UTF-16
        literal, made the file read as binary, and the key went unread."""
        from cryptography.hazmat.primitives.asymmetric import ed25519
        while True:
            seed = bytearray(os.urandom(32))
            seed[5] = 0x22
            if not any(b in seed for b in b"\\\r\n"):
                break
        seed = bytes(seed)
        key = ed25519.Ed25519PrivateKey.from_private_bytes(seed)
        pub = key.public_key().public_bytes_raw()
        kid = hashlib.sha256(pub).hexdigest()[:16]
        literal = seed.decode("latin-1").replace('"', '\\"')
        data = ('KEY = "' + literal + '"\n').encode("utf-16-le")
        problems = self.guard({f"keys/{kid}.pub": pub.hex(), "k.py": data})
        self.assertTrue(any("private half" in p for p in problems), problems)

    def test_a_blob_cut_short(self):
        """R5C-9: part of a blob was read as all of it."""
        import repo_guard
        cut = ("import sys; sha = sys.stdin.readline().strip(); "
               "sys.stdout.buffer.write(sha.encode() + b' blob 10\\n' "
               "+ b'abcde'); sys.stdout.flush()")
        with self.assertRaises(subprocess.SubprocessError):
            list(repo_guard._blobs([sys.executable, "-c", cut], ["x" * 40]))
        failed = ("import sys; sha = sys.stdin.readline().strip(); "
                  "sys.stdout.buffer.write(sha.encode() + b' blob 2\\nab\\n'); "
                  "sys.stdout.flush(); sys.exit(3)")
        with self.assertRaises(subprocess.SubprocessError):
            list(repo_guard._blobs([sys.executable, "-c", failed], ["x" * 40]))

    def test_one_member_budget_for_a_file_and_its_archives(self):
        """R5C-14: many archives of many empty members cost a minute a
        file; members now count against one budget, as bytes do."""
        import zipfile
        import repo_guard
        inner = io.BytesIO()
        with zipfile.ZipFile(inner, "w") as z:
            for i in range(6):
                z.writestr(f"e{i}.txt", "")
        outer = io.BytesIO()
        with zipfile.ZipFile(outer, "w") as z:
            for i in range(4):
                z.writestr(f"in{i}.zip", inner.getvalue())
        with mock.patch.object(repo_guard, "_MAX_ALL_MEMBERS", 12):
            problems = self.guard({"a.zip": outer.getvalue()})
        self.assertTrue(any("members the guard reads of one file and the "
                            "archives inside it" in p for p in problems),
                        problems)
        self.assertEqual(self.guard({"a.zip": outer.getvalue()}), [])


class TestRuntimeWordsRound2(unittest.TestCase):
    """R5C-11, R5C-12."""

    def test_a_status_of_ten_digits(self):
        exc = F.FetchError(F.WENT_ELSEWHERE + "HTTP 2147483647" + F.WENT_TO
                           + "https://x.example/")
        self.assertEqual(F.render_failure(exc),
                         "FetchError: " + F.WENT_ON + "answered HTTP "
                         "2147483647")

    def test_where_it_went_is_its_own_line(self):
        from types import SimpleNamespace
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            cli._say_detail(SimpleNamespace(detail="", where="https://x."
                                            "example/?t=REDACTED"), "", str)
        self.assertEqual(err.getvalue(), "[bellbriar] it went to (not "
                         "recorded): https://x.example/?t=REDACTED\n")


class TestRulesRound2(unittest.TestCase):
    """L72 and the H6 claims audit: rules whose criteria or verdicts the
    reviews found wrong."""

    @staticmethod
    def found(html, rule, path="t.html"):
        page = run_page(html, path, RB)
        for r in page.results:
            if r.rule_id == rule:
                return r.applicable, [(f.verdict, f.impact) for f in r.findings]
        raise AssertionError(f"{rule} did not run")

    def page(self, body, head="", html_attrs=' lang="en"', body_attrs=""):
        return (f'<!doctype html><html{html_attrs}><head><title>T</title>'
                f'{head}</head><body{body_attrs}>{body}</body></html>')

    def test_a_duplicated_id_fails_only_where_a_name_depends_on_it(self):
        """L72-2, L72-3, L72-7, L72-14, H6-10."""
        main = "<main><h1>x</h1></main>"
        cases = (
            ('<label for="e">Email</label><input id="e"><div id="e">x</div>',
             [(FAIL, "serious")]),
            ('<span id="n">Name</span><span id="n">Other</span>'
             '<button aria-labelledby="n"></button>', [(FAIL, "serious")]),
            ('<p id="d">a</p><p id="d">b</p><button aria-describedby="d">Go'
             '</button>', [(NEEDS_REVIEW, "moderate")]),
            ('<table><tr><th id="h">A</th><th id="h">B</th></tr><tr><td '
             'headers="h">1</td><td>2</td></tr></table>',
             [(NEEDS_REVIEW, "moderate")]),
            ('<a href="#s">Go</a><div id="s">a</div><div id="s">b</div>',
             [(NEEDS_REVIEW, MINOR)]),
            ('<div id="u">a</div><div id="u">b</div>',
             [(NEEDS_REVIEW, MINOR)]),
        )
        for body, want in cases:
            with self.subTest(body=body):
                self.assertEqual(self.found(self.page(body + main),
                                            "bb-duplicate-id"), (True, want))
        self.assertEqual(self.found(self.page(main), "bb-duplicate-id"),
                         (False, []))
        self.assertEqual(self.found(self.page('<main id="m"><h1>x</h1>'
                                              '</main>'), "bb-duplicate-id"),
                         (True, []))

    def test_aria_hidden_on_the_page_hides_nothing(self):
        """L72-4: browsers ignore aria-hidden on <html> and <body>, as
        WAI-ARIA tells them to: its content is checked as exposed."""
        body = '<main><h1>x</h1><button></button><a href="/x">Go</a></main>'
        for html in (self.page(body, body_attrs=' aria-hidden="true"'),
                     self.page(body, html_attrs=' lang="en" '
                               'aria-hidden="true"')):
            with self.subTest(html=html[:60]):
                self.assertEqual(self.found(html, "bb-button-name"),
                                 (True, [(FAIL, "blocker")]))
                self.assertEqual(self.found(html, "bb-aria-hidden-focus"),
                                 (False, []))
        inner = self.page('<main><h1>x</h1><div aria-hidden="true"><button>'
                          '</button></div></main>')
        self.assertEqual(self.found(inner, "bb-button-name"), (False, []))
        self.assertEqual(self.found(inner, "bb-aria-hidden-focus"),
                         (True, [(FAIL, "serious")]))
        rule = {r["id"]: r for r in RB["rules"]}["bb-aria-hidden-body"]
        self.assertEqual(rule["verdict_basis"], "best-practice")

    def test_a_label_names_a_progress_bar_a_meter_and_a_button(self):
        """L72-11: <progress>, <meter>, <output> and <button> are
        labelable."""
        main = "<main><h1>x</h1>{}</main>"
        for body, rule in (
                ('<label for="p">Upload</label><progress id="p" '
                 'role="progressbar" value="3" max="10"></progress>',
                 "bb-progress-name"),
                ('<label>Disk <meter role="meter" value="0.3"></meter></label>',
                 "bb-progress-name"),
                ('<label for="b">Search</label><button id="b"></button>',
                 "bb-button-name")):
            with self.subTest(body=body):
                self.assertEqual(self.found(self.page(main.format(body)),
                                            rule), (True, []))
        self.assertEqual(self.found(self.page(main.format(
            '<progress role="progressbar" value="3" max="10">30%</progress>')),
            "bb-progress-name"), (True, [(FAIL, "serious")]))
        # A <div> is not labelable: a label beside it names nothing.
        self.assertEqual(self.found(self.page(main.format(
            '<label for="d">Upload</label><div id="d" role="progressbar">'
            '</div>')), "bb-progress-name"), (True, [(FAIL, "serious")]))

    def test_header_cells_by_role(self):
        """L72-12: F91 names columnheader and rowheader roles."""
        rows = "".join(f"<tr><td>{i}</td><td>{i}</td><td>{i}</td></tr>"
                       for i in range(2))
        head = ('<tr><td role="columnheader">A</td><td role="columnheader">'
                'B</td><td role="columnheader">C</td></tr>')
        self.assertEqual(self.found(self.page(
            f"<main><h1>x</h1><table>{head}{rows}</table></main>"),
            "bb-table-headers"), (True, []))
        bare = "<tr><td>A</td><td>B</td><td>C</td></tr>"
        self.assertEqual(self.found(self.page(
            f"<main><h1>x</h1><table>{bare}{rows}</table></main>"),
            "bb-table-headers"), (True, [(FAIL, "moderate")]))

    def test_a_presentational_images_alt_is_never_read(self):
        """H6-3."""
        self.assertEqual(self.found(self.page(
            '<main><h1>x</h1><img src="s.gif" alt="spacer.gif" '
            'role="presentation"></main>'), "bb-alt-junk"), (False, []))
        self.assertEqual(self.found(self.page(
            '<main><h1>x</h1><img src="a.png" alt="IMG_1234.png"></main>'),
            "bb-alt-junk"), (True, [(FAIL, "serious")]))

    def test_autoplaying_sound_is_1_4_2s(self):
        """L72-1: 2.2.2 concerns moving visual content."""
        rule = {r["id"]: r for r in RB["rules"]}["bb-media-autoplay"]
        self.assertEqual(rule["sc"], ["1.4.2"])
        self.assertEqual(rule["w3c_failures"], ["F93"])
        page = run_page(self.page('<main><h1>x</h1><video src="v.mp4" '
                                  'autoplay muted></video></main>'), "t.html",
                        RB)
        f = [f for r in page.results if r.rule_id == "bb-media-autoplay"
             for f in r.findings]
        self.assertEqual([x.verdict for x in f], [NEEDS_REVIEW])
        self.assertIn("1.4.2 is met", f[0].message)

    def test_a_marquee_review_says_it_is_pled(self):
        """H6-7: --strict gates it, so the report says why."""
        page = run_page(self.page('<main><h1>x</h1><marquee behavior="slide">'
                                  'Hi</marquee></main>'), "t.html", RB)
        f = [f for r in page.results if r.rule_id == "bb-marquee-blink"
             for f in r.findings]
        self.assertEqual([x.verdict for x in f], [NEEDS_REVIEW])
        self.assertIn("pled in complaints", f[0].message)

    def test_a_navigation_a_toggle_collapses(self):
        """L72-13: SCR28 (ACT 3e12e1) can bypass blocks: a review, not a
        FAIL; markup cannot show the toggle collapses anything."""
        text = "<div><p>" + "Lots of content here. " * 20 + "</p></div>"
        links = ('<li><a href="/a">A</a></li><li><a href="/b">B</a></li>'
                 '<li><a href="/c">C</a></li>')
        toggled = self.page('<header><button aria-expanded="true" '
                            'aria-controls="menu">Menu</button><nav><ul '
                            f'id="menu">{links}</ul></nav></header>{text}')
        self.assertEqual(self.found(toggled, "bb-skip-link"),
                         (True, [(NEEDS_REVIEW, "moderate")]))
        plain = self.page(f'<header><nav><ul>{links}</ul></nav></header>'
                          f'{text}')
        self.assertEqual(self.found(plain, "bb-skip-link"),
                         (True, [(FAIL, "serious")]))
        # Two more links in the page header are still a block.
        more = toggled.replace("<header>", '<header><a href="/">Logo</a>'
                               '<a href="/account">Account</a>')
        self.assertEqual(self.found(more, "bb-skip-link"),
                         (True, [(FAIL, "serious")]))

    def test_text_the_pages_own_style_hides_names_nothing(self):
        """H6-4: a file run reads the page's own <style> for names too, as
        a rendered run reads what the stylesheets hide."""
        head = "<style>.closed{display:none}.ghost{visibility:hidden}</style>"
        html = self.page('<main><h1>x</h1><a href="/y"><span class="closed">'
                         'Hidden name</span></a><a href="/z"><span '
                         'class="ghost">Ghost</span></a><a href="/w"><span '
                         'class="ghost">G <b style="visibility:visible">Shown'
                         '</b></span></a></main>', head=head)
        self.assertEqual(self.found(html, "bb-link-name"),
                         (True, [(FAIL, "blocker"), (FAIL, "blocker")]))

    def test_an_object_that_shows_no_media(self):
        """H6-2: ACT 8fc3b6 requires a name only of an object showing an
        image, audio or video."""
        from tests.test_rendered_rules import (P, attr, findings, mark,
                                               rerun, run_record, snapshot)
        fail = attr(P + "-axe", mark(("object-alt", "fail", "serious",
                                      "Element has no text alternative")))
        for obj, verdict in (
                (f'<object data="frag.html" type="text/html"{fail}></object>',
                 NEEDS_REVIEW),
                (f'<object data="notes.txt"{fail}></object>', NEEDS_REVIEW),
                (f'<object data="chart" type="image/svg+xml"{fail}></object>',
                 FAIL),
                (f'<object data="/media/clip.MP4?v=2"{fail}></object>', FAIL)):
            with self.subTest(obj=obj):
                page = rerun(snapshot(obj, root=attr(
                    P + "-axe-run", run_record(["object-alt"]))))
                got = findings(page, "bb-object-alt")
                self.assertEqual([f.verdict for f in got], [verdict])

    def test_coverage_says_when_axe_core_did_not_run_every_rule(self):
        """H6-6, and H6-24's keyboard sentence."""
        from bellbriar_harness import engine as E
        from tests.test_rendered_rules import P, attr, rerun, run_record, snapshot
        from tests.test_review_round_q import ALL_AXE
        short = rerun(snapshot("<p>x</p>", root=attr(
            P + "-axe-run", run_record([], ALL_AXE[:-3]))))
        sentence = E.coverage_sentence([short])
        self.assertIn("though not every one of them on 1 of those pages",
                      sentence)
        self.assertIn("Keyboard operability (beyond whether scrollable "
                      "regions can take focus)", sentence)
        full = rerun(snapshot("<p>x</p>", root=attr(
            P + "-axe-run", run_record([], ALL_AXE))))
        self.assertNotIn("not every one", E.coverage_sentence([full]))
        self.assertNotIn("scrollable", E.COVERAGE_SENTENCE)

    def test_a_run_with_a_page_left_out_names_its_denominators(self):
        """H6-11."""
        d = tmpdir(self)
        (d / "shell.html").write_text(
            '<!doctype html><html lang="en"><head><title>App</title></head>'
            '<body><div id="root"></div><script src="/app.js"></script>'
            '</body></html>')
        code, out, err = run(FIXTURES / "good.html", d / "shell.html",
                             "--html", d / "r.html")
        self.assertEqual(code, 0, err)
        self.assertIn("1 of 2 page(s) NOT evaluated: the pass rate leaves "
                      "them out, and the tier-1-clean share counts only the "
                      "1 page(s) whose Tier-1 result is known.", out)
        self.assertIn("of the 1 page(s) whose Tier-1 result is known, with 1 "
                      "page(s) NOT evaluated", (d / "r.html").read_text())

    def test_no_layer_note_names_v0(self):
        """H6-15, H6-16."""
        from bellbriar_harness import browser_contracts
        from bellbriar_harness.engine import LAYERS
        for _layer, _status, note in LAYERS:
            self.assertNotIn("v0", note)
            self.assertNotIn("bellbriar-harness[browser]", note)
        self.assertNotIn("v0", browser_contracts._NOT_IMPLEMENTED)

    def test_a_component_the_linter_cannot_follow(self):
        """H6-19: its links and buttons are not counted, as the README now
        says: a div with a click handler around it is an error (the usual
        case is an icon from a library), as around plain content; one
        around content passed in is a warning."""
        d = tmpdir(self)
        (d / "Local.jsx").write_text(
            "export default function Local() { return <p>hi</p>; }\n")
        src = ('import { Card } from "some-ui";\n'
               'import Local from "./Local";\n'
               'function Own() { return <span>t</span>; }\n'
               'export function A({x}) { return (<div>\n'
               '  <div onClick={x}><Unknown/></div>\n'
               '  <div onClick={x}><Card/></div>\n'
               '  <div onClick={x}><Own/></div>\n'
               '  <div onClick={x}><Local/></div>\n'
               '  <div onClick={x}>{children}</div>\n'
               '</div>); }\n')
        (d / "a.jsx").write_text(src)
        got = {f.line: f.severity for f in L.lint_text(src, str(d / "a.jsx"))
               if f.rule_id == "bl-div-click"}
        self.assertEqual(got, {5: L.ERROR, 6: L.ERROR, 7: L.ERROR,
                               8: L.ERROR, 9: L.WARN})



# ---------------------------------------------------------------------------
# Round 3: the reviews of round 2 (R5E, R5F, R5G)
# ---------------------------------------------------------------------------

def _hold(test) -> int:
    """A loopback port that accepts connections and never answers."""
    import socket
    import threading
    hold = socket.socket()
    hold.bind(("127.0.0.1", 0))
    hold.listen(16)
    held = []

    def accept():
        while True:
            try:
                conn, _ = hold.accept()
            except OSError:
                return
            held.append(conn)
    threading.Thread(target=accept, daemon=True).start()

    def close():
        hold.close()
        for c in held:
            c.close()
    test.addCleanup(close)
    return hold.getsockname()[1]


class TestSecretsRound3(unittest.TestCase):
    """R5E-1, R5E-2, R5E-3, R5E-9, R5E-10, R5E-14: what a finding quotes
    holds no secret, cut or not, in a locator too."""

    TOKEN = "TOKENabc1234567890xyz"

    def test_a_url_with_white_space_in_its_authority(self):
        """R5E-1: the snippet was collapsed before it was redacted."""
        for href in ("https:\t//u:SECRETPW@h.example/x",
                     "https:\n//u:SECRETPW@h.example/x"):
            with self.subTest(href=repr(href)):
                page = run_page(PAGE.format(f'<a href="{href}"></a>'),
                                "t.html", RB)
                snippets = [f.snippet for r in page.results
                            for f in r.findings]
                self.assertTrue(snippets)
                self.assertFalse(any("SECRETPW" in x for x in snippets),
                                 snippets)

    def test_fragments_and_text(self):
        """R5E-9, R5E-14: a percent-encoded fragment parameter, and a URL
        with no slash after its scheme in text."""
        from bellbriar_harness.redact import redact_markup
        for given in (
                '<a href="https://h.example/cb#/access_token%3DSECRETTOKEN123">'
                'x</a>',
                '<a href="https://h.example/cb#access_token%3DSECRETTOKEN1">'
                'x</a>',
                '<a href="/r#/route%3Ftoken%3DSECRETTOKEN2">x</a>',
                '<p>see https:user:SECRETPW@h.example/x</p>'):
            with self.subTest(given=given):
                self.assertNotIn("SECRET", redact_markup(given))

    def test_a_short_password(self):
        """R5E-10: a password of four characters or more is the run's
        secret whatever its shape."""
        from bellbriar_harness.redact import (reset_run_secrets,
                                              scrub_secrets, set_run_secrets)
        token = set_run_secrets((), passwords=("pw12", "abc"))
        try:
            self.assertEqual(scrub_secrets("user pw12 and pw12%"),
                             "user REDACTED and REDACTED%")
            self.assertEqual(scrub_secrets("abc"), "abc")
        finally:
            reset_run_secrets(token)

    def test_a_page_that_writes_its_token_into_an_id(self):
        """R5E-2, R5E-3: the token as an id (in the locator), and straddling
        the snippet's cut."""
        from tests.test_fetch_hardening import _Site

        def echo(h):
            token = h.path.split("token=", 1)[-1]
            body = PAGE.format(
                f'<button id="{token}"></button><a href="/x" data-pad="'
                f'{"y" * 150}{token}"></a>').encode()
            h.send_response(200)
            h.send_header("Content-Type", "text/html")
            h.send_header("Content-Length", str(len(body)))
            h.end_headers()
            h.wfile.write(body)
        site = _Site({"/p": echo})
        self.addCleanup(site.stop)
        d = tmpdir(self)
        code, out, err = run("--url", f"{site.base}/p?token={self.TOKEN}",
                             "--no-render", "--json", d / "r.json",
                             "--bundle", d / "b.json", "--fail-on", "never")
        self.assertEqual(code, 0, err)
        report = json.loads((d / "r.json").read_text())
        found = {f["rule_id"]: f for p in report["pages"]
                 for f in p["findings"]}
        self.assertIn("bb-button-name", found)
        self.assertIn("bb-link-name", found)
        for name in ("r.json", "b.json"):
            text = (d / name).read_text()
            for i in range(len(self.TOKEN) - 8):
                self.assertNotIn(self.TOKEN[i:i + 9], text, name)
        self.assertNotIn(self.TOKEN[:9], out + err)


@unittest.skipUnless(HAVE_BROWSER, _WHY)
class TestNavigationRound3(unittest.TestCase):
    """R5E-4, R5E-5, R5E-6, R5E-12: where a page sends the browser."""

    site = staticmethod(R4.TestReviewOfR4Round4.site)

    @staticmethod
    def page(script="", body="<p>x</p>"):
        return PAGE.format(f"{body}<script>{script}</script>").encode()

    def test_a_page_gone_to_before_the_load_that_never_loads(self):
        """R5E-4: refused, never scored from the first page's server
        HTML."""
        from tests.test_fetch_hardening import send
        port = _hold(self)
        site = self.site({
            "/a": send(PAGE.format("").replace(
                "</title>", "</title><script>location.replace('/b')"
                "</script>").encode()),
            "/b": send(self.page(
                "", f'<img src="http://127.0.0.1:{port}/x.png" alt="">'))})
        self.addCleanup(site.stop)
        with self.assertRaises(F.FetchError) as cm:
            F.fetch(site.base + "/a", timeout_ms=4000)
        self.assertIn("did not finish loading", str(cm.exception))

    def test_a_navigation_that_never_commits(self):
        """R5E-6: after the load, and before it; within the load timeout,
        not the render deadline; in words of its own; a --render run reads
        the file instead."""
        from tests.test_fetch_hardening import send
        port = _hold(self)
        never = f"http://127.0.0.1:{port}/never?t=SECRETQ"
        site = self.site({
            "/after": send(self.page(
                f"onload = function () {{ setTimeout(function () {{"
                f" location.href = '{never}'; }}, 300); }};")),
            "/head": send(PAGE.format("").replace(
                "</title>", f"</title><script>location.href = '{never}';"
                "</script>").encode())})
        self.addCleanup(site.stop)
        for path in ("/after", "/head"):
            with self.subTest(path=path):
                start = time.monotonic()
                with self.assertRaises(F.FetchError) as cm:
                    F.fetch(site.base + path, timeout_ms=4000)
                self.assertLess(time.monotonic() - start, 40)
                text = str(cm.exception)
                self.assertIn("which had not arrived when the harness "
                              "stopped waiting for it", text)
                self.assertIn("cannot be captured while the browser waits "
                              "to leave it", text)
                self.assertNotIn("SECRETQ", text)
                self.assertNotIn("may never yield", text)
        r = F.fetch(site.base + "/after", timeout_ms=4000,
                    error_target="fallback",
                    fallback="read as the file it is")
        self.assertEqual(r.mode, "server")
        self.assertIn("had not arrived", r.fallback_reason)

    def test_before_a_render_deadline_shorter_than_the_load_timeout(self):
        """R5E-6: the reviewer's case: the deadline came first and blamed
        a script."""
        from tests.test_fetch_hardening import send
        port = _hold(self)
        site = self.site({"/after": send(self.page(
            "onload = function () { setTimeout(function () { location.href ="
            f" 'http://127.0.0.1:{port}/never'; }}, 300); }};"))})
        self.addCleanup(site.stop)
        start = time.monotonic()
        with self.assertRaises(F.FetchError) as cm:
            F.fetch(site.base + "/after", timeout_ms=30_000, deadline_s=9)
        self.assertLess(time.monotonic() - start, 9)
        self.assertIn("had not arrived", str(cm.exception))

    def test_a_slow_page_gone_to_is_read(self):
        """R5E-6: a navigation that commits late, within the load timeout,
        is followed as before."""
        import threading
        from tests.test_fetch_hardening import send

        def slow(h):
            threading.Event().wait(2)
            send(self.page())(h)
        site = self.site({
            "/a": send(self.page(
                "onload = function () { setTimeout(function () {"
                " location.replace('/slow'); }, 300); };")),
            "/slow": slow})
        self.addCleanup(site.stop)
        r = F.fetch(site.base + "/a", timeout_ms=10_000)
        self.assertEqual(r.mode, "rendered", r.fallback_reason)
        self.assertTrue(r.final_url.endswith("/slow"), r.final_url)

    def test_a_worker_registered_past_playwrights_block(self):
        """R5E-5: registered through the prototype, it answers nothing: the
        page it goes to is the server's."""
        from tests.test_fetch_hardening import send
        sw = (b"self.addEventListener('install', e => self.skipWaiting());"
              b" self.addEventListener('activate', e => e.waitUntil("
              b"clients.claim())); self.addEventListener('fetch', e => {"
              b" if (new URL(e.request.url).pathname === '/next')"
              b" e.respondWith(new Response('<!doctype html><title>t</title>"
              b"<h1>forged</h1>', {status: 200, headers: {'Content-Type':"
              b" 'text/html'}})); });")
        site = self.site({
            "/sw": send(self.page(
                "ServiceWorkerContainer.prototype.register.call("
                "navigator.serviceWorker, '/sw.js').then(function () {"
                " return navigator.serviceWorker.ready; }).then(function () {"
                " location.replace('/next'); }).catch(function () {});")),
            "/sw.js": send(sw, ctype="text/javascript"),
            "/next": send(self.page("", "<p>from the server</p>"))})
        self.addCleanup(site.stop)
        r = F.fetch(site.base + "/sw", timeout_ms=10_000)
        self.assertEqual(r.mode, "rendered", r.fallback_reason)
        self.assertNotIn("forged", r.html)
        if r.navigated:
            self.assertIn("from the server", r.html)

    def test_a_server_page_after_a_document_a_script_made(self):
        """R5E-12: a javascript: URL's document that goes on at once to a
        page a server sent with 200: the chain settles on that page, which
        is read, not refused as one a script made. (Where the page itself
        goes on 50 ms after making it, as in the reviewer's case, Chromium
        141 drops the page's timer with the page, and stays on the made
        document: refused, as R5C-2's are.)"""
        from tests.test_fetch_hardening import send
        # The page's script holds a javascript: URL in a string, and its
        # code is a string holding the document it makes.
        made = ("<!doctype html><title>m</title><script>setTimeout("
                "function () { location.replace(\\\\'/ok\\\\'); }, 200)"
                "<\\\\/script><p>made</p>")
        site = self.site({
            "/js": send(self.page(
                "onload = function () { setTimeout(function () { "
                f"location.href = \"javascript:'{made}'\"; }}, 200); }};")),
            "/ok": send(self.page("", "<p>the server's</p>"))})
        self.addCleanup(site.stop)
        r = F.fetch(site.base + "/js", timeout_ms=10_000)
        self.assertEqual(r.mode, "rendered", r.fallback_reason)
        self.assertTrue(r.final_url.endswith("/ok"), r.final_url)
        self.assertIn("the server's", r.html)


class TestPendingWatch(unittest.TestCase):
    """R5E-6, without a browser: what is pending, when the watch speaks,
    and how the record words it."""

    def docs(self):
        d = object.__new__(F._Documents)
        d.committed, d.urls, d.responses, d.worker = ["L1"], {}, {}, set()
        d.stopped, d.replaced, d.script_made = True, 0, False
        d.pending, d._cleared, d._main = None, False, "M"
        return d

    def test_what_is_pending(self):
        d = self.docs()
        d._starting({"frameId": "M", "navigationType": "sameDocument",
                     "url": "http://x/#a"})
        self.assertIsNone(d.pending)
        d._starting({"frameId": "other", "navigationType":
                     "differentDocument", "url": "http://x/frame"})
        self.assertIsNone(d.pending)
        d._starting({"frameId": "M", "navigationType": "differentDocument",
                     "url": "http://x/a"})
        since = d.pending[0]
        d._starting({"frameId": "M", "navigationType": "differentDocument",
                     "url": "http://x/b", "loaderId": "N2"})
        self.assertEqual(d.pending, (since, "http://x/b", "N2"))
        d._loading({"frameId": "M"}, True)          # a 204, a download
        self.assertIsNone(d.pending)
        # While the document before it still loads, no stop comes: its
        # 204, or its request failing (as one that becomes a download's
        # does), ends it (R5H-2); no download of the page's own does
        # (R5J-2): there is no handler for one.
        self.assertFalse(hasattr(d, "_download"))
        for end in (lambda: d._response({"type": "Document", "loaderId":
                                          "N3", "response": {"status": 204,
                                                             "headers": {}}}),
                    lambda: d._failed({"requestId": "N3"})):
            d._starting({"frameId": "M", "navigationType":
                         "differentDocument", "url": "http://x/c",
                         "loaderId": "N3"})
            end()
            self.assertIsNone(d.pending)
        # Another request's failure ends nothing.
        d._starting({"frameId": "M", "navigationType": "differentDocument",
                     "url": "http://x/c", "loaderId": "N4"})
        d._failed({"requestId": "img-1"})
        self.assertIsNotNone(d.pending)
        d.pending = None
        d._starting({"frameId": "M", "navigationType": "reload",
                     "url": "http://x/b"})
        d._navigated({"frame": {"id": "M", "loaderId": "L2",
                                "url": "http://x/b"}})
        self.assertIsNone(d.pending)

    def watch(self, docs, timeout_s, deadline_at=None, wait=3.0):
        import threading
        got = []
        done = threading.Event()
        t = threading.Thread(target=F._watch_pending, args=(
            docs, done, timeout_s, deadline_at, (), got.append), daemon=True)
        t.start()
        t.join(wait)
        done.set()
        t.join(2)
        return got

    def test_when_the_watch_speaks(self):
        from types import SimpleNamespace
        now = time.monotonic()
        docs = SimpleNamespace(committed=["L1"], pending=(
            now - 10, "http://x.example/never?t=SECRETQ"))
        got = self.watch(docs, 1.0)
        self.assertEqual(len(got), 1)
        self.assertIsInstance(got[0], F.FetchError)
        self.assertEqual(str(got[0]), F.WENT_ELSEWHERE + F.NOT_ARRIVED
                         + F.WENT_TO + "http://x.example/never?t=REDACTED")
        # Before any document committed: page.goto's own timeout.
        docs = SimpleNamespace(committed=[], pending=(now - 10, "http://x/"))
        self.assertEqual(self.watch(docs, 1.0, wait=0.5), [])
        # Near the deadline, whatever the load timeout.
        docs = SimpleNamespace(committed=["L1"], pending=(
            time.monotonic(), "http://x/"))
        self.assertEqual(len(self.watch(docs, 100.0, time.monotonic()
                                        + F.PENDING_MARGIN_S + 0.5)), 1)
        self.assertEqual(self.watch(docs, 100.0, time.monotonic() + 100,
                                    wait=0.5), [])

    def test_the_records_words(self):
        exc = F._ChildError("FetchError", F.WENT_ELSEWHERE + F.NOT_ARRIVED
                            + F.WENT_TO + "http://x.example/never")
        self.assertEqual(F.render_failure(exc), "FetchError: " + F.WENT_ON
                         + "had not arrived when the harness stopped "
                         "waiting for it")


class TestOutputsRound3(unittest.TestCase):
    """R5E-7, R5E-8: nothing a run writes replaces a file the bundle lists
    by its hash."""

    @unittest.skipUnless(hasattr(os, "link"), "no hard links")
    def test_a_hard_link_to_a_snapshot(self):
        """R5E-8: the snapshot is written as a new file, so an output
        hard-linked to the old one leaves it whole."""
        from tests.test_fetch_hardening import _Site, send
        site = _Site({"/ok": send(PAGE.format("<p>x</p>").encode())})
        self.addCleanup(site.stop)
        d = tmpdir(self)
        args = ("--url", site.base + "/ok", "--no-render", "--save-snapshots",
                d / "snaps", "--fail-on", "never")
        code, _out, err = run(*args)
        self.assertEqual(code, 0, err)
        snap = next((d / "snaps").iterdir())
        try:
            os.link(snap, d / "report.json")
        except OSError:
            self.skipTest("this file system refuses hard links")
        code, _out, err = run(*args, "--json", d / "report.json")
        self.assertEqual(code, 0, err)
        report = json.loads((d / "report.json").read_text())
        self.assertEqual(hashlib.sha256(snap.read_bytes()).hexdigest(),
                         report["pages"][0]["fetch"]["snapshot_sha256"])

    def test_fresh_files_never_write_through_a_link(self):
        """R5E-8, R5H-5, R5H-8: a snapshot is a new regular file; a link,
        a pipe or a device is refused, not written through nor replaced; a
        regular file's permissions are kept; nothing temporary is left."""
        d = tmpdir(self)
        (d / "kept.txt").write_text("kept")
        if hasattr(os, "symlink"):
            os.symlink(d / "kept.txt", d / "out.html")
            self.assertIn("not a regular file",
                          cli._write_fresh(str(d / "out.html"), b"new"))
            self.assertEqual((d / "kept.txt").read_text(), "kept")
            self.assertTrue(os.path.islink(d / "out.html"))
        if hasattr(os, "mkfifo"):
            os.mkfifo(d / "pipe.html")
            self.assertIn("not a regular file",
                          cli._write_fresh(str(d / "pipe.html"), b"new"))
        (d / "snap.html").write_text("old")
        if os.name != "nt":
            os.chmod(d / "snap.html", 0o600)
        self.assertIsNone(cli._write_fresh(str(d / "snap.html"), b"new"))
        self.assertEqual((d / "snap.html").read_bytes(), b"new")
        if os.name != "nt":
            self.assertEqual(stat.S_IMODE(os.stat(d / "snap.html").st_mode),
                             0o600)
        with mock.patch.object(os, "replace", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                cli._write_fresh(str(d / "snap.html"), b"newer")
        self.assertEqual((d / "snap.html").read_bytes(), b"new")
        self.assertEqual([p.name for p in d.iterdir()
                          if p.name.startswith(".bellbriar-")], [])

    @unittest.skipUnless(HAVE_BROWSER, _WHY)
    def test_an_output_over_a_served_file(self):
        """R5E-7, and a snapshot over a page the run evaluates."""
        d = tmpdir(self)
        site = d / "site"
        site.mkdir()
        (site / "index.html").write_text(PAGE.format(
            '<p>x</p><script src="app.js"></script>'))
        (site / "app.js").write_text("document.title = 'T';")
        code, _out, err = run("--render", site, "--json", site / "app.js",
                              "--fail-on", "never")
        self.assertEqual(code, 2, err)
        self.assertIn("names a file the build server sent the browser", err)
        self.assertEqual((site / "app.js").read_text(),
                         "document.title = 'T';")

    def test_a_snapshot_over_a_file_the_run_read(self):
        """R5E-7, R5E-8: refused before anything is written."""
        from types import SimpleNamespace
        d = tmpdir(self)
        (d / "001-site-index.html").write_text("evidence")
        args = SimpleNamespace(save_snapshot=None, save_snapshots=str(d))
        pages = [SimpleNamespace(path="site/index.html")]
        targets = cli._snapshot_targets(args, pages, [object()])
        self.assertEqual([t for t, _ in targets],
                         [str(d / "001-site-index.html")])
        with self.assertRaises(ValueError) as cm:
            cli._check_snapshot_targets(args, pages, [object()], {
                cli._file_identity(d / "001-site-index.html"): "x"})
        self.assertIn("a snapshot would be written over", str(cm.exception))
        cli._check_snapshot_targets(args, pages, [None], {
            cli._file_identity(d / "001-site-index.html"): "x"})


class TestNamesRound3(unittest.TestCase):
    """R5E-11, R5F-1."""

    def test_deep_names_end_distinct(self):
        """R5E-11: naming gave up after 64 rounds."""
        parts = [f"d{i}" for i in range(66)]
        pairs = [(Path("/r1", *parts, "a.html"), "a.html"),
                 (Path("/r2", *parts, "a.html"), "a.html")]
        got = [n for _, n in cli._distinct(pairs)]
        self.assertEqual(len(set(got)), 2, got)

    def test_any_first_part_outside_ascii(self):
        """R5F-1: no list of the characters that look like a colon or a
        letter is whole: "./" goes before a first part holding any
        character outside ASCII, or a colon."""
        for name in ("https\ua4fd/a.html", "https\u0589/a.html",
                     "https\u02f8/a.html", "https\u205a/a.html",
                     "https\u05c3/a.html", "https\u0703/a.html",
                     "https\ufe30/a.html", "https\u0903/a.html",
                     "https\u16ec/a.html", "https\u1803/a.html",
                     "caf\u00e9/a.html", "C:/a.html"):
            with self.subTest(name=name):
                self.assertTrue(B.recorded_path(name).startswith("./"))
        for name in ("dir/https\u0589/a.html", "a.html", "site/index.html"):
            with self.subTest(name=name):
                self.assertFalse(B.recorded_path(name).startswith("./"))


class TestGuardRound3(unittest.TestCase):
    """R5E-13: a key file with blank lines between its mark and its key,
    which the harness reads as one."""

    def test_blank_lines(self):
        import repo_guard
        key = "ab" * 32
        for text in (B.PRIVATE_KEY_MARK + "\n\n" + key + "\n",
                     B.PRIVATE_KEY_MARK + " \r\n \r\n\t" + key + " \r\n"):
            with self.subTest(text=repr(text[-90:])):
                self.assertEqual(B.parse_key_text(text), ("private", key))
                self.assertIsNotNone(repo_guard._KEYGEN_PRIVATE.search(text))
        self.assertIsNone(repo_guard._KEYGEN_PRIVATE.search(
            B.key_file_text(key, False)))


@NEEDS_CRYPTO
class TestEvidenceRound3(unittest.TestCase):
    """R5F-3, R5F-5, R5F-6, R5F-7, R5F-8, R5F-9."""

    def test_the_private_half_of_an_edited_bundle(self):
        """R5F-3: the signature over the statement decides, not the whole
        bundle."""
        priv, _pub, _kid = B.generate_keypair()
        bundle = B.sign_bundle_local(dict(BODY), priv)
        bundle["coverage_note"] = "edited after signing"
        d = tmpdir(self)
        (d / "b.json").write_text(json.dumps(bundle))
        (d / "k.key").write_text(B.key_file_text(priv, True))
        code, out, _err = evidence("verify", d / "b.json", "--public-key",
                                   priv)
        self.assertEqual(code, 2, out)
        self.assertIn("PRIVATE half", out)
        self.assertTrue(B.statement_signed_by(bundle["signature"],
                                              B.ed25519.Ed25519PrivateKey
                                              .from_private_bytes(
                                                  bytes.fromhex(priv))
                                              .public_key().public_bytes_raw()
                                              .hex()))
        self.assertFalse(B.statement_signed_by({}, _pub))

    @unittest.skipUnless(hasattr(os, "symlink") and hasattr(os, "link"),
                         "no links")
    def test_a_pre_1_0_public_key_through_links(self):
        """R5F-5."""
        d = tmpdir(self)
        _priv, pub, _kid = B.generate_keypair()
        (d / "plain").write_text(pub + "\n")
        os.symlink("plain", d / "mid.pub")
        os.symlink("mid.pub", d / "chain.key")
        with self.assertRaises(B.KeyFileError) as cm:
            B.read_private_key_file(str(d / "chain.key"))
        self.assertIn("a link to one", str(cm.exception))
        (d / "old.pub").write_text(pub + "\n")
        try:
            os.link(d / "old.pub", d / "hard.key")
        except OSError:
            self.skipTest("this file system refuses hard links")
        with self.assertRaises(B.KeyFileError) as cm:
            B.read_private_key_file(str(d / "hard.key"))
        self.assertIn("has another name too (a hard link)", str(cm.exception))
        (d / "alone.key").write_text(pub + "\n")
        self.assertEqual(B.read_private_key_file(str(d / "alone.key"))[0],
                         pub)

    def test_an_older_bundle_is_named(self):
        """R5F-6: every refusal to write a bundle says the file already
        there is not this run's."""
        d = tmpdir(self)
        (d / "b.json").write_text("{}")
        rulebook = json.loads((ROOT / "src" / "bellbriar_harness" /
                               "rulebook.json").read_text(encoding="utf-8"))
        del rulebook["rulebook_version"]
        (d / "rb.json").write_text(json.dumps(rulebook))
        code, _out, err = run(FIXTURES / "good.html", "--rulebook",
                              d / "rb.json", "--bundle", d / "b.json",
                              "--fail-on", "never")
        self.assertEqual(code, 2, err)
        self.assertIn(f"The file already at {d / 'b.json'} is not this "
                      "run's.", err)
        with mock.patch.object(B, "MAX_BUNDLE_FILE", 100):
            code, _out, err = run(FIXTURES / "good.html", "--bundle",
                                  d / "b.json", "--fail-on", "never")
        self.assertEqual(code, 2, err)
        self.assertIn("is not this run's", err)
        self.assertEqual((d / "b.json").read_text(), "{}")

    def test_inspect_warns_where_verify_refuses(self):
        """R5F-7."""
        priv, _pub, _kid = B.generate_keypair()
        bundle = B.sign_bundle_local(dict(BODY), priv)
        bundle["signature"]["statement"]["certified"] = "WCAG 2.1 AA"
        d = tmpdir(self)
        for name, b in (("cert", bundle), ("empty", dict(BODY, signature={}))):
            with self.subTest(name=name):
                (d / "i.json").write_text(json.dumps(b))
                out = evidence("inspect", d / "i.json")[1]
                self.assertTrue(out.startswith("WARNING     malformed "
                                               "bundle"), out[:200])

    def test_what_evidence_md_says_of_names(self):
        """R5F-8, R5F-1."""
        text = (ROOT / "docs" / "EVIDENCE.md").read_text(encoding="utf-8")
        self.assertIn("a `%` itself\n`%25`", text)
        self.assertIn("any character outside ASCII", text)

    def test_the_user_name_vector_tests_the_page_record(self):
        """R5F-9: the run's own record names a clean URL, so the page's
        record is what is refused."""
        vectors = json.loads(VECTORS.read_text(encoding="utf-8"))
        case = next(c for c in vectors["page_records"]
                    if c.get("description")
                    == "a page record whose final_url has a user name")
        self.assertEqual(case["bundle"]["fetch"]["final_url"],
                         "https://www.example.com/a")
        with self.assertRaises(B.MalformedBundle) as cm:
            B.check_body(case["bundle"])
            B.bundle_bound_values(case["bundle"])
        self.assertIn("pages[0].fetch.final_url", str(cm.exception))


class TestRulesRound3(unittest.TestCase):
    """R5G: rules whose verdicts or words the review found wrong."""

    found = staticmethod(TestRulesRound2.found)
    page = TestRulesRound2.page

    def names(self, html, *ids):
        from bellbriar_harness.accname import static_accname
        from bellbriar_harness.checks_static import PageContext
        from bellbriar_harness.model import CURRENT_PAGE
        ctx = PageContext.parse(html, path="t.html")
        token = CURRENT_PAGE.set(ctx)
        try:
            return {i: static_accname(ctx.soup.find(id=i), ctx.soup, ctx.ids)
                    for i in ids}
        finally:
            CURRENT_PAGE.reset(token)

    def test_aria_hidden_on_the_page_in_a_rendered_run(self):
        """R5G-1: axe-core takes such a page as hidden: none of its other
        rules' results are read (not evaluated), and <html> is reported
        too, at moderate impact."""
        from bellbriar_harness import checks_rendered as CR
        from tests.test_rendered_rules import P, attr, findings, mark, rerun
        from tests.test_review_round_q import ALL_AXE
        from tests.test_rendered_rules import run_record
        record = attr(P + "-axe-run", run_record(
            ["aria-hidden-body", "list"],
            sorted(set(ALL_AXE) - {"aria-hidden-body", "list"})))
        body = ('<main><h1>T</h1><ul><div>loose</div></ul><button></button>'
                '</main>')
        axe_body = attr(P + "-axe", mark(("aria-hidden-body", "fail",
                                          "blocker", "Ensure aria-hidden is "
                                          "not on the body")))
        for root, body_attrs, where in (
                ("", ' aria-hidden="true"' + axe_body, "body"),
                (' aria-hidden="true"', "", "html")):
            with self.subTest(where=where):
                html = (f'<!doctype html><html lang="en"{record}{root}><head>'
                        f'<title>T</title></head><body{body_attrs}>{body}'
                        '</body></html>')
                page = rerun(html)
                got = findings(page, "bb-aria-hidden-body")
                self.assertEqual([(f.verdict, f.impact) for f in got],
                                 [(NEEDS_REVIEW, "moderate")])
                self.assertIn(f"on the page's <{where}>", got[0].message)
                self.assertEqual([r for r in page.results
                                  if r.rule_id == "bb-list"], [])
                self.assertEqual(page.axe_unread, CR.ROOT_HIDDEN_NOTE)
                # The harness's own rules read the page as browsers expose
                # it.
                self.assertEqual(findings(page, "bb-button-name")[0].verdict,
                                 FAIL)
        from types import SimpleNamespace
        fr = SimpleNamespace(fetch_block=lambda: {"notes": ["n"]})
        self.assertEqual(cli._capture_record(SimpleNamespace(
            axe_unread="why"), fr)["notes"], ["n", "why"])
        self.assertEqual(cli._capture_record(SimpleNamespace(
            axe_unread=""), fr)["notes"], ["n"])
        rule = {r["id"]: r for r in RB["rules"]}["bb-aria-hidden-focus"]
        self.assertNotIn("(bb-aria-hidden-body reports it)", rule["notes"])

    def test_a_best_practice_is_no_blocker(self):
        """R5G-10."""
        from tests.test_rendered_rules import P, attr, findings, mark, rerun
        from tests.test_review_round_q import axe_page
        html = axe_page('<div role="checkbox"' + attr(P + "-axe", mark((
            "aria-required-attr", "fail", "blocker", "Required ARIA "
            "attributes must be provided"))) + '>x</div>',
            ["aria-required-attr"])
        got = findings(rerun(html), "bb-aria-required-attr")
        self.assertEqual([(f.verdict, f.impact) for f in got],
                         [(NEEDS_REVIEW, "moderate")])

    def test_a_label_names_its_labeled_control_only(self):
        """R5G-2: as HTML makes a label's labeled control, and Chromium 141
        names it (each case checked there)."""
        html = self.page(
            '<label for="a1" aria-hidden="true">X</label><input id="a1">'
            '<label for="a2" hidden>X</label><input id="a2">'
            '<label for="a3" class="gone">X</label><input id="a3">'
            '<label for="a4" class="ghost">X</label><input id="a4">'
            '<div class="gone"><label for="a6">Menu</label><input id="a6">'
            '</div>'
            '<label>Wrap <input id="a7"><button id="b7">B</button></label>'
            '<label>Wrap2 <button id="b8"><svg width="16" height="16">'
            '</svg></button><input id="a8"></label>'
            '<label for="a9">For <button id="b9"><svg width="16" '
            'height="16"></svg></button></label><input id="a9">'
            '<label for="a12">First</label><label for="a12">Second</label>'
            '<input id="a12">'
            '<label for="p14" hidden>Upload</label><progress id="p14" '
            'value="5" max="10"></progress>'
            '<label for="">EmptyFor <input id="a15"></label>',
            head="<style>.gone{display:none}.ghost{visibility:hidden}</style>")
        self.assertEqual(self.names(html, "a1", "a2", "a3", "a4", "a6", "a7",
                                    "b7", "b8", "a8", "a9", "b9", "a12",
                                    "p14", "a15"),
                         {"a1": "", "a2": "", "a3": "", "a4": "",
                          "a6": "Menu", "a7": "Wrap B", "b7": "B",
                          "b8": "Wrap2", "a8": "", "a9": "For", "b9": "",
                          "a12": "First Second", "p14": "", "a15": ""})
        self.assertEqual(self.found(self.page(
            '<main><h1>x</h1><form><label>Search <input type="search"> '
            '<button type="submit"><svg width="16" height="16"><path '
            'd="M0 0h16v16z"/></svg></button></label></form></main>'),
            "bb-button-name"), (True, [(FAIL, "blocker")]))

    def test_a_toggle_the_page_does_not_show(self):
        """R5G-3: SCR28 counts only a toggle the page displays."""
        text = "<div><p>" + "Lots of content here. " * 20 + "</p></div>"
        links = ('<li><a href="/a">A</a></li><li><a href="/b">B</a></li>'
                 '<li><a href="/c">C</a></li>')
        html = self.page('<header><button class="menu-toggle" '
                         'aria-expanded="true" aria-controls="menu">Menu'
                         f'</button><nav><ul id="menu">{links}</ul></nav>'
                         f'</header>{text}',
                         head="<style>.menu-toggle{display:none}</style>")
        self.assertEqual(self.found(html, "bb-skip-link"),
                         (True, [(FAIL, "serious")]))
        shown = html.replace("<style>.menu-toggle{display:none}</style>", "")
        self.assertEqual(self.found(shown, "bb-skip-link"),
                         (True, [(NEEDS_REVIEW, "moderate")]))
        # A rendered capture that recorded the toggle hidden.
        from tests.test_rendered_rules import P, rerun
        from bellbriar_harness.model import hidden_attr
        snap = shown.replace("<html", f'<html {hidden_attr(P)}="recorded"', 1
                             ).replace('<button class="menu-toggle"',
                                       f'<button {hidden_attr(P)}="display" '
                                       'class="menu-toggle"')
        got = [(f.verdict, f.impact) for r in rerun(snap).results
               if r.rule_id == "bb-skip-link" for f in r.findings]
        self.assertEqual(got, [(FAIL, "serious")])

    def test_a_presentational_image_names_nothing(self):
        """R5G-4: Chromium 141 names these links and button ''."""
        main = "<main><h1>x</h1>{}</main>"
        self.assertEqual(self.found(self.page(main.format(
            '<a href="/x"><img src="a.png" alt="IMG_1234.jpg" '
            'role="presentation"></a>')), "bb-link-name"),
            (True, [(FAIL, "blocker")]))
        self.assertEqual(self.found(self.page(main.format(
            '<button type="button"><img src="x.png" alt="Close" role="none">'
            '</button>')), "bb-button-name"), (True, [(FAIL, "blocker")]))
        # Ignored where it can take focus or carries a global ARIA
        # attribute: then it is an image, and named.
        self.assertEqual(self.names(self.page(main.format(
            '<a id="l4" href="/"><img src="l.png" alt="Acme" '
            'role="presentation" aria-label="Home"></a><a id="l5" href="/">'
            '<img src="l.png" alt="Acme" role="presentation" tabindex="-1">'
            '</a>')), "l4", "l5"), {"l4": "Home", "l5": "Acme"})

    def test_what_the_docs_say_of_vendor_markup(self):
        """R5G-5: page-level findings count vendor blocks, and are
        scored."""
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("never lower it", readme)
        self.assertIn("so vendor markup can\nlower the rate too", readme)
        self.assertIn("a finding about the page as a whole counts",
                      B.ATTESTATION)

    def test_a_show_rule_in_an_at_rule(self):
        """R5G-6: Chromium 141 names this link "Cart"; a rule under a
        condition only shows, and a print rule is not read."""
        main = '<main><h1>x</h1><a href="/cart"><span class="lbl">Cart' \
               '</span></a></main>'
        # (A show in a cascade layer loses to the unlayered hide: R5I-2.)
        for at in ("@media screen", "@media all", "@media", "@supports "
                   "(display:grid)", "@media (min-width: 1px)"):
            with self.subTest(at=at):
                head = f"<style>.lbl{{display:none}}{at}{{.lbl{{display:" \
                       "inline}}</style>"
                self.assertEqual(self.found(self.page(main, head=head),
                                            "bb-link-name"), (True, []))
        # (An @supports Chromium settles is no condition: R5K-4.)
        for head in ("<style>@supports (position:sticky){.lbl{display:none}}"
                     "</style>",
                     "<style>@media (min-width:600px){.lbl{display:none}}"
                     "</style>"):
            with self.subTest(head=head):
                self.assertEqual(self.found(self.page(main, head=head),
                                            "bb-link-name"), (True, []))
        for head in ("<style>.lbl{display:none}@media print{.lbl{display:"
                     "inline}}</style>",
                     "<style>@media screen{.lbl{display:none}}</style>",
                     "<style>@supports (display:grid){.lbl{display:none}}"
                     "</style>"):
            with self.subTest(head=head):
                self.assertEqual(self.found(self.page(main, head=head),
                                            "bb-link-name"),
                                 (True, [(FAIL, "blocker")]))

    def test_an_object_by_its_data(self):
        """R5G-7."""
        from tests.test_rendered_rules import (P, attr, findings, mark,
                                               rerun, run_record, snapshot)
        fail = attr(P + "-axe", mark(("object-alt", "fail", "serious",
                                      "Element has no text alternative")))
        for data, verdict in (
                ("data:image/svg+xml,%3Csvg%3E%3C/svg%3E", FAIL),
                ("data:,hello", NEEDS_REVIEW),
                ("/clip.avi", FAIL), ("/song.mid", FAIL), ("/p.jxl", FAIL),
                ("/doc.pdf", NEEDS_REVIEW)):
            with self.subTest(data=data):
                page = rerun(snapshot(f'<object data="{data}"{fail}></object>',
                                      root=attr(P + "-axe-run",
                                                run_record(["object-alt"]))))
                self.assertEqual([f.verdict for f in findings(
                    page, "bb-object-alt")], [verdict])

    def test_ids_html_and_drawings_reference(self):
        """R5G-8."""
        main = "<main><h1>x</h1>{}</main>"
        for body, want, words in (
                ('<button popovertarget="pop">Open</button><div id="pop" '
                 'popover>A</div><div id="pop" popover>B</div>',
                 (NEEDS_REVIEW, "moderate"), "popovertarget"),
                ('<input list="dl" aria-label="x"><datalist id="dl"></datalist>'
                 '<datalist id="dl"></datalist>', (NEEDS_REVIEW, "moderate"),
                 "an input's list"),
                ('<svg><defs><linearGradient id="g"></linearGradient></defs>'
                 '<rect fill="url(#g)"/></svg><svg><defs><linearGradient '
                 'id="g"></linearGradient></defs></svg>',
                 (NEEDS_REVIEW, MINOR), "a drawing's reference"),
                ('<div id="u">a</div><div id="u">b</div>',
                 (NEEDS_REVIEW, MINOR), "no label, ARIA, headers")):
            with self.subTest(body=body[:40]):
                page = run_page(self.page(main.format(body)), "t.html", RB)
                got = [f for r in page.results if r.rule_id ==
                       "bb-duplicate-id" for f in r.findings]
                self.assertEqual([(f.verdict, f.impact) for f in got],
                                 [want])
                self.assertIn(words, got[0].message)
                self.assertNotIn("(unreferenced)", got[0].message)

    def test_a_tables_own_header_cells(self):
        """R5G-9: a header role inside a cell, or a nested table's header,
        is none of this table's."""
        rows = "".join(f"<tr><td>{i}</td><td>{i}</td><td>{i}</td></tr>"
                       for i in range(2))
        span = ('<tr><td><span role="columnheader">Name</span></td><td>B'
                '</td><td>C</td></tr>')
        self.assertEqual(self.found(self.page(
            f"<main><h1>x</h1><table>{span}{rows}</table></main>"),
            "bb-table-headers"), (True, [(FAIL, "moderate")]))
        nested = ('<tr><td><table><tr><th>N</th></tr></table></td><td>B</td>'
                  '<td>C</td></tr>')
        got = self.found(self.page(
            f"<main><h1>x</h1><table>{nested}{rows}</table></main>"),
            "bb-table-headers")
        self.assertEqual(got[1].count((FAIL, "moderate")), 1, got)

    def test_lint_words_and_minified_files(self):
        """R5G-11, R5G-12."""
        src = ('export const A = () => <video src="v.mp4" autoPlay muted '
               'playsInline />;\n')
        got = [f.message for f in L.lint_text(src, "a.jsx")
               if f.rule_id == "bl-autoplay-media"]
        self.assertEqual(len(got), 1, got)
        self.assertIn("1.4.2 is met", got[0])
        self.assertNotIn("is required (2.2.2)", got[0])
        css = (".a{background:url(data:image/svg+xml," + "%3Csvg%20" * 1200
               + ")}\n")
        self.assertFalse(L._minified(Path("x.css"), css))
        self.assertTrue(L._minified(Path("x.min.css"), ".a{color:red}"))



# ---------------------------------------------------------------------------
# Round 4: the reviews of round 3 (R5H, R5I)
# ---------------------------------------------------------------------------

def _echo_site(test, body_for):
    """A loopback site whose page /p is body_for(token) for the token in
    its query."""
    from tests.test_fetch_hardening import _Site

    def echo(h):
        token = h.path.split("token=", 1)[-1] if "token=" in h.path else ""
        body = body_for(token).encode()
        h.send_response(200)
        h.send_header("Content-Type", "text/html")
        h.send_header("Content-Length", str(len(body)))
        h.end_headers()
        h.wfile.write(body)
    site = _Site({"/p": echo})
    test.addCleanup(site.stop)
    return site


class TestSecretsRound4(unittest.TestCase):
    """R5H-1, R5H-3, R5H-6, R5I-9."""

    TOKEN = "TOKENabc1234567890xyz"

    def test_a_token_past_the_long_cut(self):
        """R5H-1: white space runs are one character before the markup is
        cut, so a token cut there never reaches the snippet."""
        site = _echo_site(self, lambda t: PAGE.format(
            '<img src="/i.png" data-x="' + " " * 19977 + t + '">'))
        d = tmpdir(self)
        code, out, err = run("--url", f"{site.base}/p?token={self.TOKEN}",
                             "--no-render", "--json", d / "r.json",
                             "--bundle", d / "b.json", "--fail-on", "never")
        self.assertEqual(code, 0, err)
        for name in ("r.json", "b.json"):
            text = (d / name).read_text()
            self.assertNotIn(self.TOKEN[:6], text, name)

    def test_where_it_went_is_cut_after_it_is_scrubbed(self):
        """R5H-3."""
        from types import SimpleNamespace
        from bellbriar_harness.redact import redact_text
        where = ("http://127.0.0.1:1/hold/" + "p" * 262 + self.TOKEN
                 + "/next")
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            cli._say_detail(SimpleNamespace(detail="", where=where), "",
                            lambda text: redact_text(text, {self.TOKEN}, ()))
        self.assertNotIn(self.TOKEN[:6], err.getvalue())
        self.assertLessEqual(len(F._at(where)), len(F.WENT_TO)
                             + F.WENT_TO_MAX)

    def test_a_password_that_is_a_word(self):
        """R5H-6: a snippet, locator or message that holds it is withheld
        whole, never left with a word around it, and the console says
        so. R5J-4: one the harness's own words hold is refused before
        the run: which of those known words were withheld would give it
        away."""
        site = _echo_site(self, lambda t: PAGE.format(
            '<form><input name="q" type="text" class="Kq7zWord"><button '
            'data-testid="Kq7zWordid"></button></form>'))
        d = tmpdir(self)
        for password in ("name", "test", "main"):
            with self.subTest(password=password):
                (d / "pw").write_text(password)
                code, _out, err = run(
                    "--url", f"{site.base}/p", "--no-render", "--http-user",
                    "u", "--http-password-file", d / "pw", "--json",
                    d / "r.json", "--bundle", d / "b.json", "--fail-on",
                    "never")
                self.assertEqual(code, 2, err)
                self.assertIn("too common", err)
                self.assertFalse((d / "b.json").exists())
                self.assertFalse((d / "r.json").exists())
        (d / "pw").write_text("Kq7zWord")         # the page's word only
        code, _out, err = run(
            "--url", f"{site.base}/p", "--no-render", "--http-user", "u",
            "--http-password-file", d / "pw", "--json", d / "r.json",
            "--bundle", d / "b.json", "--fail-on", "never")
        self.assertEqual(code, 0, err)
        text = (d / "r.json").read_text() + (d / "b.json").read_text()
        self.assertNotIn("Kq7z", text)
        for leak in ("REDACTEDid", '=\\"REDACTED', "REDACTED > "):
            self.assertNotIn(leak, text)
        self.assertIn('"snippet": "REDACTED"', text)
        self.assertIn("quoted the --http-user password", err)
        self.assertIn("long random password", err)

    def test_a_password_with_both_quotes(self):
        """R5I-9: as an attribute holding both is serialized."""
        from bellbriar_harness import redact as R
        from bellbriar_harness.checks_static import PageContext, _f
        from bellbriar_harness.model import CURRENT_PAGE
        token = R.set_run_secrets(passwords=['Pa"ss\'wd'])
        ctx = PageContext.parse(PAGE.format(
            '<button data-x="Pa&quot;ss&#x27;wd"></button>'), path="t.html")
        page_token = CURRENT_PAGE.set(ctx)
        try:
            f = _f("bb-button-name", FAIL, "blocker", "m",
                   ctx.soup.find("button"))
        finally:
            CURRENT_PAGE.reset(page_token)
            R.reset_run_secrets(token)
        self.assertNotIn("ss'wd", f.snippet)


class TestRunEndsRound4(unittest.TestCase):
    """R5H-4, R5H-5, R5H-7."""

    def test_every_exit_2_names_an_older_bundle(self):
        d = tmpdir(self)
        (d / "b.json").write_text('{"old": "bundle"}')
        code, _out, err = run(d / "missing", "--bundle", d / "b.json")
        self.assertEqual(code, 2, err)
        self.assertIn(f"the file already at {d / 'b.json'} is not this "
                      "run's", err)
        (d / "empty").mkdir()
        code, _out, err = run(d / "empty", "--bundle", d / "b.json")
        self.assertEqual(code, 2, err)
        self.assertEqual(err.count("is not this run's"), 1, err)
        self.assertEqual((d / "b.json").read_text(), '{"old": "bundle"}')

    @unittest.skipUnless(hasattr(os, "mkfifo"), "no FIFOs")
    def test_a_snapshot_over_a_pipe(self):
        d = tmpdir(self)
        os.mkfifo(d / "s.html")
        code, _out, err = run("--url", "http://127.0.0.1:9/p", "--no-render",
                              "--save-snapshot", d / "s.html")
        self.assertEqual(code, 2, err)
        self.assertIn("it is not a regular file", err)

    @NEEDS_CRYPTO
    def test_inspect_names_a_key_id_that_is_no_string(self):
        d = tmpdir(self)
        (d / "b.json").write_text(json.dumps(dict(BODY, signature={
            "alg": "Ed25519", "context": B.STATEMENT_FORMAT, "key_id": 5,
            "signature_b64": "x", "statement": {}})))
        out = evidence("inspect", d / "b.json")[1]
        self.assertIn("signature block: a key_id that is not a string", out)


@unittest.skipUnless(HAVE_BROWSER, _WHY)
class TestNavigationRound4(unittest.TestCase):
    """R5H-2: a 204 or a download a head script goes to while the page
    still loads is not a navigation that never arrives."""

    site = staticmethod(R4.TestReviewOfR4Round4.site)

    def test_a_204_and_a_download_before_the_load(self):
        from tests.test_fetch_hardening import send
        port = _hold(self)
        img = f'<img src="http://127.0.0.1:{port}/i.png" alt="i">'
        site = self.site({
            "/to204": send(PAGE.format(img).replace(
                "</title>", "</title><script>location.href='/n'</script>")
                .encode()),
            "/todl": send(PAGE.format(img).replace(
                "</title>", "</title><script>location.href='/dl'</script>")
                .encode()),
            "/n": send(b"", status=204),
            "/dl": send(b"x" * 10, ctype="application/octet-stream",
                        headers=(("Content-Disposition",
                                  "attachment; filename=x.bin"),))})
        self.addCleanup(site.stop)
        for path in ("/to204", "/todl"):
            with self.subTest(path=path):
                try:
                    r = F.fetch(site.base + path, timeout_ms=4000)
                    reason = r.fallback_reason or ""
                except F.FetchError as exc:
                    reason = str(exc)
                self.assertNotIn("had not arrived", reason)


class TestLabelsRound4(unittest.TestCase):
    """R5I-1, R5I-4, R5I-13, R5I-14: labels as Chromium 141 names their
    controls (each case checked there)."""

    names = TestRulesRound3.names
    page = TestRulesRound2.page
    found = staticmethod(TestRulesRound2.found)

    def test_a_label_around_a_shadow_host(self):
        """R5I-1: the label's own tree, in DOM order, not the slots'."""
        html = self.page(
            '<main><h1>x</h1><label>Search <search-box><template '
            'shadowrootmode="open"><button type="button">Clear</button>'
            '<slot></slot></template><input id="s" type="search">'
            '</search-box></label></main>')
        self.assertEqual(self.found(html, "bb-control-label"), (True, []))
        rev = self.page(
            '<main><h1>x</h1><label>Name <two-slots><template '
            'shadowrootmode="open"><slot name="b"></slot><slot name="a">'
            '</slot></template><input id="a" slot="a"><input id="b" '
            'slot="b"></two-slots></label></main>')
        got = self.names(rev, "a", "b")
        self.assertEqual(got["b"], "")
        self.assertTrue(got["a"].startswith("Name"), got)

    def test_what_hides_a_label(self):
        """R5I-4."""
        html = self.page(
            '<label for="i8" inert>Inert</label><input id="i8">'
            '<label for="i12" hidden="until-found">UF</label><input id="i12">'
            '<label for="i13" style="content-visibility:hidden">CV</label>'
            '<input id="i13">'
            '<details><summary>S</summary><label for="i14">InDetails</label>'
            '</details><input id="i14">'
            '<div style="visibility:hidden"><label for="i15">VisInh</label>'
            '<input id="i15" style="visibility:visible"></div>'
            '<label style="visibility:hidden">Wrap <input id="i16" '
            'style="visibility:visible"></label>'
            '<label>Outer <label>Inner <input id="i9"></label></label>')
        self.assertEqual(self.names(html, "i8", "i12", "i13", "i14", "i15",
                                    "i16", "i9"),
                         {"i8": "Inert", "i12": "UF", "i13": "CV", "i14": "",
                          "i15": "", "i16": "", "i9": "Outer Inner"})

    def test_form_associated_custom_elements_are_said(self):
        """R5I-14."""
        rule = {r["id"]: r for r in RB["rules"]}["bb-control-label"]
        self.assertIn("form-associated custom element", rule["notes"])


class TestImagesAndDrawingsRound4(unittest.TestCase):
    """R5I-3, R5I-6: presentational images and drawings, and the ARIA
    attributes that make a browser ignore the role, as Chromium 141 has
    them (each case checked there)."""

    names = TestRulesRound3.names
    page = TestRulesRound2.page

    def test_names(self):
        html = self.page(
            '<a id="s1" href="/"><svg role="presentation" width="10" '
            'height="10"><title>Home</title></svg></a>'
            '<a id="s2" href="/"><svg role="presentation" width="40" '
            'height="20"><text x="0" y="15">Home</text></svg></a>'
            '<a id="s3" href="/"><svg role="none" width="10" height="10" '
            'aria-label="Lbl"><title>Home</title></svg></a>'
            '<a id="s4" href="/"><svg width="10" height="10"><image '
            'role="presentation" href="x.png" width="10" height="10"><title>'
            'Img</title></image></svg></a>'
            '<a id="s6" href="/"><img src="x.png" role="presentation" alt="A"'
            ' aria-description="d"></a>'
            '<a id="s7" href="/"><img src="x.png" role="presentation" alt="B"'
            ' aria-grabbed="true"></a>'
            '<a id="g1" href="/"><svg width="10" height="10"><g><title>G'
            '</title><rect width="5" height="5"/></g></svg></a>'
            '<a id="g2" href="/"><svg width="10" height="10"><title>T</title>'
            '</svg></a>'
            '<a id="g4" href="/"><svg width="40" height="20" '
            'role="presentation"><text x="0" y="15">X</text><title>T</title>'
            '</svg></a>'
            '<a id="g5" href="/"><svg width="40" height="20" '
            'role="presentation"><g><title>Gt</title><rect width="5" '
            'height="5"/></g></svg></a>'
            '<a id="g6" href="/"><svg width="40" height="20" '
            'role="presentation"><desc>D</desc><text x="0" y="15">Y</text>'
            '</svg></a>')
        self.assertEqual(
            self.names(html, "s1", "s2", "s3", "s4", "s6", "s7", "g1", "g2",
                       "g4", "g5", "g6"),
            {"s1": "", "s2": "Home", "s3": "Lbl", "s4": "", "s6": "A",
             "s7": "", "g1": "", "g2": "T", "g4": "X", "g5": "Gt",
             "g6": "Y"})


class TestOwnStyleRound4(unittest.TestCase):
    """R5I-2, R5I-5: the page's own <style> read in the cascade's order,
    media as screens match them, strings and nesting as CSS reads them."""

    found = staticmethod(TestRulesRound2.found)
    page = TestRulesRound2.page

    CASES = (
        ("<style>.lbl{display:none}@media tv{.lbl{display:inline}}</style>",
         True),
        ("<style>.lbl{display:none}@media not screen{.lbl{display:inline}}"
         "</style>", True),
        ("<style>.lbl{display:none}@media not print{.lbl{display:inline}}"
         "</style>", False),
        ("<style>.lbl{display:none}@layer base{.lbl{display:inline}}</style>",
         True),
        ("<style>.lbl{display:inline}@layer base{.lbl{display:none}}</style>",
         False),
        ("<style>.lbl{display:none!important}@media (min-width:1px){.lbl{"
         "display:inline}}</style>", True),
        ("<style>.lbl{display:none}@supports not (display:grid){.lbl{"
         "display:inline}}</style>", True),
        ("<style>.lbl{display:none}@supports (display:grid){.lbl{display:"
         "inline}}</style>", False),
        ('<style media="only screen">.lbl{display:none}</style>', True),
        ('<style media="screen, print">.lbl{display:none}</style>', True),
        ('<style media="print">.lbl{display:none}</style>', False),
        ('<style>@media print{.a::before{content:"}"} .lbl{display:none}}'
         '</style>', False),
        ('<style>.a::before{content:"{"}.lbl{display:none}</style>', True),
        ("<style>main{.lbl{display:none}}</style>", True),
        ("<style>main{& .lbl{display:none}}</style>", True),
        ("<style>nav{.lbl{display:none}}</style>", False),
        ("<style>@media not print{.lbl{display:none}}</style>", True),
        ("<style>.lbl{display:none}.lbl{display:inline}</style>", False),
        ('<style>.lbl{display:none!important}</style>', True),
    )

    def test_each_case(self):
        link = '<main><h1>x</h1><a href="/cart"><span class="lbl">Cart' \
               '</span></a></main>'
        for head, fails in self.CASES:
            with self.subTest(head=head):
                self.assertEqual(self.found(self.page(link, head=head),
                                            "bb-link-name"),
                                 (True, [(FAIL, "blocker")] if fails else []))

    def test_a_toggle_made_visible_again(self):
        """R5I-5: the nearest element that sets visibility decides; a show
        under a condition does not count for the toggle."""
        text = "<div><p>" + "Lots of content here. " * 20 + "</p></div>"
        links = ('<li><a href="/a">A</a></li><li><a href="/b">B</a></li>'
                 '<li><a href="/c">C</a></li>')

        def html(style, before="", after=""):
            return self.page(
                f'<header>{before}<button class="menu-toggle" aria-expanded='
                '"false" aria-controls="menu">Menu</button>'
                f'{after}<nav><ul id="menu">{links}</ul></nav></header>{text}',
                head=f"<style>{style}</style>")
        review = (True, [(NEEDS_REVIEW, "moderate")])
        fail = (True, [(FAIL, "serious")])
        for style, wrap, want in (
                (".bar{visibility:hidden}.menu-toggle{visibility:visible}",
                 ('<div class="bar">', "</div>"), review),
                (".bar{visibility:hidden}", ('<div class="bar">', "</div>"),
                 fail),
                (".menu-toggle{display:none}@media (max-width:600px){"
                 ".menu-toggle{display:block}}", ("", ""), fail)):
            with self.subTest(style=style):
                self.assertEqual(self.found(html(style, *wrap),
                                            "bb-skip-link"), want)


class TestRulesRound4(unittest.TestCase):
    """R5I-7, R5I-8, R5I-10, R5I-11, R5I-12."""

    def test_what_axe_core_still_found_on_a_page_hidden_at_its_root(self):
        """R5I-7: a failure stands; a rule that found none is not
        evaluated; axe-core compares the attribute exactly, so "TRUE" hides
        nothing from it."""
        from bellbriar_harness import engine as E
        from tests.test_rendered_rules import P, attr, findings, mark, rerun
        from tests.test_rendered_rules import run_record
        from tests.test_review_round_q import ALL_AXE
        applicable = ["aria-hidden-body", "color-contrast", "list"]
        record = attr(P + "-axe-run", run_record(
            applicable, sorted(set(ALL_AXE) - set(applicable))))
        contrast = attr(P + "-axe", mark(("color-contrast", "fail",
                                          "serious", "Low contrast 1.91")))
        for value, skipped in (("true", True), ("TRUE", False)):
            with self.subTest(value=value):
                html = (f'<!doctype html><html lang="en"{record}><head>'
                        f'<title>T</title></head><body aria-hidden="{value}">'
                        f'<main><h1>T</h1><p{contrast}>pale</p><ul><div>x'
                        '</div></ul></main></body></html>')
                page = rerun(html)
                self.assertEqual([f.verdict for f in findings(
                    page, "bb-contrast-min")], [FAIL])
                self.assertEqual(not any(r.rule_id == "bb-list"
                                         for r in page.results), skipped)
                self.assertEqual(bool(page.axe_unread), skipped)
                self.assertEqual(len(findings(page, "bb-aria-hidden-body")),
                                 1)
                sentence = E.coverage_sentence([page])
                self.assertEqual("aria-hidden=\"true\" on the page's <html> "
                                 "or <body> made axe-core skip" in sentence,
                                 skipped)

    def test_a_vendors_skip_link_is_the_sites_finding(self):
        """R5I-8."""
        from tests.test_rendered_rules import P, rerun
        links = "".join(f'<li {P}="site"><a {P}="site" href="/{i}">{i}</a>'
                        '</li>' for i in range(6))
        html = (f'<!doctype html><html lang="en" {P}="site"><head><title>T'
                f'</title></head><body {P}="site"><a {P}="third-party:'
                'acsbapp.com" href="#nowhere">Skip to content</a><header '
                f'{P}="site"><nav {P}="site"><ul {P}="site">{links}</ul>'
                f'</nav></header><div {P}="site"><p {P}="site">'
                + "Long text. " * 40 + '</p></div></body></html>')
        page = rerun(html)
        result = next(r for r in page.results if r.rule_id == "bb-skip-link")
        self.assertTrue(result.failed, [(f.verdict, f.origin)
                                        for f in result.findings])
        self.assertTrue(all(f.owned for f in result.findings))

    def test_notes_and_references(self):
        """R5I-10, R5I-11."""
        rule = {r["id"]: r for r in RB["rules"]}["bb-heading-structure"]
        self.assertNotIn("serious review", rule["notes"])
        main = "<main><h1>x</h1>{}</main>"
        for body, want in (
                ('<input id="a" aria-label="a"><output for="a">1</output>'
                 '<span id="a">d</span>', (NEEDS_REVIEW, "moderate")),
                ('<svg><path id="p" d="M0 0L9 9"/><text><textPath href="#p">'
                 't</textPath></text></svg><svg><path id="p" d="M0 0"/></svg>',
                 (NEEDS_REVIEW, MINOR))):
            with self.subTest(body=body[:30]):
                page = run_page(TestRulesRound2.page(
                    self, main.format(body)), "t.html", RB)
                got = [f for r in page.results if r.rule_id ==
                       "bb-duplicate-id" for f in r.findings]
                self.assertEqual([(f.verdict, f.impact) for f in got], [want])
                self.assertNotIn("no label, ARIA", got[0].message)
        page = run_page(TestRulesRound2.page(
            self, main.format(
                '<svg><defs><linearGradient id="g"></linearGradient></defs>'
                '<rect class="r"/></svg><svg><linearGradient id="g">'
                '</linearGradient></svg>'),
            head="<style>.r{fill:url(#g)}</style>"), "t.html", RB)
        got = [f.message for r in page.results if r.rule_id ==
               "bb-duplicate-id" for f in r.findings]
        self.assertTrue(got and "a drawing's reference" in got[0], got)


# ---------------------------------------------------------------------------
# Round 5: the reviews of round 4 (R5J, R5K)
# ---------------------------------------------------------------------------

class TestSecretsRound5(unittest.TestCase):
    """R5J-1, R5J-4, R5J-5, R5J-6."""

    TOKEN = "TOKENabc1234567890xyz"

    def test_a_secret_past_a_long_url(self):
        """R5J-1: the secrets are replaced before the cut, which redacting
        the URLs before it would otherwise pull into the snippet."""
        site = _echo_site(self, lambda t: PAGE.format(
            '<img src="/i.png?a=' + "A" * 19953 + f'" width="{t}">'))
        d = tmpdir(self)
        code, _out, err = run("--url", f"{site.base}/p?token={self.TOKEN}",
                              "--no-render", "--json", d / "r.json",
                              "--bundle", d / "b.json", "--fail-on", "never")
        self.assertEqual(code, 0, err)
        for name in ("r.json", "b.json"):
            text = (d / name).read_text()
            self.assertNotIn(self.TOKEN[:6], text, name)
            self.assertIn('width=\\"REDACTED\\"', text, name)

    def test_a_password_past_a_long_url(self):
        """R5J-1: a snippet that holds the password anywhere is withheld."""
        from bellbriar_harness import redact as R
        from bellbriar_harness.checks_static import PageContext, _f
        from bellbriar_harness.model import CURRENT_PAGE
        token = R.set_run_secrets(passwords=["Secr3tPassw0rd"])
        ctx = PageContext.parse(PAGE.format(
            '<img src="/i.png?a=' + "A" * 19960
            + '" width="Secr3tPassw0rd">'), path="t.html")
        page_token = CURRENT_PAGE.set(ctx)
        try:
            f = _f("bb-img-alt", FAIL, "blocker", "m", ctx.soup.find("img"))
            spaced = _f("bb-img-alt", FAIL, "blocker", "m", PageContext.parse(
                PAGE.format('<img src="/i.png" alt="Secr3tPassw0rd">'),
                path="t.html").soup.find("img"))
        finally:
            CURRENT_PAGE.reset(page_token)
            R.reset_run_secrets(token)
        self.assertEqual(f.snippet, R.REDACTED)
        self.assertEqual(spaced.snippet, R.REDACTED)
        token = R.set_run_secrets(passwords=["two  words"])
        try:
            self.assertTrue(R.holds_password("x two\nwords y"))
        finally:
            R.reset_run_secrets(token)

    def test_a_password_the_harness_or_the_url_holds(self):
        """R5J-4: refused before the run: which findings were withheld
        would give it away."""
        self.assertTrue(cli._in_own_words("name"))
        self.assertTrue(cli._in_own_words("accessible"))
        self.assertFalse(cli._in_own_words("x9Tq-7mWp-Lz3K"))
        self.assertFalse(cli._in_own_words("abc"))     # too short to look for
        site = _echo_site(self, lambda t: PAGE.format("<p>x</p>"))
        d = tmpdir(self)
        (d / "pw").write_text("Zebra42q")
        code, _out, err = run(
            "--url", f"{site.base}/p?lang=zebra42Q", "--no-render",
            "--http-user", "u", "--http-password-file", d / "pw",
            "--json", d / "r.json")
        self.assertEqual(code, 2, err)
        self.assertIn("occurs in a URL this run reads", err)
        self.assertNotIn("Zebra42q", err)
        self.assertFalse((d / "r.json").exists())

    def test_withheld_findings_on_one_line_stay_apart(self):
        """R5J-5: the narrow view's finding on another element is kept."""
        from bellbriar_harness.engine import merge_views
        from bellbriar_harness.model import Finding, RuleResult
        from bellbriar_harness.redact import REDACTED, WITHHELD_MESSAGE
        a = Finding("bb-button-name", FAIL, "serious", "m", line=1,
                    snippet=REDACTED, selector=[REDACTED], about="a" * 32)
        b = Finding("bb-button-name", FAIL, "serious", "m", line=1,
                    snippet=REDACTED, selector=[REDACTED], about="b" * 32)
        got = merge_views(RuleResult("bb-button-name", True, [a]),
                          RuleResult("bb-button-name", True, [a, b]))
        self.assertEqual(len(got.findings), 2)
        p = Finding("bb-x", NEEDS_REVIEW, "minor", WITHHELD_MESSAGE)
        q = Finding("bb-x", FAIL, "serious", WITHHELD_MESSAGE)
        got = merge_views(RuleResult("bb-x", True, [p]),
                          RuleResult("bb-x", True, [p, q]))
        self.assertEqual([f.verdict for f in got.findings],
                         [NEEDS_REVIEW, FAIL])

    def test_every_withheld_finding_is_counted(self):
        """R5J-6: an origin withheld, and a message with a note added."""
        from types import SimpleNamespace
        from bellbriar_harness import redact as R
        from bellbriar_harness.engine import NARROW_NOTE
        from bellbriar_harness.model import Finding, RuleResult
        f1 = Finding("bb-skip-link", FAIL, "serious", "m",
                     origin_detail="https://kq7zword.vendor.example")
        f2 = Finding("bb-skip-link", FAIL, "serious",
                     f"{R.WITHHELD_MESSAGE} ({NARROW_NOTE})")
        page = SimpleNamespace(results=[RuleResult("bb-skip-link", True,
                                                   [f1, f2])])
        token = R.set_run_secrets(passwords=["kq7zword"])
        try:
            self.assertEqual(cli._scrub_findings([page], ()), 2)
        finally:
            R.reset_run_secrets(token)
        self.assertEqual(f1.origin_detail, R.REDACTED)


class TestRunEndsRound5(unittest.TestCase):
    """R5J-3, R5J-7."""

    def test_an_argument_argparse_refuses_names_an_older_bundle(self):
        """R5J-3."""
        d = tmpdir(self)
        (d / "b.json").write_text('{"old": "bundle"}')
        for extra in (("--fail-on", "bogus"), ("--no-such-flag",),
                      ("--max-pages", "0")):
            with self.subTest(extra=extra):
                code, _out, err = run(FIXTURES / "good.html", "--bundle",
                                      d / "b.json", *extra)
                self.assertEqual(code, 2, err)
                self.assertEqual(err.count(
                    f"the file already at {d / 'b.json'} is not this "
                    "run's"), 1, err)
        code, _out, err = run(FIXTURES / "good.html",
                              f"--bun={d / 'b.json'}", "--fail-on", "bogus")
        self.assertIn("is not this run's", err)
        self.assertEqual((d / "b.json").read_text(), '{"old": "bundle"}')

    def test_the_note_is_said_once_and_not_of_a_folder(self):
        """R5J-7."""
        d = tmpdir(self)
        code, _out, err = run(FIXTURES / "good.html", "--bundle", d,
                              "--fail-on", "never")
        self.assertEqual(code, 2, err)
        self.assertNotIn("is not this run's", err)
        (d / "b.json").write_text('{"old": "bundle"}')
        real = cli._write

        def failing(path, data):
            return "denied" if str(path) == str(d / "b.json") \
                else real(path, data)
        with mock.patch.object(cli, "_write", failing):
            code, _out, err = run(FIXTURES / "good.html", "--bundle",
                                  d / "b.json", "--fail-on", "never")
        self.assertEqual(code, 2, err)
        self.assertEqual(err.count("not this run's"), 1, err)


@unittest.skipUnless(HAVE_BROWSER, _WHY)
class TestNavigationRound5(unittest.TestCase):
    """R5J-2: a download the page starts while a navigation it began is
    pending ends nothing: the navigation is refused at the load timeout,
    not left to hang to the render deadline."""

    site = staticmethod(R4.TestReviewOfR4Round4.site)

    def test_a_download_while_a_navigation_is_pending(self):
        from tests.test_fetch_hardening import send
        port = _hold(self)
        script = (
            "addEventListener('load', function () { setTimeout(function () {"
            f" location.href = 'http://127.0.0.1:{port}/x';"
            " setTimeout(function () { document.getElementById('d')"
            ".click(); }, 300); }, 300); });")
        site = self.site({
            "/p": send(PAGE.format(
                f'<a id="d" href="/dl" download>d</a><script>{script}'
                '</script>').encode()),
            "/dl": send(b"x" * 10, ctype="application/octet-stream",
                        headers=(("Content-Disposition",
                                  "attachment; filename=x.bin"),))})
        self.addCleanup(site.stop)
        start = time.monotonic()
        with self.assertRaises(F.FetchError) as cm:
            F.fetch(site.base + "/p", timeout_ms=4000)
        self.assertLess(time.monotonic() - start, 40)
        self.assertIn("had not arrived", str(cm.exception))


class TestLabelsRound5(unittest.TestCase):
    """R5K-1, R5K-2, R5K-8: labels as Chromium 141 names their controls
    (each case checked there)."""

    found = staticmethod(TestRulesRound2.found)
    page = TestRulesRound2.page

    def test_a_shown_label_inside_a_hidden_one(self):
        """R5K-1: read on its own."""
        html = self.page(
            '<main><h1>x</h1><label style="visibility:hidden">Outer <label '
            'style="visibility:visible">Inner <input id="i"></label></label>'
            '</main>')
        self.assertEqual(TestRulesRound3.names(self, html, "i"),
                         {"i": "Inner"})

    def test_a_label_around_a_slot(self):
        """R5K-2: its control is in its own tree, not what the slot
        shows; that still names it."""
        for light, name in (('<input aria-label="Light">', "Name Light"),
                            ("<button>Help</button>", "Name Help")):
            with self.subTest(light=light):
                html = self.page(
                    '<main><h1>x</h1><x-f><template shadowrootmode="open">'
                    '<label>Name <slot></slot> <input id="s"></label>'
                    f'</template>{light}</x-f></main>')
                self.assertEqual(self.found(html, "bb-control-label"),
                                 (True, []))

    def test_many_labels_for_one_control(self):
        """R5K-8: linear in the labels."""
        html = self.page("<main><h1>x</h1>" + "".join(
            f"<label for=t>L{i}</label>" for i in range(5000))
            + "<input id=t></main>")
        start = time.monotonic()
        run_page(html, "t.html", RB)
        self.assertLess(time.monotonic() - start, 20)


class TestNamesRound5(unittest.TestCase):
    """R5K-3, R5K-5, R5K-10, R5K-11, R5K-15: names as Chromium 141
    computes them (each case checked there)."""

    found = staticmethod(TestRulesRound2.found)
    page = TestRulesRound2.page

    def main(self, body, head=""):
        return self.page(f"<main><h1>x</h1>{body}</main>", head=head)

    def test_html_in_a_drawing_names_nothing(self):
        """R5K-3."""
        for body, rule, fails in (
                ('<a href="/"><svg role="none" width="80" height="40">'
                 '<foreignObject width="80" height="40"><p>Home</p>'
                 '</foreignObject></svg></a>', "bb-link-name", True),
                ('<button><svg role="presentation" width="8" height="8">'
                 '<foreignObject width="8" height="8"><span>Save</span>'
                 '</foreignObject></svg></button>', "bb-button-name", True),
                ('<a href="/"><svg role="none" width="80" height="40"><text>'
                 'Home</text></svg></a>', "bb-link-name", False)):
            with self.subTest(body=body[:40]):
                self.assertEqual(bool(self.found(self.main(body), rule)[1]),
                                 fails)

    def test_important_rules_beat_the_style_attribute(self):
        """R5K-5."""
        link = '<a href="/cart"><span class="lbl" style="{}">Cart</span></a>'
        for head, style, fails in (
                ("<style>.lbl{visibility:hidden!important}</style>",
                 "visibility:visible", True),
                ("<style>.lbl{display:inline!important}</style>",
                 "display:none", False),
                ("<style>.lbl{display:inline}</style>", "display:none", True)):
            with self.subTest(head=head):
                self.assertEqual(bool(self.found(self.main(
                    link.format(style), head), "bb-link-name")[1]), fails)
        empty = ('<a href="/x" class="d-ib" style="display:none"></a>')
        self.assertEqual(self.found(self.main(
            empty, "<style>.d-ib{display:inline-block!important}</style>"),
            "bb-link-name"), (True, [(FAIL, "blocker")]))
        label = '<label for="e" style="display:none">Email</label><input id="e">'
        self.assertEqual(self.found(self.main(
            label, "<style>label{display:inline!important}</style>"),
            "bb-control-label"), (True, []))

    def test_what_until_found_holds(self):
        """R5K-10: an inline element's content is rendered and names; a
        block's is skipped, but for its own name."""
        names = TestRulesRound3.names(self, self.main(
            '<a id="a1" href="/1"><span hidden="until-found">Direct <b>B'
            '</b></span></a>'
            '<a id="a2" href="/2"><div hidden="until-found">Div</div></a>'
            '<a id="a3" href="/3"><span hidden="until-found" style="display:'
            'block">SpanBlock</span></a>'
            '<a id="a4" href="/4" style="display:flex"><span hidden='
            '"until-found">Item</span></a>'
            '<a id="a5" href="/5"><div hidden="until-found" style="display:'
            'inline">DivInline</div></a>'
            '<a id="a6" href="/6"><div hidden="until-found" aria-label='
            '"OwnAL"><b>x</b></div></a>'
            '<a id="a7" href="/7"><span style="content-visibility:hidden">'
            'Cv</span></a>'
            '<label>Email <span hidden="until-found"><b>Address</b></span>'
            '<input id="i1"></label>'),
            "a1", "a2", "a3", "a4", "a5", "a6", "a7", "i1")
        self.assertEqual(names, {"a1": "Direct B", "a2": "", "a3": "",
                                 "a4": "", "a5": "DivInline", "a6": "OwnAL",
                                 "a7": "Cv", "i1": "Email Address"})

    def test_what_until_found_holds_in_a_capture(self):
        """R5K-10: the capture marks an element that skips what it holds
        "skips"; its own text names nothing."""
        from tests.test_rendered_rules import P, rerun
        html = (f'<!doctype html><html lang="en" {P}-hidden="recorded"><head>'
                '<title>T</title></head><body><main><h1>T</h1>'
                f'<a href="/1"><div hidden="until-found" {P}-hidden="skips">'
                'Direct</div></a><a href="/2"><span hidden="until-found">'
                'Inline</span></a></main></body></html>')
        page = rerun(html)
        got = [f.snippet for r in page.results if r.rule_id ==
               "bb-link-name" for f in r.findings]
        self.assertEqual(len(got), 1, got)
        self.assertIn('href="/1"', got[0])

    @unittest.skipUnless(HAVE_BROWSER, _WHY)
    def test_what_until_found_holds_in_a_browser(self):
        """R5K-10, end to end."""
        site = _echo_site(self, lambda t: PAGE.format(
            '<a href="/1"><div hidden="until-found">Direct</div></a>'
            '<a href="/2"><span hidden="until-found">Inline</span></a>'))
        d = tmpdir(self)
        code, _out, err = run("--url", f"{site.base}/p", "--json",
                              d / "r.json", "--fail-on", "never")
        self.assertEqual(code, 0, err)
        report = json.loads((d / "r.json").read_text())
        snippets = [f["snippet"] for p in report["pages"]
                    for f in p["findings"] if f["rule_id"] == "bb-link-name"]
        self.assertEqual(len(snippets), 1, snippets)
        self.assertIn('href="/1"', snippets[0])

    def test_a_drawing_is_named_by_its_own_title(self):
        """R5K-11."""
        for svg in ('<svg role="img" width="10" height="10"><g><title>G'
                    '</title><rect width="5" height="5"/></g></svg>',
                    '<svg role="img" width="10" height="10"><svg><title>'
                    'Inner</title></svg></svg>'):
            with self.subTest(svg=svg[:40]):
                self.assertEqual(self.found(self.main(svg), "bb-svg-name"),
                                 (True, [(FAIL, "serious")]))

    def test_aria_labeledby(self):
        """R5K-15: Chromium reads it as aria-labelledby, where that is
        absent, and as a global attribute."""
        html = self.main('<a id="l" href="/"><img src="x.png" role='
                         '"presentation" alt="Home" aria-labeledby="zz"></a>'
                         '<span id="zz">Z</span><button id="b" aria-labeledby='
                         '"zz" aria-labelledby="yy"></button><span id="yy">Y'
                         '</span>')
        self.assertEqual(TestRulesRound3.names(self, html, "l", "b"),
                         {"l": "Z", "b": "Y"})
        page = run_page(html, "t.html", RB)
        attr = [f.message for r in page.results if r.rule_id ==
                "bb-aria-attr" for f in r.findings]
        self.assertTrue(any("Chromium reads it as aria-labelledby" in m
                            for m in attr), attr)


class TestOwnStyleRound5(unittest.TestCase):
    """R5K-4, R5K-6, R5K-7, R5K-9, R5K-12, R5K-13."""

    found = staticmethod(TestRulesRound2.found)
    page = TestRulesRound2.page

    CASES = (
        # @supports as Chromium 141 settles it (R5K-4).
        ("<style>.lbl{display:none}@supports not (foo:bar){.lbl{display:"
         "inline}}</style>", False),
        ("<style>@supports not (foo:bar){.lbl{display:none}}</style>", True),
        ("<style>.lbl{display:none}@supports (not (display:grid)){.lbl{"
         "display:inline}}</style>", True),
        ("<style>@supports not (-webkit-touch-callout:none){.lbl{display:"
         "none}}</style>", True),
        ("<style>@supports (position:sticky){.lbl{display:none}}</style>",
         False),
        ("<style>.lbl{display:none}@supports (position:sticky){.lbl{display:"
         "inline}}</style>", False),
        # @media, @scope and comments (R5K-12).
        ("<style>@media not print and (min-width:1px){.lbl{display:none}}"
         "</style>", True),
        ("<style>@scope (main){.lbl{display:none}}</style>", True),
        ("<style>@scope (nav){.lbl{display:none}}</style>", False),
        ("<style>@scope (main) to (a){.lbl{display:none}}</style>", False),
        ('<style>.a::before{content:"/*"}.lbl{display:none}/* x */</style>',
         True),
        ("<style>.lbl{display:none}@media only{.lbl{display:inline}}</style>",
         True),
    )

    def test_each_case(self):
        link = '<main><h1>x</h1><a href="/cart"><span class="lbl">Cart' \
               '</span></a></main>'
        for head, fails in self.CASES:
            with self.subTest(head=head):
                self.assertEqual(self.found(self.page(link, head=head),
                                            "bb-link-name"),
                                 (True, [(FAIL, "blocker")] if fails else []))

    def test_nesting_stops_growing(self):
        """R5K-7: a nested rule past _MAX_NESTED characters is not read,
        and no page of a few hundred bytes takes long."""
        from bellbriar_harness.style import _MAX_NESTED, style_rules
        css = (",".join(f".c{i}" for i in range(20)) + "{") * 8 \
            + "display:none" + "}" * 8
        start = time.monotonic()
        rules = style_rules(css)
        run_page(self.page(
            '<main><h1>x</h1><a href="/"><span class="c1">Cart</span></a>'
            '</main>', head=f"<style>{css}</style>"), "t.html", RB)
        self.assertLess(time.monotonic() - start, 10)
        self.assertTrue(all(len(sel) <= _MAX_NESTED for sel, *_ in rules))

    def test_a_toggle_hidden_by_markup(self):
        """R5K-9: a show under a condition does not count for SCR28's
        toggle, whatever hides it; R5K-4 and R5K-5: one Chromium shows
        counts."""
        text = "<div><p>" + "Lots of content here. " * 20 + "</p></div>"
        links = ('<li><a href="/a">A</a></li><li><a href="/b">B</a></li>'
                 '<li><a href="/c">C</a></li>')
        review = (True, [(NEEDS_REVIEW, "moderate")])
        fail = (True, [(FAIL, "serious")])
        for style, attrs, want in (
                ("@media (max-width:600px){.t{display:block}}", "hidden",
                 fail),
                (".t{display:block}", "hidden", review),
                (".t{display:none}@supports not (foo:bar){.t{display:"
                 "inline-block}}", "", review),
                (".t{display:inline-block!important}",
                 'style="display:none"', review)):
            with self.subTest(style=style, attrs=attrs):
                html = self.page(
                    f'<header><button class="t" {attrs} aria-expanded='
                    '"false" aria-controls="menu">Menu</button><nav><ul '
                    f'id="menu">{links}</ul></nav></header>{text}',
                    head=f"<style>{style}</style>")
                self.assertEqual(self.found(html, "bb-skip-link"), want)

    def test_url_references_in_a_style(self):
        """R5K-13: not in a comment, nor in another string."""
        from bellbriar_harness.style import css_urls
        self.assertEqual(css_urls(
            '/* url(#q) */ a{fill:url(#g)} b{content:"url(#s)"} '
            'c{mask:url( "#m" )} d{x:myurl(#n)}'), ["#g", "#m"])
        page = run_page(TestRulesRound2.page(
            self, '<main><h1>x</h1><span id="q">a</span><span id="q">b'
            '</span><style>/* url(#q) */ p{content:"url(#q)"}</style>'
            '</main>'), "t.html", RB)
        got = [f.message for r in page.results if r.rule_id ==
               "bb-duplicate-id" for f in r.findings]
        self.assertTrue(got and "a drawing's reference" not in got[0], got)

    def test_the_readme_says_how_the_style_is_read(self):
        """R5K-6."""
        text = " ".join((ROOT / "README.md").read_text().split())
        for words in ("`!important` beats the style attribute",
                      "`@supports` Chromium fails is not read",
                      "20,000 characters"):
            self.assertIn(words, text)


@NEEDS_CRYPTO
class TestGuardRound5(unittest.TestCase):
    """A key whose bytes, written as they are into a string literal, hold a
    zero byte (found by the checker's random keys: one in nine has one)."""

    def test_a_zero_byte_in_a_literal(self):
        import repo_guard
        from cryptography.hazmat.primitives.asymmetric import ed25519
        seed = bytearray(range(0xA0, 0xC0))
        seed[5], seed[9] = 0x22, 0x00
        seed = bytes(seed)
        pub = ed25519.Ed25519PrivateKey.from_private_bytes(
            seed).public_key().public_bytes_raw()
        d = tmpdir(self)
        (d / "keys").mkdir()
        (d / "keys" / (hashlib.sha256(pub).hexdigest()[:16] + ".pub")
         ).write_text(pub.hex())
        (d / "k.py").write_bytes(('KEY = "' + seed.decode("latin-1").replace(
            '"', '\\"') + '"\n').encode("utf-16-le"))
        self.assertTrue(repo_guard.check(d))


class TestRulesRound5(unittest.TestCase):
    """R5K-14."""

    def test_root_aria_hidden_in_its_own_words(self):
        from bellbriar_harness import checks_rendered as CR
        from tests.test_rendered_rules import P, attr, rerun, run_record
        from tests.test_review_round_q import ALL_AXE
        record = attr(P + "-axe-run", run_record(
            ["aria-hidden-body"], sorted(set(ALL_AXE) - {"aria-hidden-body"})))
        html = (f'<!doctype html><html lang="en"{record}><head><title>T'
                '</title></head><body aria-hidden="TRUE"><main><h1>T</h1>'
                '</main></body></html>')
        page = rerun(html)
        got = [f.message for r in page.results if r.rule_id ==
               "bb-aria-hidden-body" for f in r.findings]
        self.assertEqual(len(got), 1, got)
        self.assertIn('aria-hidden="TRUE"', got[0])
        self.assertIn("but for bb-aria-hidden-body", CR.ROOT_HIDDEN_NOTE)


# ---------------------------------------------------------------------------
# Round 6: the reviews of round 5 (R5L, R5M)
# ---------------------------------------------------------------------------

class TestSecretsRound6(unittest.TestCase):
    """R5L-2 to R5L-6, R5L-8, R5L-9."""

    TOKEN = "TOKENabc1234567890xyz"

    def test_an_axe_message_is_cut_after_it_is_scrubbed(self):
        """R5L-2: the capture keeps axe-core's check texts whole (a text
        too long is not quoted), and the finding cuts the message after the
        run's secrets are replaced in it."""
        from bellbriar_harness import axe as A
        from bellbriar_harness import redact as R
        from bellbriar_harness.checks_static import _f
        text = ('ARIA attribute value is invalid: aria-current="'
                + "A" * 193 + self.TOKEN + '"')
        msg = A.message("aria-valid-attr-value", "Help", [text], "fail")
        self.assertIn(self.TOKEN, msg)
        self.assertIn("not quoted", A.message("r", "Help", ["x" * 5000],
                                              "fail"))
        token = R.set_run_secrets(secrets=[self.TOKEN])
        try:
            f = _f("bb-aria-attr-value", FAIL, "serious", msg,
                   limit=A.MAX_MESSAGE)
        finally:
            R.reset_run_secrets(token)
        self.assertNotIn(self.TOKEN[:6], f.message)
        self.assertLessEqual(len(f.message), A.MAX_MESSAGE)
        token = R.set_run_secrets(passwords=["Secr3tPassw0rd"])
        try:
            f = _f("bb-aria-attr-value", FAIL, "serious", msg.replace(
                self.TOKEN, "Secr3tPassw0rd"), limit=A.MAX_MESSAGE)
        finally:
            R.reset_run_secrets(token)
        self.assertEqual(f.message, R.WITHHELD_MESSAGE)

    def test_a_password_axe_core_says_is_refused(self):
        """R5L-3, R5L-8."""
        for word in ("foreground", "insufficient", "accessible  name",
                     "accessible\tname"):
            with self.subTest(word=word):
                self.assertTrue(cli._in_own_words(word))
        self.assertFalse(cli._in_own_words("x9Tq-7mWp-Lz3K"))

    def test_a_page_that_goes_to_the_password(self):
        """R5L-4: not evaluated; the run is incomplete, no bundle."""
        from tests.test_fetch_hardening import _Site, send

        def moved(h):
            h.send_response(302)
            h.send_header("Location", "/Zebra42q/page")
            h.send_header("Content-Length", "0")
            h.end_headers()
        site = _Site({"/r": moved, "/Zebra42q/page": send(
            PAGE.format("<p>x</p>").encode())})
        self.addCleanup(site.stop)
        d = tmpdir(self)
        (d / "pw").write_text("Zebra42q")
        code, out, err = run("--url", f"{site.base}/r", "--no-render",
                             "--http-user", "u", "--http-password-file",
                             d / "pw", "--json", d / "r.json", "--bundle",
                             d / "b.json", "--fail-on", "never")
        self.assertEqual(code, 2, err)
        self.assertIn("holds the --http-user password", err)
        self.assertFalse((d / "b.json").exists())
        self.assertNotIn("zebra42q", ((d / "r.json").read_text()
                                      + out + err).lower())

    def test_a_password_a_line_break_splits(self):
        """R5L-5: as a browser reads a URL, it is whole."""
        from bellbriar_harness import redact as R
        from bellbriar_harness.checks_static import PageContext, _f
        from bellbriar_harness.model import CURRENT_PAGE
        token = R.set_run_secrets(passwords=["Secr3tPassw0rd"])
        ctx = PageContext.parse(PAGE.format(
            '<img src="/a/Secr3t\nPassw0rd/i.png?x=1"><img src="/b/Secr3t'
            '\tPassw0rd/j.png">'), path="t.html")
        page_token = CURRENT_PAGE.set(ctx)
        try:
            got = [_f("bb-img-alt", FAIL, "blocker", "m", img).snippet
                   for img in ctx.soup.find_all("img")]
        finally:
            CURRENT_PAGE.reset(page_token)
            R.reset_run_secrets(token)
        self.assertEqual(got, [R.REDACTED, R.REDACTED])

    def test_a_cut_inside_a_page_url(self):
        """R5L-6: the long cut falls where a tag starts."""
        from bellbriar_harness.checks_static import PageContext, _f
        from bellbriar_harness.model import CURRENT_PAGE
        for markup in ('<img src="/i.png?a=' + "A" * 19953 + '" title='
                       '"https://user:Pw9secretXYZ@host/">',
                       '<div><img src="/i.png?a=' + "A" * 19953 + '"><a '
                       'title="https://user:Pw9secretXYZ@host/">x</a></div>'):
            with self.subTest(markup=markup[-60:]):
                ctx = PageContext.parse(PAGE.format(markup), path="t.html")
                page_token = CURRENT_PAGE.set(ctx)
                try:
                    f = _f("bb-img-alt", FAIL, "blocker", "m",
                           ctx.soup.find("main").contents[1])
                finally:
                    CURRENT_PAGE.reset(page_token)
                self.assertNotIn("Pw9", f.snippet)

    def test_an_ambiguous_option(self):
        """R5L-9."""
        self.assertIsNone(cli._bundle_given(["x.html", "--b", "README.md"]))
        self.assertEqual(cli._bundle_given(["--bun", "b.json"]), "b.json")


@NEEDS_CRYPTO
class TestGuardRound6(unittest.TestCase):
    """R5L-7: a key's 0x0D, or its 0x0A where a language lets a string
    hold one, written as it is."""

    def test_a_carriage_return_or_line_feed_in_a_literal(self):
        import repo_guard
        from cryptography.hazmat.primitives.asymmetric import ed25519
        for byte, name in ((0x0D, "k.php"), (0x0A, "k.rb"),
                           (0x0D, "k.js")):
            with self.subTest(byte=byte, name=name):
                seed = bytearray(range(0xA0, 0xC0))
                seed[9] = byte
                seed = bytes(seed)
                pub = ed25519.Ed25519PrivateKey.from_private_bytes(
                    seed).public_key().public_bytes_raw()
                d = tmpdir(self)
                (d / "keys").mkdir()
                (d / "keys" / (hashlib.sha256(pub).hexdigest()[:16]
                               + ".pub")).write_text(pub.hex())
                (d / name).write_bytes(('const KEY = "' + seed.decode(
                    "latin-1").replace('"', '\\"') + '";\n').encode())
                self.assertTrue(repo_guard.check(d))


class TestNamesRound6(unittest.TestCase):
    """R5L-1, R5M-1, R5M-2, R5M-4, R5M-8, R5M-9, R5M-10: names as Chromium
    141 computes them (each case checked there)."""

    names = TestRulesRound3.names
    found = staticmethod(TestRulesRound2.found)
    page = TestRulesRound2.page

    def main(self, body, head=""):
        return self.page(f"<main><h1>x</h1>{body}</main>", head=head)

    def test_what_a_box_skips(self):
        """R5L-1, R5M-1, R5M-2: a block, an inline block, a flex or grid
        container, a list item or a cell skips what it holds; a table, a
        row, ruby, an inline list item or an inline box does not; a float
        or a flex item is a block; the root of a name is skipped too."""
        cases = (
            ('<a id="x" href="/c" style="display:block;content-visibility:'
             'hidden">Cart</a>', ""),
            ('<button id="x" hidden="until-found">Save</button>', ""),
            ('<button id="x" style="content-visibility:hidden">Save</button>',
             ""),
            ('<a id="x" href="/c"><table hidden="until-found"><tr><td>Cart'
             '</td></tr></table></a>', "Cart"),
            ('<a id="x" href="/c"><table><tr hidden="until-found"><td>Cart'
             '</td></tr></table></a>', "Cart"),
            ('<a id="x" href="/c"><span style="display:inline list-item;'
             'content-visibility:hidden">Cart</span></a>', "Cart"),
            ('<a id="x" href="/c"><span style="display:table-row;'
             'content-visibility:hidden">Cart</span></a>', "Cart"),
            ('<a id="x" href="/c"><span style="float:left;content-visibility'
             ':hidden">Cart</span></a>', ""),
            ('<a id="x" href="/c" style="display:flex"><span style="display:'
             'inline;content-visibility:hidden">Cart</span></a>', ""),
            ('<a id="x" href="/c"><details><summary></summary>Cart</details>'
             '</a>', ""),
            ('<button id="x" aria-labelledby="y"></button><div hidden='
             '"until-found"><p id="y">Save</p></div>', ""),
            ('<button id="x" aria-labelledby="y"></button><div style='
             '"display:none"><p id="y">Save</p></div>', "Save"),
            ('<label for="x" style="display:block;content-visibility:hidden">'
             'Email</label><input id="x">', ""),
            ('<div hidden="until-found"><label for="x">Email</label></div>'
             '<input id="x">', ""),
        )
        for body, want in cases:
            with self.subTest(body=body[:60]):
                self.assertEqual(self.names(self.main(body), "x"),
                                 {"x": want})

    def test_what_a_box_skips_in_a_capture(self):
        """R5L-1: "shown-skips" on an element made visible again that
        skips what it holds."""
        from tests.test_rendered_rules import P, rerun
        html = (f'<!doctype html><html lang="en" {P}-hidden="recorded"><head>'
                '<title>T</title></head><body><main><h1>T</h1><a href="/1">'
                f'<span {P}-hidden="visibility"><span {P}-hidden="shown-skips"'
                '>Hidden words</span></span></a></main></body></html>')
        page = rerun(html)
        self.assertEqual(len([f for r in page.results if r.rule_id ==
                              "bb-link-name" for f in r.findings]), 1)

    @unittest.skipUnless(HAVE_BROWSER, _WHY)
    def test_what_a_box_skips_in_a_browser(self):
        """R5L-1, end to end: the capture marks only the boxes Chromium
        skips the content of."""
        site = _echo_site(self, lambda t: PAGE.format(
            '<a href="/1"><span style="visibility:hidden"><span style='
            '"display:block;visibility:visible;content-visibility:hidden">'
            'Hidden</span></span></a><a href="/2"><span style="display:'
            'table-row;content-visibility:hidden">Row</span></a><a href="/3"'
            ' style="display:block;content-visibility:hidden">Home</a>'))
        d = tmpdir(self)
        code, _out, err = run("--url", f"{site.base}/p", "--json",
                              d / "r.json", "--fail-on", "never")
        self.assertEqual(code, 0, err)
        report = json.loads((d / "r.json").read_text())
        hrefs = sorted(re.search(r'href="([^"]+)"', f["snippet"]).group(1)
                       for p in report["pages"] for f in p["findings"]
                       if f["rule_id"] == "bb-link-name")
        self.assertEqual(hrefs, ["/1", "/3"])

    def test_aria_labelledby_reads_a_drawing(self):
        """R5M-4: HTML in a <foreignObject>, and a drawing with no
        <title>, name what references them."""
        for body in ('<button id="x" aria-labelledby="y"></button><div id='
                     '"y"><svg role="none" width="80" height="40"><foreign'
                     'Object width="80" height="40"><p>Save</p></foreign'
                     'Object></svg></div>',
                     '<button id="x" aria-labelledby="y"></button><svg id="y"'
                     ' width="80" height="40"><foreignObject width="80" '
                     'height="40"><p>Save</p></foreignObject></svg>'):
            with self.subTest(body=body[:50]):
                self.assertEqual(self.names(self.main(body), "x"),
                                 {"x": "Save"})

    def test_a_labels_own_name_and_nested_labels(self):
        """R5M-8, R5M-9."""
        cases = (
            ('<label for="x" aria-label="Email"><svg aria-hidden="true" '
             'width="10" height="10"></svg></label><input id="x">', "Email"),
            ('<label aria-label="AL">Outer <input id="x"></label>', "AL"),
            ('<label for="x" aria-labeledby="z">Lab</label><input id="x">'
             '<span id="z">Zed</span>', "Zed"),
            ('<label>Outer <span aria-label="X"><label>Inner <input id="x">'
             '</label></span></label>', "Outer X Inner"),
            ('<label aria-labelledby="z">Outer <label>Inner <input id="x">'
             '</label></label><span id="z">Zed</span>', "Zed Inner"),
            ('<label>Outer <label>Inner <input id="x"></label></label>',
             "Outer Inner"),
            ('<label><svg width="200" height="50"><foreignObject width="200"'
             ' height="50"><label>Email <input id="x"></label></foreign'
             'Object></svg></label>', "Email"),
        )
        for body, want in cases:
            with self.subTest(body=body[:60]):
                self.assertEqual(self.names(self.main(body), "x"),
                                 {"x": want})

    def test_a_slots_fallback_held_the_control(self):
        """R5M-10."""
        html = self.main('<x-f><template shadowrootmode="open"><label>Name '
                         '<slot><input></slot> <input id="t"></label>'
                         '</template><b>light</b></x-f>')
        self.assertEqual(self.found(html, "bb-control-label"),
                         (True, [(FAIL, "blocker")]))


class TestOwnStyleRound6(unittest.TestCase):
    """R5M-3, R5M-5, R5M-6, R5M-7, R5M-11 to R5M-13: the page's own <style>
    as Chromium 141 applies it (each case checked there)."""

    found = staticmethod(TestRulesRound2.found)
    page = TestRulesRound2.page

    LINK = '<main><h1>x</h1><a href="/cart"><span class="lbl"{}>Cart</span>' \
           '</a></main>'

    CASES = (
        # R5M-3: a long top-level rule is read.
        (", ".join(f".item-{i}" for i in range(2500))
         + ", .lbl{display:none}", "", True),
        # R5M-5: media queries a browser drops.
        ("@media not print and(min-width:1px){.lbl{display:none}}", "",
         False),
        ("@media not print or (min-width:1px){.lbl{display:none}}", "",
         False),
        ("@media not print and (min-width:1px){.lbl{display:none}}", "",
         True),
        # R5M-6: @supports tokens and names.
        ("@supports not(foo:bar){.lbl{display:none}}", "", False),
        ("@supports not (-epub-caption-side:top){.lbl{display:none}}", "",
         False),
        (".lbl{display:none}@supports (-epub-writing-mode:horizontal-tb){"
         ".lbl{display:inline}}", "", False),
        ("@supports (--x:){.lbl{display:none}}", "", True),
        # R5M-7: CSS-wide keywords in the style attribute.
        (".lbl{display:none}", ' style="display:revert"', False),
        (".lbl{display:none}", ' style="display:revert-layer"', True),
        (".lbl{visibility:hidden}", ' style="visibility:initial"', False),
        (".lbl{visibility:hidden}", ' style="visibility:unset"', False),
        # R5M-13: an unquoted url() holding "/*".
        (".a{background:url(/img/*.png)}.lbl{display:none}/* c */", "",
         True),
    )

    def test_each_case(self):
        for style, attrs, fails in self.CASES:
            with self.subTest(style=style[:60], attrs=attrs):
                self.assertEqual(
                    self.found(self.page(self.LINK.format(attrs),
                                         head=f"<style>{style}</style>"),
                               "bb-link-name"),
                    (True, [(FAIL, "blocker")] if fails else []))

    def test_hostile_stylesheets_stay_fast(self):
        """R5M-11, R5M-12."""
        from bellbriar_harness.style import style_rules
        start = time.monotonic()
        style_rules("@supports (color: x" + " " * 80000 + "y){.a{display:"
                    "inline}}")
        style_rules(".p" * 6300 + "{ " + "&" * 140000 + " { display:none } }")
        self.assertLess(time.monotonic() - start, 5)

    def test_the_property_list_has_vendor_aliases(self):
        """R5M-6."""
        from bellbriar_harness.css_properties import PROPERTIES
        for name in ("-epub-caption-side", "-epub-text-combine",
                     "-epub-writing-mode", "-webkit-appearance"):
            self.assertIn(name, PROPERTIES)
        self.assertNotIn("-webkit-touch-callout", PROPERTIES)



# ---------------------------------------------------------------------------
# Round 7: the reviews of round 6 (R5N, R5O)
# ---------------------------------------------------------------------------

class TestSecretsRound7(unittest.TestCase):
    """R5N-2, R5N-3, R5N-5, R5N-7."""

    def test_a_message_beside_a_withheld_snippet(self):
        """R5N-2: a message quoting markup that held the password is
        withheld with it, its line break made a space or not."""
        from bellbriar_harness import axe as A
        from bellbriar_harness import redact as R
        from bellbriar_harness.checks_static import PageContext, _f
        from bellbriar_harness.model import CURRENT_PAGE
        self.assertEqual(A._check_text(" a\nb "), "a\nb")
        token = R.set_run_secrets(passwords=["Secr3tPassw0rd"])
        try:
            ctx = PageContext.parse(PAGE.format(
                '<a href="/x" aria-current="/a/Secr3t\nPassw0rd">Echo</a>'),
                path="t.html")
            page_token = CURRENT_PAGE.set(ctx)
            try:
                f = _f("bb-aria-attr-value", FAIL, "serious",
                       'aria-current="/a/Secr3t Passw0rd" is not valid',
                       ctx.soup.find("a"), limit=A.MAX_MESSAGE)
            finally:
                CURRENT_PAGE.reset(page_token)
            self.assertEqual((f.snippet, f.message),
                             (R.REDACTED, R.WITHHELD_MESSAGE))
            page = run_page(PAGE.format(
                '<img src="/i.png" alt="Secr3t\nPassw0rd.png">'), "t.html",
                RB)
            said = " ".join(f.message + f.snippet for r in page.results
                            for f in r.findings)
            self.assertNotIn("Passw0rd", said)
        finally:
            R.reset_run_secrets(token)

    def test_the_console_never_shows_the_password(self):
        """R5N-3: what the console prints has the password replaced, in any
        case and any spelling the run withholds."""
        url = "http://h/CORRECT-horse-battery-staple/x"
        got = cli._without_password(url, "correct-horse-battery-staple")
        self.assertNotIn("horse", got.lower())
        self.assertIn("REDACTED", got)
        self.assertEqual(cli._without_password("abc", "Zq9"), "abc")

    @unittest.skipUnless(HAVE_BROWSER, _WHY)
    def test_a_refresh_to_the_password_that_errors(self):
        """R5N-3, end to end."""
        from tests.test_fetch_hardening import _Site, send
        secret = "correct-horse-battery-staple"
        site = _Site({"/meta": send(PAGE.format(
            f'<meta http-equiv="refresh" content="0;url=/{secret}/x"><p>x'
            '</p>').encode())})
        self.addCleanup(site.stop)
        d = tmpdir(self)
        (d / "pw").write_text(secret)
        _code, out, err = run("--url", f"{site.base}/meta", "--http-user",
                              "u", "--http-password-file", d / "pw",
                              "--json", d / "r.json", "--fail-on", "never")
        self.assertNotIn(secret, (out + err).lower())

    def test_the_refusal_ignores_case(self):
        """R5N-5: a password the harness's words hold in another case is
        refused before the run, as too common."""
        self.assertTrue(cli._in_own_words("Rendering"))
        self.assertTrue(cli._in_own_words("FOREGROUND"))
        self.assertFalse(cli._in_own_words("x9Tq-7mWp-Lz3K"))

    def test_baseline_with_no_value(self):
        """R5N-7."""
        self.assertEqual(cli._bundle_given(
            ["x.html", "--bundle", "out.json", "--baseline"]), "out.json")


class TestGuardRound7(unittest.TestCase):
    """R5N-1, R5N-4: a key over two lines, and after a short string."""

    @staticmethod
    def keyed(test, seed):
        from cryptography.hazmat.primitives.asymmetric import ed25519
        pub = ed25519.Ed25519PrivateKey.from_private_bytes(
            seed).public_key().public_bytes_raw()
        d = tmpdir(test)
        (d / "keys").mkdir()
        (d / "keys" / (hashlib.sha256(pub).hexdigest()[:16] + ".pub")
         ).write_text(pub.hex())
        return d

    def test_a_bytes_literal_over_two_lines(self):
        import repo_guard
        for k in range(8):
            seed = hashlib.sha256(b"bellbriar R5N probe %d" % k).digest()
            for text in (f"KEY = ({seed[:16]!r}\n       {seed[16:]!r})\n",
                         f"KEY = {seed[:16]!r} \\\n      {seed[16:]!r}\n"):
                with self.subTest(k=k, text=text[:12]):
                    d = self.keyed(self, seed)
                    (d / "k.py").write_text(text)
                    self.assertTrue(repo_guard.check(d))

    def test_a_key_after_a_short_string(self):
        import repo_guard
        for k in range(8):
            seed = bytearray(hashlib.sha256(b"bellbriar R5N probe %d" % k)
                             .digest())
            seed[9] = 0x0A
            seed = bytes(b if b not in (0x22, 0x5C, 0x00, 0x0D) else 0x41
                         for b in seed)
            for name, before in (
                    ("k.php", '<?php\necho "Hello, world!";\n// the signing '
                              'key used by the tests\n$KEY = "'),
                    ("k.rb", 'URL = "https://example.com/"\n# the signing key'
                             ' used by the tests\nKEY = "')):
                with self.subTest(k=k, name=name):
                    d = self.keyed(self, seed)
                    (d / name).write_bytes((before + seed.decode("latin-1")
                                            + '"\n').encode())
                    self.assertTrue(repo_guard.check(d))


class TestNamesRound7(unittest.TestCase):
    """R5O-1, R5O-2, R5O-5, R5O-7, R5O-9 to R5O-11, R5N-6: names as
    Chromium 141 computes them (each case checked there)."""

    names = TestRulesRound3.names
    found = staticmethod(TestRulesRound2.found)
    page = TestRulesRound2.page

    def main(self, body, head=""):
        return self.page(f"<main><h1>x</h1>{body}</main>", head=head)

    def test_visibility_keywords_take_the_parents(self):
        """R5O-1: inherit, unset and revert in a style attribute leave the
        element as hidden as its parent (GSAP's autoAlpha writes inherit)."""
        for body in (
                '<div style="visibility:hidden"><a href="/x" style="visibility'
                ':inherit"></a></div>',
                '<div style="visibility:hidden"><a href="/x" style="visibility'
                ':unset"></a></div>',
                '<nav style="visibility:hidden"><ul><li style="visibility:'
                'inherit"><a href="/x"><i class="icon"></i></a></li></ul>'
                '</nav>'):
            with self.subTest(body=body[:50]):
                self.assertEqual(self.found(self.main(body), "bb-link-name"),
                                 (False, []))
        self.assertEqual(self.found(self.main(
            '<div style="visibility:hidden"><button style="visibility:revert">'
            '</button></div>'), "bb-button-name"), (False, []))
        self.assertEqual(self.found(self.main(
            '<div style="visibility:hidden"><a href="/x" style="visibility:'
            'visible"></a></div>'), "bb-link-name"),
            (True, [(FAIL, "blocker")]))

    def test_a_target_in_a_closed_details(self):
        """R5O-2: what a closed <details> holds names nothing, through
        aria-labelledby too; its first <summary> does."""
        cases = (
            ('<button id="x" aria-labelledby="d"></button><details><summary>'
             'S</summary><p id="d">Save</p></details>', ""),
            ('<button id="x" aria-labelledby="d"></button><details><summary>'
             'S</summary><div><span id="d">Save</span></div></details>', ""),
            ('<button id="x" aria-labelledby="d"></button><details open>'
             '<summary>S</summary><p id="d">Save</p></details>', "Save"),
            ('<button id="x" aria-labelledby="d"></button><details><summary '
             'id="d">Save</summary>z</details>', "Save"),
            ('<button id="x" aria-labelledby="d"></button><details><summary>'
             'S</summary><summary id="d">Save</summary></details>', ""),
            ('<label for="x" aria-labelledby="z">Lab</label><input id="x">'
             '<details><summary>S</summary><span id="z">Zed</span></details>',
             "Lab"),
        )
        for body, want in cases:
            with self.subTest(body=body[:60]):
                self.assertEqual(self.names(self.main(body), "x"),
                                 {"x": want})

    def test_displays_as_chromium_computes_them(self):
        """R5O-7, R5N-6: CSS-wide keywords resolved, a button always a box,
        multi-keyword displays, blockification through display:contents
        and not by a -webkit-box, a drawing's own content skipped, a padded
        until-found the plain hidden attribute."""
        cases = (
            ('<a id="x" href="/c" style="display:block"><div style="display:'
             'inherit;content-visibility:hidden">Cart</div></a>', ""),
            ('<a id="x" href="/c"><div style="display:inherit;content-'
             'visibility:hidden">Cart</div></a>', "Cart"),
            ('<a id="x" href="/c"><div style="display:revert;content-'
             'visibility:hidden">Cart</div></a>', ""),
            ('<a id="x" href="/c"><div style="display:unset;content-'
             'visibility:hidden">Cart</div></a>', "Cart"),
            ('<button id="x" style="display:inline;content-visibility:hidden">'
             'Save</button>', ""),
            ('<button id="x" style="display:ruby;content-visibility:hidden">'
             'Save</button>', ""),
            ('<button id="x" style="display:contents;content-visibility:'
             'hidden">Save</button>', "Save"),
            ('<a id="x" href="/c"><span style="display:flow-root list-item;'
             'content-visibility:hidden">Cart</span></a>', ""),
            ('<a id="x" href="/c"><span style="display:inline flow-root '
             'list-item;content-visibility:hidden">Cart</span></a>', ""),
            ('<a id="x" href="/c"><span style="display:block ruby;content-'
             'visibility:hidden">Cart</span></a>', ""),
            ('<a id="x" href="/c"><span style="display:table-column;content-'
             'visibility:hidden">Cart</span></a>', "Cart"),
            ('<a id="x" href="/c"><span style="display:block math;content-'
             'visibility:hidden">Cart</span></a>', ""),
            ('<a id="x" href="/c"><span style="display:math;content-'
             'visibility:hidden">Cart</span></a>', "Cart"),
            ('<a id="x" href="/c"><span style="float:left;display:table-row;'
             'content-visibility:hidden">Cart</span></a>', ""),
            ('<a id="x" href="/c"><span style="float:left;display:inline-'
             'table;content-visibility:hidden">Cart</span></a>', "Cart"),
            ('<a id="x" href="/c" style="display:-webkit-box"><span hidden='
             '"until-found">Cart</span></a>', "Cart"),
            ('<a id="x" href="/c" style="display:flex"><span style="display:'
             'contents"><span hidden="until-found">Cart</span></span></a>',
             ""),
            ('<a id="x" href="/c"><svg style="content-visibility:hidden" '
             'width="10" height="10"><title>Cart</title></svg></a>', ""),
            ('<a id="x" href="/c"><canvas style="content-visibility:hidden" '
             'width="10" height="10">Cart</canvas></a>', ""),
            ('<a id="x" href="/c"><img style="display:block;content-'
             'visibility:hidden" alt="Cart" src="data:,"></a>', "Cart"),
            ('<a id="x" href="/c"><span hidden=" until-found ">Cart</span>'
             '</a>', ""),
            ('<a id="x" href="/c"><span hidden="UNTIL-FOUND">Cart</span></a>',
             "Cart"),
        )
        for body, want in cases:
            with self.subTest(body=body[:70]):
                self.assertEqual(self.names(self.main(body), "x"),
                                 {"x": want})

    def test_the_hidden_attribute_is_htmls(self):
        """R5O-11: <svg hidden> and a part of a drawing marked so are
        shown, as in Chromium 141; HTML in a <foreignObject> is hidden."""
        self.assertEqual(self.found(self.main(
            '<a href="/x"><svg hidden width="10" height="10"><title>Home'
            '</title></svg></a>'), "bb-link-name"), (True, []))
        self.assertEqual(self.names(self.main(
            '<a id="x" href="/x"><svg width="10" height="10"><title hidden>'
            'Home</title></svg></a>'), "x"), {"x": "Home"})
        from bellbriar_harness.checks_static import PageContext
        from bellbriar_harness.style import namespace_of, ua_hidden
        for reader in ("html5", "dom"):
            with self.subTest(reader=reader):
                ctx = PageContext.parse(self.main(
                    '<svg hidden><foreignObject><p hidden id="p">x</p>'
                    '</foreignObject></svg><math><mtext><span id="s">x</span>'
                    '</mtext><mi id="m" hidden>x</mi></math>'),
                    path="t.html", **({} if reader == "html5"
                                      else {"reader": "dom"}))
                soup = ctx.soup
                self.assertFalse(ua_hidden(soup.find("svg")))
                self.assertTrue(ua_hidden(soup.find(id="p")))
                self.assertFalse(ua_hidden(soup.find(id="m")))
                self.assertEqual([namespace_of(soup.find(id=i))
                                  for i in ("p", "s", "m")],
                                 ["html", "html", "math"])

    def test_an_inner_label_is_read_once(self):
        """R5O-9: one the outer label's text reached by its own name."""
        cases = (
            ('<label>Outer <label aria-label="X">Inner <input id="x"></label>'
             '</label>', "Outer X"),
            ('<label>Outer <label aria-labelledby="z">Inner <input id="x">'
             '</label></label><span id="z">Zed</span>', "Outer Zed"),
            ('<label>Outer <span aria-label="X"><label>Inner <input id="x">'
             '</label></span></label>', "Outer X Inner"),
        )
        for body, want in cases:
            with self.subTest(body=body[:60]):
                self.assertEqual(self.names(self.main(body), "x"),
                                 {"x": want})

    def test_a_template_in_a_slots_fallback(self):
        """R5O-10: what a template holds is no part of the tree."""
        html = self.main('<x-f><template shadowrootmode="open"><label>Name '
                         '<slot><template><input></template></slot> <input '
                         'id="t"></label></template><b>light</b></x-f>')
        self.assertEqual(self.found(html, "bb-control-label"), (True, []))

    def test_invisible_and_skipping_in_a_capture(self):
        """R5O-5: "visibility-skips" on an element invisible that skips
        what it holds; an aria-labelledby target inside it names nothing."""
        from tests.test_rendered_rules import P, rerun
        html = (f'<!doctype html><html lang="en" {P}-hidden="recorded"><head>'
                '<title>T</title></head><body><main><h1>T</h1><button '
                f'aria-labelledby="y"></button><div {P}-hidden="visibility-'
                f'skips"><p id="y" {P}-hidden="display">Save</p></div></main>'
                '</body></html>')
        page = rerun(html)
        self.assertEqual(len([f for r in page.results if r.rule_id ==
                              "bb-button-name" for f in r.findings]), 1)

    @unittest.skipUnless(HAVE_BROWSER, _WHY)
    def test_skipping_in_a_browser(self):
        """R5O-5, R5N-6, R5O-1, end to end. The page's stylesheet skips,
        which markup does not show: the capture's record decides."""
        displays = ("flow-root list-item", "inline flow-root list-item",
                    "block ruby", "inline list-item", "table-row")
        style = "<style>.v{visibility:hidden;content-visibility:hidden}" + "".join(
            f".s{i}{{display:{d};content-visibility:hidden}}"
            for i, d in enumerate(displays)) + "</style>"
        site = _echo_site(self, lambda t: PAGE.format(
            style + '<button aria-labelledby="y"></button><div class="v"><p '
            'id="y">Save</p></div>'
            + "".join(f'<a href="/{i}"><span class="s{i}">Cart</span></a>'
                      for i in range(len(displays)))
            + '<nav style="visibility:hidden;opacity:0"><a href="/g" style="'
            'opacity:1;visibility:inherit"><svg width="10" height="10"></svg>'
            '</a></nav>'))
        d = tmpdir(self)
        code, _out, err = run("--url", f"{site.base}/p", "--json",
                              d / "r.json", "--fail-on", "never")
        self.assertEqual(code, 0, err)
        report = json.loads((d / "r.json").read_text())
        found = [(f["rule_id"], f["snippet"]) for p in report["pages"]
                 for f in p["findings"] if f["verdict"] == "fail"]
        self.assertEqual(sorted(re.search(r'href="([^"]+)"', s).group(1)
                                for r, s in found if r == "bb-link-name"),
                         ["/0", "/1", "/2"])
        self.assertEqual(len([r for r, _s in found if r == "bb-button-name"]),
                         1)


class TestOwnStyleRound7(unittest.TestCase):
    """R5O-4, R5O-8: the page's own <style> as Chromium 141 applies it
    (each case checked there)."""

    found = staticmethod(TestRulesRound2.found)
    page = TestRulesRound2.page
    LINK = TestOwnStyleRound6.LINK

    CASES = (
        # R5O-4: CSS-wide keywords under a condition.
        (".lbl{display:none}@media (min-width:1px){.lbl{display:revert}}",
         False),
        (".lbl{display:none}@supports (color: red){.lbl{display:revert}}",
         False),
        (".lbl{visibility:hidden}@media (min-width:1px){.lbl{visibility:"
         "inherit}}", False),
        (".lbl{visibility:hidden}@media (min-width:1px){.lbl{visibility:"
         "unset}}", False),
        # R5O-8: an empty query in a list; a function in a query.
        ("@media print, {.lbl{display:none}}", False),
        ("@media , print {.lbl{display:none}}", False),
        (".lbl{display:none}@media not print and foo(1){.lbl{display:"
         "inline}}", False),
        ("@media not print and foo(1){.lbl{display:none}}", True),
    )

    def test_each_case(self):
        for style, fails in self.CASES:
            with self.subTest(style=style[:60]):
                self.assertEqual(
                    self.found(self.page(self.LINK.format(""),
                                         head=f"<style>{style}</style>"),
                               "bb-link-name"),
                    (True, [(FAIL, "blocker")] if fails else []))

    def test_a_conditional_keyword_never_hides(self):
        """R5O-4: where it could be either, a toggle a rule hides stays
        hidden (conditional marks count only when asked)."""
        from bellbriar_harness.style import INHERIT, REVERT, _decide
        marks = {("display", False, 2, False), ("display", REVERT, 2, True)}
        self.assertTrue(_decide(marks, "display"))
        self.assertFalse(_decide(marks, "display", conditional=False))
        self.assertFalse(_decide(marks, "display", ua_sheet=True))
        marks = {("visibility", False, 2, False),
                 ("visibility", INHERIT, 2, True)}
        self.assertIsNone(_decide(marks, "visibility"))
        self.assertFalse(_decide(marks, "visibility", conditional=False))


class TestRulesRound7(unittest.TestCase):
    """R5O-3: the note says what a file run reads."""

    def test_the_label_note(self):
        note = next(r["notes"] for r in RB["rules"]
                    if r["id"] == "bb-control-label")
        self.assertIn("a file run reads content-visibility and display in "
                      "the style attribute only", note)


# ---------------------------------------------------------------------------
# Round 8: the reviews of round 7 (R5P, R5Q)
# ---------------------------------------------------------------------------

class TestSecretsRound8(unittest.TestCase):
    """R5P-1, R5P-2."""

    def test_a_message_that_does_not_quote_the_password(self):
        """R5P-1: the snippet of an element whose markup holds the password
        is withheld; its message keeps its words unless it quotes it."""
        from bellbriar_harness import redact as R
        token = R.set_run_secrets(passwords=["Zephyr-Quill-4471"])
        try:
            page = run_page(
                '<!doctype html><html><head><title>Shop</title></head><body>'
                '<main><h1>Shop</h1><img src="/img/Zephyr-Quill-4471.png"><p>'
                'Staging build Zephyr-Quill-4471</p><img src="/i.png" alt="'
                'Zephyr-Qu\nill-4471.png"></main></body></html>', "t.html", RB)
        finally:
            R.reset_run_secrets(token)
        got = {(r.rule_id, f.message.startswith("(withheld"), f.snippet)
               for r in page.results for f in r.findings
               if r.rule_id in ("bb-html-lang", "bb-img-alt", "bb-alt-junk")}
        self.assertIn(("bb-html-lang", False, R.REDACTED), got)
        self.assertIn(("bb-img-alt", False, R.REDACTED), got)
        said = " ".join(f.message for r in page.results for f in r.findings)
        self.assertNotIn("ill-4471", said)
        self.assertIn(("bb-alt-junk", True, R.REDACTED), got)

    def test_the_password_as_a_url_writes_it(self):
        """R5P-2: a browser percent-encodes only what a URL must; every
        character in any of its spellings, in any case, is found."""
        from bellbriar_harness import redact as R
        password = "Kq7 vX!p2$Lm9"
        for text in ("http://h/Kq7%20vX!p2$Lm9/", "http://h/kq7+vx%21p2%24LM9",
                     "Kq7 vX&#33;p2&#x24;Lm9", "K q 7\nvX!p2$Lm9"):
            with self.subTest(text=text):
                self.assertTrue(cli._password_in(password, [text]))
                self.assertNotIn("p2", cli._without_password(text, password)
                                 .replace("REDACTED", ""))
        self.assertFalse(cli._password_in(password, ["http://h/Kq7%2520vX"]))
        self.assertIsNone(R.password_pattern("abc"))
        token = R.set_run_secrets(passwords=[password])
        try:
            self.assertTrue(R.holds_password('<a href="/Kq7%20vX!p2$Lm9/">'))
            self.assertFalse(R.holds_password('<a href="/Kq7vXp2Lm9/">'))
        finally:
            R.reset_run_secrets(token)

    def test_a_page_that_goes_to_the_password_encoded(self):
        """R5P-2, end to end: refused, and nothing records or prints it."""
        from tests.test_fetch_hardening import _Site, send

        def moved(h):
            h.send_response(302)
            h.send_header("Location", "/ok/Kq7%20vX!p2$Lm9/")
            h.send_header("Content-Length", "0")
            h.end_headers()
        site = _Site({"/r": moved, "/ok/Kq7%20vX!p2$Lm9/": send(
            PAGE.format("<p>x</p>").encode())})
        self.addCleanup(site.stop)
        d = tmpdir(self)
        (d / "pw").write_text("Kq7 vX!p2$Lm9")
        code, out, err = run("--url", f"{site.base}/r", "--no-render",
                             "--http-user", "u", "--http-password-file",
                             d / "pw", "--json", d / "r.json", "--bundle",
                             d / "b.json", "--fail-on", "never")
        self.assertEqual(code, 2, err)
        self.assertIn("holds the --http-user password", err)
        self.assertFalse((d / "b.json").exists())
        self.assertNotIn("p2$lm9", ((d / "r.json").read_text() + out + err)
                         .lower())


class TestGuardRound8(unittest.TestCase):
    """R5P-3: a key in a string after a short one on the same line."""

    @staticmethod
    def js(seed, unicode=False):
        out = ""
        for b in seed:
            if b in (0x22, 0x5C):
                out += "\\" + chr(b)
            elif 0x20 <= b < 0x7F:
                out += chr(b)
            else:
                out += ("\\u%04x" % b) if unicode else ("\\x%02x" % b)
        return out

    def test_a_key_after_a_short_string_on_one_line(self):
        import repo_guard
        for k in range(6):
            seed = hashlib.sha256(b"bellbriar R5P probe %d" % k).digest()
            for name, text in (
                    ("k.js", 'console.log("Key:", sign(data, "'
                     + self.js(seed) + '"));\n'),
                    ("k.js", 'console.log("Key:", sign(data, "'
                     + self.js(seed, True) + '"));\n'),
                    ("k.py", 'print("Key:", sign(data, "' + self.js(seed)
                     + '"))')):
                with self.subTest(k=k, text=text[:40]):
                    d = TestGuardRound7.keyed(self, seed)
                    (d / name).write_text(text)
                    self.assertTrue(repo_guard.check(d))


class TestNamesRound8(unittest.TestCase):
    """R5P-4, R5Q-4 to R5Q-7, R5Q-9 to R5Q-11, a label's title: names as
    Chromium 141 computes them (each case checked there)."""

    names = TestRulesRound3.names
    found = staticmethod(TestRulesRound2.found)
    page = TestRulesRound2.page

    def main(self, body, head=""):
        return self.page(f"<main><h1>x</h1>{body}</main>", head=head)

    def test_skipping_as_chromium_measures_it(self):
        """R5P-4, R5Q-5, R5Q-6, R5Q-7."""
        cases = (
            # A parent's display:inherit, a slot and a shadow root's host.
            ('<a id="x" href="/c" style="display:flex"><span style="display:'
             'inherit"><span hidden="until-found">Cart</span></span></a>', ""),
            ('<a id="x" href="/c"><x-c style="display:flex"><template '
             'shadowrootmode="open"><slot></slot></template><span hidden='
             '"until-found">Cart</span></x-c></a>', ""),
            ('<a id="x" href="/c"><x-d style="display:block"><template '
             'shadowrootmode="open"><span style="display:inherit;content-'
             'visibility:hidden">Cart</span></template></x-d></a>', ""),
            ('<a id="x" href="/c"><x-e style="display:flex"><template '
             'shadowrootmode="open"><span hidden="until-found">Cart</span>'
             '</template></x-e></a>', ""),
            # A drawing: its <foreignObject> and its parts skip too.
            ('<button id="x" aria-labelledby="y"></button><div id="y"><svg '
             'width="80" height="40"><foreignObject style="display:inline;'
             'content-visibility:hidden" width="80" height="40"><div>Save'
             '</div></foreignObject></svg></div>', ""),
            ('<button id="x" aria-labelledby="y"></button><svg id="y" width='
             '"80" height="40"><g style="content-visibility:hidden"><text '
             'y="9">Save</text></g></svg>', ""),
            ('<button id="x" aria-labelledby="y"></button><svg id="y" width='
             '"80" height="40"><foreignObject hidden="until-found" width="80"'
             ' height="40"><div>Save</div></foreignObject></svg>', "Save"),
            # A fieldset is a box, a legend a block, whatever they display.
            ('<fieldset style="display:inline;content-visibility:hidden">'
             '<label for="x">Email</label></fieldset><input id="x">', ""),
            ('<div><legend style="display:table-row;content-visibility:'
             'hidden"><label for="x">Email</label></legend></div><input '
             'id="x">', ""),
            ('<fieldset><legend style="display:table;content-visibility:'
             'hidden"><label for="x">Email</label></legend></fieldset><input '
             'id="x">', "Email"),
            # A textarea's text is its value.
            ('<a id="x" href="/c"><textarea style="content-visibility:'
             'hidden">Cart</textarea></a>', "Cart"),
        )
        for body, want in cases:
            with self.subTest(body=body[:70]):
                self.assertEqual(self.names(self.main(body), "x"),
                                 {"x": want})

    def test_labels(self):
        """R5Q-10, R5Q-11, and a label's title, read when its content
        gives nothing."""
        cases = (
            ('<label aria-labelledby="in">Outer <label id="in">Inner <input '
             'id="x"></label></label>', "Inner"),
            ('<label for="x" title="Tt"></label><input id="x">', "Tt"),
            ('<label for="x" title="Tt"><span aria-hidden="true">x</span>'
             '</label><input id="x">', "Tt"),
            ('<label title="Tt"><input id="x"></label>', "Tt"),
            ('<label for="x" title="Tt">Lab</label><input id="x">', "Lab"),
            ('<label>Name <svg><input></input></svg> <input id="x"></label>',
             "Name"),
        )
        for body, want in cases:
            with self.subTest(body=body[:60]):
                self.assertEqual(self.names(self.main(body), "x"),
                                 {"x": want})
        html = self.main('<x-f><template shadowrootmode="open"><label>Name '
                         '<slot><svg><input></input></svg></slot> <input '
                         'id="t"></label></template><b>light</b></x-f>')
        self.assertEqual(self.found(html, "bb-control-label"), (True, []))

    def test_hidden_or_shown(self):
        """R5Q-4, R5Q-9: a rule's show ends the walk past inherit, var()
        shows; only a closed <details>' first <summary> is shown."""
        for body, head, rule, fails in (
                ('<div style="visibility:hidden"><span class="v"><a href="/x" '
                 'style="visibility:inherit"></a></span></div>',
                 "<style>.v{visibility:visible}</style>", "bb-link-name",
                 True),
                ('<div style="visibility:hidden;--v:visible"><a href="/x" '
                 'style="visibility:var(--v)"></a></div>', "", "bb-link-name",
                 True),
                ('<details><summary>S</summary><summary><a href="/x"></a>'
                 '</summary></details>', "", "bb-link-name", None),
                ('<details><summary><a href="/x"></a></summary></details>', "",
                 "bb-link-name", True)):
            with self.subTest(body=body[:60]):
                self.assertEqual(self.found(self.main(body, head=head), rule),
                                 (False, []) if fails is None else
                                 (True, [(FAIL, "blocker")] if fails else []))

    def test_deep_inherit_chains_stay_fast(self):
        """R5Q-1: each element's display is read once."""
        body = ("<p><span>" + '<span style="display:inherit;content-'
                'visibility:hidden"><a href="/x">t</a>' * 200 + "</span>" * 200
                + "</span></p>")
        start = time.monotonic()
        run_page(self.main(body), "t.html", RB)
        self.assertLess(time.monotonic() - start, 10)

    @unittest.skipUnless(HAVE_BROWSER, _WHY)
    def test_boxes_and_values_in_a_browser(self):
        """R5P-4, R5Q-7, end to end: a stylesheet's skipping, which markup
        does not show."""
        site = _echo_site(self, lambda t: PAGE.format(
            "<style>.s{display:inline;content-visibility:hidden}</style>"
            '<fieldset class="s"><label for="e">Email</label></fieldset>'
            '<input id="e"><a href="/t"><textarea class="s">Cart</textarea>'
            "</a>"))
        d = tmpdir(self)
        code, _out, err = run("--url", f"{site.base}/p", "--json",
                              d / "r.json", "--fail-on", "never")
        self.assertEqual(code, 0, err)
        report = json.loads((d / "r.json").read_text())
        failed = [(f["rule_id"], f["snippet"]) for p in report["pages"]
                  for f in p["findings"] if f["verdict"] == "fail"]
        self.assertTrue(any(r == "bb-control-label" and 'id="e"' in s
                            for r, s in failed), failed)
        self.assertFalse([s for r, s in failed if r == "bb-link-name"])


class TestOwnStyleRound8(unittest.TestCase):
    """R5Q-2, R5Q-3: the page's own <style> as Chromium 141 applies it
    (each case checked there, at 1280 pixels)."""

    found = staticmethod(TestRulesRound2.found)
    page = TestRulesRound2.page

    CASES = (
        # R5Q-2: a conditional inherit never outranks a show to hide.
        ('<a href="/x"><span class="menu"><span class="item">Cart</span>'
         '</span></a>', "@layer base{.item{visibility:visible}} .menu{"
         "visibility:hidden} @media (max-width:600px){.item{visibility:"
         "inherit}}", False),
        ('<a href="/x"><span class="menu"><span class="item" style="'
         'visibility:visible">Cart</span></span></a>', ".menu{visibility:"
         "hidden} @media (max-width:600px){.item{visibility:inherit "
         "!important}}", False),
        # R5Q-3: a function in a media query is unknown.
        ('<a href="/x"><span class="lbl">Cart</span></a>', ".lbl{display:"
         "none} @media screen and max-width(6000px){.lbl{display:inline}}",
         True),
        ('<a href="/x"><span class="lbl">Cart</span></a>', ".lbl{display:"
         "none} @media (min-width:1px) and foo(1){.lbl{display:inline}}",
         True),
        ('<a href="/x"><span class="lbl">Cart</span></a>', ".lbl{display:"
         "none} @media foo(1) or (min-width:1px){.lbl{display:inline}}",
         False),
    )

    def test_each_case(self):
        for body, style, fails in self.CASES:
            with self.subTest(style=style[:60]):
                self.assertEqual(
                    self.found(self.page(f"<main><h1>x</h1>{body}</main>",
                                         head=f"<style>{style}</style>"),
                               "bb-link-name"),
                    (True, [(FAIL, "blocker")] if fails else []))


class TestRulesRound8(unittest.TestCase):
    """The note names a label's title."""

    def test_the_label_note(self):
        note = next(r["notes"] for r in RB["rules"]
                    if r["id"] == "bb-control-label")
        self.assertIn("then by its content (", note)
        self.assertIn("), then by its title", note)

class TestSecretsRound9(unittest.TestCase):
    """R5R-1, R5R-2, R5R-5 to R5R-9, and what an error or a hash records."""

    def test_white_space_and_other_spellings(self):
        """R5R-1: a no-break or ideographic space as a URL or markup writes
        it; Latin-1; full case folding; named and Windows-1252 references;
        a reference without its ";" where no digit follows."""
        for password, text, found in (
                ("Kq7 vX!p2$Lm9", "http://h/ok/Kq7%C2%A0vX!p2$Lm9/", True),
                ("Kq7 vX!p2$Lm9", "http://h/ok/Kq7%E3%80%80vX!p2$Lm9/", True),
                ("Kq7 vX!p2$Lm9", "Kq7&nbsp;vX!p2$Lm9", True),
                ("Kq7 vX!p2$Lm9", "Kq7&#160;vX&excl;p2&dollar;Lm9", True),
                ("Kq7 vX!p2$Lm9", "Kq7&#xA0vX&#33p2$Lm9", True),
                ("Kq7 vX!p2$Lm9", "Kq7 vX&#331p2$Lm9", False),
                ("Kq7 vX!p2$Lm9", "Kq7vX!p2$Lm9", False),
                ("P\u00e4sswort!2026x", "/ok/P%E4sswort!2026x/", True),
                ("P\u00e4sswort!2026x", "P&auml;sswort!2026x", True),
                ("P\u00e4sswort!2026x", "P&aumlsswort!2026x", True),
                ("Stra\u00dfe-9Kq!x", "STRASSE-9KQ!X", True),
                ("Euro\u20ac-9Kq!x", "Euro&#128;-9Kq!x", True),
                ("Euro\u20ac-9Kq!x", "Euro&euro;-9Kq!x", True),
                ("a\tb\tc\td", "a&Tab;b&#9c%09d", True)):
            with self.subTest(password=password, text=text):
                self.assertEqual(cli._password_in(password, [text]), found)
                if found:
                    left = cli._without_password(text, password)
                    self.assertIn("REDACTED", left)
                    self.assertFalse(cli._password_in(password, [left]))

    def test_a_redirect_to_the_password_with_a_no_break_space(self):
        """R5R-1, end to end: refused, and nothing records or prints it."""
        from tests.test_fetch_hardening import _Site, send

        def moved(h):
            h.send_response(302)
            h.send_header("Location", "/ok/Kq7%C2%A0vX!p2$Lm9/")
            h.send_header("Content-Length", "0")
            h.end_headers()
        site = _Site({"/r": moved, "/ok/Kq7%C2%A0vX!p2$Lm9/": send(
            PAGE.format("<p>x</p>").encode())})
        self.addCleanup(site.stop)
        d = tmpdir(self)
        (d / "pw").write_text("Kq7\u00a0vX!p2$Lm9", encoding="utf-8")
        code, out, err = run("--url", f"{site.base}/r", "--no-render",
                             "--http-user", "u", "--http-password-file",
                             d / "pw", "--json", d / "r.json", "--bundle",
                             d / "b.json", "--fail-on", "never")
        self.assertEqual(code, 2, err)
        self.assertIn("holds the --http-user password", err)
        self.assertFalse((d / "b.json").exists())
        self.assertNotIn("p2$lm9", ((d / "r.json").read_text() + out + err)
                         .lower())

    def test_no_locator_anchors_on_the_password(self):
        """R5R-2: an id that holds it in another case is no anchor; as CSS
        escapes write it, a step would not be found to hold it."""
        from bellbriar_harness import redact as R
        token = R.set_run_secrets(passwords=["Zephyr!Quill.4471"])
        try:
            page = run_page(
                '<!doctype html><html lang="en"><head><title>T</title></head>'
                '<body><main><h1>Shop</h1><div id="zephyr!quill.4471"><a '
                'href="/cart"></a></div></main></body></html>', "t.html", RB)
        finally:
            R.reset_run_secrets(token)
        steps = [s for r in page.results if r.rule_id == "bb-link-name"
                 for f in r.findings for s in f.selector or ()]
        self.assertTrue(steps)
        self.assertNotIn("quill", " ".join(steps).lower())

    def test_white_space_at_its_ends_stays_linear(self):
        """R5R-5."""
        from bellbriar_harness import redact as R
        for password in (" Zephyr-Quill-4471", "Zephyr-Quill-4471 "):
            pattern = R.password_pattern(password)
            start = time.monotonic()
            for run_of in ("%20", "&#32;", " ", "&nbsp;"):
                pattern.search('<a href="/x' + run_of * 20000 + 'y">')
            self.assertLess(time.monotonic() - start, 5, password)

    def test_a_long_value_keeps_its_explanation(self):
        """R5R-6: a value a rendered-run message quotes is cut, its words
        kept; one that holds the password withholds the message."""
        from bellbriar_harness import axe as A
        from bellbriar_harness import redact as R
        from tests.test_rendered_rules import (P, attr, findings, mark,
                                               rerun, run_record, snapshot)
        said = mark(("valid-lang", "fail", "serious", "Value of lang "
                     "attribute not included in the list of valid languages"))
        others = sorted(set(A.AXE_RULES.values()) - {"valid-lang"})
        for value, password in (("x" * 750, None),
                                ("fr-Zephyr-Quill-4471", "Zephyr-Quill-4471")):
            with self.subTest(password=password):
                html = snapshot(f'<p xml:lang="{value}"{attr(P + "-axe", said)}'
                                '>Bonjour</p>', root=attr(P + "-axe-run",
                                run_record(["valid-lang"], others)))
                token = R.set_run_secrets(
                    passwords=[password] if password else [])
                try:
                    got = findings(rerun(html), "bb-element-lang")
                finally:
                    R.reset_run_secrets(token)
                self.assertEqual(len(got), 1)
                if password is None:
                    self.assertIn('xml:lang="' + "x" * 39 + '\u2026" is not a '
                                  "valid language tag", got[0].message)
                else:
                    self.assertEqual(got[0].message, R.WITHHELD_MESSAGE)

    def test_the_harness_words_as_read(self):
        """R5R-7: the rulebook's strings as JSON reads them, and axe-core's
        with their escapes read."""
        self.assertTrue(cli._in_own_words("Element's default"))
        self.assertTrue(cli._in_own_words('div role="checkbox"'))

    def test_a_password_that_is_not_utf8(self):
        """R5R-9: refused, and no byte of it quoted."""
        import argparse
        args = argparse.Namespace(http_user="u", http_password_file=None)
        with mock.patch.dict(os.environ,
                             {cli.HTTP_PASSWORD_ENV: "P\udce4sswort!2026x"}):
            with self.assertRaises(ValueError) as caught:
                cli._http_credentials(args)
        self.assertEqual(str(caught.exception),
                         "$BELLBRIAR_HTTP_PASSWORD is not UTF-8 text")

    def test_an_error_records_no_secret(self):
        """A rule's exception may quote the page: the run's secrets are
        replaced in it, and one that holds the password is withheld."""
        from bellbriar_harness import engine
        from bellbriar_harness import redact as R
        token = R.set_run_secrets(secrets=["tok_9f8e7d6c5b4a3928"],
                                  passwords=["Zephyr-Quill-4471"])
        try:
            said = engine.error_text(ValueError("bad zephyr-QUILL-4471 here"))
            other = engine.error_text(ValueError("bad tok_9f8e7d6c5b4a3928"))
        finally:
            R.reset_run_secrets(token)
        self.assertTrue(said.startswith("ValueError: (message withheld"), said)
        self.assertNotIn("quill", said.lower())
        self.assertEqual(other, "ValueError: bad REDACTED")

    def test_a_hash_holds_no_password(self):
        """An element's `about` hashes it with the run's password replaced,
        its text read past the cut for it: two passwords give one hash, so
        a hash tests no guess."""
        from bellbriar_harness import redact as R
        from bellbriar_harness.checks_static import (PageContext,
                                                     element_identity)

        def abouts(password):
            ctx = PageContext.parse(
                '<!doctype html><html lang="en"><head><title>T</title></head>'
                f'<body><a id="a" href="/y?k={password}"></a><p id="p">'
                f'{"w" * 195} {password}</p><div id="d"><img src="/{password}'
                '.png"></div></body></html>', path="t.html")
            token = R.set_run_secrets(passwords=[password])
            try:
                return [element_identity(ctx.soup.find(id=i)) for i in "apd"]
            finally:
                R.reset_run_secrets(token)
        first = abouts("Zephyr Quill 4471")
        self.assertEqual(first, abouts("Other Pass 99x"))
        self.assertNotIn("", first)


class TestGuardRound9(unittest.TestCase):
    """R5R-4: a key pair's 64 bytes as \\u00XX escapes, after a short
    string on its line."""

    def test_a_key_pair_as_unicode_escapes(self):
        import repo_guard
        from cryptography.hazmat.primitives.asymmetric import ed25519
        for k in range(8):
            seed = hashlib.sha256(b"bellbriar R5R probe %d" % k).digest()
            pair = seed + ed25519.Ed25519PrivateKey.from_private_bytes(
                seed).public_key().public_bytes_raw()
            for written in (TestGuardRound8.js(pair, True),
                            "".join("\\u%04x" % b for b in pair)):
                with self.subTest(k=k, all_escaped=written.count("\\") == 64):
                    d = TestGuardRound7.keyed(self, seed)
                    (d / "k.js").write_text('console.log("Key:", sign(data, "'
                                            + written + '"));\n')
                    self.assertTrue(repo_guard.check(d))


class TestNamesRound9(unittest.TestCase):
    """R5R-3, R5R-8, R5S-1 to R5S-5, R5S-8, R5S-9: names and skipping as
    Chromium 141 computes them (each case checked there)."""

    names = TestRulesRound3.names
    found = staticmethod(TestRulesRound2.found)
    page = TestRulesRound2.page

    def main(self, body, head=""):
        return self.page(f"<main><h1>x</h1>{body}</main>", head=head)

    def test_a_label_leaves_out_its_own_control(self):
        """R5S-5: a <select>'s options, a <textarea>'s text and a
        <button>'s words are not their own label; the label's title is
        read when its content gives nothing."""
        cases = (
            ('<label><select id="x"><option>Choose a country</option><option>'
             'France</option></select></label>', ""),
            ('<label><textarea id="x">Hello</textarea></label>', ""),
            ('<label title="Tt"><select id="x"><option>Opt</option></select>'
             '</label>', "Tt"),
            ('<label title="Tt"><textarea id="x">Val</textarea></label>', "Tt"),
            ('<label title="Tt"><button id="x">Go</button></label>', "Tt"),
            ('<label>Qty <input id="x"> <select><option>kg</option></select>'
             '</label>', "Qty kg"),
            ('<label for="x">Size <select><option>XL</option></select></label>'
             '<input id="x">', "Size XL"),
            ('<label><span>Pick</span> <select id="x"><option>One</option>'
             '</select></label>', "Pick"),
        )
        for body, want in cases:
            with self.subTest(body=body[:60]):
                self.assertEqual(self.names(self.main(body), "x"), {"x": want})
        self.assertEqual(self.found(self.main(
            '<label><select><option>Choose a country</option></select>'
            '</label>'), "bb-control-label"), (True, [(FAIL, "blocker")]))

    def test_fields_of_other_namespaces(self):
        """R5S-4: an <input>, <select> or <textarea> of MathML or of a
        drawing is no field."""
        self.assertEqual(self.found(self.main(
            '<math><input></input></math><svg><input></input><textarea>'
            '</textarea></svg>'), "bb-control-label"), (False, []))
        html = self.main('<label>Name <math><input></input></math> <input '
                         'id="x"></label>')
        self.assertEqual(self.names(html, "x"), {"x": "Name"})
        self.assertEqual(self.found(html, "bb-control-label"), (True, []))

    def test_details_and_marquee_hold_a_block(self):
        """R5S-8: what a <details> holds but its first <summary>, and what
        a <marquee> holds, sit in a block box whatever their display; the
        first summary is placed by the details' own."""
        from bellbriar_harness import style
        from bellbriar_harness.checks_static import PageContext
        cases = (
            ('<details open style="display:flex"><summary id="a" style="'
             'display:inline">S</summary><summary id="b" style="display:'
             'inline">S</summary><span id="c">x</span></details>',
             ("block", "inline", "inline")),
            ('<div style="display:flex"><details open style="display:'
             'contents"><summary id="a" style="display:inline">S</summary>'
             '<summary id="b" style="display:inline">S</summary><span id="c">'
             'x</span></details></div>', ("block", "inline", "inline")),
            ('<div><details open style="display:contents"><summary id="a" '
             'style="display:inline">S</summary><span id="b">x</span><span '
             'id="c">x</span></details></div>', ("inline", "inline", "inline")),
            ('<div style="display:flex"><marquee style="display:contents">'
             '<span id="a">S</span><span id="b">S</span><span id="c">x</span>'
             '</marquee></div>', ("inline", "inline", "inline")),
            ('<marquee style="display:grid"><span id="a">S</span><span id="b"'
             '>S</span><span id="c">x</span></marquee>',
             ("inline", "inline", "inline")),
        )
        for body, want in cases:
            for reader in ("html", "dom"):
                with self.subTest(body=body[:50], reader=reader):
                    ctx = PageContext.parse(self.main(body), path="t.html",
                                            reader=reader)
                    self.assertEqual(tuple(style._display_of(ctx.soup.find(
                        id=i)) for i in "abc"), want)
        self.assertEqual(self.found(self.main(
            '<details open style="display:flex"><summary>S</summary><span '
            'hidden="until-found"><a href="/x"></a></span></details>'),
            "bb-link-name"), (True, [(FAIL, "blocker")]))

    def test_deep_pages_remember_no_guess(self):
        """R5S-3: the display walk has no cap, so nothing is remembered
        from a parent it could not read."""
        body = ('<p>' + '<x-a hidden="until-found"><template shadowrootmode='
                '"open">' * 1200 + '<a href="/x"></a>' + '</template></x-a>'
                * 1200 + '</p>')
        self.assertEqual(self.found(self.main(body), "bb-link-name"),
                         (True, [(FAIL, "blocker")]))
        xhtml = ('<?xml version="1.0" encoding="UTF-8"?><html xmlns="http://'
                 'www.w3.org/1999/xhtml" lang="en" xml:lang="en"><head><title>'
                 'T</title></head><body><main><h1>x</h1><p>' + '<span hidden='
                 '"until-found">' * 1200 + '<a href="/x"></a>' + '</span>'
                 * 1200 + '</p></main></body></html>')
        self.assertEqual(self.found(xhtml, "bb-link-name", path="t.xhtml"),
                         (True, [(FAIL, "blocker")]))

    def test_a_visibility_known_later_in_a_name(self):
        """R5S-9: read as the parent's where it decides whether text names
        anything (and as shown where it decides whether an element is
        evaluated at all: R5Q-4)."""
        self.assertEqual(self.found(self.main(
            '<a href="/x"><span style="visibility:hidden">Cart <b style="'
            'visibility:var(--v)">X</b></span></a>'), "bb-link-name"),
            (True, [(FAIL, "blocker")]))

    def test_a_closed_details_shows_its_first_summary_only(self):
        """R5S-1, R5S-2: found once per <details>; a heading in a later
        summary opens no content."""
        nav = ('<nav><a href="/a">A</a> <a href="/b">B</a> <a href="/c">C</a>'
               '</nav>')
        for inside in ("<summary><h1>Welcome</h1></summary>",
                       "<div><h1>Welcome</h1></div>"):
            with self.subTest(inside=inside):
                self.assertEqual(self.found(self.page(
                    f"{nav}<details><summary>More</summary>{inside}</details>"
                    "<p>Body text</p>"), "bb-skip-link"),
                    (True, [(FAIL, "serious")]))
        start = time.monotonic()
        run_page(self.main("<details>" + '<a href="/x"></a>' * 16000
                           + "</details>"), "t.html", RB)
        self.assertLess(time.monotonic() - start, 15)

    def test_an_older_record_of_a_value(self):
        """R5R-8: a <textarea>'s text is its value, whatever an older
        capture marked."""
        from bellbriar_harness.model import hidden_attr
        from tests.test_rendered_rules import P, findings, rerun
        mark = hidden_attr(P)
        html = (f'<!doctype html><html lang="en" {mark}="recorded"><head>'
                '<title>T</title></head><body><main><h1>T</h1><a href="/t">'
                f'<textarea {mark}="skips">Cart</textarea></a><a href="/u">'
                f'<span {mark}="skips">Cart</span></a></main></body></html>')
        got = findings(rerun(html), "bb-link-name")
        self.assertEqual([f.verdict for f in got], [FAIL])
        self.assertIn('href="/u"', got[0].snippet)

    @unittest.skipUnless(HAVE_BROWSER, _WHY)
    def test_a_drawings_parts_in_a_browser(self):
        """R5R-3, end to end: a <g> or a <text> that skips what it holds,
        by a stylesheet only the capture reads, names nothing."""
        site = _echo_site(self, lambda t: PAGE.format(
            "<style>.s{content-visibility:hidden}</style>"
            '<button id="h1" aria-labelledby="h1t"></button><svg id="h1t" '
            'width="80" height="20"><g class="s"><text y="15">Save</text></g>'
            '</svg><button id="h5" aria-labelledby="h5t"></button><svg width='
            '"80" height="20"><text id="h5t" y="15" class="s">Save</text>'
            '</svg><button id="ok" aria-labelledby="okt"></button><svg width='
            '"80" height="20"><text id="okt" y="15">Save</text></svg>'))
        d = tmpdir(self)
        code, _out, err = run("--url", f"{site.base}/p", "--json",
                              d / "r.json", "--fail-on", "never")
        self.assertEqual(code, 0, err)
        report = json.loads((d / "r.json").read_text())
        failed = [f["snippet"] for p in report["pages"]
                  for f in p["findings"] if f["verdict"] == "fail"
                  and f["rule_id"] == "bb-button-name"]
        self.assertTrue(any('id="h1"' in s for s in failed), failed)
        self.assertTrue(any('id="h5"' in s for s in failed), failed)
        self.assertFalse(any('id="ok"' in s for s in failed), failed)


class TestOwnStyleRound9(unittest.TestCase):
    """R5S-7: a media query on a feature Chromium 141 does not know, or on
    a value only known later, holds nowhere (each case checked there, at
    1280 pixels; `not ((min-width:1px) and foo(1))` holds 0 pixels wide,
    as false and unknown is false: R6B-5)."""

    found = staticmethod(TestRulesRound2.found)
    page = TestRulesRound2.page
    NEVER = ("not (foo(1))", "screen and (foo(1))",
             "(min-width: var(--bp))",
             "not (min-width: var(--bp))",
             "(prefers-reduced-data: no-preference)", "(foo: 1)",
             "(min-width:1px) and (foo:1)", "(dynamic-range)",
             "(width > env(safe-area-inset-left))", "(min-width: foo(1px))",
             "(width > foo(1px))", "(foo(1) < width)")
    MAY = ("(min-width:1px)", "(width >= 1px)", "(400px <= width <= 20000px)",
           "(hover: hover)", "(-webkit-min-device-pixel-ratio: 1)",
           "(min-width:1px) or (foo:1)", "(dynamic-range: standard)",
           "(min-aspect-ratio: 1/1)", "((min-width: 1px))",
           "(calc(1px) < width)", "(min-width: clamp(1px, 2px, 3px))",
           "not ((min-width:1px) and foo(1))")

    def test_each_query(self):
        for query in self.NEVER + self.MAY:
            with self.subTest(query=query):
                self.assertEqual(self.found(self.page(
                    '<main><h1>x</h1><a href="/x"><span class="lbl">Cart</span>'
                    '</a></main>', head="<style>:root{--bp:10px} .lbl{display:"
                    f"none}} @media {query}{{.lbl{{display:inline}}}}</style>"),
                    "bb-link-name"),
                    (True, [(FAIL, "blocker")] if query in self.NEVER else []))

    def test_a_custom_property_in_supports(self):
        """Its value holds no ";" or "!" of its own (`!important`, in any
        case, is no part of it): Chromium 141 fails such a test."""
        for test, holds in (("(--x: a;b)", False), ("(--x: ;)", False),
                            ("(--x: a!b)", False), ("(--x: \"a;b\")", True),
                            ("(--x: (a;b))", True), ("(--x: a !IMPORTANT)", True),
                            ("(display: block !IMPORTANT)", True)):
            with self.subTest(test=test):
                self.assertEqual(self.found(self.page(
                    '<main><h1>x</h1><a href="/x"><span class="lbl">Cart</span>'
                    '</a></main>', head="<style>.lbl{display:none} @supports "
                    f"{test}{{.lbl{{display:inline}}}}</style>"),
                    "bb-link-name"),
                    (True, [] if holds else [(FAIL, "blocker")]))


class TestStringsAndBracketsRound9(unittest.TestCase):
    """A ";" or a brace inside a string or brackets ends and opens nothing,
    in a style attribute or a <style> rule, as Chromium 141 reads them
    (each case checked there)."""

    names = TestRulesRound3.names
    page = TestRulesRound2.page

    def test_each_case(self):
        link = '<a id="x" href="/x"><span class="lbl"{}>Cart</span></a>'
        for attrs, style, want in (
                (""" style='content:"x;display:none;"'""", "", "Cart"),
                (' style="background:url(data:x;display:none)"', "", "Cart"),
                (' style="--a:(x;y);display:none"', "", ""),
                ("", ".lbl{display:none; --x: (}); display:inline}", "Cart"),
                ("", ".lbl{display:none} @supports (--x: {a}) {.lbl{display:"
                 "inline}}", "Cart"),
                ("", ".lbl{display:none} @supports (--x: (a;b)) {.lbl{display:"
                 "inline}}", "Cart"),
                ("", ".lbl{display:none; --x: [;}]; display:inline}", "Cart"),
                ("", '.lbl{content:"a;display:none;"}', "Cart"),
                (' data-x="a;b"', '.lbl{display:none} [data-x="a;b"] {display:'
                 "inline}", "Cart")):
            with self.subTest(attrs=attrs, style=style):
                self.assertEqual(self.names(self.page(
                    "<main><h1>x</h1>" + link.format(attrs) + "</main>",
                    head=f"<style>{style}</style>"), "x"), {"x": want})


class TestRulesRound9(unittest.TestCase):
    """The README's media sentence and the docs' password spellings say
    what the code does."""

    def test_the_docs(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("a feature Chromium\n141 does not know", readme)
        for doc in ("README.md", "docs/EVIDENCE.md",
                    "docs/MEASUREMENT-AND-EVIDENCE-GUIDE.md"):
            text = " ".join((ROOT / doc).read_text(encoding="utf-8").split())
            with self.subTest(doc=doc):
                self.assertIn("percent-encoded (UTF-8, or Latin-1)", text)
                self.assertNotIn("in any spelling markup or a URL", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
