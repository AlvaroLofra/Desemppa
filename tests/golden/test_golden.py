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


@pytest.mark.parametrize(
    "caso",
    [
        CasoPostulacion(jurisdiccion="civil", procedimiento="monitorio", fase="inicial"),
        CasoPostulacion(jurisdiccion="civil", cuantia_eur=900),
        CasoPostulacion(jurisdiccion="civil", cuantia_eur=5000),
        CasoPostulacion(jurisdiccion="civil"),
    ],
)
def test_aviso_masc_civil_cita_lo_1_2025_sin_prometer_borradores(caso):
    r = evaluar(caso)
    assert "arts. 5 y 10 LO 1/2025" in r.base_legal
    assert "30 días naturales" in r.texto_usuario and "borrador" not in r.texto_usuario.lower()


def test_dias_habiles_restantes_solo_en_plazos_de_dias_habiles(engine):
    # Plazo en días hábiles: se cuentan los hábiles (menos que los naturales que quedan).
    habiles = engine.compute("CIV_APELACION_20H", date(2026, 6, 30), municipio_ine="08019", hoy=date(2026, 7, 1))
    assert habiles.dias_habiles_restantes is not None
    assert habiles.dias_habiles_restantes < (habiles.fecha_limite_segura - date(2026, 7, 1)).days
    # Plazo en años: no hay «días hábiles» que mostrar (antes se devolvían los naturales con esa etiqueta).
    anios = engine.compute("CIV_CONTRACTUAL_5A", date(2026, 9, 13), hoy=date(2026, 10, 24))
    assert anios.dias_habiles_restantes is None
