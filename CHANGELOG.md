# Changelog

## [1.8.3] - 2026-09-25

### Fixed (Android build)
- The FileProvider `<provider>` block was placed in
  `android.extra_manifest_application_arguments`, which only accepts attributes
  on the `<application>` tag; the resulting AndroidManifest.xml could not be
  parsed by the manifest merger. The provider is now injected by a small
  python-for-android hook (`src/android/p4a_manifest_hook.py`, `after_apk_build`)
  and `@xml/file_paths` is copied via `android.res_xml`
- With the kivy recipe fix from 1.8.2, the Android pipeline now reaches the
  gradle assembly stage instead of failing while building kivy

## [1.8.2] - 2026-09-24

### Fixed (CI / Android build)
- The local kivymd and reportlab recipes installed their dependencies with pip
  without `--no-deps`, which made pip rebuild kivy from source outside the kivy
  recipe environment (no `NDKPLATFORM`) and fail with `GL/gl.h file not found`.
  Both recipes now pass `--no-deps`; Pillow is provided by its p4a recipe
- The Android retry loop no longer masks failures: the job fails after four
  failed attempts, and a missing APK artifact is now an error instead of a
  warning. `NDKPLATFORM`/`KIVY_CROSS_PLATFORM` are also exported to the build
  container as a safeguard

## [1.8.1] - 2026-09-24

### Fixed (analog/digital separation — ISO 17636-1 vs ISO 17636-2)
- Analog radiography now always uses the film model (b = t for SWSI/DWSI,
  b = De for DWDI, f_min = C·d·b^(2/3)); the digital-only planar-detector
  formulae (8)/(9)/(13), b_ed and f_min* no longer leak into analog mode through
  the hidden detector-shape radio
- SFD_min/SDD_min receptor constraint is now mode-aware:
  analog uses the film diagonal (SFD >= 1.4·df, ISO 17636-1 Formula 4), digital
  uses the panel active-area diagonal (SDD >= 1.4·dd, ISO 17636-2 Formula 7)
- Analog film size input added (preset 80x300 / 100x400 / 300x400 / 100x500 +
  custom width/height) with automatic df = sqrt(w²+h²) and an explanatory
  warning when df is missing
- The standalone "Detector Size (dd)" field was removed; dd is now derived from
  the existing panel active-area dimensions (single source of truth). Default
  200x200 panel -> dd = 282.8 mm -> SDD_min = 396 mm (was 280 mm)
- Mode isolation: Annex F (Ug/SRb) runs only for digital, and digital-only
  values (SRb, duplex, SNR, panel exposures) / analog-only values (film class,
  optical density, film overlap) are no longer computed or stored in the other
  mode
- Output labels are mode-aware: "Minimum Source-to-Film (SFD_min)" vs
  "Minimum Source-to-Detector (SDD_min)", "Applied SFD/SDD"
- Wire/step-hole IQI display now carries the active standard prefix
  (ISO 17636-1 for analog, ISO 17636-2 for digital)

### Fixed (standard figures + b_ed)
- Standard-figure list is filtered by technology AND detector shape:
  analog -> ISO 17636-1 figures (5, 6, 7, 11, 12, 13, 14);
  digital flexible -> 5a, 6a, 7a, 8a, 9a, 10a, 11, 12, 13a;
  digital planar -> 2b, 5b, 8b, 9b, 10b, 13b, 14b, 11, 12
- Figure 14b is now correctly listed under DWSI (not DWDI) and Figure 10b under
  SWSI (not DWSI); Figure 14 (ISO 17636-1) and the digital 2b/5b/13b/8a/9a/10a
  schematics were added
- Presets store/restore the standard figure by data key (index is no longer
  stable because the list depends on technology and detector shape)
- Planar DWSI: when the edge lift (bed) is left at 0 it is computed
  automatically with Formula (10) (b_ed = (1-cos(pi/N))·r_e) and reported; SWSI
  planar with bed = 0 emits a warning to use Figure 23 / a scaled drawing

### Tests
- 91 new scenarios (mode separation, film model, df/dd engine, figure mapping,
  b_ed automation, schematic coverage); matrix oracle DWSI wire-IQI reference
  corrected to w = 2t per ISO 17636-1/2:2022 6.9 (697 total tests)

