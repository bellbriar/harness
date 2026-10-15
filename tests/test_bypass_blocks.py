"""bb-skip-link (2.4.1 bypass blocks) on the page shapes it meets in the
wild. The rule FAILs only when it can establish the failure: nothing
bypasses the repeated blocks, or the only mechanism is a skip link that
leads nowhere. A main landmark (ARIA11) or a heading that opens the content
(H69) turns a missing or broken skip link into a review, marked "pled in
complaints; not a WCAG failure on its own".

The navigation a bypass must get past is the first one before the content:
breadcrumbs inside <main>, and sidebar or footer menus after it, are not
it. A working skip link must never be reported as broken.
"""
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bellbriar_harness import cli                                # noqa: E402
from bellbriar_harness.checks_static import (PageContext,        # noqa: E402
                                             check_skip_link)
from bellbriar_harness.model import FAIL, MODERATE, NEEDS_REVIEW, SERIOUS  # noqa: E402

PLED = "pled in complaints; not a WCAG failure on its own"
NAV = '<nav><a href="/a">A</a><a href="/b">B</a><a href="/c">C</a></nav>'
MENU = '<div class="menu"><a href="/a">A</a><a href="/b">B</a><a href="/c">C</a></div>'
LINKS16 = "".join(f'<a href="/p{i}">P{i}</a>' for i in range(16))


def page(body: str, title: str = "Shop") -> str:
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<title>{title}</title></head><body>{body}</body></html>')


def skip(html: str):
    return check_skip_link(PageContext.parse(html, path="x.html"))


def outcome(html: str) -> tuple[str, str]:
    rr = skip(html)
    if not rr.applicable:
        return "n/a", ""
    if not rr.findings:
        return "pass", ""
    (f,) = rr.findings
    if f.verdict == FAIL:
        assert f.impact == SERIOUS, f
        return "fail", f.message
    assert f.verdict == NEEDS_REVIEW and f.impact == MODERATE, f
    assert PLED in f.message, f.message
    return "review", f.message


