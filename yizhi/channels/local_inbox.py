"""LocalInboxChannel: a file-backed channel, offline and deterministic.

`send` appends OutboundMessage JSON to outbox.jsonl; `poll` reads new lines from
inbox.jsonl (a human or another process writes them) tracked by a cursor file. Zero
external dependencies — the offline-safe default and the test substrate for R2.
"""

from __future__ import annotations

from pathlib import Path

from yizhi.channels.base import InboundCommand, OutboundMessage, parse_inbound


class LocalInboxChannel:
    name = "local_inbox"

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.outbox = self.root / "outbox.jsonl"
        self.inbox = self.root / "inbox.jsonl"
        self.cursor = self.root / ".inbox_cursor"

    def send(self, message: OutboundMessage) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with self.outbox.open("a", encoding="utf-8") as handle:
            handle.write(message.model_dump_json() + "\n")

    def poll(self) -> list[InboundCommand]:
        if not self.inbox.exists():
            return []
        consumed = int(self.cursor.read_text()) if self.cursor.exists() else 0
        lines = self.inbox.read_text(encoding="utf-8").splitlines()
        commands: list[InboundCommand] = []
        for line in lines[consumed:]:
            command = parse_inbound(line)
            if command is not None:
                commands.append(command)
        self.root.mkdir(parents=True, exist_ok=True)
        self.cursor.write_text(str(len(lines)))
        return commands
