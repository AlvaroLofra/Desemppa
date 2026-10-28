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
from core.materias import submaterias
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
    # Los campos críticos de CIV_LAU_FIANZA «constan» (citan una palabra de todas las consultas de prueba), para que
    # los tests de otras fases no se detengan a preguntar; las preguntas se prueban aparte.
    "campos_constan": [
        {"campo": c, "cita": "fianza"}
        for c in [
            "fecha de entrega de llaves",
            "importe de la fianza",
            "estado de la vivienda a la entrada (fotos o inventario)",
        ]
    ],
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
        "respuesta_directa": [
            {
                "texto": "Sí: pasado un mes desde que devolviste las llaves, la fianza genera interés a tu favor.",
                "tipo": "norma",
                "citas": [{"source_id": BOE_SID, "verbatim_quote": quote_boe}],
            }
        ],
        "resumen_ciudadano": [
            {"texto": resumen, "tipo": "razonamiento", "citas": [{"source_id": ROJ_SID, "verbatim_quote": Q_ROJ}]}
        ],
        "fortalezas": [
            {
                "texto": "Repintar por el uso ordinario no es imputable al inquilino.",
                "tipo": "razonamiento",
                "citas": [{"source_id": ROJ_SID, "verbatim_quote": Q_ROJ}],
            }
        ],
        "debilidades_contraparte": [],
        "riesgos_propios": [{"texto": "Tendrás que poder probar el estado inicial de la vivienda.", "tipo": "limite"}],
        "pasos_inmediatos": [{"texto": "Envía un burofax al casero reclamando la fianza.", "tipo": "consejo"}],
    }


class ScriptedRouter:
    def __init__(self, script):
        self.script = {k: list(v) for k, v in script.items()}
        self.calls = []
        self.systems = {}

    async def stream(self, profile, role, request, **kw):
        self.calls.append(role)
        self.systems[role] = request.system
        if role == "nli":
            n = request.prompt.count("### Par")
            payload = {"resultados": [{"indice": i, "etiqueta": "ENTAILS"} for i in range(n)]}
        else:
            payload = self.script[role].pop(0)
            if isinstance(payload, Exception):
                raise payload
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
    cid = s.store.create(
        "Me llamo Ana Pérez, DNI 12345678Z. Entregué las llaves el 1 de junio de 2026 y el casero no me "
        "devuelve la fianza por pintar.",
        "eco",
    )
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
    # nli ×3: inferencia de las afirmaciones para el ciudadano, hechos no constatados y fundamentos (G5)
    assert router.calls == ["triaje", "defensa", "contraparte", "magistrado", "nli", "nli", "nli"]
    # El texto para el ciudadano sale solo de afirmaciones verificadas, con su auditoría
    assert dictamen["respuesta_directa"].startswith("Sí: pasado un mes")
    assert {a["tipo"] for a in dictamen["afirmaciones"]} >= {"norma", "consejo", "limite"}
    assert all(e["resultado"] != "eliminada" for e in dictamen["auditoria"])


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
    cid = s.store.create(
        "Entregué las llaves el 1 de junio de 2026 y el casero no me devuelve la fianza por pintar la casa.", "eco"
    )
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
    cid = s.store.create(
        "Entregué las llaves el 1 de junio de 2026 y el casero no me devuelve la fianza por pintar la casa.", "eco"
    )
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
    cid = s.store.create(
        "Entregué las llaves el 1 de junio de 2026 y el casero no me devuelve la fianza por pintar la casa.", "eco"
    )
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
        "campos_constan": [
            {"campo": c, "cita": "despidieron"} for c in submaterias()["SOC_DESPIDO_DISC"].campos_criticos
        ],
    }
    s, _ = services({"triaje": [triaje]})
    cid = s.store.create("Soy camarero y me despidieron el 1 de junio de 2026.", "eco")
    t = await Orchestrator(s)._triaje(_Run(cid, "eco"))
    assert t is not None and t.convenio_aplicable == esperado


