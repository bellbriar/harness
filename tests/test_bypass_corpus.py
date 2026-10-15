"""The bypass-blocks corpus (fixtures/bypass): real-world template shapes
with the bb-skip-link verdict each should get, written from WCAG 2.4.1 and
the FAIL definition rather than from the rule's output (see the corpus
README). Every page also pins the gate: `--fail-on tier1` and
`--fail-on tier1 --strict` exit codes. No page captured from a live site
is committed; eight copy the structure of saved pages, without their text.
"""
import contextlib
import io
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bellbriar_harness import cli, engine as E                  # noqa: E402
from bellbriar_harness.model import FAIL, MODERATE, SERIOUS     # noqa: E402

CORPUS = ROOT / "fixtures" / "bypass"
EXPECTED = json.loads((CORPUS / "expected.json").read_text(encoding="utf-8"))
PLED = "pled in complaints; not a WCAG failure on its own"


def verdict(path: Path) -> str:
    page = E.run_page(path.read_text(encoding="utf-8"), str(path),
                      E.load_rulebook())
    rr = next(r for r in page.results if r.rule_id == "bb-skip-link")
    if not rr.applicable:
        return "n/a"
    if not rr.findings:
        return "pass"
    (f,) = rr.findings
    if f.verdict == FAIL:
        assert f.impact == SERIOUS, f
        return "fail"
    assert f.impact == MODERATE and PLED in f.message, f
    return "review"


def gate(path: Path, *argv: str) -> int:
    with contextlib.redirect_stdout(io.StringIO()), \
            contextlib.redirect_stderr(io.StringIO()):
        return cli.main([str(path), "--fail-on", "tier1", *argv])


class TestBypassCorpus(unittest.TestCase):
    def test_every_file_is_listed_and_labelled(self):
        on_disk = {str(p.relative_to(CORPUS)) for p in CORPUS.rglob("*.html")}
        self.assertEqual(on_disk, set(EXPECTED))
        for name, e in EXPECTED.items():
            with self.subTest(file=name):
                self.assertTrue(name.startswith("representative/"))
                self.assertIn(e["bb_skip_link"], ("pass", "n/a", "review", "fail"))
                self.assertTrue(e["why"])
                self.assertEqual(e["source"], "representative, not captured")
                text = (CORPUS / name).read_text(encoding="utf-8")
                self.assertIn("representative, not captured", text[:400])

    def test_verdicts(self):
        for name, e in EXPECTED.items():
            with self.subTest(file=name):
                got, want = verdict(CORPUS / name), e["bb_skip_link"]
                if {got, want} <= {"pass", "n/a"}:
                    continue            # both: no finding, nothing to fix
                self.assertEqual(got, want, e["why"])

    def test_the_gate(self):
        for name, e in EXPECTED.items():
            with self.subTest(file=name):
                path = CORPUS / name
                self.assertEqual(gate(path), e["exit_tier1"])
                self.assertEqual(gate(path, "--strict"), e["exit_strict"])

    def test_the_corpus_covers_what_the_queue_asked_for(self):
        families = " ".join(e["family"] for e in EXPECTED.values()).lower()
        for family in ("wordpress block", "wordpress classic", "genesis",
                       "astra", "shopify dawn", "squarespace", "wix",
                       "webflow", "drupal", "next.js", "docusaurus",
                       "gov.uk", "uswds"):
            with self.subTest(family=family):
                self.assertIn(family, families)


if __name__ == "__main__":
    unittest.main()
