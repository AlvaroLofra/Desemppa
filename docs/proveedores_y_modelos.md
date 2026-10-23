# Proveedores, modelos y APIs de IA

Todo es configuración. Tres ficheros, en orden de dependencia:

| Fichero | Qué define | ¿En git? |
|---|---|---|
| `config/providers.toml` | Cómo hablar con cada proveedor (API o CLI) | Sí |
| `config/models.toml` | Alias de modelo = proveedor + id de modelo + límites + alternativas | Sí |
| `config/profiles.toml` | Qué alias hace cada tarea (rol) en cada modo | Sí |
| `config/user_profiles.toml` | Tus cambios desde la página **Modelos** (se superponen a `profiles.toml`) | No |

Se validan al arrancar (`config/settings.py`, `load_catalog`): un perfil con un alias inexistente, un *effort* no
soportado, un modelo con un proveedor desconocido o un flag `--dangerously-*` impiden arrancar con un error claro.

## 1. Proveedores disponibles

| Id | Tipo | Suscripción / coste | Estado (23-10-2026) |
|---|---|---|---|
| `antigravity_cli` | CLI `agy` | Google AI Pro (ya pagada) | ✅ Operativo. **Canal preferente para Gemini 3.8 Flash** y alternativa para Claude 4.6 |
| `gemini_api` | API AI Studio | Gratuito con `GEMINI_API_KEY` | ✅ Operativo, cuota diaria **muy baja** |
| `claude_cli` | CLI `claude` | Claude Pro (ya pagada) | ⚠ Instalado, **sin sesión iniciada** (cae a Antigravity) |
| `codex_cli` | CLI `codex` | ChatGPT Plus/Pro | ⏸ Preparado y desactivado; no instalado |

### 1.1 Antigravity (`agy`) — Google AI Pro
- Ejecutable: `%LOCALAPPDATA%\agy\bin\agy.exe` (en el PATH).
- Modelos (`agy models`): `gemini-3.8-flash-low|medium|high`, `claude-sonnet-4-6`, `claude-opus-4-6-thinking`,
  `gpt-oss-120b-medium`. El razonamiento de Gemini va en el nombre → en `models.toml`:
  `model_id = "gemini-3.8-flash-{effort}"`.
- Invocación que usa la app (no interactiva):
  ```
  agy --model <id> --input-format stream-json --output-format stream-json --disable-slash-commands
      --print-timeout <N>s [--json-schema <fichero>] -p=
  ```
  - Prompt por **stdin** como una línea NDJSON: `{"event":"user","message":{"role":"user","content":"…"}}`.
    ⚠ `-p=-` no lee stdin (lo toma como texto) y `-p` sin `=` se come el siguiente argumento.
  - No hay flag de system prompt: el adaptador lo antepone al contenido (`system_prompt = "inline"`).
  - Salida: eventos `init`, `step_update` (`text_delta` en `agent_response`; `tool` si intenta una herramienta),
    `result` (`status`, `response`, `usage`, `structured_output` con `--json-schema`, `denied_actions`).
  - ⚠ Con `--json-schema` el `response` trae el JSON duplicado: el parser usa `structured_output`.
  - ⚠ Si vence `--print-timeout` devuelve `status: SUCCESS` con respuesta vacía: el parser lo trata como timeout.
- Seguridad: en modo no interactivo las herramientas que requieren permiso (escribir ficheros, ejecutar comandos)
  se **deniegan solas**. **Nunca** añadas `--dangerously-skip-permissions` (la configuración lo rechaza).
- Latencias medidas: 4–13 s (low/medium, prompt corto); 48 s (medium, 32 KB); **high con prompts grandes > 4 min**
  → `efforts = ["low", "medium"]` en `agy_gemini_flash`.
- Iniciar sesión: abrir Antigravity o ejecutar `agy` en una terminal e identificarse con la cuenta de Google AI Pro.

### 1.2 Gemini API (AI Studio)
- Librería `google-genai` (`core/gemini_client.py`), clave en `GEMINI_API_KEY` (`.env` o variable de entorno).
- Modelos usados: `gemini-3.5-flash` (rápido, 4–6 s), `gemini-3.5-flash-lite`, `gemini-3.8-flash` (**20 peticiones/día**
  en el plan gratuito, 80–210 s), `gemini-4-argon` (sin cuota en el plan gratuito), `gemini-embedding-001` (768 dim).
  `gemini-2.5-flash` ya no está disponible para cuentas nuevas (404).
