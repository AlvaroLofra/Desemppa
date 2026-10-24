"""Pipeline completo con LLM simulado (sin red): triaje -> ingesta -> debate -> guardarraíles."""

import json
from datetime import date

import httpx
import pytest

from connectors.boe_client import BOEClient, BOERepository
from connectors.cendoj_fetcher import CendojRepository
from connectors.convenios_db import ConveniosRepository
from connectors.retriever import HybridRetriever
from core.calendar_engine import CalendarEngine
from core.llm_types import LLMResult, StreamChunk
from core.orchestrator import Orchestrator, Services
from core.state import ConsultaStore, Estado, EventBus, TransicionInvalida
from tests.conftest import FIXTURES

LAU = "BOE-A-1994-26003"
BOE_SID = f"BOE:{LAU}:a36:2019-03-06"
ROJ_SID = "ROJ:SAP M 9999/2024"
Q_BOE = "devengará el interés legal, transcurrido un mes desde la entrega de las llaves"
Q_ROJ = "como la necesidad de repintar tras varios años de ocupación, no es imputable al arrendatario"

TRIAJE_OK = {
    "jurisdiccion_principal": "civil",
    "submateria_principal": "CIV_LAU_FIANZA",
    "ramas": [
        {"submateria": "CIV_LAU_FIANZA", "jurisdiccion": "civil", "peso_enrutamiento": 0.9, "justificacion": "fianza"}
    ],
    "grado_ambiguedad": 0.1,
    "preguntas_aclaracion": [],
    "datos_criticos_faltantes": [],
    "fecha_hechos": "2026-06-01",
    "fecha_inicio_plazo": "2026-06-01",
    "municipio": "Madrid",
    "vecindad_civil": "comun",
    "cuantia_estimada_eur": 900,
    "terminos_cendoj": ["fianza pintar"],
    "resumen_hechos": "El arrendador retiene la fianza de 900 euros alegando que hay que pintar la vivienda.",
}
ALEGATO = lambda rol, q: {  # noqa: E731
    "rol": rol,
    "pretension": "x",
    "cuestiones": [
        {
            "id": "C1",
            "argumentos": [
                {"afirmacion": "La fianza devenga interés.", "citas": [{"source_id": BOE_SID, "verbatim_quote": q}]}
            ],
        }
    ],
}


def magistrado(quote_boe=Q_BOE, resumen="Tienes argumentos sólidos para recuperar la fianza."):
    return {
        "cuestiones": [
            {
                "id": "C1",
                "enunciado": "¿Puede retenerse la fianza por pintar?",
                "tipo": "calificacion_juridica",
                "estimacion": "DEFENSA",
                "fundamentos": [
                    {
                        "afirmacion": "Pasado un mes desde la entrega de llaves la fianza devenga interés legal.",
                        "citas": [{"source_id": BOE_SID, "verbatim_quote": quote_boe}],
                    },
                    {
                        "afirmacion": "Repintar por el uso ordinario no es imputable al inquilino.",
                        "citas": [{"source_id": ROJ_SID, "verbatim_quote": Q_ROJ}],
                    },
                ],
            }
        ],
        "banda_propuesta": "criterio_consolidado_favorable",
        "razonamiento_banda": "doctrina AP",
        "resumen_ciudadano": resumen,
        "fortalezas": ["ley clara"],
        "debilidades_contraparte": [],
        "riesgos_propios": ["prueba del estado inicial"],
        "pasos_inmediatos": ["Envía un burofax"],
    }


class ScriptedRouter:
    def __init__(self, script):
        self.script = {k: list(v) for k, v in script.items()}
        self.calls = []

    async def stream(self, profile, role, request, **kw):
        self.calls.append(role)
        if role == "nli":
            n = request.prompt.count("### Par")
            payload = {"resultados": [{"indice": i, "etiqueta": "ENTAILS"} for i in range(n)]}
        else:
            payload = self.script[role].pop(0)
        text = json.dumps(payload, ensure_ascii=False)
        yield StreamChunk(text=text[:20])
        yield LLMResult(text=text, provider="gemini", alias="gemini_flash", model=f"fake-{role}")


@pytest.fixture
async def services(db):
    xml = (FIXTURES / "boe" / "lau_a36.xml").read_bytes()
    meta = {
        "data": [
            {
                "identificador": LAU,
                "titulo": "LAU",
                "rango": {"texto": "Ley"},
                "ambito": {"texto": "Estatal"},
                "estatus_derogacion": "N",
            }
        ]
    }

    def handler(request):
        if request.url.path.endswith("/metadatos"):
            return httpx.Response(200, json=meta)
        if request.url.path.endswith(f"{LAU}/texto/bloque/a36"):
            return httpx.Response(200, content=xml)
        return httpx.Response(404)

    boe = BOERepository(
        db,
        BOEClient(
            client=httpx.AsyncClient(
                base_url="https://www.boe.es/datosabiertos/api/legislacion-consolidada",
                transport=httpx.MockTransport(handler),
            ),
            max_rps=1000,
        ),
    )
    cendoj = CendojRepository(db)
    await cendoj.import_text((FIXTURES / "sentencias" / "sap_fianza_sintetica.txt").read_text(encoding="utf-8"))

    def build(script):
        router = ScriptedRouter(script)
        return Services(
            router=router,
            boe=boe,
            retriever=HybridRetriever(db),
            cendoj=cendoj,
            convenios=ConveniosRepository(db),
            calendar=CalendarEngine(),
            store=ConsultaStore(db),
            bus=EventBus(db),
            today=lambda: date(2026, 6, 10),
        ), router

    return build


