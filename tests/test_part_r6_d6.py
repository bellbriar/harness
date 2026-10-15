"""Part R, stage 6: the decisions of October 13 (D6, and R5's open ones).

  L93   a bundle's records stay open; verify and inspect say how many
        members a release does not write, and where (never their names),
        and name a coverage note or layer records not its own, the
        verdict unchanged.
  L96   a file's name that only looks like a site's, which a run writes
        after "./", is malformed without it (test_canonicalization holds
        the cases for both verifiers).
  L97   inspect exits 2 where verify would refuse the bundle as malformed.
  L53   a capture records its Chromium on the snapshot's root, and a
        re-run records it in tool.from_snapshot.
  L106  a capture records the version of its marks there too, and a
        re-run of a snapshot without this release's is not evaluated.
  L79   a path parameter's value (;jsessionid=...) is REDACTED as a
        query value is.
  L104  a form field named only by its title past a <label> that names
        it nothing, which Chromium 141 reads in the title's place, is a
        minor review (measured in Chromium 141 and axe-core 4.12).
"""
from __future__ import annotations

import contextlib
import functools
import http.server
import io
import itertools
import json
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bellbriar_harness import bundle as B                          # noqa: E402
from bellbriar_harness import cli                                  # noqa: E402
from bellbriar_harness import coverage_text as CT                  # noqa: E402
from bellbriar_harness import engine as E                          # noqa: E402
from bellbriar_harness import evidence_cli                         # noqa: E402
from bellbriar_harness import fetch as F                           # noqa: E402
from bellbriar_harness import redact as R                          # noqa: E402
from bellbriar_harness.axe import AXE_VERSION                      # noqa: E402
from bellbriar_harness.checks_rendered import RENDERED_CHECKS      # noqa: E402
from bellbriar_harness.engine import load_rulebook, run_page       # noqa: E402
from bellbriar_harness.model import (MARKS_VERSION, MINOR,         # noqa: E402
                                     MODERATE, NEEDS_REVIEW,
                                     PageResult, RuleResult)
from tests.test_fetch_hardening import HAVE_BROWSER, _WHY          # noqa: E402

FIXTURES = ROOT / "fixtures"
RB = load_rulebook()
ATTR = "data-bb-p-0123456789abcdef"


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = cli.main([str(a) for a in argv])
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


