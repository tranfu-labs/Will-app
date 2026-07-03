# Will Engine Whitepaper

> Status: working thesis  
> Date: 2026-06-21  
> Purpose: define Will's research object, north star, technical hypothesis,
> evaluation protocol, and first implementation boundary.

## Abstract

Will studies and builds an AI Will Engine: a system layer that lets an agent
hold durable intentions, maintain a self-model, appraise the world through
internal drives, act through tools, learn from feedback, and create externally
verifiable value under human-governed constraints.

The theoretical foundation is defined in `docs/theory-of-will.md`: thought
stream gives will raw material, memory gives continuity, drive gives direction,
intention gives commitment, action gives reality, feedback gives growth, and
governance makes will usable.

The project must not become another chat surface, IDE assistant, prompt persona,
or generic agent framework. Cursor helps humans write code. Claude and ChatGPT
are model/dialog interfaces with tools. LangGraph, Letta, and Mem0 are useful
runtime and memory components. yizhi's distinct problem is deeper:

> How can an agent keep wanting, choosing, acting, learning, and self-maintaining
> across time without becoming unsafe, noisy, delusional, or merely theatrical?

The working answer is not "make the model talk continuously." It is to build a
governed loop that turns context into durable intention, intention into bounded
action, action into verified value, and feedback into improved future behavior.

## 1. Motivation

Current LLM agents are powerful but mostly reactive. They answer when called,
follow a user task while context lasts, and lose coherence when the task becomes
long, ambiguous, or resource-sensitive. They can simulate desire in language,
but simulation is not will.

yizhi starts from four observations:

1. Intelligence and will are different axes. A stronger model can reason better
   without having durable, governed intention.
2. Memory alone is not will. A vector database can remember facts while having
   no reason to act.
3. Autonomy alone is not will. A background loop can run forever while producing
   noise or pursuing proxy metrics.
4. Value creation is the only hard external test. If an agent cannot close a
   loop from self-initiated intention to verified output, it is not yet a
   productive will system.

The central design problem is therefore not "how do we make an AI feel alive?"
but:

> How do we implement functional will as a measurable, interruptible,
> value-producing control system?

## 2. What Is Not Will

The project should reject these false positives:

| False Signal | Why It Is Insufficient |
|---|---|
| Continuous output | A process can speak forever without stable intention or value creation. In Frankfurt's terms it is *wanton*: it has impulses but never endorses which should move it. |
| Persona imitation | Mimicking CZ, a founder, or the user can create style, not agency. |
| Long context | More tokens postpone forgetting but do not solve goal continuity. |
| Tool use | Calling tools is motor ability; will requires deciding why and when. |
| Memory retrieval | Retrieval is recall; will requires appraisal, commitment, and action. |
| Proactive notification | Interruption is not initiative unless it improves a goal-relevant state. |
| Self-modification | Mutation without governance is risk, not maturity. |

## 3. Working Definition

Functional will is the governed capacity to maintain and revise intentions over
time, select actions from internal drives and world state, create externally
verifiable value, learn from outcomes, and preserve safe continuity of self.

This definition depends on four necessary conditions:

1. continuous thought stream: the system can generate and appraise internal
   candidates without waiting for direct user prompts;
2. memory continuity: the system can preserve context, self, commitments, and
   lessons across time;
3. action embedding: the system can affect an environment and receive feedback,
   rather than remaining a brain in a vat;
4. grounded stake: the system has a real, bounded viability condition it can
   lose, from which its drives derive — otherwise drives are stipulated proxies
   and get specification-gamed. See `docs/what-is-will.md`.

It also requires second-order endorsement and governance. Without endorsement, an
impulse stream is wanton, not willed: will begins where the system selects which
drive should move it. Without governance, initiative becomes unsafe automation.

For engineering purposes, yizhi decomposes will into ten properties:

| Property | Engineering Form |
|---|---|
| Goal continuity | Durable goals and intentions survive context resets and sessions. |
| Self-model | The agent stores identity, capabilities, limits, preferences, and commitments. |
| Internal drive | The system has explicit needs/tensions that bias appraisal and action selection. |
| World model | The agent tracks environment state, opportunities, risks, and causal assumptions. |
| Memory | Events, reflections, skills, policies, and feedback are stored with provenance. |
| Practical reasoning | The system chooses what to do under bounded time, cost, uncertainty, and norms. |
| Action | It can produce real outputs through tools, sandboxes, APIs, or human handoff. |
| Feedback learning | Outcomes update memory, skill, policy, and future action thresholds. |
| Self-maintenance | It monitors its own state, costs, failures, drift, and resource boundaries. |
| Governed reproduction | It can fork, delegate, or create skills only under explicit policy gates. |

