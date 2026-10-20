# Roadmap — what is not built, and what "built" will mean

Everything in items 1 to 8 below, but item 1 (built, struck out) and
the part of item 2 it says is built, is **[not built]** at harness 1.0.1.
Nothing here carries a date, because a date in a public repository is a
promise and we make promises only about what ships. Each item states its
acceptance criteria so that "done" is checkable rather than announced.
When an item ships, it leaves this page and its present-tense description
enters the docs and the rulebook in the same release.

Order below is rough intent, not commitment.

The last section, "Not in 1.0", lists what 1.0 leaves out and where it
reads a page otherwise than a browser or another tool does: each item
with what 1.0 does instead, and when it comes back.

## ~~1. Rendered fetch for `--url`~~ — built for 1.0

Delivered: Playwright-backed capture of the hydrated DOM, default for
`--url` whenever the browser extra is installed, with a loud fallback;
DOM-mutation provenance attributing each client-inserted subtree to the
code responsible, so markup injected by known vendors is reported without
being scored while everything else, cross-origin or not, is scored;
snapshot capture and hashing as the input manifest, which makes URL runs
bundle-able; shadow roots, open and closed (closed ones found through
the DevTools protocol at any depth, and 140 levels into a component's own
closed root, noted when deeper), and scroll-revealed content in the
snapshot; fetched-host verification against `--domain` (the host or
its `www.` form; a subdomain only with `--include-subdomains`, and the
host bound into the signature beside the domain); HTTP status and
redirect recording; waiting for the load, a scroll through the page, and
the DOM and the page's data requests to settle (`--wait-for` for what a
page shows once its data has arrived).

What it did **not** do on its own: add a layer. The rulebook added part
of the rendered layer on top of it (item 2); the interaction layer
remains unexecuted.

## 2. Browser layers: interaction and rendered

*Problem:* the operational half of the pled boilerplate — keyboard
denial, traps, invisible focus, unpausable motion, silent status changes,
contrast — cannot be observed from markup. Ten of the 27 Tier-1 rules
belong to these layers: contrast, which axe-core checks in the browser
today, and nine not built (keyboard access and traps, menus and dialogs,
carousels, focus visibility, error messages, and the two task flows).

*Built at 1.0.0 (rendered, in part):* in `--url` and `--render` runs,
axe-core 4.12.1 (pinned, hash-checked, in an isolated world) checks
contrast, target size and 27 more WCAG A/AA rules Bellbriar does not
implement itself, and Bellbriar checks reflow at 320 CSS pixels and
evaluates each page with what it hides at that width too. Native checks
are to replace axe-core's rule by rule, contrast first, each switched over
only when it matches or beats axe-core on the field corpus.

*Built means, for the rest:* the 13 planned rules in `rulebook.json`
execute under the contracts fixed in `browser_contracts.py` (`tab_walk`,
`modal_contract`, `carousel_pause`, `live_region_capture`,
`contrast_scan` for hover and focus states); each has a passing and a
failing fixture; the
coverage banner's list of unexecuted layers shrinks accordingly; the
Tier-1 coverage counter printed by every report reflects the new
denominator automatically. Task-flow verdicts (`bb-flow-ecom`,
`bb-flow-leadgen`) are all-or-nothing over a complete process.

*The accessibility-tree layer (not built):* reading the roles, states and
names the browser's accessibility tree exposes, rather than computing
them from markup. *Built means:* in a rendered run, every name rule's
verdict rests on the name Chromium computes, the static computation is
kept only for file runs, and the two are compared on the field corpus so
that a difference is a known one.

## 3. Judge calibration

*Problem:* no judge provider has any measured agreement with human
experts, so 1.0 runs no judge at all (no `--judge`), and the three judged
rules are reported as not executed.

*Built means:* a **public development set** — small, built from public
pages, versioned in this repository — with a script that reproduces its
agreement figure for any provider; a **private held-out test set**,
built from real audits with consent and anonymization, never published,
on which the reported figure is measured; a labeling protocol with at
least two raters and reported inter-rater agreement; a pinned reference
configuration (model, temperature, prompt hash) published with every
figure; the hosted judge returning a `calibration_id` that names a
published study, which is the only condition under which `calibrated`
may be `true`. Until all of that exists, no judged number appears in
any published material.

## 4. Production signing service

*Problem:* every signature in 1.0 is self-signed. `attested-submission`
is a reserved class name that nothing issues; the reference signing
service that demonstrates its contract (`tools/reference_signer.py`, not
part of the installed package) has no TLS, key rotation, billing, replay
windows or audit storage, and 1.0 has no `--sign-url`.

*Built means:* a hosted signer implementing the `/v1/sign` contract with
those properties; a production key generated offline (PREPUBLISH.md
item 8) whose public half is published at a stable URL and in this
repository; documented rotation; `--sign-url` and its client back in the
package, with the attestation text for the class. Only then can a
customer obtain a signature of that class.

## 5. Independent timestamping (replaces the "chain" idea)

*Problem:* a statement's `signed_at` is the signer's assertion; nothing
prevents back-dating, and nothing links one bundle to the next. An
append-only chain in a Bellbriar-operated store was considered and
rejected: it would prove nothing to a reader who does not already trust
Bellbriar.

*Built means:* each signed statement is recorded in a public transparency
log, and the inclusion proof travels with the bundle. The signature block
is closed (CANONICALIZATION §3, §10), so that is a new version of the
format. A verifier with the log's public key can then establish that the
statement existed no later than the log entry time, independently of us.

## 6. Hosted runner (attested execution)

*Problem:* the strongest attestation class — "we fetched these inputs and
ran the evaluation ourselves" — has a reserved class name and nothing
that issues it.

*Built means:* an isolated runner that fetches the listed inputs at
recorded times, executes the harness, and signs its own bundle with
`attestation_class: attested-execution`; the attestation text gains the
corresponding sentence; the availability column in the guide flips.
This depends on 4 and benefits from 5.

## 7. Complaint-tagging corpus

*Problem:* Tier weights (×5 / ×2 / ×1) are provisional judgments about
what plaintiff firms plead, not counts.

*Built means:* a dataset of public federal complaints tagged by success
criterion and barrier type (from public dockets; facts extracted, no
complaint text reproduced), with the tiering derived from frequency and
the rulebook version bumped when weights change. Demand letters supplied
by customers extend it privately.

## 8. Published benchmark

*Problem:* none exists. Every number that appears anywhere must be
reproducible.

