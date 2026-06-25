"""Compensation-event rollback helpers."""

from __future__ import annotations

from pathlib import Path

from yizhi.core.schemas import EventType
from yizhi.state.store import append_event


def revoke_memory(memory_id: str, reason: str, path: str | Path) -> str:
    return append_event(
        EventType.MEMORY_REVOKED,
        aggregate_type="memory",
        aggregate_id=memory_id,
        payload={"memory_id": memory_id, "reason": reason},
        path=path,
    )


def retire_intention(intention_id: str, reason: str, path: str | Path) -> str:
    return append_event(
        EventType.INTENTION_RETIRED,
        aggregate_type="intention",
        aggregate_id=intention_id,
        payload={"intention_id": intention_id, "reason": reason},
        path=path,
    )


def request_action_rollback(action_record_id: str, reason: str, path: str | Path) -> str:
    return append_event(
        EventType.ACTION_ROLLBACK_REQUESTED,
        aggregate_type="action",
        aggregate_id=action_record_id,
        payload={
            "action_record_id": action_record_id,
            "reason": reason,
            "mode": "proposal_only",
            "note": "v0 does not auto-revert files or git state",
        },
        path=path,
    )
