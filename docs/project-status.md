# Will Project Status

Status: current-state handoff after the 2026-07-06 architecture cleanup.

## Objective

Build Will as an **Autonomous Campaign Harness**:

```text
Human gives goal + boundary.
Will controls the campaign.
Workers produce candidates.
Soul critiques candidates.
Will accepts, revises, revisits, pauses, or finalizes.
Ledger records the truth.
```

The current MVP is still the BTC campaign:

```text
User: "BTC 是什么？怎么交易？怎么盈利？"
Will: create/adopt BTC campaign -> route workers -> validate artifacts ->
      acquire auditable data -> run explainable backtests -> revisit on failure ->
      deliver a complete research pack with evidence, risks, limits, and next steps.
```

The MVP success criterion is a complete research package, not discovery of a
real trading edge and not a FundArb arbitrage loop.

## Current Architecture

Current runtime modules:

```text
will/campaigns/
will/controller/
will/autonomy/
will/workers/
will/lenses/
will/ledger/
will/artifacts/
will/core/
will/config.py
will/cli.py
```

Removed from the runtime:

```text
will/attention/
will/execution/
will/state/
will/policy/
will/engine/
will/memory/
will/channels/
will/liaison/
will/web/
will/actions/
will/environments/
will/eval/
will/fundarb/
```

## Verification Snapshot

Current branch:

```text
refactor/remove-cognition-loop
```

The worktree is intentionally dirty because this is an active refactor that
renamed modules and deleted old runtime surfaces.

Current test baseline:

```bash
python3 -m pytest -q
# 70 passed
```

Targeted checks:

```bash
python3 -m pytest tests/test_campaign_executor.py tests/test_campaigns.py -q
python3 -m pytest tests/test_autonomy.py tests/test_lenses.py tests/test_delegation.py -q
```

CLI smoke:

```bash
python3 -m will.cli --db /tmp/will-final-smoke.sqlite campaign create-btc --id btc-final --workspace-root /tmp/will-final-smoke-campaigns
python3 -m will.cli --db /tmp/will-final-smoke.sqlite campaign run --id btc-final --max-ticks 1
python3 -m will.cli --db /tmp/will-final-smoke.sqlite events --limit 20
# S1 accepted, cursor advanced to 1, StageDecisionRecorded verdict=accept interruption=digest
```

## Implemented Facts

- Package namespace is `will`.
- BTC S1-S5 campaign template exists in `campaigns/btc.py`.
- `campaign_tick()` advances the deterministic campaign state machine.
- `campaign_tick()` now records `StageDecisionRecorded` before accept/reject routing.
- `autonomy/` owns `AutonomyEnvelope`, `EnvelopeUsage`, `InterruptionPolicy`,
  `StageDecision`, budget helpers, and policy gates.
- `workers/` owns governed delegation and patch drafting.
- `ledger/` owns append-only event storage and snapshots.
- `artifacts/` owns artifact/evidence/data/backtest/delivery-pack reference schemas.
- `lenses/` owns `SoulLens` protocol and `FakeSoulLens`.
- CLI is now limited to core surfaces: `init`, `events`, `state`, `delegate`,
  `campaign`, and `patch`.
- `core/schemas.py` no longer exposes the old cognition-loop objects
  (`ThoughtEvent`, `DriveSignal`, `MemoryRecord`, `Intention`, `Plan`,
  `Reflection`, `AutonomousValueLoop`).
- The ledger migration no longer creates old memory tables.

## Known Debt

P0:

- Split `campaign_tick()` into controller phases/effects without changing
  behavior.
- Pass real `StageDecision` outcomes through accept/revise/revisit/pause/finalize
  routes, including failure trajectories.
- Feed `SoulLensReport` into `campaign_tick()` rather than only testing
  `decide()` separately.
- Make S5 produce a real `DeliveryPack` manifest that only references accepted
  S1-S4 artifacts.

P1:

- Replace `TaskRun` terminology with `WorkerTask / WorkerRun / WorkerResult`.
- Replace `Deliverable` terminology with `ArtifactSubmission /
  ArtifactAcceptance / AcceptedArtifactRef`.
- Move artifact hash/provenance validation into `artifacts/` while keeping
  `campaigns/` as the contract owner.

P2:

- Add real PiWorker/CodexWorker/OpenAIWorker adapters behind `workers/`.
- Add Soul API lens behind `lenses/`.
- Reintroduce an interaction shell only through OpenClaw or an explicit shell
  adapter, not as Will core.

## Architecture Guardrails

- No `research/` core module. Research is a campaign template or worker task kind.
- No self-directed cognition loop in runtime.
- No worker owns campaign cursor, acceptance, policy, budget, memory, or ledger.
- No Soul runtime writes Will state.
- No OpenClaw/plugin/session state becomes canonical Will truth.
- No automatic trading, credential access, external write, patch apply, commit,
  push, or deployment.

## Next Slice

Recommended implementation order:

1. Add controller phase/effect tests for happy path and failure path.
2. Make `StageDecisionRecorded` drive routing instead of being a side record.
3. Add artifact manifest references for S3/S4/S5.
4. Add SoulLens runtime call before route decision.
5. Convert old `Deliverable` and `TaskRun` names once behavior is pinned.
