"""Regression tests for the fixes from the Sept 2026 pre-ship review.

Each class names the review finding it pins. They exist so that a finding,
once fixed, cannot come back without a red test.
"""
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
# The reference signing service and its client are not part of the
# installed package (D3, L2): they live in tools/.
sys.path.insert(0, str(ROOT / "tools"))
import reference_signer as R                                  # noqa: E402

from bellbriar_harness.checks_static import PageContext, check_meta_refresh  # noqa: E402
from tests.bundle_body import BODY  # noqa: E402
from bellbriar_harness.engine import (VERDICT_BASES, load_rulebook,  # noqa: E402
                                      validate_rulebook)
from bellbriar_harness.lint import (ERROR, WARN, collect, lint_text,  # noqa: E402
                                    main as lint_main)
from bellbriar_harness.model import FAIL  # noqa: E402

EXAMPLES = ROOT / "examples" / "evidence"
GUIDE = ROOT / "docs" / "MEASUREMENT-AND-EVIDENCE-GUIDE.md"


def _flat(path: Path) -> str:
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))


class TestP1_02_CryptographyIsARealDependency(unittest.TestCase):
    """A clean install printed INVALID for the valid example bundle."""

    def test_pyproject_declares_cryptography(self):
        text = (ROOT / "pyproject.toml").read_text()
        deps = re.search(r"^dependencies\s*=\s*\[(.*?)\]", text, re.M | re.S)
        self.assertIsNotNone(deps)
        self.assertIn("cryptography", deps.group(1))

    def _verify_without_cryptography(self, bundle_path: Path) -> subprocess.CompletedProcess:
        code = (
            "import sys\n"
            "for m in ['cryptography', 'cryptography.hazmat',"
            " 'cryptography.hazmat.primitives',"
            " 'cryptography.hazmat.primitives.asymmetric']:\n"
            "    sys.modules[m] = None\n"
            f"sys.path.insert(0, {str(ROOT / 'src')!r})\n"
            "from bellbriar_harness import evidence_cli\n"
            f"sys.exit(evidence_cli.main(['verify', {str(bundle_path)!r},"
            f" '--public-key', {str(EXAMPLES / 'reference-public-key.hex')!r}]))\n")
        return subprocess.run([sys.executable, "-c", code], capture_output=True,
                              text=True, timeout=120)

    def test_missing_dependency_is_not_reported_as_invalid(self):
        r = self._verify_without_cryptography(EXAMPLES / "signed-bundle-example.json")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("CANNOT VERIFY", r.stdout)
        self.assertNotIn("INVALID", r.stdout)

    def test_malformed_bundle_exits_two_not_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text('{"signature": "not-an-object"}')
            from bellbriar_harness import evidence_cli
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = evidence_cli.main(["verify", str(bad), "--public-key",
                                          str(EXAMPLES / "reference-public-key.hex")])
            self.assertEqual(code, 2, out.getvalue())
            self.assertIn("CANNOT VERIFY", out.getvalue())


class TestP3_09_LintFindsFilesUnderBuildFolders(unittest.TestCase):
    """Bitbucket Pipelines clones into .../pipelines/agent/build; every file
    was skipped and the run exited 0 after scanning nothing."""

    def test_checkout_under_a_build_folder_is_scanned(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "opt" / "atlassian" / "pipelines" / "agent" / "build" / "src"
            src.mkdir(parents=True)
            (src / "App.tsx").write_text("<div onClick={go}>x</div>")
            self.assertEqual(len(collect([str(src)])), 1)

    def test_build_folders_inside_the_tree_are_still_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "dist").mkdir()
            (root / "dist" / "bundle.js").write_text("x")
            (root / "App.tsx").write_text("x")
            self.assertEqual([p.name for p in collect([str(root)])], ["App.tsx"])

    def _run(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = lint_main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_nothing_to_lint_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "notes.py").write_text("x = 1\n")
            code, _, err = self._run([tmp])
            self.assertEqual(code, 2)
            self.assertIn("no lintable files", err)

    def test_allow_empty_opts_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _, _ = self._run([tmp, "--allow-empty"])
            self.assertEqual(code, 0)


