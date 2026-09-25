import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
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
