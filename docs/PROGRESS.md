# Progress Log

> Working log of completed and pending work. Updated per session.
> Last updated: 2026-10-17 (Release `v2.0.4`).

## Scope decision

- **Going forward: WEB ONLY.** Desktop (PyQt6) and Mobile (Kivy/Android APK)
  development is **stopped** as of 2026-10-17. Do not start new desktop/mobile
  work. The shared core (`src/core/`) is untouched and still serves all targets;
  only front-end work is redirected to `web/`.
- No desktop/mobile change made after this decision. Earlier same-session fixes
  are listed below.

## Completed this session (2026-10-17)

### Docs & tooling
- `PROJECT_INDEX.md` / `PROJECT_INDEX.json` — repo index (architecture, entry
  points, coupling, churn, risks). Freshness policy: stale after 7 days / 15 commits.
- `docs/godclass-plan.md` — god-class split plan (steps A–J).
- `RELEASE.md` — maintainer notes (5-spot version bump, god-class warning, release checks).
- `TODO_code-reviewer.md` — closed items CR-1.1/1.2/1.4/1.6/1.7 marked done (verified in code).
- `docs/PROGRESS.md` — this file.
- Commit `70ab040`.

### Fixes
- **Exposure-time calculation engines audit & fixes (Analog/Digital × X-Ray/Gamma)** —
  - Fixed **16× under-exposure bug** in `digital_xray_chart` / `dda_panel_chart` (X-Ray):
    `TYPE_X_CHART` is pre-divided by C5 film speed (`16.0`); digital mode now restores
    `exposure_mamin = raw_chart_mamin * 16.0` (`SNR_N = 70` `cr_standard` baseline) and
    reports `method = "digital_xray_chart"`.
  - Added **energy-dependent X-ray material equivalence** (`ref_factor_xray = mu(kV, mat) / mu(kV, steel)`)
    for non-steel materials in `type_x` and `digital_xray_chart`.
  - Passed `testing_class` to `calculate_dda_frame_integration` in `dda_panel_chart` (Gamma Ray)
    so Class A uses `16` frames vs `32` for Class B, and enforced DDA hardware acquisition floor
    (`max(2.0 if x_ray else 0.0, n_frames * 0.10)`).
  - Passed ISO 11699-1 film-class gradient `G̅` (`FILM_GRADIENT`) into R-factor density
    correction (`10^((D - 2.0) / G̅)`) and honored custom per-film R-factor overrides
    in `ExposureChartDatabase.calculate_exposure_time_rfactor`.
  - Applied `extra_multiplier` (`time_multiplier * base_multiplier`) inside
    `calculate_exposure_time_details` before `dda_frame_method` and hardware floor clamping;
    eliminated DDA `model` sawtooth step rounding by flooring at `min_acq_floor` instead of
    rounded `total_acq_sec`; computed `dose_rate_ugy_s` from un-clamped `t_frame_ideal`.
  - Compounded `se75_thin_class_b` (`×1.4`, ISO 17636-2 Clause 6.9) with
    `snr_location == "adjacent"` (`×1.4`, Table B.14) to `×1.96`; fixed `_check_kvp5`
    to compare `(kV_ref / kV)^5` against `exp((mu_cur - mu_ref) * w_eff)`; updated
    `dda_se` Co-60 R-factor to `0.065`; bidirectional `chart_source` ↔ `film_class_used`
    sync in `web/src/App.tsx` + mismatch warning in `engine.py`.
  - Expanded industrial NDT film catalog from 1 brand / 5 models to **4 brands / 22 models**
    across ISO 11699-1 classes `C1`–`C6`: **Carestream** (`DR50`, `M100`, `MX125`, `T200`,
    `AA400`, `HS800`), **Agfa Structurix** (`D2`, `D3`, `D4`, `D5`, `D7`, `D8`),
    **Fujifilm IX** (`IX25`, `IX50`, `IX80`, `IX100`, `IX150`), and **Foma Fomadux**
    (`R2`, `R4`, `R5`, `R7`, `R8`) with brand-preserving class/chart synchronization in
    `web/src/state/presets.ts` and `web/src/App.tsx`.
  - Expanded **Digital CR & DDA Detector** catalog from 5 generic categories to **10 industrial
    detector models** across ISO 16371-1 (`IPS-1`..`IPS-4`) and ASTM E2698/E2736:
    `cr_ips1_uhd` (40 µm, Waygate IPU / Dürr HD-IP / Carestream HR-50), `cr_highres` (50 µm,
    Carestream HR / Agfa MD4.1 / Fuji UR-1), `cr_standard` (100 µm, Carestream GP / Waygate IPC2 /
    Fuji ST-VI), `cr_fast` (130 µm, Carestream XL Blue / Waygate IPS / Fuji HR-V), `dda_si`
    (130 µm, Waygate DXR250C-W / Varex 2520DX / Carestream HPX-DR), `dda_si_hires` (75 µm,
    Varex XRpad4 3025 / Carestream HPX-ARC), `dda_se` (85 µm, Teledyne ICM / Analogic a-Se),
    `dda_gdos` (160 µm, Varex XRD 1621 / Waygate DXR250U-W), `dda_gdos_he` (200 µm,
    Varex XRD 1621 xN / Waygate DXR500L), and `dda_cmos` (50 µm, Teledyne DALSA Xineos /
    Varex Dexela), preserving indices `0..4` for desktop preset compatibility and mapping
    `cr_ips_chart` ↔ `dda_panel_chart` on CR/DDA switch.
  - Covered by 9 new regression tests in `tests/test_exposure_charts.py` and
    `tests/test_engine.py`.
