"""Fetching a page to evaluate — server HTML, or the hydrated DOM.

Why this module exists: `--url` used to read only the HTML a server sends.
On a component-framework or heavy-CMS site — which is most hospital,
university and government work — the content a user actually meets is
built by JavaScript after load, so the rules were reading a skeleton and
reporting it clean. A page whose rendered DOM carries a missing alt and an
empty button returned "Tier-1 clean, 100%". Understating a customer's
exposure is the worst thing this tool can do, so rendering is the default
whenever a browser is available, and a fallback to server HTML is loud.

Provenance. Rendering pulls in what third-party tags inject into the same
document — consent banners, chat launchers, booking widgets. On a
realistic page those outnumber the customer's own defects several to one,
and the customer cannot edit any of them. So before any page script runs
we instrument the DOM insertion entry points and record, for each inserted
subtree, which code inserted it. Markup is attributed to a *vendor* — and
reported without being scored (`references/scope-and-exclusions.md`
EXC-1) — only when every script on the call stack is cross-origin and one
of them belongs to a known vendor (KNOWN_VENDOR_DOMAINS, extendable with
`--third-party-origin`). If the page's own origin is anywhere on the stack
the markup is first-party; if the code is cross-origin but not a known
vendor (the site's own CDN, or a library loaded from a public CDN) it is
"cross-origin" and scored. Unknown provenance is always scored.

Attribution is never kept in the live DOM, where page code could read or
forge it. It lives in a closure the page cannot reach, and is written onto
the captured markup only at capture time, under an attribute name chosen at
random for that capture and removed again before any page code runs. The
rules honor attribution only under that name (FetchResult.provenance_attr),
so markup that declares its own provenance is ignored. The capture is
called over the DevTools protocol, not through JavaScript in the page's
realm, and uses only built-ins saved before page scripts ran and
prototype-less lists, and creates and clones no element, so page code
cannot read the names from the call, run during the capture, or change
what it returns. A page can still keep content out of the capture (the
shadow roots below) or serve the harness different content; nothing here
detects either.

The capture also serializes shadow roots (as <bb-shadow-root> elements,
with slotted content placed where it renders): open ones, and closed ones
— those the page's scripts attach with its own attachShadow, recorded by
the instrumentation, and every other closed root (declarative, in the HTML
or in markup passed to setHTMLUnsafe, or attached through another frame's
attachShadow), found over the DevTools protocol at any depth in the page
(_closed_shadow_roots; inside one component's closed root, to
CLOSED_ROOT_SCAN_DEPTH levels, and deeper is noted). A root the page
attaches between that search and the capture is missed. It scrolls the
page first, so content built inside web components or revealed on scroll
is evaluated rather than silently missed. It records
each <audio> and <video> element's `muted` property, under a second name
derived from the same secret (model.muted_attr): React and other frameworks
set `muted` as a property only, so the markup alone would show a muted
autoplay video as playing with sound.

The snapshot we hash is exactly the markup the rules were run over,
provenance attributes included, so anyone re-running the rules on the
snapshot with `--provenance-attr <recorded name>` reproduces our numbers.

Secrets. Protected staging and preview pages are reached with credentials
(`http_credentials`, offered only to the origin of the URL, and only when
that origin asks) or with an access token in the query. Neither is ever
recorded or printed: every URL a FetchResult holds has passed through
redact.redact_url, and every message that may quote a URL through
redact.redact_text. A URL with a user name or password in it is refused
outright — it has already leaked into shell history and CI logs.
"""
from __future__ import annotations

import base64
import contextlib
import hashlib
import ipaddress
import json
import re
import secrets
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .bundle import (_ADDRESS, _LABEL_DOTS, _ipv4_shorthand, _site,
                     address_kind, host_kind, host_scope,
                     normalize_host, url_host)
from .model import (MARKS_VERSION, axe_attr, axe_run_attr, capture_attr,
                    hidden_attr, muted_attr, narrow_changed_attr,
                    narrow_hidden_attr, reflow_attr, reflow_run_attr)
from .redact import names, printable, redact_text, redact_url, secret_values

#: Longest stretch of an error's text kept in a message or a record. Page
#: scripts can throw errors of any size, and that text lands in
#: fallback_reason.
MAX_ERROR_TEXT = 500

#: Attribute name used before per-capture names existed. Pages can write it
#: themselves, so the rules no longer trust it; kept for reference only.
ORIGIN_ATTR = "data-bb-origin"

FIRST_PARTY = "first-party"
THIRD_PARTY = "third-party"
CROSS_ORIGIN = "cross-origin"   # cross-origin code that is not a listed vendor
SERVER = "server"          # present in the HTML the server sent
UNKNOWN = "unknown"

DEFAULT_VIEWPORT = {"width": 1280, "height": 1024}
DEFAULT_SETTLE_MS = 500
DEFAULT_SETTLE_CAP_MS = 8000
DEFAULT_TIMEOUT_MS = 30000
DEFAULT_SCROLL_STEPS = 30
DEFAULT_SCROLL_PAUSE_MS = 100

#: Registrable domains of vendors whose injected widgets are reported but
#: not scored (EXC-1). Deliberately a list, not a rule: "cross-origin" alone
#: is not "vendor" — a site's own CDN, or a framework loaded from a public
#: CDN, renders the customer's own UI. Public library CDNs (cdnjs, jsDelivr,
#: unpkg, esm.sh, code.jquery.com, ajax.googleapis.com) are intentionally
#: absent. Extend per run with --third-party-origin.
VENDOR_LIST_VERSION = "2026-09-30"
KNOWN_VENDOR_DOMAINS = (
    # consent and privacy managers
    "onetrust.com", "cookielaw.org", "cookiepro.com", "cookiebot.com",
    "usercentrics.eu", "trustarc.com", "truste.com", "termly.io",
    "iubenda.com", "osano.com", "didomi.io", "cookieyes.com",
    "cookie-script.com", "consentmanager.net", "cookiefirst.com",
    "civiccomputing.com", "privacy-mgmt.com", "quantcast.com",
    # chat, support and messaging
    "intercom.io", "intercomcdn.com", "intercomassets.com", "drift.com",
    "driftt.com", "zendesk.com", "zdassets.com", "zopim.com",
    "livechatinc.com", "tawk.to", "crisp.chat", "hubspot.com",
    "hs-scripts.com", "hs-banner.com", "hsforms.net", "hs-analytics.net",
    "usemessages.com", "freshchat.com", "freshworks.com", "olark.com",
    "tidio.co", "tidiochat.com", "gorgias.chat", "helpscout.net",
    "chatra.io", "smartsupp.com", "userlike.com", "qualified.com",
    "podium.com", "birdeye.com", "liveperson.net", "lpsnmedia.net",
    "salesforceliveagent.com", "comm100.com", "kustomerapp.com",
    "frontapp.com", "ada.support",
    # booking and scheduling
    "calendly.com", "acuityscheduling.com", "zocdoc.com", "opentable.com",
    "resy.com", "mindbodyonline.com", "vagaro.com", "setmore.com",
    "youcanbook.me", "simplybook.me", "squareup.com", "sevenrooms.com",
    "exploretock.com",
    # analytics, tag managers, advertising and experimentation
    "googletagmanager.com", "google-analytics.com", "doubleclick.net",
    "googlesyndication.com", "googleadservices.com", "facebook.net",
    "hotjar.com", "clarity.ms", "segment.com", "segment.io",
    "optimizely.com", "visualwebsiteoptimizer.com", "fullstory.com",
    "mouseflow.com", "crazyegg.com", "heapanalytics.com", "mixpanel.com",
    "licdn.com", "ads-twitter.com", "bat.bing.com", "pinimg.com",
    "redditstatic.com", "analytics.tiktok.com", "taboola.com",
    "outbrain.com", "adroll.com", "criteo.net", "quantserve.com",
    # accessibility overlays
    "accessibe.com", "acsbapp.com", "userway.org", "audioeye.com",
    "equalweb.com", "reciteme.com",
    # reviews, social and embeds
    "trustpilot.com", "yotpo.com", "stamped.io", "judge.me", "okendo.io",
    "elfsight.com", "powr.io", "instagram.com", "platform.twitter.com",
    "facebook.com",
    # payments, captcha and maps
    "stripe.com", "stripe.network", "paypal.com", "paypalobjects.com",
    "klarna.com", "klarnaservices.com", "afterpay.com", "affirm.com",
    "hcaptcha.com", "recaptcha.net", "maps.googleapis.com", "mapbox.com",
)

