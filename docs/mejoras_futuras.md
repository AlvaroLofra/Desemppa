# Mejoras futuras (priorizadas)

Prioridad = impacto en «no inventar y acertar» frente al esfuerzo. **A** = siguiente, **B** = después, **C** = cuando
haya tiempo.

## 1. Precisión jurídica (lo más importante)
| Prio | Mejora | Por qué |
|---|---|---|
| A | **Corpus de jurisprudencia real**: importación guiada desde CENDOJ por materia (descarga manual de PDFs + `importar_sentencias.py`) | Hoy casi no hay sentencias; el cortafuegos prohíbe citar las que no están, así que falta doctrina |
| A | **Golden tests por materia** a partir de la batería verificable (los casos que pasan quedan como regresión) | Detectar empeoramientos al cambiar prompts o modelos |
| A | **Aviso de reforma**: si el BOE cambia un artículo usado en una consulta guardada, se avisa | Las leyes cambian (p. ej. LAU 18 en 2026) |
| B | Conector **CURIA** (sentencias del TJUE) | Derecho de la UE más allá del texto de los reglamentos |
| B | **Convenios con sus modificaciones integradas** y convenios provinciales (BOP) | Muchos trabajadores tienen convenio provincial |
| B | **Normas autonómicas** más allá de Cataluña (Aragón, Navarra, País Vasco, Galicia, Baleares) | Derecho foral |
| B | Embeddings locales (ONNX) para la búsqueda semántica sin clave de API | Mejor búsqueda en jurisprudencia y convenios |
| C | Revisión profesional de `plazos.yaml` y `postulacion.yaml` por un abogado | Validación humana de las reglas deterministas |

## 2. Proceso del análisis
| Prio | Mejora | Por qué |
|---|---|---|
| A | **Botón «Detener»** para cancelar una consulta en curso | Hoy hay que esperar a que termine |
| A | El triaje **pregunta por el convenio** cuando es laboral y falta | Sin convenio se pierden salario y plazos sectoriales |
| A | **Escalado automático**: si Flash falla el cortafuegos dos veces, repetir la fase con Argon | Más calidad solo cuando hace falta |
| B | Detectar **varias cuestiones** en una consulta y dar una respuesta por cuestión | Consultas mixtas (despido + vacaciones) |
| B | El Magistrado recalcula la banda de solidez **teniendo en cuenta lo eliminado** por el cortafuegos | La banda refleja lo que queda verificado |
| B | **Caché de dossiers** por materia y fecha | Menos descargas y respuestas más rápidas |
| C | Cola visible para invitados con un tiempo estimado | Red local con varios usuarios |

## 3. Interfaz — HECHO (25-10-2026)
Todas implementadas y probadas (vitest, E2E con navegador real, axe-core y Lighthouse):
- **Citas en línea**: superíndices [n] en la respuesta, el resumen, los pasos, las fortalezas y los riesgos; abren el
  pasaje en el visor. La misma numeración se usa en «Fundamentos verificados» y en la lista «Fuentes citadas».
- **Exportar el expediente**: Markdown (`Alt+E`, con referencias, fundamentos, razonamiento del Magistrado, alegatos y
  auditoría del cortafuegos) y PDF (imprime con todos los plegables abiertos).
- **Calendario de plazos**: `.ics` por plazo o con todos, copiando la fecha del motor determinista, con avisos 7 días
  y 1 día antes.
- **Biblioteca de fuentes**: documentos propios reutilizables (menú lateral → Biblioteca; botón de la biblioteca en
  la caja de texto).
- **Modo lectura** (`Alt+L`, `Esc` para salir) y **atajos de teclado** (`?` muestra la ayuda).
- **Código QR** del enlace de la red local (Ajustes → Red local).
- **Comparar dos consultas** (respuesta, solidez, plazos, postulación y fuentes en común o distintas).
- **axe-core y Lighthouse en el E2E**: sin errores graves de axe; Lighthouse accesibilidad 100 y buenas prácticas
  100 (umbral del test: 95 y 90).

## 4. Funcionamiento interno y operación
| Prio | Mejora | Por qué |
|---|---|---|
| A | **Panel de salud**: cuota, latencia y errores por proveedor | Saber por qué algo va lento o falla |
| A | **Copias de seguridad** de `data/local` (cifradas) | No perder consultas ni claves |
| B | Arranque como **icono en la bandeja** o servicio de Windows | Sin ventana de consola |
| B | Registros con rotación | Que los logs no crezcan sin fin |
| B | Actualización con un clic (`git pull` + rebuild + reinicio) | Hoy se hace a mano |
| C | HTTPS en la red local con un certificado autofirmado | Cifrado en la wifi |