def eval_cli(html: str, *argv: str) -> int:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "p.html"
        path.write_text(html, encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            return cli.main([str(path), *argv])


#: name: (body, outcome, a fragment the message must contain)
SHAPES = {
    # Working skip links: no finding.
    "skip link to <main>": (
        f'<a href="#main">Skip to content</a><header>{NAV}</header>'
        '<main id="main"><h1>X</h1></main>', "pass", ""),
    "WordPress: skip link to a wrapper around <main>": (
        f'<a href="#content">Skip to content</a><div id="page"><header>{NAV}'
        '</header><div id="content"><main id="primary"><h1>X</h1></main></div>'
        '</div>', "pass", ""),
    "first item inside the navigation": (
        '<header><nav><a href="#main">Skip to content</a><a href="/a">A</a>'
        '</nav></header><main id="main"><h1>X</h1></main>', "pass", ""),
    "German, recognised by position": (
        f'<a href="#inhalt">Zum Inhalt springen</a><header>{NAV}</header>'
        '<main id="inhalt"><h1>X</h1></main>', "pass", ""),
    "a broken skip link before a working one": (
        '<a href="#nav">Skip to navigation</a><a href="#main">Skip to '
        'content</a><header><nav id="nav"><a href="/a">A</a></nav></header>'
        '<main id="main"><h1>X</h1></main>', "pass", ""),
    "after a consent banner": (
        '<div class="cookie"><a href="/privacy">Privacy</a><button>OK</button>'
        f'</div><a href="#main">Skip to content</a><header>{NAV}</header>'
        '<main id="main"><h1>X</h1></main>', "pass", ""),
    "a named anchor as the target": (
        f'<a href="#content">Skip to content</a><header>{NAV}</header>'
        '<a name="content"></a><div><p>X</p></div>', "pass", ""),
    "a percent-encoded target": (
        f'<a href="#main%20content">Skip to content</a><header>{NAV}</header>'
        '<main id="main content"><h1>X</h1></main>', "pass", ""),
    "breadcrumbs inside <main>, menu not marked up as nav": (
        f'<a href="#main">Skip to content</a>{MENU}<main id="main"><nav '
        'aria-label="Breadcrumb"><a href="/">Home</a></nav><h1>X</h1></main>',
        "pass", ""),
    "only a footer menu, no <main>": (
        f'<a href="#content">Skip to content</a>{MENU}<div id="content"><p>X'
        f'</p></div><footer>{NAV}</footer>', "pass", ""),
    "sidebar menu after <main>": (
        f'<a href="#main">Skip to content</a>{MENU}<main id="main"><h1>X</h1>'
        f'</main><aside>{NAV}</aside>', "pass", ""),
    "sidebar menu after the content, no <main>": (
        f'<a href="#content">Skip to content</a>{MENU}<div id="content"><p>X'
        f'</p></div><div class="sidebar">{NAV}</div>', "pass", ""),
    "everything inside <main>": (
        f'<main><a href="#c">Skip to content</a><header>{NAV}</header>'
        '<div id="c"><h1>X</h1></div></main>', "pass", ""),
    # Broken skip links.
    "missing target, <main> present": (
        f'<a href="#content">Skip to content</a><header>{NAV}</header>'
        '<main id="primary"><h1>X</h1></main>', "review",
        "'#content', but the page has no element with that id; a main "
        "landmark can still satisfy 2.4.1"),
    "missing target, a heading opens the content": (
        f'<a href="#content">Skip to content</a><header>{NAV}</header>'
        '<div><h1>X</h1></div>', "review",
        "a heading that opens the content can still satisfy 2.4.1"),
    "missing target, nothing else": (
        f'<a href="#content">Skip to content</a><header>{NAV}</header>'
        '<div><p>X</p></div>', "fail",
        "no element with that id, and nothing else bypasses"),
    "target above the navigation": (
        f'<div id="top"></div><a href="#top">Skip to content</a><header>{NAV}'
        '</header><main id="main"><h1>X</h1></main>', "review",
        "which does not lead past the navigation"),
    "target wraps the navigation": (
        f'<a href="#page">Skip to content</a><a href="/">Logo</a><div id="page">'
        f'<header>{NAV}</header><div><p>X</p></div></div>', "fail",
        "which does not lead past the navigation"),
    "target is the navigation": (
        '<a href="#nav">Skip to content</a><div><nav id="nav"><a href="/a">A'
        '</a><a href="/b">B</a></nav></div><div><p>X</p></div>', "fail",
        "which does not lead past the navigation"),
    "no navigation element, target above the link": (
        f'<div id="top"></div><a href="#top">Skip to content</a><header>'
        f'{LINKS16}</header><div><h1>X</h1></div>', "review",
        "which does not lead to the content"),
    # No skip link.
    "no skip link, <main> present": (
        f'<header>{NAV}</header><main><h1>X</h1></main>', "review",
        "No skip link found before the navigation; a main landmark can "
        "satisfy"),
    "a hero's scroll arrow inside <main>": (
        f'<header>{NAV}</header><main><div class="hero"><h1>X</h1><a '
        'href="#work" aria-label="Scroll to content">v</a></div><section '
        'id="work"><h2>W</h2></section></main>', "review", "No skip link"),
    "a hero's scroll arrow, no <main>": (
        f'<div>{NAV}</div><div class="hero"><p>X</p><a href="#c" aria-label='
        '"Scroll to content">v</a></div><div id="c"><p>Y</p></div>', "fail",
        "no skip link found before the navigation, no main landmark and no "
        "heading that opens the content"),
    "a skip link after the navigation, no <main>": (
        f'<div>{NAV}</div><a href="#c">Skip to main content</a><div id="c">'
        '<p>Y</p></div>', "fail", "no skip link found before the navigation"),
    # G124 (a one-page site's navigation links to its sections)
    # stands in for a skip link like a main landmark does: complaints still
    # plead the missing skip link, so it is a review.
    "in-page navigation of a one-page site": (
        '<header><nav><a href="#features">Features</a><a href="#pricing">'
        'Pricing</a></nav></header><main><section id="features"><h2>F</h2>'
        '</section><section id="pricing"><h2>P</h2></section></main>',
        "review", "No skip link"),
    "a hash route": (
        f'<a href="#/shop">Skip to content</a><header>{NAV}</header><main>'
        '<h1>X</h1></main>', "review", "No skip link"),
    "Back to top": (
        f'<a href="#top" id="top">Back to top</a><header>{NAV}</header><main>'
        '<h1>X</h1></main>', "review", "No skip link"),
    "a skip link behind a utility menu": (
        '<nav aria-label="Utility"><a href="/login">Log in</a></nav><a href='
        f'"#main">Skip to content</a><header>{NAV}</header><main id="main">'
        '<h1>X</h1></main>', "pass", ""),
    "no navigation element: 16 links in a <header>, then a heading": (
        f'<header>{LINKS16}</header><div><h1>X</h1></div>', "review",
        "No skip link found among the first links; a heading that opens the "
        "content can satisfy"),
    # No navigation element and no page header: the markup does not say
    # which links are a repeated block, so this is not a FAIL.
    "no navigation element: 16 links in a <div>, then a heading": (
        f'<div>{LINKS16}</div><div><h1>X</h1></div>', "review",
        "No skip link found among the first links, no main landmark and no "
        "heading that opens the content; the markup marks no navigation or "
        "page header holding two or more links or controls"),
    "the sixth link, after a top bar": (
        '<div class="top-bar"><a href="tel:+17185550100">Call</a><a href='
        '"mailto:a@b.example">Email</a><a href="https://facebook.com/a">FB</a>'
        '<a href="https://instagram.com/a">IG</a><a href="https://yelp.com/a">'
        f'Yelp</a></div><a href="#content">Skip to content</a><header>{NAV}'
        '</header><div id="content"><h1>X</h1></div>', "pass", ""),
    "a skip button": (
        '<button onclick="document.getElementById(\'m\').focus()">Skip to '
        f'main content</button><header>{NAV}</header><main id="m" '
        'tabindex="-1"><h1>X</h1></main>', "pass", ""),
    "breadcrumbs in a wrapper, no <main>, menu not marked up as nav": (
        f'<a href="#content">Skip to content</a>{MENU}<div id="content"><nav '
        'aria-label="Breadcrumb"><a href="/">Home</a></nav><p>X</p></div>',
        "pass", ""),
    # A <main> that wraps the navigation bypasses nothing.
    "a skip link to a <main> that wraps the navigation": (
        f'<a href="#main">Skip to main content</a><main id="main"><header>{NAV}'
        '</header><section><p>Ship faster</p><a href="/signup">Go</a></section>'
        '</main>', "fail", "(the main landmark wraps the navigation, no "
        "heading that opens the content)"),
    "a <main> that wraps the navigation, no skip link": (
        f'<main><header>{NAV}</header><section><p>Ship faster</p></section>'
        '</main>', "fail", "the main landmark wraps the navigation, so it "
        "bypasses nothing"),
    "a <main> that wraps the navigation, with a heading": (
        f'<main><header>{NAV}</header><section><h1>Ship faster</h1></section>'
        '</main>', "review", "a heading that opens the content can satisfy"),
    # In-page links that open panels are not skip links.
    "a search toggle before the navigation": (
        '<div class="header"><a href="/">Acme</a><a href="#search-panel" '
        f'aria-controls="search-panel">Suchen</a>{NAV}<div id="search-panel">'
        '<form><input aria-label="q"></form></div></div><div><a href="/p/1">'
        'Hammer</a><p>Text</p></div>', "fail", "no skip link found"),
    "a cart drawer link before the navigation": (
        f'<header><a href="/">Acme</a><a href="#cart">Warenkorb</a>{NAV}'
        '</header><div><a href="/p/1">Shirt</a></div><div id="cart" role='
        '"dialog" aria-label="Cart"><a href="/cart">View cart</a></div>',
        "fail", "no skip link found"),
    # A dialog is not the page.
    "a region picker open over a hidden page": (
        '<div id="app" inert aria-hidden="true"><a href="#main">Skip to '
        f'content</a><header>{NAV}</header><main id="main"><h1>X</h1></main>'
        '</div><div role="dialog" aria-modal="true" aria-label="Region"><h2>'
        'Choose your region</h2><nav aria-label="Regions"><a href="/us/">US'
        '</a><a href="/uk/">UK</a></nav></div>', "n/a", ""),
    "a consent dialog with many links over a hidden page": (
        f'<div aria-hidden="true"><header>{NAV}</header><main><h1>X</h1></main>'
        '</div><div role="dialog" aria-modal="true" aria-label="Privacy"><ul>'
        + "".join(f'<li><a href="https://v{i}.example/privacy">Policy</a></li>'
                  for i in range(20)) + '</ul></div>', "n/a", ""),
    "a consent dialog over a visible page": (
        f'<a href="#main">Skip to content</a><header>{NAV}</header><main '
        'id="main"><h1>X</h1></main><div role="dialog" aria-label="Privacy">'
        '<a href="/privacy">Policy</a><button>OK</button></div>', "pass", ""),
    # What a heading must be to open the content.
    "a back link, then the heading": (
        f'<header>{NAV}</header><div class="post"><a href="/blog">&larr; Back '
        'to blog</a><h1>Why we moved</h1><p>It started with a lease.</p></div>',
        "review", "a heading that opens the content can satisfy"),
    "a breadcrumb list, then the heading": (
        f'<header>{NAV}</header><div><ol class="breadcrumb"><li><a href="/">'
        'Home</a></li><li><a href="/a">A</a></li><li><a href="/b">B</a></li>'
        '<li><a href="/c">C</a></li><li>Data</li></ol><h1>Data</h1></div>',
        "review", "a heading that opens the content can satisfy"),
    "a post header after the site header": (
        f'<header>{NAV}</header><div class="post"><header class="post-header">'
        '<h1>Welcome</h1></header><article><p>Text.</p></article></div>',
        "review", "a heading that opens the content can satisfy"),
    "a sidebar menu after the content, no <main>": (
        '<header><a href="/">Acme</a><ul><li><a href="/about">About</a></li>'
        '</ul></header><div id="content"><h1>Post</h1><p>Text.</p></div><div '
        'class="col"><nav aria-label="Categories"><a href="/c/1">News</a>'
        '</nav></div>', "review", "a heading that opens the content can "
        "satisfy"),
    "headings only in a div footer, after short content": (
        f'<div id="header">{NAV}</div><div id="content"><p>Call us 24/7.</p>'
        '</div><div id="footer"><h4>Hours</h4><p>All day.</p></div>', "fail",
        "no heading that opens the content"),
    "headings only in a div sidebar": (
        f'<div id="header">{NAV}</div><div id="sidebar"><h3>Categories</h3>'
        '</div><div id="content"><p>Pipes.</p><a href="/more">More</a></div>',
        "fail", "no heading that opens the content"),
    "the site name as a heading, in a div header": (
        '<div id="header"><h1><a href="/"><img src="l.png" alt="Acme"></a>'
        f'</h1>{NAV}</div><div><p>Call us.</p><form><input aria-label="Name">'
        '</form></div>', "fail", "no heading that opens the content"),
    "four links before the heading": (
        f'<header>{NAV}</header><div><a href="/1">1</a><a href="/2">2</a><a '
        'href="/3">3</a><a href="/4">4</a><h1>X</h1></div>', "fail",
        "no heading that opens the content"),
    "an eyebrow line, then the heading": (
        f'<header>{NAV}</header><div><p>New season</p><h1>Mugs</h1></div>',
        "review", "a heading that opens the content can satisfy"),
    "a card heading first": (
        f'<header>{NAV}</header><div><article><header><h3>Mug</h3></header>'
        '<p>Nice.</p></article></div>', "review",
        "a heading that opens the content can satisfy"),
    "a heading after a short search form": (
        f'<header>{NAV}</header><div><form><input aria-label="q"><button>Go'
        '</button></form><h2>Results</h2></div>', "review",
        "a heading that opens the content can satisfy"),
    "a heading after a longer form": (
        f'<header>{NAV}</header><div><form><input aria-label="a"><input '
        'aria-label="b"><input aria-label="c"><button>Go</button></form><h2>'
        'Results</h2></div>', "fail", "no heading that opens the content"),
    # Layout class names are not blocks beside the content.
    "body and wrapper classes that mention a sidebar or footer": (
        '<a href="#content">Skip to content</a><header class="header-footer-'
        f'group">{NAV}</header><div class="content-sidebar-wrap"><div id='
        '"content"><h1>Hello</h1></div></div>', "pass", ""),
    "a banner inside a sidebar block, no <main>": (
        '<div id="sidebar"><header><a href="/">Acme</a></header><nav><a href='
        '"/a">About</a></nav></div><div id="content"><h1>Hello</h1></div>',
        "review", "a heading that opens the content can satisfy"),
    "a post header first, after a div header": (
        f'<div id="header"><a href="/">Acme</a>{NAV}</div><div id="content">'
        '<div class="post"><header class="entry-header"><h1>Hello</h1>'
        '</header><p>Text.</p></div></div>', "review",
        "a heading that opens the content can satisfy"),
    "hash routes before a <main> with pagination": (
        '<div class="topbar"><a href="#/">Acme</a><a href="#/listings">'
        'Listings</a></div><main><p>' + "word " * 50 + '</p><nav aria-label='
        '"Pagination"><a href="#/listings?p=2">2</a></nav></main>', "review",
        "a main landmark can satisfy"),
    "buttons that only mention the main site or skip an intro": (
        '<div id="header"><a href="/">Acme</a><button>Switch to main site'
        '</button><button>Skip intro</button><nav><a href="/shop">Shop</a>'
        '<button>Back to main menu</button></nav></div><div id="content"><p>'
        'Welcome.</p><a href="/shop">Shop now</a></div>', "fail",
        "no skip link found before the navigation"),
    "a heading after a long introduction": (
        f'<header>{NAV}</header><div><p>{"word " * 60}</p><h2>Later</h2></div>',
        "fail", "no heading that opens the content"),
    "an empty heading": (
        f'<header>{NAV}</header><div><h1> </h1><p>X</p></div>', "fail",
        "no heading that opens the content"),
}

LONG = "word " * 70
L10 = "".join(f'<a href="/n{i}">N{i}</a>' for i in range(10))
#: The independent review of Part L (N12), each case confirmed in Chromium.
SHAPES.update({
    # False FAILs.
    "no navigation element: a skip link after a six-link cookie notice": (
        '<div class="cookie">' + "".join(f'<a href="/c{i}">C{i}</a>'
                                         for i in range(6))
        + f'</div><a href="#c">Skip to content</a><div class="menu">{LINKS16}'
        f'</div><div id="c"><p>{LONG}</p></div>', "pass", ""),
    "a list of links and nothing else (link in bio)": (
        '<ul>' + "".join(f'<li><a href="https://l{i}.example/">L{i}</a></li>'
                         for i in range(16)) + '</ul>', "review",
        "the repeated blocks cannot be told from the content"),
    "content first, then a 15-link footer": (
        f'<div><p>{LONG}</p></div><footer>{LINKS16}</footer>', "n/a", ""),
    "a one-link navigation is not a block": (
        f'<nav><a href="/">Home</a></nav><div><p>{LONG}</p></div>', "review",
        "this is not established as a failure"),
    "G124: a one-page site's in-page navigation, no heading in the hero": (
        f'<nav><a href="#about">About</a><a href="#work">Work</a></nav><div>'
        f'<p>{LONG}</p></div><section id="about"><h2>About</h2></section>'
        '<section id="work"><h2>Work</h2></section>', "review",
        "a one-page site's navigation that links to its sections (G124) can "
        "satisfy 2.4.1"),
    "G124 needs every link in-page and present": (
        f'<nav><a href="#about">About</a><a href="/blog">Blog</a></nav><div>'
        f'<p>{LONG}</p></div><section id="about"><h2>About</h2></section>',
        "fail", "no skip link found before the navigation"),
    "G123: a link at the start of the navigation to its end": (
        '<nav><a href="#end">Skip navigation</a><a href="/a">A</a><a href='
        f'"/b">B</a><span id="end" tabindex="-1"></span></nav><div><p>{LONG}'
        '</p></div>', "pass", ""),
    "G123 only when nothing of the navigation follows the target": (
        '<nav><a href="#mid">Skip navigation</a><a href="/a">A</a><span id='
        f'"mid"></span><a href="/b">B</a></nav><div><p>{LONG}</p></div>',
        "fail", "which does not lead past the navigation"),
    # False passes.
    "a skip link after the primary navigation, before a section nav": (
        f'<header><nav>{L10}</nav></header><a href="#main">Skip to content'
        '</a><nav aria-label="Section"><a href="/g">G</a></nav><main id='
        '"main"><h1>X</h1></main>', "review", "comes after 10 links"),
    "a skip link as the navigation's last item": (
        f'<header><nav>{L10}<a href="#main">Skip to content</a></nav>'
        '</header><main id="main"><h1>X</h1></main>', "review",
        "comes after 10 links"),
    "a skip link after the logo and two header links": (
        '<header><a href="/">Acme</a><a href="/login">Log in</a><a href='
        f'"/cart">Cart</a><a href="#main">Skip to content</a>{NAV}</header>'
        '<main id="main"><h1>X</h1></main>', "pass", ""),
    "a skip link out of the tab order, <main> present": (
        f'<a href="#main" tabindex="-1">Skip to content</a><header>{NAV}'
        '</header><main id="main"><h1>X</h1></main>', "review",
        "a negative tabindex takes it out of the tab order"),
    "a skip link out of the tab order, nothing else": (
        f'<a href="#c" tabindex="-1">Skip to content</a><header>{NAV}'
        f'</header><div id="c"><p>{LONG}</p></div>', "fail",
        "out of the tab order, so no keyboard user reaches it, and nothing "
        "else bypasses"),
    "a target only inside <noscript>": (
        f'<a href="#c">Skip to content</a><header>{NAV}</header><noscript>'
        '<div id="c">x</div></noscript><main><h1>X</h1></main>', "review",
        "no element with that id"),
    "a target only inside a <template>": (
        f'<a href="#c">Skip to content</a><header>{NAV}</header><template>'
        '<div id="c">x</div></template><main><h1>X</h1></main>', "review",
        "no element with that id"),
})

L8 = "".join(f'<a href="/m{i}">M{i}</a>' for i in range(8))
#: The independent review of Part L's own changes (round 2).
SHAPES.update({
    # An invalid tabindex is no tabindex: the link stays in the tab order.
    **{f"a skip link with tabindex={ti}": (
        f'<a href="#c" tabindex={ti}>Skip to content</a><header><a href="/">'
        f'Logo</a><nav>{L8}</nav></header><div id="c"><p>{LONG}</p></div>',
        "pass", "") for ti in ('""', '"0.5"', '"abc"')},
    "a skip link with tabindex=\" -1\"": (
        f'<a href="#c" tabindex=" -1">Skip to content</a><header><a href="/">'
        f'Logo</a><nav>{L8}</nav></header><div id="c"><p>{LONG}</p></div>',
        "fail", "out of the tab order"),
    # Blocks after the content lead nothing.
    "no <main>, no heading: a navigation after the text": (
        f'<div><p>{LONG}</p></div><nav><a href="/prev">Prev</a><a href='
        '"/next">Next</a></nav>', "review",
        "this is not established as a failure"),
    "a header inside the footer is not the banner": (
        f'<div><p>{LONG}</p></div><footer><header><a href="/a">A</a><a href='
        f'"/b">B</a></header></footer><div>{LINKS16}</div>', "review",
        "this is not established as a failure"),
    # G124 only on a one-page site, never for toggles, and not late.
    "G124: in-page promotion links above a site menu": (
        '<nav aria-label="Promo"><a href="#sale">Sale</a><a href="#news">News'
        f'</a></nav><header><a href="/">Logo</a><nav>{L8}</nav></header><main>'
        '<section id="sale"><h2>Sale</h2></section><section id="news"><h2>'
        'News</h2></section></main>', "review", "No skip link"),
    "G124: a one-page site with a link home in the header": (
        '<header><a href="/">Jane</a><nav><a href="#about">About</a><a href='
        '"#work">Work</a></nav></header><section id="about"><h2>About</h2>'
        '</section><section id="work"><h2>Work</h2></section>', "review",
        "No skip link"),
    "G124 is not panel toggles": (
        '<nav><a href="#search" uk-toggle>Search</a><a href="#offcanvas" '
        'uk-toggle>Menu</a></nav><div id="search"><form><input aria-label="q">'
        f'</form></div><div id="offcanvas"><nav>{L8}</nav></div><div><p>{LONG}'
        '</p></div>', "fail", "no skip link found before the navigation"),
    "G124 after a header of five controls": (
        '<header><a href="#top">Top</a><button>A</button><button>B</button>'
        '<button>C</button><button>D</button></header><nav><a href="#a">A</a>'
        '<a href="#b">B</a></nav><div><p>' + "word " * 70 + '</p></div>'
        '<section id="a"><h2>A</h2></section><section id="b"><h2>B</h2>'
        '</section>', "review", "(G124) can satisfy 2.4.1"),
    # A sidebar's links may come first: still read.
    "twenty links in an <aside> before the content": (
        "<aside>" + "".join(f'<a href="/s{i}">S{i}</a>' for i in range(20))
        + f'</aside><div><p>{LONG}</p></div>', "review",
        "this is not established as a failure"),
    # The review of round 2 (Part L, round 3).
    "G124 with a social link and no <main>": (
        '<header><a href="#top">Jane</a><nav><a href="#about">About</a><a '
        'href="#work">Work</a></nav><a href="https://social.example/jane" '
        f'aria-label="Social">S</a></header><div><p>{LONG}</p></div><section '
        'id="about"><h2>About</h2></section><section id="work"><h2>Work</h2>'
        '</section>', "review", "(G124) can satisfy 2.4.1"),
    "a broken skip link on a one-page site": (
        '<a href="#nope">Skip to content</a><nav><a href="#about">About</a>'
        f'<a href="#work">Work</a></nav><div><p>{LONG}</p></div><section id='
        '"about"><h2>About</h2></section><section id="work"><h2>Work</h2>'
        '</section>', "review", "no element with that id; a one-page site's "
        "navigation that links to its sections (G124) can still satisfy"),
    "a cookie notice above the page header hides no failure": (
        '<div role="region" aria-label="Cookies"><p>' + "We use cookies to "
        "improve your experience and measure use. " * 6 + '</p><button>Accept'
        f'</button></div><header><a href="/">Acme</a>{NAV}</header><div><p>'
        f'{LONG}</p></div>', "fail", "no skip link found before the "
        "navigation"),
    "a language menu above the navigation hides no failure": (
        '<div class="top"><select aria-label="Language">' + "".join(
            f"<option>Language {i}</option>" for i in range(30))
        + f'</select></div>{NAV}<div><p>{LONG}</p></div>', "fail",
        "no skip link found before the navigation"),
    "an off-canvas menu hidden by CSS before the skip link": (
        '<div class="offcanvas" id="menu" tabindex="-1">' + "".join(
            f'<a href="/o{i}">O{i}</a>' for i in range(12)) + '</div><a href='
        f'"#main">Skip to content</a><header>{NAV}</header><main id="main">'
        '<h1>X</h1></main>', "pass", ""),
    # Late without a navigation: twenty links before the skip link.
    "no navigation: a skip link after twenty links": (
        "<div>" + "".join(f'<a href="/t{i}">T{i}</a>' for i in range(20))
        + '</div><div><p>Intro.</p><a href="#c">Skip to content</a></div>'
        f'<div id="c"><p>{LONG}</p></div>', "review", "comes after 20 links"),
})

HEADER = f'<header><a href="/">Acme</a>{NAV}</header>'
SECTIONS = ('<section id="about"><h2>About</h2></section><section id="work">'
            '<h2>Work</h2></section>')
BARE = "Lorem ipsum dolor sit amet, consectetur adipiscing. " * 6
#: The review of round 3 (Part M).
SHAPES.update({
    # A heading above the page header is not the start of the content.
    "a notice's heading above the page header hides no failure": (
        '<div class="notice"><h2>Free shipping</h2><p>On orders over 50.</p>'
        f'</div>{HEADER}<div><p>{LONG}</p></div>', "fail",
        "no skip link found before the navigation"),
    "a visually hidden site heading above the header hides no failure": (
        f'<h1 class="sr-only">Acme</h1>{HEADER}<div><p>{LONG}</p></div>',
        "fail", "no skip link found before the navigation"),
    "a heading after the header still opens the content": (
        f'<h2 class="sr-only">Acme</h2>{HEADER}<div><h1>Mugs</h1><p>{LONG}'
        '</p></div>', "review", "a heading that opens the content"),
    # Text is placed where it is, not where its parent starts.
    "text written straight into <body>: a navigation after it leads nothing": (
        f'<header><a href="/">Acme</a></header>{BARE}{NAV}', "review",
        "this is not established as a failure"),
    "text in a wrapper that holds the header: a navigation after it": (
        f'<div id="wrap"><header><a href="/">Acme</a></header>{BARE}{NAV}'
        '</div>', "review", "this is not established as a failure"),
    "text straight into <body> after the header leaves its navigation leading": (
        f'{HEADER}{BARE}', "fail", "no skip link found before the navigation"),
    # G124: a link home or to the top of the page goes nowhere else.
    "G124 with a link home in the navigation": (
        '<header><nav><a href="/">Home</a><a href="#about">About</a><a href='
        f'"#work">Work</a></nav></header><div><p>{LONG}</p></div>{SECTIONS}',
        "review", "(G124) can satisfy 2.4.1"),
    "G124 with a link to #top and no such element": (
        '<header><nav><a href="#top">Home</a><a href="#about">About</a><a '
        f'href="#work">Work</a></nav></header><div><p>{LONG}</p></div>'
        f'{SECTIONS}', "review", "(G124) can satisfy 2.4.1"),
    "G124 with a link to the page top": (
        '<span id="page-top"></span><header><nav><a href="#page-top">Acme</a><a href="#about">About</a>'
        f'<a href="#work">Work</a></nav></header><div><p>{LONG}</p></div>'
        f'{SECTIONS}', "review", "(G124) can satisfy 2.4.1"),
    "G124 needs two links to sections": (
        '<header><nav><a href="/">Home</a><a href="#top">Top</a><a href='
        f'"#about">About</a></nav></header><div><p>{LONG}</p></div>{SECTIONS}',
        "fail", "no skip link found before the navigation"),
    "a hash-route menu is another page: no G124": (
        '<nav aria-label="Promo"><a href="#about">Sale</a><a href="#work">New'
        '</a></nav><header><nav><a href="#/shop">Shop</a><a href="#/blog">Blog'
        f'</a><a href="#/cart">Cart</a></nav></header><div><p>{LONG}</p></div>'
        f'{SECTIONS}', "fail", "no skip link found before the navigation"),
})


class TestShapes(unittest.TestCase):
    def test_each_shape(self):
        for name, (body, want, fragment) in SHAPES.items():
            with self.subTest(shape=name):
                got, message = outcome(page(body))
                self.assertEqual(got, want, message)
                self.assertIn(fragment, message)

    def test_a_working_skip_link_is_never_reported_as_broken(self):
        for name, (body, want, _) in SHAPES.items():
            if want == "pass":
                with self.subTest(shape=name):
                    self.assertEqual(eval_cli(page(body), "--fail-on", "any",
                                              "--strict"), 0)


#: The independent review's cases for rulebook 0.3.0 (N4), verbatim.
REVIEW_CASES = {
    "c1: WordPress skip link to a missing #content, <main> present": (
        '<a class="skip-link screen-reader-text" href="#content">Skip to '
        'content</a><header id="masthead" class="site-header"><a href="/" '
        'class="custom-logo-link"><img src="/logo.png" alt="Acme Store"></a>'
        '<nav id="site-navigation" aria-label="Primary"><ul><li><a href="/shop">'
        'Shop</a></li><li><a href="/about">About</a></li><li><a href="/contact">'
        'Contact</a></li></ul></nav></header><main id="primary" class="site-'
        'main"><h1>Blue Mug</h1><p>A sturdy mug.</p></main><footer><p>&copy; '
        'Acme</p></footer>', "review", 0, 1),
    "c2: headings only in a footer block": (
        '<div id="header"><a href="/" class="logo"><img src="/logo.png" alt='
        '"Acme Plumbing"></a><nav><ul><li><a href="/services">Services</a></li>'
        '<li><a href="/areas">Areas</a></li><li><a href="/reviews">Reviews</a>'
        '</li><li><a href="/contact">Contact</a></li></ul></nav></div><div id='
        '"content"><p><strong>Call us 24/7</strong> at 555-0100, or send a '
        'message.</p><form action="/send" method="post"><label for="n">Name'
        '</label><input id="n" name="n"><button type="submit">Send</button>'
        '</form></div><div id="footer"><h4>Hours</h4><p>Mon-Sun, all day.</p>'
        '<h4>Find us</h4><p>1 Main St.</p></div>', "fail", 1, 1),
    "c3: only the logo is a heading": (
        '<header><h1 class="site-title"><a href="/"><img src="/logo.png" alt='
        '"Acme Plumbing"></a></h1><nav><ul><li><a href="/services">Services'
        '</a></li><li><a href="/areas">Areas</a></li><li><a href="/reviews">'
        'Reviews</a></li><li><a href="/contact">Contact</a></li></ul></nav>'
        '</header><div id="content"><p><strong>Call us 24/7</strong> at '
        '555-0100.</p><form action="/send" method="post"><label for="n">Name'
        '</label><input id="n" name="n"><button type="submit">Send</button>'
        '</form></div><footer><p>&copy; Acme</p></footer>', "fail", 1, 1),
    "c4: a scroll arrow after the navigation, no <main>": (
        '<div class="navbar"><a href="/" class="brand"><img src="/logo.svg" '
        'alt="Acme Studio"></a><nav><a href="/work">Work</a><a href="/about">'
        'About</a><a href="/contact">Contact</a></nav></div><div class="hero">'
        '<p class="hero-title">We design brands.</p><a href="#content" class='
        '"scroll-arrow" aria-label="Scroll to content"><img src="/arrow.svg" '
        'alt=""></a></div><div id="content" class="section"><p class="section'
        '-title">Selected work</p><p>Lorem ipsum.</p></div>', "fail", 1, 1),
    "c4b: the same arrow inside <main>": (
        '<header class="navbar"><a href="/" class="brand"><img src="/logo.svg" '
        'alt="Acme Studio"></a><nav><a href="/work">Work</a><a href="/about">'
        'About</a><a href="/contact">Contact</a></nav></header><main><div '
        'class="hero"><h1>We design brands.</h1><a href="#content" class='
        '"scroll-arrow" aria-label="Scroll to content"><img src="/arrow.svg" '
        'alt=""></a></div><section id="content"><h2>Selected work</h2><p>Lorem'
        ' ipsum.</p></section></main>', "review", 0, 1),
    "c5: a skip link after an app's top bar": (
        '<div id="root"><div class="app"><div class="topbar"><a href="/" '
        'class="brand">Acme</a><nav><a href="/orders">Orders</a><a href='
        '"/customers">Customers</a><a href="/settings">Settings</a></nav></div>'
        '<a href="#content" class="skip">Skip to main content</a><div id='
        '"content" class="page"><div class="page-title">Orders</div><p>No '
        'orders yet.</p></div></div></div>', "fail", 1, 1),
    "c6: page hidden behind an age gate": (
        '<div id="__next" aria-hidden="true" inert><a href="#main">Skip to main'
        ' content</a><header><a href="/"><img src="/logo.svg" alt="Hoppy Days">'
        '</a><nav aria-label="Main"><a href="/shop">Shop</a><a href="/beers">'
        'Our beers</a></nav></header><main id="main"><h1>Shop</h1></main></div>'
        '<div role="dialog" aria-modal="true" aria-label="Age verification">'
        '<p>Are you 21 or older?</p><button type="button">Yes, enter</button>'
        '<button type="button">No</button></div>', "n/a", None, None),
    # A browser attaches the declarative root and renders its content, so
    # a file run reads it too (Part O). But the skip link inside does not
    # work: a fragment looks only in the document, which has no #main
    # (Chromium 141: the hash changes, :target stays false, focus stays).
    "c7: declarative shadow DOM": (
        '<acme-app><template shadowrootmode="open"><a href="#main" class='
        '"skip-link">Skip to main content</a><header><nav aria-label="Main">'
        '<a href="/guides">Guides</a></nav></header><main id="main"><h1>Getting'
        ' started</h1></main></template></acme-app>', "review", 0, 1),
}


class TestReviewCases(unittest.TestCase):
    def test_verdicts_and_gate(self):
        for name, (body, want, gate, strict) in REVIEW_CASES.items():
            with self.subTest(case=name):
                html = page(body)
                self.assertEqual(outcome(html)[0], want)
                if gate is None:
                    continue
                self.assertEqual(eval_cli(html, "--fail-on", "tier1"), gate)
                self.assertEqual(eval_cli(html, "--fail-on", "tier1",
                                          "--strict"), strict)


if __name__ == "__main__":
    unittest.main()
