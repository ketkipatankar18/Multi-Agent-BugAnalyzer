import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer

df = pd.read_csv("jira_rag.csv")

# ── Character length distribution ─────────────────────────────────────────────
char_lengths = df["embedding_text"].str.len()

print("=== Character Length Distribution ===")
print(f"  Mean   : {char_lengths.mean():.0f} chars")
print(f"  Median : {char_lengths.median():.0f} chars")
print(f"  Std    : {char_lengths.std():.0f} chars")
print(f"  Min    : {char_lengths.min():.0f} chars")
print(f"  Max    : {char_lengths.max():.0f} chars")
print()
print("  Percentiles:")
for p in [25, 50, 75, 90, 95, 99]:
    print(f"    {p}th  : {char_lengths.quantile(p/100):.0f} chars")

# ── Token length distribution (using BGE tokenizer) ───────────────────────────
print("\n=== Token Length Distribution (BGE-base tokenizer) ===")
tokenizer = AutoTokenizer.from_pretrained("BAAI/bge-base-en-v1.5")

# Sample 10k rows for speed — representative enough
sample = df["embedding_text"].dropna().sample(
    min(10000, len(df)), random_state=42
).tolist()

token_lengths = [
    len(tokenizer.encode(text, truncation=False))
    for text in sample
]
token_lengths = np.array(token_lengths)

print(f"  Mean   : {token_lengths.mean():.0f} tokens")
print(f"  Median : {np.median(token_lengths):.0f} tokens")
print(f"  Std    : {token_lengths.std():.0f} tokens")
print()
print("  Percentiles:")
for p in [25, 50, 75, 90, 95, 99]:
    print(f"    {p}th  : {np.percentile(token_lengths, p):.0f} tokens")

# ── How much gets cut at different limits ─────────────────────────────────────
print("\n=== What % of tickets exceed each token limit ===")
for limit in [256, 512, 1024, 2048, 4096, 8192]:
    pct_over = (token_lengths > limit).mean() * 100
    print(f"  > {limit:5d} tokens : {pct_over:.1f}% of tickets truncated")