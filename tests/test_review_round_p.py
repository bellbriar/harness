"""The independent review of Part O round 3 and Part P (PR1, PR2).

Each test reproduces a finding of that review and checks the fix. The run
shape findings that need a build server or a site (PR1-1, PR1-3, PR1-4)
are in test_run_shape.py, and the bundle rules (PR1-2) in
test_canonicalization.py ("Pages", §9.6).

  PR2-1  a slotted node's locator, through a forwarded slot
  PR2-2  nested declarative roots: linear, and the depth budget first
  PR2-3  a rendered run of a page served as XML reads it as XML
  PR2-4  entity amplification in XHTML: a budget, as Chromium has one
  PR2-5  XHTML elements in another default namespace, or none
  PR2-6  <noscript> children are elements in an XML document
  PR2-7  a capture's elements inside <menuitem> stay inside it
  PR2-8  slot assignment in tree order, fallback slots included
  PR2-9  the first meta refresh a browser can read decides
  PR2-10 locators hold at most locator.MAX_STEPS steps

And the review of those fixes (PR3; PR3-1 and PR3-4 are in
test_run_shape.py and test_canonicalization.py):

  PR3-2  comments in the light DOM are not slotted
  PR3-3  the soonest meta refresh decides
  PR3-5  a fragment variant of a rendered page is one page
  PR3-6  a page cannot make itself XML by redefining contentType
  PR3-7  locators count names as type selectors match them
  PR3-8  entity nesting through a memo; references in comments are none
  PR3-9  roots inside left-out content are not read
"""
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bellbriar_harness import fetch as F                        # noqa: E402
from bellbriar_harness import html5, locator, xhtml              # noqa: E402
from bellbriar_harness.checks_static import (PageContext,       # noqa: E402
                                             TooDeeplyNested)
from bellbriar_harness.engine import load_rulebook, run_page    # noqa: E402
from tests.test_fetch_hardening import (HAVE_BROWSER, _WHY, _Site,  # noqa: E402
                                        send)

RB = load_rulebook()
PAGE = ('<!doctype html><html lang="en"><head><title>T</title></head><body>'
        '<main><h1>T</h1>{}</main></body></html>')
XPAGE = ('<?xml version="1.0" encoding="utf-8"?>\n{doctype}<html xmlns="http://'
         'www.w3.org/1999/xhtml" lang="en"><head><title>T</title></head><body>'
         '<main><h1>T</h1>{body}</main></body></html>')


def fails(page, rule=None):
    return [(rr.rule_id, f.selector) for rr in page.results for f in rr.findings
            if f.verdict == "fail" and (rule is None or rr.rule_id == rule)]


class TestLocators(unittest.TestCase):
    def test_a_forwarded_slot(self):
        # PR2-1: x-outer's slot is a light child of x-inner, which passes
        # the link on into its own slot. The link is x-outer's child (and,
        # slotted, written by position: its siblings are not all at hand).
        html = PAGE.format(
            '<x-outer><template shadowrootmode="open"><x-inner><template '
            'shadowrootmode="open"><div><slot></slot></div></template><slot>'
            '</slot></x-inner></template><a href="/cart"></a></x-outer>'
            '<x-inner><a href="/home"></a></x-inner>')
        got = fails(run_page(html, "p.html", RB), "bb-link-name")
        self.assertIn(("bb-link-name",
                       ["body > main > x-outer > a:nth-child(1)"]), got)
        self.assertNotIn(("bb-link-name", ["x-inner > a:nth-child(1)"]), got)

    def test_noscript_children_are_elements_in_xml(self):
        # PR2-6: in an XML document <noscript>'s children are in the DOM,
        # so their ids are counted.
        doc = XPAGE.format(doctype="", body='<noscript><p id="n">no js</p>'
                           '</noscript><a id="n" href="/x"></a>')
        ctx = PageContext.parse(doc.encode(), path="p.xhtml")
        link = ctx.soup.find("a", href="/x")
        self.assertNotEqual(ctx.locator(link), ["#n"])
        html = PAGE.format('<noscript><p id="n">no js</p></noscript>'
                           '<a id="n" href="/x"></a>')
        ctx = PageContext.parse(html)                  # HTML: text there
        self.assertEqual(ctx.locator(ctx.soup.find("a", href="/x")), ["#n"])

    def test_menuitem_is_no_void_element(self):
        # PR2-7: a serialized DOM read back keeps <menuitem>'s children.
        soup = html5.BudgetSoup('<div><menuitem><a href="/m"></a></menuitem>'
                                '<a href="/n"></a><br><img src="x"></div>',
                                on_duplicate_attribute="ignore")
        self.assertEqual(soup.find("a", href="/m").parent.name, "menuitem")
        self.assertEqual(soup.find("img").parent.name, "div")
        self.assertEqual(soup.find("br").contents, [])

    def test_a_cap_on_steps(self):
        # PR2-10: a deep element has no locator rather than one as long as
        # the page is deep.
        for depth, located in ((90, True), (120, False)):
            html = PAGE.format("<div>" * depth + '<a href="/x"></a>')
            sel = fails(run_page(html, "p.html", RB), "bb-link-name")[0][1]
            self.assertEqual(sel is not None, located, depth)
            if sel:
                self.assertLessEqual(sum(s.count(">") + 1 for s in sel),
                                     locator.MAX_STEPS)


