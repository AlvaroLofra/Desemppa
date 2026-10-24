# Hoja de ruta: qué está hecho y qué queda (Uso Personal — Opción A)

Actualizado: 24-10-2026. Detalle de lo completado hoy en [estado_implementacion.md](estado_implementacion.md).
Explicación sencilla de la parte legal en [guia_juridica_para_informaticos.md](guia_juridica_para_informaticos.md).

---

## ✅ Revisión y correcciones del 24-10-2026 (Claude)

Detalle en [informe_revision_2026-10-24.md](informe_revision_2026-10-24.md) (§6, «Estado tras las correcciones»).

| # | Tarea | Estado |
|---|---|---|
| 1 | Seed de convenios: 10 referencias BOE y códigos REGCON **verificados contra el BOE** (9 de las 10 anteriores eran inventadas) | ✅ |
| 2 | Importador de convenios que **verifica cada documento** antes de indexar + test en vivo del seed | ✅ |
| 3 | Scripts `importar_convenios_boe.py` e `importar_sentencias.py` reparados, con tests de humo; `scripts/` en `mypy` | ✅ |
| 4 | Convenios: el triaje elige de una lista cerrada; búsqueda solo en la versión vigente del convenio del caso | ✅ |
| 5 | Texto MASC redactado contra los arts. 2, 5 y 10 de la LO 1/2025 + golden tests | ✅ |
| 6 | Latencia medida: Flash `high` falla en Antigravity → Eco usa `medium`; respuestas vacías ahora degradan al siguiente modelo | ✅ |
| 7 | Cadenas de alternativas reordenadas; duplicado de Gemini API eliminado; ids de Anthropic actualizados | ✅ |
| 8 | «Días hábiles restantes» ya no muestra días naturales en plazos de meses o años | ✅ |
| 9 | «Restablecer» de Modos ya no borra modelos ni proveedores; TOML con escape correcto | ✅ |
| 10 | Rediseño visual (propuesta R0–R4) | ✅ primera versión, a ajustar |

## 🔜 Qué queda por hacer (para tu uso personal, a tu ritmo)

### Paso 1 · Verificar en vivo y activar sesión de Claude Code (5 min)
| # | Tarea | Cómo hacerlo | Quién |
|---|---|---|---|
| 1.1 | Arrancar la app actualizada | Cierra cualquier ventana antigua del servidor y haz doble clic en `INICIAR_DESEMPPA.bat` (o ejecuta `powershell -ExecutionPolicy Bypass -File scripts/start.ps1`). Si tu navegador tenía cacheado `index-fDqGlMOV.js`, pulsa una vez `Ctrl + F5`. | 🧑 Tú |
| 1.2 | Iniciar sesión en Claude Code (si quieres usar tu plan Claude Pro además de Antigravity) | Abre una terminal normal PowerShell, escribe `claude` y dentro escribe `/login`. Luego en la web ve a **Modelos → Probar** en `Claude Sonnet (Plan Claude Pro)`. *(Mientras no inicies sesión en `claude`, la app usa automáticamente `Claude Sonnet 5.5` y `Gemini 4 Argon` a través de tu plan de Antigravity).* | 🧑 Tú |

### Paso 2 · Poblar tus datos locales cuando los necesites (100 % opcional según tus consultas)
| # | Tarea | Cómo hacerlo | Quién |
|---|---|---|---|
| 2.1 | Descargar e indexar los 10 grandes convenios colectivos estatales del BOE | Ejecuta `uv run python scripts/importar_convenios_boe.py`. Verifica cada referencia contra el BOE e indexa Construcción, Metal, Hostelería, Contact center, Seguridad privada, Grandes almacenes, Dependencia, Limpieza, Química y Enseñanza concertada. Ojo: las modificaciones posteriores de cada convenio no se integran (el script las lista). | 🧑 Tú (1 comando) |
| 2.2 | Añadir sentencias del CENDOJ sobre un tema que te interese | Cuando tengas un problema real (ej. fianza de alquiler o despido), busca sentencias en [CENDOJ](https://www.poderjudicial.es/search/indexAN.jsp), guarda los PDFs en una carpeta y ejecuta `uv run python scripts/importar_sentencias.py ruta/a/carpeta` (o súbelos desde la API). | 🧑 Tú |
| 2.3 | Festivos de 2027 (cuando el BOE los publique en oct/nov 2026) | Ejecutar `uv run python scripts/build_calendar_data.py festivos 2027 BOE-A-2026-XXXXX`. | 🧑/🤖 |

### Paso 3 · Mejoras futuras de interfaz y comodidad (Fase 4 opcional)
| # | Tarea | Descripción | Quién |
|---|---|---|---|
| 3.1 | Exportar el dictamen a Markdown | Ya hay «Copiar» e «Imprimir» (guardar como PDF desde el navegador) al pie de la respuesta; falta la descarga en Markdown con todas las citas y plazos. | 🤖 Desarrollo |
| 3.2 | Borrar consultas individuales del historial | Añadir `DELETE /api/consultas/{id}` y un icono de papelera en la barra lateral (`Sidebar.tsx`). | 🤖 Desarrollo |
| 3.3 | Vista «Biblioteca» en la web (patrón Fuentes de NotebookLM) | Pestaña para arrastrar PDFs de sentencias o convenios provinciales directamente desde el navegador sin usar los scripts de consola. | 🤖 Desarrollo |
| 3.4 | Si en el futuro decides comercializarlo (Opción B) | Seguir el playbook de [viabilidad_y_estrategia.md §3](viabilidad_y_estrategia.md): cambiar en Ajustes a APIs por clave (BYOK) y hacer una revisión de 4 h de los 3 ficheros YAML con un abogado colegiado. | 🧑+🤖 |
| 3.5 | Integrar en los convenios sus modificaciones posteriores | Hoy se indexa el texto original publicado; las actas y revisiones salariales que lo modifican (el importador las lista) no se aplican. | 🤖 Desarrollo |
| 3.6 | Que el triaje pregunte el convenio si falta en un asunto laboral | Ahora se avisa de que no se ha identificado y no se citan cláusulas. | 🤖 Desarrollo |
| 3.7 | Ajustes finos del rediseño | Lo que vayas viendo al usarlo (colores, densidad, textos). | 🧑+🤖 |
