import contextlib
import io
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bellbriar_harness.lint import ERROR, WARN, lint_text, main  # noqa: E402

FIXTURES = ROOT / "fixtures"


def ids(findings):
    return {f.rule_id for f in findings}


def run(text, path="x.jsx"):
    return lint_text(text, path)


class TestRules(unittest.TestCase):
    def test_bad_fixture_hits_every_expected_rule(self):
        text = (FIXTURES / "lint-bad.jsx").read_text()
        got = ids(run(text, str(FIXTURES / "lint-bad.jsx")))
        expected = {
            "bl-zoom-block", "bl-anchor-button", "bl-aria-expanded-link",
            "bl-menu-role", "bl-div-click", "bl-outline-none-class",
            "bl-tabindex-noninteractive", "bl-css-order", "bl-junk-alt-src",
            "bl-downevent-activation", "bl-icon-button-name",
            "bl-placeholder-label", "bl-autoplay-media",
            "bl-carousel-autoplay", "bl-positive-tabindex",
            "bl-conditional-live-region", "bl-autofocus", "bl-doc-link",
            "bl-dangerous-html", "bl-button-type",
        }
        missing = expected - got
        self.assertFalse(missing, f"rules did not fire: {sorted(missing)}")

    def test_good_fixture_is_clean(self):
        text = (FIXTURES / "lint-good.jsx").read_text()
        self.assertEqual(run(text, str(FIXTURES / "lint-good.jsx")), [])

    def test_div_click_downgrades_with_role(self):
        f = run('<div role="button" tabIndex={-1} onClick={go}>x</div>')
        d = [x for x in f if x.rule_id == "bl-div-click"]
        self.assertEqual(len(d), 1)
        self.assertEqual(d[0].severity, WARN)
        f2 = run('<div onClick={go}>x</div>')
        self.assertEqual([x.severity for x in f2
                          if x.rule_id == "bl-div-click"], [ERROR])

    def test_outline_none_class_ok_with_focus_visible(self):
        ok = run('<button type="button" className="outline-none '
                 'focus-visible:ring-2">x</button>')
        self.assertEqual([x for x in ok
                          if x.rule_id == "bl-outline-none-class"], [])
        bad = run('<button type="button" className="focus:outline-none">x'
                  '</button>')
        self.assertEqual([x.severity for x in bad
                          if x.rule_id == "bl-outline-none-class"], [ERROR])

    def test_css_outline_downgrade_when_replacement_in_file(self):
        css_bad = "button:focus { outline: none; }"
        f = run(css_bad, "a.css")
        self.assertEqual([x.severity for x in f
                          if x.rule_id == "bl-outline-none-css"], [ERROR])
        css_ok = ("button:focus { outline: none; }\n"
                  "button:focus-visible { outline: 2px solid blue; }")
        f2 = run(css_ok, "a.css")
        self.assertEqual([x.severity for x in f2
                          if x.rule_id == "bl-outline-none-css"], [WARN])

    def test_video_muted_variants(self):
        loud = run('<video autoPlay src="a.mp4" />')
        self.assertEqual([x.severity for x in loud
                          if x.rule_id == "bl-autoplay-media"], [ERROR])
        muted = run('<video autoPlay muted src="a.mp4" />')
        self.assertEqual([x.severity for x in muted
                          if x.rule_id == "bl-autoplay-media"], [WARN])
        fine = run('<video autoPlay muted controls src="a.mp4" />')
        self.assertEqual([x for x in fine
                          if x.rule_id == "bl-autoplay-media"], [])

    def test_suppression_comments(self):
        s = ("// bellbriar-lint-disable-next-line bl-div-click\n"
             "<div onClick={go}>x</div>")
        self.assertEqual(run(s), [])
        s2 = "<div onClick={go}>x</div> // bellbriar-lint-disable-line"
        self.assertEqual(run(s2), [])
        s3 = ("// bellbriar-lint-disable-next-line bl-doc-link\n"
              "<div onClick={go}>x</div>")  # wrong id → still fires
        self.assertEqual(len(run(s3)), 1)

    def test_conditional_live_region_multiline(self):
        s = "{msg &&\n  (<div\n    role=\"status\">{msg}</div>)}"
        self.assertIn("bl-conditional-live-region", ids(run(s)))
        ok = '<div role="status" className="sr-only">{msg}</div>'
        self.assertNotIn("bl-conditional-live-region", ids(run(ok)))

    def test_non_source_ext_ignored(self):
        self.assertEqual(run("<div onClick={x}>", "notes.md"), [])


