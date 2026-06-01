# ARIA — HR GenAI Agent Platform
## Master Build Plan

> Complete 9-phase roadmap for building ARIA from infrastructure scaffold to a production-ready,
> multi-agent GenAI platform with full DeepEval evaluation coverage.

**May 2026 | 9 Phases (0–8) | Python 3.11 | GPT-4o | LangGraph + LangChain + DeepEval**

---

## What We Are Building

ARIA (Agentic Resources Intelligence Assistant) is an enterprise-grade GenAI platform built around an
HR use case. It demonstrates the full spectrum of modern AI application development — from a simple
LLM chat interface to multi-agent orchestration, RAG pipelines, MCP tool servers, and systematic
AI evaluation.

The platform allows employees and HR managers to interact via a conversational chat interface to
query company policies, employee records, leave balances, org charts, and benefits — with every
response grounded in real data and evaluated for quality.

---

## Platform Architecture (Final State)

```
User (Streamlit UI)
      │  POST /chat  |  POST /rag/query  |  POST /rag/db/query
      ▼
FastAPI Backend  ──── Query Router (rag | db | chat)
      │
      ├──► Document RAG Chain    ──► ChromaDB (policy PDFs)
      ├──► Database RAG Chain    ──► PostgreSQL (employee records)
      ├──► Single HR Advisor     ──► LangChain Agent + 3 tools
      │         └──► MCP Server  ──► check_leave_balance
      │                              submit_leave_request
      │                              get_org_chart
      └──► LangGraph Orchestrator ── AgentState (shared)
                │
                ├──► Policy Agent     ──► Document RAG → ChromaDB
                ├──► Leave Agent      ──► Database RAG → PostgreSQL + MCP
                ├──► Onboarding Agent ──► Hybrid Retriever → Both RAGs
                └──► Payroll Agent    ──► Vector Search → ChromaDB

All paths ──► DeepEval evaluation hooks (tracing + metrics)
             └──► Confident AI dashboard (Phase 7)
```

---

## Technology Stack

| Layer | Technology | Version |
|---|---|---|
| LLM | OpenAI GPT-4o | via langchain-openai |
| Agent Orchestration | LangGraph | ≥ 0.2.0 |
| Chains & Memory | LangChain | ≥ 0.3.0 |
| Embeddings | OpenAI text-embedding-3-small | via langchain-openai |
| Vector Store | ChromaDB | ≥ 0.5.0 |
| Document Parsing | PyMuPDF | ≥ 1.24.0 |
| MCP Server | FastMCP | latest |
| Backend API | FastAPI | ≥ 0.115.0 |
| Frontend | Streamlit | ≥ 1.40.0 |
| Database | PostgreSQL 16 | via Docker |
| ORM | SQLAlchemy | ≥ 2.0.0 |
| Evaluation | DeepEval | ≥ 1.0.0 |
| Evaluation Dashboard | Confident AI | cloud |
| Package Manager | uv | latest |
| Containerisation | Docker Compose | latest |
| Language | Python | 3.11+ |

---

## Phase Status Overview

| Phase | Name | Status | Steps | Test Cases | Pass Rate |
|---|---|---|---|---|---|
| **0** | Foundation | ✅ Complete | 14 | — | — |
| **1** | LLM Chat | ✅ Complete | 4 | 24 | 100% |
| **2** | Document RAG | ✅ Complete | 9 | 26 | 100% |
| **3** | Database RAG | ✅ Complete | 8 | 13 routing | 100% |
| **4** | Vector Search + Single Agent | 🔲 Planned | — | — | — |
| **5** | MCP Server | 🔲 Planned | — | — | — |
| **6** | Multi-Agent LangGraph | 🔲 Planned | — | — | — |
| **7** | DeepEval Full Suite + CI/CD | 🔲 Planned | — | — | — |
| **8** | Polish + Documentation | 🔲 Planned | — | — | — |

---

## Phase 0 — Foundation ✅

> *Build the restaurant before hiring any chefs.*

**Goal:** Project scaffold, Docker infrastructure, database models, and a Streamlit UI that calls a
FastAPI stub endpoint. No AI yet — just a working skeleton that every future phase builds on.

### What We Accomplished

