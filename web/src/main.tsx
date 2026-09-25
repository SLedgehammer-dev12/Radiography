import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App.tsx";
import "./index.css";
import { pyClient } from "./pyodide/client";

if (import.meta.env.DEV) {
  // Test hook used by the Playwright parity harness.
  (window as unknown as Record<string, unknown>).__radiography = {
    request: (action: string, payload: Record<string, unknown> = {}) =>
      pyClient.request(action, payload),
  };
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

if (import.meta.env.PROD && "serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register("/sw.js", { updateViaCache: "none" })
      .then((registration) => registration.update().catch(() => undefined))
      .catch(() => undefined);
  });
  // Reload once when an updated service worker takes control so users never
  // stay on a stale cached build.
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    window.location.reload();
  });
}
