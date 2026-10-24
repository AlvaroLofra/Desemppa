-- 0004: origen de cada consulta para compartir la app en la red local.
-- 'local' = hecha en este ordenador; 'lan:<id>' = hecha por un invitado (id aleatorio de su navegador).
ALTER TABLE sesiones_consultas ADD COLUMN origen TEXT NOT NULL DEFAULT 'local';
CREATE INDEX idx_consultas_origen ON sesiones_consultas(origen, creado_en);
