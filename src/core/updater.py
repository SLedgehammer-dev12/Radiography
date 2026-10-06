import hashlib
import json
import os
import platform
import socket
import ssl
import sys
import tempfile
import threading
import urllib.request
import urllib.error

from src.core.version import __version__ as _version

GITHUB_REPO = "SLedgehammer-dev12/Radiography"
CURRENT_VERSION = _version


def _ssl_context():
    """
    Builds an SSL context with an explicit CA bundle.
    Packaged (PyInstaller) builds on Windows cannot always resolve the
    default OpenSSL CA bundle. certifi ships a self-contained cacert.pem.
    """
    try:
        import certifi
        cafile = certifi.where()
        if os.path.exists(cafile):
            return ssl.create_default_context(cafile=cafile)
    except Exception:
        pass
    try:
        return ssl.create_default_context()
    except Exception:
        # Do NOT fall back to unverified context automatically.
        # Raising here forces the caller to handle certificate issues explicitly.
        raise


def _open_url(req, timeout=10):
    """
    Opens URL with secure SSL context. Certificate verification failures
    are NOT silently bypassed; they raise to the caller for explicit handling.
    """
    ctx = _ssl_context()
    return urllib.request.urlopen(req, timeout=timeout, context=ctx)


def _is_android():
    """True on Android. ``platform.system()`` returns 'Linux' there, so prefer
    Kivy's platform detector when available."""
    try:
        from kivy.utils import platform as kivy_platform
        if kivy_platform == "android":
            return True
    except Exception:
        pass
    return "android" in platform.system().lower()


def _sha256_file(filepath):
    """Returns SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _verify_sha256(filepath, expected_hash):
    """Verifies file SHA-256 against expected hash. Returns (bool, actual_hash)."""
    actual = _sha256_file(filepath)
    return (actual.lower() == expected_hash.lower(), actual)


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
            req = urllib.request.Request(
                self.api_url,
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "Radiography-Updater/1.0"
                }
            )
            with _open_url(req, timeout=10) as resp:
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

    def get_download_asset(self, release_data):
        """Returns ``{"name", "url"}`` for the best asset for this platform.

        The asset name is needed to look up its published SHA-256 checksum.
        Returns ``None`` when no compatible asset exists.
        """
        system = platform.system().lower()
        android = _is_android()
        assets = release_data.get("assets", []) if release_data else []

        def matches(name, substring=False):
            if android:
                return (".apk" in name) if substring else name.endswith(".apk")
            if system in ("windows", "win32"):
                return (".exe" in name) if substring else name.endswith(".exe")
            if system in ("darwin", "mac", "macos"):
                return (".dmg" in name) if substring else name.endswith(".dmg")
            if system == "linux":
                return (".apk" in name) if substring else name.endswith(".apk")
            return False

        for asset in assets:
            name = asset.get("name", "")
            if matches(name):
                return {"name": name, "url": asset.get("browser_download_url")}
        # Generic (substring) fallback
        for asset in assets:
            name = asset.get("name", "")
            if matches(name, substring=True):
                return {"name": name, "url": asset.get("browser_download_url")}
        return None

    def get_download_url(self, release_data):
        asset = self.get_download_asset(release_data)
        return asset["url"] if asset else None

    def _extract_sha256_from_release(self, release_data, asset_name):
        """
        Attempts to extract SHA-256 hash for the given asset from release notes.
        Expected format in release body: `sha256: <hash> <filename>` or similar.
        """
        body = release_data.get("body", "") or ""
        import re
        # Look for lines like: sha256: <hash> <filename> or <hash>  <filename>
        for line in body.splitlines():
            line = line.strip()
            if asset_name in line:
                # Try to find a 64-char hex string near the filename
                match = re.search(r"([a-fA-F0-9]{64})", line)
                if match:
                    return match.group(1)
        return None

    def download_update(self, url, progress_callback=None, expected_sha256=None):
        self._cancel = False
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Radiography-Updater/1.0"})
            with _open_url(req, timeout=120) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                chunk_size = 8192
                system = platform.system().lower()
                if _is_android() or url.endswith(".apk"):
                    suffix = ".apk"
                elif system in ("windows", "win32"):
                    suffix = ".exe"
                elif system in ("darwin", "mac", "macos"):
                    suffix = ".dmg"
                else:
                    suffix = ".bin"
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
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
                    raise
                if self._cancel:
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
                    return None

                # SHA-256 verification
                actual_hash = _sha256_file(tmp_path)
                if expected_sha256 is None:
                    # Try to extract from release notes if not provided
                    pass  # caller should provide if available
                if expected_sha256:
                    ok, actual = _verify_sha256(tmp_path, expected_sha256)
                    if not ok:
                        os.unlink(tmp_path)
                        raise RuntimeError(
                            f"SHA-256 verification failed! Expected: {expected_sha256}, got: {actual}"
                        )
                # Log the hash for manual verification
                import logging
                logging.getLogger(__name__).info("Downloaded file SHA-256: %s", actual_hash)

                return tmp_path
        except Exception as e:
            raise RuntimeError(f"Download failed: {e}")

    def launch_installer(self, filepath):
        try:
            if _is_android():
                self._install_android_apk(filepath)
            elif platform.system().lower() in ("windows", "win32"):
                os.startfile(filepath)
            elif platform.system().lower() in ("darwin", "mac", "macos"):
                import subprocess
                subprocess.Popen(["open", filepath])
        except Exception as e:
            raise RuntimeError(f"Failed to launch installer: {e}")

    def _install_android_apk(self, filepath):
        """Launches the Android package installer for a downloaded APK.

        The APK is shared through the app's FileProvider (the same authority
        used by pdf_helper.share_pdf) so Android 7+ grants read access.
        """
        from jnius import autoclass

        Intent = autoclass("android.content.Intent")
        Uri = autoclass("android.net.Uri")
        File = autoclass("java.io.File")
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        FileProvider = autoclass("androidx.core.content.FileProvider")
        BuildVersion = autoclass("android.os.Build$VERSION")

        activity = PythonActivity.mActivity
        authority = f"{activity.getPackageName()}.fileprovider"
        target = File(filepath)
        if BuildVersion.SDK_INT >= 24:
            uri = FileProvider.getUriForFile(activity, authority, target)
        else:
            uri = Uri.fromFile(target)

        intent = Intent(Intent.ACTION_VIEW)
        intent.setDataAndType(uri, "application/vnd.android.package-archive")
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        activity.startActivity(intent)


def compare_versions(v1, v2):
    p1 = [int(x) if x.isdigit() else 0 for x in v1.lstrip("vV").split(".")]
    p2 = [int(x) if x.isdigit() else 0 for x in v2.lstrip("vV").split(".")]
    return (p1 > p2) - (p1 < p2)
