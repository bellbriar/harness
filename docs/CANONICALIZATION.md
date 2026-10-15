# Canonicalization and signing — `bellbriar-evidence/1`, `bellbriar-signature/1`, `bellbriar-pack/1`

*Normative for the harness from version 1.0.0rc1 on. Written so that a verifier
in any language can be built from this document alone and checked against
the vectors in §9. `tests/test_canonicalization.py` re-derives every value
below from `docs/canonicalization-vectors.json` and fails if this document
and the implementation disagree.*

## 1. Scope

Three artifact types are signed:

| Artifact | Format string | What is signed |
|---|---|---|
| Evidence bundle | `bellbriar-evidence/1` | Nothing directly — its **digest** is bound inside a statement |
| Signature statement | `bellbriar-signature/1` | The statement object (§5) |
| Pack manifest | `bellbriar-pack/1` | The manifest body (§7) |

All three use one construction (§4): `Ed25519( context ‖ SHA-256(canonical(object)) )`.

Format strings are the version. `bellbriar-evidence/1` and
`bellbriar-signature/1` were published with harness 1.0.0rc1 (its date is
in CHANGELOG.md): since then, any change to the canonical form, the
digest input, the bound fields, or the signed message requires a new
format string and a new context. There is no minor-version negotiation.

Before that they were amended in place (PREPUBLISH.md item 12), as no
bundle had been issued outside development, so a bundle signed under an
earlier draft may not verify. One amendment bound `host` (§5): a
statement signed before it carries no `host`, so it does not cover a URL
run, and the verifier says so (§6 step 5). Another recorded what a URL's
capture left out (`redacted`, now in each page's capture record,
`pages[].fetch`; §5); no verification step reads it. A later one made
`fetch` the run's record, which counts the pages, and gave each page its
own capture record (`pages[].fetch`), which must name the bound host; a
URL run's page is named by its final URL, and a snapshot input names a
page on the bound host (§5 "Pages", §6). It also gave each finding a
locator (`selector`), which no verification step reads. The amendments
made for 1.0 bound the rulebook's digest (`rulebook_sha256`, §5) beside
its version, closed the signature block to its five members (§5), and
made the harness issue only `self-signed` signatures (§5.1); a statement
signed before the first carries no `rulebook_sha256`, so it does not
cover a bundle that records one. They also closed the body to the
members §5 lists, checked the key and the signature before what the
statement says is compared with the bundle (§6), and refused public keys
and signatures built on points of small order (§6, §8). The last bound
the pack's digest (`pack_sha256`, §5) beside its name and version, named
the equation a signature is checked by (§6 step 3), and made malformed a
`domain` in another spelling than §5 gives and a page with no `fetch`
member (§6); a statement signed before the first carries no
`pack_sha256`, so it does not cover a bundle that records a pack.

`bellbriar-pack/1` is a draft, which that publication did not freeze:
1.0 ships no pack and no pack key, and its verification (§7) does not yet
do what §6 does for a bundle (strict parsing, canonical Base64, the
small-order checks, a closed signature block). A release that ships packs
brings §7 up to §6 first. A bundle that records a pack records the
digest of its manifest body (§7), which a statement binds (§5).

## 2. Canonical JSON

`canonical(object)` is the UTF-8 encoding of the object serialized as JSON
under these rules. Two implementations are conformant only if they produce
identical bytes for every object the harness can emit.

1. **Object keys are sorted by Unicode code point**, recursively. Keys
   **must** be ASCII strings; the producer rejects anything else, which
   makes code-point order and byte order coincide. (JavaScript's default
   `Array.prototype.sort` compares UTF-16 code units, which diverges from
   code-point order only for non-BMP characters — the ASCII constraint
   exists so that this can never matter.)
2. **No whitespace** anywhere outside strings: separators are `,` and `:`.
3. **Strings** are emitted with only the mandatory RFC 8259 escapes — `"`,
   `\`, and U+0000–U+001F. Control characters use the short forms `\n`,
   `\r`, `\t`, `\b`, `\f` where they exist and `\u00XX` (lowercase hex)
   otherwise. Everything else, including all non-ASCII, is emitted **raw
   as UTF-8**, never as `\uXXXX`. `/` is not escaped. A string must be
   valid Unicode: a lone surrogate, which JSON can spell (`\ud800`) but
   UTF-8 cannot encode, is rejected.
4. **Numbers.** A number is an integer or a decimal. Nothing else is
   canonical.
   - **Integers**, including integer-valued floating-point values, are
     emitted as plain integers with no fractional part or exponent:
     `1.0 → 1`, `-0.0 → 0`. This is the rule JavaScript's
     `JSON.stringify` already follows; Python's `json` does not, so the
     producer normalizes before serializing. The magnitude must not exceed
     2⁵³ (9007199254740992), the range in which an IEEE-754 double holds
     every integer exactly. Above it the two languages print different
     digits for the same double: `2.0**60` is `1152921504606846976` in
     Python and `1152921504606847000` in JavaScript.
   - **Decimals** (numbers that are not integers) must have magnitude at
     least 0.0001. Each is emitted as the shortest string that round-trips
     to the same double (Python `repr`, JavaScript `Number#toString`, RFC
     8785). In this range both languages print plain decimal notation,
     digit for digit. Below it Python switches to an exponent and
     JavaScript does not: `0.00005` is `5e-05` in Python and `0.00005` in
     JavaScript. A formatter that switches to exponent notation sooner —
     Java's `Double.toString` does below 0.001 and from 10⁷ up — is not
     conformant as it stands; use an RFC 8785 library there (below).
   - `NaN` and `±Infinity` are rejected.

   The producer **rejects** a number outside these rules rather than emit
   bytes another verifier would not reproduce. Before the digest is taken
   it also rounds every decimal to at most four places (`build_bundle`),
   so the bundles it writes never come near the 0.0001 floor. Verifiers
   accept any decimal in range, rounded or not.
5. `true`, `false`, `null` as in JSON. Empty objects and arrays are `{}`
   and `[]`.

For every object these rules admit, the canonical form is byte-identical
to RFC 8785 (JSON Canonicalization Scheme) output — equivalently,
JavaScript's `JSON.stringify` with object keys sorted — so an RFC 8785
library can produce it. Producing it is not verifying, though. A stock
JSON parser followed by `JSON.stringify` accepts files that §6 requires a
verifier to refuse: `JSON.parse` reads `1e999` as Infinity, and
`JSON.stringify` writes Infinity as `null`, so that pair would verify a
file showing `1e999` where `null` was signed. `tests/test_canonicalization.py`
checks both halves against an independent JavaScript verifier whenever
Node.js 22 or later is available.

Reference implementation: `bundle.canonical_bytes`, which is
`json.dumps(normalize(obj), sort_keys=True, separators=(",", ":"),
ensure_ascii=False, allow_nan=False).encode("utf-8")` with `normalize`
enforcing rules 1, 3 and 4.

## 3. Digests

`SHA-256` over `canonical(x)`, rendered as 64 lowercase hex characters.

