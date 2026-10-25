import { useCallback, useEffect, useRef, type RefObject } from "react";
import type { ConsultaState } from "./useConsulta";

const TITULO = "Desemppa";

/** ¿El usuario está cerca del final del contenedor? (para seguir el texto que va saliendo sin quitarle el control) */
export function cercaDelFinal(el: { scrollTop: number; clientHeight: number; scrollHeight: number }, margen = 160): boolean {
  return el.scrollHeight - el.scrollTop - el.clientHeight <= margen;
}

/** Pide permiso de notificaciones una sola vez, desde un gesto del usuario (al enviar una consulta). */
export function pedirPermisoNotificaciones(): void {
  try {
    if ("Notification" in window && Notification.permission === "default") void Notification.requestPermission();
  } catch { /* navegador sin notificaciones */ }
}

/**
 * Comportamiento al analizar:
 * - mientras sale texto, el contenedor sigue el final si el usuario no ha subido;
 * - al terminar un análisis lanzado en esta pestaña: lleva la vista al inicio del dictamen, marca el título de la
 *   pestaña y, si está en segundo plano, envía una notificación del sistema.
 * Devuelve `marcarEnVivo` para llamarlo al enviar una consulta o una aclaración (no al abrir una del historial).
 */
export function useFinAnalisis(
  state: ConsultaState,
  contenedor: RefObject<HTMLElement>,
  respuesta: RefObject<HTMLElement>,
  onTerminado: (mensaje: string) => void,
) {
  const enVivo = useRef(false);
  const siguiendo = useRef(true);

  const marcarEnVivo = useCallback(() => {
    enVivo.current = true;
    siguiendo.current = true;
  }, []);

  // El usuario decide: si sube, se deja de seguir el final; si vuelve abajo, se retoma.
  useEffect(() => {
    const el = contenedor.current;
    if (!el) return;
    const alDesplazar = () => { siguiendo.current = cercaDelFinal(el); };
    el.addEventListener("scroll", alDesplazar, { passive: true });
    return () => el.removeEventListener("scroll", alDesplazar);
  }, [contenedor, state.id]);

  // Seguir el texto que va saliendo (debate, fuentes, fases).
  const tam = state.borradores.defensa.length + state.borradores.contraparte.length + state.borradores.magistrado.length;
  useEffect(() => {
    const el = contenedor.current;
    if (!el || !state.streaming || !enVivo.current || !siguiendo.current) return;
    el.scrollTo({ top: el.scrollHeight });
  }, [tam, state.fuentes.length, state.estado, state.streaming, contenedor]);

  // Fin del análisis (o pregunta aclaratoria): llevar al usuario a lo nuevo y avisarle.
  const terminado = Boolean(state.final) || state.estado === "ESPERANDO_ACLARACION" || Boolean(state.error);
  useEffect(() => {
    if (!terminado || !enVivo.current) return;
    enVivo.current = false;
    const listo = state.final
      ? "Ya tienes la respuesta"
      : state.estado === "ESPERANDO_ACLARACION" ? "Necesito unos datos más para seguir" : "El análisis se ha detenido";
    requestAnimationFrame(() => respuesta.current?.scrollIntoView({ behavior: "smooth", block: "start" }));
    onTerminado(listo);
    if (document.hidden) {
      document.title = `● ${listo} · ${TITULO}`;
      const volver = () => {
        if (document.hidden) return;
        document.title = TITULO;
        document.removeEventListener("visibilitychange", volver);
      };
      document.addEventListener("visibilitychange", volver);
      try {
        if ("Notification" in window && Notification.permission === "granted") {
          const n = new Notification(`${TITULO}: ${listo}`, { body: state.pregunta?.slice(0, 120) ?? "", tag: "desemppa" });
          n.onclick = () => { window.focus(); n.close(); };
        }
      } catch { /* sin notificaciones */ }
    }
  }, [terminado, state.final, state.estado, state.pregunta, respuesta, onTerminado]);

  return { marcarEnVivo };
}
