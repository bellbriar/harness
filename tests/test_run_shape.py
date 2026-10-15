"""Part P, run shape: what a run measures and how it says where.

  A1  `bellbriar-eval ./dist --render` serves the build on loopback and
      evaluates each page's DOM after its scripts ran, so a client-rendered
      build (an empty shell to the static rules) is measured.
  A3  A run of many URLs: --url repeated, --urls FILE, --sitemap URL with
      --max-pages; one report and one bundle for the set, all on one host.
  A4  Every finding about an element carries a locator: CSS selectors, one
      per tree, that find it in the DOM the rules read (N23).

The bundle records each page's own capture (`pages[].fetch`) beside the
run's record of what it fetched (`fetch`); a verifier requires every page
record to name the host the statement binds, or loopback in a file run
(CANONICALIZATION §5 "Pages", tested in test_canonicalization.py).
"""
import contextlib
import gzip
import hashlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bellbriar_harness import cli                               # noqa: E402
from bellbriar_harness import fetch as F                        # noqa: E402
from bellbriar_harness.checks_static import PageContext         # noqa: E402
from bellbriar_harness.locator import css_ident                 # noqa: E402
from bellbriar_harness.serve import BuildServer, normalize_base  # noqa: E402
from tests.test_fetch_hardening import (HAVE_BROWSER, _WHY, _Site,  # noqa: E402
                                        redirect, send)

PAGE = ('<!doctype html><html lang="en"><head><title>T</title></head><body>'
        '<main><h1>T</h1>{}</main></body></html>')


def run(*argv, env=None):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
            mock.patch.dict(os.environ, env or {}):
        try:
            code = cli.main([str(a) for a in argv])
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


def locators(html, **kw):
    """{snippet start: locator} for every finding of a page."""
    from bellbriar_harness.engine import load_rulebook, run_page
    p = run_page(html, "x.html", load_rulebook(), **kw)
    return [(f.rule_id, f.selector) for rr in p.results for f in rr.findings]


class TestLocators(unittest.TestCase):
    """A4: each step picks one element; ids anchor where the tree has the
    id once (ignoring case, as a quirks-mode page compares them)."""

    def of(self, html, find):
        ctx = PageContext.parse(html)
        return ctx.locator(find(ctx.soup))

    def test_ids_anchor_and_steps_pick_one_child(self):
        html = PAGE.format('<nav id="top"><a href="/">A</a><a href="/b">B'
                           '</a></nav><ul><li>1</li><li><a href="/c">C</a>'
                           '</li></ul>')
        self.assertEqual(self.of(html, lambda s: s.find("a", href="/b")),
                         ["#top > a:nth-child(2)"])
        self.assertEqual(self.of(html, lambda s: s.find("a", href="/c")),
                         ["body > main > ul > li:nth-child(2) > a"])
        self.assertEqual(self.of(html, lambda s: s.find("html")), ["html"])

    def test_an_id_shared_ignoring_case_is_no_anchor(self):
        html = PAGE.format('<div id="Box"><a href="/x">x</a></div>'
                           '<div id="box">y</div>')
        self.assertEqual(self.of(html, lambda s: s.find("a")),
                         ["body > main > div:nth-child(2) > a"])

    def test_escapes(self):
        # CSSOM's "serialize an identifier", as CSS.escape writes it.
        for raw, want in (("1st", "\\31 st"), ("a.b c", "a\\.b\\ c"),
                          ("-", "\\-"), ("-1", "-\\31 "), ("x\x00", "x�"),
                          ("café", "café"), ("a:b", "a\\:b"),
                          ("x\x7f", "x\\7f ")):
            with self.subTest(raw):
                self.assertEqual(css_ident(raw), want)
        html = PAGE.format('<p id="1st">a</p><x-y.z>b</x-y.z>')
        self.assertEqual(self.of(html, lambda s: s.find(id="1st")),
                         ["#\\31 st"])
        self.assertEqual(self.of(html, lambda s: s.find("x-y.z")),
                         ["body > main > x-y\\.z"])

    def test_shadow_trees(self):
        html = PAGE.format(
            '<x-card id="c"><template shadowrootmode="open"><style>p{}</style>'
            '<div><slot></slot></div><div><button>Go</button></div></template>'
            '<p slot="none">left out</p><p id="lit">shown</p></x-card>')
        self.assertEqual(self.of(html, lambda s: s.find("button")),
                         ["#c", "div:nth-child(3) > button"])
        # Light DOM: its place among the host's children, the one left out
        # (no slot shows it) included.
        self.assertEqual(self.of(html, lambda s: s.find("p", id="lit")),
                         ["#lit"])
        html = html.replace('id="lit"', "")
        self.assertEqual(self.of(html, lambda s: s.find(string="shown").parent),
                         ["#c > p:nth-child(2)"])

    def test_what_is_left_out_is_no_anchor(self):
        # The unslotted <b id="x"> is in the DOM, though not in the rules'
        # tree, so `#x` could find it first.
        html = PAGE.format(
            '<x-a><template shadowrootmode="open"><slot name="s"></slot>'
            '</template><b id="x">dropped</b></x-a><a id="x" href="/x">x</a>')
        self.assertEqual(self.of(html, lambda s: s.find("a")),
                         ["body > main > a"])

    def test_a_top_level_step_that_could_match_deeper_gets_host(self):
        html = PAGE.format(
            '<x-a id="h"><template shadowrootmode="open"><div><span>1</span>'
            '<div>inner</div></div><div>outer</div></template></x-a>')
        self.assertEqual(self.of(html, lambda s: s.find(string="outer")
                                 .parent), ["#h", ":host > div:nth-child(2)"])

    def test_findings_carry_them_in_every_output(self):
        got = locators(PAGE.format('<a href="/x"></a>'))
        self.assertIn(("bb-link-name", ["body > main > a"]), got)
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        (d / "p.html").write_text(PAGE.format('<a href="/x"></a>'),
                                  encoding="utf-8")
        code, _, err = run(d / "p.html", "--json", d / "r.json", "--html",
                           d / "r.html", "--bundle", d / "b.json",
                           "--fail-on", "never")
        self.assertEqual(code, 0, err)
        for name in ("r.json", "b.json"):
            data = json.loads((d / name).read_text(encoding="utf-8"))
            sel = [f["selector"] for f in data["pages"][0]["findings"]
                   if f["rule_id"] == "bb-link-name"]
            self.assertEqual(sel, [["body > main > a"]], name)
        self.assertIn("<code>body &gt; main &gt; a</code>",
                      (d / "r.html").read_text(encoding="utf-8"))


