# References Map

This file explains how yizhi's research references are organized.

## Local Paper Database

Use [data/papers/manifest.json](/Users/griffith/Projects/AI/yizhi/data/papers/manifest.json)
for public papers with downloadable PDFs. The generated local cache is rebuilt
with:

```bash
python3 scripts/bootstrap_papers.py
```

The PDF cache and SQLite index are intentionally local-only:

- `data/papers/pdfs/`
- `data/papers/papers.sqlite`

## Non-Paper Source Database

Use [data/sources/manifest.json](/Users/griffith/Projects/AI/yizhi/data/sources/manifest.json)
for:

- books and encyclopedia entries;
- official docs;
- GitHub repositories;
- benchmark pages;
- product/market context;
- safety blogs and primary explainers.

The split matters because books, docs, and GitHub repositories should not be
forced into a PDF pipeline. yizhi needs a source graph, not just a folder of
papers.

## Research Layers

| Layer | Main Question | Primary Local Index |
|---|---|---|
| Philosophy of intention | What is will/intention as commitment? | `data/papers`, `data/sources` |
| Homeostasis and active inference | How can internal drives choose action? | `data/papers` |
| LLM agent architecture | How do memory, planning, reflection, and tools compose? | `data/papers`, `data/sources` |
| Self-evolution | How can agents improve memory, tools, skills, and code safely? | `data/papers`, `data/sources` |
| Evaluation | How do we measure persistence, value, drift, and safety? | `data/papers`, `data/sources` |
| Product strategy | Which application layers are defensible? | `docs/`, `data/sources` |

## Query Examples

```bash
sqlite3 -header -column data/papers/papers.sqlite \
  "select id, year, priority, title from papers where priority in ('will-theory','safety') order by year;"
```

```bash
sqlite3 -header -column data/papers/papers.sqlite \
  "select p.id, p.title from papers p join paper_tags t on t.paper_id = p.id where t.tag = 'self-evolving-agent';"
```

```bash
node -e "const s=require('./data/sources/manifest.json'); console.table(s.filter(x=>x.source_type==='github').map(({id,title,url,priority})=>({id,title,url,priority})))"
```

## What To Add Next

- More primary sources on autopoiesis/adaptivity/teleology.
- Current official docs when implementation begins, especially LangGraph,
  Mem0, Letta, OpenAI Agents SDK, and Temporal.
- GitHub deep-dive reports only when a candidate will actually be integrated.
