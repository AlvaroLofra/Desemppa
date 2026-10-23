import { useEffect, useState } from "react";
import { MapPin, X } from "lucide-react";
import { api } from "../lib/api";

export interface Municipio { codigo_ine: string; nombre: string; provincia: string }

export function MunicipioPicker({ value, onChange, compact = false }: {
  value: Municipio | null;
  onChange: (m: Municipio | null) => void;
  compact?: boolean;
}) {
  const [q, setQ] = useState("");
  const [opciones, setOpciones] = useState<Municipio[]>([]);
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
      <span className="chip">
        <MapPin className="h-3 w-3 text-amber-400" aria-hidden />
        {value.nombre} <span className="text-slate-500">({value.provincia})</span>
        <button aria-label="Quitar municipio" onClick={() => onChange(null)}><X className="h-3 w-3" /></button>
      </span>
    );
  }
  return (
    <div className="relative">
      <div className="flex items-center gap-1.5 rounded-lg border border-slate-800 bg-slate-900 px-2 py-1">
        <MapPin className="h-3.5 w-3.5 text-slate-500" aria-hidden />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={compact ? "Municipio" : "Municipio del juzgado u organismo"}
          aria-label="Municipio"
          className="w-48 bg-transparent text-sm outline-none placeholder:text-slate-600"
        />
      </div>
      {opciones.length > 0 && (
        <ul role="listbox" className="absolute bottom-full z-20 mb-1 max-h-60 w-72 overflow-auto rounded-lg border border-slate-700 bg-slate-900 py-1 shadow-xl scroll-thin">
          {opciones.map((m) => (
            <li key={m.codigo_ine}>
              <button
                role="option"
                aria-selected={false}
                onClick={() => { onChange(m); setQ(""); setOpciones([]); }}
                className="w-full px-3 py-1.5 text-left text-sm hover:bg-slate-800"
              >
                {m.nombre} <span className="text-slate-500">· {m.provincia}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
