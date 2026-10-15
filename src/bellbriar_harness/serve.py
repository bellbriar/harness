"""Serve a build on this machine, for `bellbriar-eval ./dist --render` (A1).

A client-rendered build (Vite, Create React App, Angular) is an empty
shell until its scripts run, and its scripts load from the server the page
came from: `/assets/index-4f2a.js`. So the harness serves the folder on the
loopback interface, the browser loads each page from there, and the rules
read the DOM the scripts built, as a --url run reads a live site.

The server is for that and nothing else:

* it listens on 127.0.0.1 only, for as long as the run, on a port taken
  from the folder's name and the base (stable_port), so a page that writes
  its own address into its markup (a share link built from location.href)
  reads the same from run to run; when another program holds that port, on
  one the system picks, and `port_stable` is False;
* it answers GET and HEAD with the files under its root, as a static host
  does (a folder's index.html for the folder), and refuses everything else:
  other methods, any path outside the root (`..`, a symlink out, a
  folder whose index.html is one), and any path with a segment that starts
  with a dot (`.env`, `.git/`) or that resolves to one, which a build does
  not serve and another process on the machine must not read;
* `base` is the path the build was built for (your bundler's base or
  homepage setting): with base `/app/`, `/app/assets/x.js` is
  `<root>/assets/x.js`, and nothing outside `/app/` is served;
* an HTML page is sent with the charset the harness reads in the file
  (encoding.sniff, as Chromium reads a local file), so the browser decodes
  it as a file run does; other text is sent as UTF-8, as static hosts do.

It records every file it served, with its SHA-256, and every path it could
not find (a base set wrong shows up as the build's own scripts missing).
"""
from __future__ import annotations

import hashlib
import http.server
import mimetypes
import os
import socket
import threading
import urllib.parse
from pathlib import Path

#: Types static hosts send, where Python's table is missing or dated.
_TYPES = {
    ".html": "text/html", ".htm": "text/html",
    ".xhtml": "application/xhtml+xml", ".xht": "application/xhtml+xml",
    ".xhtm": "application/xhtml+xml",
    ".js": "text/javascript", ".mjs": "text/javascript",
    ".cjs": "text/javascript", ".css": "text/css",
    ".json": "application/json", ".map": "application/json",
    ".webmanifest": "application/manifest+json",
    ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp",
    ".avif": "image/avif", ".ico": "image/x-icon",
    ".woff": "font/woff", ".woff2": "font/woff2", ".ttf": "font/ttf",
    ".otf": "font/otf", ".wasm": "application/wasm",
    ".txt": "text/plain", ".xml": "application/xml",
    ".mp4": "video/mp4", ".webm": "video/webm", ".mp3": "audio/mpeg",
    ".ogg": "audio/ogg", ".wav": "audio/wav", ".pdf": "application/pdf",
}
_PAGE_SUFFIXES = (".html", ".htm", ".xhtml", ".xht", ".xhtm")


def content_type(path: Path, data: bytes) -> str:
    suffix = path.suffix.lower()
    ctype = _TYPES.get(suffix) or mimetypes.guess_type(path.name)[0] \
        or "application/octet-stream"
    if suffix in _PAGE_SUFFIXES:
        from .encoding import sniff
        decoded = sniff(data, local_file=True,
                        xml=ctype == "application/xhtml+xml")
        return f"{ctype}; charset={decoded.encoding}"
    if ctype.startswith("text/") or ctype in ("application/json",
                                              "application/manifest+json",
                                              "application/xml",
                                              "image/svg+xml"):
        return f"{ctype}; charset=utf-8"
    return ctype


def normalize_base(base: str | None) -> str:
    """`base` as a URL path that starts and ends with "/": "app" and "/app"
    are "/app/". Refuses anything a URL path cannot say plainly."""
    base = (base or "/").strip()
    if not base.startswith("/"):
        base = "/" + base
    if not base.endswith("/"):
        base += "/"
    parts = [p for p in base.split("/") if p]
    if any(p in (".", "..") or "\\" in p or "?" in p or "#" in p
           for p in parts):
        raise ValueError(f"--render-base {base!r} is not a plain URL path")
    return "/" + "".join(p + "/" for p in parts)


#: The dynamic port range (RFC 6335) stable_port picks from.
_PORTS = (49152, 65535)


def stable_port(root: str | os.PathLike, base: str = "/") -> int:
    """The port a build folder is served on when it is free: taken from the
    folder's own name and the base, so the same build gets the same address
    on any machine and in any run (R3D-2)."""
    key = f"bellbriar-build|{Path(root).name}|{base}".encode("utf-8",
                                                             "replace")
    low, high = _PORTS
    return low + int(hashlib.sha256(key).hexdigest(), 16) % (high - low + 1)


