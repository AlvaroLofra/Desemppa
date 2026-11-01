import React from "react";
import { C, serif } from "./theme";
import { Eyebrow, Icono, Lienzo, Rev } from "./ui";
import { AUDITORIA, FUENTES_CITADAS, FUNDAMENTOS, SELLO } from "./datos";

export const Scene9: React.FC = () => (
  <Lienzo name="Placa 9 · Fundamentos y fuentes" style={{ alignItems: "center", justifyContent: "center" }}>
    <div style={{ width: 1680 }}>
      <Eyebrow>Fundamentos verificados</Eyebrow>
      <Rev at={2}>
        <div style={{ fontSize: 68, letterSpacing: "-0.03em", lineHeight: 1.08, marginBottom: 34 }}>Cada afirmación, con su fuente</div>
      </Rev>
      <div style={{ display: "flex", gap: 56 }}>
        <div style={{ flex: 1.5 }}>
          {FUNDAMENTOS.map((f, i) => (
            <Rev key={f.n} at={16 + i * 26} dy={20} style={{ display: "flex", gap: 20, marginBottom: 24 }}>
              <div style={{ width: 46, height: 46, borderRadius: 23, background: C.accentContainer, color: C.onAccentContainer, fontSize: 26, fontWeight: 500, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, marginTop: 2 }}>{f.n}</div>
              <div>
                <div style={{ fontSize: 30, lineHeight: 1.3 }}>{f.t}</div>
                <div style={{ fontFamily: serif, fontStyle: "italic", fontSize: 27, color: C.text2, lineHeight: 1.4, marginTop: 6 }}>«{f.cita}»</div>
                <div style={{ fontSize: 22, color: C.text3, marginTop: 4 }}>{f.src} · coincide al 100 % con el texto oficial</div>
              </div>
            </Rev>
          ))}
        </div>
        <div style={{ flex: 1 }}>
          <Rev at={96} dy={24} style={{ background: C.surface, borderRadius: 36, padding: "28px 36px", marginBottom: 22 }}>
            <div style={{ fontSize: 24, fontWeight: 500, letterSpacing: "0.1em", textTransform: "uppercase", color: C.text3, marginBottom: 10 }}>Fuentes citadas</div>
            {FUENTES_CITADAS.map((f, i) => (
              <div key={f} style={{ fontSize: 31, padding: "4px 0" }}>
                <span style={{ color: C.accent, fontWeight: 500, marginRight: 12 }}>[{i + 1}]</span>{f}
              </div>
            ))}
          </Rev>
          <Rev at={122} dy={24} style={{ background: C.surface, borderRadius: 36, padding: "26px 36px" }}>
            <div style={{ fontSize: 28, fontWeight: 500 }}>{SELLO.titulo}</div>
            <div style={{ fontSize: 23, color: C.text2, marginTop: 6 }}>{SELLO.fuente}</div>
            <div style={{ fontFamily: "monospace", fontSize: 19, color: C.text3, marginTop: 6, wordBreak: "break-all" }}>SHA-256 {SELLO.sha}</div>
            <div style={{ fontSize: 22, color: C.text2, marginTop: 10, lineHeight: 1.35 }}>{SELLO.nota}</div>
          </Rev>
        </div>
      </div>
      <Rev at={150} dy={10} style={{ display: "flex", alignItems: "center", gap: 12, fontSize: 27, color: C.text2, marginTop: 26 }}>
        <Icono n="check" size={30} color={C.success} sw={3} />
        {AUDITORIA}
      </Rev>
    </div>
  </Lienzo>
);