## [1.8.0] - 2026-09-24

### Fixed (geometry correctness — ISO 17636-1/2:2022, ASME Sec V Art 2)
- Geometric unsharpness now uses f = SDD − b (source-to-object distance) instead
  of the full SDD; the previous value understated Ug (up to ~15 %+ for DWDI/large
  object-to-detector distances) and could wrongly pass ASME/Annex F checks
- Planar/rigid detector model corrected and UI labels renamed:
  "Planar (Rigid Panel)" now uses b = bed + bgap + k·t (Formulae 8/9) and
  Formula (13) f_min* as the GOVERNING value; "Flexible (Wrapped CR/IP)" uses
  b = t and Formulae (2)/(3). The previous flat/curved behaviour was inverted and
  the Formula (13) result was silently discarded by max(f_min, f_min*)
- DWDI always uses b = De per Clause 7.6 (the planar-detector formula was wrongly
  applied to DWDI as well)
- DWSI physical SFD floor: SFD_min = max(f_min + b, 1.4·dd, De + bgap); a warning
  is emitted when the applied SFD is physically impossible (source inside pipe).
  ISO 7.6 determines f_min for DWSI by wall thickness only — b = t is unchanged
- `calculate_dwsi_exposures` clamps impossible SFD values (SFD ≤ De/2 previously
  produced nonsense counts) and guards degenerate (solid) pipes
- Level 3 reductions (DW −20 %, central projection −50 %) are now applied inside
  the shared geometry block, so f_min AND sfd_min are updated consistently in the
  UI, `last_calculated`, the compliance checker and the PDF report
- ASME Sec V Art 2 mode now derives f_min = d·b/Ug_limit(T-274.2) and shows it in
  a separate row; SFD compliance is checked against the ASME value. The ASME Ug
  check now uses the corrected denominator
- Standards references updated to the 2022 editions (f_min → 7.6 Formulae 1/2,
  exposures → Annex A, density → 7.8/Table 5, film class → Tables 3/4,
  duplex → 6.7.2, SNR_N → 7.3.1/Tables 3-4, SRb → B.13/B.14, panel → 7.8/Annex A)
- PDF report now renders the same f_min/sfd_min/Ug values as the screen (it used
  to recompute without Level 3 reductions), adds the Ug and ASME f_min rows and
  uses the dynamic target SNR for distance compensation instead of hardcoded
  130/70
- Report generator never raises: formatting/image errors return False instead of
  aborting, corrupt sketch images fall back to a placeholder, blank warnings are
  filtered, and plain dict language objects (mobile) now render the correct
  language
- Mobile (Phase 1): digital compliance no longer crashes (SNR tuple unpacking),
  the exposure screen SFD now drives Ug/time/exposure counts, applied values and
  the exposure-count check are wired, source-side IQI semantics match desktop,
  required optical density is 2.0/2.3/3.0, defect results are normalized to dicts
- Missing tooltips added (`tt_ug`, `tt_req_exposures`, `tt_single_wire_iqi`,
  `tt_duplex_iqi`, `tt_f_min_asme`) and stale clause texts removed

### Tests
- 185 new parametrized scenarios: geometry/Ug/f_min*/b helpers, DWSI physical
  constraint, Level 3 propagation, ASME geometry, PDF↔screen consistency,
  standards references and mobile parity (458 total tests)
- Fixed Windows CI failure: the updater tests now build `file://` URLs with
  `pathlib.Path.as_uri()` (the malformed `file://C:\...` URL was the reason the
  v1.7.0 release pipeline never produced a release)

### Upgrade note
- Calculation results intentionally change for planar/rigid detectors (b now
  includes bed + bgap + k·t and Formula (13) f_min* governs) and for large-diameter
  DWSI (physical SFD floor De + bgap). These corrections follow ISO 17636-2:2022
  Clause 7.6; review existing procedures/technique sheets before re-use.
- Saved presets remain compatible; the detector-shape radio buttons are renamed
  ("Planar (Rigid Panel)" / "Flexible (Wrapped CR/IP)") but keep their state keys.

## [1.7.0] - 2026-08-29