| # | Step | What Was Built |
|---|---|---|
| 1 | Project Structure | 22 folders with `.gitkeep` placeholders |
| 2 | Docker Compose | PostgreSQL 16 on port 5432, ChromaDB on port 8001 |
| 3 | pyproject.toml | All dependencies declared — uv sync installs the full stack |
| 4 | `.env.example` + `config/settings.py` | Pydantic BaseSettings config layer, singleton pattern |
| 5 | `database/models.py` | 3 SQLAlchemy ORM models: Employee, LeaveRecord, OrgChart |
| 6 | `database/migrations/init.sql` | PostgreSQL tables + indexes on key query columns |
| 7 | Seed Data CSVs | 50 employees, 30 leave records, 50 org chart rows |
| 8 | `scripts/seed_database.py` | Idempotent CSV → PostgreSQL loader |
| 9 | `backend/schemas/chat.py` | Pydantic ChatRequest / ChatResponse models |
| 10 | `backend/main.py` | FastAPI app — `GET /health`, `POST /chat` stub |
| 11 | `frontend/app.py` | Streamlit chat UI with session state and sidebar |
| 12 | `.gitignore` | Protects `.env` and secrets from commits |
| 13 | `evaluation/` structure | DeepEval folder scaffold, golden set placeholders, conftest.py |
| 14 | Exit criteria verification | Full stack smoke test — all 15 checks pass |

### Key Files Created

```
backend/main.py              — FastAPI app entry point
backend/schemas/chat.py      — ChatRequest / ChatResponse Pydantic models
config/settings.py           — Pydantic BaseSettings, database_url + chroma_url computed fields
database/models.py           — Employee (13 cols), LeaveRecord (9 cols), OrgChart (6 cols)
database/migrations/init.sql — CREATE TABLE + CREATE INDEX statements
database/seed_data/*.csv     — 50 + 30 + 50 = 130 rows of realistic HR data
scripts/seed_database.py     — Idempotent seeding script
frontend/app.py              — Streamlit chat UI
docker-compose.yml           — PostgreSQL + ChromaDB services
.env.example                 — Configuration template
evaluation/tests/conftest.py — DeepEval pytest session fixture
```

### DeepEval

Structure created. No test cases yet — judge LLM configured in `conftest.py`.

### Exit Criteria

Streamlit sends a message → FastAPI returns a hardcoded reply → visible in chat UI.

---

## Phase 1 — LLM Chat ✅

> *First working AI — GPT-4o responds in the Streamlit chat interface via FastAPI.*

**Goal:** Replace the hardcoded stub with real GPT-4o intelligence. The `/chat` endpoint gets wired
to LangChain with streaming responses and per-session conversation memory.

### What We Accomplished

| # | Step | File Created / Modified | What Was Built |
|---|---|---|---|
| 1 | LangChain Chat Chain | `backend/chains/chat_chain.py` | GPT-4o connection + per-session memory |
| 2 | FastAPI Chat Route | `backend/api/routes/chat.py` + `backend/main.py` | Live `/chat` + `/chat/stream` endpoints |
| 3 | Streaming | All three layers updated | Token-by-token SSE streaming to Streamlit |
| 4 | DeepEval Tests | `evaluation/tests/test_chat.py` + golden dataset | 24 test cases, 100% pass rate |

### Key Technical Decisions

- **`RunnableWithMessageHistory`** over deprecated `ConversationChain` — LangChain 0.3+ modern pattern
- **Per-session memory** — `_memory_store` dict keyed by `session_id`, persists for server lifetime
- **Streaming via SSE** — FastAPI `StreamingResponse` + Streamlit `st.write_stream()` for word-by-word display
- **HR system prompt** — ARIA persona, domain scope, and refusal guidelines baked into every request

### Key Files Created

```
backend/chains/chat_chain.py        — RunnableWithMessageHistory chain, ARIA_SYSTEM_PROMPT
backend/chains/__init__.py          — Package marker
backend/api/routes/chat.py          — POST /chat, POST /chat/stream
evaluation/tests/test_chat.py       — 5 test functions, 24 test cases
evaluation/datasets/agent_golden_set.json  — 20-entry HR Q&A golden dataset
```

### DeepEval Metrics

| Metric | Threshold | Result |
|---|---|---|
| `GEval` — role adherence | ≥ 0.7 | ✅ Pass |
| `AnswerRelevancyMetric` | ≥ 0.7 | ✅ Pass |
| `HallucinationMetric` | ≥ 0.7 | ✅ Pass |

**24 test cases — 100% pass rate**

### Exit Criteria

ARIA responds to HR questions with GPT-4o intelligence. Conversation history persists across messages
in the same session. All 3 DeepEval metrics pass at threshold ≥ 0.7.

---

## Phase 2 — Document RAG ✅

> *Ground ARIA's answers in real company documents.*

**Goal:** ARIA retrieves specific passages from HR policy PDFs and cites her source document and page
number in every grounded response. Eliminates hallucination on policy questions.