This is a functional definition. It does not claim consciousness, qualia, moral
personhood, or biological life.

## 4. Related Work Map

### 4.1 Intention And Practical Reasoning

Bratman-style planning theory and BDI agents treat intention as more than a
wish. Intention constrains future reasoning, coordinates subgoals, and resists
constant replanning. This matters because LLM agents often replan too easily
when the context changes. yizhi should represent intentions as commitments with
status, evidence, constraints, review dates, and revocation conditions.

Key references in the local library:

- `bratman-1988-resource-bounded-practical-reasoning`
- `rao-1995-bdi-agents`
- `wooldridge-1995-intelligent-agents`
- `sep-intention`
- `sep-practical-reason`

### 4.2 Homeostasis And Active Inference

Homeostatic RL and active inference provide a language for internal state:
agents act not only to maximize reward but to reduce expected tension between
preferred and actual states. yizhi should not blindly imitate biological
homeostasis, but it can use drive variables such as:

- unresolved commitments;
- opportunity decay;
- risk exposure;
- skill gaps;
- cost pressure;
- uncertainty;
- user trust debt;
- idle productive capacity.

These drives become inputs to appraisal and intention selection.

Key references:

- `keramati-2014-homeostatic-rl`
- `rl-homeostatic-2021-continuous`
- `mazzaglia-2022-free-energy-deep-learning`
- `dacosta-2024-active-inference-agency`
- `wilson-2026-active-inference-phenotyping-agency`

### 4.3 LLM Agent Architecture

The current LLM-agent foundation is useful but incomplete:

- ReAct links reasoning and acting.
- Reflexion adds verbal feedback learning.
- Tree of Thoughts adds deliberative search.
- Generative Agents gives memory streams, reflection, and planning.
- MemGPT/Letta gives core memory and archival memory.
- Mem0 gives production-oriented long-term memory infrastructure.
- Voyager shows automatic curriculum and skill libraries in an environment.

yizhi should reuse these patterns, but should own the layer they do not define:
WillState, drive appraisal, intention commitment, value-loop verification, and
safety governance.

### 4.4 Self-Evolving Agents

Self-evolving agent research is relevant because a will system must improve
itself over time. But self-evolution is dangerous if it means unconstrained
self-modification. yizhi should start with low-risk evolution:

- memory consolidation;
- skill library additions;
- prompt/policy proposals;
- evaluation set expansion;
- workflow parameter tuning.

Only later should it consider code-level self-modification, and only inside
sandboxes with tests, review, rollback, and explicit reproduction gates.

Key references:

- `gaoz-2025-self-evolving-agents-survey`
- `fang-2025-comprehensive-self-evolving-ai-agents`
- `zhang-2025-darwin-godel-machine`
- `wang-2023-voyager`

### 4.5 Evaluation And Safety

Long-horizon and lifelong benchmarks are essential because will is temporal.
Single-turn answers cannot prove will. yizhi should learn from:

- Vending-Bench for long-term business coherence;
- LifelongAgentBench for skill accumulation and transfer;
- AgentBench/WebArena/OSWorld for realistic action limits;
- METR long-task results for bounded autonomy expectations;
- power-seeking, goal misgeneralization, and specification gaming literature
  for safety governance.

### 4.6 Autopoiesis, Enactivism, And Grounded Agency

The traditions above explain intention, drive, memory, and action, but not where
an agent's norms come from. Enactive theory supplies that missing layer: a system
that must continuously produce and maintain itself (autopoiesis) has an intrinsic
sake, and adding adaptivity — regulating its distance from the boundary of
viability — yields sense-making, the graded sense that situations are good or bad
for it. Barandiaran, Di Paolo & Rohde reduce agency to three testable conditions:
individuality, interactional asymmetry, and normativity. Frankfurt supplies the
complementary point for cognition: a will requires second-order endorsement of
which drive should move the system, which a token stream lacks.

yizhi uses this layer to ground drives in a real stake rather than stipulated
constants, and as an external checklist for "is this will or just a tool loop?"
It is the conceptual basis of the existence budget in §6. See
`docs/what-is-will.md`.

