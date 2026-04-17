import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],

  // DuckDB-WASM requires SharedArrayBuffer which is gated behind COOP/COEP.
  // Set these headers in the dev server so the app behaves the same locally
  // as on Cloudflare Pages (where they are set via _headers file).
  server: {
    headers: {
      "Cross-Origin-Opener-Policy": "same-origin",
      "Cross-Origin-Embedder-Policy": "credentialless",
    },
  },

  // Tell Vite not to try to bundle the DuckDB WASM worker files — they must
  // be served as separate files so the browser can instantiate them.
  optimizeDeps: {
    exclude: ["@duckdb/duckdb-wasm"],
  },

  // Needed so Vite does not inline WASM files as base64 in the bundle,
  // which would break the SharedArrayBuffer threading model.
  build: {
    target: "es2020",
    rollupOptions: {
      // Keep WASM assets as separate files in the output
      output: {
        assetFileNames: "assets/[name]-[hash][extname]",
      },
    },
  },
});
