# Radiography — Repository Index

> **Status**: Current (Indexed at commit `8cc850a` | Version `2.0.3` | 2026-10-17)
> **Domain**: Industrial Radiographic Testing (NDT RT) exposure calculator & report generator
> **Freshness Policy**: Stale after 7 days or 15 new commits.

## 1. Architectural Overview

Single pure-Python calculation core (`src/core/`) shared by three targets: Desktop PyQt6 (frozen), Web React+Pyodide (active front-end), Mobile KivyMD (frozen). `CalculationEngine.calculate()` orchestrates geometry → exposure → IQI → warnings; `report.py` generates the PDF. No target duplicates physics.

## 2. Directory Taxonomy

```text
Radiography/
├── main.py                  # [Entry] Desktop bootstrap (crash-logger + QApplication)
├── pyproject.toml           # [Manifest] Python build, version 2.0.3
├── buildozer.spec           # [Manifest] Android packaging, version 2.0.3
├── Radiography.spec         # [Manifest] PyInstaller bundle
├── src/core/                # [Core] 15x .py: engine, calculator, exposure_charts,
│                            #   annex_a, api1104, asme_b31_3, asme_b36, asme_viii,
│                            #   iso5817, procedure_check, report, translation, updater, version
├── src/ui/                  # [Desktop UI] PyQt6 (main_window 2114 lines + 8 panels/)
├── src/mobile/              # [Mobile] KivyMD wizard (24 files incl. .kv)
├── src/android/             # [Packaging] p4a manifest hook
├── web/src/                 # [Web] React 19 (App.tsx 1957 lines, components/, state/, lib/, pyodide/)
├── web/python/bridge.py     # [Bridge] Pyodide JSON-RPC -> CalculationEngine
├── web/scripts/sync-assets.mjs  # [Tool] src/core -> web/public/python sync
├── tests/                   # [Tests] 37 files, 930 pytest cases (924 passed, 6 skipped)
├── web/tests/               # [Tests] 6 Playwright E2E files (33 tests)
├── tools/                   # [Tools] Annex A digitizer
└── docs/                    # [Data/Docs] ASME B36 pipe catalog JSON, PROGRESS.md, godclass-plan.md
```

## 3. Entry Points

| Target | File | Bootstrap |
| :--- | :--- | :--- |
| Desktop | `main.py::main()` | crash-logger, `QApplication`, `MainWindow` |
| Web | `web/src/main.tsx` | React root, Pyodide worker, `bridge.py` |
| Mobile | `src/mobile/main.py::RadiographyApp` | KivyMD shell, `AppState`, 5 screens |
| Launcher | `web/launcher/serve.py` | local HTTP server, `/healthz` mutex |

Core facade: `src/core/engine.py::CalculationEngine.calculate()` — single pipeline all UIs render from (`{calculated, warnings, display, values}`).

## 4. Dependency & Coupling (top)

| Module | Fan-Out | Instability | Role |
| :--- | :---: | :---: | :--- |
| `src/ui/main_window` | 18 | 0.95 High | Desktop shell (2114 lines + 8 mixins in `src/ui/panels/`) |
| `web/src/App.tsx` | 17 | 0.94 High | Web orchestrator (1883 lines + `components/*`, `state/*`) |
| `src/core/engine` | 9 | 0.82 Med | Central facade |
| `src/mobile/lib/app_state` | 9 | 0.69 Med | Mobile bridge |
| `src/core/calculator` | 2 | 0.50 Low | Stable physics |
| `src/core/exposure_charts` | 0 | 0.00 Low | Leaf data |
| `src/core/translation` | 0 | 0.00 Low | Leaf i18n |

External: Desktop `PyQt6, reportlab, matplotlib, numpy, Pillow, qrcode`; Web `react 19, pyodide 314, vite 8, playwright`; Mobile `kivy 2.3.1, kivymd`.

## 5. Change Hotspots (139 commits, 1 author)

Top churn: `build.yml` 42, `CHANGELOG.md` 32, `main_window.py` 34, `version.py` 28, `buildozer.spec` 28, `pyproject.toml` 27, `calculator.py` 21, `App.tsx` 21. 61 commits contain `fix`. Bus factor = 1 (`omer.erbas`, 139/139). Co-change cluster: `calculator.py` <-> `main_window.py` / `App.tsx`.

## 6. Risks & Debt

1. **Large UI orchestrators**: `main_window.py` (3298 → 2114 lines, −36%) and `App.tsx` (3149 → 1883 lines, −40%) were decomposed via `src/ui/panels/*` and `web/src/components/*` + `web/src/state/*`. Inputs group in `App.tsx` (38 deps) intentionally kept inline per `docs/godclass-plan.md`.
2. **Sync drift (web only)**: web copies core into `web/public/python/` (gitignored); sync is automated (`sync-assets.mjs` + predev/prebuild, diff clean). Mobile has no copy — `buildozer.spec` packages `src/core/*.py` directly at build time.
3. **Version bump (5 spots)**: `src/core/version.py`, `pyproject.toml`, `buildozer.spec`, `web/package.json`, and `FALLBACK_VERSION` in `web/src/components/Modals.tsx:7` (`RELEASE.md`).
4. **Shortcut debt (`ponytail-debt`)**: 1 marker in production code (`src/core/calculator.py:1584`, `shortcut: t unknown -> conservative N, pass t to upgrade`).
5. **Closed review items**: CR-1.1..1.7 in `TODO_code-reviewer.md` all verified and closed in code and tests.

## 7. Context Tiers (for agents)

- **Tier 1 (~450t)**: §1 + §3 — routing, simple Q&A.
- **Tier 2 (~1200t)**: §1–§4 + §6 — feature work, targeted fixes.
- **Tier 3 (~2400t)**: full doc — refactor, audit, release.
