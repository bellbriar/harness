# Bypass-blocks corpus (`bb-skip-link`, WCAG 2.4.1)

Real-world page shapes for the bypass-blocks rule, each with the verdict it
should get. `tests/test_bypass_corpus.py` runs them.

## What is here

- **`representative/`** — 44 pages, none captured from a live site; every
  file says so in its first comment.
  - 36 were written from knowledge of each template family (Genesis,
    Shopify Dawn, Wix, Drupal Olivero, USWDS, Next.js) and of shapes real
    sites ship.
  - 8 copy the structure of pages the user saved on 2026-10-06 (WordPress
    Twenty Twenty-One and Twenty Twenty-Five, Astra, Docusaurus, GOV.UK,
    Squarespace 7.1, a Webflow template, nextjs.org): the landmarks, skip
    link, navigation and their order, with the text and links replaced.
    The saved pages themselves are development material and are not
    committed. `expected.json` names what each one is modeled on.
  - A few leave out markup that would trip another rule (noted inline), so
    their exit codes come from `bb-skip-link` alone.
- **`expected.json`** — for each file: the family, the expected
  `bb-skip-link` verdict (`pass`, `n/a`, `review` or `fail`), the exit codes
  for `--fail-on tier1` and for `--fail-on tier1 --strict`, and why in WCAG
  terms. `part_k` records the verdict Part K's rule gave where it was wrong
  (12 files).

## How the verdicts were set

From WCAG 2.4.1 and the user's FAIL definition, not from the rule's output:
FAIL only when the markup identifies repeated blocks and nothing bypasses
them (no working skip link, no main landmark or only one that wraps the
navigation, no heading that opens the content, no in-page navigation on a
one-page site), or the only mechanism is a skip link that does not work;
anything less is a moderate review marked "pled in complaints; not a WCAG
failure on its own". Two files differ from a WCAG-only reading, and say so:
a page whose markup marks no repeated block is a review, not n/a, because
the harness cannot tell a block from content.
