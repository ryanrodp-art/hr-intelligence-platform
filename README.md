# hr-intelligence-platform

> A multi-agent GenAI platform for HR intelligence, built with LangGraph, RAG, MCP, and DeepEval on GPT-4o.

---

## Overview

ARIA (Agentic Resources Intelligence Assistant) is an end-to-end enterprise-grade GenAI platform built around an HR use case. It demonstrates the full spectrum of modern AI application development — from simple LLM chat to multi-agent orchestration, RAG pipelines, MCP tool servers, vector search, and systematic AI evaluation using DeepEval.

The platform allows employees and HR managers to interact via a conversational chat interface to query company policies, employee records, leave balances, org charts, and benefits — with every response grounded in real data and evaluated for quality.

---

## Use Case — HR Intelligence Platform

An internal HR assistant where:
- **Employees** ask questions about leave policies, benefits, onboarding, and company guidelines
- **HR Managers** query employee records, leave balances, and org structure
- **The platform** routes each query to the right specialist agent, retrieves grounded context from the right data source, takes actions via MCP tools, and evaluates every response for accuracy, faithfulness, and task completion

---

## Architecture

```
User (Streamlit UI)
      │  POST /chat
      ▼
FastAPI Backend
      │
      ▼
LangGraph Orchestrator ──── Agent State (shared)
      │
      ├──► Policy Agent       ──► Document RAG    ──► ChromaDB (policy PDFs)
      ├──► Leave Agent        ──► Database RAG    ──► PostgreSQL (employee records)
      │                                └──► MCP Server (leave tool, org chart)
      ├──► Onboarding Agent   ──► Hybrid Retriever ──► Both RAGs
      ├──► Payroll Agent      ──► Vector Search   ──► ChromaDB (benefits docs)
      └──► Single HR Advisor  ──► Fallback agent for simple queries

All paths ──► DeepEval evaluation hooks (tracing + metrics)
```

---

## Technology Stack

| Layer | Technology |
|---|---|
| LLM | GPT-4o (OpenAI) |
| Agent Orchestration | LangGraph |
| RAG & Chains | LangChain |
| Vector Store | ChromaDB (dev) / PgVector (prod) |
| Document Parsing | PyMuPDF |
| MCP Server | FastMCP |
| Backend API | FastAPI |
| Frontend | Streamlit |
| Database | PostgreSQL |
| Evaluation | DeepEval + Confident AI |
| Containerization | Docker Compose |
| Package Management | uv |
| Language | Python 3.11 |

---

## Project Structure

