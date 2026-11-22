# # # """
# # # app.py
# # # ------
# # # FastAPI backend for BugAnalyzer.

# # # Endpoints:
# # #   GET  /health              — health check
# # #   GET  /search              — direct Weaviate search (backward compat)
# # #   POST /analyze             — full 5-agent LangGraph pipeline
# # #   POST /feedback            — store thumbs up/down feedback
# # #   GET  /feedback/summary    — feedback stats for evaluation
# # #   GET  /review/queue        — all escalated bugs awaiting review
# # #   POST /review/{item_id}    — approve or reject a review item

# # # Run from project root:
# # #   uvicorn services.app:app --host 0.0.0.0 --port 8000 --reload
# # # """

# # # import os
# # # import uuid
# # # import time
# # # from audit_log import log_analysis, read_logs, get_summary_stats, generate_request_id
# # # from datetime import datetime
# # # from dotenv import load_dotenv
# # # load_dotenv()

# # # from fastapi import FastAPI, HTTPException
# # # from fastapi.middleware.cors import CORSMiddleware
# # # from pydantic import BaseModel
# # # import weaviate
# # # import weaviate.classes as wvc
# # # from sentence_transformers import SentenceTransformer

# # # from graph import build_graph

# # # # ── Config ─────────────────────────────────────────────────────────────────────
# # # WEAVIATE_URL    = os.environ.get("WEAVIATE_URL", "")
# # # WEAVIATE_KEY    = os.environ.get("WEAVIATE_KEY", "")
# # # COLLECTION_NAME = "JiraIssues"

# # # # ── In-memory stores (replace with a database in production) ───────────────────
# # # FEEDBACK_LOG : list[dict] = []
# # # REVIEW_QUEUE : list[dict] = []

# # # # ── Load embedding model ────────────────────────────────────────────────────────
# # # log.info("Loading nomic-embed-text-v1.5 ...")
# # # model = SentenceTransformer(
# # #     "nomic-ai/nomic-embed-text-v1.5",
# # #     trust_remote_code=True
# # # )
# # # log.info("Model loaded.")

# # # # ── Connect to Weaviate ─────────────────────────────────────────────────────────
# # # log.info(f"Connecting to Weaviate at {WEAVIATE_URL} ...")
# # # weaviate_client = weaviate.connect_to_weaviate_cloud(
# # #     cluster_url=WEAVIATE_URL,
# # #     auth_credentials=weaviate.auth.AuthApiKey(WEAVIATE_KEY)
# # # )
# # # collection = weaviate_client.collections.get(COLLECTION_NAME)
# # # log.info(f"Connected. Collection '{COLLECTION_NAME}' ready.")

# # # # ── FastAPI app ──────────────────────────────────────────────────────────────────
# # # app = FastAPI(title="BugAnalyzer Multi-Agent API")

# # # app.add_middleware(
# # #     CORSMiddleware,
# # #     allow_origins=["http://localhost:3000", "http://localhost:8501", "*"],
# # #     allow_methods=["*"],
# # #     allow_headers=["*"],
# # # )

# # # # ── Core Weaviate query function ─────────────────────────────────────────────────
# # # def query_weaviate(
# # #     query_text    : str,
# # #     n_results     : int   = 15,
# # #     min_similarity: float = 0.4
# # # ) -> list[dict]:
# # #     prefixed_query = "search_query: " + query_text
# # #     query_vector   = model.encode(
# # #         [prefixed_query],
# # #         convert_to_numpy=True
# # #     )[0].tolist()

# # #     results = collection.query.near_vector(
# # #         near_vector=query_vector,
# # #         limit=n_results,
# # #         return_properties=[
# # #             "jira_id", "key", "summary",
# # #             "priority", "resolution", "discussion",
# # #         ],
# # #         return_metadata=wvc.query.MetadataQuery(distance=True)
# # #     )

# # #     issues = []
# # #     for obj in results.objects:
# # #         distance   = obj.metadata.distance
# # #         similarity = 1 / (1 + distance)
# # #         if similarity >= min_similarity:
# # #             p = obj.properties
# # #             issues.append({
# # #                 "id"             : p.get("jira_id"),
# # #                 "key"            : p.get("key"),
# # #                 "summary"        : p.get("summary"),
# # #                 # "priority.name"  : p.get("priority"),
# # #                 "priority.name"  : p.get("priority") if p.get("priority") not in (None, "nan", "NaN", "") else "Unknown",
# # #                 "resolution.name": p.get("resolution"),
# # #                 "comments_text"  : p.get("discussion"),
# # #                 "similarity"     : round(similarity, 3),
# # #             })

# # #     log.info(f"Weaviate: '{query_text[:50]}' → {len(results.objects)} retrieved, {len(issues)} passed filter")
# # #     return issues


# # # # ── Build LangGraph ──────────────────────────────────────────────────────────────
# # # log.info("Building LangGraph agent graph ...")
# # # graph = build_graph(query_weaviate_fn=query_weaviate)
# # # log.info("Graph ready.")


# # # # ── Request / response models ────────────────────────────────────────────────────
# # # class AnalyzeRequest(BaseModel):
# # #     issue_description : str
# # #     bug_title         : str = ""
# # #     stack_trace       : str = ""
# # #     user_priority     : str = "Major"

# # # class FeedbackRequest(BaseModel):
# # #     bug_title        : str
# # #     vote             : str    # "up" or "down"
# # #     solution_snippet : str = ""

# # # class ReviewDecision(BaseModel):
# # #     status        : str    # "approved" or "rejected"
# # #     reviewer_note : str = ""


# # # # ══════════════════════════════════════════════════════════════════════════════
# # # # ROUTES
# # # # ══════════════════════════════════════════════════════════════════════════════

# # # @app.post("/analyze")
# # # def analyze(req: AnalyzeRequest):
# # #     """
# # #     Full 5-agent pipeline:
# # #       Classifier + Severity (parallel)
# # #         → Retriever (Weaviate + Cohere Rerank)
# # #           → Draft Response (Claude Sonnet)
# # #             → Escalation (Rules + Groq Llama)
# # #     """
# # #     if not req.issue_description.strip():
# # #         raise HTTPException(status_code=400, detail="issue_description is required")

# # #     log.info(f"\n{'='*60}")
# # #     log.info(f"New /analyze: {req.bug_title or req.issue_description[:60]}")
# # #     log.info(f"{'='*60}")

# # #     request_id = generate_request_id()
# # #     start_time = time.time()

# # #     result = graph.invoke({
# # #         "request_id"       : request_id,
# # #         "issue_description": req.issue_description,
# # #         "bug_title"        : req.bug_title,
# # #         "stack_trace"      : req.stack_trace,
# # #         "user_priority"    : req.user_priority,
# # #         "agent_status"     : {},
# # #         "mcp_tool_calls"   : [],
# # #         "mcp_tool_inputs"  : [],
# # #         "agent_timings"    : {},
# # #     })

# # #     response_time = time.time() - start_time
# # #     log_analysis(
# # #         request_id         = request_id,
# # #         state              = result,
# # #         response_time_secs = response_time,
# # #         # tool_calls_made    = result.get("mcp_tool_calls", [])
# # #         tool_calls_made    = result.get("mcp_tool_calls", []),
# # #         tool_inputs_log    = result.get("mcp_tool_inputs", []),
# # #     )

# # #     escalation = result.get("escalation_decision", {})
# # #     escalated  = escalation.get("escalate", False)

# # #     # ── Add to review queue if escalated ─────────────────────────────────────
# # #     if escalated:
# # #         review_item = {
# # #             # "id"                : str(uuid.uuid4()),
# # #             # "bug_title"         : req.bug_title or req.issue_description[:60],
# # #             "id"                : request_id,
# # #             "bug_title"         : req.bug_title or req.issue_description[:60],
# # #             "issue_description" : req.issue_description,
# # #             "user_priority"     : req.user_priority,
# # #             "draft_response"    : result.get("draft_response", ""),
# # #             "escalation_reasons": escalation.get("reasons", []),
# # #             "severity"          : result.get("severity_assessment", {}).get("severity", "Unknown"),
# # #             "confidence"        : result.get("confidence_score", 0),
# # #             "timestamp"         : datetime.now().isoformat(),
# # #             "status"            : "pending",
# # #             "reviewer_note"     : "",
# # #         }
# # #         REVIEW_QUEUE.append(review_item)
# # #         log.info(f"[Review Queue] Added: {review_item['bug_title'][:50]}")

# # #     return {
# # #         "request_id"         : request_id, 
# # #         "final_response"     : result.get("draft_response", ""),
# # #         "classification"     : result.get("classification", {}),
# # #         "severity_assessment": result.get("severity_assessment", {}),
# # #         "retrieved_issues"   : result.get("retrieved_issues", []),
# # #         "confidence_score"   : result.get("confidence_score", 0.7),
# # #         "escalation_decision": escalation,
# # #         "agent_status"       : result.get("agent_status", {}),
# # #         "escalated"          : escalated,
# # #         "escalation_reasons" : escalation.get("reasons", []),
# # #     }


# # # @app.get("/search")
# # # def search(query: str, n: int = 15):
# # #     """Direct Weaviate search — kept for backward compatibility."""
# # #     if not query.strip():
# # #         raise HTTPException(status_code=400, detail="Missing query parameter")
# # #     return query_weaviate(query_text=query, n_results=n)


# # # @app.get("/health")
# # # def health():
# # #     return {
# # #         "status"    : "ok",
# # #         "weaviate"  : weaviate_client.is_ready(),
# # #         "collection": COLLECTION_NAME,
# # #     }


# # # # ── Feedback endpoints ────────────────────────────────────────────────────────

# # # @app.post("/feedback")
# # # def submit_feedback(req: FeedbackRequest):
# # #     """
# # #     Store thumbs up/down feedback for evaluation.
# # #     Called by FeedbackBar on the results page.
# # #     """
# # #     if req.vote not in ("up", "down"):
# # #         raise HTTPException(status_code=400, detail="vote must be 'up' or 'down'")

