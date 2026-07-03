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


class AnthropicClient:
    """Claude-backed client speaking the Anthropic Messages API directly over
    stdlib urllib — zero new dependency (the TelegramChannel precedent). The
    same strict boundary as every LLMClient: it only *proposes* a JSON object;
    walls, budget, and memory are downstream. Anthropic has no response_format
    parameter, so JSON is enforced by the callers' system prompts and a
    tolerant parse (strip a whole-body code fence); anything else raises
    LLMError → deterministic fallback."""

    DEFAULT_BASE_URL = "https://api.anthropic.com"
    API_VERSION = "2023-06-01"

    def __init__(self, config: LLMConfig, transport=None) -> None:
        self.config = config
        self.transport = transport or self._http_post  # injectable for offline tests
        self.total_tokens = 0
        self.call_count = 0

    def _http_post(self, url: str, body: bytes, headers: dict) -> dict:
        import urllib.request

        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(request, timeout=self.config.request_timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    @staticmethod
    def _strip_fence(text: str) -> str:
        stripped = text.strip()
        if stripped.startswith("```") and stripped.endswith("```"):
            lines = stripped.splitlines()
            if len(lines) >= 2:
                return "\n".join(lines[1:-1]).strip()
        return stripped

    def complete_json(self, system: str, user: str) -> dict:
        base = (self.config.base_url or self.DEFAULT_BASE_URL).rstrip("/")
        payload = {
            "model": self.config.model,
            "max_tokens": self.config.max_output_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        headers = {
            "content-type": "application/json",
            "x-api-key": self.config.api_key,
            "anthropic-version": self.API_VERSION,
        }
        try:
            data = self.transport(
                f"{base}/v1/messages",
                json.dumps(payload).encode("utf-8"),
                headers,
            )
            blocks = data.get("content") or []
            text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
            parsed = json.loads(self._strip_fence(text))
            self.call_count += 1
            usage = data.get("usage") or {}
            self.total_tokens += int(usage.get("input_tokens", 0)) + int(usage.get("output_tokens", 0))
        except Exception as exc:  # network, auth, parse — all degrade
            raise LLMError(str(exc)) from exc
        if not isinstance(parsed, dict):
            raise LLMError(f"expected a JSON object, got {type(parsed).__name__}")
        return parsed


def load_llm(config: LLMConfig | None = None) -> LLMClient | None:
    """Return a ready LLM client, or None when the engine is off (the default).
    None means the loop uses the deterministic path — no network, no key.

    `provider == "openai"` uses the direct OpenAI client; `provider ==
    "anthropic"` uses the native stdlib AnthropicClient (no extra install);
    any other provider (gemini/ollama/…) is served by LiteLLMClient, so yizhi
    is multi-LLM without changing the LLMClient Protocol or the governed core."""
    config = config or load_llm_config()
    if not config.active:
        return None
    if config.provider == "openai":
        return OpenAILLM(config)
    if config.provider == "anthropic":
        return AnthropicClient(config)
    return LiteLLMClient(config)
