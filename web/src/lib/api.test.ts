import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, api, resetToken, token } from "./api";
import { selfHeal, type SelfHealEnv } from "./selfHeal";

function json(status: number, body: unknown) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

afterEach(() => {
  vi.unstubAllGlobals();
  resetToken();
});

describe("token y peticiones autenticadas", () => {
  it("pide el token a /api/token y lo reutiliza", async () => {
    const fetchMock = vi.fn(async () => json(200, { token: "t1" }));
    vi.stubGlobal("fetch", fetchMock);
    expect(await token()).toBe("t1");
    expect(await token()).toBe("t1");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("tras un 403 pide un token nuevo y reintenta una vez", async () => {
    let tokenActual = "viejo";
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (url === "/api/token") return json(200, { token: tokenActual });
      const enviado = new Headers(init?.headers).get("X-Iuris-Token");
      return enviado === "nuevo" ? json(201, { consulta_id: "c1" }) : json(403, { detail: "token local inválido" });
    });
    vi.stubGlobal("fetch", fetchMock);
    await token(); // cachea "viejo"
    tokenActual = "nuevo"; // el servidor se reinició
    const r = await api.crear({ texto: "texto de prueba largo", modo: "eco", adjuntos: [] });
    expect(r.consulta_id).toBe("c1");
  });

  it("el error incluye código HTTP y la llamada", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) =>
      url === "/api/token" ? json(200, { token: "x" }) : json(403, { detail: "token local inválido" })));
    const err = await api.crear({ texto: "texto de prueba largo", modo: "eco", adjuntos: [] }).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(403);
    expect(err.message).toContain("HTTP 403 · POST /api/consultas");
  });
});

describe("selfHeal", () => {
  function env(server: string | null, buildId = "b2"): SelfHealEnv & { store: Map<string, string>; calls: string[] } {
    const store = new Map<string, string>();
    const calls: string[] = [];
    return {
      buildId,
      store,
      calls,
      fetchServerBuild: async () => server,
      unregisterAll: async () => void calls.push("unregister"),
      clearCaches: async () => void calls.push("clear"),
      reload: () => void calls.push("reload"),
      storage: {
        getItem: (k) => store.get(k) ?? null,
        setItem: (k, v) => void store.set(k, v),
        removeItem: (k) => void store.delete(k),
      },
    };
  }

  it("no hace nada si el build coincide", async () => {
    const e = env("b2");
    expect(await selfHeal(e)).toBe("ok");
    expect(e.calls).toEqual([]);
  });

  it("limpia y recarga una sola vez si el JS es antiguo", async () => {
    const e = env("b3");
    expect(await selfHeal(e)).toBe("reloading");
    expect(e.calls).toEqual(["unregister", "clear", "reload"]);
    expect(await selfHeal(e)).toBe("mismatch-persisting"); // sin bucle de recargas
  });

  it("si el servidor no responde, sigue arrancando", async () => {
    const e = env(null);
    expect(await selfHeal(e)).toBe("unknown");
  });
});
