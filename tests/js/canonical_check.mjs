// An independent JavaScript reading of docs/CANONICALIZATION.md.
//
// Parsing follows §6 (duplicate names, number literals that a double does
// not hold exactly as written, and §2 violations are malformed), canonical
// form is JSON.stringify with object keys sorted (RFC 8785 for everything
// §2 admits), and signatures are checked with Node's own Ed25519. Nothing
// is shared with the Python implementation, so when the two agree, the
// spec — not one library — is what a verifier needs.
//
//   node canonical_check.mjs VECTORS.json CASES.json
//
// CASES.json: {"bundles": [{"name", "text" or "bytes_b64", "public_hex"}],
//              "roundtrip": ["<canonical text>", ...]}
// Prints one JSON object; tests/test_canonicalization.py runs it whenever
// `node` is available (Node 22 or later: it needs JSON.parse source text).
import { createHash, createPublicKey, verify } from "node:crypto";
import { readFileSync } from "node:fs";

const STATEMENT_FORMAT = "bellbriar-signature/1";
const PACK_FORMAT = "bellbriar-pack/1";
const BOUND_FIELDS = ["bundle_format", "domain", "host", "pack", "pack_version",
                      "pack_sha256", "rulebook_version", "rulebook_sha256"];
// §5: a signature block has exactly these members.
const SIGNATURE_MEMBERS = ["alg", "context", "key_id", "statement", "signature_b64"];
const STATEMENT_FIELDS = ["statement_format", "bundle_digest_sha256", "attestation_class",
                          "key_id", "signer", "signed_at", ...BOUND_FIELDS];
const MAX_EXACT_INT = 2 ** 53;
const MAX_DEPTH = 32;
// §5 "The body": its members, their JSON types, and which must be present.
const BODY_MEMBERS = {
  bundle_format: ["string"], created_at: ["string"], tool: ["object"],
  rulebook_version: ["string"], rulebook_sha256: ["string", "null"],
  domain: ["string", "null"], pack: ["object", "null"], inputs: ["array"],
  fetch: ["object", "null"], layers: ["array"], coverage_note: ["string"],
  site: ["object"], pages: ["array"], judged: ["object", "null"],
  baseline: ["object", "null"], attestation: ["string"], signature: ["object", "null"],
};
const BODY_REQUIRED = ["bundle_format", "created_at", "tool", "rulebook_version", "domain",
                       "pack", "inputs", "fetch", "layers", "coverage_note", "site", "pages",
                       "judged", "attestation"];
const BUNDLE_FORMAT = "bellbriar-evidence/1";
// §8: Ed25519's field prime, group order, and the y of its points of small order.
const P = (1n << 255n) - 19n;
const L = (1n << 252n) + 27742317777372353535851937790883648493n;
const leInt = (buf) => {
  let n = 0n;
  for (let i = buf.length - 1; i >= 0; i--) n = (n << 8n) | BigInt(buf[i]);
  return n;
};
const SMALL_ORDER_Y = new Set([0n, 1n, P - 1n,
  leInt(Buffer.from("26e8958fc2b227b045c3f489f2ef98f0d5dfac05d3c63339b13802886d53fc05", "hex")),
  leInt(Buffer.from("c7176a703d4dd84fba3c0b760d10670f2a2053fa2c39ccc64ec7fd7792ac037a", "hex"))]);
// A point of small order, or y written at or above the field prime.
function weakPoint(buf) {
  const y = leInt(buf) & ((1n << 255n) - 1n);
  return y >= P || SMALL_ORDER_Y.has(y);
}
// §8: no point of the curve (RFC 8032 §5.1.3): no x for its y, or x zero
// with the sign bit set.
const modPow = (b, e, m) => {
  let r = 1n;
  b %= m;
  for (; e > 0n; e >>= 1n, b = b * b % m) if (e & 1n) r = r * b % m;
  return r;
};
const D = ((-121665n * modPow(121666n, P - 2n, P)) % P + P) % P;
function offCurve(buf) {
  const y = leInt(buf) & ((1n << 255n) - 1n);
  if (y >= P) return true;
  const u = ((y * y - 1n) % P + P) % P;
  const v = (D * y * y + 1n) % P;
  const x2 = u * modPow(v, P - 2n, P) % P;
  if (x2 === 0n) return (buf[31] & 0x80) !== 0;
  return modPow(x2, (P - 1n) / 2n, P) !== 1n;
}

