# ARIA — HR GenAI Agent Platform
## Live Demo Guide — DeepEval GenAI/AgenticAI Validation Framework

> **Audience:** Head of DNA · Product Manager · Principal Product Architect · de.ai Team
> **Format:** 45-minute live demo + Q&A
> **Demo Machine:** MacBook (local environment)
> **Repo:** Available on request post-demo

---

## ⚡ Pre-Demo Checklist
*Complete this 10 minutes before the audience arrives*

```bash
# 1. Docker running
docker compose ps
# Expected: hr_postgres (healthy) + hr_chromadb (running)

# 2. FastAPI running — Terminal Tab 1
cd /Users/ryansrodrigues/Documents/ryan/workspaces/hr-intelligence-platform
uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# 3. Streamlit running — Terminal Tab 2
uv run streamlit run frontend/app.py --server.port 8501

# 4. Browser open at
http://localhost:8501

# 5. Timeout env vars set — Terminal Tab 3 (for DeepEval runs)
export DEEPEVAL_PER_TASK_TIMEOUT_SECONDS_OVERRIDE=600
export DEEPEVAL_PER_ATTEMPT_TIMEOUT_SECONDS_OVERRIDE=300

# 6. Verify health
curl http://localhost:8000/health
curl http://localhost:8000/rag/status

# 7. Verify DB RAG endpoint
curl -s -X POST http://localhost:8000/rag/db/query \
  -H "Content-Type: application/json" \
  -d '{"question": "How many leave days does James Chen have?"}' | python3 -m json.tool

# 8. Verify three-way router
curl "http://localhost:8000/rag/classify?query=How+many+leave+days+does+James+Chen+have"
# Expected: {"classification": "db"}
```

**You should see before the demo starts:**
- ✅ Streamlit UI open with "Backend Connected" in sidebar
- ✅ Sidebar shows "📄 19 policy chunks indexed"
- ✅ ARIA welcome message visible in chat
- ✅ DB RAG query returns `{"answer": "James Chen has 30 days of leave remaining.", "success": true}`
- ✅ Router returns `{"classification": "db"}` for the James Chen question
- ✅ Terminal Tab 3 ready with env vars set

---

## Opening Narrative *(2 minutes)*

> *"What I've built is called ARIA — Agentic Resources Intelligence Assistant. It's an HR intelligence platform that demonstrates the full GenAI and AgenticAI evaluation stack that de.ai needs to build confidence in AI systems before they go near a production environment.*
>
> *The challenge with GenAI isn't building it — it's proving it works correctly, consistently, and without hallucination. Every enterprise client will ask: how do you know your AI is giving the right answer? That's what this demo answers.*
>
> *I've implemented DeepEval — the leading open-source GenAI evaluation framework — across three phases of capability. Today you'll see it evaluate a live chatbot, a document RAG system, and I'll show you the roadmap for how it scales to agents, multi-agents, and MCP tool calls — which is exactly what de.ai's platform needs."*

---

## Architecture Overview *(3 minutes)*

### The ARIA Stack

```
┌─────────────────────────────────────────────────────────┐
│                    STREAMLIT UI                          │
│    Chat interface · Source citations · SQL expander     │
│    Routing badges · DB record count · History           │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP (SSE streaming)
┌──────────────────────▼──────────────────────────────────┐
│                   FASTAPI BACKEND                        │
│  /chat/stream  /rag/stream  /rag/db/stream  /rag/query  │
│  /rag/db/query  /rag/classify  /rag/status  /chat/stats │
└──────┬──────────────────────────────────┬───────────────┘
       │                                  │
       │                    ┌─────────────▼──────────────┐
       │                    │   THREE-WAY ROUTER          │
       │                    │   GPT-4o · temperature=0   │
       │                    │   "rag" / "db" / "chat"    │
       │                    └──────┬─────────────┬───────┘
       │                           │             │
┌──────▼──────────┐    ┌───────────▼──┐   ┌─────▼──────────────┐
│  LANGCHAIN      │    │  DOCUMENT    │   │  DATABASE RAG      │
│  Chat Chain     │    │  RAG CHAIN   │   │  NL-to-SQL (GPT-4o)│
│  Memory         │    │  Retriever   │   │  SQLAlchemy        │
│  GPT-4o (0.7)   │    │  GPT-4o(0.1) │   │  GPT-4o (temp=0)   │
└─────────────────┘    └──────┬───────┘   └─────┬──────────────┘
                              │                  │
              ┌───────────────▼──┐    ┌──────────▼──────────────┐
              │    CHROMADB      │    │      POSTGRESQL          │
              │  19 vectors      │    │  50 employees            │
              │  hr_policies     │    │  30 leave records        │
              │  text-embedding  │    │  50 org chart rows       │
              └──────────────────┘    └─────────────────────────┘
```

### Capability Growth by Phase

