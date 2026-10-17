# Pre-publish checklist (blockers before the repo goes public)

1. **LICENSE**: done in Part R4 (October 11, 2026). LICENSE is the
   verbatim Apache-2.0 text (SHA-256 `cfc7749b96f63bd31c3c42b5c471bf75`
   `6814053e847c10f3eb003417bc523d30`, as apache.org publishes it), and
   the copyright notice is in NOTICE, with axe-core's attribution; the
   package metadata states `Apache-2.0 AND MPL-2.0 AND MIT AND ISC AND
   BSD-3-Clause` (PEP 639), since the wheel carries axe-core and the source
   distribution the web-platform-tests data the tests read.
2. **ACT verification pass**: done in Part R2 (October 10, 2026). Every
   `act_rules` entry names its W3C rule by id, title and status (approved,
   proposed or deprecated), checked against `w3c/wcag`'s act-mapping.json
   and each rule's page in `w3c/wcag-act-rules`; a rule that can fail
   cites an ACT rule only for a criterion it requires for conformance and
   cites only A and AA criteria, and each criterion an `sc` rule cites
   rests on an approved ACT rule that requires it or a W3C failure
   technique (`w3c_failures`) that fails it. Before release, rebuild
   `tests/data/w3c-citations.json` from fresh clones
   (`tools/w3c_citations.py`) and update `citations_checked` in the
   rulebook: `tests/test_citations.py` then fails on any citation W3C has
   changed. Standing rule: no unverified citation ships. Rebuilt in Part
   R5 (October 11, 2026) from `w3c/wcag` 23bad59 (2026-10-04) and
   `w3c/wcag-act-rules` f39b7f8 (2026-10-08), the heads that day:
   unchanged.
3. **Spec verification pass**: done in Part R2. Every SC number, level,
   Understanding URL (in the WCAG 2.1 or 2.2 set it names) and failure
   technique is checked against `w3c/wcag` the same way, and the DOJ and
   HHS citations in README against the Federal Register (91 FR 20902 and
   91 FR 25496) on October 10, 2026. Re-check both before release.
4. **Fixture sweep**: run against 5–10 real AI-generated sites from the
   audit motion; triage false positives before the 1.0.0 tag.
5. Package name availability on PyPI; reserve `bellbriar` on npm. On
   GitHub, `bellbriar` is the maintainer's own account, a user and not
   an organization (October 13, 2026): `bellbriar/harness`,
   `bellbriar/eval-action` and `ghcr.io/bellbriar/harness` live under
   it, and no organization can take the name. Should the account become
   an organization later, `.github/CODEOWNERS` must name a person or a
   team again (item 14).
6. CODEOWNERS, SECURITY.md, contribution policy (CLA not required;
   DCO sign-off).
