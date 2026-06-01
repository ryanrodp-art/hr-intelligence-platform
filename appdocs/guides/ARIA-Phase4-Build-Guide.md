# ARIA — HR GenAI Agent Platform
## Phase 4 Build Guide — Vector Search + Single Agent

> Semantic search interface, three LangChain tools, ReAct agent, four-way router, and DeepEval agent evaluation.
> **Completed in 2 days | 7 Steps | 4 test functions | 100% pass rate**

---

## Phase 4 Overview

Phase 4 introduces the first reasoning agent. Where Phases 1–3 retrieved information deterministically — a fixed RAG chain for documents, a fixed NL-to-SQL chain for the database — Phase 4 gives ARIA a reasoning layer that decides which tool to use based on the nature of the question. For compound questions that span both sources, the agent calls multiple tools in sequence and synthesises a combined answer.

**The transformation:**

```
Phase 3 — Separate chains, rule-based routing:
User: "What is the parental leave policy and how many days does James Chen have?"
ARIA: Routes to "rag" → answers only the policy part.
      The employee data question is lost — the router picked one path.

Phase 4 — Agent with multiple tools:
User: "What is the parental leave policy and how many days does James Chen have?"
ARIA: Calls search_policies → retrieves parental leave content.
      Calls lookup_employee → queries James Chen's leave balance.
      Combines both answers into one coherent response.
```

**What Phase 4 Delivers:**

- Standalone semantic search interface wrapping ChromaDB
- Three LangChain tools: `search_policies`, `lookup_employee`, `search_knowledge_base`
- ReAct agent built on LangChain 1.x / LangGraph `create_agent`
- `AgentResponse` dataclass with reasoning trace (steps + tools used)
- Four-way query router: `"agent"` | `"rag"` | `"db"` | `"chat"`
- Keyword-based frontend override for compound question detection
- FastAPI endpoint: `POST /agent/query`
- Streamlit UI with tool badge display and collapsible reasoning trace
- DeepEval evaluation: 4 test functions, 10 golden set entries, 100% pass rate

**7 Steps:**

| # | Step | File(s) Created / Updated | Delivers |
|---|---|---|---|
| 1 | Semantic Search Interface | `vector_store/searcher.py` | `SearchResult` dataclass + `search_and_format()` |
| 2 | Agent Package + Tools | `agents/__init__.py`, `agents/single/__init__.py`, `agents/single/tools.py` | 3 LangChain tools |
| 3 | HR Advisor Agent | `agents/single/hr_advisor.py` | ReAct agent + `AgentResponse` |
| 4 | Four-way Router | `backend/chains/rag_router.py` updated | `"agent"` / `"rag"` / `"db"` / `"chat"` |
| 5 | FastAPI Agent Endpoint | `backend/api/routes/agent.py` + `backend/main.py` updated | `POST /agent/query` |
| 6 | Streamlit Agent UI | `frontend/app.py` updated | Agent badge + reasoning trace expander |
| 7 | DeepEval Agent Tests | `evaluation/tests/test_single_agent.py` + golden set | 4 test functions, 100% pass |

---

## How the Single Agent Works — The Mental Model

```
Without agent (Phase 3):
User question → Router → ONE chain → ONE source → Answer

With agent (Phase 4):
User question → Router → Agent
                            │
                   Thinks: which tool(s)?
                            │
                ┌───────────┼───────────┐
                ▼           ▼           ▼
         search_policies  lookup_  search_knowledge
                         employee     _base
                │           │           │
           ChromaDB    PostgreSQL   ChromaDB
           (policies)  (employees)  (all content)
                │           │           │
                └───────────┴───────────┘
                            │
                   Combines all results
                            │
                       Final Answer
```

**The router decides:** compound questions (needing both documents AND employee data) route to `"agent"`. Single-source questions continue to route to `"rag"` or `"db"` directly — the agent is only invoked when its multi-tool capability is needed.

**What "ReAct" means:** The agent follows a Reasoning → Acting loop:
1. **Think** — what tool should I use and why?
2. **Act** — call the tool with a specific query
3. **Observe** — read the tool's result
4. **Think again** — do I have enough to answer, or do I need another tool?
5. Repeat until ready to give a **Final Answer**

In LangChain 1.x, this loop is implemented as a LangGraph `StateGraph` with two nodes: a model node (GPT-4o decides the next action) and a tools node (executes the chosen tool). The graph loops between them until GPT-4o emits a final answer.

---

## Step 1 — Semantic Search Interface

### Concept

The document RAG chain (`rag/document_rag/chain.py`) calls the retriever directly. For agent tools, we need a simpler, standalone interface that returns clean structured results rather than the RAG chain's internal types. `searcher.py` wraps the existing `vector_store.query()` call behind a `SearchResult` dataclass and three clean functions that any tool or agent can call without understanding ChromaDB internals.

**The `SearchResult` dataclass carries:**
- `text` — the chunk content
- `source` — the filename (e.g., `"leave_policy.pdf"`)
- `page_number` — for citation
- `chunk_id` — synthesised from `{source}_chunk_{chunk_index}` (raw IDs are not returned by `store.query()`)
- `score` — cosine similarity converted from ChromaDB's cosine distance: `score = 1 - distance`
- `citation` — human-readable: `"leave_policy.pdf (Page 1)"`

**The key adaption from `store.py`'s actual interface:**
The existing `vector_store.query(question, top_k)` returns `list[dict]` already pre-flattened — not the raw `chromadb.QueryResult` object. The searcher works over this dict list directly.

### Claude Code Prompt