- **DDA saturation advisory** — `dda_frame.t_frame_ideal` exposed; `engine.py`
  warns when `< 0.08 s` (reduce mA / increase SFD). Covered by
  `tests/test_engine.py::test_dda_high_dose_rate_saturation_advisory`.
- **About-dialog HTML escaping** — `html.escape()` on translation strings in
  desktop `_show_about`. Covered by
  `tests/test_main_window.py::test_show_about_escapes_translation_html`.
- **Web version fallback** — single `FALLBACK_VERSION` const replaces 6 hardcoded
  literals. Commit `70ab040`.

### Refactors — desktop god-class (`src/ui/main_window.py`: 3298 → 2114 lines)
- `9855b3e` A: `export_pdf_report` → `src/ui/panels/report_panel.py`
- `18096da` B: `retranslate_ui` → `src/ui/panels/translation_panel.py`
- `bf66bd7` C: `get_form_values` + `_collect_engine_form` → `src/ui/panels/form_state_panel.py`
- `8c24ef9` D: `init_ui` → `src/ui/panels/ui_build_panel.py`

### Refactors — web (`web/src/App.tsx`: 3149 → 2419 lines)
- `01b92e0` E: modals + `FALLBACK_VERSION` → `web/src/components/Modals.tsx`
- `94cbee4` E2: `svgToPngBase64`, `downloadBase64` → `web/src/lib/sketchExport.ts`;
  `selectedOdKey` → `web/src/state/presets.ts`
- `6acf023` F: defect state + reactive effect + `runDefect` → `web/src/state/useDefect.ts`
- `60bdf65` G: form/lvl3/lang/theme/reportInfo + persistence → `web/src/state/usePersistedAppState.ts`
- `78a422a` H: defect Group → `web/src/components/DefectPanel.tsx`
- `286dd7b` I: outputs Group + `OUTPUT_KEYS` + `outputLabel` → `web/src/components/OutputsPanel.tsx`
- (J, in progress) Compliance + Warnings Groups → `web/src/components/CompliancePanel.tsx`,
  `web/src/components/WarningsPanel.tsx` (App.tsx → 2383)
- (J, in progress) Report info Group → `web/src/components/ReportInfoPanel.tsx`
  (App.tsx → 2358)
- (J, in progress) Right-column sketch tabs → `web/src/components/SketchTabsPanel.tsx`
  (App.tsx → 2164); `ExposuresProvenance` type added to `types.ts`
- (J, done) Hero summary + DDA integration card + provenance builders →
  `web/src/components/HeroSummaryPanel.tsx` + `formatExposuresProvenance` in `web/src/i18n.ts`;
  shared domain constants exported from `web/src/state/presets.ts` (App.tsx → 1883 lines, −40%)

### Features & Audit Fixes (web)
- **Audit & lint pass** — `LengthSliderField` now scales `min` and `max` by `1/25.4`
  in inch mode (covered by E2E); `WarningsPanel` uses `t("no_warnings")` instead of
  hardcoded English; `useDefect` tracks `form.od`; all 6 `oxlint` warnings resolved
  (`0 warnings, 0 errors`).
