import { useEffect, useId, useState } from "react";
import { CircleAlert, CircleCheck, CircleDashed, Download, Loader2, Search } from "lucide-react";
import { api, type EstadoCorpus, type NormaCorpus, type PreceptoEncontrado } from "../lib/api";
import { fechaLarga } from "../lib/highlight";

const ESTADO: Record<NormaCorpus["estado"], string> = {
  pendiente: "Sin descargar", en_curso: "Descargando", completa: "Descargado", parcial: "Incompleto", error: "Error",
};

function IconoEstado({ e }: { e: NormaCorpus["estado"] }) {
  if (e === "completa") return <CircleCheck className="h-4 w-4 text-success" aria-hidden />;
  if (e === "error" || e === "parcial") return <CircleAlert className="h-4 w-4 text-warning" aria-hidden />;
  if (e === "en_curso") return <Loader2 className="h-4 w-4 animate-spin text-accent" aria-hidden />;
  return <CircleDashed className="h-4 w-4 text-ink-3" aria-hidden />;
}

/** Códigos legales: los grandes cuerpos del BOE descargados enteros (todas sus versiones) para buscar el precepto
 *  vigente a la fecha de los hechos. La descarga es del BOE oficial y solo baja lo que ha cambiado. */
export function CodigosLegales({ onMensaje }: { onMensaje: (m: string) => void }) {
  const [estado, setEstado] = useState<EstadoCorpus | null>(null);
  const [q, setQ] = useState("");
  const [fecha, setFecha] = useState("");
  const [hallados, setHallados] = useState<PreceptoEncontrado[] | null>(null);
  const [buscando, setBuscando] = useState(false);
  const idBusqueda = useId();
  const idFecha = useId();

  const cargar = () => api.corpus().then(setEstado).catch((e) => onMensaje(e.message));
  useEffect(() => { void cargar(); }, []);
  useEffect(() => {
    if (!estado?.en_curso) return;
    const t = setInterval(() => void cargar(), 2000);
    return () => clearInterval(t);
  }, [estado?.en_curso]);

  const descargar = (normas: string[] | null) =>
    api.ingerirCorpus(normas).then(() => cargar()).catch((e) => onMensaje(e.message));

  const buscar = async (e: React.FormEvent) => {
    e.preventDefault();
    if (q.trim().length < 3) return;
    setBuscando(true);
    try {
      setHallados(await api.buscarCorpus(q.trim(), fecha || undefined));
    } catch (err) {
      onMensaje((err as Error).message);
    } finally {
      setBuscando(false);
    }
  };

  if (!estado) return null;
  const descargadas = estado.normas.filter((n) => n.preceptos_ok > 0).length;
  const curso = estado.en_curso;
  return (
    <section aria-labelledby="codigos-titulo" className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-0 flex-1">
          <h2 id="codigos-titulo" className="text-lg font-medium text-ink">Códigos legales</h2>
          <p className="text-sm text-ink-2">
            {descargadas} de {estado.normas.length} descargados del BOE oficial, con todas sus versiones: cada consulta
            busca el artículo en la redacción vigente en la fecha de los hechos.
            {estado.vectorial ? ` Búsqueda semántica activa (${estado.modelo_embeddings}).` : " Búsqueda por palabras (sin modelo semántico instalado)."}
          </p>
        </div>
        <button className="btn-primary" onClick={() => void descargar(null)} disabled={Boolean(curso)}>
          {curso ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <Download className="h-4 w-4" aria-hidden />}
          {descargadas ? "Actualizar todos" : "Descargar todos"}
        </button>
      </div>
      {curso && (
        <p className="text-sm text-ink-2" aria-live="polite">
          Descargando {curso.alias ?? "…"} ({curso.hechas + 1} de {curso.total})
          {curso.de ? ` · ${curso.fase} ${curso.hechos ?? 0}/${curso.de}` : ""}. Puedes seguir usando la app.
        </p>
      )}
      <ul className="divide-y divide-outline rounded-3xl bg-surface px-5">
        {estado.normas.map((n) => (
          <li key={n.id_norma} className="flex items-center gap-3 py-2.5 text-sm">
            <IconoEstado e={n.estado} />
            <div className="min-w-0 flex-1">
              <p className="truncate text-ink">{n.titulo}</p>
              <p className="text-xs text-ink-3">
                {n.alias} · {ESTADO[n.estado]}{n.preceptos ? ` · ${n.preceptos_ok}/${n.preceptos} artículos` : ""}
                {!n.verificado && " · identificador sin verificar: se comprueba con el BOE al descargar"}
                {n.ultimo_error && ` · ${n.ultimo_error}`}
              </p>
            </div>
            <button className="btn-ghost px-3 py-1 text-xs" disabled={Boolean(curso)} onClick={() => void descargar([n.alias])}
                    aria-label={`${n.preceptos_ok ? "Actualizar" : "Descargar"} ${n.titulo}`}>
              {n.preceptos_ok ? "Actualizar" : "Descargar"}
            </button>
          </li>
        ))}
      </ul>
      <form onSubmit={buscar} className="flex flex-wrap items-end gap-3" role="search" aria-label="Buscar en los códigos">
        <div className="min-w-[14rem] flex-1">
          <label htmlFor={idBusqueda} className="label">Buscar en los códigos descargados</label>
          <input id={idBusqueda} className="field w-full" value={q} onChange={(e) => setQ(e.target.value)}
                 placeholder="p. ej. devolución de la fianza" minLength={3} />
        </div>
        <div>
          <label htmlFor={idFecha} className="label">Vigente en</label>
          <input id={idFecha} type="date" className="field" value={fecha} onChange={(e) => setFecha(e.target.value)} />
        </div>
        <button className="btn-tonal" type="submit" disabled={buscando || q.trim().length < 3}>
          {buscando ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <Search className="h-4 w-4" aria-hidden />}Buscar
        </button>
      </form>
      {hallados && (
        hallados.length === 0
          ? <p className="text-sm text-ink-3">Sin resultados en los códigos descargados para esa fecha.</p>
          : (
            <ol className="space-y-3" aria-label="Artículos encontrados">
              {hallados.map((h) => (
                <li key={h.url} className="rounded-2xl bg-surface p-4">
                  <a href={h.url} target="_blank" rel="noreferrer" className="font-medium text-ink hover:underline">
                    {h.titulo} {h.alias && <span className="text-ink-2">· {h.alias}</span>}
                  </a>
                  {h.ubicacion && <p className="text-xs text-ink-3">{h.ubicacion}</p>}
                  <p className="legal mt-1 text-[15px]">{h.extracto}…</p>
                  <p className="mt-1 text-xs text-ink-3">
                    Redacción vigente desde el {fechaLarga(h.vigencia_desde)}
                    {h.vigencia_hasta ? ` hasta el ${fechaLarga(h.vigencia_hasta)} (ya reformada)` : " (actual)"}
                  </p>
                </li>
              ))}
            </ol>
          )
      )}
    </section>
  );
}
