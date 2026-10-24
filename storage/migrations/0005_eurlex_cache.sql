-- 0005: caché de documentos del Derecho de la UE (Cellar/EUR-Lex), por número CELEX.
CREATE TABLE eurlex_cache (
  celex TEXT PRIMARY KEY,
  html TEXT NOT NULL,
  descargado_en TEXT NOT NULL
);
