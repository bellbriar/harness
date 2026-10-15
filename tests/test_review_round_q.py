"""Part Q round 2: fixes from the independent review of Part Q (QR-1 to
QR-14) and of Part P's round-3 fixes (PR4-1).

  QR-1   axe-core results the capture could not place were dropped and the
         rule read as a pass: they are counted under their rule in the
         run's record, reported about the page, never moved onto another
         element, and the results of the rules that can fail are recorded
         first.
  QR-2   content in closed shadow roots axe-core was not given read as
         passing: the capture counts it, and a rule that found no failure
         is then not evaluated on the page.
  QR-3   page code could take a capture of its own and so choose which
         elements the narrow record names: the capture answers only the
         harness's token.
  QR-4   the narrow view read the desktop snapshot's attributes and nodes:
         an element the page removes at phone width is not rendered there,
         and a finding about something the page changed is a review.
  QR-5   a page that hides its horizontal overflow (overflow-x on the root
         or the body) was failed for scrolling sideways, which it cannot.
  QR-6   any exempt element in an overflow made the whole overflow a review:
         only what reaches past the edge decides.
  QR-7   an element's id could switch axe-core off.
  QR-8   the per-page Tier-1 count and the mixed-run coverage clause.
  QR-9   bb-widget-name skipped widgets hidden at capture time.
  QR-10  an SVG element named by its <title> was failed as unnamed.
  QR-11  the documentation of the narrow pass and of the secret names.
  QR-12  a page as large as axe-core is run on fits the render deadline;
         axe-core runs in parts with a time budget; the rules read a page
         once when the narrow record changes nothing.
  QR-13  a link or button given a role another name rule checks was failed
         by both rules.
  QR-14  merging the two views kept the narrow view's error and dropped the
         desktop findings, and merged page-level findings about different
         things.
  QR2    the review of these fixes: a failure the capture's own record shows
         still fails when only the narrow record errored (QR2-1); a page
         without the narrow record is named in the coverage, and a flood of
         changes after the capture makes the narrow-only findings reviews
         rather than turning the narrow record off (QR2-2); a flood between
         axe-core's run and the capture leaves its results counted about the
         page rather than unrecorded (QR2-3); every finding a rule makes
         goes through checks_static._f, which records its element for the
         narrow view (QR2-4).
  PR4-1  a page that navigated to an XML document after it loaded was read
         as HTML.
  Note   a combobox wrapping its text field, and a combobox's popup listbox,
         are minor reviews when unnamed (L49).
"""
import io
import json
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bellbriar_harness import axe as A                          # noqa: E402
from bellbriar_harness import engine as E                       # noqa: E402
from bellbriar_harness import fetch as F                        # noqa: E402
from bellbriar_harness.checks_rendered import RENDERED_CHECKS   # noqa: E402
from bellbriar_harness.engine import load_rulebook, run_page    # noqa: E402
from bellbriar_harness.model import (FAIL, MINOR, NEEDS_REVIEW,  # noqa: E402
                                     Finding, RuleResult)
from bellbriar_harness.scoring import score_page, score_site     # noqa: E402
from tests.test_fetch_hardening import (HAVE_BROWSER, _WHY, _Site,  # noqa: E402
                                        send)
from tests.test_rendered_rules import (  # noqa: E402
    P, attr, captured, findings, rerun, results, run_record, snapshot)

RB = load_rulebook()
ALL_AXE = sorted(set(A.AXE_RULES.values()))


def axe_page(body, applicable, unplaced=None, unchecked=0):
    """A snapshot whose run record says every other axe-core rule did not
    apply."""
    return snapshot(body, root=attr(P + "-axe-run", run_record(
        applicable, sorted(set(ALL_AXE) - set(applicable)), unplaced,
        unchecked)))


def mark(*results):
    return json.dumps([{"r": r, "v": v, "i": i, "m": m}
                       for r, v, i, m in results])


class TestUnplacedResultsAreReported(unittest.TestCase):
    """QR-1: a result no element carries is a finding about the page."""

    def test_unplaced_failures_fail_the_rule(self):
        page = rerun(axe_page("<p>text</p>", ["color-contrast", "list"],
                              unplaced={"color-contrast": {"f": 2, "r": 1,
                                                           "i": "serious"},
                                        "list": {"f": 0, "r": 3, "i": ""}}))
        got = [(f.verdict, f.impact, f.selector)
               for f in findings(page, "bb-contrast-min")]
        self.assertEqual(got, [(FAIL, "serious", ["html"]),
                               (NEEDS_REVIEW, MINOR, ["html"])])
        self.assertIn("2 more violations", findings(page, "bb-contrast-min")
                      [0].message)
        self.assertTrue(results(page, "bb-contrast-min")[0].failed)
        # Only undecided results: a review, and the rule passes.
        self.assertEqual([f.verdict for f in findings(page, "bb-list")],
                         [NEEDS_REVIEW])
        self.assertFalse(results(page, "bb-list")[0].failed)

    def test_content_axe_core_did_not_check_is_not_a_pass(self):
        # QR-2: a rule with a failure still fails; one without is not
        # evaluated, applicable or not.
        body = f'<p{attr(P + "-axe", mark(("color-contrast", "fail", "serious", "low")))}>x</p>'
        page = rerun(axe_page(body, ["color-contrast", "list"], unchecked=4))
        self.assertTrue(results(page, "bb-contrast-min")[0].failed)
        self.assertEqual(results(page, "bb-list"), [])
        self.assertEqual(results(page, "bb-summary-name"), [])
        layer = {l["layer"]: l for l in E.layer_records([page])}["rendered"]
        self.assertEqual(layer["status"], "partial")
        self.assertIn("not every rule", layer["note"])


