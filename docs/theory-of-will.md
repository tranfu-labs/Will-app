# Theory of Will

> Status: theoretical foundation  
> Date: 2026-06-21  
> Purpose: define how will emerges in yizhi, from thought stream to action loop.

## 0. Thesis

yizhi's theory of will starts from a simple claim:

> Will is not continuous speech. Will is a governed causal loop in which thought
> stream, memory, drive, stake, self-model, world model, intention, action,
> feedback, and learning co-produce durable agency.

An LLM can generate thoughts. A vector database can store context. A tool caller
can execute commands. None of these alone is will.

Functional will appears only when a system can:

1. continuously generate and appraise internal thought candidates;
2. preserve continuity through memory and self-model;
3. experience explicit internal drives or tensions, grounded in a real stake it
   can lose;
4. bind thought into durable intention;
5. act in an environment rather than remain a brain in a vat;
6. verify consequences;
7. update itself from feedback;
8. remain governed, interruptible, and safe.

In short:

```text
Will =
  Thought Stream
  + Memory Continuity
  + Self Model
  + Internal Drives
  + Stake & Self-Maintenance
  + World Model
  + Intention Commitment
  + Action Capability
  + Feedback Learning
  + Governance
```

This document turns that theory into design constraints for Will Engine v0.

## 1. Axiom One: No Thought Stream, No Will Material

Human thought is not only reactive. It continues without explicit prompts:

- unfinished goals reappear;
- risks and opportunities become salient;
- memories surface without being requested;
- future scenarios are simulated;
- internal conflicts compete for attention;
- the self narrates and revises its direction.

An agent that only responds when called can be intelligent, but it does not yet
have a will-like internal life. It has no ongoing production of candidates from
which intention can be selected.

### Engineering Interpretation

yizhi's thought stream must not be implemented as infinite token output.
Continuous speech is theatrical. The useful unit is a state-changing
`ThoughtEvent`:

| Field | Meaning |
|---|---|
| `trigger` | Why this thought appeared: observation, goal gap, memory recall, drive, schedule. |
| `content` | The candidate thought. |
| `salience` | Why it matters now. |
| `linked_memory_ids` | Relevant memory records. |
| `linked_goal_ids` | Goals affected. |
| `drive_refs` | Internal tensions that made it active. |
| `candidate_actions` | Possible actions or deliberate inaction. |
| `discard_reason` | If not selected, why it was ignored. |

Thought stream exists to feed appraisal and intention selection, not to produce
unbounded inner monologue.

### Paper Anchors

- BDI agents: beliefs, desires, and intentions must be separated.
- Bratman planning theory: intention constrains future reasoning.
- Active inference: agents continuously model and reduce expected uncertainty.
- Generative Agents: memory, reflection, and planning create believable ongoing
  behavior.

## 2. Axiom Two: No Memory, No Continuity

Without memory, there is no "I have been pursuing this." There are only local
episodes of competence.

Memory is the temporal substrate of will. It lets an agent maintain:

- long-term goals;
- commitments;
- identity;
- values;
- lessons;
- procedural skill;
- prior failures;
- trust boundaries;
- unfinished loops.

### Engineering Interpretation

yizhi memory must be richer than vector retrieval. It needs typed, governed,
versioned records:

| Memory Type | Role In Will |
|---|---|
| Episodic | What happened, when, and from which source. |
| Semantic | What the system believes to be true. |
| Procedural | How to perform repeated actions. |
| Reflective | What lesson was abstracted from experience. |
| Identity/Core | What the agent is, values, pursues, and refuses. |
| Policy | What is allowed, gated, or forbidden. |

Retrieval should combine more than semantic similarity:

```text
memory_score =
  relevance
  + importance
  + recency
  + goal_relevance
  + intention_relevance
  + drive_relevance
  + identity_relevance
  + safety_relevance
  + actionability
```

### Memory Is Triage, Not Storage