*Built means:* a frozen, versioned, held-out prompt corpus in the
repository; a deterministic-only headline ("agents alone X%, with the
pack Y%") that anyone reproduces to the digit with the pinned harness and
rulebook versions; the reference run published beside instructions for
your run; judged figures, if any, beside the headline and never inside
it, under item 3's policy.

## Not in 1.0

What 1.0 leaves out, or does otherwise than a browser, a standard or
another tool does, so that none of it is lost: each item says what 1.0
does instead and when it comes back, and keeps its number (L1, L2, …)
from the list the release was planned with. An item leaves this list
when it ships, and its present-tense description enters the docs.

- **L1.** Native versions of every axe-core check, so Bellbriar owns every
  verdict. *In 1.0:* Runs a pinned axe-core inside Bellbriar for each WCAG
  A/AA rule it lacks, so customers already use one tool. *Comes back:* Rule
  by rule after 1.0, contrast first. Switch axe's rule off only when the
  native one matches or beats it on the field corpus. Until then, update the
  pinned axe-core each minor release.
- **L2.** Remote signing: `--sign-url`, `--api-key`, the reference server,
  attested-submission bundles. *In 1.0:* Self-signed bundles only. *Comes
  back:* With the production signing service (ROADMAP 4). Bring back P4-07,
  P3-11 and the signing-key ceremony (PREPUBLISH 8).
- **L3.** Packs: `--pack`, `--pack-key`, pack pinning. *In 1.0:* No pack
  recorded; the bundle's `pack` field stays, empty. *Comes back:* When the
  WCAG pack is released. Bring back P4-04 and the pack-key ceremony.
- **L4.** The judge: `--judge` and the adequacy track. *In 1.0:* No adequacy
  grading; the bundle's `judged` field stays, empty. *Comes back:* After
  calibration (ROADMAP 3). Bring back P5-05 to P5-08.
- **L5.** The attested-submission sentences in the attestation text. *In
  1.0:* 1.0 bundles describe self-signed signatures; the worked example is
  re-signed as self-signed. *Comes back:* With L2. No format change needed:
  the verifier doesn't validate this text (CANONICALIZATION §5.1).
- **L6.** Placeholder-only form fields as a FAIL. *In 1.0:* A review, pled
  in complaints; `--strict` gates it. *Comes back:* ACT e086e5 notes such a
  field still fails 3.3.2 unless other visible text labels it, which markup
  can't settle. Make it a heuristic FAIL if the field corpus shows most have
  no such text.
- **L7.** The same-day benchmark and launch announcement (PREPUBLISH 11,
  waived). *In 1.0:* Listed on PyPI without an announcement. *Comes back:*
  When the benchmark (ROADMAP 8) is ready; that becomes the launch.
- **L8.** Bypass blocks: visible top bars before a skip link pass; a link to
  the top counts as neutral for G124. *In 1.0:* Kept as is; documented
  limits. *Comes back:* If field reports show top bars hiding real failures.
  Option: count them again, skipping off-canvas menus.
- **L9.** Sandbox fallback when Chromium's sandbox can't start. *In 1.0:*
  Falls back and records it; `--require-sandbox` refuses instead. The
  container cannot keep it on under Docker's default seccomp profile (L81).
  *Comes back:* Revisit making refusal the default once most runs use the
  container.
- **L10.** Rendered checks in file runs without a browser. *In 1.0:*
  Reported as not evaluated; axe-core needs `--render` or `--url`. *Comes
  back:* Consider making `--render` the default whenever a browser is
  installed.
- **L11.** Interaction layer: keyboard walks, traps, focus visibility, menu
  and modal behavior. *In 1.0:* Reported as not evaluated, with the Tier-1
  denominator. *Comes back:* ROADMAP 2. axe-core doesn't automate these
  either, so this is where Bellbriar can lead.
- **L12.** Timestamping and the hosted runner (attested execution). *In
  1.0:* Not built; the class name stays reserved. *Comes back:* ROADMAP 5
  and 6, after L2.
- **L13.** Header-token credentials for protected previews (N7). *In 1.0:*
  HTTP Basic and query tokens only. *Comes back:* When a customer's preview
  needs a header token.
- **L14.** Litigation support: find, fix, retest, and proof a record is
  complete (N9). *In 1.0:* Not in 1.0. *Comes back:* A product built on 1.0
  bundles.
- **L15.** Tier weights from complaint data (ROADMAP 7). *In 1.0:* Weights
  stay provisional judgments. *Comes back:* When the complaint-tagging
  corpus exists; bump the rulebook then.
- **L17.** Bundle-format changes after the freeze. *In 1.0:*
  bellbriar-evidence/1 is frozen at 1.0. *Comes back:* Any later change
  takes bellbriar-evidence/2; wanted changes are collected for it.
- **L18.** Conveniences: a config file, a single `bellbriar` command,
  branded client reports, a hosted scanner. *In 1.0:* Three commands and
  flags. *Comes back:* 1.x, by customer demand; branded reports fit the
  wholesale tier.
- **L23.** File runs read the page's own &lt;style&gt; elements, not linked
  stylesheets or @media rules, so an aria-hidden container hidden only there
  FAILs. *In 1.0:* A review where the container's own framework class or the
  page's &lt;style&gt; hides it; a rendered run decides. *Comes back:* A1
  shipped --render as an option; making it the default is L10.
- **L28.** A bundle for a run where a rule errored or a page could not be
  read. *In 1.0:* No bundle; exit 2. Both reports list each error and mark
  the run incomplete. *Comes back:* With bellbriar-evidence/2 (L17): record
  errored rules, unread pages and an errored rule's partial findings.
- **L29.** Encoding gaps against Chromium: its guesses of legacy encodings
  (Shift_JIS, windows-1257, ISO-8859-4) for undeclared pages; its UTF-8
  detector near the threshold and on overlong sequences; ISO-2022-JP
  resynchronising after a bad byte; text before a late meta over HTTP; a
  file whose only non-ASCII characters sit in its markup. *In 1.0:*
  Undeclared pages read as windows-1252 (text garbled); a measured UTF-8
  rule for files; the whole page decoded with the meta's encoding. All
  stated in the guide. *Comes back:* If field pages need it: port Chromium's
  detector (CED) and an ISO-2022-JP decoder of our own.
- **L30.** Parsing through JustHTML's private internals: three engine
  methods hooked and six module constants patched (select scope, search,
  template parent, element budget, CDATA). *In 1.0:* JustHTML pinned to
  3.13.0 (L142); the WPT and Chromium tree tests fail on any change. *Comes
  back:* Before any JustHTML upgrade; offer the hooks upstream so the pin
  can loosen.
- **L31.** Trees unlike Chromium's: 6 of 1,605 WPT documents (a lone &lt;?,
  NUL or U+FFFD before &lt;frameset&gt;, &lt;command&gt;, one
  misnested-formatting case), a &lt;/p&gt; inside a &lt;select&gt;, and the
  512-level depth limit applied after parsing. *In 1.0:* As is: no rule's
  input moves in those cases; past 512 levels an implied &lt;tbody&gt;, an
  adopted element or what follows a template opened there can land one level
  off. *Comes back:* If a field page shows one, or JustHTML exposes a hook
  to cap depth while parsing.
- **L32.** XHTML that is not well-formed: Chromium shows the part it read
  under an error; that part is not evaluated. *In 1.0:* Reported as not
  evaluated, with the parser's line and column. *Comes back:* If customers
  serve broken XHTML: evaluate the part shown, with the XML error as a
  finding.
- **L33.** Shadow-root styles beyond whole :host, :host(&lt;compound&gt;)
  and ::slotted(&lt;compound&gt;) selectors: :host .x, :host-context() and
  ::part() are not applied in file runs. *In 1.0:* Ignored; a rendered run
  reads what the browser computed. *Comes back:* If a component library
  hides content that way in file runs; Part P's rendered builds (A1) cover
  most cases.
- **L35.** A run of many pages (A3) captures them one at a time. *In 1.0:*
  In order, each with its own --render-deadline; 50 pages by default. *Comes
  back:* When runs of 50+ pages are common: several pages at once, one
  browser with a context each.
