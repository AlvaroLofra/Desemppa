"""Contrasta con el BOE real cada referencia de convenio del seed (red; `uv run pytest -m live`)."""

import httpx
import pytest

from connectors.convenios_boe import descargar_documento, verificar_documento
from connectors.convenios_db import load_seed

ESTATALES = [c for c in load_seed() if c.get("boletin_ref")]


@pytest.mark.live
@pytest.mark.parametrize("conv", ESTATALES, ids=[c["boletin_ref"] for c in ESTATALES])
def test_referencia_boe_del_seed_es_el_convenio_declarado(conv):
    with httpx.Client(timeout=60) as client:
        doc = descargar_documento(conv["boletin_ref"], client)
    assert verificar_documento(doc, conv["codigo_regcon"]) == []
