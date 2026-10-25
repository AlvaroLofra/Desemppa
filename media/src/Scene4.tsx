import { AbsoluteFill, Easing, Interactive, interpolate, useCurrentFrame } from "remotion";
import { C, sans } from "./theme";

const OUT = Easing.bezier(0.2, 0, 0, 1);
const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const PALABRAS = ["Los", "plazos", "los", "calcula", "el", "código,", "no", "el", "modelo."];

export const Scene4: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill
      name="Placa 4"
      style={{
        backgroundColor: C.bg,
        fontFamily: sans,
        alignItems: "center",
        justifyContent: "center",
        opacity: interpolate(frame, [0, 5, 39, 45], [0, 1, 1, 0], clamp),
      }}
    >
      <Interactive.Div
        name="Tarjeta"
        style={{
          width: 1380,
          background: C.surface,
          borderRadius: 48,
          boxShadow: C.shadow,
          padding: "72px 80px",
          display: "flex",
          alignItems: "center",
          gap: 64,
          opacity: interpolate(frame, [0, 12], [0, 1], { ...clamp, easing: OUT }),
          translate: interpolate(frame, [0, 12], ["0px 40px", "0px 0px"], { ...clamp, easing: OUT }),
        }}
      >
        <div
          style={{
            width: 190,
            height: 190,
            borderRadius: 56,
            background: C.accentContainer,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
            scale: interpolate(frame, [2, 14], [0.6, 1], { ...clamp, easing: Easing.bezier(0.34, 1.56, 0.64, 1) }),
          }}
        >
          <svg width="104" height="104" viewBox="0 0 24 24" fill="none" stroke={C.accent} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="4.5" width="18" height="16" rx="3" />
            <path d="M3 9.5h18M8 2.5v4M16 2.5v4" />
            <path d="M8.5 15l2.5 2.5 4.5-5" />
          </svg>
        </div>
        <div>
          <div style={{ fontSize: 76, lineHeight: 1.15, letterSpacing: "-0.03em", color: C.text }}>
            {PALABRAS.map((p, i) => {
              const at = 8 + i * 2.5;
              const o = interpolate(frame, [at, at + 7], [0, 1], { ...clamp, easing: OUT });
              return (
                <span key={i} style={{ display: "inline-block", opacity: o, translate: `0px ${(1 - o) * 18}px`, marginRight: "0.28em" }}>
                  {p}
                </span>
              );
            })}
          </div>
          <div style={{ fontSize: 32, color: C.text2, marginTop: 28, opacity: interpolate(frame, [30, 38], [0, 1], { ...clamp, easing: OUT }) }}>
            Motor de calendario determinista
          </div>
        </div>
      </Interactive.Div>
    </AbsoluteFill>
  );
};
