# ADR-004 — BTC Campaign Autonomy Architecture

Status: Accepted. The campaign harness skeleton is implemented; BTC S3/S5
capabilities remain open.

This ADR defines how Will drives a campaign. ADR-006 narrows the engineering
boundary: Will owns campaign/governance semantics; external harnesses own tool
execution, sessions, channels, and raw traces.

## Decision

Make campaign work a first-class Will action surface.

```text
Controller tick -> campaign_tick/revisit -> worker candidate -> artifact gate ->
StageDecision -> ledger event -> advance, revise, revisit, pause, or finalize
```

The current campaign is the BTC MVP:

```text
"BTC 是什么？怎么交易？怎么盈利？"
  -> S1 understand and plan
  -> S2 research BTC basics and trading modes
  -> S3 decide and acquire auditable historical data
  -> S4 run minimal explainable backtests
  -> S5 synthesize final research pack
```

## Goals

- Let Will classify a vague user question as a complex research task.
- Let Will create/adopt and advance a BTC campaign.
- Let workers produce artifacts only through bounded adapters.
- Let deterministic acceptance gates decide whether artifacts enter the ledger.
- Let failure, insufficient data, or Soul critique cause explicit revisit rather
  than silent completion.
- Produce a final research pack, not merely a chat answer.

## Non-Goals

- No live trading or trading credentials.
- No developer-hardcoded answer to the BTC research question.
- No external harness owning canonical campaign state.
- No Soul runtime writing Will state or advancing stages.
- No FundArb/ArbBot local compatibility path.

## Implemented Pieces

- `will/campaigns/btc.py` defines the S1-S5 BTC campaign template.
- `campaign_tick` advances one stage through task run, artifact validation,
  `StageDecisionRecorded`, and ledgered accept/reject/pause events.
- `revisit_stage` resets an accepted stage for explicit rework.
- deterministic fake worker for offline tests.
- delegated research worker path behind policy/run limits.
- BTC S4 executor reads a BTC OHLCV cache rather than funding packet data.
- CLI commands can create, run, inspect, and revisit campaigns.

## BTC Stage Contract

| Stage | Purpose | Required outcome |
|---|---|---|
| S1 | User question understanding and research plan | Scope, questions, risk boundary, needed data/tools. |
| S2 | BTC basics and trading research | Mechanism, venues, costs, custody, leverage, risks, sources. |
| S3 | Data acquisition decision | Candidate data sources, permission decision, cache path, quality report. |
| S4 | Minimal explainable backtest | Baselines such as buy-and-hold, DCA, SMA/cash, metrics and caveats. |
| S5 | Final research pack | User answer, evidence index, backtest summary, risks, limitations, next steps. |

## Data Acquisition Decision Loop

S3 must be a Will decision, not a developer shortcut.

Will should:

1. list candidate sources: local cache, public read-only data, third-party data,
   API-key data, and disallowed trading-permission data;
2. score each candidate for permission level, auditability, coverage, cost, and
   failure mode;
3. default to local cache or public read-only data;
4. request human approval for credentials, paid APIs, long-running jobs, or
   external writes;
5. write source, date range, cache path, quality checks, and reproducibility
   command into the artifact.

If data is insufficient, Will must return `INSUFFICIENT` and revisit or ask for
authorization. It must not invent returns.

## Tool Discovery Roadmap

MVP can use developer-provided safe primitives. The product direction is:

- Will evaluates available tools and workers.
- Tool enablement goes through policy and audit.
- Skills/MCP/browser/search/data tools are hands, not Will's agency core.
- Accepted tool decisions are ledgered.

## Campaign-Level Replan Boundary

Worker-level retry belongs to pi/Codex/OpenAI Agents SDK. Campaign-level replan
belongs to Will.

Examples:

- Worker cannot fetch a source -> worker may try another safe source.
- S3 data coverage is too short -> Will revisits S3 or asks human.
- Soul says the plan relies on second-hand summaries -> Will adopts/rejects the
  critique and may revisit S1.

## Build Order

| Step | Work | Verification |
|---|---|---|
| B1 | Campaign controller seam | Runs bounded ticks and emits ledgered campaign events. |
| B2 | Campaign adoption | Accepted deliverable advances campaign cursor and ledger. |
| B3 | Complex-question triage | BTC question creates/adopts campaign instead of only chatting. |
| B4 | S3 data loop | Data candidates, permission decision, cache, quality report. |
| B5 | S4/S5 completion | Backtest evidence and final research pack. |
| B6 | Quality revisit | Failure/INSUFFICIENT/Soul critique triggers revisit. |

B1/B2 semantics are implemented without the old `environments/` layer. B3-B6
remain the BTC MVP path.
