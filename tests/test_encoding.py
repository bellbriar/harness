"""Part O, P1-12 and L22: pages are decoded as Chromium 141 decodes them.

File runs read every file as UTF-8, so a windows-1252 or UTF-16 page lost
its text, and the server fetch found a <meta charset> with a regular
expression that also matched one inside a comment, and mapped labels by
Python's codec names rather than the Encoding Standard's. encoding.py now
uses the standard's labels and single-byte indexes, and finds a <meta> as
Chromium's meta-charset scan does.

The review of Part O (OR-1) found the first version honoring metas Chromium
ignores (one in a <script> or <title>, one past the first 1 KB in the
body), so a "replacement" label there blanked the page. Every case here is
measured: tests/data/chromium-141-encoding.json holds 442 bodies (named
cases and generated ones) with the encoding Chromium 141 chose for each,
served over HTTP without a charset and opened as a local file.
"""
import base64
import json
import sys
import time
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bellbriar_harness import encoding as E                     # noqa: E402
from bellbriar_harness import fetch as F                        # noqa: E402
from bellbriar_harness.encodings_data import LABELS, SINGLE_BYTE  # noqa: E402
from bellbriar_harness.engine import run_paths                  # noqa: E402

CAFE = "caf" + chr(0xE9)
FIXTURE = ROOT / "tests" / "data" / "chromium-141-encoding.json"
#: Encodings the bodies declare one way or another. Anything else Chromium
#: answered is its own guess from the text (its legacy-encoding detector),
#: which the harness does not make.
DECLARED = {"windows-1252", "koi8-r", "iso-8859-2", "utf-8", "replacement",
            "x-user-defined"}


def cases():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for c in data["cases"]:
        yield c["name"], zlib.decompress(base64.b64decode(c["body_zlib_b64"])), \
            c["http"], c["file"]


class TestLabels(unittest.TestCase):
    def test_the_whole_standard(self):
        self.assertEqual(len(LABELS), 228)
        self.assertEqual(len(SINGLE_BYTE), 28)
        self.assertEqual(len(set(LABELS.values())), 40)

    def test_labels_as_the_standard_reads_them(self):
        for label, want in ((" Latin1\t", "windows-1252"),
                            ("us-ascii", "windows-1252"),
                            ("x-sjis", "Shift_JIS"),
                            ("ISO-8859-8-I", "ISO-8859-8-I"),
                            ("csiso2022kr", "replacement"),
                            ("unicode-1-1-utf-8", "UTF-8"),
                            ("utf-7", None), ("utf-32", None),
                            ("base64", None), ('"utf-8"', None),
                            # str.lower() would fold the Kelvin sign to "k"
                            (chr(0x212A) + "oi8-r", None)):
            with self.subTest(label=label):
                self.assertEqual(E.get_encoding(label), want)

    def test_single_byte_indexes_not_python_codecs(self):
        # windows-1252 maps 0x81 to U+0081 (Python's cp1252 has no mapping);
        # KOI8-U maps 0xAE to U+045E (Python's koi8_u: U+255D).
        self.assertEqual(E.decode(b"\x81\x80", "windows-1252"),
                         chr(0x81) + chr(0x20AC))
        self.assertEqual(E.decode(b"\xae", "KOI8-U"), chr(0x45E))
        self.assertEqual(E.decode(b"\xa5", "ISO-8859-3"), chr(0xFFFD))
        self.assertEqual(E.decode(b"\x80", "x-user-defined"), chr(0xF780))
        self.assertEqual(E.decode(b"abc", "replacement"), chr(0xFFFD))


