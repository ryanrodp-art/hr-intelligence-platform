# ARIA — HR GenAI Agent Platform
## Live Demo Guide — DeepEval GenAI/AgenticAI Validation Framework

> **Audience:** Head of DNA · Product Manager · Principal Product Architect · de.ai Team
> **Format:** 55-minute live demo + Q&A
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

# 4. MCP Server running — Terminal Tab 4
uv run python scripts/start_mcp_server.py
# Expected: "ARIA HR MCP Server | Transport: HTTP | Port: 8002"

# 5. Browser open at
http://localhost:8501

# 6. Timeout env vars set — Terminal Tab 3 (for DeepEval runs)
export DEEPEVAL_PER_TASK_TIMEOUT_SECONDS_OVERRIDE=600
export DEEPEVAL_PER_ATTEMPT_TIMEOUT_SECONDS_OVERRIDE=300

# 7. Verify health
curl http://localhost:8000/health
curl http://localhost:8000/rag/status

# 8. Verify DB RAG endpoint
curl -s -X POST http://localhost:8000/rag/db/query \
  -H "Content-Type: application/json" \
  -d '{"question": "How many leave days does James Chen have?"}' | python3 -m json.tool

# 9. Verify four-way router
curl "http://localhost:8000/rag/classify?query=How+many+leave+days+does+James+Chen+have"
# Expected: {"classification": "db"}

curl "http://localhost:8000/rag/classify?query=What+is+the+leave+policy+and+how+many+days+does+James+Chen+have"
# Expected: {"classification": "agent"}

# 10. Verify agent endpoint
curl -s -X POST http://localhost:8000/agent/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the parental leave policy?"}' | python3 -m json.tool
# Expected: {"answer": "...", "tools_used": ["search_policies"], "success": true}

# 11. Verify MCP server tools (FastMCP Python client — curl won't work)
uv run python -c "
import asyncio
from fastmcp import Client
async def check():
    async with Client('http://localhost:8002/mcp') as c:
        tools = await c.list_tools()
        print([t.name for t in tools])
asyncio.run(check())
"
# Expected: ['check_leave_balance', 'submit_leave_request', 'get_org_chart', 'policy_lookup']
```

**You should see before the demo starts:**
- ✅ Streamlit UI open with "Backend Connected" in sidebar
- ✅ Sidebar shows "📄 19 policy chunks indexed"
- ✅ Sidebar shows "🤖 Agent: Online"
- ✅ ARIA welcome message visible in chat
- ✅ DB RAG query returns `{"answer": "James Chen has 30 days of leave remaining.", "success": true}`
- ✅ Router returns `{"classification": "db"}` for the James Chen question
- ✅ Router returns `{"classification": "agent"}` for the compound question
- ✅ Agent endpoint returns `{"tools_used": ["search_policies"], "success": true}`
- ✅ MCP server returns 4 tools: `check_leave_balance`, `submit_leave_request`, `get_org_chart`, `policy_lookup`
- ✅ Terminal Tab 3 ready with env vars set
- ✅ Terminal Tab 4 showing MCP server running on port 8002

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
│ Chat · RAG citations · SQL expander · Agent trace       │
│ Routing badges · DB record count · MCP action badges    │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP (SSE streaming)
┌──────────────────────▼──────────────────────────────────┐
│                   FASTAPI BACKEND                        │
│  /chat/stream  /rag/stream  /rag/db/stream  /agent/query│
│  /rag/db/query  /rag/classify  /rag/status  /chat/stats │
└──────┬──────────────────────────────────┬───────────────┘
       │                                  │
       │                    ┌─────────────▼──────────────┐
       │                    │   FOUR-WAY ROUTER           │
       │                    │   GPT-4o · temperature=0   │
       │                    │  "rag"/"db"/"chat"/"agent" │
       │                    └──────┬──────────┬──┬───────┘
       │                           │          │  │
┌──────▼──────────┐    ┌───────────▼──┐   ┌──▼──▼──────────────┐
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

┌─────────────────────────────────────────────────────────┐
│          SINGLE HR ADVISOR AGENT (Phase 4 + 5)          │
│   LangChain create_agent · max_iterations=7 · temp=0   │
│   Phase 4 Direct Tools:                                 │
│   ┌──────────────┐ ┌───────────────┐ ┌───────────────┐ │
│   │search_policie│ │lookup_employee│ │search_knowled-│ │
│   │s → ChromaDB  │ │→ PostgreSQL   │ │ge_base→ChromDB│ │
│   └──────────────┘ └───────────────┘ └───────────────┘ │
│                                                         │
│   Phase 5 MCP Tools via HTTP:8002:                      │
│   ┌──────────────┐ ┌───────────────┐ ┌───────────────┐ ┌──────────────┐│
│   │check_leave_  │ │submit_leave_  │ │get_org_chart  │ │policy_lookup ││
│   │balance→PG    │ │request→PG✍️   │ │→ PG self-join │ │→ ChromaDB    ││
│   └──────────────┘ └───────────────┘ └───────────────┘ └──────────────┘│
└─────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────┐
│              FASTMCP SERVER (Port 8002)                  │
│   FastMCP 3.3.1 · HTTP Transport · /mcp endpoint        │
│   Separate process — any MCP client can connect         │
│   Tools: check_leave_balance · submit_leave_request     │
│          get_org_chart · policy_lookup                  │
└─────────────────────────────────────────────────────────┘
```