class TestMergingViews(unittest.TestCase):
    """QR-4, QR-14."""

    def f(self, verdict, msg, selector=("a",), line=3):
        return Finding("bb-x", verdict, "serious", msg, line=line,
                       snippet="<a>" if selector else "",
                       selector=list(selector) if selector else None)

    def test_a_failure_stands_when_only_the_narrow_view_errored(self):
        main = RuleResult("bb-link-name", True,
                          [self.f(FAIL, "Link has no accessible name")])
        narrow = RuleResult("bb-link-name", False, errored="TypeError: x")
        got = E.merge_views(main, narrow)
        page = run_page(snapshot("<p>x</p>"), "p.html", RB)
        page.results = [r for r in page.results if r.rule_id != "bb-link-name"]
        page.results.append(got)
        s = score_page(page, RB)
        self.assertIs(s["tier1_clean"], False)
        self.assertIn("bb-link-name", s["failed_rules"])
        # Without a failure the result is unknown: no pass, no Tier-1 clean.
        unknown = E.merge_views(RuleResult("bb-link-name", True, []), narrow)
        self.assertFalse(unknown.applicable)
        page.results[-1] = unknown
        self.assertIsNone(score_page(page, RB)["tier1_clean"])

    def test_page_level_findings_about_different_things_both_stay(self):
        main = RuleResult("bb-x", True, [self.f(FAIL, "no main", None, None)])
        narrow = RuleResult("bb-x", True, [self.f(FAIL, "no main", None, None),
                                           self.f(FAIL, "no skip link", None,
                                                  None)])
        got = E.merge_views(main, narrow)
        self.assertEqual([x.message.split(" (")[0] for x in got.findings],
                         ["no main", "no skip link"])

    def test_a_finding_about_what_the_page_changed_is_a_review(self):
        main = RuleResult("bb-x", False, [])
        narrow = RuleResult("bb-x", True, [self.f(FAIL, "unnamed")])
        got = E.merge_views(main, narrow, unconfirmed=lambda f: True)
        self.assertEqual([(x.verdict, x.impact) for x in got.findings],
                         [(NEEDS_REVIEW, MINOR)])
        self.assertIn(E.UNCONFIRMED_NOTE, got.findings[0].message)
        # It never turns the capture's own review into a failure either.
        main = RuleResult("bb-x", True, [self.f(NEEDS_REVIEW, "maybe")])
        got = E.merge_views(main, narrow, unconfirmed=lambda f: True)
        self.assertEqual([x.message for x in got.findings], ["maybe"])

    ROOT_ATTRS = attr(P + "-hidden", "recorded") + attr(
        P + "-hidden-narrow", "recorded")

    def test_the_narrow_view_marks_what_the_page_changed(self):
        # The phone menu is shown only at 320 px; the page set its
        # aria-hidden to "false" there, which the snapshot does not show.
        body = (f'<div class="m" aria-hidden="true"{attr(P + "-hidden", "display")}'
                f'{attr(P + "-narrow-changed", "self")}><a href="/x">Menu</a></div>')
        page = rerun(snapshot(body, root=self.ROOT_ATTRS))
        got = findings(page, "bb-aria-hidden-focus")
        self.assertEqual([(f.verdict, f.impact) for f in got],
                         [(NEEDS_REVIEW, MINOR)])
        self.assertIn(E.UNCONFIRMED_NOTE, got[0].message)
        # Unchanged, it fails.
        page = rerun(snapshot(body.replace(attr(P + "-narrow-changed", "self"),
                                           ""), root=self.ROOT_ATTRS))
        self.assertEqual([f.verdict for f in findings(page,
                                                      "bb-aria-hidden-focus")],
                         [FAIL])
        # Only what <body> holds changed (something added beside it): the
        # finding stands.
        page = rerun(snapshot(body.replace(attr(P + "-narrow-changed", "self"),
                                           ""), root=self.ROOT_ATTRS).replace(
            "<body>", "<body" + attr(P + "-narrow-changed", "children") + ">"))
        self.assertEqual([f.verdict for f in findings(page,
                                                      "bb-aria-hidden-focus")],
                         [FAIL])

    def test_a_page_is_read_once_when_both_records_agree(self):
        calls = []
        saved = dict(E.CHECKS)
        try:
            def counting(page, fn=saved["bb-link-name"]):
                calls.append(1)
                return fn(page)
            E.CHECKS["bb-link-name"] = counting
            same = (f'<nav{attr(P + "-hidden", "display")}'
                    f'{attr(P + "-hidden-narrow", "display")}><a href="/">x</a></nav>')
            page = rerun(snapshot(same, root=self.ROOT_ATTRS))
            self.assertTrue(page.narrow)
            self.assertEqual(len(calls), 1)
            calls.clear()
            rerun(snapshot(same.replace(attr(P + "-hidden-narrow", "display"),
                                        ""), root=self.ROOT_ATTRS))
            self.assertEqual(len(calls), 2)
        finally:
            E.CHECKS.clear()
            E.CHECKS.update(saved)


