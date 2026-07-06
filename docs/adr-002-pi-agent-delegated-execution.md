# ADR-002 — pi/Codex/OpenClaw As Workers, Not Will Core

Status: Accepted. Updated after the 2026-07-06 module refactor.

## Decision

pi, Codex, OpenAI Agents SDK, and OpenClaw worker plugins are **WorkerAdapter**
candidates. They are execution bodies, not Will's campaign/governance core.

Current implementation:

```text
will/workers/delegation.py
will/workers/patches.py
```

The current `DelegationClient` is a predecessor of the future typed
`WorkerAdapter` contract.

## Boundary

Workers may:

- search;
- read a repo;
- draft a patch artifact;
- summarize tests;
- browse or call safe tools inside their own sandbox;
- return candidate reports, diffs, data, or artifact text.

Workers must not:

- advance campaign cursor;
- accept/reject/finalize stages;
- write canonical ledger events directly;
- own policy, budget, memory, or final delivery;
- apply patches, commit, push, deploy, trade, or access credentials.

## Required Flow

```text
Will creates bounded WorkerTask-like request
  -> autonomy/policy gate
  -> worker run
  -> candidate output
  -> artifact validation
  -> optional SoulLens critique
  -> StageDecision
  -> controller route
  -> ledger commit
```

Worker output is never canonical until Will accepts it.

## Future Work

Generalize `DelegationClient` into:

```text
WorkerTask -> WorkerRun -> WorkerResult
```

Then add concrete adapters:

- `FakeWorker`;
- `PiWorker`;
- `CodexWorker`;
- `OpenAIWorker`;
- `OpenClawWorkerPlugin`.
