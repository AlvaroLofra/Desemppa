let cachedToken: string | null = null;

/** Token local por arranque: lo inyecta el backend en el HTML; en desarrollo (Vite) se pide a /api/token. */
export async function token(): Promise<string> {
  if (cachedToken) return cachedToken;
  const meta = document.querySelector<HTMLMetaElement>('meta[name="iuris-token"]')?.content;
  if (meta && meta !== "__IURIS_TOKEN__") {
    cachedToken = meta;
  } else {
    const r = await fetch("/api/token");
    cachedToken = (await r.json()).token as string;
  }
  return cachedToken;
}

async function request<T>(path: string, init: RequestInit = {}, auth = false): Promise<T> {
  const headers = new Headers(init.headers);
  if (auth) headers.set("X-Iuris-Token", await token());
  const r = await fetch(path, { ...init, headers });
  if (!r.ok) {
    let detail = r.statusText;
    try {
      detail = (await r.json()).detail ?? detail;
    } catch {
      /* respuesta sin JSON */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return (await r.json()) as T;
}

export const api = {
  estado: () => request<Record<string, any>>("/api/estado"),
  proveedores: () => request<Record<string, Proveedor>>("/api/proveedores"),
  detectar: (pid: string) =>
    request<{ instalado: boolean; modelos: string[] }>(`/api/proveedores/${pid}/detectar`, { method: "POST" }, true),
  probar: (alias: string) =>
    request<{ ok: boolean; latencia_ms: number; respuesta: string; error: string | null }>(
      `/api/modelos/${alias}/probar`, { method: "POST" }, true),
  perfiles: () => request<Perfiles>("/api/ajustes/perfiles"),
  guardarPerfiles: (modos: Perfiles["modos"]) =>
    request("/api/ajustes/perfiles", {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(modos),
    }, true),
  restablecerPerfiles: () => request("/api/ajustes/perfiles", { method: "DELETE" }, true),
  consultas: () => request<{ consulta_id: string; creado_en: string; modo: string; estado: string; titulo: string; banda: string | null }[]>("/api/consultas"),
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
  return `/api/consultar/stream/${id}?token=${encodeURIComponent(await token())}&after=${after}`;
}

export interface Proveedor {
  etiqueta: string;
  tipo: string;
  habilitado: boolean;
  instalado: boolean;
  version: string | null;
  ultima_llamada: { ok: boolean; error_tipo: string | null; creado_en: string; modelo: string } | null;
  breaker: { estado: string; abierto_hasta: string | null; motivo: string | null };
  uso_ultimas_5h: { llamadas: number; input_tokens: number; output_tokens: number };
  login: string;
  modelos: string[];
}

export type Asignacion = { model: string; effort: "low" | "medium" | "high" };

export interface Perfiles {
  modos: Record<string, Record<string, Asignacion>>;
  por_defecto: Record<string, Record<string, Asignacion>>;
  modelos: Record<string, { etiqueta: string; proveedor: string; efforts: string[]; disponible: boolean }>;
}
