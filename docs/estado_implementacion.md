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

## Desviaciones respecto al dossier (decididas con evidencia)

1. **Flash principal = `gemini-3.5-flash`, no 3.8.** Medición del 23-10-2026: 3.8-flash tardó 128 s con un prompt de
   ~3.000 tokens y daba 503; el free tier le asigna **20 peticiones/día** (mensaje 429 de la API). Una consulta Eco
   gasta 6–7 llamadas, así que con 3.8 solo caben ~3 consultas al día. 3.5-flash respondió en 4–6 s. El 3.8 queda
   como último recurso de la cadena (`config/models.toml`).
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
