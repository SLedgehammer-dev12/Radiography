/// <reference lib="webworker" />

import { loadPyodide, type PyodideInterface } from "pyodide";

type Request = { id: number; action: string; payload?: unknown };

let pyodide: PyodideInterface | null = null;
let bridgeHandle: ((request: string) => string) | null = null;

function post(message: unknown) {
  (self as unknown as Worker).postMessage(message);
}

async function boot() {
  post({ type: "status", stage: "loading-pyodide" });
  pyodide = await loadPyodide({
    indexURL: new URL("/pyodide/", self.location.origin).href,
  });

  post({ type: "status", stage: "loading-core" });
  const files = (await (await fetch("/python/files.json")).json()) as string[];
  pyodide.FS.mkdirTree("/python");
  for (const file of files) {
    const response = await fetch(`/python/${file}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch /python/${file}: ${response.status}`);
    }
    const text = await response.text();
    const parts = file.split("/");
    if (parts.length > 1) {
      pyodide.FS.mkdirTree(`/python/${parts.slice(0, -1).join("/")}`);
    }
    pyodide.FS.writeFile(`/python/${file}`, text);
  }

  const binaries: [string, string][] = [
    ["/data/exposure_chart_dataset.json", "/python/exposure_chart_dataset.json"],
    ["/assets/fonts/NotoSans-Regular.ttf", "/python/src/mobile/assets/fonts/NotoSans-Regular.ttf"],
    ["/assets/fonts/NotoSans-Bold.ttf", "/python/src/mobile/assets/fonts/NotoSans-Bold.ttf"],
    ["/assets/fonts/NotoSans-Italic.ttf", "/python/src/mobile/assets/fonts/NotoSans-Italic.ttf"],
  ];
  for (const [source, destination] of binaries) {
    const response = await fetch(source);
    if (!response.ok) continue;
    const parts = destination.split("/");
    pyodide.FS.mkdirTree(parts.slice(0, -1).join("/"));
    pyodide.FS.writeFile(destination, new Uint8Array(await response.arrayBuffer()));
  }

  pyodide.runPython(`
import sys
if "/python" not in sys.path:
    sys.path.insert(0, "/python")
from bridge import handle as _bridge_handle
`);
  bridgeHandle = pyodide.globals.get("_bridge_handle") as (request: string) => string;

  const ping = JSON.parse(bridgeHandle(JSON.stringify({ action: "ping" })));
  post({ type: "ready", version: ping.version });
}

const ready = boot().catch((error) => {
  post({ type: "boot-error", error: String(error) });
  throw error;
});

self.onmessage = async (event: MessageEvent<Request>) => {
  const request = event.data;
  try {
    await ready;
    if (request.action === "pdf:prepare") {
      // Lazy-load ReportLab/qrcode only when the user exports a PDF so the
      // initial boot stays fast. Wheels are vendored locally by
      // scripts/sync-assets.mjs so this also works offline.
      await pyodide!.loadPackage(["micropip", "pillow"]);
      const wheels = (await (await fetch("/pyodide/wheels.json")).json()) as string[];
      const micropip = pyodide!.pyimport("micropip") as {
        install: (
          packages: string[],
          keepGoing?: boolean,
          deps?: boolean,
        ) => Promise<void>;
      };
      const localWheels = wheels
        .filter((name) => !name.startsWith("micropip") && !name.startsWith("pillow"))
        .map((name) => `/pyodide/${name}`);
      if (localWheels.length) {
        await micropip.install(localWheels, false, false);
      }
      post({ id: request.id, ok: true, data: { prepared: true } });
      return;
    }
    if (!bridgeHandle) throw new Error("Bridge not initialised");
    const response = bridgeHandle(
      JSON.stringify({ action: request.action, payload: request.payload ?? {} }),
    );
    post({ id: request.id, ok: true, data: JSON.parse(response) });
  } catch (error) {
    post({ id: request.id, ok: false, error: String(error) });
  }
};

export {};
