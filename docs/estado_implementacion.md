# Estado de la implementación (2026-10-23)

Referencia: [IURIS_IA_Dossier_Planificacion_v3.md](IURIS_IA_Dossier_Planificacion_v3.md). Verificación al cierre:
`uv run pytest` (205 tests), `ruff check`, `ruff format --check` y `mypy --strict` en verde; `npm run build` y
`vitest` en verde.

## Por sprint

| Sprint | Estado | Qué hay |
|---|---|---|
| 1 · Router multimodelo | ✅ (falta prueba en vivo de Claude) | `core/router.py`, `gemini_client.py`, `claude_worker.py`, `circuit_breaker.py`, `quota_ledger.py` |
| 2 · Capa de datos | ✅ código · ⏳ datos | BOE con versiones por fecha (`connectors/boe_*`), parser de sentencias con voto particular aislado, PDF, LanceDB + FTS5 híbrido, convenios con tablas salariales verificadas, seudonimización, cifrado DPAPI |
| 3 · Calendario y guardarraíles | ✅ (pendiente validación jurídica) | `core/calendar_engine.py` (36 golden), `postulacion_rules.py` (25 golden), `validators.py` (G2–G6), `nli.py` (G5) |
| 4 · Pipeline y benchmark | ✅ arnés · ⏳ 25 casos reales | `core/orchestrator.py` (4 fases, aclaraciones, reintento del Magistrado), API SSE, `benchmark/` |
| 5 · Interfaz web + PWA | ✅ | React + Tailwind en `web/`, visor de fuentes con resaltado, línea temporal, drag & drop, PWA |

## Datos cargados

- **Normas**: 40 identificadores BOE verificados contra la API (`config/catalogo_normas.json`); los 75 artículos del
  catálogo de submaterias existen en el BOE (`scripts/verificar_catalogo.py`, 0 fallos).
- **Municipios**: 8.131 del diccionario INE 2026 (`data/municipios_ine.csv`).
- **Festivos**: nacionales y autonómicos de 2026 desde la resolución oficial BOE-A-2025-21667 (`data/festivos/2026.csv`).
  La de 2027 aún no estaba publicada el 23-10-2026. Locales: **no cargados** (el motor avisa y permite añadirlos).
- **Jurisprudencia**: corpus local vacío salvo lo que importe el usuario (`POST /api/jurisprudencia/importar`).
- **Convenios**: lista candidata de 30 en `data/convenios_seed.yaml`, **sin códigos REGCON ni textos**.

## Proveedores configurables (Fase A del plan de continuación)

- `config/providers.toml` declara cada proveedor (Gemini API, Claude Code, Antigravity y Codex desactivado);
  `core/providers/` tiene el adaptador CLI genérico (cola y FileLock por proveedor, prompt por stdin, cwd vacío),
  los parsers (`claude_stream_json`, `agy_stream_json`, `codex_jsonl` experimental) y el registro.
- `config/models.toml`: cada alias es proveedor + modelo, con cadenas de fallback entre proveedores.
- Página **Modelos** en la app: estado de cada proveedor, «Detectar» modelos, «Probar» con una llamada mínima y
  matriz modo × tarea guardada en `config/user_profiles.toml` (validada; si es inválida no se guarda).
- Verificado en vivo: Gemini API, Gemini 3.8 Flash y Claude Sonnet 4.6 vía Antigravity (`pytest -m live`).

## Desviaciones respecto al dossier (decididas con evidencia)

1. **Gemini 3.8 Flash se usa vía Antigravity, no vía API.** Por la API gratuita el 3.8 solo admite 20 peticiones/día
   y tardó 128 s; vía el CLI de Antigravity (suscripción Google AI Pro) responde en 4–13 s (low/medium). Por eso los
   roles de razonamiento usan `agy_gemini_flash` y la API queda para tareas de volumen (triaje, cribado, NLI). El
   nivel `high` vía Antigravity no se usa: con prompts grandes no termina en 4 min (docs/spike_antigravity.md).
   La API gratuita de 3.5 Flash también agota su cuota diaria con unas pocas consultas: cae a 3.5 Flash-Lite.