def _events(s, cid):
    return [(t, d) for _, t, d in s.bus.history(cid)]


async def test_full_pipeline_certifies(services):
    s, router = services(
        {
            "triaje": [TRIAJE_OK],
            "defensa": [ALEGATO("DEFENSA", Q_BOE)],
            "contraparte": [ALEGATO("CONTRAPARTE", Q_BOE)],
            "magistrado": [magistrado()],
        }
    )
    cid = s.store.create("Me llamo Ana Pérez, DNI 12345678Z. El casero no me devuelve la fianza por pintar.", "eco")
    assert "12345678Z" not in s.store.get(cid).texto_seudonimizado
    await Orchestrator(s).run(cid)
    c = s.store.get(cid)
    assert c.estado == Estado.CERTIFICADA, _events(s, cid)[-1]
    dictamen = c.dictamen["dictamen"]
    assert dictamen["banda_solidez"] == "argumento_solido_sin_doctrina"  # 1 SAP no es doctrina consolidada
    assert {f["source_id"] for f in dictamen["fundamentos"]} == {BOE_SID, ROJ_SID}
    plazo = next(p for p in dictamen["plazos"] if p["tipo_plazo_id"] == "CIV_FIANZA_DEVOLUCION_1M")
    assert plazo["fecha_limite_segura"] == "2026-07-01"
    assert dictamen["postulacion"]["bloquea_escritos"] is False  # 900 € <= 2.000 €
    tipos = [t for t, _ in _events(s, cid)]
    for t in ("triage", "source", "debate_done", "guardrail", "deadline", "final"):
        assert t in tipos
    assert router.calls == ["triaje", "defensa", "contraparte", "magistrado", "nli"]


async def test_fabricated_quote_triggers_single_retry_then_certifies(services):
    falsa = "el arrendador podrá retener la fianza íntegra si la vivienda necesita pintura nueva"
    s, router = services(
        {
            "triaje": [TRIAJE_OK],
            "defensa": [ALEGATO("DEFENSA", Q_BOE)],
            "contraparte": [ALEGATO("CONTRAPARTE", falsa)],
            "magistrado": [magistrado(quote_boe=falsa), magistrado()],
        }
    )
    cid = s.store.create("El casero no me devuelve la fianza por pintar la casa.", "eco")
    await Orchestrator(s).run(cid)
    assert router.calls.count("magistrado") == 2
    assert s.store.get(cid).estado == Estado.CERTIFICADA
    guard = [d for t, d in _events(s, cid) if t == "guardrail"]
    assert guard[0]["ok"] is False and guard[1]["ok"] is True


async def test_persistent_fabrication_blocks(services):
    falsa = "el arrendador podrá retener la fianza íntegra si la vivienda necesita pintura nueva"
    mala = magistrado(quote_boe=falsa)
    mala["cuestiones"][0]["fundamentos"] = mala["cuestiones"][0]["fundamentos"][:1]
    s, _ = services(
        {
            "triaje": [TRIAJE_OK],
            "defensa": [ALEGATO("DEFENSA", Q_BOE)],
            "contraparte": [ALEGATO("CONTRAPARTE", Q_BOE)],
            "magistrado": [mala, mala],
        }
    )
    cid = s.store.create("El casero no me devuelve la fianza por pintar la casa.", "eco")
    await Orchestrator(s).run(cid)
    c = s.store.get(cid)
    assert c.estado == Estado.BLOQUEADA
    assert c.dictamen["plazos"]  # los plazos se siguen mostrando


async def test_prognosis_is_removed_from_summary(services):
    s, _ = services(
        {
            "triaje": [TRIAJE_OK],
            "defensa": [ALEGATO("DEFENSA", Q_BOE)],
            "contraparte": [ALEGATO("CONTRAPARTE", Q_BOE)],
            "magistrado": [
                magistrado(resumen="Tienes un 90% de probabilidades de ganar."),
                magistrado(resumen="Tienes un 90% de probabilidades de ganar."),
            ],
        }
    )
    cid = s.store.create("El casero no me devuelve la fianza por pintar la casa.", "eco")
    await Orchestrator(s).run(cid)
    d = s.store.get(cid).dictamen["dictamen"]
    assert "90%" not in d["resumen_ciudadano"]


