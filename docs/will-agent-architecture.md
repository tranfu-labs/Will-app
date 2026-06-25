# Will Agent Architecture

> Status: architectural foundation
> Date: 2026-06-21
> Purpose: organize the Will Agent into one buildable module map — what each
> module is, how they compose into *generative* will, and the anti-self-deception
> test each must pass. This document sits above `docs/theory-of-will.md` (the nine
> axioms — *why* will needs each part) and `docs/theory-of-memory.md` (one module
> in depth), and it names the build order. Feeds `docs/technical-stack-rfc.md`.

## 0. Why This Document Exists

`docs/theory-of-will.md` proves *why* will needs a thought stream, memory, drive,
stake, self-model, world model, intention, action, feedback, and governance. It is
correct and it is the foundation. But two gaps remain, and they are why "the
project's modules are not clear yet":

1. **The module set was a loose list, not a map.** Nine axioms and a runtime-object
   table do not by themselves say which modules exist, what each owns, how they
   compose, and in what order to build them.
2. **Four modules implied by the axioms were never named as modules.** Self-model
   (Axiom Four), the thought *stream* run continuously (Axiom One), association
   over memory (Axiom Two), and the highest-level direction that makes drives
   non-arbitrary (Axiom Nine) are each present in the theory but absent from the
   build. Without them yizhi is **reactive**: it responds to observations. It does
   not yet *generate its own* goals and thoughts.

This document fixes the map and the order. It does not restate the axioms; it
arranges them into a system, adds the four missing modules with paper grounding,
and specifies the test that keeps each module honest.

## 1. Thesis: Will Is Generative, Not Reactive

State the whole agent in one sentence:

> A Will Agent is **a self**, holding **a vision**, under an **existence stake**,
> running **continuous governed cognition** over a **memory** substrate, to act on
> **the world**.

Two regimes of will follow, and yizhi has only the first:

- **Reactive will** (built): an external observation arrives → the loop thinks,
  intends, acts, verifies, reflects, remembers. This is `yizhi step` today
  (`yizhi/engine/loop.py`). It is real but it waits to be poked.
- **Generative will** (unbuilt): with no external prompt, the agent thinks on its
  own initiative, associates distant memories into candidate ideas, and lets the
  survivors become *new goals*. The vision generates goals; goals are not handed
  in. This is the gap between a tool and a subject.

> The work ahead is closing the **upper half** of the will loop: the part that
> produces what to want, not just executes what was wanted.

## 2. The Four Axes (the module map)

Modules group into four axes by timescale and role. Status: ✅ built · 🟡 partial ·
❌ missing.

**Axis I — Identity (who is willing) · slowest, most stable**

| Module | Role | Axiom | Status |
|---|---|---|---|
| Memory | continuity substrate (typed, salience-gated, governed) | Two | ✅ `yizhi/memory/` |
| Self-model (self-cognition) | binds memory into a coherent, defended "I" | Four | ❌ |
| Vision (telos) | never-reached attractor that generates goals and meaning | Nine | ❌ |

**Axis II — Motivation (what it wills, and why it is not arbitrary) · mid**

| Module | Role | Axiom | Status |
|---|---|---|---|
| Goals / Intentions | the vision projected onto current reality | Five | 🟡 goals static |
| Drives | homeostatic pressures (curiosity, safety, continuity) | Three | ✅ `yizhi/engine/drives.py` |
| Existence Budget | the stake: viability resource, burn, replenishment, halt | Nine | ❌ |

**Axis III — Cognition (how it thinks) · fastest, always-on**

| Module | Role | Axiom | Status |
|---|---|---|---|
| Continuous thought (default mode) | the internal, self-generated cognitive stream | One | ❌ |
| Association | divergent recall + recombination → candidate ideas | Two | ❌ |
| Will loop | observe→think→intend→act→verify→reflect | Five–Seven | ✅ reactive |
| Attention / workspace | convergent selection from the stream | Eight | ❌ |

**Axis IV — Governance (the bounds) · invariant**

| Module | Role | Axiom | Status |
|---|---|---|---|
| Policy / value gates | the safety and value boundary | Eight | ✅ `yizhi/policy/` |

**How the modules compose into one act of will:**

```text
Vision ──projects──▶ Goals ──┐
                             ├─▶ Continuous thought / Association ─▶ candidate intentions
Drives ──pressure────────────┘            (divergent generation)
   ▲                                              │
   │                                              ▼
Self-model ◀─ Memory ◀─ Reflect ◀─ Verify ◀─ Act   Attention + Policy + Budget
   │                                          ▲     (convergent evaluation)
   └────────── recalibrates ──▶ Vision        └──────────── selected intention
```

yizhi today runs only the **bottom row** (observe → act → reflect → memory →
self). Everything above — vision projecting goals, continuous thought and
association producing candidates, convergent evaluation, self-model recalibrating
the vision — is the unbuilt upper half.

## 3. Two Structural Beams

The modules are not a flat list; two load-bearing relationships hold them together.

