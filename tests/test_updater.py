# -*- coding: utf-8 -*-

import hashlib
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

    def test_get_download_asset_returns_name_and_url(self):
        checker = self.UpdateChecker()
        release_data = {
            "assets": [
                {"name": "Radiography-1.4.0-Windows-x64.exe", "browser_download_url": "https://github.com/exe"},
                {"name": "Radiography-1.4.0-macOS.dmg", "browser_download_url": "https://github.com/dmg"},
            ]
        }
        import platform
        orig_sys = platform.system
        try:
            platform.system = lambda: "Windows"
            asset = checker.get_download_asset(release_data)
            self.assertEqual(asset["name"], "Radiography-1.4.0-Windows-x64.exe")
            self.assertEqual(asset["url"], "https://github.com/exe")
            platform.system = lambda: "Darwin"
            self.assertEqual(checker.get_download_asset(release_data)["url"], "https://github.com/dmg")
        finally:
            platform.system = orig_sys
        self.assertIsNone(checker.get_download_asset({"assets": []}))

    def test_extract_sha256_from_release(self):
        checker = self.UpdateChecker()
        digest = "a" * 64
        release_data = {
            "body": f"## Artifact checksums (SHA-256)\nsha256: {digest}  Radiography-1.4.0-Windows-x64.exe\n"
        }
        self.assertEqual(
            checker._extract_sha256_from_release(release_data, "Radiography-1.4.0-Windows-x64.exe"),
            digest,
        )
        self.assertIsNone(
            checker._extract_sha256_from_release(release_data, "Radiography-1.4.0-Android.apk")
        )

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

    def test_ssl_context_relaxes_strict_flag(self):
        ctx = self.ssl_context()
        if hasattr(ssl, "VERIFY_X509_STRICT"):
            self.assertEqual(
                ctx.verify_flags & ssl.VERIFY_X509_STRICT,
                0,
                "VERIFY_X509_STRICT must be disabled so corporate proxies are not rejected"
            )

    def test_check_fallback_on_ssl_verification_error(self):
        import urllib.error
        from unittest.mock import patch, MagicMock
        checker = self.UpdateChecker()

        call_count = [0]
        def mock_open_url(req, timeout=10, allow_unverified_fallback=False):
            call_count[0] += 1
            if not allow_unverified_fallback:
                raise urllib.error.URLError("[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self-signed certificate in certificate chain (_ssl.c:1032)")
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'{"tag_name": "v99.0.0", "html_url": "https://github.com/test", "body": "notes"}'
            mock_resp.__enter__.return_value = mock_resp
            return mock_resp

        with patch("src.core.updater._open_url", side_effect=mock_open_url):
            result = checker.check()
            self.assertTrue(result["available"])
            self.assertEqual(result["version"], "v99.0.0")
            self.assertTrue(result.get("ssl_fallback"))
            self.assertEqual(call_count[0], 2)

    def test_is_ssl_verify_error_detection(self):
        import urllib.error
        from src.core.updater import _is_ssl_verify_error

        # Standard SSLError / SSLCertVerificationError
        self.assertTrue(_is_ssl_verify_error(ssl.SSLCertVerificationError("self-signed certificate")))
        # Wrapped in URLError
        self.assertTrue(_is_ssl_verify_error(urllib.error.URLError(ssl.SSLCertVerificationError("verify failed"))))
        self.assertTrue(_is_ssl_verify_error(urllib.error.URLError("[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed")))
        # Non-SSL errors
        self.assertFalse(_is_ssl_verify_error(urllib.error.URLError("Connection refused")))
        self.assertFalse(_is_ssl_verify_error(TimeoutError("timed out")))

    def test_windows_cert_store_loading_mock(self):
        from unittest.mock import patch
        fake_certs = [
            (b"cert1", "X509_ASN_ENCODING", 0),
            (b"cert2", "X509_ASN_ENCODING", 0),
        ]
        with patch("sys.platform", "win32"), \
             patch("ssl.enum_certificates", create=True, return_value=fake_certs), \
             patch("ssl.DER_cert_to_PEM_cert", side_effect=lambda b: f"-----BEGIN CERTIFICATE-----\n{b.decode()}\n-----END CERTIFICATE-----"), \
             patch.object(ssl.SSLContext, "load_verify_locations") as mock_load:
            ctx = self.ssl_context()
            self.assertGreaterEqual(mock_load.call_count, 2)

    def test_download_update_ssl_fallback_with_and_without_checksum(self):
        import urllib.error
        from unittest.mock import patch, MagicMock
        checker = self.UpdateChecker()

        # Without expected_sha256: SSL error must be re-raised (no unverified download without hash)
        with patch("src.core.updater._open_url", side_effect=urllib.error.URLError("certificate verify failed")):
            with self.assertRaises(RuntimeError) as ctx_err:
                checker.download_update("https://example.com/test.exe", expected_sha256=None)
            self.assertIn("certificate verify failed", str(ctx_err.exception))

        # With expected_sha256: allowed fallback and SHA-256 validation
        call_count = [0]
        payload = b"trusted-installer-payload"
        expected_hash = hashlib.sha256(payload).hexdigest()
        def mock_open_url_dl(req, timeout=120, allow_unverified_fallback=False):
            call_count[0] += 1
            if not allow_unverified_fallback:
                raise urllib.error.URLError("certificate verify failed")
            mock_resp = MagicMock()
            mock_resp.headers = {"Content-Length": str(len(payload))}
            mock_resp.read.side_effect = [payload, b""]
            mock_resp.__enter__.return_value = mock_resp
            return mock_resp

        with patch("src.core.updater._open_url", side_effect=mock_open_url_dl):
            tmp_path = checker.download_update("https://example.com/test.exe", expected_sha256=expected_hash)
            self.assertIsNotNone(tmp_path)
            self.assertTrue(os.path.exists(tmp_path))
            os.unlink(tmp_path)
            self.assertEqual(call_count[0], 2)


if __name__ == "__main__":
    unittest.main()

