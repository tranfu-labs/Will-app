"""Configuration loading for the optional LLM cognition layer.

The deterministic loop needs no config and makes no network calls — that is the
default. An LLM is opt-in: a git-ignored `will.config.toml` (copied from
`will.config.example.toml`) supplies the provider, key, and model, and a few
env vars can override it. The legacy `yizhi.config.toml` path is still accepted
as a fallback. Read with stdlib `tomllib` so loading needs no third-party
dependency. See docs and the plan; the secret never enters git.
"""

from __future__ import annotations

import os
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG_PATH = Path("will.config.toml")
LEGACY_CONFIG_PATH = Path("yizhi.config.toml")

_warned_legacy_config = False


def _resolve_config_path(path: str | Path) -> Path:
    """Prefer Will's config name, but keep the old yizhi file working (with a
    one-time deprecation nudge — two config files is a real usage trap)."""
    global _warned_legacy_config
    config_path = Path(path)
    if config_path == DEFAULT_CONFIG_PATH and not config_path.exists() and LEGACY_CONFIG_PATH.exists():
        if not _warned_legacy_config:
            _warned_legacy_config = True
            print(
                "note: reading legacy yizhi.config.toml — rename it to will.config.toml "
                "(the legacy name keeps working for now)",
                file=sys.stderr,
            )
        return LEGACY_CONFIG_PATH
    return config_path


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
    config_path = _resolve_config_path(path)
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
    if provider == "anthropic":
        # Provider-native key wins for the anthropic provider so both keys can
        # coexist in one environment.
        api_key = os.environ.get("ANTHROPIC_API_KEY", api_key)
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
    config_path = _resolve_config_path(path)
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


@dataclass(frozen=True)
class DelegationConfig:
    """External coding-harness delegation (R0; docs/resident-operator-plan.md).

    Off by default and never used by the deterministic offline suite — tests inject a
    fake client. When enabled, `command` is the harness CLI (e.g. `claude` / `codex`)
    that Will drives as a bounded, read-only worker inside `root`."""

    enabled: bool = False
    harness: str = "claude"                                       # claude | codex | ...
    command: str = ""                                             # CLI entrypoint; empty => inactive
    default_allowed_tools: tuple[str, ...] = ("Read", "Grep", "Glob")
    request_timeout: float = 600.0                                # research-grade runs need minutes
    root: str = ""                                                # restricted root the harness may run in

    @property
    def active(self) -> bool:
        return self.enabled and bool(self.command)


def load_delegation_config(path: str | Path = DEFAULT_CONFIG_PATH) -> DelegationConfig:
    """Load `[delegation]` from the config file (if present), then overlay env vars
    (YIZHI_DELEGATION_ENABLED, YIZHI_DELEGATION_HARNESS, YIZHI_DELEGATION_COMMAND,
    YIZHI_DELEGATION_ROOT). Missing → disabled."""
    data: dict = {}
    config_path = _resolve_config_path(path)
    if config_path.exists():
        with config_path.open("rb") as handle:
            data = (tomllib.load(handle) or {}).get("delegation", {})

    defaults = DelegationConfig()
    enabled = bool(data.get("enabled", defaults.enabled))
    harness = str(data.get("harness", defaults.harness))
    command = str(data.get("command", defaults.command))
    tools = data.get("default_allowed_tools", list(defaults.default_allowed_tools))
    request_timeout = float(data.get("request_timeout", defaults.request_timeout))
    root = str(data.get("root", defaults.root))

    if "YIZHI_DELEGATION_ENABLED" in os.environ:
        enabled = _as_bool(os.environ["YIZHI_DELEGATION_ENABLED"])
    harness = os.environ.get("YIZHI_DELEGATION_HARNESS", harness)
    command = os.environ.get("YIZHI_DELEGATION_COMMAND", command)
    root = os.environ.get("YIZHI_DELEGATION_ROOT", root)

    return DelegationConfig(
        enabled=enabled,
        harness=harness,
        command=command,
        default_allowed_tools=tuple(tools),
        request_timeout=request_timeout,
        root=root,
    )


@dataclass(frozen=True)
class ChannelConfig:
    """Single-channel interaction layer (R2; docs/resident-operator-plan.md).

    `local_inbox` is the offline default (file-backed JSONL, always usable). `telegram`
    is a real adapter, manual-gated: inactive unless a bot token and chat id are set."""

    enabled: bool = False
    kind: str = "local_inbox"                 # local_inbox | telegram
    root: str = ".yizhi/channel"              # legacy local_inbox file directory
    telegram_token: str = ""
    telegram_chat_id: str = ""
    request_timeout: float = 30.0

    @property
    def active(self) -> bool:
        if self.kind == "telegram":
            return self.enabled and bool(self.telegram_token) and bool(self.telegram_chat_id)
        return True  # local_inbox is the safe offline substrate


def load_channel_config(path: str | Path = DEFAULT_CONFIG_PATH) -> ChannelConfig:
    """Load `[channel]` from the config file (if present), then overlay env vars
    (YIZHI_CHANNEL_ENABLED, YIZHI_CHANNEL_KIND, YIZHI_CHANNEL_ROOT, YIZHI_TELEGRAM_TOKEN,
    YIZHI_TELEGRAM_CHAT_ID). Missing → offline local_inbox."""
    data: dict = {}
    config_path = _resolve_config_path(path)
    if config_path.exists():
        with config_path.open("rb") as handle:
            data = (tomllib.load(handle) or {}).get("channel", {})

    defaults = ChannelConfig()
    enabled = bool(data.get("enabled", defaults.enabled))
    kind = str(data.get("kind", defaults.kind))
    root = str(data.get("root", defaults.root))
    telegram_token = str(data.get("telegram_token", defaults.telegram_token))
    telegram_chat_id = str(data.get("telegram_chat_id", defaults.telegram_chat_id))
    request_timeout = float(data.get("request_timeout", defaults.request_timeout))

    if "YIZHI_CHANNEL_ENABLED" in os.environ:
        enabled = _as_bool(os.environ["YIZHI_CHANNEL_ENABLED"])
    kind = os.environ.get("YIZHI_CHANNEL_KIND", kind)
    root = os.environ.get("YIZHI_CHANNEL_ROOT", root)
    telegram_token = os.environ.get("YIZHI_TELEGRAM_TOKEN", telegram_token)
    telegram_chat_id = os.environ.get("YIZHI_TELEGRAM_CHAT_ID", telegram_chat_id)

    return ChannelConfig(
        enabled=enabled,
        kind=kind,
        root=root,
        telegram_token=telegram_token,
        telegram_chat_id=telegram_chat_id,
        request_timeout=request_timeout,
    )
