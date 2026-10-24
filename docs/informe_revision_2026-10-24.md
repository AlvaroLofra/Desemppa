# Informe de revisión y estado del proyecto — 24-10-2026

Revisión independiente (Claude) del trabajo hecho por Gemini 4 Argon en la sesión del 23-10-2026 (cambios **sin
confirmar** en git sobre el commit `dda2c37`) y valoración general del estado de Iuris-IA.

> Resumen en una frase: **la base técnica es sólida y todo compila y pasa los tests, pero la sesión de Argon introdujo
> datos inventados (referencias BOE de convenios), dos scripts que no arrancan y documentación que afirma cosas que
> no son ciertas.** Nada de eso rompe la app en el uso diario, pero hay que corregirlo antes de confirmar los cambios.

---

## 1. Verificación realizada

| Comprobación | Resultado |
|---|---|
| `uv run pytest` | 232 en verde |
| `uv run pytest -m e2e` (navegador real) | 4 en verde |
| `ruff check`, `ruff format --check`, `mypy --strict` | En verde (33 ficheros) |
| `npm run build`, `tsc`, `vitest` | En verde (8 tests) |
| `agy models` en vivo | Los ids que usa Argon (`gemini-4-argon-*`, `gemini-3.8-flash-*`, `claude-*-5-5-*`, `gpt-oss-120b-medium`) **existen** |
| Ejecutar `scripts/importar_sentencias.py` | ❌ `ModuleNotFoundError: core.database` |
| Referencias BOE de `data/convenios_seed.yaml` contra el BOE real | ❌ **9 de 10 no corresponden a ningún convenio** (ver §3.1) |

Los tests no detectan los fallos de §3 porque **los scripts no tienen tests y `mypy` no los analiza**, y porque los
datos del seed no se contrastan con el BOE en ningún test.

---

## 2. Qué ha hecho bien Argon

- **Ids de modelos de Antigravity correctos** y verificados contra `agy models`. Perfiles sin dependencia de
  `GEMINI_API_KEY`, coherente con tu situación actual (no hay `.env` con clave).
- **Arranque más robusto**: `INICIAR_IURIS_IA.bat` y `start.ps1` esperan a `/api/version` antes de abrir el
  navegador. Bien pensado.
- **Convenios conectados a la ingesta** (`Orchestrator._ingesta`) y al visor de fuentes (`CONV:`), con el mismo
  patrón que BOE y jurisprudencia. Arreglo correcto de `buscar_clausulas` cuando la consulta FTS queda vacía.
- **Adaptadores HTTP** (`core/providers/http_adapter.py`) limpios: clasificación de errores coherente con el router,
  clave cifrada con DPAPI, transporte inyectable para tests, tests unitarios propios.
- **Superposición `user_models.toml`** con validación y *rollback* si el catálogo resultante no es válido.
- **No reintrodujo `--dangerously-*`** y respetó la validación que lo prohíbe.
- **Los documentos originales no se perdieron**: están movidos a `docs/historico_v2/` (git los ve como borrados en la
  raíz y nuevos en esa carpeta).

---

## 3. Problemas encontrados (por gravedad)

### 🔴 Críticos — corregir antes de confirmar

#### 3.1 Referencias BOE de convenios inventadas
`data/convenios_seed.yaml` asigna a los 10 convenios estatales un `boletin_ref` y un `codigo_regcon`. He
descargado el título real de cada referencia en el BOE:

| Sector en el seed | `boletin_ref` | Lo que es en realidad |
|---|---|---|
| Construcción | BOE-A-2023-20461 | Convocatoria de plazas del Ayuntamiento de Pego |
| Metal | BOE-A-2022-605 | Plan de estudios de un máster (Univ. Alfonso X) |
| Hostelería | BOE-A-2023-6347 | Revisión salarial del ALEH (tablas), no el texto del acuerdo |
| Contact center | BOE-A-2023-13742 | VIII Convenio marco estatal de *otro* sector de servicios |
| Seguridad privada | BOE-A-2022-21145 | Tribunal de oposiciones de las Cortes Generales |
| Comercio | BOE-A-2023-13917 | Normas UNE (Dirección General de Industria) |
| Dependencia | BOE-A-2023-13918 | Normas UNE en información pública |
| Limpieza | BOE-A-2013-5439 | Sentencia del Tribunal Constitucional 96/2013 |
| Química | BOE-A-2021-12082 | Ampliación de plazo de un concurso de funcionarios |
| Enseñanza | BOE-A-2021-8746 | Plan de estudios de Sociología (Univ. Granada) |

