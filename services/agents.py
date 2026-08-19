"""
agents.py
---------
The 5 agents of the BugAnalyzer multi-agent system.

Agent 1 — Classifier    : Gemini Flash  — categorizes the bug
Agent 2 — Severity      : Gemini Flash  — assesses urgency and SLA risk
Agent 3 — Retriever     : nomic + Weaviate + Cohere Rerank — finds similar tickets
Agent 4 — Draft Response: Claude Sonnet — generates the 4-section analysis
Agent 5 — Escalation    : Rules + Groq Llama — decides whether to show or escalate

Each agent receives the full LangGraph state dict and returns a partial
state dict with only the keys it updates.
"""

import os
import json
import re
from concurrent.futures import ThreadPoolExecutor
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
import anthropic
import cohere
from groq import Groq

from mcp_tools import CLAUDE_TOOLS, execute_tool, notify_reviewer, create_jira_ticket

# ── Shared clients — loaded once ──────────────────────────────────────────────
_gemini  = None
_claude  = None
_cohere  = None
_groq    = None

def get_gemini():
    global _gemini
    if _gemini is None:
        _gemini = ChatGoogleGenerativeAI(
            model="gemini-3.6-flash",
            temperature=0,
            google_api_key=os.environ.get("GOOGLE_API_KEY")
        )
    return _gemini

def get_claude():
    global _claude
    if _claude is None:
        _claude = anthropic.Anthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY")
        )
    return _claude

def get_cohere():
    global _cohere
    if _cohere is None:
        _cohere = cohere.Client(os.environ.get("COHERE_API_KEY"))
    return _cohere

def get_groq():
    global _groq
    if _groq is None:
        _groq = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    return _groq


# ══════════════════════════════════════════════════════════════════════════════
# AGENT 1 — CLASSIFIER (Gemini Flash)
# Runs in parallel with Severity Agent.
# Categorizes the bug and builds an enriched search query.
# ══════════════════════════════════════════════════════════════════════════════
def classifier_agent(state: dict) -> dict:
    print("[Classifier] Running ...")
    llm = get_gemini()

    prompt = f"""You are a bug classification system. Classify this bug report.

Bug title: {state.get("bug_title", "Not provided")}
Bug description: {state.get("issue_description", "")}
Stack trace: {state.get("stack_trace", "Not provided")}

Respond with ONLY valid JSON, no markdown, no explanation:
{{
  "category": "bug|config|performance|security|compatibility",
  "component": "network|database|ui|auth|api|filesystem|other",
  "root_cause_family": "null_pointer|race_condition|config_error|memory_leak|type_error|dependency|other",
  "enriched_query": "a precise technical search query combining key error terms, component names, and root cause keywords from the bug description — optimized for finding similar past tickets"
}}"""

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        # Strip markdown code fences if present
        # content = re.sub(r"```json|```", "", response.content).strip()
        # content = re.sub(r"```[\w]*\n?", "", response.content).strip()
        # content = content.strip("`").strip()
        # content = response.content
        # content = response.content if isinstance(response.content, str) else response.content[0].text
        raw = response.content
        if isinstance(raw, str):
            content = raw
        elif isinstance(raw, list) and len(raw) > 0:
            item = raw[0]
            if isinstance(item, dict):
                content = item.get("text", str(item))
            elif hasattr(item, "text"):
                content = item.text
            else:
                content = str(item)
        else:
            content = str(raw)
        # Remove all code fences and surrounding whitespace
        content = re.sub(r"```[\w]*", "", content)
        content = content.replace("```", "")
        content = content.strip()
        # Find the JSON object within the response
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            content = json_match.group(0)
        result  = json.loads(content)
    except Exception as e:
        print(f"[Classifier] Error: {e} — using defaults")
        result = {
            "category"        : "bug",
            "component"       : "other",
            "root_cause_family": "other",
            "enriched_query"  : state.get("issue_description", "")
        }

    print(f"[Classifier] Done — category={result.get('category')}, component={result.get('component')}")
    return {"classification": result}


