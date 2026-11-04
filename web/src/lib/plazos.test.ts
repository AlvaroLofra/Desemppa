import { describe, expect, it } from "vitest";
import { masUrgente } from "./plazos";
import type { Plazo } from "./types";

const p = (id: string, limite: string, titular: "usuario" | "contraparte" = "usuario"): Plazo => ({
  tipo_plazo_id: id, descripcion: id, naturaleza: "caducidad", titular, fecha_inicio: "2026-01-01",
  fecha_limite_segura: limite, base_legal: "x", avisos: [],
});

describe("plazo más urgente", () => {
  const hoy = new Date(2026, 2, 12);
  it("elige el propio que vence antes, ignorando vencidos y los de la otra parte", () => {
    expect(masUrgente([p("A", "2026-05-01"), p("B", "2026-03-20"), p("C", "2026-03-15", "contraparte"), p("D", "2026-03-01")], hoy)!.tipo_plazo_id).toBe("B");
  });
  it("sin plazos vivos no hay cabecera de plazo", () => {
    expect(masUrgente([p("D", "2026-03-01")], hoy)).toBeNull();
    expect(masUrgente([], hoy)).toBeNull();
  });
});