2. **`gemini-4-argon` sin cuota en el free tier** (429): el modo Auditoría degrada a Opus.
3. **NLI "no literal" no lleva a "disparidad de criterio".** El dossier decía "baja un nivel"; en el primer caso real eso
   mostró "Disparidad de criterio entre tribunales" sin ninguna sentencia de por medio. Ahora solo rebaja
   "criterio consolidado" a "argumento sólido" y deja el motivo en avisos.
4. **Reintento del Magistrado**: si tras el reintento siguen fallando citas, se descartan esas citas (con aviso) en vez de
   bloquear todo el dictamen; se bloquea solo si no queda ningún fundamento verificado.
5. **Adjuntos**: su contenido solo se envía a los modelos con consentimiento explícito por subida (§1.1.4 decía "no por
   defecto"; se implementa como casilla en la interfaz).
6. **Identificadores de bloque del BOE no uniformes**: la LAU usa `a36`, el Código Civil `art1561`, la Ley 15/2022 ids
   posicionales (`a2-8` = art. 26) y la LPH ordinales (`anoveno`). El repositorio los resuelve con el índice oficial.

## Pendiente que requiere tu intervención

1. **Iniciar sesión en el CLI de Claude** (`claude` → `/login`). Después: `uv run python scripts/spike_claude_live.py
   --record --repeat 20` y `uv run pytest -m live`. Sin esto los modos Equilibrado y Pro caen a Gemini.
2. **Revisión jurídica** (≈4 h) de `config/plazos.yaml`, `config/postulacion.yaml`, `config/catalogo_materias.yaml` y
   `tests/golden/*.yaml`. Todos los plazos se muestran como "pendiente de validación jurídica".
3. **Corpus de jurisprudencia**: aportar sentencias (PDF del CENDOJ) para importarlas; sin ellas la banda máxima es
   "argumento sólido, sin doctrina". Son también la materia prima de los 25 casos del benchmark.
4. **Convenios**: confirmar los 30 y sus códigos REGCON (o aportar los PDFs) para cargarlos.
5. **Festivos locales** de los municipios que te interesen (o del BOP de tu provincia).
6. **Clave de Gemini en `.env`** (ahora se toma de la variable de entorno del sistema) y, si quieres más cuota, valorar el
   tier de pago (rompe el "coste 0 €").

## Cómo verificar

```bash
uv run pytest
```

```bash
uv run python -m benchmark.blind_judge --modo eco --sin-permutar
```

```bash
powershell -ExecutionPolicy Bypass -File scripts/start.ps1
```

## Incidencia «token local inválido» (2026-10-23) — causas y arreglo

Desde el navegador ninguna consulta funcionaba. Los tests anteriores (incluido `scripts/test_live_fianza_beta.py`, ya
retirado) llamaban al orquestador directamente en Python y no pasaban por HTTP, token, service worker ni SSE.

1. **500 «no running event loop»**: `POST /api/consultas` y `/aclaraciones` eran funciones síncronas; FastAPI las
   ejecuta en un hilo sin bucle de eventos y `asyncio.create_task` fallaba. Ahora son `async`. Test de regresión:
   `test_crear_consulta_valida_arranca_el_analisis` (falla con el código antiguo).
2. **403 «token local inválido»**: el service worker precacheaba `index.html` con el token del arranque en que se
   instaló. Ahora el HTML no lleva token ni se cachea, el token se pide a `/api/token`, un 403 se reintenta con token
   nuevo (también en el SSE) y una copia antigua de la interfaz se detecta (`/api/version`) y se autorrepara.
3. **Dos bases de datos**: `%LOCALAPPDATA%` está virtualizado para los procesos lanzados desde la app de Claude. Los
   datos pasan a `data/local/` del proyecto; `INICIAR_IURIS_IA.bat` migra los antiguos la primera vez.
4. Se quitó `--dangerously-skip-permissions` de Antigravity y la configuración ahora rechaza ese tipo de flags.
5. Diagnóstico: `data/local/logs/iuris.log` registra cada 403 (motivo y ruta) y los errores de consulta; la interfaz
   muestra «HTTP código · método ruta».

Prueba de la ruta real: `uv run pytest -m e2e` (Chromium + service worker + servidor real con LLM simulado).
