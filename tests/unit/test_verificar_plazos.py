"""Plazos respaldados por su cita literal: la duración que calcula el motor tiene que estar en el artículo vigente."""

import asyncio
from datetime import date

import pytest
import yaml

from connectors.boe_models import Bloque, BloqueVersion
from core.calendar_engine import PLAZOS_PATH
from scripts.verificar_plazos import duracion_en_citas, verificar

TEXTO_LEC = (
    "Artículo 458. Interposición. 1. El recurso de apelación se interpondrá ante el tribunal que sea competente "
    "para conocer del mismo, en el plazo de veinte días desde la notificación de la resolución impugnada."
)
CITA = "en el plazo de veinte días desde la notificación de la resolución impugnada"


class BOEFalso:
    async def get_articulo(self, id_norma: str, articulo: str) -> Bloque:
        version = BloqueVersion(
            id_norma_modificadora=id_norma, fecha_publicacion=None, vigencia_desde=date(2000, 1, 8), texto=TEXTO_LEC
        )
        return Bloque(id_norma=id_norma, id_bloque=f"a{articulo}", versiones=[version])


def _plazo(duracion: int, cita: str = CITA, **extra):
    fuentes = [{"norma": "LEC", "articulo": "458", "cita": cita}] if cita else []
    return {"duracion": duracion, "computo": "habiles_procesal", "fuentes": fuentes, **extra}


@pytest.mark.parametrize(
    ("cita", "duracion", "computo", "esperado"),
    [
        ("dentro de los veinte días hábiles siguientes", 20, "habiles_social_caducidad", True),
        ("será de un mes, si el acto fuera expreso", 1, "meses_fecha_a_fecha", True),
        ("la acción caducará al año", 1, "anios_fecha_a_fecha", True),
        ("será de dos meses contados", 2, "meses_fecha_a_fecha", True),
        ("un plazo de veinte días naturales", 20, "naturales", True),
        ("dentro de los veinte días hábiles siguientes", 30, "habiles_procesal", False),
        ("prescriben por el transcurso de un año", 1, "meses_fecha_a_fecha", False),
        ("en los cinco artículos precedentes, a los seis meses", 5, "meses_fecha_a_fecha", False),
    ],
)
def test_duracion_en_citas(cita, duracion, computo, esperado):
    assert duracion_en_citas(duracion, computo, [cita]) is esperado


def test_verificar_detecta_cita_falsa_duracion_ajena_y_plazo_sin_fuentes():
    plazos = {
        "BIEN": _plazo(20),
        "CIFRA_AJENA": _plazo(30),
        "CITA_INVENTADA": _plazo(20, cita="en el plazo de veinte días desde que el juez lo considere oportuno ahora"),
        "SIN_FUENTES": _plazo(20, cita=""),
        "FORAL": _plazo(
            20, foral={"CT": {"duracion": 3, "fuentes": [{"norma": "LEC", "articulo": "458", "cita": CITA}]}}
        ),
    }
    fallos = asyncio.run(verificar(BOEFalso(), plazos))
    assert not any(f.startswith("BIEN") for f in fallos)
    assert any(f.startswith("CIFRA_AJENA") and "duración" in f for f in fallos)
    assert any(f.startswith("CITA_INVENTADA") and "no está" in f for f in fallos)
    assert any(f.startswith("SIN_FUENTES") for f in fallos)
    assert any(f.startswith("FORAL (CT)") for f in fallos)
    assert not any(f.startswith("FORAL:") for f in fallos)


def test_todos_los_plazos_llevan_fuentes_literales():
    plazos = yaml.safe_load(PLAZOS_PATH.read_text(encoding="utf-8"))["plazos"]
    for pid, p in plazos.items():
        assert p.get("fuentes"), pid
        for terr, f in (p.get("foral") or {}).items():
            assert f.get("fuentes"), f"{pid} ({terr})"


@pytest.mark.live
def test_live_todos_los_plazos_estan_en_el_boe_vigente(tmp_path):
    from config.settings import get_settings
    from connectors.boe_client import BOEClient, BOERepository
    from storage.database import open_database

    con = open_database(get_settings().sqlite_path or tmp_path / "x.db")
    try:
        assert asyncio.run(verificar(BOERepository(con, BOEClient()))) == []
    finally:
        con.close()
