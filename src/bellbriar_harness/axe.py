"""axe-core, pinned and hash-checked, for the WCAG A/AA rules Bellbriar does
not implement itself (decision D2).

What runs. axe-core 4.12.1 (MPL-2.0, Deque Systems), unmodified, from
vendor/axe-core/. Its SHA-256 is checked against AXE_SHA256 every time it is
loaded, and no axe-core check runs when they differ. AXE_RULES lists the
axe-core rules a rendered capture runs, each under the Bellbriar rule that
reports it; every other WCAG A/AA rule of axe-core is in NOT_RUN, with the
reason: Bellbriar's own rule decides it, or axe-core marks it experimental
or deprecated, or it needs what the capture does not read. Native checks
replace these rule by rule later (L1); the rule ids stay.

Where it runs. In the browser, after the page settles and before the
capture, in an isolated world the harness makes over the DevTools protocol
(fetch._AxeSession): a JavaScript world of its own over the page's DOM,
which the page's scripts cannot reach, so they cannot redefine what
axe-core calls or read its results. It reads only the page's own document
(iframes are other documents, which the capture does not read either), and
walks into closed shadow roots too: the protocol finds them, and in that
world alone `shadowRoot` returns them (RUNNER_JS).

How results reach the rules. The capture writes them into the snapshot,
under names derived from its secret provenance attribute, as it writes the
other records (model.axe_attr, model.axe_run_attr): each element axe-core
reported carries its results, and the root element the run's record (the
version, which rules applied, and how many results of each rule could not
be attached to an element). Each element is found where the isolated world
saw it just before the capture, and the harness checks afterwards that the
page changed nothing on the way there (RUNNER_JS `changed`): a result whose
element moved, or was removed, is counted, never dropped and never moved
onto another element. The rules read the records (checks_rendered.py), so
re-running the snapshot with --provenance-attr reproduces them, and a page
cannot write such a record about itself.
"""
from __future__ import annotations

import hashlib
import html
import json
from importlib import resources

#: The axe-core release vendored in vendor/axe-core/ (its README.md).
AXE_VERSION = "4.12.1"
#: SHA-256 of vendor/axe-core/axe.min.js, exactly as published: the npm
#: package's axe.min.js, whose integrity axe-core publishes in
#: sri-history.json as sha256-ZqiqqVqLBEp/10pUNYc78E/2WhynVWfJIbdQl0IIWhQ=.
AXE_SHA256 = "66a8aaa95a8b044a7fd74a5435873bf04ff65a1ca75567c921b7509742085a14"
AXE_FILE = ("vendor", "axe-core", "axe.min.js")

#: The axe-core rules a rendered capture runs, each under the Bellbriar rule
#: that reports it (rulebook.json, "engine": "axe-core"): every WCAG 2.0,
#: 2.1 and 2.2 A or AA rule axe-core 4.12.1 has that no Bellbriar rule
#: decides, axe-core does not mark experimental or deprecated, and needs
#: nothing the capture does not read.
AXE_RULES = {
    "bb-contrast-min": "color-contrast",
    "bb-target-size": "target-size",
    "bb-link-in-text": "link-in-text-block",
    "bb-list": "list",
    "bb-listitem": "listitem",
    "bb-definition-list": "definition-list",
    "bb-dlitem": "dlitem",
    "bb-aria-required-children": "aria-required-children",
    "bb-aria-required-parent": "aria-required-parent",
    "bb-aria-required-attr": "aria-required-attr",
    "bb-aria-allowed-attr": "aria-allowed-attr",
    "bb-aria-prohibited-attr": "aria-prohibited-attr",
    "bb-aria-conditional-attr": "aria-conditional-attr",
    "bb-aria-attr-value": "aria-valid-attr-value",
    "bb-aria-deprecated-role": "aria-deprecated-role",
    "bb-aria-braille": "aria-braille-equivalent",
    "bb-aria-hidden-body": "aria-hidden-body",
    "bb-nested-interactive": "nested-interactive",
    "bb-scrollable-region": "scrollable-region-focusable",
    "bb-server-image-map": "server-side-image-map",
    "bb-summary-name": "summary-name",
    "bb-object-alt": "object-alt",
    "bb-element-lang": "valid-lang",
    "bb-xml-lang-mismatch": "html-xml-lang-mismatch",
    "bb-td-headers": "td-headers-attr",
    "bb-th-data-cells": "th-has-data-cells",
    "bb-frame-title-unique": "frame-title-unique",
    "bb-multiple-labels": "form-field-multiple-labels",
    "bb-inline-spacing": "avoid-inline-spacing",
}