async def test_fecha_de_inicio_que_no_consta_se_descarta(services):
    from core.orchestrator import _Run

    inventada = {**TRIAJE_OK, "fecha_inicio_plazo": "2026-09-30", "fecha_hechos": "2026-09-30"}
    s, _ = services({"triaje": [inventada]})
    cid = s.store.create("Entregué las llaves el 1 de junio de 2026 y no me devuelven la fianza.", "eco")
    run = _Run(cid, "eco")
    t = await Orchestrator(s)._triaje(run)
    assert any("30/09/2026" in a for a in run.avisos)  # la inventada se descarta
    # y se usa la que el usuario escribió junto al evento («Entregué las llaves el 1 de junio»), avisándolo
    assert t is not None and t.alertas_plazo[0].fecha_inicio_computo == date(2026, 6, 1)
    assert any("01/06/2026" in a for a in run.avisos)


async def test_sin_fecha_junto_al_evento_se_pregunta(services):
    from core.orchestrator import _Run

    inventada = {**TRIAJE_OK, "fecha_inicio_plazo": "2026-09-30", "fecha_hechos": None}
    s, _ = services({"triaje": [inventada]})
    cid = s.store.create("El casero no me devuelve la fianza desde hace meses.", "eco")
    t = await Orchestrator(s)._triaje(_Run(cid, "eco"))
    assert t is None
    preguntas = next(d for tipo, d in _events(s, cid) if tipo == "clarification_needed")["preguntas"]
    assert any(p["id"] == "q_fecha" and p["texto"].startswith("Indica la fecha exacta") for p in preguntas)


async def test_fundamentos_duplicados_se_muestran_una_vez(services):
    duplicado = magistrado()
    fund = duplicado["cuestiones"][0]["fundamentos"]
    duplicado["cuestiones"][0]["fundamentos"] = [fund[0], fund[0], fund[1]]
    s, _ = services(
        {
            "triaje": [TRIAJE_OK],
            "defensa": [ALEGATO("DEFENSA", Q_BOE)],
            "contraparte": [ALEGATO("CONTRAPARTE", Q_BOE)],
            "magistrado": [duplicado],
        }
    )
    cid = s.store.create("Entregué las llaves el 1 de junio de 2026 y el casero no me devuelve la fianza.", "eco")
    await Orchestrator(s).run(cid)
    d = s.store.get(cid).dictamen["dictamen"]
    assert [f["source_id"] for f in d["fundamentos"]] == [BOE_SID, ROJ_SID]
    assert d["respuesta_directa"].startswith("Sí")


async def test_si_el_reintento_del_magistrado_falla_se_usa_la_primera_resolucion(services):
    from core.errors import ProviderTimeout

    s, router = services(
        {
            "triaje": [TRIAJE_OK],
            "defensa": [ALEGATO("DEFENSA", Q_BOE), ALEGATO("DEFENSA", Q_BOE)],
            "contraparte": [ALEGATO("CONTRAPARTE", Q_BOE), ALEGATO("CONTRAPARTE", Q_BOE)],
            # La primera resolución trae una cita inventada (fuerza el reintento) y el reintento agota el tiempo.
            "magistrado": [
                magistrado(quote_boe="texto que no aparece en la ley en absoluto, inventado"),
                ProviderTimeout("240 s", provider="antigravity_cli"),
            ],
        }
    )
    cid = s.store.create("Entregué las llaves el 1 de junio de 2026 y el casero no me devuelve la fianza.", "eco")
    await Orchestrator(s).run(cid)
    c = s.store.get(cid)
    assert c.estado == Estado.CERTIFICADA  # antes: ERROR por el timeout del reintento
    d = c.dictamen["dictamen"]
    assert [f["source_id"] for f in d["fundamentos"]] == [ROJ_SID]  # la cita inventada se descarta
    assert any("No se pudo repetir la resolución" in a for a in d["avisos"])


