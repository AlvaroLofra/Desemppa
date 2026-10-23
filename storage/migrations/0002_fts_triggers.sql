-- 0002_fts_triggers.sql — sincronización de las tablas FTS5 "external content" (dossier §3.2, nota final)

CREATE TRIGGER boe_bloques_ai AFTER INSERT ON boe_bloques BEGIN
  INSERT INTO boe_bloques_fts(rowid, texto_consolidado, titulo) VALUES (new.id, new.texto_consolidado, new.titulo);
END;
CREATE TRIGGER boe_bloques_ad AFTER DELETE ON boe_bloques BEGIN
  INSERT INTO boe_bloques_fts(boe_bloques_fts, rowid, texto_consolidado, titulo)
  VALUES ('delete', old.id, old.texto_consolidado, old.titulo);
END;
CREATE TRIGGER boe_bloques_au AFTER UPDATE ON boe_bloques BEGIN
  INSERT INTO boe_bloques_fts(boe_bloques_fts, rowid, texto_consolidado, titulo)
  VALUES ('delete', old.id, old.texto_consolidado, old.titulo);
  INSERT INTO boe_bloques_fts(rowid, texto_consolidado, titulo) VALUES (new.id, new.texto_consolidado, new.titulo);
END;

CREATE TRIGGER cendoj_ai AFTER INSERT ON cendoj_sentencias BEGIN
  INSERT INTO cendoj_fts(rowid, fundamentos_mayoria, fallo) VALUES (new.id, new.fundamentos_mayoria, new.fallo);
END;
CREATE TRIGGER cendoj_ad AFTER DELETE ON cendoj_sentencias BEGIN
  INSERT INTO cendoj_fts(cendoj_fts, rowid, fundamentos_mayoria, fallo)
  VALUES ('delete', old.id, old.fundamentos_mayoria, old.fallo);
END;
CREATE TRIGGER cendoj_au AFTER UPDATE ON cendoj_sentencias BEGIN
  INSERT INTO cendoj_fts(cendoj_fts, rowid, fundamentos_mayoria, fallo)
  VALUES ('delete', old.id, old.fundamentos_mayoria, old.fallo);
  INSERT INTO cendoj_fts(rowid, fundamentos_mayoria, fallo) VALUES (new.id, new.fundamentos_mayoria, new.fallo);
END;

CREATE TRIGGER convenios_art_ai AFTER INSERT ON convenios_articulos BEGIN
  INSERT INTO convenios_fts(rowid, texto, titulo) VALUES (new.id, new.texto, new.titulo);
END;
CREATE TRIGGER convenios_art_ad AFTER DELETE ON convenios_articulos BEGIN
  INSERT INTO convenios_fts(convenios_fts, rowid, texto, titulo) VALUES ('delete', old.id, old.texto, old.titulo);
END;
CREATE TRIGGER convenios_art_au AFTER UPDATE ON convenios_articulos BEGIN
  INSERT INTO convenios_fts(convenios_fts, rowid, texto, titulo) VALUES ('delete', old.id, old.texto, old.titulo);
  INSERT INTO convenios_fts(rowid, texto, titulo) VALUES (new.id, new.texto, new.titulo);
END;