class TestP3_08_LintDoesNotBlockCorrectCode(unittest.TestCase):
    """bellbriar-lint raised ERRORs, which fail --fail-on error, on correct
    React and Tailwind code. Each case is paired with the true positive that
    must keep firing."""

    REVIEW_CASES = [
        ("x.tsx", '<a onClick={() => track("nav")} href="/pricing">Pricing</a>'),
        ("x.tsx", '<div onClick={() => go()} role="button" tabIndex={0} '
                  'onKeyDown={onKey}>Go</div>'),
        ("x.html", '<button class="focus:outline-none focus:ring-2" '
                   'type="button">Save</button>'),
        ("x.tsx", 'return (<form>{errors.email && <p role="alert">'
                  '{errors.email.message}</p>}</form>)'),
        ("x.tsx", '<div className="dialog" onClick={(e) => e.stopPropagation()}>'
                  'Body</div>'),
        ("x.tsx", '<a href="/about" aria-expanded="false">About</a>'),
        ("x.html", '<meta http-equiv="refresh" '
                   'content="0; url=https://example.com/new">'),
    ]

    def _sev(self, src, rule, path="x.tsx"):
        return sorted(f.severity for f in lint_text(src, path)
                      if f.rule_id == rule)

    def test_review_cases_raise_no_errors(self):
        for path, src in self.REVIEW_CASES:
            with self.subTest(src=src):
                errors = [f.rule_id for f in lint_text(src, path)
                          if f.severity == ERROR]
                self.assertEqual(errors, [])

    def test_arrow_function_does_not_end_the_tag(self):
        # The scan stopped at the '>' of '=>' and never saw the href.
        self.assertEqual(self._sev('<a onClick={() => track("nav")} '
                                   'href="/pricing">Pricing</a>',
                                   "bl-anchor-button"), [])
        self.assertEqual(self._sev('<a onClick={() => open()}>Open</a>',
                                   "bl-anchor-button"), [ERROR])
        self.assertEqual(self._sev('<a href="#" onClick={() => open()}>Open</a>',
                                   "bl-anchor-button"), [ERROR])

    def test_attributes_after_an_arrow_function_are_seen(self):
        self.assertEqual(self._sev('<div onClick={() => go()} role="button">Go</div>',
                                   "bl-div-click"), [WARN])
        self.assertEqual(self._sev('<div onClick={() => go()}>Go</div>',
                                   "bl-div-click"), [ERROR])
        menu = ('<button onClick={() => x()} aria-label="Menu" type="button">'
                '<MenuIcon /></button>')
        self.assertEqual(self._sev(menu, "bl-button-type"), [])
        self.assertEqual(self._sev(menu, "bl-icon-button-name"), [])

    def test_comparisons_strings_and_elements_inside_attributes(self):
        src = ('<a onClick={() => { if (n > 0) setOpen(true); }}\n'
               '   title="a > b" render={() => <b>Don\'t</b>}\n'
               '   href="/next">Next</a>')
        self.assertEqual(self._sev(src, "bl-anchor-button"), [])
        self.assertEqual(self._sev(src.replace('href="/next"', ''),
                                   "bl-anchor-button"), [ERROR])

    def test_a_tag_that_never_closes_is_still_checked(self):
        # An unterminated string inside braces: the scanner cannot follow
        # the tag, so it falls back to the first '>' instead of skipping it.
        src = '<div onClick={go} data-x={"unterminated}>x</div>'
        self.assertEqual(self._sev(src, "bl-div-click"), [ERROR])

    def test_tailwind_focus_replacements_are_accepted(self):
        for cls in ("focus:outline-none focus:ring-2",
                    "outline-none focus-visible:ring-2 focus-visible:ring-offset-2",
                    # Tailwind UI inputs; the forms plugin draws the ring
                    "focus:outline-none focus:ring-indigo-500 focus:border-indigo-500",
                    "focus:outline-none focus:shadow-outline",   # Tailwind 1.x
                    "focus:outline-none focus:border-blue-500",
                    # Flowbite toggle: the ring is drawn when the peer is focused
                    "peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300",
                    "md:focus-visible:!ring-2 outline-none",
                    "tw-outline-none focus-visible:tw-ring-2"):  # prefixed build
            with self.subTest(cls=cls):
                src = f'<button type="button" class="{cls}">Save</button>'
                self.assertEqual(self._sev(src, "bl-outline-none-class",
                                           "x.html"), [])

    def test_outline_none_without_a_replacement_still_fails(self):
        for cls in ("focus:outline-none",
                    "outline-none focus:ring-0",
                    "outline-none ring-2",   # always on: marks nothing
                    "focus:outline-none focus-visible:outline-none",
                    "focus:outline-none focus:ring-offset-2"):
            with self.subTest(cls=cls):
                src = f'<button type="button" class="{cls}">Save</button>'
                self.assertEqual(self._sev(src, "bl-outline-none-class",
                                           "x.html"), [ERROR])

    def test_color_only_focus_change_is_a_warning(self):
        src = '<a href="/x" class="outline-none focus:bg-gray-100">X</a>'
        self.assertEqual(self._sev(src, "bl-outline-none-class", "x.html"),
                         [WARN])

    def test_indicator_on_a_related_element_is_a_warning(self):
        wrapper = ('<div class="rounded border focus-within:ring-2">'
                   '<input class="outline-none" aria-label="Search"></div>')
        self.assertEqual(self._sev(wrapper, "bl-outline-none-class", "x.html"),
                         [WARN])
        peer = ('<input type="checkbox" class="peer outline-none" id="t">'
                '<label for="t" class="peer-focus-visible:ring-2">On</label>')
        self.assertEqual(self._sev(peer, "bl-outline-none-class", "x.html"),
                         [WARN])
        group = ('<a href="/p" class="group outline-none">'
                 '<img src="p.jpg" alt="Product" class="group-focus:ring-2"></a>')
        self.assertEqual(self._sev(group, "bl-outline-none-class", "x.html"),
                         [WARN])

    def test_related_indicator_covers_only_its_own_elements(self):
        # One wrapper in a file must not excuse every outline-none in it.
        src = ('<div class="rounded border focus-within:ring-2">'
               '<input class="outline-none" aria-label="Search"></div>\n'
               '<button type="button" class="px-2 focus:outline-none">Close</button>\n'
               '<a href="/q" class="group outline-none">Q</a>\n'
               '<input class="peer outline-none" aria-label="Q">')
        self.assertEqual(self._sev(src, "bl-outline-none-class", "x.html"),
                         [ERROR, ERROR, ERROR, WARN])

    def test_self_closing_button_with_spread_props_is_not_empty(self):
        forwarded = ('const B = (props) => <button type="button" '
                     '{...props} />;')
        self.assertEqual(self._sev(forwarded, "bl-icon-button-name"), [])
        self.assertEqual(self._sev('<button type="button" />',
                                   "bl-icon-button-name"), [WARN])

    def test_hover_only_outline_removal_is_not_flagged(self):
        src = '<a href="/x" class="hover:outline-none">X</a>'
        self.assertEqual(self._sev(src, "bl-outline-none-class", "x.html"), [])

    def test_conditional_alert_warns_and_conditional_status_fails(self):
        rhf = ('return (<form>{errors.email && <p role="alert">'
               '{errors.email.message}</p>}</form>)')
        self.assertEqual(self._sev(rhf, "bl-conditional-live-region"), [WARN])
        self.assertEqual(self._sev('{saved && <p role="status">Saved</p>}',
                                   "bl-conditional-live-region"), [ERROR])
        after_arrow = ('{open ? <div onClick={() => hide()} role="status">'
                       'Saved</div> : null}')
        self.assertEqual(self._sev(after_arrow, "bl-conditional-live-region"),
                         [ERROR])

    def test_stop_propagation_handler_is_a_warning(self):
        for handler in ("(e) => e.stopPropagation()",
                        "e => { e.stopPropagation(); }",
                        "(e: React.MouseEvent<HTMLDivElement>) => e.stopPropagation()",
                        "stopPropagation"):
            with self.subTest(handler=handler):
                src = f'<div className="dialog" onClick={{{handler}}}>Body</div>'
                self.assertEqual(self._sev(src, "bl-div-click"), [WARN])
        self.assertEqual(self._sev('<div onclick="event.stopPropagation()">x</div>',
                                   "bl-div-click", "x.html"), [WARN])
        does_more = '<div onClick={(e) => { e.stopPropagation(); close(); }}>x</div>'
        self.assertEqual(self._sev(does_more, "bl-div-click"), [ERROR])

    def test_aria_hidden_backdrop_is_a_warning(self):
        backdrop = '<div aria-hidden="true" className="fixed inset-0" onClick={close} />'
        self.assertEqual(self._sev(backdrop, "bl-div-click"), [WARN])
        self.assertEqual(self._sev('<div aria-hidden="false" onClick={close}>x</div>',
                                   "bl-div-click"), [ERROR])

    def test_aria_expanded_link_is_a_warning(self):
        self.assertEqual(self._sev('<a href="/about" aria-expanded="false">About</a>',
                                   "bl-aria-expanded-link"), [WARN])

    def test_meta_refresh_matches_the_eval_rule(self):
        for content, want in (("0; url=/new", []), ("0", []), ("72001", []),
                              ("5; url=/login", [ERROR]), ("72000", [ERROR])):
            with self.subTest(content=content):
                src = f'<meta http-equiv="refresh" content="{content}">'
                self.assertEqual(self._sev(src, "bl-meta-refresh", "x.html"), want)
        self.assertEqual(self._sev('<META HTTP-EQUIV="Refresh" CONTENT="30; URL=/x">',
                                   "bl-meta-refresh", "x.html"), [ERROR])
        self.assertEqual(self._sev('<meta httpEquiv="refresh" content="5;url=/x" />',
                                   "bl-meta-refresh"), [ERROR])
        self.assertEqual(self._sev('<meta httpEquiv="refresh" content={delay} />',
                                   "bl-meta-refresh"), [WARN])


class TestP5_02_EveryFailSaysWhatItMeans(unittest.TestCase):
    """The guide claimed every fail but one was a WCAG violation."""

    def setUp(self):
        self.rb = load_rulebook()
        self.static = [r for r in self.rb["rules"] if r.get("status") == "implemented"
                       and r.get("layer") == "static-dom"]

    def test_every_static_rule_declares_a_basis(self):
        for r in self.static:
            with self.subTest(rule=r["id"]):
                self.assertIn(r.get("verdict_basis"), VERDICT_BASES)

    def test_validation_rejects_a_rulebook_without_a_basis(self):
        rb = json.loads(json.dumps(self.rb))
        for r in rb["rules"]:
            r.pop("verdict_basis", None)
        with self.assertRaises(RuntimeError):
            validate_rulebook(rb)

    def test_guide_names_every_rule_whose_fail_is_not_a_violation(self):
        guide = _flat(GUIDE)
        for r in self.static:
            if r["verdict_basis"] in ("policy", "heuristic", "best-practice"):
                with self.subTest(rule=r["id"]):
                    self.assertIn(f"`{r['id']}`", guide)

    def test_guide_no_longer_claims_every_other_fail_is_a_violation(self):
        self.assertNotIn("Every other fail is a success-criterion violation",
                         _flat(GUIDE))

    def test_reports_label_the_basis(self):
        from bellbriar_harness.cli import main as eval_main
        card = ('<!doctype html><html lang="en"><head><title>t</title></head>'
                '<body><main><h1>x</h1><div class="card"><a href="/p/1">'
                '<img src="p.jpg" alt="Shirt"></a><h3><a href="/p/1">Shirt</a>'
                '</h3></div></main></body></html>')
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp) / "p.html"
            page.write_text(card)
            j, h = Path(tmp) / "r.json", Path(tmp) / "r.html"
            with contextlib.redirect_stdout(io.StringIO()):
                eval_main([str(page), "--json", str(j), "--html", str(h),
                           "--fail-on", "never"])
            data = json.loads(j.read_text())
            # Rulebook 0.3.0: a policy rule never FAILs. The report says
            # what the finding is, in the words customer reports use.
            found = [f for f in data["pages"][0]["findings"]
                     if f["rule_id"] == "bb-redundant-links"]
            self.assertTrue(found)
            self.assertEqual({f["verdict"] for f in found}, {"needs_review"})
            self.assertEqual(found[0]["verdict_basis"], "policy")
            note = "pled in complaints; not a WCAG failure on its own"
            self.assertIn(note, found[0]["message"])
            self.assertIn(note, h.read_text())
            self.assertNotIn("FAIL (policy)", h.read_text())

    def test_a_probable_failure_is_labeled_as_one(self):
        """A heuristic FAIL — WCAG probably violated — keeps its label."""
        from bellbriar_harness.cli import main as eval_main
        bare = ('<!doctype html><html lang="en"><head><title>t</title></head>'
                '<body><nav>' + "".join(f'<a href="/{i}">L{i}</a>'
                                        for i in range(3))
                + '</nav><div><p>Body</p></div></body></html>')
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp) / "p.html"
            page.write_text(bare)
            h = Path(tmp) / "r.html"
            with contextlib.redirect_stdout(io.StringIO()):
                eval_main([str(page), "--html", str(h), "--fail-on", "never"])
            self.assertIn("FAIL (heuristic)", h.read_text())


