# Theory of Memory

> Status: theoretical foundation
> Date: 2026-06-21
> Purpose: define how yizhi remembers — not as storage but as a governed economy
> of salience, consolidation, and forgetting — grounded in human memory science
> and the agent-memory landscape. Feeds Axiom Two of `docs/theory-of-will.md` and
> the memory architecture in `docs/technical-stack-rfc.md`.

## 0. Why This Document Exists

Memory is the substrate of will (Axiom Two): without continuity there is no "I
have been pursuing this," only disconnected episodes of competence. yizhi's other
docs already say *what* to store and *how* to retrieve — but they quietly assume
that more memory is better. The project's guiding observation exposes the flaw:

> A person cannot recall what they ate three days ago, yet vividly remembers the
> day they sat the college entrance exam and the moment the scores came out. Human
> memory has triage — weight, decay, and category. A computer can record every
> meal to a file and "remember" all of them equally — and therefore has no triage
> at all.

This is the crux:

> **Recording everything is not a strong memory system; it is the absence of one.**

A flat, undecaying, equally-weighted log is *storage*. Memory is what storage
becomes once it is governed by salience, consolidation, and forgetting. This
document builds that governance from first principles, then turns it into a design
yizhi can implement and an explicit recommendation on what to build versus borrow.

## 1. Thesis: Memory Is a Governed Economy, Not a Store

State it sharply:

> Storage answers "can I retrieve X?" Memory answers "should X still be shaping
> me, and how strongly?"

A store keeps every item at equal strength forever, so retrieval *degrades* as the
store grows — everything competes equally and the signal drowns. A memory system
continuously decides what to strengthen, what to let fade, what to compress into
knowledge, and what to drop, so that what matters stays reachable and the noise
does not bury it.

Three processes define memory, and today's AI agents implement at most the first:

1. **Salience-gated encoding** — how strongly to write, decided at the moment of
   experience.
2. **Consolidation** — turning specific episodes into reusable knowledge and skill:
   absorb → learn → summarize.
3. **Adaptive forgetting** — letting strength decay toward the probability of
   future need.

yizhi must own all three. Sections 2–3 justify them from human memory; section 4
shows the field has not built them; sections 5–6 specify yizhi's version.

## 2. How Human Memory Actually Works

Five results from the literature, each with a direct engineering consequence.

### 2.1 Memory is typed, not one store

Squire's taxonomy divides long-term memory into declarative (episodic events,
semantic facts) and nondeclarative (procedural skills, priming, conditioning),
each with distinct brain systems and retrieval dynamics. There is no single
"memory"; there are several systems with different rules. (`squire-2004-memory-systems-of-the-brain`)

> Consequence: yizhi's typed memory — episodic, semantic, procedural, reflective,
> identity, policy — is correct in kind. Keep it. A single vector store collapses
> distinctions the brain spent evolution separating.

### 2.2 Encoding is salience-gated — the exam-day mechanism

Why the exam day and not the lunch? McGaugh's work shows emotional arousal
triggers adrenal stress hormones and amygdala activity that **selectively enhance
consolidation** of arousing experiences. Importance is stamped *at encoding*, not
discovered later. Beyond arousal, the brain privileges novelty, self-relevance,
goal-relevance, and prediction error. The exam day is high-stakes, self-defining,
novel, and emotionally arousing; the lunch is none of these. (`mcgaugh-2013-making-lasting-memories-significant`)

> Consequence: every memory write needs a **salience score computed at encoding**,
> not a uniform `insert()`. Generative Agents already approximate this with an
> LLM importance rating; yizhi should make salience multi-signal and tie it to the
> agent's own stakes. (`park-2023-generative-agents`)

### 2.3 Forgetting is adaptive, by design — the forgotten-lunch mechanism

Forgetting is not failure; it is optimization. Anderson & Schooler showed that a
memory's *availability* in the mind tracks the **probability it will be needed
again**, estimated from the frequency, recency, and spacing of past use — and that
human retention curves match the statistical structure of the environment. Richards
& Frankland make the functional case directly: the goal of memory is to **optimize
decision-making, not to transmit information faithfully**; transience (1) enhances
flexibility by discounting outdated information and (2) prevents overfitting to
noisy specifics, aiding generalization. (`anderson-1991-reflections-environment-memory`,
`richards-2017-persistence-and-transience-of-memory`)

