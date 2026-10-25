import { useEffect, useRef, useState, type DragEvent } from "react";
import { ArrowUp, FileText, Loader2, Paperclip, X } from "lucide-react";
import { api } from "../lib/api";
import { SelectorBiblioteca } from "./Biblioteca";
import { MunicipioPicker, type Municipio } from "./MunicipioPicker";

interface Adjunto { adjunto_id: string; nombre: string; tipo: string; aviso?: string }

export const SUGERENCIAS = [
  { corto: "No me devuelven la fianza", texto: "El casero no me devuelve la fianza de 900 € porque dice que tiene que pintar el piso." },
  { corto: "Me han despedido de baja", texto: "Me han despedido estando de baja médica, me entregaron la carta ayer." },
  { corto: "Multa que creo incorrecta", texto: "Me ha llegado una multa de zona azul que creo que no es correcta." },
];

/** Caja de texto principal. `hero`: grande y centrada (inicio); `dock`: fija al pie durante la consulta. */
export function Composer({ onEnviar, ocupado, variante, textoInicial, biblioteca = false }: {
  onEnviar: (texto: string, municipio: string | null, adjuntos: string[]) => void;
  ocupado: boolean;
  variante: "hero" | "dock";
  textoInicial?: string;
  /** Mostrar el botón de la biblioteca (solo el dueño del equipo). */
  biblioteca?: boolean;
}) {
  const [texto, setTexto] = useState("");
  const [municipio, setMunicipio] = useState<Municipio | null>(null);
  const [adjuntos, setAdjuntos] = useState<Adjunto[]>([]);
  const [subiendo, setSubiendo] = useState(false);
  const [arrastrando, setArrastrando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [permitirEnvio, setPermitirEnvio] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const areaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textoInicial) {
      setTexto(textoInicial);
      areaRef.current?.focus();
    }
  }, [textoInicial]);

  useEffect(() => {
    const el = areaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, variante === "hero" ? 320 : 200)}px`;
  }, [texto, variante]);

  async function subir(files: FileList | File[]) {
    setSubiendo(true);
    setError(null);
    for (const f of Array.from(files).slice(0, 5 - adjuntos.length)) {
      try {
        const r = await api.subir(f, permitirEnvio);
        setAdjuntos((a) => [...a, {
          ...r, aviso: r.paginas_sin_texto.length ? `${r.paginas_sin_texto.length} pág. sin texto (escaneadas)` : undefined,
        }]);
      } catch (e) {
        setError(`${f.name}: ${(e as Error).message}`);
      }
    }
    setSubiendo(false);
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setArrastrando(false);
    if (e.dataTransfer.files.length) void subir(e.dataTransfer.files);
  }

  const listo = texto.trim().length >= 10 && !ocupado;
  const enviar = () => {
    if (!listo) return;
    onEnviar(texto.trim(), municipio?.codigo_ine ?? null, adjuntos.map((a) => a.adjunto_id));
  };

  return (
    <div className="w-full">
      <div
        onDragOver={(e) => { e.preventDefault(); setArrastrando(true); }}
        onDragLeave={() => setArrastrando(false)}
        onDrop={onDrop}
        className={`rounded-[28px] bg-surface px-4 pb-2 pt-3 transition-shadow ${
          variante === "dock" ? "shadow-float" : ""
        } ${arrastrando ? "ring-2 ring-accent" : "focus-within:shadow-float"}`}
      >
        {arrastrando && <p className="pb-2 text-sm text-accent">Suelta aquí contratos, nóminas, cartas o multas (PDF o TXT)</p>}
        {adjuntos.length > 0 && (
          <div className="flex flex-wrap gap-2 pb-2">
            {adjuntos.map((a) => (
              <span key={a.adjunto_id} className="inline-flex items-center gap-1.5 rounded-xl bg-surface-2 px-3 py-1.5 text-sm text-ink" title={a.aviso}>
                <FileText className="h-4 w-4 text-ink-2" aria-hidden />{a.nombre}
                <button className="rounded-full p-0.5 hover:bg-surface-3" aria-label={`Quitar ${a.nombre}`}
                        onClick={() => setAdjuntos((x) => x.filter((y) => y !== a))}>
                  <X className="h-3.5 w-3.5" />
                </button>
              </span>
            ))}
          </div>
        )}
        <textarea
          ref={areaRef}
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              enviar();
            }
          }}
          rows={variante === "hero" ? 3 : 1}
          placeholder="Describe tu caso con fechas e importes si los sabes"
          aria-label="Describe tu caso"
          className="block w-full resize-none bg-transparent px-1 text-base leading-relaxed text-ink outline-none placeholder:text-ink-3"
        />
        <div className="flex items-center gap-1 pt-2">
          <input ref={fileRef} type="file" accept=".pdf,.txt" multiple hidden
                 onChange={(e) => e.target.files && subir(e.target.files)} />
          <button className="icon-btn" onClick={() => fileRef.current?.click()} disabled={subiendo || adjuntos.length >= 5}
                  aria-label="Adjuntar documentos" title="Adjuntar documentos (PDF o TXT)">
            {subiendo ? <Loader2 className="h-5 w-5 animate-spin" /> : <Paperclip className="h-5 w-5" />}
          </button>
          {biblioteca && (
            <SelectorBiblioteca deshabilitado={adjuntos.length >= 5}
                                onAdjuntar={(a) => setAdjuntos((x) => (x.length >= 5 ? x : [...x, a]))} />
          )}
          <MunicipioPicker value={municipio} onChange={setMunicipio} />
          <button
            className={`ml-auto inline-flex h-10 w-10 items-center justify-center rounded-full transition-colors ${
              listo ? "bg-accent text-on-accent hover:opacity-90" : "bg-surface-2 text-ink-3"
            }`}
            onClick={enviar}
            disabled={!listo}
            aria-label="Analizar"
            title="Analizar (Enter)"
          >
            {ocupado ? <Loader2 className="h-5 w-5 animate-spin" /> : <ArrowUp className="h-5 w-5" />}
          </button>
        </div>
      </div>
      {error && <p className="px-4 pt-2 text-sm text-danger">{error}</p>}
      {(variante === "hero" || adjuntos.length > 0) && (
        <label className="mx-auto mt-3 flex max-w-2xl items-start gap-2 px-4 text-xs text-ink-2">
          <input type="checkbox" checked={permitirEnvio} onChange={(e) => setPermitirEnvio(e.target.checked)}
                 className="mt-0.5 accent-[rgb(var(--accent))]" />
          <span>Permitir que el contenido de los próximos adjuntos (seudonimizado) se envíe a los modelos de IA. Si no lo
            marcas, los documentos solo se leen en tu equipo para clasificarlos.</span>
        </label>
      )}
      <p className={`px-4 pt-2 text-center text-xs text-ink-3 ${variante === "dock" ? "pb-1" : ""}`}>
        Información orientativa, no asesoramiento profesional. Los datos personales se seudonimizan antes de enviarse.
      </p>
    </div>
  );
}
