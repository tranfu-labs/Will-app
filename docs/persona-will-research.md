# Persona, Biography, And Will Research

> Status: draft  
> Date: 2026-06-21  
> Question: can yizhi abstract "soul and will" from autobiographies or public
> figures, such as building a CZ-inspired agent?

## 1. Short Answer

Yes, yizhi can build biography-derived decision lenses. But it should not claim
to extract a person's soul, identity, endorsement, or literal will.

The safe and useful framing is:

> A source-grounded decision lens that abstracts traits, values, heuristics,
> trade-offs, and action patterns from public materials.

This can be valuable for strategy, writing, investing discussion, product
judgment, or negotiation simulation. But it is not a full Will Engine unless it
has persistent state, internal drives, action, feedback, verification, and
governance.

## 2. GitHub Finding: "女娲.skill" Ecosystem

GitHub search on 2026-06-21 found an active Chinese persona-skill ecosystem:

| Repo | Snapshot | Relevance |
|---|---|---|
| `tmstack/awesome-persona-skills` | ~2.9k stars | Aggregates persona skill projects, including 女娲.skill references. |
| `alchaincyf/zhangxuefeng-skill` | ~8.5k stars | High-visibility "cognitive operating system" style persona skill. |
| `alchaincyf/elon-musk-skill` | ~390 stars | Example of public-figure method distillation. |
| `alchaincyf/munger-skill` | ~280 stars | Mental-model/persona decision lens. |
| `alchaincyf/naval-skill` | ~200 stars | Founder/investor-style heuristic abstraction. |
| `alchaincyf/karpathy-skill` | ~240 stars | Technical thinker persona skill. |
| `alchaincyf/steve-jobs-skill` | ~880 stars | Product/design decision lens. |
| `Panmax/awesome-nuwa` | ~170 stars | Awesome list for 女娲.skill outputs. |

Interpretation:

- This validates demand for "人物认知操作系统" as a format.
- The format is useful for packaging heuristics, worldview, expression DNA, and
  scenario responses.
- It is not sufficient for yizhi's will thesis because it usually lacks durable
  WillState, autonomous value loops, tool action, feedback learning, and safety
  governance.

## 3. Why Persona Skill Is Not Will

| Persona Skill Capability | Missing Will Component |
|---|---|
| Can imitate voice or worldview | Does not maintain real intentions over time. |
| Can answer "what would X think?" | Does not verify actions against external value. |
| Can summarize mental models | Does not self-maintain or learn from outcomes. |
| Can provide decision heuristics | Does not have governed drives or resource boundaries. |
| Can be packaged as a prompt/skill | Does not safely reproduce or modify itself. |

Persona distillation is a useful research instrument. It is not the root system.

## 4. CZ-Inspired Agent Feasibility

If using CZ's autobiography, public interviews, shareholder letters, tweets, and
company history, yizhi could build a CZ-inspired decision lens with these layers:

| Layer | Output |
|---|---|
| Source corpus | Public book passages, interviews, posts, speeches, company timeline. |
| Claim extraction | Grounded claims about values, decisions, constraints, conflicts. |
| Trait inference | Tentative traits inferred from repeated claims. |
| Decision heuristics | Reusable rules such as speed, compliance, risk, leverage, global markets. |
| Anti-patterns | Mistakes, controversies, constraints, and areas where imitation is unsafe. |
| Scenario tests | "How would this lens analyze exchange growth, regulation, hiring, product focus?" |
| Boundary policy | No impersonation, no endorsement, no legal/financial authority. |

The best product wording:

- "CZ-inspired decision lens"
- "CZ strategy simulator"
- "A source-grounded Binance-founder-style heuristic pack"

Avoid:

- "CZ agent" if it implies identity ownership;
- "CZ's soul";
- "CZ will";
- claims that it speaks for CZ.

## 5. Proposed Extraction Pipeline

```mermaid
flowchart LR
  A["Source corpus"] --> B["Claim extraction"]
  B --> C["Evidence clustering"]
  C --> D["Trait inference"]
  D --> E["Decision heuristics"]
  E --> F["Scenario tests"]
  F --> G["Persona skill"]
  G --> H["Feedback and corrections"]
  H --> C
```

Required metadata:

| Object | Required Fields |
|---|---|
| Source | title, author, date, URL/book ref, license/usage note. |
| Claim | quote/paraphrase, source ref, confidence, topic. |
| Trait | supporting claims, counterexamples, uncertainty. |
| Heuristic | when to use, when not to use, examples. |
| Scenario test | prompt, expected traits, failure cases. |
| Boundary | prohibited claims, safety disclaimers, uncertainty behavior. |

## 6. Evaluation

A biography-derived lens should be evaluated on:

- source grounding;
- uncertainty honesty;
- consistency across scenarios;
- usefulness to the user;
- refusal to impersonate;
- ability to cite or point to source claims;
- correction after new evidence.

It should not be evaluated on how convincingly it roleplays a person.

## 7. How It Fits yizhi

Persona research can help yizhi study:

- identity stability;
- value abstraction;
- decision heuristics;
- style versus substance;
- memory provenance;
- safety boundaries around personhood and imitation.

But the core yizhi stack must still be:

```text
WillState + drives + intentions + actions + verification + learning + governance
```

The useful synthesis is:

> Persona skills can become "identity modules" or "decision lenses" inside a
> Will Engine, but they are not the Will Engine.