**The transformation:**
```
Phase 1 — General knowledge:
"Parental leave typically provides paid time off for new parents."
(vague, generic, unverifiable)

Phase 2 — Grounded in company documents:
"Per our Leave Policy (Page 1), primary caregivers receive 16 weeks of
fully paid parental leave. Employees must give 8 weeks written notice."
(specific, accurate, cited)
```

### What We Accomplished

| # | Step | File(s) Created | What Was Built |
|---|---|---|---|
| 1 | HR Policy Documents | `documents/policies/*.pdf`, `documents/handbooks/*.pdf` | 4 source PDF documents |
| 2 | Ingestion Pipeline | `rag/document_rag/ingestion.py` | PyMuPDF text extraction with page metadata |
| 3 | Chunking Strategy | `rag/document_rag/chunker.py` | RecursiveCharacterTextSplitter — 800 chars, 100 overlap |
| 4 | Vector Store + Indexer | `vector_store/store.py`, `vector_store/indexer.py` | 19 embedded chunks in ChromaDB |
| 5 | Retriever | `rag/document_rag/retriever.py` | Similarity search + source citation metadata |
| 6 | RAG Chain | `rag/document_rag/chain.py` | Grounded GPT-4o answers at temperature=0.1 |
| 7 | FastAPI RAG Endpoints | `backend/api/routes/rag.py`, `backend/chains/rag_router.py` | `/rag/query`, `/rag/stream`, `/rag/classify`, `/rag/status` |
| 8 | Streamlit UI Update | `frontend/app.py` updated | Routing badges + source citation display |
| 9 | DeepEval RAG Tests | `evaluation/tests/test_document_rag.py` | 5 test functions, 26 cases, 100% pass rate |

### Documents Ingested

| Document | Location | Contents |
|---|---|---|
| Leave Policy | `documents/policies/leave_policy.pdf` | Annual, sick, parental, emergency leave entitlements |
| Code of Conduct | `documents/policies/code_of_conduct.pdf` | Workplace behaviour, disciplinary process |
| Benefits Guide | `documents/policies/benefits_guide.pdf` | Health insurance, pension, flexible working |
| Employee Handbook | `documents/handbooks/employee_handbook.pdf` | Onboarding, IT setup, company values |

### Key Technical Decisions

- **Embedding model:** `text-embedding-3-small` — cost-efficient, high quality for domain-specific HR text
- **Chunk size:** 800 characters with 100-character overlap — balances context and precision
- **ChromaDB collection:** `hr_policies` — all 4 documents indexed as 19 chunks
- **RAG temperature:** `0.1` — low temperature for factual, consistent policy answers
- **Two-way router:** `"rag"` (policy question) | `"chat"` (general conversation)
- **Citation format:** Source filename + page number appended to every RAG response

### Key Files Created

```
rag/document_rag/ingestion.py             — PyMuPDF PDF loader
rag/document_rag/chunker.py               — RecursiveCharacterTextSplitter
rag/document_rag/retriever.py             — ChromaDB similarity search + citations
rag/document_rag/chain.py                 — RAG chain at temperature=0.1
vector_store/store.py                     — ChromaDB HTTP client wrapper
vector_store/indexer.py                   — Ingestion → chunking → embedding → storage
backend/api/routes/rag.py                 — /rag/query, /rag/stream, /rag/classify, /rag/status
backend/chains/rag_router.py              — Two-way query classifier
scripts/ingest_documents.py               — CLI ingestion runner
evaluation/tests/test_document_rag.py     — RAG evaluation suite
evaluation/datasets/rag_golden_set.json   — RAG Q&A ground truth dataset
```

### DeepEval Metrics

| Metric | What It Measures | Threshold | Result |
|---|---|---|---|
| `FaithfulnessMetric` | Every claim is grounded in retrieved context | ≥ 0.7 | ✅ Pass |
| `AnswerRelevancyMetric` | Response directly addresses the question | ≥ 0.7 | ✅ Pass |
| `ContextualPrecisionMetric` | Retrieved chunks are all relevant (no noise) | ≥ 0.7 | ✅ Pass |
| `ContextualRecallMetric` | All necessary context was retrieved | ≥ 0.7 | ✅ Pass |
| `HallucinationMetric` | LLM did not add facts not in retrieved context | ≥ 0.7 | ✅ Pass |

**26 test cases — 100% pass rate**

### Exit Criteria

"What is the parental leave policy?" returns a grounded, cited answer from `leave_policy.pdf`.
All 5 RAG DeepEval metrics pass at threshold ≥ 0.7.

---

## Phase 3 — Database RAG ✅

> *Give ARIA a second knowledge source — live employee data from PostgreSQL.*