#: Injected before any page script. Records which code inserted each
#: element — in a closure, never in the DOM — and exposes one capture entry
#: point under a per-run property name. Every primitive it relies on is
#: captured before page scripts run, so a page cannot redefine what it
#: reads; anything it cannot establish degrades to "unknown" (scored).
#: Wrapped in try/catch throughout: instrumentation must never change how
#: the page behaves.
_INSTRUMENT_TEMPLATE = r"""
(() => {
  "use strict";
  const PROP = "%PROP%";
  const VENDOR_DOMAINS = %VENDOR_DOMAINS%;
  const VENDOR_ORIGINS = %VENDOR_ORIGINS%;
  const SELF = "bellbriar-instrumentation.js";

  const apply = Reflect.apply;
  const gopd = Object.getOwnPropertyDescriptor;
  const defProp = Object.defineProperty;
  const getProto = Object.getPrototypeOf;
  const setProto = Object.setPrototypeOf;
  const SYM_ITER = Symbol.iterator;
  const isArray = Array.isArray;
  const WM = WeakMap, WMp = WeakMap.prototype;
  const wmGet = WMp.get, wmSet = WMp.set, wmHas = WMp.has;
  const arrPush = Array.prototype.push;
  const strSlice = String.prototype.slice;
  const strIndexOf = String.prototype.indexOf;
  const strLower = String.prototype.toLowerCase;
  const reExec = RegExp.prototype.exec;
  const URLC = URL;
  const urlOrigin = gopd(URL.prototype, "origin").get;
  const urlHost = gopd(URL.prototype, "hostname").get;
  const E = Error;
  const captureST = Error.captureStackTrace;
  const nodeTypeGet = gopd(Node.prototype, "nodeType").get;
  const parentGet = gopd(Node.prototype, "parentNode").get;
  const childNodesGet = gopd(Node.prototype, "childNodes").get;
  const nlLength = gopd(NodeList.prototype, "length").get;
  const nlItem = NodeList.prototype.item;
  const shadowRootGet = gopd(Element.prototype, "shadowRoot").get;
  const localNameGet = gopd(Element.prototype, "localName").get;
  let mutedGet = null;   // throws on anything but a real media element
  try { mutedGet = gopd(HTMLMediaElement.prototype, "muted").get; } catch (e) {}
  const hostGet = gopd(ShadowRoot.prototype, "host").get;
  const docQsa = Document.prototype.querySelectorAll;
  const frQsa = DocumentFragment.prototype.querySelectorAll;
  const setAttr = Element.prototype.setAttribute;
  const removeAttr = Element.prototype.removeAttribute;
  const hasAttr = Element.prototype.hasAttribute;
  const getAttr = Element.prototype.getAttribute;
  const createEl = Document.prototype.createElement;
  const addListener = EventTarget.prototype.addEventListener;
  const getHTML = Element.prototype.getHTML;
  const outerGet = gopd(Element.prototype, "outerHTML").get;
  const innerGet = gopd(Element.prototype, "innerHTML").get;
  const docElGet = gopd(Document.prototype, "documentElement").get;
  const bodyGet = gopd(Document.prototype, "body").get;
  const doctypeGet = gopd(Document.prototype, "doctype").get;
  const nsGet = gopd(Element.prototype, "namespaceURI").get;
  // What an element of a drawing Chromium does not know is (<foo>, <font>).
  const svgProto = typeof SVGElement === "function" ? SVGElement.prototype
                                                    : null;
  const checkVis = typeof Element.prototype.checkVisibility === "function"
                   ? Element.prototype.checkVisibility : null;
  const assignedEls = typeof HTMLSlotElement === "function"
                      ? HTMLSlotElement.prototype.assignedElements : null;
  const getCS = window.getComputedStyle;
  const getPV = CSSStyleDeclaration.prototype.getPropertyValue;
  const scrollWidthGet = gopd(Element.prototype, "scrollWidth").get;
  const clientWidthGet = gopd(Element.prototype, "clientWidth").get;
  const scrollLeftGet = gopd(Element.prototype, "scrollLeft").get;
  const gbcr = Element.prototype.getBoundingClientRect;
  const rectRight = gopd(DOMRectReadOnly.prototype, "right").get;
  const rectWidth = gopd(DOMRectReadOnly.prototype, "width").get;
  const mRound = Math.round;
  const isConnGet = gopd(Node.prototype, "isConnected").get;
  const nodeValueGet = gopd(Node.prototype, "nodeValue").get;
  const createRange = Document.prototype.createRange;
  const rangeSelect = Range.prototype.selectNodeContents;
  const rangeRects = Range.prototype.getClientRects;
  const rlLength = gopd(DOMRectList.prototype, "length").get;
  const rlItem = DOMRectList.prototype.item;
  const MO = typeof MutationObserver === "function" ? MutationObserver : null;
  const moObserve = MO ? MO.prototype.observe : null;
  const moTake = MO ? MO.prototype.takeRecords : null;
  const moDisconnect = MO ? MO.prototype.disconnect : null;
  let mrTarget = null, mrType = null, mrAttrName = null;
  try {
    mrTarget = gopd(MutationRecord.prototype, "target").get;
    mrType = gopd(MutationRecord.prototype, "type").get;
    mrAttrName = gopd(MutationRecord.prototype, "attributeName").get;
  } catch (e) { mrTarget = null; }
  // Only the harness's own calls know these: a page that finds the entry
  // points (Object.getOwnPropertyNames(window) lists them) cannot take a
  // capture of its own, which would replace the list of elements the
  // narrow record names (capture), nor take that record (recordNarrow).
  const CAPTURE_TOKEN = "%CAPTURE_TOKEN%";
  const NARROW_TOKEN = "%NARROW_TOKEN%";
  const HTML_NS = "http://www.w3.org/1999/xhtml";
  // Never rendered by design, or the page's frame (html, head, body): their
  // hiding is not the page hiding content, and no rule reads it.
  const UNMARKED = {__proto__: null, html: 1, head: 1, body: 1, script: 1,
                    style: 1, link: 1, meta: 1, base: 1, title: 1,
                    template: 1, noscript: 1, option: 1, optgroup: 1,
                    datalist: 1, source: 1, track: 1, param: 1, area: 1};
  const XS = XMLSerializer;
  const xsSerialize = XMLSerializer.prototype.serializeToString;
  const pageOrigin = location.origin;
  const doc = document;

  if (gopd(window, PROP)) return;

  const origins = new WeakMap();      // Element | ShadowRoot -> origin
  const rootsByHost = new WeakMap();  // host -> ShadowRoot (closed ones too)

  // Call-site methods, captured once, so a page cannot patch them later.
  let csFile = null, csScript = null, csIsEval = null, csEvalOrigin = null;
  try {
    const probe = {};
    const saved = E.prepareStackTrace;
    E.prepareStackTrace = (err, cs) => cs;
    apply(captureST, E, [probe]);
    const cs = probe.stack;
    E.prepareStackTrace = saved;
    if (isArray(cs) && cs.length) {
      const p = getProto(cs[0]);
      csFile = p.getFileName; csScript = p.getScriptNameOrSourceURL;
      csIsEval = p.isEval; csEvalOrigin = p.getEvalOrigin;
    }
  } catch (e) {}
  // Pin both knobs as plain non-configurable data properties: pages may
  // still assign them, but cannot turn them into accessors that answer the
  // instrumentation differently from V8.
  try { defProp(E, "prepareStackTrace", {value: E.prepareStackTrace,
        writable: true, configurable: false, enumerable: false}); } catch (e) {}
  try { defProp(E, "stackTraceLimit", {value: E.stackTraceLimit,
        writable: true, configurable: false, enumerable: true}); } catch (e) {}

  const HTTP = /^https?:\/\//;
  const URL_IN = /https?:\/\/[^\s)'"]+/;
  const grab = (err, cs) => cs;

  function callSites() {
    if (!csFile) return null;
    let savedPrep, savedLimit, cs = null;
    try {
      savedPrep = E.prepareStackTrace; savedLimit = E.stackTraceLimit;
      E.prepareStackTrace = grab; E.stackTraceLimit = 200;
      if (E.prepareStackTrace !== grab || E.stackTraceLimit !== 200) return null;
      const holder = {};
      apply(captureST, E, [holder]);
      cs = holder.stack;
    } catch (e) { cs = null; }
    finally {
      try { E.prepareStackTrace = savedPrep; E.stackTraceLimit = savedLimit; } catch (e) {}
    }
    return isArray(cs) ? cs : null;
  }

  function frameUrl(c) {
    let u = "";
    try { u = apply(csScript, c, []) || apply(csFile, c, []) || ""; } catch (e) { u = ""; }
    if (!u) {
      try {
        if (apply(csIsEval, c, [])) {
          const m = apply(reExec, URL_IN, [apply(csEvalOrigin, c, []) || ""]);
          if (m) u = m[0];
        }
      } catch (e) {}
    }
    return typeof u === "string" ? u : "";
  }

  function isVendor(origin, host) {
    for (let i = 0; i < VENDOR_ORIGINS.length; i++) {
      if (origin === VENDOR_ORIGINS[i]) return true;
    }
    for (let i = 0; i < VENDOR_DOMAINS.length; i++) {
      const d = VENDOR_DOMAINS[i];
      if (host === d) return true;
      const tail = "." + d;
      if (host.length > tail.length &&
          apply(strSlice, host, [host.length - tail.length]) === tail) return true;
    }
    return false;
  }

  function originOfCaller() {
    try {
      const cs = callSites();
      if (!cs) return "unknown";
      let firstCross = "", vendor = "", sawUrl = false;
      for (let i = 0; i < cs.length; i++) {
        const u = frameUrl(cs[i]);
        if (!u || u === SELF || apply(reExec, HTTP, [u]) === null) continue;
        let o = "", h = "";
        try { const x = new URLC(u); o = apply(urlOrigin, x, []); h = apply(urlHost, x, []); }
        catch (e) { continue; }
        sawUrl = true;
        if (o === pageOrigin) return "first-party";   // the site's own code is involved
        if (!firstCross) firstCross = o;
        if (!vendor && isVendor(o, h)) vendor = o;
      }
      if (!sawUrl) return "first-party";   // inline or eval'd code of the page itself
      if (vendor) return "third-party:" + vendor;
      return "cross-origin:" + firstCross;
    } catch (e) { return "unknown"; }
  }

  function tag(node, origin) {
    try {
      if (!node || apply(nodeTypeGet, node, []) !== 1) return;
      if (apply(wmHas, origins, [node])) return;          // first attribution wins
      apply(wmSet, origins, [node, origin]);
    } catch (e) {}
  }

  // A list with no prototype. Pushing to or reading from an ordinary array
  // consults Array.prototype, where a page can define index accessors and
  // so run its own code in the middle of a capture.
  function newList() {
    const a = [];
    setProto(a, null);
    return a;
  }

  // An iterable over a list, for a WebIDL sequence argument, whose protocol
  // runs nothing the page can replace (no Array.prototype[@@iterator], no
  // %ArrayIteratorPrototype%.next).
  function safeSeq(list) {
    let i = 0;
    const it = {__proto__: null};
    it.next = function () {
      const r = {__proto__: null};
      if (i < list.length) { r.value = list[i]; i++; r.done = false; }
      else { r.value = undefined; r.done = true; }
      return r;
    };
    const s = {__proto__: null};
    s[SYM_ITER] = function () { return it; };
    return s;
  }

  function nodesOf(list) {
    const out = newList();
    try {
      const n = apply(nlLength, list, []);
      for (let i = 0; i < n; i++) apply(arrPush, out, [apply(nlItem, list, [i])]);
    } catch (e) {}
    return out;
  }

  function childrenOf(node) {
    try { return nodesOf(apply(childNodesGet, node, [])); } catch (e) { return newList(); }
  }

  // Elements an insertion call will place: the element arguments, and the
  // children of fragment arguments (read BEFORE the call empties them).
  function insertedBy(args) {
    const out = [];
    for (let i = 0; i < args.length; i++) {
      const a = args[i];
      try {
        if (!a || typeof a !== "object") continue;
        const t = apply(nodeTypeGet, a, []);
        if (t === 1) apply(arrPush, out, [a]);
        else if (t === 11) {
          const kids = childrenOf(a);
          for (let j = 0; j < kids.length; j++) apply(arrPush, out, [kids[j]]);
        }
      } catch (e) {}
    }
    return out;
  }

  function wrapInsert(proto, name, pick) {
    try {
      const orig = proto[name];
      if (typeof orig !== "function") return;
      proto[name] = function (...args) {
        let origin = "unknown", targets = [];
        try { origin = originOfCaller(); targets = insertedBy(pick(args)); } catch (e) {}
        const out = apply(orig, this, args);
        for (let i = 0; i < targets.length; i++) tag(targets[i], origin);
        return out;
      };
    } catch (e) {}
  }

  wrapInsert(Node.prototype, "appendChild", (a) => [a[0]]);
  wrapInsert(Node.prototype, "insertBefore", (a) => [a[0]]);
  wrapInsert(Node.prototype, "replaceChild", (a) => [a[0]]);
  wrapInsert(Element.prototype, "append", (a) => a);
  wrapInsert(Element.prototype, "prepend", (a) => a);
  wrapInsert(Element.prototype, "before", (a) => a);
  wrapInsert(Element.prototype, "after", (a) => a);
  wrapInsert(Element.prototype, "replaceWith", (a) => a);
  wrapInsert(Element.prototype, "replaceChildren", (a) => a);
  wrapInsert(Element.prototype, "insertAdjacentElement", (a) => [a[1]]);
  wrapInsert(DocumentFragment.prototype, "append", (a) => a);
  wrapInsert(DocumentFragment.prototype, "prepend", (a) => a);

  // HTML-string insertions: tag exactly the children that are new.
  function wrapHtmlInsert(proto, name, scopes) {
    try {
      const orig = proto[name];
      if (typeof orig !== "function") return;
      proto[name] = function (...args) {
        let origin = "unknown", before = [];
        try {
          origin = originOfCaller();
          const sc = scopes(this);
          for (let i = 0; i < sc.length; i++) apply(arrPush, before, [childrenOf(sc[i])]);
        } catch (e) {}
        const out = apply(orig, this, args);
        try {
          const sc = scopes(this);
          for (let i = 0; i < sc.length; i++) {
            const now = childrenOf(sc[i]), was = before[i] || [];
            for (let j = 0; j < now.length; j++) {
              let seen = false;
              for (let k = 0; k < was.length; k++) if (was[k] === now[j]) { seen = true; break; }
              if (!seen) tag(now[j], origin);
            }
          }
        } catch (e) {}
        return out;
      };
    } catch (e) {}
  }
  const selfAndParent = (el) => {
    const out = [el];
    try { const p = apply(parentGet, el, []); if (p) apply(arrPush, out, [p]); } catch (e) {}
    return out;
  };
  wrapHtmlInsert(Element.prototype, "insertAdjacentHTML", selfAndParent);
  wrapHtmlInsert(Element.prototype, "setHTMLUnsafe", (el) => [el]);

  for (const [prop, scopes] of [["innerHTML", (el) => [el]],
                                ["outerHTML", (el) => {
                                   try { const p = apply(parentGet, el, []); return p ? [p] : []; }
                                   catch (e) { return []; } }]]) {
    try {
      const d = gopd(Element.prototype, prop);
      if (!d || !d.set) continue;
      defProp(Element.prototype, prop, {
        configurable: true, enumerable: d.enumerable, get: d.get,
        set: function (v) {
          let origin = "unknown", before = [], sc = [];
          try {
            origin = originOfCaller(); sc = scopes(this);
            for (let i = 0; i < sc.length; i++) apply(arrPush, before, [childrenOf(sc[i])]);
          } catch (e) {}
          apply(d.set, this, [v]);
          try {
            for (let i = 0; i < sc.length; i++) {
              const now = childrenOf(sc[i]), was = before[i] || [];
              for (let j = 0; j < now.length; j++) {
                let seen = false;
                for (let k = 0; k < was.length; k++) if (was[k] === now[j]) { seen = true; break; }
                if (!seen) tag(now[j], origin);
              }
            }
          } catch (e) {}
        },
      });
    } catch (e) {}
  }

  // Shadow roots: remember every root (closed ones are otherwise
  // unreachable) and the code that attached it. Content inside a root
  // inherits that origin unless something tagged it more precisely.
  try {
    const origAttach = Element.prototype.attachShadow;
    if (typeof origAttach === "function") {
      Element.prototype.attachShadow = function (...args) {
        const root = apply(origAttach, this, args);
        try {
          apply(wmSet, rootsByHost, [this, root]);
          if (!apply(wmHas, origins, [root])) apply(wmSet, origins, [root, originOfCaller()]);
        } catch (e) {}
        return root;
      };
    }
  } catch (e) {}

  function originFor(el) {
    let n = el;
    for (let guard = 0; n && guard < 100000; guard++) {
      if (apply(wmHas, origins, [n])) return apply(wmGet, origins, [n]);
      let p = null;
      try { p = apply(parentGet, n, []); } catch (e) { p = null; }
      if (!p) return "server";
      let t = 0;
      try { t = apply(nodeTypeGet, p, []); } catch (e) { t = 0; }
      if (t === 11) {
        if (apply(wmHas, origins, [p])) return apply(wmGet, origins, [p]);
        try { n = apply(hostGet, p, []); } catch (e) { n = null; }
        continue;
      }
      n = p;
    }
    return "server";   // nothing on the chain was inserted by script
  }

  // Slotted light-DOM children render inside the <slot> they are assigned
  // to, and the static rules read them there (materialize_shadow_roots):
  // the capture fills this map before it reads what is hidden.
  let slotOf = null;

  // The element a hidden subtree hangs from, in the flat tree: the <slot> a
  // light-DOM child is assigned to, else the parent, or the host of a
  // shadow root's top-level element.
  function flatParent(n) {
    if (slotOf && apply(wmHas, slotOf, [n])) return apply(wmGet, slotOf, [n]);
    let p = null, t = 0;
    try { p = apply(parentGet, n, []); } catch (e) { return null; }
    if (!p) return null;
    try { t = apply(nodeTypeGet, p, []); } catch (e) { return null; }
    if (t === 11) { try { return apply(hostGet, p, []); } catch (e) { return null; } }
    return t === 1 ? p : null;
  }

  // An HTML element, or the outermost <svg> or <math> in HTML: the parts
  // of an SVG drawing (<title>, <defs>) are not content a rule hides.
  function markable(el) {
    let ln = "", ns = "", pns = HTML_NS;
    try { ln = apply(localNameGet, el, []); ns = apply(nsGet, el, []); }
    catch (e) { return false; }
    if (UNMARKED[ln] === 1) return false;
    if (ns === HTML_NS) return true;
    const p = flatParent(el);
    try { if (p) pns = apply(nsGet, p, []); } catch (e) { return false; }
    return pns === HTML_NS;
  }

  // The element at a place the harness's own isolated world found an
  // axe-core result's element at, just before this capture (axe.py,
  // RUNNER_JS `paths`): from the document down, each step the index of a
  // child node and that node's local name, or "s" into the shadow root of
  // the element reached so far, open or closed. Every name must match, or
  // the result is not placed. The isolated world then checks that the page
  // changed none of the child lists on the way before the capture began
  // (`changed`); a mark it cannot vouch for is dropped and counted. Reads
  // only own properties of the harness's literal and built-ins saved
  // before page scripts ran.
  function resolvePath(steps) {
    let node = doc;
    let n = 0;
    try { n = steps.length; } catch (e) { return null; }
    for (let k = 0; k < n && k < 4096; k++) {
      let st = null, a = null, ln = "";
      try { st = steps[k]; a = st[0]; ln = st[1]; } catch (e) { return null; }
      if (a === "s") {
        let root = null;
        try { root = apply(shadowRootGet, node, []); } catch (e) { root = null; }
        if (!root && apply(wmHas, rootsByHost, [node])) root = apply(wmGet, rootsByHost, [node]);
        if (!root) return null;
        node = root;
        continue;
      }
      if (typeof a !== "number") return null;
      let child = null;
      try {
        const kids = apply(childNodesGet, node, []);
        if (!(a >= 0 && a < apply(nlLength, kids, []))) return null;
        child = apply(nlItem, kids, [a]);
        if (!child || apply(nodeTypeGet, child, []) !== 1 ||
            apply(localNameGet, child, []) !== ln) return null;
      } catch (e) { return null; }
      node = child;
    }
    return node === doc ? null : node;
  }

  // Closed shadow roots no page script can reach (declarative ones, and
  // ones attached through another frame), found over the DevTools protocol
  // and passed in as the caller's own `arguments` object: its indices and
  // length are own data properties, so reading them runs no page code. The
  // ShadowRoot host getter, saved before page scripts ran, throws for
  // anything that is not a shadow root.
  function registerClosed(closed) {
    if (!closed) return;
    let n = 0;
    try { n = closed.length; } catch (e) { n = 0; }
    for (let i = 0; i < n && i < 1000000; i++) {
      try {
        const r = closed[i];
        const h = apply(hostGet, r, []);
        if (h && !apply(wmHas, rootsByHost, [h])) apply(wmSet, rootsByHost, [h, r]);
      } catch (e) {}
    }
  }

  // Every element of the document and of every shadow root (the
  // document's, then each root's, each in tree order), the roots, and the
  // <audio> and <video> elements; and the scopes, the document then each
  // root, with the scope each root's host is in and how many elements each
  // holds. Every list is prototype-less.
  function listAll() {
    const els = newList(), roots = newList(), queue = newList(), media = newList();
    const parentOf = newList(), sizes = newList();
    apply(arrPush, queue, [doc]);
    apply(arrPush, parentOf, [-1]);
    const seen = new WM();
    for (let qi = 0; qi < queue.length; qi++) {
      const scope = queue[qi];
      const list = qi === 0 ? apply(docQsa, doc, ["*"]) : apply(frQsa, scope, ["*"]);
      const found = nodesOf(list);
      apply(arrPush, sizes, [found.length]);
      for (let i = 0; i < found.length; i++) {
        const el = found[i];
        apply(arrPush, els, [el]);
        try {
          const ln = apply(localNameGet, el, []);
          if (ln === "audio" || ln === "video") apply(arrPush, media, [el]);
        } catch (e) {}
        let root = null;
        try { root = apply(shadowRootGet, el, []); } catch (e) { root = null; }
        if (!root && apply(wmHas, rootsByHost, [el])) root = apply(wmGet, rootsByHost, [el]);
        if (root && !apply(wmHas, seen, [root])) {
          apply(wmSet, seen, [root, true]);
          apply(arrPush, queue, [root]);
          apply(arrPush, roots, [root]);
          apply(arrPush, parentOf, [qi]);
        }
      }
    }
    const out = {__proto__: null};
    out.els = els; out.roots = roots; out.media = media;
    out.scopes = queue; out.parentOf = parentOf; out.sizes = sizes;
    return out;
  }

  // What the page changes after the capture, until the narrow record is
  // taken (recordNarrow), element by element: OWN where an element's own
  // attributes change, or it is inserted (or moved) into the page; HELD
  // where only what it holds changes, its child nodes or its text (for a
  // shadow root's, its host). The page sets an attribute, or swaps
  // content, when a media query starts matching (an aria-hidden="false"
  // on the menu shown on phones): the snapshot shows such an element as it
  // was at the capture's own width, so what the narrow record finds about
  // it cannot be confirmed (engine.merge_views). A change of class, style,
  // hidden or a data- attribute is not counted: what those do is show or
  // hide content, and the narrow record measures what is shown. Watched
  // with built-ins saved before page scripts ran, by an observer no page
  // script can reach.
  const OWN = 2, HELD = 1;
  const STYLING = {__proto__: null, "class": 1, style: 1, hidden: 1};
  let watcher = null, changedEls = null, changeN = 0, changeOver = false;
  let mrAdded = null;
  try { mrAdded = gopd(MutationRecord.prototype, "addedNodes").get; } catch (e) {}
  function noteChange(t, kind) {
    try {
      let tt = apply(nodeTypeGet, t, []);
      if (tt === 11) { t = apply(hostGet, t, []); tt = t ? 1 : 0; kind = HELD; }
      if (tt !== 1) return;
      const was = apply(wmHas, changedEls, [t]) ? apply(wmGet, changedEls, [t]) : 0;
      if (kind > was) apply(wmSet, changedEls, [t, kind]);
    } catch (e) {}
  }
  function noteChanges(records) {
    let n = 0;
    try { n = records.length; } catch (e) { n = 0; }
    for (let i = 0; i < n; i++) {
      if (changeOver) return;
      try {
        const rec = records[i];
        const type = apply(mrType, rec, []);
        if (type === "attributes") {
          const an = apply(mrAttrName, rec, []);
          if (typeof an !== "string" || STYLING[an] === 1 ||
              apply(strSlice, an, [0, 5]) === "data-") continue;
        }
        // Past this many changes the page changed everything, as far as
        // the narrow record can tell (recordNarrow's changedAll).
        if (++changeN > 1000000) { changeOver = true; return; }
        const t = apply(mrTarget, rec, []);
        if (type === "attributes") {
          noteChange(t, OWN);
        } else if (type === "characterData") {
          const p = apply(parentGet, t, []);       // its text changed
          if (p) noteChange(p, HELD);
        } else {
          noteChange(t, HELD);
          const added = mrAdded ? nodesOf(apply(mrAdded, rec, [])) : newList();
          for (let j = 0; j < added.length; j++) noteChange(added[j], OWN);
        }
      } catch (e) {}
    }
  }
  function startWatch(scopes) {
    changedEls = new WM(); changeN = 0; changeOver = false;
    if (watcher) { try { apply(moDisconnect, watcher, []); } catch (e) {} }
    watcher = null;
    if (!MO || !mrTarget) return;
    try {
      const w = new MO(noteChanges);
      const o = {__proto__: null};
      o.childList = true; o.subtree = true; o.attributes = true; o.characterData = true;
      for (let i = 0; i < scopes.length; i++) apply(moObserve, w, [scopes[i], o]);
      watcher = w;
    } catch (e) { watcher = null; }
  }

  // Slotted light-DOM children render inside the <slot> they are assigned
  // to (flatParent reads this map).
  function computeSlots(roots) {
    slotOf = new WM();
    for (let i = 0; assignedEls && i < roots.length; i++) {
      let slots = null;
      try { slots = nodesOf(apply(frQsa, roots[i], ["slot"])); } catch (e) { slots = null; }
      for (let j = 0; slots && j < slots.length; j++) {
        let got = null;
        try { got = apply(assignedEls, slots[j], []); } catch (e) { got = null; }
        let n = 0;
        try { n = got ? got.length : 0; } catch (e) { n = 0; }
        for (let k = 0; k < n && k < 1000000; k++) {
          try { apply(wmSet, slotOf, [got[k], slots[j]]); } catch (e) {}
        }
      }
    }
  }

  // What the page, as rendered at the current viewport, hides: for each of
  // `els`, "display", "visibility", "shown", "skips", "shown-skips",
  // "visibility-skips", "unrendered", "unboxed", "unrendered-visibility",
  // "unboxed-visibility" or ""
  // (marks), and whether the
  // <body> itself is hidden. checkVisibility() is false where display:none
  // (or content-visibility:hidden) takes an element out of rendering, and
  // with visibilityProperty also where visibility hides it. Only the
  // element where hiding starts is marked; its subtree is hidden with it.
  // The options object has no prototype, so reading it runs nothing the
  // page can define. Needs computeSlots first.
  function hidingOf(els) {
    const visOpts = {__proto__: null};
    visOpts.visibilityProperty = true;
    const states = new WM();      // element -> 0 not rendered, 1 invisible, 2 shown
    const inCanvas = new WM();    // element -> inside a <canvas>?
    const isCanvas = (n) => {
      try {
        return apply(localNameGet, n, []) === "canvas" &&
               apply(nsGet, n, []) === HTML_NS;
      } catch (e) { return false; }
    };
    // Walked up iteratively and remembered for every element passed, so a
    // deep page costs one walk, not one per element.
    const fallback = (n) => {
      const path = newList();
      let p = flatParent(n), found = false, k = 0;
      while (p && k++ < 1000000) {
        if (isCanvas(p)) { found = true; break; }
        if (apply(wmHas, inCanvas, [p])) { found = apply(wmGet, inCanvas, [p]); break; }
        apply(arrPush, path, [p]);
        p = flatParent(p);
      }
      for (let i = 0; i < path.length; i++) apply(wmSet, inCanvas, [path[i], found]);
      apply(wmSet, inCanvas, [n, found]);
      return found;
    };
    // A drawing's container that has a box Chromium 141 never paints, nor
    // lets what it holds take focus: <defs>, <symbol>, a clip path, a
    // mask, a pattern, a marker, and a <g> with display:none (which
    // Chromium boxes as it boxes <defs>: measured, R6C-3).
    // checkVisibility() is true on it and on what it holds; it is not
    // rendered.
    const SVG_HIDDEN_BOX = {__proto__: null, defs: 1, symbol: 1,
                            clipPath: 1, mask: 1, pattern: 1, marker: 1};
    const hiddenBox = (n) => {
      try {
        if (apply(nsGet, n, []) !== SVG_NS) return false;
        const ln = apply(localNameGet, n, []);
        if (SVG_HIDDEN_BOX[ln] === 1) return true;
        return ln === "g" && apply(getPV, apply(getCS, window, [n]),
                                   ["display"]) === "none";
      } catch (e) { return false; }
    };
    // Its state as checkVisibility() alone has it (hiddenBox aside).
    const rawOf = (n) => {
      try {
        if (apply(checkVis, n, [visOpts]) === true) return 2;
        return apply(checkVis, n, []) === true ? 1 : 0;
      } catch (e) { return 2; }
    };
    // Its visibility as its computed style has it (1 invisible, 2
    // visible): inside what is not rendered, where checkVisibility() is
    // false throughout, that is what names go by (R6E-4).
    const visOf = (n) => {
      try {
        const v = apply(getPV, apply(getCS, window, [n]), ["visibility"]);
        return v === "hidden" || v === "collapse" ? 1 : 2;
      } catch (e) { return 2; }
    };
    // An element with display:contents (a <slot>, by default) has no box of
    // its own, so checkVisibility() is false, yet its children render: it
    // takes its parent's state. Fallback content inside a <canvas> has no
    // box either, yet a browser lets it take focus while the canvas is
    // rendered: it is as shown as its parent unless its own style hides it.
    const stateOf = (n) => {
      if (apply(wmHas, states, [n])) return apply(wmGet, states, [n]);
      let s = 2;
      try {
        if (hiddenBox(n)) {
          s = 0;
        } else if (apply(checkVis, n, [visOpts]) !== true) {
          const p = flatParent(n);
          const cs = apply(getCS, window, [n]);
          const disp = apply(getPV, cs, ["display"]);
          if (disp === "contents") {
            s = p ? stateOf(p) : 2;
          } else if (p && fallback(n)) {
            const ps = stateOf(p), vis = apply(getPV, cs, ["visibility"]);
            s = ps === 0 || disp === "none" ? 0
              : vis === "hidden" || vis === "collapse" ? 1 : 2;
          } else {
            s = apply(checkVis, n, []) !== true ? 0 : 1;
          }
        }
      } catch (e) { s = 2; }
      apply(wmSet, states, [n, s]);
      return s;
    };
    // A rendered element that does not render what it holds:
    // content-visibility:hidden (hidden="until-found" sets it) on a box
    // whose content Chromium skips (style.RENDERING_DISPLAYS, measured: an
    // inline box, an inline list item, a table and its parts but a cell,
    // ruby and its text render what they hold, every other box skips it;
    // a <button>, a <fieldset>, a <canvas> and an element of a drawing
    // skip it whatever they compute; a <textarea>'s text is its value,
    // which stays; R5K-10, R5L-1, R5N-6, R5O-7, R5P-4, R5Q-7). The computed
    // display is a float's or a flex item's as blockified. Its child
    // elements are marked "display" where they can be; its own text is not
    // an element.
    const RENDERING = {__proto__: null, "inline": 1, "inline list-item": 1,
                       "table": 1, "inline-table": 1, "table-row-group": 1,
                       "table-header-group": 1, "table-footer-group": 1,
                       "table-row": 1, "table-column-group": 1,
                       "table-column": 1, "table-caption": 1, "ruby": 1,
                       "ruby-text": 1, "contents": 1, "none": 1};
    const BOXED = {__proto__: null, button: 1, canvas: 1, fieldset: 1};
    const VALUES = {__proto__: null, textarea: 1, input: 1};
    const SVG_NS = "http://www.w3.org/2000/svg";
    // A part of a drawing or of MathML (not HTML); a drawing's <title> and
    // <desc>, its name and its description, never rendered, are never
    // marked.
    const SVG_TEXTS = {__proto__: null, title: 1, desc: 1};
    const partMarkable = (n) => {
      try {
        const ns = apply(nsGet, n, []);
        if (ns === HTML_NS) return false;
        return !(ns === SVG_NS && SVG_TEXTS[apply(localNameGet, n, [])] === 1);
      } catch (e) { return false; }
    };
    // The mark of a part that is not rendered (`ps`: its parent's state),
    // as Chromium 141 reads such a part into names (measured, R6C-3).
    // "display", whatever its parent, where it leaves it out with what it
    // holds: one whose own display is none (but a drawing's <g> or
    // <marker>: R6G-3); and of a drawing, an element Chromium does not
    // know (<foo>, <rdf:RDF>, <font>), a <metadata>, a <view>, an
    // animation's element, what such one or a <use> holds, a filter
    // primitive (<feFlood>), a <tspan> or <textPath> in neither a <text>
    // nor an <a>, an element in a <text> that is no part of one (a <g>,
    // in an <a> in one too), and one whose conditions fail (condFails: a
    // systemLanguage, or a requiredExtensions Chromium does not pass, on
    // one that is not rendered while its parent is).
    // Where rendering stops at one it reads: "unrendered" for a container
    // Chromium boxes but does not paint (hiddenBox: <defs>, a <g> with
    // display:none, a <marker> whatever its display) and a MathML part
    // (what <mspace> holds), read with what it holds, as aria-labelledby
    // reads it (Chromium gives a name from content from no MathML, where
    // the runs read it: L92); "unboxed" for any other part of a drawing
    // (the <g>, <text>, <a>, <svg> or <foreignObject> a <switch> passes
    // over, what a filter, a gradient, a shape or an <image> holds), read
    // only where no part whose role is group (a <g>, an inner <svg>, an
    // <a> that is no link) stands between it and where the name starts,
    // nearer than another <a>, and none of what a part of it whose role
    // is group (a <g>, an <a> that is no link) holds (accname, R6I-4).
    // What a hiddenBox holds is boxed, as checkVisibility() has it: its
    // parts are marked as though the box were rendered (R6E-6).
    const SVG_LEFT_OUT = {__proto__: null, metadata: 1, view: 1, use: 1,
                          animate: 1, set: 1, animateMotion: 1,
                          animateTransform: 1, mpath: 1};
    const SVG_TEXT = {__proto__: null, text: 1, tspan: 1, textPath: 1};
    const SVG_IN_TEXT = {__proto__: null, text: 1, tspan: 1, textPath: 1,
                         a: 1, title: 1, desc: 1};
    // The elements whose conditions Chromium 141 reads (R6G-8), and a
    // requiredExtensions it passes: the extensions it has, split at ASCII
    // white space, none before the first (measured: R6G-7, R6K-2).
    const SVG_TESTS = {__proto__: null, a: 1, animate: 1, animateMotion: 1,
                       animateTransform: 1, circle: 1, defs: 1, ellipse: 1,
                       foreignObject: 1, g: 1, image: 1, line: 1, mask: 1,
                       path: 1, pattern: 1, polygon: 1, polyline: 1,
                       rect: 1, set: 1, svg: 1, switch: 1, text: 1,
                       textPath: 1, tspan: 1, use: 1};
    // (Literals: a page cannot have replaced their constructor.)
    const EXT_SPACE = /^[ \t\n\f\r]/;
    const EXT_TOKEN = /[^ \t\n\f\r]+/g;
    const extensionsPass = (v) => {
      if (v === "" || apply(reExec, EXT_SPACE, [v]) !== null) return false;
      EXT_TOKEN.lastIndex = 0;
      let m;
      while ((m = apply(reExec, EXT_TOKEN, [v])) !== null) {
        const t = m[0];
        if (t !== "http://www.w3.org/1999/xhtml" &&
            t !== "http://www.w3.org/1998/Math/MathML") return false;
      }
      return true;
    };
    // Does the part fail its own conditions: a systemLanguage, which the
    // capture cannot tell (the browser's languages decide; it is read as
    // failing, as Chromium had it where measured), or a requiredExtensions
    // Chromium does not pass? One whose conditions pass, not rendered for
    // another reason (a box that never paints), is marked as such (R6K-3).
    const condFails = (n, ln) => {
      if (SVG_TESTS[ln] !== 1) return false;
      if (apply(hasAttr, n, ["systemLanguage"])) return true;
      if (!apply(hasAttr, n, ["requiredExtensions"])) return false;
      const v = apply(getAttr, n, ["requiredExtensions"]);
      return !extensionsPass(v === null ? "" : v);
    };
    const partMark = (n, ps) => {
      try {
        const ns = apply(nsGet, n, []), ln = apply(localNameGet, n, []);
        const cs = apply(getCS, window, [n]);
        const none = apply(getPV, cs, ["display"]) === "none";
        const g = ns === SVG_NS && ln === "g";
        if (none && !g && !(ns === SVG_NS && ln === "marker"))
          return "display";
        if (ns !== SVG_NS) return ps === 0 ? "" : "unrendered";
        if (svgProto && getProto(n) === svgProto) return "display";
        const p = flatParent(n);
        const box = SVG_HIDDEN_BOX[ln] === 1 || (g && none);
        let pln = "";
        if (p && apply(nsGet, p, []) === SVG_NS)
          pln = apply(localNameGet, p, []);
        if (SVG_LEFT_OUT[ln] === 1 || SVG_LEFT_OUT[pln] === 1 ||
            (ln[0] === "f" && ln[1] === "e")) return "display";
        if ((ln === "tspan" || ln === "textPath") &&
            SVG_TEXT[pln] !== 1 && pln !== "a") return "display";
        // What holds it, past any <a>: an <a> holds what its own holder
        // may (a <g> in an <a> in a <text>: R6O-3, R6Q-3).
        let hn = p, hln = pln;
        for (let k = 0; hln === "a" && hn && k < 512; k++) {
          hn = flatParent(hn);
          hln = hn && apply(nsGet, hn, []) === SVG_NS
            ? apply(localNameGet, hn, []) : "";
        }
        if (SVG_TEXT[hln] === 1 && SVG_IN_TEXT[ln] !== 1) return "display";
        const live = ps !== 0 || (!!p && rawOf(p) !== 0);
        if (!live) return "";
        if (condFails(n, ln)) return "display";
        return box ? "unrendered" : "unboxed";
      } catch (e) { return ps === 0 ? "" : "unboxed"; }
    };
    const skipsContent = (n) => {
      try {
        const cs = apply(getCS, window, [n]);
        if (apply(getPV, cs, ["content-visibility"]) !== "hidden") return false;
        const d = apply(getPV, cs, ["display"]);
        if (d === "none" || d === "contents") return false;
        const ln = apply(localNameGet, n, []), ns = apply(nsGet, n, []);
        if (ns === HTML_NS && VALUES[ln] === 1) return false;
        if (ns === SVG_NS || (ns === HTML_NS && BOXED[ln] === 1)) return true;
        return RENDERING[d] !== 1;
      } catch (e) { return false; }
    };
    // Marked where the state changes from the parent's: "display" where
    // rendering stops, "visibility" where content turns invisible, and
    // "shown" where an element inside invisible content is made visible
    // again (visibility:visible), which it can be, focus included; and
    // "skips" on a rendered element that skips what it holds ("shown-skips"
    // where it is made visible again too, "visibility-skips" where it is
    // invisible, whatever its parent: R5O-5). A part of a drawing or of
    // MathML that is not rendered is marked as Chromium 141 reads it into
    // names (partMark: "display", "unrendered" or "unboxed", R6C-3). What
    // a hiddenBox holds is marked where it turns invisible or is made
    // visible again as against the box's own visibility, as
    // checkVisibility() has it; the box's mark keeps it not rendered,
    // "unrendered-visibility" where it is invisible itself, which nothing
    // made visible again inside it shows (R6E-5). Inside what is not
    // rendered but read (what an "unrendered" or "unboxed" part holds),
    // visibility is the computed style's: "unrendered-visibility" where it
    // turns invisible ("unboxed-visibility" on an "unboxed" part), "shown"
    // where it is made visible again (R6E-4).
    // element -> inside what is not rendered but read?
    const inPart = new WM();
    const PARTS = {__proto__: null, "unrendered": 1, "unboxed": 1};
    const marks = newList();
    for (let i = 0; i < els.length; i++) {
      let mark = "";
      try {
        const el = els[i], s = stateOf(el);
        const p = flatParent(el), ps = p ? stateOf(p) : 2;
        let part = s === 0 && ps === 0 && !!p &&
                   apply(wmGet, inPart, [p]) === true;
        let m = "";
        if (s === 0 && ps !== 0) m = "display";
        else if (s === 1 && skipsContent(el)) m = "visibility-skips";
        else if (s === 1 && ps === 2) m = "visibility";
        else if (s === 2 && ps === 1)
          m = skipsContent(el) ? "shown-skips" : "shown";
        else if (s === 2 && skipsContent(el)) m = "skips";
        else if (s === 1 && p && hiddenBox(p) && rawOf(p) === 2)
          m = "visibility";
        else if (s === 2 && p && hiddenBox(p) && rawOf(p) === 1)
          m = skipsContent(el) ? "shown-skips" : "shown";
        // The marks land on the parts of a drawing or of MathML too (a <g>
        // or a <text> invisible, made visible again, or skipping what it
        // holds: R5R-3, R6A-4), but on a drawing's <title> and <desc>.
        if (partMarkable(el)) {
          if (s === 0) {
            m = partMark(el, ps);
            if (m === "unrendered" && hiddenBox(el) && rawOf(el) === 1 &&
                (p ? rawOf(p) : 2) === 2) m = "unrendered-visibility";
            else if (PARTS[m] === 1 && !hiddenBox(el)) part = true;
          }
        }
        if (part && m !== "display") {
          const v = visOf(el), pv = p ? visOf(p) : 2;
          if (v === 1 && pv === 2)
            m = m === "unboxed" ? "unboxed-visibility"
              : "unrendered-visibility";
          else if (v === 2 && pv === 1 && m === "") m = "shown";
        } else if (m === "display") part = false;
        apply(wmSet, inPart, [el, part]);
        if (partMarkable(el) || part) mark = m;
        else if (m && (m === "shown" || m === "shown-skips" ||
                       markable(el)))
          mark = m;
      } catch (e) { mark = ""; }
      apply(arrPush, marks, [mark]);
    }
    let bodyHidden = false;
    try {
      const body = apply(bodyGet, doc, []);
      bodyHidden = !!(body && stateOf(body) !== 2);
    } catch (e) {}
    const out = {__proto__: null};
    out.marks = marks; out.bodyHidden = bodyHidden;
    return out;
  }

  // Content a page may lay out in two dimensions (WCAG 1.4.10's exception):
  // an overflow it holds is reviewed, not failed.
  const EXEMPT = {__proto__: null, table: 1, pre: 1, img: 1, svg: 1, canvas: 1,
                  video: 1, iframe: 1, object: 1, embed: 1, picture: 1, math: 1};
  const EXEMPT_ROLES = {__proto__: null, table: 1, grid: 1, treegrid: 1,
                        img: 1, image: 1, application: 1};
  const MAX_OVERFLOW = 50;
  const FINE = 0, OVER = 1, UNDER = 2, CLIPPED = 3;

  const FIRST_TOKEN = /^[\t\n\f\r ]*([^\t\n\f\r ]+)/;
  function exemptKind(el) {
    try {
      if (EXEMPT[apply(localNameGet, el, [])] === 1) return true;
      const role = apply(getAttr, el, ["role"]);
      const m = typeof role === "string" ? apply(reExec, FIRST_TOKEN, [role]) : null;
      if (m && EXEMPT_ROLES[apply(strLower, m[1], [])] === 1) return true;
    } catch (e) {}
    return false;
  }

  const CONTROLS = {__proto__: null, input: 1, select: 1, textarea: 1, button: 1};
  const NONSPACE = /[^\t\n\f\r ]/;
  const MAX_LOOK = 20000;

  // Does this text node show text past `edge`, within `bound` (the right
  // edge of the nearest element around it that clips its content)?
  function textPast(node, bound, edge, sx) {
    let v = "";
    try { v = apply(nodeValueGet, node, []); } catch (e) { return false; }
    if (typeof v !== "string" || apply(reExec, NONSPACE, [v]) === null) return false;
    try {
      const range = apply(createRange, doc, []);
      apply(rangeSelect, range, [node]);
      const rects = apply(rangeRects, range, []);
      const n = apply(rlLength, rects, []);
      for (let i = 0; i < n && i < 10000; i++) {
        const r = apply(rlItem, rects, [i]);
        const right = apply(rectRight, r, []) + sx;
        if (apply(rectWidth, r, []) > 0 && (right < bound ? right : bound) > edge) return true;
      }
    } catch (e) {}
    return false;
  }

  // What, in `el` (an outermost element reaching past the page's edge),
  // reaches past it: "c" when text or a form control does, which must
  // reflow; "x" when only content WCAG 1.4.10 exempts does (a table, an
  // image, code…: content that needs two dimensions); "e" when nothing it
  // shows does, only its box. Inside an element that clips or scrolls its
  // content sideways, only what shows within that element counts; what is
  // fixed to the viewport does not widen the page, and invisible text or
  // controls (visibility: hidden, a closed off-canvas menu) show nothing.
  // A shadow root's content is looked through as well as the host's own
  // children. An element inside exempt content (the <code> in a <pre>, a
  // cell's content) is that content.
  function overflowKind(el, cw, sx) {
    if (exemptKind(el)) return "x";
    for (let p = flatParent(el), k = 0; p && k < 100000; p = flatParent(p), k++) {
      if (exemptKind(p)) return "x";
    }
    const edge = cw + 1;
    let exempt = false;
    const qn = newList(), qb = newList();
    apply(arrPush, qn, [el]); apply(arrPush, qb, [Infinity]);
    for (let qi = 0; qi < qn.length; qi++) {
      if (qi >= MAX_LOOK) return "c";     // too much to look through: as if text
      const n = qn[qi], bound = qb[qi];
      let shows = true;              // does n's own text show?
      try {
        const v = apply(getPV, apply(getCS, window, [n]), ["visibility"]);
        shows = v !== "hidden" && v !== "collapse";
      } catch (e) { shows = true; }
      const kids = childrenOf(n);
      let root = null;
      try { root = apply(shadowRootGet, n, []); } catch (e) { root = null; }
      if (!root && apply(wmHas, rootsByHost, [n])) root = apply(wmGet, rootsByHost, [n]);
      if (root) {
        const more = childrenOf(root);
        for (let j = 0; j < more.length; j++) apply(arrPush, kids, [more[j]]);
      }
      for (let j = 0; j < kids.length; j++) {
        const c = kids[j];
        let t = 0;
        try { t = apply(nodeTypeGet, c, []); } catch (e) { continue; }
        if (t === 3) {
          if (shows && textPast(c, bound, edge, sx)) return "c";
          continue;
        }
        if (t !== 1) continue;
        let pos = "", ovx = "", vis = "";
        try {
          const cs = apply(getCS, window, [c]);
          pos = apply(getPV, cs, ["position"]); ovx = apply(getPV, cs, ["overflow-x"]);
          vis = apply(getPV, cs, ["visibility"]);
        } catch (e) {}
        if (pos === "fixed") continue;
        let right = 0, width = 0;
        try {
          const r = apply(gbcr, c, []);
          right = apply(rectRight, r, []) + sx; width = apply(rectWidth, r, []);
        } catch (e) { right = 0; width = 0; }
        const past = width > 0 && (right < bound ? right : bound) > edge;
        if (exemptKind(c)) { if (past) exempt = true; continue; }
        let ln = "";
        try { ln = apply(localNameGet, c, []); } catch (e) {}
        if (past && CONTROLS[ln] === 1 && vis !== "hidden" && vis !== "collapse") return "c";
        const clips = ovx === "hidden" || ovx === "clip" || ovx === "auto" || ovx === "scroll";
        apply(arrPush, qn, [c]);
        apply(arrPush, qb, [clips && right < bound ? right : bound]);
      }
    }
    return exempt ? "x" : "e";
  }

  // Does the viewport clip what reaches past its right edge, so the page
  // cannot scroll sideways at all? The root element's overflow-x, or the
  // <body>'s when the root's is visible: that is the one the viewport uses
  // (CSS Overflow 3). Then scrollWidth still counts what is cut off.
  function viewportClips() {
    let v = "";
    try { v = apply(getPV, apply(getCS, window, [apply(docElGet, doc, [])]), ["overflow-x"]); }
    catch (e) { v = ""; }
    if (v === "visible") {
      try {
        const b = apply(bodyGet, doc, []);
        if (b && apply(localNameGet, b, []) === "body" && apply(nsGet, b, []) === HTML_NS) {
          v = apply(getPV, apply(getCS, window, [b]), ["overflow-x"]);
        }
      } catch (e) {}
    }
    return v === "hidden" || v === "clip";
  }

  // The outermost elements whose box reaches past the right edge of the
  // page at the current viewport (`cw` CSS pixels wide), the ones that make
  // it scroll sideways: not inside an element that clips or scrolls its
  // content sideways, nor fixed to the viewport (neither scrolls the page).
  // Each is recorded with how far it reaches (document coordinates) and
  // what in it reaches that far (overflowKind). Returns how many were
  // recorded.
  function findOverflow(els, cw, scrollX) {
    const memo = new WM();         // element -> own state * 4 + what children inherit
    const own = (c, base) => {
      if (base === CLIPPED) return CLIPPED * 4 + CLIPPED;
      if (base === OVER || base === UNDER) return UNDER * 4 + UNDER;
      let cs = null;
      try { cs = apply(getCS, window, [c]); } catch (e) { cs = null; }
      let pos = "", ovx = "";
      try { pos = apply(getPV, cs, ["position"]); ovx = apply(getPV, cs, ["overflow-x"]); } catch (e) {}
      if (pos === "fixed") return CLIPPED * 4 + CLIPPED;
      let right = 0, width = 0;
      try {
        const r = apply(gbcr, c, []);
        right = apply(rectRight, r, []) + scrollX; width = apply(rectWidth, r, []);
      } catch (e) { right = 0; width = 0; }
      if (width > 0 && right > cw + 1) return OVER * 4 + UNDER;
      const clips = ovx === "hidden" || ovx === "clip" || ovx === "auto" || ovx === "scroll";
      return FINE * 4 + (clips ? CLIPPED : FINE);
    };
    const stateOf = (el) => {
      if (apply(wmHas, memo, [el])) return apply(wmGet, memo, [el]);
      const chain = newList();
      let n = el, base = FINE, k = 0;
      while (n && k++ < 1000000) {
        if (apply(wmHas, memo, [n])) { base = apply(wmGet, memo, [n]) % 4; break; }
        apply(arrPush, chain, [n]);
        n = flatParent(n);
      }
      for (let i = chain.length - 1; i >= 0; i--) {
        const v = own(chain[i], base);
        apply(wmSet, memo, [chain[i], v]);
        base = v % 4;
      }
      return apply(wmGet, memo, [el]);
    };
    let found = 0;
    for (let i = 0; i < els.length && found < MAX_OVERFLOW; i++) {
      const el = els[i];
      let v = 0;
      try { v = stateOf(el); } catch (e) { continue; }
      if ((v - v % 4) / 4 !== OVER) continue;
      let right = 0;
      try { right = apply(rectRight, apply(gbcr, el, []), []) + scrollX; } catch (e) {}
      let kind = "c";
      try { kind = overflowKind(el, cw, scrollX); } catch (e) { kind = "c"; }
      apply(wmSet, reflowEls, [el, '{"r":' + mRound(right) + ',"k":"' + kind + '"}']);
      found++;
    }
    return found;
  }

  // The elements the last capture wrote, in the order it wrote their
  // indices (capture's `extra.index`), so a record taken after it can name
  // them.
  let capturedEls = null, capturedSet = new WM();
  let reflowEls = new WM();

  // What the page hides at the narrow viewport, and how it reflows there
  // (fetch._record_narrow, L24): taken after the capture, with the viewport
  // narrowed, for the elements the capture wrote, each named by its index
  // in it. An element the page removed since is not rendered there
  // ("display", on the outermost one). The answer also names each element
  // the page changed since the capture (startWatch): the snapshot does not
  // show it as it is at this width. Nothing is written to the page and no
  // secret name is involved; the answer is plain values. Only the
  // harness's own call, which knows NARROW_TOKEN, takes it: a page that
  // finds this entry point cannot.
  function recordNarrow(token, closed) {
    if (typeof token !== "string" || token !== NARROW_TOKEN) return null;
    if (!capturedEls) return null;
    let watched = false;
    if (watcher) {
      try {
        noteChanges(apply(moTake, watcher, []));
        apply(moDisconnect, watcher, []);
        watched = true;
      } catch (e) { watched = false; }
    }
    watcher = null;
    registerClosed(closed);
    const L = listAll(), els = L.els;
    computeSlots(L.roots);
    const marks = new WM();
    let recorded = false, bodyHidden = false;
    if (checkVis) {
      const h = hidingOf(els);
      for (let i = 0; i < els.length; i++) {
        if (h.marks[i]) apply(wmSet, marks, [els[i], h.marks[i]]);
      }
      bodyHidden = h.bodyHidden;
      recorded = true;
    }
    reflowEls = new WM();
    let sw = -1, cw = -1, sx = 0, over = 0;
    try {
      const de = apply(docElGet, doc, []);
      sw = apply(scrollWidthGet, de, []); cw = apply(clientWidthGet, de, []);
      sx = apply(scrollLeftGet, de, []);
    } catch (e) { sw = -1; cw = -1; }
    const measured = typeof sw === "number" && typeof cw === "number" &&
                     sw >= 0 && cw > 0;
    const clipped = measured && viewportClips();
    if (measured && !clipped && sw > cw + 1) {
      over = findOverflow(els, cw, typeof sx === "number" ? sx : 0);
    }
    const outMarks = newList(), outReflow = newList(), outChanged = newList();
    for (let i = 0; i < capturedEls.length; i++) {
      const el = capturedEls[i];
      let mark = apply(wmHas, marks, [el]) ? apply(wmGet, marks, [el]) : "";
      if (!mark && recorded) {
        // Removed since the capture (a component a media query unmounts):
        // marked where the removed part starts, at an element left with no
        // parent, or whose parent is no element the capture wrote (a
        // shadow root, a fragment).
        try {
          if (!apply(isConnGet, el, [])) {
            const p = apply(parentGet, el, []);
            if (!p || !apply(wmHas, capturedSet, [p])) mark = "display";
          }
        } catch (e) {}
      }
      if (mark) {
        const pair = newList();
        apply(arrPush, pair, [i]); apply(arrPush, pair, [mark]);
        apply(arrPush, outMarks, [pair]);
      }
      if (apply(wmHas, reflowEls, [el])) {
        const pair = newList();
        apply(arrPush, pair, [i]); apply(arrPush, pair, [apply(wmGet, reflowEls, [el])]);
        apply(arrPush, outReflow, [pair]);
      }
      if (watched && apply(wmHas, changedEls, [el])) {
        const pair = newList();
        apply(arrPush, pair, [i]);
        apply(arrPush, pair, [apply(wmGet, changedEls, [el]) === OWN ? "self" : "children"]);
        apply(arrPush, outChanged, [pair]);
      }
    }
    return {recorded: recorded, watched: watched, changedAll: changeOver,
            bodyHidden: bodyHidden, measured: measured, clipped: clipped,
            scrollWidth: sw, clientWidth: cw, overflow: over, marks: outMarks,
            reflow: outReflow, changed: outChanged};
  }

  // One synchronous pass, so no page code runs between stamping and
  // serializing: stamp every element (document and every shadow root) with
  // its origin under a name the page has never seen, every <audio> and
  // <video> with its `muted` property under a second such name (frameworks
  // set muted as a property, which serialization drops), and each element
  // where the page as rendered stops or starts showing content again under
  // a third ("display", "visibility", "shown", "skips", "shown-skips" or
  // "visibility-skips";
  // stylesheets decide most
  // hiding, which serialization drops too); and, from `extra`, each element
  // axe-core reported with the number its results go under (the harness
  // writes the results in their place: fetch._AxeSession.place) and the
  // root element with a placeholder for the axe-core run's record (axe.py),
  // and each element with its index in the capture (for recordNarrow,
  // taken after), under names from the same secret. Serialize natively,
  // then remove the stamps. `extra` is the harness's own literal, every
  // object in it without a prototype, so reading it runs nothing the page
  // can define. `closed` holds the closed shadow roots the harness found,
  // the first `extra.axe.roots` of them those axe-core was given too.
  function capture(token, attr, mutedAttr, hiddenAttr, closed, extra) {
    if (typeof token !== "string" || token !== CAPTURE_TOKEN) return null;
    registerClosed(closed);
    // Every element is listed before the first stamp is written, so no page
    // code can run between stamping and serializing and read the names.
    const L = listAll(), els = L.els, roots = L.roots, media = L.media;
    // DOM mutation events (Chromium stopped firing them in version 127)
    // would run the page's listeners inside every stamp written below. The
    // probe is a detached element of the harness's own, so no listener of
    // the page's hears it.
    let mutationEvents = false;
    try {
      const probe = apply(createEl, doc, ["div"]);
      apply(addListener, probe, ["DOMSubtreeModified", () => { mutationEvents = true; }]);
      apply(setAttr, probe, ["data-bb-probe", "1"]);
    } catch (e) {}
    if (mutationEvents) {
      return {html: null, shadowRoots: 0, elements: els.length,
              note: "this browser fires DOM mutation events, which would run " +
                    "the page's code while the capture stamped it, so the " +
                    "capture was not used"};
    }
    // axe-core's results, placed before anything is stamped: each at the
    // element where the isolated world saw it, one per element.
    let axeAttr = "", axeRunAttr = "", axeRoots = 0;
    const axeEls = newList(), axeKs = newList();
    let ax = null;
    try { ax = extra ? extra.axe : null; } catch (e) { ax = null; }
    if (ax) {
      try {
        axeAttr = ax.attr; axeRunAttr = ax.runAttr; axeRoots = ax.roots;
        const marks = ax.marks;
        const m = marks.length;
        const taken = new WM();
        for (let i = 0; i < m && i < 1000000; i++) {
          const mk = marks[i];
          const el = resolvePath(mk.p), k = mk.k;
          if (el && typeof k === "number" && !apply(wmHas, taken, [el])) {
            apply(wmSet, taken, [el, true]);
            apply(arrPush, axeEls, [el]); apply(arrPush, axeKs, [k]);
          }
        }
      } catch (e) { axeAttr = ""; }
      if (typeof axeAttr !== "string" || typeof axeRunAttr !== "string" ||
          !axeAttr || !axeRunAttr || typeof axeRoots !== "number") axeAttr = "";
    }
    // How many elements of what is serialized axe-core did not check: those
    // inside a closed shadow root it was not given (attached after it ran,
    // or past what the harness looks for), and inside any root in one.
    let unchecked = 0;
    if (axeAttr) {
      const known = new WM();
      for (let i = 0; closed && i < axeRoots && i < 1000000; i++) {
        try { const r = closed[i]; if (r) apply(wmSet, known, [r, true]); } catch (e) {}
      }
      const blind = newList();
      apply(arrPush, blind, [false]);
      for (let s = 1; s < L.scopes.length; s++) {
        const root = L.scopes[s];
        let b = blind[L.parentOf[s]] === true;
        if (!b && !apply(wmHas, known, [root])) {
          let open = null;
          try { open = apply(shadowRootGet, apply(hostGet, root, []), []); } catch (e) { open = null; }
          b = open !== root;
        }
        apply(arrPush, blind, [b]);
        if (b) unchecked += L.sizes[s];
      }
    }
    // Each element's index in this capture, under its own secret name, so a
    // record taken after it (recordNarrow) can name the element.
    let indexAttr = "";
    try { indexAttr = extra ? extra.index : ""; } catch (e) { indexAttr = ""; }
    if (typeof indexAttr !== "string") indexAttr = "";
    // The names are secret, so no record under them can be the page's own,
    // unless it learned them from an earlier attempt: any it wrote goes.
    const names = newList();
    apply(arrPush, names, [attr]);
    if (mutedAttr) apply(arrPush, names, [mutedAttr]);
    if (hiddenAttr) apply(arrPush, names, [hiddenAttr]);
    if (axeAttr) { apply(arrPush, names, [axeAttr]); apply(arrPush, names, [axeRunAttr]); }
    if (indexAttr) apply(arrPush, names, [indexAttr]);
    for (let i = 0; i < els.length; i++) {
      for (let j = 0; j < names.length; j++) {
        try {
          if (apply(hasAttr, els[i], [names[j]])) apply(removeAttr, els[i], [names[j]]);
        } catch (e) {}
      }
    }
    // What the page, as rendered, hides, read before the first stamp so no
    // stamp can change it (hidingOf).
    let hidden = newList();
    let hideNote = "";
    const recorded = !!(hiddenAttr && checkVis);
    if (hiddenAttr && !checkVis) {
      hideNote = "this browser cannot report what the page hides; content " +
                 "hidden by stylesheets was not marked";
    }
    if (recorded) {
      computeSlots(roots);
      const h = hidingOf(els);
      hidden = h.marks;
      if (h.bodyHidden) {
        hideNote = "the page's <body> was hidden when it was captured; " +
                   "content inside it was read as shown";
      }
    }
    let html = null, note = "";
    for (let i = 0; i < els.length; i++) {
      try { apply(setAttr, els[i], [attr, originFor(els[i])]); } catch (e) {}
    }
    const rootEl = apply(docElGet, doc, []);
    if (recorded) {
      try { apply(setAttr, rootEl, [hiddenAttr, "recorded"]); } catch (e) {}
      for (let i = 0; i < els.length; i++) {
        if (!hidden[i]) continue;
        try { apply(setAttr, els[i], [hiddenAttr, hidden[i]]); } catch (e) {}
      }
    }
    if (mutedAttr && mutedGet) {
      for (let i = 0; i < media.length; i++) {
        try {   // the getter throws on anything but a real media element
          const m = apply(mutedGet, media[i], []);
          apply(setAttr, media[i], [mutedAttr, m === true ? "true" : "false"]);
        } catch (e) {}
      }
    }
    // The run's record and each element's results go in after this pass,
    // where these stand (fetch._AxeSession.place), once the harness knows
    // which marks the page did not move first.
    const axePlaced = newList();
    if (axeAttr) {
      try { apply(setAttr, rootEl, [axeRunAttr, "pending"]); } catch (e) {}
      for (let i = 0; i < axeEls.length; i++) {
        try {
          apply(setAttr, axeEls[i], [axeAttr, "" + axeKs[i]]);
          apply(arrPush, axePlaced, [axeKs[i]]);
        } catch (e) {}
      }
    }
    let rootIndex = -1;
    if (indexAttr) {
      for (let i = 0; i < els.length; i++) {
        try { apply(setAttr, els[i], [indexAttr, "" + i]); } catch (e) {}
        if (els[i] === rootEl) rootIndex = i;
      }
    }
    try {
      const root = apply(docElGet, doc, []);
      const dt = apply(doctypeGet, doc, []);
      const dts = dt ? apply(xsSerialize, new XS(), [dt]) : "";
      if (typeof getHTML === "function") {
        // The root's start tag, cut from its own serialization: outerHTML
        // is start tag + innerHTML + end tag. Never a clone: cloning a
        // customized built-in (<html is=...>) runs page code, after stamping.
        // In an XML document (XHTML served as XML, SVG) innerHTML adds
        // namespace declarations outerHTML does not, so the cut is checked;
        // there the start tag ends at the first ">", which XML
        // serialization escapes inside attribute values.
        const outer = apply(outerGet, root, []);
        const plain = apply(innerGet, root, []);
        const close = "</" + (apply(localNameGet, root, []) || "html") + ">";
        let startLen = outer.length - plain.length - close.length;
        if (!(startLen > 0
              && apply(strSlice, outer, [startLen]) === plain + close)) {
          startLen = apply(strIndexOf, outer, [">"]) + 1;
        }
        if (startLen > 1) {
          const open = apply(strSlice, outer, [0, startLen]);
          const opts = {__proto__: null};
          opts.serializableShadowRoots = false;
          opts.shadowRoots = safeSeq(roots);
          const inner = apply(getHTML, root, [opts]);
          html = dts + open + inner + close;
        }   // else html stays null: the run falls back, with its note
      } else {
        html = dts + apply(outerGet, root, []);
        if (roots.length) note = "this browser cannot serialize shadow roots; " +
                                 roots.length + " shadow root(s) were not captured";
      }
    } finally {
      for (let i = 0; i < els.length; i++) {
        try { apply(removeAttr, els[i], [attr]); } catch (e) {}
      }
      for (let i = 0; mutedAttr && i < media.length; i++) {
        try { apply(removeAttr, media[i], [mutedAttr]); } catch (e) {}
      }
      if (recorded) {
        try { apply(removeAttr, rootEl, [hiddenAttr]); } catch (e) {}
        for (let i = 0; i < els.length; i++) {
          if (!hidden[i]) continue;
          try { apply(removeAttr, els[i], [hiddenAttr]); } catch (e) {}
        }
      }
      if (axeAttr) {
        try { apply(removeAttr, rootEl, [axeRunAttr]); } catch (e) {}
        for (let i = 0; i < axeEls.length; i++) {
          try { apply(removeAttr, axeEls[i], [axeAttr]); } catch (e) {}
        }
      }
      if (indexAttr) {
        for (let i = 0; i < els.length; i++) {
          try { apply(removeAttr, els[i], [indexAttr]); } catch (e) {}
        }
      }
    }
    if (indexAttr && html !== null) {
      capturedEls = els;
      capturedSet = new WM();
      for (let i = 0; i < els.length; i++) apply(wmSet, capturedSet, [els[i], true]);
      // From here on, what the page changes is watched (recordNarrow): in
      // the same pass as the stamps' removal, so the watch sees none of them.
      startWatch(L.scopes);
    }
    if (hideNote) note = note ? note + "; " + hideNote : hideNote;
    return {html: html, shadowRoots: roots.length, elements: els.length, note: note,
            axe: axeAttr ? {placed: axePlaced, unchecked: unchecked} : null,
            index: indexAttr ? {root: rootIndex} : null};
  }

  try { defProp(window, PROP, {value: capture, writable: false,
                               configurable: false, enumerable: false}); } catch (e) {}
  try { defProp(window, PROP + "_narrow", {value: recordNarrow, writable: false,
                                           configurable: false, enumerable: false}); } catch (e) {}
})();
//# sourceURL=bellbriar-instrumentation.js
"""


