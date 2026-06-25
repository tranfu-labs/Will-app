# Memory Fork Strategy

> Status: decision record — **SUPERSEDED (2026-06-25)**
> Date: 2026-06-21
> Purpose: decide which mature open-source memory project yizhi should fork/extend
> as the base for its memory system, instead of building from scratch. Based on a
> deep fork-ability deep-dive of four candidates (Mem0, Letta, Graphiti, cognee).

> **UPDATE (2026-06-25) — decision reversed: yizhi does NOT use Mem0.**
> The governance modules below (salience-at-encoding, adaptive forgetting,
> consolidation, will-ranking) were built and tested directly on a local in-memory /
> SQLite backend. In practice that governed economy is *richer* than what a generic
> vector store (Mem0 included) provides in the dimensions that matter here — salience,
> bi-temporal supersession, governed forgetting — so renting Mem0 would either
> duplicate or fight it. The `Mem0Backend` stub and the `memory` extra were removed;
> the patterns to graft (bi-temporal validity, consolidation cadence) were absorbed
> as our own code. The candidate analysis below is kept for the historical rationale.

## 0. Original decision (TL;DR) — see UPDATE above; no longer in effect

> **Base = Mem0, extended (not hard-forked) behind yizhi's own will-governed
> schema.** Graft the bi-temporal validity pattern from Graphiti and the
> background-consolidation cadence from Letta/cognee. Build the four governance
> modules — salience-at-encoding, adaptive forgetting, consolidation, will-ranking
> — that *all four* candidates lack. Depend on a pinned Mem0 and keep yizhi's
> modules a thin layer (composition); hard-fork only if upstream blocks us.

This keeps yizhi local-first, minimizes 魔改 friction, and concentrates our effort
on the part that is actually the moat — and that nobody in the field has built.

## 1. The Constraints That Decide It

The four candidates all scored ~3.5/5 in isolation. The decision is made by
yizhi's *own* constraints, not by a generic "best memory library":

1. **Local-first.** `technical-stack-rfc.md` commits v0 to SQLite, no remote
   database, library/CLI not server. A base that forces a server or a graph DB
   fights this.
2. **Will owns governance.** yizhi must own salience, decay, consolidation,
   identity, and policy (see `theory-of-memory.md`). The base supplies storage and
   retrieval *infrastructure*, never the memory *economy*.
3. **魔改, not maintenance hell.** We want to heavily modify a base, but not
   inherit a hard fork of a fast-moving repo we must hand-merge forever.
4. **Scope = memory layer.** We are choosing a memory substrate, not a whole agent
   framework.

## 2. The Four Candidates

All four are Apache-2.0 (clean to fork and ship). Stars/health approximate, as of
2026-06.

| Project | Stars | Stack & weight | Lock-in | Unique strength | Fork friction | Verdict |
|---|---|---|---|---|---|---|
| **Mem0** (`mem0-github`) | ~59k | Python, **library mode, no server** | **None** — 24+ vector stores, 16+ LLMs, 11+ embedders all pluggable | Clean provider abstractions; hybrid retrieval (semantic+BM25+entity); search-time decay already shipped | **Low** — additive grafting on clean seams, not fighting core | Fork/extend wholesale |
| **Letta** (`letta-github`) | ~23k | Python, **server-centric** (FastAPI + Postgres/pgvector + Docker) | High — server + Postgres | 3-tier memory; **sleeptime agent** (background consolidation); full agent runtime + tools | Moderate — subclass agents; rip out server for a library | Fork only if yizhi is a service |
| **Graphiti/Zep** (`graphiti-github`) | ~28k | Python, **needs a graph DB** (Neo4j/FalkorDB) | Medium — graph DB | **Bi-temporal model**: valid_at/invalid_at, non-lossy contradiction handling | Low–Med, but you inherit 4 missing layers + a graph DB | Borrow the temporal pattern |
| **cognee** (`cognee-github`) | ~18k | Python, graph+vector, 50+ deps, ~weekly releases | Mod–High | **Memify**: a real extraction→enrichment→write-back consolidation seam | Moderate; weekly releases make a hard fork painful | Wrap, don't fork |

## 3. What All Four Lack — and Why That Is Good News

None of the four implements the things that make memory *will-governed*:

- **salience scored at encoding** (all infer importance implicitly, at best);
- **adaptive forgetting / eviction** (Mem0 has search-time decay only; Graphiti is
  explicitly non-lossy with an open, unimplemented decay issue; cognee has
  frequency weights but no time-decay; Letta has recency decay, not will-driven);
- **consolidation that replays episodes into semantic memory/skills** (only partial
  — cognee Memify, Letta sleeptime, Graphiti communities);
- **goal/drive/stake/identity governance of memory** (absent everywhere).

> This confirms the project thesis: the will-governed memory economy is real, and
> unclaimed. The base choice is therefore about **substrate fit**, not about which
> base has more of yizhi's special sauce — none of them do. We are buying storage
> and retrieval plumbing, and building the economy ourselves.

## 4. Why Mem0 Is the Base