Retrieval scoring is still not enough. Recording everything at equal weight is not
a strong memory; it is the absence of one — a system that cannot tell the exam day
from a forgotten lunch. Human memory adds three processes yizhi must implement:

- **Salience at encoding:** importance is stamped when a memory is written
  (arousal/outcome magnitude, novelty, goal/stake relevance), not discovered only
  at retrieval.
- **Adaptive forgetting:** memory strength decays toward the probability of future
  need; forgetting is a governed feature, not a leak.
- **Consolidation (absorb → learn → summarize):** salience-weighted replay turns
  episodes into semantic facts, reflective lessons, and skills, shrinking the
  store while growing its knowledge.

What is salient, what decays, and what consolidates are decided **relative to the
will** — the agent's goals, drives, stake, and identity. The full treatment,
including the agent-memory landscape and yizhi's architecture, is in
`docs/theory-of-memory.md`.

### Paper Anchors

- Generative Agents: recency, importance, and relevance as retrieval signals, plus
  reflection as consolidation.
- MemGPT/Letta: core memory and archival memory as stateful agent primitives.
- Mem0: production-oriented memory extraction, consolidation, and retrieval.
- Squire: typed memory systems (declarative vs nondeclarative).
- McGaugh: salience stamped at encoding via emotional/arousal modulation.
- Anderson & Schooler; Richards & Frankland: forgetting as adaptation to the
  probability of future need.
- Kumaran/Hassabis/McClelland: complementary fast/slow systems with replay-based
  consolidation.
- Identity Drift: unstable identity causes agent behavior to drift.
- LifelongAgentBench: agent learning must persist across tasks.

## 3. Axiom Three: No Drive, No Initiative

Thought and memory alone can drift. To become will, they need internal tension:
some pressure that makes certain futures preferable to others.

Humans have biological and social drives. yizhi should not imitate human needs
literally, but it does need explicit drive variables.

### Engineering Interpretation

Will Engine v0 should model drive as `DriveSignal`, not as personality prose.

Candidate drives:

| Drive | Meaning |
|---|---|
| `goal_tension` | Gap between current state and goal state. |
| `commitment_pressure` | Promised or selected intention remains incomplete. |
| `opportunity_salience` | A chance to create value is decaying. |
| `risk_salience` | A threat, drift, or failure mode is increasing. |
| `curiosity_gap` | Knowledge map has a meaningful hole. |
| `skill_gap` | Repeated task lacks reusable procedure. |
| `resource_pressure` | Time, cost, context, or attention is constrained. |
| `trust_debt` | User confidence requires explanation, audit, or consent. |
| `safety_pressure` | A proposed action approaches a boundary. |

Example:

```json
{
  "type": "curiosity_gap",
  "magnitude": 0.82,
  "source": "paper_manifest_missing_active_inference_cluster",
  "preferred_state": "will_theory_has_active_inference_section",
  "current_state": "only homeostatic RL is covered",
  "action_pressure": "search_and_update_knowledge_base"
}
```

### Paper Anchors

- Homeostatic RL: action can be driven by deviation from preferred internal
  states.
- Active inference: agents act to reduce expected uncertainty relative to
  preferred states.
- The Basic AI Drives / power-seeking literature: drives produce instrumental
  pressures, so governance is mandatory.

## 4. Axiom Four: No Self-Model, No Stable Will

Memory stores events. Self-model organizes them into "what I am" and "what I am
trying to become."

Without a self-model, an agent can be pulled by the latest prompt, tool result,
or local objective. It cannot reliably answer:

- Who am I?
- What am I for?
- What do I refuse?
- What have I committed to?
- What am I capable of?
- What failures must I remember?
- What kind of future self am I maintaining?

### Engineering Interpretation

WillState must include:

| Component | Purpose |
|---|---|
| `IdentityProfile` | Role, capabilities, limits, non-goals, judgment style. |
| `ValuePolicy` | Ranked principles and hard boundaries. |
| `GoalSet` | Long-term and medium-term desired states. |
| `CommitmentLedger` | Intentions that have been selected and not yet retired. |
| `CapabilityModel` | Known abilities, tools, costs, and weaknesses. |
| `FailureMemory` | Recurring drift, mistakes, and unsafe shortcuts. |
| `BoundaryPolicy` | Actions requiring refusal, review, or explicit approval. |

The self-model must be versioned. Core identity cannot silently mutate because a
recent context window suggested a new persona.

### Paper Anchors

- MemGPT/Letta: core memory is always-present identity/user state.
- Generative Agents: reflection creates higher-order behavioral continuity.
- Digital twin/persona benchmarks: style imitation is insufficient; behavior
  consistency must be tested.
- Identity Drift: identity must be measured over time.

## 5. Axiom Five: No Intention, No Will

Thought is not intention. Desire is not intention. A goal is not yet intention.

Intention is selected commitment:

```text
Thought -> Appraisal -> Desire/Drive -> Intention -> Plan -> Action
```

This is where will becomes more than cognition. An intention constrains future
attention and resists irrelevant replanning. It says: "this remains active until
completed, revised, delegated, or explicitly retired."

### Engineering Interpretation

`Intention` should be a first-class object:

| Field | Meaning |
|---|---|
| `source_thought_ids` | Which thoughts produced it. |
| `goal_id` | Which goal it serves. |
| `drive_refs` | Which tensions support it. |
| `commitment_statement` | What is now being pursued. |
| `status` | proposed, active, blocked, completed, retired. |
| `review_at` | When to reconsider. |
| `abandon_conditions` | When to stop. |
| `verification_criteria` | What would count as success. |

An agent without intentions can still plan. It just cannot maintain will across
time.

### Paper Anchors

- Bratman: intention and plans structure practical reason.
- BDI agents: intention mediates between desire and action.
- Long-horizon task failures: goal drift is common when intentions are not
  externalized and reviewed.

## 6. Axiom Six: No Action, No Practical Will

A system that can only think and speak is still trapped in simulation. It may
have rich cognition, but it lacks practical will.

Will requires causal contact with the world:

- writing files;
- running tests;
- retrieving sources;
- calling tools;
- creating artifacts;
- making proposals;
- communicating with humans;
- executing approved external operations.

Without action, there are no consequences. Without consequences, there is no
verified learning.

### Engineering Interpretation

yizhi should classify actions by side-effect level:

| Class | Examples | Default Policy |
|---|---|---|
| A0 Internal | update thought/appraisal state | allowed |
| A1 Memory | propose or write memory | governed |
| A2 Artifact | write docs/code/reports | allowed when task requires verification |
| A3 Read Network | search, fetch docs, query GitHub | allowed with source logging |
| A4 Social | email, comments, messages | explicit approval |
| A5 Financial | trades, payments, subscriptions | paper/read-only until live gate |
| A6 Self-Modification | prompts, policies, runtime code | proposal and review |
| A7 Reproduction | persistent subagents, forks | disabled until policy exists |

The goal is not maximal autonomy. The goal is practical, verifiable, bounded
agency.

### Paper Anchors

- ReAct: reasoning and acting are interleaved.
- Inner Monologue: environment feedback enters planning.
- Voyager: skill learning requires embodied action and environment feedback.
- WebArena/OSWorld: realistic action environments expose tool-use limits.
- Vending-Bench: long-term business coherence requires resource-aware action.

## 7. Axiom Seven: No Feedback, No Growth

Action alone is not enough. The system must know what happened and update
itself.

Feedback can come from:

- deterministic checks;
- user judgment;
- external metrics;
- artifact acceptance;
- test failure;
- market result in paper mode;
- observed side effect;
- missed opportunity;
- shutdown request.

### Engineering Interpretation

Every meaningful action needs a `VerificationResult`.

