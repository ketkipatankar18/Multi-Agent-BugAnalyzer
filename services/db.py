# # """
# # db.py
# # -----
# # SQLite persistence for BugAnalyzer application data.

# # Tables:
# #   analyses      — every /analyze result (one row per request_id)
# #   review_queue  — escalated analyses and their human review decision
# #   feedback      — thumbs up/down per analysis (one vote per analysis, changeable)
# #   users         — reviewer accounts (used by auth in the next batch)

# # Design notes:
# #   - One short-lived connection per operation: simple and thread-safe under
# #     FastAPI's threadpool. Opening a SQLite connection is cheap.
# #   - WAL mode: readers don't block the writer, so the review dashboard stays
# #     responsive while new analyses are being saved.
# #   - Lists/dicts are stored as JSON text and decoded on read.
# #   - All queries use ? placeholders (parameterized) — never string formatting.
# #   - Migration path: the SQL is standard apart from the PRAGMAs, so moving to
# #     PostgreSQL later is mostly a driver change.
# # """

# # import os
# # import json
# # import uuid
# # import sqlite3
# # from contextlib import contextmanager
# # from datetime import datetime, timezone
# # from logger import get_logger
# # log = get_logger(__name__)

# # SCHEMA = """
# # CREATE TABLE IF NOT EXISTS analyses (
# #     id                 TEXT PRIMARY KEY,
# #     created_at         TEXT NOT NULL,
# #     bug_title          TEXT,
# #     issue_description  TEXT NOT NULL,
# #     stack_trace        TEXT,
# #     user_priority      TEXT,
# #     category           TEXT,
# #     component          TEXT,
# #     severity           TEXT,
# #     confidence         REAL,
# #     draft_response     TEXT,
# #     escalated          INTEGER NOT NULL DEFAULT 0,
# #     escalation_reasons TEXT,            -- JSON list
# #     retrieved_issues   TEXT,            -- JSON list
# #     response_time_secs REAL,
# #     client_ip          TEXT
# # );
# # CREATE INDEX IF NOT EXISTS idx_analyses_created ON analyses(created_at);

# # CREATE TABLE IF NOT EXISTS review_queue (
# #     id            TEXT PRIMARY KEY REFERENCES analyses(id) ON DELETE CASCADE,
# #     status        TEXT NOT NULL DEFAULT 'pending'
# #                   CHECK (status IN ('pending', 'approved', 'rejected')),
# #     reviewer_note TEXT DEFAULT '',
# #     reviewed_by   TEXT,
# #     reviewed_at   TEXT,
# #     created_at    TEXT NOT NULL
# # );
# # CREATE INDEX IF NOT EXISTS idx_review_status ON review_queue(status, created_at);

# # CREATE TABLE IF NOT EXISTS feedback (
# #     id               TEXT PRIMARY KEY,
# #     analysis_id      TEXT UNIQUE,       -- one vote per analysis; NULL allowed for legacy calls
# #     vote             TEXT NOT NULL CHECK (vote IN ('up', 'down')),
# #     bug_title        TEXT,
# #     solution_snippet TEXT,
# #     created_at       TEXT NOT NULL
# # );

# # CREATE TABLE IF NOT EXISTS users (
# #     username      TEXT PRIMARY KEY,
# #     password_hash TEXT NOT NULL,
# #     role          TEXT NOT NULL CHECK (role IN ('admin', 'viewer')),
# #     is_active     INTEGER NOT NULL DEFAULT 1,
# #     created_at    TEXT NOT NULL
# # );
# # """


# # def _db_path() -> str:
# #     # Read at call time, so it works regardless of when .env was loaded
# #     return os.environ.get("DB_PATH", "data/buganalyzer.db")


# # def _now() -> str:
# #     return datetime.now(timezone.utc).isoformat()


# # @contextmanager
# # def get_conn():
# #     """Yield a connection; commit on success, roll back on error, always close."""
# #     conn = sqlite3.connect(_db_path(), timeout=10)
# #     conn.row_factory = sqlite3.Row
# #     conn.execute("PRAGMA foreign_keys = ON")
# #     try:
# #         yield conn
# #         conn.commit()
# #     except Exception:
# #         conn.rollback()
# #         raise
# #     finally:
# #         conn.close()


# # def init_db() -> None:
# #     os.makedirs(os.path.dirname(_db_path()) or ".", exist_ok=True)
# #     with get_conn() as conn:
# #         conn.execute("PRAGMA journal_mode = WAL")   # persistent, set once per file
# #         conn.executescript(SCHEMA)
# #     log.info(f"[DB] Ready at {_db_path()}")


