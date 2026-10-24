import json
from datetime import date

import httpx
import pytest

from connectors.boe_client import BOEClient, BOEError, BOERepository, fts_query
from connectors.boe_models import articulo_to_bloque, as_list, parse_bloque_xml, parse_indice_json
from core.temporal_sync import select_version, sentencia_desfasada
from tests.conftest import FIXTURES

LAU = "BOE-A-1994-26003"


@pytest.fixture(scope="module")
def bloque_a36():
    return parse_bloque_xml(LAU, (FIXTURES / "boe" / "lau_a36.xml").read_bytes())


def test_parse_versions(bloque_a36):
    v = bloque_a36.versiones
    assert bloque_a36.id_bloque == "a36" and bloque_a36.titulo == "Artículo 36"
    assert len(v) >= 7
    assert v[0].vigencia_desde == date(1995, 1, 1) and v[0].id_norma_modificadora == LAU
    assert all(a.vigencia_hasta == b.vigencia_desde for a, b in zip(v, v[1:], strict=False))
    assert v[-1].vigencia_hasta is None
    assert "devengará el interés legal" in v[0].texto


def test_version_at(bloque_a36):
    assert bloque_a36.version_at(date(1996, 6, 1)).vigencia_desde == date(1995, 1, 1)
    assert bloque_a36.version_at(date(1990, 1, 1)) is None
    assert bloque_a36.version_at(None) is bloque_a36.versiones[-1]


def test_select_version_by_fecha_hechos(bloque_a36):
    va = select_version(bloque_a36, date(2015, 5, 1))
    assert va.version.vigencia_desde == date(2013, 6, 6)
    assert va.reformado_tras_fecha_hechos and "18/12/2018" not in va.avisos[0]
    assert "19/12/2018" in va.avisos[0]  # primera reforma posterior
    sin_fecha = select_version(bloque_a36, None)
    assert sin_fecha.version is bloque_a36.versiones[-1] and sin_fecha.avisos
    assert select_version(bloque_a36, date(1980, 1, 1)).version is None


def test_sentencia_desfasada(bloque_a36):
    assert sentencia_desfasada(bloque_a36, date(2012, 1, 1)) is not None
    assert sentencia_desfasada(bloque_a36, date(2030, 1, 1)) is None


def test_indice_polymorphic():
    data = json.loads((FIXTURES / "boe" / "lau_indice.json").read_text(encoding="utf-8"))
    entries = parse_indice_json(data)
    assert entries[0].id_bloque == "preambulo" and any(e.id_bloque == "a36" for e in entries)
    single = {"data": {"bloque": {"id": "a1", "titulo": None, "fecha_actualizacion": "19941125"}}}
    assert [e.id_bloque for e in parse_indice_json(single)] == ["a1"]
    assert as_list(None) == [] and as_list("x") == ["x"]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("36", "a36"), ("Art. 1902", "a1902"), ("artículo 36 bis", "a36bis"), ("a21", "a21"), ("dt1", "dt1")],
)
def test_articulo_to_bloque(raw, expected):
    assert articulo_to_bloque(raw) == expected


def test_fts_query_is_safe():
    assert fts_query('fianza "OR" ; DROP') == '"fianza" OR "DROP"'
    assert fts_query("a b") == '""'


def _mock_boe(calls):
    xml = (FIXTURES / "boe" / "lau_a36.xml").read_bytes()
    meta = {
        "data": [
            {
                "identificador": LAU,
                "titulo": "Ley 29/1994 de Arrendamientos Urbanos",
                "rango": {"texto": "Ley"},
                "ambito": {"texto": "Estatal"},
                "estatus_derogacion": "N",
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path.endswith("/metadatos"):
            return httpx.Response(200, json=meta)
        if request.url.path.endswith("/bloque/a36"):
            return httpx.Response(200, content=xml)
        return httpx.Response(404)

    return httpx.AsyncClient(
        base_url="https://www.boe.es/datosabiertos/api/legislacion-consolidada", transport=httpx.MockTransport(handler)
    )


async def test_repository_cache_first_and_fts(db):
    calls: list[str] = []
    repo = BOERepository(db, BOEClient(client=_mock_boe(calls), max_rps=1000))
    first = await repo.get_articulo(LAU, "36")
    second = await repo.get_articulo(LAU, "36")
    assert len(calls) == 3  # índice + metadatos + bloque; la segunda vez sale de memoria y SQLite
    assert [v.vigencia_desde for v in first.versiones] == [v.vigencia_desde for v in second.versiones]
    assert db.execute("SELECT estado FROM boe_normas").fetchone()[0] == "vigente"
    hits = repo.search("fianza interés legal")
    assert hits and hits[0]["id_bloque"] == "a36"
    with pytest.raises(BOEError):
        await repo.get_articulo(LAU, "9999")


async def test_resolve_bloque_uses_norm_index(db):
    indice = {
        "data": {
            "bloque": [
                {"id": "art1561", "titulo": "Artículo 1561"},
                {"id": "a36", "titulo": "x"},
                {"id": "a2-8", "titulo": "Artículo 26"},  # Ley 15/2022: ids posicionales
                {"id": "anoveno", "titulo": "Artículo noveno"},  # LPH: ordinales en letra
                {"id": "adieciseis", "titulo": "Artículo dieciséis"},
            ]
        }
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=indice) if request.url.path.endswith("/indice") else httpx.Response(404)

    client = httpx.AsyncClient(base_url="https://x", transport=httpx.MockTransport(handler))
    repo = BOERepository(db, BOEClient(client=client, max_rps=1000))
    assert await repo.resolve_bloque("BOE-A-1889-4763", "1561") == "art1561"  # Código Civil
    assert await repo.resolve_bloque("BOE-A-1889-4763", "36") == "a36"
    assert await repo.resolve_bloque("BOE-A-1889-4763", "dt1") == "dt1"
    assert await repo.resolve_bloque("BOE-A-1889-4763", "26") == "a2-8"
    assert await repo.resolve_bloque("BOE-A-1889-4763", "9") == "anoveno"
    assert await repo.resolve_bloque("BOE-A-1889-4763", "16") == "adieciseis"


def test_articulo_con_guion_del_codigo_civil_catalan():
    from connectors.boe_client import _titulo_es_articulo

    assert _titulo_es_articulo("Artículo 121-21", "121-21") is True
    assert _titulo_es_articulo("Artículo 121-21", "121") is False
    assert _titulo_es_articulo("Artículo 36 bis", "36bis") is True
