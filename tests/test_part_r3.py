"""Part R, stage 3: the report.

  A8  The JSON report is `bellbriar-report/1`: a format string, every field
      documented (docs/REPORT.md) and stated as a JSON Schema
      (docs/bellbriar-report-1.schema.json) that real reports are checked
      against, and a fingerprint per finding (`--baseline` matches by it,
      A10).
      `bellbriar-lint --format json` is `bellbriar-lint/1`.
  A6  Fix guidance for every rule that runs (guidance.py): why it matters,
      how to fix it, and HTML, React and Vue examples. The HTML examples
      are run here: the "before" one is found by its rule, the "after" one
      is not and fails nothing. docs/RULES.md, the rules reference, is
      generated from the rulebook and the guidance and must be current.
  A7  The HTML report groups findings by rule, with counts, then by page;
      findings that read the same are shown once with their count, on a
      page or across pages (L46); it shows each page's capture record and
      the vendor behind third-party findings, and every table's caption
      names its rule and page (P5-08).

Building the executable guidance showed that axe-core 4.12.1 never fails
two rules the rulebook called heuristic, th-has-data-cells and
server-side-image-map (each only reports what it cannot decide), so they
counted as passes they could never fail: both are `review` now.
"""
import contextlib
import copy
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
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from bellbriar_harness import cli                                # noqa: E402
from bellbriar_harness import report as R                        # noqa: E402
from bellbriar_harness import report_html as RH                  # noqa: E402
from bellbriar_harness.engine import load_rulebook, run_page     # noqa: E402
from bellbriar_harness.guidance import (EXAMPLE_PAGES, GUIDANCE,  # noqa: E402
                                        example_page)
from bellbriar_harness.lint import LINT_FORMAT, lint_text        # noqa: E402
from bellbriar_harness.model import FAIL, MINOR, Finding         # noqa: E402
from tests.test_fetch_hardening import HAVE_BROWSER, _WHY        # noqa: E402

FIXTURES = ROOT / "fixtures"
SCHEMA = json.loads((ROOT / "docs" / "bellbriar-report-1.schema.json")
                    .read_text(encoding="utf-8"))
REPORT_DOC = (ROOT / "docs" / "REPORT.md").read_text(encoding="utf-8")
PAGE = ('<!doctype html><html lang="en"><head><title>T</title></head><body>'
        '<main><h1>T</h1>{}</main></body></html>')


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = cli.main([str(a) for a in argv])
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


def report_of(*argv) -> tuple[dict, str]:
    """(the JSON report, the HTML report) of a run."""
    d = Path(tempfile.mkdtemp(prefix="bb-r3-"))
    try:
        run(*argv, "--json", d / "r.json", "--html", d / "r.html",
            "--fail-on", "never")
        return (json.loads((d / "r.json").read_text(encoding="utf-8")),
                (d / "r.html").read_text(encoding="utf-8"))
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ---------------------------------------------------------------------------
# A small JSON Schema validator, for the keywords the report's schema uses,
# so the check does not depend on a library the harness does not require.
# Where `jsonschema` is installed, the schema is checked with it too.
# ---------------------------------------------------------------------------

_TYPES = {"object": dict, "array": list, "string": str, "boolean": bool,
          "null": type(None)}


def _is(value, t: str) -> bool:
    if t == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if t == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, _TYPES[t])


