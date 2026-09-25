#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Radiography Web local server (stdlib only).

Serves the built web application (dist/) over 127.0.0.1 and can open the
default browser. Used directly in development::

    python3 serve.py [--port 8765] [--no-browser] [--directory PATH]

and reused by the packaged single-file launchers (app_entry.py).
"""

import argparse
import http.server
import json
import os
import re
import socket
import sys
import threading
import urllib.error
import urllib.request
import webbrowser
from functools import partial
from pathlib import Path

HERE = Path(__file__).resolve().parent
APP_MARKER = "radiography-web"

EXTRA_TYPES = {
    ".wasm": "application/wasm",
    ".mjs": "text/javascript",
    ".js": "text/javascript",
    ".json": "application/json",
    ".webmanifest": "application/manifest+json",
    ".ttf": "font/ttf",
    ".otf": "font/otf",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".svg": "image/svg+xml",
    ".map": "application/json",
}

IMMUTABLE_SUFFIXES = (
    ".js", ".mjs", ".wasm", ".css", ".ttf", ".woff2", ".png", ".svg",
    ".whl", ".zip",
)


def bundled_dir() -> Path:
    """Directory that also holds the bundled icons (PyInstaller _MEIPASS)."""
    return Path(getattr(sys, "_MEIPASS", HERE))


def app_version() -> str:
    """Version from the bundled module, falling back to the repo source."""
    try:
        from version import __version__  # type: ignore

        return str(__version__)
    except ImportError:
        pass
    candidate = HERE.parents[1] / "src" / "core" / "version.py"
    try:
        match = re.search(
            r'__version__\s*=\s*["\']([^"\']+)["\']',
            candidate.read_text(encoding="utf-8"),
        )
        if match:
            return match.group(1)
    except OSError:
        pass
    return "0.0.0"


def resolve_dist() -> Path:
    """Locates the built application (dev checkout, package or frozen app)."""
    candidates = [
        bundled_dir() / "dist",
        HERE / "dist",
        HERE.parent / "dist",
    ]
    for candidate in candidates:
        if (candidate / "index.html").exists():
            return candidate
    return candidates[0]


class Handler(http.server.SimpleHTTPRequestHandler):
    server_version = "RadiographyWeb/" + app_version()

    def guess_type(self, path):
        suffix = os.path.splitext(path)[1].lower()
        if suffix in EXTRA_TYPES:
            return EXTRA_TYPES[suffix]
        return super().guess_type(path)

    def do_GET(self):
        if self.path.split("?")[0] == "/healthz":
            payload = json.dumps({
                "app": APP_MARKER,
                "version": app_version(),
                "pid": os.getpid(),
            }).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        super().do_GET()

    def end_headers(self):
        if self.path.endswith(IMMUTABLE_SUFFIXES):
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        else:
            self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def log_message(self, *args):  # keep the console clean
        pass


def free_port(preferred: int) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind(("127.0.0.1", preferred))
            return probe.getsockname()[1]
        except OSError:
            probe.bind(("127.0.0.1", 0))
            return probe.getsockname()[1]


def is_running(port: int, timeout: float = 0.6) -> bool:
    """True when a Radiography Web server already listens on the port."""
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/healthz", timeout=timeout
        ) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data.get("app") == APP_MARKER
    except (urllib.error.URLError, ValueError, OSError):
        return False


def start_server(directory: Path, preferred_port: int = 8765):
    """Starts the server unless an instance already runs.

    Returns ``(server, url, already_running)``; ``server`` is ``None`` when an
    existing instance was detected.
    """
    if is_running(preferred_port):
        return None, f"http://127.0.0.1:{preferred_port}/", True
    port = free_port(preferred_port)
    handler = partial(Handler, directory=str(directory))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    return server, f"http://127.0.0.1:{port}/", False


def main(argv=None):
    parser = argparse.ArgumentParser(description="Radiography Web launcher")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true",
                        help="do not open the default browser")
    parser.add_argument("--directory", default=None,
                        help="override the directory to serve")
    args = parser.parse_args(argv)

    directory = Path(args.directory).resolve() if args.directory else resolve_dist()
    if not (directory / "index.html").exists():
        print("HATA: Web uygulamasi bulunamadi (index.html yok).")
        print("Once derleyin:  cd web && npm install && npm run build")
        print(f"Beklenen dizin: {directory}")
        return 1

    server, url, already = start_server(directory, args.port)
    if already:
        print(f"Radiography Web zaten calisiyor: {url}")
        if not args.no_browser:
            webbrowser.open(url)
        return 0

    print("=" * 58)
    print("  Radiography Web " + app_version())
    print(f"  Adres / URL: {url}")
    print("  Kapatmak icin bu pencereyi kapatin / Ctrl+C")
    print("=" * 58)

    if not args.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
