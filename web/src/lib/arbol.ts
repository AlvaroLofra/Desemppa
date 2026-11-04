import type { Alegato, Argumento, Resolucion } from "./types";

export interface CitaNodo { source_id: string; verbatim_quote: string; ok: boolean | null }
export interface NodoArgumento { afirmacion: string; citas: CitaNodo[] }
export interface NodoCuestion {
  id: string;
  enunciado: string;
  estimacion: "DEFENSA" | "CONTRAPARTE" | null;
  defensa: NodoArgumento[];
  contraparte: NodoArgumento[];
  fundamentos: NodoArgumento[];
}

type AlegatoVerificado = { alegato: Alegato; verificacion: { ok: boolean }[][] };

const nodo = (a: Argumento, verif?: { ok: boolean }[]): NodoArgumento => ({
  afirmacion: a.afirmacion,
  citas: a.citas.map((c, i) => ({ source_id: c.source_id, verbatim_quote: c.verbatim_quote, ok: verif?.[i]?.ok ?? null })),
});

/** Argumentos de cada parte por cuestión, con la verificación de sus citas (el servidor la manda en el mismo orden
 *  que los argumentos: cuestión a cuestión), y la decisión del Magistrado. Sin texto propio: solo lo que llegó. */
export function construirArbol(
  alegatos: Partial<Record<"defensa" | "contraparte", AlegatoVerificado>>,
  resolucion: Resolucion | null,
): NodoCuestion[] {
  const cuestiones = new Map<string, NodoCuestion>();
  const asegurar = (id: string) => {
    if (!cuestiones.has(id)) {
      cuestiones.set(id, { id, enunciado: id, estimacion: null, defensa: [], contraparte: [], fundamentos: [] });
    }
    return cuestiones.get(id)!;
  };
  for (const q of resolucion?.cuestiones ?? []) {
    const n = asegurar(q.id);
    n.enunciado = q.enunciado;
    n.estimacion = q.estimacion;
    n.fundamentos = q.fundamentos.map((a) => nodo(a));
  }
  for (const rol of ["defensa", "contraparte"] as const) {
    const al = alegatos[rol];
    if (!al) continue;
    let k = 0;
    for (const q of al.alegato.cuestiones) {
      for (const a of q.argumentos) {
        asegurar(q.id)[rol].push(nodo(a, al.verificacion[k]));
        k += 1;
      }
    }
  }
  return [...cuestiones.values()];
}

/** Citas de un argumento que no superaron la verificación literal. */
export const citasFallidas = (a: NodoArgumento) => a.citas.filter((c) => c.ok === false).length;
