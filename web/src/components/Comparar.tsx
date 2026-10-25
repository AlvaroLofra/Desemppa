import { useEffect, useMemo, useState } from "react";
import { Loader2 } from "lucide-react";
import { api } from "../lib/api";
import { claveFuente, compararFuentes } from "../lib/comparar";
import { fechaLarga } from "../lib/highlight";
import { BANDA_TEXTO, type FinalPayload } from "../lib/types";

type Item = Awaited<ReturnType<typeof api.consultas>>[number];
interface Detalle { texto: string; final: FinalPayload | null; titulos: Map<string, string> }

const GRUPOS = ["articulos_boe", "articulos_ue", "sentencias", "clausulas_convenio", "extractos_adjuntos"];

async function cargar(id: string): Promise<Detalle> {
  const c = await api.consulta(id);
  const titulos = new Map<string, string>();
  for (const g of GRUPOS) for (const f of c.dossier?.[g] ?? []) titulos.set(claveFuente(f.source_id), f.titulo);
  return { texto: c.texto ?? "", final: (c.dictamen as FinalPayload | null) ?? null, titulos };
}

function respuesta(f: FinalPayload | null): string {
  if (!f) return "Sin resultado (consulta sin terminar).";
  const d = f.dictamen;
  if (f.estado !== "CERTIFICADA" || !d) return f.mensaje ?? f.estado;
  const r = (d.afirmaciones ?? []).filter((a) => a.seccion === "respuesta").map((a) => a.texto).join(" ");
  return r || d.respuesta_directa || d.resumen_ciudadano;
}

function Columna({ det }: { det: Detalle | null }) {
  if (!det) return <Loader2 className="h-5 w-5 animate-spin text-ink-3" />;
  const f = det.final;
  const d = f?.dictamen;
  const plazos = d?.plazos ?? f?.plazos ?? [];
  const post = d?.postulacion ?? f?.postulacion;
  const eliminadas = d?.auditoria?.filter((e) => e.resultado === "eliminada").length ?? 0;
  return (
    <div className="min-w-0 space-y-4 rounded-3xl bg-surface p-5 text-sm">
      <div><p className="eyebrow mb-1">Consulta</p><p className="whitespace-pre-line text-ink-2">{det.texto}</p></div>
      <div><p className="eyebrow mb-1">Respuesta</p><p className="legal text-[15.5px]">{respuesta(f)}</p></div>
      {d && <div><p className="eyebrow mb-1">Solidez</p><p className="text-ink">{BANDA_TEXTO[d.banda_solidez]}</p></div>}
      <div>
        <p className="eyebrow mb-1">Plazos</p>
        {plazos.length ? (
          <ul className="space-y-1">{plazos.map((p) => (
            <li key={p.tipo_plazo_id} className="text-ink">{p.descripcion}: <span className="tabular-nums">{fechaLarga(p.fecha_limite_segura)}</span></li>
          ))}</ul>
        ) : <p className="text-ink-3">Ninguno</p>}
      </div>
      {post && (
        <div><p className="eyebrow mb-1">Abogado y procurador</p>
          <p className="text-ink">{post.requiere_abogado ? `Abogado${post.requiere_procurador ? " y procurador" : ""}` : "Sin abogado"}</p></div>
      )}
      {d && (
        <p className="text-xs text-ink-3">
          {d.fundamentos.length} fundamentos verificados · {d.afirmaciones?.length ?? 0} afirmaciones mostradas · {eliminadas} eliminadas
          por el cortafuegos
        </p>
      )}
    </div>
  );
}

/** Dos consultas lado a lado: qué cambia en la respuesta, los plazos y las fuentes al cambiar los hechos. */
export function Comparar({ actual }: { actual: string | null }) {
  const [items, setItems] = useState<Item[]>([]);
  const [ids, setIds] = useState<[string, string]>([actual ?? "", ""]);
  const [det, setDet] = useState<[Detalle | null, Detalle | null]>([null, null]);

  useEffect(() => {
    api.consultas().then((xs) => {
      const terminadas = xs.filter((x) => ["CERTIFICADA", "BLOQUEADA", "FUERA_DE_ALCANCE"].includes(x.estado));
      setItems(terminadas);
      setIds(([a, b]) => {
        const primera = terminadas.some((x) => x.consulta_id === a) ? a : terminadas[0]?.consulta_id ?? "";
        return [primera, b || terminadas.find((x) => x.consulta_id !== primera)?.consulta_id || ""];
      });
    }).catch(() => setItems([]));
  }, []);

  useEffect(() => {
    setDet([null, null]);
    ids.forEach((id, i) => {
      if (!id) return;
      cargar(id).then((d) => setDet((prev) => (i === 0 ? [d, prev[1]] : [prev[0], d]))).catch(() => undefined);
    });
  }, [ids]);

  const dif = useMemo(() => compararFuentes(det[0]?.final ?? null, det[1]?.final ?? null), [det]);
  const titulo = (k: string) => det[0]?.titulos.get(k) ?? det[1]?.titulos.get(k) ?? k;

  if (items.length < 2) {
    return (
      <div className="mx-auto max-w-[760px] px-4 pt-4 sm:px-6">
        <h1 className="text-[28px] font-normal tracking-tight text-ink">Comparar consultas</h1>
        <p className="mt-2 text-sm text-ink-2">Necesitas al menos dos consultas terminadas para compararlas.</p>
      </div>
    );
  }
  return (
    <div className="mx-auto max-w-[1100px] space-y-6 px-4 pb-10 pt-4 sm:px-6">
      <h1 className="text-[28px] font-normal tracking-tight text-ink">Comparar consultas</h1>
      <div className="grid gap-4 md:grid-cols-2">
        {[0, 1].map((i) => (
          <div key={i} className="min-w-0 space-y-3">
            <label className="block">
              <span className="label">Consulta {i === 0 ? "A" : "B"}</span>
              <select className="field" value={ids[i]}
                      onChange={(e) => setIds((v) => (i === 0 ? [e.target.value, v[1]] : [v[0], e.target.value]))}>
                {items.map((x) => <option key={x.consulta_id} value={x.consulta_id}>{x.titulo}</option>)}
              </select>
            </label>
            <Columna det={det[i]} />
          </div>
        ))}
      </div>
      <section aria-label="Fuentes" className="rounded-3xl bg-surface p-5 text-sm">
        <h2 className="mb-3 text-base font-medium text-ink">Fuentes citadas</h2>
        <div className="grid gap-4 md:grid-cols-3">
          {([["En las dos", dif.comunes], ["Solo en A", dif.soloA], ["Solo en B", dif.soloB]] as const).map(([t, lista]) => (
            <div key={t}>
              <p className="eyebrow mb-1">{t} ({lista.length})</p>
              <ul className="space-y-1">
                {lista.map((k) => <li key={k} className="text-ink-2" title={k}>{titulo(k)}</li>)}
                {!lista.length && <li className="text-ink-3">—</li>}
              </ul>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
