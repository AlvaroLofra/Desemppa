# Guía Jurídica para Informáticos (Sin Saber Nada de Leyes)

Este documento traduce todos los conceptos jurídicos y los problemas legales pendientes de **Iuris-IA** al lenguaje de ingeniería de software, para que puedas mantener y evolucionar el proyecto sin tener formación en Derecho.

---

## 1. Cómo funciona el "Sistema Operativo" Legal Español (Jerarquía de Normas)

Piensa en el Derecho español como un sistema de configuración con **herencia y overrides**:

1. **Constitución y Leyes Estatales (BOE)** → Son el **Kernel / Configuración Base** (ej. *Estatuto de los Trabajadores* para laboral, *Ley de Arrendamientos Urbanos* para alquileres, *Código Civil* para contratos). Iuris-IA las descarga en tiempo real del BOE con la versión exacta que estaba vigente el día en que ocurrió el problema (`core/temporal_sync.py`).
2. **Derecho Foral (`vecindad_civil`)** → Es un **Override Regional de Código Civil**. En 6 territorios (Cataluña, Aragón, Navarra, País Vasco, Galicia y Baleares), ciertas reglas civiles (familia, herencias, algunos contratos) usan su propia ley autonómica en lugar del Código Civil estatal.
3. **Convenios Colectivos (`connectors/convenios_db.py`)** → En temas laborales, el *Estatuto de los Trabajadores* solo fija el **mínimo legal** (suelo). Por encima de él, cada sector (Construcción, Hostelería, Metal, Contact Center, Oficinas…) tiene un **fichero de configuración específico llamado Convenio Colectivo**, que mejora sueldos, vacaciones, horas anuales y define qué faltas son leves, graves o muy graves.
4. **Jurisprudencia (`connectors/cendoj_fetcher.py`)** → Son los **Logs de Producción / Casos de Test Resueltos** por los jueces (Tribunal Supremo y Audiencias Provinciales). Cuando una ley es ambigua, lo que importa es cómo la interpretan los jueces en casos reales anteriores.

---

## 2. Los 5 Problemas Jurídicos del Proyecto Explicados para Informáticos

### Problema 1: Caducidad vs. Prescripción y el Calendario Judicial (`config/plazos.yaml`)
En Derecho hay dos tipos de *timeouts* (plazos) que no tienen nada que ver entre sí:

- **Caducidad (Hard TTL con Pause/Resume)**:
  - Ejemplo estrella: **Despido laboral (`20 días hábiles`)**.
  - Si te despiden y pasan 20 días hábiles sin que actúes, **tu derecho muere para siempre (HTTP 410 Gone)**.
  - Solo se puede **pausar** el reloj presentando la "papeleta de conciliación" (SMAC). Al presentarla, el cronómetro se congela; cuando termina la conciliación sin acuerdo, el cronómetro **se reanuda donde se quedó** (no vuelve a 20).
- **Prescripción (Resettable Watchdog Timer)**:
  - Ejemplo: **Reclamar una factura o salarios impagados (`1 año` en laboral, `5 años` en civil)**.
  - Si envías una reclamación formal verificable (como un burofax), **el contador se resetea a 0** y vuelves a tener el plazo completo desde el principio.
- **Por qué un LLM nunca debe calcular fechas**:
  - En los juzgados españoles no cuentan los sábados, domingos, festivos nacionales, festivos de la Comunidad Autónoma, **2 festivos locales del municipio del juzgado**, ni tampoco **todo el mes de agosto** (salvo urgencias como despidos). Además, si el plazo vence el día $X$, la ley permite entregar el papel hasta las **15:00 h del día hábil siguiente** (*"día de gracia"*, art. 135.5 LEC).
  - Por eso Iuris-IA calcula las fechas con código Python puro en `core/calendar_engine.py` y nunca deja que el LLM sume días.

### Problema 2: El requisito de negociación previa (MASC) de la Ley Orgánica 1/2025 (`config/postulacion.yaml`)
Texto comprobado el 24-10-2026 en el BOE (LO 1/2025, BOE-A-2025-76, en vigor desde el 3-4-2025, arts. 2, 5 y 10).

- **En términos informáticos**: un *pre-flight check* obligatorio antes de abrir un ticket en el juzgado civil. Sin
  él, la demanda no se admite (art. 5.1: es un «requisito de procedibilidad»).
- **Qué cuenta como intento (art. 5.1)**: mediación, conciliación, opinión de un experto independiente, **oferta
  vinculante confidencial** o **negociación directa entre las partes** (o entre sus abogados). Tiene que versar sobre
  lo mismo que luego se pida al juez.
