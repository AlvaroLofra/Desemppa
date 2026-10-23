from fastapi.testclient import TestClient

from api.main import build_services, create_app
from config.settings import Settings, load_catalog
from core.state import Estado


def _factory(tmp_path):
    holder = {}

    def factory():
        services = build_services(Settings(IURIS_DATA_DIR=str(tmp_path), GEMINI_API_KEY=""), load_catalog())
        services.cli_version = lambda exe: "2.1.291 (Claude Code)"
        holder["s"] = services
        return services

    return factory, holder


def _client(tmp_path, base_url="http://127.0.0.1:8000"):
    factory, holder = _factory(tmp_path)
    return TestClient(create_app(factory), base_url=base_url), holder


def test_estado(tmp_path):
    client, _ = _client(tmp_path)
    with client:
        body = client.get("/api/estado").json()
    prov = body["proveedores"]
    assert prov["gemini_api"]["instalado"] is False  # sin clave
    assert prov["claude_cli"]["breaker"]["estado"] == "closed"
    assert prov["claude_cli"]["uso_ultimas_5h"]["llamadas"] == 0
    assert prov["codex_cli"]["habilitado"] is False and prov["codex_cli"]["instalado"] is False
    assert "login" in prov["antigravity_cli"]
    assert body["modo_por_defecto"] == "equilibrado"
    assert body["modos"]["pro"]["roles"]["magistrado"] == {"model": "claude_opus", "effort": "high"}
    assert body["corpus"]["municipios"] > 8000 and 2026 in body["corpus"]["anios_festivos"]


def test_api_rejects_foreign_host_header(tmp_path):
    client, _ = _client(tmp_path, base_url="http://evil.example")
    with client:
        assert client.get("/api/estado").status_code == 400


def test_mutations_require_local_token(tmp_path):
    client, holder = _client(tmp_path)
    with client:
        r = client.post("/api/consultas", json={"texto": "El casero no me devuelve la fianza", "modo": "eco"})
        assert r.status_code == 403
        r = client.post(
            "/api/consultas",
            headers={"X-Iuris-Token": "malo"},
            json={"texto": "El casero no me devuelve la fianza", "modo": "eco"},
        )
        assert r.status_code == 403
        r = client.post(
            "/api/consultas",
            headers={"X-Iuris-Token": holder["s"].token},
            json={"texto": "El casero no me devuelve la fianza", "modo": "turbo"},
        )
        assert r.status_code == 422


def test_calendario_municipios_y_tipos(tmp_path):
    client, _ = _client(tmp_path)
    with client:
        r = client.get(
            "/api/calendario/plazo",
            params={"tipo": "SOC_DESPIDO_CADUCIDAD", "fecha_inicio": "2026-03-27", "municipio_ine": "28079"},
        )
        assert r.status_code == 200 and r.json()["fecha_limite_segura"] == "2026-04-28"
        assert (
            client.get("/api/calendario/plazo", params={"tipo": "NOPE", "fecha_inicio": "2026-01-01"}).status_code
            == 422
        )
        muni = client.get("/api/municipios", params={"q": "alcala de hen"}).json()
        assert muni[0]["nombre"].startswith("Alcalá de Henares")
        assert any(t["id"] == "CA_RECURSO_2M" for t in client.get("/api/calendario/tipos").json())


def test_upload_txt_and_sse_replay(tmp_path):
    client, holder = _client(tmp_path)
    with client:
        token = holder["s"].token
        r = client.post(
            "/api/adjuntos",
            headers={"X-Iuris-Token": token},
            files={"archivo": ("carta.txt", "Carta de despido disciplinario a D. Juan Pérez".encode(), "text/plain")},
        )
        assert r.status_code == 201 and r.json()["tipo"] == "carta_despido"
        p = holder["s"].pipeline
        cid = p.store.create("Texto de una consulta de prueba", "eco", adjuntos=[r.json()["adjunto_id"]])
        p.store.set_estado(cid, Estado.TRIAJE)
        p.bus.emit(cid, "phase", {"estado": "TRIAJE"})
        p.store.set_estado(cid, Estado.FUERA_DE_ALCANCE)
        p.bus.emit(cid, "final", {"estado": "FUERA_DE_ALCANCE"})
        assert client.get(f"/api/consultar/stream/{cid}").status_code == 403
        with client.stream("GET", f"/api/consultar/stream/{cid}", params={"token": token}) as s:
            body = "".join(s.iter_text())
        assert "event: phase" in body and "event: final" in body
        det = client.get(f"/api/consultas/{cid}").json()
        assert det["adjuntos"][0]["tipo"] == "carta_despido" and "Texto de una consulta" in det["texto"]
        assert client.get("/api/consultas").json()[0]["consulta_id"] == cid


