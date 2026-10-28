# Visión del producto — Desemppa

> Definida por el usuario el 28-10-2026. Es el criterio que decide qué entra en la app y cómo.
> Resumen operativo en `CLAUDE.md`/`GEMINI.md` §1.

## 1. Qué es Desemppa

Un **asesor legal general**: debe poder responder a **cualquier inquietud o problema de ámbito legal** de un ciudadano
en España (civil, familia, vivienda, consumo, mercantil, laboral, Seguridad Social, administrativo, tributario,
extranjería, penal…). Responder a todo, también a lo penal, es decisión expresa del usuario (28-10-2026).

Fuera de alcance queda solo lo que **no es jurídico** (recetas, programación, charla sin un problema legal).

## 2. El requisito que no se negocia

**Todo lo que la app afirma debe estar basado en leyes reales, vigentes y comprobadas en tiempo real** contra la fuente
oficial (API de datos abiertos del BOE, convenios del BOE, sentencias importadas por el usuario). Lo que no se pueda
verificar no se dice, y si no hay ninguna norma verificable para la pregunta, la app lo dice abiertamente en lugar de
rellenar el hueco.

El alcance se amplía **descubriendo normas en el BOE**, nunca con el conocimiento interno del modelo.

## 3. «Mínima ventana para alucinar»: qué significa en ingeniería

Los modelos de lenguaje son un componente no fiable, como una entrada de usuario sin validar. Por eso el diseño los
encierra así:

| El modelo puede… | El modelo nunca… |
|---|---|
| Clasificar la consulta y proponer **términos de búsqueda** | Dar identificadores de normas, números de artículo, cifras, plazos o fechas que no consten |
| **Elegir** entre listas cerradas que el sistema obtuvo del BOE (leyes, artículos, convenios) | Introducir un elemento que no esté en esa lista (se descarta, como un id inválido) |
| Redactar y argumentar sobre el texto oficial que tiene delante | Hacer que una frase llegue al ciudadano sin pasar el cortafuegos (`core/firewall.py`) |

Lo determinista lo hace código: plazos (`core/calendar_engine.py`), abogado y procurador (`core/postulacion_rules.py`),
hojas de ruta y escritos con citas literales verificadas, y comprobación de citas (`verify_quote`, NLI de otra familia).

## 4. Cómo se llega ahí

1. **Rutas expertas** (`config/catalogo_materias.yaml`): materias frecuentes con normas, plazos, hojas de ruta y
   postulación deterministas, cada dato con cita literal verificada contra el BOE.
2. **Descubrimiento abierto**: para lo que no cubren las rutas expertas, el sistema busca la ley en el catálogo
   consolidado del BOE, descarga su texto vigente y el modelo solo elige artículos de esa lista. Plan en
   [hoja_de_ruta.md](hoja_de_ruta.md) («Cobertura general verificada»).
3. **Límites honestos**: sin plazo determinista no se calcula plazo; sin norma verificable, se dice. Jurisprudencia:
   solo la importada por el usuario (CENDOJ prohíbe el scraping, art. 507 LOPJ).

## 5. Ámbito de uso

Uso personal y local (`127.0.0.1:8000`), sin comercializar por ahora ([viabilidad_y_estrategia.md](viabilidad_y_estrategia.md)).
Es información jurídica orientativa: no sustituye a un abogado.
