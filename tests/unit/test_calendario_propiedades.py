"""Propiedades del motor de plazos sobre cientos de fechas (semilla fija, sin dependencias nuevas).

No repiten las reglas legales (eso lo hacen los golden y scripts/verificar_plazos.py): comprueban que el motor es
coherente consigo mismo en cualquier fecha de inicio, también en las que nadie probó a mano.
"""

from __future__ import annotations

import csv
import random
from datetime import date, timedelta

import pytest

from core.calendar_engine import CalendarEngine, PlazoError, _add_months, load_rules
from core.schemas import TipoComputo
from tests.conftest import ROOT

REGLAS = load_rules()
MADRID = "28079"
_rnd = random.Random(20261104)
FECHAS = sorted({date(2026, 1, 1) + timedelta(days=_rnd.randrange(0, 330)) for _ in range(120)})
NACIONALES = {
    date.fromisoformat(r["fecha"])
    for r in csv.DictReader((ROOT / "data" / "festivos" / "2026.csv").open(encoding="utf-8"))
    if r["ambito"] == "nacional"
}
HABILES = {TipoComputo.HABILES_PROCESAL, TipoComputo.HABILES_ADMINISTRATIVO, TipoComputo.HABILES_SOCIAL_CADUCIDAD}


@pytest.fixture(scope="module")
def motor() -> CalendarEngine:
    return CalendarEngine()


@pytest.mark.parametrize("regla", sorted(REGLAS), ids=sorted(REGLAS))
@pytest.mark.parametrize("municipio", [None, MADRID], ids=["sin_municipio", "madrid"])
def test_propiedades_en_todo_el_ano(motor, regla, municipio):
    r = REGLAS[regla]
    anterior = None
    for inicio in FECHAS:
        p = motor.compute(regla, inicio, municipio_ine=municipio, hoy=inicio)
        fin = p.fecha_limite_segura
        assert fin > inicio
        # Monótono: empezar más tarde nunca acaba antes.
        if anterior is not None:
            assert fin >= anterior, (inicio, fin, anterior)
        anterior = fin
        if r.prorroga_inhabil_final:
            # Con prórroga, el último día nunca es sábado, domingo ni fiesta nacional.
            assert fin.weekday() < 5 and fin not in NACIONALES, (inicio, fin)
        if r.computo == TipoComputo.HABILES_PROCESAL and not r.agosto_habil:
            assert fin.month != 8, (inicio, fin)
        if r.computo in HABILES:
            # Dos caminos distintos del motor (contar hacia delante y contar entre dos fechas) coinciden.
            assert p.dias_habiles_restantes == r.duracion, (inicio, fin)
        if r.computo == TipoComputo.MESES_FECHA_A_FECHA and r.agosto_habil:
            base = _add_months(inicio, r.duracion)
            assert base <= fin <= base + timedelta(days=6), (inicio, fin)
        if r.computo == TipoComputo.ANIOS_FECHA_A_FECHA and not r.prorroga_inhabil_final:
            assert (fin.month, fin.day) == (inicio.month, inicio.day) or (inicio.month, inicio.day) == (2, 29)


def test_fin_de_mes_no_desborda():
    assert _add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert _add_months(date(2024, 1, 31), 1) == date(2024, 2, 29)
    assert _add_months(date(2026, 8, 31), 6) == date(2027, 2, 28)


def test_anio_sin_calendario_cargado_avisa_y_no_falla(motor):
    p = motor.compute("SOC_DESPIDO_CADUCIDAD", date(2026, 12, 20), municipio_ine=MADRID, hoy=date(2026, 12, 20))
    assert p.fecha_limite_segura.year == 2027
    assert p.festivos_no_verificados or any("2027" in a for a in p.avisos)


def test_entradas_invalidas_se_rechazan(motor):
    with pytest.raises(PlazoError):
        motor.compute("NO_EXISTE", date(2026, 3, 2))
    with pytest.raises(PlazoError):
        motor.compute("SOC_DESPIDO_CADUCIDAD", date(2026, 3, 2), municipio_ine="99999")


def test_notificacion_en_agosto_no_vence_despues_que_el_1_de_septiembre(motor):
    """Regresión (04-11-2026): con agosto inhábil (CA_RECURSO_2M) se sumaba un mes entero por el agosto de la propia
    notificación y una del 15-08 vencía el 16-11, después que una del 01-09 (02-11)."""
    septiembre = motor.compute("CA_RECURSO_2M", date(2026, 9, 1)).fecha_limite_segura
    for dia in (1, 15, 30, 31):
        p = motor.compute("CA_RECURSO_2M", date(2026, 8, dia))
        assert p.fecha_limite_segura <= septiembre
        assert any("empieza el 1 de septiembre" in a for a in p.avisos)
