import type { Dictamen, FinalPayload } from "./types";

/** Norma y artículo de un source_id sin la versión («BOE:BOE-A-1994-26003:a36:2019-03-06» → «BOE:BOE-A-1994-26003:a36»),
 *  para que dos consultas con versiones distintas del mismo artículo cuenten como la misma fuente. */
export function claveFuente(sid: string): string {
  return sid.startsWith("BOE:") ? sid.split(":").slice(0, 3).join(":") : sid;
}

export function fuentesDe(d: Dictamen | undefined): Set<string> {
  const out = new Set<string>();
  if (!d) return out;
  for (const a of d.afirmaciones ?? []) for (const c of a.citas) out.add(claveFuente(c.source_id));
  for (const f of d.fundamentos) out.add(claveFuente(f.source_id));
  return out;
}

/** Qué fuentes citan las dos consultas y cuáles solo una. */
export function compararFuentes(a: FinalPayload | null, b: FinalPayload | null) {
  const fa = fuentesDe(a?.dictamen);
  const fb = fuentesDe(b?.dictamen);
  return {
    comunes: [...fa].filter((x) => fb.has(x)).sort(),
    soloA: [...fa].filter((x) => !fb.has(x)).sort(),
    soloB: [...fb].filter((x) => !fa.has(x)).sort(),
  };
}