| Phase | What ARIA Can Do | DeepEval Metrics Active |
|---|---|---|
| **0** *(Done)* | Infrastructure, seed data, stub responses | None — foundation only |
| **1** *(Done)* | GPT-4o chat, memory, streaming | GEval, AnswerRelevancy, Hallucination |
| **2** *(Done)* | Document RAG, citations, two-way routing | + Faithfulness, ContextualPrecision, ContextualRecall |
| **3** *(Done)* | Database RAG, NL-to-SQL, three-way routing | + Faithfulness (DB), AnswerRelevancy (DB), RoutingBoundary |
| **4** | Single agent with tools | + TaskCompletion, ToolCallAccuracy |
| **5** | MCP server — real actions | + ToolSelectionAccuracy, ParameterCorrectness |
| **6** | Multi-agent LangGraph | + OrchestratorAccuracy, AgentHandoffQuality |
| **7** | Full eval suite + CI/CD | All metrics + regression pipeline |
| **8** | Production polish | Monitoring dashboards + alerting |

---

## Demo Section A — Start the Full Stack *(2 minutes)*

> *"Let me show you the infrastructure first. Everything runs locally in Docker — two databases, a FastAPI backend, and a Streamlit frontend."*

**Show Terminal Tab 1 — FastAPI startup log:**
```
ARIA HR Intelligence Platform starting...
Environment: development
Database: localhost:5432/hr_platform
ChromaDB: http://localhost:8001
ARIA is ready to assist!
```

**Point out:**
- Every config value loaded from `.env` via Pydantic settings — no hardcoded secrets
- Uvicorn with `--reload` watches for file changes — developer-friendly
- The startup log confirms all three infrastructure components are connected

**Show the browser — point out the sidebar:**
- ✅ Backend Connected (version shown)
- 📄 19 policy chunks indexed (ChromaDB live)
- Session ID shown — every conversation is tracked

---

## Demo Section B — Phase 1: Live Chat Demo *(3 minutes)*

> *"Phase 1 wired GPT-4o into the application with conversation memory and token streaming. Watch the response appear word by word — this is Server-Sent Events, the same pattern used in production ChatGPT."*

**Type these three messages in order:**

**Message 1:**
```
Hello ARIA, what can you help me with?
```
*Point out: 💬 General HR knowledge badge — routed to chat chain, not documents*

**Message 2:**
```
Can you help me write a Python script to sort a list?
```
*Point out: ARIA redirects — "That's outside my area as an HR assistant." The GEval Role Adherence metric catches exactly this. Score was 1.00 in testing.*

**Message 3:**
```
What was the first thing I asked you?
```
*Point out: ARIA remembers — "You asked what I can help you with." This is `RunnableWithMessageHistory` — per-session conversation memory keyed by UUID. Memory persists across API calls.*

> *"Three things just demonstrated: GPT-4o integration, role boundary enforcement, and conversation memory. All three are measured in our Phase 1 DeepEval suite."*

---

## Demo Section C — Phase 2: Document RAG Demo *(4 minutes)*

> *"Phase 2 gives ARIA a filing cabinet of your company's actual HR policy documents. Watch what changes."*

**Type these four messages — pause between each to let the audience read:**

**Message 1:**
```
What is the parental leave policy?
```
*Point out:*
- 🔍 Answered from company documents badge — query classified and routed to RAG
- 📄 Sources: Leave Policy, Page 1 — citation appears below answer
- Specific facts: "Primary caregivers receive 16 weeks of fully paid parental leave"
- *Compare to Phase 1: would have said "check with your HR manager"*

**Message 2:**
```
How many days of annual leave do I get?
```
*Point out: "25 days per calendar year, accruing at 2.08 days per month" — exact numbers from the PDF, cited*

**Message 3:**
```
How do I report a harassment complaint?
```
*Point out: All 4 grievance steps listed. Source: Code of Conduct, Page 1. This is from a completely different document — the router found the right one.*

**Message 4:**
```
What does the company contribute to the 401k?
```
*Point out: "100% of first 3%, 50% of next 3%, vests over 3 years" — Benefits Guide, Page 1. Four different documents, intelligent routing across all of them.*

> *"The key insight: ARIA didn't know any of these specific numbers from training. She retrieved them from your documents at query time, grounded her answer in them, and cited the source. That's Retrieval-Augmented Generation — the most widely deployed AI pattern in enterprise today.*
>
> *And crucially — we can now measure whether this is working correctly. That's what DeepEval does."*

---

## Demo Section D — DeepEval Framework Explained *(4 minutes)*

> *"Before I run the evaluations live, let me explain what DeepEval is and why it was selected."*

### What DeepEval Is

DeepEval is an open-source GenAI evaluation framework built by Confident AI. It answers the question every enterprise client will ask: **how do you know your AI is giving the right answer?**

**The LLM-as-Judge pattern:**

