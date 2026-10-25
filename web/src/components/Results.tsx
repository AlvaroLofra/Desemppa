import { createContext, useContext, useState } from "react";
import { AlertCircle, BookOpen, Square, CalendarPlus, Check, ChevronDown, Copy, FileDown, Info, Loader2, Printer, X } from "lucide-react";
import type { ConsultaState, Rol } from "../lib/useConsulta";
import {
  BANDA_TEXTO, type SelloVerificacion, type AfirmacionVerificada, type Argumento, type Banda, type EntradaAuditoria, type Fuente, type Plazo,
  type Postulacion, type Pregunta,
} from "../lib/types";
import { numerarFuentes } from "../lib/citas";
import { descargar, nombreFichero } from "../lib/descargar";
import { diasNaturalesHasta, fechaLarga } from "../lib/highlight";
import { plazosIcs } from "../lib/ics";
import { MunicipioPicker, type Municipio } from "./MunicipioPicker";
import { DatePicker } from "./ui/DatePicker";
import { HojaDeRuta } from "./HojaDeRuta";
import { VistaProfesional } from "./VistaProfesional";
import type { PasoHoja } from "../lib/api";

export type AbrirFuente = (sourceId: string, quote?: string) => void;

/** true mientras se prepara la impresión o el PDF: todos los plegables se muestran abiertos. */
export const ImprimiendoContext = createContext(false);

const FASES = [
  { label: "Entendiendo tu caso", estados: ["RECIBIDA", "TRIAJE", "ESPERANDO_ACLARACION"] },
  { label: "Buscando en el BOE y en la jurisprudencia", estados: ["INGESTA", "INGESTA_DEGRADADA"] },
  { label: "Enfrentando los argumentos de ambas partes", estados: ["DEBATE"] },
  { label: "Verificando cada cita contra el texto oficial", estados: ["GUARDARRAILES"] },
];

/** Una sola línea de progreso, como el «pensando…» de Gemini. */
export function ProgressLine({ estado, streaming, onDetener }: {
  estado: string | null; streaming: boolean; onDetener?: () => void;
}) {
  const i = FASES.findIndex((f) => estado && f.estados.includes(estado));
  if (!streaming || i < 0) return null;
  return (
    <p className="fade-in flex items-center gap-3 text-sm text-ink-2" aria-live="polite">
      <Loader2 className="h-4 w-4 animate-spin text-accent" aria-hidden />
      {FASES[i].label}…<span className="text-ink-3">Fase {i + 1} de {FASES.length}</span>
      {onDetener && (
        <button className="btn-ghost ml-auto px-3 py-1 text-xs" onClick={onDetener} title="Detener el análisis">
          <Square className="h-3 w-3" aria-hidden />Detener
        </button>
      )}
    </p>
  );
}