**Goal:** ARIA can now answer factual questions about specific employees (leave balances, departments,
managers, org chart) by translating natural language into safe SQL and querying PostgreSQL live.

**The transformation:**
```
Phase 2 — Policy documents only:
"How many leave days does James Chen have?"
ARIA: "I don't have that in our documents. Please contact HR."
(correct refusal — not a document question)

Phase 3 — Policies + live database:
"How many leave days does James Chen have?"
ARIA: "James Chen has 30 days of leave remaining."
(specific, accurate, live database query)
```

### What We Accomplished

| # | Step | File(s) Created / Updated | What Was Built |
|---|---|---|---|
| 1 | Database Schema Context | `rag/database_rag/schema.py` | Schema description for NL-to-SQL prompting |
| 2 | NL-to-SQL Engine | `rag/database_rag/nl_to_sql.py` | GPT-4o translates natural language to validated SQL |
| 3 | SQL Executor | `rag/database_rag/executor.py` | Safe SQLAlchemy execution + date serialisation |
| 4 | Database RAG Chain | `rag/database_rag/chain.py` | Complete NL → SQL → answer pipeline at temperature=0 |
| 5 | Three-way Query Router | `backend/chains/rag_router.py` updated | `"rag"` / `"db"` / `"chat"` classification |
| 6 | FastAPI DB Endpoints | `backend/api/routes/rag.py` updated | `/rag/db/query`, `/rag/db/stream` |
| 7 | Streamlit DB UI | `frontend/app.py` updated | DB routing badge + SQL expander (shows generated SQL) |
| 8 | DeepEval Database Tests | `evaluation/tests/test_database_rag.py` | 4 test functions, 13 routing assertions |

### Key Technical Decisions

- **NL-to-SQL over embeddings:** Employee records are structured and exact — SQL is more precise than
  vector similarity for "how many days does James Chen have?"
- **Safety validation:** SQL is inspected before execution — only SELECT statements allowed, no writes
- **Temperature=0:** Database answers must be deterministic — no creative variation in factual lookups
- **Key routing rule:** If the question mentions a specific person by name → always route to `"db"`.
  No exception. This prevents the router from looking up employee data in PDF documents.
- **SQL expander in UI:** Users can expand a panel to see the exact SQL generated — builds trust and
  aids debugging
- **Three-way router upgrade:** Two-way router from Phase 2 (`rag` | `chat`) extended to
  three-way (`rag` | `db` | `chat`)

### Key Files Created

```
rag/database_rag/schema.py                — Schema description string for NL-to-SQL prompting
rag/database_rag/nl_to_sql.py             — GPT-4o NL-to-SQL engine with safety validation
rag/database_rag/executor.py              — SQLAlchemy executor with date serialisation
rag/database_rag/chain.py                 — Full NL → SQL → natural language answer chain
backend/chains/rag_router.py              — Updated to three-way classification
evaluation/tests/test_database_rag.py     — 4 test functions, 13 routing assertions
```

### DeepEval Metrics

| Metric | What It Measures | Threshold | Result |
|---|---|---|---|
| Routing correctness | `"db"` path triggered for employee questions | 100% | ✅ Pass |
| Routing correctness | `"rag"` path triggered for policy questions | 100% | ✅ Pass |
| Routing correctness | `"chat"` path triggered for general questions | 100% | ✅ Pass |
| SQL safety | Only SELECT statements produced | 100% | ✅ Pass |

**13 routing assertions — 100% pass rate**

### Exit Criteria

"How many leave days does James Chen have?" returns the exact value from PostgreSQL.
The three-way router correctly classifies `"rag"` / `"db"` / `"chat"` queries.
The SQL expander shows the generated query in the Streamlit UI.

---

## Phase 4 — Vector Search + Single Agent 🔲

> *First reasoning agent — ARIA decides which tool to call based on the question.*

**Goal:** Introduce a LangChain ReAct agent that reasons over which retrieval tool to invoke.
Instead of a rule-based router, the agent uses its own judgment to choose between policy search,
employee lookup, and knowledge base search. This is the first step from retrieval to reasoning.

### What Will Be Built

| # | Step | File(s) | What It Delivers |
|---|---|---|---|
| 1 | Semantic Search API | `vector_store/searcher.py` | Standalone similarity search endpoint |
| 2 | Agent Tools | `agents/single/tools.py` | 3 LangChain tools wired to RAG and database |
| 3 | Single HR Advisor | `agents/single/hr_advisor.py` | ReAct agent with tool selection logic |
| 4 | FastAPI Agent Route | `backend/api/routes/agent.py` | `/agent/query` endpoint |
| 5 | Streamlit Agent UI | `frontend/app.py` updated | Agent reasoning trace display |
| 6 | DeepEval Agent Tests | `evaluation/tests/test_single_agent.py` | Tool correctness evaluation |

