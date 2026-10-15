"""Part Q: the rendered checks.

  A2    axe-core (decision D2): pinned, hash-checked, run in an isolated
        world for the WCAG A/AA rules Bellbriar does not implement itself;
        the capture records its results, the rules read them there, and a
        re-run of the snapshot reproduces them.
  P2-09 the other name rules, by role: form fields (bb-control-label, as
        ACT e086e5 chooses them) and widgets (bb-widget-name).
  L19   a focusable custom control with no valid role (bb-control-role).
  L24   what the page hides at phone width, and reflow at 320 CSS pixels
        (bb-reflow-320).
  L25   the capture's record of what the page hides decides wherever it
        recorded it.
"""
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bellbriar_harness import axe as A                          # noqa: E402
from bellbriar_harness import checks_static as CS               # noqa: E402
from bellbriar_harness import engine as E                       # noqa: E402
from bellbriar_harness import fetch as F                        # noqa: E402
from bellbriar_harness.checks_rendered import RENDERED_CHECKS   # noqa: E402
from bellbriar_harness.engine import (load_rulebook, run_page,  # noqa: E402
                                      run_paths)
from bellbriar_harness.model import (CURRENT_PAGE, FAIL,         # noqa: E402
                                     NEEDS_REVIEW, PROVENANCE_ATTR,
                                     RuleResult, Finding)
from bellbriar_harness.scoring import score_page                 # noqa: E402
from tests.test_fetch_hardening import (HAVE_BROWSER, _WHY, _Site,  # noqa: E402
                                        send)

RB = load_rulebook()
P = "data-bb-p-0123456789abcdef"
PAGE = ('<!doctype html><html lang="en"{root}><head><title>T</title></head>'
        '<body><main><h1>T</h1>{body}</main></body></html>')


def run_record(applicable=(), inapplicable=(), unplaced=None, unchecked=0):
    return json.dumps({"engine": "axe-core", "version": A.AXE_VERSION,
                       "applicable": list(applicable),
                       "inapplicable": list(inapplicable),
                       "unplaced": unplaced or {}, "unchecked": unchecked})


def mark(*results):
    return json.dumps([{"r": r, "v": v, "i": i, "m": m}
                       for r, v, i, m in results])


def attr(name, value):
    """An attribute as a serialized capture writes it."""
    return f" {name}='{value}'" if '"' in value else f' {name}="{value}"'


def snapshot(body, root="", provenance=P):
    return PAGE.format(root=root, body=body)


def captured(html, provenance=P):
    """`html`, a snapshot, with the record a capture by this release
    writes on its root, which a re-run of it (run_paths) reads first
    (L53, L106)."""
    from bellbriar_harness.model import MARKS_VERSION
    record = json.dumps({"browser": "141.0", "marks": MARKS_VERSION})
    head, root, rest = html.partition("<html")
    return head + root + attr(provenance + "-capture", record) + rest


def results(page, rule):
    return [r for r in page.results if r.rule_id == rule]


def findings(page, rule):
    return [f for r in page.results if r.rule_id == rule for f in r.findings]


def rerun(html, provenance=P):
    return run_page(html, "snap.html", RB, provenance_attr=provenance,
                    reader="dom")


class TestVendoredAxe(unittest.TestCase):
    VENDOR = ROOT / "src" / "bellbriar_harness" / "vendor" / "axe-core"

    def test_the_file_is_the_pinned_release_unmodified(self):
        data = (self.VENDOR / "axe.min.js").read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), A.AXE_SHA256)
        self.assertEqual(len(data), 572_599)
        self.assertTrue(data.startswith(b"/*! axe v4.12.1\n"))
        # The digest axe-core publishes for its own axe.min.js.
        import base64
        self.assertEqual("sha256-" + base64.b64encode(
            hashlib.sha256(data).digest()).decode(),
            "sha256-ZqiqqVqLBEp/10pUNYc78E/2WhynVWfJIbdQl0IIWhQ=")
        self.assertTrue(A.axe_source().startswith("/*! axe v4.12.1"))

    def test_a_changed_file_is_never_run(self):
        saved = (A._SOURCE, A.AXE_SHA256)
        try:
            A._SOURCE, A.AXE_SHA256 = None, "0" * 64
            with self.assertRaisesRegex(A.AxeUnavailable, "not the pinned"):
                A.axe_source()
        finally:
            A._SOURCE, A.AXE_SHA256 = saved

    def test_its_licenses_and_notice_ship_with_it(self):
        self.assertTrue((self.VENDOR / "LICENSE").read_text().startswith(
            "Mozilla Public License, version 2.0"))
        third = (self.VENDOR / "LICENSE-3RD-PARTY.txt").read_text()
        self.assertIn("MIT License", third)
        self.assertIn("ISC License", third)
        notice = (self.VENDOR / "README.md").read_text()
        for needle in (A.AXE_SHA256, "4.12.1", "Mozilla Public License 2.0",
                       "https://github.com/dequelabs/axe-core/tree/v4.12.1",
                       "unmodified"):
            self.assertIn(needle, notice)
        pyproject = (ROOT / "pyproject.toml").read_text()
        self.assertIn('"vendor/axe-core/*"', pyproject)

    def test_the_rulebook_names_each_axe_rule_once(self):
        by_engine = {r["id"]: r for r in RB["rules"]
                     if r.get("engine") == "axe-core"}
        self.assertEqual(set(by_engine), set(A.AXE_RULES))
        for rid, rule in by_engine.items():
            self.assertEqual(rule["axe_rule"], A.AXE_RULES[rid])
            self.assertEqual((rule["layer"], rule["status"]),
                             ("rendered", "implemented"))
        rendered = {r["id"] for r in RB["rules"] if r.get("layer") ==
                    "rendered" and r.get("status") == "implemented"}
        self.assertEqual(rendered, set(RENDERED_CHECKS))
        self.assertEqual(len(set(A.AXE_RULES.values())), len(A.AXE_RULES))
        self.assertFalse(set(A.AXE_RULES.values()) & set(A.NOT_RUN))

    def test_each_rule_axe_core_is_not_run_for_is_one_bellbriar_decides(self):
        implemented = {r["id"] for r in RB["rules"]
                       if r.get("status") == "implemented"}
        import re
        for axe_rule, why in A.NOT_RUN.items():
            for rid in re.findall(r"bb-[a-z0-9-]+", why):
                self.assertIn(rid, implemented, axe_rule)


