"""Hoja de ruta determinista: cobertura del catálogo, coherencia con plazos y cifras siempre respaldadas por su cita."""

import asyncio

import pytest

from core.calendar_engine import CalendarEngine
from core.firewall import numeros_en
from core.hoja_de_ruta import cargar, hoja_de_ruta
from core.materias import normas, submaterias


def test_cada_submateria_dentro_del_alcance_tiene_hoja_de_ruta():
    hojas = cargar()
    faltan = [k for k, s in submaterias().items() if not s.fuera_alcance and not hojas.get(k)]
    assert faltan == []
    assert set(hojas) <= set(submaterias())


def test_normas_y_plazos_existen():
    reglas = CalendarEngine().rules
    for sub, pasos in cargar().items():
        for p in pasos:
            assert p.plazo is None or p.plazo in reglas, (sub, p.plazo)
            for b in p.base:
                assert b.norma in normas(), (sub, b.norma)
                assert len(b.cita) >= 30, (sub, b.cita)  # citas cortas no se pueden verificar con fiabilidad


def test_toda_cifra_del_texto_aparece_en_sus_citas():
    """El texto llano no puede añadir números que la ley citada no diga (la misma regla que el cortafuegos)."""
    for sub, pasos in cargar().items():
        for p in pasos:
            en_citas = set().union(*(numeros_en(b.cita) for b in p.base))
            sobrantes = numeros_en(p.titulo + " " + p.que_hacer) - en_citas - {1.0}  # «un/una» son artículos
            assert not sobrantes, (sub, p.titulo, sobrantes)


def test_resuelve_quien_y_fecha_del_motor():
    plazos = [
        {"tipo_plazo_id": "SOC_DESPIDO_CADUCIDAD", "fecha_limite_segura": "2026-11-18", "base_legal": "Art. 103 LRJS"}
    ]
    pasos = hoja_de_ruta("SOC_DESPIDO_DISC", plazos=plazos, requiere_abogado=False)
    assert pasos[0].fecha_limite == "2026-11-18" and pasos[0].quien_texto == "Lo puedes hacer tú"
    civil = hoja_de_ruta("CIV_LAU_FIANZA", requiere_abogado=True)
    assert civil[-1].quien_texto == "Necesitas abogado"
    assert hoja_de_ruta("FUERA_PENAL") == [] and hoja_de_ruta(None) == []


@pytest.mark.live
def test_live_todas_las_citas_estan_en_el_boe_vigente(tmp_path):
    from config.settings import get_settings
    from connectors.boe_client import BOEClient, BOERepository
    from scripts.verificar_hojas_de_ruta import verificar
    from storage.database import open_database

    con = open_database(get_settings().sqlite_path or tmp_path / "x.db")
    try:
        assert asyncio.run(verificar(BOERepository(con, BOEClient()))) == []
    finally:
        con.close()


def test_api_devuelve_la_hoja_de_ruta(tmp_path):
    from fastapi.testclient import TestClient

    from api.main import build_services, create_app
    from config.settings import Settings, load_catalog

    def factory():
        s = build_services(Settings(IURIS_DATA_DIR=str(tmp_path), GEMINI_API_KEY=""), load_catalog())
        s.cli_version = lambda exe: None
        return s

    with TestClient(create_app(factory), base_url="http://127.0.0.1:8000") as cli:
        pasos = cli.get("/api/hoja-de-ruta/ADM_TRAFICO_ORA").json()
        assert pasos[0]["plazo"] == "ADM_TRAFICO_ALEGACIONES_20N" and pasos[0]["escrito"] == "alegaciones_multa"
        assert all(b["cita"] for p in pasos for b in p["base"])
        assert cli.get("/api/hoja-de-ruta/NO_EXISTE").json() == []


def test_spike_agy_sin_flags_de_autoaprobacion():
    """Humo del script del spike: se importa y ninguna variante usa flags peligrosos."""
    from scripts.spike_agy_vacias import VARIANTES

    for args, _ in VARIANTES.values():
        assert not any("dangerously" in a for a in args)


def test_un_paso_de_una_redaccion_nueva_no_se_aplica_a_hechos_anteriores():
    from datetime import date

    titulos = lambda f: [p.titulo for p in hoja_de_ruta("CIV_LAU_FIANZA", fecha_hechos=f)]  # noqa: E731
    assert "Documento de finalización del arrendamiento" not in titulos(date(2026, 9, 1))
    assert "Documento de finalización del arrendamiento" in titulos(date(2026, 10, 20))
    assert "Documento de finalización del arrendamiento" not in titulos(None)  # sin fecha no se presume
