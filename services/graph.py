"""
graph.py
--------
LangGraph graph connecting the 5 BugAnalyzer agents.

Flow:
  START
    └─ parallel_classify_and_assess  (Classifier + Severity run concurrently)
         └─ retriever
              └─ draft_response
                   └─ escalation
                        └─ END

The graph takes a BugAnalyzerState dict and returns the fully populated state.
"""

from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END, START
from functools import partial

from agents import (
    parallel_classify_and_assess,
    retriever_agent,
    draft_response_agent,
    escalation_agent,
)

# from services.agents import (
#     parallel_classify_and_assess,
#     retriever_agent,
#     draft_response_agent,
#     escalation_agent,
# )

# ── State definition ──────────────────────────────────────────────────────────
class BugAnalyzerState(TypedDict, total=False):
    # ── Inputs ────────────────────────────────────────────────────────────────
    issue_description : str        # full bug description (title + desc + stack)
    bug_title         : str        # short bug title
    stack_trace       : str        # optional stack trace / error message
    user_priority     : str        # priority claimed by user

    # ── Agent outputs ─────────────────────────────────────────────────────────
    classification    : dict       # from Classifier Agent
    severity_assessment: dict      # from Severity Agent
    retrieved_issues  : list       # from Retriever Agent (reranked)
    draft_response    : str        # from Draft Response Agent
    confidence_score  : float      # from Draft Response Agent
    escalation_decision: dict      # from Escalation Agent

    # ── Metadata ──────────────────────────────────────────────────────────────
    agent_status      : dict       # tracks completion of each agent for frontend
    mcp_tool_calls    : list 

# ── Build graph ───────────────────────────────────────────────────────────────
def build_graph(query_weaviate_fn):
    """
    query_weaviate_fn: injected from app.py to give Retriever Agent
                       access to the Weaviate client without circular imports.
    """
    workflow = StateGraph(BugAnalyzerState)

    # Retriever needs query_weaviate injected — use partial
    retriever_with_fn = partial(retriever_agent, query_weaviate_fn=query_weaviate_fn)

    # ── Register nodes ────────────────────────────────────────────────────────
    workflow.add_node("parallel_start",   parallel_classify_and_assess)
    workflow.add_node("retriever",        retriever_with_fn)
    workflow.add_node("draft_response",   draft_response_agent)
    workflow.add_node("escalation",       escalation_agent)

    # ── Define edges (linear after the parallel start) ────────────────────────
    workflow.add_edge(START,              "parallel_start")
    workflow.add_edge("parallel_start",   "retriever")
    workflow.add_edge("retriever",        "draft_response")
    workflow.add_edge("draft_response",   "escalation")
    workflow.add_edge("escalation",       END)

    return workflow.compile()