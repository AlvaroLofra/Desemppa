# Propuesta de rediseño de la interfaz — «sobrio, claro, premium»

Estado: **primera versión implementada el 24-10-2026** (fases R0–R4; R5 parcial) · Afecta a `web/`.

> **Qué se ha implementado y con qué decisiones** (las «decisiones abiertas» de §10 se resolvieron así):
> - Tema: sigue al sistema por defecto, con selector Claro/Oscuro/Sistema en Ajustes → Apariencia.
> - Primitivas propias (sin Radix, para no añadir dependencias): `components/ui/primitives.tsx` (Switch, Dialog, Seccion).
> - Nombre visible «Iuris». Iconos: lucide con trazo por defecto (no se ha cambiado de librería).
> - Fuentes Inter y Source Serif 4 autoalojadas con `@fontsource` (ya no se carga Google Fonts).
> - Componentes: `TopBar`, `Sidebar`, `Composer`, `Results` (`Answer`, `ProcessDetails`, `Clarification`,
>   `ProgressLine`), `SourceViewer`, `settings/` (`SettingsPage`, `Modes`, `Accounts`, `CustomModels`).
>   Se han eliminado `Header.tsx` y `ModelsPage.tsx`.
> - Pendiente de R5: `axe-core` en el E2E y Lighthouse; atajo `Ctrl+K`; botón «Detener» (el backend aún no permite
>   cancelar una consulta, así que no se ha puesto un botón que no haría nada).
> - Desviaciones: `Results.tsx` sigue siendo un único fichero (~400 líneas) con los subcomponentes dentro.

## 1. Diagnóstico de la interfaz actual

La interfaz actual funciona, pero transmite «plantilla generada por IA»:

- **Tema oscuro fijo** con pizarra (`slate-900/950`), `backdrop-blur` y tarjetas semitransparentes (`bg-slate-900/60`).
- **Ámbar como color de marca** en todo: logotipo, modo activo, botón principal, selección y bordes. Además hay rosa,
  esmeralda y ámbar como colores de estado. Hay demasiados acentos compitiendo entre sí.
- **Ruido en la cabecera**: logotipo, eslogan, selector de 3 modos con iconos, de 3 a 10 puntos de colores de
  proveedores y el botón «Modelos», todo en una sola línea.
- **Todo es una tarjeta**: triaje, fuentes, debate y dictamen se apilan como cajas con borde del mismo peso. No hay
  jerarquía, y el resultado (el dictamen) no destaca sobre el proceso.
- **El compositor está al final** de la columna y desaparece mientras se analiza.
- **La página Modelos** (689 líneas) muestra a la vez filtros, compañías, claves, tabla de tareas y formulario.
- Chips, iconos decorativos (`Sparkles`, `Zap`, `Gauge`), textos de marketing y emojis en la documentación.

## 2. Objetivo y referencias

Una herramienta que parezca **un producto de Google de última generación**: Gemini (gemini.google.com),
NotebookLM, Google AI Studio y la familia Material 3 «expressive» en su versión más contenida.

Qué tomar de cada referencia:

| Referencia | Qué copiar | Qué **no** copiar |
|---|---|---|
| **Gemini** | Pantalla inicial vacía con saludo y un **compositor central** grande, redondeado y flotante; respuestas sin caja, como texto sobre el lienzo; barra lateral plegable | Degradados de colores en el saludo |
| **NotebookLM** | Disposición **Fuentes · Conversación · Estudio** en tres paneles; las citas como números en línea que abren la fuente con el pasaje resaltado | Ilustraciones y portadas de colores |
| **AI Studio** | Ajustes de modelo en un **panel lateral derecho** discreto, no en una página aparte | La densidad de controles |

## 3. Principios

1. **El contenido es la interfaz.** Texto jurídico legible sobre un lienzo limpio; casi nada de bordes y cajas.
2. **Un solo acento.** Un azul sobrio para la acción principal y los enlaces. El color de estado solo aparece
   cuando hay algo que comunicar (error, plazo crítico), nunca como decoración.
3. **Jerarquía por tipografía y espacio**, no por color ni bordes.
4. **Progresividad.** Por defecto se ve la respuesta; el proceso (fases, debate, modelos usados) está a un clic.
5. **Calma.** Animaciones cortas y funcionales, sin brillos, cristal ni degradados.
6. **Claro por defecto, oscuro opcional**, como Google: respeta `prefers-color-scheme` y tiene un selector manual.

## 4. Sistema visual (tokens)

Se definen como variables CSS en `web/src/index.css` y se exponen a Tailwind en `tailwind.config.js`
(`colors: { surface: "rgb(var(--surface) / <alpha-value>)", … }`). Los componentes **solo** usan tokens, nunca
`slate-800` ni similares.

