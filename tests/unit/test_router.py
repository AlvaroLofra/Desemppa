import pytest

from core.circuit_breaker import CircuitBreaker
from core.errors import NotAuthenticated, ProviderError, UsageLimitReached
from core.llm_types import LLMRequest, LLMResult, StreamChunk
from core.quota_ledger import QuotaLedger
from core.router import ModelRouter


class FakeBackend:
    """Respuesta por alias: lista de chunks + resultado, o una excepción."""

    def __init__(self, provider, behaviour=None):
        self.provider = provider
        self.behaviour = behaviour or {}
        self.calls = []

    async def stream(self, *, alias, request, spec=None, cli_model=None, timeout_s=None):
        self.calls.append((alias, request.effort))
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
            model=f"{alias}-id",
            latencia_ms=5,
            coste_equivalente_usd=0.01 if self.provider == "claude" else None,
        )


@pytest.fixture
def build(db, catalog):
    def _build(gemini=None, claude=None):
        g, c = FakeBackend("gemini", gemini), FakeBackend("claude", claude)
        breaker, ledger = CircuitBreaker(db), QuotaLedger(db)
        router = ModelRouter(catalog, gemini=g, claude=c, breaker=breaker, ledger=ledger)
        return router, g, c, breaker, ledger

    return _build


async def _run(router, mode, role):
    return [i async for i in router.stream(mode, role, LLMRequest(prompt="p"), fase="test")]


def test_router_maps_roles_per_mode(build):
    router, *_ = build()
    assert router.resolve("eco", "magistrado").model == "gemini_flash"
    assert router.resolve("equilibrado", "magistrado").model == "claude_sonnet"
    assert router.resolve("pro", "magistrado").model == "claude_opus"
    assert router.resolve("pro", "defensa").model == "claude_sonnet"
    with pytest.raises(ValueError):
        router.resolve("turbo", "magistrado")


def test_candidates_chain(build):
    router, *_ = build()
    assert router.candidates("claude_opus") == [
        "claude_opus",
        "claude_sonnet",
        "gemini_flash",
        "gemini_flash_lite",
        "gemini_flash_38",
    ]


async def test_happy_path_uses_profile_effort_and_records_ledger(build, db):
    router, g, c, *_ = build()
    items = await _run(router, "pro", "magistrado")
    assert c.calls == [("claude_opus", "high")] and g.calls == []
    result = items[-1]
    assert isinstance(result, LLMResult) and not result.degradado
    row = db.execute("SELECT proveedor, modelo, effort, ok, rol FROM llm_calls_ledger").fetchone()
    assert tuple(row) == ("claude", "claude_opus-id", "high", 1, "magistrado")


async def test_breaker_opens_on_usage_limit_and_degrades_to_gemini(build):
    router, g, c, breaker, _ = build(claude={"claude_sonnet": UsageLimitReached("limit", provider="claude")})
    items = await _run(router, "equilibrado", "magistrado")
    result = items[-1]
    assert result.provider == "gemini" and result.alias == "gemini_flash" and result.degradado
    assert breaker.state("claude") == "open"
    assert any("UsageLimitReached" in a for a in result.avisos)

    # Siguiente consulta: ni siquiera intenta Claude.
    c.calls.clear()
    items = await _run(router, "pro", "magistrado")
    assert c.calls == [] and items[-1].provider == "gemini"
    assert any("circuit breaker abierto" in a for a in items[-1].avisos)


async def test_fallback_chain_within_gemini(build, db):
    router, g, *_ = build(
        gemini={
            "gemini_flash": UsageLimitReached("x", provider="gemini"),
        }
    )
    # UsageLimitReached de gemini abre su breaker: los demás gemini se omiten -> sin modelos.
    with pytest.raises(UsageLimitReached):
        await _run(router, "eco", "triaje")
    fails = db.execute("SELECT count(*) FROM llm_calls_ledger WHERE ok = 0").fetchone()[0]
    assert fails == 1


async def test_rate_limited_falls_back_to_next_flash(build):
    from core.errors import RateLimited

    router, g, *_ = build(
        gemini={
            "gemini_flash": RateLimited("503", provider="gemini"),
            "gemini_flash_lite": RateLimited("503", provider="gemini"),
        }
    )
    items = await _run(router, "eco", "triaje")
    assert items[-1].alias == "gemini_flash_38" and items[-1].degradado
    assert [a for a, _ in g.calls] == ["gemini_flash", "gemini_flash_lite", "gemini_flash_38"]


async def test_not_authenticated_degrades(build):
    router, *_ = build(claude={"claude_sonnet": NotAuthenticated("login", provider="claude")})
    items = await _run(router, "equilibrado", "magistrado")
    assert items[-1].provider == "gemini"


async def test_error_after_streaming_is_not_degraded(build):
    router, *_ = build(claude={"claude_sonnet": (["parcial"], UsageLimitReached("x", provider="claude"))})
    with pytest.raises(UsageLimitReached):
        await _run(router, "equilibrado", "magistrado")


async def test_non_degradable_error_raises(build):
    router, *_ = build(claude={"claude_sonnet": ProviderError("bug", provider="claude")})
    with pytest.raises(ProviderError):
        await _run(router, "equilibrado", "magistrado")
