"""Aviso visible cuando un rol lo resuelve un modelo distinto del previsto (evento `quota` y «Modelos usados»)."""

from config.settings import load_catalog
from core.llm_types import LLMResult
from core.orchestrator import Orchestrator, _motivo_sustitucion
from core.state import Estado
from tests.unit.test_orchestrator import (  # noqa: F401 — `services` es un fixture
    ALEGATO,
    Q_BOE,
    TRIAJE_OK,
    ScriptedRouter,
    _events,
    magistrado,
    services,
)


def test_motivo_legible_del_primer_fallo():
    avisos = [
        "agy_gemini_flash devolvió una respuesta vacía; se repite una vez con el mismo modelo",
        "agy_gemini_flash no disponible (EmptyResponse); se degrada al siguiente modelo",
    ]
    assert _motivo_sustitucion(avisos) == "respuesta vacía"
    assert _motivo_sustitucion(["claude_cli: circuit breaker abierto, se omite claude_sonnet"]) == (
        "pausado tras varios fallos"
    )
    assert _motivo_sustitucion(["x no disponible (UsageLimitReached); se degrada"]) == "cuota agotada"
    assert _motivo_sustitucion([]) == "no disponible"


class SustitutoRouter(ScriptedRouter):
    """El Magistrado lo resuelve gemini_flash en lugar de agy_gemini_flash."""

    catalog = load_catalog(user_overrides=False)

    def resolve(self, profile, role):
        return self.catalog.profiles[profile].roles[role]

    async def stream(self, profile, role, request, **kw):
        async for item in super().stream(profile, role, request, **kw):
            if isinstance(item, LLMResult) and role == "magistrado":
                item = item.model_copy(
                    update={
                        "model": "gemini-3.8-flash",
                        "degradado": True,
                        "avisos": ["agy_gemini_flash no disponible (EmptyResponse); se degrada al siguiente modelo"],
                    }
                )
            yield item


async def test_sustitucion_se_avisa_en_progreso_y_en_modelos_usados(services):  # noqa: F811
    s, _ = services({})
    s.router = SustitutoRouter(
        {
            "triaje": [TRIAJE_OK],
            "defensa": [ALEGATO("DEFENSA", Q_BOE)],
            "contraparte": [ALEGATO("CONTRAPARTE", Q_BOE)],
            "magistrado": [magistrado()],
        }
    )
    cid = s.store.create("Entregué las llaves el 1 de junio de 2026 y el casero no me devuelve la fianza.", "eco")
    await Orchestrator(s).run(cid)
    c = s.store.get(cid)
    assert c.estado == Estado.CERTIFICADA, _events(s, cid)[-1]
    quota = [d for t, d in _events(s, cid) if t == "quota"]
    assert quota == [
        {
            "rol": "magistrado",
            "avisos": ["agy_gemini_flash no disponible (EmptyResponse); se degrada al siguiente modelo"],
            "modelo": "gemini-3.8-flash",
            "previsto": "gemini-3.8-flash-medium",
            "motivo": "respuesta vacía",
        }
    ]
    usados = c.dictamen["dictamen"]["modelos_usados"]
    assert usados["magistrado"] == "gemini-3.8-flash (en lugar de gemini-3.8-flash-medium: respuesta vacía)"
    assert usados["defensa"] == "fake-defensa"
