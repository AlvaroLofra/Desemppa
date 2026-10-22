-- 0001_init.sql — DDL literal del dossier v3, Bloque 3.2
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 5000;
PRAGMA foreign_keys = ON;
PRAGMA synchronous = NORMAL;

CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT (datetime('now')));

-- ===== BOE =====
CREATE TABLE boe_normas (
  id_norma            TEXT PRIMARY KEY CHECK (id_norma GLOB 'BOE-A-[0-9][0-9][0-9][0-9]-*'),
  titulo              TEXT NOT NULL,
  rango               TEXT,                       -- Ley, Real Decreto Legislativo, Ley Orgánica…
  ambito              TEXT NOT NULL DEFAULT 'estatal', -- estatal | autonomico:<CCAA>
  estado              TEXT NOT NULL CHECK (estado IN ('vigente','derogada','derogada_parcial')),
  fecha_actualizacion TEXT,                       -- ISO-8601
  metadatos_json      TEXT,
  fetched_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE boe_bloques (                        -- una fila por VERSIÓN de bloque
  id                  INTEGER PRIMARY KEY,
  id_norma            TEXT NOT NULL REFERENCES boe_normas(id_norma),
  id_bloque           TEXT NOT NULL,              -- 'a36', 'dt1', 'preambulo'
  titulo              TEXT,
  version_vigencia_desde TEXT NOT NULL,
  version_vigencia_hasta TEXT,                    -- NULL = versión actual
  id_norma_modificadora TEXT,                     -- norma que introdujo la versión
  texto_consolidado   TEXT NOT NULL,
  texto_hash          TEXT NOT NULL,              -- sha256 del texto normalizado
  cached_at           TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (id_norma, id_bloque, version_vigencia_desde)
);
CREATE INDEX ix_boe_bloques_vigencia ON boe_bloques(id_norma, id_bloque, version_vigencia_desde);
CREATE VIRTUAL TABLE boe_bloques_fts USING fts5(texto_consolidado, titulo, content='boe_bloques', content_rowid='id', tokenize='unicode61 remove_diacritics 2');

-- ===== CENDOJ =====
CREATE TABLE cendoj_sentencias (
  id                  INTEGER PRIMARY KEY,
  roj_id              TEXT NOT NULL UNIQUE,       -- 'STS 4512/2023'
  ecli                TEXT UNIQUE,
  tribunal            TEXT NOT NULL,
  nivel               TEXT NOT NULL CHECK (nivel IN ('TS','AN','TSJ','AP','JUZGADO')),
  sala_seccion        TEXT,
  jurisdiccion        TEXT NOT NULL CHECK (jurisdiccion IN ('civil','social','contencioso','penal','militar')),
  submaterias         TEXT NOT NULL DEFAULT '[]', -- JSON array de claves del catálogo
  fecha_resolucion    TEXT NOT NULL,
  ponente             TEXT,
  antecedentes_purgados TEXT,                     -- solo hechos, sin resoluciones previas
  fundamentos_mayoria TEXT NOT NULL,
  voto_particular     TEXT,                       -- aislado; nunca entra en el dossier
  fallo               TEXT NOT NULL,
  normas_citadas      TEXT NOT NULL DEFAULT '[]', -- JSON [{id_norma, id_bloque}]
  origen              TEXT NOT NULL CHECK (origen IN ('fetch','import_usuario','seed')),
  url_oficial         TEXT,
  texto_hash          TEXT NOT NULL,
  cached_at           TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX ix_cendoj_juris_fecha ON cendoj_sentencias(jurisdiccion, nivel, fecha_resolucion);
CREATE VIRTUAL TABLE cendoj_fts USING fts5(fundamentos_mayoria, fallo, content='cendoj_sentencias', content_rowid='id', tokenize='unicode61 remove_diacritics 2');

CREATE TABLE cendoj_fetch_queue (
  id INTEGER PRIMARY KEY,
  query TEXT NOT NULL, prioridad INTEGER NOT NULL DEFAULT 5,
  estado TEXT NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente','en_curso','hecho','error')),
  intentos INTEGER NOT NULL DEFAULT 0, ultimo_error TEXT,
  creado_en TEXT NOT NULL DEFAULT (datetime('now')), actualizado_en TEXT
);

-- ===== Convenios =====
CREATE TABLE convenios_cache (
  codigo_convenio     TEXT PRIMARY KEY,           -- código REGCON
  denominacion        TEXT NOT NULL,
  ambito_funcional    TEXT NOT NULL,              -- sector
  ambito_territorial  TEXT NOT NULL,              -- 'estatal' | provincia | CCAA
  cnae                TEXT NOT NULL DEFAULT '[]', -- JSON
  trabajadores_afectados INTEGER,
  prioridad_seed      INTEGER                     -- 1..30
);
CREATE TABLE convenios_versiones (
  version_id          TEXT PRIMARY KEY,           -- '<codigo>:<año publicación>'
  codigo_convenio     TEXT NOT NULL REFERENCES convenios_cache(codigo_convenio),
  boletin_ref         TEXT NOT NULL,              -- 'BOE-A-2024-xxxx' / 'BOCM 2024-xx-xx'
  vigencia_desde      TEXT NOT NULL,
  vigencia_hasta      TEXT,
  ultraactividad      INTEGER NOT NULL DEFAULT 0,
  texto_integro       TEXT NOT NULL,
  cached_at           TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE convenios_articulos (
  id INTEGER PRIMARY KEY,
  version_id TEXT NOT NULL REFERENCES convenios_versiones(version_id),
  articulo TEXT NOT NULL, titulo TEXT, texto TEXT NOT NULL,
  UNIQUE (version_id, articulo)
);
CREATE VIRTUAL TABLE convenios_fts USING fts5(texto, titulo, content='convenios_articulos', content_rowid='id', tokenize='unicode61 remove_diacritics 2');
CREATE TABLE convenios_tablas_salariales (
  id INTEGER PRIMARY KEY,
  version_id TEXT NOT NULL REFERENCES convenios_versiones(version_id),
  anio INTEGER NOT NULL, grupo_categoria TEXT NOT NULL, concepto TEXT NOT NULL,
  importe_eur REAL NOT NULL CHECK (importe_eur >= 0),
  periodicidad TEXT NOT NULL CHECK (periodicidad IN ('mensual','anual','diaria','hora')),
  verificado_fuzzy REAL NOT NULL CHECK (verificado_fuzzy >= 95)
);

-- ===== Calendario =====
CREATE TABLE municipios (
  codigo_ine TEXT PRIMARY KEY CHECK (length(codigo_ine) = 5),
  nombre TEXT NOT NULL, provincia TEXT NOT NULL, ccaa TEXT NOT NULL,
  partido_judicial TEXT
);
CREATE TABLE municipios_festivos (
  id INTEGER PRIMARY KEY,
  fecha TEXT NOT NULL,
  ambito TEXT NOT NULL CHECK (ambito IN ('nacional','autonomico','local')),
  ccaa TEXT,                                       -- NULL si nacional
  codigo_ine TEXT REFERENCES municipios(codigo_ine), -- solo si local
  descripcion TEXT NOT NULL,
  fuente TEXT NOT NULL CHECK (fuente IN ('boe','boletin_autonomico','bop','usuario')),
  fuente_ref TEXT,
  verificado INTEGER NOT NULL DEFAULT 1,
  CHECK ((ambito='local' AND codigo_ine IS NOT NULL) OR (ambito<>'local' AND codigo_ine IS NULL)),
  UNIQUE (fecha, ambito, ccaa, codigo_ine)
);
CREATE INDEX ix_festivos_lookup ON municipios_festivos(fecha, ccaa, codigo_ine);
CREATE TABLE calendario_cobertura (                -- qué años/ámbitos están cargados
  anio INTEGER NOT NULL, ambito TEXT NOT NULL, clave TEXT NOT NULL, completo INTEGER NOT NULL,
  PRIMARY KEY (anio, ambito, clave)
);

-- ===== Sesiones =====
CREATE TABLE sesiones_consultas (
  consulta_id TEXT PRIMARY KEY,                    -- UUIDv7
  creado_en TEXT NOT NULL DEFAULT (datetime('now')),
  modo_utilizado TEXT NOT NULL CHECK (modo_utilizado IN ('eco','equilibrado','pro','auditoria')),
  estado TEXT NOT NULL,                            -- estado de la máquina §2.2
  consulta_usuario_cifrada BLOB NOT NULL,          -- texto original cifrado (DPAPI de Windows)
  consulta_seudonimizada TEXT NOT NULL,
  pii_map_cifrado BLOB,
  triage_json TEXT,
  dossier_json TEXT,
  debate_json TEXT,
  dictamen_json TEXT,
  dictamen_markdown TEXT,
  banda_solidez TEXT,
  fuzzy_min_score REAL,
  guardrails_json TEXT,
  error TEXT
);
CREATE TABLE consulta_eventos (                    -- replay SSE
  consulta_id TEXT NOT NULL REFERENCES sesiones_consultas(consulta_id) ON DELETE CASCADE,
  seq INTEGER NOT NULL, tipo TEXT NOT NULL, data_json TEXT NOT NULL,
  creado_en TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (consulta_id, seq)
);
CREATE TABLE adjuntos (
  adjunto_id TEXT PRIMARY KEY, consulta_id TEXT REFERENCES sesiones_consultas(consulta_id) ON DELETE CASCADE,
  nombre TEXT NOT NULL, sha256 TEXT NOT NULL, tipo_detectado TEXT, -- nomina|contrato|carta_despido|sancion|otro
  texto_extraido_cifrado BLOB, ocr_usado INTEGER NOT NULL DEFAULT 0, permitir_gemini INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE llm_calls_ledger (
  id INTEGER PRIMARY KEY, consulta_id TEXT, fase TEXT NOT NULL, rol TEXT,
  proveedor TEXT NOT NULL CHECK (proveedor IN ('gemini','claude')), modelo TEXT NOT NULL, effort TEXT,
  input_tokens INTEGER, output_tokens INTEGER, coste_equivalente_usd REAL,
  latencia_ms INTEGER NOT NULL, ok INTEGER NOT NULL, error_tipo TEXT,
  creado_en TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX ix_ledger_ventana ON llm_calls_ledger(proveedor, creado_en);
CREATE TABLE circuit_breaker_state (
  proveedor TEXT PRIMARY KEY, estado TEXT NOT NULL CHECK (estado IN ('closed','open','half_open')),
  abierto_hasta TEXT, motivo TEXT
);
