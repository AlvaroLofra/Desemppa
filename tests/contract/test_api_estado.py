from fastapi.testclient import TestClient

from api.main import build_services, create_app
from config.settings import Settings, load_catalog
from core.state import Estado


def _factory(tmp_path):
    holder = {}

    def factory():
        services = build_services(Settings(IURIS_DATA_DIR=str(tmp_path), GEMINI_API_KEY=""), load_catalog())
        services.claude_version = lambda: "2.1.291 (Claude Code)"
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
    assert body["claude_cli"]["version"].startswith("2.1")
    assert body["gemini"]["api_key_configurada"] is False
    assert body["circuit_breakers"]["claude"]["estado"] == "closed"
    assert body["uso_ultimas_5h"]["claude"]["llamadas"] == 0
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
