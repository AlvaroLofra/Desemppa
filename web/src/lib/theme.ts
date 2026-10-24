export type Tema = "sistema" | "claro" | "oscuro";

const CLAVE = "iuris-tema";

export function leerTema(): Tema {
  try {
    const t = localStorage.getItem(CLAVE);
    return t === "claro" || t === "oscuro" ? t : "sistema";
  } catch {
    return "sistema";
  }
}

/** Aplica el tema con `data-theme` en <html>; «sistema» deja que mande `prefers-color-scheme`. */
export function aplicarTema(t: Tema): void {
  const root = document.documentElement;
  if (t === "sistema") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", t === "oscuro" ? "dark" : "light");
  try {
    localStorage.setItem(CLAVE, t);
  } catch {
    /* almacenamiento no disponible */
  }
}
