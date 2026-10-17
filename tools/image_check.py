#!/usr/bin/env python3
"""Run the container image on the fixtures (R4A-4, R4A-3):

    python tools/image_check.py IMAGE [--pull]

The release runs this on the image it built before anything is published,
and again on the published image, pulled with no credentials (--pull): so
the image starts, names this version, renders a page in its own browser,
and gates as the package does, and anyone can pull it. The CI runs it on
every change.

Each run is the one the README and the Action use: the image's own user
mapped to this one, a folder mounted at /work. It checks that:

* `--version` names pyproject.toml's version;
* fixtures/good.html, rendered, passes the gate (exit 0), and its capture
  says it was rendered, by Chromium, and whether its sandbox was on, and
  that axe-core ran there, the copy whose SHA-256 the package pins
  (`AXE_SHA256`): a page's static rules pass it without axe-core too;
* fixtures/bad.html, rendered, fails it (exit 1);
* the run names no library version outside the ranges the release
  declares.

It also says whether Chromium's sandbox starts when the container has
Playwright's seccomp profile (docker/seccomp_profile.json, which the
Action's `sandbox: required` passes): that depends on the host allowing
unprivileged user namespaces, so it is reported, not required.

Exit 0 when all hold, 1 when one does not, 2 when docker cannot run.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _version() -> str:
    import re
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    return re.search(r'^version = "([^"]+)"', text, re.M).group(1)


def _axe_sha256() -> str:
    """The SHA-256 of the axe-core the package pins (axe.AXE_SHA256)."""
    import re
    text = (ROOT / "src" / "bellbriar_harness" / "axe.py").read_text(
        encoding="utf-8")
    return re.search(r'^AXE_SHA256 = "([0-9a-f]{64})"', text, re.M).group(1)


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    pull = "--pull" in args
    if pull:
        args.remove("--pull")
    if len(args) != 1 or args[0].startswith("-"):
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    image = args[0]
    if shutil.which("docker") is None:
        print("image_check: docker is not installed", file=sys.stderr)
        return 2
    daemon = subprocess.run(["docker", "version", "--format",
                             "{{.Server.Version}}"], capture_output=True,
                            text=True)
    if daemon.returncode != 0:
        print(f"image_check: docker cannot run here: "
              f"{daemon.stderr.strip()[-500:]}", file=sys.stderr)
        return 2
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as out:
        env = dict(os.environ)
        if pull:
            # No credentials: what anyone can pull. A private package fails
            # here (it takes its repository's visibility: PREPUBLISH.md item
            # 14), and so do a missing tag, the network or a rate limit, so
            # docker's own words are shown (R4D-10).
            env["DOCKER_CONFIG"] = out
            got = subprocess.run(["docker", "pull", image], env=env,
                                 capture_output=True, text=True)
            if got.returncode != 0:
                print(f"image_check: {image} cannot be pulled without "
                      f"credentials: {got.stderr.strip()[-800:]} (a private "
                      "package must be made public: PREPUBLISH.md)",
                      file=sys.stderr)
                return 1
        user = (f"{os.getuid()}:{os.getgid()}" if hasattr(os, "getuid")
                else "1000:1000")
        base = ["docker", "run", "--rm", "--init", "--shm-size=2g",
                "--user", user, "-e", "HOME=/tmp",
                "-v", f"{ROOT / 'fixtures'}:/work/fixtures:ro",
                "-v", f"{out}:/out", "-w", "/work", image]

        def run(*extra):
            return subprocess.run(base + list(extra), env=env,
                                  capture_output=True, text=True,
                                  timeout=600)
        version = run("--version")
        if version.returncode == 125:
            # docker's own failure, not the image's (R4D-10).
            print(f"image_check: docker could not run {image}: "
                  f"{version.stderr.strip()[-800:]}", file=sys.stderr)
            return 2
        platform = subprocess.run(["docker", "image", "inspect", "--format",
                                   "{{.Os}}/{{.Architecture}}", image],
                                  env=env, capture_output=True, text=True)
        if platform.returncode == 0:
            print(f"image_check: {image} is {platform.stdout.strip()}")
        if version.stdout.strip() != f"bellbriar-harness {_version()}":
            problems.append(f"--version says {version.stdout.strip()!r} "
                            f"(exit {version.returncode}), not "
                            f"bellbriar-harness {_version()}: "
                            f"{version.stderr.strip()[-500:]}")
        good = run("fixtures/good.html", "--render", "--fail-on", "tier1",
                   "--json", "/out/good.json")
        if "library versions" in good.stderr:
            # The image's pins lie within the release's ranges (L134).
            problems.append("the image runs library versions outside the "
                            "ranges the release declares: "
                            f"{good.stderr.strip()[-600:]}")
        if good.returncode != 0:
            problems.append(f"fixtures/good.html, rendered: exit "
                            f"{good.returncode}, not 0: "
                            f"{good.stderr.strip()[-800:]}")
        else:
            report = json.loads((Path(out) / "good.json").read_text(
                encoding="utf-8"))
            fetch = report["pages"][0].get("fetch") or {}
            browser = fetch.get("browser") or {}
            axe = fetch.get("axe") or {}
            if fetch.get("mode") != "rendered" or \
                    browser.get("name") != "chromium":
                problems.append("fixtures/good.html was not rendered in "
                                f"Chromium: {json.dumps(fetch)[:500]}")
            elif axe.get("ran") is not True or \
                    axe.get("sha256") != _axe_sha256():
                problems.append("axe-core did not run on fixtures/good.html, "
                                "or not the copy the package pins: "
                                f"{json.dumps(axe)[:500]}")
            else:
                print(f"image_check: rendered by Chromium "
                      f"{browser.get('version')}, sandbox "
                      f"{'on' if browser.get('sandbox') else 'off'}")
        bad = run("fixtures/bad.html", "--render", "--fail-on", "tier1")
        if bad.returncode != 1:
            problems.append(f"fixtures/bad.html, rendered: exit "
                            f"{bad.returncode}, not 1: "
                            f"{bad.stderr.strip()[-800:]}")
        # The sandbox under Playwright's seccomp profile: reported only.
        profile = ROOT / "docker" / "seccomp_profile.json"
        sandboxed = subprocess.run(
            base[:4] + ["--security-opt", f"seccomp={profile}"] + base[4:]
            + ["fixtures/good.html", "--render", "--require-sandbox",
               "--fail-on", "tier1"],
            env=env, capture_output=True, text=True, timeout=600)
        print("image_check: with docker/seccomp_profile.json, Chromium's "
              "sandbox " + ("started" if sandboxed.returncode == 0 else
                            f"did not start (exit {sandboxed.returncode}: "
                            "the host may not allow unprivileged user "
                            "namespaces)"))
    for p in problems:
        print(f"image_check: {p}", file=sys.stderr)
    if problems:
        return 1
    print(f"image_check: {image} starts, renders, and gates as it should")
    return 0


if __name__ == "__main__":
    sys.exit(main())
