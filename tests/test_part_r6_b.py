"""Part R, stage 6: the review of the decisions (R6AA, R6AB), and its fixes.

  R6AA-1  a path parameter's value in markup is REDACTED whatever else the
          snippet holds (the shortcut skipped it without "?", "#" or "@").
  R6AA-2  a rendered layer's status must be the one its note's counts make
          it, and a layer recorded twice is said.
  R6AA-3  the ";" that ends a character reference (&amp;) is no path
          parameter's separator in markup.
  R6AA-5  the README and the guide say path parameters are redacted, and
          when a snapshot is not evaluated.
  R6AB-1  Chromium 141 reads a <label> inside an aria-hidden element (it
          hides only one aria-hidden itself): no review says Chrome gives
          such a field or button no name.
  R6AB-2  the review says what the <label> is: empty or hidden, or holding
          only what Chrome and Edge do not read, the field aside.
  R6AB-3  a field named only by text in its <label> that Chromium does not
          read: minor where axe-core 4.12 passes it, else moderate.
  R6AB-4  a placeholder names only a text field or a <textarea>: a <select>
          or a date field named by nothing else fails.
  R6AB-6  CODEOWNERS and PREPUBLISH item 14 say the same.
  R6AB-7  the release workflow runs the release check for a final version.
  R6AB-8  ROADMAP's opening says item 2 is built in part.
Each name and axe-core verdict below was measured in Chromium 141 and
axe-core 4.12.1 (CDP Accessibility.getPartialAXTree; the label and
select-name rules).
"""
from __future__ import annotations

import contextlib
import io
import itertools
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bellbriar_harness import bundle as B                          # noqa: E402
from bellbriar_harness import cli                                  # noqa: E402
from bellbriar_harness import coverage_text as CT                  # noqa: E402
from bellbriar_harness import engine as E                          # noqa: E402
from bellbriar_harness import redact as R                          # noqa: E402
from bellbriar_harness.axe import AXE_VERSION                      # noqa: E402
from bellbriar_harness.checks_rendered import RENDERED_CHECKS      # noqa: E402
from bellbriar_harness.engine import load_rulebook, run_page       # noqa: E402
from bellbriar_harness.model import (BLOCKER, FAIL, MINOR,         # noqa: E402
                                     MODERATE, NEEDS_REVIEW,
                                     PageResult, RuleResult)

FIXTURES = ROOT / "fixtures"
RB = load_rulebook()


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = cli.main([str(a) for a in argv])
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


def tmpdir(test) -> Path:
    d = Path(tempfile.mkdtemp(prefix="bb-r6b-"))
    test.addCleanup(shutil.rmtree, d, True)
    return d


def page(body):
    return ('<!doctype html><html lang="en"><head><title>T</title></head>'
            f'<body><main><h1>T</h1>{body}</main></body></html>')


def signed(bundle):
    priv, pub, _kid = B.generate_keypair()
    return B.sign_bundle_local(bundle, priv), pub


# ---------------------------------------------------------------------------
# R6AA-1, R6AA-3: path parameters in markup
# ---------------------------------------------------------------------------