class TestAxeAnswer(unittest.TestCase):
    """What a capture makes of axe-core's answer (axe.read_answer)."""

    def answer(self, **kw):
        out = {"status": "ran", "version": A.AXE_VERSION, "ms": 12,
               "changes": 0, "applicable": ["color-contrast", "list",
                                            "image-alt"],
               "inapplicable": ["summary-name"], "notRun": [],
               "help": {"color-contrast": "Elements must meet contrast",
                        "list": "&lt;ul&gt; holds only &lt;li&gt;"},
               "entries": [
                   {"k": 0,
                    "results": [{"r": "color-contrast", "v": "fail",
                                 "i": "serious", "c": ["ratio 2.3"]},
                                {"r": "list", "v": "review",
                                 "i": "critical", "c": ["&amp;lt;x&amp;gt;"]},
                                {"r": "image-alt", "v": "fail", "i": "critical",
                                 "c": ["no alt"]}]},
                   {"k": 1, "results": [{"r": "image-alt", "v": "fail",
                                         "i": "minor", "c": []}]}],
               "lost": {"color-contrast": {"f": 2, "r": 1, "i": "critical"}}}
        out.update(kw)
        return out

    def test_results_are_kept_by_element(self):
        answer, block, notes = A.read_answer(self.answer())
        # Only the rules a capture runs; image-alt is bb-img-alt's.
        self.assertEqual(answer.applicable, ["color-contrast", "list"])
        self.assertEqual(answer.inapplicable, ["summary-name"])
        self.assertEqual(list(answer.results), [0])
        got = json.loads(answer.mark(0))
        self.assertEqual([(m["r"], m["v"], m["i"]) for m in got],
                         [("color-contrast", "fail", "serious"),
                          ("list", "review", "minor")])
        self.assertEqual(got[0]["m"], "Elements must meet contrast: ratio "
                         "2.3 [axe-core 4.12.1 color-contrast]")
        # axe-core's text is HTML, read once: "&amp;lt;" is the text "&lt;".
        self.assertIn("<ul> holds only <li>", got[1]["m"])
        self.assertIn("&lt;x&gt;", got[1]["m"])
        self.assertTrue(got[1]["m"].startswith("axe-core could not decide"))
        self.assertTrue(block["ran"])
        self.assertEqual(block["sha256"], A.AXE_SHA256)
        # What the isolated world could not keep is counted, by rule.
        self.assertEqual(answer.lost, {"color-contrast": {
            "f": 2, "r": 1, "i": "blocker"}})
        self.assertEqual(notes, [])

    def test_results_that_do_not_reach_an_element_are_counted(self):
        answer, _, _ = A.read_answer(self.answer())
        answer.lose(0)
        self.assertEqual(answer.results, {})
        self.assertEqual(answer.lost, {
            "color-contrast": {"f": 3, "r": 1, "i": "blocker"},
            "list": {"f": 0, "r": 1, "i": ""}})
        self.assertEqual(answer.not_located(), 5)
        run = A.read_run(answer.run_record(7))
        self.assertEqual(run["unplaced"]["color-contrast"]["f"], 3)
        self.assertEqual(run["unchecked"], 7)

    def test_an_answer_not_in_the_helpers_shape_is_none(self):
        for out, why in ((self.answer(version="4.0.0"), "unexpected"),
                         (self.answer(entries=[{"k": "x", "results": []}]),
                          "unexpected"),
                         (self.answer(entries=[{"k": 0, "results": [
                             {"r": "list", "v": "maybe"}]}]), "unexpected"),
                         (self.answer(lost={"list": {"f": -1, "r": 0,
                                                     "i": ""}}), "unexpected"),
                         (self.answer(applicable=[], inapplicable=[],
                                      entries=[], lost={},
                                      notRun=sorted(A.AXE_RULES.values())),
                          "did not finish"),
                         ("junk", "no answer")):
            with self.subTest(why=why):
                answer, block, _ = A.read_answer(out)
                self.assertIsNone(answer)
                self.assertFalse(block["ran"])
                self.assertIn(why, block["reason"])

    def test_rules_it_ran_out_of_time_for_are_named(self):
        answer, block, notes = A.read_answer(self.answer(
            notRun=["target-size", "image-alt"]))
        self.assertEqual(block["not_run"], ["target-size"])
        self.assertTrue(any("not run and were not evaluated" in n
                            for n in notes))

    def test_a_page_too_large_for_axe_core_is_left_out(self):
        answer, block, _ = A.read_answer({"status": "too-large",
                                          "elements": 75000})
        self.assertIsNone(answer)
        self.assertIn("75,000 elements", block["reason"])

    def test_records_read_back_strictly(self):
        self.assertIsNone(A.read_run("{"))
        self.assertIsNone(A.read_run('{"engine": "other"}'))
        self.assertIsNone(A.read_run("pending"))
        # A record without its counts is no record.
        self.assertIsNone(A.read_run(json.dumps({
            "engine": "axe-core", "version": A.AXE_VERSION,
            "applicable": [], "inapplicable": []})))
        self.assertIsNone(A.read_run(run_record(
            unplaced={"list": {"f": 1, "r": 0, "i": ""}})))
        self.assertEqual(A.read_mark('[{"r": "list", "v": "maybe", "i": '
                                     '"minor", "m": "x"}]'), [])
        self.assertEqual(A.read_mark("[1, 2]"), [])
        self.assertEqual(A.read_mark("{"), [])

    def test_the_rules_that_can_fail_are_recorded_first(self):
        order = A.rule_order()
        basis = E.verdict_basis(RB)
        never = [basis[A.bellbriar_rule(r)] in E.NEVER_FAIL_BASES
                 for r in order]
        self.assertEqual(never, sorted(never))
        self.assertIn("color-contrast", order[:never.index(True)])
        self.assertIn("aria-allowed-attr", order[never.index(True):])
        self.assertEqual(A.run_parts(order)[:2], [["color-contrast"],
                                                 ["target-size"]])
        self.assertEqual(sorted(sum(A.run_parts(order), [])), sorted(order))


