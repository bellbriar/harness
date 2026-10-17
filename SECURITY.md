# Security policy

## Reporting a vulnerability

Report it privately, through GitHub's private vulnerability reporting:
this repository's **Security** tab, then **Report a vulnerability**
(https://github.com/bellbriar/harness/security/advisories/new). Please do
not open a public issue, pull request or discussion about it. If you have
no GitHub account, e-mail security@bellbriar.com instead.

Say which version you ran (`bellbriar-eval --version`), what you ran it
on, how to reproduce the problem, and what an attacker gains. We reply in
the advisory (or by e-mail, to a report sent so), keep you informed until
the problem is fixed or we explain why we will not fix it, and credit you
in the advisory unless you ask us not to. We acknowledge a report within
3 business days, give you our assessment within 10, and fix the problem
or publish an advisory within 90 days of the report.

## What counts

The harness reads pages it does not trust: files, sites, and what their
scripts do in a browser. We especially want to hear about anything that
lets a page or a site:

- run code on the machine outside the browser's sandbox, or read or write
  files there, beyond the reports and snapshots the run was told to write;
- reach the loopback build server of a `--render` run from elsewhere, or
  read through it what it must not serve (a path outside the folder, a
  name starting with a dot);
- put a password, token or query value into a report, log or evidence
  bundle that the run was not told to record;
- make an evidence bundle verify when it was changed, or verify as signed
  by a key that did not sign it;
- make the harness report a page as passing that it did not evaluate.

Accessibility verdicts you disagree with are ordinary issues, not security
reports.

## Supported versions

Security fixes go into the latest release. 1.0 is the first release.

## Keeping Chromium current

The container image and the `browser` extra pin one Playwright release,
and the Chromium it brings. We move them to each new Playwright release
within 30 days of it, once the suite and the browser measurements pass
on its Chromium, or say in an issue why we have not.

## Running it safely

A rendered run executes the page's scripts in Chromium. Chromium's sandbox
is on wherever it can start; where it cannot (as root, or where the host or
a container's security profile refuses the user namespaces it needs) the
browser runs without it and every capture records that. Under Docker's
default security profile, the container image is such a place. To refuse
such a run instead, pass `--require-sandbox`. Evaluate sites you do not
control from a machine or CI job that holds no secrets.
