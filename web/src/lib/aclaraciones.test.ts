import { describe, expect, it } from "vitest";
import { componerRespuesta, contestada, NO_SE, opcionesDe } from "./aclaraciones";

describe("preguntas aclaratorias", () => {
  it("las opciones del modelo mandan sobre sí/no", () => {
    expect(opcionesDe({ id: "q", texto: "¿Cómo?", tipo_respuesta: "si_no", opciones: ["En mano", "Por correo"] }))
      .toEqual(["En mano", "Por correo"]);
    expect(opcionesDe({ id: "q", texto: "¿Firmaste?", tipo_respuesta: "si_no" })).toEqual(["Sí", "No"]);
    expect(opcionesDe({ id: "q", texto: "¿Qué pasó?", tipo_respuesta: "texto" })).toEqual([]);
  });

  it("se puede matizar o contestar solo con texto libre", () => {
    expect(componerRespuesta("Sí", "pero solo de palabra")).toBe("Sí — pero solo de palabra");
    expect(componerRespuesta("", "Por burofax")).toBe("Por burofax");
    expect(componerRespuesta(NO_SE, "algo")).toBe(NO_SE);
    expect(contestada("", "  ")).toBe(false);
    expect(contestada(undefined, "Por burofax")).toBe(true);
  });
});