# ══════════════════════════════════════════════════════════════════════════════
# AGENT 2 — SEVERITY (Gemini Flash)
# Runs in parallel with Classifier Agent.
# Assesses urgency, SLA risk, and production impact.
# ══════════════════════════════════════════════════════════════════════════════
def severity_agent(state: dict) -> dict:
    print("[Severity] Running ...")
    llm = get_gemini()

    prompt = f"""You are a bug severity assessment system for a software team.

Bug title: {state.get("bug_title", "Not provided")}
Bug description: {state.get("issue_description", "")}
Stack trace: {state.get("stack_trace", "Not provided")}
User claimed priority: {state.get("user_priority", "Unknown")}

Assess severity and respond with ONLY valid JSON, no markdown:
{{
  "severity": "Critical|High|Medium|Low",
  "sla_risk": true,
  "production_impact": true,
  "escalate_immediately": false,
  "reasoning": "one sentence explaining the severity assessment"
}}

Set escalate_immediately to true ONLY if: production is down, data loss is occurring, or security is compromised."""

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        # content  = re.sub(r"```json|```", "", response.content).strip()
        # content  = re.sub(r"```[\w]*\n?", "", response.content).strip()
        # content  = content.strip("`").strip()
        # content  = response.content
        # content = response.content if isinstance(response.content, str) else response.content[0].text
        raw = response.content
        if isinstance(raw, str):
            content = raw
        elif isinstance(raw, list) and len(raw) > 0:
            item = raw[0]
            if isinstance(item, dict):
                content = item.get("text", str(item))
            elif hasattr(item, "text"):
                content = item.text
            else:
                content = str(item)
        else:
            content = str(raw)
        content  = re.sub(r"```[\w]*", "", content)
        content  = content.replace("```", "")
        content  = content.strip()
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            content = json_match.group(0)
        result   = json.loads(content)
    except Exception as e:
        print(f"[Severity] Error: {e} — using defaults")
        result = {
            "severity"           : "Medium",
            "sla_risk"           : False,
            "production_impact"  : False,
            "escalate_immediately": False,
            "reasoning"          : "Unable to assess severity automatically."
        }

    print(f"[Severity] Done — severity={result.get('severity')}, sla_risk={result.get('sla_risk')}")
    return {"severity_assessment": result}


# ══════════════════════════════════════════════════════════════════════════════
# AGENT 1+2 PARALLEL WRAPPER
# Runs Classifier and Severity concurrently using ThreadPoolExecutor.
# LangGraph calls this as a single node; internally it fans out.
# ══════════════════════════════════════════════════════════════════════════════
def parallel_classify_and_assess(state: dict) -> dict:
    print("[Parallel] Running Classifier + Severity concurrently ...")
    with ThreadPoolExecutor(max_workers=2) as executor:
        f_classifier = executor.submit(classifier_agent, state)
        f_severity   = executor.submit(severity_agent, state)
        classification     = f_classifier.result()
        severity_assessment = f_severity.result()

    return {
        **classification,
        **severity_assessment,
        "agent_status": {
            **state.get("agent_status", {}),
            "classifier": "done",
            "severity"  : "done",
        }
    }


# ══════════════════════════════════════════════════════════════════════════════
# AGENT 3 — RETRIEVER (nomic + Weaviate + Cohere Rerank)
# Uses the enriched query from Classifier to search Weaviate,
# then reranks results with Cohere for better precision.
# Falls back gracefully if Cohere fails.
# ══════════════════════════════════════════════════════════════════════════════
def retriever_agent(state: dict, query_weaviate_fn) -> dict:
    """
    query_weaviate_fn is injected from app.py to avoid circular imports.
    It's the existing query_weaviate() function.
    """
    print("[Retriever] Running ...")

    classification = state.get("classification", {})
    enriched_query = classification.get("enriched_query") or state.get("issue_description", "")

    # Append stack trace snippet if available — improves precision
    stack = state.get("stack_trace", "").strip()
    if stack:
        enriched_query = f"{enriched_query}\n{stack[:300]}"

    # Step 1 — Weaviate retrieves top 50 candidates
    candidates = query_weaviate_fn(enriched_query, n_results=50, min_similarity=0.4)
    print(f"[Retriever] Weaviate returned {len(candidates)} candidates")

    if not candidates:
        return {
            "retrieved_issues": [],
            "agent_status": {
                **state.get("agent_status", {}),
                "retriever": "done — no candidates found"
            }
        }

    # Step 2 — Cohere reranks candidates to top 15
    try:
        co   = get_cohere()
        docs = [
            f"{c['summary']} {str(c.get('comments_text', ''))[:200]}"
            for c in candidates
        ]

        rerank_results = co.rerank(
            query=state.get("issue_description", ""),
            documents=docs,
            top_n=15,
            model="rerank-english-v3.0"
        )

        reranked = [candidates[r.index] for r in rerank_results.results]
        print(f"[Retriever] Cohere reranked to {len(reranked)} issues")

    except Exception as e:
        print(f"[Retriever] Cohere rerank failed ({e}) — using top 15 from Weaviate directly")
        reranked = candidates[:15]

    return {
        "retrieved_issues": reranked,
        "agent_status": {
            **state.get("agent_status", {}),
            "retriever": f"done — {len(reranked)} issues retrieved"
        }
    }