### 4.1 Color

| Token | Claro | Oscuro | Uso |
|---|---|---|---|
| `--bg` | `#FFFFFF` | `#131314` | Lienzo |
| `--surface` | `#F8F9FA` | `#1E1F20` | Barra lateral, compositor, paneles |
| `--surface-2` | `#F0F4F9` | `#282A2C` | *Hover*, elemento seleccionado, chips |
| `--outline` | `#E3E3E3` | `#3C4043` | Separadores (finos, 1 px, escasos) |
| `--text` | `#1F1F1F` | `#E3E3E3` | Texto principal |
| `--text-2` | `#5F6368` | `#9AA0A6` | Texto secundario, metadatos |
| `--accent` | `#0B57D0` | `#A8C7FA` | Botón principal, enlaces, foco, cita activa |
| `--accent-container` | `#D3E3FD` | `#0842A0` | Fondo del modo seleccionado o de la cita resaltada |
| `--danger` | `#B3261E` | `#F2B8B5` | Errores, plazo vencido o crítico |
| `--warning` | `#8C5000` | `#FFB95C` | Avisos (cuota, cobertura degradada) |
| `--success` | `#146C2E` | `#6DD58C` | Solo «cita verificada» y estado correcto de proveedor |
| `--highlight` | `#FEF7C3` | `#4A4419` | Resaltado del pasaje citado en el visor de fuentes |

Son valores de inspiración Material 3 neutro y Gemini. Todos los pares texto/fondo deben cumplir **WCAG AA**
(4,5:1 en texto normal), y hay que comprobarlo al implementar.

### 4.2 Tipografía

- **Interfaz**: `Google Sans Text` no tiene licencia libre. Alternativas casi idénticas y autoalojadas (sin CDN, la
  app es local): **Inter** (ya se usa) o **Figtree**. Recomendación: **Inter** con `font-feature-settings: "cv11", "ss01"`
  y pesos 400/500 (no 600/700).
- **Texto jurídico** (dictamen y fuentes): mantener una serif legible, **Source Serif 4**, a 16–17 px con interlineado
  1,65 y medida máxima de unos 72 caracteres.
- Escala: 12 / 14 / 16 / 20 / 28 / 36 px. Los títulos usan peso 400–500 con *tracking* ligeramente negativo, no
  negrita.
- Números tabulares (`tabular-nums`) en plazos, importes y fechas.

### 4.3 Forma, espacio y elevación

- Radios: 8 px (chips y campos), 16 px (paneles), **28 px** (compositor, como Gemini) y `9999px` (botones
  píldora).
- Espaciado en múltiplos de 4. El lienzo central tiene un máximo de 760 px.
- Elevación: sin sombras salvo en el compositor flotante y en los menús
  (`0 1px 3px rgb(0 0 0 / .08), 0 4px 12px rgb(0 0 0 / .06)`). Nada de `backdrop-blur`.

### 4.4 Iconografía y movimiento

- **Material Symbols Rounded** (autoalojado, peso 300, relleno 0) o, para no cambiar de librería, **lucide** con
  `strokeWidth={1.5}` y tamaño fijo de 20 px. Solo iconos funcionales: se eliminan `Sparkles`, `Zap`, `Gauge` y el
  logotipo de la balanza en cada pantalla.
- Movimiento: 150–200 ms con `cubic-bezier(.2,0,0,1)`, solo en apariciones, paneles y *hover*. El *streaming* de
  texto aparece suavemente, sin cursores parpadeantes. Hay que respetar `prefers-reduced-motion`.

## 5. Estructura y pantallas

### 5.1 Esqueleto general

```
┌───────────┬──────────────────────────────────────────┬────────────────┐
│ Barra     │  Iuris                    [Equilibrado ▾] (⚙)            │
│ lateral   │                                          │  Panel derecho │
│ plegable  │          lienzo central (≤760 px)        │  contextual:   │
│           │                                          │  · Fuente      │
│ + Nueva   │                                          │  · Ajustes     │
│ Historial │                                          │  (se oculta)   │
│           │      ╭────────────────────────────╮      │                │
│ ⚙ Ajustes │      │ Describe tu caso…   📎  ➤ │      │                │
└───────────┴──────╰────────────────────────────╯──────┴────────────────┘
```

- **Cabecera mínima**: nombre en texto (sin logotipo de colores), selector de modo como **menú desplegable** (como
  el selector de modelo de Gemini) y un icono de ajustes. **Sin indicadores de proveedores** en la cabecera.
- **Barra lateral** (como Gemini): «Nueva consulta», historial agrupado por fecha (Hoy, Esta semana…) y, abajo,
  Ajustes. Se pliega a una tira de iconos.
