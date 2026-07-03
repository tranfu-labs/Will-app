# Will

Will is a research project about AI will: how an agent can move beyond passive token generation into persistent goals, identity continuity, proactive action, productive value loops, and safely governed self-maintenance.

The project now has two layers:

- a research base for the theory, references, and evaluation doctrine;
- a local deterministic v0 runtime that can run one governed will loop at a time.

## Current Materials

| Path | Purpose |
|---|---|
| `RESEARCH.md` | Foundation research report for autonomous agents, memory, identity, proactive behavior, and market context. |
| `docs/strategy-deep-dive.md` | Product/strategy deep dive around private personal agency and governed memory. |
| `docs/what-is-will.md` | Root question answered directly: what will is across the philosophy of will, the science of life/agency, and agent engineering; phenomenal vs functional will; why grounded will needs stake. |
| `docs/theory-of-will.md` | Theoretical foundation: how will emerges from thought stream, memory, drive, stake, intention, action, feedback, and governance. |
| `docs/theory-of-memory.md` | How Will remembers: memory as a governed economy of salience-at-encoding, consolidation (absorb/learn/summarize), and adaptive forgetting, grounded in human memory science and the agent-memory landscape. |
| `docs/memory-fork-strategy.md` | Superseded decision record: Mem0/Letta/Graphiti/cognee were evaluated, but Will now uses its own local SQLite/in-memory governed memory economy. |
| `docs/will-engine-whitepaper.md` | Will's working thesis: definition of functional will, WillState, Autonomous Value Loops, and safety doctrine. |
| `docs/technical-stack-rfc.md` | Technical stack decision record for Will Engine v0. |
| `docs/evaluation-protocol.md` | Evaluation protocol for will maturity, value loops, drift, resource discipline, and governed reproduction. |
| `docs/arbbot-action-environment.md` | Integration blueprint for using ArbBot as Will's first paper/read-only action environment. |
| `docs/web-panel.md` | Read-only web observability panel: live progress, task history, deliverables, and channel-routed approvals. |
| `docs/context-acquisition-strategy.md` | Strategy for acquiring user context through daily conversation, imports, local files, and later connectors. |
| `docs/persona-will-research.md` | Research note on biography/persona-derived decision lenses and why they are not complete will. |
| `docs/references.md` | Routing map for the paper database and non-paper source library. |
| `data/papers/manifest.json` | Source-of-truth paper index with metadata, URLs, priorities, and tags. |
| `data/sources/manifest.json` | Source-of-truth index for books, official docs, GitHub repos, benchmark pages, and product context. |
| `data/funding/ledger.jsonl` | Append-only FundArb funding-rate observation ledger derived from the local VPS-fetched cache. |
| `data/funding/coverage.json` | Deterministic coverage report for the append-only funding ledger. |
| `data/funding/experiment_queue.json` | Deterministic FundArb funding-diff experiment queue generated from coverage. |
| `data/funding/experiment_results.jsonl` | Append-only local execution results for queued funding-diff experiments. |
| `data/funding/promotion_packet.json` | Snapshot packet summarizing current FundArb promotion/kill/data-requirement decisions. |
| `scripts/bootstrap_papers.py` | Rebuilds the local PDF cache and SQLite paper index. |
| `scripts/build_funding_dataset.py` | Rebuilds the append-only funding ledger and coverage report from `data/funding_cache.json`. |
| `scripts/build_funding_experiment_queue.py` | Rebuilds the deterministic funding-diff experiment queue from coverage. |
| `scripts/execute_funding_experiment_queue.py` | Executes queued sentinel backtests into the append-only results ledger. |
| `scripts/build_funding_promotion_packet.py` | Builds the research-only promotion/kill packet from experiment results. |
| `data/papers/README.md` | Paper library maintenance and query guide. |
| `data/sources/README.md` | Non-paper source library maintenance guide. |
| `yizhi/campaigns/` | W1 deterministic Campaign Harness: Campaign/Stage/TaskRun/Deliverable/AcceptanceGate schemas, BTC template, fake worker tick engine, artifact validators, and event-sourced projection. |
| `yizhi/` | Internal legacy Python namespace for the Local Will Agent v0 runtime: schemas, event store, policy gate, environments, loop, runner, campaign harness, CLI, and the `yizhi/memory/` will-governed memory economy (salience-at-encoding, adaptive forgetting, consolidation, will-ranking). |
| `tests/` | pytest coverage for schemas, event store, policy gates, environments, memory, runner, planning, LLM fallbacks, ArbBot probes, loop evaluation, and rollback boundaries. |

## Will Agent v0 Runtime

The base v0 runtime is deliberately local, deterministic, and bounded. It does
not request OAuth access, create long-running subagents, read or write trading
credentials, place live orders, or modify ArbBot. Optional LLM, LiteLLM, and
embedding extras exist behind explicit config; the offline core and CI run with
those helpers disabled.

Install test/runtime dependencies in your preferred Python environment:

```bash
python3 -m pip install -e ".[dev]"
```

Initialize the local event store:

```bash
will init
```

Run one bounded loop against this repository:

```bash
will step --env self
```

Run one paper/read-only loop against ArbBot:

```bash
will step --env arbbot --root /Users/griffith/Projects/AI/ArbBot
```

Inspect recent loop evaluations:

```bash
will eval loops
```

Run continuously until a bounded stop condition:

```bash
will run --env self --max-steps 5
```

### Campaign Harness

