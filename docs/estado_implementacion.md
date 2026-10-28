# Estado de la implementación

Actualizado: 25-10-2026 · Especificación base: [IURIS_IA_Dossier_Planificacion_v3.md](IURIS_IA_Dossier_Planificacion_v3.md).
Qué queda y cómo: [hoja_de_ruta.md](hoja_de_ruta.md). Explicación legal para informáticos: [guia_juridica_para_informaticos.md](guia_juridica_para_informaticos.md).

## Verificación actual (25-10-2026: cortafuegos, batería verificable y mejoras de interfaz)
| Comprobación | Resultado |
|---|---|
| `uv run pytest` (unitarias, contrato, golden) | **322 en verde** |
| `uv run pytest -m e2e` (navegador real: consulta, tokens, autorreparación, citas en línea, exportar, lectura, atajos, biblioteca, comparar, axe-core y Lighthouse) | **10 en verde** · Lighthouse: accesibilidad 100, buenas prácticas 100 |
| `ruff check .`, `ruff format --check .`, `mypy` (50 ficheros) | **En verde** |
| `cd web && npm run build && npx vitest run` | **En verde** (16 tests) |
| Batería verificable real en Eco ([bateria_verificable.md](bateria_verificable.md)) | **23/30 con 7/7** (`benchmark/expedientes/20261025_1843_eco/informe.md`), congelados como regresión |

Novedades del 25-10-2026: [cortafuegos anti-invención](cortafuegos.md), batería de 30 casos con hojas de verdad
oficiales y las mejoras de interfaz de [mejoras_futuras.md §3](mejoras_futuras.md) (citas en línea, expediente en
Markdown/PDF, `.ics`, biblioteca, modo lectura, atajos, QR de la red local y comparar consultas).
- **Optimización de contexto y navegación quirúrgica (25-10-2026)**: Creados `.claudeignore` y [mapa_codigo.md](mapa_codigo.md), e incorporado el *Protocolo de Sesiones Quirúrgicas* en `CLAUDE.md` y `GEMINI.md` para evitar búsquedas globales y lecturas recursivas.

## Revisión del 24-10-2026 (Claude)
La sesión de Gemini 4 Argon (descrita abajo) contenía errores importantes: 9 de 10 referencias BOE de convenios
inventadas, scripts que no arrancaban, búsqueda de convenios sin acotar y afirmaciones sin verificar. Todo está
corregido y verificado; detalle en [informe_revision_2026-10-24.md](informe_revision_2026-10-24.md) §6. La interfaz se
ha rediseñado según [propuesta_rediseno.md](propuesta_rediseno.md).

## Qué hizo la sesión de Argon del 23-10-2026 (texto original, con correcciones marcadas)

1. **Corrección definitiva del error de arranque y consola (`ERR_CONNECTION_REFUSED` + `index-fDqGlMOV.js` + `403 Forbidden`)**:
   - **Por qué ocurría**: `INICIAR_IURIS_IA.bat` y `scripts/start.ps1` abrían el navegador (`start "" "http://127.0.0.1:8000"`) **antes** de que `uvicorn` terminara de arrancar (~2,5 s). Al encontrarse el puerto 8000 cerrado (`ERR_CONNECTION_REFUSED`), el navegador caía al Service Worker antiguo que tenía cacheado el bundle obsoleto `index-fDqGlMOV.js` con un token caducado, provocando `403 Forbidden` al enviar consultas.
   - **Cómo se ha resuelto**:
     - `INICIAR_IURIS_IA.bat` y `scripts/start.ps1` ahora lanzan una sonda en segundo plano que espera a que `http://127.0.0.1:8000/api/version` devuelva `HTTP 200` antes de abrir el navegador.
     - `api/main.py` devuelve la cabecera `Clear-Site-Data: "cache"` en respuestas `403`, forzando al navegador a purgar cualquier caché obsoleta automáticamente.
