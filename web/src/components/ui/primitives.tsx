import { useEffect, useRef, type ReactNode } from "react";
import { X } from "lucide-react";

export function Switch({ checked, onChange, label, disabled }: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
  disabled?: boolean;
}) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border-2 transition-colors disabled:opacity-40 ${
        checked ? "border-accent bg-accent" : "border-ink-3 bg-surface-2"
      }`}
    >
      <span
        className={`inline-block rounded-full transition-all ${
          checked ? "ml-[22px] h-4 w-4 bg-on-accent" : "ml-1 h-3 w-3 bg-ink-3"
        }`}
      />
    </button>
  );
}

export function Dialog({ titulo, onClose, children, amplio = false }: {
  titulo: string; onClose: () => void; children: ReactNode; amplio?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", esc);
    ref.current?.querySelector<HTMLElement>("input, select, button")?.focus();
    return () => document.removeEventListener("keydown", esc);
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onMouseDown={onClose}>
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-label={titulo}
        onMouseDown={(e) => e.stopPropagation()}
        className={`fade-in w-full ${amplio ? "max-w-2xl" : "max-w-md"} rounded-[28px] bg-surface p-6 shadow-float`}
      >
        <div className="mb-4 flex items-center">
          <h2 className="text-xl text-ink">{titulo}</h2>
          <button className="icon-btn -mr-2 ml-auto" onClick={onClose} aria-label="Cerrar"><X className="h-5 w-5" /></button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function Seccion({ id, titulo, descripcion, children }: {
  id: string;
  titulo: string;
  descripcion?: string;
  children: ReactNode;
}) {
  return (
    <section id={id} aria-labelledby={`${id}-t`} className="scroll-mt-6">
      <h2 id={`${id}-t`} className="text-xl text-ink">{titulo}</h2>
      {descripcion && <p className="mt-1 text-sm text-ink-2">{descripcion}</p>}
      <div className="mt-4">{children}</div>
    </section>
  );
}
