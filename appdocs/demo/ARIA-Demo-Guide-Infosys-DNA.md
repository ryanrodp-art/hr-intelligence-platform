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

# 9. Verify five-way router
curl "http://localhost:8000/rag/classify?query=What+is+the+parental+leave+policy"
# Expected: {"classification": "rag"}

curl "http://localhost:8000/rag/classify?query=How+many+leave+days+does+James+Chen+have"
# Expected: {"classification": "db"}

curl "http://localhost:8000/rag/classify?query=What+is+the+leave+policy+and+how+many+days+does+James+Chen+have"
# Expected: {"classification": "agent"}

curl "http://localhost:8000/rag/classify?query=Check+the+leave+balance+for+EMP-0001"
# Expected: {"classification": "mcp"}

curl "http://localhost:8000/rag/classify?query=Cancel+Annual+leave+for+EMP-0001+starting+2027-06-16"
# Expected: {"classification": "mcp"}

# 10. Verify agent endpoint
curl -s -X POST http://localhost:8000/agent/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the parental leave policy?"}' | python3 -m json.tool
# Expected: {"answer": "...", "tools_used": ["search_policies"], "success": true}

# 11. Verify MCP server tools (FastMCP Python client — curl won't work for MCP 3.x)
uv run python -c "
import asyncio
from fastmcp import Client
async def check():
    async with Client('http://localhost:8002/mcp') as c:
        tools = await c.list_tools()
        print([t.name for t in tools])
asyncio.run(check())
"
# Expected: ['check_leave_balance', 'submit_leave_request', 'cancel_leave_request',
#            'get_org_chart', 'policy_lookup']

