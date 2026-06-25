"""Configuration loading for the optional LLM cognition layer.

The deterministic loop needs no config and makes no network calls — that is the
default. An LLM is opt-in: a git-ignored `yizhi.config.toml` (copied from
`yizhi.config.example.toml`) supplies the provider, key, and model, and a few
env vars can override it. Read with stdlib `tomllib` so loading needs no
third-party dependency. See docs and the plan; the secret never enters git.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG_PATH = Path("yizhi.config.toml")


@dataclass(frozen=True)
class LLMConfig:
    enabled: bool = False
    provider: str = "openai"
    api_key: str = ""
    model: str = "gpt-5"
    base_url: str = ""
    max_output_tokens: int = 1024
    request_timeout: float = 60.0          # per-call wall-clock cap; a hung proxy must not block the loop forever

    @property
    def active(self) -> bool:
        """True only when the engine is fully configured to make calls."""
        return self.enabled and bool(self.api_key) and bool(self.model)


@dataclass(frozen=True)
class EmbeddingConfig:
    """Local semantic-recall embedder. Off by default; a local model means no key
    and no network at call time, but the model loads (and first-run downloads), so
    tests keep it off (see tests/conftest.py)."""

    enabled: bool = False
    model: str = "BAAI/bge-small-en-v1.5"

    @property
    def active(self) -> bool:
        return self.enabled and bool(self.model)


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_llm_config(path: str | Path = DEFAULT_CONFIG_PATH) -> LLMConfig:
    """Load `[llm]` from the config file (if present), then overlay env vars.

    Missing file or missing `[llm]` table → all defaults (LLM disabled). Env
    vars (YIZHI_LLM_ENABLED, OPENAI_API_KEY, YIZHI_LLM_MODEL, YIZHI_LLM_PROVIDER,
    YIZHI_LLM_BASE_URL) win over the file so a key can stay out of the repo dir."""
    data: dict = {}
    config_path = Path(path)
    if config_path.exists():
        with config_path.open("rb") as handle:
            data = (tomllib.load(handle) or {}).get("llm", {})

    defaults = LLMConfig()
    enabled = bool(data.get("enabled", defaults.enabled))
    provider = str(data.get("provider", defaults.provider))
    api_key = str(data.get("api_key", defaults.api_key))
    model = str(data.get("model", defaults.model))
    base_url = str(data.get("base_url", defaults.base_url))
    max_output_tokens = int(data.get("max_output_tokens", defaults.max_output_tokens))
    request_timeout = float(data.get("request_timeout", defaults.request_timeout))

    if "YIZHI_LLM_ENABLED" in os.environ:
        enabled = _as_bool(os.environ["YIZHI_LLM_ENABLED"])
    provider = os.environ.get("YIZHI_LLM_PROVIDER", provider)
    api_key = os.environ.get("OPENAI_API_KEY", api_key)
    model = os.environ.get("YIZHI_LLM_MODEL", model)
    base_url = os.environ.get("YIZHI_LLM_BASE_URL", base_url)

    return LLMConfig(
        enabled=enabled,
        provider=provider,
        api_key=api_key,
        model=model,
        base_url=base_url,
        max_output_tokens=max_output_tokens,
        request_timeout=request_timeout,
    )


def load_embedding_config(path: str | Path = DEFAULT_CONFIG_PATH) -> EmbeddingConfig:
    """Load `[embedding]` from the config file (if present), then overlay env vars
    (YIZHI_EMBEDDING_ENABLED, YIZHI_EMBEDDING_MODEL). Missing → disabled."""
    data: dict = {}
    config_path = Path(path)
    if config_path.exists():
        with config_path.open("rb") as handle:
            data = (tomllib.load(handle) or {}).get("embedding", {})

    defaults = EmbeddingConfig()
    enabled = bool(data.get("enabled", defaults.enabled))
    model = str(data.get("model", defaults.model))
    if "YIZHI_EMBEDDING_ENABLED" in os.environ:
        enabled = _as_bool(os.environ["YIZHI_EMBEDDING_ENABLED"])
    model = os.environ.get("YIZHI_EMBEDDING_MODEL", model)
    return EmbeddingConfig(enabled=enabled, model=model)
