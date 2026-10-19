import { readFileSync } from "node:fs";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const pkg = JSON.parse(
  readFileSync(new URL("./package.json", import.meta.url), "utf-8"),
);

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
  },
  worker: {
    format: "es",
  },
  optimizeDeps: {
    exclude: ["pyodide"],
  },
  server: {
    fs: {
      // The Python sources live outside web/ and are copied into public/ by
      // scripts/sync-assets.mjs before the dev server starts.
      allow: [".."],
    },
  },
});
