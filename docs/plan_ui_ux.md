# Plan de implementación UI/UX (28-10-2026)

Fuente: [propuesta_diseno_ui_ux.md](propuesta_diseno_ui_ux.md). Revisada contra el código el 28-10-2026: se adoptan las
propuestas 1–5; la 6 se descarta porque ya existe (`Composer variante="dock"` en `web/src/App.tsx`). Ninguna dependencia
nueva, ningún cambio de backend salvo el que se indica en la fase 4. Cada fase es una sesión quirúrgica y cierra con el
checklist de `CLAUDE.md` §3.5.

## Lo que ya está hecho (no repetir)

| Propuesta | Ya existe |
|---|---|
| §6 movimiento reducido | Regla global `prefers-reduced-motion` en `web/src/index.css:84` (cubre todos los `animate-spin`). Solo falta comprobarla en e2e. |
| §5 «92 %» al ciudadano | La interfaz no muestra el umbral; nada que quitar. |
| §5 sin porcentajes | `Solidez` (`Results.tsx:295`) ya dice «No es una probabilidad de ganar». |
| §7 compositor flotante | `Composer variante="dock"` ya se muestra bajo el informe. **Descartada.** |
| Aviso de fin | Pendiente; se resuelve en la fase 4 (título de la pestaña), sin sonidos. |

## Fase 1 — `DESIGN.md` (solo documentación) ✅ 28-10-2026

- Crear `DESIGN.md` en la raíz describiendo **lo que hay** en `web/src/index.css` y `web/tailwind.config.js`: tokens de
  color (`--bg`, `--surface*`, `--ink*`, `--accent*`, `--danger`…), fuentes, radios (`rounded-2xl` tarjetas,
  `rounded-full` botones), sombras, clases `.btn*`, foco (`:focus-visible`).
- Reglas de uso: serif solo para dictamen, citas literales y resolución; sans para todo lo demás.
- Reglas negativas de la propuesta §2 (sin degradados, glow, scrolls anidados, porcentajes; el color nunca va solo).
- Enlazarlo desde `CLAUDE.md` y `GEMINI.md` (§2.6), **con el mismo texto en ambos**.
- Verificación: ninguna de código; revisar que cada token citado existe (`grep` sobre `index.css`).

## Fase 2 — Solidez redundante y accesibilidad ✅ 28-10-2026

1. **Solidez con icono y texto** (`Results.tsx`, `BANDA_COLOR`/`Solidez`): añadir `BANDA_ICONO` (lucide, ya instalado:
   `CircleCheck`, `CircleAlert`, `CircleX`, `CircleHelp`…) junto a `BANDA_TEXTO`. El medidor sigue siendo de 5
   segmentos; los segmentos vacíos llevan borde para leerse en blanco y negro (impresión).
   - Test vitest: cada `Banda` tiene icono, texto y explicación (falla si se añade una banda sin los tres).
2. **Teclado y semántica** (`SourceViewer`, `Dialog`, alegatos plegables, chips de aclaración):
   - Panel de fuentes: `role="dialog"` + `aria-modal` si bloquea, o región complementaria si no; foco al abrir y
     devolución del foco al cerrar; `Esc` lo cierra.
   - Alegatos: botón con `aria-expanded`/`aria-controls` (patrón ya usado en `Solidez`).
   - Chips de aclaración: estados reposo/foco/pulsado (`aria-pressed`)/deshabilitado visibles.
3. **e2e** (`tests/e2e/`): ampliar el test de axe-core para que recorra el informe con el panel de fuentes abierto y
   una ronda de aclaración; añadir un test que emule `prefers-reduced-motion: reduce` y compruebe la duración de
   animación calculada del spinner. Lighthouse debe seguir en 100.

## Fase 3 — Cabecera de resumen (veredicto + plazo)

- Nuevo componente `ResumenCabecera` en `web/src/components/Results.tsx` (o fichero propio si pasa de ~80 líneas),
  colocado antes del texto largo del dictamen (`Results.tsx:603`).
  - Izquierda: `respuesta_directa` + `Solidez` compacta (reutilizar el componente con una prop `compacta`).
  - Derecha: el plazo **más urgente** de `apuntables(d.plazos)` (función ya existente): fecha límite segura,
    naturaleza (caducidad/prescripción, en lenguaje sencillo), días restantes con `diasNaturalesHasta` y
    `BotonCalendario`. Sin plazo → la tarjeta no se pinta y el veredicto ocupa todo el ancho.
  - `grid md:grid-cols-[2fr_1fr]`; en móvil se apilan (veredicto primero).
- No duplicar: la sección `Plazos` completa sigue debajo; la cabecera solo enlaza a ella (`#plazos`).
- Sin cambios de backend: todos los datos ya llegan en `final`/`deadline`.
- Tests: vitest de selección del plazo más urgente (ignora `titular: "contraparte"` y vencidos) y e2e de que la
  cabecera aparece y es lo primero que lee un lector de pantalla tras el título.

## Fase 4 — Monitor de proceso con eventos reales

Eventos que el backend **ya emite** (`useConsulta.ts:105`): `phase`, `triage`, `source`, `debate_done`, `guardrail`,
`deadline`, `quota`. Con ellos, sin inventar texto:

| Fase | Dato real mostrado | Origen |
|---|---|---|
| Triaje | «Materia: {submateria_descripcion}» | evento `triage` |
| Ingesta | «{n} artículos del BOE, {m} sentencias, {k} convenios» y título de la última fuente | eventos `source` |
| Debate | Texto fijo neutro de `FASES` + aviso si `quota` indica cambio de modelo | `debate_done`, `quota` |
| Certificación | «Comprobando citas… {ok}/{total} controles superados» | eventos `guardrail` |

- Ampliar `ProgressLine` (`Results.tsx:34`) a una lista de 4 pasos (hecho / en curso / pendiente) con `aria-live`
  solo en la línea en curso, para no saturar al lector de pantalla.
- Título de la pestaña: «(✓) Desemppa» al llegar `final` si la pestaña está oculta (`document.hidden`); se restaura
  al volver. Sin sonidos ni notificaciones del sistema (no piden permiso).
- Si un dato no llega (p. ej. sin fuentes `source` en ingesta degradada), se muestra solo el texto de `FASES`.
- Tests: vitest del reductor de `useConsulta` con una secuencia grabada de eventos.

## Fuera de este plan

Bento completo, librerías Tailwind v4/`motion`, efectos visuales, sonidos y *slide to confirm* (ver propuesta §8).