- **L36.** `--render` serves files only: a client-side route with no file of
  its own (an SPA's /about) is not served, there is no index.html fallback,
  and nothing under a name starting with a dot (.well-known) is served. *In
  1.0:* Each page file is evaluated; a route needs its own prerendered file,
  or a `--url` run against a preview. *Comes back:* If customers' SPAs need
  it: a fallback option (index.html for unknown paths) and a list of routes
  to render.
- **L37.** Locators are checked in Chromium only: a shadow root's top-level
  step (`:host > x`) is untested in Firefox and Safari, and a step into a
  closed root needs the developer tools. *In 1.0:* The guide gives a
  resolver and the developer-tools step; 101,971 elements resolved in
  Chromium 141. *Comes back:* When a customer works in Firefox or Safari:
  check the selectors there, and write top-level steps without :host if
  needed.
- **L38.** An element more than 100 steps below its anchors, over all its
  trees, gets no locator. *In 1.0:* Its finding gives its line; the deepest
  field page nests 20 levels. *Comes back:* If field pages need it: anchor
  at an ancestor whose name is unique in its tree.
- **L40.** A page served as XML is read from the server's bytes in a
  rendered run too: content its scripts add is not evaluated, and
  `--require-render` refuses it. *In 1.0:* Read with the XML parser, as a
  file run reads it; the capture record and the console say so. *Comes
  back:* If customers serve scripted XHTML: capture with XMLSerializer and
  read the capture with the XML reader.
- **L41.** XHTML entity limits are approximate: libxml2 charges each
  reference a fixed cost and compares with the part of the page read so far,
  so a page with many short or nested references, or an early large
  expansion, is an error to Chromium yet evaluated here. *In 1.0:* libxml2's
  limits by characters: a million or five times the page, and 39 entities
  deep; stated in the guide. *Comes back:* If such pages appear: model
  libxml2's accounting exactly.
- **L42.** Frames: axe-core's frame-focusable-content, and anything inside
  an iframe, which is a document of its own. *In 1.0:* Not run; the capture
  and axe-core read the page's own document only. *Comes back:* When frames
  matter to customers: capture each same-origin frame as a page of its own,
  and run axe-core with iframes.
- **L43.** Contrast in hover and focus states, text spacing beyond inline
  styles, and focus visibility. *In 1.0:* Not checked; every coverage note
  says so. *Comes back:* States and focus with the interaction layer (L11);
  text spacing with a pass that applies the 1.4.12 spacing.
- **L44.** The narrow record shows what stylesheets, and a script's class,
  style or hidden changes, show at 320 px; a script's other changes there
  are not in the capture. *In 1.0:* An element the page removes is not
  rendered there; a finding about anything the page changed is a minor
  review; content built only at that width is not evaluated. *Comes back:*
  If phone-only failures go unreported: a real second snapshot at 320 px,
  which needs bellbriar-evidence/2 (L17).
- **L45.** Reflow: content a page cuts off with overflow-x hidden or clip is
  not detected; 1.4.4 Resize Text is not checked; at most 50 overflowing
  elements are named. *In 1.0:* A clipped page passes, as the guide says;
  past 50, the rest are covered by the page-level FAIL. *Comes back:* With a
  200% text-zoom pass and a check for content past the edge that no
  scrolling reaches.
- **L46.** Target size (WCAG 2.2) is review-only and noisy: 2,555 findings
  on the 83 field pages. *In 1.0:* Reported for review against the 2.1 AA
  target; never gates, not even with --strict. *Comes back:* When customers
  target WCAG 2.2: a --target wcag22 that counts 2.2 rules (the report has
  grouped repeated findings since R3, A7).
- **L47.** axe-core is not run on pages of more than 20,000 elements, and a
  part of its run that started cannot be stopped, so a slow machine can
  still pass the render deadline. *In 1.0:* Its rules are not evaluated
  there, and the capture says why; no part starts after 30 s. *Comes back:*
  If large pages are common: run axe-core on the page in slices (its include
  and exclude context).
- **L48.** What axe-core cannot decide is a minor review: 793 contrast
  results on the field pages (text over images and gradients). *In 1.0:*
  Minor reviews; --strict never gates them. *Comes back:* With native
  contrast (L1): sample the pixels behind the text so fewer stay undecided.
- **L49.** An unnamed combobox wrapping its text field (the ARIA 1.1
  pattern), and a combobox's unnamed popup listbox: ACT e086e5 applies to
  both by role. *In 1.0:* Minor reviews, as axe-core exempts both; the guide
  says so. *Comes back:* If W3C adds examples, or screen-reader tests show
  users miss them: make them FAILs.
- **L50.** axe-core checks the page as it is when it starts: elements added
  after that, before the capture, are in the snapshot but not checked by it,
  so a page that keeps re-creating content keeps it from axe-core. *In 1.0:*
  Counted in the capture record (added) and its notes; the static rules read
  them. *Comes back:* Run axe-core again on what was added since it started,
  up to a cap, before the capture.
- **L51.** A page that changes itself when narrowed turns what only the
  narrow record shows into reviews, legitimately or to hide a failure. *In
  1.0:* Reported as minor reviews, each saying why. *Comes back:* With L44's
  second snapshot.
- **L52.** Closed shadow roots past the protocol search (5,000 hosts or 140
  levels deep) are not given to axe-core. *In 1.0:* On such a page,
  axe-core's rules that found no failure are not evaluated, and the capture
  says why. *Comes back:* If real pages hit it: hand axe-core the closed
  roots the instrumentation itself recorded.
- **L54.** A rendered page's requested_url keeps the spelling the operator
  typed, while final_url has Chromium's percent-encoded one; the console's
  "same page" note uses the typed spelling. *In 1.0:* One route can read two
  ways in one record (\#/a b as \#REDACTED, then \#/a%20b), and two
  different routes can print alike in the console. *Comes back:* 1.1: write
  requested_url and the console labels in the browser's spelling before
  redacting.
- **L55.** A server-mode run records a shorthand IPv4 host as written (--url
  http://0x7f.1/ binds host 0x7f.1), and a hand-made bundle's 127..1 reads
  as loopback. *In 1.0:* The class and note are right, but CANONICALIZATION
  §5 says an IPv4 host is four decimal numbers, and browsers refuse 127..1.
  *Comes back:* 1.1: record shorthand IPv4 hosts in their four-number form;
  read an empty part as no address.
- **L56.** A proxy set by PAC or WPAD is invisible to the check that decides
  whether a rendered capture connected to the page's own host. *In 1.0:*
  Where Chromium uses one, the proxy's address could be recorded as the
  page's, by address (not reproduced: headless Chromium ignored auto-proxy
  here). *Comes back:* 1.1: record the class by name whenever proxy
  auto-config is set.
- **L57.** An empty URL parameter (?name=) keeps its name unless the name
  looks like a credential (8 or more characters, not a plain lowercase
  word). *In 1.0:* A padded Base64 token made only of lowercase letters
  would be recorded; ordinary empty parameters (?q=) keep their names.
  *Comes back:* If real tokens show up: treat every empty parameter as all
  value.
- **L58.** --sign-key, --sign-key-env and the tools' --private-key never
  repeat what they were given in a message; only the default variable name
  is named. *In 1.0:* A typo in a key file's path or a custom variable's
  name is not shown back; the command line still shows it. *Comes back:*
  Keep: a key typed there by mistake would otherwise reach the CI log.
- **L61.** Lint cannot see a role or key handler an Angular component sets
  in its host: metadata, so a click handler in such a component's template
  (ng-bootstrap's rating stars) is an ERROR. *In 1.0:* Needs the component's
  metadata read beside its template. *Comes back:* Read host: bindings in
  the same file; until then, suppress with a note.
- **L62.** Lint follows a wrapper's components only through imports it can
  resolve: auto-imported components (Nuxt, unplugin), ones passed in props,
  and package components (Radix menu items) keep the wrapper's ERROR. *In
  1.0:* Needs a framework's auto-import registry or type information. *Comes
  back:* Read Nuxt's components.d.ts and unplugin-vue-components'
  declarations.
- **L64.** The lint scan runs git to read .gitignore (hardened: no transport
  or lazy fetch, no fsmonitor, git only from absolute PATH folders, a time
  budget, a note when git refuses). *In 1.0:* A Python reader must match git
  exactly: negation, anchoring, and tracked files, which live in the index.
  *Comes back:* Replace git with a reader of .gitignore, info/exclude and
  the index, tested against git.
- **L65.** bb-skip-link follows H69 (a heading must open the content); W3C's
  proposed ACT rule cf77f2 passes a page with any heading past the blocks,
  so a page whose only bypass is a later heading FAILs here. *In 1.0:* A
  deliberate, documented choice for a heuristic Tier-1 rule; R2 added the
  landmarks cf77f2 accepts. *Comes back:* Decide with field data whether a
  later heading should make it a review.
- **L66.** bb-aria-required-children FAILs a feed, row or suggestion that
  owns nothing (axe-core's behavior; it reviews other empty roles); W3C's
  ACT rule bc4a75 (proposed) passes an element that owns nothing. *In 1.0:*
  The rule is now heuristic, and its note says how it differs. *Comes back:*
  Make an empty feed, row or suggestion a review.
- **L67.** bb-widget-name FAILs an unnamed treeitem, which axe-core classes
  as a best practice. *In 1.0:* W3C's failure F68 covers controls, and a
  treeitem is one; the note says so. *Comes back:* Revisit with the
  accessibility-tree layer.
- **L68.** tests/test_citations.py checks that a cited ACT rule requires a
  criterion the rule cites, not that it tests the same element (a
  button-name ACT rule cited for links would pass). *In 1.0:* Semantic fit
  was reviewed by hand in R2. *Comes back:* Record each citation's
  applicability (elements, roles) and test it.
- **L69.** bl-outline-none-class flags outline-none on elements that never
  take focus, such as a command item whose focus stays in the search field.
  *In 1.0:* The rule has always read every element; telling which take focus
  from source is uncertain. *Comes back:* Warn instead of erring on elements
  with no tabindex that are not controls.
- **L70.** Lint follows relative imports and tsconfig alias targets that
  climb out of the project (a monorepo's ../packages), reading those files
  only to decide N26. *In 1.0:* Monorepos need it; absolute, drive and UNC
  targets are refused, and only regular files under 2 MB are read. *Comes
  back:* Limit to the git work tree, with an option for monorepos.
- **L71.** A click-handling div around content passed in (a slot, children)
  is a warning even when the div is itself the control (elk's StatusLink:
  focusable, Enter-key handler, no role). *In 1.0:* Never an error on a
  guess: the same shape is shoelace's carousel, whose handler only cancels
  clicks while dragging. *Comes back:* Read the handler's body, or the
  component's tests, to tell the two apart.
- **L72.** For a heuristic rule, which cited criteria a probable failure
  concerns is a judgment: tests/test_citations.py checks only that each is
  level A or AA (for an sc rule, also that W3C names a failure of each). *In
  1.0:* No W3C source says which criteria a probable failure concerns.
  *Comes back:* Check each heuristic rule's criteria by hand in the R5
  reviews.
- **L73.** bb-skip-link's landmark fallback takes the first content past the
  blocks as content that does not repeat; W3C's proposed ACT rule b40fd1
  asks what repeats across pages, which one page cannot show. *In 1.0:* The
  fallback only turns a FAIL into a review, and only for a landmark the
  content starts in. *Comes back:* Compare the pages of a site run before
  accepting a landmark.
- **L74.** In a file run nothing fails an unnamed &lt;summary&gt; or
  &lt;object&gt; (their name rules run in the browser); bb-aria-ref, which
  failed one with a broken aria-labelledby, now only reports the reference.
  *In 1.0:* One defect, one failure: in a browser run the name rule fails
  it, and bb-aria-ref failed every other unnamed element a second time.
  *Comes back:* Check summary and object names on the markup too.
- **L75.** An empty element whose click closes something (a modal or drawer
  backdrop: shoelace's overlay, Alpine's full-screen slide-over backdrop) is
  a bl-div-click error in every framework; Escape or a close button usually
  does the same, which the linter cannot see. *In 1.0:* The same markup is a
  real failure when it is the only control (a close icon drawn in CSS); R1
  already erred on React backdrops. *Comes back:* Warn for an empty element
  whose handler closes something, or that is named overlay, backdrop or
  scrim.
- **L76.** A URL dropped as the same page as another (it differs only in its
  fragment and was captured the same) is named only on the console, not in
  the reports. *In 1.0:* The console names each; the report's sitemap
  sentence says a page listed again with another fragment is evaluated once.
  *Comes back:* Add a field listing them to the JSON report
  (bellbriar-report/1 may add fields) and a line to the HTML report.
- **L77.** A guidance "after" example can draw another rule's review (a
  vertical list of links draws bb-target-size reviews); the tests check
  "after" examples only for FAILs and for their own rule. *In 1.0:* The
  rules reference says other rules may still list an "after" example for
  review. *Comes back:* Make each "after" example clean of every rule, in
  the browser too, and test that.
- **L78.** Fingerprints change with the page's recorded path (a folder
  evaluated from another working directory, a re-run of a saved snapshot),
  with per-request tokens other than nonce and hidden inputs' values (a
  signed image address in an element or its first 20 descendants), and with
  --render's port when another program holds it. *In 1.0:* REPORT.md says
  exactly what a fingerprint reads and when it changes; --render takes a
  port from the folder's name and says when it cannot. *Comes back:* With
  A10's baseline in use: let a baseline map old paths to new ones, and leave
  signed query values out of identities if customers hit them.
- **L81.** In the container, Chromium runs without its sandbox: Docker's
  default seccomp profile refuses the user namespaces it needs. *In 1.0:*
  Each capture records it; `--require-sandbox` refuses such a run; the image
  runs as an ordinary user; the README and the Action's README say so; the
  repository and the Action ship Playwright's seccomp profile
  (`docker/seccomp_profile.json`, and the Action's copy beside its
  `action.yml`), which the README gives with `--security-opt` and the
  Action's `sandbox: required` passes (S5-2); CI's image job shows the
  sandbox starting under the profile on x86-64 and ARM64 (October 17).
  *Comes back:* L9 decides the default: CI's image job, which lifts Ubuntu
  24.04's restriction on user namespaces, has shown the sandbox starting
  under the profile (October 17).
- **L84.** The settle step does not watch closed shadow roots or frames: a
  page that changes only inside one can look settled sooner. *In 1.0:* The
  guide says so. *Comes back:* Watch same-origin frames; note when a closed
  root's host changes.
- **L85.** A finding can read as new with nothing changed: pages that share
  a recorded path renumber when one is added or removed, and k counts a
  rule's findings across owners. *In 1.0:* REPORT.md says both; the gate
  errs toward failing and never hides a FAIL. *Comes back:* If baseline
  users hit it: number same-path pages by a stable key, and count k per
  owner.
- **L86.** A baseline is trusted as given: an edited baseline report can
  list a new failure as an old one. *In 1.0:* The bundle records the
  baseline's SHA-256; the README says to review baseline changes like code.
  *Comes back:* Sign baselines, or have verify check the recorded digest
  against a signed report.
- **L87.** The repository guard's limits: raw binary over 1 KiB is tried
  only at 32-byte steps; golden sets are found by English names, so
  `docs/CALIBRATION.md` or `tests/golden/` fails CI too; spellings its
  docstring does not list are not read. *In 1.0:* Its docstring says exactly
  what it reads; `.gitignore` is the second line of defense. *Comes back:*
  If a key gets past it, or a name rule gets in the way.
- **L89.** The console escapes control and format characters (the zero-width
  joiners aside, so a name with one prints like one without: R5A-16), the
  start of CI command lines, and the second "\#" of every "\#\#" anywhere in
  a line (R5A-2: CI runners read \#\#\[, \#\#vso\[ and \#\#teamcity\[
  anywhere): an escaped name cannot be pasted back, and a name that spells
  an escape reads like one. *In 1.0:* Reports and bundles keep the text as
  it is. *Comes back:* If it confuses users: quote names, or add a
  raw-output option.
- **L90.** A relative URL outside the attributes HTML defines for URLs
  (data-href="/x?t=…", the page's text) is quoted in a snippet as the page
  has it. *In 1.0:* URL attributes and absolute URLs are redacted, and a URL
  run's own secrets wherever a finding quotes them (H6-1); the docs say what
  is not. *Comes back:* Redact query values in any attribute value or text
  that reads as a relative URL with a query.
- **L91.** A public key file written before 1.0 (the key alone), renamed
  away from .pub, reads as a private key: signing with it signs with a key
  anyone can derive. *In 1.0:* keygen marks both halves; a .pub file, a
  public-marked file or a link to a .pub file never signs; verify names a
  bundle signed this way. *Comes back:* In a later release, warn on unmarked
  key files, then refuse them.
- **L94.** The 256 MiB cap bounds a bundle file, not the memory parsing it
  takes (21 MB of {} reached about 1 GB). *In 1.0:* bellbriar-eval refuses
  to write a bundle over the cap. *Comes back:* Count values while parsing
  and stop past a limit, or lower the cap.
- **L95.** Vendor markup counts toward which rules apply: a rule that
  applies to a vendor's elements, and fails only there, counts as passed, so
  vendor markup can raise a page's pass rate (22/22 against 17/17 in the
  audit); a finding about the page (a skip link, the headings) counts vendor
  blocks too, so it can lower one as well. *In 1.0:* README, METHODOLOGY,
  the HTML report and the attestation text say so; a finding that rests on a
  vendor's skip link is the site's (R5I-8). *Comes back:* Score a rule as
  applicable only where it applies to the site's own markup.
- **L98.** A file run reads content-visibility and display only from the
  style attribute: a &lt;span hidden="until-found"&gt; a stylesheet makes a
  block, or a block a stylesheet gives content-visibility:hidden, still
  names its link from what it skips. *In 1.0:* A rendered run reads what the
  capture recorded, as Chromium renders it; the README says a file run reads
  display and visibility. *Comes back:* Read content-visibility and display
  values from the page's own &lt;style&gt; (PageStyles).
- **L99.** @supports in a page's own &lt;style&gt; is settled by a
  property's name and display's value only; any other test (a value,
  selector()) is a condition: a show inside counts for names but not for a
  skip link's stand-in control, and a hide inside never counts. *In 1.0:*
  The README says so; a rendered run reads what Chromium applied. *Comes
  back:* Settle values as Chromium 141 does: a table of what CSS.supports
  accepts, made as tools/make_css_properties.py makes the property list.
- **L100.** A closed &lt;dialog&gt; or popover that the page displays anyway
  (an author display beats the browser's display:none) names nothing in
  Chromium 141, which leaves closed dialogs and popovers out of names
  whatever their CSS; the harness reads their text. *In 1.0:* Rare: it needs
  a closed dialog or popover inside a link, a button or a label, shown by
  the page's own CSS. *Comes back:* Leave a closed &lt;dialog&gt; and a
  closed popover out of names in both readers, after measuring an open
  popover's case in Chromium.
- **L101.** Name from content: Chromium 141 reads no text from an &lt;rt&gt;
  (ruby's annotation), a &lt;video&gt;'s or &lt;audio&gt;'s fallback (a
  label there names nothing either), or a role=combobox, listbox,
  progressbar or separator that holds only text, inside a link or a button,
  and reads an &lt;input&gt;'s, a &lt;meter&gt;'s or a &lt;progress&gt;'s
  value; the harness reads their content, and no value (an &lt;output&gt;,
  MathML, an &lt;iframe&gt;'s and an &lt;object&gt;'s fallback and a
  &lt;fieldset&gt; are read as Chromium reads them since R6 round 9: L92,
  L115); and through an aria-labelledby that points at the label around a
  control, the harness reads the control's own value too, which Chromium
  leaves out (both give a name); through aria-labelledby, Chromium reads a
  &lt;details&gt; with no &lt;summary&gt; by its default summary's
  "Details", which the harness does not (R6O round 8). *In 1.0:* None needed
  for whether a name exists but in contrived cases: a link whose only text
  is in one of these passes (Chromium names it nothing), and one holding
  only a text input fails (Chromium names it by its value). *Comes back:*
  Measure each in Chromium and read them as it does, in both readers; R6 or
  1.x.
- **L103.** Display corner cases the runs do not compute: display:contents
  on an &lt;svg&gt;, &lt;canvas&gt;, &lt;img&gt;, &lt;input&gt;,
  &lt;select&gt; or &lt;textarea&gt; computes none in Chromium 141, but the
  file run reads their title or fallback; Chromium names nothing by a
  drawing's &lt;tspan&gt; made visible again inside invisible &lt;text&gt;,
  which a rendered run reads (measured); a display only known later (var())
  is read as one that skips content, which Chromium does not where the
  variable is undefined; and a visibility only known later is read as the
  parent's where it decides a name, so text a hidden ancestor's custom
  property shows again names nothing (R5S-9). *In 1.0:* Contrived markup. A
  file run reads a drawing's parts' content-visibility from their style
  attribute; review by hand a drawing that names something through
  aria-labelledby. *Comes back:* 1.x: read contents as none on those
  elements; read the custom properties style attributes set; follow Chromium
  on a drawing's text made visible again.
- **L105.** The repo guard misses a 32-byte key split over adjacent string
  literals ("…" "…", or "…" + "…" over two lines) or over a backslash line
  continuation. *In 1.0:* Code that signs reads a key file, which the guard
  finds; review by hand any key written into code. *Comes back:* 1.x: join
  adjacent literals and continuations before reading strings.
- **L107.** Text made visible again (visibility:visible) inside invisible
  content: the runs read it into a name wherever it is, as HTML's name from
  content has it. Through aria-labelledby, Chromium 141 reads it only in
  some of a drawing's patterns (a &lt;text&gt; visible again inside an
  invisible &lt;g&gt;), not in HTML, MathML, a drawing's &lt;tspan&gt; or a
  drawing link's text, nor in a drawing a control holds (a &lt;text&gt;
  visible again inside an invisible &lt;g&gt; or &lt;defs&gt;, R6E-5):
  &lt;math id="m"&gt;&lt;mrow style="visibility:hidden"&gt;&lt;mtext
  style="visibility:visible"&gt;Save&lt;/mtext&gt;&lt;/mrow&gt;&lt;/math&gt;
  names a button labelled by it nothing there, "Save" in the runs (R6C-7,
  measured over 40 cases). The runs read more text than Chromium there,
  never less. *In 1.0:* Review by hand a control named through
  aria-labelledby by text inside invisible content. *Comes back:* 1.x:
  follow Chromium's measured patterns through aria-labelledby.
- **L108.** A drawing's parts that are not rendered: a rendered run reads
  them into names as Chromium 141 does (measured over some 390 cases of
  drawings and MathML, R6C-3), and a file run leaves out, as its markup
  shows them, a part whose own requiredExtensions fail, an element Chromium
  does not know (an &lt;rdf:RDF&gt; in an HTML document), what a
  &lt;metadata&gt;, an animation's element, a &lt;view&gt; or a &lt;use&gt;
  holds, a filter primitive outside a &lt;filter&gt;, a &lt;tspan&gt;
  outside a &lt;text&gt; and a &lt;g&gt; in one (R6M-7, round 7). A file run
  still reads text Chromium leaves out of a name: what a &lt;switch&gt;
  passes over (a &lt;g&gt;, or a part with a systemLanguage), a part with a
  systemLanguage inside a &lt;defs&gt; or a &lt;symbol&gt;, an
  &lt;rdf:RDF&gt; in XHTML (in RDF's namespace), what a shape or a gradient
  holds inside a &lt;g&gt; or what a &lt;g&gt; of it holds (R6E-4). Where an
  aria-labelledby target is not rendered (display:none), a rendered run
  reads that last there too (round 7). A rendered run reads a part whose
  conditions fail inside another part that is not rendered (a &lt;tspan&gt;
  of the &lt;text&gt; a gradient holds). Either run reads text loose in a
  &lt;g&gt;, and all of a &lt;switch&gt; inside a &lt;g&gt; with
  display:none; Chromium reads neither. The runs read more text than
  Chromium there, never less. *In 1.0:* Evaluate pages with drawings with
  --url or --render; review by hand a drawing that names a control through
  aria-labelledby or is a link's only content. *Comes back:* 1.x: read a
  drawing's parts from markup as the rendered run reads them.
- **L109.** A --http-user password that holds a spelling of white space just
  after its own white space (a %20b, x &amp;nbsp;y) may be missed in text
  that spells that white space so too: each run of white space is read whole
  and gives back none of what it took, which keeps a search linear on any
  page (R6E-7). The docs say so. *In 1.0:* Use a long random password, as
  the docs advise. *Comes back:* 1.x: read such a password's white space one
  character at a time where its own characters spell white space.
- **L112.** A drawing's display and visibility attributes (display="none",
  as Adobe Illustrator writes a hidden layer; visibility="hidden") are not
  read from markup, in either run: a link they hide is checked for its name,
  and its focus failed inside aria-hidden content, where Chromium 141 leaves
  it out of the tree and gives it no focus (measured). The style attribute's
  display and visibility, and the rules', are read. *In 1.0:* A false FAIL,
  which is visible; links in a hidden layer are rare. *Comes back:* 1.x:
  read them as CSS's presentation hints, below every author rule.
- **L113.** What a drawing's &lt;use&gt; copies is not checked: Chromium 141
  puts the copy in its accessibility tree, where it takes focus if the
  &lt;use&gt; is rendered, so an unnamed link a &lt;use&gt; copies from a
  &lt;symbol&gt;, or one it copies into aria-hidden content, is missed
  (measured). *In 1.0:* Links inside a &lt;symbol&gt; or another &lt;use&gt;
  target are rare. *Comes back:* 1.x: read a &lt;use&gt;'s copy as Chromium
  builds it.
- **L114.** A rendered run names two of a drawing's patterns otherwise than
  Chromium 141 (measured): it reads what an &lt;a&gt; in a &lt;switch&gt;
  holds after its first element, which Chromium neither renders nor reads (a
  false PASS where that is all of the name), and nothing of the HTML in a
  &lt;foreignObject&gt; a &lt;switch&gt; passes over, or that a box that
  never paints (a &lt;defs&gt;, a mask, a &lt;g&gt; with display:none) holds
  as a link's own child, which Chromium reads (a false FAIL, in a file run
  too: R6K-10, R6M-8). *In 1.0:* Contrived drawings. *Comes back:* 1.x:
  model both.
