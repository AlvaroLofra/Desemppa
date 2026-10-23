# Spike de entorno — Fase 0 (Windows)

> Documento histórico (Fase 0–Sprint 5). Desde entonces `core/claude_worker.py` y `core/stream_json.py` se sustituyeron por `core/providers/` (adaptador CLI genérico y parsers) y los datos pasaron a `data/local/`. Configuración vigente: [proveedores_y_modelos.md](proveedores_y_modelos.md).

Fecha: 2026-10-22 · Equipo: Windows 10 Pro 10.0.19045

## Versiones detectadas

| Herramienta | Versión | Nota |
|---|---|---|
| `python` (sistema, PATH) | 3.14.7 | **No se usa** para el proyecto (riesgo de falta de wheels de `lancedb`/`pyarrow`) |
| Python del venv (`.venv`) | **3.12.10** | Creado con `uv venv --python 3.12`; fijado en `.python-version` |
| SQLite del venv (`sqlite3.sqlite_version`) | 3.49.1 | FTS5 disponible ✅ (el Python 3.14 del sistema trae 3.50.4) |
| `uv` | 0.5.9 | `dependency-groups` funciona |
| `git` | 2.55.0.windows.5 | Repo inicializado (`git init`, sin commits) |
| Claude Code CLI | 2.1.291 | `C:\Users\Administrator\.local\bin\claude` |

Dependencias resueltas: 70 paquetes (p. ej. `lancedb 0.40.0`, `uvicorn 0.54.0`).

**Incidencia:** el primer `uv sync` falló con `os error 32` (la caché global de uv estaba bloqueada por otro proceso). Se instaló con una caché aparte:
`UV_CACHE_DIR=%TEMP%\uv-cache-iuris UV_LINK_MODE=copy uv sync`. Si vuelve a pasar, cierra los procesos que usen uv/Python o usa ese mismo comando.

## Flags del CLI de Claude relevantes para `claude_worker.py` (dossier §1.1.3)

Obtenidos con `claude --help` (v2.1.291):

| Necesidad del dossier | Flag disponible | Estado |
|---|---|---|
| Modo no interactivo | `-p, --print` | ✅ |
| Prompt por stdin (evita el límite de 32.767 caracteres de argv) | stdin + `--input-format text` (por defecto) o `stream-json` | ✅ (falta probarlo en vivo en el Sprint 1) |
| Salida en streaming | `--output-format stream-json` (también `json`, `text`) | ✅ |
| Streaming token a token | `--include-partial-messages` (solo con `-p` + `stream-json`) | ✅ |
| System prompt sin pasar por argv | `--system-prompt-file` / `--append-system-prompt-file` | ✅ (el texto de ayuda lo menciona; usarlo en lugar de `--system-prompt <texto>`) |
| Desactivar herramientas | `--tools ""` | ✅ |
| No cargar settings/CLAUDE.md del proyecto | `--setting-sources user` (o vacío) + cwd sandbox vacío | ✅ (falta confirmar en vivo qué valor aísla del todo) |
| Esfuerzo | `--effort low\|medium\|high\|xhigh\|max` | ✅ — el dossier preveía su posible ausencia: **sí existe** |
| Modelo | `--model haiku\|sonnet\|opus` o nombre completo | ✅ |
| Fallback de modelo nativo | `--fallback-model a,b` | ✅ (cubre la sobrecarga del modelo; el límite de uso se sigue gestionando con nuestro breaker) |
| No guardar sesiones en `~/.claude` | `--no-session-persistence` (solo `-p`) | ✅ — reduce el riesgo de colisión en `~/.claude` |
| Límite de turnos | `--max-turns` | ❌ **No aparece en `--help`**. Con `--tools ""` la respuesta es de un único turno; se verificará en el Sprint 1 |
| Tope de gasto | `--max-budget-usd` | ℹ️ Aplica a facturación por API; con la suscripción Pro no es relevante |

Invocación propuesta para el Sprint 1 (pendiente de prueba en vivo):
```
claude -p --model sonnet --effort medium --output-format stream-json --verbose \
       --include-partial-messages --tools "" --no-session-persistence \
       --system-prompt-file <tmp>\system.md     (prompt de usuario por stdin, cwd = sandbox vacío)
```

## Migración SQLite `0001_init.sql`

Aplicada con `sqlite3.executescript` del venv sobre una base de datos temporal:

- `journal_mode` = **wal** ✅
- 17 tablas normales, 3 tablas virtuales FTS5 (`boe_bloques_fts`, `cendoj_fts`, `convenios_fts`) y 4 índices `ix_*` ✅
- Sin errores de sintaxis FTS5 (`tokenize='unicode61 remove_diacritics 2'`) ✅
- Pendiente para el Sprint 2: los triggers de sincronización de FTS5 *external content* (en el dossier solo están descritos en prosa).