# ══════════════════════════════════════════════════════════════════════════════
# AGENT 4 — DRAFT RESPONSE (Claude Sonnet)
# Generates the 4-section analysis grounded in retrieved tickets.
# Appends a confidence score (0.0-1.0) that the Escalation Agent uses.
# ══════════════════════════════════════════════════════════════════════════════
# def draft_response_agent(state: dict) -> dict:
#     print("[DraftResponse] Running ...")

#     issues         = state.get("retrieved_issues", [])
#     classification = state.get("classification", {})
#     severity       = state.get("severity_assessment", {})
#     bug_title      = state.get("bug_title", "")
#     description    = state.get("issue_description", "")
#     stack          = state.get("stack_trace", "Not provided")
#     priority       = state.get("user_priority", "Unknown")

#     # Format retrieved tickets for the prompt
#     issues_summary = "\n\n".join([
#         f"{i+1}. [{t['key']}] {t['summary']}\n"
#         f"   Priority   : {t.get('priority.name', 'N/A')}\n"
#         f"   Resolution : {t.get('resolution.name', 'N/A')}\n"
#         f"   Discussion : {str(t.get('comments_text', ''))[:300]}..."
#         for i, t in enumerate(issues)
#     ])

#     confidence_note = (
#         "Note: Only a few loosely similar issues were found. "
#         "Suggestions may not directly apply.\n\n"
#         if len(issues) < 5 else ""
#     )

#     prompt = f"""You are an expert QA engineer helping resolve a software bug.

# Bug: "{(bug_title + ' — ') if bug_title else ''}{description}"
# Stack trace: {stack}
# Priority claimed by user: {priority}

# Automated assessment:
# - Category    : {classification.get('category', 'unknown')}
# - Component   : {classification.get('component', 'unknown')}
# - Severity    : {severity.get('severity', 'unknown')}
# - SLA Risk    : {severity.get('sla_risk', False)}
# - Reasoning   : {severity.get('reasoning', '')}

# {confidence_note}Most similar resolved past JIRA tickets:
# {issues_summary}

# Provide a structured analysis with EXACTLY these 4 sections using markdown:

# ### 1. Root Cause Analysis
# [Explain what is likely causing this based on the bug description and similar past issues]

# ### 2. Recommended Fix
# [Concrete steps or code to fix this, grounded in how similar tickets were resolved. Include code snippets if helpful. Reference specific ticket keys.]

# ### 3. Additional Checks
# [Other things to verify, edge cases, related areas to test]

# ### 4. Priority Assessment
# [Compare claimed priority ({priority}) against priorities of similar tickets. Include a markdown table with ticket key and priority. Recommend keeping or changing the priority with reasoning.]

# After the 4 sections, on a new line write exactly:
# CONFIDENCE: [number between 0.0 and 1.0 representing how confident you are in this analysis]

# Be technical, concise, and always reference specific ticket keys."""

#     try:
#         client   = get_claude()
#         response = client.messages.create(
#             model="claude-sonnet-4-6",
#             max_tokens=2048,
#             messages=[{"role": "user", "content": prompt}]
#         )
#         full_text = response.content[0].text

#         # Extract confidence score
#         confidence = 0.7  # default
#         if "CONFIDENCE:" in full_text:
#             try:
#                 conf_str   = full_text.split("CONFIDENCE:")[-1].strip().split()[0]
#                 confidence = float(conf_str)
#                 full_text  = full_text.split("CONFIDENCE:")[0].strip()
#             except Exception:
#                 pass

#     except Exception as e:
#         print(f"[DraftResponse] Error: {e}")
#         full_text  = "Unable to generate analysis. Please try again."
#         confidence = 0.0

#     print(f"[DraftResponse] Done — confidence={confidence:.2f}")
#     return {
#         "draft_response" : full_text,
#         "confidence_score": confidence,
#         "agent_status"   : {
#             **state.get("agent_status", {}),
#             "draft_response": f"done — confidence={confidence:.2f}"
#         }
#     }