# # # ── Analyses ──────────────────────────────────────────────────────────────────

# # def save_analysis(request_id: str, req, result: dict,
# #                   response_time_secs: float, client_ip: str | None = None) -> None:
# #     """
# #     Save one analysis. If escalated, add it to the review queue in the SAME
# #     transaction — an escalated analysis can never exist without its queue row.
# #     """
# #     classification = result.get("classification") or {}
# #     severity       = result.get("severity_assessment") or {}
# #     escalation     = result.get("escalation_decision") or {}
# #     escalated      = bool(escalation.get("escalate"))

# #     with get_conn() as conn:
# #         conn.execute(
# #             """INSERT INTO analyses (
# #                    id, created_at, bug_title, issue_description, stack_trace, user_priority,
# #                    category, component, severity, confidence, draft_response,
# #                    escalated, escalation_reasons, retrieved_issues, response_time_secs, client_ip)
# #                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
# #             (
# #                 request_id, _now(),
# #                 req.bug_title or req.issue_description[:60],
# #                 req.issue_description, req.stack_trace, req.user_priority,
# #                 classification.get("category"), classification.get("component"),
# #                 severity.get("severity"), result.get("confidence_score"),
# #                 result.get("draft_response", ""),
# #                 int(escalated),
# #                 json.dumps(escalation.get("reasons", [])),
# #                 json.dumps(result.get("retrieved_issues", []), default=str),
# #                 round(response_time_secs, 2), client_ip,
# #             ),
# #         )
# #         if escalated:
# #             conn.execute(
# #                 "INSERT INTO review_queue (id, created_at) VALUES (?, ?)",
# #                 (request_id, _now()),
# #             )


# # def count_analyses_today() -> int:
# #     """Analyses since 00:00 UTC — used for the daily cost cap."""
# #     midnight = datetime.now(timezone.utc).replace(
# #         hour=0, minute=0, second=0, microsecond=0
# #     ).isoformat()
# #     with get_conn() as conn:
# #         return conn.execute(
# #             "SELECT COUNT(*) FROM analyses WHERE created_at >= ?", (midnight,)
# #         ).fetchone()[0]


# # def get_analysis_status(analysis_id: str) -> dict | None:
# #     """Public status for the reporter's results page — no internal notes."""
# #     with get_conn() as conn:
# #         row = conn.execute(
# #             """SELECT a.id, a.escalated, r.status AS review_status, r.reviewed_at
# #                FROM analyses a LEFT JOIN review_queue r ON r.id = a.id
# #                WHERE a.id = ?""",
# #             (analysis_id,),
# #         ).fetchone()
# #     if row is None:
# #         return None
# #     return {
# #         "id"           : row["id"],
# #         "escalated"    : bool(row["escalated"]),
# #         "review_status": row["review_status"],   # None if not escalated
# #         "reviewed_at"  : row["reviewed_at"],
# #     }


# # # ── Review queue ──────────────────────────────────────────────────────────────

# # def list_review_queue(limit: int = 200) -> list[dict]:
# #     """Pending first, newest first. Shape matches the frontend ReviewItem type."""
# #     with get_conn() as conn:
# #         rows = conn.execute(
# #             """SELECT a.id, a.bug_title, a.issue_description, a.user_priority,
# #                       a.draft_response, a.escalation_reasons, a.severity, a.confidence,
# #                       r.created_at AS timestamp, r.status, r.reviewer_note,
# #                       r.reviewed_by, r.reviewed_at
# #                FROM review_queue r
# #                JOIN analyses a ON a.id = r.id
# #                ORDER BY (r.status = 'pending') DESC, r.created_at DESC
# #                LIMIT ?""",
# #             (limit,),
# #         ).fetchall()

# #     items = []
# #     for row in rows:
# #         item = dict(row)
# #         item["escalation_reasons"] = json.loads(item["escalation_reasons"] or "[]")
# #         item["confidence"]         = item["confidence"] or 0
# #         item["severity"]           = item["severity"] or "Unknown"
# #         item["reviewer_note"]      = item["reviewer_note"] or ""
# #         items.append(item)
# #     return items


# # def update_review(item_id: str, status: str, reviewer_note: str = "",
# #                   reviewed_by: str | None = None) -> bool:
# #     """Returns False if the item doesn't exist."""
# #     with get_conn() as conn:
# #         cur = conn.execute(
# #             """UPDATE review_queue
# #                SET status = ?, reviewer_note = ?, reviewed_by = ?, reviewed_at = ?
# #                WHERE id = ?""",
# #             (status, reviewer_note, reviewed_by, _now(), item_id),
# #         )
# #         return cur.rowcount > 0


