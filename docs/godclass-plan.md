# God-class bölme planı

## src/ui/main_window.py (bölme öncesi 3298 satır)
Zaten mixin tabanlı parçalama var: InputPanelMixin, DefectPanelMixin,
WarningsPanelMixin, CompliancePanelMixin. Kalan god-class yükü şu bloklarda:

  1. __init__ + init_ui (47-856) — widget wiring, ~800 satır
  2. retranslate_ui (1371-1573) — 200 satır i18n
  3. get_form_values (1738-1839) — 100 satır form extraction
  4. _render_calculation (2280-2333) — 50 satır output binding
  5. update_calculations (2357-2371) — pipeline orchestrator
  6. export_pdf_report — 260 satır PDF akışı
  7. _setup_menu_bar (2723-2789) — 66 satır

Bölme sırası (risk en düşükten en yükseğe):
  A. [x] export_pdf_report -> ReportExportMixin (src/ui/panels/report_panel.py) — 2026-10-16, 3298→3037 satır, 915 test yeşil
  B. [ ] retranslate_ui -> TranslationMixin (stateless-ish, sadece widget text)
  C. [ ] get_form_values + _collect_engine_form -> FormStateMixin
  D. [ ] __init__/init_ui son — en riskli, test blast radius'u en geniş

## web/src/App.tsx (3146 satır)
Tek fonksiyonel component, hook'lar inline. Bölmek için:
  - useEngine already extracted (state/useEngine.ts) — iyi örnek
  - Adaylar: formToDesktopState/presets (state/presets.ts — zaten ayrı),
    modal'lar (AboutModal, UpdateModal, Lvl3Dialog, DecayDialog — zaten ayrı fonksiyonlar),
    defect akışı, PDF export (svgToPngBase64, downloadBase64 — ayrı fonksiyonlar)
  - Kalan god-class yükü: useState'lerin ~40'u tek App içinde + useEffect x10.
  Öneri: useAppForm, useReportInfo, useDefectState custom hook'larına ayırmak.

## Kural
Her bölme adımı tek commit, test suite yeşil kalır, davranış değişmez.
Bus-factor-1 için: her bölme sonrası CHANGELOG'a not düşmek zorunlu.
