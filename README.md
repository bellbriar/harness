# Bellbriar Eval Harness

Open accessibility evaluation for **agent-generated web output**. WCAG 2.1 AA
baseline — the standard adopted by DOJ's ADA Title II rule and HHS's
Section 504 rule, and the one pled in court — weighted toward what
plaintiff firms plead (provisional tiers: our reading of complaints, not
yet a count of them), not the spec's full surface area.

Source, documents and issues: https://github.com/bellbriar/harness (the
files this page names, such as `docs/REPORT.md`, are there).

## Install

**In GitHub Actions**, one step, with nothing to set up (Linux runners):

```yaml
- uses: bellbriar/eval-action@v1
  with:
    args: dist --render --fail-on tier1 --html bellbriar-report.html --json bellbriar-report.json
```

`examples/ci/bellbriar-eval.yml` is a complete workflow for a site's
repository, and `action/README.md` lists the Action's inputs.

**On your machine**, with [pipx](https://pipx.pypa.io/) or
[uv](https://docs.astral.sh/uv/), which keep it apart from your other
Python packages (Homebrew's and Debian's Pythons refuse a system-wide
`pip install`). It needs Python 3.11 or later. It runs on Linux and
macOS; on Windows the commands stop and say so, and it runs in WSL (the
Windows Subsystem for Linux) or from the container image below.

```bash
pipx install 'bellbriar-harness[browser]'   # or: uv tool install 'bellbriar-harness[browser]'
bellbriar-eval --install-browser             # Chromium, for --render and --url
```

Without the `browser` extra and Chromium, file runs still work, on the
markup only, and a `--url` run reads the HTML the server sends and says
so. On Linux, Chromium also needs system libraries:
`--install-browser` says when they are missing, and Playwright's
`install-deps chromium` (run as root) installs them. Playwright's
Chromium needs macOS 14 or later: on an older Mac the three commands run,
without the browser, and the container image below runs it.

**In a container**, with Python, Chromium and its fonts installed:

```bash
docker run --rm --init --shm-size=2g --user "$(id -u):$(id -g)" \
  -v "$PWD:/work" ghcr.io/bellbriar/harness:1 dist --render --html report.html
```

In the container Chromium runs without its sandbox, and each capture
records that: Docker's default security profile refuses the user
namespaces the sandbox needs. Give the container a seccomp profile that
allows them (`--security-opt seccomp=docker/seccomp_profile.json`, a copy
of the one Playwright publishes) on a host that allows them too (on Ubuntu
24.04 and 26.04, `sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0`),
and the sandbox starts, as this project's CI shows on x86-64 and ARM64
runners (docs/ROADMAP.md, L81); `--require-sandbox` refuses a run without
it.
Without the sandbox, a page that takes the browser over can write what the
container can: mount a repository's `.git` read-only (`-v
"$PWD/.git:/work/.git:ro"`), as the Action does, and evaluate pages you do
not control only where the job holds no secrets.

## Quickstart

```bash
bellbriar-eval dist --render --html report.html --json report.json  # a build, rendered
bellbriar-eval --url https://www.example.com/ --html report.html      # a live page
bellbriar-eval dist --render --fail-on tier1    # CI gate: exit 1 on Tier-1 failures
bellbriar-lint src/ --fail-on error             # the source, before it is built
```

## What it checks, and what it does not

| Checked | Not checked |
|---|---|
| The markup, in every run: 32 rules, among them text alternatives, the names of links, buttons and other controls, form labels, page language and title, ARIA roles, attributes and references, duplicate ids, blocked zoom, autoplaying sound and skip links | Keyboard operability: focus order, keyboard traps, whether each control works from the keyboard |
| In a browser (`--render`, `--url`): 30 rules, text contrast, target size (WCAG 2.2, for review), reflow at 320 CSS pixels and 27 more WCAG A/AA rules, which axe-core decides | Focus visibility, and contrast in hover and focus states |
| How each page was read: where it came from, when, by which browser, and the SHA-256 of exactly what the rules read | What a screen reader announces, and whether alt text, link text and headings are adequate (a person judges those) |
| Patterns pled in complaints that WCAG does not require on their own, reported for review | Conformance: no tool can certify it, and this one does not claim to |

**How it relates to Lighthouse and axe-core.** Lighthouse's accessibility
score runs a subset of axe-core's rules on one page. Bellbriar runs
axe-core's WCAG A/AA rules that it does not implement itself (axe-core
4.12.1, pinned), except axe-core's experimental and deprecated ones and
`frame-focusable-content`, which needs each frame's own document (`NOT_RUN`
in `axe.py` lists them), and 33 rules of its own, on as many pages as you
give it;
it gates CI on Tier-1 failures, says in every report what was not
evaluated, and can sign its results in an evidence bundle anyone can
verify offline. A page Lighthouse scores 100 can still fail here. Neither
replaces a manual audit.

## What this is not

- **Not a conformance checker.** Version 1.0.0 executes the **static DOM
  layer** and, on pages a browser captures (a `--url` or `--render` run),
  the **rendered checks**: contrast, target size and 27 more WCAG A/AA
  rules that axe-core checks in the browser, and reflow at 320 CSS pixels.
  Keyboard operability (beyond whether scrollable regions can take focus),
  focus visibility, screen-reader announcements, and content adequacy are
  *not* evaluated. Deterministic automation detects a
  minority of WCAG failures; every report states exactly which layers ran,
  and how many Tier-1 rules that covers (17 of 27 today: 16 in a file run;
  4 of those only report for review and never fail).
- **Not a compliance certification and not legal advice.** Output is
  measured findings with methodology attached, nothing more.
- **Not an overlay.** Nothing here injects anything into your site.
  Remediation happens in your source, at generation time.
- **Not an interaction-layer evaluation.** Capturing the hydrated DOM
  changes what the static rules *read* and lets the rendered checks run; it
  does not press keys or move focus. Keyboard operability (but for
  whether scrollable regions can take focus) and focus visibility remain
  unevaluated.
- **Not finished.** `docs/ROADMAP.md` lists what isn't built and what
  "built" will mean for each item. Nothing in this repository describes an
  unbuilt capability in the present tense; if you find one, that's a bug.

## What it is

- A versioned, machine-readable **rulebook** (`rulebook.json`): 62
  deterministic rules that run today (32 on the markup, 30 in the browser),
  3 judged rules, 13 specified for the browser layers. Every rule has a
  tier and a layer, and 74 of the 78 cite WCAG success criteria (two
  review-only rules, for document links and the accessibility statement,
  cite none; two planned flow rules cite WCAG's complete-processes
  requirement). Of the deterministic rules, 40 cite W3C ACT rules and 60
  link a WCAG Understanding document; the judged and planned rules carry
  neither. Each ACT citation gives the rule's id, title and W3C status:
  of the 45 citations, 29 are approved by W3C's Accessibility Guidelines
  Working Group, 15 proposed and 1 deprecated (a rule citing that one
  never fails).
  A proposed ACT rule is written by the ACT Rules Community Group and
  published by W3C without the Working Group's approval, so a rule whose
  only support is one fails as a probable failure (`heuristic`), never as
  a success-criterion failure (`sc`), which W3C itself names: a W3C
  failure technique or an approved ACT rule. Every criterion, level,
  Understanding link, ACT citation and failure technique was checked
  against W3C's own sources (the `w3c/wcag` and `w3c/wcag-act-rules`
  repositories, October 2026; `citations_checked` in the rulebook), and
  `tests/test_citations.py` checks them against a snapshot of those
  sources on every run. Tier 1
  holds what complaint boilerplate pleads (empty links, missing alt,
  unlabeled fields, denial of keyboard access, …); the tiers and their
  weights are a provisional reading of complaints, not counts of them
  (docs/ROADMAP.md §7).
- A **CLI and CI gate**: `bellbriar-eval ./dist --fail-on tier1` exits
  non-zero when generated output contains Tier-1 fails among the rules
  that ran, and a fail means WCAG is violated, or probably is. Patterns
  plaintiffs plead that WCAG does not require on their own (redundant
  links, say) are reported for review, never failed; `--strict` fails the
  gate on them too, at moderate impact or above. Each rule's `verdict_basis` says which kind it is
  (see `docs/MEASUREMENT-AND-EVIDENCE-GUIDE.md`).
- **Honest scoring** (`docs/METHODOLOGY.md`): weighted pass rate over
  *applicable* checks, a zero-Tier-1 page bar printed with its coverage
  denominator, `needs_review` never counted as failure, policy rules and
  rules that never fail never scored, and *no pass rate at all* when
  nothing applies — never a free 100%.
- **Precision fixtures**: `fixtures/conformant-patterns.html` — common,
  conformant markup that must produce zero fails, read as a file (it
  leaves out the framework stylesheets some of its patterns assume, such
  as Bootstrap's for a closed modal, so a browser shows them open) — and
  `fixtures/subtle-bad.html` — real failures that once slipped through.
  Both are enforced by the test suite and grow with every field report,
  as is `fixtures/sample-output.html`, a page written the way the WCAG
  pack asks, which must produce no finding on its markup and no fail in a
  browser.
- **Evidence bundles** you can verify offline with a public key, under a
  byte-level spec with reproducible test vectors
  (`docs/CANONICALIZATION.md`).
- Fixed **contracts for the browser layers** (`browser_contracts.py`).
  Adequacy grading by a judge model is not in 1.0 (no judge is calibrated
  yet); its interface (`judge.py`) stays in the code for when one is.

## Running it

```bash
bellbriar-eval ./dist --html report.html --json report.json   # files, as they are
bellbriar-eval ./dist --fail-on tier1      # CI gate: exit 1 on Tier-1 fails
```

A folder is read for its pages, the `.html`, `.htm`, `.xhtml`, `.xht` and
`.xhtm` files in it and its subfolders; a file named on the command line
must be one of those too, so a source file (`.jsx`, `.vue`: what
`bellbriar-lint` reads) is never judged as a page. `bellbriar-eval --help`
lists every option, with the exit statuses: 0 when the gate passes, 1 when
it fails, 2 when the run could not be completed.

**In CI.** The gate (`--fail-on`, `tier1` by default) counts the FAIL
findings in the site's own markup, of the rules in the tiers it names:
`tier1`, `tier2` (Tiers 1 and 2) or `any`; a vendor's widget's are
reported, not counted. `--strict` adds the review findings that are pled
in complaints or a best practice, at moderate impact or above. The run
exits 1 when the gate fails, and 2, whatever the gate says, when a page
could not be read or analysed (it could not be fetched or parsed, or ran
past its budget) or a rule raised an error; and 2 when the gate found no
failure but had nothing to pass: no page that could be evaluated, or no
Tier-1 rule that applied. A page NOT EVALUATED for what it is, an app
shell or a page still loading, is listed as such, has no pass rate and is
never counted clean; the gate counts any failure it shows.
What a CI job should also know:

- A `--url` run reads only the HTML the server sends when no browser can
  start, and says so; `--require-render` makes that exit 2. `--render`
  always needs the browser.
- A capture waits for the DOM to stop changing and for the page's data
  requests (fetch, XHR) to answer, up to 8 seconds, and 2 more for
  requests still open then and those they lead to; a page still loading
  after that is not evaluated. `--wait-for SELECTOR` waits up to 30
  seconds for an element the page shows once its data has arrived, and a
  page that shows it is read whatever requests are still open: name one
  that only the data brings (`#orders li`), not the frame a loading page
  shows too (`main`).
- `--render` serves files only: a client-side route with no file of its
  own (a single-page app's `/about`) is not served, and is evaluated by a
  `--url` run against a preview of the site.
- A capture that has not finished after `--render-deadline` seconds (120
  by default) is stopped, and the page read as the server sent it (with
  `--render`, as the file it is), or, with `--require-render`, the run
  exits 2. A page whose analysis runs past `--page-budget` seconds (120
  by default) is stopped and not evaluated, and the run exits 2.
- A file run reads a page's own `<style>` elements, not its linked
  stylesheets; a rendered run reads what the browser applied.

**Reports.** `--html` writes a single-file report for people: what the
run covered, its numbers, then the findings grouped by rule — why the
rule matters and how to fix what it found, with HTML, React and Vue
examples — and within each rule by page, and last how each page was read.
Findings that read the same, on one page or across pages (a site's
header, say), are shown once with their count, and a table shows at most
100 rows, saying what it leaves out. `--json` writes the whole record for
scripts in a stable format, `bellbriar-report/1`, documented field by
field in `docs/REPORT.md`: every finding, each with a fingerprint that
stays the same from run to run while the element and the page's recorded
name do. `docs/RULES.md` describes every rule, with its guidance.

Files are read as Chromium reads them. Their bytes are decoded the way
Chromium decodes a local file: a byte-order mark, then the page's
`<meta charset>` where Chromium's own scan finds it, then UTF-8 when the
bytes look like UTF-8 (Chromium's detector is statistical; the harness
follows what it was measured to do), else windows-1252. Legacy encodings
a page does not declare are not guessed. The markup is parsed with the HTML standard's
tree-construction algorithm
([JustHTML](https://github.com/EmilStenstrom/justhtml), tested against
the web-platform-tests parser suite, and compared with the DOM Chromium
builds). Omitted end tags, tables, `<template>`, `<select>`, SVG and
MathML, and declarative shadow roots come out as the browser builds
them, so a minified page that leaves out `</li>` or `</p>` is judged on
the page the visitor gets; each shadow root keeps its own ids and styles.
A `.xhtml`, `.xht` or `.xhtm` file is read by an XML parser, as Chromium
reads it: names keep their case, `xml:lang` sets the language, and a file
that is not well-formed XML, or whose root is not XHTML's `<html>`, is
reported as not evaluated, since the browser shows an error or the XML
itself. The guide's "How the markup is read" has the details and the
known gaps.

A client-rendered app (Vite, Create React App, Angular) builds an
`index.html` that is an empty shell until JavaScript runs. The harness
reports such a page as **not evaluated** — no pass rate, never "Tier-1
clean" — and exits 2 when no page in the run could be evaluated, because a
green gate over an empty shell would be a free pass. Evaluate those sites
on their rendered pages, from the build or from the deployed site:

```bash
bellbriar-eval ./dist --render --fail-on tier1          # the build, rendered
bellbriar-eval ./dist --render --render-base /app/      # built for /app/
```

`--render` serves the folder on this machine (127.0.0.1 only, for the
length of the run, GET and HEAD only, nothing outside the folder and
nothing whose name starts with a dot) and evaluates each page's DOM after
its scripts ran, as a `--url` run does. Set `--render-base` to your
bundler's `base` (or `homepage`) when the build expects to be served under
a path; the run warns when the pages asked for scripts the folder does not
have, which is what a wrong base looks like. The evidence bundle lists
every file the server sent (`"kind": "served"`, with its SHA-256) beside
the pages, so the scripts that built the DOM are on record too.

`--url https://example.com` captures the **hydrated DOM** with a headless
browser whenever the `browser` extra is installed, so content built by
JavaScript is evaluated. Without a browser it falls back to server HTML,
loudly and in the coverage note — never silently, because understating a
site's exposure is the worst thing this tool can do. Server HTML is
decoded and parsed as a file is, with the server's declared charset
first (but, as in Chromium, never guessed as UTF-8), and as XML when
served with an XML type such as `application/xhtml+xml`. A response the
browser shows as text or downloads (`text/plain`, JSON, a feed, a file)
is refused as not a web page, in a rendered run too; a page over 32 MiB
is refused, and a server fetch that has not finished in 30 seconds is
abandoned. The rendered capture runs
in a process of its own. One that has not finished after
`--render-deadline` seconds (default 120) is stopped, browser and all,
and the run falls back the same loud way, so a page whose scripts never
yield cannot hang a CI job; if the harness itself is killed, the browser
goes with it. When a rendered fetch fails, the record says which step failed in
the harness's own words; the browser's error text, which a page can
choose, is printed to the console only.

A rule that raises an error on a page is reported as errored, never as a
pass, and so is a page the harness cannot read: markup that builds more
elements, or nests them deeper, than the harness reads (budgets against
pages that multiply elements or nest tens of thousands deep), or XHTML
that is not well-formed. The other rules
and pages still run, and the reports list the error and mark the run
incomplete. No evidence bundle is written, and the run exits 2: a
measurement with holes in it is not evidence.

```bash
bellbriar-eval --install-browser             # once: Chromium for the browser checks
bellbriar-eval --url https://example.org --domain example.org \
  --save-snapshot snapshot.html --bundle evidence.json
```

**Many pages, one run.** Repeat `--url`, list URLs in a file (`--urls
pages.txt`, one per line, `#` for comments), or name a sitemap
(`--sitemap https://example.org/sitemap.xml`, gzipped or an index of
sitemaps). One run gives one report and one bundle for the set, at most
`--max-pages` pages (50 by default; a sitemap's first 50, in its order).
A run measures one host: a page whose final URL lands elsewhere, one that
cannot be fetched, and one that answers with an error status are each
reported as not evaluated, never as a pass, and the run is then incomplete
(exit 2, no bundle). `--save-snapshots DIR` keeps every page's capture.

```bash
bellbriar-eval --sitemap https://example.org/sitemap.xml --max-pages 100 \
  --domain example.org --save-snapshots snaps/ --bundle evidence.json
```

**Where each finding is.** A finding carries the line it starts on and a
**locator**: CSS selectors that find its element in the DOM the rules
read, one per tree (`["#main > ul > li:nth-child(3) > a"]`, or
`["x-card", "div:nth-child(3) > button"]` for a button inside
`<x-card>`'s shadow root). Paste the first into the browser's console as
`document.querySelector(…)`; the guide's "Finding an element" resolves a
whole locator.

**Vendor markup is reported, not scored.** Rendering pulls in what consent
banners, chat launchers and booking widgets inject into the page. On
realistic markup those outnumber a site's own defects several to one, and
nobody can edit them. So each client-inserted subtree is attributed to the
code that inserted it. It counts as your vendor's — listed, with the
residual duties that stay with you (ask for a current VPAT, keep a
first-party path to every essential task, record the decision) — only
when that code comes from a known vendor origin: consent, chat, booking,
analytics and similar (`KNOWN_VENDOR_DOMAINS` in `fetch.py`;
`--third-party-origin` adds to it). Everything else is yours and is
scored: your own scripts, your CDN, and libraries you load from a public
CDN. The harness records attribution itself, under a name the page cannot
know until the capture is serialized, so markup cannot declare itself a
vendor's. There is exactly one score. A vendor's failures do not count
against it, but its markup still counts toward which rules apply: a rule
that applies to a vendor's elements, and fails only there, counts as
passed, so vendor markup can raise a page's pass rate. And a rule about
the page as a whole reads a vendor's markup with the site's, and its
finding is scored: a navigation a vendor's script puts before the content
is a block the page needs a way past (bb-skip-link), so vendor markup can
lower the rate too. Review items in vendor markup are counted apart as well
(`third_party_needs_review_findings`), not among yours.

A URL or `--render` run records each page's capture: final URL after redirects, HTTP status,
browser version, viewport, wait strategy, attribution policy, and the
SHA-256 of the exact snapshot evaluated. The capture scrolls the page
first and includes shadow roots, open and closed (closed ones are found
through the browser's DevTools protocol, however they were made), so
content revealed on scroll or built inside web components is evaluated
(inside a single component's closed root the search goes 140 levels deep,
and the capture notes anything deeper). It records whether Chromium
ran with its sandbox, which is off only where it cannot start (as root, or
where the host or a container's security profile refuses the user
namespaces it needs, as Docker's default profile does), and notes it when
it was off; `--require-sandbox` refuses such a run instead (exit 2). The scroll and
settle steps before the capture run, like axe-core, in a JavaScript world
of the harness's own, so a page cannot replace the timers and observers
that decide when it has settled. It also records
whether each audio and video element is muted (React and other frameworks
set `muted` as a property the markup does not show), and where the page's
stylesheets hide content (`display:none` or `visibility:hidden`): a closed
Bootstrap or Flowbite modal is hidden by its class, so nothing in it can
take focus, and text a stylesheet hides inside a link does not name it.
A file run cannot read linked stylesheets, so it reports such a modal for
review instead. It does read the page's own `<style>` elements, and
their `display` and `visibility`, so text they hide does not name its
element there either. It reads the rules for the screen, each inside
fewer than eight blocks (of `@media`, `@layer`, `@supports`,
`@container`, `@scope` or style rules): top-level, nested (CSS nesting, unless writing a nested
rule's selectors out with its parents', or an `@scope`'s root into them,
would add more than 20,000 characters, or more than 200,000 over all of a
page's stylesheets; the reports do not say where a page reached these
limits), in `@layer`, in `@media` every screen matches (`screen`, `not
print`), in `@supports` Chromium 141 passes, and in `@scope (root)` as
rules below that root.
`@supports` is settled where a property's name settles it (a test of one
Chromium lacks fails, so `not (-webkit-touch-callout: none)` holds) or
display's value does (`display: grid` passes). Of a rule under a
condition it cannot settle (`@media (min-width: …)`, another `@supports`
test, `@container`, an `@scope` with a limit or with no root), only what
it shows counts, and where a skip link's stand-in control is concerned,
not even that. A `<style media>`, `@media` no screen matches (`print`, a
query a browser drops, or one that can hold nowhere: a feature Chromium
141 does not know, or a value it does not take there, such as one only
known later, `(min-width: var(--bp))`, or a number with no unit as a
width, `(max-width: 768)`; a math function is read by the type it
computes, not by its value; a bracket that closes nothing, a bad string
or a bad url) or `@supports` Chromium fails is not read. Nor is a rule a
browser drops: a style rule whose prelude holds a `;` or a `}` that
closes nothing (`.a{}; .b{}` drops `.b`), one whose selector list has an
empty member, a pseudo-class or pseudo-element Chromium 141 does not
have (`.b, .c::-moz-selection`), one with an argument it does not take
(`:lang(en, fr)`, `:nth-child(foo)`, `:host(.a .b)`, `:has(:has(.a))`),
a "(" that opens no function (`.a (b)`), an attribute selector it does
not read (`[x!=y]`), or a namespace prefix no `@namespace` declares
ahead of the stylesheet's other rules (`svg|a`) (in `:is()` and
`:where()` such a member alone is dropped), `@scope` whose root or
limit is such a list or names a pseudo-element, `@container` whose name
or condition Chromium 141 does not take (`@container none (…)`), and
`@layer` with more than one name (`@layer a b`); the `<!--` and
`-->` of an HTML comment around a stylesheet are no part of it. Names, keywords and units are read with their escapes
(`(hover: \68over)`), a comment separates what is on its either side
but is no white space
(`(width >/**/= 1px)`), and white space is CSS's own (a no-break space
is none). The parts of a media condition are each true, false or
unknown, and combine as Media Queries 4 combines them: false and unknown
is false, so `not ((min-width: 2000px) and (foo: 1))` holds on a screen
narrower than 2000 pixels. The style attribute
and the rules are ordered as the cascade orders them for
layers, `!important` and the CSS-wide keywords (a rule's `!important`
beats the style attribute; `display: revert` shows what a rule hides),
but without specificity: where a rule that hides an element and one that
shows it stand level, it counts as shown. To
re-run the rules on a saved snapshot exactly as the capture was evaluated
(attribution, muted state, what was hidden, shadow roots, and templates
read as inert), pass `--read-as` with the page's `fetch.reader` (in the
JSON report or bundle, `pages[i].fetch`) and, when it has one,
`--provenance-attr` with its `fetch.provenance_attr` (each capture has a
name of its own, so re-run each snapshot so). Re-run so, a snapshot whose
capture does not record this release's marks (one captured before 1.0,
or by a later release that marks pages otherwise) is not evaluated:
capture the page again.

**What the browser checks.** In a `--url` or `--render` run, axe-core
4.12.1 runs on the page just before the capture is taken, and just after
it the page is narrowed to 320 by 640 CSS pixels, the width of a small
phone (it is not widened again: nothing more is read from it). axe-core
(Deque's open engine, under the MPL-2.0) is pinned, ships unmodified, and
is checked against its published SHA-256 each time it loads. It runs in an
isolated world of the harness's own, which shares the page's DOM but none
of its JavaScript, so the page's scripts can neither change what it calls
nor read its results while it runs. It runs only the WCAG A and AA rules
no Bellbriar rule decides: contrast, target size, list and table
structure, ARIA relationships, nested controls, scrollable regions and the
rest of `AXE_RULES` in `axe.py`. Each is reported under a Bellbriar rule
and held to that rule's verdict basis like every other: an ARIA attribute
or value W3C's ACT rules do not require for conformance is a best-practice
review, and target size, new in WCAG 2.2, is reported for review against
this rulebook's WCAG 2.1 AA target and never gates a build, not even with
`--strict`. What axe-core cannot decide is a minor review. A result whose
element the page removed or moved before the capture, or past the 10,000
elements one capture records, is reported about the page under its rule,
so a rule never passes on results that were left out; where axe-core could
not check part of the page (inside closed shadow roots it was not given),
a rule that found no failure there is not evaluated. Bellbriar's own
reflow check fails a page that scrolls sideways at 320 pixels because text
or a control reaches past the edge, naming each element that does; where
only a table, image or code reaches that far it is a review, since WCAG
exempts content that needs two dimensions, and where nothing the element
shows does (empty space, a background) a minor one. A page that hides what
reaches past its edge (`overflow-x: hidden` or `clip` on the root element
or the body) cannot scroll sideways and is not reported; content it cuts
off is not detected. Each page is also evaluated with what it hides at
that width, so a menu shown only on phones whose links take focus inside
`aria-hidden` content, or a button whose label phones hide, fails, and the
finding says it was found at 320 pixels; an element the page removes at
that width is not rendered there, and a finding about something the page
changed itself at that width (an attribute a script set, content it
swapped) is a review, since the snapshot shows it as it was; where that
record could not be taken, the run's coverage says on how many pages. The capture
writes all of it into the snapshot, under names derived from its secret,
so a re-run with `--provenance-attr` reproduces it; each page's capture
record names the axe-core version, its SHA-256, the rules it ran and what
it could not place or check (`fetch.axe`), and the narrow viewport
(`fetch.narrow`). axe-core reads the page's own document, closed shadow
roots included, not its iframes, which are documents of their own. A file
run renders nothing: there these rules are reported as not evaluated,
never as passed.

`--domain` must be the host actually fetched or its `www.` form: a run
that lands on `staging.example.com` is refused for `--domain example.com`.
`--include-subdomains` accepts it, and the evidence then binds the host
beside the domain, so `verify` reports that the bundle records the page
as fetched from
`staging.example.com`, a subdomain of `example.com` — a staging run cannot
pass for production. A run against `localhost`, a name below it, or an
address that is not a public site — loopback, private, link-local,
carrier-grade NAT, documentation and the other special-purpose ranges —
is named as such, from one table that the capture record and `verify`
share. Each capture records how its address class was decided
(`address_basis`): from an address, or from the name alone when the
address it connected to was not seen (through a proxy, or after the page
moved on to another host). For a name, `verify` reports the capture
records' class as theirs: it cannot check where a name pointed. `--allow-domain-mismatch` lets a report proceed
after a mismatch; with `--bundle` the mismatch is still an error. Use
`--save-snapshot` with `--bundle`: a hash of bytes nobody kept proves
nothing.

**Protected staging and preview pages.** Credentials never go in the URL:
`--url https://user:pass@…` is refused, because a password there has
already leaked into shell history and CI logs. Pass `--http-user USER`
and put the password in `$BELLBRIAR_HTTP_PASSWORD`, or in a file named by
`--http-password-file`. The credentials are offered only to the run's
one origin (with several URLs or a sitemap, they must all share it), only
when it asks for them (HTTP Basic), and are never recorded.
An access token in the query, such as a Vercel preview's
`x-vercel-protection-bypass`, can stay in `--url`.

**Recorded URLs carry no secrets.** Every URL a run records — in the
bundle, the reports and the console — is written without a user name or
password, and with every query and fragment value, and every path
parameter's (`/cart;jsessionid=…`), replaced by `REDACTED`.
Host, path and parameter names are kept, so the record still says which
page was measured, and the host a verifier reads is unchanged. A fragment
that is a client route (`#/pricing`, `#!/about`) keeps its path too, so
two routes of one app stay apart; a query after it is redacted, and a
route that holds `=`, `&`, `;`, `#` or `?`, spelled out or
percent-encoded (`#/access_token=…`, as a token handed back to a
hash-routed app looks), is redacted as parameters: names kept, values
`REDACTED`. A parameter with no value (`?<token>`), or a padded token
(`?<token>=`), is replaced whole. A token written as a segment of the
path is recorded with it: nothing tells it from a page's name.
`--record-query NAME` (repeatable) keeps the value of a query or path
parameter that identifies the page, such as `lang`. This happens at
capture because a signed bundle cannot be redacted afterwards without breaking its
signature. A finding's snippet and message, which quote the page's
markup, are written the same way where a URL sits in an attribute HTML
defines for URLs (`href`, `src`, `srcset`, `action` and the like) or is
written whole (`https://…`): no user name or password, and every query
value and path parameter's value `REDACTED` (an element's id after `#`,
as a skip link names it, is kept). The values of the URL's own
parameters that look like credentials,
and the `--http-user` credentials as a request's Authorization header
carries them (base64, as a page that echoes request headers quotes
them), are replaced wherever a finding quotes them, its locator
included, before anything is cut: as they are, or with any character as
a character reference, percent-encoded (in either case, a space as `+`),
with `&` or `%` escaped again once or more (`&amp;`, `&#38;`, `%25`), or
as JSON, a script or CSS escapes it (`\u002f`, `\x2f`, `\u{2f}`, an
octal `\57`, CSS's `\2f ` or `\00002f`, or `\/`, where a script and
CSS both read the character after a backslash as itself), its backslash
escaped again or not (`\\\/`), and `&` and `%` so too (`\u0026#43;`),
but not where a script's octal escapes and CSS's hex escapes, which read
`\61` as different characters, are both used. A run of backslashes is
found as it is, doubled, or four or eight times over, or with each
backslash spelled otherwise (`%5C`, `&#92;`). A
finding's snippet, locator or message that holds the `--http-user`
password (of four characters or more; a shorter one is not looked for),
in any case, as it is, as character references (`&#33;`, `&excl;`) or
percent-encoded (UTF-8, or Latin-1), its white space as `+` too, with
`&` or `%` escaped again or not (`&amp;#33;`, `&#38;#33;`, `%2521`,
`&#37;21`), or as JSON, a script or CSS escapes it (its white space as
`\t` or `\n` too), is withheld whole, since a
word left around it would give it away (a password that holds a
spelling of white space just after its own, as `a %20b` does, may be
missed where that white space is spelled so too). A withheld field
still tells a reader that the password is somewhere in it, in text the
reader may know: the console says how many findings were, and only a
long random password, which no page holds, avoids it.
A password the harness's own text holds ("name", "test", or a word of
the axe-core messages it quotes), or one a URL of the run holds, is
refused before the run, and a page that goes to a URL holding it, or
holding the Authorization header the credentials make, is not evaluated
(the run is then incomplete). The harness does not rewrite
the page itself: a token the page writes into its own markup stays in the
saved snapshot, and other text the page writes (a relative URL in a
`data-` attribute, say) can appear in a snippet as it is.

```bash
export BELLBRIAR_HTTP_PASSWORD     # from your CI secret store
bellbriar-eval --url 'https://staging.example.com/pricing?lang=fr' \
  --http-user ci --record-query lang --domain staging.example.com \
  --save-snapshot snapshot.html --bundle evidence.json
```

## Verify something in thirty seconds

The repository ships a worked evidence bundle that the test suite
re-verifies on every run:

```bash
bellbriar-evidence verify examples/evidence/signed-bundle-example.json \
  --public-key examples/evidence/reference-public-key.hex
# VALID: signature valid (self-signed: it shows that the holder of this key signed this
#   statement and that the bundle has not changed since; not that its results are correct or
#   unedited); every bound field matches; no fetched host is recorded: the domain
#   'cornerbakery.example' is the operator's statement, and nothing was fetched from it; the
#   bundle records rulebook '1.0.0' (sha256 bcd1499723002b80…), the digest of the one
#   bellbriar-harness 1.0.0 ships; its attestation text is the one bellbriar-harness
#   1.0.0 writes. DEMONSTRATION KEY: it signs only the harness's worked example and is in
#   no trust path; this signature is not evidence from any production signer
```

The key that signed it is a **demonstration key**, and `verify` says so:
it signs nothing but this example and is in no trust path. Its private
half is not published — anyone holding it could sign bundles that verify
against the demo key — so verifying needs only the public key beside the
example, and regenerating it (`tools/make_example_bundle.py`) is a
maintainer step.

## Lint the source, gate the output

`bellbriar-lint` mechanizes the deterministic slice of the failure
signatures in Bellbriar's WCAG pack (the rules an AI coding agent is given
while it writes a site; the pack is not distributed with the harness, and
each lint finding names the pack rule it comes from) at the *source* level
(JSX/TSX/Vue/HTML/CSS) —
div-click handlers, stripped focus outlines, conditional live regions,
junk alt expressions, menu roles inside site navigation, zoom blocking,
and friends — so the habit is caught on the line where it was typed:

```bash
bellbriar-lint src/ --fail-on error        # pre-build
bellbriar-eval ./dist --fail-on tier1      # post-build
```

Errors are patterns that are wrong essentially always; warnings need a
human or the gate. Click handlers are read in each framework's spelling:
`onClick` (JSX), `onclick` (HTML, Svelte 5), Vue `@click` and
`v-on:click`, Alpine `x-on:click`, Svelte 4 `on:click` and Angular
`(click)`, with their modifiers (`@click.stop`, `on:click|self`); one that
listens elsewhere (Alpine's `.outside`, `.window` and `.document`, Vue's
`.right`) is not a click on the element. A handler attached in script
(`addEventListener`) or passed in an object (Vue `v-on="handlers"`) is not
read. Attributes are read in their bound spellings too (Vue `:href`,
Angular `[href]`, `[attr.role]` and `routerLink`, Svelte `{href}`).
Classes are read from `class` and `className` — a string, a template
literal, or a class builder (`cn()`, `clsx()`, `classnames()`, `cx()`,
`twMerge()`) — and from bound classes (Vue `:class`, Svelte `class:name`,
Angular `[class]`, `[ngClass]` and `[class.name]`); classes held in a
variable or a CSS module are not. `outline-none` with no focus
replacement is a warning, not an error, when other classes come from an
expression the linter cannot read or when it applies only on a
condition; so is a replacement that applies only on a condition. A click
handler on a `div` around links, buttons or form fields is a warning too:
it may only handle the clicks that bubble up from them, as a menu that
closes when an item is chosen does, and so is one around content passed
in that the linter cannot see (a `<slot>`, `children`). The linter counts
the links and buttons a component renders when it can find the
component's source (declared in the same file, or imported by a relative
path or a tsconfig or jsconfig path alias, through re-exports). A
component from a package, or one that is auto-imported, is not followed:
the links and buttons it renders are not counted, so a `div` with a click
handler around one (an icon from a library, the usual case) is an error,
as one around plain content is. An attribute bound to an expression the
linter cannot read, or supplied by a spread (`{...props}`), never raises
an error: a bound `autoplay` is a warning, and so is a click handler on a
`div` or a link with a spread. To also stop the build on patterns that are
pled in complaints but are not WCAG failures on their own, add `--strict`
to `bellbriar-eval`; the linter's equivalent is `--fail-on warn`, which
also stops on its other warnings. Suppressions exist
(`bellbriar-lint-disable-next-line bl-rule-id`) and each one belongs in
the delivery notes. A clean lint is not a clean gate — lint reads source
habits, the gate proves the built DOM. A scan of a folder skips dependency
and build folders (`node_modules`, `dist`, `.next`, `.svelte-kit` and the
like), whatever git ignores there, files that look minified (a `.js`,
`.mjs` or `.css` file with `.min.` in its name, or with a line of code
over 5,000 characters not counting long strings and `data:` URIs),
and symbolic links to files outside the folder; a file or folder named on
the command line is always linted. `--exclude PATTERN`, repeatable, leaves
out more: each file and folder the shell-style pattern matches, by its
path below the named folder or by its name (`--exclude '*.stories.tsx'
--exclude src/legacy`; `*` matches `/` too, and a pattern ending in `/`
matches folders only). The run says how many folders it left out (and so
did not enter) and how many files besides, and names a pattern that
matched nothing. When git cannot read a
folder's ignore rules (a folder another user owns, say), the scan says so
and lints what they would have skipped. A file the linter cannot read is reported as a
warning (`bl-lint-error`; in SARIF, a notification at level error) and the
run goes on. `bellbriar-lint` exits 2 when it finds nothing to lint, or
can lint none of the files it found, so a wrong path cannot pass as
clean. A
GitHub Actions template for a site repository is in
`examples/ci/bellbriar-eval.yml`.

