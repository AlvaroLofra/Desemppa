import { useEffect, useState } from "react";
import { Cpu, Gauge, Scale, Sparkles, Zap } from "lucide-react";
import { api } from "../lib/api";
import type { Modo } from "../lib/types";

const MODOS: { id: Modo; label: string; icon: typeof Zap; desc: string }[] = [
  { id: "eco", label: "Eco", icon: Zap, desc: "Solo Gemini · 0 llamadas a Claude" },
  { id: "equilibrado", label: "Equilibrado", icon: Gauge, desc: "Gemini + Magistrado Sonnet · 1 llamada a Claude" },
  { id: "pro", label: "Pro", icon: Sparkles, desc: "Sonnet + Magistrado Opus · 3 llamadas a Claude" },
];

type Nivel = "ok" | "desconocido" | "aviso" | "error";
const COLOR: Record<Nivel, string> = {
  ok: "bg-emerald-400", desconocido: "bg-slate-500", aviso: "bg-amber-400", error: "bg-rose-500",
};
const ERRORES: Record<string, string> = {
  NotAuthenticated: "sin sesión: ejecuta `claude` y `/login` en una terminal",
  UsageLimitReached: "cuota agotada",
  RateLimited: "límite de peticiones alcanzado",
  ModelUnavailable: "modelo no disponible",
  ProviderTimeout: "tiempo de espera agotado",
};

/** Verde solo si la última llamada real funcionó; gris si aún no se ha usado. */
function proveedor(
  instalado: boolean, breaker: string | undefined, ultima: { ok: boolean; error_tipo: string | null } | null | undefined,
  faltaTexto: string,
): { nivel: Nivel; texto: string } {
  if (!instalado) return { nivel: "error", texto: faltaTexto };
  if (breaker === "open") return { nivel: "aviso", texto: "cuota agotada: se usa otro modelo hasta que se restablezca" };
  if (!ultima) return { nivel: "desconocido", texto: "aún no se ha usado en esta instalación" };
  if (ultima.ok) return { nivel: "ok", texto: "última llamada correcta" };
  return { nivel: "error", texto: ERRORES[ultima.error_tipo ?? ""] ?? `último error: ${ultima.error_tipo}` };
}

export function Header({ modo, onModo }: { modo: Modo; onModo: (m: Modo) => void }) {
  const [estado, setEstado] = useState<Record<string, any> | null>(null);
  useEffect(() => {
    const load = () => api.estado().then(setEstado).catch(() => setEstado(null));
    load();
    const t = setInterval(load, 30_000);
    return () => clearInterval(t);
  }, []);
  const claude = proveedor(
    Boolean(estado?.claude_cli?.version), estado?.circuit_breakers?.claude?.estado, estado?.claude_cli?.ultima_llamada,
    "CLI de Claude no encontrado",
  );
  const gemini = proveedor(
    Boolean(estado?.gemini?.api_key_configurada), estado?.circuit_breakers?.gemini?.estado,
    estado?.gemini?.ultima_llamada, "Falta GEMINI_API_KEY",
  );

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
        {([["Gemini", gemini], ["Claude", claude]] as const).map(([nombre, st]) => (
          <span key={nombre} className="flex items-center gap-1.5" title={st.texto}>
            <span className={`h-2 w-2 rounded-full ${COLOR[st.nivel]}`} />{nombre}
            <span className="sr-only">: {st.texto}</span>
          </span>
        ))}
        <Cpu className="h-3.5 w-3.5 text-slate-600" aria-hidden />
      </div>
    </header>
  );
}
