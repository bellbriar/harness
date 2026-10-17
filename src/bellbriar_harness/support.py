"""The platforms the harness runs on: Linux and macOS (L141).

On Windows itself the three commands stop before they do anything. The
suite, run there in CI for 1.0.0rc1, found a bundle recording a page's
path with backslashes where the other platforms record "/", and two
outputs named for one file through a symbolic link not refused; parts of
the suite itself assume a POSIX system. A bundle may reach a court, so
the harness does not make one where it is known to differ. WSL (the
Windows Subsystem for Linux) runs the Linux build, and the container
image runs wherever Docker runs Linux containers.
"""

from __future__ import annotations

import os
import re
import sys

#: The status of a command that could not finish.
REFUSED = 2


def unsupported(os_name: str | None = None) -> str | None:
    """Why the harness does not run here, or None where it does."""
    if (os.name if os_name is None else os_name) == "nt":
        return ("this version does not run on Windows. Run it in WSL (the "
                "Windows Subsystem for Linux), or from its container image, "
                "ghcr.io/bellbriar/harness.")
    return None


def refuse_unsupported(prog: str) -> int | None:
    """REFUSED, after saying why on stderr, where the harness does not run;
    None where it does."""
    why = unsupported()
    if why is None:
        return None
    print(f"{prog}: {why}", file=sys.stderr)
    return REFUSED


#: The versions of the libraries that decide verdicts, as this release
#: declares them (pyproject.toml: tests/test_part_s5.py holds the two
#: equal), and Playwright, which captures pages (the browser extra). A
#: forced install, a source folder run with other packages, or a later
#: install that moved one leaves a version outside them, whose verdicts can
#: differ (soupsieve 3.0 and :has(), R7-1): the run says so (L134).
LIBRARY_RANGES = {
    "beautifulsoup4": ((">=", (4, 12)), ("<", (5,))),
    "justhtml": (("==", (3, 13, 0)),),
    "soupsieve": ((">=", (2, 9, 2)), ("<", (2, 10))),
}
BROWSER_RANGES = {"playwright": (("==", (1, 63, 0)),)}

_VERSION = re.compile(r"(\d+(?:\.\d+)*)(?:(a|b|rc)(\d+))?(?:\.post(\d+))?"
                      r"(?:\.dev(\d+))?(?:\+[A-Za-z0-9.]+)?")


def _parsed(text):
    """(release numbers, whether it is a pre- or development release,
    whether it is a post-release) of a version as PEP 440 writes it, its
    local label (+…) set aside; None for anything else."""
    m = _VERSION.fullmatch(text) if isinstance(text, str) else None
    if m is None:
        return None
    release = tuple(int(x) for x in m.group(1).split("."))
    return release, bool(m.group(2) or m.group(5)), bool(m.group(4))


def _cmp(a: tuple, b: tuple) -> int:
    n = max(len(a), len(b))
    a, b = a + (0,) * (n - len(a)), b + (0,) * (n - len(b))
    return (a > b) - (a < b)


def _holds(op: str, want: tuple, got) -> bool:
    """Whether the parsed version `got` meets `op want`, as pip reads the
    clause (PEP 440): `==` takes the release itself alone (its local label
    aside), `>=` its post-releases too, `<` none of the release's own pre-
    releases."""
    release, pre, post = got
    c = _cmp(release, want)
    if op == "==":
        return c == 0 and not pre and not post
    if op == ">=":
        return c > 0 or (c == 0 and not pre)
    if op == "<":
        return c < 0 and not (pre and _cmp(release[:len(want)], want) == 0)
    raise ValueError(op)


def _written(clauses) -> str:
    return ",".join(op + ".".join(map(str, want)) for op, want in clauses)


def untested_libraries(libraries: dict, browser: bool = False) -> list[str]:
    """What `libraries` (a tool record's) holds outside the ranges this
    release declares, one line each. A library not installed is said only
    where it is required: Playwright, of the browser extra, is optional,
    and a run without it says so on its own."""
    ranges = dict(LIBRARY_RANGES)
    if browser:
        ranges.update(BROWSER_RANGES)
    out = []
    for name, clauses in ranges.items():
        if name not in libraries:
            continue
        got = libraries[name]
        if got is None:
            if name not in BROWSER_RANGES:
                out.append(f"{name}: not found (declared "
                           f"{_written(clauses)})")
            continue
        parsed = _parsed(got)
        if parsed is None or not all(_holds(op, want, parsed)
                                     for op, want in clauses):
            out.append(f"{name} {got} (declared {_written(clauses)})")
    return out
