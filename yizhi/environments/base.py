"""Environment protocol."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from yizhi.core.schemas import ActionProposal, ActionRecord, VerificationResult, WillState, WorldObservation


class ActionEnvironment(Protocol):
    name: str
    root: Path

    def observe(self) -> list[WorldObservation]: ...

    def propose_actions(self, state: WillState) -> list[ActionProposal]: ...

    def run(self, proposal: ActionProposal) -> ActionRecord: ...

    def verify(self, record: ActionRecord) -> VerificationResult: ...