# # #     entry = {
# # #         "id"              : str(uuid.uuid4()),
# # #         "bug_title"       : req.bug_title,
# # #         "vote"            : req.vote,
# # #         "solution_snippet": req.solution_snippet,
# # #         "timestamp"       : datetime.now().isoformat(),
# # #     }
# # #     FEEDBACK_LOG.append(entry)
# # #     log.info(f"[Feedback] {req.vote} — {req.bug_title[:50]}")
# # #     return {"status": "recorded", "id": entry["id"]}


# # # @app.get("/feedback/summary")
# # # def feedback_summary():
# # #     """Feedback stats — useful for evaluation dashboard."""
# # #     total   = len(FEEDBACK_LOG)
# # #     upvotes = sum(1 for f in FEEDBACK_LOG if f["vote"] == "up")
# # #     return {
# # #         "total"        : total,
# # #         "upvotes"      : upvotes,
# # #         "downvotes"    : total - upvotes,
# # #         "approval_rate": round(upvotes / total * 100, 1) if total > 0 else 0,
# # #         "recent"       : FEEDBACK_LOG[-10:],
# # #     }


# # # # ── Review queue endpoints ────────────────────────────────────────────────────

# # # @app.get("/review/queue")
# # # def get_review_queue():
# # #     """Return all items in the human review queue."""
# # #     return REVIEW_QUEUE


# # # @app.post("/review/{item_id}")
# # # def review_decision(item_id: str, decision: ReviewDecision):
# # #     """
# # #     Reviewer approves or rejects an escalated bug's AI analysis.
# # #     """
# # #     if decision.status not in ("approved", "rejected"):
# # #         raise HTTPException(status_code=400, detail="status must be 'approved' or 'rejected'")

# # #     for item in REVIEW_QUEUE:
# # #         if item["id"] == item_id:
# # #             item["status"]        = decision.status
# # #             item["reviewer_note"] = decision.reviewer_note
# # #             item["reviewed_at"]   = datetime.now().isoformat()
# # #             log.info(f"[Review] {decision.status} — {item['bug_title'][:50]}")
# # #             return {"status": "updated", "item_id": item_id}

# # #     raise HTTPException(status_code=404, detail="Review item not found")

# # # @app.get("/audit/logs")
# # # def get_audit_logs(limit: int = 50, escalated_only: bool = False):
# # #     logs = read_logs(limit=limit, escalated_only=escalated_only)
# # #     return {"count": len(logs), "logs": logs}

# # # @app.get("/audit/summary")
# # # def get_audit_summary():
# # #     return get_summary_stats()

# # # # ── Shutdown ──────────────────────────────────────────────────────────────────

# # # @app.on_event("shutdown")
# # # def shutdown():
# # #     weaviate_client.close()
# # #     log.info("Weaviate connection closed.")

# # """
# # app.py
# # ------
# # FastAPI backend for BugAnalyzer.

# # Endpoints:
# #   GET  /health                     — health check
# #   GET  /search                     — direct Weaviate search (backward compat)
# #   POST /analyze                    — start an analysis job → {job_id} (202)
# #   GET  /jobs/{id}/stream           — live progress + result (Server-Sent Events)
# #   GET  /analysis/{id}/status       — review status for the reporter
# #   POST /feedback                   — thumbs up/down (one vote per analysis)
# #   GET  /feedback/summary           — feedback stats for evaluation
# #   GET  /review/queue               — escalated analyses (pending first)
# #   POST /review/{item_id}           — approve or reject a review item
# #   GET  /audit/logs                 — recent audit records
# #   GET  /audit/summary              — aggregate audit stats
# #   POST /auth/login                 — log in (sets session cookie)
# #   POST /auth/logout                — log out
# #   GET  /auth/me                    — current user

# # Run from services/:
# #   uvicorn app:app --host 0.0.0.0 --port 8000 --reload
# # """

# # import os
# # import time
# # import json
# # import asyncio
# # from fastapi.responses import StreamingResponse
# # import jobs
# # from contextlib import asynccontextmanager

# # # Load .env BEFORE importing local modules — some read env vars at import time
# # from dotenv import load_dotenv
# # load_dotenv()

# # from fastapi import Depends, FastAPI, HTTPException, Request, Response
# # from fastapi.middleware.cors import CORSMiddleware
# # from pydantic import BaseModel
# # import weaviate
# # import weaviate.classes as wvc
# # from sentence_transformers import SentenceTransformer

# # from typing import Literal
# # from fastapi.responses import JSONResponse
# # from pydantic import Field
# # from slowapi import Limiter
# # from slowapi.errors import RateLimitExceeded
# # from slowapi.util import get_remote_address
# # from resilience import with_retry

# # import db
# # from auth import (
# #     authenticate, issue_session, clear_session,
# #     get_optional_user, get_current_user, require_role,
# # )
# # from graph import build_graph
# # from audit_log import log_analysis, log_failure, read_logs, get_summary_stats, generate_request_id
# # from logger import get_logger, set_request_id, request_id_var
# # from agents import get_gemini, get_claude

# # log = get_logger(__name__)

# # # ── Config ─────────────────────────────────────────────────────────────────────
# # WEAVIATE_URL         = os.environ.get("WEAVIATE_URL", "")
# # WEAVIATE_KEY         = os.environ.get("WEAVIATE_KEY", "")
# # COLLECTION_NAME      = "JiraIssues"
# # MAX_ANALYSES_PER_DAY = int(os.environ.get("MAX_ANALYSES_PER_DAY", "300"))
# # FRONTEND_ORIGINS  = [o.strip() for o in os.environ.get("FRONTEND_ORIGINS", "http://localhost:3000").split(",") if o.strip()]
# # PUBLIC_DEMO_QUEUE = os.environ.get("PUBLIC_DEMO_QUEUE", "false").lower() == "true"
# # ANALYZE_RATE_LIMIT = os.environ.get("ANALYZE_RATE_LIMIT", "5/minute;30/hour")
# # LOGIN_RATE_LIMIT   = os.environ.get("LOGIN_RATE_LIMIT", "5/minute")
# # CHAT_RATE_LIMIT    = os.environ.get("CHAT_RATE_LIMIT", "10/minute")
# # MAX_CHAT_TURNS     = int(os.environ.get("MAX_CHAT_TURNS", "10"))

# # # ── Database ───────────────────────────────────────────────────────────────────
# # db.init_db()

# # # ── Load embedding model ────────────────────────────────────────────────────────
# # log.info("Loading nomic-embed-text-v1.5 ...")
# # model = SentenceTransformer(
# #     "nomic-ai/nomic-embed-text-v1.5",
# #     trust_remote_code=True
# # )
# # log.info("Model loaded.")

# # # ── Connect to Weaviate ─────────────────────────────────────────────────────────
# # log.info(f"Connecting to Weaviate at {WEAVIATE_URL} ...")
# # weaviate_client = weaviate.connect_to_weaviate_cloud(
# #     cluster_url=WEAVIATE_URL,
# #     auth_credentials=weaviate.auth.AuthApiKey(WEAVIATE_KEY)
# # )
# # collection = weaviate_client.collections.get(COLLECTION_NAME)
# # log.info(f"Connected. Collection '{COLLECTION_NAME}' ready.")


# # # ── Core Weaviate query function ─────────────────────────────────────────────────
# # def query_weaviate(
# #     query_text    : str,
# #     n_results     : int   = 15,
# #     min_similarity: float = 0.4
# # ) -> list[dict]:
# #     prefixed_query = "search_query: " + query_text
# #     query_vector   = model.encode(
# #         [prefixed_query],
# #         convert_to_numpy=True
# #     )[0].tolist()

# #     results = collection.query.near_vector(
# #         near_vector=query_vector,
# #         limit=n_results,
# #         return_properties=[
# #             "jira_id", "key", "summary",
# #             "priority", "resolution", "discussion",
# #         ],
# #         return_metadata=wvc.query.MetadataQuery(distance=True)
# #     )

# #     issues = []
# #     for obj in results.objects:
# #         distance   = obj.metadata.distance
# #         similarity = 1 / (1 + distance)
# #         if similarity >= min_similarity:
# #             p        = obj.properties
# #             priority = p.get("priority")
# #             issues.append({
# #                 "id"             : p.get("jira_id"),
# #                 "key"            : p.get("key"),
# #                 "summary"        : p.get("summary"),
# #                 "priority.name"  : priority if priority not in (None, "nan", "NaN", "") else "Unknown",
# #                 "resolution.name": p.get("resolution"),
# #                 "comments_text"  : p.get("discussion"),
# #                 "similarity"     : round(similarity, 3),
# #             })

# #     log.info(f"Weaviate: '{query_text[:50]}' → {len(results.objects)} retrieved, {len(issues)} passed filter")
# #     return issues


# # # ── Build LangGraph ──────────────────────────────────────────────────────────────
# # log.info("Building LangGraph agent graph ...")
# # graph = build_graph(query_weaviate_fn=query_weaviate)
# # log.info("Graph ready.")

# # # ── Warm up LLM clients ────────────────────────────────────────────────────────
# # # The first call to a provider pays connection + auth setup.
# # # Do it once at startup so no user request pays it.
# # from agents import get_gemini
# # try:
# #     get_gemini().invoke("Reply with OK")
# #     log.info("Gemini warmed up.")
# # except Exception as e:
# #     log.warning(f"Gemini warm-up failed (non-fatal): {e}")


# # # ── App lifecycle ──────────────────────────────────────────────────────────────
# # @asynccontextmanager
# # async def lifespan(app: FastAPI):
# #     yield                                  # app runs here
# #     jobs.shutdown()                        # on shutdown: stop the worker pool
# #     weaviate_client.close()
# #     log.info("Weaviate connection closed.")


