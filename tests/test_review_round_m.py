"""The independent review of Part L's round-3 fixes (Part M, item 1).

bb-skip-link shapes from this review are in test_bypass_blocks.py (a
heading above the page header, text written straight into <body>, G124
with a link home or to the top, a hash-route menu). This module holds the
rest:

  * Inline `display` with two or three keywords was accepted whenever each
    word was a display keyword, so `display:none; display:inline block`
    (which Chromium drops) read as shown. Chromium 141 accepts an outer and
    an inner keyword, or list-item with at most one outer keyword and one
    of flow/flow-root, and nothing else.
  * bellbriar-lint read `src={null}`, `src={undefined}` and Vue
    `:src="''"` as a source, and raised an ERROR where the gate reviews.
  * The home-path scrubber rewrote the path of a URL whose host ends in
    "]" (an IPv6 literal): `http://[::1]/home/a/b` became `http://[::1]~/b`.
"""
import itertools
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bellbriar_harness import engine as E, fetch as F            # noqa: E402
from bellbriar_harness.checks_static import _valid_style_value   # noqa: E402
from bellbriar_harness.lint import ERROR, WARN, lint_text        # noqa: E402
from bellbriar_harness.redact import redact_local_paths, redact_text  # noqa: E402

#: Every multi-keyword display value Chromium 141 accepts, among all two-
#: and three-word orderings of WORDS (recorded from Chromium 141.0.7390.37).
WORDS = ("block", "inline", "run-in", "flow", "flow-root", "table", "flex",
         "grid", "ruby", "math", "list-item", "contents", "none")
CHROMIUM_ACCEPTS = {
    "block flow", "block flow-root", "block table", "block flex",
    "block grid", "block ruby", "block math", "block list-item",
    "inline flow", "inline flow-root", "inline table", "inline flex",
    "inline grid", "inline ruby", "inline math", "inline list-item",
    "flow block", "flow inline", "flow list-item", "flow-root block",
    "flow-root inline", "flow-root list-item", "table block",
    "table inline", "flex block", "flex inline", "grid block",
    "grid inline", "ruby block", "ruby inline", "math block",
    "math inline", "list-item block", "list-item inline", "list-item flow",
    "list-item flow-root",
    "block flow list-item", "block flow-root list-item",
    "block list-item flow", "block list-item flow-root",
    "inline flow list-item", "inline flow-root list-item",
    "inline list-item flow", "inline list-item flow-root",
    "flow block list-item", "flow inline list-item", "flow list-item block",
    "flow list-item inline", "flow-root block list-item",
    "flow-root inline list-item", "flow-root list-item block",
    "flow-root list-item inline", "list-item block flow",
    "list-item block flow-root", "list-item inline flow",
    "list-item inline flow-root", "list-item flow block",
    "list-item flow inline", "list-item flow-root block",
    "list-item flow-root inline",
}


def multi_values() -> list[str]:
    return [" ".join(c) for n in (2, 3)
            for c in itertools.permutations(WORDS, n)]


def page(body: str) -> str:
    return ('<!doctype html><html lang="en"><head><title>T</title></head>'
            f'<body><main><h1>T</h1>{body}</main></body></html>')


def fails(html: str, rule: str) -> bool:
    p = E.run_page(html, "x.html", E.load_rulebook())
    return any(f.verdict == "fail" for rr in p.results if rr.rule_id == rule
               for f in rr.findings)


class TestDisplayKeywords(unittest.TestCase):
    def test_multi_keyword_values_match_the_recorded_chromium_table(self):
        wrong = [v for v in multi_values()
                 if _valid_style_value("display", v) != (v in CHROMIUM_ACCEPTS)]
        self.assertEqual(wrong, [])

    def test_a_dropped_value_leaves_display_none_standing(self):
        for value in ("inline block", "flex grid", "table list-item",
                      "block run-in"):
            with self.subTest(value=value):
                self.assertFalse(fails(page(
                    f'<div style="display:none; display:{value}"><img '
                    'src="a.png"></div>'), "bb-img-alt"))
        self.assertTrue(fails(page(
            '<div style="display:none; display:inline flow-root"><img '
            'src="a.png"></div>'), "bb-img-alt"))

    @unittest.skipUnless(F.playwright_available()[0], "needs Chromium")
    def test_the_table_still_matches_the_browser(self):
        from playwright.sync_api import sync_playwright
        values = multi_values()
        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                shown = browser.new_page().evaluate(
                    "(vals) => vals.map(v => { const d = document."
                    "createElement('div'); d.style.cssText = 'display:none;"
                    " display:' + v; return d.style.display !== 'none'; })",
                    values)
            finally:
                browser.close()
        self.assertEqual({v for v, s in zip(values, shown) if s},
                         CHROMIUM_ACCEPTS)


class TestLintMediaSource(unittest.TestCase):
    def severity(self, src: str, path: str) -> str:
        found = [f.severity for f in lint_text(src, path)
                 if f.rule_id == "bl-autoplay-media"]
        return found[0] if found else ""

    def test_an_expression_that_gives_no_url_is_no_source(self):
        for src, path in (
                ('<video autoPlay src={null} />', "A.jsx"),
                ('<video autoPlay src={undefined} />', "A.jsx"),
                ("<video autoPlay src={''} />", "A.jsx"),
                ('<template><audio autoplay :src="\'\'"></audio></template>', "C.vue"),
                ('<template><audio autoplay :src="null"></audio></template>', "C.vue"),
                ('<template><audio autoplay v-bind:src="undefined"></audio></template>',
                 "C.vue"),
                ('<audio autoplay [src]="\'\'"></audio>', "c.component.html")):
            with self.subTest(src=src):
                self.assertEqual(self.severity(src, path), WARN)

    def test_a_url_expression_is_still_a_source(self):
        for src, path in (
                ('<video autoPlay src={url} />', "A.jsx"),
                ('<video autoPlay src={"a.mp4"} />', "A.jsx"),
                ('<template><audio autoplay :src="url"></audio></template>', "C.vue"),
                # A property binding writes null as the URL "null".
                ('<audio autoplay [src]="null"></audio>', "c.component.html"),
                ('<audio autoplay src="null"></audio>', "x.html")):
            with self.subTest(src=src):
                self.assertEqual(self.severity(src, path), ERROR)


class TestRedactionLeavesUrls(unittest.TestCase):
    def test_a_site_path_inside_a_url_is_kept(self):
        for text in ("net::ERR_FAILED at http://[::1]/home/a/b",
                     "at https://[2001:db8::1]:8443/Users/x/y"):
            with self.subTest(text=text):
                self.assertEqual(redact_local_paths(text), text)
                self.assertEqual(redact_text(text), text)

    def test_local_paths_and_file_urls_are_still_scrubbed(self):
        for text, want in (
                ("at /home/jdoe-m/.cache/x", "at ~/.cache/x"),
                ("file:///home/jdoe-m/site/index.html", "file://~/site/index.html"),
                ("http://[::1]/p failed; see /home/jdoe-m/log",
                 "http://[::1]/p failed; see ~/log")):
            with self.subTest(text=text):
                self.assertEqual(redact_local_paths(text), want)


if __name__ == "__main__":
    unittest.main(verbosity=2)
