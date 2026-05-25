# ARIA — HR GenAI Agent Platform
## Live Demo Guide — DeepEval GenAI/AgenticAI Validation Framework

> **Audience:** Head of DNA · Product Manager · Principal Product Architect · de.ai Team
> **Format:** 30-minute live demo + Q&A
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
```

**You should see before the demo starts:**
- ✅ Streamlit UI open with "Backend Connected" in sidebar
- ✅ Sidebar shows "📄 19 policy chunks indexed"
- ✅ ARIA welcome message visible in chat
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
│          Chat interface · Source citations              │
│          Routing badges · Conversation history          │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP (SSE streaming)
┌──────────────────────▼──────────────────────────────────┐
│                   FASTAPI BACKEND                        │
│    /chat/stream   /rag/stream   /rag/classify           │
│    /rag/status    /chat/stats   /rag/query              │
└──────┬──────────────────────────────────┬───────────────┘
       │                                  │
┌──────▼──────────┐              ┌────────▼───────────────┐
│  LANGCHAIN      │              │  RAG PIPELINE          │
│  Chat Chain     │              │  Retriever             │
│  Memory         │              │  RAG Chain             │
│  GPT-4o (0.7)   │              │  GPT-4o (0.1)          │
└─────────────────┘              └────────┬───────────────┘
                                          │
                        ┌─────────────────▼───────────────┐
                        │         CHROMADB                 │
                        │   19 vectors · hr_policies       │
                        │   text-embedding-3-small         │
                        └─────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│                   POSTGRESQL                             │
│   50 employees · 30 leave records · 50 org chart rows   │
└─────────────────────────────────────────────────────────┘
```

### Capability Growth by Phase

| Phase | What ARIA Can Do | DeepEval Metrics Active |
|---|---|---|
| **0** *(Done)* | Infrastructure, seed data, stub responses | None — foundation only |
| **1** *(Done)* | GPT-4o chat, memory, streaming | GEval, AnswerRelevancy, Hallucination |
| **2** *(Done)* | Document RAG, citations, routing | + Faithfulness, ContextualPrecision, ContextualRecall |
| **3** | Database RAG — live employee data | + DatabaseAccuracy, StructuredOutput |
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

PHASE 3 — Database RAG  (planned)
├── DatabaseAccuracy               Do SQL results match query intent?
└── StructuredOutputMetric         Is the formatted response correct?

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
$0.26 total across both evaluation suites. At enterprise scale with 50 agents and daily CI/CD runs, evaluation costs are still a rounding error compared to the cost of a hallucination reaching a client.

**4. Framework-agnostic design**
ARIA uses GPT-4o today. Swapping to Claude, Gemini, or a fine-tuned Llama model requires changing two lines in `.env`. The evaluation suite runs unchanged.

**5. Data sovereignty is solved**
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

# === CLASSIFICATION TEST ===
curl "http://localhost:8000/rag/classify?query=What+is+the+parental+leave+policy"

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

# === DATABASE VERIFY ===
docker exec -it hr_postgres psql -U hr_user -d hr_platform \
  -c "SELECT COUNT(*) FROM employees;"   # Expected: 50
```

---

## Troubleshooting During Demo

| Problem | Fix |
|---|---|
| Streamlit shows "Backend Offline" | Run Tab 1 uvicorn command |
| Sidebar shows "Document search unavailable" | `curl http://localhost:8001/api/v2/heartbeat` — restart Docker if needed |
| DeepEval 429 rate limit error | Wait 60 seconds, re-run the specific test function |
| DeepEval timeout error | Verify env vars set: `echo $DEEPEVAL_PER_TASK_TIMEOUT_SECONDS_OVERRIDE` |
| `/rag/classify` returns 500 | Restart FastAPI — likely import error on startup |
| Chat not streaming | Check trailing slash: must call `/chat/` not `/chat` |
| Parental leave returns wrong answer | Re-run indexer: `uv run python -m vector_store.indexer` |

---

*Document version: May 2026 | ARIA v0.2.0 | Phases 0–2 complete*
*Built by: Ryan Rodrigues | Nu Skin Enterprises — Data Platform Architecture*
