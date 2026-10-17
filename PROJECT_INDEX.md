# Radiography — Repository Index

> **Status**: Current (Indexed at commit `0580273` | Version `2.0.3` | 2026-10-16)
> **Domain**: Industrial Radiographic Testing (NDT RT) exposure calculator & report generator
> **Freshness Policy**: Stale after 7 days or 15 new commits.

## 1. Architectural Overview

Single pure-Python calculation core (`src/core/`) shared by three targets: Desktop PyQt6, Web React+Pyodide, Mobile KivyMD. `CalculationEngine.calculate()` orchestrates geometry → exposure → IQI → warnings; `report.py` generates the PDF. No target duplicates physics.

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
├── src/ui/                  # [Desktop UI] PyQt6 (main_window 3297 lines + panels/)
├── src/mobile/              # [Mobile] KivyMD wizard (24 files incl. .kv)
├── src/android/             # [Packaging] p4a manifest hook
├── web/src/                 # [Web] React 19 (App.tsx 3146 lines, main.tsx, pyodide/)
├── web/python/bridge.py     # [Bridge] Pyodide JSON-RPC -> CalculationEngine
├── web/scripts/sync-assets.mjs  # [Tool] src/core -> web/public/python sync
├── tests/                   # [Tests] 37 files, 919 pytest cases
├── web/tests/               # [Tests] 5 Playwright E2E files
├── tools/                   # [Tools] Annex A digitizer
└── docs/                    # [Data] ASME B36 pipe catalog JSON
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
| `src/ui/main_window` | 18 | 0.95 High | Desktop god-class (3297 lines) |
| `web/src/App.tsx` | 12 | 0.92 High | Web god-class (3146 lines) |
| `src/core/engine` | 9 | 0.82 Med | Central facade |
| `src/mobile/lib/app_state` | 9 | 0.69 Med | Mobile bridge |
| `src/core/calculator` | 2 | 0.50 Low | Stable physics |
| `src/core/exposure_charts` | 0 | 0.00 Low | Leaf data |
| `src/core/translation` | 0 | 0.00 Low | Leaf i18n |

External: Desktop `PyQt6, reportlab, matplotlib, numpy, Pillow, qrcode`; Web `react 19, pyodide 314, vite 8, playwright`; Mobile `kivy 2.3.1, kivymd`.

## 5. Change Hotspots (117 commits, 1 author)

Top churn: `build.yml` 42, `CHANGELOG.md` 32, `main_window.py` 30, `version.py` 28, `buildozer.spec` 28, `pyproject.toml` 27, `calculator.py` 20. 58 commits contain `fix`. Bus factor = 1 (`omer.erbas`, 117/117). Co-change cluster: `calculator.py` <-> `main_window.py`.

## 6. Risks & Debt

1. **God-classes**: `main_window.py` + `App.tsx` carry UI+state+events; any UI change risks regression. Test shield is thin (1 pytest file vs 3297 lines; smoke E2E vs 3146 lines).
2. **Sync drift (web only)**: web copies core into `web/public/python/` (gitignored); sync is automated (`sync-assets.mjs` + predev/prebuild, diff clean today). Mobile has no copy — `buildozer.spec` packages `src/core/*.py` directly at build time, so it cannot drift.
3. **Version fallback literals**: 4 manifests agree on `2.0.3`, but `App.tsx` keeps 4 hardcoded `"2.0.3"` fallbacks (`pyClient.version ?? "2.0.3"`) — benign display-only drift on bump. Low.
4. **Open Low items**: `_show_about` RichText without `html.escape()` (`main_window.py:2775-2786`); no `warn_dda_high_dose_rate` advisory for thin-section/high-mA saturation.
5. **Closed since TODO, pending doc update**: AbortController (CR-1.2), semver regex (CR-1.4), µGy/mGy units (CR-1.7), `noopener/noreferrer` — all verified in code.

## 7. Context Tiers (for agents)

- **Tier 1 (~450t)**: §1 + §3 — routing, simple Q&A.
- **Tier 2 (~1200t)**: §1–§4 + §6 — feature work, targeted fixes.
- **Tier 3 (~2400t)**: full doc — refactor, audit, release.
