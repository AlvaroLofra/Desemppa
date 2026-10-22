# Spike de entorno — Fase 0 (Windows)

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
