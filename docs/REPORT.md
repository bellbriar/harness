# Reports: `bellbriar-report/1` and `bellbriar-lint/1`

`bellbriar-eval --json FILE` writes the run as JSON in the format
`bellbriar-report/1`, and `--html FILE` writes the same record as a page
for people. `bellbriar-lint --format json` writes `bellbriar-lint/1`. This
page documents every field of both, so scripts can depend on them.

**What stays stable.** Within a format string, no field is removed or
renamed, and none changes its type or its meaning. A minor release
(1.1.0: CHANGELOG.md, "Versions") may add fields, and values to the lists
marked *open* below, so a script should ignore fields it does not know. Anything else takes a new format
string (`bellbriar-report/2`). Every report starts with its `format`. The
JSON Schema `docs/bellbriar-report-1.schema.json` states the fields and
types below, and the test suite checks real reports against it.

The console output is for people and is not a format: parse the JSON.

## The JSON report, `bellbriar-report/1`

| Field | Type | What it holds |
|---|---|---|
| `format` | string | `"bellbriar-report/1"` |
| `generated_at` | string | When the report was written, UTC, as `2026-10-11T14:02:09Z` |
| `source` | string | How the run got its pages: `files` (read as they are), `render` (files served on this machine for a browser, `--render`: each page's `fetch` says whether the browser captured it or the file was read as it is) or `urls` (fetched from a site: `--url`, `--urls`, `--sitemap`) |
| `tool` | object | What made the run (below) |
| `rulebook_version` | string or null | The rulebook's own version (`rulebook_version` in `rulebook.json`) |
| `rulebook_sha256` | string | The SHA-256 of the rulebook's canonical form: which rules ran, exactly. A custom `--rulebook` changes it |
| `rulebook_bundled` | boolean | Whether that is the rulebook this harness ships |
| `layers` | array | One object per layer: `layer` (its name), `status` (`executed`, `partial` or `skipped`) and `note` (what it covered) |
| `coverage_note` | string | The sentence every report carries: what the run covered, and what it did not |
| `incomplete` | boolean | True when a rule raised an error on a page, or a page could not be read: that result is unknown, not a pass, and the run wrote no evidence bundle. A page the rules had nothing to evaluate in (an app shell its scripts build, read without a browser) does not make a run incomplete: `site.pages_not_evaluable` counts it, the pass rate leaves it out, and the tier-1-clean share counts it only when a Tier-1 rule failed on it |
| `errors` | integer | How many (page, rule) pairs could not be evaluated; each is listed in its page's `errors` |
| `site` | object | The run's numbers (below) |
| `rules` | object | Each rule that ran, by id: what it is and how it fared (below) |
| `fetch` | object or null | A URL run's record of what it fetched (below); null for files, rendered with `--render` or not, and for a URL run that could fetch no page |
| `judged` | object or null | Null in 1.0. It is reserved for the adequacy track, which 1.0 leaves out: a release that brings the track back fills it with an object |
| `baseline` | object or null | The `--baseline` report the run's gate compared with (below); null for a run without one |
| `pages` | array | One object per page, in the run's order (below) |

### `tool`

| Field | Type | What it holds |
|---|---|---|
| `name` | string | `"bellbriar-harness"` |
| `version` | string | The harness version |
| `python` | string | The Python version it ran on |
| `libraries` | object | The versions of the libraries that decide verdicts, by name: `justhtml`, `beautifulsoup4`, `soupsieve`, `expat`, and, when a browser captured pages, `playwright` and `axe-core`; null for one that could not be found |
| `from_snapshot` | object | Present only when a re-run of a saved snapshot read what its capture recorded: `{"axe-core": versions, "chromium": versions}`, the axe-core whose results it holds and the Chromium that captured it: a version, or several joined by `" and "` when the snapshot's pages differ (either may be absent) |

### `site`

| Field | Type | What it holds |
|---|---|---|
| `site_weighted_pass_rate` | number or null | Passed weight over applicable weight, pooled across the pages the rules could evaluate, from 0 to 1; null when nothing applied (never 0 and never 1 for nothing) |
| `pct_pages_tier1_clean` | number or null | The share of pages whose Tier-1 status is decided that are Tier-1 clean, from 0 to 1; null when no page is decided |
| `pages_not_evaluable` | integer | Pages the static rules could not read (an app shell, an unreadable page) |
| `tier1_rules_executed` | integer | Tier-1 rules that ran to the end on at least one page |
| `tier1_rules_total` | integer | Tier-1 rules in the rulebook |
| `tier1_rules_review_only` | integer | How many of the executed Tier-1 rules never fail |
| `total_fail_findings` | integer | FAIL findings in the site's own markup |
| `total_needs_review` | integer | Review findings in the site's own markup |
| `total_third_party_fail_findings` | integer | FAIL findings in markup a known vendor's script inserted: reported, never scored |
| `total_third_party_needs_review` | integer | Review findings in such markup |
| `rule_fail_totals` | object | For each rule that failed in the site's own markup, how many pages it failed on, most first |

### `rules`

One entry per rule with a result on at least one page, keyed by rule id,
in the rulebook's order. `docs/RULES.md` describes every rule.

| Field | Type | What it holds |
|---|---|---|
| `name` | string | The rule's name |
| `sc` | array of strings | The WCAG success criteria it cites |
| `tier` | integer or null | Its tier: 1, 2 or 3, weighted 5, 2 and 1 in the pass rate, or 0 for the checks the rulebook keeps for settlements and exclusions (document links, the accessibility statement), which are never scored. A rule that never fails (basis policy, best-practice or review) weighs 0 whatever its tier |
| `layer` | string or null | `static-dom` (read from the markup) or `rendered` (checked in the browser) |
| `verdict_basis` | string or null | What a finding from it means: `sc`, `heuristic`, `policy`, `best-practice` or `review` (below) |
| `engine` | string | `bellbriar`, or `axe-core` for a rule axe-core decides in the browser |
| `understanding` | string or null | The address of W3C's Understanding document for one of its criteria |
| `why` | string or null | Why it matters, in a sentence or two |
| `fix` | string or null | How to fix what it finds |
| `pages_applicable` | integer | Pages it applied to |
| `pages_failed` | integer | Pages it failed on, in the site's own markup |
| `pages_errored` | integer | Pages where it raised: its result there is unknown |
| `fail_findings`, `needs_review_findings` | integer | Its findings in the site's own markup |
| `third_party_fail_findings`, `third_party_needs_review_findings` | integer | Its findings in vendor markup |

An internal check that raised (such as `(app-shell check)`) appears with
its id as its name, null metadata and its counts.

### `fetch` (the run's)

Present in a URL run (`--url`, `--urls`, `--sitemap`) that fetched at least
one page, and the evidence bundle's `fetch` (`docs/EVIDENCE.md`):

| Field | Type | What it holds |
|---|---|---|
| `final_url` | string | The final URL of the first page the run fetched |
| `host` | string | The host every page was fetched from, read from that URL |
| `pages` | integer | How many pages the run shows |
| `list` | object | How the pages were listed: `kind` (`urls` or `sitemap`) and `max_pages`; for a sitemap also its `url`, how many pages it `listed`, and whether that count is `complete` |

### `pages[i]`

| Field | Type | What it holds |
|---|---|---|
| `path` | string | The page: a file as the run recorded its name (never absolute, never with `..`), or the URL it was fetched from, with any user name and password removed and query and fragment values, and path parameters' values (`/shop;jsessionid=…`), recorded as `REDACTED` (a token in the path itself is kept: nothing tells it from a page's name). Two pages whose URLs differ only in what is redacted share a path; the HTML report numbers them |
| `fetch` | object or null | The page's capture record in a URL or `--render` run (below); null for a file read as it is, and for a page that could not be fetched or served |
| `score` | object | The page's numbers (below) |
| `findings` | array | Every finding on the page (below), rule by rule in the rulebook's order |
| `not_applicable_rules` | array of strings | Rules that ran and did not apply |
| `errors` | array | `{"rule_id", "error"}` for each rule that raised on the page; `"(the page)"` when the page itself could not be read |

