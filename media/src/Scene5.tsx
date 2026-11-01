import React from "react";
import { Easing, Img, interpolate, staticFile, useCurrentFrame } from "remotion";
import { C, serif } from "./theme";
import { Eyebrow, Icono, Lienzo, Rev } from "./ui";
import { CITA_ET55 } from "./datos";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

export const Scene5: React.FC = () => {
  const frame = useCurrentFrame();
  const zoom = interpolate(frame, [30, 100], [1, 1.42], { ...clamp, easing: Easing.bezier(0.45, 0, 0.2, 1) });
  const marca = interpolate(frame, [70, 96], [0, 1], clamp);
  const W = 1120;
  const H = 740;
  const BARRA = 72;

  return (
    <Lienzo name="Placa 5 · Fuente BOE" style={{ alignItems: "center", justifyContent: "center" }}>
      <div style={{ width: 1720, display: "flex", gap: 64, alignItems: "center" }}>
        <div style={{ width: 540 }}>
          <Eyebrow>Legislación · BOE</Eyebrow>
          <Rev at={2}>
            <div style={{ fontSize: 76, letterSpacing: "-0.03em", lineHeight: 1.08 }}>Lee el artículo de verdad</div>
          </Rev>
          <Rev at={16} style={{ fontSize: 34, lineHeight: 1.4, color: C.text2, marginTop: 28 }}>
            No cita de memoria: abre la página oficial y subraya el pasaje exacto en el que se apoya.
          </Rev>
          <Rev at={130} style={{ display: "flex", alignItems: "center", gap: 14, marginTop: 36, fontSize: 30, color: C.accent }}>
            <Icono n="externo" size={34} />
            Abrir en la fuente oficial
          </Rev>
        </div>

        <Rev at={0} dy={40} d={20} style={{ width: W, height: H, borderRadius: 36, overflow: "hidden", background: "#fff", boxShadow: C.shadowBig, position: "relative", flexShrink: 0 }}>
          <div style={{ height: BARRA, background: C.surface2, display: "flex", alignItems: "center", padding: "0 28px", gap: 12 }}>
            {[0, 1, 2].map((i) => <div key={i} style={{ width: 16, height: 16, borderRadius: 8, background: C.outline }} />)}
            <div style={{ marginLeft: 18, background: C.bg, borderRadius: 999, padding: "8px 24px", fontSize: 24, color: C.text2, whiteSpace: "nowrap" }}>
              boe.es/buscar/act.php?id=BOE-A-2015-11430#a55
            </div>
          </div>
          <div style={{ position: "relative", height: H - BARRA, overflow: "hidden" }}>
            <div style={{ position: "absolute", left: 0, top: -6, width: W, height: (W * 1000) / 1500, scale: zoom, transformOrigin: "50% 80%" }}>
              <Img src={staticFile("capturas/boe_et55_plano.png")} style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }} />
              <Img src={staticFile("capturas/boe_et55.png")} style={{ position: "absolute", inset: 0, width: "100%", height: "100%", opacity: marca }} />
            </div>
            <Rev
              at={112}
              dy={40}
              d={18}
              style={{ position: "absolute", left: 28, right: 28, bottom: 28, background: C.bg, borderRadius: 28, padding: "26px 34px", boxShadow: C.shadowBig, border: `1.5px solid ${C.outline}` }}
            >
              <div style={{ fontFamily: serif, fontSize: 34, lineHeight: 1.4, fontStyle: "italic" }}>«{CITA_ET55}»</div>
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 14, fontSize: 26, color: C.success, fontWeight: 500 }}>
                <Icono n="check" size={30} color={C.success} sw={3} />
                Artículo 55 ET · coincide al 100 % con el texto oficial
              </div>
            </Rev>
          </div>
        </Rev>
      </div>
    </Lienzo>
  );
};
