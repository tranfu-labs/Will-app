from __future__ import annotations

import json

import pytest

from yizhi.config import LLMConfig
from yizhi.engine.llm import AnthropicClient, LLMError, load_llm


def _config(**overrides) -> LLMConfig:
    defaults = dict(enabled=True, provider="anthropic", api_key="k", model="claude-sonnet-5")
    defaults.update(overrides)
    return LLMConfig(**defaults)


def _response(text: str, input_tokens: int = 10, output_tokens: int = 5) -> dict:
    return {
        "content": [{"type": "text", "text": text}],
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
    }


def test_anthropic_client_parses_json_and_counts_tokens():
    captured: dict = {}

    def transport(url, body, headers):
        captured["url"] = url
        captured["payload"] = json.loads(body)
        captured["headers"] = headers
        return _response('{"answer": "42"}')

    client = AnthropicClient(_config(), transport=transport)

    result = client.complete_json("system prompt", "user prompt")

    assert result == {"answer": "42"}
    assert captured["url"] == "https://api.anthropic.com/v1/messages"
    assert captured["payload"]["system"] == "system prompt"
    assert captured["payload"]["messages"] == [{"role": "user", "content": "user prompt"}]
    assert captured["headers"]["x-api-key"] == "k"
    assert client.call_count == 1 and client.total_tokens == 15


def test_anthropic_client_strips_code_fence():
    client = AnthropicClient(
        _config(), transport=lambda *a: _response('```json\n{"ok": true}\n```')
    )
    assert client.complete_json("s", "u") == {"ok": True}


def test_anthropic_client_raises_llm_error_on_bad_output():
    client = AnthropicClient(_config(), transport=lambda *a: _response("not json at all"))
    with pytest.raises(LLMError):
        client.complete_json("s", "u")

    client = AnthropicClient(_config(), transport=lambda *a: _response('["a", "list"]'))
    with pytest.raises(LLMError):
        client.complete_json("s", "u")


def test_anthropic_client_respects_base_url_override():
    seen: list[str] = []

    def transport(url, body, headers):
        seen.append(url)
        return _response('{"x": 1}')

    AnthropicClient(_config(base_url="https://proxy.internal"), transport=transport).complete_json("s", "u")
    assert seen == ["https://proxy.internal/v1/messages"]


def test_load_llm_routes_anthropic_natively():
    client = load_llm(_config())
    assert isinstance(client, AnthropicClient)
    assert load_llm(_config(enabled=False)) is None
