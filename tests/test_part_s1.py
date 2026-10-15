"""Part S, step 1: the run's secrets in more spellings, and the searches
for them sound and linear.

  R6G-1  the pre-check that picks which secrets a text is searched for
         left out ones the search finds: a reference begun before a token
         that ends inside it (`&#x26;sec` before "t…"), `&#113` with no
         ";" before a script's escape of a digit, the rest of an escaped
         "&" before a name. It now reads a text in one pass, a spelling at
         a time, as the search does; a page's reference of more than 4,300
         digits no longer stops the run.
  R6G-2  a search was quadratic over a long run of backslashes.
  R6G-5  a token in CSS's escapes, a script's `\\u{...}` or octal escapes,
         and a password's white space as JSON's `\\t`, were not found.
  R6G-6  a secret or password with many backslashes in a row made a near
         miss exponential.
"""
import html
import json
import random
import sys
import time
import unittest
from html.entities import html5
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bellbriar_harness import bundle as B                          # noqa: E402
from bellbriar_harness import redact as R                          # noqa: E402
from tests.test_fetch_hardening import _Site                       # noqa: E402
from tests.test_part_r5 import PAGE, run, tmpdir                   # noqa: E402

BS = "\\"


class _Secrets:
    """set_run_secrets for the length of a with block."""

    def __init__(self, secrets=(), passwords=()):
        self.args = (secrets, passwords)

    def __enter__(self):
        self.token = R.set_run_secrets(*self.args)

    def __exit__(self, *exc):
        R.reset_run_secrets(self.token)


# ---------------------------------------------------------------- R6G-1

#: (secret, text): each a text the pre-check left the secret out of while
#: the search over all secrets found it there.
LEFT_OUT = (
    # `&#x26;sec` is "&sec"; read with the token's "t", "&sect" is a
    # legacy name, which took the "t".
    ("tX4hSCtK-Qt9", "&#x26;sect&#38;#88&#x26;#052;hSCtK-Qt9"),
    # `&#113` with no ";" ends where the backslash starts; read after the
    # script's escape, it was `&#1135`.
    ("Zq5mnopqrs", "Z&#113" + BS + "u0035mnopqrs"),
    # "6copy" after `\u002`: read as one, `&copy` is "&copy".
    ("6copyABCDEFG", BS + "u0026copy&#65;BCDEFG"),
    # The same with "&" escaped as `\x26` in markup.
    ("26notWXYZ12345", BS + "x26not&#87;XYZ12345"),
)


class TestThePreCheck(unittest.TestCase):
    """R6G-1."""

    def test_what_it_left_out_is_found(self):
        for secret, text in LEFT_OUT:
            with self.subTest(secret=secret), _Secrets([secret]):
                self.assertTrue(R.holds_secret(text))
                scrubbed = R.scrub_secrets(text)
                self.assertIn(R.REDACTED, scrubbed)
                self.assertFalse(R.holds_secret(scrubbed), scrubbed)
                self.assertNotIn(secret[-6:], scrubbed)

    def test_it_never_leaves_out_what_the_search_finds(self):
        """For secrets that start as an escape before them could read
        them, spelled in every way the search reads, after the start of
        every kind of escape: what the search over each secret finds, the
        pre-check keeps."""
        rnd = random.Random(20261014)
        missed = []
        for secret in _secrets(rnd, 60):
            pattern = R._secrets_regex((secret,))
            for _ in range(25):
                family = rnd.choice("JC")
                after = rnd.choice(_AFTER)
                body = _spelled(rnd, secret, after, family)
                text = _before(rnd) + body + after
                self.assertIsNotNone(pattern.search(body + " "),
                                     f"{secret!r} unread in {body!r}")
                if pattern.search(text) and \
                        secret not in R._hits((secret,), text):
                    missed.append((secret, text))
        self.assertEqual(missed, [])

    def test_a_long_number_does_not_stop_a_run(self):
        """int() refuses a number of more than 4,300 digits: the pre-check
        read a page's reference with one and stopped the run."""
        with _Secrets(["tok-ABCDEFGH12"]):
            for ref in ("&#" + "1" * 5000 + ";", "&#x" + "f" * 5000 + ";",
                        "&#" + "0" * 5000 + "65;"):
                with self.subTest(ref=ref[:4]):
                    text = f'<p title="{ref}">tok-ABCD&#69;FGH12</p>'
                    self.assertNotIn("FGH12", R.scrub_secrets(text))

    def test_a_run_records_none_of_it(self):
        """A page that writes its URL token as the first case above: the
        reports and the signed bundle hold it in no spelling, and the
        bundle verifies."""
        token, spelled = LEFT_OUT[0]
        site = _Site({"/p": _page(f'<a href="/x" data-x="{spelled}"></a>')})
        self.addCleanup(site.stop)
        d = tmpdir(self)
        argv = ["--url", f"{site.base}/p?token={token}", "--no-render",
                "--json", d / "r.json", "--html", d / "r.html",
                "--bundle", d / "b.json", "--fail-on", "never"]
        priv, pub = None, None
        if B.HAVE_ED25519:
            priv, pub, _ = B.generate_keypair()
            key = d / "k.key"
            key.write_text(priv)
            key.chmod(0o600)
            argv += ["--sign-key", key]
        code, out, err = run(*argv)
        self.assertEqual(code, 0, err)
        report = json.loads((d / "r.json").read_text(encoding="utf-8"))
        snippets = [f["snippet"] for p in report["pages"]
                    for f in p["findings"]]
        self.assertTrue(any("data-x=" in s and R.REDACTED in s
                            for s in snippets), snippets)
        anywhere = R.secrets_pattern([token])
        for name in ("r.json", "r.html", "b.json"):
            text = (d / name).read_text(encoding="utf-8")
            self.assertIsNone(anywhere.search(text), name)
        self.assertIsNone(anywhere.search(out + err))
        if priv:
            ok, why = B.verify_bundle(B.read_bundle(d / "b.json"), pub)
            self.assertTrue(ok, why)


