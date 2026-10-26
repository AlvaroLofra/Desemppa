import type { Pregunta } from "./types";

export const NO_SE = "No lo sé";

/** Opciones cerradas que se muestran como botones; ninguna si la respuesta es libre (texto, fecha, importe…). */
export function opcionesDe(p: Pregunta): string[] {
  if (p.opciones?.length) return p.opciones;
  return p.tipo_respuesta === "si_no" ? ["Sí", "No"] : [];
}

/** Respuesta que se envía: la elegida y, si el usuario la matiza o escribe otra, su texto libre. */
export function componerRespuesta(valor: string | undefined, matiz: string | undefined): string {
  const v = (valor ?? "").trim();
  const m = (matiz ?? "").trim();
  if (v === NO_SE) return NO_SE;
  if (v && m) return `${v} — ${m}`;
  return v || m;
}

/** Una pregunta está contestada con un valor, con texto libre o con «No lo sé». */
export function contestada(valor: string | undefined, matiz: string | undefined): boolean {
  return componerRespuesta(valor, matiz) !== "";
}