class TestPrecision(unittest.TestCase):
    """False positives found in review, each paired with the true positive
    that must keep firing. A lint that blocks correct code at `error`
    teaches people to disable it."""

    def test_icon_plus_visible_text_is_named(self):
        self.assertNotIn("bl-icon-button-name",
                         ids(run('<button type="button"><SaveIcon /> Save</button>')))

    def test_icon_plus_sr_only_text_is_named(self):
        self.assertNotIn("bl-icon-button-name", ids(run(
            '<button type="button"><CloseIcon aria-hidden="true" />'
            '<span className="sr-only">Close</span></button>')))

    def test_icon_plus_jsx_expression_is_assumed_named(self):
        self.assertNotIn("bl-icon-button-name",
                         ids(run('<button type="button"><Icon />{label}</button>')))

    def test_icon_only_button_still_fires(self):
        self.assertIn("bl-icon-button-name",
                      ids(run('<button type="button"><SaveIcon /></button>')))
        self.assertIn("bl-icon-button-name",
                      ids(run('<button type="button"><svg aria-hidden="true"/></button>')))

    def test_aria_labelled_icon_button_is_clean(self):
        self.assertNotIn("bl-icon-button-name", ids(run(
            '<button type="button" aria-label="Save"><SaveIcon /></button>')))

    def test_component_button_does_not_need_type(self):
        self.assertNotIn("bl-button-type",
                         ids(run('<Button onClick={go}>Save changes</Button>')))
        self.assertIn("bl-button-type", ids(run('<button onClick={go}>Save</button>')))

    def test_menu_role_outside_nav_is_a_warning(self):
        f = run('<ul role="menu"><li role="menuitem">Rename</li></ul>')
        self.assertEqual({x.severity for x in f if x.rule_id == "bl-menu-role"},
                         {WARN})

    def test_menu_role_inside_nav_is_an_error(self):
        f = run('<nav><ul role="menu"><li role="menuitem"><a href="/x">X</a>'
                '</li></ul></nav>')
        self.assertEqual({x.severity for x in f if x.rule_id == "bl-menu-role"},
                         {ERROR})

    def test_i18n_key_containing_image_is_not_junk_alt(self):
        self.assertNotIn("bl-junk-alt-src",
                         ids(run("<img src={hero} alt={t('home.hero.image.alt')} />")))

    def test_image_object_as_alt_still_fires(self):
        self.assertIn("bl-junk-alt-src",
                      ids(run('<img src={p.image} alt={p.image} />')))
        self.assertIn("bl-junk-alt-src",
                      ids(run('<img src={p.image} alt={p.img.src} />')))

    def test_sort_parameter_is_not_css_order(self):
        self.assertNotIn("bl-css-order",
                         ids(run("<List query={{ sort: 'name', order: 1 }} />")))

    def test_inline_style_order_still_fires(self):
        self.assertIn("bl-css-order", ids(run('<div style={{ order: 3 }}>x</div>')))
        self.assertIn("bl-css-order", ids(run('<div style="order: 2">x</div>')))
        self.assertIn("bl-css-order", ids(run('<div className="order-2">x</div>')))

    def test_css_file_order_still_fires(self):
        self.assertIn("bl-css-order", ids(run('.a { order: 1; }', 'a.css')))


def run_cli(argv):
    """Invoke the lint CLI and capture what it wrote.

    The CLI prints a full report; left uncaptured, two of those bury a real
    failure under a few hundred lines of JSON, which is exactly when the
    output matters most. Capturing also lets the assertions below check what
    was printed rather than only the exit code.
    """
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class TestCli(unittest.TestCase):
    def setUp(self):
        self.bad = str(FIXTURES / "lint-bad.jsx")
        self.good = str(FIXTURES / "lint-good.jsx")

    def test_clean_file_exits_zero(self):
        code, out, _ = run_cli([self.good])
        self.assertEqual(code, 0)
        self.assertIn("0 error(s)", out)

    def test_errors_exit_one(self):
        code, _, _ = run_cli([self.bad, "--format", "json"])
        self.assertEqual(code, 1)

    def test_fail_on_never_exits_zero(self):
        code, _, _ = run_cli([self.bad, "--fail-on", "never",
                              "--format", "json"])
        self.assertEqual(code, 0)

    def test_json_output_is_valid_and_complete(self):
        """The JSON report is a machine interface — CI and the delivery-note
        workflow read it, so its shape is part of the contract."""
        _, out, _ = run_cli([self.bad, "--format", "json"])
        data = json.loads(out)
        self.assertEqual(data["files_scanned"], 1)
        self.assertGreater(data["errors"], 0)
        self.assertEqual(len(data["findings"]), data["errors"] + data["warnings"])
        for f in data["findings"]:
            with self.subTest(rule=f["rule_id"]):
                self.assertEqual(
                    set(f) >= {"rule_id", "severity", "path", "line",
                               "message", "ref", "snippet"}, True)
                self.assertIn(f["severity"], (ERROR, WARN))
                self.assertIsInstance(f["line"], int)

    def test_nothing_leaks_to_stdout_in_json_mode(self):
        """Anything printed beside the JSON makes the output unparseable for
        a caller that pipes it."""
        _, out, _ = run_cli([self.bad, "--format", "json"])
        self.assertTrue(out.lstrip().startswith("{"))
        json.loads(out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
