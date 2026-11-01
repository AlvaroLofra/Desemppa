import React from "react";
import { Easing, Img, interpolate, staticFile, useCurrentFrame } from "remotion";
import { C } from "./theme";
import { Lienzo, Rev } from "./ui";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

export const Scene11: React.FC = () => {
  const frame = useCurrentFrame();
  const salida = interpolate(frame, [124, 150], [0, 1], clamp);
  return (
    <Lienzo name="Placa 11 · Cierre" style={{ alignItems: "center", justifyContent: "center" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 52 }}>
        <div
          style={{
            scale: interpolate(frame, [10, 34], [0.4, 1], { ...clamp, easing: Easing.bezier(0.34, 1.56, 0.64, 1) }),
            opacity: interpolate(frame, [10, 20], [0, 1], clamp),
          }}
        >
          <Img src={staticFile("icon.svg")} style={{ width: 250, height: 250, display: "block" }} />
        </div>
        <Rev at={22} dy={0} d={20} style={{ fontSize: 200, letterSpacing: "-0.04em", translate: "0px 0px" }}>Desemppa</Rev>
      </div>
      <Rev at={44} style={{ fontSize: 38, color: C.text2, marginTop: 36, textAlign: "center" }}>
        La ley vigente y cada cita, contrastadas con el texto oficial.
      </Rev>
      <Rev at={64} style={{ position: "absolute", bottom: 130, fontSize: 28, color: C.text3 }}>
        Información orientativa, no asesoramiento profesional.
      </Rev>
      <div style={{ position: "absolute", inset: 0, background: "rgb(19,19,20)", opacity: salida }} />
    </Lienzo>
  );
};