class TestShadowRoots(unittest.TestCase):
    def test_nested_roots_are_read_in_linear_time(self):
        # PR2-2: 16,000 nested declarative roots took 136 s before the depth
        # budget could refuse the page.
        def page(n):
            return ("<!doctype html><html lang=en><head><title>t</title></head>"
                    "<body>" + '<x-a><template shadowrootmode="open">' * n
                    + "<p>x</p>")
        t = time.monotonic()
        PageContext.parse(page(3000))
        with self.assertRaises(TooDeeplyNested):
            PageContext.parse(page(16000))
        self.assertLess(time.monotonic() - t, 20)

    def test_slots_are_assigned_in_tree_order(self):
        # PR2-8: the nodes for slot b go to the first slot named b, inside
        # slot a's fallback, which a's own node hides: not rendered.
        html = PAGE.format(
            '<x-n><template shadowrootmode="open"><slot name="a"><slot '
            'name="b"></slot></slot><slot name="b"></slot></template><span '
            'slot="a">A</span><span slot="b"><a href="/hidden"></a></span>'
            '</x-n>')
        self.assertEqual(fails(run_page(html, "p.html", RB), "bb-link-name"),
                         [])
        # Without a node for slot a, its fallback shows, slot b with it.
        shown = html.replace('<span slot="a">A</span>', "")
        self.assertEqual(len(fails(run_page(shown, "p.html", RB),
                                   "bb-link-name")), 1)