### Agent Tools

| Tool | What It Does | Backs Into |
|---|---|---|
| `search_policies` | Retrieves relevant policy passages for a question | Document RAG → ChromaDB |
| `lookup_employee` | Looks up specific employee data | Database RAG → PostgreSQL |
| `search_knowledge_base` | Broad semantic search across all indexed content | ChromaDB vector store |

### DeepEval Metrics

| Metric | What It Measures |
|---|---|
| `TaskCompletionMetric` | Did the agent complete the user's task? |
| `ToolCorrectnessMetric` | Did the agent choose the right tool for the question? |
| `GoalAccuracyMetric` | Does the final answer meet the user's original intent? |

### Exit Criteria

A mixed query ("What is the leave policy and how many days does Sarah have?") triggers the correct
tools in the correct order. `ToolCorrectnessMetric` ≥ 0.8.

---

## Phase 5 — MCP Server 🔲

> *Give the agent real actions — not just retrieval but writes to the database.*

**Goal:** Build a FastMCP tool server that gives the agent the ability to perform actions on
PostgreSQL — checking leave balances and actually submitting leave requests — not just reading data.

### What Will Be Built

| # | Step | File(s) | What It Delivers |
|---|---|---|---|
| 1 | MCP Server Setup | `mcp_server/server.py` | FastMCP server entry point |
| 2 | Leave Tool | `mcp_server/tools/leave_tool.py` | `check_leave_balance`, `submit_leave_request` |
| 3 | Org Chart Tool | `mcp_server/tools/org_chart_tool.py` | `get_org_chart` — reporting chain lookup |
| 4 | Policy Lookup Tool | `mcp_server/tools/policy_lookup_tool.py` | `policy_lookup` — clause search by keyword |
| 5 | Agent MCP Integration | `agents/single/hr_advisor.py` updated | Agent wired to MCP server tools |
| 6 | MCP Start Script | `scripts/start_mcp_server.py` | CLI runner for standalone MCP server |
| 7 | DeepEval MCP Tests | `evaluation/tests/test_mcp.py` | MCP tool usage evaluation |

### MCP Tools

| Tool | Action | Writes to DB? |
|---|---|---|
| `check_leave_balance` | Fetch employee's current leave balance | No |
| `submit_leave_request` | Insert a new LeaveRecord row | **Yes** |
| `get_org_chart` | Return the reporting chain for an employee | No |
| `policy_lookup` | Search policy documents for a specific clause | No |

### DeepEval Metrics

| Metric | What It Measures |
|---|---|
| `MCPTaskCompletionMetric` | Did the MCP tool execute the task successfully? |
| `MCPUseMetric` | Did the agent invoke the correct MCP tool? |
| `MultiTurnMCPUseMetric` | Did the agent handle multi-step MCP sequences correctly? |

### Exit Criteria

"Check John's leave balance and submit a request for December 25–27" executes both MCP tools in the
correct order and writes the leave record to PostgreSQL. All 3 MCP metrics pass.

---

## Phase 6 — Multi-Agent LangGraph Orchestration 🔲

> *Route queries to specialist agents based on intent. Aggregate responses from multiple agents.*

**Goal:** Replace the single HR advisor agent with a LangGraph orchestrator that routes each query
to one or more specialist agents based on intent classification. Complex queries that span multiple
domains (leave + policy, onboarding + benefits) are handled by multiple agents in parallel.

### What Will Be Built

| # | Step | File(s) | What It Delivers |
|---|---|---|---|
| 1 | Agent State | `agents/orchestrator/state.py` | Shared `AgentState` TypedDict |
| 2 | Intent Router | `agents/orchestrator/router.py` | LLM-based intent classification node |
| 3 | Policy Agent | `agents/specialist/policy_agent.py` | Document RAG specialist |
| 4 | Leave Agent | `agents/specialist/leave_agent.py` | Database RAG + MCP specialist |
| 5 | Onboarding Agent | `agents/specialist/onboarding_agent.py` | Hybrid retriever specialist |
| 6 | Payroll Agent | `agents/specialist/payroll_agent.py` | Benefits + payroll specialist |
| 7 | Orchestrator Graph | `agents/orchestrator/graph.py` | LangGraph StateGraph wiring all agents |
| 8 | Human-in-the-Loop | Graph node | Interrupt + approval for write operations |
| 9 | FastAPI Integration | `backend/main.py` updated | Orchestrator wired into `/chat` endpoint |
| 10 | Agent Prompts | `config/prompts/*.txt` | System prompt per specialist agent |
| 11 | DeepEval Agent Tests | `evaluation/tests/test_multi_agent.py` | Multi-agent quality evaluation |

