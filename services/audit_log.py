"""
audit_log.py
------------
Structured audit logging for BugAnalyzer.

Every analysis gets a permanent JSONL record capturing:
  - Request details (bug title, description, priority)
  - Agent outputs (classification, severity, confidence)
  - Retrieval quality (tickets found, similarity scores)
  - Escalation decision (reasons, Jira ticket, Slack status)
  - MCP tool calls made by Claude
  - Response time

Format: JSONL (one JSON object per line, append-only)
Why JSONL: append-only means no corruption risk, easy to parse,
           feeds directly into RAGAS evaluation later

Usage in app.py:
    from audit_log import log_analysis
    log_analysis(request_id, state, response_time_seconds)
"""

import os
import json
import uuid
import threading
from datetime import datetime, timezone

# ── File location ──────────────────────────────────────────────────────────────
AUDIT_LOG_PATH = os.environ.get("AUDIT_LOG_PATH", "logs/audit.jsonl")

# Thread lock — multiple concurrent requests must not interleave writes
_write_lock = threading.Lock()


def _ensure_log_dir() -> None:
    """Create the logs directory if it doesn't exist."""
    log_dir = os.path.dirname(AUDIT_LOG_PATH)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)


def generate_request_id() -> str:
    """Generate a unique ID for each analysis request."""
    return str(uuid.uuid4())


def log_analysis(
    request_id         : str,
    state              : dict,
    response_time_secs : float,
    tool_calls_made    : list = None
) -> None:
    """
    Append one structured record to the audit log.

    Called once per /analyze request after the full pipeline completes.
    Fails silently — a logging error should never break the analysis response.

    Args:
        request_id         : UUID generated at request start
        state              : final LangGraph state dict
        response_time_secs : wall clock time for full pipeline
        tool_calls_made    : list of tool names Claude called (from DraftResponse agent)
    """
    try:
        _ensure_log_dir()

        classification  = state.get("classification", {})
        severity        = state.get("severity_assessment", {})
        escalation      = state.get("escalation_decision", {})
        retrieved       = state.get("retrieved_issues", [])

        # Similarity stats — useful for evaluating retrieval quality over time
        similarities = [
            float(t.get("similarity", 0))
            for t in retrieved
            if t.get("similarity") is not None
        ]

        record = {
            # ── Identity ───────────────────────────────────────────────────────
            "request_id"        : request_id,
            "timestamp"         : datetime.now(timezone.utc).isoformat(),

            # ── Input ──────────────────────────────────────────────────────────
            "bug_title"         : state.get("bug_title", ""),
            "issue_description" : state.get("issue_description", "")[:300],
            "user_priority"     : state.get("user_priority", "Unknown"),
            "has_stack_trace"   : bool(state.get("stack_trace", "").strip()),

            # ── Agent 1+2 outputs ──────────────────────────────────────────────
            "category"          : classification.get("category"),
            "component"         : classification.get("component"),
            "root_cause_family" : classification.get("root_cause_family"),
            "severity"          : severity.get("severity"),
            "sla_risk"          : severity.get("sla_risk"),
            "production_impact" : severity.get("production_impact"),
            "escalate_immediately": severity.get("escalate_immediately"),

            # ── Agent 3 retrieval quality ──────────────────────────────────────
            "tickets_retrieved" : len(retrieved),
            "avg_similarity"    : round(sum(similarities) / len(similarities), 4) if similarities else 0.0,
            "max_similarity"    : round(max(similarities), 4) if similarities else 0.0,
            "min_similarity"    : round(min(similarities), 4) if similarities else 0.0,
            "top_ticket_key"    : retrieved[0].get("key") if retrieved else None,

            # ── Agent 4 draft response ─────────────────────────────────────────
            "confidence_score"  : state.get("confidence_score", 0.0),
            "mcp_tools_called"  : tool_calls_made or [],
            "mcp_tool_count"    : len(tool_calls_made) if tool_calls_made else 0,

            # ── Agent 5 escalation ─────────────────────────────────────────────
            "escalated"         : escalation.get("escalate", False),
            "escalation_reasons": escalation.get("reasons", []),
            "escalation_action" : escalation.get("action"),
            "slack_notified"    : escalation.get("slack_notified", False),
            "jira_ticket_key"   : escalation.get("jira_ticket_key"),
            "jira_ticket_url"   : escalation.get("jira_ticket_url"),

            # ── Performance ────────────────────────────────────────────────────
            "response_time_secs": round(response_time_secs, 2),
        }

        # Thread-safe append
        with _write_lock:
            with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")

        print(f"[AuditLog] Logged request_id={request_id}, "
              f"confidence={record['confidence_score']:.2f}, "
              f"escalated={record['escalated']}, "
              f"time={record['response_time_secs']}s")

    except Exception as e:
        # Never let logging break the response
        print(f"[AuditLog] WARNING: Failed to write audit log — {e}")


def read_logs(limit: int = 50, escalated_only: bool = False) -> list:
    """
    Read the most recent audit log entries.
    Used by the GET /audit/logs endpoint.

    Args:
        limit         : max number of records to return (most recent first)
        escalated_only: if True, return only escalated analyses
    """
    try:
        if not os.path.exists(AUDIT_LOG_PATH):
            return []

        with open(AUDIT_LOG_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()

        records = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

        # Most recent first
        records.reverse()

        if escalated_only:
            records = [r for r in records if r.get("escalated")]

        return records[:limit]

    except Exception as e:
        print(f"[AuditLog] WARNING: Failed to read audit log — {e}")
        return []


def get_summary_stats() -> dict:
    """
    Compute aggregate stats across all logged analyses.
    Used by GET /audit/summary endpoint.
    Useful for spotting confidence drift or escalation rate changes over time.
    """
    try:
        records = read_logs(limit=10000)
        if not records:
            return {"total_analyses": 0}

        total           = len(records)
        escalated       = sum(1 for r in records if r.get("escalated"))
        avg_confidence  = sum(r.get("confidence_score", 0) for r in records) / total
        avg_time        = sum(r.get("response_time_secs", 0) for r in records) / total
        slack_sent      = sum(1 for r in records if r.get("slack_notified"))
        jira_created    = sum(1 for r in records if r.get("jira_ticket_key"))
        tool_calls      = sum(r.get("mcp_tool_count", 0) for r in records)

        # Escalation reason breakdown
        reason_counts = {}
        for r in records:
            for reason in r.get("escalation_reasons", []):
                reason_counts[reason] = reason_counts.get(reason, 0) + 1

        # Category breakdown
        category_counts = {}
        for r in records:
            cat = r.get("category", "unknown")
            category_counts[cat] = category_counts.get(cat, 0) + 1

        return {
            "total_analyses"      : total,
            "escalation_rate"     : round(escalated / total, 3),
            "escalated_count"     : escalated,
            "avg_confidence_score": round(avg_confidence, 3),
            "avg_response_time_secs": round(avg_time, 2),
            "slack_notifications_sent": slack_sent,
            "jira_tickets_created": jira_created,
            "total_mcp_tool_calls": tool_calls,
            "avg_mcp_tools_per_analysis": round(tool_calls / total, 2),
            "escalation_reasons_breakdown": reason_counts,
            "category_breakdown"  : category_counts,
        }

    except Exception as e:
        print(f"[AuditLog] WARNING: Failed to compute summary — {e}")
        return {"error": str(e)}