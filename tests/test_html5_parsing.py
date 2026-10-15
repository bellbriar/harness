"""Part O, P2-05: a page's own HTML is parsed as a browser parses it.

html.parser, which parsed files and server HTML before, nests whatever it
sees: `<li>a<li><a href=/x></a>` put the empty link inside the first item,
so a minified page that omits optional end tags under-reported, and
`<svg><p>`, `<table><div>`, `<template>` rows and `<select>` content came
out unlike the browser's DOM. Files and server HTML now go through
bellbriar_harness.html5 (JustHTML's WHATWG tree construction, copied into
BeautifulSoup); a rendered capture, which is the browser's own
serialization of the live DOM, is still read back as it was.

The WPT tree-construction suite (tests/data/wpt-tree-construction) runs
through the copy, so a parser upgrade that changes the trees fails here.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bs4.element import Comment, Doctype, NavigableString, Tag  # noqa: E402

from bellbriar_harness import html5                              # noqa: E402
from bellbriar_harness.checks_static import PageContext          # noqa: E402
from bellbriar_harness.engine import load_rulebook, run_page     # noqa: E402
from bellbriar_harness.model import FAIL                         # noqa: E402

WPT = ROOT / "tests" / "data" / "wpt-tree-construction"
PREFIX = {"http://www.w3.org/2000/svg": "svg ",
          "http://www.w3.org/1998/Math/MathML": "math "}
FOREIGN_ATTRS = {"xlink:actuate", "xlink:arcrole", "xlink:href", "xlink:role",
                 "xlink:show", "xlink:title", "xlink:type", "xml:lang",
                 "xml:space", "xmlns:xlink"}
#: Cases JustHTML 3.13 builds unlike the test, by their #data. Each is a
#: corner no rule depends on; if a parser upgrade fixes one, drop it here.
KNOWN = {
    # U+FFFD inside <svg> should set frameset-ok to "not ok".
    "<!doctype html><svg>&#xFFFD;</svg><frameset><frame>",
    # CDATA at an HTML integration point is text in the spec; html5 makes
    # it the comment Chromium 141 makes of it (OR2-9; TestAsChromiumBuildsIt).
    "<svg><title><![CDATA[x]]>", "<svg><foreignobject><![CDATA[x]]>",
    "<math><mtext><![CDATA[x]]>",
    # <search> is special in the spec, not in Chromium 141's parser, and
    # html5 follows Chromium (TestAsChromiumBuildsIt): a <dt> inside it
    # closes the outer <dd>, a </a> takes it along.
    "<!doctype html><dd>a<search><dt>b",
    "<!doctype html><a><search>x</a>y", "<!doctype html><a><search>x<p>y<a>z",
    "<!doctype html><li>a<search><li>b", "<!doctype html><x><search></x>y",
}


def read_dat(path: Path):
    tests, cur, key = [], None, None
    # Bytes, so a carriage return in a test stays one (read_text would
    # turn it into a line break).
    for line in path.read_bytes().decode("utf-8").split("\n"):
        if line.startswith("#") and line[1:] in (
                "data", "errors", "new-errors", "document-fragment",
                "script-off", "script-on", "document", "description"):
            key = line[1:]
            if key == "data":
                cur = {}
                tests.append(cur)
            if cur is not None:
                cur.setdefault(key, [])
            continue
        if cur is not None and key is not None:
            cur[key].append(line)
    for t in tests:
        doc = t.get("document", [])
        while doc and doc[-1] == "":
            doc.pop()
        yield {"data": "\n".join(t.get("data", [])), "document": doc,
               "fragment": "document-fragment" in t,
               "script_off": "script-off" in t}


_LIST_ATTRS = {"class", "accesskey", "dropzone", "rel", "rev", "headers",
               "accept-charset", "archive", "sizes", "sandbox", "for"}


def _items(lines: list[str]) -> list[str]:
    """The expected tree's nodes, normalized as BeautifulSoup holds them:
    a whitespace-only text node as one marker (BeautifulSoup collapses
    them), comments stripped, the doctype left out."""
    nodes: list[str] = []
    for line in lines:
        if line.startswith("| ") or not nodes:
            nodes.append(line)
        else:
            nodes[-1] += "\n" + line
    out = []
    for n in nodes:
        body = n[2:]
        indent = len(body) - len(body.lstrip(" "))
        content = body[indent:]
        if content.startswith("<!DOCTYPE"):
            continue
        if content.startswith('"') and content.endswith('"'):
            if not content[1:-1].strip("\t\n\x0c\r "):
                content = '"<ws>"'
        elif content.startswith("<!--") and content.endswith("-->"):
            content = "<!-- " + content[4:-3].strip() + " -->"
            if content.startswith("<!-- ?"):
                content = "<!-- ?PI -->"
        elif content.startswith("<?") and content.endswith(">"):
            # This WPT revision has processing instructions (and bogus
            # comments for malformed ones); Chromium 141 makes each a
            # comment of its own text (TestProcessingInstructions checks
            # it), so only the node's place is compared here.
            content = "<!-- ?PI -->"
        elif "=" in content and not content.startswith("<"):
            name, _, value = content.partition("=")
            if name in _LIST_ATTRS:
                content = f'{name}="{" ".join(value[1:-1].split())}"'
        out.append(" " * indent + content)
    return out


def _serialize(node, depth: int, out: list[str]) -> None:
    pad = "  " * depth
    for c in node.children:
        if isinstance(c, Doctype):
            continue
        if isinstance(c, Comment):
            text = str(c).strip()
            out.append(f"{pad}<!-- ?PI -->" if text.startswith("?")
                       else f"{pad}<!-- {text} -->")
        elif isinstance(c, NavigableString):
            text = str(c)
            out.append(f'{pad}"<ws>"' if not text.strip("\t\n\x0c\r ")
                       else f'{pad}"{text}"')
        elif isinstance(c, Tag):
            pre = PREFIX.get(c.namespace, "")
            out.append(f"{pad}<{pre}{c.name}>")
            attrs = []
            for k, v in c.attrs.items():
                v = " ".join(v) if isinstance(v, list) else v
                if k in _LIST_ATTRS:
                    v = " ".join(v.split())
                if pre and k in FOREIGN_ATTRS:
                    k = k.replace(":", " ")
                attrs.append((k, v))
            for k, v in sorted(attrs):
                out.append(f'{pad}  {k}="{v}"')
            if c.name == "template" and not pre:
                out.append(f"{pad}  content")
                _serialize(c, depth + 2, out)
            else:
                _serialize(c, depth + 1, out)


class TestWPTTreeConstruction(unittest.TestCase):
    def test_every_document_case(self):
        files = sorted(WPT.glob("*.dat"))
        self.assertGreater(len(files), 50)
        ran = 0
        for f in files:
            for i, t in enumerate(read_dat(f)):
                if t["fragment"] or t["script_off"] or t["data"] in KNOWN:
                    continue
                ran += 1
                got: list[str] = []
                _serialize(html5.parse(t["data"]), 0, got)
                with self.subTest(file=f.name, case=i, data=t["data"][:80]):
                    self.assertEqual("\n".join(got).split("\n"),
                                     "\n".join(_items(t["document"])).split("\n"))
        self.assertGreater(ran, 1500)


#: The DOM Chromium 141 builds, recorded (tests/data/chromium-141-trees.json):
#: every WPT document above, and <select> in twenty contexts.
CHROMIUM_TREES = ROOT / "tests" / "data" / "chromium-141-trees.json"
#: Inputs html5.parse builds unlike Chromium 141, by input. Chromium departs
#: from the spec in each (or the spec moved on): U+FFFD before <frameset>
#: leaves frameset-ok; it keeps <command> text out of the element; its
#: adoption agency stops earlier on webkit02's case; a lone "<?" is a
#: comment; and a </p> inside a <select> in a <p> inserts an empty <p>
#: (JustHTML ignores the end tag there). Each is a corner of the parser no
#: field page or fixture contains; none moves a link, a control, a name or
#: an aria-hidden boundary in its case.
CHROMIUM_KNOWN = {
    "<?",
    "<!doctype html>\ufffd<frameset><frame>",
    "<!doctype html>&#xFFFD;<frameset><frame>",
    "<!doctype html>&#0;<frameset><frame>",
    "<!DOCTYPE html><body><command>A",
    "<b><em><foo><foo><foo><aside></b></em>",
    "<!doctype html><p><select></p></select>after",
}
_DUMP_LIST = {"class", "rel", "headers", "accesskey", "dropzone", "rev",
              "accept-charset", "archive", "sizes", "sandbox", "for"}


def chromium_style_tree(html: str) -> list[str]:
    """html5.parse's tree in the form the fixture records Chromium's."""
    import json
    out: list[str] = []

    def attrs(tag) -> str:
        pairs = []
        for k, v in tag.attrs.items():
            v = " ".join(v) if isinstance(v, list) else v
            if k in _DUMP_LIST:
                v = " ".join(v.split())
            pairs.append(f'{k}="{v}"')
        return " ".join(sorted(pairs))

    def walk(node, depth):
        for c in node.children:
            pad = "  " * depth
            if isinstance(c, Doctype):
                out.append(pad + "<!DOCTYPE>")
            elif isinstance(c, Comment):
                out.append(pad + "<!---->")
            elif isinstance(c, NavigableString):
                t = str(c)
                out.append(pad + ('"<ws>"' if not t.strip("\t\n\x0c\r ")
                                  else json.dumps(t, ensure_ascii=False)))
            elif isinstance(c, Tag):
                pre = PREFIX.get(c.namespace, "")
                a = attrs(c)
                out.append(pad + f"<{pre}{c.name}{(' ' + a) if a else ''}>")
                if c.name == "template" and not pre:
                    out.append(pad + "  content")
                    walk(c, depth + 2)
                else:
                    walk(c, depth + 1)
    walk(html5.parse(html), 0)
    merged: list[str] = []
    for line in out:
        if merged and line == merged[-1] and line.strip() == '"<ws>"':
            continue
        merged.append(line)
    return merged


class TestAsChromiumBuildsIt(unittest.TestCase):
    """OR-7: html5.parse against the DOM Chromium 141 builds. A <select>
    inside a <p>, <a>, <button>, <dt> or <dd> was torn apart (two phantom
    empty links, an <hr> separator ending the paragraph): <select> is now
    a scope boundary, as in the current spec (html5)."""

    def test_the_recorded_trees(self):
        import json
        data = json.loads(CHROMIUM_TREES.read_text(encoding="utf-8"))
        seen = set()
        for case in data["cases"]:
            html = case["input"]
            got = chromium_style_tree(html)
            if html in CHROMIUM_KNOWN:
                seen.add(html)
                with self.subTest(known=html[:60]):
                    self.assertNotEqual(got, case["tree"],
                                        "now as Chromium builds it: drop it "
                                        "from CHROMIUM_KNOWN")
                continue
            with self.subTest(group=case["group"], input=html[:80]):
                self.assertEqual(got, case["tree"])
        self.assertEqual(len(data["cases"]), 2015)
        self.assertEqual(seen, CHROMIUM_KNOWN)

    def test_select_in_a_paragraph_or_a_link(self):
        # Chromium 141: one link holding the select and the inner link; the
        # <hr> separator stays in the select, the paragraph goes on after.
        self.assertEqual(fails(page('<a href="/x"><select aria-label="S">'
                                    '<a href="/y">y</a></select></a>')), [])
        soup = html5.parse('<p>Pick: <select aria-label="Size"><option>S<hr>'
                           '<option>M</select> then <a href="/x">next</a></p>')
        self.assertEqual(soup.find("a").find_parent("p").name, "p")
        self.assertEqual(len(soup.find("select").find_all("option")), 2)


class TestProcessingInstructions(unittest.TestCase):
    def test_as_chromium_keeps_them(self):
        # Measured: Chromium 141 makes a comment of everything from the "?"
        # to the first ">".
        for source, want in (("<?COM--MENT?>", "?COM--MENT?"),
                             ('<?xml version="1.0"?><p>', '?xml version="1.0"?'),
                             ("<?php echo 1 ?>", "?php echo 1 ?"),
                             ("<?a b c?>", "?a b c?"), ("<?>", "?"),
                             ("<? x>", "? x"), ("<?a?b>", "?a?b")):
            with self.subTest(source):
                got = [str(c) for c in html5.parse(source).find_all(
                    string=lambda t: isinstance(t, Comment))]
                self.assertEqual(got, [want])


RB = load_rulebook()


def page(body: str, head: str = "") -> str:
    return ('<!doctype html><html lang="en"><head><title>T</title>'
            f'{head}</head><body><main><h1>T</h1>{body}</main></body></html>')


def xpage(body: str) -> str:
    """page(), as an XHTML document: the XML reader, like a browser, shows
    a page only under XHTML's namespace."""
    return ('<html xmlns="http://www.w3.org/1999/xhtml" lang="en"><head>'
            f'<title>T</title></head><body><main><h1>T</h1>{body}</main>'
            '</body></html>')