class TestRenderedRulesReadTheSnapshot(unittest.TestCase):
    """The rules read axe-core's records from the snapshot, under the
    capture's secret only, so a re-run reproduces them and a page cannot
    write them."""

    def page_html(self, provenance=P, rules=None):
        applied = ["color-contrast", "list", "aria-valid-attr-value",
                   "target-size", "frame-title-unique"]
        run = run_record(applied, rules if rules is not None else
                         sorted(set(A.AXE_RULES.values()) - set(applied)))
        return snapshot(
            f'<p id="low"{attr(provenance + "-axe", mark(("color-contrast", "fail", "serious", "low contrast")))}>Grey</p>'
            f'<ul{attr(provenance + "-axe", mark(("list", "review", "minor", "could not tell")))}><li>a</li></ul>'
            f'<div role="checkbox" aria-checked="maybe" aria-label="x" tabindex="0"{attr(provenance + "-axe", mark(("aria-valid-attr-value", "fail", "serious", "bad value")))}></div>'
            f'<button{attr(provenance + "-axe", mark(("target-size", "fail", "serious", "too small")))}>x</button>',
            root=attr(provenance + "-axe-run", run))

    def rules(self):
        applied = ["color-contrast", "list", "aria-valid-attr-value",
                   "target-size", "frame-title-unique"]
        return applied, sorted(set(A.AXE_RULES.values()) - set(applied))

    def test_a_rerun_with_the_capture_secret_reads_them(self):
        page = rerun(self.page_html())
        contrast = findings(page, "bb-contrast-min")
        self.assertEqual([(f.verdict, f.impact, f.selector) for f in contrast],
                         [(FAIL, "serious", ["#low"])])
        self.assertNotIn("-axe", contrast[0].snippet)
        self.assertEqual([f.verdict for f in findings(page, "bb-list")],
                         [NEEDS_REVIEW])
        self.assertFalse(results(page, "bb-summary-name")[0].applicable)
        # Not in the run's record: not evaluated, no result at all.
        page = rerun(self.page_html(rules=["summary-name"]))
        self.assertEqual(results(page, "bb-object-alt"), [])
        self.assertEqual(page.axe_version, A.AXE_VERSION)

    def test_each_rule_is_held_to_its_basis(self):
        page = rerun(self.page_html())
        value = findings(page, "bb-aria-attr-value")[0]
        self.assertEqual(value.verdict, NEEDS_REVIEW)
        self.assertIn(E.BEST_PRACTICE_NOTE, value.message)
        size = findings(page, "bb-target-size")[0]
        self.assertEqual(size.verdict, NEEDS_REVIEW)
        self.assertIn(E.WCAG22_NOTE, size.message)
        # A WCAG 2.2 criterion never gates a build, not even with --strict.
        self.assertFalse(E.strict_gated({r["id"]: r for r in RB["rules"]}
                                        ["bb-target-size"]))

    def test_without_the_secret_nothing_is_read(self):
        # A file run trusts no record; a page that wrote records under some
        # name of its own is ignored under the capture's.
        for page in (run_page(self.page_html(), "p.html", RB),
                     rerun(self.page_html(provenance="data-bb-p-ffffffffffffffff"))):
            with self.subTest():
                self.assertFalse([r for r in page.results
                                  if r.rule_id in RENDERED_CHECKS])
                self.assertEqual(page.axe_version, "")
                self.assertEqual(E.coverage_sentence([page]),
                                 E.COVERAGE_SENTENCE)
                layer = {l["layer"]: l for l in E.layer_records([page])}
                self.assertEqual(layer["rendered"]["status"], "skipped")

    def test_the_run_says_what_the_browser_checked(self):
        reflow = json.dumps({"width": 320, "height": 640, "scroll_width": 320,
                             "client_width": 320, "clipped": False})
        html = self.page_html().replace(
            "<html lang=\"en\"", "<html lang=\"en\"" +
            attr(P + "-reflow-run", reflow) + attr(P + "-hidden", "recorded")
            + attr(P + "-hidden-narrow", "recorded"), 1)
        rendered = rerun(html)
        plain = run_page(self.page_html(), "p.html", RB)
        layer = {l["layer"]: l for l in E.layer_records([rendered])}
        self.assertEqual(layer["rendered"]["status"], "executed")
        self.assertIn("axe-core 4.12.1 checked 1 of 1", layer["rendered"]["note"])
        self.assertIn("reflow at 320 CSS pixels on 1 of 1",
                      layer["rendered"]["note"])
        # axe-core's rules without the reflow record: partly executed.
        only_axe = {l["layer"]: l for l in
                    E.layer_records([rerun(self.page_html())])}
        self.assertEqual(only_axe["rendered"]["status"], "partial")
        # A page where not every axe-core rule has a result (a part of the
        # run it ran out of time for): partly executed, and said so.
        short = {l["layer"]: l for l in E.layer_records([rerun(
            html.replace(run_record(*self.rules()), run_record(
                self.rules()[0], ["summary-name"])))])}
        self.assertEqual(short["rendered"]["status"], "partial")
        self.assertIn("not every rule on 1 of them", short["rendered"]["note"])
        mixed = {l["layer"]: l for l in E.layer_records([rendered, plain])}
        self.assertEqual(mixed["rendered"]["status"], "partial")
        sentence = E.coverage_sentence([rendered, plain])
        self.assertIn("on 1 of the 2 pages it read (NOT evaluated on the "
                      "other)", sentence)
        self.assertNotIn("contrast, reflow", sentence)

    def test_a_vendor_widget_is_reported_not_scored(self):
        run = run_record(["color-contrast"])
        html = snapshot(
            f'<div {P}="third-party:https://chat.example">'
            f'<p{attr(P + "-axe", mark(("color-contrast", "fail", "serious", "low")))}>x</p></div>',
            root=attr(P + "-axe-run", run))
        page = rerun(html)
        f = findings(page, "bb-contrast-min")[0]
        self.assertEqual(f.origin, "third-party")
        self.assertFalse(results(page, "bb-contrast-min")[0].failed)
        self.assertEqual(score_page(page, RB)["third_party_fail_findings"], 1)

    def test_a_snapshot_from_a_file_run_is_unchanged(self):
        run = run_paths([ROOT / "fixtures" / "good.html"])
        self.assertEqual(run["coverage_note"], E.COVERAGE_SENTENCE)
        self.assertEqual({l["layer"]: l["status"] for l in run["layers"]}
                         ["rendered"], "skipped")


