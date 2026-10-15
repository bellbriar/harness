"""A bundle body with every member the format requires
(docs/CANONICALIZATION.md §5 "The body"), for tests that build bundles by
hand: `{**BODY, "domain": "example.com", ...}`. The body is closed, so a
bundle without these members is malformed (R5B-4)."""

BODY = {
    "bundle_format": "bellbriar-evidence/1",
    "created_at": "2026-01-01T00:00:00+00:00",
    "tool": {"name": "bellbriar-harness", "version": "1.0.0"},
    "rulebook_version": "1.0.0",
    "domain": None,
    "pack": None,
    "inputs": [],
    "fetch": None,
    "layers": [],
    "coverage_note": "",
    "site": {},
    "pages": [],
    "judged": None,
    "attestation": "",
    "signature": None,
}
