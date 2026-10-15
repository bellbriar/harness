# WPT tree-construction tests

These `.dat` files are the HTML parser tree-construction tests of
[web-platform-tests](https://github.com/web-platform-tests/wpt), from
`html/syntax/parsing/resources/` at commit
`b60c4b349d9d167bf354a40bc0d4cbed15174606` (2026-10-08), under the
3-Clause BSD License in `LICENSE.md`. They are unmodified. They were first
written in html5lib-tests, under the MIT License in
`LICENSE-html5lib-tests.txt` (that repository's LICENSE, unmodified),
before they moved to WPT (html5lib-tests commit 224991e, "Tree
construction tests have moved to WPT").

`tests/test_html5_parsing.py` runs every document test in them (fragment
tests and `#script-off` tests aside: the harness parses whole documents
with scripting on) through `bellbriar_harness.html5.parse`, so an upgrade
of the parser that changes what it builds fails the suite. Left out of the
copy: `scripted_*.dat` (they need a script engine), `foreign-fragment.dat`
and `tests_innerHTML_1.dat` (fragments only), and
`processing-instructions.dat` (the 2026 rule that makes `<?...>` a
processing instruction; the harness builds the comment Chromium 141
builds).

To refresh: copy the same files from a newer WPT checkout, update the
commit above, and run the suite; a case the parser now builds differently
from the test is either a parser regression or a spec change to look at.
