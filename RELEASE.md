# Release Procedure

## Standard Values Verification (QA)

The following tables use engineering approximations and **must be verified
against the current edition of the referenced standard** before use in formal
acceptance decisions:

| Module | Approximate values | Reference |
|---|---|---|
| `src/core/iso5817.py` | Quality-level limits for porosity, slag, undercut, IP/IF | ISO 5817 |
| `src/core/asme_b31_3.py` | Table 341.3.2 service limits | ASME B31.3 |
| `src/core/asme_viii.py` | UW-51 / UW-52 limits | ASME BPVC Sec. VIII Div. 1 |
| `src/core/calculator.py` (`E747_WIRE_DIA_MM`) | ASTM E747 wire diameters (1-21) | ASTM E747 |
| `src/core/calculator.py` (isotope `MU`) | Yb-169 / Tm-170 attenuation coefficients | NIST / manufacturer data |
| `src/core/exposure_charts.py` (`HVL`) | Yb-169 / Tm-170 half-value layers | manufacturer exposure charts |
| `src/core/calculator.py` (`GAMMA_*`) | Gamma constants (R and mSv conventions) | IAEA / source certificates |

Procedure: for each table, diff the implemented thresholds against the standard
text, update the constants, and add a regression test in `tests/`.

## Prerequisites
- Write access to the repository
- GitHub Actions enabled
- All secrets configured (if code signing is enabled)

## Steps

### 1. Update Version (all 5 spots — a partial bump ships a wrong version badge)
```bash
# 1. src/core/version.py  (__version__)
# 2. pyproject.toml  (version =)
# 3. buildozer.spec  (version =)
# 4. web/package.json  ("version":)
# 5. web/src/App.tsx  (FALLBACK_VERSION const — display-only fallback)
grep -rn "2.0.3" src/core/version.py pyproject.toml buildozer.spec web/package.json web/src/App.tsx
```

### 2. Update CHANGELOG.md
- Move items from `[Unreleased]` to a new version section
- Add the release date
- Review for completeness

### 3. Commit and Tag
```bash
git add src/core/version.py pyproject.toml buildozer.spec web/package.json web/src/App.tsx CHANGELOG.md
git commit -m "Release v2.0.3"
git tag v2.0.3
git push origin v2.0.3
```

### 4. Automation
Pushing the tag triggers `.github/workflows/build.yml`:

```
Test (Ubuntu) → [parallel]
  ├── Build Windows .exe
  ├── Build macOS .dmg (universal2)
  ├── Build Android .apk (does not block the release)
  └── Build Web launchers (Windows .exe + macOS .dmg)
       ↓
  Create GitHub Release
```

A push to `main` only releases when `src/core/version.py` is newer than the
latest tag; if the tag for the current version already exists, the release is
skipped (no duplicate builds). The web front-end additionally has its own
pipeline in `.github/workflows/web.yml` (core tests + Playwright + build +
optional GitHub Pages deploy).

### Release assets
- `Radiography-<ver>-Windows-x64.exe`, `Radiography-<ver>-macOS.dmg` (desktop)
- `Radiography-<ver>-Android.apk` (mobile, best effort)
- `Radiography-Web-<ver>-Windows-x64.exe`, `Radiography-Web-<ver>-macOS.dmg`
  (browser version; see `web/README.md`)

### 5. Verify
- Check [GitHub Actions](https://github.com/SLedgehammer-dev12/Radiography/actions) for green builds
- Verify the release appears on [Releases](https://github.com/SLedgehammer-dev12/Radiography/releases)
- Download and test both `.exe` and `.dmg` artifacts

## Version Schema
- `v1.2.1` — Patch: bug fixes, minor improvements
- `v1.3.0` — Minor: new features, backward compatible
- `v2.0.0` — Major: breaking changes

## Manual Workflow Dispatch
If tag push is not desired, go to:
```
Actions → Build & Release → Run workflow
```
Enter the version number and the build will use it.

## Code Signing (Optional)
### macOS
Set GitHub Secrets:
- `APPLE_CERTIFICATE`: Base64-encoded .p12 certificate
- `APPLE_CERTIFICATE_PASSWORD`: Certificate password
- `APPLE_ID`: Apple Developer account email
- `APPLE_ID_PASSWORD`: App-specific password
- `APPLE_TEAM_ID`: Team ID

### Windows
Set GitHub Secrets:
- `WINDOWS_CERT_BASE64`: Base64-encoded .pfx certificate
- `WINDOWS_CERT_PASSWORD`: Certificate password

## God-Class Split Plan (see docs/godclass-plan.md)

- `src/ui/main_window.py` (~3300 lines, 67 methods): split order A→D —
  (A) export_pdf_report → ReportExportMixin, (B) retranslate_ui → TranslationMixin,
  (C) get_form_values/_collect_engine_form → FormStateMixin, (D) __init__/init_ui last.
- `web/src/App.tsx` (~3150 lines): extract useAppForm/useReportInfo/useDefectState hooks;
  modal and helper functions already split out.
- Rule: one split per commit, test suite stays green, no behavior change.

## Maintainer Notes (bus factor: 1 — read before touching)

- **God-classes**: `src/ui/main_window.py` (~3300 lines) and `web/src/App.tsx` (~3150 lines) hold UI+state+events. Small, isolated changes only; any UI edit risks regression — run `tests/test_main_window.py` and the web smoke suite.
- **Single physics core**: all platforms share `src/core/` via `CalculationEngine`. Never fork formulas per platform. Web copies core into `web/public/python/` (gitignored) and syncs automatically (`npm run sync` in `predev`/`prebuild`); mobile has no copy — `buildozer.spec` packages `src/core/*.py` directly at build time.
- **Verify before release**: `python3 -m pytest tests/test_engine.py tests/test_calculator.py tests/test_main_window.py` and `npx tsc -b` in `web/`.
- **Orientation**: `PROJECT_INDEX.md` (stale after 7 days / 15 commits — regenerate, don't hand-edit).
