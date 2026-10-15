"""bellbriar-evidence — keygen / verify / inspect evidence bundles.

`keygen` writes a new Ed25519 key pair for self-signed bundles: the private
key readable by its owner only (mode 600 where the system has modes), and
never over an existing file unless --force says so (P4-06).

`verify` exit codes: 0 VALID, 1 INVALID, 2 could not verify (missing
dependency, unreadable or malformed bundle, malformed key). "Could not
verify" is never reported as INVALID: that would tell a reader a genuine
bundle was forged.

Everything printed from a bundle is escaped first. A bundle is untrusted
input, and a key or value carrying terminal control characters could
otherwise paint "VALID" over the real verdict.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from .bundle import (DEMO_KEY_IDS, HEX_KEY_RE, KEY_SPACE, MAX_KEY_FILE,
                     PUBLISHED_TEST_KEY_IDS,
                     SELF_SIGNED, SIGNATURE_ALG, SIGNATURE_MEMBERS,
                     STATEMENT_FIELDS, STATEMENT_FORMAT,
                     MalformedBundle, UnreadableBundle,
                     VerificationUnavailable,
                     bundle_bound_values, bundle_digest, generate_keypair,
                     key_file_text, key_id_for, load_bundle, parse_key_text,
                     read_bundle_bytes, statement_signed_by, url_host,
                     verify_bundle, host_note)

def _printable(text: str) -> str:
    """Controls, format characters (bidi overrides and isolates,
    zero-width marks, soft hyphens, tag characters), line and paragraph
    separators and code points nothing assigns, escaped (redact.printable,
    R4C-7)."""
    from .redact import printable
    return printable(text)


def _say(text: str) -> None:
    print(_printable(text))


def _clip(value, quoted: bool = False, limit: int = 100) -> str:
    """A value from a bundle, at most `limit` characters: a bundle can make
    any of them as long as it likes (R1A-12)."""
    text = repr(value) if quoted else str(value)
    return text if len(text) <= limit else text[:limit - 1] + "…"


#: What _public_key returns for a file keygen marked as a PRIVATE key, and
#: for a file that holds no public key as keygen writes one.
PRIVATE_FILE = "private"
NOT_KEY_FILE = "not a key file"


def _public_key(key_arg: str) -> str | None:
    """The 64 hex characters --public-key gives, itself or in a file (as
    keygen writes a .pub file, or as it did before 1.0: the key alone);
    PRIVATE_FILE for a file keygen marked as a private key; NOT_KEY_FILE
    for another file; None when it gives none. Never quoted back: a private
    key passed here by mistake must not reach a log."""
    key = key_arg
    try:
        path = Path(key_arg).expanduser()
        is_file = path.is_file()
    except (OSError, ValueError, RuntimeError):
        is_file = False
    if is_file:
        try:
            with open(path, "rb") as fh:
                text = fh.read(MAX_KEY_FILE + 1).decode("ascii")
        except UnicodeDecodeError:
            return NOT_KEY_FILE
        except OSError:
            return None
        if len(text) > MAX_KEY_FILE:
            return NOT_KEY_FILE
        kind, key = parse_key_text(text)
        if kind == "private":
            return PRIVATE_FILE
        return (key if kind in (None, "public") and key is not None
                else NOT_KEY_FILE)
    key = key.strip(KEY_SPACE)
    return key.lower() if HEX_KEY_RE.fullmatch(key) else None


def _private_key_given(data, key: str) -> bool:
    """Whether `key` is the private half of the key that signed `data`:
    keygen writes both halves as 64 hex characters, and passing the .key
    file used to read as a forged bundle. Only when the signature over the
    statement holds under the public key `key` gives: a key_id is the
    bundle's word, and a forger could name one to make a bundle no key
    signed read as its owner's mistake (R5D-5). The rest of the bundle is
    not read: one edited since it was signed is still signed with that key
    (R5F-3)."""
    sig = data.get("signature") if isinstance(data, dict) else None
    if not isinstance(sig, dict) or not isinstance(sig.get("key_id"), str):
        return False
    try:
        from .bundle import ed25519
        pub = ed25519.Ed25519PrivateKey.from_private_bytes(
            bytes.fromhex(key)).public_key().public_bytes_raw().hex()
    except Exception:  # noqa: BLE001 — no cryptography, or not a key
        return False
    if key_id_for(pub) != sig["key_id"] or key_id_for(key) == sig["key_id"]:
        return False
    return statement_signed_by(sig, pub)


def _verify(bundle_path: str, key_arg: str) -> int:
    try:
        data = load_bundle(_bundle_text(bundle_path))
        key = _public_key(key_arg)
        if key == PRIVATE_FILE:
            _say("CANNOT VERIFY: --public-key names a PRIVATE key file (its "
                 "first line says so). Pass the .pub file; and if that "
                 "private key left its owner's machine, it is exposed.")
            return 2
        if key == NOT_KEY_FILE:
            # Said as what it is, not as "no key given" (R5D-15).
            _say("CANNOT VERIFY: --public-key names a file that holds no "
                 "Ed25519 public key as bellbriar-evidence keygen writes one "
                 "(its first line, then 64 hex characters; or, as before "
                 "1.0, the 64 characters alone). A byte order mark, another "
                 "first line or more text is not read as a key")
            return 2
        if key is None:
            # Not a key: "could not verify", never INVALID (R1A-4).
            _say("CANNOT VERIFY: --public-key gives no Ed25519 public key "
                 "(64 hex characters, or a file holding them)"
                 + (": it is empty" if not key_arg.strip() else ""))
            return 2
        if _private_key_given(data, key):
            # Either the private half was passed here, or the bundle was
            # signed with a public key used as a private one (R5B-2).
            _say("CANNOT VERIFY: what --public-key gives is the PRIVATE half "
                 "of the key that signed this bundle. If it is the signer's "
                 "published public key, the bundle was signed with that "
                 "public key as its private key: anyone can derive that key "
                 "from the published one, so the signature shows nothing. "
                 "Otherwise pass the .pub file; and if that private key left "
                 "its owner's machine, it is exposed.")
            return 2
        if key_id_for(key) in PUBLISHED_TEST_KEY_IDS:
            # Its private key is printed in the specification (R5B-17).
            _say(f"CANNOT VERIFY: the public key is the format "
                 f"specification's PUBLISHED TEST KEY (key_id "
                 f"{key_id_for(key)}): its private key is printed there, so "
                 "anyone can sign anything with it, and a signature under it "
                 "shows nothing about who made a bundle")
            return 2
        ok, reason = verify_bundle(data, key)
    except VerificationUnavailable as exc:
        _say(f"CANNOT VERIFY: {exc}")
        return 2
    except UnreadableBundle as exc:
        _say(f"CANNOT VERIFY: the file cannot be read as a bundle: {exc}")
        return 2
    except MalformedBundle as exc:
        _say(f"CANNOT VERIFY: malformed bundle — {exc}")
        return 2
    except ValueError as exc:
        # The public key is not one a signature means anything under.
        _say(f"CANNOT VERIFY: {exc}")
        return 2
    except Exception as exc:  # noqa: BLE001 — malformed input is not a verdict
        _say(f"CANNOT VERIFY: unreadable bundle or malformed key "
             f"({type(exc).__name__}: {exc})")
        return 2
    _say(("VALID: " if ok else "INVALID: ") + reason)
    return 0 if ok else 1


def _bundle_text(bundle_path: str) -> str:
    """The bundle file's text, read within read_bundle_bytes' limits and
    decoded as strict UTF-8 (§6). Raises MalformedBundle."""
    data = read_bundle_bytes(bundle_path)
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MalformedBundle(f"not valid UTF-8 ({exc.reason} at byte "
                              f"{exc.start})") from None


def _field(obj, *keys, default="?"):
    """obj[k1][k2]…, or `default` wherever the shape is not what a bundle's
    is. `inspect` summarizes whatever it is given; it must not crash on it."""
    for k in keys:
        if not isinstance(obj, dict) or k not in obj:
            return default
        obj = obj[k]
    return obj


def _inspect(bundle_path: str) -> int:
    problem = None
    try:
        raw = read_bundle_bytes(bundle_path)
    except UnreadableBundle as exc:
        _say(f"not a bundle: the file cannot be read as one: {exc}")
        return 2
    try:
        data = load_bundle(raw.decode("utf-8"))
    except (MalformedBundle, UnicodeDecodeError) as exc:
        # Summarize what can still be read, labeled as malformed.
        problem = (f"not valid UTF-8 ({exc.reason} at byte {exc.start})"
                   if isinstance(exc, UnicodeDecodeError) else str(exc))
        try:
            data = json.loads(raw.decode("utf-8", "replace"))
        except Exception:  # noqa: BLE001 — nothing more to show
            _say(f"not a bundle: {problem}")
            return 2
    if not isinstance(data, dict):
        _say("not a bundle: the file is not a JSON object")
        return 2
    digest = None
    try:
        from .bundle import _canonical_value, check_body
        try:
            # The whole file, the signature block too, as verify reads it:
            # a lone surrogate in a statement is malformed there (SA-3).
            _canonical_value(data)
        except (ValueError, TypeError, RecursionError) as exc:
            raise MalformedBundle(f"not in canonical form: {exc}") from None
        check_body(data)
        bundle_bound_values(data)
        if problem is None:
            # A digest only of what verify would read: never of a lenient
            # reading of the file (R5B-19).
            digest = bundle_digest(data)
    except Exception as exc:  # noqa: BLE001 — any failure means malformed
        problem = problem or str(exc)
    if data.get("signature") is not None:
        # The block and its statement, as verify checks them: a statement
        # member the format does not define, or an empty block, is
        # malformed there, and is said so here, at the top (R5F-7), in the
        # format's words: nothing the block holds is repeated, since none
        # of it is signed, or it is a claim no verifier checks.
        try:
            from .bundle import _check_statement
            _check_statement(data["signature"])
        except MalformedBundle:
            trouble = ("the signature block, or its statement, is not as "
                       "the format defines it (below)")
            problem = f"{problem}; {trouble}" if problem else trouble
    if problem:
        _say(f"WARNING     malformed bundle — {problem}; it cannot verify")
    # What this release does not write, as verify says it (L93): counted
    # and placed, never quoted.
    from .bundle import _release_said
    foreign = _release_said(data)
    if foreign:
        _say(f"NOTE        {foreign}")

    sig = data.get("signature")
    _say(f"format      {_clip(_field(data, 'bundle_format'))}")
    _say(f"created     {_clip(_field(data, 'created_at'))}")
    _say(f"domain      {_clip(_field(data, 'domain'))}")
    fetch = data.get("fetch")
    host = (None if fetch is None
            else url_host(_field(fetch, "final_url", default=None)))
    note = host_note(host)
    pages = data.get("pages") if isinstance(data.get("pages"), list) else []
    rendered = sum(1 for p in pages
                   if isinstance(p, dict) and isinstance(p.get("fetch"), dict))
    count = _field(fetch, "pages", default=None) if fetch else None
    _say("fetched     " + (
        # Absent is not null: only null says "a file run" (R5B-19).
        "? (the bundle has no fetch record: malformed)"
        if "fetch" not in data else
        ("nothing: a file run" + (f", {rendered} page(s) rendered on this "
                                  "machine" if rendered else ""))
        if fetch is None else
        _clip(host or "?") + (f" ({note}, not a public site)" if note else "")
        + (f", {count} page(s)" if isinstance(count, int) else "")))
    pack = data.get("pack")
    # This release pins no pack and runs no judge (D3): a bundle that has
    # either says so on its maker's word alone (R1A-8).
    _say("pack        " + (
        f"{_clip(_field(pack, 'name'))}@{_clip(_field(pack, 'version'))} "
        f"(signature_verified={_clip(_field(pack, 'signature_verified'))}) — "
        "the bundle's own claim: this release pins no pack"
        if pack is not None else "unpinned"))
    inputs = data.get("inputs")
    if isinstance(inputs, list):
        snaps = sum(1 for e in inputs if isinstance(e, dict)
                    and e.get("kind") == "url-snapshot")
        _say(f"inputs      {len(inputs)}: {len(inputs) - snaps} file(s), "
             f"{snaps} page snapshot(s)")
    else:
        _say("inputs      ?")
    site = data.get("site")
    # The pages no rule could be run on are named beside the rate, which
    # counts only the pages that were evaluated (R5B-16).
    unevaluated = _field(site, "pages_not_evaluable", default=None)
    _say(f"site        pass_rate={_clip(_field(site, 'site_weighted_pass_rate'))} "
         f"tier1_clean={_clip(_field(site, 'pct_pages_tier1_clean'))} "
         f"(tier-1 rules executed: "
         f"{_clip(_field(site, 'tier1_rules_executed'))}"
         f"/{_clip(_field(site, 'tier1_rules_total'))}"
         + (f", never fail: {_clip(_field(site, 'tier1_rules_review_only'))}"
            if _field(site, 'tier1_rules_review_only', default=None)
            is not None else "") + ")"
         + (f"; pages listed {len(pages)}, of which NOT evaluated: "
            f"{_clip(unevaluated)} (the rates leave them out)"
            if unevaluated not in (None, 0) else
            f"; pages listed {len(pages)}"))
    judged = data.get("judged")
    # Any judged record, even an empty one, is what verify reports as one
    # the bundle carries (R5D-15).
    if judged is not None:
        s = _field(judged, "summary", default={})
        _say(f"judged      {_clip(_field(s, 'provider'))} "
             f"model={_clip(_field(s, 'model'))} "
             f"calibrated={_clip(_field(s, 'calibrated'))} "
             f"rate={_clip(_field(s, 'judged_pass_rate'))} — the bundle's own "
             "claim: this release runs no judge")
    else:
        _say("judged      not run")
    if "baseline" in data:
        # The run's --baseline (A10): its gate counted only what that report
        # did not list, so a reader must not take a pass for a clean run
        # (R4B-16).
        base = data["baseline"]
        _say("baseline    " + (
            "none" if base is None else
            "NOT a record (the bundle has "
            + ("a string" if isinstance(base, str) else "an array"
               if isinstance(base, list) else "a number or a boolean")
            + " there): malformed, so verify refuses this bundle"
            if not isinstance(base, dict) else
            "a record without the members this release writes (sha256, "
            "findings, new_findings, new_fail_findings): its maker's own"
            if not {"sha256", "findings", "new_findings",
                    "new_fail_findings"} <= set(base) else
            f"sha256={_clip(_field(base, 'sha256'))} "
            f"made={_clip(_field(base, 'generated_at'))} "
            f"findings={_clip(_field(base, 'findings'))}: "
            f"{_clip(_field(base, 'new_findings'))} of the run's findings "
            f"not in it, {_clip(_field(base, 'new_fail_findings'))} of them "
            "failures in the site's own markup. The gate counted only "
            "findings not in it; the bundle lists every finding"))
    _say(f"digest      {digest or 'none (malformed)'}")
    stmt = _field(sig, "statement", default={})
    if not isinstance(stmt, dict):
        stmt = {}
    kid = _field(sig, "key_id")
    # The bundle's own claim, unverified — but a claim to be a key anyone or
    # no one relies on is worth knowing before anyone relies on the bundle.
    if isinstance(kid, str) and kid in PUBLISHED_TEST_KEY_IDS:
        flag = " (claims a PUBLISHED TEST key: anyone can sign with it)"
    elif isinstance(kid, str) and kid in DEMO_KEY_IDS:
        flag = " (claims the harness's DEMONSTRATION key: in no trust path)"
    else:
        flag = ""
    # Always the algorithm verify uses. signature.alg is an unsigned
    # duplicate (CANONICALIZATION §5) that anyone can rewrite after signing,
    # so it is never echoed: "Ed25519 (certified …)" would print as fact.
    cls = _field(stmt, "attestation_class")
    # The class is the signer's word too: anything but self-signed is a
    # class nothing issues in this release (D5).
    cls_note = ("" if cls == SELF_SIGNED else
                " (a class nothing issues in this release: verify reads it "
                "as no more than self-signed)")
    if sig is not None and not isinstance(sig, dict):
        # A string or a list where the block goes ("VALID - verified by
        # …") is no signature at all (R5B-19).
        held = ("a string" if isinstance(sig, str) else "an array"
                if isinstance(sig, list) else "a number or a boolean")
        _say(f"signature   NOT a signature block (the bundle has {held} "
             "there): malformed, so verify refuses this bundle")
    elif sig is None:
        _say("signature   UNSIGNED")
    elif not sig:
        # An empty block is not "no signature": verify refuses the bundle
        # (R5D-15).
        _say("signature   an EMPTY signature block: malformed, so verify "
             "refuses this bundle")
    else:
        _say(f"signature   Ed25519 key_id={_clip(kid)}{flag} "
             f"class={_clip(cls)}{cls_note} "
             f"signer={_clip(_field(stmt, 'signer'))} "
             f"at={_clip(_field(stmt, 'signed_at'))}")
    if isinstance(sig, dict) and sig:
        odd = [m for m, want in (("alg", SIGNATURE_ALG),
                                 ("context", STATEMENT_FORMAT))
               if m in sig and sig[m] != want]
        extra = len(set(sig) - set(SIGNATURE_MEMBERS))
        if extra:
            odd.append(f"{extra} member(s) the format does not define")
        missing = [m for m in SIGNATURE_MEMBERS if m not in sig]
        if missing:
            odd.append("no " + ", ".join(missing))
        odd += [f"a {m} that is not a string" for m in ("key_id",
                                                          "signature_b64")
                if m in sig and not isinstance(sig[m], str)]
        if odd:
            # Not shown: unsigned, and a verifier refuses the bundle (N10).
            _say("WARNING     signature block: " + ", ".join(odd) + " — "
                 "malformed, so verify refuses this bundle")
        statement = sig.get("statement")
        if "statement" in sig and not isinstance(statement, dict):
            _say("WARNING     statement: not an object — malformed, so "
                 "verify refuses this bundle")
        elif isinstance(statement, dict):
            # Counted, never named: a member no verifier checks would read
            # as a claim (a "certified" member, R5F-7).
            more = len(set(statement) - set(STATEMENT_FIELDS))
            typed = sum(1 for f in STATEMENT_FIELDS
                        if statement.get(f) is not None
                        and not isinstance(statement.get(f), str))
            wrong = ([f"{more} member(s) the format does not define"]
                     if more else []) + ([f"{typed} field(s) that are not "
                                          "strings"] if typed else [])
            if wrong:
                _say("WARNING     statement: " + ", ".join(wrong) + " — "
                     "malformed, so verify refuses this bundle")
    if stmt:
        digest_bound = stmt.get("rulebook_sha256")
        _say(f"bound to    domain={_clip(stmt.get('domain'), True)} "
             f"host={_clip(stmt.get('host'), True)} "
             f"pack={_clip(stmt.get('pack'), True)}"
             f"@{_clip(stmt.get('pack_version'), True)} "
             f"rulebook={_clip(stmt.get('rulebook_version'), True)}"
             + (f" (sha256 {str(digest_bound)[:16]}…)" if digest_bound
                else ""))
    if sig:
        _say("note        run `bellbriar-evidence verify` with the signer's "
             "public key: it checks the signature and says what a valid one "
             "shows")
    # A bundle verify refuses as malformed exits as verify does, 2, after
    # everything that can be read of it is shown (L97).
    return 2 if problem else 0


def _write_new(path: Path, text: str, mode: int) -> None:
    """Create `path`, which must not exist (not even as a symbolic link),
    holding `text`, with `mode` set before any byte is written."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                 | getattr(os, "O_NOFOLLOW", 0), mode)
    try:
        with os.fdopen(fd, "w", encoding="ascii") as fh:
            if hasattr(os, "fchmod"):
                os.fchmod(fh.fileno(), mode)
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
    except BaseException:
        os.unlink(path)           # ours, just made: never leave half of it
        raise


