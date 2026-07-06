#!/usr/bin/env python3
"""Build the local will paper library.

This script downloads PDFs listed in data/papers/manifest.json and writes a
SQLite database with source metadata, tags, local paths, file sizes, and hashes.
It is intentionally small and stdlib-only so the paper library can be rebuilt on
a clean machine.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "papers" / "manifest.json"
PDF_DIR = ROOT / "data" / "papers" / "pdfs"
DB_PATH = ROOT / "data" / "papers" / "papers.sqlite"
USER_AGENT = "will-paper-library/0.1 (+local research database)"


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        PRAGMA journal_mode = WAL;
        CREATE TABLE IF NOT EXISTS papers (
          id TEXT PRIMARY KEY,
          title TEXT NOT NULL,
          year INTEGER,
          authors TEXT,
          source_url TEXT,
          pdf_url TEXT,
          priority TEXT,
          notes TEXT,
          local_pdf_path TEXT,
          download_status TEXT NOT NULL,
          download_error TEXT,
          file_size_bytes INTEGER,
          sha256 TEXT,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS paper_tags (
          paper_id TEXT NOT NULL,
          tag TEXT NOT NULL,
          PRIMARY KEY (paper_id, tag),
          FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS sources (
          paper_id TEXT NOT NULL,
          source_type TEXT NOT NULL,
          url TEXT NOT NULL,
          PRIMARY KEY (paper_id, source_type, url),
          FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE
        );
        """
    )


def download_pdf(url: str, path: Path, force: bool = False) -> tuple[str, str | None]:
    if path.exists() and path.stat().st_size > 0 and not force:
        return "exists", None

    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            content_type = response.headers.get("Content-Type", "")
            data = response.read()
    except (urllib.error.URLError, TimeoutError) as exc:
        return "failed", str(exc)

    if len(data) < 1024:
        return "failed", f"download too small: {len(data)} bytes"

    if b"%PDF" not in data[:2048] and "pdf" not in content_type.lower():
        return "failed", f"unexpected content type: {content_type or 'unknown'}"

    path.write_bytes(data)
    return "downloaded", None


def upsert_paper(
    conn: sqlite3.Connection,
    item: dict,
    local_path: Path,
    status: str,
    error: str | None,
) -> None:
    rel_path = local_path.relative_to(ROOT).as_posix() if local_path.exists() else None
    file_size = local_path.stat().st_size if local_path.exists() else None
    file_hash = sha256_file(local_path) if local_path.exists() else None

    conn.execute(
        """
        INSERT INTO papers (
          id, title, year, authors, source_url, pdf_url, priority, notes,
          local_pdf_path, download_status, download_error, file_size_bytes, sha256
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
          title = excluded.title,
          year = excluded.year,
          authors = excluded.authors,
          source_url = excluded.source_url,
          pdf_url = excluded.pdf_url,
          priority = excluded.priority,
          notes = excluded.notes,
          local_pdf_path = excluded.local_pdf_path,
          download_status = excluded.download_status,
          download_error = excluded.download_error,
          file_size_bytes = excluded.file_size_bytes,
          sha256 = excluded.sha256,
          updated_at = CURRENT_TIMESTAMP
        """,
        (
            item["id"],
            item["title"],
            item.get("year"),
            item.get("authors"),
            item.get("source_url"),
            item.get("pdf_url"),
            item.get("priority"),
            item.get("notes"),
            rel_path,
            status,
            error,
            file_size,
            file_hash,
        ),
    )
    conn.execute("DELETE FROM paper_tags WHERE paper_id = ?", (item["id"],))
    for tag in item.get("themes", []):
        conn.execute(
            "INSERT OR IGNORE INTO paper_tags (paper_id, tag) VALUES (?, ?)",
            (item["id"], tag),
        )
    conn.execute(
        "INSERT OR IGNORE INTO sources (paper_id, source_type, url) VALUES (?, ?, ?)",
        (item["id"], "landing_page", item.get("source_url", "")),
    )
    conn.execute(
        "INSERT OR IGNORE INTO sources (paper_id, source_type, url) VALUES (?, ?, ?)",
        (item["id"], "pdf", item.get("pdf_url", "")),
    )


def main() -> int:
    force = "--force" in sys.argv
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with MANIFEST.open("r", encoding="utf-8") as handle:
        items = json.load(handle)

    conn = sqlite3.connect(DB_PATH)
    try:
        init_db(conn)
        for index, item in enumerate(items, start=1):
            filename = f"{item.get('year', 'unknown')}-{slugify(item['id'])}.pdf"
            local_path = PDF_DIR / filename
            print(f"[{index:02d}/{len(items):02d}] {item['id']}")
            pdf_url = item.get("pdf_url") or ""
            if not pdf_url:
                status, error = "skipped", "no pdf_url in manifest (landing page only)"
            else:
                status, error = download_pdf(pdf_url, local_path, force=force)
            if error:
                print(f"  {status}: {error}")
            else:
                print(f"  {status}: {local_path.relative_to(ROOT)}")
            upsert_paper(conn, item, local_path, status, error)
            conn.commit()
            time.sleep(0.5)
    finally:
        conn.close()

    print(f"\nDatabase: {DB_PATH.relative_to(ROOT)}")
    print(f"PDF dir:  {PDF_DIR.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