class TestPathParametersInMarkup(unittest.TestCase):

    def test_redacted_whatever_else_the_markup_holds(self):
        sid = "8F3A9C0D1E2B44F0"
        for text, want in (
                (f'<a href="/shop;jsessionid={sid}/cart"></a>',
                 '<a href="/shop;jsessionid=REDACTED/cart"></a>'),
                (f'<a href="/shop;jsessionid={sid}/cart?x=1"></a>',
                 '<a href="/shop;jsessionid=REDACTED/cart?x=REDACTED"></a>'),
                (f'see https://s.example/cart;jsessionid={sid} now',
                 'see https://s.example/cart;jsessionid=REDACTED now'),
                (f'<img src="/img;jsessionid={sid}/x.png" alt="">',
                 '<img src="/img;jsessionid=REDACTED/x.png" alt="">')):
            with self.subTest(text=text):
                self.assertEqual(R.redact_markup(text), want)

    def test_a_character_reference_is_no_separator(self):
        for text in ('<a href="/Q&amp;A/faq">FAQ</a>',
                     '<img src="/Tom&amp;Jerry.png#top" alt="">',
                     '<a href="/news&amp;events/2026">x</a>',
                     '<a href="/caf&eacute;/menu">x</a>',
                     '<p style="color:red;">a; b &amp; c</p>',
                     'Visit https://example.com/about; then'):
            with self.subTest(text=text):
                self.assertEqual(R.redact_markup(text), text)
        self.assertEqual(R.redact_markup('<a href="/Q&amp;A/faq?x=1">x</a>'),
                         '<a href="/Q&amp;A/faq?x=REDACTED">x</a>')
        # One that names a ";", or a name HTML does not have, separates
        # as the browser reads it.
        for text in ('<a href="/shop&semi;jsessionid=AB12/cart"></a>',
                     '<a href="/shop&zzz;jsessionid=AB12/cart"></a>',
                     '<a href="/shop&#59;jsessionid=AB12/cart"></a>',
                     '<a href="/caf&eacute;;sid=AB12/x"></a>',
                     # No reference in an attribute: "&amp" then "x;".
                     '<a href="/a&ampx;tok=AB12/b"></a>'):
            with self.subTest(text=text):
                self.assertNotIn("AB12", R.redact_markup(text))

    def test_a_run_writes_no_session_into_a_snippet(self):
        d = tmpdir(self)
        sid = "8F3A9C0D1E2B44F0"
        (d / "p.html").write_text(page(
            f'<a href="/shop/cart;jsessionid={sid}"></a>'
            f'<img src="/img;jsessionid={sid}/x.png">'), encoding="utf-8")
        code, out, err = run(d / "p.html", "--json", d / "r.json")
        self.assertIn(code, (0, 1), out + err)
        text = (d / "r.json").read_text(encoding="utf-8")
        self.assertNotIn(sid, text)
        self.assertIn("jsessionid=REDACTED", text)


# ---------------------------------------------------------------------------
# R6AA-2: layer records bound to what this release writes
# ---------------------------------------------------------------------------

def _pages(kinds):
    axe_rules = [r for r in RENDERED_CHECKS if r != E.REFLOW_RULE]
    out = []
    for kind in kinds:
        p = PageResult(path="p.html")
        if kind == "unread":
            p.parse_error = "ValueError: x"
            out.append(p)
            continue
        if kind in ("axe", "short", "both", "snap", "snapboth", "wide"):
            ids = axe_rules if kind != "short" else axe_rules[:3]
            p.results += [RuleResult(r, True) for r in ids]
            p.axe_version = AXE_VERSION
            p.axe_from_snapshot = kind in ("snap", "snapboth")
        if kind in ("reflow", "both", "snapboth", "wide"):
            p.results.append(RuleResult(E.REFLOW_RULE, True))
        p.narrow = kind != "wide"
        out.append(p)
    return out


class TestLayerRecordsBound(unittest.TestCase):

    def test_every_status_the_engine_writes_is_known(self):
        kinds = ("unread", "static", "axe", "short", "both", "snap",
                 "snapboth", "reflow", "wide")
        statuses = set()
        for n in (1, 2, 3):
            for combo in itertools.product(kinds, repeat=n):
                layers = E.layer_records(_pages(combo))
                self.assertEqual(CT.layer_problems(layers), [],
                                 (combo, layers))
                statuses.add(next(rec["status"] for rec in layers
                                  if rec["layer"] == "rendered"))
        self.assertEqual(statuses, {"executed", "partial", "skipped"})

    def rendered(self, kinds):
        layers = E.layer_records(_pages(kinds))
        return layers, next(i for i, rec in enumerate(layers)
                            if rec["layer"] == "rendered")

    def test_a_status_its_note_does_not_make(self):
        for kinds, flip in ((("both", "static"), "executed"),
                            (("short",), "executed"),
                            (("wide",), "executed"),
                            (("snap",), "executed"),
                            (("both",), "partial"),
                            (("snapboth", "snapboth"), "partial")):
            with self.subTest(kinds=kinds, flip=flip):
                layers, i = self.rendered(kinds)
                self.assertNotEqual(layers[i]["status"], flip)
                layers[i] = dict(layers[i], status=flip)
                self.assertEqual(CT.layer_problems(layers),
                                 ["the record of its rendered layer"])

    def test_a_layer_recorded_twice(self):
        layers, i = self.rendered(("both",))
        self.assertEqual(layers[0]["layer"], "static-dom")
        self.assertEqual(CT.layer_problems(layers + [dict(layers[0])]),
                         ["more than one record of its static-dom layer"])
        self.assertEqual(
            CT.layer_problems(layers + [dict(layers[0]), dict(layers[i])]),
            ["more than one record of its static-dom and rendered layers"])

    def test_verify_says_so_of_a_signed_bundle(self):
        d = tmpdir(self)
        code, out, err = run(FIXTURES / "good.html", "--bundle", d / "b.json")
        self.assertEqual(code, 0, out + err)
        bundle = json.loads((d / "b.json").read_text(encoding="utf-8"))
        bundle["layers"].append(dict(bundle["layers"][0]))
        ok, reason = B.verify_bundle(*signed(bundle))
        self.assertTrue(ok, reason)            # said, never refused
        self.assertIn("more than one record of its static-dom layer", reason)


