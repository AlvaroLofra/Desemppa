import { useState } from "react";
import {
  AlertTriangle, BookOpen, CalendarClock, CheckCircle2, ChevronDown, FileText, Gavel, Landmark, Loader2,
  ShieldAlert, ShieldCheck, Swords, UserRound, XCircle,
} from "lucide-react";
import type { ConsultaState, Rol } from "../lib/useConsulta";
import { BANDA_TEXTO, type Argumento, type Banda, type Fuente, type Plazo, type Postulacion, type Pregunta } from "../lib/types";
import { diasNaturalesHasta, fechaLarga } from "../lib/highlight";
import { MunicipioPicker, type Municipio } from "./MunicipioPicker";

export type AbrirFuente = (sourceId: string, quote?: string) => void;

const FASES = [
  { id: "TRIAJE", label: "Triaje", estados: ["RECIBIDA", "TRIAJE", "ESPERANDO_ACLARACION"] },
  { id: "INGESTA", label: "Fuentes", estados: ["INGESTA", "INGESTA_DEGRADADA"] },
  { id: "DEBATE", label: "Juicio contradictorio", estados: ["DEBATE"] },
  { id: "GUARDARRAILES", label: "Verificación", estados: ["GUARDARRAILES"] },
];

export function PhaseStepper({ estado, streaming }: { estado: string | null; streaming: boolean }) {
  const actual = FASES.findIndex((f) => estado && f.estados.includes(estado));
  const terminado = estado && ["CERTIFICADA", "BLOQUEADA", "FUERA_DE_ALCANCE"].includes(estado);
  return (
    <ol className="flex flex-wrap items-center gap-2 text-xs" aria-label="Progreso">
      {FASES.map((f, i) => {
        const done = terminado || i < actual;
        const active = !terminado && i === actual;
        return (
          <li key={f.id} className="flex items-center gap-2">
            <span className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 ${
              done ? "border-emerald-700/60 text-emerald-300" : active ? "border-amber-500/70 text-amber-200" : "border-slate-800 text-slate-500"
            }`}>
              {done ? <CheckCircle2 className="h-3.5 w-3.5" /> : active && streaming ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <span className="h-1.5 w-1.5 rounded-full bg-current" />}
              {f.label}
            </span>
            {i < FASES.length - 1 && <span className="h-px w-4 bg-slate-800" />}
          </li>
        );
      })}
    </ol>
  );
}

export function TriageCard({ state }: { state: ConsultaState }) {
  const t = state.triage;
  if (!t) return null;
  return (
    <section className="card p-4" aria-label="Triaje">
      <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
        <Landmark className="h-4 w-4 text-amber-400" aria-hidden />
        <span className="chip">{t.jurisdiccion_principal.replace("_", " ")}</span>
        <span className="chip">{t.submateria_descripcion ?? t.submateria_principal}</span>
        {t.fecha_hechos && <span className="chip">hechos: {t.fecha_hechos}</span>}
        {t.cuantia_estimada_eur != null && <span className="chip">{t.cuantia_estimada_eur.toLocaleString("es-ES")} €</span>}
      </div>
      {t.resumen_hechos && <p className="mt-2 text-sm text-slate-300">{t.resumen_hechos}</p>}
    </section>
  );
}

export function ClarificationForm({ preguntas, onResponder }: {
  preguntas: Pregunta[];
  onResponder: (r: { pregunta: string; respuesta: string; municipio_ine?: string | null }[]) => void;
}) {
  const [resp, setResp] = useState<Record<string, string>>({});
  const [muni, setMuni] = useState<Municipio | null>(null);
  const listo = preguntas.every((p) => (p.tipo_respuesta === "municipio" ? muni : resp[p.id]?.trim()));
  return (
    <section className="card border-amber-600/40 p-4" aria-label="Preguntas aclaratorias">
      <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-amber-200">
        <AlertTriangle className="h-4 w-4" />Necesito algunos datos para no equivocarme
      </h3>
      <div className="space-y-3">
        {preguntas.map((p) => (
          <label key={p.id} className="block text-sm">
            <span className="mb-1 block text-slate-300">{p.texto}</span>
            {p.tipo_respuesta === "municipio" ? (
              <MunicipioPicker value={muni} onChange={setMuni} compact />
            ) : p.tipo_respuesta === "si_no" ? (
              <div className="flex gap-2">
                {["Sí", "No"].map((o) => (
                  <button key={o} onClick={() => setResp({ ...resp, [p.id]: o })}
                          className={`btn border ${resp[p.id] === o ? "border-amber-500 text-amber-200" : "border-slate-700"}`}>{o}</button>
                ))}
              </div>
            ) : p.opciones?.length ? (
              <select className="rounded-lg border border-slate-700 bg-slate-900 px-2 py-1.5"
                      value={resp[p.id] ?? ""} onChange={(e) => setResp({ ...resp, [p.id]: e.target.value })}>
                <option value="">Elige…</option>
                {p.opciones.map((o) => <option key={o}>{o}</option>)}
              </select>
            ) : (
              <input type={p.tipo_respuesta === "fecha" ? "date" : p.tipo_respuesta === "importe" ? "number" : "text"}
                     className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 outline-none focus:border-amber-500"
                     value={resp[p.id] ?? ""} onChange={(e) => setResp({ ...resp, [p.id]: e.target.value })} />
            )}
          </label>
        ))}
      </div>
      <button className="btn-primary mt-4" disabled={!listo} onClick={() => onResponder(preguntas.map((p) => ({
        pregunta: p.texto,
        respuesta: p.tipo_respuesta === "municipio" ? `${muni?.nombre} (${muni?.provincia})` : resp[p.id] ?? "",
        municipio_ine: p.tipo_respuesta === "municipio" ? muni?.codigo_ine : undefined,
      })))}>Continuar análisis</button>
    </section>
  );
}

const ICONO_FUENTE = { boe: BookOpen, sentencia: Gavel, convenio: FileText, adjunto: FileText } as const;

export function SourcesList({ fuentes, onAbrir }: { fuentes: Fuente[]; onAbrir: AbrirFuente }) {
  if (!fuentes.length) return null;
  return (
    <section aria-label="Fuentes consultadas" className="flex flex-wrap gap-2">
      {fuentes.map((f) => {
        const Icon = ICONO_FUENTE[f.tipo] ?? FileText;
        return (
          <button key={f.source_id} className="chip hover:border-amber-500/60" title={f.extracto} onClick={() => onAbrir(f.source_id)}>
            <Icon className="h-3 w-3 text-amber-400" aria-hidden />{f.titulo}
          </button>
        );
      })}
    </section>
  );
}

function Argumentos({ args, verif, onAbrir }: { args: Argumento[]; verif?: { ok: boolean }[][]; onAbrir: AbrirFuente }) {
  return (
    <ul className="space-y-3">
      {args.map((a, i) => (
        <li key={i} className="text-sm">
          <p className="text-slate-200">{a.afirmacion}</p>
          {a.citas.map((c, j) => {
            const ok = verif?.[i]?.[j]?.ok;
            return (
              <button key={j} onClick={() => onAbrir(c.source_id, c.verbatim_quote)}
                      className="mt-1 block w-full rounded-md border-l-2 border-slate-700 bg-slate-950/40 px-3 py-1.5 text-left hover:border-amber-500">
                <span className="legal italic">«{c.verbatim_quote}»</span>
                <span className="mt-0.5 flex items-center gap-1 text-[11px] text-slate-500">
                  {ok === false ? <XCircle className="h-3 w-3 text-rose-400" /> : ok ? <CheckCircle2 className="h-3 w-3 text-emerald-400" /> : null}
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

export function DebateTabs({ state, onAbrir }: { state: ConsultaState; onAbrir: AbrirFuente }) {
  const [tab, setTab] = useState<Rol>("magistrado");
  const hay = state.borradores.defensa || state.borradores.contraparte || state.borradores.magistrado
    || state.alegatos.defensa || state.resolucion;
  if (!hay) return null;
  const tabs: { id: Rol; label: string; icon: typeof Swords }[] = [
    { id: "defensa", label: "Argumentos de Defensa", icon: UserRound },
    { id: "contraparte", label: "Ataque de la Contraparte", icon: Swords },
    { id: "magistrado", label: "Resolución del Magistrado", icon: Gavel },
  ];
  const borrador = state.borradores[tab];
  return (
    <section className="card" aria-label="Juicio contradictorio">
      <div role="tablist" className="flex overflow-x-auto border-b border-slate-800 scroll-thin">
        {tabs.map(({ id, label, icon: Icon }) => {
          const vivo = Boolean(state.borradores[id]);
          return (
            <button key={id} role="tab" aria-selected={tab === id} onClick={() => setTab(id)}
                    className={`flex shrink-0 items-center gap-2 px-4 py-2.5 text-sm ${tab === id ? "border-b-2 border-amber-500 text-amber-200" : "text-slate-400 hover:text-slate-200"}`}>
              <Icon className="h-4 w-4" />{label}{vivo && <Loader2 className="h-3 w-3 animate-spin" />}
            </button>
          );
        })}
      </div>
      <div role="tabpanel" className="max-h-[28rem] overflow-auto p-4 scroll-thin">
        {borrador && <pre className="whitespace-pre-wrap font-mono text-xs text-slate-500">{borrador.slice(-4000)}</pre>}
        {!borrador && tab !== "magistrado" && state.alegatos[tab] && (
          <div className="space-y-4">
            <p className="text-sm text-slate-400"><b className="text-slate-200">Pretensión:</b> {state.alegatos[tab]!.alegato.pretension}</p>
            <Argumentos args={state.alegatos[tab]!.alegato.cuestiones.flatMap((q) => q.argumentos)}
                        verif={state.alegatos[tab]!.verificacion} onAbrir={onAbrir} />
          </div>
        )}
        {!borrador && tab === "magistrado" && state.resolucion && (
          <div className="space-y-5">
            {state.resolucion.cuestiones.map((q) => (
              <div key={q.id}>
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <span className="text-sm font-semibold text-slate-100">{q.enunciado}</span>
                  <span className={`chip ${q.estimacion === "DEFENSA" ? "border-emerald-700 text-emerald-300" : "border-rose-800 text-rose-300"}`}>
                    estima: {q.estimacion === "DEFENSA" ? "tu posición" : "la contraparte"}
                  </span>
                </div>
                <Argumentos args={q.fundamentos} onAbrir={onAbrir} />
              </div>
            ))}
          </div>
        )}
        {!borrador && !(tab === "magistrado" ? state.resolucion : state.alegatos[tab as "defensa" | "contraparte"]) && (
          <p className="text-sm text-slate-500">Esperando turno…</p>
        )}
      </div>
    </section>
  );
}

const BANDA_ESTILO: Record<Banda, string> = {
  criterio_consolidado_favorable: "border-emerald-600 bg-emerald-950/40 text-emerald-200",
  argumento_solido_sin_doctrina: "border-sky-600 bg-sky-950/40 text-sky-200",
  disparidad_de_criterio: "border-amber-600 bg-amber-950/40 text-amber-200",
  riesgo_probatorio_alto: "border-orange-600 bg-orange-950/40 text-orange-200",
  criterio_consolidado_desfavorable: "border-rose-600 bg-rose-950/40 text-rose-200",
  no_determinable: "border-slate-600 bg-slate-900 text-slate-300",
};

export function BandaBadge({ banda }: { banda: Banda }) {
  return <span className={`inline-flex rounded-lg border px-3 py-1 text-sm font-medium ${BANDA_ESTILO[banda]}`}>{BANDA_TEXTO[banda]}</span>;
}

export function PostulacionBanner({ p }: { p: Postulacion }) {
  return (
    <div role={p.bloquea_escritos ? "alert" : "note"} className={`flex gap-3 rounded-xl border p-4 text-sm ${
      p.bloquea_escritos ? "border-rose-700 bg-rose-950/40 text-rose-100" : "border-slate-700 bg-slate-900/60 text-slate-300"}`}>
      {p.bloquea_escritos ? <ShieldAlert className="h-5 w-5 shrink-0 text-rose-400" /> : <ShieldCheck className="h-5 w-5 shrink-0 text-emerald-400" />}
      <div>
        <p className="font-medium">{p.requiere_abogado ? `Necesitas abogado${p.requiere_procurador ? " y procurador" : ""}` : "Puedes actuar sin abogado"}</p>
        <p className="mt-1">{p.texto_usuario} <span className="text-slate-500">({p.base_legal})</span></p>
        {p.bloquea_escritos && (
          <a className="mt-2 inline-block text-amber-300 underline" target="_blank" rel="noreferrer"
             href="https://www.abogacia.es/servicios/ciudadanos/asistencia-juridica-gratuita/">Buscar asistencia jurídica gratuita</a>
        )}
      </div>
    </div>
  );
}

export function DeadlineTimeline({ plazos }: { plazos: Plazo[] }) {
  if (!plazos.length) return null;
  return (
    <section className="card p-4" aria-label="Plazos">
      <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-100"><CalendarClock className="h-4 w-4 text-amber-400" />Plazos</h3>
      <ul className="space-y-5">
        {plazos.map((p) => {
          const total = Math.max(1, diasNaturalesHasta(p.fecha_limite_segura, new Date(`${p.fecha_inicio}T00:00:00`)));
          const restan = diasNaturalesHasta(p.fecha_limite_segura);
          const pct = Math.min(100, Math.max(0, ((total - restan) / total) * 100));
          const ajeno = p.titular === "contraparte";
          const vencido = restan < 0 && !ajeno;
          const urgente = !ajeno && restan >= 0 && restan <= 5;
          return (
            <li key={p.tipo_plazo_id}>
              <div className="flex flex-wrap items-baseline justify-between gap-2 text-sm">
                <span className="text-slate-200">{p.descripcion}</span>
                <span className={vencido ? "text-rose-400" : urgente ? "text-orange-300" : "text-slate-400"}>
                  {ajeno
                    ? restan < 0 ? "plazo de la otra parte: ya vencido (te favorece)" : `plazo de la otra parte: quedan ${restan} días`
                    : vencido ? `vencido hace ${-restan} días` : `quedan ${restan} días naturales${p.dias_habiles_restantes != null ? ` (${p.dias_habiles_restantes} hábiles)` : ""}`}
                </span>
              </div>
              <div className="relative mt-2 h-2 rounded-full bg-slate-800">
                <div className={`h-2 rounded-full ${ajeno ? "bg-sky-600" : vencido ? "bg-rose-600" : urgente ? "bg-orange-500" : "bg-amber-500"}`} style={{ width: `${pct}%` }} />
              </div>
              <div className="mt-1.5 flex flex-wrap justify-between gap-2 text-xs text-slate-500">
                <span>Desde {p.fecha_inicio}</span>
                <span className={`font-medium ${ajeno ? "text-sky-300" : "text-rose-300"}`}>{ajeno ? "Vence para la otra parte" : "Fecha límite segura"}: {fechaLarga(p.fecha_limite_segura)}</span>
              </div>
              {p.dia_gracia_hasta && (
                <p className="mt-1 text-[11px] text-slate-600">
                  Día de gracia (solo escritos al juzgado): hasta las 15:00 del {fechaLarga(p.dia_gracia_hasta)}. No lo apures.
                </p>
              )}
              <p className="mt-1 text-[11px] text-slate-600">{p.base_legal} · cálculo pendiente de validación jurídica</p>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export function Avisos({ avisos }: { avisos: string[] }) {
  const [open, setOpen] = useState(false);
  if (!avisos.length) return null;
  return (
    <section className="card">
      <button className="flex w-full items-center gap-2 px-4 py-3 text-sm text-slate-300" aria-expanded={open} onClick={() => setOpen(!open)}>
        <AlertTriangle className="h-4 w-4 text-amber-400" />Avisos ({avisos.length})
        <ChevronDown className={`ml-auto h-4 w-4 transition ${open ? "rotate-180" : ""}`} />
      </button>
      {open && <ul className="list-disc space-y-1 px-8 pb-4 text-xs text-slate-400">{avisos.map((a, i) => <li key={i}>{a}</li>)}</ul>}
    </section>
  );
}

export function FinalView({ state, onAbrir }: { state: ConsultaState; onAbrir: AbrirFuente }) {
  const f = state.final;
  if (!f) return null;
  if (f.estado !== "CERTIFICADA" || !f.dictamen) {
    return (
      <section className="space-y-4">
        <div className="card border-slate-700 p-4 text-sm text-slate-300">
          <p className="flex items-center gap-2 font-medium text-slate-100"><XCircle className="h-4 w-4 text-rose-400" />
            {f.estado === "BLOQUEADA" ? "Dictamen bloqueado por los controles de verificación" : "Fuera de alcance"}</p>
          <p className="mt-2">{f.mensaje}</p>
        </div>
        {f.postulacion && <PostulacionBanner p={f.postulacion} />}
        <DeadlineTimeline plazos={f.plazos ?? []} />
        <Avisos avisos={f.avisos ?? []} />
        {f.aviso_legal && <p className="text-[11px] text-slate-600">{f.aviso_legal}</p>}
      </section>
    );
  }
  const d = f.dictamen;
  return (
    <section className="space-y-4" aria-label="Dictamen">
      <div className="card p-5">
        <div className="mb-3 flex flex-wrap items-center gap-3">
          <BandaBadge banda={d.banda_solidez} />
          <span className="text-xs text-slate-500">Solidez argumental · sin porcentajes (art. 403 CP)</span>
        </div>
        <p className="legal whitespace-pre-line">{d.resumen_ciudadano}</p>
        {d.pasos_inmediatos.length > 0 && (
          <div className="mt-4">
            <h4 className="text-sm font-semibold text-slate-100">Qué hacer ahora</h4>
            <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm text-slate-300">{d.pasos_inmediatos.map((p, i) => <li key={i}>{p}</li>)}</ol>
          </div>
        )}
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          {d.fortalezas.length > 0 && (
            <div><h4 className="text-xs font-semibold uppercase tracking-wide text-emerald-400">A tu favor</h4>
              <ul className="mt-1 list-disc pl-5 text-sm text-slate-300">{d.fortalezas.map((x, i) => <li key={i}>{x}</li>)}</ul></div>
          )}
          {d.riesgos_propios.length > 0 && (
            <div><h4 className="text-xs font-semibold uppercase tracking-wide text-orange-400">Puntos débiles</h4>
              <ul className="mt-1 list-disc pl-5 text-sm text-slate-300">{d.riesgos_propios.map((x, i) => <li key={i}>{x}</li>)}</ul></div>
          )}
        </div>
      </div>
      {d.postulacion && <PostulacionBanner p={d.postulacion} />}
      <DeadlineTimeline plazos={d.plazos} />
      <div className="card p-4">
        <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-100"><ShieldCheck className="h-4 w-4 text-emerald-400" />Fundamentos verificados</h3>
        <ul className="space-y-3">
          {d.fundamentos.map((fu, i) => (
            <li key={i} className="text-sm">
              <p className="text-slate-200">{fu.texto}</p>
              <button onClick={() => onAbrir(fu.source_id, fu.verbatim_quote)}
                      className="mt-1 block w-full rounded-md border-l-2 border-emerald-700 bg-slate-950/40 px-3 py-1.5 text-left hover:border-amber-500">
                <span className="legal italic">«{fu.verbatim_quote}»</span>
                <span className="mt-0.5 block text-[11px] text-slate-500">
                  {fu.source_id} · coincidencia {fu.fuzzy_score.toFixed(0)}% con el texto oficial{fu.nli === "NEUTRAL" && " · inferencia no literal"}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </div>
      <Avisos avisos={d.avisos} />
      <p className="text-[11px] text-slate-600">
        {d.aviso_legal} Modelos: {Object.entries(d.modelos_usados).map(([r, m]) => `${r}=${m}`).join(", ")}.
      </p>
    </section>
  );
}
