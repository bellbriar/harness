# axe-core 4.12.1 (third-party, unmodified)

This folder holds axe-core, an accessibility testing engine by Deque Systems,
Inc., exactly as Deque publishes it. Bellbriar runs it in the browser, in a
world of its own that the page's scripts cannot reach, for the WCAG A and AA
rules Bellbriar does not implement itself (`bellbriar_harness/axe.py`).

| | |
|---|---|
| Component | axe-core |
| Version | 4.12.1 (git tag `v4.12.1`, commit 5d002cca1f862a0699d9f1bb7b5a1ec334fa1b22) |
| File | `axe.min.js`, 572,599 bytes, byte for byte the `axe.min.js` of the npm package `axe-core@4.12.1` |
| SHA-256 | `66a8aaa95a8b044a7fd74a5435873bf04ff65a1ca75567c921b7509742085a14` |
| Subresource integrity | `sha256-ZqiqqVqLBEp/10pUNYc78E/2WhynVWfJIbdQl0IIWhQ=`, as published in axe-core's `sri-history.json` |
| License | Mozilla Public License 2.0 (`LICENSE`); the code axe-core bundles is under the MIT and ISC licenses (`LICENSE-3RD-PARTY.txt`) |
| Copyright | Copyright (c) 2015 - 2026 Deque Systems, Inc. |

**Source code.** `axe.min.js` is axe-core's executable (minified) form. Its
source code form is available, at no charge, from
https://github.com/dequelabs/axe-core/tree/v4.12.1, and in the npm package
`axe-core@4.12.1` (https://www.npmjs.com/package/axe-core/v/4.12.1), which
also carries the unminified `axe.js`.

**Unmodified.** Bellbriar does not change this file. It checks the file's
SHA-256 against the value above every time it loads it, and runs no axe-core
check when they differ. The MPL-2.0 applies to this file only; the rest of
Bellbriar is under its own license (the repository's `LICENSE`).

**Updating.** Replace `axe.min.js` with the published file of the new
version, compare its digest with that version's entry in axe-core's
`sri-history.json`, and change `AXE_VERSION` and `AXE_SHA256` in
`bellbriar_harness/axe.py` and this page together.
