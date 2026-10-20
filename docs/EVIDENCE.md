# Evidence bundles and signatures

Anyone can run every layer of the harness and record the run as an
evidence bundle, and anyone holding a key can sign one. Status at 1.0.1:
the bundle format, offline verification and self-signing are built, and
self-signed is the only kind of signature this release makes. There is no
signing service, no hosted runner, no pack pinning and no judge (the ship
list's L2–L5). `docs/MEASUREMENT-AND-EVIDENCE-GUIDE.md` is the
plain-language version of this page; `docs/CANONICALIZATION.md` is the
byte-level spec with test vectors.

## Bundle contents
`bellbriar-eval … --bundle out.json` produces `bellbriar-evidence/1`:
the tool record (`tool`: the harness version, the Python it ran on, and
the versions of the libraries that decide verdicts — justhtml,
beautifulsoup4, soupsieve and expat, and with a browser Playwright and
the axe-core the harness ships), the rulebook's version and SHA-256 in
canonical form (`rulebook_sha256`: a custom `--rulebook` changes it), a
SHA-256 manifest of the input files, layer coverage and the coverage
sentence, the full deterministic results and scores (including how many
Tier-1 rules executed out of how many exist), the attestation text, and
an optional signature. The body is closed at its top level, as the
signature block is: a bundle with a member the format does not define,
without one it defines as required, with one of another JSON type, or
with another `bundle_format`, is malformed (CANONICALIZATION §5, "The
body"). The records inside it (`tool`, `site`, `pages` and the rest) are
not closed: `verify` checks in them only what the format specification's
§6 lists, so anything else they hold, like every result and the
`coverage_note`, is what whoever made the bundle wrote. `verify` says
whether the `attestation` text is the one its own release writes;
another is the words of whoever made the bundle. It also says, and
`inspect` too, what else the bundle holds that its release does not
write: how many members of those records, and where (it never repeats
their names, which are the maker's words too), a coverage note that is
not one it writes, and layer records that are not its own (a status its
note does not make, a layer twice). None of it
changes the verdict, and a bundle a later release made, with a member
this one does not know, still verifies. `pack` and `judged` are always null in the
bundles this release writes: packs and the judge are not in 1.0, and the
fields stay so that they can return without a new format. (`verify`
names a pack or judged results it finds in any bundle as its maker's
claim.) A page's findings are its report's (docs/REPORT.md,
`pages[i].findings[j]`), with `scored` in place of the report's `owned`
and without `about`, `fingerprint` and `in_baseline`; each says what kind
of verdict it is (`verdict_basis`: sc, heuristic, policy, best-practice
or review), so the bundle says it without the rulebook beside it. Each
finding about an element carries its locator (`selector`: one CSS
selector per tree, the guide's "Where a finding is"). A run gated against a `--baseline` report
records it (`baseline`: the report's SHA-256, when it was made, how many
findings it lists, and how many of the run's findings, and of its FAIL
findings in the site's own markup, it does not list; docs/REPORT.md). Its
gate counted only those, and the bundle still lists every finding;
`baseline` is null for a run without one.

A URL run records what it fetched twice over. The run's record, `fetch`,
names the host every page was fetched from, read from the first page's
final URL (`final_url`, `host`), how many pages the bundle shows
(`pages`: the URLs listed, less repeats) and how they were listed (`list`: `{"kind": "urls", "max_pages": N}`, or
`{"kind": "sitemap", "url", "listed", "complete", "max_pages"}`). Each
page's capture record is `pages[i].fetch`: its final URL, status, browser,
wait, snapshot hash and how the rules read the snapshot (`reader`: `dom`,
`html` or `xml`), so a re-run can read it the same way (`--read-as`). It
also says whether the page came from a public site (`address_class`:
loopback, private or public, from the same table `verify` reads) and what
decided it (`address_basis`: `address`, when the host is an address, or
when the connection that answered went to the recorded host itself and
its address was seen; `name`, when only the name was known — `localhost`,
a fetch through a proxy, or a page that moved on to another host — where
"public" means only that nothing said otherwise). `verify` reads only the
host, so for a name it reports such a record as what it is: the capture
records' word that the name resolved to a loopback or private address. A
rendered capture's record also names the axe-core run behind its rendered
rules (`axe`: engine, version, the SHA-256 of the file that ran, whether
its results were recorded and if not why, the rules it ran and any it ran
out of time for (`not_run`), how many elements carry its results
(`elements`), how many results no element carries (`not_located`: each
rule reports its own about the page), how many elements of the snapshot
it did not check (`unchecked`: inside closed shadow roots it was not
given) and how many the page added after it started (`added`)) and the
second, narrow viewport (`narrow`: 320 by 640 CSS pixels, taken after the
capture; whether what the page hides there was recorded, how many
elements the page changed on being narrowed (`changed`; `changed_all`
when it changed more than the watch counts, and every narrow-only finding
is then a review), its reflow
measurement, and whether the page clips what reaches past its edge
(`clipped`)); the results themselves are in the snapshot, under the
capture's secret names, so a re-run reproduces them. Each page's score
says how many Tier-1 rules ran on it (`tier1_rules_executed`). The
input manifest has one entry per page captured, its snapshot. A
`--render` run fetched nothing from a site: its `fetch` is `null`, each
page's capture record names the loopback address the build was served
from, and the manifest lists the page files and, as `"kind": "served"`,
every other file the server sent (scripts, styles, data), each with its
SHA-256. A file run's `fetch` and each `pages[i].fetch` are `null`. A
verifier requires every page's capture record to name the host the
statement binds — or, in a run that binds none, loopback — so one page of
a bundle cannot be from another site. In a URL run every page has a
capture record and is named by the URL it was fetched from, `fetch.pages`
counts the pages, and an input that names a site is the snapshot of a page
on the bound host; in a run that fetched nothing, either no page has a
record or every page has one, and no page or input is named by a site's
URL. The judged track's pages are pages of the bundle, and no final URL,
page name or snapshot name carries a user name (CANONICALIZATION §5,
"Pages"). A verifier does not read the other URLs a capture record holds
(the URL requested, the redirects, the URL the pages were listed from):
that they carry none either, as the next paragraph says, is the
producer's record, which `verify` does not check.

No URL a bundle records (a page's path, a capture record's URLs, an
input's name) carries a user name, password or parameter value: values
are written `REDACTED` unless the operator named the parameter with
`--record-query`, a path parameter's (`/shop;jsessionid=…`) as a
query's, and each page's capture record lists what was left out
(`pages[].fetch.redacted`). A fragment that is a client route (`#/pricing`)
keeps its path, its query redacted; one holding `=`, `&`, `;`, `#` or
`?` in its path, spelled out or percent-encoded (`#/access_token=…`), is
redacted as parameters, names kept. A parameter with no value, or a
padded token (`?<token>=`), is replaced whole.

A finding's snippet and message quote the page's markup. A URL in them is
written as a recorded URL is, with no user name or password and every
query value `REDACTED` (`--record-query` does not apply there), where it
sits in an attribute HTML or SVG defines for URLs (`href`, `src`,
`srcset`, `action`, `formaction`, `ping`, `poster`, `data`, `cite`,
`xlink:href`, a meta refresh's `url=` and the like) or is written whole
(`https://…`), read as a browser reads it: after a special scheme and any
slashes or backslashes, or after `//` in a relative URL, with tabs and
line breaks ignored. A fragment holding parameters is redacted too, and a
client route keeps its path; a fragment of up to 64 characters with no
`=`, `&`, `;` or `?` is kept, as an element's id (`#main`). In a
`javascript:` or `data:` value, the query values and any user name and
password written in it are replaced. The values of a URL run's own
parameters that look like credentials, and the `--http-user`
credentials as a request's Authorization header carries them (base64 of
the user name and password, and of the password alone, in either
alphabet, padded or not: a page that echoes request headers quotes
them), are replaced wherever a finding quotes them, as the URL gave
them, or with any character as a character reference, percent-encoded
(in either case, a space as `+`), with `&` or `%` escaped again once or
more (`&amp;`, `&#38;`, `%25`), or as JSON, a script or CSS escapes it
(`\u002f`, `\x2f`, `\u{2f}`, an octal `\57`, CSS's `\2f ` or
`\00002f`, or `\/`, where a script and CSS both read the character
after a backslash as itself), its backslash escaped again or not
(`\\\/`), and `&` and `%` so too (`\u0026#43;`), but not where a
script's octal escapes and CSS's hex escapes, which read `\61` as
different characters, are both used; a run of backslashes as it is,
doubled, or four or eight times over, or each backslash spelled
otherwise (`%5C`, `&#92;`); in the element's whole markup before
anything is cut:
redacting the URLs before a cut shortens what comes before it, which
would otherwise bring a value's cut-off rest into the 180 characters a
snippet keeps. A locator never anchors on an id that holds one. A
snippet, locator or message that holds the `--http-user` password
anywhere (of four characters or more; a shorter one is not looked for),
in any case, each of its characters as it is, as a character reference
(`&#33;`, `&excl;`), percent-encoded (UTF-8, or Latin-1), its white
space as `+` too, or as JSON, a script or CSS escapes it (its white space
as `\t` or `\n` too), with `&` or `%`
escaped again or not (`&amp;#33;`, `&#38;#33;`, `%2521`, `&#37;21`),
with or without white space between them, is withheld whole
(`REDACTED`, or a message saying it was withheld): a word left around it
would give it away. A password that holds a spelling of white space just
after its own (`a %20b`) may be missed where that white space is spelled
so too. A withheld field still tells a reader that the
password is somewhere in it, in text the reader may know, so only a long
random password, which no page holds, is safe from that; a password the
harness's own text holds ("name", "test", or a word of the axe-core
messages it quotes), or one a URL of the run holds, is refused before
the run, and a page that goes to a URL holding it, or holding the
Authorization header the credentials make, is not evaluated. An
axe-core message is cut, to 600 characters, only after the run's secrets
are replaced in it whole. Other
text a page writes is quoted as it is, within the 180 characters a
snippet keeps: a relative URL in an attribute HTML does not define for
URLs (`data-href="/x?t=…"`), say, the page's text, or a token the page
made from the one it was sent.

No file path is absolute or contains `..`: a
relative path is recorded as given, and any other path relative to the
parent of the file or directory argument it came from (`bellbriar-eval
/home/u/client/dist` records `dist/index.html`), with forward slashes;
two different files never share a name (each gets as many of its parent
folders as tell them apart, never a home directory: files told apart only
by one are numbered `~1/…`, `~2/…`; a relative path keeps its name; a
name's bytes that are not UTF-8 are written `%XX`, and a `%` itself
`%25`, so two names that differ only there stay two; a name whose first
part holds a colon or any character outside ASCII, which could read as a
site's URL (a folder named `https:`, or `һttps:` in Cyrillic), is written
`./` first: `./https:/…`, and a verifier refuses such a name without
it). No name starts with a
home directory: `bellbriar-eval ~` records `site/index.html`, not the
user's name. A
fetch's fallback reason names a failed rendered fetch in the harness's own
words — the Playwright step that failed and a `net::` error code, a
timeout or a fixed description — never in the browser's or the page's
text, which a script on the page can choose; that text goes to the
console only. The free text a bundle still records (a fetch's notes) has the operator's home directory, and any other home
directory a local path runs into (`/home/<user>/…`, `/Users/<user>/…`,
`C:\Users\<user>\…`), replaced with `~`; a URL other than `file://` is
left as it is.
A signed bundle cannot be redacted afterwards, so this happens at capture
and at collection.

Digest = SHA-256 over the canonical JSON of the bundle minus `signature`
(canonical form: keys sorted, no whitespace, UTF-8, and numbers limited
to integers up to 2⁵³ and decimals from 0.0001 up, with integer-valued
floats serialized as integers — see CANONICALIZATION §2. The number rules
are what keep a JavaScript verifier's digest equal to Python's. The
producer rounds decimals to four places, and canonicalization refuses
anything outside the rules rather than emit a digest only Python
reproduces. A verifier also refuses a file whose text can be read two
ways, such as a duplicated key or a number no double holds as written:
CANONICALIZATION §6).

## Signatures are over a statement, not a digest
A signature is made over a **statement** that records the bundle digest
together with the bound fields: the bundle format, the domain, the host a
URL run fetched, the pack's name, version and digest (null in this
release), and the rulebook's version and digest. `verify_bundle` recomputes the digest
and then requires every bound field in the statement to equal the
bundle's own value, so a signature cannot be moved to another bundle, or
kept over one whose claims changed. The host must be the domain or its
`www.` form, or a subdomain, which `verify` names in its result — so a run
measured on `staging.example.com` never reads as `example.com` itself.
The harness refuses a subdomain run unless `--include-subdomains` is
passed. The host is read from the capture's own `final_url`, so a bundle
cannot show a reader one host and bind another. Signatures are
`Ed25519( "bellbriar-signature/1\0" ‖ SHA-256(canonical(statement)) )`;
the context byte-string separates statement signatures from pack-manifest
signatures. The verifier fixes that context itself: a bundle's statement
is accepted only under `bellbriar-signature/1`, whatever format the
statement names. The signature block has exactly five members (`alg`,
`context`, `key_id`, `statement`, `signature_b64`); a bundle with any
other, or with another `alg` or `context`, is malformed, because nothing
in the block but its statement is signed. Pre-0.3.0 bare-digest
signatures are malformed for the same reason.

Signing is local: `bellbriar-evidence keygen --out-prefix NAME` writes a
key pair (the private key mode 600, and never over an existing file
without `--force`; with it, each new file is written beside the old one
and renamed over it, and only a regular file is replaced), and
`--sign-key FILE` or `--sign-key-env NAME` reads the private key from a
file or an environment variable. Each file's first line says which half
it holds (`# bellbriar-evidence private key (Ed25519). …` and
`# bellbriar-evidence public key (Ed25519). …`), then the key's 64 hex
characters: both halves are 64 hex characters, and a signature made with
the public half as its private key could be made by anyone. A `.pub`
file, a link that leads to one (through other links or not), or a file
whose first line says it holds a public key, never signs; a file with
another first line is no key file; a file of the key alone, as keygen
wrote them before 1.0, is read as before, unless it has another name too
(a hard link), which could be a `.pub` file's. A key is never read from the command
line, where shell history, process listings and CI logs keep it, and no
message repeats what either option was given: typed there by mistake, a
key would reach the log with the message. The render child, and the
browser under it, inherit neither the variable `--sign-key-env` names nor
`BELLBRIAR_SIGN_KEY` and `BELLBRIAR_HTTP_PASSWORD`.
`verify` reports a public key that is not 64 hex characters as "could
not verify" (exit 2), never as INVALID, and names a private key passed
in its place (a key file marked private, or the private half of the key
that signed the bundle). It reports a public key no one can hold a
private key for (a point of small order, under which a "signature" can
be made without one; a key written as no key generator writes it; or no
point of the curve at all) as "could not verify" too, and so the format specification's published test
key, whose private half is printed there (CANONICALIZATION §8, §9). It
checks the signature before it compares what the statement says with the
bundle, so no reason attributes a statement to the key's holder before
the signature shows it is theirs.

## What a signature attests — and what it does not
Every signature this release makes is `self-signed`: the holder of the
key signed the values the client computed, and no one else checked
anything. A valid one shows that the holder of that key signed exactly
this statement and that the bundle body (everything outside the signature
block) is unaltered since. It does **not** show that the evaluation ran
correctly or on the stated inputs, or that its results were not edited
before signing: the client computed them. A URL run's `fetch` block is
the client's record of its capture; no signature attests that the capture
took place as recorded, and so is each page's own capture record, a
build served on this machine included. `verify` says this in its own words, not by
quoting the bundle's `attestation` field, which whoever made the bundle
wrote.

Two more classes are reserved names: **attested submission**, for a
signing service that would check a subscription before signing, and
**attested execution** — "Bellbriar ran this itself" — for a hosted
runner that would fetch the inputs and execute the harness. **Nothing
issues either, and neither a service nor a runner exists.** `verify`
reads a statement claiming one as no more than self-signed. A reference
signing service and its client stay in the repository
(`tools/reference_signer.py`), outside the installed package, for when a
production service exists.

## Verification is third-party by design
`bellbriar-evidence verify bundle.json --public-key <hex>` is offline and
requires only the signer's published public key. It also says whether the
bundle's rulebook is the one the verifier's harness ships (by
`rulebook_sha256`): a custom rulebook, or another release's, is named.
`verify` exits 0 when the signature is valid, 1 when it is not (INVALID,
or unsigned) and 2 when it could not verify (a malformed bundle, a key
that is not one). `bellbriar-evidence inspect bundle.json` shows what a
bundle holds, with no key, and exits 2 where `verify` would refuse the
bundle as malformed, after showing what it can read of it; else 0. A customer's counsel — or
opposing counsel — verifying a bundle is the intended use. The
repository ships a worked example that must verify on every test run:

```
bellbriar-evidence verify examples/evidence/signed-bundle-example.json \
  --public-key examples/evidence/reference-public-key.hex
```

That example is signed with a **demonstration key**, and `verify` names
it as one: it signs only this example and is in no trust path. Its
private half is not published — anyone holding it could sign bundles that
verify against the demo key — so the maintainers regenerate the example
(`tools/make_example_bundle.py`), and verifying it needs only the public
key. A VALID result is only as meaningful as the public key it was
checked against.

## History
There is no chain. Each bundle stands alone as a dated, signed record;
nothing links one to the next, and a signer chooses its own `signed_at`.
Independent timestamping of statements via a public transparency log is
the intended mechanism and is on the roadmap. The signature block is
closed, so it will come as a new version of the format.

## Not in this release: packs, the judge, remote signing
Pack pinning (`--pack`), adequacy grading by a judge model (`--judge`)
and remote signing (`--sign-url`) are not in 1.0 (decision D3; the ship
list's L2–L4). Their code and tests stay in the repository for when each
returns: pack pinning when the WCAG pack is released, the judge once a
calibration meets the guide's policy (no judged number is published
before a study exists), and remote signing with a production signing
service. The bundle keeps its `pack` and `judged` fields, always null,
and the statement binds the pack's name, version and digest (null too),
so none of them needs a new format.

## What leaves the machine
Nothing but the requests a run makes for what you point it at: a URL run
fetches the pages you name (and, rendered, whatever they load). Signing
and verifying are local. `--http-user` credentials go only to the run's
one origin, and only when it asks for them. `--render` serves the build on 127.0.0.1 only, for the
length of the run. There is no telemetry.

## Personal data in what a run writes
A report, a bundle or a saved snapshot records what the pages showed the
run, so it holds personal data wherever they did. Treat each as you treat
the pages it was made from: a run over a site's account pages, signed in,
is as sensitive as those pages.

- **Findings quote the page.** Each finding's `snippet` is the start of
  the element's markup (at most 180 characters), its `selector` can name
  the element's id, and a message can quote the element's text (`Generic
  link text "click here"`). A name, an email address or an order number
  in a failing element's markup is in its snippet.
- **Snapshots are whole pages.** `--save-snapshot` and `--save-snapshots`
  write each page's markup as it was captured. A bundle names a snapshot
  by its SHA-256 (`snapshot_sha256`), never by its content.
- **URLs keep their paths.** Query and fragment values, path parameters'
  values and a user name and password in a URL are recorded as `REDACTED`
  (docs/REPORT.md, the page's `path`); a value in the path itself
  (`/users/jane-doe`) is kept, as nothing tells it from a page's name.
- **Credentials are not recorded.** Neither the `--http-user` user name
  nor its password is written anywhere; a capture record says only that
  credentials were sent (`redacted` lists `http-credentials`).
- **Who and when.** A signature names its signer as the signer chose
  (`signer`, free text: a name, a team, a role), with the key's id and
  `signed_at`; a bundle records when it was made (`created_at`) and when
  each page was fetched (`fetched_at`).
- **Files by the names the run was given.** A file is recorded by its
  path as the command line named it, when that path is relative and has
  no `..` (`bellbriar-eval site/dist` records `site/dist/index.html`), and
  otherwise from the file or folder named on (`/srv/client/dist` records
  `dist/index.html`): never absolute, and never with a home directory in
  it (`/home/alice`, `/Users/alice`, `/root`, the operator's own), which
  is left out with what is above it. The machine's name, the account that
  ran it and the environment's variables are not recorded; a capture's
  notes say only whether Chromium's sandbox ran, and why not (running as
  root, say).

The harness keeps nothing itself: it writes only the files its options
name, where they name them. Each page a browser captures has a temporary
folder of its own, which holds the browser's profile for it (its cache,
cookies and storage) and is removed when the capture ends, at its
deadline too; a run that is itself stopped mid-capture leaves it to the
capture process, which removes it as it stops, unless that process is
stopped first (a folder named `bellbriar-capture-…` in the system's
temporary folder).
