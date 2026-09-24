# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Radiography (macOS .app + Windows .exe)."""

import os
import sys

PROJECT_ROOT = os.getcwd()
sys.path.insert(0, PROJECT_ROOT)

block_cipher = None

# Dynamic version from single source of truth
from src.core.version import __version__ as APP_VERSION

try:
    from PyInstaller.utils.hooks import collect_data_files
    certifi_datas = collect_data_files('certifi')
except Exception:
    certifi_datas = []

datas = [
    ("exposure_chart_dataset.json", "."),
    ("exposure_chart_dataset.csv", "."),
    ("X-Ray Exposure Chart steel.png", "."),
    ("src/mobile/assets/fonts/NotoSans-Regular.ttf", "src/mobile/assets/fonts"),
    ("src/mobile/assets/fonts/NotoSans-Bold.ttf", "src/mobile/assets/fonts"),
    ("src/mobile/assets/fonts/NotoSans-Italic.ttf", "src/mobile/assets/fonts"),
] + certifi_datas

hiddenimports = [
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.QtWidgets",
    "PyQt6.QtNetwork",
    "PyQt6.sip",
    "reportlab",
    "reportlab.lib",
    "reportlab.lib.pagesizes",
    "reportlab.lib.styles",
    "reportlab.pdfbase",
    "reportlab.pdfbase.ttfonts",
    "reportlab.platypus",
    "matplotlib",
    "matplotlib.backends",
    "matplotlib.backends.backend_qtagg",
    "matplotlib.figure",
    "matplotlib.patches",
    "PIL",
    "PIL._imaging",
    "numpy",
    "importlib",
    "importlib.metadata",
    "urllib",
    "urllib.request",
    "ssl",
    "certifi",
    "json",
    "threading",
]

excludes = [
    "tkinter",
    "test",
    "distutils",
    "setuptools",
    "pip",
    "PyQt5",
    "notebook",
    "IPython",
    "jedi",
    "pdb",
]

a = Analysis(
    ["main.py"],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

if sys.platform == "darwin":
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        name="Radiography",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon="app.icns",
    )
    app = BUNDLE(
        exe,
        name="Radiography.app",
        icon="app.icns",
        bundle_identifier="com.radiography.app",
        info_plist={
            "NSHighResolutionCapable": True,
            "NSSupportsAutomaticGraphicsSwitching": True,
            "CFBundleShortVersionString": APP_VERSION,
            "CFBundleVersion": APP_VERSION,
            "NSHumanReadableCopyright": "© 2026 ÖMER ERBAŞ",
        },
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        name=f"Radiography-{APP_VERSION}",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon="app.ico",
    )
