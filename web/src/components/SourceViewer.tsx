import { useEffect, useId, useRef, useState } from "react";
import { ExternalLink, Loader2, X } from "lucide-react";
import { api } from "../lib/api";
import { highlightParts } from "../lib/highlight";

export interface FuenteAbierta { sourceId: string; quote?: string }

/** Panel lateral derecho con el texto oficial y el pasaje citado resaltado (patrón NotebookLM). */
export function SourceViewer({ abierta, consultaId, onClose }: {
  abierta: FuenteAbierta | null;
  consultaId: string | null;
  onClose: () => void;
}) {
  const [data, setData] = useState<Awaited<ReturnType<typeof api.fuente>> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const markRef = useRef<HTMLElement>(null);
  const panelRef = useRef<HTMLElement>(null);
  const tituloId = useId();

  useEffect(() => {
    if (!abierta) return;
    setData(null);
    setError(null);
    api.fuente(abierta.sourceId, consultaId ?? undefined, abierta.quote).then(setData).catch((e) => setError(e.message));
  }, [abierta, consultaId]);

  useEffect(() => {
    markRef.current?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [data]);

  useEffect(() => {
    if (!abierta) return;
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", esc);
    return () => document.removeEventListener("keydown", esc);
  }, [abierta, onClose]);

  // Teclado: al abrir, el foco pasa al panel; al cerrar vuelve a la cita que lo abrió (si sigue en la página).
  const abierto = Boolean(abierta);
  useEffect(() => {
    if (!abierto) return;
    const origen = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    panelRef.current?.focus();
    return () => {
      if (origen?.isConnected) origen.focus();
    };
  }, [abierto]);

  if (!abierta) return null;
  const [antes, resaltado, despues] = highlightParts(data?.texto ?? "", data?.resaltado?.offsets);
  return (
    <aside aria-labelledby={tituloId} ref={panelRef} tabIndex={-1}
           className="fade-in outline-none print:hidden fixed inset-0 z-40 flex flex-col bg-bg lg:static lg:inset-auto lg:z-auto lg:my-2 lg:mr-2 lg:w-[30rem] lg:shrink-0 lg:rounded-3xl lg:bg-surface">
      <div className="flex items-start gap-2 px-5 pb-3 pt-4">
        <div className="min-w-0 flex-1">
          <h2 id={tituloId} className="text-base font-medium text-ink">
            <span className="sr-only">Fuente oficial: </span>{data?.titulo ?? abierta.sourceId}
          </h2>
          <p className="truncate text-xs text-ink-3">{abierta.sourceId}</p>
        </div>
        {data?.url && (
          <a href={data.url} target="_blank" rel="noreferrer" className="icon-btn" title="Abrir en la fuente oficial"
             aria-label="Abrir en la fuente oficial">
            <ExternalLink className="h-5 w-5" />
          </a>
        )}
        <button className="icon-btn" onClick={onClose} aria-label="Cerrar visor"><X className="h-5 w-5" /></button>
      </div>
      <div className="flex-1 overflow-auto px-5 pb-6 scroll-thin" tabIndex={0} role="region" aria-label="Texto oficial">

        {error && <p className="text-sm text-danger">{error}</p>}
        {!data && !error && <Loader2 className="h-5 w-5 animate-spin text-ink-3" />}
        {data && (
          <>
            {data.resaltado && !data.resaltado.ok && (
              <p className="mb-3 rounded-xl bg-danger-container px-3 py-2 text-sm text-danger">
                La cita no coincide literalmente con esta fuente (similitud {data.resaltado.score}).
              </p>
            )}
            <p className="legal whitespace-pre-wrap">
              {antes}
              {resaltado && <mark ref={markRef} className="rounded bg-highlight px-0.5 text-ink">{resaltado}</mark>}
              {despues}
            </p>
          </>
        )}
      </div>
    </aside>
  );
}