### Capability Growth by Phase

| Phase | What ARIA Can Do | DeepEval Metrics Active |
|---|---|---|
| **0** *(Done)* | Infrastructure, seed data, stub responses | None — foundation only |
| **1** *(Done)* | GPT-4o chat, memory, streaming | GEval, AnswerRelevancy, Hallucination |
| **2** *(Done)* | Document RAG, citations, two-way routing | + Faithfulness, ContextualPrecision, ContextualRecall |
| **3** *(Done)* | Database RAG, NL-to-SQL, three-way routing | + Faithfulness (DB), AnswerRelevancy (DB), RoutingBoundary |
| **4** *(Done)* | ReAct agent, 3 tools, four-way routing, reasoning trace | + TaskCompletion, ToolCorrectness, AnswerRelevancy |
| **5** *(Done)* | MCP server, 4 action tools, first DB write, 7-tool agent | + TaskCompletion (MCP), AnswerRelevancy (MCP), ToolRouting |
| **6** | Multi-agent LangGraph | + StepEfficiency, PlanAdherence, PlanQuality |
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

## Demo Section D — Phase 3: Database RAG Demo *(4 minutes)*

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

## Demo Section E — Phase 4: Single HR Advisor Agent *(5 minutes)*

> *"Phase 4 is where ARIA stops following rules and starts reasoning. Instead of a hardcoded router that says 'if policy question → RAG, if employee question → DB', we now have a LangChain ReAct agent that reads the question, decides which tool to use, calls it, reads the result, and decides if it needs more information. This is the first step from retrieval to reasoning."*

**The transformation:**
```
Phase 3 — Rule-based routing:
Router classifies → hardcoded chain executes → answer

Phase 4 — Agent reasoning:
Agent reads question → thinks → chooses tool → observes result
→ thinks again → chooses another tool if needed → final answer
```

**Type these four messages in order — pause after each to show the reasoning trace:**

**Message 1 — Single tool, policy:**
```
What is the parental leave policy?
```
*Point out:*
- 🤖 **Agent** badge — this went through the ReAct agent, not the direct RAG chain
- `📄 search_policies` tool badge appears below the answer
- Click **🧠 Agent Reasoning (1 step)** expander
- Show Step 1: Tool input `{'query': 'parental leave policy'}` → Observation shows the retrieved policy text
- *"The agent read the question, decided search_policies was the right tool, called it, got the policy text, and formed its answer. One reasoning step."*

**Message 2 — Single tool, employee:**
```
How many leave days does James Chen have?
```
*Point out:*
- `👤 lookup_employee` tool badge — agent chose the database tool, not the policy search
- Click the reasoning expander — Tool input: `{'query': "What is James Chen's leave balance?"}`
- Observation: "James Chen has a leave balance of 30 days."
- *"Same agent, different tool. It read 'James Chen' — a person's name — and correctly inferred this was a database question, not a policy question. Zero hardcoded rules. Pure reasoning."*

**Message 3 — Compound query, two tools:**
```
What is the remote work policy and how many days does James Chen have?
```
*Point out:*
- Both `📄 search_policies` AND `👤 lookup_employee` badges appear
- Click **🧠 Agent Reasoning (2 steps)**
- Step 1: `search_policies` called with `{'query': 'remote work policy'}` → handbook content returned
- Step 2: `lookup_employee` called with `{'query': "What is James Chen's leave balance?"}` → "30 days"
- Final answer combines both sources coherently
- *"This is the key Phase 4 capability. One question, two knowledge sources, two tool calls, one coherent answer. The router classified this as 'agent' — it knew this question needed both document search and database lookup. Try getting that from a rule-based system."*

