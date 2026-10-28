# Propuesta de Evolución UI/UX para Desemppa
## Mejoras de diseño realistas, apoyadas en lo que ya existe

> **Documento de propuesta (versión revisada tras auditoría independiente, 28-10-2026).**
> **Ámbito:** frontend (`web/`) de Desemppa.
> **Fuente de ideas:** `Recursos Avanzados de UI_UX.md` (Misceláneo/Herramientas UI UX). De ese informe solo se conserva lo que encaja con el proyecto; el resto se descarta (ver §8).
> **Carácter:** propuesta de diseño y experiencia de usuario. No es una guía de implementación.

---

## 1. Punto de partida: lo que Desemppa ya tiene

Antes de proponer nada conviene fijar lo que **ya existe**, para no rehacerlo:

| Elemento | Estado actual |
| :--- | :--- |
| Tipografía dual | Ya está: Source Serif 4 (autoridad) + Inter variable (interfaz). |
| Superficies cálidas | Ya están: fondo crema «papel» (`--bg`), contraste AA verificado, modo oscuro automático y manual. |
| Color de acento | **Azul** (`--accent`). Se mantiene (decisión del usuario). El rojo queda reservado a error/peligro (`--danger`). |
| Medidor de solidez | Ya existe (`Solidez` en `Results.tsx`): 5 niveles y motivos deterministas, sin porcentajes. |
| Progreso de la consulta | Ya existe `FASES` («Fase i de 4») en `Results.tsx`. |
| Componentes accesibles | Ya existen `Dialog`, `Atajos`, `SourceViewer`, `MunicipioPicker`, `HojaDeRuta`. |
| Herramientas de auditoría | `axe-core` y `lighthouse` ya están instalados. |
| Stack | React 18 + Tailwind 3.4 + Vite. Sin `motion`. |

**Principio rector:** *mejorar y consolidar, no rediseñar.* El tono sigue siendo el de un **despacho judicial contemporáneo**: sobrio, sereno y preciso. Sin degradados llamativos, sin brillos, sin estética de plantilla SaaS.

> **Nota sobre dependencias.** El informe recomienda librerías (Cult UI, Kokonut UI) que exigen Tailwind v4 y el paquete `motion`. Migrar solo para eso supone riesgo (el propio informe avisa de que mezclar versiones rompe las clases) y poca ganancia. **Esta propuesta no requiere ninguna librería nueva.**

---

## 2. Propuesta 1 — `DESIGN.md`: el contrato visual del frontend

**Qué es.** Un único documento en la raíz del repositorio (`DESIGN.md`) que describe el sistema visual **tal y como ya está implementado** en `web/src/index.css` y `tailwind.config.js`: paleta y roles semánticos, tipografía, espaciados, radios, sombras, estados de los componentes y **reglas negativas**. Se enlaza desde `CLAUDE.md` y `GEMINI.md` (que deben seguir idénticos) para que Claude y Gemini lo lean antes de tocar la interfaz.

**Contenido mínimo:**
* Tokens existentes (colores, fuentes, sombras) con su función, sin inventar una paleta nueva.
* Uso de la serif: solo dictamen del Magistrado, citas literales del BOE y resolución de fondo. Sans para metadatos, tablas, botones y navegación.
* Reglas negativas: sin degradados fluorescentes ni efecto «glow»; sin scrolls anidados ocultos; sin porcentajes de éxito inventados; el color nunca es el único portador de significado.
* Objetivo de accesibilidad: **WCAG AA como mínimo** (ya verificado en el proyecto), AAA donde no cueste rediseñar la paleta.

**Por qué es útil.** Hoy cada sesión con un asistente puede improvisar radios, sombras o espaciados y la interfaz deriva poco a poco. `DESIGN.md` fija las reglas una sola vez y las hace comprobables.

**Qué aporta.** Coherencia visual entre sesiones, menos rondas de corrección y una barrera contra estéticas ajenas al proyecto. Coste muy bajo: solo documentación, sin riesgo para el código ni para los tests.

---

## 3. Propuesta 2 — Cabecera de resumen en el informe (la parte útil del «Bento»)