class _Server(http.server.ThreadingHTTPServer):
    """Binds only a port no other program listens on. SO_REUSEADDR lets a
    run take its usual port while an earlier run's connections wait out
    TIME_WAIT, and never a port another socket listens on — except on
    Windows, where it would share one, so there the port is taken
    exclusively instead."""
    allow_reuse_address = os.name != "nt"
    daemon_threads = True

    def server_bind(self):
        if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET,
                                   socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class BuildServer:
    """A loopback server for one build folder (module docstring). Use as a
    context manager; `url_for(file)` is the URL of a file under the root."""

    def __init__(self, root: str | os.PathLike, base: str = "/"):
        self.root = Path(os.path.realpath(root))
        if not self.root.is_dir():
            raise NotADirectoryError(str(root))
        self.base = normalize_base(base)
        #: {path relative to the root (posix): (sha256, bytes)} served,
        #: as first sent
        self.served: dict[str, tuple[str, int]] = {}
        #: {path: (sha256, bytes)} as last sent: a page read again as the
        #: file it is was evaluated from its latest sending (R5D-7)
        self.last_sent: dict[str, tuple[str, int]] = {}
        #: URL paths requested and not found, in order (at most 200)
        self.missing: list[str] = []
        self._lock = threading.Lock()
        self._httpd = None
        self._thread = None
        #: Whether the run got the folder's usual port (stable_port).
        self.port_stable = False

    # -- the files ---------------------------------------------------------

    def resolve(self, url_path: str) -> Path | None:
        """The file a URL path names, or None: outside the base or the
        root, a dot segment, or no such file."""
        path = urllib.parse.unquote(url_path.split("?", 1)[0]
                                    .split("#", 1)[0])
        if "\x00" in path or "\\" in path:
            return None
        if not (path + "/").startswith(self.base) and path != self.base[:-1]:
            return None
        rest = path[len(self.base):] if path.startswith(self.base) else ""
        parts = [p for p in rest.split("/") if p]
        if any(p == ".." or p.startswith(".") for p in parts):
            return None
        target = self.root.joinpath(*parts) if parts else self.root
        real = self._inside(target)
        if real is not None and real.is_dir():
            # A folder's index.html is resolved and checked in its own right:
            # it can be a symlink out of the root too.
            real = self._inside(real / "index.html")
        return real if real is not None and real.is_file() else None

    def _inside(self, path: Path) -> Path | None:
        """`path` with every symlink resolved, or None when that is outside
        the root or under a name that starts with a dot (a symlink to
        `.env` is refused as `.env` is)."""
        try:
            real = Path(os.path.realpath(path))
        except OSError:
            return None
        if real != self.root and self.root not in real.parents:
            return None                  # a symlink out of the root
        if any(p.startswith(".") for p in real.relative_to(self.root).parts):
            return None
        return real

    def url_for(self, file: str | os.PathLike,
                folder: str | os.PathLike | None = None) -> str:
        """The URL of `file`. Given the `folder` it was found in as the
        run names it, a file is served at its own path there, as a static
        host serves it — a link to another page of the build is a page of
        its own, at its own address (R3D-3); otherwise at the path its
        real file has under the root."""
        rel = None
        if folder is not None:
            mine = os.path.abspath(file)
            top = os.path.abspath(folder)
            if mine.startswith(top.rstrip(os.sep) + os.sep):
                rel = Path(os.path.relpath(mine, top)).as_posix()
        if rel is None:
            rel = Path(os.path.realpath(file)).relative_to(
                self.root).as_posix()
        quoted = "/".join(urllib.parse.quote(p) for p in rel.split("/"))
        host, port = self._httpd.server_address[:2]
        return f"http://{host}:{port}{self.base}{quoted}"

    # -- the server --------------------------------------------------------

    def __enter__(self) -> "BuildServer":
        server = self

        class Handler(http.server.BaseHTTPRequestHandler):
            server_version = "bellbriar-build-server"
            sys_version = ""
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):        # quiet: the run reports
                pass

            def _refuse(self, code: int) -> None:
                body = b""
                self.send_response(code)
                self.send_header("Content-Length", "0")
                if code == 405:
                    self.send_header("Allow", "GET, HEAD")
                self.end_headers()
                self.wfile.write(body)

            def _serve(self, head: bool) -> None:
                file = server.resolve(self.path)
                if file is None:
                    with server._lock:
                        if len(server.missing) < 200:
                            server.missing.append(
                                urllib.parse.unquote(self.path.split("?")[0]))
                    self._refuse(404)
                    return
                try:
                    data = file.read_bytes()
                except OSError:
                    self._refuse(404)
                    return
                rel = file.relative_to(server.root).as_posix()
                sent = (hashlib.sha256(data).hexdigest(), len(data))
                with server._lock:
                    server.served.setdefault(rel, sent)
                    server.last_sent[rel] = sent
                self.send_response(200)
                self.send_header("Content-Type", content_type(file, data))
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                if not head:
                    self.wfile.write(data)

            def do_GET(self):                     # noqa: N802
                self._serve(head=False)

            def do_HEAD(self):                    # noqa: N802
                self._serve(head=True)

            def _not_allowed(self):
                self._refuse(405)

            do_POST = do_PUT = do_DELETE = do_PATCH = do_OPTIONS = \
                _not_allowed

        wanted = stable_port(self.root, self.base)
        low, high = _PORTS
        for port in [low + (wanted - low + i) % (high - low + 1)
                     for i in range(8)] + [0]:
            try:
                self._httpd = _Server(("127.0.0.1", port), Handler)
                break
            except OSError:
                if port == 0:
                    raise
        self.port_stable = self._httpd.server_address[1] == wanted
        self._thread = threading.Thread(target=self._httpd.serve_forever,
                                        daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None


def build_root(arg: str | os.PathLike) -> Path:
    """The folder `bellbriar-eval ARG --render` serves: ARG itself when it
    is a folder, else the folder the file is in."""
    p = Path(arg)
    return p if p.is_dir() else p.parent
