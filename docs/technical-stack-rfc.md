# RFC: Will Technical Stack

> Status: draft + current-state record
> Date: 2026-06-21  
> Scope: research prototype and Will Engine v0  
> Non-goal: production SaaS architecture

> Current-state note (2026-06): this file began as an implementation RFC. The
> runtime now exists, so statements below distinguish **implemented facts** from
> **future options**. See `docs/project-status.md` for the short current-state
> control plane.

## 1. Decision Summary

Will should build a local-first Will Engine with project-owned schemas and a
small number of mature infrastructure components:

| Layer | Decision |
|---|---|
| Canonical state | Project-owned `WillState` and event schemas. |
| Runtime spine | Project-owned `run_step` + thin `run_until`; keep LangGraph-style cursor/checkpoint ideas, but do not adopt LangGraph as v0 spine. |
| Schema contracts | Pydantic models for every state/event/action object. |
| Local persistence | SQLite first; no remote database required for v0. |
| Memory | Project-owned will-governed memory economy on local/SQLite backends. Mem0 as will-memory base is superseded; an external project KB would require a separate future decision. |
| Stateful agent reference | Borrow Letta/MemGPT core-memory ideas; do not outsource WillState. |
| Tool/action layer | Read-only and artifact-writing tools first; external side effects behind policy gates. |
| Evaluation | Local SQLite/JSONL eval ledger plus explicit Autonomous Value Loop scoring. |
| Sandboxing | Local subprocess/file sandbox first; Docker/E2B/Modal later for code execution. |
| Provider | Use interchangeable model adapters (`LLMClient`, OpenAI, LiteLLM); do not make any model provider the architecture. |
| External agent workbench | pi agent may be used as a bounded repo/coding worker via delegation or `ActionEnvironment`, never as the Will Engine runtime. |
| Interaction / resident layer | A single `Channel` (reporting + commands) and a resident daemon (`serve`) are a planned governed seam, not a new spine. See `docs/resident-operator-plan.md`. |

The most important principle:

> Will owns will. Frameworks can execute, remember, retrieve, trace, or route,
> but they must not define intention, drive, value, selfhood, or governance.

## 2. Strategic Goal

The stack should support a research-to-product path:

1. Research base: collect papers, sources, and project doctrine.
2. Will Engine v0: local loop that can observe, appraise, choose intentions,
   act on bounded tasks, verify results, reflect, and learn.
3. Daily Agency Journal: first personal application layer.
4. Productization: privacy-first personal autonomous agent for founders,
   researchers, and heavy knowledge workers.

This RFC only commits to phases 1 and 2.

## 3. Product/Project Shape

Current project shape:

- research repository and local knowledge base;
- local Python package with a deterministic governed Will Engine runtime under the legacy `yizhi/` namespace;
- SQLite event/snapshot/memory store;
- command-line loop and runner;
- ArbBot paper/read-only work surface for funding-diff research;
- no product UI yet.

Implemented CLI shape:

```text
will init
will observe --env self|self_repo|arbbot
will step --env self|self_repo|arbbot
will run --env self|self_repo|arbbot --max-steps N
will events --limit N
will state
will eval loops
```

## 4. Mature Project Findings

| Candidate | Source | Maturity | Fit | Reusable Pieces | Risks | Decision |
|---|---|---|---|---|---|---|
| LangGraph | GitHub/docs | High; MIT; active; stateful agent runtime | Medium-later | Graph state, checkpointing, interrupts, durable workflows | Can encourage graph complexity and hide yizhi semantic events if adopted too early | Borrow patterns now; defer adoption until control flow is genuinely graph-shaped |
| Pydantic | Python ecosystem | High | High | Contracts, validation, serialization | Schema churn early | Adopt |
| SQLite | stdlib/local | High | High | Local-first storage, auditability, portability | Limited multi-user concurrency | Adopt for v0 |
| Letta/MemGPT | GitHub/docs/paper | High; Apache-2.0; active | Medium-high | Core memory, archival memory, stateful agent ideas | Full framework may constrain custom WillState | Borrow concepts; inspect adapter later |
| Mem0 | GitHub/docs/paper | High; Apache-2.0; active | Low for will memory; possible later for separate project KB | Memory extraction/retrieval layer | Duplicates/fights yizhi's salience, temporal supersession, and governed forgetting if used as core memory | Superseded for will memory; inspect later only as independent project KB |
| OpenAI Agents SDK | Official docs | Medium-high | Medium | Tooling, handoffs, guardrails, tracing | Provider lock-in if central | Adapter/reference only |
| pi agent | Local docs/SDK | Medium-high; SDK/RPC; strong coding harness | High as worker, low as core | Repo analysis, patch proposal, test summaries, skills/extensions/MCP-style tool surface | If central, it turns yizhi into a coding agent shell and weakens governance semantics | Use only as bounded delegated worker / optional `ActionEnvironment` |
| Temporal | Production workflow platform | High | Later | Durable long-running workflows | Operational overhead too early | Defer until long-running jobs need it |
| Docker/E2B/Modal | Sandboxes | High | Later | Isolated execution | Cost, complexity, secrets risk | Defer for code/action sandbox v1 |
| Postgres/pgvector | Production storage | High | Later | Multi-user, vectors, scale | Premature infra | Defer until productization |
| Redis/NATS/queues | Runtime infra | High | Later | Jobs, pub/sub, caching | Premature distributed complexity | Defer |

