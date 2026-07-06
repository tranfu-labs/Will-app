"""Effect descriptions emitted by controller routing."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field

from will.core.ids import new_id
from will.core.schemas import WillModel


class EffectKind(StrEnum):
    APPEND_EVENT = "append_event"
    REQUEST_WORKER = "request_worker"
    WRITE_ARTIFACT_MANIFEST = "write_artifact_manifest"
    RECORD_STAGE_DECISION = "record_stage_decision"
    ADVANCE_STAGE = "advance_stage"
    REVISIT_STAGE = "revisit_stage"
    PAUSE_CAMPAIGN = "pause_campaign"
    COMPLETE_CAMPAIGN = "complete_campaign"


class ControllerEffect(WillModel):
    id: str = Field(default_factory=lambda: new_id("effect"))
    kind: EffectKind
    payload: dict[str, Any] = Field(default_factory=dict)
