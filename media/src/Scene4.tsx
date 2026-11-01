import React from "react";
import { C } from "./theme";
import { CheckRedondo, Eyebrow, Lienzo, Rev } from "./ui";
import { FASES, FUENTES_LEGISLACION } from "./datos";
import { useCurrentFrame } from "remotion";

const Grupo: React.FC<{ at: number; titulo: string; items: string[] }> = ({ at, titulo, items }) => (
  <Rev at={at} dy={14} style={{ marginBottom: 26 }}>
    <div style={{ fontSize: 26, fontWeight: 500, letterSpacing: "0.1em", textTransform: "uppercase", color: C.text3, marginBottom: 8 }}>{titulo}</div>
    {items.map((x) => (
      <div key={x} style={{ fontSize: 36, padding: "6px 0" }}>{x}</div>
    ))}
  </Rev>
);

export const Scene4: React.FC = () => {
  const frame = useCurrentFrame();
  const AT = [14, 36, 58, 80];
  return (
    <Lienzo name="Placa 4 · Fuentes" style={{ alignItems: "center", justifyContent: "center" }}>
      <div style={{ width: 1640 }}>
        <Eyebrow>Fuentes oficiales</Eyebrow>
        <Rev at={2}>
          <div style={{ fontSize: 80, letterSpacing: "-0.03em", lineHeight: 1.1, marginBottom: 56 }}>Va a buscar las fuentes de verdad</div>
        </Rev>
        <div style={{ display: "flex", gap: 56, alignItems: "flex-start" }}>
          <div style={{ flex: 1 }}>
            {FASES.map((f, i) => {
              const hecha = frame >= (AT[i + 1] ?? 9999);
              return (
                <Rev key={f} at={AT[i]} dy={18} style={{ display: "flex", alignItems: "center", gap: 24, marginBottom: 38 }}>
                  <CheckRedondo size={52} hecho={hecha} />
                  <div style={{ fontSize: 42, letterSpacing: "-0.02em", lineHeight: 1.2, color: frame >= AT[i] ? C.text : C.text2 }}>{f}</div>
                </Rev>
              );
            })}
          </div>
          <Rev at={22} dy={30} style={{ width: 640, background: C.surface, borderRadius: 48, padding: "40px 48px", boxShadow: C.shadow }}>
            <div style={{ fontSize: 36, fontWeight: 500, marginBottom: 28 }}>Fuentes consultadas</div>
            <Grupo at={34} titulo="Legislación" items={FUENTES_LEGISLACION} />
            <Grupo at={60} titulo="Jurisprudencia" items={["Sentencia del Tribunal Supremo 185/2025"]} />
            <Grupo at={84} titulo="Tus documentos" items={["carta_despido.pdf"]} />
          </Rev>
        </div>
      </div>
    </Lienzo>
  );
};
