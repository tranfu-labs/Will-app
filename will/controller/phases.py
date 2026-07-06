"""Named phases for one autonomous campaign tick."""

from __future__ import annotations

from enum import StrEnum


class ControllerPhase(StrEnum):
    ANCHOR = "anchor"
    SELECT = "select"
    AUTHORIZE = "authorize"
    DELEGATE = "delegate"
    COLLECT = "collect"
    VALIDATE = "validate"
    REVIEW = "review"
    DECIDE = "decide"
    ROUTE = "route"
    CHECKPOINT = "checkpoint"


TICK_PHASES: tuple[ControllerPhase, ...] = (
    ControllerPhase.ANCHOR,
    ControllerPhase.SELECT,
    ControllerPhase.AUTHORIZE,
    ControllerPhase.DELEGATE,
    ControllerPhase.COLLECT,
    ControllerPhase.VALIDATE,
    ControllerPhase.REVIEW,
    ControllerPhase.DECIDE,
    ControllerPhase.ROUTE,
    ControllerPhase.CHECKPOINT,
)