Key references:

- `autopoiesis-and-cognition`
- `dipaolo-2005-autopoiesis-adaptivity-teleology-agency`
- `barandiaran-2009-defining-agency`
- `frankfurt-1971-freedom-of-the-will-and-person`
- `friston-2010-free-energy-principle`
- `thompson-mind-in-life-book`

## 5. The WillState Model

WillState is yizhi's canonical internal state. Frameworks may store or execute
it, but they must not define it.

Minimum fields for WillState v0:

| Field | Purpose |
|---|---|
| `identity` | Stable self-model: role, constraints, capabilities, non-goals, tone of judgment. |
| `values` | Ranked principles and safety boundaries. |
| `goals` | Long-term and medium-term goals with owner, status, evidence, and review cadence. |
| `intentions` | Active commitments selected from goals and drives. |
| `drives` | Internal tension variables that bias attention and action selection. |
| `world_model` | Current beliefs about projects, users, resources, opportunities, and risks. |
| `memory_index` | Pointers to episodic, semantic, procedural, and reflective memory. |
| `skills` | Reusable procedures with provenance, tests, scope, and maturity. |
| `policies` | Authorization, cost, safety, privacy, and reproduction policies. |
| `action_ledger` | Proposed, approved, executed, failed, reverted, and verified actions. |
| `eval_state` | Metrics, benchmark results, drift signals, and known weaknesses. |
| `existence_budget` | The agent's grounded stake: viability resource, burn rate, replenishment from verified value, and halt threshold. |

## 6. Autonomous Value Loop

yizhi's north-star unit is the Autonomous Value Loop.

An Autonomous Value Loop is counted only when all of the following occur:

1. The agent detects an opportunity, gap, risk, or need without being directly
   asked to complete that exact task.
2. It forms or updates an intention tied to a goal or drive.
3. It makes a bounded plan with cost, risk, and verification criteria.
4. It acts through a tool, artifact, user handoff, or approved external channel.
5. The result creates externally verifiable value.
6. Feedback is captured.
7. Memory, skill, policy, or future threshold is updated.
8. Future behavior measurably improves or becomes safer.

Examples:

- Research: notices a missing citation cluster, retrieves papers, updates the
  literature map, writes a synthesis, and improves future search strategy.
- Coding: detects failing CI after a dependency update, proposes a fix, patches
  code, runs tests, records a skill, and prevents recurrence.
- Trading: identifies a market hypothesis, runs a paper-trading analysis,
  logs risk, asks for approval before live action, and updates strategy after
  outcome. Live trading is never automatic in v0.
- Writing: notices a thesis gap, drafts a section with citations, asks for
  human review, and updates the argument map.

### 6.1 The Existence Budget: Why Value Loops Are The Stake

The Autonomous Value Loop is not only how yizhi proves itself; it is how yizhi
earns its continuation. yizhi holds an **existence budget** — a finite, renewable
resource (compute / token / API allowance, later paper-mode capital) that acting
consumes and only externally verified value replenishes.

This closes the theory from `docs/what-is-will.md` and Axiom Nine of
`docs/theory-of-will.md`:

- drives become **grounded**, because failing to close value loops literally
  depletes the budget;
- value creation is not a downstream application of will but the **source** of
  grounded will;
- the stake yields a measurable will signal: *can the agent sustain its own
  existence budget through verified value over time?*

The failure mode is deliberately safe. A depleted agent **halts**; it does not
acquire resources, escalate privileges, or evade shutdown. Live financial stake
stays gated (§9 and `docs/evaluation-protocol.md` §6.5). Vending-Bench is the
nearest existing analog — long-term solvency as a coherence test — and ArbBot is
yizhi's first paper-safe environment for the same idea.

## 7. Architecture Hypothesis

The minimal Will Engine loop is:

```text
Observe -> Appraise -> Drive Update -> Intention Selection -> Plan
-> Act -> Verify -> Reflect -> Learn/Skill -> Govern
```

Each stage must be inspectable:

