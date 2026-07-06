# Will Production Roadmap

Status: draft roadmap aligned with ADR-006 and ADR-007.

## North Star

Will reduces human attention load by autonomously advancing long-running
campaigns inside explicit boundaries.

Current MVP:

```text
BTC campaign research pack
```

Not current MVP:

```text
FundArb / ArbBot arbitrage loop
```

## P0: BTC Campaign MVP

Goal: prove vague question -> complete, auditable research package.

Required capabilities:

- S1 problem understanding and research plan.
- S2 BTC mechanism, trading methods, costs, and risks.
- S3 auditable data acquisition decision and BTC OHLCV cache reference.
- S4 explainable baseline backtests with reproducibility evidence.
- S5 DeliveryPack with final answer, accepted artifacts, evidence index, risks,
  limitations, and next steps.
- Failure path: missing evidence or bad backtest manifest causes revise/revisit,
  not fake completion.

Exit criterion:

```text
One local run produces accepted S1-S5 artifacts,
DataRef, BacktestRef, DeliveryPack, StageDecisionRecorded events,
and a readable audit trail.
```

## P1: Controller And Artifact Hardening

- Split `campaign_tick()` into controller phases and effects.
- Make `StageDecision` the route driver, not only an audit side event.
- Move manifest/provenance validation into `artifacts/` without moving execution
  there.
- Rename `TaskRun` toward `WorkerTask / WorkerRun / WorkerResult`.
- Rename `Deliverable` toward `ArtifactSubmission / ArtifactAcceptance`.

## P2: Worker And Soul Integration

- Generalize `DelegationClient` into typed `WorkerAdapter`.
- Add manually gated PiWorker/CodexWorker/OpenAIWorker adapters.
- Add SoulApiLens while preserving read-only advisory semantics.
- Record adopted/rejected Soul findings in the ledger.

## P3: Shell And Advanced Campaigns

- Let OpenClaw or another shell provide status, steer, pause, digest, and
  approval UI.
- Re-evaluate LangGraph/Burr/Temporal only when durable branching workflow
  complexity becomes real.
- Reintroduce FundArb-like financial research only as a separate advanced
  campaign after BTC MVP closes.

## Not Doing

- No `research/` core module.
- No self-directed cognition loop in runtime.
- No built-in web/channel shell as Will core.
- No automatic trading, credential access, patch apply, commit, push, or deploy.
