# Valoración de Viabilidad Técnica, Económica y Estrategia de Evolución

Actualizado: 24-10-2026 · Alcance actual elegido: **Opción A (Proyecto Personal 100 % Local sobre Suscripciones Activas)**.

---

## 1. Viabilidad técnica

La arquitectura implementada en Iuris-IA supera ampliamente a los asistentes legales genéricos basados en un único prompt o RAG simple:

1. **Separación estricta entre Razonamiento (LLM) y Determinismo (Python)**:
   - El LLM **nunca** calcula fechas ni elige qué artículos existen: el calendario judicial (`core/calendar_engine.py`), la vigencia temporal de cada artículo del BOE (`core/temporal_sync.py`) y las reglas de abogado/procurador (`core/postulacion_rules.py`) son 100 % deterministas y están cubiertos por 67 *golden tests* (que comprueban el código, no la corrección jurídica de las reglas).
2. **Juicio Contradictorio de 4 Fases (`core/orchestrator.py`)**:
   - **Fase 1 (Triaje)** → **Fase 2 (Ingesta verificada BOE + Jurisprudencia + Convenios)** → **Fase 3 (Debate paralelo Defensa vs. Contraparte + Resolución del Magistrado)** → **Fase 4 (Guardarraíles G1–G10 + Verificación NLI)**.
   - El guardarraíl **G2 (`core/validators.py`)** exige que cada cita legal tenga una coincidencia literal (`rapidfuzz >= 92 %`) contra el texto descargado del BOE o del convenio/sentencia. Esto impide que el modelo invente citas, pero **no** protege frente a datos de partida erróneos: si una referencia del catálogo apunta a otro documento, la cita «coincidirá» con el texto equivocado. Por eso los datos de partida se verifican contra la fuente (ver [informe_revision_2026-10-24.md](informe_revision_2026-10-24.md)).
3. **Adaptador Universal Multi-Compañía y Multi-Modalidad (`core/providers/`)**:
   - Soporta simultáneamente **Planes de Suscripción por CLI** (`antigravity_cli`, `claude_cli`, `codex_cli`) y **APIs HTTP con clave cifrada en DPAPI** (`gemini_api`, `anthropic_api`, `openai_api`, `xai_api`, `deepseek_api`, `mistral_api`, `openrouter_api`), con *circuit breaker* y degradación automática entre proveedores.

---

## 2. Viabilidad económica para uso personal

### Coste Marginal: **0,00 € por consulta**
El sistema está configurado por defecto para operar íntegramente sobre tus dos suscripciones personales ya contratadas (~20 €/mes cada una), sin requerir `GEMINI_API_KEY` ni pagos por token:

| Suscripción Activa | Canal en Iuris-IA | Modelos Utilizados | Rol Principal |
|---|---|---|---|
| **Google AI Pro (~20 €/mes)** | `antigravity_cli` (`agy`) | `gemini-3.8-flash-{low\|medium\|high}`, `gemini-4-argon-{low\|medium\|high}`, `claude-sonnet-5-5`, `claude-opus-5-5` | Todo el modo **Eco**, tareas de volumen en **Equilibrado/Pro**, y **Magistrado en modo Pro (`gemini-4-argon-high`)** |
| **Claude Pro (~20 €/mes)** | `claude_cli` (`claude`) | `sonnet`, `opus`, `haiku` (`low\|medium\|high`) | **Magistrado** en modo **Equilibrado** y **Defensa/Contraparte** en modo **Pro** |

- Si una suscripción alcanza su límite, el `CircuitBreaker` (`core/circuit_breaker.py`) desvía las siguientes llamadas a la alternativa configurada. Si el fallo llega a mitad de una respuesta, solo los pasos que devuelven JSON se repiten con otro modelo; el resto se reporta como error.

---

## 3. ¿Podría Comercializarse en el Futuro? (Hoja de Ruta si Decides Lanzarlo)

Actualmente el proyecto se mantiene como **herramienta de uso personal** (Opción A). Si más adelante decides comercializarlo o publicarlo, ten en cuenta estas tres reglas críticas:

### 3.1 Qué prohíbe comercializarlo tal cual está hoy (Modalidad B2C)
1. **Términos de Servicio de los CLIs (`agy` y `claude`)**: Las suscripciones personales de 20 €/mes prohíben revender su cuota a terceros detrás de un servidor multiusuario. Para comercializarlo como SaaS deberías cambiar en la página **Modelos** los perfiles a **APIs por Clave** (OpenAI, Anthropic, Google Vertex/AI Studio, DeepSeek, Mistral), algo para lo que la aplicación **ya ha quedado preparada** con el nuevo adaptador HTTP universal.
2. **Restricción legal del CENDOJ (art. 507 LOPJ)**: Está prohibido redistribuir comercialmente sentencias descargadas de CENDOJ sin licencia de reutilización del CGPJ.
3. **Riesgo de Asesoramiento Jurídico B2C**: Vender dictámenes legales directamente a consumidores finales sin supervisión de un abogado colegiado conlleva riesgos de responsabilidad civil y del Reglamento Europeo de IA (AI Act).

### 3.2 Las 2 Vías Comerciales Viables a Futuro
1. **Vía 1 — Herramienta B2B "Copiloto de Triaje y Verificación BOE" para Abogados, Gestorías y Sindicatos (La más rentable)**:
   - Se vende como software de productividad para profesionales colegiados (29 €–79 €/mes por puesto, usando APIs empresariales o BYOK — *Bring Your Own Key*).
   - El abogado o graduado social es quien valida y firma el escrito final, eliminando el riesgo de intrusismo y descargando la responsabilidad profesional en su seguro colegial.
2. **Vía 2 — Código Abierto (Open Source / GitHub) + BYOK Local**:
   - Publicar el motor y la interfaz web sin bases de datos privativas (el usuario descarga sus propios datos del BOE en vivo y configura sus propios CLIs o API keys locales).
