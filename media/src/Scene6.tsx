import { AbsoluteFill, Easing, Img, Interactive, interpolate, staticFile, useCurrentFrame } from "remotion";
import { C, sans } from "./theme";

const OUT = Easing.bezier(0.2, 0, 0, 1);
const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

export const Scene6: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill name="Placa 6" style={{ backgroundColor: C.bg, fontFamily: sans, alignItems: "center", justifyContent: "center" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 48 }}>
        <Interactive.Div
          name="Logo"
          style={{
            scale: interpolate(frame, [4, 20], [0.4, 1], { ...clamp, easing: Easing.bezier(0.34, 1.56, 0.64, 1) }),
            opacity: interpolate(frame, [4, 12], [0, 1], clamp),
          }}
        >
          <Img src={staticFile("icon.svg")} style={{ width: 240, height: 240, display: "block" }} />
        </Interactive.Div>
        <Interactive.Div
          name="Nombre"
          style={{
            fontSize: 190,
            fontWeight: 400,
            letterSpacing: "-0.04em",
            color: C.text,
            opacity: interpolate(frame, [10, 22], [0, 1], { ...clamp, easing: OUT }),
            translate: interpolate(frame, [10, 22], ["-40px 0px", "0px 0px"], { ...clamp, easing: OUT }),
          }}
        >
          Desemppa
        </Interactive.Div>
      </div>
      <Interactive.Div
        name="Aviso"
        style={{
          position: "absolute",
          bottom: 190,
          fontSize: 30,
          color: C.text2,
          opacity: interpolate(frame, [22, 32], [0, 1], { ...clamp, easing: OUT }),
        }}
      >
        Información orientativa, no asesoramiento profesional.
      </Interactive.Div>
      <AbsoluteFill style={{ backgroundColor: "rgb(19,19,20)", opacity: interpolate(frame, [32, 40], [0, 1], clamp) }} />
    </AbsoluteFill>
  );
};