def _page(body: str):
    data = PAGE.format(body).encode()

    def answer(h):
        h.send_response(200)
        h.send_header("Content-Type", "text/html")
        h.send_header("Content-Length", str(len(data)))
        h.end_headers()
        h.wfile.write(data)
    return answer


_PLAIN = ("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
          "-_.~=+/")
_LEGACY = sorted(n for n in html5 if not n.endswith(";"))
#: What a secret may start with that an escape before it could read.
_STARTS = (["41ab", "u002541", "x2541", "2541", "101", "55", "u0041", "x41",
            "X41", "6copy", "26not", "u0026copy", "x26lt", "026reg",
            "0026sect", "u0025", "x2"]
           + [n[j:] for n in _LEGACY for j in range(len(n))])
#: Escapes whose starts the text may hold just before a secret.
_ESCAPES = (["&" + n for n in _LEGACY] + [BS + "u0026" + n for n in _LEGACY]
            + ["&amp;" + n for n in _LEGACY]
            + ["%2541", BS + "u002541", BS * 2 + "u002541", BS + "x2541",
               "&#37;2541", "&percnt;41", "&#65;", "&#x41;", "&#X41",
               "&#00065", BS + "u0041", BS + "x41", BS + "u{00041}",
               BS + "101", BS + "55", BS + "41 ", BS + "000041", BS + "-",
               "&#x26;#65;", BS + "u0026#65;", BS + "u0026amp;#x41;",
               "&#38;#38;#65;", "&lowbar;", BS + "u0026#37;41"])
_AFTER = ("", "", "5", "a", BS + "u0035", BS + "x35", "%35", "&#53;", ";",
          "b", "0", "&#x35;", " tail", "\t", "}", BS + "61 ")
_NAMED = {"_": "&lowbar;", ".": "&period;", "=": "&equals;", "+": "&plus;",
          "/": "&sol;"}
_HEX = "0123456789abcdefABCDEF"


def _secrets(rnd, n):
    out = []
    for _ in range(n):
        start = rnd.choice(_STARTS) if rnd.random() < .6 else ""
        out.append(start + "".join(rnd.choice(_PLAIN)
                                   for _ in range(rnd.randrange(6, 14))))
    return out


def _before(rnd):
    if rnd.random() < .2:
        return ""
    escape = rnd.choice(_ESCAPES)
    return escape[:rnd.randrange(1, len(escape))]


def _spelled(rnd, secret, after, family):
    """`secret` with each character spelled in one of the ways the search
    reads, with the backslash escapes of `family`."""
    out, nxt = [], after
    for c in reversed(secret):
        out.append(_spell(rnd, c, nxt, family))
        nxt = out[-1] + nxt
    return "".join(reversed(out))


