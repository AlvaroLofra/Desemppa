import { useEffect, useState } from "react";
import { CheckCircle2, CircleDashed, FlaskConical, Loader2, RefreshCw, RotateCcw, Save, Search, XCircle } from "lucide-react";
import { api, type Asignacion, type Perfiles, type Proveedor } from "../lib/api";

const MODOS = [
  { id: "eco", label: "Eco" },
  { id: "equilibrado", label: "Equilibrado" },
  { id: "pro", label: "Pro" },
];
const ROLES = [
  { id: "triaje", label: "Triaje", ayuda: "Clasifica la consulta (volumen alto, tarea sencilla)" },
  { id: "cribado", label: "Cribado", ayuda: "Selecciona fuentes" },
  { id: "defensa", label: "Defensa", ayuda: "Argumenta a tu favor" },
  { id: "contraparte", label: "Contraparte", ayuda: "Ataca tu posición" },
  { id: "magistrado", label: "Magistrado", ayuda: "Resuelve: el rol más exigente" },
  { id: "nli", label: "Verificación NLI", ayuda: "Comprueba que la conclusión no contradice la norma; mejor otro canal" },
];

function estadoProveedor(p: Proveedor): { icono: typeof CheckCircle2; color: string; texto: string } {
  if (!p.habilitado) return { icono: CircleDashed, color: "text-slate-500", texto: "desactivado en config/providers.toml" };
  if (!p.instalado) return { icono: XCircle, color: "text-rose-400", texto: "no instalado o sin configurar" };
  if (p.breaker.estado === "open") return { icono: XCircle, color: "text-amber-400", texto: "cuota agotada temporalmente" };
  if (!p.ultima_llamada) return { icono: CircleDashed, color: "text-slate-400", texto: "instalado; aún sin usar" };
  if (p.ultima_llamada.ok) return { icono: CheckCircle2, color: "text-emerald-400", texto: "funcionando" };
  if (p.ultima_llamada.error_tipo === "NotAuthenticated")
    return { icono: XCircle, color: "text-rose-400", texto: "sin sesión iniciada" };
  return { icono: XCircle, color: "text-rose-400", texto: `último error: ${p.ultima_llamada.error_tipo}` };
}

