# DESIGN.md — contrato visual de Desemppa

Describe el sistema visual **tal y como está implementado** en `web/src/index.css` y `web/tailwind.config.js`.
Léelo antes de tocar la interfaz. Si añades un token o un patrón, actualiza este fichero en el mismo cambio.
Origen: [docs/propuesta_diseno_ui_ux.md](docs/propuesta_diseno_ui_ux.md) y [docs/plan_ui_ux.md](docs/plan_ui_ux.md).

**Tono:** despacho judicial contemporáneo. Sobrio, sereno y preciso: superficies cálidas de papel, un único acento
azul, nada decorativo que no aporte información.

## 1. Color: solo tokens

Los componentes **nunca** usan colores literales (`#…`, `text-blue-600`): solo estas clases de Tailwind, que leen
variables CSS en `rgb` y cambian solas en modo oscuro (automático por `prefers-color-scheme` o manual con
`data-theme`).

| Clase Tailwind | Variable | Función |
|---|---|---|
| `bg-bg` | `--bg` | Fondo de la página (crema «papel» / casi negro) |
| `bg-surface`, `bg-surface-2`, `bg-surface-3` | `--surface*` | Tarjetas y capas, de menos a más elevadas; `surface-2` también es el *hover* |
| `border-outline` | `--outline` | Bordes y separadores |
| `text-ink`, `text-ink-2`, `text-ink-3` | `--text*` | Texto principal, secundario y terciario (metadatos) |
| `bg-accent`, `text-on-accent` | `--accent`, `--on-accent` | Acción principal y foco. **Azul: se mantiene** |
| `bg-accent-container`, `text-on-accent-container` | `--accent-container`… | Seleccionado, acción tonal |
| `text-danger`, `bg-danger-container` | `--danger*` | Error, peligro, plazo vencido. **El rojo es solo esto** |
| `text-warning`, `bg-warning-container` | `--warning*` | Aviso, incertidumbre |
| `text-success` | `--success` | Verificado, favorable |
| `bg-highlight` | `--highlight` | Pasaje citado resaltado en el visor de fuentes |
| `shadow-float` | `--shadow` | Única sombra: elementos flotantes (menús, compositor) |

Contraste **WCAG AA verificado** para todos los pares texto/fondo (Lighthouse accesibilidad 100). Un par nuevo se
comprueba antes de usarlo.

## 2. Tipografía

- **Sans — Inter Variable** (`font-sans`, por defecto): interfaz, metadatos, tablas, botones, navegación.
- **Serif — Source Serif 4** (`font-serif` o la clase `.legal`): **solo** texto con autoridad jurídica: el dictamen
  del Magistrado, las citas literales del BOE o de una sentencia y la resolución de fondo.
- `.legal`: 16,5 px, interlineado 1,65 (19 px / 1,8 en modo lectura). `.eyebrow`: etiqueta en mayúsculas pequeñas.

## 3. Forma y espacio

| Elemento | Radio |
|---|---|
| Botones, chips de acción, iconos (`.btn*`, `.icon-btn`) | `rounded-full` |
| Bloques grandes (paneles, tarjetas del informe, visor de fuentes) | `rounded-3xl` |
| Tarjetas internas (solidez, avisos) | `rounded-2xl` / `rounded-xl` |
| Campos y chips de filtro (`.field`, `.chip`) | `rounded-lg` |

Espaciado con la escala de Tailwind (múltiplos de 4 px). Separación entre secciones del informe: `space-y-*`, no
márgenes sueltos.

## 4. Componentes base (`@layer components` en `index.css`)

`.btn-primary` (acción principal, una por vista) · `.btn-tonal` (seleccionado o secundaria destacada) ·
`.btn-outline` · `.btn-ghost` · `.icon-btn` (siempre con `aria-label`) · `.chip` · `.field` + `.label` ·
`.legal` · `.eyebrow` · `.scroll-thin` · `.fade-in` (única animación de entrada, 180 ms).

## 5. Estados e interacción

- **Foco:** regla global `:focus-visible` (contorno de 2 px en `--accent`). No se quita ni se sustituye.
- **Seleccionado** (`aria-pressed`, `aria-selected`): fondo tonal **más** un indicador no cromático (icono ✓, borde o
  subrayado).
- **Deshabilitado:** `opacity-40` + `cursor-not-allowed`.
- **Plegables:** botón con `aria-expanded` y `aria-controls` apuntando a una región que existe (oculta con `hidden`).
- **Pestañas:** patrón WAI-ARIA (`tablist`/`tab`/`tabpanel`, `tabIndex` itinerante, flechas/Inicio/Fin).
- **Paneles** (visor de fuentes): `aside` con título (`aria-labelledby`), el foco entra al abrir, `Esc` cierra y el
  foco vuelve a quien lo abrió.
- **Movimiento:** `prefers-reduced-motion: reduce` reduce todas las animaciones y transiciones a ~0 (regla global).

## 6. Solidez de la posición

Cinco niveles (`BANDA_NIVEL`) con **cuatro señales redundantes**: segmentos llenos frente a vacíos con borde (se leen
en blanco y negro), icono propio por banda (`BANDA_ICONO`, `web/src/lib/solidez.ts`), texto (`BANDA_TEXTO`) y nivel
«n/5». Verde = favorable, azul = fundado sin doctrina, ámbar = incierto o dependiente de prueba, rojo = desfavorable,
gris = no valorable. Lo comprueba `web/src/lib/solidez.test.ts`.

## 7. Reglas negativas

- Sin degradados llamativos, *glow*, cristal (*glassmorphism*) ni efectos de *shader*.
- Sin estética de plantilla SaaS ni controles lúdicos (diales, deslizar para confirmar).
- Sin scrolls anidados ocultos: si una zona tiene scroll propio, se ve (`.scroll-thin`) y es enfocable.
- **Sin porcentajes de éxito** ni umbrales técnicos (el 92 % de coincidencia) mostrados al ciudadano.
- **El color nunca es el único portador de significado.**
- Sin sonidos. Sin librerías de UI nuevas (Tailwind 3.4, sin `motion`) salvo decisión expresa.
- El rojo no se usa como acento ni decoración.