#: axe-core's other WCAG A/AA rules, which no capture runs, and why: the
#: Bellbriar rule that decides the same requirement, or another reason.
NOT_RUN = {
    "area-alt": "bb-img-alt",
    "aria-command-name": "bb-link-name, bb-button-name and bb-widget-name",
    "aria-hidden-focus": "bb-aria-hidden-focus",
    "aria-input-field-name": "bb-control-label",
    "aria-meter-name": "bb-progress-name",
    "aria-progressbar-name": "bb-progress-name",
    "aria-roles": "bb-aria-role",
    "aria-tab-name": "bb-widget-name",
    "aria-toggle-field-name": "bb-control-label and bb-widget-name",
    "aria-tooltip-name": "bb-widget-name",
    "aria-valid-attr": "bb-aria-attr",
    "autocomplete-valid": "bb-autocomplete",
    "blink": "bb-marquee-blink",
    "button-name": "bb-button-name",
    "bypass": "bb-skip-link",
    "document-title": "bb-page-title",
    "duplicate-id-aria": "bb-duplicate-id",
    "frame-title": "bb-iframe-title",
    "html-has-lang": "bb-html-lang",
    "html-lang-valid": "bb-html-lang",
    "image-alt": "bb-img-alt",
    "input-button-name": "bb-button-name",
    "input-image-alt": "bb-img-alt",
    "label": "bb-control-label",
    "link-name": "bb-link-name",
    "marquee": "bb-marquee-blink",
    "meta-refresh": "bb-meta-refresh",
    "meta-viewport": "bb-viewport-zoom",
    "no-autoplay-audio": "bb-media-autoplay",
    "role-img-alt": "bb-role-img-name",
    "select-name": "bb-control-label",
    "svg-img-alt": "bb-svg-name and bb-role-img-name",
    "video-caption": "bb-media-captions",
    "frame-focusable-content": (
        "needs each frame's own document, which neither axe-core here nor "
        "the capture reads (L42)"),
    "css-orientation-lock": "experimental in axe-core",
    "label-content-name-mismatch": "experimental in axe-core",
    "p-as-heading": "experimental in axe-core",
    "table-fake-caption": "experimental in axe-core",
    "td-has-header": "experimental in axe-core",
    "aria-roledescription": "deprecated in axe-core",
    "audio-caption": "deprecated in axe-core",
}

#: The tags of the WCAG A and AA rules (axe-core's own tags).
WCAG_A_AA_TAGS = ("wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22a",
                  "wcag22aa")

#: axe-core's impact, as Bellbriar words it (model.py).
IMPACTS = {"critical": "blocker", "serious": "serious",
           "moderate": "moderate", "minor": "minor"}
#: Bellbriar's impacts, most severe first.
SEVERITY = ("blocker", "serious", "moderate", "minor")