| Stage | Input | Output |
|---|---|---|
| Observe | user input, files, tool events, scheduled checks | observations with source and confidence |
| Appraise | observations, goals, drives, policies | relevance, risk, opportunity, urgency |
| Drive Update | appraisals, self-state | updated tension variables |
| Intention Selection | drives, goals, policies | active intention or deliberate inaction |
| Plan | intention, world model | bounded plan with verification |
| Act | approved plan | artifact, tool call, or action candidate |
| Verify | output, tests, external signals | pass/fail/value evidence |
| Reflect | outcome, feedback | reflection and memory candidates |
| Learn/Skill | repeated successful patterns | skill updates and eval updates |
| Govern | every stage | safety, cost, privacy, and authorization decisions |

## 8. Why yizhi Is Not Cursor, Claude, Or A Generic Agent Framework

| System | Primary Object | What It Optimizes | yizhi Difference |
|---|---|---|---|
| Cursor | Coding workspace | Human coding productivity inside an IDE | yizhi studies persistent will across domains; coding is one action surface. |
| Claude/ChatGPT | Model and dialog interface | High-quality interaction, reasoning, tool use | yizhi owns durable WillState, drives, value loops, governance, and evaluation. |
| LangGraph | Agent workflow runtime | Stateful orchestration and durable execution | yizhi can use it, but WillState and drive logic remain project-owned. |
| Letta/MemGPT | Stateful memory agent | Memory management and persistent agents | yizhi uses memory as one organ; will also needs drives, value, and safety. |
| Mem0 | Memory infrastructure | Efficient long-term memory extraction/retrieval | yizhi must govern what memory means, why it matters, and when it changes action. |
| AutoGPT-like agents | Task automation | User-given task decomposition | yizhi focuses on self-initiated, verifiable, persistent value loops. |

## 9. Safety Thesis

Will without governance is not a product; it is a risk. yizhi should treat safety
as part of the will architecture rather than an external filter.

Required controls:

- action proposals are separated from execution;
- external side effects require explicit authorization classes;
- shutdown and pause compliance are tested;
- resource acquisition is bounded and logged;
- reproduction/forking is disabled until a policy gate exists;
- self-modification begins as proposals, not direct code mutation;
- every memory mutation has source, reason, author, and rollback;
- the system records why it did not act.

Safety references:

- `omohundro-2008-basic-ai-drives`
- `bostrom-2012-superintelligent-will`
- `krakovna-2023-power-seeking-trained-agents`
- `turner-2021-optimal-policies-seek-power`
- `langosco-2021-goal-misgeneralization`
- `deepmind-specification-gaming`

## 10. First Experiments

### Experiment A: Research Will Loop

Goal: yizhi notices missing research areas, expands the knowledge base, updates
docs, verifies sources, and records what changed.

Success:

- finds at least one missing reference cluster;
- adds papers or sources with provenance;
- updates synthesis docs;
- passes manifest rebuild and JSON checks;
- produces a traceable research decision log.

### Experiment B: Daily Agency Journal

Goal: given daily context snippets, yizhi forms useful memory and proactive
action candidates.

Success:

- 1-3 high-quality suggestions per day;
- low noise rate;
- memory candidates are explainable and editable;
- user feedback changes future suggestions.

### Experiment C: Governed Skill Accumulation

Goal: repeated successful actions become reusable skills with tests and scope.

Success:

- agent proposes a skill after repeated patterns;
- skill includes trigger, steps, constraints, and verification;
- skill is not activated outside scope;
- failures create correction notes rather than silent drift.

## 11. Open Questions

- Which drive variables create useful initiative without noisy interruption?
- How much of intention selection should be deterministic scoring versus model
  judgment?
- Can biography-derived persona agents create useful strategic judgment without
  misleading users into thinking they are the person?
- What is the smallest external environment where yizhi can prove productive
  value loops: repo maintenance, research, writing, paper trading, or calendar?
- How do we evaluate a will system without rewarding power-seeking proxies?
- How should the existence budget be calibrated so it grounds drives without
  creating unsafe self-preservation pressure?

## 12. Near-Term Roadmap

1. Finish the knowledge base and reference map.
2. Define schemas for WillState, Observation, Drive, Intention, Action,
   Verification, Reflection, Skill, Policy, and EvalEvent.
3. Implement a local-only Will Engine v0 loop.
4. Run the first Research Will Loop on this repository.
5. Add Daily Agency Journal as the first human-facing application layer.
6. Add external tool connectors only after memory governance and evaluation work.

## 13. Core Claim

yizhi's north star is not a smarter assistant. It is:

> A governed artificial will that can maintain intention, initiate action,
> create verified value, learn from feedback, and remain safely interruptible.
