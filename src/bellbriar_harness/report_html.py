"""Self-contained single-file HTML report (no external assets), drawn from
the JSON report (report.build_report), so the two never disagree.

Layout (A7): the coverage banner and the run's numbers; the rules with
findings, with their counts; the pages and their Tier-1 status; then the
findings grouped by rule — what the rule checks, why it matters and how to
fix it, with examples (A6, guidance.py) — and within each rule by page;
then how each page was read (its capture record, P5-08). Findings that
read the same (an element with the same `about` — tag, start of its text
and first descendants — and the same message) are shown once with their
count, on one page or across pages (L46); a table shows at most ROW_LIMIT
rows, and the JSON report lists every finding.

The report itself must satisfy the harness: semantic structure, labeled
regions, sufficient contrast, no reliance on color alone. The coverage
banner and the footer are mandatory — reports never imply conformance.
"""
from __future__ import annotations

import html as H

from .guidance import guidance_for
from .model import FAIL, IMPACT_ORDER

#: The most rows one rule's table shows for one page (or across pages);
#: the JSON report lists every finding.
ROW_LIMIT = 100
#: The most locators one grouped row lists.
LOCATOR_LIMIT = 10

_CSS = """
:root{--ink:#212832;--paper:#FAF8F3;--rule:#d8d2c4;--amber:#7E5C24;
--amberbg:#F3EAD8;--fail:#8a2a2a;--review:#7E5C24;--ok:#2f5e3f;
--link:#1d4f91}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);
font:15px/1.55 Georgia,'Times New Roman',serif;padding:32px 16px;
overflow-wrap:anywhere}
main{max-width:1000px;margin:0 auto}h1,h2,h3{font-weight:600;line-height:1.25}
h1{font-size:26px;margin:0 0 4px}h2{font-size:21px;margin:40px 0 10px;
border-top:1px solid var(--rule);padding-top:18px}h3{font-size:17px;
margin:28px 0 6px}a{color:var(--link)}
.mono{font-family:'Courier New',monospace;font-size:12.5px;
overflow-wrap:anywhere}
.banner{background:var(--amberbg);border:1px solid var(--amber);
border-radius:6px;padding:14px 16px;margin:20px 0}
.banner strong{color:var(--amber)}
table{border-collapse:collapse;width:100%;margin:10px 0 22px;font-size:14px;
table-layout:fixed}
caption{text-align:left;font-weight:600;padding:6px 0;overflow-wrap:anywhere}
th,td{border:1px solid var(--rule);padding:6px 8px;text-align:left;
vertical-align:top;overflow-wrap:anywhere}th{background:#efe9db}
.v-fail{color:var(--fail);font-weight:700}.v-review{color:var(--review);
font-weight:700}.v-ok{color:var(--ok);font-weight:700}
.cards{display:flex;gap:14px;flex-wrap:wrap;margin:14px 0}
.card{border:1px solid var(--rule);border-radius:6px;padding:12px 16px;
min-width:180px;flex:1 1 180px;background:#fff}
.card .n{font-size:24px;font-weight:700}
footer{margin-top:40px;border-top:1px solid var(--rule);padding-top:14px;
font-size:13px;color:#4a4437}
code{background:#efe9db;padding:1px 4px;border-radius:3px}
pre{background:#fff;border:1px solid var(--rule);border-radius:4px;
padding:8px 10px;margin:4px 0 12px;white-space:pre-wrap;
overflow-wrap:anywhere;font-size:13px}
pre code{background:none;padding:0}
.rule{border:1px solid var(--rule);border-radius:6px;background:#fff;
padding:4px 16px 8px;margin:18px 0}
details{margin:8px 0 14px}summary{cursor:pointer;font-weight:600}
.c-rule{width:34%}.c-sc{width:14%}.c-n{width:10%}.c-verdict{width:13%}
.c-impact{width:10%}.c-where{width:24%}.c-msg{width:28%}.c-el{width:25%}
.c-page{width:30%}.c-read{width:18%}.c-t1{width:22%}
@media (max-width:600px){body{padding:20px 8px}th,td{padding:4px 5px}
.rule{padding:4px 8px 6px}table{font-size:13px}}
.skip{margin:0 0 10px;font-size:14px}
dl{display:grid;grid-template-columns:minmax(120px,max-content) 1fr;
gap:4px 14px;margin:8px 0 18px}dt{font-weight:600}dd{margin:0;
overflow-wrap:anywhere}
"""


def _e(value) -> str:
    return H.escape("" if value is None else str(value))


def _pct(x: float | None) -> str:
    """None means nothing was measured — never render that as a percentage."""
    if x is None:
        return "n/a"
    return f"{x * 100:.1f}%"


def _plural(n: int, one: str, many: str | None = None) -> str:
    return f"{n:,} {one if n == 1 else (many or one + 's')}"


def _counted(n: int) -> str:
    """A count in words a sentence can start with: "none" for 0."""
    return f"{n:,}" if n else "none"


def _when(stamp: str | None) -> str:
    """"2026-10-11T05:52:54Z" as "2026-10-11 05:52 UTC"."""
    if not stamp or len(stamp) < 16:
        return _e(stamp or "")
    return _e(stamp[:10] + " " + stamp[11:16] + " UTC")


