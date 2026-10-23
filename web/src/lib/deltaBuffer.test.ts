import { describe, expect, it } from "vitest";
import { createDeltaBuffer } from "./deltaBuffer";
import { highlightParts } from "./highlight";

describe("createDeltaBuffer", () => {
  it("agrupa todos los deltas de un frame en una sola actualización", () => {
    const queued: (() => void)[] = [];
    const flushes: Record<string, string>[] = [];
    const buf = createDeltaBuffer((c) => flushes.push(c), (cb) => queued.push(cb));
    for (let i = 0; i < 5000; i++) buf.push("magistrado", "a");
    buf.push("defensa", "b");
    expect(queued.length).toBe(1);
    queued[0]();
    expect(flushes).toEqual([{ magistrado: "a".repeat(5000), defensa: "b" }]);
    buf.push("magistrado", "c");
    expect(queued.length).toBe(2);
  });
});

describe("highlightParts", () => {
  it("parte el texto en antes / resaltado / después", () => {
    expect(highlightParts("hola mundo cruel", [5, 10])).toEqual(["hola ", "mundo", " cruel"]);
    expect(highlightParts("abc", null)).toEqual(["abc", "", ""]);
    expect(highlightParts("abc", [2, 99])).toEqual(["ab", "c", ""]);
  });
});