# # # ── Feedback ──────────────────────────────────────────────────────────────────

# # def save_feedback(vote: str, analysis_id: str | None = None,
# #                   bug_title: str = "", solution_snippet: str = "") -> str:
# #     """One vote per analysis — clicking 👍 then 👎 updates the vote, not a second row."""
# #     feedback_id = str(uuid.uuid4())
# #     with get_conn() as conn:
# #         conn.execute(
# #             """INSERT INTO feedback (id, analysis_id, vote, bug_title, solution_snippet, created_at)
# #                VALUES (?, ?, ?, ?, ?, ?)
# #                ON CONFLICT(analysis_id) DO UPDATE SET
# #                    vote = excluded.vote, created_at = excluded.created_at""",
# #             (feedback_id, analysis_id or None, vote, bug_title, solution_snippet, _now()),
# #         )
# #     return feedback_id


# # def feedback_summary(recent: int = 10) -> dict:
# #     with get_conn() as conn:
# #         row     = conn.execute(
# #             "SELECT COUNT(*), COALESCE(SUM(vote = 'up'), 0) FROM feedback"
# #         ).fetchone()
# #         recents = conn.execute(
# #             "SELECT * FROM feedback ORDER BY created_at DESC LIMIT ?", (recent,)
# #         ).fetchall()

# #     total, upvotes = row[0], row[1]
# #     return {
# #         "total"        : total,
# #         "upvotes"      : upvotes,
# #         "downvotes"    : total - upvotes,
# #         "approval_rate": round(upvotes / total * 100, 1) if total else 0,
# #         "recent"       : [dict(r) for r in recents],
# #     }

# # # ── Users ─────────────────────────────────────────────────────────────────────

# # def create_user(username: str, password_hash: str, role: str) -> None:
# #     """Create a user, or reset password/role and reactivate if it exists."""
# #     with get_conn() as conn:
# #         conn.execute(
# #             """INSERT INTO users (username, password_hash, role, is_active, created_at)
# #                VALUES (?, ?, ?, 1, ?)
# #                ON CONFLICT(username) DO UPDATE SET
# #                    password_hash = excluded.password_hash,
# #                    role          = excluded.role,
# #                    is_active     = 1""",
# #             (username, password_hash, role, _now()),
# #         )

# # def get_user(username: str) -> dict | None:
# #     with get_conn() as conn:
# #         row = conn.execute(
# #             "SELECT username, password_hash, role, is_active FROM users WHERE username = ?",
# #             (username,),
# #         ).fetchone()
# #     return dict(row) if row else None

# # def set_user_active(username: str, active: bool) -> bool:
# #     with get_conn() as conn:
# #         cur = conn.execute(
# #             "UPDATE users SET is_active = ? WHERE username = ?",
# #             (int(active), username),
# #         )
# #         return cur.rowcount > 0

# # def list_users() -> list[dict]:
# #     with get_conn() as conn:
# #         rows = conn.execute(
# #             "SELECT username, role, is_active, created_at FROM users ORDER BY created_at"
# #         ).fetchall()
# #     return [dict(r) for r in rows]

# # def get_analysis(analysis_id: str) -> dict | None:
# #     """Bug + draft for the follow-up chat — loaded server-side, never trusted from the client."""
# #     with get_conn() as conn:
# #         row = conn.execute(
# #             """SELECT id, bug_title, issue_description, stack_trace, user_priority, draft_response
# #                FROM analyses WHERE id = ?""",
# #             (analysis_id,),
# #         ).fetchone()
# #     return dict(row) if row else None

# """
# services/db.py — PostgreSQL backend (replaces SQLite)

# Drop-in replacement: every public function keeps its original signature.
# All callers in app.py, auth.py, create_user.py are unchanged.

# Env vars
# --------
# DATABASE_URL  postgresql://user:pass@host:5432/dbname   (required in prod)
#               falls back to   postgresql://localhost/buganalyzer   for local dev
# DB_POOL_MIN   min pool connections  (default 2)
# DB_POOL_MAX   max pool connections  (default 20)
# """

# from __future__ import annotations

# import json
# import os
# import uuid
# from contextlib import contextmanager
# from datetime import datetime, timezone
# from typing import Any

# import psycopg2
# import psycopg2.extras
# from psycopg2.pool import ThreadedConnectionPool

# from logger import get_logger

# log = get_logger(__name__)

# # ---------------------------------------------------------------------------
# # Connection pool
# # ---------------------------------------------------------------------------