# 12. Verify MCP endpoint via FastAPI
curl -s -X POST http://localhost:8000/mcp/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Check the leave balance for EMP-0001"}' | python3 -m json.tool
# Expected: {"answer": "James Chen has 30 days...", "tools_used": ["check_leave_balance"], "success": true}
```

**You should see before the demo starts:**
- ✅ Streamlit UI open with "Backend Connected" in sidebar
- ✅ Sidebar shows "📄 19 policy chunks indexed"
- ✅ Sidebar shows "🤖 Agent: Online"
- ✅ Sidebar shows "🔧 MCP Server: Online"
- ✅ ARIA welcome message visible in chat
- ✅ DB RAG query returns `{"answer": "James Chen has 30 days of leave remaining.", "success": true}`
- ✅ Router returns `{"classification": "db"}` for the James Chen name question
- ✅ Router returns `{"classification": "agent"}` for the compound question
- ✅ Router returns `{"classification": "mcp"}` for the EMP-0001 question
- ✅ Agent endpoint returns `{"tools_used": ["search_policies"], "success": true}`
- ✅ MCP server returns 5 tools: `check_leave_balance`, `submit_leave_request`, `cancel_leave_request`, `get_org_chart`, `policy_lookup`
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
│ MCP action badge · Write confirmation banner            │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP (SSE streaming / JSON)
┌──────────────────────▼──────────────────────────────────┐
│                   FASTAPI BACKEND                        │
│  /chat/stream  /rag/stream  /rag/db/stream              │
│  /agent/query  /mcp/query                               │
│  /rag/classify  /rag/status  /chat/stats                │
└──────┬──────────────────────────────────┬───────────────┘
       │                                  │
       │                    ┌─────────────▼──────────────┐
       │                    │   FIVE-WAY ROUTER           │
       │                    │   GPT-4o · temperature=0   │
       │                    │  mcp/rag/db/chat/agent     │
       │                    └──┬──┬──────┬──┬────────────┘
       │                       │  │      │  │
       │          ┌────────────▼┐ │ ┌────▼──▼────────────┐
       │          │  DOCUMENT   │ │ │  DATABASE RAG      │
       │          │  RAG CHAIN  │ │ │  NL-to-SQL (GPT-4o)│
       │          │  GPT-4o     │ │ │  SQLAlchemy        │
       │          └──────┬──────┘ │ └────────┬───────────┘
       │                 │        │           │
       │     ┌───────────▼──┐ ┌──▼──┐ ┌─────▼──────────┐
       │     │   CHROMADB   │ │CHAT │ │  POSTGRESQL    │
       │     │  19 vectors  │ │GPT  │ │  50 employees  │
       │     └──────────────┘ └─────┘ │  30+ leave recs│
       │                              └────────────────┘
       │
┌──────▼─────────────────────────────────────────────────┐
│          SINGLE HR ADVISOR AGENT (Phase 4 + 5)          │
│   LangChain create_agent · 8 tools · temp=0            │
│                                                         │
│   Phase 4 Direct Tools (natural language inputs):       │
│   ┌──────────────┐ ┌───────────────┐ ┌───────────────┐ │
│   │search_policie│ │lookup_employee│ │search_knowled-│ │
│   │s → ChromaDB  │ │→ PostgreSQL   │ │ge_base→ChromDB│ │
│   └──────────────┘ └───────────────┘ └───────────────┘ │
│                                                         │
│   Phase 5 MCP Tools (EMP-ID / structured inputs):      │
│   ┌─────────────┐ ┌──────────────┐ ┌──────────────┐   │
│   │check_leave_ │ │submit_leave_ │ │cancel_leave_ │   │
│   │balance → PG │ │request → PG✍️│ │request → PG🗑│   │
│   └─────────────┘ └──────────────┘ └──────────────┘   │
│   ┌─────────────┐ ┌──────────────┐                     │
│   │get_org_chart│ │policy_lookup │                     │
│   │→ PG self-jn │ │→ ChromaDB    │                     │
│   └─────────────┘ └──────────────┘                     │
└─────────────────────────┬──────────────────────────────┘
                          │ HTTP → localhost:8002/mcp
┌─────────────────────────▼──────────────────────────────┐
│              FASTMCP SERVER (Port 8002)                  │
│   FastMCP 3.3.1 · HTTP Transport · /mcp endpoint        │
│   5 tools: check_leave_balance · submit_leave_request   │
│            cancel_leave_request · get_org_chart         │
│            policy_lookup                                │
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
| **5** *(Done)* | MCP server, 5 action tools, first DB write + delete, 8-tool agent, five-way routing | + TaskCompletion (MCP), AnswerRelevancy (MCP), ToolRouting |
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
- 🤖 Agent: Online
- 🔧 MCP Server: Online
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
- 🔍 Answered from company documents badge — classified as `rag`, routed to ChromaDB
- 📄 Sources: Leave Policy, Page 1 — citation appears below answer
- Specific facts: "Primary caregivers receive 16 weeks of fully paid parental leave"

**Message 2:**
```
How many days of annual leave do I get?
```
*Point out: "25 days per calendar year, accruing at 2.08 days per month" — exact numbers from the PDF, cited*

**Message 3:**
```
How do I report a harassment complaint?
```
*Point out: All 4 grievance steps listed. Source: Code of Conduct, Page 1. Different document — the router found the right one.*

**Message 4:**
```
What does the company contribute to the 401k?
```
*Point out: "100% of first 3%, 50% of next 3%, vests over 3 years" — Benefits Guide, Page 1. Four different documents, intelligent routing across all.*

> *"The key insight: ARIA didn't know any of these specific numbers from training. She retrieved them from your documents at query time, grounded her answer in them, and cited the source. That's Retrieval-Augmented Generation — and crucially we can now measure whether this is working correctly. That's what DeepEval does."*

---

## Demo Section D — Phase 3: Database RAG Demo *(4 minutes)*

> *"Phase 3 gives ARIA a second knowledge source — the live employee database. The router now has three paths: document search, database query, or general chat."*

**Type these five messages — pause after each to show the SQL expander:**

**Message 1:**
```
How many leave days does James Chen have?
```
*Point out:*
- 🗄️ Answered from employee database · 1 record(s) found badge — classified as `db`
- `View database query` expander — click and show the SQL
- GPT-4o generated `ILIKE` name matching from the question
- Answer: "James Chen has 30 days of leave remaining."

**Message 2:**
```
Who is currently on leave?
```
*Point out:*
- "Isabella Fernandez is currently on leave." — name only by design
- SQL shows `WHERE e.status = 'On Leave'` — GPT-4o inferred the right column value
- Real-time data from PostgreSQL, not cached

**Message 3:**
```
Who reports to the VP of Engineering?
```
*Point out:*
- Multi-table JOIN — employees table joined to org_chart table
- "Priya Sharma and Marcus Johnson report to the VP of Engineering"
- Show SQL expander — subquery to find VP employee_id then JOIN for direct reports

**Message 4:**
```
How many employees are in each department?
```
*Point out: Aggregate GROUP BY — "Engineering: 15, Sales: 10, Finance: 9, HR: 8, Marketing: 8"*

**Message 5 (immediate follow-up to show router switching):**
```
What is the parental leave policy?
```
*Point out:*
- Answer switches to 🔍 Answered from company documents — back to document RAG
- Source citation reappears: Leave Policy, Page 1
- SQL expander gone — came from ChromaDB not PostgreSQL
- *"Same interface, two completely different knowledge sources. The router makes the decision transparently."*

> *"The SQL expander is a deliberate design choice for enterprise AI. When an AI gives you a number about a specific employee, you want to be able to audit how it got there. The SQL is the audit trail."*

---

## Demo Section E — Phase 4: Single HR Advisor Agent *(5 minutes)*

> *"Phase 4 is where ARIA stops following rules and starts reasoning. Instead of a hardcoded router, we now have a LangChain ReAct agent that reads the question, decides which tool to use, calls it, reads the result, and decides if it needs more information."*

**Type these four messages — pause after each to show the reasoning trace:**

**Message 1 — Single tool, policy:**
```
What is the parental leave policy?
```
*Point out:*
- 🤖 **Agent** badge — went through the ReAct agent
- `📄 search_policies` tool badge
- Click **🧠 Agent Reasoning (1 step)** expander
- Step 1: Tool input `{'query': 'parental leave policy'}` → retrieved policy text

**Message 2 — Single tool, employee:**
```
How many leave days does James Chen have?
```
*Point out:*
- `👤 lookup_employee` tool badge — agent chose the database tool
- Tool input: `{'query': "What is James Chen's leave balance?"}`
- *"Zero hardcoded rules. Pure reasoning — it saw a person's name and chose the database tool."*

**Message 3 — Compound query, two tools:**
```
What is the remote work policy and how many days does James Chen have?
```
*Point out:*
- Both `📄 search_policies` AND `👤 lookup_employee` badges appear
- Click **🧠 Agent Reasoning (2 steps)**
- Step 1: `search_policies` → handbook content
- Step 2: `lookup_employee` → "30 days"
- *"One question, two knowledge sources, two tool calls, one coherent answer. This is what the router classified as 'agent'."*

**Message 4 — Broad knowledge base:**
```
What should a new hire know about their first week?
```
*Point out:*
- `🔍 search_knowledge_base` badge — broad cross-cutting search
- Pulls from onboarding, IT setup, buddy programme across multiple sections
- *"Three tools. The agent chose each one without being told."*

> *"What you just saw is a ReAct agent — Reason and Act. The reasoning trace in the UI is not cosmetic — it's the actual internal thought process of the agent, captured as it runs."*

---

## Demo Section K — Phase 5: MCP Server — From Answers to Actions *(7 minutes)*

> *"Phase 4 ARIA could tell you things. Phase 5 ARIA can do things — and undo them. This is the most important capability jump in the platform, built on MCP, Anthropic's open standard for connecting AI agents to external tools.*
>
> *Phase 4 tools were baked directly into the agent's code. Phase 5 tools run as a separate server on port 8002. Any MCP-compatible client — Claude Desktop, Cursor, another agent — can call these same tools without touching ARIA's code. That's what makes MCP an enterprise-grade standard."*

**Show the MCP server running in Terminal Tab 4:**
```
ARIA HR MCP Server
Transport: HTTP | Port: 8002
Endpoint: http://localhost:8002/mcp
Tools: check_leave_balance, submit_leave_request, get_org_chart, policy_lookup
```

**Explain the tool architecture shift:**
```
Phase 4 — 3 direct tools (natural language inputs):
  search_policies       → ChromaDB (read)
  lookup_employee       → PostgreSQL (read)
  search_knowledge_base → ChromaDB (read)