| Decisive criterion | Mem0 | Letta | Graphiti | cognee |
|---|---|---|---|---|
| Local-first / no server | **Yes (library)** | No (server) | No (graph DB) | No (graph+vector) |
| Zero infra lock-in | **Yes** | No (Postgres) | Partial (graph DB) | Partial |
| Fork friction | **Low (additive)** | Moderate | Low–Med | Moderate + churn |
| Scope = memory layer | **Yes** | No (whole framework) | Yes | Yes |
| Community health | **Largest, very active** | Active | Active | Active, churny |

Mem0 wins on every criterion that yizhi's constraints actually weight. Its clean
`LLMBase` / `EmbeddingBase` / `VectorStoreBase` / `Memory` abstractions mean we can
run fully offline with local models and a local vector store, and inject our
governance at well-defined seams without rewriting the core.

**The tradeoff we accept:** Mem0's contradiction/temporal handling is weaker than
Graphiti's bi-temporal model. We close that gap by grafting the validity-window
pattern (§6), not by adopting a graph DB.

## 5. Extend, Don't Hard-Fork

Mem0 moves fast (reported 10+ commits/day in June 2026). A hard, divergent fork
would be a permanent merge burden. So:

- depend on a **pinned** `mem0ai` version as a library;
- implement yizhi's governance as a **thin layer in `yizhi/`** (composition over
  inheritance), calling Mem0 at its public seams;
- only hard-fork if we are forced to change Mem0 core extraction internals.

This is the "wrap, don't fork" wisdom from the cognee analysis — applied to Mem0,
whose seams are cleaner, so it is even more viable here.

## 6. The Four Modules yizhi Builds (the Moat)

Each maps to a clean Mem0 seam and to `theory-of-memory.md` §5.

| Module | Responsibility | Mem0 hook |
|---|---|---|
| `SalienceScorer` | Score importance at encoding from novelty, goal/drive/**stake**/identity relevance, outcome magnitude. | Intercept in `Memory.add()` after extraction, before persistence. |
| `ForgettingPolicy` | Real adaptive forgetting: strength decays toward probability of future need; identity/policy floored; demote→archive→drop, reversible. | Extend `VectorStoreBase` with `evict_stale()`; background worker. |
| `ConsolidationJob` | absorb → learn → summarize: salience-weighted replay turns episodes into semantic facts, reflective lessons, skills. | New worker; cadence modeled on Letta sleeptime / cognee Memify. |
| `WillRanker` | Retrieval ranked by alignment to current goals/drives/stake/identity, not generic similarity. | Wrap `Memory.search()` with a `context={goals,drives,stake,identity}` rerank. |

## 7. Patterns to Graft From the Others (Without Forking Them)

- **Graphiti — bi-temporal validity.** Adopt `valid_from` / `valid_until` on
  identity/semantic memory and non-lossy contradiction handling (already specified
  in `theory-of-memory.md` §5.5). Pattern, not dependency.
- **Letta — sleeptime + always-in-prompt core memory.** Model `ConsolidationJob`
  cadence on the sleeptime heartbeat; model identity memory on the always-present
  core block.
- **cognee — Memify.** Model the consolidation pipeline on
  extraction → enrichment → write-back.

## 8. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Mem0 upstream velocity / breaking changes | Pin version; thin composition layer; integration tests at the seam. |
| Mem0 extraction is goal-agnostic | Add salience/will at the `add()` boundary with our own scoring call. |
| Mem0 decay is search-time only (no eviction) | Add real eviction via `VectorStoreBase` extension + `ForgettingPolicy`. |
| Provider keys / cost | Use local/OSS models + a local vector store for v0 (Mem0 supports both). |
| Weaker temporal model than Graphiti | Graft validity-window pattern (§7) into our schema. |

## 9. Scaffolding Plan (Next Step)

On approval (task: 经确认后落地所选基座的 fork 脚手架):

1. Add `mem0ai` as a pinned dependency in `pyproject.toml` (optional extra).
2. Create `yizhi/memory/`:
   - `schema.py` — `MemoryRecord` with `salience`, `strength`, `decay_rate`,
     `last_reinforced_at`, `consolidation_state`, `valid_from/until`, `provenance`,
     `version` (per `technical-stack-rfc.md` §9).
   - `store.py` — `MemoryStore` wrapping Mem0 behind yizhi's schema, with a
     local-only backend for v0.
   - `salience.py`, `forgetting.py`, `consolidation.py`, `ranking.py` — the four
     modules as stubs with deterministic v0 behavior + unit tests.
3. Wire `MemoryStore` into the engine loop; keep `self`/`arbbot` environments and
   all existing tests green.
4. No live LLM calls in v0 tests — deterministic stubs, mirroring the current
   runtime's local/deterministic stance.

## 10. Decision Record

> Base = **Mem0** (extend, pinned, composition). Temporal pattern = **Graphiti**.
> Consolidation cadence = **Letta sleeptime / cognee Memify**. Moat = yizhi's four
> governance modules (salience, forgetting, consolidation, will-ranking). All four
> candidates are Apache-2.0; none implements will-governed memory, so the economy
> is ours to own. See `docs/theory-of-memory.md` for the theory this implements.