class TestWidgetNamesByRole(unittest.TestCase):
    """P2-09: every element whose role needs a name is checked, native or
    not, by the rule for its role."""

    def check(self, body):
        return run_page(snapshot(body), "p.html", RB)

    def test_form_fields_by_role(self):
        page = self.check(
            '<div role="checkbox" tabindex="0" aria-checked="false"></div>'
            '<div role="checkbox" tabindex="0" aria-checked="false">Subscribe</div>'
            '<div role="textbox" contenteditable>its value</div>'
            '<div role="textbox" contenteditable aria-label="Notes"></div>'
            '<div role="slider" aria-valuenow="3" tabindex="0">3</div>'
            '<div role="searchbox" aria-placeholder="Search"></div>'
            '<input type="text" role="button">')
        got = [(f.verdict, f.snippet) for f in
               findings(page, "bb-control-label")]
        self.assertEqual(
            got, [(FAIL, '<div aria-checked="false" role="checkbox" '
                         'tabindex="0"></div>'),
                  # A textbox's text is its value, a slider's too: no name.
                  (FAIL, '<div contenteditable="" role="textbox">its value'
                         '</div>'),
                  (FAIL, '<div aria-valuenow="3" role="slider" tabindex="0">3'
                         '</div>'),
                  (NEEDS_REVIEW, '<div aria-placeholder="Search" '
                                 'role="searchbox"></div>')])
        # role=button makes it a button: bb-button-name's.
        self.assertEqual(len(findings(page, "bb-button-name")), 1)

    def test_widgets_by_role(self):
        page = self.check(
            '<div role="progressbar" aria-valuenow="40">40%</div>'
            '<div role="progressbar" aria-label="Upload"></div>'
            '<div role="meter" aria-valuenow="1"></div>'
            '<div role="tablist"><div role="tab"></div><div role="tab">Two'
            '</div></div><div role="menu"><div role="menuitem"></div></div>'
            '<div role="tree"><div role="treeitem">Leaf</div></div>'
            '<i class="icon" role="img"></i><span role="img" aria-label="Star">'
            '*</span><svg role="img"></svg><img src="a.png" role="img">')
        # One rule for each basis W3C gives an unnamed one (Part R2
        # review): controls (F68), role=img images (ACT 23a2a8), and progress
        # bars and meters (no W3C failure: heuristic).
        got = {rule: sorted(f.snippet.split(">")[0] for f in
                            findings(page, rule))
               for rule in ("bb-widget-name", "bb-role-img-name",
                            "bb-progress-name")}
        self.assertEqual(got, {
            "bb-widget-name": ['<div role="menuitem"', '<div role="tab"'],
            "bb-role-img-name": ['<i class="icon" role="img"'],
            "bb-progress-name": ['<div aria-valuenow="1" role="meter"',
                                 '<div aria-valuenow="40" role="progressbar"']})
        self.assertTrue(all(f.verdict == FAIL for rule in got
                            for f in findings(page, rule)))
        # The <svg> and <img> are their own rules'.
        self.assertTrue(findings(page, "bb-svg-name"))
        self.assertTrue(findings(page, "bb-img-alt"))

    def test_an_empty_tooltip_in_a_file_is_a_review(self):
        page = self.check('<div role="tooltip" id="t"></div>')
        self.assertEqual([f.verdict for f in findings(page, "bb-widget-name")],
                         [NEEDS_REVIEW])

    def test_hidden_widgets_are_not_checked(self):
        page = self.check('<div hidden><div role="tab"></div></div>'
                          '<div aria-hidden="true"><div role="tab"></div></div>')
        self.assertEqual(findings(page, "bb-widget-name"), [])


