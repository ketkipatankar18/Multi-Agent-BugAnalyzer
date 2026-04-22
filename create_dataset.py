"""
build_jira_rag_csv.py
---------------------
Builds jira_rag.csv — the single source of truth for the JIRA RAG app.

Flow:
  issues.csv + comments.csv  →  jira_rag.csv

Columns in output
─────────────────
  id               ChromaDB document ID (used to look up rows after retrieval)
  key              JIRA ticket key e.g. PDFBOX-4071  (shown in UI)
  summary          Bug title                          (shown in UI + embedded)
  priority.name    Major / Minor / Blocker etc        (shown in UI + embedded)
  resolution.name  Fixed / Won't Fix etc              (shown in UI only —
                   all rows are "Fixed" so no semantic value in embedding)
  comments_text    Cleaned human discussion           (shown in UI + embedded)
  embedding_text   Final text sent to ChromaDB        (embedded only)

Dropped columns (with reasons)
───────────────────────────────
  labels              → 81 % are empty []  — no signal
  assignee            → anonymized hex IDs — meaningless to LLM
  resolution.id       → internal numeric ID — not human readable
  resolution.description → identical string for every Fixed issue — no signal
  priority.id         → internal numeric ID — not human readable
"""

import re
import pandas as pd
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR      = Path(".")
ISSUES_FILE   = BASE_DIR / "issues.csv"
COMMENTS_FILE = BASE_DIR / "comments.csv"
OUT_FILE      = BASE_DIR / "jira_rag.csv"

# ── Config ─────────────────────────────────────────────────────────────────────
MAX_COMMENT_CHARS = 4000    # cap joined comments to keep embeddings manageable
KEEP_RESOLUTIONS  = ["Fixed"]

# ══════════════════════════════════════════════════════════════════════════════
# 1. LOAD
# ══════════════════════════════════════════════════════════════════════════════
print("Loading CSVs ...")
issues   = pd.read_csv(ISSUES_FILE)
comments = pd.read_csv(COMMENTS_FILE)
print(f"  issues   : {len(issues):,} rows")
print(f"  comments : {len(comments):,} rows")

# ══════════════════════════════════════════════════════════════════════════════
# 2. FILTER — only keep tickets with a real resolution
# ══════════════════════════════════════════════════════════════════════════════
fixed = issues[issues["resolution.name"].isin(KEEP_RESOLUTIONS)].copy()
print(f"\nIssues after resolution filter ({KEEP_RESOLUTIONS}): {len(fixed):,}")

# ══════════════════════════════════════════════════════════════════════════════
# 3. CLEAN COMMENTS
#    3a. Drop entire comment rows that are bot/commit noise
#    3b. Clean the text inside surviving rows
# ══════════════════════════════════════════════════════════════════════════════

# Patterns that mark a comment row as pure noise (entire row is dropped)
NOISE_PATTERNS = [
    r'^commit \d+',                 # SVN commit messages
    r'svn\.apache\.org',            # SVN links
    r'github pull request',         # GitHub bot
    r'^\[~\w+\] committed',         # JIRA commit macro
    r'this issue links to',         # automated link comments
    r'^migrated from',              # migration bots
    r'^https?://\S+$',              # bare URL only
    r'^\s*\+\d+\s*$',              # vote counts like "+1"
    r'^worklog:',                   # worklog entries
]
NOISE_RE = re.compile("|".join(NOISE_PATTERNS), re.IGNORECASE)

def is_noise(text: str) -> bool:
    t = str(text).strip()
    if len(t) < 20:
        return True
    return bool(NOISE_RE.search(t))

def clean_comment_text(text: str) -> str:
    """
    Strip JIRA markup and anonymized identifiers from a comment body.
    Keeps JIRA issue keys (e.g. PDFBOX-4071) because those are meaningful.
    """
    t = str(text)
    # JIRA user mention macros  [~username]
    t = re.sub(r'\[~\w+\]', '', t)
    # Anonymized 8-char hex user IDs like b20375d7, 4d4054ac
    t = re.sub(r'\b[a-f0-9]{8}\b', '', t)
    # Long numeric IDs like 12691823  (7+ digits avoids wiping years/versions)
    t = re.sub(r'\b\d{7,}\b', '', t)
    # Code blocks
    t = re.sub(r'\{code[^}]*\}.*?\{code\}', '[code block]', t, flags=re.DOTALL)
    t = re.sub(r'\{noformat\}.*?\{noformat\}', '[noformat block]', t, flags=re.DOTALL)
    # Collapse URLs to a token (keeps sentence flow readable)
    t = re.sub(r'https?://\S+', '[link]', t)
    # Collapse whitespace / newlines
    t = re.sub(r'\s+', ' ', t)
    return t.strip()


