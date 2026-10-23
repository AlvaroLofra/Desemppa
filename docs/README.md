# Documentación de Iuris-IA / Lex-Agent ES

Asistente legal **personal y local** para el derecho español: analiza un caso enfrentando los argumentos del
usuario con los de la contraparte, verifica cada cita literalmente contra el BOE o la jurisprudencia del corpus y
calcula los plazos con un motor de calendario determinista.

> No es asesoramiento profesional. Las tablas jurídicas (plazos, postulación, materias) están **pendientes de
> validación por un profesional del derecho**.

## Por dónde empezar

| Si quieres… | Lee |
|---|---|
| Arrancar y usar la app | [operacion.md](operacion.md) |
| Saber qué está hecho, qué falta y en qué orden | [estado_implementacion.md](estado_implementacion.md) y [hoja_de_ruta.md](hoja_de_ruta.md) |
| Entender cómo funciona por dentro | [arquitectura.md](arquitectura.md) |
| Programar: entorno, convenciones, tests y "cómo añadir X" | [guia_desarrollo.md](guia_desarrollo.md) |
| Llamar a la API local (REST + SSE) | [api.md](api.md) |
| Configurar modelos y proveedores (Gemini, Claude, Antigravity, Codex…) | [proveedores_y_modelos.md](proveedores_y_modelos.md) |
| Fuentes de datos externas (BOE, CENDOJ, INE, convenios) y la base de datos | [datos_y_fuentes.md](datos_y_fuentes.md) |
| La especificación original (por qué cada decisión) | [IURIS_IA_Dossier_Planificacion_v3.md](IURIS_IA_Dossier_Planificacion_v3.md) |
| Mediciones reales de los CLIs y APIs | [spike_entorno_fase0.md](spike_entorno_fase0.md), [spike_antigravity.md](spike_antigravity.md) |
| Resultados comparativos de modelos | [../benchmark/reports/ab_modelos.md](../benchmark/reports/ab_modelos.md) |

## Mapa del repositorio

```
api/            Backend FastAPI: REST, SSE, token local, servido del frontend
config/         Configuración declarativa: proveedores, modelos, perfiles, catálogos jurídicos, plazos, postulación
core/           Lógica: orquestador de 4 fases, router de modelos, guardarraíles, calendario, seudonimización…
core/providers/ Adaptadores de proveedores (CLI genérico + parsers + registro)
core/prompts/   Prompts de cada rol (triaje, defensa, contraparte, magistrado)
connectors/     Fuentes externas: BOE, sentencias, convenios, PDF, embeddings, búsqueda híbrida
storage/        SQLite (WAL) + migraciones, LanceDB (vectores)
data/           Datos estáticos versionados (municipios, festivos, convenios) y data/local/ (datos de uso, NO en git)
benchmark/      Benchmark ciego: casos, purga, permutaciones, evaluador, informes
scripts/        Utilidades: arranque, migración de datos, carga de festivos, verificación del catálogo, spikes
tests/          unit · contract · golden (plazos/postulación) · e2e (navegador real) · fixtures
web/            Frontend React + Tailwind + PWA (Vite)
docs/           Esta documentación
```

## Convenciones de esta documentación
- Rutas relativas a la raíz del proyecto. Comandos para Windows con `uv` (Python) y `npm` (frontend).
- 🔎 = criterio jurídico cambiante o pendiente de validar. ⚠ = riesgo o trampa conocida.
- Cuando el código y la documentación discrepen, manda el código: abre una incidencia o corrige el documento.
