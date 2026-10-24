import { useEffect, useState } from "react";
import { AlertCircle } from "lucide-react";
import { Composer, SUGERENCIAS } from "./components/Composer";
import { Answer, Clarification, ProcessDetails, ProgressLine, type AbrirFuente } from "./components/Results";
import { SettingsPage } from "./components/settings/SettingsPage";
import { Sidebar } from "./components/Sidebar";
import { SourceViewer, type FuenteAbierta } from "./components/SourceViewer";
import { TopBar } from "./components/TopBar";
import type { Modo } from "./lib/types";
import { useConsulta } from "./lib/useConsulta";
import { api, type Sesion } from "./lib/api";

function leer<T extends string>(clave: string, defecto: T): T {
  try {
    return (localStorage.getItem(clave) as T) || defecto;
  } catch {
    return defecto;
  }
}
function guardar(clave: string, valor: string) {
  try { localStorage.setItem(clave, valor); } catch { /* almacenamiento no disponible */ }
}

export default function App() {
  const [modo, setModo] = useState<Modo>(() => leer<Modo>("iuris-modo", "equilibrado"));
  const [vista, setVista] = useState<"consulta" | "ajustes">("consulta");
  const [lateral, setLateral] = useState(() => leer("iuris-lateral", window.innerWidth >= 1024 ? "1" : "0") === "1");
  const [fuente, setFuente] = useState<FuenteAbierta | null>(null);
  const [sugerencia, setSugerencia] = useState<string | undefined>();
  const [refresco, setRefresco] = useState(0);
  const { state, nueva, abrir, responder, limpiar } = useConsulta();
  const [sesion, setSesion] = useState<Sesion>({ rol: "dueno", modos_permitidos: ["eco", "equilibrado", "pro"] });
  const invitado = sesion.rol === "invitado";

  useEffect(() => {
    api.sesion().then((s) => {
      setSesion(s);
      // Un invitado solo puede usar los modos que permita quien comparte la app (por defecto, Eco).
      if (s.rol === "invitado" && !s.modos_permitidos.includes(modo)) setModo((s.modos_permitidos[0] ?? "eco") as Modo);
    }).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const cambiarModo = (m: Modo) => { setModo(m); guardar("iuris-modo", m); };
  const alternarLateral = () => setLateral((v) => { guardar("iuris-lateral", v ? "0" : "1"); return !v; });
  const cerrarLateralEnMovil = () => window.innerWidth < 768 && setLateral(false);
  const abrirFuente: AbrirFuente = (sourceId, quote) => setFuente({ sourceId, quote });
  const enviar = async (texto: string, municipio: string | null, adjuntos: string[]) => {
    setFuente(null);
    await nueva(texto, modo, municipio, adjuntos);
    setRefresco((r) => r + 1);
  };

  const inicio = vista === "consulta" && !state.id;
  const puedePreguntar = !state.id || state.final || state.error;

  return (
    <div className="flex h-full bg-bg">
      {lateral && (
        <div className="fixed inset-0 z-20 bg-black/30 md:hidden print:hidden" onClick={() => setLateral(false)} aria-hidden />
      )}
      <Sidebar abierta={lateral} actual={state.id} refresco={refresco + (state.final ? 1 : 0)}
               onAbrir={(id) => { setVista("consulta"); setFuente(null); cerrarLateralEnMovil(); void abrir(id); }}
               onNueva={() => { setVista("consulta"); setFuente(null); cerrarLateralEnMovil(); limpiar(); }} />
      <div className="flex min-w-0 flex-1 flex-col">
        {invitado && (
          <p className="bg-surface px-4 py-1.5 text-center text-xs text-ink-2 print:hidden">
            Estás usando Desemppa en el ordenador de otra persona: tus consultas se procesan allí y esa persona puede verlas.
          </p>
        )}
        <TopBar modo={modo} onModo={cambiarModo} onMenu={alternarLateral} enAjustes={vista === "ajustes"}
                invitado={invitado} permitidos={sesion.modos_permitidos.filter((m) => m !== "auditoria")}
                onAjustes={() => { setFuente(null); setVista((v) => (v === "ajustes" ? "consulta" : "ajustes")); }} />
        <div className="flex min-h-0 flex-1">
          <main className="flex min-w-0 flex-1 flex-col">
            {vista === "ajustes" && !invitado ? (
              <div className="flex-1 overflow-auto scroll-thin"><SettingsPage /></div>
            ) : inicio ? (
              <div className="flex flex-1 flex-col items-center justify-center overflow-auto px-4 pb-10">
                <div className="w-full max-w-3xl">
                  <h1 className="mb-2 text-center text-[40px] font-normal leading-tight tracking-tight text-ink">
                    ¿En qué te puedo ayudar?
                  </h1>
                  <p className="mb-8 text-center text-base text-ink-2">
                    Analizo tu caso con la ley vigente y compruebo cada cita contra el texto oficial.
                  </p>
                  <Composer variante="hero" onEnviar={enviar} ocupado={state.streaming} textoInicial={sugerencia} />
                  <div className="mt-6 flex flex-wrap justify-center gap-2">
                    {SUGERENCIAS.map((s) => (
                      <button key={s.corto} className="chip" onClick={() => setSugerencia(s.texto)}>{s.corto}</button>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <>
                <div className="flex-1 overflow-auto scroll-thin">
                  <div className="mx-auto max-w-[760px] space-y-8 px-4 pb-10 pt-4 sm:px-6">
                    {state.pregunta && (
                      <div className="flex justify-end">
                        <p className="max-w-[85%] whitespace-pre-line rounded-[24px] rounded-tr-md bg-surface-2 px-5 py-3 text-[15px] text-ink">
                          {state.pregunta}
                        </p>
                      </div>
                    )}
                    <ProgressLine estado={state.estado} streaming={state.streaming} />
                    {state.error && (
                      <div role="alert" className="flex gap-3 rounded-2xl bg-danger-container px-4 py-3 text-sm text-danger">
                        <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />{state.error}
                      </div>
                    )}
                    {state.avisosQuota.length > 0 && !state.final && (
                      <p className="text-sm text-ink-2">
                        Algún modelo no estaba disponible y se ha usado otro: {state.avisosQuota[state.avisosQuota.length - 1]}
                      </p>
                    )}
                    {state.estado === "ESPERANDO_ACLARACION" && state.preguntas.length > 0 && (
                      <Clarification preguntas={state.preguntas} onResponder={responder} />
                    )}
                    <Answer state={state} onAbrir={abrirFuente} />
                    <ProcessDetails state={state} onAbrir={abrirFuente} />
                  </div>
                </div>
                {puedePreguntar && (
                  <div className="mx-auto w-full max-w-[760px] px-4 pb-3 sm:px-6 print:hidden">
                    <Composer variante="dock" onEnviar={enviar} ocupado={state.streaming} />
                  </div>
                )}
              </>
            )}
          </main>
          <SourceViewer abierta={vista === "consulta" ? fuente : null} consultaId={state.id} onClose={() => setFuente(null)} />
        </div>
      </div>
    </div>
  );
}