A rule with no result on a page (a browser rule on a page no browser
captured) appears in neither `findings` nor `not_applicable_rules`: it was
not evaluated there.

### `pages[i].fetch` (the capture record)

The evidence bundle's `pages[i].fetch`; `docs/EVIDENCE.md` says more about
some of its fields. Objects within it may gain fields.

| Field | Type | What it holds |
|---|---|---|
| `requested_url` | string | The URL as requested, secrets redacted |
| `final_url` | string | The URL after redirects, secrets redacted |
| `host` | string | The final URL's host |
| `mode` | string | `rendered` (captured after the page's scripts ran) or `server` (the HTML the server sent, or with `--render` the file as it is) |
| `http_status` | integer | The HTTP status of the final response |
| `redirects` | array | Where the page was redirected: the requested URL, then each URL it was sent to, the last being the final URL; empty when it was not redirected |
| `redacted` | array of strings | What was removed from recorded URLs (`path`, `query`, `fragment`, `userinfo`, `http-credentials`) |
| `fetched_at` | string | When the page was fetched |
| `browser` | object or null | The browser: `name`, `version`, and whether it ran with its `sandbox` |
| `viewport` | object or null | The viewport, `width` and `height` in CSS pixels |
| `wait` | object or null | How long the capture waited for the page to settle, and whether it did |
| `instrumented` | boolean | Whether the capture recorded attribution and what the page hides |
| `provenance_attr` | string or null | The attribute name the capture's records are under (for `--provenance-attr`) |
| `attribution` | object or null | The attribution policy and vendor list version |
| `shadow_roots` | integer or null | Shadow roots the capture included |
| `axe` | object or null | The axe-core run: its version, its SHA-256, the rules it ran and what it could not check |
| `narrow` | object or null | The narrow viewport (320 by 640): what was recorded there, and its reflow measurement |
| `reader` | string | How the rules read the snapshot: `dom`, `html` or `xml` (`--read-as`) |
| `address_class` | string | Whether the host is a public site, loopback or private, from one table `verify` shares |
| `address_basis` | string | What decided it: `address` or `name` |
| `snapshot_sha256` | string | The SHA-256 of exactly what the rules read |
| `fallback_reason` | string or null | Why the page was not rendered, in the harness's own words; null when it was |
| `notes` | array of strings | What else the capture says (the sandbox, content it could not check) |

The capture's `wait`, in a rendered capture:

| Field | Type | What it holds |
|---|---|---|
| `strategy` | string | `load+scroll+dom-and-data-settle`: after the load event the page is scrolled through, then waited on until its DOM has not changed, and none of its data requests has been open, for `quiet_ms` |
| `quiet_ms` | integer | How long the page must stay still: 500 |
| `cap_ms` | integer | The longest that wait lasts: 8000 |
| `waited_ms` | integer | How long it lasted |
| `settled` | boolean | Whether the DOM stopped changing within `cap_ms` |
| `data_requests` | integer | The page's fetch and XHR requests seen, a known vendor's and a `--third-party-origin`'s left out |
| `data_requests_open` | integer | How many of them had not answered at the end: those open at `cap_ms`, and those they lead to, get 2000 ms more, until none has been open for `quiet_ms`, and the DOM then as long again to settle; a page with any open is not evaluated, unless `wait_for` names what it shows once loaded |
| `wait_for` | string or null | The `--wait-for` selector the capture waited for, up to 30 seconds, before the rest of its wait |
| `scroll_steps` | integer | How many steps the page was scrolled through in |

### `pages[i].score`

| Field | Type | What it holds |
|---|---|---|
| `path` | string | The page, as above |
| `weighted_pass_rate` | number or null | As the site's, for this page; null when nothing applied or the page could not be evaluated |
| `applicable_weight`, `passed_weight` | integer | The rate's two terms |
| `tier1_clean` | boolean or null | No failure among the Tier-1 rules that can fail and applied here; null when undecided (no such rule applied, one raised, or the page could not be evaluated) |
| `tier1_rules_executed` | integer | Tier-1 rules that ran to the end on this page |
| `tier1_rules_applicable` | integer | Of those, the ones that can fail and applied: what `tier1_clean` rests on |
| `evaluable` | boolean | False when the static rules could not read the page |
| `not_evaluable_reason` | string | Why, or "" |
| `fail_findings`, `needs_review_findings` | integer | Findings in the site's own markup |
| `third_party_fail_findings`, `third_party_needs_review_findings` | integer | Findings in vendor markup |
| `failed_rules` | array of strings | Rules that failed here, in the site's own markup |

### `pages[i].findings[j]`

| Field | Type | What it holds |
|---|---|---|
| `rule_id` | string | The rule |
| `verdict` | string | `fail` or `needs_review` |
| `verdict_basis` | string | The rule's basis, as in `rules`: `sc` (a FAIL is a failure of the cited criteria that W3C names), `heuristic` (a probable failure), or `policy`, `best-practice` or `review` (never a FAIL); "" for a rule the rulebook does not list |
| `impact` | string | `blocker`, `serious`, `moderate` or `minor` |
| `message` | string | What was found; a release may improve the wording |
| `line` | integer or null | The line the element starts on in what the rules read (the file, or the captured snapshot); null for a finding about the page |
| `selector` | array of strings or null | The element's locator: one CSS selector per tree, the first matched in the document and each next one in the shadow root of the element the one before found (the guide's "Where a finding is"); null for a finding about the page |
| `snippet` | string | The element's markup, whitespace collapsed, at most 180 characters; "" for a finding about the page |
| `origin` | string | Who inserted the markup, where a rendered capture recorded it: `first-party`, `cross-origin`, `third-party`, `server` (in the HTML the server sent) or `unknown`; "" where nothing was recorded (a file, server HTML). *Open* |
| `origin_detail` | string | For `third-party` and `cross-origin`, the script origin responsible |
| `owned` | boolean | Whether it counts as the site's own: false only for `third-party` |
| `about` | string | What the finding is about, the same on any page and in any run while the element is (below): 32 hexadecimal digits, or "" for a finding about the page |
| `fingerprint` | string | 32 hexadecimal digits that identify the finding on its page from run to run (below) |
| `in_baseline` | boolean or null | Whether the `--baseline` report lists a finding with this fingerprint and the same `verdict`, `owned`, `impact` and rule tier ("`baseline`", below); null for a run without a baseline |