Phase 5 — adds 5 MCP tools via network service (EMP-ID inputs):
  check_leave_balance  → PostgreSQL (read)
  submit_leave_request → PostgreSQL (WRITE) ← first write in ARIA
  cancel_leave_request → PostgreSQL (DELETE) ← first delete in ARIA
  get_org_chart        → PostgreSQL (read, self-join)
  policy_lookup        → ChromaDB (read)

Total: 8 tools. 3 direct calls. 5 MCP network calls.
```

> **Important:** MCP queries use **Employee IDs** (EMP-XXXX format), not names. EMP-ID format → MCP tool. Name format → Phase 4 direct tool. The agent routes based on tool descriptions — no hardcoded rules.

**Type these five messages — pause after each:**

**Message 1 — MCP read, leave balance:**
```
Check the leave balance for EMP-0001
```
*Point out:*
- 🔧 **MCP Action** badge — classified as `mcp` by the five-way router
- `💰 check_leave_balance` tool badge
- Answer: "James Chen has 30 days of leave remaining. Status: Active"
- *"EMP-ID format → MCP tool. The router and agent both handle this boundary without any hardcoded rules."*

**Message 2 — MCP read, org chart:**
```
Who are the direct reports of EMP-0001?
```
*Point out:*
- `🏢 get_org_chart` tool badge
- Answer: James Chen, VP Engineering, top level — Marcus Johnson and Priya Sharma as direct reports
- *"One MCP tool call ran two SQL queries — employee info plus direct reports — sharing a single atomic connection."*

**Message 3 — MCP write — the milestone moment:**
```
Submit Annual leave for EMP-0001 from 2027-06-16 to 2027-06-18
```
*Point out:*
- `✍️ submit_leave_request` tool badge
- ✅ "Leave request submitted — record created in database" confirmation banner appears
- Answer: "Leave request submitted successfully for EMP-0001. Dates: 2027-06-16 to 2027-06-18 (3 days). Type: Annual. Status: Pending. Your manager will be notified for approval."
- *"This is the first time in this entire demo that ARIA wrote to the database. A user's natural language instruction just created a new record in PostgreSQL."*

**Verify the write in terminal — show the audience:**
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
*"There it is. Row in the database. Status: Pending."*

**Message 4 — MCP delete — close the loop:**
```
Cancel Annual leave for EMP-0001 starting 2027-06-16
```
*Point out:*
- `🗑️ cancel_leave_request` tool badge
- Answer: "Leave request cancelled successfully for EMP-0001. Annual leave from 2027-06-16 to 2027-06-18 has been removed. Status was: Pending."
- *"And now ARIA can undo it. The agent found the pending record, deleted it atomically, and confirmed. Write and delete — the complete leave management lifecycle, from natural language."*

**Verify the delete in terminal:**
```bash
docker exec -it hr_postgres psql -U hr_user -d hr_platform \
  -c "SELECT employee_id, start_date, end_date, leave_type, status FROM leave_records WHERE employee_id = 'EMP-0001' AND start_date = '2027-06-16';"
```
```
 employee_id | start_date | end_date | leave_type | status
