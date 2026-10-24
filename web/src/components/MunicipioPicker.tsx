import { useEffect, useRef, useState } from "react";
import { MapPin, X } from "lucide-react";
import { api } from "../lib/api";

export interface Municipio { codigo_ine: string; nombre: string; provincia: string }

export function MunicipioPicker({ value, onChange, compact = false, arriba = true }: {
  value: Municipio | null;
  onChange: (m: Municipio | null) => void;
  compact?: boolean;
  arriba?: boolean;
}) {
  const [q, setQ] = useState("");
  const [abierto, setAbierto] = useState(false);
  const [opciones, setOpciones] = useState<Municipio[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (abierto) inputRef.current?.focus();
  }, [abierto]);
  useEffect(() => {
    if (q.trim().length < 2) {
      setOpciones([]);
      return;
    }
    const t = setTimeout(() => api.municipios(q).then(setOpciones).catch(() => setOpciones([])), 180);
    return () => clearTimeout(t);
  }, [q]);

  if (value) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-surface-2 py-1.5 pl-3 pr-1.5 text-sm text-ink">
        <MapPin className="h-3.5 w-3.5 text-ink-2" aria-hidden />
        {value.nombre} <span className="text-ink-3">· {value.provincia}</span>
        <button className="rounded-full p-0.5 hover:bg-surface-3" aria-label="Quitar municipio" onClick={() => onChange(null)}>
          <X className="h-3.5 w-3.5" />
        </button>
      </span>
    );
  }
  if (compact === false && !abierto) {
    return (
      <button
        className="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm text-ink-2 hover:bg-surface-2"
        onClick={() => setAbierto(true)}
      >
        <MapPin className="h-4 w-4" aria-hidden />Municipio
      </button>
    );
  }
  return (
    <div className="relative">
      <div className="flex items-center gap-1.5 rounded-full border border-outline bg-bg px-3 py-1.5">
        <MapPin className="h-4 w-4 text-ink-3" aria-hidden />
        <input
          ref={inputRef}
          autoFocus={!compact}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Municipio del juzgado u organismo"
          aria-label="Municipio"
          className="w-56 bg-transparent text-sm text-ink outline-none placeholder:text-ink-3"
        />
        {!compact && (
          <button className="rounded-full p-0.5 text-ink-3 hover:bg-surface-2" aria-label="Cerrar buscador de municipio"
                  onClick={() => { setQ(""); setAbierto(false); }}>
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>
      {opciones.length > 0 && (
        <ul
          role="listbox"
          className={`absolute z-40 max-h-64 w-72 overflow-auto rounded-2xl bg-surface p-1.5 shadow-float scroll-thin ${
            arriba ? "bottom-full mb-2" : "top-full mt-2"
          }`}
        >
          {opciones.map((m) => (
            <li key={m.codigo_ine}>
              <button
                role="option"
                aria-selected={false}
                onClick={() => {
                  onChange(m);
                  setQ("");
                  setOpciones([]);
                  setAbierto(false);
                }}
                className="w-full rounded-xl px-3 py-2 text-left text-sm text-ink hover:bg-surface-2"
              >
                {m.nombre} <span className="text-ink-3">· {m.provincia}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
