"""Consolidation and reconsolidation (docs/theory-of-memory.md sec 5.4-5.5).

Two governed operations turn a growing pile of episodes into compact, coherent
knowledge. They run on different rhythms: reconsolidation is per-step hygiene
that keeps memory current; abstraction is periodic compression.

* Abstraction (`run`) — salience-weighted replay clusters raw episodic memories
  of the same kind into a semantic summary, so the store gets smaller and
  smarter. Deterministic v0: ordered reduction, no LLM; the seam for LLM
  abstraction under governance is documented in docs/memory-fork-strategy.md.

* Reconsolidation (`reconsolidate`) — when several memories speak to the same
  `subject`, the newest reading is current and the older ones are *superseded*:
  their validity window is closed (`valid_until`) and an heir is linked
  (`superseded_by`), so recall sees the present truth while history stays
  auditable. This is the deterministic core of contradiction resolution /
  temporal supersession; it needs no LLM because validity is decided by recency
  over a stable subject.

Inputs are marked, never deleted, so the lineage of belief is preserved.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from yizhi.core.schemas import ConsolidationState, MemoryRecord, MemoryType


@dataclass
class ConsolidationResult:
    summaries: list[MemoryRecord] = field(default_factory=list)
    updated_inputs: list[MemoryRecord] = field(default_factory=list)


def _type_value(memory_type) -> str:
    return memory_type.value if isinstance(memory_type, MemoryType) else str(memory_type)


class ConsolidationJob:
    """Replay raw episodic memories into semantic summaries, and reconsolidate
    same-subject memories so the store stays coherent and current."""

    def __init__(self, *, min_cluster: int = 2, summary_char_limit: int = 400) -> None:
        self.min_cluster = min_cluster
        self.summary_char_limit = summary_char_limit

    def run(self, records: list[MemoryRecord], will_state=None) -> ConsolidationResult:
        """Abstraction: cluster raw episodic memories by kind into semantic
        summaries; mark the inputs consolidated (not deleted)."""
        result = ConsolidationResult()
        clusters: dict[str, list[MemoryRecord]] = {}
        for record in records:
            if record.revoked:
                continue
            if _type_value(record.memory_type) != MemoryType.EPISODIC.value:
                continue
            if record.consolidation_state != ConsolidationState.RAW.value:
                continue
            clusters.setdefault(record.kind, []).append(record)

        for kind, group in clusters.items():
            if len(group) < self.min_cluster:
                continue
            ordered = sorted(group, key=lambda r: (-r.salience, r.ts))
            result.summaries.append(self._summarize(kind, ordered))
            for record in ordered:
                result.updated_inputs.append(
                    record.model_copy(update={"consolidation_state": ConsolidationState.CONSOLIDATED.value})
                )
        return result

    def reconsolidate(self, records: list[MemoryRecord]) -> list[MemoryRecord]:
        """Reconsolidation: among currently-valid memories sharing a subject, the
        newest is current; close the validity window of the older ones and link
        the heir. Returns the superseded records (updated copies)."""
        live_by_subject: dict[str, list[MemoryRecord]] = {}
        for record in records:
            if record.revoked or record.subject is None or record.valid_until is not None:
                continue
            live_by_subject.setdefault(record.subject, []).append(record)

        superseded: list[MemoryRecord] = []
        for group in live_by_subject.values():
            if len(group) < 2:
                continue
            ordered = sorted(group, key=lambda r: (r.valid_from, r.ts))
            current = ordered[-1]
            for older in ordered[:-1]:
                superseded.append(
                    older.model_copy(
                        update={
                            "valid_until": current.valid_from,
                            "superseded_by": current.id,
                            "version": older.version + 1,
                        }
                    )
                )
        return superseded

    def _summarize(self, kind: str, group: list[MemoryRecord]) -> MemoryRecord:
        clauses: list[str] = []
        for record in group:
            head = record.content.split(".")[0].strip()
            if head and head not in clauses:
                clauses.append(head)
        body = "; ".join(clauses)[: self.summary_char_limit]
        return MemoryRecord(
            kind=kind,
            content=f"[consolidated x{len(group)}] {body}",
            memory_type=MemoryType.SEMANTIC,
            consolidation_state=ConsolidationState.CONSOLIDATED,
            salience=max(r.salience for r in group),
            strength=1.0,
            provenance=[r.id for r in group],
            source_event_ids=sorted({eid for r in group for eid in r.source_event_ids}),
        )
