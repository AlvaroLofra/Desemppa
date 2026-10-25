# Mapa de Navegación Quirúrgica — Desemppa

Referencia rápida de alta densidad para localizar cualquier módulo del proyecto sin ejecutar búsquedas exploratorias globales (`grep` / `find`).

---

## 1. Núcleo y Pipeline (Backend)

* **Contratos de datos (Pydantic):** `core/schemas.py`
* **Orquestador de las 4 fases:** `core/orchestrator.py`
* **Cortafuegos anti-invención y afirmaciones tipadas:** `core/firewall.py`
* **Validación NLI y verificación cruzada:** `core/nli.py`
* **Fechas estrictas del usuario (anti-invención):** `core/fechas_es.py`
* **Guardarraíles G1–G10 y citas literales:** `core/validators.py`
* **Motor determinista de plazos y días hábiles:** `core/calendar_engine.py` (reglas en `config/plazos.yaml`)
* **Abogado, procurador y MASC LO 1/2025:** `core/postulacion_rules.py` (reglas en `config/postulacion.yaml`)
* **Árbol determinista de trámites:** `core/hoja_de_ruta.py` (reglas en `config/hojas_de_ruta.yaml`)
* **Router y resiliencia de modelos:** `core/router.py` (config en `config/profiles.toml` y `config/models.toml`)
* **Prompts del sistema de los agentes:** `core/prompts/` (`magistrado.md`, `triaje.md`, `defensa.md`, `contraparte.md`)
* **Esquema de base de datos SQLite y migraciones:** `storage/database.py` y `storage/migrations/`

---

## 2. Conectores y Fuentes Oficiales

* **BOE con vigencia temporal:** `connectors/boe_client.py` y `core/temporal_sync.py`
* **Derecho de la Unión Europea (Cellar):** `connectors/eurlex_client.py`
* **Convenios colectivos (FTS5):** `connectors/convenios_db.py` y `connectors/convenios_boe.py`
* **Jurisprudencia y vector store:** `connectors/retriever.py`, `connectors/cendoj_fetcher.py`

---

## 3. API y Red Local

* **Endpoints REST + SSE:** `api/main.py`
* **Compartir en LAN y tokens de invitados:** `api/red_local.py`

---

## 4. Frontend (React / TypeScript en `web/src/`)

* **Tipos globales:** `web/src/lib/types.ts`
* **Cliente API y SSE:** `web/src/lib/api.ts`
* **Generación determinista de escritos sin LLM:** `web/src/lib/escritos.ts`
* **Vista principal y dictamen:** `web/src/components/Results.tsx`
* **Vista técnica procesal:** `web/src/components/VistaProfesional.tsx`
* **Visor lateral de fuentes (drawer):** `web/src/components/SourceViewer.tsx`
* **Hoja de ruta interactiva:** `web/src/components/HojaDeRuta.tsx`
* **Ajustes, modelos y salud:** `web/src/components/settings/`