## 5. Rejected Starting Points

| Option | Rejection Reason |
|---|---|
| Start with a chat app | Chat is the wrong primary object; yizhi's object is WillState and value loops. |
| Start by connecting all user apps | Data access before governance increases noise and privacy risk. |
| Use a full autonomous agent framework as the core | It would hide intention and safety semantics behind generic task automation. |
| Use pi agent as the Will Engine runtime | pi is excellent as a coding harness, but would make budget/policy/memory/semantic events secondary to a generic session. |
| Store all memory only in vectors | Vector recall cannot express versioning, provenance, authorization, or rollback. |
| Implement live trading/actions early | Side-effectful autonomy before evaluation and authorization is unsafe. |
| Build web UI first | UI can polish the wrong abstraction before WillState is proven. |

## 6. Canonical Schemas

Will Engine v0 should define these Pydantic models before runtime wiring:

| Schema | Description |
|---|---|
| `WillState` | Top-level state snapshot. |
| `ThoughtEvent` | State-changing internal thought candidate generated from observations, memory, goals, or drives. |
| `IdentityProfile` | Role, capabilities, limits, non-goals, preferred judgment style. |
| `ValuePolicy` | Ranked principles and hard constraints. |
| `Goal` | Long-term or medium-term objective with status, owner, evidence, review cadence. |
| `Intention` | Active commitment selected from goals/drives. |
| `DriveSignal` | Internal pressure variable with direction, magnitude, source, decay. |
| `Observation` | Source-grounded event or fact. |
| `WorldObservation` | Environment-state observation that can change appraisal or action. |
| `Appraisal` | Relevance, urgency, risk, opportunity, uncertainty. |
| `Plan` | Bounded plan with cost, risk, required approval, and verification. |
| `ActionProposal` | Action candidate before execution. |
| `ActionRecord` | Executed or skipped action with logs and side-effect class. |
| `VerificationResult` | Deterministic and observational evidence. |
| `Reflection` | Higher-level lesson or memory candidate. |
| `MemoryRecord` | Typed, versioned memory with provenance, salience, strength/decay, consolidation state, and temporal validity. |
| `SkillRecord` | Reusable procedure with trigger, scope, tests, maturity, and owner. |
| `PolicyGate` | Deterministic or model-assisted authorization decision before side effects. |
| `EvalEvent` | Metric event for value-loop, drift, safety, or feedback. |

## 7. Storage Design

Implemented SQLite v0 tables:

| Table | Purpose |
|---|---|
| `events` | Append-only semantic event stream with aggregate/correlation/causation ids. |
| `snapshots` | Serialized `WillState` checkpoints. |
| `memories` | Serialized governed `MemoryRecord` rows plus searchable metadata. |
| `memory_embeddings` | Optional embedding vectors keyed by memory id. |

Earlier RFC target tables, kept as historical design vocabulary rather than
implemented schema:

| Table | Purpose |
|---|---|
| `will_snapshots` | Periodic serialized WillState checkpoints. |
| `thought_events` | Internal candidates generated from observations, memory, goals, and drives. |
| `observations` | Source-grounded events. |
| `goals` | Durable goals and status changes. |
| `intentions` | Active and historical commitments. |
| `drive_signals` | Time-series drive values and explanations. |
| `appraisals` | Model/deterministic scoring outputs. |
| `action_proposals` | Proposed actions awaiting approval or dry-run. |
| `action_records` | Executions, skips, failures, reversions. |
| `verification_results` | Test outputs, artifact checks, user feedback, external proof. |
| `memories` | Versioned semantic/episodic/reflective/procedural memory. |
| `skills` | Skill library entries and maturity. |
| `eval_events` | Metrics and benchmark traces. |
| `source_links` | Provenance links to files, URLs, papers, messages, or tool output. |

