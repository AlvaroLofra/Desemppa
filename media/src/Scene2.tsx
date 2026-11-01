import React from "react";
import { Easing, interpolate, useCurrentFrame } from "remotion";
import { C } from "./theme";
import { Eyebrow, Icono, Lienzo, Rev, rev } from "./ui";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

export const Scene2: React.FC = () => {
  const frame = useCurrentFrame();
  // El archivo cae sobre el compositor (frames 24→44) y queda como ficha.
  const caida = interpolate(frame, [24, 44], [0, 1], { ...clamp, easing: Easing.bezier(0.34, 1.3, 0.64, 1) });
  const dropzone = interpolate(frame, [18, 26, 44, 54], [0, 1, 1, 0], clamp);
  const foco = frame >= 20 && frame <= 48;

  return (
    <Lienzo name="Placa 2 · Documentos" style={{ alignItems: "center", justifyContent: "center" }}>
      <div style={{ width: 1440 }}>
        <Eyebrow>Tus documentos</Eyebrow>
        <Rev at={4}>
          <div style={{ fontSize: 88, letterSpacing: "-0.03em", lineHeight: 1.1, marginBottom: 48 }}>Añade tus documentos</div>
        </Rev>

        <div
          style={{
            background: C.surface,
            borderRadius: 56,
            boxShadow: C.shadowBig,
            padding: "40px 56px 36px",
            border: `3px solid ${foco ? C.accent : "transparent"}`,
            opacity: rev(frame, 6, 16),
          }}
        >
          <div style={{ height: 48, fontSize: 34, color: C.accent, opacity: dropzone }}>
            Suelta aquí contratos, nóminas, cartas o multas (PDF o TXT)
          </div>
          <div style={{ display: "flex", gap: 16, minHeight: 84 }}>
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 14,
                background: C.surface2,
                borderRadius: 24,
                padding: "16px 28px",
                fontSize: 36,
                opacity: caida,
                translate: `${(1 - caida) * 220}px ${(1 - caida) * -140}px`,
              }}
            >
              <Icono n="archivo" size={40} color={C.text2} />
              carta_despido.pdf
              <Icono n="x" size={30} color={C.text2} />
            </div>
          </div>
          <div style={{ fontSize: 36, color: C.text3, marginTop: 24, marginBottom: 28 }}>Describe tu caso con fechas e importes si los sabes</div>
          <div style={{ display: "flex", alignItems: "center" }}>
            <div style={{ borderRadius: 44, width: 84, height: 84, display: "flex", alignItems: "center", justifyContent: "center", background: foco ? C.accentContainer : "transparent" }}>
              <Icono n="clip" size={44} color={foco ? C.accent : C.text2} />
            </div>
            <div style={{ marginLeft: 20, fontSize: 30, color: C.text2 }}>Adjuntar documentos (PDF o TXT)</div>
          </div>
        </div>

        <Rev at={70} style={{ display: "flex", gap: 20, alignItems: "flex-start", marginTop: 40, fontSize: 31, lineHeight: 1.45, color: C.text2 }}>
          <div style={{ width: 34, height: 34, border: `3px solid ${C.outline}`, borderRadius: 8, flexShrink: 0, marginTop: 4 }} />
          <div>
            Permitir que el contenido de los próximos adjuntos (seudonimizado) se envíe a los modelos de IA.{" "}
            <span style={{ color: C.text }}>Si no lo marcas, los documentos solo se leen en tu equipo para clasificarlos.</span>
          </div>
        </Rev>
      </div>
    </Lienzo>
  );
};
