/**
 * Auto-reparación de instalaciones antiguas de la PWA.
 *
 * Si el service worker sirve un bundle de un build anterior (el síntoma del "token local inválido"), el id de
 * build compilado en este JS no coincide con el que anuncia el servidor en /api/version. En ese caso se
 * desregistran los service workers, se borran las cachés y se recarga UNA sola vez (marca en sessionStorage
 * para no entrar en bucle si algo más fallara).
 */
export interface SelfHealEnv {
  buildId: string;
  fetchServerBuild: () => Promise<string | null>;
  unregisterAll: () => Promise<void>;
  clearCaches: () => Promise<void>;
  reload: () => void;
  storage: Pick<Storage, "getItem" | "setItem" | "removeItem">;
}

const MARK = "iuris-selfheal";

export async function selfHeal(env: SelfHealEnv): Promise<"ok" | "reloading" | "mismatch-persisting" | "unknown"> {
  let server: string | null;
  try {
    server = await env.fetchServerBuild();
  } catch {
    return "unknown";
  }
  if (!server) return "unknown";
  if (server === env.buildId) {
    env.storage.removeItem(MARK);
    return "ok";
  }
  if (env.storage.getItem(MARK) === server) return "mismatch-persisting"; // ya se intentó con este build
  env.storage.setItem(MARK, server);
  await env.unregisterAll();
  await env.clearCaches();
  env.reload();
  return "reloading";
}

export function browserEnv(buildId: string): SelfHealEnv {
  return {
    buildId,
    fetchServerBuild: async () => {
      const r = await fetch("/api/version", { cache: "no-store" });
      return r.ok ? ((await r.json()).build as string | null) : null;
    },
    unregisterAll: async () => {
      if (!("serviceWorker" in navigator)) return;
      for (const reg of await navigator.serviceWorker.getRegistrations()) await reg.unregister();
    },
    clearCaches: async () => {
      if (!("caches" in window)) return;
      for (const key of await caches.keys()) await caches.delete(key);
    },
    reload: () => window.location.reload(),
    storage: sessionStorage,
  };
}