def _staged(path: Path, text: str, mode: int) -> Path:
    """A new file beside `path` holding `text`, ready to be renamed over
    it: a replacement never rewrites the old file in place, where a FIFO
    would hand the new key to whoever reads it and a descriptor opened
    while the old file was readable would read the new one (R1A-3)."""
    import tempfile
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".new",
                               dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="ascii") as fh:
            if hasattr(os, "fchmod"):
                os.fchmod(fh.fileno(), mode)
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
    except BaseException:
        os.unlink(tmp)
        raise
    return Path(tmp)


def _in_a_git_checkout(path: Path) -> bool:
    try:
        here = path.resolve().parent
    except OSError:
        return False
    return any((d / ".git").exists() for d in (here, *here.parents))


def _keygen(prefix: str, force: bool) -> int:
    """Write <prefix>.key and <prefix>.pub (P4-06). An existing file is
    never replaced without --force: the key it held may be the only one
    that verifies bundles already handed out. The private key is created
    readable by its owner only, before any key byte is written. With
    --force, each new file is written beside the old one and renamed over
    it, and only a regular file is ever replaced (R1A-3). Both targets are
    checked before anything is written, so a refusal leaves the old pair
    as it was."""
    import stat as _stat
    key, pub_path = Path(f"{prefix}.key"), Path(f"{prefix}.pub")
    # lexists: a symbolic link counts, even one that points nowhere.
    existing = [str(p) for p in (key, pub_path) if os.path.lexists(p)]
    if existing and not force:
        _say(f"error: {' and '.join(existing)} already exist(s); refusing to "
             "replace a key pair (bundles it signed verify only against its "
             "public key). Choose another --out-prefix, or pass --force.")
        return 2
    for p in (key, pub_path):
        try:
            st = os.lstat(p)
        except FileNotFoundError:
            continue
        except OSError as exc:
            _say(f"error: cannot check {p}: {exc.strerror or exc}")
            return 2
        if _stat.S_ISLNK(st.st_mode):
            _say(f"error: {p} is a symbolic link; refusing to write a key "
                 "through one, or to replace one")
            return 2
        if not _stat.S_ISREG(st.st_mode):
            _say(f"error: {p} is not a regular file (a directory, FIFO or "
                 "device); refusing to replace it, also with --force")
            return 2
    if not key.parent.is_dir():
        _say(f"error: {key.parent} is not a directory")
        return 2
    priv, pub, kid = generate_keypair()
    if not force:
        # Nothing exists at either path: create both, never over a file
        # that appeared since the checks above.
        try:
            _write_new(key, key_file_text(priv, True), 0o600)
        except OSError as exc:
            _say(f"error: cannot write {key}: {exc.strerror or exc}")
            return 2
        try:
            _write_new(pub_path, key_file_text(pub, False), 0o644)
        except OSError as exc:
            os.unlink(key)        # ours, just made: no half pair is left
            _say(f"error: cannot write {pub_path}: {exc.strerror or exc}; "
                 "no key was written")
            return 2
    else:
        staged: list[Path] = []
        try:
            staged.append(_staged(key, key_file_text(priv, True), 0o600))
            staged.append(_staged(pub_path, key_file_text(pub, False), 0o644))
        except OSError as exc:
            for tmp in staged:
                os.unlink(tmp)
            _say(f"error: cannot write beside {key}: {exc.strerror or exc}; "
                 "the old pair is untouched")
            return 2
        try:
            os.replace(staged[0], key)
        except OSError as exc:
            for tmp in staged:
                os.unlink(tmp)
            _say(f"error: cannot replace {key}: {exc.strerror or exc}; the "
                 "old pair is untouched")
            return 2
        try:
            os.replace(staged[1], pub_path)
        except OSError as exc:
            os.unlink(staged[1])
            # The new private key is in place: give its public half here
            # (it is no secret), so the pair is not lost.
            _say(f"error: replaced {key} but cannot replace {pub_path}: "
                 f"{exc.strerror or exc}. The new public key (key_id {kid}) "
                 f"is {pub}; write it to {pub_path} yourself.")
            return 2
    print(f"key_id {kid}\nprivate → {key}  (mode 600; guard it, and keep it "
          f"out of any repository)\npublic  → {pub_path}  (publish it, so "
          "others can verify what you sign)")
    if _in_a_git_checkout(key):
        print(f"warning: {key} is inside a git checkout. Keep it out of every "
              "commit and zip: move it, or add it to .gitignore.",
              file=sys.stderr)
    if os.name != "posix":
        print(f"note: this system has no file modes: make sure only you can "
              f"read {key}")
    return 0