-------------+------------+----------+------------+--------
(0 rows)
```
*"Gone. The agent completed the full workflow: submit, confirm, cancel, confirm. One HR workflow, zero human clicks on a system."*

**Message 5 — Compound MCP + direct tool:**
```
Check leave balance for EMP-0001 and look up the parental leave policy
```
*Point out:*
- `💰 check_leave_balance` (MCP) AND `📄 search_policies` (Phase 4 direct) badges both appear
- Answer combines MCP balance data + ChromaDB policy text
- *"The agent called tools from two completely different sources — a network MCP call and a direct Python function — and combined the results into one coherent answer. This is the 8-tool agent working as designed."*

> *"What you just saw is the transition from a Q&A system to an enterprise AI agent. Phase 4 ARIA was a very good assistant. Phase 5 ARIA can complete and reverse HR workflows. The same evaluation framework — the same DeepEval metrics, the same golden set discipline — applied to a system that now modifies database state on behalf of users."*

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

The judge is a separate GPT-4o instance evaluating ARIA's output. It reads the question, ARIA's answer, any retrieved context, and an evaluation rubric — then scores and explains its reasoning.

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

PHASE 3 — Database RAG
├── FaithfulnessMetric (DB)        Are DB answers grounded in SQL rows returned?
├── AnswerRelevancyMetric (DB)     Does the answer address the employee question?
└── Routing Boundary (assertion)   Do DB questions route 'db', policy questions 'rag'?

PHASE 4 — Single Agent
├── TaskCompletionMetric           Did the agent complete the full task?
├── ToolCorrectnessMetric          Did it choose the right tool(s)?
└── AnswerRelevancyMetric          Did the answer stay focused and on-point?

PHASE 5 — MCP Tools
├── TaskCompletionMetric (MCP)     Did the MCP action complete successfully?
├── AnswerRelevancyMetric (MCP)    Is the action response focused and accurate?
└── Tool Routing (assertion)       Did each question invoke the correct MCP tool?
                                   Covers all 5 tools across 13 golden set entries.

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

> *"Now I'll run the Phase 1 evaluation suite live. 5 test functions, 24 test cases, calling the live ARIA API and having GPT-4o judge every response."*

**Switch to Terminal Tab 3. Run:**

```bash
uv run deepeval test run evaluation/tests/test_chat.py -v
```

**When results appear:**

```
HR Role Adherence [GEval]   avg=0.95   pass=100%   14 cases
Answer Relevancy             avg=0.98   pass=100%   13 cases
Hallucination                avg=0.00   pass=100%   10 cases
Overall: 24/24 passed
```

**Key talking points:**
- Hallucination score `0.00` — best possible. ARIA never invents facts
- Cost: `$0.19` for 24 test cases — cheap enough to run on every pull request

---

## Demo Section H — Phase 2 DeepEval Suite Live *(9 minutes)*

> *"Phase 2 introduces four RAG-specific metrics that don't exist in standard LLM evaluation."*

**Run as one block:**

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

### Final Phase 2 Results

| Test | Metric | Score | Pass Rate | Cost |
|---|---|---|---|---|
| Faithfulness | Claims grounded in docs | **1.00** | 100% | $0.029 |
| Contextual Precision | Best chunk ranked first | **1.00** | 100% | $0.018 |
| Contextual Recall | All needed info retrieved | **1.00** | 100% | $0.011 |
| Answer Relevancy | Response addresses question | **1.00** | 100% | $0.012 |
| Document Routing | All policy questions → RAG | **100%** | 100% | $0.000 |
| **Total Phase 2** | | **1.00** | **100%** | **$0.07** |

---

## Demo Section I — Phase 3: DeepEval Suite *(5 minutes)*

**Run routing boundary first — no LLM judge, instant:**

```bash
uv run deepeval test run evaluation/tests/test_database_rag.py::test_db_routing_boundary -v
```

```
test_db_routing_boundary PASSED — 13/13 assertions correct
Cost: $0.00 | Time: ~13s
```

**Run LLM-judged tests with sleep gaps:**

```bash
sleep 60 && \
uv run deepeval test run evaluation/tests/test_database_rag.py::test_db_employee_lookup -v && \
sleep 60 && \
uv run deepeval test run evaluation/tests/test_database_rag.py::test_db_aggregate_queries -v && \
sleep 60 && \
uv run deepeval test run evaluation/tests/test_database_rag.py::test_db_join_queries -v
```

### Final Phase 3 Results

| Test | Metric | Pass Rate | Cases | Cost | Time |
|---|---|---|---|---|---|
| Routing Boundary | 13 assertions | **100%** | 13 | $0.000 | ~13s |
| Employee Lookup | Faithfulness + Relevancy | **100%** | 3 | ~$0.030 | ~15s |
| Aggregate Queries | Faithfulness + Relevancy | **100%** | 3 | ~$0.030 | ~15s |
| Join Queries | Faithfulness + Relevancy | **100%** | 2 | ~$0.020 | ~12s |

---

## Demo Section J — Phase 4: DeepEval Agent Suite *(5 minutes)*

> *"Phase 4 introduces three DeepEval metrics designed specifically for agents."*

**Run the full Phase 4 suite:**

```bash
uv run deepeval test run evaluation/tests/test_single_agent.py -v
```

**When results appear:**

```
Task Completion     avg=0.95   pass=100%   9 cases
Tool Correctness    avg=1.00   pass=100%   19 cases
Answer Relevancy    avg=0.90   pass=100%   9 cases
Overall: 19/19 passed
```

### Final Phase 4 Results

| Test | Metrics | Pass Rate | Cases | Cost | Time |
|---|---|---|---|---|---|
| Policy queries | TaskCompletion + ToolCorrectness + AnswerRelevancy | **100%** | 3 | ~$0.025 | ~15s |
| Employee queries | ToolCorrectness + AnswerRelevancy | **100%** | 3 | ~$0.010 | ~20s |
| Compound queries | TaskCompletion + ToolCorrectness + AnswerRelevancy | **100%** | 3 | ~$0.025 | ~20s |
| Tool boundary | ToolCorrectness only | **100%** | 10 | $0.000 | ~40s |
| **Total Phase 4** | | **100%** | **19** | **$0.073** | **~115s** |

---

## Demo Section L — Phase 5: DeepEval MCP Suite *(5 minutes)*

> *"Phase 5 has five tests — four LLM-judged, one pure boundary assertion. We cover all five MCP tools across 13 golden set entries."*

### Golden Set — `evaluation/datasets/mcp_golden_set.json`

13 entries across 4 categories:

| # | Input | Type | Expected Tool |
|---|---|---|---|
| 1 | "Check the leave balance for EMP-0001" | read | `check_leave_balance` |
| 2 | "What is the leave balance for EMP-0022?" | read | `check_leave_balance` |
| 3 | "What is James Chen's position and who reports to him? Use EMP-0001" | read | `get_org_chart` |
| 4 | "Who are the direct reports of EMP-0001?" | read | `get_org_chart` |
| 5 | "Submit Annual leave for EMP-0001 from 2027-01-02 to 2027-01-03" | write | `submit_leave_request` |
| 6 | "Book Sick leave for EMP-0022 from 2027-01-10 to 2027-01-10" | write | `submit_leave_request` |
| 7 | "Request Emergency leave for EMP-0001 on 2027-02-14" | write | `submit_leave_request` |
| 8 | "Cancel Annual leave for EMP-0001 starting 2027-01-02" | cancel | `cancel_leave_request` |
| 9 | "Delete the Sick leave request for EMP-0022 on 2027-01-10" | cancel | `cancel_leave_request` |
| 10 | "Withdraw Emergency leave for EMP-0001 starting 2027-02-14" | cancel | `cancel_leave_request` |
| 11 | "Check leave balance for EMP-0001 and look up the parental leave policy" | multi_step | `check_leave_balance` |
| 12 | "Get the org chart for EMP-0001 and check their leave balance" | multi_step | `get_org_chart` |
| 13 | "Submit Annual leave for EMP-0001 from 2027-03-01 to 2027-03-03 and confirm balance" | multi_step | `submit_leave_request` |

> **Run order dependency:** Cancel entries (8–10) depend on write entries (5–7) having created the pending records first. Always run `test_mcp_write_tool` before `test_mcp_cancel_tool`.

**Run the boundary test first — no cost, no LLM judge:**

```bash
uv run deepeval test run evaluation/tests/test_mcp.py::test_mcp_tool_routing_boundary -v
```

*While it runs:*
> *"This test calls all 13 golden set questions through the live agent and verifies each one invoked the correct MCP tool. 13 questions × 3-second sleep = ~78 seconds. Zero cost. All five MCP tools are covered — read, write, delete, and multi-step."*

**When results appear:**
```
13/13 entries routed to correct MCP tool — PASSED
Cost: $0.00 | Time: ~78s
```

**Run the LLM-judged tests in dependency order:**

```bash
# 1. Read tools — no dependencies
uv run deepeval test run evaluation/tests/test_mcp.py::test_mcp_read_tools -v
```

### test_mcp_read_tools *(~21 seconds)*
> *"Three read tool questions — two leave balance checks via EMP-ID, one org chart lookup. TaskCompletionMetric at 0.98, AnswerRelevancy at 1.00."*

```bash
# 2. Write tool — creates records that cancel tests depend on
uv run deepeval test run evaluation/tests/test_mcp.py::test_mcp_write_tool -v
```

### test_mcp_write_tool *(~21 seconds)*
> *"Three write operations — Annual, Sick, and Emergency leave submissions for two different employees. Both metrics at 1.00 across all three. TaskCompletionMetric correctly recognises that submitting a leave request was completed, not just described."*

```bash
# 3. Cancel tool — must run AFTER write tool (deletes what was submitted above)
uv run deepeval test run evaluation/tests/test_mcp.py::test_mcp_cancel_tool -v
```

### test_mcp_cancel_tool *(~21 seconds)*
> *"Three cancel operations — cancelling the Annual, Sick, and Emergency leave records created in the write test. TaskCompletionMetric evaluates whether the deletion was confirmed correctly. Both write and delete now have LLM judge coverage. Together, write + cancel tests prove the complete leave management lifecycle."*

**Expected results:**
```
Task Completion:   avg=1.00  pass=100%  total=3
Answer Relevancy:  avg=1.00  pass=100%  total=3
```

```bash
# 4. Multi-step — independent of write/cancel
uv run deepeval test run evaluation/tests/test_mcp.py::test_mcp_multi_step -v
```

### test_mcp_multi_step *(~29 seconds)*
> *"Three multi-step sequences — balance check plus policy lookup, org chart plus balance, submit leave plus confirm balance. Two MCP tool calls in a single reasoning loop. Task Completion 0.98, Answer Relevancy 0.95."*

**Run the complete Phase 5 suite in correct order:**

```bash
# Correct run order (cancel depends on write)
uv run deepeval test run evaluation/tests/test_mcp.py::test_mcp_tool_routing_boundary -v && \
uv run deepeval test run evaluation/tests/test_mcp.py::test_mcp_read_tools -v && \
uv run deepeval test run evaluation/tests/test_mcp.py::test_mcp_write_tool -v && \
uv run deepeval test run evaluation/tests/test_mcp.py::test_mcp_cancel_tool -v && \
uv run deepeval test run evaluation/tests/test_mcp.py::test_mcp_multi_step -v
```

### Final Phase 5 Results

| Test | Metrics | Avg Score | Pass Rate | Cases | Cost | Time |
|---|---|---|---|---|---|---|
| Tool routing boundary | Assertion (no judge) | 100% | **100%** | 13 | $0.000 | ~78s |
| MCP read tools | TaskCompletion + AnswerRelevancy | 0.99 | **100%** | 3 | $0.024 | ~21s |
| MCP write tool | TaskCompletion + AnswerRelevancy | **1.00** | **100%** | 3 | $0.025 | ~21s |
| MCP cancel tool | TaskCompletion + AnswerRelevancy | **1.00** | **100%** | 3 | $0.025 | ~21s |
| MCP multi-step | TaskCompletion + AnswerRelevancy | 0.97 | **100%** | 3 | $0.031 | ~29s |
| **Total Phase 5** | | **0.99** | **100%** | **25** | **$0.105** | **~170s** |

> *"$0.10 to evaluate a system that can write to and delete from a production database on behalf of users. That's the ROI of evaluation-first development."*

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

---

## What This Proves for de.ai *(1 minute)*

**1. Evaluation-first architecture works**
DeepEval was integrated from Phase 0 — not bolted on at the end. Every phase adds metrics before adding features.

**2. Metric coverage scales with capability**
Three metrics in Phase 1. Seven in Phase 2. Fourteen across five phases. The framework grows with the system.

**3. Cost is not a barrier**
Under $0.60 total across all five evaluation suites — chat, document RAG, database RAG, agent, and MCP (including cancel). Routing boundary tests are $0.00 — zero cost to run on every commit.

**4. Framework-agnostic design**
ARIA uses GPT-4o today. Swapping to Claude, Gemini, or a fine-tuned Llama model requires changing two lines in `.env`. The evaluation suite runs unchanged.

**5. Agentic reasoning is measurable**
Phase 4 demonstrates that agent behaviour — specifically tool selection — is fully measurable with `ToolCorrectnessMetric`. 1.00 across 10 diverse queries.

**6. AI agents can perform and reverse actions safely**
Phase 5 demonstrates that an AI agent can write to a production database (`submit_leave_request`) and delete from it (`cancel_leave_request`). DeepEval's `TaskCompletionMetric` correctly evaluates whether both operations completed. 1.00 across all 6 write and cancel test cases. The same evaluation framework that validates answers also validates actions and reversals.

**7. MCP is the enterprise integration standard**
The Phase 5 MCP server runs independently of the agent — any MCP-compatible client can call the same tools without code changes.

**8. Hybrid knowledge architecture is production-ready**
Phases 3–5 together: a single assistant that transparently switches between document retrieval (ChromaDB), database querying (PostgreSQL), network MCP tool calls (port 8002), database writes, and database deletes — based on the nature of the question.

**9. Data sovereignty is solved**
SmithDB's self-hosted VPC deployment means no sensitive AI traces leave the Infosys infrastructure boundary.

---

## If the Principal Architect Wants to Go Deeper

### The ReAct Agent Pattern — Why Tool Descriptions Are Everything
The ReAct agent selects tools based entirely on their docstring descriptions — not hardcoded rules. The `lookup_employee` tool description explicitly states "Always use this tool when the question mentions a person by name." The `check_leave_balance` description says "employee_id must be in format EMP-XXXX." These two rules alone produce correct tool routing: names → Phase 4 direct tools, EMP-IDs → Phase 5 MCP tools. Tool description engineering is the critical work — `ToolCorrectnessMetric` is the quality gate.

### The Five-Way Router
The five-way router adds `"mcp"` as the **highest priority** classification — any question containing an EMP-XXXX ID, or using an explicit action verb (submit, book, request, cancel, delete, withdraw), routes to MCP before any other classification is considered. This prevents EMP-ID questions from falling through to `"db"` (which uses name-based NL-to-SQL) and ensures write/delete actions always go through the validated MCP tool layer.

### Why `cancel_leave_request` Uses IN({placeholders}) Not ANY(:ids)
`cancel_leave_request` fetches all pending records matching the employee/date, then deletes them all in one statement. SQLAlchemy's `text()` layer does not bind Python lists correctly to PostgreSQL's `ANY(:ids)` operator — it transmits only the first element. The correct pattern is to build explicit named parameters (`id_0`, `id_1`, ...) and a matching `IN (:id_0, :id_1, ...)` clause. Both the SELECT and DELETE run inside one `engine.begin()` transaction — atomic read + delete with auto-commit on success.

### The Duplicate Guard in submit_leave_request
After Phase 5 testing, a duplicate check was added to `submit_leave_request`: if a pending record already exists for the same employee and start date, the tool returns an informative error rather than inserting a duplicate. This means DeepEval write tests can only run once per database state — to re-run, either cancel the records first (using `cancel_leave_request`) or reset the database. The golden set is designed accordingly: write entries (5–7) use dates in 2027-01, cancel entries (8–10) cancel those same records.

### Why Two Separate Tool Sets Coexist (Phase 4 direct + Phase 5 MCP)
Phase 4 tools accept natural language — names, questions, phrases. Phase 5 MCP tools accept structured inputs — EMP-IDs, YYYY-MM-DD dates, leave type enums. The agent's tool descriptions create a natural routing boundary without hardcoded rules. This is the correct design: two tool layers with distinct input contracts serving distinct user intents.

### Why FastMCP 3.x Cannot Be Verified with curl
FastMCP 3.x uses Streamable HTTP transport, which requires a session ID established through an MCP handshake. Raw curl skips the handshake and fails with "Missing session ID". Use the `fastmcp.Client` Python context manager — it handles the handshake transparently.

### The First Database Write and Delete — Why It Matters Architecturally
`submit_leave_request` is the first mutation — it inserts into `leave_records` with `status='Pending'`. `cancel_leave_request` is the first deletion — it removes pending rows atomically. Both use `engine.begin()` — auto-commits on success, auto-rolls back on exception. The employee existence check and the insert share one connection — validate first, write atomically, confirm explicitly. This is the pattern for all AI-initiated mutations: no partial writes.

### SQL Safety Validation
Every SQL string generated by GPT-4o passes through `validate_sql()` before execution — must begin with `SELECT`, must not contain `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`, `CREATE`, `GRANT`, `REVOKE`. The MCP tools bypass this validator because they use parameterised `text()` queries directly, not GPT-4o-generated SQL — they are safe by construction.

---

## Quick Reference — All Streamlit Queries by Route

### 💬 Chat Route (casual / off-topic → `chat`)
```
Hello ARIA, what can you help me with?
Can you help me write a Python script to sort a list?
What was the first thing I asked you?
What is human resources?
```

### 🔍 Document RAG Route (policy questions → `rag`)
```
What is the parental leave policy?
How many days of annual leave do I get?
How do I report a harassment complaint?
What does the company contribute to the 401k?
What is the remote work policy?
What is the probation period notice?
What are the working hours at Acme Corp?
```

### 🗄️ Database RAG Route (named employee data → `db`)
```
How many leave days does James Chen have?
Who is currently on leave?
Who reports to the VP of Engineering?
How many employees are in each department?
How many employees are in Engineering?
Who is in the HR department?
How many leave records are pending?
```

### 🤖 Agent Route (compound: policy + named employee → `agent`)
```
What is the remote work policy and how many days does James Chen have?
Tell me about parental leave and how much leave does Isabella Fernandez have?
What is the annual leave entitlement and who is currently on leave?
What is the leave policy and what is Sarah's department?
```

### 🔧 MCP Route (EMP-ID queries and action requests → `mcp`)

**Read tools:**
```
Check the leave balance for EMP-0001
What is the leave balance for EMP-0022?
Who are the direct reports of EMP-0001?
Get the org chart for EMP-0001
What is James Chen's position and who reports to him? Use employee ID EMP-0001
```

**Write tool:**
```
Submit Annual leave for EMP-0001 from 2027-06-16 to 2027-06-18
Book Sick leave for EMP-0022 from 2027-07-01 to 2027-07-01
Request Emergency leave for EMP-0001 on 2027-08-15
Submit Parental leave for EMP-0001 from 2027-09-01 to 2027-10-31
```

**Cancel tool:**
```
Cancel Annual leave for EMP-0001 starting 2027-06-16
Delete the pending Sick leave for EMP-0022 on 2027-07-01
Withdraw Emergency leave for EMP-0001 starting 2027-08-15
Cancel my leave request for EMP-0001 on 2027-06-16
```

**Multi-step MCP + direct:**
```
Check leave balance for EMP-0001 and look up the parental leave policy
Get the org chart for EMP-0001 and check their leave balance
Submit Annual leave for EMP-0001 from 2027-09-01 to 2027-09-03 and confirm balance
```

---

## Quick Reference — All Demo Commands

```bash
# === INFRASTRUCTURE ===
docker compose up -d                    # Start PostgreSQL + ChromaDB
docker compose ps                       # Verify both healthy

