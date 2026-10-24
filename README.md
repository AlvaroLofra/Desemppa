# Iuris-IA / Lex-Agent ES

Asistente legal **personal y local** para el derecho español. Analiza un caso enfrentando los argumentos del
usuario con los de la contraparte (`Defensa` → `Contraparte` → `Magistrado`), verifica cada cita literalmente contra
el BOE, los convenios colectivos o la jurisprudencia del corpus local y calcula los plazos con un motor de calendario determinista.

> Herramienta de información y apoyo a la autodefensa para uso personal. **No es asesoramiento profesional.** Las reglas de
> plazos y postulación están pendientes de validación por un profesional del derecho (ver [docs/guia_juridica_para_informaticos.md](docs/guia_juridica_para_informaticos.md)).

## Contexto rápido para IA (`CLAUDE.md` / `GEMINI.md`)

En la raíz del proyecto están [`CLAUDE.md`](CLAUDE.md) y [`GEMINI.md`](GEMINI.md) con el mapa completo del proyecto,
suscripciones activas, reglas arquitectónicas y estado actual para que cualquier sesión futura tenga todo el contexto
sin necesidad de re-explicarlo.

## Documentación

| Documento | Para qué |
|---|---|
| [docs/README.md](docs/README.md) | Índice general y mapa del repositorio |
| [docs/guia_juridica_para_informaticos.md](docs/guia_juridica_para_informaticos.md) | **Nuevo:** Explicación sencilla para informáticos de todos los conceptos y problemas legales (MASC LO 1/2025, caducidad vs. prescripción, postulación, CENDOJ) |
| [docs/viabilidad_y_estrategia.md](docs/viabilidad_y_estrategia.md) | **Nuevo:** Valoración técnica, económica (coste 0 € marginal) y opciones futuras de comercialización |
| [docs/operacion.md](docs/operacion.md) | Arrancar, usar y diagnosticar problemas |
| [docs/estado_implementacion.md](docs/estado_implementacion.md) | Qué está hecho, qué se ha corregido y estado de pruebas |
| [docs/hoja_de_ruta.md](docs/hoja_de_ruta.md) | Qué queda por hacer y en qué orden |
| [docs/proveedores_y_modelos.md](docs/proveedores_y_modelos.md) | Selector universal por Plan (Antigravity, Claude Pro, Codex) o por API (Google, Anthropic, OpenAI, xAI Grok, DeepSeek, Mistral, OpenRouter) |
| [docs/arquitectura.md](docs/arquitectura.md) | Cómo funciona por dentro el pipeline de 4 fases |
| [docs/guia_desarrollo.md](docs/guia_desarrollo.md) | Pautas, tests, convenciones y "cómo añadir X" |
| [docs/api.md](docs/api.md) | API local REST + SSE |
| [docs/datos_y_fuentes.md](docs/datos_y_fuentes.md) | BOE, CENDOJ, INE, convenios, festivos y base de datos |

## Arranque rápido (Windows)

**Doble clic en `INICIAR_IURIS_IA.bat`** (migra datos antiguos si aplica, compila la interfaz si falta, arranca el backend y abre el navegador **solo cuando el servidor responde `200 OK` en `/api/version`**, evitando errores `ERR_CONNECTION_REFUSED` o cachés antiguas del Service Worker).

Requisitos: Python 3.12 (vía `uv`), Node 18+ y al menos un proveedor de modelos.

### Suscripciones activas por defecto (0 € de coste extra por token)
1. **Antigravity (`agy` — Suscripción Google AI Pro ~20 €/mes)**:
   - Modelos configurados: **`Gemini 4 Argon`** (`gemini-4-argon-low|medium|high`), **`Gemini 3.8 Flash`** (`gemini-3.8-flash-low|medium|high`), **`Claude Opus 5.5`** (`claude-opus-5-5-low|medium|high`), **`Claude Sonnet 5.5`** (`claude-sonnet-5-5-low|medium|high`) y `gpt-oss-120b-medium`.
2. **Claude Code (`claude` — Suscripción Claude Pro ~20 €/mes)**:
   - Modelos configurados: `Claude Sonnet`, `Claude Opus 5.5` y `Claude Haiku` (`low|medium|high`).
3. **No necesitas `GEMINI_API_KEY`**: Todos los perfiles por defecto (`Eco`, `Equilibrado`, `Pro`, `Auditoría`) funcionan al 100 % sobre Antigravity y Claude Pro. De los modelos Flash solo se utiliza **Gemini 3.8 Flash**, con esfuerzo `low` o `medium` (`high` falla en Antigravity: ver [docs/proveedores_y_modelos.md](docs/proveedores_y_modelos.md)).

### Adaptable a cualquier modelo y API de cualquier compañía
Desde **Ajustes** (engranaje, arriba a la derecha) eliges qué modelo hace cada tarea en cada modo, por **plan de suscripción (CLI)** o por **clave de API** (**Google, Anthropic, OpenAI, xAI, DeepSeek, Mistral y OpenRouter**), guardas claves (cifradas con Windows DPAPI en `data/local/provider_keys.bin`) o añades modelos nuevos.

## Modos y modelos por defecto (`config/profiles.toml`)

| Modo | Triaje / Cribado / NLI | Defensa / Contraparte | Magistrado |
|---|---|---|---|
| **Eco** (100 % Antigravity) | Gemini 3.8 Flash (`low`) | Gemini 3.8 Flash (`medium`) | Gemini 3.8 Flash (`medium`) |
| **Equilibrado** (Por defecto) | Gemini 3.8 Flash (`low`) | Gemini 3.8 Flash (`medium`) | Claude Sonnet (`medium`, Claude Pro → fallback Antigravity) |
| **Pro** (Máxima potencia) | Gemini 3.8 Flash (`low` / `medium`) | Claude Sonnet (`medium`) | **Gemini 4 Argon (`high`, Antigravity)** |
| **Auditoría** | Gemini 3.8 Flash (`low` / `medium`) | Claude Sonnet (`medium`) | Claude Opus (`high`) + Auditor Gemini 4 Argon (`high`) |

## Desarrollo y Verificación

```powershell
uv sync
uv run pytest
uv run pytest -m e2e
uv run ruff check . && uv run mypy
```

## Privacidad

- Los datos personales detectados (DNI/NIE, teléfonos, emails, IBAN, matrículas y nombres tras fórmulas como "me llamo", "D.", "Sra.") se sustituyen por seudónimos antes de enviarse a un modelo.
- El texto original, el mapa de seudónimos, los adjuntos y las claves API se guardan cifrados con DPAPI de Windows en `data/local/`.
- El servidor solo escucha en `127.0.0.1` y exige un token local para cualquier operación de escritura.
