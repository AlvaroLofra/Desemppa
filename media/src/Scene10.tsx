import React from "react";
import { C } from "./theme";
import { Boton, Eyebrow, Icono, Lienzo, Rev } from "./ui";

const ACCIONES = [
  { i: "descarga", t: "Exportar el expediente completo (.md)" },
  { i: "imprimir", t: "Imprimir o guardar como PDF, con el proceso y la verificación" },
  { i: "calendario", t: "Añadir los plazos al calendario (.ics), con avisos 7 días y 1 día antes" },
  { i: "libro", t: "Modo lectura" },
];

export const Scene10: React.FC = () => (
  <Lienzo name="Placa 10 · Exportar" style={{ alignItems: "center", justifyContent: "center" }}>
    <div style={{ width: 1560 }}>
      <Eyebrow>Tu expediente</Eyebrow>
      <Rev at={2}>
        <div style={{ fontSize: 80, letterSpacing: "-0.03em", lineHeight: 1.08, marginBottom: 48 }}>Llévate tu caso contigo</div>
      </Rev>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 28 }}>
        {ACCIONES.map((a, k) => (
          <Rev key={a.t} at={22 + k * 14} dy={22} style={{ background: C.surface, borderRadius: 36, padding: "30px 36px", display: "flex", alignItems: "center", gap: 28 }}>
            <div style={{ width: 92, height: 92, borderRadius: 30, background: C.accentContainer, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
              <Icono n={a.i} size={50} />
            </div>
            <div style={{ fontSize: 33, lineHeight: 1.25 }}>{a.t}</div>
          </Rev>
        ))}
      </div>
      <Rev at={88} dy={16} style={{ display: "flex", alignItems: "center", gap: 28, marginTop: 36, fontSize: 30, color: C.text2 }}>
        <Boton tipo="tonal" size={28}><Icono n="archivo" size={32} color={C.onAccentContainer} />Borrador del escrito</Boton>
        <div>Word · Texto · PDF. Solo cuando tu posición tiene respaldo suficiente.</div>
      </Rev>
    </div>
  </Lienzo>
);