### Specialist Agents

| Agent | Domain | Data Sources |
|---|---|---|
| `Policy Agent` | HR policies, procedures, compliance | Document RAG → ChromaDB |
| `Leave Agent` | Leave balances, requests, approval | Database RAG → PostgreSQL + MCP |
| `Onboarding Agent` | New hire guidance, setup, orientation | Hybrid retriever → Both RAGs |
| `Payroll Agent` | Benefits, payroll, compensation | Vector search → ChromaDB |

### LangGraph Flow

```
User query
    │
    ▼
Intent Router Node ──► Single domain? ──► Route to 1 specialist agent
                  └──► Multi domain?  ──► Route to 2+ agents in parallel
                                                │
                                         Aggregate responses
                                                │
                                    Human-in-the-loop check
                                    (for write operations)
                                                │
                                          Final response
```

### DeepEval Metrics

| Metric | What It Measures |
|---|---|
| `TaskCompletionMetric` | Did the orchestrator complete the user's full request? |
| `ToolCorrectnessMetric` | Did routing select the correct specialist agent(s)? |
| `StepEfficiencyMetric` | Did the graph take the minimum steps needed? |
| `PlanAdherenceMetric` | Did agents follow their assigned role? |
| `PlanQualityMetric` | Was the overall execution plan appropriate? |

### Exit Criteria

"I'm a new hire — what do I need to know about leave and benefits?" routes to both the Onboarding
Agent and the Leave Agent and returns a combined, coherent response. All 5 metrics pass.

---

## Phase 7 — DeepEval Full Suite + CI/CD 🔲

> *Systematic evaluation of every component. Automated on every code push.*

**Goal:** Make evaluation a first-class engineering practice. Every component has a complete golden
dataset. Every push to main triggers the full eval suite automatically. Results are visible in the
Confident AI dashboard.

### What Will Be Built

| # | Step | File(s) | What It Delivers |
|---|---|---|---|
| 1 | Complete golden datasets | `evaluation/datasets/*.json` | 100 Q&A pairs across all components |
| 2 | Custom HR metric | `evaluation/metrics/custom_hr_metric.py` | G-Eval for HR policy accuracy |
| 3 | Full test suite | `evaluation/tests/test_*.py` (all 7 files) | All components evaluated |
| 4 | Eval runner script | `scripts/run_evals.py` | One-command full suite execution |
| 5 | GitHub Actions CI | `.github/workflows/eval.yml` | Automated eval on push to main |
| 6 | Confident AI integration | `evaluation/tests/conftest.py` updated | Cloud dashboard with results |
| 7 | Streamlit eval dashboard | `frontend/pages/03_eval_dashboard.py` | In-app metrics viewer |

### Golden Datasets (Target: 100 Total Q&A Pairs)

| Dataset | File | Target Pairs | Coverage |
|---|---|---|---|
| Chat | `agent_golden_set.json` | 20 | HR chat quality, refusals, memory |
| Document RAG | `rag_golden_set.json` | 30 | Policy questions with citations |
| Database RAG | `rag_golden_set.json` | 20 | Employee queries, SQL accuracy |
| MCP Tools | `mcp_golden_set.json` | 15 | Tool invocation sequences |
| Multi-Agent | `agent_golden_set.json` | 15 | Cross-domain routing scenarios |

### Full DeepEval Metric Coverage

| Component | Metrics |
|---|---|
| LLM Chat | `GEval`, `AnswerRelevancyMetric`, `HallucinationMetric` |
| Document RAG | `FaithfulnessMetric`, `ContextualPrecisionMetric`, `ContextualRecallMetric`, `AnswerRelevancyMetric`, RAGAS |
| Database RAG | `FaithfulnessMetric`, `ContextualRelevancyMetric`, `HallucinationMetric` |
| Single Agent | `TaskCompletionMetric`, `ToolCorrectnessMetric`, `GoalAccuracyMetric` |
| MCP Server | `MCPTaskCompletionMetric`, `MCPUseMetric`, `MultiTurnMCPUseMetric` |
| Multi-Agent | `TaskCompletionMetric`, `ToolCorrectnessMetric`, `StepEfficiencyMetric`, `PlanAdherenceMetric`, `PlanQualityMetric` |
| All components | `CustomHRAccuracyMetric` (G-Eval for HR policy correctness) |

### Exit Criteria

