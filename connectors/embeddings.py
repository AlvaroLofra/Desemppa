"""Embeddings: Gemini Embedding API (si hay clave) o un modelo local ONNX en CPU con `fastembed` (extra opcional
`embeddings`, decisión del usuario del 04-11-2026). Sin ninguno de los dos, la búsqueda es solo léxica (BM25)."""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Sequence
from typing import Any, Literal, Protocol

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from core.errors import ModelUnavailable, RateLimited

log = logging.getLogger(__name__)
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


# Modelo local por defecto: multilingüe, 384 dimensiones, 0,22 GB (comprobado en `TextEmbedding.list_supported_models()`
# de fastembed 0.9.1 el 04-11-2026). Trunca a 128 tokens, por eso el corpus legal se trocea en fragmentos cortos.
# Alternativa de más calidad: IURIS_EMBEDDINGS_MODELO=google/embeddinggemma-300m (768 dim., 1,24 GB, 2048 tokens).
MODELO_LOCAL_DEFECTO = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
# Prefijos que exige cada modelo (descripción del modelo en fastembed): (consulta, documento).
_PREFIJOS: dict[str, tuple[str, str]] = {
    "google/embeddinggemma-300m": ("task: search result | query: ", "title: none | text: "),
    "intfloat/multilingual-e5-large": ("query: ", "passage: "),
}


class LocalEmbedder:
    """Embeddings en CPU con ONNX Runtime (fastembed). El modelo se descarga una vez a la caché de fastembed."""

    def __init__(self, model: str = MODELO_LOCAL_DEFECTO, *, cache_dir: str | None = None, motor: Any | None = None):
        if motor is None:
            try:
                from fastembed import TextEmbedding
            except ImportError as exc:  # extra opcional no instalado
                raise ModelUnavailable("fastembed no instalado (uv sync --extra embeddings)", provider="local") from exc
            soportados = {m["model"]: m for m in TextEmbedding.list_supported_models()}
            if model not in soportados:
                raise ModelUnavailable(f"modelo de embeddings no soportado por fastembed: {model}", provider="local")
            self.dim = int(soportados[model]["dim"])
            motor = TextEmbedding(model_name=model, cache_dir=cache_dir, lazy_load=True)
        else:
            self.dim = int(getattr(motor, "dim", 0)) or 384
        self.model = model
        self._motor = motor
        self._lock = asyncio.Lock()  # ONNX Runtime ya usa varios hilos: una llamada cada vez

    def _calcular(self, texts: list[str], task: TaskType) -> list[list[float]]:
        q, d = _PREFIJOS.get(self.model, ("", ""))
        prefijo = q if task == "RETRIEVAL_QUERY" else d
        return [[float(x) for x in v] for v in self._motor.embed([prefijo + t for t in texts])]

    async def embed(self, texts: Sequence[str], task: TaskType) -> list[list[float]]:
        if not texts:
            return []
        async with self._lock:
            return await asyncio.to_thread(self._calcular, list(texts), task)


def crear_embedder(
    gemini_key: str | None, *, gemini_model: str | None = None, gemini_dim: int = 768
) -> Embedder | None:
    """Gemini si hay clave; si no, el modelo local (si `fastembed` está instalado y no se ha desactivado con
    IURIS_EMBEDDINGS=no); si tampoco, None y la búsqueda queda en BM25."""
    if gemini_key and gemini_model:
        try:
            return GeminiEmbedder(gemini_key, model=gemini_model, dim=gemini_dim)
        except ModelUnavailable:
            pass
    if os.environ.get("IURIS_EMBEDDINGS", "").strip().lower() in ("no", "0", "false"):
        return None
    try:
        return LocalEmbedder(os.environ.get("IURIS_EMBEDDINGS_MODELO") or MODELO_LOCAL_DEFECTO)
    except ModelUnavailable as exc:
        log.info("Sin embeddings locales: %s", exc)
        return None