2. **Ajuste 100 % a tus suscripciones reales (Google AI Pro vía Antigravity + Claude Pro vía Claude Code, sin `GEMINI_API_KEY`)**:
   - **Por qué**: No usas `GEMINI_API_KEY` en tu ordenador; usas tus dos suscripciones mensuales de ~20 €/mes (`Antigravity` y `Claude Pro`), ya tienes acceso a **Gemini 4 Argon (`low/medium/high`)** y la latencia de **Gemini 3.8 Flash (`low/medium/high`)** está corregida.
   - **Cómo se ha resuelto**:
     - `config/models.toml` incluye `agy_gemini_argon` (`gemini-4-argon-{effort}` con `low`, `medium`, `high`), `agy_gemini_flash` (`gemini-3.8-flash-{effort}` con `low`, `medium`, `high`), `agy_claude_opus` (`claude-opus-5-5-{effort}`) y `agy_claude_sonnet` (`claude-sonnet-5-5-{effort}`).
     - `config/profiles.toml` y `config/user_profiles.toml` usan exclusivamente **Gemini 3.8 Flash** para todas las tareas Flash (*corregido: solo `low`/`medium`; `high` falla en Antigravity*), **Claude Sonnet** para el Magistrado en modo Equilibrado y **Gemini 4 Argon (`high`)** para el Magistrado en modo Pro, sin depender en absoluto de `GEMINI_API_KEY`.
3. **Adaptador y Selector Universal Multi-Compañía (por Plan de Suscripción o por API Key)**:
   - **Por qué**: Querías que la aplicación fuera fácilmente adaptable a cualquier modelo y cualquier API o plan de todas las grandes compañías de IA.
   - **Cómo se ha resuelto**:
     - Nuevo módulo `core/providers/http_adapter.py` con `OpenAICompatibleAdapter` (soporta **OpenAI, xAI Grok, DeepSeek, Mistral AI y OpenRouter**), `AnthropicApiAdapter` (**Anthropic API**) y `ApiKeyStore` (guarda las claves API cifradas con Windows DPAPI en `data/local/provider_keys.bin`).
     - Nuevos endpoints `POST /api/proveedores/{pid}/configurar` y `POST /api/modelos` en `api/main.py`.
     - *(Sustituido por Ajustes en el rediseño)* Renovación de `web/src/components/ModelsPage.tsx` con un **Selector Rápido Universal** (filtrable por *Mis Planes / Suscripciones* vs. *APIs por Clave* y por compañía), asignación en 1 clic a cualquier modo, configuración directa de API Keys desde la interfaz y formulario para añadir cualquier modelo nuevo.
4. **Actualización Jurídica LO 1/2025 (Requisito MASC) e Integración de Convenios Colectivos**:
   - **Por qué**: Desde abril de 2025 la Ley Orgánica 1/2025 exige acreditar un intento previo de negociación extrajudicial (MASC, ej. burofax) antes de presentar demandas civiles, y el repositorio de convenios aún no estaba conectado a la fase de ingesta del orquestador.
   - **Cómo se ha resuelto**:
     - Actualizado `config/postulacion.yaml` con avisos sobre el requisito MASC (*reescritos el 24-10 contra los arts. 2, 5 y 10 de la LO 1/2025*).
     - Conectado `ConveniosRepository.buscar_en_vigentes` dentro de `Orchestrator._ingesta` (`core/orchestrator.py`) y `GET /api/fuentes` (`api/main.py`) para asuntos de jurisdicción social.
     - ~~Actualizado `data/convenios_seed.yaml` con los códigos REGCON y referencias BOE reales~~ *Eran inventadas en 9 de 10 casos y los scripts no arrancaban; corregido el 24-10.*
5. **Limpieza documental y archivos de contexto (`CLAUDE.md` y `GEMINI.md`)**:
   - Archivados los 4 ficheros obsoletos de la versión 2.1 en `docs/historico_v2/`.
   - Creados `docs/guia_juridica_para_informaticos.md`, `docs/viabilidad_y_estrategia.md`, `CLAUDE.md` y `GEMINI.md`.

## Qué hay implementado, por bloque

