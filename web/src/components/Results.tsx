import { useState } from "react";
import { AlertCircle, Check, ChevronDown, Copy, Info, Loader2, Printer, X } from "lucide-react";
import type { ConsultaState, Rol } from "../lib/useConsulta";
import { BANDA_TEXTO, type Argumento, type Banda, type Fuente, type Plazo, type Postulacion, type Pregunta } from "../lib/types";
import { diasNaturalesHasta, fechaLarga } from "../lib/highlight";
import { MunicipioPicker, type Municipio } from "./MunicipioPicker";

export type AbrirFuente = (sourceId: string, quote?: string) => void;

const FASES = [
  { label: "Entendiendo tu caso", estados: ["RECIBIDA", "TRIAJE", "ESPERANDO_ACLARACION"] },
  { label: "Buscando en el BOE y en la jurisprudencia", estados: ["INGESTA", "INGESTA_DEGRADADA"] },
  { label: "Enfrentando los argumentos de ambas partes", estados: ["DEBATE"] },
  { label: "Verificando cada cita contra el texto oficial", estados: ["GUARDARRAILES"] },
];

/** Una sola línea de progreso, como el «pensando…» de Gemini. */
export function ProgressLine({ estado, streaming }: { estado: string | null; streaming: boolean }) {
  const i = FASES.findIndex((f) => estado && f.estados.includes(estado));
  if (!streaming || i < 0) return null;
  return (
    <p className="fade-in flex items-center gap-3 text-sm text-ink-2" aria-live="polite">
      <Loader2 className="h-4 w-4 animate-spin text-accent" aria-hidden />
      {FASES[i].label}…<span className="text-ink-3">Fase {i + 1} de {FASES.length}</span>
    </p>
  );
}

export function Clarification({ preguntas, onResponder }: {
  preguntas: Pregunta[];
  onResponder: (r: { pregunta: string; respuesta: string; municipio_ine?: string | null }[]) => void;
}) {
  const [resp, setResp] = useState<Record<string, string>>({});
  const [muni, setMuni] = useState<Municipio | null>(null);
  const listo = preguntas.every((p) => (p.tipo_respuesta === "municipio" ? muni : resp[p.id]?.trim()));
  return (
    <section className="fade-in space-y-4" aria-label="Preguntas aclaratorias">
      <p className="text-base text-ink">Antes de seguir, necesito algunos datos para no equivocarme:</p>
      <div className="space-y-4 rounded-3xl bg-surface p-5">
        {preguntas.map((p) => (
          <label key={p.id} className="block">
            <span className="mb-2 block text-sm text-ink">{p.texto}</span>
            {p.tipo_respuesta === "municipio" ? (
              <MunicipioPicker value={muni} onChange={setMuni} compact arriba={false} />
            ) : p.tipo_respuesta === "si_no" ? (
              <span className="flex gap-2">
                {["Sí", "No"].map((o) => (
                  <button key={o} type="button" onClick={() => setResp({ ...resp, [p.id]: o })}
                          aria-pressed={resp[p.id] === o}
                          className={resp[p.id] === o ? "btn-tonal" : "btn-outline"}>{o}</button>
                ))}
              </span>
            ) : p.opciones?.length ? (
              <select className="field max-w-sm" value={resp[p.id] ?? ""}
                      onChange={(e) => setResp({ ...resp, [p.id]: e.target.value })}>
                <option value="">Elige…</option>
                {p.opciones.map((o) => <option key={o}>{o}</option>)}
              </select>
            ) : (
              <input type={p.tipo_respuesta === "fecha" ? "date" : p.tipo_respuesta === "importe" ? "number" : "text"}
                     className="field max-w-sm" value={resp[p.id] ?? ""}
                     onChange={(e) => setResp({ ...resp, [p.id]: e.target.value })} />
            )}
          </label>
        ))}
        <button className="btn-primary" disabled={!listo} onClick={() => onResponder(preguntas.map((p) => ({
          pregunta: p.texto,
          respuesta: p.tipo_respuesta === "municipio" ? `${muni?.nombre} (${muni?.provincia})` : resp[p.id] ?? "",
          municipio_ine: p.tipo_respuesta === "municipio" ? muni?.codigo_ine : undefined,
        })))}>Continuar</button>
      </div>
    </section>
  );
}