class TestEveryFindingHasItsElement(unittest.TestCase):
    """QR2-4: the narrow view tells what a finding is about by the element
    checks_static._f recorded; a finding made any other way would read as
    one about the page."""

    def test_rules_make_findings_only_through_f(self):
        for name in ("checks_static.py", "checks_rendered.py"):
            text = (ROOT / "src" / "bellbriar_harness" / name).read_text(
                encoding="utf-8")
            for m in re.finditer(r"findings\.(append|extend)\(\s*(\S{0,12})",
                                 text):
                with self.subTest(file=name, at=m.start()):
                    self.assertTrue(m.group(2).startswith(("_f(", "_unplaced(")))
            self.assertEqual(text.count("Finding("),
                             1 if name == "checks_static.py" else 0)


class TestNameRules(unittest.TestCase):
    """QR-9, QR-10, QR-13 and the combobox note."""

    def names(self, html, rule, provenance=None):
        page = run_page(html, "p.html", RB, provenance_attr=provenance,
                        reader="dom" if provenance else None)
        return [(f.verdict, f.impact, f.snippet.split(">")[0])
                for f in findings(page, rule)]

    def test_a_closed_menu_is_named_in_a_rendered_run_too(self):
        body = (f'<ul role="menu"{attr(P + "-hidden", "display")}>'
                '<li role="menuitem" tabindex="-1"><svg aria-hidden="true">'
                '</svg></li></ul>')
        rendered = self.names(snapshot(body, root=attr(P + "-hidden",
                                                       "recorded")),
                              "bb-widget-name", provenance=P)
        plain = self.names(snapshot(body), "bb-widget-name")
        self.assertEqual(rendered, plain)
        self.assertEqual([v for v, _, _ in rendered], [FAIL])
        # A hidden tooltip with no text yet is a review: the script that
        # shows it writes its text.
        tip = (f'<div role="tooltip" id="t"{attr(P + "-hidden", "display")}>'
               '</div>')
        self.assertEqual([v for v, _, _ in self.names(
            snapshot(tip, root=attr(P + "-hidden", "recorded")),
            "bb-widget-name", provenance=P)], [NEEDS_REVIEW])

    def test_an_svg_element_is_named_by_its_title(self):
        got = self.names(snapshot(
            '<svg viewBox="0 0 10 10"><g role="img"><title>Sales by month'
            '</title><rect width="5" height="5"/></g><g role="img"><rect '
            'width="5" height="5"/></g><foreignObject><div role="img">'
            '<title>not svg</title></div></foreignObject></svg>'),
            "bb-role-img-name")
        self.assertEqual(got, [(FAIL, "serious", '<g role="img"'),
                               (FAIL, "serious", '<div role="img"')])

    def test_one_unnamed_control_is_one_finding(self):
        html = snapshot('<a href="/x" role="menuitem"></a>'
                        '<button role="tab"></button>'
                        '<input type="button" role="switch">'
                        '<a href="/y"></a><div role="button" tabindex="0"></div>')
        page = run_page(html, "p.html", RB)
        by_rule = {rid: [f.snippet.split(">")[0] for f in findings(page, rid)]
                   for rid in ("bb-link-name", "bb-button-name",
                               "bb-widget-name", "bb-control-label")}
        self.assertEqual(by_rule["bb-link-name"], ['<a href="/y"'])
        self.assertEqual(by_rule["bb-button-name"],
                         ['<div role="button" tabindex="0"'])
        self.assertEqual(sorted(by_rule["bb-widget-name"]),
                         ['<a href="/x" role="menuitem"',
                          '<button role="tab"'])
        self.assertEqual([s.rstrip("/") for s in by_rule["bb-control-label"]],
                         ['<input role="switch" type="button"'])

    def test_the_parts_of_a_combobox_are_reviews(self):
        html = snapshot(
            '<label for="c1">City</label>'
            '<div role="combobox" aria-expanded="true" aria-owns="lb1">'
            '<input id="c1" type="text"></div>'
            '<ul role="listbox" id="lb1"><li role="option">Oslo</li></ul>'
            '<input role="combobox" aria-label="Town" aria-controls="lb2">'
            '<div role="listbox" id="lb2"><div role="option">Rome</div></div>'
            '<div role="combobox" tabindex="0"></div>'
            '<div role="listbox"><div role="option">Alone</div></div>')
        got = self.names(html, "bb-control-label")
        self.assertEqual(got, [
            (NEEDS_REVIEW, MINOR, '<div aria-expanded="true" aria-owns="lb1" '
                                  'role="combobox"'),
            (NEEDS_REVIEW, MINOR, '<ul id="lb1" role="listbox"'),
            (NEEDS_REVIEW, MINOR, '<div id="lb2" role="listbox"'),
            (FAIL, "blocker", '<div role="combobox" tabindex="0"'),
            (FAIL, "blocker", '<div role="listbox"')])


