"""
app.py
------
FastAPI backend for BugAnalyzer.

Endpoints:
  GET  /health              — health check
  GET  /search              — direct Weaviate search (backward compat)
  POST /analyze             — full 5-agent LangGraph pipeline
  POST /feedback            — store thumbs up/down feedback
  GET  /feedback/summary    — feedback stats for evaluation
  GET  /review/queue        — all escalated bugs awaiting review
  POST /review/{item_id}    — approve or reject a review item

Run from project root:
  uvicorn services.app:app --host 0.0.0.0 --port 8000 --reload
"""

import os
import uuid
import time
from audit_log import log_analysis, read_logs, get_summary_stats, generate_request_id
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import weaviate
import weaviate.classes as wvc
from sentence_transformers import SentenceTransformer

from graph import build_graph

# ── Config ─────────────────────────────────────────────────────────────────────
WEAVIATE_URL    = os.environ.get("WEAVIATE_URL", "")
WEAVIATE_KEY    = os.environ.get("WEAVIATE_KEY", "")
COLLECTION_NAME = "JiraIssues"

# ── In-memory stores (replace with a database in production) ───────────────────
FEEDBACK_LOG : list[dict] = []
REVIEW_QUEUE : list[dict] = []

# ── Load embedding model ────────────────────────────────────────────────────────
print("Loading nomic-embed-text-v1.5 ...")
model = SentenceTransformer(
    "nomic-ai/nomic-embed-text-v1.5",
    trust_remote_code=True
)
print("Model loaded.")

# ── Connect to Weaviate ─────────────────────────────────────────────────────────
print(f"Connecting to Weaviate at {WEAVIATE_URL} ...")
weaviate_client = weaviate.connect_to_weaviate_cloud(
    cluster_url=WEAVIATE_URL,
    auth_credentials=weaviate.auth.AuthApiKey(WEAVIATE_KEY)
)
collection = weaviate_client.collections.get(COLLECTION_NAME)
print(f"Connected. Collection '{COLLECTION_NAME}' ready.")

