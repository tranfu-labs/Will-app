"""Tool surface for Liaison.

All read tools are projections over the existing web/event-store layer. The only
write tool appends a governed command to the channel inbox, preserving the
existing will-side consumption path.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from yizhi.channels.base import InboundCommand, InboundVerb
from yizhi.core.schemas import EventType
from yizhi.web.data import append_inbox, fetch_events, latest_state, load_packet, read_inbox_lines
from yizhi.web.projections import project_approvals, project_now, project_task_history

ReadToolName = Literal["get_state", "get_tasks", "get_events", "get_findings", "get_packet", "get_delegations"]


class LiaisonTools:
    def __init__(
        self,
        *,
        db_path: str | Path,
        channel_root: str | Path,
        packet_path: str | Path = Path("data/funding/promotion_packet.json"),
    ) -> None:
        self.db_path = Path(db_path)
        self.channel_root = Path(channel_root)
        self.packet_path = Path(packet_path)

    def get_state(self) -> dict[str, Any]:
        events = fetch_events(
            self.db_path, event_type=EventType.INTENTION_ACTIVATED.value, newest_first=True, limit=1
        )
        return project_now(latest_state(self.db_path), list(reversed(events))).model_dump()

    def get_tasks(self) -> list[dict[str, Any]]:
        return [t.model_dump() for t in project_task_history(fetch_events(self.db_path), latest_state(self.db_path))]

    def get_events(self, limit: int = 20, event_type: str | None = None) -> list[dict[str, Any]]:
        events = fetch_events(self.db_path, event_type=event_type, newest_first=True, limit=max(1, min(limit, 100)))
        return [
            {
                "ts": event.get("ts", ""),
                "type": event.get("type", ""),
                "aggregate_id": event.get("aggregate_id", ""),
                "correlation_id": event.get("correlation_id") or "",
                "payload": event.get("payload") or {},
            }
            for event in events
        ]

    def get_findings(self, limit: int = 20) -> list[dict[str, Any]]:
        events = fetch_events(
            self.db_path, event_type=EventType.JUDGMENT_RENDERED.value, newest_first=True, limit=max(1, min(limit, 100))
        )
        return [
            {
                "ts": event.get("ts", ""),
                "verdict": (event.get("payload") or {}).get("verdict", ""),
                "subject": (event.get("payload") or {}).get("subject", ""),
                "reason": (event.get("payload") or {}).get("reason", ""),
                "payload": event.get("payload") or {},
            }
            for event in events
        ]

    def get_packet(self) -> dict[str, Any] | None:
        return load_packet(self.packet_path)

    def get_delegations(self, limit: int = 30) -> list[dict[str, Any]]:
        delegation_types = {
            EventType.DELEGATION_REQUESTED.value,
            EventType.DELEGATION_COMPLETED.value,
            EventType.DELEGATION_FAILED.value,
        }
        events = [e for e in fetch_events(self.db_path, newest_first=True, limit=200) if e.get("type") in delegation_types]
        return [
            {
                "ts": event.get("ts", ""),
                "type": event.get("type", ""),
                "correlation_id": event.get("correlation_id") or "",
                "payload": event.get("payload") or {},
            }
            for event in events[: max(1, min(limit, 100))]
        ]

    def pending_approvals(self) -> list[dict[str, Any]]:
        return [a.model_dump() for a in project_approvals(fetch_events(self.db_path), read_inbox_lines(self.channel_root))]

    def read_tool(self, name: str, args: dict[str, Any] | None = None) -> Any:
        args = args or {}
        if name == "get_state":
            return self.get_state()
        if name == "get_tasks":
            return self.get_tasks()
        if name == "get_events":
            return self.get_events(limit=int(args.get("limit", 20)), event_type=args.get("event_type"))
        if name == "get_findings":
            return self.get_findings(limit=int(args.get("limit", 20)))
        if name == "get_packet":
            return self.get_packet()
        if name == "get_delegations":
            return self.get_delegations(limit=int(args.get("limit", 30)))
        raise ValueError(f"unknown liaison read tool: {name}")

    def send_to_will(
        self,
        verb: str,
        text: str,
        *,
        confirmed: bool = False,
        correlation_id: str | None = None,
    ) -> InboundCommand:
        """Append one command to the will inbox.

        `note` and `ask` may be sent directly. `vision`, `kill`, and `approve`
        are confirmation-gated. Approvals must reference a real approval
        projection so a vague "yes" cannot approve the wrong action.
        """
        normalized = verb.strip().lower()
        if normalized in {"note", "ask"}:
            return append_inbox(self.channel_root, InboundVerb(normalized), text.strip())
        if normalized == "vision":
            if not confirmed:
                raise PermissionError("vision changes require confirmation")
            return append_inbox(self.channel_root, InboundVerb.VISION, text.strip())
        if normalized == "kill":
            if not confirmed:
                raise PermissionError("kill commands require confirmation")
            if text.strip().lower() not in {"goal", "current goal", "当前目标", "目标"}:
                raise ValueError("liaison kill only supports the current goal")
            return append_inbox(self.channel_root, InboundVerb.KILL, "goal")
        if normalized == "approve":
            if not confirmed:
                raise PermissionError("approval commands require confirmation")
            cid = correlation_id or text.strip()
            known = {a["correlation_id"] for a in self.pending_approvals()}
            if cid not in known:
                raise ValueError("approval correlation_id is not pending")
            return append_inbox(self.channel_root, InboundVerb.APPROVE, cid)
        raise ValueError(f"unsupported will command verb: {verb}")