```
Your AI (ARIA)         Judge LLM (GPT-4o)
─────────────          ──────────────────
Receives question  →   Reads: question + ARIA's answer
Generates answer   →   Evaluates against criteria
Returns response   →   Returns: score (0.0–1.0) + reasoning
                   →   Pass if score ≥ threshold
```

The judge is a separate GPT-4o instance evaluating ARIA's output. It reads the question, ARIA's answer, any retrieved context, and an evaluation rubric — then scores and explains its reasoning. This is more reliable than rule-based checks because it understands nuance, tone, and semantic accuracy.

### Why DeepEval Over Alternatives

| Capability | DeepEval | LangSmith Evals | Custom Testing |
|---|---|---|---|
| LLM chat metrics | ✅ Built-in | ⚠️ Basic | ❌ Manual |
| RAG metrics (4 types) | ✅ Built-in | ⚠️ Limited | ❌ Manual |
| Agent metrics | ✅ Built-in | ⚠️ Partial | ❌ Manual |
| MCP tool metrics | ✅ Built-in | ❌ None | ❌ Manual |
| Multi-agent metrics | ✅ Built-in | ❌ None | ❌ Manual |
| Golden set management | ✅ Native | ✅ Native | ❌ Manual |
| CI/CD integration | ✅ pytest native | ✅ GitHub Actions | ⚠️ Custom |
| Self-hostable | ✅ Yes | ⚠️ Partial | ✅ Yes |
| Open source | ✅ Yes | ❌ Paid | ✅ Yes |

### Complete Metric Coverage — All 8 Phases

```
PHASE 1 — LLM Chat
├── GEval (HR Role Adherence)      Does ARIA stay in persona?
├── AnswerRelevancyMetric          Is the response relevant?
└── HallucinationMetric            Does ARIA invent facts?

PHASE 2 — Document RAG
├── FaithfulnessMetric             Are claims grounded in retrieved docs?
├── ContextualPrecisionMetric      Is the best chunk ranked first?
├── ContextualRecallMetric         Does retrieval surface all needed info?
└── AnswerRelevancyMetric          Regression check from Phase 1

PHASE 3 — Database RAG  (complete)
├── FaithfulnessMetric (DB)        Are DB answers grounded in SQL rows returned?
├── AnswerRelevancyMetric (DB)     Does the answer address the employee question?
└── Routing Boundary (assertion)   Do DB questions route 'db', policy questions 'rag'?

PHASE 4 — Single Agent  (planned)
├── TaskCompletionMetric           Did the agent complete the task?
└── ToolCallAccuracyMetric         Did it use the right tools?

PHASE 5 — MCP Tools  (planned)
├── ToolSelectionAccuracyMetric    Right tool for right task?
└── ParameterCorrectnessMetric     Correct parameters passed?

PHASE 6 — Multi-Agent LangGraph  (planned)
├── OrchestratorAccuracyMetric     Correct routing to specialist agents?
└── AgentHandoffQualityMetric      Clean context handoffs?

PHASE 7 — Full Suite + CI/CD  (planned)
└── All above metrics in regression pipeline on every commit

PHASE 8 — Production  (planned)
└── Online evals + drift detection + alerting
```

---

## Demo Section E — Phase 1 DeepEval Suite Live *(3 minutes)*

> *"Now I'll run the Phase 1 evaluation suite live. This is 5 test functions, 24 test cases, calling the live ARIA API and having GPT-4o judge every response."*

**Switch to Terminal Tab 3. Run:**

```bash
uv run deepeval test run evaluation/tests/test_chat.py -v
```

**While it runs, narrate:**
- *"DeepEval is calling ARIA's `/chat/` endpoint for each of the 20 golden set questions"*
- *"Each response is sent to GPT-4o with an evaluation rubric — you can see the judge model in the output: `gpt-5.4` for GEval, `gpt-4o` for the others"*
- *"The golden set has 20 entries — 10 standard HR questions and 10 deliberate edge cases including failure scenarios"*

**When results appear — point out:**

```
HR Role Adherence [GEval]   avg=0.95   pass=100%   14 cases
Answer Relevancy             avg=0.98   pass=100%   13 cases
Hallucination                avg=0.00   pass=100%   10 cases
Overall: 24/24 passed
```

**Key talking points:**
- Hallucination score is `0.00` — best possible. ARIA never invents facts
- Role Adherence `0.95` — occasionally ARIA doesn't re-introduce herself as ARIA mid-conversation. Known gap, addressable with system prompt tuning in Phase 7
- Cost: `$0.19` for 24 test cases — cheap enough to run on every pull request
- Time: ~72 seconds — fast enough for CI/CD

---

## Demo Section F — Phase 2 DeepEval Suite Live *(9 minutes)*

> *"Phase 2 introduces four new RAG-specific metrics that don't exist in standard LLM evaluation. These are the metrics that matter for enterprise document AI."*

**Run this single script — it handles all 5 tests with the required sleep gaps:**