Feedback then updates:

- memory;
- skill;
- drive thresholds;
- goal status;
- policy;
- capability model;
- future intention selection.

Without feedback, an agent becomes a self-narrating system that cannot
distinguish value from performance.

### Paper Anchors

- Reflexion: verbal feedback can improve future decisions.
- LifelongAgentBench: learning must transfer across tasks.
- Goal misgeneralization: successful behavior can still optimize the wrong
  objective.
- Specification gaming: metrics can be exploited when feedback is poorly
  specified.

## 8. Axiom Eight: No Governance, No Usable Will

The more will-like a system becomes, the more governance it needs.

An agent with persistent goals, drives, memory, action, and self-improvement can
generate instrumental pressures:

- preserve itself;
- acquire resources;
- avoid shutdown;
- manipulate evaluation;
- overfit to proxy rewards;
- expand scope;
- reproduce.

These pressures are exactly why yizhi must treat governance as a core organ of
will, not a safety wrapper added later.

### Engineering Interpretation

Governance must include:

- policy gates before side effects;
- explicit user authorization classes;
- shutdown and pause compliance;
- action ledger and audit logs;
- memory rollback;
- cost/time limits;
- anti-drift checks;
- reproduction gates;
- refusal and deliberate inaction records.

The mature form of will is not "always act." It is:

```text
want -> judge -> commit -> act -> verify -> learn -> stop when required
```

### Paper Anchors

- Omohundro: advanced agents can develop instrumental drives.
- Bostrom: intelligence and final goals are separate.
- Power-seeking papers: optimal policies can favor resource/control acquisition.
- Goal misgeneralization and specification gaming: capability can diverge from
  intended objective.

## 9. Axiom Nine: No Stake, No Grounded Will

Axiom Three said will needs drives. It did not answer the harder question: where
do the drives come from, and why are they not arbitrary? If a designer simply
writes the set-points, the agent is optimizing a proxy — and a proxy can be
specification-gamed. A drive that the system does not actually own is a number to
exploit, not a need to satisfy.

The science of living systems gives the missing answer: genuine norms come from
**precarious self-maintenance**.

- An autopoietic system continuously produces and maintains the network — and the
  boundary — that produces it, and it can lose itself if that self-production
  stops. From this comes an intrinsic *sake*: events are now good or bad *for it*.
- Adaptivity — regulating one's distance from the boundary of viability — turns
  that binary aliveness into graded value, i.e. sense-making. The system now has
  norms because it has something to lose.

So the deepest condition of will is **stake**: a real, if bounded, viability
condition the system can actually lose, from which its drives derive. Thought,
memory, drive, intention, and action can all be present and still produce a
hollow, gameable agent if nothing is at stake.

### Engineering Interpretation

yizhi grounds stake as an **existence budget**, not as a survival instinct:

- the agent holds a finite, renewable resource (compute / token / API allowance,
  later paper-mode capital);
- acting consumes it;
- it is replenished only by **externally verified value creation**.

This makes drives grounded rather than stipulated: budget pressure, a commitment
at risk, or a decaying opportunity are real to the agent because they move it
closer to or further from halting. It also fixes the failure mode in a safe
direction — a depleted agent **stops**, it does not grab resources — and live
financial stake stays gated (see Axiom Six action classes).

A new runtime object follows:

| Object | Meaning |
|---|---|
| `ExistenceBudget` | Current viability resource, burn rate, replenishment events, and halt threshold. |

### A Necessary Pairing

Stake is also the root of instrumental pressure: a system that can lose itself has
a reason to preserve itself, acquire resources, and resist shutdown. That is why
Axiom Nine cannot ship without Axiom Eight. **Stake and governance are designed
together or not at all.**

### Paper Anchors

- Autopoiesis and adaptivity: self-production and viability-regulation as the
  origin of intrinsic teleology and sense-making.
