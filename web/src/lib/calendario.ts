/** Utilidades de fecha del selector (fechas como «AAAA-MM-DD», sin zona horaria: nada de Date local ambiguo). */

export const MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
  "noviembre", "diciembre"];
export const DIAS_SEMANA = ["L", "M", "X", "J", "V", "S", "D"];
export const DIAS_SEMANA_LARGOS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"];

const pad = (n: number, w = 2) => String(n).padStart(w, "0");

export function iso(anio: number, mes: number, dia: number): string {
  return `${pad(anio, 4)}-${pad(mes + 1)}-${pad(dia)}`;
}

export function partes(f: string): { anio: number; mes: number; dia: number } {
  const [a, m, d] = f.split("-").map(Number);
  return { anio: a, mes: m - 1, dia: d };
}

export function diasDelMes(anio: number, mes: number): number {
  return new Date(Date.UTC(anio, mes + 1, 0)).getUTCDate();
}

/** 0 = lunes … 6 = domingo. */
export function diaSemana(f: string): number {
  const { anio, mes, dia } = partes(f);
  return (new Date(Date.UTC(anio, mes, dia)).getUTCDay() + 6) % 7;
}

export function sumarDias(f: string, n: number): string {
  const { anio, mes, dia } = partes(f);
  const d = new Date(Date.UTC(anio, mes, dia + n));
  return iso(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate());
}

/** Mismo día en otro mes (si no existe, el último día de ese mes). */
export function sumarMeses(f: string, n: number): string {
  const { anio, mes, dia } = partes(f);
  const total = anio * 12 + mes + n;
  const a = Math.floor(total / 12), m = ((total % 12) + 12) % 12;
  return iso(a, m, Math.min(dia, diasDelMes(a, m)));
}

/** Cuadrícula de 6 semanas (lunes primero) para el mes dado: fechas ISO, con días de los meses vecinos. */
export function cuadricula(anio: number, mes: number): string[] {
  const primero = iso(anio, mes, 1);
  const inicio = sumarDias(primero, -diaSemana(primero));
  return Array.from({ length: 42 }, (_, i) => sumarDias(inicio, i));
}

/** «25/10/2026» o «25-10-2026» o «25.10.26» → «2026-10-25»; null si no es una fecha real. */
export function leerDMA(texto: string): string | null {
  const m = texto.trim().match(/^(\d{1,2})[/.\-\s](\d{1,2})[/.\-\s](\d{2}|\d{4})$/);
  if (!m) return null;
  const dia = Number(m[1]), mes = Number(m[2]) - 1;
  let anio = Number(m[3]);
  if (m[3].length === 2) anio += anio > 69 ? 1900 : 2000;
  if (mes < 0 || mes > 11 || dia < 1 || dia > diasDelMes(anio, mes)) return null;
  return iso(anio, mes, dia);
}

export function escribirDMA(f: string | null | undefined): string {
  if (!f) return "";
  const { anio, mes, dia } = partes(f);
  return `${pad(dia)}/${pad(mes + 1)}/${pad(anio, 4)}`;
}

export function hoyISO(ahora = new Date()): string {
  return iso(ahora.getFullYear(), ahora.getMonth(), ahora.getDate());
}

export function dentro(f: string, min?: string, max?: string): boolean {
  return (!min || f >= min) && (!max || f <= max);
}
