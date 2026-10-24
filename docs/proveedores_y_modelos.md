# Proveedores, modelos y APIs de IA (Multi-Compañía · por Plan o por API)

Actualizado: 24-10-2026.

Iuris-IA está diseñada para adaptarse a **cualquier modelo y cualquier proveedor** de las grandes compañías de IA,
distinguiendo claramente entre dos modalidades:
1. **Planes de Suscripción por CLI (`modalidad = "plan"`, coste marginal 0 €)**: usan tus suscripciones mensuales ya contratadas (**Google AI Pro vía Antigravity**, **Claude Pro vía Claude Code**, **ChatGPT Plus/Pro vía Codex**).
2. **APIs HTTP por Clave (`modalidad = "api"`, pago por uso)**: conectan directamente con las APIs oficiales de **Google Gemini, Anthropic, OpenAI, xAI (Grok), DeepSeek, Mistral AI y OpenRouter**.

---

## 1. Archivos de configuración

| Fichero | Qué define | ¿En git? |
|---|---|---|
| `config/providers.toml` | Todos los proveedores por Plan (CLI) y por API (`compania`, `modalidad`, `tipo`, `base_url`, `api_key_env`) | Sí |
| `config/models.toml` | Catálogo de modelos = proveedor + `model_id` (con soporte `{effort}`) + `efforts` + cadena `fallbacks` | Sí |
| `config/profiles.toml` | Qué modelo y nivel de esfuerzo (`low`, `medium`, `high`) hace cada tarea en cada modo | Sí |
| `config/user_profiles.toml` | Tus cambios de asignación guardados desde **Ajustes → Modos** | No |
| `config/user_models.toml` | Modelos personalizados y activación de proveedores desde **Ajustes** (se borra solo con «Restablecer modelos y proveedores», no con «Restablecer» de Modos) | No |
| `data/local/provider_keys.bin` | Claves API guardadas desde la UI, **cifradas en local con Windows DPAPI** | No |

---

## 2. Tus Suscripciones Activas por Defecto (Configuración Principal)

No necesitas tener `GEMINI_API_KEY` en tu ordenador: los perfiles por defecto (`Eco`, `Equilibrado`, `Pro`, `Auditoría`) operan al 100 % sobre tus dos suscripciones de ~20 €/mes:

### 2.1 Antigravity (`antigravity_cli` · `agy`) — Suscripción Google AI Pro
- **Modelos verificados y activos en tu cuenta (`agy models`)**:
  - `agy_gemini_argon` → `gemini-4-argon-{effort}` (`low`, `medium`, `high`)
  - `agy_gemini_flash` → `gemini-3.8-flash-{effort}` (`low`, `medium`, `high`)
  - `agy_claude_opus` → `claude-opus-5-5-{effort}` (`low`, `medium`, `high`)
  - `agy_claude_sonnet` → `claude-sonnet-5-5-{effort}` (`low`, `medium`, `high`)
  - `agy_gpt_oss` → `gpt-oss-120b-medium` (`medium`)
- **Regla importante sobre modelos Flash**: de la familia Flash se utiliza **únicamente Gemini 3.8 Flash** (`agy_gemini_flash`), con esfuerzo `low` o `medium`.
- **Medición real (24-10-2026, prompt de ~47.000 caracteres, el tamaño de un Magistrado)**:

  | Modelo · esfuerzo | Resultado |
  |---|---|
  | `gemini-3.8-flash-medium` | ✅ 51 s |
  | `gemini-3.8-flash-high` | ❌ 3 de 3 fallos: el modelo intenta ejecutar un comando, el modo no interactivo se lo deniega y devuelve una respuesta vacía |
  | `gemini-4-argon-high` | ✅ 46 s |
  | `gemini-4-argon-medium` | ✅ 22 s |

  Por eso el Magistrado de Eco usa Flash `medium`. Si un modelo devuelve una respuesta vacía, el router pasa al siguiente (`EmptyResponse`, degradable).

### 2.2 Claude Code (`claude_cli` · `claude`) — Suscripción Claude Pro
- **Modelos**: `claude_sonnet` (`sonnet`), `claude_opus` (`opus`), `claude_haiku` (`haiku`), todos con soporte `--effort low|medium|high`.
- **Iniciar sesión**: ejecuta `claude` en una terminal normal y escribe `/login`. Mientras no haya sesión iniciada, el router salta automáticamente a los modelos equivalentes en Antigravity (`agy_claude_sonnet`, `agy_claude_opus`, `agy_gemini_argon`).

