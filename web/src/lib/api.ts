let cachedToken: string | null = null;

/** Identificador aleatorio de este navegador. Solo importa cuando se usa la app desde otro equipo de la red
 *  (invitado): el servidor lo usa para mostrarle únicamente sus consultas y aplicar los límites de uso. */
export function idInvitado(): string {
  const clave = "desemppa-invitado";
  try {
    const actual = localStorage.getItem(clave);
    if (actual && /^[A-Za-z0-9_-]{8,64}$/.test(actual)) return actual;
    const nuevo = Array.from(crypto.getRandomValues(new Uint8Array(12)), (b) => b.toString(16).padStart(2, "0")).join("");
    localStorage.setItem(clave, nuevo);
    return nuevo;
  } catch {
    return "sin-almacenamiento";
  }
}

/** Error HTTP con el código y la llamada que falló, para que la interfaz los muestre. */
export class ApiError extends Error {
  constructor(readonly status: number, readonly method: string, readonly path: string, readonly detail: string) {
    super(`${detail} (HTTP ${status} · ${method} ${path})`);
  }
}

/** Token local del servidor. Siempre se pide a /api/token (no va en el HTML, que el service worker podría
 *  tener cacheado de un arranque anterior). `forceRefresh` lo vuelve a pedir tras un 403. */
export async function token(forceRefresh = false): Promise<string> {
  if (cachedToken !== null && !forceRefresh) return cachedToken;
  const r = await fetch("/api/token", { cache: "no-store", headers: { "X-Desemppa-Invitado": idInvitado() } });
  if (!r.ok) throw new ApiError(r.status, "GET", "/api/token", "no se pudo obtener el token local");
  const data = await r.json();
  cachedToken = typeof data?.token === "string" ? data.token : "";
  return cachedToken ?? "";
}

export function resetToken(): void {
  cachedToken = null;
}

async function request<T>(path: string, init: RequestInit = {}, auth = false): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers(init.headers);
  headers.set("X-Desemppa-Invitado", idInvitado());
  if (auth) headers.set("X-Iuris-Token", await token());
  let r = await fetch(path, { ...init, headers, cache: "no-store" });
  if (r.status === 403 && auth) {
    // Token caducado (servidor reiniciado o pestaña antigua): se pide de nuevo y se reintenta una sola vez.
    headers.set("X-Iuris-Token", await token(true));
    r = await fetch(path, { ...init, headers, cache: "no-store" });
  }
  if (!r.ok) {
    let detail = r.statusText || "error";
    try {
      const body = await r.json();
      detail = typeof body?.detail === "string" ? body.detail : JSON.stringify(body?.detail ?? body);
    } catch {
      /* respuesta sin JSON */
    }
    throw new ApiError(r.status, method, path.split("?")[0], detail);
  }
  return (await r.json()) as T;
}