async def test_toda_consulta_civil_lleva_el_requisito_masc_al_dossier(services):
    from core.orchestrator import _Run

    s, _ = services({"triaje": [TRIAJE_OK]})
    cid = s.store.create("Entregué las llaves el 1 de junio de 2026 y no me devuelven la fianza.", "eco")
    t = await Orchestrator(s)._triaje(_Run(cid, "eco"))
    assert t is not None
    assert any(n.id_norma == "BOE-A-2025-76" and n.articulos == ["5", "10"] for n in t.normas_boe_objetivo)


async def test_con_municipio_elegido_no_se_pregunta_aunque_el_modelo_lo_haga_como_texto(services):
    from core.orchestrator import _Run

    triaje = {
        **TRIAJE_OK,
        "municipio": None,
        "grado_ambiguedad": 0.5,
        "datos_criticos_faltantes": ["municipio del juzgado"],
        "preguntas_aclaracion": [
            {"id": "q1", "texto": "¿En qué localidad está la vivienda?", "tipo_respuesta": "texto"},
            {"id": "q2", "texto": "¿En qué municipio está el juzgado?", "tipo_respuesta": "municipio"},
            {"id": "q3", "texto": "¿Cuándo entregaste las llaves?", "tipo_respuesta": "texto"},
            {"id": "q4", "texto": "¿Cuál es el importe de la fianza?", "tipo_respuesta": "importe"},
            {"id": "q5", "texto": "¿Hiciste fotos del piso al salir?", "tipo_respuesta": "si_no"},
        ],
    }
    s, router = services({"triaje": [triaje]})
    cid = s.store.create(
        "Entregué las llaves el 1 de junio de 2026 y no me devuelven la fianza de 900 euros.",
        "eco",
        municipio_ine="28079",
    )
    t = await Orchestrator(s)._triaje(_Run(cid, "eco"))
    assert t is None
    preguntas = next(d for tipo, d in _events(s, cid) if tipo == "clarification_needed")["preguntas"]
    assert [p["id"] for p in preguntas] == ["q5"]  # municipio, fecha e importe ya constaban
    assert "Madrid" in router.systems["triaje"] and "2026-06-01" in router.systems["triaje"]


async def test_sin_municipio_se_pregunta_una_sola_vez(services):
    from core.orchestrator import _Run

    triaje = {
        **TRIAJE_OK,
        "municipio": None,
        "preguntas_aclaracion": [
            {"id": "q1", "texto": "¿En qué ciudad vives?", "tipo_respuesta": "texto"},
            {"id": "q2", "texto": "¿Municipio del juzgado?", "tipo_respuesta": "municipio"},
        ],
    }
    s, router = services({"triaje": [triaje]})
    cid = s.store.create("Entregué las llaves el 1 de junio de 2026 y no me devuelven la fianza.", "eco")
    t = await Orchestrator(s)._triaje(_Run(cid, "eco"))
    assert t is None
    preguntas = next(d for tipo, d in _events(s, cid) if tipo == "clarification_needed")["preguntas"]
    municipio = [p for p in preguntas if p["tipo_respuesta"] == "municipio" or "ciudad" in p["texto"]]
    assert [p["id"] for p in municipio] == ["q_municipio"]
    assert "(ninguno)" not in router.systems["triaje"]  # la fecha escrita sí se pasa como conocida