def evidence(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = evidence_cli.main([str(a) for a in argv])
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue() + err.getvalue()


def tmpdir(test) -> Path:
    d = Path(tempfile.mkdtemp(prefix="bb-d6-"))
    test.addCleanup(shutil.rmtree, d, True)
    return d


def page(body, head=""):
    return ('<!doctype html><html lang="en"><head><title>T</title>'
            f'{head}</head><body><main><h1>T</h1>{body}</main></body></html>')


def signed(bundle):
    priv, pub, _kid = B.generate_keypair()
    return B.sign_bundle_local(bundle, priv), pub


# ---------------------------------------------------------------------------
# L93: what a release does not write, said and never refused
# ---------------------------------------------------------------------------

class TestWhatThisReleaseDoesNotWrite(unittest.TestCase):

    def file_bundle(self):
        d = tmpdir(self)
        code, out, err = run(FIXTURES / "good.html", "--bundle", d / "b.json")
        self.assertEqual(code, 0, out + err)
        return json.loads((d / "b.json").read_text(encoding="utf-8"))

    def test_a_bundle_this_release_made_holds_nothing_else(self):
        bundle = self.file_bundle()
        self.assertEqual(B.not_this_release(bundle), [])
        ok, reason = B.verify_bundle(*signed(bundle))
        self.assertTrue(ok, reason)
        self.assertNotIn("does not write", reason)

    def test_members_are_counted_and_placed_never_quoted(self):
        bundle = self.file_bundle()
        bundle["site"]["certification"] = "Certified by Bellbriar"
        bundle["tool"]["Certified_WCAG_conformant"] = True
        bundle["pages"][0]["auditor_note"] = "Reviewed and approved"
        if bundle["pages"][0]["findings"]:
            bundle["pages"][0]["findings"][0]["approved"] = True
        ok, reason = B.verify_bundle(*signed(bundle))
        self.assertTrue(ok, reason)            # said, never refused
        self.assertIn("does not write (another release's, or added or "
                      "edited), which is the word of whoever made the "
                      "bundle", reason)
        self.assertIn("in tool, site and pages[0]", reason)
        for words in ("certification", "Certified", "auditor_note",
                      "approved", "Reviewed"):
            self.assertNotIn(words, reason)
        count, places = B.foreign_members(bundle)
        self.assertEqual(places[:3], ["tool", "site", "pages[0]"])
        self.assertEqual(count, len(places))

    def test_texts_not_this_releases(self):
        bundle = self.file_bundle()
        bundle["coverage_note"] = ("This run covers every layer. The site "
                                   "is certified WCAG 2.1 AA conformant.")
        layers = bundle["layers"]
        layers[1] = dict(layers[1], status="executed")
        layers.append({"layer": "certification", "status": "executed",
                       "note": "Passed."})
        del layers[4]                          # the judge's
        ok, reason = B.verify_bundle(*signed(bundle))
        self.assertTrue(ok, reason)
        self.assertIn("its coverage note", reason)
        self.assertIn("the record of its accessibility-tree layer", reason)
        self.assertIn("1 layer record of no layer this release has", reason)
        self.assertIn("a list of layers without the judge layer", reason)
        self.assertNotIn("certification", reason)

    def test_inspect_says_so_too(self):
        bundle = self.file_bundle()
        bundle["site"]["certification"] = "x"
        d = tmpdir(self)
        (d / "b.json").write_text(json.dumps(bundle), encoding="utf-8")
        code, out = evidence("inspect", d / "b.json")
        self.assertEqual(code, 0, out)
        self.assertIn("NOTE        it holds what bellbriar-harness", out)
        self.assertIn("1 member it does not define (in site)", out)

    def test_inspect_exits_as_verify_does_on_a_malformed_bundle(self):
        """L97."""
        bundle = self.file_bundle()
        d = tmpdir(self)
        for name, broken in (
                ("member", dict(bundle, certified="yes")),
                ("signature", dict(bundle, signature="VALID")),
                ("lookalike", dict(bundle, pages=[
                    dict(bundle["pages"][0],
                         path="\u3164https://bank.example/")]))):
            with self.subTest(name):
                (d / "b.json").write_text(json.dumps(broken),
                                          encoding="utf-8")
                code, out = evidence("inspect", d / "b.json")
                self.assertEqual(code, 2, out)
                self.assertIn("malformed bundle", out)

    def test_every_coverage_note_and_layer_note_the_engine_writes(self):
        """The patterns know every text engine.coverage_sentence,
        engine.layer_records and cli._coverage_note write."""
        self.assertEqual(CT.AXE_RULES, len(RENDERED_CHECKS) - 1)
        axe_rules = [r for r in RENDERED_CHECKS if r != E.REFLOW_RULE]

        def make(kind):
            p = PageResult(path="p.html")
            if kind == "unread":
                p.parse_error = "ValueError: x"
                return p
            if kind in ("axe", "short", "both", "snap", "hidden", "wide"):
                ids = axe_rules if kind != "short" else axe_rules[:3]
                if kind == "hidden":
                    ids = axe_rules[:2]
                    p.axe_unread = "hidden root"
                p.results += [RuleResult(r, True) for r in ids]
                p.axe_version = ("4.11.0" if kind == "snap" else AXE_VERSION)
                p.axe_from_snapshot = kind == "snap"
            if kind in ("reflow", "both", "wide"):
                p.results.append(RuleResult(E.REFLOW_RULE, True))
            p.narrow = kind != "wide"
            return p

        kinds = ("unread", "static", "axe", "short", "both", "snap",
                 "hidden", "reflow", "wide")
        seen = 0
        for n in (1, 2, 3):
            for combo in itertools.product(kinds, repeat=n):
                pages = [make(k) for k in combo]
                note = E.coverage_sentence(pages)
                self.assertTrue(CT.coverage_note_known(note), note)
                self.assertEqual(CT.layer_problems(E.layer_records(pages)),
                                 [], (combo, E.layer_records(pages)))
                for modes in itertools.product(("rendered", "static", None),
                                               repeat=n):
                    caps = [None if m is None else SimpleNamespace(mode=m)
                            for m in modes]
                    for build in (False, True):
                        full = cli._coverage_note(pages, caps, build)
                        self.assertTrue(CT.coverage_note_known(full), full)
                        seen += 1
        self.assertGreater(seen, 10000)
        # And none of these is one.
        for note in ("", E.COVERAGE_SENTENCE + " Certified.",
                     E.COVERAGE_SENTENCE.replace("NOT ", ""),
                     E.NOTHING_READ_SENTENCE + E.SERVER_ONLY_SENTENCE,
                     None, 7, "x" * 9000):
            self.assertFalse(CT.coverage_note_known(note), note)


@unittest.skipUnless(HAVE_BROWSER, _WHY)
class TestRenderedBundlesHoldNothingElse(unittest.TestCase):
    """A --render run, a URL run and a re-run of its snapshot each make a
    bundle that holds nothing this release does not write (L93), and the
    re-run records the Chromium the capture names (L53)."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        d = Path(cls.tmp.name)
        site = d / "site"
        site.mkdir()
        (site / "index.html").write_text(page(
            '<p>Home</p><a href="/two.html">Two</a>'), encoding="utf-8")
        (site / "two.html").write_text(page(
            '<p>Two</p><button></button>'), encoding="utf-8")
        class Handler(http.server.SimpleHTTPRequestHandler):
            # A server that keeps a session in the path (;jsessionid=).
            def translate_path(self, path):
                return super().translate_path(path.split(";", 1)[0])

            def log_message(self, *a):
                pass
        handler = functools.partial(Handler, directory=str(site))
        cls.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"
        cls.render = run(site, "--render", "--bundle", d / "render.json")
        cls.url = run("--url", base + "/index.html;jsessionid=AB12CD34EF",
                      "--url", base + "/two.html", "--save-snapshots",
                      d / "snaps", "--bundle", d / "url.json",
                      "--json", d / "url-report.json")
        report = json.loads((d / "url-report.json").read_text())
        rec = report["pages"][0]["fetch"]
        snaps = sorted((d / "snaps").iterdir())
        # Each capture has its own name: the first page's snapshot alone.
        cls.rerun = run(snaps[0], "--provenance-attr",
                        rec["provenance_attr"], "--read-as", "dom",
                        "--bundle", d / "rerun.json")
        cls.both = run(*snaps, "--provenance-attr", rec["provenance_attr"],
                       "--read-as", "dom")
        cls.dir = d
        cls.rec = rec

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.tmp.cleanup()

    def bundle(self, name):
        return json.loads((self.dir / name).read_text(encoding="utf-8"))

    def test_each_holds_nothing_else(self):
        for name, result in (("render.json", self.render),
                             ("url.json", self.url),
                             ("rerun.json", self.rerun)):
            with self.subTest(name):
                self.assertIn(result[0], (0, 1), result[1] + result[2])
                bundle = self.bundle(name)
                self.assertEqual(B.not_this_release(bundle), [])
                ok, reason = B.verify_bundle(*signed(bundle))
                self.assertTrue(ok, reason)
                self.assertNotIn("does not write", reason)

    def test_another_captures_snapshot_is_not_read_under_this_name(self):
        """L106: its record is under its own capture's name."""
        code, out, err = self.both
        self.assertEqual(code, 2, out + err)
        self.assertIn("holds no capture record under the name given", err)

    def test_the_re_run_records_the_capturing_chromium(self):
        """L53."""
        tool = self.bundle("rerun.json")["tool"]
        self.assertEqual(tool["from_snapshot"]["chromium"],
                         self.rec["browser"]["version"])
        self.assertEqual(tool["from_snapshot"]["axe-core"], AXE_VERSION)

    def test_a_path_parameter_is_redacted_in_the_record(self):
        """L79: the session id in the path is not recorded."""
        bundle = self.bundle("url.json")
        text = json.dumps(bundle)
        self.assertNotIn("AB12CD34EF", text)
        paths = [p["path"] for p in bundle["pages"]]
        self.assertTrue(any(p.endswith("/index.html;jsessionid=REDACTED")
                            for p in paths), paths)
        self.assertIn("path", bundle["pages"][0]["fetch"]["redacted"])


# ---------------------------------------------------------------------------
# L106, L53: the capture's own record
# ---------------------------------------------------------------------------

class TestTheCaptureRecord(unittest.TestCase):

    def test_it_goes_on_the_root(self):
        html = (f'<!doctype html><html {ATTR}="server" lang="en"><head '
                f'{ATTR}="server"></head><body {ATTR}="server"></body></html>')
        placed = F.place_capture_record(html, ATTR, "141.0.7390.37")
        self.assertTrue(placed.startswith(
            f'<!doctype html><html {ATTR}-capture="'))
        self.assertEqual(placed.count(f"{ATTR}-capture="), 1)
        # A record the page wrote under that name first goes.
        forged = html.replace("<body", f'<body {ATTR}-capture="x"')
        self.assertEqual(F.place_capture_record(forged, ATTR, "1").count(
            f"{ATTR}-capture="), 1)
        # No provenance attribute: no record.
        self.assertEqual(F.place_capture_record("<html></html>", ATTR, "1"),
                         "<html></html>")

    def snapshot_run(self, root_attr):
        d = tmpdir(self)
        html = page('<a href="/x">Go</a>').replace(
            '<html lang="en"', f'<html lang="en" {ATTR}="server"{root_attr}')
        (d / "s.html").write_text(html, encoding="utf-8")
        return E.run_paths([d / "s.html"], RB, provenance_attr=ATTR,
                           reader="dom")

    def test_a_snapshot_without_this_releases_marks_is_not_evaluated(self):
        """L106."""
        for label, root in (
                ("none", ""),
                ("other marks", f" {ATTR}-capture='{{\"browser\":\"1\","
                                f"\"marks\":{MARKS_VERSION + 1}}}'"),
                ("not json", f' {ATTR}-capture="x"')):
            with self.subTest(label):
                result = self.snapshot_run(root)
                p = result["pages"][0]
                self.assertFalse(p.evaluable)
                self.assertTrue(p.parse_error)
                self.assertIn("capture the page again",
                              p.not_evaluable_reason)
                self.assertEqual(p.results, [])
                self.assertEqual(result["coverage_note"],
                                 E.NOTHING_READ_SENTENCE)

    def test_one_with_them_is_read_and_names_its_chromium(self):
        """L53, L106."""
        record = json.dumps({"browser": "141.0.7390.37",
                             "marks": MARKS_VERSION})
        result = self.snapshot_run(f" {ATTR}-capture='{record}'")
        p = result["pages"][0]
        self.assertTrue(p.evaluable, p.not_evaluable_reason)
        self.assertEqual(p.capture_browser, "141.0.7390.37")
        self.assertEqual(result["tool"]["from_snapshot"],
                         {"chromium": "141.0.7390.37"})

    def test_a_fresh_capture_is_not_held_to_it(self):
        """In-process pages of a capture are read as before."""
        got = run_page(page("<p>x</p>").replace(
            '<html lang="en"', f'<html lang="en" {ATTR}="server"'),
            "p.html", RB, provenance_attr=ATTR, reader="dom")
        self.assertTrue(got.evaluable)


# ---------------------------------------------------------------------------
# L79: path parameters
# ---------------------------------------------------------------------------

class TestPathParameters(unittest.TestCase):

    def test_a_recorded_url(self):
        for url, want, removed in (
                ("https://x.test/shop;jsessionid=AB12CD/cart?q=1",
                 "https://x.test/shop;jsessionid=REDACTED/cart?q=REDACTED",
                 {"path", "query"}),
                ("https://x.test/a;b", "https://x.test/a;REDACTED", {"path"}),
                ("https://x.test/p/;v=1;w=2/q",
                 "https://x.test/p/;v=REDACTED;w=REDACTED/q", {"path"}),
                ("https://x.test/a;", "https://x.test/a;", set()),
                ("https://x.test/plain/page", "https://x.test/plain/page",
                 set())):
            with self.subTest(url):
                got, what = R.redact_url(url)
                self.assertEqual(got, want)
                self.assertEqual(set(what), removed)
        self.assertEqual(R.redact_url("https://x.test/a;lang=en",
                                      keep=("lang",))[0],
                         "https://x.test/a;lang=en")

    def test_its_secret_is_scrubbed_elsewhere_and_in_markup(self):
        url = "https://x.test/shop;jsessionid=Zm9vYmFyYmF6cXV4MTIz/cart"
        self.assertIn("Zm9vYmFyYmF6cXV4MTIz", R.secret_values(url))
        self.assertEqual(R._redact_one("/shop;jsessionid=AB12CD/cart"),
                         "/shop;jsessionid=REDACTED/cart")


# ---------------------------------------------------------------------------
# L104: form fields whose <label> names them nothing in Chromium
# ---------------------------------------------------------------------------

#: (field markup, the review: None for none, else its impact), each
#: measured in Chromium 141 (its name) and axe-core 4.12 (label,
#: select-name): every field below with a review has no name in Chromium
#: and passes in axe-core.
_FIELDS = (
    ('<label class="switch"><input type="checkbox" title="Dark mode">'
     '</label>', MINOR),
    ('<label for="f2" style="display:none">Dark</label><input id="f2" '
     'type="checkbox" title="Dark mode">', MINOR),
    ('<label for="f3"></label><input id="f3" type="text" title="Search">',
     MINOR),
    ('<label for="f4"></label><select id="f4" title="Size"><option>S'
     '</option></select>', MINOR),
    ('<label for="f5" aria-hidden="true">Notes</label><textarea id="f5" '
     'title="Notes"></textarea>', MINOR),
    ('<label for="f9"></label><input id="f9" type="text" '
     'placeholder="Search" title="Find">', MINOR),
    ('<label for="f10" style="visibility:hidden">Opt</label><input '
     'id="f10" type="radio" title="Option">', MINOR),
    ('<label for="f11"><img alt="" src="data:,"></label><input id="f11" '
     'type="text" title="City">', MINOR),
    ('<label for="f14" hidden>Volume</label><input id="f14" type="range" '
     'title="Volume">', MINOR),
    ('<label for="f16"> </label><input id="f16" type="number" '
     'title="Qty">', MINOR),
    ('<label for="f18"></label><input id="f18" type="text" '
     'value="Prefilled" title="Code">', MINOR),
    # Named in Chromium too: no review.
    ('<label for="f6">Name</label><input id="f6" type="text" title="x">',
     None),
    ('<label for="f7" hidden>Name</label><input id="f7" type="text" '
     'title="Search" aria-label="Find">', None),
    ('<label for="f12"></label><label for="f12">Mail</label><input '
     'id="f12" type="email" title="x">', None),
    ('<span id="l15">Zip</span><label for="f15"></label><input id="f15" '
     'type="text" aria-labelledby="l15">', None),
)


class TestFieldsWhoseLabelNamesThemNothing(unittest.TestCase):

    def findings(self, body):
        got = run_page(page(body), "t.html", RB)
        return [f for r in got.results if r.rule_id == "bb-control-label"
                for f in r.findings]

    def test_each_measured_field(self):
        for body, impact in _FIELDS:
            with self.subTest(body=body):
                found = self.findings(body)
                if impact is None:
                    self.assertEqual(found, [])
                    continue
                self.assertEqual([(f.verdict, f.impact) for f in found],
                                 [(NEEDS_REVIEW, impact)])
                self.assertIn("not in Chrome or Edge", found[0].message)
                self.assertIn("in place of its title and placeholder",
                              found[0].message)

    def test_a_placeholder_alone_says_so(self):
        for body in ('<label><input type="text" placeholder="Search">'
                     '</label>',
                     '<label for="f17" style="display:none">Hidden</label>'
                     '<input id="f17" type="text" placeholder="Hint">'):
            with self.subTest(body=body):
                found = self.findings(body)
                self.assertEqual([(f.verdict, f.impact) for f in found],
                                 [(NEEDS_REVIEW, MODERATE)])
                self.assertIn("so there it has no name at all (L104)",
                              found[0].message)
        # One with no <label> at all says nothing of one.
        found = self.findings('<input type="text" placeholder="Search">')
        self.assertNotIn("L104", found[0].message)


if __name__ == "__main__":
    unittest.main(verbosity=2)
