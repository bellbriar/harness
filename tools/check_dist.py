#!/usr/bin/env python3
"""Check what a release ships (P1-09, H4, H5), before it is uploaded:

    python tools/check_dist.py dist

For the one wheel and one source distribution in the folder:

* both name the version in pyproject.toml;
* the wheel's metadata states the license expression and carries the
  license files (LICENSE, NOTICE, axe-core's two), and the cryptography
  pin for Intel Macs;
* the wheel holds the rulebook and the vendored axe-core, the copy whose
  SHA-256 the package pins (axe.AXE_SHA256), and nothing outside the
  package and its metadata;
* the source distribution carries every file git tracks (when this is a
  git checkout, as in CI), so the suite runs from it, and in any case
  what the suite reads (tests, fixtures, docs, examples, tools, the
  workflows, the image and the Action) and the license files (R4A-1);
* neither holds a private key, a golden set or a pack other than the
  sample: each is unpacked and read by tools/repo_guard.py.

Exit 0 when all hold, 1 when one does not, 2 when it cannot look.
"""
from __future__ import annotations

import hashlib
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import repo_guard  # noqa: E402

LICENSE_EXPRESSION = "Apache-2.0 AND MPL-2.0 AND MIT AND ISC AND BSD-3-Clause"
LICENSE_FILES = ("LICENSE", "NOTICE",
                 "src/bellbriar_harness/vendor/axe-core/LICENSE",
                 "src/bellbriar_harness/vendor/axe-core/LICENSE-3RD-PARTY.txt",
                 "tests/data/wpt-tree-construction/LICENSE.md",
                 "tests/data/wpt-tree-construction/"
                 "LICENSE-html5lib-tests.txt")
WHEEL_NEEDS = ("bellbriar_harness/rulebook.json",
               "bellbriar_harness/vendor/axe-core/axe.min.js",
               "bellbriar_harness/vendor/axe-core/LICENSE",
               "bellbriar_harness/vendor/axe-core/LICENSE-3RD-PARTY.txt",
               "bellbriar_harness/vendor/axe-core/README.md")
SDIST_NEEDS = ("pyproject.toml", "README.md", "LICENSE", "NOTICE",
               "MANIFEST.in", "SECURITY.md", "CONTRIBUTING.md",
               "CHANGELOG.md", "tests/test_part_r3.py", "fixtures/good.html",
               "docs/REPORT.md", "examples/evidence",
               "tools/repo_guard.py", ".github/workflows/bellbriar-eval.yml",
               ".dockerignore", "docker/Dockerfile", "action/action.yml",
               "action/README.md",
               "src/bellbriar_harness/vendor/axe-core/axe.min.js")


def tracked() -> list[str] | None:
    """The files git tracks in this checkout, or None outside one."""
    import subprocess
    try:
        out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"],
                             capture_output=True, timeout=60,
                             check=True).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    names = [n for n in out.decode("utf-8", "surrogateescape").split("\0")
             if n]
    return names or None


def _axe_sha256() -> str:
    """The SHA-256 of the axe-core the package pins (axe.AXE_SHA256)."""
    import re
    text = (ROOT / "src" / "bellbriar_harness" / "axe.py").read_text(
        encoding="utf-8")
    return re.search(r'^AXE_SHA256 = "([0-9a-f]{64})"', text, re.M).group(1)


def _version() -> str:
    try:
        import tomllib
    except ImportError:                                 # Python 3.10
        import re
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        return re.search(r'^version = "([^"]+)"', text, re.M).group(1)
    with open(ROOT / "pyproject.toml", "rb") as fh:
        return tomllib.load(fh)["project"]["version"]


