# API local (REST + SSE)

Actualizado: 24-10-2026 · Base: `http://127.0.0.1:8000` · Implementación: `api/main.py`.
Documentación interactiva OpenAPI en `http://127.0.0.1:8000/docs` mientras el servidor está en marcha.

## Reglas comunes

| Aspecto | Regla |
|---|---|
| Host | Solo `127.0.0.1` o `localhost` (otro `Host` → **400**, protección frente a DNS rebinding) |
| Autenticación | Operaciones de escritura exigen cabecera `X-Iuris-Token: <token>`. El stream SSE lo exige como `?token=` |
| Obtener el token | `GET /api/token` (guardado en `data/local/local_token.txt`, estable entre reinicios) |
| Autolimpieza en 403 | Si una pestaña antigua envía un token caducado, el 403 incluye `Clear-Site-Data: "cache"` para purgar cachés obsoletas del navegador |

## Roles: dueño e invitado (red local)
| Origen de la petición | Rol | Condición |
|---|---|---|
| `127.0.0.1` / `::1` | dueño | `Host` = `127.0.0.1` o `localhost` |
| IP privada de la LAN | invitado | solo con la red activada (`PUT /api/red`) y `Host` = IP de este equipo |
| cualquier otra | — | 403 antes de llegar a la app |

El invitado envía `X-Desemppa-Invitado: <id aleatorio>` (y `?invitado=` en el stream SSE); recibe un token propio en
`/api/token`. Las rutas marcadas 👤 son solo del dueño. Un invitado solo ve, abre y sigue sus propias consultas
(404 para las demás); solo puede usar los modos permitidos (403), 1 consulta en curso y un tope diario (429).

### `GET /api/sesion`
`{"rol": "dueno" | "invitado", "modos_permitidos": [...], "en_curso": n}` (`en_curso`: análisis en marcha en este equipo).

### `GET /api/red` 👤 · `PUT /api/red` 👤🔒
Estado de la red local: `activo`, `escucha_red` (el servidor se arrancó en `0.0.0.0`), `ip`, `url`,
`modos_permitidos` (Eco siempre), `tope_diario`, `invitados_activos` (últimos 2 min), `consultas_hoy`.
`PUT` acepta `{"activo"?, "modos_permitidos"?, "tope_diario"? (1-200)}`. El estado vive en memoria: al reiniciar,
la red vuelve a estar desactivada.

### `GET /api/red/qr` 👤
Código QR (SVG, generado con `segno`) del enlace para invitados. `409` si la red no está activa.

## Endpoints de Estado, Proveedores y Modelos

### `GET /api/version`
`{"build": "<id>", "servidor": "<huella>"}` — build de `web/dist/version.json` y huella del código Python con el que arrancó el servidor (el lanzador sustituye un servidor antiguo).

### `GET /api/token`
`{"token": "<hex>"}` — token local de seguridad.

### `GET /api/estado` 👤
Resumen general de proveedores (incluyendo `compania`, `modalidad`: `"plan" | "api"`, `api_key_env`), modos, modelos y tamaño del corpus (`sentencias`, `convenios`, `municipios`, `anios_festivos`).

### `GET /api/proveedores` 👤
Estado detallado de todos los proveedores configurados (`antigravity_cli`, `claude_cli`, `codex_cli`, `gemini_api`, `anthropic_api`, `openai_api`, `xai_api`, `deepseek_api`, `mistral_api`, `openrouter_api`).

### `POST /api/proveedores/{pid}/configurar` 🔒
Activa/desactiva un proveedor o guarda su `api_key` cifrada con Windows DPAPI en `data/local/provider_keys.bin`:
```json
{"api_key": "sk-...", "habilitado": true}
```

### `POST /api/proveedores/{pid}/detectar` 🔒
Lista los modelos disponibles en el proveedor (`{"instalado": true, "modelos": [...]}`).

