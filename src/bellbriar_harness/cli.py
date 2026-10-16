"""bellbriar-eval — run the harness against HTML: files and folders, a build
rendered on loopback (--render), or pages fetched from a site (--url,
repeatable; --urls FILE; --sitemap URL).

A run of many pages gives one report and one bundle, for one host: the
bundle's `fetch` is the run's record of what it fetched, and each page's
capture record is its own `pages[i].fetch`. Every finding about an element
carries a locator (locator.py).

Evidence: --bundle writes an evidence bundle, and --sign-key (or
--sign-key-env) signs it self-signed with a key of your own. Remote
signing, packs and the judge are not in 1.0 (the ship list's L2–L4); their
code stays in the repository, and none of it is reachable from here.

Exit codes: 0 clean per --fail-on policy; 1 gate failed; 2 usage/run error,
including a run in which no page could be evaluated (every page a
client-rendered app shell) and one that executed no Tier-1 rule.
The CI gate is deterministic-only by design.
"""
from __future__ import annotations

import argparse
import contextvars
import functools
import json
import os
import re
import stat
import sys
import urllib.parse
from pathlib import Path

from . import __version__
from .coverage_text import BUILD_SENTENCE, BUILD_STATIC_SENTENCE
from .engine import (RENDERED_SENTENCE, SERVER_ONLY_SENTENCE,
                     coverage_sentence, layer_records, load_rulebook,
                     run_header, run_page, run_paths,
                     validate_rulebook)
from .model import BLOCKER, FAIL, MINOR, MODERATE, NEEDS_REVIEW, SERIOUS
from .report_html import render
from .scoring import score_site


def _pct(x: float | None) -> str:
    """None means nothing was measured. An empty denominator is an undefined
    score, not a perfect one — see scoring.py."""
    return "n/a" if x is None else f"{x:.1%}"


#: What a directory walk evaluates, in any case: export tools write
#: `INDEX.HTM` as readily as `index.html`.
HTML_SUFFIXES = (".html", ".htm", ".xhtml", ".xht", ".xhtm")


def _collect(paths: list[str]) -> list[tuple[Path, str]]:
    """(file, the name the run records for it) for each file argument, and
    for each HTML file under each directory argument, sorted. The name is
    bundle.recorded_path: never absolute, never with `..`."""
    from .bundle import recorded_path
    out: list[tuple[Path, str]] = []
    unfollowed: list[str] = []
    for p in paths:
        pp = Path(p)
        if pp.is_dir():
            entries = list(pp.rglob("*"))
            found = sorted(f for f in entries
                           if f.suffix.lower() in HTML_SUFFIXES and f.is_file())
            # A walk does not follow a link to a folder (it could lead out
            # of the folder, or round in a circle); it says so (R3D-8).
            unfollowed += sorted(recorded_path(f, p) for f in entries
                                 if f.is_symlink() and f.is_dir())
        elif pp.is_file():
            found = [pp]
        elif os.path.islink(p):
            raise FileNotFoundError(f"path not found: {p} links to nothing")
        elif os.path.lexists(p):
            raise FileNotFoundError(f"not a file or folder: {p}")
        else:
            raise FileNotFoundError(f"path not found: {p}")
        out.extend((f, recorded_path(f, p)) for f in found)
    if unfollowed:
        print(f"[bellbriar] note: {len(unfollowed)} linked folder(s) were "
              f"not followed ({unfollowed[0]}"
              + (", …" if len(unfollowed) > 1 else "") + "): name one on "
              "its own to evaluate it.", file=sys.stderr)
    # A file named twice (`dist dist/index.html`) is one page, evaluated
    # once, under the first name it was given (R3A-2). A link to a file is
    # a name of its own, which a server serves at its own address, so it
    # stays a page of its own (R3C-5).
    once: dict = {}
    listings: dict = {}
    again = []
    for f, name in out:
        key = _entry(f, listings)
        if key in once:
            again.append(once[key][1])
        else:
            once[key] = (f, name)
    if again:
        kept = sorted(set(again))
        print(f"[bellbriar] note: {len(kept)} file(s) named more than once "
              f"are evaluated once, under the first name given ({kept[0]}"
              + (", …" if len(kept) > 1 else "") + ").", file=sys.stderr)
    return _distinct(list(once.values()))


def _entry(f: Path, listings: dict) -> tuple:
    """The directory entry `f` names: its folder, as the file system
    identifies it, and its name there as the folder lists it. Two names
    for one entry (`dist` and `dist/index.html`, `./a.html` and `a.html`,
    `A.html` for `a.html` where the file system ignores case) give one
    key; a symbolic or hard link is an entry of its own. `listings` caches
    each folder's names."""
    import unicodedata
    folder = f.parent
    try:
        st = os.stat(folder)
        # No inode (0) on some file systems (FAT): its real path instead.
        where: tuple = ((st.st_dev, st.st_ino) if st.st_ino else
                        (os.path.normcase(os.path.realpath(folder)),))
    except OSError:
        where = (os.path.abspath(folder),)
    names = listings.get(where)
    if names is None:
        try:
            names = set(os.listdir(folder))
        except OSError:
            names = set()
        listings[where] = names
    name = f.name
    if name not in names:
        # Found under another spelling: a file system that ignores case,
        # or one that stores another Unicode normalization (macOS).
        def fold(n: str) -> str:
            return unicodedata.normalize("NFC", n).casefold()
        same = [n for n in names if fold(n) == fold(name)]
        if len(same) == 1:
            name = same[0]
    return where + (name,)


def _home_folder(parts: tuple, j: int) -> bool:
    """Is parts[j] a home directory (bundle.home_folder)?"""
    from .bundle import home_folder
    return home_folder(parts, j)


def _distinct(pairs: list[tuple[Path, str]],
              fixed: int = 0) -> list[tuple[Path, str]]:
    """Two different files recorded under one name (`index.html` from
    /a/dist and from /a/dist/sub) get as many of their own parent folders
    as tell them apart (`dist/index.html`, `sub/index.html`), never the
    root, a drive or a home directory. A relative path recorded as given
    keeps its name while it can. Files told apart only by a home
    directory, or not at all by their folders, are numbered instead
    (`~1/site/index.html`, `~2/site/index.html`), given names too, so the
    names always end distinct (R5D-1). The same file named twice keeps one
    name. The first `fixed` pairs keep their names: the files they clash
    with take other ones (a --render run's served files beside its pages,
    R5D-10). ValueError if no names can be found."""
    from pathlib import PurePath
    absolute = [os.path.abspath(f) for f, _ in pairs]
    names = [n for _, n in pairs]
    given = [i < fixed or (not PurePath(f).anchor
                           and ".." not in PurePath(f).parts)
             for i, (f, _) in enumerate(pairs)]
    # Each round grows a clashing name by one folder or numbers it, so the
    # deepest path bounds the rounds needed (R5E-11: a cap of 64 refused
    # files 66 folders deep).
    rounds = 2 + max((len(PurePath(a).parts) for a in absolute), default=0)
    for _ in range(rounds):
        groups: dict[str, list[int]] = {}
        for i, n in enumerate(names):
            groups.setdefault(n, []).append(i)
        clashes = [ix for ix in groups.values()
                   if len({absolute[i] for i in ix}) > 1]
        if not clashes:
            return [(f, n) for (f, _), n in zip(pairs, names)]
        grown = False
        for ix in clashes:
            for i in ix:
                parts = PurePath(absolute[i]).parts      # parts[0]: the root
                k = len(PurePath(names[i]).parts)
                j = len(parts) - k - 1                   # the folder to add
                if given[i] or j < 1 or _home_folder(parts, j):
                    continue
                names[i] = _grown_name(PurePath(*parts[j:]).as_posix())
                grown = True
        if not grown:
            for ix in clashes:
                order: dict[str, int] = {}
                held = {absolute[i] for i in ix if i < fixed}
                for i in ix:
                    if i < fixed or absolute[i] in held:
                        continue
                    n = order.setdefault(absolute[i], len(order) + 1)
                    names[i] = f"~{n}/{names[i]}"
    raise ValueError("cannot give the files of this run names that tell "
                     "them apart: " + ", ".join(sorted(
                         {n for ix in clashes for n in (names[i] for i in ix)}
                     )[:3]))


def _grown_name(name: str) -> str:
    """A name _distinct grew, written as recorded_path writes one (its
    undecodable bytes as %XX, never read as a site)."""
    from .bundle import _not_a_site, name_escaped
    return name_escaped(_not_a_site(name))


#: This run's --bundle, and whether the run wrote it or said that the
#: file there is not its own (_stale): {"bundle", "written", "said"}. In
#: the run's own context (main).
_BUNDLE_STATE: contextvars.ContextVar = contextvars.ContextVar(
    "bellbriar_bundle_state", default=None)


def _older_file(path) -> bool:
    """Is there something at `path` that could pass for a bundle: anything
    but a directory?"""
    return bool(path) and os.path.exists(path) and not os.path.isdir(path)


def _stale(args) -> str:
    """" The file already at … is not this run's." when a run that writes
    no bundle finds one at --bundle: an older bundle there could pass for
    this run's (R5F-6). Nothing is said when there is none."""
    out = getattr(args, "bundle_out", None)
    if not _older_file(out):
        return ""
    _said()
    return f" The file already at {out} is not this run's."


def _said() -> None:
    """The run has said what it had to about the file at --bundle."""
    state = _BUNDLE_STATE.get()
    if state is not None:
        state["said"] = True


def _stale_at_exit() -> None:
    """Said once, for a run that ends with status 2 and wrote no bundle,
    when no refusal of its own said it (R5H-4): an older bundle at
    --bundle could pass for this run's."""
    state = _BUNDLE_STATE.get()
    if (state is not None and state["bundle"] and not state["written"]
            and not state["said"] and _older_file(state["bundle"])):
        print(f"[bellbriar] note: no evidence bundle was written; the file "
              f"already at {state['bundle']} is not this run's.",
              file=sys.stderr)


def _bundle_given(argv) -> str | None:
    """--bundle's value in `argv`, read as the run's own parser reads an
    option (any unique start of its name, "=" or the next argument), for a
    run whose arguments that parser refused before it read them (R5J-3)."""
    class _Quiet(argparse.ArgumentParser):
        def error(self, message):
            raise ValueError(message)
    ap = _Quiet(add_help=False)
    ap.add_argument("--bundle", dest="bundle_out")
    # The run's other option that starts so: `--b` is ambiguous (R5L-9);
    # given with no value, it leaves --bundle read (R5N-7).
    ap.add_argument("--baseline", nargs="?")
    try:
        known, _rest = ap.parse_known_args(list(argv))
    except (ValueError, TypeError, SystemExit):
        return None
    return known.bundle_out if isinstance(known.bundle_out, str) else None


def _write(path: str, data: bytes) -> str | None:
    """Write an output file; the reason it failed, or None."""
    try:
        Path(path).write_bytes(data)
    except OSError as exc:
        return exc.strerror or str(exc)
    return None


def _unwritable(path: str) -> str | None:
    """Why an output file cannot be written, found before the run: a
    missing or non-directory parent. A failed write after the run still
    exits 2 (_write), but this way a run, and a remote signature, is not
    spent on a typo."""
    parent = Path(path).parent
    if not parent.is_dir():
        return ("no such directory" if not parent.exists()
                else "its parent is not a directory")
    if Path(path).is_dir():
        return "it is a directory"
    return None


#: How many pages one run evaluates by default (--max-pages), and at most.
DEFAULT_MAX_PAGES = 50
MAX_PAGES = 1000

#: --fail-on thresholds: the highest tier the gate counts.
_THRESHOLDS = {"tier1": 1, "tier2": 2, "any": 3}
#: --strict also fails the gate on the reviews a report marks "pled in
#: complaints" or "a best practice" (engine.strict_gated) at this impact or
#: above: in effect the gate before rulebook 0.3.0, plus a missing skip
#: link even where a main landmark stands in for one. Minor ones (a logo
#: link then "Home", a skipped heading level) stay informational even
#: then.
STRICT_MIN_IMPACT = MODERATE
_IMPACT_RANK = {MINOR: 1, MODERATE: 2, SERIOUS: 3, BLOCKER: 4}


def _strict_findings(pages, rulebook: dict, policy: str) -> list:
    """The owned findings --strict would fail the gate on, within the tiers
    --fail-on counts."""
    from .engine import strict_gated
    threshold = _THRESHOLDS.get(policy)
    if threshold is None:
        return []
    rules = {r["id"]: r for r in rulebook["rules"]}
    floor = _IMPACT_RANK[STRICT_MIN_IMPACT]
    out = []
    for page in pages:
        for rr in page.results:
            meta = rules.get(rr.rule_id, {})
            if (not strict_gated(meta)
                    or not 1 <= int(meta.get("tier", 3)) <= threshold):
                continue
            out.extend(f for f in rr.findings
                       if f.verdict == NEEDS_REVIEW and f.owned
                       and _IMPACT_RANK.get(f.impact, 0) >= floor)
    return out