def _verdict(f: dict) -> tuple[str, str]:
    """(css class, label) for a finding: FAIL, FAIL (heuristic) — a
    probable failure — or REVIEW; a failure in a vendor's markup says so,
    and is not counted."""
    if f["verdict"] != FAIL:
        return "v-review", "REVIEW"
    qualifiers = []
    basis = f.get("verdict_basis") or "sc"
    if basis != "sc":
        qualifiers.append(basis)
    if not f.get("owned", True):
        qualifiers.append("3rd-party")
        return "v-review", f"FAIL ({', '.join(qualifiers)})"
    return "v-fail", f"FAIL ({', '.join(qualifiers)})" if qualifiers \
        else "FAIL"


def _origin_note(f: dict) -> str:
    """Who inserted the markup a finding sits in, where a capture recorded
    it: a known vendor's script (reported, not counted) or another
    origin's (counted as yours)."""
    detail = f.get("origin_detail") or ""
    if f.get("origin") == "third-party":
        return ("In markup a vendor's script inserted"
                + (f" ({_e(detail)})" if detail else "")
                + ": reported, not counted as yours.")
    if f.get("origin") == "cross-origin":
        return ("In markup a script from another origin inserted"
                + (f" ({_e(detail)})" if detail else "")
                + ": counted as yours (--third-party-origin names a "
                  "vendor).")
    return ""


def _locator(f: dict) -> str:
    """A finding's line, and its locator: the selector that finds it, and
    one more per shadow root it is inside (each matched in the shadow root
    of the element the one before it found)."""
    out = [f"line {f['line']}"] if f.get("line") is not None else []
    steps = f.get("selector") or []
    if steps:
        out.append("<code>" + _e(steps[0]) + "</code>")
        out.extend("&#8627; shadow root: <code>" + _e(s) + "</code>"
                   for s in steps[1:])
    return "<br>".join(out)


def _group_key(f: dict) -> tuple:
    """Findings that read the same: the same verdict, impact, message,
    owner and element (its `about`: its tag, the start of its text and its
    first descendants; with none, its markup); a finding about the page
    has no element."""
    return (f["verdict"], f.get("owned", True), f["impact"], f["message"],
            f.get("about") or f.get("snippet") or "",
            f.get("origin_detail") or "", f.get("in_baseline"))


def _sorted_groups(groups: list[list]) -> list[list]:
    """Failures in the site's own markup first, then by impact."""
    return sorted(groups, key=lambda g: (
        0 if g[0]["verdict"] == FAIL and g[0].get("owned", True) else 1,
        IMPACT_ORDER.get(g[0]["impact"], 9)))


def _groups(findings: list) -> list[list]:
    """`findings` grouped by _group_key, in the order each first appears;
    then failures before reviews, by impact."""
    groups: dict = {}
    for f in findings:
        groups.setdefault(_group_key(f), []).append(f)
    return _sorted_groups(list(groups.values()))


def _where_cell(group: list) -> str:
    shown = group[:LOCATOR_LIMIT]
    parts = []
    if len(group) > 1:
        parts.append(f"<strong>&times;{len(group):,}</strong>")
    for f in shown:
        loc = _locator(f)
        if loc:
            parts.append(loc)
    if len(group) > len(shown):
        parts.append(f"and {len(group) - len(shown):,} more (in the JSON "
                     "report)")
    note = _origin_note(group[0])
    if note:
        parts.append(note)
    return "<br>".join(parts) or "the page"


def _counts(findings: list) -> str:
    fails = sum(1 for f in findings if f["verdict"] == FAIL
                and f.get("owned", True))
    reviews = sum(1 for f in findings if f["verdict"] != FAIL
                  and f.get("owned", True))
    vendor = sum(1 for f in findings if not f.get("owned", True))
    parts = []
    if fails:
        parts.append(_plural(fails, "failure"))
    if reviews:
        parts.append(_plural(reviews, "review item"))
    if vendor:
        parts.append(_plural(vendor, "finding") + " in vendor markup")
    return ", ".join(parts) or "no findings"