# ── FastAPI app ──────────────────────────────────────────────────────────────────
app = FastAPI(title="BugAnalyzer Multi-Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8501", "*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Core Weaviate query function ─────────────────────────────────────────────────
def query_weaviate(
    query_text    : str,
    n_results     : int   = 15,
    min_similarity: float = 0.4
) -> list[dict]:
    prefixed_query = "search_query: " + query_text
    query_vector   = model.encode(
        [prefixed_query],
        convert_to_numpy=True
    )[0].tolist()

    results = collection.query.near_vector(
        near_vector=query_vector,
        limit=n_results,
        return_properties=[
            "jira_id", "key", "summary",
            "priority", "resolution", "discussion",
        ],
        return_metadata=wvc.query.MetadataQuery(distance=True)
    )

    issues = []
    for obj in results.objects:
        distance   = obj.metadata.distance
        similarity = 1 / (1 + distance)
        if similarity >= min_similarity:
            p = obj.properties
            issues.append({
                "id"             : p.get("jira_id"),
                "key"            : p.get("key"),
                "summary"        : p.get("summary"),
                # "priority.name"  : p.get("priority"),
                "priority.name"  : p.get("priority") if p.get("priority") not in (None, "nan", "NaN", "") else "Unknown",
                "resolution.name": p.get("resolution"),
                "comments_text"  : p.get("discussion"),
                "similarity"     : round(similarity, 3),
            })

    print(f"Weaviate: '{query_text[:50]}' → {len(results.objects)} retrieved, {len(issues)} passed filter")
    return issues


# ── Build LangGraph ──────────────────────────────────────────────────────────────
print("Building LangGraph agent graph ...")
graph = build_graph(query_weaviate_fn=query_weaviate)
print("Graph ready.")


# ── Request / response models ────────────────────────────────────────────────────
class AnalyzeRequest(BaseModel):
    issue_description : str
    bug_title         : str = ""
    stack_trace       : str = ""
    user_priority     : str = "Major"

class FeedbackRequest(BaseModel):
    bug_title        : str
    vote             : str    # "up" or "down"
    solution_snippet : str = ""

class ReviewDecision(BaseModel):
    status        : str    # "approved" or "rejected"
    reviewer_note : str = ""


# ══════════════════════════════════════════════════════════════════════════════
# ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    """
    Full 5-agent pipeline:
      Classifier + Severity (parallel)
        → Retriever (Weaviate + Cohere Rerank)
          → Draft Response (Claude Sonnet)
            → Escalation (Rules + Groq Llama)
    """
    if not req.issue_description.strip():
        raise HTTPException(status_code=400, detail="issue_description is required")

    print(f"\n{'='*60}")
    print(f"New /analyze: {req.bug_title or req.issue_description[:60]}")
    print(f"{'='*60}")

    request_id = generate_request_id()
    start_time = time.time()

    result = graph.invoke({
        "issue_description": req.issue_description,
        "bug_title"        : req.bug_title,
        "stack_trace"      : req.stack_trace,
        "user_priority"    : req.user_priority,
        "agent_status"     : {},
        "mcp_tool_calls"   : [],
    })

    response_time = time.time() - start_time
    log_analysis(
        request_id         = request_id,
        state              = result,
        response_time_secs = response_time,
        tool_calls_made    = result.get("mcp_tool_calls", [])
    )

    escalation = result.get("escalation_decision", {})
    escalated  = escalation.get("escalate", False)

    # ── Add to review queue if escalated ─────────────────────────────────────
    if escalated:
        review_item = {
            "id"                : str(uuid.uuid4()),
            "bug_title"         : req.bug_title or req.issue_description[:60],
            "issue_description" : req.issue_description,
            "user_priority"     : req.user_priority,
            "draft_response"    : result.get("draft_response", ""),
            "escalation_reasons": escalation.get("reasons", []),
            "severity"          : result.get("severity_assessment", {}).get("severity", "Unknown"),
            "confidence"        : result.get("confidence_score", 0),
            "timestamp"         : datetime.now().isoformat(),
            "status"            : "pending",
            "reviewer_note"     : "",
        }
        REVIEW_QUEUE.append(review_item)
        print(f"[Review Queue] Added: {review_item['bug_title'][:50]}")

    return {
        "request_id"         : request_id,    # ← add this
        "final_response"     : result.get("draft_response", ""),
        "final_response"     : result.get("draft_response", ""),
        "classification"     : result.get("classification", {}),
        "severity_assessment": result.get("severity_assessment", {}),
        "retrieved_issues"   : result.get("retrieved_issues", []),
        "confidence_score"   : result.get("confidence_score", 0.7),
        "escalation_decision": escalation,
        "agent_status"       : result.get("agent_status", {}),
        "escalated"          : escalated,
        "escalation_reasons" : escalation.get("reasons", []),
    }


@app.get("/search")
def search(query: str, n: int = 15):
    """Direct Weaviate search — kept for backward compatibility."""
    if not query.strip():
        raise HTTPException(status_code=400, detail="Missing query parameter")
    return query_weaviate(query_text=query, n_results=n)


@app.get("/health")
def health():
    return {
        "status"    : "ok",
        "weaviate"  : weaviate_client.is_ready(),
        "collection": COLLECTION_NAME,
    }


# ── Feedback endpoints ────────────────────────────────────────────────────────

@app.post("/feedback")
def submit_feedback(req: FeedbackRequest):
    """
    Store thumbs up/down feedback for evaluation.
    Called by FeedbackBar on the results page.
    """
    if req.vote not in ("up", "down"):
        raise HTTPException(status_code=400, detail="vote must be 'up' or 'down'")

    entry = {
        "id"              : str(uuid.uuid4()),
        "bug_title"       : req.bug_title,
        "vote"            : req.vote,
        "solution_snippet": req.solution_snippet,
        "timestamp"       : datetime.now().isoformat(),
    }
    FEEDBACK_LOG.append(entry)
    print(f"[Feedback] {req.vote} — {req.bug_title[:50]}")
    return {"status": "recorded", "id": entry["id"]}


@app.get("/feedback/summary")
def feedback_summary():
    """Feedback stats — useful for evaluation dashboard."""
    total   = len(FEEDBACK_LOG)
    upvotes = sum(1 for f in FEEDBACK_LOG if f["vote"] == "up")
    return {
        "total"        : total,
        "upvotes"      : upvotes,
        "downvotes"    : total - upvotes,
        "approval_rate": round(upvotes / total * 100, 1) if total > 0 else 0,
        "recent"       : FEEDBACK_LOG[-10:],
    }


# ── Review queue endpoints ────────────────────────────────────────────────────

@app.get("/review/queue")
def get_review_queue():
    """Return all items in the human review queue."""
    return REVIEW_QUEUE


@app.post("/review/{item_id}")
def review_decision(item_id: str, decision: ReviewDecision):
    """
    Reviewer approves or rejects an escalated bug's AI analysis.
    """
    if decision.status not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="status must be 'approved' or 'rejected'")

    for item in REVIEW_QUEUE:
        if item["id"] == item_id:
            item["status"]        = decision.status
            item["reviewer_note"] = decision.reviewer_note
            item["reviewed_at"]   = datetime.now().isoformat()
            print(f"[Review] {decision.status} — {item['bug_title'][:50]}")
            return {"status": "updated", "item_id": item_id}

    raise HTTPException(status_code=404, detail="Review item not found")

@app.get("/audit/logs")
def get_audit_logs(limit: int = 50, escalated_only: bool = False):
    logs = read_logs(limit=limit, escalated_only=escalated_only)
    return {"count": len(logs), "logs": logs}

@app.get("/audit/summary")
def get_audit_summary():
    return get_summary_stats()

# ── Shutdown ──────────────────────────────────────────────────────────────────

@app.on_event("shutdown")
def shutdown():
    weaviate_client.close()
    print("Weaviate connection closed.")