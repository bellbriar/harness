# Changelog

What each release changes, newest first. The release workflow refuses a
version tag whose version has no section here, or whose section still
says it is unreleased: the release commit replaces "unreleased" with the
day it is published (UTC).

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
record (`tool`): where a library's later versions change what matches,
the range the package asks pip for leaves them out, and a run with a
version outside the declared ranges says so before it starts.

Not stable: the console output (it is for people: parse the JSON), the
HTML report's layout, and the wording of messages.

## 1.0.1 — unreleased

Two verdict corrections to one rule, otherwise wording and
documentation: no option, exit status or format changes. Because
`bb-redundant-links` finds differently, the rulebook version becomes
1.0.1 in the release commit (with `docs/RULES.md` and the signed example
bundle regenerated, as the version bump requires), so a report says
which rule semantics made it.

- `bb-redundant-links` no longer reviews adjacent links whose shared
  `href` is a placeholder: `#!` and `#/` join `#`. A template footer of
  `#!` links (every Start Bootstrap theme) reviewed as "adjacent links to
  the same destination" on every pair, at moderate impact, which
  `--strict` gated; the links go nowhere yet, which is a different
  problem and not this rule's. A site that passed the strict gate before
  still passes; one that failed only on this can now pass.
- `bb-redundant-links` reports the moderate (strict-gated) impact only
  for the H2 shape — an image link and a title link in one card. It
  judged the shape by the two links' nearest common ancestor alone, so a
  footer's logo link followed by its `<nav>`'s Home link (common ancestor
  a `<div>`, the `<nav>` never seen) and two mentions of an email address
  forty lines apart in a notice wrapped in a `<div>` were both strict-
  gated. Two of three sites built from scratch for the build-mode
  benchmark failed `--strict` on nothing else. The impact is now minor
  when either link has a landmark (`header`, `nav`, `main`, `footer`,
  `aside`, `section`, `form`, or a landmark role) below the common
  ancestor, or when a heading or more than 120 characters of text lies
  between the two links. The pairs are still reported.
- `bellbriar-lint`: `bl-tabindex-noninteractive` no longer warns on a
  `<div tabindex="0">` that carries both a `role` and an accessible name
  (`aria-label` or `aria-labelledby`): a scrolling table wrapper built as
  the rule's own message asks for was reported as "roleless and
  nameless".

- CHANGELOG: the 1.0.0 section's "Since 1.0.0rc1" paragraph was false
  (the macOS runner fix was already in rc1) and is corrected above; the
  v1.0.0 GitHub release notes were corrected by hand on 2026-10-18.
- `bellbriar-lint`: three findings cited the wrong section of Bellbriar's
  WCAG pack in their `ref`: `bl-marquee-blink` (WGT-5 → VIS-8),
  `bl-autofocus` and `bl-dangerous-html` (SPA-6 → SPA-5). The ids and
  messages are unchanged.
- README and the Action's README: the sysctl line that lets Chromium's
  sandbox start applies to Ubuntu 26.04 as well as 24.04 (GitHub moves
  `ubuntu-latest` to 26.04 between 2026-10-19 and 2026-11-19); README
  says that Playwright's Chromium needs macOS 14 or later, and what runs
  without it.

## 1.0.0 — 2026-10-17

The first release. It needs Python 3.11 or later. It runs on Linux and
macOS: on Windows the three commands stop and say so, and WSL (the
Windows Subsystem for Linux) or the container image runs it.

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

Since 1.0.0rc1, the code is unchanged but for its version number: README
and the Action's README now say that this project's CI shows Chromium's
sandbox starting under the seccomp profile on x86-64 and ARM64, and the
worked example is re-signed with 1.0.0. (This paragraph was corrected in
1.0.1: the 1.0.0 release notes and sdist carry the earlier wording, which
wrongly placed the macOS runner fix after rc1; rc1 already held it.)

## 1.0.0rc1 — 2026-10-17

A release candidate for 1.0.0, published to rehearse the release:
CHANGELOG.md's 1.0.0 section lists what it holds. To install it, ask pip
for it (`pip install --pre bellbriar-harness`, or
`bellbriar-harness==1.0.0rc1`). With it, `bellbriar-evidence/1` and
`bellbriar-signature/1` are published: any change to them now takes a
new format string (`docs/CANONICALIZATION.md` §1).