def draft_response_agent(state: dict) -> dict:
    print("[DraftResponse] Running ...")
 
    issues         = state.get("retrieved_issues", [])
    classification = state.get("classification", {})
    severity       = state.get("severity_assessment", {})
    bug_title      = state.get("bug_title", "")
    description    = state.get("issue_description", "")
    stack          = state.get("stack_trace", "Not provided")
    priority       = state.get("user_priority", "Unknown")
 
    # Format retrieved tickets for the prompt
    issues_summary = "\n\n".join([
        f"{i+1}. [{t['key']}] {t['summary']}\n"
        f"   Priority   : {t.get('priority.name', 'N/A')}\n"
        f"   Resolution : {t.get('resolution.name', 'N/A')}\n"
        f"   Discussion : {str(t.get('comments_text', ''))[:300]}..."
        for i, t in enumerate(issues)
    ])
 
    confidence_note = (
        "Note: Only a few loosely similar issues were found. "
        "Suggestions may not directly apply.\n\n"
        if len(issues) < 5 else ""
    )
 
    prompt = f"""You are an expert QA engineer helping resolve a software bug.
 
Bug: "{(bug_title + ' — ') if bug_title else ''}{description}"
Stack trace: {stack}
Priority claimed by user: {priority}
 
Automated assessment:
- Category    : {classification.get('category', 'unknown')}
- Component   : {classification.get('component', 'unknown')}
- Severity    : {severity.get('severity', 'unknown')}
- SLA Risk    : {severity.get('sla_risk', False)}
- Reasoning   : {severity.get('reasoning', '')}
 
{confidence_note}Most similar resolved past JIRA tickets:
{issues_summary}

You have two tools available but use them sparingly:
- get_ticket_details: ONLY call this for 1-2 specific tickets where the 
  discussion text shown above is truncated and you genuinely need more 
  context to write an accurate fix recommendation.
- search_full_dataset: ONLY call this if the retrieved tickets above have 
  avg similarity below 0.75 and are clearly not matching the bug.

If the retrieved tickets already give you sufficient context to write a 
confident analysis, do NOT call any tools — proceed directly to the analysis.
 
Provide a structured analysis with EXACTLY these 4 sections using markdown:
 
### 1. Root Cause Analysis
[Explain what is likely causing this based on the bug description and similar past issues]
 
### 2. Recommended Fix
[Concrete steps or code to fix this, grounded in how similar tickets were resolved. Reference specific ticket keys.]
 
### 3. Additional Checks
[Other things to verify, edge cases, related areas to test]
 
### 4. Priority Assessment
[Compare claimed priority ({priority}) against priorities of similar tickets. Include a markdown table with ticket key and priority.]
 
After the 4 sections, on a new line write exactly:
CONFIDENCE: [You MUST write a number between 0.0 and 1.0. 
Use low values (0.3-0.5) when retrieved tickets are only 
loosely related or the bug description is unclear or 
nonsensical. Use high values (0.8-0.95) only when multiple 
retrieved tickets directly match the exact error and component.]"""
 
    try:
        client   = get_claude()
        messages = [{"role": "user", "content": prompt}]
 
        # ── Agentic loop ───────────────────────────────────────────────────────
        # Claude may call tools before writing its final response.
        # We execute each tool call and feed the result back.
        # Max 3 rounds to prevent infinite loops.
        MAX_TOOL_ROUNDS = 3
        rounds          = 0
        tool_calls_log = state.get("mcp_tool_calls", [])
        
        while rounds < MAX_TOOL_ROUNDS:
            response = client.messages.create(
                model      = "claude-sonnet-4-6",
                max_tokens = 2048,
                tools      = CLAUDE_TOOLS,
                messages   = messages
            )

            if response.stop_reason == "end_turn":
                break

            if response.stop_reason == "tool_use":
                rounds += 1
                messages.append({"role": "assistant", "content": response.content})

                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        print(f"[DraftResponse] Claude calling tool: {block.name}({block.input})")
                        result = execute_tool(block.name, block.input)
                        tool_results.append({
                            "type"       : "tool_result",
                            "tool_use_id": block.id,
                            "content"    : result
                        })
                        tool_calls_log.append(block.name)

                messages.append({"role": "user", "content": tool_results})
            else:
                break

        # ── Force final response if loop hit max rounds ────────────────────────
        # After max rounds, Claude still has pending tool results but never
        # wrote its analysis. Make one final call without tools to force it.
        if response.stop_reason != "end_turn":
            print(f"[DraftResponse] Max tool rounds hit — forcing final response")
            response = client.messages.create(
                model      = "claude-sonnet-4-6",
                max_tokens = 2048,
                # No tools here — forces end_turn and makes Claude write analysis
                messages   = messages
            )
 
        # ── Extract final text ─────────────────────────────────────────────────
        full_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                full_text += block.text
 
        # Extract and strip the confidence score
        confidence = 0.7  # default
        if "CONFIDENCE:" in full_text:
            try:
                conf_str   = full_text.split("CONFIDENCE:")[-1].strip().split()[0]
                confidence = float(conf_str)
                full_text  = full_text.split("CONFIDENCE:")[0].strip()
            except Exception:
                pass
 
    except Exception as e:
        print(f"[DraftResponse] Error: {e}")
        full_text  = "Unable to generate analysis. Please try again."
        confidence = 0.0
 
    print(f"[DraftResponse] Done — confidence={confidence:.2f}, tool_rounds={rounds}")
    return {
        "draft_response" : full_text,
        "confidence_score": confidence,
        "agent_status"   : {
            **state.get("agent_status", {}),
            "draft_response": f"done — confidence={confidence:.2f}"
        },
        "mcp_tool_calls": tool_calls_log,
    }