class TestAsChromiumDecides(unittest.TestCase):
    def test_every_measured_case(self):
        n = guesses = 0
        for name, body, http, file in cases():
            for where, want, local in (("http", http, False),
                                       ("file", file, True)):
                n += 1
                got = E.sniff(body, local_file=local).encoding
                with self.subTest(case=name, where=where):
                    if want.lower() in DECLARED:
                        self.assertEqual(got.lower(), want.lower())
                    else:
                        guesses += 1          # Chromium guessed from the text
                        self.assertEqual(got, "windows-1252")
        self.assertEqual(n, 884)
        self.assertLess(guesses, n * 0.03)

    def test_what_the_scan_ignores(self):
        # One probe byte (0xE9: é in windows-1252, И in KOI8-R), so only a
        # declaration can decide. Each tail would have chosen KOI8-R in the
        # first version (OR-1); Chromium 141 ignores all of them.
        p = b"<p id=m>\xe9</p>"
        meta = b"<meta charset=koi8-r>"
        pad = b"<p>" + b"filler text " * 100 + b"</p>"
        for body in (b"<head><script>var s='" + meta + b"'</script>" + p,
                     b"<head><title>" + meta + b"</title>" + p,
                     b"<body>" + pad + meta + p,
                     b"<body>" + pad + b"<template>" + meta + b"</template>" + p,
                     b"<body>" + pad + b"<svg>" + meta + b"</svg>" + p,
                     b"<body>" + pad * 50 + meta + p):
            with self.subTest(body=body[:40]):
                self.assertEqual(E.sniff(body).encoding, "windows-1252")

    def test_a_late_meta_in_a_long_head_still_counts(self):
        # The scan stops 1 KB after the first tag that cannot be in the
        # head; a long head of styles is still head (300 KB here). The whole
        # page is decoded with it, the text before it included, as Chromium
        # decodes a file (over HTTP, Chromium decodes text that arrived in
        # an earlier network chunk as windows-1252: 4 loads in 8 at 300 KB;
        # document.characterSet is KOI8-R either way).
        style = b"<style>" + b"/*x*/" * (300 * 1024 // 5) + b"</style>"
        body = (b"<html><head><title>\xe9</title>" + style +
                b"<meta charset=koi8-r></head><body><p>\xe9</p>")
        got = E.sniff(body)
        self.assertEqual((got.encoding, got.source), ("KOI8-R", "meta"))
        self.assertEqual(got.text.count(chr(0x418)), 2)

    def test_a_replacement_label_where_chromium_reads_it(self):
        got = E.sniff(b'<meta charset="iso-2022-kr"><p>abc')
        self.assertEqual((got.encoding, got.text), ("replacement", chr(0xFFFD)))

    def test_utf8_is_detected_in_files_only(self):
        body = ("<p>" + CAFE + " " + chr(0x6F22)).encode()
        self.assertEqual(E.sniff(body, local_file=True).source,
                         "utf-8-detected")
        self.assertEqual(E.sniff(body).encoding, "windows-1252")
        # Chromium reads the first 256 KiB of a file for it.
        filler = b"<p>" + b"x" * (E.UTF8_DETECTION_BYTES - 40)
        self.assertEqual(E.sniff(filler + "é".encode(), local_file=True).encoding,
                         "UTF-8")
        late = b"<p>" + b"x" * (E.UTF8_DETECTION_BYTES + 40) + "é".encode()
        self.assertEqual(E.sniff(late, local_file=True).encoding,
                         "windows-1252")
        # A character cut in two at the window's edge is no error, and no
        # evidence either (measured in Chromium 141: UTF-8 with a whole é
        # before it, windows-1252 alone).
        edge = b"x" * (E.UTF8_DETECTION_BYTES - 1) + "é".encode() + b"x"
        self.assertEqual(E.sniff(edge, local_file=True).encoding,
                         "windows-1252")
        edge = "é".encode() + edge[2:]
        self.assertEqual(E.sniff(edge, local_file=True).encoding, "UTF-8")
        # Not UTF-8 at all: a lone 0xE9 beside a valid é.
        self.assertEqual(E.sniff("é".encode() + b"\xe9",
                                 local_file=True).encoding, "windows-1252")

    def test_precedence(self):
        p = b"<meta charset=koi8-r><p>\xe9"
        self.assertEqual(E.sniff(b"\xef\xbb\xbf" + p, "iso-8859-2").source, "bom")
        self.assertEqual(E.sniff(p, "iso-8859-2").encoding, "ISO-8859-2")
        self.assertEqual(E.sniff(p, "utf-7").encoding, "KOI8-R")
        got = E.sniff(b"\xff\xfe" + ("<p>" + CAFE).encode("utf-16-le"))
        self.assertEqual((got.encoding, got.text), ("UTF-16LE", "<p>" + CAFE))
        self.assertEqual(E.sniff(b"<?xml version='1.0' encoding='koi8-r'?>"
                                 b"<p>\xe9").source, "xml-declaration")
        # UTF-16 without a byte-order mark is not UTF-16
        self.assertEqual(E.sniff("<p>".encode("utf-16-le")).encoding,
                         "windows-1252")

    def test_xml_documents(self):
        # XHTML is decoded as XML: no <meta> counts, UTF-8 by default
        # (measured: served as application/xhtml+xml, and .xhtml files).
        body = ('<html xmlns="http://www.w3.org/1999/xhtml"><head><meta '
                'charset="koi8-r"/></head><body><p>' + CAFE).encode()
        got = E.sniff(body, xml=True)
        self.assertEqual((got.encoding, got.text.endswith(CAFE)), ("UTF-8", True))
        self.assertEqual(E.sniff(b"<?xml version='1.0' encoding='koi8-r'?>"
                                 b"<p>\xe9", xml=True).encoding, "KOI8-R")

    def test_the_scan_is_linear(self):
        # The first version searched for "--!>" to the end of the page at
        # every comment: 80,000 comments took 10 s (OR-10).
        t0 = time.monotonic()
        E.sniff(b"<!--c-->" * 500_000 + b"charset")          # 4 MB, all head
        E.sniff(b"<html><head>" + b"<script>a='<!--x-->'</script>" * 100_000)
        self.assertLess(time.monotonic() - t0, 10)


class TestWhereItApplies(unittest.TestCase):
    def test_file_runs_decode_the_file(self):
        import tempfile
        d = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: [p.unlink() for p in d.iterdir()] and d.rmdir())
        f = d / "p.html"
        f.write_bytes(('<!doctype html><html lang="fr"><head><title>T</title>'
                       '</head><body><main><h1>T</h1><img src="a.png" alt="'
                       + CAFE + '"></main></body></html>').encode("cp1252"))
        run = run_paths([f])
        imgs = [x for rr in run["pages"][0].results for x in rr.findings
                if rr.rule_id == "bb-img-alt"]
        self.assertEqual(imgs, [])
        from bellbriar_harness.checks_static import PageContext
        ctx = PageContext.parse(f.read_bytes())
        self.assertEqual(ctx.soup.find("img")["alt"], CAFE)
        # A local file in UTF-8 without a declaration is detected as such.
        ctx = PageContext.parse(("<p>" + CAFE).encode())
        self.assertEqual(ctx.soup.find("p").get_text(), CAFE)

    def test_server_fetch_uses_the_same_rules(self):
        self.assertEqual(F.decode_html(b'<!-- <meta charset="koi8-r"> --><p>\xe9'),
                         '<!-- <meta charset="koi8-r"> --><p>' + chr(0xE9))
        self.assertEqual(F.decode_html(b"<p>\xc1", "koi8-r"),
                         "<p>" + chr(0x430))

    def test_a_snapshot_reads_back_as_captured(self):
        # The page declared Shift_JIS and was decoded at capture; the saved
        # snapshot is UTF-8 with a byte-order mark, which outranks the
        # page's own <meta>.
        text = ('<!doctype html><html lang="ja"><head><meta charset="shift_jis">'
                '<title>T</title></head><body><p>' + chr(0x65E5) + '</p>'
                '</body></html>')
        fr = F.FetchResult(url="http://x.test/", final_url="http://x.test/",
                           mode="server", html=text, status=200)
        self.assertTrue(fr.snapshot_bytes.startswith(b"\xef\xbb\xbf"))
        self.assertEqual(E.sniff(fr.snapshot_bytes).text, text)

    def test_a_second_byte_order_mark_is_text(self):
        # Only the first is the encoding's; a page saved with two (a PHP
        # include's) starts with U+FEFF, so it renders in quirks mode, where
        # a <table> does not close an open <p> (OR-13, Chromium 141).
        from bellbriar_harness.checks_static import PageContext
        body = (b"\xef\xbb\xbf\xef\xbb\xbf<!doctype html><p aria-hidden=true>"
                b"<table><tr><td><a href=/x></a></td></tr></table>")
        ctx = PageContext.parse(body)
        self.assertIsNotNone(ctx.soup.find("a").find_parent("p"))
        ctx = PageContext.parse(body[3:])
        self.assertIsNone(ctx.soup.find("a").find_parent("p"))


if __name__ == "__main__":
    unittest.main()
