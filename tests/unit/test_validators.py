import pytest

from core.nli import NLIChecker, extract_json
from core.schemas import BandaSolidez as B
from core.schemas import DictamenCertificadoSchema
from core.validators import (
    EvidenciaBanda,
    cap_band,
    coherent_band,
    find_pronosticos,
    lower_band,
    verify_quote,
)

FUENTE = (
    "4. El saldo de la fianza en metálico que deba ser restituido al arrendatario al final del arriendo, "
    "devengará el interés legal, transcurrido un mes desde la entrega de las llaves por el mismo sin que se "
    "hubiere hecho efectiva dicha restitución."
)


def test_exact_quote_offsets_point_to_original():
    quote = "devengará el interés legal, transcurrido un mes desde la entrega de las llaves"
    r = verify_quote(quote, FUENTE)
    assert r.ok and r.score == 100
    assert FUENTE[r.offsets[0] : r.offsets[1]] == quote


def test_typographic_variants_still_match():
    quote = "«DEVENGARÁ  el interés legal,\ntranscurrido un mes desde la entrega de las llaves»"
    assert verify_quote(quote.replace("«", "").replace("»", ""), FUENTE).ok


@pytest.mark.parametrize(
    ("quote", "ok"),
    [
        ("devengará el interés legal, transcurrido un mes desde la entrega de las llaves", True),
        ("devengará el interés legal, transcurrido un mes desde la entrega de los llaves", True),  # 1 letra
        ("devengará el interés legal, transcurridos dos meses desde la entrega de las llaves", False),
        ("el arrendador podrá retener la fianza para pintar la vivienda tras el contrato", False),
    ],
)
def test_fuzzy_threshold_95(quote, ok):
    assert verify_quote(quote, FUENTE).ok is ok


def test_quote_must_match_declared_source():
    real = "devengará el interés legal, transcurrido un mes desde la entrega de las llaves"
    otra_fuente = "Artículo 1561. El arrendatario debe devolver la finca, al concluir el arriendo, tal como la recibió."
    assert not verify_quote(real, otra_fuente).ok


def test_min_quote_length():
    r = verify_quote("interés legal", FUENTE)
    assert not r.ok and "corta" in r.motivo


@pytest.mark.parametrize(
    ("text", "flag"),
    [
        ("Tienes un 78% de probabilidades de ganar.", True),
        ("La viabilidad estimada es del 80 %.", True),
        ("Hay un 90 por ciento de éxito en estos casos.", True),
        ("Ganarías con un 60% de seguridad", True),
        ("las posibilidades de prosperar rondan el 70%", True),
        ("Puedes pagar la multa con una reducción del 50 % en 20 días naturales.", False),
        ("El interés legal del dinero es del 3,25 %.", False),
        ("La indemnización es de 33 días por año trabajado.", False),
        ("El IVA aplicable es del 21%.", False),
        ("Tu argumento es sólido y hay doctrina favorable.", False),
    ],
)
def test_anti_percentage_regex(text, flag):
    assert bool(find_pronosticos(text)) is flag


def test_dictamen_schema_rejects_prognosis():
    from datetime import datetime

    base = dict(
        consulta_id="x",
        modo="eco",
        modelos_usados={},
        banda_solidez="no_determinable",
        fundamentos=[],
        aviso_legal="a",
        generado_en=datetime.now(),
    )
    with pytest.raises(ValueError):
        DictamenCertificadoSchema(resumen_ciudadano="Tienes un 78% de probabilidad de ganar", **base)
    DictamenCertificadoSchema(resumen_ciudadano="Pronto pago: reducción del 50 %", **base)


def test_band_ordering_never_upgrades():
    assert lower_band(B.CRITERIO_CONSOLIDADO_FAVORABLE) == B.ARGUMENTO_SOLIDO_SIN_DOCTRINA
    assert lower_band(B.NO_DETERMINABLE) == B.NO_DETERMINABLE
    assert cap_band(B.RIESGO_PROBATORIO_ALTO, B.DISPARIDAD_DE_CRITERIO) == B.RIESGO_PROBATORIO_ALTO
    assert cap_band(B.CRITERIO_CONSOLIDADO_FAVORABLE, B.DISPARIDAD_DE_CRITERIO) == B.DISPARIDAD_DE_CRITERIO
    assert cap_band(B.CRITERIO_CONSOLIDADO_DESFAVORABLE, B.NO_DETERMINABLE) == B.CRITERIO_CONSOLIDADO_DESFAVORABLE


