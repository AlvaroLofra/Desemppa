-- 0008: el usuario puede renombrar y archivar sus consultas desde el historial.
-- El título puede contener datos personales: se guarda cifrado con DPAPI (core/secure_store.py).
ALTER TABLE sesiones_consultas ADD COLUMN titulo_cifrado BLOB;
ALTER TABLE sesiones_consultas ADD COLUMN archivada INTEGER NOT NULL DEFAULT 0;