class TestControlRole(unittest.TestCase):
    """L19: a focusable generic element whose role names no known role has
    no role at all (F59)."""

    def test_a_misspelled_role_on_a_custom_control_fails(self):
        page = run_page(snapshot(
            '<div role="buton" tabindex="0">Go</div>'
            '<x-thing role="widget" tabindex="0">x</x-thing>'
            '<div role="buton">not focusable</div>'
            '<button role="buton">native</button>'
            '<div role="buton button" tabindex="0">valid fallback</div>'
            '<span role="buton" tabindex="-1">script focus only</span>'),
            "p.html", RB)
        failed = [f.snippet for f in findings(page, "bb-control-role")]
        self.assertEqual(failed, ['<div role="buton" tabindex="0">Go</div>',
                                  '<x-thing role="widget" tabindex="0">x</x-thing>'])
        # bb-aria-role reviews the others, and not these two again.
        reviewed = [f.snippet for f in findings(page, "bb-aria-role")]
        self.assertEqual(len(reviewed), 3)
        self.assertFalse(set(failed) & set(reviewed))


def in_page(html, fn, provenance=P):
    """Call `fn(ctx)` as a rule runs, with the capture's records honored."""
    ctx = CS.PageContext.parse(html, provenance_attr=provenance, reader="dom")
    a, b = PROVENANCE_ATTR.set(provenance), CURRENT_PAGE.set(ctx)
    try:
        return fn(ctx)
    finally:
        CURRENT_PAGE.reset(b)
        PROVENANCE_ATTR.reset(a)


class TestRecordDecidesHiding(unittest.TestCase):
    """L25: where the capture recorded what the page hides, that record
    decides, not the markup a stylesheet can override."""

    REC = attr(P + "-hidden", "recorded")

    def test_markup_hiding_a_stylesheet_undoes(self):
        html = snapshot('<nav id="n" hidden style="display:none"><a href="/a">A'
                        '</a></nav><video id="v" hidden autoplay controls '
                        'src="a.mp4"></video>', root=self.REC)
        def probe(ctx):
            nav, video = ctx.soup.find(id="n"), ctx.soup.find(id="v")
            return CS._hidden_here(nav), CS._controls_unusable(video)
        self.assertEqual(in_page(html, probe), (False, ""))
        # Without the record, markup decides.
        self.assertEqual(in_page(html, probe, provenance=None), (True, "hidden"))

    def test_hiding_the_record_shows(self):
        html = snapshot(
            f'<nav id="n"{attr(P + "-hidden", "display")}></nav>'
            f'<video id="v" autoplay controls src="a.mp4"'
            f'{attr(P + "-hidden", "display")}></video>', root=self.REC)
        def probe(ctx):
            nav, video = ctx.soup.find(id="n"), ctx.soup.find(id="v")
            return CS._hidden_here(nav), CS._controls_unusable(video)
        self.assertEqual(in_page(html, probe), (True, "hidden"))


class TestNarrowView(unittest.TestCase):
    """L24: a capture that also recorded what the page hides at phone width
    is evaluated with that record too."""

    ROOT_ATTRS = attr(P + "-hidden", "recorded") + attr(
        P + "-hidden-narrow", "recorded")

    def test_a_phone_only_menu_and_a_label_hidden_on_phones(self):
        html = snapshot(
            # Hidden at the capture's own width, shown on phones.
            f'<div class="m" aria-hidden="true"{attr(P + "-hidden", "display")}>'
            '<a href="/x">Menu link</a></div>'
            # The label shows at the capture's own width, not on phones.
            f'<button><svg aria-hidden="true"></svg><span'
            f'{attr(P + "-hidden-narrow", "display")}>Search</span></button>',
            root=self.ROOT_ATTRS)
        page = rerun(html)
        self.assertTrue(page.narrow)
        for rule in ("bb-aria-hidden-focus", "bb-button-name"):
            with self.subTest(rule=rule):
                got = [f for f in findings(page, rule) if f.verdict == FAIL]
                self.assertEqual(len(got), 1)
                self.assertIn(E.NARROW_NOTE, got[0].message)
        # One record only: neither shows.
        single = rerun(html.replace(attr(P + "-hidden-narrow", "recorded"), ""))
        self.assertFalse(single.narrow)
        self.assertFalse([f for f in findings(single, "bb-button-name")
                          if f.verdict == FAIL])

    def test_views_merge_one_finding_per_element(self):
        def f(verdict, msg, line=3):
            return Finding("bb-x", verdict, "serious", msg, line=line,
                           snippet="<a>", selector=["a"])
        main = RuleResult("bb-x", applicable=False,
                          findings=[f(NEEDS_REVIEW, "kept hidden")])
        narrow = RuleResult("bb-x", applicable=True,
                            findings=[f(FAIL, "shown"), f(FAIL, "other", 9)])
        got = E.merge_views(main, narrow)
        self.assertTrue(got.applicable)
        self.assertEqual([(x.verdict, x.message.split(" (")[0])
                          for x in got.findings],
                         [(FAIL, "shown"), (FAIL, "other")])
        same = E.merge_views(RuleResult("bb-x", True, [f(FAIL, "a")]),
                             RuleResult("bb-x", True, [f(FAIL, "b")]))
        self.assertEqual([x.message for x in same.findings], ["a"])
        broken = RuleResult("bb-x", False, errored="TypeError: x")
        self.assertEqual(E.merge_views(broken, narrow).errored, "TypeError: x")
        # Raised only with the narrow record: errored, and what the
        # capture's own record found is still reported (QR-14).
        got = E.merge_views(main, broken)
        self.assertTrue(got.errored.startswith("TypeError: x (with the page"))
        self.assertEqual(got.findings, main.findings)
        self.assertFalse(got.applicable)