def _findings_table(caption: str, groups: list,
                    pages_col: list | None = None) -> str:
    """One table of grouped findings, each group a list of findings that
    read the same. `pages_col`, for the table of findings on more than one
    page, gives each group's pages: [(page label, how many on it)]."""
    head = ("<th scope=\"col\" class=\"c-verdict\">Verdict</th>"
            "<th scope=\"col\" class=\"c-impact\">Impact</th>"
            "<th scope=\"col\" class=\"c-where\">Where</th>"
            "<th scope=\"col\" class=\"c-msg\">Message</th>"
            "<th scope=\"col\" class=\"c-el\">Element</th>"
            + ("<th scope=\"col\" class=\"c-where\">Pages</th>"
               if pages_col is not None else ""))
    rows = []
    for i, group in enumerate(groups[:ROW_LIMIT]):
        f = group[0]
        cls, label = _verdict(f)
        if f.get("in_baseline") is False:
            label += " · new"           # not in the --baseline (A10)
        if pages_col is None:
            where = _where_cell(group)
        else:
            on = pages_col[i]
            where = ("an element that reads the same on each page listed"
                     + (f"; &times;{len(group):,} in all" if len(group) > len(
                         on) else "")
                     + (". " + _origin_note(f) if _origin_note(f) else ""))
        cells = (f"<td class=\"{cls}\">{_e(label)}</td>"
                 f"<td>{_e(f['impact'])}</td>"
                 f"<td>{where}</td>"
                 f"<td>{_e(f['message'])}</td>"
                 f"<td class=\"mono\">{_e(f.get('snippet') or '')}</td>")
        if pages_col is not None:
            on = pages_col[i]
            listed = "<br>".join(_e(label) for label, _n in on[:LOCATOR_LIMIT])
            more = (f"<br>and {len(on) - LOCATOR_LIMIT:,} more"
                    if len(on) > LOCATOR_LIMIT else "")
            cells += (f"<td><strong>{len(on):,} pages</strong><br>"
                      f"{listed}{more}</td>")
        rows.append(f"<tr>{cells}</tr>")
    if len(groups) > ROW_LIMIT:
        hidden = groups[ROW_LIMIT:]
        n = sum(len(g) for g in hidden)
        fails = sum(1 for g in hidden for f in g if f["verdict"] == FAIL)
        # Not in the --baseline: the rows above mark theirs (R4B-15).
        fresh = sum(1 for g in hidden for f in g
                    if f.get("in_baseline") is False)
        also = [x for x in (f"{fails:,} of them failures" if fails else "",
                            f"{fresh:,} of them new" if fresh else "") if x]
        span = 6 if pages_col is not None else 5
        rows.append(f"<tr><td colspan=\"{span}\">{n:,} more findings of "
                    f"this rule here"
                    + (", " + " and ".join(also) + "," if also else "")
                    + " are not shown; the JSON report lists every one."
                    "</td></tr>")
    return (f"<table><caption>{caption}</caption><thead><tr>{head}</tr>"
            f"</thead><tbody>{''.join(rows)}</tbody></table>")


def _examples(rid: str, name: str) -> str:
    """The examples shipped with the harness (guidance.py) for a rule."""
    g = guidance_for(rid)
    blocks = []
    for label, key in (("HTML, before", "html_bad"), ("HTML, after",
                                                      "html_good"),
                       ("React", "react"), ("Vue", "vue")):
        if g.get(key):
            blocks.append(f"<p>{label}:</p><pre><code>{_e(g[key])}"
                          "</code></pre>")
    if not blocks:
        return ""
    return (f"<details><summary>Fix examples for &ldquo;{_e(name)}&rdquo;: "
            f"HTML, React and Vue</summary>{''.join(blocks)}</details>")


def _meaning(basis: str | None, sc: list) -> str:
    """What a finding of a rule with this verdict basis means."""
    crit = ", ".join(sc)
    if basis == "sc":
        return (f"A FAIL here is a failure of WCAG {_e(crit)}, one W3C "
                "names.")
    if basis == "heuristic":
        return (f"A FAIL here is a probable failure of WCAG {_e(crit)}: "
                "markup alone cannot settle it, or W3C does not itself name "
                "it, so confirm each one.")
    if basis == "policy":
        return ("This rule never fails: it is stricter than this rulebook's "
                "WCAG 2.1 AA target (a pattern pled in complaints, or a WCAG "
                "2.2 criterion), so its findings are for review.")
    if basis == "best-practice":
        return ("This rule never fails: WCAG does not require this on its "
                "own, so its findings are for review.")
    if basis == "review":
        return ("This rule never fails: its findings ask for a person's "
                "review" + (f" against WCAG {_e(crit)}" if crit else "")
                + ".")
    return ""


def _rule_order(rules: dict, by_rule: dict) -> list[str]:
    """Rules with failures in the site's own markup first, by tier (1, 2,
    3, then 0) and number of failures; then the others, by tier and
    number of findings."""
    def key(rid):
        fs = by_rule[rid]
        fails = sum(1 for _p, f in fs if f["verdict"] == FAIL
                    and f.get("owned", True))
        tier = (rules.get(rid) or {}).get("tier")
        tier = tier if isinstance(tier, int) and tier > 0 else 9
        return (0 if fails else 1, tier, -(fails or len(fs)), rid)
    return sorted(by_rule, key=key)


def _understanding(url) -> str:
    """A link to the rule's Understanding document, named by its page: the
    rulebook links the document of one of the criteria it cites, not
    always the first. Only an https:// address is a link (R3A-9)."""
    if not (isinstance(url, str) and url.startswith("https://")):
        return ""
    page = url.rstrip("/").rsplit("/", 1)[-1].removesuffix(".html")
    return (f"<a href=\"{_e(url)}\">W3C's Understanding document "
            f"({_e(page)})</a>")


