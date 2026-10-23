import hashlib
from datetime import date

import pytest

from connectors.cendoj_fetcher import CendojRepository, FetchLimitReached, PoliteFetcher, normas_citadas
from connectors.cendoj_parser import parse_sentencia, purge_antecedentes
from connectors.pdf_extractor import clean_text, extract_pdf
from connectors.retriever import HybridRetriever, rrf
from storage.lance_schema import JurisprudenciaStore, chunk_text
from tests.conftest import FIXTURES, ROOT

SENTENCIA = (FIXTURES / "sentencias" / "sap_fianza_sintetica.txt").read_text(encoding="utf-8")


class FakeEmbedder:
    """Embeddings deterministas por bolsa de palabras (dim 16) para tests sin red."""

    model = "fake-embedding"
    dim = 16

    async def embed(self, texts, task):
        out = []
        for t in texts:
            v = [0.0] * self.dim
            for w in t.lower().split():
                v[int(hashlib.md5(w.encode()).hexdigest(), 16) % self.dim] += 1.0
            out.append(v)
        return out


def test_parse_sentencia_sections():
    s = parse_sentencia(SENTENCIA)
    assert s.roj == "SAP M 9999/2024" and s.ecli == "ECLI:ES:APM:2024:9999"
    assert s.fecha == date(2024, 3, 14) and s.nivel == "AP"
    assert "36.4 de la LAU" in s.fundamentos and "VOTO" not in s.fundamentos
    assert s.fallo.startswith("Desestimamos")
    assert len(s.votos_particulares) == 1 and "Estimaría parcialmente" in s.votos_particulares[0]
    assert [n for n, _ in s.fundamentos_lista] == ["PRIMERO", "SEGUNDO", "TERCERO"]


def test_purge_antecedentes_removes_procedural_history():
    s = parse_sentencia(SENTENCIA)
    assert "entregó las llaves" in s.antecedentes_purgados
    assert "dictó sentencia" not in s.antecedentes_purgados
    assert "recurso de apelación" not in s.antecedentes_purgados
    assert purge_antecedentes("El Juzgado de lo Social nº 3 dictó sentencia estimando la demanda.") == ""


def test_normas_citadas():
    assert normas_citadas("conforme al artículo 36.4 de la LAU y art. 1561 del Código Civil") == [
        "CÓDIGO CIVIL:a1561",
        "LAU:a36",
    ] or normas_citadas("conforme al artículo 36 de la LAU") == ["LAU:a36"]


def test_chunk_text_overlap():
    text = ". ".join(f"Frase número {i} con contenido jurídico relevante" for i in range(200))
    chunks = chunk_text(text, max_chars=500)
    assert len(chunks) > 5 and all(len(c) <= 500 for c in chunks)
    assert chunks[0][-40:].split()[-1] in chunks[1]  # hay solape


def test_pdf_extractor_on_real_pdf():
    result = extract_pdf(ROOT / "Propuesta_Maestra_IurisIA_LexAgent_Definitiva.pdf")
    assert len(result.pages) == 6 and result.ocr_pending == []
    assert "Fase 3" in result.text


def test_clean_text():
    assert clean_text("conﬁ-\nanza   en   el\n\n\nbanco") == "confianza en el\nbanco"


async def test_import_index_and_hybrid_search(db, tmp_path):
    store = JurisprudenciaStore(tmp_path / "lance", dim=FakeEmbedder.dim)
    repo = CendojRepository(db, store=store, embedder=FakeEmbedder())
    res = await repo.import_text(SENTENCIA, submaterias=["CIV_LAU_FIANZA"])
    assert res.roj_id == "SAP M 9999/2024" and res.nueva and res.chunks_indexados >= 4
    assert any("voto" in a for a in res.avisos)
    again = await repo.import_text(SENTENCIA)
    assert not again.nueva and store.count() == res.chunks_indexados  # reindexado sin duplicar
    row = db.execute("SELECT voto_particular, jurisdiccion FROM cendoj_sentencias").fetchone()
    assert "magistrado discrepante" in row[0] and row[1] == "civil"
    chunks = store._table.to_arrow().to_pylist()
    assert all("discrepante" not in c["chunk_text"] for c in chunks)

    retriever = HybridRetriever(db, store=store, embedder=FakeEmbedder())
    hits = await retriever.search("devolución de la fianza por pintar la vivienda", jurisdiccion="civil")
    assert hits and hits[0].roj_id == "SAP M 9999/2024" and hits[0].fuentes == {"bm25", "vector"}
    assert await retriever.search("fianza", jurisdiccion="social") == []


async def test_import_rejects_text_without_roj(db):
    with pytest.raises(ValueError, match="ROJ"):
        await CendojRepository(db).import_text("texto cualquiera sin identificador")


def test_rrf():
    scores = rrf([["a", "b"], ["b", "c"]])
    assert max(scores, key=scores.get) == "b"


async def test_polite_fetcher_daily_cap():
    import httpx

    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, text="ok")))
    fetcher = PoliteFetcher(min_interval_s=0, daily_cap=2, client=client)
    await fetcher.get("https://example.org/1")
    await fetcher.get("https://example.org/2")
    with pytest.raises(FetchLimitReached):
        await fetcher.get("https://example.org/3")
    assert fetcher.last_user_agent.startswith("IurisIA/")