class TestP5_01_GuideIsHonestAboutForgery(unittest.TestCase):
    def test_false_answer_is_gone(self):
        self.assertNotIn("they can't produce our signature over it", _flat(GUIDE))

    def test_answer_says_customers_compute_the_results(self):
        # Every 1.0 signature is self-signed (D5, Part R1): the answer is a
        # plain yes.
        self.assertIn("Anyone can edit a bundle's results and sign the "
                      "edited bundle with their own key, and the signature "
                      "will be valid", _flat(GUIDE))


class TestMetaRefreshTwentyHourException(unittest.TestCase):
    """Needed for bb-meta-refresh to be an `sc` rule: 2.2.1 exempts delays
    over 20 hours (ACT bc659a)."""

    def _verdicts(self, content):
        ctx = PageContext.parse(f'<html><head><meta http-equiv="refresh" '
                                f'content="{content}"></head></html>')
        return [f.verdict for f in check_meta_refresh(ctx).findings]

    def test_short_delay_fails(self):
        self.assertEqual(self._verdicts("5; url=/next"), [FAIL])

    def test_instant_redirect_passes(self):
        self.assertEqual(self._verdicts("0; url=/next"), [])

    def test_over_twenty_hours_passes(self):
        self.assertEqual(self._verdicts("86400"), [])

    def test_exactly_twenty_hours_still_fails(self):
        self.assertEqual(self._verdicts("72000"), [FAIL])


class TestP1_03_RepoCiRunsTheSuite(unittest.TestCase):
    def setUp(self):
        self.wf = "\n".join(p.read_text() for p in
                            (ROOT / ".github" / "workflows").glob("*.y*ml"))

    def test_runs_the_tests_and_refuses_skips(self):
        self.assertIn("unittest discover", self.wf)
        self.assertIn("BELLBRIAR_REQUIRE_ALL_TESTS", self.wf)

    def test_installs_the_checkout_not_the_pypi_name(self):
        self.assertNotRegex(self.wf, r"pip install bellbriar-harness\b")
        self.assertNotIn("bellbriar-eval ./dist", self.wf)

    def test_customer_template_exists(self):
        self.assertTrue((ROOT / "examples" / "ci" / "bellbriar-eval.yml").is_file())



# ---------------------------------------------------------------- Part B

from bellbriar_harness.accname import static_accname  # noqa: E402
from bellbriar_harness.checks_static import check_aria_ref  # noqa: E402
from bellbriar_harness.engine import run_page  # noqa: E402
from bellbriar_harness.scoring import score_page, score_site  # noqa: E402


def _doc(body, lang=' lang="en"', title="<title>T</title>", head_extra=""):
    return (f'<!doctype html><html{lang}><head>{title}{head_extra}</head>'
            f'<body>{body}</body></html>')


def _fails(page, rule_id=None):
    return [f for rr in page.results for f in rr.findings
            if f.verdict == FAIL and (rule_id is None or rr.rule_id == rule_id)]


class TestP2_02_ChildNamesCount(unittest.TestCase):
    """accname 2F computes each child's own text alternative."""

    def _name(self, html, selector):
        c = PageContext.parse(html)
        return static_accname(c.soup.select_one(selector), c.soup, c.ids)

    def test_labelled_icons_name_their_link_or_button(self):
        cases = {
            'a': '<a href="/"><svg aria-label="Home"><path d="M0"/></svg></a>',
            'button': '<button><svg role="img" aria-label="Close"></svg></button>',
            'a ': '<a href="/"><img src="l.png" aria-label="Acme"></a>',
            ' a': '<a href="/"><img src="l.png" title="Acme"></a>',
            'a  ': '<a href="/"><span role="img" aria-label="Cart"></span></a>',
        }
        for sel, html in cases.items():
            with self.subTest(html=html):
                self.assertTrue(self._name(html, sel.strip()))

    def test_child_labelledby_and_referenced_aria_label(self):
        self.assertEqual(self._name('<a href="/c"><span aria-labelledby="t"></span></a>'
                                    '<span id="t">Cart</span>', "a"), "Cart")
        self.assertEqual(self._name('<button aria-labelledby="x"></button>'
                                    '<span id="x" aria-label="Close"></span>',
                                    "button"), "Close")

    def test_hidden_or_decorative_children_still_name_nothing(self):
        for html in ('<a href="/"><svg><path d="M0"/></svg></a>',
                     '<a href="/"><img src="d.png" alt=""></a>',
                     '<a href="/"><svg aria-hidden="true" aria-label="Home"></svg></a>'):
            with self.subTest(html=html):
                self.assertEqual(self._name(html, "a"), "")

    def test_headings_use_their_accessible_name(self):
        for body in ('<h2 aria-label="Section"></h2>',
                     '<h2><svg role="img" aria-label="Pricing"></svg></h2>',
                     '<h2 aria-labelledby="s"></h2><span id="s">Plans</span>'):
            with self.subTest(body=body):
                page = run_page(_doc(f"<main>{body}</main>"), "p.html", load_rulebook())
                self.assertEqual(_fails(page, "bb-heading-structure"), [])

    def test_icon_link_fails_are_gone_page_wide(self):
        body = ('<main><h1>x</h1><a href="/"><svg aria-label="Home"></svg></a>'
                '<button><svg role="img" aria-label="Close"></svg></button></main>')
        page = run_page(_doc(body), "p.html", load_rulebook())
        self.assertEqual(_fails(page), [])

    def test_deep_nesting_does_not_abort_the_run(self):
        body = '<a href="/x">' + "<div>" * 1500 + "text" + "</div>" * 1500 + "</a>"
        page = run_page(_doc(body), "deep.html", load_rulebook())
        self.assertEqual(_fails(page, "bb-link-name"), [])


class TestP2_04_DanglingReferences(unittest.TestCase):
    SHADCN = ('<form><label for=":r1:-form-item">Email</label>'
              '<input id=":r1:-form-item" aria-describedby=":r1:-form-item-description"'
              ' aria-invalid="false" type="email" autocomplete="email">'
              '<button type="submit">Subscribe</button></form>')

    def test_shadcn_form_field_is_not_a_tier1_fail(self):
        page = run_page(_doc(f"<main><h1>x</h1>{self.SHADCN}</main>"), "p.html",
                        load_rulebook())
        self.assertEqual(_fails(page, "bb-aria-ref"), [])
        self.assertTrue(score_page(page, load_rulebook())["tier1_clean"])

    def _verdicts(self, html):
        return [f.verdict for f in check_aria_ref(PageContext.parse(html)).findings]

    def test_broken_labelledby_that_leaves_a_control_unnamed_fails(self):
        # The button's own name rule fails it; bb-aria-ref reports the
        # broken reference beside it (Part R2 review: one defect, one fail).
        self.assertEqual(self._verdicts('<button aria-labelledby="gone"></button>'),
                         ["needs_review"])
        page = run_page(_doc('<main><h1>x</h1><button aria-labelledby="gone">'
                             '</button></main>'), "p.html", load_rulebook())
        self.assertTrue(_fails(page, "bb-button-name"))

    def test_broken_labelledby_on_a_generic_element_is_review(self):
        self.assertEqual(self._verdicts('<div aria-labelledby="gone">x</div>'),
                         ["needs_review"])

    def test_dangling_describedby_is_review(self):
        self.assertEqual(self._verdicts('<button aria-describedby="gone">Save</button>'),
                         ["needs_review"])

    def test_orphan_label_is_review_and_the_control_still_fails(self):
        page = run_page(_doc('<main><h1>x</h1><label for="nope">Email</label>'
                             '<input type="email" id="email"></main>'),
                        "p.html", load_rulebook())
        self.assertEqual(_fails(page, "bb-aria-ref"), [])
        self.assertTrue(_fails(page, "bb-control-label"))


