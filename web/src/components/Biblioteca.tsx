import { useEffect, useRef, useState, type DragEvent } from "react";
import { FileText, Library, Loader2, Plus, Trash2, Upload, X } from "lucide-react";
import { api, type DocumentoBiblioteca } from "../lib/api";

const TIPO_DOC: Record<string, string> = {
  nomina: "Nómina", contrato: "Contrato", carta_despido: "Carta de despido", sancion: "Sanción o multa", otro: "Documento",
};

const fecha = (s: string) => new Date(s.replace(" ", "T") + "Z").toLocaleDateString("es-ES");

/** Biblioteca de documentos propios (sentencias, convenios, contratos…) que se reutilizan en varias consultas.
 *  Al usarlos en una consulta se tratan como cualquier adjunto: el cortafuegos verifica las citas contra su texto. */
export function Biblioteca({ onMensaje }: { onMensaje: (m: string) => void }) {
  const [docs, setDocs] = useState<DocumentoBiblioteca[] | null>(null);
  const [subiendo, setSubiendo] = useState(false);
  const [arrastrando, setArrastrando] = useState(false);
  const [permitirEnvio, setPermitirEnvio] = useState(true);
  const [abierto, setAbierto] = useState<(DocumentoBiblioteca & { texto: string }) | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const cargar = () => api.biblioteca().then(setDocs).catch((e) => { setDocs([]); onMensaje(e.message); });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { void cargar(); }, []);

  async function subir(files: FileList | File[]) {
    setSubiendo(true);
    for (const f of Array.from(files)) {
      try {
        const r = await api.guardarDocumento(f, permitirEnvio);
        if (r.paginas_sin_texto.length) onMensaje(`${f.name}: ${r.paginas_sin_texto.length} páginas escaneadas sin texto`);
      } catch (e) {
        onMensaje(`${f.name}: ${(e as Error).message}`);
      }
    }
    setSubiendo(false);
    await cargar();
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setArrastrando(false);
    if (e.dataTransfer.files.length) void subir(e.dataTransfer.files);
  }

  async function borrar(d: DocumentoBiblioteca) {
    if (!window.confirm(`¿Quitar «${d.nombre}» de la biblioteca? Las consultas que ya lo usaron conservan su copia.`)) return;
    try {
      await api.borrarDocumento(d.doc_id);
      if (abierto?.doc_id === d.doc_id) setAbierto(null);
      await cargar();
    } catch (e) {
      onMensaje((e as Error).message);
    }
  }

  return (
    <div className="mx-auto max-w-[760px] space-y-6 px-4 pb-10 pt-4 sm:px-6">
      <div>
        <h1 className="text-[28px] font-normal tracking-tight text-ink">Biblioteca</h1>
        <p className="mt-1 text-sm text-ink-2">
          Guarda aquí sentencias, convenios, contratos o cartas que quieras usar en varias consultas. Al escribir una consulta,
          añádelos con el botón <Library className="inline h-4 w-4 align-text-bottom" aria-label="Biblioteca" /> y cada cita
          que se haga de ellos se comprobará literalmente contra su texto.
        </p>
      </div>

      <div onDragOver={(e) => { e.preventDefault(); setArrastrando(true); }} onDragLeave={() => setArrastrando(false)} onDrop={onDrop}
           className={`rounded-3xl border-2 border-dashed p-6 text-center transition-colors ${arrastrando ? "border-accent bg-accent-container/40" : "border-outline"}`}>
        <Upload className="mx-auto h-6 w-6 text-ink-3" aria-hidden />
        <p className="mt-2 text-sm text-ink-2">Arrastra aquí PDF o TXT, o</p>
        <input ref={fileRef} type="file" accept=".pdf,.txt,.md" multiple hidden onChange={(e) => e.target.files && subir(e.target.files)} />
        <button className="btn-tonal mt-3" onClick={() => fileRef.current?.click()} disabled={subiendo}>
          {subiendo ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}Añadir documentos
        </button>
        <label className="mx-auto mt-4 flex max-w-lg items-start gap-2 text-left text-xs text-ink-2">
          <input type="checkbox" checked={permitirEnvio} onChange={(e) => setPermitirEnvio(e.target.checked)}
                 className="mt-0.5 accent-[rgb(var(--accent))]" />
          <span>Permitir que su contenido (seudonimizado) se envíe a los modelos de IA cuando lo uses en una consulta. Sin este
            permiso solo se usa para clasificar tu caso.</span>
        </label>
      </div>

      {docs === null ? <Loader2 className="h-5 w-5 animate-spin text-ink-3" /> : docs.length === 0 ? (
        <p className="text-sm text-ink-3">Aún no hay documentos en tu biblioteca.</p>
      ) : (
        <ul className="divide-y divide-outline rounded-3xl bg-surface px-2">
          {docs.map((d) => (
            <li key={d.doc_id} className="flex items-center gap-3 px-3 py-3">
              <FileText className="h-5 w-5 shrink-0 text-ink-2" aria-hidden />
              <button className="min-w-0 flex-1 text-left" onClick={() => api.documento(d.doc_id).then(setAbierto).catch((e) => onMensaje(e.message))}>
                <span className="block truncate text-sm text-ink">{d.nombre}</span>
                <span className="block text-xs text-ink-3">
                  {TIPO_DOC[d.tipo] ?? d.tipo} · {d.caracteres.toLocaleString("es-ES")} caracteres · {fecha(d.creado_en)}
                  {!d.permitir_envio && " · solo para clasificar"}
                </span>
              </button>
              <button className="icon-btn h-9 w-9" aria-label={`Quitar ${d.nombre} de la biblioteca`} title="Quitar" onClick={() => borrar(d)}>
                <Trash2 className="h-4 w-4" />
              </button>
            </li>
          ))}
        </ul>
      )}

      {abierto && (
        <section aria-label={`Texto de ${abierto.nombre}`} className="rounded-3xl bg-surface p-5">
          <div className="mb-3 flex items-center gap-2">
            <p className="min-w-0 flex-1 truncate text-sm font-medium text-ink">{abierto.nombre}</p>
            <button className="icon-btn h-9 w-9" aria-label="Cerrar el texto" onClick={() => setAbierto(null)}><X className="h-4 w-4" /></button>
          </div>
          <p tabIndex={0} className="legal max-h-[28rem] overflow-auto whitespace-pre-wrap text-[15px] scroll-thin">{abierto.texto}</p>
        </section>
      )}
    </div>
  );
}