# # # ── FastAPI app ──────────────────────────────────────────────────────────────────
# # app = FastAPI(title="BugAnalyzer Multi-Agent API", lifespan=lifespan)

# # # # NOTE: tightened to explicit origins + credentials in the auth batch
# # # app.add_middleware(
# # #     CORSMiddleware,
# # #     allow_origins=["http://localhost:3000", "http://localhost:8501", "*"],
# # #     allow_methods=["*"],
# # #     allow_headers=["*"],
# # # )

# # app.add_middleware(
# #     CORSMiddleware,
# #     allow_origins    = FRONTEND_ORIGINS,
# #     allow_credentials= True,             # lets the browser send the session cookie
# #     allow_methods    = ["GET", "POST"],
# #     allow_headers    = ["Content-Type"],
# # )

# # # ── Rate limiting (per client IP, in memory — fine for a single server) ───────
# # limiter = Limiter(key_func=get_remote_address)
# # app.state.limiter = limiter

# # @app.exception_handler(RateLimitExceeded)
# # async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
# #     log.warning(f"[RateLimit] {get_remote_address(request)} exceeded {exc.detail} on {request.url.path}")
# #     return JSONResponse(
# #         status_code=429,
# #         content={"detail": "Too many requests — please wait a minute and try again."},
# #         headers={"Retry-After": "60"},
# #     )

# # # ── Request models ───────────────────────────────────────────────────────────────
# # class AnalyzeRequest(BaseModel):
# #     issue_description : str
# #     bug_title         : str = ""
# #     stack_trace       : str = ""
# #     user_priority     : str = "Major"

# # class FeedbackRequest(BaseModel):
# #     bug_title        : str
# #     vote             : str    # "up" or "down"
# #     solution_snippet : str = ""
# #     analysis_id      : str = ""

# # class ReviewDecision(BaseModel):
# #     status        : str    # "approved" or "rejected"
# #     reviewer_note : str = ""

# # class LoginRequest(BaseModel):
# #     username : str
# #     password : str

# # class ChatMessage(BaseModel):
# #     role   : Literal["user", "assistant"]
# #     content: str = Field(min_length=1, max_length=4000)

# # class ChatRequest(BaseModel):
# #     analysis_id: str
# #     messages   : list[ChatMessage] = Field(min_length=1)

# # # ══════════════════════════════════════════════════════════════════════════════
# # # ROUTES
# # # ══════════════════════════════════════════════════════════════════════════════
# # # ── Auth ──────────────────────────────────────────────────────────────────────

# # @app.post("/auth/login")
# # @limiter.limit(LOGIN_RATE_LIMIT)
# # # def login(req: LoginRequest, response: Response):
# # def login(req: LoginRequest, request: Request, response: Response):
# #     user = authenticate(req.username, req.password)
# #     if user is None:
# #         log.warning(f"[Auth] Failed login for '{req.username[:40]}'")
# #         raise HTTPException(status_code=401, detail="Invalid username or password")
# #     issue_session(response, user)
# #     log.info(f"[Auth] {user['username']} logged in ({user['role']})")
# #     return {"username": user["username"], "role": user["role"]}

# # @app.post("/auth/logout")
# # def logout(response: Response):
# #     clear_session(response)
# #     return {"status": "ok"}

# # @app.get("/auth/me")
# # def me(user: dict = Depends(get_current_user)):
# #     return user

# # # @app.post("/analyze")
# # # @limiter.limit(ANALYZE_RATE_LIMIT)
# # # def analyze(req: AnalyzeRequest, request: Request):
# # #     """
# # #     Full 5-agent pipeline:
# # #       Classifier + Severity (parallel)
# # #         → Retriever (Weaviate + Cohere Rerank)
# # #           → Draft Response (Claude Sonnet)
# # #             → Escalation (Rules + Slack + Jira)
# # #     """
# # #     if not req.issue_description.strip():
# # #         raise HTTPException(status_code=400, detail="issue_description is required")

# # #     if db.count_analyses_today() >= MAX_ANALYSES_PER_DAY:
# # #         raise HTTPException(
# # #             status_code=429,
# # #             detail="Daily demo limit reached — please try again tomorrow."
# # #         )

# # #     # request_id = generate_request_id()
# # #     # start_time = time.time()

# # #     # log.info(f"\n{'='*60}")
# # #     # log.info(f"New /analyze [{request_id[:8]}]: {req.bug_title or req.issue_description[:60]}")
# # #     # log.info(f"{'='*60}")

# # #     # try:
# # #     #     result = graph.invoke({
# # #     request_id = generate_request_id()
# # #     start_time = time.time()
# # #     token      = set_request_id(request_id)

# # #     log.info(f"New /analyze: {req.bug_title or req.issue_description[:60]}")

# # #     try:
# # #         result = graph.invoke({
# # #             "request_id"       : request_id,
# # #             "issue_description": req.issue_description,
# # #             "bug_title"        : req.bug_title,
# # #             "stack_trace"      : req.stack_trace,
# # #             "user_priority"    : req.user_priority,
# # #             "agent_status"     : {},
# # #             "mcp_tool_calls"   : [],
# # #             "mcp_tool_inputs"  : [],
# # #             "agent_timings"    : {},
# # #         })
# # #     # except Exception as e:
# # #     #     log.info(f"[Analyze] PIPELINE FAILED [{request_id[:8]}]: {type(e).__name__}: {e}")
# # #     #     raise HTTPException(
# # #     #         status_code=500,
# # #     #         detail="Analysis failed unexpectedly. Please try again."
# # #     #     )
# # #     except Exception as e:
# # #         log.exception(f"[Analyze] PIPELINE FAILED: {type(e).__name__}: {e}")  # includes traceback
# # #         log_failure(
# # #             request_id         = request_id,
# # #             inputs             = req.model_dump(),
# # #             error              = f"{type(e).__name__}: {e}",
# # #             response_time_secs = time.time() - start_time,
# # #         )
# # #         request_id_var.reset(token)
# # #         raise HTTPException(
# # #             status_code=500,
# # #             detail="Analysis failed unexpectedly. Please try again."
# # #         )

# # #     response_time = time.time() - start_time

# # #     log_analysis(
# # #         request_id         = request_id,
# # #         state              = result,
# # #         response_time_secs = response_time,
# # #         tool_calls_made    = result.get("mcp_tool_calls", []),
# # #         tool_inputs_log    = result.get("mcp_tool_inputs", []),
# # #     )

# # #     escalation = result.get("escalation_decision", {})
# # #     escalated  = escalation.get("escalate", False)

# # #     # ── Persist analysis (+ review queue row if escalated, same transaction) ──
# # #     try:
# # #         db.save_analysis(
# # #             request_id, req, result, response_time,
# # #             client_ip=request.client.host if request.client else None,
# # #         )
# # #         if escalated:
# # #             log.info(f"[Review Queue] Added: {(req.bug_title or req.issue_description)[:50]}")
# # #     except Exception as e:
# # #         log.error(f"[DB] ERROR saving analysis {request_id}: {e}")
# # #     request_id_var.reset(token)
# # #     return {
# # #         "request_id"         : request_id,
# # #         "final_response"     : result.get("draft_response", ""),
# # #         "classification"     : result.get("classification", {}),
# # #         "severity_assessment": result.get("severity_assessment", {}),
# # #         "retrieved_issues"   : result.get("retrieved_issues", []),
# # #         "confidence_score"   : result.get("confidence_score", 0.7),
# # #         "escalation_decision": escalation,
# # #         "agent_status"       : result.get("agent_status", {}),
# # #         "escalated"          : escalated,
# # #         "escalation_reasons" : escalation.get("reasons", []),
# # #     }

# # def _run_pipeline(job_id: str, req: AnalyzeRequest, client_ip: str | None) -> bool:
# #     """Runs on a worker thread. Emits a final 'result' or 'error' event."""
# #     token      = set_request_id(job_id)
# #     start_time = time.time()
# #     log.info(f"Analysis started: {req.bug_title or req.issue_description[:60]}")
# #     try:
# #         try:
# #             result = graph.invoke({
# #                 "request_id"       : job_id,
# #                 "issue_description": req.issue_description,
# #                 "bug_title"        : req.bug_title,
# #                 "stack_trace"      : req.stack_trace,
# #                 "user_priority"    : req.user_priority,
# #                 "agent_status"     : {},
# #                 "mcp_tool_calls"   : [],
# #                 "mcp_tool_inputs"  : [],
# #                 "agent_timings"    : {},
# #             })
# #         except Exception as e:
# #             log.exception(f"[Analyze] PIPELINE FAILED: {type(e).__name__}: {e}")
# #             log_failure(
# #                 request_id         = job_id,
# #                 inputs             = req.model_dump(),
# #                 error              = f"{type(e).__name__}: {e}",
# #                 response_time_secs = time.time() - start_time,
# #             )
# #             jobs.emit(job_id, "error", {"detail": "Analysis failed unexpectedly. Please try again."})
# #             return False

# #         response_time = time.time() - start_time
# #         log_analysis(
# #             request_id         = job_id,
# #             state              = result,
# #             response_time_secs = response_time,
# #             tool_calls_made    = result.get("mcp_tool_calls", []),
# #             tool_inputs_log    = result.get("mcp_tool_inputs", []),
# #         )

# #         escalation = result.get("escalation_decision", {})
# #         escalated  = escalation.get("escalate", False)

# #         try:
# #             db.save_analysis(job_id, req, result, response_time, client_ip=client_ip)
# #             if escalated:
# #                 log.info(f"[Review Queue] Added: {(req.bug_title or req.issue_description)[:50]}")
# #         except Exception as e:
# #             log.error(f"[DB] ERROR saving analysis {job_id}: {e}")