_START_TAG = re.compile(r"<([A-Za-z][^\s/>]*)")
_RAW_TEXT = ("script", "style", "textarea", "title", "xmp", "iframe",
             "noembed", "noframes", "plaintext")


def stamp(markup: str) -> str:
    """`markup` with data-u="N" in every start tag outside comments and raw
    text, so an element is known by more than its name: a locator that
    finds a sibling or a cousin of the same name is caught (PR2-7)."""
    out, i, n = [], 0, 0
    while i < len(markup):
        if markup.startswith("<!--", i):
            j = markup.find("-->", i + 4)
            j = len(markup) if j < 0 else j + 3
            out.append(markup[i:j])
            i = j
            continue
        m = _START_TAG.match(markup, i)
        if not m:
            out.append(markup[i])
            i += 1
            continue
        n += 1
        out.append(f'{m.group(0)} data-u="{n}"')
        i = m.end()
        name = m.group(1).lower()
        if name in _RAW_TEXT:
            end = markup.lower().find("</" + name, markup.find(">", i))
            end = len(markup) if end < 0 else end
            out.append(markup[i:end])
            i = end
    return "".join(out)


@unittest.skipUnless(HAVE_BROWSER, _WHY)
class TestLocatorsInChromium(unittest.TestCase):
    """Every element's locator, resolved by Chromium, finds that element and
    no other: in a file as the parser builds it (scripts off), and in a
    rendered capture with shadow roots its scripts attached. An element is
    known by its chain of names and data-u stamps up to its tree's top."""

    RESOLVE = r"""(paths) => paths.map((path) => {
      if (!path) return "no locator";
      let scope = document, el = null, unique = true;
      for (let i = 0; i < path.length; i++) {
        const all = scope.querySelectorAll(path[i]);
        if (all.length !== 1) unique = false;
        el = all[0];
        if (!el) return null;
        if (i < path.length - 1) {
          scope = el.shadowRoot;
          if (!scope) return el.localName.includes("-") ? "closed" : null;
        }
      }
      const chain = [];
      for (let n = el; n && n.nodeType === 1; n = n.parentNode)
        chain.push(n.nodeName.toLowerCase() + "#" +    // with its prefix
                   (n.getAttribute("data-u") || ""));
      return unique ? chain.join("<") : "not unique";
    })"""

    def expected(self, ctx):
        """[(locator, what Chromium should find)]: the element's chain of
        names and stamps up to its tree's top, or "closed" behind a closed
        shadow root (page scripts cannot open one; developer tools can)."""
        from bellbriar_harness import shadow
        from bellbriar_harness.checks_static import _inert_content
        out = []
        for el in ctx.soup.find_all(True):
            if shadow.is_wrapper(el) or _inert_content(el):
                continue
            path = ctx.locator(el)
            loc = ctx._locators
            chain, n = [], el
            while n is not None:
                chain.append(n.name.lower() + "#" + (n.get("data-u") or ""))
                n = loc._dom_parent(n)
            closed = any(shadow.is_wrapper(w) and
                         str(w.get("data-mode", "")).lower() == "closed"
                         for w in el.parents)
            out.append((path, "closed" if closed else "<".join(chain)))
        return out

    def check(self, page, items):
        got = page.evaluate(self.RESOLVE, [p for p, _ in items])
        bad = [(p, want, g) for (p, want), g in zip(items, got) if g != want]
        self.assertEqual(bad, [])

    def test_a_file_as_parsed(self):
        from playwright.sync_api import sync_playwright
        html = stamp((ROOT / "tests" / "data" / "locator-page.html").read_text(
            encoding="utf-8")).encode("utf-8")
        ctx = PageContext.parse(html)
        items = self.expected(ctx)
        self.assertGreater(len(items), 50)
        self.assertEqual(sum(w == "closed" for _, w in items), 1)
        self.assertTrue(any(len(p) == 3 for p, _ in items))   # two roots deep
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        (d / "p.html").write_bytes(html)
        with sync_playwright() as p:
            b = p.chromium.launch()
            try:
                page = b.new_context(java_script_enabled=False).new_page()
                page.goto((d / "p.html").as_uri())
                self.check(page, items)
            finally:
                b.close()

    def test_an_xhtml_file(self):
        # Names keep their case and their prefix in XML: <A> is not <a>, and
        # its step is `A` (by position too, since an HTML document's `A`
        # would match an <a>); <dc:title> is written by position (`*`).
        from playwright.sync_api import sync_playwright
        html = (b'<?xml version="1.0" encoding="utf-8"?>\n<html xmlns="http://'
                b'www.w3.org/1999/xhtml" xmlns:dc="http://purl.org/dc/elements'
                b'/1.1/" lang="en"><head><title>X</title></head><body><p>'
                b'<a href="/1">1</a><A href="/2">2</A><a href="/3">3</a></p>'
                b'<div><dc:title>t</dc:title><dc:title>u</dc:title><span>s'
                b'</span></div><noscript><p id="n">ns</p></noscript><a id="n" '
                b'href="/n">n</a><svg xmlns="http://www.w3.org/2000/svg"><g><rect'
                b'/></g><foreignObject><p xmlns="http://www.w3.org/1999/xhtml">'
                b'f</p></foreignObject></svg><div id="Q">q</div><div id="q">'
                b'<b>r</b></div></body></html>')
        html = stamp(html.decode("utf-8")).encode("utf-8")
        ctx = PageContext.parse(html, path="p.xhtml")
        items = self.expected(ctx)
        self.assertGreater(len(items), 15)
        self.assertIn(["body > p > A:nth-child(2)"], [p for p, _ in items])
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        (d / "p.xhtml").write_bytes(html)
        with sync_playwright() as p:
            b = p.chromium.launch()
            try:
                page = b.new_context(java_script_enabled=False).new_page()
                page.goto((d / "p.xhtml").as_uri())
                self.check(page, items)
            finally:
                b.close()

    def test_a_rendered_capture(self):
        from playwright.sync_api import sync_playwright

        from bellbriar_harness.model import PROVENANCE_ATTR
        body = (ROOT / "tests" / "data" / "locator-app.html").read_bytes()
        site = _Site({"/": send(body)})
        self.addCleanup(site.stop)
        fr = F.fetch_rendered(site.base + "/")
        token = PROVENANCE_ATTR.set(fr.provenance_attr)
        try:
            ctx = PageContext.parse(fr.html, provenance_attr=fr.provenance_attr)
            items = self.expected(ctx)
        finally:
            PROVENANCE_ATTR.reset(token)
        self.assertGreater(len(items), 30)
        self.assertTrue(any(len(p) == 3 for p, _ in items))   # two roots deep
        with sync_playwright() as p:
            b = p.chromium.launch()
            try:
                page = b.new_page()
                page.goto(site.base + "/")
                page.wait_for_timeout(300)
                self.check(page, items)
            finally:
                b.close()


