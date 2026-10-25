import { describe, expect, it } from "vitest";
import type { PasoHoja } from "./api";
import { escritoComoDoc, generarEscrito, puedeGenerarEscrito } from "./escritos";
import type { Dictamen } from "./types";

const LAU36 = "BOE:BOE-A-1994-26003:a36:2026-10-08";
const d = {
  banda_solidez: "argumento_solido_sin_doctrina",
  afirmaciones: [
    { seccion: "respuesta", tipo: "norma", texto: "La fianza devenga interés legal pasado un mes.",
      citas: [{ source_id: LAU36, verbatim_quote: "devengará el interés legal" }] },
    { seccion: "riesgo", tipo: "razonamiento", texto: "Quizá el casero pruebe daños.",
      citas: [{ source_id: LAU36, verbatim_quote: "salvo prueba en contrario" }] },
    { seccion: "paso", tipo: "consejo", texto: "Reúne fotos.", citas: [] },
  ],
} as unknown as Dictamen;
const paso: PasoHoja = {
  titulo: "Reclamar", que_hacer: "x", quien: "tu", plazo: null, escrito: "requerimiento",
  base: [{ norma: "LAU", articulo: "36", cita: "En caso de no suscribirse el documento de finalización" }],
};

describe("borradores de escritos", () => {
  it("solo usa el relato del usuario, afirmaciones «norma» verificadas y la base literal del trámite", () => {
    const e = generarEscrito("requerimiento", d, "Entregué las llaves el 1 de septiembre.\nNo me devuelve 900 €.", paso,
      new Map([[LAU36, "Artículo 36 LAU"]]), new Date(2026, 9, 25))!;
    expect(e.texto).toContain("1. Entregué las llaves el 1 de septiembre.");
    expect(e.texto).toContain("2. No me devuelve 900 €.");
    expect(e.texto).toContain("Así lo dice Artículo 36 LAU: «devengará el interés legal».");
    expect(e.texto).toContain("Artículo 36 (LAU): «En caso de no suscribirse el documento de finalización».");
    expect(e.texto).not.toContain("Quizá el casero"); // los razonamientos y consejos no son fundamentos
    expect(e.texto).toContain("[NOMBRE Y APELLIDOS]");
    expect(e.texto).toContain("25 de octubre de 2026");
  });

  it("no hay borrador con solidez baja ni plantillas inventadas", () => {
    expect(puedeGenerarEscrito(d)).toBe(true);
    expect(puedeGenerarEscrito({ ...d, banda_solidez: "riesgo_probatorio_alto" })).toBe(false);
    expect(generarEscrito("carta_al_juez", d, "x", paso, new Map())).toBeNull();
  });

  it("el documento para Word escapa el HTML", () => {
    expect(escritoComoDoc({ titulo: "T", texto: "<script>" })).toContain("&lt;script&gt;");
  });
});

describe("vista profesional", () => {
  it("muestra la versión del artículo y arma el esquema solo con material verificado", async () => {
    const { esquemaEscrito, versionDe } = await import("../components/VistaProfesional");
    expect(versionDe("BOE:BOE-A-1994-26003:a36:2026-10-08")).toBe("08-10-2026");
    expect(versionDe("EUR:32004R0261:art7")).toBeNull();
    const e = esquemaEscrito({ ...d, fundamentos: [] }, "Hecho uno.", new Map([[LAU36, "Artículo 36 LAU"]]));
    expect(e).toContain("HECHOS\n1. Hecho uno.");
    expect(e).toContain("Artículo 36 LAU (redacción vigente desde 08-10-2026): «devengará el interés legal»");
    expect(e).not.toContain("Quizá el casero");
  });
});
