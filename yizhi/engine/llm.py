"""Provider-agnostic LLM cognition client (the engine inside the harness).

The will loop stays deterministic by default; an LLM is opt-in (see
`yizhi/config.py`). The boundary is strict: the LLM only *proposes* structured
cognition — it never sets salience, the existence budget, policy decisions, or
the `verified` flag, and any action it proposes still passes the deterministic
policy gate. Callers must treat an `LLMError` as a signal to fall back to the
deterministic path, so a network blip or bad key never crashes the loop.

OpenAI/GPT is the direct first provider (the user supplies the key); ANY other
provider (anthropic/gemini/ollama/…) is served by `LiteLLMClient` behind the same
`LLMClient` Protocol, so yizhi is multi-LLM without touching the governed core.
The `openai`/`litellm` packages are imported lazily so the deterministic runtime
and its offline tests never require them.
"""

from __future__ import annotations

import json
from typing import Protocol, runtime_checkable

from yizhi.config import LLMConfig, load_llm_config


class LLMError(RuntimeError):
    """Any failure of an LLM call. Callers fall back to the deterministic path."""


def normalize_base_url(base_url: str) -> str:
    """OpenAI-compatible endpoints serve the API under `/v1`. A bare host with no
    path (e.g. `https://proxy.example.com/`) would otherwise hit the site root and
    return HTML, which silently disables the engine. Append `/v1` only when no
    path is given; respect any explicit path."""
    if not base_url:
        return ""
    from urllib.parse import urlsplit

    if urlsplit(base_url).path.strip("/") == "":
        return base_url.rstrip("/") + "/v1"
    return base_url


@runtime_checkable
class LLMClient(Protocol):
    def complete_json(self, system: str, user: str) -> dict: ...


class OpenAILLM:
    """OpenAI/GPT-backed client. Returns a parsed JSON object or raises LLMError."""

    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self.total_tokens = 0  # accumulated across calls, for the cost metric
        self.call_count = 0

    def _client(self):
        try:
            from openai import OpenAI  # lazy: optional dep, see pyproject [llm]
        except ImportError as exc:  # pragma: no cover - only without the extra
            raise LLMError("openai not installed; `pip install yizhi[llm]`") from exc
        kwargs: dict = {"api_key": self.config.api_key, "timeout": self.config.request_timeout, "max_retries": 2}
        if self.config.base_url:
            kwargs["base_url"] = normalize_base_url(self.config.base_url)
        return OpenAI(**kwargs)

    def complete_json(self, system: str, user: str) -> dict:
        """One JSON-constrained completion. The word 'JSON' in the system prompt
        is required by the response_format; model-specific params may need tuning
        for some GPT models — any failure raises LLMError for graceful fallback."""
        try:
            response = self._client().chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format={"type": "json_object"},
                max_tokens=self.config.max_output_tokens,
            )
            content = response.choices[0].message.content or ""
            parsed = json.loads(content)
            self.call_count += 1
            usage = getattr(response, "usage", None)
            if usage is not None and getattr(usage, "total_tokens", None):
                self.total_tokens += int(usage.total_tokens)
        except Exception as exc:  # network, auth, bad-request, parse — all degrade
            raise LLMError(str(exc)) from exc
        if not isinstance(parsed, dict):
            raise LLMError(f"expected a JSON object, got {type(parsed).__name__}")
        return parsed


class LiteLLMClient:
    """Any-provider client behind the SAME LLMClient Protocol, via LiteLLM's one
    OpenAI-format call over 100+ providers (anthropic/gemini/ollama/groq/…). yizhi
    becomes multi-LLM with no change to the governed core: the LLM still only
    *proposes* a JSON object; the two walls + budget + memory are downstream and
    untouched. `litellm` is imported lazily so the deterministic offline runtime
    and its tests never require it. Any failure raises LLMError → deterministic
    fallback, exactly like OpenAILLM."""

    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self.total_tokens = 0
        self.call_count = 0

    def _model_id(self) -> str:
        # LiteLLM addresses a model as "<provider>/<model>" (e.g. "anthropic/claude-...").
        # Respect a fully-qualified id if the user already wrote one.
        model = self.config.model
        return model if "/" in model else f"{self.config.provider}/{model}"

    def complete_json(self, system: str, user: str) -> dict:
        try:
            from litellm import completion  # lazy: optional dep, see pyproject [litellm]
        except ImportError as exc:  # pragma: no cover - only without the extra
            raise LLMError("litellm not installed; `pip install yizhi[litellm]`") from exc
        kwargs: dict = {
            "model": self._model_id(),
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": self.config.max_output_tokens,
            "timeout": self.config.request_timeout,
        }
        if self.config.api_key:
            kwargs["api_key"] = self.config.api_key
        if self.config.base_url:
            kwargs["base_url"] = normalize_base_url(self.config.base_url)
        try:
            response = completion(**kwargs)  # LiteLLM normalizes to the OpenAI response shape
            content = response.choices[0].message.content or ""
            parsed = json.loads(content)
            self.call_count += 1
            usage = getattr(response, "usage", None)
            if usage is not None and getattr(usage, "total_tokens", None):
                self.total_tokens += int(usage.total_tokens)
        except Exception as exc:  # network, auth, unsupported-format, parse — all degrade
            raise LLMError(str(exc)) from exc
        if not isinstance(parsed, dict):
            raise LLMError(f"expected a JSON object, got {type(parsed).__name__}")
        return parsed


def load_llm(config: LLMConfig | None = None) -> LLMClient | None:
    """Return a ready LLM client, or None when the engine is off (the default).
    None means the loop uses the deterministic path — no network, no key.

    `provider == "openai"` uses the direct OpenAI client; ANY OTHER provider
    (anthropic/gemini/ollama/…) is served by LiteLLMClient, so yizhi is multi-LLM
    without changing the LLMClient Protocol or the governed core."""
    config = config or load_llm_config()
    if not config.active:
        return None
    if config.provider == "openai":
        return OpenAILLM(config)
    return LiteLLMClient(config)