class TestXML(unittest.TestCase):
    LOL = ('<!ENTITY a0 "lol">' + "".join(
        f'<!ENTITY a{i} "{("&a%d;" % (i - 1)) * 10}">' for i in range(1, 10)))

    def doc(self, subset, body):
        return XPAGE.format(doctype=f"<!DOCTYPE html [{subset}]>\n",
                            body=body).encode()

    def test_entity_amplification(self):
        # PR2-4: past a million characters and five times the page (libxml2's
        # limit), an XML error to Chromium, and not evaluated here; read
        # before an attribute can be blown up.
        for body in ("<p>&a6;</p>", '<p title="&a6;">t</p>',
                     "<p>" + "&e;" * 70000 + "</p>"):
            with self.subTest(body=body[:20]), \
                    self.assertRaisesRegex(xhtml.NotWellFormed, "entities"):
                xhtml.parse(self.doc(self.LOL + '<!ENTITY e "' + "x" * 90 + '">',
                                     body).decode())
        xhtml.parse(self.doc(self.LOL, "<p>&a4;</p>").decode())   # 30,000
        nested = ('<!ENTITY e0 "x">' + "".join(
            f'<!ENTITY e{i} "&e{i - 1};">' for i in range(1, 40)))
        xhtml.parse(self.doc(nested, "<p>&e38;</p>").decode())
        with self.assertRaisesRegex(xhtml.NotWellFormed, "nest"):
            xhtml.parse(self.doc(nested, "<p>&e39;</p>").decode())

    def test_elements_in_another_namespace_are_not_html(self):
        # PR2-5: Chromium makes these plain elements: no image, no link.
        body = ('<div xmlns="urn:example:widgets"><img src="a.png"/><a '
                'href="/x"></a><button/></div><div xmlns=""><img src="b.png"/>'
                '</div>')
        page = run_page(XPAGE.format(doctype="", body=body).encode(),
                        "p.xhtml", RB)
        self.assertEqual(fails(page), [])
        soup = xhtml.parse(XPAGE.format(doctype="", body=body))
        self.assertEqual(sorted({el.name for el in soup.find_all(True)
                                 if el.name.startswith("ns:")}),
                         ["ns:a", "ns:button", "ns:div", "ns:img"])

    def test_the_root_is_named_without_a_made_up_prefix(self):
        with self.assertRaisesRegex(xhtml.NotAPage, "<feed>"):
            xhtml.parse('<feed xmlns="http://www.w3.org/2005/Atom"/>')

    @unittest.skipUnless(HAVE_BROWSER, _WHY)
    def test_a_rendered_run_reads_xml_as_xml(self):
        # PR2-3: a capture is read back as HTML, which folds XML's case.
        doc = XPAGE.format(doctype="", body='<img ALT="Acme" src="l.png"/>'
                           '<A href="/up"></A>').replace(' lang="en"',
                                                         ' xml:lang="en"')
        site = _Site({"/x": send(doc.encode(), ctype="application/xhtml+xml")})
        self.addCleanup(site.stop)
        fr = F.fetch(site.base + "/x")
        self.assertEqual((fr.mode, fr.reader), ("server", "xml"))
        self.assertEqual(fr.fallback_reason, F.XML_PAGE_REASON)
        page = run_page(fr.html, fr.final_url, RB, reader=fr.reader)
        self.assertEqual(sorted({r for r, _ in fails(page)}), ["bb-img-alt"])
        with self.assertRaisesRegex(F.FetchError, "an XML document"):
            F.fetch(site.base + "/x", render=True)


class TestRoundThree(unittest.TestCase):
    def test_comments_are_not_slotted(self):
        # PR3-2: Lit, Vue and Angular leave comments among a host's
        # children; only elements and text are slotted, so the fallback
        # still names the button.
        html = PAGE.format(
            '<my-button><template shadowrootmode="open"><button><slot>Close'
            '</slot></button></template><!--lit-part--><?x y?><!--/lit-part-->'
            '</my-button>')
        self.assertEqual(fails(run_page(html, "p.html", RB)), [])

    def test_the_soonest_refresh_decides(self):
        # PR3-3: Chromium keeps the soonest refresh it can read.
        def refresh(*contents):
            metas = "".join(f'<meta http-equiv="refresh" content="{c}">'
                            for c in contents)
            html = PAGE.format("").replace("</head>", metas + "</head>")
            return fails(run_page(html, "p.html", RB), "bb-meta-refresh")
        self.assertEqual(len(refresh("100000; url=a.html", "2; url=b.html")),
                         1)
        self.assertEqual(refresh("5", "0; url=a.html"), [])

    def test_names_as_type_selectors_match_them(self):
        # PR3-7: `a` matches an <a> in any namespace.
        doc = XPAGE.format(doctype="", body='<p><a xmlns="" href="/y">y</a>'
                           '<a href="/z">z</a></p>')
        ctx = PageContext.parse(doc.encode(), path="p.xhtml")
        link = ctx.soup.find("a", href="/z")
        self.assertEqual(ctx.locator(link), ["body > main > p > a:nth-child(2)"])

    def test_entity_nesting_through_the_memo(self):
        # PR3-8: an entity first expanded near the top is still judged by
        # its whole nesting when reached deeper; a reference in a comment,
        # CDATA or a processing instruction is none.
        chain = ('<!ENTITY e0 "x">' + "".join(
            f'<!ENTITY e{i} "&e{i - 1};">' for i in range(1, 30)))
        deep = chain + "".join(f'<!ENTITY d{i} "&d{i - 1};">'
                               for i in range(1, 15)).replace(
                                   "&d0;", "&e29;", 1)
        doc = TestXML().doc(deep, "<p>&e29;</p><p>&d14;</p>").decode()
        with self.assertRaisesRegex(xhtml.NotWellFormed, "nest"):
            xhtml.parse(doc)
        big = '<!ENTITY b "' + "x" * 5000 + '">'
        body = "<!-- " + "&b;" * 400 + " --><p>ok</p>"
        xhtml.parse(TestXML().doc(big, body).decode())

    def test_roots_in_left_out_content_are_not_read(self):
        # PR3-9: 400 nested hosts with empty roots over 50,000 elements took
        # 13 s; what no slot shows is read once.
        html = ("<!doctype html><html lang=en><head><title>t</title></head>"
                "<body>" + '<x-b><template shadowrootmode="open"></template>'
                * 400 + "<i>x</i>" * 50000 + "</body></html>")
        t = time.monotonic()
        PageContext.parse(html)
        self.assertLess(time.monotonic() - t, 8)


