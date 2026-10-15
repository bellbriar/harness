"""Write src/bellbriar_harness/css_properties.py: the CSS property names the
harness's Chromium knows, which an @supports test in a page's own <style>
is read against (style._supports, R5K-4).

    python tools/make_css_properties.py      # needs the browser extra

A name counts when `CSS.supports(name, "inherit")` is true in that
browser: every property takes `inherit`, and nothing else is a property.
The names tried are every property its CSSStyleDeclaration exposes
(camelCase accessors, written as CSS writes them, with and without a
leading "-" for a vendor's prefix), every name getComputedStyle lists,
and each of those with each prefix a vendor has used (-epub-caption-side
has no accessor). Run it again when the harness moves to another
Chromium, and say which in the module it writes.
"""
from __future__ import annotations

import sys
from pathlib import Path

OUT = (Path(__file__).resolve().parent.parent / "src" / "bellbriar_harness"
       / "css_properties.py")

_LIST = """() => {
  const out = new Set();
  const keys = [];
  const st = document.body.style;
  for (const k in st) keys.push(k);
  for (const k of Object.getOwnPropertyNames(CSSStyleDeclaration.prototype))
    keys.push(k);
  for (const k of keys) {
    if (typeof k !== "string" || /^\\d+$/.test(k)) continue;
    let h = k;
    if (/[A-Z]/.test(k)) h = k.replace(/[A-Z]/g, (m) => "-" + m.toLowerCase());
    // A vendor's prefix (webkitX, epubX) is written -webkit-x, -epub-x.
    for (const name of [h, "-" + h])
      if (CSS.supports(name, "inherit")) out.add(name);
  }
  const cs = getComputedStyle(document.body);
  for (let i = 0; i < cs.length; i++)
    if (CSS.supports(cs[i], "inherit")) out.add(cs[i]);
  // Aliases no accessor exposes (-epub-caption-side): each name found,
  // with each prefix a vendor has used.
  const prefixes = ["-webkit-", "-epub-", "-moz-", "-ms-", "-o-"];
  for (const name of [...out]) {
    const base = name.replace(/^-(webkit|epub|moz|ms|o)-/, "");
    for (const prefix of ["", ...prefixes])
      if (CSS.supports(prefix + base, "inherit")) out.add(prefix + base);
  }
  return [...out].sort();
}"""


def main() -> int:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            names = page.evaluate(_LIST)
            version = browser.version
        finally:
            browser.close()
    if not names or any(not isinstance(n, str) or not n.isascii()
                        for n in names):
        print("unexpected property names", file=sys.stderr)
        return 1
    lines = [
        '"""The CSS property names Chromium ' + version + ' knows (CSS.supports('
        'name,',
        '"inherit")), which an @supports test in a page\'s own <style> is read',
        "against (style._supports, R5K-4). Written by",
        'tools/make_css_properties.py: do not edit by hand."""',
        "",
        f"CHROMIUM = {version!r}",
        "",
        "PROPERTIES = frozenset((",
    ]
    row = "   "
    for name in names:
        piece = f" {name!r},"
        if len(row) + len(piece) > 79:
            lines.append(row)
            row = "   "
        row += piece
    lines.append(row)
    lines.append("))")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({len(names)} names, Chromium {version})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
