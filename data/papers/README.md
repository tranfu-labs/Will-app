# yizhi Paper Library

This folder is the local research database for yizhi's will/agent study.

## Layout

```text
data/papers/
├── README.md
├── manifest.json          # source-of-truth paper list
├── papers.sqlite          # generated SQLite index
└── pdfs/                  # downloaded PDFs
```

## Rebuild

```bash
python3 scripts/bootstrap_papers.py
```

Force redownload:

```bash
python3 scripts/bootstrap_papers.py --force
```

The script is stdlib-only and writes:

- `papers`: paper metadata, local PDF path, download status, SHA-256.
- `paper_tags`: many-to-many theme tags.
- `sources`: landing-page and PDF URLs.

## Query Examples

All papers:

```bash
sqlite3 -header -column data/papers/papers.sqlite \
  "select id, year, priority, title from papers order by year, id;"
```

Papers related to memory:

```bash
sqlite3 -header -column data/papers/papers.sqlite \
  "select p.id, p.title from papers p join paper_tags t on t.paper_id = p.id where t.tag = 'memory';"
```

Download status:

```bash
sqlite3 -header -column data/papers/papers.sqlite \
  "select download_status, count(*) from papers group by download_status;"
```

## Current Theme Layers

| Layer | Purpose |
|---|---|
| `will-theory` | Internal drive, homeostasis, agency theory references. |
| `core` | yizhi core architecture: memory, identity, proactive behavior, long-horizon reliability. |
| `foundation` | Common LLM agent primitives such as ReAct, Reflexion, planning, embodied feedback. |
| `safety` | Required safety references for self-maintenance, resources, and reproduction. |
| `watch` | Newer or less-verified papers that should be rechecked before becoming core doctrine. |

## Maintenance Rules

- Add new papers to `manifest.json`, then rerun `scripts/bootstrap_papers.py`.
- Keep `notes` short and project-relevant.
- Use `priority = watch` for papers whose claims or metadata still need verification.
- Do not store API keys, private datasets, or copyrighted full books here.
- For books, biographies, transcripts, and non-paper sources, create a separate source library instead of forcing them into this PDF database.