# ---------------------------------------------------------------------------
# R6AB-1 to R6AB-4: form fields, measured
# ---------------------------------------------------------------------------

#: (body, the field's findings as (rule, verdict, impact) or [], words its
#: message holds). Chromium 141's name and axe-core 4.12's verdict, each
#: measured, are in the comment.
_CASES = [
    # R6AB-1. A <label> in an aria-hidden element: Chromium names by it.
    ('<div aria-hidden="true"><label for="f">Search</label></div>'
     '<input id="f" type="search" title="Search the site">', [], ()),
    #   ^ "Search", axe passes.
    ('<div aria-hidden="true"><div><label for="f">Deep</label></div></div>'
     '<input id="f" title="T">', [], ()),               # "Deep", passes
    ('<div aria-hidden="true"><label for="f" aria-hidden="false">Neg'
     '</label></div><input id="f" title="T">', [], ()),  # "Neg", passes
    ('<div aria-hidden="true"><label for="f">Size</label></div>'
     '<select id="f" title="T"><option>S</option></select>', [], ()),
    ('<div aria-hidden="true"><label for="f"><span>Inner</span></label>'
     '</div><textarea id="f" title="T"></textarea>', [], ()),
    ('<div aria-hidden="true"><label for="f">L</label></div>'
     '<label for="f"></label><input id="f" title="T">', [], ()),  # "L"
    ('<div aria-hidden="true"><label for="b">Save</label></div>'
     '<button id="b" title="Save it"></button>', [], ()),      # "Save"
    ('<div aria-hidden="true"><label for="b">Go</label></div>'
     '<input id="b" type="submit" value="Send">', [], ()),    # "Go"
    # Named by its placeholder alone as the computation reads it, by its
    # label in Chromium ("Email", axe passes): the review, no L104 words.
    ('<div aria-hidden="true"><label for="f">Email</label></div>'
     '<input id="f" type="email" placeholder="you@example.com">',
     [("bb-control-label", NEEDS_REVIEW, MODERATE)], ("placeholder",)),
    # Its own aria-hidden, or a hidden ancestor: "" in Chromium.
    ('<label for="f" aria-hidden="true">Email</label>'
     '<input id="f" type="email" title="T">',
     [("bb-control-label", NEEDS_REVIEW, MINOR)], ("empty or hidden",)),
    ('<div aria-hidden="true" style="display:none"><label for="f">X'
     '</label></div><input id="f" title="T">',
     [("bb-control-label", NEEDS_REVIEW, MINOR)], ("empty or hidden",)),
    ('<div aria-hidden="true"><label for="f"><span aria-hidden="true">Star'
     '</span></label></div><input id="f" title="T">',
     [("bb-control-label", NEEDS_REVIEW, MINOR)], ("empty or hidden",)),
    # The same label alone names a field in Chromium, which the
    # computation and axe-core leave nameless: it fails (L128).
    ('<div aria-hidden="true"><label for="f">Name</label></div>'
     '<input id="f">', [("bb-control-label", FAIL, BLOCKER)], ()),
    # R6AB-2: a label holding the field and an empty part, or the field.
    ('<label class="switch"><input type="checkbox" title="Dark mode">'
     '<span class="slider"></span></label>',
     [("bb-control-label", NEEDS_REVIEW, MINOR)],
     ("holds only what they do not read, the field itself aside",)),
    ('<label><input placeholder="Search"></label>',
     [("bb-control-label", NEEDS_REVIEW, MODERATE)],
     ("holds only what they do not read, the field itself aside",
      "(L104)")),
    # R6AB-3: text in the label Chromium does not read.
    ('<label for="f"><math><mi>x</mi></math></label><input id="f">',
     [("bb-control-label", NEEDS_REVIEW, MODERATE)], ("MathML",)),
    ('<label for="f"><math><mi>x</mi></math></label>'
     '<input id="f" title="T">',
     [("bb-control-label", NEEDS_REVIEW, MINOR)], ("<math>",)),
    ('<label for="f"><math><mi>x</mi></math></label>'
     '<input id="f" placeholder="P">',
     [("bb-control-label", NEEDS_REVIEW, MINOR)], ("<math>",)),
    ('<label for="f"><math><mi>x</mi></math></label>'
     '<textarea id="f" placeholder="P"></textarea>',
     [("bb-control-label", NEEDS_REVIEW, MINOR)], ("<math>",)),
    ('<label for="f"><math><mi>x</mi></math></label>'
     '<select id="f"><option>A</option></select>',
     [("bb-control-label", NEEDS_REVIEW, MODERATE)], ("MathML",)),
    ('<label for="f"><math><mi>x</mi></math></label>'
     '<select id="f" title="T"><option>A</option></select>',
     [("bb-control-label", NEEDS_REVIEW, MINOR)], ("<math>",)),
    ('<label for="f"><span title="Name"> </span></label><input id="f">',
     [("bb-control-label", NEEDS_REVIEW, MODERATE)],
     ("Nor does axe-core 4.12 read that title",)),
    ('<label for="f"><span role="presentation" title="Name"></span>'
     '</label><input id="f">',
     [("bb-control-label", NEEDS_REVIEW, MODERATE)],
     ("Nor does axe-core 4.12 read that title",)),
    ('<label for="f"><article>Name</article></label><input id="f">',
     [("bb-control-label", NEEDS_REVIEW, MODERATE)],
     ("by rules of its own",)),
    ('<label for="f"><object>Name</object></label><input id="f">',
     [("bb-control-label", NEEDS_REVIEW, MODERATE)], ("<object>",)),
    ('<label for="f"><i class="icon" title="City"></i></label>'
     '<input id="f">', [("bb-control-label", NEEDS_REVIEW, MINOR)],
     ("title of an <i>",)),                        # "", axe passes
    # axe-core passes this one by its <figure>; the review stays moderate,
    # and says only that other checks may fail it.
    ('<label for="f"><figure>Name</figure></label><input id="f">',
     [("bb-control-label", NEEDS_REVIEW, MODERATE)],
     ("may fail it too", "by rules of its own")),
]

