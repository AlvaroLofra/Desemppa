# API local (REST + SSE)

Base: `http://127.0.0.1:8000`. Implementación: `api/main.py`. Documentación interactiva generada por FastAPI en
`http://127.0.0.1:8000/docs` (mientras la app está arrancada).

## Reglas comunes

| Aspecto | Regla |
|---|---|
| Host | Solo `127.0.0.1` o `localhost` (otro `Host` → **400**, protección frente a DNS rebinding) |
| Autenticación | Las operaciones de escritura exigen la cabecera `X-Iuris-Token: <token>`. El SSE lo exige como `?token=` |
| Obtener el token | `GET /api/token` (no tiene CORS: solo la propia app puede leerlo). Se guarda en `data/local/local_token.txt` y es estable entre reinicios; si se borra el fichero se genera otro |
| Errores | JSON `{"detail": "..."}` con el código HTTP. 403 de token: `token local inválido (ausente|distinto del actual); recarga la página` (queda en `data/local/logs/iuris.log`) |
| Codificación | UTF-8; fechas ISO `AAAA-MM-DD`; municipios con código INE de 5 dígitos |

Ejemplo de cliente mínimo (PowerShell):
```powershell
$t = (Invoke-RestMethod http://127.0.0.1:8000/api/token).token
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/consultas -Headers @{"X-Iuris-Token"=$t} `
  -ContentType "application/json" -Body '{"texto":"El casero no me devuelve la fianza de 900 euros","modo":"eco","municipio_ine":"28079"}'
```

## Estado y versión

### `GET /api/version`
`{"build": "mvl1ogjz"}`: identificador del build de `web/dist` (`version.json`). El frontend lo compara con el
suyo para autorrepararse.

### `GET /api/token`
`{"token": "…"}`.

### `GET /api/estado`
Resumen para la cabecera de la app:
```json
{
  "proveedores": {"<id>": { ...ver /api/proveedores... }},
  "modo_por_defecto": "equilibrado",
  "modos": {"eco": {"label": "Eco", "llamadas_claude_por_consulta": 0, "roles": {"triaje": {"model": "...", "effort": "low"}}}},
  "modelos": {"agy_gemini_flash": {"proveedor": "antigravity_cli", "id": "gemini-3.8-flash-{effort}", "etiqueta": "..."}},
  "corpus": {"sentencias": 0, "municipios": 8131, "anios_festivos": [2026]}
}
```

## Proveedores y asignación de modelos

### `GET /api/proveedores`
Por proveedor (`gemini_api`, `claude_cli`, `antigravity_cli`, `codex_cli`):
```json
{"etiqueta": "Antigravity (suscripción Google AI Pro)", "tipo": "cli", "habilitado": true, "instalado": true,
 "version": "1.4.6", "ultima_llamada": {"ok": true, "error_tipo": null, "creado_en": "...", "modelo": "..."},
 "breaker": {"estado": "closed", "abierto_hasta": null, "motivo": null},
 "uso_ultimas_5h": {"llamadas": 3, "input_tokens": 0, "output_tokens": 0, "coste_equivalente_usd": 0},
 "login": "instrucciones para iniciar sesión", "modelos": ["agy_gemini_flash", "agy_claude_sonnet"]}
```

### `POST /api/proveedores/{id}/detectar` 🔒
Lista los modelos que ofrece el proveedor (CLI: su orden de descubrimiento, p. ej. `agy models`).
`{"instalado": true, "modelos": ["gemini-3.8-flash-high", ...]}` · 404 si está desactivado o no existe.

### `POST /api/modelos/{alias}/probar` 🔒
Llamada mínima real ("Responde exactamente con la palabra: OK") con el primer *effort* del modelo. Consume cuota
mínima y queda en el ledger. `{"ok": true, "latencia_ms": 12500, "respuesta": "OK", "error": null}`.

### `GET /api/ajustes/perfiles`
```json
{"modos": {"eco": {"triaje": {"model": "...", "effort": "low"}}},
 "por_defecto": { "...igual, sin las preferencias del usuario..." },
 "modelos": {"<alias>": {"etiqueta": "...", "proveedor": "...", "efforts": ["low","medium"], "disponible": true}}}
```

### `PUT /api/ajustes/perfiles` 🔒
Cuerpo: `{"<modo>": {"<rol>": {"model": "<alias>", "effort": "low|medium|high"}}}` (parcial: lo no indicado se
mantiene). Se valida contra el catálogo; inválido → **422** y no se guarda. Se aplica a las consultas siguientes.

### `DELETE /api/ajustes/perfiles` 🔒
Borra `config/user_profiles.toml` (vuelve a `config/profiles.toml`).

## Consultas

### `POST /api/consultas` 🔒 → 201
```json
{"texto": "10–20.000 caracteres", "modo": "eco|equilibrado|pro|auditoria",
 "municipio_ine": "28079", "adjuntos": ["<adjunto_id>", "..."]}
```
Respuesta `{"consulta_id": "<uuid>"}`. El análisis arranca en segundo plano; síguelo por el SSE.
Errores: 422 (validación o modo desconocido), 403 (token).

### `POST /api/consultas/{id}/aclaraciones` 🔒
Solo si la consulta está en `ESPERANDO_ACLARACION` (si no → **409**).
```json
{"respuestas": [{"pregunta": "¿Cuándo entregaste las llaves?", "respuesta": "2026-06-01"},
                {"pregunta": "Municipio", "respuesta": "Madrid", "municipio_ine": "28079"}]}
