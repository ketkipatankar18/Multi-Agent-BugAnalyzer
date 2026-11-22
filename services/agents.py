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
import time
from concurrent.futures import ThreadPoolExecutor
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
import anthropic
import cohere
from groq import Groq

from mcp_tools import CLAUDE_TOOLS, execute_tool, notify_reviewer, create_jira_ticket
import contextvars
from logger import get_logger, set_request_id, request_id_var
from resilience import with_retry
from jobs import emit

log = get_logger(__name__)
# ── Shared clients — loaded once ──────────────────────────────────────────────
_gemini  = None
_claude  = None
_cohere  = None
_groq    = None

def get_gemini():
    global _gemini
    if _gemini is None:
        _gemini = ChatGoogleGenerativeAI(
            # model="gemini-3.6-flash",
            model="gemini-3.8-flash",
            thinking_budget=0,    # classification needs no reasoning
            max_retries=0,        # retries handled by resilience.with_retry
            timeout=30,
            google_api_key=os.environ.get("GOOGLE_API_KEY")
        )
    return _gemini

def get_claude():
    global _claude
    if _claude is None:
        _claude = anthropic.Anthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY"),
            max_retries=0,
            timeout=90.0,
        )
    return _claude

def get_cohere():
    global _cohere
    if _cohere is None:
        _cohere = cohere.Client(os.environ.get("COHERE_API_KEY"), timeout=20)
    return _cohere

def get_groq():
    global _groq
    if _groq is None:
        _groq = Groq(api_key=os.environ.get("GROQ_API_KEY"), max_retries=0, timeout=20.0)
    return _groq

# def timed(name: str):
#     """Wrap a LangGraph node: print its duration and record it in state['agent_timings']."""
#     def decorator(fn):
#         def wrapper(state: dict) -> dict:
#             t0      = time.perf_counter()
#             out     = fn(state)
#             elapsed = round(time.perf_counter() - t0, 2)
#             log.info(f"[Timing] {name}: {elapsed}s")
#             out["agent_timings"] = {**state.get("agent_timings", {}), name: elapsed}
#             return out
#         return wrapper
#     return decorator

# def timed(name: str):
#     """Wrap a LangGraph node: tag logs with the request ID, time it, record the timing."""
#     def decorator(fn):
#         def wrapper(state: dict) -> dict:
#             token = set_request_id(state.get("request_id", ""))
#             try:
#                 t0      = time.perf_counter()
#                 out     = fn(state)
#                 elapsed = round(time.perf_counter() - t0, 2)
#                 log.info(f"[Timing] {name}: {elapsed}s")
#                 out["agent_timings"] = {**state.get("agent_timings", {}), name: elapsed}
#                 return out
#             finally:
#                 request_id_var.reset(token)
#         return wrapper
#     return decorator

def timed(name: str):
    """Wrap a LangGraph node: tag logs, emit start/done progress events, record timing."""
    def decorator(fn):
        def wrapper(state: dict) -> dict:
            rid   = state.get("request_id", "")
            token = set_request_id(rid)
            emit(rid, "stage", {"agent": name, "status": "running"})
            try:
                t0      = time.perf_counter()
                out     = fn(state)
                elapsed = round(time.perf_counter() - t0, 2)
                log.info(f"[Timing] {name}: {elapsed}s")
                out["agent_timings"] = {**state.get("agent_timings", {}), name: elapsed}
                emit(rid, "stage", {"agent": name, "status": "done", "secs": elapsed})
                return out
            finally:
                request_id_var.reset(token)
        return wrapper
    return decorator

def _parse_json_response(response) -> dict:
    """Extract a JSON object from an LLM response (handles str or list content, code fences)."""
    raw = response.content
    if isinstance(raw, list) and raw:
        item = raw[0]
        raw  = item.get("text", str(item)) if isinstance(item, dict) else getattr(item, "text", str(item))
    content = str(raw).replace("```json", "").replace("```", "").strip()
    match   = re.search(r"\{.*\}", content, re.DOTALL)
    return json.loads(match.group(0) if match else content)