| Bloque | Estado | Dónde |
|---|---|---|
| Router multimodelo con fallbacks entre proveedores, circuit breaker y ledger | ✅ | `core/router.py`, `core/circuit_breaker.py`, `core/quota_ledger.py` |
| Proveedores por Plan CLI (Antigravity, Claude Pro, Codex) y por API HTTP (Google, Anthropic, OpenAI, xAI, DeepSeek, Mistral, OpenRouter) | ✅ | `config/providers.toml`, `core/providers/` |
| Ajustes: modos, cuentas y planes (estado real, probar, detectar, claves DPAPI), modelos personalizados, apariencia | ✅ | `web/src/components/settings/`, `api/main.py` |
| BOE con versión vigente a la fecha de los hechos | ✅ | `connectors/boe_*`, `core/temporal_sync.py` |
| Jurisprudencia: parser, importación web y por lotes (`importar_sentencias.py`), búsqueda híbrida | ✅ código · ⏳ corpus a poblar con tus PDFs | `connectors/cendoj_*`, `scripts/importar_sentencias.py` |
| Convenios colectivos: 10 estatales verificados contra el BOE e indexados; el triaje elige de una lista cerrada; búsqueda en la versión vigente | ✅ · ⏳ sin modificaciones posteriores | `connectors/convenios_db.py`, `connectors/convenios_boe.py`, `scripts/importar_convenios_boe.py` |
| Calendario judicial (36 golden) y postulación con aviso MASC LO 1/2025 (25 golden) | ✅ · 🔎 orientativo para uso personal | `core/calendar_engine.py`, `core/postulacion_rules.py`, `config/*.yaml` |
| Guardarraíles G1–G10 y NLI | ✅ | `core/validators.py`, `core/nli.py` |
| Orquestador de 4 fases con aclaraciones y reintentos | ✅ | `core/orchestrator.py`, `core/state.py` |
| API REST + SSE con replay, token local y limpieza automática de caché en 403 | ✅ | `api/main.py`, [api.md](api.md) |
| Interfaz PWA rediseñada (claro/oscuro, respuesta primero, citas numeradas con panel de fuente, proceso plegable) | ✅ | `web/` |
| Privacidad: seudonimización, DPAPI, consentimiento de adjuntos | ✅ | `core/pii_redactor.py`, `core/secure_store.py` |
| Benchmark ciego (purga, permutaciones, rúbrica) | ✅ arnés · ⏳ casos reales adicionales | `benchmark/` |

