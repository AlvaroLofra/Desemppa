import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["icon.svg"],
      manifest: {
        name: "Iuris-IA · Asistente legal personal",
        short_name: "Iuris-IA",
        description: "Información jurídica española verificada, en local.",
        lang: "es",
        start_url: "/",
        display: "standalone",
        background_color: "#020617",
        theme_color: "#020617",
        icons: [{ src: "icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any maskable" }],
      },
      // Solo se cachea el "shell": nunca respuestas de la API (dossier §2.5).
      workbox: { navigateFallbackDenylist: [/^\/api\//], runtimeCaching: [] },
    }),
  ],
  server: { port: 3000, proxy: { "/api": { target: "http://127.0.0.1:8000", changeOrigin: false } } },
  test: { environment: "node" },
});
