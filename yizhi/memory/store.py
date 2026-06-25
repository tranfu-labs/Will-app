"""MemoryStore: yizhi's will-governed memory economy over a pluggable backend.

The store owns the three processes that distinguish memory from storage
(docs/theory-of-memory.md): salience-at-encoding on `remember`, will-governed
ranking on `recall`, consolidation on `consolidate`, and adaptive forgetting on
`forget_pass`. The backend (local in-memory or SQLite) only stores and
returns records. Deterministic v0: no LLM, no network; pass `now_ts` for
reproducible decay.
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable

from yizhi.core.schemas import (
    ConsolidationState,
    EventType,
    MemoryRecord,
    MemorySource,
    MemoryType,
    WillState,
)
from yizhi.core.time import utc_now_iso
from yizhi.memory.backends import LocalMemoryBackend, MemoryBackend
from yizhi.memory.consolidation import ConsolidationJob, ConsolidationResult
from yizhi.memory.embedding import Embedder, cosine
from yizhi.memory.forgetting import ForgettingPolicy, apply_decay, decayed_strength, should_forget
from yizhi.memory.ranking import rank
from yizhi.memory.salience import SalienceSignals, derive_signals, score_salience
from yizhi.memory.text import overlap

# A sink the will loop wires to the event store so every memory mutation is
# auditable. The store stays the single place memory events are emitted, while
# the *how* of persistence stays out of the economy. Default None keeps the
# deterministic library pure (no events, no db) for tests.
EventSink = Callable[[EventType, MemoryRecord], None]


def _expired_at(valid_until: str | None, now_dt: datetime) -> bool:
    """True if the validity window has closed by now. A malformed `valid_until`
    (e.g. a hand-edited or partially-written row) is treated as not-expired rather
    than crashing the recall — one bad row must not take down the safety channel."""
    if valid_until is None:
        return False
    try:
        return datetime.fromisoformat(valid_until) <= now_dt
    except ValueError:
        return False


class MemoryStore:
    def __init__(
        self,
        backend: MemoryBackend | None = None,
        policy: ForgettingPolicy | None = None,
        *,
        consolidation: ConsolidationJob | None = None,
        event_sink: EventSink | None = None,
        embedder: Embedder | None = None,
    ) -> None:
        self.backend: MemoryBackend = backend or LocalMemoryBackend()
        self.policy = policy or ForgettingPolicy()
        self.consolidation = consolidation or ConsolidationJob()
        self.event_sink = event_sink
        self.embedder = embedder

    def _emit(self, event_type: EventType, record: MemoryRecord) -> None:
        if self.event_sink is not None:
            self.event_sink(event_type, record)

    def remember(
        self,
        content: str,
        *,
        memory_type: MemoryType = MemoryType.EPISODIC,
        kind: str | None = None,
        will_state: WillState | None = None,
        signals: SalienceSignals | None = None,
        source_event_ids: list[str] | None = None,
        subject: str | None = None,
        source: MemorySource = MemorySource.OBSERVED,
        grounding: list[str] | None = None,
        pinned: bool = False,
        trigger: str | None = None,
    ) -> MemoryRecord:
        """Encode a memory, scoring salience at write time (the anti-log step).
        `subject` keys temporal supersession (the stable entity a state-memory is
        about). `source` marks observed vs inferred; `grounding` pins it to real
        artifacts; `pinned` makes it non-decaying (falsifications); `trigger` is a
        prospective cue. See docs/theory-of-memory.md sec 8."""
        if signals is None:
            signals = derive_signals(content, will_state) if will_state else SalienceSignals()
        salience = score_salience(memory_type, signals, will_state=will_state)
        mtype = memory_type if isinstance(memory_type, MemoryType) else MemoryType(memory_type)
        record = MemoryRecord(
            kind=kind or mtype.value,
            content=content,
            memory_type=mtype,
            salience=salience,
            source_event_ids=source_event_ids or [],
            subject=subject,
            source=source,
            grounding=grounding or [],
            pinned=pinned,
            trigger=trigger,
        )
        stored = self.backend.add(record)
        if self.embedder is not None:
            try:  # embed at write time so recall is cheap; never break a write on it
                self.backend.set_embedding(stored.id, self.embedder.embed([content])[0])
            except Exception:
                pass
        self._emit(EventType.MEMORY_CREATED, stored)
        return stored

    def reinforce(self, memory_id: str, *, now_ts: str | None = None, record: MemoryRecord | None = None) -> MemoryRecord | None:
        """Strengthen a memory on use (retrieval reinforcement). Pass `record` when
        the caller already holds it (e.g. from recall) to skip a redundant re-fetch."""
        record = record if record is not None else self.backend.get(memory_id)
        if record is None:
            return None
        now = now_ts or utc_now_iso()
        updated = record.model_copy(
            update={
                "strength": min(1.0, record.strength + (1.0 - record.strength) * 0.5),
                "reinforcement_count": record.reinforcement_count + 1,
                "last_reinforced_ts": now,
            }
        )
        stored = self.backend.update(updated)
        self._emit(EventType.MEMORY_REINFORCED, stored)
        return stored

    def _embedding_relevance(self, query: str, records: list[MemoryRecord]):
        """Build a relevance function over embedding cosine similarity, falling
        back to keyword overlap for any record lacking a stored embedding (e.g.
        written before semantic recall was enabled)."""
        try:
            query_vec = self.embedder.embed([query])[0]
        except Exception:
            return None  # embedder failed → rank() uses keyword overlap
        embeddings = self.backend.get_embeddings([r.id for r in records])

        def relevance(record: MemoryRecord) -> float:
            vector = embeddings.get(record.id)
            return cosine(query_vec, vector) if vector else overlap(record.content, [query])

        return relevance

    def recall(
        self,
        query: str,
        will_state: WillState,
        *,
        now_ts: str | None = None,
        k: int = 5,
        reinforce: bool = True,
    ) -> list[MemoryRecord]:
        """Return the top-k memories ranked by relevance and will, reinforcing
        what is recalled (use strengthens, as in human memory)."""
        now = now_ts or utc_now_iso()
        records = self.backend.all(live_only=True)  # revoked never rank; skip their parse + embeddings
        relevance_fn = self._embedding_relevance(query, records) if self.embedder is not None else None
        ranked = rank(records, query, will_state, now, k=k, policy=self.policy, relevance_fn=relevance_fn)
        results: list[MemoryRecord] = []
        for record, _score in ranked:
            if reinforce:
                results.append(self.reinforce(record.id, now_ts=now, record=record) or record)
            else:
                results.append(record)
        return results

    def recall_standing(
        self,
        *,
        now_ts: str | None = None,
        k: int = 3,
        reinforce: bool = True,
    ) -> list[MemoryRecord]:
        """Surface the will's *standing* lessons — high-salience reflective,
        identity, and policy memory — independent of textual relevance to any
        query. A prior refusal, or the identity itself, constrains every step,
        so it is recalled by salience and surviving strength rather than by
        similarity to the moment (docs/theory-of-memory.md sec 5.6, core memory;
        docs/theory-of-will.md, the asymmetry of safety). This is the second
        channel of will-governed retrieval; contextual `recall` is the first.
        Use reinforces, so only the strongest lessons stay resident."""
        now = now_ts or utc_now_iso()
        now_dt = datetime.fromisoformat(now)
        standing = {
            MemoryType.REFLECTIVE.value,
            MemoryType.IDENTITY.value,
            MemoryType.POLICY.value,
            MemoryType.CALIBRATION.value,
        }
        candidates = [
            record
            for record in self.backend.all(live_only=True)
            if record.memory_type in standing
            and not _expired_at(record.valid_until, now_dt)
        ]
        candidates.sort(key=lambda r: (-(r.salience * decayed_strength(r, now, self.policy)), r.ts))
        results: list[MemoryRecord] = []
        for record in candidates[:k]:
            results.append(self.reinforce(record.id, now_ts=now) or record if reinforce else record)
        return results

    def due_prospective(self, *, now_ts: str | None = None) -> list[MemoryRecord]:
        """Prospective memories whose time-trigger has arrived — the deferred
        intentions it is now time to act on (theory-of-memory.md sec 8.2). Trigger
        form `time:<iso>`. Condition triggers (`condition:<desc>`) are fired by the
        caller when the cue is detected; here we resolve only time cues."""
        now = now_ts or utc_now_iso()
        now_dt = datetime.fromisoformat(now)
        due: list[MemoryRecord] = []
        for record in self.backend.all(live_only=True):
            if record.memory_type != MemoryType.PROSPECTIVE.value:
                continue
            trigger = record.trigger or ""
            if trigger.startswith("time:"):
                when = trigger[len("time:") :]
                try:
                    if datetime.fromisoformat(when) <= now_dt:
                        due.append(record)
                except ValueError:
                    continue
        return sorted(due, key=lambda r: r.trigger or "")

    def consolidate(self, will_state: WillState | None = None) -> ConsolidationResult:
        """Replay episodic memories into semantic summaries (absorb/learn/summarize).
        Periodic compression; reconsolidation is a separate per-step pass."""
        result = self.consolidation.run(self.backend.all(live_only=True), will_state)
        for summary in result.summaries:
            self.backend.add(summary)
            self._emit(EventType.MEMORY_CONSOLIDATED, summary)
        for updated_input in result.updated_inputs:
            self.backend.update(updated_input)
        return result

    def reconsolidate(self) -> list[MemoryRecord]:
        """Supersede stale same-subject memory so the store stays current (a
        newer reading closes the older's validity window). Per-step hygiene;
        emits MEMORY_SUPERSEDED. Reversible: history is kept, only re-dated."""
        superseded = self.consolidation.reconsolidate(self.backend.all(live_only=True))
        for record in superseded:
            self.backend.update(record)
            self._emit(EventType.MEMORY_SUPERSEDED, record)
        return superseded

    def forget_pass(self, *, now_ts: str | None = None) -> list[str]:
        """Demote the forgettable to a reversible revoke (graceful demotion, never a
        silent delete). Decay is computed *live* for the decision and never persisted:
        persisting a decayed strength without re-anchoring would compound across passes
        (each pass re-decaying an already-decayed value against the full window). So a
        survivor's at-rest strength is left untouched — ranking/standing recompute decay
        from the fixed anchor on read — and only the records actually forgotten are
        written, which also stops the per-step full-table rewrite."""
        now = now_ts or utc_now_iso()
        forgotten: list[str] = []
        for record in self.backend.all(live_only=True):  # revoked are already forgotten; don't re-scan them
            decayed = apply_decay(record, now, self.policy)  # live copy, for the decision only
            if should_forget(decayed, self.policy):
                revoked = decayed.model_copy(
                    update={
                        "revoked": True,
                        "revoke_reason": "forgotten:low-strength",
                        "consolidation_state": ConsolidationState.SUMMARIZED.value,
                    }
                )
                forgotten.append(revoked.id)
                self.backend.update(revoked)
                self._emit(EventType.MEMORY_FORGOTTEN, revoked)
        return forgotten