// ---------- proceso (plegado por defecto) ----------

const TIPO_FUENTE: Record<Fuente["tipo"], string> = {
  boe: "Legislación", ue: "Derecho de la UE", sentencia: "Jurisprudencia", convenio: "Convenio colectivo",
  adjunto: "Tus documentos",
};

function Fuentes({ fuentes, onAbrir }: { fuentes: Fuente[]; onAbrir: AbrirFuente }) {
  if (!fuentes.length) return null;
  const tipos = [...new Set(fuentes.map((f) => f.tipo))];
  return (
    <div className="space-y-3">
      {tipos.map((t) => (
        <div key={t}>
          <p className="eyebrow mb-1">{TIPO_FUENTE[t] ?? t}</p>
          <ul>
            {fuentes.filter((f) => f.tipo === t).map((f) => (
              <li key={f.source_id}>
                <button className="w-full truncate rounded-lg px-2 py-1.5 text-left text-sm text-ink hover:bg-surface-2"
                        title={f.extracto} onClick={() => onAbrir(f.source_id)}>{f.titulo}</button>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

function Citas({ args, verif, onAbrir }: { args: Argumento[]; verif?: { ok: boolean }[][]; onAbrir: AbrirFuente }) {
  return (
    <ul className="space-y-4">
      {args.map((a, i) => (
        <li key={i}>
          <p className="text-sm text-ink">{a.afirmacion}</p>
          {a.citas.map((c, j) => {
            const ok = verif?.[i]?.[j]?.ok;
            return (
              <button key={j} onClick={() => onAbrir(c.source_id, c.verbatim_quote)}
                      className="mt-1.5 block w-full border-l-2 border-outline pl-3 text-left hover:border-accent">
                <span className="font-serif text-[15px] italic leading-relaxed text-ink-2">«{c.verbatim_quote}»</span>
                <span className="mt-0.5 flex items-center gap-1 text-xs text-ink-3">
                  {ok === false ? <X className="h-3 w-3 text-danger" aria-hidden /> : ok ? <Check className="h-3 w-3 text-success" aria-hidden /> : null}
                  {c.source_id}{ok === false && " · cita no verificada"}
                </span>
              </button>
            );
          })}
        </li>
      ))}
    </ul>
  );
}

function Debate({ state, onAbrir }: { state: ConsultaState; onAbrir: AbrirFuente }) {
  const [tab, setTab] = useState<Rol>("magistrado");
  const tabs: { id: Rol; label: string }[] = [
    { id: "defensa", label: "Defensa" },
    { id: "contraparte", label: "Contraparte" },
    { id: "magistrado", label: "Magistrado" },
  ];
  const borrador = state.borradores[tab];
  return (
    <div>
      <div role="tablist" className="flex gap-6 border-b border-outline">
        {tabs.map(({ id, label }) => (
          <button key={id} role="tab" aria-selected={tab === id} onClick={() => setTab(id)}
                  className={`-mb-px flex items-center gap-2 border-b-2 pb-2 pt-1 text-sm transition-colors ${
                    tab === id ? "border-accent font-medium text-accent" : "border-transparent text-ink-2 hover:text-ink"
                  }`}>
            {label}{state.borradores[id] && <Loader2 className="h-3 w-3 animate-spin" aria-hidden />}
          </button>
        ))}
      </div>
      <div role="tabpanel" className="max-h-[28rem] overflow-auto pt-4 scroll-thin">
        {borrador && <pre className="whitespace-pre-wrap font-mono text-xs text-ink-3">{borrador.slice(-4000)}</pre>}
        {!borrador && tab !== "magistrado" && state.alegatos[tab] && (
          <div className="space-y-4">
            <p className="text-sm text-ink-2"><span className="font-medium text-ink">Pretensión:</span> {state.alegatos[tab]!.alegato.pretension}</p>
            <Citas args={state.alegatos[tab]!.alegato.cuestiones.flatMap((q) => q.argumentos)}
                   verif={state.alegatos[tab]!.verificacion} onAbrir={onAbrir} />
          </div>
        )}
        {!borrador && tab === "magistrado" && state.resolucion && (
          <div className="space-y-6">
            {state.resolucion.cuestiones.map((q) => (
              <div key={q.id}>
                <p className="text-sm font-medium text-ink">{q.enunciado}</p>
                <p className="mb-2 text-xs text-ink-2">Estima: {q.estimacion === "DEFENSA" ? "tu posición" : "la de la otra parte"}</p>
                <Citas args={q.fundamentos} onAbrir={onAbrir} />
              </div>
            ))}
          </div>
        )}
        {!borrador && !(tab === "magistrado" ? state.resolucion : state.alegatos[tab as "defensa" | "contraparte"]) && (
          <p className="text-sm text-ink-3">Esperando turno…</p>
        )}
      </div>
    </div>
  );
}

function Plegable({ titulo, abiertoInicial = false, children }: { titulo: string; abiertoInicial?: boolean; children: React.ReactNode }) {
  const [abierto, setAbierto] = useState(abiertoInicial);
  return (
    <div>
      <button className="flex items-center gap-1 text-sm text-ink-2 hover:text-ink" aria-expanded={abierto}
              onClick={() => setAbierto(!abierto)}>
        {titulo}<ChevronDown className={`h-4 w-4 transition-transform ${abierto ? "rotate-180" : ""}`} aria-hidden />
      </button>
      {abierto && <div className="fade-in pt-3">{children}</div>}
    </div>
  );
}

/** Triaje, fuentes consultadas y debate: el «cómo se ha llegado», a un clic. Abierto mientras se analiza. */
export function ProcessDetails({ state, onAbrir }: { state: ConsultaState; onAbrir: AbrirFuente }) {
  const t = state.triage;
  const hayDebate = state.borradores.defensa || state.borradores.contraparte || state.borradores.magistrado
    || state.alegatos.defensa || state.resolucion;
  if (!t && !state.fuentes.length && !hayDebate) return null;
  const terminado = Boolean(state.final);
  return (
    <Plegable titulo={terminado ? "Ver cómo se ha analizado" : "Ver el análisis en curso"} abiertoInicial={!terminado}>
      <div className="space-y-6 rounded-3xl bg-surface p-5">
        {t && (
          <div>
            <p className="eyebrow mb-1">Tu caso</p>
            <p className="text-sm text-ink">
              {t.submateria_descripcion ?? t.submateria_principal}
              <span className="text-ink-2"> · {t.jurisdiccion_principal.replace("_", " ")}
                {t.fecha_hechos && ` · hechos del ${fechaLarga(t.fecha_hechos)}`}
                {t.cuantia_estimada_eur != null && ` · ${t.cuantia_estimada_eur.toLocaleString("es-ES")} €`}</span>
            </p>
            {t.resumen_hechos && <p className="mt-2 text-sm text-ink-2">{t.resumen_hechos}</p>}
          </div>
        )}
        {state.fuentes.length > 0 && (
          <div>
            <p className="mb-2 text-sm font-medium text-ink">Fuentes consultadas</p>
            <Fuentes fuentes={state.fuentes} onAbrir={onAbrir} />
          </div>
        )}
        {hayDebate && (
          <div>
            <p className="mb-2 text-sm font-medium text-ink">Juicio contradictorio</p>
            <Debate state={state} onAbrir={onAbrir} />
          </div>
        )}
      </div>
    </Plegable>
  );
}

// ---------- respuesta ----------

const BANDA_COLOR: Record<Banda, string> = {
  criterio_consolidado_favorable: "bg-success",
  argumento_solido_sin_doctrina: "bg-accent",
  disparidad_de_criterio: "bg-warning",
  riesgo_probatorio_alto: "bg-warning",
  criterio_consolidado_desfavorable: "bg-danger",
  no_determinable: "bg-ink-3",
};

function Postulacion({ p }: { p: Postulacion }) {
  return (
    <div role={p.bloquea_escritos ? "alert" : "note"} className="flex gap-3 text-sm">
      <Info className={`mt-0.5 h-4 w-4 shrink-0 ${p.bloquea_escritos ? "text-danger" : "text-ink-2"}`} aria-hidden />
      <div>
        <p className="font-medium text-ink">
          {p.requiere_abogado ? `Necesitas abogado${p.requiere_procurador ? " y procurador" : ""}` : "Puedes actuar sin abogado"}
        </p>
        <p className="mt-1 text-ink-2">{p.texto_usuario} <span className="text-ink-3">({p.base_legal})</span></p>
        {p.bloquea_escritos && (
          <a className="mt-2 inline-block text-accent hover:underline" target="_blank" rel="noreferrer"
             href="https://www.abogacia.es/servicios/ciudadanos/asistencia-juridica-gratuita/">Buscar asistencia jurídica gratuita</a>
        )}
      </div>
    </div>
  );
}

function Plazos({ plazos }: { plazos: Plazo[] }) {
  if (!plazos.length) return null;
  return (
    <section aria-label="Plazos" className="space-y-3">
      <h3 className="text-base font-medium text-ink">Plazos</h3>
      {plazos.map((p) => {
        const restan = diasNaturalesHasta(p.fecha_limite_segura);
        const ajeno = p.titular === "contraparte";
        const vencido = restan < 0 && !ajeno;
        const urgente = !ajeno && restan >= 0 && restan <= 7;
        return (
          <div key={p.tipo_plazo_id} className="rounded-3xl bg-surface p-5">
            <p className="text-sm text-ink-2">{p.descripcion}</p>
            <p className={`mt-1 text-2xl tabular-nums ${vencido || urgente ? "text-danger" : "text-ink"}`}>
              {fechaLarga(p.fecha_limite_segura)}
            </p>
            <p className="mt-1 text-sm text-ink-2">
              {ajeno
                ? restan < 0 ? "Plazo de la otra parte: ya ha vencido (te favorece)" : `Plazo de la otra parte: quedan ${restan} días`
                : vencido ? `Vencido hace ${-restan} días` : `Quedan ${restan} días naturales${p.dias_habiles_restantes != null ? ` (${p.dias_habiles_restantes} hábiles al hacer el análisis)` : ""}`}
              <span className="text-ink-3"> · desde el {fechaLarga(p.fecha_inicio)}</span>
            </p>
            {p.dia_gracia_hasta && (
              <p className="mt-2 text-xs text-ink-3">
                Día de gracia (solo escritos al juzgado): hasta las 15:00 del {fechaLarga(p.dia_gracia_hasta)}. No lo apures.
              </p>
            )}
            <p className="mt-2 text-xs text-ink-3">{p.base_legal} · cálculo pendiente de validación jurídica</p>
          </div>
        );
      })}
    </section>
  );
}

function Avisos({ avisos }: { avisos: string[] }) {
  if (!avisos.length) return null;
  return (
    <Plegable titulo={`Avisos (${avisos.length})`}>
      <ul className="list-disc space-y-1 pl-5 text-sm text-ink-2">{avisos.map((a, i) => <li key={i}>{a}</li>)}</ul>
    </Plegable>
  );
}

function Acciones({ texto }: { texto: string }) {
  const [copiado, setCopiado] = useState(false);
  return (
    <div className="flex gap-1">
      <button className="icon-btn h-9 w-9" aria-label="Copiar respuesta" title="Copiar"
              onClick={() => navigator.clipboard?.writeText(texto).then(() => {
                setCopiado(true);
                setTimeout(() => setCopiado(false), 1500);
              })}>
        {copiado ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
      </button>
      <button className="icon-btn h-9 w-9" aria-label="Imprimir" title="Imprimir o guardar como PDF" onClick={() => window.print()}>
        <Printer className="h-4 w-4" />
      </button>
    </div>
  );
}

export function Answer({ state, onAbrir }: { state: ConsultaState; onAbrir: AbrirFuente }) {
  const f = state.final;
  if (!f) return null;
  if (f.estado !== "CERTIFICADA" || !f.dictamen) {
    return (
      <section className="fade-in space-y-6" aria-label="Resultado">
        <div className="flex gap-3">
          <AlertCircle className="mt-1 h-5 w-5 shrink-0 text-danger" aria-hidden />
          <div>
            <p className="text-lg text-ink">
              {f.estado === "BLOQUEADA" ? "No puedo darte un dictamen fiable" : "Este caso queda fuera de mi alcance"}
            </p>
            <p className="mt-1 text-sm text-ink-2">{f.mensaje}</p>
          </div>
        </div>
        {f.postulacion && <Postulacion p={f.postulacion} />}
        <Plazos plazos={f.plazos ?? []} />
        <Avisos avisos={f.avisos ?? []} />
        {f.aviso_legal && <p className="text-xs text-ink-3">{f.aviso_legal}</p>}
      </section>
    );
  }
  const d = f.dictamen;
  return (
    <article className="fade-in space-y-8" aria-label="Dictamen">
      {d.respuesta_directa && (
        <p className="text-xl leading-snug text-ink">{d.respuesta_directa}</p>
      )}
      <div>
        <p className="mb-3 flex items-center gap-2 text-sm text-ink-2">
          <span className={`h-2 w-2 rounded-full ${BANDA_COLOR[d.banda_solidez]}`} aria-hidden />
          Solidez: <span className="text-ink">{BANDA_TEXTO[d.banda_solidez]}</span>
        </p>
        <p className="legal whitespace-pre-line">{d.resumen_ciudadano}</p>
      </div>

      {d.pasos_inmediatos.length > 0 && (
        <section>
          <h3 className="mb-2 text-base font-medium text-ink">Qué hacer ahora</h3>
          <ol className="list-decimal space-y-1.5 pl-5 text-[15px] leading-relaxed text-ink">{d.pasos_inmediatos.map((p, i) => <li key={i}>{p}</li>)}</ol>
        </section>
      )}

      {(d.fortalezas.length > 0 || d.riesgos_propios.length > 0) && (
        <div className="grid gap-6 sm:grid-cols-2">
          {d.fortalezas.length > 0 && (
            <section><h3 className="mb-2 text-base font-medium text-ink">A tu favor</h3>
              <ul className="list-disc space-y-1 pl-5 text-sm text-ink-2">{d.fortalezas.map((x, i) => <li key={i}>{x}</li>)}</ul></section>
          )}
          {d.riesgos_propios.length > 0 && (
            <section><h3 className="mb-2 text-base font-medium text-ink">Puntos débiles</h3>
              <ul className="list-disc space-y-1 pl-5 text-sm text-ink-2">{d.riesgos_propios.map((x, i) => <li key={i}>{x}</li>)}</ul></section>
          )}
        </div>
      )}

      <Plazos plazos={d.plazos} />
      {d.postulacion && <Postulacion p={d.postulacion} />}

      <section aria-label="Fundamentos verificados">
        <h3 className="mb-3 text-base font-medium text-ink">Fundamentos verificados</h3>
        <ol className="space-y-4">
          {d.fundamentos.map((fu, i) => (
            <li key={i} className="flex gap-3">
              <button onClick={() => onAbrir(fu.source_id, fu.verbatim_quote)}
                      aria-label={`Abrir fuente ${i + 1}: ${fu.source_id}`}
                      className="mt-0.5 flex h-6 min-w-6 shrink-0 items-center justify-center rounded-full bg-accent-container px-1.5 text-xs font-medium text-on-accent-container hover:opacity-80">
                {i + 1}
              </button>
              <div className="min-w-0">
                <p className="text-[15px] text-ink">{fu.texto}</p>
                <button onClick={() => onAbrir(fu.source_id, fu.verbatim_quote)} className="mt-1 text-left">
                  <span className="font-serif text-[15px] italic leading-relaxed text-ink-2 hover:text-ink">«{fu.verbatim_quote}»</span>
                  <span className="mt-0.5 block text-xs text-ink-3">
                    {fu.source_id} · coincide al {fu.fuzzy_score.toFixed(0)} % con el texto oficial{fu.nli === "NEUTRAL" && " · inferencia no literal"}
                  </span>
                </button>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <Avisos avisos={d.avisos} />
      <div className="flex flex-wrap items-center gap-3 border-t border-outline pt-4">
        <Acciones texto={[d.respuesta_directa, d.resumen_ciudadano].filter(Boolean).join("\n\n")} />
        <p className="min-w-0 flex-1 text-xs text-ink-3">
          {d.aviso_legal} Modelos: {Object.entries(d.modelos_usados).map(([r, m]) => `${r} ${m}`).join(" · ")}.
        </p>
      </div>
    </article>
  );
}
