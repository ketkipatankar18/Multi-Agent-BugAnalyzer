"""
mcp_tools.py
------------
MCP-style tools for BugAnalyzer.

These tools are passed to Claude via Anthropic's tool_use API so Claude
decides when to call them — not your code. That's what makes it agentic.

Four tools:
    get_ticket_details   — look up a specific ticket by key from local CSV
    search_full_dataset  — keyword search over the 100k corpus as fallback
    notify_reviewer      — send Slack notification on escalation
    create_jira_ticket   — create real Jira ticket on escalation

Scalability patterns included:
    TTL cache            — repeated lookups return instantly
    Circuit breaker      — Slack/Jira outages degrade gracefully
    Sync + async         — sync versions for LangGraph, async for FastAPI
"""

import os
import json
import httpx
import pandas as pd
from datetime import datetime, timedelta
from base64 import b64encode

# ── Dataset — loaded once at startup ──────────────────────────────────────────
_JIRA_DF = None

def get_jira_df() -> pd.DataFrame:
    global _JIRA_DF
    if _JIRA_DF is None:
        csv_path = os.environ.get("JIRA_CSV_PATH", "../jira_demo.csv")
        try:
            _JIRA_DF = pd.read_csv(csv_path)
            print(f"[MCP] Loaded {len(_JIRA_DF):,} tickets from {csv_path}")
        except Exception as e:
            print(f"[MCP] Warning: could not load CSV — {e}")
            _JIRA_DF = pd.DataFrame()
    return _JIRA_DF

# ── TTL Cache ──────────────────────────────────────────────────────────────────
_cache: dict = {}

def get_cached(key: str, ttl_seconds: int = 300):
    if key in _cache:
        value, timestamp = _cache[key]
        if datetime.now() - timestamp < timedelta(seconds=ttl_seconds):
            return value
        del _cache[key]
    return None

def set_cached(key: str, value) -> None:
    _cache[key] = (value, datetime.now())

# ── Circuit Breaker ────────────────────────────────────────────────────────────
class CircuitBreaker:
    """
    Stops calling an external API after repeated failures.
    Tries again after recovery_timeout seconds.
    Prevents one broken service from cascading into a full system failure.
    """
    def __init__(self, failure_threshold: int = 3, recovery_timeout: int = 60):
        self.failures        = 0
        self.threshold       = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.last_failure    = None
        self.open            = False

    def is_open(self) -> bool:
        if self.open and self.last_failure:
            if (datetime.now() - self.last_failure).seconds > self.recovery_timeout:
                self.open     = False
                self.failures = 0
                print("[CircuitBreaker] Half-open — retrying")
        return self.open

    def record_success(self) -> None:
        self.failures = 0
        self.open     = False

    def record_failure(self) -> None:
        self.failures     += 1
        self.last_failure  = datetime.now()
        if self.failures >= self.threshold:
            self.open = True
            print(f"[CircuitBreaker] OPEN after {self.failures} failures — backing off")

# One breaker per external service
slack_breaker = CircuitBreaker()
jira_breaker  = CircuitBreaker()


# ══════════════════════════════════════════════════════════════════════════════
# TOOL 1 — get_ticket_details
# Claude calls this when it wants more info about a specific ticket it mentions.
# Looks up the local CSV — no external API needed.
# TTL cache means repeated lookups are instant.
# ══════════════════════════════════════════════════════════════════════════════
def get_ticket_details(ticket_key: str) -> dict:
    """
    Get full details of a specific JIRA ticket by key.
    Called by Claude when it references a ticket and wants more context.
    Example: get_ticket_details("PDFBOX-4071")
    """
    cache_key = f"ticket:{ticket_key.upper()}"
    cached    = get_cached(cache_key)
    if cached:
        print(f"[MCP:get_ticket_details] Cache hit — {ticket_key}")
        return cached

    df = get_jira_df()
    if df.empty:
        return {"error": "Dataset not available"}

    row = df[df["key"].str.upper() == ticket_key.upper()]
    if row.empty:
        return {"error": f"Ticket {ticket_key} not found in local database"}

    r = row.iloc[0]
    result = {
        "key"       : str(r.get("key", "")),
        "summary"   : str(r.get("summary", "")),
        "priority"  : str(r.get("priority.name", "N/A")),
        "resolution": str(r.get("resolution.name", "N/A")),
        "discussion": str(r.get("comments_text", ""))[:1000],
    }

    set_cached(cache_key, result)
    print(f"[MCP:get_ticket_details] Found {ticket_key}")
    return result


