-- 0006: biblioteca de documentos del usuario (sentencias, convenios, contratos…) reutilizables en varias consultas.
-- El texto se guarda cifrado (DPAPI) como en `adjuntos`; al usarlo en una consulta se copia como adjunto nuevo.
CREATE TABLE biblioteca (
  doc_id TEXT PRIMARY KEY,
  nombre TEXT NOT NULL,
  sha256 TEXT NOT NULL UNIQUE,
  tipo_detectado TEXT,
  texto_cifrado BLOB NOT NULL,
  caracteres INTEGER NOT NULL,
  ocr_usado INTEGER NOT NULL DEFAULT 0,
  permitir_envio INTEGER NOT NULL DEFAULT 0,
  creado_en TEXT NOT NULL DEFAULT (datetime('now'))
);