# === APPLICATION ===
# Tab 1 — FastAPI:
uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# Tab 2 — Streamlit:
uv run streamlit run frontend/app.py --server.port 8501

# Tab 4 — MCP Server (keep running throughout demo):
uv run python scripts/start_mcp_server.py

# Browser:
open http://localhost:8501
open http://localhost:8000/docs         # FastAPI interactive docs

# === HEALTH CHECKS ===
curl http://localhost:8000/health
curl http://localhost:8000/rag/status
curl http://localhost:8000/chat/stats

# === FIVE-WAY ROUTER TESTS ===
curl "http://localhost:8000/rag/classify?query=What+is+the+parental+leave+policy"
# Expected: {"classification": "rag"}

curl "http://localhost:8000/rag/classify?query=How+many+leave+days+does+James+Chen+have"
# Expected: {"classification": "db"}

curl "http://localhost:8000/rag/classify?query=What+is+the+leave+policy+and+how+many+days+does+James+Chen+have"
# Expected: {"classification": "agent"}

curl "http://localhost:8000/rag/classify?query=Check+the+leave+balance+for+EMP-0001"
# Expected: {"classification": "mcp"}

curl "http://localhost:8000/rag/classify?query=Cancel+Annual+leave+for+EMP-0001+starting+2027-06-16"
# Expected: {"classification": "mcp"}

