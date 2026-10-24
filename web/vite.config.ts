import { writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

// Identificador único de cada build: va compilado en el JS (__BUILD_ID__) y en dist/version.json, que el backend
// expone en /api/version. Si no coinciden, el JS es una copia antigua cacheada (ver src/lib/selfHeal.ts).
const BUILD_ID = Date.now().toString(36);

function versionFile(): Plugin {
  return {
    name: "iuris-version-file",
    apply: "build",
    writeBundle(options) {
      writeFileSync(resolve(options.dir ?? "dist", "version.json"), JSON.stringify({ build: BUILD_ID }));
    },
  };
}

export default defineConfig({
  define: { __BUILD_ID__: JSON.stringify(BUILD_ID) },
  plugins: [
    react(),
    versionFile(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["icon.svg"],
      manifest: {
        name: "Iuris · Asistente legal personal",
        short_name: "Iuris",
        description: "Información jurídica española verificada, en local.",
        lang: "es",
        start_url: "/",
        display: "standalone",
        background_color: "#ffffff",
        theme_color: "#ffffff",
        icons: [{ src: "icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any maskable" }],
      },
      workbox: {
        // Nunca se cachea HTML ni la API: el HTML lo sirve siempre el servidor (sin caché) y así una copia
        // antigua no puede dejar la app con un bundle o un token de otro arranque.
        globPatterns: ["**/*.{js,css,svg,webmanifest}"],
        globIgnores: ["**/version.json"],
        navigateFallback: null,
        runtimeCaching: [],
        cleanupOutdatedCaches: true,
        skipWaiting: true,
        clientsClaim: true,
      },
    }),
  ],
  server: { port: 3000, proxy: { "/api": { target: "http://127.0.0.1:8000", changeOrigin: false } } },
  test: { environment: "node" },
});
