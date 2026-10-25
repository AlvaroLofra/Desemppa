import { ATAJOS } from "../lib/atajos";
import { Dialog } from "./ui/primitives";

/** Ayuda con los atajos de teclado (se abre con «?»). */
export function AyudaAtajos({ onClose }: { onClose: () => void }) {
  return (
    <Dialog titulo="Atajos de teclado" onClose={onClose}>
      <dl className="space-y-2 text-sm">
        {ATAJOS.map((a) => (
          <div key={a.accion} className="flex items-center gap-3">
            <dt className="w-24 shrink-0">
              <kbd className="rounded-md border border-outline bg-bg px-1.5 py-0.5 font-mono text-xs text-ink">{a.teclas}</kbd>
            </dt>
            <dd className="text-ink-2">{a.descripcion}</dd>
          </div>
        ))}
      </dl>
    </Dialog>
  );
}