def main(argv=None) -> int:
    """bellbriar-evidence: _main, with everything it prints escaped as
    redact.console_text escapes it (R4G-5), ending quietly with status 2
    when the reader of its output stops reading (R5D-15)."""
    from .redact import run_escaped
    return run_escaped(_main, argv)


def _main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="bellbriar-evidence")
    sub = ap.add_subparsers(dest="cmd", required=True)

    kg = sub.add_parser("keygen", help="generate an Ed25519 key pair for "
                                       "self-signed bundles")
    kg.add_argument("--out-prefix", default="bellbriar",
                    help="writes <prefix>.key (private, mode 600) and "
                         "<prefix>.pub")
    kg.add_argument("--force", action="store_true",
                    help="replace an existing key pair; bundles it signed "
                         "then verify only against the old public key, if "
                         "you keep it")

    vf = sub.add_parser("verify", help="verify a signed bundle offline "
                                       "(exit 0 VALID, 1 INVALID, 2 could "
                                       "not verify)")
    vf.add_argument("bundle")
    vf.add_argument("--public-key", required=True,
                    help="Ed25519 public key: 64-char hex, or a file "
                         "containing it")

    ins = sub.add_parser("inspect", help="summarize a bundle")
    ins.add_argument("bundle")

    args = ap.parse_args(argv)

    if args.cmd == "keygen":
        return _keygen(args.out_prefix, args.force)

    if args.cmd == "verify":
        return _verify(args.bundle, args.public_key)
    return _inspect(args.bundle)


if __name__ == "__main__":
    sys.exit(main())
