# Bellbriar Measurement & Evidence Guide

*A plain-language companion to `docs/METHODOLOGY.md`, `docs/EVIDENCE.md`
and `docs/CANONICALIZATION.md`. Written for three readers at once: our
own operators, a customer's technical lead, and a lawyer deciding how
much weight a Bellbriar report deserves. Everything here is publishable —
the harness is open source and the measurement system only works if
outsiders can understand and check it.*

*Status convention: this guide describes the harness at version 1.0.0.
Anything not yet built is marked **[not built]** and listed in
`docs/ROADMAP.md`. If a sentence here reads as present tense and the
capability does not exist, the sentence is wrong and should be fixed —
that is a bug report we want.*

---

## Part A — How we measure

### The unit of measurement: a check

The harness is a versioned list of rules (the **rulebook**). Each rule
names the WCAG success criteria it tests, except two review-only rules
that test none (document links, the accessibility statement) and two
planned flow rules that cite WCAG's complete-processes requirement. Of the
62 deterministic rules, 60 link a W3C Understanding document and 40 cite
W3C's test rules (ACT); the judged and planned rules carry neither. An ACT citation gives the rule's id, title and W3C status: of the
45 citations, 29 are approved by W3C's Accessibility Guidelines Working
Group, 15 proposed and 1 deprecated, which only a rule that never fails cites. A
proposed rule is written by the ACT Rules Community Group and published by
W3C without the Working Group's approval: it is not W3C's consensus, so a
rule it alone supports fails as `heuristic`, not `sc`. Every criterion,
level, Understanding link, ACT citation and failure technique was checked
against W3C's own sources in October 2026 (the `w3c/wcag` and
`w3c/wcag-act-rules` repositories, at the commits `citations_checked` in
the rulebook names), and the test suite checks them against a snapshot of
those sources on every run. When the rulebook
changes, its version number changes, and every report states which
version produced it, with the rulebook's SHA-256 (`rulebook_sha256`): a
custom rulebook (`--rulebook`) can keep the version and change the rules,
and the digest says so. Verdicts also depend on the code that reads the
page, so every report and bundle records the harness version, the Python
it ran on, and the versions of the libraries that parse and query the
markup (`tool`: justhtml, beautifulsoup4, soupsieve, expat; with a browser,
Playwright and axe-core, and each page's Chromium in its capture record).
The package asks pip for justhtml 3.13.0 exactly, as 3.13.1 builds a
tree Chromium does not (L142), and for soupsieve's 2.9 line, from 2.9.2:
soupsieve's later versions change what a page's selectors match (L133).
Its `browser` extra asks for Playwright 1.63.0, whose Chromium the
container image runs too (L143). A run whose versions lie outside these
ranges (beautifulsoup4 from 4.12, below 5, too) says so on standard error
before it starts, as its verdicts can differ; its record names the
versions it used.
A re-run of a saved snapshot records, as `tool.from_snapshot`, the
axe-core whose results the snapshot holds and the Chromium that
captured it (L53). Two reports are
comparable only when all of these match. The rulebook's
version changes whenever a verdict can change.

At harness 1.0.0 the rulebook (version 1.0.0) holds 78 rules: 32
deterministic rules that run on the markup, 30 that run in the browser
(29 of them axe-core's, one Bellbriar's own: *What the browser checks*,
below), 3 judged rules (adequacy questions graded by a language model),
and 13 rules that are specified but not implemented because they need the
interaction layer or more of the rendered one.

### Verdicts: what "fail" does and doesn't mean

Every finding is one of two verdicts, and the difference is the honesty
of the whole system:

- **fail** — WCAG is violated, or probably is: the rule's failure
  condition is met in the page itself, with no judgment call. An image
  with no text alternative is a fail. For most rules that condition is a
  WCAG success-criterion failure; for a few it is a probable one that
  markup alone cannot settle, and each rule's `verdict_basis` in the
  rulebook says which (see *Which fails are violations* below).
- **needs_review** — a pattern that requires judgment (is this alt text
  actually *good*? does this video have speech?). Reviews are surfaced
  for a human or the judge layer. **They are never counted as failures.**
  Patterns that plaintiffs plead but that WCAG does not require on their
  own — redundant links, or a missing skip link on a page whose main
  landmark or opening heading can satisfy 2.4.1 — are reported this way,
  marked "pled in complaints; not a WCAG failure on its own".

A rule *passes* on a page when it applies there and produced zero fails.
If a rule doesn't apply — a page with no tables can't fail the table rule
— it leaves the math entirely. We don't pad scores with free passes for
things a page doesn't contain, nor for rules that cannot fail: a rule that
only ever reports for review weighs nothing. A page where *nothing*
applies has no pass rate at all: the report says so rather than printing
100%. The same
goes for a page the rules cannot evaluate — the empty `index.html` shell of
a client-rendered app, whose content JavaScript builds. It is reported as
*not evaluated*, never as clean, and a run in which no page could be
evaluated ends in an error rather than a pass.

Two consequences of "prove it from the page" that a reader should know:

- Rules about names, labels and alternatives follow the W3C ACT notion of
  applicability: they evaluate what is in the accessibility tree *as
  served*. Content inside a closed drawer, a closed dialog, or an
  `aria-hidden` region is evaluated in the state where it is exposed —
  which is the interaction layer's job **[not built]**, not a static
  false fail.
- Where a pattern is common and conformant but a naïve rule would fail
  it (a decorative image with `role="presentation"`, a tag-manager
  iframe, a key/value table with no header row), the rule is written to
  pass or to ask for review, and a fixture of such patterns
  (`fixtures/conformant-patterns.html`) must produce zero fails, read as
  a file, on every test run (it leaves out the framework stylesheets some
  of its patterns assume). The mirror fixture (`fixtures/subtle-bad.html`) holds real
  failures that once passed. Both grow whenever the field finds a miss.

### Tiers: why some failures count five times more

Rules carry a tier, and the tiers come from litigation, not from the
W3C — WCAG itself has no severity ranking:

| Tier | What it means | Weight |
|---|---|---|
| 1 | The failure types pled nearly verbatim in filed accessibility complaints (missing alt, empty links, unlabeled fields, keyboard denial, and their kin) | ×5 |
| 2 | Regularly alleged or demanded in settlements | ×2 |
| 3 | In the standard, rarely the basis of a filing | ×1 |
| 0 | Policy checks (e.g., the accessibility-statement link) — reported, never scored | ×0 |

A rule that never fails (*Which fails are violations*, below) weighs ×0
too, whatever its tier: it is reported, never scored. The weights are
stated in the rulebook and are provisional until a complaint-tagging
dataset replaces judgment with counts **[not built]**.
When they change, the rulebook version changes.

### Which fails are violations

Each rule's `verdict_basis` in the rulebook states what its findings
mean. A fail always means WCAG is violated, or probably is; only one kind
is a success-criterion violation:

| `verdict_basis` | What a finding means | Rules |
|---|---|---|
| `sc` | A fail is a failure of each success criterion the rule cites, one W3C names: a W3C failure technique (the rule's `w3c_failures`), or an ACT rule approved by W3C's Working Group that requires the criterion for conformance. Such a rule cites no other criterion, so a report beside its fail names only criteria the fail is a failure of | 22 of the 62 deterministic rules, including missing alt text and unnamed `role=img` images, empty links and buttons, unlabeled fields (4.1.2: whether one also fails 1.3.1 or 3.3.2 turns on visible text that markup alone cannot settle), unnamed menu items, options, tabs and tree items, chosen by their `role` attribute (F68), missing `lang` or title, blocked zoom, focusable content inside `aria-hidden`, and, in the browser, text contrast, links told apart by color alone (F73), nested controls, scrollable regions out of keyboard reach, invalid `lang` values (an invalid `xml:lang` alone, which HTML ignores, is a review), and table header references. A field named only by its placeholder is a review marked "pled in complaints": the placeholder gives it a name, but unless other visible text labels it, it fails 3.3.2, which markup alone cannot settle. A placeholder names only a text field or a `<textarea>`: a `<select>` or a date field named by nothing else fails, as in Chrome and Edge, though axe-core 4.12 passes an `<input>` by its placeholder whatever its type. An unnamed combobox that wraps the text field users type in (the ARIA 1.1 pattern), and a combobox's unnamed popup listbox, are minor reviews: ACT rule e086e5 applies to both by their roles but has no example of either, axe-core exempts both, and assistive technology announces the field's own name (L49). A link, a button or a form field named only by what Chrome and Edge do not read (the text in an `<article>` or a `<figure>`, MathML, a `<span>`'s title, a control's own name or title where an empty `<label>` takes its place: "HTML" below) is a review, not a fail: the accessible-name computation names it (L92, L115, L104) |
| `heuristic` | A fail is a probable failure of the criteria the rule cites, which markup alone cannot settle, or one W3C does not itself name | 15 of the 62 deterministic rules. In the browser: `bb-reflow-320` (content a page needs in two dimensions is exempt), axe-core's list and definition-list structure (no W3C technique makes them failures, and the ACT rule for a list's items is proposed), ARIA roles without the children or parent they require (W3C's ACT rules for them are proposed). On the markup, `bb-iframe-title` (an iframe in the tab order, not marked as decorative, with no name; W3C's ACT rule cae760 is proposed), `bb-progress-name` (an unnamed progress bar or meter, chosen by its `role` attribute: WAI-ARIA requires a name and axe-core reports one under 1.1.1, but W3C names no failure), `bb-control-role` (a focusable element whose role names no role, as W3C failure F59 describes; focus alone does not show it is a control), `bb-marquee-blink` (a `<marquee>` that moves, as failure F16 describes; markup cannot show that nothing pauses it, and one that may stop by itself or that a handler on the page stops is a review). And `bb-skip-link` (fails only when the markup identifies repeated blocks — a leading navigation or page header with two or more links or controls — and nothing bypasses them: no skip link, no main landmark or only one that wraps the navigation, no named region or form landmark the content starts in, no heading that opens the content, and, on a one-page site, no navigation whose links lead to its sections (a link home or to the top aside) — or the only mechanism is a skip link that leads nowhere or is out of the tab order; anything less, including a missing or broken skip link where a main landmark, another landmark the content starts in, an opening heading, a one-page site's in-page navigation or a control that may expand and collapse the navigation (SCR28) remains, a page whose blocks the markup does not identify, and a skip link that comes after most of what it skips, is a review marked "pled in complaints"), `bb-duplicate-id` (fails a duplicated id that a `<label for>` or `aria-labelledby` names, which can name a control from the wrong element; other duplicates are reviews, as 4.1.1 no longer applies to HTML), `bb-table-headers` (a table of three rows and three columns or more with no header cell, as W3C failure F91 describes), `bb-media-autoplay` (fails sound that plays automatically with no controls, or with native controls markup shows hidden or kept from assistive technology; other native controls are a review: a stylesheet can hide them, and ACT notes they are not keyboard-operable in some browsers) |
| `policy` | Stricter than this rulebook's target, WCAG 2.1 AA: **never a fail**. Reported for review, marked "pled in complaints; not a WCAG failure on its own", or, for a WCAG 2.2 criterion, "a WCAG 2.2 criterion, beyond this rulebook's WCAG 2.1 AA target" | `bb-redundant-links`: adjacent duplicate links to the same destination, the pled "redundant links" shape (see the pack's `policy-vs-spec.md`); a product card with an image link and a title link to the same page conforms. `bb-target-size`: a pointer target under 24 by 24 CSS pixels without room around it fails WCAG 2.2's 2.5.8, which the 2.1 baseline does not include; its findings never gate a build, not even with `--strict` |
| `best-practice` | WCAG does not require the pattern on its own: W3C's ACT rules do not make it a conformance requirement, or W3C names no failure for it (each rule's notes say which): **never a fail**. Reported for review, marked "pled in complaints" or "a best practice" | `bb-aria-role`, `bb-aria-attr`, `bb-heading-structure` (empty headings), `bb-positive-tabindex` (WCAG fails it only when the order loses meaning, F44), axe-core's ARIA attribute rules in the browser (required states, allowed, prohibited and conditional attributes, valid values, deprecated roles, braille labels: W3C's ACT rules map them to WCAG only as secondary requirements, or not at all), `bb-xml-lang-mismatch` (W3C deprecated its ACT rule: screen readers no longer read `xml:lang` beside `lang`), and `bb-aria-hidden-body` (current browsers ignore `aria-hidden` on `<body>` and `<html>`, as WAI-ARIA now tells them to; an older one may hide the whole page) |
| `review` | The rule only asks for review: **never a fail** | `bb-aria-ref` (a reference that points nowhere, pled in complaints as "broken ARIA"; when it leaves an element with no name, that element's own name rule fails it, so one defect is one fail), `bb-media-captions`, `bb-autocomplete`, `bb-generic-link-text`, `bb-doc-links`, `bb-a11y-statement`, and in the browser `bb-frame-title-unique` (two frames with one title fail only if their purposes differ), `bb-multiple-labels`, and `bb-th-data-cells` (a header cell that heads no data cell) and `bb-server-image-map`, which axe-core 4.12.1 never fails: it reports each as a result it cannot decide |

Only `sc` fails may be described as success-criterion violations, and
only `sc` and `heuristic` rules fail at all; reports label a heuristic
fail as one. The CI gate counts fails. With `--strict` it also counts
the findings marked "pled in complaints" or "a best practice" — from
`policy` (target size, a WCAG 2.2 criterion, aside) and `best-practice`
rules, a missing, broken or late skip link,
and a field named only by its placeholder — at
moderate impact or above, in the tiers `--fail-on` counts: in effect the
gate before rulebook 0.3.0, plus a missing skip link even where a main
landmark stands in for one. It is for teams that want none of these
patterns before launch.

### The numbers a report shows

1. **Tier-1 clean** (per page): zero failures among the Tier-1 rules that
   *ran*. Every report prints how many that is — at 1.0.0, 17 of 27
   Tier-1 rules are deterministic: 16 run on the markup, and contrast runs
   in the browser, so a file run executes 16 and a `--url` or `--render`
   run 17. The other 10 (keyboard walks and traps, modal and menu
   contracts, carousel pause, focus visibility, error messages, task
   flows, alt-text quality) need the interaction layer or the judge
   **[not built]**. Four never fail — `bb-redundant-links`,
   `bb-positive-tabindex`, `bb-aria-ref` and `bb-media-captions` list
   findings for review — and reports say so: "clean" speaks for the others. Each page
   also says how many Tier-1 rules ran on it (`tier1_rules_executed` in
   its score, and `[17/27]` beside it on the console): in a run that
   rendered some pages and not others, or where axe-core did not finish on
   a page, the count differs from page to page, and a page's "clean"
   speaks only for the rules that ran there.
   "Tier-1 clean" is the ship/no-ship bar for what can be measured; it is
   not a statement about the other 10.
2. **Weighted pass rate**: passed weight ÷ applicable weight, counting
   only rules that can fail. A progress diagnostic — good for tracking a remediation, wrong to quote as
   "percent compliant." There is no such thing as percent compliant.
3. **Flow completability** **[not built]**: can the whole task — find a
   doctor, book, check out — be finished? WCAG defines conformance over
   complete processes, and complaints describe failed tasks, so flow
   verdicts will be all-or-nothing when the interaction layer exists.

### Layer coverage: the banner on every report

Today the harness executes the **static structure layer** — what can be
proven from the page's markup — and, on pages a browser captured, part of
the **rendered layer**: the checks axe-core makes in the browser, and
reflow at 320 CSS pixels (*What the browser checks*, below). It does not
press Tab, move focus, or listen to a screen reader. That is the
interaction layer **[not built]**, and with focus visibility it covers
much of the rest of what lawsuits plead. So every report carries a
coverage banner listing exactly which layers ran (the rendered layer as
`executed`, `partial` when it ran on some pages, or `skipped`), and a
sentence saying what they cover. A file run's, verbatim:

> This run covers the static DOM layer only. Keyboard operability, focus
> visibility, contrast, reflow, screen-reader announcements, and content
> adequacy were NOT evaluated. A passing result here is not sufficient,
> and is not a determination of WCAG conformance or legal compliance.

and a rendered run's:

> This run covers the static DOM layer and the 29 rules axe-core 4.12.1
> checks in the browser (contrast, target size and 27 more WCAG A/AA
> rules) and reflow at 320 CSS pixels. Keyboard operability (beyond
> whether scrollable regions can take focus), focus visibility,
> screen-reader announcements, and content adequacy were NOT evaluated. A
> passing result here is not sufficient, and is not a determination of
> WCAG conformance or legal compliance.

(on a run where some pages were not rendered it names how many were).
Removing that banner from a report voids the report's meaning. Until the
interaction layer ships, a documented human keyboard-and-screen-reader
pass fills the gap (Bellbriar's WCAG pack, which is not distributed with
the harness, has a checklist for it).

### How the page is obtained, and why it matters

`--url` captures the **hydrated DOM** — the page after its JavaScript has
run — whenever a browser is available. That is what a user meets, so it is
what gets measured. Without a browser the run falls back to the HTML the
server sent, and says so in its coverage note and on the console; it is
never a silent fallback, because a JavaScript-built page read as static
markup reports cleaner than it is. The capture also records whether each
audio and video element is muted: React and other frameworks set `muted`
as a property, which the markup alone does not show. And it records where
the page as rendered hides content (`display:none`, `visibility:hidden`),
which stylesheets decide and markup does not show: content in a closed
modal cannot take focus, and hidden text inside a link does not name it.
Where the capture recorded what the page hides, that record decides, not
the `hidden` attribute or an inline style a stylesheet can override.
Elements hidden when the page was captured are still checked for names,
since a menu or dialog shows them later. Hiding is recorded twice: at
the capture's 1280×1024 viewport, and at 320×640, the width of a small
phone, to which the page is narrowed just after the capture (it is not
widened again: nothing more is read from it). Each page is evaluated with
each record, so a menu shown only on phones whose links take focus inside
`aria-hidden` content, or a button whose label phones hide, fails, and the
finding says it was found with the page 320 CSS pixels wide. A finding
both records show is reported once, and where the two records hide the
same things the rules read the page once. The narrow record covers what
the page shows by its stylesheets at that width, and what its scripts
show and hide by a class, a style or the `hidden` attribute. What else a
script changes when the page is narrowed is not in the capture: an
element it removes is not rendered there, and a finding the narrow record
makes about anything it changed (an `aria-hidden` it sets, content it
swaps, an element it moves) is a minor review, because the snapshot shows
that as it was at the capture's own width (a page that changes itself
more than a million times there has all of them read so). Content a
script builds only when the page is narrow is not in the capture, and is
not evaluated. Where the narrow record could not be taken (the page went
to another document when narrowed, one a server sent with HTTP 200 — any
other is refused, below — or its changes could not be watched),
the page's rules ran with the capture's own record only, and the run's
coverage note names how many pages that was.