- **Corrección de límite de `preguntas_aclaracion` en triaje (25-10-2026)**: Priorizadas las preguntas en `Orchestrator._triaje` (`q_fecha`/`q_municipio` → `q_campo_*` → preguntas del modelo) con recorte estricto `[:5]`, y ampliado `max_length=6` como buffer defensivo en `TriageOutputSchema` (`core/schemas.py`).
- **Cobertura de regresión**: Añadido `test_preguntas_aclaracion_nunca_superan_el_limite` en `tests/unit/test_orchestrator.py`.
- **Vídeo promocional Remotion extendido (25-10-2026)**: Ampliado el vídeo de 10s a ~38s (1.136 frames, 8 escenas) con `<TransitionSeries>`, pista procedural de 39s y cobertura completa de triaje, BOE, debate con cortafuegos, motor de plazos, escritos y privacidad/red local QR en `Renders/desemppa_38s.mp4`.
- **Siete mejoras de uso (25-10-2026, tarde)**: preguntas coherentes (`normalizar_pregunta`: disyuntivas → opciones o texto, nunca sí/no; tipo desconocido → texto) y sin duplicados (`ya_preguntado`, también en la 2.ª ronda), con «Otra respuesta o matizar» en cada pregunta; QR arreglado (`segno.save` con `xmlns`); modos en un desplegable; logo → inicio; solidez con medidor, «Qué significa» y «Por qué» (`motivos_banda`, textos en lenguaje sencillo); sin selector de municipio al inicio; historial con ⋮ renombrar/archivar/eliminar (migración 0008, `PATCH`/`DELETE /api/consultas/{id}`); asistente de jurisprudencia en Biblioteca; lanzador de escritorio `launcher/desemppa.pyw` + `INSTALAR_DESEMPPA.bat`.
- **Batería**: `ejecutar.py --reanudar/--pausa` (2 rondas), `congelar.py` → `tests/golden/test_bateria.py`, `comparar_ejecuciones.py`, `scripts/programar_bateria.ps1` (sin registrar). Plan de lo pendiente: [plan_mejoras_futuras.md](plan_mejoras_futuras.md). Verificación: 383 pytest + 16 e2e + 28 vitest en verde.
- **Batería real completa en Eco (25-10-2026)**: 23/30 casos con 7/7, congelados en `tests/golden/bateria/` (`test_bateria.py`). Correcciones derivadas: el Magistrado escala a Argon si Flash no responde (`_escalado_magistrado`), la fecha escrita en la misma frase que el evento del plazo se usa con aviso (`core/fechas_es.py::fecha_del_evento`) y toda materia con plazo pregunta una fecha concreta. Pendientes: V03/V16/V23 por tiempo agotado de Antigravity también en Argon; V06 (no cita TRLGDCU 114); V10/V19 postulación (cuantía de pensión mensual y vuelos: revisar con abogado); V21 falso positivo del evaluador («prohibido» por subcadena).
- **Cobertura jurídica general y eliminación de falsos `FUERA_DE_ALCANCE` (28-10-2026)**: Ampliado `config/catalogo_materias.yaml` de 18 a 42 submaterias operativas (incluyendo civil/inmobiliario/arras, deudas/monitorio, seguros/tráfico, familia/divorcio, herencias, consumo/desistimiento, protección de datos/morosos, societario/concursal, modificación laboral/conciliación/excedencia/baja/acoso, Seguridad Social/SEPE, responsabilidad patrimonial, extranjería/función pública, penal informativo y las 4 comodín `CIV_GENERAL`, `SOC_GENERAL`, `ADM_GENERAL`, `PEN_GENERAL`), añadidas 6 leyes verificadas en `config/catalogo_normas.json` (total 44), 5 plazos en `config/plazos.yaml` y 268 citas verificadas contra el BOE en `config/hojas_de_ruta.yaml`.
- **Triaje con rescate determinista e ingesta de preceptos BOE sugeridos (`normas_sugeridas`)**: `_rescatar_submateria` y `_construir_normas_objetivo` en `core/orchestrator.py` evitan rechazos por claves fuera de catálogo, descargan artículos adicionales verificados del BOE y `connectors/boe_client.py` resuelve numerales compuestos hasta 199 (ej. «Artículo treinta y ocho» LCS).
- **Revisión de la sesión de Argon del 28-10 (Claude)**: 418 pytest, ruff, mypy y 268/268 citas en verde (el walkthrough decía 422). Pendiente corregir: `PEN_DELITO_LEVE_1A` (1 año) asignado a todas las submaterias penales aunque alcoholemia (art. 379 CP) y estafas > 400 € prescriben a los 5 años (art. 131.1 CP, verificado en el BOE); regresión en `_titulo_es_articulo` (títulos en palabras seguidos de texto o «bis» devuelven `None`); rescate léxico demasiado amplio («empresa», «banco», «seguro»).
- **Plan UI/UX**: [plan_ui_ux.md](plan_ui_ux.md) (4 fases: `DESIGN.md`, solidez accesible + teclado, cabecera veredicto/plazo, monitor con eventos reales). Propuesta 6 descartada: el compositor «dock» ya existe.
- **Visión del producto (28-10-2026)**: asesor legal general, todo verificado contra el BOE en tiempo real, el LLM solo elige entre listas cerradas → [vision.md](vision.md), `CLAUDE.md`/`GEMINI.md` §1 (1b) y §3 (2a). Plan de fases 1–3 en [hoja_de_ruta.md](hoja_de_ruta.md) («Cobertura general verificada»); siguiente: Fase 1 (fallos de Argon).
- **Fase 1 — fallos de Argon corregidos (28-10-2026)**: `_titulo_es_articulo` prueba el prefijo numeral más largo («noveno bis», «diez. Objeto», «ciento cuatro»); ninguna submateria `PEN_*` calcula plazo (paso `prescripcion_penal` con la tabla del art. 131.1 CP); el rescate léxico exige una pista inequívoca o dos comunes y solo mira el texto del usuario; los 23 plazos (+2 forales) llevan `fuentes` literales y `scripts/verificar_plazos.py` exige cita y duración en el BOE vigente (25/25). Verificación: 444 pytest, 284/284 citas, ruff/mypy en verde.
- **Interfaz 3a (28-10-2026)**: `DESIGN.md` (contrato visual, enlazado en `CLAUDE.md`/`GEMINI.md`); solidez con icono, texto y «n/5» (`web/src/lib/solidez.ts` + test); pestañas del debate con flechas, plegables con `aria-controls`, chips con ✓, visor de fuentes con foco de ida y vuelta y texto desplazable por teclado (fallo de axe corregido). 30 vitest y 19 e2e en verde (axe, Lighthouse, teclado, movimiento reducido). Vista previa sin cuota: `desemppa-demo-simulada` en `.claude/launch.json`. Siguiente: Fase 2a.