```
Create vector_store/searcher.py — a standalone semantic search interface
that wraps the existing ChromaDB vector store for use by the Phase 4
LangChain agent tools.

The existing vector store is in vector_store/store.py and exposes a
singleton called vector_store with a collection named "hr_policies".
The VectorStore class has a method:
  query(question: str, top_k: int) → list[dict]
  where each dict has: text, source, page_number, chunk_index, distance

Create the following in searcher.py:

Imports:
- from vector_store.store import vector_store
- from dataclasses import dataclass
- from typing import Optional
- import logging

Dataclass SearchResult:
- text: str          — the chunk content
- source: str        — filename e.g. "leave_policy.pdf"
- page_number: int   — page number from metadata
- chunk_id: str      — unique chunk identifier
- score: float       — cosine similarity score (0.0–1.0)
- citation: str      — formatted as "leave_policy.pdf (Page 1)"

Function semantic_search(query, n_results=3, min_score=0.0):
- Call vector_store.query(question=query, top_k=n_results)
- Convert cosine distance to similarity: score = 1 - distance
- Filter results below min_score
- Build SearchResult for each item — chunk_id from source + chunk_index
- Sort by score descending
- Log query and result count
- Return empty list on exception (log the error)

Function format_search_results(results):
- If no results: return "No relevant information found."
- Format each: "[Source: {citation}]\n{text}"
- Join with "\n\n---\n\n"

Function search_and_format(query, n_results=3):
- Convenience wrapper: calls both and returns formatted string

Test block with 4 sample queries
```

### Run Command

```bash
uv run python -m vector_store.searcher
```

### Results

```
Query: What is the parental leave policy?
Results: 3
  [0.842] leave_policy.pdf (Page 1)
  Primary caregivers are entitled to 16 weeks of fully paid parental leave...
  [0.791] leave_policy.pdf (Page 2)
  ...
  [0.624] employee_handbook.pdf (Page 3)
  ...

Query: How many days of annual leave do employees get?
Results: 3
  [0.889] leave_policy.pdf (Page 1)
  Full-time employees receive 25 days of annual leave per calendar year...
  ...
```

### Exit Criteria

| Check | Status |
|---|---|
| `vector_store/searcher.py` created | ✅ |
| `SearchResult` dataclass with all 6 fields | ✅ |
| `score = 1 - distance` conversion correct | ✅ |
| `chunk_id` synthesised from `source + chunk_index` | ✅ |
| `search_and_format()` returns LLM-ready string | ✅ |
| Returns empty list on exception, not crash | ✅ |

> **Interface adaption noted:** `store.query()` signature is `query(question: str, top_k: int)` — not
> `query(query_texts=[], n_results=)` as ChromaDB's raw client uses. The searcher calls
> `vector_store.query(question=query, top_k=n_results)` to match the actual method signature.

---

## Step 2 — Agent Package Files and Tools

### Concept

Three LangChain `@tool` decorated functions give the agent its vocabulary of actions. Each tool has a docstring that GPT-4o reads when deciding which to call — the docstring is the tool's interface specification, not a comment for humans. Imprecise descriptions cause the agent to pick the wrong tool; precise ones produce correct routing.

**Three tools and their sources:**

| Tool | Calls | Data Source |
|---|---|---|
| `search_policies` | `search_and_format(query, n_results=3)` | ChromaDB — HR policy PDFs |
| `lookup_employee` | `asyncio.run(db_rag_query(query))` | PostgreSQL — employee records |
| `search_knowledge_base` | `search_and_format(query, n_results=5)` | ChromaDB — all indexed content |

**The `lookup_employee` async bridge:**
`db_rag_query()` is an async function but LangChain tools are synchronous. `asyncio.run()` bridges this — it creates a temporary event loop, runs the coroutine, and returns the result. This works in FastAPI's thread pool (sync endpoints run in threads, not the main event loop). If the agent is later called from a fully async context, this would need to change to `await db_rag_query()` with an `async def` tool.

**Tool description design — what was learned:**
The `lookup_employee` description was updated through iteration. Initially it said "when the question mentions a person by name" — this caused the agent to send department headcount questions like "How many employees are in Engineering?" to `search_knowledge_base` instead of `lookup_employee`. The fix added explicit coverage: "OR for questions about employee counts and statistics by department, status, or other database fields."

