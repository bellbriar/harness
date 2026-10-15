"""bb-media-autoplay and bl-autoplay-media (review finding P2-10).

The rule used to FAIL conformant media and to misread muted media:

  * `<audio autoplay controls>` and `<video autoplay controls>` failed,
    though native controls are the mechanism 1.4.2 asks for (ACT 4c31df,
    Passed Example 1). They are now a minor review — native controls are
    not keyboard-operable in some browser and assistive-technology
    combinations (ACT's own note), and a stylesheet can hide them — and
    still FAIL when markup shows them hidden, aria-hidden, inert or
    zero-size.
  * `<audio autoplay muted>` failed; muted media plays no sound.
  * React sets `muted` as a property only (react#10389), so a hydrated
    `<video autoPlay muted>` hero was captured without `muted` and failed
    as autoplaying with sound. The rendered capture now records the
    property, under a name derived from its per-capture secret, which page
    code never sees.
  * Media inside <template> or <noscript> never plays in a browser that
    runs scripts (a declarative shadow root does), nor does SVG or MathML
    `video`, nor media with no source.
  * The capture call ran through page-reachable JavaScript: a page could
    learn the secret names from the arguments, rewrite the returned
    snapshot (also in Part J), or run code mid-capture through prototype
    accessors. It now goes over CDP with prototype-less internals.
"""
import contextlib
import io
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bellbriar_harness import cli, engine as E, fetch as F      # noqa: E402
from bellbriar_harness.lint import ERROR, WARN, lint_text       # noqa: E402
from bellbriar_harness.model import (FAIL, MINOR, MODERATE,      # noqa: E402
                                     NEEDS_REVIEW, SERIOUS, muted_attr)
from tests.test_fetch import HAVE_BROWSER, _WHY, _Server       # noqa: E402

RULE = "bb-media-autoplay"


def page(body: str) -> str:
    return ('<!doctype html><html lang="en"><head><title>Media</title></head>'
            f'<body><main><h1>Media</h1>{body}</main></body></html>')


def findings(html: str, provenance_attr=None):
    p = E.run_page(html, "x.html", E.load_rulebook(),
                   provenance_attr=provenance_attr)
    rr = next(r for r in p.results if r.rule_id == RULE)
    return rr, [(f.verdict, f.impact) for f in rr.findings], rr.findings


