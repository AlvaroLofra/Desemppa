# Guía de desarrollo

## 1. Entorno
- Windows 10/11, Python **3.12** (fijado en `.python-version`; 3.14 no tiene ruedas de `lancedb`/`pyarrow`), `uv`,
  Node 18+, Git.
- Instalación:
  ```bash
  uv sync
  ```
  ```bash
  cd web && npm install && npm run build
  ```
- ⚠ Si `uv sync` falla con "os error 32" (caché bloqueada por otro proceso): `UV_CACHE_DIR=%TEMP%\uv-cache-iuris`.
- Variables (`.env`, ver `.env.example`): `GEMINI_API_KEY`, `IURIS_DATA_DIR` (por defecto `data/local`),
  `IURIS_CLAUDE_EXE`, `IURIS_HOST`/`IURIS_PORT` (solo loopback), `IURIS_WEB_DIST` (otra copia del build; lo usan los E2E).
- Frontend en desarrollo con recarga: `cd web && npm run dev` (puerto 3000, proxy de `/api` al 8000). El backend
  se arranca aparte **sin `--reload`** (en Windows el recargador puede romper los subprocesos de los CLI).

## 2. Comandos de calidad (todos deben quedar en verde antes de un commit)
```bash
uv run pytest
```
```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy
```
```bash
cd web && npm run build && npx vitest run
```
```bash
uv run pytest -m e2e
```
`mypy --strict` cubre `core/` y `connectors/`. `ruff` usa línea de 120 y excluye `docs/`, `web/` y los `.md`
(⚠ sin esa exclusión, `ruff format` reescribe los bloques de código de la documentación).

## 3. Capas de pruebas

| Capa | Carpeta | Qué cubre | Cuándo se ejecuta |
|---|---|---|---|
| Unitarias | `tests/unit/` | Módulos aislados con dobles (router, adaptadores CLI con proceso simulado, parsers con fixtures reales, BOE con `httpx.MockTransport`, orquestador con LLM guionizado) | Siempre (`uv run pytest`) |
| Contrato | `tests/contract/` | API HTTP con `TestClient` (token, ajustes, crear consulta + SSE) | Siempre |
| Golden | `tests/golden/` | 36 plazos calculados a mano y 25 casos de postulación | Siempre |
| E2E | `tests/e2e/` | **Navegador real** (Chromium/Playwright) + servidor real + service worker, LLM y BOE simulados | `uv run pytest -m e2e` |
| Live | `tests/contract/test_live_providers.py` | Llamadas reales a cada proveedor (consume cuota) | `uv run pytest -m live` |
| Benchmark | `benchmark/` | Calidad jurídica de extremo a extremo con modelos reales | `uv run python -m benchmark.blind_judge --modo eco` |

⚠ **Lección aprendida (23-10-2026)**: un test que llama al orquestador directamente no prueba la app. La app no
funcionaba desde el navegador (500 por `asyncio.create_task` en un endpoint síncrono y 403 por un token cacheado en el
service worker) y ningún test lo detectó hasta que se añadieron los E2E. **Todo cambio que toque API, frontend, token,
SSE o service worker debe pasar `pytest -m e2e`.**

Fixtures reales en `tests/fixtures/`: salidas grabadas de `claude`, `agy`, bloques XML del BOE y una sentencia
sintética con formato CENDOJ.

## 4. Pautas de código
1. **El LLM no decide lo determinista**: fechas, plazos, normas aplicables, postulación y banda final los calcula el
   código. El LLM argumenta y cita; el código verifica.
2. **Toda cita debe ser verificable**: si añades un tipo de fuente, dale un `source_id` estable y asegúrate de que
   `verify_quote` pueda comprobarla contra su texto literal.
3. **Nada de proveedores cableados**: el pipeline solo habla con `ModelRouter`; los proveedores se configuran en
   `config/`.
4. **Endpoints que lanzan tareas asíncronas son `async def`** (un `def` se ejecuta en un hilo sin bucle de eventos).
5. **Errores tipados**: lanza las clases de `core/errors.py`; marca como degradable solo lo que otro modelo pueda
   resolver.
6. **Privacidad por defecto**: nada de texto del usuario a un modelo sin pasar por `pii_redactor`; nada de adjuntos
   sin consentimiento; nada de datos personales en logs.
7. **Seguridad de CLIs**: sin herramientas, cwd vacío, prompt por stdin, sin flags de autoaprobación.
8. Estilo: nombres y comentarios en español (dominio jurídico), docstring breve por módulo explicando el *porqué*,
   tipos completos, sin dependencias nuevas sin motivo.
