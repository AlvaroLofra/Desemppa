import type { Plazo } from "./types";

/** Escapa texto según RFC 5545 (barra invertida, punto y coma, coma y saltos de línea). */
export function escaparIcs(s: string): string {
  return s.replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,").replace(/\r?\n/g, "\\n");
}

/** Pliega una línea a 75 octetos (RFC 5545 §3.1): las siguientes empiezan por un espacio. */
export function plegar(linea: string): string[] {
  const enc = new TextEncoder();
  const out: string[] = [];
  let actual = "";
  for (const ch of linea) {
    const limite = out.length ? 74 : 75; // la continuación lleva un espacio delante
    if (enc.encode(actual + ch).length > limite) {
      out.push(out.length ? ` ${actual}` : actual);
      actual = ch;
    } else {
      actual += ch;
    }
  }
  out.push(out.length ? ` ${actual}` : actual);
  return out;
}

const fechaIcs = (iso: string) => iso.replaceAll("-", "");

function diaSiguiente(iso: string): string {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + 1);
  return d.toISOString().slice(0, 10);
}

/** Calendario .ics con un evento de día completo por plazo (la fecha límite segura que calculó el motor
 *  determinista) y avisos 7 días y 1 día antes. No calcula fechas: solo copia las del dictamen. */
export function plazosIcs(plazos: Plazo[], asunto: string, ahora = new Date()): string {
  const sello = ahora.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
  const lineas = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Desemppa//Plazos//ES", "CALSCALE:GREGORIAN", "METHOD:PUBLISH"];
  for (const p of plazos) {
    const descripcion = [
      `Asunto: ${asunto}`,
      `Plazo: ${p.descripcion}`,
      `Desde el ${p.fecha_inicio}. Base legal: ${p.base_legal}.`,
      p.dia_gracia_hasta ? `Día de gracia (solo escritos al juzgado) hasta las 15:00 del ${p.dia_gracia_hasta}.` : "",
      "Cálculo orientativo pendiente de validación jurídica: no apures el último día.",
    ].filter(Boolean).join("\n");
    lineas.push(
      "BEGIN:VEVENT",
      `UID:${p.tipo_plazo_id}-${fechaIcs(p.fecha_inicio)}-${fechaIcs(p.fecha_limite_segura)}@desemppa.local`,
      `DTSTAMP:${sello}`,
      `DTSTART;VALUE=DATE:${fechaIcs(p.fecha_limite_segura)}`,
      `DTEND;VALUE=DATE:${fechaIcs(diaSiguiente(p.fecha_limite_segura))}`,
      `SUMMARY:${escaparIcs(`Vence: ${p.descripcion}`)}`,
      `DESCRIPTION:${escaparIcs(descripcion)}`,
      "TRANSP:TRANSPARENT",
    );
    for (const antes of ["-P7D", "-P1D"]) {
      lineas.push("BEGIN:VALARM", "ACTION:DISPLAY", `TRIGGER:${antes}`,
        `DESCRIPTION:${escaparIcs(`Plazo: ${p.descripcion}`)}`, "END:VALARM");
    }
    lineas.push("END:VEVENT");
  }
  lineas.push("END:VCALENDAR");
  return `${lineas.flatMap(plegar).join("\r\n")}\r\n`;
}
