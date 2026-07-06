# References Map

This file explains how will's research references are organized.

## Local Paper Database

Use [data/papers/manifest.json](/Users/griffith/Projects/AI/will/data/papers/manifest.json)
for public papers with downloadable PDFs. The generated local cache is rebuilt
with:

```bash
python3 scripts/bootstrap_papers.py
```

The PDF cache and SQLite index are intentionally local-only:

- `data/papers/pdfs/`
- `data/papers/papers.sqlite`

## Non-Paper Source Database

Use [data/sources/manifest.json](/Users/griffith/Projects/AI/will/data/sources/manifest.json)
for:

- books and encyclopedia entries;
- official docs;
- GitHub repositories;
- benchmark pages;
- product/market context;
- safety blogs and primary explainers.

The split matters because books, docs, and GitHub repositories should not be
forced into a PDF pipeline. will needs a source graph, not just a folder of
papers.

## Research Layers

| Layer | Main Question | Primary Local Index |
|---|---|---|
| Philosophy of will and intention | What is will, and what is intention as commitment? | `data/papers`, `data/sources` |
| Homeostasis and active inference | How can internal drives choose action? | `data/papers` |
| Autopoiesis and grounded agency | Where do an agent's drives and norms come from? | `data/papers`, `data/sources` |
| Memory systems | How should an agent encode, consolidate, forget, and retrieve? | `data/papers`, `data/sources` |
| Self-cognition | How does an agent maintain a coherent self-model over time? | `data/papers`, `data/sources` |
| Continuous thought | How does a mind think when no task is given (default mode)? | `data/papers` |
| Association and creativity | How do distant memories recombine into new ideas? | `data/papers`, `data/sources` |
| Vision, meaning, and goal hierarchy | Why does an agent have a telos that generates goals? | `data/papers`, `data/sources` |
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

- Primary sources on the neuroscience of volition (e.g. Libet) and the
  attention/global-workspace gate that selects from the continuous stream
  (Baars, Dehaene). (Self-cognition, default-mode/continuous thought,
  association/creativity, and vision/goal-hierarchy are now seeded — see the
  four new research layers above: Metzinger/Gallagher/Northoff/Seth,
  Raichle/Christoff/Smallwood, Collins-Loftus/Mednick/Schacter-Addis,
  Markus-Nurius/Deci-Ryan/Carver-Scheier/Powers. Self-determination theory is
  now covered by Deci & Ryan 2000.)
- An `existence-budget` source set: metabolic/economic governors of cognition,
  since continuous thought and association both depend on it.
- Current official docs when implementation begins, especially LangGraph,
  Mem0, Letta, OpenAI Agents SDK, and Temporal.
- GitHub deep-dive reports only when a candidate will actually be integrated.