# ══════════════════════════════════════════════════════════════════════════════
# AGENT 5 — ESCALATION (Rules + Groq Llama)
# Decides whether to show the AI response or route to human review.
#
# Escalation triggers (rule-based — fast, no LLM):
#   • confidence < 0.5
#   • severity agent flagged escalate_immediately
#   • category is "security"
#   • no similar issues found
#
# Borderline check (Groq Llama — only when confidence is 0.5-0.65):
#   • sentiment analysis to detect user distress/urgency
# ══════════════════════════════════════════════════════════════════════════════
# def escalation_agent(state: dict) -> dict:
#     print("[Escalation] Running ...")

#     confidence  = state.get("confidence_score", 0.7)
#     severity    = state.get("severity_assessment", {})
#     classif     = state.get("classification", {})
#     issues      = state.get("retrieved_issues", [])
#     description = state.get("issue_description", "")

#     escalate_reasons = []

#     # Rule-based checks — no LLM needed
#     if confidence < 0.5:
#         escalate_reasons.append("low_confidence")

#     if severity.get("escalate_immediately"):
#         escalate_reasons.append("high_severity_immediate")

#     if classif.get("category") == "security":
#         escalate_reasons.append("security_issue")

#     if not issues:
#         escalate_reasons.append("no_similar_issues_found")

#     # Backup security check — catches cases where classifier missed the category
#     SECURITY_KEYWORDS = [
#         "injection", "sql injection", "xss", "vulnerability",
#         "exploit", "authentication bypass", "unauthorized access",
#         "data breach", "sensitive data", "csrf", "rce",
#         "remote code execution", "privilege escalation"
#     ]
#     if not any(r == "security_issue" for r in escalate_reasons):
#         if any(kw in description.lower() for kw in SECURITY_KEYWORDS):
#             escalate_reasons.append("security_keywords_detected")

#     # Borderline case — use Groq Llama for sentiment check
#     if not escalate_reasons and 0.5 <= confidence < 0.65:
#         try:
#             groq_client = get_groq()
#             response    = groq_client.chat.completions.create(
#                 model="llama-3.3-70b-versatile",
#                 messages=[{
#                     "role": "user",
#                     "content": (
#                         f"Is this bug report written with high urgency, distress, or describing a critical "
#                         f"production outage?\nBug: {description[:300]}\n"
#                         f"Answer with ONLY one word: URGENT or NORMAL"
#                     )
#                 }],
#                 max_tokens=5,
#                 temperature=0
#             )
#             sentiment = response.choices[0].message.content.strip().upper()
#             if "URGENT" in sentiment:
#                 escalate_reasons.append("urgent_sentiment_detected")
#             print(f"[Escalation] Groq sentiment check: {sentiment}")
#         except Exception as e:
#             print(f"[Escalation] Groq sentiment check failed: {e}")

#     should_escalate = len(escalate_reasons) > 0
#     action          = "human_review" if should_escalate else "show_response"

#     print(f"[Escalation] Done — escalate={should_escalate}, reasons={escalate_reasons}")
#     return {
#         "escalation_decision": {
#             "escalate": should_escalate,
#             "reasons" : escalate_reasons,
#             "action"  : action,
#         },
#         "agent_status": {
#             **state.get("agent_status", {}),
#             "escalation": f"done — action={action}"
#         }
#     }

