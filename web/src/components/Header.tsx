import { useEffect, useState } from "react";
import { Gauge, Scale, SlidersHorizontal, Sparkles, Zap } from "lucide-react";
import { api, type Proveedor } from "../lib/api";
import type { Modo } from "../lib/types";

const MODOS: { id: Modo; label: string; icon: typeof Zap; desc: string }[] = [
  { id: "eco", label: "Eco", icon: Zap, desc: "Sin Claude: Gemini 3.5 (API) y Gemini 3.8 Flash (Antigravity)" },
  { id: "equilibrado", label: "Equilibrado", icon: Gauge, desc: "Gemini para el volumen + Magistrado Claude Sonnet" },
  { id: "pro", label: "Pro", icon: Sparkles, desc: "Defensa y Contraparte Sonnet + Magistrado Opus" },
];
const NOMBRE_CORTO: Record<string, string> = {
  gemini_api: "Gemini API", claude_cli: "Claude", antigravity_cli: "Antigravity", codex_cli: "Codex",
};

type Nivel = "ok" | "desconocido" | "aviso" | "error";
const COLOR: Record<Nivel, string> = {
  ok: "bg-emerald-400", desconocido: "bg-slate-500", aviso: "bg-amber-400", error: "bg-rose-500",
};
const ERRORES: Record<string, string> = {
  NotAuthenticated: "sin sesión iniciada",
  UsageLimitReached: "cuota agotada",
  RateLimited: "límite de peticiones alcanzado",
  ModelUnavailable: "modelo no disponible",
  ProviderTimeout: "tiempo de espera agotado",
};

/** Verde solo si la última llamada real funcionó; gris si aún no se ha usado. */
function nivel(p: Proveedor): { nivel: Nivel; texto: string } {
  if (!p.instalado) return { nivel: "error", texto: "no instalado o sin configurar" };
  if (p.breaker.estado === "open") return { nivel: "aviso", texto: "cuota agotada: se usa otro modelo" };
  if (!p.ultima_llamada) return { nivel: "desconocido", texto: "aún no se ha usado" };
  if (p.ultima_llamada.ok) return { nivel: "ok", texto: "última llamada correcta" };
  return { nivel: "error", texto: ERRORES[p.ultima_llamada.error_tipo ?? ""] ?? `último error: ${p.ultima_llamada.error_tipo}` };
}

export function Header({ modo, onModo, onModelos, enModelos }: {
  modo: Modo;
  onModo: (m: Modo) => void;
  onModelos: () => void;
  enModelos: boolean;
}) {
  const [proveedores, setProveedores] = useState<Record<string, Proveedor> | null>(null);
  useEffect(() => {
    const load = () => api.proveedores().then(setProveedores).catch(() => setProveedores(null));
    load();
    const t = setInterval(load, 30_000);
    return () => clearInterval(t);
  }, []);

  return (
    <header className="flex flex-wrap items-center gap-3 border-b border-slate-800 bg-slate-950/80 px-4 py-3 backdrop-blur">
      <div className="flex items-center gap-2">
        <Scale className="h-6 w-6 text-amber-400" aria-hidden />
        <span className="text-lg font-semibold tracking-tight text-slate-100">Iuris-IA</span>
        <span className="hidden text-xs text-slate-500 sm:inline">asistente legal personal · España</span>
      </div>
      <nav aria-label="Modo de razonamiento" className="ml-auto flex rounded-lg border border-slate-800 bg-slate-900 p-0.5">
        {MODOS.map(({ id, label, icon: Icon, desc }) => (
          <button
            key={id}
            title={desc}
            aria-pressed={modo === id}
            onClick={() => onModo(id)}
            className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm transition ${
              modo === id ? "bg-amber-500 text-slate-950" : "text-slate-400 hover:text-slate-100"
            }`}
          >
            <Icon className="h-3.5 w-3.5" aria-hidden />
            {label}
          </button>
        ))}
      </nav>
      <div className="flex items-center gap-3 text-xs">
        {proveedores && Object.entries(proveedores).filter(([, p]) => p.habilitado).map(([pid, p]) => {
          const st = nivel(p);
          return (
            <span key={pid} className="flex items-center gap-1.5" title={`${p.etiqueta}: ${st.texto}`}>
              <span className={`h-2 w-2 rounded-full ${COLOR[st.nivel]}`} />{NOMBRE_CORTO[pid] ?? pid}
              <span className="sr-only">: {st.texto}</span>
            </span>
          );
        })}
        <button onClick={onModelos} aria-pressed={enModelos}
                className={`btn-ghost px-2 py-1 text-xs ${enModelos ? "text-amber-300" : ""}`} title="Modelos y proveedores">
          <SlidersHorizontal className="h-3.5 w-3.5" />Modelos
        </button>
      </div>
    </header>
  );
}
