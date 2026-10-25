import { AbsoluteFill, Easing, Interactive, interpolate, useCurrentFrame } from "remotion";
import { C, sans } from "./theme";

const TEXTO = "Me han despedido estando de baja médica, me entregaron la carta ayer.";
const OUT = Easing.bezier(0.2, 0, 0, 1);

export const Scene1: React.FC = () => {
  const frame = useCurrentFrame();
  const chars = Math.floor(
    interpolate(frame, [20, 54], [0, TEXTO.length], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
  );
  const caret = chars < TEXTO.length || Math.floor(frame / 8) % 2 === 0 ? 1 : 0;

  return (
    <AbsoluteFill name="Placa 1" style={{ backgroundColor: C.bg, opacity: interpolate(frame, [54, 60], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }), fontFamily: sans, alignItems: "center", justifyContent: "center" }}>
      <div style={{ width: 1360 }}>
        <Interactive.Div
          name="Título"
          style={{
            fontSize: 96,
            fontWeight: 400,
            letterSpacing: "-0.03em",
            textAlign: "center",
            color: C.text,
            marginBottom: 56,
            opacity: interpolate(frame, [0, 16], [0, 1], { extrapolateRight: "clamp", easing: OUT }),
            translate: interpolate(frame, [0, 16], ["0px 24px", "0px 0px"], { extrapolateRight: "clamp", easing: OUT }),
          }}
        >
          ¿En qué te puedo ayudar?
        </Interactive.Div>
        <Interactive.Div
          name="Compositor"
          style={{
            background: C.surface,
            border: `1.5px solid ${C.outline}`,
            borderRadius: 56,
            boxShadow: C.shadowBig,
            padding: "44px 56px",
            minHeight: 250,
            display: "flex",
            alignItems: "flex-end",
            justifyContent: "space-between",
            gap: 32,
            opacity: interpolate(frame, [6, 22], [0, 1], { extrapolateRight: "clamp", extrapolateLeft: "clamp", easing: OUT }),
            translate: interpolate(frame, [6, 22], ["0px 60px", "0px 0px"], { extrapolateRight: "clamp", extrapolateLeft: "clamp", easing: OUT }),
          }}
        >
          <div style={{ fontSize: 48, lineHeight: 1.4, color: C.text, flex: 1 }}>
            {TEXTO.slice(0, chars)}
            <span style={{ opacity: caret, color: C.accent }}>|</span>
          </div>
          <div
            style={{
              width: 76,
              height: 76,
              borderRadius: 38,
              background: C.accent,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
              opacity: interpolate(frame, [50, 56], [0.35, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
            }}
          >
            <svg width="38" height="38" viewBox="0 0 24 24" fill="none" stroke={C.onAccent} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 19V5M5 12l7-7 7 7" />
            </svg>
          </div>
        </Interactive.Div>
      </div>
    </AbsoluteFill>
  );
};