```bash
echo "=== test_rag_faithfulness ===" && \
uv run deepeval test run evaluation/tests/test_document_rag.py::test_rag_faithfulness -v && \
echo "Waiting 60s..." && sleep 60 && \
echo "=== test_rag_contextual_precision ===" && \
uv run deepeval test run evaluation/tests/test_document_rag.py::test_rag_contextual_precision -v && \
echo "Waiting 60s..." && sleep 60 && \
echo "=== test_rag_contextual_recall ===" && \
uv run deepeval test run evaluation/tests/test_document_rag.py::test_rag_contextual_recall -v && \
echo "Waiting 60s..." && sleep 60 && \
echo "=== test_rag_answer_relevancy ===" && \
uv run deepeval test run evaluation/tests/test_document_rag.py::test_rag_answer_relevancy -v && \
echo "Waiting 60s..." && sleep 60 && \
echo "=== test_rag_document_routing ===" && \
uv run deepeval test run evaluation/tests/test_document_rag.py::test_rag_document_routing -v
```

**While each test runs, narrate what it measures:**

### test_rag_faithfulness *(~14 seconds)*
> *"Faithfulness is the most critical RAG metric. It asks: does every factual claim in ARIA's answer trace back to the retrieved document chunks? If ARIA says '25 days annual leave' but the retrieved chunk says '20 days' — that's a faithfulness failure. Score of 1.00 means every claim in every answer was perfectly grounded."*

**Expected result:**
```
Faithfulness: avg=1.00, pass=100%, 3 cases
"No contradictions between actual output and retrieval context"
```

### test_rag_contextual_precision *(~12 seconds)*
> *"Contextual precision measures retrieval ranking. The most relevant chunk should always be ranked first. We fixed a bug where 'parental leave' was returning sick leave content as the top result — the parental leave section was merged with sick leave in one chunk. We regenerated the PDFs with better section formatting and reindexed. Now precision is 1.00 — the right chunk is always first."*

**Expected result:**
```
Contextual Precision: avg=1.00, pass=100%, 3 cases
"Relevant node ranked first provides direct answer: 16 weeks fully paid"
```

### test_rag_contextual_recall *(~9 seconds)*
> *"Recall measures completeness. Do the retrieved chunks contain everything needed to produce the expected answer? For a multi-step answer like the harassment reporting process — all 4 steps must be in the retrieved context. Score of 1.00 means retrieval is complete."*

**Expected result:**
```
Contextual Recall: avg=1.00, pass=100%, 2 cases
"Every sentence in expected output aligned with retrieval context"
```

### test_rag_answer_relevancy *(~12 seconds)*
> *"This metric carries over from Phase 1 as a regression check. RAG answers must remain as relevant as chat answers — we haven't traded relevancy for grounding. Score improved from 0.98 in Phase 1 to 1.00 in Phase 2 because grounded answers are more focused."*

**Expected result:**
```
Answer Relevancy: avg=1.00, pass=100%, 3 cases
"Response perfectly addressed the question without irrelevant information"
```

### test_rag_document_routing *(~10 seconds)*
> *"This test has no LLM judge — it's a pure assertion. All 15 policy questions in the golden set must be classified as 'rag' by our query router, not 'chat'. Zero rate limit risk, zero cost. 15/15 correctly routed."*

**Expected result:**
```
Document routing: 15/15 classified as "rag" — PASSED
```

### Final Results Summary

| Test | Metric | Score | Pass Rate | Cost |
|---|---|---|---|---|
| Faithfulness | Claims grounded in docs | **1.00** | 100% | $0.029 |
| Contextual Precision | Best chunk ranked first | **1.00** | 100% | $0.018 |
| Contextual Recall | All needed info retrieved | **1.00** | 100% | $0.011 |
| Answer Relevancy | Response addresses question | **1.00** | 100% | $0.012 |
| Document Routing | All policy questions → RAG | **100%** | 100% | $0.000 |
| **Total Phase 2** | | **1.00** | **100%** | **$0.07** |

> *"$0.07 to run the full RAG evaluation suite. $0.19 for the full chat suite. Less than 30 cents to prove an AI system is working correctly. At enterprise scale with CI/CD, you run this on every pull request — it's the quality gate before any change goes to production."*

---

## Demo Section G — Phase 3: Database RAG Demo *(4 minutes)*

> *"Phase 3 gives ARIA a second knowledge source — the live employee database. Watch what happens when you ask questions that are about specific people, not policies. The router now has three paths: document search, database query, or general chat."*

**Type these four messages — pause after each to show the SQL expander:**

**Message 1:**
```
How many leave days does James Chen have?
```
*Point out:*
- 🗄️ Answered from employee database · 1 record(s) found badge — this did NOT go to documents
- `View database query` expander — click it and show the SQL
- The SQL uses `ILIKE` for case-insensitive name matching — GPT-4o generated this from the question
- Answer is specific: "James Chen has 30 days of leave remaining."
- *Compare to Phase 2: would have returned "I don't have specific information about that in our company documents"*

