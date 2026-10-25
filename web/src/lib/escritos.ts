import type { PasoHoja } from "./api";
import { hoyISO } from "./calendario";
import { fechaLarga } from "./highlight";
import type { Banda, Dictamen } from "./types";

/**
 * Borradores de escritos que el ciudadano puede presentar sin abogado. Se componen en el navegador SIN LLM:
 * - hechos: el relato literal de la persona (con sus datos reales, que nunca salen de este equipo);
 * - fundamentos: solo afirmaciones de tipo «norma» que superaron el cortafuegos, con su cita literal;
 * - base del trámite: las citas verificadas de la hoja de ruta;
 * - lo que no se sabe va entre corchetes para que la persona lo complete.
 */

export const BANDAS_CON_ESCRITO: Banda[] = ["criterio_consolidado_favorable", "argumento_solido_sin_doctrina"];

export interface Escrito { titulo: string; texto: string }

interface Plantilla {
  titulo: string;
  destinatario: string;
  asunto: string;
  intro: string;
  solicito: string[];
  cierre: string;
  extra?: string[];
}

const PLANTILLAS: Record<string, Plantilla> = {
  requerimiento: {
    titulo: "Requerimiento por escrito",
    destinatario: "[NOMBRE DEL DESTINATARIO], con domicilio en [DOMICILIO DEL DESTINATARIO]",
    asunto: "Requerimiento de [devolución / pago] de [CONCEPTO]",
    intro: "Por medio del presente escrito le expongo los siguientes hechos y fundamentos:",
    solicito: [
      "Que me abone la cantidad de [IMPORTE] euros correspondiente a [CONCEPTO], más los intereses que procedan.",
      "Que realice el pago mediante [FORMA DE PAGO / NÚMERO DE CUENTA] en el plazo de [PLAZO] días desde la recepción.",
    ],
    cierre: "De no atenderse este requerimiento, me reservo el ejercicio de las acciones que me correspondan.",
  },
  propuesta_masc: {
    titulo: "Solicitud de negociación previa (medio adecuado de solución de controversias)",
    destinatario: "[NOMBRE DE LA OTRA PARTE], con domicilio en [DOMICILIO]",
    asunto: "Invitación a negociar antes de acudir a los tribunales",
    intro: "Con el fin de intentar un acuerdo antes de acudir a la vía judicial, le expongo:",
    solicito: [
      "Que acepte negociar para resolver esta controversia. Mi propuesta de acuerdo es: [DESCRIBE TU PROPUESTA].",
      "Que me responda por escrito a [DIRECCIÓN / CORREO ELECTRÓNICO] indicando si acepta o su contrapropuesta.",
    ],
    cierre: "Le ruego que conserve este escrito: acredita el intento de negociación.",
  },
  papeleta_conciliacion: {
    titulo: "Papeleta de conciliación",
    destinatario: "Servicio de Mediación, Arbitraje y Conciliación de [PROVINCIA]",
    asunto: "Solicitud de acto de conciliación",
    intro: "Contra la empresa [NOMBRE DE LA EMPRESA], con CIF [CIF] y domicilio en [DOMICILIO], expongo:",
    solicito: [
      "Que se cite a las partes a acto de conciliación.",
      "Pretensión: [readmisión / indemnización / pago de IMPORTE euros por CONCEPTO].",
    ],
    cierre: "",
    extra: [
      "Datos laborales: antigüedad desde [FECHA], categoría [CATEGORÍA], salario [IMPORTE] euros [mensuales/brutos], convenio [CONVENIO].",
    ],
  },
  reclamacion_empresa: {
    titulo: "Reclamación a la empresa",
    destinatario: "Servicio de atención al cliente de [EMPRESA]",
    asunto: "Reclamación por [CONCEPTO]",
    intro: "Presento la siguiente reclamación:",
    solicito: [
      "Que se resuelva mi reclamación mediante [reparación / sustitución / devolución / compensación de IMPORTE euros].",
      "Que me entreguen la clave identificativa y el justificante por escrito de esta reclamación.",
    ],
    cierre: "",
  },
  recurso_reposicion: {
    titulo: "Recurso de reposición",
    destinatario: "[ÓRGANO QUE DICTÓ EL ACTO]",
    asunto: "Recurso de reposición contra [ACTO RECURRIDO], expediente [NÚMERO], notificado el [FECHA]",
    intro: "Dentro de plazo, interpongo recurso de reposición con base en lo siguiente:",
    solicito: ["Que se estime el recurso y se anule [EL ACTO RECURRIDO]."],
    cierre: "",
  },
  alegaciones_multa: {
    titulo: "Escrito de alegaciones",
    destinatario: "[ÓRGANO INSTRUCTOR]",
    asunto: "Alegaciones al expediente sancionador [NÚMERO DE EXPEDIENTE / BOLETÍN DE DENUNCIA]",
    intro: "Dentro de plazo, formulo las siguientes alegaciones:",
    solicito: ["Que se tengan por presentadas estas alegaciones y se acuerde el archivo del expediente."],
    cierre: "",
    extra: ["Pruebas que aporto o propongo: [FOTOGRAFÍAS, TICKETS, TESTIGOS…]."],
  },
  monitorio: {
    titulo: "Datos para la petición de proceso monitorio",
    destinatario: "Juzgado de Primera Instancia de [LOCALIDAD DEL DOMICILIO DEL DEUDOR]",
    asunto: "Petición inicial de proceso monitorio (rellena el formulario oficial del juzgado o su sede electrónica)",
    intro: "Datos que pide el formulario:",
    solicito: ["Que se requiera de pago al deudor por la cantidad de [IMPORTE] euros."],
    cierre: "",
    extra: [
      "Deudor: [NOMBRE] — domicilio: [DOMICILIO].",
      "Origen y cuantía de la deuda: [CONCEPTO] — [IMPORTE] euros.",
      "Documentos que acreditan la deuda: [CONTRATO, FACTURAS, MENSAJES…].",
    ],
  },
};

