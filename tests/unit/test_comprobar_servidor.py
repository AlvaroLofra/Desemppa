"""Lanzador: sustituir un servidor antiguo de Desemppa sin tocar procesos ajenos (sin red ni procesos reales)."""

import pytest

from api.version_codigo import huella_codigo
from scripts import comprobar_servidor as cs

PROYECTO = str(cs.ROOT)
NUESTRO = f'"python.exe" "{PROYECTO}' + r'\.venv\Scripts\uvicorn.exe" api.main:app --host 127.0.0.1 --port 8000'


@pytest.fixture
def entorno(monkeypatch):
    estado = {"pids": {12544}, "remota": None, "procesos": {}, "matados": []}
    monkeypatch.setattr(cs, "_pids_escuchando", lambda p: set() if estado["matados"] else estado["pids"])
    monkeypatch.setattr(cs, "_version_remota", lambda p: estado["remota"])
    monkeypatch.setattr(cs, "_procesos", lambda: estado["procesos"])

    def run(args, **kw):
        if args[0] == "taskkill":
            estado["matados"].append(int(args[2]))

    monkeypatch.setattr(cs.subprocess, "run", run)
    monkeypatch.setattr(cs.time, "sleep", lambda s: None)
    return estado


def test_puerto_libre(entorno):
    entorno["pids"] = set()
    assert cs.main([]) == 0


def test_servidor_actual_solo_abre_navegador(entorno):
    entorno["remota"] = {"build": "x", "servidor": huella_codigo()}
    assert cs.main([]) == 2 and entorno["matados"] == []


def test_servidor_antiguo_de_este_proyecto_se_cierra_desde_la_raiz_del_arbol(entorno):
    entorno["remota"] = {"build": "x"}  # versión anterior: sin «servidor»
    entorno["procesos"] = {12544: (13344, NUESTRO), 13344: (14580, NUESTRO), 14580: (1, "cmd.exe")}
    assert cs.main([]) == 0 and entorno["matados"] == [13344]


def test_proceso_ajeno_no_se_toca(entorno):
    entorno["procesos"] = {12544: (1, r'"C:\otro\servidor.exe" --port 8000')}
    assert cs.main([]) == 3 and entorno["matados"] == []


def test_huella_estable_e_ignora_ficheros_personales(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "models.toml").write_text("a = 1", encoding="utf-8")
    h1 = huella_codigo(tmp_path)
    (tmp_path / "config" / "user_profiles.toml").write_text("b = 2", encoding="utf-8")
    assert huella_codigo(tmp_path) == h1
    (tmp_path / "config" / "models.toml").write_text("a = 2", encoding="utf-8")
    assert huella_codigo(tmp_path) != h1