- **Panel derecho contextual** (como NotebookLM o AI Studio): se abre al pulsar una cita (visor de fuente) o los
  ajustes, y desplaza el lienzo en lugar de taparlo.

### 5.2 Inicio (sin consulta)

- Saludo centrado en tipografía grande y ligera, en color de texto normal, sin degradado: «¿En qué te puedo
  ayudar?» y debajo, en `--text-2`, una línea: «Analizo tu caso con la ley vigente y cito el texto oficial».
- **Compositor central** de 28 px de radio, fondo `--surface` y altura que crece con el texto. Dentro: adjuntar
  (📎), municipio como chip opcional («Juzgado: Madrid ✕») y enviar (➤) solo activo con texto.
- Opcional: 3 o 4 **sugerencias** en chips sobrios («Me han despedido», «No me devuelven la fianza»…).

### 5.3 Consulta en curso y resultado

El orden se invierte respecto al actual: **primero la respuesta**, y el proceso queda plegado.

1. **Tu pregunta**, alineada a la derecha en una burbuja `--surface-2`, como en Gemini.
2. **Indicador de progreso compacto** en una sola línea: «Buscando en el BOE… · Fase 2 de 4», con un spinner
   discreto. Al terminar se convierte en «Analizado en 1 min 42 s · ver proceso ▸», que despliega fases, debate y
   modelos usados.
3. **Dictamen** como texto sobre el lienzo, sin tarjeta:
   - Una línea de **conclusión** destacada (20 px).
   - **Solidez** como una etiqueta de texto («Solidez: media») con un punto de color, no como un medidor.
   - Las **citas en línea como superíndices numerados** `[1]` en color de acento. Al pasar el ratón se ve el extracto;
     al hacer clic se abre el panel derecho con el texto oficial y el pasaje resaltado (patrón NotebookLM).
   - **Plazos**: bloque con fondo `--surface` (la única «caja» del dictamen) con fecha límite en números
     tabulares grandes, días restantes y base legal. Solo se usa `--danger` si quedan ≤ 5 días hábiles.
   - **Postulación y MASC**: nota en `--text-2` con un icono de información.
   - Acciones al pie, como iconos sutiles: copiar, exportar e imprimir.
4. **Debate** (Defensa / Contraparte / Magistrado) dentro de «ver proceso», con **pestañas subrayadas** (estilo
   Material), no botones de colores.
5. **Aclaraciones** (cuando el triaje pregunta): las preguntas aparecen como un mensaje del asistente con campos
   integrados, y el compositor queda deshabilitado con el texto «Responde arriba para continuar».
6. El **compositor se mantiene siempre abajo** (fijo), deshabilitado mientras se analiza, con un botón «Detener».

### 5.4 Fuentes (panel derecho, patrón NotebookLM)

- Lista de fuentes de la consulta agrupadas por tipo (**Legislación · Jurisprudencia · Convenio · Tus
  documentos**), cada una con un título de una línea y una marca de verificación en `--success` si la cita se
  verificó.
- Visor: título, enlace «Abrir en BOE ↗», texto en serif y pasaje resaltado con `--highlight` y desplazamiento
  automático hasta él.

### 5.5 Ajustes (sustituye a la página «Modelos»)

Panel lateral derecho o página con navegación vertical, dividido en secciones cortas:

| Sección | Contenido |
|---|---|
| **Modos** | Una fila por modo (Eco, Equilibrado, Pro, Auditoría) y dentro, una lista de roles con un desplegable de modelo y otro de esfuerzo. Sin tabla densa |
| **Cuentas y planes** | Una fila por proveedor: nombre, estado en texto («Conectado», «Sin sesión: ejecuta `claude /login`»), interruptor de activado y «Probar». Las claves de API van en un diálogo, no en línea |
| **Modelos personalizados** | Lista y botón «Añadir modelo» que abre un diálogo |
| **Datos** | Corpus (sentencias, convenios, festivos) con botones de importar (futura «Biblioteca») |
| **Apariencia** | Claro / Oscuro / Sistema |

El estado de los proveedores que hoy está en la cabecera pasa aquí. En la cabecera solo aparece un aviso si
*ningún* proveedor del modo elegido está disponible.

## 6. Qué se elimina

- El ámbar como color de marca y todos los acentos decorativos (rosa, esmeralda, ámbar en bordes).
- El tema oscuro fijo, el `backdrop-blur` y las tarjetas semitransparentes.
- Los puntos de colores de proveedores en la cabecera.
- Los iconos en los botones de modo, el eslogan de la cabecera y el logotipo en la pantalla inicial.
- Las tarjetas con borde para triaje, fuentes y debate: pasan a ser secciones con título o quedan plegadas.
- Las clases `.card`, `.chip` y `.btn-*` actuales: se sustituyen por componentes con tokens.