/** Menú del compositor para añadir documentos de la biblioteca a la consulta que se está escribiendo. */
export function SelectorBiblioteca({ onAdjuntar, deshabilitado }: {
  onAdjuntar: (a: { adjunto_id: string; nombre: string; tipo: string }) => void;
  deshabilitado: boolean;
}) {
  const [abierto, setAbierto] = useState(false);
  const [docs, setDocs] = useState<DocumentoBiblioteca[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!abierto) return;
    api.biblioteca().then(setDocs).catch((e) => setError(e.message));
    const cerrar = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !ref.current?.contains(e.target as Node)) setAbierto(false);
    };
    document.addEventListener("mousedown", cerrar);
    document.addEventListener("keydown", cerrar);
    return () => {
      document.removeEventListener("mousedown", cerrar);
      document.removeEventListener("keydown", cerrar);
    };
  }, [abierto]);

  return (
    <div ref={ref} className="relative">
      <button className="icon-btn" onClick={() => setAbierto((v) => !v)} disabled={deshabilitado} aria-haspopup="menu"
              aria-expanded={abierto} aria-label="Añadir desde tu biblioteca" title="Añadir desde tu biblioteca">
        <Library className="h-5 w-5" />
      </button>
      {abierto && (
        <div role="menu" className="fade-in absolute bottom-full left-0 z-40 mb-2 w-80 rounded-2xl bg-surface p-1.5 shadow-float">
          {error && <p className="px-3 py-2 text-sm text-danger">{error}</p>}
          {!docs && !error && <Loader2 className="m-3 h-4 w-4 animate-spin text-ink-3" />}
          {docs?.length === 0 && <p className="px-3 py-2 text-sm text-ink-3">Tu biblioteca está vacía. Añade documentos desde el menú lateral.</p>}
          {docs?.map((d) => (
            <button key={d.doc_id} role="menuitem" className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-sm text-ink hover:bg-surface-2"
                    onClick={() => api.adjuntarDocumento(d.doc_id).then((a) => { onAdjuntar(a); setAbierto(false); })
                      .catch((e) => setError(e.message))}>
              <FileText className="h-4 w-4 shrink-0 text-ink-2" aria-hidden /><span className="truncate">{d.nombre}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