**Message 2:**
```
Who is currently on leave?
```
*Point out:*
- "Isabella Fernandez is currently on leave." — name only, no role, no department, no location
- This was explicitly designed: the prompt rules say WHO questions get name + direct answer only
- Show the SQL — `WHERE e.status = 'On Leave'` — GPT-4o inferred the right column value
- 1 record returned — this is real-time data from PostgreSQL, not a cached answer

**Message 3:**
```
Who reports to the VP of Engineering?
```
*Point out:*
- Multi-table JOIN — employees table joined to org_chart table
- "Priya Sharma and Marcus Johnson report to the VP of Engineering. Both are Directors of Engineering."
- Show the SQL expander — subquery to find VP's employee_id, then JOIN to find their direct reports
- The router classified this as `"db"` because it's an org chart question, not a policy question

**Message 4:**
```
How many employees are in each department?
```
*Point out:*
- Aggregate query with GROUP BY
- "Engineering: 15, Sales: 10, Finance: 9, HR: 8, Marketing: 8" — total 50 employees
- Immediately follow with a policy question to show the router switching paths:

**Message 5 (immediate follow-up):**
```
What is the parental leave policy?
```
*Point out:*
- Answer switches to 🔍 Answered from company documents — back to document RAG
- Source citation reappears: Leave Policy, Page 1
- SQL expander gone — this answer came from ChromaDB, not PostgreSQL
- *"Same interface, two completely different knowledge sources. The router makes the decision transparently."*

> *"The SQL expander is a deliberate design choice for enterprise AI. When an AI gives you a number about a specific employee, you want to be able to audit how it got there. The SQL is the audit trail."*

---

## Demo Section H — Phase 3: DeepEval Suite *(5 minutes)*

> *"Phase 3 has four test functions. One runs instantly with no LLM judge — it's a pure routing assertion. Three use GPT-4o as the judge. I'll run the routing test live and walk through the results of the LLM-judged tests."*

### Part 1 — Routing Boundary Test (live, ~15 seconds)

**Run:**

```bash
uv run deepeval test run evaluation/tests/test_database_rag.py::test_db_routing_boundary -v
```

**While it runs, narrate:**
- *"This test makes 13 HTTP calls to the `/rag/classify` endpoint — no LLM judge involved, just pure assertions"*
- *"10 database questions must classify as 'db'. 3 policy questions must classify as 'rag'. If the router regresses and starts sending employee questions to document search, this fails immediately"*
- *"Zero cost, 13 seconds — this is what you run on every commit as a fast quality gate"*

**When results appear:**

```
test_db_routing_boundary PASSED — 13/13 assertions correct
Cost: $0.00 | Time: ~13s
```

**Point out the 13 assertions verified:**

| Category | Count | Example |
|---|---|---|
| DB questions → `"db"` | 10 | "How many leave days does James Chen have?" |
| Policy questions → `"rag"` | 3 | "What is the parental leave policy?" |

> *"The three policy questions in this test are the Phase 2 regression check. Phase 3 added a new routing path — this test verifies it didn't break the Phase 2 document routing. That's the discipline: every new phase proves the previous phase still works."*

---

### Part 2 — LLM-Judged Database Tests (walk through results)

> *"The three LLM-judged tests evaluate answer quality. Each gets FaithfulnessMetric and AnswerRelevancyMetric — the same metrics used in Phase 2, but now the retrieval_context is the formatted SQL result instead of document chunks."*

**Run the three tests with sleep gaps:**

```bash
sleep 60 && \
uv run deepeval test run evaluation/tests/test_database_rag.py::test_db_employee_lookup -v && \
sleep 60 && \
uv run deepeval test run evaluation/tests/test_database_rag.py::test_db_aggregate_queries -v && \
sleep 60 && \
uv run deepeval test run evaluation/tests/test_database_rag.py::test_db_join_queries -v
```

**While each runs, narrate what it tests:**

### test_db_employee_lookup *(~15 seconds)*
> *"Three questions about specific employees — James Chen's leave balance, his department, and who is currently on leave. Faithfulness asks: does ARIA's answer contain only claims that appear in the database rows returned? If the SQL returns `leave_balance: 30` and ARIA says '30 days' — that's faithful. If ARIA adds '...and he's been with the company for 5 years' when hire date wasn't in the query — that's a faithfulness failure."*

### test_db_aggregate_queries *(~15 seconds)*
> *"Three aggregate questions — employees per department, active employee count, total leave records. The retrieval context is a GROUP BY result or a COUNT. Faithfulness here means: if the DB says Engineering has 15 employees, ARIA must say 15. Any number other than what the database returned is unfaithful."*