def fails(html, path="x.html", **kw) -> list:
    p = run_page(html, path, RB, **kw)
    return sorted(f.rule_id for rr in p.results for f in rr.findings
                  if f.verdict == FAIL)


class TestBrowserTrees(unittest.TestCase):
    """What used to differ from the browser's DOM, and the verdict it moved."""

    def test_omitted_end_tags(self):
        # The empty link is in the second item, outside the aria-hidden one.
        self.assertEqual(fails(page('<ul><li aria-hidden="true">Decor'
                                    '<li><a href="/shop"></a></ul>')),
                         ["bb-link-name"])
        # <p> closes before <div>: the button is not inside the paragraph.
        soup = html5.parse(page("<p>Note<div><button></button></div>"))
        self.assertIsNone(soup.find("button").find_parent("p"))
        # A cell closes the previous one.
        soup = html5.parse(page('<table><tr><td aria-hidden="true">x<td>'
                                '<a href="/x"><img src="a.png"></a></table>'))
        self.assertIsNone(soup.find("a").find_parent(attrs={
            "aria-hidden": True}))

    def test_template_rows_stay_inert(self):
        html = page('<table><tbody><template x-for="r in rows"><tr><td>'
                    '<a href="/x"></a></td></tr></template></tbody></table>')
        self.assertEqual(fails(html), [])

    def test_noscript_content_is_text(self):
        html = ('<!doctype html><html lang="en"><head><title>T</title>'
                '<noscript><img src="/pixel.gif"></noscript></head><body>'
                '<main><h1>T</h1></main></body></html>')
        self.assertEqual(fails(html), [])
        self.assertIsNone(html5.parse(html).find("img"))

    def test_select_keeps_its_content(self):
        soup = html5.parse(page('<select><option><img src="s.png">A</option>'
                                '</select>'))
        self.assertIsNotNone(soup.find("option").find("img"))

    def test_search_and_dialog_close_a_paragraph(self):
        for tag in ("search", "dialog open"):
            soup = html5.parse(page(f"<p>Note<{tag}><button>Go</button>"))
            self.assertIsNone(soup.find("button").find_parent("p"), tag)

    def test_foreign_content(self):
        soup = html5.parse(page('<svg viewBox="0 0 1 1"><p>out</p></svg>'))
        self.assertIsNone(soup.find("p").find_parent("svg"))
        svg = soup.find("svg")
        self.assertEqual(svg.namespace, "http://www.w3.org/2000/svg")
        self.assertEqual(svg.get("viewBox"), "0 0 1 1")
        # HTML inside foreignObject plays; a <video> directly in SVG is no
        # HTML media element.
        self.assertIn("bb-media-autoplay", fails(page(
            '<svg><foreignObject><video autoplay src="a.mp4"></video>'
            '</foreignObject></svg>')))
        self.assertNotIn("bb-media-autoplay", fails(page(
            '<svg><video autoplay src="a.mp4"></video></svg>')))

    def test_nested_links_and_buttons_split(self):
        soup = html5.parse(page('<a href="/a">A<a href="/b">B</a></a>'
                                '<button>1<button>2</button></button>'))
        self.assertIsNone(soup.find("a", href="/b").find_parent("a"))
        self.assertEqual(len(soup.find_all("button")), 2)
        self.assertIsNone(soup.find_all("button")[1].find_parent("button"))

    def test_image_is_img_and_text_is_normalized(self):
        soup = html5.parse(page('<image src="i.png"><a href="/c">a\r\nb</a>'))
        self.assertIsNotNone(soup.find("img"))
        self.assertEqual(soup.find("a").get_text(), "a\nb")

    def test_processing_instruction_is_a_comment(self):
        # Chromium 141 builds `<?php ... ?>` as a comment: the link is empty.
        html = page('<a href="/"><?php echo $label ?></a>')
        self.assertIn("bb-link-name", fails(html))

    def test_first_of_two_attributes_wins(self):
        soup = html5.parse(page('<img alt="" alt="Logo" src="l.png">'))
        self.assertEqual(soup.find("img")["alt"], "")