class TestBuildServer(unittest.TestCase):
    """A1's loopback server serves the build and nothing else."""

    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.d, ignore_errors=True)
        (self.d / "site" / "assets").mkdir(parents=True)
        (self.d / "site" / "index.html").write_text("<p>i</p>", encoding="utf-8")
        (self.d / "site" / "assets" / "a.js").write_text("x=1", encoding="utf-8")
        (self.d / "site" / ".env").write_text("SECRET=1", encoding="utf-8")
        (self.d / "secret.txt").write_text("no", encoding="utf-8")
        (self.d / "site" / "sub").mkdir()
        try:
            os.symlink(self.d / "secret.txt", self.d / "site" / "link.txt")
            # A folder whose index.html is a symlink out, and a symlink in
            # the root to a dot-named file (PR1-1).
            os.symlink(self.d / "secret.txt",
                       self.d / "site" / "sub" / "index.html")
            os.symlink(self.d / "site" / ".env", self.d / "site" / "env.txt")
        except OSError:
            pass

    def get(self, url):
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                return r.status, r.headers.get("Content-Type"), r.read()
        except urllib.error.HTTPError as exc:
            return exc.code, None, b""

    def test_only_the_build(self):
        with BuildServer(self.d / "site", "/app/") as srv:
            base = srv.url_for(self.d / "site" / "index.html").rsplit("/", 1)[0]
            self.assertTrue(base.startswith("http://127.0.0.1:"))
            self.assertTrue(base.endswith("/app"))
            origin = base[:-len("/app")]
            status, ctype, body = self.get(base + "/")
            self.assertEqual((status, body), (200, b"<p>i</p>"))
            self.assertEqual(ctype, "text/html; charset=windows-1252")
            status, ctype, _ = self.get(base + "/assets/a.js")
            self.assertEqual((status, ctype),
                             (200, "text/javascript; charset=utf-8"))
            for path in ("/app/.env", "/app/assets/../../secret.txt",
                         "/app/%2e%2e/secret.txt", "/app/link.txt",
                         "/app/sub/", "/app/sub", "/app/sub/index.html",
                         "/app/env.txt", "/index.html", "/app/nope.js"):
                with self.subTest(path):
                    self.assertEqual(self.get(origin + path)[0], 404)
            req = urllib.request.Request(base + "/", data=b"x", method="POST")
            with self.assertRaises(urllib.error.HTTPError) as cm:
                urllib.request.urlopen(req, timeout=5)
            self.assertEqual(cm.exception.code, 405)
            self.assertEqual(set(srv.served), {"index.html", "assets/a.js"})
            self.assertIn("/app/nope.js", srv.missing)

    def test_bases(self):
        for raw, want in (("/", "/"), ("app", "/app/"), ("/a/b", "/a/b/"),
                          ("//x//", "/x/")):
            self.assertEqual(normalize_base(raw), want)
        for bad in ("/../x", "/a/./b", "/a?b"):
            with self.subTest(bad), self.assertRaises(ValueError):
                normalize_base(bad)


