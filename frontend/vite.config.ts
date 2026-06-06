/// <reference types="vitest" />
import * as path from "path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The graph bundle is built into the dbdocs SPA's asset tree and committed, so
// `dbdocs generate` ships it without needing Node. A single `index.js` +
// `index.css` keeps the SPA's <script>/<link> wiring trivial.
export default defineConfig({
  plugins: [react()],
  base: "./",
  // The IIFE lib build inlines React; force the production build so React's
  // `process.env.NODE_ENV` references are replaced (no `process` at runtime).
  define: {
    "process.env.NODE_ENV": JSON.stringify("production"),
    "process.env": "{}",
  },
  build: {
    outDir: path.resolve(__dirname, "../dbdocs/site/bundle/assets/graph"),
    emptyOutDir: true,
    sourcemap: false,
    lib: {
      entry: path.resolve(__dirname, "src/main.tsx"),
      formats: ["iife"],
      name: "dbdocsGraph",
      fileName: () => "index.js",
    },
    rollupOptions: {
      output: {
        assetFileNames: "index.[ext]",
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    include: ["tests/**/*.test.{ts,tsx}"],
  },
});