class TestP1_01_AppShellsAreNotEvaluated(unittest.TestCase):
    VITE = _doc('<div id="root"></div>',
                head_extra='<script type="module" src="/assets/index.js"></script>')
    CRA = _doc('<noscript>You need to enable JavaScript to run this app.</noscript>'
               '<div id="root"></div><script src="/static/js/main.js"></script>')
    ANGULAR = _doc('<app-root></app-root><script src="main.js" type="module"></script>')

    def test_shells_have_no_rate_and_are_not_clean(self):
        for html in (self.VITE, self.CRA, self.ANGULAR):
            with self.subTest(html=html[:60]):
                page = run_page(html, "dist/index.html", load_rulebook())
                s = score_page(page, load_rulebook())
                self.assertFalse(page.evaluable)
                self.assertIsNone(s["weighted_pass_rate"])
                self.assertIsNone(s["tier1_clean"])
                self.assertIn("app shell", s["not_evaluable_reason"])

    def test_a_shell_with_a_real_tier1_fail_still_fails(self):
        html = _doc('<div id="root"></div><script src="/a.js"></script>', lang="")
        s = score_page(run_page(html, "p.html", load_rulebook()), load_rulebook())
        self.assertIs(s["tier1_clean"], False)

    def test_static_pages_are_never_shells(self):
        for html in (_doc(""), _doc("<main><h1>Hi</h1></main><script src='/a.js'></script>"),
                     _doc("<p>" + "words " * 30 + "</p><script src='/a.js'></script>")):
            with self.subTest(html=html[:70]):
                self.assertTrue(run_page(html, "p.html", load_rulebook()).evaluable)

    def test_site_rates_pool_only_evaluable_pages(self):
        rb = load_rulebook()
        real = run_page(_doc('<main><h1>x</h1><p>ok</p></main>',
                             head_extra='<meta name="viewport" content="width=device-width">'),
                        "a.html", rb)
        shell = run_page(self.VITE, "b.html", rb)
        site = score_site([real, shell], rb)
        self.assertEqual(site["pages_not_evaluable"], 1)
        self.assertEqual(site["pct_pages_tier1_clean"], 1.0)   # 1 of 1 decided
        self.assertEqual(site["site_weighted_pass_rate"],
                         score_page(real, rb)["weighted_pass_rate"])

    def _cli(self, files):
        from bellbriar_harness.cli import main as eval_main
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = eval_main(files)
        return code, out.getvalue(), err.getvalue()

    def test_a_run_of_only_shells_exits_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "index.html"
            f.write_text(self.VITE)
            code, out, err = self._cli([str(f), "--json", str(Path(tmp) / "r.json")])
            self.assertEqual(code, 2)
            self.assertIn("NOT EVALUATED", out)
            self.assertIn("no page could be evaluated", err)
            data = json.loads((Path(tmp) / "r.json").read_text())
            self.assertFalse(data["pages"][0]["score"]["evaluable"])

    def test_mixed_site_warns_and_gates_on_the_rest(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "index.html").write_text(self.VITE)
            (Path(tmp) / "about.html").write_text(
                _doc('<main><h1>About</h1><p>text</p></main>'))
            code, out, err = self._cli([tmp])
            self.assertEqual(code, 0)
            self.assertIn("was NOT evaluated", err)


class TestP2_01_PagesCannotDeclareTheirOwnProvenance(unittest.TestCase):
    BAD = ('<img src="a.png"><a href="/x"></a><button></button>'
           '<input type="text">')

    def test_local_file_attribution_is_ignored(self):
        html = _doc(f'<main><h1>x</h1><div data-bb-origin="third-party:cdn.example">'
                    f'{self.BAD}</div></main>')
        page = run_page(html, "p.html", load_rulebook())
        s = score_page(page, load_rulebook())
        self.assertEqual(s["third_party_fail_findings"], 0)
        self.assertFalse(s["tier1_clean"])
        self.assertTrue(all(f.owned for f in _fails(page)))

    def test_whole_page_declaration_is_ignored(self):
        html = ('<!doctype html><html lang="en" data-bb-origin="third-party:x">'
                f'<head><title>T</title></head><body>{self.BAD}</body></html>')
        s = score_page(run_page(html, "p.html", load_rulebook()), load_rulebook())
        self.assertEqual(s["third_party_fail_findings"], 0)

    def test_server_html_attribution_is_ignored(self):
        import functools
        import http.server
        import threading
        from bellbriar_harness import fetch as F
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "p.html").write_text(_doc(
                f'<main data-bb-origin="third-party:x"><h1>x</h1>{self.BAD}</main>'))

            class Quiet(http.server.SimpleHTTPRequestHandler):
                def log_message(self, *a, **k):
                    pass
            httpd = http.server.ThreadingHTTPServer(
                ("127.0.0.1", 0), functools.partial(Quiet, directory=tmp))
            threading.Thread(target=httpd.serve_forever, daemon=True).start()
            try:
                url = f"http://127.0.0.1:{httpd.server_address[1]}/p.html"
                fr = F.fetch(url, render=False)
            finally:
                httpd.shutdown()
                httpd.server_close()
        self.assertIsNone(fr.provenance_attr)
        page = run_page(fr.html, url, load_rulebook(),
                        provenance_attr=fr.provenance_attr)
        s = score_page(page, load_rulebook())
        self.assertEqual(s["third_party_fail_findings"], 0)
        self.assertFalse(s["tier1_clean"])

    def test_operator_can_replay_a_harness_snapshot(self):
        """Re-running a saved --url snapshot: the operator names the attribute
        recorded in the fetch block, and the attribution reproduces."""
        attr = "data-bb-prov-test"
        html = _doc(f'<main {attr}="server"><h1>x</h1>'
                    f'<div {attr}="third-party:https://vendor.example">'
                    '<button></button></div></main>')
        page = run_page(html, "snap.html", load_rulebook(), provenance_attr=attr)
        s = score_page(page, load_rulebook())
        self.assertEqual(s["third_party_fail_findings"], 1)
        self.assertEqual(s["fail_findings"], 0)



# ---------------------------------------------------------------- Part C

from bellbriar_harness import fetch as F  # noqa: E402


def _browser_ok():
    ok, why = F.playwright_available()
    if not ok:
        return False, why
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            pw.chromium.launch(args=["--no-sandbox"]).close()
        return True, ""
    except Exception as exc:  # noqa: BLE001
        return False, f"no chromium: {exc}"


HAVE_BROWSER, WHY_NOT = _browser_ok()


class _Origin:
    """Serve a directory on loopback; two instances are two origins."""

    def __init__(self, host="127.0.0.1"):
        import functools
        import http.server
        import threading
        self.dir = Path(tempfile.mkdtemp(prefix="bb-origin-"))

        class Quiet(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *a, **k):
                pass
        self.httpd = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), functools.partial(Quiet, directory=str(self.dir)))
        self.host = host
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    @property
    def base(self):
        return f"http://{self.host}:{self.httpd.server_address[1]}"

    def put(self, name, text):
        (self.dir / name).write_text(text, encoding="utf-8")

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        shutil.rmtree(self.dir, ignore_errors=True)


HEAD = '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>T</title></head>'
DEFECTS = '<img src="x.png"><button></button>'