### Fixed (macOS crash hardening)
- Global exception handler in `main.py`: unhandled PyQt6 slot exceptions are now
  logged to `~/Library/Logs/Radiography/` instead of calling `qFatal()`/`abort()`
- Isotope decay tool no longer crashes when the calibration date is empty or in a
  non-ISO format (`calculate_decayed_activity` never raises on bad dates)
- PDF report export no longer crashes when user report fields contain XML special
  characters (`&`, `<`, `>`) — all user text is escaped for ReportLab Paragraph
- Update checker no longer crashes when GitHub returns `null` release notes, and
  the download progress callback no longer touches Qt widgets from the worker
  thread (thread-safety)

### Fixed (calculation correctness)
- Metric/imperial toggle no longer double-converts standard ASME pipe dimensions
  (114.3 mm was becoming ~2903 mm); custom entries are still converted to mm
- Defect evaluation (API 1104 / ISO 5817 / ASME) now converts inch inputs to mm;
  a 1.0" indication is no longer evaluated as 1.0 mm
- Mobile calculation engine rewritten: weld cap now included in `w_eff`, and
  `f_min`/`sfd_min`/`Ug`/SDD are computed with real geometry instead of zero
- Mobile procedure-compliance check no longer always errors (tuple `.get` misuse)
- PDF report now uses the dynamic DWDI elliptical exposure count (3 when
  t/De >= 0.12) instead of a hardcoded 2
- PDF and UI share the same geometry block (`_compute_geometry`), so `f_min*`
  (magnification rule) is consistent between screen and report
- Film-speed fallback now matches the documented default (C5 = 16.0)
- Date parsing accepts DD.MM.YYYY / DD/MM/YYYY / DD-MM-YYYY formats

### Fixed (security)
- Updater no longer silently falls back to an unverified SSL context (MITM risk);
  downloaded installers are verified with SHA-256 when a hash is available
- Android PDF sharing uses FileProvider (`content://`) instead of `Uri.fromFile`
  (FileUriExposedException on Android 7.0+)

### Added
- ISO 17636-2 digital detector figures (8b/9b/10b/14b) added to the standard
  schematic selector
- Setup sketch weld caps now scale with the user-entered cap height
- `get_filter_recommendations` returns language-neutral structural data; TR/EN
  formatting moved to the i18n layer (`format_filter_recommendation`)
- Approximate-standard disclaimer (ISO 5817 / ASME B31.3 / ASME VIII) shown in
  the defect evaluation UI and PDF report
- Version is read from a single source (`src/core/version.py`) for dmgbuild and
  synced into `buildozer.spec` by CI

### Infrastructure
- `certifi` added to `pyproject.toml` dependencies; mobile pipe list sorted by
  numeric outer diameter instead of fragile string parsing

## [1.6.2] - 2026-08-27

### Added
- ISO 17636-1:2022 Clause 7.3 lead-screen table: source/kV-based front/back lead
  screen thickness ranges returned by `get_filter_recommendations` (`screen_table`)
  and shown in the filter recommendation output
- Setup schematic now includes a true metre-scale plan-view inset of the radiation
  safety perimeter (pipe drawn to real scale inside the actual safety-circle radius)

## [1.6.1] - 2026-08-26

### Added
- Mobile parity: Yb-169 / Tm-170 selectable as radiation sources on Android, and
  the radiation barrier distance (controlled/supervised) shown on the results screen
- `qrcode` added to `pyproject.toml` dependencies (kept in sync with requirements)

### Fixed
- Android APK build: install Mesa/OpenGL dev headers (`libgl1-mesa-dev`,
  `libglu1-mesa-dev`, `mesa-common-dev`) in the buildozer docker so the kivy
  wheel build can find `GL/gl.h`

### Docs
- `RELEASE.md`: standard-values verification (QA) checklist for the approximate
  ISO 5817 / ASME / ASTM / isotope tables

## [1.6.0] - 2026-08-26

### Added
- Isotope decay engine: `calculate_decayed_activity` (A0·2^(-Δt/T½)) with half-lives
  for Ir-192, Se-75, Co-60, Yb-169, Tm-170 + an "Isotope Decay Tool" dialog that
  auto-fills the current activity from serial/initial activity/calibration date