```
hr-genai-agent-platform/
│
├── README.md
├── .env
├── .env.example
├── docker-compose.yml
├── pyproject.toml
│
├── frontend/                          # Streamlit UI
│   ├── app.py                         # Main entry point
│   ├── pages/
│   │   ├── 01_chat.py                 # Employee chat interface
│   │   ├── 02_hr_dashboard.py         # HR manager view
│   │   └── 03_eval_dashboard.py       # DeepEval metrics dashboard
│   └── components/
│       ├── chat_widget.py
│       └── sidebar.py
│
├── backend/                           # FastAPI backend
│   ├── main.py                        # App entry point
│   ├── api/
│   │   ├── routes/
│   │   │   ├── chat.py                # POST /chat
│   │   │   ├── rag.py                 # POST /rag/query
│   │   │   └── eval.py                # POST /eval/run
│   │   └── middleware/
│   │       ├── auth.py
│   │       └── logging.py
│   └── schemas/
│       ├── chat.py                    # Pydantic request/response models
│       └── eval.py
│
├── agents/                            # LangGraph agents
│   ├── orchestrator/
│   │   ├── graph.py                   # Main LangGraph orchestrator graph
│   │   ├── router.py                  # Intent classification + routing
│   │   └── state.py                   # Shared AgentState TypedDict
│   ├── specialist/
│   │   ├── policy_agent.py            # Answers policy questions
│   │   ├── leave_agent.py             # Handles leave queries + actions
│   │   ├── onboarding_agent.py        # New employee onboarding
│   │   └── payroll_agent.py           # Payroll and benefits
│   └── single/
│       └── hr_advisor.py              # Standalone single agent (fallback)
│
├── rag/                               # RAG pipelines
│   ├── document_rag/
│   │   ├── ingestion.py               # PDF ingestion pipeline
│   │   ├── chunker.py                 # Document chunking strategy
│   │   ├── retriever.py               # Vector store retrieval
│   │   └── chain.py                   # LangChain RAG chain
│   ├── database_rag/
│   │   ├── embedder.py                # Embed DB records into vector store
│   │   ├── retriever.py               # Semantic search over employee records
│   │   └── chain.py                   # LangChain RAG chain
│   └── hybrid_retriever.py            # Queries both RAGs, merges results
│
├── vector_store/                      # Vector search layer
│   ├── store.py                       # ChromaDB wrapper
│   ├── indexer.py                     # Indexing pipeline
│   └── searcher.py                    # Semantic search interface
│
├── mcp_server/                        # MCP server
│   ├── server.py                      # FastMCP server definition
│   └── tools/
│       ├── leave_tool.py              # Check and submit leave balances
│       ├── policy_lookup_tool.py      # Look up specific policy clauses
│       └── org_chart_tool.py          # Org structure queries
│
├── database/                          # Data layer
│   ├── models.py                      # SQLAlchemy models
│   ├── seed_data/
│   │   ├── employees.csv
│   │   ├── leave_records.csv
│   │   └── org_chart.csv
│   └── migrations/
│       └── init.sql
│
├── documents/                         # Source HR documents (ingested into RAG)
│   ├── policies/
│   │   ├── leave_policy.pdf
│   │   ├── code_of_conduct.pdf
│   │   └── benefits_guide.pdf
│   └── handbooks/
│       └── employee_handbook.pdf
│
├── evaluation/                        # DeepEval integration
│   ├── datasets/
│   │   ├── rag_golden_set.json        # Ground truth Q&A for RAG evals
│   │   ├── agent_golden_set.json      # Ground truth for agent evals
│   │   └── mcp_golden_set.json        # Ground truth for MCP evals
│   ├── tests/
│   │   ├── test_chat.py               # Chat quality metrics
│   │   ├── test_document_rag.py       # Document RAG metrics
│   │   ├── test_database_rag.py       # Database RAG metrics
│   │   ├── test_hybrid_rag.py         # Hybrid retrieval metrics
│   │   ├── test_single_agent.py       # Single agent metrics
│   │   ├── test_mcp.py                # MCP metrics
│   │   └── test_multi_agent.py        # Multi-agent metrics
│   ├── metrics/
│   │   └── custom_hr_metric.py        # Custom G-Eval for HR accuracy
│   └── reports/
│       └── .gitkeep
│
├── config/
│   ├── settings.py                    # Pydantic settings (env vars)
│   └── prompts/
│       ├── orchestrator.txt
│       ├── policy_agent.txt
│       ├── leave_agent.txt
│       ├── onboarding_agent.txt
│       └── payroll_agent.txt
│
└── scripts/
├── ingest_documents.py            # Run document ingestion into ChromaDB
├── seed_database.py               # Seed PostgreSQL with employee data
├── run_evals.py                   # Run full DeepEval evaluation suite
└── start_mcp_server.py            # Start the MCP server standalone
```

---

## Build Phases

This project is built incrementally — each phase delivers a working, evaluated feature before moving to the next.

### Phase 0 — Foundation

**Goal:**
Project scaffold, Docker infrastructure, database setup, basic Streamlit UI calling a FastAPI stub.

**Components:**
- Docker Compose
- PostgreSQL
- ChromaDB
- FastAPI skeleton
- Streamlit chat UI
- Seed data