def test_campos_criticos_sin_cita_literal_se_preguntan(tmp_path):
    """Un campo crítico solo cuenta como conocido si el modelo cita una frase LITERAL de la consulta."""
    from core.materias import submaterias
    from core.orchestrator import _preguntas_campos_criticos

    sub = submaterias()["CIV_LAU_FIANZA"]
    hechos = "Entregué las llaves el 1 de junio y el casero se queda los 900 euros de la fianza."
    constan = [
        {"campo": "importe de la fianza", "cita": "los 900 euros de la fianza"},  # literal: consta
        {
            "campo": "estado de la vivienda a la entrada (fotos o inventario)",
            "cita": "hice fotos al entrar",
        },  # inventada
    ]
    preguntas = _preguntas_campos_criticos(sub, constan, hechos, {"fecha": True}, [])
    textos = [p.texto for p in preguntas]
    assert textos == ["Indica estado de la vivienda a la entrada (fotos o inventario)"]


def test_campo_critico_tipo_si_no(tmp_path):
    from core.materias import submaterias
    from core.orchestrator import _preguntas_campos_criticos

    preguntas = _preguntas_campos_criticos(submaterias()["SOC_DESPIDO_IT"], [], "Me despidieron.", {}, [])
    baja = next(p for p in preguntas if "baja" in p.texto)
    assert baja.tipo_respuesta == "si_no"


def test_campo_disyuntivo_se_pregunta_con_opciones():
    """«¿se lo compraste a un comercio o a un particular?» no se contesta con sí o no (fallo real)."""
    from core.materias import submaterias
    from core.orchestrator import _preguntas_campos_criticos

    for sub in submaterias().values():
        for p in _preguntas_campos_criticos(sub, [], "", {}, []):
            if p.tipo_respuesta == "si_no":
                assert " o " not in p.texto.replace(" o no", ""), p.texto
    compra = next(
        p
        for p in _preguntas_campos_criticos(submaterias()["CIV_CONSUMO_GARANTIA"], [], "", {}, [])
        if "particular" in p.texto
    )
    assert compra.tipo_respuesta == "opcion" and compra.opciones and len(compra.opciones) == 2


@pytest.mark.parametrize(
    ("texto", "tipo", "opciones", "esperado", "esperadas"),
    [
        ("¿Te la entregaron en mano o por correo?", "si_no", None, "texto", None),
        ("¿Has reclamado o no?", "si_no", None, "si_no", None),
        ("¿Qué contrato tenías?", "si_no", ["Temporal", "Indefinido"], "opcion", ["Temporal", "Indefinido"]),
        ("¿Qué contrato tenías?", "opcion", None, "texto", None),
        ("¿Firmaste?", "opcion", ["Sí", "No", "No lo sé"], "si_no", None),
        ("¿Cuándo?", "fecha", ["ayer", "hoy"], "fecha", None),
    ],
)
def test_normalizar_pregunta(texto, tipo, opciones, esperado, esperadas):
    from core.orchestrator import normalizar_pregunta
    from core.schemas import PreguntaAclaratoria

    p = normalizar_pregunta(PreguntaAclaratoria(id="q", texto=texto, tipo_respuesta=tipo, opciones=opciones))
    assert (p.tipo_respuesta, p.opciones) == (esperado, esperadas)


def test_tipo_de_respuesta_desconocido_no_tumba_el_triaje():
    from core.schemas import HechoDeterminante, PreguntaAclaratoria

    assert (
        PreguntaAclaratoria.model_validate({"id": "q", "texto": "x", "tipo_respuesta": "si/no"}).tipo_respuesta
        == "texto"
    )
    assert HechoDeterminante.model_validate({"pregunta": "x", "tipo_respuesta": None}).tipo_respuesta == "texto"