def validate(value, schema: dict, root: dict = SCHEMA, at: str = "$"
             ) -> list[str]:
    if "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[-1]
        return validate(value, root["$defs"][name], root, at)
    out = []
    if "oneOf" in schema:
        ok = [s for s in schema["oneOf"] if not validate(value, s, root, at)]
        if len(ok) != 1:
            out.append(f"{at}: matches {len(ok)} of oneOf")
        return out
    if "const" in schema and value != schema["const"]:
        out.append(f"{at}: {value!r} is not {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        out.append(f"{at}: {value!r} not in {schema['enum']}")
    if "type" in schema:
        types = schema["type"] if isinstance(schema["type"], list) \
            else [schema["type"]]
        if not any(_is(value, t) for t in types):
            return out + [f"{at}: {type(value).__name__} is not {types}"]
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            out.append(f"{at}: below {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            out.append(f"{at}: above {schema['maximum']}")
    if isinstance(value, str) and "pattern" in schema and \
            not re.search(schema["pattern"], value):
        out.append(f"{at}: {value!r} does not match {schema['pattern']}")
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                out.append(f"{at}: missing {key}")
        props = schema.get("properties", {})
        for key, sub in value.items():
            if key in props:
                out += validate(sub, props[key], root, f"{at}.{key}")
            elif isinstance(schema.get("additionalProperties"), dict):
                out += validate(sub, schema["additionalProperties"], root,
                                f"{at}.{key}")
    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            out.append(f"{at}: fewer than {schema['minItems']} items")
        if "items" in schema:
            for i, item in enumerate(value):
                out += validate(item, schema["items"], root, f"{at}[{i}]")
    return out


def undeclared(value, schema: dict, root: dict = SCHEMA, at: str = "$"
               ) -> list[str]:
    """Keys the report has that the schema, where it lists an object's
    properties, does not declare: a field nobody documented."""
    if "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[-1]
        return undeclared(value, root["$defs"][name], root, at)
    if "oneOf" in schema:
        for s in schema["oneOf"]:
            if not validate(value, s, root, at):
                return undeclared(value, s, root, at)
        return []
    out = []
    if isinstance(value, dict) and "properties" in schema:
        for key, sub in value.items():
            if key not in schema["properties"]:
                out.append(f"{at}.{key}")
            else:
                out += undeclared(sub, schema["properties"][key], root,
                                  f"{at}.{key}")
    elif isinstance(value, dict) and isinstance(
            schema.get("additionalProperties"), dict):
        for key, sub in value.items():
            out += undeclared(sub, schema["additionalProperties"], root,
                              f"{at}.{key}")
    elif isinstance(value, list) and "items" in schema:
        for i, item in enumerate(value):
            out += undeclared(item, schema["items"], root, f"{at}[{i}]")
    return out


def schema_properties(schema: dict = SCHEMA) -> set:
    """Every property name the schema declares."""
    names = set()

    def walk(node):
        if isinstance(node, dict):
            names.update(node.get("properties", {}))
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(schema)
    return names


class TestSchema(unittest.TestCase):
    """A8: the format and its schema."""

    def check(self, report: dict) -> None:
        self.assertEqual(report["format"], "bellbriar-report/1")
        self.assertEqual(validate(report, SCHEMA), [])
        self.assertEqual(undeclared(report, SCHEMA), [])
        try:
            import jsonschema
        except ImportError:
            return
        jsonschema.Draft202012Validator.check_schema(SCHEMA)
        errors = [e.message for e in jsonschema.Draft202012Validator(
            SCHEMA).iter_errors(report)]
        self.assertEqual(errors, [])

    def test_a_file_run(self):
        report, _html = report_of(FIXTURES / "bad.html",
                                  FIXTURES / "subtle-bad.html",
                                  FIXTURES / "good.html")
        self.check(report)
        self.assertIsNone(report["fetch"])
        self.assertIsNone(report["judged"])
        self.assertTrue(all(p["fetch"] is None for p in report["pages"]))

    def test_an_incomplete_run_and_an_app_shell(self):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        (d / "shell.html").write_text(
            '<!doctype html><html lang="en"><head><title>A</title>'
            '<script src="/app.js"></script></head><body><div id="root">'
            '</div></body></html>', encoding="utf-8")
        (d / "deep.html").write_text(
            "<!doctype html><html lang=en><head><title>T</title></head>"
            "<body><p>" + "".join(f"<b id=b{i}>" for i in range(1000))
            + "</p>" + "<p>x</p>" * 1000, encoding="utf-8")
        report, html = report_of(d / "shell.html", d / "deep.html")
        self.check(report)
        self.assertTrue(report["incomplete"])
        self.assertEqual(report["errors"], 1)
        shell = next(p for p in report["pages"]
                     if p["path"].endswith("shell.html"))
        self.assertFalse(shell["score"]["evaluable"])
        self.assertIn("Incomplete run", html)
        self.assertIn("client-rendered app shell", html)

    def test_every_schema_field_is_documented(self):
        for name in sorted(schema_properties()):
            with self.subTest(field=name):
                self.assertIn(f"`{name}`", REPORT_DOC)

    def test_the_lint_format(self):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        (d / "a.jsx").write_text('<div onClick={go}>x</div>\n')
        from bellbriar_harness import lint as L
        out = io.StringIO()
        with contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(io.StringIO()):
            L.main([str(d), "--format", "json", "--fail-on", "never"])
        data = json.loads(out.getvalue())
        self.assertEqual(data["format"], LINT_FORMAT)
        self.assertEqual(LINT_FORMAT, "bellbriar-lint/1")
        self.assertEqual(list(data), ["format", "files_scanned", "errors",
                                      "warnings", "notes", "findings"])
        self.assertEqual(set(data["findings"][0]),
                         {"rule_id", "severity", "path", "line", "message",
                          "ref", "snippet"})
        for name in list(data) + list(data["findings"][0]):
            with self.subTest(field=name):
                self.assertIn(f"`{name}`", REPORT_DOC)


@unittest.skipUnless(HAVE_BROWSER, _WHY)
class TestSchemaRendered(TestSchema):
    """The same checks on a --render run and a URL run, whose pages carry
    capture records, with vendor markup reported apart."""

    test_a_file_run = None
    test_an_incomplete_run_and_an_app_shell = None
    test_every_schema_field_is_documented = None
    test_the_lint_format = None

    def test_a_render_run(self):
        report, html = report_of(FIXTURES / "bad.html", FIXTURES / "good.html",
                                 "--render")
        self.check(report)
        self.assertIsNone(report["fetch"])
        for page in report["pages"]:
            self.assertEqual(page["fetch"]["mode"], "rendered")
            # P5-08: the capture record is in the HTML report.
            self.assertIn(page["fetch"]["snapshot_sha256"], html)
            self.assertIn(page["fetch"]["fetched_at"], html)
        self.assertIn("How each page was read", html)
        self.assertIn("rendered by chromium", html)

    def test_a_url_run_with_vendor_markup(self):
        from tests.test_fetch import TwoOriginSite
        site = TwoOriginSite()
        self.addCleanup(site.stop)
        report, html = report_of("--url", site.url, "--third-party-origin",
                                 site.third.base)
        self.check(report)
        self.assertEqual(report["fetch"]["host"], "127.0.0.1")
        vendor = [f for p in report["pages"] for f in p["findings"]
                  if f["origin"] == "third-party"]
        self.assertTrue(vendor, "the fixture's vendor markup has findings")
        self.assertTrue(all(not f["owned"] for f in vendor))
        # P5-08: the vendor behind each is named, not just "3rd-party".
        self.assertIn(vendor[0]["origin_detail"], html)
        self.assertIn("In markup a vendor's script inserted", html)
        server = [p["fetch"] for p in report["pages"]]
        self.assertTrue(all(fb["final_url"] in html for fb in server))


# ---------------------------------------------------------------------------
# Fingerprints
# ---------------------------------------------------------------------------

class TestFingerprints(unittest.TestCase):
    """A8: what --baseline (A10) matches findings by."""

    @staticmethod
    def prints(html: str, path: str = "p.html") -> dict:
        page = run_page(html, path, load_rulebook())
        pairs = [(rr.rule_id, f) for rr in page.results for f in rr.findings]
        return {(rid, f.snippet, i): fp for i, ((rid, f), fp) in
                enumerate(zip(pairs, R.finding_fingerprints(path, pairs)))}

    def test_a_line_moving_keeps_the_fingerprint(self):
        link = '<a href="/x"></a>'
        a = self.prints(PAGE.format(link))
        b = self.prints(PAGE.format("<p>New</p>\n\n\n<p>lines</p>\n" + link))
        fa = {fp for (rid, snip, _i), fp in a.items() if rid == "bb-link-name"}
        fb = {fp for (rid, snip, _i), fp in b.items() if rid == "bb-link-name"}
        self.assertEqual(len(fa), 1)
        self.assertEqual(fa, fb)

    def test_copies_of_one_element_are_told_apart(self):
        got = self.prints(PAGE.format('<a href="/x"></a>' * 3))
        fps = [fp for (rid, _s, _i), fp in got.items()
               if rid == "bb-link-name"]
        self.assertEqual(len(fps), 3)
        self.assertEqual(len(set(fps)), 3)
        self.assertEqual(fps, [fp for (rid, _s, _i), fp in self.prints(
            PAGE.format('<a href="/x"></a>' * 3)).items()
            if rid == "bb-link-name"])

    def test_the_message_and_line_are_left_out(self):
        f1 = Finding("bb-link-name", FAIL, "blocker", "one wording", line=3,
                     snippet='<a href="/x"></a>')
        f2 = Finding("bb-link-name", FAIL, "blocker", "another wording",
                     line=90, snippet='<a href="/x"></a>')
        self.assertEqual(
            R.finding_fingerprints("p.html", [("bb-link-name", f1)]),
            R.finding_fingerprints("p.html", [("bb-link-name", f2)]))

    def test_the_page_and_the_rule_count(self):
        f = Finding("bb-link-name", FAIL, "blocker", "m",
                    snippet='<a href="/x"></a>')
        base = R.finding_fingerprints("a.html", [("bb-link-name", f)])
        self.assertNotEqual(base, R.finding_fingerprints(
            "b.html", [("bb-link-name", f)]))
        self.assertNotEqual(base, R.finding_fingerprints(
            "a.html", [("bb-button-name", f)]))

    def test_the_documented_construction(self):
        """REPORT.md's "`about` and fingerprints", step by step (R3A-3,
        R3C-1, R3C-2, R3C-7)."""
        import hashlib

        def digest(value):
            return hashlib.sha256(json.dumps(
                value, ensure_ascii=True, separators=(",", ":")).encode(
                "ascii")).hexdigest()[:32]
        # The doc's example, written two ways that read the same.
        html = PAGE.format('<a href="/cart" class="icon  big">\n  Caf\u00e9 '
                           '<b>menu</b></a><a class="icon big" href="/cart">'
                           'Caf\u00e9 <b>menu</b></a>')
        page = run_page(html, "p.html", load_rulebook())
        pairs = [(rr.rule_id, f) for rr in page.results for f in rr.findings
                 if rr.rule_id == "bb-redundant-links"]
        self.assertTrue(pairs)
        value = [["a", [["class", "icon big"], ["href", "/cart"]]],
                 "Caf\u00e9 menu", [["b", []]]]
        self.assertIn("`" + json.dumps(value, ensure_ascii=False,
                                       separators=(",", ":")) + "`",
                      REPORT_DOC)
        about = digest(value)
        self.assertEqual(pairs[0][1].about, about)
        self.assertEqual(
            R.finding_fingerprints("p.html", pairs[:1]),
            [digest(["bellbriar-finding/1", "bb-redundant-links", "p.html",
                     0, about, 0])])
        # The page as a whole: its own tag alone.
        doc = ('<!doctype html><html><head><title>T</title>'
               '<meta name="csrf" content="{}"></head><body>'
               '<main><h1>T</h1></main></body></html>')
        one = run_page(doc.format("AAAA"), "p.html", load_rulebook())
        two = run_page(doc.format("BBBB"), "p.html", load_rulebook())

        def lang(page):
            return [f.about for rr in page.results for f in rr.findings
                    if rr.rule_id == "bb-html-lang"]
        self.assertEqual(lang(one), [digest([["html", []], "", []])])
        self.assertEqual(lang(one), lang(two))

    def test_a_long_shared_prefix_does_not_move_a_fingerprint(self):
        """R3A-4: two controls told apart only past 180 characters; fixing
        one must leave the other's fingerprint where it was."""
        cls = ("inline-flex items-center justify-center whitespace-nowrap "
               "rounded-md text-sm font-medium ring-offset-background "
               "transition-colors focus-visible:outline-none "
               "focus-visible:ring-2 h-10 w-10")
        btn = ('<button class="{}" data-action="{}"{}><svg aria-hidden="true">'
               '</svg></button>')
        before = PAGE.format(btn.format(cls, "save", "")
                             + btn.format(cls, "delete", ""))
        after = PAGE.format(btn.format(cls, "save", ' aria-label="Save"')
                            + btn.format(cls, "delete", ""))

        def prints(html):
            page = run_page(html, "p.html", load_rulebook())
            pairs = [(rr.rule_id, f) for rr in page.results
                     for f in rr.findings if rr.rule_id == "bb-button-name"]
            # By where each is: the snippets, cut at 180 characters, are
            # the same.
            return dict(zip([f.selector[0] for _r, f in pairs],
                            R.finding_fingerprints("p.html", pairs)))
        b, a = prints(before), prints(after)
        self.assertEqual(len(b), 2)
        self.assertEqual(len(set(b.values())), 2)
        self.assertEqual(len(a), 1)
        (where, fp), = a.items()
        self.assertEqual(b[where], fp, "the delete button's fingerprint moved")

    def test_two_pages_with_one_recorded_path(self):
        """R3A-1: URLs that differ only in redacted values share a path;
        their findings must not share fingerprints."""
        f = Finding("bb-link-name", FAIL, "blocker", "m", about="a" * 32)
        one = R.finding_fingerprints("p?id=REDACTED", [("bb-link-name", f)], 0)
        two = R.finding_fingerprints("p?id=REDACTED", [("bb-link-name", f)], 1)
        self.assertNotEqual(one, two)

    def test_unique_in_a_report(self):
        report, _html = report_of(FIXTURES / "bad.html",
                                  FIXTURES / "subtle-bad.html")
        prints = [f["fingerprint"] for p in report["pages"]
                  for f in p["findings"]]
        self.assertEqual(len(prints), len(set(prints)))


# ---------------------------------------------------------------------------
# A6: guidance and the rules reference
# ---------------------------------------------------------------------------

def _runs() -> list[dict]:
    return [r for r in load_rulebook()["rules"]
            if r.get("status") == "implemented"
            and r.get("layer") in ("static-dom", "rendered")]


class TestGuidance(unittest.TestCase):

    def test_every_rule_that_runs_has_guidance(self):
        ids = [r["id"] for r in _runs()]
        self.assertEqual(sorted(GUIDANCE), sorted(ids))
        for rid in ids:
            g = GUIDANCE[rid]
            with self.subTest(rule=rid):
                for key in ("why", "fix", "html_bad", "html_good", "react",
                            "vue"):
                    self.assertTrue(g.get(key, "").strip(), key)
                self.assertIn(g.get("where", "body"), EXAMPLE_PAGES)
                self.assertNotEqual(g["html_bad"], g["html_good"])
                self.assertEqual(set(g) - {"why", "fix", "html_bad",
                                           "html_good", "react", "vue",
                                           "where", "good_still_reviews"},
                                 set())

    def test_the_static_examples_do_what_they_say(self):
        rb = load_rulebook()
        for r in _runs():
            if r["layer"] != "static-dom":
                continue
            rid, g = r["id"], GUIDANCE[r["id"]]
            where = g.get("where", "body")
            with self.subTest(rule=rid):
                bad = run_page(example_page(g["html_bad"], where), "b.html", rb)
                own = [f for rr in bad.results if rr.rule_id == rid
                       for f in rr.findings]
                self.assertTrue(own, "the 'before' example finds nothing")
                if r.get("verdict_basis") in ("sc", "heuristic"):
                    self.assertIn(FAIL, {f.verdict for f in own})
                good = run_page(example_page(g["html_good"], where), "g.html",
                                rb)
                own = [f for rr in good.results if rr.rule_id == rid
                       for f in rr.findings]
                if g.get("good_still_reviews") == rid:
                    self.assertTrue(all(f.verdict != FAIL
                                        and f.impact == MINOR for f in own))
                else:
                    self.assertEqual(own, [])
                fails = [(rr.rule_id, f.message) for rr in good.results
                         for f in rr.findings if f.verdict == FAIL]
                self.assertEqual(fails, [], "the 'after' example fails")

    def test_the_framework_examples_lint_without_errors(self):
        """Guidance must not teach what bellbriar-lint calls an error. A
        Vue example is a single-file component when it has a <template>,
        and otherwise markup inside one (or plain script)."""
        for rid, g in GUIDANCE.items():
            vue = g["vue"]
            if "<template>" not in vue and not vue.lstrip().startswith(
                    ("<script", "//")):
                vue = "<template>\n" + vue + "\n</template>"
            for path, src in (("Example.jsx", g["react"]),
                              ("Example.vue", vue)):
                with self.subTest(rule=rid, file=path):
                    errors = [(f.rule_id, f.message) for f in
                              lint_text(src, path) if f.severity == "error"]
                    self.assertEqual(errors, [])

    def test_a_vue_example_with_styles_is_a_component(self):
        """R3B-12: a <style> beside bare markup is neither a template nor a
        single-file component."""
        for rid, g in GUIDANCE.items():
            if "<style" in g["vue"]:
                with self.subTest(rule=rid):
                    self.assertTrue(g["vue"].startswith("<template>"))

    def test_claims_the_reviews_found_false_are_gone(self):
        """R3B-1 to R3B-4, R3B-8, R3B-9: what the guidance said that the
        standards, the browsers or the rule itself contradict."""
        text = {rid: g["why"] + " " + g["fix"] for rid, g in GUIDANCE.items()}
        self.assertNotIn("overrides", text["bb-aria-conditional-attr"])
        self.assertIn("ignore aria-checked", text["bb-aria-conditional-attr"])
        self.assertNotIn("hover", text["bb-link-in-text"])
        self.assertIn("G183", text["bb-link-in-text"])
        self.assertIn("not checked", text["bb-aria-required-attr"])
        self.assertNotIn("get nothing", text["bb-aria-braille"])
        self.assertIn("aria-controls", text["bb-aria-ref"])
        self.assertIn("meets WCAG 2.4.4", text["bb-generic-link-text"])
        rb = {r["id"]: r for r in load_rulebook()["rules"]}
        self.assertNotIn("hover", rb["bb-link-in-text"]["notes"])

    def test_guidance_text_is_plain(self):
        for rid, g in GUIDANCE.items():
            for key in ("why", "fix"):
                with self.subTest(rule=rid, key=key):
                    text = g[key]
                    self.assertLess(len(text), 420)
                    self.assertTrue(text.endswith("."))
                    self.assertNotIn("  ", text)


@unittest.skipUnless(HAVE_BROWSER, _WHY)
class TestRenderedExamples(unittest.TestCase):
    """The rendered rules' examples, in a browser: each "before" example is
    found by its rule, inside that example; each "after" one is not, and no
    "after" example fails any rule."""

    @classmethod
    def setUpClass(cls):
        from bs4 import BeautifulSoup
        cls.rules = {r["id"]: r for r in _runs() if r["layer"] == "rendered"}
        d = Path(tempfile.mkdtemp(prefix="bb-r3-ex-"))
        cls.tmp = d
        site = d / "site"
        site.mkdir()
        # bb-object-alt applies only to an <object> whose data loaded.
        (site / "sales.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="40" height="20">'
            '<rect width="40" height="20" fill="#36c"/></svg>')
        single = {}
        for kind in ("bad", "good"):
            body = []
            for rid in cls.rules:
                g = GUIDANCE[rid]
                if g.get("where", "body") != "body":
                    name = f"{kind}-{rid}.html"
                    single[name] = rid
                    (site / name).write_text(
                        example_page(g[f"html_{kind}"], g["where"]))
                    continue
                body.append(f'<div id="ex-{rid}">{g["html_" + kind]}</div>')
            (site / f"{kind}.html").write_text(example_page("\n".join(body)))
        code, _out, err = run(site, "--render", "--require-render", "--json",
                              d / "r.json", "--save-snapshots", d / "snaps",
                              "--fail-on", "never")
        assert code == 0, err
        report = json.loads((d / "r.json").read_text())
        snaps = sorted((d / "snaps").glob("*.html"))
        cls.found: dict = {}
        for page, snap in zip(report["pages"], snaps):
            name = Path(page["path"]).name
            kind = name.split("-", 1)[0].split(".", 1)[0]
            soup = BeautifulSoup(snap.read_text(encoding="utf-8"),
                                 "html.parser")
            for f in page["findings"]:
                where = single.get(name)
                if where is None and f["selector"]:
                    el = soup.select_one(f["selector"][0])
                    while el is not None and getattr(el, "name", None):
                        if (el.get("id") or "").startswith("ex-"):
                            where = el["id"][3:]
                            break
                        el = el.parent
                cls.found.setdefault((kind, f["rule_id"], where), []).append(f)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_each_before_example_is_found_by_its_rule(self):
        for rid, r in self.rules.items():
            with self.subTest(rule=rid):
                got = self.found.get(("bad", rid, rid), [])
                self.assertTrue(got)
                if r.get("verdict_basis") in ("sc", "heuristic"):
                    self.assertIn("fail", {f["verdict"] for f in got})

    def test_no_after_example_is_found_or_fails(self):
        for rid in self.rules:
            with self.subTest(rule=rid):
                self.assertEqual(self.found.get(("good", rid, rid), []), [])
        fails = [(k, f["message"][:60]) for k, fs in self.found.items()
                 for f in fs if k[0] == "good" and f["verdict"] == "fail"]
        self.assertEqual(fails, [])

    def test_every_rule_that_can_fail_does(self):
        """Part R3: axe-core 4.12.1 never fails th-has-data-cells or
        server-side-image-map: a rule that can never FAIL is no
        `heuristic` rule, or it counts as a free pass."""
        for rid, r in self.rules.items():
            if r.get("verdict_basis") not in ("sc", "heuristic"):
                continue
            with self.subTest(rule=rid):
                self.assertIn("fail", {f["verdict"] for f in
                                       self.found.get(("bad", rid, rid), [])})
        basis = {r["id"]: r.get("verdict_basis")
                 for r in load_rulebook()["rules"]}
        self.assertEqual(basis["bb-th-data-cells"], "review")
        self.assertEqual(basis["bb-server-image-map"], "review")


class TestRulesReference(unittest.TestCase):

    def test_docs_rules_md_is_current(self):
        from make_rules_reference import OUT, render
        self.assertEqual(OUT.read_text(encoding="utf-8"),
                         render(load_rulebook()),
                         "run python tools/make_rules_reference.py")

    def test_it_lists_every_rule(self):
        text = (ROOT / "docs" / "RULES.md").read_text(encoding="utf-8")
        for r in load_rulebook()["rules"]:
            with self.subTest(rule=r["id"]):
                self.assertIn(f"`{r['id']}`", text)
        import html as H
        for r in _runs():
            with self.subTest(rule=r["id"]):
                self.assertIn(f"### {r['id']}\n", text)
                self.assertIn(H.escape(GUIDANCE[r["id"]]["fix"], quote=False),
                              text)

    def test_it_survives_a_markdown_viewer(self):
        """R3B-6: a tag named in prose (<title>, <summary>) became one in a
        Markdown viewer, and swallowed the rest of the page."""
        text = (ROOT / "docs" / "RULES.md").read_text(encoding="utf-8")
        prose, fenced = [], False
        for line in text.splitlines():
            if line.startswith("```"):
                fenced = not fenced
            elif not fenced:
                prose.append(line)
        self.assertEqual([ln for ln in prose if re.search(r"<[a-zA-Z/!]", ln)],
                         [])
        try:
            from markdown_it import MarkdownIt
        except ImportError:
            return
        html = MarkdownIt("commonmark", {"html": True}).enable(
            "table").render(text)
        for r in _runs():
            with self.subTest(rule=r["id"]):
                self.assertIn(f"<h3>{r['id']}</h3>", html)

    def test_its_basis_lines_are_true(self):
        """R3B-5, R3B-14: best-practice is not "classed as a best practice"
        by W3C or axe-core for every rule; --strict counts reviews."""
        text = (ROOT / "docs" / "RULES.md").read_text(encoding="utf-8")
        self.assertNotIn("class it as a best practice", text)
        self.assertIn("--strict", text)


# ---------------------------------------------------------------------------
# A7: the HTML report's layout
# ---------------------------------------------------------------------------

class TestHtmlLayout(unittest.TestCase):

    def test_grouped_by_rule_then_by_page(self):
        report, html = report_of(FIXTURES / "bad.html",
                                 FIXTURES / "subtle-bad.html")
        self.assertNotRegex(html, r"<caption[^>]*>Findings</caption>")
        self.assertIn("<h2>Rules with findings</h2>", html)
        self.assertIn('<h2 id="findings">Findings by rule</h2>', html)
        ids = {f["rule_id"] for p in report["pages"] for f in p["findings"]}
        for rid in ids:
            with self.subTest(rule=rid):
                self.assertIn(f'<h3 id="rule-{rid}">', html)
                self.assertIn(f'href="#rule-{rid}"', html)
        # Every table names what it holds: the rule and the page.
        captions = re.findall(r"<caption[^>]*>(.*?)</caption>", html)
        self.assertGreaterEqual(len(captions), 3)
        for cap in captions:
            with self.subTest(caption=cap):
                self.assertTrue(cap.startswith(("Rules with findings",
                                                "Pages evaluated", "bb-")))
        for page in report["pages"]:
            self.assertIn(f"bb-link-name on {page['path']}:", html)

    def test_the_guidance_is_shown_beside_the_findings(self):
        _report, html = report_of(FIXTURES / "bad.html")
        g = GUIDANCE["bb-img-alt"]
        import html as H
        self.assertIn(H.escape(g["why"]), html)
        self.assertIn(H.escape(g["fix"]), html)
        self.assertIn(H.escape(g["react"]), html)
        self.assertIn("Fix examples for &ldquo;Images have text "
                      "alternatives&rdquo;: HTML, React and Vue", html)

    def test_the_same_finding_on_many_pages_is_shown_once(self):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        for i in range(4):
            (d / f"p{i}.html").write_text(PAGE.format(
                '<a href="/cart"><svg aria-hidden="true"></svg></a>'
                f'<p>Page {i}</p>' + ('<a href="/x"></a>' if i == 0 else "")))
        report, html = report_of(d)
        self.assertEqual(len(report["pages"]), 4)
        self.assertIn("bb-link-name: findings on more than one page", html)
        self.assertIn("<strong>4 pages</strong>", html)
        # The page-specific one is in its page's table.
        first = report["pages"][0]["path"]
        self.assertTrue(first.endswith("p0.html"))
        self.assertIn(f"bb-link-name on {first}: 1 failure", html)
        # The JSON keeps every finding.
        self.assertEqual(sum(1 for p in report["pages"] for f in p["findings"]
                             if f["rule_id"] == "bb-link-name"), 5)

    def test_copies_on_one_page_are_counted_in_one_row(self):
        report, html = report_of(*self._page('<a href="/x"></a>' * 7))
        self.assertIn("<strong>&times;7</strong>", html)
        self.assertEqual(sum(1 for f in report["pages"][0]["findings"]
                             if f["rule_id"] == "bb-link-name"), 7)

    def test_a_long_list_is_cut_and_says_where_the_rest_is(self):
        links = "".join(f'<a href="/{i}"></a>' for i in range(130))
        report, html = report_of(*self._page(links))
        self.assertEqual(sum(1 for f in report["pages"][0]["findings"]
                             if f["rule_id"] == "bb-link-name"), 130)
        self.assertIn("30 more findings of this rule here, 30 of them "
                      "failures, are not shown; the JSON report lists every "
                      "one.", html)

    def _page(self, body: str) -> list:
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        (d / "p.html").write_text(PAGE.format(body))
        return [d / "p.html"]

    def test_vendor_findings_name_the_vendor(self):
        """P5-08: "FAIL (3rd-party)" did not say whose markup it was."""
        report, _html = report_of(FIXTURES / "bad.html")
        report = copy.deepcopy(report)
        f = report["pages"][0]["findings"][0]
        f.update(origin="third-party", owned=False,
                 origin_detail="https://widget.vendor.example")
        report["site"]["total_third_party_fail_findings"] = 1
        html = RH.render(report)
        self.assertIn("FAIL (3rd-party)", html)
        self.assertIn("In markup a vendor's script inserted "
                      "(https://widget.vendor.example)", html)
        self.assertIn("(from https://widget.vendor.example)", html)

    def test_the_html_and_json_agree(self):
        report, html = report_of(FIXTURES / "bad.html",
                                 FIXTURES / "subtle-bad.html")
        self.assertEqual(RH.render(report), html)
        import html as H
        for p in report["pages"]:
            for f in p["findings"]:
                self.assertIn(H.escape(f["message"]), html)

    def test_a_file_run_says_how_its_pages_were_read(self):
        _report, html = report_of(FIXTURES / "bad.html")
        self.assertIn("The pages were read from their files as they are: no "
                      "browser ran for them.", html)

    def test_the_report_passes_the_harness_on_the_markup(self):
        _report, html = report_of(FIXTURES / "bad.html",
                                  FIXTURES / "subtle-bad.html")
        page = run_page(html, "r.html", load_rulebook())
        self.assertEqual([(rr.rule_id, f.message) for rr in page.results
                          for f in rr.findings], [])

    def test_the_sample_page_is_clean_on_the_markup(self):
        """P5-08: fixtures/sample-output.html, a page as the pack has an
        agent write it, was used by nothing. It is a precision fixture."""
        page = run_page((FIXTURES / "sample-output.html").read_bytes(),
                        "sample-output.html", load_rulebook())
        self.assertEqual([(rr.rule_id, f.message) for rr in page.results
                          for f in rr.findings], [])


class _Serve:
    """Serve a folder on loopback for URL runs that need no browser."""

    def __init__(self, folder):
        import functools
        import http.server
        import threading

        class Quiet(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *a, **k):
                pass
        handler = functools.partial(Quiet, directory=str(folder))
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0),
                                                     handler)
        threading.Thread(target=self.httpd.serve_forever,
                         daemon=True).start()
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def no_proxy():
    """Loopback fetches go straight to the server."""
    return mock.patch.dict(os.environ, {k: "" for k in os.environ
                                        if k.lower().endswith("_proxy")})


