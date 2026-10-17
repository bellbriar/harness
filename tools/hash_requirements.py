#!/usr/bin/env python3
"""Write the SHA-256 of every file the container image installs into
docker/requirements.txt, so the image's pip installs only those files
(--require-hashes: docker/Dockerfile).

    python tools/hash_requirements.py

It needs pip and the network: for each pinned version in the file, it
asks pip for the wheel pip in the image would choose, for Python 3.12
(Ubuntu 24.04's, which the image runs) on x86-64 and on ARM64 Linux
(platforms()), and writes the SHA-256 of each file under its pin. The
pins themselves, and the comments above them, stay as they are. A pin
with no such wheel stops it; so does a hash pip in the image later finds
missing (a file other than these chosen there), as --require-hashes
refuses it. Run it again whenever a pin moves (Dependabot updates the
hashes of the pins it moves).

Exit 0 when the file was written, 1 when a pin has no wheel for one of the
two, 2 when pip could not run.
"""
from __future__ import annotations

import hashlib
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = ROOT / "docker" / "requirements.txt"

#: What pip in the image accepts: CPython 3.12 on glibc 2.39 (Ubuntu
#: 24.04), for each architecture the release builds.
PYTHON = "3.12"
ABIS = ("cp312", "abi3", "none")
GLIBC_MINOR = 39
#: The oldest glibc minor version pip takes a manylinux wheel for, on each
#: architecture (the packaging library's: 2.5 on x86-64, 2.17 elsewhere).
OLDEST_MINOR = {"x86_64": 5, "aarch64": 17}
#: The legacy names of three manylinux_2_N tags (PEP 600).
LEGACY = {17: "manylinux2014", 12: "manylinux2010", 5: "manylinux1"}
ARCHES = ("x86_64", "aarch64")

_PIN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([0-9][^\s;\\]*)\s*$")


def canonical(name: str) -> str:
    """A distribution's name as files and indexes compare it."""
    return re.sub(r"[-_.]+", "-", name).lower()


def read_pins(text: str) -> tuple[list[str], list[tuple[str, str]]]:
    """(the comment lines at the top, [(name, version)]): a line that is a
    pin's hash, or its continuation, is dropped, as it is written again."""
    header, pins = [], []
    for line in text.splitlines():
        stripped = line.strip()
        if not pins and (stripped.startswith("#") or not stripped):
            header.append(line)
            continue
        if not stripped or stripped.startswith(("#", "--hash")):
            continue
        m = _PIN.match(stripped.rstrip("\\").strip())
        if m is None:
            raise SystemExit(f"hash_requirements: cannot read {line!r}: "
                             "each requirement is name==version")
        pins.append((m.group(1), m.group(2)))
    return header, pins


def platforms(arch: str) -> list[str]:
    """The platform tags pip in the image accepts, in its order, newest
    first: every manylinux_2_N from the image's glibc down to the oldest
    one pip takes on `arch`, each legacy name beside its own
    (manylinux2014, 2010 and 1: Playwright's x86-64 wheel is manylinux1),
    then linux_<arch>. `pip download --platform` takes each tag as it is
    given, not the older ones a manylinux tag implies, so all are given."""
    out = []
    for minor in range(GLIBC_MINOR, OLDEST_MINOR[arch] - 1, -1):
        out.append(f"manylinux_2_{minor}_{arch}")
        if minor in LEGACY:
            out.append(f"{LEGACY[minor]}_{arch}")
    return out + [f"linux_{arch}"]


def download(pins: list[tuple[str, str]], arch: str, dest: Path) -> int:
    argv = [sys.executable, "-m", "pip", "download", "--no-deps",
            "--only-binary=:all:", "--dest", str(dest),
            "--python-version", PYTHON, "--implementation", "cp"]
    for abi in ABIS:
        argv += ["--abi", abi]
    for platform in platforms(arch):
        argv += ["--platform", platform]
    argv += [f"{name}=={version}" for name, version in pins]
    return subprocess.run(argv).returncode


def file_hashes(folder: Path) -> dict[str, set[str]]:
    """{canonical name: {sha256 of each of its files}} in `folder`."""
    out: dict[str, set[str]] = {}
    for f in sorted(folder.iterdir()):
        if not f.name.endswith(".whl"):
            continue
        name = canonical(f.name.split("-", 1)[0])
        out.setdefault(name, set()).add(
            hashlib.sha256(f.read_bytes()).hexdigest())
    return out


def render(header: list[str], pins, hashes: dict[str, set[str]]) -> str:
    lines = list(header)
    for name, version in pins:
        digests = sorted(hashes[canonical(name)])
        lines.append(f"{name}=={version} \\")
        for i, digest in enumerate(digests):
            end = " \\" if i < len(digests) - 1 else ""
            lines.append(f"    --hash=sha256:{digest}{end}")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    path = Path((argv or sys.argv[1:] or [str(REQUIREMENTS)])[0])
    header, pins = read_pins(path.read_text(encoding="utf-8"))
    hashes: dict[str, set[str]] = {}
    with tempfile.TemporaryDirectory() as tmp:
        for arch in ARCHES:
            dest = Path(tmp) / arch
            dest.mkdir()
            if download(pins, arch, dest) != 0:
                print(f"hash_requirements: pip could not download the "
                      f"{arch} files (above)", file=sys.stderr)
                return 2
            got = file_hashes(dest)
            missing = [n for n, _ in pins if canonical(n) not in got]
            if missing:
                print(f"hash_requirements: no {arch} wheel for "
                      f"{', '.join(missing)}", file=sys.stderr)
                return 1
            for name, digests in got.items():
                hashes.setdefault(name, set()).update(digests)
    path.write_text(render(header, pins, hashes), encoding="utf-8")
    total = sum(len(v) for v in hashes.values())
    print(f"hash_requirements: wrote {total} hashes for {len(pins)} pins "
          f"to {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
