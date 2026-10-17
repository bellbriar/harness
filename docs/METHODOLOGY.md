# Scoring methodology

Published so the benchmark is auditable. Honest denominators, defined before
any number is quoted.

## Verdicts
- **fail** — WCAG is violated, or probably is: the executed rule's failure
  condition is met, decided deterministically. Each rule's `verdict_basis`
  in `rulebook.json` says which: `sc` (a success-criterion failure W3C
  names, by a failure technique or an approved ACT rule) or `heuristic`
  (a probable failure that markup alone cannot settle, or one W3C does
  not itself name). Only `sc` fails are success-criterion violations.
- **needs_review** — requires human or higher-layer judgment; surfaced,
  never counted as failure. Rules whose basis is `policy` (stricter than
  the rulebook's WCAG 2.1 AA target: a pled pattern, or a WCAG 2.2
  criterion) or `best-practice` (WCAG does not require it on its own:
  W3C's ACT rules do not make it a conformance requirement, or W3C names
  no failure for it) report only this verdict, marked "pled in complaints", "a
  best practice" or "a WCAG 2.2 criterion"; none is a WCAG 2.1 failure on
  its own (rulebook 0.3.0 and later). The rules axe-core runs in the
  browser (rulebook 0.4.0 and later) are held to their bases the same way, and what
  axe-core could not decide is a minor review. An `sc` or `heuristic` rule can report a
  pled pattern for review, marked "pled in complaints", where markup
  cannot settle it (a field named only by its placeholder, which fails
  3.3.2 unless other visible text labels it; a missing skip link where a
  main landmark stands in). Rules whose basis is `review` only ask for
  review.
- A rule **passes** on a page when applicable with zero fail findings in
  the site's own markup. Markup attributed to a vendor's script counts
  toward whether a rule applies, and its failures do not count: a rule
  that fails only there passes. A finding about the page as a whole (no
  way past its repeated blocks, bb-skip-link) is the site's, and scored,
  whoever's markup the blocks are.
- **applicable=false** rules leave the denominator (a page with no tables is
  not credited for "table headers pass"). A rendered rule on a page no
  browser captured (a file run) has no result at all: it was not
  evaluated, which the layer coverage says, and it neither passes nor
  counts among the Tier-1 rules executed. A page with no applicable rules
  has no pass rate (`null`), not 100%. Neither does a page the static
  rules cannot evaluate at all — a client-rendered app shell, whose
  content JavaScript builds — which is reported as not evaluated and is
  never Tier-1 clean (a real Tier-1 fail on it still counts).

## Weights and tiers
Tier 1 = complaint-boilerplate rules (×5) · Tier 2 = regularly pled or
settlement-cited (×2) · Tier 3 = rarely filed, still graded (×1) ·
Tier 0 = policy rules (settlement terms, and duties that remain for
content outside evaluation, such as document files; ×0, reported only). A rule that never fails — basis `policy`, `best-practice`
or `review` — also weighs ×0, whatever its tier: an applicable rule that
cannot fail would be a free pass in the rate. Weights are provisional
until the complaint-tagging corpus lands; they ship in `rulebook.json` and
version with it.

## Reported numbers
1. **Weighted pass rate** = Σ w(passed) / Σ w(applicable), pooled across
   pages — *executed layers only*, and labeled as such.
2. **% pages Tier-1 clean** — the page bar, always reported with the
   number of Tier-1 rules that executed out of the number that exist
   (`tier1_rules_executed` / `tier1_rules_total`) and how many of those
   never fail (`tier1_rules_review_only`), because "clean" is a statement
   about the rules that ran and could fail, and nothing else. Each page's
   score carries its own `tier1_rules_executed`: the rules that ran on
   that page, which in a mixed run (some pages rendered, some not) is
   fewer on some pages than the run's; and `tier1_rules_applicable`: the
   ones among them that can fail and applied to the page, which "clean"
   rests on. A page where that is zero — no Tier-1 rule ran, or only ones
   that never fail, or none of those that can fail applied — is not
   Tier-1 clean but undecided, as a pass rate with nothing applicable is
   undefined; and a run where no page is decided cannot pass a gate that
   counts Tier-1 failures: it exits 2. (A custom rulebook that demotes
   every Tier-1 rule used to report "T1 clean [0/0]", and one that keeps
   only rules that never fail, "T1 clean [3/3]".)
3. (When browser layers land) **% critical flows completable** — conjunctive
   per WCAG's complete-process conformance requirement.

Findings in markup a known vendor's script injected are counted apart:
`third_party_fail_findings` (never scored) and
`third_party_needs_review_findings`; `fail_findings` and
`needs_review_findings` are the site's own. A rule that raised on a page
is errored there: it is not applicable for the rates, it counts as
executed only if it ran to the end on some other page, a page where a
Tier-1 rule errored is not Tier-1 clean (undecided), and the run is
reported incomplete and exits 2 without an evidence bundle. So is a page
the harness could not read: one that builds more elements, or nests them
deeper, than its budgets, and XHTML that is not well-formed or not a page
(the browser shows an error or the XML itself).

## Which rules, exactly
A report and a bundle name the rulebook by version and by SHA-256 of its
canonical form (`rulebook_sha256`). A report says whether it is the
rulebook the harness ships; for a bundle, `bellbriar-evidence verify`
compares the digest with the rulebook its own harness ships, and says
what the bundle records (a key's holder can record any digest). Two numbers are comparable only when the rulebook
digest, the harness version and the recorded library versions (`tool`)
match: a custom rulebook can keep a version and change tiers and weights,
and the parser's version decides what markup the rules see.

## What a green run means
That the executed layers found nothing. It does not mean the page is
accessible, conformant, or lawsuit-proof: unexecuted layers cover keyboard
operability, focus, announcements, and adequacy — and, in a file run,
contrast and reflow — i.e., much of the operational half of the pled
boilerplate. Every report embeds its layer
coverage; stripping that banner voids the report's meaning.

## Benchmark discipline
Bare-agent vs with-pack numbers are produced on a frozen, versioned,
held-out prompt corpus and are **deterministic only**, so anyone with the
open harness reproduces the headline; packs are never tuned on held-out
prompts. Judged numbers are not published until a calibration study
exists (public development set, private held-out test set, at least two
raters, pinned reference configuration); when they are, they appear
beside the headline with their agreement figure and confidence interval,
never inside it. No benchmark has been published yet.