print("\nCleaning comments ...")
before = len(comments)
comments = comments[~comments["comment.body"].apply(is_noise)].copy()
print(f"  Noise rows removed : {before - len(comments):,}")
print(f"  Clean rows kept    : {len(comments):,}")

comments["comment.body"] = comments["comment.body"].apply(clean_comment_text)

# ══════════════════════════════════════════════════════════════════════════════
# 4. AGGREGATE — join all clean comments per issue chronologically
# ══════════════════════════════════════════════════════════════════════════════
comments = comments.sort_values("comment.created")

comments_agg = (
    comments
    .groupby("key")["comment.body"]
    .apply(lambda x: " || ".join(x.astype(str))[:MAX_COMMENT_CHARS])
    .reset_index()
    .rename(columns={"comment.body": "comments_text"})
)
print(f"\nIssues with at least 1 clean comment: {len(comments_agg):,}")

# ══════════════════════════════════════════════════════════════════════════════
# 5. MERGE comments into fixed issues
# ══════════════════════════════════════════════════════════════════════════════
df = fixed.merge(comments_agg, on="key", how="left")
df["comments_text"] = df["comments_text"].fillna("")

# ══════════════════════════════════════════════════════════════════════════════
# 6. BUILD EMBEDDING TEXT
#
#    Fields included (semantic signal):
#      summary      — what the bug is about
#      priority     — severity context (Blocker vs Minor matters for similarity)
#      comments     — reproduction steps, error messages, fix details
#
#    Fields excluded from embedding:
#      resolution.name  — all rows are "Fixed", zero discriminative signal
# ══════════════════════════════════════════════════════════════════════════════
def safe(val) -> str:
    s = str(val).strip()
    return "" if s.lower() in {"nan", "none", "null", "[]", ""} else s

def build_embedding_text(row) -> str:
    parts = {
        "Ticket Summary"    : safe(row.get("summary", "")),
        "Ticket Priority"   : safe(row.get("priority.name", "")),
        "Ticket Resolution and Discussion" : safe(row.get("comments_text", "")),
    }
    return " | ".join(f"{k}: {v}" for k, v in parts.items() if v)

df["embedding_text"] = df.apply(build_embedding_text, axis=1)

# ══════════════════════════════════════════════════════════════════════════════
# 7. SELECT FINAL COLUMNS
#
#  id              → ChromaDB doc ID  (used to look up rows in CSV after retrieval)
#  key             → human-readable ticket key shown in UI
#  summary         → bug title — shown in UI + used in LLM prompt
#  priority.name   → shown in UI + used in LLM prompt
#  resolution.name → shown in UI ("this was Fixed")
#  comments_text   → shown in UI as "how it was resolved" + fed to LLM prompt
#  embedding_text  → fed into ChromaDB only, not shown in UI
# ══════════════════════════════════════════════════════════════════════════════
FINAL_COLS = [
    "id",
    "key",
    "summary",
    "priority.name",
    "resolution.name",
    "comments_text",
    "embedding_text",
]

final_cols = [c for c in FINAL_COLS if c in df.columns]
final_df   = df[final_cols].drop_duplicates(subset=["id"]).copy()

# ══════════════════════════════════════════════════════════════════════════════
# 8. SAVE
# ══════════════════════════════════════════════════════════════════════════════
final_df.to_csv(OUT_FILE, index=False)

print(f"\n  Saved {len(final_df):,} rows  ->  {OUT_FILE}")
print(f"  Columns: {list(final_df.columns)}")

# ── Sanity check ───────────────────────────────────────────────────────────────
print("\n-- Sample row --")
s = final_df.iloc[0]
print(f"  id              : {s['id']}")
print(f"  key             : {s['key']}")
print(f"  summary         : {s['summary']}")
print(f"  priority.name   : {s['priority.name']}")
print(f"  resolution.name : {s['resolution.name']}")
print(f"  comments_text   : {str(s['comments_text'])[:200]} ...")
print(f"  embedding_text  : {str(s['embedding_text'])[:300]} ...")

print("\n-- Stats --")
no_comments = (final_df["comments_text"] == "").sum()
print(f"  Issues WITH comments    : {len(final_df) - no_comments:,}")
print(f"  Issues WITHOUT comments : {no_comments:,}")
print(f"  Avg embedding_text len  : {final_df['embedding_text'].str.len().mean():.0f} chars")
print(f"\n  Priority distribution:")
print(final_df["priority.name"].value_counts().to_string())