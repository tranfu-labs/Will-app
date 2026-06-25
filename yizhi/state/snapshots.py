"""Snapshot helpers."""

from __future__ import annotations

from pathlib import Path

from yizhi.core.schemas import WillState
from yizhi.state.store import create_snapshot, load_latest_snapshot


def load_or_create_state(path: str | Path) -> WillState:
    state = load_latest_snapshot(path)
    if state is not None:
        return state
    state = WillState()
    create_snapshot(state, path=path)
    return state
