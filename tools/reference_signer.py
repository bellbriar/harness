"""Reference signing service and its client — NOT part of the installed
package, and NOT the production service.

Kept in the repository for the ship list's L2: remote signing returns with
a production signing service. Until then bellbriar-harness signs only
self-signed bundles (decision D5), and nothing it installs calls this
module. It moved here from `bellbriar_harness.server_reference`, with the
client half (`remote_sign`, from `bellbriar_harness.bundle`), so that no
installed code can attach a statement of a class the installed attestation
text does not describe. ATTESTED_SUBMISSION_TEXT below is the attestation
text attested-submission bundles carried; L5 brings it back with L2.

Demonstrates the two metered endpoints so integrators can build against a
real contract:

  POST /v1/sign   Bearer-auth; validates the subscription (domain, the
                  host a URL run fetched, pack) from keys.json; signs the
                  submitted digest; appends a usage record. This is the
                  meter.
  POST /v1/judge  Bearer-auth; reference build has no model configured and
                  says so honestly (verdict needs_review) — production
                  wires a calibrated provider here.
  GET  /v1/public-key   Publishes {key_id, public_hex, attestation}.

keys.json:
{"api_keys": {"<key>": {"customer": "...", "domains": ["example.com"],
              "packs": {"wcag": ">=0"}}}}

"domains" scopes a subscription; without it, any domain is signed. Entries
are lowercase host names. "example.com" covers example.com and
www.example.com, as a stated domain and as the host a URL run fetched.
"*.example.com" covers the names below it: under a scoped subscription, a
run measured on a subdomain (staging.example.com) is signed only when the
subscription lists it. Either way the statement records the domain and
the host, so the evidence says which host was measured.

Run: python tools/reference_signer.py --keys keys.json \
       --private-key FILE [--port 8787]
Production concerns deliberately out of scope here: TLS, rotation, rate
limits, billing, replay windows, audit storage.
"""
from __future__ import annotations

import argparse
import json
import re
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import sys
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bellbriar_harness.bundle import (  # noqa: E402
    ATTESTED_SUBMISSION, BOUND_FIELDS, HAVE_ED25519, STATEMENT_FORMAT,
    build_statement, bundle_bound_values, bundle_digest, host_scope,
    key_id_for, normalize_host, _sign_statement, _site)

#: The attestation text bundles signed by this service carried, until D5
#: made every 1.0 bundle self-signed (the ship list's L5).
ATTESTED_SUBMISSION_TEXT = (
    "This signature covers a signed statement, not a bare digest. The "
    "statement records the bundle digest together with the bundle format, "
    "domain, fetched host, pack, pack version and rulebook version that the "
    "signer authorized, and verification fails unless every one of them "
    "matches this bundle and, where a domain is stated, any fetched host is "
    "that domain, its www. form, or a host below the site they name. A "
    "valid signature of class 'attested-submission' "
    "therefore attests that: (1) an authenticated subscription in good "
    "standing submitted this exact bundle digest at signed_at; (2) that "
    "subscription covered the domain, any fetched host, and the pack "
    "version named in this bundle; (3) nothing in the bundle outside its "
    "signature block has changed since signing. It does NOT attest that "
    "the evaluation was executed "
    "correctly or on the stated inputs — the client computed those. "
    "Attested execution requires the Bellbriar hosted runner. A signature "
    "of class 'self-signed' asserts no subscription at all and proves only "
    "origin and integrity. Where this bundle has a `fetch` block, that "
    "block is the client's record of one capture of a live page at the "
    "recorded time; no signature attests that the capture took place as "
    "recorded. The page may have differed before or after, the recorded "
    "snapshot hash identifies the bytes the client reports it evaluated, "
    "and findings attributed to third-party injected markup are reported "
    "but excluded from the score. No signature of any class is a "
    "determination of WCAG conformance, legal compliance, or fitness for "
    "any purpose."
)

if HAVE_ED25519:
    import base64

    from cryptography.hazmat.primitives.asymmetric import ed25519

