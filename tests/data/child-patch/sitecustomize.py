"""Loaded at start-up by the capture child process in tests only (the test
puts this directory on PYTHONPATH): with BELLBRIAR_TEST_CAPTURE_RESULT set,
the capture call returns that JSON value, so a test sees what the harness
makes of a capture result after it went through the child process and the
parent's restricted unpickler (fetch._fetch_rendered_isolated)."""
import json
import os

_VALUE = os.environ.get("BELLBRIAR_TEST_CAPTURE_RESULT")
if _VALUE:
    import bellbriar_harness.fetch as _fetch

    # (result, note, provenance attribute, axe-core's session): a stand-in
    # capture has no session of axe-core's.
    _RETURNED = tuple(json.loads(_VALUE))[:3] + (None,)
    _fetch._call_capture = lambda *args, **kwargs: _RETURNED