A second refinement came from the system prompt — compound questions were passing vague queries like "How many days does Isabella have?" to `lookup_employee`. The NL-to-SQL engine returned leave records (showing she's on leave) rather than her leave balance. Fixed by adding a system prompt rule: "When the question is about how many leave days or remaining leave an employee has, pass the query as 'What is [full name]'s leave balance?'"

### Claude Code Prompt

```
Create three files:
  agents/__init__.py          (empty package file)
  agents/single/__init__.py   (empty package file)
  agents/single/tools.py      (the tools module)

In agents/single/tools.py create three LangChain tools.

Imports:
- from langchain.tools import tool
- from vector_store.searcher import search_and_format
- from rag.database_rag.chain import db_rag_query
- from config.settings import settings
- import asyncio, logging

TOOL 1: search_policies
Description: Use for questions about specific HR policies, rules,
entitlements, or procedures at Acme Corp. Examples: leave entitlements,
parental leave, sick leave, code of conduct, anti-harassment policy,
benefits, health insurance, 401k, working hours, remote work policy,
probation, termination notice.
Do NOT use if the question mentions a specific employee by name.
Implementation: call search_and_format(query, n_results=3)

TOOL 2: lookup_employee
Description: Use for questions about a specific named employee OR for
questions about employee counts and statistics by department, status, or
other database fields. Use when the question mentions a person by name,
OR when it asks about headcount, department size, or aggregate employee data.
Implementation:
- asyncio.run(db_rag_query(query))
- If result.answer == "NOT_DB_QUERY": return fallback message
- If not result.success: return f"Database query failed: {result.error}"
- Return result.answer

TOOL 3: search_knowledge_base
Description: Use for broad HR questions that don't mention a specific
employee by name and aren't about a specific policy clause. Use for
general onboarding, cross-cutting topics, company culture, or when
unsure which specific policy applies. Searches all HR content.
Implementation: call search_and_format(query, n_results=5)

After the three tools:
HR_ADVISOR_TOOLS = [search_policies, lookup_employee, search_knowledge_base]

Test block invoking each tool.
```

### Run Command

```bash
uv run python -m agents.single.tools
```

### Results

```
=== Tool: search_policies ===
[Source: leave_policy.pdf (Page 1)]
Primary caregivers are entitled to 16 weeks of fully paid parental leave...

=== Tool: lookup_employee ===
James Chen has 30 days of leave remaining.

=== Tool: search_knowledge_base ===
[Source: employee_handbook.pdf (Page 1)]
During your first week, you will receive your IT equipment...

Tools registered: ['search_policies', 'lookup_employee', 'search_knowledge_base']
```

### Exit Criteria

| Check | Status |
|---|---|
| `agents/__init__.py` created (empty) | ✅ |
| `agents/single/__init__.py` created (empty) | ✅ |
| `agents/single/tools.py` created | ✅ |
| `search_policies` calls `search_and_format(query, n_results=3)` | ✅ |
| `lookup_employee` handles `NOT_DB_QUERY` and `success=False` gracefully | ✅ |
| `search_knowledge_base` calls `search_and_format(query, n_results=5)` | ✅ |
| `HR_ADVISOR_TOOLS` list registered with all 3 tools | ✅ |

---

## Step 3 — HR Advisor Agent

### Concept

The HR Advisor is a ReAct agent built on LangChain 1.x. In LangChain 1.x, the agent stack changed significantly from 0.3.x — `AgentExecutor` and the classic `create_react_agent` from `langchain.agents` are removed. The modern replacement is `create_agent` from `langchain.agents` (LangGraph-backed), which returns a compiled `StateGraph` directly.

**LangChain 1.x compatibility changes required:**

| What the original spec assumed | What LangChain 1.3.1 actually requires |
|---|---|
| `from langchain.agents import AgentExecutor, create_react_agent` | `AgentExecutor` removed — use `create_agent` from `langchain.agents` |
| `PromptTemplate` with `{tools}`, `{tool_names}`, `{input}`, `{agent_scratchpad}` | LangGraph handles ReAct formatting internally — plain `system_prompt=` string |
| `executor.invoke({"input": question})` → `result["output"]` | `agent.invoke({"messages": [...]})` → `result["messages"][-1].content` |
| Intermediate steps from `result["intermediate_steps"]` as `(AgentAction, str)` tuples | Extracted from `AIMessage.tool_calls` + matching `ToolMessage` by `tool_call_id` |

**The `AgentResponse` dataclass:**
Instead of returning raw LangGraph output, `run_hr_advisor()` extracts the final answer, reasoning steps, and tool names into a clean `AgentResponse`. Each step has four keys: `thought` (why this tool), `tool` (tool name), `tool_input` (query sent), `observation` (result, capped at 300 chars). This structure powers the Streamlit reasoning trace expander.

**The system prompt design:**
The system prompt is a plain string — no template variables needed because LangGraph injects tool descriptions automatically through the `create_agent` API. Key rules embedded in the prompt:
- Always use a tool before answering — never answer from memory alone
- If the question mentions a specific person by name, use `lookup_employee`
- When asking about leave days, phrase the query as "What is [full name]'s leave balance?" — anchors NL-to-SQL to `employees.leave_balance` column rather than `leave_records`
- Only suggest `hr@acmecorp.com` when ALL tools returned no results — never as a footer on successful answers

The HR contact rule was refined after initial testing showed ARIA appending "For more details, contact the HR department at hr@acmecorp.com" to successful answers. The `AnswerRelevancyMetric` judge scored this as irrelevant padding, dropping scores below the 0.70 threshold.

### Claude Code Prompt

```
Create agents/single/hr_advisor.py — the Phase 4 Single HR Advisor
ReAct agent using LangChain 1.x.

Imports:
- from langchain.agents import create_agent
- from langchain_openai import ChatOpenAI
- from langchain_core.messages import AIMessage, ToolMessage
- from agents.single.tools import HR_ADVISOR_TOOLS
- from config.settings import settings
- from dataclasses import dataclass
- import logging

HR_ADVISOR_SYSTEM_PROMPT — a plain string (no template variables):
  "You are ARIA, an HR Intelligence Assistant for Acme Corp.
   You help employees and HR managers with questions about HR
   policies, employee records, leave balances, and org structure.

   RULES:
   - Always use a tool before answering — never answer from memory alone
   - If the question mentions a specific person by name, always use
     lookup_employee. When the question is about leave days or remaining
     leave, pass the query as 'What is [full name]'s leave balance?'
     so the correct leave_balance column is queried.
   - If the question is about a policy rule or entitlement, use search_policies
   - If the question is broad or cross-cutting, use search_knowledge_base
   - For compound questions (policy + employee data), call multiple tools
   - Always cite your source in the final answer
   - Only mention hr@acmecorp.com when ALL tools returned no results —
     never add it as a footer when the question was answered successfully
   - Do not end successful answers with 'for more details contact HR'"

@dataclass AgentResponse:
  answer: str
  steps: list[dict]   — each: thought, tool, tool_input, observation
  tools_used: list[str]
  success: bool

Function get_llm():
- ChatOpenAI, temperature=0, model + api_key from settings

Function build_hr_advisor():
- create_agent(model=get_llm(), tools=HR_ADVISOR_TOOLS,
               system_prompt=HR_ADVISOR_SYSTEM_PROMPT)
- Returns CompiledStateGraph

Function run_hr_advisor(question: str) -> AgentResponse:
- Build agent, invoke with {"messages": [("human", question)]}
- Extract answer from result["messages"][-1].content
- Extract steps from AIMessage.tool_calls + matching ToolMessages by tool_call_id
- Return AgentResponse(answer, steps, tools_used, success=True)
- Wrap in try/except — return AgentResponse(success=False) on error

Test block with 4 test questions.
```

### Run Command

```bash
uv run python -m agents.single.hr_advisor
```

### Results

```
============================================================
Q: What is the parental leave policy?

Answer: The parental leave policy at Acme Corp is as follows:
- Primary caregivers receive 16 weeks of fully paid parental leave.
  Employees must have completed 6 months of continuous service...
[Source: leave_policy.pdf (Page 1)]
Tools used: ['search_policies']
Steps: 1

============================================================
Q: How many leave days does James Chen have?

Answer: James Chen has 30 days of leave remaining.
Tools used: ['lookup_employee']
Steps: 1

============================================================
Q: What is the remote work policy and how many days does Isabella Fernandez have?

Answer: The remote work policy at Acme Corp allows employees to work
remotely up to 2 days per week (hybrid model: minimum 3 days in office).
[Source: employee_handbook.pdf (Page 3)]

Regarding Isabella Fernandez, she has 8 days of leave remaining.
Tools used: ['search_policies', 'lookup_employee']
Steps: 2
```

### Exit Criteria

| Check | Status |
|---|---|
| `hr_advisor.py` created | ✅ |
| `create_agent` from `langchain.agents` used (LangChain 1.x compatible) | ✅ |
| `system_prompt=` parameter used (not `prompt=`) | ✅ |
| `AgentResponse` dataclass with all 4 fields | ✅ |
| Steps extracted correctly from `AIMessage.tool_calls` + `ToolMessage` pairs | ✅ |
| Compound question triggers 2 tool calls | ✅ |
| HR contact footer NOT added on successful answers | ✅ |

> **LangChain 1.x migration:** The `create_react_agent` from `langgraph.prebuilt` was initially used
> but showed a deprecation warning pointing to `create_agent` from `langchain.agents`. The switch
> required changing the import and renaming `prompt=` to `system_prompt=`. The underlying behaviour
> is identical — both build the same LangGraph StateGraph with model + tools nodes.

---

## Step 4 — Four-way Query Router

### Concept

Phase 3 had a three-way router: `"rag"` (document questions), `"db"` (employee data questions), `"chat"` (general conversation). Phase 4 adds a fourth classification: `"agent"` for compound questions that require BOTH a policy lookup AND an employee data lookup in the same response.

**The critical ordering constraint:**
`"agent"` must be evaluated before `"db"` in the prompt. The original three-way router had an `IMPORTANT` rule: "If the question mentions a SPECIFIC PERSON by name, always return 'db'." A compound question like "What is the parental leave policy and how many days does James Chen have?" mentions James Chen by name — the old rule would route it to `"db"` before it could be considered for `"agent"`. The new rule flips the priority: check for `"agent"` first.

**Classification guide:**

| Returns | When |
|---|---|
| `"agent"` | Question requires BOTH policy/document retrieval AND specific employee data — cannot be fully answered from one source |
| `"db"` | Question is about employee data only — no policy component |
| `"rag"` | Question is about policies or procedures only — no employee-specific data |
| `"chat"` | General conversation, concepts not specific to Acme Corp |

**Frontend keyword override:**
Because LLM-based classification can be non-deterministic for edge cases, a deterministic keyword check in `frontend/app.py` acts as a safety net. If any of `["and how many", "and what is", "and who is", "tell me about"]` appear in the question (lowercased), the classification is overridden to `"agent"` regardless of what the LLM-based classifier returned. This runs after the classify API call and before routing.

### Claude Code Prompt

```
Update backend/chains/rag_router.py to add "agent" as a fourth
classification for compound questions needing BOTH document and
employee data retrieval.

Add "agent" to ROUTER_PROMPT before the existing "db" section:

Return 'agent' if the question REQUIRES BOTH:
- A policy or document lookup (general rules, entitlements, procedures)
- AND a specific employee data lookup (named person, leave balance,
  org structure)
The question cannot be fully answered without retrieving from BOTH sources.
Examples:
  "What is the leave policy and how many days does James have?"
  "What is the remote work policy and what is Sarah's department?"
  "Tell me about parental leave and how much does Isabella have?"

Update the IMPORTANT rule to: "Classify as 'agent' before 'db' — if
the question needs BOTH a policy document AND a named employee lookup,
always return 'agent'."

Update the fallback guard from ("rag", "db", "chat") to
("agent", "rag", "db", "chat").
```

### Run Command

```bash
# Run router directly
uv run python -m backend.chains.rag_router

# Or test via API
curl "http://localhost:8000/rag/classify?query=What+is+the+parental+leave+policy+and+how+many+days+does+James+Chen+have"
# Expected: {"classification": "agent"}
```

### Classification Test Results

| Question | Expected | Result |
|---|---|---|
| "What is the parental leave policy and how many days does James Chen have?" | `agent` | `agent` ✅ |
| "What is the remote work policy and what is Sarah's department?" | `agent` | `agent` ✅ |
| "Tell me about parental leave and how much does Isabella have?" | `agent` | `agent` ✅ |
| "What is the parental leave policy?" | `rag` | `rag` ✅ |
| "How many leave days does James Chen have?" | `db` | `db` ✅ |
| "Hello, how are you?" | `chat` | `chat` ✅ |

### Exit Criteria

| Check | Status |
|---|---|
| `"agent"` classification added to router prompt | ✅ |
| `"agent"` listed before `"db"` in evaluation order | ✅ |
| IMPORTANT rule updated to check `"agent"` before `"db"` | ✅ |
| Fallback guard updated to include `"agent"` | ✅ |
| Compound questions correctly classified as `"agent"` | ✅ |
| Existing `"rag"` / `"db"` / `"chat"` routing unchanged | ✅ |

---

## Step 5 — FastAPI Agent Endpoint

### Concept

A new FastAPI route file exposes the HR Advisor agent. The route is simple — one endpoint, no streaming (agent reasoning is sequential, not token-by-token). Two design decisions:

**Return 200, not 500, on agent failure:**
The initial implementation raised `HTTPException(500)` when `result.success == False`. This caused `raise_for_status()` in test code to throw, crashing the entire test's list comprehension mid-iteration — no further entries ran, and no useful error message was produced. Changed to return 200 with `success=False` in the response body. Only genuine server exceptions (import errors, connection failures) return 500.

**Response shape:**
`AgentQueryResponse` exposes the full reasoning trace — `steps` is the list of tool calls with thoughts and observations. The Streamlit UI uses this to render the collapsible "Agent Reasoning" expander. DeepEval test code only reads `answer` and `tools_used`.

### Claude Code Prompt

```
Create backend/api/routes/agent.py — the Phase 4 FastAPI route
that exposes the Single HR Advisor agent.

Imports:
- from fastapi import APIRouter, HTTPException
- from pydantic import BaseModel
- from agents.single.hr_advisor import run_hr_advisor, AgentResponse
- import logging

router = APIRouter(prefix="/agent", tags=["agent"])

Request model AgentRequest(BaseModel):
- question: str

Response model AgentQueryResponse(BaseModel):
- answer: str
- tools_used: list[str]
- steps: list[dict]
- success: bool
- question: str

POST /agent/query endpoint:
- Call run_hr_advisor(request.question)
- Return AgentQueryResponse with all fields from result
- If result.success is False, return 200 with success=False in body
  (do NOT raise 500 — agent failure is not a server error)
- Only raise HTTPException(500) on unexpected exceptions
- Log: f"Agent query: {request.question[:50]}"

Also update backend/main.py:
- Add: from backend.api.routes import agent as agent_router
- Add: app.include_router(agent_router.router)
  (alongside existing chat_router and rag_router registrations)
```

### Verification Commands

```bash
# Start backend first
uv run uvicorn backend.main:app --reload --port 8000

# Test policy query
curl -X POST http://localhost:8000/agent/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the parental leave policy?"}'

# Test compound query
curl -X POST http://localhost:8000/agent/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the remote work policy and how many days does James Chen have?"}'

# Verify route registered
curl http://localhost:8000/docs
# Should show /agent/query under "agent" tag
```

### Verification Results

| Test | Result |
|---|---|
| `POST /agent/query` policy question | `{"answer": "...", "tools_used": ["search_policies"], "success": true}` ✅ |
| `POST /agent/query` compound question | `{"tools_used": ["search_policies", "lookup_employee"], "success": true}` ✅ |
| `/docs` shows agent endpoint | `/agent/query` visible under `agent` tag ✅ |
| `app.include_router(agent_router.router)` in main.py | ✅ |

### Exit Criteria

| Check | Status |
|---|---|
| `backend/api/routes/agent.py` created | ✅ |
| `AgentRequest` and `AgentQueryResponse` Pydantic models defined | ✅ |
| `POST /agent/query` returns 200 with full response | ✅ |
| `success=False` returns 200, not 500 | ✅ |
| `backend/main.py` updated with agent router import and registration | ✅ |

---

## Step 6 — Streamlit Agent UI

### Concept

Three additions to `frontend/app.py` for the agent path:

1. **`get_agent_response(question)`** — calls `POST /agent/query` via `httpx.post()` with a 60-second timeout (agents take 10–30 seconds), returns the full JSON dict.

2. **Agent routing branch** — when classification is `"agent"`, displays the answer with a "🤖 **Agent**" badge, colour-coded tool badges for each tool used, and a collapsible reasoning trace showing each step.

3. **Keyword override** — after the `GET /rag/classify` call, a deterministic check overrides the classification to `"agent"` if any compound-query keyword is detected. This catches cases where the LLM-based classifier routes a compound question to `"db"` (because it saw a person's name) instead of `"agent"`.

**Structural consideration:**
The existing rag/db/chat routing block lives inside a shared `with st.chat_message("assistant"):` context. The agent branch needs its own `with st.chat_message("assistant"):` inside the agent code block. To avoid nesting two `st.chat_message` contexts, the agent branch is placed outside (before) the `else:` block that wraps rag/db/chat — a clean `if agent / else rag-db-chat` structure.

**Sidebar agent status check:**
A `POST /agent/query` call with `{"question": "ping"}` is made to show "🤖 Agent: Online" in the sidebar. In practice this will almost always timeout (5s timeout vs. 10–30s agent runtime) and show "Offline" — it's a structural placeholder that a lightweight `GET /agent/status` health endpoint should replace in Phase 7.

### Claude Code Prompt

```
Update frontend/app.py to add Phase 4 agent support.
Do not modify any existing chat, rag, or db routing paths.

CHANGE 1 — Add agent sidebar status check after the RAG status check:
try:
    httpx.post(f"{BACKEND_URL}/agent/query",
               json={"question": "ping"}, timeout=5)
    st.sidebar.success("🤖 Agent: Online")
except:
    st.sidebar.error("🤖 Agent: Offline")

CHANGE 2 — Add get_agent_response() helper function before
the streaming helpers section:
def get_agent_response(question: str) -> dict:
    response = httpx.post(f"{BACKEND_URL}/agent/query",
                          json={"question": question}, timeout=60)
    response.raise_for_status()
    return response.json()

CHANGE 3 — Add keyword override after the classify API call:
agent_keywords = ["and how many", "and what is", "and who is",
                  "tell me about"]
if any(kw in prompt.lower() for kw in agent_keywords):
    classification = "agent"

CHANGE 4 — Restructure routing block:
if classification == "agent":
    try:
        result = get_agent_response(prompt)
    except Exception as e:
        with st.chat_message("assistant"):
            st.error(f"❌ Could not reach ARIA agent: {str(e)}")
        result = None

    if result:
        with st.chat_message("assistant"):
            st.markdown("🤖 **Agent**")
            st.markdown(result["answer"])

            # Tool badges
            if result.get("tools_used"):
                cols = st.columns(len(result["tools_used"]))
                tool_icons = {"search_policies": "📄",
                              "lookup_employee": "👤",
                              "search_knowledge_base": "🔍"}
                for i, tool in enumerate(result["tools_used"]):
                    icon = tool_icons.get(tool, "🔧")
                    cols[i].markdown(
                        f"<span style='background:#1a1a2e;padding:4px 10px;"
                        f"border-radius:12px;font-size:0.8em;color:#00C8FF'>"
                        f"{icon} {tool}</span>", unsafe_allow_html=True)

            # Reasoning trace
            if result.get("steps"):
                with st.expander(f"🧠 Agent Reasoning ({len(result['steps'])} steps)"):
                    for i, step in enumerate(result["steps"], 1):
                        st.markdown(f"**Step {i} — {step['tool']}**")
                        st.markdown(f"*Tool input:* `{step['tool_input']}`")
                        st.markdown("*Observation:*")
                        st.text(step["observation"][:400])
                        if i < len(result["steps"]):
                            st.divider()

        st.session_state.messages.append({
            "role": "assistant",
            "content": result["answer"],
        })

else:  # rag / db / chat — wrap existing routing block in else
    with st.chat_message("assistant"):
        if classification == "rag": ...
        elif classification == "db": ...
        else: ...
    if response_text:
        st.session_state.messages.append(...)
```

### UI Test Results

| Question | Classification | UI Result |
|---|---|---|
| "What is the parental leave policy and how many days does James Chen have?" | `agent` (keyword override) | 🤖 **Agent** badge, 2 tool badges, 2-step reasoning trace ✅ |
| "What is the parental leave policy?" | `rag` | 🔍 Answered from company documents, citation ✅ |
| "How many leave days does James Chen have?" | `db` | 🗄️ Employee database, SQL expander ✅ |

### Exit Criteria

| Check | Status |
|---|---|
| `get_agent_response()` function added | ✅ |
| Agent sidebar status check added | ✅ |
| Keyword override runs after classify API call | ✅ |
| Agent routing branch is outside outer `with st.chat_message` | ✅ |
| Tool badges rendered with correct icons | ✅ |
| Reasoning trace expander shows all steps | ✅ |
| Existing rag / db / chat routing unchanged | ✅ |

---

## Step 7 — DeepEval Agent Tests

### Concept

Phase 4 evaluation differs from Phases 2 and 3. There is no `retrieval_context` field — the agent's knowledge sources are its tools, not pre-retrieved chunks passed as context. The evaluation focuses on three dimensions:

1. **Did the agent complete the task?** (`TaskCompletionMetric`) — used for policy and compound queries where there is a clear goal
2. **Did the agent call the right tools?** (`ToolCorrectnessMetric`) — no LLM judge, score-based comparison of `tools_called` vs `expected_tools`
3. **Did the answer directly address the question?** (`AnswerRelevancyMetric`) — replaces `GoalAccuracyMetric` which is not compatible with `LLMTestCase` in DeepEval 4.x

**DeepEval 4.x compatibility fix:**
`GoalAccuracyMetric` was originally specified for this phase but is not a `BaseMetric` subclass in DeepEval 4.0.2 — `evaluate()` with `LLMTestCase` rejects it with `ValueError`. Replaced with `AnswerRelevancyMetric` which measures the same property (does the answer address the question) and is confirmed compatible.

**`TaskCompletionMetric` exclusion from employee tests:**
The `TaskCompletionMetric` judge consistently scored "Who is currently on leave?" at 0.50, reasoning that the answer was incomplete because it only named one person. The seed data has exactly one employee on leave — the answer is complete. But the judge can't know this from the question text alone. `TaskCompletionMetric` is excluded from `test_agent_employee_queries` and only used where completeness judgement is reliable — policy queries (clear rubric) and compound queries (both parts must be answered).

**`ToolCorrectnessMetric` — no model required:**
This metric is not LLM-judged. It compares `tools_called` against `expected_tools` by name and returns a score based on the overlap ratio. Threshold `0.8` means at least 80% of expected tools must have been called.

**build_test_case() success check:**
If the agent returns `success=False` (because it couldn't complete the task), `build_test_case()` calls `pytest.fail()` with the specific query and error message. This prevents a failed agent response from being evaluated against quality metrics with a meaningless output.

### Claude Code Prompt

```
Create two files:

FILE 1: evaluation/datasets/agent_golden_set.json
10 entries with structure:
  {"input": str, "expected_output": str, "query_type": str,
   "expected_tools": list[str]}

Policy queries (3): parental leave (search_policies),
  remote work policy (search_policies), probation period (search_policies)

Employee queries (4): James Chen leave days (lookup_employee),
  Isabella's department (lookup_employee), who is on leave (lookup_employee),
  Engineering headcount (lookup_employee)

Compound queries (3): parental leave + James Chen days,
  sick leave + who is on leave, remote work + Isabella's days
  — all with ["search_policies", "lookup_employee"]

FILE 2: evaluation/tests/test_single_agent.py

Imports: sys, os, pytest, json, time, httpx, pathlib
  from deepeval import evaluate
  from deepeval.metrics import (TaskCompletionMetric,
    ToolCorrectnessMetric, AnswerRelevancyMetric)
  from deepeval.test_case import LLMTestCase, ToolCall

BACKEND_URL = "http://localhost:8000"

Helper get_agent_response(question) → POST /agent/query, timeout=60, sleep(0.5)

Helper build_test_case(item):
  - call get_agent_response
  - if not result.get("success"): pytest.fail() with query + error
  - build LLMTestCase with tools_called and expected_tools as ToolCall lists

Fixture agent_golden_set: load JSON
Fixture agent_metrics: dict with task_completion, tool_correctness,
  answer_relevancy

Test 1: test_agent_policy_queries — policy items[:3]
  Metrics: task_completion + tool_correctness + answer_relevancy

Test 2: test_agent_employee_queries — employee items[:3]
  Metrics: tool_correctness + answer_relevancy only
  (TaskCompletionMetric excluded — false fails on open "who" questions)

Test 3: test_agent_compound_queries — all compound items
  Metrics: all three — this is the Phase 4 exit criteria test

Test 4: test_agent_tool_correctness_boundary — all 10 entries
  Metric: tool_correctness only (no LLM judge)
```

### DeepEval Run Command

```bash
# Requires backend running in Tab 1
uv run deepeval test run evaluation/tests/test_single_agent.py -v

# Or run individual tests
uv run deepeval test run evaluation/tests/test_single_agent.py::test_agent_compound_queries -v
uv run deepeval test run evaluation/tests/test_single_agent.py::test_agent_tool_correctness_boundary -v
```

### DeepEval Results — Final Baseline

#### test_agent_policy_queries

| Case | Task Completion | Tool Correctness | Answer Relevancy |
|---|---|---|---|
| Parental leave entitlement | 0.95 ✅ | 1.00 ✅ | 1.00 ✅ |
| Remote work policy | 0.95 ✅ | 1.00 ✅ | 1.00 ✅ |
| 90-day probation period | 0.95 ✅ | 1.00 ✅ | 0.86 ✅ |

**Aggregate: Task Completion 0.95 · Tool Correctness 1.00 · Answer Relevancy 0.95 · Pass Rate 100%**

#### test_agent_employee_queries

| Case | Tool Correctness | Answer Relevancy |
|---|---|---|
| James Chen leave days | 1.00 ✅ | 1.00 ✅ |
| Isabella Fernandez department | 1.00 ✅ | 1.00 ✅ |
| Who is currently on leave | 1.00 ✅ | 1.00 ✅ |

**Aggregate: Tool Correctness 1.00 · Answer Relevancy 1.00 · Pass Rate 100%**

> `TaskCompletionMetric` excluded — see concept section above.

#### test_agent_compound_queries — Phase 4 Exit Criteria

| Case | Task Completion | Tool Correctness | Answer Relevancy |
|---|---|---|---|
| Parental leave policy + James Chen days | 0.95 ✅ | 1.00 ✅ | 0.86 ✅ |
| Sick leave + who is on leave | 0.95 ✅ | 1.00 ✅ | 1.00 ✅ |
| Remote work + Isabella Fernandez days | 0.95 ✅ | 1.00 ✅ | 0.86 ✅ |

**Aggregate: Task Completion 0.95 · Tool Correctness 1.00 · Answer Relevancy 0.90 · Pass Rate 100%**

#### test_agent_tool_correctness_boundary

All 10 golden set entries. No LLM judge.

| Metric | Average | Pass Rate | Entries |
|---|---|---|---|
| Tool Correctness | 1.00 | 100% | 10 |

---

## Phase 4 DeepEval Complete Baseline

| Test | Metrics | Pass Rate | Cases | Time |
|---|---|---|---|---|
| `test_agent_policy_queries` | Task Completion + Tool Correctness + Answer Relevancy | **100%** | 3 | ~15s |
| `test_agent_employee_queries` | Tool Correctness + Answer Relevancy | **100%** | 3 | ~20s |
| `test_agent_compound_queries` | All three — exit criteria | **100%** | 3 | ~40s |
| `test_agent_tool_correctness_boundary` | Tool Correctness only (no judge) | **100%** | 10 | ~40s |

**Total: 4 passed, 4 warnings in 115.34s (1:55)**

---

## Phase 4 Complete ✅

| Step | What Was Built | Status |
|---|---|---|
| Step 1 | `vector_store/searcher.py` — `SearchResult` dataclass, `semantic_search()`, `search_and_format()` | ✅ |
| Step 2 | `agents/single/tools.py` — 3 LangChain tools with precise descriptions | ✅ |
| Step 3 | `agents/single/hr_advisor.py` — LangChain 1.x `create_agent`, `AgentResponse`, reasoning trace extraction | ✅ |
| Step 4 | Four-way router — `"agent"` classification added, ordering priority fixed | ✅ |
| Step 5 | `backend/api/routes/agent.py` — `POST /agent/query`, 200 on agent failure | ✅ |
| Step 6 | `frontend/app.py` — agent routing path, tool badges, reasoning trace expander, keyword override | ✅ |
| Step 7 | DeepEval — 4 test functions, 10 golden set entries, 100% pass rate | ✅ |

---

## Phase 4 vs Phase 3 Capability Comparison

| Capability | Phase 3 | Phase 4 |
|---|---|---|
| Policy questions | ✅ Document RAG | ✅ Document RAG (unchanged) |
| Employee-specific questions | ✅ Database RAG | ✅ Database RAG (unchanged) |
| Compound questions | ❌ Router picks one path | ✅ Agent calls both tools, combines answer |
| Multi-tool reasoning | ❌ No | ✅ Yes — ReAct loop |
| Reasoning transparency | SQL expander | Reasoning trace with step-by-step tool calls |
| Query routing | `"rag"` / `"db"` / `"chat"` | `"agent"` / `"rag"` / `"db"` / `"chat"` |
| DeepEval metrics | Faithfulness + AnswerRelevancy + Routing | + ToolCorrectness + TaskCompletion |

---

## Lessons Learned

### LangChain 1.x Breaks the Spec

The original Phase 4 specification was written assuming LangChain 0.3.x. LangChain 1.3.1 (installed via `pyproject.toml`) made three breaking changes:

1. `AgentExecutor` no longer exported from `langchain.agents` — use `create_agent` which builds the same LangGraph graph under the hood
2. `create_react_agent` from `langgraph.prebuilt` marked deprecated — use `create_agent` from `langchain.agents` with `system_prompt=` parameter
3. `PromptTemplate` with ReAct variables (`{tools}`, `{tool_names}`, `{agent_scratchpad}`) not needed — LangGraph handles formatting internally

Lesson: always verify installed package versions before writing prompts that specify exact API calls.

### Tool Descriptions Are the Agent's Routing Logic

The agent's routing accuracy is entirely determined by its tool descriptions. Two descriptions needed iteration:

`lookup_employee` — initially described as "for questions about a specific named employee." Caused department headcount questions ("How many employees in Engineering?") to go to `search_knowledge_base` instead. Fixed by adding: "OR for questions about employee counts and statistics by department, status, or other database fields."

The system prompt also contributed — a compound question passed vague leave-day queries to `lookup_employee`, which the NL-to-SQL engine interpreted as leave history rather than leave balance. Fixed with an explicit instruction: "pass the query as 'What is [full name]'s leave balance?'"

### DeepEval Metric Compatibility Must Be Verified at Runtime

`GoalAccuracyMetric` was specified for Phase 4 agent evaluation but is not a `BaseMetric` subclass in DeepEval 4.0.2. The error only appears at runtime — `evaluate()` raises `ValueError: Metric Goal Accuracy is not a valid metric for LLMTestCase.` Replaced with `AnswerRelevancyMetric` which measures the same property.

Always verify metric compatibility by running a single test case before building the full golden set.

### `TaskCompletionMetric` Is Wrong for Open-ended Listing Questions

"Who is currently on leave?" scored 0.50 — the judge inferred the task requires an exhaustive list. The seed data has one employee on leave. The correct answer is "Isabella Fernandez is currently on leave" — but the judge doesn't know the population size. `TaskCompletionMetric` is only appropriate for questions with a defined, verifiable completion state. For open "who/what" factual queries, `AnswerRelevancyMetric` is the right measure.

---

## Known Gaps — Phase 5 and Phase 7 Items

| Issue | Severity | Fix |
|---|---|---|
| `asyncio.run()` in `lookup_employee` would fail in fully-async contexts | Low — Phase 4 uses sync FastAPI endpoint | If agent moves to async route, change tool to `async def` + `await db_rag_query()` |
| Agent sidebar status check always shows "Offline" (5s timeout < agent runtime) | Low — cosmetic | Add `GET /agent/status` lightweight health endpoint in Phase 7 |
| `build_hr_advisor()` called fresh per request — agent re-initialises each time | Low — stateless is safe; minor latency | Lift to module-level singleton if latency becomes a concern |
| Keyword override in frontend is a string-matching heuristic | Medium — can produce false positives | Replace with LLM-based compound detection or improve router prompt in Phase 7 |
| `test_agent_employee_queries` omits `TaskCompletionMetric` | Low — documented decision | If seed data is expanded (multiple employees on leave), `TaskCompletionMetric` can be reintroduced |

---

## What Comes Next — Phase 5

Phase 5 adds **real database actions** via a FastMCP server — not just retrieval but writes. The agent will be able to check leave balances AND submit leave requests that actually insert rows into PostgreSQL.

**Phase 5 components:**
- FastMCP server at `localhost:8002` — three tools: `check_leave_balance`, `submit_leave_request`, `get_org_chart`
- `submit_leave_request` writes a new `LeaveRecord` row — the first write operation in the platform
- MCP client integration into the agent tool layer
- DeepEval `MCPTaskCompletionMetric`, `MCPUseMetric`, `MultiTurnMCPUseMetric`

**The Phase 4 baseline must be maintained:** All four agent evaluation tests must continue to pass through Phase 5 and beyond. The three-tool agent established in Phase 4 is the foundation that MCP tools extend.

> **Golden Rule:** The agent always uses a tool before answering — it never answers from GPT-4o's training knowledge alone. Every fact in every answer is grounded in a tool result. This is the discipline that carries forward to all future phases.
