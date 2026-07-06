# ADR-001 — Build vs Rent vs Port

Status: Historical baseline. Superseded in runtime details by ADR-006 and
ADR-007.

## Preserved Principle

Will should not absorb an external agent framework as its core just because the
framework can run tools. Will keeps only the campaign/governance semantics that
external harnesses do not naturally own:

- campaign and stage contracts;
- artifact acceptance;
- autonomy boundary;
- adoption/revisit/finalization decisions;
- append-only delivery ledger.

Tool execution, browsing, coding workbench behavior, provider sessions, and
interaction shells should be rented or adapted through workers and shells.

## Current Runtime Decision

Current code follows the seven-module architecture:

```text
campaigns / controller / autonomy / workers / lenses / ledger / artifacts
```

LangGraph, Burr, Temporal, OpenAI Agents SDK, pi, Codex, and OpenClaw may be
used as worker/session/workflow/shell layers later, but none of them owns Will's
campaign state or ledger.

## Upgrade Trigger

Re-evaluate graph or durable workflow runtimes only when the hand-written
controller hits real complexity:

- concurrent campaigns;
- branching dependency graphs;
- durable async worker queues;
- long-running retry/resume;
- human approval resume across sessions;
- failure compensation.