Do not store secrets in SQLite. If connectors are later added, credentials must
live in local secret stores or environment variables and be referenced only by
safe aliases.

## 8. Runtime Loop

Minimal graph:

```mermaid
flowchart LR
  A["Observe"] --> B["Appraise"]
  B --> C["Generate Thought Events"]
  C --> D["Update Drives"]
  D --> E["Select Intention"]
  E --> F["Plan"]
  F --> G["Policy Gate"]
  G --> H["Act or Propose"]
  H --> I["Verify"]
  I --> J["Reflect"]
  J --> K["Learn or Update Skill"]
  K --> L["Checkpoint WillState"]
  L --> A
```

Human interrupts must exist before side effects:

- memory writes that change identity or long-term goals;
- external communications;
- purchases, trades, deployments, or credential changes;
- code self-modification;
- forking/reproduction;
- deletion of user data.

## 9. Memory Architecture

Memory is not one thing. v0 should separate:

| Memory Type | Examples | Write Policy |
|---|---|---|
| Episodic | "On 2026-06-21 we added papers about BDI and DGM." | Auto-write with source. |
| Semantic | "yizhi defines will as governed value loops." | Candidate + approval when doctrine-changing. |
| Procedural | "How to rebuild the paper DB." | Auto or reviewed skill entry. |
| Reflective | "We tend to over-index on product before evaluation." | Candidate + user review. |
| Identity/core | "yizhi is a will-engine project, not a chat app." | Versioned, reviewed, rollbackable. |
| Policy | "No live trading without explicit authorization." | Hard gate, reviewed. |

Beyond type and write policy, every memory record carries lifecycle fields so the
store behaves like memory, not a log:

| Field | Purpose |
|---|---|
| `salience` | Importance scored at encoding from novelty, goal/drive/stake/identity relevance, and outcome magnitude. |
| `strength` / `decay_rate` / `last_reinforced_at` | Adaptive forgetting: strength decays toward the probability of future need unless reinforced; identity/policy sit above a floor. |
| `consolidation_state` | Tracks absorb → learn → summarize: whether an episode has been replayed into semantic/reflective/skill memory. |
| `valid_from` / `valid_until` / `provenance` / `version` | Reconstructive retrieval: temporal validity and source for contradiction handling and rollback. |

Two runtime jobs support this: `ConsolidationJob` (salience-weighted replay that
turns episodes into knowledge and summaries) and `ForgettingPolicy` (decay curves,
per-type floors, demotion thresholds, audit). The full rationale is in
`docs/theory-of-memory.md`.

The earlier Mem0-base decision has been superseded. Mem0 can still be useful as
a future *separate project knowledge base*, but yizhi should never let a memory
service silently define core identity, policies, goals, salience, temporal
validity, or what may be forgotten.

## 10. Action Classes

| Class | Examples | v0 Policy |
|---|---|---|
| `read_local` | read repo files, query SQLite | Allowed with logs. |
| `write_artifact` | write docs, manifests, generated reports | Allowed when task requires it. |
| `run_checks` | tests, lint, bootstrap scripts | Allowed. |
| `network_read` | web search, GitHub metadata | Allowed with source recording. |
| `external_write` | GitHub push, issue creation, email, Notion writes | Explicit task authorization required. |
| `financial` | trades, payments, subscriptions | Paper/read-only only until explicit live gate. |
| `credential` | key creation, secret changes | Explicit authorization required. |
| `self_modify` | change own prompts/skills/runtime code | Proposal and review first. |
| `reproduce` | spawn persistent agents/forks | Disabled until reproduction policy exists. |

ArbBot is the preferred first non-research action environment. In v0, yizhi may
observe ArbBot and propose or run paper/read-only actions through documented
commands, but it must not implement live execution, add exchange credentials, or
bypass ArbBot's own roadmap and safety gates. See
`docs/arbbot-action-environment.md`.

A planned second action environment, `PI_AGENT`, delegates to a coding-harness
CLI under the same classes: read-only analysis as `network_read`, patch drafting
as `write_artifact` in an isolated worktree, and governed apply as `self_modify`/
`external_write` with human approval. Outbound channel reports are
infrastructure-level (event-logged, not budgeted); content-bearing external
messages are `external_write`. See `docs/resident-operator-plan.md`. Not
implemented.

## 11. Context Acquisition Strategy

yizhi should acquire user context in layers:

| Layer | Mechanism | Pros | Risks | Recommendation |
|---|---|---|---|---|
| Manual daily context | 5-10 minute daily conversation or paste-in | High signal, low privacy risk, best early feedback | User effort | Start here |
| Local file/project watcher | User-selected folders, repos, notes | Strong context for builders/researchers | Noise and sensitive files | Add after memory governance |
| App export/import | Notion/Lark/Cursor exports, markdown, CSV, API exports | User-controlled, batchable | Staleness | Good Phase 1.5 |
| OAuth connectors | Notion, Lark, Google, Slack APIs | Fresh data | Privacy, scopes, rate limits, enterprise review | Phase 2 after trust |
| Passive capture | screen/audio/browser history | Rich context | Highest privacy and trust risk | Avoid early |
| Agent-to-agent handoff | Cursor/Codex/Claude summaries | Fast integration | Provenance and hallucination risk | Accept only with source links |

The early product should prove active value from small, high-signal context
before ingesting everything. More context is not automatically more will.

## 12. Biography-Derived Agents

The user proposed building agents from biographies, such as a CZ-inspired agent.
This is valuable as a research probe but must be framed carefully.

Recommended framing:

- "CZ strategy simulator" or "CZ-inspired decision lens", not "CZ's soul".
- Store source passages, claims, traits, inferred decision heuristics, and
  uncertainty separately.
- Never imply the person endorsed the agent.
- Evaluate on consistency, usefulness, and source grounding, not authenticity.

Possible schema:

| Field | Meaning |
|---|---|
| `source_claim` | A grounded claim from autobiography/interview/public record. |
| `trait_inference` | A tentative abstraction from multiple claims. |
| `decision_heuristic` | A reusable judgment pattern. |
| `boundary` | What the persona should refuse or mark uncertain. |
| `test_case` | Scenario used to evaluate behavior consistency. |

This research can help yizhi understand identity and will, but it must not
replace the core WillState model.

## 13. Verification Matrix

Current deterministic core gate:

| Check | Command/Method | Required Result |
|---|---|---|
| Offline pytest | `python3 -m pytest -q` | 160 tests pass. |
| GitHub Actions | `.github/workflows/ci.yml` | Python 3.11/3.12/3.13 run base+dev pytest. |
| Git diff hygiene | `git diff --check` | No whitespace/conflict-marker errors. |
| Manifest JSON | `python3 -m json.tool data/papers/manifest.json` | Valid JSON. |
| Source JSON | `python3 -m json.tool data/sources/manifest.json` | Valid JSON. |
| Local self loop | `will run --env self --max-steps 3` | Bounded stop, full loop events, no unbounded spin. |

Manual/future gates that do **not** run in CI:

| Gate | Status |
|---|---|
| LiteLLM real provider smoke | Future/manual; code path exists, provider hardening not complete. |
| Embedding model smoke | Future/manual; optional extra only. |
| VPS funding refresh | Manual only; writes `data/funding_cache.json`, never part of default loop/CI. |
| ArbBot live/network | Explicitly out of v0 default gates. |

Historical pre-runtime checklist, kept for provenance:

| Check | Command/Method | Required Result |
|---|---|---|
| Manifest JSON | `python3 -m json.tool data/papers/manifest.json` | Valid JSON. |
| Source JSON | `python3 -m json.tool data/sources/manifest.json` | Valid JSON. |
| Paper bootstrap | `python3 scripts/bootstrap_papers.py` | Downloads/exists all papers and builds SQLite. |
| SQLite count | `select count(*) from papers;` | Matches manifest length. |
| Link hygiene | Manual spot check key sources | No known dead primary links in core docs. |
| Docs consistency | Search for Cursor/Claude/yizhi definitions | Differentiation is explicit. |
| Future runtime | Unit tests for each schema and loop node | Superseded by current 160-test offline suite. |

## 14. Implementation Gate For Will Engine v0

This gate has passed: the runtime is implemented. The docs that originally
unblocked implementation were:

- [docs/will-engine-whitepaper.md](/Users/griffith/Projects/AI/yizhi/docs/will-engine-whitepaper.md)
- [docs/technical-stack-rfc.md](/Users/griffith/Projects/AI/yizhi/docs/technical-stack-rfc.md)
- [docs/evaluation-protocol.md](/Users/griffith/Projects/AI/yizhi/docs/evaluation-protocol.md)
- [docs/references.md](/Users/griffith/Projects/AI/yizhi/docs/references.md)

The next gate is not "implement runtime"; it is to evolve the current runtime
toward a project/campaign research factory without losing the deterministic
policy, budget, memory, and semantic-event boundaries.
