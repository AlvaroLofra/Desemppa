export type Modo = "eco" | "equilibrado" | "pro" | "auditoria";

export type Estado =
  | "RECIBIDA" | "TRIAJE" | "ESPERANDO_ACLARACION" | "FUERA_DE_ALCANCE" | "INGESTA" | "INGESTA_DEGRADADA"
  | "DEBATE" | "GUARDARRAILES" | "CERTIFICADA" | "BLOQUEADA" | "ERROR";

export type Banda =
  | "criterio_consolidado_favorable" | "argumento_solido_sin_doctrina" | "disparidad_de_criterio"
  | "riesgo_probatorio_alto" | "criterio_consolidado_desfavorable" | "no_determinable";

export interface Pregunta {
  id: string;
  texto: string;
  tipo_respuesta: "si_no" | "fecha" | "importe" | "opcion" | "texto" | "municipio";
  opciones?: string[] | null;
  motivo?: string;
}

export interface Triage {
  jurisdiccion_principal: string;
  submateria_principal: string;
  submateria_descripcion?: string | null;
  resumen_hechos?: string;
  fecha_hechos?: string | null;
  municipio_ine_organo?: string | null;
  cuantia_estimada_eur?: number | null;
  normas_boe_objetivo: { id_norma: string; articulos: string[]; motivo: string }[];
}

export interface Fuente {
  source_id: string;
  tipo: "boe" | "sentencia" | "convenio" | "adjunto" | "ue";
  titulo: string;
  url?: string | null;
  extracto: string;
}

export interface Cita { source_id: string; verbatim_quote: string }
export interface Argumento { afirmacion: string; citas: Cita[] }
export interface Verificacion { source_id: string; ok: boolean; score: number; motivo?: string }

export interface Alegato {
  rol: "DEFENSA" | "CONTRAPARTE";
  pretension: string;
  cuestiones: { id: string; argumentos: Argumento[] }[];
}

export interface Cuestion {
  id: string;
  enunciado: string;
  tipo: string;
  estimacion: "DEFENSA" | "CONTRAPARTE";
  fundamentos: Argumento[];
  importe_estimado_eur?: number | null;
}

export interface Resolucion {
  cuestiones: Cuestion[];
  banda_propuesta: Banda;
  razonamiento_banda: string;
  resumen_ciudadano: string;
}

export interface Plazo {
  tipo_plazo_id: string;
  descripcion: string;
  naturaleza: string;
  titular?: "usuario" | "contraparte";
  fecha_inicio: string;
  fecha_limite_segura: string;
  dia_gracia_hasta?: string | null;
  dias_habiles_restantes?: number | null;
  base_legal: string;
  avisos: string[];
}

export interface Postulacion {
  requiere_abogado: boolean;
  requiere_procurador: boolean;
  bloquea_escritos: boolean;
  base_legal: string;
  texto_usuario: string;
}

export interface Fundamento {
  texto: string;
  source_id: string;
  verbatim_quote: string;
  fuzzy_score: number;
  nli: "ENTAILS" | "NEUTRAL";
}

export interface Dictamen {
  consulta_id: string;
  banda_solidez: Banda;
  respuesta_directa?: string;
  resumen_ciudadano: string;
  fundamentos: Fundamento[];
  cuestiones: Cuestion[];
  fortalezas: string[];
  debilidades_contraparte: string[];
  riesgos_propios: string[];
  pasos_inmediatos: string[];
  plazos: Plazo[];
  postulacion?: Postulacion | null;
  avisos: string[];
  modelos_usados: Record<string, string>;
  aviso_legal: string;
  afirmaciones?: AfirmacionVerificada[];
  auditoria?: EntradaAuditoria[];
  respuesta_parcial?: boolean;
  hechos_determinantes?: string[];
  motivos_banda?: string[];
  sello?: SelloVerificacion | null;
}

/** Para que un tercero recompruebe el dictamen: versión y huella (SHA-256) del texto exacto de cada fuente. */
export interface SelloVerificacion {
  verificado_en: string;
  fuentes: { source_id: string; titulo: string; version?: string | null; sha256: string; url?: string | null }[];
  afirmaciones_mostradas: number;
  afirmaciones_eliminadas: number;
  modelos: Record<string, string>;
}

export type TipoAfirmacion = "norma" | "razonamiento" | "hecho" | "consejo" | "limite";

export interface AfirmacionVerificada {
  seccion: "respuesta" | "resumen" | "fortaleza" | "riesgo" | "paso";
  texto: string;
  tipo: TipoAfirmacion;
  citas: { source_id: string; verbatim_quote: string; score?: number | null }[];
}

export interface EntradaAuditoria {
  seccion: string;
  texto: string;
  tipo_propuesto: string;
  resultado: "aceptada" | "reclasificada" | "eliminada";
  tipo_final?: string | null;
  citas_verificadas: string[];
  nli?: string | null;
  motivos: string[];
}

export interface FinalPayload {
  estado: "CERTIFICADA" | "BLOQUEADA" | "FUERA_DE_ALCANCE";
  dictamen?: Dictamen;
  banda_texto?: string;
  mensaje?: string;
  plazos?: Plazo[];
  postulacion?: Postulacion;
  avisos?: string[];
  aviso_legal?: string;
}

export interface Guardrail { id: string; ok: boolean; detalle: string[] }

export const BANDA_TEXTO: Record<Banda, string> = {
  criterio_consolidado_favorable: "Favorable: los tribunales suelen dar la razón en casos así",
  argumento_solido_sin_doctrina: "Bien fundado en la ley, sin sentencias que lo confirmen",
  disparidad_de_criterio: "Incierto: no hay un criterio único",
  riesgo_probatorio_alto: "Depende de lo que puedas demostrar",
  criterio_consolidado_desfavorable: "Desfavorable: la ley o los tribunales van en tu contra",
  no_determinable: "No se puede valorar con lo verificado",
};

/** Qué significa cada nivel de solidez, para quien no sabe Derecho. No es una probabilidad de ganar. */
export const BANDA_EXPLICACION: Record<Banda, string> = {
  criterio_consolidado_favorable: "La ley y sentencias verificadas respaldan tu posición en casos como el tuyo.",
  argumento_solido_sin_doctrina: "La ley verificada te respalda, pero no se han encontrado sentencias que confirmen cómo la aplican los tribunales.",
  disparidad_de_criterio: "Hay razones en los dos sentidos: sentencias contrarias, una jurisprudencia que cambia o un análisis que no coincide. Mira «Por qué».",
  riesgo_probatorio_alto: "Tienes argumentos, pero el resultado depende de hechos que tendrías que probar (documentos, fotos, testigos).",
  criterio_consolidado_desfavorable: "La ley o las sentencias verificadas van en contra de tu posición.",
  no_determinable: "No hay base verificada suficiente para valorar tu caso. Conviene consultar a un profesional.",
};

/** Posición en el medidor de 5 niveles (0 = sin valorar). */
export const BANDA_NIVEL: Record<Banda, number> = {
  criterio_consolidado_favorable: 5,
  argumento_solido_sin_doctrina: 4,
  disparidad_de_criterio: 3,
  riesgo_probatorio_alto: 2,
  criterio_consolidado_desfavorable: 1,
  no_determinable: 0,
};