**A build, rendered.** A client-rendered build (Vite, Create React App,
Angular) is an empty shell until its scripts run, and its scripts load
from the server the page came from (`/assets/index-4f2a.js`), so opening
the file is not enough. `bellbriar-eval ./dist --render` serves each
folder it is given on this machine and captures each page (at most
`--max-pages` of them) as `--url` does. The server listens on 127.0.0.1
only, for the length of the run, on a port taken from the folder's name
(so a page that writes its own address into its markup, as share links
do, reads the same from run to run; when another program holds that port,
the run uses another and says so). It answers GET and HEAD with the files
under the folder (a folder's `index.html` for the folder) and nothing
else: no path outside the folder or through a symlink out of it, and no
name that starts with a dot (`.env`, `.git/`), which a build does not
serve and another process on the machine must not read. A page under such
a name is reported as not evaluated. A symlink to a page inside the folder
is served at its own path, as a static host serves it, and evaluated as a
page of its own; a walk of a folder does not follow a link to another
folder, and says so. `--render-base /app/` serves the build under
the path its bundler's `base` names; when the pages ask for scripts or
styles the folder does not have, the run says so and suggests the
setting. Pages are sent with the charset the harness reads in the file,
so the browser decodes each one as a file run does. A page that sends the
browser to another document when rendered (a script's redirect to a login
page, a refresh) is read as the file it is, since what the browser showed
is another page, and the page it went to, if the build has it, is
evaluated as itself; `--require-render` refuses such a page. A history
change (`pushState`) is no new document, so a client-routed page is
captured as usual. Without a browser the
files are read as they are, loudly, as a `--url` run falls back to server
HTML; `--require-render` makes that an error. Nothing is fetched from a
site, so the evidence binds no host: each page's capture record names
the loopback address it was served from, and the input manifest lists,
beside the pages, every other file the server sent (`"kind": "served"`,
with its SHA-256), the scripts that built each DOM among them.

**Many pages.** `--url` repeated, `--urls FILE` (one URL a line; blank
lines and lines starting with `#` are skipped) and `--sitemap URL` each
make one run of many pages: one report, one bundle, one score for the
set. Repeats are evaluated once: two spellings a browser requests the
same way are one URL, and two URLs that differ only in their fragment are
one page when they capture the same (a client router can show a different
page for each `#/route`, so those are kept apart). Such a page is
recorded under the least of its URLs, whichever the list names first, and
the console says which. A run
evaluates at most `--max-pages` pages
(50 by default, at most 1,000): listing more is an error, and a sitemap
gives its first pages in its own order. A sitemap is read as the protocol
(sitemaps.org) defines it: a `<urlset>`, or a `<sitemapindex>` whose
sitemaps are read in turn (two levels deep, at most 50 files), gzipped or
not; entries on another host are skipped and counted, and a document with
a DOCTYPE is refused, since no sitemap has one and its entities could
expand without bound. A run measures one host, the first page's: a page
whose final URL is on another host is not evaluated, nor is one that
cannot be fetched or answers with an error status, and the run is then
incomplete (exit 2, no bundle), because a page not measured is not a
pass. HTTP credentials are offered only to the run's one origin, so with
`--http-user` the sitemap and every page must share it. The run's own
record (`fetch` in the report and bundle) names the host, the first
page's final URL, how many pages were listed and how (`list`: `urls`, or
`sitemap` with its URL, the pages it listed and whether every sitemap was
read); each page's capture record is its own `fetch`. `--save-snapshots
DIR` writes every capture as `NNN-<page>.html`.

**How the markup is read.** A file, or what a server sent, is decoded and
parsed as Chromium 141 does it. Decoding, in order:

- a byte-order mark;
- the charset the server declared, read from its Content-Type as
  Chromium reads it (`charset='utf-8'`, quotes and all, names no
  encoding; of two Content-Type headers the later type decides; a header
  folded over two lines is one header; a label with a stray control
  character in it names none);
- the first `<meta charset>` (or `http-equiv` Content-Type) Chromium's own
  meta scan finds: one in a comment, an attribute value, `<script>`,
  `<style>` or `<title>` does not count, and one past the first 1 KB
  counts only while everything before it could be in the page's head
  (a meta in the body, a `<template>` or an `<svg>` past that point is
  ignored, as Chromium ignores it);
- an XML declaration's encoding;
- for a local file only, UTF-8 when its first 256 KiB look like UTF-8.
  Chromium's detector is statistical; the harness takes a file as UTF-8
  when every non-ASCII byte there belongs to a UTF-8 character, or when
  there are at least ten UTF-8 characters and no fewer of them than of
  the bytes that do not
  (measured: twenty accented letters among twenty stray Latin-1 bytes
  are UTF-8 to Chromium, five among one are not). Chromium never guesses
  UTF-8 for a page a server sends without a charset, and shows its bytes
  as windows-1252, so the harness reads them that way too;
- windows-1252.

Labels and single-byte tables are the Encoding Standard's own. An XML
document (below) is decoded as XML: no `<meta>` counts, and UTF-8 is the
default. Each rule above is measured against Chromium: the test suite
holds 442 documents with the encoding Chromium chose for each, over HTTP
and from a file, and 37 sets of Content-Type headers. Known gaps:

- Chromium also guesses legacy encodings (Shift_JIS, windows-1257, even
  ISO-8859-4 for a short page with a stray byte or a cut-off character)
  from the text of a page that declares none. The harness does not, so
  such a page reads as windows-1252 and its text is garbled. For the
  same reason the harness's UTF-8 rule can differ from Chromium's
  detector near its threshold, and on rare byte patterns such as an
  overlong UTF-8 sequence. Chromium's detector reads the page's text, so
  a file whose only non-ASCII characters sit in its markup (an id or
  another attribute value) can be windows-1257 to Chromium and UTF-8 to
  the harness.
- Over HTTP, Chromium can decode the text before a late `<meta charset>`
  in a long head as windows-1252, when that text arrives in an earlier
  network chunk; the page's encoding (`document.characterSet`) is still
  the meta's. The harness, like a file load, decodes the whole page with
  the meta's encoding.
- Python's ISO-2022-JP decoder does not recover from a malformed byte as
  Chromium's does.

**Which responses are pages.** The server's Content-Type decides, as it
does for Chromium: `text/html`, or no usable type, is read as HTML;
`application/xhtml+xml`, `application/xml`, `text/xml`, `image/svg+xml`
and `text/xsl` as XML. Anything else is not a web page: the browser shows
`text/plain`, JSON, CSS or a feed as text and downloads the rest, so the
harness evaluates nothing and says why. A rendered run reaches the same
answer from what the browser shows. A page served as XML is read from
the server's bytes with the XML parser in a rendered run too, and its
capture record says so: the harness reads a capture back as HTML, which
would fold the case XML keeps, so content such a page's scripts add is
not evaluated, and `--require-render` refuses the page.

**HTML.** Parsing follows HTML's tree-construction algorithm (JustHTML,
tested against the web-platform-tests parser suite), with three changes
Chromium 141 makes, each measured: a `<select>` bounds every element
scope, so a `<select>` inside a `<p>`, `<a>` or `<button>` keeps its
options; `<search>` is not a special element; and a CDATA section at an
HTML integration point (an SVG `<title>` or `<foreignObject>`, a MathML
`<mtext>`) is a comment, so `<svg><title><![CDATA[Home]]>` names
nothing. The suite compares the trees with the DOM Chromium 141 builds:
1,599 of the 1,605 WPT documents and 409 of 410 `<select>` cases are
identical. The rest (a lone `<?`, a NUL or U+FFFD before `<frameset>`,
`<command>`, one misnested-formatting case, a `</p>` inside a
`<select>`) are listed in `tests/test_html5_parsing.py`, and no rule
reads those patterns. A processing instruction becomes the comment
Chromium makes of it. A `<button>` that is a `<select>`'s first child (a
customizable select's) is inert, as HTML makes it, so no rule evaluates
it as a button. Differences from Chromium 141 remain in MathML and in
names from content. Chromium does not render the HTML inside a MathML
`<annotation-xml>`, so a rendered run reads it as hidden where a file
run reads its text. Chromium gives a link or a button no name from
MathML content at all (`<a href="…"><math><mi>x</mi></math></a>` has
none), where the accessible-name computation reads the MathML's text.
And of an element inside a link or a button whose role is one that holds
other content (`<article>`, `<figure>`, `<nav>`, `<header>`, `<aside>`,
`<main>`, `<blockquote>`, `<fieldset>`, `<dialog>`, `<object>`, a
`<table>` of data, role="group", "toolbar", "table", "img" and the
like), Chromium reads only the element's own name, its author's
(aria-labelledby, aria-label, title) or, for some, its markup's (a
`<fieldset>`'s `<legend>` or a `<table>`'s `<caption>` where shown, a
`<table>`'s summary where it has no `<caption>`, an `<output>`'s
`<label>`), never the rest of what it holds: `<a href="…"><figure><img
src="map.png" alt="Map"></figure></a>` has no name there, where the
accessible-name computation reads the element's content. Nor does
Chromium read the title of a `<span>`, a `<div>`, an `<i>`, a `<p>`, an
element HTML does not have (an `<icon>`) and the like there (`<a
href="…"><i class="icon" title="Home"></i></a>` has no name, or only an
icon font's glyph where a stylesheet draws one), where it reads a
heading's, an `<abbr>`'s, an image's or a custom element's (but one
whose role is none or presentation), and that of an element with a
`tabindex`, of a link, and of a `<span>`, a `<div>`, an `<i>`, an
`<icon>` and the like with a `draggable` attribute. It reads a
`<label>`'s content naming a button the same way, and a button's
`<label>` (one whose `for` names it, or one that holds it as its first
labelable element) takes the place of the button's own content, value
and title, an empty or hidden one too, or one that holds the button
alone, but not one in a `<template>` or inside a closed `<details>`
(each measured). A submit or reset button's default name (Submit, Reset)
names it only where it has no `value` attribute: an empty value names it
nothing, and Chromium reads no title after it. The harness names such a
link or button as the accessible-name computation does, so it is no
failure, and reviews one whose only name Chromium does not read. The
review says when it matters: in Chrome and Edge the control has no
accessible name. It is minor (other tools usually pass it), or moderate
where axe-core 4.12 does not read that name either (MathML, text inside
an `<object>`, a `<canvas>` or a drawing, the title of a `<slot>` or of
an element that holds white space or whose role is none or
presentation), and its message gives the reason it found. A form
field's `<label>` takes the place of its title and placeholder in
Chromium the same way, an empty or hidden one too: a field named only
by its title past such a label is a minor review (axe-core 4.12 passes
it), and the review of a field named only by its placeholder says so
(L104). A field named only by text in its `<label>` that Chromium does
not read is a review as a button's is: minor where axe-core passes it
(by the field's title or placeholder, or by that text where it is a
title axe-core reads), else moderate (axe-core reads a `<label>`'s
content by rules of its own: it fails one holding an `<article>`, passes
one holding a `<figure>`). Chromium reads a `<label>` inside an
`aria-hidden` element, unlike the accessible-name
computation and axe-core, which leave it out; a control named by such a
label alone fails as it does in axe-core (L128). A
`<table>` is one of data by its markup alone (a `<caption>`, `<thead>`,
a `<th>`, a cell's `scope`, twenty rows and the like); one that only its
cells' borders or colors make one of data, which the page's styles
decide (a `border` or `bgcolor` attribute too, which a style may undo),
is read as one of layout (L121). A control inside the link (a combobox,
a progress bar) is read by its content, as before, where Chromium reads
its value (L101).

A declarative shadow root (`<template shadowrootmode>`) attaches as
Chromium attaches it: to the element the template was opened in, if that
element may host one and has none yet, decided as the parser meets it.
Its content is evaluated, and the host's children appear in the slots
that show them. Each shadow root is a tree of its own: an `id`, a `<label
for>`, an `aria-labelledby` and a `<style>` reach only within the tree
they are in (a shadow root's `:host` and `::slotted` rules style its host
and the host's children), and a fragment link (`#main`) only the
document's, so two instances of a component may repeat an id, and a skip
link into a shadow root moves nothing.

