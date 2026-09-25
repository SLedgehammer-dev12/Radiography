#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Packages the built web app into distributable launchers.

Modes
-----
* default            -> versioned zips with the Python launcher scripts
                        (recipients need Python 3 installed)
* ``--onefile``      -> single-file executable for the host platform
                        (Windows: RadiographyWeb.exe with icon + version info;
                         macOS: "Radiography Web <ver>.app" with icon)
* ``--dmg``          -> additionally wraps the macOS .app into a versioned DMG

Examples (repository root)::

    python3 web/launcher/package.py
    python3 web/launcher/package.py --onefile
    python3 web/launcher/package.py --onefile --dmg
"""

import argparse
import os
import plistlib
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
WEB = HERE.parent
REPO = WEB.parent
DIST = WEB / "dist"
OUT = REPO / "release-artifacts"
BUILD = HERE / ".build"

LAUNCHERS = {
    "macos": "Radiography Web.command",
    "windows": "Radiography Web.bat",
}


def read_version() -> str:
    source = (REPO / "src" / "core" / "version.py").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', source)
    return match.group(1) if match else "0.0.0"


def ensure_dist() -> None:
    if not (DIST / "index.html").exists():
        sys.exit("dist/ bulunamadi. Once derleyin:  cd web && npm install && npm run build")


# ---------------------------------------------------------------------------
# Python-launcher zips (no compilation)
# ---------------------------------------------------------------------------
def make_zip(platform: str, version: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / f"Radiography-Web-{version}-{platform}.zip"
    launcher = LAUNCHERS[platform]

    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(HERE / "serve.py", "serve.py")

        info = zipfile.ZipInfo(launcher)
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o755 << 16  # executable for macOS Archive Utility
        archive.writestr(info, (HERE / launcher).read_bytes())

        for path in DIST.rglob("*"):
            if path.is_file():
                archive.write(path, str(Path("dist") / path.relative_to(DIST)))

    return target


# ---------------------------------------------------------------------------
# Single-file executables (PyInstaller)
# ---------------------------------------------------------------------------
WINDOWS_VERSION_TEMPLATE = """VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({v0}, {v1}, {v2}, 0),
    prodvers=({v0}, {v1}, {v2}, 0),
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable('040904B0', [
        StringStruct('CompanyName', 'Radiography'),
        StringStruct('FileDescription', 'Radiography Web - RT exposure calculator'),
        StringStruct('FileVersion', '{version}'),
        StringStruct('InternalName', 'RadiographyWeb'),
        StringStruct('OriginalFilename', 'RadiographyWeb.exe'),
        StringStruct('ProductName', 'Radiography Web'),
        StringStruct('ProductVersion', '{version}'),
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


def _version_tuple(version: str):
    parts = [int(part) for part in re.findall(r"\d+", version)[:3]]
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def _write_build_version_module(version: str) -> Path:
    BUILD.mkdir(parents=True, exist_ok=True)
    module = BUILD / "version.py"
    module.write_text(f'__version__ = "{version}"\n', encoding="utf-8")
    return module


def _pyinstaller_available() -> bool:
    try:
        import PyInstaller  # noqa: F401

        return True
    except ImportError:
        return False


def build_onefile(version: str) -> Path:
    ensure_dist()
    if not _pyinstaller_available():
        sys.exit("PyInstaller gerekli:  pip install pyinstaller")

    is_windows = sys.platform.startswith("win")
    is_macos = sys.platform == "darwin"
    name = "RadiographyWeb" if is_windows else f"Radiography Web {version}"
    separator = ";" if is_windows else ":"

    version_module = _write_build_version_module(version)
    build_dist = BUILD / "dist"
    work = BUILD / "work"
    specs = BUILD / "spec"

    # Windows: true single-file .exe. macOS: onedir inside the .app bundle
    # (fast startup; PyInstaller v7 rejects onefile + .app bundles).
    bundle_mode = "--onedir" if is_macos else "--onefile"

    command = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", bundle_mode, "--windowed",
        "--name", name,
        "--distpath", str(build_dist),
        "--workpath", str(work),
        "--specpath", str(specs),
        "--add-data", f"{DIST}{separator}dist",
        "--add-data", f"{version_module}{separator}.",
        "--add-data", f"{HERE / 'RadiographyWeb.ico'}{separator}.",
        "--add-data", f"{HERE / 'RadiographyWeb.png'}{separator}.",
    ]

    if is_windows:
        version_file = BUILD / "version_info.txt"
        version_file.write_text(
            WINDOWS_VERSION_TEMPLATE.format(
                version=version, v0=_version_tuple(version)[0],
                v1=_version_tuple(version)[1], v2=_version_tuple(version)[2],
            ),
            encoding="utf-8",
        )
        command += ["--icon", str(HERE / "RadiographyWeb.ico"),
                    "--version-file", str(version_file)]
    elif is_macos:
        command += ["--icon", str(REPO / "app.icns"),
                    "--osx-bundle-identifier", "com.radiography.web"]

    command.append(str(HERE / "app_entry.py"))
    subprocess.run(command, check=True, cwd=str(REPO))

    OUT.mkdir(parents=True, exist_ok=True)
    if is_windows:
        built = build_dist / "RadiographyWeb.exe"
        target = OUT / f"Radiography-Web-{version}-Windows-x64.exe"
        shutil.copy2(built, target)
        return target

    if is_macos:
        app = build_dist / f"{name}.app"
        _patch_macos_info_plist(app, version)
        target = OUT / f"Radiography Web {version}.app"
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(app, target, symlinks=True)
        return target

    built = build_dist / name
    target = OUT / f"Radiography-Web-{version}-Linux-x64"
    shutil.copy2(built, target)
    return target


def _patch_macos_info_plist(app: Path, version: str) -> None:
    info = app / "Contents" / "Info.plist"
    data = plistlib.loads(info.read_bytes())
    data["CFBundleShortVersionString"] = version
    data["CFBundleVersion"] = version
    data["CFBundleDisplayName"] = f"Radiography Web {version}"
    info.write_bytes(plistlib.dumps(data))


def build_dmg(app_path: Path, version: str) -> Path:
    if sys.platform != "darwin":
        sys.exit("--dmg yalnizca macOS'ta uretilebilir.")
    staging = BUILD / "dmg"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    shutil.copytree(app_path, staging / app_path.name, symlinks=True)
    os.symlink("/Applications", staging / "Applications")

    target = OUT / f"Radiography-Web-{version}-macOS.dmg"
    if target.exists():
        target.unlink()
    subprocess.run(
        [
            "hdiutil", "create",
            "-volname", f"Radiography Web {version}",
            "-srcfolder", str(staging),
            "-ov", "-format", "UDZO",
            str(target),
        ],
        check=True,
    )
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Radiography Web packager")
    parser.add_argument("--platform", choices=sorted(LAUNCHERS), default=None,
                        help="sadece bu platform icin zip uret")
    parser.add_argument("--onefile", action="store_true",
                        help="host platform icin tek dosya calistirilabilir uret")
    parser.add_argument("--exe", action="store_true",
                        help="--onefile ile ayni (geriye donuk uyumluluk)")
    parser.add_argument("--dmg", action="store_true",
                        help="macOS .app'i versiyonlu DMG'ye paketle (--onefile ile)")
    args = parser.parse_args()

    version = read_version()

    if args.onefile or args.exe or args.dmg:
        artifact = build_onefile(version)
        print(f"Tek dosya: {artifact}")
        if args.dmg:
            dmg = build_dmg(artifact, version)
            print(f"DMG: {dmg} ({dmg.stat().st_size / 1_048_576:.1f} MB)")
        return 0

    ensure_dist()
    platforms = [args.platform] if args.platform else list(LAUNCHERS)
    for platform in platforms:
        target = make_zip(platform, version)
        print(f"Paketlendi: {target} ({target.stat().st_size / 1_048_576:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