class Malformed extends Error {}

// ---------------------------------------------------------------- §2 / §6 parsing

// A JSON number literal as sign, significant digits and exponent, so two
// spellings of one decimal value compare equal ("1.0" and "1", "1e2" and "100").
function decimalKey(literal) {
  const m = /^(-?)(\d+)(?:\.(\d+))?(?:[eE]([+-]?\d+))?$/.exec(literal);
  if (!m) throw new Malformed(`not a JSON number: ${literal}`);
  const [, sign, whole, frac = "", exp = "0"] = m;
  let digits = (whole + frac).replace(/^0+/, "");
  if (digits === "") return "0";
  let e = BigInt(exp) - BigInt(frac.length);
  const zeros = digits.length - digits.replace(/0+$/, "").length;
  digits = digits.slice(0, digits.length - zeros);
  e += BigInt(zeros);
  return `${sign}${digits}e${e}`;
}

function checkNumber(value, literal) {
  if (!Number.isFinite(value)) throw new Malformed(`number ${literal} does not fit in a double`);
  if (Number.isInteger(value) && Math.abs(value) > MAX_EXACT_INT)
    throw new Malformed(`number ${literal} exceeds 2^53`);
  const read = JSON.stringify(value);
  if (decimalKey(literal) !== decimalKey(read))
    throw new Malformed(`number ${literal} is read as ${read}`);
  if (!Number.isInteger(value) && Math.abs(value) < 1e-4)
    throw new Malformed(`number ${literal} is smaller than 0.0001`);
}

// What JSON.parse does not report: a member name repeated within one
// object, and nesting deeper than MAX_DEPTH. The text is already known to
// be valid JSON.
function checkStructure(text) {
  const stack = [];
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    const top = stack[stack.length - 1];
    if (c === '"') {
      let j = i + 1;
      while (text[j] !== '"') j += text[j] === "\\" ? 2 : 1;
      if (top && top.names && top.expectName) {
        const name = JSON.parse(text.slice(i, j + 1));
        if (top.names.has(name)) throw new Malformed(`duplicate member name ${JSON.stringify(name)}`);
        top.names.add(name);
        top.expectName = false;
      }
      i = j;
    } else if (c === "{" || c === "[") {
      stack.push(c === "{" ? { names: new Set(), expectName: true } : {});
      if (stack.length > MAX_DEPTH) throw new Malformed(`nested deeper than ${MAX_DEPTH} levels`);
    } else if (c === "}" || c === "]") stack.pop();
    else if (c === "," && top && top.names) top.expectName = true;
  }
}

// §6: a file's bytes are strict UTF-8. A lenient decoder turns a stray byte
// into U+FFFD and would verify a file whose bytes were never signed.
function decodeStrict(bytes) {
  try {
    return new TextDecoder("utf-8", { fatal: true, ignoreBOM: true }).decode(bytes);
  } catch {
    throw new Malformed("not valid UTF-8");
  }
}

function parseStrict(text) {
  if (text.startsWith("﻿")) throw new Malformed("the file starts with a byte-order mark");
  let value;
  try {
    value = JSON.parse(text, function (key, v, context) {
      if (!/^[\x00-\x7f]*$/.test(key)) throw new Malformed("object keys must be ASCII");
      if (typeof v === "number") checkNumber(v, context.source);
      if (typeof v === "string" && !v.isWellFormed()) throw new Malformed("lone surrogate in a string");
      return v;
    });
  } catch (e) {
    throw e instanceof Malformed ? e : new Malformed(`not valid JSON: ${e.message}`);
  }
  checkStructure(text);
  return value;
}

// ---------------------------------------------------------------- §2 canonical form, §6 verify

function canonical(v) {
  if (Array.isArray(v)) return "[" + v.map(canonical).join(",") + "]";
  if (v !== null && typeof v === "object") {
    return "{" + Object.keys(v).sort()
      .map((k) => JSON.stringify(k) + ":" + canonical(v[k])).join(",") + "}";
  }
  return JSON.stringify(v);
}

