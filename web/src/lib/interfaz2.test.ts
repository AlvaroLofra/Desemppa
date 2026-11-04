import { describe, expect, it } from "vitest";
import { construirArbol, citasFallidas } from "./arbol";
import { hitosLinea, NATURALEZA } from "./lineaTemporal";
import { pasosMonitor } from "./monitor";
import type { Alegato, Plazo, Resolucion } from "./types";

const cita = (sid: string) => ({ source_id: sid, verbatim_quote: "texto literal de la fuente oficial citada" });

describe("árbol de argumentos", () => {
  const defensa: Alegato = { rol: "DEFENSA", pretension: "p", cuestiones: [
    { id: "C1", argumentos: [{ afirmacion: "A favor 1", citas: [cita("BOE:1"), cita("BOE:2")] }] },
    { id: "C2", argumentos: [{ afirmacion: "A favor 2", citas: [cita("BOE:3")] }] },
  ] };
  const contraparte: Alegato = { rol: "CONTRAPARTE", pretension: "q", cuestiones: [
    { id: "C1", argumentos: [{ afirmacion: "En contra 1", citas: [cita("BOE:9")] }] },
  ] };
  const resolucion = { cuestiones: [
    { id: "C1", enunciado: "¿Procede?", tipo: "calificacion_juridica", estimacion: "DEFENSA", fundamentos: [{ afirmacion: "Sí", citas: [cita("BOE:1")] }] },
  ], banda_propuesta: "argumento_solido_sin_doctrina", razonamiento_banda: "", resumen_ciudadano: "" } as Resolucion;

  it("agrupa por cuestión con la verificación de cada cita en orden", () => {
    const arbol = construirArbol({
      defensa: { alegato: defensa, verificacion: [[{ ok: true }, { ok: false }], [{ ok: true }]] },
      contraparte: { alegato: contraparte, verificacion: [[{ ok: false }]] },
    }, resolucion);
    expect(arbol.map((q) => q.id)).toEqual(["C1", "C2"]);
    const [c1, c2] = arbol;
    expect(c1.enunciado).toBe("¿Procede?");
    expect(c1.estimacion).toBe("DEFENSA");
    expect(c1.defensa[0].citas.map((c) => c.ok)).toEqual([true, false]);
    expect(citasFallidas(c1.defensa[0])).toBe(1);
    expect(c1.contraparte[0].afirmacion).toBe("En contra 1");
    expect(c2.estimacion).toBeNull();
    expect(c2.defensa[0].citas[0].ok).toBe(true);
  });

  it("sin debate no hay árbol", () => {
    expect(construirArbol({}, null)).toEqual([]);
  });
});

describe("línea temporal de plazos", () => {
  const plazo = (id: string, limite: string, naturaleza: string, titular: "usuario" | "contraparte" = "usuario"): Plazo => ({
    tipo_plazo_id: id, descripcion: id, naturaleza, titular, fecha_inicio: "2026-03-02", fecha_limite_segura: limite,
    base_legal: "x", avisos: [],
  });

  it("ordena hechos, hoy y límites y los sitúa en proporción", () => {
    const h = hitosLinea([plazo("B", "2026-04-01", "caducidad"), plazo("A", "2026-03-30", "prescripcion")], "2026-03-12", "2026-03-02");
    expect(h.map((x) => x.tipo)).toEqual(["hechos", "hoy", "limite", "limite"]);
    expect(h[0].posicion).toBe(0);
    expect(h[h.length - 1].posicion).toBe(100);
    expect(h[1].posicion).toBeGreaterThan(30);
    expect(h[1].posicion).toBeLessThan(40);
    expect(h[3].naturaleza).toBe(NATURALEZA.caducidad);
  });

  it("marca vencidos y los plazos de la otra parte", () => {
    const h = hitosLinea([plazo("X", "2026-03-05", "procesal"), plazo("Y", "2026-05-01", "procesal", "contraparte")], "2026-03-12");
    expect(h.find((x) => x.etiqueta === "X")!.vencido).toBe(true);
    expect(h.find((x) => x.etiqueta === "Y")!.tipo).toBe("limite_contraparte");
    expect(hitosLinea([], "2026-03-12")).toEqual([]);
  });
});

describe("monitor del proceso", () => {
  const base = { estado: null, triage: null, fuentes: [], alegatos: {}, resolucion: null, guardrails: [], final: null, descubrimiento: null };

  it("muestra solo datos reales de los eventos", () => {
    const pasos = pasosMonitor({
      ...base,
      estado: "DEBATE",
      triage: { jurisdiccion_principal: "civil", submateria_principal: "X", submateria_descripcion: "Fianza", normas_boe_objetivo: [] },
      fuentes: [
        { source_id: "BOE:1", tipo: "boe", titulo: "Artículo 36 LAU", extracto: "", origen: "catalogo" },
        { source_id: "BOE:2", tipo: "boe", titulo: "Artículo 1101 CC", extracto: "", origen: "descubierto" },
        { source_id: "ROJ:1", tipo: "sentencia", titulo: "SAP M 1/2024", extracto: "" },
      ],
    });
    expect(pasos.map((p) => p.estado)).toEqual(["hecho", "hecho", "en_curso", "pendiente"]);
    expect(pasos[0].detalle).toBe("Materia: Fianza");
    expect(pasos[1].detalle).toBe("2 artículos oficiales (1 encontrados en los códigos), 1 sentencia · último: SAP M 1/2024");
    expect(pasos[2].detalle).toBeNull();
  });

  it("cuenta los controles superados", () => {
    const pasos = pasosMonitor({ ...base, estado: "GUARDARRAILES", guardrails: [{ id: "G1", ok: true, detalle: [] }, { id: "G2", ok: false, detalle: [] }] });
    expect(pasos[3]).toMatchObject({ estado: "en_curso", detalle: "1/2 controles superados" });
  });
});