### 2.3 Codex (`codex_cli` · `codex`) — Suscripción ChatGPT Plus / Pro (Opcional)
- Preparado en `config/providers.toml` (desactivado; sus flags están sin verificar porque Codex no está instalado) y activable desde **Ajustes → Cuentas y planes** si instalas `@openai/codex`.

---

## 3. APIs de Todas las Grandes Compañías (`core/providers/http_adapter.py`)

Si quieres usar una API por clave, ve a **Ajustes → Cuentas y planes**, pulsa **Clave** en la compañía y guárdala (o defínela en `.env`). Los ids de Google y Anthropic están verificados (oct-2026); el resto son ejemplos sin verificar: usa **Detectar** para ver los reales antes de asignarlos.

| Proveedor (`pid`) | Compañía | Variable de entorno alternativa | Modelos preconfigurados en `config/models.toml` |
|---|---|---|---|
| `openai_api` | **OpenAI** | `OPENAI_API_KEY` | `openai_gpt41` (`gpt-4.1`), `openai_o3` (`o3`) |
| `anthropic_api` | **Anthropic** | `ANTHROPIC_API_KEY` | `anthropic_sonnet_api` (`claude-sonnet-5-5`), `anthropic_opus_api` (`claude-opus-5-5`) |
| `gemini_api` | **Google** | `GEMINI_API_KEY` | `gemini_flash` (`gemini-3.8-flash`, 20 peticiones/día en el plan gratuito), `gemini_top` (`gemini-4-argon`) |
| `xai_api` | **xAI (Grok)** | `XAI_API_KEY` | `xai_grok3` (`grok-3`), `xai_grok3_mini` (`grok-3-mini`) |
| `deepseek_api` | **DeepSeek** | `DEEPSEEK_API_KEY` | `deepseek_v3` (`deepseek-chat`), `deepseek_r1` (`deepseek-reasoner`) |
| `mistral_api` | **Mistral AI** | `MISTRAL_API_KEY` | `mistral_large` (`mistral-large-latest`) |
| `openrouter_api` | **OpenRouter** | `OPENROUTER_API_KEY` | `openrouter_auto` (`openrouter/auto`) + cualquier modelo de OpenRouter |

### Cómo añadir cualquier modelo nuevo sin tocar código
En **Ajustes → Modelos personalizados** → **Añadir modelo**:
1. Elige el proveedor (cualquier Plan CLI o API).
2. Escribe un alias corto (ej. `grok_4` o `gpt_45`).
3. Escribe el `model_id` oficial de la compañía (ej. `grok-4-latest` o `gemini-4-argon-{effort}`).
4. Pulsa **Guardar modelo en catálogo**: queda inmediatamente disponible en el Selector Rápido y en la tabla de tareas.

---

## 4. Asignación por Defecto (`config/profiles.toml`)

| Modo | Triaje / Cribado | Defensa / Contraparte | Magistrado | Verificación NLI |
|---|---|---|---|---|
| **Eco** | `agy_gemini_flash` (`low`) | `agy_gemini_flash` (`medium`) | `agy_gemini_flash` (`medium`) | `agy_gemini_flash` (`low`) |
| **Equilibrado** (defecto) | `agy_gemini_flash` (`low`) | `agy_gemini_flash` (`medium`) | `claude_sonnet` (`medium`) | `agy_gemini_flash` (`low`) |
| **Pro** | `agy_gemini_flash` (`low`/`medium`) | `claude_sonnet` (`medium`) | **`agy_gemini_argon` (`high`)** | `agy_gemini_flash` (`low`) |
| **Auditoría** | `agy_gemini_flash` (`low`/`medium`) | `claude_sonnet` (`medium`) | `claude_opus` (`high`) + Auditor `agy_gemini_argon` (`high`) | `agy_gemini_flash` (`low`) |

## 5. Cadenas de alternativas (fallbacks)

Si un modelo falla, agota cuota o no tiene sesión, el router prueba el siguiente de su cadena (`config/models.toml`).
Los proveedores desactivados se saltan sin llamarlos.

| Modelo | Alternativas, en orden |
|---|---|
| `agy_gemini_flash` | `agy_claude_sonnet` → `agy_gpt_oss` → `claude_sonnet` → `gemini_flash` (API) |
| `claude_sonnet` | `agy_claude_sonnet` → `agy_gemini_flash` → `gemini_flash` (API) |
| `agy_gemini_argon` | `agy_claude_opus` → `claude_opus` → `claude_sonnet` → `agy_claude_sonnet` → `agy_gemini_flash` |

Primero se prueba otra familia dentro del mismo plan (Antigravity) y después otro proveedor, para no gastar un salto
en un proveedor desactivado.