# ══════════════════════════════════════════════════════════════════════════════
# AGENT 1 — CLASSIFIER (Gemini Flash)
# Runs in parallel with Severity Agent.
# Categorizes the bug and builds an enriched search query.
# ══════════════════════════════════════════════════════════════════════════════
def classifier_agent(state: dict) -> dict:
    log.info("[Classifier] Running ...")
    emit(state.get("request_id", ""), "stage", {"agent": "classifier", "status": "running"})
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
        # response = llm.invoke([HumanMessage(content=prompt)])
        # log.info(f"[Classifier] usage={response.usage_metadata}")
        # # Strip markdown code fences if present
        # # content = re.sub(r"```json|```", "", response.content).strip()
        # # content = re.sub(r"```[\w]*\n?", "", response.content).strip()
        # # content = content.strip("`").strip()
        # # content = response.content
        # # content = response.content if isinstance(response.content, str) else response.content[0].text
        # raw = response.content
        # if isinstance(raw, str):
        #     content = raw
        # elif isinstance(raw, list) and len(raw) > 0:
        #     item = raw[0]
        #     if isinstance(item, dict):
        #         content = item.get("text", str(item))
        #     elif hasattr(item, "text"):
        #         content = item.text
        #     else:
        #         content = str(item)
        # else:
        #     content = str(raw)
        # # Remove all code fences and surrounding whitespace
        # content = re.sub(r"```[\w]*", "", content)
        # content = content.replace("```", "")
        # content = content.strip()
        # # Find the JSON object within the response
        # json_match = re.search(r'\{.*\}', content, re.DOTALL)
        # if json_match:
        #     content = json_match.group(0)
        # result  = json.loads(content)
        # response = llm.invoke([HumanMessage(content=prompt)])
        response = with_retry("gemini.classifier", llm.invoke, [HumanMessage(content=prompt)])
        result   = _parse_json_response(response)
    except Exception as e:
        log.warning(f"[Classifier] Error: {e} — using defaults")
        result = {
            "category"        : "bug",
            "component"       : "other",
            "root_cause_family": "other",
            "enriched_query"  : state.get("issue_description", "")
        }

    log.info(f"[Classifier] Done — category={result.get('category')}, component={result.get('component')}")
    emit(state.get("request_id", ""), "stage", {
        "agent": "classifier", "status": "done",
        "detail": f"{result.get('category')} · {result.get('component')}",
    })
    return {"classification": result}


# ══════════════════════════════════════════════════════════════════════════════
# AGENT 2 — SEVERITY (Gemini Flash)
# Runs in parallel with Classifier Agent.
# Assesses urgency, SLA risk, and production impact.
# ══════════════════════════════════════════════════════════════════════════════
def severity_agent(state: dict) -> dict:
    log.info("[Severity] Running ...")
    emit(state.get("request_id", ""), "stage", {"agent": "severity", "status": "running"})
    llm = get_gemini()

    prompt = f"""You are a bug severity assessment system for a software team.

Bug title: {state.get("bug_title", "Not provided")}
Bug description: {state.get("issue_description", "")}
Stack trace: {state.get("stack_trace", "Not provided")}
User claimed priority: {state.get("user_priority", "Unknown")}

Assess severity and respond with ONLY valid JSON, no markdown:
{{
  "severity": "Critical|High|Medium|Low",
  "sla_risk": true|false,
  "production_impact": true|false,
  "escalate_immediately": true|false,
  "reasoning": "one sentence explaining the severity assessment"
}}

Set escalate_immediately to true ONLY if: production is down, data loss is occurring, or security is compromised."""

    try:
        # response = llm.invoke([HumanMessage(content=prompt)])
        # # content  = re.sub(r"```json|```", "", response.content).strip()
        # # content  = re.sub(r"```[\w]*\n?", "", response.content).strip()
        # # content  = content.strip("`").strip()
        # # content  = response.content
        # # content = response.content if isinstance(response.content, str) else response.content[0].text
        # raw = response.content
        # if isinstance(raw, str):
        #     content = raw
        # elif isinstance(raw, list) and len(raw) > 0:
        #     item = raw[0]
        #     if isinstance(item, dict):
        #         content = item.get("text", str(item))
        #     elif hasattr(item, "text"):
        #         content = item.text
        #     else:
        #         content = str(item)
        # else:
        #     content = str(raw)
        # content  = re.sub(r"```[\w]*", "", content)
        # content  = content.replace("```", "")
        # content  = content.strip()
        # json_match = re.search(r'\{.*\}', content, re.DOTALL)
        # if json_match:
        #     content = json_match.group(0)
        # result   = json.loads(content)
        # response = llm.invoke([HumanMessage(content=prompt)])
        response = with_retry("gemini.severity", llm.invoke, [HumanMessage(content=prompt)])
        result   = _parse_json_response(response)
    except Exception as e:
        log.warning(f"[Severity] Error: {e} — using defaults")
        result = {
            "severity"           : "Medium",
            "sla_risk"           : False,
            "production_impact"  : False,
            "escalate_immediately": False,
            "reasoning"          : "Unable to assess severity automatically."
        }

    log.info(f"[Severity] Done — severity={result.get('severity')}, sla_risk={result.get('sla_risk')}")
    emit(state.get("request_id", ""), "stage", {
        "agent": "severity", "status": "done",
        "detail": result.get("severity"),
    })
    return {"severity_assessment": result}


