# Guía Maestra de Contexto del Proyecto — Desemppa (antes Iuris-IA) (`CLAUDE.md` = `GEMINI.md`)

> **Instrucción para el Agente de IA (Claude Code / Gemini / Antigravity):**
> Este fichero (`CLAUDE.md` y su gemelo idéntico `GEMINI.md`) contiene las reglas operativas, el perfil del usuario, las restricciones de suscripciones/modelos y el mapa de lectura rápida para que puedas retomar el trabajo en **Desemppa** en cualquier sesión **sin pedir contexto adicional al usuario**.
> **Regla de sincronización:** Si en el futuro modificas `CLAUDE.md` o `GEMINI.md`, **debes actualizar ambos ficheros con exactamente el mismo contenido**.

---

## 1. Perfil del Usuario y Alcance del Proyecto

1. **Perfil del usuario**: El usuario es **informático / desarrollador de software**, pero **no tiene conocimientos de Derecho**. Siempre que expliques cualquier cuestión legal (plazos, caducidad vs. prescripción, postulación, MASC de la LO 1/2025, convenios, jurisprudencia), hazlo en **lenguaje sencillo, claro y con analogías de ingeniería de software** (ver [`docs/guia_juridica_para_informaticos.md`](docs/guia_juridica_para_informaticos.md)).
2. **Alcance actual (Opción A — Proyecto Personal Local)**:
   - El proyecto es de **uso exclusivamente personal y local** (`127.0.0.1:8000`) en Windows. No se va a comercializar ni publicar por ahora (aunque el análisis de viabilidad futura ya está documentado en [`docs/viabilidad_y_estrategia.md`](docs/viabilidad_y_estrategia.md)).
3. **Suscripciones y Modelos del Usuario (REGLA ESTRICTA)**:
   - El usuario **SOLO utiliza dos suscripciones mensuales de ~20 €/mes**:
     1. **Google AI Pro a través de Antigravity (`antigravity_cli`, ejecutable `agy`)**.
     2. **Claude Pro a través de Claude Code (`claude_cli`, ejecutable `claude`)**.
   - El usuario **NO tiene `GEMINI_API_KEY` configurada en su ordenador**. Ningún perfil por defecto (`config/profiles.toml` o `config/user_profiles.toml`) debe depender de `gemini_api`.
   - **Modelos disponibles en Antigravity (`agy models`)**:
     - `gemini-4-argon-low`, `gemini-4-argon-medium`, `gemini-4-argon-high` (alias `agy_gemini_argon`, `efforts = ["low", "medium", "high"]`)
     - `gemini-3.8-flash-low`, `gemini-3.8-flash-medium`, `gemini-3.8-flash-high` (alias `agy_gemini_flash`, `efforts = ["low", "medium", "high"]`). **Medido el 24-10-2026 con un prompt de ~47.000 caracteres: `medium` responde en ~50 s; `high` falla 3 de 3 veces** (el modelo intenta ejecutar un comando, el modo no interactivo se lo deniega y devuelve respuesta vacía). Por eso ningún perfil usa Flash en `high`. `gemini-4-argon-high` sí funciona (~46 s).
     - `claude-opus-5-5-low`, `claude-opus-5-5-medium`, `claude-opus-5-5-high` (alias `agy_claude_opus`)
     - `claude-sonnet-5-5-low`, `claude-sonnet-5-5-medium`, `claude-sonnet-5-5-high` (alias `agy_claude_sonnet`)
     - `gpt-oss-120b-medium` (alias `agy_gpt_oss`)
   - **Regla sobre modelos Flash**: De los modelos Flash **solo se usa Gemini 3.8 Flash (`agy_gemini_flash`)**, variando únicamente el nivel de esfuerzo (`low`, `medium`, `high`). No uses `gemini-3.5-flash` en los perfiles.
4. **Adaptabilidad Universal Multi-Compañía (por Plan o por API)**:
   - Además de los planes por suscripción CLI (`antigravity_cli`, `claude_cli`, `codex_cli`), la app soporta en [`core/providers/http_adapter.py`](core/providers/http_adapter.py) y en la página **Ajustes** ([`web/src/components/settings/`](web/src/components/settings/)) un selector claro y sencillo para usar cualquier modelo por **Plan** o por **API Key** (guardada cifrada con Windows DPAPI en `data/local/provider_keys.bin`) de todas las grandes compañías: **Google, Anthropic, OpenAI, xAI (Grok), DeepSeek, Mistral AI y OpenRouter**.

---

## 2. Cómo Acceder a Todo el Contexto en Segundos (Orden de Lectura)

Cuando inicies una nueva sesión, consulta directamente estos ficheros según la tarea:

1. **Estado actual, navegación quirúrgica y qué falta por hacer**:
   - [`docs/estado_implementacion.md`](docs/estado_implementacion.md) — Qué está implementado, qué se corrigió en la última sesión y resultados de la suite de tests.
   - [`docs/mapa_codigo.md`](docs/mapa_codigo.md) — Mapa de navegación quirúrgica (a qué fichero acudir directamente sin búsquedas exploratorias).
   - [`docs/hoja_de_ruta.md`](docs/hoja_de_ruta.md) — Tareas completadas y próximos pasos priorizados.
   - [`docs/mejoras_futuras.md`](docs/mejoras_futuras.md) — Mejoras futuras priorizadas (precisión jurídica, proceso, interfaz, operación).
2. **Traducción de conceptos legales para informáticos y estrategia**:
   - [`docs/guia_juridica_para_informaticos.md`](docs/guia_juridica_para_informaticos.md) — Explicación para desarrolladores de caducidad vs. prescripción, requisito MASC (LO 1/2025), postulación (umbral 2.000 €), convenios colectivos y restricción anti-scraping de CENDOJ (art. 507 LOPJ).
   - [`docs/viabilidad_y_estrategia.md`](docs/viabilidad_y_estrategia.md) — Evaluación técnica, económica y hoja de ruta si algún día se comercializa.
3. **Configuración de Modelos, Proveedores y Router**:
   - [`docs/proveedores_y_modelos.md`](docs/proveedores_y_modelos.md)
   - [`config/providers.toml`](config/providers.toml), [`config/models.toml`](config/models.toml), [`config/profiles.toml`](config/profiles.toml)
   - [`core/router.py`](core/router.py), [`core/providers/registry.py`](core/providers/registry.py), [`core/providers/cli_adapter.py`](core/providers/cli_adapter.py), [`core/providers/http_adapter.py`](core/providers/http_adapter.py)
4. **Arquitectura del Pipeline de 4 Fases y Reglas Deterministas**:
   - [`docs/arquitectura.md`](docs/arquitectura.md) y especificación completa en [`docs/IURIS_IA_Dossier_Planificacion_v3.md`](docs/IURIS_IA_Dossier_Planificacion_v3.md) *(Nota: los borradores antiguos v2.1 están archivados en `docs/historico_v2/` y no deben usarse como referencia).*
   - [`core/orchestrator.py`](core/orchestrator.py) — Orquestador de las 4 fases:
     - **Fase 1 (`_triaje`)**: Clasificación de submateria (`config/catalogo_materias.yaml`), detección de ambigüedad y hasta 1 ronda de preguntas aclaratorias.
     - **Fase 2 (`_ingesta`)**: Descarga determinista del BOE con versión vigente a la fecha de los hechos (`connectors/boe_client.py`, `core/temporal_sync.py`), búsqueda híbrida BM25 + LanceDB en jurisprudencia (`connectors/retriever.py`) y búsqueda FTS5 en convenios colectivos vigentes (`connectors/convenios_db.py`).
     - **Fase 3 (`_juicio`)**: Debate paralelo `DEFENSA` vs. `CONTRAPARTE` y resolución estructurada del `MAGISTRADO`.
     - **Cortafuegos anti-invención** (`core/firewall.py`, ver [`docs/cortafuegos.md`](docs/cortafuegos.md)): el Magistrado devuelve afirmaciones tipadas (`norma`/`razonamiento`/`hecho`/`consejo`/`limite`); se verifican cita literal, escáner determinista de artículos/leyes/sentencias/cifras/fechas, NLI de **otra familia** y hechos no contados; lo no respaldado se elimina y queda en `auditoria`.
     - **Fase 4 (`_certificar`)**: Guardarraíles deterministas G1–G10 (`core/validators.py`, coincidencia literal `rapidfuzz >= 92 %`, prohibición de porcentajes de éxito), verificación NLI (`core/nli.py`), motor determinista de plazos (`core/calendar_engine.py`, `config/plazos.yaml`) y reglas de abogado/procurador + aviso MASC LO 1/2025 (`core/postulacion_rules.py`, `config/postulacion.yaml`).
5. **Batería verificable de 30 casos reales**: [`docs/bateria_verificable.md`](docs/bateria_verificable.md) (`benchmark/ejecutar.py`, `evaluar.py`, `juez.py`, hojas de verdad con texto oficial y SHA-256).
6. **API Local y Frontend React/Vite**:
   - [`docs/api.md`](docs/api.md) y [`api/main.py`](api/main.py)
   - [`docs/operacion.md`](docs/operacion.md), [`web/src/App.tsx`](web/src/App.tsx), [`web/src/components/settings/SettingsPage.tsx`](web/src/components/settings/SettingsPage.tsx), [`web/src/lib/api.ts`](web/src/lib/api.ts)

---

## 3. Reglas Inquebrantables de Ingeniería y Seguridad en este Proyecto