BUILD_JS = (b"document.getElementById('root').innerHTML = '<header><nav><a "
            b"href=\"/\">Home</a></nav></header><main><h1>' + document.title "
            b"+ '</h1><button class=\"icon\"></button></main>';")


def make_build(d: Path, base: str = "") -> Path:
    dist = d / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "about").mkdir()
    shell = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
             '<title>{}</title><script type="module" src="' + base
             + '/assets/app.js"></script></head><body><div id="root"></div>'
             '</body></html>')
    (dist / "index.html").write_text(shell.format("Home"), encoding="utf-8")
    (dist / "about" / "index.html").write_text(shell.format("About"),
                                               encoding="utf-8")
    (dist / "assets" / "app.js").write_bytes(BUILD_JS)
    return dist


class TestRenderFlags(unittest.TestCase):
    def test_a_page_under_a_dot_folder_is_not_served(self):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        dist = make_build(d)
        (dist / ".cache").mkdir()
        (dist / ".cache" / "x.html").write_text(PAGE.format("<p>x</p>"),
                                                encoding="utf-8")
        with mock.patch.object(F, "playwright_available",
                               lambda: (False, "no browser here")):
            code, _, err = run(dist, "--render", "--fail-on", "never")
        self.assertEqual(code, 2)
        self.assertIn("dist/.cache/x.html: it is under a name that starts "
                      "with a dot", err)

    def test_contradictions_are_refused(self):
        for argv in (("x", "--render", "--no-render"),
                     ("x", "--render-base", "/app/"),
                     ("--url", "http://127.0.0.1:9/", "--render"),
                     ("--url", "http://a.test/", "--urls", "f"),
                     ("x", "--url", "http://a.test/"),
                     ("x", "--save-snapshot", "s.html"),
                     ("--url", "http://a.test/", "--max-pages", "0"),
                     ("x", "--render", "--read-as", "dom")):
            with self.subTest(argv):
                code, _, _ = run(*argv)
                self.assertEqual(code, 2)


