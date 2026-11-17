from __future__ import annotations

import http.server
import posixpath
import shutil
from functools import partial
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlparse


def resolve_public_path(public_dir: str | Path, request_path: str) -> Path | None:
    public = Path(public_dir).resolve()
    parsed_path = unquote(urlparse(request_path).path)
    normalized = posixpath.normpath(parsed_path)
    if parsed_path.endswith("/") and normalized != "/":
        normalized += "/"

    parts = [part for part in PurePosixPath(normalized.lstrip("/")).parts if part not in ("", ".")]
    if any(part == ".." for part in parts):
        return None

    if not parts:
        candidates = [
            public / "index.html",
            public / "stops" / "index.html",
            public / "concepts" / "index.html",
            public / "works" / "index.html",
        ]
    else:
        relative = Path(*parts)
        direct = public / relative
        candidates = [direct]
        if direct.is_dir():
            candidates.append(direct / "index.html")
        if relative.suffix == "":
            candidates.append(public / (relative.as_posix() + ".html"))
            candidates.append(direct / "index.html")

    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if public == resolved or public in resolved.parents:
            if resolved.is_file():
                return resolved
    return None


class CleanUrlHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, public_dir: str | Path, **kwargs):
        self.public_dir = Path(public_dir).resolve()
        super().__init__(*args, directory=str(self.public_dir), **kwargs)

    def do_HEAD(self) -> None:
        self._serve(head_only=True)

    def do_GET(self) -> None:
        self._serve(head_only=False)

    def _serve(self, *, head_only: bool) -> None:
        resolved = resolve_public_path(self.public_dir, self.path)
        status = 200
        if resolved is None:
            resolved = self.public_dir / "404.html"
            status = 404
            if not resolved.is_file():
                self.send_error(404, "File not found")
                return

        try:
            file = resolved.open("rb")
        except OSError:
            self.send_error(404, "File not found")
            return

        with file:
            self.send_response(status)
            self.send_header("Content-type", self.guess_type(str(resolved)))
            self.send_header("Content-Length", str(resolved.stat().st_size))
            self.end_headers()
            if not head_only:
                shutil.copyfileobj(file, self.wfile)


def serve_wiki(wiki_dir: str | Path, host: str = "127.0.0.1", port: int = 8888) -> None:
    public_dir = Path(wiki_dir) / "public"
    if not public_dir.exists():
        raise FileNotFoundError(f"Quartz public directory not found: {public_dir}")

    handler = partial(CleanUrlHandler, public_dir=public_dir)
    with http.server.ThreadingHTTPServer((host, port), handler) as server:
        print(f"Serving Quartz wiki at http://{host}:{port}/")
        print("Press Ctrl+C to stop.")
        server.serve_forever()