Full eval suite runs automatically on every push to main via GitHub Actions. All metrics pass at
threshold ≥ 0.7. Results are visible in the Confident AI cloud dashboard.

---

## Phase 8 — Polish + Documentation 🔲

> *Production-ready, portfolio-presentable project.*

**Goal:** Make the platform runnable by a new developer in under 10 minutes with a single command.
Add visual traces, a recorded demo, and a complete architecture diagram.

### What Will Be Built

| # | Deliverable | What It Is |
|---|---|---|
| 1 | Architecture diagram | Visual diagram of the complete system (all components + data flows) |
| 2 | One-command startup | `docker compose up` starts the entire stack — no manual steps |
| 3 | Agent trace viewer | Streamlit page showing LangGraph execution steps per query |
| 4 | Streamlit multi-page app | `frontend/pages/01_chat.py`, `02_hr_dashboard.py`, `03_eval_dashboard.py` |
| 5 | HR manager dashboard | `frontend/pages/02_hr_dashboard.py` — employee record browser |
| 6 | README update | Quick start in ≤ 10 minutes, architecture explanation, demo link |
| 7 | Recorded demo | Screen recording of the full platform in action |
| 8 | Sample data | Pre-ingested ChromaDB snapshot so new installs skip the ingest step |

### Exit Criteria

`docker compose up` starts the entire stack. `streamlit run frontend/app.py` launches a fully
functional 3-page app. A new developer can run the platform in under 10 minutes by following the
README alone.

---

## DeepEval Evaluation Philosophy

ARIA measures quality at every layer. Rather than testing the system as a black box, each component
has its own dedicated metrics and golden dataset so failures can be traced to the exact subsystem.

```
User question
      │
      ├──► Chat quality    → GEval, AnswerRelevancy, Hallucination
      ├──► RAG retrieval   → ContextualPrecision, ContextualRecall
      ├──► RAG generation  → Faithfulness, AnswerRelevancy
      ├──► Agent reasoning → TaskCompletion, ToolCorrectness, GoalAccuracy
      ├──► MCP actions     → MCPTaskCompletion, MCPUse, MultiTurnMCPUse
      ├──► Multi-agent     → StepEfficiency, PlanAdherence, PlanQuality
      └──► All components  → CustomHRAccuracyMetric (domain-specific G-Eval)
```

The judge LLM for all metrics is GPT-4o (configured in `evaluation/tests/conftest.py`).
Results are streamed to Confident AI for trend analysis and regression detection in Phase 7.

---

## Running the Platform

### Prerequisites

- Docker Desktop running
- Python 3.11+
- `uv` installed (`pip install uv`)
- OpenAI API key

### Start the Full Stack

```bash
# 1. Clone and configure
git clone https://github.com/ryanrodp-art/hr-intelligence-platform.git
cd hr-intelligence-platform
cp .env.example .env
# Add OPENAI_API_KEY to .env

# 2. Install dependencies
uv sync

# 3. Start infrastructure
docker compose up -d

# 4. Seed the database
uv run python scripts/seed_database.py

# 5. Ingest HR documents into ChromaDB
uv run python scripts/ingest_documents.py

# 6. Start backend (terminal 1)
uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# 7. Start frontend (terminal 2)
uv run streamlit run frontend/app.py --server.port 8501

# 8. Run evaluations
deepeval test run evaluation/tests/
```

### Service URLs

| Service | URL |
|---|---|
| Streamlit UI | http://localhost:8501 |
| FastAPI docs | http://localhost:8000/docs |
| FastAPI health | http://localhost:8000/health |
| ChromaDB API | http://localhost:8001/api/v2/heartbeat |
| MCP Server | http://localhost:8002 |
| PostgreSQL | localhost:5432 |

---

## Phase-by-Phase File Map