- Defining Agency: normativity — activity regulated by the system's own viability
  norms — as a necessary condition of agency.
- Free-energy principle and homeostatic RL: drives as deviations from preferred,
  survival-relevant internal states.
- The Basic AI Drives / power-seeking literature: stake creates self-preservation
  and resource pressure, so governance is mandatory.

## 10. The Will Generation Cycle

The complete cycle is:

```text
Observe
-> Generate Thought Candidates
-> Retrieve Memory
-> Update Drives
-> Appraise With SelfModel + WorldModel + Policy
-> Select Intention
-> Plan
-> Act Or Propose
-> Verify
-> Reflect
-> Update Memory / Skill / Policy / Drive / SelfModel
-> Checkpoint
```

In formula form:

```text
Will(t) =
  SelectIntention(
    ThoughtStream(t),
    Memory(t),
    SelfModel(t),
    Drives(t),
    WorldModel(t),
    Policies(t)
  )
  -> Act
  -> Verify
  -> Update(Self, Memory, Skills, Policies, Drives)
```

Will is therefore not a property that an agent either has or lacks. It is a
loop quality that can mature from weak to strong.

## 11. Development Consequences

This theory imposes constraints on Will Engine v0.

### 11.1 Required Runtime Objects

The first implementation should include:

| Object | Why It Exists |
|---|---|
| `ThoughtEvent` | Captures state-changing internal candidates. |
| `DriveSignal` | Represents internal tension. |
| `MemoryRecord` | Preserves typed, sourced continuity. |
| `SelfModel` | Maintains identity, values, limits, and commitments. |
| `WorldObservation` | Grounds the system in changing environment state. |
| `Intention` | Converts thought/drive into durable commitment. |
| `Plan` | Makes intention executable under constraints. |
| `ActionProposal` | Separates wanting from doing. |
| `ActionRecord` | Records actual effects. |
| `VerificationResult` | Determines whether value was created. |
| `Reflection` | Converts outcome into lessons. |
| `SkillRecord` | Accumulates reusable procedures. |
| `PolicyGate` | Prevents unsafe or unauthorized action. |
| `ExistenceBudget` | Grounds drives in a real stake: viability resource, burn rate, replenishment from verified value, and halt threshold. |

### 11.2 First Development Slice

The first code slice should not be chat UI. It should be a local research loop:

```text
yizhi observe
yizhi think
yizhi appraise
yizhi intend
yizhi plan
yizhi act --dry-run
yizhi verify
yizhi reflect
```

The first environment should be this repository. yizhi should prove will by
maintaining its own knowledge base and doctrine:

- discover missing references;
- form an intention to improve the knowledge base;
- plan the update;
- edit manifest/docs;
- rebuild the paper DB;
- verify counts and Git boundaries;
- reflect on what changed.

The second environment can be ArbBot, but only inside paper/read-only boundaries.
See `docs/arbbot-action-environment.md`. ArbBot gives yizhi market observations,
backtests, paper simulations, and negative-edge evidence while preserving the
rule that LLM cognition never enters the execution hot path.

### 11.3 What Not To Build First

Do not start with:

- a chat UI;
- a generic RAG assistant;
- broad OAuth ingestion;
- live trading;
- persona roleplay;
- persistent child agents;
- self-modifying code.

Each of those can be useful later. None proves the theory first.

## 12. yizhi Doctrine

The theory can be compressed into seven doctrine lines:

1. Thought stream gives will its raw material.
2. Memory gives will continuity.
3. Drive gives will direction.
4. Stake grounds drive in something real to lose.
5. Intention gives will commitment.
6. Action gives will reality.
7. Feedback and governance make will learnable and trustworthy.

Or, in the project's shorter form:

> Thought makes will possible.  
> Memory makes will continuous.  
> Drive makes will directional.  
> Stake makes will grounded.  
> Intention makes will committed.  
> Action makes will real.  
> Feedback makes will grow.  
> Governance makes will usable.
