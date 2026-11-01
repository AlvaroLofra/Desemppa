import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { C } from "./theme";
import { Boton, Eyebrow, Lienzo, Rev, rev } from "./ui";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

// Preguntas reales de la app para un despido (eventos `clarification_needed` de data/local/local_cache.db).
const Q1 = {
  texto: "¿Firmaste la carta de despido haciendo constar «no conforme» y la fecha?",
  motivo: "si la firma acredita la fecha fehaciente de notificación, queda determinada con certeza la base para el cómputo de plazos de reclamación.",
};
const Q2 = {
  texto: "¿En qué municipio está el juzgado o el organismo (o, si no lo sabes, tu municipio)?",
  motivo: "festivos locales del calendario",
};

export const Scene3: React.FC = () => {
  const frame = useCurrentFrame();
  const sel = frame >= 96;
  const muni = "Sevilla (Sevilla)".slice(0, Math.floor(interpolate(frame, [104, 126], [0, 17], clamp)));

  return (
    <Lienzo name="Placa 3 · Aclaraciones" style={{ alignItems: "center", justifyContent: "center" }}>
      <div style={{ width: 1520 }}>
        <Eyebrow>Aclaraciones</Eyebrow>
        <Rev at={4}>
          <div style={{ fontSize: 80, letterSpacing: "-0.03em", lineHeight: 1.1, marginBottom: 40 }}>Te pregunta lo que necesita saber</div>
        </Rev>
        <div style={{ background: C.surface, borderRadius: 48, padding: "44px 56px 44px", opacity: rev(frame, 10, 16), translate: `0px ${(1 - rev(frame, 10, 16)) * 40}px` }}>
          <div style={{ fontSize: 40 }}>Antes de seguir, necesito algunos datos para no equivocarme:</div>
          <div style={{ fontSize: 28, color: C.text2, marginTop: 10, marginBottom: 34 }}>
            Cuanto más precisas sean tus respuestas, más fiable será el resultado. Si no sabes algo, dilo: no se supondrá.
          </div>

          <Rev at={26} dy={16} style={{ marginBottom: 30 }}>
            <div style={{ fontSize: 34 }}>{Q1.texto}</div>
            <div style={{ fontSize: 26, color: C.text3, margin: "6px 0 16px" }}>Por qué lo pregunto: {Q1.motivo}</div>
            <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
              <Boton tipo={sel ? "tonal" : "outline"} size={30}>Sí</Boton>
              <Boton tipo="outline" size={30}>No</Boton>
              <div style={{ fontSize: 26, color: C.text2, marginLeft: 12 }}>No lo sé</div>
            </div>
          </Rev>

          <Rev at={60} dy={16} style={{ marginBottom: 34 }}>
            <div style={{ fontSize: 34 }}>{Q2.texto}</div>
            <div style={{ fontSize: 26, color: C.text3, margin: "6px 0 14px" }}>Por qué lo pregunto: {Q2.motivo}</div>
            <div style={{ width: 640, border: `2px solid ${frame >= 104 ? C.accent : C.outline}`, borderRadius: 16, padding: "14px 22px", fontSize: 32, minHeight: 30, background: C.bg }}>
              {muni || <span style={{ color: C.text3 }}>Municipio del juzgado u organismo</span>}
            </div>
          </Rev>

          <Rev at={40} dy={10}>
            <Boton tipo="primario" size={32}>Continuar</Boton>
          </Rev>
        </div>
      </div>
    </Lienzo>
  );
};