#: R6AB-4: the input types a placeholder names (Chromium 141: the
#: placeholder is the name), and those it does not ("").
_NAMED_BY_PLACEHOLDER = ("text", "search", "tel", "url", "email",
                         "password", "number", "Number", "foo", " date", "")
_NOT_NAMED_BY_PLACEHOLDER = ("date", "DATE", "month", "week", "time",
                             "datetime-local", "range", "color", "checkbox",
                             "radio", "file")


class TestFieldsMeasured(unittest.TestCase):

    def findings(self, body):
        got = run_page(page(body), "t.html", RB)
        return [(r.rule_id, f) for r in got.results
                if r.rule_id in ("bb-control-label", "bb-button-name")
                for f in r.findings]

    def test_each_case(self):
        for body, want, words in _CASES:
            with self.subTest(body=body):
                found = self.findings(body)
                self.assertEqual([(rule, f.verdict, f.impact)
                                  for rule, f in found], want)
                for word in words:
                    self.assertIn(word, found[0][1].message)
                if found and "Chrome" in found[0][1].message:
                    self.assertNotIn("(it is empty or hidden)",
                                     found[0][1].message)

    def test_a_placeholder_names_text_fields_alone(self):
        for kind in _NAMED_BY_PLACEHOLDER:
            with self.subTest(type=kind):
                found = self.findings(f'<input type="{kind}" placeholder="P">'
                                      if kind else '<input placeholder="P">')
                self.assertEqual([(f.verdict, f.impact) for _r, f in found],
                                 [(NEEDS_REVIEW, MODERATE)])
        found = self.findings('<textarea placeholder="P"></textarea>')
        self.assertEqual([(f.verdict, f.impact) for _r, f in found],
                         [(NEEDS_REVIEW, MODERATE)])
        for kind in _NOT_NAMED_BY_PLACEHOLDER:
            with self.subTest(type=kind):
                found = self.findings(f'<input type="{kind}" placeholder="P">')
                self.assertEqual([(f.verdict, f.impact) for _r, f in found],
                                 [(FAIL, BLOCKER)])
                self.assertIn("though axe-core 4.12 passes an <input> by its "
                              "placeholder", found[0][1].message)
        for body in ('<select placeholder="Country"><option>A</option>'
                     '</select>',
                     '<select multiple placeholder="C"><option>A</option>'
                     '</select>'):
            with self.subTest(body=body):
                found = self.findings(body)
                self.assertEqual([(f.verdict, f.impact) for _r, f in found],
                                 [(FAIL, BLOCKER)])
                self.assertIn("Its placeholder does not name it",
                              found[0][1].message)
                self.assertNotIn("axe-core", found[0][1].message)
        # A field with no placeholder says nothing of one.
        found = self.findings('<input type="date">')
        self.assertEqual(found[0][1].message,
                         "Form field has no associated label or accessible "
                         "name.")