async def test_clarification_pauses_and_resumes(services):
    ambiguo = {
        **TRIAJE_OK,
        "fecha_inicio_plazo": None,
        "municipio": None,
        "grado_ambiguedad": 0.5,
        "preguntas_aclaracion": [{"id": "q1", "texto": "¿Cuándo entregaste las llaves?", "tipo_respuesta": "fecha"}],
    }
    s, router = services(
        {
            "triaje": [ambiguo, TRIAJE_OK],
            "defensa": [ALEGATO("DEFENSA", Q_BOE)],
            "contraparte": [ALEGATO("CONTRAPARTE", Q_BOE)],
            "magistrado": [magistrado()],
        }
    )
    cid = s.store.create("El casero no me devuelve la fianza.", "eco")
    await Orchestrator(s).run(cid)
    assert s.store.get(cid).estado == Estado.ESPERANDO_ACLARACION
    preguntas = next(d for t, d in _events(s, cid) if t == "clarification_needed")["preguntas"]
    assert {p["id"] for p in preguntas} >= {"q1", "q_municipio"}
    s.store.add_aclaraciones(
        cid, [{"pregunta": "llaves", "respuesta": "el 1 de junio de 2026", "municipio_ine": "28079"}]
    )
    await Orchestrator(s).run(cid)
    c = s.store.get(cid)
    assert c.estado == Estado.CERTIFICADA and c.municipio_ine == "28079"
    assert router.calls.count("triaje") == 2


async def test_out_of_scope(services):
    penal = {**TRIAJE_OK, "jurisdiccion_principal": "penal", "submateria_principal": "FUERA_PENAL", "ramas": []}
    s, router = services({"triaje": [penal]})
    cid = s.store.create("Me han robado el móvil y quiero denunciar.", "eco")
    await Orchestrator(s).run(cid)
    assert s.store.get(cid).estado == Estado.FUERA_DE_ALCANCE and router.calls == ["triaje"]


async def test_invalid_json_twice_reports_error(services):
    s, _ = services({"triaje": [{"x": 1}, {"y": 2}]})

    class Broken(type(s.router)):
        async def stream(self, profile, role, request, **kw):
            yield LLMResult(text="no es json", provider="gemini", alias="a", model="m")

    s.router = Broken({})
    cid = s.store.create("Consulta cualquiera de prueba.", "eco")
    await Orchestrator(s).run(cid)
    assert s.store.get(cid).estado == Estado.ERROR
    assert _events(s, cid)[-1][0] == "error"


def test_state_machine_rejects_invalid_transition(db):
    store = ConsultaStore(db)
    cid = store.create("texto de prueba suficiente", "eco")
    with pytest.raises(TransicionInvalida):
        store.set_estado(cid, Estado.CERTIFICADA)
    store.set_estado(cid, Estado.TRIAJE)
    store.set_estado(cid, Estado.INGESTA)


def test_event_bus_replay(db):
    bus = EventBus(db)
    store = ConsultaStore(db)
    cid = store.create("texto de prueba suficiente", "eco")
    bus.emit(cid, "phase", {"estado": "TRIAJE"})
    bus.emit(cid, "debate_delta", {"text": "x"})  # no se persiste
    bus.emit(cid, "final", {"ok": True})
    hist = bus.history(cid)
    assert [t for _, t, _ in hist] == ["phase", "final"]
    assert [t for _, t, _ in bus.history(cid, after=hist[0][0])] == ["final"]


def test_recover_interrupted(db):
    store = ConsultaStore(db)
    a = store.create("consulta interrumpida a medias", "eco")
    store.set_estado(a, Estado.TRIAJE)
    store.set_estado(a, Estado.INGESTA)
    b = store.create("consulta esperando aclaración", "eco")
    store.set_estado(b, Estado.TRIAJE)
    store.set_estado(b, Estado.ESPERANDO_ACLARACION)
    assert store.recover_interrupted() == 1
    assert store.get(a).estado == Estado.ERROR and store.get(b).estado == Estado.ESPERANDO_ACLARACION


@pytest.mark.parametrize(("propuesto", "esperado"), [("99010365011900", "99010365011900"), ("12345678901234", None)])
async def test_triaje_solo_acepta_convenios_indexados(services, db, propuesto, esperado):
    from core.orchestrator import _Run

    repo = ConveniosRepository(db)
    repo.upsert_convenio("99010365011900", "VI ALEH", "Hostelería", "estatal", prioridad=3)
    repo.add_version(
        "99010365011900", "Artículo 1. Ámbito.\nTexto.", boletin_ref="BOE-A-2023-6344", vigencia_desde=date(2023, 3, 10)
    )
    triaje = {
        **TRIAJE_OK,
        "jurisdiccion_principal": "social",
        "submateria_principal": "SOC_DESPIDO_DISC",
        "ramas": [{"submateria": "SOC_DESPIDO_DISC", "jurisdiccion": "social", "peso_enrutamiento": 1.0}],
        "convenio_aplicable": propuesto,  # un código inventado por el modelo debe descartarse
    }
    s, _ = services({"triaje": [triaje]})
    cid = s.store.create("Soy camarero y me han despedido.", "eco")
    t = await Orchestrator(s)._triaje(_Run(cid, "eco"))
    assert t is not None and t.convenio_aplicable == esperado