- **Cómo se demuestra (art. 10)**: por escrito. Vale un documento firmado por ambas partes o, si la otra parte no
  colabora, **cualquier documento que pruebe que recibió tu invitación o propuesta para negociar y pudo leerla
  entera** (en la práctica, un burofax con certificación de contenido que contenga esa propuesta; un simple «págame»
  sin propuesta de negociación es más discutible).
- **Cuándo se da por fracasado (art. 10.4)**: si pasan **30 días naturales** desde que la otra parte recibe la
  solicitud sin reunión ni respuesta escrita, entre otros supuestos.
- **Dónde se exige (art. 5.2)**: en los procesos declarativos y en los especiales del libro IV de la LEC — ahí está
  el **monitorio**, que **no** figura entre las excepciones. Sí están exceptuados, entre otros: derechos
  fundamentales, medidas del art. 158 CC, apoyos a personas con discapacidad, filiación, tutela sumaria de la
  posesión, obra ruinosa, ciertas medidas de menores y el **juicio cambiario**; y (art. 5.3) la demanda ejecutiva,
  las medidas cautelares previas, las diligencias preliminares, la jurisdicción voluntaria (salvo excepciones), el
  monitorio europeo y el proceso europeo de escasa cuantía.
- **Cómo lo resuelve Iuris-IA**: el aviso aparece en todas las reglas civiles de `config/postulacion.yaml`. Las
  excepciones no se evalúan automáticamente: el aviso es general.

### Problema 3: Postulación (`Abogado` y `Procurador` = Permisos RBAC para hablar con el Juez)
- En España existen dos profesionales distintos:
  - **Abogado**: el arquitecto que escribe la defensa técnica.
  - **Procurador**: el "mensajero oficial / API Gateway" entre tú y el juzgado que recibe notificaciones y presenta escritos.
- **La regla de los 2.000 € en Civil (`config/postulacion.yaml`)**:
  - Si reclamas **hasta 2.000 €** (o presentas la petición inicial de un juicio *monitorio* para cobrar una factura documentada), tienes permiso `root` para ir tú solo al juzgado sin abogado ni procurador.
  - Si reclamas **más de 2.000 €**, la ley te obliga a contratar abogado y procurador. Por seguridad legal (para no incurrir en intrusismo profesional, art. 403 del Código Penal), cuando Iuris-IA detecta que necesitas abogado obligatorio, **bloquea la generación de demandas judiciales** (`bloquea_escritos: true`) y se limita a informarte (la herramienta no redacta escritos ni burofaxes).

### Problema 4: Por qué no se puede hacer *scraping* de sentencias del CENDOJ
- El buscador público de sentencias en España se llama **CENDOJ** (dependiente del Consejo General del Poder Judicial, CGPJ).
- El **artículo 507 de la Ley Orgánica del Poder Judicial (LOPJ)** y el aviso legal del CGPJ prohíben expresamente hacer descargas masivas automatizadas (*scraping*) o crear bases de datos comerciales con sus sentencias. Además, tienen bloqueos anti-bot muy agresivos.
- **Cómo funciona en Iuris-IA**: En vez de hacer *scraping* ilegal, cuando tú quieras estudiar un tema a fondo, entras manualmente en el buscador del CENDOJ desde tu navegador, descargas los PDFs de las sentencias que te interesen en una carpeta y ejecutas:
  ```powershell
  uv run python scripts/importar_sentencias.py ruta/a/mis_pdfs
  ```
  Iuris-IA las trocea e indexa sus Fundamentos de Derecho (SQLite FTS5; y además LanceDB si hay clave de la Gemini API para los embeddings) y a partir de ese momento las usa y cita literalmente en tus consultas.

### Problema 5: Qué significa `PENDIENTE DE VALIDACIÓN JURÍDICA` en los YAML
- Los ficheros `config/plazos.yaml`, `config/postulacion.yaml` y `config/catalogo_materias.yaml` están cubiertos por *golden tests* (67 en total) que pasan al 100 %, pero los tests solo comprueban que el código hace lo que dicen los YAML, no que los YAML sean jurídicamente correctos.
- Sin embargo, en Derecho siempre hay excepciones finas (por ejemplo, qué pasa si el día de inicio del plazo es inhábil en vía administrativa frente a vía civil).
- Para tu **uso personal**, la herramienta ya te avisa claramente en pantalla de que los plazos son orientativos y te muestra el artículo exacto del BOE para que lo verifiques en un clic. Si algún día decidieras comercializarla, un abogado colegiado debería firmar la revisión de esos tres ficheros YAML (~4 horas de trabajo).
