# Cortafuegos anti-invención

Objetivo: **ningún modelo puede mostrar al ciudadano algo que no esté respaldado** por una fuente descargada (BOE, EUR-Lex,
sentencia del corpus, convenio, adjunto), por lo que contó el propio ciudadano o por un cálculo determinista (plazos y
postulación). El prompt lo pide, pero quien lo garantiza es el código. Analogía de ingeniería: el LLM es un cliente no
confiable y el cortafuegos es la validación del servidor. Que el cliente valide no basta.

Código: [`core/firewall.py`](../core/firewall.py), llamado desde `_guardarrailes` en [`core/orchestrator.py`](../core/orchestrator.py).
Pruebas: [`tests/unit/test_firewall.py`](../tests/unit/test_firewall.py), con unos 40 casos adversarios.

## 1. El Magistrado ya no escribe texto libre
`respuesta_directa`, `resumen_ciudadano`, `fortalezas`, `riesgos_propios` y `pasos_inmediatos` son listas de
**afirmaciones tipadas** (`core/schemas.py → Afirmacion`):

| Tipo | Qué es | Qué se le exige |
|---|---|---|
| `norma` | Lo que dice la ley | Cita literal verificada **y** NLI = ENTAILS (la cita implica lo afirmado) |
| `razonamiento` | Inferencia a partir de una norma | Cita literal verificada y NLI ≠ CONTRADICTS. Se muestra con la etiqueta «razonamiento» |
| `hecho` | Lo que contó el ciudadano | Tiene que constar en la consulta o en sus aclaraciones |
| `consejo` | Acción práctica | Sin referencias legales, cifras ni fechas |
| `limite` | Lo que no se sabe | Igual que `consejo` |

El texto que lee el ciudadano **se compone en código** solo con las afirmaciones aceptadas.

## 2. Capas (por orden)
1. **Cita literal**: `verify_quote` (rapidfuzz). La cita tiene que estar en el texto completo de la fuente del dossier.
2. **Sin cita no hay afirmación jurídica**: un `norma` o `razonamiento` sin ninguna cita válida se elimina.
3. **Escáner determinista** (regex, sin LLM) sobre cada frase:
   - artículos («art. 36 LAU», «artículo 1561 del Código Civil»): la norma y el artículo tienen que estar en el dossier;
   - números de ley («Ley 29/1994», «LO 1/2025», «Reglamento 261/2004»);
   - jurisprudencia («STS 123/2020», «C-28/20», «el Supremo ha dicho…»): solo si está en el corpus;
   - importes, porcentajes y duraciones, en cifras o en palabras («treinta días»): tienen que aparecer en la consulta,
     en una fuente o en un plazo del motor;
   - fechas: solo las que constan o las calculadas por `CalendarEngine`.

   Las bases legales de los plazos y de la postulación cuentan como referencias permitidas.
4. **NLI de otra familia**: si resuelve Gemini, verifica Claude (y al revés). Así no se corrige a sí mismo. Una
   `norma` con NEUTRAL pasa a `razonamiento`; con CONTRADICTS se elimina.
5. **Hechos no contados** (`hechos_no_constatados`): se elimina lo que atribuye al ciudadano o a la otra parte algo
   que no dijo.
6. **Un reintento**: si algo falla, se devuelve al Magistrado con la lista exacta de fallos. Lo que siga fallando se
   elimina.
7. **Abstención**: si la respuesta directa se queda vacía, se muestra «No puedo contestar… con las fuentes
   disponibles» (`respuesta_parcial`). Nunca se rellena.

Los fundamentos (citas del dictamen) pasan también por el escáner. Los plazos y la postulación no los decide el LLM:
salen del motor determinista.

## 3. Auditoría visible
El dictamen guarda `auditoria`: por cada afirmación, su tipo propuesto y final, sus citas, el resultado de NLI y los
motivos de eliminación o reclasificación. En la interfaz está en **«Cómo se ha verificado (N afirmaciones, M
eliminadas)»**, y en los expedientes de la batería en la sección 4.

## 4. Prompt común
[`core/prompts/_reglas.md`](../core/prompts/_reglas.md) se antepone a Defensa, Contraparte y Magistrado: solo el
dossier, una cita literal por afirmación, nada de normas, sentencias, cifras ni fechas ausentes, «si no consta, dilo» y
nada de porcentajes de éxito. El prompt reduce los fallos y el código los elimina.

## 5. Límites conocidos
- El NLI es un LLM: puede equivocarse. Por eso solo puede **degradar** una afirmación (de norma a razonamiento) o
  eliminarla, nunca añadir nada.
- El escáner reconoce las formas habituales de citar. Una referencia escrita de forma muy rara podría no detectarse,
  pero aun así necesitaría una cita literal verificada para mostrarse como norma.
- Una afirmación correcta puede eliminarse por exceso de celo (falso positivo). Se prefiere eso a mostrar una inventada.
