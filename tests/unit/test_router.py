import pytest

from core.circuit_breaker import CircuitBreaker
from core.errors import (
    EmptyResponse,
    ModelUnavailable,
    NotAuthenticated,
    ProviderError,
    RateLimited,
    UsageLimitReached,
)
from core.llm_types import LLMRequest, LLMResult, StreamChunk
from core.quota_ledger import QuotaLedger
from core.router import ModelRouter


class FakeBackend:
    """Respuesta por alias: lista de chunks + resultado, o una excepción."""

    def __init__(self, provider, behaviour=None):
        self.provider = provider
        self.behaviour = behaviour or {}
        self.calls = []

    async def stream(self, *, alias, spec, request):
        self.calls.append((alias, request.effort, spec.resolved_id(request.effort)))
        outcome = self.behaviour.get(alias)
        if isinstance(outcome, tuple):  # (chunks emitidos, excepción posterior)
            for text in outcome[0]:
                yield StreamChunk(text=text)
            raise outcome[1]
        if isinstance(outcome, Exception):
            raise outcome
        yield StreamChunk(text=f"[{alias}]")
        yield LLMResult(
            text=f"[{alias}]",
            provider=self.provider,
            alias=alias,
            model=spec.resolved_id(request.effort),
            latencia_ms=5,
        )


@pytest.fixture
def build(db, catalog):
    def _build(gemini=None, claude=None, agy=None, sin=(), respaldo="familia"):
        cat = catalog.model_copy(deep=True, update={"respaldo": respaldo})  # el fixture es de sesión: no se muta
        backends = {
            "gemini_api": FakeBackend("gemini_api", gemini),
            "claude_cli": FakeBackend("claude_cli", claude),
            "antigravity_cli": FakeBackend("antigravity_cli", agy),
        }
        for pid in sin:
            backends.pop(pid)
        breaker, ledger = CircuitBreaker(db), QuotaLedger(db)
        router = ModelRouter(cat, providers=backends, breaker=breaker, ledger=ledger)
        return router, backends, breaker

    return _build


async def _run(router, mode, role):
    return [i async for i in router.stream(mode, role, LLMRequest(prompt="p"), fase="test")]


def test_router_maps_roles_per_mode(build):
    router, *_ = build()
    assert router.resolve("eco", "magistrado").model == "agy_gemini_flash"
    assert router.resolve("eco", "triaje").model == "agy_gemini_flash"
    assert router.resolve("equilibrado", "magistrado").model == "claude_sonnet"
    assert router.resolve("pro", "magistrado").model == "agy_gemini_argon"
    with pytest.raises(ValueError):
        router.resolve("turbo", "magistrado")


def test_candidates_chain_crosses_providers(build):
    router, *_ = build()
    assert router.candidates("claude_opus") == [
        "claude_opus",
        "agy_claude_opus",
        "agy_gemini_argon",
        "claude_sonnet",
        "agy_claude_sonnet",
        "agy_gemini_flash",
        "gemini_flash",
        "agy_gpt_oss",
        "gemini_flash_lite",
    ]


async def test_happy_path_effort_in_model_id_and_ledger(build, db):
    router, b, _ = build()
    items = await _run(router, "eco", "magistrado")
    assert b["antigravity_cli"].calls == [("agy_gemini_flash", "medium", "gemini-3.8-flash-medium")]
    assert isinstance(items[-1], LLMResult) and not items[-1].degradado
    row = db.execute("SELECT proveedor, modelo, effort, ok FROM llm_calls_ledger").fetchone()
    assert tuple(row) == ("antigravity_cli", "gemini-3.8-flash-medium", "medium", 1)


async def test_agy_flash_and_argon_support_all_efforts(build):
    router, b, _ = build()
    await _run(router, "pro", "nli")  # nli = agy_gemini_flash low
    spec_flash = router.catalog.models["agy_gemini_flash"]
    spec_argon = router.catalog.models["agy_gemini_argon"]
    assert spec_flash.efforts == ["low", "medium", "high"]
    assert spec_argon.efforts == ["low", "medium", "high"]