def test_ajustes_perfiles_roundtrip(tmp_path, monkeypatch):
    import shutil

    import config.settings as cs

    cfg = tmp_path / "cfg"
    cfg.mkdir()
    for name in ("models.toml", "providers.toml", "profiles.toml"):
        shutil.copy(cs.CONFIG_DIR / name, cfg / name)
    monkeypatch.setattr(cs, "CONFIG_DIR", cfg)
    import api.main as am

    monkeypatch.setattr(am, "CONFIG_DIR", cfg)
    monkeypatch.setattr(am, "save_user_profiles", lambda body: cs.save_user_profiles(body, cfg))
    monkeypatch.setattr(am, "reset_user_profiles", lambda: cs.reset_user_profiles(cfg))
    monkeypatch.setattr(am, "load_catalog", lambda *a, **k: cs.load_catalog(cfg, **k))
    client, holder = _client(tmp_path)
    with client:
        token = {"X-Iuris-Token": holder["s"].token}
        data = client.get("/api/ajustes/perfiles").json()
        assert data["modos"]["eco"]["magistrado"]["model"] == "agy_gemini_flash"
        assert data["modelos"]["claude_opus"]["proveedor"] == "claude_cli"
        nuevo = {"eco": {"magistrado": {"model": "claude_opus", "effort": "high"}}}
        assert client.put("/api/ajustes/perfiles", json=nuevo).status_code == 403
        assert client.put("/api/ajustes/perfiles", json=nuevo, headers=token).status_code == 200
        assert holder["s"].router.resolve("eco", "magistrado").model == "claude_opus"
        malo = {"eco": {"magistrado": {"model": "fantasma", "effort": "low"}}}
        assert client.put("/api/ajustes/perfiles", json=malo, headers=token).status_code == 422
        assert client.delete("/api/ajustes/perfiles", headers=token).status_code == 200
        assert holder["s"].router.resolve("eco", "magistrado").model == "agy_gemini_flash"
        assert client.post("/api/proveedores/nope/detectar", headers=token).status_code == 404


def test_version_and_html_without_token(tmp_path, monkeypatch):
    import api.main as am

    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html><head></head><body>app</body></html>", encoding="utf-8")
    (dist / "version.json").write_text('{"build": "abc123"}', encoding="utf-8")
    (dist / "sw.js").write_text("// sw", encoding="utf-8")
    monkeypatch.setattr(am, "WEB_DIST", dist)
    factory, holder = _factory(tmp_path)
    with TestClient(create_app(factory), base_url="http://127.0.0.1:8000") as client:
        assert client.get("/api/version").json() == {"build": "abc123"}
        r = client.get("/")
        assert holder["s"].token not in r.text and "no-store" in r.headers["cache-control"]
        assert "no-store" in client.get("/sw.js").headers["cache-control"]
        assert client.get("/cualquier/ruta").text == r.text  # SPA fallback, también sin token


def test_rejected_token_is_logged(tmp_path):
    client, holder = _client(tmp_path)
    with client:
        r = client.post(
            "/api/consultas",
            headers={"X-Iuris-Token": "viejo"},
            json={"texto": "El casero no me devuelve la fianza", "modo": "eco"},
        )
        assert r.status_code == 403 and "distinto del actual" in r.json()["detail"]
    log = (tmp_path / "logs" / "iuris.log").read_text(encoding="utf-8")
    assert "403 token distinto del actual en POST /api/consultas" in log


def test_crear_consulta_valida_arranca_el_analisis(tmp_path):
    """Regresión: crear() era síncrono y asyncio.create_task fallaba con 'no running event loop' (500)."""
    from tests.e2e.fake_server import FakeRouter

    def factory():
        s = build_services(Settings(IURIS_DATA_DIR=str(tmp_path), GEMINI_API_KEY=""), load_catalog())
        s.cli_version = lambda exe: None
        s.pipeline.router = FakeRouter(s.catalog)
        return s

    with TestClient(create_app(factory), base_url="http://127.0.0.1:8000") as client:
        s = client.app.state.services
        r = client.post(
            "/api/consultas",
            headers={"X-Iuris-Token": s.token},
            json={"texto": "El casero no me devuelve la fianza de 900 euros", "modo": "eco"},
        )
        assert r.status_code == 201, r.text
        cid = r.json()["consulta_id"]
        with client.stream("GET", f"/api/consultar/stream/{cid}", params={"token": s.token}) as stream:
            body = "".join(stream.iter_text())
        assert "event: triage" in body and ("event: final" in body or "event: error" in body)
