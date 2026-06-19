# Changelog

## [1.3.2] - 2026-06-19

### Changed
- Extracted ASME B36.10 pipe data from inline dict in `input_panel.py` to shared `src/core/asme_b36.py`
- Created `ASME_B36_19_PIPES` dict for stainless steel pipe schedules (5S/10S/40S/80S)
- Generated `docs/asme_b36_10_19_pipe_data.json` — full pipe data export for external use
- Corrected outer diameter values per ASME B36.10-2022: 10"(273.1), 18"(457.2), 22"(558.8), 24"(609.6), 26"(660.4), 28"(711.2), 32"(812.8), 34"(863.6), 36"(914.4)
- Added missing schedules: SCH 160 + XXS for NPS 1/8–3/8
- Mobile Step 2 (Dimensions): replaced static 15-pipe list with full ASME B36.10 database + schedule sub-menu
- `buildozer.spec` source.include_patterns updated to include `src/core/asme_b36.py`

### Added
- Helper functions: `get_pipe_od()`, `get_pipe_schedules()`, `find_nps_by_od()`, `get_default_schedule()`
- 17 validation tests for `core.asme_b36`
- `pipe_schedule` attribute to `AppState` for mobile

## [1.3.1] - 2026-06-18

### Added (Mobile - KivyMD Android)
- Complete Material Design 3 responsive UI in KivyMD
- Compact wizard (<600dp): 5-step form (Technique → Dimensions → Exposure → Results → Sketch)
- Medium layout (600-839dp): NavigationRail (collapsed) + ScreenManager
- Expanded layout (≥840dp): NavigationRail (labeled) + ScreenManager
- Automatic foldable/layout switching via Window.size binding with state preservation
- Weld sketch engine: 10 Kivy Canvas drawing types (cross-section, longitudinal, double-wall, elliptical, superimposed, panoramic, girth weld, T-joint, source-film, defect map)
- PDF report generation with ReportLab + NotoSans font (Regular/Bold/Italic)
- Android Share Sheet integration (Pyjnius Intent ACTION_SEND)
- Singleton AppState manager with core calculator integration (~2200 lines)

### Infrastructure
- Buildozer spec for Android APK/AAB packaging
- GitHub Actions CI: Android APK build via kivy/buildozer-action
- Unified release pipeline: Windows .exe + macOS .dmg + Android APK under same version tag
- NotoSans static TTF fonts bundled for PDF generation

## [1.3.0] - 2026-06-13

### Added
- API 1104 defect types: slag, undercut, burn-through, cross-accumulation check
- Gradient-based density correction (ISO 17636-1 Annex C film gradient table)
- DWSI technique lookup from ISO 17636-1 Annex C
- Beam hardening approximation for X-ray
- QSettings persistence (window geometry, splitter sizes, theme, language, form state)
- Modular panel mixins (InputPanel, DefectPanel, WarningsCompliancePanel)

### Changed
- UI redesigned: 3-column horizontal splitter layout (inputs 25% | outputs+compliance 25% | sketch+warnings+defects 50%)
- Output values arranged vertically (QVBoxLayout) instead of grid
- Sketch displayed square in right panel top 50%
- Procedure compliance panel moved below calculation results
- Splitter handles thickened to 8px with hover color effects
- QGroupBox card-style background for visual depth
- Input field border-radius increased to 6px for softer look

### Fixed
- Restored missing `txt_app_time`, `lbl_app_time`, `cmb_app_wire`, `lbl_app_wire` widgets
- Fixed `cmb_app_duplex` userData assignment (currentData returned None)
- Replaced stray `print()` call with `logger.error()` in report module

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
