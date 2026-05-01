import { svelte } from "@sveltejs/vite-plugin-svelte";
import { defineConfig } from "vite";

const backend = process.env.BACKEND_URL ?? "http://localhost:8000";

export default defineConfig({
  plugins: [svelte()],
  server: {
    port: 5173,
    proxy: {
      "/v1": { target: backend, changeOrigin: true },
      "/api": { target: backend, changeOrigin: true },
      "/health": { target: backend, changeOrigin: true },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
});
