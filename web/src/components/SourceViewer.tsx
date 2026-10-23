import { useEffect, useRef, useState } from "react";
import { ExternalLink, Loader2, X } from "lucide-react";
import { api } from "../lib/api";
import { highlightParts } from "../lib/highlight";

export interface FuenteAbierta { sourceId: string; quote?: string }

export function SourceViewer({ abierta, consultaId, onClose }: {
  abierta: FuenteAbierta | null;
  consultaId: string | null;
  onClose: () => void;
}) {
  const [data, setData] = useState<Awaited<ReturnType<typeof api.fuente>> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const markRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (!abierta) return;
    setData(null);
    setError(null);
    api.fuente(abierta.sourceId, consultaId ?? undefined, abierta.quote).then(setData).catch((e) => setError(e.message));
  }, [abierta, consultaId]);

  useEffect(() => {
    markRef.current?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [data]);

  if (!abierta) return null;
  const [antes, resaltado, despues] = highlightParts(data?.texto ?? "", data?.resaltado?.offsets);
  return (
    <aside aria-label="Visor de fuentes"
           className="fixed inset-x-0 bottom-0 z-30 flex max-h-[75vh] flex-col border-t border-slate-800 bg-slate-950 shadow-2xl lg:static lg:inset-auto lg:max-h-none lg:w-[28rem] lg:shrink-0 lg:border-l lg:border-t-0">
      <div className="flex items-start gap-2 border-b border-slate-800 px-4 py-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-slate-100">{data?.titulo ?? abierta.sourceId}</p>
          <p className="truncate text-[11px] text-slate-500">{abierta.sourceId}</p>
        </div>
        {data?.url && (
          <a href={data.url} target="_blank" rel="noreferrer" className="btn-ghost ml-auto px-2" title="Abrir en la fuente oficial">
            <ExternalLink className="h-4 w-4" />
          </a>
        )}
        <button className={`btn-ghost px-2 ${data?.url ? "" : "ml-auto"}`} onClick={onClose} aria-label="Cerrar visor"><X className="h-4 w-4" /></button>
      </div>
      <div className="flex-1 overflow-auto px-4 py-3 scroll-thin">
        {error && <p className="text-sm text-rose-400">{error}</p>}
        {!data && !error && <Loader2 className="h-5 w-5 animate-spin text-slate-500" />}
        {data && (
          <>
            {data.resaltado && !data.resaltado.ok && (
              <p className="mb-2 rounded-md bg-rose-950/50 px-2 py-1 text-xs text-rose-300">
                La cita no coincide literalmente con esta fuente (similitud {data.resaltado.score}).
              </p>
            )}
            <p className="legal whitespace-pre-wrap">
              {antes}
              {resaltado && <mark ref={markRef} className="rounded bg-amber-400/25 px-0.5 text-amber-100">{resaltado}</mark>}
              {despues}
            </p>
          </>
        )}
      </div>
    </aside>
  );
}