# ══════════════════════════════════════════════════════════════════════════════
# AGENT 1+2 PARALLEL WRAPPER
# Runs Classifier and Severity concurrently using ThreadPoolExecutor.
# LangGraph calls this as a single node; internally it fans out.
# ══════════════════════════════════════════════════════════════════════════════
def parallel_classify_and_assess(state: dict) -> dict:
    log.info("[Parallel] Running Classifier + Severity concurrently ...")
    with ThreadPoolExecutor(max_workers=2) as executor:
        # f_classifier = executor.submit(classifier_agent, state)
        # f_severity   = executor.submit(severity_agent, state)
        # don't inherit the request ID automatically instead pass it along
        f_classifier = executor.submit(contextvars.copy_context().run, classifier_agent, state)
        f_severity   = executor.submit(contextvars.copy_context().run, severity_agent, state)
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
    log.info("[Retriever] Running ...")

    classification = state.get("classification", {})
    enriched_query = classification.get("enriched_query") or state.get("issue_description", "")

    # Append stack trace snippet if available — improves precision
    stack = state.get("stack_trace", "").strip()
    if stack:
        enriched_query = f"{enriched_query}\n{stack[:300]}"

    # Step 1 — Weaviate retrieves top 50 candidates
    candidates = query_weaviate_fn(enriched_query, n_results=50, min_similarity=0.4)
    log.info(f"[Retriever] Weaviate returned {len(candidates)} candidates")

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

        # rerank_results = co.rerank(
        rerank_results = with_retry(
               "cohere.rerank", co.rerank,
            # query=state.get("issue_description", ""),
            query=f"{state.get('bug_title', '')}\n{state.get('issue_description', '')}".strip(),
            documents=docs,
            top_n=15,
            model="rerank-english-v3.0"
        )

        reranked = [candidates[r.index] for r in rerank_results.results]
        log.info(f"[Retriever] Cohere reranked to {len(reranked)} issues")

    except Exception as e:
        log.warning(f"[Retriever] Cohere rerank failed ({e}) — using top 15 from Weaviate directly")
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
def _claude_stream(request_id: str, **kwargs):
    """
    One Claude call that streams text to the job's event log as it's generated.
    Returns the final Message (same shape as messages.create), so the rest of
    the agent logic — stop_reason, tool calls, usage — is unchanged.
    """
    emit(request_id, "draft_reset", {})   # each attempt/round starts a fresh draft
    with get_claude().messages.stream(**kwargs) as stream:
        for text in stream.text_stream:
            emit(request_id, "token", {"text": text})
        return stream.get_final_message()
    
def draft_response_agent(state: dict) -> dict:
    log.info("[DraftResponse] Running ...")
 
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
retrieved tickets directly match the exact error and component.]

