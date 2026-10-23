import { useRef, useState, type DragEvent } from "react";
import { FileText, Loader2, Paperclip, Send, X } from "lucide-react";
import { api } from "../lib/api";
import { MunicipioPicker, type Municipio } from "./MunicipioPicker";

interface Adjunto { adjunto_id: string; nombre: string; tipo: string; aviso?: string }

const EJEMPLOS = [
  "El casero no me devuelve la fianza de 900 € porque dice que tiene que pintar el piso.",
  "Me han despedido estando de baja médica, me entregaron la carta ayer.",
  "Me ha llegado una multa de zona azul que creo que no es correcta.",
];

export function Composer({ onEnviar, ocupado }: {
  onEnviar: (texto: string, municipio: string | null, adjuntos: string[]) => void;
  ocupado: boolean;
}) {
  const [texto, setTexto] = useState("");
  const [municipio, setMunicipio] = useState<Municipio | null>(null);
  const [adjuntos, setAdjuntos] = useState<Adjunto[]>([]);
  const [subiendo, setSubiendo] = useState(false);
  const [arrastrando, setArrastrando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [permitirEnvio, setPermitirEnvio] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

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

  const enviar = () => {
    if (texto.trim().length < 10 || ocupado) return;
    onEnviar(texto.trim(), municipio?.codigo_ine ?? null, adjuntos.map((a) => a.adjunto_id));
  };

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setArrastrando(true); }}
      onDragLeave={() => setArrastrando(false)}
      onDrop={onDrop}
      className={`card p-3 transition ${arrastrando ? "border-amber-500 ring-2 ring-amber-500/30" : ""}`}
    >
      {arrastrando && <p className="pb-2 text-center text-sm text-amber-300">Suelta aquí contratos, nóminas, cartas o multas (PDF/TXT)</p>}
      <textarea
        value={texto}
        onChange={(e) => setTexto(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) enviar(); }}
        rows={4}
        placeholder="Cuéntame qué te ha pasado, con fechas e importes si los sabes…"
        aria-label="Describe tu caso"
        className="w-full resize-none bg-transparent text-[15px] leading-relaxed outline-none placeholder:text-slate-600"
      />
      {!texto && (
        <div className="flex flex-wrap gap-2 pb-2">
          {EJEMPLOS.map((e) => (
            <button key={e} onClick={() => setTexto(e)} className="chip hover:border-amber-500/60 hover:text-amber-200">{e}</button>
          ))}
        </div>
      )}
      {adjuntos.length > 0 && (
        <div className="flex flex-wrap gap-2 pb-2">
          {adjuntos.map((a) => (
            <span key={a.adjunto_id} className="chip" title={a.aviso}>
              <FileText className="h-3 w-3 text-amber-400" aria-hidden />{a.nombre}
              <span className="text-slate-500">· {a.tipo.replace("_", " ")}</span>
              <button aria-label={`Quitar ${a.nombre}`} onClick={() => setAdjuntos((x) => x.filter((y) => y !== a))}>
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
      )}
      {error && <p className="pb-2 text-xs text-rose-400">{error}</p>}
      <div className="flex flex-wrap items-center gap-2 border-t border-slate-800 pt-2">
        <input ref={fileRef} type="file" accept=".pdf,.txt" multiple hidden onChange={(e) => e.target.files && subir(e.target.files)} />
        <button className="btn-ghost" onClick={() => fileRef.current?.click()} disabled={subiendo || adjuntos.length >= 5}>
          {subiendo ? <Loader2 className="h-4 w-4 animate-spin" /> : <Paperclip className="h-4 w-4" />}Adjuntar
        </button>
        <MunicipioPicker value={municipio} onChange={setMunicipio} />
        <span className="ml-auto hidden text-xs text-slate-600 sm:inline">Ctrl + Enter</span>
        <button className="btn-primary" onClick={enviar} disabled={ocupado || texto.trim().length < 10}>
          {ocupado ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}Analizar
        </button>
      </div>
      <label className="flex items-start gap-2 pt-2 text-[11px] text-slate-500">
        <input type="checkbox" checked={permitirEnvio} onChange={(e) => setPermitirEnvio(e.target.checked)}
               className="mt-0.5 accent-amber-500" />
        <span>
          Permitir que el contenido de los próximos adjuntos (seudonimizado) se envíe a los modelos de IA. Si no lo
          marcas, los documentos solo se leen en tu equipo para clasificarlos. Ojo: el plan gratuito de Gemini puede
          usar lo que recibe para mejorar sus productos.
        </span>
      </label>
      <p className="pt-1 text-[11px] text-slate-600">
        Antes de enviar tu texto se sustituyen por seudónimos los DNI/NIE, teléfonos, emails, IBAN, matrículas y los
        nombres que se detecten. La detección de nombres no es perfecta: evita escribir datos que no hagan falta.
      </p>
    </div>
  );
}