class TestLines(unittest.TestCase):
    def test_lines_are_the_start_tags(self):
        html = ('<!doctype html>\n<html lang="en">\n<head><title>T</title>'
                '</head>\n<body>\n<p>one\n<p>two\n<table>\n<div id="f">x</div>'
                '\n<tr><td>c</td></tr></table>\n<b>1<p id="q">2</b>3\n')
        soup = html5.parse(html)
        self.assertEqual(soup.find("html").sourceline, 2)
        self.assertEqual([p.sourceline for p in soup.find_all("p")][:2], [5, 6])
        self.assertEqual(soup.find(id="f").sourceline, 8)     # foster-parented
        self.assertIsNone(soup.find("tbody").sourceline)      # implied
        clone = soup.find(id="q").find("b")                   # adoption clone
        self.assertEqual(clone.sourceline, 10)

    def test_finding_lines_match_the_markup(self):
        html = page('\n\n<a href="/x"></a>')
        p = run_page(html, "x.html", RB)
        lines = [f.line for rr in p.results for f in rr.findings
                 if rr.rule_id == "bb-link-name"]
        self.assertEqual(lines, [3])


class TestDepth(unittest.TestCase):
    def test_chromium_depth_limit(self):
        # Measured in Chromium 141: an element inserted while more than 512
        # elements are open goes to the current node's parent.
        html = ("<!doctype html><html><head></head><body>"
                + "".join(f'<div id="d{i}">' for i in range(1, 601)) + "x")
        soup = html5.parse(html)

        def depth(t):
            n = 0
            while t.parent is not None and t.parent.name != "[document]":
                n, t = n + 1, t.parent
            return n
        got = {i: (depth(soup.find(id=f"d{i}")),
                   soup.find(id=f"d{i}").parent.get("id"))
               for i in (510, 511, 512, 600)}
        self.assertEqual(got, {510: (511, "d509"), 511: (512, "d510"),
                               512: (512, "d510"), 600: (512, "d510")})
        self.assertEqual(soup.find(id="d600").get_text(), "x")

    def test_deep_pages_stay_fast(self):
        import time
        t0 = time.monotonic()
        p = run_page(page("<div>" * 20000 + '<a href="/x"></a>'), "x.html", RB)
        self.assertLess(time.monotonic() - t0, 30)
        self.assertIn("bb-link-name", [rr.rule_id for rr in p.results
                                       for f in rr.findings])