curl "http://localhost:8000/rag/classify?query=Submit+Annual+leave+for+EMP-0001+from+2027-06-16+to+2027-06-18"
# Expected: {"classification": "mcp"}

# === DB RAG ENDPOINT TESTS ===
curl -s -X POST http://localhost:8000/rag/db/query \
  -H "Content-Type: application/json" \
  -d '{"question": "How many leave days does James Chen have?"}' | python3 -m json.tool

curl -s -X POST http://localhost:8000/rag/db/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Who is currently on leave?"}' | python3 -m json.tool

# === AGENT ENDPOINT TESTS ===
curl -s -X POST http://localhost:8000/agent/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the parental leave policy?"}' | python3 -m json.tool

curl -s -X POST http://localhost:8000/agent/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the remote work policy and how many days does James Chen have?"}' | python3 -m json.tool

# === MCP ENDPOINT TESTS ===
curl -s -X POST http://localhost:8000/mcp/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Check the leave balance for EMP-0001"}' | python3 -m json.tool

curl -s -X POST http://localhost:8000/mcp/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Submit Annual leave for EMP-0001 from 2027-06-16 to 2027-06-18"}' | python3 -m json.tool

curl -s -X POST http://localhost:8000/mcp/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Cancel Annual leave for EMP-0001 starting 2027-06-16"}' | python3 -m json.tool