# _pool: ThreadedConnectionPool | None = None


# def _get_pool() -> ThreadedConnectionPool:
#     global _pool
#     if _pool is None:
#         dsn = os.environ.get(
#             "DATABASE_URL", "postgresql://localhost/buganalyzer"
#         )
#         minconn = int(os.environ.get("DB_POOL_MIN", "2"))
#         maxconn = int(os.environ.get("DB_POOL_MAX", "20"))
#         _pool = ThreadedConnectionPool(minconn=minconn, maxconn=maxconn, dsn=dsn)
#         log.info(f"[DB] ThreadedConnectionPool created (min={minconn} max={maxconn})")
#     return _pool


# def close_pool() -> None:
#     """Call this during app shutdown (lifespan teardown)."""
#     global _pool
#     if _pool:
#         _pool.closeall()
#         _pool = None
#         log.info("[DB] Connection pool closed")


# @contextmanager
# def get_conn():
#     """Yield a psycopg2 connection, committing on success or rolling back on error."""
#     pool = _get_pool()
#     conn = pool.getconn()
#     try:
#         yield conn
#         conn.commit()
#     except Exception:
#         conn.rollback()
#         raise
#     finally:
#         pool.putconn(conn)


# def _now() -> str:
#     return datetime.now(timezone.utc).isoformat()


# # ---------------------------------------------------------------------------
# # Schema
# # ---------------------------------------------------------------------------

# _SCHEMA: list[str] = [
#     """
#     CREATE TABLE IF NOT EXISTS analyses (
#         id                 TEXT             PRIMARY KEY,
#         created_at         TEXT             NOT NULL,
#         bug_title          TEXT,
#         issue_description  TEXT             NOT NULL,
#         stack_trace        TEXT,
#         user_priority      TEXT,
#         category           TEXT,
#         component          TEXT,
#         severity           TEXT,
#         confidence         DOUBLE PRECISION,
#         draft_response     TEXT,
#         escalated          BOOLEAN          NOT NULL DEFAULT FALSE,
#         escalation_reasons TEXT,
#         retrieved_issues   TEXT,
#         response_time_secs DOUBLE PRECISION,
#         client_ip          TEXT
#     )
#     """,
#     "CREATE INDEX IF NOT EXISTS idx_analyses_created ON analyses(created_at)",
#     """
#     CREATE TABLE IF NOT EXISTS review_queue (
#         id            TEXT PRIMARY KEY REFERENCES analyses(id) ON DELETE CASCADE,
#         status        TEXT NOT NULL DEFAULT 'pending'
#                       CHECK (status IN ('pending', 'approved', 'rejected')),
#         reviewer_note TEXT DEFAULT '',
#         reviewed_by   TEXT,
#         reviewed_at   TEXT,
#         created_at    TEXT NOT NULL
#     )
#     """,
#     "CREATE INDEX IF NOT EXISTS idx_review_status ON review_queue(status, created_at)",
#     """
#     CREATE TABLE IF NOT EXISTS feedback (
#         id               TEXT PRIMARY KEY,
#         analysis_id      TEXT UNIQUE,
#         vote             TEXT NOT NULL CHECK (vote IN ('up', 'down')),
#         bug_title        TEXT,
#         solution_snippet TEXT,
#         created_at       TEXT NOT NULL
#     )
#     """,
#     """
#     CREATE TABLE IF NOT EXISTS users (
#         username      TEXT PRIMARY KEY,
#         password_hash TEXT    NOT NULL,
#         role          TEXT    NOT NULL CHECK (role IN ('admin', 'viewer')),
#         is_active     BOOLEAN NOT NULL DEFAULT TRUE,
#         created_at    TEXT    NOT NULL
#     )
#     """,
# ]


# def init_db() -> None:
#     """Create tables and indexes if they do not already exist."""
#     with get_conn() as conn:
#         with conn.cursor() as cur:
#             for stmt in _SCHEMA:
#                 cur.execute(stmt)
#     log.info("[DB] PostgreSQL schema ready")


# # ---------------------------------------------------------------------------
# # analyses
# # ---------------------------------------------------------------------------

# def save_analysis(
#     request_id: str,
#     req: Any,
#     result: dict,
#     response_time_secs: float,
#     client_ip: str | None = None,
# ) -> None:
#     classification = result.get("classification") or {}
#     severity_info  = result.get("severity_assessment") or {}
#     escalation     = result.get("escalation_decision") or {}
#     escalated      = bool(escalation.get("escalate"))

