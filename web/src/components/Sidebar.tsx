import { useEffect, useState } from "react";
import { History, Plus } from "lucide-react";
import { api } from "../lib/api";
import { BANDA_TEXTO, type Banda } from "../lib/types";

type Item = Awaited<ReturnType<typeof api.consultas>>[number];

export function Sidebar({ actual, onAbrir, onNueva, refresco }: {
  actual: string | null;
  onAbrir: (id: string) => void;
  onNueva: () => void;
  refresco: number;
}) {
  const [items, setItems] = useState<Item[]>([]);
  useEffect(() => {
    api.consultas().then(setItems).catch(() => setItems([]));
  }, [refresco]);
  return (
    <aside className="hidden w-64 shrink-0 flex-col border-r border-slate-800 bg-slate-950 md:flex" aria-label="Historial">
      <div className="p-3">
        <button className="btn-ghost w-full justify-start border border-slate-800" onClick={onNueva}><Plus className="h-4 w-4" />Nueva consulta</button>
      </div>
      <p className="flex items-center gap-1.5 px-4 pb-1 text-[11px] uppercase tracking-wide text-slate-600"><History className="h-3 w-3" />Historial</p>
      <ul className="flex-1 overflow-auto px-2 pb-3 scroll-thin">
        {items.map((it) => (
          <li key={it.consulta_id}>
            <button onClick={() => onAbrir(it.consulta_id)}
                    className={`w-full rounded-lg px-2 py-2 text-left text-sm hover:bg-slate-900 ${actual === it.consulta_id ? "bg-slate-900" : ""}`}>
              <span className="line-clamp-2 text-slate-300">{it.titulo}</span>
              <span className="mt-0.5 block text-[11px] text-slate-600">
                {it.creado_en.slice(0, 16)} · {it.modo} · {it.banda ? BANDA_TEXTO[it.banda as Banda] ?? it.banda : it.estado.toLowerCase()}
              </span>
            </button>
          </li>
        ))}
        {!items.length && <li className="px-2 text-xs text-slate-600">Aún no hay consultas.</li>}
      </ul>
    </aside>
  );
}