- Razonamiento: `ThinkingConfig(thinking_level=LOW|MEDIUM|HIGH)` (con alternativa a `thinking_budget` si el modelo lo
  rechaza). JSON: `response_mime_type="application/json"` y, si se pasa, `response_json_schema`.
- Límites: token bucket por alias (`rpm`) y contador diario (`rpd`, leído del ledger). Un 429 con "retry in 7h…" o
  `retryDelay` > 60 s marca el modelo como **agotado hasta esa hora** y no se reintenta; 429/500/503 transitorios se
  reintentan con backoff exponencial (máx. 3). Los reintentos internos del SDK están desactivados.
- ⚠ Privacidad: el plan gratuito puede usar lo que recibe para mejorar productos de Google. La app seudonimiza y no
  envía adjuntos sin consentimiento, pero conviene usarlo solo para tareas de volumen.

### 1.3 Claude Code (`claude -p`) — Claude Pro
- Invocación: `claude -p --model <haiku|sonnet|opus> --effort <low|medium|high> --output-format stream-json --verbose
  --include-partial-messages --tools "" --no-session-persistence --system-prompt-file <tmp>`; prompt por stdin.
- Salida `stream-json`: `system/init` (modelo), `stream_event` con `content_block_delta/text_delta`, `result`
  (`is_error`, `result`, `usage`, `total_cost_usd` = coste orientativo, no se cobra).
- Errores clasificados: "Not logged in" → `NotAuthenticated`; "usage limit"/"weekly limit" → `UsageLimitReached`
  (abre el breaker hasta el reinicio o 60 min); "overloaded/429/529" → `RateLimited`.
- Iniciar sesión: en una terminal, `claude` y luego `/login`. Comprobar: página **Modelos → Probar** sobre un modelo
  de Claude Code, o `uv run python scripts/spike_claude_live.py --alias claude_haiku`.

### 1.4 Codex (`codex exec`) — EXPERIMENTAL
- Bloque preparado en `providers.toml` con `habilitado = false`, parser `codex_jsonl` probado solo con eventos
  sintéticos (`item.completed` con `agent_message`, `turn.completed`, `error`/`turn.failed`).
- Pasos para activarlo: ver §4 ("Añadir o activar un proveedor") y **verificar los flags con `codex exec --help`**.

## 2. Catálogo de modelos (`config/models.toml`)

```toml
[models.agy_gemini_flash]
etiqueta = "Gemini 3.8 Flash (Antigravity)"
provider = "antigravity_cli"
model_id = "gemini-3.8-flash-{effort}"
efforts = ["low", "medium"]
timeout_s = 240
fallbacks = ["gemini_flash_38_api", "gemini_flash"]
```
Campos: `etiqueta`, `provider`, `model_id` (admite `{effort}`), `efforts` (por defecto low/medium/high), `timeout_s`,
`rpm`/`rpd` (solo API), `output_dimensionality` (embeddings), `fallbacks` (alias en orden; pueden ser de otro
proveedor).

Cadenas actuales:
- `claude_opus → agy_claude_opus → claude_sonnet → agy_claude_sonnet → agy_gemini_flash → gemini_flash_38_api →
  gemini_flash → gemini_flash_lite`
- `agy_gemini_flash → gemini_flash_38_api → gemini_flash → gemini_flash_lite`
- `gemini_flash → gemini_flash_lite`

## 3. Perfiles (qué modelo hace cada tarea)

Roles: `triaje`, `cribado`, `defensa`, `contraparte`, `magistrado`, `nli` (+ `auditor` en Auditoría).

| Modo | Triaje / cribado | Defensa / Contraparte | Magistrado | NLI |
|---|---|---|---|---|
| Eco (por defecto del repo) | Gemini 3.5 API | Gemini 3.8 Antigravity | Gemini 3.8 Antigravity | Gemini 3.5 API |
| Eco (**tu configuración actual**, `user_profiles.toml`) | Gemini 3.8 Antigravity | Gemini 3.8 Antigravity | Gemini 3.8 Antigravity | Gemini 3.8 Antigravity |
| Equilibrado | Gemini 3.5 API | Gemini 3.8 Antigravity | Claude Sonnet (Claude Code) | Gemini 3.5 API |
| Pro | Gemini 3.5 API | Claude Sonnet | Claude Opus (high) | Gemini 3.8 Antigravity |

