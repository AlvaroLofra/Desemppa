import { describe, expect, it } from "vitest";
import { BANDA_COLOR, BANDA_ICONO, BANDA_TONO } from "./solidez";
import { BANDA_EXPLICACION, BANDA_NIVEL, BANDA_TEXTO, type Banda } from "./types";

const BANDAS = Object.keys(BANDA_TEXTO) as Banda[];

describe("solidez: el color nunca es el único portador de significado", () => {
  it("cada banda tiene icono, texto, explicación, nivel y color", () => {
    for (const b of BANDAS) {
      expect(BANDA_ICONO[b], b).toBeDefined();
      expect(BANDA_TEXTO[b], b).toBeTruthy();
      expect(BANDA_EXPLICACION[b], b).toBeTruthy();
      expect(BANDA_NIVEL[b], b).toBeTypeOf("number");
      expect(BANDA_COLOR[b], b).toMatch(/^bg-/);
      expect(BANDA_TONO[b], b).toMatch(/^text-/);
    }
    expect(Object.keys(BANDA_ICONO).sort()).toEqual([...BANDAS].sort());
  });

  it("las bandas que comparten color se distinguen por icono y texto", () => {
    for (const a of BANDAS) {
      for (const b of BANDAS) {
        if (a !== b && BANDA_COLOR[a] === BANDA_COLOR[b]) {
          expect(BANDA_ICONO[a]).not.toBe(BANDA_ICONO[b]);
          expect(BANDA_TEXTO[a]).not.toBe(BANDA_TEXTO[b]);
        }
      }
    }
  });
});