# #         jobs.emit(job_id, "result", {
# #             "request_id"         : job_id,
# #             "final_response"     : result.get("draft_response", ""),
# #             "classification"     : result.get("classification", {}),
# #             "severity_assessment": result.get("severity_assessment", {}),
# #             "retrieved_issues"   : result.get("retrieved_issues", []),
# #             "confidence_score"   : result.get("confidence_score", 0.7),
# #             "escalation_decision": escalation,
# #             "escalated"          : escalated,
# #             "escalation_reasons" : escalation.get("reasons", []),
# #             "agent_timings"      : result.get("agent_timings", {}),
# #             "response_time_secs" : round(response_time, 2),
# #         })
# #         return True
# #     finally:
# #         request_id_var.reset(token)


# # @app.post("/analyze", status_code=202)
# # @limiter.limit(ANALYZE_RATE_LIMIT)
# # def analyze(req: AnalyzeRequest, request: Request):
# #     """
# #     Start a 5-agent analysis in the background. Returns immediately with a job_id;
# #     progress and the result stream from GET /jobs/{job_id}/stream.
# #     """
# #     if not req.issue_description.strip():
# #         raise HTTPException(status_code=400, detail="issue_description is required")

# #     if db.count_analyses_today() >= MAX_ANALYSES_PER_DAY:
# #         raise HTTPException(status_code=429, detail="Daily demo limit reached — please try again tomorrow.")

# #     if jobs.pending_count() >= jobs.JOB_MAX_PENDING:
# #         raise HTTPException(status_code=503, detail="The server is busy right now — please try again in a minute.")

# #     job_id    = generate_request_id()
# #     client_ip = request.client.host if request.client else None
# #     jobs.create_job(job_id)
# #     jobs.submit(job_id, _run_pipeline, job_id, req, client_ip)
# #     log.info(f"[Jobs] Queued {job_id[:8]} (pending: {jobs.pending_count()})")
# #     return {"job_id": job_id, "stream_url": f"/jobs/{job_id}/stream"}


# # @app.get("/jobs/{job_id}/stream")
# # async def stream_job(job_id: str, request: Request):
# #     """
# #     Server-Sent Events: replays every past event for this job, then streams new
# #     ones live until the job finishes. Supports reconnect via Last-Event-ID.
# #     """
# #     job = jobs.get_job(job_id)
# #     if job is None:
# #         raise HTTPException(status_code=404, detail="Job not found or expired")

# #     last_id = request.headers.get("last-event-id", "")
# #     start   = int(last_id) + 1 if last_id.isdigit() else 0

# #     async def event_stream():
# #         index     = start
# #         last_sent = time.monotonic()
# #         while True:
# #             if await request.is_disconnected():
# #                 break
# #             finished   = job.status in ("done", "failed")   # read BEFORE fetching events
# #             new_events = jobs.events_since(job, index)
# #             for ev in new_events:
# #                 yield f"id: {ev['id']}\nevent: {ev['event']}\ndata: {json.dumps(ev['data'], default=str)}\n\n"
# #             index += len(new_events)
# #             if new_events:
# #                 last_sent = time.monotonic()
# #             if finished and not new_events:
# #                 break                                       # everything delivered
# #             if time.monotonic() - last_sent > 15:
# #                 yield ": keep-alive\n\n"                    # stops proxies closing idle streams
# #                 last_sent = time.monotonic()
# #             await asyncio.sleep(0.1)

# #     return StreamingResponse(
# #         event_stream(),
# #         media_type="text/event-stream",
# #         headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
# #     )

# # @app.get("/search")
# # def search(query: str, n: int = 15):
# #     """Direct Weaviate search — kept for backward compatibility."""
# #     if not query.strip():
# #         raise HTTPException(status_code=400, detail="Missing query parameter")
# #     return query_weaviate(query_text=query, n_results=n)


# # @app.get("/health")
# # def health():
# #     return {
# #         "status"    : "ok",
# #         "weaviate"  : weaviate_client.is_ready(),
# #         "collection": COLLECTION_NAME,
# #     }


# # # ── Reporter-facing status ────────────────────────────────────────────────────

# # @app.get("/analysis/{analysis_id}/status")
# # def analysis_status(analysis_id: str):
# #     """Lets the results page show whether a reviewer approved or rejected it."""
# #     status = db.get_analysis_status(analysis_id)
# #     if status is None:
# #         raise HTTPException(status_code=404, detail="Analysis not found")
# #     return status

# # # ── Follow-up chat ────────────────────────────────────────────────────────────

# # CHAT_SYSTEM_PROMPT = (
# #     "You are an expert QA engineer helping a developer resolve a software bug. "
# #     "Answer follow-up questions about this bug and your earlier analysis. "
# #     "Be concise and technical. If a question is unrelated to this bug or to "
# #     "software engineering, politely decline."
# # )

# # @app.post("/chat")
# # @limiter.limit(CHAT_RATE_LIMIT)
# # def chat(req: ChatRequest, request: Request):
# #     """Follow-up questions about one analysis. Context is loaded from the DB."""
# #     analysis = db.get_analysis(req.analysis_id)
# #     if analysis is None:
# #         raise HTTPException(status_code=404, detail="Analysis not found")

# #     turns = [m.model_dump() for m in req.messages]
# #     user_turns = sum(1 for t in turns if t["role"] == "user")
# #     if user_turns > MAX_CHAT_TURNS:
# #         raise HTTPException(
# #             status_code=400,
# #             detail=f"Follow-up limit reached ({MAX_CHAT_TURNS} questions per analysis). Start a new search to continue."
# #         )
# #     alternates = all(turns[i]["role"] != turns[i + 1]["role"] for i in range(len(turns) - 1))
# #     if turns[0]["role"] != "user" or turns[-1]["role"] != "user" or not alternates:
# #         raise HTTPException(status_code=400, detail="Messages must alternate, starting and ending with the user.")

# #     token = set_request_id(req.analysis_id)
# #     try:
# #         context = (
# #             f"Bug title: {analysis['bug_title']}\n"
# #             f"Description: {analysis['issue_description']}\n"
# #             f"Stack trace: {analysis['stack_trace'] or 'Not provided'}\n"
# #             f"Claimed priority: {analysis['user_priority']}\n\n"
# #             f"Your earlier analysis:\n{analysis['draft_response']}"
# #         )
# #         response = with_retry(
# #             "claude.chat", get_claude().messages.create,
# #             model      = "claude-sonnet-4-6",
# #             max_tokens = 1024,
# #             system     = CHAT_SYSTEM_PROMPT,
# #             messages   = [
# #                 {"role": "user",      "content": context},
# #                 {"role": "assistant", "content": "Understood — I have the bug and my analysis. What would you like to know?"},
# #                 *turns,
# #             ],
# #         )
# #         reply = "".join(b.text for b in response.content if hasattr(b, "text"))
# #         log.info(f"[Chat] question {user_turns}/{MAX_CHAT_TURNS} answered — out={response.usage.output_tokens} tokens")
# #         return {"reply": reply}
# #     except HTTPException:
# #         raise
# #     except Exception as e:
# #         log.error(f"[Chat] failed — {type(e).__name__}: {e}")
# #         raise HTTPException(status_code=502, detail="The assistant is unavailable right now. Please try again.")
# #     finally:
# #         request_id_var.reset(token)

# # # ── Feedback endpoints ────────────────────────────────────────────────────────

# # @app.post("/feedback")
# # def submit_feedback(req: FeedbackRequest):
# #     """Store thumbs up/down. One vote per analysis; a second click updates it."""
# #     if req.vote not in ("up", "down"):
# #         raise HTTPException(status_code=400, detail="vote must be 'up' or 'down'")
# #     feedback_id = db.save_feedback(
# #         vote             = req.vote,
# #         analysis_id      = req.analysis_id or None,
# #         bug_title        = req.bug_title,
# #         solution_snippet = req.solution_snippet,
# #     )
# #     log.info(f"[Feedback] {req.vote} — {req.bug_title[:50]}")
# #     return {"status": "recorded", "id": feedback_id}

# # @app.get("/feedback/summary")
# # def feedback_summary(user: dict = Depends(require_role("admin"))):
# #     """Feedback stats — admin only."""
# #     return db.feedback_summary()


# # # ── Review queue ──────────────────────────────────────────────────────────────

# # SECURITY_REASONS = {"security_issue", "security_keywords_detected"}

# # def _redact_for_demo(items: list[dict]) -> list[dict]:
# #     """Public demo view: no security bugs, no AI drafts, truncated descriptions."""
# #     redacted = []
# #     for item in items:
# #         if SECURITY_REASONS & set(item["escalation_reasons"]):
# #             continue
# #         desc = item["issue_description"] or ""
# #         redacted.append({
# #             **item,
# #             "issue_description": desc[:140] + ("…" if len(desc) > 140 else ""),
# #             "draft_response"   : "",
# #             "reviewer_note"    : "",
# #             "reviewed_by"      : None,
# #         })
# #     return redacted


# # @app.get("/review/queue")
# # def get_review_queue(user: dict | None = Depends(get_optional_user)):
# #     """
# #     Logged in (admin or viewer) → full queue.
# #     Logged out + PUBLIC_DEMO_QUEUE=true → read-only, redacted queue.
# #     Logged out otherwise → 401.
# #     """
# #     if user:
# #         return {"mode": "full", "user": user, "items": db.list_review_queue()}
# #     if PUBLIC_DEMO_QUEUE:
# #         return {"mode": "demo", "user": None, "items": _redact_for_demo(db.list_review_queue())}
# #     raise HTTPException(status_code=401, detail="Not authenticated")


# # @app.post("/review/{item_id}")
# # def review_decision(item_id: str, decision: ReviewDecision,
# #                     user: dict = Depends(require_role("admin"))):
# #     """Approve or reject an escalated analysis — admin only."""
# #     set_request_id(item_id)
# #     if decision.status not in ("approved", "rejected"):
# #         raise HTTPException(status_code=400, detail="status must be 'approved' or 'rejected'")
# #     if not db.update_review(item_id, decision.status, decision.reviewer_note,
# #                             reviewed_by=user["username"]):
# #         raise HTTPException(status_code=404, detail="Review item not found")
# #     log.info(f"[Review] {decision.status} by {user['username']} — {item_id}")
# #     return {"status": "updated", "item_id": item_id}


