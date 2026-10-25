import { useState } from "react";
import { Check, Copy } from "lucide-react";
import type { ConsultaState } from "../lib/useConsulta";
import type { Dictamen } from "../lib/types";
import type { AbrirFuente } from "./Results";

/** «BOE:BOE-A-1994-26003:a36:2026-10-08» → versión vigente desde el 08-10-2026. */
export function versionDe(sid: string): string | null {
  const m = sid.match(/^BOE:[^:]+:[^:]+:(\d{4})-(\d{2})-(\d{2})$/);
  return m ? `${m[3]}-${m[2]}-${m[1]}` : null;
}

/** Esquema hechos / fundamentos de derecho / súplica, solo con material verificado. */
export function esquemaEscrito(d: Dictamen, relato: string, titulos: Map<string, string>): string {
  const normas = (d.afirmaciones ?? []).filter((a) => a.tipo === "norma" && a.citas.length);
  const ref = (sid: string) => `${titulos.get(sid) ?? sid}${versionDe(sid) ? ` (redacción vigente desde ${versionDe(sid)})` : ""}`;
  return [
    "HECHOS",
    ...relato.trim().split(/\n+/).map((l, i) => `${i + 1}. ${l}`),
    "",
    "FUNDAMENTOS DE DERECHO",
    ...normas.map((a, i) => `${i + 1}. ${a.texto} — ${ref(a.citas[0].source_id)}: «${a.citas[0].verbatim_quote}».`),
    ...d.fundamentos.map((f, i) => `${normas.length + i + 1}. ${f.texto} — ${ref(f.source_id)}: «${f.verbatim_quote}».`),
    "",
    "SÚPLICA",
    "[Concreta la pretensión: condena al pago de IMPORTE euros más intereses / anulación del acto / readmisión…]",
  ].join("\n");
}

/** Vista para profesionales: mismo dictamen y mismas verificaciones, en registro técnico. */
export function VistaProfesional({ state, d, onAbrir }: { state: ConsultaState; d: Dictamen; onAbrir: AbrirFuente }) {
  const [copiado, setCopiado] = useState(false);
  const t = state.triage;
  const titulos = new Map(state.fuentes.map((x) => [x.source_id, x.titulo]));
  const contraparte = state.alegatos.contraparte?.alegato;
  const esquema = esquemaEscrito(d, state.pregunta ?? "", titulos);
  return (
    <section aria-label="Vista profesional" className="space-y-5 rounded-3xl border border-outline p-5">
      <div>
        <p className="eyebrow mb-1">Vista profesional</p>
        {t && (
          <p className="text-sm text-ink">
            {t.submateria_descripcion ?? t.submateria_principal} · orden {t.jurisdiccion_principal.replace("_", " ")}
            {t.fecha_hechos && ` · hechos: ${t.fecha_hechos}`}
            {t.cuantia_estimada_eur != null && ` · cuantía: ${t.cuantia_estimada_eur.toLocaleString("es-ES")} €`}
          </p>
        )}
      </div>

      {state.resolucion && (
        <div>
          <p className="mb-2 text-sm font-medium text-ink">Cuestiones litigiosas y estimación</p>
          <ol className="space-y-3 text-sm">
            {state.resolucion.cuestiones.map((q) => (
              <li key={q.id}>
                <p className="text-ink">{q.id}. {q.enunciado} <span className="text-ink-2">({q.tipo.replace(/_/g, " ")})</span></p>
                <p className={q.estimacion === "DEFENSA" ? "text-success" : "text-danger"}>
                  Se estima la posición de {q.estimacion === "DEFENSA" ? "la parte consultante" : "la contraparte"}
                </p>
                {q.fundamentos.map((f, i) => (
                  <p key={i} className="mt-1 text-ink-2">
                    {f.afirmacion}{" "}
                    {f.citas.map((c, j) => (
                      <button key={j} className="text-xs text-accent hover:underline" onClick={() => onAbrir(c.source_id, c.verbatim_quote)}>
                        [{titulos.get(c.source_id) ?? c.source_id}{versionDe(c.source_id) ? `, v. ${versionDe(c.source_id)}` : ""}]
                      </button>
                    ))}
                  </p>
                ))}
              </li>
            ))}
          </ol>
        </div>
      )}

      {contraparte && (
        <div>
          <p className="mb-1 text-sm font-medium text-ink">Argumentos previsibles de la contraparte</p>
          <p className="mb-1 text-sm text-ink-2">Pretensión: {contraparte.pretension}</p>
          <ul className="list-disc space-y-1 pl-5 text-sm text-ink-2">
            {contraparte.cuestiones.flatMap((q) => q.argumentos.map((a, i) => (
              <li key={`${q.id}-${i}`}>{a.afirmacion}</li>
            )))}
          </ul>
        </div>
      )}

      <div>
        <div className="mb-1 flex items-center gap-2">
          <p className="flex-1 text-sm font-medium text-ink">Esquema de escrito (solo material verificado)</p>
          <button className="btn-ghost px-2 py-1 text-xs print:hidden" onClick={() => navigator.clipboard?.writeText(esquema).then(() => {
            setCopiado(true);
            setTimeout(() => setCopiado(false), 1500);
          })}>
            {copiado ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}{copiado ? "Copiado" : "Copiar"}
          </button>
        </div>
        <pre className="max-h-80 overflow-auto whitespace-pre-wrap rounded-2xl bg-surface p-4 font-mono text-xs text-ink scroll-thin print:max-h-none"
             tabIndex={0}>{esquema}</pre>
      </div>
    </section>
  );
}
