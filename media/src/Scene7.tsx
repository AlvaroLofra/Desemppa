import React from "react";
import { C } from "./theme";
import { Eyebrow, Lienzo, Ref, Rev } from "./ui";
import { A_TU_FAVOR, PUNTOS_DEBILES, RESPUESTA, SOLIDEZ } from "./datos";

const Lista: React.FC<{ titulo: string; items: { t: string; n?: number }[]; at: number }> = ({ titulo, items, at }) => (
  <Rev at={at} dy={22} style={{ flex: 1 }}>
    <div style={{ fontSize: 38, fontWeight: 500, marginBottom: 14 }}>{titulo}</div>
    {items.map((x, i) => (
      <Rev key={i} at={at + 10 + i * 12} dy={12} style={{ display: "flex", gap: 14, fontSize: 27, lineHeight: 1.35, color: C.text2, marginBottom: 12 }}>
        <div style={{ width: 9, height: 9, borderRadius: 5, background: C.text2, marginTop: 13, flexShrink: 0 }} />
        <div>{x.t}{x.n && <Ref n={x.n} />}</div>
      </Rev>
    ))}
  </Rev>
);

export const Scene7: React.FC = () => (
  <Lienzo name="Placa 7 · Resultado" style={{ alignItems: "center", justifyContent: "center" }}>
    <div style={{ width: 1620 }}>
      <Eyebrow>Tu resultado</Eyebrow>
      <Rev at={4} style={{ fontSize: 44, lineHeight: 1.32, marginBottom: 30 }}>
        {RESPUESTA.map((r) => (
          <span key={r.n}>{r.t}<Ref n={r.n} /> </span>
        ))}
      </Rev>

      <Rev at={52} dy={24} style={{ background: C.surface, borderRadius: 32, padding: "26px 36px", marginBottom: 34, display: "flex", gap: 40, alignItems: "center" }}>
        <div style={{ width: 430, flexShrink: 0 }}>
          <div style={{ fontSize: 26, color: C.text2, marginBottom: 12 }}>Solidez de tu posición</div>
          <div style={{ display: "flex", gap: 8 }}>
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} style={{ height: 16, width: 74, borderRadius: 8, background: i <= SOLIDEZ.nivel ? C.warning : C.surface2 }} />
            ))}
          </div>
        </div>
        <div>
          <div style={{ fontSize: 38, fontWeight: 500 }}>{SOLIDEZ.texto}</div>
          <div style={{ fontSize: 26, color: C.text2, marginTop: 6, lineHeight: 1.35 }}>{SOLIDEZ.explicacion}</div>
          <div style={{ fontSize: 22, color: C.text3, marginTop: 8 }}>{SOLIDEZ.nota}</div>
        </div>
      </Rev>

      <div style={{ display: "flex", gap: 56 }}>
        <Lista titulo="A tu favor" items={A_TU_FAVOR} at={104} />
        <Lista titulo="Puntos débiles" items={PUNTOS_DEBILES} at={130} />
      </div>
    </div>
  </Lienzo>
);
