import { useEffect, useMemo, useRef, useState } from "react";
import { Archive, ArchiveRestore, ChevronDown, Columns2, Library, MoreVertical, Pencil, Plus, Trash2 } from "lucide-react";
import { api, type ItemHistorial as Item } from "../lib/api";

function grupo(creado: string, hoy = new Date()): string {
  const d = new Date(creado.replace(" ", "T"));
  const dias = Math.floor((new Date(hoy.toDateString()).getTime() - new Date(d.toDateString()).getTime()) / 86_400_000);
  if (dias <= 0) return "Hoy";
  if (dias === 1) return "Ayer";
  if (dias < 7) return "Últimos 7 días";
  if (dias < 30) return "Últimos 30 días";
  return "Anteriores";
}

/** Menú «⋮» de un caso: renombrar, archivar y eliminar (con confirmación, porque no se puede deshacer). */
function MenuCaso({ it, onRenombrar, onArchivar, onEliminar }: {
  it: Item;
  onRenombrar: () => void;
  onArchivar: () => void;
  onEliminar: () => void;
}) {
  const [abierto, setAbierto] = useState(false);
  const [confirmar, setConfirmar] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!abierto) return;
    const cerrar = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !ref.current?.contains(e.target as Node)) {
        setAbierto(false);
        setConfirmar(false);
      }
    };
    document.addEventListener("mousedown", cerrar);
    document.addEventListener("keydown", cerrar);
    return () => {
      document.removeEventListener("mousedown", cerrar);
      document.removeEventListener("keydown", cerrar);
    };
  }, [abierto]);
  const opcion = "flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-ink hover:bg-surface-2";
  return (
    <div ref={ref} className="relative shrink-0">
      <button className={`icon-btn h-8 w-8 ${abierto ? "" : "md:opacity-0 md:group-hover:opacity-100 md:focus:opacity-100"}`}
              aria-haspopup="menu" aria-expanded={abierto} aria-label={`Opciones de «${it.titulo}»`}
              onClick={() => setAbierto((v) => !v)}>
        <MoreVertical className="h-4 w-4" />
      </button>
      {abierto && (
        <div role="menu" className="fade-in absolute right-0 z-40 mt-1 w-56 rounded-2xl bg-surface p-1.5 shadow-float">
          {confirmar ? (
            <div className="p-2">
              <p className="text-sm text-ink">¿Eliminar este caso para siempre?</p>
              <p className="mt-1 text-xs text-ink-2">Se borran la consulta, sus respuestas y sus adjuntos. No se puede deshacer.</p>
              <div className="mt-3 flex justify-end gap-2">
                <button className="btn-ghost px-3 py-1 text-xs" onClick={() => setConfirmar(false)}>Cancelar</button>
                <button className="btn bg-danger-container px-3 py-1 text-xs font-medium text-danger hover:opacity-90"
                        onClick={() => { setAbierto(false); setConfirmar(false); onEliminar(); }}>Eliminar</button>
              </div>
            </div>
          ) : (
            <>
              <button role="menuitem" className={opcion} onClick={() => { setAbierto(false); onRenombrar(); }}>
                <Pencil className="h-4 w-4 text-ink-2" aria-hidden />Renombrar
              </button>
              <button role="menuitem" className={opcion} onClick={() => { setAbierto(false); onArchivar(); }}>
                {it.archivada
                  ? <><ArchiveRestore className="h-4 w-4 text-ink-2" aria-hidden />Desarchivar</>
                  : <><Archive className="h-4 w-4 text-ink-2" aria-hidden />Archivar</>}
              </button>
              <button role="menuitem" className={`${opcion} text-danger`} onClick={() => setConfirmar(true)}>
                <Trash2 className="h-4 w-4" aria-hidden />Eliminar
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}

export function Sidebar({ abierta, actual, onAbrir, onNueva, onBorrada, refresco, vista, onBiblioteca, onComparar }: {
  abierta: boolean;
  actual: string | null;
  onAbrir: (id: string) => void;
  onNueva: () => void;
  /** Se ha eliminado un caso (si era el abierto, hay que volver al inicio). */
  onBorrada: (id: string) => void;
  refresco: number;
  vista: string;
  /** Solo el dueño del equipo tiene biblioteca. */
  onBiblioteca?: () => void;
  onComparar: () => void;
}) {
  const [items, setItems] = useState<Item[]>([]);
  const [editando, setEditando] = useState<string | null>(null);
  const [borrador, setBorrador] = useState("");
  const [verArchivadas, setVerArchivadas] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const cargar = () => api.consultas().then(setItems).catch(() => setItems([]));
  useEffect(() => {
    void cargar();
  }, [refresco]);
  const activas = useMemo(() => items.filter((i) => !i.archivada), [items]);
  const archivadas = useMemo(() => items.filter((i) => i.archivada), [items]);
  const grupos = useMemo(() => {
    const out: [string, Item[]][] = [];
    for (const it of activas) {
      const g = grupo(it.creado_en);
      const last = out[out.length - 1];
      if (last && last[0] === g) last[1].push(it);
      else out.push([g, [it]]);
    }
    return out;
  }, [activas]);

  const accion = async (fn: () => Promise<unknown>) => {
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
    await cargar();
  };
  const guardarTitulo = (it: Item) => {
    const titulo = borrador.trim();
    setEditando(null);
    if (titulo === it.titulo) return;
    void accion(() => api.editarConsulta(it.consulta_id, { titulo }));
  };

  const fila = (it: Item) => (
    <li key={it.consulta_id} className="group flex items-center">
      {editando === it.consulta_id ? (
        <input className="field w-full py-1.5 text-sm" autoFocus value={borrador} maxLength={120}
               aria-label="Nuevo nombre del caso"
               onChange={(e) => setBorrador(e.target.value)}
               onBlur={() => guardarTitulo(it)}
               onKeyDown={(e) => {
                 if (e.key === "Enter") guardarTitulo(it);
                 if (e.key === "Escape") setEditando(null);
               }} />
      ) : (
        <>
          <button
            onClick={() => onAbrir(it.consulta_id)}
            aria-current={actual === it.consulta_id ? "page" : undefined}
            title={it.titulo}
            className={`min-w-0 flex-1 truncate rounded-full px-3 py-2 text-left text-sm transition-colors ${
              actual === it.consulta_id
                ? "bg-accent-container text-on-accent-container"
                : "text-ink hover:bg-surface-2"
            }`}
          >
            {it.invitado && <span className="mr-1.5 rounded-md bg-surface-3 px-1.5 py-0.5 text-[11px] text-ink-2">Invitado</span>}
            {it.titulo}
          </button>
          <MenuCaso it={it}
                    onRenombrar={() => { setBorrador(it.titulo); setEditando(it.consulta_id); }}
                    onArchivar={() => void accion(() => api.editarConsulta(it.consulta_id, { archivada: !it.archivada }))}
                    onEliminar={() => void accion(async () => {
                      await api.borrarConsulta(it.consulta_id);
                      onBorrada(it.consulta_id);
                    })} />
        </>
      )}
    </li>
  );

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
        {onBiblioteca && (
          <button className={`btn-ghost mt-1 w-full justify-start px-4 ${vista === "biblioteca" ? "bg-surface-2 text-ink" : ""}`}
                  aria-current={vista === "biblioteca" ? "page" : undefined} onClick={onBiblioteca}>
            <Library className="h-4 w-4" />Biblioteca
          </button>
        )}
        <button className={`btn-ghost mt-1 w-full justify-start px-4 ${vista === "comparar" ? "bg-surface-2 text-ink" : ""}`}
                aria-current={vista === "comparar" ? "page" : undefined} onClick={onComparar}>
          <Columns2 className="h-4 w-4" />Comparar consultas
        </button>
      </div>
      <nav className="flex-1 overflow-auto px-3 pb-4 scroll-thin">
        {error && <p role="alert" className="mt-2 px-3 text-xs text-danger">No se pudo completar: {error}</p>}
        {grupos.map(([g, lista]) => (
          <div key={g} className="mt-4">
            <p className="px-3 pb-1 text-xs font-medium text-ink-2">{g}</p>
            <ul>{lista.map(fila)}</ul>
          </div>
        ))}
        {!items.length && <p className="mt-4 px-3 text-sm text-ink-3">Aún no hay consultas.</p>}
        {archivadas.length > 0 && (
          <div className="mt-4">
            <button className="flex w-full items-center gap-1 px-3 pb-1 text-xs font-medium text-ink-2 hover:text-ink"
                    aria-expanded={verArchivadas} onClick={() => setVerArchivadas((v) => !v)}>
              <ChevronDown className={`h-3.5 w-3.5 transition-transform ${verArchivadas ? "rotate-180" : ""}`} aria-hidden />
              Archivadas ({archivadas.length})
            </button>
            {verArchivadas && <ul>{archivadas.map(fila)}</ul>}
          </div>
        )}
      </nav>
    </aside>
  );
}