_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
_CONSTRAINT_RE = re.compile(r"^\s*(>=|<=|==|!=|>|<|=)?\s*(.+?)\s*$")


def parse_version(v: str) -> tuple[int, int, int]:
    """Loose semver parse. 'v1.2' -> (1,2,0); '1.0.0-rc1' -> (1,0,0)."""
    core = str(v).strip().lstrip("vV").split("+")[0].split("-")[0]
    parts = core.split(".")[:3]
    out = []
    for part in parts:
        digits = "".join(c for c in part if c.isdigit())
        out.append(int(digits) if digits else 0)
    while len(out) < 3:
        out.append(0)
    return tuple(out)  # type: ignore[return-value]


def satisfies(version: str | None, constraint: str | None) -> tuple[bool, str]:
    """Evaluate a pack version against a subscription constraint.

    Supported: '*' / 'any' / '' (anything, version may be absent), and
    comma-separated clauses combined with AND, each of the form
    '>=1.0.0', '>1.0', '<=2', '<2.0.0', '==1.0.0', '!=1.0.0', or a bare
    '1.0.0' meaning exact equality.

    A constraint other than '*' REQUIRES a version: 'the domain is running a
    current pack' cannot be evaluated against an unstated one.
    """
    c = (constraint or "").strip()
    if c in ("", "*", "any"):
        return True, "any version"
    if not version:
        return False, (f"subscription requires pack version {c!r} but the "
                       "run stated no pack version")
    have = parse_version(version)
    for clause in [x for x in c.split(",") if x.strip()]:
        m = _CONSTRAINT_RE.match(clause)
        if not m:
            return False, f"unparseable version constraint {clause!r}"
        op, want_raw = m.group(1) or "==", m.group(2)
        want = parse_version(want_raw)
        ok = {">=": have >= want, ">": have > want, "<=": have <= want,
              "<": have < want, "==": have == want, "=": have == want,
              "!=": have != want}[op]
        if not ok:
            return False, (f"pack version {version} does not satisfy "
                           f"{clause.strip()!r}")
    return True, f"{version} satisfies {c}"


def _covers(entries: list, name: str) -> bool:
    """Does a subscription's domain list cover a host name? "example.com"
    covers example.com and www.example.com; "*.example.com" covers every
    name below example.com, and not example.com itself."""
    for entry in entries:
        if not isinstance(entry, str):
            continue
        if entry.startswith("*."):
            if name.endswith(entry[1:]):
                return True
        elif host_scope(name, entry) == "same":
            return True
    return False


