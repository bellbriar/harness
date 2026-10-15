# Changelog

What each release changes, newest first. The release workflow refuses a
version tag whose version has no section here, or whose section still
says it is unreleased: the release commit replaces "unreleased" with the
day it is published.

## Versions

The harness follows [Semantic Versioning](https://semver.org/). Within
1.x, no release removes or changes these; that takes 2.0.0:

- the command-line options of `bellbriar-eval`, `bellbriar-lint` and
  `bellbriar-evidence`, and what each does;
- their exit statuses, as README.md, `docs/EVIDENCE.md` and
  `action/README.md` give them: 0, 1 when a gate fails (`--fail-on`) or
  `verify` finds a bundle INVALID, 2 when a run or a check cannot be
  completed;
- the formats `bellbriar-report/1` and `bellbriar-lint/1`
  (`docs/REPORT.md`, "What stays stable"), and `bellbriar-evidence/1` and
  `bellbriar-signature/1` (`docs/CANONICALIZATION.md`): a 1.x release
  writes them as their documents give them, adding only a field, or a
  value to a list, where its document allows one. Any other change takes a
  new format string, which only 2.0.0 may bring, and `verify` keeps
  accepting the published formats it knows. (`bellbriar-pack/1` is a
  draft, outside this promise: CANONICALIZATION §1.)

A minor release (1.1.0) may add options, fields, rules and values a list
marks open; a patch release (1.0.1) fixes what a release does wrongly.

What a rule finds can change in any release, as a rule is corrected or
made to read a page as a browser does. The rulebook has a version of its
own (`rulebook_version`), which every report and bundle records beside
the rulebook's SHA-256: a release that changes what any rule finds, a
rule's tier or weight, or which rules run, changes it, and its section
here says what changed. A verdict is reproduced with the harness and
rulebook versions that made it, and the libraries its report and bundle
record (`tool`): where a library's new version changes what matches, the
package asks pip for the range it was tested with.

Not stable: the console output (it is for people: parse the JSON), the
HTML report's layout, and the wording of messages.

## 1.0.0 — unreleased

The first release. It needs Python 3.11 or later.

- `bellbriar-eval` evaluates built pages (a folder of files, served on
  this machine for a browser with `--render`) or live ones (`--url`,
  `--urls`, `--sitemap`) against WCAG 2.1 AA, weighted toward what
  plaintiff firms plead (provisional tiers): 32 rules on the markup in
  every run, and in a browser reflow at 320 CSS pixels and contrast,
  target size and 27 more WCAG A/AA rules, which axe-core 4.12.1 (pinned)
  decides. It gates CI (`--fail-on`, against a baseline with
  `--baseline`), and writes a report for people (`--html`) and one for
  scripts (`--json`, `bellbriar-report/1`).
- `bellbriar-lint` reads a site's source (JSX, TSX, Vue, HTML, CSS)
  before it is built: text, `bellbriar-lint/1` JSON or SARIF 2.1.0.
- `bellbriar-evidence` makes keys and verifies and shows evidence bundles
  offline. A run can be kept as a `bellbriar-evidence/1` bundle and
  signed with a key of your own: every signature 1.0 makes is
  self-signed, which shows who held the key, not that the results are
  correct.
- A GitHub Action (`bellbriar/eval-action@v1`) and a container image
  (`ghcr.io/bellbriar/harness:1`).

What 1.0 leaves out, and where it reads a page otherwise than a browser
or another tool does, is listed in `docs/ROADMAP.md` ("Not in 1.0"):
among it the keyboard and focus checks, remote signing, rule packs and
the judge.

## 1.0.0rc1 — 2026-10-15

A release candidate for 1.0.0, published to rehearse the release:
CHANGELOG.md's 1.0.0 section lists what it holds. To install it, ask pip
for it (`pip install --pre bellbriar-harness`, or
`bellbriar-harness==1.0.0rc1`). With it, `bellbriar-evidence/1` and
`bellbriar-signature/1` are published: any change to them now takes a
new format string (`docs/CANONICALIZATION.md` §1).