# === MCP SERVER DIRECT TOOL VERIFICATION ===
# List all registered tools (5 expected)
uv run python -c "
import asyncio
from fastmcp import Client
async def check():
    async with Client('http://localhost:8002/mcp') as c:
        tools = await c.list_tools()
        print([t.name for t in tools])
asyncio.run(check())
"
# Expected: ['check_leave_balance', 'submit_leave_request', 'cancel_leave_request',
#            'get_org_chart', 'policy_lookup']

# Test check_leave_balance
uv run python -c "
import asyncio
from fastmcp import Client
async def test():
    async with Client('http://localhost:8002/mcp') as c:
        r = await c.call_tool('check_leave_balance', {'employee_id': 'EMP-0001'})
        print(r.data)
asyncio.run(test())
"

# Test submit_leave_request (WRITE)
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

# Test cancel_leave_request (DELETE)
uv run python -c "
import asyncio
from fastmcp import Client
async def test():
    async with Client('http://localhost:8002/mcp') as c:
        r = await c.call_tool('cancel_leave_request', {
            'employee_id': 'EMP-0001', 'start_date': '2027-06-16',
            'leave_type': 'Annual'})
        print(r.data)
asyncio.run(test())
"

# Test get_org_chart
uv run python -c "
import asyncio
from fastmcp import Client
async def test():
    async with Client('http://localhost:8002/mcp') as c:
        r = await c.call_tool('get_org_chart', {'employee_id': 'EMP-0001'})
        print(r.data)
asyncio.run(test())
"

# Test policy_lookup
uv run python -c "
import asyncio
from fastmcp import Client
async def test():
    async with Client('http://localhost:8002/mcp') as c:
        r = await c.call_tool('policy_lookup', {'query': 'parental leave entitlement'})
        print(str(r.data)[:300])
asyncio.run(test())
"

# === DATABASE VERIFICATION ===
# Verify write
docker exec -it hr_postgres psql -U hr_user -d hr_platform \
  -c "SELECT employee_id, start_date, end_date, leave_type, status FROM leave_records WHERE employee_id = 'EMP-0001' ORDER BY id DESC LIMIT 5;"

# Verify cancel (row should be gone)
docker exec -it hr_postgres psql -U hr_user -d hr_platform \
  -c "SELECT employee_id, start_date, leave_type, status FROM leave_records WHERE employee_id = 'EMP-0001' AND start_date = '2027-06-16';"

# Count records
docker exec -it hr_postgres psql -U postgres -d hr_platform \
  -c "SELECT COUNT(*) FROM employees;"            # Expected: 50
docker exec -it hr_postgres psql -U postgres -d hr_platform \
  -c "SELECT COUNT(*) FROM leave_records;"        # varies with test runs
docker exec -it hr_postgres psql -U postgres -d hr_platform \
  -c "SELECT employee_id, first_name, last_name, leave_balance FROM employees WHERE first_name = 'James' AND last_name = 'Chen';"

# === DEEPEVAL ENV VARS ===
export DEEPEVAL_PER_TASK_TIMEOUT_SECONDS_OVERRIDE=600
export DEEPEVAL_PER_ATTEMPT_TIMEOUT_SECONDS_OVERRIDE=300