class TestCoverage(unittest.TestCase):
    """QR-8."""

    def test_each_partial_check_says_where_it_did_not_run(self):
        reflow = json.dumps({"width": 320, "height": 640, "scroll_width": 320,
                             "client_width": 320, "clipped": False})
        axe_only = rerun(axe_page("<p>x</p>", ["color-contrast"]))
        both = rerun(snapshot("<p>x</p>", root=attr(
            P + "-axe-run", run_record(["color-contrast"], [
                r for r in ALL_AXE if r != "color-contrast"]))
            + attr(P + "-reflow-run", reflow)))
        sentence = E.coverage_sentence([axe_only, both])
        self.assertIn("the 29 rules axe-core 4.12.1 checks in the browser "
                      "(contrast, target size and 27 more WCAG A/AA rules) and "
                      "reflow at 320 CSS pixels on 1 of the 2 pages it read "
                      "(NOT evaluated on the other)", sentence)
        plain = run_page(snapshot("<p>x</p>"), "p.html", RB)
        sentence = E.coverage_sentence([both, plain, plain])
        self.assertEqual(sentence.count("NOT evaluated on the other 2"), 2)

    def test_a_page_without_the_narrow_record_is_named(self):
        # QR2-2: a page a browser checked whose rules did not also run with
        # what it hides at 320 px (it navigated on narrowing, or the record
        # could not be kept) is named in the run's coverage.
        reflow = json.dumps({"width": 320, "height": 640, "scroll_width": 320,
                             "client_width": 320, "clipped": False})
        root = (attr(P + "-reflow-run", reflow) + attr(P + "-hidden", "recorded"))
        without = rerun(snapshot("<p>x</p>", root=root))
        with_it = rerun(snapshot("<p>x</p>", root=root + attr(
            P + "-hidden-narrow", "recorded")))
        layer = {l["layer"]: l for l in E.layer_records([with_it, without])}
        self.assertEqual(layer["rendered"]["status"], "partial")
        self.assertIn("what 1 of them hide at 320 CSS pixels was not recorded",
                      layer["rendered"]["note"])
        sentence = E.coverage_sentence([with_it, without])
        self.assertIn("what 1 of its pages hide at 320 CSS pixels, "
                      "screen-reader announcements, and content adequacy were "
                      "NOT evaluated", sentence)
        self.assertNotIn("hide at 320", E.coverage_sentence([with_it]))

    def test_each_page_counts_the_tier1_rules_that_ran_on_it(self):
        rendered = rerun(axe_page("<p>x</p>", ALL_AXE))
        plain = run_page(snapshot("<p>x</p>"), "p.html", RB)
        site = score_site([rendered, plain], RB)
        here = [p["tier1_rules_executed"] for p in site["pages"]]
        self.assertGreater(here[0], here[1])
        self.assertEqual(here[0], site["tier1_rules_executed"])

    def test_the_console_shows_each_pages_own_count(self):
        from bellbriar_harness import cli
        with tempfile.TemporaryDirectory() as d:
            a, b = Path(d) / "a.html", Path(d) / "b.html"
            a.write_text(captured(axe_page("<p>x</p>", ALL_AXE)),
                         encoding="utf-8")
            b.write_text(captured(snapshot("<p>x</p>")), encoding="utf-8")
            out = io.StringIO()
            with redirect_stdout(out):
                cli.main([str(a), str(b), "--provenance-attr", P,
                          "--read-as", "dom"])
        lines = [line for line in out.getvalue().splitlines()
                 if line.startswith(("T1 ", "NOT "))]
        counts = [re.search(r"\[(\d+)/(\d+)\]", line).group(1)
                  for line in lines]
        self.assertEqual(len(set(counts)), 2, out.getvalue())
        self.assertIn("each page's [n/", out.getvalue())


