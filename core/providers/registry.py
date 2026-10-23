"""Construye los adaptadores de proveedores a partir de config/providers.toml."""

from __future__ import annotations

import subprocess
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any, Protocol

from config.settings import Catalog, ModelSpec, ProviderSpec, Settings
from core.gemini_client import GeminiClient
from core.llm_types import LLMRequest, LLMResult, StreamChunk
from core.providers.cli_adapter import CliAdapter


class ProviderAdapter(Protocol):
    id: str
    spec: ProviderSpec

    def stream(self, *, alias: str, spec: ModelSpec, request: LLMRequest) -> AsyncIterator[StreamChunk | LLMResult]: ...

    def installed(self) -> bool: ...

    def discover_models(self, timeout_s: float = 60) -> list[str]: ...

    def stop(self) -> None: ...


class GeminiApiAdapter:
    """Envuelve GeminiClient con la interfaz común."""

    def __init__(self, provider_id: str, spec: ProviderSpec, client: GeminiClient, catalog: Catalog) -> None:
        self.id = provider_id
        self.spec = spec
        self.client = client
        self._catalog = catalog

    def stream(self, *, alias: str, spec: ModelSpec, request: LLMRequest) -> AsyncIterator[StreamChunk | LLMResult]:
        return self.client.stream(alias=alias, spec=spec, request=request)

    def installed(self) -> bool:
        return self.client.configured

    def discover_models(self, timeout_s: float = 60) -> list[str]:
        return sorted({m.model_id for m in self._catalog.models.values() if m.provider == self.id})

    def stop(self) -> None:
        return None


def build_registry(
    catalog: Catalog,
    settings: Settings,
    *,
    gemini: GeminiClient,
    popen: Callable[..., Any] = subprocess.Popen,
    exe_overrides: dict[str, str | None] | None = None,
) -> dict[str, ProviderAdapter]:
    assert settings.claude_sandbox_dir is not None
    base_sandbox: Path = settings.claude_sandbox_dir.parent / "sandboxes"
    registry: dict[str, ProviderAdapter] = {}
    for pid, spec in catalog.providers.items():
        if not spec.habilitado:
            continue
        if spec.tipo == "api_gemini":
            registry[pid] = GeminiApiAdapter(pid, spec, gemini, catalog)
        elif spec.tipo == "cli":
            registry[pid] = CliAdapter(
                pid,
                spec,
                sandbox_dir=base_sandbox / pid,
                lock_path=settings.data_dir / f"{pid}.lock",
                exe=(exe_overrides or {}).get(pid),
                popen=popen,
            )
        # "api_openai": reservado; se añadirá cuando haya clave (el router lo trata como no disponible).
    return registry