Keep the analysis focused:
- In Recommended Fix, show only the corrected code. Do not show before-and-after versions of the same code.
- Additional Checks: at most 5 one-line bullets.
- Priority Assessment: a table of the 5 most relevant tickets, then 1-2 sentences."""
 
    # try:
    #     client   = get_claude()
    #     messages = [{"role": "user", "content": prompt}]
 
    #     # ── Agentic loop ───────────────────────────────────────────────────────
    #     # Claude may call tools before writing its final response.
    #     # We execute each tool call and feed the result back.
    #     # Max 3 rounds to prevent infinite loops.
    #     MAX_TOOL_ROUNDS = 3
    #     rounds          = 0
    #     tool_calls_log = state.get("mcp_tool_calls", [])
    #     tool_inputs_log = state.get("mcp_tool_inputs", [])
        
    #     while rounds < MAX_TOOL_ROUNDS:
    #         response = client.messages.create(
    #             model      = "claude-sonnet-4-6",
    #             # max_tokens = 2048,
    #             max_tokens = 4069,
    #             tools      = CLAUDE_TOOLS,
    #             messages   = messages
    #         )

    #         if response.stop_reason == "end_turn":
    #             break

    #         if response.stop_reason == "tool_use":
    #             rounds += 1
    #             messages.append({"role": "assistant", "content": response.content})

    #             tool_results = []
    #             for block in response.content:
    #                 if block.type == "tool_use":
    #                     log.info(f"[DraftResponse] Claude calling tool: {block.name}({block.input})")
    #                     result = execute_tool(block.name, block.input)
    #                     tool_results.append({
    #                         "type"       : "tool_result",
    #                         "tool_use_id": block.id,
    #                         "content"    : result
    #                     })
    #                     tool_calls_log.append(block.name)
    #                     tool_inputs_log.append({"tool": block.name, "input": block.input})

    #             messages.append({"role": "user", "content": tool_results})
    #         else:
    #             break

    #     # ── Force final response if loop hit max rounds ────────────────────────
    #     # After max rounds, Claude still has pending tool results but never
    #     # wrote its analysis. Make one final call without tools to force it.
    #     if response.stop_reason != "end_turn":
    #         log.info(f"[DraftResponse] Max tool rounds hit — forcing final response")
    #         response = client.messages.create(
    #             model      = "claude-sonnet-4-6",
    #             max_tokens = 2048,
    #             # No tools here — forces end_turn and makes Claude write analysis
    #             messages   = messages
    #         )
 
    #     # ── Extract final text ─────────────────────────────────────────────────
    #     full_text = ""
    #     for block in response.content:
    #         if hasattr(block, "text"):
    #             full_text += block.text
 
    #     # Extract and strip the confidence score
    #     confidence = 0.7  # default
    #     if "CONFIDENCE:" in full_text:
    #         try:
    #             conf_str   = full_text.split("CONFIDENCE:")[-1].strip().split()[0]
    #             confidence = float(conf_str)
    #             full_text  = full_text.split("CONFIDENCE:")[0].strip()
    #         except Exception:
    #             pass
 
    # except Exception as e:
    #     log.info(f"[DraftResponse] Error: {e}")
    #     full_text  = "Unable to generate analysis. Please try again."
    #     confidence = 0.0
 
    # log.info(f"[DraftResponse] Done — confidence={confidence:.2f}, tool_rounds={rounds}")
    # return {
    #     "draft_response" : full_text,
    #     "confidence_score": confidence,
    #     "agent_status"   : {
    #         **state.get("agent_status", {}),
    #         "draft_response": f"done — confidence={confidence:.2f}"
    #     },
    #     "mcp_tool_calls": tool_calls_log,
    # }
            # Initialise before try — so the print/return below never hit UnboundLocalError
    MAX_TOOL_ROUNDS = 3
    request_id      = state.get("request_id", "")
    rounds          = 0
    tool_calls_log  = list(state.get("mcp_tool_calls", []))
    tool_inputs_log = list(state.get("mcp_tool_inputs", []))

    try:
        client   = get_claude()
        messages = [{"role": "user", "content": prompt}]

        # ── Agentic loop ───────────────────────────────────────────────────────
        # Claude may call tools before writing its final response.
        # Each tool result is fed back. Max 3 rounds to prevent infinite loops.
        while rounds < MAX_TOOL_ROUNDS:
            # response = client.messages.create(
            # response = with_retry(
            #     "claude.draft", client.messages.create,
            #     model      = "claude-sonnet-4-6",
            #     max_tokens = 4096,
            #     tools      = CLAUDE_TOOLS,
            #     messages   = messages
            # )

            response = with_retry(
                "claude.draft", _claude_stream, request_id,
                model      = "claude-sonnet-4-6",
                max_tokens = 4096,
                tools      = CLAUDE_TOOLS,
                messages   = messages,
            )

            if response.stop_reason != "tool_use":
                break

            rounds += 1
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    log.info(f"[DraftResponse] Tool call #{len(tool_calls_log) + 1}: "
                          f"{block.name} input={json.dumps(block.input)}")
                    result = execute_tool(block.name, block.input)
                    tool_results.append({
                        "type"       : "tool_result",
                        "tool_use_id": block.id,
                        "content"    : result
                    })
                    tool_calls_log.append(block.name)
                    tool_inputs_log.append({"tool": block.name, "input": block.input})

            messages.append({"role": "user", "content": tool_results})

        # ── Force final response if loop hit max rounds ────────────────────────
        # Messages contain tool_use blocks, so tools must still be declared —
        # tool_choice "none" forbids further calls and forces the written analysis.
        if response.stop_reason == "tool_use":
            log.info("[DraftResponse] Max tool rounds hit — forcing final response")
            # response = client.messages.create(
            # response = with_retry(
            #     "claude.draft_final", client.messages.create,
            #     model       = "claude-sonnet-4-6",
            #     max_tokens  = 4096,
            #     tools       = CLAUDE_TOOLS,
            #     tool_choice = {"type": "none"},
            #     messages    = messages
            # )

            response = with_retry(
                "claude.draft_final", _claude_stream, request_id,
                model       = "claude-sonnet-4-6",
                max_tokens  = 4096,
                tools       = CLAUDE_TOOLS,
                tool_choice = {"type": "none"},
                messages    = messages,
            )

        if response.stop_reason == "max_tokens":
            log.warning("[DraftResponse] WARNING: response hit max_tokens — output may be truncated")

        # ── Extract final text ─────────────────────────────────────────────────
        full_text = "".join(
            block.text for block in response.content if hasattr(block, "text")
        )
        log.info(f"[DraftResponse] tokens in={response.usage.input_tokens} "
              f"out={response.usage.output_tokens}")

        # Extract and strip the confidence score
        confidence = 0.7  # default
        if "CONFIDENCE:" in full_text:
            try:
                conf_str   = full_text.split("CONFIDENCE:")[-1].strip().split()[0]
                confidence = max(0.0, min(1.0, float(conf_str)))
                full_text  = full_text.split("CONFIDENCE:")[0].strip()
            except Exception:
                pass

    except Exception as e:
        log.error(f"[DraftResponse] Error: {e}")
        full_text  = "Unable to generate analysis. Please try again."
        confidence = 0.0

    log.info(f"[DraftResponse] Done — confidence={confidence:.2f}, tool_rounds={rounds}, "
          f"tools={tool_calls_log}")
    return {
        "draft_response"  : full_text,
        "confidence_score": confidence,
        "mcp_tool_calls"  : tool_calls_log,
        "mcp_tool_inputs" : tool_inputs_log,
        "agent_status"    : {
            **state.get("agent_status", {}),
            "draft_response": f"done — confidence={confidence:.2f}"
        },
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
def escalation_agent(state: dict) -> dict:
    log.info("[Escalation] Running ...")
 
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

    if severity.get("sla_risk"):
        escalate_reasons.append("sla_risk")
 
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
            # response    = groq_client.chat.completions.create(
            response = with_retry(
                "groq.sentiment", groq_client.chat.completions.create,
                # model="llama-3.3-70b-versatile",
                # model="llama3-70b-8192",
                model = "qwen/qwen3.8-27b",
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
            log.info(f"[Escalation] Groq sentiment: {sentiment}")
        except Exception as e:
            log.warning(f"[Escalation] Groq sentiment check failed: {e}")
 
    should_escalate = len(escalate_reasons) > 0
    action          = "human_review" if should_escalate else "show_response"
 
    # ── MCP tools — only called when escalating ────────────────────────────────
    slack_result = {}
    jira_result  = {}
 
    if should_escalate:
        log.info(f"[Escalation] Escalating — reasons: {escalate_reasons}")
 
        # Tool 3: Slack notification
        # slack_result = notify_reviewer(
        #     bug_summary        = f"{bug_title}: {description[:150]}",
        #     severity           = severity.get("severity", "Unknown"),
        #     escalation_reasons = escalate_reasons,
        #     review_url         = os.environ.get("REVIEW_URL", "http://localhost:3000/review")
        # )
        request_id      = state.get("request_id", "")
        base_review_url = os.environ.get("REVIEW_URL", "http://localhost:3000/review")
        review_url      = f"{base_review_url}?id={request_id}" if request_id else base_review_url

        slack_result = notify_reviewer(
            bug_summary        = f"{bug_title}: {description[:150]}",
            severity           = severity.get("severity", "Unknown"),
            escalation_reasons = escalate_reasons,
            review_url         = review_url
        )
        log.info(f"[Escalation] Slack: {slack_result.get('status')}")
 
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
        log.info(f"[Escalation] Jira: {jira_result.get('status')} — {jira_result.get('ticket_key', '')}")
 
    log.info(f"[Escalation] Done — escalate={should_escalate}, reasons={escalate_reasons}")
 
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
 