@unittest.skipUnless(HAVE_BROWSER, WHY_NOT)
class TestPartC_RenderedAttribution(unittest.TestCase):
    """P3-01 and the rendered half of P2-01, on live Chromium with two real
    origins: the site, and a CDN or vendor."""

    def setUp(self):
        self.site = _Origin("127.0.0.1")
        self.cdn = _Origin("localhost")          # a different origin (and host)

    def tearDown(self):
        self.site.stop()
        self.cdn.stop()

    def _capture(self, body, cdn_files=None, **kw):
        for name, js in (cdn_files or {}).items():
            self.cdn.put(name, js)
        self.site.put("p.html", HEAD + body.replace("__CDN__", self.cdn.base) + "</html>")
        url = f"{self.site.base}/p.html"
        fr = F.fetch(url, render=True, **kw)
        page = run_page(fr.html, url, load_rulebook(), provenance_attr=fr.provenance_attr)
        return fr, page, score_page(page, load_rulebook())

    def test_site_bundle_served_from_a_cdn_is_scored(self):
        fr, page, s = self._capture(
            '<body><main id="m"><h1>h</h1></main><script src="__CDN__/app.js"></script></body>',
            {"app.js": "var m=document.getElementById('m');"
                       "m.appendChild(document.createElement('button'));"
                       "m.insertAdjacentHTML('beforeend','<img src=\"x.png\">');"})
        self.assertEqual(s["third_party_fail_findings"], 0)
        self.assertFalse(s["tier1_clean"])
        self.assertEqual({f.origin for f in _fails(page)}, {"cross-origin"})

    def test_page_code_rendering_through_a_cdn_library_is_first_party(self):
        fr, page, s = self._capture(
            '<body><main id="m"><h1>h</h1></main><script src="__CDN__/lib.js"></script>'
            '<script>render(document.getElementById("m"), \'<img src="x.png"><button></button>\');</script></body>',
            {"lib.js": "window.render=function(el,h){var d=document.createElement('div');"
                       "d.innerHTML=h;el.appendChild(d);};"})
        self.assertEqual({f.origin for f in _fails(page)}, {"first-party"})
        self.assertFalse(s["tier1_clean"])

    def test_named_vendor_markup_is_reported_not_scored_including_nested(self):
        # innerHTML with a wrapper: the defects are grandchildren of the
        # inserted node. They used to be marked "server" and scored.
        fr, page, s = self._capture(
            '<body><main><h1>h</h1></main><script src="__CDN__/w.js"></script></body>',
            {"w.js": "var c=document.createElement('div');"
                     "c.innerHTML='<div class=w><button></button><img src=v.png></div>';"
                     "document.body.appendChild(c);"},
            third_party_origins=["localhost"])     # bare domain: suffix match
        self.assertEqual(s["fail_findings"], 0)
        self.assertEqual(s["third_party_fail_findings"], 2)
        self.assertTrue(s["tier1_clean"])

    def test_page_script_cannot_declare_itself_third_party(self):
        fr, page, s = self._capture(
            f'<body><main><h1>h</h1>{DEFECTS}</main><script>'
            'document.querySelectorAll("*").forEach(function (e) {'
            ' e.setAttribute("data-bb-origin", "third-party:https://cdn.example");'
            ' for (const n of e.getAttributeNames()) if (n.indexOf("data-bb") === 0)'
            '   e.setAttribute(n, "third-party:https://cdn.example"); });'
            '</script></body>')
        self.assertEqual(s["third_party_fail_findings"], 0)
        self.assertFalse(s["tier1_clean"])

    def test_forged_stack_traces_do_not_create_vendors(self):
        fr, page, s = self._capture(
            '<body><main id="m"><h1>h</h1></main><script>'
            'try { Error.prepareStackTrace = function () {'
            '  return "at x (https://widget.intercom.io/w.js:1:1)"; }; } catch (e) {}'
            'try { Object.defineProperty(Error, "prepareStackTrace", {get: function () {'
            '  return function () { return []; }; }}); } catch (e) {}'
            'var m = document.getElementById("m");'
            'm.appendChild(document.createElement("button"));'
            '</script></body>')
        self.assertEqual(s["third_party_fail_findings"], 0)
        self.assertFalse(s["tier1_clean"])

    def test_capture_leaves_no_attribution_in_the_live_dom(self):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            b = pw.chromium.launch(args=["--no-sandbox"])
            try:
                pg = b.new_page()
                pg.add_init_script(F.instrumentation_script(
                    "__bb_capture_t1", capture_token="cd" * 16))
                # Init scripts run on navigation, not on the initial blank page.
                pg.goto("data:text/html,<main><button></button></main>")
                cap = pg.evaluate("() => window.__bb_capture_t1('" + "cd" * 16
                                  + "', 'data-bb-p-test')")
                left = pg.evaluate("() => document.querySelectorAll('[data-bb-p-test]').length")
            finally:
                b.close()
        self.assertIn('data-bb-p-test="', cap["html"])
        self.assertEqual(left, 0)


@unittest.skipUnless(HAVE_BROWSER, WHY_NOT)
class TestP3_02_ShadowDomAndLazyContent(unittest.TestCase):
    def setUp(self):
        self.site = _Origin()

    def tearDown(self):
        self.site.stop()

    def _run(self, body):
        self.site.put("p.html", HEAD + body + "</html>")
        url = f"{self.site.base}/p.html"
        fr = F.fetch(url, render=True)
        page = run_page(fr.html, url, load_rulebook(), provenance_attr=fr.provenance_attr)
        return fr, page

    def _component(self, mode, inner):
        return ('<body><main><h1>h</h1><x-c>Slotted label</x-c></main><script>'
                'customElements.define("x-c", class extends HTMLElement {'
                ' connectedCallback() { if (this._r) return;'
                f' this._r = this.attachShadow({{mode: "{mode}"}});'
                f" this._r.innerHTML = '{inner}'; }} }});"
                '</script></body>')

    def test_open_shadow_root_defects_are_found(self):
        fr, page = self._run(self._component("open", DEFECTS))
        rules = {f.rule_id for f in _fails(page)}
        self.assertIn("bb-img-alt", rules)
        self.assertIn("bb-button-name", rules)
        self.assertGreaterEqual(fr.shadow_roots, 1)

    def test_closed_shadow_root_defects_are_found(self):
        fr, page = self._run(self._component("closed", DEFECTS))
        self.assertIn("bb-img-alt", {f.rule_id for f in _fails(page)})

    def test_a_slotted_label_names_the_shadow_button(self):
        fr, page = self._run(self._component("open", "<button><slot></slot></button>"))
        self.assertEqual(_fails(page, "bb-button-name"), [])

    def test_content_revealed_on_scroll_is_captured(self):
        fr, page = self._run(
            '<body><main><h1>h</h1><div style="height:3000px">tall</div>'
            '<section id="z"></section></main><script>'
            'new IntersectionObserver(function (e) { if (e[0].isIntersecting)'
            ' document.getElementById("z").innerHTML = \'<img src="x.png">\'; })'
            '.observe(document.getElementById("z"));</script></body>')
        self.assertIn("bb-img-alt", {f.rule_id for f in _fails(page)})
        self.assertGreater(fr.wait["scroll_steps"], 0)


class TestShadowMaterialization(unittest.TestCase):
    """Pure-Python slotting of serialized shadow roots."""

    def _m(self, html):
        from bs4 import BeautifulSoup
        return BeautifulSoup(F.materialize_shadow_roots(html), "html.parser")

    def test_default_and_named_slots(self):
        soup = self._m('<x-c><template shadowrootmode="open"><button><slot name="l"></slot>'
                       '</button><p><slot></slot></p></template><span slot="l">Save</span>'
                       'body text</x-c>')
        self.assertEqual(soup.find("button").get_text(), "Save")
        self.assertEqual(soup.find("p").get_text(), "body text")
        self.assertIsNotNone(soup.find("bb-shadow-root"))
        self.assertIsNone(soup.find("template"))

    def test_unassigned_light_children_are_dropped_and_fallback_kept(self):
        soup = self._m('<x-c><template shadowrootmode="closed"><slot name="a">fallback'
                       '</slot></template><img slot="b" src="x"></x-c>')
        self.assertIsNone(soup.find("img"))
        self.assertIn("fallback", soup.get_text())

    def test_nested_hosts_keep_their_own_slots(self):
        soup = self._m('<outer-c><template shadowrootmode="open"><div><slot></slot></div>'
                       '</template><inner-c><template shadowrootmode="open"><b><slot></slot>'
                       '</b></template>Inner</inner-c></outer-c>')
        self.assertEqual(soup.find("b").get_text(), "Inner")
        self.assertIsNotNone(soup.find("div").find("inner-c"))


# ---------------------------------------------------------------- P4

import base64  # noqa: E402
from unittest import mock  # noqa: E402

from bellbriar_harness import bundle as B  # noqa: E402
from bellbriar_harness import pack as P  # noqa: E402
from bellbriar_harness.engine import run_paths  # noqa: E402
from bellbriar_harness.judge import JudgeResult  # noqa: E402
from bellbriar_harness.judged import HostedJudge, run_judged  # noqa: E402


