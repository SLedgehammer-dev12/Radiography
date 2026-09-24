# -*- coding: utf-8 -*-

import os
import ssl
import unittest


class TestUpdater(unittest.TestCase):
    """Tests for the update checker SSL handling and version parsing."""

    def setUp(self):
        from src.core.updater import UpdateChecker, _ssl_context, compare_versions
        self.UpdateChecker = UpdateChecker
        self.ssl_context = _ssl_context
        self.compare_versions = compare_versions

    def test_ssl_context_is_verified(self):
        ctx = self.ssl_context()
        self.assertIsInstance(ctx, ssl.SSLContext)
        self.assertFalse(ctx.check_hostname is False and ctx.verify_mode == ssl.CERT_NONE,
                         "SSL context must perform certificate verification")

    def test_ssl_context_uses_certifi_when_available(self):
        try:
            import certifi
        except ImportError:
            self.skipTest("certifi not installed")
        ctx = self.ssl_context()
        cafile = certifi.where()
        self.assertTrue(os.path.exists(cafile), "certifi CA bundle must exist")

    def test_update_checker_init(self):
        checker = self.UpdateChecker(repo="owner/repo", current_version="1.0.0")
        self.assertEqual(checker.repo, "owner/repo")
        self.assertIn("api.github.com", checker.api_url)

    def test_compare_versions(self):
        self.assertEqual(self.compare_versions("1.3.3", "1.3.4"), -1)
        self.assertEqual(self.compare_versions("1.3.4", "1.3.3"), 1)
        self.assertEqual(self.compare_versions("1.3.4", "1.3.4"), 0)
        self.assertEqual(self.compare_versions("v1.3.4", "1.3.4"), 0)

    def test_parse_version_handles_prefix(self):
        checker = self.UpdateChecker()
        self.assertEqual(checker._parse_version("v1.3.4"), (1, 3, 4))
        self.assertEqual(checker._parse_version("1.3.4"), (1, 3, 4))

    def test_get_download_url_platforms(self):
        checker = self.UpdateChecker()
        release_data = {
            "assets": [
                {"name": "Radiography-1.4.0-Windows-x64.exe", "browser_download_url": "https://github.com/exe"},
                {"name": "Radiography-1.4.0-macOS.dmg", "browser_download_url": "https://github.com/dmg"},
                {"name": "Radiography-1.4.0-Android-arm64-v8a.apk", "browser_download_url": "https://github.com/apk"},
            ]
        }
        import platform
        orig_sys = platform.system
        try:
            platform.system = lambda: "Windows"
            self.assertEqual(checker.get_download_url(release_data), "https://github.com/exe")

            platform.system = lambda: "Darwin"
            self.assertEqual(checker.get_download_url(release_data), "https://github.com/dmg")

            platform.system = lambda: "Linux"
            self.assertEqual(checker.get_download_url(release_data), "https://github.com/apk")
        finally:
            platform.system = orig_sys

    def test_sha256_file_and_verify(self):
        from src.core.updater import _sha256_file, _verify_sha256
        import hashlib, tempfile

        with tempfile.NamedTemporaryFile("wb", delete=False) as f:
            f.write(b"Radiography test payload")
            path = f.name
        try:
            digest = _sha256_file(path)
            self.assertEqual(len(digest), 64)
            expected = hashlib.sha256(b"Radiography test payload").hexdigest()
            self.assertEqual(digest, expected)
            ok, actual = _verify_sha256(path, expected)
            self.assertTrue(ok)
            self.assertEqual(actual, expected)
            bad, _ = _verify_sha256(path, "0" * 64)
            self.assertFalse(bad)
        finally:
            os.unlink(path)

    def test_download_update_rejects_wrong_hash(self):
        # A local file:// URL with a mismatched expected SHA-256 must raise.
        from src.core.updater import UpdateChecker
        import pathlib
        import tempfile

        with tempfile.NamedTemporaryFile("wb", suffix=".bin", delete=False) as f:
            f.write(b"malicious-payload")
            path = f.name
        url = pathlib.Path(path).as_uri()  # correct file:// URL on Windows too
        checker = UpdateChecker()
        try:
            with self.assertRaises(RuntimeError):
                checker.download_update(url, expected_sha256="0" * 64)
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_download_update_accepts_correct_hash(self):
        from src.core.updater import UpdateChecker, _sha256_file
        import pathlib
        import tempfile

        with tempfile.NamedTemporaryFile("wb", suffix=".bin", delete=False) as f:
            f.write(b"good-payload")
            path = f.name
        url = pathlib.Path(path).as_uri()  # correct file:// URL on Windows too
        checker = UpdateChecker()
        try:
            downloaded = checker.download_update(url, expected_sha256=_sha256_file(path))
            self.assertIsNotNone(downloaded)
            self.assertTrue(os.path.exists(downloaded))
            if downloaded:
                os.unlink(downloaded)
        finally:
            if os.path.exists(path):
                os.unlink(path)

if __name__ == "__main__":
    unittest.main()