def _rule_section(rid: str, meta: dict, found: list, labels: list,
                  axe_version: str) -> str:
    """One rule's section: what it is, why it matters and how to fix it,
    then its findings: those on more than one page together, then each
    page's. `found` holds (page index, finding); `labels` names each
    page."""
    name = meta.get("name") or rid
    sc = meta.get("sc") or []
    parts = [f"<section class=\"rule\" aria-labelledby=\"rule-{_e(rid)}\">",
             f"<h3 id=\"rule-{_e(rid)}\">{_e(name)} "
             f"<span class=\"mono\">{_e(rid)}</span></h3>"]
    facts = []
    if sc:
        facts.append("WCAG " + _e(", ".join(sc)))
    if meta.get("tier") is not None:
        facts.append(f"Tier {_e(meta['tier'])}")
    if meta.get("engine") == "axe-core":
        facts.append("checked by axe-core"
                     + (f" {_e(axe_version)}" if axe_version else "")
                     + " in the browser")
    elif meta.get("layer"):
        facts.append("checked by Bellbriar" + (
            " in the browser" if meta.get("layer") == "rendered"
            else " on the markup"))
    link = _understanding(meta.get("understanding"))
    if link:
        facts.append(link)
    facts.append(_counts([f for _i, f in found]) + " on " + _plural(
        len({i for i, _f in found}), "page"))
    parts.append(f"<p>{' · '.join(facts)}</p>")
    meaning = _meaning(meta.get("verdict_basis"), sc)
    if meaning:
        parts.append(f"<p>{meaning}</p>")
    # Why and how, as the JSON report carries them (R3B-15).
    if meta.get("why"):
        parts.append(f"<p><strong>Why it matters.</strong> "
                     f"{_e(meta['why'])}</p>")
    if meta.get("fix"):
        parts.append(f"<p><strong>How to fix it.</strong> "
                     f"{_e(meta['fix'])}</p>")
    parts.append(_examples(rid, name))
    # Findings that read the same on more than one page: once, with the
    # pages (a site's header or footer, say).
    across: dict = {}
    if len(labels) > 1:
        for i, f in found:
            across.setdefault(_group_key(f), {}).setdefault(i, []).append(f)
        across = {k: v for k, v in across.items() if len(v) > 1}
    if across:
        groups = _sorted_groups([[f for fs in by_page.values() for f in fs]
                                 for by_page in across.values()])
        pages_col = []
        for g in groups:
            by_page = across[_group_key(g[0])]
            pages_col.append([(labels[i], len(fs)) for i, fs in
                              sorted(by_page.items())])
        n = sum(len(g) for g in groups)
        parts.append(_findings_table(
            f"{_e(rid)}: findings on more than one page "
            f"({_plural(n, 'finding')}, each reading the same on every "
            "page listed)", groups, pages_col))
    by_page: dict = {}
    for i, f in found:
        if _group_key(f) in across:
            continue
        by_page.setdefault(i, []).append(f)
    for i, fs in sorted(by_page.items()):
        parts.append(_findings_table(
            f"{_e(rid)} on {_e(labels[i])}: {_counts(fs)}", _groups(fs)))
    parts.append("</section>")
    return "".join(parts)


def _tier1_badge(score: dict, site: dict, errors: list) -> str:
    """A page's Tier-1 status, said as the console says it (R1A-7): only a
    page the rules could not read is "not evaluated"."""
    if score["tier1_clean"] is None:
        if not score.get("evaluable", True):
            why = ("Not evaluated — "
                   + (score.get("not_evaluable_reason") or
                      "the rules could not read this page"))
        elif errors:
            why = ("Tier-1 undecided — a rule raised on this page, so "
                   "its result here is unknown, not a pass")
        elif not score.get("tier1_rules_executed"):
            why = "Tier-1 undecided — no Tier-1 rule ran on this page"
        else:
            why = ("Tier-1 undecided — no Tier-1 rule that can fail "
                   "applied to this page")
        return f"<span class=\"v-review\">{_e(why)}</span>"
    if score["tier1_clean"]:
        ran_here = score.get("tier1_rules_executed")
        here = (f"{site['tier1_rules_executed']} of "
                f"{site['tier1_rules_total']}" if ran_here is None else
                f"{ran_here} of {site['tier1_rules_total']}")
        return (f"<span class=\"v-ok\">Tier-1 clean ({here} Tier-1 "
                "rules executed on this page)</span>")
    return "<span class=\"v-fail\">Tier-1 failures present</span>"


def _read_as(page: dict, source: str) -> str:
    """How a page was read, in a few words, by how the run got its pages
    (the report's `source`): files read as they are, files served on this
    machine (--render), or pages fetched from a site."""
    fetch = page.get("fetch")
    if fetch:
        if fetch.get("mode") == "rendered":
            browser = fetch.get("browser") or {}
            return ("rendered by " + _e(browser.get("name") or "a browser")
                    + (" " + _e(browser.get("version"))
                       if browser.get("version") else ""))
        if source == "render":
            return "the file as it is (not rendered)"
        return "the HTML the server sent (not rendered)"
    unread = any(e.get("rule_id") == "(the page)"
                 for e in page.get("errors") or [])
    if source == "urls":
        return "not read: it could not be fetched (its error is listed above)"
    if source == "render":
        return "not read: it could not be served (its error is listed above)"
    return ("the file, which could not be read (its error is listed above)"
            if unread else "the file as it is")


