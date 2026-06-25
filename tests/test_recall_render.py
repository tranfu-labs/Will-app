"""Tests for the shared recall→prompt seam: structured rendering and two-channel merge.

These pin the fidelity the audit found missing — that a recalled memory reaches a
prompt with the fields a model needs to weigh it (type, salience, recency, markers),
and that the loop's two-channel read-closure dedupes with standing lessons leading.
"""

from __future__ import annotations

from yizhi.core.schemas import MemoryRecord, MemoryType
from yizhi.engine.recall_render import merge_recall, render_recall

T0 = "2026-01-01T00:00:00+00:00"
T7 = "2026-01-08T00:00:00+00:00"
T_FAR = "2027-01-01T00:00:00+00:00"


def _mem(content, mtype, **kw) -> MemoryRecord:
    return MemoryRecord(kind="k", content=content, memory_type=mtype, **kw)


def test_render_recall_exposes_weighable_fields_and_markers():
    pinned_policy = _mem(
        "never place live orders during a dry-run", MemoryType.POLICY,
        salience=0.82, last_reinforced_ts=T0, pinned=True,
    )
    stale_semantic = _mem(
        "binance funding was 0.01%", MemoryType.SEMANTIC,
        salience=0.30, last_reinforced_ts=T7, valid_until=T_FAR,  # superseded -> stale
    )
    block = render_recall([pinned_policy, stale_semantic])

    assert block.startswith("recalled memory:\n")
    # type + salience + date + content survive the render (the model can weigh + date it)
    assert "policy" in block and "sal0.82" in block and "2026-01-01" in block
    assert "never place live orders during a dry-run" in block
    # markers distinguish a load-bearing pin and a stale (superseded) reading
    assert "pinned" in block
    assert "stale" in block


def test_render_recall_empty_is_blank_and_cap_is_respected():
    assert render_recall([]) == ""
    one = _mem("x", MemoryType.EPISODIC, salience=0.1, last_reinforced_ts=T0)
    block = render_recall([one] * 10, k=3)
    assert block.count("- [") == 3            # capped to k items
    # a custom label is honored (calibration uses "already known")
    assert render_recall([one], label="already known").startswith("already known:\n")


def test_merge_recall_dedupes_with_standing_first():
    a = _mem("standing lesson", MemoryType.POLICY, salience=0.8, last_reinforced_ts=T0)
    b = _mem("contextual episode", MemoryType.EPISODIC, salience=0.2, last_reinforced_ts=T0)
    # `a` is surfaced by BOTH channels; it must appear once, and standing leads.
    merged = merge_recall([a], [b, a])
    assert [m.id for m in merged] == [a.id, b.id]   # standing first, deduped (a not repeated)


def test_merge_recall_handles_empty_channels():
    assert merge_recall([], []) == []
    only = _mem("lone standing", MemoryType.IDENTITY, salience=0.9, last_reinforced_ts=T0)
    assert [m.id for m in merge_recall([only], [])] == [only.id]
