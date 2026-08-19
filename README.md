# 🐛 BugAnalyzer — Multi-Agent System for Automated Bug Resolution

A 5-agent LangGraph pipeline that analyzes software bugs against 100k+ resolved Apache JIRA tickets and returns structured root cause analysis, fix recommendations, and priority assessments — with human-in-the-loop escalation for security and low-confidence cases.

---

## Demo

> *Demo GIF coming soon — deployment in progress*

---

## Architecture

```
User submits bug report (title + description + stack trace + priority)
    ↓
┌─────────────────────────────────────────┐
│  Agent 1: Classifier (Gemini Flash)     |
|                                         │  ← runs in parallel
│  Agent 2: Severity   (Gemini Flash)     │  
└─────────────────────────────────────────┘
    ↓
Agent 3: Retriever
    ├── nomic-embed-text-v1.5 encodes query
    ├── Weaviate fetches top 50 candidates
    └── Cohere Rerank trims to top 15
    ↓
Agent 4: Draft Response (Claude Sonnet)
    ├── MCP tool: get_ticket_details (on demand)
    ├── MCP tool: search_full_dataset (on demand)
    └── Generates 4-section analysis + confidence score
    ↓
Agent 5: Escalation (Rules + Groq Llama 3.3-70B)
    ├── Rule triggers: security, low confidence, no match
    ├── Groq sentiment check for borderline cases
    ├── MCP tool: notify_reviewer → Slack
    └── MCP tool: create_jira_ticket → Atlassian
    ↓
Response to user  OR  Human review queue
```

---

## Features

- **5-agent LangGraph pipeline** — Classifier and Severity run in parallel via ThreadPoolExecutor, cutting latency by ~40%
- **Weaviate + Cohere Rerank retrieval** — 50 semantic candidates reranked to top 15 using Cohere's cross-encoder
- **nomic-embed-text-v1.5 embeddings** — 8192-token context eliminates the 22% truncation seen with 512-token models across the dataset
- **Claude Sonnet with MCP tool access** — agentic loop lets Claude fetch individual ticket details or search for additional matches before writing the analysis
- **Confidence-calibrated escalation** — sub-0.5 confidence, security keywords, and urgent sentiment all trigger escalation
- **Groq Llama 3.3-70B sentiment check** — borderline cases (0.5-0.65 confidence) are routed through a fast sentiment classifier
- **Slack notifications** — real-time escalation alerts sent to reviewer channel with link to review queue
- **Atlassian Jira integration** — escalated bugs automatically create real tickets in your Jira project
- **Human-in-the-loop review queue** — approve/reject AI analysis with reviewer notes
- **Structured audit logging** — every analysis logged to JSONL with confidence, similarity, tool calls, response time, and escalation outcome
- **Circuit breaker pattern** — Slack and Jira outages degrade gracefully; analysis always completes
- **TTL cache** — repeated ticket lookups served from memory, no redundant CSV reads
- **Follow-up chat** — multi-turn conversation with Claude Sonnet grounded in the original analysis
- **Thumbs up/down feedback** — structured feedback collection for downstream evaluation

---

## Escalation Logic

| Trigger | Condition | Action |
|---|---|---|
| Low confidence | score < 0.5 | Escalate + Slack + Jira |
| Security issue | category == "security" | Escalate + Slack + Jira |
| Security keywords | injection, xss, rce, etc. in description | Escalate + Slack + Jira |
| Immediate severity | Gemini flags escalate_immediately | Escalate + Slack + Jira |
| No similar issues | 0 tickets retrieved | Escalate + Slack + Jira |
| Urgent sentiment | Groq detects distress (0.5–0.65 confidence) | Escalate + Slack + Jira |

---

## Repository Structure