def _spell(rnd, c, nxt, family):
    n = ord(c)
    bs = BS * rnd.choice((1, 1, 2, 4))
    amp = rnd.choice(["&", "&", bs + "u0026", bs + "x26", "&amp;", "&#38;"])
    pct = rnd.choice(["%", "%", bs + "u0025", bs + "x25", amp + "#37;",
                      amp + "percnt;"]) + "25" * rnd.choice((0, 0, 1))
    hexa = "".join(d.upper() if rnd.random() < .5 else d for d in f"{n:x}")
    forms = ["lit", "lit", "pct", "dec", "hex", "u4", "x2", "u6",
             "oct" if family == "J" else "css"]
    if c in "ghijklmopqswyzGHIJKLMOPQSWYZ-_.~=+/":
        forms.append("id")
    if c in _NAMED:
        forms.append("name")
    form = rnd.choice(forms)
    first = nxt[:1]
    if form == "pct":
        return pct + f"{n:02x}"
    if form == "dec":
        return amp + f"#0{n}" + (";" if first.isdigit() or first == ""
                                 else rnd.choice(("", ";")))
    if form == "hex":
        return amp + f"#x{hexa}" + (";" if first in _HEX
                                    else rnd.choice(("", ";")))
    if form == "u4":
        return bs + f"u{n:04x}"
    if form == "x2":
        return bs + f"x{n:02X}"
    if form == "u6":
        return bs + "u{00" + hexa + "}"
    if form == "oct":
        return bs + f"{n:03o}"
    if form == "css":
        tail = " " if first in _HEX or first in " \t\n\r\f" \
            else rnd.choice(("", " ", "\r\n"))
        return bs + "0" * rnd.randrange(0, 7 - len(hexa)) + hexa + tail
    if form == "id":
        return bs + c
    if form == "name":
        return amp + _NAMED[c][1:]
    return c


# ---------------------------------------------------------------- R6G-2

class TestLongRunsOfBackslashes(unittest.TestCase):
    """R6G-2: a search tries a run of backslashes once."""

    def test_linear(self):
        text = BS * 200000 + "z"
        with _Secrets(["Zk3-9fQ!x", "tok-N1secret-91bd"], ["hunter22pw"]):
            for name, search in (
                    ("scrub", R.scrub_secrets), ("holds", R.holds_secret),
                    ("in any case", lambda t: R.holds_secret(t, True)),
                    ("password", R.holds_password)):
                with self.subTest(name):
                    start = time.monotonic()
                    search(text)
                    self.assertLess(time.monotonic() - start, 3.0)

    def test_an_escape_after_a_run_is_still_read(self):
        with _Secrets(["tok-N1secret-91bd"]):
            text = "x" + BS * 7 + "u0074ok-N1secret-91bd"
            self.assertTrue(R.holds_secret(text))
            self.assertNotIn("N1secret", R.scrub_secrets(text))


# ---------------------------------------------------------------- R6G-5

TOKEN = "tok-N1secret-91bd"


def _css(s, tail=" "):
    return "".join(f"{BS}{ord(c):x}{tail}" for c in s)


