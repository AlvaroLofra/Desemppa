import { useState } from "react";
import { AlertOctagon, Scale } from "lucide-react";
import { Composer } from "./components/Composer";
import { Header } from "./components/Header";
import {
  ClarificationForm, DebateTabs, FinalView, PhaseStepper, SourcesList, TriageCard, type AbrirFuente,
} from "./components/Results";
import { ModelsPage } from "./components/ModelsPage";
import { Sidebar } from "./components/Sidebar";
import { SourceViewer, type FuenteAbierta } from "./components/SourceViewer";
import type { Modo } from "./lib/types";
import { useConsulta } from "./lib/useConsulta";

function leerModo(): Modo {
  try {
    return (localStorage.getItem("iuris-modo") as Modo) || "equilibrado";
  } catch {
    return "equilibrado";
  }
}

export default function App() {
  const [modo, setModo] = useState<Modo>(leerModo);
  const [vista, setVista] = useState<"consulta" | "modelos">("consulta");
  const [fuente, setFuente] = useState<FuenteAbierta | null>(null);
  const [refresco, setRefresco] = useState(0);
  const { state, nueva, abrir, responder, limpiar } = useConsulta();

  const cambiarModo = (m: Modo) => {
    setModo(m);
    try { localStorage.setItem("iuris-modo", m); } catch { /* almacenamiento no disponible */ }
  };
  const abrirFuente: AbrirFuente = (sourceId, quote) => setFuente({ sourceId, quote });
  const enviar = async (texto: string, municipio: string | null, adjuntos: string[]) => {
    setFuente(null);
    await nueva(texto, modo, municipio, adjuntos);
    setRefresco((r) => r + 1);
  };

  return (
    <div className="flex h-full flex-col">
      <Header modo={modo} onModo={cambiarModo} enModelos={vista === "modelos"}
              onModelos={() => setVista((v) => (v === "modelos" ? "consulta" : "modelos"))} />
      <div className="flex min-h-0 flex-1">
        <Sidebar actual={state.id} refresco={refresco + (state.final ? 1 : 0)}
                 onAbrir={(id) => { setVista("consulta"); setFuente(null); void abrir(id); }}
                 onNueva={() => { setVista("consulta"); setFuente(null); limpiar(); }} />
        <main className="min-w-0 flex-1 overflow-auto scroll-thin">
          {vista === "modelos" ? <ModelsPage /> : (
          <div className="mx-auto max-w-3xl space-y-4 px-4 py-6">
            {!state.id && (
              <div className="pb-2 pt-8 text-center">
                <Scale className="mx-auto h-10 w-10 text-amber-400" aria-hidden />
                <h1 className="mt-3 text-2xl font-semibold tracking-tight text-slate-100">¿Qué problema legal tienes?</h1>
                <p className="mx-auto mt-2 max-w-lg text-sm text-slate-400">
                  Analizo tu caso con la ley vigente del BOE y jurisprudencia, enfrentando tus argumentos con los de la otra
                  parte. Cada cita se comprueba contra el texto oficial y los plazos se calculan con el calendario judicial.
                </p>
              </div>
            )}
            {state.id && <PhaseStepper estado={state.estado} streaming={state.streaming} />}
            {state.error && (
              <div role="alert" className="flex gap-2 rounded-xl border border-rose-800 bg-rose-950/40 p-3 text-sm text-rose-200">
                <AlertOctagon className="h-4 w-4 shrink-0" />{state.error}
              </div>
            )}
            {state.avisosQuota.length > 0 && (
              <p className="rounded-lg border border-amber-800/60 bg-amber-950/30 px-3 py-2 text-xs text-amber-200">
                Algún modelo no estaba disponible y se ha usado otro: {state.avisosQuota[state.avisosQuota.length - 1]}
              </p>
            )}
            <TriageCard state={state} />
            {state.estado === "ESPERANDO_ACLARACION" && state.preguntas.length > 0 && (
              <ClarificationForm preguntas={state.preguntas} onResponder={responder} />
            )}
            <SourcesList fuentes={state.fuentes} onAbrir={abrirFuente} />
            <DebateTabs state={state} onAbrir={abrirFuente} />
            <FinalView state={state} onAbrir={abrirFuente} />
            {(!state.id || state.final || state.error) && (
              <Composer onEnviar={enviar} ocupado={state.streaming} />
            )}
          </div>
          )}
        </main>
        <SourceViewer abierta={fuente} consultaId={state.id} onClose={() => setFuente(null)} />
      </div>
    </div>
  );
}