## Pendiente para el spike del Sprint 1
1. Llamada real a `claude -p` con un prompt de más de 40.000 caracteres por stdin y captura del evento `result` (`usage`, `total_cost_usd`).
2. Texto exacto del error de "usage limit" para el circuit breaker.
3. Modelos y límites reales del free tier de la Gemini API (`GEMINI_API_KEY` sin configurar todavía).

---

# Sprint 1 — Resultados de los spikes en vivo (2026-10-22)

## Gemini API (clave tomada de la variable de entorno `GEMINI_API_KEY` del sistema)
- **Modelos con la clave:** `gemini-3.8-flash`, `gemini-3.7-flash`, `gemini-3.6-flash`, `gemini-3.5-flash`, `gemini-4-argon`, `gemini-embedding-001`/`-2` y otros (salida de `scripts/spike_gemini_live.py`).
- `gemini-2.5-flash` devuelve **404** ("no longer available to new users") → retirado de `models.toml`.
- `gemini-3.8-flash` y `gemini-3.7-flash` devolvían **503 UNAVAILABLE** (saturación) de forma sostenida durante la prueba; `gemini-3.5-flash` respondió. Cadena configurada: `3.8-flash → 3.7-flash → 3.5-flash`.
- `gemini-4-argon` existe en la API pero devuelve **429 RESOURCE_EXHAUSTED** (sin cuota en el free tier) → el modo Auditoría degradará a `claude_opus`.
- `thinking_level` (LOW/MEDIUM/HIGH) aceptado por `gemini-3.5-flash`. Primer token ≈ 3,2 s en el spike y < 3 s en el test en vivo `test_gemini_first_token_under_3s` (objetivo < 3 s: **cumplido, pero al límite**).
- El SDK `google-genai` reintenta por su cuenta (tenacity); se desactiva (`HttpRetryOptions(attempts=1)`) para que el backoff y la degradación los controle `GeminiClient`/`ModelRouter`.

## Claude CLI
- `claude -p` lanzado desde una terminal normal responde **"Not logged in · Please run /login"**: el CLI no tiene sesión propia en este equipo (la app de escritorio no la comparte con el CLI). No hay `~/.claude/.credentials.json`.
- La cadena completa sí está verificada hasta ese punto: prompt de ~40.000 caracteres por stdin, `--system-prompt-file`, cwd sandbox, `FileLock`, parser `stream-json` y clasificación del error como `NotAuthenticated` (degradable → el router cae a Gemini).
- Formato real del error guardado en `tests/fixtures/claude_stream/error_not_logged_in.jsonl`: evento `assistant` con modelo `<synthetic>` + `result` con `is_error: true`, `subtype: "success"`, `terminal_reason: "api_error"`.
- Salida UTF-8 correcta (el `·` llega como `c2 b7`).

## Pendiente (requiere acción del usuario)
1. Iniciar sesión en el CLI una vez: ejecutar `claude` en una terminal y escribir `/login`.
2. Después: `uv run python scripts/spike_claude_live.py --record` (graba `ok_haiku.jsonl` real), `... --repeat 20` (estabilidad en Windows) y `uv run pytest -m live` (primer token de Sonnet < 10 s).
3. Revisar los patrones de `UsageLimitReached` en `core/stream_json.py` la primera vez que aparezca el mensaje real de límite de uso.

---

# Sprints 2–5 — Hallazgos en vivo (2026-10-23)

- **Cuota free tier `gemini-3.8-flash`: 20 peticiones/día por modelo** (429 `GenerateRequestsPerDayPerProjectPerModel-FreeTier`,
  `quotaValue: 20`). Latencia observada 80–210 s por llamada en el pipeline y 128 s en una prueba aislada.
- `gemini-3.5-flash`: 4,1 s (thinking LOW) y 6,2 s (HIGH) con ~3.100 tokens de entrada. Pasa a ser el Flash principal.
- `gemini-3.5-flash-lite` disponible y respondiendo; `gemini-4-argon` sin cuota (429).
- `GeminiClient` ahora lee el `retryDelay`/"retry in 7h42m" del 429 y salta el modelo agotado sin reintentar.
- BOE: los ids de bloque varían por norma (`a36`, `art1561`, `a2-8`, `anoveno`); hay versiones con la misma fecha de
  vigencia (correcciones): prevalece la última publicada.
- Primer dictamen real (caso sintético de fianza, modo Eco, 3.8-flash): CERTIFICADO, 2 citas literales del BOE verificadas,
  plazos y postulación correctos; ~12 min de extremo a extremo por la latencia de 3.8-flash.
