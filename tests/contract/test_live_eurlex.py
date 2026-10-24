"""Descarga real del Reglamento (CE) 261/2004 desde Cellar (red; `uv run pytest -m live`)."""

import asyncio

import pytest

from connectors.eurlex_client import EURLexRepository


@pytest.mark.live
def test_reglamento_261_desde_cellar(db):
    art = asyncio.run(EURLexRepository(db).get_articulo("32004R0261", "7"))
    assert "250 euros para vuelos de hasta 1500 kilómetros" in art.texto