0. **Nombre**: la app se llama **Desemppa** en todo lo visible. Los identificadores internos conservan `iuris` (`X-Iuris-Token`, variables `IURIS_*`, claves de `localStorage`, `data/local/iuris.log`, nombre de carpeta) para no romper datos ni scripts: no los renombres.
1. **Nada de memoria: todo dato se verifica contra la fuente en la misma sesión.** Referencias BOE, códigos REGCON, artículos de ley e ids de modelos se comprueban (BOE, `agy models`, documentación oficial) antes de escribirlos en configuración, datos o documentación. Lo que no se pueda verificar se marca como «sin verificar». Todo script nuevo lleva al menos un test de humo. (Motivo: el 23-10-2026 se introdujeron 9 referencias BOE inventadas; ver [`docs/informe_revision_2026-10-24.md`](docs/informe_revision_2026-10-24.md).)
2. **El LLM nunca calcula fechas ni inventa normas ni hechos**: las fechas del triaje solo valen si constan en el texto del usuario (`core/fechas_es.py`); el texto para el ciudadano se contrasta con sus hechos (`core/nli.py::hechos_no_constatados`); el Magistrado debe dar una `respuesta_directa` a la pregunta. Todo cálculo de plazos pasa por `CalendarEngine` (`core/calendar_engine.py`) y toda cita se verifica literalmente contra el texto del BOE/sentencia/convenio con `verify_quote` (`core/validators.py`). Nada del Magistrado llega al ciudadano sin pasar por el cortafuegos (`core/firewall.py::verificar_afirmaciones`); no lo debilites, y el verificador NLI debe ser de **otra familia** que el Magistrado, salvo en el modo **Eco**, donde por decisión expresa del usuario (25-10-2026) verifica Gemini 3.8 Flash para no gastar cuota de Claude (lo comprueba `tests/unit/test_settings.py`). Si un modelo falla, el router solo usa otro de la **misma familia** (`respaldo = "familia"` en `config/profiles.toml`) y avisa en el progreso y en «Modelos usados».
2b. **Hoja de ruta y escritos sin LLM**: `config/hojas_de_ruta.yaml` solo admite pasos con cita literal del artículo vigente (cualquier cifra del texto debe estar en sus citas); tras editarla ejecuta `uv run python scripts/verificar_hojas_de_ruta.py`. Los borradores de escritos (`web/src/lib/escritos.ts`) se componen sin LLM con el relato del usuario y afirmaciones «norma» verificadas. El texto del BOE excluye las notas editoriales (redacción anterior): no lo cambies.
3. **Seguridad de subprocesos CLI**: Jamás añadas flags de autoaprobación como `--dangerously-skip-permissions` en `config/providers.toml` (`config/settings.py` los rechaza expresamente). En Windows, `uvicorn` debe ejecutarse **sin `--reload`** para no romper el `ProactorEventLoop` necesario para subprocesos asíncronos.
4. **Privacidad, loopback y red local**: El servidor escucha en `0.0.0.0` pero `api/red_local.py` rechaza todo lo que no venga de este equipo salvo que el dueño active «Compartir en la red local» (solo IPs privadas, `Host` = IP del equipo, rol invitado con token propio, solo sus consultas, solo modos permitidos y límites de uso). Nunca expongas el token del dueño ni rutas de ajustes a invitados. El servidor valida el `Host` contra DNS rebinding, exige cabecera `X-Iuris-Token` en escrituras, seudonimiza PII antes de llamar a cualquier LLM (`core/pii_redactor.py`) y cifra datos sensibles y API keys con Windows DPAPI (`core/secure_store.py`).
5. **Checklist de verificación antes de cerrar cualquier cambio**:
   ```powershell
   uv run ruff check .
   uv run ruff format --check .
   uv run mypy
   uv run pytest -q
   cd web && npm run build && npx vitest run
   uv run pytest -m e2e -q
   uv run pytest -m live tests/contract/test_live_convenios_boe.py -q   # si tocas data/convenios_seed.yaml
   ```

---

## 4. Protocolo de Sesiones Quirúrgicas (1 sesión = 1 tarea acotada)

1. **Prohibición de exploración global:** La IA tiene prohibido hacer `grep_search` en toda la carpeta o leer múltiples ficheros sin necesidad. Debe consultar [`docs/mapa_codigo.md`](docs/mapa_codigo.md) e ir directo al archivo involucrado.
2. **Lectura obligatoria al iniciar sesión (y nada más):** Solo leer [`docs/estado_implementacion.md`](docs/estado_implementacion.md) para saber en qué punto se quedó la sesión anterior. No reanalizar el repositorio.
3. **Comandos estrictamente silenciosos:** Ejecutar siempre con flags que no inunden el contexto de tokens: `uv run pytest -q`, `uv run ruff check .`, `git status -s`.
4. **Cierre de sesión:** Al terminar la tarea, actualizar con 2 líneas [`docs/estado_implementacion.md`](docs/estado_implementacion.md) resumiendo el cambio exacto para que la siguiente sesión lo recoja al vuelo.