```
Multi_Agent_BugAnalyzer/
├── services/
│   ├── app.py                  # FastAPI backend — all endpoints
│   ├── graph.py                # LangGraph graph definition
│   ├── agents.py               # All 5 agents
│   ├── mcp_tools.py            # MCP tools: Slack, Jira, CSV search, ticket lookup
│   ├── audit_log.py            # Structured JSONL audit logging
│   ├── logs/
│   │   └── audit.jsonl         # Audit log (gitignored)
│   └── requirements.txt
│
├── frontend/
│   ├── app/
│   │   ├── page.tsx            # Home — bug input form, example chips
│   │   ├── results/page.tsx    # Results — pipeline viz, sections, feedback
│   │   ├── review/page.tsx     # Human review queue
│   │   └── api/chat/route.ts   # Follow-up chat API route (Claude Sonnet)
│   └── package.json
│
├── data_pipeline/
│   ├── create_dataset.py           # 1.1M → 714k cleaned → train/eval/demo split
│   └── create_embeddings_weaviate.ipynb  # Kaggle T4 GPU embedding pipeline
│
├── .env.example                # Environment variable template
├── .gitignore
└── README.md
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js, React, TypeScript, Tailwind CSS, Vercel |
| Backend | FastAPI, Python, AWS EC2 |
| Orchestration | LangGraph, ThreadPoolExecutor (parallel agents) |
| Vector Store | Weaviate Cloud |
| Embedding Model | nomic-embed-text-v1.5 (8192-token context, 768 dims) |
| Reranking | Cohere Rerank v3 (rerank-english-v3.0) |
| Agent LLMs | Gemini Flash 3.6 (Classifier + Severity), Claude Sonnet (Draft Response), Groq Llama 3.3-70B (Escalation) |
| MCP Tools | Anthropic tool_use API — get_ticket_details, search_full_dataset, notify_reviewer, create_jira_ticket |
| Notifications | Slack Incoming Webhooks |
| Issue Tracking | Atlassian Jira REST API v2 |
| Resilience | Circuit breaker pattern, TTL cache |
| Audit Logging | JSONL append-only structured logs |

---

## How It Works

### 1. Classification and Severity (Parallel)

Two Gemini Flash agents run concurrently. The Classifier assigns category, component, and root cause family, and builds an enriched search query optimized for Weaviate retrieval. The Severity agent independently assesses urgency, SLA risk, and production impact, and flags whether to escalate immediately.

### 2. Retrieval

The enriched query (plus up to 300 chars of stack trace) is embedded using `nomic-embed-text-v1.5` with a `search_query:` prefix. Weaviate returns 50 candidates by cosine similarity. Cohere's cross-encoder reranks them to the top 15 using the original bug description as the query — this two-stage approach catches cases where semantic similarity alone would surface loosely related tickets.

### 3. Draft Response with MCP Tools

Claude Sonnet receives the top 15 tickets and the full bug context. Before writing the analysis, Claude can call two MCP tools: `get_ticket_details` to fetch the full discussion of a specific ticket (the CSV stores up to 4000 chars, plenty for most cases), or `search_full_dataset` to keyword-search the full 100k corpus when the retrieved tickets don't match well. Claude then writes a 4-section markdown analysis and assigns a confidence score.

### 4. Escalation

Rule-based checks run first — no LLM needed for clear cases. For borderline confidence scores (0.5–0.65), Groq Llama 3.3-70B performs a single-word urgency classification. When escalation fires, `notify_reviewer` posts a structured Slack message with severity, reasons, and a link to the review queue. `create_jira_ticket` creates a real ticket in the configured Atlassian project with the full bug context and escalation metadata.

### 5. Human Review

Escalated bugs appear in the `/review` queue. Reviewers can read the AI draft, add notes, and approve or reject. The decision is stored and shown in the UI.

---

## Data Pipeline

Raw dataset: [tedlozzo/apaches-jira-issues](https://www.kaggle.com/datasets/tedlozzo/apaches-jira-issues) — 1.1M Apache JIRA issues across Kafka, Hadoop, Spark, Cassandra, and 100+ other projects.

**Processing steps:**
1. `create_dataset.py` — joins issues + comments, filters to resolved tickets, produces `jira_rag.csv` (714k rows)
2. Stratified split → `jira_train.csv` (95%) + `jira_eval.csv` (5% holdout) + `jira_demo.csv` (100k stratified sample for Weaviate free tier)
3. `create_embeddings_weaviate.ipynb` — runs on Kaggle T4 GPU, embeds `jira_demo.csv` into Weaviate with `search_document:` prefix

**Why nomic-embed-text-v1.5 over BGE-base:**
Token distribution analysis on 714k tickets showed 22% truncation at the 512-token limit. nomic-embed-text-v1.5's 8192-token context reduces truncation to 0% across the full dataset.

---

## Local Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- Weaviate Cloud account (free sandbox)
- API keys for Anthropic, Google (Gemini), Cohere, Groq

### 1. Clone and install

```bash
git clone https://github.com/ketkipatankar18/Multi-Agent-BugAnalyzer.git
cd Multi-Agent-BugAnalyzer
pip install -r services/requirements.txt
cd frontend && npm install
```

### 2. Configure environment

Copy `.env.example` to `services/.env` and fill in:

```bash
cp .env.example services/.env
```

```bash
# Weaviate
WEAVIATE_URL=your_weaviate_cluster_url
WEAVIATE_KEY=your_weaviate_api_key