#: The most elements whose results one capture records, and the longest
#: message one result keeps: a page cannot make the snapshot huge. Results
#: past it are counted, never dropped silently: the run's record says, for
#: each rule, how many of its results the capture could not attach to an
#: element (read_run), and those are findings about the page
#: (checks_rendered). A run records the results of the rules that can fail
#: first (rule_order), so results that never count cannot crowd them out.
MAX_ELEMENTS = 10_000
MAX_MESSAGE = 600
#: How long axe-core may take on one page. A run takes its rules in parts
#: (RUN_PARTS: contrast, then target size, then the rest), and no part
#: starts once this much time has gone: the rules of a part that did not
#: run are not evaluated on the page, and the capture says so. axe-core
#: works without yielding inside a part, so a part that started runs to
#: its end; MAX_PAGE_ELEMENTS bounds how long that takes.
DEFAULT_TIMEOUT_MS = 30_000
#: The most elements (in the document and its shadow roots) a page may have
#: for axe-core to run on it. axe-core takes up to about 1.3 ms an element
#: on a large page (26 s for 20,000 elements; 0.7 ms on the field corpus,
#: whose largest page had 5,400): past this, one page's run could take the
#: capture past its render deadline (fetch.DEFAULT_RENDER_DEADLINE_S) and
#: lose the whole capture rather than axe-core's part.
MAX_PAGE_ELEMENTS = 20_000
#: The parts a run takes axe-core's rules in (DEFAULT_TIMEOUT_MS): the two
#: that take longest on a large page, each alone, then the rest together.
RUN_PARTS = (("color-contrast",), ("target-size",))


class AxeUnavailable(RuntimeError):
    """axe-core cannot be run: the vendored file is missing or is not the
    pinned release."""


_SOURCE: str | None = None


def axe_source() -> str:
    """axe-core's code, read from the package and checked against
    AXE_SHA256 (AxeUnavailable when it is missing or differs)."""
    global _SOURCE
    if _SOURCE is not None:
        return _SOURCE
    try:
        ref = resources.files("bellbriar_harness").joinpath(*AXE_FILE)
        data = ref.read_bytes()
    except (OSError, ValueError) as exc:
        raise AxeUnavailable(
            f"the vendored axe-core is missing ({type(exc).__name__})") \
            from None
    digest = hashlib.sha256(data).hexdigest()
    if digest != AXE_SHA256:
        raise AxeUnavailable(
            f"the vendored axe-core is not the pinned {AXE_VERSION}: its "
            f"SHA-256 is {digest}, not {AXE_SHA256}")
    _SOURCE = data.decode("utf-8")
    return _SOURCE


def bellbriar_rule(axe_rule: str) -> str | None:
    """The Bellbriar rule that reports `axe_rule`, or None."""
    for bb, ax in AXE_RULES.items():
        if ax == axe_rule:
            return bb
    return None


def rule_order() -> list[str]:
    """axe-core's rules in the order a run records their results, which
    decides whose go uncounted-for first past MAX_ELEMENTS: those of the
    rules that can fail (the bundled rulebook's verdict_basis sc or
    heuristic) first, then those of the rules that never fail."""
    from .engine import NEVER_FAIL_BASES, load_rulebook
    basis = {r["id"]: r.get("verdict_basis")
             for r in load_rulebook()["rules"]}
    return sorted(set(AXE_RULES.values()), key=lambda ax: (
        basis.get(bellbriar_rule(ax)) in NEVER_FAIL_BASES, ax))


def run_parts(rules) -> list[list[str]]:
    """`rules` in the parts a run takes them in (RUN_PARTS)."""
    rules = list(rules)
    alone = [list(p) for p in RUN_PARTS if all(r in rules for r in p)]
    rest = [r for r in rules if not any(r in p for p in alone)]
    return alone + ([rest] if rest else [])