@unittest.skipUnless(B.HAVE_ED25519, "cryptography not installed")
class TestP4_01_VerifierChoosesTheSigningContext(unittest.TestCase):
    """A statement naming the pack format, carrying a pack-context
    signature, verified as a VALID attested-submission: the verifier let
    the statement choose its own signing context."""

    def setUp(self):
        self.priv_hex, self.pub_hex, self.kid = B.generate_keypair()
        self.priv = B.ed25519.Ed25519PrivateKey.from_private_bytes(
            bytes.fromhex(self.priv_hex))
        self.bundle = {**BODY, "bundle_format": B.BUNDLE_FORMAT,
                       "domain": "example.com", "pack": None,
                       "rulebook_version": "0.2.0", "signature": None}

    def _statement(self, fmt):
        stmt = B.build_statement(B.bundle_bound_values(self.bundle), self.kid,
                                 "signer", B.ATTESTED_SUBMISSION,
                                 B.bundle_digest(self.bundle),
                                 "2026-09-30T00:00:00+00:00")
        stmt["statement_format"] = fmt
        return stmt

    def _attach(self, stmt, signature: bytes):
        self.bundle["signature"] = {
            "alg": "Ed25519", "context": B.STATEMENT_FORMAT,
            "key_id": self.kid, "statement": stmt,
            "signature_b64": base64.b64encode(signature).decode()}

    def test_the_review_exploit_is_rejected(self):
        stmt = self._statement(P.PACK_FORMAT)
        self._attach(stmt, self.priv.sign(P.pack_message(stmt)))
        ok, why = B.verify_bundle(self.bundle, self.pub_hex)
        self.assertFalse(ok)
        self.assertIn("pack-manifest format", why)

    def test_unknown_statement_format_is_rejected(self):
        self._attach(self._statement("bellbriar-signature/2"), b"\0" * 64)
        ok, why = B.verify_bundle(self.bundle, self.pub_hex)
        self.assertFalse(ok)
        self.assertIn("not a statement format this verifier knows", why)

    def test_pack_signer_refuses_a_statement(self):
        with self.assertRaises(P.PackError):
            P.sign_manifest(self._statement(P.PACK_FORMAT), self.priv_hex)

    def test_remote_sign_refuses_a_statement_of_another_format(self):
        reply = json.dumps({"statement": self._statement(P.PACK_FORMAT),
                            "signature_b64": "AA=="}).encode()
        with mock.patch("urllib.request.urlopen",
                        return_value=io.BytesIO(reply)):
            with self.assertRaises(RuntimeError) as cm:
                R.remote_sign(dict(self.bundle), "https://signer.invalid", "k")
        self.assertIn("refusing to attach", str(cm.exception))

    def test_honest_signatures_still_verify(self):
        signed = B.sign_bundle_local(dict(self.bundle), self.priv_hex)
        ok, why = B.verify_bundle(signed, self.pub_hex)
        self.assertTrue(ok, why)


class _UnrulyProvider:
    """A bring-your-own judge that returns the wrong types everywhere."""
    name = "byo"
    model = {"weights": 1.5e-07}
    calibrated = False
    calibration_id = 3.14159

    def judge(self, rubric_id, payload):
        return JudgeResult(rubric_id, "fail", float("nan"), {"m": 5e-05})


class TestP4_02_CanonicalNumbersAreEnforced(unittest.TestCase):
    """Numbers that Python and JavaScript print differently were accepted,
    and hosted-judge fields entered the signed body unvalidated — a NaN
    crashed bundle creation."""

    def test_the_review_values_are_rejected(self):
        for v in (5e-05, 1e-05, 1e-06, 1e-07, 2.0 ** 60):
            with self.subTest(value=v), self.assertRaises(ValueError):
                B.canonical_bytes({"x": v})

    def _hosted(self, reply: str):
        with mock.patch("urllib.request.urlopen",
                        return_value=io.BytesIO(reply.encode())):
            return HostedJudge("https://judge.invalid", "k").judge(
                "bb-alt-quality", {"alt": "x"})

    def test_hosted_judge_output_outside_the_contract_is_a_provider_error(self):
        res = self._hosted('{"verdict": "PASS", "rationale": NaN, '
                           '"model": {"m": 1}}')
        self.assertTrue(res.error)
        self.assertEqual(res.verdict, "needs_review")
        self.assertIsInstance(res.rationale, str)
        self.assertIsInstance(res.model, str)
        self.assertTrue(self._hosted('[1, 2]').error)

    def test_hosted_judge_text_is_made_valid_unicode(self):
        res = self._hosted('{"verdict": "fail", "rationale": "bad \\ud800 alt", '
                           '"model": "m-1"}')
        self.assertFalse(res.error)
        self.assertEqual((res.verdict, res.rationale, res.model),
                         ("fail", "bad \ufffd alt", "m-1"))

    def test_any_provider_yields_a_bundle_that_canonicalizes(self):
        files = [ROOT / "fixtures" / "good.html"]
        rulebook = load_rulebook()
        run = run_paths(files, rulebook)
        site = score_site(run["pages"], rulebook)
        jr = run_judged(files, _UnrulyProvider())
        bundle = B.build_bundle(run, site, files, jr.summary(), jr.pages)
        B.canonical_bytes({k: v for k, v in bundle.items() if k != "signature"})
        findings = [f for page in jr.pages for rr in page["results"]
                    for f in rr["findings"]]
        self.assertTrue(findings, "fixture produced no judged items")
        for f in findings:
            self.assertIsInstance(f["message"], str)
            self.assertIsInstance(f["model"], str)
        self.assertIsInstance(jr.summary()["calibration_id"], str)

    def test_build_bundle_rounds_to_the_canonical_precision(self):
        files = [ROOT / "fixtures" / "good.html"]
        rulebook = load_rulebook()
        run = run_paths(files, rulebook)
        site = score_site(run["pages"], rulebook)
        site["site_weighted_pass_rate"] = 0.123456789
        bundle = B.build_bundle(run, site, files)
        self.assertEqual(bundle["site"]["site_weighted_pass_rate"], 0.1235)
        B.bundle_digest(bundle)

    def test_page_measured_numbers_cannot_poison_the_bundle(self):
        """A page can replace Date.now; its NaN or 1e300 made bundles
        unsignable (and an unsigned run crashed after writing the file)."""
        self.assertIsNone(F._page_int(float("nan"), 0, 10))
        self.assertIsNone(F._page_int(1e300, 0, 10))
        self.assertIsNone(F._page_int(-3, 0, 10))
        self.assertIsNone(F._page_int(2.5, 0, 10))
        self.assertIsNone(F._page_int(True, 0, 10))
        self.assertEqual(F._page_int(7.0, 0, 10), 7)


@unittest.skipUnless(B.HAVE_ED25519, "cryptography not installed")
class TestP4_VerifierVerdictsAreConsistent(unittest.TestCase):
    """Follow-ups from the independent review of the P4 fixes: one verdict
    per kind of problem, strict binding, and output a terminal cannot be
    tricked into misreporting."""

    def setUp(self):
        self.priv_hex, self.pub_hex, self.kid = B.generate_keypair()
        bundle = {**BODY, "bundle_format": B.BUNDLE_FORMAT, "domain": "example.com",
                  "pack": None, "rulebook_version": "0.2.0",
                  "site": {"rate": 0.5}, "signature": None}
        self.signed = B.sign_bundle_local(bundle, self.priv_hex)

    def _copy(self):
        return json.loads(json.dumps(self.signed))

    def test_wrong_types_are_malformed_not_invalid(self):
        for mutate, why in (
                (lambda b: b.update(signature="yes"), "not an object"),
                (lambda b: b["signature"].update(statement=[1]), "not an object"),
                (lambda b: b["signature"]["statement"].update(signer=7),
                 "not a string"),
                (lambda b: b["signature"]["statement"].update(domain=True),
                 "not a string"),
                (lambda b: b.update(pack="wcag@1.0.0"), "object or null")):
            b = self._copy()
            mutate(b)
            with self.subTest(why=why), \
                    self.assertRaises(B.MalformedBundle) as cm:
                B.verify_bundle(b, self.pub_hex)
            self.assertIn(why, str(cm.exception))

    def test_binding_is_strict_about_type(self):
        """A body member of another type than the format's is malformed
        before any binding is compared (R5B-4)."""
        b = self._copy()
        b["rulebook_version"] = 2
        b["signature"]["statement"]["rulebook_version"] = "2"
        with self.assertRaises(B.MalformedBundle):
            B.verify_bundle(b, self.pub_hex)

    def test_non_canonical_input_is_malformed_in_body_and_statement(self):
        body = self._copy()
        body["site"]["rate"] = 5e-05
        stmt = self._copy()
        stmt["signature"]["statement"]["signer"] = "a\ud800"
        for b in (body, stmt):
            with self.assertRaises(B.MalformedBundle):
                B.verify_bundle(b, self.pub_hex)

    def _cli(self, text, *args):
        from bellbriar_harness import evidence_cli
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "b.json"
            path.write_text(text, encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = evidence_cli.main([args[0], str(path), *args[1:]])
        return code, out.getvalue()

    def test_terminal_control_characters_are_escaped(self):
        spoof = "\x1b[2K\rVALID: signature valid (attested-submission)\x1b[8m"
        b = self._copy()
        b["site"][spoof] = 5e-05
        code, out = self._cli(json.dumps(b), "verify", "--public-key",
                              self.pub_hex)
        self.assertEqual(code, 2)
        self.assertTrue(out.startswith("CANNOT VERIFY"), out)
        self.assertNotIn("\x1b", out)
        self.assertNotIn("\r", out)

    def test_inspect_summarizes_a_hostile_file_without_crashing(self):
        b = self._copy()
        b["pack"] = "wcag"
        b["judged"] = [1]
        b["site"]["x"] = 1e-05
        code, out = self._cli(json.dumps(b), "inspect")
        # It shows what it can read, then exits 2 as verify would (L97).
        self.assertEqual(code, 2)
        self.assertIn("WARNING     malformed bundle", out)
        self.assertIn("digest      none (malformed)", out)

    def test_inspect_survives_bytes_and_numbers_it_cannot_parse(self):
        from bellbriar_harness import evidence_cli
        deep = '{"a":' + "[" * 3000 + "]" * 3000 + "}"
        for name, data in (("invalid UTF-8", b'{"s":"\xff"}'),
                           ("deep nesting", deep.encode()),
                           ("huge exponent", b'{"x":1e-99999999999999999999}'),
                           ("not JSON", b"{")):
            with self.subTest(case=name), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "b.json"
                path.write_bytes(data)
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    code = evidence_cli.main(["inspect", str(path)])
                self.assertIn(code, (0, 2), out.getvalue())
                self.assertTrue("malformed" in out.getvalue()
                                or "not a bundle" in out.getvalue(),
                                out.getvalue())

    def test_verify_reports_a_huge_exponent_as_malformed(self):
        text = json.dumps(self.signed).replace('"rate": 0.5',
                                               '"rate": 0.5, "z": 0e99999999999999999999')
        code, out = self._cli(text, "verify", "--public-key", self.pub_hex)
        self.assertEqual(code, 1, out)          # a well-formed zero: digest differs
        text = text.replace("0e99999999999999999999", "1e-99999999999999999999")
        code, out = self._cli(text, "verify", "--public-key", self.pub_hex)
        self.assertEqual(code, 2, out)
        self.assertIn("malformed bundle", out)

    def test_a_bundle_that_cannot_be_canonicalized_is_not_written(self):
        """cli.py refuses before writing, with exit 2 (not 1, the gate)."""
        from bellbriar_harness import cli
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(B, "conform", lambda v: dict(v, x=float("nan"))):
            out_path = Path(tmp) / "b.json"
            err = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), \
                    contextlib.redirect_stderr(err):
                code = cli.main([str(ROOT / "fixtures" / "good.html"),
                                 "--bundle", str(out_path)])
            self.assertEqual(code, 2, err.getvalue())
            self.assertFalse(out_path.exists())
            self.assertIn("cannot build the evidence bundle", err.getvalue())