**Qué es.** En la pantalla de resultados, una franja superior siempre visible con lo esencial, antes del texto largo:

```
┌───────────────────────────────────────────┬──────────────────────────┐
│ VEREDICTO                                 │ PLAZO                    │
│ Respuesta directa en lenguaje claro       │ Fecha límite (motor de   │
│ + medidor de solidez (5 niveles)          │ plazos), tipo: caducidad │
│                                           │ o prescripción, días     │
│                                           │ restantes y «Añadir al   │
│                                           │ calendario»              │
└───────────────────────────────────────────┴──────────────────────────┘
        (debajo, la lectura lineal de siempre: postulación, MASC,
         hoja de ruta, borrador y expediente técnico)
```

En móvil, las dos tarjetas se apilan: primero veredicto, luego plazo.

**Sobre el Bento completo.** La idea original era repartir *todo* el informe en una cuadrícula de siete cápsulas. Se recomienda **no hacerlo ahora**: mezcla información de distinta urgencia, el orden de lectura se vuelve ambiguo y el informe solo muestra ejemplos de páginas de marketing, no de consulta legal. Si más adelante se quiere probar, se haría como experimento opcional en pantalla ancha.

**Por qué es útil.** Un ciudadano preocupado quiere saber en pocos segundos dos cosas: *qué me dicen* y *cuánto tiempo tengo*. Hoy ambas están dentro de un scroll largo.

**Qué aporta.** Comprensión inmediata del caso, menos riesgo de pasar por alto un plazo fatal y mejor jerarquía visual, **reutilizando datos que ya calcula el sistema** (`Solidez`, `CalendarEngine`, `respuesta_directa`) y sin cambiar el backend.

---

## 4. Propuesta 3 — Monitor de proceso más informativo (mejora de `FASES`)

**Qué es.** Evolucionar el indicador «Fase i de 4» actual para que, durante los 30–60 segundos de espera, muestre **lo que realmente está pasando**, fase a fase:

* **Triaje:** materia detectada y hechos que constan en el texto del usuario.
* **Ingesta:** normas del BOE, jurisprudencia o convenios que se están recuperando.
* **Debate:** indicación neutra de que se contrastan la posición del usuario y la contraria.
* **Certificación:** comprobación de citas, plazos y hechos antes de mostrar nada.

**Condición obligatoria:** solo se muestra información que el backend **ya emite** como eventos reales. Nada simulado ni redactado a mano. Las frases deben ser neutras y salir de los datos de la consulta (no suponer, por ejemplo, un conflicto «empresa-trabajador»).

**Por qué es útil.** Un spinner con una línea de texto genera incertidumbre cuando la espera es larga, y la transparencia es justo el valor diferencial de Desemppa (cortafuegos, citas verificadas).

**Qué aporta.** Confianza durante la espera y una forma de mostrar el rigor del sistema sin añadir complejidad visual. Si el backend no emite algún dato, se deja como está en lugar de inventarlo.

---

## 5. Propuesta 4 — Semáforo de solidez accesible

**Qué es.** Mantener los 5 niveles de solidez actuales, con una **codificación redundante**: cada nivel combina color, icono y texto corto, nunca solo color. Los significados siguen la lógica ya definida:

* **Verde:** criterio favorable y pacífico.
* **Ámbar:** criterios dispares o riesgo probatorio.
* **Rojo:** criterio consolidado en contra o caducidad inminente.
* **Gris:** hechos no determinables o pendientes de aclarar.

Se mantiene la regla ya vigente: **sin porcentajes de éxito inventados**. En el expediente técnico, los sellos del cortafuegos dirán «cita verificada literalmente» y no un porcentaje interno (el 92 % es un umbral técnico que no significa nada para el ciudadano).

**Por qué es útil.** El color solo no llega a personas con daltonismo ni a quien imprime en blanco y negro, y el informe es un documento que se imprime y se enseña.

**Qué aporta.** Accesibilidad real, lectura más rápida y coherencia con el rigor del resto de la aplicación.

---

## 6. Propuesta 5 — Accesibilidad y teclado como mejora continua