**DeepEval:**
Install and configure. Folder structure created. No tests yet.

**Exit Criteria:**
Streamlit sends a message → FastAPI returns a hardcoded reply → visible in chat UI.

---

### Phase 1 — LLM Chat

**Goal:** First working AI. GPT-4o responds in the Streamlit chat interface via FastAPI.

**Components:**
- LangChain ChatOpenAI
- Streaming responses
- Conversation memory
- HR system prompt

**DeepEval Metrics:**
- `GEval` — role adherence
- `AnswerRelevancyMetric`
- `HallucinationMetric`

**Exit Criteria:** Chat works end-to-end. DeepEval tests pass with threshold ≥ 0.7.

---

### Phase 2 — Document RAG

**Goal:**
Ground LLM responses in real HR policy documents.

**Components:**
- PDF ingestion (PyMuPDF)
- ChromaDB vector store
- LangChain RAG chain
- Source citation in UI

**Documents Ingested:**
- Leave policy
- Code of conduct
- Benefits guide
- Employee handbook

**DeepEval Metrics:**
- `AnswerRelevancyMetric`
- `FaithfulnessMetric`
- `ContextualPrecisionMetric`
- `ContextualRecallMetric`
- RAGAS score

**Exit Criteria:**
"What is the parental leave policy?" returns a grounded, cited answer. All 4 RAG metrics pass.

---

### Phase 3 — Database RAG + Hybrid Retrieval

**Goal:**
Add structured employee data as a second knowledge source. Query both simultaneously.

**Components:**
- Embed PostgreSQL records into ChromaDB
- Hybrid retriever merging both RAGs

**DeepEval Metrics:**
- `FaithfulnessMetric`
- `ContextualRelevancyMetric`
- `HallucinationMetric`

**Exit Criteria:**
"What is Sarah's leave balance and what does the policy say about carryover?" returns accurate data from both sources.

---

### Phase 4 — Vector Search + Single Agent

**Goal:**
First reasoning agent. Decides which tool to call based on the question.

**Components:**
- Semantic search API
- LangChain agent with 3 tools:
  - `search_policies`
  - `lookup_employee`
  - `search_knowledge_base`

**DeepEval Metrics:**
- `TaskCompletionMetric`
- `ToolCorrectnessMetric`
- `GoalAccuracyMetric`

**Exit Criteria:**
Mixed query triggers correct tools. Tool Correctness ≥ 0.8.

---

### Phase 5 — MCP Server

**Goal:**
Give the agent real actions — not just retrieval but writes to the database.

**Components:**
- FastMCP server with 3 tools:
  - `check_leave_balance`
  - `submit_leave_request`
  - `get_org_chart`

**DeepEval Metrics:**
- `MCPTaskCompletionMetric`
- `MCPUseMetric`
- `MultiTurnMCPUseMetric`

**Exit Criteria:**
"Check John's leave and submit a request for Dec 25–27" executes correctly against PostgreSQL.

---

### Phase 6 — Multi-Agent LangGraph Orchestration

**Goal:**
Route queries to specialist agents based on intent. Aggregate responses from multiple agents.

**Components:**
- LangGraph orchestrator graph
- AgentState (shared state across agents)
- Intent router
- 4 specialist agents:
  - `Policy Agent`
  - `Leave Agent`
  - `Onboarding Agent`
  - `Payroll Agent`
- Human-in-the-loop node

**DeepEval Metrics:**
- `TaskCompletionMetric`
- `ToolCorrectnessMetric`
- `StepEfficiencyMetric`
- `PlanAdherenceMetric`
- `PlanQualityMetric`

**Exit Criteria:**
"I'm a new hire — what do I need to know about leave and benefits?" routes to Onboarding + Leave agents and returns a combined response.

---

### Phase 7 — DeepEval Full Suite + CI/CD

