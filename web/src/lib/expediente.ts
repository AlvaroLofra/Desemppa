import type { PasoHoja } from "./api";
import { numerarFuentes } from "./citas";
import { BANDA_EXPLICACION, BANDA_TEXTO, type AfirmacionVerificada, type Plazo, type Postulacion } from "./types";
import type { ConsultaState } from "./useConsulta";

const SECCIONES: { id: AfirmacionVerificada["seccion"]; titulo: string }[] = [
  { id: "respuesta", titulo: "Respuesta" },
  { id: "resumen", titulo: "Explicación" },
  { id: "fortaleza", titulo: "A tu favor" },
  { id: "riesgo", titulo: "Puntos débiles" },
  { id: "paso", titulo: "Qué hacer ahora" },
];

const TIPO: Record<string, string> = {
  norma: "lo dice la norma", razonamiento: "razonamiento", hecho: "lo que contaste", consejo: "consejo",
  limite: "límite",
};

const md = (s: string) => s.replace(/\r?\n/g, " ").replace(/\|/g, "/");

function plazos(ps: Plazo[]): string[] {
  if (!ps.length) return [];
  return ["## Plazos (motor determinista)", "",
    ...ps.map((p) => `- **${p.descripcion}**: hasta el ${p.fecha_limite_segura} (desde el ${p.fecha_inicio}). ${p.base_legal}.`
      + (p.titular === "contraparte" ? " Plazo de la otra parte." : "")),
    "", "> Cálculo orientativo pendiente de validación jurídica.", ""];
}

function postulacion(p: Postulacion | null | undefined): string[] {
  if (!p) return [];
  return ["## Abogado y procurador", "",
    `- ${p.requiere_abogado ? `Necesitas abogado${p.requiere_procurador ? " y procurador" : ""}` : "Puedes actuar sin abogado"}.`,
    `- ${p.texto_usuario} (${p.base_legal})`, ""];
}

function hojaDeRuta(pasos: PasoHoja[]): string[] {
  if (!pasos.length) return [];
  return ["## Qué hacer a continuación", "", ...pasos.flatMap((p, i) => [
    `${i + 1}. **${p.titulo}** — ${p.que_hacer}`,
    ...p.base.map((b) => `   > «${md(b.cita)}» (art. ${b.articulo} ${b.norma})`),
  ]), ""];
}

/** Expediente completo en Markdown: lo mismo que se ve en pantalla más el proceso, para llevarlo a un abogado o
 *  verificarlo con otro LLM. Solo usa datos del análisis (no añade nada). */