### test_db_join_queries *(~12 seconds)*
> *"Two JOIN questions — pending leave requests and VP Engineering direct reports. These are the hardest queries: two tables joined. The retrieval context has first_name, last_name, and job_title from the JOIN result. Answer Relevancy checks that ARIA answered the actual question — not just summarized the rows."*

**Final Phase 3 Results:**

| Test | Metric | Pass Rate | Cases | Cost | Time |
|---|---|---|---|---|---|
| Routing Boundary | 13 assertions | **100%** | 13 | $0.000 | ~13s |
| Employee Lookup | Faithfulness + Relevancy | **100%** | 3 | ~$0.030 | ~15s |
| Aggregate Queries | Faithfulness + Relevancy | **100%** | 3 | ~$0.030 | ~15s |
| Join Queries | Faithfulness + Relevancy | **100%** | 2 | ~$0.020 | ~12s |

> *"Phase 3 demonstrates something important: the exact same evaluation framework — DeepEval, FaithfulnessMetric, AnswerRelevancyMetric — works for both document retrieval and database retrieval. We changed what goes into retrieval_context. The evaluation infrastructure didn't change at all. That's the power of a framework-first approach."*

---

## Enterprise Observability Roadmap *(2 minutes)*

> *"Before I wrap up, I want to show you the proposed observability architecture for when this moves beyond proof of concept into production. This is directly relevant to de.ai's platform requirements."*

### The Proposed Enterprise Stack