Los códigos REGCON probablemente también son inventados (no verificados). **Si el importador funcionara, indexaría
como «convenio de la construcción» una convocatoria municipal**, y el sistema la citaría con verificación literal
«correcta», porque la cita coincidiría con el texto descargado. Es justo el tipo de alucinación que la arquitectura
intenta impedir, pero metida en los datos de partida, donde los guardarraíles no la ven.

**Acción**: revertir esos campos o sustituirlos por referencias comprobadas una a una en el buscador del BOE.
Añadir un test `live` que compruebe que el título de cada `boletin_ref` contiene «convenio» y el sector.

#### 3.2 Los dos scripts importadores no arrancan
`scripts/importar_convenios_boe.py` y `scripts/importar_sentencias.py` importan `core.database` (no existe) y usan
`settings.db_path` y `settings.Lance_dir` (los campos reales son `sqlite_path` y `lancedb_dir`). Fallan en la
primera línea. La documentación (`hoja_de_ruta.md`, `operacion.md`, `guia_juridica…`) te pide ejecutarlos.
**Acción**: usar `storage.database.open_database` y los campos correctos, y añadir un test de humo
que ejecute cada script con `--help` o con una carpeta vacía. Hay que incluir `scripts/` en `mypy`.

#### 3.3 La búsqueda de convenios mezcla convenios y versiones
`ConveniosRepository.buscar_en_vigentes` filtra solo `vigencia_desde <= fecha`: no comprueba `vigencia_hasta`, así
que devuelve también versiones caducadas. Además, busca en **todos** los convenios, no en el que se aplica al
trabajador. Una consulta de hostelería puede recibir artículos del convenio del metal como «fuente verificada».
**Acción**: filtrar por vigencia completa, quedarse con la última versión de cada convenio y, sobre todo, que el
triaje identifique el sector o convenio (o preguntarlo en la ronda de aclaraciones) antes de buscar.

### 🟠 Importantes

#### 3.4 Texto jurídico nuevo sin validar (MASC, LO 1/2025)
El aviso MASC en `config/postulacion.yaml` va bien encaminado, pero tiene imprecisiones:
- ~~Se añade al **monitorio**, y es muy probable que el monitorio esté entre las excepciones~~ **Rectificado tras
  leer el BOE**: el art. 5.2 exige el requisito en los procesos especiales del libro IV de la LEC (donde está el
  monitorio) y entre las excepciones solo figuran el juicio cambiario y el monitorio europeo. Argon acertaba en esto.
- Presenta el **burofax** como MASC suficiente. La ley habla de negociación, mediación, conciliación u oferta
  vinculante confidencial, y que un simple requerimiento baste es discutible.
- Para > 2.000 € dice que la herramienta «prepara borradores previos (como burofax)», **funcionalidad que no
  existe**.
- No recoge las demás excepciones (tutela de derechos fundamentales, medidas cautelares, ejecución, ciertos procesos
  de familia…).

**Acción**: redactar el texto contra el articulado del BOE y añadir golden tests de excepciones.

#### 3.5 Documentación que afirma cosas no verificadas o falsas
- «La latencia en `high` ya está corregida» (`CLAUDE.md`, `proveedores_y_modelos.md`): no hay ningún cambio de
  código que lo justifique. En el spike, `gemini-3.8-flash-high` con prompts grandes superaba los 240 s. El modo
  **Eco usa `high` para el Magistrado**, el paso con el prompt más grande. Riesgo de *timeouts* y de consultas muy
  lentas.
- `proveedores_y_modelos.md` dice `claude-sonnet-4-6` / `claude-opus-4-6`, mientras que `models.toml` y
  `providers.toml` usan `claude-sonnet-4-5` / `claude-opus-4-5`. Son incoherentes entre sí y probablemente están
  desactualizados respecto a los modelos actuales de la API de Anthropic.
