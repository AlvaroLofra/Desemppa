# Hoja de ruta: qué queda y cómo hacerlo

Estado de partida (23-10-2026, commit `686958d`): pipeline completo de 4 fases, proveedores configurables, interfaz
PWA, 229 tests + 4 E2E en navegador real. Detalle en [estado_implementacion.md](estado_implementacion.md).

Cada tarea indica **qué**, **cómo** (pasos y ficheros), **criterio de aceptación** y **quién** (🧑 tú, 🤖 desarrollo).
Orden recomendado: F0 → F1 → F2 → F3 (F4 y F5 pueden ir en paralelo cuando haya tiempo).

---

## F0 · Confirmar que la app funciona en tu equipo (inmediato)
| # | Tarea | Cómo | Aceptación | Quién |
|---|---|---|---|---|
| 0.1 | Arrancar la versión arreglada | Cerrar el servidor viejo; doble clic en `INICIAR_IURIS_IA.bat` | La ventana muestra el servidor en 127.0.0.1:8000 | 🧑 |
| 0.2 | Consulta real en Brave (modo Eco) | Caso de la fianza con municipio Madrid | Llega a "Fundamentos verificados" sin "token local inválido" | 🧑 |
| 0.3 | Si falla, recoger diagnóstico | Copiar el mensaje (trae código y ruta) y las últimas líneas de `data/local/logs/iuris.log` | Causa identificada | 🧑→🤖 |
| 0.4 | Comprobar la migración de datos | `uv run python scripts/migrar_datos.py --listar` desde una terminal normal | El historial antiguo aparece en la app | 🧑 |

## F1 · Proveedores y modelos
| # | Tarea | Cómo | Aceptación | Quién |
|---|---|---|---|---|
| 1.1 | Sesión en Claude Code | Terminal → `claude` → `/login` | Página Modelos: "Claude Code" en verde tras **Probar** | 🧑 |
| 1.2 | Fixture real y estabilidad de Claude | `uv run python scripts/spike_claude_live.py --alias claude_haiku --record --repeat 20` | 20/20 llamadas sin error; fixture guardado; mensajes reales de error de cuota anotados en `core/providers/parsers.py` | 🤖 |
| 1.3 | Pruebas en vivo completas | `uv run pytest -m live` | Los 4 proveedores pasan sus objetivos de latencia | 🤖 |
| 1.4 | Codex (cuando lo tengas) | Ver [proveedores_y_modelos.md §4](proveedores_y_modelos.md): spike, fixtures, verificar flags, `habilitado = true`, tests | Detectar + Probar en verde; tests del parser con salidas reales | 🧑 instalar · 🤖 integrar |
| 1.5 | Breaker por modelo además de por proveedor | `core/circuit_breaker.py` + router: clave `proveedor:modelo` para cuotas de un solo modelo | Agotar un modelo no bloquea los demás del mismo proveedor | 🤖 |
| 1.6 | Ajuste fino de timeouts y efforts | Medir con el ledger (`llm_calls_ledger`) latencias p50/p95 por rol | Timeouts ≈ p95 × 1,5; ningún rol por encima de 2 min en Eco | 🤖 |

