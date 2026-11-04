"""Descarga del BOE los grandes cuerpos legales enteros, con todas sus versiones (corpus legal local).

Con el corpus en local, cada consulta busca el precepto pertinente en la redacción vigente A LA FECHA DE LOS HECHOS
y el modelo solo elige de esa lista. La primera descarga tarda (≈ 2 peticiones por segundo, por cortesía con el BOE);
las siguientes solo bajan lo que el índice oficial marca como actualizado.

Uso:
    uv run python scripts/ingerir_corpus.py                 # el núcleo (Código Civil, Penal, ET, LEC, LECrim…)
    uv run python scripts/ingerir_corpus.py --normas CC,CP  # solo esas (alias de config/catalogo_normas.json)
    uv run python scripts/ingerir_corpus.py --estado        # qué hay descargado
    uv run python scripts/ingerir_corpus.py --forzar        # vuelve a descargarlo todo
    uv run python scripts/ingerir_corpus.py --sin-vectores  # sin calcular embeddings

Búsqueda semántica: `uv sync --extra embeddings` instala el modelo local (ONNX, CPU; se descarga una vez).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):  # consola de Windows con codificación antigua
    sys.stdout.reconfigure(errors="replace")

from config.settings import get_settings  # noqa: E402
from connectors.boe_client import BOEClient, BOERepository  # noqa: E402
from connectors.corpus_legal import CorpusLegal, ProgresoIngesta  # noqa: E402
from connectors.embeddings import crear_embedder  # noqa: E402
from core.materias import normas, nucleo  # noqa: E402
from storage.database import open_database  # noqa: E402
from storage.lance_schema import LegislacionStore, directorio_por_modelo  # noqa: E402


def _imprimir_estado(corpus: CorpusLegal) -> None:
    for e in corpus.estado():
        marca = "" if e["verificado"] else " (id sin verificar: se comprueba al descargar)"
        print(f"  {e['alias']:<9} {e['estado']:<10} {e['preceptos_ok']:>5}/{e['preceptos']:<5} {e['titulo']}{marca}")


def _progreso(p: ProgresoIngesta) -> None:
    if p.fase in ("bloques", "vectores") and p.total:
        print(f"\r  {p.alias}: {p.fase} {p.hechos}/{p.total}", end="", flush=True)
    elif p.fase == "fin":
        print()


async def _ejecutar(args: argparse.Namespace, client: BOEClient | None) -> int:
    settings = get_settings()
    assert settings.sqlite_path is not None and settings.lancedb_dir is not None
    con = open_database(settings.sqlite_path)
    boe_client = client or BOEClient()
    embedder = None if args.sin_vectores else crear_embedder(settings.gemini_api_key)
    store = (
        LegislacionStore(directorio_por_modelo(settings.lancedb_dir, embedder.model), embedder.dim)
        if embedder is not None
        else None
    )
    corpus = CorpusLegal(con, BOERepository(con, boe_client), boe_client, store=store, embedder=embedder)
    if args.estado:
        _imprimir_estado(corpus)
        return 0
    aliases = [a.strip().upper() for a in args.normas.split(",") if a.strip()] if args.normas else nucleo()
    desconocidas = [a for a in aliases if a not in normas()]
    if desconocidas:
        print(f"No están en config/catalogo_normas.json: {', '.join(desconocidas)}")
        return 2
    if embedder is None and not args.sin_vectores:
        print("Sin embeddings (instala el extra: uv sync --extra embeddings): solo búsqueda léxica BM25.")
    fallos = 0
    for alias in aliases:
        print(f"{alias} · {normas()[alias]['titulo']}")
        try:
            res = await corpus.ingerir(alias, progreso=_progreso, forzar=args.forzar, vectores=embedder is not None)
        except Exception as exc:  # p. ej. el modelo de embeddings no se pudo descargar: se sigue con lo demás
            print(f"\n  ✗ {exc}")
            fallos += 1
            continue
        print(
            f"  {res.modo or '-'}: {res.descargados} descargados, {res.sin_cambios} sin cambios, "
            f"{res.errores} errores, {res.vectores_nuevos} vectores nuevos"
        )
        for aviso in res.avisos:
            print(f"  ! {aviso}")
        fallos += 1 if res.errores else 0
    print("\nEstado del corpus:")
    _imprimir_estado(corpus)
    if client is None:
        await boe_client.aclose()
    return 1 if fallos else 0


def main(argv: list[str] | None = None, *, client: BOEClient | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--normas", help="alias separados por comas (por defecto, el núcleo)")
    parser.add_argument("--estado", action="store_true", help="solo mostrar qué hay descargado")
    parser.add_argument("--forzar", action="store_true", help="descargar de nuevo aunque no haya cambios")
    parser.add_argument("--sin-vectores", action="store_true", help="no calcular embeddings")
    return asyncio.run(_ejecutar(parser.parse_args(argv), client))


if __name__ == "__main__":
    raise SystemExit(main())
