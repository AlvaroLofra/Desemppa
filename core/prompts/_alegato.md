Responde SOLO con un objeto JSON:
{
  "rol": "{rol}",
  "pretension": "qué pide esta parte, en una frase",
  "cuestiones": [
    {"id": "C1", "argumentos": [
      {"afirmacion": "argumento jurídico concreto",
       "citas": [{"source_id": "<id exacto de una FUENTE>", "verbatim_quote": "frase copiada LITERALMENTE de esa fuente, mínimo 40 caracteres"}]}
    ]}
  ],
  "importe_reclamado_eur": número | null
}

Reglas de citación (se verifican automáticamente y las citas falsas se descartan):
- Solo puedes citar las FUENTES del dossier, por su `source_id` exacto.
- `verbatim_quote` debe ser una copia literal de un fragmento de esa fuente (mínimo 40 caracteres). No parafrasees dentro de la cita.
- No inventes artículos, sentencias ni importes. Para conceptos indeterminados ("desgaste normal", "pequeñas reparaciones") solo puedes fijar cuantías si una sentencia del dossier lo hace.
- Usa los ids de cuestión C1, C2... que se listan en "CUESTIONES LITIGIOSAS".
- Nunca expreses probabilidades ni porcentajes de éxito.
