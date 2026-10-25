import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { CalendarDays, ChevronDown, ChevronLeft, ChevronRight } from "lucide-react";
import {
  DIAS_SEMANA, DIAS_SEMANA_LARGOS, MESES, cuadricula, dentro, diaSemana, escribirDMA, hoyISO, leerDMA, partes,
  sumarDias, sumarMeses,
} from "../../lib/calendario";

/** Selector de fecha al estilo de Google (Material 3): campo dd/mm/aaaa que admite escribir, y calendario
 *  emergente con lunes primero, vista de años, «Hoy» y teclado completo. `value`/`onChange` en «AAAA-MM-DD». */
export function DatePicker({ value, onChange, min, max, label = "Fecha" }: {
  value: string | null;
  onChange: (iso: string | null) => void;
  min?: string;
  max?: string;
  label?: string;
}) {
  const [texto, setTexto] = useState(escribirDMA(value));
  const [abierto, setAbierto] = useState(false);
  const [vistaAnios, setVistaAnios] = useState(false);
  const [foco, setFoco] = useState(value ?? hoyISO());
  const [error, setError] = useState<string | null>(null);
  const raiz = useRef<HTMLDivElement>(null);
  const rejilla = useRef<HTMLDivElement>(null);
  const idDialogo = useId();
  const hoy = hoyISO();

  useEffect(() => { setTexto(escribirDMA(value)); }, [value]);

  useEffect(() => {
    if (!abierto) return;
    const fuera = (e: MouseEvent) => { if (!raiz.current?.contains(e.target as Node)) setAbierto(false); };
    document.addEventListener("mousedown", fuera);
    return () => document.removeEventListener("mousedown", fuera);
  }, [abierto]);

  useEffect(() => {
    if (abierto && !vistaAnios) rejilla.current?.querySelector<HTMLButtonElement>(`[data-fecha="${foco}"]`)?.focus();
  }, [abierto, vistaAnios, foco]);

  const elegir = (f: string) => {
    if (!dentro(f, min, max)) return;
    onChange(f);
    setError(null);
    setAbierto(false);
  };

  const confirmarTexto = () => {
    if (!texto.trim()) { onChange(null); setError(null); return; }
    const f = leerDMA(texto);
    if (!f) { setError("Escribe la fecha como día/mes/año, por ejemplo 25/10/2026"); return; }
    if (!dentro(f, min, max)) { setError("Esa fecha está fuera del intervalo permitido"); return; }
    setError(null);
    onChange(f);
    setFoco(f);
  };

  const teclaDia = (e: KeyboardEvent) => {
    const mover: Record<string, () => string> = {
      ArrowLeft: () => sumarDias(foco, -1), ArrowRight: () => sumarDias(foco, 1),
      ArrowUp: () => sumarDias(foco, -7), ArrowDown: () => sumarDias(foco, 7),
      PageUp: () => sumarMeses(foco, e.shiftKey ? -12 : -1), PageDown: () => sumarMeses(foco, e.shiftKey ? 12 : 1),
      Home: () => sumarDias(foco, -diaSemana(foco)), End: () => sumarDias(foco, 6 - diaSemana(foco)),
    };
    if (mover[e.key]) { e.preventDefault(); setFoco(mover[e.key]()); }
    else if (e.key === "Escape") { e.preventDefault(); setAbierto(false); }
  };

  const { anio, mes } = partes(foco);
  const anios = Array.from({ length: 121 }, (_, i) => anio - 100 + i).filter((a) =>
    (!min || a >= partes(min).anio) && (!max || a <= partes(max).anio));

  return (
    <div ref={raiz} className="relative max-w-sm">
      <div className={`flex items-center rounded-lg border bg-bg pr-1 transition-colors focus-within:border-accent ${error ? "border-danger" : "border-outline"}`}>
        <input value={texto} inputMode="numeric" placeholder="dd/mm/aaaa" aria-label={label} aria-invalid={Boolean(error)}
               onChange={(e) => setTexto(e.target.value)} onBlur={confirmarTexto}
               onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); confirmarTexto(); } if (e.key === "ArrowDown" && e.altKey) setAbierto(true); }}
               className="min-w-0 flex-1 bg-transparent px-3 py-2 text-sm text-ink outline-none placeholder:text-ink-3" />
        <button type="button" className="icon-btn h-9 w-9" aria-label="Abrir calendario" aria-haspopup="dialog"
                aria-expanded={abierto} aria-controls={idDialogo}
                onClick={() => { setFoco(value ?? (dentro(hoy, min, max) ? hoy : min ?? max ?? hoy)); setVistaAnios(false); setAbierto((v) => !v); }}>
          <CalendarDays className="h-5 w-5" />
        </button>
      </div>
      {error && <p className="mt-1 text-xs text-danger" role="alert">{error}</p>}

      {abierto && (
        <div id={idDialogo} role="dialog" aria-label={`Elegir ${label.toLowerCase()}`}
             className="fade-in absolute left-0 z-50 mt-2 w-[328px] rounded-[28px] bg-surface p-3 shadow-float">
          <div className="flex items-center gap-1 px-1 pb-2">
            <button type="button" className="btn-ghost px-3 py-1.5 text-sm text-ink" aria-label={`${MESES[mes]} de ${anio}: elegir año`}
                    onClick={() => setVistaAnios((v) => !v)}>
              <span className="capitalize">{MESES[mes]}</span> {anio}
              <ChevronDown className={`h-4 w-4 transition-transform ${vistaAnios ? "rotate-180" : ""}`} aria-hidden />
            </button>
            {!vistaAnios && (
              <span className="ml-auto flex">
                <button type="button" className="icon-btn h-9 w-9" aria-label="Mes anterior" onClick={() => setFoco(sumarMeses(foco, -1))}>
                  <ChevronLeft className="h-5 w-5" />
                </button>
                <button type="button" className="icon-btn h-9 w-9" aria-label="Mes siguiente" onClick={() => setFoco(sumarMeses(foco, 1))}>
                  <ChevronRight className="h-5 w-5" />
                </button>
              </span>
            )}
          </div>

          {vistaAnios ? (
            <div className="grid max-h-[264px] grid-cols-3 gap-1 overflow-auto p-1 scroll-thin" role="listbox" aria-label="Año">
              {anios.map((a) => (
                <button key={a} type="button" role="option" aria-selected={a === anio}
                        ref={(el) => { if (a === anio) el?.scrollIntoView({ block: "center" }); }}
                        onClick={() => { setFoco(sumarMeses(foco, (a - anio) * 12)); setVistaAnios(false); }}
                        className={`rounded-full py-2 text-sm ${a === anio ? "bg-accent text-on-accent" : "text-ink hover:bg-surface-2"}`}>
                  {a}
                </button>
              ))}
            </div>
          ) : (
            <div ref={rejilla} role="grid" aria-label={`${MESES[mes]} de ${anio}`} onKeyDown={teclaDia}>
              <div role="row" className="grid grid-cols-7">
                {DIAS_SEMANA.map((d, i) => (
                  <span key={d} role="columnheader" aria-label={DIAS_SEMANA_LARGOS[i]} className="py-1 text-center text-xs text-ink-2">{d}</span>
                ))}
              </div>
              {Array.from({ length: 6 }, (_, w) => (
                <div key={w} role="row" className="grid grid-cols-7">
                  {cuadricula(anio, mes).slice(w * 7, w * 7 + 7).map((f) => {
                    const p = partes(f);
                    const otroMes = p.mes !== mes;
                    const elegido = f === value;
                    const permitido = dentro(f, min, max);
                    return (
                      <span key={f} role="gridcell" aria-selected={elegido} className="flex justify-center py-0.5">
                        <button type="button" data-fecha={f} tabIndex={f === foco ? 0 : -1} disabled={!permitido}
                                aria-label={`${DIAS_SEMANA_LARGOS[diaSemana(f)]} ${p.dia} de ${MESES[p.mes]} de ${p.anio}${f === hoy ? ", hoy" : ""}`}
                                onClick={() => elegir(f)} onFocus={() => setFoco(f)}
                                className={`h-10 w-10 rounded-full text-sm tabular-nums transition-colors disabled:opacity-30 ${
                                  elegido ? "bg-accent font-medium text-on-accent"
                                    : f === hoy ? "border border-accent text-accent hover:bg-accent-container"
                                      : otroMes ? "text-ink-3 hover:bg-surface-2" : "text-ink hover:bg-surface-2"}`}>
                          {p.dia}
                        </button>
                      </span>
                    );
                  })}
                </div>
              ))}
            </div>
          )}

          <div className="flex items-center gap-1 px-1 pt-2">
            <button type="button" className="btn-ghost px-3 py-1.5 text-sm" disabled={!dentro(hoy, min, max)} onClick={() => elegir(hoy)}>Hoy</button>
            {value && <button type="button" className="btn-ghost px-3 py-1.5 text-sm" onClick={() => { onChange(null); setAbierto(false); }}>Borrar</button>}
            <button type="button" className="btn-ghost ml-auto px-3 py-1.5 text-sm text-accent" onClick={() => setAbierto(false)}>Cerrar</button>
          </div>
        </div>
      )}
    </div>
  );
}