def eval_cli(html: str, *argv: str) -> int:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "p.html"
        path.write_text(html, encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            return cli.main([str(path), *argv])


class TestVerdicts(unittest.TestCase):
    CASES = {
        # sound, with native controls markup shows usable: review, minor
        '<audio autoplay controls src="a.mp3"></audio>': [(NEEDS_REVIEW, MINOR)],
        '<video autoplay controls src="a.mp4"></video>': [(NEEDS_REVIEW, MINOR)],
        # sound, no controls: FAIL (heuristic: duration and other controls
        # are unknown to markup)
        '<audio autoplay src="a.mp3"></audio>': [(FAIL, SERIOUS)],
        '<video autoplay src="a.mp4"></video>': [(FAIL, SERIOUS)],
        # sound, controls the user cannot see or reach: FAIL
        '<audio autoplay controls hidden src="a.mp3"></audio>': [(FAIL, SERIOUS)],
        '<video autoplay controls style="display: none" src="a.mp4"></video>':
            [(FAIL, SERIOUS)],
        '<div aria-hidden="true"><video autoplay controls src="a.mp4"></video></div>':
            [(FAIL, SERIOUS)],
        '<div inert><video autoplay controls src="a.mp4"></video></div>':
            [(FAIL, SERIOUS)],
        '<video autoplay controls width="0" height="0" src="a.mp4"></video>':
            [(FAIL, SERIOUS)],
        # muted: no sound. A muted video can still be moving content.
        '<audio autoplay muted src="a.mp3"></audio>': [],
        '<video autoplay muted src="a.mp4"></video>': [(NEEDS_REVIEW, MODERATE)],
        '<video autoplay muted controls src="a.mp4"></video>': [],
        # no autoplay: applicable, nothing to report
        '<video controls src="a.mp4"></video>': [],
        # no source in markup: script may add one on click (fine) or by
        # lazy loading (sound at once), so a minor review, never a FAIL
        '<audio autoplay></audio>': [(NEEDS_REVIEW, MINOR)],
        '<audio autoplay src=" "></audio>': [(NEEDS_REVIEW, MINOR)],
        '<video autoplay data-src="a.mp4"></video>': [(NEEDS_REVIEW, MINOR)],
        '<video autoplay muted></video>': [(NEEDS_REVIEW, MODERATE)],
        '<video autoplay><source src="a.mp4"></video>': [(FAIL, SERIOUS)],
        # only a child <source> loads
        '<video autoplay><div><source src="a.mp4"></div></video>':
            [(NEEDS_REVIEW, MINOR)],
        # a declarative shadow root is rendered, and its media plays
        '<x-a><template shadowrootmode="open"><audio autoplay src="a.mp3">'
        '</audio></template></x-a>': [(FAIL, SERIOUS)],
        '<x-a><template shadowrootmode="open"><audio autoplay controls '
        'src="a.mp3"></audio></template></x-a>': [(NEEDS_REVIEW, MINOR)],
        # HTML inside SVG/MathML integration points is HTML, and so is
        # anything after a start tag that makes the parser leave SVG
        '<svg><foreignObject><video autoplay src="a.mp4"></video>'
        '</foreignObject></svg>': [(FAIL, SERIOUS)],
        '<svg><desc><video autoplay src="a.mp4"></video></desc></svg>':
            [(FAIL, SERIOUS)],
        '<math><mtext><video autoplay src="a.mp4"></video></mtext></math>':
            [(FAIL, SERIOUS)],
        '<svg><path></path><div><video autoplay src="a.mp4"></video></div></svg>':
            [(FAIL, SERIOUS)],
        '<svg><font color="red"><audio autoplay src="a.mp3"></audio></font></svg>':
            [(FAIL, SERIOUS)],
        '<x-a><template shadowrootmode="OPEN"><audio autoplay src="a.mp3">'
        '</audio></template></x-a>': [(FAIL, SERIOUS)],
        # inline visibility: the nearest declaration wins, as in CSS
        '<div style="visibility:hidden"><video autoplay controls '
        'style="visibility: visible" src="a.mp4"></video></div>':
            [(NEEDS_REVIEW, MINOR)],
        '<div style="visibility:hidden"><video autoplay controls '
        'src="a.mp4"></video></div>': [(FAIL, SERIOUS)],
        '<video autoplay controls style="content-visibility: hidden" '
        'src="a.mp4"></video>': [(NEEDS_REVIEW, MINOR)],
    }

    def test_each_case(self):
        for body, want in self.CASES.items():
            with self.subTest(body=body):
                rr, got, _ = findings(page(body))
                self.assertTrue(rr.applicable)
                self.assertEqual(got, want)

    def test_media_that_never_plays_is_not_applicable(self):
        for body in ('<template><audio autoplay src="a.mp3"></audio></template>',
                     '<noscript><video autoplay src="a.mp4"></video></noscript>',
                     '<template><x-a><template shadowrootmode="open"><audio '
                     'autoplay src="a.mp3"></audio></template></x-a></template>',
                     # the parser attaches no root here: <ul> cannot host
                     # one, and a host takes only its first
                     '<ul><template shadowrootmode="open"><audio autoplay '
                     'src="a.mp3"></audio></template></ul>',
                     '<x-a><template shadowrootmode="open"></template><template '
                     'shadowrootmode="open"><audio autoplay src="a.mp3"></audio>'
                     '</template></x-a>',
                     '<x-a><template shadowrootmode="sideways"><audio autoplay '
                     'src="a.mp3"></audio></template></x-a>',
                     # the browser does not trim the value
                     '<x-a><template shadowrootmode=" open"><audio autoplay '
                     'src="a.mp3"></audio></template></x-a>',
                     # a reserved name is no custom element
                     '<font-face><template shadowrootmode="open"><audio '
                     'autoplay src="a.mp3"></audio></template></font-face>',
                     '<svg><font><audio autoplay src="a.mp3"></audio></font></svg>',
                     '<svg><video autoplay src="a.mp4"></video></svg>',
                     '<math><video autoplay src="a.mp4"></video></math>'):
            with self.subTest(body=body):
                rr, got, _ = findings(page(body))
                self.assertFalse(rr.applicable)
                self.assertEqual(got, [])

    def test_templates_left_in_a_capture_are_inert(self):
        """In a rendered capture the real shadow roots are already
        <bb-shadow-root>; a <template shadowrootmode> still there was set
        by innerHTML, which never attaches one."""
        html = page('<div><template shadowrootmode="open"><audio autoplay '
                    'src="a.mp3"></audio></template></div>')
        self.assertEqual(findings(html)[1], [(FAIL, SERIOUS)])     # parsed: a root
        rr, got, _ = findings(html, "data-bb-p-0123456789abcdef")
        self.assertFalse(rr.applicable)
        self.assertEqual(got, [])

    def test_materialize_leaves_real_templates_alone(self):
        attr = "data-bb-p-0123456789abcdef"
        html = (f'<div {attr}="server"><template shadowrootmode="open">'
                f'<p {attr}="server">root</p></template></div>'
                f'<div {attr}="server"><template {attr}="first-party" '
                f'shadowrootmode="open"><p>inert</p></template></div>')
        out = F.materialize_shadow_roots(html, attr)
        self.assertEqual(out.count("<bb-shadow-root"), 1)
        self.assertIn(f'<template {attr}="first-party" shadowrootmode="open">',
                      out)

    def test_each_reason_is_stated_accurately(self):
        """aria-hidden controls are visible; inert ones are visible too.
        Neither may be called hidden."""
        cases = {
            '<div aria-hidden="true"><video autoplay controls src="a.mp4">'
            '</video></div>': "inside aria-hidden content, which assistive "
                              "technology does not expose",
            '<div inert><video autoplay controls src="a.mp4"></video></div>':
                "inside inert content, which no one can operate",
            '<video autoplay controls hidden src="a.mp4"></video>':
                "native controls are hidden.",
            '<video autoplay controls width="0" src="a.mp4"></video>':
                "zero-size, so no one can see them",
        }
        for body, phrase in cases.items():
            with self.subTest(body=body):
                (f,) = findings(page(body))[2]
                self.assertEqual(f.verdict, FAIL)
                self.assertIn(phrase, f.message)
                self.assertIn("ACT 4c31df", f.message)

    def test_messages_cite_wcag_not_the_pack(self):
        """A FAIL is a WCAG claim; the old audio message cited a pack rule."""
        for body in self.CASES:
            for f in findings(page(body))[2]:
                with self.subTest(body=body):
                    self.assertNotIn("pack", f.message.lower())
                    self.assertTrue("1.4.2" in f.message
                                    or "2.2.2" in f.message, f.message)


class TestCapturedMutedState(unittest.TestCase):
    """The record of the `muted` property is read only under the capture's
    own secret name; markup anywhere else cannot claim it."""

    ATTR = "data-bb-p-0123456789abcdef"

    def test_name_derives_from_the_provenance_attribute(self):
        self.assertEqual(muted_attr(self.ATTR), self.ATTR + "-muted")

    def test_record_honored_both_ways_under_the_trusted_name(self):
        m = muted_attr(self.ATTR)
        muted = page(f'<video autoplay {m}="true" src="a.mp4"></video>')
        self.assertEqual(findings(muted, self.ATTR)[1], [(NEEDS_REVIEW, MODERATE)])
        # The attribute set the starting state; script unmuted it.
        unmuted = page(f'<video autoplay muted {m}="false" src="a.mp4"></video>')
        self.assertEqual(findings(unmuted, self.ATTR)[1], [(FAIL, SERIOUS)])

    def test_a_page_cannot_write_the_record(self):
        m = muted_attr(self.ATTR)
        forged = page(f'<video autoplay {m}="true" src="a.mp4"></video>')
        # File and server runs: no trusted name, so the stamp is ignored.
        self.assertEqual(findings(forged)[1], [(FAIL, SERIOUS)])
        # A rendered run reads only its own name, which differs per capture.
        self.assertEqual(findings(forged, "data-bb-p-fedcba9876543210")[1],
                         [(FAIL, SERIOUS)])

    def test_unrecognised_record_values_fall_back_to_markup(self):
        m = muted_attr(self.ATTR)
        odd = page(f'<video autoplay {m}="yes" src="a.mp4"></video>')
        self.assertEqual(findings(odd, self.ATTR)[1], [(FAIL, SERIOUS)])


class TestGate(unittest.TestCase):
    def test_native_controls_do_not_fail_the_gate_even_with_strict(self):
        html = page('<video autoplay controls src="a.mp4"></video>')
        self.assertEqual(eval_cli(html, "--fail-on", "any"), 0)
        self.assertEqual(eval_cli(html, "--fail-on", "any", "--strict"), 0)

    def test_sound_without_controls_still_fails_the_gate(self):
        html = page('<video autoplay src="a.mp4"></video>')
        self.assertEqual(eval_cli(html, "--fail-on", "tier2"), 1)


class TestLint(unittest.TestCase):
    """bl-autoplay-media mirrors the rule: an error only where the gate
    would fail; the pack's ban on autoplaying sound stays a warning."""

    def sev(self, src, path="C.jsx"):
        return [f.severity for f in lint_text(src, path)
                if f.rule_id == "bl-autoplay-media"]

    def test_verdicts(self):
        cases = {
            '<audio autoPlay src="a.mp3" />': [ERROR],
            '<audio autoPlay controls src="a.mp3" />': [WARN],
            '<audio autoPlay muted src="a.mp3" />': [],
            '<video autoPlay src="a.mp4" />': [ERROR],
            '<video autoPlay controls src="a.mp4" />': [WARN],
            '<video autoPlay muted src="a.mp4" />': [WARN],
            '<video autoPlay muted controls src="a.mp4" />': [],
        }
        for src, want in cases.items():
            with self.subTest(src=src):
                self.assertEqual(self.sev(src), want)

    def test_a_boolean_bound_to_false_is_off(self):
        """React renders no controls for controls={false}; Vue none for
        :controls="false". A plain HTML value is on whatever it says."""
        cases = {
            ('<video autoPlay controls={false} src="a.mp4" />', "C.jsx"): [ERROR],
            ('<video autoPlay muted={false} src="a.mp4" />', "C.jsx"): [ERROR],
            ('<video autoPlay={false} src="a.mp4" />', "C.jsx"): [],
            ('<template><video autoplay :controls="false" src="a.mp4">'
             '</video></template>', "C.vue"): [ERROR],
            ('<template><video autoplay v-bind:muted="false" src="a.mp4">'
             '</video></template>', "C.vue"): [ERROR],
            ('<video autoplay muted="false" src="a.mp4"></video>', "a.html"): [WARN],
            ('<video autoplay controls="false" src="a.mp4"></video>', "a.html"): [WARN],
        }
        for (src, path), want in cases.items():
            with self.subTest(src=src):
                self.assertEqual(self.sev(src, path), want)

    def test_framework_bindings(self):
        cases = {
            ('<video autoplay [muted]="true" src="a.mp4"></video>',
             "a.component.html"): [WARN],       # Angular's hero-video idiom
            ('<video autoplay [attr.muted]="true" src="a.mp4"></video>',
             "a.component.html"): [WARN],
            ('<video autoplay [muted]="false" src="a.mp4"></video>',
             "a.component.html"): [ERROR],
            ('<template><video autoplay :muted.prop="true" src="a.mp4">'
             '</video></template>', "C.vue"): [WARN],
            ('<video autoplay muted="{false}" src="a.mp4"></video>',
             "C.svelte"): [ERROR],
            ('<video autoPlay muted={!quiet} src="a.mp4" />', "C.jsx"): [WARN],
            # an expression the linter cannot read is never an error
            ('<video autoplay bind:muted={m} src="a.mp4"></video>',
             "C.svelte"): [WARN],
            ('<video autoplay x-bind:muted="true" src="a.mp4"></video>',
             "a.html"): [WARN],                  # Alpine
            ('html`<video autoplay ?muted=${true} src="a.mp4"></video>`',
             "c.js"): [WARN],                    # Lit
            ('html`<video autoplay .muted=${true} src="a.mp4"></video>`',
             "c.js"): [WARN],
            ('html`<video autoplay ?muted=${false} src="a.mp4"></video>`',
             "c.js"): [ERROR],
            # "{false}" is an expression only in Svelte; in HTML it mutes
            ('<video autoplay muted="{false}" src="a.mp4"></video>',
             "a.html"): [WARN],
        }
        for (src, path), want in cases.items():
            with self.subTest(src=src):
                self.assertEqual(self.sev(src, path), want)

    def test_vue_and_html_spellings(self):
        self.assertEqual(self.sev('<template><audio autoplay controls '
                                  'src="a.mp3"></audio></template>', "C.vue"),
                         [WARN])
        self.assertEqual(self.sev('<audio autoplay src="a.mp3"></audio>',
                                  "a.html"), [ERROR])

    def test_the_warning_names_the_pack_ban_and_wcag(self):
        msg = next(f.message for f in lint_text(
            '<audio autoPlay controls src="a.mp3" />', "C.jsx")
            if f.rule_id == "bl-autoplay-media")
        self.assertIn("pack", msg.lower())
        self.assertIn("1.4.2", msg)


@unittest.skipUnless(HAVE_BROWSER, _WHY)
class TestRenderedCaptureRecordsMuted(unittest.TestCase):
    """A real Chromium. `v.muted = true` with no attribute is exactly what
    React does for <video autoPlay muted> (checked by hand against React
    19.2.8: the hydrated markup carries autoplay but no muted)."""

    @classmethod
    def setUpClass(cls):
        cls.dir = Path(tempfile.mkdtemp(prefix="bb-media-"))
        cls.srv = _Server(cls.dir)

    @classmethod
    def tearDownClass(cls):
        cls.srv.stop()
        import shutil
        shutil.rmtree(cls.dir, ignore_errors=True)

    def capture(self, body_and_script: str, html_attrs: str = ""):
        (self.dir / "p.html").write_text(
            page(body_and_script).replace('<html lang="en">',
                                          f'<html lang="en"{html_attrs}>'),
            encoding="utf-8")
        fr = F.fetch(f"{self.srv.base}/p.html", render=True)
        self.assertTrue(fr.instrumented, fr.notes)
        p = E.run_page(fr.html, "p", E.load_rulebook(),
                       provenance_attr=fr.provenance_attr)
        rr = next(r for r in p.results if r.rule_id == RULE)
        by_id = {}
        for f in rr.findings:
            m = re.search(r'id="(\w+)"', f.snippet)
            by_id.setdefault(m.group(1) if m else "?", []).append(f.verdict)
        return fr, by_id

    def test_property_muted_is_recorded_and_unmuting_is_seen(self):
        fr, by_id = self.capture(
            '<div id="slot"></div><video id="unmuted" autoplay muted '
            'src="b.mp4"></video><script>'
            'var v = document.createElement("video"); v.id = "hero";'
            'v.autoplay = true; v.muted = true; v.loop = true; v.src = "a.mp4";'
            'document.getElementById("slot").appendChild(v);'
            'var a = document.createElement("audio"); a.id = "quiet";'
            'a.autoplay = true; a.muted = true; a.src = "q.mp3";'
            'document.getElementById("slot").appendChild(a);'
            'var l = document.createElement("video"); l.id = "loud";'
            'l.autoplay = true; l.src = "l.mp4";'
            'document.getElementById("slot").appendChild(l);'
            'document.getElementById("unmuted").muted = false;'
            '</script>')
        self.assertNotIn(' muted', re.search(r'<video id="hero"[^>]*>',
                                             fr.html).group(0)
                         .replace(muted_attr(fr.provenance_attr), ""),
                         "the browser serialized a muted attribute; the "
                         "test no longer reproduces React's property-only "
                         "muted")
        self.assertEqual(by_id.get("hero"), [NEEDS_REVIEW])   # moving content
        self.assertNotIn("quiet", by_id)
        self.assertEqual(by_id.get("loud"), [FAIL])
        self.assertEqual(by_id.get("unmuted"), [FAIL])

    def test_a_page_cannot_fake_muted(self):
        """The getter is captured before page scripts run; a page that
        redefines it, or writes its own stamp, changes nothing."""
        fr, by_id = self.capture(
            '<video id="loud" autoplay src="l.mp4" '
            'data-bb-p-0000000000000000-muted="true"></video><script>'
            'Object.defineProperty(HTMLMediaElement.prototype, "muted", '
            '{get: function () { return true; }, set: function () {}, '
            'configurable: true});</script>')
        self.assertEqual(by_id.get("loud"), [FAIL])
        self.assertIn(f'{muted_attr(fr.provenance_attr)}="false"', fr.html)

    def test_media_in_a_shadow_root_is_recorded(self):
        fr, by_id = self.capture(
            '<x-hero></x-hero><script>customElements.define("x-hero", '
            'class extends HTMLElement { connectedCallback() {'
            ' const r = this.attachShadow({mode: "closed"});'
            ' const v = document.createElement("video"); v.id = "shadowed";'
            ' v.autoplay = true; v.muted = true; v.src = "a.mp4";'
            ' r.appendChild(v);'
            ' const a = document.createElement("audio"); a.id = "shadowloud";'
            ' a.autoplay = true; a.src = "a.mp3"; r.appendChild(a); } });'
            '</script>')
        m = muted_attr(fr.provenance_attr)
        self.assertRegex(fr.html, rf'<video[^>]*id="shadowed"[^>]*{m}="true"'
                         rf'|<video[^>]*{m}="true"[^>]*id="shadowed"')
        self.assertEqual(by_id.get("shadowed"), [NEEDS_REVIEW])  # moving content
        self.assertEqual(by_id.get("shadowloud"), [FAIL])

    def test_page_code_cannot_reach_the_capture(self):
        """Each hook, once it can see the stamps, marks the loud video muted
        and the image third-party, or rewrites the returned snapshot. The
        first three worked against page.evaluate; the localName one and
        the `then` one worked in Part J; the index setter worked against
        the first draft of this change."""
        forge = ('function forge(){ try { var v = document.getElementById('
                 '"loud"), im = document.getElementById("noalt");'
                 ' v.getAttributeNames().forEach(function (a) {'
                 '  if (a.indexOf("data-bb-p-") !== 0) return;'
                 '  if (/-muted$/.test(a)) v.setAttribute(a, "true");'
                 '  else im.setAttribute(a, "third-party:cdn.example"); });'
                 ' } catch (e) {} }')
        hooks = {
            "arguments iterator": 'var o = Array.prototype[Symbol.iterator];'
                'Array.prototype[Symbol.iterator] = function () { try {'
                ' if (this.length === 3 && String(this[0]).indexOf('
                '"__bb_capture_") === 0) { document.getElementById("loud")'
                '.setAttribute(this[2], "true"); document.getElementById('
                '"noalt").setAttribute(this[1], "third-party:x");'
                ' return o.call([this[0], "data-x-decoy", "data-x-decoy-m"]);'
                ' } } catch (e) {} return o.call(this); };',
            "result then": 'Object.defineProperty(Object.prototype, "then", '
                '{configurable: true, get: function () { if (this && typeof '
                'this.html === "string") this.html = this.html.replace('
                '/<video id="loud"[^>]*><\\/video>/, ""); return undefined; }});',
            "result toJSON": 'Object.prototype.toJSON = function () { if '
                '(typeof this.html === "string") this.html = ""; return this; };',
            "array index accessors": 'for (var k = 0; k < 4; k++) (function (k) {'
                ' Object.defineProperty(Array.prototype, k, {configurable: true,'
                ' set: function (v) { forge(); Object.defineProperty(this, k, '
                '{value: v, writable: true, enumerable: true, configurable: '
                'true}); }, get: function () { forge(); return undefined; }});'
                ' })(k);',
            "array iterator next": 'var ai = Object.getPrototypeOf([]'
                '[Symbol.iterator]()), on = ai.next; ai.next = function () {'
                ' forge(); return on.call(this); };',
            "localName getter": 'var lg = Object.getOwnPropertyDescriptor('
                'Element.prototype, "localName").get; Object.defineProperty('
                'Element.prototype, "localName", {configurable: true, get: '
                'function () { forge(); return lg.call(this); }});',
            "Object.prototype accessors": '["serializableShadowRoots", '
                '"shadowRoots", "next", "done", "value"].forEach(function (k) {'
                ' Object.defineProperty(Object.prototype, k, {configurable: '
                'true, get: function () { forge(); return undefined; }, set: '
                'function (v) { forge(); Object.defineProperty(this, k, {value:'
                ' v, writable: true, configurable: true, enumerable: true}); '
                '}}); });',
            "WeakMap replaced": 'window.WeakMap = function () { forge(); '
                'return {}; };',
        }
        hooks["customized built-in root"] = (
            'class XRoot extends HTMLHtmlElement { constructor() { super();'
            ' if (this !== document.documentElement) forge(); } }'
            'customElements.define("x-root", XRoot, {extends: "html"});')
        for name, js in hooks.items():
            with self.subTest(hook=name):
                # Positive control: the hook is installed (the attribute is
                # in the snapshot). Each route was shown to forge or erase
                # the record against an earlier build.
                fr, by_id = self.capture(
                    '<video id="loud" autoplay src="l.mp4"></video>'
                    '<img id="noalt" src="x.png"><script>' + forge + js
                    + 'document.body.setAttribute("data-hooked", "1");'
                    '</script>', html_attrs=' is="x-root"')
                self.assertIn('data-hooked="1"', fr.html)
                self.assertEqual(by_id.get("loud"), [FAIL])
                p = E.run_page(fr.html, "p", E.load_rulebook(),
                               provenance_attr=fr.provenance_attr)
                img = [f for r in p.results if r.rule_id == "bb-img-alt"
                       for f in r.findings]
                self.assertEqual([(f.verdict, f.origin) for f in img],
                                 [(FAIL, "server")])

    def test_an_xml_document_is_read_as_xml(self):
        """XHTML served as XML is read from the server's bytes, as XML,
        in a rendered run too (PR2-3): a capture is read back as HTML. Its
        root keeps lang (it once lost it to a capture cut by length), and
        --require-render refuses the page."""
        (self.dir / "x.xhtml").write_text(
            '<?xml version="1.0" encoding="utf-8"?>\n<html xmlns='
            '"http://www.w3.org/1999/xhtml" xml:lang="en" lang="en" '
            'class="no-js"><head><title>X</title></head><body><main>'
            '<h1>X</h1><video id="loud" autoplay="autoplay" src="l.mp4">'
            '</video></main></body></html>', encoding="utf-8")
        fr = F.fetch(f"{self.srv.base}/x.xhtml")
        self.assertEqual((fr.mode, fr.reader), ("server", "xml"))
        self.assertEqual(fr.fallback_reason, F.XML_PAGE_REASON)
        p = E.run_page(fr.html, "x", E.load_rulebook(), reader=fr.reader)
        lang = [f for r in p.results if r.rule_id == "bb-html-lang"
                for f in r.findings if f.verdict == FAIL]
        self.assertEqual(lang, [])
        with self.assertRaisesRegex(F.FetchError, "an XML document"):
            F.fetch(f"{self.srv.base}/x.xhtml", render=True)

    def test_an_inert_template_set_by_innerHTML_is_not_a_shadow_root(self):
        fr, by_id = self.capture(
            '<div id="s"></div><script>document.getElementById("s").innerHTML'
            ' = \'<div><template shadowrootmode="open"><audio id="inert" '
            'autoplay src="a.mp3"></audio></template></div>\';</script>')
        self.assertNotIn("inert", by_id)
        self.assertNotIn("<bb-shadow-root", fr.html)

    def test_records_are_removed_from_the_live_page(self):
        from playwright.sync_api import sync_playwright
        (self.dir / "q.html").write_text(page(
            '<video id="v" autoplay muted src="a.mp4"></video>'),
            encoding="utf-8")
        with sync_playwright() as p:
            b = p.chromium.launch(args=["--no-sandbox"])
            try:
                pg = b.new_page()
                pg.add_init_script(F.instrumentation_script(
                    "__bb_cap_t", capture_token="ab" * 16))
                pg.goto(f"{self.srv.base}/q.html", wait_until="load")
                cap = pg.evaluate("() => window.__bb_cap_t('" + "ab" * 16 +
                                  "', 'data-bb-p-t', 'data-bb-p-t-muted')")
                left = pg.evaluate("() => document.getElementById('v')"
                                   ".getAttributeNames()")
            finally:
                b.close()
        self.assertIn('data-bb-p-t-muted="true"', cap["html"])
        self.assertEqual([n for n in left if n.startswith("data-bb-p-t")], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