# ---------------------------------------------------------------------------
# R6AA-5, R6AB-6 to R6AB-8: the documents
# ---------------------------------------------------------------------------

def _flat(rel):
    return re.sub(r"\s+", " ", (ROOT / rel).read_text(encoding="utf-8"))


class TestTheDocuments(unittest.TestCase):

    def test_path_parameters_and_re_runs(self):
        readme = _flat("README.md")
        guide = _flat("docs/MEASUREMENT-AND-EVIDENCE-GUIDE.md")
        for text in (readme, guide):
            self.assertIn("every path parameter's (`/cart;jsessionid=…`)",
                          text)
            self.assertIn("every query value and path parameter's value "
                          "`REDACTED`", text)
            self.assertNotIn("A token in a path is recorded", text)
            self.assertNotIn("A token written into a path", text)
        self.assertIn("keeps the value of a query or path parameter", readme)
        self.assertIn("Re-run so, a snapshot whose capture does not record "
                      "this release's marks", readme)

    def test_codeowners_and_item_14_agree(self):
        """CODEOWNERS names the maintainer's own account (a GitHub user,
        not a team: Oct 13), as PREPUBLISH item 14 says, and SECURITY.md
        gives an address for reporters without a GitHub account."""
        owners = (ROOT / ".github" / "CODEOWNERS").read_text(encoding="utf-8")
        prepublish = _flat("PREPUBLISH.md")
        self.assertEqual(re.findall(r"(?m)^[^#\s].*$", owners),
                         ["* @bellbriar"])
        self.assertNotIn("Every change is reviewed", owners)
        self.assertIn("`.github/CODEOWNERS` names that person's account "
                      "(`@bellbriar`", prepublish)
        self.assertNotIn("@bellbriar/maintainers", prepublish)
        security = _flat("SECURITY.md")
        self.assertIn("If you have no GitHub account, e-mail "
                      "security@bellbriar.com instead.", security)
        self.assertIn("SECURITY.md gives security@bellbriar.com", prepublish)

    def test_a_final_release_runs_the_release_check(self):
        import yaml
        wf = yaml.safe_load((ROOT / ".github" / "workflows" / "release.yml")
                            .read_text(encoding="utf-8"))
        steps = wf["jobs"]["build"]["steps"]
        names = [s.get("name", "") for s in steps]
        check = next(s for s in steps
                     if "nothing pending" in s.get("name", ""))
        # After the version is known, before anything is built.
        self.assertLess(names.index(check["name"]),
                        next(i for i, s in enumerate(steps)
                             if "python -m build" in s.get("run", "")))
        self.assertEqual(check["env"]["BELLBRIAR_RELEASE"], "1")
        self.assertIn("test_nothing_is_pending_for_a_release", check["run"])
        self.assertIn("*rc[0-9]*", check["run"])
        # A check skipped, not run, stops the release too.
        self.assertIn('grep -qx "OK" "$RUNNER_TEMP/release-check.log"',
                      check["run"])
        self.assertIn('cd "$RUNNER_TEMP/release-check"', check["run"])
        self.assertIn("the release workflow refuses a final version",
                      _flat("PREPUBLISH.md"))

    def test_the_roadmap_says_item_2_is_built_in_part(self):
        self.assertIn("but item 1 (built, struck out) and the part of item 2 "
                      "it says is built, is **[not built]** at harness",
                      _flat("docs/ROADMAP.md"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