def instrumentation_script(capture_prop: str,
                           vendor_domains=KNOWN_VENDOR_DOMAINS,
                           vendor_origins=(),
                           narrow_token: str | None = None,
                           capture_token: str | None = None) -> str:
    """The init script for one capture. `capture_prop` is the per-run
    property name of the capture entry point, which takes `capture_token`
    (_call_capture); the narrow-viewport record's entry point is
    `capture_prop + "_narrow"`, and takes `narrow_token` (_record_narrow).
    Each is a fresh random one when not given."""
    token = narrow_token or secrets.token_hex(16)
    ctoken = capture_token or secrets.token_hex(16)
    for t in (token, ctoken):
        if not re.fullmatch(r"[0-9a-f]{16,64}", t):
            raise ValueError("the tokens must be lowercase hex")
    return (_INSTRUMENT_TEMPLATE
            .replace("%NARROW_TOKEN%", token)
            .replace("%CAPTURE_TOKEN%", ctoken)
            .replace("%PROP%", capture_prop)
            .replace("%VENDOR_DOMAINS%", json.dumps(list(vendor_domains)))
            .replace("%VENDOR_ORIGINS%", json.dumps(list(vendor_origins))))


#: Scroll through the page in viewport steps so content that builds itself
#: on scroll (IntersectionObserver sections, lazy lists) exists before the
#: capture. Capped, then back to the top.
_SCROLL_JS = r"""
async ([pause, maxSteps]) => {
  const height = () => Math.max(
    document.documentElement ? document.documentElement.scrollHeight : 0,
    document.body ? document.body.scrollHeight : 0);
  let steps = 0, y = 0;
  while (steps < maxSteps) {
    y += window.innerHeight || 800;
    window.scrollTo(0, y);
    await new Promise((r) => setTimeout(r, pause));
    steps++;
    if (y + (window.innerHeight || 800) >= height()) break;
  }
  window.scrollTo(0, 0);
  await new Promise((r) => setTimeout(r, pause));
  return {steps: steps, height: height()};
}
"""

#: Waits for DOM mutations to stop for `quiet` ms, capped. `networkidle` is
#: not usable: a 300 ms analytics poll — entirely ordinary — never goes idle,
#: and the wait times out on a page that is perfectly settled.
#:
#: It watches the document itself, not its root element, so a page that
#: replaces its root or rewrites itself (document.open) is still watched,
#: and every open shadow root, looked for again every 250 ms, since a
#: document's observer does not see into them (R4B-7). Only changes to
#: nodes in the document count: a shadow root whose host was removed can
#: go on changing without keeping the page from settling (R4C-2). A closed
#: shadow root no script can reach, and frames are documents of their own:
#: a page that changes only inside one can look settled sooner
#: (docs/MEASUREMENT-AND-EVIDENCE-GUIDE.md).
_SETTLE_JS = r"""
([quiet, cap]) => new Promise((resolve) => {
  let last = Date.now();
  const started = Date.now();
  const opts = {childList: true, subtree: true, attributes: true,
                characterData: true};
  const obs = new MutationObserver((records) => {
    for (const r of records) {
      if (r.target.isConnected) { last = Date.now(); return; }
    }
  });
  obs.observe(document, opts);
  const seen = new WeakSet();
  const roots = (top) => {
    const stack = [top];
    let n = 0;
    while (stack.length && n < 1000000) {
      const it = document.createTreeWalker(stack.pop(), NodeFilter.SHOW_ELEMENT);
      for (let el = it.nextNode(); el && n < 1000000; el = it.nextNode()) {
        n++;
        const sr = el.shadowRoot;
        if (!sr) continue;
        if (!seen.has(sr)) {
          seen.add(sr); obs.observe(sr, opts); last = Date.now();
        }
        stack.push(sr);
      }
    }
  };
  roots(document);
  let looked = Date.now();
  const timer = setInterval(() => {
    let now = Date.now();
    if (now - looked >= 250) { roots(document); looked = now = Date.now(); }
    if (now - last >= quiet || now - started >= cap) {
      clearInterval(timer); obs.disconnect();
      resolve({settled: now - last >= quiet, waited: now - started});
    }
  }, 50);
})
"""


class _DataRequests:
    """The page's data requests in flight (S5-3): its fetch and XHR
    requests, from any frame, but not those to a vendor the run lists
    (KNOWN_VENDOR_DOMAINS, --third-party-origin: analytics, chat and
    consent widgets poll on their own). A client-rendered page often
    builds its content when one of these answers, which can take longer
    than the DOM stays still before it: the settle step waits for them
    too (_settle). Event handlers, so the page's scripts cannot see or
    stop them."""

    TYPES = ("fetch", "xhr")

    def __init__(self, page, vendor_domains=(), vendor_origins=()):
        import time
        self._clock = time.monotonic
        self.domains = tuple(d.lower() for d in vendor_domains)
        self.origins = frozenset(o.lower() for o in vendor_origins)
        self.pending: dict = {}
        self.last = self._clock()
        self.seen = 0
        page.on("request", self._start)
        page.on("requestfinished", self._end)
        page.on("requestfailed", self._end)

    def _vendor(self, url: str) -> bool:
        try:
            parts = urllib.parse.urlsplit(url)
            host = (parts.hostname or "").lower()
            origin = f"{parts.scheme.lower()}://{parts.netloc.lower()}"
        except ValueError:
            return False
        return origin in self.origins or any(
            host == d or host.endswith("." + d) for d in self.domains)

    def _start(self, req) -> None:
        try:
            if req.resource_type in self.TYPES and not self._vendor(req.url):
                self.pending[req] = True
                self.seen += 1
                self.last = self._clock()
        except Exception:                               # noqa: BLE001
            pass

    def _end(self, req) -> None:
        if self.pending.pop(req, None) is not None:
            self.last = self._clock()

    def in_flight(self) -> int:
        return len(self.pending)

    def quiet_for_ms(self) -> int:
        return int((self._clock() - self.last) * 1000)


def _settle(ctx, page, quiet_ms: int, cap_ms: int, data) -> dict:
    """Wait until the DOM has not changed for `quiet_ms` (_SETTLE_JS) and
    no data request (_DataRequests) has been in flight for as long, or
    `cap_ms` has passed in all (S5-3). A response usually changes the DOM,
    so each wait for the requests is followed by another for the DOM.
    {"settled", "waited", "in_flight", "data_requests"}: `settled` is the
    DOM's, `in_flight` how many data requests were still open at the end."""
    import time
    started = time.monotonic()
    deadline = started + cap_ms / 1000
    dom: dict = {}
    while True:
        left = max(1, int((deadline - time.monotonic()) * 1000))
        got = _in_own_world(ctx, page, _SETTLE_JS, [quiet_ms, left])
        dom = got if isinstance(got, dict) else {}
        if data is None:
            break
        while data.in_flight() and time.monotonic() < deadline:
            page.wait_for_timeout(50)
        if data.in_flight() or time.monotonic() >= deadline:
            break
        rest = quiet_ms - data.quiet_for_ms()
        if rest <= 0 and dom.get("settled"):
            break
        if rest > 0:
            page.wait_for_timeout(min(rest, max(1, int(
                (deadline - time.monotonic()) * 1000))))
    open_now = 0
    if data is not None and data.in_flight():
        # The requests open at the cap get SETTLE_GRACE_MS more to answer,
        # and so do any they lead to (one fetch chained to the next): the
        # wait ends when none has been open for `quiet_ms`, as the settle
        # step's does, which a page that polls now and then gives it. One
        # held open (a long poll), or one chained on still, is open at the
        # end, and counted.
        until = time.monotonic() + SETTLE_GRACE_MS / 1000
        while time.monotonic() < until and (
                data.in_flight() or data.quiet_for_ms() < quiet_ms):
            page.wait_for_timeout(50)
        open_now = len(data.pending)
        if not open_now:
            # What the answers bring is built after them: the DOM is
            # waited on again, as after any wait for the requests.
            got = _in_own_world(ctx, page, _SETTLE_JS,
                                [quiet_ms, SETTLE_GRACE_MS])
            dom = got if isinstance(got, dict) else {}
    return {"settled": bool(dom.get("settled")),
            "waited": int((time.monotonic() - started) * 1000),
            "in_flight": open_now,
            "data_requests": data.seen if data is not None else 0}


#: How long the requests open at the settle cap, and those they lead to,
#: get to answer (_settle); the DOM then gets as long again to settle.
SETTLE_GRACE_MS = 2000


#: Why a page is refused when --wait-for's element never appears.
WAIT_FOR_MISSING = ("no element matched the --wait-for selector within "
                    "{seconds:g} s, so the page never showed what the run "
                    "was told to wait for")


#: Why a page is refused when the browser cannot read --wait-for's
#: selector (one the selector library takes and Chromium does not).
WAIT_FOR_UNREADABLE = ("the browser could not read the --wait-for selector "
                       "as CSS, so the run could not wait for it")