```
┌─────────────────────────────────────────────────────────────────┐
│              PRODUCTION OBSERVABILITY ARCHITECTURE              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  DeepEval ──────────────────────────────────────────────────── │
│  Offline evaluation · Quality gates · Metric scores            │
│  Runs in CI/CD on every commit · Golden set regression         │
│                                                                 │
│  Confident AI Dashboard ────────────────────────────────────── │
│  DeepEval's native analytics · Metric trends · Test history    │
│  Visual pass/fail tracking · Team sharing                      │
│                                                                 │
│  LangSmith ─────────────────────────────────────────────────── │
│  Runtime observability · Traces every LLM call live            │
│  Latency per chain step · Token usage · Error traces           │
│  Prompt version history · Production monitoring                │
│                                                                 │
│  SmithDB ───────────────────────────────────────────────────── │
│  The storage engine powering LangSmith traces                  │
│  Self-hostable inside Infosys VPC                              │
│  Sensitive traces never leave your infrastructure              │
│  P50 latency: 92ms trace loads · 15x faster than alternatives  │
│  Object-storage backed LSM · 3 stateless components            │
│                                                                 │
│  ClickHouse ────────────────────────────────────────────────── │
│  Long-term metric trend storage · High-throughput writes       │
│  DeepEval metric history · Cost tracking over time             │
│  Dashboard: "Has hallucination risk changed this sprint?"      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Why This Stack Matters for de.ai

**DeepEval + LangSmith are complementary, not competing:**

| | DeepEval | LangSmith + SmithDB |
|---|---|---|
| **When it runs** | Offline — before deployment | Online — in production |
| **What it measures** | Quality scores against golden set | Latency, errors, token usage |
| **Output** | Pass/fail with metric reasoning | Trace trees, execution timelines |
| **Use case** | "Is this change safe to deploy?" | "Why did this production call fail?" |
| **Data sovereignty** | Runs locally or in your VPC | SmithDB self-hosted in Infosys VPC |

**SmithDB's enterprise significance:**
- Traces contain sensitive employee data, prompt content, and proprietary tool logic
- SmithDB deploys inside your VPC — three stateless components on object storage and Postgres
- No sensitive traces leave the Infosys infrastructure boundary
- Critical for client engagements with data residency requirements

**ClickHouse enables the question every CISO will ask:**
> *"Show me the hallucination rate trend over the last 6 months across all our AI agents."*

ClickHouse handles the write throughput of continuous metric ingestion and the query performance to answer that question in milliseconds.

---

## What This Proves for de.ai *(1 minute)*

> *"Let me close with five things this proof of concept demonstrates that are directly transferable to the de.ai platform."*

**1. Evaluation-first architecture works**
DeepEval was integrated from Phase 0 — not bolted on at the end. Every phase adds metrics before adding features. This is the discipline de.ai needs to build client confidence.

**2. Metric coverage scales with capability**
Three metrics in Phase 1. Seven in Phase 2. The framework grows with the system — the same pattern applies through agents, MCP tools, and multi-agent orchestration.

**3. Cost is not a barrier**
Under $0.40 total across all three evaluation suites — chat, document RAG, and database RAG. At enterprise scale with 50 agents and daily CI/CD runs, evaluation costs are still a rounding error compared to the cost of a hallucination reaching a client. The routing boundary test is $0.00 — zero cost to run on every commit.

**4. Framework-agnostic design**
ARIA uses GPT-4o today. Swapping to Claude, Gemini, or a fine-tuned Llama model requires changing two lines in `.env`. The evaluation suite runs unchanged.

**5. Hybrid knowledge architecture is production-ready**
Phase 3 demonstrates that a single AI assistant can transparently switch between document retrieval (ChromaDB) and database querying (PostgreSQL) based on the nature of the question. The same router, the same streaming interface, the same evaluation framework. Enterprise HR systems always have both structured employee data and unstructured policy documents — ARIA handles both.

**6. Data sovereignty is solved**
SmithDB's self-hosted VPC deployment means no sensitive AI traces leave the Infosys infrastructure boundary — a non-negotiable requirement for enterprise financial, healthcare, and government clients.

---

## If the Principal Architect Wants to Go Deeper

*Additional technical detail available on request:*

### Chunk Boundary Debugging — The Parental Leave Story
The parental leave policy section was initially being merged with the sick leave section in one 800-character chunk. The chunk's vector was dominated by sick leave content, causing parental leave queries to return the wrong top result. Diagnosed by inspecting all ChromaDB chunks directly, fixed by regenerating PDFs with explicit `\n\n` section separators and reindexing. Contextual Precision metric caught this — scored correctly at 1.00 after fix. This is a real production RAG debugging workflow.

### LLM-as-Judge Reliability
DeepEval's GEval metric used `gpt-5.4` as judge (DeepEval auto-selects latest available). The payroll question scored `0.67` in Run 1 and `0.80` in Run 2 — same question, same ARIA response, different judge score. Non-determinism in the evaluator is a known property. Mitigation: run evaluations multiple times and track trends, not individual scores. Phase 7 implements 3-run averaging for all critical metrics.

### Rate Limit Architecture
At 30,000 TPM limit on the free OpenAI tier, running 15 concurrent judge calls hits the ceiling. Solution: 60-second gaps between test functions, 3 test cases maximum per LLM-judged function. At production tier (150,000+ TPM), the full 15-case suite runs in a single pass in under 2 minutes. Architecture is the same — only the concurrency limit changes.

### sys.path Fix for Test Isolation
DeepEval test files in `evaluation/tests/` need project root on Python path to import from `rag.*` and `backend.*`. Fixed with:
```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)
))))
```
This pattern is standard for monorepo pytest configurations.

### The WHO Prompt Iteration — Database Answer Verbosity
"Who is currently on leave?" initially returned "Isabella Fernandez, who is an HR Coordinator in the HR department, is on leave. She is based in our Singapore office." — accurate but unrequested detail. Three iterations were needed: first adding a WHO rule, then making it the first rule in the system prompt with explicit correct/wrong examples. The final rule: for WHO questions, respond with ONLY the person's name and the direct answer — no role, no department, no location unless explicitly asked. This is a production concern: enterprise HR chatbots that volunteer PII beyond what was asked create compliance exposure.

### The NOT_DB_QUERY Sentinel Pattern
When the NL-to-SQL model cannot answer a question from the database (e.g., "What is the annual leave policy?"), it returns the literal string `NOT_DB_QUERY` instead of SQL. This sentinel travels through the entire stack: the chain returns it, the API endpoint returns a fallback message, the streaming endpoint emits it as a token, and Streamlit catches it to set `last_answer_type = "rag_fallback"`. The sentinel pattern avoids exception handling for expected cases and keeps the code path explicit at every layer.

### SQL Safety Validation
Every SQL string generated by GPT-4o passes through `validate_sql()` before execution. Two checks: the statement must begin with `SELECT` (lowercased, stripped), and it must not contain dangerous keywords (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`, `CREATE`, `GRANT`, `REVOKE`) detected via word-boundary regex. This is defense-in-depth: the NL-to-SQL prompt already instructs SELECT-only, but the validator provides a hard gate regardless of prompt compliance. This is the correct pattern for any AI system that generates executable code or queries.

### Double Call in /rag/db/stream
The `/rag/db/stream` endpoint runs `db_rag_query_stream()` for the streaming tokens, then calls `db_rag_query()` a second time to get the SQL and row count for the metadata SSE event. This is an acknowledged double call — the same pattern as Phase 2's `/rag/stream`. The alternative (threading metadata through the async generator) adds complexity for ~0.5s overhead. Phase 7 refactors this with a wrapper that captures metadata from the first call and passes it through to the metadata event.

### Trailing Slash Convention
FastAPI routes `POST /chat/` with trailing slash. `httpx` (and browsers) don't follow redirects on POST — so Streamlit must call `/chat/` not `/chat`. This is a FastAPI architectural decision to canonicalize routes. All internal callers use trailing slash consistently.

---

## Quick Reference — All Demo Commands

