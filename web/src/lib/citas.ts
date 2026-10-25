import type { Dictamen } from "./types";

/** Número de cada fuente citada en el dictamen, en orden de primera aparición (afirmaciones y luego fundamentos).
 *  El mismo número aparece en los superíndices del texto y en «Fundamentos verificados». */
export function numerarFuentes(d: Pick<Dictamen, "afirmaciones" | "fundamentos">): Map<string, number> {
  const out = new Map<string, number>();
  const anadir = (sid: string) => { if (!out.has(sid)) out.set(sid, out.size + 1); };
  for (const a of d.afirmaciones ?? []) for (const c of a.citas) anadir(c.source_id);
  for (const f of d.fundamentos ?? []) anadir(f.source_id);
  return out;
}