> Consequence: yizhi must implement **decay** — memory strength that falls over
> time toward the expected probability of future need — and treat forgetting
> (demote, summarize, drop) as a first-class, governed operation, not a storage
> leak. This is the single capability the agent-memory field is missing (§4).

### 2.4 Consolidation turns episodes into knowledge — absorb → learn → summarize

This is the heart of "learning from memory," and it is exactly 吸纳 → 学习 → 总结.
Complementary Learning Systems theory (McClelland; updated by Kumaran, Hassabis &
McClelland for intelligent agents) holds that minds need **two** systems: a fast
**hippocampal** store that captures specific episodes immediately, and a slow
**neocortical** system that, through repeated **replay**, interleaves those
episodes into structured semantic knowledge — without overwriting what is already
known. Replay is not uniform: it is **weighted by reward and novelty**, so
important experiences are consolidated preferentially. (`kumaran-2016-complementary-learning-systems-updated`)

The LLM analog already exists: Generative Agents' **reflection** periodically reads
a batch of episodic observations and synthesizes higher-level insights, triggered
when accumulated importance crosses a threshold. (`park-2023-generative-agents`)

> Consequence: yizhi needs a **consolidation process** that runs between actions and
> on schedule:
> - **absorb** raw observations into episodic memory with salience;
> - **learn** by replaying salience-weighted episodes to extract semantic facts,
>   reflective lessons, and procedural skills;
> - **summarize** clusters into compact higher-level memory, retiring the redundant
>   detail.
> This is how the system *grows* from experience instead of merely accumulating it.

### 2.5 Retrieval is reconstructive, not playback

Memory is not a tape recorder. Recall **rebuilds** a memory from fragments and
schema, and the act of recall can **alter** what is stored (reconsolidation). Two
recalls of the same event can differ; a confident memory can be wrong. (Bartlett's
schema theory; the modern reconsolidation literature; and the agent-specific risk
of identity drift over long contexts. `identity-drift-2024-llm-agents`)

> Consequence: every memory needs **provenance, versioning, and a validity window**.
> yizhi must be able to say where a memory came from, when it was true, and whether
> a later memory superseded it — never treat a retrieved memory as ground truth.

## 3. Why "Record Everything" Is the Wrong Default for AI

The asymmetry the project's observation names is real and worth stating as failure
modes:

| "Record everything" property | Failure it causes |
|---|---|
| No salience at encoding | The exam day and the lunch are stored identically; the system cannot tell what mattered. |
| No decay | Stale facts retain full weight; the agent acts on outdated beliefs. |
| Equal weighting at retrieval | As the log grows, relevant memories are outvoted by volume; recall quality falls with scale. |
| No consolidation | Ten thousand episodes never become one lesson; the agent re-derives the same conclusion forever. |
| No forgetting | Cost (tokens, storage, latency) grows without bound; contradictions accumulate unresolved. |

These map directly onto yizhi's own metrics: **drift** (acting on stale or
contradictory memory), **resource discipline** (unbounded memory cost), and
**skill accumulation** (experience that never compounds). A store maximizes recall;
a memory system maximizes *useful* recall under bounded cost. yizhi needs the
latter.

## 4. The Agent-Memory Landscape and the Gap yizhi Should Own

A scan of the mature open-source memory systems (2026) shows a clear pattern: they
are strong on storage and retrieval, and weak on exactly the three human processes
above.

| System | Core mechanism | Has | Lacks |
|---|---|---|---|
| Generative Agents (`park-2023-generative-agents`) | memory stream + reflection | importance score, recency, reflection | decay, typed governance |
| MemGPT / Letta (`packer-2023-memgpt`) | core + archival tiers, self-edited | tiered memory, agent-managed writes, background reflection | salience, decay, forgetting |
| Mem0 (`mem0-2025-memory-layer`) | extract → consolidate → retrieve | LLM salience-ish ADD/UPDATE/DELETE, recency | time-decay, neuroscience-grounded salience |
| Zep / Graphiti (`zep-2025-temporal-knowledge-graph-memory`) | temporal knowledge graph | fact validity windows (when true / superseded) | decay, salience, consolidation |
| HippoRAG (`hipporag-2024-neurobiologically-inspired-memory`) | KG + Personalized PageRank index | hippocampal-style retrieval ranking | it is indexing, not a memory lifecycle |
| A-MEM (`amem-2025-agentic-memory`) | Zettelkasten auto-linking notes | self-organizing links, attribute update | decay, salience |
| Memory OS (`memoryos-2025-memory-os-of-ai-agent`) | OS tiers, FIFO + page promotion | tier transitions | decay, salience |
| Hindsight (`hindsight-2025-agent-memory-retain-recall-reflect`) | facts/experiences/summaries/beliefs + reflect | four-network split, first-class reflection | decay, salience |

