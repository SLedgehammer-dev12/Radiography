# -*- coding: utf-8 -*-
"""dmgbuild settings for Radiography.
Volume name can be overridden via env DMG_VOLUME_NAME for CI builds.
"""

import os
import sys


def _app_version():
    """Reads the version from src/core/version.py (single source of truth)."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from src.core.version import VERSION
        return str(VERSION)
    except Exception:
        pass
    vfile = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src", "core", "version.py")
    try:
        import re

        with open(vfile, "r", encoding="utf-8") as f:
            match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', f.read())
            if match:
                return match.group(1)
    except OSError:
        pass
    return "0.0.0"


APP_NAME = "Radiography"
VOLUME_NAME = os.environ.get("DMG_VOLUME_NAME", f"Radiography {_app_version()}")
APP_PATH = os.path.abspath(os.path.join("dist", "Radiography.app"))

icon = os.path.abspath("app.icns")

window_rect = ((200, 200), (500, 400))

icon_locations = {
    APP_NAME: (140, 180),
    "Applications": (360, 180),
}

applications_aliases = True

format = "UDZO"
compression_level = 9

files = [APP_PATH]
symlinks = {"Applications": "/Applications"}