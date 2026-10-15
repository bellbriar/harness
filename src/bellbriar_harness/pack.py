"""Pack pinning — Layer 2.

Conceptual point the re-analysis fixed: the *agent* loads the pack at
generation time; the *harness* does not execute it. At eval time the pack
is PINNED — its manifest is verified and its identity recorded into the
evidence bundle, so "which pack version this run was measured against" is
a fact carried inside the evidence rather than a claim made beside it.

Pack manifest (pack.json at the pack root):
{
  "name": "wcag", "version": "1.0.0", "rulebook_min": "0.1.0",
  "files": {"SKILL.md": "<sha256>", ...},
  "signature": {"alg": "Ed25519", "context": "bellbriar-pack/1",
                "key_id": "...", "signature_b64": "..."}
}
The signature (optional in dev) is Ed25519 over
    "bellbriar-pack/1\\x00" || SHA-256(canonical(manifest minus "signature"))
made with Bellbriar's pack key — the same construction as bundle
statements, with a different context so a signature over one artifact
type can never be presented as a signature over another
(docs/CANONICALIZATION.md §4, §7). Manifests signed under the earlier
context-less form are rejected and must be re-signed.
"""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

from .bundle import HAVE_ED25519, SIGNING_CONTEXTS, canonical_bytes, key_id_for

PACK_FORMAT = "bellbriar-pack/1"

if HAVE_ED25519:
    from cryptography.hazmat.primitives.asymmetric import ed25519


class PackError(RuntimeError):
    pass


def load_manifest(pack_dir: str | Path) -> dict:
    path = Path(pack_dir) / "pack.json"
    if not path.is_file():
        raise PackError(f"no pack.json in {pack_dir}")
    return json.loads(path.read_text(encoding="utf-8"))


def verify_files(pack_dir: str | Path, manifest: dict) -> None:
    root = Path(pack_dir)
    for rel, expected in manifest.get("files", {}).items():
        f = root / rel
        if not f.is_file():
            raise PackError(f"pack file missing: {rel}")
        actual = hashlib.sha256(f.read_bytes()).hexdigest()
        if actual != expected:
            raise PackError(f"pack file altered: {rel}")


def manifest_body(manifest: dict) -> dict:
    return {k: v for k, v in manifest.items() if k != "signature"}


def pack_message(body: dict) -> bytes:
    """The bytes actually signed: context || SHA-256(canonical(body))."""
    return (SIGNING_CONTEXTS[PACK_FORMAT]
            + hashlib.sha256(canonical_bytes(body)).digest())


def verify_signature(manifest: dict, public_hex: str | None) -> bool:
    """True if a valid signature by public_hex is present; False if the
    manifest is unsigned or no key was supplied (recorded, not fatal).
    Raises PackError for a signature that is present but wrong."""
    sig = manifest.get("signature")
    if not sig or not public_hex:
        return False
    if not HAVE_ED25519:
        # A key was supplied to check a signed manifest; silently recording
        # "unverified" would look like a verification that happened.
        raise PackError("the cryptography package is required to verify "
                        "the pack signature (pip install cryptography)")
    if sig.get("context") != PACK_FORMAT:
        raise PackError(
            "pack signature carries no signing context — this is a legacy "
            "signature over a bare digest and is no longer accepted; re-sign "
            f"the manifest under {PACK_FORMAT!r}")
    if sig.get("key_id") != key_id_for(public_hex):
        raise PackError("pack signature key_id does not match supplied key")
    try:
        pub = ed25519.Ed25519PublicKey.from_public_bytes(
            bytes.fromhex(public_hex))
        pub.verify(base64.b64decode(sig["signature_b64"]),
                   pack_message(manifest_body(manifest)))
    except Exception as exc:  # noqa: BLE001
        raise PackError(f"pack signature invalid: {exc}") from exc
    return True


#: Fields that define a bundle signature statement (docs/CANONICALIZATION.md
#: §5). No pack manifest has them.
_STATEMENT_FIELDS = ("statement_format", "bundle_digest_sha256",
                     "attestation_class")


def _check_manifest_shape(body: dict) -> None:
    """Sign only what is a pack manifest. The pack context already keeps a
    pack signature from verifying as a bundle signature; refusing anything
    shaped like a statement keeps a pack signer from being used to produce
    one in the first place (§4, §7)."""
    found = [f for f in _STATEMENT_FIELDS if f in body]
    if found:
        raise PackError(
            f"refusing to sign: the body carries statement fields "
            f"({', '.join(found)}); a pack signer signs pack manifests only")
    if not (isinstance(body.get("name"), str)
            and isinstance(body.get("version"), str)
            and isinstance(body.get("files"), dict)):
        raise PackError("refusing to sign: a pack manifest needs a string "
                        "'name', a string 'version' and a 'files' object")


def sign_manifest(manifest: dict, private_hex: str) -> dict:
    """Service-side: sign a pack manifest for release."""
    if not HAVE_ED25519:
        raise PackError("cryptography package required")
    _check_manifest_shape(manifest_body(manifest))
    priv = ed25519.Ed25519PrivateKey.from_private_bytes(
        bytes.fromhex(private_hex))
    sig = priv.sign(pack_message(manifest_body(manifest)))
    manifest["signature"] = {
        "alg": "Ed25519",
        "context": PACK_FORMAT,
        "key_id": key_id_for(priv.public_key().public_bytes_raw().hex()),
        "signature_b64": base64.b64encode(sig).decode("ascii"),
    }
    return manifest


def pack_reference(pack_dir: str | Path,
                   public_hex: str | None = None) -> dict:
    """Verify a pack directory and return the bundle-embeddable reference."""
    manifest = load_manifest(pack_dir)
    if not isinstance(manifest, dict):
        raise PackError(f"{Path(pack_dir) / 'pack.json'} is not a JSON object")
    for field in ("name", "version"):
        value = manifest.get(field)
        if value is not None and not isinstance(value, str):
            # Bound into signed statements, whose values are strings or
            # null; a numeric version would make every bundle pinning this
            # pack fail to sign. Say so here, where the fix is obvious.
            raise PackError(f"{Path(pack_dir) / 'pack.json'}: {field!r} must "
                            f'be a string such as "1.0.0", not {value!r}')
    verify_files(pack_dir, manifest)
    signed = verify_signature(manifest, public_hex)
    body = manifest_body(manifest)
    return {
        "name": manifest.get("name"),
        "version": manifest.get("version"),
        "manifest_sha256": hashlib.sha256(canonical_bytes(body)).hexdigest(),
        "files": len(manifest.get("files", {})),
        "signature_verified": signed,
    }