@unittest.skipUnless(HAVE_BROWSER, _WHY)
class TestRoundThreeRendered(unittest.TestCase):
    def test_a_fragment_variant_is_one_page(self):
        # PR3-5: each capture names its stamp afresh, so captures of one
        # page are compared with the stamp's name written one way.
        import json
        import shutil
        import tempfile
        from tests.test_run_shape import run
        site = _Site({"/": send(PAGE.format("<p>x</p>").encode())})
        self.addCleanup(site.stop)
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        code, _, err = run("--url", site.base + "/#/a", "--url",
                           site.base + "/#/b", "--json", d / "r.json",
                           "--fail-on", "never")
        self.assertEqual(code, 0, err)
        report = json.loads((d / "r.json").read_text(encoding="utf-8"))
        self.assertEqual(len(report["pages"]), 1)
        self.assertIn("is the same page as", err)

    def test_content_type_is_the_servers_word(self):
        # PR3-6: an HTML page that redefines document.contentType is still
        # captured as rendered.
        body = PAGE.format(
            '<div id="r"></div><script>Object.defineProperty(Document.'
            'prototype, "contentType", {get: () => "application/xml"});'
            'document.getElementById("r").innerHTML = "<button></button>";'
            '</script>').encode()
        site = _Site({"/": send(body)})
        self.addCleanup(site.stop)
        fr = F.fetch(site.base + "/")
        self.assertEqual((fr.mode, fr.reader), ("rendered", "dom"))
        page = run_page(fr.html, fr.final_url, RB, reader=fr.reader,
                        provenance_attr=fr.provenance_attr)
        self.assertIn("bb-button-name", {r for r, _ in fails(page)})


class TestMetaRefresh(unittest.TestCase):
    def test_the_first_readable_one_decides(self):
        # PR2-9: a browser skips a refresh it cannot read.
        for first in ('<meta http-equiv="refresh" content="">',
                      '<meta http-equiv="refresh" content="soon">',
                      '<meta http-equiv="refresh">'):
            html = PAGE.format("").replace(
                "</head>", first + '<meta http-equiv="refresh" content="1; '
                'url=next.html"></head>')
            with self.subTest(first=first):
                self.assertEqual(len(fails(run_page(html, "p.html", RB),
                                           "bb-meta-refresh")), 1)
        html = PAGE.format("").replace(
            "</head>", '<meta http-equiv="refresh" content="0; url=a.html">'
            '<meta http-equiv="refresh" content="5"></head>')
        self.assertEqual(fails(run_page(html, "p.html", RB),
                               "bb-meta-refresh"), [])


if __name__ == "__main__":
    unittest.main()
