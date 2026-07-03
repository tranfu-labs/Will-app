"""Schemas for the web-side Liaison coordinator."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from yizhi.core.ids import new_id
from yizhi.core.schemas import YizhiModel
from yizhi.core.time import utc_now_iso


LiaisonSource = Literal["human", "liaison", "will", "system"]
PendingVerb = Literal["vision", "kill", "approve"]
RiskLevel = Literal["low", "medium", "high"]


class LiaisonPendingAction(YizhiModel):
    id: str = Field(default_factory=lambda: new_id("liaison-action"))
    verb: PendingVerb
    text: str
    risk: RiskLevel = "medium"
    confirmation_prompt: str
    correlation_id: str | None = None
    confirmed: bool = False


class LiaisonMessage(YizhiModel):
    id: str = Field(default_factory=lambda: new_id("liaison-msg"))
    ts: str = Field(default_factory=utc_now_iso)
    conversation_id: str = "default"
    source: LiaisonSource
    label: str = ""
    title: str = ""
    text: str = ""
    pending_action: LiaisonPendingAction | None = None
    refs: list[str] = Field(default_factory=list)


class LiaisonDecision(YizhiModel):
    action: Literal["tool", "reply", "propose"]
    tool: str | None = None
    args: dict[str, Any] = Field(default_factory=dict)
    reply: str = ""
    proposal: LiaisonPendingAction | None = None


class LiaisonTurnResult(YizhiModel):
    messages: list[LiaisonMessage]
    sent_command_id: str | None = None
    pending_action: LiaisonPendingAction | None = None