class SigningService:
    def __init__(self, keys_path: str, private_hex: str,
                 usage_log: str | None = None):
        self.keys = json.loads(Path(keys_path).read_text())["api_keys"]
        self.priv = ed25519.Ed25519PrivateKey.from_private_bytes(
            bytes.fromhex(private_hex))
        self.public_hex = self.priv.public_key().public_bytes_raw().hex()
        self.key_id = key_id_for(self.public_hex)
        self.usage_log = usage_log
        self._lock = threading.Lock()

    def _record(self, api_key: str, endpoint: str, ok: bool) -> None:
        if not self.usage_log:
            return
        line = json.dumps({"ts": datetime.now(timezone.utc).isoformat(),
                           "key": api_key[:8] + "…", "endpoint": endpoint,
                           "ok": ok})
        with self._lock, open(self.usage_log, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def authorize(self, api_key: str) -> dict | None:
        return self.keys.get(api_key)

    def sign(self, api_key: str, req: dict) -> tuple[int, dict]:
        """Authorize, then sign a STATEMENT recording what was authorized.

        The signer never sees the bundle body, so the client states the
        bound fields. Recording them inside the signed statement is what
        makes that safe: verify_bundle re-checks every one against the
        bundle itself and rejects a mismatch.
        """
        sub = self.authorize(api_key)
        if sub is None:
            self._record(api_key, "sign", False)
            return 401, {"error": "unknown api key"}

        digest = req.get("digest_sha256", "")
        if not isinstance(digest, str) or not _DIGEST_RE.match(digest):
            self._record(api_key, "sign", False)
            return 400, {"error": "digest_sha256 must be 64 lowercase hex"}

        bound = {f: req.get(f) for f in BOUND_FIELDS}
        wrong = [f for f, v in bound.items()
                 if v is not None and not isinstance(v, str)]
        if wrong:
            # Statement values are strings or null (CANONICALIZATION §5).
            self._record(api_key, "sign", False)
            return 400, {"error": f"{', '.join(wrong)} must be a string or "
                                  "null"}
        for field in ("domain", "host"):
            value = bound[field]
            if value is None:
                continue
            try:
                normal = normalize_host(value)
            except ValueError:
                normal = None
            if normal != value:
                # One spelling per host, so a signed name can't be a
                # look-alike of another (Unicode, case, trailing dot).
                self._record(api_key, "sign", False)
                return 400, {"error": f"{field} must be a normalized host "
                                      f"name (lowercase ASCII, IDNA "
                                      f"A-labels), not {value!r}"}
        domain, host, pack, pack_version = (
            bound["domain"], bound["host"], bound["pack"], bound["pack_version"])
        scope = host_scope(host, domain)
        if scope == "unrelated":
            self._record(api_key, "sign", False)
            return 403, {"error": f"host {host!r} is not domain {domain!r} or "
                                  "a subdomain of it"}

        allowed_domains = sub.get("domains")
        if allowed_domains:
            if not domain:
                self._record(api_key, "sign", False)
                return 403, {"error": "this subscription is scoped to "
                                      "specific domains; the run stated none"}
            if not _covers(allowed_domains, domain):
                self._record(api_key, "sign", False)
                return 403, {"error": f"domain {domain!r} not on subscription"}
            if host is not None and not _covers(allowed_domains, host):
                self._record(api_key, "sign", False)
                if scope == "subdomain":
                    return 403, {"error": f"host {host!r} is a subdomain of "
                                          f"{_site(domain)!r} and not on "
                                          f"this subscription; runs measured "
                                          f"on subdomains need "
                                          f"'*.{_site(domain)}'"}
                return 403, {"error": f"host {host!r} not on subscription"}

        packs = sub.get("packs")
        if packs is not None:
            if not pack:
                self._record(api_key, "sign", False)
                return 403, {"error": "this subscription is scoped to "
                                      "specific packs; the run pinned none"}
            if pack not in packs:
                self._record(api_key, "sign", False)
                return 403, {"error": f"pack {pack!r} not on subscription"}
            ok, why = satisfies(pack_version, packs[pack])
            if not ok:
                self._record(api_key, "sign", False)
                return 403, {"error": f"pack {pack!r}: {why}"}

        statement = build_statement(bound, self.key_id, "bellbriar-reference",
                                    ATTESTED_SUBMISSION, digest)
        sig_b64 = _sign_statement(statement, self.priv)
        self._record(api_key, "sign", True)
        return 200, {
            "alg": "Ed25519",
            "key_id": self.key_id,
            "statement": statement,
            "signature_b64": sig_b64,
            "attestation": ATTESTED_SUBMISSION_TEXT,
        }


def make_handler(service: SigningService):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, obj: dict) -> None:
            body = json.dumps(obj).encode("utf-8")
            self.send_response(code)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _api_key(self) -> str:
            auth = self.headers.get("authorization", "")
            return auth.removeprefix("Bearer ").strip()

        def do_GET(self):  # noqa: N802 (http.server API)
            if self.path == "/v1/public-key":
                self._send(200, {"key_id": service.key_id,
                                 "public_hex": service.public_hex,
                                 "attestation": ATTESTED_SUBMISSION_TEXT})
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("content-length", "0"))
            try:
                req = json.loads(self.rfile.read(length) or b"{}")
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._send(400, {"error": "invalid json"})
                return
            if not isinstance(req, dict):
                self._send(400, {"error": "the request body must be a JSON "
                                          "object"})
                return
            if self.path == "/v1/sign":
                code, obj = service.sign(self._api_key(), req)
                self._send(code, obj)
            elif self.path == "/v1/judge":
                if service.authorize(self._api_key()) is None:
                    self._send(401, {"error": "unknown api key"})
                    return
                service._record(self._api_key(), "judge", True)
                self._send(200, {
                    "verdict": "needs_review",
                    "rationale": "Reference server has no judge model "
                                 "configured; production wires a calibrated "
                                 "provider here.",
                    "model": "reference-none"})
            else:
                self._send(404, {"error": "not found"})

        def log_message(self, *args):  # silence default stderr chatter
            return

    return Handler