async def test_segunda_ronda_no_repite_lo_ya_preguntado(services):
    """El Magistrado reformula una pregunta ya contestada (con «No lo sé»): no se vuelve a hacer."""
    from core.orchestrator import _Run

    s, _ = services({})
    cid = s.store.create("El casero no me devuelve la fianza.", "eco")
    s.store.add_aclaraciones(
        cid, [{"pregunta": "¿Hiciste inventario o fotos al entrar a la vivienda?", "respuesta": "No lo sé"}]
    )
    for e in (Estado.TRIAJE, Estado.INGESTA, Estado.DEBATE):
        s.store.set_estado(cid, e)
    m = magistrado()
    m["hechos_determinantes"] = [
        {"pregunta": "¿Firmaste un inventario al entrar en la vivienda?", "tipo_respuesta": "si_no"},
        {"pregunta": "¿Te entregaron la fianza en mano o por transferencia?", "tipo_respuesta": "si_no"},
    ]
    assert Orchestrator(s)._pedir_hechos_determinantes(_Run(cid, "eco"), {"magistrado": m})
    preguntas = next(d for tipo, d in _events(s, cid) if tipo == "clarification_needed")["preguntas"]
    assert [p["texto"] for p in preguntas] == ["¿Te entregaron la fianza en mano o por transferencia?"]
    assert preguntas[0]["tipo_respuesta"] == "texto"  # disyuntiva: nunca sí/no


@pytest.mark.parametrize(
    ("nueva", "previa", "duplicada"),
    [
        ("¿Estabas de baja médica cuando te despidieron?", "¿estabas de baja al ser despedido?", True),
        (
            "¿Firmaste un inventario al entrar en la vivienda?",
            "¿Hiciste inventario o fotos al entrar a la vivienda?",
            True,
        ),
        ("¿Te dieron la carta de despido?", "¿Cuál es la fecha de notificación del despido?", False),
        ("¿Has reclamado antes al banco?", "¿Qué tipo de producto contrataste con el banco?", False),
        ("¿Cuál es el importe de la fianza?", "¿Cuál es la fecha de entrega de llaves?", False),
    ],
)
def test_ya_preguntado(nueva, previa, duplicada):
    from core.orchestrator import ya_preguntado

    assert ya_preguntado(nueva, [previa]) is duplicada


async def test_tras_dos_fallos_el_magistrado_se_repite_con_argon(services):
    """Escalado dentro de la misma familia: Flash falla la verificación dos veces → una vez con Argon."""
    from types import SimpleNamespace

    falsa = "el arrendador podrá retener la fianza íntegra si la vivienda necesita pintura nueva"
    mala = magistrado(quote_boe=falsa)
    mala["cuestiones"][0]["fundamentos"] = mala["cuestiones"][0]["fundamentos"][:1]
    s, router = services(
        {
            "triaje": [TRIAJE_OK],
            "defensa": [ALEGATO("DEFENSA", Q_BOE)],
            "contraparte": [ALEGATO("CONTRAPARTE", Q_BOE)],
            "magistrado": [mala, mala, magistrado()],
        }
    )
    modelos: list[object] = []
    original = router.stream

    async def stream(profile, role, request, **kw):  # type: ignore[no-untyped-def]
        if role == "magistrado":
            modelos.append(kw.get("modelo"))
        async for x in original(profile, role, request, **kw):
            yield x

    router.stream = stream
    router.resolve = lambda modo, rol: SimpleNamespace(model="agy_gemini_flash")
    router.catalog = SimpleNamespace(models={"agy_gemini_argon": object()})
    cid = s.store.create(
        "Entregué las llaves el 1 de junio de 2026 y el casero no me devuelve la fianza por pintar la casa.", "eco"
    )
    await Orchestrator(s).run(cid)
    assert modelos == [None, None, "agy_gemini_argon"]
    c = s.store.get(cid)
    assert c.estado == Estado.CERTIFICADA
    assert any("agy_gemini_argon" in a for a in c.dictamen["dictamen"]["avisos"])


