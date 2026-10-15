#!/usr/bin/env python3
"""Regenerate src/bellbriar_harness/langtags.py from the IANA Language
Subtag Registry and the ISO 639-2 code list.

    python tools/make_langtags.py language-subtag-registry ISO-639-2_utf-8.txt [OUT]

The first argument is the registry as IANA publishes it, the record-jar text at
https://www.iana.org/assignments/language-subtag-registry/language-subtag-registry
(records separated by "%%", fields such as "Type: language", "Subtag: aa").
The JSON array of the language-subtag-registry npm package
(data/json/registry.json) is read too. Ranges ("qaa..qtz") are expanded.
Deprecated subtags stay valid: the registry keeps them, and a browser and
a screen reader still read them.

The second is the ISO 639-2 list the Library of Congress publishes at
https://www.loc.gov/standards/iso639-2/ISO-639-2_utf-8.txt (lines of
bibliographic|terminologic|alpha-2|English|French), or the same data as the
CSV of the datasets/language-codes repository (data/language-codes-full.csv,
public domain). It gives the three-letter codes of the languages BCP 47
writes with two letters, which the registry never lists: lang="eng" fails
(ACT bf051a, Failed Example 3), since English is "en".

bb-html-lang (ACT rule bf051a) checks that a page's primary language subtag
is one the registry lists; the module this writes holds both lists.
"""
from __future__ import annotations

import csv
import io
import json
import string
import sys
import textwrap
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "src" / "bellbriar_harness" / "langtags.py"


def records(path: Path) -> tuple[str, list[dict]]:
    text = path.read_text(encoding="utf-8")
    if text.lstrip().startswith("["):
        data = json.loads(text)
        meta = path.with_name("meta.json")
        date = (json.loads(meta.read_text(encoding="utf-8")).get("File-Date", "")
                if meta.exists() else "")
        return date, data
    date, out = "", []
    for block in text.split("%%"):
        rec: dict = {}
        key = None
        for line in block.splitlines():
            if not line.strip():
                continue
            if line[0] in " \t" and key:          # a folded continuation line
                rec[key] = f"{rec[key]} {line.strip()}"
                continue
            key, _, value = line.partition(":")
            key, value = key.strip(), value.strip()
            rec[key] = value
        if "File-Date" in rec:
            date = rec["File-Date"]
        elif rec:
            out.append(rec)
    return date, out


def iso639_2(path: Path) -> dict[str, str]:
    """Three-letter ISO 639-2 codes, bibliographic and terminologic, of the
    languages that have a two-letter code: {"eng": "en", "fre": "fr", ...}."""
    text = path.read_text(encoding="utf-8-sig")
    first = text.splitlines()[0] if text else ""
    rows = csv.reader(io.StringIO(text), delimiter="|" if "|" in first else ",")
    out: dict[str, str] = {}
    for row in rows:
        if len(row) < 3:
            continue
        bib, term, two = (c.strip().lower() for c in row[:3])
        if len(two) != 2 or not two.isalpha():
            continue                              # a header, or no 2-letter code
        for three in (bib, term):
            if len(three) == 3 and three.isalpha():
                out[three] = two
    return out


def expand(subtag: str) -> list[str]:
    if ".." not in subtag:
        return [subtag.lower()]
    lo, hi = (s.lower() for s in subtag.split(".."))
    letters = string.ascii_lowercase
    out = []
    a, b, c = (letters.index(ch) for ch in lo)
    x, y, z = (letters.index(ch) for ch in hi)
    for i in range(a, x + 1):
        for j in range(26):
            for k in range(26):
                code = letters[i] + letters[j] + letters[k]
                if lo <= code <= hi:
                    out.append(code)
    return out


def main(argv: list[str]) -> int:
    if len(argv) not in (3, 4):
        print(__doc__)
        return 2
    out = Path(argv[3]) if len(argv) == 4 else OUT
    date, recs = records(Path(argv[1]))
    two_letter = iso639_2(Path(argv[2]))
    langs: set[str] = set()
    grandfathered: dict[str, str] = {}
    for r in recs:
        if r.get("Type") == "language" and r.get("Subtag"):
            langs.update(expand(r["Subtag"]))
        elif r.get("Type") == "grandfathered" and r.get("Tag"):
            grandfathered[r["Tag"].lower()] = (r.get("Preferred-Value")
                                               or "").strip()
    two = sorted(s for s in langs if len(s) == 2)
    three = sorted(s for s in langs if len(s) == 3)
    if len(two) < 150 or len(three) < 7000:
        print(f"refusing: {len(two)} two-letter and {len(three)} three-letter "
              "subtags is not a whole registry")
        return 1
    # A code the registry lists stays valid whatever ISO 639-2 says.
    iso = {k: v for k, v in sorted(two_letter.items()) if k not in langs}
    if len(iso) < 150:
        print(f"refusing: {len(iso)} ISO 639-2 codes is not the whole list")
        return 1

    def block(codes):
        return "\n".join(textwrap.wrap(" ".join(codes), 76))

    out.write_text(f'''"""Primary language subtags of the IANA Language Subtag Registry, File-Date
{date} ({len(two)} two-letter, {len(three)} three-letter, ranges expanded,
deprecated ones kept), and the ISO 639-2 codes BCP 47 replaces with two
letters ({len(iso)}). Generated by tools/make_langtags.py; do not edit.

bb-html-lang (ACT rule bf051a) fails a page whose primary language subtag
is not in the registry. The registry adds a few three-letter codes every
year, so a three-letter subtag missing from this copy is a review, not a
failure, unless ISO 639-2 gives it for a language BCP 47 writes with two
letters (lang="eng" for "en").
"""

REGISTRY_DATE = "{date}"

_TWO = """
{block(two)}
"""

_THREE = """
{block(three)}
"""

PRIMARY_LANGUAGE_SUBTAGS = frozenset(_TWO.split()) | frozenset(_THREE.split())

_ISO_639_2 = """
{block(f"{k}:{v}" for k, v in iso.items())}
"""

#: ISO 639-2 three-letter codes (bibliographic and terminologic) of the
#: languages BCP 47 writes with their two-letter code: "eng" is "en".
ISO_639_2_TWO_LETTER = dict(pair.split(":") for pair in _ISO_639_2.split())

#: Whole tags the registry lists as grandfathered, with the tag it prefers
#: ("" where it names none). ACT bf051a fails them all: a grandfathered tag
#: has no known primary language tag (zh-min-nan included).
GRANDFATHERED = {{
{block(sorted(f"{g!r}: {v!r}," for g, v in grandfathered.items()))}
}}
''', encoding="utf-8")
    print(f"wrote {out} ({date}: {len(two)} + {len(three)} subtags, "
          f"{len(iso)} ISO 639-2 codes, {len(grandfathered)} grandfathered tags)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
