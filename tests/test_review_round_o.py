"""Part O: P2-12 (one page or rule must not stop a site run, and an error
is never a pass), the slow spots it found, and P1-13 (review items in
vendor markup are counted apart, as vendor failures were).

  * A rule that raised aborted the whole run: no report, no bundle, and
    nothing about the pages before it. It is now recorded as errored for
    that page (not applicable for the rates; a Tier-1 rule that errored
    leaves the page undecided rather than clean), the other rules and pages
    run, the reports say so, no evidence bundle is written, and the run
    exits 2. A page the harness cannot parse is reported the same way.
  * The page's own <style> rules were each run over the whole document
    (2,000 rules on 8,000 elements: 64 s; now 0.6 s), a control's
    <label for> was found by scanning every label (8,000 fields: 25 s; now
    1.2 s), and every element's ancestors were walked before asking whether
    it could take focus at all.
  * A review item in markup a vendor script injected counted as the
    site's own (needs_review_findings); it is now
    third_party_needs_review_findings, beside third_party_fail_findings.
"""
import io
import json
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bellbriar_harness import checks_static as CS                # noqa: E402
from bellbriar_harness import cli                               # noqa: E402
from bellbriar_harness.engine import load_rulebook, run_page    # noqa: E402
from bellbriar_harness.scoring import score_page, score_site    # noqa: E402

RB = load_rulebook()


def page(body: str, head: str = "") -> str:
    return ('<!doctype html><html lang="en"><head><title>T</title>'
            f'{head}</head><body><main><h1>T</h1>{body}</main></body></html>')


def boom(ctx):
    raise RuntimeError("the rule broke at /home/someone/x")


class TestRuleErrors(unittest.TestCase):
    def test_an_errored_rule_is_never_a_pass(self):
        with mock.patch.dict(CS.CHECKS, {"bb-img-alt": boom}):
            p = run_page(page('<img src="a.png"><a href="/x"></a>'), "x.html", RB)
        bad = [r for r in p.results if r.errored]
        self.assertEqual([r.rule_id for r in bad], ["bb-img-alt"])
        self.assertFalse(bad[0].applicable)
        self.assertIn("RuntimeError: the rule broke", bad[0].errored)
        self.assertNotIn("/home/someone", bad[0].errored)
        # The other rules ran: the empty link still fails.
        self.assertIn("bb-link-name", p.failed_rules())
        s = score_page(p, RB)
        self.assertFalse(s["tier1_clean"])      # decided: a Tier-1 rule failed

    def test_an_errored_tier1_rule_leaves_a_clean_page_undecided(self):
        with mock.patch.dict(CS.CHECKS, {"bb-img-alt": boom}):
            p = run_page(page('<img src="a.png" alt="A">'), "x.html", RB)
        self.assertIsNone(score_page(p, RB)["tier1_clean"])
        self.assertIsNone(score_site([p], RB)["pct_pages_tier1_clean"])

    def test_a_page_that_cannot_be_parsed(self):
        with mock.patch.object(CS.PageContext, "parse",
                               side_effect=ValueError("no")):
            p = run_page("<p>", "x.html", RB)
        self.assertFalse(p.evaluable)
        self.assertEqual(p.errors(), [("(the page)", "ValueError: no")])
        self.assertIn("not a pass", p.not_evaluable_reason)


class TestTheRunReportsItAndExits2(unittest.TestCase):
    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(list(args))
        return code, out.getvalue(), err.getvalue()

    def test_reports_written_bundle_refused(self):
        d = Path(tempfile.mkdtemp())
        (d / "a.html").write_text(page('<img src="a.png" alt="A">'),
                                  encoding="utf-8")
        (d / "b.html").write_text(page("<p>ok</p>"), encoding="utf-8")
        calls = {"n": 0}
        real = CS.CHECKS["bb-img-alt"]

        def first_page_only(ctx):
            calls["n"] += 1
            if calls["n"] == 1:
                raise KeyError("x")
            return real(ctx)
        with mock.patch.dict(CS.CHECKS, {"bb-img-alt": first_page_only}):
            code, out, err = self.run_cli(
                str(d), "--json", str(d / "r.json"), "--html", str(d / "r.html"),
                "--bundle", str(d / "e.json"))
        self.assertEqual(code, 2)
        self.assertIn("bb-img-alt raised on", err)
        self.assertIn("not a pass", err)
        self.assertIn("refusing to write the evidence bundle", err)
        self.assertFalse((d / "e.json").exists())
        report = json.loads((d / "r.json").read_text(encoding="utf-8"))
        errs = [e for p in report["pages"] for e in p["errors"]]
        self.assertEqual([e["rule_id"] for e in errs], ["bb-img-alt"])
        errored = next(p for p in report["pages"] if p["errors"])
        self.assertNotIn("bb-img-alt", errored["not_applicable_rules"])
        self.assertEqual(len(report["pages"]), 2)        # the run went on
        self.assertIn("Incomplete run", (d / "r.html").read_text(encoding="utf-8"))


