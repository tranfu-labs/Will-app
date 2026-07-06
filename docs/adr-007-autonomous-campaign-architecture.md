# ADR-007 — Autonomous Campaign Architecture

Status: Accepted(2026-07-06).

## Decision

Will is an **Autonomous Campaign Harness** with seven core modules:

```text
campaigns -> controller -> autonomy -> workers -> lenses -> artifacts -> ledger
```

The modules are not a feature list. They are ownership boundaries:

| Module | Owns | Must not own |
|---|---|---|
| `campaigns/` | Campaign templates, stages, artifact contracts, acceptance gates | Execution, final routing, ledger writes |
| `controller/` | Tick phases, routing, replan, revisit, checkpoint, finalization | Tool logic, quality standards, artifact schemas |
| `autonomy/` | Scope, usage, interruption policy, StageDecision, exception boundaries | Worker execution, artifact validation, event storage |
| `workers/` | Worker adapters and candidate outputs | Campaign cursor, acceptance, policy, canonical truth |
| `lenses/` | SoulLens reports and quality critique | Mutating state, blocking directly, advancing stages |
| `artifacts/` | Artifact/evidence/data/backtest/delivery references | Search, fetch, backtest, report writing |
| `ledger/` | Append-only events and projections | Reasoning, policy, validation, routing |

## Non-Decision

`research/` is rejected as a core module. Research is a campaign template or
worker task kind. BTC is the first MVP campaign, not Will's architectural
identity.

## Core Invariant

```text
Campaign defines required outcome.
Worker produces candidate.
Artifact describes candidate.
Soul critiques candidate.
Autonomy decides whether continuing is inside the boundary.
Controller routes the next effect.
Ledger records facts.

No module may own produce + judge + commit at the same time.
```

## Human Boundary

Human attention is not part of the normal loop. Humans can inspect, steer,
pause, or approve exceptions, but completion must not depend on turn-by-turn
human attention.

Will asks for a human only at these boundaries:

- permission boundary;
- direction conflict;
- budget/scope exhaustion;
- evidence boundary where continuing would mislead;
- irreversible action.

## Worker / Soul / OpenClaw Boundary

```text
Will = campaign control, acceptance, adoption, ledger, final delivery.
Workers = execution body.
Soul = read-only quality/risk/methodology lens.
OpenClaw = future interaction shell.
```

No external harness owns canonical campaign state, policy, budget, memory, or
ledger.

## BTC MVP Mapping

| BTC MVP concern | Architecture location |
|---|---|
| S1-S5 campaign | `campaigns/btc.py` |
| Data acquisition | worker task kind + artifact DataRef |
| Backtest | worker/backtest executor + BacktestRef |
| Evidence | SourceRef / EvidenceRef |
| Final research pack | DeliveryPack |
| Quality critique | SoulLensReport |
| Accept/revise/revisit | StageDecision + controller route |
| Audit | ledger events |

## Upgrade Conditions

Keep the current hand-written state machine until these become real needs:

- concurrent campaigns;
- durable multi-day retry;
- asynchronous worker queues;
- branching dependency graphs;
- human approval resume across sessions;
- compensation transactions.

At that point, evaluate LangGraph, Burr, or Temporal for the workflow layer
without giving them ownership of Will's campaign/governance core.
