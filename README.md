# yizhi

yizhi is a research project about AI will: how an agent can move beyond passive token generation into persistent goals, identity continuity, proactive action, productive value loops, and safely governed self-maintenance.

The project is currently a research base, not an application runtime.

## Current Materials

| Path | Purpose |
|---|---|
| `RESEARCH.md` | Foundation research report for autonomous agents, memory, identity, proactive behavior, and market context. |
| `docs/strategy-deep-dive.md` | Product/strategy deep dive around private personal agency and governed memory. |
| `docs/theory-of-will.md` | Theoretical foundation: how will emerges from thought stream, memory, drive, intention, action, feedback, and governance. |
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
will emerges from thought stream, memory continuity, drive, intention, action,
feedback, and governance.
