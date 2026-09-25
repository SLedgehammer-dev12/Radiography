// Copies the runtime assets needed by the web build into web/public/:
//  - the Pyodide runtime (from node_modules)
//  - the Python core sources (single source of truth: ../src/core)
//  - the Python bridge module (web/python/bridge.py)
//  - exposure chart data and bundled Noto fonts
// Run automatically by `npm run dev` / `npm run build` (predev/prebuild).

import {
  cpSync,
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  rmSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const webRoot = dirname(dirname(fileURLToPath(import.meta.url)));
const repoRoot = dirname(webRoot);
const publicDir = join(webRoot, "public");

const PYODIDE_FILES = [
  "pyodide.asm.wasm",
  "pyodide.asm.mjs",
  "pyodide.mjs",
  "pyodide-lock.json",
  "python_stdlib.zip",
];

function clean(path) {
  if (existsSync(path)) rmSync(path, { recursive: true, force: true });
}

function copyPyodideRuntime() {
  const src = join(webRoot, "node_modules", "pyodide");
  if (!existsSync(src)) {
    console.error("[sync-assets] pyodide is not installed; run npm install first.");
    process.exit(1);
  }
  const dst = join(publicDir, "pyodide");
  mkdirSync(dst, { recursive: true });
  for (const file of PYODIDE_FILES) {
    cpSync(join(src, file), join(dst, file));
  }
}

async function download(url, destination) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} for ${url}`);
  }
  const buffer = Buffer.from(await response.arrayBuffer());
  writeFileSync(destination, buffer);
  return buffer.length;
}

function pyodideLock() {
  return JSON.parse(
    readFileSync(join(webRoot, "node_modules", "pyodide", "pyodide-lock.json"), "utf-8"),
  );
}

async function pypiWheelUrl(name, version) {
  const spec = version ? `${name}/${version}` : `${name}`;
  const response = await fetch(`https://pypi.org/pypi/${spec}/json`);
  if (!response.ok) throw new Error(`PyPI ${spec}: HTTP ${response.status}`);
  const data = await response.json();
  const files = data.urls ?? [];
  const wheel =
    files.find((file) => file.filename.endsWith("-py3-none-any.whl")) ??
    files.find((file) => file.filename.endsWith(".whl"));
  if (!wheel) throw new Error(`No wheel found for ${spec}`);
  return wheel.url;
}

// Vendors the wheels needed for PDF export so it works offline:
// micropip + Pillow come from the Pyodide distribution, while ReportLab,
// qrcode and charset-normalizer are pure-Python wheels from PyPI.
async function vendorPdfPackages() {
  const dst = join(publicDir, "pyodide");
  const lock = pyodideLock();
  const version = JSON.parse(
    readFileSync(join(webRoot, "package.json"), "utf-8"),
  ).dependencies.pyodide.replace(/^[^0-9]*/, "");
  const cdn = `https://cdn.jsdelivr.net/pyodide/v${version}/full`;

  const vendored = [];
  for (const name of ["micropip", "pillow"]) {
    const entry = lock.packages[name];
    if (!entry) continue;
    const destination = join(dst, entry.file_name);
    if (!existsSync(destination)) {
      try {
        const size = await download(`${cdn}/${entry.file_name}`, destination);
        console.log(`[sync-assets] vendored ${entry.file_name} (${size} bytes)`);
      } catch (error) {
        console.warn(`[sync-assets] could not vendor ${entry.file_name}: ${error}`);
        continue;
      }
    }
    vendored.push(entry.file_name);
  }

  for (const [name, version_] of [
    ["reportlab", null],
    ["qrcode", null],
    ["charset-normalizer", null],
  ]) {
    try {
      const url = await pypiWheelUrl(name, version_);
      const filename = decodeURIComponent(url.split("/").pop());
      const destination = join(dst, filename);
      if (!existsSync(destination)) {
        const size = await download(url, destination);
        console.log(`[sync-assets] vendored ${filename} (${size} bytes)`);
      }
      vendored.push(filename);
    } catch (error) {
      console.warn(`[sync-assets] could not vendor ${name}: ${error}`);
    }
  }

  writeFileSync(join(dst, "wheels.json"), JSON.stringify(vendored), "utf-8");
}

function collectPythonFiles() {
  const pythonDir = join(publicDir, "python");
  clean(pythonDir);
  const files = [];

  const walk = (srcDir, dstDir) => {
    mkdirSync(dstDir, { recursive: true });
    for (const entry of readdirSync(srcDir)) {
      if (entry === "__pycache__") continue;
      const src = join(srcDir, entry);
      const dst = join(dstDir, entry);
      if (statSync(src).isDirectory()) {
        walk(src, dst);
      } else if (entry.endsWith(".py") || entry.endsWith(".json")) {
        // .json: bundled core data (e.g. src/core/data/annex_a_*.json)
        cpSync(src, dst);
        files.push(relative(pythonDir, dst).split("\\").join("/"));
      }
    }
  };

  walk(join(repoRoot, "src", "core"), join(pythonDir, "src", "core"));
  cpSync(join(repoRoot, "src", "__init__.py"), join(pythonDir, "src", "__init__.py"));
  files.push("src/__init__.py");

  cpSync(join(webRoot, "python", "bridge.py"), join(pythonDir, "bridge.py"));
  files.push("bridge.py");

  writeFileSync(join(pythonDir, "files.json"), JSON.stringify(files), "utf-8");
}

function copyDataAndFonts() {
  const dataDir = join(publicDir, "data");
  mkdirSync(dataDir, { recursive: true });
  const chart = join(repoRoot, "exposure_chart_dataset.json");
  if (existsSync(chart)) cpSync(chart, join(dataDir, "exposure_chart_dataset.json"));

  const fontsDir = join(publicDir, "assets", "fonts");
  mkdirSync(fontsDir, { recursive: true });
  const srcFonts = join(repoRoot, "src", "mobile", "assets", "fonts");
  if (existsSync(srcFonts)) {
    for (const font of readdirSync(srcFonts)) {
      if (font.endsWith(".ttf")) cpSync(join(srcFonts, font), join(fontsDir, font));
    }
  }
}

copyPyodideRuntime();
collectPythonFiles();
copyDataAndFonts();
await vendorPdfPackages();
console.log("[sync-assets] pyodide runtime, Python core and data copied to public/");
