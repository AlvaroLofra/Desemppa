# Operación: arrancar, usar y diagnosticar

Actualizado: 24-10-2026.

## 1. Arrancar la aplicación
- **Doble clic en `INICIAR_IURIS_IA.bat`** (recomendado). Hace, en orden:
  1. Si el puerto 8000 ya está en uso, abre directamente el navegador (no arranca un segundo servidor).
  2. La primera vez, migra los datos antiguos a `data/local/` (`scripts/migrar_datos.py`).
  3. Si falta `web/dist`, compila la interfaz web.
  4. Lanza en segundo plano un vigilante que **espera hasta que `http://127.0.0.1:8000/api/version` devuelve `200 OK`** antes de abrir el navegador, y arranca `uvicorn` en el puerto 8000. Así nunca se produce `ERR_CONNECTION_REFUSED` al arrancar.
- Alternativa por terminal: `powershell -ExecutionPolicy Bypass -File scripts/start.ps1`.

> **Nota si tenías la pestaña abierta de una versión anterior (`index-fDqGlMOV.js`)**:
> Si tu navegador tenía cacheado el Service Worker antiguo anterior al sistema de autorreparación, pulsa una sola vez **`Ctrl + Shift + R` (o `Ctrl + F5`)** al abrir `http://127.0.0.1:8000`. Además, el servidor ahora envía automáticamente la cabecera `Clear-Site-Data: "cache"` si detecta un `403` con token antiguo, limpiando la caché del navegador por sí solo.

## 2. Usar
1. Elige el modo (`Eco` / `Equilibrado` / `Pro`) en el menú de arriba a la derecha: muestra qué modelo resuelve en cada uno.
2. Describe tu caso con fechas e importes; indica el municipio del juzgado u organismo; adjunta documentos si los tienes. `Enter` envía y `Mayús + Enter` hace salto de línea.
3. Responde las preguntas aclaratorias si aparecen (máximo 1 ronda).
4. Revisa (primero aparece la respuesta; «Ver cómo se ha analizado» despliega el proceso):
   - **Fuentes verificadas** (haz clic en cualquier artículo del BOE, sentencia o convenio colectivo para ver el texto oficial completo con la cita literal resaltada).
   - **Debate contradictorio** (`Defensa` vs. `Contraparte` vs. `Magistrado`).
   - **Dictamen certificado** con banda de solidez, plazos calculados de forma determinista y requisitos de postulación (incluyendo el aviso del requisito MASC de la Ley Orgánica 1/2025 en vía civil).
5. **Ajustes** (icono de engranaje, arriba a la derecha; un punto naranja avisa si algún proveedor activo falla):
   - **Modos**: qué modelo y esfuerzo hace cada tarea en Eco, Equilibrado y Pro («Usar un modelo para todo…» aplica
     uno a todas las tareas del modo). «Restablecer» solo deshace esta asignación.
   - **Cuentas y planes**: estado real de cada proveedor, activar/desactivar, **Probar** (llamada mínima),
     **Detectar** (modelos que ofrece) y **Clave** para las APIs (cifrada con DPAPI).
   - **Modelos personalizados**: añadir un modelo por su id exacto; «Restablecer modelos y proveedores» borra
     `config/user_models.toml`.
   - **Apariencia**: claro, oscuro o como el sistema.

## 3. Problemas frecuentes y solución rápida
| Síntoma | Causa | Solución |
|---|---|---|
| En la consola salía `ERR_CONNECTION_REFUSED` + `index-fDqGlMOV.js` + `403 Forbidden` | El `.bat` antiguo abría el navegador antes de que `uvicorn` escuchara en el puerto 8000 y el navegador servía un bundle antiguo desde el Service Worker | **Ya corregido en el código actual.** Cierra la ventana antigua del servidor, lanza el nuevo `INICIAR_IURIS_IA.bat` y pulsa `Ctrl + F5` una vez en el navegador |
| Proveedor `Claude Code` en rojo ("sin sesión iniciada") | No has iniciado sesión en el CLI `claude` | Abre una terminal, ejecuta `claude` y escribe `/login`. Mientras tanto, el sistema usa automáticamente `Claude 5.5` y `Gemini 4 Argon` vía Antigravity |
| "No hay jurisprudencia aplicable en el corpus local" | Aún no has importado PDFs de sentencias del CENDOJ | Descarga los PDFs de [CENDOJ](https://www.poderjudicial.es/search/indexAN.jsp) y ejecuta `uv run python scripts/importar_sentencias.py <carpeta>` |
| Quieres cargar los 10 grandes convenios colectivos estatales | Aún no se ha ejecutado el importador BOE de convenios | Ejecuta `uv run python scripts/importar_convenios_boe.py` (verifica cada referencia contra el BOE antes de indexar) |
| En asuntos laborales sale «No se ha identificado tu convenio colectivo» | La consulta no indica sector o convenio | Indica tu sector (p. ej. «trabajo de camarero») o el nombre del convenio |