**Message 4 — Broad knowledge base:**
```
What should a new hire know about their first week?
```
*Point out:*
- `🔍 search_knowledge_base` badge — the broad search tool for cross-cutting questions
- Answer pulls from onboarding, working hours, buddy programme, IT setup — across multiple handbook sections
- *"The third tool — search_knowledge_base — is the broad fallback. Not a specific policy clause, not a specific employee. General HR knowledge. The agent chose this without being told."*

> *"What you just saw is a ReAct agent — Reason and Act. The agent loops: think about which tool, call the tool, observe the result, think again, call another tool if needed, form the final answer. The reasoning trace in the UI is not cosmetic — it's the actual internal thought process of the agent, captured as it runs. This is the pattern that powers every serious AI agent system in production today."*

---

## Demo Section K — Phase 5: MCP Server — From Answers to Actions *(6 minutes)*

> *"Phase 4 ARIA could tell you things. Phase 5 ARIA can do things. This is the most important capability jump in the platform — and it's built on MCP, Anthropic's open standard for connecting AI agents to external tools.*
>
> *The difference: Phase 4 tools were baked directly into the agent's code. Phase 5 tools run as a separate server on port 8002. Any MCP-compatible client — Claude Desktop, Cursor, another agent — can call these same tools without touching ARIA's code. That's what makes MCP an enterprise-grade standard, not just a demo trick."*

**Show the MCP server running in Terminal Tab 4:**
```
ARIA HR MCP Server
Transport: HTTP | Port: 8002
Endpoint: http://localhost:8002/mcp
Tools: check_leave_balance, submit_leave_request, get_org_chart, policy_lookup
```

**Explain the tool architecture shift:**
```
Phase 4 — 3 tools, baked into the agent:
  search_policies → ChromaDB (read)
  lookup_employee → PostgreSQL (read)
  search_knowledge_base → ChromaDB (read)

Phase 5 — adds 4 MCP tools via network service:
  check_leave_balance → PostgreSQL (read)
  submit_leave_request → PostgreSQL (WRITE) ← first write in ARIA
  get_org_chart → PostgreSQL (read, self-join)
  policy_lookup → ChromaDB (read)

Total: 7 tools. 3 direct calls. 4 MCP network calls.
```

**Type these queries in the Streamlit UI — pause after each:**

> **Important:** The MCP queries use **Employee IDs** (EMP-XXXX format), not names. This is intentional — the MCP tools are designed for structured, programmatic inputs. The Phase 4 direct tools handle natural name-based lookups. The agent routes correctly based on the question format.

**Message 1 — MCP read tool, leave balance:**
```
Check the leave balance for EMP-0001
```
*Point out:*
- Answer: "James Chen has 30 days of leave remaining. Status: Active"
- Tools used: `check_leave_balance` — from the MCP server, not the direct Phase 4 tools
- *"Same data as before, but now accessed through a network protocol rather than a direct function call. EMP-ID format → MCP tool. Name format → Phase 4 direct tool. The agent decides based on tool descriptions."*

**Message 2 — MCP read tool, org chart:**
```
Who are the direct reports of EMP-0001?
```
*Point out:*
- Answer: James Chen's position + Marcus Johnson and Priya Sharma as direct reports
- Tools used: `get_org_chart` — a self-join across three tables in one MCP call
- *"One MCP tool call ran two SQL queries — employee info plus direct reports — in a single atomic connection. That's the power of encapsulating business logic in a tool."*

**Message 3 — MCP write tool — the milestone moment:**
```
Submit Annual leave for EMP-0001 from 2027-06-16 to 2027-06-18
```
*Point out:*
- Answer: "Leave request submitted successfully for EMP-0001. Dates: 2027-06-16 to 2027-06-18 (3 days). Type: Annual. Status: Pending. Your manager will be notified for approval."
- Tools used: `submit_leave_request`
- *"This is the first time in this entire demo that ARIA wrote to the database. Not retrieved, not answered — acted. A user's natural language instruction just created a new record in PostgreSQL."*