async def test_usage_limit_opens_breaker_and_degrades_to_other_provider(build):
    router, b, breaker = build(claude={"claude_sonnet": UsageLimitReached("limit", provider="claude_cli")})
    items = await _run(router, "equilibrado", "magistrado")
    assert items[-1].provider == "antigravity_cli" and items[-1].alias == "agy_claude_sonnet"
    assert items[-1].degradado and breaker.state("claude_cli") == "open"
    b["claude_cli"].calls.clear()
    items = await _run(router, "pro", "defensa")  # claude_sonnet: breaker abierto -> ni se intenta
    assert b["claude_cli"].calls == [] and items[-1].alias == "agy_claude_sonnet"
    assert any("circuit breaker abierto" in a for a in items[-1].avisos)


async def test_disabled_provider_is_skipped(build):
    router, b, _ = build(sin=("antigravity_cli",), respaldo="cualquiera")
    items = await _run(router, "eco", "magistrado")
    assert items[-1].alias == "claude_sonnet"
    assert any("desactivado" in a for a in items[-1].avisos)


async def test_rate_limited_falls_back_to_other_family_then_other_provider(build):
    router, b, _ = build(
        agy={"agy_gemini_flash": RateLimited("503", provider="antigravity_cli")}, respaldo="cualquiera"
    )
    items = await _run(router, "eco", "triaje")
    assert items[-1].alias == "agy_claude_sonnet" and items[-1].degradado  # mismo plan, otra familia
    err = RateLimited("503", provider="antigravity_cli")
    router, b, _ = build(
        agy={"agy_gemini_flash": err, "agy_claude_sonnet": err, "agy_gpt_oss": err}, respaldo="cualquiera"
    )
    items = await _run(router, "eco", "triaje")
    assert items[-1].alias == "claude_sonnet" and items[-1].degradado


async def test_not_authenticated_degrades(build):
    router, *_ = build(claude={"claude_sonnet": NotAuthenticated("login", provider="claude_cli")})
    items = await _run(router, "equilibrado", "magistrado")
    assert items[-1].provider == "antigravity_cli"


async def test_error_after_streaming_is_not_degraded(build):
    router, *_ = build(claude={"claude_sonnet": (["parcial"], UsageLimitReached("x", provider="claude_cli"))})
    with pytest.raises(UsageLimitReached):
        await _run(router, "equilibrado", "magistrado")


async def test_non_degradable_error_raises(build):
    router, *_ = build(claude={"claude_sonnet": ProviderError("bug", provider="claude_cli")})
    with pytest.raises(ProviderError):
        await _run(router, "equilibrado", "magistrado")


async def test_everything_down_raises_last_error(build):
    err = RateLimited("x", provider="p")
    router, *_ = build(
        agy={"agy_gemini_flash": err, "agy_claude_sonnet": err, "agy_gpt_oss": err},
        claude={"claude_sonnet": err},
        gemini={"gemini_flash": err, "gemini_flash_lite": err},
        respaldo="cualquiera",
    )
    with pytest.raises(RateLimited):
        await _run(router, "eco", "triaje")


async def test_restartable_mid_stream_failure_moves_to_next_model(build):
    router, b, _ = build(
        agy={"agy_gemini_flash": (['{"parcial'], RateLimited("503", provider="antigravity_cli"))},
        respaldo="cualquiera",
    )
    items = [i async for i in router.stream("eco", "triaje", LLMRequest(prompt="p"), fase="t", restartable=True)]
    assert items[-1].alias == "agy_claude_sonnet" and items[-1].degradado
    assert any("mitad de respuesta" in a for a in items[-1].avisos)


class EmptyOnce(FakeBackend):
    """Devuelve una respuesta vacía las primeras `veces` llamadas a cada alias de `vacios`."""

    def __init__(self, provider, vacios, veces=1):
        super().__init__(provider)
        self.pendientes = dict.fromkeys(vacios, veces)

    async def stream(self, *, alias, spec, request):
        if self.pendientes.get(alias, 0) > 0:
            self.pendientes[alias] -= 1
            self.calls.append((alias, request.effort, spec.resolved_id(request.effort)))
            raise EmptyResponse("vacía", provider=self.provider)
        async for item in super().stream(alias=alias, spec=spec, request=request):
            yield item


def test_familias_de_los_modelos(catalog):
    fam = {a: m.familia_modelo() for a, m in catalog.models.items()}
    assert fam["agy_gemini_flash"] == fam["agy_gemini_argon"] == fam["gemini_flash"] == "gemini"
    assert fam["agy_claude_sonnet"] == fam["claude_sonnet"] == fam["claude_opus"] == "claude"
    assert fam["anthropic_opus_api"] == "claude"
    assert fam["agy_gpt_oss"] == fam["codex_default"] == fam["openai_o3"] == "gpt"