class TestReaders(unittest.TestCase):
    def test_a_capture_keeps_the_live_nesting(self):
        # A script can put a <div> inside a <p>; the capture serializes
        # that, and reading it back keeps it.
        html = page('<p id="p"><div><a href="/x"></a></div></p>')
        ctx = PageContext.parse(html, provenance_attr="data-bb-p-0123456789abcdef")
        self.assertIsNotNone(ctx.soup.find("a").find_parent(id="p"))
        ctx = PageContext.parse(html, reader="dom")
        self.assertIsNotNone(ctx.soup.find("a").find_parent(id="p"))
        ctx = PageContext.parse(html)              # a page's own markup
        self.assertIsNone(ctx.soup.find("a").find_parent(id="p"))

    def test_xhtml_is_read_as_xml_reads_it(self):
        # `<script/>` closes itself in XML; in HTML it would swallow the page.
        body = ('<script src="a.js"/><a href="/x"></a>')
        self.assertIn("bb-link-name", fails(xpage(body), path="x.xhtml"))
        self.assertNotIn("bb-link-name", fails(xpage(body), path="x.html"))

    def test_another_vocabulary_keeps_its_prefix(self):
        # An RDF block's <dc:title> is not the page's <title>, and an <a> of
        # another namespace is no link.
        body = ('<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
                ' xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>Doc'
                '</dc:title><x:a xmlns:x="urn:x" href="/x"/></rdf:RDF>')
        doc = xpage(body).replace("<title>T</title>", "")
        p = run_page(doc, "x.xhtml", RB)
        self.assertEqual(p.parse_error, "")
        self.assertEqual(fails(doc, path="x.xhtml"), ["bb-page-title"])

    def test_bytes_are_decoded_as_a_browser_decodes_them(self):
        html = ('<!doctype html><html lang="en"><head><meta charset="koi8-r">'
                '<title>T</title></head><body><main><h1>T</h1>'
                '<a href="/x">' + chr(0x430) + '</a></main></body></html>')
        ctx = PageContext.parse(html.encode("koi8-r"))
        self.assertEqual(ctx.soup.find("a").get_text(), chr(0x430))


