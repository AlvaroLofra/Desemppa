"""Descubrimiento de preceptos en el corpus legal: el LLM solo elige de una lista cerrada (docs/vision.md §3).

El BOE es el simulado de test_corpus_legal (textos sintéticos de la LAU con un artículo reformado en 2020 y otro
introducido en 2022)."""

from __future__ import annotations

from datetime import date

import httpx

from connectors.boe_client import BOEClient, BOERepository
from connectors.cendoj_fetcher import CendojRepository
from connectors.convenios_db import ConveniosRepository
from connectors.corpus_legal import CorpusLegal
from connectors.recuperador_legislacion import RecuperadorLegislacion
from connectors.retriever import HybridRetriever
from core.calendar_engine import CalendarEngine
from core.errors import ProviderTimeout
from core.orchestrator import Orchestrator, Services, _Run, indices_elegidos, limpiar_busquedas
from core.schemas import Jurisdiccion, NormaObjetivo, RamaCandidata, TriageOutputSchema
from core.state import ConsultaStore, Estado, EventBus
from tests.unit.test_corpus_legal import LAU, BOEFalso
from tests.unit.test_orchestrator import TRIAJE_OK, ScriptedRouter


async def _servicios(db, script, *, con_corpus=True):
    boe_falso = BOEFalso()
    cliente = boe_falso.cliente()
    boe = BOERepository(db, cliente)
    corpus = CorpusLegal(db, boe, cliente)
    if con_corpus:
        await corpus.ingerir("LAU")
    router = ScriptedRouter(script)
    s = Services(
        router=router,
        boe=boe,
        retriever=HybridRetriever(db),
        cendoj=CendojRepository(db),
        convenios=ConveniosRepository(db),
        calendar=CalendarEngine(),
        store=ConsultaStore(db),
        bus=EventBus(db),
        today=lambda: date(2026, 6, 10),
        corpus=corpus if con_corpus else None,
        legislacion=RecuperadorLegislacion(boe) if con_corpus else None,
    )
    return s, router, boe_falso


def _triage(cid, fecha=date(2019, 3, 15), normas=None):
    return TriageOutputSchema(
        consulta_id=cid,
        jurisdiccion_principal=Jurisdiccion.CIVIL,
        submateria_principal="CIV_LAU_FIANZA",
        ramas=[RamaCandidata(submateria="CIV_LAU_FIANZA", jurisdiccion="civil", peso_enrutamiento=1, justificacion="")],
        grado_ambiguedad=0.1,
        fecha_hechos=fecha,
        normas_boe_objetivo=normas or [],
        busquedas_boe=["devolución de la fianza por el arrendador"],
    )


def _consulta(s, texto):
    cid = s.store.create(texto, "eco")
    s.store.set_estado(cid, Estado.TRIAJE)  # _ingesta se llama aquí sin pasar por el triaje
    return cid


def _eventos(s, cid, tipo):
    return [d for _, t, d in s.bus.history(cid) if t == tipo]


async def test_el_cribado_elige_de_la_lista_cerrada_en_la_version_de_los_hechos(db):
    s, router, _ = await _servicios(db, {"cribado": [{"elegidos": [0, 42, "x", 0], "motivo": "fianza"}]})
    cid = _consulta(s, "En marzo de 2019 dejé el piso y el casero no me devuelve la fianza.")
    dossier = await Orchestrator(s)._ingesta(_Run(cid, "eco"), _triage(cid), "El casero retiene la fianza.")
    assert router.calls == ["cribado"]
    lista = router.systems["cribado"]
    assert "LISTA CERRADA" in lista or "lista cerrada" in lista.lower()
    [art] = dossier.articulos_boe
    assert art.id_bloque == "a2" and "quince días" in art.texto_verbatim  # redacción de 2019, no la de 2020
    assert art.source_id == f"BOE:{LAU}:a2:1995-01-01" and art.reformado_tras_fecha_hechos
    [ev] = _eventos(s, cid, "descubrimiento")
    assert ev["descartados"] == 3 and ev["fecha"] == "2019-03-15" and ev["candidatos"] >= 1
    assert [e["origen"] for e in _eventos(s, cid, "source") if e["tipo"] == "boe"] == ["descubierto"]


