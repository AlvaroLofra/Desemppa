"""Errores tipados de proveedores LLM. `degradable` indica si el router debe probar un fallback."""

from __future__ import annotations

from datetime import datetime


class ProviderError(Exception):
    degradable = False

    def __init__(self, message: str, *, provider: str = "") -> None:
        super().__init__(message)
        self.provider = provider


class RateLimited(ProviderError):
    """429 / 503 persistente tras los reintentos, o límite RPD local alcanzado."""

    degradable = True

    def __init__(self, message: str, *, provider: str = "", retry_after: float | None = None) -> None:
        super().__init__(message, provider=provider)
        self.retry_after = retry_after


class UsageLimitReached(ProviderError):
    """Cuota de la suscripción agotada (ventana de 5 h / semanal de Claude Pro). Abre el circuit breaker."""

    degradable = True

    def __init__(self, message: str, *, provider: str = "", reset_at: datetime | None = None) -> None:
        super().__init__(message, provider=provider)
        self.reset_at = reset_at


class ProviderTimeout(ProviderError):
    degradable = True


class ModelUnavailable(ProviderError):
    """Modelo inexistente, retirado o proveedor no configurado (p. ej. sin clave)."""

    degradable = True


class NotAuthenticated(ProviderError):
    """El CLI de Claude no tiene sesión iniciada: el usuario debe ejecutar `claude` y `/login`."""

    degradable = True


class EmptyResponse(ProviderError):
    """El modelo terminó sin texto (p. ej. Antigravity intentó usar una herramienta y el modo no interactivo se la
    denegó). Es un fallo de esa llamada, no un error de programación: el router prueba el siguiente modelo."""

    degradable = True
