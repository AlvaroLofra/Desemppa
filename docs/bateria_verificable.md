# Batería verificable (30 casos reales)

Pruebas de extremo a extremo con modelos reales cuyo resultado **puede comprobar cualquier persona o LLM** solo con el
expediente generado, sin acceso a la app.

## Piezas
| Fichero | Qué hace |
|---|---|
| `benchmark/casos_verificables/V01..V30.json` | Los casos: 12 típicos, 8 límite, 6 con trampa y 4 con aclaraciones. Incluye consulta, municipio, fecha de los hechos, respuestas simuladas a las aclaraciones y `verdad` (estado y respuesta esperados, artículos clave, plazos, postulación, puntos clave y frases prohibidas) |
| `benchmark/construir_hoja_verdad.py` | Genera `hojas/V*.json`: texto **literal** de cada artículo clave (BOE vigente a la fecha de los hechos o EUR-Lex) con su SHA-256, plazos calculados por `CalendarEngine` y postulación según `postulacion.yaml`. Si algo no se puede descargar, falla: nunca se rellena a mano |
| `benchmark/ejecutar.py` | Ejecuta los casos por la API, responde las aclaraciones, descarga el texto completo de cada fuente citada y guarda el expediente, la evaluación y `informe.md` |
| `benchmark/expediente.py` | `expediente.md` y `.json`: consulta, respuesta, afirmaciones con su cita, fundamentos, plazos, postulación, razonamiento del Magistrado por cuestión, alegatos, auditoría del cortafuegos, texto completo de las fuentes y hoja de verdad |
| `benchmark/evaluar.py` | Evaluación automática sin LLM: estado, citas literales, escáner del cortafuegos, artículos clave citados, plazos, postulación y frases prohibidas |
| `benchmark/instrucciones_verificador.md` | Prompt autocontenido para que **cualquier LLM** verifique un expediente y devuelva un veredicto en JSON |
| `benchmark/juez.py` | Juez LLM de otra familia (por defecto Claude Sonnet 5.5 por Antigravity) sobre todos los expedientes. Añade al informe sus notas y los desacuerdos con la evaluación automática |

## Uso
```bash
uv run python benchmark/construir_hoja_verdad.py
```
```bash
uv run python benchmark/ejecutar.py --modo eco --casos todos --base http://127.0.0.1:8000
```
```bash
uv run python benchmark/juez.py benchmark/expedientes/<ejecucion>
```
`--casos` admite `todos`, una categoría (`tipico`, `limite`, `trampa`, `aclaracion`) o ids (`V05 V16`). Cada consulta en
Eco tarda unos 2 minutos.

## Verificar con un LLM externo
Abre cualquier LLM (ChatGPT, Gemini, Claude…) y pega primero el contenido de `benchmark/instrucciones_verificador.md` y
después el `expediente.md` del caso. El expediente contiene todo lo necesario: el texto de las fuentes y la hoja de
verdad con los artículos oficiales y sus hashes. Si el verificador encuentra una afirmación sin respaldo, es un fallo
real.

## Cómo leer un expediente
1. **Respuesta y afirmaciones**: cada línea dice su sección y su tipo (`norma`, `razonamiento`, `hecho`, `consejo`,
   `limite`) y debajo lleva la cita literal con su `source_id`.
2. **Razonamiento del Magistrado**: por cada cuestión en disputa, a quién da la razón (Defensa o Contraparte) y con qué
   citas.
3. **Auditoría**: lo que el cortafuegos eliminó o reclasificó antes de mostrarlo, y por qué.
4. **Fuentes**: el texto completo de cada artículo citado, con su URL oficial, para comprobar las citas a mano.
5. **Hoja de verdad**: lo que debería decir, comprobado contra el BOE y EUR-Lex.

Los resultados de cada ejecución quedan en `benchmark/expedientes/<fecha>_<modo>/informe.md`.