def _wait_for(page, selector: str, timeout_ms: int) -> None:
    """Wait for an element `selector` (CSS) matches, in the page or an open
    shadow root, or raise FetchError: WAIT_FOR_MISSING when none appeared in
    time, WAIT_FOR_UNREADABLE when the browser refused the selector."""
    from playwright.sync_api import TimeoutError as PlaywrightTimeout
    try:
        page.wait_for_selector(f"css={selector}", state="attached",
                               timeout=timeout_ms)
    except PlaywrightTimeout:
        raise FetchError(WAIT_FOR_MISSING.format(
            seconds=timeout_ms / 1000)) from None
    except Exception as exc:                            # noqa: BLE001
        if _CLOSED.match(str(exc).split(":", 1)[-1].strip()):
            raise
        raise FetchError(WAIT_FOR_UNREADABLE) from None


#: Why a capture whose data requests never finished is not evaluated.
STILL_LOADING = ("still loading when captured: {n} of the page's data "
                 "requests (fetch or XHR) had not answered by the end of the "
                 "capture's wait (the {cap} ms settle cap, and {grace} ms "
                 "more for the requests open then and those they led to), so "
                 "the content they bring may be missing. This is not a pass: "
                 "give --wait-for an element the page shows once it has "
                 "loaded")


class FetchError(RuntimeError):
    pass


class BrowserUnavailable(FetchError):
    """A run that needs a browser (--render: browser_required) found none,
    or none that starts: every other page would fail the same way."""


#: The isolated world the scroll and settle steps run in (L21): it shares
#: the page's DOM but none of its JavaScript, so the page cannot replace
#: the timers, clocks or observers the steps use to decide that it
#: settled, nor make them fail.
STEPS_WORLD = "bellbriar-steps"


class StepFailed(Exception):
    """The scroll or settle step could not finish. Its text is the
    harness's own, never the page's (render_failure): "page" when the page
    crashed, closed or went to another document while it ran, "script"
    when the step's script raised in the page's document (R4B-8)."""


class _Documents:
    """The documents the tab's main frame commits, in order, and what the
    server sent for each, from Chromium's own events (R4G-1, R4G-3):
    Page.frameNavigated fires when a document commits — not for a
    navigation that commits none (a download, a 204), nor for the history
    API — and Network.responseReceived carries each navigation's response
    (its status and Content-Type) under the same loader id. Watched from
    before the page is requested, so the first document is the one it was
    sent to. Raises StepFailed when the browser cannot be watched."""

    def __init__(self, ctx, page):
        #: The loader id of each document the main frame committed.
        self.committed: list = []
        #: {loader id: (HTTP status, [Content-Type header lines])}.
        self.responses: dict = {}
        #: {loader id: the URL the document committed at}.
        self.urls: dict = {}
        #: The loader ids whose document a service worker answered, not a
        #: server: none while the worker is bypassed, as it is (R5E-5).
        self.worker: set = set()
        #: {loader id: [(URL, the address its server answered from)]} for
        #: each redirect on a document's way and its own response, in
        #: order, as Chromium connected (remoteIPAddress); and {loader id:
        #: (URL, address)} for its own response alone. A name resolved
        #: again later can resolve elsewhere (DNS rebinding: S5 re-review).
        self.peers: dict = {}
        self.own_peer: dict = {}
        #: Whether the main frame stopped loading since it last started
        #: (Page.frameStoppedLoading): until it has, nothing in it is
        #: read while the page is still loading (_loaded_anyway).
        self.stopped = False
        #: How many times a document replaced the one shown without a
        #: commit: a javascript: URL makes one so, clearing the page's
        #: contexts and making a new one with no Page.frameNavigated
        #: (R5C-2). No server sent such a document.
        self.replaced = 0
        #: Whether the document shown now is one of those: cleared when a
        #: document commits after it (a javascript: page, then a server's
        #: 200 page, is that page: R5E-12).
        self.script_made = False
        #: (when it started, by time.monotonic(); its URL; its loader id)
        #: for the main frame's navigation to another document while it
        #: has neither committed nor ended, from
        #: Page.frameStartedNavigating; None when there is none. Chromium
        #: holds every DevTools call made to the page while one is pending
        #: until it ends, so a call made then waits with it (R5E-6,
        #: _watch_pending). It ends with a commit, with the frame's loading
        #: stopping, or, while the document before it still loads, with a
        #: 204 or 205 for it or its own request failing, as one does that
        #: becomes a download (R5H-2). Another download, such as a link the
        #: page clicks while it waits, ends nothing (R5J-2).
        self.pending: tuple | None = None
        self._cleared = False
        try:
            self._cdp = ctx.new_cdp_session(page)
            self._main = self._cdp.send("Page.getFrameTree")[
                "frameTree"]["frame"]["id"]
            self._cdp.on("Page.frameStartedNavigating", self._starting)
            self._cdp.on("Network.loadingFailed", self._failed)
            self._cdp.on("Page.frameNavigated", self._navigated)
            self._cdp.on("Network.responseReceived", self._response)
            self._cdp.on("Network.requestWillBeSent", self._request)
            self._cdp.on("Page.frameStartedLoading",
                         lambda event: self._loading(event, False))
            self._cdp.on("Page.frameStoppedLoading",
                         lambda event: self._loading(event, True))
            self._cdp.on("Runtime.executionContextsCleared", self._clear)
            self._cdp.on("Runtime.executionContextCreated", self._context)
            self._cdp.send("Page.enable")
            self._cdp.send("Network.enable")
            # No service worker answers any request of the page's: what a
            # server sends is what is read (R5C-3). Playwright's own block
            # only hides navigator.serviceWorker.register, which a page can
            # still reach (R5E-5); this is DevTools' "Bypass for network".
            self._cdp.send("Network.setBypassServiceWorker",
                           {"bypass": True})
            self._cdp.send("Runtime.enable")
        except Exception:                               # noqa: BLE001
            raise StepFailed("page") from None

    def _clear(self, _event) -> None:
        self._cleared = True

    def _context(self, event) -> None:
        try:
            aux = (event.get("context") or {}).get("auxData") or {}
            if aux.get("isDefault") and aux.get("frameId") == self._main:
                if self._cleared:
                    # Cleared, and no document committed before this one.
                    self.replaced += 1
                    self.script_made = True
                self._cleared = False
        except Exception:                               # noqa: BLE001
            pass

    def _loading(self, event, stopped: bool) -> None:
        try:
            if event.get("frameId") == self._main:
                self.stopped = stopped
                if stopped:
                    # A navigation that ends with no document (a download,
                    # a 204, one stopped) stops the frame's loading.
                    self.pending = None
        except Exception:                               # noqa: BLE001
            pass

    def _starting(self, event) -> None:
        try:
            if event.get("frameId") == self._main and event.get(
                    "navigationType") not in ("sameDocument",
                                              "historySameDocument"):
                import time
                # From the first of navigations that follow each other
                # with none committing: the browser has waited since then.
                since = self.pending[0] if self.pending else time.monotonic()
                self.pending = (since, str(event.get("url") or ""),
                                event.get("loaderId"))
        except Exception:                               # noqa: BLE001
            pass

    def _ended(self, loader) -> None:
        """The pending navigation, if it is `loader`'s, ended with no
        document."""
        pending = self.pending
        if pending is not None and loader and pending[2] == loader:
            self.pending = None

    def _failed(self, event) -> None:
        try:
            # A navigation's request id is its loader id.
            self._ended(event.get("requestId"))
        except Exception:                               # noqa: BLE001
            pass

    def _navigated(self, event) -> None:
        try:
            frame = event.get("frame") or {}
            if not frame.get("parentId") and frame.get("loaderId"):
                self.committed.append(frame["loaderId"])
                self.urls[frame["loaderId"]] = str(frame.get("url") or "")
                self._cleared = False
                self.script_made = False
                self.pending = None
        except Exception:                               # noqa: BLE001
            pass

    def _peer(self, loader, response) -> tuple | None:
        url, ip = response.get("url"), response.get("remoteIPAddress")
        if not (isinstance(url, str) and isinstance(ip, str) and ip):
            return None
        pairs = self.peers.setdefault(loader, [])
        if len(pairs) < 100:
            pairs.append((url, ip))
        return url, ip

    def _request(self, event) -> None:
        try:
            redirect = event.get("redirectResponse")
            if event.get("type") == "Document" and event.get("loaderId") \
                    and isinstance(redirect, dict):
                self._peer(event["loaderId"], redirect)
        except Exception:                               # noqa: BLE001
            pass

    def _response(self, event) -> None:
        try:
            if event.get("type") != "Document" or not event.get("loaderId"):
                return
            response = event.get("response") or {}
            own = self._peer(event["loaderId"], response)
            if own is not None:
                self.own_peer[event["loaderId"]] = own
            headers = response.get("headers") or {}
            # Chromium joins the lines of a header sent twice with "\n".
            lines = [line for name, value in headers.items()
                     if str(name).lower() == "content-type"
                     for line in str(value).split("\n")]
            status = response.get("status")
            if status in (204, 205):
                # No document comes of it (R5H-2).
                self._ended(event["loaderId"])
            if response.get("fromServiceWorker"):
                # A worker's answer, not a server's (R5C-3).
                status = None
                self.worker.add(event["loaderId"])
            self.responses[event["loaderId"]] = (
                int(status) if isinstance(status, (int, float))
                and not isinstance(status, bool) else None, lines)
        except Exception:                               # noqa: BLE001
            pass

    def changes(self) -> int:
        """How many documents the tab has shown: those committed, and those
        that replaced one without a commit."""
        return len(self.committed) + self.replaced

    def moved(self) -> bool:
        """Does the tab show a document other than the first it loaded (a
        script or a refresh sent it on)?"""
        return len(self.committed) > 1 and \
            self.committed[-1] != self.committed[0]

    def shown_url(self) -> str:
        """The URL of the document the tab shows ("" before any)."""
        return self.urls.get(self.committed[-1], "") if self.committed \
            else ""

    def first(self) -> tuple:
        """(HTTP status or None, [Content-Type lines]) of the first
        document the tab committed: the one it was sent to."""
        if not self.committed:
            return None, []
        return self.responses.get(self.committed[0], (None, []))

    def shown(self) -> tuple:
        """(HTTP status or None, media type or "") the server sent for the
        document the tab shows; (None, "") for one that came with no
        response (about:blank)."""
        if not self.committed:
            return None, ""
        status, lines = self.responses.get(self.committed[-1], (None, []))
        try:
            mime = parse_content_type(lines)[0] if lines else ""
        except Exception:                               # noqa: BLE001
            mime = ""
        return status, mime


def _await_document(ctx, page, docs, before: int, timeout_ms: int) -> bool:
    """Wait, quietly and at most `timeout_ms`, for the document the tab
    showed after its first `before` (docs.changes) to load (_wait_loaded),
    so what it is can be read (check_shown): two seconds for one to come,
    or longer while a navigation to one is pending (docs.pending: one that
    never commits is the watch's, _watch_pending). Whether it loaded."""
    import time
    deadline = time.monotonic() + timeout_ms / 1000
    try:
        waited = 0
        while docs.changes() <= before and time.monotonic() < deadline and (
                waited < 20 or docs.pending is not None):
            page.wait_for_timeout(100)
            waited += 1
        left_ms = int((deadline - time.monotonic()) * 1000)
        return left_ms > 0 and _wait_loaded(ctx, page, docs, left_ms)
    except Exception:                                   # noqa: BLE001
        return False


def _loaded_anyway(ctx, page, docs) -> bool:
    """Is the document the tab shows loaded, its load event seen or not:
    its frame stopped loading, and its readyState "complete", read in the
    harness's own world? A head script that sends the tab to a download or
    a 204 leaves a page so with no load event seen: no document replaces
    it (R5A-8)."""
    # Read only once the frame stopped loading: a page whose script never
    # yields would hold the reading until the run's deadline, where its
    # load wait times out as it always did.
    if not docs.committed or not docs.stopped:
        return False
    try:
        state = _in_own_world(ctx, page, "() => document.readyState", [])
    except StepFailed:
        return False
    return state == "complete"


#: How long a page must stay loaded, its load event unseen, before the
#: wait for that event ends (_goto). A page's load event follows its
#: readyState "complete" at once, its handlers run; this is far longer.
LOADED_UNSEEN_S = 1.0


def _wait_loaded(ctx, page, docs, timeout_ms: int) -> bool:
    """Wait, at most `timeout_ms`, for the load event of the document the
    tab shows, or until it has been loaded for LOADED_UNSEEN_S with that
    event unseen (_loaded_anyway): a head script that sends the tab to a
    download or a 204 made a capture wait out the whole timeout (R5A-8,
    L88). True when it loaded, False at the timeout."""
    import time
    from playwright.sync_api import TimeoutError as PlaywrightTimeout
    deadline = time.monotonic() + timeout_ms / 1000
    loaded_since = None
    while True:
        left_ms = int((deadline - time.monotonic()) * 1000)
        if left_ms <= 0:
            return False
        try:
            page.wait_for_load_state("load", timeout=min(500, left_ms))
            return True
        except PlaywrightTimeout:
            pass
        if _loaded_anyway(ctx, page, docs):
            now = time.monotonic()
            if loaded_since is None:
                loaded_since = now
            elif now - loaded_since >= LOADED_UNSEEN_S:
                return True
        else:
            loaded_since = None


def _goto(ctx, page, docs, url: str, timeout_ms: int, keep=()):
    """page.goto(url), then the wait for the page to load (_wait_loaded),
    together within `timeout_ms`; the response, as page.goto returns it.
    Raises what page.goto raises, a timeout as page.goto words one
    (render_failure reads it); FetchError when the page went on before it
    loaded and never settled (`keep`: the --record-query names, for the
    URL it went to)."""
    import time
    from playwright.sync_api import TimeoutError as PlaywrightTimeout
    deadline = time.monotonic() + timeout_ms / 1000
    resp = page.goto(url, wait_until="commit", timeout=timeout_ms)
    left_ms = int((deadline - time.monotonic()) * 1000)
    if left_ms <= 0 or not _wait_loaded(ctx, page, docs, left_ms):
        if docs.changes() > MAX_READS:
            # Not slow: it kept going to other documents before it loaded
            # (a page that reloads itself from its head, R5C-8).
            raise FetchError(f"{WENT_ELSEWHERE}{KEPT_GOING}")
        if docs.changes() > 1:
            # It went on, before it loaded, to a document that never
            # finished loading: refused in words of its own, and never
            # read as the page it left (R5E-4).
            raise FetchError(f"{WENT_ELSEWHERE}{NOT_LOADED}"
                             + _at(docs.shown_url(), keep))
        pending = docs.pending
        if pending is not None and docs.committed:
            # The same, for a document that never came (R5E-6).
            raise FetchError(f"{WENT_ELSEWHERE}{NOT_ARRIVED}"
                             + _at(pending[1], keep))
        raise PlaywrightTimeout(f"Page.goto: Timeout {timeout_ms}ms "
                                "exceeded.")
    return resp


#: How long before the render deadline the capture gives up on a
#: navigation still pending (_watch_pending): time to answer before the
#: supervisor stops it, from a clock that started a moment later.
PENDING_MARGIN_S = 3.0


def _watch_pending(docs, done, timeout_s: float, deadline_at, keep,
                   on_stuck) -> None:
    """Until `done` is set, watch for a navigation of the main frame that
    started after a document committed and is still pending (docs.pending)
    `timeout_s` (the load timeout) after it started, or PENDING_MARGIN_S
    before `deadline_at` (time.monotonic()): then call `on_stuck` with the
    FetchError that says so, once. Chromium holds every DevTools call made
    to the page while a navigation is pending, so the capture itself waits
    with it, and a supervisor that stopped it at its deadline blamed a
    script (R5E-6). Runs in a thread of its own and makes no call to the
    browser: `on_stuck` must end the capture (_render_child does)."""
    import time
    while not done.wait(0.1):
        pending = docs.pending
        if pending is None or not docs.committed:
            continue
        now = time.monotonic()
        if now - pending[0] < timeout_s and (
                deadline_at is None or now < deadline_at - PENDING_MARGIN_S):
            continue
        on_stuck(FetchError(f"{WENT_ELSEWHERE}{NOT_ARRIVED}"
                            + _at(pending[1], keep)))
        return


def _in_own_world(ctx, page, function: str, args: list):
    """Call `function` (a function's source) with `args` in an isolated
    world of the harness's own (STEPS_WORLD), awaiting what it returns.
    Raises StepFailed, never the page's error text."""
    try:
        cdp = ctx.new_cdp_session(page)
    except Exception:                                   # noqa: BLE001
        raise StepFailed("page") from None
    try:
        frame = cdp.send("Page.getFrameTree")["frameTree"]["frame"]["id"]
        world = cdp.send("Page.createIsolatedWorld", {
            "frameId": frame, "worldName": STEPS_WORLD,
            "grantUniveralAccess": False})["executionContextId"]
        res = cdp.send("Runtime.evaluate", {
            "expression": f"({function})({json.dumps(args)})",
            "contextId": world, "awaitPromise": True,
            "returnByValue": True})
    except Exception:                                   # noqa: BLE001
        res = None
    finally:
        try:
            cdp.detach()
        except Exception:                               # noqa: BLE001
            pass
    if not isinstance(res, dict):
        raise StepFailed("page")
    if res.get("exceptionDetails"):
        raise StepFailed("script")
    return (res.get("result") or {}).get("value")


@dataclass
class FetchResult:
    """One capture of one page, with everything needed to say what it was."""
    url: str
    final_url: str
    mode: str                       # "rendered" | "server"
    html: str
    status: int | None = None
    redirects: list = field(default_factory=list)
    fetched_at: str = ""
    browser: dict | None = None     # {"name": "chromium", "version": "…"}
    viewport: dict | None = None
    wait: dict | None = None        # {"strategy", "quiet_ms", "waited_ms", "settled"}
    fallback_reason: str | None = None
    instrumented: bool = False
    #: The attribute this capture wrote provenance into — a random name
    #: chosen for this capture — or None when no harness-written attribution
    #: exists (server HTML, failed instrumentation). The rules honor
    #: attribution only under this name.
    provenance_attr: str | None = None
    #: How first/third-party was decided (policy, vendor list version, any
    #: --third-party-origin additions); None for server HTML.
    attribution: dict | None = None
    #: Shadow roots serialized into the snapshot as <bb-shadow-root>.
    shadow_roots: int = 0
    #: The axe-core run behind the capture's rendered rules (axe.py,
    #: _AxeSession.place): engine, version, sha256, whether its results
    #: were recorded (and why not), the rules it ran (and any it ran out of
    #: time for), how many elements carry its results, how many results no
    #: element carries, how many elements of the snapshot it did not check
    #: (in closed shadow roots it was not given) and how many the page
    #: added after it started; None when no browser captured the page.
    axe: dict | None = None
    #: The capture's second viewport (_narrow_outcome, L24): its size,
    #: whether the snapshot records what the page hides there, how many
    #: elements the page changed after the capture, and its reflow
    #: measurement; None when no narrow record was taken.
    narrow: dict | None = None
    #: How the rules read the snapshot (checks_static.READERS): "dom" for a
    #: rendered capture, the browser's serialization of the live DOM;
    #: "html" for server HTML; "xml" for a page served with an XML type
    #: (application/xhtml+xml). A re-run passes it as --read-as.
    reader: str = "html"
    address_class: str = "public"   # loopback | private | public
    #: What decided address_class (address_record, L20): "address" or
    #: "name".
    address_basis: str = "name"
    notes: list = field(default_factory=list)
    #: Query, fragment and path parameters whose values the operator chose
    #: to record (--record-query). Every other value is recorded as
    #: REDACTED.
    record_query: tuple = ()
    #: What the recorded URLs leave out (redact.py): "userinfo", "path",
    #: "query", "fragment" — and "http-credentials" when credentials were
    #: offered.
    redacted: list = field(default_factory=list)
    #: Literal secrets seen in the URLs, for scrubbing free text. Never
    #: recorded.
    _scrub: tuple = field(default=(), init=False, repr=False, compare=False)
    #: (URL, address) for the document a rendered capture read and each
    #: redirect on its way there, as the browser connected to them, where
    #: it connected to the host itself rather than to a proxy: what
    #: _refuse_private_page judges, rather than a name resolved again
    #: (DNS rebinding: S5 re-review). Never recorded.
    document_peers: list = field(default_factory=list, repr=False,
                                 compare=False)
    #: The first line of a failed rendered fetch's own error text, cleaned:
    #: printed to the console, never recorded (fetch.render_failure).
    fallback_detail: str | None = field(default=None, repr=False,
                                        compare=False)
    #: A rendered page sent the tab on to another document (a script or a
    #: refresh): what was captured is the document it went to, at
    #: final_url. The history API (pushState) does not count, nor does a
    #: navigation that commits no document (a download, a 204; R4G-3).
    navigated: bool = field(default=False, compare=False)

    def __post_init__(self):
        # A verifier reads the fetched host from final_url (bundle.url_host),
        # so final_url carries its host in the one spelling evidence uses,
        # as a browser writes it, whichever fetcher produced it.
        self.final_url = canonical_url(self.final_url)
        # Then nothing secret is kept. Every URL this result holds loses its
        # userinfo and its parameter values (redact.py) before anything can
        # record or print it. The host is untouched, so `host` — the value a
        # signature binds — reads the same before and after.
        keep = tuple(sorted(names(self.record_query)))
        self.record_query = keep
        removed = set(self.redacted or ())
        scrub: set = set()

        def clean(url):
            safe, what = redact_url(url, keep)
            removed.update(what)
            scrub.update(secret_values(url, keep))
            return safe

        self.url = clean(self.url)
        self.final_url = clean(self.final_url)
        self.redirects = [clean(r) for r in (self.redirects or [])]
        self._scrub = tuple(sorted(scrub))
        self.redacted = sorted(removed)
        self.notes = [self._clean_text(n) for n in (self.notes or [])]
        self.fallback_reason = self._clean_text(self.fallback_reason)

    def _clean_text(self, text):
        """Free text as it may be recorded: URLs redacted, known secrets
        replaced. Error messages quote URLs, often with the token in them."""
        return redact_text(text, self._scrub, self.record_query)

    @property
    def snapshot_bytes(self) -> bytes:
        """The snapshot as saved: UTF-8 with a byte-order mark. The page's
        own encoding was decoded at capture; the mark makes a re-run read the
        snapshot as UTF-8 whatever its <meta charset> says, as a browser
        does (a byte-order mark comes first)."""
        return b"\xef\xbb\xbf" + self.html.encode("utf-8")

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.snapshot_bytes).hexdigest()

    @property
    def host(self) -> str | None:
        """The host actually fetched (after redirects), read from final_url
        exactly as a verifier reads it. Bound into the signature, beside the
        stated domain."""
        return url_host(self.final_url)

    def manifest_entry(self) -> dict:
        """The `inputs` record for a URL run. The hash is over the exact bytes
        the rules were run on, so the snapshot identifies what was measured."""
        return {
            "path": self.final_url,
            "sha256": self.sha256,
            "bytes": len(self.snapshot_bytes),
            "kind": "url-snapshot",
            "fetch_mode": self.mode,
        }

    def fetch_block(self) -> dict:
        return {
            "requested_url": self.url,
            "final_url": self.final_url,
            "host": self.host,
            "mode": self.mode,
            "http_status": self.status,
            "redirects": self.redirects,
            "redacted": self.redacted,
            "fetched_at": self.fetched_at,
            "browser": self.browser,
            "viewport": self.viewport,
            "wait": self.wait,
            "instrumented": self.instrumented,
            "provenance_attr": self.provenance_attr,
            "attribution": self.attribution,
            "shadow_roots": self.shadow_roots,
            "axe": self.axe,
            "narrow": self.narrow,
            "reader": self.reader,
            "address_class": self.address_class,
            "address_basis": self.address_basis,
            "snapshot_sha256": self.sha256,
            # Assigned after construction too (fetch() sets the reason for a
            # fallback), so cleaned again on the way out.
            "fallback_reason": self._clean_text(self.fallback_reason),
            "notes": [self._clean_text(n) for n in self.notes],
        }


# ---------------------------------------------------------------------------
# Domain binding
# ---------------------------------------------------------------------------

_URL_PARTS = re.compile(r"(https?)://([^/?#]*)(.*)", re.IGNORECASE | re.DOTALL)


def canonical_url(url: str) -> str:
    """`url` with its scheme and host written as a browser writes them: the
    host in the one spelling evidence uses (bundle.normalize_host:
    lowercase, IDNA A-labels, standard IP forms), keeping a domain name's
    trailing dot as browsers do. Nothing else changes, so a URL a browser
    reported comes back as it was. A URL whose host has no such spelling is
    returned as it is."""
    m = _URL_PARTS.match(url or "")
    if not m or "\\" in m.group(2):
        return url
    scheme, authority, rest = m.groups()
    userinfo, at, hostport = authority.rpartition("@")
    if hostport.startswith("["):
        end = hostport.find("]")
        if end < 0:
            return url
        host, port = hostport[1:end], hostport[end + 1:]
    else:
        host, colon, port = hostport.partition(":")
        port = colon + port
    if host != host.strip():
        return url              # not a host a browser would report
    try:
        normal = normalize_host(host)
    except ValueError:
        return url
    is_address = ":" in normal or _ADDRESS.fullmatch(normal)
    if host and _LABEL_DOTS.fullmatch(host[-1]) and not is_address:
        normal += "."           # example.com. stays example.com.
    shown = f"[{normal}]" if ":" in normal else normal
    return f"{scheme.lower()}://{userinfo}{at}{shown}{port}{rest}"


def host_of(url: str) -> str:
    """The host of a URL as evidence records it, or "" when there is none."""
    return url_host(canonical_url(url)) or ""


def domain_matches(url: str, domain: str | None,
                   include_subdomains: bool = False) -> tuple[bool, str]:
    """Is the fetched host the stated domain?

    `--domain` is the claim the signer binds into the statement, so it must
    be the site that was measured: the domain itself or its www. form. A
    subdomain (staging.example.com, pr-123.example.com) is a different site
    and passes only with include_subdomains — and even then the host is
    bound into the signature beside the domain, so it cannot read as the
    domain itself.
    """
    if not domain:
        return True, "no domain stated"
    try:
        want = normalize_host(domain)
    except ValueError as exc:
        return False, str(exc)
    got = host_of(url)
    if not got:
        return False, f"could not parse a host from {redact_url(url)[0]!r}"
    scope = host_scope(got, want)
    if scope == "same":
        return True, f"{got} is {want}"
    if scope == "subdomain":
        if include_subdomains:
            return True, (f"{got} is a subdomain of {_site(want)} "
                          "(allowed by --include-subdomains)")
        return False, (f"fetched host {got!r} is a subdomain of "
                       f"{_site(want)!r}, not {want!r} itself: a staging or "
                       f"preview host is not evidence for the production "
                       f"domain. Pass --domain {got} to evidence that host, "
                       f"or --include-subdomains to record this run as {want} "
                       f"measured at {got}")
    return False, (f"fetched host {got!r} is not {want!r} or a subdomain of "
                   f"it; the run would be signed as evidence for a domain it "
                   f"did not measure")


ALLOWED_SCHEMES = ("http", "https")
DEFAULT_PORTS = {"http": 80, "https": 443}

_SCHEME_NAME = re.compile(r"[A-Za-z][A-Za-z0-9+.\-]*")
_TARGET = re.compile(r"(https?)://([^/?#]*)", re.IGNORECASE)

#: Where to point someone whose URL carried credentials.
CREDENTIALS_HINT = ("pass --http-user USER and put the password in "
                    "$BELLBRIAR_HTTP_PASSWORD or in a file named by "
                    "--http-password-file")


def check_scheme(url: str) -> None:
    """`--url` means a web page, written so that every parser reads the same
    host from it, with no credentials in it.

    A file:// path parses, fetches, and yields a FetchResult with no host
    and no HTTP status — which then slips past the non-200 gate and produces
    a bundle whose `final_url` is a local path. Local files have their own
    code path; reject anything else here.

    A user name or password in the URL is refused: it is already in shell
    history and CI logs, and Chromium would carry it into every URL it
    reports. Credentials go in through `http_credentials` instead. So that
    no parser can find credentials the check missed, the URL must be
    written `http(s)://host…` with no backslash before the path: browsers
    skip extra slashes and end the host at a backslash, other parsers do
    not. Messages never quote the URL with its secrets in it."""
    text = url if isinstance(url, str) else ""
    head, colon, _ = text.partition(":")
    scheme = head.lower() if colon and _SCHEME_NAME.fullmatch(head) else ""
    if scheme not in ALLOWED_SCHEMES:
        raise FetchError(
            f"--url accepts http(s) only, got {scheme or 'no'} scheme. To "
            "evaluate a local file, pass its path as an argument instead of "
            "using --url.")
    m = _TARGET.match(text)
    if not m or not m.group(2):
        raise FetchError(f"--url must be written {scheme}://host/…, with the "
                         "host directly after the two slashes")
    authority = m.group(2)
    if "\\" in authority:
        raise FetchError("--url has a backslash before its path; browsers and "
                         "other URL parsers disagree about which host that "
                         "names. Write it with forward slashes")
    if "@" in authority:
        raise FetchError(
            f"--url carries a user name or password. Credentials in a URL "
            f"leak into shell history and CI logs, and the harness never "
            f"records them: {CREDENTIALS_HINT}. The URL without them is "
            f"{redact_url(text)[0]}")