class TestDeclarativeShadowRoots(unittest.TestCase):
    """A browser attaches a declarative shadow root when it parses a file,
    so a file run now reads its content (Part O); before, only
    bb-media-autoplay did."""

    def test_content_and_slots_are_read(self):
        html = page('<my-el><template shadowrootmode="open"><button><slot>'
                    '</slot></button></template>Save</my-el><my-el><template '
                    'shadowrootmode="open"><button><slot></slot></button>'
                    '</template></my-el>')
        self.assertEqual(fails(html), ["bb-button-name"])

    def test_what_attaches_none_stays_inert(self):
        for label, body in (
                ("a second template",
                 '<my-el><template shadowrootmode="open"><b>x</b></template>'
                 '<template shadowrootmode="open"><a href="/x"></a></template>'
                 '</my-el>'),
                ("an invalid host",
                 '<li><template shadowrootmode="open"><a href="/x"></a>'
                 '</template></li>'),
                ("an unknown mode",
                 '<my-el><template shadowrootmode="sideways"><a href="/x">'
                 '</a></template></my-el>')):
            with self.subTest(label):
                self.assertEqual(fails(page(body)), [])

    def test_no_root_attaches_in_xhtml(self):
        body = ('<my-el><template shadowrootmode="open"><a href="/x"></a>'
                '</template></my-el>')
        self.assertEqual(fails(page(body), path="x.html"), ["bb-link-name"])
        p = run_page(xpage(body), "x.xhtml", RB)
        self.assertEqual(p.parse_error, "")
        self.assertEqual(fails(xpage(body), path="x.xhtml"), [])

    def test_root_text_is_rendered_text(self):
        soup = PageContext.parse(page(
            '<my-el><template shadowrootmode="open"><p>Hi</p></template>'
            '</my-el>')).soup
        self.assertIs(type(soup.find("p").string), NavigableString)


if __name__ == "__main__":
    unittest.main()
