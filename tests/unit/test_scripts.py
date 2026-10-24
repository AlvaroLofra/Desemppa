"""Pruebas de humo de los scripts de importación (sin red: el BOE se simula)."""

from pathlib import Path

import pytest

from config.settings import get_settings
from scripts import importar_convenios_boe, importar_sentencias
from tests.unit.test_convenios_boe import CONVENIO


@pytest.fixture
def datos(tmp_path, monkeypatch):
    monkeypatch.setenv("IURIS_DATA_DIR", str(tmp_path / "datos"))
    monkeypatch.delenv("IURIS_SQLITE_PATH", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


def test_importar_sentencias_carpeta_inexistente(datos):
    assert importar_sentencias.main([str(datos / "no_existe")]) == 1


def test_importar_sentencias_importa_un_txt(datos, capsys):
    carpeta = datos / "pdfs"
    carpeta.mkdir()
    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "sentencias" / "sap_fianza_sintetica.txt"
    (carpeta / "s1.txt").write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")
    assert importar_sentencias.main([str(carpeta)]) == 0
    assert "1/1 sentencias importadas" in capsys.readouterr().out


def test_importar_convenios_rechaza_referencias_que_no_cuadran(datos, monkeypatch, capsys):
    from connectors import convenios_boe

    seed = [
        {
            "prioridad": 1,
            "denominacion": "Construcción",
            "sector": "Construcción",
            "territorio": "estatal",
            "codigo_regcon": "99005585011900",
            "boletin_ref": "BOE-A-2023-19903",
        },
        {
            "prioridad": 2,
            "denominacion": "Código equivocado",
            "sector": "Metal",
            "territorio": "estatal",
            "codigo_regcon": "99003435011981",
            "boletin_ref": "BOE-A-2023-19903",
        },
    ]
    monkeypatch.setattr(importar_convenios_boe, "load_seed", lambda: seed)
    monkeypatch.setattr(
        importar_convenios_boe, "descargar_documento", lambda ref, client: convenios_boe.parse_documento(ref, CONVENIO)
    )
    assert importar_convenios_boe.main([]) == 1  # hay un rechazado
    out = capsys.readouterr().out
    assert "1 correctos, 1 rechazados" in out and "99003435011981" in out