export function Clarification({ preguntas, onResponder }: {
  preguntas: Pregunta[];
  onResponder: (r: { pregunta: string; respuesta: string; municipio_ine?: string | null }[]) => void;
}) {
  const [resp, setResp] = useState<Record<string, string>>({});
  const [muni, setMuni] = useState<Municipio | null>(null);
  const NO_SE = "No lo sé";
  const listo = preguntas.every((p) => resp[p.id] === NO_SE || (p.tipo_respuesta === "municipio" ? muni : resp[p.id]?.trim()));
  return (
    <section className="fade-in space-y-4" aria-label="Preguntas aclaratorias">
      <p className="text-base text-ink">Antes de seguir, necesito algunos datos para no equivocarme:</p>
      <p className="-mt-2 text-sm text-ink-2">Cuanto más precisas sean tus respuestas, más fiable será el resultado. Si no sabes algo, dilo: no se supondrá.</p>
      <div className="space-y-4 rounded-3xl bg-surface p-5">
        {preguntas.map((p) => (
          <div key={p.id} className="block">
            <span className="block text-sm text-ink">{p.texto}</span>
            {p.motivo && <span className="mb-2 block text-xs text-ink-3">Por qué lo pregunto: {p.motivo}</span>}
            {!p.motivo && <span className="mb-2 block" />}
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
              <select className="field max-w-sm" value={resp[p.id] ?? ""} aria-label={p.texto}
                      onChange={(e) => setResp({ ...resp, [p.id]: e.target.value })}>
                <option value="">Elige…</option>
                {p.opciones.map((o) => <option key={o}>{o}</option>)}
              </select>
            ) : p.tipo_respuesta === "fecha" ? (
              <DatePicker value={resp[p.id] || null} label={p.texto}
                          onChange={(f) => setResp({ ...resp, [p.id]: f ?? "" })} />
            ) : (
              <input type={p.tipo_respuesta === "importe" ? "number" : "text"} aria-label={p.texto}
                     className="field max-w-sm" value={resp[p.id] ?? ""}
                     onChange={(e) => setResp({ ...resp, [p.id]: e.target.value })} />
            )}
            <button type="button" aria-pressed={resp[p.id] === NO_SE}
                    onClick={() => setResp({ ...resp, [p.id]: resp[p.id] === NO_SE ? "" : NO_SE })}
                    className={`mt-2 rounded-full px-3 py-1 text-xs transition-colors ${
                      resp[p.id] === NO_SE ? "bg-accent-container text-on-accent-container" : "text-ink-2 hover:bg-surface-2"}`}>
              {NO_SE}
            </button>
          </div>
        ))}
        <button className="btn-primary" disabled={!listo} onClick={() => onResponder(preguntas.map((p) => ({
          pregunta: p.texto,
          respuesta: resp[p.id] === NO_SE ? NO_SE
            : p.tipo_respuesta === "municipio" ? `${muni?.nombre} (${muni?.provincia})` : resp[p.id] ?? "",
          municipio_ine: p.tipo_respuesta === "municipio" && resp[p.id] !== NO_SE ? muni?.codigo_ine : undefined,
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
      <div role="tabpanel" tabIndex={0} aria-label="Contenido del debate" className="max-h-[28rem] overflow-auto pt-4 scroll-thin print:max-h-none print:overflow-visible">
        {borrador && !state.final && <pre className="whitespace-pre-wrap font-mono text-xs text-ink-3 print:hidden">{borrador.slice(-4000)}</pre>}
        {(!borrador || state.final) && tab !== "magistrado" && state.alegatos[tab] && (
          <div className="space-y-4">
            <p className="text-sm text-ink-2"><span className="font-medium text-ink">Pretensión:</span> {state.alegatos[tab]!.alegato.pretension}</p>
            <Citas args={state.alegatos[tab]!.alegato.cuestiones.flatMap((q) => q.argumentos)}
                   verif={state.alegatos[tab]!.verificacion} onAbrir={onAbrir} />
          </div>
        )}
        {(!borrador || state.final) && tab === "magistrado" && state.resolucion && (
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
        {(!borrador || state.final) && !(tab === "magistrado" ? state.resolucion : state.alegatos[tab as "defensa" | "contraparte"]) && (
          <p className="text-sm text-ink-3">Esperando turno…</p>
        )}
      </div>
    </div>
  );
}

function Plegable({ titulo, abiertoInicial = false, children }: { titulo: string; abiertoInicial?: boolean; children: React.ReactNode }) {
  const [abierto, setAbierto] = useState(abiertoInicial);
  const imprimiendo = useContext(ImprimiendoContext);
  return (
    <div>
      <button className="flex items-center gap-1 text-sm text-ink-2 hover:text-ink" aria-expanded={abierto}
              onClick={() => setAbierto(!abierto)}>
        {titulo}<ChevronDown className={`h-4 w-4 transition-transform ${abierto ? "rotate-180" : ""}`} aria-hidden />
      </button>
      {(abierto || imprimiendo) && <div className="fade-in pt-3">{children}</div>}
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

export interface AccionesDictamen {
  lectura: boolean;
  onLectura: () => void;
  onExportar: () => void;
  onImprimir: () => void;
}

type Numeracion = Map<string, number>;

/** Superíndices con el número de cada fuente citada; al pulsarlos se abre el pasaje en el visor. */
function Refs({ citas, num, onAbrir }: { citas: AfirmacionVerificada["citas"]; num: Numeracion; onAbrir: AbrirFuente }) {
  const vistas = new Set<string>();
  const unicas = citas.filter((c) => !vistas.has(c.source_id) && Boolean(vistas.add(c.source_id)));
  if (!unicas.length) return null;
  return (
    <>
      {unicas.map((c) => (
        <sup key={c.source_id}>
          <button onClick={() => onAbrir(c.source_id, c.verbatim_quote)}
                  title={`«${c.verbatim_quote}» — ${c.source_id}`}
                  aria-label={`Ver fuente ${num.get(c.source_id)}: ${c.source_id}`}
                  className="ml-0.5 rounded px-0.5 font-sans text-[11px] font-medium text-accent hover:bg-accent-container">
            [{num.get(c.source_id)}]
          </button>
        </sup>
      ))}
    </>
  );
}

function Etiqueta({ a }: { a: AfirmacionVerificada }) {
  if (a.tipo !== "razonamiento") return null;
  return (
    <span title="Inferencia a partir de la fuente citada: la fuente no lo dice literalmente"
          className="ml-1 rounded-md bg-surface-2 px-1.5 py-0.5 align-middle font-sans text-[11px] text-ink-2">
      razonamiento
    </span>
  );
}

/** Texto compuesto solo con afirmaciones verificadas y su referencia; las inferencias se marcan como «razonamiento». */
function TextoVerificado({ afirmaciones, num, onAbrir }: {
  afirmaciones: AfirmacionVerificada[]; num: Numeracion; onAbrir: AbrirFuente;
}) {
  return (
    <>
      {afirmaciones.map((a, i) => (
        <span key={i}>{a.texto}<Refs citas={a.citas} num={num} onAbrir={onAbrir} /><Etiqueta a={a} />{" "}</span>
      ))}
    </>
  );
}

function ListaVerificada({ items, textos, num, onAbrir, ordenada = false, className }: {
  items: AfirmacionVerificada[]; textos: string[]; num: Numeracion; onAbrir: AbrirFuente; ordenada?: boolean;
  className: string;
}) {
  const filas = items.length
    ? items.map((a, i) => <li key={i}>{a.texto}<Refs citas={a.citas} num={num} onAbrir={onAbrir} /><Etiqueta a={a} /></li>)
    : textos.map((x, i) => <li key={i}>{x}</li>);
  return ordenada ? <ol className={className}>{filas}</ol> : <ul className={className}>{filas}</ul>;
}

function BotonCalendario({ plazos, asunto, etiqueta }: { plazos: Plazo[]; asunto: string; etiqueta?: string }) {
  if (!plazos.length) return null;
  const nombre = `plazos-${nombreFichero(asunto)}.ics`;
  return (
    <button className={etiqueta ? "btn-ghost px-3 text-sm" : "icon-btn h-8 w-8"}
            title="Añadir al calendario (.ics) con avisos 7 días y 1 día antes"
            aria-label={etiqueta ?? "Añadir este plazo al calendario"}
            onClick={() => descargar(nombre, plazosIcs(plazos, asunto), "text/calendar")}>
      <CalendarPlus className="h-4 w-4" aria-hidden />{etiqueta}
    </button>
  );
}

/** Plazos que interesa apuntar: los del usuario que no han vencido. */
const apuntables = (plazos: Plazo[]) =>
  plazos.filter((p) => p.titular !== "contraparte" && diasNaturalesHasta(p.fecha_limite_segura) >= 0);

function Plazos({ plazos, asunto }: { plazos: Plazo[]; asunto: string }) {
  if (!plazos.length) return null;
  const todos = apuntables(plazos);
  return (
    <section aria-label="Plazos" className="space-y-3">
      <div className="flex items-center gap-2">
        <h3 className="flex-1 text-base font-medium text-ink">Plazos</h3>
        {todos.length > 1 && (
          <span className="print:hidden"><BotonCalendario plazos={todos} asunto={asunto} etiqueta="Añadir todos al calendario" /></span>
        )}
      </div>
      {plazos.map((p) => {
        const restan = diasNaturalesHasta(p.fecha_limite_segura);
        const ajeno = p.titular === "contraparte";
        const vencido = restan < 0 && !ajeno;
        const urgente = !ajeno && restan >= 0 && restan <= 7;
        return (
          <div key={p.tipo_plazo_id} className="rounded-3xl bg-surface p-5">
            <div className="flex items-start gap-2">
              <p className="flex-1 text-sm text-ink-2">{p.descripcion}</p>
              {todos.includes(p) && <span className="print:hidden"><BotonCalendario plazos={[p]} asunto={asunto} /></span>}
            </div>
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

/** Sello de verificación: versión y huella del texto de cada fuente, para recomprobar el dictamen fuera de la app. */
function Sello({ sello }: { sello: SelloVerificacion }) {
  return (
    <Plegable titulo={`Sello de verificación (${sello.fuentes.length} fuentes)`}>
      <div className="space-y-2 rounded-3xl bg-surface p-5 text-xs text-ink-2">
        <p>Verificado el {new Date(sello.verificado_en).toLocaleString("es-ES")} · {sello.afirmaciones_mostradas} afirmaciones mostradas,
          {" "}{sello.afirmaciones_eliminadas} eliminadas · modelos: {Object.entries(sello.modelos).map(([r, m]) => `${r} ${m}`).join(", ")}</p>
        <ul className="space-y-1">
          {sello.fuentes.map((f) => (
            <li key={f.source_id} className="break-all">
              <span className="text-ink">{f.titulo}</span>{f.version && ` · redacción vigente desde ${f.version}`}
              <span className="block font-mono text-[11px] text-ink-3">SHA-256 {f.sha256}</span>
            </li>
          ))}
        </ul>
        <p className="text-ink-3">Cualquier persona puede descargar el texto oficial, calcular su SHA-256 y comprobar que las citas salen de ese texto exacto.</p>
      </div>
    </Plegable>
  );
}

const ESTADO_AUDITORIA = { aceptada: "Verificada", reclasificada: "Pasa a razonamiento", eliminada: "Eliminada" } as const;

/** «Cómo se ha verificado»: qué hizo el cortafuegos con cada afirmación (docs/cortafuegos.md). */
function Auditoria({ entradas }: { entradas: EntradaAuditoria[] }) {
  const eliminadas = entradas.filter((e) => e.resultado === "eliminada").length;
  return (
    <Plegable titulo={`Cómo se ha verificado (${entradas.length} afirmaciones, ${eliminadas} eliminadas)`}>
      <ul className="divide-y divide-outline rounded-3xl bg-surface px-5">
        {entradas.map((e, i) => (
          <li key={i} className="py-3 text-sm">
            <p className={e.resultado === "eliminada" ? "text-ink-3 line-through" : "text-ink"}>{e.texto}</p>
            <p className="mt-1 text-xs text-ink-2">
              <span className={e.resultado === "eliminada" ? "text-danger" : e.resultado === "reclasificada" ? "text-warning" : "text-success"}>
                {ESTADO_AUDITORIA[e.resultado]}
              </span>
              {" · "}{e.seccion} · {e.tipo_propuesto}{e.tipo_final && e.tipo_final !== e.tipo_propuesto ? ` → ${e.tipo_final}` : ""}
              {e.citas_verificadas.length > 0 && ` · citas verificadas: ${e.citas_verificadas.join(", ")}`}
              {e.nli && ` · inferencia: ${e.nli}`}
            </p>
            {e.motivos.length > 0 && <p className="mt-0.5 text-xs text-ink-3">{e.motivos.join(" · ")}</p>}
          </li>
        ))}
      </ul>
    </Plegable>
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

function Acciones({ texto, acciones }: { texto: string; acciones?: AccionesDictamen }) {
  const [copiado, setCopiado] = useState(false);
  return (
    <div className="flex gap-1 print:hidden">
      <button className="icon-btn h-9 w-9" aria-label="Copiar respuesta" title="Copiar"
              onClick={() => navigator.clipboard?.writeText(texto).then(() => {
                setCopiado(true);
                setTimeout(() => setCopiado(false), 1500);
              })}>
        {copiado ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
      </button>
      {acciones && (
        <>
          <button className="icon-btn h-9 w-9" aria-label="Exportar el expediente en Markdown"
                  title="Exportar el expediente completo (.md) · Alt+E" onClick={acciones.onExportar}>
            <FileDown className="h-4 w-4" />
          </button>
          <button className="icon-btn h-9 w-9" aria-label="Imprimir o guardar el expediente como PDF"
                  title="Imprimir o guardar como PDF (con el proceso y la verificación)" onClick={acciones.onImprimir}>
            <Printer className="h-4 w-4" />
          </button>
          <button className={`icon-btn h-9 w-9 ${acciones.lectura ? "bg-surface-2 text-ink" : ""}`}
                  aria-pressed={acciones.lectura} aria-label="Modo lectura" title="Modo lectura · Alt+L"
                  onClick={acciones.onLectura}>
            <BookOpen className="h-4 w-4" />
          </button>
        </>
      )}
    </div>
  );
}

export function Answer({ state, onAbrir, acciones, hoja = [], profesional = false }: {
  state: ConsultaState; onAbrir: AbrirFuente; acciones?: AccionesDictamen; hoja?: PasoHoja[]; profesional?: boolean;
}) {
  const f = state.final;
  if (!f) return null;
  const asunto = state.triage?.submateria_descripcion ?? state.pregunta?.slice(0, 60) ?? "Consulta";
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
        <Plazos plazos={f.plazos ?? []} asunto={asunto} />
        <HojaDeRuta pasos={hoja} plazos={f.plazos ?? []} postulacion={f.postulacion} relato={state.pregunta ?? ""}
                    titulos={new Map(state.fuentes.map((x) => [x.source_id, x.titulo]))} />
        <Avisos avisos={f.avisos ?? []} />
        {f.aviso_legal && <p className="text-xs text-ink-3">{f.aviso_legal}</p>}
        <div className="border-t border-outline pt-4"><Acciones texto={f.mensaje ?? ""} acciones={acciones} /></div>
      </section>
    );
  }
  const d = f.dictamen;
  const num = numerarFuentes(d);
  const afs = d.afirmaciones ?? [];
  const de = (s: AfirmacionVerificada["seccion"]) => afs.filter((a) => a.seccion === s);
  const titulos = new Map(state.fuentes.map((x) => [x.source_id, x.titulo]));
  const [respuesta, resumen, fortalezas, riesgos, pasos] = [de("respuesta"), de("resumen"), de("fortaleza"), de("riesgo"), de("paso")];
  const hayFortalezas = fortalezas.length > 0 || d.fortalezas.length > 0;
  const hayRiesgos = riesgos.length > 0 || d.riesgos_propios.length > 0;
  return (
    <article className="fade-in space-y-8" aria-label="Dictamen">
      {respuesta.length > 0
        ? <p className="text-xl leading-snug text-ink"><TextoVerificado afirmaciones={respuesta} num={num} onAbrir={onAbrir} /></p>
        : d.respuesta_directa && <p className="text-xl leading-snug text-ink">{d.respuesta_directa}</p>}
      <div>
        <p className="mb-3 flex items-center gap-2 text-sm text-ink-2">
          <span className={`h-2 w-2 rounded-full ${BANDA_COLOR[d.banda_solidez]}`} aria-hidden />
          Solidez: <span className="text-ink">{BANDA_TEXTO[d.banda_solidez]}</span>
        </p>
        {resumen.length > 0
          ? <p className="legal"><TextoVerificado afirmaciones={resumen} num={num} onAbrir={onAbrir} /></p>
          : <p className="legal whitespace-pre-line">{d.resumen_ciudadano}</p>}
      </div>

      {!profesional && state.resolucion && state.resolucion.cuestiones.length > 1 && (
        <section aria-label="Cuestiones de tu caso">
          <h3 className="mb-2 text-base font-medium text-ink">Tu caso tiene {state.resolucion.cuestiones.length} cuestiones</h3>
          <ul className="space-y-1.5 text-[15px] text-ink">
            {state.resolucion.cuestiones.map((q) => (
              <li key={q.id} className="flex gap-2">
                <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${q.estimacion === "DEFENSA" ? "bg-success" : "bg-danger"}`} aria-hidden />
                <span>{q.enunciado} <span className="text-ink-2">— {q.estimacion === "DEFENSA" ? "a tu favor" : "a favor de la otra parte"}</span></span>
              </li>
            ))}
          </ul>
        </section>
      )}
      {profesional && <VistaProfesional state={state} d={d} onAbrir={onAbrir} />}

      {(pasos.length > 0 || d.pasos_inmediatos.length > 0) && (
        <section>
          <h3 className="mb-2 text-base font-medium text-ink">Qué hacer ahora</h3>
          <ListaVerificada items={pasos} textos={d.pasos_inmediatos} num={num} onAbrir={onAbrir} ordenada
                           className="list-decimal space-y-1.5 pl-5 text-[15px] leading-relaxed text-ink" />
        </section>
      )}

      {(hayFortalezas || hayRiesgos) && (
        <div className="grid gap-6 sm:grid-cols-2">
          {hayFortalezas && (
            <section><h3 className="mb-2 text-base font-medium text-ink">A tu favor</h3>
              <ListaVerificada items={fortalezas} textos={d.fortalezas} num={num} onAbrir={onAbrir}
                               className="list-disc space-y-1 pl-5 text-sm text-ink-2" /></section>
          )}
          {hayRiesgos && (
            <section><h3 className="mb-2 text-base font-medium text-ink">Puntos débiles</h3>
              <ListaVerificada items={riesgos} textos={d.riesgos_propios} num={num} onAbrir={onAbrir}
                               className="list-disc space-y-1 pl-5 text-sm text-ink-2" /></section>
          )}
        </div>
      )}

      <Plazos plazos={d.plazos} asunto={asunto} />
      {d.postulacion && <Postulacion p={d.postulacion} />}
      <HojaDeRuta pasos={hoja} dictamen={d} plazos={d.plazos} postulacion={d.postulacion} relato={state.pregunta ?? ""}
                  titulos={titulos} />

      <section aria-label="Fundamentos verificados">
        <h3 className="mb-3 text-base font-medium text-ink">Fundamentos verificados</h3>
        <ol className="space-y-4">
          {d.fundamentos.map((fu, i) => (
            <li key={i} className="flex gap-3">
              <button onClick={() => onAbrir(fu.source_id, fu.verbatim_quote)}
                      aria-label={`Abrir fuente ${num.get(fu.source_id)}: ${fu.source_id}`}
                      className="mt-0.5 flex h-6 min-w-6 shrink-0 items-center justify-center rounded-full bg-accent-container px-1.5 text-xs font-medium text-on-accent-container hover:opacity-80">
                {num.get(fu.source_id)}
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
        {num.size > 0 && (
          <div className="mt-5">
            <p className="eyebrow mb-1">Fuentes citadas</p>
            <ol className="space-y-0.5 text-sm">
              {[...num.entries()].map(([sid, n]) => (
                <li key={sid}>
                  <button className="text-left text-ink-2 hover:text-ink" onClick={() => onAbrir(sid)}>
                    <span className="mr-1.5 font-medium text-accent">[{n}]</span>{titulos.get(sid) ?? sid}
                  </button>
                </li>
              ))}
            </ol>
          </div>
        )}
      </section>

      {d.hechos_determinantes && d.hechos_determinantes.length > 0 && (
        <section aria-label="Lo que podría cambiar el resultado" className="rounded-3xl bg-warning-container/60 p-5">
          <h3 className="mb-1 text-base font-medium text-ink">Lo que podría cambiar el resultado</h3>
          <p className="mb-2 text-sm text-ink-2">No consta en tu consulta. Si puedes, reúne la prueba o vuelve a consultar con el dato:</p>
          <ul className="list-disc space-y-1 pl-5 text-sm text-ink">{d.hechos_determinantes.map((h, i) => <li key={i}>{h}</li>)}</ul>
        </section>
      )}

      <Avisos avisos={d.avisos} />
      {d.auditoria && d.auditoria.length > 0 && <Auditoria entradas={d.auditoria} />}
      {d.sello && <Sello sello={d.sello} />}
      <div className="flex flex-wrap items-center gap-3 border-t border-outline pt-4">
        <Acciones texto={[d.respuesta_directa, d.resumen_ciudadano].filter(Boolean).join("\n\n")} acciones={acciones} />
        <p className="min-w-0 flex-1 text-xs text-ink-3">
          {d.aviso_legal} Modelos usados:{" "}
          {Object.entries(d.modelos_usados).map(([r, m], i) => (
            <span key={r}>
              {i > 0 && " · "}
              {/* «modelo (en lugar de previsto: motivo)»: lo resolvió otro modelo y se destaca */}
              <span className={m.includes("(en lugar de ") ? "font-medium text-warning" : undefined}>{r} {m}</span>
            </span>
          ))}.
        </p>
      </div>
    </article>
  );
}

/** El «cómo se ha llegado» para imprimir o guardar como PDF: en prosa y con sus citas, sin pestañas ni texto en
 *  crudo de los modelos. Solo se ve al imprimir. */
export function ProcesoImpresion({ state }: { state: ConsultaState }) {
  const t = state.triage;
  const r = state.resolucion;
  if (!state.final || (!t && !r && !state.alegatos.defensa)) return null;
  const cita = (c: { source_id: string; verbatim_quote: string }, k: number) => (
    <p key={k} className="ml-4 font-serif text-[13px] italic text-ink-2">«{c.verbatim_quote}» <span className="not-italic text-ink-3">({c.source_id})</span></p>
  );
  return (
    <section aria-label="Cómo se ha analizado" className="hidden space-y-5 border-t border-outline pt-6 print:block">
      <h2 className="text-lg font-medium text-ink">Cómo se ha analizado</h2>
      {t && (
        <div className="text-sm text-ink">
          <p className="font-medium">Tu caso</p>
          <p>{t.submateria_descripcion ?? t.submateria_principal} · {t.jurisdiccion_principal.replace("_", " ")}
            {t.fecha_hechos && ` · hechos del ${fechaLarga(t.fecha_hechos)}`}</p>
          {t.resumen_hechos && <p className="text-ink-2">{t.resumen_hechos}</p>}
        </div>
      )}
      {r && (
        <div className="space-y-3 text-sm text-ink">
          <p className="font-medium">Razonamiento del Magistrado</p>
          {r.cuestiones.map((q) => (
            <div key={q.id} className="break-inside-avoid">
              <p>{q.enunciado} — <span className="font-medium">da la razón a {q.estimacion === "DEFENSA" ? "tu posición" : "la otra parte"}</span></p>
              {q.fundamentos.map((f, i) => (
                <div key={i} className="mt-1"><p className="text-ink-2">{f.afirmacion}</p>{f.citas.map(cita)}</div>
              ))}
            </div>
          ))}
        </div>
      )}
      {(["defensa", "contraparte"] as const).map((rol) => {
        const al = state.alegatos[rol]?.alegato;
        if (!al) return null;
        return (
          <div key={rol} className="space-y-1 text-sm text-ink">
            <p className="font-medium">{rol === "defensa" ? "Argumentos a tu favor (defensa)" : "Argumentos de la otra parte"}</p>
            <p className="text-ink-2">Pretensión: {al.pretension}</p>
            <ul className="list-disc pl-5 text-ink-2">
              {al.cuestiones.flatMap((q) => q.argumentos).map((a, i) => <li key={i}>{a.afirmacion}</li>)}
            </ul>
          </div>
        );
      })}
      {state.fuentes.length > 0 && (
        <div className="text-sm text-ink">
          <p className="font-medium">Fuentes consultadas</p>
          <ul className="list-disc pl-5 text-ink-2">{state.fuentes.map((f) => <li key={f.source_id}>{f.titulo} ({f.source_id})</li>)}</ul>
        </div>
      )}
    </section>
  );
}