class TestPlaceNarrow(unittest.TestCase):
    """The narrow record, taken after the capture, is written in by each
    element's index in the capture (fetch._place_narrow)."""

    IDX = F.index_attr(P)

    def capture(self):
        return (f'<!doctype html><html lang="en" {self.IDX}="0"><head '
                f'{self.IDX}="1"></head><body {self.IDX}="2"><nav {self.IDX}="3">'
                f'<a href="/" {self.IDX}="4">Home</a></nav><div {self.IDX}="5">'
                'w</div></body></html>')

    def test_marks_land_on_their_elements(self):
        info = {"recorded": True, "watched": True, "measured": True,
                "scrollWidth": 600, "clientWidth": 320, "bodyHidden": False,
                "clipped": False, "changed": [[4, "self"], [2, "bogus"], "x"],
                "marks": [[3, "display"], [4, "shown"], [9, "display"],
                          [5, "bogus"]],
                "reflow": [[5, '{"r":600,"k":"c"}'], [2, "not json"],
                           [3, '{"r":600,"x":false}']]}
        html, hiding, reflow = F._place_narrow(self.capture(), P, info, 0)
        self.assertEqual((hiding, reflow), (True, True))
        self.assertNotIn(self.IDX + '="', html)
        self.assertIn(f'<nav {P}-hidden-narrow="display">', html)
        self.assertIn(f'<a href="/" {P}-hidden-narrow="shown" '
                      f'{P}-narrow-changed="self">', html)
        self.assertIn(f'<div {P}-reflow="{{&quot;r&quot;:600,&quot;k&quot;:'
                      '&quot;c&quot;}">', html)
        self.assertIn(f'{P}-hidden-narrow="recorded"', html.split("<head")[0])
        self.assertIn(f'{P}-reflow-run=', html.split("<head")[0])
        page = rerun(html)
        self.assertTrue(page.narrow)
        self.assertEqual([f.selector for f in findings(page, "bb-reflow-320")],
                         [["body > div"]])

    def test_no_record_leaves_no_trace(self):
        for info, root in ((None, 0), ({"recorded": True, "watched": True,
                                        "marks": [[3, "display"]]}, None),
                           # What the page changed is not known: what it
                           # hides is not written either.
                           ({"recorded": True, "watched": False,
                             "marks": [[3, "display"]]}, 0)):
            html, hiding, reflow = F._place_narrow(self.capture(), P, info, root)
            self.assertNotIn(self.IDX + '="', html)
            self.assertNotIn("hidden-narrow", html)
            self.assertEqual((hiding, reflow), (False, False))


class TestReflow(unittest.TestCase):
    """L24: at 320 CSS pixels wide nothing makes the page scroll sideways."""

    def page(self, sw, marks="", cw=320, clipped=False):
        run = json.dumps({"width": 320, "height": 640, "scroll_width": sw,
                          "client_width": cw, "clipped": clipped})
        return rerun(snapshot(marks, root=attr(P + "-reflow-run", run)))

    def test_what_reaches_past_the_edge_fails(self):
        page = self.page(708, (
            f'<div class="wide"{attr(P + "-reflow", json.dumps({"r": 608, "k": "c"}))}>w</div>'
            f'<table{attr(P + "-reflow", json.dumps({"r": 708, "k": "x"}))}>'
            '<tr><td>1</td></tr></table>'
            f'<div class="row"{attr(P + "-reflow", json.dumps({"r": 335, "k": "e"}))}>r</div>'))
        got = [(f.verdict, f.impact, f.selector)
               for f in findings(page, "bb-reflow-320")]
        self.assertEqual(got, [(FAIL, "serious", ["body > main > div:nth-child(2)"]),
                               (NEEDS_REVIEW, "moderate", ["body > main > table"]),
                               (NEEDS_REVIEW, "minor", ["body > main > div:nth-child(4)"])])
        self.assertIn("608 px", findings(page, "bb-reflow-320")[0].message)

    def test_a_page_that_clips_its_overflow_does_not_scroll(self):
        # overflow-x: hidden or clip on the root element or the body (QR-5).
        page = self.page(600, clipped=True)
        self.assertEqual(results(page, "bb-reflow-320")[0].findings, [])
        self.assertTrue(results(page, "bb-reflow-320")[0].applicable)

    def test_an_overflow_it_cannot_place_still_fails(self):
        got = findings(self.page(400), "bb-reflow-320")
        self.assertEqual([(f.verdict, f.selector) for f in got],
                         [(FAIL, ["html"])])

    def test_a_page_that_fits_passes_and_none_is_not_evaluated(self):
        fits = self.page(321)
        self.assertEqual(results(fits, "bb-reflow-320")[0].findings, [])
        self.assertTrue(results(fits, "bb-reflow-320")[0].applicable)
        self.assertEqual(results(rerun(snapshot("")), "bb-reflow-320"), [])


SITE_PAGE = b"""<!doctype html><html lang="en"><head><title>Q</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>.low{color:#aaa;background:#fff}
@media (min-width: 768px) { .mobile-menu { display: none; } }
@media (max-width: 600px) { .label { display: none; } }
.wide { width: 600px; }</style></head><body>
<header><div class="mobile-menu" aria-hidden="true"><a href="/x">Menu link</a></div>
<button><svg aria-hidden="true" width="10" height="10"></svg><span class="label">Search</span></button></header>
<main><h1>Q</h1><p class="low">Low contrast text</p>
<ul><div>not an item</div><li>item</li></ul>
<div role="list"><span>no items</span></div>
<button style="width:10px;height:10px;padding:0;border:0" aria-label="a"></button><button style="width:10px;height:10px;padding:0;border:0" aria-label="b"></button>
<my-el></my-el><div id="host"></div><div class="wide">A line of text set in a column 600 pixels wide, which does not reflow</div></main>
<script>
const r = document.getElementById('host').attachShadow({mode:'closed'});
r.innerHTML = '<p style="color:#bbb;background:#fff">closed low</p>';
customElements.define('my-el', class extends HTMLElement { constructor(){ super();
  this.attachShadow({mode:'open'}).innerHTML='<p style="color:#ccc">open low</p>'; } });
%TAMPER%
</script></body></html>"""