def _ev(**kw):
    base = dict(
        citas_boe_verificadas=1,
        sentencias_favorables_ts=0,
        sentencias_favorables_ap=0,
        sentencias_desfavorables=0,
        nli_neutral=0,
        nli_contradice=0,
        doctrina_cambiante=False,
        cobertura_degradada=False,
        hechos_sin_prueba=False,
    )
    return EvidenciaBanda(**{**base, **kw})


@pytest.mark.parametrize(
    ("propuesta", "ev", "esperada"),
    [
        (B.CRITERIO_CONSOLIDADO_FAVORABLE, _ev(sentencias_favorables_ts=1), B.CRITERIO_CONSOLIDADO_FAVORABLE),
        (B.CRITERIO_CONSOLIDADO_FAVORABLE, _ev(sentencias_favorables_ap=2), B.CRITERIO_CONSOLIDADO_FAVORABLE),
        (B.CRITERIO_CONSOLIDADO_FAVORABLE, _ev(sentencias_favorables_ap=1), B.ARGUMENTO_SOLIDO_SIN_DOCTRINA),
        (
            B.CRITERIO_CONSOLIDADO_FAVORABLE,
            _ev(sentencias_favorables_ts=1, doctrina_cambiante=True),
            B.DISPARIDAD_DE_CRITERIO,
        ),
        (
            B.CRITERIO_CONSOLIDADO_FAVORABLE,
            _ev(sentencias_favorables_ts=1, sentencias_desfavorables=1),
            B.DISPARIDAD_DE_CRITERIO,
        ),
        (B.ARGUMENTO_SOLIDO_SIN_DOCTRINA, _ev(hechos_sin_prueba=True), B.RIESGO_PROBATORIO_ALTO),
        (
            B.CRITERIO_CONSOLIDADO_FAVORABLE,
            _ev(sentencias_favorables_ts=1, nli_neutral=1),
            B.ARGUMENTO_SOLIDO_SIN_DOCTRINA,
        ),
        (B.ARGUMENTO_SOLIDO_SIN_DOCTRINA, _ev(nli_neutral=1), B.ARGUMENTO_SOLIDO_SIN_DOCTRINA),
        (B.CRITERIO_CONSOLIDADO_FAVORABLE, _ev(nli_contradice=1), B.NO_DETERMINABLE),
        (B.ARGUMENTO_SOLIDO_SIN_DOCTRINA, _ev(citas_boe_verificadas=0), B.NO_DETERMINABLE),
        (B.DISPARIDAD_DE_CRITERIO, _ev(cobertura_degradada=True), B.DISPARIDAD_DE_CRITERIO),
        (B.CRITERIO_CONSOLIDADO_DESFAVORABLE, _ev(sentencias_favorables_ts=0), B.CRITERIO_CONSOLIDADO_DESFAVORABLE),
    ],
)
def test_band_never_upgraded_by_guardrails(propuesta, ev, esperada):
    banda, _ = coherent_band(propuesta, ev)
    assert banda == esperada


def test_extract_json_tolerates_fences():
    assert extract_json('Aquí va:\n```json\n{"a": 1}\n```') == {"a": 1}
    with pytest.raises(ValueError):
        extract_json("sin json")


async def test_nli_checker_parses_router_output():
    from core.llm_types import LLMResult

    class FakeRouter:
        async def stream(self, profile, role, request, **kw):
            assert role == "nli" and request.response_schema
            yield LLMResult(
                text='{"resultados": [{"indice": 1, "etiqueta": "CONTRADICTS"}, '
                '{"indice": 0, "etiqueta": "ENTAILS"}, {"indice": 9, "etiqueta": "ENTAILS"}]}',
                provider="gemini",
                alias="gemini_flash",
                model="m",
            )

    out = await NLIChecker(FakeRouter(), "eco").check([("p0", "h0"), ("p1", "h1"), ("p2", "h2")])
    assert [r.label for r in out] == ["ENTAILS", "CONTRADICTS", "NEUTRAL"]
