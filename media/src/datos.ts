// Datos del vídeo. Todo sale de fuentes reales del proyecto o de las páginas oficiales:
// · Caso V02: benchmark/casos_verificables/V02.json y expediente certificado
//   benchmark/expedientes/20261025_0112_eco/V02/expediente.{md,json} (modo eco, 25-10-2026).
// · Textos de interfaz: web/src/components/{Composer,Results,HojaDeRuta}.tsx y web/src/lib/{types,aclaraciones}.ts.
// · Preguntas aclaratorias: eventos reales `clarification_needed` de data/local/local_cache.db (consulta de despido).
// · Citas: texto literal de la API de datos abiertos del BOE y de la página boe.es (comprobado el 25-10-2026).
// · Sentencia: STS 185/2025 (ECLI:ES:TS:2025:1128), texto extraído del PDF del documento CENDOJ; ver sentencia.json.
import sentencia from "./sentencia.json";

export const CONSULTA =
  "Trabajo de dependiente en Sevilla. El 20 de octubre de 2026 me entregaron una carta de despido disciplinario por bajo rendimiento sin concretar ningún hecho. ¿Cuánto tiempo tengo para reclamar y qué tengo que hacer?";

export const FASES = [
  "Entendiendo tu caso",
  "Buscando en el BOE y en la jurisprudencia",
  "Enfrentando los argumentos de ambas partes",
  "Verificando cada cita contra el texto oficial",
];

export const FUENTES_LEGISLACION = ["Artículo 55 ET", "Artículo 103 LRJS", "Artículo 63 LRJS", "Artículo 65 LRJS"];

export const CITA_ET55 =
  "El despido deberá ser notificado por escrito al trabajador, haciendo figurar los hechos que lo motivan y la fecha en que tendrá efectos.";
export const CITA_LRJS103 =
  "El trabajador podrá reclamar contra el despido, dentro de los veinte días hábiles siguientes a aquél en que se hubiera producido.";

export const SENTENCIA = {
  titulo: "Sentencia del Tribunal Supremo 185/2025",
  meta: "Sala de lo Social · 11-03-2025 · ECLI:ES:TS:2025:1128",
  fragmento: sentencia.fragmento,
  resaltado: "es exigible la audiencia previa del trabajador",
};

export const DEBATE = [
  { rol: "Defensa", texto: "Declarar la improcedencia del despido disciplinario por incumplimiento de los requisitos formales y falta de acreditación de los hechos motivadores…" },
  { rol: "Contraparte", texto: "Declarar la procedencia de la extinción contractual o, subsidiariamente, hacer valer la facultad empresarial de subsanación formal mediante un nuevo despido…" },
  { rol: "Magistrado", texto: "Calificación jurídica del despido ante la omisión de concreción fáctica en la carta de despido.", estima: "Estima: tu posición" },
];

// Respuesta directa y puntos del dictamen certificado (afirmaciones mostradas tras el cortafuegos); n = fuente citada.
export const RESPUESTA = [
  { t: "El plazo para impugnar el despido es de veinte días hábiles computados con arreglo a la norma procesal.", n: 1 },
  { t: "Antes de acudir a los juzgados es preceptivo promover el trámite previo de conciliación o mediación administrativa.", n: 2 },
];
export const A_TU_FAVOR: { t: string; n?: number }[] = [
  { t: "La carta de despido incumple frontalmente la exigencia legal de consignar los hechos motivadores de la sanción.", n: 3 },
  { t: "El defecto de forma en la notificación escrita conlleva expresamente la improcedencia de la extinción disciplinaria.", n: 3 },
];
export const PUNTOS_DEBILES: { t: string; n?: number }[] = [
  { t: "Si la empresa notificara un nuevo despido subsanando la falta de hechos en el plazo legal, podría convalidar los defectos de la primera comunicación.", n: 3 },
  { t: "No constan en las fuentes los términos del convenio colectivo ni datos sobre circunstancias de especial protección que motiven nulidad." },
];

export const SOLIDEZ = {
  nivel: 2,
  texto: "Depende de lo que puedas demostrar",
  explicacion: "Tienes argumentos, pero el resultado depende de hechos que tendrías que probar (documentos, fotos, testigos).",
  nota: "No es una probabilidad de ganar: resume cuánto respaldo verificado tiene tu posición.",
};

export const PLAZO = {
  descripcion: "Accionar contra el despido (papeleta de conciliación / demanda)",
  limite: "miércoles, 18 de noviembre de 2026",
  desde: "20 de octubre de 2026",
  habiles: 17,
  base: "Art. 59.3 ET; arts. 103 y 65 LRJS",
  aviso: "La papeleta de conciliación suspende el plazo, que se reanuda al día siguiente del intento de conciliación o a los 15 días hábiles sin celebrarse (art. 65 LRJS).",
};

export const PASOS = [
  { t: "Ojo al plazo: veinte días hábiles", q: "Lo puedes hacer tú", d: "No se cuentan sábados, domingos ni festivos, y si se pasa no hay remedio." },
  { t: "Papeleta de conciliación (obligatoria antes de la demanda)", q: "Lo puedes hacer tú", d: "Presentarla suspende el plazo de caducidad." },
  { t: "Demanda ante el Juzgado de lo Social", q: "Lo puedes hacer tú", d: "Si no hay acuerdo, se presenta la demanda por escrito acompañando el justificante de la conciliación." },
];
export const SIN_BORRADOR = "Sin borrador: con esta solidez conviene reunir antes las pruebas de «Puntos débiles».";
export const POSTULACION = "En la primera instancia social puedes comparecer por ti mismo, aunque es muy recomendable contar con abogado, graduado social o sindicato.";

export const FUNDAMENTOS = [
  { n: 1, t: "La impugnación del despido está sujeta a un plazo de caducidad fijado en veinte días hábiles.", cita: CITA_LRJS103, src: "BOE:BOE-A-2011-15936:a103:2024-03-20" },
  { n: 2, t: "El intento de conciliación o mediación ante el órgano administrativo correspondiente constituye un presupuesto procesal preceptivo.", cita: "Será requisito previo para la tramitación del proceso el intento de conciliación o, en su caso, de mediación ante el servicio administrativo correspondiente", src: "BOE:BOE-A-2011-15936:a63:2011-12-11" },
  { n: 3, t: "La comunicación extintiva debe contener necesariamente la relación de hechos que fundamentan el despido disciplinario.", cita: CITA_ET55, src: "BOE:BOE-A-2015-11430:a55:2025-04-03" },
];
export const FUENTES_CITADAS = ["Artículo 103 LRJS", "Artículo 63 LRJS", "Artículo 55 ET", "Artículo 65 LRJS"];
export const SELLO = {
  titulo: "Sello de verificación (4 fuentes)",
  fuente: "Artículo 55 ET · redacción vigente desde 2025-04-03",
  sha: "335fe7ffcf843c6cf97ee47eabeb7c76812e09a282931ad4775334e82384b03d",
  nota: "Cualquier persona puede descargar el texto oficial, calcular su SHA-256 y comprobar que las citas salen de ese texto exacto.",
};
export const AUDITORIA = "Cómo se ha verificado (15 afirmaciones, 0 eliminadas)";
