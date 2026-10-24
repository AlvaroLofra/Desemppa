import { useState } from "react";
import { KeyRound, Loader2, Search } from "lucide-react";
import { api, type Perfiles, type Proveedor } from "../../lib/api";
import { Dialog, Switch } from "../ui/primitives";

function estado(p: Proveedor): { texto: string; tono: "ok" | "neutro" | "aviso" | "error" } {
  if (!p.habilitado) return { texto: "Desactivado", tono: "neutro" };
  if (!p.instalado) return { texto: p.modalidad === "api" ? "Falta la clave de API" : "Programa no instalado", tono: "error" };
  if (p.breaker.estado === "open") return { texto: "Cuota agotada por ahora: se usa otro", tono: "aviso" };
  if (!p.ultima_llamada) return { texto: "Listo · aún sin usar", tono: "neutro" };
  if (p.ultima_llamada.ok) return { texto: "Funcionando", tono: "ok" };
  if (p.ultima_llamada.error_tipo === "NotAuthenticated")
    return { texto: p.modalidad === "api" ? "Clave de API no válida" : "Sin sesión iniciada", tono: "error" };
  return { texto: `Último error: ${p.ultima_llamada.error_tipo}`, tono: "error" };
}

const TONO = { ok: "bg-success", neutro: "bg-ink-3", aviso: "bg-warning", error: "bg-danger" } as const;

function Fila({ pid, p, perfiles, onCambio, onMensaje }: {
  pid: string;
  p: Proveedor;
  perfiles: Perfiles | null;
  onCambio: () => void;
  onMensaje: (m: string) => void;
}) {
  const [ocupado, setOcupado] = useState(false);
  const [detectados, setDetectados] = useState<string[] | "cargando" | null>(null);
  const [pruebas, setPruebas] = useState<Record<string, string>>({});
  const [dialogo, setDialogo] = useState(false);
  const [clave, setClave] = useState("");
  const st = estado(p);

  const configurar = async (body: { api_key?: string; habilitado?: boolean }) => {
    setOcupado(true);
    try {
      await api.configurarProveedor(pid, body);
      onCambio();
    } catch (e) {
      onMensaje(`No se pudo actualizar ${p.etiqueta}: ${(e as Error).message}`);
    } finally {
      setOcupado(false);
    }
  };
  const probar = async (alias: string) => {
    setPruebas((x) => ({ ...x, [alias]: "probando…" }));
    try {
      const r = await api.probar(alias);
      setPruebas((x) => ({ ...x, [alias]: r.ok ? `correcto en ${(r.latencia_ms / 1000).toFixed(1)} s` : r.error ?? "error" }));
    } catch (e) {
      setPruebas((x) => ({ ...x, [alias]: (e as Error).message }));
    }
    onCambio();
  };
  const detectar = async () => {
    setDetectados("cargando");
    try {
      const r = await api.detectar(pid);
      setDetectados(r.instalado ? r.modelos : []);
    } catch (e) {
      onMensaje((e as Error).message);
      setDetectados(null);
    }
  };

  return (
    <li className="py-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-sm text-ink">{p.etiqueta}</p>
          <p className="flex items-center gap-1.5 text-xs text-ink-2">
            <span className={`h-1.5 w-1.5 rounded-full ${TONO[st.tono]}`} aria-hidden />{st.texto}
            {p.version ? ` · ${p.version}` : ""}
            {p.uso_ultimas_5h.llamadas > 0 && ` · ${p.uso_ultimas_5h.llamadas} llamadas en 5 h`}
          </p>
        </div>
        {p.modalidad === "api" && (
          <button className="btn-ghost px-3 py-1.5" onClick={() => setDialogo(true)}><KeyRound className="h-4 w-4" />Clave</button>
        )}
        {p.habilitado && p.instalado && (
          <button className="btn-ghost px-3 py-1.5" onClick={detectar} disabled={detectados === "cargando"}>
            {detectados === "cargando" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}Detectar
          </button>
        )}
        <Switch checked={p.habilitado} onChange={(v) => configurar({ habilitado: v })} disabled={ocupado}
                label={`${p.habilitado ? "Desactivar" : "Activar"} ${p.etiqueta}`} />
      </div>
      {p.habilitado && (st.tono === "error") && p.login && (
        <p className="mt-2 rounded-xl bg-surface-2 px-3 py-2 text-xs text-ink">{p.login}</p>
      )}
      {Array.isArray(detectados) && (
        <p className="mt-2 text-xs text-ink-2">Modelos que ofrece: {detectados.length ? detectados.join(", ") : "ninguno"}</p>
      )}
      {p.habilitado && p.instalado && p.modelos.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-2">
          {p.modelos.map((alias) => (
            <button key={alias} className="chip py-1 text-xs" onClick={() => probar(alias)} title="Hacer una llamada mínima de prueba">
              Probar {perfiles?.modelos[alias]?.etiqueta ?? alias}
              {pruebas[alias] && <span className="text-ink-3">· {pruebas[alias]}</span>}
            </button>
          ))}
        </div>
      )}
      {dialogo && (
        <Dialog titulo={`Clave de ${p.compania}`} onClose={() => setDialogo(false)}>
          <p className="mb-3 text-sm text-ink-2">
            Se guarda cifrada en tu equipo con Windows DPAPI. También puedes definir {p.api_key_env ?? "la variable"} en
            el fichero <code>.env</code>.
          </p>
          <input type="password" className="field" value={clave} onChange={(e) => setClave(e.target.value)}
                 placeholder={p.instalado ? "Hay una clave guardada; pega otra para cambiarla" : "Pega la clave"}
                 aria-label="Clave de API" />
          <div className="mt-5 flex justify-end gap-2">
            <button className="btn-ghost" onClick={() => setDialogo(false)}>Cancelar</button>
            <button className="btn-primary" disabled={!clave.trim() || ocupado} onClick={async () => {
              await configurar({ api_key: clave.trim(), habilitado: true });
              setClave("");
              setDialogo(false);
            }}>Guardar</button>
          </div>
        </Dialog>
      )}
    </li>
  );
}

/** Proveedores por plan (programas locales) y por clave de API, con su estado real. */
export function Accounts({ proveedores, perfiles, onCambio, onMensaje }: {
  proveedores: Record<string, Proveedor> | null;
  perfiles: Perfiles | null;
  onCambio: () => void;
  onMensaje: (m: string) => void;
}) {
  if (!proveedores) return <Loader2 className="h-5 w-5 animate-spin text-ink-3" />;
  const grupos = [
    { titulo: "Tus planes", nota: "Programas locales con tu suscripción: sin coste por consulta.",
      items: Object.entries(proveedores).filter(([, p]) => p.modalidad !== "api") },
    { titulo: "APIs por clave", nota: "Opcionales, de pago por uso.",
      items: Object.entries(proveedores).filter(([, p]) => p.modalidad === "api") },
  ];
  return (
    <div className="space-y-6">
      {grupos.map((g) => (
        <div key={g.titulo} className="rounded-3xl bg-surface px-5 pt-4">
          <h3 className="text-base font-medium text-ink">{g.titulo}</h3>
          <p className="text-xs text-ink-2">{g.nota}</p>
          <ul className="divide-y divide-outline">
            {g.items.map(([pid, p]) => (
              <Fila key={pid} pid={pid} p={p} perfiles={perfiles} onCambio={onCambio} onMensaje={onMensaje} />
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
