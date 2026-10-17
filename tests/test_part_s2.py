"""Part S, round 2: the Python floor, and the findings of the scoped review
of what the freeze locks (SA) and of the release path (SB).

  S2-1   Python 3.11 or later, said the same everywhere: pyproject.toml,
         README, CHANGELOG and the CI matrix.
  SB-1   GitHub's Windows runners check text out with CRLF, and the suite
         compares bytes: .gitattributes turns conversion off, and the
         sdist carries it.
  SB-2   a run that builds the files again uploads nothing (PyPI keeps the
         first) but would attach and bake the new ones:
         tools/pypi_files.py holds the release to PyPI's files.
  SB-3   PREPUBLISH item 15 names README's quote of verify, and tags the
         merged commit as it stands on origin/main.
  SB-4   check_dist and image_check require the axe-core the package pins,
         and the image check that it ran.
  SB-5   build and setuptools pinned for the build; a final release needs
         the base image pinned by digest.
  SA-1   the equation a signature is checked by (the vectors and both
         verifiers: tests/test_canonicalization.py, TestSmallOrderParts).
  SA-2   verify and inspect count members in the records a capture writes
         inside its own (browser, viewport, wait, attribution, axe,
         narrow).
  SA-3   inspect refuses a file verify refuses for its signature block.
  SA-4   a domain in another spelling, and a page with no fetch member, are
         malformed; an empty port is no port (§9.5, §9.6, §9.8).
  SA-5   step references after the reorder; `pages[].fetch.redacted`.
  SA-6   EVIDENCE.md says which recorded URLs a verifier reads.
  SA-7   the pack's digest is a bound field (`pack_sha256`).
  SA-8   bellbriar-pack/1 is a draft, outside the freeze.
  SA-10  the report's `judged` is an object or null; `from_snapshot` can
         join versions; CHANGELOG says a changed format is 2.0.0; which
         lists of values are open.
"""
from __future__ import annotations

import base64
import contextlib
import hashlib
import io
import json
import re
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from bellbriar_harness import bundle as B                          # noqa: E402
from bellbriar_harness import evidence_cli                         # noqa: E402
from tests.bundle_body import BODY                                 # noqa: E402
from tests.test_examples import unpinned_base_images               # noqa: E402

KEY_HEX = hashlib.sha256(b"bellbriar-part-s2/1").hexdigest()


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _flat(path: str) -> str:
    return re.sub(r"\s+", " ", _text(path))


def _yaml(path: str) -> dict:
    try:
        import yaml
    except ImportError:
        raise unittest.SkipTest("PyYAML is not installed")
    return yaml.safe_load(_text(path))


def _private():
    return B.ed25519.Ed25519PrivateKey.from_private_bytes(
        bytes.fromhex(KEY_HEX))


def _public() -> str:
    return _private().public_key().public_bytes_raw().hex()


def _signed(bundle: dict, **statement) -> dict:
    """`bundle` signed with this module's key, its statement's bound values
    replaced by `statement` (a value of None removes the field), as a
    forger who holds a key would sign it."""
    priv = _private()
    kid = B.key_id_for(_public())
    bound = dict(B.bundle_bound_values(bundle))
    stmt = B.build_statement(bound, kid, "s2", B.SELF_SIGNED,
                             B.bundle_digest(bundle),
                             "2026-10-14T00:00:00+00:00")
    for field, value in statement.items():
        if value is None:
            stmt.pop(field, None)
        else:
            stmt[field] = value
    return dict(bundle, signature={
        "alg": "Ed25519", "context": B.STATEMENT_FORMAT, "key_id": kid,
        "statement": stmt, "signature_b64": B._sign_statement(stmt, priv)})


