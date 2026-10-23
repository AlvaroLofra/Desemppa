-- 0003: los proveedores pasan a ser configurables (config/providers.toml). Se quita el CHECK
-- proveedor IN ('gemini','claude') del ledger y se renombran los ids antiguos.

CREATE TABLE llm_calls_ledger_new (
  id INTEGER PRIMARY KEY, consulta_id TEXT, fase TEXT NOT NULL, rol TEXT,
  proveedor TEXT NOT NULL, modelo TEXT NOT NULL, effort TEXT,
  input_tokens INTEGER, output_tokens INTEGER, coste_equivalente_usd REAL,
  latencia_ms INTEGER NOT NULL, ok INTEGER NOT NULL, error_tipo TEXT,
  creado_en TEXT NOT NULL DEFAULT (datetime('now'))
);
INSERT INTO llm_calls_ledger_new
  SELECT id, consulta_id, fase, rol,
         CASE proveedor WHEN 'gemini' THEN 'gemini_api' WHEN 'claude' THEN 'claude_cli' ELSE proveedor END,
         modelo, effort, input_tokens, output_tokens, coste_equivalente_usd, latencia_ms, ok, error_tipo, creado_en
  FROM llm_calls_ledger;
DROP TABLE llm_calls_ledger;
ALTER TABLE llm_calls_ledger_new RENAME TO llm_calls_ledger;
CREATE INDEX ix_ledger_ventana ON llm_calls_ledger(proveedor, creado_en);

UPDATE circuit_breaker_state SET proveedor = 'gemini_api' WHERE proveedor = 'gemini';
UPDATE circuit_breaker_state SET proveedor = 'claude_cli' WHERE proveedor = 'claude';