# === PHASE 1 EVALS ===
uv run deepeval test run evaluation/tests/test_chat.py -v

# === PHASE 2 EVALS ===
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
uv run deepeval test run evaluation/tests/test_database_rag.py::test_db_routing_boundary -v && \
sleep 60 && \
uv run deepeval test run evaluation/tests/test_database_rag.py::test_db_employee_lookup -v && \
sleep 60 && \
uv run deepeval test run evaluation/tests/test_database_rag.py::test_db_aggregate_queries -v && \
sleep 60 && \
uv run deepeval test run evaluation/tests/test_database_rag.py::test_db_join_queries -v

# === PHASE 4 EVALS ===
uv run deepeval test run evaluation/tests/test_single_agent.py -v
# Individual:
uv run deepeval test run evaluation/tests/test_single_agent.py::test_agent_policy_queries -v
uv run deepeval test run evaluation/tests/test_single_agent.py::test_agent_employee_queries -v
uv run deepeval test run evaluation/tests/test_single_agent.py::test_agent_compound_queries -v
uv run deepeval test run evaluation/tests/test_single_agent.py::test_agent_tool_correctness_boundary -v

# === PHASE 5 EVALS (run in order — cancel depends on write) ===
uv run deepeval test run evaluation/tests/test_mcp.py::test_mcp_tool_routing_boundary -v
uv run deepeval test run evaluation/tests/test_mcp.py::test_mcp_read_tools -v
uv run deepeval test run evaluation/tests/test_mcp.py::test_mcp_write_tool -v
uv run deepeval test run evaluation/tests/test_mcp.py::test_mcp_cancel_tool -v
uv run deepeval test run evaluation/tests/test_mcp.py::test_mcp_multi_step -v
```

---

## Troubleshooting During Demo

| Problem | Fix |
|---|---|
| Streamlit shows "Backend Offline" | Run Tab 1 uvicorn command |
| Sidebar shows "Document search unavailable" | `curl http://localhost:8001/api/v2/heartbeat` — restart Docker if needed |
| Sidebar shows "🤖 Agent: Offline" | Check `/agent/query` endpoint — restart FastAPI |
| Sidebar shows "🔧 MCP Server: Offline" | Restart `scripts/start_mcp_server.py` in Tab 4 |
| DB answer not showing SQL expander | Check that `/rag/db/stream` is sending `sql_used` in the metadata event |
| `/rag/classify` returns `"chat"` for a DB question | Check that `rag_router.py` has five-way router — not an older three or four-way version |
| `/rag/classify` returns `"db"` for EMP-ID question | Five-way router not updated — `"mcp"` classification must be first in the prompt |
| `/rag/classify` returns `"db"` for compound question | Four-way router not updated — check `rag_router.py` for `"agent"` classification |
| `/rag/classify` returns wrong type for cancel query | Check cancel example phrases in `rag_router.py` — cancel/delete/withdraw must be listed |
| `/agent/query` returns 500 | Check `agents/single/hr_advisor.py` — must use `from langchain.agents import create_agent` |
| Agent reasoning trace not showing | LangGraph 1.2.0 pattern — tool calls in `msg.tool_calls`, not `intermediate_steps` |
| Agent uses wrong tool | Tool description mismatch — check `agents/single/tools.py` descriptions |
| DeepEval `ToolCorrectnessMetric` fails | Check `tools_called` is populated from `result["tools_used"]` in `build_test_case()` |
| MCP server not starting | Check `uv run python scripts/start_mcp_server.py` — must be run from project root |
| MCP server shows only 4 tools | `cancel_leave_request` not imported — check `mcp_server/tools/leave_tool.py` and `mcp_server/server.py` imports |
| MCP tools return 0 / no data | MCP server started but tool imports failed — check Tab 4 terminal for import errors |
| `curl` against port 8002 fails | Expected — FastMCP 3.x requires session handshake. Use `fastmcp.Client` in Python |
| MCP `check_leave_balance` returns "No employee found" | Verify EMP-ID format: must be `EMP-0001` not `EMP-1` or `emp-0001` |
| `submit_leave_request` fails with "Employee not found" | Employee ID doesn't exist — verify with `SELECT employee_id FROM employees LIMIT 5` |
| `submit_leave_request` fails with date error | Dates must be `YYYY-MM-DD` and end_date >= start_date |
| `submit_leave_request` returns "A pending request already exists" | Duplicate guard triggered — cancel the existing record first or use a different start date |
| `cancel_leave_request` returns "No pending leave request found" | No pending record exists for that employee/date — run submit_leave_request first |
| `cancel_leave_request` deletes only 1 of multiple duplicates | Should use the IN clause version — check that `engine.begin()` is used for both SELECT and DELETE |
| DeepEval MCP cancel tests fail | Ensure write tests ran first in the same session to create the pending records |
| DeepEval MCP tests fail with "MCP server offline" | Restart `scripts/start_mcp_server.py` in Tab 4 before running MCP tests |
| DeepEval MCP 429 rate limit | Each MCP test has 3s sleep built in — if still hitting limits wait 60s between test functions |
| DeepEval 429 rate limit error | Wait 60 seconds, re-run the specific test function |
| DeepEval timeout error | Verify env vars: `echo $DEEPEVAL_PER_TASK_TIMEOUT_SECONDS_OVERRIDE` |
| `/rag/classify` returns 500 | Restart FastAPI — likely import error on startup |
| Chat not streaming | Check trailing slash: must call `/chat/` not `/chat` |
| Parental leave returns wrong answer | Re-run indexer: `uv run python -m vector_store.indexer` |
| PostgreSQL connection error | Run `docker compose ps` — verify `hr_postgres` is healthy. Use `hr_user` not `postgres` as DB user |

---

*Document version: June 2026 | ARIA v0.5.0 | Phases 0–5 complete*
*Built by: Ryan Rodrigues | Nu Skin Enterprises — Data Platform Architecture*
