"""Ejecuta la batería verificable contra un servidor de Desemppa en marcha (por la API, no por el navegador).

Para cada caso: crea la consulta, responde las aclaraciones con las del caso, espera al resultado, descarga el
texto completo de cada fuente citada y guarda el expediente verificable (`expediente.md` + `.json`) y su evaluación
automática. Al final escribe `informe.md` con solo datos medidos.

Uso:
    uv run python benchmark/ejecutar.py --modo eco --casos todos
    uv run python benchmark/ejecutar.py --casos limite          # tipico | limite | trampa | aclaracion
    uv run python benchmark/ejecutar.py --casos V05 V16 --base http://127.0.0.1:8010
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

from benchmark.evaluar import evaluar  # noqa: E402
from benchmark.expediente import guardar  # noqa: E402

CASOS = ROOT / "benchmark" / "casos_verificables"
SALIDA = ROOT / "benchmark" / "expedientes"
TERMINALES = {"CERTIFICADA", "BLOQUEADA", "FUERA_DE_ALCANCE", "ERROR"}


def _preguntas(cli: httpx.Client, cid: str, token: str) -> list[dict[str, Any]]:
    texto = cli.get(f"/api/consultar/stream/{cid}", params={"token": token}, timeout=60).text
    datos = [json.loads(ln[6:]) for ln in texto.splitlines() if ln.startswith("data: ") and '"preguntas"' in ln]
    return list(datos[-1]["preguntas"]) if datos else []


def _responder(cli: httpx.Client, caso: dict[str, Any], preguntas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for p in preguntas:
        r = next(
            (
                a["respuesta"]
                for a in caso["aclaraciones_simuladas"]
                if a["pregunta_contiene"].lower() in p["texto"].lower()
            ),
            None,
        )
        if p.get("tipo_respuesta") == "municipio":
            nombre = r or caso.get("municipio_nombre") or ""
            muni = cli.get("/api/municipios", params={"q": nombre}).json() if nombre else []
            out.append(
                {
                    "pregunta": p["texto"],
                    "respuesta": nombre or "No lo sé",
                    "municipio_ine": muni[0]["codigo_ine"] if muni else None,
                }
            )
        else:
            out.append({"pregunta": p["texto"], "respuesta": r or "No lo sé"})
    return out


def ejecutar_caso(cli: httpx.Client, caso: dict[str, Any], modo: str) -> dict[str, Any]:
    token = cli.get("/api/token").json()["token"]
    h = {"X-Iuris-Token": token}
    t0 = time.monotonic()
    r = cli.post(
        "/api/consultas",
        headers=h,
        json={"texto": caso["consulta"], "modo": modo, "municipio_ine": caso.get("municipio_ine"), "adjuntos": []},
    )
    r.raise_for_status()
    cid = r.json()["consulta_id"]
    aclaraciones: list[dict[str, Any]] = []
    c: dict[str, Any] = {}
    while time.monotonic() - t0 < 1500:
        c = cli.get(f"/api/consultas/{cid}").json()
        if c["estado"] == "ESPERANDO_ACLARACION":
            if aclaraciones:  # solo hay una ronda; si vuelve a pedir, se termina
                break
            aclaraciones = _responder(cli, caso, _preguntas(cli, cid, token))
            cli.post(
                f"/api/consultas/{cid}/aclaraciones", headers=h, json={"respuestas": aclaraciones}
            ).raise_for_status()
        elif c["estado"] in TERMINALES:
            break
        time.sleep(6)
    d = c.get("dictamen") or {}
    final = d.get("dictamen") if isinstance(d.get("dictamen"), dict) else {}
    citados = {ci["source_id"] for a in (final or {}).get("afirmaciones", []) for ci in a.get("citas", [])}
    citados |= {f["source_id"] for f in (final or {}).get("fundamentos", [])}
    fuentes = {}
    for sid in sorted(citados):
        fr = cli.get("/api/fuentes", params={"source_id": sid, "consulta_id": cid}, timeout=60)
        if fr.status_code == 200:
            fj = fr.json()
            fuentes[sid] = {"titulo": fj.get("titulo"), "url": fj.get("url"), "texto": fj.get("texto")}
    return {
        "consulta_id": cid,
        "modo": modo,
        "fecha": date.today().isoformat(),
        "estado": c.get("estado"),
        "duracion_s": round(time.monotonic() - t0),
        "aclaraciones": aclaraciones,
        "dictamen": d,
        "mensaje": d.get("mensaje"),
        "debate": c.get("debate"),
        "triage": c.get("triage"),
        "fuentes": fuentes,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--modo", default="eco")
    ap.add_argument("--casos", nargs="+", default=["todos"])
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    args = ap.parse_args(argv)
    casos = [json.loads(f.read_text(encoding="utf-8")) for f in sorted(CASOS.glob("V*.json"))]
    sel = set(args.casos)
    if "todos" not in sel:
        casos = [c for c in casos if c["id"] in sel or c["categoria"] in sel]
    destino = SALIDA / f"{datetime.now():%Y%m%d_%H%M}_{args.modo}"
    filas = []
    with httpx.Client(base_url=args.base, timeout=60) as cli:
        for caso in casos:
            hoja_f = CASOS / "hojas" / f"{caso['id']}.json"
            hoja = json.loads(hoja_f.read_text(encoding="utf-8")) if hoja_f.exists() else None
            print(f"[{caso['id']}] {caso['categoria']} · {caso['materia_esperada']} ...", flush=True)
            try:
                res = ejecutar_caso(cli, caso, args.modo)
            except httpx.HTTPError as exc:
                res = {"estado": "ERROR_CLIENTE", "mensaje": str(exc), "duracion_s": 0}
            ev = evaluar(caso, hoja, res)
            guardar(destino / caso["id"], caso, hoja, res)
            (destino / caso["id"] / "evaluacion.json").write_text(
                json.dumps(ev, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            filas.append((caso, res, ev))
            print(
                f"    {res['estado']} en {res.get('duracion_s')} s · {ev['aprobadas']}/{ev['total']} comprobaciones",
                flush=True,
            )
    _informe(destino, args.modo, filas)
    print(f"\nExpedientes e informe en {destino}")
    return 0


def _informe(destino: Path, modo: str, filas: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]]) -> None:
    destino.mkdir(parents=True, exist_ok=True)
    total = len(filas)
    L = [
        f"# Batería verificable · modo {modo} · {datetime.now():%d/%m/%Y %H:%M}",
        "",
        "Solo datos medidos. «Comprobaciones» = evaluación automática sin LLM (benchmark/evaluar.py).",
        "",
        "| Caso | Categoría | Estado | Tiempo | Comprobaciones | Fallos |",
        "|---|---|---|---|---|---|",
    ]
    for caso, res, ev in filas:
        fallos = ", ".join(k for k, c in ev["checks"].items() if not c["ok"]) or "—"
        L.append(
            f"| [{caso['id']}]({caso['id']}/expediente.md) | {caso['categoria']} | {res['estado']} | "
            f"{res.get('duracion_s')} s | {ev['aprobadas']}/{ev['total']} | {fallos} |"
        )
    perfectos = sum(1 for *_, ev in filas if ev["aprobadas"] == ev["total"])
    tiempos = [r.get("duracion_s") or 0 for _, r, _ in filas]
    eliminadas = sum(
        sum(
            1
            for e in ((r.get("dictamen") or {}).get("dictamen") or {}).get("auditoria", [])
            if e["resultado"] == "eliminada"
        )
        for _, r, _ in filas
    )
    L += [
        "",
        f"- Casos con todas las comprobaciones superadas: **{perfectos}/{total}**",
        f"- Tiempo medio: **{sum(tiempos) / max(1, total):.0f} s**",
        f"- Afirmaciones eliminadas por el cortafuegos (antes de mostrarse): **{eliminadas}**",
    ]
    for nombre in ("estado", "citas_literales", "escaner", "articulos_clave", "plazos", "postulacion", "prohibido"):
        n = [ev["checks"][nombre]["ok"] for *_, ev in filas if nombre in ev["checks"]]
        if n:
            L.append(f"- {nombre}: {sum(n)}/{len(n)}")
    (destino / "informe.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
