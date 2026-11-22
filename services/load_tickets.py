"""
load_tickets.py
---------------
One-time load of the JIRA CSV into SQLite.

Builds:
  tickets      — B-tree primary key on `key`  → O(log n) exact lookup
  tickets_fts  — FTS5 full-text index on summary + discussion → BM25-ranked
                 keyword search (replaces pandas str.contains full scans)

Writes to a temp file and swaps it in atomically, so a running server
keeps reading the old DB until the new one is complete.

Run from services/:   python load_tickets.py
Re-running rebuilds from scratch.
"""

import os
import time
import sqlite3
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

CSV_PATH = os.environ.get("JIRA_CSV_PATH", "../jira_demo.csv")
DB_PATH  = os.environ.get("TICKETS_DB_PATH", "data/tickets.db")
CHUNK    = 10_000


def main():
    t0 = time.time()
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    tmp_path = DB_PATH + ".tmp"
    if os.path.exists(tmp_path):
        os.remove(tmp_path)

    conn = sqlite3.connect(tmp_path)
    conn.executescript("""
        PRAGMA journal_mode = OFF;     -- bulk load into a throwaway file: speed over durability
        PRAGMA synchronous  = OFF;

        CREATE TABLE tickets (
            key        TEXT PRIMARY KEY,
            summary    TEXT,
            priority   TEXT,
            resolution TEXT,
            discussion TEXT
        );

        -- External-content FTS5 table: indexes tickets without duplicating the text
        CREATE VIRTUAL TABLE tickets_fts USING fts5(
            summary, discussion,
            content='tickets', content_rowid='rowid',
            tokenize='porter unicode61'
        );
    """)

    print(f"Loading {CSV_PATH} → {DB_PATH}")
    total = 0
    for chunk in pd.read_csv(CSV_PATH, chunksize=CHUNK, dtype=str, keep_default_na=False):
        rows = [
            (
                str(r.get("key", "")).strip().upper(),
                r.get("summary", ""),
                r.get("priority.name", ""),
                r.get("resolution.name", ""),
                r.get("comments_text", ""),
            )
            for r in chunk.to_dict("records")
        ]
        rows = [r for r in rows if r[0]]
        conn.executemany("INSERT OR IGNORE INTO tickets VALUES (?, ?, ?, ?, ?)", rows)
        total += len(rows)
        print(f"  {total:,} rows read ...")

    print("Building full-text index ...")
    conn.execute("INSERT INTO tickets_fts(tickets_fts) VALUES ('rebuild')")
    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
    conn.close()

    os.replace(tmp_path, DB_PATH)   # atomic swap
    print(f"Done — {count:,} unique tickets in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()