def url_origin(url: str) -> str:
    """The origin of `url` as a browser writes it — scheme://host[:port],
    with the scheme's default port left out — which is what Playwright
    compares `http_credentials.origin` against. Credentials are offered
    only to this origin."""
    canon = canonical_url(url)
    m = _URL_PARTS.match(canon)
    if not m:
        raise FetchError("not an http(s) URL")
    scheme, authority = m.group(1).lower(), m.group(2)
    hostport = authority.rpartition("@")[2]
    if hostport.startswith("["):
        end = hostport.find("]")
        host, port = hostport[:end + 1], hostport[end + 1:]
    else:
        host, colon, port = hostport.partition(":")
        port = colon + port
    digits = port[1:]
    if not digits:
        port = ""
    elif digits.isdigit() and digits.isascii():
        # A browser reads leading zeros away and refuses a port past 65535
        # (int() would also refuse a run of more than 4,300 digits).
        significant = digits.lstrip("0") or "0"
        if len(significant) > 5 or int(significant) > 65535:
            raise FetchError("the URL's port is out of range")
        number = int(significant)
        port = "" if number == DEFAULT_PORTS[scheme] else f":{number}"
    return f"{scheme}://{host}{port}"


def page_key(url: str) -> tuple[str, str | None]:
    """(the URL as a browser requests it, its fragment or None): scheme and
    host as canonical_url writes them, the default port left out, an empty
    path written "/". Two URLs with one key fetch the same page from the
    server (a fragment is never sent). A URL with no origin is its own
    key."""
    try:
        origin = url_origin(url)
    except FetchError:
        return url, None
    rest = _URL_PARTS.match(canonical_url(url)).group(3)
    rest, hash_, fragment = rest.partition("#")
    if not rest.startswith("/"):
        rest = "/" + rest                  # "?q" alone, or nothing at all
    return origin + rest, (fragment if hash_ else None)


def _check_credentials(credentials) -> tuple[str, str] | None:
    """(user, password) for HTTP authentication, or None."""
    if credentials is None:
        return None
    user, password = credentials
    if not isinstance(user, str) or not isinstance(password, str):
        raise FetchError("HTTP credentials must be a user name and a password")
    if not user:
        raise FetchError("--http-user is empty")
    if ":" in user:
        raise FetchError("--http-user cannot contain ':' (HTTP Basic "
                         "authentication separates user and password with it)")
    if any(ord(c) < 0x20 or ord(c) == 0x7F for c in user + password):
        raise FetchError("HTTP credentials cannot contain control characters")
    return user, password


class _BasicAuthForOrigin(urllib.request.BaseHandler):
    """Offers HTTP Basic credentials to one origin, and only when that origin
    asks for them with a 401 and a Basic challenge — as a browser does. A
    redirect to another origin never receives them.

    urllib's HTTPBasicAuthHandler is not used: it raises ValueError on a
    challenge other than Basic, ignores a Basic challenge without a realm,
    and scopes credentials by host and port, not by scheme."""

    def __init__(self, origin: str, user: str, password: str):
        self.origin = origin
        token = base64.b64encode(f"{user}:{password}".encode("utf-8"))
        self.header = "Basic " + token.decode("ascii")

    def http_error_401(self, req, fp, code, msg, headers):
        if req.get_header("Authorization") == self.header:
            return None                     # refused: report the 401
        challenges = headers.get_all("WWW-Authenticate") or []
        if not any(re.search(r"(?:^|,)\s*basic(?:\s|,|$)", c, re.IGNORECASE)
                   for c in challenges):
            return None
        try:
            if url_origin(req.full_url) != self.origin:
                return None
        except FetchError:
            return None
        try:
            fp.close()                      # urllib never reuses the socket
        except Exception:                    # noqa: BLE001
            pass
        req.add_unredirected_header("Authorization", self.header)
        return self.parent.open(req, timeout=req.timeout)


def address_record(url: str, peer: str | None = None) -> tuple[str, str]:
    """(class, basis), as a capture record holds them (`address_class`,
    `address_basis`).

    The class is loopback, private or public, from the one table `verify`
    reads too (bundle.ADDRESS_TABLE, N13): a bundle fetched from 127.0.0.1
    or 10.x is a test or a staging artifact, not evidence about a public
    site, and the evidence should say so on its face rather than leave a
    reader to infer it from the URL. The basis says what decided it (L20):

      "address"  an address: the host is one (or a shorthand a browser
                 reads as one, `127.1`), or the fetcher connected to the
                 host itself and the address it connected to was seen
                 (`peer`), so `127.0.0.1.nip.io`, or an internal name that
                 resolves to 10.x, is recorded as what it is;
      "name"     the name alone: `localhost` or a name below it, which is
                 loopback by definition (RFC 6761), or any other name whose
                 connected address was not seen — through a proxy, where
                 the address is the proxy's, or after the page went on to
                 another host. "public" then means only that nothing said
                 otherwise.

    NOTE for the hosted runner (ROADMAP item 6): there, the URL comes from a
    customer rather than from whoever runs the CLI, and fetching
    169.254.169.254 or an internal host becomes a live SSRF vector. Address
    filtering belongs in that service — including on every redirect hop, not
    just the first request. This function classifies; it does not block,
    because the CLI's operator chose the target and our own tests fetch
    loopback deliberately.
    """
    host = host_of(url)
    if host == "localhost" or host.endswith(".localhost"):
        return "loopback", "name"
    ip = _address_of(host)
    if ip is None and isinstance(peer, str) and peer:
        ip = _address_of(peer.strip("[]").split("%", 1)[0])
    if ip is None:
        return "public", "name"
    kind = address_kind(ip)
    return (kind[0] if kind else "public"), "address"


def address_class(url: str, peer: str | None = None) -> str:
    """The class address_record gives."""
    return address_record(url, peer)[0]


#: The refusal when a run that starts on a public site is led to a page on
#: a private network (S5-2): a hostile site's redirect, or its script,
#: would otherwise copy an intranet page into the reports, the snapshots
#: and the bundle. The check reads the address the fetch connected to,
#: and otherwise the host's own name and what the system's resolver says
#: of it; through a proxy that resolves names itself it cannot see more.
PRIVATE_HOP = ("{start} is on a public site and led to {host}, {note}: a "
               "run that starts on a public site reads no page on a private "
               "network; to evaluate that page, run the harness on it "
               "directly")


def _private_kind(host: str, peer: str | None = None):
    """(class, note) when `host` is loopback or private: by the address a
    connection went to (`peer`), by its name or literal address
    (bundle.host_kind), or by an address the system's resolver gives for
    it. None when none of them says so."""
    if peer:
        ip = _address_of(str(peer).strip("[]").split("%", 1)[0])
        kind = address_kind(ip) if ip is not None else None
        if kind:
            return kind
    kind = host_kind(host) if host else None
    if kind or not host:
        return kind
    import socket
    try:
        infos = socket.getaddrinfo(host.strip("[]"), None,
                                   proto=socket.IPPROTO_TCP)
    except (OSError, UnicodeError, ValueError):
        return None
    for info in infos:
        ip = _address_of(str(info[4][0]).split("%", 1)[0])
        kind = address_kind(ip) if ip is not None else None
        if kind:
            return kind
    return None


def _refuse_private_page(start: str, result) -> None:
    """refuse_private_hops for a rendered capture: the documents its
    navigation went through, and the one it read, whose address class the
    capture recorded when the browser connected to its host itself. The
    addresses the browser connected to for the document read and the
    redirects on its way there (document_peers) are judged as they were
    then, not only the names resolved again now, which can resolve
    elsewhere (DNS rebinding: S5 re-review)."""
    hops = [(u, None) for u in (result.redirects or [])[1:]]
    hops = list(getattr(result, "document_peers", None) or []) + hops
    if result.address_basis == "address" and result.address_class in (
            "loopback", "private") and not _private_kind(host_of(start)):
        raise FetchError(PRIVATE_HOP.format(
            start=printable(host_of(start)),
            host=printable(result.host or ""),
            note=f"an address of the {result.address_class} kind"))
    refuse_private_hops(start, None, hops + [(result.final_url, None)])


def refuse_private_hops(start: str, start_peer, hops) -> None:
    """Raise FetchError when `start` is on a public site and one of `hops`
    ((URL, the address connected to or None), in order) is on a private
    network (PRIVATE_HOP). A start that is itself loopback or private (a
    staging server, a --render build server) may go anywhere."""
    if _private_kind(host_of(start), start_peer):
        return
    for url, peer in hops:
        try:
            host = host_of(url)
        except FetchError:
            continue
        kind = _private_kind(host, peer)
        if kind:
            raise FetchError(PRIVATE_HOP.format(
                start=printable(host_of(start)), host=printable(host),
                note=kind[1]))


def _address_of(text: str):
    """The address `text` is, read as a browser reads a host (`127.1` and
    `0x7f000001` are 127.0.0.1), or None for a name."""
    if not text:
        return None
    try:
        return ipaddress.ip_address(text)
    except ValueError:
        return _ipv4_shorthand(text)


def _direct(url: str) -> bool:
    """Does a fetch of `url` connect to its host itself, rather than to a
    proxy? Read as urllib reads the proxy settings (http_proxy, https_proxy,
    all_proxy and no_proxy, and the system's settings on macOS and
    Windows), which is where Chromium reads them on those systems and on
    Linux. Unsure is no: the connected address is then left out."""
    try:
        parts = urllib.parse.urlsplit(url)
        host = parts.hostname or ""
        proxies = urllib.request.getproxies()
        if not (proxies.get(parts.scheme.lower()) or proxies.get("all")):
            return True
        return bool(urllib.request.proxy_bypass(host))
    except Exception:                                   # noqa: BLE001
        return False


# ---------------------------------------------------------------------------
# Server fetch
# ---------------------------------------------------------------------------

def _fetch_failure(exc: BaseException) -> str:
    """Why a server fetch failed, in words that cannot quote the URL.

    urllib and http.client put the URL, or pieces of it, into many of their
    messages — a redirect to user:pw@host fails as "nonnumeric port:
    'pw@host'", with no scheme for a URL pattern to find. System errors
    (refused, unresolvable, timed out, TLS) carry no URL and are the ones
    worth reading; anything else is named by its type."""
    reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
    if isinstance(reason, OSError):
        return str(reason)[:MAX_ERROR_TEXT] or type(reason).__name__
    return type(reason).__name__


#: The largest page body a server fetch reads. A larger one is refused, not
#: cut short: a truncated page would be measured as if it were the page.
MAX_PAGE_BYTES = 32 * 1024 * 1024


class _PageTooLarge(Exception):
    pass


class _Abandoned(Exception):
    pass


def _peer_connection(base, peers: list, req):
    """An http.client connection class that records, for every connection
    it makes, (the request's URL, the address it connected to) — the
    address None when it connected to a proxy (urllib then points the
    request at the proxy) or could not tell. One entry per connection, so
    the last one is the connection that answered last, never an earlier
    hop's (R1B-1)."""
    direct = (urllib.parse.urlsplit(req.full_url).netloc.rpartition("@")[2]
              .lower() == (req.host or "").lower())
    url = req.full_url

    class Conn(base):
        def connect(self):
            super().connect()
            peer = None
            if direct:
                try:
                    peer = self.sock.getpeername()[0]
                except Exception:                       # noqa: BLE001
                    peer = None
            peers.append((url, peer))
    return Conn


class _PeerHTTPHandler(urllib.request.HTTPHandler):
    def __init__(self, peers: list):
        super().__init__()
        self.peers = peers

    def http_open(self, req):
        import http.client
        return self.do_open(_peer_connection(http.client.HTTPConnection,
                                             self.peers, req), req)


class _PeerHTTPSHandler(urllib.request.HTTPSHandler):
    def __init__(self, peers: list):
        super().__init__()
        self.peers = peers

    def https_open(self, req):
        import http.client
        return self.do_open(_peer_connection(http.client.HTTPSConnection,
                                             self.peers, req), req,
                            context=self._context)


class _RefusedHop(OSError):
    """A redirect the fetch does not follow (its text is the harness's)."""


class _RedirectRecorder(urllib.request.HTTPRedirectHandler):
    """Records each URL a redirect leads to, so the chain is kept. It
    follows only http and https URLs (urllib's own handler follows ftp
    too), and, when `start` is on a public site, none to a host on a
    private network (refuse_private_hops), before connecting to it."""
    def __init__(self, hops: list, start: str = "", peers: list = None):
        super().__init__()
        self.hops = hops
        self.start = start
        self.peers = peers if peers is not None else []

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urllib.parse.urljoin(req.full_url, newurl)
        why = None
        if urllib.parse.urlsplit(target).scheme.lower() not in ("http",
                                                                "https"):
            why = ("a redirect to a URL that is not http or https is not "
                   "followed")
        elif self.start:
            first = self.peers[0][1] if self.peers else None
            try:
                refuse_private_hops(self.start, first, [(target, None)])
            except FetchError as exc:
                why = str(exc)
        if why is not None:
            # The redirect's own response is not read on: its connection
            # closes here, not when the garbage collector finds it.
            with contextlib.suppress(Exception):
                fp.close()
            raise _RefusedHop(why)
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is not None:
            self.hops.append(new.full_url)
        return new


class _NoFTP(urllib.request.FTPHandler):
    """urllib's default opener reads ftp:, file: and data: URLs too: a
    server fetch reads only http and https ones (check_scheme for the
    first, _RedirectRecorder for each redirect), and these stay closed
    whatever reaches them."""
    def ftp_open(self, req):
        raise _RefusedHop("only http and https URLs are fetched")


class _NoFile(urllib.request.FileHandler):
    def file_open(self, req):
        raise _RefusedHop("only http and https URLs are fetched")


class _NoData(urllib.request.DataHandler):
    def data_open(self, req):
        raise _RefusedHop("only http and https URLs are fetched")


def _read_page(opener, req, timeout, stop) -> tuple:
    """(body, final URL, status, charset) — an error status keeps its body
    and the URL it came from, after any redirects."""
    try:
        resp = opener.open(req, timeout=timeout)
        status, final = resp.status, resp.geturl()
    except urllib.error.HTTPError as exc:
        resp, status, final = exc, exc.code, exc.geturl() or req.full_url
    chunks: list = []
    size = 0
    try:
        read = getattr(resp, "read1", None) or resp.read
        while True:
            if stop.is_set():
                raise _Abandoned()
            chunk = read(65536)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_PAGE_BYTES:
                raise _PageTooLarge()
            chunks.append(chunk)
    except (_Abandoned, _PageTooLarge):
        raise
    except Exception:                                   # noqa: BLE001
        if isinstance(resp, urllib.error.HTTPError):
            chunks = []          # an error page: refused as a non-200 anyway
        else:
            raise
    finally:
        try:
            resp.close()
        except Exception:                               # noqa: BLE001
            pass
    try:
        types = resp.headers.get_all("Content-Type") or []
    except Exception:                                   # noqa: BLE001
        types = []
    return b"".join(chunks), final, status, [str(t) for t in types]


_LWS = " \t"


def _split_values(line: str) -> list[str]:
    """One header line's comma-separated values, as Chromium splits them:
    not at a comma inside double quotes (where a backslash escapes the next
    character); each trimmed, empty ones dropped."""
    out, cur, quoted, i = [], [], False, 0
    while i < len(line):
        ch = line[i]
        if quoted and ch == "\\" and i + 1 < len(line):
            cur.append(line[i:i + 2])
            i += 2
            continue
        if ch == '"':
            quoted = not quoted
        if ch == "," and not quoted:
            out.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
        i += 1
    out.append("".join(cur))
    return [v.strip(_LWS) for v in out if v.strip(_LWS)]


def _parse_one_type(value: str, state: dict) -> None:
    """Chromium's HttpUtil::ParseContentType over one value, updating
    state["mime"] and state["charset"] as it does: a value with no "/" (or
    "*/*") is skipped; a new type resets the charset to its own (possibly
    none); the first `charset` parameter counts, its name exactly "charset"
    in any case (`charset =x` and `charset*=x` are other parameters), its
    value unquoted (a backslash escapes the next character) or up to the
    next ";" with surrounding spaces trimmed (`'x'` keeps its quotes)."""
    start = len(value) - len(value.lstrip(_LWS))
    end = start
    while end < len(value) and value[end] not in _LWS + ";(":
        end += 1
    mime = value[start:end]
    charset, has_charset = "", False
    offset = value.find(";", end)
    while 0 <= offset < len(value):
        offset += 1
        while offset < len(value) and value[offset] in _LWS:
            offset += 1
        name_start = offset
        stops = [i for i in (value.find(";", offset), value.find("=", offset))
                 if i >= 0]
        if not stops:
            break
        offset = min(stops)
        if value[offset] == ";":
            continue
        name = value[name_start:offset]
        offset += 1
        while offset < len(value) and value[offset] in _LWS:
            offset += 1
        if offset >= len(value) or value[offset] == ";":
            continue
        if value[offset] != '"':
            stop = value.find(";", offset)
            stop = len(value) if stop < 0 else stop
            param = value[offset:stop].rstrip(_LWS)
            offset = stop
        else:
            offset += 1
            chars = []
            while offset < len(value) and value[offset] != '"':
                if value[offset] == "\\" and offset + 1 < len(value):
                    offset += 1
                chars.append(value[offset])
                offset += 1
            param = "".join(chars)
            stop = value.find(";", offset)
            offset = len(value) if stop < 0 else stop
        if not has_charset and name.lower() == "charset":
            charset, has_charset = param, True
    if not mime or value == "*/*" or "/" not in mime:
        return                          # (`*/*;charset=x` still counts)
    same = bool(state["mime"]) and mime.lower() == state["mime"]
    if not same:
        state["mime"] = mime.lower()
    if (not same and state["had_charset"]) or has_charset:
        state["had_charset"] = True
        state["charset"] = charset.lower()


def parse_content_type(values) -> tuple[str, str]:
    """(MIME type, charset label) from a response's Content-Type header
    lines, as Chromium 141 reads them (measured): each line split at
    commas outside quotes, each value read in turn; "" for either when
    there is none. The label is not checked here: `'utf-8'`, quotes and
    all, names no encoding (encoding.get_encoding)."""
    state = {"mime": "", "charset": "", "had_charset": False}
    for line in values or ():
        # A header folded over lines (obsolete, but sent) is one line.
        line = re.sub(r"\r?\n[ \t]+", " ", str(line))
        for value in _split_values(line):
            _parse_one_type(value, state)
    return state["mime"], state["charset"]


#: The types Chromium 141 opens as an XML document (measured): it shows
#: application/rss+xml and application/atom+xml as text, and downloads
#: other +xml types (application/mathml+xml, application/xslt+xml).
XML_DOCUMENT_TYPES = frozenset(("text/xml", "application/xml",
                                "application/xhtml+xml", "image/svg+xml",
                                "text/xsl"))


def is_xml_type(mime: str) -> bool:
    """A MIME type Chromium opens as an XML document (XML_DOCUMENT_TYPES)."""
    return (mime or "").lower() in XML_DOCUMENT_TYPES


def page_reader(mime: str) -> str | None:
    """How a response of this MIME type is read as a page: "html" for
    text/html (or no usable type, which a browser sniffs), "xml" for an XML
    document type, None for anything a browser shows as text (text/plain,
    application/json, a feed) or saves as a file: no page to evaluate."""
    mime = (mime or "").lower()
    if mime in ("", "*/*", "text/html"):
        return "html"
    return "xml" if mime in XML_DOCUMENT_TYPES else None


def decode_html(body: bytes, charset: str | None = None,
                xml: bool = False) -> str:
    """Page bytes a server sent, as text, decoded as Chromium decodes them
    (encoding.sniff): a byte-order mark, then the charset the server
    declared, then a <meta> found as Chromium's meta-charset scan finds it,
    then an XML declaration; with none of them, windows-1252, however UTF-8
    the bytes are (Chromium detects UTF-8 only in local files). Only labels
    the Encoding Standard lists count: `base64` or `utf-7` is no encoding,
    as no browser decodes it. An `xml` document (an XML MIME type) is
    decoded as Chromium decodes XML: no <meta> counts, and UTF-8 is the
    default."""
    from .encoding import sniff
    return sniff(body, charset or None, xml=xml).text


def fetch_bytes(url: str, timeout: int = 30,
                http_credentials: tuple[str, str] | None = None,
                record_query=()) -> tuple:
    """(body, final URL, status, Content-Type values, redirect hops,
    connections) for one GET: each connection as (URL, the address
    connected to, or None through a proxy), in order. `timeout` bounds the
    whole fetch — connecting, redirects, a login retry and reading the body
    — not only each read, so a server that trickles bytes cannot hold the
    run; a body over MAX_PAGE_BYTES is refused. Credentials go only to the
    URL's origin. A failure raises FetchError, its text redacted."""
    import threading
    check_scheme(url)
    credentials = _check_credentials(http_credentials)
    keep = tuple(sorted(names(record_query)))
    req = urllib.request.Request(url, headers={"user-agent": "bellbriar-eval"})
    peers: list = []
    hops: list = []
    handlers = [_PeerHTTPHandler(peers), _PeerHTTPSHandler(peers),
                _RedirectRecorder(hops, url, peers), _NoFTP(), _NoFile(),
                _NoData()]
    if credentials:
        handlers.append(_BasicAuthForOrigin(url_origin(url), *credentials))
    opener = urllib.request.build_opener(*handlers)
    box: dict = {}
    stop = threading.Event()

    def work():
        try:
            box["page"] = _read_page(opener, req, timeout, stop)
        except BaseException as exc:                    # noqa: BLE001
            box["error"] = exc

    worker = threading.Thread(target=work, name="bellbriar-server-fetch",
                              daemon=True)
    worker.start()
    worker.join(timeout)
    failure = None
    if worker.is_alive():
        stop.set()               # it stops at its next read; nothing waits
        failure = f"no complete response within {timeout} s"
    elif isinstance(box.get("error"), _PageTooLarge):
        failure = (f"the page is larger than {MAX_PAGE_BYTES // (1024 * 1024)}"
                   " MiB, so it was not read")
    elif "error" in box:
        failure = _fetch_failure(box["error"])
    if failure is not None:
        # Raised with no exception as its context, so no URL comes with it.
        scrub = secret_values(url, keep) | (
            {credentials[1]} if credentials else set())
        raise FetchError(redact_text(f"could not fetch {url}: {failure}",
                                     scrub, keep))
    body, final, status, types = box["page"]
    # Each connection after the first, by the address it went to: a name
    # that resolved one way for the check before the redirect and another
    # for the connection is caught here (S5-2).
    first = peers[0][1] if peers else None
    refuse_private_hops(url, first, peers[1:] + [(final, None)])
    return body, final, status, types, hops, peers


def fetch_server(url: str, timeout: int = 30,
                 http_credentials: tuple[str, str] | None = None,
                 record_query=()) -> FetchResult:
    """The HTML the server sends (fetch_bytes), read as a page: refused
    when its type is no page a browser shows."""
    credentials = _check_credentials(http_credentials)
    keep = tuple(sorted(names(record_query)))
    body, final, status, types, hops, peers = fetch_bytes(
        url, timeout, credentials, keep)
    mime, charset = parse_content_type(types)
    reader = page_reader(mime)
    if reader is None:
        scrub = secret_values(url, keep)
        # The type is the server's word, escaped as any text a server
        # writes is before a console or a report shows it (R4G-5).
        shown = printable(mime[:100], backslash=True)
        raise FetchError(redact_text(
            f"{url} is not a web page: the server sent it as {shown}, which "
            "a browser shows as text or saves as a file, so there is nothing "
            "to evaluate", scrub, keep))
    xml = reader == "xml"
    html = decode_html(body, charset, xml=xml)
    redirects = [url, *hops] if hops else ([url, final] if final != url else [])
    result = FetchResult(url=url, final_url=final, mode=SERVER, html=html,
                         reader=reader,
                         status=status, redirects=redirects,
                         fetched_at=datetime.now(timezone.utc).isoformat(
                             timespec="seconds"),
                         record_query=keep,
                         redacted=["http-credentials"] if credentials else [])
    # The address counts only when the connection that answered last went
    # to the recorded host itself: not to a proxy, and not an earlier hop's
    # connection to another host (R1B-1). The class is the recorded host's,
    # as a verifier reads it (R1B-8).
    last_url, last_peer = peers[-1] if peers else ("", None)
    peer = (last_peer if last_peer and result.host
            and host_of(last_url.split("#", 1)[0]) == result.host else None)
    result.address_class, result.address_basis = address_record(
        result.final_url, peer)
    return result


# ---------------------------------------------------------------------------
# Rendered fetch
# ---------------------------------------------------------------------------

def playwright_available() -> tuple[bool, str]:
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError:
        return False, ("playwright is not installed — install the harness "
                       "with its browser extra (pipx install "
                       "'bellbriar-harness[browser]', or uv tool install "
                       "'bellbriar-harness[browser]'), then run "
                       "bellbriar-eval --install-browser")
    return True, ""


def _page_int(value, low: int, high: int) -> int | None:
    """A count or duration measured inside the page, fit for the evidence
    bundle. The page's own scripts can replace Date.now and friends, so
    anything that is not a whole number in range is recorded as unknown
    rather than trusted (NaN or 1e300 would make the bundle unsignable)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value != value or not low <= value <= high or value != int(value):
        return None
    return int(value)


def _vendor_entries(third_party_origins) -> tuple[list[str], list[str]]:
    """Split --third-party-origin values into bare domains (suffix match)
    and full origins (exact match, e.g. http://127.0.0.1:8001).

    An origin is written as the instrumentation compares it — a browser's
    URL.origin, default port left out — and never carries a user name or
    password: these values are recorded in the fetch block."""
    domains, origins = list(KNOWN_VENDOR_DOMAINS), []
    for raw in third_party_origins or ():
        v = (raw or "").strip().rstrip("/")
        if not v:
            continue
        if "://" in v:
            u = urllib.parse.urlparse(v)
            if not (u.scheme and u.hostname):
                continue
            if u.scheme.lower() in ALLOWED_SCHEMES:
                try:
                    origins.append(url_origin(redact_url(v)[0]).lower())
                    continue
                except FetchError:
                    pass
            try:
                port = f":{u.port}" if u.port else ""
            except ValueError:
                continue
            origins.append(f"{u.scheme}://{u.hostname}{port}".lower())
        else:
            domains.append(v.lower().lstrip("."))
    return domains, origins


def materialize_shadow_roots(html: str, provenance_attr: str | None = None) -> str:
    """The capture's serialized shadow roots as markup the static rules
    evaluate (shadow.materialize): each `<template shadowrootmode>` the
    capture wrote becomes a `<bb-shadow-root>`, with the host's light-DOM
    children in the slots that render them. A <template> that carries the
    capture's provenance attribute is an element of the document (every
    one is stamped), not a shadow root, and is left alone.

    The capture is the browser's serialization of the live DOM, so it is
    read with html.parser, which keeps the nesting the live page had.
    """
    if "shadowrootmode" not in html:
        return html
    from .checks_static import too_deep
    from .html5 import BudgetSoup
    from .shadow import materialize, partial_attr, slotted_attr
    soup = BudgetSoup(html, "html.parser")
    too_deep(soup)                 # before anything walks the roots
    # Each element moved into a slot is recorded under the capture's
    # secret, so the rules know it is light DOM (shadow.mark_capture).
    materialize(soup, lambda t: t.get("shadowrootmode") is not None and not (
        provenance_attr and t.has_attr(provenance_attr)),
        slotted_attr=slotted_attr(provenance_attr) if provenance_attr else None,
        partial_attr=partial_attr(provenance_attr) if provenance_attr else None)
    return str(soup)


class SandboxRefused(Exception):
    """Chromium's sandbox could not start and the run was told to refuse
    rather than run the browser without it (--require-sandbox, D9). Not a
    FetchError: no page of the run is evaluated, and nothing falls back to
    the server's HTML."""