def serve(keys: str, private_hex: str, host: str = "127.0.0.1",
          port: int = 8787, usage_log: str | None = None
          ) -> ThreadingHTTPServer:
    service = SigningService(keys, private_hex, usage_log)
    httpd = ThreadingHTTPServer((host, port), make_handler(service))
    httpd.bellbriar_service = service
    return httpd


def remote_sign(bundle: dict, base_url: str, api_key: str,
                timeout: int = 30) -> dict:
    """Obtain a signature from a Bellbriar signing endpoint (the meter).

    Sends the bundle digest plus the bundle's own bound values. The server
    authorizes against them and returns a statement recording what it
    authorized. This function then re-checks the returned statement against
    the bundle before storing it, so a signer that authorized something
    other than what was asked for is caught here rather than at the
    customer's counsel's desk.
    """
    # A bundle this signer signs carries the text that describes its class,
    # not the self-signed text the harness writes (R1A, outside its items).
    bundle["attestation"] = ATTESTED_SUBMISSION_TEXT
    bound = bundle_bound_values(bundle)
    digest = bundle_digest(bundle)
    body = json.dumps({"digest_sha256": digest, **bound}).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/sign", data=body, method="POST",
        headers={"content-type": "application/json",
                 "authorization": f"Bearer {api_key}"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    statement = data.get("statement")
    if not isinstance(statement, dict):
        raise RuntimeError("signer returned no statement")
    if statement.get("statement_format") != STATEMENT_FORMAT:
        raise RuntimeError(
            f"signer returned a statement of format "
            f"{statement.get('statement_format')!r}, not {STATEMENT_FORMAT!r}; "
            "refusing to attach a signature no verifier will accept")
    if statement.get("bundle_digest_sha256") != digest:
        raise RuntimeError("signer returned a statement for a different "
                           "bundle digest")
    for field in BOUND_FIELDS:
        if statement.get(field) != bound.get(field):
            raise RuntimeError(
                f"signer authorized {field}={statement.get(field)!r} but this "
                f"bundle says {bound.get(field)!r}; refusing to attach")
    bundle["signature"] = {
        "alg": data.get("alg", "Ed25519"),
        "context": STATEMENT_FORMAT,
        "key_id": statement.get("key_id"),
        "statement": statement,
        "signature_b64": data["signature_b64"],
    }
    return bundle


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="bellbriar-reference-server")
    ap.add_argument("--keys", required=True)
    ap.add_argument("--private-key", required=True, metavar="FILE",
                    help="file holding the Ed25519 private key (hex); never "
                         "the key itself on the command line")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--usage-log", default="bellbriar-usage.jsonl")
    args = ap.parse_args(argv)
    # Read as bellbriar-eval --sign-key reads a key file: no message quotes
    # what --private-key was given, which may be a key typed there (R1A-1).
    from bellbriar_harness.bundle import KeyFileError, read_private_key_file
    try:
        private_hex, _mode = read_private_key_file(args.private_key)
    except KeyFileError as exc:
        print(f"--private-key: {exc}", file=sys.stderr)
        return 2
    httpd = serve(args.keys, private_hex, args.host, args.port,
                  args.usage_log)
    print(f"reference signer on http://{args.host}:{args.port} "
          f"(key_id {httpd.bellbriar_service.key_id})")
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
