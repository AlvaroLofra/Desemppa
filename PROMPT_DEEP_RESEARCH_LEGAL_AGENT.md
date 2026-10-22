# DIRECTIVA MAESTRA DE INVESTIGACIÓN PROFUNDA (GEMINI DEEP RESEARCH) - VERSIÓN AUDITADA Y REFACTORIZADA
## PROYECTO: IURIS-IA / LEX-AGENT ES (Asistente Legal Personal Autónomo para el Ordenamiento Jurídico Español)

---

### INSTRUCCIONES DE EJECUCIÓN PARA GEMINI DEEP RESEARCH
> **Objetivo:** Actúa como un consorcio interdisciplinar de **Arquitecto Principal de Sistemas de Software & Agentes de IA (MCP)** y **Magistrado Especialista de lo Contencioso, Civil y Social**.
> Debes realizar una investigación técnica y jurídica exhaustiva en fuentes oficiales del Estado español, portales judiciales, repositorios abiertos y doctrina legal para recopilar **todos los datos, identificadores, selectores, esquemas JSON, expresiones regulares, datasets municipales y precedentes reales** necesarios para implementar la aplicación de escritorio `Iuris-IA / Lex-Agent ES`.
>
> **Premisas Fundamentales de la Arquitectura (Coste 0€ y Modelos Suscritos):**
> 1. **Stack de Modelos Exclusivo sobre Suscripciones Pro del Usuario:**
>    - **Google AI Pro (Antigravity):** Gemini 3.8 Flash (con niveles de thinking: Low/Medium/High) y Gemini 4 Argon cuando esté activo.
>    - **Google AI Studio (Free Tier sin tarjeta):** Llamadas directas en Python con la librería oficial `google-genai` para absorción masiva de contexto (Gemini 3.8 Flash / 2.5 Pro con ventana de 1M tokens a coste 0€).
>    - **Claude Pro (Claude Code Headless):** Claude Haiku, Claude Sonnet y Claude Opus 5.5 (con niveles de thinking effort Low/Medium/High configurables) invocados mediante el CLI `claude -p` sin cobro por API Key residual.
>    - **Sin Modelos Locales:** Queda completamente descartado el uso de modelos locales (Ollama/Qwen/vLLM) o requisitos de GPU/VRAM en el ordenador del usuario.
> 2. **Estrategia "Cache-First" con Base Vectorial Local:** No se scrapea el CENDOJ en vivo en cada turno. Se alimenta una base local (LanceDB / SQLite-VSS) con las 5.000 resoluciones más frecuentes y un worker en background con `playwright-stealth` para casos no cubiertos.
> 3. **Superación del Vacío de Convenios:** Pre-indexación local de los **30 convenios colectivos provinciales y sectoriales más masivos de España** (Hostelería, Comercio, Construcción, Metal, Oficinas de Madrid, Barcelona, Valencia, Sevilla, etc.), más selector UI para adjuntar PDF de nómina o convenio de empresa.
> 4. **Guardarraíl Determinista Robusto:** Token Fuzzy Matching (ratio de Levenshtein tokenizado ≥ 95%) + micro-validador NLI (Natural Language Inference) que certifique la congruencia semántica entre el artículo y la conclusión.
> 5. **Motor de Calendario Judicial Completo:** Integración del mapa de festivos locales de los **8.131 municipios de España** más la regla del "Día de Gracia" procesal (Art. 135.5 LEC: hasta las 15:00 horas del día hábil posterior).
> 6. **Blindaje Deontológico y AI Act:** Reemplazo de porcentajes de éxito por bandas cualitativas de solidez argumental, advertencia de postulación obligatoria con Abogado y Procurador en litigios >2.000 € (Arts. 23 y 31 LEC) y encuadre como herramienta de auto-defensa e investigación ciudadana.

---

## 1. EJE TECNOLÓGICO: API DEL BOE Y LEGISLACIÓN CONSOLIDADA

Investiga a fondo la infraestructura REST de la Agencia Estatal del Boletín Oficial del Estado (`https://www.boe.es/datosabiertos/api/legislacion-consolidada`):