9. Configuración antes que código: catálogos, plazos, reglas y modelos viven en `config/` (YAML/TOML/JSON).

## 5. Cómo añadir…

### Una submateria (tipo de caso)
1. `config/catalogo_materias.yaml`: clave, `descripcion` (en lenguaje del ciudadano), `jurisdiccion`,
   `procedimiento`, `normas` (alias de `catalogo_normas.json` + artículos), `campos_criticos`, `plazos`,
   `terminos_cendoj`, banderas (`doctrina_cambiante`, `competencia_local`…).
2. `uv run python scripts/verificar_catalogo.py` (los artículos deben existir en el BOE).
3. Un caso en `benchmark/cases/` y, si cambia plazos o postulación, casos golden.

### Una norma nueva
1. Buscar su id `BOE-A-AAAA-NNNNN` (API de búsqueda, ver [datos_y_fuentes.md](datos_y_fuentes.md)).
2. Añadirla a `config/catalogo_normas.json` con un alias y usarla en el catálogo de materias.
3. `scripts/verificar_catalogo.py`.

### Un plazo
1. `config/plazos.yaml`: `duracion`, `computo` (`habiles_procesal`, `habiles_social_caducidad`,
   `habiles_administrativo`, `naturales`, `meses_fecha_a_fecha`, `anios_fecha_a_fecha`), `naturaleza`, `agosto_habil`,
   `dia_gracia`, `prorroga_inhabil_final`, `dias_dudosos`, `admite_suspension`, `titular`, `foral`, `base_legal`.
2. **Al menos 3 casos golden calculados a mano** en `tests/golden/plazos.yaml` (incluye un fin de semana, un festivo
   y un cambio de mes o agosto).
3. Marcarlo para revisión jurídica.

### Una regla de postulación
`config/postulacion.yaml` (se evalúan en orden, gana la primera) + casos en `tests/golden/postulacion.yaml`.

### Un cambio de prompt
`core/prompts/*.md`. Ejecutar el benchmark antes y después y comparar (`benchmark/reports/`). Mantener intactas las
reglas de citación y de "sin porcentajes".

### Un cambio de esquema de base de datos
Nueva migración `storage/migrations/000N_descripcion.sql` (idempotente con `IF NOT EXISTS` cuando se pueda) + test.
Nunca editar una migración publicada.

### Un evento SSE nuevo
Emitir con `self._emit(run, "<tipo>", {...})` en el orquestador, añadirlo a `EVENTOS` y al reducer en
`web/src/lib/useConsulta.ts`, documentarlo en [api.md](api.md) y cubrirlo en un test de contrato o E2E.

### Un proveedor de modelos
Ver [proveedores_y_modelos.md §4](proveedores_y_modelos.md#4-añadir-o-activar-un-proveedor-p-ej-codex).

## 6. Definición de terminado (checklist)
- [ ] Tests nuevos para el cambio (unitario + contrato o E2E si toca la ruta del navegador).
- [ ] `pytest`, `pytest -m e2e`, `ruff`, `ruff format --check`, `mypy`, `npm run build`, `vitest` en verde.
- [ ] Si cambia el comportamiento con modelos reales: `pytest -m live` y/o benchmark, con el informe guardado.
- [ ] Documentación actualizada (`docs/` y, si aplica, `README.md`).
- [ ] Sin secretos, bases de datos ni `data/local/` en el commit; sin flags peligrosos.
- [ ] Mensaje de commit que explique el porqué.

## 7. Trampas conocidas (no repetirlas)
| Trampa | Síntoma | Solución aplicada |
|---|---|---|
| Endpoint `def` que crea tareas | 500 "no running event loop" | `async def` |
| Token en HTML cacheado por el service worker | 403 permanente | Token por `/api/token`, HTML sin caché, autorreparación |
| `%LOCALAPPDATA%` virtualizado (MSIX) | Dos bases de datos | `data/local/` del proyecto |
| Prompt por argv en Windows | Corte a 32.767 caracteres | Prompt por stdin |
| `agy -p=-` | Envía "-" como prompt | NDJSON por stdin con `--input-format stream-json` |
| `--json-schema` en agy | JSON duplicado en `response` | Usar `structured_output` |
| Ids de bloque del BOE | 404 en el Código Civil o la LPH | Resolver con el índice y el título |
| Cuota gratuita de Gemini | 429 con espera de horas | Saltar el modelo hasta el reinicio; usar Antigravity |
| Corte a mitad de respuesta | Consulta en ERROR | `restartable=True` en pasos JSON |
| `ruff format` sobre Markdown | Reescribe el dossier | `docs` y `*.md` excluidos |
