"""Contrato en vivo de la búsqueda del catálogo consolidado del BOE (ejecución manual: `-m live`).

El 01-11-2026 la búsqueda respondía `500 Code: 101` incluso a los ejemplos de la documentación oficial; este test
confirma el formato de respuesta que asume `BOEClient.buscar_normas` cuando el servicio vuelva."""

import pytest

from connectors.boe_client import BOEClient

pytestmark = pytest.mark.live


async def test_buscar_normas_encuentra_la_lau():
    boe = BOEClient()
    try:
        normas = await boe.buscar_normas("arrendamientos urbanos")
    finally:
        await boe.aclose()
    assert "BOE-A-1994-26003" in [n.id_norma for n in normas]