#: The isolated world's helper. Defined in that world only, under KEY: no
#: page script can reach the world, so the name needs no secret. Answers
#: are plain values the protocol returns by value.
#:
#: `run` runs axe-core, in parts, and keeps each element it reported. Right
#: before the capture, `paths` says where each of them is (the index of
#: each node among its parent's child nodes, from the document down) and
#: starts watching the page's structure; after it, `changed` says which of
#: those places the page changed before the capture began (its first stamp
#: under the name `paths` was given), so the capture's marks on them cannot
#: be trusted. A place is changed when any node on the way to it had its
#: child nodes changed: the index of the next step may differ.
RUNNER_JS = r"""
(() => {
  "use strict";
  const KEY = "__bellbriar_axe";
  // A world made again under the same name is the same world: define all
  // this once. An own property, which no element's id can stand in for (a
  // window's named properties sit on its prototype chain).
  if (Object.getOwnPropertyDescriptor(window, KEY)) return;
  const proto = Element.prototype;
  const desc = Object.getOwnPropertyDescriptor(proto, "shadowRoot");
  const closed = new WeakMap();
  // axe-core walks into a component through node.shadowRoot. Here, and only
  // here, that also returns the closed roots the protocol found, so axe-core
  // evaluates what the capture serializes.
  Object.defineProperty(proto, "shadowRoot", {
    configurable: true, enumerable: desc.enumerable,
    get() { return desc.get.call(this) || closed.get(this) || null; }});

  // The closed shadow roots passed in: answers the indices of those it now
  // walks into (all of them, but for any that is not a closed root).
  function register() {
    const got = [];
    for (let i = 0; i < arguments.length; i++) {
      try {
        const r = arguments[i], h = r && r.host;
        if (h && !desc.get.call(h) && (!closed.has(h) || closed.get(h) === r)) {
          closed.set(h, r);
          got.push(i);
        }
      } catch (e) {}
    }
    return got;
  }

  // Every element of the document and of every shadow root this world
  // reaches (open ones, and the closed ones registered), and those roots.
  function composed() {
    const els = [], roots = [], queue = [document];
    for (let qi = 0; qi < queue.length; qi++) {
      for (const el of queue[qi].querySelectorAll("*")) {
        els.push(el);
        const r = el.shadowRoot;
        if (r) { queue.push(r); roots.push(r); }
      }
    }
    return {els: els, roots: roots};
  }

  const SEVERITY = ["critical", "serious", "moderate", "minor"];
  function worse(a, b) {
    const i = SEVERITY.indexOf(a), j = SEVERITY.indexOf(b);
    if (i < 0) return j < 0 ? "" : b;
    return j >= 0 && j < i ? b : a;
  }

  function messages(node) {
    const out = [];
    for (const group of ["none", "all", "any"]) {
      for (const c of node[group] || []) {
        if (c && typeof c.message === "string" && c.message) out.push(c.message);
      }
    }
    return out;
  }

  let state = null;

  async function run(rules, parts, budgetMs, maxElements, maxPage) {
    state = null;
    const started = performance.now();
    const before = composed();
    if (before.els.length > maxPage) {
      return {status: "too-large", elements: before.els.length};
    }
    const startSet = new WeakSet(before.els);
    let changes = 0;
    const mo = new MutationObserver((records) => { changes += records.length; });
    const watch = {subtree: true, childList: true, attributes: true,
                   characterData: true};
    mo.observe(document, watch);
    for (const r of before.roots) mo.observe(r, watch);
    const found = {violations: [], incomplete: []};
    const applicable = [], inapplicable = [], help = {}, notRun = [];
    try {
      for (let p = 0; p < parts.length; p++) {
        const left = budgetMs - (performance.now() - started);
        if (left <= 0) { notRun.push(...parts[p]); continue; }
        let timer = null;
        const late = new Promise((resolve) => {
          timer = setTimeout(() => resolve(null), left);
        });
        let res = null;
        try {
          res = await Promise.race([axe.run(document, {
            runOnly: {type: "rule", values: parts[p]},
            resultTypes: ["violations", "incomplete"],
            elementRef: true, iframes: false, selectors: false,
            ancestry: false, xpath: false, absolutePaths: false,
            preload: false, restoreScroll: true, performanceTimer: false}),
            late]);
        } finally {
          clearTimeout(timer);
        }
        if (!res) {
          // axe-core is still waiting on something; it cannot be run again
          // until it is done, so this part and the rest are not run.
          for (let q = p; q < parts.length; q++) notRun.push(...parts[q]);
          break;
        }
        for (const kind of ["violations", "incomplete"]) {
          for (const r of res[kind] || []) {
            found[kind].push(r);
            help[r.id] = typeof r.help === "string" ? r.help : "";
          }
        }
        for (const kind of ["violations", "incomplete", "passes"]) {
          for (const r of res[kind] || []) {
            if (!applicable.includes(r.id)) applicable.push(r.id);
          }
        }
        for (const r of res.inapplicable || []) {
          if (!applicable.includes(r.id) && !inapplicable.includes(r.id)) {
            inapplicable.push(r.id);
          }
        }
      }
    } finally {
      changes += mo.takeRecords().length;
      mo.disconnect();
    }
    const ms = Math.round(performance.now() - started);
    // Each result, failures first, then by `rules` (the order whose
    // results are recorded first when there are too many elements).
    const rank = new Map(rules.map((r, i) => [r, i]));
    const items = [];
    for (const kind of ["violations", "incomplete"]) {
      for (const r of found[kind]) {
        for (const node of r.nodes || []) {
          items.push({fail: kind === "violations", rule: r.id, node: node,
                      impact: typeof node.impact === "string" ? node.impact :
                              (typeof r.impact === "string" ? r.impact : "")});
        }
      }
    }
    items.sort((a, b) => (a.fail === b.fail ? 0 : a.fail ? -1 : 1) ||
                         ((rank.has(a.rule) ? rank.get(a.rule) : 1e9) -
                          (rank.has(b.rule) ? rank.get(b.rule) : 1e9)));
    const byEl = new Map(), els = [], entries = [], lost = {};
    const lose = (it) => {
      const l = lost[it.rule] || (lost[it.rule] = {f: 0, r: 0, i: ""});
      if (it.fail) { l.f++; l.i = worse(l.i, it.impact); } else { l.r++; }
    };
    for (const it of items) {
      const el = it.node.element;
      let entry = el ? byEl.get(el) : undefined;
      if (!entry) {
        if (!el || el.nodeType !== 1 || !el.isConnected ||
            els.length >= maxElements) { lose(it); continue; }
        entry = {k: els.length, results: []};
        byEl.set(el, entry);
        els.push(el);
        entries.push(entry);
      }
      entry.results.push({r: it.rule, v: it.fail ? "fail" : "review",
                          i: it.impact, c: messages(it.node)});
    }
    state = {els: els, startSet: startSet, seen: null, mo: null, chains: null};
    return {status: "ran", version: axe.version, ms: ms, changes: changes,
            applicable: applicable, inapplicable: inapplicable, help: help,
            entries: entries, lost: lost, notRun: notRun};
  }

  // Each element's place, from the document down: the index of each node
  // among its parent's child nodes with the node's local name, and ["s",
  // ""] to step into the shadow root of the element before it; and the
  // nodes whose child nodes those indices are into.
  function placeOf(el, indexOf) {
    const steps = [], chain = [];
    let n = el, guard = 0;
    while (n && n !== document && guard++ < 100000) {
      const p = n.parentNode;
      if (!p) return null;
      const i = indexOf(p, n);
      if (i < 0) return null;
      steps.push([i, n.localName]);
      chain.push(p);
      if (p.nodeType === 11) {
        if (!p.host) return null;
        steps.push(["s", ""]);
        n = p.host;
      } else {
        n = p;
      }
    }
    return n === document ? {steps: steps.reverse(), chain: chain} : null;
  }

  function paths(name) {
    if (!state) return null;
    const now = composed();
    let added = 0;
    for (const el of now.els) if (!state.startSet.has(el)) added++;
    // From here to the capture's first stamp under `name`, every change to
    // the page's structure is recorded (`changed`).
    const seen = {targets: new Set(), added: 0, boundary: false,
                  overflow: false, n: 0};
    const take = (records) => {
      for (const x of records) {
        if (seen.boundary || seen.overflow) return;
        if (x.type === "attributes") {
          if (x.attributeName === name) {
            seen.boundary = true;
            mo.disconnect();
            return;
          }
          continue;
        }
        // Past this many, the page changed everything as far as anyone
        // can tell: no mark stands (`changed`).
        if (++seen.n > 1000000) { seen.overflow = true; mo.disconnect(); return; }
        seen.targets.add(x.target);
        for (const a of x.addedNodes) {
          if (a.nodeType === 1) seen.added += 1 + a.getElementsByTagName("*").length;
        }
      }
    };
    const mo = new MutationObserver(take);
    const opts = {childList: true, subtree: true, attributes: true,
                  attributeFilter: [name]};
    mo.observe(document, opts);
    for (const r of now.roots) mo.observe(r, opts);
    const memo = new Map();
    const indexOf = (p, n) => {
      let m = memo.get(p);
      if (!m) {
        m = new Map();
        const kids = p.childNodes;
        for (let i = 0; i < kids.length; i++) m.set(kids[i], i);
        memo.set(p, m);
      }
      return m.has(n) ? m.get(n) : -1;
    };
    const out = [], gone = [], chains = [];
    for (let k = 0; k < state.els.length; k++) {
      const el = state.els[k];
      const place = el.isConnected ? placeOf(el, indexOf) : null;
      if (!place) { gone.push(k); chains.push(null); continue; }
      out.push([k, place.steps]);
      chains.push(place.chain);
    }
    state.seen = seen; state.mo = mo; state.take = take; state.chains = chains;
    return {places: out, gone: gone, added: added};
  }

  function changed() {
    if (!state || !state.mo) return null;
    state.take(state.mo.takeRecords());
    state.mo.disconnect();
    const s = state.seen;
    state.mo = null;
    // No stamp seen (and no flood that hid it): the capture never began.
    if (!s.boundary && !s.overflow) return {boundary: false};
    const invalid = [];
    for (let k = 0; k < state.chains.length; k++) {
      const ch = state.chains[k];
      if (!ch) continue;
      if (s.overflow) { invalid.push(k); continue; }
      for (const n of ch) {
        if (s.targets.has(n)) { invalid.push(k); break; }
      }
    }
    return {boundary: true, invalid: invalid, added: s.added,
            overflow: s.overflow};
  }

  Object.defineProperty(window, KEY, {
    value: {register: register, run: run, paths: paths, changed: changed},
    writable: false, configurable: false, enumerable: false});
})();
"""


