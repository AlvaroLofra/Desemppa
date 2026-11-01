import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { C } from "./theme";
import { Icono, Lienzo, Rev, rev } from "./ui";
import { CONSULTA } from "./datos";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

export const Scene1: React.FC = () => {
  const frame = useCurrentFrame();
  const chars = Math.floor(interpolate(frame, [18, 108], [0, CONSULTA.length], clamp));
  const escribiendo = chars < CONSULTA.length;
  const caret = escribiendo || Math.floor(frame / 10) % 2 === 0 ? 1 : 0;
  const listo = frame >= 108;
  const pulso = listo ? 1 + 0.08 * Math.max(0, Math.sin((frame - 108) / 4)) : 1;

  return (
    <Lienzo name="Placa 1 · Pregunta" style={{ alignItems: "center", justifyContent: "center" }}>
      <div style={{ width: 1440 }}>
        <Rev at={0} dy={28} d={18}>
          <div style={{ fontSize: 100, fontWeight: 400, letterSpacing: "-0.03em", textAlign: "center", marginBottom: 20 }}>
            ¿En qué te puedo ayudar?
          </div>
        </Rev>
        <Rev at={8} dy={16}>
          <div style={{ fontSize: 34, color: C.text2, textAlign: "center", marginBottom: 56 }}>
            Analizo tu caso con la ley vigente y compruebo cada cita contra el texto oficial.
          </div>
        </Rev>
        <div
          style={{
            background: C.surface,
            border: `1.5px solid ${C.outline}`,
            borderRadius: 56,
            boxShadow: C.shadowBig,
            padding: "48px 60px 40px",
            opacity: rev(frame, 6, 18),
            translate: `0px ${(1 - rev(frame, 6, 18)) * 60}px`,
          }}
        >
          <div style={{ fontSize: 42, lineHeight: 1.45, minHeight: 4 * 61 }}>
            {CONSULTA.slice(0, chars)}
            <span style={{ opacity: caret, color: C.accent }}>|</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", marginTop: 24 }}>
            <Icono n="clip" size={44} color={C.text2} />
            <div
              style={{
                marginLeft: "auto",
                width: 84,
                height: 84,
                borderRadius: 42,
                background: listo ? C.accent : C.surface2,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                scale: pulso,
              }}
            >
              <Icono n="arriba" size={44} color={listo ? C.onAccent : C.text3} sw={2.4} />
            </div>
          </div>
        </div>
      </div>
    </Lienzo>
  );
};