- **Bundle digest** — `x` is the bundle with the **top-level** key
  `signature` removed. Nothing else is removed or altered; nested keys
  named `signature` (none exist today) would be included.
- **Statement digest** — `x` is the whole statement object (§5).
- **Pack body digest** — `x` is the manifest with the top-level key
  `signature` removed (§7).

The bundle digest excludes `signature`, and nothing in the signature
block but its statement is signed, so anyone can change the rest of the
block without breaking the signature. The block is therefore **closed**:
it has exactly the members §5 lists, with the values §5 fixes, and a
verifier treats anything else as malformed (§6) rather than ignoring it,
because a member a reader takes for part of the evidence (`"verified_by":
"Bellbriar"`) would be covered by nothing. Like every part of the file the
block must satisfy §2 and the parsing rules of §6. The bundle body is
closed too, at its top level (§5 "The body"): a member §5 does not list
makes the file malformed, and any new or changed body member is a new
format. The records inside it (`tool`, `site`, `pages` and the rest) are
not closed: a verifier checks in them only what §6 lists, and anything
else they hold, like every result, is what the bundle's maker wrote. A
verifier says how many members of them its own release does not write,
and where, and whether the coverage note and the layer records are its
release's (§6): it never refuses a bundle for them, so a later release
can add a member without a new format.

## 4. Signing contexts and the signed message

A signature is never made over a bare digest. The message is

    message = context ‖ SHA-256(canonical(object))

where `context` is the artifact's format string followed by a single NUL
byte, and `‖` is byte concatenation:

| Format | Context bytes (hex) |
|---|---|
| `bellbriar-signature/1` | `62656c6c62726961722d7369676e61747572652f3100` |
| `bellbriar-pack/1` | `62656c6c62726961722d7061636b2f3100` |

The verifier fixes the context from the kind of artifact it is checking.
It never reads the context from the signed object or from the signature
block, because whoever presents a signature writes both. A bundle
verifier uses `bellbriar-signature/1` and rejects any statement whose
`statement_format` is something else (§6 step 1); a pack verifier uses
`bellbriar-pack/1`. That is what makes the separation hold: a signature
made over a pack manifest can never be presented as a signature over a
statement, or the reverse, even under a shared key, because the signed
messages differ in their first bytes and each verifier accepts only its
own.

Signers keep the same discipline from the other side. The statement
signer signs only an object whose `statement_format` is
`bellbriar-signature/1`. The pack signer refuses a body that carries
statement fields (`statement_format`, `bundle_digest_sha256`,
`attestation_class`) or that lacks a manifest's string `name`, string
`version` and `files` object.

Signature algorithm: **Ed25519** (RFC 8032, pure, no pre-hash). Signatures
are deterministic, so the vectors in §9 are byte-exact. Encoding: the 64
signature bytes, standard Base64 with padding, in `signature_b64`. The
encoding must be canonical — re-encoding the 64 bytes gives the same
string — so that no two verifiers disagree about a string one of them
decodes leniently.

## 5. The signature statement (`bellbriar-signature/1`)

The object that is actually signed for a bundle. It has the members
below and no other, and each value is a string or `null`; a member may be
absent, which reads as `null`. A member the table does not list makes the
file malformed (§6): it would be signed, and could be read as a claim no
verifier checks.

| Field | Value |
|---|---|
| `statement_format` | `"bellbriar-signature/1"` |
| `bundle_digest_sha256` | The bundle digest (§3) |
| `attestation_class` | `"self-signed"`, `"attested-submission"`, or `"attested-execution"` (§5.1) |
| `key_id` | Identifier of the signing key (§8) |
| `signer` | Free-text signer name |
| `signed_at` | RFC 3339 timestamp, UTC, seconds precision |
| `bundle_format` | copied from the bundle |
| `domain` | copied from the bundle (`null` if unstated) |
| `host` | the host read from `bundle.fetch.final_url` (below): where a URL run actually fetched its pages, after redirects. `null` when `fetch` is `null` (a file run, its files rendered or not) |
| `pack` | `bundle.pack.name` (`null` if unpinned) |
| `pack_version` | `bundle.pack.version` (`null` if unpinned) |
| `pack_sha256` | `bundle.pack.manifest_sha256`, the digest of the pack's manifest body (§7; `null` if unpinned) |
| `rulebook_version` | copied from the bundle |
| `rulebook_sha256` | copied from the bundle: SHA-256 (§3) of the rulebook the run applied, in canonical form (§2), so that a rulebook's spacing, key order and line endings do not change it; `null` if unrecorded |

The last eight are the **bound fields**. A version names a release of a
rulebook or a pack; a digest names its content, which a custom rulebook
(one that demotes every Tier-1 rule, say) or an edited pack changes while
keeping the version. The signer never sees the bundle body; the client states these values when requesting a signature, and the
signer records what it *authorized* inside the signed statement. At
verification each is compared for strict equality with the bundle's own
value (§6 step 5). This is what stops a subscriber obtaining a signature
for one domain or pack version and attaching it to a bundle claiming
another — the signature would be genuine and the check would still fail.

`domain` and `host` are host names in one spelling, the one a browser
writes in a URL: lowercase ASCII, internationalized labels in their IDNA
A-label form (`bücher.de` is `xn--bcher-kva.de`), no trailing dot; IPv4
addresses as four decimal numbers and IPv6 addresses in the WHATWG URL
form without brackets (`::1`, `::ffff:7f00:1`). A name made only of digits
and dots, or one containing a colon, is an address. The single spelling
keeps look-alike Unicode names from passing for each other. A bundle
whose `domain` is a string in another spelling is malformed (§6): one
that is empty, holds a character other than lowercase ASCII letters,
digits, `-`, `_` and `.`, has an empty label (a trailing dot is one), or
ends in a label a browser reads as a number (digits only, or `0x`
followed by hex digits or by nothing), unless it is an address written as
above. A verifier checks the
spelling only: it does not decode an `xn--` label. A harness
refuses a name with an `xn--` label whose Punycode does not decode, does
not re-encode to the same label, or decodes to plain ASCII, to text that
is not in NFC, or to a control character, surrogate, private-use code
point, noncharacter or space: a browser refuses such a name. The check is
deliberately partial (fixed code point ranges, so its answer does not
depend on a Unicode version) and does not refuse every name a browser
does. `host` is
bound beside `domain` so that a run against `staging.example.com` can
never read as `example.com` itself (§6 step 6).

**Reading the host.** `bundle.fetch.final_url` is the URL the page was
captured from. A verifier reads the host from it in plain string steps,
so that every verifier reads the same one, and strictly enough that no
URL parser reads a different one:

1. The value is printable ASCII (`!` to `~`: no spaces) and begins with
   `http://` or `https://`, in any case.
2. The authority runs from there to the first `/`, `?` or `#`. It
   contains no `\` (browsers end the authority there; other parsers do
   not) and no `@`: the producer records no user name, and a person reads
   `https://bank.example@site.example/` as the bank.
