import type { Plazo } from "./types";

export type TipoHito = "hechos" | "hoy" | "limite" | "limite_contraparte";
export interface Hito {
  fecha: string;
  etiqueta: string;
  tipo: TipoHito;
  naturaleza?: string;
  posicion: number; // 0..100 a lo largo de la línea
  vencido?: boolean;
}

/** Naturaleza del plazo en lenguaje sencillo (docs/guia_juridica_para_informaticos.md, problema 1). */
export const NATURALEZA: Record<string, string> = {
  caducidad: "Caducidad: si vence sin actuar, se pierde el derecho",
  prescripcion: "Prescripción: una reclamación formal puede reiniciar el plazo",
  procesal: "Plazo procesal",
  administrativo: "Plazo administrativo",
  sustantivo: "Plazo legal",
};

const dia = (iso: string) => Date.UTC(+iso.slice(0, 4), +iso.slice(5, 7) - 1, +iso.slice(8, 10));

/** Hitos de la línea temporal: hechos, hoy y cada fecha límite, ordenados y situados proporcionalmente. */
export function hitosLinea(plazos: Plazo[], hoyISO: string, fechaHechos?: string | null): Hito[] {
  if (!plazos.length) return [];
  const hitos: Omit<Hito, "posicion">[] = [];
  const inicio = fechaHechos ?? plazos.map((p) => p.fecha_inicio).sort()[0];
  hitos.push({ fecha: inicio, etiqueta: "Hechos", tipo: "hechos" });
  hitos.push({ fecha: hoyISO, etiqueta: "Hoy", tipo: "hoy" });
  for (const p of plazos) {
    const ajeno = p.titular === "contraparte";
    hitos.push({
      fecha: p.fecha_limite_segura,
      etiqueta: p.descripcion,
      tipo: ajeno ? "limite_contraparte" : "limite",
      naturaleza: NATURALEZA[p.naturaleza] ?? p.naturaleza,
      vencido: p.fecha_limite_segura < hoyISO,
    });
  }
  const fechas = hitos.map((h) => dia(h.fecha));
  const min = Math.min(...fechas);
  const rango = Math.max(...fechas) - min || 1;
  return hitos
    .map((h) => ({ ...h, posicion: Math.round(((dia(h.fecha) - min) / rango) * 1000) / 10 }))
    .sort((a, b) => a.fecha.localeCompare(b.fecha) || (a.tipo === "hoy" ? -1 : 1));
}
