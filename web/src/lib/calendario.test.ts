import { describe, expect, it } from "vitest";
import { cuadricula, dentro, diaSemana, escribirDMA, leerDMA, sumarDias, sumarMeses } from "./calendario";
import { cercaDelFinal } from "./finAnalisis";

describe("selector de fechas", () => {
  it("lee lo que escribe una persona y rechaza fechas imposibles", () => {
    expect(leerDMA("25/10/2026")).toBe("2026-10-25");
    expect(leerDMA("1-2-26")).toBe("2026-02-01");
    expect(leerDMA("29/02/2024")).toBe("2024-02-29");
    expect(leerDMA("29/02/2026")).toBeNull();
    expect(leerDMA("31/04/2026")).toBeNull();
    expect(leerDMA("2026-10-25")).toBeNull();
    expect(escribirDMA("2026-01-05")).toBe("05/01/2026");
  });

  it("la semana empieza en lunes y la cuadrícula tiene 6 semanas", () => {
    expect(diaSemana("2026-10-26")).toBe(0); // lunes
    expect(diaSemana("2026-10-25")).toBe(6); // domingo
    const g = cuadricula(2026, 9); // octubre de 2026 empieza en jueves
    expect(g).toHaveLength(42);
    expect(g[0]).toBe("2026-09-28");
    expect(g[3]).toBe("2026-10-01");
  });

  it("suma días y meses sin errores de zona horaria ni de fin de mes", () => {
    expect(sumarDias("2026-12-31", 1)).toBe("2027-01-01");
    expect(sumarDias("2026-03-29", 1)).toBe("2026-03-30"); // cambio de hora
    expect(sumarMeses("2026-01-31", 1)).toBe("2026-02-28");
    expect(sumarMeses("2026-01-15", -1)).toBe("2025-12-15");
    expect(dentro("2026-10-25", "2026-01-01", "2026-12-31")).toBe(true);
    expect(dentro("2027-01-01", undefined, "2026-12-31")).toBe(false);
  });
});

describe("fin del análisis", () => {
  it("sigue el texto solo si el usuario está abajo", () => {
    expect(cercaDelFinal({ scrollTop: 900, clientHeight: 600, scrollHeight: 1600 })).toBe(true);
    expect(cercaDelFinal({ scrollTop: 100, clientHeight: 600, scrollHeight: 1600 })).toBe(false);
  });
});