**Qué es.** Una pasada de revisión con las herramientas que ya están instaladas (`axe-core`, `lighthouse`):

* **`prefers-reduced-motion`:** que los spinners y transiciones se atenúen o desactiven para quien lo pida en su sistema (hay muchos `animate-spin`; se debe comprobar que todos lo respetan).
* **Navegación completa por teclado:** orden lógico de tabulación, foco visible de alto contraste, apertura de fuentes y selección de aclaraciones sin ratón.
* **Semántica coherente** (vocabulario de The Component Gallery): distinguir *Dialog* modal, *Drawer* lateral de fuentes y *Collapsible* de alegatos, y usar los roles ARIA correspondientes.
* **Chips de aclaración:** estados claros en reposo, foco, pulsado y deshabilitado, con foco de teclado bien visible.

**Por qué es útil.** El público incluye personas mayores y personas en situación de estrés; además la accesibilidad es una forma barata de reducir errores.

**Qué aporta.** Una interfaz más inclusiva y robusta sin añadir dependencias, con resultados medibles (informes de `axe` y Lighthouse).

---

## 7. Propuesta 6 — Compositor flotante (opcional)

**Qué es.** Al hacer scroll por un dictamen largo, la caja de repregunta se contrae en un dock inferior discreto, con fondo ligeramente difuminado.

**Por qué es útil y qué aporta.** Permite seguir preguntando sin perder el punto de lectura. Es una mejora pequeña y de bajo riesgo; debe revisarse en móvil para que no tape contenido ni el teclado virtual. Se implementaría después de las propuestas 1–5.

---

## 8. Lo que se descarta (y por qué)

| Idea del informe original | Motivo del descarte |
| :--- | :--- |
| Librerías Cult UI / Kokonut UI / Hover.dev | Exigen Tailwind v4 y `motion`; la app usa Tailwind 3.4. Riesgo alto, beneficio bajo. |
| Efectos Liquid Glass, ShaderGradient y similares | Contrarios al tono sobrio; ShaderGradient añade ~294 KB; Liquid Glass falla en Safari y Firefox. |
| Controles «físicos» (dials, botones de rasgar, cordones) | Estética lúdica incompatible con un asunto legal serio. |
| Confirmación deslizante (*Slide to Confirm*) | Peor para teclado y accesibilidad que un diálogo de confirmación claro. Para acciones irreversibles se usará un diálogo con texto explícito. |
| Micro-sonidos (Kenney UI Audio) | Aportan poco y chocan con el tono sereno. El aviso de «análisis terminado» se resolverá mejor con el título de la pestaña o una notificación del navegador. |
| Bento Grid completo de 7 cápsulas | Ver §3. Solo se adopta la cabecera de resumen. |
| Acento rojo borgoña | Se confundiría con el color de error. Se mantiene el azul actual. |
| Servidores MCP de Figma / shadcn | El proyecto no usa Figma ni shadcn; añadirían complejidad sin necesidad. |

---

## 9. Orden de ejecución sugerido

1. **`DESIGN.md`** (documentación; base para lo demás).
2. **Accesibilidad y teclado** (§6) y **semáforo accesible** (§5).
3. **Cabecera de resumen** (§3).
4. **Monitor de proceso** (§4), solo con eventos reales del backend.
5. **Compositor flotante** (§7), si tras las anteriores sigue pareciendo útil.

Cada paso debe cerrar con el checklist habitual del proyecto (`ruff`, `mypy`, `pytest`, `npm run build`, `vitest`).

---

## 10. Resumen de impacto

| Dimensión | Hoy | Con esta propuesta |
| :--- | :--- | :--- |
| Coherencia visual entre sesiones | Depende de cada asistente | `DESIGN.md` fija las reglas |
| Comprensión inicial del informe | Hay que leer el scroll | Veredicto y plazo visibles al instante |
| Espera de la consulta | Indicador genérico por fases | Información real de cada fase |
| Accesibilidad | Buena base (AA) | Redundancia color/texto/icono, teclado y movimiento reducido verificados |
| Tono institucional | Sobrio y cálido | Se mantiene y queda documentado |
| Dependencias nuevas | — | Ninguna |
