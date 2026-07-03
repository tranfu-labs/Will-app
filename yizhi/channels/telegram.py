"""TelegramChannel: a real adapter, manual-gated.

Uses only stdlib urllib so it adds no dependency. The offline suite never reaches the
network: send/poll are no-ops unless ChannelConfig is active (bot token + chat id). A
channel failure is swallowed — a flaky network must never crash the agent.
See docs/resident-operator-plan.md (pillar B, R2).
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request

from yizhi.channels.base import InboundCommand, OutboundMessage, parse_inbound
from yizhi.config import ChannelConfig

_API = "https://api.telegram.org/bot{token}/{method}"


class TelegramChannel:
    name = "telegram"

    def __init__(self, config: ChannelConfig) -> None:
        self.config = config
        self._offset = 0

    def _call(self, method: str, params: dict) -> dict:
        url = _API.format(token=self.config.telegram_token, method=method)
        data = urllib.parse.urlencode(params).encode()
        with urllib.request.urlopen(url, data=data, timeout=self.config.request_timeout) as resp:
            return json.loads(resp.read().decode())

    def send(self, message: OutboundMessage) -> None:
        if not self.config.active:
            return
        text = f"[{message.kind}] {message.title}\n{message.body}".strip()
        try:
            self._call("sendMessage", {"chat_id": self.config.telegram_chat_id, "text": text})
        except Exception:  # noqa: BLE001 - a channel failure must not crash the agent
            pass

    def poll(self) -> list[InboundCommand]:
        if not self.config.active:
            return []
        try:
            resp = self._call("getUpdates", {"offset": self._offset, "timeout": 0})
        except Exception:  # noqa: BLE001
            return []
        commands: list[InboundCommand] = []
        for update in resp.get("result", []):
            self._offset = max(self._offset, int(update.get("update_id", 0)) + 1)
            text = (update.get("message") or {}).get("text", "")
            command = parse_inbound(text)
            if command is not None:
                commands.append(command)
        return commands