The W1 Campaign Harness is the deterministic project-work spine for BTC MVP:
campaign → stage → task run → deliverable → acceptance gate → cursor advance or
revisit. W1 uses only a fake worker and local artifacts; it proves the harness,
not real BTC research.

```bash
will campaign create-btc
will campaign run --id btc-mvp --max-ticks 2
will campaign state --id btc-mvp
will campaign revisit --id btc-mvp --stage S1 --note "补充调研资金费率机制"
```

Campaign artifacts are local cache under `data/campaigns/<id>/` and ignored by
Git. The event store records artifact paths, hashes, validation results, and
supersession events.

### Web Panel

A read-only observability panel shows live progress (goal, plan cursor, budget),
task history rebuilt from the goal lifecycle events, the event timeline (SSE
live tail), FundArb deliverables, and an approval queue whose approve/kill
buttons append to the channel inbox — the same governed `InboundCommand` path
Telegram uses. The panel never starts runs and opens the store read-only.

```bash
python3 -m pip install -e ".[web]"
will serve-web        # http://127.0.0.1:8321
```

See `docs/web-panel.md` for pages, API, SSE design, and security boundaries.

Runtime state is stored in `.yizhi/state.sqlite` and is intentionally ignored by
Git. The event store records observations, thoughts, drive updates, intentions,
plans, proposals, policy decisions, actions, verification, reflection, memory,
eval events, and snapshots. Failures and policy denials are first-class events,
not silent aborts.

### ArbBot Boundary

In v0, ArbBot is only an `ActionEnvironment` for observation and allowlisted
paper/read-only commands. The policy gate rejects live trading, credentials,
reproduction, self-modification, concrete execution venues, and non-allowlisted
ArbBot commands. In the deterministic loop the chosen action follows the will's
second-order endorsement: an endorsed exploratory drive takes a paper-safe probe
(e.g. `make test`), while a maintenance/continuity drive takes `git status --short
--branch`. Either way the smoke loop records or tests ArbBot state without modifying
ArbBot.

## FundArb Data Ledger

`data/funding_cache.json` is the current local snapshot fetched outside the will
loop. The append-only dataset lives under `data/funding/`: each JSONL record is a
single venue/symbol/timestamp funding-rate observation, deduplicated by
`record_id`. Re-running the build on the same cache is idempotent.

Build or refresh the ledger and coverage report with either entrypoint:

```bash
python3 scripts/build_funding_dataset.py
will funding dataset
```

Build or refresh the deterministic experiment queue:

```bash
python3 scripts/build_funding_experiment_queue.py
will funding queue
```

Execute queued local sentinel backtests and summarize the current research packet:

```bash
python3 scripts/execute_funding_experiment_queue.py --max-experiments 3
python3 scripts/build_funding_promotion_packet.py
will funding run-queue --max-experiments 3
will funding packet
```

Execute the full current deterministic queue by omitting the smoke limit:

```bash
will funding run-queue
will funding packet
```

The command writes:

- `data/funding/ledger.jsonl`
- `data/funding/coverage.json`
- `data/funding/experiment_queue.json`
- `data/funding/experiment_results.jsonl`
- `data/funding/promotion_packet.json`

Current local cache status: the generated queue covers 12 symbols and 60
experiments. The full current queue has been executed into the append-only
results ledger. Its research-only packet contains 12
`kill_or_data_requirement` decisions: 12 `KILL` verdicts for broad enter-all
baselines and 48 `INSUFFICIENT` verdicts for sample-limited filtered tests.
There are 0 `PROMOTE` and 0 `ITERATE` verdicts. This is not paper/live trading
authorization.

## Local Paper Library

PDFs and the generated SQLite database are local cache files and are intentionally not tracked in Git.

Rebuild them with:

```bash
python3 scripts/bootstrap_papers.py
```

This downloads PDFs listed in `data/papers/manifest.json` into `data/papers/pdfs/` and builds `data/papers/papers.sqlite`.

Query example:

```bash
sqlite3 -header -column data/papers/papers.sqlite \
  "select id, year, priority, title from papers order by year, id;"
```

## Knowledge Base Policy

GitHub should store:

- Durable project thinking and strategy docs.
- Paper/source manifests with URLs and short notes.
- Scripts that rebuild local caches.
- Schemas and small derived metadata.
- The append-only FundArb funding ledger and its coverage report.

GitHub should not store by default:

- Downloaded PDFs that can be regenerated from public URLs.
- Generated SQLite/cache files.
- Full copyrighted books, transcripts, or private materials.
- API keys, tokens, or local environment files.

This keeps the repository lightweight and makes updates efficient: edit the manifest, rerun the bootstrap script locally, and commit only the updated manifest/scripts/docs.

## Current North Star

Will is not trying to be another chat assistant, IDE assistant, or generic
agent shell. The research object is functional AI will:

> goal continuity + self-model + internal drive + world model + memory +
> practical reasoning + action + feedback learning + self-maintenance +
> governed reproduction.

The north-star unit is the **Autonomous Value Loop**: the agent discovers a gap
or opportunity, forms an intention, plans, acts, verifies external value,
captures feedback, updates memory/skill/policy, and improves future behavior.

See `docs/will-engine-whitepaper.md` and `docs/evaluation-protocol.md` for the
current doctrine. See `docs/theory-of-will.md` for the upstream theory of how
will emerges from thought stream, memory continuity, drive, stake, intention,
action, feedback, and governance. See `docs/what-is-will.md` for the root
question itself: what will is, which literature defines it, and whether an agent
can have it.