export const api = {
  estado: () => request<Record<string, any>>("/api/estado"),
  proveedores: () => request<Record<string, Proveedor>>("/api/proveedores"),
  detectar: (pid: string) =>
    request<{ instalado: boolean; modelos: string[] }>(`/api/proveedores/${pid}/detectar`, { method: "POST" }, true),
  configurarProveedor: (pid: string, body: { api_key?: string | null; habilitado?: boolean | null; base_url?: string | null }) =>
    request<{ ok: boolean; instalado: boolean; habilitado: boolean }>(`/api/proveedores/${pid}/configurar`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    }, true),
  crearModelo: (body: { alias: string; proveedor: string; model_id: string; etiqueta: string; efforts: string[] }) =>
    request<{ ok: boolean; alias: string }>("/api/modelos", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    }, true),
  probar: (alias: string) =>
    request<{ ok: boolean; latencia_ms: number; respuesta: string; error: string | null }>(
      `/api/modelos/${alias}/probar`, { method: "POST" }, true),
  perfiles: () => request<Perfiles>("/api/ajustes/perfiles"),
  guardarPerfiles: (modos: Perfiles["modos"]) =>
    request("/api/ajustes/perfiles", {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(modos),
    }, true),
  restablecerPerfiles: () => request("/api/ajustes/perfiles", { method: "DELETE" }, true),
  restablecerModelos: () => request("/api/ajustes/modelos", { method: "DELETE" }, true),
  sesion: () => request<Sesion>("/api/sesion"),
  red: () => request<EstadoRed>("/api/red"),
  ajustarRed: (body: { activo?: boolean; modos_permitidos?: string[]; tope_diario?: number }) =>
    request<EstadoRed>("/api/red", {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    }, true),
  consultas: () => request<{ consulta_id: string; creado_en: string; modo: string; estado: string; titulo: string; banda: string | null; invitado: boolean }[]>("/api/consultas"),
  consulta: (id: string) => request<Record<string, any>>(`/api/consultas/${id}`),
  crear: (body: { texto: string; modo: string; municipio_ine?: string | null; adjuntos: string[] }) =>
    request<{ consulta_id: string }>("/api/consultas", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    }, true),
  aclarar: (id: string, respuestas: { pregunta: string; respuesta: string; municipio_ine?: string | null }[]) =>
    request(`/api/consultas/${id}/aclaraciones`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ respuestas }),
    }, true),
  subir: (file: File, permitirEnvio: boolean) => {
    const fd = new FormData();
    fd.append("archivo", file);
    fd.append("permitir_envio", String(permitirEnvio));
    return request<{ adjunto_id: string; nombre: string; tipo: string; caracteres: number; paginas_sin_texto: number[] }>(
      "/api/adjuntos", { method: "POST", body: fd }, true);
  },
  fuente: (sourceId: string, consultaId?: string, quote?: string) => {
    const p = new URLSearchParams({ source_id: sourceId });
    if (consultaId) p.set("consulta_id", consultaId);
    if (quote) p.set("quote", quote);
    return request<{ titulo: string; texto: string; url: string | null; resaltado: { offsets: [number, number] | null; ok: boolean; score: number } | null }>(
      `/api/fuentes?${p}`);
  },
  municipios: (q: string) => request<{ codigo_ine: string; nombre: string; provincia: string }[]>(
    `/api/municipios?q=${encodeURIComponent(q)}`),
};

export async function streamUrl(id: string, after = 0): Promise<string> {
  return `/api/consultar/stream/${id}?token=${encodeURIComponent(await token())}&after=${after}&invitado=${idInvitado()}`;
}

export interface Proveedor {
  etiqueta: string;
  compania: string;
  modalidad: "plan" | "api";
  tipo: string;
  habilitado: boolean;
  instalado: boolean;
  version: string | null;
  api_key_env: string | null;
  ultima_llamada: { ok: boolean; error_tipo: string | null; creado_en: string; modelo: string } | null;
  breaker: { estado: string; abierto_hasta: string | null; motivo: string | null };
  uso_ultimas_5h: { llamadas: number; input_tokens: number; output_tokens: number };
  login: string;
  modelos: string[];
}

export type Asignacion = { model: string; effort: "low" | "medium" | "high" };

export interface ModeloCatalogo {
  etiqueta: string;
  proveedor: string;
  compania: string;
  modalidad: "plan" | "api";
  model_id: string;
  efforts: string[];
  disponible: boolean;
}

export interface Perfiles {
  modos: Record<string, Record<string, Asignacion>>;
  por_defecto: Record<string, Record<string, Asignacion>>;
  modelos: Record<string, ModeloCatalogo>;
}

export interface Sesion { rol: "dueno" | "invitado"; modos_permitidos: string[] }

export interface EstadoRed {
  activo: boolean;
  escucha_red: boolean;
  ip: string | null;
  url: string | null;
  modos_permitidos: string[];
  modos_disponibles: string[];
  tope_diario: number;
  invitados_activos: number;
  consultas_hoy: number;
}
