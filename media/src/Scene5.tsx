import { AbsoluteFill, Easing, Interactive, interpolate, useCurrentFrame } from "remotion";
import { C, sans } from "./theme";

const OUT = Easing.bezier(0.2, 0, 0, 1);
const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

const Fila: React.FC<{ at: number; texto: string; icono: React.ReactNode }> = ({ at, texto, icono }) => {
  const frame = useCurrentFrame();
  const o = interpolate(frame, [at, at + 8], [0, 1], { ...clamp, easing: OUT });
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 40, opacity: o, translate: `0px ${(1 - o) * 24}px` }}>
      <div style={{ width: 120, height: 120, borderRadius: 36, background: C.accentContainer, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
        {icono}
      </div>
      <div style={{ fontSize: 62, letterSpacing: "-0.02em", color: C.text, lineHeight: 1.2 }}>{texto}</div>
    </div>
  );
};

const svg = { width: 64, height: 64, viewBox: "0 0 24 24", fill: "none", stroke: C.accent, strokeWidth: 1.7, strokeLinecap: "round", strokeLinejoin: "round" } as const;

export const Scene5: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill
      name="Placa 5"
      style={{
        backgroundColor: C.bg,
        fontFamily: sans,
        alignItems: "center",
        justifyContent: "center",
        opacity: interpolate(frame, [0, 5, 29, 35], [0, 1, 1, 0], clamp),
      }}
    >
      <Interactive.Div name="Filas" style={{ display: "flex", flexDirection: "column", gap: 64, width: 1380 }}>
        <Fila
          at={2}
          texto="Tus datos personales se seudonimizan antes de enviarse."
          icono={<svg {...svg}><path d="M12 3l8 3v6c0 4.5-3.2 8-8 9-4.8-1-8-4.5-8-9V6l8-3z" /><path d="M9 12l2 2 4-4" /></svg>}
        />
        <Fila
          at={12}
          texto="Tus consultas se guardan cifradas en tu ordenador."
          icono={<svg {...svg}><rect x="5" y="11" width="14" height="10" rx="2.5" /><path d="M8 11V8a4 4 0 018 0v3" /></svg>}
        />
      </Interactive.Div>
    </AbsoluteFill>
  );
};