The survey literature confirms the taxonomy and the gaps. (`zhang-2024-memory-mechanism-survey`)

> The consensus gap across the field: **online decay/forgetting, salience-at-
> encoding grounded in significance, mid-reasoning consolidation, temporal
> reasoning, and coherence-preserving updates.** Only managed services (e.g. an
> Ebbinghaus-curve memory) implement real decay; open-source systems mostly evict
> by LRU or not at all.

This gap *is* the set of human-memory features from §2. It is also yizhi's
opening: nobody owns a memory layer where **salience and forgetting are governed by
the agent's drives, stake, goals, and identity.** That is the will-engine
difference — memory triage is not generic, it is relative to what the agent is
trying to be and do.

## 5. yizhi's Memory Architecture

**Principle:** memory is a governed economy, and the governor is the will. What is
important, what decays, and what gets consolidated are decided relative to the
agent's goals, drives, stake (existence budget), and identity — not by a generic
relevance score.

Five mechanisms, each tracing to §2:

### 5.1 Typed, governed store (← 2.1)
Keep the six memory types (episodic, semantic, procedural, reflective, identity,
policy), each with its own write policy and decay floor. Identity and policy
memory have a high floor and require review to change; episodic memory is cheap to
write and quick to fade.

### 5.2 Salience-at-encoding (← 2.2)
Every `MemoryRecord` is scored at write time, not uniformly inserted. Salience is
multi-signal and **will-relative**:

```text
salience =
    novelty / surprise (prediction error vs world model)
  + goal_relevance
  + drive_relevance
  + stake_relevance      (does this bear on the existence budget / a commitment?)
  + identity_relevance
  + emotional_proxy      (high-magnitude outcomes: large win/loss, failure, conflict)
  + repetition / reinforcement
```

This extends the retrieval-time `memory_score` already in Axiom Two to **encoding
time**, where human memory actually sets importance.

### 5.3 Decay and selective forgetting (← 2.3)
Each memory carries a `strength` that decays over time unless reinforced (by
retrieval, repetition, or consolidation), with the decay rate set by the expected
probability of future need (Anderson & Schooler). Forgetting is a governed
lifecycle, not deletion:

```text
strong/hot  → (decay) → warm → (decay) → cold/archived → (decay) → summarized-then-dropped
```

Identity and policy memory sit above a floor and never silently drop. Everything is
reversible and logged: yizhi forgets like a brain (graceful demotion), not like a
`rm`.

### 5.4 Consolidation: absorb → learn → summarize (← 2.4)
A process that runs between actions and on schedule (and can be triggered when
accumulated salience crosses a threshold, as in Generative Agents):

1. **absorb** — batch recent episodic memories;
2. **learn** — replay them salience-weighted (CLS-style prioritized replay) to
   extract semantic facts, reflective lessons, and reusable skills;
3. **summarize** — compress clusters into compact higher-level memory and retire
   redundant detail, so the store gets *smaller and smarter*, not just larger.

This is the mechanism by which yizhi grows from experience — the project's "we
ourselves absorb, learn, and summarize" made concrete.

### 5.5 Reconstructive, governed retrieval (← 2.5)
Retrieval uses the multi-signal `memory_score`, but every memory carries
provenance, version, and a **validity window** (Zep-style: when true, when
superseded). Contradictions are resolved temporally rather than by silent
overwrite, and recall never treats a memory as ground truth.

