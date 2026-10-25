"""ModelRouter: (modo, rol) -> alias -> proveedor, con circuit breaker y fallbacks (dossier §1.1).

La política de respaldo del modo (`Catalog.respaldo_de`) decide qué fallbacks se prueban: por defecto solo los de la
misma familia, para no gastar sin aviso la cuota de otra suscripción. Una respuesta vacía se reintenta una vez con el
mismo modelo antes de pasar al siguiente (suele ser un intento de herramienta denegado, no una caída del modelo)."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator, Mapping
from typing import Protocol

from config.settings import Catalog, ModelSpec, Respaldo, RoleAssignment
from core.circuit_breaker import CircuitBreaker
from core.errors import EmptyResponse, ModelUnavailable, ProviderError, UsageLimitReached
from core.llm_types import LLMRequest, LLMResult, StreamChunk
from core.quota_ledger import QuotaLedger


class Backend(Protocol):
    def stream(self, *, alias: str, spec: ModelSpec, request: LLMRequest) -> AsyncIterator[StreamChunk | LLMResult]: ...


class ModelRouter:
    def __init__(
        self,
        catalog: Catalog,
        *,
        providers: Mapping[str, Backend],
        breaker: CircuitBreaker,
        ledger: QuotaLedger,
    ) -> None:
        self.catalog = catalog
        self.providers = providers
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

    def candidates(self, alias: str, respaldo: Respaldo = "cualquiera") -> list[str]:
        """Alias principal seguido de sus fallbacks (recursivos, sin repetir) que permite la política de respaldo."""
        if respaldo == "nunca":
            return [alias]
        order: list[str] = []
        pending = [alias]
        while pending:
            current = pending.pop(0)
            if current in order:
                continue
            order.append(current)
            pending.extend(self.catalog.models[current].fallbacks)
        if respaldo == "familia":
            familia = self.catalog.models[alias].familia_modelo()
            order = [a for a in order if self.catalog.models[a].familia_modelo() == familia]
        return order

    def _call(self, alias: str, spec: ModelSpec, request: LLMRequest) -> AsyncIterator[StreamChunk | LLMResult]:
        return self.providers[spec.provider].stream(alias=alias, spec=spec, request=request)

    async def stream(
        self,
        profile: str,
        role: str,
        request: LLMRequest,
        *,
        fase: str | None = None,
        consulta_id: str | None = None,
        restartable: bool = False,
        modelo: str | None = None,
    ) -> AsyncIterator[StreamChunk | LLMResult]:
        """`restartable=True`: el llamante solo usa el resultado final (p. ej. JSON), así que un fallo a mitad
        de respuesta también puede pasar al siguiente modelo (el texto parcial ya emitido se descarta)."""
        assignment = self.resolve(profile, role)
        # `modelo`: sustituye al del modo para esta llamada (escalado tras fallos repetidos del cortafuegos).
        primary = modelo if modelo and modelo in self.catalog.models else assignment.model
        respaldo = self.catalog.respaldo_de(profile)
        candidatos = self.candidates(primary, respaldo)
        avisos: list[str] = []
        last_error: ProviderError | None = None
        for alias in candidatos:
            spec = self.catalog.models[alias]
            if spec.provider not in self.providers:
                avisos.append(f"{alias}: proveedor '{spec.provider}' desactivado o no configurado")
                continue
            if not self._breaker.allow(spec.provider):
                avisos.append(f"{spec.provider}: circuit breaker abierto, se omite {alias}")
                continue
            effort = assignment.effort if assignment.effort in spec.efforts else spec.efforts[-1]
            call_request = request.model_copy(update={"effort": effort})
            for repeticion in range(2):
                started = time.monotonic()
                emitted = False
                try:
                    async for item in self._call(alias, spec, call_request):
                        if isinstance(item, LLMResult):
                            self._breaker.record_success(spec.provider)
                            self._ledger.record(
                                consulta_id=consulta_id,
                                fase=fase or role,
                                rol=role,
                                proveedor=spec.provider,
                                modelo=item.model,
                                effort=effort,
                                input_tokens=item.usage.input_tokens,
                                output_tokens=item.usage.output_tokens,
                                coste_equivalente_usd=item.coste_equivalente_usd,
                                latencia_ms=item.latencia_ms,
                                ok=True,
                            )
                            yield item.model_copy(
                                update={"degradado": alias != primary, "avisos": avisos + item.avisos}
                            )
                            return
                        emitted = True
                        yield item
                except ProviderError as exc:
                    self._ledger.record(
                        consulta_id=consulta_id,
                        fase=fase or role,
                        rol=role,
                        proveedor=spec.provider,
                        modelo=spec.resolved_id(effort),
                        effort=effort,
                        latencia_ms=int((time.monotonic() - started) * 1000),
                        ok=False,
                        error_tipo=type(exc).__name__,
                    )
                    if isinstance(exc, UsageLimitReached):
                        self._breaker.trip(spec.provider, reset_at=exc.reset_at, motivo=str(exc)[:200])
                    else:
                        self._breaker.record_failure(spec.provider)
                    if (emitted and not restartable) or not exc.degradable:
                        raise
                    last_error = exc
                    if isinstance(exc, EmptyResponse) and not repeticion:
                        avisos.append(f"{alias} devolvió una respuesta vacía; se repite una vez con el mismo modelo")
                        continue
                    if emitted:
                        avisos.append(f"{alias} falló a mitad de respuesta ({type(exc).__name__}); se repite con otro")
                    else:
                        avisos.append(f"{alias} no disponible ({type(exc).__name__}); se degrada al siguiente modelo")
                    break
        excluidos = [a for a in self.candidates(primary) if a not in candidatos]
        if excluidos:
            # La política impidió probar otros modelos: se explica en el error para que el usuario lo vea.
            raise ModelUnavailable(
                f"{role}: {primary} no ha respondido y la política de respaldo '{respaldo}' no permite usar "
                f"{', '.join(excluidos)}. " + "; ".join(avisos),
                provider=last_error.provider if last_error else "",
            ) from last_error
        raise last_error or ModelUnavailable(f"ningún modelo disponible para {profile}/{role}: " + "; ".join(avisos))
