from fastapi.testclient import TestClient

from api.main import build_services, create_app
from config.settings import Settings, load_catalog


def _factory(tmp_path):
    def factory():
        services = build_services(Settings(IURIS_DATA_DIR=str(tmp_path), GEMINI_API_KEY=""), load_catalog())
        services.claude_version = lambda: "2.1.291 (Claude Code)"
        return services

    return factory


def test_estado(tmp_path):
    with TestClient(create_app(_factory(tmp_path)), base_url="http://127.0.0.1:8000") as client:
        body = client.get("/api/estado").json()
    assert body["claude_cli"]["version"].startswith("2.1")
    assert body["gemini"]["api_key_configurada"] is False
    assert body["circuit_breakers"]["claude"]["estado"] == "closed"
    assert body["uso_ultimas_5h"]["claude"]["llamadas"] == 0
    assert body["modo_por_defecto"] == "equilibrado"
    assert body["modos"]["pro"]["roles"]["magistrado"] == {"model": "claude_opus", "effort": "high"}


def test_api_rejects_foreign_host_header(tmp_path):
    with TestClient(create_app(_factory(tmp_path)), base_url="http://evil.example") as client:
        assert client.get("/api/estado").status_code == 400