### 5.6 Schema deltas
Add to `MemoryRecord`: `salience`, `strength`, `last_reinforced_at`,
`decay_rate`, `consolidation_state`, `valid_from` / `valid_until`, `provenance`,
`version`. Add two runtime objects: `ConsolidationJob` (absorb/learn/summarize run
with inputs, outputs, and salience weighting) and `ForgettingPolicy` (decay curves,
type floors, demotion thresholds, audit).

## 6. Build vs Integrate

The recommendation is deliberate and matches the existing RFC stance.

| Layer | Decision | Why |
|---|---|---|
| Salience / decay / consolidation **policy** and typed governance | **Build and own.** | This is the moat and the field's gap; it is where will governs memory. A memory service must not define what is important or what may be forgotten. |
| Typed store + event log | **Build on SQLite first.** | Local-first, auditable, versionable; vectors can't express provenance/validity/rollback. |
| Extraction + semantic retrieval | **Integrate behind the schema** (Mem0 as adapter candidate). | Mature, token-efficient; but kept behind yizhi's governance so it never owns identity/policy. |
| Temporal facts / contradiction handling | **Borrow the Graphiti/Zep pattern** (validity windows). | Clean, proven; implement as a field, adopt the engine only if needed. |
| Retrieval ranking | **Optionally borrow HippoRAG's Personalized PageRank** as one signal. | Useful neurobiologically-inspired ranking; not a lifecycle. |

> yizhi owns the memory *economy* (salience, decay, consolidation, governance) and
> rents the memory *infrastructure* (extraction, vector recall, graph storage).
> Never invert that.

## 7. Reference Map

- Human memory — typology: `squire-2004-memory-systems-of-the-brain`.
- Human memory — salience at encoding: `mcgaugh-2013-making-lasting-memories-significant`.
- Human memory — adaptive forgetting: `anderson-1991-reflections-environment-memory`,
  `richards-2017-persistence-and-transience-of-memory`.
- Human memory — consolidation (absorb/learn/summarize): `kumaran-2016-complementary-learning-systems-updated`.
- LLM memory — reflection and stream: `park-2023-generative-agents`; core/archival:
  `packer-2023-memgpt`; survey: `zhang-2024-memory-mechanism-survey`.
- LLM memory — production and patterns: `mem0-2025-memory-layer`,
  `zep-2025-temporal-knowledge-graph-memory`, `hipporag-2024-neurobiologically-inspired-memory`,
  `amem-2025-agentic-memory`, `memoryos-2025-memory-os-of-ai-agent`,
  `hindsight-2025-agent-memory-retain-recall-reflect`.
- Repos: `mem0-github`, `letta-github`, `graphiti-github`, `hipporag-github`,
  `cognee-github`.

## 8. Memory Architecture v1 (Converged)

Sections 1–7 derive memory from first principles. This section records the
*implementation-converged* architecture for yizhi's concrete north star — an
agent that uses LLM keys to continuously advance the ArbBot engineering project —
after a deliberate multi-lens review (cognitive science, production agent-memory
engineering, quant R&D, and a minimalist critique). The review's net effect was
to make the design **leaner**, not larger. Three findings drove it.

### 8.1 Two axes: layers are a *view*, categories stay lean

Memory has two orthogonal axes, and only one of them is stored.

- **Layers (access) are a computed projection, not a stored field.** "Core /
  working / archival" is `f(salience × decayed_strength, type)` — and the code
  already implements all three behaviours: `recall_standing()` *is* core memory,
  `rank()` top-k *is* working memory, the backend *is* archival. Reifying a
  layer column would create a second source of truth that disagrees with the
  strength score. So: **no layer field.** Token-budgeted context assembly is a
  later optimization, deferred until context is actually token-bound.
- **Categories (content) stay close to Squire's taxonomy.** Two proposed
  "categories" were demoted because they are not memory *kinds*:
  - **Project state is subject-keyed semantic memory**, not a type. A fact about
    ArbBot lives as a `semantic` record with `subject="arbbot/…"`; currency comes
    from the existing reconsolidation (§5.4) — a newer reading supersedes the
    older. Bi-temporal validity is a property of every fact (the Zep pattern,
    `zep-2025-temporal-knowledge-graph-memory`), not a node type.
  - **Vision/telos is `WillState` config**, not a memory record. A goal-generator
    is motivation; what is genuinely memory about it is the *semantic statement*
    of the goal and the *episodic/reflective* record of why it was adopted.