## F2 · Datos (lo que más mejora la calidad)
| # | Tarea | Cómo | Aceptación | Quién |
|---|---|---|---|---|
| 2.1 | Aportar sentencias | CENDOJ → filtrar por TS / AP y materias del catálogo → descargar PDFs (empezar por 10 por submateria frecuente: fianza, despido, sanción, multas) | ≥ 100 sentencias en una carpeta | 🧑 |
| 2.2 | Página **Biblioteca** en la app | Nueva vista en `web/src/components/` usando `POST /api/jurisprudencia/importar` (ya existe): arrastrar varios PDFs, ver el corpus (`GET` nuevo `/api/jurisprudencia`), borrar | Importar 20 PDFs de una vez; errores por fichero visibles | 🤖 |
| 2.3 | Importador por lotes | `scripts/importar_sentencias.py <carpeta>` con `CendojRepository.import_pdf`, informe de fallos | Carpeta de 100 PDFs importada; avisos de segmentación listados | 🤖 |
| 2.4 | Embeddings del corpus | Con `GEMINI_API_KEY`: los vectores se crean al importar; para reindexar, script que recorra `cendoj_sentencias` | Búsqueda híbrida con `fuentes == {bm25, vector}` | 🤖 |
| 2.5 | Convenios | 🧑 confirmar la lista de `data/convenios_seed.yaml` (prioriza tu sector) y conseguir PDFs y códigos REGCON. 🤖 `scripts/importar_convenio.py <pdf> --codigo --vigencia --boletin` usando `ConveniosRepository.add_version` + extracción asistida de tablas salariales con verificación literal (`add_tabla_salarial`) | Convenio visible en `/api/convenios`; cláusulas citables en el dossier; filas salariales verificadas ≥ 95 % | 🧑+🤖 |
| 2.6 | Integrar convenios en la ingesta | `Orchestrator._ingesta`: si la submateria es laboral y hay convenio aplicable, añadir `ClausulaConvenio` (FTS sobre artículos) | Consulta de despido con convenio cita artículos del convenio | 🤖 |
| 2.7 | Festivos locales | 🧑 los 2 festivos de tu municipio y del de tu juzgado (BOP o web del ayuntamiento). 🤖 importador CSV + formulario en la app que escriba en `municipios_festivos` (`fuente='usuario'`) | Plazos sin aviso "festivos locales no cargados" en esos municipios | 🧑+🤖 |
| 2.8 | Festivos 2027 | Cuando se publique la resolución (octubre-noviembre de 2026): `scripts/build_calendar_data.py festivos 2027 BOE-A-…` | `anios_festivos` incluye 2027 | 🤖 |

## F3 · Calidad jurídica y benchmark
| # | Tarea | Cómo | Aceptación | Quién |
|---|---|---|---|---|
| 3.1 | **Revisión jurídica** | 🧑 sesión de ~4 h con un abogado o clínica jurídica revisando `config/plazos.yaml`, `config/postulacion.yaml`, `config/catalogo_materias.yaml`, `tests/golden/*.yaml` y los avisos 🔎. 🤖 aplicar correcciones y marcar `validado_juridicamente` | Lista de correcciones aplicada; golden actualizados | 🧑+🤖 |
| 3.2 | `scripts/crear_caso.py` | Desde una sentencia importada: hechos purgados (`benchmark/purge.py`), artículos citados como propuesta de `articulos_gold`, plantilla JSON en `benchmark/cases/` para completar el fallo esperado | Caso generado en < 1 min por sentencia | 🤖 |
| 3.3 | 25 casos reales | 15 TS + 10 AP, con fallo esperado confirmado por ti o por el abogado | 25 JSON en `benchmark/cases/` | 🧑+🤖 |
| 3.4 | Juez de doctrina | `benchmark/evaluator.py`: los 25 puntos de "doctrina" con un LLM de otra familia que el Magistrado (rúbrica JSON acotada); revisión manual de 5 | Puntuación completa sobre 100 | 🤖 |
| 3.5 | Benchmark completo y A/B | `uv run python -m benchmark.blind_judge --modo eco` (y equilibrado/pro), con permutaciones | Resultado correcto ≥ 80 %, 0 alucinaciones finales, diferencia original/permutado ≤ 10 puntos; informe en `benchmark/reports/` | 🤖 |
| 3.6 | Ajuste de prompts con datos | Iterar `core/prompts/*.md` comparando informes | Mejora sostenida sin regresiones | 🤖 |
| 3.7 | Conjunto de evaluación del NLI | 30–50 pares (premisa, hipótesis, etiqueta) revisados | Exactitud NLI ≥ 90 % y 0 "CONTRADICTS" tomados por "ENTAILS" | 🧑+🤖 |