async def test_magistrado_sin_respuesta_se_repite_con_argon(services):
    """Flash agota el tiempo en el Magistrado → una vez con Argon (misma familia) en lugar de perder la consulta."""
    from types import SimpleNamespace

    from core.errors import ProviderTimeout

    s, router = services(
        {
            "triaje": [TRIAJE_OK],
            "defensa": [ALEGATO("DEFENSA", Q_BOE)],
            "contraparte": [ALEGATO("CONTRAPARTE", Q_BOE)],
            "magistrado": [ProviderTimeout("superó 240 s", provider="antigravity_cli"), magistrado()],
        }
    )
    router.resolve = lambda modo, rol: SimpleNamespace(model="agy_gemini_flash")
    router.catalog = SimpleNamespace(models={"agy_gemini_argon": object()})
    cid = s.store.create(
        "Entregué las llaves el 1 de junio de 2026 y el casero no me devuelve la fianza por pintar la casa.", "eco"
    )
    await Orchestrator(s).run(cid)
    c = s.store.get(cid)
    assert c.estado == Estado.CERTIFICADA
    assert any("no respondió" in a and "agy_gemini_argon" in a for a in c.dictamen["dictamen"]["avisos"])


async def test_la_banda_se_rebaja_si_el_cortafuegos_elimina_la_respuesta(services):
    m = magistrado()
    sid = next(c["source_id"] for a in m["respuesta_directa"] for c in a.get("citas", []))
    m["respuesta_directa"].append(
        {
            "texto": "La ley obliga al casero a pagar el doble de la fianza.",
            "tipo": "norma",
            "citas": [
                {"source_id": sid, "verbatim_quote": "el arrendador deberá abonar el doble de la fianza sin excepción"}
            ],
        }
    )
    s, _ = services(
        {
            "triaje": [TRIAJE_OK],
            "defensa": [ALEGATO("DEFENSA", Q_BOE)],
            "contraparte": [ALEGATO("CONTRAPARTE", Q_BOE)],
            "magistrado": [m, m],
        }
    )
    cid = s.store.create(
        "Entregué las llaves el 1 de junio de 2026 y el casero no me devuelve la fianza por pintar la casa.", "eco"
    )
    await Orchestrator(s).run(cid)
    d = s.store.get(cid).dictamen["dictamen"]
    assert any(e["seccion"] == "respuesta" and e["resultado"] == "eliminada" for e in d["auditoria"])
    assert any("solidez se ha rebajado" in a for a in d["avisos"])


async def test_doble_magistrado_con_discrepancia_ajusta_la_solidez(services):
    from types import SimpleNamespace

    a_favor = magistrado()
    en_contra = magistrado()
    for q in en_contra["cuestiones"]:
        q["estimacion"] = "CONTRAPARTE"
    s, router = services(
        {
            "triaje": [TRIAJE_OK],
            "defensa": [ALEGATO("DEFENSA", Q_BOE)],
            "contraparte": [ALEGATO("CONTRAPARTE", Q_BOE)],
            "magistrado": [a_favor, en_contra],
        }
    )
    router.catalog = SimpleNamespace(profiles={"eco": SimpleNamespace(magistrado_doble=True)}, models={})
    cid = s.store.create(
        "Entregué las llaves el 1 de junio de 2026 y el casero no me devuelve la fianza por pintar la casa.", "eco"
    )
    await Orchestrator(s).run(cid)
    d = s.store.get(cid).dictamen["dictamen"]
    assert router.calls.count("magistrado") == 2
    assert d["banda_solidez"] not in ("criterio_consolidado_favorable", "argumento_solido_sin_doctrina")
    assert any("no coinciden" in a for a in d["avisos"])
    assert d["sello"]["fuentes"] and all(len(f["sha256"]) == 64 for f in d["sello"]["fuentes"])


