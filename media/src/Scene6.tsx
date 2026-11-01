import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { C, serif } from "./theme";
import { Eyebrow, Icono, Lienzo, Rev } from "./ui";
import { DEBATE, SENTENCIA } from "./datos";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

export const Scene6: React.FC = () => {
  const frame = useCurrentFrame();
  const p = interpolate(frame, [96, 124], [0, 1], clamp);
  const i = SENTENCIA.fragmento.indexOf(SENTENCIA.resaltado);
  const antes = SENTENCIA.fragmento.slice(0, i);
  const despues = SENTENCIA.fragmento.slice(i + SENTENCIA.resaltado.length);

  return (
    <Lienzo name="Placa 6 · Jurisprudencia" style={{ alignItems: "center", justifyContent: "center" }}>
      <div style={{ width: 1740, display: "flex", gap: 56, alignItems: "center" }}>
        <div style={{ width: 760 }}>
          <Eyebrow>Jurisprudencia y debate</Eyebrow>
          <Rev at={2}>
            <div style={{ fontSize: 66, letterSpacing: "-0.03em", lineHeight: 1.08, marginBottom: 34 }}>No solo lee la ley: la interpreta</div>
          </Rev>
          {DEBATE.map((d, k) => (
            <Rev key={d.rol} at={20 + k * 24} dy={20} style={{ background: C.surface, borderRadius: 32, padding: "24px 32px", marginBottom: 20, borderLeft: `8px solid ${k === 2 ? C.accent : C.outline}` }}>
              <div style={{ fontSize: 28, fontWeight: 500, color: k === 2 ? C.accent : C.text2, marginBottom: 6 }}>{d.rol}</div>
              <div style={{ fontSize: 28, lineHeight: 1.35 }}>{d.texto}</div>
              {d.estima && <div style={{ fontSize: 26, color: C.success, fontWeight: 500, marginTop: 8 }}>{d.estima}</div>}
            </Rev>
          ))}
        </div>

        <Rev at={6} dy={40} d={20} style={{ width: 920, background: C.surface, borderRadius: 48, padding: "36px 44px 32px", boxShadow: C.shadowBig }}>
          <div style={{ display: "flex", alignItems: "flex-start", gap: 20 }}>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 38, fontWeight: 500, lineHeight: 1.2 }}>{SENTENCIA.titulo}</div>
              <div style={{ fontSize: 25, color: C.text3, marginTop: 6 }}>{SENTENCIA.meta}</div>
            </div>
            <Icono n="externo" size={34} color={C.text2} />
            <Icono n="x" size={34} color={C.text2} />
          </div>
          <div style={{ fontFamily: serif, fontSize: 35, lineHeight: 1.55, marginTop: 28 }}>
            {antes}
            <span style={{ background: `rgba(241,220,147,${p})`, borderRadius: 6, padding: "0 4px" }}>{SENTENCIA.resaltado}</span>
            {despues}…
          </div>
          <div style={{ fontSize: 23, color: C.text3, marginTop: 24 }}>
            Ejemplo del visor con una sentencia real del Tribunal Supremo. Las citas de jurisprudencia se verifican igual que las de la ley.
          </div>
        </Rev>
      </div>
    </Lienzo>
  );
};
