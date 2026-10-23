import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { registerSW } from "virtual:pwa-register";
import App from "./App";
import { browserEnv, selfHeal } from "./lib/selfHeal";
import "./index.css";

declare const __BUILD_ID__: string;

async function arrancar() {
  // Si este JS viene de una caché antigua del service worker, se limpia y se recarga antes de pintar nada.
  const estado = await selfHeal(browserEnv(__BUILD_ID__));
  if (estado === "reloading") return;
  registerSW({ immediate: true });
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}

void arrancar();
