import type { ConsultaState } from "./useConsulta";

export type EstadoPaso = "hecho" | "en_curso" | "pendiente";
export interface PasoMonitor { id: string; titulo: string; estado: EstadoPaso; detalle: string | null }

const PASOS = [
  { id: "triaje", titulo: "Entendiendo tu caso", estados: ["RECIBIDA", "TRIAJE", "ESPERANDO_ACLARACION"] },
  { id: "ingesta", titulo: "Buscando en el BOE y en la jurisprudencia", estados: ["INGESTA", "INGESTA_DEGRADADA"] },
  { id: "debate", titulo: "Enfrentando los argumentos de ambas partes", estados: ["DEBATE"] },
  { id: "certificacion", titulo: "Verificando cada cita contra el texto oficial", estados: ["GUARDARRAILES"] },
] as const;

const plural = (n: number, uno: string, varios: string) => `${n} ${n === 1 ? uno : varios}`;

/** Los cuatro pasos del análisis con datos REALES de los eventos del servidor (nunca texto inventado): materia del
 *  triaje, fuentes encontradas (y cuántas descubiertas en los códigos), turnos del debate y controles superados. */
export function pasosMonitor(s: Pick<ConsultaState, "estado" | "triage" | "fuentes" | "alegatos" | "resolucion" | "guardrails" | "final" | "descubrimiento">): PasoMonitor[] {
  const actual = PASOS.findIndex((p) => s.estado && (p.estados as readonly string[]).includes(s.estado));
  const terminado = Boolean(s.final);
  const boe = s.fuentes.filter((f) => f.tipo === "boe" || f.tipo === "ue");
  const descubiertos = s.fuentes.filter((f) => f.origen === "descubierto").length;
  const sentencias = s.fuentes.filter((f) => f.tipo === "sentencia").length;
  const convenios = s.fuentes.filter((f) => f.tipo === "convenio").length;
  const ingesta = s.fuentes.length
    ? [
        plural(boe.length, "artículo oficial", "artículos oficiales") + (descubiertos ? ` (${descubiertos} encontrados en los códigos)` : ""),
        sentencias ? plural(sentencias, "sentencia", "sentencias") : "",
        convenios ? plural(convenios, "cláusula de convenio", "cláusulas de convenio") : "",
      ].filter(Boolean).join(", ") + ` · último: ${s.fuentes[s.fuentes.length - 1].titulo}`
    : s.descubrimiento ? `${plural(s.descubrimiento.candidatos, "precepto candidato", "preceptos candidatos")} en los códigos descargados` : null;
  const turnos = [
    s.alegatos.defensa ? "defensa ✓" : null,
    s.alegatos.contraparte ? "contraparte ✓" : null,
    s.resolucion ? "magistrado ✓" : null,
  ].filter(Boolean);
  const controles = s.guardrails.length
    ? `${s.guardrails.filter((g) => g.ok).length}/${s.guardrails.length} controles superados`
    : null;
  const detalles: Record<string, string | null> = {
    triaje: s.triage ? `Materia: ${s.triage.submateria_descripcion ?? s.triage.submateria_principal}` : null,
    ingesta,
    debate: turnos.length ? turnos.join(" · ") : null,
    certificacion: controles,
  };
  return PASOS.map((p, i) => ({
    id: p.id,
    titulo: p.titulo,
    estado: terminado || (actual >= 0 && i < actual) ? "hecho" : i === actual ? "en_curso" : "pendiente",
    detalle: detalles[p.id],
  }));
}
