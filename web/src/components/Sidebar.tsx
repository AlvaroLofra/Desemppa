import { useEffect, useMemo, useState } from "react";
import { Plus } from "lucide-react";
import { api } from "../lib/api";

type Item = Awaited<ReturnType<typeof api.consultas>>[number];

function grupo(creado: string, hoy = new Date()): string {
  const d = new Date(creado.replace(" ", "T"));
  const dias = Math.floor((new Date(hoy.toDateString()).getTime() - new Date(d.toDateString()).getTime()) / 86_400_000);
  if (dias <= 0) return "Hoy";
  if (dias === 1) return "Ayer";
  if (dias < 7) return "Últimos 7 días";
  if (dias < 30) return "Últimos 30 días";
  return "Anteriores";
}

export function Sidebar({ abierta, actual, onAbrir, onNueva, refresco }: {
  abierta: boolean;
  actual: string | null;
  onAbrir: (id: string) => void;
  onNueva: () => void;
  refresco: number;
}) {
  const [items, setItems] = useState<Item[]>([]);
  useEffect(() => {
    api.consultas().then(setItems).catch(() => setItems([]));
  }, [refresco]);
  const grupos = useMemo(() => {
    const out: [string, Item[]][] = [];
    for (const it of items) {
      const g = grupo(it.creado_en);
      const last = out[out.length - 1];
      if (last && last[0] === g) last[1].push(it);
      else out.push([g, [it]]);
    }
    return out;
  }, [items]);

  if (!abierta) return null;
  return (
    <aside
      aria-label="Historial"
      className="fixed inset-y-0 left-0 z-30 flex w-72 print:hidden shrink-0 flex-col bg-surface pt-16 shadow-float md:static md:z-auto md:pt-0 md:shadow-none"
    >
      <div className="px-3 pb-2 pt-1">
        <button className="btn-ghost w-full justify-start bg-surface-2 px-4 text-ink" onClick={onNueva}>
          <Plus className="h-4 w-4" />Nueva consulta
        </button>
      </div>
      <nav className="flex-1 overflow-auto px-3 pb-4 scroll-thin">
        {grupos.map(([g, lista]) => (
          <div key={g} className="mt-4">
            <p className="px-3 pb-1 text-xs font-medium text-ink-2">{g}</p>
            <ul>
              {lista.map((it) => (
                <li key={it.consulta_id}>
                  <button
                    onClick={() => onAbrir(it.consulta_id)}
                    aria-current={actual === it.consulta_id ? "page" : undefined}
                    title={it.titulo}
                    className={`w-full truncate rounded-full px-3 py-2 text-left text-sm transition-colors ${
                      actual === it.consulta_id
                        ? "bg-accent-container text-on-accent-container"
                        : "text-ink hover:bg-surface-2"
                    }`}
                  >
                    {it.titulo}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ))}
        {!items.length && <p className="mt-4 px-3 text-sm text-ink-3">Aún no hay consultas.</p>}
      </nav>
    </aside>
  );
}