class TestSlowSpots(unittest.TestCase):
    """Budgets far above today's timings (in brackets) and far below the
    old ones, so a quadratic regression fails here."""

    def timed(self, html) -> float:
        t0 = time.monotonic()
        run_page(html, "x.html", RB)
        return time.monotonic() - t0

    def test_many_style_rules(self):                    # 64 s -> [0.6 s]
        n = 2000
        html = page("".join(f'<div class="c{i}" aria-hidden="true"><a href="/'
                            f'{i}">x</a></div>' for i in range(n)),
                    "<style>" + "".join(f".c{i}{{display:none}} .d{i} .e{i}"
                                        "{visibility:visible}"
                                        for i in range(n)) + "</style>")
        self.assertLess(self.timed(html), 15)

    def test_many_labelled_fields(self):                # 25 s -> [1.2 s]
        html = page("".join(f'<label for="f{i}">F{i}</label><input id="f{i}">'
                            for i in range(8000)))
        self.assertLess(self.timed(html), 12)

    def test_deep_nesting(self):                        # 9 s -> [1.6 s]
        self.assertLess(self.timed(page("<div>" * 32000 + '<a href="/x">'
                                        "</a>")), 12)

    def test_the_bucketed_styles_still_read_the_cascade(self):
        html = page('<div class="menu is-open" aria-hidden="true"><a href="/x">'
                    'Go</a></div><div id="m" class="menu" aria-hidden="true">'
                    '<a href="/y">Go</a></div>',
                    "<style>.menu{display:none}.menu.is-open{display:block}"
                    "</style>")
        p = run_page(html, "x.html", RB)
        got = sorted((f.verdict, f.snippet[:30]) for rr in p.results
                     for f in rr.findings if rr.rule_id == "bb-aria-hidden-focus")
        self.assertEqual([v for v, _ in got], ["fail", "needs_review"])


class TestThirdPartyReviews(unittest.TestCase):
    ATTR = "data-bb-p-0123456789abcdef"

    def test_counted_apart(self):
        a = self.ATTR
        # A placeholder-only field is a moderate review (D4); one sits in
        # the site's markup, one in a vendor's.
        html = (f'<!doctype html><html lang="en" {a}="server" {a}-hidden='
                f'"recorded"><head><title>T</title></head><body {a}="server">'
                f'<main {a}="server"><h1 {a}="server">T</h1>'
                f'<input {a}="server" placeholder="Email">'
                f'<div {a}="third-party:https://chat.vendor.example">'
                f'<input {a}="third-party:https://chat.vendor.example" '
                'placeholder="Ask us"></div></main></body></html>')
        p = run_page(html, "https://site.example/", RB, provenance_attr=a)
        s = score_page(p, RB)
        # the site's field, and the page-level accessibility-statement review
        self.assertEqual(s["needs_review_findings"], 2)
        self.assertEqual(s["third_party_needs_review_findings"], 1)
        site = score_site([p], RB)
        self.assertEqual(site["total_needs_review"], 2)
        self.assertEqual(site["total_third_party_needs_review"], 1)


class TestRenderDeadline(unittest.TestCase):
    """N18: a page whose script never yields hung a --url run forever."""

    def test_only_a_fetch_result_comes_back(self):
        import pickle
        from bellbriar_harness import fetch as F
        good = F.FetchResult(url="http://x.test/", final_url="http://x.test/",
                             mode="rendered", html="<p>")
        got = F._ResultUnpickler.loads(pickle.dumps(("ok", good), protocol=4))
        self.assertEqual(got[1].html, "<p>")

        class Evil:
            def __reduce__(self):
                return (print, ("pwned",))
        with self.assertRaises(pickle.UnpicklingError):
            F._ResultUnpickler.loads(pickle.dumps(("ok", Evil())))

    def test_the_deadline_words_its_own_failure(self):
        from bellbriar_harness import fetch as F
        self.assertEqual(F.render_failure(F.RenderDeadline(15)),
                         "capture: did not finish within 15 s, so the browser"
                         " was stopped (a script on the page may never yield)")


def _live_browsers() -> list[str]:
    import subprocess
    out = subprocess.run(["ps", "-A", "-o", "stat=,comm="],
                         capture_output=True, text=True).stdout
    return [line for line in out.splitlines()
            if "headless" in line.lower() or "chrom" in line.lower()
            if not line.strip().startswith("Z")]


from tests.test_fetch_hardening import HAVE_BROWSER, _WHY, _Site, send  # noqa: E402


@unittest.skipUnless(HAVE_BROWSER, _WHY)
class TestRenderDeadlineInABrowser(unittest.TestCase):
    HANG = (b'<!doctype html><html lang="en"><head><title>T</title></head>'
            b'<body><main><h1>T</h1><a href="/x"></a></main><script>'
            b'setTimeout(function () { while (true) {} }, 50);</script>'
            b'</body></html>')

    def setUp(self):
        self.site = _Site({"/": send(self.HANG)})
        self.addCleanup(self.site.stop)

    def test_a_page_that_never_yields_falls_back_loudly(self):
        from bellbriar_harness import fetch as F
        t0 = time.monotonic()
        fr = F.fetch(self.site.base + "/", render=None, deadline_s=8)
        self.assertLess(time.monotonic() - t0, 40)
        self.assertEqual(fr.mode, "server")
        self.assertIn("did not finish within 8 s, so the browser was stopped",
                      fr.fallback_reason)
        for _ in range(20):                 # the killed browser is gone
            if not _live_browsers():
                break
            time.sleep(0.25)
        self.assertEqual(_live_browsers(), [])

    def test_required_rendering_fails_instead(self):
        from bellbriar_harness import fetch as F
        with self.assertRaises(F.FetchError) as cm:
            F.fetch(self.site.base + "/", render=True, deadline_s=8)
        self.assertIn("did not finish within 8 s", str(cm.exception))

    def test_the_cli_reports_it_and_evaluates_the_server_html(self):
        code, out, err = TestTheRunReportsItAndExits2.run_cli(
            self, "--url", self.site.base + "/", "--render-deadline", "8")
        self.assertEqual(code, 1)           # the empty link fails the gate
        self.assertIn("server HTML only", err)
        self.assertIn("did not finish within 8 s", err)


if __name__ == "__main__":
    unittest.main()