# # # ── Audit endpoints (admin only — contain user-submitted bug reports) ─────────

# # @app.get("/audit/logs")
# # def get_audit_logs(limit: int = 50, escalated_only: bool = False,
# #                    user: dict = Depends(require_role("admin"))):
# #     logs = read_logs(limit=limit, escalated_only=escalated_only)
# #     return {"count": len(logs), "logs": logs}


# # @app.get("/audit/summary")
# # def get_audit_summary(user: dict = Depends(require_role("admin"))):
# #     return get_summary_stats()

# """
# BugAnalyzer — FastAPI application
# ==================================
# Production-ready multi-agent bug analysis API.

# Architecture
# ------------
# POST /analyze           → enqueues job, returns job_id immediately
# GET  /jobs/{id}/stream  → SSE stream: poll Redis LIST until done/failed

# Storage
# -------
# • PostgreSQL (db.py)  — analyses, review_queue, feedback, users
# • Redis     (jobs.py) — running-job state & SSE event lists

# Auth
# ----
# JWT stored in httpOnly cookie (auth.py).
# Roles: admin (full access) | viewer (read-only, no review actions)
# """

# from __future__ import annotations

# import asyncio
# import json
# import logging
# import os
# import time
# import uuid
# from contextlib import asynccontextmanager
# from concurrent.futures import ThreadPoolExecutor
# from typing import Any, Optional

# from dotenv import load_dotenv
# from fastapi import (
#     Cookie,
#     Depends,
#     FastAPI,
#     HTTPException,
#     Request,
#     Response,
#     status,
# )
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.responses import JSONResponse, StreamingResponse
# from pydantic import BaseModel, Field
# from slowapi import Limiter, _rate_limit_exceeded_handler
# from slowapi.errors import RateLimitExceeded
# from slowapi.util import get_remote_address

# load_dotenv()

# # ── Local modules ─────────────────────────────────────────────────────────────
# import db
# import jobs
# from audit_log import generate_request_id, log_analysis, read_logs, get_summary_stats
# from auth import (
#     COOKIE_NAME,
#     SESSION_HOURS,
#     authenticate,
#     issue_session,
#     clear_session,
#     get_current_user,
#     require_role,
#     verify_password,
# )
# from graph import build_graph

# # Optional Kafka producer — imported lazily so the app starts without Kafka
# try:
#     from kafka_producer import publish_analysis_event

#     _KAFKA_ENABLED = True
# except ImportError:
#     _KAFKA_ENABLED = False
#     publish_analysis_event = None  # type: ignore[assignment]

# # ── Logging ───────────────────────────────────────────────────────────────────
# logging.basicConfig(
#     level=logging.INFO,
#     format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
# )
# logger = logging.getLogger("buganalyzer.app")

# # ── Config ────────────────────────────────────────────────────────────────────
# MAX_ANALYSES_PER_DAY = int(os.getenv("MAX_ANALYSES_PER_DAY", "300"))
# MAX_CHAT_TURNS = int(os.getenv("MAX_CHAT_TURNS", "10"))
# JOB_WORKERS = int(os.getenv("JOB_WORKERS", "8"))
# FRONTEND_ORIGINS = [
#     o.strip()
#     for o in os.getenv("FRONTEND_ORIGINS", "http://localhost:3000").split(",")
#     if o.strip()
# ]

# # ── Thread pool for blocking LangGraph calls ──────────────────────────────────
# _executor = ThreadPoolExecutor(max_workers=JOB_WORKERS, thread_name_prefix="bg-worker")

# # ── Rate limiter ──────────────────────────────────────────────────────────────
# limiter = Limiter(key_func=get_remote_address)

# ANALYZE_RATE = os.getenv("ANALYZE_RATE_LIMIT", "5/minute")
# LOGIN_RATE = os.getenv("LOGIN_RATE_LIMIT", "5/minute")
# CHAT_RATE = os.getenv("CHAT_RATE_LIMIT", "10/minute")


# # ─────────────────────────────────────────────────────────────────────────────
# # Lifespan — startup / shutdown
# # ─────────────────────────────────────────────────────────────────────────────

# @asynccontextmanager
# async def lifespan(app: FastAPI):  # noqa: ANN001
#     # ── Startup ──────────────────────────────────────────────────────────────
#     logger.info("Starting BugAnalyzer API…")

#     # 1. PostgreSQL — create tables if they don't exist
#     db.init_db()
#     logger.info("PostgreSQL ready")

#     # 2. Redis — verify connection
#     jobs.init()
#     logger.info("Redis job queue ready")

#     # 3. LangGraph pipeline — compile once and cache
#     app.state.graph = build_graph()
#     logger.info("LangGraph pipeline compiled")

#     yield

#     # ── Shutdown ─────────────────────────────────────────────────────────────
#     logger.info("Shutting down…")
#     jobs.shutdown()
#     db.close_pool()
#     _executor.shutdown(wait=False)
#     logger.info("Shutdown complete")


# # ─────────────────────────────────────────────────────────────────────────────
# # FastAPI app
# # ─────────────────────────────────────────────────────────────────────────────

# app = FastAPI(
#     title="BugAnalyzer API",
#     version="2.0.0",
#     description="Multi-agent AI system for intelligent bug triage and resolution.",
#     lifespan=lifespan,
# )

# app.state.limiter = limiter
# app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=FRONTEND_ORIGINS,
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )


# # Auth dependencies re-exported from auth.py for use in route signatures
# # get_current_user  → raises 401 if no valid session cookie
# # require_role(...) → raises 403 if user doesn't have one of the given roles


# # ─────────────────────────────────────────────────────────────────────────────
# # Request / Response schemas
# # ─────────────────────────────────────────────────────────────────────────────

# class AnalyzeRequest(BaseModel):
#     bug_title: str = Field(..., min_length=3, max_length=200)
#     issue_description: str = Field(..., min_length=10, max_length=8000)
#     stack_trace: Optional[str] = Field(default=None, max_length=16000)
#     user_priority: str = Field(default="medium", pattern="^(low|medium|high|critical)$")


# class JobResponse(BaseModel):
#     job_id: str
#     status: str
#     message: str


# class FeedbackRequest(BaseModel):
#     vote: str = Field(..., pattern="^(up|down)$")
#     analysis_id: Optional[str] = None
#     bug_title: Optional[str] = ""
#     solution_snippet: Optional[str] = ""


# class ChatRequest(BaseModel):
#     message: str = Field(..., min_length=1, max_length=2000)


# class ReviewUpdateRequest(BaseModel):
#     status: str = Field(..., pattern="^(approved|rejected)$")
#     reviewer_note: Optional[str] = ""


# class LoginRequest(BaseModel):
#     username: str
#     password: str


# # ─────────────────────────────────────────────────────────────────────────────
# # Background worker — runs LangGraph pipeline in thread pool
# # ─────────────────────────────────────────────────────────────────────────────

# def _run_pipeline(job_id: str, req: AnalyzeRequest, client_ip: Optional[str]) -> None:
#     """
#     Blocking function executed in ThreadPoolExecutor.
#     Emits SSE-style events to Redis; stores result in PostgreSQL.
#     """
#     start = time.time()
#     try:
#         jobs.emit(job_id, "status", {"message": "Classifying bug…"})

#         graph = app.state.graph  # compiled in lifespan
#         result = graph.invoke(
#             {
#                 "bug_title": req.bug_title,
#                 "issue_description": req.issue_description,
#                 "stack_trace": req.stack_trace or "",
#                 "user_priority": req.user_priority,
#             }
#         )

#         elapsed = round(time.time() - start, 2)

#         # ── Persist to PostgreSQL ─────────────────────────────────────────
#         analysis_id = job_id  # reuse job ID as analysis ID for simplicity
#         db.save_analysis(analysis_id, req, result, elapsed, client_ip)

#         # ── Audit log (JSONL file) ────────────────────────────────────────
#         log_analysis(
#             request_id=analysis_id,
#             bug_title=req.bug_title,
#             category=result.get("category", "unknown"),
#             severity=result.get("severity", "unknown"),
#             escalated=result.get("escalated", False),
#             response_time=elapsed,
#         )

#         # ── Kafka event ───────────────────────────────────────────────────
#         if _KAFKA_ENABLED and publish_analysis_event is not None:
#             try:
#                 publish_analysis_event(
#                     analysis_id=analysis_id,
#                     category=result.get("category", "unknown"),
#                     severity=result.get("severity", "unknown"),
#                     escalated=result.get("escalated", False),
#                     response_time_secs=elapsed,
#                 )
#             except Exception as kafka_err:
#                 logger.warning("Kafka publish failed (non-fatal): %s", kafka_err)

#         # ── Emit final result to SSE stream ───────────────────────────────
#         jobs.emit(
#             job_id,
#             "result",
#             {
#                 "analysis_id": analysis_id,
#                 "category": result.get("category"),
#                 "component": result.get("component"),
#                 "severity": result.get("severity"),
#                 "confidence": result.get("confidence"),
#                 "draft_response": result.get("draft_response"),
#                 "escalated": result.get("escalated", False),
#                 "escalation_reasons": result.get("escalation_reasons", []),
#                 "retrieved_issues": result.get("retrieved_issues", [])[:5],
#                 "response_time_secs": elapsed,
#             },
#         )

#         # Mark job done
#         job = jobs.RedisJob(job_id)
#         job.status = "done"
#         logger.info("Job %s completed in %.2fs", job_id, elapsed)

#     except Exception as exc:
#         logger.exception("Pipeline failed for job %s", job_id)
#         jobs.emit(job_id, "error", {"message": str(exc)})
#         job = jobs.RedisJob(job_id)
#         job.status = "failed"


