
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
# LOAD MODEL  (same as SnapChef)
# ══════════════════════════════════════════════════════════════════════════════
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"\nLoading model on {device} ...")
model = SentenceTransformer("all-MiniLM-L6-v2").to(device)

# ══════════════════════════════════════════════════════════════════════════════
# INIT CHROMADB
# ══════════════════════════════════════════════════════════════════════════════
CHROMA_PATH.mkdir(parents=True, exist_ok=True)
chroma_client = chromadb.PersistentClient(path=str(CHROMA_PATH))
collection    = chroma_client.get_or_create_collection(name=COLLECTION_NAME)
print(f"ChromaDB collection '{COLLECTION_NAME}' ready at {CHROMA_PATH}")

df = pd.read_csv(CSV_PATH)

print("\n-- Sanity check query --")
test_query = "NullPointerException when processing HTTP request on Linux"

test_embedding = model.encode([test_query], convert_to_numpy=True)
results = collection.query(
    query_embeddings=test_embedding.tolist(),
    n_results=5,
)

print(f"Query : '{test_query}'")
print("Top 5 matches (IDs):", results["ids"][0])

# Look up summaries from the CSV for a readable check
matched = df[df["id"].astype(str).isin(results["ids"][0])][["id", "key", "summary"]]
print(matched.to_string(index=False))