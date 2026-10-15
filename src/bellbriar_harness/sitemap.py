"""The pages a sitemap lists (A3): `bellbriar-eval --sitemap URL`.

A sitemap (https://www.sitemaps.org/protocol.html) is XML: a `<urlset>` of
`<url><loc>` entries, or a `<sitemapindex>` of `<sitemap><loc>` entries
naming further sitemaps. Either may be gzipped. The harness reads them in
order, follows an index into its sitemaps (two levels deep, at most
MAX_SITEMAPS files), and takes the first page URLs up to the run's page
limit, as the sitemap lists them.

As the protocol requires, a sitemap speaks only for its own host: an
entry on another host, or a sitemap there, is skipped and counted. A
document with a DOCTYPE is refused (no sitemap has one, and an XML DOCTYPE
can define entities that expand without bound).
"""
from __future__ import annotations

import zlib
from dataclasses import dataclass, field

#: Sitemap files read for one run, index files included.
MAX_SITEMAPS = 50
#: How deep sitemap indexes may nest (an index of indexes of sitemaps).
MAX_INDEX_DEPTH = 2
#: The most a gzipped sitemap may inflate to (the protocol allows 50 MB).
MAX_INFLATED = 64 * 1024 * 1024


class SitemapError(ValueError):
    """The sitemap could not be read as one."""


@dataclass
class SitemapList:
    urls: list[str] = field(default_factory=list)
    #: Page entries seen in the sitemaps read (at least len(urls)).
    listed: int = 0
    #: Every sitemap the index named was read, so `listed` is the total.
    complete: bool = True
    #: Entries (pages or sitemaps) on another host, skipped.
    other_host: int = 0
    sitemaps_read: int = 0


def _inflate(body: bytes) -> bytes:
    if body[:2] != b"\x1f\x8b":
        return body
    d = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        out = d.decompress(body, MAX_INFLATED)
    except zlib.error as exc:
        raise SitemapError(f"its gzip data is damaged ({exc})") from None
    if d.unconsumed_tail:
        raise SitemapError(f"it inflates past {MAX_INFLATED // (1024 * 1024)}"
                           " MiB")
    return out


def parse(body: bytes) -> tuple[str, list[str]]:
    """("urlset" or "sitemapindex", the <loc> values in order)."""
    import xml.parsers.expat as expat
    p = expat.ParserCreate(namespace_separator=" ")
    p.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    state = {"root": None, "in": [], "text": [], "locs": []}

    def local(name: str) -> str:
        return name.rsplit(" ", 1)[-1]

    def start(name, attrs):
        name = local(name)
        if state["root"] is None:
            state["root"] = name
        state["in"].append(name)
        if name == "loc":
            state["text"] = []

    def end(name):
        name = local(name)
        stack = state["in"]
        if name == "loc" and len(stack) >= 2 and stack[-2] in ("url",
                                                                 "sitemap"):
            state["locs"].append("".join(state["text"]).strip())
        stack.pop()

    def data(text):
        if state["in"] and state["in"][-1] == "loc":
            state["text"].append(text)

    def doctype(*_args):
        raise SitemapError("it has a DOCTYPE, which no sitemap has")

    p.StartElementHandler = start
    p.EndElementHandler = end
    p.CharacterDataHandler = data
    p.StartDoctypeDeclHandler = doctype
    try:
        p.Parse(body, True)
    except expat.ExpatError as exc:
        raise SitemapError(f"it is not well-formed XML (line {exc.lineno}: "
                           f"{expat.ErrorString(exc.code)})") from None
    if state["root"] not in ("urlset", "sitemapindex"):
        raise SitemapError(f"its root element is <{state['root']}>, not "
                           "<urlset> or <sitemapindex>")
    return state["root"], state["locs"]


def read(url: str, max_pages: int, http_credentials=None, record_query=(),
         timeout: int = 30) -> SitemapList:
    """The first `max_pages` page URLs the sitemap at `url` lists (module
    docstring). Raises SitemapError, or fetch.FetchError for the first
    sitemap; a sitemap an index names that cannot be read is skipped and
    makes the list incomplete. Credentials go only to the first sitemap's
    origin: a sitemap the index names on the same host over plain http, or
    on another port, is fetched without them."""
    from .fetch import FetchError, fetch_bytes, host_of, page_key, url_origin
    out = SitemapList()
    host = host_of(url)
    origin = url_origin(url)
    #: fetch.page_key of each page taken: where it is in out.urls, or None
    #: past max_pages.
    seen_pages: dict = {}
    seen_maps: set[str] = set()
    queue: list[tuple[str, int]] = [(url, 0)]
    first = True
    while queue:
        if len(out.urls) >= max_pages:
            out.complete = False
            break
        map_url, depth = queue.pop(0)
        if map_url in seen_maps:
            continue
        seen_maps.add(map_url)
        if out.sitemaps_read >= MAX_SITEMAPS:
            out.complete = False
            break
        try:
            body, final, status, _types, _hops, _peers = fetch_bytes(
                map_url, timeout,
                http_credentials if url_origin(map_url) == origin else None,
                record_query)
            if status != 200:
                raise SitemapError(f"the server answered HTTP {status}")
            if host_of(final) != host:
                raise SitemapError(f"it redirected to another host "
                                   f"({host_of(final)})")
            kind, locs = parse(_inflate(body))
        except (FetchError, SitemapError) as exc:
            if first:
                raise
            out.complete = False
            continue
        finally:
            first = False
        out.sitemaps_read += 1
        for loc in locs:
            if not loc.lower().startswith(("http://", "https://")) or \
                    host_of(loc) != host:
                out.other_host += 1
                continue
            if kind == "sitemapindex":
                if depth < MAX_INDEX_DEPTH:
                    queue.append((loc, depth + 1))
                else:
                    out.complete = False
                continue
            key = page_key(loc)
            if key in seen_pages:
                # One page under two spellings: the least of them, so the
                # recorded URL does not depend on the sitemap's order
                # (R4E-1).
                at = seen_pages[key]
                if at is not None and loc < out.urls[at]:
                    out.urls[at] = loc
                continue
            out.listed += 1
            if len(out.urls) < max_pages:
                seen_pages[key] = len(out.urls)
                out.urls.append(loc)
            else:
                seen_pages[key] = None
    if queue:
        out.complete = False
    return out