// §5: the host read from fetch.final_url, by plain string steps.
function urlHost(url) {
  if (typeof url !== "string" || !/^[!-~]+$/.test(url)) return null;
  const m = /^https?:\/\/([^\/?#]*)/i.exec(url);
  if (!m || m[1].includes("\\") || m[1].includes("@")) return null;
  const hostport = m[1];
  let host;
  if (hostport.startsWith("[")) {
    const end = hostport.indexOf("]");
    if (end < 0) return null;
    host = hostport.slice(1, end);
    if (!/^[0-9A-Fa-f:.]+$/.test(host)) return null;
    const port = hostport.slice(end + 1);
    if (port !== "" && !/^:[0-9]*$/.test(port)) return null;
  } else {
    const colon = hostport.indexOf(":");
    host = colon < 0 ? hostport : hostport.slice(0, colon);
    if (!/^[A-Za-z0-9._-]+$/.test(host)) return null;
    if (colon >= 0 && !/^[0-9]*$/.test(hostport.slice(colon + 1))) return null;
  }
  host = host.toLowerCase();
  if (host.endsWith(".")) host = host.slice(0, -1);
  return host === "" ? null : host;
}

// §5 "Pages": a recorded path that names a site, not a file: after any
// Cc, Cf, Zs, Zl or Zp characters, "http:" or "https:" and a slash or a
// backslash.
const namesSite = (path) => typeof path === "string" &&
  /^[\p{Cc}\p{Cf}\p{Zs}\p{Zl}\p{Zp}]*https?:[\/\\]/iu.test(path);

// §5 "Pages": a file's name whose first part holds a colon or a
// character outside ASCII is written after "./", so that no one reads it
// as a site; a name that would be, and is not, is no name a run records.
const notAsRecorded = (path) => {
  if (typeof path !== "string") return false;
  const first = path.split("/")[0];
  return first.includes(":") || /[^\x00-\x7f]/.test(first) || namesSite(path);
};

// §5: this machine, as a page record of a file run must name it.
function loopbackHost(h) {
  return h === "localhost" || h.endsWith(".localhost") || h === "::1" ||
    /^127(\.(25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])){3}$/.test(h);
}

// §6 step 6: how the fetched host relates to the stated domain.
function hostScope(host, domain) {
  if (!host || !domain) return "unstated";
  if (host === domain) return "same";
  const isAddress = (name) => /^[0-9.]+$/.test(name) || name.includes(":");
  if (isAddress(host) || isAddress(domain)) return "unrelated";
  const site = (name) => {
    const rest = name.startsWith("www.") ? name.slice(4) : name;
    return rest.includes(".") ? rest : name;
  };
  if (site(host) === site(domain)) return "same";
  return host.endsWith("." + site(domain)) ? "subdomain" : "unrelated";
}

const sha256 = (text) => createHash("sha256").update(Buffer.from(text, "utf8")).digest();
const context = (format) => Buffer.from(format + "\0", "utf8");
const isObject = (v) => v !== null && typeof v === "object" && !Array.isArray(v);

function publicKey(hex) {
  const x = Buffer.from(hex, "hex").toString("base64url");
  return createPublicKey({ key: { kty: "OKP", crv: "Ed25519", x }, format: "jwk" });
}

function keyId(hex) {
  return createHash("sha256").update(Buffer.from(hex, "hex")).digest("hex").slice(0, 16);
}

// §5: a `domain` that is a string is a host in the one spelling, read by
// its spelling alone (SA-4).
function spelledOnce(d) {
  if (d === "" || !/^[\x00-\x7f]+$/.test(d)) return false;
  if (d.includes(":")) {
    try { return new URL(`http://[${d}]/`).hostname === `[${d}]`; } catch { return false; }
  }
  if (!/^[a-z0-9_-]+(\.[a-z0-9_-]+)*$/.test(d)) return false;
  if (/^[0-9.]+$/.test(d)) {
    const parts = d.split(".");
    return parts.length === 4 &&
      parts.every((p) => /^(0|[1-9][0-9]{0,2})$/.test(p) && Number(p) <= 255);
  }
  return !/^([0-9]+|0x[0-9a-f]*)$/.test(d.split(".").pop());
}

// §5 "The body": closed, of this format, its members of their types.
function jsonType(v) {
  return v === null ? "null" : Array.isArray(v) ? "array" : typeof v;
}
function checkBody(bundle) {
  if (bundle.bundle_format !== BUNDLE_FORMAT) return "MALFORMED: not a bundle format this verifier reads";
  for (const k of Object.keys(bundle))
    if (!Object.hasOwn(BODY_MEMBERS, k)) return `MALFORMED: the bundle has a member the format does not define (${k})`;
  for (const k of BODY_REQUIRED)
    if (!Object.hasOwn(bundle, k)) return `MALFORMED: the bundle lacks ${k}`;
  for (const [k, types] of Object.entries(BODY_MEMBERS))
    if (Object.hasOwn(bundle, k) && !types.includes(jsonType(bundle[k])))
      return `MALFORMED: ${k} is not ${types.join(" or ")}`;
  if (typeof bundle.domain === "string" && !spelledOnce(bundle.domain))
    return "MALFORMED: domain is not a host in the one spelling §5 gives";
  return null;
}

// §6. "VALID", "INVALID: <reason>" or "MALFORMED: <reason>".
function verifyBundle(bundle, pubHex) {
  // The key first: one that is not a key, encodes a point of small
  // order, or encodes no point, is "could not verify" (§6, §8).
  // Only ASCII space, tab, CR and LF around it (§6): trim() takes more.
  const bare = typeof pubHex === "string" ? pubHex.replace(/^[ \t\r\n]+|[ \t\r\n]+$/g, "") : null;
  if (bare === null || !/^[0-9a-fA-F]{64}$/.test(bare))
    return "MALFORMED: the public key is not an Ed25519 public key";
  pubHex = bare.toLowerCase();
  if (weakPoint(Buffer.from(pubHex, "hex")))
    return "MALFORMED: the public key is a point of small order, or not canonical";
  if (offCurve(Buffer.from(pubHex, "hex")))
    return "MALFORMED: the public key is no point of the curve";
  // Every malformed condition before any verdict, in the order §6 lists
  // them (parseStrict has already checked every value against §2).
  if (!isObject(bundle)) return "MALFORMED: a bundle is a JSON object";
  const body = checkBody(bundle);
  if (body) return body;
  const records = checkRecords(bundle);
  if (records) return records;
  return verifySignature(bundle, pubHex);
}

// §5 "Pages" and the other structure §6 lists, on a bundle whose body
// checkBody accepted. null, or "MALFORMED: <reason>".
function checkRecords(bundle) {
  if (!isObject(bundle)) return "MALFORMED: a bundle is a JSON object";
  if (bundle.pack !== undefined && bundle.pack !== null && !isObject(bundle.pack))
    return "MALFORMED: pack must be an object or null";
  if (bundle.fetch !== undefined && bundle.fetch !== null && !isObject(bundle.fetch))
    return "MALFORMED: fetch must be an object or null";
  let fetchedHost = null;
  if (isObject(bundle.fetch)) {
    fetchedHost = urlHost(bundle.fetch.final_url);
    if (fetchedHost === null) return "MALFORMED: fetch.final_url gives no host";
    if (Object.hasOwn(bundle.fetch, "host") && bundle.fetch.host !== fetchedHost)
      return "MALFORMED: fetch.host is not the host of fetch.final_url";
  }
  // §5 "Pages": a URL run counts its pages, and each has its own capture
  // record, is named by its final_url and names the bound host; a run that
  // fetched nothing has no page record, or one for every page naming this
  // machine (a build rendered on loopback).
  const urlRun = isObject(bundle.fetch);
  if (bundle.pages !== undefined && bundle.pages !== null) {
    if (!Array.isArray(bundle.pages)) return "MALFORMED: pages must be an array";
    const records = [];
    for (let i = 0; i < bundle.pages.length; i++) {
      const page = bundle.pages[i];
      if (!isObject(page)) return `MALFORMED: pages[${i}] is not an object`;
      if (!Object.hasOwn(page, "fetch")) return `MALFORMED: pages[${i}] has no fetch member`;
      const rec = page.fetch;
      if (rec !== null && !isObject(rec)) return `MALFORMED: pages[${i}].fetch must be an object or null`;
      records.push(rec);
    }
    if (urlRun) {
      const n = bundle.fetch.pages;
      if (typeof n !== "number" || !Number.isInteger(n) || n !== bundle.pages.length)
        return "MALFORMED: fetch.pages is not the number of pages";
    } else if (records.some((r) => r !== null) && records.some((r) => r === null)) {
      return "MALFORMED: some pages have a capture record and some do not";
    }
    for (let i = 0; i < records.length; i++) {
      const rec = records[i];
      if (rec === null) {
        if (urlRun) return `MALFORMED: pages[${i}] of a URL run has no capture record`;
        continue;
      }
      const h = urlHost(rec.final_url);
      if (h === null) return `MALFORMED: pages[${i}].fetch.final_url gives no host`;
      if (Object.hasOwn(rec, "host") && rec.host !== h)
        return `MALFORMED: pages[${i}].fetch.host is not the host of its final_url`;
      if (fetchedHost !== null && h !== fetchedHost)
        return `MALFORMED: pages[${i}] was fetched from another host than fetch.final_url`;
      if (fetchedHost === null && !loopbackHost(h))
        return `MALFORMED: pages[${i}].fetch names a host other than this machine in a file run`;
      if (urlRun && bundle.pages[i].path !== rec.final_url)
        return `MALFORMED: pages[${i}].path is not its fetch.final_url`;
    }
    if (!urlRun)
      for (let i = 0; i < bundle.pages.length; i++) {
        if (namesSite(bundle.pages[i].path))
          return `MALFORMED: pages[${i}].path names a site in a run that fetched nothing`;
        if (notAsRecorded(bundle.pages[i].path))
          return `MALFORMED: pages[${i}].path is no name a run records for a file`;
      }
  }
  // §5 "Pages": a URL run's inputs are snapshots of its pages, on the bound
  // host; a run that fetched nothing lists files, none naming a site.
  if (bundle.inputs !== undefined && bundle.inputs !== null) {
    if (!Array.isArray(bundle.inputs)) return "MALFORMED: inputs must be an array";
    for (let i = 0; i < bundle.inputs.length; i++) {
      const entry = bundle.inputs[i];
      if (!isObject(entry)) return `MALFORMED: inputs[${i}] is not an object`;
      const snapshot = entry.kind === "url-snapshot";
      if (!(namesSite(entry.path) || snapshot)) {              // a file
        if (notAsRecorded(entry.path))
          return `MALFORMED: inputs[${i}].path is no name a run records for a file`;
        continue;
      }
      if (!urlRun) return `MALFORMED: inputs[${i}] names a site in a run that fetched nothing`;
      if (!snapshot || urlHost(entry.path) !== fetchedHost)
        return `MALFORMED: inputs[${i}] is not a snapshot of a page on the bound host`;
    }
  }
  // §5 "Pages": the judged track's pages are pages of the bundle.
  if (bundle.judged !== undefined && bundle.judged !== null) {
    if (!isObject(bundle.judged)) return "MALFORMED: judged must be an object or null";
    const listed = bundle.judged.pages;
    if (listed !== undefined && listed !== null) {
      if (!Array.isArray(listed)) return "MALFORMED: judged.pages must be an array";
      const names = new Set(Array.isArray(bundle.pages)
        ? bundle.pages.filter((p) => isObject(p) && typeof p.path === "string")
            .map((p) => p.path) : []);
      for (let i = 0; i < listed.length; i++)
        if (!isObject(listed[i]) || typeof listed[i].path !== "string" ||
            !names.has(listed[i].path))
          return `MALFORMED: judged.pages[${i}] is not one of the bundle's pages`;
    }
  }
  const sig = bundle.signature;
  if (sig !== undefined && sig !== null && !isObject(sig)) return "MALFORMED: signature is not an object";
  return null;
}

// §6 steps 1-6, on a bundle whose structure checkRecords accepted.
function verifySignature(bundle, pubHex) {
  const sig = bundle.signature;
  const fetchedHost = isObject(bundle.fetch) ? urlHost(bundle.fetch.final_url) : null;
  if (sig === undefined || sig === null) return "INVALID: unsigned";
  if (!isObject(sig)) return "MALFORMED: signature is not an object";
  // §5 "The signature block": exactly five members, alg and context fixed.
  for (const k of Object.keys(sig))
    if (!SIGNATURE_MEMBERS.includes(k)) return `MALFORMED: signature has a member the format does not define (${k})`;
  for (const k of SIGNATURE_MEMBERS)
    if (!Object.hasOwn(sig, k)) return `MALFORMED: signature lacks ${k}`;
  if (sig.alg !== "Ed25519") return "MALFORMED: signature.alg is not Ed25519";
  if (sig.context !== STATEMENT_FORMAT) return "MALFORMED: signature.context is not " + STATEMENT_FORMAT;
  if (typeof sig.key_id !== "string" || typeof sig.signature_b64 !== "string")
    return "MALFORMED: signature.key_id or signature.signature_b64 is not a string";
  const st = sig.statement;
  if (!isObject(st)) return "MALFORMED: statement is not an object";
  // §5: the statement is closed too.
  for (const k of Object.keys(st))
    if (!STATEMENT_FIELDS.includes(k)) return `MALFORMED: statement has a member the format does not define (${k})`;
  for (const f of STATEMENT_FIELDS)
    if (st[f] !== undefined && st[f] !== null && typeof st[f] !== "string")
      return `MALFORMED: statement field ${f} is not a string`;
  // 1. Structure.
  if (st.statement_format !== STATEMENT_FORMAT) return "INVALID: statement_format is not " + STATEMENT_FORMAT;
  // 2. Key.
  const kid = keyId(pubHex);
  if (sig.key_id !== kid || st.key_id !== kid) return "INVALID: key_id mismatch";
  // 3. Signature: canonical Base64, R not a small-order point, S below L.
  const raw = Buffer.from(sig.signature_b64, "base64");
  if (raw.length !== 64 || raw.toString("base64") !== sig.signature_b64)
    return "INVALID: signature_b64 is not 64 bytes in canonical Base64";
  if (weakPoint(raw.subarray(0, 32))) return "INVALID: R is a point of small order, or not canonical";
  if (leInt(raw.subarray(32)) >= L) return "INVALID: S is not reduced";
  const message = Buffer.concat([context(STATEMENT_FORMAT), sha256(canonical(st))]);
  let ok = false;
  try { ok = verify(null, message, publicKey(pubHex), raw); } catch { ok = false; }
  if (!ok) return "INVALID: signature invalid";
  // 4. Digest.
  const body = Object.fromEntries(Object.entries(bundle).filter(([k]) => k !== "signature"));
  if (st.bundle_digest_sha256 !== sha256(canonical(body)).toString("hex")) return "INVALID: digest mismatch";
  // 5. Binding.
  const pack = bundle.pack || {};
  const own = {
    bundle_format: bundle.bundle_format ?? null, domain: bundle.domain ?? null,
    host: fetchedHost, pack: pack.name ?? null, pack_version: pack.version ?? null,
    pack_sha256: pack.manifest_sha256 ?? null,
    rulebook_version: bundle.rulebook_version ?? null,
    rulebook_sha256: bundle.rulebook_sha256 ?? null,
  };
  for (const f of BOUND_FIELDS) if ((st[f] ?? null) !== own[f]) return "INVALID: binding mismatch on " + f;
  // 6. Host.
  if (hostScope(st.host ?? null, st.domain ?? null) === "unrelated")
    return "INVALID: the fetched host is not the stated domain or a subdomain of it";
  return "VALID";
}

function verifyText(textOrBytes, pubHex) {
  let bundle;
  try {
    bundle = parseStrict(typeof textOrBytes === "string" ? textOrBytes : decodeStrict(textOrBytes));
  } catch (e) {
    if (e instanceof Malformed) return "MALFORMED: " + e.message;
    throw e;
  }
  return verifyBundle(bundle, pubHex);
}

// ---------------------------------------------------------------- run

const [vectorsPath, casesPath] = process.argv.slice(2);
const V = JSON.parse(readFileSync(vectorsPath, "utf8"));
const C = casesPath ? JSON.parse(readFileSync(casesPath, "utf8")) : { bundles: [], roundtrip: [] };
const out = {};

out.canonical_mismatches = V.canonicalization
  .filter((c) => canonical(c.input) !== c.canonical_utf8)
  .map((c) => ({ description: c.description, got: canonical(c.input), want: c.canonical_utf8 }));

// Every input the vectors reject, and every malformed file text, must be
// malformed here too.
function isMalformed(text) {
  try { return !isObject(parseStrict(text)); } catch (e) {
    if (e instanceof Malformed) return true;
    throw e;
  }
}
out.rejected_accepted = V.rejected.filter((c) => c.input_json && !isMalformed(c.input_json))
  .map((c) => c.description);
out.malformed_accepted = V.malformed_texts.filter((c) => !isMalformed(c.text))
  .map((c) => c.description);
out.malformed_bytes_accepted = V.malformed_bytes.filter((c) => {
  try { return !isMalformed(decodeStrict(Buffer.from(c.hex, "hex"))); } catch (e) {
    if (e instanceof Malformed) return false;
    throw e;
  }
}).map((c) => c.description);
out.well_formed_mismatches = V.well_formed_spellings
  .filter((c) => canonical(parseStrict(c.text)) !== c.canonical_utf8)
  .map((c) => c.text);
out.host_relation_mismatches = V.host_relations
  .filter((c) => hostScope(c.host, c.domain) !== c.relation)
  .map((c) => ({ ...c, got: hostScope(c.host, c.domain) }));
out.url_host_mismatches = V.url_hosts
  .filter((c) => urlHost(c.final_url) !== c.host)
  .map((c) => ({ ...c, got: urlHost(c.final_url) }));
out.page_record_mismatches = (V.page_records || [])
  .map((c) => {
    // Whole bundles (§9.6): the body first, as verifyBundle checks it.
    const got = (checkBody(c.bundle) || checkRecords(c.bundle)) ? "malformed" : "fine";
    return { ...c, got };
  })
  .filter((c) => c.got !== c.result);

const bv = V.bundle;
// §9.8: a domain in another spelling than §5 gives is malformed.
out.domain_spelling_mismatches = (V.domain_spellings || [])
  .map((c) => ({ ...c, got: checkBody({ ...bv.unsigned_bundle, domain: c.domain }) ? "malformed" : "fine" }))
  .filter((c) => c.got !== c.result);
const body = Object.fromEntries(Object.entries(bv.unsigned_bundle).filter(([k]) => k !== "signature"));
out.bundle_vector_body = canonical(body) === bv.canonical_body_utf8;
out.bundle_vector_digest = sha256(canonical(body)).toString("hex") === bv.bundle_digest_sha256;
out.bundle_vector = verifyBundle({ ...bv.unsigned_bundle, signature: bv.signature_block },
                                 V.vector_key.public_hex);

// §9.7: signature blocks over the bundle vector's body.
out.signature_block_mismatches = (V.signature_blocks || [])
  .map((c) => {
    const r = verifyBundle({ ...bv.unsigned_bundle, signature: c.signature_block },
                           V.vector_key.public_hex);
    const got = r === "VALID" ? "valid" : r.startsWith("MALFORMED") ? "malformed" : "invalid";
    return { description: c.description, result: c.result, got, said: r };
  })
  .filter((c) => c.got !== c.result);

// §6 step 3 (§9.2): signatures on which the equations RFC 8032 allows disagree.
out.small_order_mismatches = (V.small_order_parts || [])
  .map((c) => {
    const r = verifyBundle({ ...bv.unsigned_bundle, signature: c.signature_block },
                           c.public_hex);
    const got = r === "VALID" ? "valid" : r.startsWith("MALFORMED") ? "malformed" : "invalid";
    return { description: c.description, result: c.result, got, said: r };
  })
  .filter((c) => c.got !== c.result);

const pv = V.pack;
const packMessage = Buffer.concat([context(PACK_FORMAT), sha256(canonical(pv.manifest_body))]);
out.pack_vector = verify(null, packMessage, publicKey(V.vector_key.public_hex),
                         Buffer.from(pv.signature_block.signature_b64, "base64")) ? "VALID" : "INVALID";

// Every bundle case twice: as §6 requires, and the naive way (JSON.parse,
// no checks), so the tests can show each attack would have worked on a
// verifier that skipped the parsing rules.
out.bundles = {};
for (const b of C.bundles) {
  // A file given as bytes is decoded strictly by the §6 verifier and
  // leniently by the naive one (Buffer#toString turns bad bytes into U+FFFD).
  const bytes = b.bytes_b64 !== undefined ? Buffer.from(b.bytes_b64, "base64") : null;
  let naive;
  try {
    naive = verifyBundle(JSON.parse(bytes ? bytes.toString("utf8") : b.text), b.public_hex);
  } catch (e) { naive = "ERROR: " + e.message; }
  out.bundles[b.name] = { strict: verifyText(bytes || b.text, b.public_hex), naive };
}

out.roundtrip_checked = C.roundtrip.length;
out.roundtrip_mismatches = C.roundtrip
  .filter((t) => canonical(parseStrict(t)) !== t)
  .slice(0, 5)
  .map((t) => ({ python: t, javascript: canonical(JSON.parse(t)) }));

console.log(JSON.stringify(out));