1. **Especificación Técnica de la API Oficial:**
   - URL base exacta y métodos HTTP admitidos (GET).
   - Cabeceras de solicitud para negociación de contenido (`Accept: application/json` vs `Accept: application/xml`).
   - Gestión de esquemas polimórficos de párrafos (casos en los que el JSON devuelve un string simple si hay 1 párrafo o un array si hay múltiples párrafos) y modelos Pydantic con `Union[str, List[str]]`.
   - Parámetros y formatos de respuesta de los endpoints oficiales:
     * Búsqueda general y facetada: `/datosabiertos/api/legislacion-consolidada`
     * Descarga del sumario / índice de bloques: `/datosabiertos/api/legislacion-consolidada/id/{id_norma}/texto/indice`
     * Descarga de bloque / artículo atómico: `/datosabiertos/api/legislacion-consolidada/id/{id_norma}/texto/bloque/{id_bloque}`
     * Nodo de análisis normativo y reformas: `/datosabiertos/api/legislacion-consolidada/id/{id_norma}/analisis`
2. **Esquema de Metadatos para Trazabilidad Temporal:**
   - Estructura exacta de los campos que indican:
     * `fecha_actualizacion` de cada artículo individual.
     * `estatus_derogacion` (vigente, derogada parcial, derogada total).
     * Relaciones normativas: referencias anteriores (`modifica_a`), referencias posteriores (`modificada_por`) y disposiciones transitorias.
3. **Diccionario Maestro de Identificadores Oficiales del BOE (`id_norma`):**
   - Proporciona un diccionario Python validado con los identificadores oficiales (`BOE-A-YYYY-NNNNN`) de las 35 normas más críticas de España:
     * Código Civil (`BOE-A-1889-4763`)
     * Código Penal (`BOE-A-1995-25444`)
     * Ley de Enjuiciamiento Civil - LEC (`BOE-A-2000-323`)
     * Ley de Enjuiciamiento Criminal - LECrim (`BOE-A-1882-6036`)
     * Estatuto de los Trabajadores - ET (`BOE-A-2015-11430`)
     * Ley Reguladora de la Jurisdicción Social - LRJS (`BOE-A-2011-15936`)
     * Ley de Arrendamientos Urbanos - LAU (`BOE-A-1994-26003`)
     * Ley General para la Defensa de los Consumidores y Usuarios (`BOE-A-2007-20555`)
     * Ley 39/2015 del Procedimiento Administrativo Común (`BOE-A-2015-10565`)
     * Ley 40/2015 de Régimen Jurídico del Sector Público (`BOE-A-2015-10566`)
     * Ley de Propiedad Horizontal - LPH (`BOE-A-1960-10906`)
     * Ley Hipotecaria (`BOE-A-1946-2453`)
     * Ley sobre Responsabilidad Civil y Seguro en la Circulación de Vehículos de Motor (`BOE-A-2004-18910`)
     * Ley General Tributaria (`BOE-A-2003-23186`)
4. **Estado del Arte en MCP Open Source:**
   - Analiza los repositorios de GitHub `ComputingVictor/MCP-BOE` y `Proxera-Group/boe-mcp`. Describe sus funciones expuestas, limitaciones, manejo de caché y cómo implementan `get_law_structure` y `get_law_text_block`.

---

## 2. EJE JUDICIAL: JURISPRUDENCIA DEL CENDOJ (CGPJ) Y EXTRACCIÓN ROBUSTA

Investiga la plataforma del Centro de Documentación Judicial (`https://www.poderjudicial.es/search/indexAN.jsp`):

1. **Estrategia Dual de Jurisprudencia:**
   - *Capa 1 (Cache-First):* Esquema de almacenamiento en LanceDB / SQLite-VSS para 5.000 resoluciones pre-indexadas con metadatos: `roj`, `ecli`, `tribunal`, `sala`, `fecha`, `hechos_vector`, `fundamentos_vector`, `fallo`.
   - *Capa 2 (Background Scraper con `playwright-stealth`):*
     * Configuración de cabeceras TLS JA3/JA4, bypass de detección de Chromium (`navigator.webdriver = false`, emulación de plugins y WebGL).
     * Selectores DOM actualizados del formulario monolítico JSP (`indexAN.jsp`): campos de jurisdicción, órgano, fechas y operadores booleanos.
2. **Identificadores Oficiales de Resoluciones:**
   - Estructura y sintaxis del código **ROJ** (Registro Oficial de Jurisprudencia, ej. `STS 4512/2023`) y del código **ECLI** para España (`ECLI:ES:TS:2023:...`).