@unittest.skipUnless(HAVE_BROWSER, _WHY)
class TestRenderTheBuild(unittest.TestCase):
    """A1."""

    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.d, ignore_errors=True)

    def test_a_client_rendered_build_is_measured(self):
        dist = make_build(self.d)
        # Read as files, every page is an empty shell: not evaluated.
        code, _, err = run(dist, "--fail-on", "never")
        self.assertEqual(code, 2)
        self.assertIn("--render", err)
        code, _, err = run(dist, "--render", "--json", self.d / "r.json",
                           "--bundle", self.d / "b.json", "--save-snapshots",
                           self.d / "snaps", "--fail-on", "tier1")
        self.assertEqual(code, 1, err)              # the unnamed button
        bundle = json.loads((self.d / "b.json").read_text(encoding="utf-8"))
        self.assertIsNone(bundle["fetch"])           # nothing binds a host
        self.assertIn("served the files on this machine",
                      bundle["coverage_note"])
        names = [p["path"] for p in bundle["pages"]]
        self.assertEqual(names, ["dist/about/index.html", "dist/index.html"])
        for page in bundle["pages"]:
            rec = page["fetch"]
            self.assertEqual(rec["mode"], "rendered")
            self.assertEqual(rec["address_class"], "loopback")
            fails = [(f["rule_id"], f["selector"]) for f in page["findings"]
                     if f["verdict"] == "fail"]
            self.assertIn(("bb-button-name", ["#root > main > button"]), fails)
        inputs = {i["path"]: i for i in bundle["inputs"]}
        self.assertEqual(inputs["dist/assets/app.js"]["kind"], "served")
        self.assertEqual(inputs["dist/assets/app.js"]["sha256"],
                         hashlib.sha256(BUILD_JS).hexdigest())
        self.assertNotIn("kind", inputs["dist/index.html"])
        snaps = sorted((self.d / "snaps").iterdir())
        self.assertEqual(len(snaps), 2)
        self.assertEqual(hashlib.sha256(snaps[0].read_bytes()).hexdigest(),
                         bundle["pages"][0]["fetch"]["snapshot_sha256"])
        from bellbriar_harness.bundle import bundle_bound_values
        self.assertIsNone(bundle_bound_values(bundle)["host"])

    def test_a_base_path(self):
        dist = make_build(self.d, base="/app")
        code, _, err = run(dist, "--render", "--fail-on", "never")
        self.assertIn("--render-base", err)          # its script was missing
        self.assertIn("empty when captured", err)
        code, _, err = run(dist, "--render", "--render-base", "/app/",
                           "--json", self.d / "r.json", "--fail-on", "never")
        self.assertEqual(code, 0, err)
        report = json.loads((self.d / "r.json").read_text(encoding="utf-8"))
        self.assertTrue(all(p["score"]["evaluable"] for p in report["pages"]))

    def test_a_page_that_navigates_away_is_read_as_the_file_it_is(self):
        # PR1-3, PR3-1: a build page that sends the browser to another
        # document (a login page of the build, another local service) is
        # not what the browser showed: it is read as the file it is, and a
        # page the build has is evaluated as itself.
        other = _Site({"/": send(PAGE.format("<p>elsewhere</p>").encode())})
        self.addCleanup(other.stop)
        dist = self.d / "dist"
        dist.mkdir()
        body = ('<main><h1>Home</h1><img src="x.png"><button></button>'
                '</main>')
        for name, to in (("index.html", "/login.html"),
                         ("away.html", other.base + "/")):
            (dist / name).write_text(
                '<!doctype html><html lang="en"><head><title>Go</title>'
                f'<script>addEventListener("load", () => location.replace('
                f'"{to}"))</script></head><body>{body}</body></html>',
                encoding="utf-8")
        # As an app sends a visitor without a token to its login page,
        # before the page has loaded.
        (dist / "now.html").write_text(
            '<!doctype html><html lang="en"><head><title>Go</title></head>'
            f'<body>{body}<script>location.replace("/login.html")</script>'
            '</body></html>', encoding="utf-8")
        (dist / "login.html").write_text(PAGE.format("<p>Sign in</p>"),
                                         encoding="utf-8")
        code, _, err = run(dist, "--render", "--json", self.d / "r.json",
                           "--fail-on", "tier1")
        self.assertEqual(code, 1, err)
        # Seen once the new page has loaded, or as the old page's scripts
        # vanishing while it is scrolled, whichever the timing gives.
        self.assertRegex(err, r"when rendered, it navigated to|navigated "
                              r"away, while it was scrolled")
        report = json.loads((self.d / "r.json").read_text(encoding="utf-8"))
        pages = {p["path"]: p for p in report["pages"]}
        for name in ("dist/index.html", "dist/away.html", "dist/now.html"):
            page = pages[name]
            self.assertEqual(page["fetch"]["mode"], "server", name)
            fails = sorted(f["rule_id"] for f in page["findings"]
                           if f["verdict"] == "fail")
            self.assertEqual(fails, ["bb-button-name", "bb-img-alt"], name)
        self.assertEqual(pages["dist/login.html"]["fetch"]["mode"], "rendered")
        code, _, err = run(dist, "--render", "--require-render", "--fail-on",
                           "never")
        self.assertEqual(code, 2)

    def test_without_a_browser_the_files_are_read_as_they_are(self):
        dist = make_build(self.d)
        with mock.patch.object(F, "playwright_available",
                               lambda: (False, "no browser here")):
            code, _, err = run(dist, "--render", "--json", self.d / "r.json",
                               "--fail-on", "never")
        self.assertEqual(code, 2)                    # empty shells, loudly
        self.assertIn("not rendered, read as the file it is", err)
        report = json.loads((self.d / "r.json").read_text(encoding="utf-8"))
        self.assertIn("could not render the files", report["coverage_note"])
        with mock.patch.object(F, "playwright_available",
                               lambda: (False, "no browser here")):
            code, _, err = run(dist, "--render", "--require-render")
        self.assertEqual(code, 2)