def check(folder: Path) -> list[str]:
    problems: list[str] = []
    version = _version()
    wheels = sorted(folder.glob("*.whl"))
    sdists = sorted(folder.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        return [f"expected one wheel and one .tar.gz in {folder}, found "
                f"{len(wheels)} and {len(sdists)}"]
    wheel, sdist = wheels[0], sdists[0]
    for f in (wheel, sdist):
        if f"-{version}" not in f.name:
            problems.append(f"{f.name} does not name version {version}")
    with zipfile.ZipFile(wheel) as z:
        names = z.namelist()
        meta = next((n for n in names if n.endswith(".dist-info/METADATA")),
                    None)
        text = z.read(meta).decode("utf-8") if meta else ""
        if f"License-Expression: {LICENSE_EXPRESSION}" not in text:
            problems.append(f"{wheel.name}: METADATA does not state "
                            f"License-Expression: {LICENSE_EXPRESSION}")
        for lic in LICENSE_FILES:
            if f"License-File: {lic}" not in text:
                problems.append(f"{wheel.name}: METADATA names no "
                                f"License-File {lic}")
            if not any(n.endswith(".dist-info/licenses/" + lic)
                       for n in names):
                problems.append(f"{wheel.name}: {lic} is not in the wheel")
        if "Classifier: License ::" in text:
            problems.append(f"{wheel.name}: a License classifier beside the "
                            "license expression")
        pins = [ln for ln in text.splitlines()
                if ln.startswith("Requires-Dist: cryptography")]
        if not any("platform_machine == \"x86_64\"" in p and "<49" in p
                   for p in pins):
            problems.append(f"{wheel.name}: no cryptography<49 pin for Intel "
                            f"Macs (found {pins})")
        for need in WHEEL_NEEDS:
            if need not in names:
                problems.append(f"{wheel.name}: {need} is missing")
        axe = "bellbriar_harness/vendor/axe-core/axe.min.js"
        if axe in names and hashlib.sha256(z.read(axe)).hexdigest() \
                != _axe_sha256():
            problems.append(f"{wheel.name}: {axe} is not the axe-core the "
                            "package pins (axe.AXE_SHA256)")
        stray = [n for n in names if not n.startswith(("bellbriar_harness/",
                 f"bellbriar_harness-{version}.dist-info/"))]
        if stray:
            problems.append(f"{wheel.name}: holds files outside the package "
                            f"({stray[0]}, …)")
        with tempfile.TemporaryDirectory() as tmp:
            z.extractall(tmp)
            problems += [f"{wheel.name}: {p}" for p in
                         repo_guard.check(Path(tmp), everything=True)]
    with tarfile.open(sdist) as t:
        members = t.getmembers()
        top = members[0].name.split("/")[0] if members else ""
        rel = {m.name[len(top) + 1:] for m in members}
        for need in SDIST_NEEDS:
            if need not in rel:
                problems.append(f"{sdist.name}: {need} is missing")
        left_out = sorted(set(tracked() or ()) - rel - set(SDIST_NEEDS))
        if left_out:
            problems.append(f"{sdist.name}: leaves out {len(left_out)} "
                            f"file(s) git tracks ({', '.join(left_out[:3])}"
                            + (", …" if len(left_out) > 3 else "") + "); "
                            "MANIFEST.in must include them")
        with tempfile.TemporaryDirectory() as tmp:
            safe = [m for m in members if m.isfile() and not
                    m.name.startswith(("/", "..")) and "/../" not in m.name]
            for m in safe:
                target = Path(tmp) / m.name
                target.parent.mkdir(parents=True, exist_ok=True)
                src = t.extractfile(m)
                if src is not None:
                    target.write_bytes(src.read())
            problems += [f"{sdist.name}: {p}" for p in
                         repo_guard.check(Path(tmp) / top, everything=True)]
    return problems


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    folder = Path(args[0]) if args else ROOT / "dist"
    if not folder.is_dir():
        print(f"check_dist: not a folder: {folder}", file=sys.stderr)
        return 2
    problems = check(folder)
    for p in problems:
        # Escaped as the guard escapes it: a name inside a distribution
        # cannot start a line of its own (R4H-9).
        print(f"check_dist: {repo_guard._shown(p)}", file=sys.stderr)
    if problems:
        return 1
    print(f"check_dist: the wheel and the source distribution in {folder} "
          "are as they should be")
    return 0


if __name__ == "__main__":
    sys.exit(main())
