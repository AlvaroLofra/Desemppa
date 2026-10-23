"""Golden tests de plazos y postulación (deben pasar al 100 %; pendientes de validación jurídica)."""

from datetime import date
from pathlib import Path

import pytest
import yaml

from core.calendar_engine import CalendarEngine
from core.postulacion_rules import CasoPostulacion, evaluar

HERE = Path(__file__).parent
PLAZOS = yaml.safe_load((HERE / "plazos.yaml").read_text(encoding="utf-8"))["casos"]
POSTULACION = yaml.safe_load((HERE / "postulacion.yaml").read_text(encoding="utf-8"))["casos"]


@pytest.fixture(scope="module")
def engine():
    return CalendarEngine()


@pytest.mark.parametrize("caso", PLAZOS, ids=[c["id"] for c in PLAZOS])
def test_golden_plazo(engine, caso):
    suspensiones = [(date.fromisoformat(str(a)), date.fromisoformat(str(b))) for a, b in caso.get("suspensiones", [])]
    p = engine.compute(
        caso["plazo"],
        caso["inicio"],
        municipio_ine=caso.get("ine"),
        suspensiones=suspensiones,
        territorio_foral=caso.get("foral"),
    )
    assert p.fecha_limite_segura == caso["limite"], caso.get("nota", "")
    if "gracia" in caso:
        assert p.dia_gracia_hasta is not None
        assert p.dia_gracia_hasta.date() == caso["gracia"] and p.dia_gracia_hasta.hour == 15
    else:
        assert p.dia_gracia_hasta is None
    if "aviso" in caso:
        assert any(caso["aviso"] in a for a in p.avisos)
    assert p.validado_juridicamente is False


@pytest.mark.parametrize("caso", POSTULACION, ids=[c["id"] for c in POSTULACION])
def test_golden_postulacion(caso):
    r = evaluar(CasoPostulacion(**caso["caso"]))
    assert (r.requiere_abogado, r.requiere_procurador, r.bloquea_escritos) == (
        caso["abogado"],
        caso["procurador"],
        caso["bloquea"],
    ), r.base_legal


def test_titular_del_plazo(engine):
    assert engine.compute("CIV_FIANZA_DEVOLUCION_1M", date(2026, 1, 31)).titular == "contraparte"
    assert engine.compute("SOC_DESPIDO_CADUCIDAD", date(2026, 3, 27), municipio_ine="28079").titular == "usuario"
