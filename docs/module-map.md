# Module Map

Status: current source of truth after the 2026-07-06 harness refactor.

Will is now organized around seven core modules:

```text
will/
  campaigns/    CampaignTemplate, Campaign, Stage, ArtifactContract, AcceptanceGate
  controller/   tick phases, routing effects, future replay/checkpoint seams
  autonomy/     AutonomyScope/Envelope, usage, interruption policy, StageDecision, policy gates
  workers/      WorkerTask-style delegation, fake worker, patch drafting, future PiWorker/CodexWorker
  lenses/       SoulLens protocol, FakeSoulLens, future Soul API lens
  ledger/       append-only events, snapshots, migrations
  artifacts/    ArtifactRef, SourceRef, EvidenceRef, DataRef, BacktestRef, DeliveryPack
```

Supporting packages:

| Package | Responsibility |
|---|---|
| `core/` | Shared ids, time, secret scanning, legacy/common schemas. |
| `config.py` | Optional provider and worker-adapter configuration. |
| `cli.py` | Thin CLI for ledger, campaign, delegation, and patch drafting. |

Deleted from the runtime surface:

| Removed area | Reason |
|---|---|
| `attention/` | Renamed and reframed as `autonomy/`; human attention is not a normal loop dependency. |
| `execution/` | Renamed and reframed as `workers/`; workers produce candidates only. |
| `state/` | Renamed and reframed as `ledger/`; append-only truth, not general app state. |
| `policy/` | Merged into `autonomy/`; permission gates are autonomy boundaries. |
| `engine/` | Removed; old cognition loop is not Will's runtime identity. |
| `memory/` | Removed from core; canonical truth is ledger + accepted artifacts. |
| `channels/`, `liaison/`, `web/` | Removed from core; long-term interaction shell belongs to OpenClaw. |
| `actions/`, `environments/`, `eval/` | Removed from current core; worker/policy/trajectory tests cover the retained semantics. |
| `fundarb/`, ArbBot/funding scripts/data/tests | Removed; later advanced campaign, not BTC MVP. |

## Boundary Invariants

```text
Campaign defines required outcome.
Worker produces candidate.
Artifact describes and indexes candidate.
Soul critiques candidate.
Autonomy decides whether continuing is inside the boundary.
Controller routes the next effect.
Ledger records facts.
```

No module may simultaneously own `produce + judge + commit`.

## Current Implementation Notes

- `campaigns/engine.py` is still the main concrete state machine. It now records
  `StageDecisionRecorded`, but still needs to be split into controller phases.
- `controller/` currently contains the target phase/effect seam, not a full
  replacement for `campaign_tick`.
- `artifacts/` currently contains reference and delivery-pack schemas. It does
  not execute BTC data acquisition or backtests.
- `workers/delegation.py` is the current worker seam. It should evolve from
  `DelegationClient` into a typed `WorkerAdapter` contract.
- `lenses/` is wired in tests through `decide()`, but `campaign_tick()` does not
  yet call a lens at runtime.

## BTC Mapping

BTC is a campaign template, not a core module:

| BTC concern | Core location |
|---|---|
| S1-S5 stage contract | `campaigns/btc.py` |
| Worker research or analysis | `workers/` task execution |
| BTC data cache reference | `artifacts.DataRef` |
| Backtest output reference | `artifacts.BacktestRef` |
| Final research pack | `artifacts.DeliveryPack` |
| Acceptance or revisit decision | `autonomy.StageDecision` + `controller` routing |
| Historical truth | `ledger/` events |