#     with get_conn() as conn:
#         with conn.cursor() as cur:
#             cur.execute(
#                 """
#                 INSERT INTO analyses (
#                     id, created_at, bug_title, issue_description, stack_trace,
#                     user_priority, category, component, severity, confidence,
#                     draft_response, escalated, escalation_reasons, retrieved_issues,
#                     response_time_secs, client_ip
#                 ) VALUES (
#                     %s, %s, %s, %s, %s,
#                     %s, %s, %s, %s, %s,
#                     %s, %s, %s, %s,
#                     %s, %s
#                 )
#                 """,
#                 (
#                     request_id,
#                     _now(),
#                     req.bug_title or req.issue_description[:60],
#                     req.issue_description,
#                     req.stack_trace,
#                     req.user_priority,
#                     classification.get("category"),
#                     classification.get("component"),
#                     severity_info.get("severity"),
#                     result.get("confidence_score"),
#                     result.get("draft_response", ""),
#                     escalated,
#                     json.dumps(escalation.get("reasons", [])),
#                     json.dumps(result.get("retrieved_issues", []), default=str),
#                     round(response_time_secs, 2),
#                     client_ip,
#                 ),
#             )
#             if escalated:
#                 cur.execute(
#                     "INSERT INTO review_queue (id, created_at) VALUES (%s, %s)",
#                     (request_id, _now()),
#                 )


# def count_analyses_today() -> int:
#     """Count rows created since local UTC midnight."""
#     midnight = (
#         datetime.now(timezone.utc)
#         .replace(hour=0, minute=0, second=0, microsecond=0)
#         .isoformat()
#     )
#     with get_conn() as conn:
#         with conn.cursor() as cur:
#             cur.execute(
#                 "SELECT COUNT(*) FROM analyses WHERE created_at >= %s",
#                 (midnight,),
#             )
#             return cur.fetchone()[0]


# def get_analysis_status(analysis_id: str) -> dict | None:
#     with get_conn() as conn:
#         with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
#             cur.execute(
#                 """
#                 SELECT a.id, a.escalated,
#                        r.status AS review_status, r.reviewed_at
#                 FROM   analyses a
#                 LEFT JOIN review_queue r ON r.id = a.id
#                 WHERE  a.id = %s
#                 """,
#                 (analysis_id,),
#             )
#             row = cur.fetchone()

#     if row is None:
#         return None
#     return {
#         "id"           : row["id"],
#         "escalated"    : bool(row["escalated"]),
#         "review_status": row["review_status"],
#         "reviewed_at"  : row["reviewed_at"],
#     }


# def get_analysis(analysis_id: str) -> dict | None:
#     """Return the raw analysis row (used by /chat endpoint for context)."""
#     with get_conn() as conn:
#         with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
#             cur.execute(
#                 """
#                 SELECT id, bug_title, issue_description, stack_trace,
#                        user_priority, draft_response
#                 FROM   analyses
#                 WHERE  id = %s
#                 """,
#                 (analysis_id,),
#             )
#             row = cur.fetchone()
#     return dict(row) if row else None


# # ---------------------------------------------------------------------------
# # review_queue
# # ---------------------------------------------------------------------------

# def list_review_queue(limit: int = 200) -> list[dict]:
#     with get_conn() as conn:
#         with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
#             cur.execute(
#                 """
#                 SELECT a.id, a.bug_title, a.issue_description, a.user_priority,
#                        a.draft_response, a.escalation_reasons, a.severity, a.confidence,
#                        r.created_at AS timestamp, r.status,
#                        r.reviewer_note, r.reviewed_by, r.reviewed_at
#                 FROM   review_queue r
#                 JOIN   analyses     a ON a.id = r.id
#                 ORDER BY (r.status = 'pending') DESC, r.created_at DESC
#                 LIMIT  %s
#                 """,
#                 (limit,),
#             )
#             rows = cur.fetchall()

#     items = []
#     for row in rows:
#         item = dict(row)
#         item["escalation_reasons"] = json.loads(item["escalation_reasons"] or "[]")
#         item["confidence"]         = item["confidence"] or 0.0
#         item["severity"]           = item["severity"] or "Unknown"
#         item["reviewer_note"]      = item["reviewer_note"] or ""
#         items.append(item)
#     return items


# def update_review(
#     item_id: str,
#     status: str,
#     reviewer_note: str = "",
#     reviewed_by: str | None = None,
# ) -> bool:
#     with get_conn() as conn:
#         with conn.cursor() as cur:
#             cur.execute(
#                 """
#                 UPDATE review_queue
#                 SET    status = %s, reviewer_note = %s,
#                        reviewed_by = %s, reviewed_at = %s
#                 WHERE  id = %s
#                 """,
#                 (status, reviewer_note, reviewed_by, _now(), item_id),
#             )
#             return cur.rowcount > 0


