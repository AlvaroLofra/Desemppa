import { useId } from "react";
import { Check, CircleCheck, CircleX, Circle, Loader2, Scale, Square } from "lucide-react";
import { construirArbol, citasFallidas, type NodoArgumento } from "../lib/arbol";
import { pasosMonitor } from "../lib/monitor";
import type { ConsultaState } from "../lib/useConsulta";

type AbrirFuente = (sourceId: string, quote?: string) => void;

/** Monitor del análisis: los cuatro pasos con lo que realmente ha ocurrido (eventos del servidor). Solo la línea
 *  en curso se anuncia al lector de pantalla, para no saturarlo. */
export function MonitorProceso({ state, onDetener }: { state: ConsultaState; onDetener?: () => void }) {
  if (!state.streaming || !state.estado || ["CERTIFICADA", "BLOQUEADA", "FUERA_DE_ALCANCE", "ERROR"].includes(state.estado)) {
    return null;
  }
  const pasos = pasosMonitor(state);
  if (!pasos.some((p) => p.estado === "en_curso")) return null;
  return (
    <section aria-label="Progreso del análisis" className="fade-in rounded-3xl bg-surface p-4">
      <div className="mb-2 flex items-center">
        <p className="eyebrow flex-1">Análisis en curso</p>
        {onDetener && (
          <button className="btn-ghost px-3 py-1 text-xs" onClick={onDetener} title="Detener el análisis">
            <Square className="h-3 w-3" aria-hidden />Detener
          </button>
        )}
      </div>
      <ol className="space-y-2">
        {pasos.map((p, i) => (
          <li key={p.id} className="flex gap-3" aria-current={p.estado === "en_curso" ? "step" : undefined}>
            <span className="mt-0.5 shrink-0" aria-hidden>
              {p.estado === "hecho" ? <Check className="h-4 w-4 text-success" />
                : p.estado === "en_curso" ? <Loader2 className="h-4 w-4 animate-spin text-accent" />
                : <Circle className="h-4 w-4 text-ink-3" />}
            </span>
            <div className="min-w-0 text-sm">
              <p className={p.estado === "pendiente" ? "text-ink-3" : "text-ink"}>
                <span className="sr-only">{p.estado === "hecho" ? "Hecho: " : p.estado === "en_curso" ? "En curso: " : "Pendiente: "}</span>
                {p.titulo}<span className="text-ink-3"> · paso {i + 1} de {pasos.length}</span>
              </p>
              {p.detalle && (
                <p className="truncate text-xs text-ink-2" aria-live={p.estado === "en_curso" ? "polite" : undefined}>{p.detalle}</p>
              )}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

function Argumentos({ args, vacio, onAbrir }: { args: NodoArgumento[]; vacio: string; onAbrir: AbrirFuente }) {
  if (!args.length) return <p className="text-sm text-ink-3">{vacio}</p>;
  return (
    <ul className="space-y-3">
      {args.map((a, i) => {
        const fallidas = citasFallidas(a);
        return (
          <li key={i} className="text-sm">
            <p className="text-ink">{a.afirmacion}</p>
            <ul className="mt-1 flex flex-wrap gap-1.5">
              {a.citas.map((c, k) => (
                <li key={k}>
                  <button className="chip gap-1 text-xs" onClick={() => onAbrir(c.source_id, c.verbatim_quote)}
                          title={c.verbatim_quote}>
                    {c.ok === false
                      ? <CircleX className="h-3.5 w-3.5 text-danger" aria-hidden />
                      : <CircleCheck className="h-3.5 w-3.5 text-success" aria-hidden />}
                    <span>{c.ok === false ? "Cita no literal" : c.ok ? "Cita verificada" : "Cita"}</span>
                    <span className="text-ink-3">· {c.source_id.split(":").slice(0, 3).join(":")}</span>
                  </button>
                </li>
              ))}
            </ul>
            {fallidas > 0 && <p className="mt-1 text-xs text-ink-3">Este argumento cita algo que no está literalmente en la fuente: no cuenta.</p>}
          </li>
        );
      })}
    </ul>
  );
}

/** Árbol de argumentos: por cada cuestión, lo que alegó cada parte (con la verificación de sus citas) y cómo la
 *  resolvió el Magistrado. Todo sale de los eventos del debate: no hay texto añadido. */
export function ArbolArgumentos({ state, onAbrir }: { state: ConsultaState; onAbrir: AbrirFuente }) {
  const arbol = construirArbol(state.alegatos, state.resolucion);
  const base = useId();
  if (!arbol.length) return null;
  return (
    <ol className="space-y-4" aria-label="Árbol de argumentos">
      {arbol.map((q) => {
        const titulo = `${base}-${q.id}`;
        const favorable = q.estimacion === "DEFENSA";
        return (
          <li key={q.id} className="rounded-3xl bg-surface p-5" aria-labelledby={titulo}>
            <p id={titulo} className="font-medium text-ink"><span className="text-ink-3">{q.id} · </span>{q.enunciado}</p>
            {q.estimacion && (
              <p className={`mt-1 flex items-center gap-1.5 text-sm ${favorable ? "text-success" : "text-danger"}`}>
                <Scale className="h-4 w-4" aria-hidden />
                Decisión: da la razón a {favorable ? "tu posición" : "la otra parte"}
              </p>
            )}
            <div className="mt-4 grid gap-5 md:grid-cols-2">
              <section aria-label={`${q.id}: argumentos a tu favor`} className="border-l-2 border-outline pl-3">
                <p className="eyebrow mb-2">Tu posición (defensa)</p>
                <Argumentos args={q.defensa} vacio="Sin argumentos en esta cuestión." onAbrir={onAbrir} />
              </section>
              <section aria-label={`${q.id}: argumentos de la otra parte`} className="border-l-2 border-dashed border-outline pl-3">
                <p className="eyebrow mb-2">La otra parte</p>
                <Argumentos args={q.contraparte} vacio="Sin argumentos en esta cuestión." onAbrir={onAbrir} />
              </section>
            </div>
            {q.fundamentos.length > 0 && (
              <section aria-label={`${q.id}: fundamentos de la decisión`} className="mt-4 border-t border-outline pt-3">
                <p className="eyebrow mb-2">Por qué lo decide así</p>
                <Argumentos args={q.fundamentos} vacio="" onAbrir={onAbrir} />
              </section>
            )}
          </li>
        );
      })}
    </ol>
  );
}
