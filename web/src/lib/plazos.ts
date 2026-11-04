import { diasNaturalesHasta } from "./highlight";
import type { Plazo } from "./types";

/** Plazos que interesa apuntar: los del usuario que no han vencido. */
export const apuntables = (plazos: Plazo[], hoy = new Date()) =>
  plazos.filter((p) => p.titular !== "contraparte" && diasNaturalesHasta(p.fecha_limite_segura, hoy) >= 0);

/** El plazo propio más urgente (el que vence antes), o null. */
export function masUrgente(plazos: Plazo[], hoy = new Date()): Plazo | null {
  const vivos = apuntables(plazos, hoy);
  return vivos.length ? vivos.reduce((a, b) => (b.fecha_limite_segura < a.fecha_limite_segura ? b : a)) : null;
}
