# Changelog

## [1.2.0] - 2026-06-08

### Added
- ISO 17636-2 digital detector support (CR/DDA with DQE-based speed modeling)
- API 1104 defect evaluation module (crack, IP, IF, IC, porosity)
- Level 3 Authority exceptions panel (voltage override, distance compensation, etc.)
- Procedure compliance checker (applied vs required parameters)
- Multi-language support (Turkish / English) with full UI retranslation
- Dynamic weld geometry sketch with matplotlib (Qt Agg canvas)
- Standard ISO 17636 figure schematics (Figures 5, 6, 7, 11, 12, 13)
- Exposure chart database (R-Factor SCRATA + Type X chart)
- Filter/screen recommendations per ISO 17636-1 Table 1
- Automatic update checker via GitHub Releases
- ASME B36.10 standard pipe dimensions table
- PDF inspection report generation with ReportLab
- Dark/Light theme toggle (Catppuccin Mocha / Professional Slate)
- Edge case handling for extreme thicknesses, zero values, and missing data
- Comprehensive test suite (133 tests)

### Changed
- Version management centralized to `src/core/version.py`
- CI/CD pipeline now builds universal2 macOS binaries
- GitHub Release workflow extracts notes from CHANGELOG.md
- DMG volume name is dynamically set from git tag
- Windows .exe renamed with version and platform suffix

### Fixed
- GitHub repo URL typo in updater (`Radiogrphy` -> `Radiography`)
- English translation strings cleaned of Turkish words
- Theme contrast in popup dialogs (QMessageBox, Level3 dialog)
- Info button and output label colors adapt to active theme
- Sketch canvas colors update on theme toggle

## [1.1.0] - 2026-05-15

### Added
- Initial dual-language support framework
- Basic PDF report generation
- Weld geometry calculator (SWSI, DWSI, DWDI)
- ISO 17636-1 Class A/B compliance checks
- Geometric unsharpness and minimum distance calculations

## [1.0.0] - 2026-04-01

### Added
- First stable release
- Core RT exposure time calculator
- PyInstaller packaging for Windows and macOS
- Basic Qt6 GUI with input/output form