- **Accessibility & error/loading polish (`4f84a81`)** — all modals (`DecayDialog`,
  `Lvl3Dialog`, `AboutModal`, `UpdateModal`) expose `role="dialog"` +
  `aria-modal="true"` and close on `Escape`; `InfoTip` supports `Enter`/`Space`
  activation and `Escape`-to-close; keyboard shortcuts (`Ctrl/Cmd+Enter`,
  `Ctrl/Cmd+S`) guard against `!ready`, key repeat, `pdfBusy`, and open modals;
  `.app-progress` and header status reflect both `busy` and `pdfBusy`;
  `OutputsPanel` and `CompliancePanel` handle initial loading and error states
  cleanly without sticking on "Calculating…" or flashing a false non-compliant badge.
- **Keyboard shortcuts** — `Ctrl/Cmd+Enter` exports the PDF, `Ctrl/Cmd+S` saves
  the current form as a preset (browser save dialog suppressed). PDF button
  title hints the shortcut. E2E covers both.
- **Loading feedback** — indeterminate progress bar at the bottom of the sticky
  header while a calculation/PDF export runs; outputs panel shows a
  "Hesaplanıyor… / Calculating…" empty state before the first result.
- **Sticky action bar** — topbar + menu bar wrapped in a sticky header; topbar now
  carries always-visible primary actions: **Reset** (form → defaults) and
  **Export PDF**. New E2E in `web/tests/e2e/feedback.spec.ts` (reset + sticky).
- **Interaction & feedback** — toast now carries a kind (info/success/error) with
  colour-coded left border, a close button, `role="alert"` for errors, and
  auto-dismiss (4.5s info/success, 8s error). New E2E:
  `web/tests/e2e/feedback.spec.ts`.
- **Mobile / responsive UX** — `web/src/App.css` gains a touch/mobile block:
  hides the desktop-only custom scrollbar on coarse pointers; 16px form controls
  on phones (stops iOS focus auto-zoom); ≥40px tap targets for buttons, tabs,
  radios (keeping inline `.sync-btn`/`.sketch-mini-btn` pills compact at 28px);
  sketch tabs wrap instead of ellipsising; tighter mobile padding.
  New E2E: `web/tests/e2e/mobile.spec.ts` (390×844, touch) — no horizontal
  overflow, 16px inputs, tap-to-open info modal.

## Verification (re-run before continuing)

```bash
python3 -m pytest -q                    # 930 passed, 6 skipped, 849 subtests
cd web && npx tsc -b                    # clean
cd web && npx oxlint src/               # 0 warnings, 0 errors
cd web && npx playwright test           # 44 passed (9 E2E spec files)
```

### UX & Catalog Polish (web)
- **Native `<optgroup>` categorization** — `SelectField` accepts an optional `group`
  property on options and cleanly renders native `<optgroup label={group}>` blocks
  without custom DOM wrappers or breaking keyboard accessibility.
- **Detector & film brand groupings** — Digital detectors grouped into **CR (ISO 16371-1)**
  and **DDA (ASTM E2698)**; 22 analog isotope film charts grouped into **Carestream**,
  **Agfa Structurix**, **Fujifilm IX**, **Foma Fomadux**, and **Calculation Model**;
  selecting any film model (e.g. `D7`, `R8`) automatically syncs `film_class_used`.
  Covered by new Playwright E2E in `web/tests/e2e/analog-ui.spec.ts`.
- **Web UI/UX Usability Iteration 1 (Kullanım Kolaylığı Geliştirmeleri)**:
  - **Quick Presets Chips Bar**: 1-click preset chips bar (`.preset-chips-bar`) at the top of the inputs column for instant switching between workshop X-ray and field isotope setups without hunting through dropdown menus.
  - **Sticky Header "⚡ Uygula / Sync" Button**: Instant synchronization of calculated targets (`sfd_min`, `req_exposures`, `calc_time`, `app_wire`) into applied fields directly from the sticky header.
  - **Collapsible Input Sub-Sections**: Separated the monolithic 400-line inputs column into 3 semantic collapsible `<Group>` blocks (`1. Boru ve Kaynak Geometrisi`, `2. Radyasyon ve Çekim Tekniği`, `3. Standart ve IQI Şartları`) plus applied parameters, significantly reducing vertical scrolling on laptops and tablets.
  - **Copy to Clipboard & Inspection Summary**: Added "📋 Özeti Kopyala" (copies full standardized RT field notes to clipboard) and click-to-copy handlers on calculated hero values with success toast notifications.
  - Verified with 35 Playwright E2E tests, 0 `oxlint` errors, and clean TypeScript build.
