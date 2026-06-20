# yizhi

yizhi is a research project about AI will: how an agent can move beyond passive token generation into persistent goals, identity continuity, proactive action, productive value loops, and safely governed self-maintenance.

The project is currently a research base, not an application runtime.

## Current Materials

| Path | Purpose |
|---|---|
| `RESEARCH.md` | Foundation research report for autonomous agents, memory, identity, proactive behavior, and market context. |
| `docs/strategy-deep-dive.md` | Product/strategy deep dive around private personal agency and governed memory. |
| `data/papers/manifest.json` | Source-of-truth paper index with metadata, URLs, priorities, and tags. |
| `scripts/bootstrap_papers.py` | Rebuilds the local PDF cache and SQLite paper index. |
| `data/papers/README.md` | Paper library maintenance and query guide. |

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