class TestReviewOfR3(unittest.TestCase):
    """The two independent reviews of stage R3 (R3A, R3B)."""

    def site(self) -> tuple:
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        (d / "p.html").write_text(PAGE.format(
            '<img src="a.png"><a href="/x"></a>'), encoding="utf-8")
        (d / "dir").mkdir()
        (d / "dir" / "index.html").write_text(PAGE.format("<p>x</p>"),
                                              encoding="utf-8")
        server = _Serve(d)
        self.addCleanup(server.stop)
        return d, server

    def url_report(self, *argv) -> tuple:
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        with no_proxy():
            code, out, err = run(*argv, "--no-render", "--json", d / "r.json",
                                 "--html", d / "r.html", "--fail-on", "never")
        return (code, err, json.loads((d / "r.json").read_text()),
                (d / "r.html").read_text())

    def test_two_pages_under_one_recorded_url(self):
        """R3A-1: URLs that differ only in a redacted value."""
        _d, server = self.site()
        code, err, rep, html = self.url_report(
            "--url", f"{server.base}/p.html?id=1",
            "--url", f"{server.base}/p.html?id=2",
            "--url", f"{server.base}/missing.html?a=1",
            "--url", f"{server.base}/missing.html?a=2")
        self.assertEqual(code, 2)
        paths = [p["path"] for p in rep["pages"]]
        self.assertEqual(len(paths), 4)
        self.assertEqual(len(set(paths)), 2)
        prints = [f["fingerprint"] for p in rep["pages"]
                  for f in p["findings"]]
        self.assertEqual(len(prints), len(set(prints)))
        self.assertEqual(rep["errors"], 2)
        self.assertIn("(page 2 of 2 with this name)", html)
        self.assertIn("bb-img-alt", rep["rules"])
        self.assertEqual(rep["rules"]["bb-img-alt"]["pages_failed"], 2)
        self.assertIn("2 failures on 2 pages", html)
        self.assertIn("name more than one page of this run", err)

    def test_a_file_named_twice_is_one_page(self):
        """R3A-2."""
        report, _html = report_of(FIXTURES / "bad.html", FIXTURES / "bad.html")
        self.assertEqual(len(report["pages"]), 1)

    def test_pages_never_read_are_not_called_files(self):
        """R3A-5."""
        _d, server = self.site()
        _code, _err, rep, html = self.url_report(
            "--url", f"{server.base}/missing.html",
            "--url", f"{server.base}/p.html")
        self.assertEqual(rep["source"], "urls")
        self.assertNotIn("read from their files", html)
        self.assertNotIn("the file as it is", html)
        self.assertIn("not read: it could not be fetched", html)
        _code, _err, rep, html = self.url_report(
            "--url", f"{server.base}/missing.html",
            "--url", f"{server.base}/gone.html")
        self.assertIsNone(rep["fetch"])
        self.assertIn("The run could fetch none of its pages", html)
        static = next(x for x in rep["layers"] if x["layer"] == "static-dom")
        self.assertEqual(static["status"], "skipped")

    def test_a_redirect_is_counted_once(self):
        """R3A-8: `redirects` is the chain, the requested URL first."""
        _d, server = self.site()
        _code, _err, rep, html = self.url_report(
            "--url", f"{server.base}/dir?token=x")
        chain = rep["pages"][0]["fetch"]["redirects"]
        self.assertEqual(len(chain), 2)
        self.assertIn("<dt>Redirects</dt><dd>1 redirect</dd>", html)

    def test_the_cap_counts_what_it_hides(self):
        """R3A-6: the cap row counted one finding per page."""
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        imgs = "".join(f'<img src="s{n}.png">' for n in range(102))
        for name in ("a", "b"):
            (d / f"{name}.html").write_text(PAGE.format(
                imgs + '<img src="s101.png">' * 2), encoding="utf-8")
        report, html = report_of(d)
        self.assertIn("8 more findings of this rule here, 8 of them "
                      "failures, are not shown", html)

    def test_a_custom_rulebook_cannot_say_untrue_things(self):
        """R3A-9, R3A-10, R3B-7: the fields reports print beside a rule's
        findings, and their types."""
        from bellbriar_harness.engine import validate_rulebook
        for key, value in (("understanding",
                            "javascript:alert(1)//non-text-content.html"),
                           ("tier", "1"), ("sc", "2.4.4"), ("sc", [111]),
                           ("understanding", 5), ("name", ["x"]),
                           ("sc", ["1.4.6"]), ("engine", "axe-core"),
                           ("name", "Contrast"),
                           ("understanding", "https://www.w3.org/WAI/WCAG21/"
                            "Understanding/contrast-enhanced.html")):
            rb = copy.deepcopy(load_rulebook())
            for r in rb["rules"]:
                if r["id"] == "bb-img-alt":
                    r[key] = value
            with self.subTest(key=key, value=value):
                with self.assertRaises(RuntimeError):
                    validate_rulebook(rb)
        # Tiers and weights may still change.
        rb = copy.deepcopy(load_rulebook())
        for r in rb["rules"]:
            if r["id"] == "bb-img-alt":
                r["tier"] = 2
        validate_rulebook(rb)
        self.assertEqual(RH._understanding("javascript:alert(1)"), "")
        self.assertIn('href="https://www.w3.org/x.html"',
                      RH._understanding("https://www.w3.org/x.html"))

    def test_a_report_that_cannot_be_made_is_a_run_error(self):
        """R3A-10: a traceback and exit 1 — the gate's code — even with
        --fail-on never."""
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        with mock.patch.object(cli, "render", side_effect=TypeError("boom")):
            code, _out, err = run(FIXTURES / "bad.html", "--json",
                                  d / "r.json", "--html", d / "r.html",
                                  "--fail-on", "never")
        self.assertEqual(code, 2)
        self.assertIn("the html report could not be made", err)
        self.assertTrue((d / "r.json").exists())
        self.assertFalse((d / "r.html").exists())

    @unittest.skipUnless(os.name == "posix", "byte file names")
    def test_a_file_name_that_is_not_utf8(self):
        """R3A-11: no report at all, and a traceback."""
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        folder = os.path.join(os.fsencode(str(d)), b"names")
        os.mkdir(folder)
        try:
            with open(os.path.join(folder, b"caf\xe9.html"), "wb") as fh:
                fh.write(PAGE.format('<a href="/x"></a>').encode())
        except (OSError, ValueError):
            # APFS, macOS's, refuses the name (EILSEQ).
            self.skipTest("this file system refuses names that are not UTF-8")
        code, _out, err = run(os.fsdecode(folder), "--json", d / "r.json",
                              "--html", d / "r.html", "--fail-on", "never")
        self.assertEqual(code, 0, err)
        report = json.loads((d / "r.json").read_text())
        self.assertEqual(len(report["pages"]), 1)
        self.assertTrue((d / "r.html").exists())

    def test_an_unknown_origin_is_the_sites_own(self):
        """R3A-12: "owned is false only for third-party" — and an origin
        the harness does not know shrank the score."""
        self.assertTrue(Finding("r", FAIL, "minor", "m",
                                origin="partner").owned)
        self.assertFalse(Finding("r", FAIL, "minor", "m",
                                 origin="third-party").owned)

    def test_a_sitemap_run_says_how_many_it_took(self):
        """R3A-13."""
        listing = {"kind": "sitemap", "url": "https://e.x/s.xml",
                   "listed": 4, "complete": True, "max_pages": 3}
        text = RH._listing({"pages": 3, "list": listing})
        self.assertIn("3 pages from the sitemap", text)
        self.assertIn("which lists 4", text)
        listing.update(listed=4, complete=False)
        self.assertIn("4 or more", RH._listing({"pages": 3,
                                                "list": listing}))
        listing.update(listed=3, complete=True)
        self.assertIn("the 3 pages the sitemap",
                      RH._listing({"pages": 3, "list": listing}))

    def test_the_html_shows_the_reports_own_guidance(self):
        """R3B-15: "drawn from the JSON report", but the guidance came
        from the module."""
        report, _html = report_of(FIXTURES / "bad.html")
        report["rules"]["bb-img-alt"]["why"] = "WHY-FROM-THE-JSON."
        self.assertIn("WHY-FROM-THE-JSON.", RH.render(report))

    def test_what_a_review_rule_means(self):
        """R3B-15: a policy rule's findings are not failures of the
        criterion they cite."""
        self.assertNotIn("against WCAG", RH._meaning("policy", ["2.4.4"]))
        self.assertIn("stricter than", RH._meaning("policy", ["2.4.4"]))
        self.assertIn("does not require", RH._meaning("best-practice",
                                                      ["4.1.2"]))

    def test_the_guide_counts_the_tier1_rules_that_never_fail(self):
        """R3B-17: it said three; bb-aria-ref is the fourth."""
        never = [r for r in _runs() if r["tier"] == 1 and
                 r["verdict_basis"] in ("policy", "best-practice", "review")]
        words = {3: "Three", 4: "Four", 5: "Five"}
        guide = " ".join((ROOT / "docs" / "MEASUREMENT-AND-EVIDENCE-GUIDE.md")
                         .read_text(encoding="utf-8").split())
        self.assertIn(f"{words[len(never)]} never fail", guide)
        for r in never:
            self.assertIn(f"`{r['id']}`", guide)


