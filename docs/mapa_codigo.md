# Mapa de Navegación Quirúrgica — Desemppa

Referencia rápida de alta densidad para localizar cualquier módulo del proyecto sin ejecutar búsquedas exploratorias globales (`grep` / `find`).

Visión y criterio de alcance: [vision.md](vision.md). Plan en curso: [hoja_de_ruta.md](hoja_de_ruta.md) («Cobertura general verificada»).

---

## 1. Núcleo y Pipeline (Backend)

* **Contratos de datos (Pydantic):** `core/schemas.py`
* **Orquestador de las 4 fases:** `core/orchestrator.py`
* **Cortafuegos anti-invención y afirmaciones tipadas:** `core/firewall.py`
* **Validación NLI y verificación cruzada:** `core/nli.py`
* **Fechas estrictas del usuario (anti-invención):** `core/fechas_es.py`
* **Guardarraíles G1–G10 y citas literales:** `core/validators.py`
* **Motor determinista de plazos y días hábiles:** `core/calendar_engine.py` (reglas en `config/plazos.yaml`, cada una con citas literales que comprueba `scripts/verificar_plazos.py`)
* **Abogado, procurador y MASC LO 1/2025:** `core/postulacion_rules.py` (reglas en `config/postulacion.yaml`)
* **Árbol determinista de trámites:** `core/hoja_de_ruta.py` (reglas en `config/hojas_de_ruta.yaml`)
* **Router y resiliencia de modelos:** `core/router.py` (config en `config/profiles.toml` y `config/models.toml`)
* **Prompts del sistema de los agentes:** `core/prompts/` (`magistrado.md`, `triaje.md`, `defensa.md`, `contraparte.md`, `cribado.md`)
* **Descubrimiento de preceptos (lista cerrada):** `Orchestrator._descubrir_articulos` / `_fuente_boe` / `_sin_norma_verificable` en `core/orchestrator.py`; `limpiar_busquedas` e `indices_elegidos`; tests en `tests/unit/test_descubrimiento.py`
* **Esquema de base de datos SQLite y migraciones:** `storage/database.py` y `storage/migrations/`

---

## 2. Conectores y Fuentes Oficiales

* **BOE con vigencia temporal:** `connectors/boe_client.py` (`buscar_a_fecha`, guarda de identidad `titulo_boe_contiene`) y `core/temporal_sync.py`
* **Corpus legal local (grandes códigos enteros, todas las versiones):** `connectors/corpus_legal.py`; descarga con `scripts/ingerir_corpus.py` o `POST /api/corpus/ingerir`; núcleo en `config/catalogo_normas.json` (`nucleo`); migración `0009`
* **Búsqueda de preceptos a la fecha de los hechos (BM25 + vectores + RRF):** `connectors/recuperador_legislacion.py`; vectores en `storage/lance_schema.py::LegislacionStore`; embeddings locales ONNX en `connectors/embeddings.py::LocalEmbedder` (extra `embeddings`)
* **Derecho de la Unión Europea (Cellar):** `connectors/eurlex_client.py`
* **Convenios colectivos (FTS5):** `connectors/convenios_db.py` y `connectors/convenios_boe.py`
* **Jurisprudencia y vector store:** `connectors/retriever.py`, `connectors/cendoj_fetcher.py`

---

## 3. API y Red Local

* **Endpoints REST + SSE:** `api/main.py`
* **Compartir en LAN y tokens de invitados:** `api/red_local.py`
* **Lanzador de escritorio (ventana + bandeja):** `launcher/desemppa.pyw` (lógica en `launcher/servidor.py`); instalación con `INSTALAR_DESEMPPA.bat` → `scripts/instalar.ps1`; icono con `scripts/generar_icono.py`
* **Batería verificable:** `benchmark/ejecutar.py` (`--reanudar`), `evaluar.py`, `juez.py`, `congelar.py` → `tests/golden/bateria/`, `comparar_ejecuciones.py`

---

## 4. Frontend (React / TypeScript en `web/src/`)

* **Tipos globales:** `web/src/lib/types.ts`
* **Cliente API y SSE:** `web/src/lib/api.ts`
* **Generación determinista de escritos sin LLM:** `web/src/lib/escritos.ts`
* **Vista principal y dictamen:** `web/src/components/Results.tsx`
* **Vista técnica procesal:** `web/src/components/VistaProfesional.tsx`
* **Visor lateral de fuentes (drawer):** `web/src/components/SourceViewer.tsx`
* **Preguntas aclaratorias (UI):** `Clarification` en `web/src/components/Results.tsx` + `web/src/lib/aclaraciones.ts`; backend `normalizar_pregunta` / `ya_preguntado` en `core/orchestrator.py`
* **Historial (renombrar, archivar, borrar):** `web/src/components/Sidebar.tsx`; `PATCH`/`DELETE /api/consultas/{id}`; migración `0008`
* **Asistente de jurisprudencia:** `web/src/components/Jurisprudencia.tsx`; `GET /api/jurisprudencia/resumen`
* **Hoja de ruta interactiva:** `web/src/components/HojaDeRuta.tsx`
* **Ajustes, modelos y salud:** `web/src/components/settings/`
