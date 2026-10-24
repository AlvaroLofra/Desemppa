# Valoración del benchmark de Gemini 3.8 Flash (modo Eco) — 24-10-2026

Revisión independiente (Claude) de `benchmark/reports/benchmark_38_flash_20261024_1730.*`: 8 casos reales ejecutados
con navegador en modo Eco por Gemini 3.8 Flash. Se leyó cada dictamen completo y se contrastó con la fuente
oficial. **Ninguna valoración jurídica de este documento se ha hecho de memoria**: los artículos citados se
comprobaron en el BOE o en EUR-Lex/Cellar en esta sesión, y lo que no se pudo comprobar se indica.

## 1. Fiabilidad del informe original
La nota «9,2 / 10» **no era fiable**:
- La sección «Análisis cualitativo» estaba escrita a mano en `benchmark/browser_runner.py` y salía idéntica en
  cualquier ejecución. Aparecía igual en la que sacó 3/10. Contenía afirmaciones falsas: «se resuelve entre 45 y
  80 s» frente a una media medida de 142 s; un lock en `%LOCALAPPDATA%` que ya no existe.
- 3 de los 10 puntos se daban solo por certificar.
- La comprobación de normas aceptaba cualquier artículo de la ley: bastaba con que apareciera el identificador
  `BOE-A-…`.
- La «estimación» miraba solo la primera cuestión.
- El caso 4 tenía una respuesta «esperada» (DEFENSA) discutible para una decisión de recurrir o pagar.
- El caso 7 exigía el art. 128 TRLGDCU y no el Reglamento 261/2004, que es la norma que da los 250 €.

**Corregido** en `browser_runner.py` y en los casos:
- se elimina el texto fijo;
- se exige norma Y artículo en la cita verificada;
- sin puntos por certificar;
- se añade una lista de comprobación manual con los `puntos_clave` de cada caso;
- caso 4 sin parte «ganadora»; caso 7 con el Reglamento 261/2004, arts. 5 y 7.

## 2. Lectura real de los 8 dictámenes (antes de las correcciones)

| Caso | Valoración |
|---|---|
| 1 Fianza (LAU) | ✅ Correcto: arts. 1561 CC, 21 y 36 LAU; plazos bien calculados |
| 2 Despido en baja médica | ✅ Correcto y prudente (Ley 15/2022, art. 55 ET, caducidad de 20 días hábiles); fundamentos repetidos |
| 3 Salarios en hostelería | ✅ Correcto (art. 29.3 ET, mora del 10 %; art. 35 ET, horas extra). Avisa con razón de que el convenio de hostelería de Madrid no está cargado |
| 4 Multa ORA | 🟡 Razonable (20 días naturales, pago con el 50 %). Fallo: calculaba la reposición desde la denuncia, pero el art. 96.2 LTSV la cuenta desde la notificación de la **resolución** |
| 5 Filtración en Barcelona | ❌ No respondía «¿ha prescrito?». **Usaba una fecha de inicio inventada** (30-09-2026; el usuario dijo 10-06-2024) y aplicaba la LPH estatal en lugar del Código civil catalán |
| 6 Falso autónomo | ✅ Correcto (arts. 1 y 8 ET, art. 11 LETA); fundamentos repetidos |
| 7 Vuelo cancelado | ❌ No citaba el Reglamento 261/2004 ni los 250 € (no estaba en el corpus) e **inventaba un hecho** («la aerolínea alega que debes esperar su plazo interno») |
| 8 Comisión de apertura | ❌ No contestaba «¿puedo demandar ya?» (requisito de negociación previa de la LO 1/2025). La aclaración decía «¿Cuál es la tipo de producto?» |

Además, 3 de 8 consultas tuvieron una respuesta vacía de Flash, que salvó el modelo alternativo.

## 3. Correcciones y verificación en vivo (misma sesión, modo Eco)

| Problema | Corrección | Resultado en vivo |
|---|---|---|
| Fecha de plazo inventada | `core/fechas_es.py`: una fecha solo vale si consta en el texto o en las aclaraciones; si no, se pregunta | Caso 5: plazo del 10-06-2024 al **10-06-2027** (3 años) |
| Derecho foral catalán | `normas_forales` en el catálogo: en Cataluña, art. 121-21 CCCat y libro V en lugar de la LPH. El conector BOE resuelve artículos con guion («121-21» → bloque `a12121`). Textos comprobados en el BOE | Caso 5: «No, no ha prescrito… 3 años (Código Civil de Cataluña)», citando arts. 121-21 y 553-38 CCCat |
| Sin respuesta a la pregunta | Campo `respuesta_directa` obligatorio en el Magistrado (si falta, se repite la resolución); se muestra arriba del dictamen | Casos 5, 7 y 8 empiezan contestando lo preguntado |
| Hechos inventados | `hechos_no_constatados` (`core/nli.py`): las frases que atribuyen hechos no contados fuerzan la repetición y, si persisten, se eliminan | Caso 7 sin el hecho inventado |
| Sin Derecho de la UE | `connectors/eurlex_client.py` (Cellar/EUR-Lex), fuente `EUR:` verificada literalmente. Catálogo: Reglamento 261/2004, arts. 5, 7 y 8 | Caso 7: «Sí… 250 euros», citando los arts. 5, 7 y 8 verificados; reconoce que la doctrina del TJUE sobre huelgas no está en el corpus |
| Negociación previa (MASC) | Los arts. 5 y 10 de la LO 1/2025 entran en el dossier de toda consulta civil | Caso 8: «No es posible demandar directamente… la ley exige acudir con carácter previo a un medio de solución de controversias», citando los arts. 5 y 10 verificados |
| Reintento que tumbaba la consulta | Si el reintento del Magistrado falla, se sigue con la primera resolución; un importe sin fundamento se anula sin forzar reintento | Caso 8 pasa de ERROR (3 timeouts de 240 s) a certificado en 287 s |
| Fundamentos repetidos | Deduplicación por fuente y cita o afirmación | — |
| Reposición en tráfico | Se quita del cálculo y se explica en una nota (arts. 95.4 y 96.2 LTSV, verificados) | — |
| «Días hábiles» en plazos de años | Solo se informan en plazos de días hábiles | — |

## 4. Lo que el benchmark NO mide y queda pendiente
- La **doctrina jurisprudencial** (TS, TJUE) no está en el corpus. En los casos 2, 7 y 8 es decisiva y la app lo
  advierte, pero no la puede citar. Hay que importar sentencias (CENDOJ) y, para la UE, valorar un conector de
  CURIA.
- La revisión jurídica profesional de los YAML sigue pendiente.
- Flash devuelve a veces respuestas vacías porque intenta usar herramientas: el modelo alternativo lo cubre, pero
  añade latencia.