export const ESCRITOS = Object.fromEntries(Object.entries(PLANTILLAS).map(([k, v]) => [k, v.titulo]));

export function puedeGenerarEscrito(d: Dictamen | undefined): boolean {
  return Boolean(d && BANDAS_CON_ESCRITO.includes(d.banda_solidez));
}

/** Compone el borrador. `titulos`: título legible de cada fuente del dictamen (state.fuentes). */
export function generarEscrito(
  tipo: string, d: Dictamen, relato: string, paso: PasoHoja, titulos: Map<string, string>, hoy = new Date(),
): Escrito | null {
  const p = PLANTILLAS[tipo];
  if (!p) return null;
  const normas = (d.afirmaciones ?? []).filter((a) => a.tipo === "norma" && a.citas.length);
  const fundamentos = [
    ...normas.map((a) => `${a.texto} Así lo dice ${titulos.get(a.citas[0].source_id) ?? a.citas[0].source_id}: «${a.citas[0].verbatim_quote}».`),
    ...paso.base.map((b) => `Artículo ${b.articulo} (${b.norma}): «${b.cita}».`),
  ];
  const L = [
    `[LOCALIDAD], ${fechaLarga(hoyISO(hoy))}`,
    "",
    "De: [NOMBRE Y APELLIDOS], con DNI [DNI] y domicilio en [DOMICILIO].",
    `A: ${p.destinatario}.`,
    "",
    `ASUNTO: ${p.asunto}`,
    "",
    p.intro,
    "",
    "HECHOS (revisa este relato: es lo que contaste en la consulta)",
    ...relato.trim().split(/\n+/).map((l, i) => `${i + 1}. ${l}`),
    ...(p.extra ?? []).flatMap((x) => ["", x]),
    "",
    "FUNDAMENTOS",
    ...fundamentos.map((f, i) => `${i + 1}. ${f}`),
    "",
    "SOLICITO",
    ...p.solicito.map((s, i) => `${i + 1}. ${s}`),
    ...(p.cierre ? ["", p.cierre] : []),
    "",
    "Atentamente,",
    "",
    "[FIRMA]",
    "",
    "—",
    "Borrador orientativo generado por Desemppa. Completa lo que está entre corchetes, revisa los hechos y las citas",
    "antes de enviarlo y, si tienes dudas, consúltalo con un abogado o en el servicio de orientación jurídica gratuita.",
  ];
  return { titulo: p.titulo, texto: L.join("\n") };
}

/** Documento que Word abre directamente (HTML con el tipo de Word), sin librerías. */
export function escritoComoDoc(e: Escrito): string {
  const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const cuerpo = e.texto.split("\n").map((l) => (l ? `<p>${esc(l)}</p>` : "<p>&nbsp;</p>")).join("");
  return `<html><head><meta charset="utf-8"><title>${esc(e.titulo)}</title>`
    + `<style>body{font-family:Calibri,Arial,sans-serif;font-size:11pt}p{margin:0 0 4pt}</style></head><body>${cuerpo}</body></html>`;
}
