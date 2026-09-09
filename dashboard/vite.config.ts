import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  // duckdb-wasm ships pre-bundled workers and wasm; let Vite serve them as assets.
  optimizeDeps: { exclude: ["@duckdb/duckdb-wasm"] },
  build: { target: "es2022", chunkSizeWarningLimit: 1500 },
});
