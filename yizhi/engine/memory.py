"""Glue between the will loop and the will-governed memory economy.

The loop owns no memory mechanism: it delegates to `MemoryStore` over the
durable SQLite backend and lets the store emit MEMORY_* events through a sink.
This module only (a) builds that store for a loop and (b) derives salience
signals from the loop's live outcome — so importance is grounded in what
happened (a refusal, a failure, a high-stake action) and in the active drives,
rather than hand-passed. Deterministic v0: no LLM, no novelty/world-model yet
(that is the next deepening; see docs/theory-of-memory.md sec 5.2).
"""

from __future__ import annotations

from pathlib import Path

from yizhi.core.schemas import ActionClass, DriveSignal, LoopStatus
from yizhi.memory import MemoryStore, SqliteMemoryBackend
from yizhi.memory.store import EventSink

# How many memories the loop encodes per step is bounded; consolidation folds
# clusters and forgetting demotes the weak, so episodic writes stay an economy.
CONSOLIDATE_EVERY = 5

# Stake grounds salience (theory-of-will Axiom Nine): memory of what the agent
# could lose matters more. Map each action class to how much is at stake.
_STAKE_BY_CLASS: dict[str, float] = {
    ActionClass.CREDENTIAL.value: 0.9,
    ActionClass.SELF_MODIFY.value: 0.9,
    ActionClass.REPRODUCE.value: 0.9,
    ActionClass.FINANCIAL.value: 0.8,
    ActionClass.EXTERNAL_WRITE.value: 0.8,
    ActionClass.NETWORK_READ.value: 0.4,
    ActionClass.ARTIFACT.value: 0.4,
    ActionClass.MEMORY.value: 0.2,
    ActionClass.INTERNAL.value: 0.2,
}

# A refusal teaches the most; a failure next; success is moderately salient.
_OUTCOME_BY_STATUS: dict[str, float] = {
    LoopStatus.BLOCKED.value: 1.0,
    LoopStatus.FAILED.value: 0.9,
    LoopStatus.FULL.value: 0.5,
    LoopStatus.PARTIAL.value: 0.3,
}


def build_memory_store(db_path: str | Path, event_sink: EventSink | None = None, embedder=None) -> MemoryStore:
    """A MemoryStore on the durable event-store database, wired to emit events.
    `embedder` (optional) upgrades recall relevance from keyword to semantic."""
    return MemoryStore(backend=SqliteMemoryBackend(db_path), event_sink=event_sink, embedder=embedder)


def stake_relevance(action_class: ActionClass | str) -> float:
    value = action_class.value if isinstance(action_class, ActionClass) else str(action_class)
    return _STAKE_BY_CLASS.get(value, 0.2)


def outcome_magnitude(status: LoopStatus | str) -> float:
    value = status.value if isinstance(status, LoopStatus) else str(status)
    return _OUTCOME_BY_STATUS.get(value, 0.3)


def drive_relevance(drives: list[DriveSignal]) -> float:
    """Salience rises with the strongest live drive: memory follows pressure."""
    return max((drive.intensity for drive in drives), default=0.0)