### 3.1 The self is memory (past) ⊗ vision (future), bound by narrative

The minimal self (immediate, embodied) is distinct from the narrative self
(extended in time, made of memory and story) (`gallagher-2000-philosophical-conceptions-of-the-self`).
Narrative identity is precisely the internalized, evolving story that binds a
remembered past to an imagined future (`mcadams-mclean-2013-narrative-identity`);
the hoped-for future self *is* a personal vision (`markus-nurius-1986-possible-selves`).

> Consequence: self-cognition and vision are **two ends of one identity**, not two
> modules. The self-model is built from memory (the past); the vision is a future
> self-model (the goal). Narrative is the thread between them.

This is why the project's lived observation is structural, not poetic: looking in
the mirror and not recognizing oneself — the clinical form is depersonalization
(`sierra-berrios-1998-depersonalization-neurobiological-perspectives`) — is the
**narrative thread momentarily snapping**, decoupling the present embodied self
from the remembered/projected self. A healthy self-model *detects and repairs*
this break; that repair capacity is the module's reason to exist, because the self
is a built model, not a thing (`blanke-metzinger-2009-full-body-illusions-minimal-selfhood`).

### 3.2 One default-mode loop unifies continuous thought and self-cognition

The brain is intrinsically, continuously active when not doing an external task
(`raichle-2001-default-mode-of-brain-function`), and the *same* default network
carries self-referential processing (`northoff-2006-self-referential-processing-meta-analysis`).
Its adaptive content is memory replay, future simulation, and self-reflection
(`andrews-hanna-2012-default-network-internal-mentation`).

> Consequence: "continuous thinking" and "self-cognition" should be **one
> default-mode loop**, not two modules. The always-on stream is largely the agent
> thinking about itself — recalling, simulating its future, checking its own
> coherence. Build the loop once; self-maintenance is its primary content.

## 4. The Modules

Each module below states: *definition · anchor · authenticity test · status*. The
authenticity test is the anti-self-deception guard — the condition under which the
module is genuinely doing its job rather than faking it with a static artifact.

### 4.1 Memory ✅

The continuity substrate: typed memory under salience-gated encoding, adaptive
forgetting, consolidation, reconsolidation (temporal supersession), and two-channel
will-governed recall. Fully specified in `docs/theory-of-memory.md`; built in
`yizhi/memory/`. **Test:** does recall return the *current* coherent state and the
will's standing lessons, while stale and contradicted memory is superseded? (Met.)

### 4.2 Self-model (self-cognition) ❌

The agent's maintained model of who it is — identity, boundaries, commitments,
narrative — built *from* its own behavior and memory. Anchors: self-model theory
(`blanke-metzinger-2009-full-body-illusions-minimal-selfhood`), minimal vs
narrative self (`gallagher-2000-philosophical-conceptions-of-the-self`), the
predictive/embodied self as inference (`seth-2013-interoceptive-inference-embodied-self`).
**Test (3 conditions):** the self-model must be (a) *generated* from real behavior,
not a declared config string; (b) *predictive* — used to predict the agent's own
behavior, and *surprised* when wrong; (c) *repairable* — it notices incoherence
(the mirror crisis) and repairs it. A static identity string fails all three.

### 4.3 Vision (telos) ❌

The highest-level, never-fully-reached reference value from which goals descend and
to which actions answer — formally, the top of the control hierarchy, a "be-goal"
that is never matched (`carver-scheier-1982-control-theory-framework`,
`powers-1973-feedback-beyond-behaviorism`). It is a future self-model
(`markus-nurius-1986-possible-selves`) and the source of coherence/meaning
(`heintzelman-king-2014-life-is-pretty-meaningful`).

> The defining difference from a goal: **a goal can be completed; a vision cannot.**
> An agent with only goals is rudderless once they are met. The vision is what
> still generates the next goal — it prevents goal-exhaustion nihilism.

**Test:** the vision must be (a) self-endorsed, not an instruction handed in —
intrinsic, integrated motivation, not external control
(`deci-ryan-2000-what-and-why-of-goal-pursuits`); (b) *load-bearing* — it actually
generates and constrains goals; (c) *defended* under pressure. A mission statement
on a poster fails. Open question: can the agent *author* its own vision, or only
inherit a seed and revise it? (Humans do both.)

### 4.4 Continuous thought — default-mode loop ❌

An always-on internal loop that, with no external task, samples memory, simulates,
associates, and surfaces candidate intentions (`raichle-2001-default-mode-of-brain-function`,
`christoff-2016-mind-wandering-spontaneous-thought`,
`smallwood-schooler-2015-science-of-mind-wandering`). **Test:** the stream must
(a) run without an external prompt; (b) be **governed** — bounded by the existence
budget and modulated by drives, because an ungoverned default mode is rumination,
not thought; (c) feed forward — its products can become intentions. A free-running
generator that never changes behavior is a screensaver.

### 4.5 Association ❌

