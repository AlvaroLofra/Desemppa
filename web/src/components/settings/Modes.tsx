import type { Asignacion, Perfiles } from "../../lib/api";

export const MODOS_AJUSTES = [
  { id: "eco", label: "Eco" },
  { id: "equilibrado", label: "Equilibrado" },
  { id: "pro", label: "Pro" },
];

const ROLES = [
  { id: "triaje", label: "Triaje", ayuda: "Clasifica la consulta" },
  { id: "cribado", label: "Cribado", ayuda: "Selecciona fuentes" },
  { id: "defensa", label: "Defensa", ayuda: "Argumenta a tu favor" },
  { id: "contraparte", label: "Contraparte", ayuda: "Ataca tu posición" },
  { id: "magistrado", label: "Magistrado", ayuda: "Resuelve: la tarea más exigente" },
  { id: "nli", label: "Verificación", ayuda: "Comprueba que la conclusión no contradice la norma" },
];

const ESFUERZO: Record<string, string> = { low: "Bajo", medium: "Medio", high: "Alto" };

function OpcionesModelo({ perfiles }: { perfiles: Perfiles }) {
  const grupos = [
    { label: "Tus planes", items: Object.entries(perfiles.modelos).filter(([, m]) => m.modalidad !== "api") },
    { label: "APIs por clave", items: Object.entries(perfiles.modelos).filter(([, m]) => m.modalidad === "api") },
  ];
  return (
    <>
      {grupos.map((g) => (
        <optgroup key={g.label} label={g.label}>
          {g.items.map(([alias, m]) => (
            <option key={alias} value={alias}>{m.etiqueta}{m.disponible ? "" : " (no disponible)"}</option>
          ))}
        </optgroup>
      ))}
    </>
  );
}

/** Qué modelo y esfuerzo hace cada tarea en cada modo. */
export function Modes({ perfiles, modos, onCambiar, onTodoElModo }: {
  perfiles: Perfiles;
  modos: Perfiles["modos"];
  onCambiar: (modo: string, rol: string, cambio: Partial<Asignacion>) => void;
  onTodoElModo: (modo: string, alias: string) => void;
}) {
  return (
    <div className="space-y-6">
      {MODOS_AJUSTES.map((m) => (
        <div key={m.id} className="rounded-3xl bg-surface p-5">
          <div className="mb-3 flex flex-wrap items-center gap-3">
            <h3 className="text-base font-medium text-ink">{m.label}</h3>
            <select
              aria-label={`Usar un modelo para todas las tareas del modo ${m.label}`}
              className="field ml-auto w-auto max-w-[16rem] py-1.5 text-xs"
              value=""
              onChange={(e) => e.target.value && onTodoElModo(m.id, e.target.value)}
            >
              <option value="">Usar un modelo para todo…</option>
              <OpcionesModelo perfiles={perfiles} />
            </select>
          </div>
          <ul className="divide-y divide-outline">
            {ROLES.map((r) => {
              const a = modos[m.id]?.[r.id];
              if (!a) return null;
              const info = perfiles.modelos[a.model];
              const def = perfiles.por_defecto[m.id]?.[r.id];
              const cambiado = def && (def.model !== a.model || def.effort !== a.effort);
              return (
                <li key={r.id} className="flex flex-wrap items-center gap-x-4 gap-y-2 py-3">
                  <div className="min-w-[10rem] flex-1">
                    <p className="text-sm text-ink">{r.label}{cambiado && <span className="ml-2 text-xs text-accent">modificado</span>}</p>
                    <p className="text-xs text-ink-2">{r.ayuda}</p>
                    {info && !info.disponible && (
                      <p className="text-xs text-warning">No disponible ahora: se usará su alternativa</p>
                    )}
                  </div>
                  <select aria-label={`${r.label} en modo ${m.label}`} className="field w-full py-1.5 sm:w-72"
                          value={a.model} onChange={(e) => onCambiar(m.id, r.id, { model: e.target.value })}>
                    <OpcionesModelo perfiles={perfiles} />
                  </select>
                  <select aria-label={`Esfuerzo de ${r.label} en modo ${m.label}`} className="field w-28 py-1.5"
                          value={a.effort}
                          onChange={(e) => onCambiar(m.id, r.id, { effort: e.target.value as Asignacion["effort"] })}>
                    {(info?.efforts ?? []).map((ef) => <option key={ef} value={ef}>{ESFUERZO[ef] ?? ef}</option>)}
                  </select>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
      <p className="text-xs text-ink-3">
        Si un modelo falla, agota su cuota o su programa no tiene sesión, la consulta pasa sola a la siguiente alternativa
        definida en <code>config/models.toml</code> y la respuesta lo indica en sus avisos.
      </p>
    </div>
  );
}
