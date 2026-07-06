"""Configuration for optional providers and worker adapters."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG_PATH = Path("will.config.toml")


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _table(path: str | Path, name: str) -> dict:
    config_path = Path(path)
    if not config_path.exists():
        return {}
    with config_path.open("rb") as handle:
        return (tomllib.load(handle) or {}).get(name, {})


@dataclass(frozen=True)
class LLMConfig:
    """Optional provider config for worker or lens adapters.

    The autonomous campaign controller does not require an LLM provider.
    """

    enabled: bool = False
    provider: str = "openai"
    api_key: str = ""
    model: str = "gpt-5"
    base_url: str = ""
    max_output_tokens: int = 1024
    request_timeout: float = 60.0

    @property
    def active(self) -> bool:
        return self.enabled and bool(self.api_key) and bool(self.model)


def load_llm_config(path: str | Path = DEFAULT_CONFIG_PATH) -> LLMConfig:
    data = _table(path, "llm")
    defaults = LLMConfig()
    enabled = bool(data.get("enabled", defaults.enabled))
    provider = str(data.get("provider", defaults.provider))
    api_key = str(data.get("api_key", defaults.api_key))
    model = str(data.get("model", defaults.model))
    base_url = str(data.get("base_url", defaults.base_url))
    max_output_tokens = int(data.get("max_output_tokens", defaults.max_output_tokens))
    request_timeout = float(data.get("request_timeout", defaults.request_timeout))

    if "WILL_LLM_ENABLED" in os.environ:
        enabled = _as_bool(os.environ["WILL_LLM_ENABLED"])
    provider = os.environ.get("WILL_LLM_PROVIDER", provider)
    api_key = os.environ.get("OPENAI_API_KEY", api_key)
    if provider == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY", api_key)
    model = os.environ.get("WILL_LLM_MODEL", model)
    base_url = os.environ.get("WILL_LLM_BASE_URL", base_url)

    return LLMConfig(
        enabled=enabled,
        provider=provider,
        api_key=api_key,
        model=model,
        base_url=base_url,
        max_output_tokens=max_output_tokens,
        request_timeout=request_timeout,
    )


@dataclass(frozen=True)
class DelegationConfig:
    """External worker adapter config.

    Off by default. When enabled, `command` is a coding/research harness CLI
    such as Codex, Claude Code, pi, or an OpenClaw worker plugin.
    """

    enabled: bool = False
    harness: str = "codex"
    command: str = ""
    default_allowed_tools: tuple[str, ...] = ("Read", "Grep", "Glob")
    request_timeout: float = 600.0
    root: str = ""

    @property
    def active(self) -> bool:
        return self.enabled and bool(self.command)


def load_delegation_config(path: str | Path = DEFAULT_CONFIG_PATH) -> DelegationConfig:
    data = _table(path, "delegation")
    defaults = DelegationConfig()
    enabled = bool(data.get("enabled", defaults.enabled))
    harness = str(data.get("harness", defaults.harness))
    command = str(data.get("command", defaults.command))
    tools = data.get("default_allowed_tools", list(defaults.default_allowed_tools))
    request_timeout = float(data.get("request_timeout", defaults.request_timeout))
    root = str(data.get("root", defaults.root))

    if "WILL_DELEGATION_ENABLED" in os.environ:
        enabled = _as_bool(os.environ["WILL_DELEGATION_ENABLED"])
    harness = os.environ.get("WILL_DELEGATION_HARNESS", harness)
    command = os.environ.get("WILL_DELEGATION_COMMAND", command)
    root = os.environ.get("WILL_DELEGATION_ROOT", root)

    return DelegationConfig(
        enabled=enabled,
        harness=harness,
        command=command,
        default_allowed_tools=tuple(tools),
        request_timeout=request_timeout,
        root=root,
    )