### 8.2 The real gaps were two missing memory *functions*, not more types

The review found two functionally dissociable memory systems genuinely missing —
both load-bearing for a long-horizon autonomous agent:

- **Calibration (metamemory)** — the running self-model of *reliability*: "when I
  predicted an edge, was I right?" It is split out of `identity` because it has
  the **opposite dynamics**: identity is near-frozen (high floor); calibration
  must track a *moving* hit-rate (low floor, kept current by supersession, not by
  freezing). Scored predictions consolidate here.
- **Prospective memory** — remembering *to act later* at a time or condition cue
  ("re-test after the data refresh", "if drawdown > X, revisit policy"). This is
  a distinct system from retrospective recall (Einstein & McDaniel), and it is
  exactly what a weeks-long agent runs on. A prospective record carries a
  `trigger` and surfaces when due.

Both are added as types. `procedural` stays defined but dormant until a multi-step
sequence actually recurs.

### 8.3 Cross-cutting attributes, and the verification frontier

Three attributes cut across all declarative memory:

- **`grounding`** — references to the real artifact a memory is about (a commit,
  a backtest id, a log). "Advance ArbBot without losing the plot" *is* keeping
  memory pinned to real project state.
- **`source`** — `observed | inferred | told`. Source memory is dissociable and
  decision-critical: a fact the agent *observed* is not a fact it *inferred*.
- **`pinned`** — a hard non-decay floor. Most memory should decay (transience
  aids generalization, `richards-2017-persistence-and-transience-of-memory`), but
  **falsifications must not**: a dead hypothesis that decays out of recall gets
  re-proposed as novel. Negative results are pinned.

The **believed-vs-verified** frontier (a `verified` flag set *only* by the
deterministic oracle, never by the LLM) is the highest-value mechanism none of
the surveyed systems have — but its exact schema is deferred until real
LLM-generated predictions exist to shape it, rather than guessed in the abstract.

### 8.4 R&D disciplines (principles now, code when the loop exists)

For an autonomous agent, cheap parallel backtests make naive significance
worthless: the 200th hypothesis clears a fixed bar by luck. The memory must
therefore enforce, when the experiment loop is built:

1. **Pre-registration** — a hypothesis is registered (params, dataset, decision
   threshold frozen) *before* its backtest; the oracle writes the result back to
   that exact entry. Post-hoc cherry-picking becomes impossible by construction.
2. **A multiple-testing gate** — trials-per-dataset deflate the significance bar.
   Without it, "verified" launders overfit noise.
3. **Conditional memory** — every edge carries its `regime` and `cost_model`
   version; an edge is recalled *in the regime it held*, not unconditionally.

`verified` reproduces a result *on this data*; only these disciplines tell the
agent it is *not just the luckiest of N tries*.

### 8.5 What is built now vs deferred

| Built in this pass | Deferred until trigger |
|---|---|
| `calibration`, `prospective` types | `verified`/prediction schema → first real LLM predictions |
| `grounding`, `source`, `pinned` fields | token-budgeted assembly → context becomes token-bound |
| pinned non-decay (falsifications) | multiple-testing gate → R&D experiment loop is built |
| calibration in standing recall; `due_prospective()` | `procedural` activation → a sequence recurs ≥N times |
| layers as the existing computed view | regime/cost memory → first cross-regime edge appears |

> The converged rule: **own a lean, dissociable category set and the deterministic
> economy; add capability as *mechanisms* (calibration, prospective, pinning,
> grounding), not as ever-more types; and let the first real prediction shape the
> verification schema rather than designing it in the abstract.**

## 9. Doctrine

> Storage keeps everything; memory keeps what matters.
> Importance is stamped at encoding, by salience, not discovered later.
> Forgetting is a feature: strength should decay toward the odds of future need.
> Consolidation is how experience becomes knowledge — absorb, learn, summarize.
> Retrieval rebuilds; so provenance, versions, and validity are mandatory.
> And the governor of all four is the will: yizhi remembers relative to its
> goals, drives, stake, and identity — not as an indiscriminate recorder.

See `docs/theory-of-will.md` Axiom Two for memory's role in will, and
`docs/technical-stack-rfc.md` §9 for the runtime memory schema.
