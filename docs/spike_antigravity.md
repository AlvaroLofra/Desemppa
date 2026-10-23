# Spike — CLI de Antigravity (`agy`) como proveedor (2026-10-23)

`agy` (en `%LOCALAPPDATA%\agy\bin\agy.exe`) usa la suscripción Google AI Pro del usuario, no el free tier de la API.

## Modelos (`agy models`)
`gemini-3.8-flash-low|medium|high`, `claude-sonnet-4-6`, `claude-opus-4-6-thinking`, `gpt-oss-120b-medium`.
El nivel de razonamiento de Gemini va en el nombre del modelo.

## Invocación no interactiva
```
agy --model <id> --input-format stream-json --output-format stream-json --disable-slash-commands
    --print-timeout <N>s [--json-schema <fichero>] -p=
```
- **Prompt por stdin** (sin límite de argv): una línea NDJSON
  `{"event":"user","message":{"role":"user","content":"<texto>"}}`.
  `-p=-` NO lee stdin (toma "-" como prompt literal) y `-p` sin `=` se come el siguiente flag.
- No hay flag de system prompt: se antepone al contenido.
- Salida NDJSON: `init` → `step_update` (con `text_delta` en `step_type: agent_response`; `tool` si intenta una
  herramienta; `finish`) → `result` con `status`, `response`, `usage`, opcional `structured_output` (con
  `--json-schema`) y `denied_actions`.
- **Con `--json-schema` el `response` contiene el JSON dos veces** (texto + salida estructurada): usar
  `structured_output`.
- **`--print-timeout` agotado devuelve `status: SUCCESS` con `response` vacío** y un aviso en stderr: hay que tratarlo
  como timeout.

## Seguridad
En modo headless las herramientas con permiso (p. ej. `write_file`) se **deniegan automáticamente**
(`denied_actions`, sin fichero creado). Se ejecuta con `cwd` en un directorio vacío; si aparece un paso `tool`,
el adaptador lo registra como aviso.

## Latencias medidas
| Modelo | Prompt | Tiempo total |
|---|---|---|
| 3.8-flash-low | "hola" | 3,7 s |
| 3.8-flash-medium | 1 frase | 11 s (4,6 s de modelo) |
| 3.8-flash-high | 1 frase | 13 s (9,2 s de modelo) |
| 3.8-flash-low | 32 KB + json-schema | 13 s |
| 3.8-flash-medium | 32 KB + json-schema | 48 s (3.725 tokens de razonamiento) |
| 3.8-flash-high | 32 KB | **> 240 s (sin terminar)** |

Conclusión: 3.8 Flash vía Antigravity es viable y rápido en low/medium; **high con prompts grandes no es usable**
(el adaptador limita Gemini vía Antigravity a low/medium). Comparado con la API gratuita (128 s y 20 peticiones/día),
es el canal preferente para 3.8 Flash.

## Pendiente
- Mensaje exacto de cuota agotada de la suscripción (no se ha alcanzado).
- Términos de uso: es tu suscripción personal y se usa en local; revisa la configuración de privacidad de Antigravity.
