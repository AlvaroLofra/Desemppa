-- 0009: corpus legal local (grandes códigos del BOE con todas sus versiones) y búsqueda por vigencia.
-- boe_bloques ya guarda una fila por versión; aquí se registra qué normas están descargadas enteras, el orden y la
-- ubicación (Libro > Título > Capítulo) de cada precepto y la fecha de actualización que dio el índice del BOE, para
-- actualizar solo lo que cambia.
CREATE TABLE IF NOT EXISTS boe_corpus (
  id_norma          TEXT PRIMARY KEY CHECK (id_norma GLOB 'BOE-A-[0-9][0-9][0-9][0-9]-*'),
  alias             TEXT NOT NULL,
  titulo            TEXT NOT NULL DEFAULT '',
  estado            TEXT NOT NULL DEFAULT 'pendiente'
                    CHECK (estado IN ('pendiente', 'en_curso', 'completa', 'parcial', 'error')),
  preceptos         INTEGER NOT NULL DEFAULT 0,      -- preceptos del índice oficial
  preceptos_ok      INTEGER NOT NULL DEFAULT 0,      -- preceptos con texto en boe_bloques
  errores           INTEGER NOT NULL DEFAULT 0,
  modo              TEXT,                            -- texto_completo | bloques
  ultimo_error      TEXT,
  actualizado_en    TEXT
);

CREATE TABLE IF NOT EXISTS boe_corpus_bloques (
  id_norma                TEXT NOT NULL,
  id_bloque               TEXT NOT NULL,
  orden                   INTEGER NOT NULL,
  ubicacion               TEXT NOT NULL DEFAULT '',
  fecha_actualizacion_boe TEXT,                      -- ISO; la del índice oficial al descargarlo
  ingerido_en             TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (id_norma, id_bloque)
);

-- Búsqueda «a la fecha de los hechos»: versión vigente si desde <= fecha < hasta (o hasta NULL).
CREATE INDEX IF NOT EXISTS ix_boe_bloques_rango ON boe_bloques(version_vigencia_desde, version_vigencia_hasta);
