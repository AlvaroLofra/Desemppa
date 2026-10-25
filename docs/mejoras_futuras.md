# Mejoras futuras: estado (actualizado el 25-10-2026)

**HECHO** = implementado y con pruebas. **PENDIENTE** = no hecho todavía, con el motivo. La prioridad (A, B, C) mide el
impacto en «no inventar y acertar» frente al esfuerzo.

## 1. Precisión jurídica
| Estado | Mejora | Notas |
|---|---|---|
| HECHO | **Aviso de reforma** | Al abrir una consulta, `GET /api/consultas/{id}/vigencia` compara cada artículo del BOE citado con su redacción actual. Si ha cambiado después de la consulta, se avisa y se propone volver a consultar |
| HECHO | **Texto del BOE sin notas editoriales** | La «Redacción anterior», «Téngase en cuenta» y «Se modifica…» del BOE ya no forman parte del texto citable (`connectors/boe_models.py`, migración 0007). Antes, una cita copiada de la redacción derogada pasaba la verificación (p. ej. el LEC 250 mostraba «quince mil» y «seis mil euros») |
| PENDIENTE (A) | Golden tests por materia a partir de la batería | Necesita una ejecución completa de los 30 casos (`benchmark/ejecutar.py`). Los casos que pasen quedarán como regresión |
| PENDIENTE (A) | Corpus de jurisprudencia: importación guiada desde CENDOJ | La descarga tiene que hacerla una persona (art. 507 LOPJ). Ya existe `scripts/importar_sentencias.py`; falta un asistente por materia en la interfaz |
| PENDIENTE (B) | Conector CURIA (TJUE) | Conector nuevo con su verificación; no se ha empezado |
| PENDIENTE (B) | Convenios con modificaciones integradas y convenios provinciales (BOP) | Cada BOP publica de forma distinta, así que hay que diseñar el conector provincia a provincia |
| PENDIENTE (B) | Normas autonómicas (Aragón, Navarra, País Vasco, Galicia, Baleares) | Hay que verificar en el BOE el identificador de cada norma antes de añadirla (regla 1 de `CLAUDE.md`) |
| PENDIENTE (B) | Embeddings locales (ONNX) | Requiere añadir el modelo y un runtime nuevos; no se ha empezado |
| PENDIENTE (C) | Revisión por un abogado de `plazos.yaml`, `postulacion.yaml` y `hojas_de_ruta.yaml` | No la puede hacer el código. Las citas de la hoja de ruta ya se comprueban automáticamente contra el BOE |

## 2. Proceso del análisis
| Estado | Mejora | Notas |
|---|---|---|
| HECHO | **Preguntar todo lo necesario** | Cada campo crítico de la submateria solo cuenta como conocido si el triaje cita una frase literal de la consulta; si no, se pregunta. Todas las preguntas tienen «No lo sé» y explican por qué se hacen. No se repiten el municipio ni lo ya contado |
| HECHO | **Segunda ronda tras el debate** | El Magistrado indica en `hechos_determinantes` los hechos no contados que cambiarían una estimación. Se preguntan antes de dar el resultado (máximo 2 rondas); los que quedan sin aclarar se muestran en «Lo que podría cambiar el resultado» |
| HECHO | **Botón «Detener»** | `POST /api/consultas/{id}/cancelar`: cancela la tarea y mata el proceso del CLI |
| HECHO | **Escalado** | Si Flash falla la verificación dos veces, se repite una vez con Argon (misma familia) y se avisa |
| HECHO | **Banda según lo verificado** | Se rebaja un nivel si el cortafuegos elimina parte de la respuesta directa o al menos un tercio de las afirmaciones jurídicas |
| HECHO | **Varias cuestiones** | «Tu caso tiene N cuestiones», con la estimación de cada una |
| HECHO | **Cola visible para invitados** | `/api/sesion` devuelve `en_curso` y el aviso para invitados se actualiza cada 20 s |
| HECHO | **Respaldo de modelos** | Por defecto solo dentro de la misma familia, con aviso visible. Se reintenta una respuesta vacía y se añade la instrucción «sin herramientas» (ver `proveedores_y_modelos.md` §5-6) |
| PENDIENTE (C) | Caché de dossiers | El BOE y EUR-Lex ya se guardan 7 días en caché, así que una caché de dossier solo ahorraría la búsqueda local. Se deja para cuando se mida que hace falta |

## 3. Interfaz — HECHO
- Citas en línea, exportar el expediente (Markdown y PDF), calendario `.ics`, biblioteca, modo lectura, atajos, QR de la red local, comparar consultas, axe-core y Lighthouse en el E2E.
- 25-10-2026, segunda tanda:
  - aviso y desplazamiento al terminar el análisis (notificación si la pestaña está oculta);
  - PDF sin texto interno: era un fallo real del stream SSE, que perdía el `debate_done`;
  - selector de fechas propio estilo Google;
  - **hoja de ruta** («Qué hacer a continuación»);
  - **borradores de escritos**;
  - **modo profesional**;
  - **sello de verificación**.

## 4. Funcionamiento interno y operación
| Estado | Mejora | Notas |
|---|---|---|
| HECHO | **Panel de salud** | Ajustes → «Salud de los modelos»: llamadas, correctas, vacías, tiempo agotado y tiempo medio por modelo |
| HECHO | **Copias de seguridad cifradas** | `scripts/copia_seguridad.py`: DPAPI, conserva las 10 últimas y restaura sin sobrescribir |
| HECHO | **Registros con rotación** | 5 ficheros de 5 MB |
| PENDIENTE (B) | Icono en la bandeja o servicio de Windows | Requiere una dependencia nueva (p. ej. `pystray`) y probarlo en el escritorio |
| PENDIENTE (B) | Actualización con un clic | Toca git y el reinicio del servidor; conviene hacerlo con calma |
| PENDIENTE (C) | HTTPS en la red local | Exige gestionar un certificado autofirmado en cada dispositivo invitado |

## 5. Fiabilidad comprobable (propuestas propias)
| Estado | Mejora | Notas |
|---|---|---|
| HECHO | **Sello de verificación** | Por fuente citada: redacción vigente y SHA-256 del texto exacto verificado; también fecha, modelos y afirmaciones mostradas y eliminadas. Va en el dictamen, en el PDF y en el Markdown |
| HECHO | **Coherencia interna** | Si todas las cuestiones se estiman a favor de la otra parte, la solidez no puede ser favorable |
| HECHO | **Doble Magistrado en Pro** | Dos resoluciones independientes en paralelo; si discrepan en una cuestión, la solidez pasa a «disparidad de criterio» con aviso |
| HECHO | **Hoja de ruta verificada** | Las 121 citas de `config/hojas_de_ruta.yaml` se comprueban contra el BOE vigente (`scripts/verificar_hojas_de_ruta.py` y test `live`) |
| PENDIENTE (A) | Batería verificable periódica con informe comparativo | El ejecutor y el evaluador existen; falta lanzar la batería completa y programarla (gasta cuota real) |