### `POST /api/modelos` 🔒 → 201
Añade un modelo personalizado al catálogo (`config/user_models.toml`) y recarga el router en caliente:
```json
{
  "alias": "grok_3_custom",
  "proveedor": "xai_api",
  "model_id": "grok-3",
  "etiqueta": "Grok 3 (xAI)",
  "efforts": ["low", "medium", "high"]
}
```

### `POST /api/modelos/{alias}/probar` 🔒
Realiza una llamada mínima real (`"Responde exactamente con la palabra: OK"`) y devuelve `{"ok": true, "latencia_ms": 1200, "respuesta": "OK", "error": null}`.

### `GET / PUT / DELETE /api/ajustes/perfiles` 🔒
Lee, guarda (`config/user_profiles.toml`) o restablece la asignación de modelos y niveles de esfuerzo (`low`, `medium`, `high`) por modo y rol. `DELETE` solo borra `user_profiles.toml`.

### `DELETE /api/ajustes/modelos` 🔒
Borra `config/user_models.toml` (modelos personalizados y activación de proveedores) y recarga el catálogo.

## Endpoints de Consultas, Fuentes, Calendario y Corpus

- `POST /api/consultas` 🔒 → 201: Crea y lanza el análisis asíncrono (`{"texto", "modo", "municipio_ine", "adjuntos"}`).
- `POST /api/consultas/{id}/aclaraciones` 🔒: Envía las respuestas a las preguntas aclaratorias de la Fase 1 y reanuda el pipeline.
- `GET /api/consultas` y `GET /api/consultas/{id}`: Lista el historial y recupera el detalle completo (con PII restaurado en local).
- `GET /api/consultar/stream/{id}?token=…&after=N`: Stream SSE con replay automático desde el evento `N`. Termina siempre con el evento `fin` (el navegador cierra al recibirlo).
- `POST /api/adjuntos` 🔒 → 201: Extrae texto de PDF/TXT en local y lo cifra con DPAPI (solo se envía al LLM si `permitir_envio=true`).
- `GET /api/biblioteca` 👤, `POST /api/biblioteca` 👤🔒 → 201, `GET /api/biblioteca/{doc_id}` 👤, `DELETE /api/biblioteca/{doc_id}` 👤🔒: biblioteca de documentos reutilizables (texto cifrado con DPAPI; un mismo fichero, por SHA-256, no se duplica). Borrar un documento no lo quita de las consultas que ya lo usaron.
- `POST /api/biblioteca/{doc_id}/adjuntar` 👤🔒: copia el documento como adjunto nuevo (`{"adjunto_id", "nombre", "tipo"}`) para pasarlo en `adjuntos` al crear la consulta.
- `POST /api/consultas/{id}/cancelar` 🔒: detiene un análisis en curso (cancela la tarea y el proceso del CLI). La consulta queda en `ERROR` con el motivo.
- `GET /api/consultas/{id}/vigencia`: artículos del BOE citados que han cambiado de redacción después de la consulta (`source_id`, `titulo`, `version_citada`, `version_actual`).
- `GET /api/hoja-de-ruta/{submateria}`: pasos deterministas de `config/hojas_de_ruta.yaml`, cada uno con su base literal verificada.
- `GET /api/salud?dias=7` 👤: llamadas, correctas, vacías, tiempo agotado y latencia media por modelo, y consultas por estado.
- `GET /api/fuentes?source_id=…&consulta_id=…&quote=…`: Devuelve el texto íntegro oficial de fuentes `BOE:...`, `EUR:...` (Derecho de la UE), `ROJ:...`, `CONV:...` y `DOC:...` con offsets de resaltado literal.
- `GET /api/calendario/plazo`, `GET /api/calendario/tipos`, `GET /api/municipios?q=…`: Motor determinista de plazos procesales y buscador de los 8.131 municipios del INE.
- `GET /api/convenios`: Lista los convenios colectivos indexados en SQLite.
- `POST /api/jurisprudencia/importar` 🔒 → 201: Importa e indexa una sentencia en formato PDF o TXT.
