"""
build_jira_rag_csv.py
---------------------
Builds jira_rag.csv and splits into train/eval/demo sets.

Flow:
  issues.csv + comments.csv
    → jira_rag.csv      (full dataset, kept as reference)
    → jira_train.csv    (95% of full — kept for reference)
    → jira_eval.csv     (5%  — never touches Weaviate, used for evaluation)
    → jira_demo.csv     (100k stratified sample — goes into Weaviate free tier)

Why jira_demo.csv:
  Weaviate free tier has a 100,000 object limit.
  100k tickets stratified by priority gives a representative
  subset that fits the free tier and is sufficient for a live demo.

Columns in output
-----------------
  id               Unique row ID
  key              JIRA ticket key e.g. PDFBOX-4071
  summary          Bug title
  priority.name    Major / Minor / Blocker etc
  resolution.name  Fixed
  comments_text    Cleaned human discussion
  embedding_text   Text sent to Weaviate for embedding

Dropped columns (with reasons)
-------------------------------
  labels              81% are empty []  — no signal
  assignee            anonymized hex IDs — meaningless to LLM
  resolution.id       internal numeric ID
  resolution.description  identical for every Fixed issue — no signal
  priority.id         internal numeric ID
"""

import re
import pandas as pd
from pathlib import Path
from sklearn.model_selection import train_test_split

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR      = Path(".")
ISSUES_FILE   = BASE_DIR / "issues.csv"
COMMENTS_FILE = BASE_DIR / "comments.csv"
OUT_FILE      = BASE_DIR / "jira_rag.csv"
TRAIN_FILE    = BASE_DIR / "jira_train.csv"
EVAL_FILE     = BASE_DIR / "jira_eval.csv"
DEMO_FILE     = BASE_DIR / "jira_demo.csv"

# ── Config ─────────────────────────────────────────────────────────────────────
MAX_COMMENT_CHARS = 4000
KEEP_RESOLUTIONS  = ["Fixed"]
EVAL_SIZE         = 0.05       # 5% holdout for evaluation
DEMO_SIZE         = 100_000    # fits Weaviate free tier (100k object limit)
RANDOM_SEED       = 42

# ══════════════════════════════════════════════════════════════════════════════
# 1. LOAD
# ══════════════════════════════════════════════════════════════════════════════
print("Loading CSVs ...")
issues   = pd.read_csv(ISSUES_FILE)
comments = pd.read_csv(COMMENTS_FILE)
print(f"  issues   : {len(issues):,} rows")
print(f"  comments : {len(comments):,} rows")

# ══════════════════════════════════════════════════════════════════════════════
# 2. FILTER — only keep Fixed tickets
# ══════════════════════════════════════════════════════════════════════════════
fixed = issues[issues["resolution.name"].isin(KEEP_RESOLUTIONS)].copy()
print(f"\nFixed issues: {len(fixed):,}")

# ══════════════════════════════════════════════════════════════════════════════
# 3. CLEAN COMMENTS
# ══════════════════════════════════════════════════════════════════════════════
NOISE_PATTERNS = [
    r'^commit \d+',
    r'svn\.apache\.org',
    r'github pull request',
    r'^\[~\w+\] committed',
    r'this issue links to',
    r'^migrated from',
    r'^https?://\S+$',
    r'^\s*\+\d+\s*$',
    r'^worklog:',
]
NOISE_RE = re.compile("|".join(NOISE_PATTERNS), re.IGNORECASE)

def is_noise(text: str) -> bool:
    t = str(text).strip()
    if len(t) < 20:
        return True
    return bool(NOISE_RE.search(t))

def clean_comment_text(text: str) -> str:
    t = str(text)
    t = re.sub(r'\[~\w+\]', '', t)
    t = re.sub(r'\b[a-f0-9]{8}\b', '', t)
    t = re.sub(r'\b\d{7,}\b', '', t)
    t = re.sub(r'\{code[^}]*\}.*?\{code\}', '[code block]', t, flags=re.DOTALL)
    t = re.sub(r'\{noformat\}.*?\{noformat\}', '[noformat block]', t, flags=re.DOTALL)
    t = re.sub(r'https?://\S+', '[link]', t)
    t = re.sub(r'\s+', ' ', t)
    return t.strip()

print("\nCleaning comments ...")
before   = len(comments)
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
# 5. MERGE
# ══════════════════════════════════════════════════════════════════════════════
df = fixed.merge(comments_agg, on="key", how="left")
df["comments_text"] = df["comments_text"].fillna("")

# ══════════════════════════════════════════════════════════════════════════════
# 6. BUILD EMBEDDING TEXT
# ══════════════════════════════════════════════════════════════════════════════
def safe(val) -> str:
    s = str(val).strip()
    return "" if s.lower() in {"nan", "none", "null", "[]", ""} else s

