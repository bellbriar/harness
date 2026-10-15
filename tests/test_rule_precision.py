"""Rule precision: false positives and false negatives, per rule.

Two contracts, each backed by a fixture and by small per-rule cases:

  fixtures/conformant-patterns.html — ARIA/ACT-conformant markup that is
      common on real sites. The static layer must report ZERO fail findings.
      A false fail here is what a customer's web lead sees first, and it is
      the fastest way to lose the room.

  fixtures/subtle-bad.html — real failures that used to pass as clean. A
      "TIER1-CLEAN, 100%" verdict on an empty button or a missing title is
      the scanner-green page that gets filed on.

The unit cases below mirror tests/test_lint.py: for each rule, the pattern
that must fail, and the neighbouring pattern that must not.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bellbriar_harness.accname import static_accname, subtree_text  # noqa: E402
from bellbriar_harness.checks_static import (                      # noqa: E402
    CHECKS, PageContext, check_aria_hidden_focus, check_aria_ref,
    check_button_name, check_heading_structure, check_iframe_title,
    check_img_alt, check_link_name, check_media_captions, check_page_title,
    check_redundant_links, check_table_headers)
from bellbriar_harness.engine import load_rulebook, run_paths                     # noqa: E402
from bellbriar_harness.model import (FAIL, MINOR, MODERATE,       # noqa: E402
                                     NEEDS_REVIEW, SERIOUS)
from bellbriar_harness.scoring import score_site                   # noqa: E402

FIXTURES = ROOT / "fixtures"


def ctx(html):
    return PageContext.parse(html)


def verdicts(rr):
    return [f.verdict for f in rr.findings]


# ---------------------------------------------------------------------------
# Fixture contracts
# ---------------------------------------------------------------------------

class TestConformantFixtureIsClean(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = run_paths([FIXTURES / "conformant-patterns.html"])
        cls.page = cls.report["pages"][0]

    def test_zero_fail_findings(self):
        fails = [(rr.rule_id, f.message) for rr in self.page.results
                 for f in rr.findings if f.verdict == FAIL]
        self.assertEqual(fails, [], "false positives on conformant markup")

    def test_tier1_clean_and_full_rate(self):
        site = score_site(self.report["pages"], self.report["rulebook"])
        self.assertTrue(site["pages"][0]["tier1_clean"])
        self.assertEqual(site["site_weighted_pass_rate"], 1.0)

    def test_only_the_expected_review_flags(self):
        reviews = {rr.rule_id for rr in self.page.results
                   for f in rr.findings if f.verdict == NEEDS_REVIEW}
        self.assertEqual(reviews, {"bb-redundant-links",   # logo then Home
                                   "bb-aria-ref",          # lazy panel
                                   "bb-table-headers",     # 2x2 key/value
                                   # a closed Bootstrap modal: hidden by its
                                   # class, which a file run cannot read
                                   "bb-aria-hidden-focus"})


class TestSubtleBadFixtureFails(unittest.TestCase):
    EXPECTED_FAILS = {
        "bb-button-name",       # ligature icon (A), comment-only (F), input (E)
        "bb-page-title",        # SVG <title> is not the document title (B)
        "bb-link-name",         # aria-hidden (D) or inline-hidden (H) text, role=link (J)
        "bb-aria-hidden-focus", # an editing host inside aria-hidden (I)
    }
    #: Detected, and reported for review: not WCAG failures on their own.
    EXPECTED_REVIEWS = {
        "bb-redundant-links",   # nested same-href pair (C)
        "bb-heading-structure", # heading text hidden from AT (G)
    }

    @classmethod
    def setUpClass(cls):
        cls.report = run_paths([FIXTURES / "subtle-bad.html"])
        cls.page = cls.report["pages"][0]

    def test_expected_rules_fail(self):
        failed = set(self.page.failed_rules())
        missing = self.EXPECTED_FAILS - failed
        self.assertFalse(missing, f"rules did not fail: {sorted(missing)}")

    def test_expected_patterns_are_reported_not_failed(self):
        reviewed = {rr.rule_id for rr in self.page.results
                    for f in rr.findings if f.verdict == NEEDS_REVIEW}
        self.assertFalse(self.EXPECTED_REVIEWS - reviewed)
        self.assertFalse(self.EXPECTED_REVIEWS & set(self.page.failed_rules()))

    def test_not_tier1_clean(self):
        site = score_site(self.report["pages"], self.report["rulebook"])
        self.assertFalse(site["pages"][0]["tier1_clean"])

    def test_three_unnamed_buttons(self):
        rr = next(r for r in self.page.results if r.rule_id == "bb-button-name")
        self.assertEqual(verdicts(rr).count(FAIL), 3)


# ---------------------------------------------------------------------------
# Accessible-name computation
# ---------------------------------------------------------------------------

class TestAccnameHiddenContent(unittest.TestCase):
    def test_aria_hidden_descendant_text_is_not_a_name(self):
        c = ctx('<button><i aria-hidden="true">menu</i></button>')
        self.assertEqual(static_accname(c.soup.button, c.soup, c.ids), "")

    def test_hidden_attribute_descendant_is_not_a_name(self):
        c = ctx('<button><span hidden>Save</span></button>')
        self.assertEqual(static_accname(c.soup.button, c.soup, c.ids), "")

    def test_comment_is_not_a_name(self):
        c = ctx('<button><!-- close --><svg aria-hidden="true"></svg></button>')
        self.assertEqual(static_accname(c.soup.button, c.soup, c.ids), "")

    def test_visible_text_beside_hidden_icon_is_the_name(self):
        c = ctx('<button><i aria-hidden="true">menu</i> Menu</button>')
        self.assertEqual(static_accname(c.soup.button, c.soup, c.ids), "Menu")

    def test_sr_only_span_is_a_name(self):
        c = ctx('<button><svg aria-hidden="true"></svg>'
                '<span class="sr-only">Menu</span></button>')
        self.assertEqual(static_accname(c.soup.button, c.soup, c.ids), "Menu")

    def test_labelledby_uses_a_hidden_target(self):
        """accname 2A: a hidden node *directly referenced* still contributes."""
        c = ctx('<span id="l" hidden>Search</span><input aria-labelledby="l">')
        self.assertEqual(static_accname(c.soup.input, c.soup, c.ids), "Search")

    def test_subtree_text_skips_script_and_template(self):
        c = ctx('<a href="/x"><script>var a=1</script><template>t</template>'
                'Go</a>')
        self.assertEqual(subtree_text(c.soup.a), "Go")


# ---------------------------------------------------------------------------
# Per-rule cases
# ---------------------------------------------------------------------------

class TestImgAlt(unittest.TestCase):
    def test_missing_alt_fails(self):
        self.assertEqual(verdicts(check_img_alt(ctx('<img src="a.png">'))), [FAIL])

    def test_role_presentation_passes(self):
        self.assertEqual(verdicts(check_img_alt(ctx(
            '<img src="a.png" role="presentation">'))), [])
        self.assertEqual(verdicts(check_img_alt(ctx(
            '<img src="a.png" role="none">'))), [])

    def test_aria_hidden_passes(self):
        self.assertEqual(verdicts(check_img_alt(ctx(
            '<img src="a.png" aria-hidden="true">'))), [])
        self.assertEqual(verdicts(check_img_alt(ctx(
            '<div aria-hidden="true"><img src="a.png"></div>'))), [])

    def test_aria_label_names_it(self):
        self.assertEqual(verdicts(check_img_alt(ctx(
            '<img src="a.png" aria-label="Chart">'))), [])

    def test_hidden_image_not_applicable(self):
        rr = check_img_alt(ctx('<img src="a.png" hidden>'))
        self.assertFalse(rr.applicable)


class TestLinkName(unittest.TestCase):
    def test_aria_hidden_image_link_in_card_passes(self):
        html = ('<a href="/p" aria-hidden="true" tabindex="-1">'
                '<img src="p.jpg" alt=""></a><a href="/p">Product</a>')
        self.assertEqual(verdicts(check_link_name(ctx(html))), [])

    def test_link_with_only_hidden_text_fails(self):
        self.assertEqual(verdicts(check_link_name(ctx(
            '<a href="/m"><span aria-hidden="true">Read more</span></a>'))),
            [FAIL])

    def test_empty_link_still_fails(self):
        self.assertEqual(verdicts(check_link_name(ctx(
            '<a href="/x"><span class="icon"></span></a>'))), [FAIL])


class TestButtonName(unittest.TestCase):
    def test_ligature_icon_button_fails(self):
        self.assertEqual(verdicts(check_button_name(ctx(
            '<button><i class="material-icons" aria-hidden="true">menu</i>'
            '</button>'))), [FAIL])

    def test_input_button_without_value_fails(self):
        self.assertEqual(verdicts(check_button_name(ctx(
            '<input type="button">'))), [FAIL])

    def test_input_submit_has_implicit_name(self):
        self.assertEqual(verdicts(check_button_name(ctx(
            '<input type="submit">'))), [])

    def test_input_button_with_value_passes(self):
        self.assertEqual(verdicts(check_button_name(ctx(
            '<input type="button" value="Go">'))), [])

    def test_button_in_closed_dialog_is_skipped(self):
        rr = check_button_name(ctx('<dialog><button></button></dialog>'))
        self.assertEqual(verdicts(rr), [])


class TestPageTitle(unittest.TestCase):
    def test_svg_title_is_not_the_document_title(self):
        html = ('<html><head></head><body><svg role="img"><title>Wave</title>'
                '</svg></body></html>')
        self.assertEqual(verdicts(check_page_title(ctx(html))), [FAIL])

    def test_head_title_passes(self):
        html = '<html><head><title>Home</title></head><body></body></html>'
        self.assertEqual(verdicts(check_page_title(ctx(html))), [])


class TestAriaRef(unittest.TestCase):
    def test_collapsed_disclosure_with_lazy_panel_is_review(self):
        rr = check_aria_ref(ctx('<button aria-expanded="false" '
                                'aria-controls="p">More</button>'))
        self.assertEqual(verdicts(rr), [NEEDS_REVIEW])

    def test_expanded_disclosure_with_missing_panel_is_review(self):
        # The button keeps its name, role and state; whether the panel
        # exists under another id is not provable from markup.
        rr = check_aria_ref(ctx('<button aria-expanded="true" '
                                'aria-controls="p">More</button>'))
        self.assertEqual(verdicts(rr), [NEEDS_REVIEW])

    def test_dangling_labelledby_that_leaves_no_name_is_the_link_rules(self):
        # bb-link-name fails the unnamed link; this rule reports the broken
        # reference (Part R2 review: one defect, one fail).
        rr = check_aria_ref(ctx('<a href="/c" aria-labelledby="nope"></a>'))
        self.assertEqual(verdicts(rr), [NEEDS_REVIEW])
        self.assertIn("bb-link-name decides", rr.findings[0].message)

    def test_dangling_labelledby_with_a_fallback_name_is_review(self):
        # Browsers fall back to the content: the link is still named "x".
        rr = check_aria_ref(ctx('<a href="/c" aria-labelledby="nope">x</a>'))
        self.assertEqual(verdicts(rr), [NEEDS_REVIEW])


class TestAriaHiddenFocus(unittest.TestCase):
    def test_hidden_attribute_container_passes(self):
        rr = check_aria_hidden_focus(ctx(
            '<div aria-hidden="true" hidden><a href="/a">A</a></div>'))
        self.assertEqual(verdicts(rr), [])

    def test_inline_display_none_passes(self):
        rr = check_aria_hidden_focus(ctx(
            '<div aria-hidden="true" style="display:none"><button>x</button>'
            '</div>'))
        self.assertEqual(verdicts(rr), [])

    def test_closed_dialog_passes(self):
        rr = check_aria_hidden_focus(ctx(
            '<dialog aria-hidden="true"><button>x</button></dialog>'))
        self.assertEqual(verdicts(rr), [])

    def test_closed_details_body_passes_but_summary_is_focusable(self):
        rr = check_aria_hidden_focus(ctx(
            '<div aria-hidden="true"><details><summary tabindex="-1">h'
            '</summary><a href="/x">x</a></details></div>'))
        self.assertEqual(verdicts(rr), [])
        rr2 = check_aria_hidden_focus(ctx(
            '<div aria-hidden="true"><details><summary>h</summary>'
            '</details></div>'))
        self.assertEqual(verdicts(rr2), [FAIL])

    def test_visible_focusable_inside_aria_hidden_still_fails(self):
        rr = check_aria_hidden_focus(ctx(
            '<div aria-hidden="true"><button>Hidden but focusable</button>'
            '</div>'))
        self.assertEqual(verdicts(rr), [FAIL])


class TestIframeTitle(unittest.TestCase):
    def test_gtm_noscript_frame_is_ignored(self):
        rr = check_iframe_title(ctx(
            '<noscript><iframe src="https://www.googletagmanager.com/ns.html"'
            ' height="0" width="0" style="display:none"></iframe></noscript>'))
        self.assertFalse(rr.applicable)

    def test_zero_size_frame_is_ignored(self):
        rr = check_iframe_title(ctx('<iframe src="/px" width="0" height="0">'
                                    '</iframe>'))
        self.assertFalse(rr.applicable)

    def test_visible_untitled_frame_fails(self):
        rr = check_iframe_title(ctx('<iframe src="https://maps.example.com">'
                                    '</iframe>'))
        self.assertEqual(verdicts(rr), [FAIL])


class TestTableHeaders(unittest.TestCase):
    def _table(self, rows, cols, th=False):
        cell = "<th scope=\"col\">h</th>" if th else "<td>x</td>"
        first = "<tr>" + cell * cols + "</tr>"
        rest = ("<tr>" + "<td>x</td>" * cols + "</tr>") * (rows - 1)
        return f"<table>{first}{rest}</table>"

    def test_small_headerless_table_is_review(self):
        self.assertEqual(verdicts(check_table_headers(ctx(self._table(2, 2)))),
                         [NEEDS_REVIEW])

    def test_large_headerless_table_fails(self):
        self.assertEqual(verdicts(check_table_headers(ctx(self._table(3, 3)))),
                         [FAIL])

    def test_large_table_with_headers_passes(self):
        self.assertEqual(verdicts(check_table_headers(
            ctx(self._table(3, 3, th=True)))), [])

    def test_presentation_table_not_applicable(self):
        rr = check_table_headers(ctx(
            '<table role="presentation"><tr><td>a</td><td>b</td><td>c</td>'
            '</tr><tr><td>d</td><td>e</td><td>f</td></tr><tr><td>g</td>'
            '<td>h</td><td>i</td></tr></table>'))
        self.assertFalse(rr.applicable)


class TestRedundantLinks(unittest.TestCase):
    """Redundant links are pled in complaints but are not a WCAG failure on
    their own (basis `policy`): reported for review, never failed. The H2
    shape is moderate impact, which --strict gates; the rest is minor."""

    def test_sibling_duplicates_are_reported_at_moderate_impact(self):
        rr = check_redundant_links(ctx(
            '<a href="/p"><img src="p.jpg" alt="P"></a><a href="/p">P</a>'))
        self.assertEqual(verdicts(rr), [NEEDS_REVIEW])
        self.assertEqual(rr.findings[0].impact, MODERATE)

    def test_nested_duplicates_in_a_card_are_reported_at_moderate_impact(self):
        rr = check_redundant_links(ctx(
            '<div class="card"><a href="/p"><img src="p.jpg" alt="P"></a>'
            '<h2><a href="/p">P</a></h2></div>'))
        self.assertEqual(verdicts(rr), [NEEDS_REVIEW])
        self.assertEqual(rr.findings[0].impact, MODERATE)

    def test_logo_then_home_across_landmarks_is_minor(self):
        rr = check_redundant_links(ctx(
            '<header><a href="/"><img src="l.svg" alt="Acme"></a>'
            '<nav><a href="/">Home</a></nav></header>'))
        self.assertEqual(verdicts(rr), [NEEDS_REVIEW])
        self.assertEqual(rr.findings[0].impact, MINOR)

    def test_hidden_image_link_treatment_passes(self):
        rr = check_redundant_links(ctx(
            '<div><a href="/p" aria-hidden="true" tabindex="-1">'
            '<img src="p.jpg" alt=""></a><h2><a href="/p">P</a></h2></div>'))
        self.assertEqual(verdicts(rr), [])

    def test_button_between_breaks_adjacency(self):
        rr = check_redundant_links(ctx(
            '<div><a href="/p">P</a><button>Add</button><a href="/p">P</a>'
            '</div>'))
        self.assertEqual(verdicts(rr), [])

    def test_different_destinations_pass(self):
        rr = check_redundant_links(ctx('<a href="/a">A</a><a href="/b">B</a>'))
        self.assertEqual(verdicts(rr), [])


class TestHeadingStructure(unittest.TestCase):
    def test_heading_with_only_hidden_text_is_empty(self):
        rr = check_heading_structure(ctx(
            '<h1>T</h1><h2><span aria-hidden="true">Services</span></h2>'))
        empty = [f for f in rr.findings if f.message.startswith("Empty heading")]
        self.assertEqual([f.verdict for f in empty], [NEEDS_REVIEW])
        self.assertEqual(empty[0].impact, SERIOUS)      # --strict gates it

    def test_hidden_heading_itself_is_skipped(self):
        rr = check_heading_structure(ctx('<h1>T</h1><h2 hidden></h2>'))
        self.assertNotIn(FAIL, verdicts(rr))


class TestMediaCaptions(unittest.TestCase):
    """Every finding is needs_review: markup cannot prove speech or visual
    information, but no video may pass silently at an AA target."""

    def test_uncaptioned_video_is_flagged_serious(self):
        rr = check_media_captions(ctx('<video src="a.mp4" controls></video>'))
        self.assertEqual(verdicts(rr), [NEEDS_REVIEW])
        self.assertEqual(rr.findings[0].impact, "serious")
        self.assertFalse(rr.failed)

    def test_captioned_video_still_asks_about_audio_description(self):
        rr = check_media_captions(ctx(
            '<video src="a.mp4" controls><track kind="captions" src="a.vtt" '
            'srclang="en" label="English"></video>'))
        self.assertEqual(verdicts(rr), [NEEDS_REVIEW])
        self.assertIn("1.2.5", rr.findings[0].message)

    def test_audio_asks_for_transcript(self):
        rr = check_media_captions(ctx('<audio src="a.mp3" controls></audio>'))
        self.assertIn("1.2.1", rr.findings[0].message)

    def test_video_embeds_are_flagged_but_maps_are_not(self):
        rr = check_media_captions(ctx(
            '<iframe src="https://www.youtube.com/embed/x" title="Tour"></iframe>'
            '<iframe src="https://maps.example.com/e" title="Map"></iframe>'))
        self.assertEqual(len(rr.findings), 1)

    def test_hidden_video_not_applicable(self):
        rr = check_media_captions(ctx('<div hidden><video src="a.mp4"></video></div>'))
        self.assertFalse(rr.applicable)


class TestCliOutputs(unittest.TestCase):
    """Exercise the CLI's own output paths.

    Nothing covered these, and a local variable named `render` shadowed the
    module-level report renderer for the whole of main() — so `--html`
    raised UnboundLocalError on every run while 185 tests stayed green. The
    report is a customer deliverable; it needs a test that actually writes
    one.
    """

    def _run(self, extra):
        import subprocess, sys, os
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
        return subprocess.run(
            [sys.executable, "-m", "bellbriar_harness",
             str(FIXTURES / "subtle-bad.html")] + extra,
            capture_output=True, text=True, env=env, cwd=str(ROOT))

    def test_html_report_is_written_and_is_html(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "r.html")
            r = self._run(["--html", out])
            # Nothing on stderr but the count of files evaluated (P1-04).
            self.assertEqual(r.stderr, "[bellbriar] evaluated 1 file(s)\n",
                             r.stderr)
            self.assertTrue(os.path.exists(out), "no HTML report written")
            html = Path(out).read_text()
            self.assertTrue(html.startswith("<!doctype html"))
            self.assertIn("Coverage.", html)

    def test_html_report_passes_the_harness_it_reports_for(self):
        """report_html.py promises the report satisfies the harness. A report
        that fails our own Tier-1 rules would be indefensible."""
        import tempfile, os
        from bellbriar_harness.engine import load_rulebook, run_page
        from bellbriar_harness.scoring import score_site
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "r.html")
            self._run(["--html", out])
            page = run_page(Path(out).read_text(), out, load_rulebook())
            site = score_site([page], load_rulebook())
            fails = [(rr.rule_id, f.message) for rr in page.results
                     for f in rr.findings if f.verdict == FAIL]
            self.assertEqual(fails, [], "our own report fails our own rules")
            self.assertTrue(site["pages"][0]["tier1_clean"])

    def test_json_report_is_written_and_parses(self):
        import tempfile, os, json
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "r.json")
            r = self._run(["--json", out])
            # Nothing on stderr but the count of files evaluated (P1-04).
            self.assertEqual(r.stderr, "[bellbriar] evaluated 1 file(s)\n",
                             r.stderr)
            data = json.loads(Path(out).read_text())
            for key in ("tool", "rulebook_version", "layers", "coverage_note",
                        "site", "pages"):
                self.assertIn(key, data)
            self.assertEqual(data["site"]["tier1_rules_total"],
                             sum(1 for r in load_rulebook()["rules"]
                                 if r.get("tier") == 1))

    def test_both_outputs_together(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as d:
            h, j = os.path.join(d, "r.html"), os.path.join(d, "r.json")
            r = self._run(["--html", h, "--json", j])
            self.assertEqual(r.returncode, 1)          # tier-1 failures present
            self.assertTrue(os.path.exists(h) and os.path.exists(j))

    def test_clean_page_exits_zero(self):
        import subprocess, sys, os
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
        r = subprocess.run([sys.executable, "-m", "bellbriar_harness",
                            str(FIXTURES / "conformant-patterns.html")],
                           capture_output=True, text=True, env=env, cwd=str(ROOT))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class TestEveryCheckStillRuns(unittest.TestCase):
    def test_on_both_fixtures(self):
        for name in ("conformant-patterns.html", "subtle-bad.html"):
            c = PageContext.parse((FIXTURES / name).read_text())
            for rule_id, fn in CHECKS.items():
                self.assertEqual(fn(c).rule_id, rule_id)


if __name__ == "__main__":
    unittest.main(verbosity=2)
