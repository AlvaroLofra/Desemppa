import { useCallback, useEffect, useMemo, useReducer, useRef } from "react";
import { api, streamUrl } from "./api";
import { createDeltaBuffer } from "./deltaBuffer";
import type { Alegato, Estado, FinalPayload, Fuente, Guardrail, Plazo, Pregunta, Resolucion, Triage } from "./types";

export type Rol = "defensa" | "contraparte" | "magistrado";

export interface ConsultaState {
  id: string | null;
  estado: Estado | null;
  triage: Triage | null;
  preguntas: Pregunta[];
  fuentes: Fuente[];
  borradores: Record<Rol, string>;
  alegatos: Partial<Record<"defensa" | "contraparte", { alegato: Alegato; verificacion: { ok: boolean }[][] }>>;
  resolucion: Resolucion | null;
  guardrails: Guardrail[];
  plazos: Plazo[];
  avisosQuota: string[];
  final: FinalPayload | null;
  error: string | null;
  streaming: boolean;
}

const inicial: ConsultaState = {
  id: null, estado: null, triage: null, preguntas: [], fuentes: [],
  borradores: { defensa: "", contraparte: "", magistrado: "" }, alegatos: {}, resolucion: null,
  guardrails: [], plazos: [], avisosQuota: [], final: null, error: null, streaming: false,
};

type Accion =
  | { t: "reset"; id: string | null }
  | { t: "evento"; tipo: string; data: any }
  | { t: "deltas"; chunks: Record<string, string> }
  | { t: "streaming"; v: boolean }
  | { t: "error"; msg: string };

function reducer(s: ConsultaState, a: Accion): ConsultaState {
  switch (a.t) {
    case "reset":
      return { ...inicial, id: a.id, streaming: a.id !== null };
    case "streaming":
      return { ...s, streaming: a.v };
    case "error":
      return { ...s, error: a.msg, streaming: false };
    case "deltas": {
      const b = { ...s.borradores };
      for (const [k, v] of Object.entries(a.chunks)) b[k as Rol] = (b[k as Rol] ?? "") + v;
      return { ...s, borradores: b };
    }
    case "evento": {
      const d = a.data;
      switch (a.tipo) {
        case "phase":
          return { ...s, estado: d.estado, preguntas: d.estado === "TRIAJE" ? [] : s.preguntas };
        case "triage":
          return { ...s, triage: d };
        case "clarification_needed":
          return { ...s, preguntas: d.preguntas, estado: "ESPERANDO_ACLARACION", streaming: false };
        case "source":
          return s.fuentes.some((f) => f.source_id === d.source_id) ? s : { ...s, fuentes: [...s.fuentes, d] };
        case "debate_done":
          if (d.rol === "magistrado") {
            return { ...s, resolucion: d.resolucion, borradores: { ...s.borradores, magistrado: "" } };
          }
          return {
            ...s,
            alegatos: { ...s.alegatos, [d.rol]: { alegato: d.alegato, verificacion: d.verificacion } },
            borradores: { ...s.borradores, [d.rol]: "" },
          };
        case "guardrail":
          return { ...s, guardrails: [...s.guardrails, d] };
        case "deadline":
          return { ...s, plazos: d.plazos };
        case "quota":
          return { ...s, avisosQuota: [...s.avisosQuota, ...(d.avisos ?? [])] };
        case "final":
          return { ...s, final: d, estado: d.estado, streaming: false };
        case "error":
          return { ...s, error: d.mensaje, estado: "ERROR", streaming: false };
        default:
          return s;
      }
    }
  }
}

const EVENTOS = ["phase", "triage", "clarification_needed", "source", "debate_done", "guardrail", "deadline",
  "quota", "final", "error"];

export function useConsulta() {
  const [state, dispatch] = useReducer(reducer, inicial);
  const esRef = useRef<EventSource | null>(null);
  const lastSeq = useRef(0);
  const buffer = useMemo(() => createDeltaBuffer((chunks) => dispatch({ t: "deltas", chunks })), []);

  const cerrar = useCallback(() => {
    esRef.current?.close();
    esRef.current = null;
  }, []);

  const escuchar = useCallback(async (id: string, desdeCero = true) => {
    cerrar();
    if (desdeCero) lastSeq.current = 0;
    dispatch({ t: "streaming", v: true });
    const es = new EventSource(await streamUrl(id, lastSeq.current));
    esRef.current = es;
    for (const tipo of EVENTOS) {
      es.addEventListener(tipo, (ev) => {
        const msg = ev as MessageEvent;
        const seq = Number(msg.lastEventId);
        if (Number.isFinite(seq) && seq > lastSeq.current) lastSeq.current = seq;
        const data = JSON.parse(msg.data);
        dispatch({ t: "evento", tipo, data });
        if (tipo === "final" || tipo === "error" || tipo === "clarification_needed") cerrar();
      });
    }
    es.addEventListener("debate_delta", (ev) => {
      const d = JSON.parse((ev as MessageEvent).data);
      buffer.push(d.rol, d.text);
    });
    es.onerror = () => {
      // EventSource reintenta solo y el servidor reenvía desde Last-Event-ID; si el stream terminó, cerramos.
      if (es.readyState === EventSource.CLOSED) dispatch({ t: "streaming", v: false });
    };
  }, [buffer, cerrar]);

  const nueva = useCallback(async (texto: string, modo: string, municipio: string | null, adjuntos: string[]) => {
    try {
      const { consulta_id } = await api.crear({ texto, modo, municipio_ine: municipio, adjuntos });
      dispatch({ t: "reset", id: consulta_id });
      await escuchar(consulta_id);
      return consulta_id;
    } catch (e) {
      dispatch({ t: "error", msg: (e as Error).message });
      return null;
    }
  }, [escuchar]);

  const abrir = useCallback(async (id: string) => {
    dispatch({ t: "reset", id });
    await escuchar(id);
  }, [escuchar]);

  const responder = useCallback(async (respuestas: { pregunta: string; respuesta: string; municipio_ine?: string | null }[]) => {
    if (!state.id) return;
    try {
      await api.aclarar(state.id, respuestas);
      await escuchar(state.id, false);
    } catch (e) {
      dispatch({ t: "error", msg: (e as Error).message });
    }
  }, [state.id, escuchar]);

  const limpiar = useCallback(() => {
    cerrar();
    dispatch({ t: "reset", id: null });
  }, [cerrar]);

  useEffect(() => cerrar, [cerrar]);
  return { state, nueva, abrir, responder, limpiar };
}
