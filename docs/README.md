# Will Docs Index

Will is documented as an **Autonomous Campaign Harness**.

Core boundary:

```text
Will owns campaign control, autonomy boundaries, artifact acceptance, and ledger.
Workers own execution.
Soul owns quality critique.
OpenClaw owns future interaction shell.
Humans own authority.
```

## Current Documents

| Document | Status | Purpose |
|---|---|---|
| [project-status.md](project-status.md) | Current facts | Current state, verification, and remaining debt. |
| [module-map.md](module-map.md) | Current facts | Runtime module map after the refactor. |
| [adr-001-build-rent-port.md](adr-001-build-rent-port.md) | Historical | Build/rent/port baseline; superseded where newer ADRs are more specific. |
| [adr-002-pi-agent-delegated-execution.md](adr-002-pi-agent-delegated-execution.md) | Accepted | pi/Codex-style harnesses are bounded workers, not Will core. |
| [adr-004-campaign-autonomy-architecture.md](adr-004-campaign-autonomy-architecture.md) | Accepted | BTC campaign S1-S5 contract and autonomy expectations. |
| [adr-005-will-soul-collaboration.md](adr-005-will-soul-collaboration.md) | Accepted | Soul as external read-only quality lens. |
| [adr-006-will-harness-kernel.md](adr-006-will-harness-kernel.md) | Accepted | Minimal campaign/governance harness decision. |
| [adr-007-autonomous-campaign-architecture.md](adr-007-autonomous-campaign-architecture.md) | Accepted | Seven-module autonomous campaign architecture. |
| [will-engine-production-roadmap.md](will-engine-production-roadmap.md) | Draft roadmap | BTC MVP phases and priorities. |
| [references.md](references.md) | Source map | Research/reference routing notes. |

## Removed From Current Work Surface

- FundArb/ArbBot runtime code, funding data, scripts, and tests.
- Old cognition engine, memory economy, dialogue, web, channels, actions, and
  environments runtime surfaces.
- Self-model mutation ADR and cognition-loop schema surface.
- `research/` as a proposed core module.
- `Attention-Aware` as the project identity.

## Implementation Truths To Preserve

- `campaigns/` is the campaign contract and stage aggregate.
- `controller/` is the deterministic state-machine seam.
- `autonomy/` is the permission/budget/interruption/decision boundary.
- `workers/` are execution adapters; they produce candidates only.
- `lenses/` are advisory quality views; they never mutate Will state.
- `ledger/` is canonical event truth.
- `artifacts/` describes references and delivery manifests, not execution.