# ══════════════════════════════════════════════════════════════════════════════
# TOOL 2 — search_full_dataset
# Keyword search over the 100k corpus — complements Weaviate's semantic search.
# Weaviate finds by meaning; this finds by exact keyword match.
# Claude calls this when Weaviate results feel insufficient.
# ══════════════════════════════════════════════════════════════════════════════
def search_full_dataset(keywords: str, max_results: int = 5) -> list:
    """
    Keyword search over the full ticket corpus.
    Use when Weaviate returns no good semantic match.
    Searches both ticket summaries and discussion text.
    Example: search_full_dataset("NullPointerException HTTP handler")
    """
    cache_key = f"search:{keywords.lower()[:60]}"
    cached    = get_cached(cache_key, ttl_seconds=120)
    if cached:
        print(f"[MCP:search_full_dataset] Cache hit — '{keywords}'")
        return cached

    df = get_jira_df()
    if df.empty:
        return []

    kw = keywords.lower()

    summary_mask = df["summary"].str.lower().str.contains(kw, na=False)

    if "comments_text" in df.columns:
        disc_mask = df["comments_text"].str.lower().str.contains(kw, na=False)
        mask = summary_mask | disc_mask
    else:
        mask = summary_mask

    results = df[mask].head(max_results)

    output = [
        {
            "key"       : str(row.get("key", "")),
            "summary"   : str(row.get("summary", "")),
            "priority"  : str(row.get("priority.name", "N/A")),
            "resolution": str(row.get("resolution.name", "N/A")),
            "discussion": str(row.get("comments_text", ""))[:300],
        }
        for _, row in results.iterrows()
    ]

    set_cached(cache_key, output)
    print(f"[MCP:search_full_dataset] '{keywords}' → {len(output)} results")
    return output


