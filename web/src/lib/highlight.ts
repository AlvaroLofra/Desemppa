/** Divide un texto en [antes, resaltado, después] según offsets [inicio, fin) del texto original. */
export function highlightParts(text: string, offsets: [number, number] | null | undefined): [string, string, string] {
  if (!offsets) return [text, "", ""];
  const start = Math.max(0, Math.min(offsets[0], text.length));
  const end = Math.max(start, Math.min(offsets[1], text.length));
  return [text.slice(0, start), text.slice(start, end), text.slice(end)];
}

export function fechaLarga(iso: string): string {
  const d = new Date(`${iso.slice(0, 10)}T12:00:00`);
  return d.toLocaleDateString("es-ES", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
}

export function diasNaturalesHasta(iso: string, hoy = new Date()): number {
  const fin = new Date(`${iso.slice(0, 10)}T00:00:00`);
  const base = new Date(hoy.getFullYear(), hoy.getMonth(), hoy.getDate());
  return Math.round((fin.getTime() - base.getTime()) / 86_400_000);
}