def _capture_section(i: int, page: dict, label: str, source: str) -> str:
    """One page's capture record, as the JSON report and the bundle hold it
    (P5-08): where it came from, when, how it was read, and the hash of
    exactly what the rules read."""
    fb = page["fetch"]
    rows = []

    def row(name: str, value: str) -> None:
        if value:
            rows.append(f"<dt>{name}</dt><dd>{value}</dd>")
    row("Final URL", "<span class=\"mono\">" + _e(fb.get("final_url"))
        + "</span>")
    if fb.get("requested_url") and fb.get("requested_url") != \
            fb.get("final_url"):
        row("Requested URL", "<span class=\"mono\">"
            + _e(fb.get("requested_url")) + "</span>")
    # `redirects` is the chain of URLs, the requested one first (R3A-8).
    hops = max(len(fb.get("redirects") or []) - 1, 0)
    if hops:
        row("Redirects", _plural(hops, "redirect"))
    row("HTTP status", _e(fb.get("http_status")))
    row("Captured", _e(fb.get("fetched_at")))
    read = _read_as(page, source)
    browser = fb.get("browser") or {}
    if fb.get("mode") == "rendered" and "sandbox" in browser:
        read += (", with its sandbox" if browser.get("sandbox")
                 else ", without its sandbox")
    row("Read as", read)
    if fb.get("fallback_reason"):
        row("Why not rendered", _e(fb.get("fallback_reason"))
            + ". Content built by JavaScript was not evaluated on this page.")
    vp = fb.get("viewport") or {}
    narrow = (fb.get("narrow") or {}).get("viewport") or {}
    if vp:
        row("Viewport", f"{_e(vp.get('width'))} by {_e(vp.get('height'))} "
            "CSS pixels" + (f"; also read at {_e(narrow.get('width'))} by "
                            f"{_e(narrow.get('height'))}" if narrow else ""))
    wait = fb.get("wait") or {}
    if wait.get("waited_ms") is not None:
        row("Waited", f"{_e(wait.get('waited_ms'))} ms"
            + ("" if wait.get("settled") else
               ", and the page had not settled"))
    axe = fb.get("axe") or {}
    if isinstance(axe, dict) and axe.get("version"):
        row("axe-core", _e(axe.get("version"))
            + (" (ran)" if axe.get("ran") else " (did not run)"))
    if fb.get("address_class"):
        row("Address", _e(fb.get("address_class"))
            + (f" (decided from the {_e(fb.get('address_basis'))})"
               if fb.get("address_basis") else ""))
    row("Snapshot SHA-256", "<span class=\"mono\">"
        + _e(fb.get("snapshot_sha256")) + "</span>")
    notes = fb.get("notes") or []
    if notes:
        row("Notes", "<ul>" + "".join(f"<li>{_e(n)}</li>" for n in notes)
            + "</ul>")
    return (f"<section aria-labelledby=\"page-{i}\"><h3 id=\"page-{i}\">"
            f"{_e(label)}</h3><dl>{''.join(rows)}</dl></section>")


def _labels(pages: list) -> list[str]:
    """Each page's name in the report: its path, numbered where two pages
    of the run were recorded under one (R3A-1): their URLs differ only in
    what is recorded as REDACTED."""
    count: dict = {}
    for page in pages:
        count[page["path"]] = count.get(page["path"], 0) + 1
    seen: dict = {}
    out = []
    for page in pages:
        path = page["path"]
        seen[path] = seen.get(path, 0) + 1
        out.append(f"{path} (page {seen[path]} of {count[path]} with this "
                   "name)" if count[path] > 1 else path)
    return out


def _listing(run_fetch: dict) -> str:
    """Where a URL run's pages came from, from its record (R3A-13)."""
    listing = run_fetch.get("list") or {}
    shown = run_fetch.get("pages") or 0
    if listing.get("kind") != "sitemap":
        return "the URLs given to the run"
    listed = listing.get("listed") or 0
    many = f"{listed:,}" + ("" if listing.get("complete") else " or more")
    url = f"<span class=\"mono\">{_e(listing.get('url'))}</span>"
    if listing.get("complete") and shown == listed:
        return f"the {_plural(listed, 'page')} the sitemap {url} lists"
    # Fewer than it lists: past --max-pages, or a page listed again under
    # another fragment, evaluated once (R3C-12).
    return (f"{_plural(shown, 'page')} from the sitemap {url}, which lists "
            f"{many}: a run takes at most the first "
            f"{_e(listing.get('max_pages'))} (--max-pages), and evaluates "
            "once a page listed again with another fragment")