def test_candidates_por_politica(build):
    router, *_ = build()
    assert router.candidates("agy_gemini_flash", "familia") == ["agy_gemini_flash", "gemini_flash", "gemini_flash_lite"]
    assert router.candidates("agy_claude_sonnet", "familia") == ["agy_claude_sonnet", "claude_sonnet"]
    assert router.candidates("claude_sonnet", "familia") == ["claude_sonnet", "agy_claude_sonnet"]
    assert router.candidates("agy_gemini_flash", "nunca") == ["agy_gemini_flash"]


async def test_respaldo_familia_no_salta_a_claude(build):
    err = RateLimited("503", provider="antigravity_cli")
    router, b, _ = build(agy={"agy_gemini_flash": err}, gemini={"gemini_flash": err, "gemini_flash_lite": err})
    with pytest.raises(ModelUnavailable, match="familia") as info:
        await _run(router, "eco", "magistrado")
    assert "agy_claude_sonnet" in str(info.value) and isinstance(info.value.__cause__, RateLimited)
    assert b["claude_cli"].calls == [] and all(c[0] == "agy_gemini_flash" for c in b["antigravity_cli"].calls)


async def test_respaldo_familia_pasa_a_otro_gemini(build):
    router, b, _ = build(agy={"agy_gemini_flash": RateLimited("503", provider="antigravity_cli")})
    items = await _run(router, "eco", "magistrado")
    assert items[-1].alias == "gemini_flash" and items[-1].degradado
    assert b["claude_cli"].calls == []


async def test_respaldo_familia_claude_cruza_de_plan(build):
    router, b, _ = build(claude={"claude_sonnet": UsageLimitReached("limit", provider="claude_cli")})
    items = await _run(router, "equilibrado", "magistrado")
    assert items[-1].alias == "agy_claude_sonnet" and items[-1].degradado


async def test_respaldo_nunca_falla_con_aviso(build):
    router, b, _ = build(agy={"agy_gemini_flash": RateLimited("503", provider="antigravity_cli")}, respaldo="nunca")
    with pytest.raises(ModelUnavailable, match="'nunca'"):
        await _run(router, "eco", "magistrado")
    assert b["gemini_api"].calls == [] and b["claude_cli"].calls == []


async def test_respaldo_por_modo_prevalece_sobre_el_global(build):
    router, b, _ = build(agy={"agy_gemini_flash": RateLimited("503", provider="antigravity_cli")})
    router.catalog.profiles["eco"].respaldo = "cualquiera"
    items = await _run(router, "eco", "magistrado")
    assert items[-1].alias == "agy_claude_sonnet"


async def test_respuesta_vacia_se_repite_una_vez_con_el_mismo_modelo(build, db):
    router, b, _ = build()
    b["antigravity_cli"] = EmptyOnce("antigravity_cli", ["agy_gemini_flash"])
    router.providers = b
    items = await _run(router, "eco", "magistrado")
    assert items[-1].alias == "agy_gemini_flash" and not items[-1].degradado
    assert [c[0] for c in b["antigravity_cli"].calls] == ["agy_gemini_flash", "agy_gemini_flash"]
    assert any("se repite una vez con el mismo modelo" in a for a in items[-1].avisos)
    assert [r[0] for r in db.execute("SELECT ok FROM llm_calls_ledger ORDER BY id")] == [0, 1]


async def test_dos_respuestas_vacias_pasan_al_siguiente_modelo(build):
    router, b, _ = build()
    b["antigravity_cli"] = EmptyOnce("antigravity_cli", ["agy_gemini_flash"], veces=2)
    router.providers = b
    items = await _run(router, "eco", "magistrado")
    assert [c[0] for c in b["antigravity_cli"].calls] == ["agy_gemini_flash", "agy_gemini_flash"]
    assert items[-1].alias == "gemini_flash" and items[-1].degradado


async def test_otros_errores_no_se_repiten(build):
    router, b, _ = build(agy={"agy_gemini_flash": RateLimited("503", provider="antigravity_cli")})
    await _run(router, "eco", "magistrado")
    assert [c[0] for c in b["antigravity_cli"].calls] == ["agy_gemini_flash"]
