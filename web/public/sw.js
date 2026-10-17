/* Radiography offline service worker.
 * Pre-caches the app shell, the Pyodide runtime, the Python core sources and
 * the PDF wheels so the whole tool works offline after the first visit.
 *
 * All paths are derived from the registration scope, so the same worker works
 * at the site root (local launcher) and under a sub-path (GitHub Pages).
 */

const BASE = new URL(self.registration.scope).pathname; // "/" or "/Radiography/"
const CACHE = "radiography-v2.0.4";

const CORE_ASSETS = [
  `${BASE}index.html`,
  `${BASE}manifest.webmanifest`,
  `${BASE}icon.svg`,
  `${BASE}pyodide/pyodide.mjs`,
  `${BASE}pyodide/pyodide.asm.mjs`,
  `${BASE}pyodide/pyodide.asm.wasm`,
  `${BASE}pyodide/python_stdlib.zip`,
  `${BASE}pyodide/pyodide-lock.json`,
  `${BASE}python/files.json`,
  `${BASE}python/bridge.py`,
  `${BASE}data/exposure_chart_dataset.json`,
  `${BASE}assets/fonts/NotoSans-Regular.ttf`,
  `${BASE}assets/fonts/NotoSans-Bold.ttf`,
  `${BASE}assets/fonts/NotoSans-Italic.ttf`,
];

async function precache() {
  const cache = await caches.open(CACHE);
  await cache.addAll(CORE_ASSETS).catch(() => undefined);

  for (const manifest of [`${BASE}python/files.json`, `${BASE}pyodide/wheels.json`]) {
    try {
      const response = await fetch(manifest);
      if (!response.ok) continue;
      const entries = await response.json();
      const base = manifest.includes("wheels") ? `${BASE}pyodide/` : `${BASE}python/`;
      await cache.addAll(entries.map((name) => `${base}${name}`));
    } catch {
      /* optional assets */
    }
  }
}

self.addEventListener("install", (event) => {
  event.waitUntil(precache().then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET" || new URL(request.url).origin !== self.location.origin) {
    return;
  }

  const url = new URL(request.url);
  const isNavigation =
    request.mode === "navigate" ||
    url.pathname === BASE ||
    url.pathname.endsWith("/index.html");

  // Navigation or unhashed Python/data assets: network-first so freshly updated
  // code and calculation logic are always served immediately when online.
  const isDynamicAsset =
    isNavigation ||
    url.pathname.includes("/python/") ||
    url.pathname.endsWith("/files.json") ||
    url.pathname.endsWith("/bridge.py");

  if (isDynamicAsset) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response.ok) {
            const copy = response.clone();
            caches.open(CACHE).then((cache) => cache.put(request, copy));
          }
          return response;
        })
        .catch(() =>
          caches
            .match(request)
            .then((cached) => cached || (isNavigation ? caches.match(`${BASE}index.html`) : undefined)),
        ),
    );
    return;
  }

  // Hashed/immutable assets: cache-first.
  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) return cached;
      return fetch(request)
        .then((response) => {
          if (response.ok && response.type === "basic") {
            const copy = response.clone();
            caches.open(CACHE).then((cache) => cache.put(request, copy));
          }
          return response;
        })
        .catch(() => caches.match(`${BASE}index.html`));
    }),
  );
});