class TestReviewOfR3Round2(unittest.TestCase):
    """The review of the fixes (R3C)."""

    @staticmethod
    def abouts(html: str, rule: str, **kw) -> list:
        page = run_page(html, "p.html", load_rulebook(), **kw)
        return [f.about for rr in page.results for f in rr.findings
                if rr.rule_id == rule]

    def test_a_captures_records_are_not_part_of_an_element(self):
        """R3C-1: records whose values hold quotes (axe-core's) stayed in,
        with the capture's secret, so every rendered run gave every finding
        a new fingerprint."""
        def about(secret):
            stamp = (f' {secret}="first-party" {secret}-axe=\''
                     '[{"r":"image-alt","i":"critical"}]\'' if secret else "")
            return self.abouts(PAGE.format(f'<img src="a.png"{stamp}>'),
                               "bb-img-alt", provenance_attr=secret,
                               reader="dom" if secret else None)
        one = about("data-bb-p-0123456789abcdef")
        self.assertEqual(len(one), 1)
        self.assertEqual(one, about("data-bb-p-fedcba9876543210"))
        self.assertEqual(one, about(None))

    def test_a_file_and_its_capture_agree(self):
        """R3C-2: a capture is read with html.parser, which lowercases
        names (viewBox), and a browser writes attributes in its own
        order."""
        html = PAGE.format(
            '<a HREF="/x?a=1&amp;b=2" class="  k1   k2  " data-x=\'say "hi"\'>'
            '<img src="i.png"></a><svg viewBox="0 0 10 10" role="img">'
            '<circle r="4"/></svg>')
        for rule in ("bb-link-name", "bb-img-alt", "bb-svg-name"):
            with self.subTest(rule=rule):
                file_run = self.abouts(html, rule)
                self.assertEqual(len(file_run), 1)
                self.assertEqual(file_run, self.abouts(html, rule,
                                                       reader="dom"))

    def test_elements_that_differ_are_told_apart(self):
        """R3C-7: three icon buttons that differ only in their icon, and
        two start tags that read alike when values are not escaped."""
        icons = "".join(f'<button class="btn icon"><svg aria-hidden="true">'
                        f'<path d="M{i} 0L{i} 9"></path></svg></button>'
                        for i in range(3))
        quoted = ('<button data-a=\'x" y="z\'></button>'
                  '<button data-a="x" y="z"></button>')
        for body, n in ((icons, 3), (quoted, 2)):
            with self.subTest(body=body[:40]):
                got = self.abouts(PAGE.format(body), "bb-button-name")
                self.assertEqual(len(got), n)
                self.assertEqual(len(set(got)), n)

    def test_a_render_run_says_how_many_pages_the_browser_took(self):
        """R3C-3: "each page captured in a browser" when none was."""
        report, _html = report_of(FIXTURES / "bad.html")
        report["source"] = "render"
        html = RH.render(report)
        self.assertNotIn("each page captured in a browser", html)
        self.assertIn("which captured no page", html)
        report["pages"] = report["pages"] * 2
        self.assertIn("which captured none of the 2 pages", RH.render(report))

    def test_a_run_that_read_no_page_says_so(self):
        """R3C-4: "covers the static DOM layer only" when no page could be
        read."""
        from bellbriar_harness.engine import NOTHING_READ_SENTENCE
        _d, server = TestReviewOfR3.site(self)
        _code, _err, rep, html = TestReviewOfR3.url_report(
            self, "--url", f"{server.base}/nope1.html",
            "--url", f"{server.base}/nope2.html")
        self.assertEqual(rep["coverage_note"], NOTHING_READ_SENTENCE)
        self.assertNotIn("static DOM layer only", html)

    @unittest.skipUnless(hasattr(os, "symlink"), "symbolic links")
    def test_a_link_to_a_file_is_a_page_of_its_own(self):
        """R3C-5: a symbolic link to a page dropped the page."""
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        (d / "sub").mkdir()
        (d / "sub" / "page.html").write_text(PAGE.format("<p>x</p>"),
                                             encoding="utf-8")
        try:
            os.symlink("page.html", d / "sub" / "alias.html")
        except OSError:
            self.skipTest("cannot make a symbolic link here")
        report, _html = report_of(d / "sub")
        self.assertEqual(sorted(Path(p["path"]).name
                                for p in report["pages"]),
                         ["alias.html", "page.html"])
        code, _out, err = run(d / "sub", d / "sub" / "page.html",
                              "--fail-on", "never")
        self.assertEqual(code, 0, err)
        self.assertIn("1 file(s) named more than once are evaluated once, "
                      "under the first name given (", err)
        self.assertIn("page.html).", err)
        self.assertIn("evaluated 2 file(s)", err)

    def test_tier_weights_are_checked(self):
        """R3C-6: a weight of "5" raised in scoring (exit 1, the gate's
        code), and -5 was taken."""
        from bellbriar_harness.engine import validate_rulebook
        good = {"0": 0, "1": 5, "2": 2, "3": 1}
        for weights in ({**good, "1": "5"}, {**good, "1": -5},
                        {**good, "1": True}, {**good, "1": 5.5},
                        {"1": 5, "2": 2, "3": 1}, [5, 2, 1], None):
            rb = copy.deepcopy(load_rulebook())
            if weights is None:
                del rb["tier_weights"]
            else:
                rb["tier_weights"] = weights
            with self.subTest(weights=weights):
                with self.assertRaisesRegex(RuntimeError, "tier_weights"):
                    validate_rulebook(rb)
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        rb = copy.deepcopy(load_rulebook())
        rb["tier_weights"]["1"] = "5"
        (d / "rb.json").write_text(json.dumps(rb), encoding="utf-8")
        code, _out, err = run(FIXTURES / "bad.html", "--rulebook",
                              d / "rb.json", "--fail-on", "never")
        self.assertEqual(code, 2, err)
        self.assertIn("tier_weights", err)

    def test_a_rulebook_may_leave_defaults_out(self):
        """R3C-8: a field left at its default was a difference, and the
        refusal did not say which field differed."""
        from bellbriar_harness.engine import validate_rulebook
        rb = copy.deepcopy(load_rulebook())
        for r in rb["rules"]:
            for key, default in (("pled_pattern", False),
                                 ("understanding", ""), ("sc", [])):
                if key in r and r[key] == default:
                    del r[key]
        validate_rulebook(rb)
        for r in rb["rules"]:
            if r["id"] == "bb-img-alt":
                r["sc"] = ["1.4.6"]
            if r["id"] == "bb-skip-link":
                r["pled_pattern"] = False
        with self.assertRaisesRegex(
                RuntimeError, r"bb-img-alt \(sc\).*bb-skip-link "
                r"\(pled_pattern\)|bb-skip-link \(pled_pattern\).*"
                r"bb-img-alt \(sc\)"):
            validate_rulebook(rb)

    def test_a_report_that_cannot_be_made_says_what_is_missing(self):
        """R3C-9: the bundle went unwritten without a word, and an earlier
        run's report stayed beside this run's."""
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        (d / "r.html").write_text("an earlier run's report",
                                  encoding="utf-8")
        with mock.patch.object(cli, "render", side_effect=TypeError("boom")):
            code, _out, err = run(FIXTURES / "bad.html", "--json",
                                  d / "r.json", "--html", d / "r.html",
                                  "--bundle", d / "b.json",
                                  "--fail-on", "never")
        self.assertEqual(code, 2)
        self.assertIn("the html report could not be made: whatever", err)
        self.assertIn("is not this run's html report", err)
        self.assertIn("no evidence bundle was written", err)
        self.assertFalse((d / "b.json").exists())
        self.assertTrue((d / "r.json").exists())

    def test_the_th_example_filters_the_cells_too(self):
        """R3C-11: only the header row was filtered."""
        g = GUIDANCE["bb-th-data-cells"]
        self.assertIn("shown.map((c) => <td", g["react"])
        self.assertIn('<td v-for="c in shown"', g["vue"])

    def test_a_sitemap_run_does_not_blame_the_cap_alone(self):
        """R3C-12: a page listed twice was put down to --max-pages."""
        listing = {"kind": "sitemap", "url": "https://e.x/s.xml",
                   "listed": 2, "complete": True, "max_pages": 50}
        text = RH._listing({"pages": 1, "list": listing})
        self.assertIn("1 page from the sitemap", text)
        self.assertIn("listed again with another fragment", text)


