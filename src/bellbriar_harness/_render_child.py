"""One rendered capture, in a process of its own (fetch._fetch_rendered_isolated).

A page whose script never yields blocks the browser's main thread, and
with it every call the capture makes; run in the harness's own process,
that hung the whole run with no output (N18). Here it runs in a child the
harness can stop: the parent sends the request on stdin and reads the
result on stdout, and kills this process and the browser under it when the
deadline passes.

The child also looks after itself, so nothing outlives the harness (OR-9):

* the parent holds stdin open until it has the result, so stdin ends when
  the parent does, however it ends (Ctrl-C, SIGTERM from a CI job's
  timeout, SIGKILL): the child then stops the browser's driver and
  Chromium under it, and exits;
* it gives up on its own a while after the deadline, should the parent be
  alive but not watching;
* before it answers, it stops anything the capture left running under it,
  so the parent never has to signal a process that may already be gone;
* a navigation that never commits holds every call the capture makes to
  the page: it answers for such a capture itself, in words of its own,
  before the deadline (fetch._watch_pending);
* as it stops on its own, it removes the capture's temporary folder (its
  TMPDIR, which holds the browser's profile), which the parent removes
  when it outlives the child.

Not a command for people to run: the parent writes the request.
"""
from __future__ import annotations

import os
import pickle
import sys
import threading

#: How long after the deadline the child stops itself, if the parent has
#: not stopped it by then.
GRACE_S = 30

#: The capture's temporary folder, as the parent named it in the request.
_SCRATCH = None


def _read_exactly(stream, n: int) -> bytes:
    data = b""
    while len(data) < n:
        chunk = stream.read(n - len(data))
        if not chunk:
            raise EOFError("the request ended early")
        data += chunk
    return data


def stop_descendants() -> None:
    """Kill every process under this one: the browser's driver, Chromium
    (in a process group of its own) and its renderers. (On Windows the
    parent's taskkill /T does this on a deadline, and _give_up kills the
    whole tree, this process included.)"""
    if os.name == "nt":                                # pragma: no cover
        return
    import signal
    from bellbriar_harness.fetch import _descendants
    own = os.getpgid(0)
    groups = set()
    for pid in _descendants(os.getpid()):
        try:
            groups.add(os.getpgid(pid))
        except OSError:
            pass
        try:
            os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    # Chromium runs in a process group of its own: a process it started
    # after the list was taken is in it too (this process's own group is
    # left to the exit that follows).
    for group in groups - {own}:
        try:
            os.killpg(group, signal.SIGKILL)
        except OSError:
            pass


def _give_up(code: int) -> None:
    try:
        if os.name == "nt":                            # pragma: no cover
            import subprocess
            subprocess.run(["taskkill", "/PID", str(os.getpid()), "/T", "/F"],
                           capture_output=True, timeout=30)
        stop_descendants()
        if _SCRATCH is not None:
            from bellbriar_harness.fetch import remove_capture_scratch
            remove_capture_scratch(_SCRATCH, settle_s=0.5)
    finally:
        os._exit(code)


def _watch_parent(stream) -> None:
    """Block on stdin, which only the parent holds open: at its end the
    parent is gone (or has its answer), and so is the reason to run."""
    try:
        while stream.read(65536):
            pass
    except Exception:                                  # noqa: BLE001
        pass
    _give_up(3)


#: Held by whichever thread answers the parent: the capture's, or the
#: one that watches for a navigation that never commits. Never released:
#: the parent reads one answer.
_ANSWERING = threading.Lock()


def _answer(result) -> None:
    """Stop everything under this process, then write `result`. A capture
    that finished may leave the browser's driver behind for a moment;
    nothing under the child outlives its answer."""
    stop_descendants()
    sys.stdout.buffer.write(pickle.dumps(result, protocol=4))
    sys.stdout.buffer.flush()


def _stuck(exc: BaseException) -> None:
    """The capture waits on a navigation that never commits, and every
    call it makes to the page waits with it (fetch._watch_pending): answer
    with `exc` in its place, unless it has answered, and end, with the
    browser it leaves (on Windows, the whole tree: _give_up)."""
    if not _ANSWERING.acquire(blocking=False):
        return
    try:
        _answer(("error", type(exc).__name__, str(exc)))
    finally:
        _give_up(0)


def main() -> int:
    import time
    global _SCRATCH
    stdin = sys.stdin.buffer
    size = int.from_bytes(_read_exactly(stdin, 8), "big")
    # The request comes from the harness's own parent process.
    request = pickle.loads(_read_exactly(stdin, size))
    _SCRATCH = request.get("scratch")
    threading.Thread(target=_watch_parent, args=(stdin,), daemon=True,
                     name="bellbriar-parent-watch").start()
    deadline = request.get("deadline_s")
    deadline_at = None
    if deadline:
        # The parent's clock started as it sent the request: a moment
        # before this one.
        deadline_at = time.monotonic() + deadline
        timer = threading.Timer(deadline + GRACE_S, _give_up, args=(4,))
        timer.daemon = True
        timer.start()
    from bellbriar_harness.fetch import fetch_rendered
    try:
        result = ("ok", fetch_rendered(request["url"], **request["kw"],
                                       on_stuck=_stuck,
                                       deadline_at=deadline_at))
    except BaseException as exc:                     # noqa: BLE001
        # The parent words the record from the text (fetch.render_failure).
        result = ("error", type(exc).__name__, str(exc))
    # Should the watch be answering, it ends this process.
    _ANSWERING.acquire()
    _answer(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