3. **Pipeline de Parsing y Normalización de PDFs Judiciales:**
   - Detección automática de PDFs escaneados sin capa de texto (<100 caracteres extraídos) y conmutación a OCR local (Tesseract / Windows OCR).
   - Normalización de ligaduras tipográficas (`\ufb01` -> `fi`, `\ufb02` -> `fl`) y des-silabeo con expresiones regulares.
   - Expresiones regulares multilínea en Python para segmentar:
     * Metadatos de cabecera.
     * `ANTECEDENTES DE HECHO` / `HECHOS PROBADOS` (purgando referencias a instancias previas).
     * `FUNDAMENTOS DE DERECHO` (excluyendo o aislando explícitamente `VOTOS PARTICULARES` disidentes).
     * `FALLO` / `PARTE DISPOSITIVA`.

---

## 3. EJE LABORAL Y LOCAL: CONVENIOS COLECTIVOS Y DERECHO MUNICIPAL

1. **Pre-empaquetado de los 30 Convenios Colectivos Clave en España:**
   - Identifica y cataloga los 30 convenios colectivos con mayor número de trabajadores afectados en España, abarcando las principales provincias (Madrid, Barcelona, Valencia, Sevilla, Vizcaya, Málaga, Zaragoza) y sectores:
     * Hostelería y Restauración.
     * Comercio del Metal y Siderometalurgia.
     * Oficinas y Despachos / Consultoría y Servicios TIC.
     * Construcción y Obras Públicas.
     * Limpieza de Edificios y Locales.
     * Transporte de Mercancías por Carretera.
     * Sanidad Privada y Residencias de Mayores.
   - Para cada convenio: Código oficial de convenio (ej. `28000000000000`), denominación exacta, ámbito territorial y fecha de publicación oficial en el BOP o diario autonómico.
2. **Protocolo para Normativa Municipal (BOP):**
   - Cómo diseñar el triaje para detectar litigios de ordenanza local (multas ORA/SER, terrazas, Plusvalía municipal, ruidos vecinales) e instruir al usuario para cargar el PDF de la sanción municipal.

---

## 4. EJE PROCESAL: MOTOR DE CALENDARIO JUDICIAL Y DERECHO FORAL

1. **Motor de Calendario Judicial y Cómputo de Días Hábiles (`calendar_engine.py`):**
   - Cómo estructurar el dataset de festivos locales de los **8.131 municipios de España** (a partir de fuentes abiertas como `datos.gob.es` o boletines autonómicos).
   - Algoritmo de cómputo para los plazos fatales:
     * Despido disciplinario: **20 días hábiles** (excluyendo sábados, domingos, festivos nacionales, autonómicos y los 2 festivos locales del municipio del centro de trabajo).
     * Aplicación estricta de la regla del **Día de Gracia Procesal** (Art. 135.5 LEC: el escrito puede presentarse válidamente hasta las 15:00 horas del día hábil siguiente al del vencimiento del plazo).
     * Habilitación procesal del mes de agosto en materia de despido y derechos fundamentales (Art. 43 LRJS) frente a su inhabilidad en la jurisdicción civil ordinaria (Art. 130 LEC).
2. **Catálogo de Plazos Extintivos y Prescripciones:**
   - Social: Despido (20 días hábiles), cantidad/salarios (1 año), sanciones (20 días).
   - Civil: Responsabilidad extracontractual (1 año, Art. 1968.2 CC), acciones contractuales generales (5 años, Art. 1964.2 CC), vicios ocultos (6 meses, Art. 1490 CC), garantías de consumo (3 años / 2 años de presunción, RDL 1/2007), fianza de alquiler (1 mes para liquidar intereses, Art. 36.4 LAU).
   - Contencioso-Administrativo: Reposición/Alzada (1 mes), Contencioso Judicial (2 meses).
3. **Mapeo del Derecho Civil Foral Especial:**
   - Prevalencias en Cataluña (*Codi Civil de Catalunya*: separación de bienes legal, legítima del 25%, prescripción general de 10 años, rescisión por lesión ultradimidium).
   - Navarra (*Fuero Nuevo*: libertad de testar, conquistas).
   - País Vasco, Aragón, Galicia, Baleares (peculiaridades sucesorias y consorciales).
4. **Carga de la Prueba (Art. 217 LEC) y Validez de Evidencias Digitales:**
   - Requisitos de cotejo judicial y peritaje para WhatsApp (STS 300/2015 y STS 754/2022).
   - Burofax fehaciente (acuse de recibo y certificación de contenido) y negativa a recepción (STS 101/2021).

