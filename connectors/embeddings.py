"""Embeddings con la Gemini Embedding API (free tier). Sin modelos locales (restricción del proyecto)."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any, Literal, Protocol

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from core.errors import ModelUnavailable, RateLimited

TaskType = Literal["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"]


class Embedder(Protocol):
    model: str
    dim: int

    async def embed(self, texts: Sequence[str], task: TaskType) -> list[list[float]]: ...


class GeminiEmbedder:
    def __init__(
        self,
        api_key: str | None,
        *,
        model: str = "gemini-embedding-001",
        dim: int = 768,
        batch_size: int = 50,
        client: Any | None = None,
        max_retries: int = 3,
    ) -> None:
        if client is None and not api_key:
            raise ModelUnavailable("GEMINI_API_KEY no configurada: no hay embeddings", provider="gemini")
        self._client = client or genai.Client(
            api_key=api_key, http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=1))
        )
        self.model = model
        self.dim = dim
        self._batch = batch_size
        self._max_retries = max_retries

    async def embed(self, texts: Sequence[str], task: TaskType) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self._batch):
            chunk = list(texts[start : start + self._batch])
            vectors.extend(await self._embed_batch(chunk, task))
        return vectors

    async def _embed_batch(self, texts: list[str], task: TaskType) -> list[list[float]]:
        config = types.EmbedContentConfig(task_type=task, output_dimensionality=self.dim)
        for attempt in range(self._max_retries + 1):
            try:
                contents: Any = texts
                response = await self._client.aio.models.embed_content(
                    model=self.model, contents=contents, config=config
                )
                return [list(e.values or []) for e in response.embeddings or []]
            except genai_errors.APIError as exc:
                if exc.code in (429, 500, 503) and attempt < self._max_retries:
                    await asyncio.sleep(2 ** (attempt + 1))
                    continue
                if exc.code in (429, 503):
                    raise RateLimited(f"embeddings: {exc}", provider="gemini") from exc
                raise
        raise AssertionError("inalcanzable")
