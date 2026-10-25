import { useEffect, useRef, useState } from "react";
import { Briefcase, Check, ChevronDown, Keyboard, Menu, Settings } from "lucide-react";
import { api, type Perfiles, type Proveedor } from "../lib/api";
import type { Modo } from "../lib/types";

export const MODOS: { id: Modo; label: string; resumen: string }[] = [
  { id: "eco", label: "Eco", resumen: "Rápido, todo con tu plan de Antigravity" },
  { id: "equilibrado", label: "Equilibrado", resumen: "Más criterio en la resolución" },
  { id: "pro", label: "Pro", resumen: "Los modelos más capaces para casos difíciles" },
];

/** Hay que avisar si algún proveedor activo no está instalado o su última llamada falló. */
function hayProblema(proveedores: Record<string, Proveedor> | null): string | null {
  if (!proveedores) return null;
  const malos = Object.values(proveedores).filter(
    (p) => p.habilitado && (!p.instalado || (p.ultima_llamada && !p.ultima_llamada.ok) || p.breaker.estado === "open"),
  );
  return malos.length ? `Revisa: ${malos.map((p) => p.etiqueta).join(", ")}` : null;
}

function ModeMenu({ modo, onModo, permitidos }: { modo: Modo; onModo: (m: Modo) => void; permitidos: string[] }) {
  const [abierto, setAbierto] = useState(false);
  const [perfiles, setPerfiles] = useState<Perfiles | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!abierto) return;
    api.perfiles().then(setPerfiles).catch(() => setPerfiles(null));
    const cerrar = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !ref.current?.contains(e.target as Node)) setAbierto(false);
    };
    document.addEventListener("mousedown", cerrar);
    document.addEventListener("keydown", cerrar);
    return () => {
      document.removeEventListener("mousedown", cerrar);
      document.removeEventListener("keydown", cerrar);
    };
  }, [abierto]);

  const visibles = MODOS.filter((m) => permitidos.includes(m.id));
  const actual = visibles.find((m) => m.id === modo) ?? visibles[0] ?? MODOS[0];
  const magistrado = (id: string) => {
    const alias = perfiles?.modos[id]?.magistrado?.model;
    return alias ? perfiles?.modelos[alias]?.etiqueta ?? alias : null;
  };

  return (
    <div ref={ref} className="relative">
      <button
        className="btn-ghost px-3"
        aria-haspopup="listbox"
        aria-expanded={abierto}
        aria-label={`Modo de razonamiento: ${actual.label}`}
        onClick={() => setAbierto((v) => !v)}
      >
        {actual.label}
        <ChevronDown className="h-4 w-4" aria-hidden />
      </button>
      {abierto && (
        <ul
          role="listbox"
          aria-label="Modo de razonamiento"
          className="fade-in absolute right-0 z-40 mt-1 w-80 rounded-2xl bg-surface p-1.5 shadow-float"
        >
          {visibles.map((m) => (
            <li key={m.id}>
              <button
                role="option"
                aria-selected={m.id === modo}
                onClick={() => {
                  onModo(m.id);
                  setAbierto(false);
                }}
                className="flex w-full items-start gap-3 rounded-xl px-3 py-2.5 text-left hover:bg-surface-2"
              >
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-medium text-ink">{m.label}</span>
                  <span className="block text-xs text-ink-2">{m.resumen}</span>
                  {magistrado(m.id) && (
                    <span className="mt-0.5 block text-xs text-ink-3">Resuelve: {magistrado(m.id)}</span>
                  )}
                </span>
                {m.id === modo && <Check className="mt-0.5 h-4 w-4 text-accent" aria-hidden />}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function TopBar({ modo, onModo, onMenu, onAjustes, onAyuda, enAjustes, invitado, permitidos, profesional, onProfesional }: {
  modo: Modo;
  onModo: (m: Modo) => void;
  onMenu: () => void;
  onAjustes: () => void;
  onAyuda: () => void;
  profesional: boolean;
  onProfesional: () => void;
  enAjustes: boolean;
  invitado: boolean;
  permitidos: string[];
}) {
  const [proveedores, setProveedores] = useState<Record<string, Proveedor> | null>(null);
  useEffect(() => {
    if (invitado) return;
    let t: ReturnType<typeof setInterval> | undefined;
    const load = () => api.proveedores().then(setProveedores).catch(() => {
      setProveedores(null);
      clearInterval(t); // sin reintentos en bucle si el servidor no responde a esta ruta
    });
    load();
    t = setInterval(load, 30_000);
    return () => clearInterval(t);
  }, [invitado]);
  const problema = hayProblema(proveedores);

  return (
    <header className="flex h-16 shrink-0 items-center gap-1 px-2 sm:px-3 print:hidden">
      <button className="icon-btn" onClick={onMenu} aria-label="Mostrar u ocultar el historial">
        <Menu className="h-5 w-5" />
      </button>
      <span className="ml-1 text-[22px] font-normal tracking-tight text-ink">Desemppa</span>
      <div className="ml-auto flex items-center gap-1">
        {!enAjustes && permitidos.length > 1 && <ModeMenu modo={modo} onModo={onModo} permitidos={permitidos} />}
        {!enAjustes && permitidos.length === 1 && (
          <span className="px-3 text-sm text-ink-2" title="Modo fijado por quien comparte la app">
            {MODOS.find((m) => m.id === permitidos[0])?.label ?? permitidos[0]}
          </span>
        )}
        <button className={`icon-btn ${profesional ? "bg-accent-container text-on-accent-container" : ""}`} onClick={onProfesional}
                aria-pressed={profesional} aria-label="Modo profesional"
                title={profesional ? "Modo profesional activado: vista técnica para abogados" : "Modo profesional (vista técnica para abogados)"}>
          <Briefcase className="h-5 w-5" />
        </button>
        <button className="icon-btn hidden sm:inline-flex" onClick={onAyuda} aria-label="Atajos de teclado" title="Atajos de teclado (?)">
          <Keyboard className="h-5 w-5" />
        </button>
        {!invitado && <button
          className={`icon-btn relative ${enAjustes ? "bg-surface-2 text-ink" : ""}`}
          onClick={onAjustes}
          aria-pressed={enAjustes}
          aria-label="Ajustes"
          title={problema ?? "Ajustes"}
        >
          <Settings className="h-5 w-5" />
          {problema && <span className="absolute right-2 top-2 h-2 w-2 rounded-full bg-warning" aria-hidden />}
          {problema && <span className="sr-only">: {problema}</span>}
        </button>}
      </div>
    </header>
  );
}
