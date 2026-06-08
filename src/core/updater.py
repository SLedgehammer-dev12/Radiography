import json
import os
import platform
import sys
import tempfile
import threading
import urllib.request
import urllib.error


GITHUB_REPO = "SLedgehammer-dev12/Radiogrphy"
CURRENT_VERSION = "1.2.0"


class UpdateChecker:
    def __init__(self, repo=GITHUB_REPO, current_version=CURRENT_VERSION):
        self.repo = repo
        self.current_version = current_version
        self.api_url = f"https://api.github.com/repos/{repo}/releases/latest"
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def _parse_version(self, tag):
        v = tag.lstrip("vV")
        parts = v.split(".")
        return tuple(int(p) if p.isdigit() else 0 for p in parts)

    def check(self):
        try:
            req = urllib.request.Request(self.api_url, headers={"Accept": "application/json", "User-Agent": "Radiography-Updater/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            return {"available": False, "error": str(e), "data": None}

        tag = data.get("tag_name", "")
        latest_ver = self._parse_version(tag)
        current_ver = self._parse_version(self.current_version)

        if latest_ver > current_ver:
            return {
                "available": True,
                "version": tag,
                "url": data.get("html_url", ""),
                "release_notes": data.get("body", ""),
                "assets": data.get("assets", []),
            }
        return {"available": False, "error": None, "data": data}

    def get_download_url(self, release_data):
        system = platform.system().lower()
        for asset in release_data.get("assets", []):
            name = asset.get("name", "")
            if system == "windows" and name.endswith(".exe"):
                return asset.get("browser_download_url")
            elif system == "darwin" and name.endswith(".dmg"):
                return asset.get("browser_download_url")
        return None

    def download_update(self, url, progress_callback=None):
        self._cancel = False
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Radiography-Updater/1.0"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                chunk_size = 8192
                suffix = ".exe" if platform.system().lower() == "windows" else ".dmg"
                fd, tmp_path = tempfile.mkstemp(suffix=suffix, prefix="Radiography_")
                try:
                    with os.fdopen(fd, "wb") as f:
                        while not self._cancel:
                            chunk = resp.read(chunk_size)
                            if not chunk:
                                break
                            f.write(chunk)
                            downloaded += len(chunk)
                            if progress_callback and total > 0:
                                progress_callback(downloaded / total)
                except Exception:
                    os.unlink(tmp_path)
                    raise
                if self._cancel:
                    os.unlink(tmp_path)
                    return None
                return tmp_path
        except Exception as e:
            raise RuntimeError(f"Download failed: {e}")

    def launch_installer(self, filepath):
        system = platform.system().lower()
        try:
            if system == "windows":
                os.startfile(filepath)
            elif system == "darwin":
                import subprocess
                subprocess.Popen(["open", filepath])
        except Exception as e:
            raise RuntimeError(f"Failed to launch installer: {e}")


def compare_versions(v1, v2):
    p1 = [int(x) if x.isdigit() else 0 for x in v1.lstrip("vV").split(".")]
    p2 = [int(x) if x.isdigit() else 0 for x in v2.lstrip("vV").split(".")]
    return (p1 > p2) - (p1 < p2)