3. The host is the authority up to the `:` that starts a port, and is
   made of ASCII letters, digits, `-`, `_` and `.`. When the authority
   begins with `[`, the host is the text inside the brackets instead,
   made of hex digits, `:` and `.`. A port is digits only, and may be
   empty (`https://example.com:/`), as URL parsers read it.
4. ASCII letters are lowercased and one trailing dot is removed. What
   remains must not be empty.

The producer writes `final_url` the way a browser reports it — with the
host in the spelling above, apart from a trailing dot, which step 4
removes — and records the host again as `fetch.host` for readers. It
writes no credentials into any URL it records: no user name or password,
and every query or fragment value, and every path parameter's value (what
follows `;` in a segment: `/shop;jsessionid=…`), replaced with
`REDACTED` unless the operator named that parameter, because a signed
bundle cannot be redacted later without breaking its signature. A fragment that is a
client route (`#/about`, `#!/about`) keeps its path, as the URL keeps
its own, and the query after it (`#/search?q=…`) is redacted as a query
is; a route holding `=`, `&`, `;`, `#` or `?` in its path, spelled out
or percent-encoded (once or more: the path is decoded until no escape is
left, eight times at most, and one still changing is not a route), is
redacted as parameters, which is how a token handed back to a hash-routed
app looks (`#/access_token=…`), and so is one holding a space, a control
character or a character outside ASCII, which a browser reports
percent-encoded: a recorded URL stays printable ASCII. A parameter with
no `=` is all value, and so is one with nothing but `=` after a name that
looks like a credential (eight characters or more, not a plain lowercase
word: a padded Base64 token, `?<token>=`); both are replaced whole.
Each page's capture record lists what was left out of its URLs as
`pages[].fetch.redacted` (`"userinfo"`, `"path"`, `"query"`,
`"fragment"`, and `"http-credentials"` when credentials were offered
outside the URL).
Neither change touches the host that steps 1–4 read. A
bundle whose `final_url` gives no host, or whose `fetch.host` is present
and is not that host, is malformed (§6): it would show a reader one host
and bind another. §9.5 lists cases.

**The body.** A bundle is an object with the members below and no
other, each of the type listed. A required member must be present; the
others may be absent, which reads as `null` (bundles made before
`rulebook_sha256` and `baseline` were added lack them).

| Member | Type | Required |
|---|---|---|
| `bundle_format` | the string `"bellbriar-evidence/1"` | yes |
| `created_at` | string | yes |
| `tool` | object | yes |
| `rulebook_version` | string | yes |
| `rulebook_sha256` | string or `null` | no |
| `domain` | string or `null` | yes |
| `pack` | object or `null` | yes |
| `inputs` | array | yes |
| `fetch` | object or `null` | yes |
| `layers` | array | yes |
| `coverage_note` | string | yes |
| `site` | object | yes |
| `pages` | array | yes |
| `judged` | object or `null` | yes |
| `baseline` | object or `null` | no |
| `attestation` | string | yes |
| `signature` | object or `null` | no |

The signature covers every member of the body, so a member the table does
not list would be signed and could be read as a claim
(`"certification": "WCAG 2.1 AA conformant"`) that no verifier checks. A
file with such a member, without a required one, with a member of another
type, or with another `bundle_format`, is malformed (§6): a verifier
cannot read a format it does not know. This closes the top level only.
Inside `tool`, `site`, `pages`, `layers` and the other records a verifier
checks only what §6 lists, so a member there that this format does not
describe (`"site": {"certification": …}`), like the `coverage_note` and
every result, is signed as what the bundle's maker wrote and is checked
by no one; a verifier says where it is (§6).

**Pages.** `fetch` is the run's record of what it fetched: `final_url` is
the final URL of the run's first page fetched, `host` that host again,
`pages` how many pages the bundle shows, and `list` how they were listed.
Each page's own capture record is that page's `fetch`, and it names its
own `final_url`. A run binds one host, so in a URL run (`fetch` is an
object):

- `fetch.pages` is the number of pages in `pages`;
- every page has a capture record, and its `path` is that record's
  `final_url`: a page is named by the URL it was fetched from;
- every page's `fetch.final_url` gives the host `fetch.final_url` gives
  (steps 1–4), and its `fetch.host`, when present, is that host.