# # ---------------------------------------------------------------------------
# # feedback
# # ---------------------------------------------------------------------------

# def save_feedback(
#     vote: str,
#     analysis_id: str | None = None,
#     bug_title: str = "",
#     solution_snippet: str = "",
# ) -> str:
#     feedback_id = str(uuid.uuid4())
#     with get_conn() as conn:
#         with conn.cursor() as cur:
#             cur.execute(
#                 """
#                 INSERT INTO feedback (id, analysis_id, vote, bug_title, solution_snippet, created_at)
#                 VALUES (%s, %s, %s, %s, %s, %s)
#                 ON CONFLICT (analysis_id) DO UPDATE
#                     SET vote       = EXCLUDED.vote,
#                         created_at = EXCLUDED.created_at
#                 """,
#                 (feedback_id, analysis_id or None, vote, bug_title, solution_snippet, _now()),
#             )
#     return feedback_id


# def feedback_summary(recent: int = 10) -> dict:
#     with get_conn() as conn:
#         with conn.cursor() as cur:
#             cur.execute(
#                 """
#                 SELECT COUNT(*),
#                        COALESCE(SUM(CASE WHEN vote = 'up' THEN 1 ELSE 0 END), 0)
#                 FROM   feedback
#                 """
#             )
#             total_row = cur.fetchone()

#         with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
#             cur.execute(
#                 "SELECT * FROM feedback ORDER BY created_at DESC LIMIT %s",
#                 (recent,),
#             )
#             recents = [dict(r) for r in cur.fetchall()]

#     total   = total_row[0]
#     upvotes = int(total_row[1])
#     return {
#         "total"        : total,
#         "upvotes"      : upvotes,
#         "downvotes"    : total - upvotes,
#         "approval_rate": round(upvotes / total * 100, 1) if total else 0.0,
#         "recent"       : recents,
#     }


# # ---------------------------------------------------------------------------
# # users
# # ---------------------------------------------------------------------------

# def create_user(username: str, password_hash: str, role: str) -> None:
#     with get_conn() as conn:
#         with conn.cursor() as cur:
#             cur.execute(
#                 """
#                 INSERT INTO users (username, password_hash, role, is_active, created_at)
#                 VALUES (%s, %s, %s, TRUE, %s)
#                 ON CONFLICT (username) DO UPDATE
#                     SET password_hash = EXCLUDED.password_hash,
#                         role          = EXCLUDED.role,
#                         is_active     = TRUE
#                 """,
#                 (username, password_hash, role, _now()),
#             )


# def get_user(username: str) -> dict | None:
#     with get_conn() as conn:
#         with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
#             cur.execute(
#                 "SELECT username, password_hash, role, is_active FROM users WHERE username = %s",
#                 (username,),
#             )
#             row = cur.fetchone()
#     return dict(row) if row else None


# def set_user_active(username: str, active: bool) -> bool:
#     with get_conn() as conn:
#         with conn.cursor() as cur:
#             cur.execute(
#                 "UPDATE users SET is_active = %s WHERE username = %s",
#                 (active, username),
#             )
#             return cur.rowcount > 0


# def list_users() -> list[dict]:
#     with get_conn() as conn:
#         with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
#             cur.execute(
#                 "SELECT username, role, is_active, created_at FROM users ORDER BY created_at"
#             )
#             rows = cur.fetchall()
#     return [dict(r) for r in rows]

"""
services/db.py — PostgreSQL backend (replaces SQLite)

Drop-in replacement: every public function keeps its original signature.
All callers in app.py, auth.py, create_user.py are unchanged.

Env vars
--------
DATABASE_URL  postgresql://user:pass@host:5432/dbname   (required in prod)
              falls back to   postgresql://localhost/buganalyzer   for local dev
DB_POOL_MIN   min pool connections  (default 2)
DB_POOL_MAX   max pool connections  (default 20)
"""

from __future__ import annotations

import json
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool

from logger import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Connection pool
# ---------------------------------------------------------------------------

_pool: ThreadedConnectionPool | None = None


def _get_pool() -> ThreadedConnectionPool:
    global _pool
    if _pool is None:
        dsn = os.environ.get(
            "DATABASE_URL", "postgresql://localhost/buganalyzer"
        )
        minconn = int(os.environ.get("DB_POOL_MIN", "2"))
        maxconn = int(os.environ.get("DB_POOL_MAX", "20"))
        _pool = ThreadedConnectionPool(minconn=minconn, maxconn=maxconn, dsn=dsn)
        log.info(f"[DB] ThreadedConnectionPool created (min={minconn} max={maxconn})")
    return _pool