class TestReviewOfR3Round3(unittest.TestCase):
    """The review of the round-3 fixes (R3D)."""

    abouts = staticmethod(TestReviewOfR3Round2.abouts)

    def test_what_a_noscript_holds_is_left_out(self):
        """R3D-1: a page's parser reads it as text, a capture read back as
        elements; and a declarative root's mode keeps the page's case."""
        card = PAGE.format('<a href="/post/1" class="card">'
                           '<img src="p1-blur.jpg" alt="">'
                           '<noscript><img src="p1.jpg" alt=""></noscript></a>')
        self.assertEqual(self.abouts(card, "bb-link-name"),
                         self.abouts(card, "bb-link-name", reader="dom"))
        host = PAGE.format('<a href="/x"><span><template shadowrootmode='
                           '"{}"><slot></slot></template></span></a>')
        self.assertEqual(self.abouts(host.format("OPEN"), "bb-link-name"),
                         self.abouts(host.format("open"), "bb-link-name"))

    def test_tokens_that_change_on_every_request_are_left_out(self):
        """R3D-5: a CSRF token in a hidden input, a nonce."""
        page = PAGE.format(
            '<div class="drawer" aria-hidden="true"><form action="/cart" '
            'method="post"><input type="hidden" name="token" value="{0}">'
            '<script nonce="{0}"></script><button type="submit">Checkout'
            '</button></form></div>')
        one = self.abouts(page.format("AAAA"), "bb-aria-hidden-focus")
        self.assertEqual(len(one), 1)
        self.assertEqual(one, self.abouts(page.format("BBBB"),
                                          "bb-aria-hidden-focus"))
        # A visible field's value is the page's own.
        field = PAGE.format('<input value="{}">')
        self.assertNotEqual(self.abouts(field.format("a"), "bb-control-label"),
                            self.abouts(field.format("b"), "bb-control-label"))

    def test_text_nodes_are_joined_by_a_space(self):
        """R3D-6: as REPORT.md now says."""
        import hashlib

        def digest(value):
            return hashlib.sha256(json.dumps(
                value, ensure_ascii=True, separators=(",", ":")).encode(
                "ascii")).hexdigest()[:32]
        # Two adjacent copies, so bb-redundant-links reports the link.
        got = self.abouts(PAGE.format('<a href="/x">Ca<b>f\u00e9</b>'
                                      '<script>x()</script></a>' * 2),
                          "bb-redundant-links")
        self.assertIn('`<a>Ca<b>f\u00e9</b></a>`', REPORT_DOC)
        self.assertIn('reads `"Ca f\u00e9"`', REPORT_DOC)
        want = digest([["a", [["href", "/x"]]], "Ca f\u00e9",
                       [["b", []], ["script", []]]])
        self.assertIn(want, got)

    def test_a_build_keeps_its_port(self):
        """R3D-2: a share link built from location.href carried a new port
        into every run's fingerprints."""
        import socket
        from bellbriar_harness.serve import BuildServer, stable_port
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        (d / "dist").mkdir()
        (d / "dist" / "index.html").write_text(PAGE.format("<p>x</p>"),
                                               encoding="utf-8")
        port = stable_port(d / "dist")
        self.assertEqual(port, stable_port("/elsewhere/dist"))
        self.assertTrue(49152 <= port <= 65535)
        with BuildServer(d / "dist") as srv:
            self.assertTrue(srv.port_stable)
            self.assertIn(f":{port}/", srv.url_for(d / "dist" / "index.html"))
        # Another program on the port: the build is served elsewhere, and
        # the run can say so.
        holder = socket.socket()
        self.addCleanup(holder.close)
        try:
            holder.bind(("127.0.0.1", port))
            holder.listen(1)
        except OSError:
            self.skipTest("the port is in use here")
        with BuildServer(d / "dist") as srv:
            self.assertFalse(srv.port_stable)
            self.assertNotIn(f":{port}/", srv.url_for(d / "dist" /
                                                     "index.html"))

    @unittest.skipUnless(hasattr(os, "symlink"), "symbolic links")
    def test_a_link_is_served_at_its_own_path(self):
        """R3D-3: --render loaded a link from its target's address, so one
        URL was scored as two pages."""
        import urllib.request
        from bellbriar_harness.serve import BuildServer
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        (d / "site").mkdir()
        (d / "site" / "z.html").write_text(PAGE.format("<p>z</p>"),
                                           encoding="utf-8")
        try:
            os.symlink("z.html", d / "site" / "a-link.html")
        except OSError:
            self.skipTest("cannot make a symbolic link here")
        with BuildServer(d / "site") as srv, no_proxy():
            url = srv.url_for(d / "site" / "a-link.html", d / "site")
            self.assertTrue(url.endswith("/a-link.html"), url)
            with urllib.request.urlopen(url) as resp:
                self.assertIn(b"<p>z</p>", resp.read())

    def test_the_coverage_note_counts_pages_not_read(self):
        """R3D-4: "evaluated each page's DOM" beside a page never served,
        and "1 of its 2 pages" in a run of three."""
        from types import SimpleNamespace
        page = run_page(PAGE.format("<p>x</p>"), "a.html", load_rulebook())
        unread = cli._unread_page("b.html", "it is not inside a folder")
        note = cli._coverage_note([page, unread],
                                  [SimpleNamespace(mode="rendered"), None],
                                  build=True)
        self.assertNotIn("evaluated each page's DOM", note)
        self.assertIn("Of the run's 2 pages, 1 was captured after its "
                      "scripts ran and 1 could not be read", note)
        note = cli._coverage_note(
            [page, page, unread], [SimpleNamespace(mode="rendered"),
                                   SimpleNamespace(mode="server"), None],
            build=True)
        self.assertIn("1 was captured after its scripts ran, 1 was read as "
                      "files are and 1 could not be read", note)

    def test_a_report_that_cannot_be_written_says_what_is_missing(self):
        """R3D-7: the run stopped there, saying nothing of the other report
        or the bundle."""
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        (d / "r.json").write_text("{}", encoding="utf-8")
        real = cli._write

        def fail_json(path, data, *kind):
            return "no space left" if str(path).endswith(".json") and \
                "b.json" not in str(path) else real(path, data, *kind)
        with mock.patch.object(cli, "_write", side_effect=fail_json):
            code, _out, err = run(FIXTURES / "bad.html", "--json",
                                  d / "r.json", "--html", d / "r.html",
                                  "--bundle", d / "b.json",
                                  "--fail-on", "never")
        self.assertEqual(code, 2)
        self.assertIn("cannot write", err)
        self.assertIn("is not this run's json report", err)
        self.assertIn("no evidence bundle was written", err)
        self.assertTrue((d / "r.html").exists())
        self.assertFalse((d / "b.json").exists())

    @unittest.skipUnless(hasattr(os, "symlink"), "symbolic links")
    def test_a_linked_folder_is_named_not_followed(self):
        """R3D-8: skipped without a word."""
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        (d / "site").mkdir()
        (d / "outside").mkdir()
        (d / "site" / "a.html").write_text(PAGE.format("<p>a</p>"),
                                           encoding="utf-8")
        (d / "outside" / "o.html").write_text(PAGE.format("<p>o</p>"),
                                              encoding="utf-8")
        try:
            os.symlink(d / "outside", d / "site" / "linkdir")
        except OSError:
            self.skipTest("cannot make a symbolic link here")
        code, _out, err = run(d / "site", "--fail-on", "never")
        self.assertEqual(code, 0, err)
        self.assertIn("1 linked folder(s) were not followed", err)
        self.assertIn("linkdir", err)

    def test_a_missing_path_says_so(self):
        """P1-14: it printed only `[bellbriar] error: ./nope`."""
        code, _out, err = run("./no-such-folder-here")
        self.assertEqual(code, 2)
        self.assertIn("error: path not found: ./no-such-folder-here", err)

    def test_a_rulebook_s_shape_is_checked(self):
        """R3D-9: a rule listed twice let the last entry decide; a rule
        that is not an object raised; 5.0 read as a Python value."""
        from bellbriar_harness.engine import validate_rulebook
        rb = copy.deepcopy(load_rulebook())
        twin = copy.deepcopy(next(r for r in rb["rules"]
                                  if r["id"] == "bb-img-alt"))
        twin["tier"] = 3
        rb["rules"].append(twin)
        with self.assertRaisesRegex(RuntimeError, "listed again: bb-img-alt"):
            validate_rulebook(rb)
        rb = copy.deepcopy(load_rulebook())
        rb["rules"].append("bb-x")
        with self.assertRaisesRegex(RuntimeError, "a list of objects"):
            validate_rulebook(rb)
        rb = copy.deepcopy(load_rulebook())
        rb["tier_weights"]["1"] = 5.0
        with self.assertRaisesRegex(RuntimeError,
                                    r'without a decimal point.*"1": 5\.0'):
            validate_rulebook(rb)