def _shown(text, limit: int = 200) -> str:
    """Text from a file the run was given (a baseline's page paths), as the
    console may print it (redact.printable): every control and format
    character escaped, and backslashes, so a path cannot start a line of
    its own (a CI runner reads "::error" at the start of one as a command),
    hide or reorder what is printed, or rewrite the terminal (R4B-12,
    R4C-7); at most `limit` characters."""
    from .redact import printable
    text = printable(text, backslash=True)
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _gate_findings(pages, rulebook: dict, policy: str, strict: bool = False,
                   baseline=None) -> tuple[list, list]:
    """What the gate counts: (the FAIL findings in the site's own markup,
    in the tiers --fail-on counts, of rules that applied — a FAIL means
    WCAG is violated, or probably is — and, with --strict, the findings
    that are not WCAG failures on their own, _strict_findings). With a
    `baseline` (A10), only those it does not list (report.baseline_key).
    The console's counts and the exit code both come from here, so they
    cannot disagree (R4B-5)."""
    if policy == "never":
        return [], []
    tiers = {r["id"]: int(r.get("tier", 3)) for r in rulebook["rules"]}
    threshold = _THRESHOLDS[policy]
    fails = [f for page in pages for rr in page.results
             if rr.applicable and 1 <= tiers.get(rr.rule_id, 3) <= threshold
             for f in rr.findings if f.verdict == FAIL and f.owned]
    held = _strict_findings(pages, rulebook, policy) if strict else []
    if baseline is not None:
        from .report import new_findings
        new = new_findings(pages, rulebook, baseline)
        fails = [f for f in fails if id(f) in new]
        held = [f for f in held if id(f) in new]
    return fails, held


def _gate_failed(rulebook: dict, policy: str, pages=(), strict: bool = False,
                 baseline=None) -> bool:
    """Does the gate fail (_gate_findings)?"""
    fails, held = _gate_findings(pages, rulebook, policy, strict, baseline)
    return bool(fails or held)


def _say_baseline(baseline, run: dict, policy: str, strict: bool) -> None:
    """What --baseline does to this run's gate, and when the comparison
    looks wrong (A10): a baseline none of whose findings this run has may
    have recorded its pages under other names, and one made with another
    rulebook reads the findings of rules whose tier changed as new."""
    from .report import baseline_counts, run_fingerprints
    new, new_fail = baseline_counts(run["pages"], run["rulebook"], baseline)
    total = len(run_fingerprints(run["pages"]))
    fails, held = _gate_findings(run["pages"], run["rulebook"], policy,
                                 strict, baseline)
    if policy == "never":
        gate = "the gate counts none of them (--fail-on never)"
    else:
        what = f"{len(fails)} failure(s) in the tiers --fail-on {policy} counts"
        if strict:
            what += f" and {len(held)} --strict finding(s)"
        gate = f"the gate counts {what}, and only those"
    print(f"baseline: {_shown(baseline.path)} (sha256 "
          f"{baseline.sha256[:16]}…, {baseline.findings} finding(s)): {new} "
          f"of this run's {total} finding(s) are not in it ({new_fail} of "
          f"them failures in the site's own markup); {gate}. The reports "
          "still list every finding.")
    if baseline.findings and total and new == total:
        print("[bellbriar] warning: none of this run's findings is in the "
              "baseline. If the pages were recorded under other names (a "
              "folder named another way, another working directory, URLs "
              "beside files), every finding reads as new: the baseline's "
              "pages are "
              + ", ".join(_shown(p) for p in baseline.paths[:2])
              + (", …" if len(baseline.paths) > 2 else "") + ".",
              file=sys.stderr)
    if baseline.rulebook_sha256 and \
            baseline.rulebook_sha256 != run.get("rulebook_sha256"):
        print("[bellbriar] note: the baseline was made with another "
              "rulebook; the findings of a rule whose tier changed read as "
              "new.", file=sys.stderr)


def _check_recordable_host(url: str) -> None:
    """Refuse, before fetching, a --url whose host no run could record. A
    bundle binds the host read from the final URL (CANONICALIZATION §5):
    letters, digits, "-", "_" and ".", or an IP address. A browser accepts
    some ASCII punctuation (`a!b.com`) that no DNS name has, and refuses a
    bogus xn-- label; either way finding out after the run wastes it.
    Anything a browser may still turn into a recordable host (127.1, a
    percent escape, a Unicode name, a redirect) is left to the check on the
    final URL after the run."""
    from .bundle import _valid_a_label
    authority = url.split("://", 1)[-1]
    for end in "/?#":
        authority = authority.split(end, 1)[0]
    host = authority.rpartition("@")[2]
    if host.startswith("["):
        return                          # an IPv6 literal
    name = urllib.parse.unquote(host.rpartition(":")[0] if ":" in host
                                else host)
    odd = sorted({ch for ch in name if ch.isascii()
                  and not (ch.isalnum() or ch in "._-")})
    if odd:
        raise ValueError(
            f"--url: the host {name!r} contains {''.join(odd)!r}, which no "
            "DNS name has, so evidence could not record it and no bundle "
            "could be written. Use the site's DNS name, or run without "
            "--bundle.")
    bogus = [label for label in name.lower().split(".")
             if label.startswith("xn--") and not _valid_a_label(label)]
    if bogus:
        raise ValueError(
            f"--url: the host {name!r} has a label, {bogus[0]!r}, that is "
            "not a valid internationalized (xn--) label, so no browser can "
            "fetch it.")


def _serialize(run: dict, site: dict, judged: dict | None,
               baseline=None) -> dict:
    """The JSON report, `bellbriar-report/1` (report.build_report)."""
    from .report import build_report
    return build_report(run, site, judged, baseline=baseline)


#: --sign-key-env's default variable name, for the record: nothing reads
#: it unless --sign-key-env names it. A key is never taken implicitly,
#: and never from the command line (P1-11).
SIGN_KEY_ENV = "BELLBRIAR_SIGN_KEY"
#: What --sign-key-env takes: the name of an environment variable.
_ENV_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,127}")


def _private_key(args) -> str | None:
    """The signing key, read from the file --sign-key names or from the
    environment variable --sign-key-env names; None when neither is given.
    A key itself on the command line would land in shell history, process
    listings and CI logs, so a value that is not a file is refused.

    No message quotes what either option was given, nor anything read
    through it: passed by mistake where the path or the name goes, a key
    would reach the CI log with the message (R1A-1). The one exception is
    the default variable name, which is no secret. Raises ValueError with
    a reason a person can act on."""
    from .bundle import (KeyFileError, looks_like_key, parse_key_text,
                         read_private_key_file)
    if args.sign_key is not None:
        try:
            key, mode = read_private_key_file(args.sign_key)
        except KeyFileError as exc:
            raise ValueError(f"--sign-key: {exc}") from None
        if os.name == "posix" and mode & (stat.S_IRWXG | stat.S_IRWXO):
            print("[bellbriar] warning: the key file --sign-key names is "
                  "readable by other users of this machine; chmod 600 it",
                  file=sys.stderr)
        return key
    if args.sign_key_env is None:
        return None
    name = args.sign_key_env
    if not _ENV_NAME.fullmatch(name) or looks_like_key(name):
        raise ValueError(
            "--sign-key-env takes the NAME of an environment variable "
            f"({SIGN_KEY_ENV}, say), not its value. What was given is not "
            "repeated here, in case it was a key"
            + ("; if it is a key in use, treat it as exposed (it is in your "
               "shell history or CI configuration)" if looks_like_key(name)
               else ""))
    # A secret this process holds is not passed to the browser it starts
    # (R1A-9).
    from .fetch import WITHHELD_ENV
    WITHHELD_ENV.add(name)
    text = os.environ.get(name)
    shown = name if name == SIGN_KEY_ENV else "the variable it names"
    if text is None:
        raise ValueError(f"--sign-key-env: {shown} is not set (in CI, check "
                         "that the secret is available to this job)")
    kind, key = parse_key_text(text)
    if kind == "public":
        raise ValueError(f"--sign-key-env: {shown} holds a PUBLIC key (its "
                         "first line says so), which its owner publishes: a "
                         "bundle signed with it could be signed by anyone")
    if key is None or kind == "other":
        # Never quote what was read: it may be most of a key.
        raise ValueError(f"--sign-key-env: {shown} does not hold an Ed25519 "
                         "private key (64 hex characters, alone or as "
                         "bellbriar-evidence keygen writes the .key file)")
    return key


#: Where --http-user finds its password when --http-password-file is not
#: given. Never a command-line value: argv shows up in process listings,
#: shell history and CI logs.
HTTP_PASSWORD_ENV = "BELLBRIAR_HTTP_PASSWORD"


def _http_credentials(args) -> tuple[str, str] | None:
    """(user, password) for --http-user, with the password read from a file
    or the environment. Raises ValueError with a reason a person can act on."""
    if args.http_user is None:
        if args.http_password_file:
            raise ValueError("--http-password-file needs --http-user")
        return None
    if args.http_password_file:
        path = args.http_password_file
        try:
            raw = Path(path).read_bytes()
        except OSError as exc:
            raise ValueError(f"--http-password-file {path}: "
                             f"{exc.strerror or exc}") from None
        try:
            password = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise ValueError(f"--http-password-file {path} is not UTF-8 "
                             "text") from None
        password = password.rstrip("\r\n")   # one line, as editors save it
    else:
        password = os.environ.get(HTTP_PASSWORD_ENV)
        if password is None:
            raise ValueError(
                f"--http-user needs a password: set ${HTTP_PASSWORD_ENV} or "
                "pass --http-password-file FILE (never on the command line)")
    if not password:
        raise ValueError("the --http-user password is empty (in CI, check "
                         "that the secret is available to this job)")
    try:
        password.encode("utf-8")
    except UnicodeEncodeError:
        # Bytes the environment could not decode: no error may quote them
        # (R5R-9).
        raise ValueError(f"${HTTP_PASSWORD_ENV} is not UTF-8 text") from None
    if _in_own_words(password):
        raise ValueError(
            "the --http-user password is too common: the harness's own "
            "text holds it, as a page's text and its findings' can, so the "
            "findings withheld for quoting it could let a reader of the "
            "report or bundle work it out. Use a long random password for "
            "the site")
    return args.http_user, password


def _without_password(text, password: str):
    """`text` with the --http-user password, in any case and in each
    spelling redact.password_pattern reads (percent-encoded, as character
    references: R5P-2, R5R-1), replaced by REDACTED: what the console
    prints (R5N-3). A password too short to be looked for is left
    (MIN_PASSWORD_SCRUB)."""
    from .redact import REDACTED, password_pattern
    pattern = password_pattern(password)
    if pattern is None or not isinstance(text, str) or not text:
        return text
    return pattern.sub(REDACTED, text)


def _password_in(password: str, texts) -> bool:
    """Does any of `texts` hold `password`, in any case or spelling
    (redact.password_pattern)?"""
    from .redact import password_pattern
    pattern = password_pattern(password)
    return pattern is not None and any(pattern.search(str(t))
                                       for t in texts if t)


def _header_in(credentials, texts) -> bool:
    """Does any of `texts` hold the Authorization header the --http-user
    credentials make (redact.basic_auth_tokens), in any spelling (R6C-2)?"""
    from .redact import basic_auth_tokens, secrets_pattern
    pattern = secrets_pattern(basic_auth_tokens(*credentials))
    return pattern is not None and any(pattern.search(str(t))
                                       for t in texts if t)


def _check_password_urls(credentials, urls) -> None:
    """Refuse a --http-user password that a URL of the run holds, in any
    case or spelling, and a URL that holds the Authorization header the
    credentials make (a sitemap a server wrote may list one: R6C-2):
    reports and bundles record the URLs, and no record of a URL leaves a
    word out of its host or path (R5J-4). A page that goes to one is not
    evaluated (_run_urls, R5L-4)."""
    if _password_in(credentials[1], urls):
        raise ValueError(
            "the --http-user password occurs in a URL this run reads, which "
            "its reports and bundle record: use a long random password for "
            "the site")
    if _header_in(credentials, urls):
        raise ValueError(
            "a URL this run reads holds the Authorization header its "
            "--http-user credentials make, which its reports and bundle "
            "would record")


#: Words a locator is made of beside the page's own ids and classes: the
#: elements most pages have, and how a step counts its place.
_LOCATOR_WORDS = (
    "html", "head", "body", "main", "header", "footer", "nav", "section",
    "article", "aside", "div", "span", "form", "input", "button", "label",
    "select", "option", "textarea", "fieldset", "legend", "table", "thead",
    "tbody", "tfoot", "caption", "figure", "figcaption", "details",
    "summary", "dialog", "template", "slot", "picture", "source", "video",
    "audio", "track", "iframe", "object", "embed", "canvas", "image",
    "svg", "path", "title", "desc", "use", "symbol", "foreignObject",
    "nth-of-type(", "nth-child(", " > ")


