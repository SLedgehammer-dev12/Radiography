# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Radiography (macOS .app + Windows .exe)."""

import os
import sys

PROJECT_ROOT = os.getcwd()
sys.path.insert(0, PROJECT_ROOT)

block_cipher = None

# Dynamic version from single source of truth
from src.core.version import __version__ as APP_VERSION

datas = [
    ("exposure_chart_dataset.json", "."),
    ("exposure_chart_dataset.csv", "."),
    ("X-Ray Exposure Chart steel.png", "."),
    ("ISO 17636-2 2022(E).pdf", "."),
    ("pdfcoffee.com_iso-17636-1-2022-pdf-free.pdf", "."),
]

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
            "CFBundleShortVersionString": "1.2.0",
            "CFBundleVersion": "1.2.0",
            "NSHumanReadableCopyright": "2026 Radiography",
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