def render(report: dict) -> str:
    """The HTML report for a JSON report (report.build_report)."""
    tool = report["tool"]
    site = report["site"]
    rules = report.get("rules") or {}
    pages = report["pages"]
    ts = _when(report.get("generated_at"))

    parts: list[str] = []
    parts.append("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">")
    parts.append("<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">")
    parts.append(f"<title>Bellbriar eval report — {ts}</title>")
    parts.append(f"<style>{_CSS}</style></head><body><main>")
    has_findings = any(page["findings"] for page in report["pages"])
    if has_findings:
        # Past the coverage, the numbers and the tables, for keyboard and
        # screen-reader users (the harness's own bb-skip-link).
        parts.append("<p class=\"skip\"><a href=\"#findings\">Skip to the "
                     "findings by rule</a></p>")
    parts.append("<h1>Bellbriar Eval Harness — run report</h1>")
    digest = report.get("rulebook_sha256") or ""
    parts.append(f"<p class=\"mono\">tool {_e(tool['name'])} v"
                 f"{_e(tool['version'])} · rulebook "
                 f"{_e(report['rulebook_version'])}"
                 + (f" (sha256 {_e(digest[:16])}…"
                    + ("" if report.get("rulebook_bundled") else
                       ", <strong>not the rulebook this harness ships</strong>")
                    + ")" if digest else "")
                 + f" · {ts} · {_e(report.get('format', ''))}</p>")
    # The versions that decide verdicts, as the JSON report and the bundle
    # record them (P5-04, R1B-11).
    libs = tool.get("libraries") or {}
    versions = [f"Python {tool['python']}"] if tool.get("python") else []
    versions += [f"{name} {value}" for name, value in libs.items()]
    versions += [f"{name} {value} (recorded in the snapshot)"
                 for name, value in (tool.get("from_snapshot") or {}).items()]
    if versions:
        parts.append("<p class=\"mono\">verdicts read with "
                     + _e(" · ".join(str(v) for v in versions)) + "</p>")

    # Layer coverage banner — mandatory.
    parts.append("<section class=\"banner\" aria-label=\"Layer coverage\">")
    parts.append(f"<strong>Coverage.</strong> {_e(report['coverage_note'])}<ul>")
    for layer in report["layers"]:
        parts.append(f"<li><strong>{_e(layer['layer'])}</strong> — "
                     f"{_e(layer['status'])}. {_e(layer['note'])}</li>")
    parts.append("</ul></section>")

    # Site summary.
    parts.append("<h2>Summary</h2><div class=\"cards\">")
    parts.append(f"<div class=\"card\"><div class=\"n\">"
                 f"{_pct(site['site_weighted_pass_rate'])}</div>weighted pass "
                 "rate (executed checks only)</div>")
    t1 = f"{site['tier1_rules_executed']} of {site['tier1_rules_total']}"
    review_only = site.get("tier1_rules_review_only", 0)
    never = f"; {review_only} of those never fail" if review_only else ""
    unevaluated = site.get("pages_not_evaluable") or 0
    decided = sum(1 for page in report["pages"]
                  if (page.get("score") or {}).get("tier1_clean") is not None)
    of_pages = (f"; of the {decided} page(s) whose Tier-1 result is known, "
                f"with {unevaluated} page(s) NOT evaluated"
                if 0 < unevaluated < len(report["pages"]) else "")
    parts.append(f"<div class=\"card\"><div class=\"n\">"
                 f"{_pct(site['pct_pages_tier1_clean'])}</div>pages with zero "
                 f"failures among executed Tier-1 rules ({t1} executed{never}"
                 f"{of_pages})</div>")
    parts.append(f"<div class=\"card\"><div class=\"n\">"
                 f"{site['total_fail_findings']:,}</div>fail findings</div>")
    parts.append(f"<div class=\"card\"><div class=\"n\">"
                 f"{site['total_needs_review']:,}</div>needs-review findings"
                 "</div></div>")
    labels = _labels(pages)
    source = report.get("source") or "files"
    base = report.get("baseline")
    if isinstance(base, dict):
        # A10: what the gate compared with, said where nobody can miss it.
        n_new = base.get("new_findings") or 0
        new_fail = base.get("new_fail_findings") or 0
        if n_new:
            what = (f"{n_new:,} of this run's findings "
                    f"{'is' if n_new == 1 else 'are'} not in it "
                    f"({_counted(new_fail)} of them "
                    f"{'a failure' if new_fail == 1 else 'failures'} in the "
                    "site's own markup), each marked “new” below. ")
        else:
            what = ("it lists every finding of this run, so none is marked "
                    "“new”. ")
        parts.append(
            "<section class=\"banner\" aria-label=\"Baseline\"><p>"
            "<strong>Compared with a baseline.</strong> This run's gate "
            "counted only the findings an earlier report did not list with "
            "the same verdict, owner, tier and impact "
            f"(SHA-256 <span class=\"mono\">{_e(base.get('sha256'))}</span>"
            + (f", made {_when(base.get('generated_at'))}"
               if base.get("generated_at") else "")
            + f", {_plural(base.get('findings') or 0, 'finding')}): "
            + what +
            "Every finding is listed and counted in the numbers above, "
            "whether the baseline lists it or not.</p></section>")
    errors = [(labels[i], e["rule_id"], e["error"])
              for i, page in enumerate(pages)
              for e in page.get("errors") or []]
    if errors:
        items = "".join(f"<li><code>{_e(rid)}</code> on "
                        f"{_e(path)}: {_e(err)}</li>"
                        for path, rid, err in errors)
        raised = any(rid != "(the page)" for _p, rid, _e in errors)
        parts.append(
            "<section class=\"banner\" aria-label=\"Incomplete run\">"
            "<p><strong>Incomplete run.</strong> The harness could not "
            "evaluate these, so their result is unknown — not a pass. Nothing "
            "here is counted for them, and this run cannot produce an "
            "evidence bundle. "
            + ("A rule that raised an error is a harness bug; please report "
               "it with the page." if raised else
               "Each line says why the page was not evaluated.")
            + f"</p><ul>{items}</ul></section>")
    shells = sum(1 for page in pages
                 if not page["score"].get("evaluable", True)
                 and not page.get("errors"))
    if shells:
        parts.append(
            "<section class=\"banner\" aria-label=\"Pages not evaluated\">"
            f"<p><strong>Not evaluated.</strong> "
            f"{shells} page(s) gave the static rules nothing to read: "
            "client-rendered app shells, whose content JavaScript builds, "
            "or pages still empty when captured. They have no pass rate and "
            "are not counted as clean; each one's reason is in the table of "
            "pages below.</p></section>")
    third_fails = site.get("total_third_party_fail_findings") or 0
    third_reviews = site.get("total_third_party_needs_review") or 0
    if third_fails or third_reviews:
        what = " and ".join(x for x in (
            f"{third_fails} failure(s)" if third_fails else "",
            f"{third_reviews} review item(s)" if third_reviews else "") if x)
        vendors = sorted({f.get("origin_detail") for page in pages
                          for f in page["findings"]
                          if f.get("origin") == "third-party"
                          and f.get("origin_detail")})
        parts.append(
            "<section class=\"banner\" aria-label=\"Third-party findings\">"
            f"<p><strong>Third-party markup.</strong> {what} "
            "were found "
            "in markup injected by vendor scripts — consent banners, chat "
            "launchers, booking widgets"
            + (" (from " + _e(", ".join(vendors)) + ")" if vendors else "")
            + ". They are reported here but "
            "<strong>do not count as failures in the score or in the site's "
            "own counts</strong> (a rule that applies to vendor markup still "
            "counts as applicable, so it can raise the pass rate; and a "
            "finding about the page as a whole, such as no way past a "
            "vendor's navigation, is scored): you cannot edit "
            "them, and embed internals are outside evaluation scope. The "
            "duties that remain are yours: ask the vendor for a current "
            "VPAT or accessibility conformance report, keep a first-party "
            "path to every essential task, and record the decision.</p>"
            "</section>")

    # Judged track (separate, labeled; never mixed into deterministic score).
    judged = report.get("judged")
    if judged:
        rate = ("no pass rate — nothing decidable"
                if judged["judged_pass_rate"] is None
                else _pct(judged["judged_pass_rate"]))
        parts.append("<h2>Judged track (adequacy)</h2>")
        parts.append("<section class=\"banner\" aria-label=\"Judged track\">")
        parts.append(
            f"<p><strong>{_e(judged['provider'])}</strong> · model "
            f"{_e(judged['model'])} · calibrated: "
            f"<strong>{'yes' if judged['calibrated'] else 'no'}</strong> · "
            f"rubrics v{_e(judged['rubric_version'])}</p>")
        parts.append(
            f"<p>pass rate {rate} · fails {judged['fail_findings']} · "
            f"needs review {judged['needs_review_findings']} · provider "
            f"errors {judged['provider_errors']} · decided "
            f"{judged['items_decided']} of {judged['items_graded']} graded "
            f"({judged['items_extracted']} extracted)</p>")
        parts.append(f"<p>{_e(judged['disclosure'])}</p></section>")

    # Every finding, by rule.
    by_rule: dict = {}
    for i, page in enumerate(pages):
        for f in page["findings"]:
            by_rule.setdefault(f["rule_id"], []).append((i, f))
    order = _rule_order(rules, by_rule)
    if order:
        parts.append("<h2>Rules with findings</h2>")
        rows = []
        for rid in order:
            meta = rules.get(rid) or {}
            fs = [f for _p, f in by_rule[rid]]
            own_fail = sum(1 for f in fs if f["verdict"] == FAIL
                           and f.get("owned", True))
            own_review = sum(1 for f in fs if f["verdict"] != FAIL
                             and f.get("owned", True))
            vendor = len(fs) - own_fail - own_review
            npages = len({i for i, _f in by_rule[rid]})
            rows.append(
                f"<tr><td><a href=\"#rule-{_e(rid)}\">"
                f"{_e(meta.get('name') or rid)}</a><br>"
                f"<span class=\"mono\">{_e(rid)}</span></td>"
                f"<td class=\"mono\">{_e(', '.join(meta.get('sc') or []))}</td>"
                f"<td>{_e(meta.get('tier', ''))}</td>"
                f"<td>{own_fail:,}</td><td>{own_review:,}</td>"
                f"<td>{vendor:,}</td><td>{npages:,}</td></tr>")
        parts.append(
            "<table><caption>Rules with findings: failures and review items "
            "in the site's own markup, findings in vendor markup, and pages "
            "affected</caption><thead><tr>"
            "<th scope=\"col\" class=\"c-rule\">Rule</th>"
            "<th scope=\"col\" class=\"c-sc\">WCAG</th>"
            "<th scope=\"col\" class=\"c-n\">Tier</th>"
            "<th scope=\"col\" class=\"c-n\">Failures</th>"
            "<th scope=\"col\" class=\"c-n\">Review items</th>"
            "<th scope=\"col\" class=\"c-n\">In vendor markup</th>"
            "<th scope=\"col\" class=\"c-n\">Pages</th></tr></thead><tbody>"
            + "".join(rows) + "</tbody></table>")

    # The pages.
    parts.append("<h2>Pages</h2>")
    page_rows = []
    captured = [i for i, page in enumerate(pages, 1) if page.get("fetch")]
    for i, page in enumerate(pages, 1):
        score = page["score"]
        name = _e(labels[i - 1])
        if page.get("fetch"):
            name = f"<a href=\"#page-{i}\">{name}</a>"
        badge = _tier1_badge(score, site, page.get("errors") or [])
        page_rows.append(
            f"<tr><td class=\"mono\">{name}</td>"
            f"<td>{_read_as(page, source)}</td><td>{badge}</td>"
            f"<td>{_pct(score['weighted_pass_rate'])}</td>"
            f"<td>{score['fail_findings']:,}</td>"
            f"<td>{score['needs_review_findings']:,}</td></tr>")
    parts.append(
        "<table><caption>Pages evaluated: how each was read, its Tier-1 "
        "status, weighted pass rate, failures and review items</caption>"
        "<thead><tr><th scope=\"col\" class=\"c-page\">Page</th>"
        "<th scope=\"col\" class=\"c-read\">Read as</th>"
        "<th scope=\"col\" class=\"c-t1\">Tier-1</th>"
        "<th scope=\"col\" class=\"c-n\">Pass rate</th>"
        "<th scope=\"col\" class=\"c-n\">Failures</th>"
        "<th scope=\"col\" class=\"c-n\">Review items</th>"
        "</tr></thead><tbody>" + "".join(page_rows) + "</tbody></table>")

    if order:
        parts.append("<h2 id=\"findings\">Findings by rule</h2>")
        parts.append(
            "<p>Each rule's findings, with what the rule checks, why it "
            "matters and how to fix it. Findings that read the same — an "
            "element with the same tag and attributes, start of its text "
            "and first descendants, and the same message — are shown once "
            "with their count, and a table shows at most "
            f"{ROW_LIMIT} of them; the JSON report lists every finding, "
            "with its own fingerprint.</p>")
        axe_version = (tool.get("libraries") or {}).get("axe-core") or \
            (tool.get("from_snapshot") or {}).get("axe-core") or ""
        for rid in order:
            parts.append(_rule_section(rid, rules.get(rid) or {},
                                       by_rule[rid], labels, axe_version))

    # How each page was read (P5-08).
    parts.append("<h2>How each page was read</h2>")
    run_fetch = report.get("fetch") or {}
    if source == "urls":
        parts.append(
            "<p>Fetched from <span class=\"mono\">"
            f"{_e(run_fetch.get('host'))}</span>; the pages are "
            f"{_listing(run_fetch)}.</p>" if run_fetch else
            "<p>The run could fetch none of its pages; each one's error is "
            "listed above.</p>")
    elif source == "render":
        # Served for a browser; whether it captured each page is the
        # page's own record (R3C-3).
        shot = sum(1 for p in pages
                   if (p.get("fetch") or {}).get("mode") == "rendered")
        if shot == len(pages):
            parts.append("<p>The files were served on this machine "
                         "(loopback only) and each page captured in a "
                         "browser.</p>")
        else:
            parts.append(
                "<p>The files were served on this machine (loopback only) "
                "for a browser, which captured "
                + (f"{shot} of the {len(pages)} pages; the table of pages "
                   "above says how the others were read" if shot else
                   f"none of the {len(pages)} pages; the table of pages "
                   "above says how each was read" if len(pages) > 1 else
                   "no page; the table of pages above says how it was read")
                + ".</p>")
    if captured:
        parts.append(
            "<p>Each page's capture record, as the JSON report and an "
            "evidence bundle hold it (<code>pages[i].fetch</code>): where "
            "it came from, when, how it was read, and the SHA-256 of "
            "exactly what the rules read.</p>")
        for i in captured:
            parts.append(_capture_section(i, pages[i - 1], labels[i - 1],
                                          source))
    rest = len(pages) - len(captured)
    if rest and source == "files":
        parts.append(
            "<p>The pages were read from their files as they are: no "
            "browser ran for them"
            + (", and the browser checks recorded in the saved snapshot "
               "were read from it" if tool.get("from_snapshot") else "")
            + ".</p>")
    elif rest:
        parts.append(f"<p>{_plural(rest, 'page')} could not be read; "
                     "each one's error is listed above.</p>")

    parts.append(
        "<footer><p><strong>What this report is.</strong> Measured results from "
        "the executed layers listed above, produced by an open evaluation "
        "harness with a versioned rulebook. A plain FAIL is a failure of "
        "each success criterion cited beside it, one W3C names; FAIL "
        "(heuristic) is a probable failure of them, which markup alone "
        "cannot settle, to confirm. REVIEW findings need a "
        "person's judgment; those marked &ldquo;pled in complaints&rdquo; or "
        "&ldquo;a best practice&rdquo; are not WCAG failures on their own and "
        "do not count against the score or the CI gate, except that with "
        "--strict the gate counts those of moderate impact or more in the "
        "tiers it counts (never those of a WCAG 2.2 criterion). "
        "<strong>What it is not.</strong> "
        "It is not a WCAG conformance determination, not a certification of "
        "compliance with the ADA or any law, and not legal advice. Zero "
        "findings from executed layers does not mean the page is accessible: "
        "unexecuted layers cover, among other things, keyboard operability, "
        "focus visibility and screen-reader announcements, and, on a page no "
        "browser checked, contrast and reflow.</p>"
        "</footer></main></body></html>")
    return "".join(parts)