def _clean(text, limit: int = MAX_MESSAGE, axe_text: bool = False) -> str:
    """`text` on one line and at most `limit` characters; axe-core's own
    text (`axe_text`) is HTML ("&lt;li&gt;"), read once as such."""
    text = html.unescape(str(text)) if axe_text else str(text)
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _int(value, high: int = 10 ** 9) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) \
        and 0 <= value <= high else None


#: How long one of axe-core's check texts may be, as the capture keeps it.
#: A longer one is not quoted rather than cut: a cut could keep part of a
#: run secret that the run's scrub, which reads the text whole, could no
#: longer find (R5L-2). The message is cut to MAX_MESSAGE where the
#: finding is made, after that scrub (checks_static._f).
MAX_CHECK_TEXT = 2000


def _check_text(text) -> str:
    """One check text, unescaped, its white space as axe-core wrote it but
    at its ends: the finding's message reads the run's password across a
    line break (redact.holds_password) before it makes its white space one
    space."""
    text = html.unescape(str(text)).strip()
    return (text if len(text) <= MAX_CHECK_TEXT else
            f"(a text of {len(text):,} characters, not quoted)")


def message(axe_rule: str, help_text: str, checks, verdict: str) -> str:
    """One finding's message: axe-core's summary of the rule, what its
    checks found on the element (each whole: MAX_CHECK_TEXT), and where the
    verdict came from."""
    found = "; ".join(_check_text(c)
                      for c in checks if isinstance(c, str) and c)
    # axe-core's own words, which hold nothing of the page's.
    head = _clean(help_text or axe_rule, 200, axe_text=True)
    text = f"{head}: {found}" if found else head
    if verdict == "review":
        text = f"axe-core could not decide, so this needs a person's review. {text}"
    return f"{text} [axe-core {AXE_VERSION} {axe_rule}]"