# # ─────────────────────────────────────────────────────────────────────────────
# # Routes
# # ─────────────────────────────────────────────────────────────────────────────

# # ── Health ────────────────────────────────────────────────────────────────────

# @app.get("/health", tags=["meta"])
# async def health():
#     return {
#         "status": "ok",
#         "kafka": _KAFKA_ENABLED,
#         "analyses_today": db.count_analyses_today(),
#     }


# # ── Auth ──────────────────────────────────────────────────────────────────────

# @app.post("/auth/login", tags=["auth"])
# @limiter.limit(LOGIN_RATE)
# async def login(request: Request, body: LoginRequest, response: Response):
#     user = authenticate(body.username, body.password)
#     if not user:
#         raise HTTPException(status_code=401, detail="Invalid username or password")
#     issue_session(response, user)
#     return {"username": user["username"], "role": user["role"]}


# @app.post("/auth/logout", tags=["auth"])
# async def logout(response: Response):
#     clear_session(response)
#     return {"message": "Logged out"}


# @app.get("/auth/me", tags=["auth"])
# async def me(user: dict = Depends(get_current_user)):
#     return {"username": user["username"], "role": user["role"]}


# # ── Analysis — async job pattern ──────────────────────────────────────────────

# @app.post("/analyze", response_model=JobResponse, tags=["analysis"])
# @limiter.limit(ANALYZE_RATE)
# async def analyze(
#     request: Request,
#     body: AnalyzeRequest,
#     user: dict = Depends(get_current_user),
# ):
#     # Daily quota check
#     today_count = db.count_analyses_today()
#     if today_count >= MAX_ANALYSES_PER_DAY:
#         raise HTTPException(
#             status_code=429,
#             detail=f"Daily analysis limit ({MAX_ANALYSES_PER_DAY}) reached. Try again tomorrow.",
#         )

#     # Create job in Redis
#     job = jobs.create_job()
#     client_ip = request.client.host if request.client else None

#     # Submit to thread pool (non-blocking)
#     _executor.submit(_run_pipeline, job.id, body, client_ip)

#     return JobResponse(
#         job_id=job.id,
#         status="queued",
#         message="Analysis started. Connect to the stream endpoint for live updates.",
#     )


# @app.get("/jobs/{job_id}/stream", tags=["analysis"])
# async def stream_job(
#     job_id: str,
#     user: dict = Depends(get_current_user),
# ):
#     """
#     Server-Sent Events stream for a running analysis job.

#     The client connects and receives events until it gets a 'result' or 'error'
#     event, at which point the stream ends. Events are stored in a Redis LIST,
#     so the client can reconnect and resume from where it left off using the
#     Last-Event-ID header (not implemented on this endpoint yet — the client
#     simply replays from index 0 which is fast because events are tiny).
#     """

#     async def event_generator():
#         index = 0
#         terminal_seen = False

#         while not terminal_seen:
#             # Fetch events from Redis
#             batch = jobs.events_since(jobs.RedisJob(job_id), index)
#             for evt in batch:
#                 index = evt["id"] + 1
#                 event_type = evt.get("event", "message")
#                 data = json.dumps(evt.get("data", {}))
#                 yield f"id: {evt['id']}\nevent: {event_type}\ndata: {data}\n\n"
#                 if event_type in ("result", "error"):
#                     terminal_seen = True
#                     break

#             if not terminal_seen:
#                 # Check job status — avoid infinite loop if Redis TTL expired
#                 job = jobs.RedisJob(job_id)
#                 if job.status in ("done", "failed", "unknown"):
#                     if not batch:
#                         # No events and job is done — something went wrong
#                         yield f'event: error\ndata: {{"message":"Job state lost"}}\n\n'
#                         break
#                     # Events already sent above, just break
#                     break

#                 await asyncio.sleep(0.1)

#     return StreamingResponse(
#         event_generator(),
#         media_type="text/event-stream",
#         headers={
#             "Cache-Control": "no-cache",
#             "X-Accel-Buffering": "no",  # disable nginx buffering
#         },
#     )


# @app.get("/analyses/{analysis_id}", tags=["analysis"])
# async def get_analysis(analysis_id: str, user: dict = Depends(get_current_user)):
#     row = db.get_analysis(analysis_id)
#     if not row:
#         raise HTTPException(status_code=404, detail="Analysis not found")
#     return row


# @app.get("/analyses", tags=["analysis"])
# async def list_analyses(
#     limit: int = 50,
#     user: dict = Depends(require_role("admin")),
# ):
#     """Admin-only: list recent analyses."""
#     rows = db.list_analyses(limit=limit)
#     return {"analyses": rows, "count": len(rows)}


# # ── Chat (follow-up on an analysis) ──────────────────────────────────────────

# @app.post("/chat/{analysis_id}", tags=["chat"])
# @limiter.limit(CHAT_RATE)
# async def chat(
#     request: Request,
#     analysis_id: str,
#     body: ChatRequest,
#     user: dict = Depends(get_current_user),
# ):
#     """
#     Follow-up Q&A on a completed analysis.
#     Uses the stored draft_response as context for the LLM reply.
#     """
#     analysis = db.get_analysis(analysis_id)
#     if not analysis:
#         raise HTTPException(status_code=404, detail="Analysis not found")

#     # Simple stateless reply: use Claude with analysis context
#     from langchain_anthropic import ChatAnthropic

#     llm = ChatAnthropic(model="claude-sonnet-4-5", temperature=0.3, max_tokens=1024)
#     context = (
#         f"Bug: {analysis.get('bug_title', '')}\n"
#         f"Category: {analysis.get('category', '')} | Severity: {analysis.get('severity', '')}\n"
#         f"Previous analysis:\n{analysis.get('draft_response', '')[:2000]}"
#     )
#     prompt = (
#         f"You are a senior software engineer assisting with bug triage.\n\n"
#         f"Context:\n{context}\n\n"
#         f"User follow-up question: {body.message}\n\n"
#         f"Provide a concise, accurate response."
#     )

#     # Run in thread pool (LangChain is synchronous)
#     loop = asyncio.get_event_loop()
#     response = await loop.run_in_executor(
#         _executor, lambda: llm.invoke(prompt).content
#     )

#     return {"reply": response, "analysis_id": analysis_id}


# # ── Feedback ─────────────────────────────────────────────────────────────────

# @app.post("/feedback", tags=["feedback"])
# async def submit_feedback(
#     body: FeedbackRequest,
#     user: dict = Depends(_current_user),
# ):
#     feedback_id = db.save_feedback(
#         vote=body.vote,
#         analysis_id=body.analysis_id,
#         bug_title=body.bug_title or "",
#         solution_snippet=body.solution_snippet or "",
#     )
#     return {"feedback_id": feedback_id, "vote": body.vote}


# @app.get("/feedback/summary", tags=["feedback"])
# async def feedback_summary(user: dict = Depends(_require_admin)):
#     return db.feedback_summary()


# # ── Review queue ──────────────────────────────────────────────────────────────

# @app.get("/review-queue", tags=["review"])
# async def get_review_queue(
#     limit: int = 100,
#     user: dict = Depends(_require_admin),
# ):
#     items = db.list_review_queue(limit=limit)
#     return {"items": items, "count": len(items)}


# @app.patch("/review-queue/{item_id}", tags=["review"])
# async def update_review_item(
#     item_id: str,
#     body: ReviewUpdateRequest,
#     user: dict = Depends(_require_admin),
# ):
#     ok = db.update_review(
#         item_id=item_id,
#         status=body.status,
#         reviewer_note=body.reviewer_note or "",
#         reviewed_by=user.get("sub"),
#     )
#     if not ok:
#         raise HTTPException(status_code=404, detail="Review item not found")
#     return {"item_id": item_id, "status": body.status}


# # ── Admin — user management ───────────────────────────────────────────────────

# @app.get("/admin/users", tags=["admin"])
# async def list_users(user: dict = Depends(_require_admin)):
#     return {"users": db.list_users()}


# @app.post("/admin/users", tags=["admin"])
# async def create_user(
#     request: Request,
#     user: dict = Depends(_require_admin),
# ):
#     body = await request.json()
#     username = body.get("username", "").strip()
#     password = body.get("password", "")
#     role = body.get("role", "viewer")

#     if not username or not password:
#         raise HTTPException(status_code=400, detail="username and password required")
#     if role not in ("admin", "viewer"):
#         raise HTTPException(status_code=400, detail="role must be admin or viewer")

#     import bcrypt

#     pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
#     db.create_user(username, pw_hash, role)
#     return {"username": username, "role": role}


# @app.patch("/admin/users/{username}/active", tags=["admin"])
# async def set_user_active(
#     username: str,
#     request: Request,
#     user: dict = Depends(_require_admin),
# ):
#     body = await request.json()
#     active = bool(body.get("active", True))
#     ok = db.set_user_active(username, active)
#     if not ok:
#         raise HTTPException(status_code=404, detail="User not found")
#     return {"username": username, "is_active": active}


# # ── Audit log (admin) ─────────────────────────────────────────────────────────

# @app.get("/admin/audit-log", tags=["admin"])
# async def audit_log(limit: int = 100, user: dict = Depends(_require_admin)):
#     return {"entries": read_logs(limit=limit), "stats": get_summary_stats()}


# # ─────────────────────────────────────────────────────────────────────────────
# # Development entrypoint
# # ─────────────────────────────────────────────────────────────────────────────

# if __name__ == "__main__":
#     import uvicorn

#     uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)

"""
BugAnalyzer — FastAPI application - app.py
==================================
Production-ready multi-agent bug analysis API.

Architecture
------------
POST /analyze           → enqueues job, returns job_id immediately
GET  /jobs/{id}/stream  → SSE stream: poll Redis LIST until done/failed

Storage
-------
• PostgreSQL (db.py)  — analyses, review_queue, feedback, users
• Redis     (jobs.py) — running-job state & SSE event lists

Auth
----
JWT stored in httpOnly cookie (auth.py).
Roles: admin (full access) | viewer (read-only, no review actions)
"""