**Verify the write in the terminal — show the audience:**
```bash
docker exec -it hr_postgres psql -U hr_user -d hr_platform \
  -c "SELECT employee_id, start_date, end_date, leave_type, status FROM leave_records WHERE employee_id = 'EMP-0001' ORDER BY id DESC LIMIT 3;"
```
```
 employee_id | start_date |  end_date  | leave_type | status
-------------+------------+------------+------------+---------
 EMP-0001    | 2027-06-16 | 2027-06-18 | Annual     | Pending
(1 row)
```
*"There it is. Row in the database. Status: Pending. Manager gets notified. This is what enterprise AI agents need to do — not just answer questions, but complete workflows."*

**Message 4 — Compound MCP + direct tool:**
```
Check leave balance for EMP-0001 and look up the parental leave policy
```
*Point out:*
- Answer combines MCP balance data + ChromaDB policy text in one response
- Tools used: `check_leave_balance` (MCP) + `search_policies` (Phase 4 direct)
- *"The agent called tools from two completely different sources — a network MCP tool and a direct Python function — and combined the results into one coherent answer. This is the 7-tool agent working as designed."*

> *"What you just saw is the transition from a Q&A system to an enterprise AI agent. Phase 4 ARIA was a very good assistant. Phase 5 ARIA can complete HR workflows. The same evaluation framework, the same DeepEval metrics, the same golden set discipline — applied to a system that now modifies database state on behalf of users."*

---

## Demo Section F — DeepEval Framework Explained *(4 minutes)*

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

PHASE 4 — Single Agent  (complete)
├── TaskCompletionMetric           Did the agent complete the full task?
├── ToolCorrectnessMetric          Did it choose the right tool(s)?
└── AnswerRelevancyMetric          Did the answer stay focused and on-point?

PHASE 5 — MCP Tools  (complete)
├── TaskCompletionMetric (MCP)     Did the MCP action complete successfully?
├── AnswerRelevancyMetric (MCP)    Is the action response focused and accurate?
└── Tool Routing (assertion)       Did each question invoke the correct MCP tool?

PHASE 6 — Multi-Agent LangGraph  (planned)
├── OrchestratorAccuracyMetric     Correct routing to specialist agents?
└── AgentHandoffQualityMetric      Clean context handoffs?

PHASE 7 — Full Suite + CI/CD  (planned)
└── All above metrics in regression pipeline on every commit