A run that fetched nothing binds no host (`fetch` is null), and names its
pages by their files: no page's `path` names a site. A path names a site
when, after any characters of the Unicode categories Cc, Cf, Zs, Zl and
Zp, it begins with `http:` or `https:`, in any case, and then `/` or `\`:
a person reads ` https://x`, a zero-width space before `https://x`, or
`https:/x` as a URL too, and a browser corrects the last. A producer
writes `./` before a file's name whose first part holds a colon or any
character outside ASCII (a folder named `https:`, or one whose name only
looks like it), so that no reader takes it for a site, and a file's name
that holds such a first part without `./` before it is no name a run
records (a page's `path` here, an entry of `inputs` that is a file):
U+3164 or U+2800 before `https://`, a full-width colon or a Cyrillic
letter in `https` read as a site to a person, and no list of such
characters is whole. Either no page has
a capture record
(files read as they are), or every page has one (a build the harness
rendered from its own loopback server, `--render`), and then each page's
`fetch.final_url` gives a host that is this machine — `localhost` or a
name ending in `.localhost`, `::1`, or `127.` followed by three numbers
from 0 to 255 written without leading zeros.

`inputs` is an array of objects. An entry that names a site (as a page's
`path` does, above), or whose
`kind` is `url-snapshot`, records a page's snapshot: its `kind` is
`url-snapshot` and its `path` gives the host the statement binds, so a run
that binds none has no such entry. Other entries name files as the run
recorded them, `./` first where a page's name would have it.

`judged`, the judged track, is an object or null, and its `pages`, when
present and not null, is an array of objects whose `path` is the `path`
of one of the bundle's pages.

A `judged.pages` that is null counts as absent and is not checked;
`pages` and `inputs` are arrays in every bundle (above), so null there is
malformed. Anything else these paragraphs rule out is malformed too (§6):
a page or an input would show a reader a host the statement does not
bind, or a page the run did not count. §9.6 lists cases.

The statement is carried in the bundle as:

```json
"signature": {
  "alg": "Ed25519",
  "context": "bellbriar-signature/1",
  "key_id": "<key_id>",
  "statement": { … },
  "signature_b64": "<base64>"
}
```

The block has exactly these five members, all required: `alg` is the
string `"Ed25519"`, `context` the string `"bellbriar-signature/1"`,
`key_id` and `signature_b64` are strings, and `statement` is an object.
Any other member — even one whose value is `null` — or another value of
`alg` or `context`, makes the file malformed (§6). `alg` and `context`
are duplicates of what this document fixes (§4), which a verifier uses
whatever the block says; a block that says otherwise would mislead a
reader, so it is refused. `statement.statement_format` must name that
same context. A new member (a transparency-log proof, say) is a new
format (§10). §9.7 lists cases.

### 5.1 Attestation classes

| Class | Who checked what |
|---|---|
| `self-signed` | The holder of a key signed the client's own bound values. **No one else checked anything.** A valid signature shows who held the key and that the bundle has not changed since; not that its results are correct, or were not edited before signing. The only class this release issues. |
| `attested-submission` | Reserved for a signing service that checks a subscription covers the stated domain, any fetched host and the pack version before it signs. **Nothing issues this class in this release.** |
| `attested-execution` | Reserved for a runner that fetches the inputs and executes the evaluation itself. **Nothing issues this class in this release.** |

A verifier reports a reserved class, or any other value, as the signer's
claim, and says that it shows no more than a self-signed signature: no
service exists that could have checked what the class names.

The bundle's `attestation` field restates these limits in prose and is
part of the signed body. A verifier does not rely on it: whoever made the
bundle wrote it, so a verifier states what a valid signature shows in its
own words, and says whether the text is the one its own harness writes
(§6).

## 6. Verification

Input: a bundle file and one Ed25519 public key (32 bytes, hex). Output:
`VALID` or `INVALID` with a reason — or neither, when the file is
malformed (below) or the key is not one a signature means anything under
(§8): then nothing can be concluded, and the verifier says it could not
verify the bundle (`bellbriar-evidence verify` exits 2).

**Parsing.** Files that parse to the same value have the same digest, so
a verifier must refuse any file whose bytes can be read as something
other than the value it verifies. The file is **malformed** when:

- its bytes are not strict UTF-8, or it begins with a byte-order mark. A
  lenient decoder turns a stray byte into U+FFFD, and U+FFFD is a
  character the producer writes, so the lenient reading can verify bytes
  that were never signed;
- a member name repeats within one object: parsers disagree about which
  value wins, and a reader sees the first;
- a number literal, read as an exact decimal, differs from the §2 text of
  the double it parses to. `9007199254740993`, `1e999`,
  `0.67570000000000001` and `1e-400` fail; other spellings of the same
  number (`1.0`, `1e2`, `-0.0`, `0.67570`, `0e99999999999999999999`)
  are fine. A file need not be canonical, only unambiguous. Compare
  digits and exponents exactly: a decimal type with a bounded exponent
  cannot hold every literal;
- objects and arrays nest deeper than 32 levels, counting the bundle
  itself as one. Bundles the harness writes reach about 11. Without a
  fixed limit each verifier stops at its own recursion depth, and two
  verifiers disagree about the same file;
- `NaN` or `Infinity` appears, or anything anywhere in the parsed value —
  the signature block included — breaks §2 (a number out of range, a lone
  surrogate, a non-ASCII key);
- a part of the structure has the wrong type: the file is not a JSON
  object, `pack` or `fetch` is neither an object nor `null`, `signature` is
  present and neither an object nor `null` (a `null` or absent
  `signature` is an unsigned bundle: INVALID, not malformed), or a
  statement field listed in §5 is neither a string nor `null`;
- `signature` is present and is not a block of exactly the five members
  §5 lists, with `alg` `"Ed25519"`, `context` `"bellbriar-signature/1"`,
  string `key_id` and `signature_b64`, and an object `statement` with no
  member §5 does not list. The pre-0.3.0 form, a bare `digest_sha256`
  with no statement, is one such block: a bare digest binds nothing to the
  domain or pack, and it cannot be verified;
- the body is not as §5 "The body" lists: a member it does not list, a
  required member missing, a member of another type, a
  `bundle_format` other than `"bellbriar-evidence/1"`, or a `domain` that
  is a string in another spelling than §5 gives;
- `fetch` is an object and its `final_url` gives no host by the steps in
  §5, or its `host` is present and is not that host;
- `pages` is not an array of objects, or a page has no `fetch` member or
  one that is neither an object nor `null`; or a page's `fetch.final_url`
  gives no host, its `fetch.host` is present and is not that host, or that
  host is not the one `fetch.final_url` gives (a URL run) or is not this
  machine (a run where `fetch` is null); or, in a URL run, `fetch.pages`
  is not the number of pages, a page has no capture record, or its `path`
  is not its `fetch.final_url`; or, where `fetch` is null, some pages have
  a capture record and others do not, or a page's `path` names a site, or
  is no name a run records for a file, as §5 "Pages" says;
- `inputs` is not an array of objects, or an entry
  that names a site or whose `kind` is `url-snapshot` is not a
  `url-snapshot` whose `path` gives the host the statement binds, or an
  entry that is a file has a `path` no run records for a file;
  `judged` is neither an object nor null, or a page it lists is not one of
  the bundle's pages (§5 "Pages").

A verifier checks all of these before reaching any verdict, so a file
broken in two ways gets the same answer from every verifier. The vectors
in §9.1 list malformed files and bytes. Reference: `bundle.read_bundle`
and `bundle.load_bundle` for what only the bytes can show, and
`bundle.verify_bundle` for the rest.

Then these steps, in order; the first failure ends verification. The
key and the signature come before anything the statement says is compared
with the bundle, so a reason never attributes a statement to the key's
holder before the signature shows that the holder signed it:

1. **Structure.** `signature` is present (an unsigned bundle is
   rejected), and its statement's `statement_format` is exactly
   `bellbriar-signature/1`. Any other value, `bellbriar-pack/1` included,
   is rejected: the verifier chooses the context, not the statement (§4).
2. **Key.** `key_id_for(public_key)` (§8) must equal both
   `signature.key_id` and `statement.key_id`.
3. **Signature.** Verify `signature_b64` over
   `context ‖ SHA-256(canonical(statement))` under the public key, where
   `context` is the `bellbriar-signature/1` context (§4). A signature
   whose first 32 bytes (R) encode a point of small order, or encode y at
   or above the field prime (§8), or whose last 32 bytes (S), read as a
   little-endian integer, are not less than the group order
   L = 2^252 + 27742317777372353535851937790883648493, is rejected: no
   signer writes one, and the first is what a signature made without a
   private key looks like. Otherwise the signature is valid when
   [S]B = R + [k]A, where R is the point its first 32 bytes encode (RFC
   8032 §5.1.3; bytes that encode no point fail), A the public key's
   point, B the base point, and k the SHA-512 digest of R's 32 bytes, the
   key's 32 bytes and the signed message, one after the other, read as a
   little-endian integer and reduced modulo L. RFC 8032 §5.1.7 states the
   check as [8][S]B = [8]R + [8][k]A and allows this one instead. The two
   disagree when R or the key has a part of small order, and so does
   either one with k left unreduced: a verifier of this format checks
   [S]B = R + [k]A with k reduced, as OpenSSL does (the reference and
   `tests/js/canonical_check.mjs` verify through it), so that verifiers
   give a signature one answer. §9.2 lists signatures on which they
   disagree.
4. **Digest.** Recompute the bundle digest (§3) and compare with
   `statement.bundle_digest_sha256`. Mismatch: the key's holder signed a
   statement about other contents, so the body was altered after signing,
   or the signature was taken from another bundle.
5. **Binding.** For each bound field (§5), `statement[field]` must strictly
   equal the bundle's own value — same type and same value; `null` equals
   only `null`, and the string `"1"` never equals the number `1`. A field
   the statement lacks counts as `null`, so a statement signed before
   `host` was bound (§1) fails here for every URL run. Mismatch: the key's
   holder signed a statement naming other values, so the signature does
   not cover this bundle's claims.
6. **Host.** When the statement names both a `domain` and a `host`, the
   two must name the same site, or the host must be below it.
   `example.com` and `www.example.com` are one site, either way round
   (`www.` is dropped only when a dot remains, so `www.com` is its own
   site); `staging.example.com` is below it. An address matches only
   itself. Anything else is **rejected**: the statement would claim one
   site while recording another. A host below the site is accepted but
   reported — `verify` says the bundle records the page as fetched from
   `staging.example.com`, a subdomain of `example.com` and not
   `example.com` itself — so no reader can take a staging run for
   production. §9.4 lists cases. A host that is not a public site is
   reported too: `localhost` or a name below it (RFC 6761), or an address
   in the table below — an IPv6 address that carries an IPv4 address
   (IPv4-mapped `::ffff:0:0/96`, NAT64's `64:ff9b::/96`, 6to4's
   `2002::/16`) by that IPv4 address, and a host a browser reads as an
   IPv4 address (`127.1`, `2130706433`) by that address. `verify` names it
   as the table does, and as not a public site, so no reader takes a run
   against a developer machine or an internal network for a public site.
   Neither report changes the verdict. A capture records a class from the
   same table (`address_class`: loopback, private or public) and what
   decided it (`address_basis`, §5). For a host that is an address, that
   is the address itself, which `verify` reads alike. For a name, it is
   the address the client connected to, when it connected to that host
   itself rather than to a proxy: something `verify` cannot check. So
   `verify` reports it as the capture records' word: a name they record
   as resolving to a loopback or private address is named as such, and as
   not a public site.

   The rows are read in order; the first that holds the address decides:

   | Ranges | Class | `verify` calls it |
   |---|---|---|
   | `127.0.0.0/8`, `::1/128` | loopback | a loopback address |
   | `0.0.0.0/32`, `::/128` | loopback | an unspecified address, which connects to this machine |
   | `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `fc00::/7` | private | a private address |
   | `100.64.0.0/10` | private | a shared address (carrier-grade NAT, as Tailscale uses) |
   | `169.254.0.0/16`, `fe80::/10` | private | a link-local address |
   | `fec0::/10` | private | a site-local address |
   | `224.0.0.0/4`, `ff00::/8` | private | a multicast address |
   | `192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`, `2001:db8::/32`, `3fff::/20` | private | a documentation address |
   | `198.18.0.0/15`, `2001:2::/48` | private | a benchmarking address |
   | `240.0.0.0/4` | private | a reserved address |
   | `0.0.0.0/8` | private | a "this network" address |
   | `192.0.0.8/32`, `100:0:0:1::/64` | private | a dummy address |
   | `192.0.0.0/24`, `2001::/23` | private | an IETF protocol address |
   | `192.88.99.0/24` | private | a deprecated 6to4 relay address |
   | `64:ff9b:1::/48` | private | a local-use NAT64 address |
   | `100::/64` | private | a discard-only address |
   | `5f00::/16` | private | a segment routing (SRv6) address |

   Except the addresses inside those blocks that the registries mark as
   globally reachable, which are public: `192.0.0.9/32`, `192.0.0.10/32`,
   `2001:1::1/128`, `2001:1::2/128`, `2001:1::3/128`, `2001:3::/32`,
   `2001:4:112::/48`, `2001:20::/28` and `2001:30::/28`.

   The ranges are the blocks the IANA special-purpose address registries
   (as updated on 2025-10-09) mark as not globally reachable, with
   multicast and the deprecated site-local block; the unspecified
   addresses are loopback, since connecting to one reaches this machine on
   common systems. They are fixed here rather than read from a library
   whose ranges move between releases.
A valid result says what the signature shows in the verifier's own words
(§5.1), never the bundle's: for `self-signed`, that the key's holder
signed this statement and the bundle has not changed since, not that its
results are correct or unedited; for any other class, that it shows no
more than that. It also reports the rulebook: `rulebook_sha256` is
compared with the digest of the rulebook the verifier's own harness
ships, and a bundle whose digest differs is named as using another
rulebook (a custom one, or another release's), whose tiers and rules may
differ; a bundle with no digest is named as identifying its rules by the
version alone. It says whether the bundle's `attestation` text is the one
the verifier's own harness writes, or another (an older release's, or
anyone's), which is the words of whoever made the bundle. It says what
else the bundle holds that its own release does not write (another
release's, or added or edited): how many members of the records inside
the body it does not define, and where (never their names, which are
the maker's words too), a coverage note that is not one its release
writes, and layer records that are not (their status and note, and the
status the note's counts make it), that repeat a layer, or that are of
a layer it does not have, or a list without one of its layers. None of
these reports changes the verdict.

Not checked, by design, and to be evaluated by the reader: `signed_at`
(no expiry semantics exist), and what the `attestation` text says.

Reference: `bundle.verify_bundle`. CLI: `bellbriar-evidence verify
bundle.json --public-key <hex-or-file>`.

## 7. Pack manifests (`bellbriar-pack/1`)

A draft, which the publication of the other two formats did not freeze
(§1). A pack manifest is `pack.json` at the pack root:

```json
{
  "name": "wcag", "version": "1.0.0", "rulebook_min": "0.1.0",
  "files": {"SKILL.md": "<sha256 of file bytes>", …},
  "signature": {"alg": "Ed25519", "context": "bellbriar-pack/1",
                "key_id": "<key_id>", "signature_b64": "<base64>"}
}
```

Signing: `Ed25519( "bellbriar-pack/1\0" ‖ SHA-256(canonical(body)) )`
where `body` is the manifest with `signature` removed. The signer refuses
a body shaped like a statement (§4). The pack key is distinct from any
bundle-signing key; the context, fixed by each verifier, makes the
separation hold even if that discipline ever slipped.

Verification (`pack.verify_signature`), in order: (1) if the manifest is
unsigned or no key was supplied, the result is *unverified*, not invalid
— pinning records `signature_verified: false`; (2) `signature.context`
must equal `"bellbriar-pack/1"` — a signature without it is the earlier
context-less form and is rejected with instructions to re-sign; (3)
`key_id` must match the supplied key; (4) the Ed25519 signature must
verify over the message above. Separately, every file listed in `files`
must exist and hash to its listed value (`pack.verify_files`).

The bundle records a pinned pack as `{name, version, manifest_sha256,
files, signature_verified}`, where `manifest_sha256` is the pack body
digest.

## 8. Keys and key identifiers

Ed25519 keys are handled as raw 32-byte values, hex-encoded (64 lowercase
characters) in files and API responses. A verifier reads a key as 64 hex
characters, in either case, with nothing around them but ASCII spaces,
tabs, carriage returns and line feeds: any other character, a byte-order
mark or Unicode white space included, makes it no key, as languages
disagree about what white space is. `bellbriar-evidence keygen`
writes each half in a file of its own whose first line names the half
(`# bellbriar-evidence private key (Ed25519). …` or `# bellbriar-evidence
public key (Ed25519). …`), so neither can be given where the other goes:
both are 64 hex characters, and a public key used to sign would be a
private key anyone can derive. A file holding the 64 characters alone, as
keygen wrote them before 1.0, is read too, unless it has another name (a
hard link); one named `*.pub`, or reached through a link with such a name,
or marked as a public key, is never read as a signing key.

A public key that encodes a point of small order — y, the encoding with its
top bit cleared, is one of 0, 1, p − 1 (p = 2^255 − 19),
`26e8958fc2b227b045c3f489f2ef98f0d5dfac05d3c63339b13802886d53fc05` or
`c7176a703d4dd84fba3c0b760d10670f2a2053fa2c39ccc64ec7fd7792ac037a` (as
little-endian bytes) — or y at or above p, is refused: no one holds its
private key, and under it a signature can be made without one (R the same
kind of point, S zero), so it shows nothing about who signed. So is one
that encodes no point of the curve: no x satisfies the curve's equation
for its y, or x is zero and the sign bit is set (RFC 8032 §5.1.3). No
private key has such a key, so no signature under it shows anything.
`bellbriar-evidence verify` says it could not verify such a bundle (exit
2), and does the same under the published test key of §9, whose private
key is printed below.

    key_id = first 16 hex characters of SHA-256(raw 32-byte public key)

`key_id` is a locator, not a security boundary: the verifier still checks
the full signature under the full public key. Rotation publishes a new
public key with its new `key_id`; old bundles continue to verify under
the key that signed them.

## 9. Test vectors

All values below are in `docs/canonicalization-vectors.json`, which
`tools/make_canonicalization_vectors.py` regenerates and
`tests/test_canonicalization.py` checks against both the library and this
document. The signing key is **public by construction**:

    private key = SHA-256("bellbriar-canonicalization-vector-key/1")
                = 86682fe0b10f1e2e3ba92301bf62568d51e49efceb3291f9cb0776093dbc6dd9
    public key  = ab09aea58dae707abe74fb7d31af56285d78ac02cd7f11aec1cf6c4d782aee96
    key_id      = 172f109161589572

### 9.1 Canonicalization

| Input (Python literal) | `canonical` (UTF-8) |
|---|---|
| `{"rate": 1.0}` | `{"rate":1}` |
| `{"rate": -0.0}` | `{"rate":0}` |
| `{"rate": 0.9375}` | `{"rate":0.9375}` |
| `{"rate": 0.0001}` | `{"rate":0.0001}` |
| `{"rate": 12345.6789}` | `{"rate":12345.6789}` |
| `{"x": 0.30000000000000004}` | `{"x":0.30000000000000004}` |
| `{"bytes": 1263, "n": -7}` | `{"bytes":1263,"n":-7}` |
| `{"n": 9007199254740992}` | `{"n":9007199254740992}` |
| `{"n": 9007199254740992.0}` | `{"n":9007199254740992}` |
| `{"b": {"y": 2, "x": 1}, "a": [3, {"d": 4, "c": 5}]}` | `{"a":[3,{"c":5,"d":4}],"b":{"x":1,"y":2}}` |
| `{"ok": True, "no": False, "none": None}` | `{"no":false,"none":null,"ok":true}` |
| `{"s": "천연 발효빵 — ünïcödé"}` | `{"s":"천연 발효빵 — ünïcödé"}` |
| `{"s": "a\"b\\c\nd\te\u0001f/g"}` | `{"s":"a\"b\\c\nd\te\u0001f/g"}` |
| `{"o": {}, "l": []}` | `{"l":[],"o":{}}` |

Rejected by the producer, and malformed to a verifier (the JSON file gives
each as JSON text where JSON can express it):

| Input (Python literal) | Why |
|---|---|
| `{"x": float("nan")}`, `{"x": float("inf")}` | not JSON |
| `{"ключ": 1}` | non-ASCII object key |
| `{1: "a"}` | non-string object key |
| `{"x": 2**53 + 1}` | integer beyond 2⁵³ |
| `{"x": 2.0**60}` | integer-valued number beyond 2⁵³: Python prints `1152921504606846976`, JavaScript `1152921504606847000` |
| `{"x": 0.00005}` | decimal smaller than 0.0001: Python prints `5e-05`, JavaScript `0.00005` |
| `{"s": "\ud800"}` | lone surrogate: no UTF-8 encoding |

Malformed files (§6): a verifier must refuse each of these texts.

| File text | Why |
|---|---|
| `{"domain":"a.com","domain":"b.com"}` | duplicate member names |
| `{"signature":{"alg":"Ed25519","alg":"Ed25519"}}` | duplicate member names inside the signature block |
| `{"signature":{"statement":{},"\u0073tatement":{}}}` | duplicate member names, one spelled with an escape |
| `{"x":1e999}` | too large for a double: `JSON.parse` reads Infinity |
| `{"x":9007199254740993}` | integer literal beyond 2⁵³: a double reads 9007199254740992 |
| `{"x":9007199254740993.0}` | the same integer spelled as a decimal |
| `{"x":0.67570000000000001}` | more digits than a double holds: read as 0.6757 |
| `{"x":1e-400}` | underflows: read as 0 |
| `{"x":1e-99999999999999999999}` | underflows, with an exponent no bounded decimal type holds |
| `{"x":NaN}` | not JSON |
| `{"x":5e-05}` | decimal smaller than 0.0001 (§2) |
| `{"s":"\ud800"}` | lone surrogate (§2) |
| `{"ключ":1}` | non-ASCII object key (§2) |
| `[1,2]` | not an object |
| `{"a":[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]}` | 33 levels: deeper than 32 |

Malformed bytes (§6), in hex:

| File bytes | Why |
|---|---|
| `efbbbf7b7d` | a byte-order mark before `{}` |
| `7b2273223a22ff227d` | `{"s":"` then the byte `ff`, which is not UTF-8 |

Other spellings that a verifier must accept, because each denotes exactly
the canonical value:

| File text | `canonical` (UTF-8) |
|---|---|
| `{"x":1.0}` | `{"x":1}` |
| `{"x":1e2}` | `{"x":100}` |
| `{"x":-0.0}` | `{"x":0}` |
| `{"x":0.67570}` | `{"x":0.6757}` |
| `{"x":6.757e-1}` | `{"x":0.6757}` |
| `{"x":0e99999999999999999999}` | `{"x":0}` |
| `{"s":"\u0041"}` | `{"s":"A"}` |
| `{"a":[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]}` | the same: 32 levels, the most allowed |

### 9.2 Bundle and statement

Unsigned bundle (see the JSON file for the exact object). Its canonical
body:

```
{"attestation":"A test vector: evidence of nothing.","bundle_format":"bellbriar-evidence/1","coverage_note":"천연 발효빵","created_at":"2026-01-01T00:00:00+00:00","domain":"example.com","fetch":{"final_url":"https://www.example.com/","host":"www.example.com","pages":0},"inputs":[{"bytes":1263,"path":"fixtures/good.html","sha256":"ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"}],"judged":null,"layers":[],"pack":{"files":1,"manifest_sha256":"0000000000000000000000000000000000000000000000000000000000000000","name":"wcag","signature_verified":false,"version":"1.0.0"},"pages":[],"rulebook_sha256":"0ed2bae6a54ecb271075cdc39f0e5a8d00afa7fa336a2d5e7bbe994051f47aff","rulebook_version":"0.1.0","site":{"pct_pages_tier1_clean":0.5,"site_weighted_pass_rate":1,"total_fail_findings":0},"tool":{"name":"bellbriar-harness","version":"0.3.0"}}
```

Note `"site_weighted_pass_rate":1` — the bundle holds `1.0`; the canonical
form holds `1` (§2 rule 4). The body has every member §5 "The body"
requires, most of them empty: the `fetch` block is cut down to the three
fields that matter here, and the run has no pages; a real one also says
how the pages were listed, and each page carries its own capture record
(§5 "Pages").

    bundle digest      0e3a1d15bca0f4c3193b536cb22b7b53660dfa665a343a4558ce436b2a3845a2

Statement (`self-signed`, signer `vector-signer`, signed at
`2026-01-01T00:00:01+00:00`), canonical:

```
{"attestation_class":"self-signed","bundle_digest_sha256":"0e3a1d15bca0f4c3193b536cb22b7b53660dfa665a343a4558ce436b2a3845a2","bundle_format":"bellbriar-evidence/1","domain":"example.com","host":"www.example.com","key_id":"172f109161589572","pack":"wcag","pack_sha256":"0000000000000000000000000000000000000000000000000000000000000000","pack_version":"1.0.0","rulebook_sha256":"0ed2bae6a54ecb271075cdc39f0e5a8d00afa7fa336a2d5e7bbe994051f47aff","rulebook_version":"0.1.0","signed_at":"2026-01-01T00:00:01+00:00","signer":"vector-signer","statement_format":"bellbriar-signature/1"}
```

    statement digest   9795cafea3bca0173394fd707c52b1da1645184bcc67158bd307bc136340a392
    context (hex)      62656c6c62726961722d7369676e61747572652f3100
    signed message     62656c6c62726961722d7369676e61747572652f31009795cafea3bca0173394fd707c52b1da1645184bcc67158bd307bc136340a392
    signature_b64      kRyrNVqVdh+aQIHhTrOqaoe7f/KF4JCz6ZbsaUKAd1JqtI3XFmgv5URUHtXZ/J9ZZ59EuvE1Bd0nyXf35rn/AA==

**The equation (§6 step 3).** RFC 8032 §5.1.7 allows two equations,
and on the three signatures below they disagree: a verifier that checks
the other one, or leaves k unreduced, gives another answer on at least
one of them. Each is over the statement above with `key_id` set to the
key it is verified under, and is in `small_order_parts` in the JSON file.
The first is the vector key's own, with the point of order 8 whose y is
the first §8 lists added to R. The other two are under the vector key
with that point added,

    public key  51bf35c84963ec7dd7a2a6e0b58c5d4780e362b76a5553b4b50f320a023af62c
    key_id      098e6568f0c13c92

a key no RFC 8032 key generation makes and §8 does not refuse: the
second with R as the RFC derives it, the third with R holding
the part of order 8 that makes [S]B = R + [k]A hold. "k not reduced" is
that equation with k left as the 512-bit integer SHA-512 gives.

| Signature (`signature_b64`) | [S]B = R + [k]A | k not reduced | [8][S]B = [8]R + [8][k]A | Result |
|---|---|---|---|---|
| R with a part of order 8: `kzqGl0V3tz6tKSuY06B2aUzzXB/CUK9O71snZplD8bW4UwqFuYS/0pN5c121CHWxR61YuM6050OTRb+z+OnxCw==` | fails | fails | holds | INVALID |
| a key with a part of order 8: `iPZJktkPn/IC3X9qexEJ+MS+/7BBYLtixy/o2/PAiS6lyUMD1vDNnRbLVgZxtjhMgCwSoSQOaH4wOzpS7xc0Dg==` | fails | fails | holds | INVALID |
| a key with a part of order 8, and R with the part that cancels it: `znR0qzc4m8f5vKDEPAlnnFHpWJY9liyfYfENauIhxxEekvft8YQvV5l0BEPEmYLjdWeu9VkYCqd7wcqza9nACQ==` | holds | fails | holds | VALID |

### 9.3 Pack manifest

Body: `{"name":"wcag","version":"1.0.0","rulebook_min":"0.1.0","files":{"SKILL.md":SHA-256("# wcag\n")}}`, canonical:

```
{"files":{"SKILL.md":"0e93c596a07ba57c5deb3e03fb0b170a7dd3b8931a9dac257ec2c2cce7e8d696"},"name":"wcag","rulebook_min":"0.1.0","version":"1.0.0"}
```

    body digest        7e3aafc27de7371f7d9a4eedcddde88e572cb7057b544ba88c06f15d01f2fcae
    context (hex)      62656c6c62726961722d7061636b2f3100
    signed message     62656c6c62726961722d7061636b2f31007e3aafc27de7371f7d9a4eedcddde88e572cb7057b544ba88c06f15d01f2fcae
    signature_b64      zyP2nsZdS/yoFs4AxEWdNS7OfJuj97P/EJGAveDtcfc7O1Dh18D295pF+/ST72T/N6BvHWmH6nvyC9jw501PBw==

### 9.4 Host and domain (§6 step 6)

How a statement's `host` relates to its `domain`. `unrelated` is
rejected; `subdomain` verifies and is named in the result; `unstated`
means there is nothing to compare (a file run, or no domain stated).

| `host` | `domain` | Relation |
|---|---|---|
| `example.com` | `example.com` | same |
| `www.example.com` | `example.com` | same |
| `example.com` | `www.example.com` | same |
| `staging.example.com` | `example.com` | subdomain |
| `staging.example.com` | `www.example.com` | subdomain |
| `a.b.example.com` | `example.com` | subdomain |
| `www.staging.example.com` | `staging.example.com` | same |
| `example.com` | `staging.example.com` | unrelated |
| `badexample.com` | `example.com` | unrelated |
| `example.com.evil.test` | `example.com` | unrelated |
| `evil.com` | `www.com` | unrelated |
| `192.0.2.1` | `192.0.2.1` | same |
| `192.0.2.10` | `192.0.2.1` | unrelated |
| `::1` | `::1` | same |
| `::1` | `localhost` | unrelated |
| null | `example.com` | unstated |
| `example.com` | null | unstated |

### 9.5 The host read from `final_url` (§5)

| `fetch.final_url` | Host |
|---|---|
| `https://www.example.com/` | `www.example.com` |
| `HTTPS://Example.COM:8443/a?b#c` | `example.com` |
| `https://user:pw@staging.example.com/` | malformed (§6) |
| `https://a@b@example.com/` | malformed (§6) |
| `https://example.com?x=@evil.test` | `example.com` |
| `https://example.com#@evil.test` | `example.com` |
| `https://example.com./` | `example.com` |
| `http://127.0.0.1` | `127.0.0.1` |
| `http://[::1]:8080/x` | `::1` |
| `https://[::ffff:7f00:1]/` | `::ffff:7f00:1` |
| `https://xn--bcher-kva.de/` | `xn--bcher-kva.de` |
| `https://evil.test\@example.com/` | malformed (§6) |
| `https://ex%61mple.com/` | malformed (§6) |
| `https://bücher.de/` | malformed (§6) |
| `https://example.com/a b` | malformed (§6) |
| `https://example.com:80a/` | malformed (§6) |
| `https://example.com:/` | `example.com` |
| `https://[::1/` | malformed (§6) |
| `https:///path` | malformed (§6) |
| `ftp://example.com/` | malformed (§6) |
| `example.com` | malformed (§6) |

### 9.6 Page capture records (§5 "Pages")

Each case is a whole bundle: the bundle of §9.2, unsigned, with its own
`fetch`, `pages`, `inputs` (empty unless the case gives them) and `judged`
(null unless the case gives it), so a verifier checks it as it checks any
bundle. The vectors file holds each one. First, a URL run of one page,
`fetch` = `{"final_url": <first column>, "pages": 1}` and that page named
by its own `final_url` (by the first column when it has no record), or,
where the first column is null, a run that fetched nothing (`fetch` null)
whose one page, `index.html`, has the record in the second column:

| `fetch.final_url` | the page's `fetch` | Result |
|---|---|---|
| `https://www.example.com/` | `{"final_url": "https://www.example.com/about"}` | fine |
| `https://www.example.com/` | `{"final_url": "HTTPS://WWW.Example.com:443/x"}` | fine |
| `https://www.example.com/` | `{"final_url": "https://www.example.com/x", "host": "www.example.com"}` | fine |
| `https://www.example.com/` | null | malformed |
| `https://www.example.com/` | `{"final_url": "https://example.com/"}` | malformed |
| `https://www.example.com/` | `{"final_url": "https://www.example.com/x", "host": "example.com"}` | malformed |
| `https://www.example.com/` | `{"final_url": "www.example.com/x"}` | malformed |
| null | `{"final_url": "http://127.0.0.1:8123/index.html"}` | fine |
| null | `{"final_url": "http://[::1]:8080/"}` | fine |
| null | `{"final_url": "http://localhost:3000/"}` | fine |
| null | `{"final_url": "http://app.localhost/"}` | fine |
| null | null | fine |
| null | `{"final_url": "https://www.example.com/"}` | malformed |
| null | `{"final_url": "http://127.000.0.1/"}` | malformed |
| null | `{"final_url": "http://10.0.0.5/"}` | malformed |
| null | `{"final_url": "http://localhost.example.com/"}` | malformed |

Then bundles whose `fetch`, `pages`, `inputs` and `judged` are these:

| Bundle | Result |
|---|---|
| a URL run of two pages | fine |
| fetch.pages counts more pages than the bundle has | malformed |
| a URL run's fetch without pages | malformed |
| a page of a URL run with no capture record | malformed |
| a page named by another URL than it was fetched from | malformed |
| a snapshot input from another host | malformed |
| a snapshot input in a run that fetched nothing | malformed |
| a build rendered on this machine: every page has a record | fine |
| a run that fetched nothing, with one page record of two | malformed |
| inputs that are not an array of objects | malformed |
| a URL run's input that is not a page's snapshot | malformed |
| a run that fetched nothing, with an input naming a site | malformed |
| a run that fetched nothing, with a page named by a site | malformed |
| a judged page that is not a page of the bundle | malformed |
| judged pages that are pages of the bundle | fine |
| a page record whose final_url has a user name | malformed |
| pages and inputs that are null | malformed |
| judged pages that are null, as if absent | fine |
| a page with no fetch member | malformed |

### 9.7 The signature block (§5)

Each case is the bundle of §9.2 with this signature block; the vectors
file holds each block.

| Signature block | Result |
|---|---|
| the vector's own block | valid |
| an extra member | malformed |
| an extra member that is null | malformed |
| alg that is not Ed25519 | malformed |
| context that is the pack format | malformed |
| no alg | malformed |
| no context | malformed |
| key_id that is a number | malformed |
| signature_b64 that is null | malformed |
| statement that is a string | malformed |
| statement that is null | malformed |
| a __proto__ member | malformed |
| a statement with a member the format does not define | malformed |
| a statement with a __proto__ member | malformed |
| the pre-0.3.0 bare-digest form | malformed |
| signature_b64 without its padding | invalid |
| key_id of another key | invalid |

### 9.8 The spelling of `domain` (§5)

The §9.2 bundle with its `domain` replaced, as JSON strings (`\u0430` is
the Cyrillic letter that looks like `a`). "fine" means the body is as §5
gives it; "malformed" means a verifier refuses the file (§6).

| `domain` | Result |
|---|---|
| `"example.com"` | fine |
| `"www.cornerbakery.example"` | fine |
| `"xn--bcher-kva.de"` | fine |
| `"under_score.example"` | fine |
| `"localhost"` | fine |
| `"192.0.2.1"` | fine |
| `"::1"` | fine |
| `"::ffff:7f00:1"` | fine |
| `""` | malformed |
| `"WWW.CornerBakery.example"` | malformed |
| `"example.com."` | malformed |
| `"a..example"` | malformed |
| `"cornerb\u0430kery.example"` | malformed |
| `"b\u00fccher.de"` | malformed |
| `"https://example.com/"` | malformed |
| `"example.com:443"` | malformed |
| `"1.2.3"` | malformed |
| `"01.2.3.4"` | malformed |
| `"example.0x1f"` | malformed |
| `"[::1]"` | malformed |
| `"0:0:0:0:0:0:0:1"` | malformed |
| `"::ffff:127.0.0.1"` | malformed |

## 10. Extension and versioning

- The bundle **body** is closed at its top level for
  `bellbriar-evidence/1` (§5 "The body"); the records inside it are not,
  and a verifier checks in them only what §6 lists, naming where they
  hold a member its release does not write (§6): a later release may
  add one there without a new format. No field is reserved;
  in particular there is no `prev_digest` and no chain semantics. A bundle
  is evidence of one measurement.
- A list of the values a record's member takes is closed unless
  `docs/REPORT.md` marks it *open* (a finding's `origin`): a later release
  may add a value to an open list, in a bundle's records as in a report,
  without a new format.
- The **signature block** is closed (§3, §5): a new member, such as a
  public transparency-log inclusion proof for the statement, is a new
  format, because nothing in the block but the statement is signed and a
  verifier that ignored unknown members would show a reader whatever
  anyone added.
- After publication (§1), a new bundle format is a new `bundle_format`
  string, a new `statement_format`, and a new context. Verifiers keep
  accepting earlier published formats they know; bundles do not migrate.
