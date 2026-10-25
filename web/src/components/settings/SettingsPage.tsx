import { useEffect, useState } from "react";
import { api, type Asignacion, type Perfiles, type Proveedor } from "../../lib/api";
import { aplicarTema, leerTema, type Tema } from "../../lib/theme";
import { Seccion } from "../ui/primitives";
import { Salud } from "./Salud";
import { Accounts } from "./Accounts";
import { CustomModels } from "./CustomModels";
import { LanShare } from "./LanShare";
import { MODOS_AJUSTES, Modes } from "./Modes";

const INDICE = [
  { id: "modos", label: "Modos" },
  { id: "cuentas", label: "Cuentas y planes" },
  { id: "salud", label: "Salud de los modelos" },
  { id: "modelos", label: "Modelos personalizados" },
  { id: "red", label: "Red local" },
  { id: "apariencia", label: "Apariencia" },
];

export function SettingsPage() {
  const [proveedores, setProveedores] = useState<Record<string, Proveedor> | null>(null);
  const [perfiles, setPerfiles] = useState<Perfiles | null>(null);
  const [modos, setModos] = useState<Perfiles["modos"] | null>(null);
  const [respaldo, setRespaldo] = useState<Perfiles["respaldo"] | null>(null);
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [tema, setTema] = useState<Tema>(leerTema);

  const cargar = () => {
    api.proveedores().then(setProveedores).catch((e) => setMensaje(e.message));
    api.perfiles().then((p) => { setPerfiles(p); setModos(p.modos); setRespaldo(p.respaldo); })
      .catch((e) => setMensaje(e.message));
  };
  useEffect(cargar, []);

  /** Aplica el cambio y, si el modelo nuevo no admite el esfuerzo actual, usa «medium» o el primero que admita. */
  const ajustar = (a: Asignacion, cambio: Partial<Asignacion>): Asignacion => {
    const sig = { ...a, ...cambio };
    const efforts = perfiles?.modelos[sig.model]?.efforts ?? [];
    if (efforts.includes(sig.effort)) return sig;
    return { ...sig, effort: (efforts.includes("medium") ? "medium" : efforts[0]) as Asignacion["effort"] };
  };
  const cambiar = (modo: string, rol: string, cambio: Partial<Asignacion>) => {
    if (!modos) return;
    setModos({ ...modos, [modo]: { ...modos[modo], [rol]: ajustar(modos[modo][rol], cambio) } });
  };
  const todoElModo = (modo: string, alias: string) => {
    if (!modos) return;
    const roles = Object.fromEntries(Object.entries(modos[modo]).map(([rol, a]) => [rol, ajustar(a, { model: alias })]));
    setModos({ ...modos, [modo]: roles });
  };
  const guardar = async () => {
    if (!modos) return;
    try {
      await api.guardarPerfiles(
        Object.fromEntries(MODOS_AJUSTES.map((m) => [m.id, modos[m.id]])),
        Object.fromEntries(MODOS_AJUSTES.filter((m) => respaldo?.[m.id]).map((m) => [m.id, respaldo![m.id]])),
      );
      setMensaje("Guardado. Se aplica a las próximas consultas.");
      cargar();
    } catch (e) {
      setMensaje(`No se ha guardado: ${(e as Error).message}`);
    }
  };
  const restablecer = async () => {
    await api.restablecerPerfiles();
    setMensaje("Asignación de modelos restablecida a la configuración por defecto.");
    cargar();
  };
  const cambios = modos && perfiles
    ? JSON.stringify(modos) !== JSON.stringify(perfiles.modos) || JSON.stringify(respaldo) !== JSON.stringify(perfiles.respaldo)
    : false;

  return (
    <div className="mx-auto flex max-w-5xl gap-10 px-4 pb-24 pt-4 sm:px-6">
      <nav aria-label="Secciones de ajustes" className="sticky top-4 hidden h-fit w-48 shrink-0 lg:block">
        <h1 className="mb-4 text-2xl text-ink">Ajustes</h1>
        <ul className="space-y-0.5">
          {INDICE.map((s) => (
            <li key={s.id}><a href={`#${s.id}`} className="block rounded-full px-4 py-2 text-sm text-ink hover:bg-surface-2">{s.label}</a></li>
          ))}
        </ul>
      </nav>
      <div className="min-w-0 flex-1 space-y-12">
        <h1 className="text-2xl text-ink lg:hidden">Ajustes</h1>
        {mensaje && (
          <p role="status" className="fade-in rounded-2xl bg-accent-container px-4 py-3 text-sm text-on-accent-container">{mensaje}</p>
        )}
        <Seccion id="modos" titulo="Modos" descripcion="Qué modelo y con cuánto esfuerzo hace cada tarea en cada modo.">
          {perfiles && modos && (
            <Modes perfiles={perfiles} modos={modos} respaldo={respaldo ?? perfiles.respaldo} onCambiar={cambiar}
                   onTodoElModo={todoElModo}
                   onRespaldo={(modo, valor) => setRespaldo({ ...(respaldo ?? perfiles.respaldo), [modo]: valor })} />
          )}
          <div className="mt-4 flex gap-2">
            <button className="btn-primary" onClick={guardar} disabled={!cambios}>Guardar cambios</button>
            <button className="btn-ghost" onClick={restablecer}>Restablecer</button>
          </div>
        </Seccion>
        <Seccion id="cuentas" titulo="Cuentas y planes" descripcion="El estado refleja la última llamada real a cada proveedor.">
          <Accounts proveedores={proveedores} perfiles={perfiles} onCambio={cargar} onMensaje={setMensaje} />
        </Seccion>
        <Seccion id="salud" titulo="Salud de los modelos"
                 descripcion="Cómo han respondido los modelos en este equipo: fallos, respuestas vacías y tiempos (llamadas reales).">
          <Salud />
        </Seccion>
        <Seccion id="modelos" titulo="Modelos personalizados" descripcion="Añade modelos que no estén en el catálogo.">
          <CustomModels proveedores={proveedores} onCambio={cargar} onMensaje={setMensaje} />
        </Seccion>
        <Seccion id="red" titulo="Compartir en la red local"
                 descripcion="Deja que otras personas de tu wifi usen Desemppa desde su ordenador; todo se ejecuta en este.">
          <LanShare onMensaje={setMensaje} />
        </Seccion>
        <Seccion id="apariencia" titulo="Apariencia">
          <div role="radiogroup" aria-label="Tema" className="inline-flex rounded-full border border-outline p-1">
            {(["sistema", "claro", "oscuro"] as Tema[]).map((t) => (
              <button key={t} role="radio" aria-checked={tema === t}
                      onClick={() => { setTema(t); aplicarTema(t); }}
                      className={`rounded-full px-4 py-1.5 text-sm transition-colors ${
                        tema === t ? "bg-accent-container text-on-accent-container" : "text-ink-2 hover:text-ink"}`}>
                {{ sistema: "Como el sistema", claro: "Claro", oscuro: "Oscuro" }[t]}
              </button>
            ))}
          </div>
        </Seccion>
      </div>
    </div>
  );
}
