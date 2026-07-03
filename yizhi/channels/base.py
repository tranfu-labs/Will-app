"""Channel contract and message schemas for the interaction layer (R2).

A Channel is how a resident yizhi speaks to a human: `send` pushes a reportable event out,
`poll` drains human commands back in. Reporting is infrastructure-level — it carries no
WillState and burns no existence budget. The harness/will boundary is unchanged.
See docs/resident-operator-plan.md (pillar B, R2).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import Field

from yizhi.core.ids import new_id
from yizhi.core.schemas import YizhiModel
from yizhi.core.time import utc_now_iso


class MessageKind(StrEnum):
    REPORT = "report"                       # routine: a judgment / finding / completion
    ALERT = "alert"                         # attention needed: budget halted, failure
    APPROVAL_REQUEST = "approval_request"   # a gated action awaits human approve/deny


class InboundVerb(StrEnum):
    APPROVE = "approve"
    KILL = "kill"
    ASK = "ask"
    NOTE = "note"
    VISION = "vision"   # human-seeded strategy: re-seed WillState.vision (goal genesis runs under it)


class OutboundMessage(YizhiModel):
    id: str = Field(default_factory=lambda: new_id("msg-out"))
    ts: str = Field(default_factory=utc_now_iso)
    kind: MessageKind = MessageKind.REPORT
    title: str
    body: str = ""
    correlation_id: str | None = None
    source_event_type: str | None = None


class InboundCommand(YizhiModel):
    id: str = Field(default_factory=lambda: new_id("msg-in"))
    ts: str = Field(default_factory=utc_now_iso)
    verb: InboundVerb
    arg: str = ""
    raw: str = ""


@runtime_checkable
class Channel(Protocol):
    name: str

    def send(self, message: OutboundMessage) -> None: ...

    def poll(self) -> list[InboundCommand]: ...


def parse_inbound(line: str) -> InboundCommand | None:
    """Parse one inbound line: a JSON InboundCommand, or a `verb arg` text line. Anything
    that is not a known verb becomes a NOTE, so a human can type freely."""
    line = line.strip()
    if not line:
        return None
    if line.startswith("{"):
        try:
            return InboundCommand.model_validate_json(line)
        except Exception:  # noqa: BLE001 - malformed json falls through to text parsing
            pass
    parts = line.split(maxsplit=1)
    verb_raw = parts[0].lower()
    if verb_raw in {v.value for v in InboundVerb}:
        arg = parts[1] if len(parts) > 1 else ""
        return InboundCommand(verb=InboundVerb(verb_raw), arg=arg, raw=line)
    return InboundCommand(verb=InboundVerb.NOTE, arg=line, raw=line)