- Selectable gamma dose-rate convention (R·m²/(h·Ci) or mSv·m²/(h·Ci)) for the
  radiation barrier calculation
- Radiation safety perimeter ring drawn on the setup schematic (metre-scale value)
- ASTM E747 real wire table (wires 1-21, Sets A-D) and ASTM E1025 T-276 hole IQI
  with selectable 2-2T / 2-1T / 1-2T sensitivity
- ASME B31.3 Table 341.3.2 defect evaluator (Normal Fluid / Severe Cyclic)
- ASME Section VIII Div.1 UW-51 / UW-52 defect evaluator
- Mobile defect-standard selector (API 1104 / ISO 5817 / ASME B31.3 / ASME VIII)
- Report: Revision No, Joint ID and formal Level II / Level III approval blocks
  (ISO 9712 / SNT-TC-1A name + certificate, stamp area)
- CSV project export/import and built-in named inspection presets
- DWDI elliptical beam angle computed from x = SFD·tan(alpha)
- Full metric/imperial coverage for detector, bed/bgap, panel and overlap inputs

### Fixed
- Qt abort in the offscreen test runner caused by re-applying the application-wide
  stylesheet on every window; the app stylesheet is now only applied when it changes,
  and the startup update timer is parented to the window
- Test determinism: QSettings are cleared between tests

## [1.5.0] - 2026-08-26

### Added
- Inspection standard selector (ISO 17636 / ASME Sec V Art 2):
  - ASME T-274.2 geometric unsharpness limits (0.51/0.76/1.02/1.78 mm) and compliance check
  - ASTM E1025 (2-2T hole) and E747 (wire, 2% sensitivity) IQI requirements
- Radiation safety barrier distance (NDK/TAEK & IAEA practice):
  - Dose-rate model D(R)=Γ·A/R² with collimator/shielding HVL selection
  - Controlled (20 µSv/h) and supervised (7.5 µSv/h) area distances in results and PDF
- Extended isotope library: Yb-169 and Tm-170 (mu, HVL, gamma, exposure defaults, Table 2 already defined)
- Radiographic Equivalence Factors (REF) for steel/copper/titanium/aluminum (informational)
- Official NDT report header fields (Report No, Project/Client, Welder ID, WPS/PQR, Procedure No, Device Serial, Calibration Date, Personnel/Cert) rendered in the PDF
- Verification QR code in the PDF report (optional `qrcode` package)
- Preset (template) save/load and full project JSON export/import via the Data menu
- ISO 5817 quality-level defect evaluation (levels B/C/D) with a defect-standard selector in the module
- Metric/imperial (mm ↔ inch) toggle for the main dimensional inputs
- DWDI elliptical schematic: source offset and 10-15° beam-angle annotations; flat-panel DDA coverage overlay with the minimum 10 mm overlap band
- Turkish-character-safe PDF fonts: bundled real Noto Sans TTFs with Arial-first, Noto Sans fallback (WinAnsi Helvetica cannot render Ğ/İ/ş/ı)
- Report identity: owner (ÖMER ERBAŞ), liability disclaimer, and contact channels (GitHub Issues + email) in About and PDF

### Fixed
- Mobile PDF used WinAnsi Helvetica (broken Turkish chars); the bundled Noto Sans were invalid HTML files — replaced with real static TTFs and wired into the font resolution chain
- `pdf_helper.py` reported `tech_text` from geometry instead of the RT technology

## [1.4.1] - 2026-08-25

### Added
- Dynamic Output Results Visibility:
  - Isotope sources hide Tube Voltage ($U_{\text{max}}$) output row cleanly (no irrelevant "N/A" clutter).
  - Analog Film hides Duplex IQI and DDA Flat-Panel exposure rows; updates target label to Optical Density ($D$) and detector quality to Required Film Class.
  - Digital Mode shows Duplex IQI and Flat-Panel exposure count rows; updates target label to $\text{SNR}_N$ and detector quality to Required Detector Class / $\text{SR}_b$.
- Analog Film Applied Exposure Count Input & Procedure Compliance Check:
  - Applied Exposure Count is now accessible and active for Analog Film inspections.
  - `procedure_check.py` evaluates analog exposure counts against ISO standard minimums (DWSI/DWDI/SWSI) with localized pass/fail messages (`exp_pass_analog` / `exp_fail_analog`).
