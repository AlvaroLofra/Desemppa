import { describe, expect, it } from "vitest";
import { avisoSustitucion } from "./useConsulta";

describe("avisoSustitucion", () => {
  it("dice qué modelo resolvió el rol, en lugar de cuál y por qué", () => {
    expect(avisoSustitucion({ rol: "magistrado", modelo: "gemini-3.8-flash", previsto: "gemini-3.8-flash-medium", motivo: "respuesta vacía" }))
      .toBe("El Magistrado lo ha resuelto gemini-3.8-flash porque gemini-3.8-flash-medium falló (respuesta vacía).");
  });

  it("tolera roles desconocidos y motivo ausente", () => {
    expect(avisoSustitucion({ rol: "auditor", modelo: "a", previsto: "b" })).toBe("auditor lo ha resuelto a porque b falló (no disponible).");
  });
});
