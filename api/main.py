"""Backend FastAPI local. Sprint 1: solo `GET /api/estado` (dossier Bloque 5, Sprint 1)."""

from __future__ import annotations

import subprocess
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from fastapi import FastAPI, Request
from starlette.middleware.trustedhost import TrustedHostMiddleware

from config.settings import Catalog, Settings, get_catalog, get_settings
from core.circuit_breaker import CircuitBreaker
from core.claude_worker import ClaudeWorker
from core.gemini_client import GeminiClient
from core.quota_ledger import QuotaLedger
from core.router import ModelRouter
from storage.database import open_database

ALLOWED_HOSTS = ["127.0.0.1", "localhost"]


@dataclass
class Services:
    settings: Settings
    catalog: Catalog
    breaker: CircuitBreaker
    ledger: QuotaLedger
    claude: ClaudeWorker
    gemini: GeminiClient
    router: ModelRouter
    claude_version: Callable[[], str | None]


@lru_cache(maxsize=1)
def _claude_version(exe: str | None) -> str | None:
    try:
        out = subprocess.run(
            [exe or "claude", "--version"], capture_output=True, text=True, timeout=15, check=True
        )
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def build_services(settings: Settings | None = None, catalog: Catalog | None = None) -> Services:
    settings = settings or get_settings()
    catalog = catalog or get_catalog()
    assert settings.sqlite_path is not None and settings.claude_sandbox_dir is not None
    con = open_database(settings.sqlite_path)
    breaker = CircuitBreaker(con, default_open_minutes=catalog.circuit_breaker.default_open_minutes)
    ledger = QuotaLedger(con)
    claude = ClaudeWorker(
        sandbox_dir=settings.claude_sandbox_dir, lock_path=settings.claude_lock_path, exe=settings.claude_exe
    )
    gemini = GeminiClient(
        settings.gemini_api_key,
        daily_count=ledger.daily_count,
        max_retries=catalog.circuit_breaker.gemini_max_retries,
    )
    router = ModelRouter(catalog, gemini=gemini, claude=claude, breaker=breaker, ledger=ledger)
    return Services(
        settings=settings, catalog=catalog, breaker=breaker, ledger=ledger, claude=claude,
        gemini=gemini, router=router, claude_version=lambda: _claude_version(settings.claude_exe),
    )


def create_app(services_factory: Callable[[], Services] = build_services) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        services = services_factory()
        app.state.services = services
        try:
            yield
        finally:
            services.claude.stop()

    app = FastAPI(title="Iuris-IA", version="0.1.0", lifespan=lifespan)
    # Protección frente a DNS rebinding: solo se aceptan peticiones dirigidas a loopback (dossier §2.5).
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)

    @app.get("/api/estado")
    def estado(request: Request) -> dict[str, Any]:
        s: Services = request.app.state.services
        return {
            "claude_cli": {"version": s.claude_version()},
            "gemini": {"api_key_configurada": s.gemini.configured},
            "circuit_breakers": {p: s.breaker.snapshot(p) for p in ("claude", "gemini")},
            "uso_ultimas_5h": {p: s.ledger.window_usage(p) for p in ("claude", "gemini")},
            "modo_por_defecto": s.catalog.default_profile(),
            "modos": {
                name: {
                    "label": p.label,
                    "llamadas_claude_por_consulta": p.claude_calls_per_query,
                    "roles": {r: a.model_dump() for r, a in p.roles.items()},
                }
                for name, p in s.catalog.profiles.items()
            },
            "modelos": {
                alias: {"proveedor": m.provider, "id": m.model_id or m.cli_model}
                for alias, m in s.catalog.models.items()
            },
        }

    return app


app = create_app()