class Unexpected(ValueError):
    """axe-core's answer is not what the isolated world's helper gives."""


class AxeAnswer:
    """One axe-core run's answer (RUNNER_JS `run`), checked, and what the
    capture makes of it: each element's results (`results`, by the index
    `k` the isolated world keeps the element under), and, for each rule,
    the results that no element in the snapshot carries (`lost`: failures,
    reviews, and the most severe impact among the failures)."""

    def __init__(self, applicable, inapplicable, results, lost, not_run,
                 changes: int):
        self.applicable: list[str] = applicable
        self.inapplicable: list[str] = inapplicable
        self.results: dict[int, list[dict]] = results
        self.lost: dict[str, dict] = lost
        self.not_run: list[str] = not_run
        self.changes = changes

    def lose(self, k: int) -> None:
        """Count element `k`'s results as not attached to any element."""
        for res in self.results.pop(k, ()):
            entry = self.lost.setdefault(res["r"], {"f": 0, "r": 0, "i": ""})
            if res["v"] == "fail":
                entry["f"] += 1
                entry["i"] = worse(entry["i"], res["i"])
            else:
                entry["r"] += 1

    def mark(self, k: int) -> str:
        """The record element `k` carries: its results, as JSON."""
        return json.dumps(self.results[k], ensure_ascii=False,
                          separators=(",", ":"))

    def not_located(self) -> int:
        return sum(e["f"] + e["r"] for e in self.lost.values())

    def run_record(self, unchecked: int) -> str:
        """The run's record for the root element: the version, the rules
        that applied and did not, the results no element carries, by rule,
        and how many elements of the snapshot axe-core could not check
        (inside closed shadow roots it was not given)."""
        return json.dumps({
            "engine": "axe-core", "version": AXE_VERSION,
            "applicable": self.applicable, "inapplicable": self.inapplicable,
            "unplaced": {r: dict(e) for r, e in sorted(self.lost.items())
                         if e["f"] or e["r"]},
            "unchecked": unchecked}, separators=(",", ":"))


