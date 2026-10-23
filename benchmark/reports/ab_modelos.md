# A/B de modelos — 2026-10-23 (2 casos sintéticos, sin permutar)

Muestra mínima (2 casos escritos a mano): sirve para comparar canales y latencias, **no** para medir calidad
jurídica. La comparación de calidad necesita los 25 casos reales.

| Configuración | Certificadas | Media rúbrica | Tiempo total (2 casos) | Notas |
|---|---|---|---|---|
| Eco · 3.8 Flash vía **API gratuita** (22-oct) | 1/1 (el 2.º no terminó) | 90 | ~25 min | 128–210 s por llamada; cuota de 20/día agotada |
| Eco · 3.5 Flash vía API (22-oct) | 2/2 | 95,0 | ~6 min | cuota diaria de 3.5 agotada a mitad: cayó a 3.5-Lite |
| **Eco · 3.8 Flash vía Antigravity** (23-oct) | **2/2** | **96,7** | 7 min | Defensa 28–33 s, Contraparte 43–52 s, Magistrado 44–127 s |
| Equilibrado · Magistrado Claude Sonnet | 1/2 | 58,6 | 4 min | Claude Code sin sesión → **Sonnet 4.6 vía Antigravity** (72 s); el caso fallido fue un 503 de la API de Gemini a mitad del triaje (corregido: ahora se repite con otro modelo) |

Puntuación de "sin alucinación" (citas verificadas a la primera, sobre 15) en el caso de la fianza: 3.8 vía
Antigravity 10,0; 3.5 vía API 7,5. En el caso del despido, ambos 15/15.

Decisión: se mantienen los perfiles por defecto (3.8 Flash vía Antigravity para Defensa, Contraparte y Magistrado
en Eco; Gemini API solo para triaje, cribado y NLI). Repetir con los 25 casos reales y con Claude Code con sesión.
