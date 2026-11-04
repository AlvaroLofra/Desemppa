"""Contrasta con el BOE real lo que se escribió sin acceso al BOE el 04-11-2026 (red; `uv run pytest -m live`).

1. Formato de `/id/{id}/texto` (texto completo): cada <bloque> se analiza como un bloque suelto.
2. El identificador del Código de Comercio (`CCOM`, marcado `"verificado": false`) es de verdad esa norma.
3. Las normas del núcleo existen y siguen vigentes.
Si todo pasa, se puede quitar `"verificado": false` de CCOM en config/catalogo_normas.json.
"""

import pytest

from connectors.boe_client import BOEClient, BOERepository
from core.materias import id_norma, normas, nucleo
from storage.database import open_database


@pytest.mark.live
async def test_texto_completo_coincide_con_los_bloques_sueltos():
    client = BOEClient()
    try:
        lau = id_norma("LAU")
        bloques = {b.id_bloque: b for b in await client.texto_completo(lau)}
        suelto = await client.bloque(lau, "a36")
        assert "a36" in bloques and len(bloques) > 50
        assert [v.vigencia_desde for v in bloques["a36"].versiones] == [v.vigencia_desde for v in suelto.versiones]
        assert bloques["a36"].versiones[-1].texto == suelto.versiones[-1].texto
    finally:
        await client.aclose()


@pytest.mark.live
async def test_codigo_de_comercio_es_la_norma_declarada():
    repo = BOERepository(open_database(":memory:"), BOEClient())
    meta = await repo.ensure_norma(id_norma("CCOM"))  # lanza BOEError si el título no es el Código de Comercio
    assert not meta.derogada


@pytest.mark.live
@pytest.mark.parametrize("alias", nucleo())
async def test_normas_del_nucleo_vigentes(alias):
    meta = await BOERepository(open_database(":memory:"), BOEClient()).ensure_norma(normas()[alias]["id"])
    assert meta.titulo and not meta.derogada