# from __future__ import annotations
from typing import Annotated

import asyncio
import json
import logging
import os
import time
import uuid
import threading
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import (
    Body,
    Depends,
    FastAPI,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

load_dotenv()

# ── Local modules ─────────────────────────────────────────────────────────────
import db
import jobs
from audit_log import generate_request_id, log_analysis, read_logs, get_summary_stats
from auth import (
    authenticate,
    issue_session,
    clear_session,
    get_current_user,
    require_role,
    verify_password,
)
from graph import build_graph

# Optional Kafka producer — imported lazily so the app starts without Kafka
try:
    from kafka_producer import publish_analysis_event

    _KAFKA_ENABLED = True
except ImportError:
    _KAFKA_ENABLED = False
    publish_analysis_event = None  # type: ignore[assignment]

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("buganalyzer.app")

# ── Config ────────────────────────────────────────────────────────────────────
MAX_ANALYSES_PER_DAY = int(os.getenv("MAX_ANALYSES_PER_DAY", "300"))
MAX_CHAT_TURNS = int(os.getenv("MAX_CHAT_TURNS", "10"))
JOB_WORKERS = int(os.getenv("JOB_WORKERS", "8"))
MAX_CONCURRENT_PIPELINES = int(os.getenv("MAX_CONCURRENT_PIPELINES", "5"))
_active_pipelines = 0
_pipeline_lock = threading.Lock()
FRONTEND_ORIGINS = [
    o.strip()
    for o in os.getenv("FRONTEND_ORIGINS", "http://localhost:3000").split(",")
    if o.strip()
]

# ── Thread pool for blocking LangGraph calls ──────────────────────────────────
_executor = ThreadPoolExecutor(max_workers=JOB_WORKERS, thread_name_prefix="bg-worker")

# ── Rate limiter ──────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

# ANALYZE_RATE = os.getenv("ANALYZE_RATE_LIMIT", "5/minute")
ANALYZE_RATE = os.getenv("ANALYZE_RATE_LIMIT", "3/minute")
LOGIN_RATE = os.getenv("LOGIN_RATE_LIMIT", "5/minute")
CHAT_RATE = os.getenv("CHAT_RATE_LIMIT", "10/minute")


# ─────────────────────────────────────────────────────────────────────────────
# Lifespan — startup / shutdown
# ─────────────────────────────────────────────────────────────────────────────

# @asynccontextmanager
# async def lifespan(app: FastAPI):  # noqa: ANN001
#     # ── Startup ──────────────────────────────────────────────────────────────
#     logger.info("Starting BugAnalyzer API…")

#     # 1. PostgreSQL — create tables if they don't exist
#     db.init_db()
#     logger.info("PostgreSQL ready")

#     # 2. Redis — verify connection (lazy singleton; ping on first call)
#     jobs._r()
#     logger.info("Redis job queue ready")

#     # 3. LangGraph pipeline — compile once and cache
#     app.state.graph = build_graph()
#     logger.info("LangGraph pipeline compiled")

#     yield

#     # ── Shutdown ─────────────────────────────────────────────────────────────
#     logger.info("Shutting down…")
#     jobs.shutdown()
#     db.close_pool()
#     _executor.shutdown(wait=False)
#     logger.info("Shutdown complete")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────────
    logger.info("Starting BugAnalyzer API…")

    # 1. PostgreSQL
    db.init_db()
    logger.info("PostgreSQL ready")

    # 2. Redis
    jobs._r()
    logger.info("Redis job queue ready")

    # 3. Embedding model + Weaviate
    import weaviate
    import weaviate.classes as wvc
    from sentence_transformers import SentenceTransformer

    WEAVIATE_URL = os.getenv("WEAVIATE_URL", "")
    WEAVIATE_KEY = os.getenv("WEAVIATE_KEY", "")

    logger.info("Loading embedding model…")
    _model = SentenceTransformer("nomic-ai/nomic-embed-text-v1.5", trust_remote_code=True)

    # logger.info(f"Connecting to Weaviate at {WEAVIATE_URL} …")
    # _weaviate = weaviate.connect_to_weaviate_cloud(
    #     cluster_url=WEAVIATE_URL,
    #     auth_credentials=weaviate.auth.AuthApiKey(WEAVIATE_KEY),
    # )
    # _collection = _weaviate.collections.get("JiraIssues")
    # app.state.weaviate_client = _weaviate
    logger.info(f"Connecting to Weaviate at {WEAVIATE_URL} …")
    _weaviate = None
    _collection = None
    try:
        _weaviate = weaviate.connect_to_weaviate_cloud(
            cluster_url=WEAVIATE_URL,
            auth_credentials=weaviate.auth.AuthApiKey(WEAVIATE_KEY),
        )
        _collection = _weaviate.collections.get("JiraIssues")
        app.state.weaviate_client = _weaviate
        logger.info("Weaviate connected ✓")
    except Exception as _wv_err:
        logger.warning(f"Weaviate unavailable (non-fatal): {_wv_err} — RAG will return empty results")
        app.state.weaviate_client = None

    def query_weaviate(query_text: str, n_results: int = 15, min_similarity: float = 0.4) -> list[dict]:
        if _collection is None:
            return []
        vec = _model.encode(["search_query: " + query_text], convert_to_numpy=True)[0].tolist()
        results = _collection.query.near_vector(
            near_vector=vec,
            limit=n_results,
            return_properties=["jira_id", "key", "summary", "priority", "resolution", "discussion"],
            return_metadata=wvc.query.MetadataQuery(distance=True),
        )
        issues = []
        for obj in results.objects:
            sim = 1 / (1 + obj.metadata.distance)
            if sim >= min_similarity:
                p = obj.properties
                pri = p.get("priority")
                issues.append({
                    "id":              p.get("jira_id"),
                    "key":             p.get("key"),
                    "summary":         p.get("summary"),
                    "priority.name":   pri if pri not in (None, "nan", "NaN", "") else "Unknown",
                    "resolution.name": p.get("resolution"),
                    "comments_text":   p.get("discussion"),
                    "similarity":      round(sim, 3),
                })
        return issues

    # 4. LangGraph pipeline
    app.state.graph = build_graph(query_weaviate_fn=query_weaviate)
    logger.info("LangGraph pipeline compiled")

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────────
    logger.info("Shutting down…")
    # if hasattr(app.state, "weaviate_client"):
    #     app.state.weaviate_client.close()
    if hasattr(app.state, "weaviate_client") and app.state.weaviate_client is not None:
        app.state.weaviate_client.close()
    jobs.shutdown()
    db.close_pool()
    _executor.shutdown(wait=False)
    logger.info("Shutdown complete")


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI app
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="BugAnalyzer API",
    version="2.0.0",
    description="Multi-agent AI system for intelligent bug triage and resolution.",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────────────
# Request / Response schemas
# ─────────────────────────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    bug_title: str = Field(..., min_length=3, max_length=200)
    issue_description: str = Field(..., min_length=10, max_length=8000)
    stack_trace: Optional[str] = Field(default=None, max_length=16000)
    # user_priority: str = Field(default="medium", pattern="^(low|medium|high|critical)$")
    # user_priority: str = Field(default="Major")
    # user_priority: str = Field(default="Medium", pattern="^(?i)(critical|high|medium|low|minor|major)$")
    user_priority: str = Field(
    default="Major",
    pattern="^(?i)(blocker|critical|major|minor|trivial)$")

class JobResponse(BaseModel):
    job_id: str
    status: str
    message: str


class FeedbackRequest(BaseModel):
    vote: str = Field(..., pattern="^(up|down)$")
    analysis_id: Optional[str] = None
    bug_title: Optional[str] = ""
    solution_snippet: Optional[str] = ""


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)


class ReviewUpdateRequest(BaseModel):
    status: str = Field(..., pattern="^(approved|rejected)$")
    reviewer_note: Optional[str] = ""


class LoginRequest(BaseModel):
    username: str
    password: str


# ─────────────────────────────────────────────────────────────────────────────
# Background worker — runs LangGraph pipeline in thread pool
# ─────────────────────────────────────────────────────────────────────────────