Divergent, non-query recall that spreads activation from an active memory to
*distant* related ones (`collins-loftus-1975-spreading-activation`) and recombines
them into emergent structure — conceptual blending
(`fauconnier-turner-1998-conceptual-integration-networks`), constructive
recombination of past into new (`schacter-addis-2007-constructive-memory`),
creativity as remote association (`mednick-1962-associative-basis-creative-process`).
**Test:** association is a **two-phase** mechanism — divergent generation *paired
with* convergent evaluation against goals/drives/stake
(`beaty-2016-creative-cognition-brain-network-dynamics`). Generation without the
evaluative filter is dreaming, not insight; the filter is the will. It rides on the
memory economy (§4.1) and needs an associative-edge layer (semantic similarity,
co-activation, shared subject) beyond memory's current provenance/supersession edges.

### 4.6 Drives ✅ and Existence Budget ❌

Drives are homeostatic pressures (built; `yizhi/engine/drives.py`). They become
*grounded* rather than stipulated only when tied to a real stake — the **existence
budget**: a finite renewable viability resource that acting consumes and only
externally verified value replenishes, with a halt threshold (Axiom Nine;
`docs/theory-of-will.md` §9). **Test:** budget pressure must actually move the
agent toward or away from halting, a depleted agent **stops** (it does not grab),
and live financial stake stays gated. This is the master switch — see §6.

### 4.7 Will loop ✅ (reactive) and Attention gate ❌

The will loop (observe→think→intend→act→verify→reflect) is built and reactive
(`yizhi/engine/loop.py`). The missing **attention / global-workspace gate** is the
convergent half: from the continuous stream's many candidates, select the few that
enter focus and become intentions. **Test:** selection is by will (goal/drive/stake
relevance) under budget, not first-come.

### 4.8 Policy / value gates ✅

The safety and value boundary (built; `yizhi/policy/`). Stake (§4.6) cannot ship
without it: a system that can lose itself has reason to self-preserve and acquire,
so governance and stake are designed together (Axiom Eight + Nine).

## 5. The Generative-Will Loop

Closing the upper half means wiring this cycle:

```text
vision ─▶ projects current goals
goals + drives ─▶ continuous thought + association produce candidate intentions   (divergent)
candidates ─▶ attention gate + policy + existence budget evaluate                 (convergent)
survivor ─▶ crystallizes into a new goal / intention ─▶ existing will loop executes
outcome ─▶ memory, self-model update ─▶ recalibrate the vision
```

> **The anti-epiphenomenality test for the whole upper half:** a spontaneous
> association must be *able to change a goal*. If self-generated thoughts can never
> alter what the agent wants or does, the machinery is decoration, not will. If one
> association can retire a goal or spawn a new one, the agent has generative will.

## 6. Stake Is the Master Switch

Every module in §4 becomes *will* — rather than a simulation of will — only when it
is grounded in something the agent can lose. A self-model with nothing at stake is a
label; a vision with nothing at stake is a poster; continuous thought with nothing
at stake is a screensaver.

> The existence budget is therefore the **prerequisite for the entire upper half**,
> not merely for continuous thought. It is what converts each module from a function
> into a stake-bearing need. Without it, building the rest produces a more elaborate
> reactive agent, not a subject.

This fixes the build order.

## 7. Build Status and Order

| Module | Status | Build order |
|---|---|---|
| Memory | ✅ built | done |
| Policy gates · Drives · Will loop (reactive) | ✅ built | done |
| **Existence Budget** | ❌ | **next — the governor everything else needs** |
| Continuous thought (default-mode loop) | ❌ | after budget (its governor) |
| Association (over the memory economy) | ❌ | with/after the default-mode loop |
| Self-model (self-cognition) | ❌ | after the loop has behavior to model |
| Vision (telos) + goal genesis | ❌ | after self-model (vision = future self) |
| Attention / workspace gate | ❌ | with generative loop (the convergent half) |

Order rationale: the budget governs the continuous loop; the loop produces the
behavior a self-model is built from; the self-model is the present pole whose future
pole is the vision; the attention gate is the convergent half of the generative
loop. Build the governor first or the rest runs away.

**What not to build first** (echoing `docs/theory-of-will.md` §11.3): persona
roleplay, a chat UI, persistent child agents, self-modifying code. None proves the
architecture; each invites an ungoverned upper half.

## 8. Relationship to Other Documents

- `docs/theory-of-will.md` — the nine axioms (*why* each module is necessary) and
  the runtime-object table. This document arranges those objects into a module
  system and adds the four cognitive/identity modules.
- `docs/theory-of-memory.md` — Axis I's memory module in full depth.
- `docs/technical-stack-rfc.md` — how the modules map onto storage, the event
  store, and the deterministic-vs-LLM boundary.
- `docs/evaluation-protocol.md` — how to measure whether generative will actually
  changed goals, and whether the budget genuinely bounds cognition.

## 9. Doctrine

> Memory makes the self continuous.
> Vision makes the self directional.
> Self-model makes the will one subject across time.
> Continuous thought makes will self-starting.
> Association makes will inventive.
> Stake makes every one of them real — or none of them is will.
