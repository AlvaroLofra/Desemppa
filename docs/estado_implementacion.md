# Estado de la implementación

Actualizado: 23-10-2026 · commit base `686958d`. Especificación: [IURIS_IA_Dossier_Planificacion_v3.md](IURIS_IA_Dossier_Planificacion_v3.md).
Qué queda y cómo: [hoja_de_ruta.md](hoja_de_ruta.md).

## Verificación al cierre
| Comprobación | Resultado |
|---|---|
| `uv run pytest` (unitarias, contrato, golden) | 229 en verde |
| `uv run pytest -m e2e` (Chromium real + service worker) | 4 en verde |
| `uv run pytest -m live` (proveedores reales) | Gemini API y Antigravity (Gemini 3.8 Flash, Claude Sonnet 4.6) en verde; Claude Code omitido por falta de sesión |
| `ruff check`, `ruff format --check`, `mypy --strict` | En verde |
| `npm run build`, `vitest` (8) | En verde |
| Benchmark con 2 casos sintéticos (Eco, 3.8 Flash vía Antigravity) | 2/2 certificados, media 96,7 (no mide calidad jurídica: faltan casos reales) |

## Qué hay, por bloque

| Bloque | Estado | Dónde |
|---|---|---|
| Router multimodelo con fallbacks entre proveedores, circuit breaker y ledger | ✅ | `core/router.py`, `core/circuit_breaker.py`, `core/quota_ledger.py` |
| Proveedores configurables (Gemini API, Claude Code, Antigravity; Codex preparado) | ✅ (Claude sin sesión; Codex sin probar) | `config/providers.toml`, `core/providers/` |
| Página Modelos (estado, Detectar, Probar, matriz modo × tarea) | ✅ | `web/src/components/ModelsPage.tsx`, `/api/proveedores`, `/api/ajustes/perfiles` |
| BOE con versión vigente a la fecha de los hechos | ✅ | `connectors/boe_*`, `core/temporal_sync.py` |
| Jurisprudencia: parser, importación, búsqueda híbrida | ✅ código · ⏳ corpus vacío | `connectors/cendoj_*`, `connectors/retriever.py` |
| Convenios con tablas salariales verificadas | ✅ código · ⏳ sin datos ni importador | `connectors/convenios_db.py` |
| Calendario judicial (36 golden) y postulación (25 golden) | ✅ · 🔎 pendiente de validación jurídica | `core/calendar_engine.py`, `core/postulacion_rules.py`, `config/*.yaml` |
| Guardarraíles G1–G10 y NLI | ✅ | `core/validators.py`, `core/nli.py` |
| Orquestador de 4 fases con aclaraciones y reintentos | ✅ | `core/orchestrator.py`, `core/state.py` |
| API REST + SSE con replay y token local | ✅ | `api/main.py`, [api.md](api.md) |
| Interfaz PWA (debate, visor de fuentes, plazos, adjuntos, autorreparación) | ✅ | `web/` |
| Privacidad: seudonimización, DPAPI, consentimiento de adjuntos | ✅ | `core/pii_redactor.py`, `core/secure_store.py` |
| Benchmark ciego (purga, permutaciones, rúbrica) | ✅ arnés · ⏳ 25 casos reales y juez de doctrina | `benchmark/` |

## Datos cargados
- **Normas**: 40 identificadores BOE verificados; los 75 artículos del catálogo existen (0 fallos en
  `scripts/verificar_catalogo.py`).
- **Municipios**: 8.131 (INE 2026). **Festivos**: nacionales y autonómicos de 2026 (`BOE-A-2025-21667`); 2027 aún no
  publicado; **locales: ninguno**.
- **Jurisprudencia**: vacía. **Convenios**: 30 candidatos sin código ni texto.
- **Tu configuración**: `config/user_profiles.toml` pone el modo Eco entero en Gemini 3.8 Flash vía Antigravity.

## Decisiones tomadas con evidencia (desviaciones del dossier)
1. **Gemini 3.8 Flash vía Antigravity, no vía API**: la API gratuita da 20 peticiones/día y 80–210 s; Antigravity
   (Google AI Pro) responde en 4–13 s (low/medium). `high` con prompts grandes no termina en 4 min → no se usa.
2. **La API gratuita de 3.5 Flash también se agota** con pocas consultas: el cliente salta el modelo hasta la hora de
   reinicio que indica el 429 y el router pasa al siguiente.
3. **`gemini-4-argon` sin cuota** en el plan gratuito: Auditoría degrada a Opus.
4. **NLI "no literal"** solo rebaja "criterio consolidado" a "argumento sólido" (no a "disparidad de criterio").
5. **Citas que siguen fallando tras el reintento se descartan** con aviso; solo se bloquea si no queda ningún fundamento.
6. **Adjuntos**: se envían a los modelos solo con consentimiento explícito en cada subida.
7. **Ids de bloque del BOE** no uniformes: se resuelven con el índice oficial y el título del bloque.
8. **Sin scraping del CENDOJ**: el corpus se nutre de sentencias importadas por el usuario.
9. **Datos en `data/local/`** y no en `%LOCALAPPDATA%` (virtualizado por Windows para apps empaquetadas).

## Incidencias resueltas relevantes
- **23-10 · La app no funcionaba desde el navegador**: 500 "no running event loop" (endpoint síncrono que lanzaba
  una tarea) y 403 "token local inválido" (token en HTML cacheado por el service worker). Arreglados, con test de
  regresión y E2E en navegador real. Los tests anteriores (y el script `test_live_fianza_beta.py`, retirado) no pasaban
  por HTTP, token, service worker ni SSE.
- **23-10 · `--dangerously-skip-permissions`** añadido por otro asistente a Antigravity: retirado y prohibido por la
  validación de configuración.
- **23-10 · 503 de Gemini a mitad de respuesta** dejaba la consulta en ERROR: los pasos JSON se repiten en otro modelo.

## Riesgos abiertos
| Riesgo | Mitigación actual | Siguiente paso |
|---|---|---|
| Reglas jurídicas sin validar | Todas las salidas lo indican; avisos 🔎 | Revisión jurídica (F3.1) |
| Corpus vacío → valoraciones sin jurisprudencia | Banda limitada a "argumento sólido" | Importar sentencias (F2) |
| Cuotas de suscripción no publicadas | Breaker + fallbacks + ledger | Panel de consumo (F4.8) |
| Formato de salida de los CLI cambia con sus actualizaciones | Parsers con tests sobre fixtures reales | Repetir spikes al actualizar (`pytest -m live`) |
| Detección de nombres incompleta | Aviso en la interfaz | Diccionario de nombres (F4.7) |
