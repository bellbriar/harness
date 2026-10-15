#!/usr/bin/env python3
"""A release's notes, from CHANGELOG.md (R4A-14):

    python tools/release_notes.py VERSION

prints the section of CHANGELOG.md headed `## VERSION` (or
`## [VERSION]`), for the GitHub release. Exit 1 when there is none, or
when its heading still says it is unreleased: the release workflow runs
this before anything is published, so a version is never released
without its notes.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def notes(text: str, version: str) -> str:
    """The section for `version`, heading included; ValueError says why
    there is none to publish."""
    lines = text.splitlines()
    # `## 1.0.0 — date` or `## [1.0.0] - date`: never `## 1.0.0-beta.1`.
    head = re.compile(r"## (?:" + re.escape(version) + r"|\["
                      + re.escape(version) + r"\])(?=$|\s)")
    start = next((i for i, line in enumerate(lines) if head.match(line)),
                 None)
    if start is None:
        raise ValueError(f"CHANGELOG.md has no section for {version} "
                         f"(a heading '## {version}')")
    if "unreleased" in lines[start].lower():
        raise ValueError(f"CHANGELOG.md still calls {version} unreleased: "
                         "write its notes and date it first")
    end = next((i for i in range(start + 1, len(lines))
                if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end]).strip() + "\n"


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    try:
        text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        sys.stdout.write(notes(text, args[0]))
    except (OSError, ValueError) as exc:
        print(f"release_notes: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
