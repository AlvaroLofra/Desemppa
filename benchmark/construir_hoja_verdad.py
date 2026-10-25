"""Construye la «hoja de verdad» de cada caso de benchmark/casos_verificables/*.json.

Solo admite lo que se puede comprobar, sin LLM ni memoria:
- artículos clave: texto LITERAL descargado del BOE (versión vigente a la fecha de los hechos) o de EUR-Lex, con su
  hash SHA-256, URL oficial y fecha de la versión;
- plazos: calculados por el motor determinista (CalendarEngine) con los festivos del municipio;
- postulación: evaluada con las reglas de config/postulacion.yaml.
Si un artículo no se puede descargar, el script falla: nunca se rellena a mano.

Uso:
    uv run python benchmark/construir_hoja_verdad.py            # todos los casos
    uv run python benchmark/construir_hoja_verdad.py V01 V16    # algunos
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

from config.settings import get_settings  # noqa: E402
from connectors.boe_client import BOEClient, BOERepository  # noqa: E402
from connectors.eurlex_client import EURLexRepository  # noqa: E402
from core.calendar_engine import CalendarEngine, CalendarioFestivos  # noqa: E402
from core.materias import id_norma  # noqa: E402
from core.postulacion_rules import CasoPostulacion, evaluar  # noqa: E402
from core.temporal_sync import select_version  # noqa: E402
from storage.database import open_database  # noqa: E402

CASOS = ROOT / "benchmark" / "casos_verificables"
HOJAS = CASOS / "hojas"


async def _articulo(
    boe: BOERepository, ue: EURLexRepository, norma: str, art: str, fecha: date | None
) -> dict[str, Any]:
    if norma.startswith("EUR:"):
        celex = norma[4:]
        a = await ue.get_articulo(celex, art)
        texto, url, version = a.texto, a.url, "Diario Oficial de la UE (texto publicado)"
        source_id = f"EUR:{celex}:art{art}"
    else:
        ident = id_norma(norma)
        bloque = await boe.get_articulo(ident, art)
        va = select_version(bloque, fecha)
        if va.version is None:
            raise RuntimeError(f"{norma} art. {art}: no hay versión vigente el {fecha}")
        texto = va.version.texto
        version = va.version.vigencia_desde.isoformat()
        url = f"https://www.boe.es/buscar/act.php?id={ident}#{bloque.id_bloque}"
        source_id = f"BOE:{ident}:{bloque.id_bloque}:{version}"
    return {
        "norma": norma,
        "articulo": art,
        "source_id": source_id,
        "url": url,
        "version": version,
        "sha256": hashlib.sha256(texto.encode("utf-8")).hexdigest(),
        "texto": texto,
    }


async def construir(ids: list[str]) -> int:
    settings = get_settings()
    assert settings.sqlite_path is not None
    con = open_database(settings.sqlite_path)
    boe, ue = BOERepository(con, BOEClient()), EURLexRepository(con)
    calendario = CalendarEngine(CalendarioFestivos(con=con))
    HOJAS.mkdir(parents=True, exist_ok=True)
    errores = 0
    for f in sorted(CASOS.glob("V*.json")):
        caso = json.loads(f.read_text(encoding="utf-8"))
        if ids and caso["id"] not in ids:
            continue
        v = caso["verdad"]
        fecha = date.fromisoformat(caso["fecha_hechos"]) if caso.get("fecha_hechos") else None
        hoja: dict[str, Any] = {"id": caso["id"], "construida": date.today().isoformat(), "articulos": [], "plazos": []}
        try:
            for a in v["articulos_clave"]:
                hoja["articulos"].append(await _articulo(boe, ue, a["norma"], a["articulo"], fecha))
            for p in v["plazos"]:
                ccaa = calendario.festivos.ccaa_de(p["municipio_ine"])
                calc = calendario.compute(
                    p["tipo"],
                    date.fromisoformat(p["inicio"]),
                    municipio_ine=p["municipio_ine"],
                    territorio_foral="CT" if ccaa == "CT" else None,
                )
                hoja["plazos"].append(
                    {
                        "tipo": p["tipo"],
                        "inicio": p["inicio"],
                        "fecha_limite_segura": calc.fecha_limite_segura.isoformat(),
                        "base_legal": calc.base_legal,
                    }
                )
            if v.get("postulacion"):
                r = evaluar(CasoPostulacion(**v["postulacion"], fase="instancia"))
                hoja["postulacion"] = {
                    "requiere_abogado": r.requiere_abogado,
                    "requiere_procurador": r.requiere_procurador,
                    "base_legal": r.base_legal,
                }
        except Exception as exc:  # cualquier fallo invalida la hoja: no se rellena a mano
            errores += 1
            print(f"✗ {caso['id']}: {exc}")
            continue
        (HOJAS / f"{caso['id']}.json").write_text(
            json.dumps(hoja, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        resumen = ", ".join(f"{a['norma']} {a['articulo']}" for a in hoja["articulos"]) or "sin artículos"
        print(f"✓ {caso['id']}: {resumen}; plazos {[p['fecha_limite_segura'] for p in hoja['plazos']]}")
    con.close()
    return 1 if errores else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(construir(sys.argv[1:])))
