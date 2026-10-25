import { AbsoluteFill, Easing, Interactive, interpolate, useCurrentFrame } from "remotion";
import { C, sans, serif } from "./theme";

const OUT = Easing.bezier(0.2, 0, 0, 1);
const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

// Literal de la API de datos abiertos del BOE (BOE-A-2015-11430, bloque a55, apartado 3), comprobado el 25-10-2026.
const PRE = "El despido será calificado como ";
const RES = "procedente, improcedente o nulo.";

export const Scene3: React.FC = () => {
  const frame = useCurrentFrame();
  const sweep = interpolate(frame, [22, 38], [0, 100], { ...clamp, easing: Easing.bezier(0.4, 0, 0.2, 1) });
  const pop = interpolate(frame, [40, 48], [0, 1], { ...clamp, easing: Easing.bezier(0.34, 1.56, 0.64, 1) });
  return (
    <AbsoluteFill
      name="Placa 3"
      style={{
        backgroundColor: C.bg,
        fontFamily: sans,
        alignItems: "center",
        justifyContent: "center",
        opacity: interpolate(frame, [0, 5, 54, 60], [0, 1, 1, 0], clamp),
      }}
    >
      <div style={{ width: 1280 }}>
        <Interactive.Div
          name="Fase"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 24,
            fontSize: 46,
            letterSpacing: "-0.02em",
            color: C.text,
            marginBottom: 56,
            opacity: interpolate(frame, [0, 10], [0, 1], { ...clamp, easing: OUT }),
          }}
        >
          <div style={{ width: 40, height: 40, borderRadius: 20, background: pop > 0.5 ? C.accent : C.accentContainer, display: "flex", alignItems: "center", justifyContent: "center" }}>
            {pop > 0.5 ? (
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke={C.onAccent} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12l5 5 9-10" /></svg>
            ) : (
              <div style={{ width: 14, height: 14, borderRadius: 7, background: C.accent, scale: 0.8 + 0.2 * Math.sin(frame / 3) }} />
            )}
          </div>
          Verificando cada cita contra el texto oficial
        </Interactive.Div>

        <Interactive.Div
          name="Tarjeta"
          style={{
            background: C.surface,
            borderRadius: 48,
            padding: "52px 64px 48px",
            boxShadow: C.shadow,
            opacity: interpolate(frame, [8, 22], [0, 1], { ...clamp, easing: OUT }),
            translate: interpolate(frame, [8, 22], ["0px 40px", "0px 0px"], { ...clamp, easing: OUT }),
          }}
        >
          <div style={{ fontSize: 28, fontWeight: 500, color: C.text2, marginBottom: 28 }}>Fundamentos verificados</div>
          <div style={{ fontFamily: serif, fontSize: 58, lineHeight: 1.4, color: C.text }}>
            {PRE}
            <span
              style={{
                backgroundImage: `linear-gradient(${C.highlight}, ${C.highlight})`,
                backgroundRepeat: "no-repeat",
                backgroundSize: `${sweep}% 100%`,
                padding: "0 6px",
                margin: "0 -6px",
              }}
            >
              {RES}
            </span>
          </div>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 40 }}>
            <div style={{ fontSize: 28, color: C.text2 }}>Estatuto de los Trabajadores, art. 55.3 · BOE</div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                fontSize: 28,
                fontWeight: 500,
                color: C.success,
                opacity: pop,
                scale: 0.8 + 0.2 * pop,
              }}
            >
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke={C.success} strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10" /><path d="M7.5 12.5l3 3 6-7" /></svg>
              Cita verificada
            </div>
          </div>
        </Interactive.Div>
      </div>
    </AbsoluteFill>
  );
};
