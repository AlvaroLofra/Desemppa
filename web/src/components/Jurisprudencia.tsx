import { useEffect, useMemo, useRef, useState, type DragEvent } from "react";
import { Check, Copy, ExternalLink, Gavel, Loader2, Upload } from "lucide-react";
import { api, type ResumenJurisprudencia } from "../lib/api";

const JURISDICCION: Record<string, string> = {
  civil: "Civil", social: "Laboral", contencioso: "Contencioso-administrativo", administrativa_previa: "Administrativo",
};

type Resultado = { nombre: string; ok: boolean; texto: string };

/** Asistente para poblar la jurisprudencia local. La descarga de CENDOJ la hace una persona en su navegador
 *  (art. 507 LOPJ y aviso legal del CGPJ prohíben la descarga automática); aquí solo se guía y se importa. */
export function Jurisprudencia({ onMensaje }: { onMensaje: (m: string) => void }) {
  const [res, setRes] = useState<ResumenJurisprudencia | null>(null);
  const [materia, setMateria] = useState<string>("");
  const [subiendo, setSubiendo] = useState(false);
  const [arrastrando, setArrastrando] = useState(false);
  const [resultados, setResultados] = useState<Resultado[]>([]);
  const [copiado, setCopiado] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const cargar = () => api.resumenJurisprudencia().then((r) => {
    setRes(r);
    // Por defecto, la materia con menos sentencias (la que más falta hace).
    setMateria((m) => m || [...r.materias].sort((a, b) => a.sentencias - b.sentencias)[0]?.clave || "");
  }).catch((e) => onMensaje(e.message));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { void cargar(); }, []);

  const actual = useMemo(() => res?.materias.find((m) => m.clave === materia), [res, materia]);

  async function importar(files: FileList | File[]) {
    setSubiendo(true);
    const nuevos: Resultado[] = [];
    for (const f of Array.from(files)) {
      try {
        const r = await api.importarSentencia(f);
        nuevos.push({
          nombre: f.name, ok: true,
          texto: `${r.roj} ${r.nueva ? "importada" : "actualizada"}${r.avisos.length ? ` · ${r.avisos.join("; ")}` : ""}`,
        });
      } catch (e) {
        nuevos.push({ nombre: f.name, ok: false, texto: (e as Error).message });
      }
    }
    setResultados((x) => [...nuevos, ...x].slice(0, 20));
    setSubiendo(false);
    await cargar();
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setArrastrando(false);
    if (e.dataTransfer.files.length) void importar(e.dataTransfer.files);
  }

  async function copiar(t: string) {
    try {
      await navigator.clipboard.writeText(t);
      setCopiado(t);
      setTimeout(() => setCopiado(null), 1500);
    } catch {
      onMensaje("No se pudo copiar: selecciona el texto y cópialo a mano.");
    }
  }

  return (
    <section aria-label="Jurisprudencia" className="space-y-4 rounded-3xl bg-surface p-5">
      <div className="flex items-start gap-3">
        <Gavel className="mt-0.5 h-5 w-5 shrink-0 text-ink-2" aria-hidden />
        <div>
          <h2 className="text-lg font-normal text-ink">Jurisprudencia</h2>
          <p className="mt-0.5 text-sm text-ink-2">
            {res ? <>Tienes <strong className="font-medium text-ink">{res.total}</strong> sentencias importadas
              {Object.keys(res.por_jurisdiccion).length > 0 && <> ({Object.entries(res.por_jurisdiccion)
                .map(([j, n]) => `${JURISDICCION[j] ?? j}: ${n}`).join(", ")})</>}.</> : "Cargando…"}
            {" "}Con sentencias, la solidez puede llegar a «Favorable» y el análisis cita cómo deciden los tribunales.
          </p>
        </div>
      </div>

      <ol className="space-y-4 text-sm text-ink">
        <li>
          <p className="font-medium">1. Elige la materia</p>
          <select className="field mt-1.5 w-full" value={materia} onChange={(e) => setMateria(e.target.value)}
                  aria-label="Materia para buscar sentencias">
            {res?.materias.map((m) => (
              <option key={m.clave} value={m.clave}>
                {m.descripcion} — {m.sentencias ? `${m.sentencias} sentencias` : "ninguna aún"}
              </option>
            ))}
          </select>
        </li>
        <li>
          <p className="font-medium">2. Busca en CENDOJ con estos términos y descarga los PDF</p>
          <p className="mt-0.5 text-xs text-ink-2">
            Filtra por jurisdicción {actual ? <strong>{JURISDICCION[actual.jurisdiccion] ?? actual.jurisdiccion}</strong> : null} y
            prioriza Tribunal Supremo y Audiencias Provinciales. Pulsa el icono de PDF de cada sentencia y guárdala.
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            {actual?.terminos.map((t) => (
              <button key={t} type="button" className="btn-outline px-3 py-1 text-xs" onClick={() => copiar(t)}
                      title="Copiar para pegarlo en el buscador">
                {copiado === t ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}{t}
              </button>
            ))}
          </div>
          {res && (
            <a className="btn-tonal mt-3 inline-flex" href={res.buscador} target="_blank" rel="noopener noreferrer">
              <ExternalLink className="h-4 w-4" />Abrir el buscador de CENDOJ
            </a>
          )}
        </li>
        <li>
          <p className="font-medium">3. Arrastra aquí los PDF descargados</p>
          <div onDragOver={(e) => { e.preventDefault(); setArrastrando(true); }} onDragLeave={() => setArrastrando(false)} onDrop={onDrop}
               className={`mt-1.5 rounded-2xl border-2 border-dashed p-5 text-center transition-colors ${arrastrando ? "border-accent bg-accent-container/40" : "border-outline"}`}>
            <Upload className="mx-auto h-5 w-5 text-ink-3" aria-hidden />
            <input ref={fileRef} type="file" accept=".pdf,.txt" multiple hidden aria-label="Importar sentencias"
                   onChange={(e) => e.target.files && importar(e.target.files)} />
            <button className="btn-outline mt-2" onClick={() => fileRef.current?.click()} disabled={subiendo}>
              {subiendo ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}Elegir sentencias
            </button>
            <p className="mt-2 text-xs text-ink-3">Se lee el ROJ, la fecha y los fundamentos; los votos particulares no se usan.</p>
          </div>
        </li>
      </ol>

      {resultados.length > 0 && (
        <ul className="space-y-1 text-xs" aria-live="polite">
          {resultados.map((r, i) => (
            <li key={`${r.nombre}-${i}`} className={r.ok ? "text-ink-2" : "text-danger"}>
              {r.ok ? "✓" : "✗"} {r.nombre}: {r.texto}
            </li>
          ))}
        </ul>
      )}
      {res && res.ultimas.length > 0 && (
        <details className="text-xs text-ink-2">
          <summary className="cursor-pointer">Últimas importadas</summary>
          <ul className="mt-1 space-y-0.5 pl-4">
            {res.ultimas.map((u) => <li key={u.roj}>{u.roj} · {u.tribunal} · {u.fecha}</li>)}
          </ul>
        </details>
      )}
    </section>
  );
}