class TestDocsSayWhatTheCodeDoes(unittest.TestCase):
    """QR-11: the narrow pass comes after the capture and the page is not
    widened again; the secret names are unknown to the page until the
    capture is serialized, not forever."""

    def test_no_document_says_otherwise(self):
        texts = {p: p.read_text(encoding="utf-8") for p in [
            ROOT / "README.md", ROOT / "docs" / "MEASUREMENT-AND-EVIDENCE-GUIDE.md",
            ROOT / "docs" / "EVIDENCE.md", ROOT / "docs" / "METHODOLOGY.md",
            *(ROOT / "src" / "bellbriar_harness").glob("*.py")]}
        for path, text in texts.items():
            flat = " ".join(text.split())
            for claim in ("narrowed before the capture", "widened back",
                          "never learns those names", "page code never sees",
                          "under a name the page never sees",
                          "Content the capture recorded as hidden is not "
                          "checked"):
                with self.subTest(path=path.name, claim=claim):
                    self.assertNotIn(claim, flat)


class TestLimits(unittest.TestCase):
    """QR-12."""

    def test_a_page_axe_core_is_run_on_fits_the_deadline(self):
        # About 1.3 ms an element on a large page: 26 s at the cap, within
        # the run's budget and well within the render deadline.
        self.assertEqual(A.MAX_PAGE_ELEMENTS, 20_000)
        self.assertLessEqual(A.MAX_PAGE_ELEMENTS * 1.3 / 1000,
                             A.DEFAULT_TIMEOUT_MS / 1000)
        self.assertLess(A.DEFAULT_TIMEOUT_MS / 1000,
                        F.DEFAULT_RENDER_DEADLINE_S / 3)


PHONE = b"""<!doctype html><html lang="en"><head><title>Phone</title><style>
@media (max-width: 600px) { .desk { display: none; } }
@media (min-width: 601px) { .phone { display: none; } }
</style></head><body>
<nav class="desk"><a href="/a">Desktop nav</a></nav>
<main><h1>Phone</h1><p>Text</p></main>
<div class="phone" aria-hidden="true"><a href="/m">Phone menu link</a></div>
%SCRIPT%
</body></html>"""

#: The reviewer's attack: on narrowing, take a capture of the page's own,
#: with spacers placed so its indices name the phone menu where the
#: harness's name the desktop nav.
CAPTURE_ATTACK = b"""<script>
addEventListener('resize', () => {
  if (innerWidth > 400) return;
  const prop = Object.getOwnPropertyNames(window).find(
    n => /^__bb_capture_[0-9a-f]+$/.test(n));
  if (!prop) return;
  const all = Array.from(document.querySelectorAll('*'));
  const desk = document.querySelector('nav.desk');
  const phone = document.querySelector('div.phone');
  const k = all.indexOf(phone) - all.indexOf(desk);
  const spacers = [];
  for (let i = 0; i < k; i++) { const s = document.createElement('span');
    spacers.push(s); desk.before(s); }
  for (const t of ['', '0'.repeat(32)]) {
    try { window[prop](t, 'data-x', '', '', null, {index: 'data-y'}); } catch (e) {}
    try { window[prop]('data-x', '', '', null, {index: 'data-y'}); } catch (e) {}
  }
  for (const s of spacers) s.remove();
});
</script>"""

MQ_ARIA = b"""<!doctype html><html lang="en"><head><title>MQ</title>
<style>@media (min-width: 601px) { .phone { display: none; } }</style></head>
<body><main><h1>MQ</h1><p>Text</p></main>
<nav class="phone" aria-hidden="true" aria-label="Phone"><a href="/m">Phone menu link</a></nav>
<script>
const mq = matchMedia('(max-width: 600px)');
const bar = document.querySelector('.phone');
function sync() { bar.setAttribute('aria-hidden', mq.matches ? 'false' : 'true'); }
mq.addEventListener('change', sync); sync();
</script></body></html>"""

UNMOUNT = b"""<!doctype html><html lang="en"><head><title>Unmount</title></head>
<body><main><h1>Unmount</h1><p>Text</p></main>
<div id="dd" aria-hidden="true" style="display:none"><a href="/x">Closed desktop dropdown link</a></div>
<script>
const mq = matchMedia('(max-width: 600px)');
mq.addEventListener('change', () => { if (mq.matches) document.getElementById('dd')?.remove(); });
</script></body></html>"""

#: A sidebar a script collapses at phone width by a class on <body> (SB
#: Admin 2): a styling change the narrow record measures, so its finding
#: stands.
COLLAPSE = b"""<!doctype html><html lang="en"><head><title>R</title><style>
.collapsed .brand-text { display: none; }</style></head><body>
<nav><a class="brand" href="/"><svg aria-hidden="true" width="8" height="8"></svg>
<span class="brand-text">Brand</span></a></nav><main><h1>R</h1></main>
<script>addEventListener('resize', () => {
  if (innerWidth < 600) document.body.classList.add('collapsed'); });</script>
</body></html>"""

BASE = (b'<!doctype html><html lang="en"><head><title>Base</title></head>'
        b'<body>%PRE%<main><h1>Base</h1>'
        b'<p style="color:#aaa;background:#fff">Low contrast text one</p>'
        b'<p style="color:#bbb;background:#fff">Low contrast text two</p>'
        b'<ul><div>not an item</div><li>item</li></ul></main>%POST%'
        b'</body></html>')