def close_pool() -> None:
    """Call this during app shutdown (lifespan teardown)."""
    global _pool
    if _pool:
        _pool.closeall()
        _pool = None
        log.info("[DB] Connection pool closed")


@contextmanager
def get_conn():
    """Yield a psycopg2 connection, committing on success or rolling back on error."""
    pool = _get_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS analyses (
        id                 TEXT             PRIMARY KEY,
        created_at         TEXT             NOT NULL,
        bug_title          TEXT,
        issue_description  TEXT             NOT NULL,
        stack_trace        TEXT,
        user_priority      TEXT,
        category           TEXT,
        component          TEXT,
        severity           TEXT,
        confidence         DOUBLE PRECISION,
        draft_response     TEXT,
        escalated          BOOLEAN          NOT NULL DEFAULT FALSE,
        escalation_reasons TEXT,
        retrieved_issues   TEXT,
        response_time_secs DOUBLE PRECISION,
        client_ip          TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_analyses_created ON analyses(created_at)",
    """
    CREATE TABLE IF NOT EXISTS review_queue (
        id            TEXT PRIMARY KEY REFERENCES analyses(id) ON DELETE CASCADE,
        status        TEXT NOT NULL DEFAULT 'pending'
                      CHECK (status IN ('pending', 'approved', 'rejected')),
        reviewer_note TEXT DEFAULT '',
        reviewed_by   TEXT,
        reviewed_at   TEXT,
        created_at    TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_review_status ON review_queue(status, created_at)",
    """
    CREATE TABLE IF NOT EXISTS feedback (
        id               TEXT PRIMARY KEY,
        analysis_id      TEXT UNIQUE,
        vote             TEXT NOT NULL CHECK (vote IN ('up', 'down')),
        bug_title        TEXT,
        solution_snippet TEXT,
        created_at       TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS users (
        username      TEXT PRIMARY KEY,
        password_hash TEXT    NOT NULL,
        role          TEXT    NOT NULL CHECK (role IN ('admin', 'viewer')),
        is_active     BOOLEAN NOT NULL DEFAULT TRUE,
        created_at    TEXT    NOT NULL
    )
    """,
]


def init_db() -> None:
    """Create tables and indexes if they do not already exist."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            for stmt in _SCHEMA:
                cur.execute(stmt)
    log.info("[DB] PostgreSQL schema ready")


# ---------------------------------------------------------------------------
# analyses
# ---------------------------------------------------------------------------

def save_analysis(
    request_id: str,
    req: Any,
    result: dict,
    response_time_secs: float,
    client_ip: str | None = None,
) -> None:
    classification = result.get("classification") or {}
    severity_info  = result.get("severity_assessment") or {}
    escalation     = result.get("escalation_decision") or {}
    escalated      = bool(escalation.get("escalate"))

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO analyses (
                    id, created_at, bug_title, issue_description, stack_trace,
                    user_priority, category, component, severity, confidence,
                    draft_response, escalated, escalation_reasons, retrieved_issues,
                    response_time_secs, client_ip
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s
                )
                """,
                (
                    request_id,
                    _now(),
                    req.bug_title or req.issue_description[:60],
                    req.issue_description,
                    req.stack_trace,
                    req.user_priority,
                    classification.get("category"),
                    classification.get("component"),
                    severity_info.get("severity"),
                    result.get("confidence_score"),
                    result.get("draft_response", ""),
                    escalated,
                    json.dumps(escalation.get("reasons", [])),
                    json.dumps(result.get("retrieved_issues", []), default=str),
                    round(response_time_secs, 2),
                    client_ip,
                ),
            )
            if escalated:
                cur.execute(
                    "INSERT INTO review_queue (id, created_at) VALUES (%s, %s)",
                    (request_id, _now()),
                )


def count_analyses_today() -> int:
    """Count rows created since local UTC midnight."""
    midnight = (
        datetime.now(timezone.utc)
        .replace(hour=0, minute=0, second=0, microsecond=0)
        .isoformat()
    )
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM analyses WHERE created_at >= %s",
                (midnight,),
            )
            return cur.fetchone()[0]


def get_analysis_status(analysis_id: str) -> dict | None:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT a.id, a.escalated,
                       r.status AS review_status, r.reviewed_at
                FROM   analyses a
                LEFT JOIN review_queue r ON r.id = a.id
                WHERE  a.id = %s
                """,
                (analysis_id,),
            )
            row = cur.fetchone()

    if row is None:
        return None
    return {
        "id"           : row["id"],
        "escalated"    : bool(row["escalated"]),
        "review_status": row["review_status"],
        "reviewed_at"  : row["reviewed_at"],
    }


def get_analysis(analysis_id: str) -> dict | None:
    """Return the raw analysis row (used by /chat endpoint for context)."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, bug_title, issue_description, stack_trace,
                       user_priority, draft_response
                FROM   analyses
                WHERE  id = %s
                """,
                (analysis_id,),
            )
            row = cur.fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# review_queue
