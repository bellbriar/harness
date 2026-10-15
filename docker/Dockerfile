# The harness with Python, Chromium and fonts preinstalled (A11, N28):
# ghcr.io/bellbriar/harness:<version>, built by .github/workflows/release.yml
# from the release's own wheel (dist/), never from a laptop.
#
#   docker run --rm --init --ipc=host --user "$(id -u):$(id -g)" \
#     -v "$PWD:/work" ghcr.io/bellbriar/harness:1 dist --render --html report.html
#
# It runs as pwuser, an ordinary user, or as the --user you give it
# ("$(id -u):$(id -g)" is root only when you are). Even so, Docker's
# default seccomp profile refuses the user namespaces Chromium's sandbox
# needs, so the browser runs without it here unless the container gets a
# profile that allows them (Playwright publishes one) on a host that
# allows them too (R4A-2). Each capture records whether the sandbox was on,
# and --require-sandbox refuses a run without it (D9).

# Playwright's Python image: Ubuntu 24.04, Chromium and the libraries and
# fonts it needs, and an ordinary user, pwuser; for x86-64 and ARM64. The
# Playwright package installed below is docker/requirements.txt's, which
# must be this image's version, whose browsers it holds
# (tests/test_part_r4.py checks). A release pins the image's digest too
# (PREPUBLISH.md): a tag can be moved, a digest cannot. Dependabot proposes
# new versions of both.
FROM mcr.microsoft.com/playwright/python:v1.63.0-noble@sha256:72bd171a9ffc2b4b59532aaa6210e21014d07093120dc25528870c0b840da1f0

COPY docker/requirements.txt /tmp/requirements.txt
COPY dist/ /tmp/dist/
RUN wheel="$(ls /tmp/dist/bellbriar_harness-*-py3-none-any.whl)" \
 && python3 -m pip install --no-cache-dir --break-system-packages \
      --constraint /tmp/requirements.txt "${wheel}[browser]" \
 && rm -rf /tmp/dist /tmp/requirements.txt \
 && bellbriar-eval --version

# A home any user can write to, for `docker run --user "$(id -u):$(id -g)"`
# (needed to write reports into a mounted folder you own).
ENV HOME=/tmp
USER pwuser
WORKDIR /work
ENTRYPOINT ["bellbriar-eval"]
CMD ["--help"]