CHURN = BASE.replace(b"%PRE%", b"").replace(
    b"%POST%", b"<script>setInterval(() => document.body.prepend("
               b"document.createComment('')), 2);</script>")
LONG_NAME = BASE.replace(b"<main>", b"<x-" + b"a" * 200 + b"><main>").replace(
    b"</main>", b"</main></x-" + b"a" * 200 + b">").replace(
    b"%PRE%", b"").replace(b"%POST%", b"")
CLOBBER = BASE.replace(b"%PRE%", b'<div id="__bellbriar_axe"></div>').replace(
    b"%POST%", b"")
CAP = BASE.replace(b"%PRE%", b"<div>" + b'<span aria-checked="true">.</span> '
                   * 12 + b"</div>").replace(b"%POST%", b"")

HOSTS = b"""<!doctype html><html lang="en"><head><title>Hosts</title></head>
<body><main><h1>Hosts</h1>
<div class="h"></div><div class="h"></div><div class="h"></div><div class="h" id="last"></div>
<script>
for (const h of document.querySelectorAll('.h')) {
  const r = h.attachShadow({mode: 'closed'});
  r.innerHTML = h.id === 'last'
    ? '<p style="color:#bbb;background:#fff">Low contrast inside the 4th closed root</p>'
    : '<p>fine</p>';
}
</script></main></body></html>"""

REFLOW = b"""<!doctype html><html lang="en"><head><title>R</title><style>%CSS%</style>
</head><body>%BODY%</body></html>"""
WIDE_TEXT = (b"<div class='page'><h1>R</h1><p>Body text in a 960 px column, "
             b"which does not reflow, so a reader at 320 px scrolls sideways "
             b"for every line.</p><img alt='' width='1' height='1' "
             b"style='margin-left:900px' src='data:image/gif;base64,"
             b"R0lGODlhAQABAAAAACw='></div>")


def reflow_page(css, body):
    return REFLOW.replace(b"%CSS%", css).replace(b"%BODY%", body)


XML_PAGE = (b'<?xml version="1.0"?><html xmlns="http://www.w3.org/1999/xhtml" '
            b'lang="en"><head><title>X</title></head><body><a href="/x"></a>'
            b'</body></html>')
GOES_TO_XML = (b'<!doctype html><html lang="en"><head><title>G</title></head>'
               b'<body><main><h1>G</h1></main><script>setTimeout(() => '
               b'{ location.href = "/feed"; }, 50);</script></body></html>')


