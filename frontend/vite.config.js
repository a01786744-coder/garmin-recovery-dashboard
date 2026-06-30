import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { readFileSync } from "fs";
import { fileURLToPath } from "url";

// The app version lives in the root package.json; expose it (and the repo) to the
// client so the update notifier can compare against the latest GitHub release.
const pkg = JSON.parse(readFileSync(fileURLToPath(new URL("../package.json", import.meta.url)), "utf-8"));

export default defineConfig({
  plugins: [react()],
  base: "./",
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
    __REPO__: JSON.stringify("a01786744-coder/garmin-recovery-dashboard"),
  },
  server: { port: 5173 },
  build: { outDir: "dist" },
});
