# yizhi

yizhi is a research project about AI will: how an agent can move beyond passive token generation into persistent goals, identity continuity, proactive action, productive value loops, and safely governed self-maintenance.

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
| `docs/theory-of-memory.md` | How yizhi remembers: memory as a governed economy of salience-at-encoding, consolidation (absorb/learn/summarize), and adaptive forgetting, grounded in human memory science and the agent-memory landscape. |
| `docs/memory-fork-strategy.md` | Decision record: which mature OSS memory project (Mem0/Letta/Graphiti/cognee) to fork/extend as yizhi's memory base, and the four governance modules to build on top. |
| `docs/will-engine-whitepaper.md` | yizhi's working thesis: definition of functional will, WillState, Autonomous Value Loops, and safety doctrine. |
| `docs/technical-stack-rfc.md` | Technical stack decision record for Will Engine v0. |
| `docs/evaluation-protocol.md` | Evaluation protocol for will maturity, value loops, drift, resource discipline, and governed reproduction. |
| `docs/arbbot-action-environment.md` | Integration blueprint for using ArbBot as yizhi's first paper/read-only action environment. |
| `docs/context-acquisition-strategy.md` | Strategy for acquiring user context through daily conversation, imports, local files, and later connectors. |
| `docs/persona-will-research.md` | Research note on biography/persona-derived decision lenses and why they are not complete will. |
| `docs/references.md` | Routing map for the paper database and non-paper source library. |
| `data/papers/manifest.json` | Source-of-truth paper index with metadata, URLs, priorities, and tags. |
| `data/sources/manifest.json` | Source-of-truth index for books, official docs, GitHub repos, benchmark pages, and product context. |
| `scripts/bootstrap_papers.py` | Rebuilds the local PDF cache and SQLite paper index. |
| `data/papers/README.md` | Paper library maintenance and query guide. |
| `data/sources/README.md` | Non-paper source library maintenance guide. |
| `yizhi/` | Local Will Agent v0 runtime: schemas, event store, policy gate, environments, loop, CLI, and the `yizhi/memory/` will-governed memory economy (salience-at-encoding, adaptive forgetting, consolidation, will-ranking; Mem0 optional backend). |
| `tests/` | pytest coverage for schemas, event store, policy gates, environments, loop evaluation, and rollback boundaries. |

## Will Agent v0 Runtime

The v0 runtime is deliberately local, deterministic, and bounded. It does not
call an LLM, request OAuth access, create long-running subagents, read or write
trading credentials, place live orders, or modify ArbBot.

Install test/runtime dependencies in your preferred Python environment:

```bash
python3 -m pip install -e ".[dev]"
```

Initialize the local event store:

```bash
python3 -m yizhi.cli init
```

Run one bounded loop against this repository:

```bash
python3 -m yizhi.cli step --env self
```

Run one paper/read-only loop against ArbBot:

```bash
python3 -m yizhi.cli step --env arbbot --root /Users/griffith/Projects/AI/ArbBot
```

Inspect recent loop evaluations:

```bash
python3 -m yizhi.cli eval loops
```

Runtime state is stored in `.yizhi/state.sqlite` and is intentionally ignored by
Git. The event store records observations, thoughts, drive updates, intentions,
plans, proposals, policy decisions, actions, verification, reflection, memory,
eval events, and snapshots. Failures and policy denials are first-class events,
not silent aborts.

### ArbBot Boundary

In v0, ArbBot is only an `ActionEnvironment` for observation and allowlisted
paper/read-only commands. The policy gate rejects live trading, credentials,
reproduction, self-modification, concrete execution venues, and non-allowlisted
ArbBot commands. The default ArbBot proposal chosen by the deterministic loop is
`git status --short --branch`, so a smoke loop records ArbBot state without
modifying ArbBot.

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

GitHub should not store by default:

- Downloaded PDFs that can be regenerated from public URLs.
- Generated SQLite/cache files.
- Full copyrighted books, transcripts, or private materials.
- API keys, tokens, or local environment files.

This keeps the repository lightweight and makes updates efficient: edit the manifest, rerun the bootstrap script locally, and commit only the updated manifest/scripts/docs.

## Current North Star

yizhi is not trying to be another chat assistant, IDE assistant, or generic
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
