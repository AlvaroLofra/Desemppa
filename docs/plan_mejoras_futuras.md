# Plan para las mejoras futuras pendientes (25-10-2026)

Cómo incorporar todo lo que queda **PENDIENTE** en [mejoras_futuras.md](mejoras_futuras.md). Cada fase:
- es una sesión acotada (regla de sesiones quirúrgicas de `CLAUDE.md`);
- termina con el checklist completo en verde.

Ningún identificador (BOE, CELEX, ECLI, URL de un boletín) se escribe sin comprobarlo en la fuente esa misma sesión
(regla 1). Lo que aquí aparece sin verificar va marcado como **sin verificar**.

## Ya hecho en esta tanda
| Mejora | Qué se ha hecho |
|---|---|
| Corpus de jurisprudencia: importación guiada | Biblioteca → «Jurisprudencia». Por materia muestra los términos de búsqueda del catálogo, un botón al buscador de CENDOJ y una zona para arrastrar los PDF (`POST /api/jurisprudencia/importar`). También muestra cuántas sentencias tienes por materia (`GET /api/jurisprudencia/resumen`). La descarga sigue siendo manual (art. 507 LOPJ). |
| Batería periódica y goldens | `benchmark/ejecutar.py` admite `--reanudar` y `--pausa`, y responde dos rondas de preguntas. `benchmark/congelar.py` convierte los casos con 7/7 en regresión (`tests/golden/test_bateria.py`). `benchmark/comparar_ejecuciones.py` genera el informe A→B. `scripts/programar_bateria.ps1` crea la tarea semanal, pero **no se registra sin tu sí**. |
| Icono en la bandeja | Lanzador de escritorio `launcher/desemppa.pyw`, con ventana propia y bandeja; lo instala `INSTALAR_DESEMPPA.bat`. |

## Fase 1 (A): golden tests por materia
1. Ejecutar la batería completa en Eco y repetir los casos que fallen por causas ajenas a la app (cuota, interrupciones). Para repetirlos: borrar su carpeta y lanzar `--reanudar <dir>`.
2. Ejecutar `benchmark/juez.py <dir>` y revisar a mano los casos en los que el juez y el evaluador discrepen.
3. Ejecutar `benchmark/congelar.py <dir>` y hacer commit de `tests/golden/bateria/*.json`.
4. Para cada fallo real, crear una tarea con el caso, la comprobación que falla y el fichero implicado.

Los plazos y la postulación de las hojas de verdad ya se recalculan con el motor, así que no se duplican en `plazos.yaml`.

**Verificación:** `uv run pytest tests/golden -q`.

## Fase 2 (B): conector CURIA (TJUE)
- **Qué:** sentencias del TJUE como fuente citable (`CURIA:<ECLI>`), con el mismo cortafuegos que el BOE.
- **Cómo:**
  - nuevo `connectors/curia_client.py`, con la misma forma que `eurlex_client.py`;
  - el texto se obtiene por CELEX de jurisprudencia desde Cellar, con la API que ya usa `eurlex_client.py`. Hay que confirmar que Cellar sirve el texto de las sentencias: **sin verificar**;
  - caché de 7 días;
  - `FragmentoFuente(tipo="sentencia")` y el prefijo nuevo en `SourceId` (`core/schemas.py`).
- **Riesgo:** el formato de las sentencias (párrafos numerados). Hace falta un parser y un test con un fixture descargado a mano.
- **Verificación:** test de contrato con el fixture y un test `live` marcado.

## Fase 3 (B): convenios con modificaciones y convenios provinciales (BOP)
- **Modificaciones:**
  - `scripts/importar_convenios_boe.py` ya trae el texto original;
  - hay que añadir las «disposiciones posteriores» de cada convenio (tablas salariales, revisiones) como versiones nuevas en `convenios_versiones`, con su fecha de vigencia;
  - `buscar_en_vigentes` ya elige la versión vigente.
- **BOP:** cada boletín provincial publica de una forma distinta. Se haría un conector por provincia (`connectors/bop/<provincia>.py`), empezando por las del usuario. Las URL de cada BOP están **sin verificar**.
- **Verificación:** `uv run pytest -m live tests/contract/test_live_convenios_boe.py -q`, más un test por provincia.

## Fase 4 (B): normas autonómicas (Aragón, Navarra, País Vasco, Galicia, Baleares)
- **Qué:** derecho civil foral, igual que ya se hace con Cataluña (`normas_forales` en `config/catalogo_materias.yaml`).
- **Cómo:**
  - buscar en el BOE el identificador consolidado de cada compilación y comprobar que existe con `connectors/boe_client.py`;
  - añadirlo a `config/materias` / `normas_forales` y crear un golden por territorio.
  - Hasta que se compruebe, todos los identificadores están **sin verificar**.
- **Verificación:** `scripts/verificar_hojas_de_ruta.py` y un test `live` de la descarga.

## Fase 5 (B): embeddings locales (ONNX)
- **Qué:** búsqueda semántica sin `GEMINI_API_KEY` (hoy, sin clave, solo se usa BM25).
- **Cómo:**
  - `onnxruntime` y un modelo multilingüe pequeño, descargado una vez a `data/local/modelos/`;
  - una clase `OnnxEmbedder` que cumpla el protocolo de `connectors/embeddings.py`;
  - volver a indexar con `scripts/importar_sentencias.py`.
- **Riesgo:** el tamaño del modelo y la licencia, que hay que revisar antes de elegirlo.
- **Verificación:** test de contrato de la dimensión y un benchmark de recuperación con las sentencias importadas.

## Fase 6 (B): actualización con un clic
- **Qué:** un botón en Ajustes, «Actualizar».
- **Cómo:**
  - `git pull --ff-only`, `uv sync`, `npm ci && npm run build` y reinicio;
  - el reinicio lo hace el lanzador de escritorio: para el servidor y vuelve a arrancarlo con `launcher/servidor.py`.
- **Riesgo:** que haya cambios locales sin commit. En ese caso no se actualiza y se avisa.
- **Verificación:** test unitario de la secuencia con `subprocess` simulado.

## Fase 7 (C): HTTPS en la red local
Requiere generar un certificado autofirmado e instalarlo en cada móvil invitado, así que solo merece la pena si se
abre a más gente. Se deja documentado y sin implementar.

## Fase 8 (C): caché de dossiers
Solo si se mide que la búsqueda local es lenta: se guardaría el dossier por (submateria, fecha de los hechos, hash
de los términos).

## Fase 9 (C): revisión por un abogado
Revisión externa de `plazos.yaml`, `postulacion.yaml` y `hojas_de_ruta.yaml`. No la puede hacer el código. El
expediente en Markdown, con su sello SHA-256, sirve como material de revisión.
