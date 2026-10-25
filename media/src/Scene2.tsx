import { AbsoluteFill, Easing, Interactive, interpolate, useCurrentFrame } from "remotion";
import { C, sans } from "./theme";

const OUT = Easing.bezier(0.2, 0, 0, 1);
const FASES = [
  { t: "Entendiendo tu caso", at: 4 },
  { t: "Buscando en el BOE y en la jurisprudencia", at: 15 },
  { t: "Enfrentando los argumentos de ambas partes", at: 27 },
];
const ROLES = ["Defensa", "Contraparte", "Magistrado"];

export const Scene2: React.FC = () => {
  const frame = useCurrentFrame();
  const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
  return (
    <AbsoluteFill
      name="Placa 2"
      style={{
        backgroundColor: C.bg,
        fontFamily: sans,
        alignItems: "center",
        justifyContent: "center",
        opacity: interpolate(frame, [0, 5, 54, 60], [0.0, 1, 1, 0], clamp),
      }}
    >
      <div style={{ width: 1100 }}>
        <Interactive.Div
          name="Pregunta"
          style={{
            alignSelf: "flex-end",
            marginLeft: "auto",
            width: "fit-content",
            background: C.surface2,
            color: C.text,
            fontSize: 30,
            padding: "20px 34px",
            borderRadius: "36px 36px 8px 36px",
            marginBottom: 64,
            translate: interpolate(frame, [0, 14], ["0px 30px", "0px 0px"], { ...clamp, easing: OUT }),
          }}
        >
          Me han despedido estando de baja médica, me entregaron la carta ayer.
        </Interactive.Div>

        {FASES.map((f, i) => {
          const o = interpolate(frame, [f.at, f.at + 8], [0, 1], { ...clamp, easing: OUT });
          const activa = frame >= f.at && (i === FASES.length - 1 || frame < FASES[i + 1].at);
          const hecha = i < FASES.length - 1 && frame >= FASES[i + 1].at;
          return (
            <div key={f.t} style={{ display: "flex", alignItems: "center", gap: 28, marginBottom: 30, opacity: o, translate: `0px ${(1 - o) * 20}px` }}>
              <div style={{ width: 40, height: 40, borderRadius: 20, background: hecha ? C.accent : C.accentContainer, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                {hecha ? (
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke={C.onAccent} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12l5 5 9-10" /></svg>
                ) : (
                  <div style={{ width: 14, height: 14, borderRadius: 7, background: C.accent, scale: 0.8 + 0.2 * Math.sin(frame / 3) }} />
                )}
              </div>
              <div style={{ fontSize: 46, letterSpacing: "-0.02em", color: activa || hecha ? C.text : C.text2 }}>{f.t}</div>
            </div>
          );
        })}

        <div style={{ display: "flex", gap: 20, marginTop: 44, marginLeft: 68 }}>
          {ROLES.map((r, i) => {
            const at = 38 + i * 5;
            const o = interpolate(frame, [at, at + 8], [0, 1], { ...clamp, easing: OUT });
            return (
              <Interactive.Div
                key={r}
                name={r}
                style={{
                  fontSize: 32,
                  color: C.onAccentContainer,
                  background: C.accentContainer,
                  borderRadius: 16,
                  padding: "14px 30px",
                  opacity: o,
                  translate: `0px ${(1 - o) * 16}px`,
                }}
              >
                {r}
              </Interactive.Div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};