#: Page code that tries to reach or bend the harness: everything axe-core
#: and the capture could consult in the page's own world, and the narrow
#: record's entry point, called with tokens of its own. (A getter for "d"
#: on Object.prototype is left out: Playwright's own page.evaluate, which
#: the scroll and settle steps still use (L21), reads one; the capture reads
#: its literal's own properties only.)
TAMPER = r"""
Array.prototype.map = function () { throw new Error('tampered'); };
Array.prototype.includes = function () { return false; };
window.getComputedStyle = function () { throw new Error('tampered'); };
JSON.parse = function () { return {}; };
window.axe = {run: function () { throw new Error('tampered'); }};
for (const k of ['axe', 'narrow', 'marks', 'attr', 'runAttr', 'run', 'p', 'k',
                 'roots', 'index', 'reflowAttr', 'reflowRunAttr', 'width',
                 'height']) {
  Object.defineProperty(Object.prototype, k, {configurable: true,
    get() { window.__touched = (window.__touched || 0) + 1; return undefined; }});
}
setInterval(() => {
  for (const name of Object.getOwnPropertyNames(window)) {
    if (/^__bb_capture_[0-9a-f]+(_narrow)?$/.test(name)) {
      // The entry points, with tokens of the page's own: a capture of its
      // own would make the narrow record name its elements (QR-3).
      try { window.__answers = (window.__answers || []).concat([
        window[name]('0'.repeat(32), 'data-x', '', '', null, {index: 'data-y'})]); } catch (e) {}
    }
  }
}, 20);
"""


#: A page whose script, once the window is narrowed, collapses its sidebar
#: for good (as Start Bootstrap's SB Admin 2 does): the capture must show
#: the page as loaded, and the narrow record what phones see.
RESIZES = b"""<!doctype html><html lang="en"><head><title>R</title><style>
.collapsed .brand-text { display: none; }</style></head><body>
<nav><a class="brand" href="/"><svg aria-hidden="true" width="8" height="8"></svg>
<span class="brand-text">Brand</span></a></nav><main><h1>R</h1></main>
<script>addEventListener('resize', () => {
  if (innerWidth < 600) document.body.classList.add('collapsed'); });</script>
</body></html>"""


