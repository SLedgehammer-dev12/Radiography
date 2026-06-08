# Release Procedure

## Prerequisites
- Write access to the repository
- GitHub Actions enabled
- All secrets configured (if code signing is enabled)

## Steps

### 1. Update Version
```bash
# Edit src/core/version.py
__version__ = "1.2.1"

# Keep pyproject.toml in sync (same version string)
```

### 2. Update CHANGELOG.md
- Move items from `[Unreleased]` to a new version section
- Add the release date
- Review for completeness

### 3. Commit and Tag
```bash
git add src/core/version.py pyproject.toml CHANGELOG.md
git commit -m "Release v1.2.1"
git tag v1.2.1
git push origin v1.2.1
```

### 4. Automation
Pushing the tag triggers `.github/workflows/build.yml`:

```
Test (Ubuntu) → [parallel]
  ├── Build Windows .exe
  └── Build macOS .dmg (universal2)
       ↓
  Create GitHub Release
```

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
