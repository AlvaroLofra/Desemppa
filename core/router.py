"""ModelRouter: (modo, rol) -> alias -> proveedor, con circuit breaker y fallbacks (dossier §1.1)."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Protocol

from config.settings import Catalog, ModelSpec, RoleAssignment
from core.circuit_breaker import CircuitBreaker
from core.errors import ModelUnavailable, ProviderError, UsageLimitReached
from core.llm_types import LLMRequest, LLMResult, StreamChunk
from core.quota_ledger import QuotaLedger


class GeminiBackend(Protocol):
    def stream(
        self, *, alias: str, spec: ModelSpec, request: LLMRequest
    ) -> AsyncIterator[StreamChunk | LLMResult]: ...


class ClaudeBackend(Protocol):
    def stream(
        self, *, alias: str, cli_model: str, request: LLMRequest, timeout_s: float
    ) -> AsyncIterator[StreamChunk | LLMResult]: ...


class ModelRouter:
    def __init__(
        self,
        catalog: Catalog,
        *,
        gemini: GeminiBackend,
        claude: ClaudeBackend,
        breaker: CircuitBreaker,
        ledger: QuotaLedger,
    ) -> None:
        self.catalog = catalog
        self._gemini = gemini
        self._claude = claude
        self._breaker = breaker
        self._ledger = ledger

    def resolve(self, profile: str, role: str) -> RoleAssignment:
        try:
            roles = self.catalog.profiles[profile].roles
        except KeyError as exc:
            raise ValueError(f"modo desconocido: {profile}") from exc
        if role not in roles:
            raise ValueError(f"el modo '{profile}' no define el rol '{role}'")
        return roles[role]

    def candidates(self, alias: str) -> list[str]:
        """Alias principal seguido de sus fallbacks (recursivos, sin repetir)."""
        order: list[str] = []
        pending = [alias]
        while pending:
            current = pending.pop(0)
            if current in order:
                continue
            order.append(current)
            pending.extend(self.catalog.models[current].fallbacks)
        return order

    def _call(
        self, alias: str, spec: ModelSpec, request: LLMRequest
    ) -> AsyncIterator[StreamChunk | LLMResult]:
        if spec.provider == "gemini":
            return self._gemini.stream(alias=alias, spec=spec, request=request)
        assert spec.cli_model is not None
        return self._claude.stream(
            alias=alias, cli_model=spec.cli_model, request=request, timeout_s=spec.timeout_s
        )

    async def stream(
        self,
        profile: str,
        role: str,
        request: LLMRequest,
        *,
        fase: str | None = None,
        consulta_id: str | None = None,
    ) -> AsyncIterator[StreamChunk | LLMResult]:
        assignment = self.resolve(profile, role)
        primary = assignment.model
        avisos: list[str] = []
        last_error: ProviderError | None = None
        for alias in self.candidates(primary):
            spec = self.catalog.models[alias]
            if not self._breaker.allow(spec.provider):
                avisos.append(f"{spec.provider}: circuit breaker abierto, se omite {alias}")
                continue
            effort = assignment.effort if assignment.effort in spec.efforts else spec.efforts[-1]
            call_request = request.model_copy(update={"effort": effort})
            started = time.monotonic()
            emitted = False
            try:
                async for item in self._call(alias, spec, call_request):
                    if isinstance(item, LLMResult):
                        self._breaker.record_success(spec.provider)
                        self._ledger.record(
                            consulta_id=consulta_id, fase=fase or role, rol=role, proveedor=spec.provider,
                            modelo=item.model, effort=effort, input_tokens=item.usage.input_tokens,
                            output_tokens=item.usage.output_tokens,
                            coste_equivalente_usd=item.coste_equivalente_usd,
                            latencia_ms=item.latencia_ms, ok=True,
                        )
                        yield item.model_copy(
                            update={"degradado": alias != primary, "avisos": avisos + item.avisos}
                        )
                        return
                    emitted = True
                    yield item
            except ProviderError as exc:
                self._ledger.record(
                    consulta_id=consulta_id, fase=fase or role, rol=role, proveedor=spec.provider,
                    modelo=spec.model_id or spec.cli_model or alias, effort=effort,
                    latencia_ms=int((time.monotonic() - started) * 1000), ok=False,
                    error_tipo=type(exc).__name__,
                )
                if isinstance(exc, UsageLimitReached):
                    self._breaker.trip(spec.provider, reset_at=exc.reset_at, motivo=str(exc)[:200])
                else:
                    self._breaker.record_failure(spec.provider)
                if emitted or not exc.degradable:
                    raise
                avisos.append(f"{alias} no disponible ({type(exc).__name__}); se degrada al siguiente modelo")
                last_error = exc
        raise last_error or ModelUnavailable(
            f"ningún modelo disponible para {profile}/{role}: " + "; ".join(avisos)
        )
