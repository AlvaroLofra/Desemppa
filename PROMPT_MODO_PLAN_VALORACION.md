# PROMPT MAESTRO PARA MODO PLAN (/plan)
## PROYECTO: IURIS-IA / LEX-AGENT ES (Asistente Legal Personal Autónomo para España)

```markdown
# DIRECTIVA PARA SESIÓN DE PLANIFICACIÓN INTEGRAL (MODO PLAN / NO-CODE)
## ROL: Principal Systems Architect & Senior Legal Tech Consultant
## PROYECTO: IURIS-IA / LEX-AGENT ES (Asistente Legal Personal Autónomo - España)

---

### INSTRUCCIÓN DE EJECUCIÓN INICIAL Y REGLA DE ORO
> **MODO PLAN ESTRICTO — PROHIBIDO PROGRAMAR CÓDIGO FUNCIONAL:**
> En esta sesión **NO debes generar código de aplicación ni implementar scripts**. Tu objetivo exclusivo es realizar una **evaluación exhaustiva de viabilidad, arquitectura del sistema y diseño documental previo**, dejando el proyecto 100% especificado, estructurado y listo para ser programado en fases posteriores.
>
> **Entorno y Contexto del Desarrollador:**
> 1. El desarrollador es **ingeniero informático sin formación jurídica**. Toda complejidad procesal del derecho español debe quedar resuelta mediante diseño de software determinista, contratos de datos estrictos y validadores en Python.
> 2. **Infraestructura a Coste 0,00 € adicionales:** El sistema operará combinando exclusivamente las suscripciones activas del usuario:
>    - **Google AI Pro / Antigravity:** Gemini 3.8 Flash (niveles de thinking: low/med/high) y Gemini 4 Argon.
>    - **Google AI Studio:** Free Tier sin tarjeta con la librería oficial `google-genai` en Python para la ingesta masiva de PDFs y BOE a coste cero.
>    - **Claude Pro (20 €/mes):** Claude Haiku, Claude Sonnet y Claude Opus 5.5 (con thinking effort low/med/high) vía subprocesos headless serializados (`claude -p`).
>    - *Queda totalmente descartado el uso de modelos locales (Ollama/Qwen) y requisitos de GPU.*
> 3. **Documentación Base de Referencia:** El proyecto parte del documento `Propuesta_Maestra_IurisIA_LexAgent_Definitiva.pdf` presente en el workspace, que superó 3 rondas de auditoría destructiva Red Team.

---

### OBJETIVOS Y ENTREGABLES DE ESTA SESIÓN DE PLANIFICACIÓN

Debes estructurar y generar un dossier documental completo dividido en los siguientes 5 bloques analíticos:

---

#### BLOQUE 1: EVALUACIÓN INTEGRAL DE VIABILIDAD Y MATRIZ DE RIESGOS RESIDUALES
Realiza un diagnóstico de ingeniería y derecho positivo sobre los 4 pilares operativos:
1. **Viabilidad Técnica y de Cuotas:**
   - Análisis de consumo de la ventana de 5 horas de Claude Pro: cómo asegurar que la absorción de PDFs y legislación se derive íntegramente a Gemini 3.8 Flash (Free Tier / Pro) para reservar la cuota de Claude Sonnet y Opus 5.5 exclusivamente para la Fase 3 de razonamiento dialectal.
   - Estrategia de cola asíncrona serializada para evitar colisiones en `~/.claude` o bloqueos de concurrencia en Windows.
2. **Viabilidad del Acceso a Datos (CENDOJ, BOE y Convenios):**
   - Validación de la estrategia "Cache-First": almacenamiento local en **LanceDB / SQLite-VSS** de 5.000 precedentes clave (<50 ms de latencia) frente al riesgo de bloqueo por WAF en CENDOJ.
   - Protocolo de ingesta para los **30 convenios colectivos provinciales/sectoriales más masivos de España** (Hostelería, Comercio, Metal, Construcción, Oficinas) y selector UI para carga de nóminas o convenios de empresa.
3. **Viabilidad Procesal y Deontológica:**
   - Cortafuegos estricto contra el delito de intrusismo (Art. 403 CP): erradicación de porcentajes de victoria (*"78%"*) y sustitución por bandas cualitativas de solidez argumental.
   - Bloqueo imperativo ante causas con postulación obligatoria de Abogado y Procurador en litigios >2.000 € (Arts. 23 y 31 LEC).
   - Motor de calendario judicial (`calendar_engine.py`) con dataset de los **8.131 festivos municipales** más la regla procesal del **Día de Gracia** (Art. 135.5 LEC: hasta las 15:00 horas del siguiente día hábil).

---

#### BLOQUE 2: ESPECIFICACIÓN DE ARQUITECTURA DE SOFTWARE Y FLUJO DE DATOS
Diseña la arquitectura técnica completa del sistema sin ambigüedades:
1. **Diagrama de Componentes y Flujo de Estados (Formato Mermaid):**
   - Flujo secuencial de las 4 fases:
     * *Fase 1: Triaje Multihop* (Detección de ramas con probabilidad, preguntas aclaratorias ante ambigüedad como falsos autónomos).
     * *Fase 2: Ingesta Quirúrgica* (BOE REST API + LanceDB local + fallback worker `playwright-stealth`).
     * *Fase 3: Juicio Contradictorio* (Defensa del Usuario vs Posición de la Contraparte dirimido por Magistrado bajo **lógica disyuntiva estricta**, prohibiendo acuerdos salomónicos en materias de derecho estricto).
     * *Fase 4: Guardarraíles y Auditoría NLI* (Token Fuzzy Matching ≥95%, validación de entailment semántico y cálculo de días hábiles preclusivos).
2. **Diseño de la Interfaz Web Local Reactiva (Arquitectura Web Moderna):**
   - **Arquitectura UI Desacoplada:** Backend local en **FastAPI (Python)** exponiendo endpoints REST y streaming por Server-Sent Events (SSE) en `/api/consultar/stream` + Frontend Web moderno (Tailwind CSS, estética dark/slate legal prémium tipo Harvey/Perplexity, iconos Lucide).
   - Maquetación y componentes visuales:
     * Panel central de chat conversacional con **streaming ultrafluido token a token** (la interfaz nunca se congela).
     * Pestañas/acordeones interactivos para visualizar el debate: *"Argumentos de Defensa"*, *"Ataque de la Contraparte"* y *"Resolución del Magistrado"*.
     * Selector superior de modos: *Modo Eco* (Gemini Flash), *Modo Equilibrado* (Flash + Sonnet), *Modo Pro* (Flash + Opus 5.5 / Argon con thinking configurable).
     * Panel lateral retráctil / visor dividido: Visualizador en vivo de artículos del BOE con resaltado de párrafos citados, extractos de sentencias del CENDOJ y texto del convenio colectivo aplicable.
     * Línea temporal gráfica interactiva de plazos procesales (días hábiles restantes y fecha límite con Día de Gracia).
     * Soporte de arrastrar y soltar (drag & drop) para adjuntos (PDFs de contratos, nóminas, cartas de despido o sanciones municipales).
     * Preparada para ejecución en navegador local (`localhost:8000` / `localhost:3000`) o instalable con 1 clic como **PWA (Progressive Web App)** con icono propio en Windows.

---

#### BLOQUE 3: CONTRATOS DE DATOS Y ESQUEMA DE BASE DE DATOS (ESPECIFICACIÓN FORMAL)
Define la estructura de datos exacta (esquemas Pydantic y DDL SQL) que utilizarán los módulos:
1. **Modelos Pydantic Tipados para Contratos entre Fases:**
   - `TriageOutputSchema`: campos para jurisdicción, submateria, grado de ambigüedad, preguntas de clarificación, alertas de prescripción, IDs de normas BOE objetivo y convenio aplicable.
   - `DossierIngestaSchema`: artículos consolidados del BOE, extractos de sentencias (purgados de antecedentes contaminados) y cláusulas del convenio.
   - `DictamenCertificadoSchema`: banda cualitativa de solidez, resumen en lenguaje ciudadano, fundamentos con `source_id` y `verbatim_quote`, fortalezas, debilidades de la contraparte, pasos inmediatos y advertencia de postulación letrada.
2. **Esquema Relacional SQLite3 (Modo WAL):**
   - Tablas definitivas: `boe_bloques`, `cendoj_sentencias`, `convenios_cache`, `municipios_festivos` y `sesiones_consultas`.
3. **Esquema Vectorial LanceDB:**
   - Estructura de la tabla de embeddings para búsqueda semántica instantánea de resoluciones judiciales.

---

#### BLOQUE 4: GLOSARIO JURÍDICO Y GUÍA DE TRADUCCIÓN PARA EL DESARROLLADOR
Elabora una guía de referencia rápida para el ingeniero informático que traduzca conceptos legales a lógica de código:
1. **Tabla de Mapeo "Lenguaje Coloquial" vs "Institución Jurídica":**
   - Mapeo de al menos 15 casos típicos (ej. *"el casero no me devuelve la fianza por pintar"* &rarr; Arts. 21 y 36 LAU; *"me echan del trabajo estando de baja"* &rarr; Nulidad por Ley 15/2022 vs improcedencia; *"multa por aparcar en zona azul"* &rarr; Ordenanza municipal ORA/SER y vía de apremio).
2. **Tabla Maestra de Plazos Procesales Fatales (Preclusivos):**
   - Cómputo de días hábiles vs naturales, plazos en el orden social (20 días despido), civil (1 año extracontractual, 5 años contractual) y administrativo (1 mes reposición/alzada).
3. **Reglas de Derecho Foral:**
   - Cuándo el Código Civil queda desplazado por el *Codi Civil de Catalunya*, *Fuero Nuevo de Navarra*, etc.

---

#### BLOQUE 5: PLAN DE SPRINTS Y DEFINICIÓN DE TERMINADO (DEFINITION OF DONE)
Estructura la hoja de ruta de implementación en 5 Sprints detallados:
- **Sprint 1: Conectividad y Router Multimodelo** (Pruebas unitarias de llamadas a Gemini y Claude).
- **Sprint 2: Capa de Datos (BOE REST, LanceDB y Convenios)** (Descarga atómica y caché).
- **Sprint 3: Motor de Calendario y Guardarraíles Semánticos** (Fuzzy match al 95%, festivos municipales y NLI).
- **Sprint 4: Pipeline Agéntico y Suite de Benchmark Ciego** (Ejecución de los 25 casos de prueba contra el TS y Audiencias).
- **Sprint 5: Interfaz Web Reactiva (FastAPI + Modern Web UI) y PWA** (UI web reactiva con streaming SSE, visor lateral de artículos y soporte drag & drop).
- Para cada Sprint, define:
  * Archivos concretos a crear.
  * Pruebas unitarias a superar.
  * Criterios de aceptación objetivos.

---

### FORMATO DE SALIDA ESPERADO
Presenta el plan en un **documento técnico estructurado en Markdown**, exhaustivo, con diagramas Mermaid, tablas comparativas, modelos de datos Pydantic completos y esquemas DDL SQL listos para ser implementados cuando arranque la fase de programación.
```
