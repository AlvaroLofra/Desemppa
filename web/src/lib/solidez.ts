import { CircleAlert, CircleCheck, CircleHelp, CircleX, FileSearch, Scale, type LucideIcon } from "lucide-react";
import type { Banda } from "./types";

/** Color de los segmentos llenos del medidor. Nunca va solo: lo acompañan el icono y el texto (DESIGN.md). */
export const BANDA_COLOR: Record<Banda, string> = {
  criterio_consolidado_favorable: "bg-success",
  argumento_solido_sin_doctrina: "bg-accent",
  disparidad_de_criterio: "bg-warning",
  riesgo_probatorio_alto: "bg-warning",
  criterio_consolidado_desfavorable: "bg-danger",
  no_determinable: "bg-ink-3",
};

/** Color del icono, del mismo rol que el medidor. */
export const BANDA_TONO: Record<Banda, string> = {
  criterio_consolidado_favorable: "text-success",
  argumento_solido_sin_doctrina: "text-accent",
  disparidad_de_criterio: "text-warning",
  riesgo_probatorio_alto: "text-warning",
  criterio_consolidado_desfavorable: "text-danger",
  no_determinable: "text-ink-3",
};

/** Icono distinto por nivel, para quien no distingue colores o imprime en blanco y negro. */
export const BANDA_ICONO: Record<Banda, LucideIcon> = {
  criterio_consolidado_favorable: CircleCheck,
  argumento_solido_sin_doctrina: Scale,
  disparidad_de_criterio: CircleAlert,
  riesgo_probatorio_alto: FileSearch,
  criterio_consolidado_desfavorable: CircleX,
  no_determinable: CircleHelp,
};