class TestMoreSpellings(unittest.TestCase):
    """R6G-5."""

    def test_css_escapes(self):
        cases = (_css(TOKEN), _css(TOKEN, "\r\n"),
                 "".join(f"{BS}{ord(c):06x}" for c in TOKEN),
                 "tok" + BS + "2d" + " N1secret-91bd",
                 "tok" + BS + "-N1secret" + BS + "-91bd",
                 "tok-N1secret-9" + BS + "31 bd",
                 "url(/a?t=" + BS + "74 ok-N1secret-91bd)")
        with _Secrets([TOKEN]):
            for text in cases:
                with self.subTest(text=text):
                    self.assertTrue(R.holds_secret(text))
                    self.assertFalse(R.holds_secret(R.scrub_secrets(text)))

    def test_a_scripts_escapes(self):
        cases = ("".join(BS + "u{" + f"{ord(c):x}" + "}" for c in TOKEN),
                 "tok" + BS + "u{00002d}N1secret-91bd",
                 "".join(f"{BS}{ord(c):03o}" for c in TOKEN),
                 "tok" + BS + "55N1secret" + BS + "5591bd",
                 "tok-" + BS * 2 + "116" + "1secret-91bd")
        with _Secrets([TOKEN]):
            for text in cases:
                with self.subTest(text=text):
                    self.assertTrue(R.holds_secret(text))
                    self.assertFalse(R.holds_secret(R.scrub_secrets(text)))

    def test_a_hex_digit_after_a_css_escape_is_part_of_it(self):
        """CSS reads `\\74ok` as U+074 and "ok", but `\\74 6f` as "t" and
        U+06F: the search reads them as CSS does."""
        with _Secrets([TOKEN]):
            self.assertFalse(R.holds_secret(BS + "746f" + "k-N1secret-91bd"))
            self.assertTrue(R.holds_secret(BS + "74 " + BS + "6f k-N1secret"
                                           "-91bd"))

    def test_octal_and_css_escapes_together_are_not_read(self):
        """CSS reads `\\61` as "a", a script's octal escape as "1": a token
        is found in either's escapes, not in some of each (the module's
        documented limit), and the pre-check agrees with the search."""
        mixed = BS + "164ok-N1secret-9" + BS + "31 bd"   # octal t, CSS 1
        with _Secrets([TOKEN]):
            self.assertFalse(R.holds_secret(mixed))
        self.assertIsNone(R._secrets_regex((TOKEN,)).search(mixed))

    def test_a_passwords_white_space_as_json_writes_it(self):
        with _Secrets(passwords=["correct horse staple"]):
            for text in ("correct" + BS + "thorse" + BS + "nstaple",
                         "CORRECT" + BS * 2 + "thorse staple",
                         "correct" + BS + "u0009horse" + BS + "r" + BS
                         + "nstaple",
                         "correct" + BS + "9 horse" + BS + "20 staple",
                         "correct" + BS + "11horse" + BS + "040staple"):
                with self.subTest(text=text):
                    self.assertTrue(R.holds_password(text))

    def test_a_passwords_characters_as_css_and_a_script_write_them(self):
        with _Secrets(passwords=["P4ss-word!"]):
            for text in (_css("P4ss-word!"), BS + "u{50}4ss-word!",
                         "P" + BS + "64ss" + BS + "-word" + BS + "!",
                         BS + "120" + "4ss-word!"):
                with self.subTest(text=text):
                    self.assertTrue(R.holds_password(text))

    def test_a_run_records_none_of_it(self):
        """A page that writes its URL token in CSS's escapes in a style
        attribute: the reports and the bundle hold it in no spelling."""
        style = "--k:" + _css(TOKEN)
        site = _Site({"/p": _page(f'<a href="/x" style="{style}"></a>')})
        self.addCleanup(site.stop)
        d = tmpdir(self)
        code, out, err = run("--url", f"{site.base}/p?token={TOKEN}",
                             "--no-render", "--json", d / "r.json",
                             "--html", d / "r.html", "--bundle",
                             d / "b.json", "--fail-on", "never")
        self.assertEqual(code, 0, err)
        report = json.loads((d / "r.json").read_text(encoding="utf-8"))
        snippets = [f["snippet"] for p in report["pages"]
                    for f in p["findings"]]
        self.assertTrue(any("--k:" in s and R.REDACTED in s
                            for s in snippets), snippets)
        anywhere = R.secrets_pattern([TOKEN])
        written = _css(TOKEN)[:40]     # as the page wrote it
        for name, text in _outputs(d):
            self.assertNotIn(written, text, name)
            self.assertIsNone(anywhere.search(text), name)
        self.assertIsNone(anywhere.search(out + err))


def _outputs(d):
    """(name, text) of each output of a run in `d`, as a reader reads it:
    the JSON files' strings decoded, the HTML report's references."""
    def strings(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for v in value.values():
                yield from strings(v)
        elif isinstance(value, list):
            for v in value:
                yield from strings(v)
    for name in ("r.json", "b.json"):
        data = json.loads((d / name).read_text(encoding="utf-8"))
        yield name, "\n".join(strings(data))
    yield "r.html", html.unescape((d / "r.html").read_text(encoding="utf-8"))


# ---------------------------------------------------------------- R6G-6

class TestBackslashesInASecret(unittest.TestCase):
    """R6G-6: a run of a secret's backslashes is read one way."""

    def test_a_near_miss_is_quick(self):
        for m in (16, 64):
            secret = "pw" + BS * m + "x1yz"
            text = "pw" + BS * (4 * m) + "x1yq"
            with self.subTest(m=m), _Secrets([secret], [secret]):
                start = time.monotonic()
                self.assertFalse(R.holds_secret(text))
                self.assertFalse(R.holds_password(text))
                self.assertLess(time.monotonic() - start, 2.0)

    def test_written_out_or_escaped(self):
        secret = "pw" + BS * 3 + "&x1yz"
        cases = {"as it is": secret,
                 "JSON": "pw" + BS * 6 + "&x1yz",
                 "JSON in JSON": "pw" + BS * 12 + "&x1yz",
                 "JSON, the next one escaped": "pw" + BS * 7 + "u0026x1yz",
                 "JSON in JSON, the next one escaped":
                     "pw" + BS * 14 + "u0026x1yz",
                 "percent-encoded": "pw%5C%5c%5C&x1yz",
                 "references": "pw&#92;&#92;&#92;&amp;x1yz",
                 "a script's escapes": "pw" + (BS + "u005c") * 3 + "&x1yz"}
        with _Secrets([secret], [secret]):
            for name, text in cases.items():
                with self.subTest(name):
                    self.assertTrue(R.holds_secret(text))
                    self.assertTrue(R.holds_password(text))
                    self.assertFalse(R.holds_secret(R.scrub_secrets(text)))


if __name__ == "__main__":
    unittest.main()
