# Progress Log

> Working log of completed and pending work. Updated per session.
> Last updated: 2026-10-17 (HEAD at time of writing: `ffb76f2`).

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
python3 -m pytest -q                    # 915 passed, 6 skipped, 849 subtests
cd web && npx tsc -b                    # clean
cd web && npx oxlint src/               # 0 warnings, 0 errors
cd web && npx playwright test           # 33 passed (21 + 3 mobile + 9 feedback)
```

## Pending / next

- [x] **J: remaining web panels** — **STOPPED by decision (2026-10-17).** The
      remaining Inputs Group has 38 external deps; a component would need 38 props
      with no cohesion gain. Done: Compliance, Warnings, Report info, Sketch tabs,
      HeroSummaryPanel. App.tsx stands at 1883 lines (−40%). Do not resume without
      a new approach (semantic sub-panels or a form context). See `docs/godclass-plan.md` step J.
- [x] **Web feature development (interaction, feedback, error-state & accessibility pass)** —
      Done: toast variants + auto-dismiss; sticky header with Reset/PDF; header
      progress bar (`busy || pdfBusy`); outputs & compliance loading/error state polish;
      keyboard shortcuts + modal/busy guards; modal `role="dialog"` + `Escape`-to-close +
      keyboard `InfoTip`; inch-mode `LengthSliderField` bounds fix; `0` oxlint warnings.
- [ ] Decide whether to record the web-only scope in `AGENTS.md`.

## Notes & risks

- Web copies `src/core` into `web/public/python/` (gitignored); sync is automatic
  (`npm run sync` in `predev`/`prebuild`). Mobile has **no copy** — `buildozer.spec`
  packages `src/core/*.py` directly, so it cannot drift (desktop/mobile now frozen).
- Agent & skill configuration (`GEMINI.md`, `.agents/agents/`, `.opencode/agents/`,
  `.opencode/skills/`, `.opencode/command/repo-indexer.md`) committed in `ffb76f2`.
- `docs/godclass-plan.md` dated some entries 2026-10-16; actual session commits are
  2026-10-17.