```
→ `{"consulta_id": "...", "estado": "reanudada"}`; reabre el SSE con `after=<último id recibido>`.

### `GET /api/consultas`
Historial (50 más recientes): `[{"consulta_id", "creado_en", "modo", "estado", "titulo", "banda"}]`.

### `GET /api/consultas/{id}`
`{"consulta_id", "modo", "estado", "triage", "dossier", "debate", "dictamen", "texto" (original restaurado), "adjuntos"}`.

### `GET /api/consultar/stream/{id}?token=…&after=N` (SSE)
- Reenvía primero el historial persistido desde el evento `N` (o desde la cabecera `Last-Event-ID`) y luego los
  eventos en vivo. Cierra tras `final`, `error` o `clarification_needed`.
- Cada evento: `id: <secuencia>`, `event: <tipo>`, `data: <JSON>`. Cada 15 s llega `heartbeat`.
- Los `debate_delta` no se persisten (no se reenvían en el replay).

| Evento | `data` |
|---|---|
| `phase` | `{"estado": "TRIAJE"}` (todas las transiciones de la máquina de estados) |
| `triage` | `TriageOutputSchema` + `resumen_hechos` + `submateria_descripcion` |
| `clarification_needed` | `{"preguntas": [{"id","texto","tipo_respuesta":"si_no|fecha|importe|opcion|texto|municipio","opciones","motivo"}]}` |
| `source` | `{"source_id","tipo":"boe|sentencia|adjunto","titulo","url","extracto"}` |
| `debate_delta` | `{"rol":"defensa|contraparte|magistrado","text":"…"}` (texto en vivo del JSON) |
| `debate_done` | Defensa/Contraparte: `{"rol","alegato","verificacion":[[{"ok","score","source_id","motivo"}]]}`; Magistrado: `{"rol","resolucion"}` |
| `guardrail` | `{"id":"G2-G4|G5|G6|G9","ok":bool,"detalle":[...]}` (G6 añade `banda_propuesta`/`banda_final`) |
| `deadline` | `{"plazos":[PlazoCalculado],"avisos":[...]}` |
| `quota` | `{"rol","avisos":[...],"modelo"}`: se usó un modelo alternativo |
| `final` | `{"estado":"CERTIFICADA","dictamen":DictamenCertificadoSchema,"banda_texto"}` · `{"estado":"BLOQUEADA","mensaje","plazos","postulacion","avisos","aviso_legal"}` · `{"estado":"FUERA_DE_ALCANCE","mensaje","aviso_legal"}` |
| `error` | `{"mensaje","tipo"}` |
| `heartbeat` | `{}` |

Esquemas completos: `core/schemas.py` (`TriageOutputSchema`, `PlazoCalculado`, `DictamenCertificadoSchema`…).

## Adjuntos y fuentes

### `POST /api/adjuntos` 🔒 → 201 (multipart)
Campos: `archivo` (PDF o TXT, máx. 20 MB) y `permitir_envio` (`true|false`, por defecto `false`).
El texto se extrae en local y se guarda cifrado. **Sin `permitir_envio`, su contenido nunca se envía a un modelo.**
→ `{"adjunto_id","nombre","tipo":"nomina|carta_despido|sancion|contrato|otro","caracteres","paginas_sin_texto":[n],"permitir_envio"}`.
Errores: 413, 415, 422 (sin texto: PDF escaneado sin OCR).

### `GET /api/fuentes?source_id=…&consulta_id=…&quote=…`
Texto completo de una fuente (del dossier de la consulta, del corpus o del BOE) y, si se pasa `quote`, el rango
a resaltar: `{"source_id","titulo","texto","url","resaltado":{"offsets":[ini,fin],"score":100.0,"ok":true}}`.

## Calendario, municipios, convenios y jurisprudencia

### `GET /api/calendario/plazo?tipo=…&fecha_inicio=AAAA-MM-DD&municipio_ine=…&foral=CT`
Calcula un plazo con el motor determinista → `PlazoCalculado` (`fecha_limite_segura`, `dia_gracia_hasta`,
`dias_habiles_restantes`, `avisos`, `titular`…). Tipo desconocido o municipio inválido → 422.

### `GET /api/calendario/tipos`
`[{"id","descripcion","base_legal"}]` (de `config/plazos.yaml`).

### `GET /api/municipios?q=alca`
Hasta 15 coincidencias (sin tildes ni mayúsculas): `[{"codigo_ine","nombre","provincia"}]`.

### `GET /api/convenios?sector=…&territorio=…`
Convenios cargados en la base de datos.

### `POST /api/jurisprudencia/importar` 🔒 → 201 (multipart, campo `archivo`)
PDF o texto de una sentencia (formato CENDOJ). Se segmenta, se aísla el voto particular, se indexa en FTS5 y, si
hay clave de Gemini, en LanceDB. → `{"roj","nueva","chunks","avisos"}`; sin ROJ o sin fecha → 422.

## Frontend
- `GET /` y cualquier ruta no-API → `index.html` (sin caché, sin token).
- `GET /assets/*` → bundle; `sw.js`, `version.json` y `manifest.webmanifest` se sirven sin caché.

🔒 = requiere `X-Iuris-Token`.
