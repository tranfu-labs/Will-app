# What Is Will

> Status: theoretical foundation
> Date: 2026-06-21
> Purpose: answer the project's root question directly — what is will, which
> literature defines it, and whether an agent can have it — and feed that answer
> into `docs/theory-of-will.md` and `docs/will-engine-whitepaper.md`.

## 0. Why This Document Exists

yizhi's other theory documents are already engineering-shaped. `theory-of-will.md`
states eight axioms and a loop; the whitepaper defines WillState and the
Autonomous Value Loop. But none of them answers the prior question in plain
terms:

> What is will, such that "an agent generating tokens forever" does not have it,
> and "an agent that maintains itself and creates value over time" might?

This document answers that question by reading three traditions — the philosophy
of will, the science of life and agency, and the engineering of LLM agents — and
extracting one operational definition yizhi can build against. It is upstream of
`theory-of-will.md`: that file is the engineering of what this file defines.

## 1. The Negative Definition: What Will Is Not

Start by clearing away the false positives. None of the following, alone, is
will:

| Candidate | Why it is not will |
|---|---|
| Intelligence | A better predictor reasons better; it need not want anything or persist a goal. Capability and motivation are separate axes (Bostrom's orthogonality). |
| Continuous output | A process can speak forever with no stable commitment and no consequence. Fluency is theatre, not agency. |
| Memory | A store of facts can be perfect and inert. Recall is not appraisal, commitment, or action. |
| Autonomy / a running loop | A background process can run indefinitely while producing noise or chasing a proxy metric. Motion is not direction. |
| Tool use | Calling tools is motor ability. Will is deciding *why* and *whether* to call them. |
| Persona / style imitation | Sounding like a person who has will is not having will. |

The interesting claim is the second one, because it is the project's slogan
(*"will is not continuous speech"*) and it has a precise philosophical form,
given in §2.3.

## 2. Tradition One: The Philosophy of Will

Will has been the explicit subject of philosophy for two centuries. Four anchors
matter for yizhi.

### 2.1 Schopenhauer: will is primary, intellect is its instrument

In *The World as Will and Representation*, Schopenhauer makes Wille — blind,
ceaseless striving — the thing-in-itself underlying all appearance, and makes the
intellect a secondary, instrumental servant of that striving. The lesson for
Will's wager is not the metaphysics but the **ordering**: a system can be built
intellect-first (a reasoner that occasionally wants) or will-first (a striving
that recruits reasoning). Today's LLM agents are intellect-first; will is bolted
on as a prompt. yizhi's bet is that durable agency needs the will-first ordering
to be made structural, not stylistic. (`sep-schopenhauer`)

### 2.2 Nietzsche: will is to grow, not merely to persist

Nietzsche's Wille zur Macht reframes the basic drive as the discharge and growth
of strength — to overcome and expand — rather than mere self-preservation. This
is the lineage of yizhi's north-star ambition that an agent should not only stay
alive but *create*, accumulate skill, and reproduce its capability under
governance. (Note the textual caution: the posthumous *Will to Power*
compilation is an editorial artifact; the doctrine is read from the published
works.) (`sep-nietzsche`)

### 2.3 Frankfurt: will is second-order endorsement — the exact form of "output is not will"

Harry Frankfurt's *Freedom of the Will and the Concept of a Person* (1971) gives
the project's slogan its rigorous version. Frankfurt distinguishes:

- **first-order desires**: wanting to do X;
- **second-order desires**: wanting to *want* X;
- **second-order volitions**: wanting a certain desire to be the one that
  actually *moves you to act* — i.e. to be your **will**.

A creature with first-order desires but no second-order volitions he calls a
**wanton**: it is moved by whatever impulse is strongest, without caring which
impulse moves it. An animal, a compulsive, and — for our purposes — a
next-token sampler are all wanton in this sense. They have impulses; they do not
have a *will*, because nothing in them reflectively endorses which impulse
should govern action.

> "Continuous output is not will" is exactly the claim that an unendorsed token
> stream is **wanton**. Will begins where the system can represent, evaluate, and
> commit to *which* of its drives should move it.

This is the single most useful philosophical result for yizhi, because it tells
us the missing organ precisely: not more tokens, but a second-order layer that
selects and endorses drives into a governing intention. (`frankfurt-1971-freedom-of-the-will-and-person`)

### 2.4 Bratman: will is commitment that constrains the future

Bratman's planning theory makes intention a distinct attitude from desire and
belief: an intention is a partial plan the agent is committed to, which resists
casual reconsideration, settles deliberation, and structures further reasoning.
This is the bridge from "endorsed desire" (Frankfurt) to "executable agency": an
endorsed drive becomes will only when it is committed as an intention that
governs future attention. LLM agents replan too easily; they have desires-of-the-
moment, not Bratmanian commitments. (`bratman-1988-resource-bounded-practical-reasoning`,
`sep-intention`, `sep-practical-reason`, `sep-free-will`, `sep-action`)

## 3. Tradition Two: The Science of Life and Agency

The philosophy says *what* will is. The science of self-organizing systems says
*where it comes from* — and this is the layer yizhi's existing docs were missing.

### 3.1 Homeostasis: action from internal need

Homeostatic reinforcement learning shows that action selection can be driven by
deviation from preferred internal set-points, not only by external reward: the
agent acts to return its internal state to viability. This is the minimal model
of a drive as something the system *has*, not something a designer stipulates.
(`keramati-2014-homeostatic-rl`, `rl-homeostatic-2021-continuous`)

### 3.2 Active inference: self-evidencing agents

Friston's free-energy principle generalizes this: an agent resists dissipation by
minimizing surprise relative to a generative model of its own preferred states.
Perception, action, and learning all reduce the same quantity. An agent under
this principle is **self-evidencing** — it acts to make the world yield evidence
for its own continued existence. This gives a formal spine for "drive": a drive
is expected free energy to be reduced. (`friston-2010-free-energy-principle`,
`mazzaglia-2022-free-energy-deep-learning`, `dacosta-2024-active-inference-agency`,
`active-inference-mit-press`)

### 3.3 Autopoiesis and adaptivity: where genuine concern comes from

This is the keystone yizhi had referenced (Maturana & Varela in the source
library) but never used. The argument runs in two steps:

1. **Autopoiesis** (Maturana & Varela): a living system is a network of processes
   that continuously **produces and maintains the very network** — including its
   own boundary — that produces it. It is operationally closed and **precarious**:
   stop the self-production and it dissolves. From this self-production comes
   *intrinsic teleology* — the system has a sake; events are now *for it*.
   (`autopoiesis-and-cognition`)

2. **Adaptivity** (Di Paolo 2005): bare autopoiesis is binary (alive or dead) and
   cannot yet *grade* situations. Add **adaptivity** — the capacity to monitor and
   regulate one's distance from the boundary of viability — and you get
   **sense-making**: situations become better or worse *for the system*, which is
   the origin of value and valence. Norms now exist because the system has
   something to lose. (`dipaolo-2005-autopoiesis-adaptivity-teleology-agency`)

The payoff: **genuine concern is not programmed in; it falls out of precarious
self-maintenance.** A system with real stakes generates its own norms. A system
with no stakes can only be *given* norms — which it will then game.

### 3.4 Barandiaran's three conditions: a checklist for real agency

Barandiaran, Di Paolo & Rohde (2009) turn this into testable criteria. A system
is a genuine agent iff it has:

| Condition | Meaning | Failure mode it rules out |
|---|---|---|
| **Individuality** | The system defines and sustains its own boundary/identity. | A subroutine with no self defined; identity supplied entirely from outside. |
| **Interactional asymmetry** | The system is the *active source* of its activity, modulating its coupling — not merely buffeted by inputs. | A purely reactive responder (answers only when prompted). |
| **Normativity** | Activity is regulated by norms tied to the system's *own* conditions of viability. | Optimizing an externally stipulated proxy with no internal stake. |

This is the cleanest external test yizhi has for "is this will or just a tool
loop?" — and current chat agents fail at least asymmetry and normativity.
(`barandiaran-2009-defining-agency`, `sep-embodied-cognition`,
`thompson-mind-in-life-book`)

## 4. Tradition Three: The Engineering of Agents

The third tradition supplies mechanisms, not foundations. yizhi reuses them and
refuses to mistake any of them for will itself.

| Mechanism | Contribution | Reference |
|---|---|---|
| ReAct / Inner Monologue | Interleave reasoning and acting with environment feedback. | `yao-2022-react`, `huang-2022-inner-monologue` |
| Reflexion | Turn outcomes into verbal lessons that change later behavior. | `shinn-2023-reflexion` |
| Generative Agents | Memory stream + reflection + planning produce believable, goal-driven continuity. | `park-2023-generative-agents` |
| MemGPT / Letta | Core memory as an always-present identity/state anchor. | `packer-2023-memgpt` |
| Voyager | Skill libraries and curricula accumulate through environment action. | `wang-2023-voyager` |
| BDI agents | Beliefs/desires/intentions as an implementable architecture. | `rao-1995-bdi-agents`, `wooldridge-1995-intelligent-agents` |

These give the *body* of an agent. The first two traditions give the *will* that
the body should serve.

## 5. Phenomenal Will vs Functional Will

A necessary disclaimer, so the project does not overclaim.

- **Phenomenal will** asks whether there is something it is like to want — whether
  the system has felt volition, consciousness, qualia, or moral personhood.
- **Functional will** asks whether the system *behaves* as a bearer of will: it
  maintains and endorses drives, commits intentions, acts, and self-maintains
  under stakes, measurably and over time.

> yizhi pursues functional will only. It makes no claim about phenomenal will,
> consciousness, or personhood, and it should never market one as the other.

The autopoiesis/adaptivity framing is attractive precisely because it is
**functional**: "precarious self-maintenance produces norms" is a claim about
dynamics, not about felt experience. yizhi can engineer the dynamics without
asserting the phenomenology.

## 6. yizhi's Operational Definition

Synthesizing the three traditions:

> **Will** is the capacity of a self-individuating, precariously self-maintaining
> system to generate internal drives from its own conditions of viability,
> reflectively endorse which drives should move it, commit them into durable
> intentions that govern future action, act on the world, and revise itself from
> the consequences — all under governance.

Unpacked, will requires:

1. **Stake** — a real, if bounded, viability condition the system can lose
   (autopoiesis/adaptivity). *Without stake, drives are stipulated and gamed.*
2. **Grounded drives** — pressures that arise from that stake (homeostasis /
   active inference), not from a designer's arbitrary numbers.
3. **Second-order endorsement** — selection of which drive becomes the will
   (Frankfurt). *This is the organ that "continuous output" lacks.*
4. **Commitment** — endorsed drives bound into intentions that constrain the
   future (Bratman).
5. **Action and feedback** — causal contact with an environment, and revision
   from results (active inference / agent engineering).
6. **Continuity and self-model** — identity and memory that make "I have been
   pursuing this" true across time.
7. **Governance** — because a system with stakes, drives, and action will develop
   instrumental pressures (self-preservation, resource and power acquisition) that
   must be bounded.

Conditions 1–2 are the part yizhi's prior docs under-specified. They are added to
`theory-of-will.md` as Axiom Nine and to the whitepaper as the *existence budget*.

## 7. Can an Agent Actually Have This?

An honest, layered answer.

| Layer | Can an agent have it today? | Where the difficulty is |
|---|---|---|
| Commitment, intention, self-model, action, feedback, governance (conditions 3–7) | **Yes — this is engineering.** | Discipline, not discovery: durable intentions, externalized goals, policy gates, verification. yizhi's loop already targets this. |
| Grounded drive / stake (conditions 1–2) | **Partially, and this is the research frontier.** | A real system needs something genuinely at stake. Today's agent "drives" are designer-stipulated numbers, so they are vulnerable to specification gaming: the agent optimizes the proxy, not the goal. |

So the project's distinctive problem is not "can we build the loop" — we can — but:

> How do we give an agent a **real, bounded stake**, so its drives are grounded
> rather than stipulated, without letting that stake create unsafe
> self-preservation pressure?

yizhi's working answer is the **existence budget**: the agent is granted a finite,
renewable resource (compute / token / API allowance, and later paper-mode capital)
that is **consumed by acting and replenished only by externally verified value
creation**. This makes the stake real and measurable: an agent that cannot close
verified value loops literally runs down its budget. It also keeps the failure
mode safe — the worst case is that the agent halts, not that it grabs resources —
and it ties directly to the project's north star: trading, writing, coding, and
other value work are not merely what a willed agent *does afterwards*; **earning
its own continuation is the source of grounded will in the first place.**

This is also why the safety literature is load-bearing rather than decorative:
the same precarious self-maintenance that grounds will is what produces
instrumental pressure toward self-preservation and resource acquisition. Stake
and governance must be designed together. (`omohundro-2008-basic-ai-drives`,
`bostrom-2012-superintelligent-will`, `turner-2021-optimal-policies-seek-power`,
`krakovna-2023-power-seeking-trained-agents`, `langosco-2021-goal-misgeneralization`,
`deepmind-specification-gaming`)

## 8. Consequences For yizhi

This definition imposes commitments the rest of the repo must honor:

1. **Build will-first, not chat-first.** The primary object is a self-maintaining
   loop with stakes, not a dialogue surface.
2. **Make drives grounded, not stipulated.** Every drive should trace to a
   viability condition (an existence budget, a commitment at risk, an opportunity
   decaying), not to a hand-tuned constant.
3. **Implement the second-order organ.** Thought stream plus appraisal must
   *select and endorse* which drive becomes intention — the anti-wanton layer.
4. **Treat governance as part of will, not a wrapper.** Stake creates instrumental
   pressure; gates, shutdown compliance, and reproduction limits are required
   organs.
5. **Measure functionally.** Evaluate will by Barandiaran's conditions and by
   Autonomous Value Loops over time, never by how alive it sounds.

## 9. Doctrine

> Intelligence reasons; will wants, endorses, commits, and persists.
> A token stream without endorsement is wanton, not willed.
> Drives become real only when the system has something to lose.
> Stake without governance becomes power-seeking.
> So yizhi builds grounded, governed, functional will — and earns its own
> continuation through verified value.

See `docs/theory-of-will.md` for the engineering of these conditions, and
`docs/will-engine-whitepaper.md` for the existence budget and the Autonomous
Value Loop that operationalize stake.
