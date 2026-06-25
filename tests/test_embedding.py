"""Offline tests for semantic recall wiring.

A FakeEmbedder gives deterministic vectors so the suite stays fast and offline
(no model load): it proves recall surfaces a memory that shares NO keywords with
the query — exactly what keyword overlap cannot do — and that records without an
embedding fall back to keyword relevance. The real model is exercised separately,
outside pytest.
"""

from __future__ import annotations

from yizhi.core.schemas import WillState
from yizhi.memory import MemoryStore
from yizhi.memory.embedding import cosine

# A tiny hand-built embedding space. The query and the semantically-related memory
# share NO words, but their vectors are close; the unrelated memory is orthogonal.
_QUERY = "funding rate arbitrage opportunity"
_RELATED = "perpetual basis carry between venues"      # no shared words with the query
_UNRELATED = "sunny weather expected tomorrow"
_TABLE = {
    _QUERY: [1.0, 0.0, 0.0],
    _RELATED: [0.96, 0.10, 0.0],
    _UNRELATED: [0.0, 0.0, 1.0],
}


class FakeEmbedder:
    def __init__(self, table):
        self.table = table

    def embed(self, texts):
        return [self.table[t] for t in texts]


def test_cosine():
    assert cosine([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert cosine([1.0, 0.0], [0.0, 1.0]) == 0.0
    assert cosine([], []) == 0.0
    assert abs(cosine([1.0, 1.0], [1.0, 0.0]) - 0.7071) < 1e-3


def test_recall_surfaces_semantic_match_with_no_shared_keywords():
    ws = WillState()
    store = MemoryStore(embedder=FakeEmbedder(_TABLE))
    store.remember(_RELATED, will_state=ws)
    store.remember(_UNRELATED, will_state=ws)

    recalled = store.recall(_QUERY, ws, k=2, reinforce=False)
    # the related memory ranks first by embedding cosine, despite sharing no words
    assert recalled[0].content == _RELATED
    # sanity: keyword overlap alone would NOT find it (no shared tokens)
    from yizhi.memory.text import overlap
    assert overlap(_QUERY, [_RELATED]) == 0.0


def test_recall_falls_back_to_keywords_for_unembedded_records():
    ws = WillState()
    store = MemoryStore(embedder=FakeEmbedder({**_TABLE, "paper manifest count check": [0.0, 1.0, 0.0]}))
    # a record added straight to the backend has no stored embedding
    from yizhi.core.schemas import MemoryRecord
    store.backend.add(MemoryRecord(kind="note", content="paper manifest count check"))
    recalled = store.recall("paper manifest count check", ws, k=1, reinforce=False)
    assert recalled and recalled[0].content == "paper manifest count check"  # matched via overlap fallback
