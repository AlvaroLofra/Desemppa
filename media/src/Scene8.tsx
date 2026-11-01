import React from "react";
import { C } from "./theme";
import { Boton, Eyebrow, Icono, Lienzo, Rev } from "./ui";
import { PASOS, PLAZO, POSTULACION, SIN_BORRADOR } from "./datos";

export const Scene8: React.FC = () => (
  <Lienzo name="Placa 8 · Fechas y pautas" style={{ alignItems: "center", justifyContent: "center" }}>
    <div style={{ width: 1740 }}>
      <Eyebrow>Plazos y pautas</Eyebrow>
      <Rev at={2}>
        <div style={{ fontSize: 64, letterSpacing: "-0.03em", lineHeight: 1.08, marginBottom: 28 }}>Las fechas las calcula el código</div>
      </Rev>
      <div style={{ display: "flex", gap: 48, alignItems: "flex-start" }}>
        <Rev at={14} dy={30} style={{ width: 760, background: C.surface, borderRadius: 40, padding: "36px 44px" }}>
          <div style={{ fontSize: 30, color: C.text2 }}>{PLAZO.descripcion}</div>
          <Rev at={28} dy={12} style={{ fontSize: 58, marginTop: 12, lineHeight: 1.1, letterSpacing: "-0.02em", color: C.text }}>{PLAZO.limite}</Rev>
          <Rev at={44} dy={8} style={{ fontSize: 28, color: C.text2, marginTop: 14 }}>
            Quedan {PLAZO.habiles} días hábiles al hacer el análisis <span style={{ color: C.text3 }}>· desde el {PLAZO.desde}</span>
          </Rev>
          <Rev at={58} dy={8} style={{ fontSize: 25, color: C.text3, marginTop: 16, lineHeight: 1.35 }}>
            {PLAZO.aviso}
          </Rev>
          <Rev at={72} dy={8} style={{ fontSize: 24, color: C.text3, marginTop: 14 }}>{PLAZO.base} · cálculo pendiente de validación jurídica</Rev>
          <Rev at={86} dy={10} style={{ marginTop: 26 }}>
            <Boton tipo="ghost" size={28} style={{ marginLeft: -20 }}>
              <Icono n="calendario" size={34} />
              Añadir al calendario
            </Boton>
          </Rev>
        </Rev>

        <div style={{ flex: 1 }}>
          <Rev at={22} dy={14} style={{ fontSize: 40, fontWeight: 500, marginBottom: 20 }}>Qué hacer a continuación</Rev>
          {PASOS.map((p, i) => (
            <Rev key={p.t} at={90 + i * 28} dy={20} style={{ background: C.surface, borderRadius: 32, padding: "22px 30px", marginBottom: 16, display: "flex", gap: 20 }}>
              <div style={{ width: 44, height: 44, borderRadius: 22, background: C.accentContainer, color: C.onAccentContainer, fontSize: 26, fontWeight: 500, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>{i + 1}</div>
              <div>
                <div style={{ fontSize: 31, fontWeight: 500, lineHeight: 1.2 }}>{p.t}</div>
                <div style={{ fontSize: 24, color: C.text2, marginTop: 4 }}>{p.q}</div>
                <div style={{ fontSize: 26, marginTop: 8, lineHeight: 1.35 }}>{p.d}</div>
                {i === 1 && <div style={{ fontSize: 23, color: C.text3, marginTop: 8 }}>{SIN_BORRADOR}</div>}
              </div>
            </Rev>
          ))}
          <Rev at={178} dy={10} style={{ fontSize: 25, color: C.text2, lineHeight: 1.35, marginTop: 8 }}>{POSTULACION}</Rev>
        </div>
      </div>
    </div>
  </Lienzo>
);
