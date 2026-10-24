# Documentación de Desemppa (antes Iuris-IA)

Asistente legal **personal y local** para el derecho español: analiza un caso enfrentando los argumentos del
usuario con los de la contraparte, verifica cada cita literalmente contra el BOE, los convenios colectivos o la
jurisprudencia del corpus y calcula los plazos con un motor de calendario determinista.

> No es asesoramiento profesional. Las tablas jurídicas (plazos, postulación, materias) están **pendientes de
> validación por un profesional del derecho** (ver explicación sencilla en [guia_juridica_para_informaticos.md](guia_juridica_para_informaticos.md)).

## Por dónde empezar

| Si quieres… | Lee |
|---|---|
| Entender los problemas legales del proyecto sin saber nada de Derecho | [guia_juridica_para_informaticos.md](guia_juridica_para_informaticos.md) |
| Ver la valoración técnica, económica y de viabilidad comercial | [viabilidad_y_estrategia.md](viabilidad_y_estrategia.md) |
| Arrancar y usar la app sin errores de caché ni puerto | [operacion.md](operacion.md) |
| Saber qué está hecho, qué se ha corregido hoy y qué falta | [estado_implementacion.md](estado_implementacion.md) y [hoja_de_ruta.md](hoja_de_ruta.md) |
| Ver la última revisión independiente (problemas detectados y prioridades) | [informe_revision_2026-10-24.md](informe_revision_2026-10-24.md) |
| Ver el diseño de la interfaz (propuesta e implementación) | [propuesta_rediseno.md](propuesta_rediseno.md) |
| Ver la valoración jurídica del benchmark en modo Eco y sus correcciones | [benchmark_eco_2026-10-24.md](benchmark_eco_2026-10-24.md) |
| Compartir la app con otros equipos de tu wifi | [operacion.md §3](operacion.md) |
| Configurar modelos por Plan (Antigravity, Claude Pro, Codex) o por API (OpenAI, Anthropic, Google, xAI, DeepSeek, Mistral, OpenRouter) | [proveedores_y_modelos.md](proveedores_y_modelos.md) |
| Entender cómo funciona por dentro | [arquitectura.md](arquitectura.md) |
| Programar: entorno, convenciones, tests y "cómo añadir X" | [guia_desarrollo.md](guia_desarrollo.md) |
| Llamar a la API local (REST + SSE) | [api.md](api.md) |
| Fuentes de datos externas (BOE, CENDOJ, INE, convenios) y la base de datos | [datos_y_fuentes.md](datos_y_fuentes.md) |
| La especificación original v3.0 (por qué cada decisión) | [IURIS_IA_Dossier_Planificacion_v3.md](IURIS_IA_Dossier_Planificacion_v3.md) |
| Mediciones reales de los CLIs y APIs | [spike_entorno_fase0.md](spike_entorno_fase0.md), [spike_antigravity.md](spike_antigravity.md) |
| Documentos antiguos v2.1 archivados | `docs/historico_v2/` |

## Mapa del repositorio

```
CLAUDE.md       Contexto maestro para sesiones de Claude Code (idéntico a GEMINI.md)
GEMINI.md       Contexto maestro para sesiones de Gemini / Antigravity (idéntico a CLAUDE.md)
api/            Backend FastAPI: REST, SSE, token local, configuración de proveedores/modelos y servido del frontend
config/         Configuración declarativa: proveedores, modelos, perfiles, catálogos jurídicos, plazos, postulación
core/           Lógica: orquestador de 4 fases, router de modelos, guardarraíles, calendario, seudonimización…
core/providers/ Adaptadores de proveedores (CLI genérico + HTTP OpenAI/Anthropic/Gemini + almacén DPAPI de claves + registro)
core/prompts/   Prompts de cada rol (triaje, defensa, contraparte, magistrado)
connectors/     Fuentes externas: BOE, sentencias, convenios, PDF, embeddings, búsqueda híbrida
storage/        SQLite (WAL) + migraciones, LanceDB (vectores)
data/           Datos estáticos versionados (municipios, festivos, convenios_seed.yaml) y data/local/ (datos de uso, NO en git)
benchmark/      Benchmark ciego: casos, purga, permutaciones, evaluador, informes
scripts/        Utilidades: arranque, migración de datos, importador de convenios BOE, importador de sentencias PDF, spikes
tests/          unit · contract · golden (plazos/postulación) · e2e (navegador real) · fixtures
web/            Frontend React + Tailwind + PWA (Vite) con selector universal de modelos
docs/           Esta documentación (y docs/historico_v2/ con borradores antiguos v2.1)
```
