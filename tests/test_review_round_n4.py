"""Part N, round 4: the independent review of the round-2 and round-3 fixes.

  * High: any `popover` attribute took its subtree out of every rule,
    open or not, in file and rendered runs: one attribute and an author
    display value moved a page's failures out of the score. The same held,
    before Part N, for the `hidden` attribute and a <dialog> without
    `open` under an inline display. Markup hiding by the browser's own
    stylesheet now yields to any author display value (the page's inline
    style or its own <style>), and in a rendered run that recorded what the
    page hides, markup hides only where the capture saw it hidden.
  * The page's own <style> was read without the cascade: an element both
    hidden and shown by its rules, an inline style that shows it, a
    visibility:visible descendant, a conditional media query, a non-CSS
    style type, and a rule that holds only without scripts all left a real
    failure a review.
  * Content hidden now by a container around or inside the aria-hidden one
    FAILed in a file run (round 3) and passed or reviewed rendered: it is a
    review in both now.
  * The capture placed slotted children by their DOM parent, but the rules
    read them inside the slot that renders them; "shown" could not land
    inside SVG.
  * Smaller: address classes from explicit IANA tables (6to4 and NAT64 read
    by the IPv4 address they embed), every grandfathered language tag fails
    (ACT bf051a) with its preferred tag, and the evaluate-failure wording.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bellbriar_harness import fetch as F                        # noqa: E402
from bellbriar_harness.engine import load_rulebook, run_page    # noqa: E402
from bellbriar_harness.model import FAIL, MODERATE, NEEDS_REVIEW  # noqa: E402
from tests.test_fetch_hardening import HAVE_BROWSER, _WHY, _Site, send  # noqa: E402

CONTENT = ('<img src="a.png"><a href="/x"></a><button></button>'
           '<input type="text" name="q">')
NAME_RULES = ("bb-img-alt", "bb-link-name", "bb-button-name", "bb-control-label")


def page(body: str, head: str = "") -> str:
    return ('<!doctype html><html lang="en"><head><title>T</title>'
            f'{head}</head><body><main><h1>T</h1>{body}</main></body></html>')


def failed_rules(html: str, provenance_attr=None) -> list:
    p = run_page(html, "x.html", load_rulebook(), provenance_attr=provenance_attr)
    return sorted(rr.rule_id for rr in p.results
                  if any(f.verdict == FAIL for f in rr.findings))


def findings(html: str, rule: str, provenance_attr=None) -> list:
    p = run_page(html, "x.html", load_rulebook(), provenance_attr=provenance_attr)
    return [f for rr in p.results if rr.rule_id == rule for f in rr.findings]


class TestAuthorStylesBeatTheBrowsersHiding(unittest.TestCase):
    def test_a_shown_popover_dialog_or_hidden_element_is_evaluated(self):
        for label, wrap in (
                ("popover, inline display", '<div popover style="display:block">{}</div>'),
                ("hidden, inline display", '<div hidden style="display:flex">{}</div>'),
                ("dialog without open, inline display",
                 '<dialog style="display:block">{}</dialog>'),
                ("display: initial", '<div hidden style="display:initial">{}</div>'),
                # Chromium 141 shows it: the hidden attribute is no part of
                # its own stylesheet, which revert falls back to (R5M-7).
                ("display: revert", '<div hidden style="display:revert">{}</div>')):
            with self.subTest(label):
                self.assertEqual(failed_rules(page(wrap.format(CONTENT))),
                                 sorted(NAME_RULES))

    def test_a_rule_in_the_page_own_style_shows_it_too(self):
        style = "<style>[popover]{display:block}</style>"
        self.assertEqual(failed_rules(page(f"<div popover>{CONTENT}</div>", style)),
                         sorted(NAME_RULES))

    def test_what_the_browser_keeps_hidden_stays_hidden(self):
        for label, wrap in (
                ("closed popover", "<div popover>{}</div>"),
                ("hidden", "<div hidden>{}</div>"),
                ("display: revert-layer",
                 '<div hidden style="display:revert-layer">{}</div>'),
                ("closed dialog, display: revert",
                 '<dialog style="display:revert">{}</dialog>'),
                ("closed dialog", "<dialog>{}</dialog>")):
            with self.subTest(label):
                self.assertEqual(failed_rules(page(wrap.format(CONTENT))), [])

    def test_names_read_shown_text(self):
        html = page('<a href="/c"><span hidden style="display:inline">Cart</span></a>')
        self.assertEqual(findings(html, "bb-link-name"), [])
        html = page('<a href="/c"><span hidden>Cart</span></a>')
        self.assertEqual([f.verdict for f in findings(html, "bb-link-name")], [FAIL])


class TestPageStyleCascade(unittest.TestCase):
    def verdicts(self, body, style):
        return [f.verdict for f in findings(page(body, style), "bb-aria-hidden-focus")]

    def test_what_the_page_shows_again_still_fails(self):
        link = '<a href="/x">Go</a>'
        for label, style, body in (
                ("hidden and shown by its rules",
                 "<style>.menu{display:none}.menu.is-open{display:block}</style>",
                 f'<div class="menu is-open" aria-hidden="true">{link}</div>'),
                ("an inline style shows it",
                 "<style>#m{display:none}</style>",
                 f'<div id="m" style="display:block" aria-hidden="true">{link}</div>'),
                ("visible again below it",
                 "<style>.off{visibility:hidden}.off a{visibility:visible}</style>",
                 f'<div class="off" aria-hidden="true">{link}</div>'),
                ("a conditional media query",
                 '<style media="screen and (max-width:600px)">.m{display:none}</style>',
                 f'<div class="m" aria-hidden="true">{link}</div>'),
                ("not CSS", '<style type="text/x-template">.m{display:none}</style>',
                 f'<div class="m" aria-hidden="true">{link}</div>'),
                ("holds only without scripts",
                 "<style>html:not(.js) .m{display:none}.no-js .n{display:none}</style>",
                 f'<div class="m n" aria-hidden="true">{link}</div>')):
            with self.subTest(label):
                self.assertEqual(self.verdicts(body, style), [FAIL])

    def test_a_plain_hiding_rule_still_makes_a_review(self):
        self.assertEqual(self.verdicts(
            '<div class="m" aria-hidden="true"><a href="/x">Go</a></div>',
            '<style media="screen">.m{display:none}</style>'), [NEEDS_REVIEW])


class TestAddressTables(unittest.TestCase):
    def test_embedded_and_special_purpose_addresses(self):
        for url, want in (("http://[2002:7f00:1::]/", "loopback"),
                          ("http://[2002:5db8:d70e::]/", "public"),
                          ("http://[64:ff9b::7f00:1]/", "loopback"),
                          ("http://[64:ff9b::a00:1]/", "private"),
                          ("http://192.0.2.5/", "private"),
                          ("http://[2001:db8::1]/", "private"),
                          ("http://[3fff::1]/", "private"),
                          ("http://[2606:4700::1111]/", "public")):
            with self.subTest(url=url):
                self.assertEqual(F.address_class(url), want)


@unittest.skipUnless(HAVE_BROWSER, _WHY)
class TestRenderedRuns(unittest.TestCase):
    def capture(self, body, head=""):
        site = _Site({"/": send(page(body, head).encode())})
        self.addCleanup(site.stop)
        fr = F.fetch(site.base + "/", render=True)
        return fr

    def test_an_open_popover_is_evaluated(self):
        fr = self.capture(f'<div popover="manual" id="banner">{CONTENT}</div>'
                          '<script>banner.showPopover()</script>')
        self.assertEqual(failed_rules(fr.html, fr.provenance_attr), sorted(NAME_RULES))

    def test_a_closed_popover_is_not(self):
        fr = self.capture(f'<div popover="manual">{CONTENT}</div>')
        self.assertEqual(failed_rules(fr.html, fr.provenance_attr), [])

    def test_a_stylesheet_that_shows_hidden_content_wins(self):
        fr = self.capture(f'<div hidden class="d-block">{CONTENT}</div>',
                          "<style>.d-block{display:block!important}</style>")
        self.assertEqual(failed_rules(fr.html, fr.provenance_attr), sorted(NAME_RULES))

    def test_hidden_inside_the_container_is_a_review(self):
        fr = self.capture('<nav aria-hidden="true"><div class="oc"><a href="/x">Go</a>'
                          '</div></nav>', "<style>.oc{visibility:hidden}</style>")
        found = findings(fr.html, "bb-aria-hidden-focus", fr.provenance_attr)
        self.assertEqual([(f.verdict, f.impact) for f in found],
                         [(NEEDS_REVIEW, MODERATE)])
        self.assertIn("inside it", found[0].message)

    def test_slotted_content_is_read_where_it_renders(self):
        script = ("<script>customElements.define('my-el', class extends HTMLElement {"
                  "connectedCallback(){ this.attachShadow({mode:'open'}).innerHTML ="
                  " '<div style=\"visibility:hidden\"><slot></slot></div>'; }});</script>")
        fr = self.capture('<div aria-hidden="true" id="ah"><my-el><a href="/f" '
                          'style="visibility:visible">F</a></my-el></div>' + script)
        self.assertEqual([f.verdict for f in findings(fr.html, "bb-aria-hidden-focus",
                                                      fr.provenance_attr)], [FAIL])

    def test_text_shown_again_inside_svg_names_the_button(self):
        # Chromium 141 names this button "I" (and a button holding a plain
        # SVG <text> nothing). The stylesheet decides, so only the capture's
        # record can tell the rules.
        fr = self.capture('<button><svg class="h" width="20" height="20">'
                          '<text class="v" x="0" y="15">I</text></svg></button>',
                          "<style>.h{visibility:hidden}.v{visibility:visible}</style>")
        self.assertEqual(findings(fr.html, "bb-button-name", fr.provenance_attr), [])


if __name__ == "__main__":
    unittest.main()
