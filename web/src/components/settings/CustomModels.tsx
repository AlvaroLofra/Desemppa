import { useState, type FormEvent } from "react";
import { Plus } from "lucide-react";
import { api, type Proveedor } from "../../lib/api";
import { Dialog } from "../ui/primitives";

/** Alta de un modelo que no está en el catálogo (se guarda en config/user_models.toml). */
export function CustomModels({ proveedores, onCambio, onMensaje }: {
  proveedores: Record<string, Proveedor> | null;
  onCambio: () => void;
  onMensaje: (m: string) => void;
}) {
  const [abierto, setAbierto] = useState(false);
  const [proveedor, setProveedor] = useState("antigravity_cli");
  const [alias, setAlias] = useState("");
  const [modelId, setModelId] = useState("");
  const [etiqueta, setEtiqueta] = useState("");

  const crear = async (e: FormEvent) => {
    e.preventDefault();
    try {
      await api.crearModelo({
        alias: alias.trim().toLowerCase().replace(/[^a-z0-9_]/g, "_"),
        proveedor,
        model_id: modelId.trim(),
        etiqueta: etiqueta.trim(),
        efforts: ["low", "medium", "high"],
      });
      setAbierto(false);
      setAlias("");
      setModelId("");
      setEtiqueta("");
      onMensaje("Modelo añadido: ya puedes asignarlo en «Modos».");
      onCambio();
    } catch (err) {
      onMensaje(`No se pudo añadir el modelo: ${(err as Error).message}`);
    }
  };

  const restablecer = async () => {
    if (!window.confirm("¿Borrar los modelos personalizados y volver a activar o desactivar los proveedores como venían por defecto?")) return;
    await api.restablecerModelos();
    onMensaje("Modelos personalizados y proveedores restablecidos.");
    onCambio();
  };

  return (
    <div className="flex flex-wrap gap-2">
      <button className="btn-outline" onClick={() => setAbierto(true)}><Plus className="h-4 w-4" />Añadir modelo</button>
      <button className="btn-ghost" onClick={restablecer}>Restablecer modelos y proveedores</button>
      {abierto && proveedores && (
        <Dialog titulo="Añadir modelo" onClose={() => setAbierto(false)}>
          <form onSubmit={crear} className="space-y-3">
            <p className="text-sm text-ink-2">
              Usa el identificador exacto del proveedor. Pulsa «Detectar» en «Cuentas y planes» para ver los que ofrece.
            </p>
            <label className="block"><span className="label">Proveedor</span>
              <select className="field" value={proveedor} onChange={(e) => setProveedor(e.target.value)}>
                {Object.entries(proveedores).map(([pid, p]) => <option key={pid} value={pid}>{p.etiqueta}</option>)}
              </select>
            </label>
            <label className="block"><span className="label">Identificador del modelo</span>
              <input className="field" required value={modelId} onChange={(e) => setModelId(e.target.value)}
                     placeholder="p. ej. gemini-4-argon-{effort}" />
            </label>
            <label className="block"><span className="label">Nombre visible</span>
              <input className="field" required minLength={2} value={etiqueta} onChange={(e) => setEtiqueta(e.target.value)} />
            </label>
            <label className="block"><span className="label">Alias interno (minúsculas y guiones bajos)</span>
              <input className="field" required minLength={2} pattern="[a-z0-9_]+" value={alias}
                     onChange={(e) => setAlias(e.target.value)} placeholder="p. ej. argon_personal" />
            </label>
            <div className="flex justify-end gap-2 pt-2">
              <button type="button" className="btn-ghost" onClick={() => setAbierto(false)}>Cancelar</button>
              <button type="submit" className="btn-primary">Añadir</button>
            </div>
          </form>
        </Dialog>
      )}
    </div>
  );
}