#: What Chromium says when its sandbox cannot start, and what the record
#: says instead (L27): the fallback is taken for these errors and no
#: other, so a launch that failed for another reason that happens to
#: mention the sandbox is not retried without it.
#: Why the sandbox found no user namespaces: the host's kernel or AppArmor
#: policy can refuse them (Ubuntu 23.10 and later restrict them), and so
#: can a container's seccomp profile (Docker's default does), R4A-2.
_NO_USERNS = ("user namespaces are not available to it here (the host, or "
              "a container's security profile, does not allow them)")
_SANDBOX_ERRORS = (
    (re.compile(r"No usable sandbox"), _NO_USERNS),
    (re.compile(r"Failed to move to new namespace"), _NO_USERNS),
    # Where the host lets Chromium make a user namespace but not map its
    # user into it, as AppArmor's restriction does (R4B-6):
    # "[FATAL:sandbox/linux/services/credentials.cc:131] Check failed: . :
    # Permission denied (13)", or credentials.cc(126) in older builds.
    (re.compile(r"credentials\.cc[:(]\d+\)?\] Check failed"), _NO_USERNS),
    (re.compile(r"The SUID sandbox helper binary"),
     "its setuid helper is not set up"),
    (re.compile(r"Running as root without --no-sandbox"), "running as root"),
)


def _sandbox_failure(exc: BaseException) -> str:
    """Why Chromium's sandbox could not start, in the record's words, when
    `exc` is the launch failing for that; else "" (L27)."""
    text = str(exc)
    for said, why in _SANDBOX_ERRORS:
        if said.search(text):
            return why
    return ""


def _launch_chromium(p, require_sandbox: bool = False) -> tuple:
    """(browser, why the sandbox is off or ""). Chromium's sandbox keeps a
    renderer exploit on an untrusted page from running as this user — in
    CI, beside the repository's secrets — so it is on whenever it can
    start. It cannot run as root (containers often are), and some hosts
    give it no user namespaces; then the browser runs without it and the
    capture records that it did (fetch.browser.sandbox, and a note), or,
    with `require_sandbox`, the run is refused (SandboxRefused, D9)."""
    import os
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        if require_sandbox:
            raise SandboxRefused(
                "--require-sandbox: this run is running as root, where "
                "Chromium's sandbox cannot start; run it as an ordinary "
                "user where unprivileged user namespaces are allowed (in a "
                "container, that takes a seccomp profile that allows them "
                "too)")
        return (p.chromium.launch(chromium_sandbox=False),
                "running as root, where Chromium's sandbox cannot start")
    try:
        return p.chromium.launch(chromium_sandbox=True), ""
    except Exception as exc:                            # noqa: BLE001
        why = _sandbox_failure(exc)
        if not why:
            raise
    if require_sandbox:
        raise SandboxRefused(
            f"--require-sandbox: Chromium's sandbox could not start here "
            f"({why}); allow unprivileged user namespaces (in a container, "
            "with a seccomp profile that allows them too), or run without "
            "--require-sandbox to let it run without one, as the record "
            "would then say")
    return (p.chromium.launch(chromium_sandbox=False),
            f"it could not start here: {why}")


#: How deep DOM.describeNode is asked to describe a closed shadow root's
#: host. Chromium cannot return a description nested much deeper (its
#: protocol encoder stops at about 145 levels), so a component nested
#: deeper inside is looked through to this depth and the capture notes it.
CLOSED_ROOT_SCAN_DEPTH = 140
#: How many hosts of closed shadow roots the protocol search describes.
#: Each costs two round trips; a page cannot make the capture take minutes
#: by holding a hundred thousand of them. Past this, the capture notes it.
MAX_CLOSED_ROOT_HOSTS = 5000


def _closed_shadow_roots(cdp) -> tuple[list, str]:
    """The objectIds of the closed shadow roots in the page's document, in
    the page's own world, and a note when the search could not cover it
    all (_closed_root_backends)."""
    backend_ids, note = _closed_root_backends(cdp)
    ids, missed = _resolve_nodes(cdp, backend_ids)
    if missed:
        note = "; ".join(n for n in (note, f"{missed} closed shadow root(s) "
                                     "could not be captured") if n)
    return ids, note


def _resolve_nodes(cdp, backend_ids, context_id: int | None = None
                   ) -> tuple[list, int]:
    """(objectIds of the nodes, in the page's own world or the world
    `context_id` names; how many could not be resolved)."""
    ids, missed = [], 0
    for b in backend_ids:
        params = {"backendNodeId": b}
        if context_id is not None:
            params["executionContextId"] = context_id
        try:
            ids.append(cdp.send("DOM.resolveNode", params)["object"]["objectId"])
        except Exception:                               # noqa: BLE001
            missed += 1
    return ids, missed


def _closed_root_backends(cdp) -> tuple[list, str]:
    """The backend node ids of the closed shadow roots in the page's
    document, and a note when the search could not cover it all. The
    DevTools protocol
    sees every shadow root, however it was made: a closed declarative root
    (<template shadowrootmode="closed"> in the HTML or in markup passed to
    setHTMLUnsafe) or one attached through another frame's attachShadow,
    which no script in the page can reach.

    DOMSnapshot lists the page's nodes flat, each with the kind of shadow
    root it is in, so a node in a closed root whose parent is not marks
    that parent as a host, at any depth and in one call. Each such host is
    then described with its subtree (pierce), which gives the root objects,
    nested closed roots included. Browser-internal (user-agent) roots,
    template content and other documents (iframes) are skipped. A closed
    root with nothing in it holds nothing to evaluate and is not found."""
    snap = cdp.send("DOMSnapshot.captureSnapshot", {"computedStyles": []})
    strings = snap.get("strings") or []
    nodes = ((snap.get("documents") or [{}])[0] or {}).get("nodes") or {}
    rare = nodes.get("shadowRootType") or {}
    kind = {i: strings[v] for i, v in zip(rare.get("index") or (),
                                          rare.get("value") or ())
            if isinstance(v, int) and 0 <= v < len(strings)}
    parents = nodes.get("parentIndex") or []
    backend = nodes.get("backendNodeId") or []
    hosts: list = []
    for i, k in kind.items():
        if k != "closed" or not 0 <= i < len(parents):
            continue
        p = parents[i]
        if (isinstance(p, int) and 0 <= p < len(backend)
                and kind.get(p) != "closed" and backend[p] not in hosts):
            hosts.append(backend[p])
    backend_ids: list = []
    deeper = missed = 0
    skipped = max(0, len(hosts) - MAX_CLOSED_ROOT_HOSTS)
    for host in hosts[:MAX_CLOSED_ROOT_HOSTS]:
        try:
            node = cdp.send("DOM.describeNode", {
                "backendNodeId": host, "depth": CLOSED_ROOT_SCAN_DEPTH,
                "pierce": True})["node"]
        except Exception:                               # noqa: BLE001
            missed += 1
            continue
        stack = [(node, 0)]
        while stack:
            n, depth = stack.pop()
            if not isinstance(n, dict):
                continue
            if depth >= CLOSED_ROOT_SCAN_DEPTH and n.get("nodeType") == 1:
                deeper += 1              # its children and roots unseen
                continue
            for sr in n.get("shadowRoots") or ():
                k = sr.get("shadowRootType") if isinstance(sr, dict) else None
                if k not in ("open", "closed"):
                    continue
                if (k == "closed" and isinstance(sr.get("backendNodeId"), int)
                        and sr["backendNodeId"] not in backend_ids):
                    backend_ids.append(sr["backendNodeId"])
                stack.append((sr, depth + 1))
            for child in n.get("children") or ():
                stack.append((child, depth + 1))
    notes = []
    if deeper:
        notes.append(f"a component with a closed shadow root nests more than "
                     f"{CLOSED_ROOT_SCAN_DEPTH} levels deep; below that depth "
                     "inside it, only closed shadow roots the page attached "
                     "with its own attachShadow were captured")
    if missed:
        notes.append(f"{missed} closed shadow root(s) could not be captured")
    if skipped:
        notes.append(f"the page has more than {MAX_CLOSED_ROOT_HOSTS} hosts of "
                     f"closed shadow roots; {skipped} were not looked into, and "
                     "only closed roots the page attached with its own "
                     "attachShadow were captured there")
    return backend_ids, "; ".join(notes)


def _capture_args(token: str, provenance_attr: str) -> str:
    return (f"{json.dumps(token)}, {json.dumps(provenance_attr)}, "
            f"{json.dumps(muted_attr(provenance_attr))}, "
            f"{json.dumps(hidden_attr(provenance_attr))}")


def _js_literal(value) -> str:
    """`value` as a JavaScript literal in which no object has a prototype
    (`{"__proto__": null, …}` makes one so), so the page's own world reads
    it without consulting anything a page script can define: own
    properties only. JSON otherwise (JSON is JavaScript)."""
    if isinstance(value, dict):
        return "{" + ",".join(['"__proto__":null'] + [
            f"{json.dumps(str(k))}:{_js_literal(v)}"
            for k, v in value.items()]) + "}"
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_js_literal(v) for v in value) + "]"
    return json.dumps(value)


def index_attr(provenance_attr: str) -> str:
    """Where a capture writes each element's index in it, for the narrow
    record taken after it (_place_narrow); never left in a snapshot."""
    return provenance_attr + "-n"


def _capture_extra(axe: dict | None, index: bool, provenance_attr: str) -> str:
    """The capture's last argument (`extra`): the records the capture
    writes besides its own, under names derived from `provenance_attr`:
    placeholders for axe-core's (_AxeSession.extra), and each element's
    index when a narrow record is to follow (_record_narrow)."""
    return _js_literal({
        "axe": None if not axe else {
            "attr": axe_attr(provenance_attr),
            "runAttr": axe_run_attr(provenance_attr),
            "roots": axe["roots"], "marks": axe["marks"]},
        "index": index_attr(provenance_attr) if index else ""})


def _new_provenance_attr() -> str:
    return "data-bb-p-" + secrets.token_hex(8)


def _resolve_pairs(cdp, backend_ids, context_id: int | None = None
                   ) -> tuple[list, int]:
    """([(backend node id, objectId)] for the nodes that resolve, in the
    page's own world or the world `context_id` names; how many did not)."""
    pairs, missed = [], 0
    for b in backend_ids:
        params = {"backendNodeId": b}
        if context_id is not None:
            params["executionContextId"] = context_id
        try:
            pairs.append((b, cdp.send("DOM.resolveNode",
                                      params)["object"]["objectId"]))
        except Exception:                               # noqa: BLE001
            missed += 1
    return pairs, missed


def _call_capture(ctx, page, capture_prop: str, token: str, axe=None,
                  index: bool = False):
    """Run the capture entry point: (its result or None, a note or "", the
    provenance attribute it stamped under, axe-core's session or None).

    Over CDP, not page.evaluate: Playwright passes arguments and reads the
    result with JavaScript in the page's own realm (array destructuring, a
    `then` lookup), which page code can hook to learn the secret attribute
    names or rewrite the returned snapshot. Runtime.evaluate with
    returnByValue takes the names as literals in the expression and
    serializes the result natively. Closed shadow roots no page script can
    reach (_closed_root_backends) are passed in as protocol object
    references, with Runtime.callFunctionOn, which hands them to the
    function as its arguments without running page code. The entry point
    answers only a call with `token`, which only the harness knows.

    `axe(cdp, closed)`, when given, runs axe-core first over the same
    protocol session, with the closed shadow roots' backend node ids, and
    returns its _AxeSession: the roots it was given are passed to the
    capture first, the session says where each element it reported is
    right before the capture (`extra`), and checks right after it what the
    page changed in between (`check`). `index`: stamp each element's index
    too, for the narrow record (_record_narrow).

    A second attempt, after the first failed in the protocol, stamps under
    new names: if the first ran at all, the page may have seen its names
    (a MutationObserver reports attribute names after the fact). It
    carries no record of axe-core's, whose places were found for the
    first names."""
    provenance_attr = _new_provenance_attr()
    cdp = None
    note = ""
    session = None
    try:
        cdp = ctx.new_cdp_session(page)
        try:
            backend, note = _closed_root_backends(cdp)
        except Exception:                               # noqa: BLE001
            backend, note = [], "closed shadow roots could not be listed"
        pairs, missed = _resolve_pairs(cdp, backend)
        if missed:
            note = "; ".join(n for n in (note, f"{missed} closed shadow "
                                         "root(s) could not be captured") if n)
        if axe is not None:
            try:
                session = axe(cdp, backend)
            except Exception:                           # noqa: BLE001
                session = None
        given = session.registered if session is not None else set()
        closed = ([oid for b, oid in pairs if b in given]
                  + [oid for b, oid in pairs if b not in given])
        axe_extra = None
        if session is not None:
            axe_extra = session.extra(cdp, provenance_attr,
                                      sum(1 for b, _ in pairs if b in given))
        res = None
        if closed:
            try:
                res = cdp.send("Runtime.callFunctionOn", {
                    "functionDeclaration": (
                        f"function () {{ return window[{json.dumps(capture_prop)}]"
                        f"({_capture_args(token, provenance_attr)}, arguments, "
                        f"{_capture_extra(axe_extra, index, provenance_attr)}); }}"),
                    "objectId": closed[0],
                    "arguments": [{"objectId": oid} for oid in closed],
                    "returnByValue": True})
            except Exception:                           # noqa: BLE001
                res = None
                note = (f"{len(closed)} closed shadow root(s) could not be "
                        "captured")
        if res is None:
            if closed:
                provenance_attr = _new_provenance_attr()
                axe_extra = None
                if session is not None:
                    session.fail("the capture had to be taken again without "
                                 "the closed shadow roots, so axe-core's "
                                 "results could not be matched to it")
            res = cdp.send("Runtime.evaluate", {
                "expression": (f"window[{json.dumps(capture_prop)}]"
                               f"({_capture_args(token, provenance_attr)}, null, "
                               f"{_capture_extra(axe_extra, index, provenance_attr)})"),
                "returnByValue": True})
        if session is not None:
            session.check(cdp)
    except Exception:                                   # noqa: BLE001
        return None, note, provenance_attr, session
    finally:
        if cdp is not None:
            try:
                cdp.detach()
            except Exception:                           # noqa: BLE001
                pass
    if not isinstance(res, dict) or res.get("exceptionDetails"):
        return None, note, provenance_attr, session
    value = (res.get("result") or {}).get("value")
    return ((value if isinstance(value, dict) else None), note,
            provenance_attr, session)


#: The capture's second viewport (L24): what the page hides at phone width,
#: and whether it reflows at 320 CSS pixels (WCAG 1.4.10), are recorded
#: there after the capture is taken at the capture's own viewport. The page
#: stays narrow after that: nothing more is read from it.
NARROW_VIEWPORT = {"width": 320, "height": 640}
#: How long the page may take to settle once it is narrowed.
NARROW_SETTLE_CAP_MS = 4000


def _record_narrow(ctx, page, capture_prop: str, token: str) -> dict | None:
    """Take the narrow viewport's record (the instrumentation's
    recordNarrow), after the capture, with the viewport narrowed: what the
    page hides there, which elements make it scroll sideways, and which the
    page changed since the capture, each named by its index in the capture.
    Over the DevTools protocol as the capture is (_call_capture), with the
    closed shadow roots passed in. Answers the record, or None when it
    could not be taken."""
    cdp = None
    try:
        cdp = ctx.new_cdp_session(page)
        try:
            backend, _ = _closed_root_backends(cdp)
        except Exception:                               # noqa: BLE001
            backend = []
        closed, _ = _resolve_nodes(cdp, backend)
        call = (f"window[{json.dumps(capture_prop + '_narrow')}]"
                f"({json.dumps(token)}")
        if closed:
            res = cdp.send("Runtime.callFunctionOn", {
                "functionDeclaration": f"function () {{ return {call}, arguments); }}",
                "objectId": closed[0],
                "arguments": [{"objectId": oid} for oid in closed],
                "returnByValue": True})
        else:
            res = cdp.send("Runtime.evaluate", {
                "expression": f"{call}, null)", "returnByValue": True})
    except Exception:                                   # noqa: BLE001
        return None
    finally:
        if cdp is not None:
            try:
                cdp.detach()
            except Exception:                           # noqa: BLE001
                pass
    if not isinstance(res, dict) or res.get("exceptionDetails"):
        return None
    value = (res.get("result") or {}).get("value")
    return value if isinstance(value, dict) else None


def _narrow_pairs(pairs, values) -> dict:
    """{index: value} from the record's [index, value] pairs, each value one
    `values` accepts; anything else is dropped."""
    out: dict = {}
    for pair in pairs if isinstance(pairs, list) else ():
        if (isinstance(pair, list) and len(pair) == 2
                and isinstance(pair[0], int) and not isinstance(pair[0], bool)
                and 0 <= pair[0] < 10 ** 8 and values(pair[1])):
            out[pair[0]] = pair[1]
    return out


#: What reaches past the page's edge in an element that does, as the
#: narrow record says it (the instrumentation's overflowKind): text or a
#: form control ("c"), only content WCAG 1.4.10 exempts ("x"), or nothing
#: it shows ("e").
REFLOW_KINDS = ("c", "x", "e")


def _reflow_value(v) -> bool:
    if not isinstance(v, str) or len(v) > 100:
        return False
    try:
        mark = json.loads(v)
    except ValueError:
        return False
    return (isinstance(mark, dict) and set(mark) == {"r", "k"}
            and isinstance(mark["r"], int) and not isinstance(mark["r"], bool)
            and mark["k"] in REFLOW_KINDS)


def place_capture_record(html: str, provenance_attr: str,
                         browser) -> str:
    """The capture with its own record on its root element
    (model.capture_attr): the Chromium that captured it, and the version of
    its marks (model.MARKS_VERSION). The root's start tag is the first to
    carry the provenance attribute, whose secret name no page knows before
    the capture is serialized; any record under the capture record's name
    goes first. Without the provenance attribute, the html as it is: a
    re-run then finds no record and evaluates nothing (L53, L106)."""
    import html as H
    name = capture_attr(provenance_attr)
    html = re.sub(" " + re.escape(name) + r'="[^"]*"', "", html)
    at = html.find(f' {provenance_attr}="')
    if at < 0:
        return html
    record = json.dumps({"browser": browser if isinstance(browser, str)
                         else None, "marks": MARKS_VERSION},
                        separators=(",", ":"))
    return html[:at] + f' {name}="{H.escape(record)}"' + html[at:]


def _place_narrow(html: str, provenance_attr: str, info: dict | None,
                  root: int | None) -> tuple[str, bool, bool]:
    """The capture with the narrow record written in: each element the
    capture indexed (index_attr) gets its mark of what the page hides at
    the narrow viewport (model.narrow_hidden_attr), a mark when the page
    changed it, or what it holds, since the capture ("self" or "children":
    model.narrow_changed_attr), and, if it
    reaches past the page's edge there, its reflow mark
    (model.reflow_attr); the root element gets "recorded" and the reflow
    measurement (model.reflow_run_attr). What the page hides there is
    written only when what it changed is known too. Every index attribute
    goes, whatever else happens. Returns (the html, whether hiding was
    recorded, whether reflow was)."""
    import html as H
    pattern = re.compile(r" " + re.escape(index_attr(provenance_attr))
                         + r'="(\d+)"')
    if not isinstance(info, dict) or root is None:
        return pattern.sub("", html), False, False
    hiding = info.get("recorded") is True and info.get("watched") is True
    marks = _narrow_pairs(info.get("marks"), lambda v: v in (
        "display", "visibility", "shown", "skips", "shown-skips",
        "visibility-skips", "unrendered", "unboxed", "unrendered-visibility",
        "unboxed-visibility")) if hiding else {}
    changed = _narrow_pairs(info.get("changed"), lambda v: v in (
        "self", "children")) if hiding else {}
    if hiding and info.get("changedAll") is True:
        # More changes than the watch keeps count of: the page changed
        # everything, as far as the record can tell.
        changed = {root: "self"}
    reflow = _narrow_pairs(info.get("reflow"), _reflow_value)
    sw = _page_int(info.get("scrollWidth"), 0, 10 ** 7)
    cw = _page_int(info.get("clientWidth"), 1, 10 ** 7)
    measured = info.get("measured") is True and sw is not None and cw is not None
    narrow, refl = narrow_hidden_attr(provenance_attr), reflow_attr(provenance_attr)
    moved = narrow_changed_attr(provenance_attr)
    run = json.dumps({"width": NARROW_VIEWPORT["width"],
                      "height": NARROW_VIEWPORT["height"],
                      "scroll_width": sw, "client_width": cw,
                      "clipped": info.get("clipped") is True},
                     separators=(",", ":"))
    placed = {"root": False}

    def write(m):
        i = int(m.group(1))
        out = ""
        if i == root:
            placed["root"] = True
            if hiding:
                out += f' {narrow}="recorded"'
            if measured:
                out += f' {reflow_run_attr(provenance_attr)}="{H.escape(run)}"'
        if i in marks:
            out += f' {narrow}="{marks[i]}"'
        if i in changed:
            out += f' {moved}="{changed[i]}"'
        if measured and i in reflow:
            out += f' {refl}="{H.escape(reflow[i])}"'
        return out
    written = pattern.sub(write, html)
    if not placed["root"]:
        return pattern.sub("", html), False, False
    return written, hiding, measured


def _narrow_outcome(info: dict | None, hiding: bool, reflow: bool,
                    settled: bool, notes: list) -> dict | None:
    """The capture record's `narrow` block: the viewport, whether the
    snapshot records what the page hides there (`hiding_recorded`), how
    many elements the page changed after the capture (`changed`), and its
    reflow measurement (_place_narrow); None when no narrow record was
    taken. Every number came from inside the page and is range-checked."""
    if not isinstance(info, dict) or not (hiding or reflow):
        notes.append("what the page hides at 320 CSS pixels wide, and how it "
                     "reflows there, could not be recorded, so neither was "
                     "evaluated")
        return None
    sw = _page_int(info.get("scrollWidth"), 0, 10 ** 7)
    cw = _page_int(info.get("clientWidth"), 1, 10 ** 7)
    clipped = reflow and info.get("clipped") is True
    block = {"viewport": dict(NARROW_VIEWPORT),
             "settled": bool(settled),
             "hiding_recorded": hiding,
             "changed": (len(_narrow_pairs(info.get("changed"), lambda v: v in (
                 "self", "children"))) if hiding else 0),
             "changed_all": hiding and info.get("changedAll") is True,
             "reflow_recorded": reflow,
             "scroll_width": sw if reflow else None,
             "client_width": cw if reflow else None,
             "clipped": clipped,
             "overflowing": (len(_narrow_pairs(info.get("reflow"),
                                               _reflow_value))
                             if reflow else 0)}
    if not hiding and info.get("recorded") is True:
        notes.append("what the page changed after the capture could not be "
                     "watched, so what it hides at 320 CSS pixels wide was not "
                     "evaluated")
    if hiding and info.get("changedAll") is True:
        notes.append("the page changed itself more than a million times after "
                     "the capture: what only the page at 320 CSS pixels wide "
                     "shows is reported for review, not as failures")
    if info.get("bodyHidden") is True and hiding:
        notes.append("the page's <body> was hidden at 320 CSS pixels wide; "
                     "content inside it was read as shown there")
    if clipped:
        notes.append("at 320 CSS pixels wide the page hides what reaches past "
                     "its right edge (overflow-x on the root element or the "
                     "body), so it cannot scroll sideways; content it cuts "
                     "off there is not detected")
    if not settled:
        notes.append(f"at 320 CSS pixels wide the DOM was still mutating when "
                     f"the {NARROW_SETTLE_CAP_MS} ms cap was reached")
    return block


#: The isolated world axe-core runs in (Page.createIsolatedWorld). Made
#: again under this name in the same document, it is the same world.
AXE_WORLD = "bellbriar-axe"

#: The isolated world's helper (axe.RUNNER_JS).
_AXE = "window.__bellbriar_axe"


def _place_steps(steps) -> bool:
    """Is `steps` a place the isolated world gives (RUNNER_JS `paths`),
    small enough to hand to the capture?"""
    if not (isinstance(steps, list) and 0 < len(steps) <= 4096):
        return False
    size = 0
    for s in steps:
        if not (isinstance(s, list) and len(s) == 2 and isinstance(s[1], str)):
            return False
        if s[0] == "s":
            if s[1] != "":
                return False
        elif not (isinstance(s[0], int) and not isinstance(s[0], bool)
                  and 0 <= s[0] < 10 ** 7 and 0 < len(s[1]) <= 1024):
            return False
        size += len(s[1])
    return size <= 200_000