def escalation_agent(state: dict) -> dict:
    print("[Escalation] Running ...")
 
    confidence  = state.get("confidence_score", 0.7)
    severity    = state.get("severity_assessment", {})
    classif     = state.get("classification", {})
    issues      = state.get("retrieved_issues", [])
    description = state.get("issue_description", "")
    bug_title   = state.get("bug_title", "Unknown bug")
    priority    = state.get("user_priority", "Major")
 
    escalate_reasons = []
 
    # ── Rule-based checks — no LLM needed ─────────────────────────────────────
    if confidence < 0.5:
        escalate_reasons.append("low_confidence")
 
    if severity.get("escalate_immediately"):
        escalate_reasons.append("high_severity_immediate")
 
    if classif.get("category") == "security":
        escalate_reasons.append("security_issue")
 
    if not issues:
        escalate_reasons.append("no_similar_issues_found")
 
    # Backup security keyword scan — catches what classifier may have missed
    SECURITY_KEYWORDS = [
        "injection", "sql injection", "xss", "vulnerability",
        "exploit", "authentication bypass", "unauthorized access",
        "data breach", "sensitive data", "csrf", "rce",
        "remote code execution", "privilege escalation"
    ]
    if not any(r == "security_issue" for r in escalate_reasons):
        if any(kw in description.lower() for kw in SECURITY_KEYWORDS):
            escalate_reasons.append("security_keywords_detected")
 
    # ── Borderline check — Groq Llama sentiment analysis ──────────────────────
    if not escalate_reasons and 0.5 <= confidence < 0.65:
        try:
            groq_client = get_groq()
            response    = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{
                    "role"   : "user",
                    "content": (
                        f"Is this bug report written with high urgency, distress, or describing "
                        f"a critical production outage?\nBug: {description[:300]}\n"
                        f"Answer with ONLY one word: URGENT or NORMAL"
                    )
                }],
                max_tokens  = 5,
                temperature = 0
            )
            sentiment = response.choices[0].message.content.strip().upper()
            if "URGENT" in sentiment:
                escalate_reasons.append("urgent_sentiment_detected")
            print(f"[Escalation] Groq sentiment: {sentiment}")
        except Exception as e:
            print(f"[Escalation] Groq sentiment check failed: {e}")
 
    should_escalate = len(escalate_reasons) > 0
    action          = "human_review" if should_escalate else "show_response"
 
    # ── MCP tools — only called when escalating ────────────────────────────────
    slack_result = {}
    jira_result  = {}
 
    if should_escalate:
        print(f"[Escalation] Escalating — reasons: {escalate_reasons}")
 
        # Tool 3: Slack notification
        slack_result = notify_reviewer(
            bug_summary        = f"{bug_title}: {description[:150]}",
            severity           = severity.get("severity", "Unknown"),
            escalation_reasons = escalate_reasons,
            review_url         = os.environ.get("REVIEW_URL", "http://localhost:3000/review")
        )
        print(f"[Escalation] Slack: {slack_result.get('status')}")
 
        # Tool 4: Create Jira ticket
        jira_result = create_jira_ticket(
            summary     = f"[BugAnalyzer Escalation] {bug_title or description[:100]}",
            description = (
                f"Bug Description:\n{description}\n\n"
                f"Stack Trace:\n{state.get('stack_trace', 'Not provided')}\n\n"
                f"Escalation Reasons: {', '.join(escalate_reasons)}\n"
                f"AI Confidence Score: {confidence:.2f}\n"
                f"Severity Assessment: {severity.get('severity', 'Unknown')}"
            ),
            priority   = priority,
            issue_type = "Bug"
        )
        print(f"[Escalation] Jira: {jira_result.get('status')} — {jira_result.get('ticket_key', '')}")
 
    print(f"[Escalation] Done — escalate={should_escalate}, reasons={escalate_reasons}")
 
    return {
        "escalation_decision": {
            "escalate"        : should_escalate,
            "reasons"         : escalate_reasons,
            "action"          : action,
            "slack_notified"  : slack_result.get("status") == "sent",
            "jira_ticket_key" : jira_result.get("ticket_key"),
            "jira_ticket_url" : jira_result.get("url"),
        },
        "agent_status": {
            **state.get("agent_status", {}),
            "escalation": f"done — action={action}"
        }
    }
 