## 7. Correspondencia con los componentes actuales

| Actual (`web/src/components`) | Nuevo | Cambio |
|---|---|---|
| `Header.tsx` | `TopBar.tsx` + `ModeMenu.tsx` | Mínima; el estado de proveedores se va a Ajustes |
| `Sidebar.tsx` | `Sidebar.tsx` | Plegable, agrupada por fecha, Ajustes abajo |
| `Composer.tsx` + `MunicipioPicker.tsx` | `Composer.tsx` | Centrado al inicio y fijo abajo después; municipio como chip |
| `Results.tsx` (365 líneas) | `Answer.tsx`, `Citation.tsx`, `DeadlineBlock.tsx`, `ProcessDetails.tsx`, `Clarification.tsx` | Trocear; la respuesta primero y el proceso plegado |
| `SourceViewer.tsx` | `SidePanel.tsx` + `SourceView.tsx` | Panel derecho reutilizable (fuente o ajustes) |
| `ModelsPage.tsx` (689 líneas) | `settings/Modes.tsx`, `settings/Accounts.tsx`, `settings/CustomModels.tsx`, `settings/Appearance.tsx` | Dividir por sección |
| — | `ui/Button.tsx`, `ui/IconButton.tsx`, `ui/Select.tsx`, `ui/Switch.tsx`, `ui/Dialog.tsx`, `ui/Tabs.tsx`, `ui/Tooltip.tsx` | Primitivas mínimas propias o **Radix UI** (accesibles, sin estilo) |

`lib/` (`api.ts`, `useConsulta.ts`, `selfHeal.ts`…) **no cambia**: el rediseño es solo de presentación.

## 8. Accesibilidad

- Contraste AA verificado en ambos temas, con un test automático (p. ej. `axe-core` en el E2E de Playwright).
- Foco visible: anillo de 2 px en `--accent` con separación de 2 px.
- Todo usable con teclado: `Ctrl+K` para nueva consulta, `Esc` para cerrar el panel y `Enter` / `Shift+Enter` en
  el compositor.
- Regiones ARIA: `nav` (barra lateral), `main`, `complementary` (panel derecho) y `aria-live="polite"` para el
  progreso.
- Superíndices de cita con `aria-label="Fuente 3: art. 56 Estatuto de los Trabajadores"`.

## 9. Plan de implementación por fases

| Fase | Contenido | Criterio de aceptación |
|---|---|---|
| **R0 · Fundamentos** | Tokens CSS (claro y oscuro), configuración de Tailwind, fuentes autoalojadas, primitivas `ui/`, selector de tema | Página de muestra interna con todos los tokens y primitivas en ambos temas; AA verificado |
| **R1 · Esqueleto** | `TopBar`, `Sidebar` plegable, `SidePanel`, layout de 3 zonas, responsive (< 900 px: barra lateral como cajón y panel a pantalla completa) | La navegación actual funciona sin cambios de lógica; E2E existentes en verde |
| **R2 · Inicio y compositor** | Saludo, compositor central o fijo, chip de municipio, adjuntos | Se puede enviar una consulta igual que hoy; vitest del compositor |
| **R3 · Respuesta** | `Answer` con citas numeradas, `DeadlineBlock`, `ProcessDetails` plegado y debate en pestañas | Un caso real (fianza) se lee de arriba abajo sin desplegar nada; las citas abren el panel con el resaltado correcto |
| **R4 · Ajustes** | Sustituir `ModelsPage` por las secciones de Ajustes | Todas las funciones actuales de Modelos accesibles; ningún componente supera las 250 líneas |
| **R5 · Pulido** | Movimiento, estados vacíos, errores en lenguaje claro, atajos de teclado, `axe` en el E2E | Lighthouse Accesibilidad ≥ 95; capturas antes/después en ambos temas |

Cada fase es un commit independiente. El E2E de navegador (`tests/e2e/test_navegador.py`) debe seguir en verde en
todas ellas, adaptando los selectores a roles y etiquetas accesibles (no a clases CSS).

## 10. Decisiones abiertas para cuando se implemente

1. **¿Tema por defecto?** Recomendación: seguir al sistema (claro si el sistema es claro).
2. **¿Radix UI o primitivas propias?** Recomendación: Radix para `Dialog`, `Select`, `Tabs` y `Tooltip`, porque
   resuelve la accesibilidad. Añade unos 30 KB.
3. **¿Nombre visible?** «Iuris» a secas en la cabecera queda más limpio que «Iuris-IA».
4. **¿Iconos?** Material Symbols da el aspecto más «Google». Lucide con trazo fino evita cambiar de dependencia.
