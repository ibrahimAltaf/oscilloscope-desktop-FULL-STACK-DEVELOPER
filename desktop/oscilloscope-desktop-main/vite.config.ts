import path from "node:path";
import { copyFileSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import electron from "vite-plugin-electron";
import renderer from "vite-plugin-electron-renderer";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/** Copy CommonJS preload (not bundled as ESM) into dist-electron for Electron to load. */
function copyPreloadCjs(): void {
  const outDir = path.join(__dirname, "dist-electron");
  mkdirSync(outDir, { recursive: true });
  copyFileSync(
    path.join(__dirname, "electron", "preload.js"),
    path.join(outDir, "preload.js"),
  );
}

export default defineConfig({
  plugins: [
    {
      name: "preload-cjs-copy",
      buildStart() {
        copyPreloadCjs();
      },
      configureServer() {
        copyPreloadCjs();
      },
    },
    react(),
    electron([
      {
        entry: "electron/main.ts",
        vite: {
          build: {
            outDir: "dist-electron",
            rollupOptions: { external: ["electron"] },
          },
        },
      },
    ]),
    renderer(),
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
});
