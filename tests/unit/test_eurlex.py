"""Conector de Derecho de la UE (Cellar/EUR-Lex) con el Reglamento (CE) 261/2004 como fixture real."""

import asyncio

import httpx
import pytest

from connectors.eurlex_client import EURLexError, EURLexRepository, parse_articulos
from tests.conftest import FIXTURES

HTML = (FIXTURES / "eurlex" / "32004R0261_es.html").read_text(encoding="utf-8")


def test_parse_articulos_del_reglamento_261():
    arts = parse_articulos(HTML)
    assert list(arts)[:3] == ["1", "2", "3"] and len(arts) == 19
    titulo, texto = arts["7"]
    assert titulo == "Derecho a compensación"
    assert "a) 250 euros para vuelos de hasta 1500 kilómetros;" in texto
    assert "circunstancias extraordinarias" in arts["5"][1]  # art. 5.3
    assert "Hecho en" not in arts["19"][1]  # la fórmula final no se mezcla con el último artículo


def test_repositorio_usa_cellar_en_espanol_y_cachea(db):
    peticiones = []

    def handler(request: httpx.Request) -> httpx.Response:
        peticiones.append(request)
        return httpx.Response(200, text=HTML, headers={"content-type": "text/html;charset=UTF-8"})

    repo = EURLexRepository(db, client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    art = asyncio.run(repo.get_articulo("32004R0261", "7"))
    asyncio.run(repo.get_articulo("32004R0261", "8"))
    assert len(peticiones) == 1  # el segundo artículo sale de la caché
    assert peticiones[0].headers["accept-language"] == "spa"
    assert str(peticiones[0].url) == "http://publications.europa.eu/resource/celex/32004R0261"
    assert art.url.endswith("CELEX:32004R0261") and art.texto.startswith("Artículo 7")
    with pytest.raises(EURLexError):
        asyncio.run(repo.get_articulo("32004R0261", "99"))


def test_error_del_servidor_sin_cache(db):
    repo = EURLexRepository(
        db, client=httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(202, text="")))
    )
    with pytest.raises(EURLexError, match="202"):
        asyncio.run(repo.get_articulo("32004R0261", "7"))