async def test_hechos_recientes_usan_la_redaccion_vigente(db):
    s, _, _ = await _servicios(db, {"cribado": [{"elegidos": [0]}]})
    cid = _consulta(s, "Dejé el piso en mayo de 2026 y no me devuelven la fianza.")
    dossier = await Orchestrator(s)._ingesta(_Run(cid, "eco"), _triage(cid, date(2026, 5, 2)), "Fianza retenida.")
    assert "treinta días" in dossier.articulos_boe[0].texto_verbatim


async def test_si_el_cribado_falla_se_usan_los_mejor_puntuados_con_aviso(db):
    s, _, _ = await _servicios(db, {"cribado": [ProviderTimeout("sin respuesta", provider="x")] * 2})
    cid = _consulta(s, "En marzo de 2019 dejé el piso y el casero no me devuelve la fianza.")
    dossier = await Orchestrator(s)._ingesta(_Run(cid, "eco"), _triage(cid), "El casero retiene la fianza.")
    assert dossier.articulos_boe and dossier.articulos_boe[0].id_bloque == "a2"
    assert any("cribado de preceptos no respondió" in a for a in dossier.avisos)


async def test_lista_vacia_del_cribado_no_anade_nada(db):
    s, _, _ = await _servicios(db, {"cribado": [{"elegidos": []}]})
    cid = _consulta(s, "En marzo de 2019 dejé el piso y el casero no me devuelve la fianza.")
    dossier = await Orchestrator(s)._ingesta(_Run(cid, "eco"), _triage(cid), "El casero retiene la fianza.")
    assert dossier.articulos_boe == [] and dossier.cobertura == "degradada_sin_boe"


async def test_articulos_propuestos_de_memoria_no_se_piden_si_la_ley_esta_descargada(db):
    s, _, boe = await _servicios(db, {"cribado": [{"elegidos": [0]}]})
    cid = _consulta(s, "En marzo de 2019 dejé el piso y el casero no me devuelve la fianza.")
    normas_obj = [
        NormaObjetivo(id_norma=LAU, articulos=["99"], motivo="LAU (propuesta)"),  # el modelo «recordaba» un art. 99
        NormaObjetivo(id_norma=LAU, articulos=["1"], motivo="LAU"),  # catálogo: sí se pide
    ]
    boe.llamadas.clear()
    dossier = await Orchestrator(s)._ingesta(_Run(cid, "eco"), _triage(cid, normas=normas_obj), "Fianza.")
    assert not any(p.endswith("/bloque/a99") for p in boe.llamadas)
    assert {a.id_bloque for a in dossier.articulos_boe} == {"a1", "a2"}
    assert [e["origen"] for e in _eventos(s, cid, "source")] == ["catalogo", "descubierto"]


async def test_sin_ninguna_norma_verificable_no_hay_debate(db):
    """Sin BOE, sin corpus, sin sentencias ni convenios: mensaje fijo, sin llamar a Defensa/Contraparte/Magistrado."""
    s, router, _ = await _servicios(db, {"triaje": [TRIAJE_OK]}, con_corpus=False)

    def sin_red(request):
        raise httpx.ConnectError("sin red")

    s.boe = BOERepository(db, BOEClient(client=httpx.AsyncClient(transport=httpx.MockTransport(sin_red))))
    cid = s.store.create("Entregué las llaves el 1 de junio de 2026 y el casero no me devuelve la fianza.", "eco")
    await Orchestrator(s).run(cid)
    c = s.store.get(cid)
    assert c.estado == Estado.BLOQUEADA and router.calls == ["triaje"]
    [final] = _eventos(s, cid, "final")
    assert final["motivo"] == "sin_norma_verificable" and "no te doy una respuesta jurídica" in final["mensaje"]
    assert any(p["tipo_plazo_id"] == "CIV_FIANZA_DEVOLUCION_1M" for p in final["plazos"])  # el plazo sí se calcula
    assert final["postulacion"]


def test_busquedas_sin_identificadores_ni_articulos():
    assert limpiar_busquedas(["despido art. 54 ET", "BOE-A-2015-11430", "artículo 1902", "fianza", "Fianza", 3]) == [
        "despido ET",
        "fianza",
    ]
    assert indices_elegidos([2, "1", "[0]", {"n": 1}, 9, -1, True], 3) == [2, 1, 0]