class _AxeSession:
    """axe-core on one page, over the protocol session that takes the
    capture (axe.py): run in an isolated world of the harness's own, which
    shares the page's DOM but none of its JavaScript, so the page's scripts
    can neither change what axe-core calls nor read its results; then,
    right before the capture, asked where each element it reported is
    (`extra`); right after it, asked what the page changed on the way
    (`check`); and last written into the serialized capture (`place`).
    Every failure is worded by the harness: a page can make axe-core raise
    with any text.

    Nothing axe-core found is lost silently. A result that does not reach
    the snapshot on its element (the page removed or moved the element
    first, or there were more than axe.MAX_ELEMENTS) is counted in the
    run's record under its rule, and the rule reports it about the page
    (checks_rendered). When the results cannot be matched to the capture at
    all, no record is written and the rules are not evaluated."""

    def __init__(self, cdp, closed_backend, timeout_ms: int | None = None):
        from . import axe as A
        self.A = A
        self.timeout_ms = int(timeout_ms or A.DEFAULT_TIMEOUT_MS)
        self.block: dict = {"engine": "axe-core", "version": A.AXE_VERSION,
                            "sha256": A.AXE_SHA256, "ran": False}
        self.notes: list[str] = []
        self.answer = None
        self.world = None
        #: The closed shadow roots axe-core was given (backend node ids).
        self.registered: set = set()
        self.added = 0
        self.invalid: set = set()
        self.checked = False
        #: Why axe-core's results cannot be recorded, once they cannot.
        self.failure = ""
        self._run(cdp, list(closed_backend or ()))

    def fail(self, reason: str) -> None:
        if not self.failure:
            self.failure = reason

    def _eval(self, cdp, expression: str):
        res = cdp.send("Runtime.evaluate", {
            "expression": expression, "contextId": self.world,
            "returnByValue": True})
        if not isinstance(res, dict) or res.get("exceptionDetails"):
            raise RuntimeError("raised")
        return (res.get("result") or {}).get("value")

    def _not_run(self, reason: str) -> None:
        self.block["reason"] = reason
        self.notes.append(f"{reason}, so the rules axe-core runs were not "
                          "evaluated")

    def _run(self, cdp, backend: list) -> None:
        A = self.A
        try:
            source = A.axe_source()
        except A.AxeUnavailable as exc:
            self.block["reason"] = str(exc)
            self.notes.append(f"axe-core was not run: {exc}, so the rules it "
                              "runs were not evaluated")
            return
        step = "making its world"
        try:
            frame = cdp.send("Page.getFrameTree")["frameTree"]["frame"]["id"]
            self.world = cdp.send("Page.createIsolatedWorld", {
                "frameId": frame, "worldName": AXE_WORLD,
                "grantUniveralAccess": False})["executionContextId"]
            step = "loading it"
            for code in (source, A.RUNNER_JS):
                self._eval(cdp, code)
            pairs, _ = _resolve_pairs(cdp, backend, self.world)
            if pairs:
                step = "handing it the closed shadow roots"
                res = cdp.send("Runtime.callFunctionOn", {
                    "functionDeclaration": (f"function () {{ return {_AXE}."
                                            "register.apply(null, arguments); }"),
                    "executionContextId": self.world,
                    "arguments": [{"objectId": oid} for _, oid in pairs],
                    "returnByValue": True})
                got = ((res.get("result") or {}).get("value")
                       if isinstance(res, dict)
                       and not res.get("exceptionDetails") else None)
                for i in got if isinstance(got, list) else ():
                    if (isinstance(i, int) and not isinstance(i, bool)
                            and 0 <= i < len(pairs)):
                        self.registered.add(pairs[i][0])
            step = "running it"
            rules = A.rule_order()
            out = cdp.send("Runtime.evaluate", {
                "expression": (f"{_AXE}.run({json.dumps(rules)}, "
                               f"{json.dumps(A.run_parts(rules))}, "
                               f"{self.timeout_ms}, {A.MAX_ELEMENTS}, "
                               f"{A.MAX_PAGE_ELEMENTS})"),
                "contextId": self.world, "awaitPromise": True,
                "returnByValue": True})
        except Exception:                               # noqa: BLE001
            self._not_run(f"axe-core could not run in the page ({step})")
            return
        if not isinstance(out, dict) or out.get("exceptionDetails"):
            self._not_run("axe-core stopped with an error on this page")
            return
        answer, block, notes = A.read_answer(
            (out.get("result") or {}).get("value"), self.timeout_ms)
        self.block, self.answer = block, answer
        self.notes.extend(notes)
        if answer is None:
            self.notes.append(f"{block['reason']}, so the rules axe-core runs "
                              "were not evaluated")

    def extra(self, cdp, name: str, roots: int) -> dict | None:
        """The capture's `extra.axe`: where each element axe-core reported
        is now (RUNNER_JS `paths`, which from now watches the page's
        structure until the capture's first stamp under `name`), and how
        many of the closed shadow roots passed to the capture, first among
        them, axe-core was given (`roots`). An element no longer in the
        page has no place: its results are counted. None when there is no
        answer to record, or its places cannot be read (`failure`)."""
        if self.answer is None or self.failure:
            return None
        try:
            value = self._eval(cdp, f"{_AXE}.paths({json.dumps(name)})")
        except Exception:                               # noqa: BLE001
            value = None
        if not (isinstance(value, dict) and isinstance(value.get("places"),
                                                        list)):
            self.fail("where axe-core's results are in the page could not be "
                      "read")
            return None
        answer = self.answer
        marks, seen = [], set()
        for item in value["places"]:
            if not (isinstance(item, list) and len(item) == 2):
                continue
            k, steps = item
            if (isinstance(k, int) and not isinstance(k, bool)
                    and k in answer.results and k not in seen
                    and _place_steps(steps)):
                seen.add(k)
                marks.append({"p": steps, "k": k})
        for k in list(answer.results):
            if k not in seen:
                answer.lose(k)
        self.added = _page_int(value.get("added"), 0, 10 ** 8) or 0
        return {"roots": int(roots), "marks": marks}

    def check(self, cdp) -> None:
        """Right after the capture: which marks the page may have moved
        before the capture began (RUNNER_JS `changed`). Without that answer
        no mark can be trusted, and nothing is recorded."""
        if self.answer is None or self.failure:
            return
        try:
            value = self._eval(cdp, f"{_AXE}.changed()")
        except Exception:                               # noqa: BLE001
            value = None
        if not (isinstance(value, dict) and value.get("boundary") is True
                and isinstance(value.get("invalid"), list)):
            self.fail("what the page changed before the capture could not be "
                      "read, so axe-core's results could not be matched to it")
            return
        self.invalid = {k for k in value["invalid"]
                        if isinstance(k, int) and not isinstance(k, bool)}
        self.added += _page_int(value.get("added"), 0, 10 ** 8) or 0
        self.checked = True

    def place(self, html: str, provenance_attr: str, cap_axe) -> tuple[str, dict]:
        """`html`, the serialized capture, with axe-core's records written
        where the capture left their placeholders: each mark the page did
        not move first becomes its element's results, and the root
        element's placeholder the run's record, which counts every other
        result under its rule (axe.AxeAnswer.run_record). Returns the html
        and the capture record's `axe` block; its notes go to self.notes.
        When the results cannot be matched to the capture, every
        placeholder goes and nothing is recorded."""
        import html as H
        mark_name = axe_attr(provenance_attr)
        run_name = axe_run_attr(provenance_attr)
        mark_re = re.compile(r" " + re.escape(mark_name) + r'="(\d{1,7})"')
        run_re = re.compile(r" " + re.escape(run_name) + r'="pending"')
        answer = self.answer
        if answer is not None and not self.failure:
            if not isinstance(cap_axe, dict):
                self.fail("the capture did not record axe-core's results")
            elif not self.checked:
                self.fail("axe-core's results could not be matched to the "
                          "capture")
            elif len(run_re.findall(html)) != 1:
                self.fail("the capture did not record axe-core's run")
        if answer is None or self.failure:
            block = {k: v for k, v in self.block.items()
                     if k not in ("rules", "not_run")}
            if answer is not None:
                block["ran"] = False
                block["reason"] = self.failure
                self.notes.append(f"{self.failure}; the rules axe-core runs "
                                  "were not evaluated")
            return run_re.sub("", mark_re.sub("", html)), block
        placed = {k for k in cap_axe.get("placed") or ()
                  if isinstance(k, int) and not isinstance(k, bool)}
        good = placed - self.invalid
        written: set = set()

        def write(m):
            k = int(m.group(1))
            if k in good and k in answer.results and k not in written:
                written.add(k)
                return f' {mark_name}="{H.escape(answer.mark(k))}"'
            return ""
        html = mark_re.sub(write, html)
        for k in list(answer.results):
            if k not in written:
                answer.lose(k)
        unchecked = _page_int(cap_axe.get("unchecked"), 0, 10 ** 8) or 0
        record = answer.run_record(unchecked)
        html = run_re.sub(lambda m: f' {run_name}="{H.escape(record)}"', html,
                          count=1)
        lost = answer.not_located()
        block = dict(self.block)
        block.update({"elements": len(written), "not_located": lost,
                      "unchecked": unchecked, "added": self.added})
        if lost:
            self.notes.append(
                f"{lost} of axe-core's results could not be attached to an "
                "element in the capture: the page removed or moved their "
                "elements first, or there were more than "
                f"{self.A.MAX_ELEMENTS:,} elements to record; each rule "
                "reports its own as findings about the page")
        if unchecked:
            self.notes.append(
                f"axe-core did not check {unchecked} element(s) the capture "
                "holds, inside closed shadow roots it was not given (attached "
                "after it ran, or past what the harness looks for); on this "
                "page its rules that found no failure are not evaluated")
        if self.added:
            self.notes.append(
                f"{self.added} element(s) were added to the page after "
                "axe-core started, before the capture: they are in the "
                "snapshot, but axe-core did not check them")
        return html, block


#: "page" for an HTML document, or an XML one whose root is XHTML's <html>;
#: "xml-error" for an XML document that is not well-formed, which Chromium
#: shows as its error message over the part it read (a file or server run
#: reports such a page as not evaluated: xhtml.NotWellFormed); otherwise the
#: document's content type.
_PAGE_KIND_JS = """() => {
  const t = document.contentType, r = document.documentElement;
  const X = "http://www.w3.org/1999/xhtml";
  if (t === "text/html") return "page";
  if (/xml/.test(t) && document.getElementsByTagNameNS(X, "parsererror").length)
    return "xml-error";
  if (r && r.namespaceURI === X && r.localName === "html" && /xml/.test(t))
    return "xml-page";
  return t;
}"""

def _served_type(value) -> str:
    """The media type a Content-Type header value names, or ""."""
    try:
        return parse_content_type([value])[0] if value else ""
    except Exception:                                   # noqa: BLE001
        return ""


#: How a FetchError says the document that was not a page is one the page
#: sent the browser on to (render_failure words it). Not "after it
#: loaded": a script in the head can send it on before the load (R4G-7).
WENT_ELSEWHERE = "it sent the browser on to another document: "
#: …one no server sent: the browser's own error page, or a blank page.
NO_SERVER = "no server sent it"
#: How render_failure's words begin for such a document.
WENT_ON = "it sent the browser on to another document, which "
#: What fetch_rendered says, after WENT_ELSEWHERE, of a page whose
#: documents went on to others MAX_READS times while it was read, or
#: before it loaded (R5C-8).
KEPT_GOING = "and on again: it stays on no one document"
#: The most documents a capture reads in turn, each one a page went on
#: to while the one before was read (a chain of redirects that settles).
MAX_READS = 5
#: ... of a document it went to that did not finish loading in time.
NOT_LOADED = "one that did not finish loading within the load timeout"
#: ... of one whose navigation had not committed when the harness stopped
#: waiting for it: the load timeout, or the render deadline (R5E-6).
NOT_ARRIVED = ("one that had not arrived when the harness stopped waiting "
               "for it")
#: ... of a document a script made in place of the page, with no commit.
MADE_BY_SCRIPT = "one a script on the page made in its place"
#: ... of one a service worker answered in the server's place.
WORKER = "one a service worker answered in the server's place"
#: How such a refusal ends: where the page went, for the console only
#: (R5A-18). render_failure reads only the kind before it, so no record
#: holds the page's choice of URL.
WENT_TO = " — at "


def _at(where: str, keep=()) -> str:
    """WENT_TO and the document's URL, redacted as a recorded URL is; for a
    document at no http(s) URL (blob:, about:), its scheme alone. Cut only
    far out: the console's line is cut after the run's own secrets are
    scrubbed from it (cli._say_detail), so a token in the path is never
    left half shown (R5H-3)."""
    if not where:
        return ""
    if where.lower().startswith(("http:", "https:")):
        shown = redact_url(where, keep)[0]
    else:
        shown = where.split(":", 1)[0][:20] + ":…"
    return WENT_TO + "".join(shown.split())[:WENT_TO_MAX]


#: The longest went-to URL a FetchError carries (_at).
WENT_TO_MAX = 4096


def _check_page_kind(kind, served: str) -> None:
    """FetchError unless the document the browser shows is a web page it
    can capture (_PAGE_KIND_JS), served as HTML: a capture is read back as
    HTML (XML_PAGE_REASON)."""
    if kind == "xml-error":
        raise FetchError("not a web page: it is not well-formed XML, and the "
                         "browser shows an XML error instead")
    if is_xml_type(served) and kind in ("page", "xml-page"):
        raise FetchError("an XML document, which the harness reads from the "
                         "server: it reads a capture as HTML")
    if kind not in ("page", "xml-page"):
        raise FetchError(f"not a web page: the browser shows it as "
                         f"{str(kind)[:80]}")


def _axe_not_recorded(reason: str, notes: list, block: dict | None = None
                      ) -> dict:
    """The capture record's `axe` block when no record of axe-core's could
    be written: its rules are not evaluated on the page."""
    from .axe import AXE_SHA256, AXE_VERSION
    out = {"engine": "axe-core", "version": AXE_VERSION,
           "sha256": AXE_SHA256, "ran": False}
    if isinstance(block, dict) and not block.get("ran") and block.get("reason"):
        out["reason"] = block["reason"]           # axe-core did not run at all
        return out
    out["reason"] = reason
    notes.append(f"{reason}; the rules axe-core runs were not evaluated")
    return out


#: Why a page served as XML is read from the server's bytes in a rendered
#: run (PR2-3): a capture is read back as HTML (html.parser), which folds
#: the case XML keeps (`<A href>` is no link there) and drops xml:lang.
XML_PAGE_REASON = ("an XML document (served as XML): read as the server sent "
                   "it, with an XML parser, since the harness reads a "
                   "rendered capture as HTML")


def fetch_rendered(url: str, timeout_ms: int = DEFAULT_TIMEOUT_MS,
                   viewport: dict | None = None,
                   settle_ms: int = DEFAULT_SETTLE_MS,
                   settle_cap_ms: int = DEFAULT_SETTLE_CAP_MS,
                   third_party_origins=None,
                   scroll_steps: int = DEFAULT_SCROLL_STEPS,
                   scroll_pause_ms: int = DEFAULT_SCROLL_PAUSE_MS,
                   http_credentials: tuple[str, str] | None = None,
                   record_query=(), axe: bool = True,
                   axe_timeout_ms: int | None = None,
                   narrow: bool = True,
                   require_sandbox: bool = False,
                   on_stuck=None, deadline_at: float | None = None,
                   wait_for: str | None = None
                   ) -> FetchResult:
    """Capture the hydrated DOM, instrumented for provenance. With
    `wait_for` (a CSS selector, --wait-for), the capture first waits, up to
    `timeout_ms`, for an element it matches, and refuses the page when none
    appears (WAIT_FOR_MISSING); the settle step then waits for the DOM and
    the page's data requests (_settle). With `axe`,
    axe-core runs first, in an isolated world (_AxeSession), and the
    capture records what it found. With `narrow`, after the capture the
    page is narrowed to NARROW_VIEWPORT, where what it hides, what it
    changes and how it reflows are recorded (_record_narrow) and written
    into the capture (_place_narrow); the page is not widened again, since
    nothing more is read from it.

    With `on_stuck`, a navigation the page starts that has not committed
    within the load timeout, or near `deadline_at` (time.monotonic()), is
    handed to it as a FetchError from another thread (_watch_pending): the
    capture waits with it, and `on_stuck` must end it (_render_child)."""
    check_scheme(url)
    credentials = _check_credentials(http_credentials)
    from playwright.sync_api import sync_playwright

    viewport = viewport or dict(DEFAULT_VIEWPORT)
    vendor_domains, vendor_origins = _vendor_entries(third_party_origins)
    capture_prop = "__bb_capture_" + secrets.token_hex(8)
    narrow_token = secrets.token_hex(16)
    capture_token = secrets.token_hex(16)
    script = instrumentation_script(capture_prop, vendor_domains, vendor_origins,
                                    narrow_token=narrow_token,
                                    capture_token=capture_token)
    chain: list = []
    # No service worker registered through navigator.serviceWorker; and
    # _Documents bypasses any a page registers another way, for every
    # request (R5C-3, R5E-5).
    context_options: dict = {"viewport": viewport, "service_workers": "block"}
    if credentials:
        # Offered only to the page's own origin and only on a 401 challenge:
        # vendor scripts, CDNs and cross-origin redirects never see them.
        context_options["http_credentials"] = {
            "username": credentials[0], "password": credentials[1],
            "origin": url_origin(url)}
    done = threading.Event()
    with sync_playwright() as p:
        browser, unsandboxed = _launch_chromium(p, require_sandbox)
        try:
            ctx = browser.new_context(**context_options)
            page = ctx.new_page()
            page.add_init_script(script)
            data = _DataRequests(page, vendor_domains, vendor_origins)
            # Each document the tab commits, and what its server sent; the
            # history API commits none (PR3-1), and neither does a
            # navigation to a download (R4G-3).
            docs = _Documents(ctx, page)
            if on_stuck is not None:
                threading.Thread(
                    target=_watch_pending, daemon=True,
                    name="bellbriar-pending-watch",
                    args=(docs, done, timeout_ms / 1000, deadline_at,
                          record_query, on_stuck)).start()
            resp = _goto(ctx, page, docs, url, timeout_ms, record_query)
            first_status, first_type = docs.first()
            status = resp.status if resp is not None else first_status
            # A browser shows text/plain, JSON or a feed as text, in a
            # document of its own making: that is no page to evaluate.
            # Whether the page is an XML document is the server's word (its
            # Content-Type), not the page's: a script can redefine
            # document.contentType (PR3-6).
            try:
                served = parse_content_type(
                    resp.header_values("content-type") if resp is not None
                    else first_type)[0] if (resp is not None
                                            or first_type) else ""
            except Exception:                           # noqa: BLE001
                served = ""

            def check_shown(hops: int = 0) -> None:
                """FetchError unless the document the tab shows now is a
                page, judged by its own server's word: the one it was sent
                to, or the one a script or a refresh sent it on to (R4G-2),
                which the error then says it went to (R4E-4). One it went
                on to, from a page that answered 200, must have come from
                a server with 200 too, whatever its type: an error page,
                the browser's own error page or a blank page is not the
                page (R4I-1, R4I-3)."""
                for attempt in range(3):
                    before = docs.changes()
                    try:
                        kind = page.evaluate(_PAGE_KIND_JS)
                        break
                    except Exception:                   # noqa: BLE001
                        # A document committed while it was read (a refresh
                        # due now): read the one it went to, once loaded.
                        if attempt == 2:
                            raise
                        _await_document(ctx, page, docs, before,
                                        timeout_ms)
                        if docs.changes() == before:
                            raise
                if docs.script_made:
                    # A script replaced the page with a document of its
                    # own, with no commit (a javascript: URL): no server
                    # sent it, whatever status the page had (R5C-2). Unless
                    # it goes on at once to one a server sent: a chain
                    # that settles is judged by where it settles (R5E-12).
                    before = docs.changes()
                    if (hops < MAX_READS and _await_document(
                            ctx, page, docs, before, timeout_ms)
                            and docs.changes() > before
                            and not docs.script_made):
                        return check_shown(hops + 1)
                    raise FetchError(f"{WENT_ELSEWHERE}{MADE_BY_SCRIPT}")
                moved = docs.moved()
                if moved and status == 200:
                    shown_status = docs.shown()[0]
                    where = docs.shown_url()
                    # A blob: or other non-http(s) document came from no
                    # server, whatever status Chromium gives it (R5A-7).
                    if docs.committed[-1] in docs.worker:
                        raise FetchError(f"{WENT_ELSEWHERE}{WORKER}"
                                         + _at(where, record_query))
                    if shown_status is None or not where.lower().startswith(
                            ("http:", "https:")):
                        raise FetchError(f"{WENT_ELSEWHERE}{NO_SERVER}"
                                         + _at(where, record_query))
                    if shown_status != 200:
                        raise FetchError(f"{WENT_ELSEWHERE}HTTP "
                                         f"{shown_status}"
                                         + _at(where, record_query))
                try:
                    _check_page_kind(kind, docs.shown()[1] if moved
                                     else served)
                except FetchError as exc:
                    if moved:
                        raise FetchError(
                            f"{WENT_ELSEWHERE}{exc}"
                            + _at(docs.shown_url(), record_query)) from None
                    raise
            check_shown()
            # The page's own redirect chain, read back from the response the
            # navigation ended on: an iframe's redirects are not the page's.
            try:
                req = resp.request if resp is not None else None
                while req is not None and len(chain) < 100:
                    chain.append(req.url)
                    req = req.redirected_from
            except Exception:                           # noqa: BLE001
                chain = []
            chain.reverse()
            peer, peer_url = None, None
            try:
                addr = resp.server_addr() if resp is not None else None
                peer = addr.get("ipAddress") if isinstance(addr, dict) else None
                peer_url = resp.url
            except Exception:                           # noqa: BLE001
                peer = None
            # In a world of the harness's own (L21). A page that goes to
            # another document while it is read (a script after the load,
            # a refresh due now) is judged by the document it went to, as
            # one that goes there before the load is: an error page or a
            # document no server sent is refused, never read in its place
            # (R5A-1). A page it went to that is one is read once more.
            # What was read is the document the tab showed when the reading
            # began, if it still shows it when the reading ends: its HTML,
            # its URL, and how many documents had committed by then.
            if wait_for:
                _wait_for(page, wait_for, timeout_ms)
            captured_at = 0
            for attempt in range(1, MAX_READS + 1):
                read_from = docs.changes()
                try:
                    scrolled = (_in_own_world(ctx, page, _SCROLL_JS,
                                              [scroll_pause_ms, scroll_steps])
                                if scroll_steps > 0 else {"steps": 0})
                    wait = _settle(ctx, page, settle_ms, settle_cap_ms,
                                   data)
                    cap, scan_note, provenance_attr, session = _call_capture(
                        ctx, page, capture_prop, capture_token,
                        axe=((lambda cdp, closed: _AxeSession(
                            cdp, closed, axe_timeout_ms))
                             if axe else None),
                        index=narrow)
                    if cap and isinstance(cap.get("html"), str) and \
                            cap["html"]:
                        html, instrumented = cap["html"], True
                    else:
                        html, instrumented = page.content(), False
                    final = page.url
                    failed = None
                except Exception as exc:                # noqa: BLE001
                    failed = exc
                if docs.changes() == read_from:
                    if failed is not None:
                        raise failed
                    captured_at = len(docs.committed)
                    break
                if not _await_document(ctx, page, docs, read_from,
                                       timeout_ms):
                    # What it went to never finished loading: no capture
                    # of it would be of a page as it is shown (R5C-7).
                    raise FetchError(f"{WENT_ELSEWHERE}{NOT_LOADED}"
                                     + _at(docs.shown_url(), record_query))
                check_shown()
                if attempt == MAX_READS:
                    raise FetchError(f"{WENT_ELSEWHERE}{KEPT_GOING}")
            version = browser.version
            # Moved by the time of the capture: one that moves after it is
            # judged below, and leaves the capture as it was.
            navigated = (captured_at > 1 and docs.committed[captured_at - 1]
                         != docs.committed[0])
            if navigated:
                # The page sent the tab on to another document (a script,
                # a refresh): what was captured is that document, so it must
                # be a page too (PR4-1), one a server sent with 200
                # (R4G-1, R4I-1).
                check_shown()
                if status != 200 and resp is not None:
                    # The page it was sent to answered with an error, and
                    # that is what a run refuses: named by its own URL, and
                    # not said to be the document it went on to (R4I-5).
                    final, navigated = resp.url, False
            # The narrow viewport's record, taken after the capture, so
            # nothing a page does on being narrowed (a sidebar that collapses
            # and stays so) changes what was captured at its own viewport.
            narrow_info, narrow_settled = None, False
            went_later = False
            if narrow and instrumented:
                # Counted from the capture: a document that committed
                # since, even before this step began, is not the one
                # captured, and its record would not be that page's.
                before = captured_at
                try:
                    page.set_viewport_size(dict(NARROW_VIEWPORT))
                    settled_n = _in_own_world(ctx, page, _SETTLE_JS, [
                        settle_ms, NARROW_SETTLE_CAP_MS])
                    narrow_settled = bool(isinstance(settled_n, dict)
                                          and settled_n.get("settled"))
                    narrow_info = _record_narrow(ctx, page, capture_prop,
                                                 narrow_token)
                except Exception:                       # noqa: BLE001
                    narrow_info = None
                if docs.changes() > before:
                    # It went to another document after it was captured:
                    # judged as one it went to sooner is (R5A-1). One that
                    # is a page leaves the capture as it was, with a note.
                    narrow_info = None
                    _await_document(ctx, page, docs, before, timeout_ms)
                    check_shown()
                    went_later = True
            if docs.changes() > captured_at and not went_later:
                # The same, for a run with no narrow step, or a capture
                # that failed: whatever the tab went to before it closed.
                _await_document(ctx, page, docs, captured_at, timeout_ms)
                check_shown()
                went_later = True
        finally:
            done.set()
            browser.close()

    # The addresses the browser connected to for the document it read and
    # the redirects on its way there, as they were then (S5 re-review). The
    # document read is the one committed when the capture was taken, or
    # the first, which the run refuses below, when that one's server
    # answered with an error.
    read_loader = None
    if captured_at:
        read_loader = (docs.committed[captured_at - 1] if navigated
                       else docs.committed[0])
    connected = list(docs.peers.get(read_loader, [])) if read_loader else []
    own_url, own_peer = docs.own_peer.get(read_loader) or (peer_url, peer)
    # Everything below was measured inside the page, whose scripts can
    # tamper with the clocks and counters it read. Only in-range whole
    # numbers are kept; a bundle must never inherit NaN or 1e300 from a page.
    wait = wait if isinstance(wait, dict) else {}
    scrolled = scrolled if isinstance(scrolled, dict) else {}
    notes = []
    if not wait.get("settled"):
        notes.append(
            f"DOM was still mutating when the {settle_cap_ms} ms cap was "
            "reached; the capture is a point in time on a page that had not "
            "settled.")
    if wait.get("in_flight"):
        notes.append(
            f"{_page_int(wait.get('in_flight'), 0, 10 ** 9)} of the page's "
            "data requests (fetch or XHR) had not answered when it was "
            "captured.")
    if not instrumented:
        # The capture's own note is the harness's words (fixed text and
        # counts), never the page's.
        why = (f"the capture failed ({str(cap['note'])[:300]})"
               if isinstance(cap, dict) and cap.get("note")
               else "the capture failed" if isinstance(cap, dict)
               else "the capture did not run")
        notes.append(f"{why}; the page was read as the browser serialized "
                     "it. Findings cannot be attributed to first- or "
                     "third-party code, and all of them are scored. What the "
                     "page's stylesheets hide was not recorded, and neither "
                     "was media muted state set by script (React sets it so), "
                     "so a muted video may be reported as playing sound.")
    elif cap.get("note"):
        notes.append(str(cap["note"])[:500])
    if instrumented and scan_note:
        notes.append(scan_note)
    if navigated:
        notes.append("the page sent the browser on to another document (by a "
                     "script or a refresh); what was captured is the document "
                     "it went to, at the final URL")
    if went_later:
        notes.append("after the capture, the page sent the browser on to "
                     "another document, a page a server sent with HTTP 200; "
                     "what was captured is the document before it")
    axe_block = None
    if axe:
        if session is None:
            axe_block = _axe_not_recorded(
                "the capture failed, so axe-core could not be run for it",
                notes)
        elif instrumented:
            html, axe_block = session.place(html, provenance_attr,
                                            cap.get("axe"))
            notes.extend(session.notes)
        else:
            notes.extend(session.notes)
            axe_block = _axe_not_recorded(
                "the capture failed, so axe-core's results could not be "
                "recorded", notes, session.block)
    narrow_block = None
    if instrumented:
        root = (cap.get("index") or {}).get("root") if isinstance(
            cap.get("index"), dict) else None
        html, hiding, reflow = _place_narrow(
            html, provenance_attr, narrow_info if narrow else None,
            root if isinstance(root, int) and not isinstance(root, bool)
            else None)
        if narrow:
            narrow_block = _narrow_outcome(narrow_info, hiding, reflow,
                                           narrow_settled, notes)
    if unsandboxed:
        notes.append(f"Chromium ran without its sandbox ({unsandboxed}): code "
                     "on the page that exploited the browser would have run "
                     "with this user's permissions.")
    # Only a capture serializes shadow roots. Any other <template
    # shadowrootmode> in the live DOM is inert (set by innerHTML, which
    # never attaches one) and stays a template.
    html = (materialize_shadow_roots(html, provenance_attr) if instrumented
            else html)
    if instrumented:
        html = place_capture_record(html, provenance_attr, version)
    # As server mode records it: the requested URL, then every hop, ending
    # at the final URL (a script or refresh may navigate after the load).
    # A request carries no fragment, so the fragment alone is no hop: it
    # used to record a redirect of every route URL to itself (R1B-12).
    hops = chain[1:]
    if final.split("#", 1)[0] != (chain[-1] if chain else url).split("#", 1)[0]:
        hops.append(final)
    result = FetchResult(
        url=url, final_url=final, mode="rendered", html=html, status=status,
        reader="dom", redirects=[url, *hops] if hops else [],
        navigated=navigated,
        fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        browser={"name": "chromium", "version": version,
                 "sandbox": not unsandboxed},
        viewport=viewport,
        wait={"strategy": "load+scroll+dom-and-data-settle",
              "quiet_ms": settle_ms,
              "cap_ms": settle_cap_ms,
              "waited_ms": _page_int(wait.get("waited"), 0,
                                     10 * settle_cap_ms),
              "settled": bool(wait.get("settled")),
              "data_requests": _page_int(wait.get("data_requests", 0), 0,
                                         10 ** 9),
              "data_requests_open": _page_int(wait.get("in_flight", 0), 0,
                                              10 ** 9),
              "wait_for": wait_for or None,
              "scroll_steps": _page_int(scrolled.get("steps", 0), 0,
                                        scroll_steps)},
        instrumented=instrumented,
        provenance_attr=provenance_attr if instrumented else None,
        attribution=({"policy": "vendor-list",
                      "vendor_list_version": VENDOR_LIST_VERSION,
                      "extra_third_party": sorted(
                          set(vendor_domains) - set(KNOWN_VENDOR_DOMAINS))
                      + vendor_origins}
                     if instrumented else None),
        shadow_roots=(_page_int(cap.get("shadowRoots", 0), 0, 10 ** 7)
                      if instrumented else 0),
        axe=axe_block,
        narrow=narrow_block,
        notes=notes,
        record_query=tuple(sorted(names(record_query))),
        redacted=["http-credentials"] if credentials else [],
        document_peers=[(u, ip) for u, ip in connected if _direct(u)])
    # The address the page came from counts only when the browser connected
    # to the recorded host itself (no proxy, no later navigation to another
    # host); the class is the recorded host's (R1B-8). It is the address
    # of the document read (S5 re-review).
    result.address_class, result.address_basis = address_record(
        result.final_url,
        own_peer if own_url and result.host
        and host_of(own_url.split("#", 1)[0]) == result.host
        and _direct(final) else None)
    return result