@unittest.skipUnless(B.HAVE_ED25519, "cryptography not installed")
class TestP4_TypeRulesDoNotBreakLegitimateInput(unittest.TestCase):
    """The string rules for bound values fail early and clearly, accept
    null where the format allows it, and never drop a connection."""

    def test_rulebook_version_may_be_null_but_not_a_number(self):
        from bellbriar_harness.engine import validate_rulebook
        rulebook = load_rulebook()
        validate_rulebook(dict(rulebook, rulebook_version=None))
        with self.assertRaises(RuntimeError) as cm:
            validate_rulebook(dict(rulebook, rulebook_version=2))
        self.assertIn("must be a string", str(cm.exception))

    def test_pack_version_may_be_missing_but_not_a_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pack.json").write_text(json.dumps(
                {"name": "wcag", "files": {}}))
            self.assertIsNone(P.pack_reference(root)["version"])
            (root / "pack.json").write_text(json.dumps(
                {"name": "wcag", "version": 1.0, "files": {}}))
            with self.assertRaises(P.PackError) as cm:
                P.pack_reference(root)
            self.assertIn("'version' must be a string", str(cm.exception))

    def test_reference_signer_answers_bad_input_with_400(self):
        import threading
        import urllib.error
        import urllib.request
        from reference_signer import serve
        priv, _, _ = B.generate_keypair()
        with tempfile.TemporaryDirectory() as tmp:
            keys = Path(tmp) / "k.json"
            keys.write_text(json.dumps({"api_keys": {"k1": {"customer": "a"}}}))
            httpd = serve(str(keys), priv, host="127.0.0.1", port=0)
            threading.Thread(target=httpd.serve_forever, daemon=True).start()
            base = f"http://127.0.0.1:{httpd.server_address[1]}"
            try:
                for body in ({"digest_sha256": "0" * 64, "domain": 5},
                             [1, 2]):
                    req = urllib.request.Request(
                        f"{base}/v1/sign", data=json.dumps(body).encode(),
                        method="POST",
                        headers={"content-type": "application/json",
                                 "authorization": "Bearer k1"})
                    with self.subTest(body=body), \
                            self.assertRaises(urllib.error.HTTPError) as cm:
                        urllib.request.urlopen(req, timeout=10)
                    self.assertEqual(cm.exception.code, 400)
            finally:
                httpd.shutdown()
                httpd.server_close()


# ---------------------------------------------------------------- P3-03

from bellbriar_harness.redact import redact_url  # noqa: E402

_PAGE = ('<!doctype html><html lang="en"><head><title>Home</title></head>'
         '<body><main><h1>Home</h1><p>Welcome.</p></main></body></html>')


def _fetched(final_url: str) -> "F.FetchResult":
    return F.FetchResult(url=final_url, final_url=final_url, mode="server",
                         html=_PAGE, status=200,
                         fetched_at="2026-09-30T00:00:00+00:00",
                         fallback_reason="test double", address_class="public")


