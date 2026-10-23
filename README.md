# Iuris-IA / Lex-Agent ES

Asistente legal **personal y local** para el derecho español. Analiza un caso enfrentando los argumentos del
usuario con los de la contraparte (Defensa → Contraparte → Magistrado), verifica cada cita literalmente contra
el BOE o la jurisprudencia del corpus local y calcula los plazos con un motor de calendario determinista.

> Herramienta de información y apoyo a la autodefensa. **No es asesoramiento profesional.** Las reglas de
> plazos y postulación están pendientes de validación por un profesional del derecho (ver `docs/`).

Especificación completa: [docs/IURIS_IA_Dossier_Planificacion_v3.md](docs/IURIS_IA_Dossier_Planificacion_v3.md) ·
Estado de la implementación: [docs/estado_implementacion.md](docs/estado_implementacion.md)

## Arranque rápido (Windows)

Requisitos: Python 3.12 (vía `uv`), Node 18+, y al menos un proveedor de modelos:
- **Gemini**: variable de entorno o `.env` con `GEMINI_API_KEY` (ver `.env.example`).
- **Claude Pro** (opcional, modos Equilibrado/Pro): el CLI `claude` con sesión iniciada (`claude` → `/login`).

```bash
uv sync
```

```bash
powershell -ExecutionPolicy Bypass -File scripts/start.ps1
```

Se abre `http://127.0.0.1:8000`. Desde Edge/Chrome puedes instalarla como aplicación (icono de instalar en la
barra de direcciones).

## Modos

| Modo | Triaje / cribado | Defensa / Contraparte | Magistrado | Llamadas a Claude |
|---|---|---|---|---|
| Eco | Gemini Flash | Gemini Flash | Gemini Flash (high) | 0 |
| Equilibrado | Gemini Flash | Gemini Flash | Claude Sonnet | 1 |
| Pro | Gemini Flash | Claude Sonnet | Claude Opus (high) | 3 |

Si un proveedor falla o agota la cuota, el router pasa al siguiente modelo de la cadena (`config/models.toml`) y
la interfaz lo avisa.

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