_PW_METHOD = re.compile(
    r"^\s*((?:Page|Frame|Browser|BrowserType|BrowserContext|CDPSession|"
    r"ElementHandle|JSHandle|Response|Request|Locator|Worker)"
    r"\.[a-z][A-Za-z_]{1,40}):")
_CLOSED = re.compile(r"(Target page, context or browser has been closed|"
                     r"Target crashed|Page crashed|Browser closed|"
                     r"Browser has been closed)")
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]+")


#: Playwright methods whose failures come from loading the page — the
#: network stack and the harness's own timeouts — rather than from a script
#: on the page.
_NAVIGATION_METHODS = (".goto", ".reload", ".go_back", ".go_forward",
                       ".wait_for_load_state", ".wait_for_url")


#: The longest a rendered capture may take, start to finish, before the
#: browser is stopped (N18): the page load timeout, the settle cap and the
#: scrolling, with room for starting the browser and taking the capture.
DEFAULT_RENDER_DEADLINE_S = 120


class RenderDeadline(Exception):
    """The rendered capture did not finish in time and was stopped."""

    def __init__(self, seconds: float):
        super().__init__(f"the rendered capture did not finish within "
                         f"{seconds:g} s")
        self.seconds = seconds


#: The kind of the errors the capture's supervisor raises itself (the
#: process died, or answered nothing it can read): their words are the
#: harness's, so the record keeps them (R4E-3).
CAPTURE_PROCESS = "CaptureProcess"


class _ChildError(Exception):
    """An error the capture process reported, with its own text, so that
    render_failure reads it as it would read the original."""

    def __init__(self, kind: str, text: str):
        super().__init__(text)
        self.kind = kind


class _ResultUnpickler:
    """Reads the capture process's answer, allowing nothing but a
    FetchResult and plain values: a page the browser rendered must not be
    able to make the harness load a class of its choosing."""

    _ALLOWED = {("builtins", n) for n in ("dict", "list", "tuple", "set",
                                          "frozenset", "str", "int", "float",
                                          "bool", "bytes")}

    @classmethod
    def loads(cls, data: bytes):
        import io
        import pickle

        class Restricted(pickle.Unpickler):
            def find_class(self, module, name):
                if (module, name) == (__name__, "FetchResult"):
                    return FetchResult
                if (module, name) in cls._ALLOWED:
                    import builtins
                    return getattr(builtins, name)
                raise pickle.UnpicklingError(f"refused {module}.{name}")
        return Restricted(io.BytesIO(data)).load()


def _descendants(pid: int) -> list[int]:
    """Every process under `pid`, parents before children: the browser's
    driver, Chromium (which Playwright starts in a process group of its
    own) and Chromium's renderers. From /proc where there is one, so no
    helper process is listed; otherwise from `ps`, leaving out the `ps` run
    for it (which has exited by then: its pid is no process's to signal,
    OR2-10)."""
    import os
    import subprocess
    children: dict[int, list[int]] = {}
    pairs: list[tuple[int, int]] = []
    if os.path.isdir("/proc"):
        for entry in os.listdir("/proc"):
            if not entry.isdigit():
                continue
            try:
                with open(f"/proc/{entry}/stat") as f:
                    stat = f.read()
                pairs.append((int(entry),
                              int(stat.rsplit(")", 1)[1].split()[1])))
            except (OSError, ValueError, IndexError):
                continue
    else:                                             # pragma: no cover
        try:
            ps = subprocess.Popen(["ps", "-A", "-o", "pid=", "-o", "ppid="],
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, text=True)
            out, _ = ps.communicate(timeout=10)
            pairs = [(c, pp) for c, pp in (tuple(map(int, line.split()))
                                           for line in out.splitlines()
                                           if len(line.split()) == 2)
                     if c != ps.pid]
        except (OSError, ValueError, subprocess.SubprocessError):
            pairs = []
    for child, parent in pairs:
        children.setdefault(parent, []).append(child)
    out_pids, todo = [], [pid]
    while todo:
        for c in children.get(todo.pop(0), ()):
            if c not in out_pids:
                out_pids.append(c)
                todo.append(c)
    return out_pids


def _kill_tree(proc) -> None:
    """Stop the capture process and everything under it."""
    import os
    import signal
    import subprocess
    if os.name == "nt":                               # pragma: no cover
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                       capture_output=True, timeout=30)
    else:
        for pid in [*_descendants(proc.pid), proc.pid]:
            try:
                os.kill(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            pass
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:                 # pragma: no cover
        pass


#: Environment variables the render child, and the browser under it, never
#: inherit: secrets this process reads, which nothing a page runs should
#: share a process tree with (R1A-9). The CLI adds the one --sign-key-env
#: names. HTTP credentials reach the child on its stdin, not through these.
WITHHELD_ENV = {"BELLBRIAR_SIGN_KEY", "BELLBRIAR_HTTP_PASSWORD"}

#: Nor any variable whose name reads as a secret's (S5-2): a word of its
#: name, split at "_", is one of these, or it is one of the runner's own
#: (ACTIONS_*, which mint tokens). A renderer that a page takes over runs
#: as this user, so a CI job's tokens, cloud keys and the SSH agent's
#: socket stay out of its reach. What the browser needs (PATH, HOME, the
#: locale, the proxy settings, the CA bundles, PLAYWRIGHT_*) has no such
#: word. A secret named otherwise, whose value holds no URL with a
#: password, is not recognized: pass the harness no more environment than
#: it needs.
SECRET_NAME_WORDS = frozenset((
    "TOKEN", "TOKENS", "SECRET", "SECRETS", "PASSWORD", "PASSWORDS",
    "PASSWD", "PASS", "PASSPHRASE", "CREDENTIAL", "CREDENTIALS", "CREDS",
    "KEY", "KEYS", "APIKEY", "PAT", "AUTH", "COOKIE", "COOKIES", "DSN",
    "PRIVATE"))
SECRET_NAME_PREFIXES = ("ACTIONS_",)
#: Names that hold a password inside a URL by convention.
SECRET_NAMES = frozenset(("DATABASE_URL", "REDIS_URL", "MONGODB_URI",
                          "MONGO_URL", "AMQP_URL", "CONNECTION_STRING"))
#: A word of a name that ends so is a secret's too: PGPASSWORD,
#: SYSTEM_ACCESSTOKEN (Azure Pipelines), NGROK_AUTHTOKEN (S5-2).
SECRET_WORD_ENDINGS = ("TOKEN", "TOKENS", "PASSWORD", "PASSWORDS", "PASSWD",
                       "SECRET", "SECRETS", "PASSPHRASE", "APIKEY",
                       "CREDENTIALS")
#: A name ending in URL, URI or DSN with one of these words before it is a
#: database's, whose URL carries its password (POSTGRES_URL, MONGO_URI,
#: JDBC_DATABASE_URL).
DATABASE_WORDS = frozenset((
    "DATABASE", "DB", "POSTGRES", "POSTGRESQL", "PG", "MYSQL", "MARIADB",
    "MONGO", "MONGODB", "REDIS", "AMQP", "RABBITMQ", "JDBC", "SQL", "MSSQL",
    "ELASTICSEARCH", "CASSANDRA", "CLICKHOUSE", "NEO4J", "SUPABASE",
    "PRISMA"))
#: A URL with a user name and a password in it, which a value can hold
#: whatever its variable is named (pip's index, a deploy hook).
_CREDENTIALED_URL = re.compile(
    r"[A-Za-z][A-Za-z0-9+.-]*://[^\s/@:]*:[^\s/@]*@")
#: The proxy settings, which the browser needs as they are, credentials
#: and all, to reach any page.
_PROXY_NAMES = frozenset(("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
                          "NO_PROXY", "FTP_PROXY"))


def secret_like(name: str, value: str | None = None) -> bool:
    """Does the environment variable `name` read as a secret's
    (SECRET_NAME_WORDS, SECRET_WORD_ENDINGS, SECRET_NAME_PREFIXES,
    SECRET_NAMES, a connection string's, a database's URL), or its `value`
    hold a URL with a password, the proxy settings' aside? `PWD` and
    `OLDPWD`, the current folder, are no secret's; `MYSQL_PWD` is."""
    upper = name.upper()
    if upper.startswith(SECRET_NAME_PREFIXES) or upper in SECRET_NAMES:
        return True
    words = [w for w in upper.split("_") if w]
    if any(w in SECRET_NAME_WORDS or w.endswith(SECRET_WORD_ENDINGS)
           or w.startswith("JWT") for w in words):
        return True
    if "PWD" in words and len(words) > 1:
        return True
    if upper.endswith(("CONNECTION_STRING", "CONNECTIONSTRING")):
        return True
    if words and words[-1] in ("URL", "URI", "DSN") and \
            any(w in DATABASE_WORDS for w in words[:-1]):
        return True
    return bool(value) and upper not in _PROXY_NAMES and \
        _CREDENTIALED_URL.search(value) is not None


def withheld(name: str, value: str | None = None) -> bool:
    """Is the environment variable `name` one a child process must not
    see (WITHHELD_ENV, or a name, or a `value`, that reads as a secret's:
    secret_like)? On Windows names are compared ignoring case, as the
    system compares them: there os.environ holds them in upper case, so
    `--sign-key-env my_key` read MY_KEY and passed it on (R5B-8)."""
    import os
    if secret_like(name, value):
        return True
    if os.name == "nt":
        return name.upper() in {w.upper() for w in WITHHELD_ENV}
    return name in WITHHELD_ENV


def _fetch_rendered_isolated(url: str, deadline_s: float, **kw) -> FetchResult:
    """fetch_rendered in a child process (_render_child), stopped with the
    browser under it when `deadline_s` passes (RenderDeadline). A script
    that never yields can block every call the capture makes, and in this
    process that hung the run with no output (N18). So can a navigation
    that never commits; the child ends a capture held by one itself, and
    says so (_watch_pending, R5E-6).

    The request goes on the child's stdin, which stays open until the
    answer is in: if this process dies first, however it dies, the child
    sees stdin end and stops the browser itself (OR-9).

    The capture has a temporary folder of its own (CAPTURE_SCRATCH_PREFIX,
    the child's TMPDIR): the browser's profile for the page, its cache,
    cookies and storage, goes there, and the folder is removed once the
    capture process has ended, by this process or, if this one ended
    first, by the capture process as it stops (S5 re-review: a capture
    stopped at its deadline left its profile behind)."""
    import tempfile
    scratch = tempfile.mkdtemp(prefix=CAPTURE_SCRATCH_PREFIX)
    answered = False
    try:
        result = _isolated_capture(url, deadline_s, scratch, **kw)
        answered = True
        return result
    finally:
        # A capture that answered closed its browser itself; one that was
        # stopped may leave a process that writes a moment longer.
        remove_capture_scratch(scratch, settle_s=0.0 if answered else 0.5)


#: The start of a capture's temporary folder's name (_fetch_rendered_isolated).
CAPTURE_SCRATCH_PREFIX = "bellbriar-capture-"


#: How long remove_capture_scratch keeps trying: a browser process that
#: started as the capture was stopped (one the stop could not yet see)
#: writes into the folder until it sees the browser gone, and ends.
SCRATCH_PATIENCE_S = 10.0


def remove_capture_scratch(path, patience_s: float | None = None,
                           settle_s: float = 0.0) -> bool:
    """Remove a capture's temporary folder, and nothing else: a path whose
    name does not start with CAPTURE_SCRATCH_PREFIX, or that is a link, is
    left as it is. What a browser process still writes into it is removed
    in turn, for up to `patience_s` (SCRATCH_PATIENCE_S); with `settle_s`,
    for a capture that was stopped rather than ended, the folder must stay
    gone that long, as such a process can make it again. Whether it is
    gone."""
    import os
    import shutil
    import time
    if not isinstance(path, str) or not os.path.basename(
            path).startswith(CAPTURE_SCRATCH_PREFIX) or os.path.islink(path):
        return False
    until = time.monotonic() + (SCRATCH_PATIENCE_S if patience_s is None
                                else patience_s)
    while True:
        shutil.rmtree(path, ignore_errors=True)
        if not os.path.lexists(path):
            if settle_s <= 0:
                return True
            time.sleep(settle_s)
            if not os.path.lexists(path):
                return True
        if time.monotonic() >= until:
            return False
        time.sleep(0.25)


def _isolated_capture(url: str, deadline_s: float, scratch: str,
                      **kw) -> FetchResult:
    import os
    import pickle
    import subprocess
    import threading
    from pathlib import Path
    package_root = str(Path(__file__).resolve().parents[1])
    env = {k: v for k, v in os.environ.items() if not withheld(k, v)}
    env["PYTHONPATH"] = os.pathsep.join(
        [package_root] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
    # Where the capture, its browser driver and the browser make their
    # temporary files (Python, Node and Chromium read these).
    for name in ("TMPDIR", "TMP", "TEMP"):
        env[name] = scratch
    popen = {"start_new_session": True} if os.name != "nt" else {
        "creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)}
    # Started from the package's own directory, so nothing in the user's
    # working directory can be imported by the child (-m puts the working
    # directory on its path).
    proc = subprocess.Popen(
        [sys.executable, "-m", "bellbriar_harness._render_child"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, cwd=package_root, env=env, **popen)
    request = pickle.dumps({"url": url, "kw": kw, "deadline_s": deadline_s,
                            "scratch": scratch}, protocol=4)
    box: dict = {}

    def read_answer():
        try:
            box["out"] = proc.stdout.read()
        except Exception as exc:                    # noqa: BLE001
            box["error"] = exc

    reader = threading.Thread(target=read_answer, daemon=True,
                              name="bellbriar-capture-answer")
    try:
        try:
            proc.stdin.write(len(request).to_bytes(8, "big") + request)
            proc.stdin.flush()
        except (BrokenPipeError, OSError):
            pass                    # the child is gone; its answer says why
        reader.start()
        reader.join(deadline_s)
        if reader.is_alive():
            raise RenderDeadline(deadline_s)
    except BaseException:
        # Still running (not reaped), so its pid is its own to signal.
        _kill_tree(proc)
        reader.join(10)
        _close_pipes(proc)
        raise
    _close_pipes(proc)
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:               # pragma: no cover
        _kill_tree(proc)
    try:
        answer = _ResultUnpickler.loads(box.get("out") or b"")
    except Exception:                                 # noqa: BLE001
        code = proc.returncode
        # A process a signal ended has no exit status; Python gives the
        # signal's number, negated (R4G-8).
        how = (f"stopped by signal {-code}" if isinstance(code, int)
               and code < 0 else f"exit status {code}")
        raise _ChildError(CAPTURE_PROCESS,
                          "the capture process ended without a result "
                          f"({how})") from None
    if answer[0] == "ok" and isinstance(answer[1], FetchResult):
        return answer[1]
    if answer[0] == "error" and len(answer) == 3:
        kind = str(answer[1])
        # The capture process names Python's exception classes, and none is
        # called this, so the supervisor's own words stay its own.
        raise _ChildError("RuntimeError" if kind == CAPTURE_PROCESS
                          else kind, str(answer[2]))
    raise _ChildError(CAPTURE_PROCESS, "the capture process answered "
                      "something unexpected")


def _close_pipes(proc) -> None:
    for pipe in (proc.stdin, proc.stdout):
        try:
            pipe.close()
        except Exception:                           # noqa: BLE001
            pass


def render_failure(exc: BaseException) -> str:
    """Why a rendered fetch failed, in words the harness chose. The text of
    a browser error can come from the page — a script on it can throw any
    message during scrolling or settling, net::ERR_… or "Timeout" included
    — and carries Playwright's call log and banners, so it never goes into
    a record. The failing call decides what is read from it: a net:: error
    code or a timeout only from a navigation, which a page script cannot
    word, and one fixed description for anything that ran the page's
    scripts."""
    if isinstance(exc, RenderDeadline):
        return (f"capture: did not finish within {exc.seconds:g} s, so the "
                "browser was stopped (a script on the page may never yield)")
    text = str(exc)
    m = _PW_METHOD.match(text)
    where = m.group(1) if m else getattr(exc, "kind", type(exc).__name__)
    # Only what Playwright puts first, right after the method: further on,
    # the line can quote a URL the page navigated to, which it can word.
    rest = (text.splitlines()[0][m.end():].strip() if m else "")
    net = re.match(r"net::(ERR_[A-Z0-9_]{1,60})\b", rest)
    timeout = re.match(r"Timeout (\d{1,9}) ?ms exceeded", rest)
    if where == "StepFailed" and text == "script":
        # The step's own script raised in this document (R4B-8): the
        # harness's failure on this page, not the page's.
        what = ("the harness could not scroll the page and wait for it to "
                "settle: the script it runs for that failed in this "
                "document")
    elif where == "StepFailed" or (m and where.endswith(
            (".evaluate", ".evaluate_handle"))):
        # The scroll and settle steps run in a world of the harness's own
        # (L21), where no page script can raise into them; what stops them
        # otherwise is the page crashing, closing or going to another
        # document. (Only the page-kind check still runs through evaluate.)
        what = ("the page crashed, closed or navigated away while it was "
                "scrolled and left to settle"
                if where == "StepFailed" else
                "a script on the page raised an error, or the page crashed, "
                "closed or navigated away, while it was read")
    elif m and where.startswith("BrowserType."):
        what = ("the Chromium build Playwright uses is not installed "
                "(bellbriar-eval --install-browser installs it)"
                if "Executable doesn't exist" in text
                else "the browser could not be started")
    elif m and where.endswith(_NAVIGATION_METHODS) and net:
        what = f"net::{net.group(1)}"
    elif m and where.endswith(_NAVIGATION_METHODS) and timeout:
        what = f"timed out after {int(timeout.group(1))} ms"
    elif m and _CLOSED.match(rest):
        what = "the page, context or browser closed or crashed"
    elif where == "FetchError" and text.startswith(WENT_ELSEWHERE):
        # The harness's own refusal; only its kind is read (R4E-4).
        rest = text[len(WENT_ELSEWHERE):].split(WENT_TO, 1)[0]
        code = re.match(r"HTTP (\d+)\b", rest)
        what = WENT_ON + (
            f"answered HTTP {code.group(1)}" if code else
            "no server sent (the browser's own error page, or a blank page)"
            if rest.startswith(NO_SERVER) else
            "sent it on again, and again: it stays on no one document"
            if rest.startswith(KEPT_GOING) else
            "did not finish loading within the load timeout"
            if rest.startswith(NOT_LOADED) else
            "a script on the page made in its place (a javascript: URL): "
            "no server sent it"
            if rest.startswith(MADE_BY_SCRIPT) else
            "had not arrived when the harness stopped waiting for it"
            if rest.startswith(NOT_ARRIVED) else
            "a service worker answered in the server's place"
            if rest.startswith(WORKER) else
            "is an XML document (served as XML)"
            if rest.startswith("an XML document") else
            "is not a web page (the browser shows it as text, an XML error or "
            "the XML itself, or downloads it)")
    elif where == "FetchError" and text.startswith(
            (WAIT_FOR_MISSING.split("{", 1)[0], WAIT_FOR_UNREADABLE)):
        # The harness's own refusals, which quote no selector (S5-3).
        what = text.splitlines()[0][:200]
    elif where == "FetchError" and text.startswith("an XML document"):
        what = "an XML document (served as XML)"
    elif where == "FetchError" and text.startswith("not a web page"):
        # The harness's own refusal (fetch_rendered): no page text in it.
        what = ("not a web page (the browser shows it as text, an XML error "
                "or the XML itself, or downloads it)")
    elif where == CAPTURE_PROCESS:
        # The supervisor's own words, the exit status included (R4E-3).
        what = text.splitlines()[0][:200] if text else "failed"
    elif where == "TooManyElements":
        what = ("the captured page builds more elements than the harness "
                "reads (html5.element_budget)")
    elif where == "TooDeeplyNested":
        what = ("the captured page nests its elements deeper than the "
                "harness reads (checks_static.too_deep)")
    else:
        what = "failed"
    return f"{where}: {what}"


def failure_detail(exc: BaseException, clean) -> str:
    """The first line of the error's own text, for the console only: cleaned
    of secrets (clean), control characters and length."""
    text = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
    text = _CONTROL.sub(" ", clean(text)).strip()
    return text[:300] + ("…" if len(text) > 300 else "")


#: The range of --render-deadline accepted: below 5 s no capture can
#: finish (Chromium starts, loads, scrolls and settles first), so the
#: record would blame the page for the deadline; a day at most.
MIN_RENDER_DEADLINE_S = 5
MAX_RENDER_DEADLINE_S = 24 * 3600


def check_deadline(seconds) -> float:
    """A render deadline in seconds: DEFAULT_RENDER_DEADLINE_S for None, and
    otherwise a number from MIN_RENDER_DEADLINE_S to MAX_RENDER_DEADLINE_S
    (ValueError for anything else: 0, -5, 1e-9, inf, nan)."""
    if seconds is None:
        return float(DEFAULT_RENDER_DEADLINE_S)
    try:
        value = float(seconds)
    except (TypeError, ValueError):
        raise ValueError(f"not a number of seconds: {seconds!r}") from None
    if not MIN_RENDER_DEADLINE_S <= value <= MAX_RENDER_DEADLINE_S:  # nan too
        raise ValueError(f"must be from {MIN_RENDER_DEADLINE_S} to "
                         f"{MAX_RENDER_DEADLINE_S} seconds, not {seconds!r}")
    return value


def fetch(url: str, render: bool | None = None, *,
          http_credentials: tuple[str, str] | None = None,
          record_query=(), deadline_s: float | None = None,
          fallback: str = "used server HTML", error_target: str = "refuse",
          browser_required: bool = False, **kw) -> FetchResult:
    """Fetch a page. `render=None` means render if a browser is available.
    `fallback` says, in a failed capture's reason, what was read instead: a
    --render run's build server sends the file as it is (R4G-11). A page
    that, rendered, sends the browser on to another document that is not
    a page a server sent with HTTP 200 (an error page, one no server sent,
    one that is not a web page or is an XML document, one a script made,
    one that never finished loading, one that never arrived) before the
    capture ends (the narrow step included: nothing later is watched), is
    refused (`error_target` "refuse": a URL run refuses an error page it
    is sent to directly, and never scores the server's HTML in place of
    what the browser went to), or read as `fallback` says ("fallback": a
    --render run reads the file as it is) (R4I-1, R4I-3, R5A-1, R5A-5,
    R5E-6).

    A fallback to server HTML is never silent: the reason travels in the
    result, into the report and into the bundle, because a quiet fallback
    is how a customer ends up with a clean report on a broken page.

    `http_credentials` is (user, password), offered only to the URL's own
    origin. `record_query` names the query or fragment parameters whose
    values are recorded; every other value is recorded as REDACTED. The
    rendered capture runs in a process of its own and is stopped after
    `deadline_s` (DEFAULT_RENDER_DEADLINE_S), then falls back as any other
    failure does.

    `browser_required` (a --render run, S5-3): a browser that is missing
    or cannot start is refused, never fallen back from, since every page
    would then be read without one; a failure of one page's capture still
    falls back as `fallback` says.
    """
    check_scheme(url)
    credentials = _check_credentials(http_credentials)
    keep = tuple(sorted(names(record_query)))
    # Browser errors quote the URL they failed on, token and all.
    scrub = secret_values(url, keep) | ({credentials[1]} if credentials
                                        else set())

    def clean(text: str) -> str:
        return redact_text(text, scrub, keep)

    def server() -> FetchResult:
        return fetch_server(url, timeout=kw.get("timeout", 30),
                            http_credentials=credentials, record_query=keep)

    if render is False:
        r = server()
        r.fallback_reason = "rendering disabled with --no-render"
        return r
    ok, why = playwright_available()
    if not ok:
        if browser_required:
            raise BrowserUnavailable(why)
        if render is True:
            raise FetchError(why)
        r = server()
        r.fallback_reason = why
        return r
    went_to = ""
    try:
        rendered = _fetch_rendered_isolated(
            url, check_deadline(deadline_s),
            http_credentials=credentials, record_query=keep, **kw)
    except Exception as exc:                      # noqa: BLE001
        if isinstance(exc, SandboxRefused) or \
                getattr(exc, "kind", "") == "SandboxRefused":
            # Refused, not failed: nothing falls back (D9). Its text is
            # the harness's own.
            refused = str(exc)
        else:
            refused = ""
            # The record gets only words the harness chose
            # (render_failure): a page script can throw any text. The
            # error's own first line, cleaned, is for the console.
            failure = render_failure(exc)
            went_to = str(exc) if WENT_TO in str(exc) else ""
            # Words render_failure already recorded are not shown again: a
            # step's code (R4C-9), the deadline, the supervisor's own
            # (R4E-3). The rest are the error's own, for the console.
            detail = ("" if isinstance(exc, (StepFailed, RenderDeadline))
                      or getattr(exc, "kind", "") in ("StepFailed",
                                                      CAPTURE_PROCESS)
                      else failure_detail(exc, clean))
    else:
        # A refusal, not a failure: nothing falls back (S5-2).
        _refuse_private_page(url, rendered)
        return rendered
    if refused:
        raise SandboxRefused(refused)
    if browser_required and failure.startswith("BrowserType."):
        refusal = BrowserUnavailable(f"rendered fetch failed: {failure}")
        refusal.detail = detail
        raise refusal
    # Outside the handler, so nothing raised from here on carries the
    # browser's exception — and the URL it quotes — as its context.
    if render is True:
        # Only the harness's words in the text a record keeps; the
        # browser's, which a page can word, ride along for the console
        # (R4C-3).
        refusal = FetchError(f"rendered fetch failed: {failure}")
        refusal.detail = detail
        raise refusal
    went = failure[len("FetchError: "):] if failure.startswith(
        "FetchError: " + WENT_ON) else ""
    if error_target == "refuse" and went:
        # Wherever it went, the server's HTML of the page that sent it
        # there is not what anyone is shown: an error page, a document no
        # server sent, one that is not a web page or one served as XML is
        # refused in a URL run, never scored in its place (R4I-1, R5A-5).
        to = went_to.split(WENT_TO, 1)[1] if WENT_TO in went_to else ""
        answered = re.match(re.escape(WENT_ON) + r"answered HTTP (\d+)", went)
        why = ("the harness evaluates only a page its server sends with HTTP "
               "200" if answered and answered.group(1).startswith("2")
               and len(answered.group(1)) == 3 else
               "an error page is not the page you meant to evaluate"
               if went.startswith((WENT_ON + "answered HTTP",
                                   WENT_ON + "no server sent")) else
               "evaluate that document by its own URL, if it is a page"
               if went.startswith(WENT_ON + "is an XML document") else
               "a page that stays on no one document cannot be evaluated"
               if went.startswith(WENT_ON + "sent it on again") else
               "a page that never finished loading is not one anyone was "
               "shown whole" if went.startswith(WENT_ON + "did not finish")
               else "a page cannot be captured while the browser waits to "
               "leave it" if went.startswith(WENT_ON + "had not arrived")
               else "a document a javascript: URL made is not the page its "
               "server sent" if went.startswith(WENT_ON + "a script on the page")
               else "a service worker's answer is not the page its server "
               "sent" if went.startswith(WENT_ON + "a service worker")
               else "a document that is not a web page is not the page you "
               "meant to evaluate")
        refusal = FetchError(f"when rendered, {went}: {why}")
        if to:
            # The page's choice of URL: for the console only (R5C-12).
            refusal.where = to
        raise refusal
    r = server()
    if (failure == "FetchError: an XML document (served as XML)"
            and r.reader == "xml"):
        r.fallback_reason = XML_PAGE_REASON
    else:
        r.fallback_reason = f"rendered fetch failed ({failure}); {fallback}"
        r.fallback_detail = detail or None
    return r