@unittest.skipUnless(HAVE_BROWSER, _WHY)
class TestManyPages(unittest.TestCase):
    """A3."""

    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.d, ignore_errors=True)
        good = PAGE.format("<p>ok</p>").encode()
        bad = PAGE.format('<a href="/x"></a>').encode()
        self.site = _Site({"/a": send(good), "/b": send(bad),
                           "/gone": send(b"nope", status=404)})
        self.addCleanup(self.site.stop)
        port = self.site.port
        self.site_other = None
        # 127.0.0.1 and localhost are different hosts to evidence.
        self.elsewhere = f"http://localhost:{port}/a"

    def test_one_report_and_one_bundle(self):
        b = self.site.base
        code, _, err = run("--url", b + "/a", "--url", b + "/b", "--url",
                           b + "/a", "--no-render", "--bundle",
                           self.d / "b.json", "--json", self.d / "r.json",
                           "--save-snapshots", self.d / "s", "--fail-on",
                           "never")
        self.assertEqual(code, 0, err)
        bundle = json.loads((self.d / "b.json").read_text(encoding="utf-8"))
        self.assertEqual(bundle["fetch"]["pages"], 2)      # the repeat dropped
        self.assertEqual(bundle["fetch"]["host"], "127.0.0.1")
        self.assertEqual(bundle["fetch"]["final_url"], b + "/a")
        self.assertEqual(bundle["fetch"]["list"], {"kind": "urls",
                                                   "max_pages": 50})
        self.assertEqual([p["path"] for p in bundle["pages"]],
                         [b + "/a", b + "/b"])
        self.assertEqual([i["path"] for i in bundle["inputs"]],
                         [b + "/a", b + "/b"])
        for page, snap in zip(bundle["pages"], sorted((self.d / "s").iterdir())):
            self.assertEqual(hashlib.sha256(snap.read_bytes()).hexdigest(),
                             page["fetch"]["snapshot_sha256"])
        report = json.loads((self.d / "r.json").read_text(encoding="utf-8"))
        self.assertEqual(report["fetch"], bundle["fetch"])

    def test_one_page_listed_twice_is_one_page(self):
        # PR1-4: spellings a browser requests the same way are one URL; a
        # second fragment is fetched, and dropped when its capture is the
        # same. A client-routed page that differs by fragment is kept.
        b = self.site.base
        port = self.site.port
        code, _, err = run("--url", b + "/a", "--url", f"HTTP://127.0.0.1:"
                           f"{port}/a", "--url", b + "/a#one", "--url",
                           b + "/b", "--no-render", "--json", self.d / "r.json",
                           "--fail-on", "never")
        self.assertEqual(code, 0, err)
        self.assertIn("is the same page as", err)
        report = json.loads((self.d / "r.json").read_text(encoding="utf-8"))
        self.assertEqual([p["path"] for p in report["pages"]],
                         [b + "/a", b + "/b"])
        self.assertEqual(report["fetch"]["pages"], 2)
        routed = (b'<!doctype html><html lang="en"><head><title>R</title>'
                  b'</head><body><main><h1>R</h1></main><script>document.'
                  b'querySelector("h1").textContent = location.hash'
                  b'</script></body></html>')
        site = _Site({"/r": send(routed)})
        self.addCleanup(site.stop)
        code, _, err = run("--url", site.base + "/r#/one", "--url",
                           site.base + "/r#/two", "--json", self.d / "s.json",
                           "--fail-on", "never")
        self.assertEqual(code, 0, err)
        report = json.loads((self.d / "s.json").read_text(encoding="utf-8"))
        self.assertEqual(len(report["pages"]), 2)

    def test_a_page_not_measured_is_no_pass(self):
        b = self.site.base
        Path(self.d / "urls.txt").write_text(
            f"# the pages\n{b}/a\n\n{b}/gone\n{self.elsewhere}\n{b}/b\n",
            encoding="utf-8")
        code, _, err = run("--urls", self.d / "urls.txt", "--no-render",
                           "--json", self.d / "r.json", "--bundle",
                           self.d / "b.json", "--fail-on", "never")
        self.assertEqual(code, 2)
        self.assertIn("returned HTTP 404", err)
        self.assertIn("a run measures one host", err)
        self.assertIn("refusing to write the evidence bundle", err)
        self.assertFalse((self.d / "b.json").exists())
        report = json.loads((self.d / "r.json").read_text(encoding="utf-8"))
        self.assertTrue(report["incomplete"])
        states = [(p["fetch"] is not None, bool(p["errors"]))
                  for p in report["pages"]]
        self.assertEqual(states, [(True, False), (False, True), (False, True),
                                  (True, False)])

    def test_the_page_limit(self):
        b = self.site.base
        code, _, err = run("--url", b + "/a", "--url", b + "/b",
                           "--max-pages", "1", "--no-render")
        self.assertEqual(code, 2)
        self.assertIn("more than --max-pages (1)", err)
        code, _, err = run("--url", b + "/a", "--url", b + "/b", "--no-render",
                           "--save-snapshot", self.d / "one.html")
        self.assertEqual(code, 2)
        self.assertIn("--save-snapshots", err)

    def test_credentials_go_to_one_origin(self):
        code, _, err = run("--url", self.site.base + "/a", "--url",
                           self.elsewhere, "--http-user", "u",
                           env={cli.HTTP_PASSWORD_ENV: "pw"})
        self.assertEqual(code, 2)
        self.assertIn("one origin", err)