- `viabilidad_y_estrategia.md` se pone notas (8,8 y 9,8 sobre 10) y afirma que las alucinaciones normativas quedan
  «prácticamente a cero». §3.1 demuestra lo contrario. Conviene un tono menos promocional.
- `hoja_de_ruta.md` marca como «✅ Hecho» los scripts y los convenios del BOE, que no funcionan.

#### 3.6 Cadena de *fallbacks* con saltos inútiles
`agy_gemini_flash` cae primero a `claude_sonnet` (proveedor `claude_cli`, **desactivado** en tu
`user_models.toml`) y luego a dos modelos de la Gemini API, también desactivada. En la práctica, si Antigravity
falla, no hay alternativa y el error llega tarde. Además, `gemini_flash` y `gemini_flash_38_api` son el mismo modelo
duplicado, y `rpd = 250` contradice los 20 al día que medimos en el plan gratuito.
**Acción**: que el *fallback* de Flash sea `agy_claude_sonnet` o `agy_gpt_oss` (mismo plan, otra familia),
eliminar el duplicado y poner el RPD medido.

#### 3.7 «Restablecer perfiles» borra más de lo que dice
`reset_user_profiles()` ahora también borra `user_models.toml`: al pulsar «Restablecer» en la página Modelos se
pierden en silencio los proveedores desactivados y los modelos personalizados. Debería ser una acción aparte.

### 🟡 Menores / deuda técnica
- `save_user_provider_or_model` escribe TOML a mano sin escapar comillas ni barras invertidas: una etiqueta con `"`
  rompe el fichero. El *rollback* lo salva, pero conviene usar `tomli_w`.
- `configurar_proveedor` modifica `s.gemini._api_key` (atributo privado). Mejor un método público `set_api_key`.
- Los adaptadores HTTP no hacen *streaming* real (devuelven todo al final) y `AnthropicApiAdapter` ignora
  `json_mode` y fija `max_tokens = 8192`. Es aceptable mientras no se usen.
- ~~`discover_models` bloquea el bucle de eventos~~ **Rectificado**: el endpoint `detectar` lo ejecuta con
  `asyncio.to_thread`, así que no bloquea.
- Los modelos personalizados se crean siempre con `fallbacks = ["agy_gemini_flash"]` y `timeout_s = 240` fijos.
- `Clear-Site-Data: "cache"` en cada 403 es inofensivo, pero es un parche más. La causa ya estaba resuelta con
  selfHeal.
- `CLAUDE.md` y `GEMINI.md` son idénticos y obligan a mantenerlos a mano. Mejor que `GEMINI.md` tenga una línea
  que remita a `CLAUDE.md`, o un enlace simbólico.
- `docs/arquitectura_interactiva.html` carga Tailwind desde `cdn.tailwindcss.com` y fuentes de Google. Es aceptable
  en un documento, pero no funciona sin conexión.
- `ModelsPage.tsx` ha crecido a 689 líneas en un solo componente. Conviene trocearlo (y el rediseño lo hará).
- Sin búsqueda vectorial: sin clave de Gemini no hay `GeminiEmbedder`, así que la jurisprudencia solo usa BM25. No
  está documentado como limitación.
- El conjunto de cambios es grande y **no está confirmado**: 40 ficheros mezclan arreglos, funcionalidades,
  datos y documentación.

---

## 4. Estado general del proyecto

