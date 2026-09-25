# Radiography Web

Browser version of the Radiography RT calculator. The Python core
(`../src/core`) runs in the browser via [Pyodide](https://pyodide.org)
(WebAssembly), so the desktop, mobile and web front-ends share exactly the
same calculation engine.

## Development

```bash
npm install          # also downloads the Pyodide runtime and PDF wheels
npm run dev          # http://localhost:5173 (predev syncs the Python core)
```

`scripts/sync-assets.mjs` copies into `public/` (git-ignored):

- the Pyodide runtime from `node_modules/pyodide`,
- the Python core (`../src/core`, including `src/core/data/*.json`),
- `python/bridge.py` (JSON RPC used by the web worker),
- `exposure_chart_dataset.json` and the bundled Noto Sans fonts,
- the vendored PDF wheels (ReportLab, qrcode, charset-normalizer).

## Tests

```bash
npm run build
npx playwright test          # 15 E2E tests (parity, PDF, sketches, launcher UI)
python3 ../tests/test_web_parity_fixture.py   # fixture <-> engine lock
```

The 147-scenario parity fixture is regenerated from the repository root with:

```bash
python3 scripts/export-parity-fixtures.py
```

## Production build

```bash
npm run build        # typecheck + bundle into dist/
npm run serve        # local static server (opens the browser)
npm run package:web  # versioned zips with the Python launcher scripts
```

## Single-file launchers

```bash
python3 launcher/package.py --onefile          # host platform executable
python3 launcher/package.py --onefile --dmg    # macOS .app + .dmg
```

- Windows: `Radiography-Web-<ver>-Windows-x64.exe` (icon + version info)
- macOS: `Radiography-Web-<ver>-macOS.dmg` containing the iconed
  `Radiography Web <ver>.app`

Double-click starts a local server on `127.0.0.1:8765` (fallback to a free
port), opens the default browser and shows a small control window with
"Tarayıcıda Aç" / "Kapat". Launching again while it runs just re-opens the
browser (`/healthz` marker).