@unittest.skipUnless(HAVE_BROWSER, _WHY)
class TestRenderedCapture(unittest.TestCase):
    """The whole path, in Chromium: axe-core in its own world, the narrow
    record, the capture's records, the rules, and a re-run."""

    @classmethod
    def setUpClass(cls):
        cls.site = _Site({
            "/": send(SITE_PAGE.replace(b"%TAMPER%", b"")),
            "/tampered": send(SITE_PAGE.replace(b"%TAMPER%", TAMPER.encode())),
            "/resizes": send(RESIZES)})

    @classmethod
    def tearDownClass(cls):
        cls.site.stop()

    def summary(self, page):
        return sorted((f.rule_id, f.verdict, tuple(f.selector or ()),
                       E.NARROW_NOTE in f.message)
                      for r in page.results for f in r.findings
                      if r.rule_id in RENDERED_CHECKS or E.NARROW_NOTE in f.message)

    def test_a_rendered_page_is_checked_and_a_rerun_reproduces_it(self):
        fr = F.fetch(self.site.base + "/", render=True)
        self.assertEqual(fr.mode, "rendered")
        self.assertTrue(fr.axe["ran"])
        self.assertEqual((fr.axe["version"], fr.axe["sha256"]),
                         (A.AXE_VERSION, A.AXE_SHA256))
        self.assertEqual(sorted(fr.axe["rules"]), sorted(A.AXE_RULES.values()))
        self.assertEqual(fr.narrow["viewport"], F.NARROW_VIEWPORT)
        self.assertTrue(fr.narrow["hiding_recorded"])
        page = run_page(fr.html, fr.final_url, RB,
                        provenance_attr=fr.provenance_attr, reader=fr.reader)
        got = self.summary(page)
        contrast = [s for s in got if s[0] == "bb-contrast-min"]
        # The document's text, the open root's and the closed root's.
        self.assertEqual({s[2] for s in contrast},
                         {("body > main > p",), ("body > main > my-el", "p"),
                          ("#host", "p")})
        self.assertIn(("bb-list", FAIL, ("body > main > ul",), False), got)
        self.assertIn(("bb-aria-required-children", FAIL,
                       ("body > main > div:nth-child(4)",), False), got)
        self.assertEqual(len([s for s in got if s[0] == "bb-target-size"]), 2)
        self.assertIn(("bb-reflow-320", FAIL,
                       ("body > main > div:nth-child(9)",), False), got)
        # What only a phone shows (L24).
        self.assertIn(("bb-aria-hidden-focus", FAIL,
                       ("body > header > div",), True), got)
        self.assertIn(("bb-button-name", FAIL, ("body > header > button",),
                       True), got)
        # The snapshot carries all of it: a re-run reads the same.
        again = run_page(fr.html, "snapshot.html", RB,
                         provenance_attr=fr.provenance_attr, reader="dom")
        self.assertEqual(self.summary(again), got)
        block = fr.fetch_block()
        self.assertEqual(block["axe"], fr.axe)
        self.assertEqual(block["narrow"], fr.narrow)

    def test_page_code_cannot_bend_or_reach_it(self):
        plain = F.fetch(self.site.base + "/", render=True)
        bent = F.fetch(self.site.base + "/tampered", render=True)
        self.assertTrue(bent.axe["ran"])
        self.assertTrue(bent.narrow["hiding_recorded"])
        def rule_summary(fr):
            page = run_page(fr.html, "x", RB,
                            provenance_attr=fr.provenance_attr, reader="dom")
            return [(s[0], s[1], s[2], s[3]) for s in self.summary(page)]
        self.assertEqual(rule_summary(bent), rule_summary(plain))

    def test_without_axe_core_its_rules_are_not_evaluated(self):
        saved = (A._SOURCE, A.AXE_SHA256)
        try:
            A._SOURCE, A.AXE_SHA256 = None, "0" * 64
            fr = F.fetch_rendered(self.site.base + "/")
        finally:
            A._SOURCE, A.AXE_SHA256 = saved
        self.assertFalse(fr.axe["ran"])
        self.assertIn("not the pinned", fr.axe["reason"])
        self.assertTrue(any("axe-core was not run" in n for n in fr.notes))
        page = run_page(fr.html, "x", RB, provenance_attr=fr.provenance_attr,
                        reader="dom")
        ran = {r.rule_id for r in page.results if r.rule_id in RENDERED_CHECKS}
        self.assertEqual(ran, {"bb-reflow-320"})

    def test_axe_core_that_runs_too_long_is_left_out(self):
        # A run that never settles (axe-core awaits its checks): the capture
        # goes on without it once the timeout passes.
        saved = A.RUNNER_JS
        try:
            A.RUNNER_JS = saved.replace("Promise.race([axe.run(",
                                        "Promise.race([new Promise(() => {}) || axe.run(")
            self.assertNotEqual(A.RUNNER_JS, saved)
            fr = F.fetch_rendered(self.site.base + "/", axe_timeout_ms=300,
                                  narrow=False)
        finally:
            A.RUNNER_JS = saved
        self.assertFalse(fr.axe["ran"])
        self.assertIn("did not finish", fr.axe["reason"])
        self.assertIsNone(fr.narrow)
        page = run_page(fr.html, "x", RB, provenance_attr=fr.provenance_attr,
                        reader="dom")
        self.assertFalse([r for r in page.results
                          if r.rule_id in RENDERED_CHECKS])

    def test_narrowing_does_not_change_what_was_captured(self):
        fr = F.fetch(self.site.base + "/resizes", render=True)
        self.assertNotIn('class="collapsed"', fr.html)   # the page as loaded
        page = run_page(fr.html, "x", RB, provenance_attr=fr.provenance_attr,
                        reader="dom")
        got = findings(page, "bb-link-name")
        self.assertEqual(len(got), 1)
        self.assertIn(E.NARROW_NOTE, got[0].message)

    def test_the_entry_points_answer_only_the_harness(self):
        from playwright.sync_api import sync_playwright
        token, ctoken = "ab" * 16, "cd" * 16
        with sync_playwright() as p:
            browser, _ = F._launch_chromium(p)
            try:
                pg = browser.new_page()
                pg.add_init_script(F.instrumentation_script(
                    "__bb_capture_t", narrow_token=token,
                    capture_token=ctoken))
                pg.goto(self.site.base + "/")
                answers = pg.evaluate("""([t, c]) => [
                    window.__bb_capture_t_narrow('0'.repeat(32)),
                    window.__bb_capture_t_narrow(t),
                    window.__bb_capture_t_narrow(t.toUpperCase()),
                    window.__bb_capture_t('0'.repeat(32), 'data-x', '', '',
                                          null, {index: 'data-y'}),
                    window.__bb_capture_t(c.toUpperCase(), 'data-x'),
                    window.__bb_capture_t_narrow(t)]""", [token, ctoken])
                taken = pg.evaluate("(c) => window.__bb_capture_t(c, 'data-x')"
                                    ".html.length > 0", ctoken)
            finally:
                browser.close()
        # Wrong tokens get nothing; the right one, before any capture, too:
        # a page cannot take a capture whose elements the narrow record then
        # names.
        self.assertEqual(answers, [None] * 6)
        self.assertTrue(taken)
        for bad in ({"narrow_token": "not hex"}, {"capture_token": "X" * 32}):
            with self.assertRaises(ValueError):
                F.instrumentation_script("__bb_t", **bad)

    def test_a_page_too_large_for_axe_core_keeps_its_capture(self):
        saved = A.MAX_PAGE_ELEMENTS
        try:
            A.MAX_PAGE_ELEMENTS = 10
            fr = F.fetch_rendered(self.site.base + "/")
        finally:
            A.MAX_PAGE_ELEMENTS = saved
        self.assertEqual(fr.mode, "rendered")
        self.assertFalse(fr.axe["ran"])
        self.assertIn("more than the 10 axe-core is run on", fr.axe["reason"])
        self.assertTrue(fr.narrow["hiding_recorded"])

    def test_every_wcag_rule_of_axe_core_is_classified(self):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser, _ = F._launch_chromium(p)
            try:
                pg = browser.new_page()
                pg.set_content("<p>x</p>")
                pg.add_script_tag(content=A.axe_source())
                rules = pg.evaluate("() => axe.getRules().map(r => "
                                    "({id: r.ruleId, tags: r.tags}))")
            finally:
                browser.close()
        wcag = {r["id"] for r in rules
                if set(r["tags"]) & set(A.WCAG_A_AA_TAGS)}
        self.assertEqual(wcag, set(A.AXE_RULES.values()) | set(A.NOT_RUN))
        tags = {r["id"]: set(r["tags"]) for r in rules}
        for rule in A.AXE_RULES.values():
            self.assertFalse(tags[rule] & {"experimental", "deprecated"}, rule)


if __name__ == "__main__":
    unittest.main(verbosity=2)
