import { useEffect, useState } from "react";
import { Check, Copy, Loader2 } from "lucide-react";
import { ApiError, QR_RED_URL, api, type EstadoRed } from "../../lib/api";
import { Switch } from "../ui/primitives";

const ETIQUETA: Record<string, string> = { eco: "Eco", equilibrado: "Equilibrado", pro: "Pro", auditoria: "Auditoría" };

/** Interruptor en vivo para que otros equipos de la wifi usen Desemppa en este ordenador. */
export function LanShare({ onMensaje }: { onMensaje: (m: string) => void }) {
  const [red, setRed] = useState<EstadoRed | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [copiado, setCopiado] = useState(false);

  const [bloqueo, setBloqueo] = useState<string | null>(null);

  useEffect(() => {
    let t: ReturnType<typeof setInterval> | undefined;
    const cargar = () => api.red().then(setRed).catch((e) => {
      // 404/403: el servidor no tiene esta función (versión anterior) o no la permite. No se reintenta en bucle.
      if (e instanceof ApiError && (e.status === 404 || e.status === 403)) {
        clearInterval(t);
        setBloqueo(e.status === 404
          ? "El servidor en marcha es de una versión anterior. Ciérralo y abre INICIAR_DESEMPPA.bat para activar esta función."
          : "Esta opción solo está disponible en el ordenador donde se ejecuta Desemppa.");
        return;
      }
      onMensaje(e.message);
    });
    cargar();
    t = setInterval(cargar, 5000);
    return () => clearInterval(t);
  }, [onMensaje]);

  const ajustar = async (cambio: { activo?: boolean; modos_permitidos?: string[]; tope_diario?: number }) => {
    setOcupado(true);
    try {
      setRed(await api.ajustarRed(cambio));
    } catch (e) {
      onMensaje(`No se pudo cambiar la red local: ${(e as Error).message}`);
    } finally {
      setOcupado(false);
    }
  };

  if (bloqueo) {
    return <p role="alert" className="rounded-xl bg-warning-container px-4 py-3 text-sm text-warning">{bloqueo}</p>;
  }
  if (!red) return <Loader2 className="h-5 w-5 animate-spin text-ink-3" />;
  const extra = red.modos_disponibles.filter((m) => m !== "eco");

  return (
    <div className="space-y-4 rounded-3xl bg-surface p-5">
      <div className="flex items-center gap-4">
        <div className="min-w-0 flex-1">
          <p className="text-sm text-ink">Permitir el acceso desde otros equipos de tu red</p>
          <p className="text-xs text-ink-2">
            {red.activo
              ? `Activo · ${red.invitados_activos} ${red.invitados_activos === 1 ? "persona conectada" : "personas conectadas"} · ${red.consultas_hoy} consultas de invitados hoy`
              : "Desactivado: solo se puede usar desde este ordenador."}
          </p>
        </div>
        <Switch checked={red.activo} disabled={ocupado || !red.escucha_red || !red.ip}
                onChange={(v) => ajustar({ activo: v })} label="Compartir en la red local" />
      </div>

      {!red.escucha_red && (
        <p className="rounded-xl bg-warning-container px-3 py-2 text-sm text-warning">
          El servidor se ha arrancado solo para este equipo. Ciérralo y ábrelo con <code>INICIAR_DESEMPPA.bat</code> para
          poder compartirlo.
        </p>
      )}
      {red.escucha_red && !red.ip && (
        <p className="rounded-xl bg-warning-container px-3 py-2 text-sm text-warning">
          No se ha encontrado una red local (wifi o cable) en este equipo.
        </p>
      )}

      {red.activo && red.url && (
        <div className="fade-in flex flex-wrap items-center gap-2 rounded-2xl bg-bg px-4 py-3">
          <span className="text-sm text-ink-2">Enlace para la otra persona:</span>
          <code className="text-base text-ink">{red.url}</code>
          <button className="btn-ghost ml-auto px-3 py-1.5" onClick={() => navigator.clipboard?.writeText(red.url!).then(() => {
            setCopiado(true);
            setTimeout(() => setCopiado(false), 1500);
          })}>
            {copiado ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}{copiado ? "Copiado" : "Copiar"}
          </button>
          <div className="flex w-full items-center gap-4 pt-2">
            <img src={`${QR_RED_URL}?u=${encodeURIComponent(red.url)}`} alt={`Código QR del enlace ${red.url}`}
                 width={132} height={132} className="rounded-lg bg-white p-1" />
            <p className="text-sm text-ink-2">Desde el móvil o la tableta: abre la cámara y apunta a este código para entrar sin teclear la
              dirección. Tiene que estar conectado a la misma wifi.</p>
          </div>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
        <div>
          <p className="label">Modos que pueden usar</p>
          <div className="flex flex-wrap gap-3 text-sm text-ink">
            <label className="flex items-center gap-1.5 text-ink-2"><input type="checkbox" checked disabled /> Eco</label>
            {extra.map((m) => (
              <label key={m} className="flex items-center gap-1.5">
                <input type="checkbox" checked={red.modos_permitidos.includes(m)} disabled={ocupado}
                       onChange={(e) => ajustar({
                         modos_permitidos: e.target.checked
                           ? [...red.modos_permitidos, m]
                           : red.modos_permitidos.filter((x) => x !== m),
                       })} />
                {ETIQUETA[m] ?? m}
              </label>
            ))}
          </div>
        </div>
        <label className="block">
          <span className="label">Consultas por persona y día</span>
          <input type="number" min={1} max={200} className="field w-24 py-1.5" defaultValue={red.tope_diario}
                 onBlur={(e) => {
                   const n = Number(e.target.value);
                   if (n >= 1 && n <= 200 && n !== red.tope_diario) void ajustar({ tope_diario: n });
                 }} />
        </label>
      </div>

      <ul className="list-disc space-y-1 pl-5 text-xs text-ink-2">
        <li>Todo se ejecuta en este ordenador con tu suscripción; cada persona puede tener una consulta a la vez y las
          consultas se atienden de una en una.</li>
        <li>La primera vez, Windows puede preguntar si permite el acceso de Python a la red: acepta solo en redes
          privadas. Tu wifi debe estar configurada como «Privada».</li>
        <li>La conexión no va cifrada (HTTP): úsalo solo en una red de confianza y desactívalo al terminar. Al
          reiniciar Desemppa se desactiva sola.</li>
        <li>Las suscripciones son personales: compartirlas de forma continuada puede ir contra sus condiciones de uso.</li>
        <li>Tú ves en tu historial las consultas de los invitados (marcadas); cada invitado solo ve las suyas.</li>
      </ul>
    </div>
  );
}
