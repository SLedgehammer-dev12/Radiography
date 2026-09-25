/* Radiography offline service worker.
 * Pre-caches the app shell, the Pyodide runtime, the Python core sources and
 * the PDF wheels so the whole tool works offline after the first visit.
 */

const CACHE = "radiography-v2";

const CORE_ASSETS = [
  "/",
  "/index.html",
  "/manifest.webmanifest",
  "/icon.svg",
  "/pyodide/pyodide.mjs",
  "/pyodide/pyodide.asm.mjs",
  "/pyodide/pyodide.asm.wasm",
  "/pyodide/python_stdlib.zip",
  "/pyodide/pyodide-lock.json",
  "/python/files.json",
  "/python/bridge.py",
  "/data/exposure_chart_dataset.json",
  "/assets/fonts/NotoSans-Regular.ttf",
  "/assets/fonts/NotoSans-Bold.ttf",
  "/assets/fonts/NotoSans-Italic.ttf",
];

async function precache() {
  const cache = await caches.open(CACHE);
  await cache.addAll(CORE_ASSETS).catch(() => undefined);

  for (const manifest of ["/python/files.json", "/pyodide/wheels.json"]) {
    try {
      const response = await fetch(manifest);
      if (!response.ok) continue;
      const entries = await response.json();
      const base = manifest.includes("wheels") ? "/pyodide/" : "/python/";
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
    request.mode === "navigate" || url.pathname === "/" || url.pathname.endsWith("/index.html");

  // Navigation: network-first so a freshly built app is always served when
  // online; the cache is only a fallback for offline use.
  if (isNavigation) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put(request, copy));
          return response;
        })
        .catch(() => caches.match(request).then((cached) => cached || caches.match("/index.html"))),
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
        .catch(() => caches.match("/index.html"));
    }),
  );
});