def _in_own_words(password: str) -> bool:
    """Does the harness's own fixed text hold `password`, in a spelling
    findings quote it in: every string in its source and its rulebook,
    which its messages, notes and locators are made of? A finding that
    quotes the password is withheld (redact.WITHHELD_MESSAGE), and which
    of these known words were withheld would give the password away
    (R5J-4). One too short to be looked for is never withheld."""
    from .redact import password_pattern
    pattern = password_pattern(password)
    # As findings are withheld for it: in any case and each spelling
    # password_pattern reads, white space between its characters or not
    # (R5L-8, R5N-5).
    return pattern is not None and pattern.search(_own_text()) is not None


@functools.lru_cache(maxsize=1)
def _own_text() -> str:
    """The harness's own fixed text (_in_own_words): every string in its
    source but the docstrings, which nothing prints, its rulebook, and the
    axe-core it runs, whose words its findings quote (R5L-3)."""
    import ast
    here = Path(__file__).resolve().parent
    parts = list(_LOCATOR_WORDS)
    for source in sorted(here.glob("*.py")):
        try:
            tree = ast.parse(source.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError, ValueError):
            continue
        docs = set()
        for node in ast.walk(tree):
            body = getattr(node, "body", None)
            if (isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                  ast.AsyncFunctionDef)) and body
                    and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)):
                docs.add(id(body[0].value))
        parts.extend(node.value for node in ast.walk(tree)
                     if isinstance(node, ast.Constant)
                     and isinstance(node.value, str)
                     and id(node) not in docs)
    # The rulebook's strings, as JSON reads them, and the axe-core it runs
    # with its strings' escapes read (`Element\'s`), as well as written
    # (R5R-7).
    try:
        rulebook = json.loads((here / "rulebook.json").read_text(
            encoding="utf-8"))
    except (OSError, ValueError):
        rulebook = None
    stack = [rulebook]
    while stack:
        item = stack.pop()
        if isinstance(item, str):
            parts.append(item)
        elif isinstance(item, dict):
            stack.extend(item.keys())
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    try:
        axe = (here / "vendor" / "axe-core" / "axe.min.js").read_text(
            encoding="utf-8", errors="replace")
    except OSError:
        axe = ""
    parts += [axe, _JS_ESCAPE.sub(_js_unescape, axe)]
    return "\x00".join(parts)


#: A JavaScript string's escape: \uXXXX, \u{…}, \xXX, or one character.
_JS_ESCAPE = re.compile(r"\\(?:u([0-9a-fA-F]{4})|u\{([0-9a-fA-F]{1,6})\}"
                        r"|x([0-9a-fA-F]{2})|(.))", re.S)


def _js_unescape(m: re.Match) -> str:
    code = m.group(1) or m.group(2) or m.group(3)
    if code is not None:
        n = int(code, 16)
        return chr(n) if n <= 0x10FFFF and not 0xD800 <= n <= 0xDFFF \
            else "\ufffd"
    ch = m.group(4)
    return {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f",
            "v": "\v", "0": "\x00"}.get(ch, ch)


def _render_deadline_default() -> int:
    from .fetch import DEFAULT_RENDER_DEADLINE_S
    return DEFAULT_RENDER_DEADLINE_S