**Goal:**
Systematic evaluation of every component. Automated on every code push.

**Components:**
- Complete golden datasets (100 Q&A pairs)
- GitHub Actions CI pipeline
- Confident AI dashboard integration
- Custom HR accuracy G-Eval metric
- Streamlit eval dashboard page

**All Metrics Running:**

| Component | Metrics |
|---|---|
| Chat | `GEval`, `AnswerRelevancyMetric`, `HallucinationMetric` |
| Document RAG | `FaithfulnessMetric`, `ContextualPrecisionMetric`, `ContextualRecallMetric` |
| Database RAG | `FaithfulnessMetric`, `HallucinationMetric`, `ContextualRelevancyMetric` |
| Single Agent | `TaskCompletionMetric`, `ToolCorrectnessMetric`, `GoalAccuracyMetric` |
| MCP | `MCPTaskCompletionMetric`, `MCPUseMetric`, `MultiTurnMCPUseMetric` |
| Multi-Agent | `StepEfficiencyMetric`, `PlanAdherenceMetric`, `PlanQualityMetric` |

**Exit Criteria:**
Full eval suite runs in CI on push to main. Results visible in Confident AI dashboard.


---

### Phase 8 — Polish + Documentation

**Goal:**
Production-ready, portfolio-presentable project.

**Components:**
- Architecture diagram
- One-command Docker startup
- Streamlit agent trace viewer
- Sample data
- Recorded demo

**Exit Criteria:**
`docker compose up` starts the entire stack. README enables a new developer to run it in under 10 minutes.

---

## DeepEval Evaluation Coverage

| Component | Metrics |
|---|---|
| LLM Chat | GEval, Answer Relevancy, Hallucination |
| Document RAG | Faithfulness, Contextual Precision, Contextual Recall, Answer Relevancy, RAGAS |
| Database RAG | Faithfulness, Contextual Relevancy, Hallucination |
| Hybrid RAG | Contextual Relevancy, Answer Relevancy |
| Single Agent | Task Completion, Tool Correctness, Goal Accuracy |
| MCP Server | MCP Task Completion, MCP Use, Multi-Turn MCP Use |
| Multi-Agent | Task Completion, Tool Correctness, Step Efficiency, Plan Adherence, Plan Quality |
| All | Custom G-Eval: HR Accuracy |

---

## Getting Started

### Prerequisites
- Docker Desktop
- Python 3.11+
- OpenAI API key
- uv (Python package manager)

### Quick Start
```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/hr-genai-agent-platform.git
cd hr-genai-agent-platform

# Copy environment variables
cp .env.example .env
# Add your OPENAI_API_KEY to .env

# Start infrastructure
docker compose up -d

# Install dependencies
uv sync

# Seed the database
python scripts/seed_database.py

# Ingest HR documents
python scripts/ingest_documents.py

# Start the backend
uvicorn backend.main:app --reload --port 8000

# Start the frontend (new terminal)
streamlit run frontend/app.py

# Run evaluations
deepeval test run evaluation/tests/
```

---

## Environment Variables

```bash
# .env.example
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o

POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=hr_platform
POSTGRES_USER=hr_user
POSTGRES_PASSWORD=hr_password

CHROMA_HOST=localhost
CHROMA_PORT=8001

DEEPEVAL_API_KEY=...          # From confident-ai.com (optional)

FASTAPI_HOST=localhost
FASTAPI_PORT=8000

MCP_SERVER_HOST=localhost
MCP_SERVER_PORT=8002
```

---

## License

MIT

---

## Author

Built as a learning project to demonstrate end-to-end GenAI and Agentic AI application development using modern AI engineering practices, including integration with the open-source [DeepEval](https://github.com/confident-ai/deepeval) evaluation framework for systematically validating and measuring the performance of every AI component — LLM chat quality, RAG faithfulness and relevancy, MCP tool usage, single agent task completion, and multi-agent orchestration accuracy.