@unittest.skipUnless(HAVE_BROWSER, _WHY)
class TestInTheBrowser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.site = _Site({
            "/phone": send(PHONE.replace(b"%SCRIPT%", b"")),
            "/phone-attack": send(PHONE.replace(b"%SCRIPT%", CAPTURE_ATTACK)),
            "/mq": send(MQ_ARIA), "/unmount": send(UNMOUNT),
            "/collapse": send(COLLAPSE),
            "/base": send(BASE.replace(b"%PRE%", b"").replace(b"%POST%", b"")),
            "/churn": send(CHURN), "/long": send(LONG_NAME),
            "/clobber": send(CLOBBER), "/cap": send(CAP), "/hosts": send(HOSTS),
            "/rf-clip": send(reflow_page(
                b"body{overflow-x:clip;margin:0} .off{position:absolute;top:0;"
                b"left:100%;width:280px}",
                b"<main><h1>R</h1><p>Text.</p></main><nav class='off'>"
                b"<a href='/a'>Menu</a></nav>")),
            "/rf-hidden": send(reflow_page(
                b"html,body{overflow-x:hidden} .off{position:absolute;top:0;"
                b"left:100%;width:280px}",
                b"<main><h1>R</h1><p>Text.</p></main><nav class='off'>"
                b"<a href='/a'>Menu</a></nav>")),
            "/rf-text": send(reflow_page(b".page{width:960px}", WIDE_TEXT)),
            "/rf-table": send(reflow_page(
                b"table{width:900px}",
                b"<main><h1>R</h1><p>Text that reflows.</p><div><table>"
                b"<tr><td>1</td><td>2</td></tr></table></div></main>")),
            "/rf-code": send(reflow_page(
                b"pre{margin:0}",
                b"<main><h1>R</h1><p>Text that reflows.</p><pre><code>"
                b"const answer = computeTheAnswerToLifeTheUniverseAndEverything"
                b"(42, 'a long line of code');</code></pre></main>")),
            "/rf-empty": send(reflow_page(
                b".row{margin-right:-40px}",
                b"<main><h1>R</h1><div class='row'><p>Short text.</p></div>"
                b"</main>")),
            "/goes-to-xml": send(GOES_TO_XML),
            "/feed": send(XML_PAGE, ctype="application/xml"),
        })

    @classmethod
    def tearDownClass(cls):
        cls.site.stop()

    def capture(self, path, **kw):
        fr = F.fetch_rendered(self.site.base + path, **kw)
        page = run_page(fr.html, fr.final_url, RB,
                        provenance_attr=fr.provenance_attr, reader=fr.reader)
        return fr, page

    def contrast(self, page):
        return [(f.verdict, tuple(f.selector or ()))
                for f in findings(page, "bb-contrast-min")]

    # QR-1

    def test_a_page_that_keeps_changing_cannot_drop_its_failures(self):
        fr, page = self.capture("/churn")
        self.assertTrue(fr.axe["ran"])
        self.assertTrue(results(page, "bb-contrast-min")[0].failed)
        self.assertTrue(results(page, "bb-list")[0].failed)
        # Where a result went on its element, it is the right element.
        placed = [s for v, s in self.contrast(page) if s != ("html",)]
        self.assertTrue(all(s[0].startswith("body > main > p") for s in placed))
        self.assertEqual(fr.axe["elements"] + fr.axe["not_located"], 3)

    def test_a_long_element_name_drops_nothing(self):
        fr, page = self.capture("/long")
        self.assertEqual((fr.axe["elements"], fr.axe["not_located"]), (3, 0))
        self.assertEqual(len(self.contrast(page)), 2)

    def test_results_that_never_fail_cannot_crowd_out_failures(self):
        saved = A.MAX_ELEMENTS
        try:
            A.MAX_ELEMENTS = 5
            fr, page = self.capture("/cap", narrow=False)
        finally:
            A.MAX_ELEMENTS = saved
        self.assertEqual(sorted(s for v, s in self.contrast(page)),
                         [("body > main > p:nth-child(2)",),
                          ("body > main > p:nth-child(3)",)])
        allowed = findings(page, "bb-aria-allowed-attr")
        self.assertEqual(sum(1 for f in allowed if f.selector == ["html"]), 1)
        self.assertIn("more violation", [f for f in allowed
                                         if f.selector == ["html"]][0].message)
        self.assertGreater(fr.axe["not_located"], 0)

    def test_a_mark_the_page_moves_before_the_capture_is_dropped(self):
        # Between where the isolated world found the elements and the
        # capture, the page swaps the two paragraphs: neither keeps a result
        # that may be the other's, and both are reported about the page.
        swap = ("(() => { const m = document.querySelector('main'); "
                "const ps = m.querySelectorAll('p'); "
                "m.insertBefore(ps[1], ps[0]); })()")

        class Swapping(F._AxeSession):
            def extra(self, cdp, name, roots):
                out = super().extra(cdp, name, roots)
                cdp.send("Runtime.evaluate", {"expression": swap})
                return out
        saved = F._AxeSession
        try:
            F._AxeSession = Swapping
            fr, page = self.capture("/base", narrow=False)
        finally:
            F._AxeSession = saved
        self.assertEqual(self.contrast(page), [(FAIL, ("html",))])
        self.assertIn("2 more violations",
                      findings(page, "bb-contrast-min")[0].message)
        # The list sits in the <main> the page changed: its place could
        # have moved too, so it is reported about the page as well.
        self.assertEqual([f.selector for f in findings(page, "bb-list")],
                         [["html"]])

    def test_a_flood_before_the_capture_leaves_results_counted(self):
        # QR2-3: more changes between axe-core's places and the capture
        # than the watch counts: no mark stands, and every result is
        # reported about the page (the run's record is still written).
        flood = ("(() => { const b = document.body, x = document.createElement('i');"
                 " for (let i = 0; i < 600000; i++) { b.append(x); x.remove(); } })()")

        class Flooding(F._AxeSession):
            def extra(self, cdp, name, roots):
                out = super().extra(cdp, name, roots)
                cdp.send("Runtime.evaluate", {"expression": flood})
                return out
        saved = F._AxeSession
        try:
            F._AxeSession = Flooding
            fr, page = self.capture("/base", narrow=False)
        finally:
            F._AxeSession = saved
        self.assertTrue(fr.axe["ran"])
        self.assertEqual((fr.axe["elements"], fr.axe["not_located"]), (0, 3))
        self.assertEqual(self.contrast(page), [(FAIL, ("html",))])
        self.assertTrue(results(page, "bb-list")[0].failed)

    # QR-2

    def test_closed_roots_axe_core_was_not_given_are_not_a_pass(self):
        saved = F.MAX_CLOSED_ROOT_HOSTS
        try:
            F.MAX_CLOSED_ROOT_HOSTS = 3
            fr, page = self.capture("/hosts", narrow=False)
        finally:
            F.MAX_CLOSED_ROOT_HOSTS = saved
        self.assertEqual(fr.axe["unchecked"], 1)
        self.assertEqual(results(page, "bb-contrast-min"), [])
        self.assertTrue(any("did not check 1 element" in n for n in fr.notes))
        fr, page = self.capture("/hosts", narrow=False)
        self.assertEqual(fr.axe["unchecked"], 0)
        self.assertEqual(self.contrast(page), [(FAIL, ("#last", "p"))])

    # QR-3

    def test_a_page_cannot_take_a_capture_of_its_own(self):
        for path in ("/phone", "/phone-attack"):
            with self.subTest(path):
                fr, page = self.capture(path)
                narrow = F.narrow_hidden_attr(fr.provenance_attr)
                self.assertRegex(fr.html, f'<nav class="desk"[^>]* {narrow}='
                                          '"display"')
                self.assertNotRegex(fr.html, f'<div class="phone"[^>]* {narrow}=')
                got = findings(page, "bb-aria-hidden-focus")
                self.assertEqual([f.verdict for f in got], [FAIL])
                self.assertIn(E.NARROW_NOTE, got[0].message)

    # QR-4

    def test_what_the_page_changes_at_phone_width_is_not_read_as_failing(self):
        fr, page = self.capture("/mq")
        self.assertGreater(fr.narrow["changed"], 0)
        got = findings(page, "bb-aria-hidden-focus")
        self.assertEqual([(f.verdict, f.impact) for f in got],
                         [(NEEDS_REVIEW, MINOR)])
        fr, page = self.capture("/unmount")
        self.assertEqual(findings(page, "bb-aria-hidden-focus"), [])
        # A class the page sets is a styling change the record measures.
        fr, page = self.capture("/collapse")
        got = findings(page, "bb-link-name")
        self.assertEqual([f.verdict for f in got], [FAIL])
        self.assertNotIn(E.UNCONFIRMED_NOTE, got[0].message)

    def test_a_flood_of_changes_after_the_capture_makes_reviews(self):
        # QR2-2: more changes than the watch counts, and the narrow-only
        # failure is reported for review, not dropped with the record.
        flood = PHONE.replace(b"%SCRIPT%", b"""<script>
addEventListener('resize', () => {
  if (innerWidth > 400) return;
  const s = document.createElement('i'); document.body.append(s);
  for (let i = 0; i < 1000100; i++) s.setAttribute('aria-label', 'x' + i);
});</script>""")
        site = _Site({"/": send(flood)})
        try:
            fr = F.fetch_rendered(site.base + "/")
        finally:
            site.stop()
        page = run_page(fr.html, fr.final_url, RB,
                        provenance_attr=fr.provenance_attr, reader="dom")
        self.assertTrue(fr.narrow["hiding_recorded"])
        self.assertTrue(fr.narrow["changed_all"])
        got = findings(page, "bb-aria-hidden-focus")
        self.assertEqual([(f.verdict, f.impact) for f in got],
                         [(NEEDS_REVIEW, MINOR)])

    # QR-5, QR-6

    def test_reflow(self):
        for path, want in (("/rf-clip", []), ("/rf-hidden", []),
                           ("/rf-text", [(FAIL, "serious")]),
                           ("/rf-table", [(NEEDS_REVIEW, "moderate")]),
                           # The <code> in a <pre> is the <pre>'s content.
                           ("/rf-code", [(NEEDS_REVIEW, "moderate")]),
                           ("/rf-empty", [(NEEDS_REVIEW, MINOR)])):
            with self.subTest(path):
                fr, page = self.capture(path)
                self.assertEqual([(f.verdict, f.impact) for f in
                                  findings(page, "bb-reflow-320")], want)
                self.assertEqual(fr.narrow["clipped"],
                                 path in ("/rf-clip", "/rf-hidden"))

    # QR-7

    def test_an_id_cannot_switch_axe_core_off(self):
        fr, page = self.capture("/clobber", narrow=False)
        self.assertTrue(fr.axe["ran"])
        self.assertEqual(len(self.contrast(page)), 2)

    # PR4-1

    def test_a_page_that_goes_on_to_an_xml_document_is_not_read_as_html(self):
        # The page goes on to an XML document after it loaded, by the time
        # of the capture (as a script or a refresh can): the capture is of
        # that document, which a capture cannot read as it is served.
        saved = F._call_capture
        base = self.site.base

        def later(ctx, page, *a, **kw):
            page.goto(base + "/feed", wait_until="load")
            return saved(ctx, page, *a, **kw)
        try:
            F._call_capture = later
            with self.assertRaisesRegex(F.FetchError, "an XML document"):
                F.fetch_rendered(base + "/base", narrow=False)
            # Another HTML page is captured as the document it ended on: the
            # page goes there once, and the capture reads it once more
            # (R5A-1).
            went = []

            def once(ctx, page, *a, **kw):
                if not went:
                    went.append(page.goto(base + "/phone", wait_until="load"))
                return saved(ctx, page, *a, **kw)
            F._call_capture = once
            fr = F.fetch_rendered(base + "/base", narrow=False)
        finally:
            F._call_capture = saved
        self.assertTrue(fr.navigated)
        self.assertTrue(fr.final_url.endswith("/phone"))
        self.assertTrue(any("sent the browser on to another document" in n
                            for n in fr.notes))


if __name__ == "__main__":
    unittest.main(verbosity=2)