PHASE 8 — Production  (planned)
└── Online evals + drift detection + alerting
```

---

## Demo Section G — Phase 1 DeepEval Suite Live *(3 minutes)*

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

## Demo Section H — Phase 2 DeepEval Suite Live *(9 minutes)*

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

## Demo Section I — Phase 3: DeepEval Suite *(5 minutes)*

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

## Demo Section J — Phase 4: DeepEval Agent Suite *(5 minutes)*

> *"Phase 4 introduces three new DeepEval metrics designed specifically for agents. These are native DeepEval metrics — no custom code. The framework already knows how to evaluate agents."*

**Run the full Phase 4 suite:**

```bash
uv run deepeval test run evaluation/tests/test_single_agent.py -v
```

**While it runs, narrate the four tests:**

### test_agent_policy_queries *(~15 seconds)*
> *"Three policy questions — parental leave, remote work policy, probation period. TaskCompletionMetric asks: did the agent fully accomplish what the user asked? ToolCorrectnessMetric verifies search_policies was called. AnswerRelevancyMetric checks the answer stayed focused. All three passed at 100%."*

### test_agent_employee_queries *(~20 seconds)*
> *"Three employee questions. The key thing here is ToolCorrectnessMetric — did the agent call lookup_employee rather than search_policies? For named employee questions, the agent must use the database tool. Score: 1.00. It never went to the wrong knowledge source."*

### test_agent_compound_queries *(~20 seconds)*
> *"This is the most important test — three compound questions requiring both tools. TaskCompletionMetric checks the combined answer is complete. ToolCorrectnessMetric verifies BOTH search_policies AND lookup_employee were called. This is what the agent was built for. All three passed."*

### test_agent_tool_correctness_boundary *(~40 seconds)*
> *"The boundary test runs all 10 golden set entries through ToolCorrectnessMetric only — no LLM judge, pure tool selection verification. 10 questions, 10 correct tool choices. Score: 1.00 across all entries. This is the Phase 4 exit criteria — Tool Correctness ≥ 0.8. We hit 1.00."*

**When results appear — point out:**

```
Task Completion     avg=0.95   pass=100%   9 cases
Tool Correctness    avg=1.00   pass=100%   19 cases
Answer Relevancy    avg=0.90   pass=100%   9 cases
Overall: 19/19 passed
```

**Final Phase 4 Results:**

| Test | Metrics | Pass Rate | Cases | Cost | Time |
|---|---|---|---|---|---|
| Policy queries | TaskCompletion + ToolCorrectness + AnswerRelevancy | **100%** | 3 | ~$0.025 | ~15s |
| Employee queries | ToolCorrectness + AnswerRelevancy | **100%** | 3 | ~$0.010 | ~20s |
| Compound queries | TaskCompletion + ToolCorrectness + AnswerRelevancy | **100%** | 3 | ~$0.025 | ~20s |
| Tool boundary | ToolCorrectness only | **100%** | 10 | $0.000 | ~40s |
| **Total Phase 4** | | **100%** | **19** | **$0.073** | **~115s** |

> *"ToolCorrectnessMetric at 1.00 is the headline result. The agent chose the right tool for every single query — policy questions went to search_policies, employee questions went to lookup_employee, compound questions triggered both. That's not luck. That's well-designed tool descriptions and a well-prompted ReAct agent — and now we have a metric that proves it reproducibly."*

---

## Demo Section L — Phase 5: DeepEval MCP Suite *(4 minutes)*

> *"Phase 5 has four tests — three LLM-judged, one pure boundary assertion. We use TaskCompletionMetric and AnswerRelevancyMetric — the same metrics as Phase 4, now applied to MCP tool calls including the write operation."*

**Run the boundary test first — no cost, instant:**

```bash
uv run deepeval test run evaluation/tests/test_mcp.py::test_mcp_tool_routing_boundary -v
```

*While it runs:*
> *"This test calls all 10 golden set questions through the live agent and verifies each one invoked the correct MCP tool — no LLM judge, pure assertion. 10 questions × 3-second sleep = 62 seconds. Zero cost."*

**When results appear:**
```
10/10 entries routed to correct MCP tool — PASSED
Cost: $0.00 | Time: 62s
```

**Now run the LLM-judged tests:**

```bash
uv run deepeval test run evaluation/tests/test_mcp.py::test_mcp_read_tools -v
```

### test_mcp_read_tools *(~21 seconds)*
> *"Three read tool questions — two leave balance checks via EMP-ID, one org chart lookup. TaskCompletionMetric at 0.98, AnswerRelevancy at 1.00. The org chart entry required a specific question about one employee's position — broad questions like 'get the org chart' caused the judge to expect a company-wide org chart. Lesson: golden set specificity matters as much as agent quality."*

```bash
uv run deepeval test run evaluation/tests/test_mcp.py::test_mcp_write_tool -v
```

### test_mcp_write_tool *(~21 seconds)*
> *"Three write operation questions — Annual, Sick, and Emergency leave submissions for two different employees. Both metrics at 1.00 across all three. This is the headline: DeepEval's TaskCompletionMetric correctly recognises that submitting a leave request — an action — was completed, not just described. The judge understood the task was a write operation."*

```bash
uv run deepeval test run evaluation/tests/test_mcp.py::test_mcp_multi_step -v
```

### test_mcp_multi_step *(~29 seconds)*
> *"Three multi-step sequences — balance check plus policy lookup, org chart plus balance, submit leave plus confirm balance. The last one is particularly interesting: the agent submitted a leave request AND then checked the remaining balance in the same reasoning loop. Two MCP tool calls, one coherent answer. Task Completion 0.98, Answer Relevancy 0.95."*

**When all results are in — Final Phase 5 Results:**

| Test | Metrics | Avg Score | Pass Rate | Cases | Cost | Time |
|---|---|---|---|---|---|---|
| Tool routing boundary | Assertion (no judge) | 100% | **100%** | 10 | $0.000 | 62s |
| MCP read tools | TaskCompletion + AnswerRelevancy | 0.99 | **100%** | 3 | $0.024 | 21s |
| MCP write tool | TaskCompletion + AnswerRelevancy | **1.00** | **100%** | 3 | $0.025 | 21s |
| MCP multi-step | TaskCompletion + AnswerRelevancy | 0.97 | **100%** | 3 | $0.031 | 29s |
| **Total Phase 5** | | **0.99** | **100%** | **19** | **$0.080** | **133s** |

> *"$0.08 to evaluate a system that can now write to a production database on behalf of users. That's the ROI of evaluation-first development — you know your agent is working correctly before it goes anywhere near a real HR system."*

---

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

> *"Let me close with what this proof of concept demonstrates that is directly transferable to the de.ai platform."*

**1. Evaluation-first architecture works**
DeepEval was integrated from Phase 0 — not bolted on at the end. Every phase adds metrics before adding features. This is the discipline de.ai needs to build client confidence.

**2. Metric coverage scales with capability**
Three metrics in Phase 1. Seven in Phase 2. Fourteen across five phases. The framework grows with the system — the same pattern applies through agents, MCP tools, and multi-agent orchestration.

**3. Cost is not a barrier**
Under $0.50 total across all five evaluation suites — chat, document RAG, database RAG, agent, and MCP. The routing boundary tests are $0.00 — zero cost to run on every commit. At enterprise scale with 50 agents and daily CI/CD runs, evaluation costs are still a rounding error compared to the cost of a hallucination or a bad write operation reaching a client.

**4. Framework-agnostic design**
ARIA uses GPT-4o today. Swapping to Claude, Gemini, or a fine-tuned Llama model requires changing two lines in `.env`. The evaluation suite runs unchanged.

**5. Agentic reasoning is measurable**
Phase 4 demonstrates that agent behaviour — specifically tool selection — is fully measurable with DeepEval's native `ToolCorrectnessMetric`. A 1.00 score across 10 diverse queries proves the ReAct agent consistently reasons to the correct tool without hardcoded rules.

**6. AI agents can perform actions safely**
Phase 5 demonstrates that an AI agent can write to a production database — `submit_leave_request` inserts records into PostgreSQL — and DeepEval's `TaskCompletionMetric` correctly evaluates whether the action was completed. `1.00` across all 3 write test cases. The same evaluation framework that validates answers also validates actions.

**7. MCP is the enterprise integration standard**
The Phase 5 MCP server runs independently of the agent — any MCP-compatible client (Claude Desktop, Cursor, future ARIA versions) can call the same tools without code changes. This is the architecture pattern de.ai needs for enterprise tool integration at scale.

**8. Hybrid knowledge architecture is production-ready**
Phases 3–5 together demonstrate that a single AI assistant can transparently switch between document retrieval (ChromaDB), database querying (PostgreSQL), network tool calls (MCP server), and database writes — based on the nature of the question. Enterprise HR systems always have both structured data and unstructured documents — ARIA handles all of it.

**9. Data sovereignty is solved**
SmithDB's self-hosted VPC deployment means no sensitive AI traces leave the Infosys infrastructure boundary — a non-negotiable requirement for enterprise financial, healthcare, and government clients.

---

## If the Principal Architect Wants to Go Deeper

*Additional technical detail available on request:*

### The ReAct Agent Pattern — Why Tool Descriptions Are Everything
The ReAct agent selects tools based entirely on their docstring descriptions — not hardcoded rules. The `lookup_employee` tool description explicitly states "Always use this tool when the question mentions a person by name." The `search_policies` description says "Do NOT use this tool if the question mentions a specific employee by name." These two rules alone produce correct tool selection across all employee vs policy questions. The lesson: in agentic systems, prompt engineering moves from the system prompt to the tool description. Getting tool descriptions precisely right is the critical engineering task — `ToolCorrectnessMetric` is the quality gate that confirms they're working.

### The Four-Way Router Upgrade
The Phase 3 three-way router (`rag` / `db` / `chat`) was extended to four-way by adding a single classification rule: if a question requires retrieving from BOTH policy documents AND the employee database to fully answer — classify as `"agent"`. Single-source questions remain `"rag"` or `"db"`. This means compound questions like "What is the leave policy and how many days does James have?" route to the agent, while simple questions bypass it entirely — keeping the faster direct chains for single-domain queries.

### Why `max_iterations=5` Matters
The `AgentExecutor` is capped at 5 reasoning iterations. Without this, a confused agent could loop indefinitely burning API credits. 5 iterations is sufficient for the most complex compound question (policy lookup + employee lookup + reasoning), while providing a hard safety ceiling. In production, this ceiling should be logged as a metric — hitting max_iterations signals either a poorly formed question or a tool failure that needs investigation.

### Why Two Separate Tool Sets Coexist (Phase 4 direct + Phase 5 MCP)
The Phase 4 tools accept natural language inputs — names, questions, phrases. They are optimised for retrieval. The Phase 5 MCP tools accept structured inputs — EMP-IDs, date strings in YYYY-MM-DD format, leave type enums. They are optimised for actions. The agent's tool descriptions create a natural routing boundary: questions mentioning a person's name go to `lookup_employee` (direct); questions using EMP-ID format go to `check_leave_balance` (MCP). No hardcoded routing rules — the LLM reads the tool descriptions and decides. This is the correct design pattern for multi-tool agents.

### Why FastMCP 3.x Cannot Be Verified with curl
FastMCP 3.x uses Streamable HTTP transport, which requires a session ID established through an MCP handshake before any tool calls can be made. Raw curl skips the handshake and fails with "Missing session ID". The correct approach is the `fastmcp.Client` Python context manager — it handles the handshake transparently. This is a FastMCP 3.x design decision to enforce protocol compliance over raw HTTP convenience.

### The First Database Write — Why It Matters Architecturally
Every system before Phase 5 was read-only. `submit_leave_request` is the first mutation — it inserts a new row into `leave_records` with `status='Pending'`. The transaction uses `engine.begin()` (SQLAlchemy's context manager for atomic writes) which auto-commits on success and auto-rolls back on any exception. The employee existence check and the insert share one connection — if the employee check fails, no partial insert occurs. This is the correct pattern for all AI-initiated write operations: validate first, write atomically, confirm explicitly.

### Chunk boundary debugging — The Parental Leave Story
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

# === PHASE 4 EVALS ===
uv run deepeval test run evaluation/tests/test_single_agent.py -v

# Run individual Phase 4 tests
uv run deepeval test run evaluation/tests/test_single_agent.py::test_agent_policy_queries -v
uv run deepeval test run evaluation/tests/test_single_agent.py::test_agent_employee_queries -v
uv run deepeval test run evaluation/tests/test_single_agent.py::test_agent_compound_queries -v
uv run deepeval test run evaluation/tests/test_single_agent.py::test_agent_tool_correctness_boundary -v

# === MCP SERVER ===
# Tab 4 — start MCP server (keep running throughout demo)
uv run python scripts/start_mcp_server.py

# Verify MCP tools (FastMCP Python client — curl won't work for MCP 3.x)
uv run python -c "
import asyncio
from fastmcp import Client
async def check():
    async with Client('http://localhost:8002/mcp') as c:
        tools = await c.list_tools()
        print([t.name for t in tools])
asyncio.run(check())
"

# Test MCP tools directly
uv run python -c "
import asyncio
from fastmcp import Client
async def test():
    async with Client('http://localhost:8002/mcp') as c:
        r = await c.call_tool('check_leave_balance', {'employee_id': 'EMP-0001'})
        print(r.data)
asyncio.run(test())
"

# Verify MCP write (submit leave request)
uv run python -c "
import asyncio
from fastmcp import Client
async def test():
    async with Client('http://localhost:8002/mcp') as c:
        r = await c.call_tool('submit_leave_request', {
            'employee_id': 'EMP-0001', 'start_date': '2027-06-16',
            'end_date': '2027-06-18', 'leave_type': 'Annual'})
        print(r.data)
asyncio.run(test())
"

# Verify write in database
docker exec -it hr_postgres psql -U hr_user -d hr_platform \
  -c "SELECT employee_id, start_date, end_date, leave_type, status FROM leave_records WHERE employee_id = 'EMP-0001' ORDER BY id DESC LIMIT 3;"

# === PHASE 5 EVALS ===
# Boundary test first — no LLM judge, no cost
uv run deepeval test run evaluation/tests/test_mcp.py::test_mcp_tool_routing_boundary -v

# LLM-judged tests
uv run deepeval test run evaluation/tests/test_mcp.py::test_mcp_read_tools -v
uv run deepeval test run evaluation/tests/test_mcp.py::test_mcp_write_tool -v
uv run deepeval test run evaluation/tests/test_mcp.py::test_mcp_multi_step -v

# Or full Phase 5 suite
uv run deepeval test run evaluation/tests/test_mcp.py -v

# === STREAMLIT MCP QUERIES (type these in the chat UI) ===
# Read tools — use EMP-ID format:
#   "Check the leave balance for EMP-0001"
#   "What is the leave balance for EMP-0022?"
#   "Who are the direct reports of EMP-0001?"
#   "Get the org chart for EMP-0001"
# Write tool:
#   "Submit Annual leave for EMP-0001 from 2027-06-16 to 2027-06-18"
#   "Book Sick leave for EMP-0022 from 2027-07-01 to 2027-07-01"
#   "Request Emergency leave for EMP-0001 on 2027-08-15"
# Multi-step:
#   "Check leave balance for EMP-0001 and look up the parental leave policy"
#   "Get the org chart for EMP-0001 and check their leave balance"
#   "Submit Annual leave for EMP-0001 from 2027-09-01 to 2027-09-03 and confirm balance"

# === AGENT ENDPOINT TEST ===
curl -s -X POST http://localhost:8000/agent/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the parental leave policy?"}' | python3 -m json.tool

curl -s -X POST http://localhost:8000/agent/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the remote work policy and how many days does James Chen have?"}' | python3 -m json.tool

# === FOUR-WAY ROUTER TEST ===
curl "http://localhost:8000/rag/classify?query=What+is+the+parental+leave+policy"
# Expected: {"classification": "rag"}

curl "http://localhost:8000/rag/classify?query=How+many+days+does+James+Chen+have"
# Expected: {"classification": "db"}

curl "http://localhost:8000/rag/classify?query=What+is+the+leave+policy+and+how+many+days+does+James+Chen+have"
# Expected: {"classification": "agent"}

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
| Sidebar shows "🤖 Agent: Offline" | Check `/agent/query` endpoint — restart FastAPI |
| DB answer not showing SQL expander | Check that `/rag/db/stream` is sending `sql_used` in the metadata event |
| `/rag/classify` returns `"chat"` for a DB question | Check that `rag_router.py` has four-way router — not the Phase 3 three-way version |
| `/rag/classify` returns `"db"` for compound question | Four-way router not updated — check `rag_router.py` for `"agent"` classification |
| `/agent/query` returns 500 | Check `agents/single/hr_advisor.py` — must use `from langchain.agents import create_agent` |
| Agent reasoning trace not showing | LangGraph 1.2.0 pattern — tool calls in `msg.tool_calls`, not `intermediate_steps` |
| Agent uses wrong tool | Tool description mismatch — check `agents/single/tools.py` tool descriptions |
| DeepEval `ToolCorrectnessMetric` fails | Check `tools_called` is populated from `result["tools_used"]` in `build_test_case()` |
| MCP server not starting | Check `uv run python scripts/start_mcp_server.py` — must be run from project root |
| MCP tools return 0 / no data | MCP server started but tool imports failed — check Tab 4 terminal for import errors |
| `curl` against port 8002 fails | Expected — FastMCP 3.x requires session handshake. Use `fastmcp.Client` in Python instead |
| MCP `check_leave_balance` returns "No employee found" | Verify EMP-ID format: must be `EMP-0001` not `EMP-1` or `emp-0001` |
| `submit_leave_request` fails with "Employee not found" | Employee ID doesn't exist in DB — verify with `SELECT employee_id FROM employees LIMIT 5` |
| `submit_leave_request` fails with date error | Dates must be `YYYY-MM-DD` format and end_date >= start_date |
| DeepEval MCP tests fail with "MCP server offline" | Restart `scripts/start_mcp_server.py` in Tab 4 before running MCP tests |
| DeepEval MCP 429 rate limit | Each MCP test has 3s sleep built in — if still hitting limits wait 60s between test functions |
| `/rag/db/query` returns 500 | Restart FastAPI — check that `from rag.database_rag.chain import db_rag_query` import is present in `routes/rag.py` |
| DB answer returns `NOT_DB_QUERY` text in UI | Question was misclassified as `"db"` but GPT-4o returned NOT_DB_QUERY — question is policy-related, not a DB question |
| DeepEval 429 rate limit error | Wait 60 seconds, re-run the specific test function |
| DeepEval timeout error | Verify env vars set: `echo $DEEPEVAL_PER_TASK_TIMEOUT_SECONDS_OVERRIDE` |
| `/rag/classify` returns 500 | Restart FastAPI — likely import error on startup |
| Chat not streaming | Check trailing slash: must call `/chat/` not `/chat` |
| Parental leave returns wrong answer | Re-run indexer: `uv run python -m vector_store.indexer` |
| PostgreSQL connection error | Run `docker compose ps` — verify `hr_postgres` is healthy. Use `hr_user` not `postgres` as the DB user |

---

*Document version: June 2026 | ARIA v0.5.0 | Phases 0–5 complete*
*Built by: Ryan Rodrigues | Nu Skin Enterprises — Data Platform Architecture*
