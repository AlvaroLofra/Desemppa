"""Compartir en la red local: quién entra, con qué token y qué puede hacer un invitado."""

import asyncio

import pytest
from fastapi.testclient import TestClient

from api.main import build_services, create_app
from api.red_local import EstadoRed, es_privada
from config.settings import Settings, load_catalog
from tests.e2e.fake_server import FakeRouter

IP_LAN = "192.168.1.10"
INVITADO = "invitado-abcdef12"
TEXTO = "El casero no me devuelve la fianza de 900 euros"


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(EstadoRed, "ip", lambda self: IP_LAN)

    def factory():
        s = build_services(Settings(IURIS_DATA_DIR=str(tmp_path), GEMINI_API_KEY=""), load_catalog())
        s.cli_version = lambda exe: None
        s.pipeline.router = FakeRouter(s.catalog)
        return s

    return create_app(factory)


def _dueno(app):
    return TestClient(app, base_url="http://127.0.0.1:8000")


def _invitado(app, ip="192.168.1.50"):
    return TestClient(
        app, base_url=f"http://{IP_LAN}:8000", client=(ip, 50000), headers={"X-Desemppa-Invitado": INVITADO}
    )


def _activar(dueno, **cambios):
    s = dueno.app.state.services
    r = dueno.put("/api/red", headers={"X-Iuris-Token": s.token}, json={"activo": True, **cambios})
    assert r.status_code == 200, r.text
    return r.json()


def test_lan_rechazada_mientras_la_red_esta_desactivada(app):
    with _dueno(app) as dueno, _invitado(app) as inv:
        assert inv.get("/api/version").status_code == 403
        assert dueno.get("/api/red").json()["activo"] is False


def test_solo_ips_privadas_y_host_de_este_equipo(app):
    assert es_privada("192.168.1.50") and es_privada("10.0.0.7") and not es_privada("8.8.8.8")
    with _dueno(app) as dueno:
        _activar(dueno)
        with _invitado(app, ip="8.8.8.8") as publico:
            assert publico.get("/api/version").status_code == 403
        with TestClient(app, base_url="http://evil.example:8000", client=("192.168.1.50", 1)) as rebinding:
            assert rebinding.get("/api/version").status_code == 400


def test_invitado_recibe_su_token_y_no_el_del_dueno(app):
    with _dueno(app) as dueno:
        _activar(dueno)
        s = dueno.app.state.services
        with _invitado(app) as inv:
            t = inv.get("/api/token").json()["token"]
            assert t != s.token and t == dueno.app.state.red.token_invitado
            assert inv.get("/api/sesion").json() == {"rol": "invitado", "modos_permitidos": ["eco"]}
            # El token del dueño no sirve desde la LAN
            r = inv.post("/api/consultas", headers={"X-Iuris-Token": s.token}, json={"texto": TEXTO, "modo": "eco"})
            assert r.status_code == 403


def test_invitado_sin_acceso_a_ajustes(app):
    with _dueno(app) as dueno:
        _activar(dueno)
        with _invitado(app) as inv:
            t = inv.get("/api/token").json()["token"]
            h = {"X-Iuris-Token": t}
            for metodo, ruta in [
                ("get", "/api/estado"),
                ("get", "/api/proveedores"),
                ("get", "/api/ajustes/perfiles"),
                ("get", "/api/red"),
                ("put", "/api/red"),
                ("delete", "/api/ajustes/perfiles"),
                ("post", "/api/modelos/agy_gemini_flash/probar"),
            ]:
                assert getattr(inv, metodo)(ruta, headers=h).status_code == 403, ruta


def test_modo_tope_y_consultas_ajenas(app):
    with _dueno(app) as dueno:
        _activar(dueno, tope_diario=1)
        s = dueno.app.state.services
        propia_dueno = s.pipeline.store.create(TEXTO, "pro")
        with _invitado(app) as inv:
            h = {"X-Iuris-Token": inv.get("/api/token").json()["token"]}
            r = inv.post("/api/consultas", headers=h, json={"texto": TEXTO, "modo": "pro"})
            assert r.status_code == 403 and "no está permitido" in r.json()["detail"]
            r = inv.post("/api/consultas", headers=h, json={"texto": TEXTO, "modo": "eco"})
            assert r.status_code == 201, r.text
            cid = r.json()["consulta_id"]
            asyncio.run(asyncio.sleep(0))
            r = inv.post("/api/consultas", headers=h, json={"texto": TEXTO, "modo": "eco"})
            assert r.status_code == 429
            # Solo ve lo suyo; lo del dueño ni se lista ni se abre
            assert [c["consulta_id"] for c in inv.get("/api/consultas").json()] == [cid]
            assert inv.get(f"/api/consultas/{propia_dueno}").status_code == 404
            assert inv.get(f"/api/consultas/{cid}").status_code == 200
        # El dueño ve todas, con la del invitado marcada
        todas = {c["consulta_id"]: c["invitado"] for c in dueno.get("/api/consultas").json()}
        assert todas == {cid: True, propia_dueno: False}


def test_el_dueno_puede_ampliar_los_modos(app):
    with _dueno(app) as dueno:
        cuerpo = _activar(dueno, modos_permitidos=["pro"])
        assert cuerpo["modos_permitidos"] == ["eco", "pro"]
        with _invitado(app) as inv:
            assert inv.get("/api/sesion").json()["modos_permitidos"] == ["eco", "pro"]
        s = dueno.app.state.services
        r = dueno.put("/api/red", headers={"X-Iuris-Token": s.token}, json={"activo": False})
        assert r.json()["activo"] is False
        with _invitado(app) as inv:
            assert inv.get("/api/version").status_code == 403
