# Operación: arrancar, usar y diagnosticar

Actualizado: 24-10-2026.

## 1. Arrancar la aplicación
- **Doble clic en `INICIAR_DESEMPPA.bat`** (recomendado; `INICIAR_IURIS_IA.bat` sigue funcionando y lo llama).
  Hace, en orden:
  1. Si el puerto 8000 ya está en uso, `scripts/comprobar_servidor.py` mira quién lo ocupa:
     - si es un Desemppa **con el código actual** (la huella `servidor` de `/api/version` coincide), solo abre el
       navegador;
     - si es un Desemppa **antiguo** de esta carpeta (huella distinta o sin huella, y su línea de comandos contiene
       `api.main:app` y la ruta del proyecto), lo cierra y arranca el nuevo;
     - si es **otro programa**, avisa y no toca nada.
  2. La primera vez, migra los datos antiguos a `data/local/` (`scripts/migrar_datos.py`).
  3. Si falta `web/dist`, compila la interfaz web.
  4. Lanza en segundo plano un vigilante que **espera hasta que `http://127.0.0.1:8000/api/version` devuelve `200 OK`** antes de abrir el navegador, y arranca `uvicorn` en el puerto 8000 escuchando en todas las interfaces (`0.0.0.0`), para poder compartir
     la app en la red local. **Mientras no actives «Compartir en la red local» en Ajustes, cualquier petición que no
     venga de este ordenador recibe 403.**
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

## 3. Compartir en la red local (otros ordenadores de tu wifi)
1. Arranca con `INICIAR_DESEMPPA.bat` (escucha en la red; arrancado con `--host 127.0.0.1` el interruptor sale
   desactivado con un aviso).
2. **Ajustes → Red local** → activa el interruptor. Aparece el enlace (`http://<IP-de-tu-PC>:8000`) con el botón
   Copiar. Pásaselo a la otra persona: lo abre en su navegador y ya está.
3. Por defecto solo pueden usar **Eco**; marca Equilibrado, Pro o Auditoría si quieres permitirlos. Ajusta el tope de
   consultas por persona y día (10 por defecto). Cada invitado puede tener 1 consulta en curso.
4. Los invitados no ven Ajustes ni tu historial; solo sus consultas. Tú ves las suyas en tu historial con la etiqueta
   «Invitado». Su consulta se ejecuta en tu ordenador con tu suscripción y se encola con las tuyas.
5. Al reiniciar Desemppa se desactiva sola.

Avisos:
- **Firewall de Windows**: la primera vez pedirá permiso para Python; acéptalo **solo en redes privadas**. Tu wifi
  debe estar como «Red privada» (Configuración → Red e Internet → propiedades de la wifi). Si no, los otros equipos no
  podrán conectar.
- La conexión no va cifrada (HTTP): úsalo solo en tu red de casa o de confianza y desactívalo al terminar.
- Las suscripciones (Google AI Pro, Claude Pro) son personales: compartirlas de forma continuada puede ir contra sus
  condiciones de uso. Pensado para pruebas puntuales.
- Seguridad: solo se aceptan IPs privadas; el `Host` debe ser la IP de tu equipo (protección frente a DNS
  rebinding); los invitados reciben un token distinto del tuyo y no pueden tocar ajustes, proveedores ni modelos.

## 4. Problemas frecuentes y solución rápida
| Síntoma | Causa | Solución |
|---|---|---|
| En la consola salía `ERR_CONNECTION_REFUSED` + `index-fDqGlMOV.js` + `403 Forbidden` | El `.bat` antiguo abría el navegador antes de que `uvicorn` escuchara en el puerto 8000 y el navegador servía un bundle antiguo desde el Service Worker | **Ya corregido en el código actual.** Cierra la ventana antigua del servidor, lanza `INICIAR_DESEMPPA.bat` y pulsa `Ctrl + F5` una vez en el navegador |
| En la consola salía `GET /api/red 404` en bucle y no se podía abrir «Red local» | El servidor en marcha era anterior a la red local, pero la interfaz ya era la nueva | **Corregido**: `INICIAR_DESEMPPA.bat` sustituye el servidor antiguo; la interfaz deja de reintentar y muestra «el servidor en marcha es el anterior: ciérralo y abre INICIAR_DESEMPPA.bat» |
| Proveedor `Claude Code` en rojo ("sin sesión iniciada") | No has iniciado sesión en el CLI `claude` | Abre una terminal, ejecuta `claude` y escribe `/login`. Mientras tanto, el sistema usa automáticamente `Claude 5.5` y `Gemini 4 Argon` vía Antigravity |
| "No hay jurisprudencia aplicable en el corpus local" | Aún no has importado PDFs de sentencias del CENDOJ | Descarga los PDFs de [CENDOJ](https://www.poderjudicial.es/search/indexAN.jsp) y ejecuta `uv run python scripts/importar_sentencias.py <carpeta>` |
| Quieres cargar los 10 grandes convenios colectivos estatales | Aún no se ha ejecutado el importador BOE de convenios | Ejecuta `uv run python scripts/importar_convenios_boe.py` (verifica cada referencia contra el BOE antes de indexar) |
| En asuntos laborales sale «No se ha identificado tu convenio colectivo» | La consulta no indica sector o convenio | Indica tu sector (p. ej. «trabajo de camarero») o el nombre del convenio |