# ══════════════════════════════════════════════════════════════════════════════
# TOOL 3 — notify_reviewer  (sync version for LangGraph agents)
# Sends a structured Slack notification when a bug is escalated.
# Uses circuit breaker — if Slack is down, analysis still completes.
# ══════════════════════════════════════════════════════════════════════════════
def notify_reviewer(
    bug_summary        : str,
    severity           : str,
    escalation_reasons : list,
    review_url         : str = "http://localhost:3000/review"
) -> dict:
    """
    Send Slack notification when a bug needs human review.
    Called by the Escalation agent after deciding to escalate.
    """
    if slack_breaker.is_open():
        return {"status": "skipped", "reason": "circuit_open — Slack unavailable"}

    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        return {"status": "error", "reason": "SLACK_WEBHOOK_URL not configured"}

    reasons_text = " | ".join(escalation_reasons) if escalation_reasons else "manual escalation"

    payload = {
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "🚨 Bug Needs Human Review — BugAnalyzer"}
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Bug:*\n{bug_summary[:200]}"},
                    {"type": "mrkdwn", "text": f"*Severity:*\n{severity}"},
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Escalation Reasons:*\n`{reasons_text}`"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Open Review Queue →"},
                        "url" : review_url,
                        "style": "danger"
                    }
                ]
            }
        ]
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(webhook_url, json=payload)
            resp.raise_for_status()
        slack_breaker.record_success()
        print(f"[MCP:notify_reviewer] Slack sent — severity={severity}, reasons={escalation_reasons}")
        return {"status": "sent", "severity": severity, "reasons": escalation_reasons}
    except Exception as e:
        slack_breaker.record_failure()
        print(f"[MCP:notify_reviewer] Slack failed — {e}")
        return {"status": "error", "reason": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# TOOL 4 — create_jira_ticket  (sync version for LangGraph agents)
# Creates a real Jira ticket in your Atlassian project on escalation.
# The ticket appears immediately at ketkipatankar18.atlassian.net
# Uses circuit breaker — Jira outage doesn't break the analysis.
# ══════════════════════════════════════════════════════════════════════════════
def create_jira_ticket(
    summary    : str,
    description: str,
    priority   : str = "Major",
    issue_type : str = "Bug"
) -> dict:
    """
    Create a real Jira ticket for an escalated bug.
    Called by the Escalation agent when a bug is routed to human review.
    Ticket will appear in the SCRUM project at ketkipatankar18.atlassian.net
    """
    if jira_breaker.is_open():
        return {"status": "skipped", "reason": "circuit_open — Jira unavailable"}

    base_url = os.environ.get("JIRA_BASE_URL")
    email    = os.environ.get("JIRA_EMAIL")
    token    = os.environ.get("JIRA_API_TOKEN")
    project  = os.environ.get("JIRA_PROJECT_KEY", "SCRUM")

    if not all([base_url, email, token]):
        return {"status": "error", "reason": "Jira credentials not fully configured"}

    # Jira uses HTTP Basic Auth with base64(email:token)
    credentials = b64encode(f"{email}:{token}".encode()).decode()
    headers = {
        "Authorization": f"Basic {credentials}",
        "Content-Type" : "application/json"
    }

    # Map internal severity names to Jira priority values
    priority_map = {
        "Critical": "Critical", "High": "High",
        "Medium"  : "Medium",   "Low" : "Low",
        "Blocker" : "Highest",  "Major": "High",
        "Minor"   : "Low",      "Trivial": "Lowest"
    }
    jira_priority = priority_map.get(priority, "Medium")

    payload = {
        "fields": {
            "project"    : {"key": project},
            "summary"    : summary[:255],
            "description": (
                f"*Escalated by BugAnalyzer*\n\n{description[:2000]}\n\n"
                f"_This ticket was automatically created because the AI analysis "
                f"confidence was low or the bug was flagged as high severity._"
            ),
            "issuetype"  : {"name": issue_type},
            "priority"   : {"name": jira_priority},
            "labels"     : ["buganalyzer-escalation"]
        }
    }

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                f"{base_url}/rest/api/2/issue",
                headers=headers,
                json=payload
            )
            resp.raise_for_status()
        result     = resp.json()
        ticket_key = result.get("key")
        jira_breaker.record_success()
        print(f"[MCP:create_jira_ticket] Created {ticket_key}")
        return {
            "status"    : "created",
            "ticket_key": ticket_key,
            "url"       : f"{base_url}/browse/{ticket_key}"
        }
    except Exception as e:
        jira_breaker.record_failure()
        print(f"[MCP:create_jira_ticket] Failed — {e}")
        return {"status": "error", "reason": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# CLAUDE TOOL SCHEMAS
# These are passed to client.messages.create(tools=CLAUDE_TOOLS)
# so Claude knows what tools exist and when to call them.
# Only get_ticket_details and search_full_dataset go to Claude —
# notify_reviewer and create_jira_ticket are called by Python directly
# after the escalation decision, not by Claude.
# ══════════════════════════════════════════════════════════════════════════════
CLAUDE_TOOLS = [
    {
        "name"       : "get_ticket_details",
        "description": (
            "Get full details of a specific JIRA ticket by its key (e.g. PDFBOX-4071). "
            "Use this when you want to reference more information about a specific ticket "
            "mentioned in the retrieved issues before writing your analysis."
        ),
        "input_schema": {
            "type"      : "object",
            "properties": {
                "ticket_key": {
                    "type"       : "string",
                    "description": "The JIRA ticket key, e.g. PDFBOX-4071 or HADOOP-123"
                }
            },
            "required": ["ticket_key"]
        }
    },
    {
        "name"       : "search_full_dataset",
        "description": (
            "Search the full ticket corpus by keyword when the retrieved issues are "
            "insufficient. Use this to find tickets matching specific error messages, "
            "exception types, or technical terms not well-represented in the initial results."
        ),
        "input_schema": {
            "type"      : "object",
            "properties": {
                "keywords": {
                    "type"       : "string",
                    "description": "Keywords to search for in ticket summaries and discussions"
                },
                "max_results": {
                    "type"       : "integer",
                    "description": "Maximum results to return (default 5)",
                    "default"    : 5
                }
            },
            "required": ["keywords"]
        }
    }
]


# ══════════════════════════════════════════════════════════════════════════════
# TOOL EXECUTOR
# Routes a tool_use block from Claude to the correct Python function.
# Returns result as JSON string so Claude can read it.
# ══════════════════════════════════════════════════════════════════════════════
def execute_tool(tool_name: str, tool_input: dict) -> str:
    """Execute a Claude tool call and return the result as a JSON string."""
    try:
        if tool_name == "get_ticket_details":
            result = get_ticket_details(tool_input["ticket_key"])
        elif tool_name == "search_full_dataset":
            result = search_full_dataset(
                tool_input["keywords"],
                tool_input.get("max_results", 5)
            )
        else:
            result = {"error": f"Unknown tool: {tool_name}"}
        return json.dumps(result, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})