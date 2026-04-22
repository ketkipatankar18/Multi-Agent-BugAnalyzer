import os

# os.environ["OMP_NUM_THREADS"] = "1"
# os.environ["MKL_NUM_THREADS"] = "1"
# os.environ["OPENBLAS_NUM_THREADS"] = "1"
# os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
# os.environ["TOKENIZERS_PARALLELISM"] = "false"
# os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

from flask import Flask, request, jsonify
import pandas as pd
import chromadb
# from sentence_transformers import SentenceTransformer

app = Flask(__name__)

# Load once (IMPORTANT FIX)
# model = SentenceTransformer("all-MiniLM-L6-v2")

# def get_model():
#     import threading
#     global model

#     if "model" not in globals():
#         model = SentenceTransformer("all-MiniLM-L6-v2")
#     return model

csv_path = "services/ChromaDB/jira_rag_embedded.csv"
JIRA_DF = pd.read_csv(csv_path)
JIRA_DF['id'] = JIRA_DF['id'].astype(int)

chroma_client = chromadb.PersistentClient(
    path="services/ChromaDB/dataset"
)
collection = chroma_client.get_collection("jira_issues")
# chroma_client = chromadb.HttpClient(
#     host="localhost",
#     port=8001
# )

# collection = chroma_client.get_or_create_collection(name="jira_issues")

# def query_chroma(query_texts, n_results=15, min_similarity=0.7):
#     # query_embedding = model.encode([query_text])
#     # model = get_model()
#     # query_embedding = model.encode([query_text])

#     results = collection.query(
#         # query_embeddings=query_embedding.tolist(),
#         query_texts=query_texts,
#         n_results=n_results,
#         include=["distances"]
#     )

#     # ids       = [int(i) for i in results['ids'][0]]
#     ids = [int(float(i)) for i in results['ids'][0]]
#     distances = results['distances'][0]
#     similarities = [1 / (1 + d) for d in distances]

#     filtered_ids = [
#         id_ for id_, sim in zip(ids, similarities)
#         if sim >= min_similarity
#     ]

#     # print(f"Retrieved: {len(ids)} | After filter: {len(filtered_ids)}")

#     if not filtered_ids:
#         return []

#     matched_df = JIRA_DF[JIRA_DF['id'].isin(filtered_ids)]
#     return matched_df.to_dict(orient="records")

def query_chroma(query_texts, n_results=10):
    # Embed the query
    # query_embedding = model.encode([query_text])
 
    # Query ChromaDB for similar issue IDs
    results = collection.query(
        query_texts=query_texts,
        # query_embeddings=query_embedding,
        n_results=n_results
    )
 
    # Flatten and convert IDs to int
    # ids = [int(i) for i in results['ids'][0]]
    ids = [int(float(i)) for i in results['ids'][0]]
    print("Retrieved IDs:", ids)
 
    # Look up full issue details from CSV
    matched_df = JIRA_DF[JIRA_DF['id'].isin(ids)]
 
    return matched_df.to_dict(orient="records")

@app.route('/search', methods=['GET'])
def search():
    query_text = request.args.get('query')
    n_results  = int(request.args.get('n', 15))

    if not query_text:
        return jsonify({"error": "Missing 'query' parameter"}), 400

    issues = query_chroma(query_text, n_results)
    return jsonify(issues)

if __name__ == '__main__':
    # app.run(host='0.0.0.0', port=8000, debug=True)
    # app.run(host='0.0.0.0', port=8000, use_reloader=False)
    app.run(host='0.0.0.0', port=8000, use_reloader=False, threaded=False, processes=1)