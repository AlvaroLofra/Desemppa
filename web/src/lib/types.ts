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
  criterio_consolidado_favorable: "Criterio consolidado favorable",
  argumento_solido_sin_doctrina: "Argumento sólido, sin doctrina consolidada",
  disparidad_de_criterio: "Disparidad de criterio entre tribunales",
  riesgo_probatorio_alto: "Depende de pruebas que quizá no tengas",
  criterio_consolidado_desfavorable: "Criterio consolidado desfavorable",
  no_determinable: "No es posible valorar",
};
