# Operación: arrancar, usar y diagnosticar

## 1. Arrancar
- **Doble clic en `INICIAR_IURIS_IA.bat`** (recomendado). Hace, en orden:
  1. si el puerto 8000 ya está en uso, solo abre el navegador (no arranca un segundo servidor);
  2. la primera vez, migra los datos antiguos a `data/local/` (`scripts/migrar_datos.py`);
  3. si falta `web/dist`, compila la interfaz;
  4. abre `http://127.0.0.1:8000` y arranca el servidor en esa ventana (ciérrala para parar la app).
- Alternativa: `powershell -ExecutionPolicy Bypass -File scripts/start.ps1`.
- Instalar como aplicación: en Edge/Chrome/Brave, icono "Instalar" en la barra de direcciones.

Tras actualizar el código: cierra la ventana del servidor y vuelve a lanzar el `.bat`. Si cambió el frontend,
compílalo (`cd web && npm run build`); el navegador se actualiza solo (autorreparación).

## 2. Usar
1. Elige el modo (Eco / Equilibrado / Pro) en la cabecera. Los puntos de color indican el estado de cada proveedor
   (verde: última llamada correcta; gris: sin usar; ámbar: cuota agotada; rojo: sin instalar o sin sesión).
2. Describe el caso con fechas e importes; indica el municipio del juzgado u organismo; adjunta documentos
   (marca la casilla de consentimiento solo si quieres que su contenido se envíe a los modelos).
3. Responde las preguntas aclaratorias si aparecen.
4. Revisa: fuentes (clic para ver el texto oficial con la cita resaltada), debate (Defensa, Contraparte,
   Magistrado), dictamen con su banda de solidez, plazos (fecha límite segura) y si necesitas abogado.
5. **Página Modelos**: estado de proveedores, Detectar/Probar y qué modelo hace cada tarea.

## 3. Dónde mirar cuando algo falla
| Fuente | Contenido |
|---|---|
| Mensaje en la app | Incluye código HTTP y llamada: p. ej. `… (HTTP 403 · POST /api/consultas)` |
| `data/local/logs/iuris.log` | Arranque (carpeta de datos y build), cada 403 con motivo, errores de consultas y proveedores |
| Ventana del servidor | Errores no capturados (trazas de Python) |
| Página Modelos | Última llamada y error de cada proveedor |
| `GET /api/estado`, `/api/proveedores`, `/api/version` | Estado en JSON |

## 4. Problemas frecuentes
| Síntoma | Causa | Solución |
|---|---|---|
| "token local inválido" | Pestaña o caché de un arranque anterior | Recarga. Si persiste: F12 → Application → Service workers → Unregister; Storage → Clear site data; Ctrl+Shift+R. Mira `iuris.log` (motivo "ausente" o "distinto del actual") |
| Error 500 al analizar | Bug del servidor | Traza en la ventana del servidor y en `iuris.log`; reproduce con `uv run pytest -m e2e` |
| "Se usó un modelo alternativo" | Cuota agotada o modelo saturado | Normal; si es constante, cambia la asignación en Modelos |
| Proveedor en rojo "sin sesión" | CLI sin login | Claude: `claude` → `/login`. Antigravity: abrir la app o `agy` e iniciar sesión |
| Consulta en ERROR "interrumpida" | Se cerró el servidor mientras analizaba | Volver a lanzarla |
| No aparecen consultas antiguas | Datos en la ubicación vieja | `uv run python scripts/migrar_datos.py --listar` y luego sin `--listar` (desde una terminal normal) |
| "No hay jurisprudencia aplicable" | Corpus vacío | Importar sentencias (ver [datos_y_fuentes.md](datos_y_fuentes.md)) |
| Aviso "festivos locales no cargados" | Sin festivos de ese municipio | Añadirlos (ver [datos_y_fuentes.md](datos_y_fuentes.md)) |

## 5. Mantenimiento periódico
| Cada | Tarea | Cómo |
|---|---|---|
| Octubre | Festivos del año siguiente | `scripts/build_calendar_data.py festivos <año> BOE-A-…` |
| Enero | Municipios INE | `scripts/build_calendar_data.py municipios diccionarioAA.xlsx` |
| Mes | Comprobar el catálogo contra el BOE | `uv run python scripts/verificar_catalogo.py` |
| Cambio de modelos | Probar proveedores y repetir el A/B | Modelos → Probar; `benchmark.blind_judge` |
| Siempre | Copia de seguridad | Copiar `data/local/` con la app cerrada |