def _cli(*args) -> tuple[int, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = evidence_cli.main(list(args))
    return code, out.getvalue() + err.getvalue()


def _file(test, text: str) -> str:
    folder = tempfile.mkdtemp()
    test.addCleanup(__import__("shutil").rmtree, folder, True)
    path = Path(folder) / "bundle.json"
    path.write_text(text, encoding="utf-8")
    return str(path)


# ---------------------------------------------------------------------------
# S2-1  Python 3.11
# ---------------------------------------------------------------------------

class TestPythonFloor(unittest.TestCase):

    def test_said_the_same_everywhere(self):
        pyproject = _text("pyproject.toml")
        self.assertIn('requires-python = ">=3.11"', pyproject)
        versions = re.findall(r'"Programming Language :: Python :: (3\.\d+)"',
                              pyproject)
        self.assertEqual(versions, ["3.11", "3.12", "3.13", "3.14", "3.15"])
        self.assertIn("It needs Python 3.11 or later.", _flat("README.md"))
        self.assertIn("It needs Python 3.11 or later.", _flat("CHANGELOG.md"))
        matrix = _yaml(".github/workflows/bellbriar-eval.yml")[
            "jobs"]["test"]["strategy"]["matrix"]
        self.assertEqual(matrix["python-version"],
                         ["3.11", "3.12", "3.13", "3.14", "3.15"])
        self.assertGreaterEqual(sys.version_info[:2], (3, 11))

    def test_no_document_offers_3_10(self):
        for path in ("README.md", "CHANGELOG.md", "pyproject.toml",
                     "docs/MEASUREMENT-AND-EVIDENCE-GUIDE.md"):
            with self.subTest(path=path):
                self.assertNotRegex(_flat(path),
                                    r"Python 3\.10 or later|3\.10\+")


# ---------------------------------------------------------------------------
# SB-1  line endings
# ---------------------------------------------------------------------------

class TestLineEndings(unittest.TestCase):

    def test_no_conversion_anywhere(self):
        rules = [line for line in _text(".gitattributes").splitlines()
                 if line.strip() and not line.startswith("#")]
        # text=auto would convert the two web-platform-tests files that
        # hold CR on purpose.
        self.assertEqual(rules, ["* -text"])

    def test_the_sdist_carries_it(self):
        self.assertRegex(_text("MANIFEST.in"),
                         r"(?m)^include .*\.gitattributes(\s|$)")

    def test_what_is_compared_by_its_bytes_has_no_cr(self):
        for path in ("LICENSE", "fixtures/good.html",
                     "src/bellbriar_harness/vendor/axe-core/axe.min.js"):
            with self.subTest(path=path):
                self.assertNotIn(b"\r", (ROOT / path).read_bytes())


# ---------------------------------------------------------------------------
# SB-2  the release's files are the ones PyPI holds
# ---------------------------------------------------------------------------

def _opener(files=None, status=200, calls=None):
    def opener(url, timeout=30):
        if calls is not None:
            calls.append(url)
        if status == "down":
            raise urllib.error.URLError("no route to host")
        if status != 200:
            raise urllib.error.HTTPError(url, status, "status", {}, None)
        return io.BytesIO(json.dumps({"urls": [
            {"filename": n, "digests": {"sha256": d}}
            for n, d in (files or {}).items()]}).encode("utf-8"))
    return opener


class TestPyPIFiles(unittest.TestCase):

    def setUp(self):
        import pypi_files
        self.P = pypi_files
        self.dist = Path(tempfile.mkdtemp())
        self.addCleanup(__import__("shutil").rmtree, self.dist, True)
        self.files = {}
        for name, data in (("bellbriar_harness-1.0.0-py3-none-any.whl", b"w"),
                           ("bellbriar_harness-1.0.0.tar.gz", b"s")):
            (self.dist / name).write_bytes(data)
            self.files[name] = hashlib.sha256(data).hexdigest()

    def run_it(self, *args, opener):
        sleeps = []
        err = io.StringIO()
        with contextlib.redirect_stderr(err), \
                contextlib.redirect_stdout(io.StringIO()):
            code = self.P.main([*args, "1.0.0", str(self.dist)], opener=opener,
                               sleep=sleeps.append)
        return code, err.getvalue(), sleeps

    def test_a_first_upload_goes_ahead(self):
        calls = []
        code, _, sleeps = self.run_it(opener=_opener(status=404, calls=calls))
        self.assertEqual((code, sleeps), (0, []))
        self.assertEqual(calls, [
            "https://pypi.org/pypi/bellbriar-harness/1.0.0/json"])

    def test_the_same_files_pass(self):
        for args in ((), ("--all",)):
            with self.subTest(args=args):
                code, err, _ = self.run_it(*args, opener=_opener(self.files))
                self.assertEqual(code, 0, err)

    def test_files_built_again_stop_the_run(self):
        other = dict(self.files)
        other["bellbriar_harness-1.0.0.tar.gz"] = "0" * 64
        for args in ((), ("--all",)):
            with self.subTest(args=args):
                code, err, _ = self.run_it(*args, opener=_opener(other))
                self.assertEqual(code, 1)
                self.assertIn("bellbriar_harness-1.0.0.tar.gz is not the file "
                              "PyPI holds", err)
                self.assertIn("Re-run only the failed jobs", err)

    def test_after_the_upload_every_file_must_be_there(self):
        """With --all, a file PyPI does not list is asked for again (its
        record can lag), then the run stops."""
        partial = {k: v for k, v in self.files.items() if k.endswith(".whl")}
        code, err, sleeps = self.run_it("--all", opener=_opener(partial))
        self.assertEqual(code, 1)
        self.assertIn("bellbriar_harness-1.0.0.tar.gz is not on PyPI", err)
        self.assertEqual(sleeps, [self.P.WAIT_S] * (self.P.TRIES - 1))
        code, _, sleeps = self.run_it(opener=_opener(partial))
        self.assertEqual((code, sleeps), (0, []))

    def test_pypi_that_cannot_be_read_stops_the_run(self):
        for status in (500, 403, "down"):
            with self.subTest(status=status):
                code, err, _ = self.run_it(opener=_opener(status=status))
                self.assertEqual(code, 2, err)

    def test_an_empty_folder_is_no_release(self):
        for f in self.dist.iterdir():
            f.unlink()
        code, err, _ = self.run_it(opener=_opener(self.files))
        self.assertEqual(code, 1)
        self.assertIn("there are no files", err)

    def test_the_workflow_checks_before_each_use(self):
        wf = _yaml(".github/workflows/release.yml")["jobs"]

        def index(job, test):
            steps = wf[job]["steps"]
            return next(i for i, s in enumerate(steps) if test(s))
        def uses(name):
            return lambda s: name in (s.get("uses") or "")

        def check(every):
            return lambda s: ("tools/pypi_files.py" in (s.get("run") or "")
                              and ("--all" in s["run"]) is every)
        self.assertLess(index("pypi", check(False)),
                        index("pypi", uses("pypa/gh-action-pypi-publish")))
        self.assertEqual(wf["pypi"]["permissions"],
                         {"contents": "read", "id-token": "write"})
        # S5-5: the images are built from the run's files before PyPI;
        # their version tag waits for PyPI to hold those files.
        self.assertLess(index("image", check(True)),
                        index("image", lambda s: s.get("id") == "index"))
        run = wf["release"]["steps"][index("release", check(True))]["run"]
        self.assertLess(run.index("tools/pypi_files.py --all"),
                        run.index("gh release create"))
        for job in ("pypi", "image", "release"):
            step = wf[job]["steps"][index(job, lambda s: "pypi_files" in (
                s.get("run") or ""))]
            self.assertEqual(step["env"]["VERSION"],
                             "${{ needs.build.outputs.version }}")


# ---------------------------------------------------------------------------
# SB-3  the rehearsal's steps
# ---------------------------------------------------------------------------

class TestRehearsalSteps(unittest.TestCase):

    def test_item_15(self):
        item = _flat("PREPUBLISH.md").split("15. **Rehearse the release**", 1)[
            1].split("16. **", 1)[0]
        self.assertIn('README\'s quote of what `verify` says of the example '
                      '("Verify something in thirty seconds"), which names '
                      'the version twice', item)
        self.assertIn("git fetch origin && git tag -a v1.0.0rc1 -m v1.0.0rc1 "
                      "origin/main && git push origin v1.0.0rc1`, as "
                      "bellbriar-ops, an annotated tag, not a signed one "
                      "(L147)", item)
        self.assertIn("`pack_sha256`", item)


# ---------------------------------------------------------------------------
# SB-4  the pinned axe-core, and that it ran
# ---------------------------------------------------------------------------

class TestTheAxeCorePinned(unittest.TestCase):

    def test_check_dist_compares_the_wheel_copy(self):
        import check_dist as CD
        from tests.test_part_r4 import TestCheckDist
        maker = TestCheckDist()
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(__import__("shutil").rmtree, folder, True)
        with mock.patch.object(CD, "tracked", return_value=None):
            maker.make(folder)
            self.assertEqual(CD.check(folder), [])
            with mock.patch.object(CD, "_axe_sha256", return_value="0" * 64):
                problems = " ".join(CD.check(folder))
        self.assertIn("axe.min.js", problems)

    def _image_check(self, axe: dict) -> tuple[int, str]:
        import image_check as IC
        version = IC._version()

        def run(cmd, **kwargs):
            done = mock.Mock(stdout="", stderr="", returncode=0)
            if cmd[:2] == ["docker", "version"]:
                return done
            if "--version" in cmd:
                done.stdout = f"bellbriar-harness {version}\n"
            elif "fixtures/good.html" in cmd:
                out = next(v.split(":/out")[0] for v in cmd
                           if v.endswith(":/out"))
                browser = {"name": "chromium", "version": "141",
                           "sandbox": True}
                (Path(out) / "good.json").write_text(json.dumps({"pages": [{
                    "fetch": {"mode": "rendered", "axe": axe,
                              "browser": browser}}]}), encoding="utf-8")
            elif "fixtures/bad.html" in cmd:
                done.returncode = 1
            return done
        err = io.StringIO()
        with mock.patch.object(IC.shutil, "which",
                               return_value="/bin/docker"), \
                mock.patch.object(IC.subprocess, "run", side_effect=run), \
                contextlib.redirect_stderr(err), \
                contextlib.redirect_stdout(io.StringIO()):
            code = IC.main(["ghcr.io/bellbriar/harness:test"])
        return code, err.getvalue()

    def test_image_check_requires_the_run_and_the_copy(self):
        import image_check as IC
        pinned = IC._axe_sha256()
        from bellbriar_harness.axe import AXE_SHA256
        self.assertEqual(pinned, AXE_SHA256)
        self.assertEqual(self._image_check({"ran": True, "sha256": pinned}),
                         (0, ""))
        for axe in ({"ran": False, "sha256": pinned,
                     "reason": "axe-core was not run"},
                    {"ran": True, "sha256": "0" * 64}, {}):
            with self.subTest(axe=axe):
                code, err = self._image_check(axe)
                self.assertEqual(code, 1)
                self.assertIn("not the copy the package pins", err)


# ---------------------------------------------------------------------------
# SB-5  what builds the release is pinned
# ---------------------------------------------------------------------------

class TestBuildPins(unittest.TestCase):

    def test_build_and_setuptools_are_pinned(self):
        pins = [line for line in
                _text("tools/build-constraints.txt").splitlines()
                if line.strip() and not line.startswith("#")]
        self.assertEqual([p.split("==")[0] for p in pins],
                         ["build", "setuptools"])
        for pin in pins:
            self.assertRegex(pin, r"\A[a-z]+==\d+(\.\d+)+\Z")
        build = _yaml(".github/workflows/release.yml")["jobs"]["build"]
        self.assertEqual(build["env"]["PIP_CONSTRAINT"],
                         "${{ github.workspace }}/tools/build-constraints.txt")

    def test_the_pinned_setuptools_is_one_the_build_accepts(self):
        try:
            from packaging.requirements import Requirement
        except ImportError:
            raise unittest.SkipTest("packaging is not installed")
        import tomllib
        requires = tomllib.loads(_text("pyproject.toml"))["build-system"][
            "requires"]
        pins = dict(line.split("==") for line in
                    _text("tools/build-constraints.txt").splitlines()
                    if "==" in line and not line.startswith("#"))
        for req in map(Requirement, requires):
            with self.subTest(requirement=str(req)):
                self.assertIn(req.name, pins)
                self.assertIn(pins[req.name], req.specifier)

    def test_a_final_release_needs_the_base_image_digest(self):
        digest = "@sha256:" + "a" * 64
        self.assertEqual(unpinned_base_images("FROM python:3.12\n"),
                         ["python:3.12"])
        self.assertEqual(
            unpinned_base_images(f"FROM python:3.12{digest}\n"), [])
        self.assertEqual(unpinned_base_images(
            f"FROM --platform=linux/amd64 python:3.12{digest} AS base\n"), [])
        self.assertEqual(unpinned_base_images(
            f"FROM a{digest}\nFROM b:1\n"), ["b:1"])
        self.assertEqual(unpinned_base_images("# FROM a\n"),
                         ["(no FROM line)"])
        check = _text("tests/test_examples.py").split(
            "def test_nothing_is_pending_for_a_release", 1)[1].split(
                "\n    def ", 1)[0]
        self.assertIn("unpinned_base_images(", check)


# ---------------------------------------------------------------------------
# SA-2  the records inside a capture record
# ---------------------------------------------------------------------------

class TestRecordsInsideACapture(unittest.TestCase):

    def test_members_there_are_counted(self):
        url = "http://127.0.0.1:8123/a"
        record = {"final_url": url,
                  "browser": {"name": "chromium", "audited": True},
                  "viewport": {"width": 1280, "height": 800, "dpr": 2},
                  "wait": {"strategy": "quiet", "approved_by": "x"},
                  "attribution": {"policy": "p", "signed": True},
                  "axe": {"ran": True, "certified_by": "Deque Systems"},
                  "narrow": {"settled": True, "passed": True,
                             "viewport": {"width": 320, "zoom": 4}}}
        bundle = {**BODY, "pages": [{"path": "a.html", "fetch": record}]}
        count, places = B.foreign_members(bundle)
        self.assertEqual(count, 7)
        self.assertEqual(places, [f"pages[0].fetch.{p}" for p in (
            "browser", "viewport", "wait", "attribution", "axe", "narrow",
            "narrow.viewport")])
        clean = json.loads(json.dumps(bundle))
        for part in ("browser", "viewport", "wait", "attribution", "axe",
                     "narrow"):
            for k in list(clean["pages"][0]["fetch"][part]):
                if k not in B.RECORD_MEMBERS[f"pages[].fetch.{part}"]:
                    del clean["pages"][0]["fetch"][part][k]
        del clean["pages"][0]["fetch"]["narrow"]["viewport"]["zoom"]
        self.assertEqual(B.foreign_members(clean), (0, []))

    def test_verify_names_them(self):
        bundle = {**BODY, "pages": [{"path": "a.html", "fetch": {
            "final_url": "http://127.0.0.1:8123/a",
            "axe": {"ran": True, "certified_by": "Deque Systems"}}}]}
        ok, reason = B.verify_bundle(_signed(bundle), _public())
        self.assertTrue(ok, reason)
        self.assertIn("1 member it does not define (in pages[0].fetch.axe)",
                      reason)
        self.assertNotIn("Deque", reason)


# ---------------------------------------------------------------------------
# SA-3  inspect reads the signature block as verify does
# ---------------------------------------------------------------------------

class TestInspectReadsTheWholeFile(unittest.TestCase):

    def test_a_lone_surrogate_in_the_statement(self):
        text = json.dumps(_signed(dict(BODY)), ensure_ascii=False)
        self.assertEqual(text.count('"signer": "s2"'), 1)
        broken = _file(self, text.replace('"signer": "s2"',
                                          '"signer": "s2\\ud800"'))
        code, out = _cli("verify", broken, "--public-key", _public())
        self.assertEqual(code, 2, out)
        code, out = _cli("inspect", broken)
        self.assertEqual(code, 2, out)
        self.assertIn("surrogate", out)
        code, out = _cli("inspect", _file(self, text))
        self.assertEqual(code, 0, out)


# ---------------------------------------------------------------------------
# SA-4  one spelling of a domain; every page has a fetch member
# ---------------------------------------------------------------------------

class TestMalformedAtTheDomainAndThePage(unittest.TestCase):

    def test_a_domain_in_another_spelling(self):
        for domain, code in (("example.com", 0), ("WWW.Example.com", 2),
                             ("", 2), ("example.com.", 2),
                             ("cornerb\u0430kery.example", 2)):
            with self.subTest(domain=domain):
                bundle = dict(BODY, domain=domain)
                try:
                    text = json.dumps(_signed(bundle), ensure_ascii=False)
                except B.MalformedBundle:
                    # Signed as a forger would: the statement says what the
                    # forger likes, the verifier reads the body.
                    text = json.dumps(_forged(bundle), ensure_ascii=False)
                got, out = _cli("verify", _file(self, text), "--public-key",
                                _public())
                self.assertEqual(got, code, out)
                if code:
                    self.assertIn("one spelling", out)

    def test_a_page_with_no_fetch_member(self):
        bundle = dict(BODY, pages=[{"path": "a.html"}])
        with self.assertRaises(B.MalformedBundle) as caught:
            B.bundle_bound_values(bundle)
        self.assertIn("pages[0] has no fetch member", str(caught.exception))
        B.bundle_bound_values(dict(BODY, pages=[{"path": "a.html",
                                                 "fetch": None}]))

    def test_an_empty_port_is_no_port(self):
        self.assertEqual(B.url_host("https://example.com:/"), "example.com")
        self.assertIsNone(B.url_host("https://example.com:x/"))


def _forged(bundle: dict) -> dict:
    priv = _private()
    kid = B.key_id_for(_public())
    with mock.patch.object(B, "check_body"):
        digest = B.bundle_digest(bundle)
    bound = {f: bundle.get(f) for f in ("bundle_format", "domain")}
    stmt = B.build_statement(bound, kid, "s2", B.SELF_SIGNED, digest,
                             "2026-10-14T00:00:00+00:00")
    return dict(bundle, signature={
        "alg": "Ed25519", "context": B.STATEMENT_FORMAT, "key_id": kid,
        "statement": stmt, "signature_b64": B._sign_statement(stmt, priv)})


# ---------------------------------------------------------------------------
# SA-5, SA-6, SA-8, SA-10  what the documents say
# ---------------------------------------------------------------------------

class TestTheDocuments(unittest.TestCase):

    DOCS = ("README.md", "docs/CANONICALIZATION.md", "docs/EVIDENCE.md",
            "docs/MEASUREMENT-AND-EVIDENCE-GUIDE.md", "docs/REPORT.md")

    def test_steps_and_members_named_as_they_are(self):
        """SA-5: binding is §6 step 5 and the host step 6, since the key
        and signature moved first; what was redacted is a page's record."""
        for path in self.DOCS:
            with self.subTest(path=path):
                text = _flat(path)
                self.assertNotIn("§6 step 4", text)
                self.assertNotRegex(text, r"(?<!pages\[\]\.)`fetch\.redacted`")
        spec = _flat("docs/CANONICALIZATION.md")
        self.assertIn("value (§6 step 5).", spec)
        self.assertIn("### 9.4 Host and domain (§6 step 6)",
                      _text("docs/CANONICALIZATION.md"))
        for path in ("src/bellbriar_harness/bundle.py",
                     "tools/make_canonicalization_vectors.py",
                     "tests/js/canonical_check.mjs"):
            with self.subTest(path=path):
                self.assertNotIn("§6 step 4", _text(path))

    def test_which_urls_a_verifier_reads(self):
        """SA-6: verify reads the final URLs, page names and snapshot
        names; the other URLs a capture record holds are the producer's."""
        text = _flat("docs/EVIDENCE.md")
        self.assertNotIn("and no recorded URL carries a user name", text)
        self.assertIn("no final URL, page name or snapshot name carries a "
                      "user name", text)
        self.assertIn("which `verify` does not check", text)

    def test_the_pack_format_is_a_draft(self):
        """SA-8: 1.0 ships no packs, and §7 does less than §6."""
        self.assertIn("`bellbriar-pack/1` is a draft, which that "
                      "publication did not freeze",
                      _flat("docs/CANONICALIZATION.md"))
        self.assertIn("`bellbriar-pack/1` is a draft, outside this promise",
                      _flat("CHANGELOG.md"))
        self.assertIn("`bellbriar-pack/1` stays a draft, outside the freeze",
                      _flat("PREPUBLISH.md"))

    def test_types_values_and_versions(self):
        """SA-10."""
        report = _flat("docs/REPORT.md")
        self.assertIn("| `judged` | object or null | Null in 1.0.", report)
        schema = json.loads(_text("docs/bellbriar-report-1.schema.json"))
        self.assertEqual(sorted(schema["properties"]["judged"]["type"]),
                         ["null", "object"])
        self.assertIn('several joined by `" and "`', report)
        from bellbriar_harness.engine import _axe_versions
        pages = [mock.Mock(axe_version="4.11.0"),
                 mock.Mock(axe_version="4.10.3")]
        self.assertEqual(_axe_versions(pages), "4.10.3 and 4.11.0")
        changelog = _flat("CHANGELOG.md")
        self.assertIn("Any other change takes a new format string, which "
                      "only 2.0.0 may bring", changelog)
        self.assertIn("A list of the values a record's member takes is "
                      "closed unless `docs/REPORT.md` marks it *open*",
                      _flat("docs/CANONICALIZATION.md"))
        self.assertIn("*Open*", _text("docs/REPORT.md"))


# ---------------------------------------------------------------------------
# SA-7  the pack's digest is bound
# ---------------------------------------------------------------------------

class TestThePackDigestIsBound(unittest.TestCase):

    PACK = {"name": "wcag", "version": "1.0.0", "manifest_sha256": "ab" * 32,
            "files": 1, "signature_verified": False}

    def test_a_bound_field(self):
        self.assertEqual(B.BOUND_FIELDS, (
            "bundle_format", "domain", "host", "pack", "pack_version",
            "pack_sha256", "rulebook_version", "rulebook_sha256"))
        self.assertIn("pack_sha256", B.STATEMENT_FIELDS)
        self.assertEqual(B.bundle_bound_values(dict(BODY, pack=self.PACK))[
            "pack_sha256"], "ab" * 32)
        self.assertIsNone(B.bundle_bound_values(dict(BODY))["pack_sha256"])

    def test_verify_compares_it(self):
        with_pack = dict(BODY, pack=self.PACK)
        ok, reason = B.verify_bundle(_signed(with_pack), _public())
        self.assertTrue(ok, reason)
        for label, value in (("another digest", "cd" * 32),
                             ("none, as statements before Part S", None)):
            with self.subTest(statement=label):
                ok, reason = B.verify_bundle(
                    _signed(with_pack, pack_sha256=value), _public())
                self.assertFalse(ok)
                self.assertIn("pack_sha256", reason)
        # A statement without it covers a bundle with no pack, as the worked
        # example's does until its re-signing (PENDING_STATEMENT_FIELDS).
        ok, reason = B.verify_bundle(_signed(dict(BODY), pack_sha256=None),
                                     _public())
        self.assertTrue(ok, reason)

    def test_the_spec_and_the_mirror_list_it(self):
        spec = _text("docs/CANONICALIZATION.md")
        self.assertIn("| `pack_sha256` | `bundle.pack.manifest_sha256`", spec)
        self.assertIn("The last eight are the **bound fields**", spec)
        js = _text("tests/js/canonical_check.mjs")
        self.assertIn('"pack_sha256", "rulebook_version", '
                      '"rulebook_sha256"]', js)
        self.assertIn("pack_sha256: pack.manifest_sha256 ?? null", js)

    def test_the_example_binds_it(self):
        """Re-signed for 1.0.0rc1: its statement binds the pack's digest
        (null: 1.0 pins no pack), and its attestation names it."""
        from tests import test_examples as TE
        self.assertEqual(TE.PENDING_STATEMENT_FIELDS, set())
        data = json.loads(
            _text("examples/evidence/signed-bundle-example.json"))
        self.assertIn("pack_sha256", data["signature"]["statement"])
        self.assertIsNone(data["signature"]["statement"]["pack_sha256"])
        self.assertIsNone(data["pack"])
        self.assertIn("pack version, pack digest, rulebook version",
                      data["attestation"])


if __name__ == "__main__":
    unittest.main()