class TestSitemap(unittest.TestCase):
    """A3: --sitemap, as the protocol reads it."""

    def setUp(self):
        self.pages = {f"/p{i}": send(PAGE.format(f"<p>{i}</p>").encode())
                      for i in range(6)}
        self.routes = dict(self.pages)
        self.site = _Site(self.routes)
        self.addCleanup(self.site.stop)

    def urlset(self, paths, other=()):
        b = self.site.base
        locs = "".join(f"<url><loc> {b}{p} </loc></url>" for p in paths)
        locs += "".join(f"<url><loc>{u}</loc></url>" for u in other)
        return ('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://'
                f'www.sitemaps.org/schemas/sitemap/0.9">{locs}</urlset>').encode()

    def test_an_index_of_sitemaps(self):
        from bellbriar_harness import sitemap
        b = self.site.base
        self.routes["/s1.xml"] = send(self.urlset(["/p0", "/p1", "/p1"],
                                                  ["https://elsewhere.test/x"]),
                                      ctype="application/xml")
        self.routes["/s2.xml.gz"] = send(gzip.compress(self.urlset(
            ["/p2", "/p3", "/p4"])), ctype="application/gzip")
        self.routes["/index.xml"] = send(
            ('<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
             f'<sitemap><loc>{b}/s1.xml</loc></sitemap>'
             f'<sitemap><loc>{b}/s2.xml.gz</loc></sitemap>'
             '<sitemap><loc>https://elsewhere.test/s.xml</loc></sitemap>'
             '</sitemapindex>').encode(), ctype="text/xml")
        got = sitemap.read(b + "/index.xml", max_pages=10)
        self.assertEqual(got.urls, [b + p for p in ("/p0", "/p1", "/p2", "/p3",
                                                    "/p4")])
        self.assertEqual((got.listed, got.complete, got.other_host),
                         (5, True, 2))
        got = sitemap.read(b + "/index.xml", max_pages=2)
        self.assertEqual(got.urls, [b + "/p0", b + "/p1"])
        self.assertFalse(got.complete)               # s2 never read

    def test_credentials_stay_with_the_sitemaps_origin(self):
        # Same host, another port: another origin. Its sitemap is read
        # without the password (and is skipped when it asks for one), and a
        # run whose pages are there is refused before any page is fetched.
        from bellbriar_harness import sitemap
        seen = []
        body = self.urlset(["/p0"])

        def challenge(h):
            seen.append(h.headers.get("Authorization"))
            if h.headers.get("Authorization"):
                send(body, ctype="application/xml")(h)
                return
            h.send_response(401)
            h.send_header("WWW-Authenticate", 'Basic realm="x"')
            h.send_header("Content-Length", "0")
            h.end_headers()
        other = _Site({"/s.xml": challenge})
        self.addCleanup(other.stop)
        b = self.site.base
        self.routes["/index.xml"] = send(
            ('<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
             f'<sitemap><loc>{other.base}/s.xml</loc></sitemap>'
             '</sitemapindex>').encode(), ctype="application/xml")
        got = sitemap.read(b + "/index.xml", max_pages=5,
                           http_credentials=("u", "pw"))
        self.assertEqual(seen, [None])
        self.assertEqual((got.urls, got.complete), ([], False))
        self.routes["/elsewhere.xml"] = send(
            self.urlset([]).replace(b"</urlset>", f"<url><loc>{other.base}/p0"
                                    "</loc></url></urlset>".encode()),
            ctype="application/xml")
        code, _, err = run("--sitemap", b + "/elsewhere.xml", "--http-user",
                           "u", "--no-render", env={cli.HTTP_PASSWORD_ENV: "pw"})
        self.assertEqual(code, 2)
        self.assertIn("one origin", err)
        self.assertEqual(seen, [None])

    def test_what_is_refused(self):
        from bellbriar_harness import sitemap
        b = self.site.base
        self.routes["/dtd.xml"] = send(
            b'<!DOCTYPE urlset [<!ENTITY a "aaaa">]><urlset><url><loc>&a;</loc>'
            b'</url></urlset>', ctype="application/xml")
        self.routes["/html"] = send(PAGE.format("").encode())
        for path, why in (("/dtd.xml", "DOCTYPE"), ("/html", "not well-formed"),
                          ("/missing.xml", "HTTP 404")):
            with self.subTest(path), self.assertRaisesRegex(
                    (sitemap.SitemapError, F.FetchError), why):
                sitemap.read(b + path, max_pages=5)

    @unittest.skipUnless(HAVE_BROWSER, _WHY)
    def test_the_cli_records_how_the_pages_were_listed(self):
        b = self.site.base
        self.routes["/sitemap.xml"] = send(self.urlset(["/p0", "/p1", "/p2"]),
                                           ctype="application/xml")
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        code, _, err = run("--sitemap", b + "/sitemap.xml", "--max-pages", "2",
                           "--no-render", "--json", d / "r.json")
        self.assertEqual(code, 0, err)
        self.assertIn("2 of 3 listed page(s)", err)
        fetch = json.loads((d / "r.json").read_text(encoding="utf-8"))["fetch"]
        self.assertEqual(fetch["list"], {"kind": "sitemap",
                                         "url": b + "/sitemap.xml",
                                         "listed": 3, "complete": True,
                                         "max_pages": 2})
        self.assertEqual(fetch["pages"], 2)


if __name__ == "__main__":
    unittest.main()
