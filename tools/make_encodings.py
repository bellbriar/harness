#!/usr/bin/env python3
"""Regenerate src/bellbriar_harness/encodings_data.py from the WHATWG
Encoding Standard.

    python tools/make_encodings.py ENCODINGS_JSON INDEXES_JSON [OUT]

Both inputs come from the Encoding Standard's repository
(https://github.com/whatwg/encoding, `git clone` it): encodings.json lists
every encoding a browser decodes and every label that names it;
indexes.json holds each legacy encoding's index. The module this writes
holds the label table (the standard's "get an encoding") and, for the 28
single-byte encodings, the code point of each byte from 0x80 to 0xFF,
which Python's codecs do not always match (windows-1252 decodes 0x81 as
U+0081; Python's cp1252 has no mapping for it).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

OUT = (Path(__file__).resolve().parents[1] / "src" / "bellbriar_harness"
       / "encodings_data.py")

#: The standard's copyright notice and license, which the module keeps
#: (the standard's LICENSE: what it incorporates into source code is under
#: the BSD 3-Clause License). LICENSE-whatwg-encoding.txt beside the
#: module is that LICENSE file, as the repository holds it.
LICENSE_HEADER = """\
# The labels and indexes in this module are the WHATWG Encoding Standard's
# (https://encoding.spec.whatwg.org/; encodings.json and indexes.json in
# https://github.com/whatwg/encoding), written as Python.
#
# Copyright \u00a9 WHATWG (Apple, Google, Mozilla, Microsoft).
#
# The standard is licensed under a Creative Commons Attribution 4.0
# International License. To the extent portions of it are incorporated into
# source code, as they are here, such portions in the source code are
# licensed under the BSD 3-Clause License instead
# (LICENSE-whatwg-encoding.txt, beside this module, holds both):
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

"""


def _escaped(text: str) -> str:
    """`text` as the body of an ASCII-only Python string literal."""
    out = []
    for ch in text:
        cp = ord(ch)
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif 0x20 <= cp < 0x7F:
            out.append(ch)
        elif cp <= 0xFF:
            out.append(f"\\x{cp:02x}")
        else:
            out.append(f"\\u{cp:04x}")
    return "".join(out)


def main(argv: list[str]) -> int:
    if len(argv) not in (3, 4):
        print(__doc__)
        return 2
    out = Path(argv[3]) if len(argv) == 4 else OUT
    groups = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    indexes = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
    labels: dict[str, str] = {}
    single: dict[str, str] = {}
    for group in groups:
        for enc in group["encodings"]:
            name = enc["name"]
            for label in enc["labels"]:
                if label in labels:
                    print(f"refusing: label {label!r} names two encodings")
                    return 1
                labels[label] = name
            if group["heading"] == "Legacy single-byte encodings":
                index = indexes.get(name.lower())
                if index is None and name == "ISO-8859-8-I":
                    index = indexes.get("iso-8859-8")   # same index
                if not index or len(index) != 128:
                    print(f"refusing: no 128-entry index for {name}")
                    return 1
                # U+FFFE marks a byte the index leaves unmapped: charmap
                # decoding treats it as undefined, so the byte decodes to
                # U+FFFD, as the standard's decoder errors there.
                single[name] = "".join(chr(cp) if cp is not None else chr(0xFFFE)
                                       for cp in index)
    if len(labels) < 200 or len(single) != 28:
        print(f"refusing: {len(labels)} labels and {len(single)} single-byte "
              "encodings is not the whole standard")
        return 1

    def label_lines():
        for label, name in sorted(labels.items()):
            yield f'    "{_escaped(label)}": "{name}",'

    def table_lines():
        for name, table in single.items():
            body = _escaped(table)
            # Lines of at most 64 characters, never splitting an escape.
            chunks, line = [], ""
            i = 0
            while i < len(body):
                if body[i] == "\\":
                    n = {"x": 4, "u": 6}.get(body[i + 1], 2)
                    piece = body[i:i + n]
                else:
                    n, piece = 1, body[i]
                if len(line) + len(piece) > 64:
                    chunks.append(line)
                    line = ""
                line += piece
                i += n
            if line:
                chunks.append(line)
            yield f'    "{name}": ('
            for c in chunks:
                yield f'        "{c}"'
            yield "    ),"

    out.write_text(
        LICENSE_HEADER +
        '"""The WHATWG Encoding Standard\'s labels and single-byte indexes.\n'
        "Generated by tools/make_encodings.py from the standard's\n"
        "encodings.json and indexes.json; do not edit.\n\n"
        f"{len(labels)} labels name {len(set(labels.values()))} encodings; "
        f"{len(single)} single-byte encodings\n"
        "map bytes 0x80-0xFF (U+FFFE where the index has no code point).\n"
        '"""\n\n'
        "#: Every label a browser accepts, lowercased, to the encoding it names.\n"
        "LABELS = {\n" + "\n".join(label_lines()) + "\n}\n\n"
        "#: For each single-byte encoding, the code points of bytes 0x80-0xFF.\n"
        "SINGLE_BYTE = {\n" + "\n".join(table_lines()) + "\n}\n",
        encoding="utf-8")
    print(f"wrote {out} ({len(labels)} labels, {len(single)} single-byte "
          "indexes)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
