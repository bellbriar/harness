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
