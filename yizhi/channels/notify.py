"""Event → message mapping and channel factory (R2).

`event_to_message` decides which semantic events are worth telling a human about, and at
what severity. It reads a plain event dict (as `list_events` returns) so the daemon can
feed it straight from the store. `make_channel` builds the configured channel; the
file-backed local_inbox is the offline default.
"""

from __future__ import annotations

import json

from yizhi.channels.base import Channel, MessageKind, OutboundMessage
from yizhi.channels.local_inbox import LocalInboxChannel
from yizhi.channels.telegram import TelegramChannel
from yizhi.config import ChannelConfig, load_channel_config
from yizhi.core.schemas import EventType

# Events worth surfacing, with severity. Routine machinery (observations, drives, memory
# bookkeeping) is intentionally absent — a report stream is signal, not a log tail.
_REPORTABLE: dict[str, MessageKind] = {
    EventType.JUDGMENT_RENDERED.value: MessageKind.REPORT,
    EventType.DELEGATION_COMPLETED.value: MessageKind.REPORT,
    EventType.GOAL_SET.value: MessageKind.REPORT,
    EventType.DELIVERABLE_ACCEPTED.value: MessageKind.REPORT,
    EventType.CAMPAIGN_COMPLETED.value: MessageKind.REPORT,
    EventType.BUDGET_HALTED.value: MessageKind.ALERT,
    EventType.DELEGATION_FAILED.value: MessageKind.ALERT,
    EventType.DELIVERABLE_REJECTED.value: MessageKind.ALERT,
    EventType.ACTION_FAILED.value: MessageKind.ALERT,
}

_BODY_KEYS = ("verdict", "subject", "reason", "summary", "title", "balance", "decision")


def _body(payload: object) -> str:
    if not isinstance(payload, dict):
        return str(payload)[:300]
    # Campaign-shaped payloads: surface the human-relevant facts, not a state dump.
    if "deliverable" in payload and isinstance(payload["deliverable"], dict):
        deliverable = payload["deliverable"]
        return (
            f"stage={deliverable.get('stage_id')}; schema={deliverable.get('schema_name')}; "
            f"verdict={deliverable.get('verdict')}; artifact={deliverable.get('artifact_path')}"
        )
    if "campaign" in payload and isinstance(payload["campaign"], dict):
        campaign = payload["campaign"]
        return (
            f"campaign={campaign.get('id')}; status={campaign.get('status')}; "
            f"cursor={campaign.get('cursor')}/{len(campaign.get('stages') or [])}"
        )
    parts = [f"{key}={payload[key]}" for key in _BODY_KEYS if key in payload]
    return "; ".join(parts) if parts else json.dumps(payload, ensure_ascii=False)[:300]


def event_to_message(event: dict) -> OutboundMessage | None:
    """Map one stored event to a channel message, or None if it is not worth reporting."""
    etype = event.get("type")
    payload = event.get("payload") or {}
    if etype == EventType.ACTION_PROPOSED.value:
        # only proposals that genuinely await human approval surface as a request
        if isinstance(payload, dict) and payload.get("requires_approval"):
            return OutboundMessage(
                kind=MessageKind.APPROVAL_REQUEST,
                title="Approval needed",
                body=_body(payload),
                correlation_id=event.get("correlation_id"),
                source_event_type=etype,
            )
        return None
    kind = _REPORTABLE.get(etype)
    if kind is None:
        return None
    return OutboundMessage(
        kind=kind,
        title=str(etype),
        body=_body(payload),
        correlation_id=event.get("correlation_id"),
        source_event_type=etype,
    )


def make_channel(config: ChannelConfig | None = None) -> Channel:
    config = config or load_channel_config()
    if config.kind == "telegram":
        return TelegramChannel(config)
    return LocalInboxChannel(config.root)
