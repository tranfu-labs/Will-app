"""Independent conversation storage for Liaison.

Liaison history is intentionally separate from the will event store and memory
economy: casual coordination should not become high-salience will observation
unless Liaison explicitly routes it through the channel inbox.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from yizhi.liaison.schemas import LiaisonMessage


def default_liaison_db_path(will_db_path: str | Path) -> Path:
    path = Path(will_db_path)
    return path.with_name("liaison.sqlite")


class LiaisonStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def init(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS liaison_messages (
                    id TEXT PRIMARY KEY,
                    ts TEXT NOT NULL,
                    conversation_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_liaison_messages_conversation_ts "
                "ON liaison_messages(conversation_id, ts)"
            )

    def append(self, message: LiaisonMessage) -> LiaisonMessage:
        self.init()
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO liaison_messages "
                "(id, ts, conversation_id, source, payload_json) VALUES (?, ?, ?, ?, ?)",
                (message.id, message.ts, message.conversation_id, message.source, message.model_dump_json()),
            )
        return message

    def list_messages(self, conversation_id: str = "default", limit: int = 150) -> list[LiaisonMessage]:
        if not self.path.exists():
            return []
        with sqlite3.connect(self.path) as conn:
            rows = conn.execute(
                "SELECT payload_json FROM liaison_messages WHERE conversation_id = ? "
                "ORDER BY ts DESC LIMIT ?",
                (conversation_id, limit),
            ).fetchall()
        messages = [LiaisonMessage.model_validate_json(row[0]) for row in rows]
        messages.reverse()
        return messages

    def get_pending(self, action_id: str) -> LiaisonPendingAction | None:
        from yizhi.liaison.schemas import LiaisonPendingAction

        if not self.path.exists():
            return None
        with sqlite3.connect(self.path) as conn:
            rows = conn.execute(
                "SELECT payload_json FROM liaison_messages WHERE payload_json LIKE ? ORDER BY ts DESC LIMIT 50",
                (f"%{action_id}%",),
            ).fetchall()
        for row in rows:
            message = LiaisonMessage.model_validate_json(row[0])
            if message.pending_action and message.pending_action.id == action_id:
                return LiaisonPendingAction.model_validate(message.pending_action.model_dump())
        return None