7. Confirm the no-telemetry statement remains true in code review.
8. **Key ceremony** — not for 1.0, which signs only self-signed bundles
   with each user's own key (D5): with the production signing service
   and the pack release (the ship list's L2, L3), generate the production
   Ed25519 signing key and the pack-release key offline; publish public
   keys in the repo and at a well-known URL; document rotation (key_id
   already travels in bundles).
9. The reference signing service (`tools/reference_signer.py`, outside
   the installed package) is a contract demo — a production signer needs
   TLS, replay windows, rotation, billing, and audit storage before any
   customer-facing use (L2).
10. Calibration golden sets, judge agreement data, and real packs never
   enter this repo; CI check for accidental inclusion.
11. ~~Do not publish until the first benchmark number is ready to ship the
   same day (repo + stat land together).~~ **Waived for 1.0** (decision
   D1, October 8, 2026): 1.0 is listed on PyPI without an announcement,
   and the launch waits for the benchmark (`docs/ROADMAP.md` item 8, and
   "Not in 1.0", L7).
12. **Freeze the evidence formats**: done at 1.0.0rc1 (decided in Part
   S). `bellbriar-evidence/1` and `bellbriar-signature/1` were amended in
   place while unpublished, so a bundle signed under an earlier draft may
   not verify (a URL run signed before `host` was bound does not).
   CANONICALIZATION §1 now says they were published with 1.0.0rc1, and
   that every change since takes a new format string and context.
   `bellbriar-pack/1` stays a draft, outside the freeze (§1, §7): 1.0
   ships no packs, and its verification does not yet do what §6 does for
   a bundle.
13. **Re-sign the worked example** (`examples/evidence/`, the ship list's
   L34): done October 14, 2026, with harness 1.0.0 and the demonstration
   key, kept outside the repository (`python tools/make_example_bundle.py
   --private-key <file>`), and again for 1.0.0rc1 (item 15), with the
   libraries the package installs, which also gave its statement the pack
   digest (SA-7). `tests/test_examples.py`'s PENDING lists are empty, the
   README's note about the example is gone, and the README
   quotes what `verify` says of it ("Verify something in thirty seconds"),
   which a test holds to verify's output. The sample pack's SKILL.md, which
   the old example's pack record had fixed, is reworded (L59). A change
   that reaches what the example records (a version: item 15) means
   signing it again, refilling a PENDING list until then; the suite with
   `BELLBRIAR_RELEASE=1` fails while anything is pending. The script
   signs only with the libraries the package installs (R7-2: the first
   signing recorded soupsieve 3.0.1, outside the range), and the release
   check refuses an example that records another.
14. **Repository and registry settings before the first release** (the
   R4 review: R4A-3, R4A-4, R4A-5, R4A-9, R4A-17). The files say what
   these make true; only the settings make it so.
   - Default branch: a ruleset (or branch protection) requiring pull
     requests and the DCO check (install the DCO app,
     https://github.com/apps/dco, and require its check). While one
     person maintains the project, `.github/CODEOWNERS` names that
     person's account (`@bellbriar`, October 13, 2026), and a code
     owner's review is not required: GitHub does not let the author of a
     pull request approve it, so the rule would block every change.
     Require it once a second maintainer can review, and name them in
     CODEOWNERS.
   - Tags: a ruleset restricting who can create `v*` tags, and refusing
     their update and deletion. The release also refuses a tag whose
     commit is not on the default branch.
   - The environment `pypi`: deployment tags limited to `v*` (and a
     required reviewer, if wanted); on PyPI, this repository and
     `release.yml` with environment `pypi` as the trusted publisher.
   - Private vulnerability reporting: enabled (Settings, Code security),
     since SECURITY.md sends reports there. For reporters without a GitHub
     account, SECURITY.md gives security@bellbriar.com (October 13, 2026):
     the address must receive mail (bellbriar.com's mail goes to Proton
     Mail) and be read within SECURITY.md's response times.
   - After the first release pushes the image: make the
     `ghcr.io/bellbriar/harness` package public (its Package settings),
     then re-run the release's `public` job, which pulls it with no
     credentials, and the jobs after it (`tags`, `release`). Until then
     customers' runners cannot pull it.
   - Pin the base image's digest in `docker/Dockerfile`: done October
     15, 2026, for 1.0.0rc1, with the digest the registry gave for
     `v1.63.0-noble`'s multi-platform index (an OCI image index), read by
     the maintainer with `curl` from MCR; `docker buildx imagetools
     inspect` of the tag gives it too. Dependabot then moves tag and digest
     together.
15. **Rehearse the release** before tagging 1.0.0. `release.yml` has never
   run: it needs GitHub, Docker and PyPI, which the stage that wrote it did
   not have (actionlint and shellcheck pass it). Set the version to a
   release candidate, `1.0.0rc1`, everywhere it is stated: pyproject.toml's
   `version`, `__version__` in `src/bellbriar_harness/__init__.py` (a test
   holds the two equal; `--version` prints it, and the release's image
   check compares them), the status lines in README.md and docs that
   `tests/test_examples.py` names (`STATUS_PHRASES`), and README's quote
   of what `verify` says of the example ("Verify something in thirty
   seconds"), which names the version twice; regenerate the
   canonicalization vectors (`python tools/make_canonicalization_vectors.py`:
   the bundle vector's verification names the version) and re-sign the
   worked example with the demonstration key (item 13's command: the suite
   holds the example's tool version to the harness's). Item 13 is done
   first, once (the example re-signed, its PENDING lists emptied, the
   README's note removed); here its command runs again, and the PENDING
   entry Part S added is removed (the statement's `pack_sha256`, SA-7),
   with `ATTESTATION` naming the pack digest among the bound fields from
   1.0.0rc1 on, which the re-signed example then carries. Add a dated
   `## 1.0.0rc1` section to CHANGELOG.md; run the whole suite; merge, then
   tag the merged commit as it stands on the default branch and push the
   tag (`git fetch origin && git tag -s v1.0.0rc1 origin/main && git push
   origin v1.0.0rc1`: a squash or rebase merge leaves your branch's head
   off `main`, the release refuses a tag whose commit is not on it, and
   the tag ruleset forbids moving the tag), and watch every job. Then the
   same steps again for 1.0.0
   (version, vectors, example, CHANGELOG), and the suite once more with
   `BELLBRIAR_RELEASE=1`: for a final version the release workflow runs
   that check too, and stops before anything is published while an item
   is pending (items 13 and 18). A candidate does no harm: the
   image gets only its own tag, GitHub marks the release a pre-release,
   and pip installs a candidate only when asked (`--pre`, or
   `bellbriar-harness==1.0.0rc1`) while PyPI holds a final release that
   it can install, which until 1.0.0 is the 0.0.1 placeholder if its
   files are still there. Fix what fails, then release 1.0.0.

16. **Refresh the language subtags** (`src/bellbriar_harness/langtags.py`,
   which bb-html-lang reads): done October 14, 2026 (Part S), from the
   IANA Language Subtag Registry of File-Date 2026-09-17 (IANA's latest
   that day) and the Library of Congress's ISO 639-2 list, which the
   maintainer downloaded from
   `https://www.iana.org/assignments/language-subtag-registry/language-subtag-registry`
   and `https://www.loc.gov/standards/iso639-2/ISO-639-2_utf-8.txt`
   (`python tools/make_langtags.py language-subtag-registry
   ISO-639-2_utf-8.txt`): eight three-letter subtags added since
   2025-08-25 (bih, dyl, lfb, olb, osd, scz, tvg, zhk), none removed, the
   ISO 639-2 codes unchanged. Refresh it again before a release made much
   later: a page in a language whose three-letter subtag the copy lacks
   gets a review, not a failure; one whose two-letter subtag it lacks
   would fail.

17. **Publish the Action, and check every claim about what is published**
   (the R5 claims audit, H6-21). README's install section and
   `action/README.md` describe the released state: `bellbriar/eval-action@v1`,
   `pipx install bellbriar-harness`, `ghcr.io/bellbriar/harness:1`, private
   vulnerability reporting (SECURITY.md) and the DCO check (CONTRIBUTING.md).
   None exists until the first release. Create the repository
   `bellbriar/eval-action` with every file of `action/` at its root
   (`action.yml`, `README.md`, `LICENSE`, `NOTICE` and
   `seccomp_profile.json`, which `sandbox: required` reads beside
   `action.yml`), once the 1.0.0 image is public (item 14); tag it `v1.0.0`
   and a `v1` that follows it; run `examples/ci/bellbriar-eval.yml`
   against it. Then try each install line of the README on a clean
   machine, and confirm item 14's settings, before announcing the release.

18. **Fix the redaction findings parked as L111** (the ship list), a
   release blocker (decided October 13, 2026): SECURITY.md counts a token
   or a password reaching a report or a bundle as a vulnerability. Done
   October 14, 2026 (Part S), with tests (`tests/test_part_s1.py`): the
   review's report was not at hand, so the fixes follow the ship list's
   description of each finding and what fuzzing the searches found.
   `RELEASE_BLOCKERS` in `tests/test_examples.py` is empty. While a
   blocker is listed there, the suite fails with `BELLBRIAR_RELEASE=1`,
   and the release workflow refuses a final version (item 15).
