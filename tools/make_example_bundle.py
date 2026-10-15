#!/usr/bin/env python3
"""Regenerate examples/evidence/ — the worked example a stranger verifies.

Why this is a script and not a hand-kept file: the published example is the
first thing an outside reader runs, and an example that drifts out of format
is worse than no example at all. Everything here goes through the same code
paths a customer uses (run -> score -> build_bundle -> sign_bundle_local ->
verify_bundle), so the example cannot claim a shape the library no longer
produces. tests/test_examples.py re-verifies the committed output on every
run. The example is self-signed, as every bundle this release signs is
(decision D5), and pins no pack (packs are not in 1.0: the ship list's L3).

THE KEY USED HERE IS A DEMONSTRATION KEY. It signs nothing but this example,
it is not a production signing key (PREPUBLISH.md item 8), and it is in no
trust path. `bellbriar-evidence verify` says so in its result for any key
listed in bundle.DEMO_KEY_IDS.

Its private half is never committed, and is kept outside the repository:
anyone holding it could sign bundles that verify against the published demo
key. Verification never needs it:

    python tools/make_example_bundle.py --check

Regenerating needs it, in a file (never the key itself on the command line,
where shell history and process listings keep it):

    python tools/make_example_bundle.py --private-key /path/outside/repo/demo.key

Rotating (the old private half is lost, say) takes two steps, so a key that
`verify` would not label can never sign the example:

    python tools/make_example_bundle.py --new-key /path/outside/repo/demo.key
    # add the printed key_id to DEMO_KEY_IDS in src/bellbriar_harness/bundle.py
    python tools/make_example_bundle.py --private-key /path/outside/repo/demo.key

It signs only with the library versions the package asks pip for
(pyproject.toml's `dependencies`): the example records them (`tool`), and
a run from a source folder where other versions are installed records,
and can show, results the installed package never gives (soupsieve 3.0,
R7-1).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bellbriar_harness import __version__, bundle as B          # noqa: E402
from bellbriar_harness.engine import run_paths                  # noqa: E402
from bellbriar_harness.scoring import score_site                # noqa: E402

OUT_DIR = ROOT / "examples" / "evidence"
PUB_PATH = OUT_DIR / "reference-public-key.hex"
BUNDLE_PATH = OUT_DIR / "signed-bundle-example.json"

DOMAIN = "cornerbakery.example"
# Paths are RELATIVE and the generator chdirs to the repo root: bundle inputs
# record `path` verbatim, and a published example must not carry the
# generating machine's directory layout (it leaked /home/<user>/… once).
PAGES = [Path("fixtures") / "good.html"]
SIGNER = "worked example (demonstration key)"


def _public_of(priv_hex: str) -> str:
    return B.ed25519.Ed25519PrivateKey.from_private_bytes(
        bytes.fromhex(priv_hex)).public_key().public_bytes_raw().hex()


def _outside_repo(path: Path) -> bool:
    """A private key kept inside the working tree ends up in a commit or in
    a zip of the folder sooner or later."""
    try:
        path.resolve().relative_to(ROOT.resolve())
    except ValueError:
        return True
    return False


def _dependency_lines_310(text: str) -> list:
    """The strings of pyproject.toml's `dependencies` array, read line by
    line where Python has no tomllib (3.10)."""
    block = re.search(r"(?ms)^dependencies = \[\n(.*?)^\]", text)
    if block is None:
        raise SystemExit("pyproject.toml: no `dependencies` array found")
    return re.findall(r'^\s*"([^"]+)",?\s*$', block.group(1), re.M)


def _dependency_lines(text: str) -> list:
    try:
        import tomllib
    except ImportError:                 # Python 3.10
        return _dependency_lines_310(text)
    return list(tomllib.loads(text)["project"]["dependencies"])


def _release(text):
    """A version's numbers ("2.9.2" -> (2, 9, 2)), or None for one with
    more than numbers (a pre- or post-release), which is not compared."""
    if not isinstance(text, str) or not re.fullmatch(r"[0-9]+(\.[0-9]+)*",
                                                     text):
        return None
    return tuple(int(x) for x in text.split("."))


def _compare(a: tuple, b: tuple) -> int:
    n = max(len(a), len(b))
    a, b = a + (0,) * (n - len(a)), b + (0,) * (n - len(b))
    return (a > b) - (a < b)


_CLAUSE = re.compile(r"\s*(>=|<=|==|!=|<|>)\s*([0-9]+(?:\.[0-9]+)*)\s*")
_HOLDS = {">=": lambda c: c >= 0, "<=": lambda c: c <= 0,
          ">": lambda c: c > 0, "<": lambda c: c < 0,
          "==": lambda c: c == 0, "!=": lambda c: c != 0}


def declared_ranges(text: str = None) -> dict:
    """{name: (requirement, [(operator, numbers), ...])} for each
    dependency pyproject.toml declares on every platform (no marker): what
    the package asks pip for. A range this cannot read stops it."""
    if text is None:
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    ranges = {}
    for dep in _dependency_lines(text):
        if ";" in dep:
            continue
        m = re.fullmatch(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)(.*)", dep)
        clauses = []
        if m is not None and m.group(2).strip():
            for part in m.group(2).split(","):
                c = _CLAUSE.fullmatch(part)
                if c is None:
                    m = None
                    break
                clauses.append((c.group(1), _release(c.group(2))))
        if m is None:
            raise SystemExit(f"pyproject.toml: cannot read {dep!r}")
        ranges[m.group(1).lower()] = (dep.replace(" ", ""), clauses)
    return ranges


def libraries_outside_ranges(libraries: dict, ranges: dict = None) -> list:
    """[(line, requirement)] for each library a run records (its
    `tool.libraries`) whose version lies outside the range pyproject.toml
    declares for it, or cannot be compared with it."""
    if ranges is None:
        ranges = declared_ranges()
    out = []
    for name, (requirement, clauses) in sorted(ranges.items()):
        if name not in libraries:
            continue
        got = libraries[name]
        numbers = _release(got)
        if got is None:
            out.append((f"{name}: no version found", requirement))
        elif numbers is None:
            out.append((f"{name} {got}: not a version this compares",
                        requirement))
        elif not all(_HOLDS[op](_compare(numbers, want))
                     for op, want in clauses):
            out.append((f"{name} {got} is outside {requirement}",
                        requirement))
    return out


def mint_key(path_arg: str) -> int:
    """Write a new demo private key to `path_arg` and stop."""
    if B.looks_like_key(path_arg):
        raise SystemExit("--new-key takes the path the new key is written "
                         "to, not a key (what was given is not repeated "
                         "here, in case it was one)")
    try:
        path = Path(path_arg).expanduser()
    except RuntimeError:                # "~user" naming no user
        raise SystemExit("--new-key: no such user's home folder") from None
    if not _outside_repo(path):
        raise SystemExit(f"refusing to write a private key inside the "
                         f"repository ({path}); choose a path outside "
                         f"{ROOT}")
    if path.exists():
        raise SystemExit(f"{path} exists; not overwriting a key")
    priv, _pub, kid = B.generate_keypair()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(B.key_file_text(priv, private=True))
    print(f"wrote a NEW demonstration private key to {path} (mode 600)")
    print(f"  key_id {kid}")
    print("  next: add this key_id to DEMO_KEY_IDS in "
          "src/bellbriar_harness/bundle.py, then run")
    print(f"    python tools/make_example_bundle.py --private-key {path}")
    print("  This rotates the published demo key: reference-public-key.hex "
          "changes when the example is regenerated.")
    return 0


def read_key(key_arg: str) -> tuple[str, str]:
    """(private_hex, public_hex) from the file `key_arg` names. A key file
    inside the repository is refused, not read: it is one `git add -A` or
    one zip of the folder away from being published. A key itself is
    refused too (P1-11): on the command line it lands in shell history.
    The file is read as `bellbriar-eval --sign-key` reads one
    (bundle.read_private_key_file), and no message quotes what was given
    unless it is a file inside the repository (R1A-1, R1A-13)."""
    try:
        p = Path(key_arg).expanduser()
    except RuntimeError:                # "~user" naming no user
        p = Path(key_arg)
    if p.is_file() and not _outside_repo(p):
        raise SystemExit(f"refusing to use a private key kept inside the "
                         f"repository ({p}); move it outside {ROOT}")
    try:
        priv, _mode = B.read_private_key_file(key_arg)
    except B.KeyFileError as exc:
        raise SystemExit(f"--private-key: {exc}") from None
    return priv, _public_of(priv)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Regenerate or check examples/evidence/. See the module "
                    "docstring for the key handling.")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true",
                      help="verify the committed example without rewriting "
                           "it (needs no private key)")
    mode.add_argument("--private-key", metavar="FILE",
                      help="a file holding the demonstration private key, "
                           "kept outside the repository")
    mode.add_argument("--new-key", metavar="FILE",
                      help="mint a new demonstration key, write its private "
                           "half to FILE (outside the repository) and stop. "
                           "This rotates the published demo key")
    args = ap.parse_args(argv)

    # Key paths mean what they meant where the command was typed: resolve
    # them before moving to the repository root.
    if args.new_key:
        return mint_key(args.new_key)
    if args.private_key:
        priv, pub = read_key(args.private_key)
    os.chdir(ROOT)

    if args.check:  # verify only; never creates or touches keys
        # read_bundle, as `bellbriar-evidence verify` reads it: a file whose
        # text can be read two ways (a duplicated key) is not VALID.
        data = B.read_bundle(BUNDLE_PATH)
        ok, reason = B.verify_bundle(data, PUB_PATH.read_text().strip())
        print(("VALID: " if ok else "INVALID: ") + reason)
        return 0 if ok else 1

    kid = B.key_id_for(pub)
    if kid not in B.DEMO_KEY_IDS:
        print(f"refusing to sign the example with key_id {kid}: it is not in "
              "DEMO_KEY_IDS (src/bellbriar_harness/bundle.py), so `verify` "
              "would not label it a demonstration key. Add it there first.",
              file=sys.stderr)
        return 1

    # 1. Run the harness over the fixture, exactly as a customer would.
    run = run_paths(PAGES)
    site = score_site(run["pages"], run["rulebook"])
    bundle = B.build_bundle(run, site, PAGES, domain=DOMAIN)

    # 1b. Only with the libraries the package installs (the docstring).
    outside = libraries_outside_ranges(bundle["tool"]["libraries"])
    if outside:
        print("refusing to sign the example with libraries the package does "
              "not install (pyproject.toml): "
              + "; ".join(line for line, _ in outside)
              + ". Install them in range first:\n  python -m pip install "
              "--only-binary=:all: "
              + " ".join(f'"{req}"' for _, req in outside), file=sys.stderr)
        return 1

    # 2. Sign it self-signed, as `bellbriar-eval --sign-key` does: the only
    #    class this release issues (D5).
    bundle = B.sign_bundle_local(bundle, priv, signer=SIGNER)

    # 3. Verify before writing. An example is never published unverified.
    ok, reason = B.verify_bundle(bundle, pub)
    if not ok:
        print(f"refusing to write an example that does not verify: {reason}",
              file=sys.stderr)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PUB_PATH.write_text(pub + "\n")
    BUNDLE_PATH.write_text(json.dumps(bundle, indent=2) + "\n",
                           encoding="utf-8")

    stmt = bundle["signature"]["statement"]
    try:
        shown = BUNDLE_PATH.relative_to(ROOT)
    except ValueError:                  # a test's scratch folder
        shown = BUNDLE_PATH
    print(f"wrote {shown}")
    print(f"  tool           bellbriar-harness {__version__}")
    print(f"  class          {stmt['attestation_class']}")
    print(f"  key_id         {stmt['key_id']}  (DEMONSTRATION KEY)")
    print(f"  bound to       domain={stmt['domain']!r} host={stmt['host']!r} "
          f"rulebook={stmt['rulebook_version']!r} "
          f"(sha256 {stmt['rulebook_sha256'][:16]}…)")
    print(f"  verify         {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
