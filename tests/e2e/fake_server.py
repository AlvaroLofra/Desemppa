"""Servidor real de Iuris-IA (FastAPI + web/dist + SSE + token + service worker) con LLM y BOE simulados.

  python tests/e2e/fake_server.py <puerto>    (usa IURIS_DATA_DIR e IURIS_WEB_DIST del entorno)

Solo sustituye lo externo (modelos y API del BOE): todo lo demás es el código de producción.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402
import uvicorn  # noqa: E402

from api.main import Services, build_services, create_app  # noqa: E402
from connectors.boe_client import BOEClient, BOERepository  # noqa: E402
from core.llm_types import LLMResult, StreamChunk  # noqa: E402
from tests.unit.test_orchestrator import ALEGATO, LAU, Q_BOE, TRIAJE_OK, magistrado  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"


class FakeRouter:
    """Responde a cualquier rol con JSON válido, en trozos (para ejercitar el streaming)."""

    def __init__(self, catalog: object) -> None:
        self.catalog = catalog

    async def stream(self, profile, role, request, **kw):  # type: ignore[no-untyped-def]
        if role == "nli":
            n = request.prompt.count("### Par")
            payload: object = {"resultados": [{"indice": i, "etiqueta": "ENTAILS"} for i in range(n)]}
        else:
            payload = {
                "triaje": TRIAJE_OK,
                "defensa": ALEGATO("DEFENSA", Q_BOE),
                "contraparte": ALEGATO("CONTRAPARTE", Q_BOE),
                "magistrado": magistrado(),
            }[role]
        text = json.dumps(payload, ensure_ascii=False)
        for i in range(0, len(text), 200):
            yield StreamChunk(text=text[i : i + 200])
        yield LLMResult(text=text, provider="gemini_api", alias="fake", model=f"fake-{role}")


def build_fake() -> Services:
    services = build_services()
    assert services.pipeline is not None
    xml = (FIXTURES / "boe" / "lau_a36.xml").read_bytes()
    meta = {
        "data": [
            {
                "identificador": LAU,
                "titulo": "LAU",
                "rango": {"texto": "Ley"},
                "ambito": {"texto": "Estatal"},
                "estatus_derogacion": "N",
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/metadatos"):
            return httpx.Response(200, json=meta)
        if request.url.path.endswith(f"{LAU}/texto/bloque/a36"):
            return httpx.Response(200, content=xml)
        return httpx.Response(404)

    services.pipeline.boe = BOERepository(
        services.pipeline.boe._con,  # noqa: SLF001
        BOEClient(
            client=httpx.AsyncClient(base_url="https://boe.test", transport=httpx.MockTransport(handler)), max_rps=1000
        ),
    )
    services.pipeline.router = FakeRouter(services.catalog)  # type: ignore[assignment]
    return services


if __name__ == "__main__":
    uvicorn.run(create_app(build_fake), host="127.0.0.1", port=int(sys.argv[1]), log_level="warning")