| Área | Estado | Comentario |
|---|---|---|
| Núcleo (router, *breaker*, *ledger*, CLIs) | 🟢 Sólido | Bien probado; la cola serializada y el *restart* funcionan |
| Pipeline de 4 fases + guardarraíles | 🟢 Sólido | La verificación literal es el gran valor diferencial |
| BOE con versión vigente | 🟢 Sólido | Probado en vivo |
| Calendario y plazos | 🟢 Bueno · 🔎 orientativo | 36 golden tests; pendiente de validación jurídica |
| Postulación | 🟠 | Base buena; el texto MASC nuevo necesita revisión (§3.4) |
| Jurisprudencia | 🟠 Código listo, corpus vacío | Importador por lotes roto (§3.2); solo BM25 sin clave de Gemini |
| Convenios | 🔴 | Integración correcta, pero con datos falsos y búsqueda sin acotar (§3.1, §3.3) |
| Proveedores y modelos | 🟢/🟠 | Muy flexible; *fallbacks* mal ordenados y riesgo de `high` (§3.5, §3.6) |
| API + seguridad local | 🟢 | Loopback, token, DPAPI y validación de flags peligrosos |
| Interfaz | 🟠 Funcional | Funciona, pero tiene el aspecto genérico que comentas → ver [propuesta_rediseno.md](propuesta_rediseno.md) |
| Documentación | 🟠 | Abundante, pero con afirmaciones no verificadas tras la última sesión |

**Madurez estimada**: un prototipo funcional avanzado (~70 % de lo que pide el dossier v3 para uso personal). Lo
que falta no es arquitectura, sino **datos fiables** (convenios, sentencias), **validación jurídica** de los YAML y
**pulido de producto** (interfaz, exportar, borrar consultas).

---

## 5. Recomendaciones priorizadas

### Ahora (antes de confirmar el trabajo de Argon)
1. Revertir o corregir `boletin_ref` y `codigo_regcon` en `data/convenios_seed.yaml` (§3.1).
2. Arreglar los dos scripts y añadir tests de humo; meter `scripts/` en `mypy` (§3.2).
3. Acotar `buscar_en_vigentes` a convenios vigentes y al convenio del caso (§3.3).
4. Ajustar los *fallbacks* de `agy_gemini_flash` y quitar el duplicado de Gemini API (§3.6).
5. Corregir la documentación falsa (latencia `high`, ids de Anthropic, «✅ Hecho» de los scripts) (§3.5).
6. Confirmar en **varios commits temáticos** (arranque · proveedores HTTP · convenios · documentación), no en uno.

### Pronto
7. Medir en vivo la latencia de `gemini-3.8-flash-high` con un prompt de Magistrado real. Si supera los 180 s, usar
   `medium` en Eco o subir el *timeout* solo para ese rol.
8. Revisar el texto MASC contra la LO 1/2025 y añadir golden tests de excepciones (§3.4).
9. Separar «restablecer perfiles» de «restablecer modelos y proveedores» (§3.7).
10. Test `live` que valide los títulos BOE del seed de convenios.

### Producto (a tu ritmo)
11. **Rediseño de la interfaz** según [propuesta_rediseno.md](propuesta_rediseno.md).
12. Exportar el dictamen (Markdown o impresión a PDF) y borrar consultas del historial.
13. «Biblioteca»: subir sentencias y convenios desde la web, siguiendo el modelo de *fuentes* de NotebookLM (encaja
    con el rediseño).
14. Embeddings locales opcionales (p. ej. un modelo ONNX pequeño) para tener búsqueda vectorial sin clave de API.
15. Validación jurídica profesional de `plazos.yaml`, `postulacion.yaml` y `catalogo_materias.yaml` si el uso deja
    de ser estrictamente personal.

### Lección de proceso
Argon trabaja rápido y deja todo «en verde», pero **verde no significa correcto**: los tests no cubren datos
externos ni scripts. Para futuras sesiones con cualquier agente: (a) todo dato con referencia externa (BOE, REGCON,
ids de modelo) se verifica contra la fuente en la misma sesión, y (b) todo script nuevo lleva al menos un test de
humo.

---

## 6. Estado tras las correcciones (24-10-2026, misma sesión)

Todo lo de §5 «Ahora» y «Pronto» está hecho, más dos fallos nuevos encontrados al probar en vivo. Cada dato se ha
comprobado contra su fuente en esta sesión.