```bash
# === INFRASTRUCTURE ===
docker compose up -d                    # Start PostgreSQL + ChromaDB
docker compose ps                       # Verify both healthy

# === APPLICATION ===
# Tab 1:
uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# Tab 2:
uv run streamlit run frontend/app.py --server.port 8501

# Browser:
open http://localhost:8501
open http://localhost:8000/docs         # FastAPI interactive docs

# === HEALTH CHECKS ===
curl http://localhost:8000/health
curl http://localhost:8000/rag/status
curl http://localhost:8000/chat/stats

# === CLASSIFICATION TEST — two-way and three-way ===
curl "http://localhost:8000/rag/classify?query=What+is+the+parental+leave+policy"
# Expected: {"classification": "rag"}

curl "http://localhost:8000/rag/classify?query=How+many+leave+days+does+James+Chen+have"
# Expected: {"classification": "db"}

# === DB RAG ENDPOINT TEST ===
curl -s -X POST http://localhost:8000/rag/db/query \
  -H "Content-Type: application/json" \
  -d '{"question": "How many leave days does James Chen have?"}' | python3 -m json.tool

curl -s -X POST http://localhost:8000/rag/db/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Who is currently on leave?"}' | python3 -m json.tool

# === DEEPEVAL ENV VARS ===
export DEEPEVAL_PER_TASK_TIMEOUT_SECONDS_OVERRIDE=600
export DEEPEVAL_PER_ATTEMPT_TIMEOUT_SECONDS_OVERRIDE=300

# === PHASE 1 EVALS ===
uv run deepeval test run evaluation/tests/test_chat.py -v

# === PHASE 2 EVALS (run as one block) ===
uv run deepeval test run evaluation/tests/test_document_rag.py::test_rag_faithfulness -v && \
sleep 60 && \
uv run deepeval test run evaluation/tests/test_document_rag.py::test_rag_contextual_precision -v && \
sleep 60 && \
uv run deepeval test run evaluation/tests/test_document_rag.py::test_rag_contextual_recall -v && \
sleep 60 && \
uv run deepeval test run evaluation/tests/test_document_rag.py::test_rag_answer_relevancy -v && \
sleep 60 && \
uv run deepeval test run evaluation/tests/test_document_rag.py::test_rag_document_routing -v

# === PHASE 3 EVALS ===
# Routing boundary first (fast, no LLM judge — run before anything else)
uv run deepeval test run evaluation/tests/test_database_rag.py::test_db_routing_boundary -v

# LLM-judged tests with sleep gaps
sleep 60 && \
uv run deepeval test run evaluation/tests/test_database_rag.py::test_db_employee_lookup -v && \
sleep 60 && \
uv run deepeval test run evaluation/tests/test_database_rag.py::test_db_aggregate_queries -v && \
sleep 60 && \
uv run deepeval test run evaluation/tests/test_database_rag.py::test_db_join_queries -v

# === DATABASE VERIFY ===
docker exec -it hr_postgres psql -U postgres -d hr_platform \
  -c "SELECT COUNT(*) FROM employees;"            # Expected: 50
docker exec -it hr_postgres psql -U postgres -d hr_platform \
  -c "SELECT COUNT(*) FROM leave_records;"        # Expected: 30
docker exec -it hr_postgres psql -U postgres -d hr_platform \
  -c "SELECT employee_id, first_name, last_name, leave_balance FROM employees WHERE first_name = 'James' AND last_name = 'Chen';"
```

---

## Troubleshooting During Demo

| Problem | Fix |
|---|---|
| Streamlit shows "Backend Offline" | Run Tab 1 uvicorn command |
| Sidebar shows "Document search unavailable" | `curl http://localhost:8001/api/v2/heartbeat` — restart Docker if needed |
| DB answer not showing SQL expander | Check that `/rag/db/stream` is sending `sql_used` in the metadata event |
| `/rag/classify` returns `"chat"` for a DB question | Check that `rag_router.py` has three-way router — not the Phase 2 two-way version |
| `/rag/db/query` returns 500 | Restart FastAPI — check that `from rag.database_rag.chain import db_rag_query` import is present in `routes/rag.py` |
| DB answer returns `NOT_DB_QUERY` text in UI | Question was misclassified as `"db"` but GPT-4o returned NOT_DB_QUERY — question is policy-related, not a DB question |
| DeepEval 429 rate limit error | Wait 60 seconds, re-run the specific test function |
| DeepEval timeout error | Verify env vars set: `echo $DEEPEVAL_PER_TASK_TIMEOUT_SECONDS_OVERRIDE` |
| `/rag/classify` returns 500 | Restart FastAPI — likely import error on startup |
| Chat not streaming | Check trailing slash: must call `/chat/` not `/chat` |
| Parental leave returns wrong answer | Re-run indexer: `uv run python -m vector_store.indexer` |
| PostgreSQL connection error in DB RAG | Run `docker compose ps` — verify `hr_postgres` is healthy, not just running |

---

*Document version: May 2026 | ARIA v0.3.0 | Phases 0–3 complete*
*Built by: Ryan Rodrigues | Nu Skin Enterprises — Data Platform Architecture*
