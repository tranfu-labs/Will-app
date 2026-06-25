"""Local semantic embedder for will-governed recall.

yizhi keeps the governed memory economy (salience, decay, supersession, the
two-channel recall); this only upgrades the *relevance* term of ranking from
keyword overlap to embedding cosine similarity, so "the thing I should recall"
is found by meaning, not shared words. The model is local (fastembed / ONNX —
no key, no network at call time), loaded lazily and once. Off by default; when
no embedder is configured, ranking falls back to deterministic keyword overlap,
so the offline test suite and the deterministic runtime are unchanged.
"""

from __future__ import annotations

import math
from typing import Protocol, runtime_checkable

from yizhi.config import EmbeddingConfig, load_embedding_config


@runtime_checkable
class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


class FastEmbedder:
    """fastembed-backed local embedder. The model is loaded once, lazily."""

    def __init__(self, model: str) -> None:
        self.model_name = model
        self._model = None

    def _ensure(self):
        if self._model is None:
            from fastembed import TextEmbedding  # lazy: optional dep, first run downloads the model

            self._model = TextEmbedding(model_name=self.model_name)
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return [list(map(float, v)) for v in self._ensure().embed(texts)]


_EMBEDDER_CACHE: dict[str, Embedder] = {}


def load_embedder(config: EmbeddingConfig | None = None) -> Embedder | None:
    """Return a ready embedder, or None when semantic recall is off (the default).
    None means ranking uses deterministic keyword overlap — no model, no network.
    The embedder is cached per model so the (slow) model loads once per process."""
    config = config or load_embedding_config()
    if not config.active:
        return None
    if config.model not in _EMBEDDER_CACHE:
        try:
            _EMBEDDER_CACHE[config.model] = FastEmbedder(config.model)
        except Exception:  # never let an embedder problem break recall — fall back to keywords
            return None
    return _EMBEDDER_CACHE[config.model]