Pautas para elegir:
1. **Volumen** (triaje, cribado, NLI): modelo rápido y con cuota abundante. Si la API gratuita se agota a menudo,
   usa Antigravity low (como en tu Eco actual).
2. **Razonamiento** (defensa, contraparte, magistrado): el mejor modelo disponible con effort medium; el Magistrado
   es el rol más exigente.
3. **NLI en otro canal** que el Magistrado cuando sea posible (verificación cruzada).
4. Cambia la asignación desde la app (**Modelos → matriz → Guardar**); "Restablecer" vuelve a `profiles.toml`.

## 4. Añadir o activar un proveedor (p. ej. Codex)

1. **Instalar e iniciar sesión** en su CLI desde una terminal normal. Comprobar que responde en modo no interactivo.
2. **Spike rápido** (30 min) para conocer su salida:
   ```bash
   echo "Responde solo: hola" | codex exec --json --model <modelo> --skip-git-repo-check --sandbox read-only - > salida.jsonl
   ```
   Mira qué eventos emite (texto, final, uso, errores), cómo se pasa el prompt por stdin y cómo se indica el modelo
   y el razonamiento. Guarda 2–3 salidas reales en `tests/fixtures/<proveedor>_stream/`.
3. **Bloque en `config/providers.toml`**: `tipo = "cli"`, `ejecutable`, `args` (marcadores `{model}`, `{effort}`,
   `{timeout_inner}`), `system_prompt` (`file` con `system_prompt_args` o `inline`), `stdin` (`text` o
   `agy_ndjson`), `parser`, opcionalmente `json_schema_args`, `descubrir` y `modelos_conocidos`, `login`,
   `habilitado = true`.
   - Regla de seguridad: el CLI debe ejecutarse **sin poder modificar el equipo** (sandbox de solo lectura, sin
     herramientas). Nada de flags de autoaprobación.
4. **Parser** (si el formato es nuevo) en `core/providers/parsers.py`: una clase con `feed(line)` (devuelve
   `StreamChunk` con el texto incremental o lanza un `ProviderError` tipado vía `classify_error`), `finish(stderr)`
   (rellena o valida `self.final: CliFinal`) y `avisos`. Regístrala en `PARSERS`.
5. **Modelos** en `config/models.toml` (`provider = "<id>"`) y, si quieres, en las cadenas `fallbacks` de otros.
6. **Tests**: parser con los fixtures reales (`tests/unit/test_parsers.py`), parametriza
   `tests/unit/test_cli_adapter.py` con el nuevo proveedor y añade el alias a `OBJETIVOS` en
   `tests/contract/test_live_providers.py`.
7. **En la app**: Modelos → **Detectar** → **Probar** → asignar en la matriz → Guardar.

Para un proveedor por **API HTTP** (p. ej. OpenAI con clave): el tipo `api_openai` está reservado; habría que crear un
adaptador como `GeminiApiAdapter` (método `stream(alias, spec, request)` que emita `StreamChunk` y un `LLMResult`
final) y registrarlo en `core/providers/registry.py`.

## 5. Interfaz común (para programar contra el router)
```python
async for item in router.stream(modo, rol, LLMRequest(system=..., prompt=..., json_mode=True),
                                fase="magistrado", consulta_id=cid, restartable=True):
    if isinstance(item, LLMResult): ...   # resultado final (texto completo, modelo efectivo, uso, degradado, avisos)
    else: ...                             # StreamChunk: texto incremental
```
Errores (`core/errors.py`): `ProviderError` (base) y los degradables `RateLimited`, `UsageLimitReached`,
`ProviderTimeout`, `ModelUnavailable`, `NotAuthenticated`.

## 6. Problemas frecuentes
| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| Proveedor en rojo "sin sesión iniciada" | CLI sin login | Iniciar sesión en el CLI (ver §1) y **Probar** |
| Avisos "se usó un modelo alternativo" | Cuota agotada o 503 del modelo principal | Normal; si es constante, cambia la asignación |
| Gemini API siempre "RateLimited" | Cuota diaria gratuita agotada | Esperar al reinicio indicado o pasar esas tareas a Antigravity |
| Antigravity tarda > 4 min | Effort `high` con prompt grande | Usar low/medium |
| "flags no permitidos" al arrancar | Alguien añadió `--dangerously-*` | Quitarlo de `providers.toml` |