def worse(a: str, b: str) -> str:
    """The more severe of two Bellbriar impacts ("" is none)."""
    if a not in SEVERITY:
        return b if b in SEVERITY else ""
    return b if b in SEVERITY and SEVERITY.index(b) < SEVERITY.index(a) else a


def read_answer(out, timeout_ms: int = DEFAULT_TIMEOUT_MS
                ) -> tuple[AxeAnswer | None, dict, list[str]]:
    """axe-core's answer from the isolated world, checked: (the answer, or
    None when there is nothing to record; the capture record's `axe` block;
    notes). Only rules in AXE_RULES are kept. Anything not in the shape the
    helper gives is taken as no answer: the rules are then not evaluated,
    which is never a pass."""
    block = {"engine": "axe-core", "version": AXE_VERSION,
             "sha256": AXE_SHA256, "ran": False}
    notes: list[str] = []
    if not isinstance(out, dict):
        block["reason"] = "axe-core gave no answer"
        return None, block, notes
    if out.get("status") == "too-large":
        size = _int(out.get("elements")) or 0
        block["reason"] = (f"the page has {size:,} elements, more than the "
                           f"{MAX_PAGE_ELEMENTS:,} axe-core is run on")
        return None, block, notes
    try:
        answer = _checked(out)
    except Unexpected:
        block["reason"] = "axe-core answered something unexpected"
        return None, block, notes
    if not (answer.applicable or answer.inapplicable):
        block["reason"] = (f"axe-core did not finish within "
                           f"{timeout_ms / 1000:g} s")
        return None, block, notes
    block.update({"ran": True, "rules": sorted(answer.applicable
                                               + answer.inapplicable)})
    if answer.not_run:
        block["not_run"] = sorted(answer.not_run)
        notes.append(
            f"axe-core used up its {timeout_ms / 1000:g} s on this page, so "
            f"{len(answer.not_run)} of its rules were not run and were not "
            f"evaluated ({', '.join(sorted(answer.not_run))})")
    if answer.changes:
        notes.append("the page changed while axe-core ran; its results "
                     "describe each element as axe-core read it")
    return answer, block, notes


