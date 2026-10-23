# Datos y fuentes externas

## 1. Dónde viven los datos

| Qué | Dónde | En git |
|---|---|---|
| Datos de uso (consultas, caché, ledger, corpus, vectores, token, log) | `data/local/` (cambiable con `IURIS_DATA_DIR`) | No |
| Municipios INE | `data/municipios_ine.csv` | Sí |
| Festivos nacionales y autonómicos | `data/festivos/<año>.csv` | Sí |
| Lista candidata de convenios | `data/convenios_seed.yaml` | Sí |
| Catálogos jurídicos | `config/catalogo_normas.json`, `config/catalogo_materias.yaml`, `config/plazos.yaml`, `config/postulacion.yaml` | Sí |

⚠ Antes los datos de uso estaban en `%LOCALAPPDATA%\iuris`. Windows redirige esa carpeta para los procesos lanzados
desde la app de Claude (`…\Packages\Claude_…\LocalCache\Local\iuris`), lo que creaba dos bases de datos distintas.
`scripts/migrar_datos.py` copia la antigua a `data/local/` (el lanzador lo hace solo la primera vez). Ejecútalo
desde una terminal normal para que vea la carpeta real.

Copia de seguridad: basta con copiar `data/local/` con la app cerrada (los datos sensibles van cifrados con DPAPI:
solo se descifran con tu usuario de Windows en este equipo).

## 2. BOE — legislación consolidada (API de Datos Abiertos)

Base: `https://www.boe.es/datosabiertos/api/legislacion-consolidada` · Cliente: `connectors/boe_client.py`
(máx. 2 peticiones/s, User-Agent identificado) · Modelos y parser: `connectors/boe_models.py`.

| Endpoint | Formato | Uso |
|---|---|---|
| `GET /id/{id_norma}/metadatos` | JSON | Título, rango, ámbito, derogación, fecha de actualización |
| `GET /id/{id_norma}/texto/indice` | JSON | Bloques de la norma (`id`, `titulo`); `data` puede ser objeto o lista |
| `GET /id/{id_norma}/texto/bloque/{id_bloque}` | **XML** | Texto de un bloque con **todas sus versiones** (`<version fecha_vigencia=… id_norma=…>`) |
| `GET /?query={"query":{"query_string":{"query":"titulo:\"…\""}}}` | JSON | Búsqueda de normas por título |
| `https://www.boe.es/datosabiertos/api/boe/sumario/AAAAMMDD` | JSON | Sumario diario (así se localizan las resoluciones de festivos) |

Particularidades (todas resueltas en el código):
- **Identificadores de bloque no uniformes**: LAU `a36`; Código Civil `art1561`; Ley 15/2022 posicionales (`a2-8` =
  art. 26); LPH ordinales en letra (`anoveno`, `adiecisiete`). `BOERepository.resolve_bloque` usa el índice oficial y
  el título del bloque ("Artículo 26", "Artículo noveno").
- **Versiones**: la aplicable es la vigente en la **fecha de los hechos** (`core/temporal_sync.py`), con aviso si se
  reformó después. Si hay dos versiones con la misma fecha (correcciones), prevalece la última publicada.
- Caché en SQLite (`boe_normas`, `boe_bloques` + FTS5) con caducidad de 7 días.
- Verificar que el catálogo sigue existiendo: `uv run python scripts/verificar_catalogo.py` (hoy: 75 artículos, 0 fallos).

Normas núcleo: 40 identificadores verificados en `config/catalogo_normas.json` (CE, CC, LEC, ET, LRJS, LAU, LPH,
TRLGDCU, Ley 39/2015, LJCA, LGT, Ley de Tráfico, CCCat libros I–VI, Fuero Nuevo de Navarra…).

## 3. Jurisprudencia (CENDOJ)

- **Sin scraping automatizado** (decisión del dossier §1.2.2): el corpus crece importando sentencias que aporta el
  usuario (PDF o texto del CENDOJ) por la API `POST /api/jurisprudencia/importar`.
- `connectors/cendoj_parser.py`: extrae ROJ, ECLI, fecha, órgano y ponente; separa antecedentes, fundamentos de
  derecho (mayoría), fallo y **votos particulares** (aislados: nunca entran en el dossier ni en los vectores); purga
  de los antecedentes la historia procesal previa (para que el benchmark no "vea" el resultado).
- `connectors/cendoj_fetcher.py`: `CendojRepository` (SQLite + LanceDB), cola de búsquedas pendientes y
  `PoliteFetcher` (1 petición cada 10 s, tope diario) para descargas puntuales de URLs concretas.
- Búsqueda: `connectors/retriever.py` → FTS5/BM25 + vectores (Gemini Embedding 768 dim, si hay clave) con fusión
  RRF; filtra por jurisdicción.