- **L116.** An @property Chromium 141 drops for a value (an initial-value
  its syntax does not take, a syntax it does not read) is read as kept where
  the run decides which @namespace rules count, so an @namespace after it is
  not read, where Chromium reads it (measured: R6J-6). Every other block
  at-rule Chromium drops for its prelude or what it holds is read as
  dropped. *In 1.0:* Contrived: an invalid @property ahead of @namespace in
  a page's own &lt;style&gt;. *Comes back:* 1.x: read @property's syntax and
  initial-value.
- **L117.** A file run does not say on which page it stopped reading nested
  rules at its limits (20,000 characters for a rule's selectors written out
  with its parents', 200,000 over a page's stylesheets, eight blocks deep);
  the README states the limits and that the reports do not say where. *In
  1.0:* Rules past a limit, hides and shows alike, are not read; a page
  needs that much nested CSS of its own. *Comes back:* 1.x: a per-page note
  in the reports and the bundle (a report schema change).
- **L118.** An :nth-child(), :nth-last-child(), :nth-of-type() or
  :nth-last-of-type() whose An+B or `of` is written with escapes
  (`:nth-child(\6f dd)`, `:nth-child(2\6e)`, `:nth-child(2n \6f f .a)`):
  Chromium 141 reads it, the harness drops the rule (measured), so a file
  run does not read what that rule hides or shows. *In 1.0:* Contrived: none
  of the field sweeps' 14,304 saved pages and stylesheets escapes one; a
  rendered run reads it as Chromium does. *Comes back:* 1.x: read An+B by
  CSS's tokens.
