"""yizhi will-governed memory economy.

Memory is not storage. This package owns salience-at-encoding, adaptive
forgetting, consolidation (absorb -> learn -> summarize), and will-governed
retrieval ranking, over a pluggable backend (local in-memory or SQLite). The
governed economy here is deliberately richer than a generic vector store, so it
is self-built rather than rented. See docs/theory-of-memory.md.
"""

from __future__ import annotations

from yizhi.memory.backends import LocalMemoryBackend, MemoryBackend, SqliteMemoryBackend
from yizhi.memory.consolidation import ConsolidationJob, ConsolidationResult
from yizhi.memory.forgetting import ForgettingPolicy, apply_decay, decayed_strength, should_forget, tier
from yizhi.memory.ranking import rank, score
from yizhi.memory.salience import SalienceSignals, derive_signals, score_salience
from yizhi.memory.store import MemoryStore

__all__ = [
    "MemoryStore",
    "MemoryBackend",
    "LocalMemoryBackend",
    "SqliteMemoryBackend",
    "SalienceSignals",
    "score_salience",
    "derive_signals",
    "ForgettingPolicy",
    "decayed_strength",
    "apply_decay",
    "should_forget",
    "tier",
    "ConsolidationJob",
    "ConsolidationResult",
    "rank",
    "score",
]
