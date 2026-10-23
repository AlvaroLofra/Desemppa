# Iuris-IA / Lex-Agent ES

Asistente legal **personal y local** para el derecho español. Analiza un caso enfrentando los argumentos del
usuario con los de la contraparte (Defensa → Contraparte → Magistrado), verifica cada cita literalmente contra
el BOE o la jurisprudencia del corpus local y calcula los plazos con un motor de calendario determinista.

> Herramienta de información y apoyo a la autodefensa. **No es asesoramiento profesional.** Las reglas de
> plazos y postulación están pendientes de validación por un profesional del derecho (ver `docs/`).

Especificación completa: [docs/IURIS_IA_Dossier_Planificacion_v3.md](docs/IURIS_IA_Dossier_Planificacion_v3.md) ·
Estado de la implementación: [docs/estado_implementacion.md](docs/estado_implementacion.md)

## Arranque rápido (Windows)

Requisitos: Python 3.12 (vía `uv`), Node 18+ y al menos un proveedor de modelos. Los proveedores se declaran en
`config/providers.toml` y se gestionan desde la página **Modelos** de la app:
- **Antigravity** (suscripción Google AI Pro): CLI `agy` con sesión iniciada. Da Gemini 3.8 Flash y Claude 4.6.
- **Gemini API**: `GEMINI_API_KEY` en `.env` (ver `.env.example`). Plan gratuito con cuota diaria muy baja.
- **Claude Code** (suscripción Claude Pro): CLI `claude` con sesión iniciada (`claude` → `/login`).
- **Codex** (suscripción ChatGPT, opcional): instalar el CLI, activarlo en `config/providers.toml` y pulsar «Detectar».

```bash
uv sync
```

```bash
powershell -ExecutionPolicy Bypass -File scripts/start.ps1
```

Se abre `http://127.0.0.1:8000`. Desde Edge/Chrome puedes instalarla como aplicación (icono de instalar en la
barra de direcciones).

## Modos y modelos

Asignación por defecto (`config/profiles.toml`); cámbiala desde la página **Modelos** (se guarda en
`config/user_profiles.toml`):

| Modo | Triaje / cribado / NLI | Defensa / Contraparte | Magistrado |
|---|---|---|---|
| Eco | Gemini 3.5 Flash (API) | Gemini 3.8 Flash (Antigravity) | Gemini 3.8 Flash (Antigravity) |
| Equilibrado | Gemini 3.5 Flash (API) | Gemini 3.8 Flash (Antigravity) | Claude Sonnet (Claude Code) |
| Pro | Gemini 3.5 Flash (API) / 3.8 (NLI) | Claude Sonnet | Claude Opus |

Si un modelo falla, se queda sin cuota o su CLI no tiene sesión, el router pasa a la siguiente alternativa
(`fallbacks` en `config/models.toml`, que puede cruzar proveedores: p. ej. Claude Code → Claude vía Antigravity →
Gemini 3.8) y la interfaz lo avisa.

### Añadir un proveedor nuevo
1. Instala su CLI e inicia sesión.
2. Añade (o activa) su bloque en `config/providers.toml`: ejecutable, plantilla de argumentos y parser de salida.
3. Añade sus modelos en `config/models.toml` (`provider = "<id>"`, `model_id = "..."`).
4. En la app: **Modelos → Detectar → Probar**, y asígnalo a las tareas que quieras.

## Desarrollo

```bash
uv run pytest
```

```bash
uv run ruff check . && uv run mypy
```

```bash
cd web && npm run dev
```

Utilidades:
- `uv run python scripts/verificar_catalogo.py` — comprueba contra el BOE que existen todos los artículos del catálogo.
- `uv run python scripts/build_calendar_data.py festivos 2027 BOE-A-AAAA-NNNNN` — carga el calendario oficial de un año.
- `uv run python -m benchmark.blind_judge --modo eco` — benchmark ciego (consume cuota).
- `uv run python scripts/spike_claude_live.py --record` — prueba real del CLI de Claude.

## Privacidad

- Los datos personales detectados (DNI/NIE, teléfonos, emails, IBAN, matrículas y nombres tras fórmulas como
  "me llamo", "D.", "Sra.") se sustituyen por seudónimos antes de enviarse a un modelo.
- El texto original, el mapa de seudónimos y los adjuntos se guardan cifrados con DPAPI de Windows.
- El contenido de los adjuntos solo se envía a los modelos si lo autorizas al subirlos.
- El servidor solo escucha en `127.0.0.1` y exige un token local por arranque para cualquier operación de escritura.