async def test_preguntas_aclaracion_nunca_superan_el_limite(services):
    from core.orchestrator import _Run

    triaje = {
        **TRIAJE_OK,
        "fecha_hechos": None,
        "fecha_inicio_plazo": None,
        "municipio": None,
        "grado_ambiguedad": 0.8,
        "campos_constan": [],
        "preguntas_aclaracion": [
            {"id": f"q{i}", "texto": f"¿Detalle adicional relevante número {i}?", "tipo_respuesta": "texto"}
            for i in range(1, 7)
        ],
    }
    s, _ = services({"triaje": [triaje]})
    cid = s.store.create("El casero no me devuelve el dinero.", "eco")
    t = await Orchestrator(s)._triaje(_Run(cid, "eco"))
    assert t is None
    assert s.store.get(cid).estado == Estado.ESPERANDO_ACLARACION
    preguntas = next(d for tipo, d in _events(s, cid) if tipo == "clarification_needed")["preguntas"]
    assert len(preguntas) == 5
    ids = [p["id"] for p in preguntas]
    assert ids[:2] == ["q_fecha", "q_municipio"]
    assert all(i.startswith("q_campo_") for i in ids[2:4])
    assert ids[4] == "q1"


@pytest.mark.parametrize(
    ("texto", "evento", "esperada"),
    [
        (
            "El 10 de marzo de 2026 compré una lavadora. Ha dejado de funcionar.",
            "fecha de compra o entrega",
            date(2026, 3, 10),
        ),
        ("Entregué las llaves el 1 de septiembre de 2026.", "fecha de entrega de llaves", date(2026, 9, 1)),
        # La única fecha va con otro hecho: no se usa
        ("Firmé el contrato el 1 de enero de 2020. Me subieron el alquiler.", "fecha de entrega de llaves", None),
        # Dos fechas candidatas: no se elige ninguna
        ("Compré una el 1 de marzo de 2026 y compré otra el 5 de marzo de 2026.", "fecha de compra", None),
    ],
)
def test_fecha_del_evento_solo_si_esta_en_la_misma_frase(texto, evento, esperada):
    from core.fechas_es import fecha_del_evento

    assert fecha_del_evento(texto, evento, date(2026, 10, 25)) == esperada


def test_toda_materia_con_plazo_pregunta_una_fecha_concreta():
    """Nada de «fecha del hecho principal» (V03 y V10 de la batería del 25-10-2026)."""
    for clave, sub in submaterias().items():
        if sub.plazos:
            assert any("fecha" in c.lower() for c in sub.campos_criticos), clave


def test_ninguna_submateria_penal_calcula_plazo_de_prescripcion():
    # El plazo de prescripción depende de la pena máxima del delito (art. 131.1 CP), que el sistema no puede fijar
    # sin el LLM: se informa con la cita literal en la hoja de ruta, nunca como fecha límite calculada.
    for clave, sub in submaterias().items():
        if clave.startswith("PEN_"):
            assert sub.plazos == [], clave


async def test_consulta_elaborada_sin_submateria_exacta_usa_fallback_jurisdiccion(services):
    from core.orchestrator import _Run

    triaje = {
        **TRIAJE_OK,
        "jurisdiccion_principal": "civil",
        "submateria_principal": "CIV_SERVIDUMBRE_PASO_ATIPICA",
        "ramas": [],
        "campos_constan": [
            {"campo": c, "cita": "1 de junio de 2026"} for c in submaterias()["CIV_GENERAL"].campos_criticos
        ],
    }
    s, _ = services({"triaje": [triaje]})
    cid = s.store.create(
        "El 1 de junio de 2026 mi vecino cerró el camino de paso hacia mi finca en Madrid (reclamo 1500 euros).",
        "eco",
        municipio_ine="28079",
    )
    t = await Orchestrator(s)._triaje(_Run(cid, "eco"))
    assert t is not None
    assert t.submateria_principal == "CIV_GENERAL"
    assert s.store.get(cid).estado != Estado.FUERA_DE_ALCANCE