# LLM APIs
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=your_google_key
COHERE_API_KEY=your_cohere_key
GROQ_API_KEY=your_groq_key

# MCP — Slack
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/xxx/yyy/zzz

# MCP — Jira
JIRA_BASE_URL=https://yourname.atlassian.net
JIRA_EMAIL=your@email.com
JIRA_API_TOKEN=your_atlassian_api_token
JIRA_PROJECT_KEY=SCRUM

# Data
JIRA_CSV_PATH=../jira_demo.csv
AUDIT_LOG_PATH=logs/audit.jsonl
REVIEW_URL=http://localhost:3000/review
```

### 3. Start the backend

```bash
cd services
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Startup loads the embedding model and connects to Weaviate. Takes ~30 seconds on first run.

### 4. Start the frontend

```bash
cd frontend
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/analyze` | Full 5-agent pipeline |
| GET | `/search` | Direct Weaviate search |
| GET | `/health` | Health check |
| POST | `/feedback` | Thumbs up/down feedback |
| GET | `/feedback/summary` | Feedback stats |
| GET | `/review/queue` | Human review queue |
| POST | `/review/{item_id}` | Approve or reject a review item |
| GET | `/audit/logs` | Recent audit log entries |
| GET | `/audit/summary` | Aggregate stats across all analyses |

---

## Key Design Decisions

**Why 5 agents instead of one LLM call?**
Each agent has a distinct job and the best model for that job. Gemini Flash is fast and cheap for classification. Cohere is purpose-built for reranking. Claude Sonnet produces the highest-quality structured analysis. Groq Llama gives sub-second sentiment classification. One LLM call can't specialize.

**Why nomic-embed-text-v1.5 over all-MiniLM or BGE-base?**
Token distribution analysis on the actual dataset showed 22% of tickets exceed 512 tokens. BGE-base and MiniLM silently truncate those tickets during indexing, degrading retrieval quality. nomic's 8192-token context handles the full dataset at 0% truncation.

**Why two-stage retrieval (Weaviate → Cohere Rerank)?**
Weaviate's approximate nearest neighbour search is fast but the similarity score measures embedding distance, not relevance to the specific bug. Cohere's cross-encoder reads the bug description and each ticket together, scoring actual relevance — consistently surfacing better results at the top 15.

**Why MCP tools instead of hardcoded tool calls?**
MCP lets Claude decide when it needs more information rather than always fetching it. When retrieved tickets are directly relevant (similarity > 0.8), Claude skips tool calls and writes immediately. When tickets are loosely matched, Claude calls `search_full_dataset` to find better ones. The agent drives the decision.

**Why circuit breakers for Slack and Jira?**
External API failures should never crash the analysis. A Slack outage means the reviewer doesn't get a notification — it doesn't mean the user should get a 500 error. Circuit breakers absorb the failure, log it, and let the pipeline complete.

---

## Dataset

[Apache JIRA Issues](https://www.kaggle.com/datasets/tedlozzo/apaches-jira-issues) — 1.1M issues from Apache projects including Kafka, Hadoop, Spark, Cassandra, Hive, and 100+ others.

100k stratified sample embedded using `nomic-embed-text-v1.5` and stored in Weaviate Cloud (collection: `JiraIssues`, dims=768, metric=cosine).
