# -*- coding: utf-8 -*-
"""Tests for the cross-platform web launcher (web/launcher/serve.py)."""

import importlib.util
import pathlib
import sys
import threading
import urllib.request

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVE_PATH = ROOT / "web" / "launcher" / "serve.py"


def _load_serve():
    spec = importlib.util.spec_from_file_location("web_serve", SERVE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_serve_module_exists_and_exposes_api():
    assert SERVE_PATH.exists()
    module = _load_serve()
    assert callable(module.main)
    assert callable(module.resolve_dist)
    assert callable(module.start_server)
    assert callable(module.is_running)
    assert module.APP_MARKER == "radiography-web"


def test_wasm_and_module_mime_types():
    module = _load_serve()
    assert module.EXTRA_TYPES[".wasm"] == "application/wasm"
    assert module.EXTRA_TYPES[".mjs"] == "text/javascript"
    assert module.EXTRA_TYPES[".webmanifest"] == "application/manifest+json"
    assert module.EXTRA_TYPES[".ttf"] == "font/ttf"


def test_free_port_returns_bindable_port():
    module = _load_serve()
    port = module.free_port(0)
    assert 0 < port < 65536


def test_frozen_dist_resolution(tmp_path, monkeypatch):
    module = _load_serve()
    frozen = tmp_path / "meipass"
    (frozen / "dist").mkdir(parents=True)
    (frozen / "dist" / "index.html").write_text("<html></html>", encoding="utf-8")
    monkeypatch.setattr(sys, "_MEIPASS", str(frozen), raising=False)
    assert module.resolve_dist() == frozen / "dist"


def test_healthz_and_single_instance(tmp_path):
    module = _load_serve()
    directory = tmp_path / "dist"
    directory.mkdir()
    (directory / "index.html").write_text("<html></html>", encoding="utf-8")

    server, url, already = module.start_server(directory, 0)
    assert server is not None and already is False
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(f"{url}healthz", timeout=2) as response:
            payload = response.read().decode("utf-8")
        assert module.APP_MARKER in payload
        port = int(url.rsplit(":", 1)[1].rstrip("/"))
        assert module.is_running(port) is True

        # A second start on the same port must not create another server.
        second, second_url, already = module.start_server(directory, port)
        assert second is None
        assert already is True
        assert second_url == url
    finally:
        server.shutdown()
        server.server_close()


def test_version_reads_repo_source():
    module = _load_serve()
    version = module.app_version()
    assert version and version != "0.0.0"
    assert version.count(".") >= 1


@pytest.mark.parametrize("flag", ["--no-gui", "--no-browser"])
def test_app_entry_help(flag):
    entry = ROOT / "web" / "launcher" / "app_entry.py"
    assert entry.exists()
    assert flag in entry.read_text(encoding="utf-8")
