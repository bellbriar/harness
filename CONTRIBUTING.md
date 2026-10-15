# Contributing

Thank you for helping. Bellbriar's reports can end up in front of a client
or a court, so every change is held to one rule: what the code, the
reports and the documentation say must be exactly what the code does.

## Sign off your commits (DCO)

We use the Developer Certificate of Origin 1.1
(https://developercertificate.org/), not a CLA. By signing off a commit
you certify that you wrote it, or otherwise have the right to submit it,
under the project's license (Apache-2.0). Sign off every commit:

    git commit -s

which adds a line such as `Signed-off-by: Ada Lovelace <ada@example.com>`
matching the commit's author. A check on every pull request refuses
commits without one (the DCO app's check, which branch protection
requires). `git commit --amend -s` fixes the last commit, and
`git rebase --signoff "$(git merge-base HEAD upstream/main)"` every commit
of your branch, where `upstream` is this repository (in a clone of your
fork, `git remote add -f upstream https://github.com/bellbriar/harness`
adds and fetches it): it signs off exactly the commits your branch added,
whatever its upstream branch is. Both rewrite commits you may have pushed
already, so push the branch again with `git push --force-with-lease`
(not `git pull`, which would merge the unsigned commits back in).

## Set up

    python -m venv .venv && . .venv/bin/activate
    python -m pip install -e ".[dev,browser]"
    python -m playwright install --with-deps chromium

On an Intel Mac, pip installs `cryptography` 48: the package keeps it
below 49 there, the last series with wheels for Intel Macs.

## Before you open a pull request

- Run the whole suite with nothing skipped (it needs Playwright's
  Chromium, `cryptography`, PyYAML, git and Node.js 22; the setup above
  installs all but git and Node.js):

      BELLBRIAR_REQUIRE_ALL_TESTS=1 python -m unittest discover -s tests -t .

- If you changed `rulebook.json` or `guidance.py`, regenerate the rules
  reference: `python tools/make_rules_reference.py`.
- Run the repository guard: `python tools/repo_guard.py`. Private keys,
  calibration golden sets and packs never enter this repository.
- Add a test for every behavior you change, and change the documentation
  in the same pull request.
- A change to an evidence format (bundles, statements, verification)
  needs its spec text, the regenerated vectors and the JavaScript mirror
  (docs/CANONICALIZATION.md).

## Security problems

Do not open an issue: see SECURITY.md.