def build_embedding_text(row) -> str:
    parts = {
        "Ticket Summary"                   : safe(row.get("summary", "")),
        "Ticket Priority"                  : safe(row.get("priority.name", "")),
        "Ticket Resolution and Discussion" : safe(row.get("comments_text", "")),
    }
    return " | ".join(f"{k}: {v}" for k, v in parts.items() if v)

df["embedding_text"] = df.apply(build_embedding_text, axis=1)

# ══════════════════════════════════════════════════════════════════════════════
# 7. SELECT FINAL COLUMNS
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
# 8. SAVE FULL DATASET
# ══════════════════════════════════════════════════════════════════════════════
final_df.to_csv(OUT_FILE, index=False)
print(f"\n  Saved full dataset : {len(final_df):,} rows → {OUT_FILE}")

# ══════════════════════════════════════════════════════════════════════════════
# 9. HOLDOUT SPLIT — 95% train / 5% eval
#    jira_eval.csv must NEVER be loaded into Weaviate.
# ══════════════════════════════════════════════════════════════════════════════
print(f"\nSplitting into train ({int((1-EVAL_SIZE)*100)}%) / eval ({int(EVAL_SIZE*100)}%) ...")

train_df, eval_df = train_test_split(
    final_df,
    test_size=EVAL_SIZE,
    random_state=RANDOM_SEED,
    shuffle=True
)

train_df.to_csv(TRAIN_FILE, index=False)
eval_df.to_csv(EVAL_FILE, index=False)

print(f"  Train : {len(train_df):,} rows → {TRAIN_FILE}  (reference, not uploaded)")
print(f"  Eval  : {len(eval_df):,} rows  → {EVAL_FILE}   (never touches Weaviate)")

# ══════════════════════════════════════════════════════════════════════════════
# 10. DEMO SAMPLE — 100k stratified by priority
#     This is what goes into Weaviate free tier (100k object limit).
#     Stratified sampling ensures priority distribution matches the full dataset.
#     Sampled from train_df only — eval rows are excluded.
# ══════════════════════════════════════════════════════════════════════════════
print(f"\nCreating {DEMO_SIZE:,} row demo sample (stratified by priority) ...")

# Some priority values may have too few rows for stratification
# Check minimum class size and reduce if needed
min_class_size = train_df["priority.name"].value_counts().min()
actual_demo_size = min(DEMO_SIZE, len(train_df))

try:
    demo_df, _ = train_test_split(
        train_df,
        train_size=actual_demo_size,
        random_state=RANDOM_SEED,
        stratify=train_df["priority.name"]
    )
except ValueError:
    # Fallback to random sample if stratification fails
    print("  Stratification failed — falling back to random sample")
    demo_df = train_df.sample(n=actual_demo_size, random_state=RANDOM_SEED)

demo_df.to_csv(DEMO_FILE, index=False)
print(f"  Demo  : {len(demo_df):,} rows → {DEMO_FILE}  (upload this to Kaggle)")

# ── Sanity checks ─────────────────────────────────────────────────────────────
print("\n-- Sample demo row --")
s = demo_df.iloc[0]
print(f"  id              : {s['id']}")
print(f"  key             : {s['key']}")
print(f"  summary         : {s['summary']}")
print(f"  priority.name   : {s['priority.name']}")
print(f"  resolution.name : {s['resolution.name']}")
print(f"  comments_text   : {str(s['comments_text'])[:200]} ...")
print(f"  embedding_text  : {str(s['embedding_text'])[:300]} ...")

print("\n-- Stats --")
no_comments = (demo_df["comments_text"] == "").sum()
print(f"  Demo WITH comments    : {len(demo_df) - no_comments:,}")
print(f"  Demo WITHOUT comments : {no_comments:,}")
print(f"  Avg embedding_text len: {demo_df['embedding_text'].str.len().mean():.0f} chars")

print(f"\n  Priority distribution (demo vs full dataset):")
full_pct = final_df["priority.name"].value_counts(normalize=True) * 100
demo_pct = demo_df["priority.name"].value_counts(normalize=True) * 100
comparison = pd.DataFrame({
    "Full dataset %" : full_pct.round(1),
    "Demo sample %"  : demo_pct.round(1)
})
print(comparison.to_string())
print("\n  (Demo % should closely match Full dataset % — confirms stratification worked)")

print(f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Files produced:
    jira_rag.csv    — full {len(final_df):,} rows (reference)
    jira_train.csv  — {len(train_df):,} rows (reference)
    jira_eval.csv   — {len(eval_df):,} rows (evaluation — never upload)
    jira_demo.csv   — {len(demo_df):,} rows (upload this to Kaggle)

  Next step:
    Upload jira_demo.csv to Kaggle as a dataset
    then run create_embeddings_weaviate.ipynb
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")