import { useCallback, useEffect, useRef, useState } from "react";
import { AlertCircle, X } from "lucide-react";
import { AyudaAtajos } from "./components/Atajos";
import { Biblioteca } from "./components/Biblioteca";
import { Comparar } from "./components/Comparar";
import { useHojaDeRuta } from "./components/HojaDeRuta";
import { Composer, SUGERENCIAS } from "./components/Composer";
import {
  Answer, Clarification, ImprimiendoContext, ProcesoImpresion, ProcessDetails, ProgressLine, type AbrirFuente,
} from "./components/Results";
import { SettingsPage } from "./components/settings/SettingsPage";
import { Sidebar } from "./components/Sidebar";
import { SourceViewer, type FuenteAbierta } from "./components/SourceViewer";
import { TopBar } from "./components/TopBar";
import type { Modo } from "./lib/types";
import { useConsulta } from "./lib/useConsulta";
import { ApiError, api, type Sesion } from "./lib/api";
import { accionAtajo } from "./lib/atajos";
import { descargar, nombreFichero } from "./lib/descargar";
import { expedienteMarkdown } from "./lib/expediente";
import { pedirPermisoNotificaciones, useFinAnalisis } from "./lib/finAnalisis";

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
  const [vista, setVista] = useState<"consulta" | "ajustes" | "biblioteca" | "comparar">("consulta");
  const [lectura, setLectura] = useState(false);
  const [profesional, setProfesional] = useState(() => leer<string>("iuris-profesional", "0") === "1");
  const [imprimiendo, setImprimiendo] = useState(false);
  const [ayuda, setAyuda] = useState(false);
  const [lateral, setLateral] = useState(() => leer("iuris-lateral", window.innerWidth >= 1024 ? "1" : "0") === "1");
  const [fuente, setFuente] = useState<FuenteAbierta | null>(null);
  const [sugerencia, setSugerencia] = useState<string | undefined>();
  const [refresco, setRefresco] = useState(0);
  const { state, nueva, abrir, responder, limpiar, detener } = useConsulta();
  const scrollRef = useRef<HTMLDivElement>(null);
  const respuestaRef = useRef<HTMLDivElement>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const { marcarEnVivo } = useFinAnalisis(state, scrollRef, respuestaRef, setAviso);
  const pasos = useHojaDeRuta(state.final ? state.triage?.submateria_principal : null, state.triage?.fecha_hechos);
  const [sesion, setSesion] = useState<Sesion>({ rol: "dueno", modos_permitidos: ["eco", "equilibrado", "pro"] });
  const invitado = sesion.rol === "invitado";
  const [servidorAntiguo, setServidorAntiguo] = useState(false);

  // Los invitados ven la cola: la sesión se refresca cada 20 s.
  useEffect(() => {
    if (!invitado) return;
    const t = setInterval(() => { api.sesion().then(setSesion).catch(() => undefined); }, 20_000);
    return () => clearInterval(t);
  }, [invitado]);

  useEffect(() => {
    api.sesion().then((s) => {
      setSesion(s);
      // Un invitado solo puede usar los modos que permita quien comparte la app (por defecto, Eco).
      if (s.rol === "invitado" && !s.modos_permitidos.includes(modo)) setModo((s.modos_permitidos[0] ?? "eco") as Modo);
    }).catch((e) => {
      // La interfaz es más nueva que el servidor en marcha (se actualizó sin reiniciarlo).
      if (e instanceof ApiError && e.status === 404) setServidorAntiguo(true);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const cambiarModo = (m: Modo) => { setModo(m); guardar("iuris-modo", m); };
  const alternarLateral = () => setLateral((v) => { guardar("iuris-lateral", v ? "0" : "1"); return !v; });
  const cerrarLateralEnMovil = () => window.innerWidth < 768 && setLateral(false);
  const abrirFuente: AbrirFuente = (sourceId, quote) => setFuente({ sourceId, quote });
  // El municipio no se pide al empezar: se deduce del relato o se pregunta solo si hace falta (plazos, foral).
  const enviar = async (texto: string, adjuntos: string[]) => {
    setFuente(null);
    pedirPermisoNotificaciones();
    marcarEnVivo();
    await nueva(texto, modo, null, adjuntos);
    setRefresco((r) => r + 1);
  };

  const irA = (v: typeof vista) => { setFuente(null); setLectura(false); setVista(v); cerrarLateralEnMovil(); };

  const exportar = useCallback(() => {
    if (!state.final) {
      setAviso("Aún no hay un resultado que exportar.");
      return;
    }
    descargar(`expediente-${nombreFichero(state.pregunta ?? "consulta")}.md`, expedienteMarkdown(state, new Date(), pasos), "text/markdown");
  }, [state, pasos]);

  // PDF: se abren todos los plegables (proceso, verificación, avisos), se imprime y se vuelven a cerrar.
  useEffect(() => {
    if (!imprimiendo) return;
    const fin = () => setImprimiendo(false);
    window.addEventListener("afterprint", fin);
    const t = setTimeout(() => window.print(), 80);
    return () => { clearTimeout(t); window.removeEventListener("afterprint", fin); };
  }, [imprimiendo]);

  useEffect(() => { setLectura(false); }, [state.id]);

  // Aviso de reforma: si un artículo citado ha cambiado de redacción desde la consulta, se dice.
  const conResultado = Boolean(state.final?.dictamen);
  useEffect(() => {
    if (!state.id || !conResultado) return;
    let vivo = true;
    api.vigencia(state.id).then((cambios) => {
      if (!vivo || !cambios.length) return;
      const lista = cambios.map((c) => `${c.titulo} (nueva redacción vigente desde ${c.version_actual.split("-").reverse().join("/")})`);
      setAviso(`Desde que hiciste esta consulta ha cambiado la ley: ${lista.join("; ")}. Vuelve a consultar para un análisis actualizado.`);
    }).catch(() => undefined);
    return () => { vivo = false; };
  }, [state.id, conResultado]);

  // Atajos de teclado (lib/atajos.ts). El manejador se renueva en cada render para ver el estado actual.
  const atajo = useRef<(e: KeyboardEvent) => void>(() => undefined);
  atajo.current = (e) => {
    const el = e.target as HTMLElement | null;
    const escribiendo = Boolean(el && (el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName)));
    switch (accionAtajo(e, escribiendo)) {
      case "enfocar": {
        const caja = document.querySelector<HTMLTextAreaElement>('textarea[aria-label="Describe tu caso"]');
        if (!caja) return;
        e.preventDefault();
        caja.focus();
        return;
      }
      case "nueva":
        e.preventDefault();
        irA("consulta");
        limpiar();
        return;
      case "historial":
        e.preventDefault();
        if (!lectura) alternarLateral();
        return;
      case "lectura":
        if (!state.final) return;
        e.preventDefault();
        setVista("consulta");
        setLectura((v) => !v);
        return;
      case "exportar":
        e.preventDefault();
        exportar();
        return;
      case "ayuda":
        e.preventDefault();
        setAyuda(true);
        return;
      case "escape":
        // El visor de fuentes y los diálogos se cierran solos con Esc; si no hay ninguno abierto, sale del modo lectura.
        if (!ayuda && !fuente && lectura) setLectura(false);
        return;
      default:
    }
  };
  useEffect(() => {
    const h = (e: KeyboardEvent) => atajo.current(e);
    document.addEventListener("keydown", h);
    return () => document.removeEventListener("keydown", h);
  }, []);

  const inicio = vista === "consulta" && !state.id;
  const puedePreguntar = !state.id || state.final || state.error;
  const acciones = {
    lectura,
    onLectura: () => setLectura((v) => !v),
    onExportar: exportar,
    onImprimir: () => setImprimiendo(true),
  };

  return (
    <ImprimiendoContext.Provider value={imprimiendo}>
      <div className={`flex h-full bg-bg ${lectura ? "lectura" : ""}`}>
        {lateral && !lectura && (
          <div className="fixed inset-0 z-20 bg-black/30 md:hidden print:hidden" onClick={() => setLateral(false)} aria-hidden />
        )}
        {!lectura && (
          <Sidebar abierta={lateral} actual={vista === "consulta" ? state.id : null} refresco={refresco + (state.final ? 1 : 0)} vista={vista}
                   onAbrir={(id) => { irA("consulta"); void abrir(id); }}
                   onNueva={() => { irA("consulta"); limpiar(); }}
                   onBorrada={(id) => { if (state.id === id) { irA("consulta"); limpiar(); } }}
                   onBiblioteca={invitado ? undefined : () => irA("biblioteca")}
                   onComparar={() => irA("comparar")} />
        )}
        <div className="flex min-w-0 flex-1 flex-col">
          {servidorAntiguo && (
            <p role="alert" className="bg-warning-container px-4 py-1.5 text-center text-xs text-warning print:hidden">
              Desemppa se ha actualizado, pero el servidor en marcha es el anterior: ciérralo y abre INICIAR_DESEMPPA.bat.
            </p>
          )}
          {invitado && (
            <p className="bg-surface px-4 py-1.5 text-center text-xs text-ink-2 print:hidden">
              Estás usando Desemppa en el ordenador de otra persona: tus consultas se procesan allí y esa persona puede verlas.
            {(sesion.en_curso ?? 0) > 0 && !state.streaming &&
              ` Ahora hay ${sesion.en_curso} ${sesion.en_curso === 1 ? "análisis" : "análisis"} en marcha: el tuyo puede tardar más.`}
            </p>
          )}
          {aviso && (
            <div role="status" className="flex items-center gap-2 bg-surface-2 px-4 py-1.5 text-sm text-ink print:hidden">
              <span className="min-w-0 flex-1">{aviso}</span>
              <button className="icon-btn h-7 w-7" aria-label="Cerrar aviso" onClick={() => setAviso(null)}><X className="h-4 w-4" /></button>
            </div>
          )}
          {lectura ? (
            <header className="flex h-14 shrink-0 items-center gap-2 px-4 print:hidden">
              <span className="text-sm text-ink-2">Modo lectura</span>
              <button className="btn-ghost ml-auto" onClick={() => setLectura(false)}>
                <X className="h-4 w-4" />Salir <kbd className="ml-1 text-xs text-ink-3">Esc</kbd>
              </button>
            </header>
          ) : (
            <TopBar modo={modo} onModo={cambiarModo} onMenu={alternarLateral} enAjustes={vista === "ajustes"}
                    onInicio={() => { irA("consulta"); limpiar(); }}
                    invitado={invitado} permitidos={sesion.modos_permitidos.filter((m) => m !== "auditoria")}
                    onAyuda={() => setAyuda(true)} profesional={profesional}
                    onProfesional={() => setProfesional((v) => { guardar("iuris-profesional", v ? "0" : "1"); return !v; })}
                    onAjustes={() => { setFuente(null); setVista((v) => (v === "ajustes" ? "consulta" : "ajustes")); }} />
          )}
          <div className="flex min-h-0 flex-1">
            <main className="flex min-w-0 flex-1 flex-col">
              {vista === "ajustes" && !invitado ? (
                <div className="flex-1 overflow-auto scroll-thin"><SettingsPage /></div>
              ) : vista === "biblioteca" && !invitado ? (
                <div className="flex-1 overflow-auto scroll-thin"><Biblioteca onMensaje={setAviso} /></div>
              ) : vista === "comparar" ? (
                <div className="flex-1 overflow-auto scroll-thin"><Comparar actual={state.id} /></div>
              ) : inicio ? (
                <div className="flex flex-1 flex-col items-center justify-center overflow-auto px-4 pb-10">
                  <div className="w-full max-w-3xl">
                    <h1 className="mb-2 text-center text-[40px] font-normal leading-tight tracking-tight text-ink">
                      ¿En qué te puedo ayudar?
                    </h1>
                    <p className="mb-8 text-center text-base text-ink-2">
                      Analizo tu caso con la ley vigente y compruebo cada cita contra el texto oficial.
                    </p>
                    <Composer variante="hero" onEnviar={enviar} ocupado={state.streaming} textoInicial={sugerencia}
                              biblioteca={!invitado} />
                    <div className="mt-6 flex flex-wrap justify-center gap-2">
                      {SUGERENCIAS.map((s) => (
                        <button key={s.corto} className="chip" onClick={() => setSugerencia(s.texto)}>{s.corto}</button>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <>
                  <div ref={scrollRef} className="flex-1 overflow-auto scroll-thin">
                    <div className={`mx-auto space-y-8 px-4 pb-10 pt-4 sm:px-6 ${lectura ? "max-w-[680px]" : "max-w-[760px]"}`}>
                      {state.pregunta && (
                        <div className="flex justify-end">
                          <p className="max-w-[85%] whitespace-pre-line rounded-[24px] rounded-tr-md bg-surface-2 px-5 py-3 text-[15px] text-ink">
                            {state.pregunta}
                          </p>
                        </div>
                      )}
                      <ProgressLine estado={state.estado} streaming={state.streaming} onDetener={() => void detener()} />
                      {state.error && (
                        <div role="alert" className="flex gap-3 rounded-2xl bg-danger-container px-4 py-3 text-sm text-danger">
                          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />{state.error}
                        </div>
                      )}
                      {state.avisosQuota.length > 0 && !state.final && (
                        <div role="status" className="flex gap-3 rounded-2xl bg-warning-container px-4 py-3 text-sm text-warning">
                          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
                          <ul className="space-y-1">{state.avisosQuota.map((a, i) => <li key={i}>{a}</li>)}</ul>
                        </div>
                      )}
                      {state.estado === "ESPERANDO_ACLARACION" && state.preguntas.length > 0 && (
                        <div ref={respuestaRef} className="scroll-mt-4">
                          <Clarification preguntas={state.preguntas}
                                         onResponder={(r) => { marcarEnVivo(); void responder(r); }} />
                        </div>
                      )}
                      <div ref={state.estado === "ESPERANDO_ACLARACION" ? undefined : respuestaRef} className="scroll-mt-4">
                        <Answer state={state} onAbrir={abrirFuente} acciones={acciones} hoja={pasos} profesional={profesional} />
                      </div>
                      {!lectura && <div className="print:hidden"><ProcessDetails state={state} onAbrir={abrirFuente} /></div>}
                      <ProcesoImpresion state={state} />
                    </div>
                  </div>
                  {puedePreguntar && !lectura && (
                    <div className="mx-auto w-full max-w-[760px] px-4 pb-3 sm:px-6 print:hidden">
                      <Composer variante="dock" onEnviar={enviar} ocupado={state.streaming} biblioteca={!invitado} />
                    </div>
                  )}
                </>
              )}
            </main>
            <SourceViewer abierta={vista === "consulta" ? fuente : null} consultaId={state.id} onClose={() => setFuente(null)} />
          </div>
        </div>
        {ayuda && <AyudaAtajos onClose={() => setAyuda(false)} />}
      </div>
    </ImprimiendoContext.Provider>
  );
}
