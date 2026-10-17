# bellbriar/eval-action

Runs the [Bellbriar accessibility harness](https://github.com/bellbriar/harness)
on built pages or URLs in a GitHub Actions job, from its container image
(`ghcr.io/bellbriar/harness`), and fails the job when the gate fails (exit
1) or the run cannot be completed (exit 2), or when Docker cannot start it
(Docker's own exit status, such as 125 when the image cannot be pulled). Linux runners only, x86-64 or
ARM64, and not in a job that runs in a container (`container:`): there the
image would see the host's folders and network, not the job's. On a macOS
runner, install the harness itself instead: `pipx install
'bellbriar-harness[browser]'` (or `uv tool install
'bellbriar-harness[browser]'`), then `bellbriar-eval --install-browser`
for Chromium. The harness does not run on Windows.

```yaml
jobs:
  accessibility:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - run: npm ci && npm run build
      - uses: bellbriar/eval-action@v1
        with:
          args: dist --render --fail-on tier1 --html bellbriar-report.html --json bellbriar-report.json
      - if: always()
        uses: actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9 # v7.0.2
        with:
          name: bellbriar-report
          path: bellbriar-report.*
```

Inputs:

- `args` (required): the `bellbriar-eval` arguments, separated by spaces,
  or one per line (`args: |`) to pass one that holds a space. They are
  never read by a shell: no quotes, variables or wildcards. Empty, the
  step fails (exit 2) rather than pass on nothing.
- `version`: the harness version, `1` by default (the newest 1.x, pulled
  again on each run); a release such as `1.0.0`; a pre-release such as
  `1.0.0rc1`, which `1` never follows; or, for runs that must never
  change, the image's digest (`sha256:…`, in each release's notes, or
  from `docker buildx imagetools inspect ghcr.io/bellbriar/harness:1.0.0`),
  pulled only when the runner does not have it.
- `pass-env`: names of environment variables to hand to the harness, such
  as `BELLBRIAR_HTTP_PASSWORD` for `--http-user`. Set their values in the
  step's `env`, from secrets.
- `sandbox`: `off` (the default) or `required`. `required` gives the
  container Playwright's seccomp profile (`seccomp_profile.json`, shipped
  with the Action) and passes `--require-sandbox`, so the step fails (exit
  2) when Chromium's sandbox cannot start; the runner must allow
  unprivileged user namespaces, which Ubuntu 24.04 restricts: an earlier
  step can run `sudo sysctl -w
  kernel.apparmor_restrict_unprivileged_userns=0`. The harness's CI
  shows the sandbox starting so, on x86-64 and ARM64 runners (L81 in its
  [roadmap](https://github.com/bellbriar/harness/blob/main/docs/ROADMAP.md)).

A job that must run the same thing every time pins both: the Action by its
commit (`bellbriar/eval-action@<commit> # v1.0.0`), since `@v1` moves with
each 1.x release, and the image by its digest (`version: sha256:…`).

The harness runs as the runner's own user (root only on a runner that
itself runs as root). Docker's default security profile refuses the user
namespaces Chromium's sandbox needs, so in this container the browser runs
without its sandbox; each capture records that, and `--require-sandbox`
refuses such a run. Evaluate pages you do not control only in a job that
holds no secrets. The workspace is mounted at `/work`, its `.git` read-only,
and reports are written into it. The container shares the runner's network
(`--network host`), so a server the job started (`npm run preview &`) is
reachable at `http://127.0.0.1:PORT/`, and so is everything else the
runner can reach, for the pages the browser renders too.

License: Apache-2.0.