@unittest.skipUnless(HAVE_BROWSER, _WHY)
class TestHtmlInTheBrowser(unittest.TestCase):

    def test_the_report_passes_the_harness_in_a_browser(self):
        """The report is a deliverable: it must pass every rule the harness
        runs, contrast and reflow included, and with --strict; a page with
        a long name, which once made it scroll sideways (R3A-7), too."""
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        long = d / ("catalog-electronics-televisions-samsung-QN65S95DAFXZA-"
                    "with-a-name-long-enough-to-reach-past-the-edge-of-a-"
                    "phone-screen.html")
        shutil.copy(FIXTURES / "bad.html", long)
        _report, html = report_of(long, FIXTURES / "subtle-bad.html",
                                  "--render")
        (d / "report.html").write_text(html, encoding="utf-8")
        report, _ = report_of(d / "report.html", "--render", "--strict")
        page = report["pages"][0]
        self.assertEqual(page["fetch"]["mode"], "rendered")
        self.assertEqual([(f["rule_id"], f["message"][:80])
                          for f in page["findings"]], [])
        self.assertTrue(page["score"]["tier1_clean"])

    def test_the_sample_page_fails_nothing_in_a_browser(self):
        # Its map is a frame from another site: served from here instead,
        # so the test makes no request off this machine.
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        html = (FIXTURES / "sample-output.html").read_text(encoding="utf-8")
        self.assertIn("https://maps.example.com/", html)
        (d / "sample-output.html").write_text(html.replace(
            "https://maps.example.com/embed?q=corner-bakery", "/map.html"),
            encoding="utf-8")
        (d / "map.html").write_text(PAGE.format("<p>Map</p>"),
                                    encoding="utf-8")
        report, _ = report_of(d / "sample-output.html", "--render")
        page = report["pages"][0]
        self.assertEqual(page["fetch"]["mode"], "rendered")
        self.assertEqual([f for f in page["findings"]
                          if f["verdict"] == "fail"], [])