def _seconds(text: str) -> float:
    """--render-deadline: 5 to 86,400 seconds (fetch.check_deadline); 0,
    -5, inf and nan are refused, not quietly read."""
    from .fetch import check_deadline
    try:
        return check_deadline(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from None


def _coverage_note(pages: list, captures: list, build: bool) -> str:
    """The run's coverage note: what its layers covered (coverage_sentence),
    then what its pages were read from — every page rendered, none, or
    some, and how many could not be read at all (R3D-4); each page's
    record says which. `captures` holds each page's capture, None for a
    page the run could not fetch or serve."""
    head = coverage_sentence(pages)
    if not any(not getattr(p, "parse_error", "") for p in pages):
        # Nothing the rules could read (R3C-4).
        return head
    rendered = static = unread = 0
    for i, page in enumerate(pages):
        fr = captures[i] if i < len(captures) else None
        if fr is None or getattr(page, "parse_error", ""):
            unread += 1
        elif fr.mode == "rendered":
            rendered += 1
        else:
            static += 1
    if not (rendered or static):
        return head
    if rendered == len(pages):
        return head + (BUILD_SENTENCE if build else RENDERED_SENTENCE)
    if static == len(pages):
        return head + (BUILD_STATIC_SENTENCE if build
                       else SERVER_ONLY_SENTENCE)
    parts = []
    if rendered:
        parts.append(f"{rendered} {'was' if rendered == 1 else 'were'} "
                     f"captured after {'its' if rendered == 1 else 'their'} "
                     "scripts ran")
    if static:
        parts.append(f"{static} {'was' if static == 1 else 'were'} read "
                     + ("as files are" if build else
                        "from the HTML the server sent"))
    if unread:
        parts.append(f"{unread} could not be read")
    said = (", ".join(parts[:-1]) + " and " + parts[-1] if len(parts) > 1
            else parts[0])
    return head + (
        f" Of the run's {len(pages)} pages, {said} (each page's record "
        "says which)" + (": on those read without a browser, content "
                         "built by JavaScript was NOT evaluated." if static
                         else "."))


def _no_page_why(pages: list, args, url_run: bool) -> str:
    """Why no page of the run could be evaluated, every page being empty
    to the rules, and what to do about it, by how the pages were read
    (N27, R4B-14)."""
    modes = [(getattr(p, "fetch", None) or {}).get("mode") for p in pages]
    rendered = sum(1 for m in modes if m == "rendered")
    if modes and rendered == len(modes):
        return ("every page was empty when captured, after its scripts ran "
                "(each page's warning above says why): check that the pages "
                "build their content in a browser, and look at the "
                "browser's console for errors.")
    if getattr(args, "provenance_attr", None) or \
            getattr(args, "read_as", None) == "dom":
        # Saved captures, re-read: their scripts ran when they were made.
        return ("every page was empty as it was saved: these are captures "
                "a browser made earlier, after the pages' scripts ran. "
                "Capture the pages again, and check that they build their "
                "content in a browser.")
    if args.render or (url_run and not args.no_render):
        rest = len(modes) - rendered

        def were(n):
            return "was" if n == 1 else "were"

        def read(n):
            return ("the HTML the server sent" if not args.render else
                    "a file" if n == 1 else "files")
        got = (f"{rendered} of them {were(rendered)} rendered and still "
               f"empty after {'its' if rendered == 1 else 'their'} scripts "
               f"ran, and the other {rest} "
               f"{were(rest)} read as {read(rest)}" if rendered else
               f"it could not be rendered, so this run read it as "
               f"{read(1)}" if len(modes) == 1 else
               f"none of them could be rendered, so this run read them as "
               f"{read(len(modes))}")
        return ("every page is a client-rendered app shell or was empty: "
                f"{got}. Each page's capture record says why it was not "
                "rendered"
                + (": a page that went to another document when rendered is "
                   "read as the file it is, and" if args.render else ";")
                + " a browser that is missing or cannot start is named there "
                "(bellbriar-eval --install-browser installs it).")
    if url_run:
        return ("every page is a client-rendered app shell, and this run "
                "read only the HTML the server sent: run it without "
                "--no-render, so the pages' scripts build them.")
    return ("every page is a client-rendered app shell. Render the build: "
            "bellbriar-eval <folder> --render (or --url against a server).")


def _install_browser(require_sandbox: bool = False) -> int:
    """`bellbriar-eval --install-browser` (N28): the Chromium build the
    browser checks use, through Playwright's own installer, then a check
    that it starts, and whether with its sandbox. Exit 0 when it does (with
    `require_sandbox`, only when its sandbox starts too), else 2."""
    import subprocess
    try:
        import playwright  # noqa: F401
    except ImportError:
        print("[bellbriar] error: the browser checks need Playwright, which "
              "the browser extra installs: pip install "
              "'bellbriar-harness[browser]' (pipx: pipx install "
              "'bellbriar-harness[browser]'; uv: uv tool install "
              "'bellbriar-harness[browser]'), then run this again.",
              file=sys.stderr)
        return 2
    cmd = [sys.executable, "-m", "playwright", "install", "chromium"]
    print(f"[bellbriar] installing Chromium for Playwright: "
          f"{' '.join(cmd[1:])}", file=sys.stderr)
    try:
        code = subprocess.call(cmd)
    except OSError as exc:
        print(f"[bellbriar] error: Playwright's installer could not run "
              f"({exc.strerror or exc}).", file=sys.stderr)
        return 2
    if code != 0:
        print(f"[bellbriar] error: Playwright's installer stopped (exit "
              f"status {code}); its own messages above say why.",
              file=sys.stderr)
        return 2
    why, sandbox_off = _browser_starts()
    if why:
        print(f"[bellbriar] error: Chromium is installed but does not start "
              f"({why})."
              + (" On Linux it needs system libraries: sudo "
                 f"{sys.executable} -m playwright install-deps chromium, or "
                 "use the container image." if sys.platform.startswith(
                     "linux") else ""), file=sys.stderr)
        return 2
    if sandbox_off and require_sandbox:
        print(f"[bellbriar] error: Chromium is installed and starts, but not "
              f"with its sandbox ({sandbox_off}), so runs with "
              "--require-sandbox would be refused.", file=sys.stderr)
        return 2
    if sandbox_off:
        print(f"[bellbriar] Chromium is installed and starts, without its "
              f"sandbox ({sandbox_off}): --url and --render runs can render "
              "pages, and each capture records that its sandbox was off; "
              "--require-sandbox would refuse them.", file=sys.stderr)
        return 0
    print("[bellbriar] Chromium is installed and starts with its sandbox: "
          "--url and --render runs can render pages.", file=sys.stderr)
    return 0


def _browser_starts() -> tuple[str, str]:
    """("" when Playwright's Chromium starts here, else why not; why it
    runs without its sandbox, "" when the sandbox starts), in words of the
    harness's own. It starts the browser as a run does
    (fetch._launch_chromium): with its sandbox wherever that can start, so
    it does not report a browser that starts only without it as ready
    (R4B-6)."""
    try:
        from playwright.sync_api import sync_playwright

        from .fetch import _launch_chromium
        with sync_playwright() as p:
            browser, sandbox_off = _launch_chromium(p)
            browser.close()
    except Exception as exc:                            # noqa: BLE001
        text = str(exc)
        if "Executable doesn't exist" in text:
            return "Playwright cannot find it", ""
        if "shared libraries" in text or "missing dependencies" in text \
                or "Host system is missing" in text:
            return "system libraries it needs are missing", ""
        return "it failed to launch", ""
    return "", sandbox_off


def _unread_page(path: str, why: str):
    """A page the run could not fetch or read: not evaluated, never a pass
    (it makes the run incomplete, P2-12)."""
    from .model import PageResult
    return PageResult(path=path, evaluable=False, parse_error=why,
                      not_evaluable_reason=(
                          f"it could not be evaluated ({why}); no rule ran on "
                          "it, and that is not a pass"))


def _url_list(args, credentials, keep) -> tuple[list[str], dict]:
    """The run's URLs, in order, and how they were listed (the run-level
    fetch record's `list`): --url (repeatable), --urls FILE, or --sitemap.
    Exact repeats are dropped; more than --max-pages listed explicitly is
    an error, and a sitemap gives its first --max-pages."""
    from .redact import redact_url
    if args.sitemap:
        from . import sitemap
        from .fetch import canonical_url
        got = sitemap.read(args.sitemap, args.max_pages, credentials, keep)
        if not got.urls:
            raise ValueError(f"the sitemap {args.sitemap} lists no page on "
                             "its own host")
        print(f"[bellbriar] sitemap: {len(got.urls)} of "
              f"{'' if got.complete else 'at least '}{got.listed} listed "
              f"page(s) to evaluate"
              + (f"; {got.other_host} entr(ies) on other hosts skipped"
                 if got.other_host else ""), file=sys.stderr)
        listing = {"kind": "sitemap",
                   "url": redact_url(canonical_url(args.sitemap), keep)[0],
                   "listed": got.listed, "complete": got.complete,
                   "max_pages": args.max_pages}
        return got.urls, listing
    if args.urls:
        try:
            text = Path(args.urls).read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as exc:
            raise ValueError(f"--urls {args.urls}: "
                             f"{getattr(exc, 'strerror', None) or exc}") \
                from None
        urls = [line.strip() for line in text.splitlines()
                if line.strip() and not line.strip().startswith("#")]
        if not urls:
            raise ValueError(f"--urls {args.urls} lists no URL")
    else:
        urls = list(args.url)
    urls = _distinct_urls(urls)
    if len(urls) > args.max_pages:
        raise ValueError(f"{len(urls)} URLs listed, more than --max-pages "
                         f"({args.max_pages}); raise it, or list fewer")
    return urls, {"kind": "urls", "max_pages": args.max_pages}


def _capture_digest(fr) -> str:
    """The SHA-256 of a capture with its provenance attribute's name, which
    is new on every capture, written one way: two captures of one page
    compare equal (PR3-5)."""
    import hashlib
    data = fr.snapshot_bytes
    if fr.provenance_attr:
        data = data.replace(fr.provenance_attr.encode("ascii"), b"data-bb-p")
    return hashlib.sha256(data).hexdigest()


def _distinct_urls(urls: list) -> list:
    """`urls` without repeats: two URLs that a browser requests the same
    way, fragment included (`HTTP://Example.com:80/` is `http://example.com/`),
    are one page, evaluated where the first is listed under the least of
    their spellings, so the recorded URL does not depend on the list's
    order (R4E-1); the console says how many were dropped. URLs that differ
    only in their fragment stay apart here, since a client router can show
    a different page for each (`#/about`); _run_urls drops one whose
    capture turns out the same."""
    from .fetch import page_key
    least: dict = {}
    for u in urls:
        key = page_key(u)
        least[key] = min(least[key], u) if key in least else u
    if len(least) < len(urls):
        print(f"[bellbriar] note: {len(urls) - len(least)} URL(s) name a "
              "page the list already names (spelled another way, or "
              "repeated): each page is evaluated once.", file=sys.stderr)
    return list(least.values())


def _rendered_any(captures) -> bool:
    """Did a browser capture any of the run's pages (tool_record)?"""
    return any(fr is not None and fr.mode == "rendered" for fr in captures)


def _report_capture(fr, tag: str, safe, name: str | None = None,
                    said: set | None = None) -> None:
    """The console lines for one capture: rendered or not, and its notes
    (a note every page shares, such as the sandbox's, once: `said` holds
    the ones already printed). `name` is a --render run's file name."""
    shown = name or safe(fr.final_url)
    if fr.mode == "rendered":
        print(f"[bellbriar] {tag}rendered {shown} (chromium "
              f"{fr.browser['version']}, settled after "
              f"{fr.wait['waited_ms']} ms)", file=sys.stderr)
    else:
        what = ("not rendered, read as the file it is" if name
                else "server HTML only")
        print(f"[bellbriar] {tag}WARNING: {shown}: {what} — "
              f"{safe(fr.fallback_reason)}. Content built by JavaScript was "
              "not evaluated; this page may have barriers this run could not "
              "see.", file=sys.stderr)
        if fr.fallback_detail:
            from .redact import printable
            print(f"[bellbriar] {tag}the error's own words (not recorded): "
                  f"{printable(safe(fr.fallback_detail))}", file=sys.stderr)
    for note in fr.notes:
        if said is not None:
            if note in said:
                continue
            said.add(note)
        print(f"[bellbriar] {tag}note: {safe(note)}", file=sys.stderr)


def _say_detail(exc, tag: str, safe) -> None:
    """The error's own words for a failed capture, on the console only: a
    page can word them, so no record holds them (R4C-3), and they are
    escaped like any text a page writes (R4E-2)."""
    from .redact import printable
    detail = getattr(exc, "detail", "")
    if detail:
        print(f"[bellbriar] {tag}the error's own words (not recorded): "
              f"{printable(safe(detail))}", file=sys.stderr)
    where = getattr(exc, "where", "")
    if where:
        # The URL the page sent the browser to: the page chose it, so no
        # record holds it (R5C-12). Cut after the run's secrets are
        # scrubbed from it, never before (R5H-3).
        shown = printable(safe(where))
        print(f"[bellbriar] {tag}it went to (not recorded): "
              + (shown[:300] + "…" if len(shown) > 300 else shown),
              file=sys.stderr)


_SHELL_TEXT = re.compile(r"\((\d+) characters of text\)")


def _shell_reason(page, fr, build: bool) -> None:
    """An app shell read as the HTML the server sent, in a run that meant
    to render it (or that --no-render kept from it): its reason says how it
    was read and why, not to run what the run already ran (R4C-6)."""
    why = page.not_evaluable_reason or ""
    if page.evaluable or fr.mode != "server" or \
            not why.startswith("client-rendered app shell"):
        return
    m = _SHELL_TEXT.search(why)
    chars = f" ({m.group(1)} characters of text)" if m else ""
    how = ("this run read it as the file it is" if build else
           "this run read the HTML the server sent")
    page.not_evaluable_reason = (
        "client-rendered app shell: outside its scripts the markup has no "
        "links, images, controls, headings or other content the static "
        f"rules read{chars}. Its content is built by JavaScript, and {how} "
        f"without running it ({fr.fallback_reason or 'it was not rendered'})"
        ", so this cannot show whether the page is accessible.")


def _run_urls(args, urls: list, listing: dict, rulebook: dict, domain,
              credentials, keep, safe) -> tuple:
    """Fetch and evaluate each URL in turn (A3): (run, captures, an exit
    code to stop with, or None). One run measures one host: a page whose
    final URL is on another host is not evaluated. A page that cannot be
    fetched, or answers with an error status, is not evaluated either; the
    others still are, and the run is incomplete (exit 2, no bundle)."""
    from . import fetch as F
    from .redact import redact_url
    render_mode = False if args.no_render else (
        True if args.require_render else None)
    pages: list = []
    captures: list = []
    host = None
    redacted: set = set()
    said: set = set()
    #: {(the URL as requested, fragment aside; its capture's sha256): (the
    #: page's recorded URL, the page, where the list names it)}: one page
    #: listed twice, with two fragments.
    same: dict = {}
    def page_of(made, url: str):
        # The URL as given, canonical, numbers pages that share a recorded
        # path (report.page_numbers); it stays in memory.
        made.order = F.canonical_url(url)
        pages.append(made)
    for i, url in enumerate(urls, 1):
        tag = f"[{i}/{len(urls)}] " if len(urls) > 1 else ""
        label = redact_url(F.canonical_url(url), keep)[0]
        try:
            fr = F.fetch(url, render=render_mode,
                         third_party_origins=args.third_party_origin,
                         http_credentials=credentials, record_query=keep,
                         deadline_s=args.render_deadline,
                         require_sandbox=args.require_sandbox)
        except F.FetchError as exc:
            why = safe(str(exc))
            print(f"[bellbriar] {tag}error: {why}", file=sys.stderr)
            _say_detail(exc, tag, safe)
            page_of(_unread_page(label, why), url)
            captures.append(None)
            continue
        record = [fr.final_url, *fr.redirects, *(fr.notes or ()),
                  fr.fallback_reason or ""]
        if credentials and (_password_in(credentials[1], record)
                            or _header_in(credentials, record)):
            # Where it went, and the notes on it, are recorded: one holds
            # the password (R5L-4, R5N-5), or the Authorization header the
            # run sent, which a server can put in a redirect (R6C-2).
            why = ("what its record would say of it (where it went, or a "
                   "note on it) holds the --http-user password; use a long "
                   "random password for the site"
                   if _password_in(credentials[1], record) else
                   "what its record would say of it (where it went, or a "
                   "note on it) holds the Authorization header the run "
                   "sent with the --http-user credentials")
            print(f"[bellbriar] {tag}error: {label}: {why}. Refusing to "
                  "score it.", file=sys.stderr)
            page_of(_unread_page(label, why), url)
            captures.append(None)
            continue
        _report_capture(fr, tag, safe, said=said)
        redacted |= set(fr.redacted)
        if fr.status != 200:
            hint = ""
            if fr.status == 401:
                hint = (" The server did not accept the --http-user "
                        "credentials, or asked for a kind of login other "
                        "than HTTP Basic." if credentials else
                        " The page asks for a login; if it uses HTTP Basic "
                        f"authentication, {F.CREDENTIALS_HINT}.")
            # Only a page its server sends with 200 is evaluated; a 203 or
            # a 206 is no error page, but it is not that either (R5A-17).
            what = ("the harness evaluates only a page its server sends "
                    "with HTTP 200" if fr.status is not None
                    and 200 <= fr.status < 300 else
                    "an error page is not the page you meant to evaluate")
            print(f"[bellbriar] {tag}error: {safe(fr.final_url)} returned "
                  f"HTTP {fr.status}; {what}. Refusing to score it.{hint}",
                  file=sys.stderr)
            page_of(_unread_page(fr.final_url, f"HTTP {fr.status}"), url)
            captures.append(None)
            continue
        if host is None:
            host = fr.host
            ok, why = F.domain_matches(fr.final_url, domain,
                                       include_subdomains=args.include_subdomains)
            if not ok:
                if args.bundle_out:
                    print(f"[bellbriar] error: {why}. Refusing to write "
                          "evidence for a domain this run did not measure "
                          "(--allow-domain-mismatch covers the report only).",
                          file=sys.stderr)
                    return None, [], 2
                lvl = "warning" if args.allow_domain_mismatch else "error"
                print(f"[bellbriar] {lvl}: {why}", file=sys.stderr)
                if not args.allow_domain_mismatch:
                    return None, [], 2
            if fr.address_class != "public":
                # As verify will put it: an address by the table's note, a
                # name by what it resolved to (R1B-2).
                from .bundle import host_note
                note = host_note(fr.host)
                what = (f"is {note}" if note else
                        f"resolved to a {fr.address_class} address")
                print(f"[bellbriar] note: {fr.host} {what} — this run is a "
                      "test or staging artifact, not evidence about a public "
                      "site. The bundle records it as such.", file=sys.stderr)
        elif fr.host != host:
            why = (f"its final URL is on {fr.host}, and this run measures "
                   f"{host}: a run measures one host, so evaluate {fr.host} "
                   "in a run of its own")
            print(f"[bellbriar] {tag}error: {safe(fr.final_url)}: {why}",
                  file=sys.stderr)
            page_of(_unread_page(fr.final_url, why), url)
            captures.append(None)
            continue
        key = (F.page_key(url)[0], _capture_digest(fr))

        def evaluated():
            # A rendered capture is the browser's serialization of the
            # live DOM, read back as it was; server HTML is parsed as a
            # browser parses it, as HTML or XML by its Content-Type.
            # Attribution is honored only from this run's own capture.
            # Each page's capture record says which.
            made = run_page(fr.html, fr.final_url, rulebook,
                            provenance_attr=fr.provenance_attr,
                            reader=fr.reader)
            made.fetch = _capture_record(made, fr)
            _shell_reason(made, fr, build=False)
            return made
        if key in same:
            kept_label, kept, kept_at = same[key]
            least = F.canonical_url(url) < kept.order
            # The least of its URLs is the one kept, which may be this one
            # (R4G-9), named by its place in the list: two fragments read
            # alike once redacted (R4I-4).
            print(f"[bellbriar] {tag}note: {label} is the same page as "
                  f"{kept_label} (the same URL but for its fragment, "
                  "captured the same): evaluated once, as distinct URL "
                  f"{i if least else kept_at} of the {len(urls)} listed "
                  "(exact repeats dropped)",
                  file=sys.stderr)
            if least:
                # The least of its URLs stands for the page, its recorded
                # URL and its number, whichever the list names first
                # (R4C-1, R4E-1): the captures are the same.
                at = next(i for i, q in enumerate(pages) if q is kept)
                page = evaluated()
                page.order = F.canonical_url(url)
                pages[at], captures[at] = page, fr
                same[key] = (label, page, i)
            continue
        page = evaluated()
        page_of(page, url)
        same[key] = (label, page, i)
        captures.append(fr)
    if {"path", "query", "fragment"} & redacted:
        print("[bellbriar] note: URL parameter values are recorded as "
              "REDACTED, so access tokens stay out of reports, logs and "
              "bundles. --record-query NAME records a value that identifies "
              "the page, such as lang.", file=sys.stderr)
    if "userinfo" in redacted:
        print("[bellbriar] note: a user name and password were removed from "
              "a recorded URL.", file=sys.stderr)
    if "http-credentials" in redacted:
        print(f"[bellbriar] note: HTTP credentials were offered only to "
              f"{F.url_origin(urls[0])} and are not recorded.",
              file=sys.stderr)
    first = next((fr for fr in captures if fr is not None), None)
    shared = sorted({p.path for p in pages
                     if sum(1 for q in pages if q.path == p.path) > 1})
    if shared:
        # Two pages whose URLs differ only in what is redacted read alike
        # in every record (R3A-1); the reports number them.
        print(f"[bellbriar] note: {len(shared)} recorded URL(s) name more "
              f"than one page of this run ({safe(shared[0])}"
              + (", …" if len(shared) > 1 else "") + "): their URLs differ "
              "only in values recorded as REDACTED. The reports number "
              "them; --record-query NAME keeps a parameter that tells them "
              "apart.", file=sys.stderr)
    run = {
        **run_header(rulebook, browser=_rendered_any(captures)),
        "source": "urls",
        "layers": layer_records(pages),
        "coverage_note": _coverage_note(pages, captures, build=False),
        # The run's record of what it fetched: the host every page was
        # fetched from, read from the first page's final URL as a verifier
        # reads it (CANONICALIZATION §5); each page's own capture record is
        # its `fetch`.
        "fetch": (None if first is None else
                  {"final_url": first.final_url, "host": host,
                   "pages": len(pages), "list": listing}),
        "pages": pages,
        "rulebook": rulebook,
    }
    return run, captures, None


def _same_origin(a: str, b: str) -> bool:
    """Are two recorded URLs on one origin (scheme, host and port)? A URL
    that is not http(s), such as about:blank, is on none."""
    from .fetch import FetchError, url_origin
    try:
        return url_origin(a) == url_origin(b)
    except FetchError:
        return False


def _run_build(args, collected: list, rulebook: dict, safe) -> tuple:
    """Serve each folder on loopback and evaluate each page's DOM after its
    scripts ran (A1): (run, captures, the other files served, as `inputs`
    records, and those files' paths). A page the browser could not render
    is read as the file it is (loudly), or not evaluated with
    --require-render."""
    from contextlib import ExitStack

    from . import fetch as F
    from .bundle import recorded_path
    from .serve import BuildServer, build_root
    render_mode = True if args.require_render else None
    roots = []                       # (argument, its folder as given, real)
    for arg in args.paths:
        folder = build_root(arg)
        roots.append((arg, os.path.abspath(folder),
                      os.path.realpath(folder)))
    pages: list = []
    captures: list = []
    served: list = []
    said: set = set()
    page_files = {os.path.realpath(f) for f, _ in collected}
    with ExitStack() as stack:
        servers = {}
        for _arg, _folder, real in roots:
            if real not in servers:
                servers[real] = stack.enter_context(
                    BuildServer(real, args.render_base))
        print(f"[bellbriar] serving {len(servers)} folder(s) on this machine "
              f"to render {len(collected)} page(s)", file=sys.stderr)
        moved = [s for s in servers.values() if not s.port_stable]
        if moved:
            print("[bellbriar] note: another program holds the port "
                  f"{len(moved)} folder(s) are usually served on, so a page "
                  "that writes its own address into its markup reads "
                  "differently in this run (its findings' fingerprints "
                  "too).", file=sys.stderr)
        for i, (file, name) in enumerate(collected, 1):
            tag = f"[{i}/{len(collected)}] " if len(collected) > 1 else ""
            real = os.path.realpath(file)
            mine = os.path.abspath(file)
            # The folder it was found in, as the run names it: a link is
            # served at its own path there (R3D-3).
            given = [(f, r) for _a, f, r in roots
                     if mine.startswith(f.rstrip(os.sep) + os.sep)]
            owners = [r for _a, _f, r in roots
                      if real.startswith(r.rstrip(os.sep) + os.sep)]
            if given:
                folder, root = max(given, key=lambda g: len(g[0]))
                if not real.startswith(root.rstrip(os.sep) + os.sep):
                    owners = []          # a link out of the folder served
            else:
                folder, root = None, (max(owners, key=len) if owners
                                      else None)
            if not owners:
                why = ("it links to a file outside the folder this run "
                       "serves" if given else
                       "it is not inside a folder this run serves")
                print(f"[bellbriar] {tag}error: {name}: {why}",
                      file=sys.stderr)
                pages.append(_unread_page(name, why))
                captures.append(None)
                continue
            server = servers[root]
            if any(p.startswith(".") for p in
                   Path(os.path.relpath(real, server.root)).parts) or (
                    folder is not None and any(
                        p.startswith(".") for p in
                        Path(os.path.relpath(mine, folder)).parts)):
                why = ("it is under a name that starts with a dot, which the "
                       "build server never serves (.git, .env); serve the "
                       "folder that holds the build")
                print(f"[bellbriar] {tag}error: {name}: {why}",
                      file=sys.stderr)
                pages.append(_unread_page(name, why))
                captures.append(None)
                continue
            try:
                url = server.url_for(file, folder)
                fr = F.fetch(url, render=render_mode,
                             third_party_origins=args.third_party_origin,
                             deadline_s=args.render_deadline,
                             require_sandbox=args.require_sandbox,
                             fallback="read as the file it is",
                             error_target="fallback")
                # Whether it went elsewhere first: the status of a page it
                # went to is not the file's (R4G-1).
                if fr.mode == "rendered" and (
                        fr.navigated or not _same_origin(fr.final_url, url)):
                    # The page sent the browser to another document (a
                    # redirect to a login, a refresh, another local
                    # service): what was captured is not this file (PR1-3,
                    # PR3-1). It is read as the file it is; the page it
                    # went to, if the build has it, is a page of its own.
                    went = fr.final_url
                    why = (f"when rendered, it navigated to {went}, so the "
                           "browser showed another page")
                    if args.require_render:
                        raise F.FetchError(why)
                    fr = F.fetch(url, render=False)
                    fr.fallback_reason = f"{why}; read as the file it is"
                if fr.status != 200:
                    raise F.FetchError(f"the build server answered HTTP "
                                       f"{fr.status}")
            except F.FetchError as exc:
                why = safe(str(exc))
                print(f"[bellbriar] {tag}error: {name}: {why}",
                      file=sys.stderr)
                _say_detail(exc, tag, safe)
                pages.append(_unread_page(name, why))
                captures.append(None)
                continue
            _report_capture(fr, tag, safe, name=name, said=said)
            page = run_page(fr.html, name, rulebook,
                            provenance_attr=fr.provenance_attr,
                            reader=fr.reader)
            page.fetch = _capture_record(page, fr)
            # The file as the server sent it, for the input manifest: a
            # second reading at bundle time could differ (R5B-10). A page
            # read again as the file it is was evaluated from that last
            # sending, not the browser's (R5D-7).
            page.input_digest = _served_digest(
                server, file, last=fr.mode != "rendered")
            _shell_reason(page, fr, build=True)
            pages.append(page)
            captures.append(fr)
    for arg, folder, real in roots:
        server = servers.get(real)
        if server is None:
            continue
        servers.pop(real)               # each server's files once
        for rel, (digest, size) in sorted(server.served.items()):
            path = os.path.join(real, *rel.split("/"))
            if os.path.realpath(path) in page_files:
                continue
            served.append({"path": recorded_path(
                               os.path.join(folder, *rel.split("/")), arg),
                           "sha256": digest, "bytes": size,
                           "kind": "served", "_file": path})
        missing = list(dict.fromkeys(server.missing))
        if missing:
            shown = ", ".join(missing[:3]) + (", …" if len(missing) > 3
                                              else "")
            code = [m for m in missing
                    if m.lower().endswith((".js", ".mjs", ".css"))]
            print(f"[bellbriar] warning: the pages asked for {len(missing)} "
                  f"path(s) the build does not have ({shown})."
                  + (" Its own scripts or styles are among them, so it may "
                     "expect to be served under another path: set "
                     "--render-base to your bundler's base (e.g. /app/)."
                     if code else ""), file=sys.stderr)
    # Two builds' files can share a name (dist/assets/app.js from each):
    # they take other names, and the pages keep theirs (R5D-10).
    named = _distinct([(Path(f), n) for f, n in collected]
                      + [(Path(e["_file"]), e["path"]) for e in served],
                      fixed=len(collected))
    served_files = []
    for entry, (_f, name) in zip(served, named[len(collected):]):
        entry["path"] = name
        served_files.append(entry.pop("_file"))
    run = {
        **run_header(rulebook, browser=_rendered_any(captures)),
        "source": "render",
        "layers": layer_records(pages),
        "coverage_note": _coverage_note(pages, captures, build=True),
        # A build served from this machine: nothing was fetched from a
        # site, so nothing binds a host. Each page's capture record (its
        # `fetch`) says where it was served from: loopback.
        "fetch": None,
        "pages": pages,
        "rulebook": rulebook,
    }
    return run, captures, served, served_files


def _capture_record(page, fr) -> dict:
    """The page's capture record (FetchResult.fetch_block), its notes
    saying too why the rules read none of axe-core's results on it when
    they did not (PageResult.axe_unread, R5G-1)."""
    block = fr.fetch_block()
    if getattr(page, "axe_unread", "") and isinstance(block, dict) \
            and isinstance(block.get("notes"), list):
        block["notes"].append(page.axe_unread)
    return block


def _file_identity(path) -> tuple:
    """What the file system finds at `path`: an existing file by device
    and inode (a hard link, a symbolic link and the file itself are one),
    a file still to be made by its real path, as the system compares
    names."""
    try:
        st = os.stat(path)
        if st.st_ino:            # 0 where a file system has no inode (FAT)
            return ("file", st.st_dev, st.st_ino)
    except OSError:
        pass
    return ("path", os.path.normcase(os.path.realpath(path)))


def _scrub_findings(pages, secrets) -> int:
    """The run's secrets (redact.set_run_secrets: its URLs' parameter
    values that look like credentials, the --http-user password) replaced
    with REDACTED in every finding's snippet, message, locator and origin,
    also as markup escapes them and as a URL encodes them; a snippet,
    locator or message that holds the password is withheld whole, since a
    word left around it could give it away (R5H-6). The rules already
    write them so (checks_static._f, locator); this is what makes sure,
    whatever wrote a finding (H6-1, R5E-2). `secrets` adds any the run's
    context does not hold. Snapshots are the bytes measured, and keep
    them. How many findings had a field withheld."""
    from .redact import (REDACTED, WITHHELD_MESSAGE, holds_password,
                         reset_run_secrets, scrub_secrets, set_run_secrets)
    token = set_run_secrets(secrets, keep=True)
    withheld = 0
    try:
        for page in pages:
            for result in getattr(page, "results", ()):
                for f in result.findings:
                    held = False
                    for field, whole in (("snippet", REDACTED),
                                         ("message", WITHHELD_MESSAGE),
                                         ("origin_detail", REDACTED)):
                        value = getattr(f, field, None)
                        if not isinstance(value, str):
                            continue
                        if holds_password(value):
                            setattr(f, field, whole)
                            held = True
                        else:
                            setattr(f, field, scrub_secrets(value))
                    selector = getattr(f, "selector", None)
                    if isinstance(selector, list):
                        if any(holds_password(step) for step in selector):
                            f.selector = [REDACTED]
                            held = True
                        else:
                            f.selector = [scrub_secrets(step)
                                          for step in selector]
                    # Or withheld by the rule that wrote it (_f), with a
                    # note added to its message since (R5J-6).
                    withheld += held or (
                        str(getattr(f, "message", "")).startswith(
                            WITHHELD_MESSAGE)
                        or getattr(f, "snippet", "") == REDACTED
                        or getattr(f, "selector", None) == [REDACTED])
    finally:
        reset_run_secrets(token)
    return withheld


def _served_digest(server, file, last: bool = False) -> tuple | None:
    """(sha256, bytes) of `file` as the build server first sent it (to the
    browser), or as it last sent it (`last`: to a server-HTML reading), or
    None if it never sent it."""
    sent = server.last_sent if last else server.served
    for path in (os.path.realpath(file), os.path.abspath(file)):
        try:
            rel = Path(path).relative_to(server.root).as_posix()
        except ValueError:
            continue
        got = sent.get(rel)
        if got is not None:
            return got
    return None


def _snapshot_name(i: int, path: str) -> str:
    """`NNN-<page>.html`: the page's name or URL path in safe characters."""
    import re
    tail = re.sub(r"\.x?html?$", "", path.split("://", 1)[-1],
                  flags=re.IGNORECASE)
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", tail).strip("-.")[:80] or "page"
    return f"{i:03d}-{slug}.html"


def _snapshot_targets(args, pages: list, captures: list) -> list:
    """[(path, capture)] of each snapshot --save-snapshot or
    --save-snapshots writes."""
    if args.save_snapshot:
        if len(captures) != 1:
            raise ValueError("--save-snapshot is for a one-page run; this run "
                             f"has {len(captures)} pages: use --save-snapshots "
                             "DIR")
        return [(str(args.save_snapshot), captures[0])] \
            if captures[0] is not None else []
    if not args.save_snapshots:
        return []
    folder = Path(args.save_snapshots)
    return [(str(folder / _snapshot_name(i, page.path)), fr)
            for i, (page, fr) in enumerate(zip(pages, captures), 1)
            if fr is not None]


def _check_snapshot_targets(args, pages: list, captures: list,
                            evidence: dict) -> None:
    """ValueError if a snapshot would be written over a file this run
    evaluated or its build server sent (`evidence`, by _file_identity):
    the bundle lists those by their hashes (R5E-7, R5E-8); or over
    something that is not a regular file (R5H-5)."""
    for target, _fr in _snapshot_targets(args, pages, captures):
        if _file_identity(target) in evidence:
            raise ValueError(f"a snapshot would be written over a file this "
                             f"run evaluated or served ({target}): write the "
                             "snapshots elsewhere")
        if _not_regular(target):
            raise ValueError(f"a snapshot would be written over something "
                             f"that is not a regular file ({target}: a "
                             "link, a device or a pipe): write the snapshots "
                             "elsewhere")


def _not_regular(path) -> bool:
    """Is there something at `path` that is not a regular file (a link, a
    directory, a device, a pipe)?"""
    try:
        return not stat.S_ISREG(os.lstat(path).st_mode)
    except FileNotFoundError:
        return False
    except OSError:
        return True


def _write_fresh(path: str, data: bytes) -> str | None:
    """Write `data` as a new file at `path`, replacing a regular file there
    and keeping its permissions, never writing through it: no other name
    of the file changes with it (a hard link to a snapshot, R5E-8).
    Anything at `path` that is not a regular file (a link, a device, a
    pipe) is refused, not replaced (R5H-5). The reason it failed, or
    None; a temporary file is never left behind (R5H-8)."""
    import tempfile
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        st = None
    except OSError as exc:
        return exc.strerror or str(exc)
    if st is not None and not stat.S_ISREG(st.st_mode):
        return ("it is not a regular file (a link, a device or a pipe), and "
                "a snapshot is written only as one")
    try:
        fd, tmp = tempfile.mkstemp(
            dir=os.path.dirname(os.path.abspath(path)),
            prefix=".bellbriar-", suffix=".tmp")
    except OSError as exc:
        return exc.strerror or str(exc)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        if os.name != "nt":
            if st is not None:
                mode = stat.S_IMODE(st.st_mode)     # the file's own
            else:
                # As a file this process made by name would be: mkstemp's
                # own mode is the owner's alone.
                mask = os.umask(0)
                os.umask(mask)
                mode = 0o666 & ~mask
            os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException as exc:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        if isinstance(exc, OSError):
            return exc.strerror or str(exc)
        raise
    return None


def _save_snapshots(args, pages: list, captures: list) -> None:
    """--save-snapshot FILE (a one-page run) or --save-snapshots DIR. The
    bytes are written, not text: text mode on Windows rewrites "\\n" as
    "\\r\\n", and the file would no longer match its hash. Each is a
    new file (_write_fresh): one hard-linked to an output written later
    would change with it (R5E-8)."""
    if not (args.save_snapshot or args.save_snapshots):
        return
    if args.save_snapshot:
        targets = _snapshot_targets(args, pages, captures)
        if not targets:
            return
        fr = targets[0][1]
        why = _write_fresh(args.save_snapshot, fr.snapshot_bytes)
        if why:
            raise ValueError(f"cannot write {args.save_snapshot}: {why}")
        print(f"[bellbriar] snapshot: {args.save_snapshot} "
              f"(sha256 {fr.sha256[:16]}…)", file=sys.stderr)
        return
    Path(args.save_snapshots).mkdir(exist_ok=True)
    count = 0
    for out, fr in _snapshot_targets(args, pages, captures):
        why = _write_fresh(out, fr.snapshot_bytes)
        if why:
            raise ValueError(f"cannot write {out}: {why}")
        count += 1
    print(f"[bellbriar] snapshots: {count} in {args.save_snapshots} (each "
          "page's capture record holds its sha256)", file=sys.stderr)


def main(argv=None) -> int:
    """bellbriar-eval: _main, with everything it prints escaped as
    redact.console_text escapes it (R4G-5), ending quietly with status 2
    when the reader of its output stops reading (R5D-15). In a context of
    its own, so the run's secrets (redact.set_run_secrets) end with it.
    On Windows it stops first (support.py)."""
    from .redact import run_escaped
    from .support import refuse_unsupported

    refused = refuse_unsupported("bellbriar-eval")
    if refused is not None:
        return refused

    def run(a):
        try:
            code = _main(a)
        except SystemExit as exc:
            if exc.code == 2:
                if _BUNDLE_STATE.get() is None:
                    # argparse refused the arguments before the run could
                    # read them: a bad option or value (R5J-3).
                    _BUNDLE_STATE.set({
                        "bundle": _bundle_given(sys.argv[1:] if a is None
                                                else a),
                        "written": False, "said": False})
                _stale_at_exit()
            raise
        if code == 2:
            _stale_at_exit()
        return code
    return run_escaped(lambda a: contextvars.copy_context().run(run, a),
                       argv)


def _main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="bellbriar-eval",
        description="Accessibility evaluation for agent-generated web "
                    "output. Every run declares its layer coverage; a "
                    "passing run is necessary, not sufficient.")
    ap.add_argument("paths", nargs="*",
                    help="HTML files, or directories: every .html, .htm, "
                         ".xhtml, .xht and .xhtm file under one, in any case")
    ap.add_argument("--url", action="append", default=[], metavar="URL",
                    help="Fetch and evaluate a URL. The hydrated DOM is "
                         "captured when a browser is available (see "
                         "--no-render). Repeatable: one report and one "
                         "bundle for the set, all on one host")
    ap.add_argument("--urls", metavar="FILE",
                    help="Evaluate every URL listed in FILE, one per line "
                         "(blank lines and lines starting with # skipped)")
    ap.add_argument("--sitemap", metavar="URL",
                    help="Evaluate the pages a sitemap lists, in its order "
                         "(an index is followed into its sitemaps), up to "
                         "--max-pages; only pages on the sitemap's own host")
    ap.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES,
                    metavar="N",
                    help="The most pages a URL or --render run evaluates "
                         f"(default {DEFAULT_MAX_PAGES}, at most {MAX_PAGES}):"
                         " a sitemap's first N; more URLs listed, or more "
                         "files to render, is an error")
    ap.add_argument("--render", action="store_true",
                    help="Files: serve them on this machine (loopback only) "
                         "and evaluate each page's DOM after its scripts "
                         "run, as --url does — for client-rendered builds "
                         "(Vite, Create React App), which are empty shells "
                         "until then. Each directory argument is served as "
                         "a site root; a file's folder is served for it")
    ap.add_argument("--render-base", metavar="PATH", default="/",
                    help="With --render: the URL path the build expects to "
                         "be served under, as your bundler's base or "
                         "homepage setting says (e.g. /app/; default /)")
    ap.add_argument("--no-render", action="store_true",
                    help="Read only the HTML the server sends. Faster, and "
                         "wrong on any site that builds content with "
                         "JavaScript — the run says so in its coverage note")
    ap.add_argument("--require-render", action="store_true",
                    help="Fail (exit 2) rather than fall back to server HTML "
                         "(with --render, to the files as they are)")
    ap.add_argument("--require-sandbox", action="store_true",
                    help="Refuse the run (exit 2) rather than run Chromium "
                         "without its sandbox where the sandbox cannot start "
                         "(as root, or on a host without user namespaces). "
                         "Without it the browser runs unsandboxed there, and "
                         "each capture records that it did")
    ap.add_argument("--render-deadline", type=_seconds, metavar="SECONDS",
                    help="Stop a rendered capture that has not finished "
                         f"after SECONDS (5 to 86400; default "
                         f"{_render_deadline_default()}) and fall back to the "
                         "server's HTML, or exit 2 with --require-render. A "
                         "page whose scripts never yield would otherwise hang "
                         "the run")
    ap.add_argument("--http-user", metavar="USER",
                    help="User name for HTTP Basic authentication on a "
                         "protected --url (staging, preview). The password "
                         f"comes from ${HTTP_PASSWORD_ENV} or "
                         "--http-password-file, never the command line. "
                         "Credentials are offered only to the run's one "
                         "origin, which every URL (and a --sitemap) must "
                         "share, and are never recorded; a URL with "
                         "user:password@ in it is refused")
    ap.add_argument("--http-password-file", metavar="FILE",
                    help="File holding the --http-user password (one line)")
    ap.add_argument("--record-query", action="append", default=[],
                    metavar="NAME",
                    help="Record the value of URL parameter NAME as fetched "
                         "(e.g. lang). Every other query, fragment and path "
                         "parameter value (;name=value) is recorded as "
                         "REDACTED in the URLs a run records, "
                         "and, as the URL gave it, wherever a report, log or "
                         "bundle quotes the page; the saved snapshot is the "
                         "page as measured. Repeatable")
    ap.add_argument("--save-snapshot", metavar="FILE",
                    help="Write the captured DOM of a one-page run. Strongly "
                         "recommended with --bundle: the bundle records the "
                         "snapshot's hash, and a hash of bytes nobody kept "
                         "proves nothing")
    ap.add_argument("--save-snapshots", metavar="DIR",
                    help="Write every page's captured DOM into DIR (made if "
                         "missing), as NNN-<page>.html")
    ap.add_argument("--third-party-origin", action="append", default=[],
                    metavar="ORIGIN",
                    help="Treat markup inserted by scripts from ORIGIN (a "
                         "domain such as widget.vendor.com, or a full origin) "
                         "as a vendor's: reported, not scored. Adds to the "
                         "built-in vendor list; repeatable")
    ap.add_argument("--allow-domain-mismatch", action="store_true",
                    help="Proceed when --domain does not match the fetched "
                         "host, for the report only. With --bundle a "
                         "mismatch is still an error: evidence for a domain "
                         "the run did not measure is refused")
    ap.add_argument("--include-subdomains", action="store_true",
                    help="Accept a fetched host below --domain (e.g. "
                         "staging.example.com for example.com). Off by "
                         "default: --domain must be the host itself or its "
                         "www. form. The measured host is bound into the "
                         "signature either way")
    ap.add_argument("--provenance-attr", metavar="NAME",
                    help="Re-running a snapshot saved by --url: honor the "
                         "first/third-party attribution, the media muted "
                         "state and the record of what the page's "
                         "stylesheets hid, which the harness wrote under "
                         "NAME (the page's fetch.provenance_attr). Without "
                         "it, no attribution is honored, the muted "
                         "attribute decides what is muted, and only markup "
                         "shows what is hidden. Implies --read-as dom")
    ap.add_argument("--read-as", choices=["html", "dom", "xml"],
                    help="Re-running a snapshot saved by --url: read it as "
                         "the run did (the page's fetch.reader): dom for a "
                         "rendered capture, the browser's serialization of "
                         "the live DOM, any <template> in it inert; html "
                         "for server HTML, parsed as a browser parses a "
                         "page, its declarative shadow roots attached; xml "
                         "for a page served as XHTML. By default a file is "
                         "read by its name (.xhtml, .xht and .xhtm as XML) "
                         "and otherwise as html, or as dom with "
                         "--provenance-attr")
    ap.add_argument("--json", dest="json_out", help="Write JSON report")
    ap.add_argument("--html", dest="html_out", help="Write HTML report")
    ap.add_argument("--rulebook", metavar="FILE",
                    help="An alternate rulebook.json. Reports record its "
                         "SHA-256 and say it is not the rulebook this "
                         "harness ships; bundles record the SHA-256, which "
                         "`bellbriar-evidence verify` compares with the "
                         "rulebook it ships. A run where no Tier-1 rule that "
                         "can fail applies cannot pass the gate")
    ap.add_argument("--fail-on", choices=["tier1", "tier2", "any", "never"],
                    default="tier1", help="CI gate threshold (default: tier1;"
                                          " deterministic FAIL findings "
                                          "only, and a FAIL means WCAG is "
                                          "violated or probably is)")
    ap.add_argument("--strict", action="store_true",
                    help="Also fail the gate on review findings marked "
                         "pled in complaints or a best practice, at moderate "
                         "impact or above, in the tiers --fail-on counts")
    ap.add_argument("--baseline", metavar="REPORT",
                    help="The JSON report (--json) of an earlier run: the "
                         "gate counts only findings not in it, matched by "
                         "fingerprint, verdict, owner, tier and impact "
                         "(docs/REPORT.md). The reports and any bundle still "
                         "list every finding, and record the baseline's "
                         "SHA-256")
    # Evidence.
    ap.add_argument("--domain", help="Domain this run evidences, e.g. "
                                     "example.com (recorded and bound into "
                                     "a signature; for --url, checked "
                                     "against the host fetched)")
    ap.add_argument("--bundle", dest="bundle_out",
                    help="Write an evidence bundle (JSON)")
    key = ap.add_mutually_exclusive_group()
    key.add_argument("--sign-key", metavar="FILE",
                     help="Sign the bundle with the Ed25519 private key in "
                          "FILE (64 hex characters, as `bellbriar-evidence "
                          "keygen` writes it; keep it mode 600). The "
                          "signature is self-signed: it shows who signed "
                          "and that nothing changed since, not that the "
                          "results are true")
    key.add_argument("--sign-key-env", metavar="NAME",
                     help="As --sign-key, with the key read from the "
                          f"environment variable NAME (e.g. {SIGN_KEY_ENV}"
                          ", set from a CI secret). Never pass a key "
                          "itself on the command line")
    ap.add_argument("--install-browser", action="store_true",
                    help="Install the Chromium build the browser checks use "
                         "(Playwright's installer), check that it starts, "
                         "and exit. Needs the browser extra: pip install "
                         "'bellbriar-harness[browser]'")
    ap.add_argument("--version", action="version",
                    version=f"bellbriar-harness {__version__}")
    args = ap.parse_args(argv)
    _BUNDLE_STATE.set({"bundle": args.bundle_out, "written": False,
                       "said": False})
    if args.install_browser:
        # Nothing else applies to it, so nothing else is silently ignored,
        # whatever its value (R4B-16, R4C-11); --require-sandbox makes it
        # check the sandbox too. argparse takes an option by any unique
        # start of its name.
        given = argv if argv is not None else sys.argv[1:]
        own = ("--install-browser", "--require-sandbox")
        other = [a for a in given
                 if a.startswith("-") and a != "-" and not any(
                     len(a.split("=", 1)[0]) > 2
                     and o.startswith(a.split("=", 1)[0]) for o in own)]
        if other or args.paths:
            ap.error("--install-browser installs the browser and exits (with "
                     "--require-sandbox, it also checks that the browser's "
                     "sandbox starts): run the evaluation after it")
        return _install_browser(args.require_sandbox)
    sources = [flag for flag, given in (("--url", args.url),
                                        ("--urls", args.urls),
                                        ("--sitemap", args.sitemap)) if given]
    url_run = bool(sources)
    if len(sources) > 1:
        ap.error(f"{' and '.join(sources)}: list a run's pages one way")
    if url_run and args.paths:
        ap.error("pass files or URLs, not both")
    if url_run and args.read_as:
        ap.error("--read-as is for re-running a saved snapshot; a --url run "
                 "reads what it captures as it captured it")
    if args.provenance_attr and args.read_as not in (None, "dom"):
        ap.error("--provenance-attr re-runs a rendered capture, which is read "
                 f"as dom, not --read-as {args.read_as}")
    if args.render:
        if url_run:
            ap.error("--render is for files; a URL run renders by default")
        if args.no_render:
            ap.error("--render and --no-render contradict each other")
        if args.provenance_attr or args.read_as:
            ap.error("--render evaluates files as a browser renders them; "
                     "--provenance-attr and --read-as re-run a saved "
                     "snapshot")
    if not 1 <= args.max_pages <= MAX_PAGES:
        ap.error(f"--max-pages must be 1 to {MAX_PAGES}")
    if args.save_snapshot and args.save_snapshots:
        ap.error("--save-snapshot is for one page, --save-snapshots for any "
                 "number: pass one of them")
    if (args.save_snapshot or args.save_snapshots) and not (url_run
                                                            or args.render):
        ap.error("--save-snapshot and --save-snapshots save what a URL or "
                 "--render run captured")
    if args.render_base != "/" and not args.render:
        ap.error("--render-base is for --render")
    if (args.sign_key or args.sign_key_env) and not args.bundle_out:
        ap.error("--sign-key and --sign-key-env sign the evidence bundle: "
                 "pass --bundle FILE too")
    # Read before the run, so a bad baseline costs no run (A10).
    baseline = None
    if args.baseline:
        from . import baseline as BL
        try:
            baseline = BL.load(args.baseline)
        except BL.BaselineError as exc:
            print(f"[bellbriar] error: {exc}", file=sys.stderr)
            return 2
    # Read before the run, so a missing or malformed key costs no run.
    try:
        sign_key = _private_key(args)
    except ValueError as exc:
        print(f"[bellbriar] error: {exc}", file=sys.stderr)
        return 2

    # The domain is bound into signed statements, so it is recorded in one
    # form: lowercase ASCII, no trailing dot ("Example.COM", a URL and
    # "bücher.de" become "example.com" and "xn--bcher-kva.de").
    domain = None
    if args.domain:
        from .bundle import normalize_host
        try:
            domain = normalize_host(args.domain)
        except ValueError as exc:
            print(f"[bellbriar] error: --domain: {exc}", file=sys.stderr)
            return 2

    outputs = (("--json", args.json_out), ("--html", args.html_out),
               ("--bundle", args.bundle_out),
               ("--save-snapshot", args.save_snapshot))
    if args.save_snapshot and _not_regular(args.save_snapshot) \
            and not os.path.isdir(args.save_snapshot):
        # A snapshot is written as a new regular file (_write_fresh): one
        # never replaces a link, a device or a pipe (R5H-5).
        print(f"[bellbriar] error: cannot write {args.save_snapshot} "
              "(--save-snapshot): it is not a regular file (a link, a device "
              "or a pipe), and a snapshot is written only as one",
              file=sys.stderr)
        return 2
    for flag, out in outputs:
        why = _unwritable(out) if out else None
        if why:
            print(f"[bellbriar] error: cannot write {out} ({flag}): {why}",
                  file=sys.stderr)
            return 2
    # Two outputs written to one file: the later would replace the earlier,
    # and a bundle that overwrote the snapshot it hashes would identify
    # bytes no one holds (R5B-14). Compared as the file system will find
    # them (a link, a hard link: R5D-8), before anything runs.
    seen: dict = {}
    for flag, out in outputs:
        if not out:
            continue
        where = _file_identity(out)
        if where in seen:
            print(f"[bellbriar] error: {seen[where]} and {flag} name the same "
                  f"file ({out}): each output needs a file of its own",
                  file=sys.stderr)
            return 2
        seen[where] = flag
    if args.save_snapshots:
        # The folder holds the snapshots alone: an output written into it
        # could take a snapshot's name and replace it (R5D-8).
        root = os.path.normcase(os.path.realpath(args.save_snapshots))
        for flag, out in outputs:
            if not out:
                continue
            real = os.path.normcase(os.path.realpath(out))
            if real == root or real.startswith(root.rstrip(os.sep) + os.sep):
                print(f"[bellbriar] error: {flag} names a file in the "
                      "--save-snapshots folder, which holds the snapshots "
                      "alone", file=sys.stderr)
                return 2
    if args.save_snapshots:
        folder = Path(args.save_snapshots)
        why = ("it is not a directory" if folder.exists() and
               not folder.is_dir() else "no such directory"
               if not folder.parent.is_dir() else None)
        if why:
            print(f"[bellbriar] error: cannot write snapshots into "
                  f"{args.save_snapshots}: {why}", file=sys.stderr)
            return 2

    files: list[Path] = []
    names: list[str] = []
    #: Each page's capture (fetch.FetchResult), or None for a page that
    #: could not be fetched: URL and --render runs.
    captures: list = []
    #: The files a --render run's server sent besides the pages (inputs).
    served: list = []
    # Secrets to keep out of anything printed: the URLs' parameter values
    # and the --http-user password. Every URL the run records is redacted at
    # capture (fetch.FetchResult); this covers messages that quote one.
    from .redact import redact_text, secret_values
    keep = tuple(args.record_query)
    scrub: set = set()
    #: The --http-user password, once read: the console never shows it,
    #: whatever its shape (R5N-3).
    passwords: list = []

    def safe(text):
        out = redact_text(text, scrub, keep)
        for password in passwords:
            out = _without_password(out, password)
        return out

    try:
        rulebook = load_rulebook(args.rulebook)
        validate_rulebook(rulebook)     # URL runs too, not only file runs
        if url_run:
            from . import fetch as F
            for u in [*args.url, args.sitemap or ""]:
                scrub |= secret_values(u, keep)
            credentials = _http_credentials(args)
            tokens: set = set()
            if credentials:
                from .redact import basic_auth_tokens
                scrub.add(credentials[1])
                passwords.append(credentials[1])
                # The Authorization header that carries them, which a page
                # may echo (R6A-1).
                tokens = basic_auth_tokens(*credentials)
                scrub |= tokens
                _check_password_urls(credentials,
                                     [*args.url, args.sitemap or ""])
            urls, listing = _url_list(args, credentials, keep)
            if credentials:
                _check_password_urls(credentials, urls)
            for u in urls:
                scrub |= secret_values(u, keep)
                F.check_scheme(u)           # a URL with a password first
                if args.bundle_out:
                    _check_recordable_host(u)
            # Kept out of every snippet, message and locator the rules
            # write, before they are cut (R5E-1 to R5E-3, R5E-10).
            from .redact import set_run_secrets
            set_run_secrets(scrub, (credentials[1],) if credentials else (),
                            tokens=tokens)
            origins = {F.url_origin(u) for u in urls}
            if args.sitemap:
                # The sitemap's own origin too: pages it lists on its host
                # over plain http would get the password in clear text.
                origins.add(F.url_origin(args.sitemap))
            if credentials and len(origins) > 1:
                raise ValueError(
                    "--http-user credentials are offered to one origin, and "
                    "these URLs have several (" + ", ".join(sorted(origins))
                    + "); run each origin on its own")
            run, captures, stop = _run_urls(args, urls, listing, rulebook,
                                            domain, credentials, keep, safe)
            if stop is not None:
                return stop
        else:
            collected = _collect(args.paths)
            if not collected:
                ap.error("no HTML files found; pass paths or --url")
            if len(collected) > args.max_pages and args.render:
                raise ValueError(
                    f"{len(collected)} pages to render, more than --max-pages "
                    f"({args.max_pages}); raise it, or pass fewer paths")
            files = [f for f, _ in collected]
            names = [n for _, n in collected]
            # An output written over an input would leave the bundle the
            # hash of bytes no one holds (R5D-8).
            inputs_at = {_file_identity(f): f for f in files}
            for flag, out in outputs:
                if out and _file_identity(out) in inputs_at:
                    raise ValueError(f"{flag} names a file this run evaluates "
                                     f"({out}): write the output elsewhere")
            if args.render:
                run, captures, served, served_files = _run_build(
                    args, collected, rulebook, safe)
                # Nor over a file the build server sent: the bundle lists
                # it by its hash (R5E-7). Known only once it was served.
                sent_at = {_file_identity(f): f for f in served_files}
                for flag, out in outputs:
                    if out and _file_identity(out) in sent_at:
                        raise ValueError(
                            f"{flag} names a file the build server sent the "
                            f"browser ({out}): write the output elsewhere")
                inputs_at.update(sent_at)
            else:
                print(f"[bellbriar] evaluated {len(files)} file(s)",
                      file=sys.stderr)
                run = run_paths(files, rulebook,
                                provenance_attr=args.provenance_attr,
                                names=names, reader=args.read_as)
            # And no snapshot replaces one either.
            _check_snapshot_targets(args, run["pages"], captures, inputs_at)
        _save_snapshots(args, run["pages"], captures)
        withheld = _scrub_findings(run["pages"], scrub)
        if withheld:
            print(f"[bellbriar] warning: {withheld} finding(s) quoted the "
                  "--http-user password, so a snippet, locator or message "
                  "of theirs is withheld; each still shows a reader of the "
                  "report or bundle that the password is in the text "
                  "there. Use a long random password for the site, which "
                  "no page holds.", file=sys.stderr)
    except Exception as exc:  # noqa: BLE001 — CLI boundary
        print(f"[bellbriar] error: {safe(str(exc))}", file=sys.stderr)
        return 2

    site = score_site(run["pages"], rulebook)

    # Console summary.
    print(f"bellbriar-harness {__version__} · rulebook "
          f"{run['rulebook_version']} (sha256 {run['rulebook_sha256'][:16]}…"
          + ("" if run.get("rulebook_bundled") else
             ", not the rulebook this harness ships") + ")")
    print("layers: " + ", ".join(f"{l['layer']}={l['status']}"
                                 for l in run["layers"]))
    # The note the run actually carries, not the generic one: a rendered or
    # server-only fetch changes what this sentence must say, and the console
    # must not disagree with the bundle.
    print(run["coverage_note"])
    print("-" * 72)
    for page, ps in zip(run["pages"], site["pages"]):
        # The Tier-1 rules that ran on this page: in a run that rendered
        # some pages and not others, fewer on the others (QR-8).
        t1 = (f"{ps.get('tier1_rules_executed', site['tier1_rules_executed'])}"
              f"/{site['tier1_rules_total']}")
        if ps["tier1_clean"] is None and ps["evaluable"] and page.errors():
            # The other rules ran; a Tier-1 rule that raised leaves the
            # page's Tier-1 status undecided (P2-12).
            flag = f"T1 ERROR [{t1}]"
        elif ps["tier1_clean"] is None and ps["evaluable"] and not \
                ps.get("tier1_rules_executed"):
            # The page was read, but no Tier-1 rule ran on it (P1-08).
            flag = f"NO T1 RULE RAN [{t1}]"
        elif ps["tier1_clean"] is None and ps["evaluable"]:
            # Tier-1 rules ran, but none that can fail applied (R1A-2).
            flag = f"T1 UNDECIDED [{t1}]"
        elif ps["tier1_clean"] is None:
            flag = f"NOT EVALUATED [{t1}]"
        elif ps["tier1_clean"]:
            flag = f"T1 clean [{t1}]"
        else:
            flag = f"T1 FAIL  [{t1}]"
        print(f"{flag}  rate={_pct(ps['weighted_pass_rate'])}  "
              f"fails={ps['fail_findings']:<3} review="
              f"{ps['needs_review_findings']:<3} "
              f"{_shown(safe(page.path), 500)}")
    print("-" * 72)
    shells = [(page.path, ps["not_evaluable_reason"])
              for page, ps in zip(run["pages"], site["pages"])
              if not ps["evaluable"]]
    for path, why in shells:
        print(f"[bellbriar] WARNING: {_shown(safe(path), 500)} was NOT "
              f"evaluated — {why}", file=sys.stderr)
    print(f"site weighted pass rate: {_pct(site['site_weighted_pass_rate'])}"
          f"   pages tier1-clean: {_pct(site['pct_pages_tier1_clean'])}")
    unevaluated = site.get("pages_not_evaluable") or 0
    if 0 < unevaluated < len(site["pages"]):
        # Name the denominators, so a run with a page left out does not
        # read as all of it clean (H6-11).
        decided = sum(1 for ps in site["pages"]
                      if ps["tier1_clean"] is not None)
        print(f"  {unevaluated} of {len(site['pages'])} page(s) NOT "
              "evaluated: the pass rate leaves them out, and the tier-1-clean "
              f"share counts only the {decided} page(s) whose Tier-1 result "
              "is known.")
    ran, total = site["tier1_rules_executed"], site["tier1_rules_total"]
    review_only = site.get("tier1_rules_review_only", 0)
    if not ran:
        print(f"tier-1 coverage: no tier-1 rule executed in this run (0 of "
              f"{total}), so no page is Tier-1 clean: it is undecided.")
    elif ran == review_only:
        print(f"tier-1 coverage: {ran} of {total} tier-1 rules executed by "
              "this run, and none of them can fail (they list findings for "
              "review), so no page is Tier-1 clean: it is undecided.")
    else:
        print(f"tier-1 coverage: {ran} of {total} tier-1 rules executed by this "
              "run" + ("" if all(ps.get("tier1_rules_executed") == ran
                                for ps in site["pages"]) else
                       " (on at least one of its pages; each page's [n/"
                       f"{total}] says how many ran there)")
              + (f"; {review_only} of them never fail, they list findings "
                 "for review" if review_only else "")
              + ". 'T1 clean' means no failure among "
              + (f"the {ran - review_only} that can fail" if review_only
                 else "those")
              + f". The other {total - ran} need layers this run did not "
              "execute.")
        undecided = sum(1 for page, ps in zip(run["pages"], site["pages"])
                        if ps["tier1_clean"] is None and ps["evaluable"]
                        and ps.get("tier1_rules_executed")
                        and not page.errors())
        if undecided:
            print(f"  T1 UNDECIDED: on {undecided} page(s) no tier-1 rule "
                  "that can fail applied, so 'clean' there would be a pass "
                  "on nothing.")
    if site["site_weighted_pass_rate"] is None:
        if not any(ps["evaluable"] for ps in site["pages"]):
            print("  NO PASS RATE (no page was evaluated): this is not 0% "
                  "and not 100%.")
        else:
            print("  NO PASS RATE (no applicable rules): this is not 0% and "
                  "not 100% — the executed layers had nothing to measure "
                  "here.")
    if site["rule_fail_totals"]:
        worst = ", ".join(f"{k}×{v}" for k, v in
                          list(site["rule_fail_totals"].items())[:6])
        print(f"top failing rules: {worst}")
    if baseline is not None:
        _say_baseline(baseline, run, args.fail_on, args.strict)
    held = _strict_findings(run["pages"], rulebook, args.fail_on)
    if held:
        # With a baseline, --strict counts only the ones it does not list
        # (R4B-5): say which, as the gate will count them.
        counted = (_gate_findings(run["pages"], rulebook, args.fail_on, True,
                                  baseline)[1] if args.strict else [])
        print(f"not WCAG failures on their own: {len(held)} finding(s) pled "
              "in complaints or best practices, listed for review — "
              + ("--strict fails the gate on them." if not args.strict else
                 "failing the gate (--strict)." if baseline is None else
                 f"{len(counted)} of them not in the baseline, and --strict "
                 "fails the gate on those."))
    cross = sum(1 for page in run["pages"] for rr in page.results
                for f in rr.findings if f.origin == "cross-origin")
    if cross:
        print(f"cross-origin: {cross} finding(s) sit in markup inserted by "
              "cross-origin scripts that are not known vendors (your CDN, or "
              "a library you load). They are scored as yours; if one is a "
              "vendor's widget, pass --third-party-origin.")
    third_fails = site.get("total_third_party_fail_findings") or 0
    third_reviews = site.get("total_third_party_needs_review") or 0
    if third_fails or third_reviews:
        what = " and ".join(x for x in (
            f"{third_fails} failure(s)" if third_fails else "",
            f"{third_reviews} review item(s)" if third_reviews else "") if x)
        print(f"third-party: {what} in markup injected by vendor scripts "
              "(consent banners, chat widgets). Reported, not counted as "
              "yours — you cannot edit them. Residual duties: ask the vendor "
              "for a current VPAT/ACR, keep a first-party path to every "
              "essential task, and record the decision.")
    errors = [(page.path, rid, err) for page in run["pages"]
              for rid, err in page.errors()]
    for path, rid, err in errors:
        if rid == "(the page)":
            print(f"[bellbriar] ERROR: {safe(path)} could not be evaluated "
                  f"({safe(err)}); its result is unknown, not a pass.",
                  file=sys.stderr)
        else:
            print(f"[bellbriar] ERROR: {rid} raised on {safe(path)} "
                  f"({safe(err)}); its result there is unknown, not a pass.",
                  file=sys.stderr)

    # One record for both reports, so they never disagree. A report that
    # cannot be made or written is a run error (2), never the gate failing
    # (1), whatever --fail-on says; the other report is still written, and
    # no bundle is (R3C-9, R3D-7).
    report = None
    made_all = True
    for out, label, kind in ((args.json_out, "json report", "json"),
                             (args.html_out, "html report", "html")):
        if not out:
            continue
        why = None
        try:
            if report is None:
                report = _serialize(run, site, None, baseline)
            data = (json.dumps(report, indent=2).encode("utf-8")
                    if kind == "json" else
                    # A name that is not valid UTF-8 (a file name's
                    # undecodable bytes) is written as a replacement
                    # character (R3A-11).
                    render(report).encode("utf-8", "replace"))
        except Exception as exc:  # noqa: BLE001 — CLI boundary
            print(f"[bellbriar] error: the {label} could not be made "
                  f"({type(exc).__name__}: {safe(str(exc))[:200]}); this is "
                  "a harness bug: please report it with the page.",
                  file=sys.stderr)
            why = "made"
        else:
            failed = _write(out, data)
            if failed:
                print(f"[bellbriar] error: cannot write {out}: {failed}",
                      file=sys.stderr)
                why = "written"
        if why:
            made_all = False
            # A file already at this path could pass for this run's report,
            # beside this run's other one: it is left as it is, but named.
            if _older_file(out):
                print(f"[bellbriar] error: the {label} could not be {why}: "
                      f"whatever {out} holds is not this run's {label}.",
                      file=sys.stderr)
            continue
        print(f"{label}: {out}")
    if not made_all:
        if args.bundle_out:
            print(f"[bellbriar] error: no evidence bundle was written to "
                  f"{args.bundle_out}, because a report of this run could "
                  "not be made or written." + _stale(args), file=sys.stderr)
        return 2

    if errors:
        # An incomplete run is not evidence: the bundle would sign a
        # measurement with holes in it. The reports above say what ran.
        raised = any(rid != "(the page)" for _p, rid, _e in errors)
        print(f"[bellbriar] error: {len(errors)} rule run(s) or page(s) could "
              "not be evaluated (listed above), so this run is incomplete"
              + ("; refusing to write the evidence bundle"
                 if args.bundle_out else "")
              # A page refused for what it is (an error page, one that went
              # elsewhere) is no bug; a rule that raised is (H6-20).
              + (". A rule that raised an error is a harness bug: please "
                 "report it with the page." if raised else
                 ". Each page's line above says why it was not evaluated.")
              + _stale(args), file=sys.stderr)
        return 2

    # A run that cannot pass for want of anything to gate on exits 2, and
    # writes no evidence bundle: a signed bundle of it would read as a
    # measurement (R5B-15). Decided before the bundle, never after it. A
    # failed gate (1) is evidence of the failure, and keeps its bundle.
    gate_failed = _gate_failed(rulebook, args.fail_on, pages=run["pages"],
                               strict=args.strict, baseline=baseline)
    refusal = None
    if not gate_failed and shells and len(shells) == len(run["pages"]):
        # Nothing the gate could evaluate. Passing here is how a
        # client-rendered site used to go green with nothing measured. What
        # to do depends on how the pages were read: telling a run that
        # already rendered them to render them sends it in a circle (N27).
        refusal = ("[bellbriar] error: no page could be evaluated: "
                   + _no_page_why(run["pages"], args, url_run)
                   + " This is not a pass.")
    elif not gate_failed and args.fail_on != "never" and all(
            ps["tier1_clean"] is None for ps in site["pages"]):
        # "T1 clean [0/0]" is how a rulebook that demotes every Tier-1 rule
        # used to pass the gate (P1-08), and "T1 clean [3/3]" how one that
        # keeps only rules that never fail still did (R1A-2): no page has a
        # Tier-1 status to gate on.
        why = ("this run executed no Tier-1 rule" if not
               site["tier1_rules_executed"] else
               "no Tier-1 rule that can fail applied to any page of this run")
        refusal = (f"[bellbriar] error: {why}, so it cannot pass a gate that "
                   "counts Tier-1 failures. This is not a pass."
                   + ("" if run.get("rulebook_bundled") else
                      " Its rulebook is not the one this harness ships "
                      "(--rulebook): check its tiers."))
    if refusal:
        print(refusal + (f" No evidence bundle was written to "
                         f"{args.bundle_out}." if args.bundle_out else "")
              + _stale(args), file=sys.stderr)
        return 2

    # Evidence bundle, and its self-signed signature.
    if args.bundle_out:
        from .bundle import (MAX_BUNDLE_FILE, build_bundle,
                             bundle_bound_values, bundle_digest, check_body,
                             sign_bundle_local)
        if captures and not (args.save_snapshot or args.save_snapshots):
            print("[bellbriar] warning: bundling a captured run without "
                  "--save-snapshot(s). The bundle records each snapshot's "
                  "hash, but nobody will hold the bytes it identifies.",
                  file=sys.stderr)
        if url_run:
            inputs = [fr.manifest_entry() for fr in captures if fr is not None]
        else:
            from .bundle import input_manifest
            # Each file as the run read it (or its server sent it) when it
            # evaluated it, not as it is now (R5B-10).
            digests = [getattr(pg, "input_digest", None)
                       for pg in run["pages"]]
            inputs = input_manifest(files, names or None,
                                    digests if len(digests) == len(files)
                                    else None) + served
        from . import baseline as BL
        from .report import baseline_counts
        bundle = build_bundle(
            run, site, files, domain=domain, names=names or None,
            inputs=inputs,
            baseline=(BL.record(baseline, *baseline_counts(
                run["pages"], rulebook, baseline))
                      if baseline is not None else None))
        if not isinstance(bundle.get("rulebook_version"), str):
            # A custom rulebook may leave it out; a bundle may not (R5D-6).
            print("[bellbriar] cannot build the evidence bundle: the "
                  "rulebook gives no rulebook_version (a string such as "
                  "\"1.0.0\"), which every bundle records and its signature "
                  "binds; no bundle was written." + _stale(args),
                  file=sys.stderr)
            return 2
        try:
            bundle_digest(bundle)
            # What verify checks of the body, before anything is signed: a
            # rulebook without a version made a bundle the harness signed
            # and its own verifier refused (R5D-6).
            check_body(bundle)
            bundle_bound_values(bundle)     # e.g. a final_url with no host
        except (ValueError, TypeError) as exc:
            # Refuse to write evidence no verifier could check. Exit 2, not
            # 1: this is not the gate failing.
            print(f"[bellbriar] cannot build the evidence bundle: {exc}. "
                  "No bundle was written." + _stale(args), file=sys.stderr)
            return 2
        if sign_key is not None:
            try:
                bundle = sign_bundle_local(bundle, sign_key)
            except Exception as exc:  # noqa: BLE001
                print(f"[bellbriar] signing error: {type(exc).__name__}; "
                      "no bundle was written." + _stale(args),
                      file=sys.stderr)
                return 2
        data = json.dumps(bundle, indent=2).encode("utf-8")
        if len(data) > MAX_BUNDLE_FILE:
            # A verifier reads no file this large (R5D-14).
            print(f"[bellbriar] error: the evidence bundle would be "
                  f"{len(data):,} bytes, more than the {MAX_BUNDLE_FILE:,} "
                  "bellbriar-evidence verify reads; no bundle was written: "
                  "split the run." + _stale(args), file=sys.stderr)
            return 2
        why = _write(args.bundle_out, data)
        if why:
            print(f"[bellbriar] error: cannot write {args.bundle_out}: {why}"
                  + (" (the signature was made and is lost)"
                     if bundle.get("signature") else "")
                  + (f". Whatever {args.bundle_out} holds is not this run's "
                     "bundle." if _older_file(args.bundle_out) else ""),
                  file=sys.stderr)
            _said()                 # said once (R5J-7)
            return 2
        written = _BUNDLE_STATE.get()
        if written is not None:
            written["written"] = True
        sig = bundle.get("signature")
        stmt = (sig or {}).get("statement") or {}
        state = (f"signed by {stmt.get('signer','?')} "
                 f"[{stmt.get('attestation_class','?')}] "
                 f"(key {sig['key_id']})" if sig else "UNSIGNED")
        print(f"evidence bundle: {args.bundle_out} "
              f"[digest {bundle_digest(bundle)[:16]}… · {state}]")
        if not sig:
            print("  note: an unsigned bundle shows nothing about who made "
                  "it; --sign-key FILE signs it (self-signed: who signed, "
                  "and that nothing changed since).")

    return 1 if gate_failed else 0