async def test_consulta_penal_se_atiende_con_normas_del_codigo_penal_y_lecrim(services):
    from core.orchestrator import _Run

    triaje = {
        **TRIAJE_OK,
        "jurisdiccion_principal": "penal",
        "submateria_principal": "PEN_ESTAFAS_PATRIMONIO",
        "ramas": [{"submateria": "PEN_ESTAFAS_PATRIMONIO", "jurisdiccion": "penal", "peso_enrutamiento": 1.0}],
        "campos_constan": [
            {"campo": c, "cita": "1 de junio de 2026"} for c in submaterias()["PEN_ESTAFAS_PATRIMONIO"].campos_criticos
        ],
    }
    s, _ = services({"triaje": [triaje]})
    cid = s.store.create(
        "El 1 de junio de 2026 sufrí una estafa por phishing de 900 euros y quiero saber cómo denunciar.",
        "eco",
        municipio_ine="28079",
    )
    t = await Orchestrator(s)._triaje(_Run(cid, "eco"))
    assert t is not None
    assert t.submateria_principal == "PEN_ESTAFAS_PATRIMONIO"
    ids_normas = {n.id_norma for n in t.normas_boe_objetivo}
    assert {"BOE-A-1995-25444", "BOE-A-1882-6036"} <= ids_normas


async def test_normas_sugeridas_validas_se_incorporan_y_las_inventadas_se_descartan(services):
    from core.orchestrator import _Run

    triaje = {
        **TRIAJE_OK,
        "normas_sugeridas": [
            {"norma": "CC", "articulos": ["Art. 1454.1", "1124"]},
            {"norma": "ET", "articulos": ["34.8"]},
            {"norma": "LEY_INVENTADA_99", "articulos": ["1", "2"]},
        ],
    }
    s, _ = services({"triaje": [triaje]})
    cid = s.store.create("Entregué las llaves el 1 de junio de 2026 y no me devuelven la fianza.", "eco")
    t = await Orchestrator(s)._triaje(_Run(cid, "eco"))
    assert t is not None
    por_norma = {
        n.id_norma: [a for x in t.normas_boe_objetivo if x.id_norma == n.id_norma for a in x.articulos]
        for n in t.normas_boe_objetivo
    }
    assert "1454" in por_norma["BOE-A-1889-4763"]
    assert "34" in por_norma["BOE-A-2015-11430"]
    assert all("INVENTADA" not in n.motivo for n in t.normas_boe_objetivo)


@pytest.mark.parametrize(
    ("texto", "esperada"),
    [
        ("El 1 de junio de 2026 firmé un contrato de arras por 900 euros y el vendedor incumplió.", "CIV_GENERAL"),
        ("El 1 de junio de 2026 dejé el piso y mi casero no me devuelve la fianza.", "CIV_GENERAL"),
        ("El 1 de junio de 2026 la empresa cambió mi jornada y mi jefe no me paga.", "SOC_GENERAL"),
        ("¿Qué seguro de coche me recomiendas?", None),
        ("Dame una receta de paella valenciana.", None),
        ("Mi empresa organiza una cena el viernes, ¿qué me pongo?", None),
    ],
)
async def test_rescate_lexico_solo_con_pistas_juridicas_claras(services, texto, esperada):
    from core.orchestrator import _Run

    triaje = {
        **TRIAJE_OK,
        "jurisdiccion_principal": "fuera_alcance",
        "submateria_principal": "",
        "ramas": [],
        # El resumen lo escribe el LLM: su vocabulario jurídico no debe bastar para rescatar.
        "resumen_hechos": "El usuario plantea un problema legal de contrato, demanda e indemnización.",
        "campos_constan": [
            {"campo": c, "cita": "1 de junio de 2026"}
            for c in (submaterias()[esperada].campos_criticos if esperada else [])
        ],
    }
    s, _ = services({"triaje": [triaje]})
    cid = s.store.create(texto, "eco", municipio_ine="28079")
    t = await Orchestrator(s)._triaje(_Run(cid, "eco"))
    if esperada is None:
        assert t is None
        assert s.store.get(cid).estado == Estado.FUERA_DE_ALCANCE
    else:
        assert t is not None
        assert t.submateria_principal == esperada
        assert s.store.get(cid).estado != Estado.FUERA_DE_ALCANCE
