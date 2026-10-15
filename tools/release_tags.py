#!/usr/bin/env python3
"""The tags a release's container image gets (R4A-13):

    python tools/release_tags.py --check VERSION
    python tools/release_tags.py VERSION IMAGE [--released FILE] [--pypi FILE]

`--check` exits 0 when VERSION is one this project releases (1.0.0, or a
pre-release such as 1.1.0rc1), else 2: the release runs it before
anything is published, so a version the image steps would refuse
(1.0.0.post1, 1.2) never reaches PyPI (R4D-1).

Otherwise it prints, for $GITHUB_OUTPUT, `floating=…`, the floating tags
this release gets, comma-separated (possibly none), and `latest=true` or
`latest=false`. A final release gets each floating tag only while it is
the newest final release that tag covers: `MAJOR.MINOR`, `MAJOR` and
`latest`. So a fix to an older line (1.0.5 after 1.1.0) moves `1.0` and
nothing else, and a pre-release (1.1.0rc1) moves nothing. The image's own
version tag is pushed first, on its own; these follow once that image has
been pulled and run (R4D-2). The releases are the tags `--released` FILE
lists, one per line (the release workflow lists its GitHub releases, so a
tag whose run stopped before publishing is not one, R4F-11), and the
versions PyPI's JSON for the project (`--pypi` FILE) lists with a file
not yanked (a run that published there and stopped before its GitHub
release still released that version, R4H-2: its simple index as JSON,
PEP 691, or the JSON API's deprecated `releases`); with neither, the
repository's version tags (v1.0.0), read with git (the checkout then
needs them: fetch-depth: 0).

Exit 0, or 2 when VERSION is not a version this project releases.
"""
from __future__ import annotations

import re
import subprocess
import sys

#: What this project's versions look like: 1.0.0, or 1.1.0rc1 (PEP 440,
#: normalized, as setuptools writes them into the file names).
VERSION = re.compile(r"(\d+)\.(\d+)\.(\d+)(?:(a|b|rc)(\d+))?")


def parse(version: str):
    """(major, minor, patch, pre-release or None) of a version, or None."""
    m = VERSION.fullmatch(version)
    if not m:
        return None
    major, minor, patch = (int(x) for x in m.group(1, 2, 3))
    pre = (m.group(4), int(m.group(5))) if m.group(4) else None
    return major, minor, patch, pre


def released(tags, strict: bool = False) -> list[tuple]:
    """The final releases among git tags (v1.0.0), as (major, minor,
    patch). With `strict` (the lists of GitHub's releases and PyPI's
    versions), a release that is not a version this project releases
    (1.1.0.post1, 1.1, 2.0.0.dev1) is a ValueError: the floating tags
    never move on part of the releases (R5A-15)."""
    out = []
    odd = []
    for tag in tags:
        v = parse(tag[1:]) if tag.startswith("v") else None
        if v is None:
            if strict:
                odd.append(tag)
            continue
        if v[3] is None:
            out.append(v[:3])
    if odd:
        raise ValueError(
            "releases this script cannot order among this project's "
            f"versions: {', '.join(sorted(odd)[:5])}"
            + (", …" if len(odd) > 5 else "") + "; no floating tag moves "
            "until they are removed or this script reads them")
    return out


def pypi_versions(doc) -> list[str]:
    """The versions PyPI lists for a project with at least one file not
    yanked, as tags (v1.0.0): from its simple index as JSON (PEP 691,
    https://pypi.org/simple/NAME/ asked for
    application/vnd.pypi.simple.v1+json), or from its JSON API's
    `releases`, which PyPI has deprecated (R4J-11)."""
    if not isinstance(doc, dict):
        raise ValueError("the PyPI file is not a JSON object")
    if isinstance(doc.get("files"), list):
        out = set()
        for f in doc["files"]:
            if not isinstance(f, dict) or f.get("yanked"):
                continue
            version = _file_version(str(f.get("filename", "")))
            if version:
                out.add("v" + version)
        return sorted(out)
    releases = doc.get("releases")
    if not isinstance(releases, dict):
        raise ValueError("the PyPI file lists no files and no releases")
    return ["v" + str(v) for v, files in releases.items()
            if isinstance(files, list) and any(
                isinstance(f, dict) and not f.get("yanked") for f in files)]


def _file_version(filename: str) -> str:
    """The version a distribution's file name holds (a wheel's
    NAME-VERSION-…whl, an sdist's NAME-VERSION.tar.gz), or ""."""
    if filename.endswith(".whl"):
        parts = filename[:-4].split("-")
        return parts[1] if len(parts) >= 5 else ""
    for ext in (".tar.gz", ".zip"):
        if filename.endswith(ext):
            stem = filename[:-len(ext)]
            return stem.rsplit("-", 1)[1] if "-" in stem else ""
    return ""


def tags_for(version: str, image: str, releases: list[tuple]) -> list[str]:
    v = parse(version)
    if v is None:
        raise ValueError(f"not a version this project releases: {version!r}")
    out = [f"{image}:{version}"]
    if v[3] is not None:
        return out                      # a pre-release moves nothing
    mine = v[:3]
    finals = set(releases) | {mine}
    if mine == max(r for r in finals if r[:2] == mine[:2]):
        out.append(f"{image}:{mine[0]}.{mine[1]}")
    if mine == max(r for r in finals if r[0] == mine[0]):
        out.append(f"{image}:{mine[0]}")
    if mine == max(finals):
        out.append(f"{image}:latest")
    return out


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) == 2 and args[0] == "--check":
        if parse(args[1]) is None:
            print(f"release_tags: {args[1]!r} is not a version this project "
                  "releases (1.0.0, or a pre-release such as 1.1.0rc1)",
                  file=sys.stderr)
            return 2
        return 0
    files: dict = {}
    while len(args) > 2 and args[2] in ("--released", "--pypi") and \
            args[2] not in files and len(args) > 3:
        files[args[2]] = args[3]
        args = args[:2] + args[4:]
    if len(args) != 2:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    version, image = args
    try:
        listed: list = []
        if "--released" in files:
            with open(files["--released"], encoding="utf-8") as fh:
                listed += fh.read().split()
        if "--pypi" in files:
            import json
            with open(files["--pypi"], encoding="utf-8") as fh:
                listed += pypi_versions(json.load(fh))
        if not files:
            listed = subprocess.run(["git", "tag", "--list", "v*"],
                                    capture_output=True, text=True,
                                    check=True, timeout=60).stdout.split()
        tags = tags_for(version, image, released(listed, strict=bool(files)))
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        print(f"release_tags: {exc}", file=sys.stderr)
        return 2
    print("floating=" + ",".join(tags[1:]))
    print(f"latest={'true' if f'{image}:latest' in tags else 'false'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