export function ModelsPage() {
  const [proveedores, setProveedores] = useState<Record<string, Proveedor> | null>(null);
  const [perfiles, setPerfiles] = useState<Perfiles | null>(null);
  const [modos, setModos] = useState<Perfiles["modos"] | null>(null);
  const [detectados, setDetectados] = useState<Record<string, string[] | "cargando">>({});
  const [pruebas, setPruebas] = useState<Record<string, string>>({});
  const [mensaje, setMensaje] = useState<string | null>(null);

  const cargar = () => {
    api.proveedores().then(setProveedores).catch((e) => setMensaje(e.message));
    api.perfiles().then((p) => { setPerfiles(p); setModos(p.modos); }).catch((e) => setMensaje(e.message));
  };
  useEffect(cargar, []);

  const detectar = async (pid: string) => {
    setDetectados((d) => ({ ...d, [pid]: "cargando" }));
    try {
      const r = await api.detectar(pid);
      setDetectados((d) => ({ ...d, [pid]: r.instalado ? r.modelos : [] }));
    } catch (e) {
      setMensaje((e as Error).message);
      setDetectados((d) => ({ ...d, [pid]: [] }));
    }
  };
  const probar = async (alias: string) => {
    setPruebas((p) => ({ ...p, [alias]: "probando…" }));
    try {
      const r = await api.probar(alias);
      setPruebas((p) => ({ ...p, [alias]: r.ok ? `OK · ${(r.latencia_ms / 1000).toFixed(1)} s` : r.error ?? "error" }));
    } catch (e) {
      setPruebas((p) => ({ ...p, [alias]: (e as Error).message }));
    }
    api.proveedores().then(setProveedores).catch(() => undefined);
  };
  const cambiar = (modo: string, rol: string, cambio: Partial<Asignacion>) => {
    if (!modos || !perfiles) return;
    const actual = modos[modo][rol];
    let siguiente = { ...actual, ...cambio } as Asignacion;
    const efforts = perfiles.modelos[siguiente.model]?.efforts ?? [];
    if (!efforts.includes(siguiente.effort)) siguiente = { ...siguiente, effort: efforts[efforts.length - 1] as Asignacion["effort"] };
    setModos({ ...modos, [modo]: { ...modos[modo], [rol]: siguiente } });
  };
  const guardar = async () => {
    if (!modos) return;
    try {
      const soloModos = Object.fromEntries(MODOS.map((m) => [m.id, modos[m.id]]));
      await api.guardarPerfiles(soloModos);
      setMensaje("Asignación guardada. Se aplica a las próximas consultas.");
      cargar();
    } catch (e) {
      setMensaje(`No se ha guardado: ${(e as Error).message}`);
    }
  };
  const restablecer = async () => {
    await api.restablecerPerfiles();
    setMensaje("Restablecida la asignación por defecto.");
    cargar();
  };

  const cambios = modos && perfiles ? JSON.stringify(modos) !== JSON.stringify(perfiles.modos) : false;
  return (
    <div className="mx-auto max-w-5xl space-y-6 px-4 py-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-100">Modelos y proveedores</h1>
        <p className="mt-1 text-sm text-slate-400">
          Elige qué modelo hace cada tarea. Para añadir un proveedor nuevo (p. ej. Codex), instálalo, inicia sesión,
          actívalo en <code className="text-slate-300">config/providers.toml</code> y pulsa «Detectar».
        </p>
      </div>
      {mensaje && <p role="status" className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-300">{mensaje}</p>}

      <section aria-label="Proveedores" className="grid gap-3 sm:grid-cols-2">
        {!proveedores && <Loader2 className="h-5 w-5 animate-spin text-slate-500" />}
        {proveedores && Object.entries(proveedores).map(([pid, p]) => {
          const st = estadoProveedor(p);
          const det = detectados[pid];
          return (
            <div key={pid} className="card p-4">
              <div className="flex items-start gap-2">
                <st.icono className={`mt-0.5 h-4 w-4 shrink-0 ${st.color}`} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-slate-100">{p.etiqueta}</p>
                  <p className="text-xs text-slate-500">{st.texto}{p.version ? ` · ${p.version}` : ""} · {p.uso_ultimas_5h.llamadas} llamadas en 5 h</p>
                </div>
                {p.habilitado && (
                  <button className="btn-ghost px-2 py-1 text-xs" onClick={() => detectar(pid)} disabled={det === "cargando"}>
                    {det === "cargando" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Search className="h-3.5 w-3.5" />}Detectar
                  </button>
                )}
              </div>
              {(!p.instalado || st.texto.includes("sesión")) && p.login && (
                <p className="mt-2 rounded-md bg-slate-950/60 px-2 py-1.5 text-xs text-amber-200">{p.login}</p>
              )}
              {Array.isArray(det) && (
                <p className="mt-2 text-xs text-slate-400">
                  Modelos ofrecidos: {det.length ? det.join(", ") : "ninguno"}
                </p>
              )}
              <div className="mt-2 flex flex-wrap gap-1.5">
                {p.modelos.map((alias) => (
                  <button key={alias} onClick={() => probar(alias)} disabled={!p.instalado}
                          className="chip hover:border-amber-500/60" title="Hacer una llamada mínima de prueba">
                    <FlaskConical className="h-3 w-3 text-amber-400" />{perfiles?.modelos[alias]?.etiqueta ?? alias}
                    {pruebas[alias] && <span className="text-slate-400">· {pruebas[alias]}</span>}
                  </button>
                ))}
              </div>
            </div>
          );
        })}
      </section>

      <section aria-label="Asignación por modo" className="card overflow-x-auto p-4 scroll-thin">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <h2 className="text-sm font-semibold text-slate-100">Qué modelo hace cada tarea</h2>
          <button className="btn-ghost ml-auto text-xs" onClick={cargar}><RefreshCw className="h-3.5 w-3.5" />Recargar</button>
          <button className="btn-ghost text-xs" onClick={restablecer}><RotateCcw className="h-3.5 w-3.5" />Restablecer</button>
          <button className="btn-primary text-xs" onClick={guardar} disabled={!cambios}><Save className="h-3.5 w-3.5" />Guardar</button>
        </div>
        {modos && perfiles && (
          <table className="w-full min-w-[640px] text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-slate-500">
                <th className="py-2 pr-3 font-medium">Tarea</th>
                {MODOS.map((m) => <th key={m.id} className="py-2 pr-3 font-medium">{m.label}</th>)}
              </tr>
            </thead>
            <tbody>
              {ROLES.map((r) => (
                <tr key={r.id} className="border-t border-slate-800 align-top">
                  <td className="py-2 pr-3">
                    <p className="text-slate-200">{r.label}</p>
                    <p className="text-[11px] text-slate-500">{r.ayuda}</p>
                  </td>
                  {MODOS.map((m) => {
                    const a = modos[m.id]?.[r.id];
                    if (!a) return <td key={m.id} />;
                    const info = perfiles.modelos[a.model];
                    const modificado = perfiles.por_defecto[m.id]?.[r.id]?.model !== a.model;
                    return (
                      <td key={m.id} className="py-2 pr-3">
                        <select aria-label={`${r.label} en modo ${m.label}`} value={a.model}
                                onChange={(e) => cambiar(m.id, r.id, { model: e.target.value })}
                                className={`w-full rounded-md border bg-slate-900 px-2 py-1 text-xs ${modificado ? "border-amber-600" : "border-slate-700"}`}>
                          {Object.entries(perfiles.modelos).map(([alias, mo]) => (
                            <option key={alias} value={alias}>{mo.disponible ? "" : "⚠ "}{mo.etiqueta}</option>
                          ))}
                        </select>
                        <select aria-label={`Razonamiento de ${r.label} en modo ${m.label}`} value={a.effort}
                                onChange={(e) => cambiar(m.id, r.id, { effort: e.target.value as Asignacion["effort"] })}
                                className="mt-1 w-full rounded-md border border-slate-700 bg-slate-900 px-2 py-1 text-xs">
                          {(info?.efforts ?? []).map((ef) => <option key={ef} value={ef}>razonamiento {ef}</option>)}
                        </select>
                        {info && !info.disponible && <p className="mt-0.5 text-[11px] text-amber-300">proveedor no disponible: se usará su alternativa</p>}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <p className="mt-3 text-[11px] text-slate-500">
          Si el modelo elegido falla, se agota su cuota o su CLI no tiene sesión, la consulta pasa automáticamente a la
          siguiente alternativa definida en <code>config/models.toml</code> y la interfaz lo avisa.
        </p>
      </section>
    </div>
  );
}
