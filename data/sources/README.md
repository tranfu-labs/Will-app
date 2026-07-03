# Will Source Library

This folder tracks important non-paper sources for Will.

Use `data/papers/manifest.json` for public papers with stable downloadable PDFs.
Use `data/sources/manifest.json` for books, encyclopedia entries, official docs,
GitHub repositories, product pages, benchmark pages, and strategy references.

## Rules

- Store URLs and short project-relevant notes, not full copyrighted texts.
- Prefer primary sources: official docs, source repositories, papers, and original
  benchmark pages.
- Use `source_type` to separate `book`, `encyclopedia`, `official-docs`,
  `github`, `benchmark`, `blog`, and `market`.
- Keep generated crawls, local HTML caches, and private transcripts out of Git
  unless a later RFC explicitly approves a source-capture format.
- If a source becomes central and has a public PDF, add it to
  `data/papers/manifest.json` instead of duplicating it here.

## Update Pattern

1. Add or update entries in `data/sources/manifest.json`.
2. If a source motivates a strategic or architectural decision, cite it in a
   document under `docs/`.
3. Keep notes concise enough that the manifest remains a routing index rather
   than a second research report.
