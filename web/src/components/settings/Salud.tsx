import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { api, type Salud as DatosSalud } from "../../lib/api";

const ESTADOS: Record<string, string> = {
  CERTIFICADA: "Certificadas", BLOQUEADA: "Bloqueadas", FUERA_DE_ALCANCE: "Fuera de alcance", ERROR: "Con error",
  ESPERANDO_ACLARACION: "Esperando tus datos",
};

/** Panel de salud: qué tal responden los modelos (llamadas reales registradas en el equipo). */
export function Salud() {
  const [dias, setDias] = useState(7);
  const [datos, setDatos] = useState<DatosSalud | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setDatos(null);
    api.salud(dias).then(setDatos).catch((e) => setError(e.message));
  }, [dias]);
  if (error) return <p className="text-sm text-danger">{error}</p>;
  if (!datos) return <Loader2 className="h-5 w-5 animate-spin text-ink-3" />;
  return (
    <div className="space-y-4">
      <label className="flex items-center gap-2 text-sm text-ink-2">
        Periodo:
        <select className="field w-auto py-1" value={dias} onChange={(e) => setDias(Number(e.target.value))}>
          {[1, 7, 30, 90].map((d) => <option key={d} value={d}>{d === 1 ? "último día" : `últimos ${d} días`}</option>)}
        </select>
      </label>
      <p className="text-sm text-ink-2">
        Consultas: {Object.entries(datos.consultas).map(([e, n]) => `${ESTADOS[e] ?? e} ${n}`).join(" · ") || "ninguna"}
      </p>
      {datos.modelos.length === 0 ? <p className="text-sm text-ink-3">Sin llamadas en este periodo.</p> : (
        <div className="overflow-x-auto rounded-2xl bg-surface scroll-thin" tabIndex={0}>
          <table className="w-full text-left text-sm">
            <thead className="text-xs text-ink-2">
              <tr>
                <th className="px-4 py-2 font-medium">Modelo</th>
                <th className="px-3 py-2 font-medium">Llamadas</th>
                <th className="px-3 py-2 font-medium">Correctas</th>
                <th className="px-3 py-2 font-medium">Vacías</th>
                <th className="px-3 py-2 font-medium">Tiempo agotado</th>
                <th className="px-3 py-2 font-medium">Tiempo medio</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline">
              {datos.modelos.map((m) => {
                const pct = m.llamadas ? Math.round((100 * m.correctas) / m.llamadas) : 0;
                return (
                  <tr key={`${m.proveedor}-${m.modelo}`}>
                    <td className="px-4 py-2 text-ink">{m.modelo}<span className="block text-xs text-ink-3">{m.proveedor}</span></td>
                    <td className="px-3 py-2 tabular-nums">{m.llamadas}</td>
                    <td className={`px-3 py-2 tabular-nums ${pct < 80 ? "text-danger" : "text-ink"}`}>{pct} %</td>
                    <td className="px-3 py-2 tabular-nums">{m.vacias}</td>
                    <td className="px-3 py-2 tabular-nums">{m.tiempo_agotado}</td>
                    <td className="px-3 py-2 tabular-nums">{m.latencia_media_s} s</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