def _checked(out: dict) -> AxeAnswer:
    if out.get("status") != "ran" or out.get("version") != AXE_VERSION:
        raise Unexpected("status")
    wanted = set(AXE_RULES.values())

    def rules(key) -> list[str]:
        value = out.get(key)
        if not (isinstance(value, list) and all(isinstance(r, str)
                                                for r in value)):
            raise Unexpected(key)
        return sorted({r for r in value if r in wanted})
    applicable = rules("applicable")
    inapplicable = sorted(set(rules("inapplicable")) - set(applicable))
    not_run = sorted(set(rules("notRun")) - set(applicable)
                     - set(inapplicable))
    help_texts = out.get("help") if isinstance(out.get("help"), dict) else {}
    results: dict[int, list[dict]] = {}
    entries = out.get("entries")
    if not isinstance(entries, list) or len(entries) > MAX_ELEMENTS:
        raise Unexpected("entries")
    for entry in entries:
        k = _int(entry.get("k"), MAX_ELEMENTS - 1) if isinstance(
            entry, dict) else None
        found = entry.get("results") if isinstance(entry, dict) else None
        if k is None or k in results or not isinstance(found, list) \
                or not found:
            raise Unexpected("entry")
        kept = []
        for res in found:
            if not (isinstance(res, dict) and isinstance(res.get("r"), str)
                    and res.get("v") in ("fail", "review")):
                raise Unexpected("result")
            if res["r"] not in wanted:
                continue
            if res["r"] not in applicable:
                raise Unexpected("result rule")
            verdict = res["v"]
            # What axe-core could not decide is a minor review, whatever
            # impact a failure would have had: --strict never gates it.
            impact = (IMPACTS.get(res.get("i"), "moderate")
                      if verdict == "fail" else "minor")
            checks = res.get("c") if isinstance(res.get("c"), list) else []
            kept.append({"r": res["r"], "v": verdict, "i": impact,
                         "m": message(res["r"], help_texts.get(res["r"], ""),
                                      checks, verdict)})
        results[k] = kept
    lost: dict[str, dict] = {}
    raw = out.get("lost")
    if not isinstance(raw, dict):
        raise Unexpected("lost")
    for rule, entry in raw.items():
        if not (isinstance(entry, dict) and _int(entry.get("f")) is not None
                and _int(entry.get("r")) is not None
                and isinstance(entry.get("i"), str)):
            raise Unexpected("lost entry")
        if rule not in wanted:
            continue
        if rule not in applicable:
            raise Unexpected("lost rule")
        lost[rule] = {"f": entry["f"], "r": entry["r"],
                      "i": IMPACTS.get(entry["i"], "moderate")
                      if entry["f"] else ""}
    answer = AxeAnswer(applicable, inapplicable, {}, lost, not_run,
                       _int(out.get("changes")) or 0)
    for k, kept in results.items():
        if kept:
            answer.results[k] = kept
    return answer


def read_run(value) -> dict | None:
    """The run's record from the root element's attribute, or None when it
    is not one (then no axe-core rule was evaluated on the page)."""
    try:
        run = json.loads(value)
    except (TypeError, ValueError):
        return None
    if not (isinstance(run, dict) and run.get("engine") == "axe-core"
            and isinstance(run.get("version"), str)
            and isinstance(run.get("applicable"), list)
            and isinstance(run.get("inapplicable"), list)
            and isinstance(run.get("unplaced"), dict)
            and _int(run.get("unchecked")) is not None):
        return None
    unplaced = {}
    for rule, entry in run["unplaced"].items():
        if not (isinstance(entry, dict) and _int(entry.get("f")) is not None
                and _int(entry.get("r")) is not None
                and (entry.get("i") in SEVERITY
                     or (entry.get("i") == "" and not entry["f"]))):
            return None
        unplaced[rule] = {"f": entry["f"], "r": entry["r"], "i": entry["i"]}
    run["unplaced"] = unplaced
    run["applicable"] = [r for r in run["applicable"] if isinstance(r, str)]
    run["inapplicable"] = [r for r in run["inapplicable"]
                           if isinstance(r, str)]
    return run


def read_mark(value) -> list[dict]:
    """One element's results from its attribute: [{"r", "v", "i", "m"}]."""
    try:
        results = json.loads(value)
    except (TypeError, ValueError):
        return []
    if not isinstance(results, list):
        return []
    out = []
    for res in results:
        if (isinstance(res, dict) and isinstance(res.get("r"), str)
                and res.get("v") in ("fail", "review")
                and res.get("i") in IMPACTS.values()
                and isinstance(res.get("m"), str)):
            out.append(res)
    return out