- **Cómo conseguir sentencias**: buscador del CENDOJ (`https://www.poderjudicial.es/search/`), filtrar por
  jurisdicción, tribunal (TS / Audiencias Provinciales) y términos (p. ej. "devolución fianza pintura"); descargar el
  PDF de cada resolución; importarlo. Priorizar las submaterias de `config/catalogo_materias.yaml`.

## 4. Convenios colectivos

- `connectors/convenios_db.py`: `ConveniosRepository` con versiones (vigencia), artículos (FTS5) y **tablas
  salariales verificadas**: cada fila se acepta solo si su texto aparece literalmente (≥ 95 %) en el convenio y
  contiene el importe declarado.
- Estado: 30 candidatos en `data/convenios_seed.yaml` **sin código REGCON ni texto** (no se cargan hasta tenerlos).
- Fuentes: REGCON del Ministerio de Trabajo, BOE (convenios estatales) y boletines provinciales (BOP). La versión
  vigente es la última publicada en el boletín oficial.
- Pendiente: script/UI de importación (ver [hoja_de_ruta.md](hoja_de_ruta.md)).

## 5. Calendario: municipios y festivos

- Municipios: `data/municipios_ine.csv` (8.131, diccionario INE 2026) generado con
  `uv run python scripts/build_calendar_data.py municipios <diccionarioAA.xlsx>` desde
  `https://www.ine.es/daco/daco42/codmun/diccionarioAA.xlsx`.
- Festivos nacionales y autonómicos: resolución anual de la Dirección General de Trabajo en el BOE ("relación de
  fiestas laborales para el año AAAA", se publica en octubre del año anterior). 2026: `BOE-A-2025-21667`.
  Cargar un año: `uv run python scripts/build_calendar_data.py festivos 2027 BOE-A-AAAA-NNNNN`. Para encontrar el id:
  buscar en los sumarios de octubre (§2) el título "fiestas laborales para el año 2027".
- Festivos locales: dos por municipio, publicados por cada comunidad o provincia. Hoy **no hay ninguno cargado**: el
  motor avisa y cuenta prudentemente. Se pueden añadir en la tabla `municipios_festivos` (`ambito='local'`,
  `codigo_ine`, `fuente`) o como CSV en `data/festivos/` con columnas
  `fecha,ambito,ccaa,codigo_ine,descripcion,fuente,fuente_ref`.
- Años sin resolución cargada: solo se descuentan las fiestas nacionales fijas (1-ene, 1-may, 12-oct, 25-dic) y se avisa.

## 6. Esquema de la base de datos

`storage/migrations/` (se aplican en orden al arrancar; para cambiar el esquema, añade `0004_…sql`, nunca edites una
migración ya aplicada):

| Tabla | Contenido |
|---|---|
| `schema_migrations` | Migraciones aplicadas |
| `boe_normas`, `boe_bloques` (+ `boe_bloques_fts`) | Caché del BOE por versión de bloque |
| `cendoj_sentencias` (+ `cendoj_fts`), `cendoj_fetch_queue` | Corpus de jurisprudencia y búsquedas pendientes |
| `convenios_cache`, `convenios_versiones`, `convenios_articulos` (+ `convenios_fts`), `convenios_tablas_salariales` | Convenios |
| `municipios`, `municipios_festivos`, `calendario_cobertura` | Calendario (los nacionales/autonómicos se leen de CSV) |
| `sesiones_consultas` | Consulta: texto original y mapa de seudónimos **cifrados**, triaje, dossier, debate, dictamen, estado |
| `consulta_eventos` | Eventos SSE persistidos (replay) |
| `adjuntos` | Texto extraído cifrado, tipo detectado, consentimiento de envío |
| `llm_calls_ledger` | Cada llamada a un modelo: proveedor, modelo, effort, tokens, latencia, ok/error |
| `circuit_breaker_state` | Breakers por proveedor |

LanceDB `jurisprudencia_chunks`: `chunk_id, roj_id, ecli, nivel, tribunal, jurisdiccion, submaterias,
fecha_resolucion, seccion (fundamentos_mayoria|fallo), fd_numero, chunk_text, normas_citadas, vector[768],
embedding_model, texto_hash` (`storage/lance_schema.py`).

## 7. Datos personales
- Antes de enviar texto a un modelo: `core/pii_redactor.py` sustituye DNI/NIE (con letra de control válida), IBAN,
  teléfonos, emails, matrículas y nombres introducidos por fórmulas ("me llamo", "D.", "Sra.") por tokens
  `[[TIPO_n]]` reversibles. El mapa se guarda cifrado y solo se restaura en local.
- ⚠ La detección de nombres no es exhaustiva: un nombre sin fórmula previa no se detecta.
