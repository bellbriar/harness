#!/usr/bin/env python3
"""Hold a release's files to the ones PyPI already has (SB-2):

    python tools/pypi_files.py VERSION dist [--all]

A build is not the same byte for byte twice, and the upload skips a file
PyPI already holds (`skip-existing`) without comparing the two. So before
the upload, every file in `dist` that PyPI already holds for VERSION must
be the same file (its SHA-256). With --all, before the image is built
from the wheel and before the GitHub release attaches the files, every
file in `dist` must be on PyPI, and the same: a run that builds them
again (GitHub's "Re-run all jobs") then stops, instead of publishing an
image and release files that differ from what PyPI serves.

PyPI's record of a release can lag its upload by a little: with --all, a
file not yet listed is asked for again, five times, 20 seconds apart.

Exit 0 when all hold, 1 when one does not, 2 when PyPI cannot be read.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT = "bellbriar-harness"
INDEX = "https://pypi.org/pypi/{project}/{version}/json"
TRIES = 5
WAIT_S = 20


def held(version: str, opener=urllib.request.urlopen) -> dict | None:
    """{file name: SHA-256} of what PyPI holds for `version`, or None when
    it holds no release of that version. Raises OSError when PyPI cannot
    be read."""
    url = INDEX.format(project=PROJECT, version=version)
    try:
        with opener(url, timeout=30) as answer:
            data = json.load(answer)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise OSError(f"PyPI answered HTTP {exc.code} for {url}") from None
    except (urllib.error.URLError, ValueError) as exc:
        raise OSError(f"PyPI could not be read ({exc})") from None
    return {f["filename"]: f["digests"]["sha256"]
            for f in data.get("urls") or ()
            if isinstance(f, dict) and "filename" in f}


def problems(folder: Path, on_pypi: dict | None, every: bool) -> list[str]:
    """What keeps the files in `folder` from being the ones PyPI holds
    (`on_pypi`, from held()): a file PyPI holds with another SHA-256, and,
    with `every`, a file it does not hold."""
    files = sorted(p for p in folder.iterdir() if p.is_file())
    if not files:
        return [f"there are no files in {folder}"]
    out = []
    for path in files:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        theirs = (on_pypi or {}).get(path.name)
        if theirs is None:
            if every:
                out.append(f"{path.name} is not on PyPI: publish it there "
                           "first, from this run")
        elif theirs != digest:
            out.append(f"{path.name} is not the file PyPI holds (SHA-256 "
                       f"{digest}, PyPI's {theirs}): this run built it again. "
                       "Re-run only the failed jobs of the run that uploaded "
                       "it, or release a new version")
    return out


def main(argv=None, opener=urllib.request.urlopen, sleep=time.sleep) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    every = "--all" in args
    args = [a for a in args if a != "--all"]
    if len(args) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    version, folder = args[0], Path(args[1])
    for attempt in range(TRIES if every else 1):
        try:
            on_pypi = held(version, opener)
        except OSError as exc:
            print(f"pypi_files: {exc}", file=sys.stderr)
            return 2
        found = problems(folder, on_pypi, every)
        missing = [p for p in found if "is not on PyPI" in p]
        if not missing or attempt == TRIES - 1:
            break
        sleep(WAIT_S)
    for p in found:
        print(f"pypi_files: {p}", file=sys.stderr)
    if found:
        return 1
    if on_pypi is None:
        print(f"pypi_files: PyPI holds no {PROJECT} {version} yet")
    elif every:
        print(f"pypi_files: every file in {folder} is the one PyPI holds")
    else:
        print(f"pypi_files: each file PyPI already holds for {version} is "
              f"the one in {folder}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