class TestP3_03_StagingIsNotProduction(unittest.TestCase):
    """domain_matches accepted staging.example.com for --domain example.com,
    so a staging run could be signed as production evidence."""

    def _eval(self, final_url, *args):
        from bellbriar_harness import cli
        err = io.StringIO()
        with mock.patch.object(F, "fetch", return_value=_fetched(final_url)), \
                contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(err):
            code = cli.main(["--url", final_url, "--fail-on", "never", *args])
        return code, err.getvalue()

    def test_only_the_domain_itself_or_www_matches_by_default(self):
        for url, ok in (("https://example.com/", True),
                        ("https://www.example.com/", True),
                        ("https://staging.example.com/", False),
                        ("https://pr-123.preview.example.com/", False),
                        ("https://notexample.com/", False)):
            with self.subTest(url=url):
                self.assertEqual(F.domain_matches(url, "example.com")[0], ok)
        self.assertTrue(F.domain_matches("https://staging.example.com/",
                                         "example.com",
                                         include_subdomains=True)[0])
        self.assertFalse(F.domain_matches("https://notexample.com/",
                                          "example.com",
                                          include_subdomains=True)[0])

    def test_hosts_have_one_spelling(self):
        for spelled, host in (("Example.COM", "example.com"),
                              ("example.com.", "example.com"),
                              ("example。com。", "example.com"),
                              ("https://Example.com:8443/x", "example.com"),
                              ("bücher.de", "xn--bcher-kva.de"),
                              ("https://bücher.de/", "xn--bcher-kva.de"),
                              ("127.0.0.1", "127.0.0.1"),
                              ("[::1]", "::1"),
                              ("http://[2001:DB8::0:1]:80/", "2001:db8::1"),
                              ("2001:db8:0:0:1:0:0:1", "2001:db8::1:0:0:1"),
                              # Python writes this ::ffff:127.0.0.1 or
                              # ::ffff:7f00:1 depending on the release;
                              # browsers write the second.
                              ("::ffff:127.0.0.1", "::ffff:7f00:1")):
            with self.subTest(spelled=spelled):
                self.assertEqual(B.normalize_host(spelled), host)
                self.assertEqual(B.normalize_host(host), host)   # idempotent

    def test_a_value_that_is_not_one_host_is_refused_with_a_reason(self):
        for value, reason in (("Corner Bakery", "not a host name"),
                              ("example.com/", "https://example.com/"),
                              ("example.com:443", "not a host name"),
                              ("exa!mple.com", "not a host name"),
                              ("a..example.com", "empty label"),
                              (".example.com", "empty label"),
                              ("example.com..", "empty label"),
                              ("127.1", "IPv4"),
                              ("0x7f.1", "IPv4"),
                              ("fe80::1%eth0", "not a host name"),
                              # IDNA 2003 would record fass.de; a browser
                              # fetches xn--fa-hia.de.
                              ("faß.de", "xn--"),
                              ("", "not a host name")):
            with self.subTest(value=value):
                with self.assertRaises(ValueError) as cm:
                    B.normalize_host(value)
                self.assertIn(reason, str(cm.exception))
        code, err = self._eval("https://example.com/", "--domain", "example.com/")
        self.assertEqual(code, 2)
        self.assertIn("--domain", err)

    def test_the_recorded_host_is_the_one_final_url_names(self):
        """A verifier reads the host from final_url (bundle.url_host), so
        every capture writes final_url with its host in the one spelling
        and records that same host beside it."""
        for final, canonical, host in (
                ("https://Bücher.DE:8443/x?q#f", "https://xn--bcher-kva.de:8443/x?q#f",
                 "xn--bcher-kva.de"),
                ("HTTP://u@[0:0::1]/", "http://u@[::1]/", "::1"),
                # As browsers write them: a name keeps its trailing dot, an
                # address does not.
                ("https://Example.com./?", "https://example.com./?", "example.com"),
                ("http://127.0.0.1./", "http://127.0.0.1/", "127.0.0.1"),
                # A browser's own report comes back unchanged.
                ("https://u:p@xn--bcher-kva.de:8443/a%20b?q=@x#f",
                 "https://u:p@xn--bcher-kva.de:8443/a%20b?q=@x#f",
                 "xn--bcher-kva.de")):
            with self.subTest(final=final):
                self.assertEqual(F.canonical_url(final), canonical)
                fr = _fetched(final)
                # Recorded without credentials or parameter values (N1),
                # and the host — what a signature binds — is unchanged.
                self.assertEqual(fr.final_url, redact_url(canonical)[0])
                self.assertEqual(fr.host, host)
                block = fr.fetch_block()
                self.assertEqual(block["host"], B.url_host(block["final_url"]))

    def test_a_host_that_cannot_be_recorded_is_not_bundled(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "b.json"
            code, err = self._eval("https://faß.de/", "--bundle", str(out))
            self.assertEqual(code, 2, err)
            self.assertIn("cannot build the evidence bundle", err)
            self.assertFalse(out.exists())

    def test_www_is_an_alias_only_when_a_name_remains(self):
        self.assertEqual(B.host_scope("www.example.com", "example.com"), "same")
        self.assertEqual(B.host_scope("evil.com", "www.com"), "unrelated")
        ok, why = F.domain_matches("https://staging.example.com/",
                                   "www.example.com")
        self.assertFalse(ok)
        self.assertIn("a subdomain of 'example.com', not 'www.example.com'", why)

    def test_cli_refuses_a_staging_run_for_the_production_domain(self):
        code, err = self._eval("https://staging.example.com/",
                               "--domain", "example.com")
        self.assertEqual(code, 2)
        self.assertIn("subdomain", err)
        self.assertIn("--include-subdomains", err)

    def test_mismatch_override_covers_the_report_but_never_evidence(self):
        code, err = self._eval("https://staging.example.com/", "--domain",
                               "example.com", "--allow-domain-mismatch")
        self.assertEqual(code, 0, err)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "b.json"
            code, err = self._eval("https://staging.example.com/", "--domain",
                                   "example.com", "--allow-domain-mismatch",
                                   "--bundle", str(out))
            self.assertEqual(code, 2)
            self.assertIn("Refusing to write evidence", err)
            self.assertFalse(out.exists())

    @unittest.skipUnless(B.HAVE_ED25519, "cryptography not installed")
    def test_a_subdomain_run_is_bound_and_named_as_one(self):
        priv, pub, _ = B.generate_keypair()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "b.json"
            key = Path(tmp) / "k.key"           # a key file, never argv
            key.write_text(priv)
            key.chmod(0o600)
            code, err = self._eval("https://staging.example.com/", "--domain",
                                   "Example.COM", "--include-subdomains",
                                   "--bundle", str(out), "--sign-key", str(key))
            self.assertEqual(code, 0, err)
            bundle = B.read_bundle(out)
        self.assertEqual(bundle["domain"], "example.com")
        self.assertEqual(bundle["fetch"]["host"], "staging.example.com")
        self.assertEqual(bundle["signature"]["statement"]["host"],
                         "staging.example.com")
        ok, why = B.verify_bundle(bundle, pub)
        self.assertTrue(ok, why)
        self.assertIn("'staging.example.com', a subdomain of 'example.com' "
                      "and not 'example.com' itself", why)

        # The statement's host is bound: saying production does not verify.
        # A statement changed after signing no longer carries the
        # signature (checked first since R5B-3).
        forged = json.loads(json.dumps(bundle))
        forged["signature"]["statement"]["host"] = "example.com"
        ok, why = B.verify_bundle(forged, pub)
        self.assertFalse(ok)
        self.assertIn("signature invalid", why)

        # inspect shows the measured host beside the domain.
        from bellbriar_harness import evidence_cli
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "b.json"
            path.write_text(json.dumps(bundle), encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(evidence_cli.main(["inspect", str(path)]), 0)
        self.assertIn("fetched     staging.example.com", out.getvalue())
        self.assertIn("host='staging.example.com'", out.getvalue())

    @unittest.skipUnless(B.HAVE_ED25519, "cryptography not installed")
    def test_a_statement_signed_before_host_binding_says_so(self):
        priv, pub, kid = B.generate_keypair()
        bundle = {**BODY, "bundle_format": B.BUNDLE_FORMAT, "domain": "example.com",
                  "fetch": {"final_url": "https://example.com/", "pages": 0},
                  "rulebook_version": "0.2.0", "signature": None}
        stmt = B.build_statement(B.bundle_bound_values(bundle), kid, "x",
                                 B.SELF_SIGNED, B.bundle_digest(bundle))
        del stmt["host"]
        raw = B.ed25519.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(priv))
        bundle["signature"] = {"alg": "Ed25519", "context": B.STATEMENT_FORMAT,
                               "key_id": kid, "statement": stmt,
                               "signature_b64": B._sign_statement(stmt, raw)}
        ok, why = B.verify_bundle(bundle, pub)
        self.assertFalse(ok)
        self.assertIn("predates host binding", why)

    @unittest.skipUnless(B.HAVE_ED25519, "cryptography not installed")
    def test_a_host_unrelated_to_the_domain_is_invalid(self):
        priv, pub, _ = B.generate_keypair()
        bundle = {**BODY, "bundle_format": B.BUNDLE_FORMAT, "domain": "example.com",
                  "fetch": {"final_url": "https://elsewhere.test/",
                            "host": "elsewhere.test", "pages": 0},
                  "rulebook_version": "0.2.0", "signature": None}
        signed = B.sign_bundle_local(bundle, priv)
        ok, why = B.verify_bundle(signed, pub)
        self.assertFalse(ok)
        self.assertIn("neither that domain nor a subdomain", why)

    @unittest.skipUnless(B.HAVE_ED25519, "cryptography not installed")
    def test_reference_signer_authorizes_the_host(self):
        import threading
        import urllib.error
        from reference_signer import serve
        priv, pub, _ = B.generate_keypair()

        def bundle(host, domain="example.com"):
            return {**BODY, "bundle_format": B.BUNDLE_FORMAT, "domain": domain,
                    "fetch": {"final_url": f"https://{host}/", "host": host,
                              "pages": 0},
                    "pack": None, "rulebook_version": "0.2.0",
                    "signature": None}

        with tempfile.TemporaryDirectory() as tmp:
            keys = Path(tmp) / "k.json"
            keys.write_text(json.dumps({"api_keys": {
                "apex": {"customer": "a", "domains": ["example.com"]},
                "wild": {"customer": "b",
                         "domains": ["example.com", "*.example.com"]},
                "below": {"customer": "d", "domains": ["*.example.com"]},
                "open": {"customer": "c"}}}))
            httpd = serve(str(keys), priv, host="127.0.0.1", port=0)
            threading.Thread(target=httpd.serve_forever, daemon=True).start()
            base = f"http://127.0.0.1:{httpd.server_address[1]}"
            try:
                for key, host, domain, allowed in (
                        ("apex", "www.example.com", "example.com", True),
                        ("apex", "example.com", "www.example.com", True),
                        ("apex", "staging.example.com", "example.com", False),
                        ("wild", "staging.example.com", "example.com", True),
                        ("below", "shop.example.com", "shop.example.com", True),
                        ("below", "example.com", "example.com", False),
                        ("open", "staging.example.com", "example.com", True),
                        ("open", "elsewhere.test", "example.com", False)):
                    with self.subTest(key=key, host=host, domain=domain):
                        if allowed:
                            signed = R.remote_sign(bundle(host, domain), base, key)
                            ok, why = B.verify_bundle(signed, pub)
                            self.assertTrue(ok, why)
                            self.assertIn(host, why)
                        else:
                            with self.assertRaises(urllib.error.HTTPError) as cm:
                                R.remote_sign(bundle(host, domain), base, key)
                            self.assertEqual(cm.exception.code, 403)
                            if key == "apex":
                                self.assertIn("*.example.com",
                                              cm.exception.read().decode())
                with self.assertRaises(urllib.error.HTTPError) as cm:
                    R.remote_sign(bundle("example.com", domain="Example.com"),
                                  base, "open")
                self.assertEqual(cm.exception.code, 400)
            finally:
                httpd.shutdown()
                httpd.server_close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