- **Dual Dynamic $f_{\min}$ Calculation & Step-by-Step Info Modal**:
  - Concurrently calculates both **ISO 17636-1/2** ($f_{\min} = C \cdot d \cdot b^{2/3}$ or Formula 13 planar $f_{\min}^* = f_{\min}(b=t) \cdot C_i$) and **ASME Sec V Art 2 T-274.2** ($f_{\min} = d \cdot b / U_{g,\text{limit}}$).
  - Wires an accessible `<InfoTip>` directly on the $f_{\min}$ hero card opening an interactive dialog containing the dynamic values line, step-by-step arithmetic substitutions ($C \times d \times b^{2/3}$ and $d \times b / U_{g,\text{limit}}$), active Level 3 exceptions (%20 DW / %50 central reduction), and governing standard resolution.
  - Displays dual ISO & ASME metrics simultaneously in `.hero-sub` (`ISO: ... mm | ASME: ... mm • b = ... mm`) with the governing standard active badge (`ISO ✓` or `ASME ✓`).
  - Passes all 925 Python tests and 35 Playwright E2E tests.
- **DWSI Figure 14 ($f_{\min} > OD$) Validation per ISO 17636-1 / ISO 17636-2 Clause 7.6**:
  - Enforced normative check: In DWSI "Odak Yüzeyde / Source on Surface" (`fig14`, `fig14a`, `fig14b`), the source-to-object distance is bounded by the outer pipe diameter ($f \approx OD - t$). When dynamically calculated $f_{\min} > OD$, the source cannot physically or normatively be placed on the surface without violating geometric unsharpness ($U_g$) limits.
  - **Engine warnings**: Emits localized warning in [`engine.py`](file:///Users/macbook/Documents/Kodlama/Radiography/src/core/engine.py) advising that the figure is invalid and directing the operator to switch to Figure 13 / 13a / 13b (source outside the pipe at $f \ge f_{\min}$).
  - **Procedure check**: Registers structured `dwsi_figure` check in [`procedure_check.py`](file:///Users/macbook/Documents/Kodlama/Radiography/src/core/procedure_check.py) failing procedure compliance when $f_{\min} > OD$ and passing when $f_{\min} \le OD$.
  - Covered by unit tests in [`tests/test_procedure_check.py`](file:///Users/macbook/Documents/Kodlama/Radiography/tests/test_procedure_check.py) and [`tests/test_engine.py`](file:///Users/macbook/Documents/Kodlama/Radiography/tests/test_engine.py). Commit `60d8527`.
- **DWDI Film & Panel Size Coverage & Minimum Width Notification (ISO 17636-1/2 Clauses 7.1.6 & 7.1.7)**:
  - In DWDI (Figures 11 & 12: Elliptical and Superimposed), the exposure count ($N = 2$ or $N = 3$) is fixed by normative $t/D_e$ rules, but the film or detector panel must be physically large enough to project the full pipe diameter without cutoff.
  - Added [`calculate_dwdi_coverage`](file:///Users/macbook/Documents/Kodlama/Radiography/src/core/calculator.py) in `RTCalculator` computing geometric magnification $M = SFD / f$ (where $b = OD + \text{bgap}$, $f = SFD - b$), projected pipe diameter $W_{\text{proj}} = OD \cdot M$, and required minimum film/panel width $W_{\min} = W_{\text{proj}} + 10.0\text{ mm}$ (margin for wire IQI and lead identification markers), along with standard film orientation analysis (normal vs rotated).
  - Integrated in [`CalculationEngine`](file:///Users/macbook/Documents/Kodlama/Radiography/src/core/engine.py): computes `dwdi_coverage`, formats detailed step-by-step arithmetic (`dwdi_coverage_detail`), updates exposure provenance, and emits localized warning if entered film/panel dimensions do not cover $W_{\min}$.
  - Added structured `dwdi_coverage` check in [`ProcedureComplianceChecker`](file:///Users/macbook/Documents/Kodlama/Radiography/src/core/procedure_check.py).
  - Wired into Web [`HeroSummaryPanel.tsx`](file:///Users/macbook/Documents/Kodlama/Radiography/web/src/components/HeroSummaryPanel.tsx) with an accessible `<InfoTip>` modal on the "Gerekli Poz Sayısı" hero card and status badge (`Boyut Yetersiz ⚠` / `ISO ✓`).
  - Covered by unit tests in `tests/test_calculator.py`, `tests/test_engine.py`, and `tests/test_procedure_check.py`. Full test suite: 930 passed, 35 Playwright E2E passed.
- **Resizable 3-Column Layout & 40% 3D Column Default Width**:
  - Set default desktop layout to Left (Inputs) 28%, Middle (Outputs) 32%, Right (3D View) 40%, giving the 3D visualization and pipe projection scene prominent visual space.
  - Added custom hook [`useResizableColumns.ts`](file:///Users/macbook/Documents/Kodlama/Radiography/web/src/state/useResizableColumns.ts) with pointer event dragging (`onPointerDown`), safe boundary clamping (Col 1: 20%–45%, Col 2: 20%–48%, Col 3: 25%–60%), and `localStorage` persistence under `"radiography_col_widths_v1"`.
  - Added dual accessible separator handles (`.column-resizer` with `role="separator"`, `tabIndex={0}`, keyboard `ArrowLeft`/`ArrowRight`/`Shift`, `Enter`/`Space` reset, and double-click reset).
  - Added "Kolonları Sıfırla (%28 - %32 - %40)" button to the "Görünüm" (View) dropdown menu in [`App.tsx`](file:///Users/macbook/Documents/Kodlama/Radiography/web/src/App.tsx).
  - Added `ResizeObserver` in [`WeldSetup3D.tsx`](file:///Users/macbook/Documents/Kodlama/Radiography/web/src/components/WeldSetup3D.tsx) to automatically adapt logical canvas resolution to the expanded column width without pixelation or stretching.
  - Responsive breakpoints ($\le 1150\text{px}$ and $\le 860\text{px}$) cleanly hide resizers and switch to 2-column and 1-column layouts.
  - Verified with new Playwright E2E test [`resizable-columns.spec.ts`](file:///Users/macbook/Documents/Kodlama/Radiography/web/tests/e2e/resizable-columns.spec.ts), 0 `oxlint` errors, and clean TypeScript build.
- **Agent Skills & 6-Phase Lifecycle Orchestration (`c0d6c22`)**:
  - Integrated Addy Osmani's `agent-skills` suite across `.agents/`, `.opencode/`, and `~/.gemini/config/plugins/agent-skills/` alongside existing Ponytail and RT domain skills (`rt-research`, `rt-review`, `code-reviewer`, `security-auditor`, `test-engineer`, `web-performance-auditor`).
- **Web UI/UX Usability Iteration 2 & 3 (`04a45f8` + follow-up)**:
  1. **Recent Calculations History**: `useCalculationHistory.ts` + `CalculationHistoryModal` in `Modals.tsx` keeping a 5-entry debounced, deduplicated, schema-validated `localStorage` stack with 1-click restore and clear (`⏱️ Geçmiş (N)` / `Alt+H`).
  2. **Outdoor High-Contrast Mode**: `[data-theme="outdoor"]` WCAG AAA sunlight mode (`#ffffff` bg, `#000000` text, `2px` black borders, high-contrast 3D canvas gradient) cycling in the header (`🌙 / ☀️ / 🕶️`).
  3. **Keyboard Quick-Jump (`Alt+1..4`, `Alt+H`)**: Cross-platform `event.code` shortcuts auto-expanding `<details>` groups (`#section-geometry`, `#section-radiation`, `#section-standards`, `#section-applied`), scrolling into view, and focusing the first control.
  4. **Shareable Setup URL (`🔗 Paylaş / Share`)**: `buildShareUrl` and `parseUrlSetup` in `usePersistedAppState.ts` encoding non-default `FormState` deltas into `?setup=...` with strict `DEFAULT_FORM` key/type allowlisting and automatic URL cleanup on boot.
  5. **NDT Terminology Fixes**: Fixed API 1104 Clause 9.3.6 `defect_ic` translation ("Internal Concavity (IC)" / "İç Çöküntü / Kök Çöküntüsü (IC)") and ISO 17636-2 Table 2 footnote label in `src/core/translation.py`.
  6. Covered by 5 E2E tests in [`usability-iteration-2.spec.ts`](file:///Users/macbook/Documents/Kodlama/Radiography/web/tests/e2e/usability-iteration-2.spec.ts).

## Pending / next

- [ ] Decide whether to record the web-only scope in `AGENTS.md`.

## Notes & risks

- Web copies `src/core` into `web/public/python/` (gitignored); sync is automatic
  (`npm run sync` in `predev`/`prebuild`). Mobile has **no copy** — `buildozer.spec`
  packages `src/core/*.py` directly, so it cannot drift (desktop/mobile now frozen).
- Agent & skill configuration (`AGENTS.md`, `GEMINI.md`, `.agents/`, `.opencode/`) committed in `ffb76f2` and `c0d6c22`.
- `docs/godclass-plan.md` dated some entries 2026-10-16; actual session commits are
  2026-10-17 / 2026-10-18.