@unittest.skipUnless(HAVE_BROWSER, _WHY)
class TestRenderRunsOfRound3(unittest.TestCase):
    """R3D-2 and R3D-3 in a browser."""

    def test_a_page_that_writes_its_address_keeps_its_fingerprints(self):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        (d / "share").mkdir()
        (d / "share" / "post.html").write_text(PAGE.format(
            '<div id="s"></div><script>document.getElementById("s")'
            '.innerHTML = \'<a href="\' + location.href + \'#copy"><svg '
            'aria-hidden="true"></svg></a>\';</script>'), encoding="utf-8")
        prints = []
        for _ in range(2):
            report, _html = report_of(d / "share", "--render")
            self.assertEqual(report["pages"][0]["fetch"]["mode"], "rendered")
            prints.append([f["fingerprint"] for f in
                           report["pages"][0]["findings"]
                           if f["rule_id"] == "bb-link-name"])
        self.assertEqual(len(prints[0]), 1)
        self.assertEqual(prints[0], prints[1])

    @unittest.skipUnless(hasattr(os, "symlink"), "symbolic links")
    def test_a_link_and_its_page_are_two_addresses(self):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        (d / "site").mkdir()
        (d / "site" / "z.html").write_text(PAGE.format("<p>z</p>"),
                                           encoding="utf-8")
        try:
            os.symlink("z.html", d / "site" / "a-link.html")
        except OSError:
            self.skipTest("cannot make a symbolic link here")
        report, _html = report_of(d / "site", "--render")
        urls = sorted(p["fetch"]["requested_url"].rsplit("/", 1)[-1]
                      for p in report["pages"])
        self.assertEqual(urls, ["a-link.html", "z.html"])


if __name__ == "__main__":
    unittest.main()
