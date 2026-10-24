"""Importa en lote las sentencias (PDF o TXT) de una carpeta local al corpus de jurisprudencia.

Iuris-IA no hace descargas masivas de CENDOJ (aviso legal del CGPJ): descargas tú los PDFs que te interesen desde
https://www.poderjudicial.es/search/indexAN.jsp y los pasas por este script (o los subes desde la web).

Sin clave de la Gemini API solo se indexa para búsqueda por palabras (BM25); con clave, también por embeddings.

Uso:
    uv run python scripts/importar_sentencias.py ruta/a/carpeta
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

from config.settings import get_settings, load_catalog  # noqa: E402
from connectors.cendoj_fetcher import CendojRepository  # noqa: E402
from connectors.embeddings import Embedder, GeminiEmbedder  # noqa: E402
from core.errors import ModelUnavailable  # noqa: E402
from core.providers.http_adapter import ApiKeyStore  # noqa: E402
from storage.database import open_database  # noqa: E402
from storage.lance_schema import JurisprudenciaStore  # noqa: E402


async def _importar(carpeta: Path) -> int:
    archivos = sorted(f for f in carpeta.iterdir() if f.suffix.lower() in (".pdf", ".txt"))
    if not archivos:
        print(f"No hay ficheros .pdf ni .txt en {carpeta}")
        return 0
    settings = get_settings()
    assert settings.sqlite_path is not None and settings.lancedb_dir is not None  # rellenados desde data_dir
    con = open_database(settings.sqlite_path)
    key = ApiKeyStore(settings.data_dir / "provider_keys.bin").get("gemini_api", None) or settings.gemini_api_key
    emb_spec = load_catalog().models.get("gemini_embedding")
    embedder: Embedder | None = None
    store: JurisprudenciaStore | None = None
    if key and emb_spec and emb_spec.model_id:
        try:
            embedder = GeminiEmbedder(key, model=emb_spec.model_id, dim=emb_spec.output_dimensionality or 768)
            store = JurisprudenciaStore(settings.lancedb_dir, dim=embedder.dim)
        except ModelUnavailable:
            embedder = store = None
    print("Índice: BM25 + embeddings" if embedder else "Índice: solo BM25 (sin clave de la Gemini API)")
    repo = CendojRepository(con, store=store, embedder=embedder)
    ok = 0
    for f in archivos:
        data = f.read_bytes()
        try:
            if f.suffix.lower() == ".pdf":
                res = await repo.import_pdf(data)
            else:
                res = await repo.import_text(data.decode("utf-8", errors="replace"))
        except Exception as exc:  # un fichero defectuoso no debe parar el lote
            print(f"  ✗ {f.name}: {exc}")
            continue
        ok += 1
        estado = "nueva" if res.nueva else "ya existía"
        print(f"  ✓ {f.name} → {res.roj_id} ({estado}, {res.chunks_indexados} fragmentos)")
        for aviso in res.avisos:
            print(f"    ! {aviso}")
    con.close()
    print(f"\n{ok}/{len(archivos)} sentencias importadas en {settings.sqlite_path}")
    return 0 if ok == len(archivos) else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("carpeta", type=Path, help="carpeta con PDFs o TXT de sentencias")
    args = parser.parse_args(argv)
    if not args.carpeta.is_dir():
        print(f"No existe la carpeta: {args.carpeta}")
        return 1
    return asyncio.run(_importar(args.carpeta))


if __name__ == "__main__":
    raise SystemExit(main())