```
hr-intelligence-platform/
│
├── backend/
│   ├── main.py                          Phase 0 — FastAPI app entry point
│   ├── schemas/chat.py                  Phase 0 — Pydantic request/response models
│   ├── chains/
│   │   ├── chat_chain.py                Phase 1 — LangChain chat chain + memory
│   │   └── rag_router.py                Phase 2/3 — Query classifier (rag|db|chat)
│   └── api/routes/
│       ├── chat.py                      Phase 1 — /chat, /chat/stream
│       ├── rag.py                       Phase 2/3 — /rag/query, /rag/stream, /rag/db/query
│       └── agent.py                     Phase 4 — /agent/query
│
├── rag/
│   ├── document_rag/
│   │   ├── ingestion.py                 Phase 2 — PyMuPDF PDF loader
│   │   ├── chunker.py                   Phase 2 — Text splitter
│   │   ├── retriever.py                 Phase 2 — ChromaDB similarity search
│   │   └── chain.py                     Phase 2 — RAG chain
│   └── database_rag/
│       ├── schema.py                    Phase 3 — Schema context for NL-to-SQL
│       ├── nl_to_sql.py                 Phase 3 — GPT-4o NL-to-SQL engine
│       ├── executor.py                  Phase 3 — Safe SQL executor
│       └── chain.py                     Phase 3 — Database RAG chain
│
├── vector_store/
│   ├── store.py                         Phase 2 — ChromaDB HTTP client wrapper
│   └── indexer.py                       Phase 2 — Ingestion → embedding → storage pipeline
│
├── agents/
│   ├── single/
│   │   ├── hr_advisor.py                Phase 4 — ReAct agent with 3 tools
│   │   └── tools.py                     Phase 4 — search_policies, lookup_employee, search_kb
│   ├── specialist/
│   │   ├── policy_agent.py              Phase 6 — Document RAG specialist
│   │   ├── leave_agent.py               Phase 6 — Database RAG + MCP specialist
│   │   ├── onboarding_agent.py          Phase 6 — Hybrid retriever specialist
│   │   └── payroll_agent.py             Phase 6 — Benefits specialist
│   └── orchestrator/
│       ├── state.py                     Phase 6 — Shared AgentState TypedDict
│       ├── router.py                    Phase 6 — Intent classification node
│       └── graph.py                     Phase 6 — LangGraph StateGraph
│
├── mcp_server/
│   ├── server.py                        Phase 5 — FastMCP server entry point
│   └── tools/
│       ├── leave_tool.py                Phase 5 — check_leave_balance, submit_leave_request
│       ├── org_chart_tool.py            Phase 5 — get_org_chart
│       └── policy_lookup_tool.py        Phase 5 — policy_lookup
│
├── evaluation/
│   ├── datasets/
│   │   ├── rag_golden_set.json          Phase 2/3 — RAG Q&A ground truth
│   │   ├── agent_golden_set.json        Phase 1/4/6 — Chat and agent Q&A ground truth
│   │   └── mcp_golden_set.json          Phase 5 — MCP tool usage ground truth
│   ├── tests/
│   │   ├── conftest.py                  Phase 0 — DeepEval pytest session config
│   │   ├── test_chat.py                 Phase 1 — Chat quality metrics
│   │   ├── test_document_rag.py         Phase 2 — RAG faithfulness + relevancy metrics
│   │   ├── test_database_rag.py         Phase 3 — DB routing + SQL accuracy metrics
│   │   ├── test_single_agent.py         Phase 4 — Tool correctness metrics
│   │   ├── test_mcp.py                  Phase 5 — MCP task completion metrics
│   │   └── test_multi_agent.py          Phase 6 — Orchestration quality metrics
│   └── metrics/
│       └── custom_hr_metric.py          Phase 7 — Custom G-Eval for HR accuracy
│
├── frontend/
│   ├── app.py                           Phase 0/1/2/3 — Main Streamlit app (updated each phase)
│   └── pages/
│       ├── 01_chat.py                   Phase 8 — Dedicated chat page
│       ├── 02_hr_dashboard.py           Phase 8 — HR manager employee browser
│       └── 03_eval_dashboard.py         Phase 7/8 — DeepEval metrics dashboard
│
├── config/
│   ├── settings.py                      Phase 0 — Pydantic settings
│   └── prompts/
│       ├── orchestrator.txt             Phase 6 — Orchestrator system prompt
│       ├── policy_agent.txt             Phase 6 — Policy agent persona
│       ├── leave_agent.txt              Phase 6 — Leave agent persona
│       ├── onboarding_agent.txt         Phase 6 — Onboarding agent persona
│       └── payroll_agent.txt            Phase 6 — Payroll agent persona
│
├── scripts/
│   ├── seed_database.py                 Phase 0 — Seed PostgreSQL with CSV data
│   ├── ingest_documents.py              Phase 2 — Ingest PDFs into ChromaDB
│   ├── run_evals.py                     Phase 7 — Run full DeepEval suite
│   └── start_mcp_server.py              Phase 5 — Start MCP server standalone
│
└── database/
    ├── models.py                        Phase 0 — SQLAlchemy ORM models
    ├── migrations/init.sql              Phase 0 — PostgreSQL table creation
    └── seed_data/
        ├── employees.csv                Phase 0 — 50 employees
        ├── leave_records.csv            Phase 0 — 30 leave records
        └── org_chart.csv                Phase 0 — 50 org chart rows
```

---

*ARIA Build Plan — May 2026 | hr-intelligence-platform | ryanrodp-art*