---

## 5. EJE DE EVALUACIÓN: BANCO DE SENTENCIAS REALES DEL TRIBUNAL SUPREMO Y AUDIENCIAS PROVINCIALES

Compila **15 sentencias reales verificadas** (10 del Tribunal Supremo y 5 de Audiencias Provinciales representativas):
1. **Casos del Tribunal Supremo (Casación Compleja):**
   - Fianza en alquiler y obras de habitabilidad vs desgaste ordinario (Art. 21 LAU).
   - Gastos hipotecarios y comisión de apertura (control de transparencia TJUE / TS).
   - Tarjetas revolving y usura (TAE medio BdE + diferencial doctrina STS 257/2023).
   - Prohibición de pisos turísticos por mayoría de 3/5 en comunidades (Art. 17.12 LPH).
   - Despido con videovigilancia oculta y juicio de proporcionalidad (López Ribalda).
   - Accidente laboral doméstico en régimen de teletrabajo (Art. 156 LGSS).
   - Estafa por phishing bancario y negligencia grave del usuario (RDL 19/2018).
   - Anulación de sanción administrativa por falta de ratificación del agente.
   - Conflicto sucesorio por vecindad civil foral vs común.
   - Demanda civil o laboral desestimada por caducidad extintiva de plazos.
2. **Casos de Audiencias Provinciales (Justicia Ordinaria de Proximidad):**
   - Cuantificación de "pequeñas reparaciones" en vivienda arrendada (AP Madrid vs AP Barcelona).
   - Daños por humedades en propiedad horizontal y seguro comunitario.
   - Vicios ocultos en vehículo de segunda mano entre particulares.
   - Reclamación de fianza por tenencia de mascotas no prohibida en contrato.
   - Oposición a monitorio bancario por intereses abusivos.

**Para cada sentencia documentar:**
- ROJ oficial (ej. `STS 4512/2023` o `SAP M 1204/2022`), ECLI, Órgano, Sala, Fecha y Ponente.
- Antecedentes de Hecho cronológicos limpios (sin filtración de fallos de instancias previas).
- Fundamentos de Derecho y preceptos del BOE nucleares.
- Fallo vinculante y condena en costas.

---

## 6. EJE DE IMPLEMENTACIÓN: ENRUTADOR CLAUDE PRO & GEMINI AI PRO

1. **Orquestación sobre el Stack Pro del Usuario (Coste 0€ adicional):**
   - Integración con **Google GenAI SDK** (`google-genai` en Python) para Gemini 3.8 Flash (con thinking: low/medium/high) y Gemini 4 Argon.
   - Integración headless con **Claude Code CLI** (`claude -p`) configurando `--model opus` o `--model sonnet` y `--effort low|medium|high` sin cobrar por API Key residual.
   - Manejo de streaming token a token mediante Server-Sent Events (SSE) en la Web UI local (FastAPI).
2. **Módulo Local de Anonimización RGPD:**
   - Script con spaCy (`es_core_news_md` / `es_core_news_lg`) con diccionario estricto de excepciones de entidades institucionales (juzgados, ministerios, BOE, CGPJ, FOGASA, DGT) para evitar ofuscar autoridades judiciales.
3. **Guardarraíl Determinista de Citación con Token Fuzzy Matching:**
   - Implementación en Python de la función `validate_citation(verbatim_quote, source_id, cached_doc)`:
     * Normalización de espacios, saltos de línea y comillas tipográficas (`"` vs `«` vs `”`).
     * Cálculo de ratio Levenshtein tokenizado (`rapidfuzz` o `thefuzz`). Aprobación si similitud ≥ 95%.
     * Prompt de verificación NLI (Natural Language Inference) para detectar contradicciones semánticas flagrantes.
4. **Cortafuegos Deontológico y Procesal (Arts. 23 y 31 LEC):**
   - Función en Python que evalúa la cuantía del litigio y la materia. Si cuantía > 2.000 € o juicio ordinario/social, inyecta bloqueo imperativo de generación de escritos procesales y muestra advertencia no saltable de preceptividad de Letrado y Procurador colegiados.

---

### FORMATO DE ENTREGA ESPERADO
Presenta el informe en formato Markdown exhaustivo, con bloques de código Python listos para producción (tipado con Pydantic, manejo de excepciones y comentarios técnicos), tablas de datos estructuradas, identificadores contrastados y enlaces a las fuentes públicas oficiales.
