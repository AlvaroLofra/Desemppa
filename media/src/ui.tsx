import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { C, sans } from "./theme";

export const OUT = Easing.bezier(0.2, 0, 0, 1);
const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

/** Progreso eased 0→1 entre los frames `at` y `at + d`. */
export const rev = (frame: number, at: number, d = 14) => interpolate(frame, [at, at + d], [0, 1], { ...clamp, easing: OUT });

/** Aparición con fundido y desplazamiento vertical, a partir del frame local `at`. */
export const Rev: React.FC<{ at: number; d?: number; dy?: number; style?: React.CSSProperties; children: React.ReactNode }> = ({
  at, d = 14, dy = 24, style, children,
}) => {
  const frame = useCurrentFrame();
  const p = rev(frame, at, d);
  return (
    <div style={{ opacity: p, translate: `0px ${(1 - p) * dy}px`, ...style }}>{children}</div>
  );
};

/** Lienzo crema de una escena. */
export const Lienzo: React.FC<{ name: string; children: React.ReactNode; style?: React.CSSProperties }> = ({ name, children, style }) => (
  <AbsoluteFill name={name} style={{ backgroundColor: C.bg, fontFamily: sans, color: C.text, ...style }}>{children}</AbsoluteFill>
);

/** Etiqueta superior de la escena (estilo .eyebrow de la app). */
export const Eyebrow: React.FC<{ children: React.ReactNode; at?: number }> = ({ children, at = 0 }) => (
  <Rev at={at} dy={12} style={{ fontSize: 28, fontWeight: 500, letterSpacing: "0.1em", textTransform: "uppercase", color: C.text3, marginBottom: 20 }}>
    {children}
  </Rev>
);

const ICONOS: Record<string, string[]> = {
  arriba: ["M12 19V5", "M5 12l7-7 7 7"],
  clip: ["m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48"],
  archivo: ["M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7z", "M14 2v4a2 2 0 0 0 2 2h4", "M10 9H8", "M16 13H8", "M16 17H8"],
  check: ["M20 6 9 17l-5-5"],
  calendario: ["M8 2v4", "M16 2v4", "M21 13V6a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h8", "M3 10h18", "M19 16v6", "M16 19h6"],
  descarga: ["M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7z", "M14 2v4a2 2 0 0 0 2 2h4", "M12 18v-6", "M9 15l3 3 3-3"],
  imprimir: ["M6 9V2h12v7", "M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2", "M6 14h12v8H6z"],
  libro: ["M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z", "M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"],
  copiar: ["M10 8h10a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H10a2 2 0 0 1-2-2V10a2 2 0 0 1 2-2z", "M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"],
  externo: ["M15 3h6v6", "M10 14 21 3", "M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"],
  x: ["M18 6 6 18", "M6 6l12 12"],
  candado: ["M7 11V8a5 5 0 0 1 10 0v3", "M6 11h12a1 1 0 0 1 1 1v8a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1v-8a1 1 0 0 1 1-1z"],
};

export const Icono: React.FC<{ n: keyof typeof ICONOS | string; size?: number; color?: string; sw?: number }> = ({ n, size = 32, color = C.accent, sw = 1.8 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round">
    {ICONOS[n].map((d, i) => <path key={i} d={d} />)}
  </svg>
);

/** Insignia redonda con check, como el de la fase completada. */
export const CheckRedondo: React.FC<{ size?: number; hecho: boolean }> = ({ size = 40, hecho }) => {
  const frame = useCurrentFrame();
  return (
    <div style={{ width: size, height: size, borderRadius: size / 2, background: hecho ? C.accent : C.accentContainer, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
      {hecho ? <Icono n="check" size={size * 0.6} color={C.onAccent} sw={3} /> : <div style={{ width: size * 0.35, height: size * 0.35, borderRadius: size, background: C.accent, scale: 0.8 + 0.2 * Math.sin(frame / 3) }} />}
    </div>
  );
};

/** Superíndice de fuente [n] como en el dictamen de la app. */
export const Ref: React.FC<{ n: number }> = ({ n }) => (
  <sup style={{ fontSize: "0.5em", fontWeight: 500, color: C.accent, marginLeft: 4 }}>[{n}]</sup>
);

/** Botón estilo app (píldora). */
export const Boton: React.FC<{ children: React.ReactNode; tipo?: "primario" | "tonal" | "outline" | "ghost"; size?: number; style?: React.CSSProperties }> = ({
  children, tipo = "tonal", size = 30, style,
}) => {
  const base: Record<string, React.CSSProperties> = {
    primario: { background: C.accent, color: C.onAccent },
    tonal: { background: C.accentContainer, color: C.onAccentContainer },
    outline: { border: `2px solid ${C.outline}`, color: C.text },
    ghost: { color: C.text2 },
  };
  return (
    <div style={{ display: "inline-flex", alignItems: "center", gap: 12, borderRadius: 999, padding: `${size * 0.4}px ${size * 0.9}px`, fontSize: size, fontWeight: 500, ...base[tipo], ...style }}>{children}</div>
  );
};