**`about` and fingerprints.** Both are the first 32 hex digits of the
SHA-256 of a JSON array written with ASCII escapes (`\u00e9` for `é`) and
no spaces. A finding's `about` hashes `[tag, text, inside]`, read from the
tree the rules read (below).

- `tag` is its element as `[name, [[attribute, value], ...]]`: the element
  and attribute names lowercased, the attributes sorted by name, each value
  with its white space collapsed (a class list reads `"icon big"`). Left
  out are the records a rendered capture writes into the page, and two
  attributes a page changes on every request by design: `nonce`, and the
  `value` of an `<input type="hidden">` (CSRF tokens, view state).
- `text` is the first 200 characters of the element's text: its text
  nodes joined by a space, then white space collapsed (any Unicode white
  space, as Python's `str.split()` reads it), so `<a>Ca<b>fé</b></a>`
  reads `"Ca fé"`. Inside most elements the text of `<script>`, `<style>`
  and `<template>` is not counted, nor are comments.
- `inside` is the `tag` of each of its first 20 descendant elements, in
  document order (so three icon buttons that differ only in their `<svg>`
  are three elements). The content of a `<template>` counts. What a
  `<noscript>` holds counts in neither part, because a page's own markup
  and a browser's capture of it hold it differently. A shadow root reads
  as a `<template shadowrootmode>` (its mode lowercased) holding its
  content, with the host's light-DOM children where the slots that show
  them are.
- For `<html>`, `<head>` and `<body>`, whose text and descendants are the
  whole page's, `text` is `""` and `inside` is `[]`.
- In a URL run, the run's secrets are replaced by `REDACTED` in every name,
  value and text first (the text before its 200 characters are cut): the
  values of its URL's parameters that look like credentials and the
  `--http-user` credentials as a request's Authorization header carries
  them, in the spellings of markup, a URL, JSON, a script and CSS that
  README.md lists ("Recorded URLs carry no secrets"), and the
  `--http-user` password,
  wherever a withheld finding would find it. A hash of them as they were
  would let a reader test a guess at one.

For example, `<a class="icon  big" href="/cart">Café <b>menu</b></a>` is
about `[["a",[["class","icon big"],["href","/cart"]]],"Café menu",[["b",[]]]]`.
Because names and order are normalized, the same element has the same
`about` in a file run and in a `--render` run, unless a script changed it
there (the browser's page is what its scripts left). A `--render` run
serves each folder on a port taken from the folder's name, so a page that
writes its own address into its markup reads the same from run to run;
when another program holds that port, the run says so.

A finding's `fingerprint` hashes `["bellbriar-finding/1", rule id, path,
n, about, k]`: `n` numbers the pages of the run recorded under the same
`path` (0 unless two pages share one, as URLs that differ only in values
recorded as `REDACTED` do), and `k` counts the earlier findings on the
page with the same rule and `about` (0 for the first). Pages that share a
path are numbered in an order fixed by the SHA-256 of the full URL the run
was given for each, which no record holds: a list that names them in
another order gives each the same `n`, but adding or removing one of them
can renumber the others. Two URLs that name one page are evaluated once,
under the least of them, whichever the list names first; a sitemap is
read only until it has given `--max-pages` pages, so a spelling it lists
after that is not compared. So
the same element failing the same rule on the same page keeps its
fingerprint from run to run, even when lines above it move, and its line
and message, which a release may reword, are left out. A fingerprint
changes when its element changes (an attribute added or edited, the start
of its text, or one of its first 20 descendants, including any token in
their attributes that changes on every request other than the two left
out above, such as a signed image address), when an element that reads
the same is added or removed before it on the page, and when the page's
recorded `path` changes: evaluate a folder the same way each time
(`bellbriar-eval dist`, not `cd dist` and `bellbriar-eval .`), and note
that a re-run of a saved snapshot records the snapshot's file name, not
the URL. `k` counts every earlier finding of the rule about the same
thing, the site's and a vendor's alike: when a vendor's script inserts an
element that reads the same as one of the site's before it, the site's
finding takes the next `k`, and to a baseline it reads as new (a failure
the gate shows, never one it hides).

### `baseline`

`--baseline REPORT` names the JSON report of an earlier run, and the
run's gate then counts only the findings it does not list: an agency can
add the gate to a site that already has failures without a red build until
every one is fixed, and still stop new ones. A finding is matched by its
`fingerprint` and by what the gate reads of it: its `verdict`, `owned`,
`impact`, and its rule's `tier` as each report's `rules` records it. One
whose verdict, owner, impact or tier changed is new, because the baseline
accepted what it was, not what it became: a review that became a FAIL, a
vendor's failure now in the site's own markup, a rule a rulebook moved
into a tier the gate counts. Only the gate changes. The reports (and any
evidence bundle) list every finding, count it in every number, and record
the baseline:

| Field | Type | What it holds |
|---|---|---|
| `sha256` | string | The SHA-256 of the baseline file: which report, exactly |
| `generated_at` | string or null | When the baseline report was made, its own `generated_at` |
| `findings` | integer | How many findings the baseline lists |
| `new_findings` | integer | How many of this run's findings it does not list (as above) |
| `new_fail_findings` | integer | How many of those are FAIL findings in the site's own markup (`owned`) |

A baseline matches only findings recorded the same way: the same page
`path` (so make it from a run over the same folder or URLs, from the same
working directory) and the same element, as its fingerprint reads it. When
none of a run's findings is in its baseline, the console says so, since a
renamed folder makes every finding read as new; when the baseline was
made with another rulebook, it says that too, since a rule whose tier
changed makes each of its findings new. The gate trusts its baseline: a
change that adds its own failures to the file passes, so a committed
baseline needs the review code gets.

## The HTML report

The HTML report is drawn from the same record. It opens with the coverage
banner and the run's numbers, then lists the rules with findings and their
counts, the pages and how each was read, and then the findings by rule:
for each rule, what it checks, why it matters, how to fix it (with HTML,
React and Vue examples, which come from the harness, not the JSON) and its
findings, page by page. Findings that read the same (an element with the
same `about`, and the same message) are shown once with their count, on
one page or, in a table of their own, across pages; a table shows at most
100 rows, and says how many findings, and how many of them failures, it
leaves out: the JSON report lists every finding. Last comes each page's
capture record.
The report is a single file with no external assets, and it passes the
harness's own rules, in the browser too.

## Lint output, `bellbriar-lint/1`

`bellbriar-lint --format json` prints one object:

| Field | Type | What it holds |
|---|---|---|
| `format` | string | `"bellbriar-lint/1"` |
| `files_scanned` | integer | Files the linter read: those it could not lint are counted (each is a `bl-lint-error` finding), and files it skipped as minified are not |
| `errors`, `warnings` | integer | Findings of each severity |
| `notes` | array of strings | What the scan could not do or skipped (a folder whose ignore rules git could not read, files that look minified) |
| `findings` | array | One object per finding (below) |

| Field | Type | What it holds |
|---|---|---|
| `rule_id` | string | The lint rule (`bl-…`); `bl-lint-error` for a file that could not be linted |
| `severity` | string | `error` or `warn` |
| `path` | string | The file, as the scan found it |
| `line` | integer | The line |
| `message` | string | What was found; a release may improve the wording |
| `ref` | string | The rule of Bellbriar's WCAG pack the finding comes from (the pack is not distributed with the harness) |
| `snippet` | string | The line, trimmed, at most 160 characters |

`bellbriar-lint --format sarif` writes the same findings as SARIF 2.1.0
(https://docs.oasis-open.org/sarif/sarif/v2.1.0/), the format GitHub code
scanning reads: one run whose tool is `bellbriar-lint`, a rule for each
rule id found (with a one-line description), and a result for each
finding on its file and line, its level `error` or `warning` as the
finding's severity, its message ending with the WCAG pack rule. A file
inside the folder the scan ran in is named by its path relative to that
folder, any other by an absolute `file:` URI; bytes of a name that are not
UTF-8 are percent-encoded. What the scan could not do is in the run's
`invocations[0].toolExecutionNotifications`: a file it could not lint
(`bl-lint-error` in the other formats) is a notification at level `error`
naming the file, not a result, and makes `executionSuccessful` false; the
other notes are at level `note`. The exit status is the same in every
format, and is 2 when no file could be linted. SARIF is its own standard; this page's stability promise covers
`bellbriar-lint/1`.