## F4 · Producto e interfaz
| # | Tarea | Cómo | Aceptación | Quién |
|---|---|---|---|---|
| 4.1 | Exportar el dictamen | Botón "Descargar" (Markdown ya generado en `sesiones_consultas.dictamen_markdown`; PDF con la impresión del navegador o una plantilla) | Fichero con fuentes, plazos y aviso legal | 🤖 |
| 4.2 | Historial en móvil | `Sidebar` como cajón desplegable en pantallas estrechas | Historial accesible a 375 px | 🤖 |
| 4.3 | E2E de más flujos | `tests/e2e/`: aclaraciones, página Modelos (guardar y restablecer), adjuntos, visor de fuentes | Todos en verde con `pytest -m e2e` | 🤖 |
| 4.4 | Accesibilidad y PWA | Auditoría Lighthouse (accesibilidad ≥ 90, instalable) | Informe guardado y correcciones aplicadas | 🤖 |
| 4.5 | Borrar consultas | `DELETE /api/consultas/{id}` (con sus eventos y adjuntos) + botón | Consulta y datos cifrados eliminados | 🤖 |
| 4.6 | OCR opcional | Instalar Tesseract + `pytesseract` (el extractor ya lo usa si existe) | PDF escaneado → texto | 🧑 instalar · 🤖 probar |
| 4.7 | Mejor detección de nombres | Diccionario de nombres y apellidos frecuentes (INE) en `core/pii_redactor.py` | Nombres sin fórmula detectados; tests con falsos positivos controlados | 🤖 |
| 4.8 | Panel de consumo | Vista con el ledger: llamadas, tokens y latencia por proveedor y día | Ver de un vistazo cuánto se usa cada suscripción | 🤖 |

## F5 · Calidad del código y mantenimiento
| # | Tarea | Cómo | Aceptación |
|---|---|---|---|
| 5.1 | Integración continua local | Script `scripts/check_all.ps1` que ejecute todo el checklist de [guia_desarrollo.md §6](guia_desarrollo.md) | Un único comando en verde antes de cada commit |
| 5.2 | Remoto y copias | Crear un repositorio privado (GitHub) y hacer push periódico | Código respaldado fuera del equipo |
| 5.3 | Actualizaciones de dependencias | `uv lock --upgrade` y `npm update` trimestral, con la suite completa | Sin regresiones |

---

## Tareas que tienes que hacer tú (resumen)

1. **Probar la app arreglada** (F0): cierra el servidor viejo, lanza `INICIAR_IURIS_IA.bat` y haz una consulta Eco en
   Brave. Si falla, envía el mensaje (con código HTTP) y las últimas líneas de `data/local/logs/iuris.log`.
2. **Claude Code**: en una terminal, `claude` y `/login`; luego en la app, Modelos → Probar sobre un modelo de Claude.
3. **Privacidad**: en Antigravity y en Claude, desactiva el uso de tus conversaciones para entrenar modelos.
4. **Revisión jurídica** (~4 h): con un abogado o una clínica jurídica universitaria, sobre los ficheros de F3.1.
   Prepara las preguntas marcadas con 🔎.
5. **Sentencias**: descarga PDFs del CENDOJ (TS y Audiencias Provinciales) de las materias frecuentes; ~25 para el
   benchmark (con el fallo de cada una) y todas las que puedas para el corpus.
6. **Convenios**: confirma cuáles te interesan de `data/convenios_seed.yaml` y consigue sus PDFs o códigos REGCON.
7. **Festivos locales**: los 2 de tu municipio y los del municipio de tu juzgado (fecha y nombre).
8. **Clave de Gemini en `.env`**: copia `.env.example` a `.env` y pon `GEMINI_API_KEY` (hoy se lee de una variable de
   entorno del sistema). Opcional: valorar el plan de pago si la cuota gratuita se queda corta.
9. **Codex** (si contratas el plan): instala el CLI, inicia sesión y avisa para integrarlo.
10. **Decidir la asignación de modelos** tras el benchmark con casos reales (página Modelos).
11. **Copia de seguridad**: copia periódica de `data/local/` y, si quieres, crear un repositorio privado remoto.