export function expedienteMarkdown(state: ConsultaState, fecha = new Date(), pasos: PasoHoja[] = []): string {
  const f = state.final;
  const titulos = new Map(state.fuentes.map((x) => [x.source_id, x]));
  const L: string[] = ["# Expediente de Desemppa", "", `Generado el ${fecha.toLocaleString("es-ES")}.`, ""];
  if (state.pregunta) L.push("## Tu consulta", "", ...state.pregunta.split("\n").map((l) => `> ${l}`), "");
  const t = state.triage;
  if (t) {
    L.push("## Tu caso", "", `- Materia: ${t.submateria_descripcion ?? t.submateria_principal}`,
      `- Jurisdicción: ${t.jurisdiccion_principal.replace("_", " ")}`);
    if (t.fecha_hechos) L.push(`- Fecha de los hechos: ${t.fecha_hechos}`);
    if (t.cuantia_estimada_eur != null) L.push(`- Cuantía: ${t.cuantia_estimada_eur} €`);
    if (t.resumen_hechos) L.push(`- Resumen: ${t.resumen_hechos}`);
    L.push("");
  }
  if (!f) return [...L, "_El análisis aún no ha terminado._", ""].join("\n");
  const d = f.dictamen;
  if (f.estado !== "CERTIFICADA" || !d) {
    L.push("## Resultado", "", f.mensaje ?? f.estado, "", ...plazos(f.plazos ?? []), ...postulacion(f.postulacion));
    for (const a of f.avisos ?? []) L.push(`- Aviso: ${a}`);
    return L.join("\n");
  }
  const num = numerarFuentes(d);
  const ref = (sid: string) => `[${num.get(sid)}]`;
  L.push(`**Solidez:** ${BANDA_TEXTO[d.banda_solidez]}. ${BANDA_EXPLICACION[d.banda_solidez]}`, "");
  for (const m of d.motivos_banda ?? []) L.push(`- ${m}`);
  if (d.motivos_banda?.length) L.push("");
  if (d.respuesta_parcial) L.push("> Respuesta parcial: no todo superó la verificación y se ha omitido.", "");
  const afs = d.afirmaciones ?? [];
  for (const s of SECCIONES) {
    const lista = afs.filter((a) => a.seccion === s.id);
    if (!lista.length) continue;
    L.push(`## ${s.titulo}`, "");
    for (const a of lista) {
      const citas = [...new Set(a.citas.map((c) => ref(c.source_id)))].join("");
      L.push(`- ${a.texto}${citas ? ` ${citas}` : ""} _(${TIPO[a.tipo] ?? a.tipo})_`);
    }
    L.push("");
  }
  if (!afs.length) L.push("## Respuesta", "", d.respuesta_directa ?? "", "", d.resumen_ciudadano, "");
  L.push(...plazos(d.plazos), ...postulacion(d.postulacion), ...hojaDeRuta(pasos));
  L.push("## Fundamentos verificados", "");
  for (const fu of d.fundamentos) {
    L.push(`- ${ref(fu.source_id)} ${fu.texto}`, `  > «${md(fu.verbatim_quote)}»`,
      `  > — \`${fu.source_id}\`, coincidencia ${fu.fuzzy_score.toFixed(0)} %${fu.nli === "NEUTRAL" ? ", inferencia no literal" : ""}`);
  }
  L.push("", "## Fuentes citadas", "");
  for (const [sid, n] of num) {
    const fu = titulos.get(sid);
    L.push(`${n}. ${fu?.titulo ?? sid} — \`${sid}\`${fu?.url ? ` — ${fu.url}` : ""}`);
  }
  L.push("");
  const r = state.resolucion;
  if (r) {
    L.push("## Razonamiento del Magistrado", "");
    for (const q of r.cuestiones) {
      L.push(`### ${q.enunciado}`, "", `Da la razón a: **${q.estimacion === "DEFENSA" ? "tu posición" : "la otra parte"}**`, "");
      for (const fu of q.fundamentos) {
        L.push(`- ${fu.afirmacion}`, ...fu.citas.map((c) => `  > «${md(c.verbatim_quote)}» — \`${c.source_id}\``));
      }
      L.push("");
    }
  }
  for (const rol of ["defensa", "contraparte"] as const) {
    const al = state.alegatos[rol]?.alegato;
    if (!al) continue;
    L.push(`## Alegato de ${rol === "defensa" ? "la defensa" : "la contraparte"}`, "", `Pretensión: ${al.pretension}`, "");
    for (const q of al.cuestiones) for (const a of q.argumentos) L.push(`- ${a.afirmacion}`);
    L.push("");
  }
  if (d.auditoria?.length) {
    L.push("## Cómo se ha verificado (cortafuegos)", "", "| Resultado | Sección | Tipo | Afirmación | Motivos |", "|---|---|---|---|---|");
    for (const e of d.auditoria) {
      const tipo = e.tipo_final && e.tipo_final !== e.tipo_propuesto ? `${e.tipo_propuesto} → ${e.tipo_final}` : e.tipo_propuesto;
      L.push(`| ${e.resultado} | ${e.seccion} | ${tipo} | ${md(e.texto)} | ${md(e.motivos.join("; "))} |`);
    }
    L.push("");
  }
  if (d.hechos_determinantes?.length) {
    L.push("## Lo que podría cambiar el resultado", "", ...d.hechos_determinantes.map((h) => `- ${h}`), "");
  }
  if (d.avisos.length) L.push("## Avisos", "", ...d.avisos.map((a) => `- ${a}`), "");
  if (d.sello) {
    L.push("## Sello de verificación", "", `Verificado el ${d.sello.verificado_en}. ${d.sello.afirmaciones_mostradas} afirmaciones mostradas, ${d.sello.afirmaciones_eliminadas} eliminadas.`, "",
      "| Fuente | Versión | SHA-256 del texto verificado |", "|---|---|---|",
      ...d.sello.fuentes.map((f) => `| ${md(f.titulo)} (\`${f.source_id}\`) | ${f.version ?? "—"} | \`${f.sha256}\` |`), "");
  }
  L.push("---", "", d.aviso_legal, "", `Modelos: ${Object.entries(d.modelos_usados).map(([k, v]) => `${k} ${v}`).join(" · ")}`, "");
  return L.join("\n");
}