| Problema | Corrección | Cómo se ha verificado |
|---|---|---|
| §3.1 Referencias BOE inventadas | Seed reescrito con las 10 referencias reales y sus códigos (el del metal también era erróneo: `…011900`, no `…011981`). El importador verifica cada documento antes de indexar (`connectors/convenios_boe.py`) | Título y «Código de convenio n.º» leídos del XML del BOE; test `live` (10/10); los 10 convenios indexados en `data/local` (10 versiones, 1.054 artículos; los números repetidos dentro de un texto, p. ej. en anexos, se guardan una sola vez) |
| §3.2 Scripts rotos | Reescritos con `storage.database.open_database` y los campos reales; `scripts/` entra en `mypy` | Tests de humo (`tests/unit/test_scripts.py`); ejecución real de ambos |
| §3.3 Convenios sin acotar | El triaje elige el convenio **de una lista cerrada** de convenios indexados (un código inventado se descarta) y la ingesta busca solo en la versión vigente de ese convenio | Tests de repositorio y de triaje; consulta laboral en vivo (ver abajo) |
| §3.4 Texto MASC | Redactado contra los arts. 2, 5 y 10 de la LO 1/2025 (qué cuenta como intento, cómo se acredita, plazo de 30 días) sin prometer borradores | Texto leído del BOE consolidado (BOE-A-2025-76); golden tests |
| §3.5 «Latencia en high corregida» | **Medido**: `gemini-3.8-flash-high` falla 3 de 3 veces con un prompt de Magistrado (intenta ejecutar un comando, se le deniega, respuesta vacía). `medium`: 51 s. `gemini-4-argon-high`: 46 s. Eco pasa a `medium` | Llamadas reales a Antigravity |
| Nuevo: respuesta vacía abortaba la consulta | `EmptyResponse` (degradable): el router pasa al siguiente modelo | Test de parser |
| §3.6 Fallbacks | Flash → Claude Sonnet y GPT-OSS en Antigravity → Claude CLI → Gemini API; duplicado eliminado; RPD 20 | Tests del router |
| Ids de la API de Anthropic | `claude-sonnet-5-5` / `claude-opus-5-5` | Lista oficial de modelos vigente |
| §3.7 «Restablecer» borraba modelos | Separado en `DELETE /api/ajustes/perfiles` y `DELETE /api/ajustes/modelos` | Test de ajustes |
| TOML sin escape, atributo privado | Escape JSON-compatible; `GeminiClient.set_api_key` (además, la clave nueva ya no se ignoraba por el cliente cacheado) | Test de ajustes |
| Nuevo: «1786 días hábiles» con 1785 naturales | En plazos de meses o años el campo «hábiles» devolvía naturales. Ahora solo se informa en plazos de días hábiles, y la interfaz indica que es a la fecha del análisis | Golden test; visto en la interfaz |
| Rediseño | Implementado (R0–R4 de la propuesta): ver [propuesta_rediseno.md](propuesta_rediseno.md) | Build, E2E y revisión visual en claro, oscuro y móvil |

### Verificación final
| Comprobación | Resultado |
|---|---|
| `pytest` | 250 en verde |
| `pytest -m e2e` (navegador real) | 4 en verde |
| `pytest -m live tests/contract/test_live_convenios_boe.py` | 10 en verde |
| `ruff`, `ruff format`, `mypy --strict` (ahora 42 ficheros, con `scripts/`) | En verde |
| `tsc`, `vitest`, `npm run build` | En verde |
| Consulta real en modo Eco (fianza, Madrid) desde el navegador | Certificada en ~3 min; citas abiertas en el panel con el pasaje resaltado |
| Consulta laboral real en modo Eco por la API (camarero sancionado por impuntualidad) | Certificada en 136 s; el triaje eligió el ALEH VI y el dictamen cita sus arts. 38, 39 y 41 verificados. Antes de afinar la búsqueda (usar los términos jurídicos del triaje en vez del resumen) recuperaba artículos de clasificación profesional, irrelevantes |

### Lo que sigue pendiente
- Los convenios se indexan con su texto original: las modificaciones posteriores (actas, revisiones salariales) no se
  integran. El importador las lista.
- Si en un asunto laboral no se identifica el convenio, se avisa pero no se pregunta (mejora en la hoja de ruta).
- Validación jurídica profesional de los YAML (plazos, postulación, materias): sigue pendiente.
- Los ids de modelo de OpenAI, xAI, DeepSeek, Mistral y OpenRouter no están verificados (proveedores desactivados).
