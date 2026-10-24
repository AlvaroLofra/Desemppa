"""Compartir la app en la red local (opción temporal que el dueño activa en Ajustes).

El servidor puede escuchar en todas las interfaces, pero este middleware decide quién entra:
- Peticiones desde este ordenador (loopback): rol «dueño», con el `Host` limitado a 127.0.0.1/localhost.
- Peticiones desde otra IP: solo si la red está activada, la IP es privada (LAN) y el `Host` es la IP de este equipo.
  Rol «invitado»: token propio, solo modos permitidos, solo sus consultas y límites de uso.
Con la red desactivada (estado al arrancar) cualquier petición que no sea local recibe 403 sin llegar a la app.
"""

from __future__ import annotations

import ipaddress
import re
import secrets
import socket
import time
from dataclasses import dataclass, field
from typing import Any, Literal

from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send

Rol = Literal["dueno", "invitado"]
HOSTS_LOCALES = {"127.0.0.1", "localhost", "[::1]"}
INVITADO_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
_CLIENTE_TESTS = "testclient"  # Starlette TestClient no tiene IP: se trata como local


def ip_lan() -> str | None:
    """IP privada de este equipo en la red local (la de la ruta por defecto). No envía tráfico."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.254.254.254", 1))
            ip = str(s.getsockname()[0])
    except OSError:
        return None
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return None
    return ip if addr.is_private and not addr.is_loopback else None


def es_loopback(host: str | None) -> bool:
    if host == _CLIENTE_TESTS:
        return True
    try:
        return host is not None and ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def es_privada(host: str | None) -> bool:
    try:
        addr = ipaddress.ip_address(host or "")
    except ValueError:
        return False
    return addr.is_private and not addr.is_loopback and not addr.is_link_local


@dataclass
class EstadoRed:
    escucha_red: bool = False  # el servidor se arrancó en 0.0.0.0 (si no, activar no sirve de nada)
    puerto: int = 8000
    activo: bool = False
    modos_permitidos: set[str] = field(default_factory=lambda: {"eco"})
    tope_diario: int = 10
    token_invitado: str = field(default_factory=lambda: secrets.token_urlsafe(24))
    vistos: dict[str, float] = field(default_factory=dict)  # id de invitado -> última petición (monotonic)
    _ip: str | None = None
    _ip_leida: float = 0.0

    def ip(self) -> str | None:
        if time.monotonic() - self._ip_leida > 30:
            self._ip, self._ip_leida = ip_lan(), time.monotonic()
        return self._ip

    def url(self) -> str | None:
        ip = self.ip()
        return f"http://{ip}:{self.puerto}" if ip else None

    def invitados_activos(self, ventana_s: float = 120) -> int:
        ahora = time.monotonic()
        return sum(1 for t in self.vistos.values() if ahora - t <= ventana_s)

    def resumen(self) -> dict[str, Any]:
        return {
            "activo": self.activo,
            "escucha_red": self.escucha_red,
            "ip": self.ip(),
            "url": self.url(),
            "modos_permitidos": sorted(self.modos_permitidos),
            "tope_diario": self.tope_diario,
            "invitados_activos": self.invitados_activos(),
        }


def _host_sin_puerto(host_header: str) -> str:
    if host_header.startswith("["):
        return host_header.split("]")[0] + "]"
    return host_header.rsplit(":", 1)[0] if ":" in host_header else host_header


class RedLocalMiddleware:
    """Asigna el rol de cada petición y rechaza lo que no deba entrar (sustituye a TrustedHostMiddleware)."""

    def __init__(self, app: ASGIApp, estado: EstadoRed) -> None:
        self.app = app
        self.estado = estado

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        cliente = (scope.get("client") or (None, None))[0]
        headers = {k.decode("latin-1"): v.decode("latin-1") for k, v in scope.get("headers", [])}
        host = _host_sin_puerto(headers.get("host", ""))
        rol: Rol
        if es_loopback(cliente):
            # Protección frente a DNS rebinding: una web externa que resuelva a 127.0.0.1 llega con otro Host.
            if host not in HOSTS_LOCALES:
                await PlainTextResponse("Host no permitido", status_code=400)(scope, receive, send)
                return
            rol = "dueno"
        else:
            if not self.estado.activo or not es_privada(cliente):
                await PlainTextResponse("Desemppa no está compartida en la red", status_code=403)(scope, receive, send)
                return
            if host != self.estado.ip():
                await PlainTextResponse("Host no permitido", status_code=400)(scope, receive, send)
                return
            rol = "invitado"
            invitado = headers.get("x-desemppa-invitado", "")
            if INVITADO_RE.match(invitado):
                self.estado.vistos[invitado] = time.monotonic()
        scope.setdefault("state", {})["rol"] = rol
        await self.app(scope, receive, send)
