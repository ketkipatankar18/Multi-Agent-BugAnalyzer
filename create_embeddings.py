"""
generate_embeddings.py
----------------------
Reads jira_rag.csv, embeds the embedding_text column using
all-MiniLM-L6-v2 (same model as SnapChef), and stores in ChromaDB.

Run AFTER build_jira_rag_csv.py has produced jira_rag.csv.

Usage:
    python generate_embeddings.py
"""

import pandas as pd
import chromadb
import torch
from tqdm import tqdm
from sentence_transformers import SentenceTransformer
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
CSV_PATH    = Path("jira_rag.csv")
CHROMA_PATH = Path("services/ChromaDB/dataset")

# ── Config ─────────────────────────────────────────────────────────────────────
COLLECTION_NAME = "jira_issues"
BATCH_SIZE      = 512

# ══════════════════════════════════════════════════════════════════════════════
# 1. LOAD CSV
# ══════════════════════════════════════════════════════════════════════════════
print("Loading jira_rag.csv ...")
df = pd.read_csv(CSV_PATH)
print(f"  Total rows : {len(df):,}")

# Drop any rows where embedding_text is empty — nothing to embed
df = df[df["embedding_text"].notna() & (df["embedding_text"].str.strip() != "")]
print(f"  Rows with embedding text : {len(df):,}")

embedding_texts = df["embedding_text"].tolist()
ids             = df["id"].astype(str).tolist()   # ChromaDB requires string IDs

# ══════════════════════════════════════════════════════════════════════════════
# 2. LOAD MODEL  (same as SnapChef)
# ══════════════════════════════════════════════════════════════════════════════
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"\nLoading model on {device} ...")
model = SentenceTransformer("all-MiniLM-L6-v2").to(device)

# ══════════════════════════════════════════════════════════════════════════════
# 3. INIT CHROMADB
# ══════════════════════════════════════════════════════════════════════════════
CHROMA_PATH.mkdir(parents=True, exist_ok=True)
chroma_client = chromadb.PersistentClient(path=str(CHROMA_PATH))
collection    = chroma_client.get_or_create_collection(name=COLLECTION_NAME)
print(f"ChromaDB collection '{COLLECTION_NAME}' ready at {CHROMA_PATH}")

# ══════════════════════════════════════════════════════════════════════════════
# 4. EMBED + UPSERT IN BATCHES
# ══════════════════════════════════════════════════════════════════════════════
print(f"\nEmbedding {len(embedding_texts):,} issues in batches of {BATCH_SIZE} ...")

for i in tqdm(range(0, len(embedding_texts), BATCH_SIZE), desc="Embedding"):
    batch_texts = embedding_texts[i : i + BATCH_SIZE]
    batch_ids   = ids[i : i + BATCH_SIZE]

    batch_embeddings = model.encode(
        batch_texts,
        batch_size=BATCH_SIZE,
        device=str(device),
        show_progress_bar=False,
        convert_to_numpy=True,
    )

    collection.upsert(
        documents=batch_texts,
        embeddings=batch_embeddings.tolist(),
        ids=batch_ids,
    )

print(f"\n  Done. {collection.count():,} documents in ChromaDB.")
