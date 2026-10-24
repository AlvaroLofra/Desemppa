"""Descarga del BOE, verifica e indexa los convenios estatales de `data/convenios_seed.yaml`.

Cada referencia se comprueba antes de indexar (título de resolución que registra y publica un convenio y código
de convenio dentro del texto); si no cuadra, se rechaza. Como fecha de vigencia se toma la de publicación en el
BOE (criterio conservador: no se presume vigencia retroactiva).

Uso:
    uv run python scripts/importar_convenios_boe.py            # importa todos los estatales del seed
    uv run python scripts/importar_convenios_boe.py --verificar  # solo comprueba las referencias, sin indexar
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):  # consola de Windows con codificación antigua
    sys.stdout.reconfigure(errors="replace")

from config.settings import get_settings  # noqa: E402
from connectors.convenios_boe import descargar_documento, verificar_documento  # noqa: E402
from connectors.convenios_db import ConveniosRepository, load_seed, split_articulos  # noqa: E402
from storage.database import open_database  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--verificar", action="store_true", help="solo verificar las referencias del seed")
    args = parser.parse_args(argv)

    seed = [c for c in load_seed() if c.get("codigo_regcon") and c.get("boletin_ref")]
    settings = get_settings()
    assert settings.sqlite_path is not None  # lo rellena Settings a partir de data_dir
    con = None if args.verificar else open_database(settings.sqlite_path)
    repo = ConveniosRepository(con) if con is not None else None
    ok = fallos = 0
    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        for item in seed:
            codigo, ref, denom = str(item["codigo_regcon"]), str(item["boletin_ref"]), str(item["denominacion"])
            print(f"[{int(item['prioridad']):02d}] {ref} · {denom}")
            try:
                doc = descargar_documento(ref, client)
            except (httpx.HTTPError, ValueError) as exc:
                print(f"  ✗ no se pudo descargar: {exc}")
                fallos += 1
                continue
            errores = verificar_documento(doc, codigo)
            arts = split_articulos(doc.texto)
            if not arts:
                errores.append("no se detectaron artículos en el texto")
            if errores:
                for e in errores:
                    print(f"  ✗ {e}")
                fallos += 1
                continue
            if doc.modificaciones_posteriores:
                print(
                    f"  ! {len(doc.modificaciones_posteriores)} modificaciones posteriores NO integradas: "
                    + ", ".join(doc.modificaciones_posteriores)
                )
            if repo is not None and doc.fecha_publicacion is not None:
                repo.upsert_convenio(
                    codigo, denom, str(item["sector"]), str(item["territorio"]), prioridad=int(item["prioridad"])
                )
                vid = repo.add_version(codigo, doc.texto, boletin_ref=ref, vigencia_desde=doc.fecha_publicacion)
                print(f"  ✓ indexado {vid}: {len(arts)} artículos (publicado el {doc.fecha_publicacion:%d/%m/%Y})")
            else:
                print(f"  ✓ verificado: {len(arts)} artículos")
            ok += 1
    if con is not None:
        con.close()
    print(
        f"\n{ok} correctos, {fallos} rechazados"
        + ("" if args.verificar else f" · base de datos: {settings.sqlite_path}")
    )
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
