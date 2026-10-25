export type AccionAtajo = "enfocar" | "nueva" | "historial" | "lectura" | "exportar" | "ayuda" | "escape";

export const ATAJOS: { teclas: string; accion: AccionAtajo; descripcion: string }[] = [
  { teclas: "/", accion: "enfocar", descripcion: "Escribir una consulta" },
  { teclas: "Alt + N", accion: "nueva", descripcion: "Nueva consulta" },
  { teclas: "Alt + B", accion: "historial", descripcion: "Mostrar u ocultar el historial" },
  { teclas: "Alt + L", accion: "lectura", descripcion: "Modo lectura del dictamen" },
  { teclas: "Alt + E", accion: "exportar", descripcion: "Exportar el expediente (Markdown)" },
  { teclas: "?", accion: "ayuda", descripcion: "Ver estos atajos" },
  { teclas: "Esc", accion: "escape", descripcion: "Cerrar el visor, la ayuda o el modo lectura" },
];

const CON_ALT: Record<string, AccionAtajo> = { KeyN: "nueva", KeyB: "historial", KeyL: "lectura", KeyE: "exportar" };

/** Qué atajo corresponde a una pulsación. Mientras se escribe en un campo solo cuentan Alt+letra y Esc. */
export function accionAtajo(
  e: { key: string; code: string; altKey: boolean; ctrlKey: boolean; metaKey: boolean },
  escribiendo: boolean,
): AccionAtajo | null {
  if (e.key === "Escape") return "escape";
  if (e.altKey && !e.ctrlKey && !e.metaKey) return CON_ALT[e.code] ?? null;
  if (escribiendo || e.altKey || e.ctrlKey || e.metaKey) return null;
  if (e.key === "/") return "enfocar";
  if (e.key === "?") return "ayuda";
  return null;
}
