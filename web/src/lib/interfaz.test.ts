import { describe, expect, it } from "vitest";
import { accionAtajo } from "./atajos";
import { numerarFuentes } from "./citas";
import { claveFuente, compararFuentes } from "./comparar";
import { nombreFichero } from "./descargar";
import { expedienteMarkdown } from "./expediente";
import { escaparIcs, plazosIcs, plegar } from "./ics";
import type { Dictamen, FinalPayload, Plazo } from "./types";
import type { ConsultaState } from "./useConsulta";

const LAU36 = "BOE:BOE-A-1994-26003:a36:2019-03-06";
const CC1561 = "BOE:BOE-A-1889-4763:art1561:1889-08-16";

const plazo: Plazo = {
  tipo_plazo_id: "reclamacion_fianza", descripcion: "Reclamar la fianza", naturaleza: "civil", titular: "usuario",
  fecha_inicio: "2026-09-01", fecha_limite_segura: "2026-12-31", base_legal: "Art. 1964 CC", avisos: [],
};

const dictamen: Dictamen = {
  consulta_id: "c1", banda_solidez: "argumento_solido_sin_doctrina", respuesta_directa: "Sí.", resumen_ciudadano: "",
  fundamentos: [
    { texto: "Interés legal", source_id: LAU36, verbatim_quote: "devengará el interés legal", fuzzy_score: 100, nli: "ENTAILS" },
    { texto: "Desgaste", source_id: CC1561, verbatim_quote: "menoscabado por el tiempo", fuzzy_score: 98, nli: "NEUTRAL" },
  ],
  cuestiones: [], fortalezas: [], debilidades_contraparte: [], riesgos_propios: [], pasos_inmediatos: [],
  plazos: [plazo], postulacion: null, avisos: ["Aviso de prueba"], modelos_usados: { magistrado: "flash" },
  aviso_legal: "Información orientativa.",
  afirmaciones: [
    { seccion: "respuesta", texto: "Deben devolverte la fianza con intereses.", tipo: "norma",
      citas: [{ source_id: CC1561, verbatim_quote: "menoscabado por el tiempo" }] },
    { seccion: "paso", texto: "Reclama por escrito.", tipo: "consejo", citas: [] },
  ],
  auditoria: [{ seccion: "resumen", texto: "Tienes 90 % de éxito | seguro", tipo_propuesto: "norma", resultado: "eliminada",
    citas_verificadas: [], motivos: ["porcentaje inventado"] }],
};

const final: FinalPayload = { estado: "CERTIFICADA", dictamen };

function estado(extra: Partial<ConsultaState> = {}): ConsultaState {
  return {
    id: "c1", pregunta: "El casero no me devuelve la fianza", estado: "CERTIFICADA", triage: null, preguntas: [],
    fuentes: [{ source_id: LAU36, tipo: "boe", titulo: "Artículo 36 LAU", url: "https://www.boe.es/x", extracto: "" }],
    borradores: { defensa: "", contraparte: "", magistrado: "" }, alegatos: {}, resolucion: null, guardrails: [],
    plazos: [], avisosQuota: [], final, error: null, streaming: false, ...extra,
  };
}

describe("citas en línea", () => {
  it("numera las fuentes por orden de aparición, primero las afirmaciones", () => {
    const n = numerarFuentes(dictamen);
    expect([...n.entries()]).toEqual([[CC1561, 1], [LAU36, 2]]);
  });
});

describe("calendario .ics", () => {
  it("escapa y pliega según RFC 5545", () => {
    expect(escaparIcs("a;b,c\\d\ne")).toBe("a\\;b\\,c\\\\d\\ne");
    const lineas = plegar(`DESCRIPTION:${"á".repeat(80)}`);
    expect(lineas.length).toBeGreaterThan(1);
    for (const l of lineas) expect(new TextEncoder().encode(l).length).toBeLessThanOrEqual(75);
    expect(lineas.slice(1).every((l) => l.startsWith(" "))).toBe(true);
  });

  it("copia la fecha límite del motor como día completo con dos avisos", () => {
    const ics = plazosIcs([plazo], "Fianza", new Date("2026-10-25T10:00:00Z"));
    expect(ics).toContain("DTSTART;VALUE=DATE:20261231\r\n");
    expect(ics).toContain("DTEND;VALUE=DATE:20270101\r\n");
    expect(ics).toContain("DTSTAMP:20261025T100000Z");
    expect(ics.match(/BEGIN:VALARM/g)).toHaveLength(2);
    expect(ics).toContain("TRIGGER:-P7D");
    expect(ics.startsWith("BEGIN:VCALENDAR\r\n") && ics.endsWith("END:VCALENDAR\r\n")).toBe(true);
  });
});

describe("atajos de teclado", () => {
  const k = (key: string, code = "", alt = false) => ({ key, code, altKey: alt, ctrlKey: false, metaKey: false });
  it("Alt+letra funciona incluso escribiendo; / y ? solo fuera de un campo", () => {
    expect(accionAtajo(k("n", "KeyN", true), true)).toBe("nueva");
    expect(accionAtajo(k("/", "Slash"), false)).toBe("enfocar");
    expect(accionAtajo(k("/", "Slash"), true)).toBeNull();
    expect(accionAtajo(k("?", "Minus"), false)).toBe("ayuda");
    expect(accionAtajo(k("Escape", "Escape"), true)).toBe("escape");
    expect(accionAtajo(k("x", "KeyX", true), false)).toBeNull();
  });
});

describe("expediente en Markdown", () => {
  it("incluye respuesta con referencias, fundamentos, fuentes, plazos y auditoría sin romper la tabla", () => {
    const md = expedienteMarkdown(estado(), new Date("2026-10-25T10:00:00Z"));
    expect(md).toContain("> El casero no me devuelve la fianza");
    expect(md).toContain("- Deben devolverte la fianza con intereses. [1] _(lo dice la norma)_");
    expect(md).toContain("- [2] Interés legal");
    expect(md).toContain("2. Artículo 36 LAU — `" + LAU36 + "` — https://www.boe.es/x");
    expect(md).toContain("hasta el 2026-12-31");
    expect(md).toContain("| eliminada | resumen | norma | Tienes 90 % de éxito / seguro | porcentaje inventado |");
  });

  it("si no ha terminado, lo dice", () => {
    expect(expedienteMarkdown(estado({ final: null }))).toContain("aún no ha terminado");
  });
});

describe("comparar y ficheros", () => {
  it("ignora la versión del artículo al comparar fuentes", () => {
    expect(claveFuente(LAU36)).toBe("BOE:BOE-A-1994-26003:a36");
    const otro: FinalPayload = { estado: "CERTIFICADA", dictamen: { ...dictamen, afirmaciones: [], fundamentos: [
      { ...dictamen.fundamentos[0], source_id: "BOE:BOE-A-1994-26003:a36:2024-01-01" }] } };
    expect(compararFuentes(final, otro)).toEqual({
      comunes: ["BOE:BOE-A-1994-26003:a36"], soloA: ["BOE:BOE-A-1889-4763:art1561"], soloB: [] });
  });

  it("genera nombres de fichero seguros", () => {
    expect(nombreFichero("¿Mi casero NO me devuelve la fianza?")).toBe("mi-casero-no-me-devuelve-la-fianza");
    expect(nombreFichero("???")).toBe("consulta");
  });
});