- **L119.** Names through a &lt;use&gt;: in Chromium 141, what a &lt;use&gt;
  copies into a drawing (a &lt;symbol&gt;'s &lt;title&gt; or text, a
  &lt;g&gt;'s text, an aria-label) names a control through aria-labelledby,
  and a &lt;symbol&gt;'s &lt;title&gt; names a drawing's &lt;a&gt; that
  holds the &lt;use&gt; (measured); both runs read nothing a &lt;use&gt;
  copies, so such a control FAILs bb-link-name or bb-button-name where
  Chromium names it. *In 1.0:* Uncommon: an icon sprite's control is usually
  named by aria-label or HTML text; review by hand a control named only
  through a &lt;use&gt;. *Comes back:* 1.x: read what a &lt;use&gt;
  references, as Chromium copies it.
- **L120.** A file run matches the page's own rules against each element it
  asks about, and a rule like `[data-x] *` against every ancestor of it: on
  a page hundreds of levels deep with hundreds of such rules, asking about
  an element at the bottom costs the depth squared times the rules (400
  levels and 300 rules: about 33 s for a link there, as at partR6-r6; a
  label's ancestors are walked only where it holds hidden content: R6O-1).
  *In 1.0:* Slow, not wrong; the deepest field page nests 20 levels. *Comes
  back:* 1.x: match descendant selectors in one pass over the tree, or a
  time limit per page in a file run.
- **L121.** A &lt;table&gt; that only its page's styles make one of data
  (cells' borders or background colors, which Chromium 141 weighs; since
  round 10 a border or bgcolor attribute too, which a style may undo: R6Q-2)
  is read as one of layout, and a cell's headers of white space alone as
  empty (the reader splits it to nothing): a link or a button named only by
  such a table's text is not reviewed, though Chromium names it nothing. *In
  1.0:* A silent pass, as before round 9, on a link or a button that wraps a
  styled table; none of the 13,091 saved field pages has one. *Comes back:*
  1.x: read the cells' computed borders and colors in a rendered run, as
  Chromium's heuristic does.
- **L122.** Braces and url() tokens in a selector list are not read as CSS
  reads blocks: in ":is({ ) }, .q), .lbl" or ":is(url(\[), .q), .lbl" the
  list is split at the comma inside :is(, and the rule is dropped, where
  Chromium 141 keeps it (as ":is(.q), .lbl"). *In 1.0:* Contrived: no
  shipped selector seen holds a brace or a url() (Bootstrap, Tailwind,
  normalize, Font Awesome and WordPress sheets read the same); a silent pass
  on such a page. *Comes back:* 1.x: skip {} blocks and url() tokens in
  split_selectors, \_selector_check and \_forgiven.
- **L123.** display:revert-layer outside any cascade layer is read as no
  value; Chromium 141 reverts it to the browser's own stylesheet, which
  hides a closed &lt;dialog&gt; and a popover. *In 1.0:* Contrived: a FAIL
  where a review is due, on focusable content in a closed &lt;dialog&gt; or
  a popover inside aria-hidden that a var() may show and an unlayered
  revert-layer hides. *Comes back:* 1.x: read an unlayered revert-layer as
  revert where no layered rule sets the property.
- **L124.** An image button's &lt;label&gt; (&lt;input type=image&gt;) takes
  the place of its alt in Chromium 141, an empty or a hidden one too
  (measured), as a button's does (R6S-4); bb-img-alt reads the alt. *In
  1.0:* A silent pass on an image button whose &lt;label&gt; names it
  nothing in Chrome and Edge; rare (an image button seldom has a
  &lt;label&gt;). *Comes back:* 1.x: review it as bb-button-name reviews a
  button's empty &lt;label&gt;.
- **L125.** Two readings of axe-core 4.12 the review's impact does not
  model: it stops at a &lt;caption&gt; of white space (a link named only by
  such a table's text is moderate for axe-core, minor in the review), and it
  passes a button whose &lt;label for&gt; it does not see on screen for a
  reason the review does not read: a clip or a clip-path, opacity:0, a place
  off screen, or no size with overflow hidden (minor for axe-core, moderate
  in the review where axe-core does not read the button's own content
  either). *In 1.0:* Contrived: the verdict (a review) is right; only its
  impact, minor or moderate, differs from what axe-core does. *Comes back:*
  1.x: read a caption of white space, and a label off screen, as axe-core
  does.
- **L126.** An @scope's root and limit where markup could decide them: in an
  @scope with no root, the root is the &lt;style&gt;'s parent, which no
  selector names, so `:scope` and `&` there match nothing in a file run; and
  a show past an @scope's limit counts as one that may hold (the limit is
  not matched). *In 1.0:* Contrived: a FAIL where a bare @scope inside the
  hidden element shows it again; a silent pass where a show past a limit is
  the only one. *Comes back:* 1.x: match a bare @scope's root and an
  @scope's limit against the page.
- **L127.** Three readings left as they are: the title of a
  &lt;foreignObject&gt; in a drawing of role none or presentation is not
  read; a &lt;legend&gt;'s content is read by the accessible-name rules, not
  as Chromium 141 reads it; and a bare @scope nested in a style rule or in a
  rooted @scope is read against the outer selector, where Chromium's root
  for it is the &lt;style&gt;'s parent. *In 1.0:* Contrived. A link named
  only by such a title FAILs where Chromium names it; a link named only by a
  title inside a &lt;legend&gt; passes where Chromium names it nothing
  (axe-core passes it: a minor review missed); a show in such an @scope
  counts, so a link whose text Chromium hides may pass. *Comes back:* 1.x:
  read all three as Chromium 141 does.
- **L128.** A form field or a button whose only name is a &lt;label&gt;
  inside an aria-hidden element (the label itself not aria-hidden) fails, as
  the accessible-name computation and axe-core 4.12 read it, though Chromium
  141 names it by that label. *In 1.0:* The FAIL stands, as in axe-core; the
  Chromium reading only keeps a review from saying Chrome and Edge give such
  a control no name. Rare: the label is hidden from assistive technology
  while its control is not. *Comes back:* 1.x: decide whether such a label
  names its control (Chromium) or not (axe-core, the accessible-name
  computation); the accessibility-tree layer (ROADMAP item 2) reads
  Chromium's names.
- **L129.** A re-run of a snapshot whose capture record is hostile: JSON
  nested thousands deep ends the run with an error rather than refusing that
  page; a marks value thousands of characters long is printed whole; a marks
  number of thousands of digits is said to be no record. *In 1.0:* Each
  exits 2 and is never a pass; only a crafted snapshot holds one. *Comes
  back:* 1.x: refuse that page alone, with a short reason, in each case.
- **L130.** A &lt;label&gt; whose first labelable descendant is a
  form-associated custom element: the review of the field after it says
  Chrome and Edge give that field no name, where Chromium 141 names it by
  its title (the label labels the custom element). *In 1.0:* Contrived; it
  rests on the documented reading of R5I-14 (markup cannot show which custom
  elements are form-associated). *Comes back:* 1.x: a rendered run records
  which custom elements are form-associated.
- **L131.** verify and inspect match a bundle's coverage note and layer
  notes to the texts this release writes, not to the bundle's own pages: a
  file run's bundle given a note that claims browser checks is not named.
  *In 1.0:* Each note is checked against this release's texts and statuses
  only; each page's own records say what ran on it, and the verdict is
  unchanged either way. *Comes back:* 1.x: verify recomputes the notes from
  the bundle's pages.
- **L132.** A form field named only by text in its &lt;label&gt; that
  Chromium 141 does not read, inside an element whose content axe-core 4.12
  reads there (a &lt;figure&gt;'s), is a moderate review, though axe-core
  passes it. *In 1.0:* Moderate unless axe-core passes the field by its
  title or placeholder, or the text is a title it reads; the message says
  only that other checks may fail it. Contrived. *Comes back:* 1.x: read a
  &lt;label&gt;'s content as axe-core does, role by role.
- **L133.** soupsieve after 2.9: its 3.0 refuses complex selectors inside
  :has() by default, which Chromium applies (with it, a link whose only text
  such a rule hides passed; measured), and 2.10 reworked matching (sibling
  caching, attribute values). *In 1.0:* The package asks for
  soupsieve&gt;=2.9.2,&lt;2.10, the 2.9.2 the suite, the field sweeps and
  the image ran; a test holds :has() rules to Chromium's names. *Comes
  back:* 1.x: pass soupsieve's NOSTRICT flag, run the suite, a field sweep
  and the Chromium measurements on the new version, then widen the range.
- **L135.** A token whose backslash escapes mix a script's octal ones with
  CSS's hex ones, which read `\61` as different characters ("1" and "a"), is
  not found; nor one with a character after a backslash that a script and
  CSS read differently (`\n` is a line feed in a script, "n" in CSS). *In
  1.0:* A token is found with JSON's and a script's escapes, octal ones
  included, or with CSS's; README, EVIDENCE.md and the guide say so. (Each
  is read in its own pass, so the quick pass that picks which tokens to look
  for in a text keeps every one the search finds: R6G-1). *Comes back:* If a
  page is seen writing a token so: a pre-check that reads both in one pass.
- **L136.** A run of backslashes in a secret or password is found only when
  spelled one way throughout: as it is, doubled, or four or eight times over
  (an escape after it may take one to four more), or with every backslash
  spelled otherwise (`%5C`, `&#92;`); a run that mixes the two, or one
  followed by an escape escaped more often, is not. *In 1.0:* Each run is
  read one way, so a search stays linear on a near miss, which was
  exponential (R6G-6). *Comes back:* If a page is seen writing one so.
- **L137.** Python 3.10: 1.0 needs Python 3.11 or later. *In 1.0:* The
  secret searches stay linear with atomic groups and possessive quantifiers,
  which Python 3.11 added (R6G-2); the CI tests 3.11 to 3.15. *Comes back:*
  If someone needs 3.10, whose own support ends in October 2026 (PEP 619).
- **L138.** A memory limit for `verify` and `inspect`: they need about 50
  times a bundle's size in memory (an 8 MB file took 422 MB) and read files
  up to 256 MB, so a hostile file can need more memory than a machine has.
  *In 1.0:* Files over 256 MB are refused (`MAX_BUNDLE_FILE`). *Comes back:*
  Before a service verifies bundles others made: count containers while
  parsing, or lower the limit.
- **L139.** The release's build images and tools pinned by digest:
  setup-buildx pulls `moby/buildkit:buildx-stable-1` by tag, and BuildKit's
  SBOM step `docker/buildkit-syft-scanner:stable-1` by tag (setup-qemu,
  which pulled `tonistiigi/binfmt:latest`, left the release in S5-5); build
  and setuptools are pinned by version, not by hash, with their own
  dependencies unpinned. *In 1.0:* The actions are pinned by commit, the
  base image by digest (which a final version's release check requires), the
  image's Python packages by hash (`docker/requirements.txt`, S5), and build
  and setuptools by version (`tools/build-constraints.txt`). *Comes back:*
  When their digests and hashes are looked up from the registries and
  checked.
- **L140.** `bellbriar-pack/1` frozen with the other formats: its
  verification lacks what CANONICALIZATION §6 gives a bundle (strict
  parsing, canonical Base64, the small-order checks, a closed signature
  block). *In 1.0:* No packs or pack key ship; CANONICALIZATION §1 and §7
  call the format a draft, outside the freeze. *Comes back:* With packs
  (L3): bring CANONICALIZATION §7 up to §6 before a release ships one.
- **L141.** Native Windows. The suite, run on Windows in CI for 1.0.0rc1
  (Python 3.11 to 3.14), found a bundle recording a page's path with
  backslashes (fixtures\\good.html) where Linux and macOS record
  fixtures/good.html; two outputs named for one file through a symbolic link
  not refused (R5B-14); a name with a drive (C:/a.html) recorded otherwise
  than elsewhere (R5F-1); and parts of the suite itself that assume POSIX
  (os.geteuid and signal.SIGKILL, files read without encoding="utf-8", POSIX
  paths in fixtures). 12 failures and 10 errors in all; that run's CI log
  has the rest. *In 1.0:* On Windows, bellbriar-eval, bellbriar-lint and
  bellbriar-evidence stop before doing anything (exit 2) and point to WSL
  and the container image (support.py). CI tests Linux and macOS only; the
  package's classifiers name Linux and macOS; the Action stops on a Windows
  runner and says to use a Linux one. *Comes back:* A customer needs native
  Windows: fix each difference, make the suite run there, and put Windows
  back in CI.
- **L142.** justhtml after 3.13.0. 3.13.1 (October 12, 2026) parses
  &lt;!doctype
  html&gt;&lt;svg&gt;&amp;\#xFFFD;&lt;/svg&gt;&lt;frameset&gt;&lt;frame&gt;
  to a body holding the drawing, where the tree the suite recorded from
  Chromium has the frameset (tests/test_html5_parsing.py); every test job in
  CI failed on it. *In 1.0:* pyproject.toml pins justhtml==3.13.0, as the
  image's requirements already did. *Comes back:* A justhtml release: run
  the suite, and compare any changed tree with Chromium's, before the pin
  moves.
- **L143.** Browsers after Chromium 153. The harness's readings were
  measured in Chromium 141; the image and the browser extra run Chromium 153
  (Playwright 1.63.0). In CI, Playwright 1.64.0's Chromium 156 drew a
  drawing's &lt;a&gt; whose requiredExtensions starts with white space (s7,
  R6 round 6), which Chromium 141 does not draw. The static rules, and the
  capture's own reading of a part's conditions (used where the browser
  paints nothing to measure), still fail such a part, as 141 does. *In 1.0:*
  The browser extra pins playwright==1.63.0, the version the image runs. The
  s7 test asks the running browser whether it draws the part. *Comes back:*
  Before the pin moves: measure the new Chromium where the harness reads as
  141 does (requiredExtensions with white space first, and the other
  measured readings), and run the suite.
- **L144.** bellbriar-lint has no configuration file: its `--exclude`
  patterns, and its other options, go on the command line. *In 1.0:*
  `--exclude PATTERN`, repeatable (S5-4). *Comes back:* If projects ask to
  keep their lint settings in a file.
- **L145.** A page with nothing beyond its scripts but a loading indicator
  (a status, alert, log, timer or marquee region, a progress bar, an
  aria-busy region, a spinner) is not evaluated, even where the indicator
  holds a link or a control (an error message's "Try again"). *In 1.0:* Not
  evaluated, exit 2: a loading shell no longer passes as Tier-1 clean
  (S5-3). *Comes back:* If such pages need a verdict: read the links and
  controls inside those regions as content.
- **L146.** A page that keeps a data request open (a long poll), or that
  polls more often than the settle step's quiet period (500 ms by default)
  so that a request may be open when the wait ends, is not evaluated unless
  `--wait-for` names what it shows once loaded: the capture cannot tell such
  a request from data still on its way. *In 1.0:* Not evaluated, exit 2;
  `--wait-for SELECTOR` evaluates it (S5-3). *Comes back:* If such pages are
  common: tell a long poll, or a frequent poll, from a page still loading.
- **L147.** Release tags are annotated, not signed, though H4 asks for
  signed tags. *In 1.0:* The maintainer pushes an annotated tag as
  bellbriar-ops. Rulesets let only the repository's admin create `v*` tags,
  and no one move or delete them; the release checks that the tagged commit
  is on `main`, and PyPI's attestations name the workflow and the commit.
  *Comes back:* When the release is used beyond its first testers: sign tags
  with the maintainer's SSH key, registered on GitHub as a signing key, and
  PREPUBLISH 15 says so.

## Not on this roadmap

- "Conforming alternate versions" or separate accessible versions of a
  site. Out of scope by design.
- A compliance certificate or a single compliance score. Never.
