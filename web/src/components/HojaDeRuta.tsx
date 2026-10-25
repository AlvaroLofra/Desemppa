import { useEffect, useState } from "react";
import { Check, ChevronDown, Copy, FileText, Printer } from "lucide-react";
import { api, type PasoHoja } from "../lib/api";
import { descargar, nombreFichero } from "../lib/descargar";
import { escritoComoDoc, generarEscrito, puedeGenerarEscrito, type Escrito } from "../lib/escritos";
import { diasNaturalesHasta, fechaLarga } from "../lib/highlight";
import type { Dictamen, Plazo, Postulacion } from "../lib/types";
import { Dialog } from "./ui/primitives";

/** Pasos de la hoja de ruta (se cargan una vez por submateria). */
export function useHojaDeRuta(submateria: string | null | undefined, fechaHechos?: string | null): PasoHoja[] {
  const [pasos, setPasos] = useState<PasoHoja[]>([]);
  useEffect(() => {
    setPasos([]);
    // La fecha de los hechos decide qué pasos aplican (una redacción nueva no rige hechos anteriores).
    if (submateria) api.hojaDeRuta(submateria, fechaHechos).then(setPasos).catch(() => setPasos([]));
  }, [submateria, fechaHechos]);
  return pasos;
}

export function quienTexto(p: PasoHoja, postulacion?: Postulacion | null): string {
  if (p.quien === "tu") return "Lo puedes hacer tú";
  if (p.quien === "abogado") return "Necesitas abogado";
  if (!postulacion) return "Depende de la cuantía: mira «Abogado y procurador»";
  return postulacion.requiere_abogado ? "Necesitas abogado" : "Lo puedes hacer tú";
}

function EscritoDialog({ escrito, onClose }: { escrito: Escrito; onClose: () => void }) {
  const [texto, setTexto] = useState(escrito.texto);
  const [copiado, setCopiado] = useState(false);
  const final = { ...escrito, texto };
  const base = nombreFichero(escrito.titulo);
  const imprimir = () => {
    const w = window.open("", "_blank", "noopener=no");
    if (!w) return;
    w.document.write(escritoComoDoc(final));
    w.document.close();
    w.print();
  };
  return (
    <Dialog titulo={escrito.titulo} onClose={onClose} amplio>
      <p className="mb-2 text-xs text-ink-2">
        Borrador orientativo: completa lo que está entre corchetes y revisa los hechos. Los fundamentos son solo citas
        literales que han superado la verificación.
      </p>
      <textarea value={texto} onChange={(e) => setTexto(e.target.value)} aria-label="Texto del escrito"
                className="field h-80 resize-y font-mono text-xs leading-relaxed" />
      <div className="mt-3 flex flex-wrap gap-2">
        <button className="btn-tonal" onClick={() => descargar(`${base}.doc`, escritoComoDoc(final), "application/msword")}>
          <FileText className="h-4 w-4" />Word
        </button>
        <button className="btn-outline" onClick={() => descargar(`${base}.txt`, texto, "text/plain")}>Texto</button>
        <button className="btn-outline" onClick={imprimir}><Printer className="h-4 w-4" />Imprimir o PDF</button>
        <button className="btn-ghost" onClick={() => navigator.clipboard?.writeText(texto).then(() => {
          setCopiado(true);
          setTimeout(() => setCopiado(false), 1500);
        })}>
          {copiado ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}{copiado ? "Copiado" : "Copiar"}
        </button>
      </div>
    </Dialog>
  );
}

/** «Qué hacer a continuación»: pasos deterministas con su base legal literal, plazos del motor y escritos. */
export function HojaDeRuta({ pasos, dictamen, plazos, postulacion, relato, titulos }: {
  pasos: PasoHoja[];
  dictamen?: Dictamen;
  plazos: Plazo[];
  postulacion?: Postulacion | null;
  relato: string;
  titulos: Map<string, string>;
}) {
  const [abierto, setAbierto] = useState<number | null>(null);
  const [escrito, setEscrito] = useState<Escrito | null>(null);
  if (!pasos.length) return null;
  const porTipo = new Map(plazos.map((p) => [p.tipo_plazo_id, p]));
  const conEscrito = puedeGenerarEscrito(dictamen);
  return (
    <section aria-label="Qué hacer a continuación" className="space-y-3">
      <h3 className="text-base font-medium text-ink">Qué hacer a continuación</h3>
      <ol className="space-y-3">
        {pasos.map((p, i) => {
          const plazo = p.plazo ? porTipo.get(p.plazo) : undefined;
          const restan = plazo ? diasNaturalesHasta(plazo.fecha_limite_segura) : null;
          return (
            <li key={i} className="break-inside-avoid rounded-3xl bg-surface p-5">
              <div className="flex items-start gap-3">
                <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent-container text-xs font-medium text-on-accent-container">{i + 1}</span>
                <div className="min-w-0 flex-1">
                  <p className="text-[15px] font-medium text-ink">{p.titulo}</p>
                  <p className="mt-0.5 text-xs text-ink-2">{quienTexto(p, postulacion)}</p>
                  <p className="mt-2 text-sm leading-relaxed text-ink">{p.que_hacer}</p>
                  {plazo && (plazo.titular === "contraparte" ? (
                    <p className="mt-2 text-sm text-ink-2">
                      Plazo de la otra parte: hasta el <span className="font-medium">{fechaLarga(plazo.fecha_limite_segura)}</span>
                      {restan !== null && (restan < 0 ? " — ya ha vencido, lo que te favorece" : ` (quedan ${restan} días)`)}
                    </p>
                  ) : (
                    <p className={`mt-2 text-sm ${restan !== null && restan >= 0 && restan <= 7 ? "text-danger" : "text-ink-2"}`}>
                      Tu fecha límite según el cálculo: <span className="font-medium">{fechaLarga(plazo.fecha_limite_segura)}</span>
                      {restan !== null && (restan < 0 ? " (ya vencida)" : ` (quedan ${restan} días)`)}
                    </p>
                  ))}
                  <div className="mt-3 flex flex-wrap items-center gap-2 print:hidden">
                    <button className="btn-ghost px-2 py-1 text-xs" aria-expanded={abierto === i}
                            onClick={() => setAbierto(abierto === i ? null : i)}>
                      Base legal ({p.base.length})
                      <ChevronDown className={`h-3.5 w-3.5 transition-transform ${abierto === i ? "rotate-180" : ""}`} aria-hidden />
                    </button>
                    {p.escrito && dictamen && (conEscrito ? (
                      <button className="btn-tonal px-3 py-1 text-xs"
                              onClick={() => setEscrito(generarEscrito(p.escrito!, dictamen, relato, p, titulos))}>
                        <FileText className="h-3.5 w-3.5" />Borrador del escrito
                      </button>
                    ) : (
                      <span className="text-xs text-ink-3">Sin borrador: con esta solidez conviene reunir antes las pruebas de «Puntos débiles».</span>
                    ))}
                  </div>
                  <ul className={`mt-2 space-y-1.5 ${abierto === i ? "" : "hidden print:block"}`}>
                    {p.base.map((b, j) => (
                      <li key={j} className="border-l-2 border-outline pl-3">
                        <span className="font-serif text-[14px] italic text-ink-2">«{b.cita}»</span>
                        <span className="block text-xs text-ink-3">Artículo {b.articulo} · {b.norma} (texto vigente verificado en el BOE)</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </li>
          );
        })}
      </ol>
      {escrito && <EscritoDialog escrito={escrito} onClose={() => setEscrito(null)} />}
    </section>
  );
}