**Lint findings on the pull request.** `bellbriar-lint src/ --format
sarif --fail-on never > bellbriar-lint.sarif` writes SARIF 2.1.0, which
GitHub code scanning reads (`github/codeql-action/upload-sarif`, with
`permissions: security-events: write`, and on a private repository also
`actions: read` and `contents: read` and GitHub's code security product):
each finding then shows on the line that caused it in the pull request.
`--fail-on never` lets the upload run when there are errors; gate on them
in a step of its own.

**A gate for a site that already has failures.** Make a report once,
`bellbriar-eval ./dist --render --json baseline.json --fail-on never`,
commit it, and gate with `--baseline baseline.json`: the gate then fails
only on findings that report does not list, matched by fingerprint (the
same element failing the same rule on the same page, wherever its line
moves) and by what the gate reads of each: a finding whose verdict, owner
(the site or a vendor), tier or impact changed is new. The reports and
any evidence bundle still list and count every finding, and record the
baseline's SHA-256. Make the baseline from the same kind of run over the
same folder or URLs, since findings are matched by the page's recorded
name (docs/REPORT.md, "`baseline`"). The gate trusts the file: a pull
request that adds its own failures to it passes. Have changes to it
reviewed (a `CODEOWNERS` line for it, with branch protection requiring
code-owner review), or read it from the main branch rather than from the
pull request.

## Layers

| Layer | 1.0.0 status | Covers |
|---|---|---|
| static-dom | **executed** | Names, labels, lang, titles, ARIA validity and references, skip links, viewport zoom, heading and table structure, autoplay, captions/media flags — on the hydrated DOM for `--url` runs |
| accessibility-tree | not built | Spec-faithful accessible names, live roles and states |
| interaction | not built | Keyboard walks and traps, menu and modal contracts, carousels, live regions, task flows |
| rendered | **executed** in `--url` and `--render` runs | Contrast, target size and 27 more WCAG A/AA rules (axe-core 4.12.1, pinned), reflow at 320 CSS pixels; contrast in hover and focus states, text spacing beyond inline styles and focus visibility are not built |
| judge | not in 1.0 | Adequacy: alt quality, link purpose, headings — needs a judge calibrated against human experts, and none is yet |

The calibration policy a judge must meet before it returns (public
development set, private held-out test set, nothing published before a
study exists) is in `docs/MEASUREMENT-AND-EVIDENCE-GUIDE.md`.

## Evidence bundles and signatures

A run can be captured as an **evidence bundle** — input hashes, layer
coverage, results, the rulebook's version and SHA-256, the versions of
the harness, Python and the parsing libraries that decided them, and an
attestation of what a signature does and does not mean — and signed
with a key of your own:

```bash
bellbriar-evidence keygen --out-prefix ~/keys/acme      # mode 600; no overwrite without --force
bellbriar-eval ./dist --domain example.com \
  --bundle evidence.json --sign-key ~/keys/acme.key
bellbriar-evidence verify evidence.json --public-key ~/keys/acme.pub
```

The key is read from a file, or from an environment variable named by
`--sign-key-env` (for a CI secret), and never from the command line,
where shell history, process listings and CI logs would keep it. Each
file keygen writes says on its first line which half it holds, and the
public half (a `.pub` file, or one marked public) never signs: a bundle
signed with it could be signed by anyone.

Every signature this release makes is **self-signed**: it shows who held
the key and that the bundle has not changed since, not that its results
are correct — whoever holds the key could have edited them first. It
covers a **statement** binding the bundle digest to the domain, the host
a URL run fetched, and the rulebook's version and digest, so a signature
cannot be moved to another bundle, or to other claims. `verify` compares
the recorded rulebook digest with the rulebook it ships and names one it
does not ship (a custom `--rulebook`, or another release's); but whoever
holds the key can record any digest before signing, as they can edit any
result. The format reserves
two more classes, `attested-submission` and `attested-execution`, for a
signing service and a hosted runner that do not exist; `verify` reads
either as no more than self-signed. Remote signing, pack pinning and the
judge are not in 1.0 (`docs/ROADMAP.md`). See `docs/EVIDENCE.md`.

## Scope

The harness evaluates what a generating agent authors at build time.
Third-party embed internals, document files (PDF/Office), media
production, platform-locked surfaces, and post-delivery drift are outside
evaluation scope — and are flagged, not ignored, because they are **not**
legal safe harbors.

## Regulatory context

DOJ's ADA Title II rule (28 CFR part 35, subpart H) and HHS's Section 504
rule (45 CFR part 84) both adopt WCAG 2.1 AA. Both agencies extended
their compliance dates by one year in interim final rules (DOJ, 91 FR
20902, April 20, 2026: April 26, 2027 for governments of 50,000 people or
more, April 26, 2028 for smaller ones and special district governments;
HHS, 91 FR 25496, May 11, 2026: May 11, 2027 for recipients with 15 or
more employees, May 10, 2028 for fewer); the technical standard is
unchanged, and both agencies say they plan further rulemaking on the
rules' substance. Checked against the Federal Register on October 10,
2026; verify current status before relying on any date here.

## License and data

Apache-2.0 (LICENSE, with the copyright notice in NOTICE), except
axe-core, which ships unmodified in `src/bellbriar_harness/vendor/axe-core/`
under its own license, the Mozilla Public License 2.0 (its `README.md`
there says where to get its source code; the code it bundles is under the
MIT and ISC licenses); the WHATWG Encoding Standard's labels and indexes
in `src/bellbriar_harness/encodings_data.py`, under the 3-Clause BSD
License, as the standard licenses what source code incorporates of it
(`LICENSE-whatwg-encoding.txt` beside it); and the web-platform-tests
data the tests use (`tests/data/wpt-tree-construction/`, in the source
distribution only), under the 3-Clause BSD License, first written in
html5lib-tests under the MIT License. The package metadata states all five:
`Apache-2.0 AND MPL-2.0 AND MIT AND ISC AND BSD-3-Clause`. **No telemetry.** The harness sends nothing
about you or your runs anywhere. What reaches the network is what you
ask for: a URL run requests the pages you name, and a rendered run
(`--url` or `--render`) lets the browser load whatever those pages or
your built files load, from any origin; `--install-browser` downloads
Chromium through Playwright. Signing and verifying happen locally.
Reports, bundles and snapshots quote the pages they were made from, so
they can hold personal data those pages showed (docs/EVIDENCE.md,
"Personal data in what a run writes").
