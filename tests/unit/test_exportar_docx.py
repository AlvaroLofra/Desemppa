"""Exportación del dictamen a Word: contenido verificado, anexo de auditoría separado y casos sin dictamen."""

from __future__ import annotations

import io

from docx import Document

from core.exportar_docx import dictamen_docx
from core.orchestrator import Orchestrator
from tests.golden.test_pipeline_dorado import CASOS, HOY, INVENCIONES, RouterAdversarial, _boe_sintetico, _triaje


async def _certificada(db):
    from connectors.boe_client import BOERepository
    from connectors.cendoj_fetcher import CendojRepository
    from connectors.convenios_db import ConveniosRepository
    from connectors.retriever import HybridRetriever
    from core.calendar_engine import CalendarEngine
    from core.orchestrator import Services
    from core.state import ConsultaStore, EventBus

    caso = CASOS[0]  # despido disciplinario
    s = Services(
        router=RouterAdversarial(_triaje(caso)),
        boe=BOERepository(db, _boe_sintetico()),
        retriever=HybridRetriever(db),
        cendoj=CendojRepository(db),
        convenios=ConveniosRepository(db),
        calendar=CalendarEngine(),
        store=ConsultaStore(db),
        bus=EventBus(db),
        today=lambda: HOY,
    )
    cid = s.store.create(caso.texto, "eco")
    await Orchestrator(s).run(cid)
    c = s.store.get(cid)
    return {"texto": caso.texto, "triage": c.triage, "debate": c.debate, "dictamen": c.dictamen}


def _parrafos(contenido: bytes) -> list[str]:
    doc = Document(io.BytesIO(contenido))
    textos = [p.text for p in doc.paragraphs]
    for t in doc.tables:
        textos += [c.text for fila in t.rows for c in fila.cells]
    return textos


async def test_word_del_dictamen_certificado(db):
    consulta = await _certificada(db)
    textos = _parrafos(dictamen_docx(consulta))
    todo = "\n".join(textos)
    assert "Dictamen de orientación jurídica" in todo and "carta de despido" in todo
    assert "Sí: el titular puede ejercitar su derecho" in todo
    assert "no es una probabilidad de ganar" in todo
    assert "Fundamentos verificados" in todo and "SHA-256" in todo
    assert "30/03/2026" in todo  # fecha límite del motor de plazos (20 días hábiles)
    # Lo inventado solo aparece en el anexo, marcado como descartado, nunca en el cuerpo.
    anexo = next(i for i, t in enumerate(textos) if t.startswith("Anexo"))
    cuerpo = "\n".join(textos[:anexo])
    for inventada in INVENCIONES.values():
        assert inventada not in cuerpo
    assert INVENCIONES["articulo"] in "\n".join(textos[anexo:])


def test_word_sin_dictamen_certificado():
    consulta = {
        "texto": "Consulta de prueba",
        "triage": {},
        "debate": None,
        "dictamen": {"estado": "BLOQUEADA", "mensaje": "No he encontrado ninguna norma verificable.", "avisos": ["x"]},
    }
    todo = "\n".join(_parrafos(dictamen_docx(consulta)))
    assert "No he encontrado ninguna norma verificable." in todo and "Consulta de prueba" in todo
