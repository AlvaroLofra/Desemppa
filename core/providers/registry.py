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
from core.providers.http_adapter import AnthropicApiAdapter, ApiKeyStore, OpenAICompatibleAdapter


class ProviderAdapter(Protocol):
    id: str
    spec: ProviderSpec

    def stream(self, *, alias: str, spec: ModelSpec, request: LLMRequest) -> AsyncIterator[StreamChunk | LLMResult]: ...

    def installed(self) -> bool: ...

    def discover_models(self, timeout_s: float = 60) -> list[str]: ...

    def stop(self) -> None: ...


class GeminiApiAdapter:
    """Envuelve GeminiClient con la interfaz común y soporta clave guardada desde la UI."""

    def __init__(
        self,
        provider_id: str,
        spec: ProviderSpec,
        client: GeminiClient,
        catalog: Catalog,
        key_store: ApiKeyStore | None = None,
    ) -> None:
        self.id = provider_id
        self.spec = spec
        self.client = client
        self._catalog = catalog
        self._keys = key_store

    def _sync_key(self) -> None:
        if self._keys is not None and not self.client.configured:
            stored = self._keys.get(self.id, None)
            if stored:
                self.client.set_api_key(stored)

    def stream(self, *, alias: str, spec: ModelSpec, request: LLMRequest) -> AsyncIterator[StreamChunk | LLMResult]:
        self._sync_key()
        return self.client.stream(alias=alias, spec=spec, request=request)

    def installed(self) -> bool:
        self._sync_key()
        return self.client.configured

    def discover_models(self, timeout_s: float = 60) -> list[str]:
        return list(self.spec.modelos_conocidos) or sorted(
            {m.model_id for m in self._catalog.models.values() if m.provider == self.id}
        )

    def stop(self) -> None:
        return None


def build_registry(
    catalog: Catalog,
    settings: Settings,
    *,
    gemini: GeminiClient,
    popen: Callable[..., Any] = subprocess.Popen,
    exe_overrides: dict[str, str | None] | None = None,
    key_store: ApiKeyStore | None = None,
) -> dict[str, ProviderAdapter]:
    assert settings.claude_sandbox_dir is not None
    base_sandbox: Path = settings.claude_sandbox_dir.parent / "sandboxes"
    keys = key_store or ApiKeyStore(settings.data_dir / "provider_keys.bin")
    registry: dict[str, ProviderAdapter] = {}
    for pid, spec in catalog.providers.items():
        if not spec.habilitado:
            continue
        if spec.tipo == "api_gemini":
            registry[pid] = GeminiApiAdapter(pid, spec, gemini, catalog, key_store=keys)
        elif spec.tipo == "cli":
            registry[pid] = CliAdapter(
                pid,
                spec,
                sandbox_dir=base_sandbox / pid,
                lock_path=settings.data_dir / f"{pid}.lock",
                exe=(exe_overrides or {}).get(pid),
                popen=popen,
            )
        elif spec.tipo == "api_openai":
            registry[pid] = OpenAICompatibleAdapter(pid, spec, keys, catalog)
        elif spec.tipo == "api_anthropic":
            registry[pid] = AnthropicApiAdapter(pid, spec, keys, catalog)
    return registry