- Multi-Platform Update Robustness & SSL Fallback:
  - Windows PyInstaller builds now package `certifi` CA certificates (`cacert.pem`) in datas.
  - `updater.py` incorporates SSL verification fallback to guarantee update checks succeed across all Windows systems and restrictive network environments.
  - Multi-platform asset downloader accurately resolves `.exe` (Windows), `.dmg` (macOS), and `.apk` (Android) releases.
- Android APK buildozer / p4a recipe modernized:
  - ReportLab recipe replaced with modern Pure Python (`PythonRecipe`) using PyPI sdist, eliminating legacy C-extension compilation and broken FTP dependencies.

## [1.4.0] - 2026-08-25

### Added
- Isotope source activity (Ci / GBq) dynamic input and conversion:
  - Added unit selector (Curie / Gigabecquerel) on desktop and mobile with automatic $1\text{ Ci} = 37\text{ GBq}$ conversion.
  - Added Activity (Ci) input and slider to Mobile Step 3 (Exposure).
  - Exposure time calculations correctly scale inversely proportional to isotope activity ($t \propto 1/A$) in both Physics and R-Factor models.
- Dynamic UI simplification based on technique and source:
  - **X-Ray vs Isotope:** X-Ray shows Tube Voltage (kV) and Amperage (mA) while hiding isotope activity; Isotope shows Source Activity while hiding kV/mA and dynamically adjusting focal size and base factor labels.
  - **Analog vs Digital:** Analog Film hides digital detector, DDA panel, SRb resolution, duplex IQI and SNR inputs; Digital hides film class, film overlap and density inputs.
- Unit tests for dynamic UI visibility, isotope activity inverse proportionality and activity unit conversion.

### Fixed
- Fixed mobile `app_state.py` where `output_val` was hardcoded to `ma` (5.0), causing incorrect isotope exposure times.
- Fixed `calculate_exposure_time` parameter mapping in `app_state.py`.

## [1.3.5] - 2026-08-13

### Fixed
- Update check on Windows no longer fails with `SSL Certificate Verify Failed: missing authority key identifier`:
  - The updater now uses an explicit CA bundle from `certifi` instead of relying on the default OpenSSL store, which PyInstaller-frozen builds cannot always resolve
  - `certifi` added to `requirements.txt` and to the PyInstaller spec (`hiddenimports`) so the `cacert.pem` bundle is shipped inside the .exe/.dmg

## [1.3.4] - 2026-08-13

### Fixed
- "Standart ISO Şekli" combo box no longer blank: the input-panel and standard-tab combos are now kept in sync (`_sync_std_figure_tab`)
- Dynamic setup schematic now honours the selected theme: `draw_setup` was hard-coded to dark colours, so the light theme never applied
- Fixed crash (`KeyError: f_min_applied`) on the panel coverage path when a fixed-geometry case returned early

### Added
- User-provided source-to-object distance (f) and object-to-detector distance (b) inputs (digital mode, blank = auto):
  - `calculate_panel_exposures` accepts `f_source`/`b_object` overrides
  - Measured geometry is checked against applied SFD, wall thickness and the Clause 7.6 `f_min = C·d·b^(2/3)` geometric limit
- Base Exposure Multiplier input (default 1.0): scales the calculated exposure time and the compliance reference to compensate for field conditions (film batch, chemistry, detector ageing, material composition)
- TR/EN translations and tooltips for the new fields; PDF report row for the base multiplier

## [1.3.3] - 2026-08-11

### Added
- Flat-panel DDA coverage-based minimum exposure count per ISO 17636-2:2022 (Clauses 7.6/7.8)
- New panel inputs (digital only): active width/height, digital image overlap %, applied exposures
- Panel vs standard/graph vs applied exposure comparison in outputs and procedure compliance check
- PDF report rows for panel/applied/check exposure values

### Infrastructure
- Fully automated GitHub release pipeline: on push to `main`, a version bump in `src/core/version.py` triggers Windows .exe + macOS .dmg + Android APK build and GitHub Release creation
- Version is now read from `src/core/version.py` in the macOS bundle plist

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
