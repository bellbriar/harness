#!/usr/bin/env python3
"""Snapshot the W3C facts the rulebook cites, from W3C's own sources (P2-14).

The rulebook cites WCAG success criteria (by number, with a conformance
level), a WCAG Understanding document per rule, W3C ACT rules, and W3C
failure techniques. Every citation is checked by tests/test_citations.py
against the snapshot this script writes, tests/data/w3c-citations.json, so
a citation that drifts from W3C's text fails the suite rather than
shipping (PREPUBLISH items 2 and 3). The snapshot is made from local
clones of W3C's repositories, not from web pages:

    git clone --depth 1 https://github.com/w3c/wcag
    git clone --depth 1 https://github.com/w3c/wcag-act-rules
    python tools/w3c_citations.py --wcag wcag --act wcag-act-rules

From w3c/wcag: each success criterion in the order guidelines/index.html
includes it (which gives its number), its title and level from its own
file, the version that introduced it (the sc/20, sc/21 or sc/22 folder),
whether it is obsolete (4.1.1), the name of its Understanding document in
the WCAG 2.1 and 2.2 sets (the 2.1 set has none for a 2.2 criterion, and
calls 2.5.5's document target-size, as the site's build does), and the
failure techniques its Understanding document lists
(understanding/understanding.11tydata.js); each failure technique's
criteria and whether it is obsolete (techniques/failures). From
guidelines/act-mapping.json, the list the W3C site publishes: every ACT
rule's id, title, status (deprecated, proposed, or else approved), and
the criteria it maps to, required for conformance or secondary. With
--act, each rule's title and status are checked against its page in
w3c/wcag-act-rules (content/rules/<id>/), and the script stops on any
difference.

The output holds facts (numbers, levels, titles, ids), not W3C prose.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tests" / "data" / "w3c-citations.json"
VERSIONS = {"20": "2.0", "21": "2.1", "22": "2.2"}


def _commit(repo: Path) -> dict:
    out = subprocess.run(["git", "-C", str(repo), "log", "-1",
                          "--format=%H %cs"], capture_output=True, text=True,
                         check=True).stdout.split()
    return {"commit": out[0], "date": out[1]}


#: The WCAG 2.1 set's names for documents the 2.2 sources renamed
#: (11ty/guidelines.ts, generateScSlugOverrides).
SLUG_21 = {"target-size-enhanced": "target-size"}


def failures_by_slug(wcag: Path) -> dict:
    """{criterion slug: [failure technique ids]}, as each Understanding
    document lists them (understanding/understanding.11tydata.js)."""
    text = (wcag / "understanding" / "understanding.11tydata.js").read_text(
        encoding="utf-8")
    keys = [(m.start(), m.group(1)) for m in
            re.finditer(r'^      "?([a-z0-9-]+)"?: \{', text, re.M)]
    out = {}
    for i, (pos, slug) in enumerate(keys):
        block = text[pos:keys[i + 1][0] if i + 1 < len(keys) else len(text)]
        m = re.search(r'\n        failure: \[(.*?)\],?\n', block, re.S)
        if m:
            out[slug] = re.findall(r'"(F\d+)"', m.group(1))
    if len(out) < 40:
        raise SystemExit(f"read failures for only {len(out)} criteria: has "
                         "understanding.11tydata.js changed?")
    return out


def criteria(wcag: Path) -> dict:
    index = (wcag / "guidelines" / "index.html").read_text(encoding="utf-8")
    failing = failures_by_slug(wcag)
    out, p, g, k = {}, 0, 0, 0
    for m in re.finditer(r'<section class="(principle|guideline)"'
                         r'|data-include="sc/(\d\d)/([a-z0-9-]+)\.html"', index):
        if m.group(1) == "principle":
            p, g = p + 1, 0
        elif m.group(1) == "guideline":
            g, k = g + 1, 0
        else:
            k += 1
            folder, slug = m.group(2), m.group(3)
            text = (wcag / "guidelines" / "sc" / folder / f"{slug}.html"
                    ).read_text(encoding="utf-8")
            title = re.search(r"<h4>(.*?)</h4>", text, re.S)
            level = re.search(r'<p class="conformance-level">\s*([A-Z]*)\s*</p>',
                              text)
            title = html.unescape(re.sub(r"<[^>]+>", "", title.group(1))).strip()
            doc = next((v for v in VERSIONS if (wcag / "understanding" / v /
                                                f"{slug}.html").is_file()), None)
            out[f"{p}.{g}.{k}"] = {
                "slug": slug, "title": title,
                "level": level.group(1) if level else None,
                "introduced": VERSIONS[folder],
                "obsolete": "(Obsolete" in title,
                "understanding": {
                    "2.1": (SLUG_21.get(slug, slug)
                            if doc in ("20", "21") else None),
                    "2.2": slug if doc else None,
                },
                "failures": failing.get(slug, []),
            }
    if len(out) < 80:
        raise SystemExit(f"read only {len(out)} criteria: has index.html changed?")
    return out


def failures(wcag: Path, crit: dict) -> dict:
    """{failure technique id: its criteria and whether W3C made it
    obsolete}, for each failure technique an Understanding document lists."""
    out = {}
    for number, c in crit.items():
        for fid in c["failures"]:
            out.setdefault(fid, {"criteria": [], "obsolete": False})
            out[fid]["criteria"].append(number)
    for fid, f in out.items():
        path = wcag / "techniques" / "failures" / f"{fid}.html"
        if not path.is_file():
            raise SystemExit(f"{fid} is listed but has no file in "
                             "techniques/failures")
        f["obsolete"] = re.search(r"^obsoleteSince:", _front_matter(path),
                                  re.M) is not None
    return dict(sorted(out.items(), key=lambda kv: int(kv[0][1:])))


def _front_matter(path: Path) -> str:
    m = re.match(r"---\n(.*?)\n---", path.read_text(encoding="utf-8"), re.S)
    return m.group(1) if m else ""


def rule_pages(act: Path) -> dict:
    """{id: (title, status)} from the rule pages w3c/wcag-act-rules
    publishes: content/rules/<id>/index.md is an approved rule's page,
    proposed.md every rule's proposed version, which says `deprecated:`
    when the rule is."""
    out = {}
    for folder in sorted((act / "content" / "rules").iterdir()):
        index, proposed = folder / "index.md", folder / "proposed.md"
        if not proposed.is_file():
            continue
        head = _front_matter(index if index.is_file() else proposed)
        title = re.search(r'^title:\s*"?(.*?)"?\s*$', head, re.M)
        rid = re.search(r"^\s+id:\s*(\S+)", head, re.M)
        if title is None or rid is None or rid.group(1) != folder.name:
            raise SystemExit(f"{folder}: no title, or rule_meta.id is not "
                             f"{folder.name}")
        status = ("deprecated" if re.search(r"^deprecated:", _front_matter(proposed),
                                            re.M)
                  else "approved" if index.is_file() else "proposed")
        out[folder.name] = (html.unescape(title.group(1)), status)
    if len(out) < 80:
        raise SystemExit(f"read only {len(out)} rule pages in {act}: has "
                         "w3c/wcag-act-rules changed its layout?")
    return out


def act_rules(wcag: Path, act: Path | None) -> dict:
    mapping = json.loads((wcag / "guidelines" / "act-mapping.json")
                         .read_text(encoding="utf-8"))
    pages = rule_pages(act) if act is not None else None
    out = {}
    for r in mapping["act-rules"]:
        fm = r.get("frontmatter") or {}
        rid = fm.get("id")
        reqs = {k.split(":", 1)[1]: v
                for k, v in (fm.get("accessibility_requirements") or {}).items()
                if re.match(r"wcag2[012]:\d+\.\d+\.\d+$", k)}
        conformance = sorted(c for c, v in reqs.items()
                             if isinstance(v, dict) and v.get("forConformance"))
        secondary = sorted(c for c in reqs if c not in conformance)
        status = ("deprecated" if r.get("deprecated") else
                  "proposed" if r.get("proposed") else "approved")
        if pages is not None and pages.get(rid) != (r["title"], status):
            raise SystemExit(f"ACT {rid}: act-mapping.json has "
                             f"{(r['title'], status)!r}, its rule page "
                             f"{pages.get(rid)!r}")
        out[rid] = {"title": r["title"], "status": status,
                    "conformance": conformance, "secondary": secondary}
    if pages is not None and set(pages) != set(out):
        raise SystemExit("rule pages and act-mapping.json list different "
                         f"rules: {sorted(set(pages) ^ set(out))}")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--wcag", required=True, type=Path,
                    help="a clone of https://github.com/w3c/wcag")
    ap.add_argument("--act", type=Path,
                    help="a clone of https://github.com/w3c/wcag-act-rules, "
                         "to check each ACT title against its rule file")
    args = ap.parse_args(argv)
    snapshot = {
        "about": ("Facts the rulebook cites, from W3C's repositories; "
                  "regenerate with tools/w3c_citations.py"),
        "sources": {
            "wcag": {"repo": "https://github.com/w3c/wcag",
                     **_commit(args.wcag)},
            **({"act_rules": {"repo": "https://github.com/w3c/wcag-act-rules",
                              **_commit(args.act)}} if args.act else {}),
        },
        "criteria": criteria(args.wcag),
        "act_rules": act_rules(args.wcag, args.act),
    }
    snapshot["failures"] = failures(args.wcag, snapshot["criteria"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(snapshot, indent=1, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(snapshot['criteria'])} "
          f"criteria, {len(snapshot['act_rules'])} ACT rules, "
          f"{len(snapshot['failures'])} failure techniques")
    return 0


if __name__ == "__main__":
    sys.exit(main())