def _run_pipeline(job_id: str, req: AnalyzeRequest, client_ip: Optional[str]) -> None:
    """
    Blocking function executed in ThreadPoolExecutor.
    Emits SSE-style events to Redis; stores result in PostgreSQL.
    """
    global _active_pipelines
    with _pipeline_lock:
        _active_pipelines += 1
    start = time.time()
    try:
        jobs.emit(job_id, "status", {"message": "Classifying bug…"})

        graph = app.state.graph  # compiled in lifespan
        result = graph.invoke({
            "request_id":        job_id,
            "issue_description": req.issue_description,
            "bug_title":         req.bug_title,
            "stack_trace":       req.stack_trace or "",
            "user_priority":     req.user_priority,
            "agent_status":      {},
            "mcp_tool_calls":    [],
            "mcp_tool_inputs":   [],
            "agent_timings":     {},
        })

        elapsed = round(time.time() - start, 2)

        # ── Persist to PostgreSQL ─────────────────────────────────────────
        db.save_analysis(job_id, req, result, elapsed, client_ip)

        # ── Audit log (JSONL file) ────────────────────────────────────────
        # log_analysis(
        #     request_id=job_id,
        #     bug_title=req.bug_title,
        #     category=result.get("category", "unknown"),
        #     severity=result.get("severity", "unknown"),
        #     escalated=result.get("escalated", False),
        #     response_time=elapsed,
        # )
        log_analysis(
            request_id=job_id,
            state=result,
            response_time_secs=elapsed,
            tool_calls_made=result.get("mcp_tool_calls", []),
            tool_inputs_log=result.get("mcp_tool_inputs", []),
        )

        # ── Kafka event ───────────────────────────────────────────────────
        if _KAFKA_ENABLED and publish_analysis_event is not None:
            try:
                publish_analysis_event(
                    analysis_id=job_id,
                    category=result.get("category", "unknown"),
                    severity=result.get("severity", "unknown"),
                    escalated=result.get("escalated", False),
                    response_time_secs=elapsed,
                )
            except Exception as kafka_err:
                logger.warning("Kafka publish failed (non-fatal): %s", kafka_err)

        # ── Emit final result to SSE stream ───────────────────────────────
        # jobs.emit(
        #     job_id,
        #     "result",
        #     {
        #         "analysis_id": job_id,
        #         "category": result.get("category"),
        #         "component": result.get("component"),
        #         "severity": result.get("severity"),
        #         "confidence": result.get("confidence"),
        #         "draft_response": result.get("draft_response"),
        #         "escalated": result.get("escalated", False),
        #         "escalation_reasons": result.get("escalation_reasons", []),
        #         "retrieved_issues": result.get("retrieved_issues", [])[:5],
        #         "response_time_secs": elapsed,
        #     },
        # )
                # ── Emit final result to SSE stream ───────────────────────────────
        _esc = result.get("escalation_decision", {})
        jobs.emit(
            job_id,
            "result",
            {
                "request_id":          job_id,
                "analysis_id":         job_id,
                "final_response":      result.get("draft_response", ""),
                "draft_response":      result.get("draft_response", ""),
                "classification":      result.get("classification", {}),
                "severity_assessment": result.get("severity_assessment", {}),
                "confidence_score":    result.get("confidence_score", 0),
                "escalated":           _esc.get("escalate", False),
                "escalation_reasons":  _esc.get("reasons", []),
                "retrieved_issues":    result.get("retrieved_issues", [])[:5],
                "response_time_secs":  elapsed,
            },
        )

        # Mark job done
        job = jobs.RedisJob(job_id)
        job.status = "done"
        logger.info("Job %s completed in %.2fs", job_id, elapsed)

    except Exception as exc:
        logger.exception("Pipeline failed for job %s", job_id)
        jobs.emit(job_id, "error", {"message": str(exc)})
        job = jobs.RedisJob(job_id)
        job.status = "failed"
    finally:
        with _pipeline_lock:
            _active_pipelines -= 1 


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["meta"])
async def health():
    return {"status": "ok"}


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.post("/auth/login", tags=["auth"])
@limiter.limit(LOGIN_RATE)
async def login(request: Request, response: Response, body: LoginRequest = Body(...)):
    user = authenticate(body.username, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    issue_session(response, user)
    return {"username": user["username"], "role": user["role"]}


@app.post("/auth/logout", tags=["auth"])
async def logout(response: Response):
    clear_session(response)
    return {"message": "Logged out"}


@app.get("/auth/me", tags=["auth"])
async def me(user: dict = Depends(get_current_user)):
    return {"username": user["username"], "role": user["role"]}


# ── Analysis — async job pattern ──────────────────────────────────────────────

@app.post("/analyze", response_model=JobResponse, tags=["analysis"])
@limiter.limit(ANALYZE_RATE)
async def analyze(
    request: Request,
    body: AnalyzeRequest = Body(...),
    # user: dict = Depends(get_current_user),
):
    today_count = db.count_analyses_today()
    if today_count >= MAX_ANALYSES_PER_DAY:
        raise HTTPException(
            status_code=429,
            detail=f"Daily analysis limit ({MAX_ANALYSES_PER_DAY}) reached. Try again tomorrow.",
        )

    # Generate job_id here, pass it to create_job
    job_id = str(uuid.uuid4())
    with _pipeline_lock:
        if _active_pipelines >= MAX_CONCURRENT_PIPELINES:
            raise HTTPException(
                status_code=429,
                detail=f"Server busy — too many analyses running. Please wait a moment and retry.",
            )
    jobs.create_job(job_id)
    client_ip = request.client.host if request.client else None

    _executor.submit(_run_pipeline, job_id, body, client_ip)

    return JobResponse(
        job_id=job_id,
        status="queued",
        message="Analysis started. Connect to the stream endpoint for live updates.",
    )


@app.get("/jobs/{job_id}/stream", tags=["analysis"])
async def stream_job(
    job_id: str,
    request: Request
    # user: dict = Depends(get_current_user),
):
    """Server-Sent Events stream for a running analysis job."""

    async def event_generator():
        index = 0
        terminal_seen = False

        while not terminal_seen:
            if await request.is_disconnected():
                break
            batch = jobs.events_since(jobs.RedisJob(job_id), index)
            for evt in batch:
                index = evt["id"] + 1
                event_type = evt.get("event", "message")
                data = json.dumps(evt.get("data", {}))
                yield f"id: {evt['id']}\nevent: {event_type}\ndata: {data}\n\n"
                if event_type in ("result", "error"):
                    terminal_seen = True
                    break

            if not terminal_seen:
                job = jobs.RedisJob(job_id)
                if job.status in ("done", "failed", "unknown"):
                    if not batch:
                        yield f'event: error\ndata: {{"message":"Job state lost"}}\n\n'
                    break
                await asyncio.sleep(0.1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/analyses/{analysis_id}", tags=["analysis"])
async def get_analysis(analysis_id: str):
    row = db.get_analysis_status(analysis_id)
    if not row:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return row


@app.get("/analyses", tags=["analysis"])
async def list_analyses(
    limit: int = 50,
    user: dict = Depends(require_role("admin")),
):
    """Admin-only: list recent analyses."""
    rows = db.list_analyses(limit=limit)
    return {"analyses": rows, "count": len(rows)}


# ── Chat (follow-up on an analysis) ──────────────────────────────────────────

@app.post("/chat/{analysis_id}", tags=["chat"])
@limiter.limit(CHAT_RATE)
async def chat(
    request: Request,
    analysis_id: str,
    body: ChatRequest = Body(...),
    # user: dict = Depends(get_current_user),
):
    """Follow-up Q&A on a completed analysis."""
    analysis = db.get_analysis(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    from langchain_anthropic import ChatAnthropic

    llm = ChatAnthropic(model="claude-sonnet-4-6", temperature=0.3, max_tokens=1024)
    context = (
        f"Bug: {analysis.get('bug_title', '')}\n"
        f"Category: {analysis.get('category', '')} | Severity: {analysis.get('severity', '')}\n"
        f"Previous analysis:\n{analysis.get('draft_response', '')[:2000]}"
    )
    prompt = (
        f"You are a senior software engineer assisting with bug triage.\n\n"
        f"Context:\n{context}\n\n"
        f"User follow-up question: {body.message}\n\n"
        f"Provide a concise, accurate response."
    )

    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        _executor, lambda: llm.invoke(prompt).content
    )

    return {"reply": response, "analysis_id": analysis_id}


# ── Feedback ─────────────────────────────────────────────────────────────────

@app.post("/feedback", tags=["feedback"])
async def submit_feedback(body: FeedbackRequest):
    feedback_id = db.save_feedback(
        vote=body.vote,
        analysis_id=body.analysis_id,
        bug_title=body.bug_title or "",
        solution_snippet=body.solution_snippet or "",
    )
    return {"feedback_id": feedback_id, "vote": body.vote}


@app.get("/feedback/summary", tags=["feedback"])
async def feedback_summary(user: dict = Depends(require_role("admin"))):
    return db.feedback_summary()


# ── Review queue ──────────────────────────────────────────────────────────────

# @app.get("/review-queue", tags=["review"])
# async def get_review_queue(
#     limit: int = 100,
#     user: dict = Depends(require_role("admin")),
# ):
#     items = db.list_review_queue(limit=limit)
#     return {"items": items, "count": len(items)}

@app.get("/review-queue", tags=["review"])
async def get_review_queue(
    limit: int = 100,
    user: dict = Depends(require_role("admin")),
):
    items = db.list_review_queue(limit=limit)
    return {
        "items": items,
        "count": len(items),
        "mode": "full",
        "user": {"username": user["username"], "role": user["role"]},
    }


@app.patch("/review-queue/{item_id}", tags=["review"])
async def update_review_item(
    item_id: str,
    body: ReviewUpdateRequest,
    user: dict = Depends(require_role("admin")),
):
    ok = db.update_review(
        item_id=item_id,
        status=body.status,
        reviewer_note=body.reviewer_note or "",
        reviewed_by=user.get("username"),   # fixed: was user.get("sub")
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Review item not found")
    return {"item_id": item_id, "status": body.status}


# ── Admin — user management ───────────────────────────────────────────────────

@app.get("/admin/users", tags=["admin"])
async def list_users(user: dict = Depends(require_role("admin"))):
    return {"users": db.list_users()}


@app.post("/admin/users", tags=["admin"])
async def create_user(
    request: Request,
    user: dict = Depends(require_role("admin")),
):
    body = await request.json()
    username = body.get("username", "").strip()
    password = body.get("password", "")
    role = body.get("role", "viewer")

    if not username or not password:
        raise HTTPException(status_code=400, detail="username and password required")
    if role not in ("admin", "viewer"):
        raise HTTPException(status_code=400, detail="role must be admin or viewer")

    import bcrypt

    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    db.create_user(username, pw_hash, role)
    return {"username": username, "role": role}


@app.patch("/admin/users/{username}/active", tags=["admin"])
async def set_user_active(
    username: str,
    request: Request,
    user: dict = Depends(require_role("admin")),
):
    body = await request.json()
    active = bool(body.get("active", True))
    ok = db.set_user_active(username, active)
    if not ok:
        raise HTTPException(status_code=404, detail="User not found")
    return {"username": username, "is_active": active}


# ── Audit log (admin) ─────────────────────────────────────────────────────────

@app.get("/admin/audit-log", tags=["admin"])
async def audit_log(limit: int = 100, user: dict = Depends(require_role("admin"))):
    return {"entries": read_logs(limit=limit), "stats": get_summary_stats()}


# ─────────────────────────────────────────────────────────────────────────────
# Development entrypoint
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)