# ---------------------------------------------------------------------------

def list_review_queue(limit: int = 200) -> list[dict]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT a.id, a.bug_title, a.issue_description, a.user_priority,
                       a.draft_response, a.escalation_reasons, a.severity, a.confidence,
                       r.created_at AS timestamp, r.status,
                       r.reviewer_note, r.reviewed_by, r.reviewed_at
                FROM   review_queue r
                JOIN   analyses     a ON a.id = r.id
                ORDER BY (r.status = 'pending') DESC, r.created_at DESC
                LIMIT  %s
                """,
                (limit,),
            )
            rows = cur.fetchall()

    items = []
    for row in rows:
        item = dict(row)
        item["escalation_reasons"] = json.loads(item["escalation_reasons"] or "[]")
        item["confidence"]         = item["confidence"] or 0.0
        item["severity"]           = item["severity"] or "Unknown"
        item["reviewer_note"]      = item["reviewer_note"] or ""
        items.append(item)
    return items


def update_review(
    item_id: str,
    status: str,
    reviewer_note: str = "",
    reviewed_by: str | None = None,
) -> bool:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE review_queue
                SET    status = %s, reviewer_note = %s,
                       reviewed_by = %s, reviewed_at = %s
                WHERE  id = %s
                """,
                (status, reviewer_note, reviewed_by, _now(), item_id),
            )
            return cur.rowcount > 0


# ---------------------------------------------------------------------------
# feedback
# ---------------------------------------------------------------------------

def save_feedback(
    vote: str,
    analysis_id: str | None = None,
    bug_title: str = "",
    solution_snippet: str = "",
) -> str:
    feedback_id = str(uuid.uuid4())
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO feedback (id, analysis_id, vote, bug_title, solution_snippet, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (analysis_id) DO UPDATE
                    SET vote       = EXCLUDED.vote,
                        created_at = EXCLUDED.created_at
                """,
                (feedback_id, analysis_id or None, vote, bug_title, solution_snippet, _now()),
            )
    return feedback_id


def feedback_summary(recent: int = 10) -> dict:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*),
                       COALESCE(SUM(CASE WHEN vote = 'up' THEN 1 ELSE 0 END), 0)
                FROM   feedback
                """
            )
            total_row = cur.fetchone()

        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM feedback ORDER BY created_at DESC LIMIT %s",
                (recent,),
            )
            recents = [dict(r) for r in cur.fetchall()]

    total   = total_row[0]
    upvotes = int(total_row[1])
    return {
        "total"        : total,
        "upvotes"      : upvotes,
        "downvotes"    : total - upvotes,
        "approval_rate": round(upvotes / total * 100, 1) if total else 0.0,
        "recent"       : recents,
    }


# ---------------------------------------------------------------------------
# users
# ---------------------------------------------------------------------------

def create_user(username: str, password_hash: str, role: str) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (username, password_hash, role, is_active, created_at)
                VALUES (%s, %s, %s, TRUE, %s)
                ON CONFLICT (username) DO UPDATE
                    SET password_hash = EXCLUDED.password_hash,
                        role          = EXCLUDED.role,
                        is_active     = TRUE
                """,
                (username, password_hash, role, _now()),
            )


def get_user(username: str) -> dict | None:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT username, password_hash, role, is_active FROM users WHERE username = %s",
                (username,),
            )
            row = cur.fetchone()
    return dict(row) if row else None


def set_user_active(username: str, active: bool) -> bool:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET is_active = %s WHERE username = %s",
                (active, username),
            )
            return cur.rowcount > 0


def list_users() -> list[dict]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT username, role, is_active, created_at FROM users ORDER BY created_at"
            )
            rows = cur.fetchall()
    return [dict(r) for r in rows]


def list_analyses(limit: int = 50) -> list[dict]:
    """Return recent analyses (admin dashboard)."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, created_at, bug_title, category, severity,
                       escalated, response_time_secs, client_ip
                FROM   analyses
                ORDER  BY created_at DESC
                LIMIT  %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
    return [dict(r) for r in rows]