Past 512 open elements a new element goes to the current node's parent,
as in Chromium (approximately: Chromium decides it while parsing, the
harness after, so an implied `<tbody>` or an element the adoption agency
moves past that depth can land one level off, and so can what follows a
`<template>` opened there). Nothing leaves a
`<template>`, whose content is a fragment of its own, and a declarative
shadow root stays with its host, so a component nested deep in a page is
evaluated as Chromium renders it.

**XML.** A page served with an XML type, or saved as `.xhtml`, `.xht` or
`.xhtm`, is read with an XML parser (Python's expat, with namespaces), as
Chromium reads it: names keep their case (`<A href>` is no link, `ALT` is
no alt), `<x/>` closes itself, a CDATA section is text, `xml:lang` sets
the language, there are no implied elements, a `<template>`'s children
are its content, and no declarative shadow root attaches. HTML's named
characters (`&nbsp;`) are known, in text and attribute values alike, only
under one of the XHTML DOCTYPEs Chromium recognizes by public identifier;
any other undeclared entity is an XML error. Entities a page declares
itself may add at most a million characters to it, or five times its
size if that is more, and nest at most 39 deep, as Chromium's parser
(libxml2) allows; past either the page is an XML error to Chromium and
not evaluated by the harness. (libxml2 also charges each reference a
fixed cost on top of its text, and compares with the part of the page read
so far, so a page with many short or nested references, or one whose large
expansion comes early, can be an XML error to Chromium yet evaluated
here.) References in comments, CDATA sections and processing instructions
are none. An
element of another vocabulary is no HTML element: one with a prefix keeps
it (`<dc:title>` in an RDF block is not the page's title), and one in
another default namespace or in none (`<img xmlns="urn:x"/>`) is named
`ns:img`, so no rule reads it as an image or a link. Two kinds of
document are reported as not evaluated, because the browser shows no
page: one that is not well-formed, which Chromium replaces with an XML
error over the part it read, and one whose root is not XHTML's `<html>`
(an SVG image, a feed, XHTML without its namespace), which it shows as
XML. On 9,000 generated documents (5,191 pages, 3,727 not well-formed,
82 not pages), the harness and Chromium agreed on every one: well-formed
or not, a page or not, and for each page its elements, their attributes
and its text.

**Budgets.** Some markup makes the parser build far more elements than it
has tags (formatting elements such as `<b>` are reopened in every block
after them), and nesting tens of thousands deep makes every rule walk
long ancestor chains. So a page is read within two budgets, in every
reader (a rendered capture's included): the elements it builds, each
attribute weighing a thirtieth of an element (one per byte of markup, at
least 200,000 and at most 1.5 million), and the sum of every element's
depth (40 million). A page past either is reported as not evaluated, with
the reason, rather than read until memory or the CI job's time runs
out. No real page comes near them: of the 83 pages in the
field sweep, the deepest nests 20 levels and the largest builds 5,422
elements.

A rendered capture is different: it is the browser's own serialization of
the live DOM, read back exactly as it was, because re-parsing it would
"repair" nesting the live page really had. The run records how it read
the page in its capture record (`pages[i].fetch`; `reader`: `dom` for a rendered capture,
`html` for server HTML, `xml` for an XML page). To re-run a saved
snapshot as its run did, pass that as `--read-as`, and the record's
`provenance_attr`, when it has one, as `--provenance-attr` (which alone
implies `--read-as dom`, whatever the snapshot is called).

The snapshot is saved as UTF-8 with a byte-order mark. The page's own
encoding was decoded at capture; the mark makes a re-run read the
snapshot as UTF-8, whatever its `<meta charset>` says.

**Timeouts and errors.** The rendered capture runs in a process of its
own. If it has not finished after `--render-deadline` seconds (5 to
86,400; 120 by default), it is stopped with the browser under it. The run
then falls back to server HTML loudly, or exits 2 with `--require-render`.
If the harness itself is stopped (Ctrl-C, a CI job's timeout, a kill),
the capture process notices and stops the browser too.

A rule that raises on a page is recorded as errored for that page, and a
page the harness cannot read (one past the element budget) as not
evaluated. Neither is ever a pass: an errored rule is left out of the
rates and of the count of Tier-1 rules executed, unless it ran elsewhere,
and a page where a Tier-1 rule errored is not called Tier-1 clean (the
console marks it `T1 ERROR`). The other rules and pages still run; the
reports list each error, and the JSON report says `"incomplete": true`.
No evidence bundle is written, and the run exits 2.

Capturing the hydrated DOM changes the **input** the static rules read,
and lets the rendered checks run. It does not execute the interaction
layer, which stays unevaluated: nothing presses a key or moves focus, and
nothing in a report should be read as claiming otherwise.

### What the browser checks

In a `--url` or `--render` run the browser runs axe-core just before the
capture is taken, and just after it narrows the page to 320 by 640 CSS
pixels, where it records what the page hides, what the page changed on
being narrowed, and whether it reflows (above).

**axe-core.** axe-core is Deque's open accessibility engine (MPL-2.0).
The harness ships version 4.12.1 unmodified (`vendor/axe-core/`, with its
licenses and a notice saying where its source is) and checks the file
against its published SHA-256 each time it loads it: a file that differs
is never run, and the page's axe-core rules are then reported as not
evaluated. It runs in an isolated world the harness makes through the
browser's DevTools protocol: a JavaScript world of its own over the
page's DOM, which the page's scripts cannot reach, so they can neither
redefine what axe-core calls nor read its results. It reads the page's own
document, closed shadow roots included (the protocol finds them), and not
its iframes, which are documents of their own. It runs only the WCAG 2.0,
2.1 and 2.2 A and AA rules that no Bellbriar rule decides, axe-core does
not mark experimental or deprecated, and need nothing the capture does not
read: 29 of them (`AXE_RULES` in `axe.py`, each beside the Bellbriar rule
that reports it; `NOT_RUN` lists every other WCAG rule of axe-core and
why). Where Bellbriar has its own rule (alt text, names, labels, `lang`,
titles, the skip link, ARIA hiding), Bellbriar's rule decides and
axe-core's is not run. Native checks replace axe-core's rule by rule
later, and the rule ids stay.

Each axe-core rule is reported under a Bellbriar rule and held to that
rule's verdict basis, like every other (*Which fails are violations*,
above): a violation of a rule whose basis is `sc` or `heuristic` is a
fail; one of a `best-practice`, `policy` or `review` rule is reported for
review (target size, a WCAG 2.2 criterion, never gates a build, not even
with `--strict`). A result axe-core could not decide (text over an image, say) is a
review at minor impact, which `--strict` never gates. Findings carry
axe-core's own words and name the axe-core rule and version.

Nothing axe-core finds is dropped, but for one case below (part of the
page it did not check). Just before the capture, the isolated
world says where each element it reported is, and just after it, whether
the page changed anything on the way there; a result whose element the
page removed or moved first, or past the 10,000 elements one capture
records, is not put on any element (never on the wrong one) and is
reported about the page instead, as a fail or a review under its rule. A
page cannot crowd out failures with results that never count: those of
the rules that can fail are recorded first. Where axe-core did not check
part of what was captured (inside closed shadow roots it was not given:
one the page attached after it ran, or more than the harness looks for),
a rule that found no failure is not evaluated on that page: the reviews
it found there are not reported, and the capture's notes say so. axe-core takes contrast, then target size, then
its other rules, in parts, and starts no part after 30 seconds on one
page; it is not run at all on a page of more than 20,000 elements, which
could take the capture past its deadline. Either way the rules it did not
run are not evaluated there. axe-core checks the page as it is when it
starts: elements the page adds after that, before the capture, are in the
snapshot and the static rules read them, but axe-core did not check them,
and the capture's notes count them.

**Reflow.** Bellbriar's own check, `bb-reflow-320`: at 320 CSS pixels
wide nothing may make the page scroll sideways (WCAG 1.4.10). The capture
records the page's scroll width there and each outermost element that
reaches past the right edge, outside anything that clips or scrolls
sideways and not fixed to the viewport, with what in it reaches that far.
Where text or a form control does, it is a fail, as a probable failure.
Content that needs two dimensions is exempt, so where only a table,
image, map, video or code reaches past the edge it is a review; where
nothing the element shows does (empty space, a background, a row's
negative margin) it is a minor review. A page whose root element or body
hides what reaches past its edge (`overflow-x: hidden` or `clip`, which
the viewport takes) cannot scroll sideways, and is not reported; content
it cuts off there is not detected (L45).

**Where the results live.** The capture writes axe-core's results, the
narrow record and the reflow measurement into the snapshot, under names
derived from its secret provenance attribute, as it writes attribution.
The page cannot know those names before the capture is serialized, so it
cannot write such a record about itself; a script watching the page's
attributes can see them afterwards, when they no longer name anything the
harness reads from the page (each capture's names are new, and nothing
after it is written to the page under them). The capture's entry points
answer only calls carrying tokens the page never sees. A re-run of the
snapshot with `--provenance-attr` reads the records and reproduces every
finding. Each page's capture record (`pages[i].fetch`) names the axe-core
version, its SHA-256, whether its results were recorded (and if not,
why), the rules it ran and any it ran out of time for, how many elements
carry its results, how many results no element carries, how many
elements it did not check and how many the page added after it started
(`axe`), and the narrow viewport with what the page changed there and its
reflow measurement (`narrow`). A file run renders nothing, so the
rendered rules are reported as not evaluated there, never as passed.

**Vendor markup is reported and not scored.** A rendered page includes
whatever consent banners, chat launchers and booking widgets inject into
it. On realistic markup those produce several times more findings than the
site's own code, and the site owner cannot edit any of them. So each
client-inserted subtree is attributed to the code that inserted it.
Markup counts as a third-party widget, which `scope-and-exclusions.md`
EXC-1 places outside evaluation scope, only when the code that inserted
it comes from a known vendor origin — consent managers, chat and booking
widgets, analytics and tag managers (the list is versioned in the
harness, and an operator can add a vendor with `--third-party-origin`).
Everything else is first-party and is scored: the site's own scripts, its
CDN, and libraries it loads from a public CDN, because being served from
another origin does not make code someone else's. The harness records
attribution itself, at capture time and under a name the page cannot
know until the capture is serialized, so a page cannot declare its own
markup a vendor's. Third-party
findings appear in the report with the duties that remain with the site
owner — obtain the vendor's current conformance report, keep a
first-party path to every essential task, record the decision. There is
one score, and it covers what the customer can act on. Two numbers would
invite quoting the friendlier one. Review items in vendor markup are
counted apart in the same way (`third_party_needs_review_findings`
beside `third_party_fail_findings`), so the site's review count is its
own.

A rendered run records, for each page, what it captured: the final URL after redirects,
the HTTP status, the browser name and version, the viewport, the wait
strategy and how long it waited, the attribution policy, and the SHA-256
of the exact snapshot evaluated. Before capturing, it scrolls through the
page, and the snapshot includes shadow roots, open and closed (closed
ones are found through the browser's DevTools protocol, however they were
made), so content revealed on scroll or built inside web components is
measured rather than missed (inside a single component's closed root the
search goes 140 levels deep, and the capture notes anything deeper). Chromium
runs with its sandbox wherever it can start, and the record says when it
could not, and why, for the errors Chromium gives when it cannot (the
user namespaces it needs are refused, by the host or by a container's
security profile, its setuid helper is not set up, or the run is root's);
it runs without one only after those errors, and `--require-sandbox`
refuses the run instead. Docker's default security profile refuses those
namespaces, so the container image runs Chromium without its sandbox
unless it is given a profile that allows them. The scroll and settle steps
run in an isolated world of the harness's own, as axe-core does, so a
page's scripts cannot replace the clocks, timers or observers they use.
The settle step watches the whole document, a replaced root, a rewritten
document and open shadow roots included, but not inside closed shadow
roots, which no script can reach, nor inside frames: a page that changes
only there can look settled sooner. A non-200 is refused rather than scored — an error page is not
the page anyone meant to measure. So is a page that, before the capture
ends (the 320-pixel step included), sends the browser on to anything but
a web page a server sent with HTTP 200: an
error page, the browser's own error page or a blank page, a document a
script made (a `blob:` or `javascript:` URL) that does not go on at once
to a page, one that is not a web page, one that never finished loading,
one that had not arrived when the load timeout ended (or a few seconds
before the render deadline: while a navigation is pending the browser
answers none of the harness's calls to the page it leaves), or a chain of
documents that does not settle. A page it went to that is one is read in
its place, and the record says so; one it goes to after the capture
leaves the capture as it was, with a note. What a page does after the
capture ends is not watched.
No service worker answers any of the page's requests (the capture
bypasses them, as the developer tools' "Bypass for network" does), so a
page is read as a server sends it. And the host actually fetched must be
the stated `--domain` or its `www.` form. A run that lands on a
subdomain — `staging.example.com` for `example.com` — is refused unless
the operator passes `--include-subdomains`; the evidence then records the
host beside the domain, inside the signed statement, and the verifier
names it. A staging run cannot be read as production. (A file run records
no fetched host: its domain is the operator's statement, and the verifier
says so.)

A run keeps the secrets it is given out of what it records. Staging and
preview pages are often reached
with a password or an access token. A URL with a password in it is
refused; the operator passes `--http-user` instead, with the password in
the environment or a file, and it is offered only to that site. Every URL
the run records — in the bundle, the reports and the build log — is
written without a user name or password, and with every query and
fragment value, and every path parameter's (`/cart;jsessionid=…`),
replaced by `REDACTED`; each page's capture record says what was left
out (`pages[].fetch.redacted`).
Host, path and parameter names are kept, so the record still
identifies the page, and the snapshot hash identifies the exact bytes. A
fragment that is a client route (`#/pricing`) keeps its path as the URL
keeps its own, so two routes of one app stay apart; its query is
redacted, and a route holding `=`, `&`, `;`, `#` or `?`, spelled out or
percent-encoded — the shape of a token handed back to a hash-routed app,
`#/access_token=…` — is redacted as parameters: names kept, values
`REDACTED`. A parameter with no value, or a padded token (`?<token>=`),
is replaced whole. A token written as a segment of the path is recorded
with it: nothing tells it from a page's name. An
operator can keep a value that identifies the page, such as a language,
with `--record-query`. This happens at capture because a signed bundle
cannot be redacted later without breaking its signature: evidence has to
be safe to hand over exactly as it is. A finding's snippet and message
quote the page's markup. A URL in them is written as a recorded URL is,
with no user name or password and every query value and path
parameter's value `REDACTED`, where it
sits in an attribute HTML or SVG defines for URLs (`href`, `src`,
`srcset`, `action` and the like) or is written whole (`https://…`, read
as a browser reads it, `https:\\…` too); a fragment holding parameters
is redacted as well, a client route keeps its path, and an element's id
(`#main`: up to 64 characters with no `=`, `&`, `;` or `?`) is kept, as a
skip link names it. In a `javascript:` or `data:` value, the query values
and any user name and password written in it are replaced. And the values
of the run's own URL parameters that look like credentials are replaced
wherever a finding quotes them, its locator included, as the URL gave
them, or with any character as a character reference, percent-encoded
(in either case, a space as `+`), with `&` or `%` escaped again once or
more, or as JSON, a script or CSS escapes it, its backslash escaped again
or not (but not with a script's octal escapes and CSS's hex escapes,
which read `\61` as different characters, both used): a page can write
the token it was sent into its own markup, into a script's data, or into
its CSS. So are the `--http-user`
credentials as a request's Authorization header carries them, which a
page that echoes request headers quotes. A finding's snippet, locator
or message that holds the `--http-user` password (of four characters or
more), in any case, as it is, as character references (`&#33;`,
`&excl;`), percent-encoded (UTF-8, or Latin-1), its white space as `+`
too, or as JSON, a script or CSS escapes it (its white space as `\t` or
`\n` too), with `&` or `%` escaped again or not, is withheld whole: a word left around it would give it away (one
that holds a spelling of white space just after its own, as `a %20b`,
may be missed where that white space is spelled so too). A
withheld field still tells a reader that the password is somewhere in
it, in text the reader may know, so the harness refuses a password its
own text holds (the axe-core messages it quotes included), or a URL of
the run holds, does not evaluate a page that goes to a URL holding it
(or holding the Authorization header the credentials make), and only a
long random password is safe. Other text the page writes is quoted as it
is: a relative URL in a `data-` attribute, say, or a token the page made
from its own. The
snapshot itself is not rewritten — it is the bytes that were measured,
and the bundle holds only its hash.

### Where a finding is: locators

A finding's line number points into the file the rules read, and for a
rendered run that is a snapshot nobody has open. So every finding about
an element also carries a **locator** (`selector` in the JSON report and
the bundle; the "Where" column of the HTML report): CSS selectors that
find the element in the DOM the rules read — a file or a server's HTML as
a browser parses it, a rendered run's DOM as captured.

A locator is a list with one selector per tree. The first is matched in
the document; each next one in the shadow root of the element the one
before it found, so an element inside a shadow root inside another has
three. Each selector is a chain of child steps from an anchor down to the
element, as the browser's own "Copy selector" writes one
(`#main > ul > li:nth-child(3) > a`). The anchor is the nearest element,
from the element itself upward, whose `id` no other element of its tree
has (ignoring ASCII case, as a quirks-mode page compares ids); failing
that `body`, `head` or `html`; at the top of a shadow root, its top-level
element, after `:host >` when that step alone could also match deeper
down. Below the anchor, each step is the element's name, with
`:nth-child(k)` when a sibling has the same name. A host's light-DOM
children are counted where they are in the DOM, not in the slot that
shows them (a slot can pass them on into a nested component's own slot),
and an id or name among the children no slot shows is never an anchor,
since a selector could find one of them first. A name with a prefix
(`dc:title` in XHTML) is written `*` and found by position. A locator
holds at most 100 steps over all its trees: an element deeper than that
below its anchors has none (`selector` is null), and its finding gives
its line.

**Finding an element.** In the browser's console, on the page:

```js
function resolve(locator) {
  let scope = document, el = null;
  for (const selector of locator) {
    if (!scope) return null;        // a closed shadow root: see below
    el = scope.querySelector(selector);
    if (!el) return null;
    scope = el.shadowRoot;
  }
  return el;
}
resolve(["x-card", "div:nth-child(3) > button"]);
```

A page script cannot open a closed shadow root. In the developer tools,
expand the host's `#shadow-root (closed)` in the Elements panel, select
any element inside it, and run the next selector with
`$0.getRootNode().querySelector(…)`.

Each locator matches exactly its element in the DOM the rules read, by
construction, and the suite resolves every element's locator in Chromium
141: in files as the parser builds them (scripts off), in XHTML, and in a
rendered capture with shadow roots attached by script, each found and
none matching another element. Of the 101,971 elements in the field
corpus and the web-platform-tests parser documents, Chromium found every
one but six, and none of those six is in Chromium's tree: four sit in the
parser differences listed under "How the markup is read", and two in a
`<noscript>` that Chromium, with scripts off, parses as markup, where the
harness reads it as a browser with scripts on does, as text. A rendered
page's locators are for the DOM that was captured: the live page matches
them while it renders the same way.

### The judge track (AI-graded judgment calls)

Some questions are judgment (alt-text quality, link purpose in context,
heading descriptiveness). A language model could grade them, and the
rubrics and runner are in the code, but this release does not run them:
no judge is calibrated, so the judge layer is skipped and its three rules
are among those a run reports it did not execute. When a judge returns
(with a calibration that meets the policy below), three rules hold
regardless of provider:

- A judge never overrides a deterministic result.
- Judged numbers are reported on their own track, labeled with the
  provider, the model, and whether it was calibrated.
- Judged output never gates a build and never appears in a compliance
  determination.

**No judge is calibrated, and none runs in 1.0.** There is no
human-labeled golden set, no calibration code, and no measurement of
judge-versus-human agreement, so the judge is not offered in this
release. When it returns, every judged number will carry the label
*UNCALIBRATED: no measured agreement with human experts; treat as
advisory* until calibration exists; a provider that fails to answer will
count as an error, not as a pass and not as a genuine "needs review"; and
a run in which nothing was decided will report *no pass rate*, which is
neither 0% nor 100%.

When calibration is built **[not built]**, it will follow this policy:

- **Two labeled sets.** A *public development set* — small, built from
  public pages, versioned in the repository — that anyone can run to
  reproduce a development-set agreement figure. A *private held-out test
  set* — built from real audits with customer consent and anonymization,
  never published — on which the reported figure is measured, so that
  neither our pack nor anyone else's can be tuned to it.
- **What gets published with a judged number:** the test-set agreement
  figure with a confidence interval; the set's size and composition; the
  labeling protocol (number of raters, inter-rater agreement); the
  pinned reference configuration (model, temperature, prompt hash); and
  the development-set figure that a reader can reproduce.
- **Until that exists, no judged number is published.**

### Benchmark discipline

When we publish "agents alone pass X%; with the pack, Y%":

- The headline number is **deterministic only** — produced by the open
  rules on an open, frozen, versioned, held-out prompt corpus, so that
  anyone with the harness reproduces it to the digit. The rules are
  deterministic given an input; a live URL is not a reproducible input, so
  a rendered run records one capture and ships the snapshot that
  identifies it. Anyone can re-run the rules on that snapshot, with
  `--read-as` set to the capture's recorded reader and `--provenance-attr`
  to its recorded name, when it has one (that carries the attribution, the
  media muted state, the records of what the page hid at both widths,
  axe-core's results, the reflow measurement and which shadow roots the
  capture wrote), and get the same digits. If a
  published
  deterministic number cannot be reproduced from the open harness and
  corpus, the number is wrong and we will retract it.
- The pack is never tuned on the held-out corpus.
- The exact rulebook version and digest, the weights, the harness version
  and the recorded library versions ship with the number, and a
  *reference run* (our configuration, our result) is reported separately
  from *your run*.
- Judged figures, if ever included, follow the calibration policy above
  and are reported beside the headline, never inside it.

No benchmark has been published yet **[not built]**.

### What we never produce

A single "compliance score." A certificate. A guarantee. The output of
this system is *measured findings with methodology attached* — that
phrase is the product.

---

## Part B — How we prove it

### What exists today

| Capability | Status at 1.0.0 |
|---|---|
| Evidence bundle (`bellbriar-evidence/1`) | Built. Any run can produce one, including a URL run of one page or many (its input manifest is each captured snapshot's hash) and a `--render` run (the files, and every file the server sent). Each finding carries a locator. |
| Rendered capture of a live page | Built. Default for `--url`, `--urls` and `--sitemap` with the browser extra, and for a build with `--render`; records browser, viewport, wait, status, redirects and snapshot hash per page; includes shadow roots and scroll-revealed content; attributes findings to known vendors (reported, not scored) or to the site (scored); records what the page hides at its own width and at 320 CSS pixels. |
| Rendered checks | Built for contrast, target size and 27 more WCAG A/AA rules (axe-core 4.12.1, pinned and hash-checked, in an isolated world) and reflow at 320 CSS pixels, in `--url` and `--render` runs. Contrast in hover and focus states, text spacing beyond inline styles and focus visibility are **not built**. |
| Offline third-party verification | Built. `bellbriar-evidence verify` with a public key; spec and test vectors in `docs/CANONICALIZATION.md`. |
| Self-signed bundles (your own key) | Built, and the only kind this release signs. Shows who held the key and that the bundle has not changed since; asserts nothing else. |
| Attested-submission bundles (service-signed) | **Not in 1.0.** The class name is reserved; nothing issues it. A reference signing service stays in the repository (`tools/reference_signer.py`), outside the installed package, for when a production service exists. |
| Attested-execution bundles (runner-signed) | **Not built.** The class name is reserved; nothing issues it. |
| Pack pinning | **Not in 1.0.** The bundle keeps its `pack` field, always null. |
| Append-only audit history / chain | **Not built**, and not planned in that form — see "History" below. |
| Judge calibration | **Not built.** See Part A. |

### The evidence bundle

Every run can be captured as a **bundle**: one JSON file containing the
fingerprints (SHA-256 hashes) of the exact input files, the full results
and scores, the layer-coverage statement, timestamps, the rulebook's
version and SHA-256, the versions of the harness, Python and the parsing
libraries, and — this matters — an **attestation paragraph** stating
precisely what a signature on the bundle does and does not prove. The
fine print travels inside the evidence, not on our website. Anyone who
makes a bundle can write another paragraph, so `verify` says whether a
bundle's is the text its own release writes. The bundle's top level is
closed: a member the format does not define (a `"certification"`, say)
makes it malformed. Inside its records `verify` checks only what the
format specification lists; anything else there, like every result and
the coverage sentence, is the word of whoever made the bundle.

### The fingerprint and the signature

The bundle is serialized in one canonical way and hashed; that hash is
the bundle's fingerprint. Change any value outside the signature block —
a score, a date — and the fingerprint changes. Writing the same value
another way does not: `27`, `27.0` and `2.7e1` are one number, and the
order of a record's keys and the spaces between them are not part of the
fingerprint (`docs/CANONICALIZATION.md` §2).

A signature is **not** made over the bare fingerprint. It is made over a
small **statement** that records the fingerprint *together with* the
bundle format, the domain, the host a URL run actually fetched, the
pack's name, version and digest (always null in this release), and the
rulebook's version and digest. The verifier compares every one of those values with
the bundle's own, so a signature cannot be moved to another bundle, or
kept over a bundle whose claims changed. The signature block itself holds
exactly five members; anything else in it is refused, because nothing in
it but the statement is signed. The exact bytes, the statement schema,
the six-step verification order and reproducible test vectors are in
`docs/CANONICALIZATION.md`.

Every signature this release makes is **self-signed**: the person or
system that ran the harness signs with its own key (`bellbriar-evidence
keygen` makes one; `--sign-key FILE` or `--sign-key-env NAME` reads it,
never the command line). Anyone with the matching *public* key can then
verify, offline, with the open tool:

```
bellbriar-evidence verify bundle.json --public-key <the signer's public key>
```

`VALID` means exactly this, and `verify` says it in its own words rather
than quoting the bundle (it checks the signature before it compares what
the statement says, so no reason attributes a statement to a key's holder
before the signature shows it is theirs): the statement was signed by the named key; the
bundle body (everything outside the signature block) is unaltered since;
every bound value is the one this bundle claims; and, for a URL run, the
host the bundle records the pages as fetched from is that domain or its
`www.` form — or a host below that site, which the result names — and
every page's own capture record names that host (in a file or `--render`
run, which binds no host, loopback). A host that is not a public site
(`localhost`, `127.0.0.1`, `10.0.0.5`, `100.64.0.1`, `0.0.0.0`) is named
as such, from the same table the capture record uses. The result also
says whether the rulebook is the one the verifier's harness ships: a
bundle made with a custom rulebook, or another release's, is named as
such. The fetch itself is the client's record: no signature attests that
it happened as recorded. It does **not** mean the site is accessible, or
that the results are correct: whoever held the key computed them, and
could have edited them before signing.

A VALID result is only as meaningful as the public key it was checked
against. Check against a key the signer published through a channel you
trust, never against one that arrives with the bundle: anyone can sign
with a key of their own. The harness's own worked example is signed with
a demonstration key that is in no trust path, and `verify` says so in its
result. Two kinds of key mean nothing, and `bellbriar-evidence verify`
answers "could not verify" (exit 2) for them, never VALID: the format
specification's published test key, whose private half is printed there,
and a key no one can hold a private key for: a point of small order,
under which anyone can make a "signature" without one, or no point of the
curve at all. (The library's `bundle.verify_bundle`, which checks the
specification's test vectors, accepts the test key, and its reason says
the signature is evidence of nothing; it refuses the others as the
command does.)

### Three kinds of signature, and which exist

| Class | Who ran the evaluation | What a valid signature proves | What it does NOT prove | Available today |
|---|---|---|---|---|
| **Unsigned** | Anyone | Nothing about provenance | Everything — treat as a scratch note | Yes |
| **Self-signed** (your own key) | Whoever holds the key | That the holder of that key signed exactly this bundle, and its body is unaltered since | That the results are correct or unedited, or that anyone else checked anything | Yes: the only kind this release signs |
| **Attested submission** (service-signed) | The customer's own machine; a signing service would sign the statement after checking a subscription | That an authenticated subscription submitted exactly this bundle, for this domain, fetched host and pack version | That the evaluation was run correctly, or on the inputs it claims — the customer computes those | **Not in 1.0**: no signing service exists; `verify` reads this class as no more than self-signed |
| **Attested execution** (runner-signed) | Our runner would fetch the pages and run the evaluation itself | All of the above, **plus** that we retrieved the listed inputs at the recorded times and ran the harness over exactly that content | WCAG conformance, legal compliance, or any guarantee — no signature proves those | **Not built** |

Keeping these separate is deliberate. Collapsing them — implying we
verified something we merely countersigned — would be the evidence-
system version of overclaiming, and the attestation text in each bundle
names its own class.

### History: what a series of bundles does and does not establish

Each bundle is a dated, signed record of one measurement. A customer who
keeps their bundles holds a series of such records, and each one can be
verified independently at any time. That is the whole claim: each
bundle shows what its signer recorded — what was measured, when, and
against which rules — and that the record has not changed since it was
signed. With self-signed bundles, those are the signer's own words.

What a series does **not** establish today: that no bundle was omitted,
reordered, or signed with a timestamp other than the time of signing.
Nothing in the format links one bundle to another, and a signer can put
any `signed_at` it likes in a statement. Earlier drafts of this guide
described an append-only chain with a store that refused non-extending
bundles; that was never built and is not the right design — a chain in
a store we operate would prove nothing to a reader who does not already
trust us. The honest mechanism is an independent timestamp on each
signature (a public transparency log). The signature block is closed, so
that will be a new version of the format. It is on the roadmap
**[not built]**; until it ships, the timestamp in a statement is the
signer's assertion, and the guide says so.

### Questions a skeptical reader should ask (and our answers)

**"Couldn't the signer back-date a favorable audit?"** Yes. Nothing
technical prevents a signer from writing an earlier `signed_at` into a
statement. What a reader holds is a signed record whose *contents* cannot
be altered after signing; the date inside it is the signer's assertion.
Independent timestamping is the fix, and it is not built yet.

**"Couldn't the customer forge a bundle?"** Yes. Every signature in this
release is self-signed: the machine that runs the harness computes every
finding and score, and whoever holds the key signs them. Anyone can edit
a bundle's results and sign the edited bundle with their own key, and the
signature will be valid. What a valid signature shows is narrow: that the
holder of that key signed exactly this bundle, and that nothing outside
its signature block has changed since. What the statement binding
catches is a bundle changed after it was signed, or a signature moved
from one bundle to another: the signature is genuine and verification
still fails. Only a signing service that checks a subscription **[not
in 1.0]** would say who submitted a bundle, and only attested execution
**[not built]** — a runner fetching the pages and running the evaluation
itself — would make the results themselves something a third party
attests.

**"What if the signing key leaks?"** Every signature names its key by
fingerprint (`key_id`); on a leak the key's owner makes a new pair and
publishes the new public key (`keygen` never overwrites a key without
`--force`, so the old public key survives a mistake). Signatures made
under the old key remain verifiable under it; which of them its owner
made and which the thief made is not decidable from the signatures alone
— another reason independent timestamping is on the roadmap.

**"Does a valid signature mean the site won't be sued?"** No, and the
bundle itself says so. It means that the key's holder signed this bundle
and that it has not changed since: not that the measurement was made as
recorded, nor that its results are correct.
Litigation risk reduction comes from what was measured and fixed, not
from the signature.
