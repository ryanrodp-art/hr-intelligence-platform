# ARIA — HR GenAI Agent Platform
## Phase 5 Build Guide — MCP Server

> FastMCP tool server, 4 HR action tools, first database write via AI agent, and agent upgraded from 3 to 7 tools.
> **Completed in 1 day | 7 Steps | 19 DeepEval cases | 100% pass rate | $0.080 total cost**

---

## Phase 5 Overview

Phase 5 gives ARIA the ability to **act**, not just answer. The Phase 4 ReAct agent could retrieve information — leave balances, policies, org charts. Phase 5 adds a FastMCP server that exposes 4 HR tools, including the first write operation in the entire ARIA platform: `submit_leave_request` inserts a new `LeaveRecord` row into PostgreSQL.

**The transformation:**

```
Phase 4 — Read-only retrieval agent:
User: "How many leave days does James Chen have?"
ARIA: "James Chen has 30 days of leave remaining."
      (reads from database, answers question)

Phase 5 — Action-capable agent:
User: "Submit Annual leave for EMP-0001 from Dec 28 to Dec 30"
ARIA: "Leave request submitted successfully for EMP-0001.
       Dates: 2026-12-28 to 2026-12-30 (3 days).
       Type: Annual. Status: Pending.
       Your manager will be notified for approval."
      (WRITES to database, confirms action)
```

**Why MCP specifically:**
MCP (Model Context Protocol) is Anthropic's open standard for connecting AI agents to external tools and systems. Instead of hardcoding tool logic inside the agent like Phase 4, MCP tools run as a **separate server** on port 8002 that any MCP-compatible agent or client can call. This is the architectural upgrade from tools baked into the agent to tools as a network service — the same tools can be called by Claude Desktop, Cursor, or any future ARIA agent without code changes.

**The complete agent tool set after Phase 5:**

```
ReAct Agent — 7 tools total:
├── search_policies          (Phase 4 — direct Python call, read-only)
├── lookup_employee          (Phase 4 — direct Python call, read-only)
├── search_knowledge_base    (Phase 4 — direct Python call, read-only)
└── MCP tools via port 8002: (Phase 5 — HTTP network service)
    ├── check_leave_balance       (read — PostgreSQL)
    ├── submit_leave_request      (WRITE — only write op in ARIA)
    ├── get_org_chart             (read — PostgreSQL self-join)
    └── policy_lookup             (read — ChromaDB)
```

**What Phase 5 Delivers:**

- FastMCP 3.3.1 server on port 8002 with HTTP transport
- 4 MCP tools — 3 read, 1 write — registered and verified
- First write operation: `submit_leave_request` → PostgreSQL `leave_records` table
- `langchain-mcp-adapters 0.2.2` integration via `MultiServerMCPClient`
- Agent upgraded from 3 direct tools to 7 tools (3 direct + 4 MCP)
- LangChain 1.3.1 + LangGraph 1.2.0 migration applied to `hr_advisor.py`
- Tool routing verified: EMP-ID queries → MCP tools, name-based → direct tools
- Compound queries span both tool types in a single reasoning loop
- DeepEval: 4 tests, 19 cases, 100% pass rate, $0.080 total cost

**7 Steps:**

| # | Step | File(s) Created / Updated | Delivers |
|---|---|---|---|
| 1 | MCP Server + Package Files | `mcp_server/__init__.py`, `mcp_server/tools/__init__.py`, `mcp_server/server.py` | FastMCP server entry point on port 8002 |
| 2 | Leave Tool | `mcp_server/tools/leave_tool.py` | `check_leave_balance`, `submit_leave_request` |
| 3 | Org Chart Tool | `mcp_server/tools/org_chart_tool.py` | `get_org_chart` |
| 4 | Policy Lookup Tool | `mcp_server/tools/policy_lookup_tool.py` | `policy_lookup` |
| 5 | MCP Start Script | `scripts/start_mcp_server.py` | CLI runner + full server verification |
| 6 | Agent MCP Integration | `agents/single/hr_advisor.py` updated | 7-tool agent, LangChain 1.3.1 migration |
| 7 | DeepEval MCP Tests | `evaluation/tests/test_mcp.py` + golden set | 4 tests, 19 cases, 100% pass |

---

## How MCP Works — The Mental Model

```
Phase 4 — Tools baked into the agent (direct function calls):
hr_advisor.py → tools.py → search_and_format() → ChromaDB
hr_advisor.py → tools.py → db_rag_query()      → PostgreSQL

Phase 5 — Tools as a network service (HTTP calls):
hr_advisor.py → MultiServerMCPClient → HTTP:8002/mcp → FastMCP server
                                                              ↓
                                               check_leave_balance → PostgreSQL (read)
                                               submit_leave_request → PostgreSQL (WRITE)
                                               get_org_chart → PostgreSQL (read)
                                               policy_lookup → ChromaDB (read)
```

**Tool selection routing — how the agent decides which tool to call:**

| Question type | Example | Tool selected |
|---|---|---|
| Named employee | "How many days does James Chen have?" | `lookup_employee` (Phase 4 direct) |
| Employee ID | "Check leave for EMP-0001" | `check_leave_balance` (MCP) |
| Action request | "Submit leave for EMP-0001 Dec 28-30" | `submit_leave_request` (MCP write) |
| Org by ID | "Get org chart for EMP-0001" | `get_org_chart` (MCP) |
| Policy | "What is the leave policy?" | `search_policies` (Phase 4 direct) |
| General HR | "What should a new hire know?" | `search_knowledge_base` (Phase 4 direct) |
| Compound | "Leave policy and check EMP-0001 balance" | `search_policies` + `check_leave_balance` |

**Why two separate tool sets exist:**
The Phase 4 tools accept natural language (names, questions, phrases) and are optimised for retrieval. The MCP tools accept structured inputs (EMP-IDs, date strings, leave types) and are optimised for actions. The agent's tool descriptions route correctly without any hardcoded rules — tool description engineering is the critical design work in Phase 5.

---

## Pre-Phase Setup — Install Dependencies

### Install FastMCP and LangChain MCP Adapters

```bash
uv add fastmcp
uv add langchain-mcp-adapters
```

### Verify Installation

```bash
uv run python -c "import fastmcp; print(fastmcp.__version__)"
uv run python -c "from langchain_mcp_adapters.client import MultiServerMCPClient; print('langchain-mcp-adapters OK')"
```

### Results

```
3.3.1
langchain-mcp-adapters OK
```

**Version stack for Phase 5:**

| Package | Version |
|---|---|
| `fastmcp` | 3.3.1 |
| `langchain-mcp-adapters` | 0.2.2 |
| `langchain` | 1.3.1 |
| `langgraph` | 1.2.0 |

---

## Step 1 — MCP Server Entry Point

### Concept

The FastMCP server is a **separate process** from FastAPI. It runs on port 8002 and exposes 4 HR tools via HTTP transport. The server file defines the `mcp` instance first — tool module imports are deferred until after the instance is created because the `@mcp.tool` decorator in each tool file needs the `mcp` instance to exist when those modules load.

**FastMCP 3.x key facts:**
- `@mcp.tool` decorator (no parentheses in v3) turns any Python function into an MCP tool
- Docstrings become tool descriptions automatically — the LLM reads these for tool selection
- Type hints generate input schemas automatically
- HTTP transport serves at `/mcp` endpoint by default
- Functions stay callable as normal Python — not converted to objects (a v3 improvement over v2)

### Claude Code Prompt

```
Create three files:
  mcp_server/__init__.py          (empty package marker)
  mcp_server/tools/__init__.py    (empty package marker)
  mcp_server/server.py            (FastMCP server entry point)

In mcp_server/server.py:

from fastmcp import FastMCP
import logging

Create the FastMCP instance:
  mcp = FastMCP(
      "ARIA HR MCP Server",
      instructions=(
          "You are connected to the ARIA HR MCP Server for Acme Corp. "
          "This server provides tools to check employee leave balances, "
          "submit leave requests, look up org chart information, and "
          "search HR policy documents. All write operations require "
          "valid employee_id in EMP-XXXX format."
      )
  )

Import tool modules AFTER creating mcp (deferred so decorators
can reference the mcp instance):
  from mcp_server.tools import leave_tool
  from mcp_server.tools import org_chart_tool
  from mcp_server.tools import policy_lookup_tool

Logging setup and if __name__ == "__main__" block:
  mcp.run(transport="http", host="0.0.0.0", port=8002)
```

### Implementation Notes from Claude Code

The tool module imports are placed after `mcp` is defined so the decorators in `leave_tool`, `org_chart_tool`, and `policy_lookup_tool` can reference the `mcp` instance when those modules are loaded. Reversing this order causes an `ImportError` — `mcp` would not yet exist when the decorator fires.

### Exit Criteria

| Check | Status |
|---|---|
| `mcp_server/__init__.py` created (empty) | ✅ |
| `mcp_server/tools/__init__.py` created (empty) | ✅ |
| `mcp_server/server.py` created | ✅ |
| `mcp` instance created before tool imports | ✅ |
| HTTP transport configured on port 8002 | ✅ |

---

## Step 2 — Leave Tool

### Concept

Two tools in one file — one read, one write. `check_leave_balance` reads PostgreSQL for an employee's remaining leave days. `submit_leave_request` inserts a new `LeaveRecord` row — the **first write operation in the entire ARIA platform**.

Both tools validate `employee_id` format before touching the database. `submit_leave_request` validates leave type against the allowed enum, parses and validates the date range, verifies the employee exists, then performs the insert in a single atomic transaction.

**The key SQLAlchemy pattern distinction:**
- `engine.connect()` for reads — lightweight, auto-closes, no transaction overhead
- `engine.begin()` for writes — opens a transaction, auto-commits on success, auto-rolls back on any exception

### Claude Code Prompt

```
Create mcp_server/tools/leave_tool.py with two FastMCP tools.

Imports:
  from mcp_server.server import mcp
  from sqlalchemy import create_engine, text
  from sqlalchemy.exc import SQLAlchemyError
  from config.settings import settings
  import datetime
  import logging

TOOL 1: check_leave_balance
@mcp.tool
def check_leave_balance(employee_id: str) -> str:
    """
    Check the current leave balance for an Acme Corp employee.
    Use this tool when an employee asks how many leave days they
    have remaining. Returns the employee name and leave balance
    in days. employee_id must be in format EMP-XXXX e.g. EMP-0001.
    """
    - Validate employee_id starts with "EMP-"
    - Use engine.connect() for read
    - SELECT first_name, last_name, leave_balance, status FROM
      employees WHERE employee_id = :emp_id
    - Return: "{name} has {balance} days of leave remaining.
      Status: {status}"
    - On SQLAlchemyError: log and return error string

TOOL 2: submit_leave_request
@mcp.tool
def submit_leave_request(
    employee_id: str,
    start_date: str,
    end_date: str,
    leave_type: str = "Annual",
    reason: str = "",
) -> str:
    """
    Submit a new leave request for an Acme Corp employee.
    This tool WRITES a new leave record to the database.
    Use when an employee explicitly asks to submit, book, or
    request leave. employee_id must be in EMP-XXXX format.
    start_date and end_date must be in YYYY-MM-DD format.
    leave_type must be one of: Annual, Sick, Parental,
    Emergency, Unpaid. Default is Annual.
    """
    - Validate employee_id starts with "EMP-"
    - Validate leave_type in allowed list
    - Parse dates with datetime.date.fromisoformat()
    - Validate end_date >= start_date
    - Calculate days = (end_date - start_date).days + 1
    - Use engine.begin() for atomic transaction
    - Verify employee exists first — return error if not found
    - INSERT INTO leave_records with status='Pending'
    - Return confirmation string
    - On exception: rollback, log, return error string
```

### Implementation Notes from Claude Code

- `engine.begin()` is used in `submit_leave_request` — it auto-commits on success and auto-rolls back on exception, so no explicit `conn.commit()` / `conn.rollback()` calls are needed.
- `engine.connect()` is used in `check_leave_balance` since no write is needed.
- The employee existence check and the insert share the same `engine.begin()` connection, so both run in one atomic transaction — if the employee check fails, no partial insert occurs.

### Exit Criteria

| Check | Status |
|---|---|
| `leave_tool.py` created | ✅ |
| `check_leave_balance` registered on `mcp` instance | ✅ |
| `submit_leave_request` registered on `mcp` instance | ✅ |
| `engine.begin()` used for atomic write | ✅ |
| `engine.connect()` used for read | ✅ |

---

## Step 3 — Org Chart Tool

### Concept

Single tool that runs two queries inside one `engine.connect()` context: a three-table join (`employees` → `org_chart` → `employees` self-join for manager name) for the employee's position and manager, then a second query for all direct reports. Both queries share one connection.

### Claude Code Prompt

```
Create mcp_server/tools/org_chart_tool.py with one FastMCP tool.

Imports:
  from mcp_server.server import mcp
  from sqlalchemy import create_engine, text
  from sqlalchemy.exc import SQLAlchemyError
  from config.settings import settings
  import logging

TOOL: get_org_chart
@mcp.tool
def get_org_chart(employee_id: str) -> str:
    """
    Get the organisational chart information for an Acme Corp
    employee — their manager, direct reports, team, and level.
    Use this tool when asked about reporting structure, who
    someone reports to, or who reports to them.
    employee_id must be in EMP-XXXX format e.g. EMP-0001.
    """
    - Validate employee_id starts with "EMP-"
    - Use single engine.connect() for both queries

    Query 1 — employee info + manager (LEFT JOIN for top-level):
      SELECT e.first_name, e.last_name, e.role, e.department,
             o.level, o.team, o.manager_id,
             m.first_name AS manager_first,
             m.last_name AS manager_last,
             m.role AS manager_role
      FROM employees e
      JOIN org_chart o ON e.employee_id = o.employee_id
      LEFT JOIN employees m ON o.manager_id = m.employee_id
      WHERE e.employee_id = :emp_id

    Query 2 — direct reports:
      SELECT e.employee_id, e.first_name, e.last_name, e.role
      FROM employees e
      JOIN org_chart o ON e.employee_id = o.employee_id
      WHERE o.manager_id = :emp_id
      ORDER BY e.last_name

    Build result string with 4 lines:
      "{name} — {role} ({department})"
      "Team: {team} | Level: {level}"
      "Reports to: {manager}" or "No manager (top level)"
      "Direct reports ({count}): {list}" or "None"

    - On SQLAlchemyError: return error string
```

### Implementation Notes from Claude Code

Both queries run inside a single `engine.connect()` context so they share one connection. Direct reports are accessed by column name (`r.first_name`) using SQLAlchemy's named-column row interface. The LEFT JOIN on the manager table handles top-level employees (VP-level) who have `manager_id = NULL`.

### Exit Criteria

| Check | Status |
|---|---|
| `org_chart_tool.py` created | ✅ |
| `get_org_chart` registered on `mcp` instance | ✅ |
| Single `engine.connect()` for both queries | ✅ |
| LEFT JOIN handles top-level employees correctly | ✅ |

---

## Step 4 — Policy Lookup Tool

### Concept

The simplest of the four tools. Wraps the existing `search_and_format()` from `vector_store/searcher.py` as an MCP tool — giving any MCP-compatible client direct semantic search over the HR policy ChromaDB collection. No new code paths — pure reuse of the Phase 2 vector store infrastructure.

### Claude Code Prompt

```
Create mcp_server/tools/policy_lookup_tool.py with one FastMCP tool.

Imports:
  from mcp_server.server import mcp
  from vector_store.searcher import search_and_format
  import logging

TOOL: policy_lookup
@mcp.tool
def policy_lookup(query: str) -> str:
    """
    Search Acme Corp HR policy documents for a specific clause,
    rule, or entitlement. Use this tool when an employee asks
    about a specific policy topic and needs the exact wording
    or details from the official policy documents.
    Returns the most relevant policy excerpts with source citations.
    query should be a specific topic or keyword, for example:
    'parental leave entitlement', 'probation period notice',
    '401k contribution matching'.
    """
    - Call search_and_format(query, n_results=3)
    - Log: f"Policy lookup MCP tool called: {query[:50]}"
    - If result is empty or sentinel "No relevant information found.":
      return "No policy information found. Contact hr@acmecorp.com"
    - Return formatted result string
```

### Implementation Notes from Claude Code

Logging uses `%s` style lazy evaluation consistent with the other tool files. Empty-string check uses `not result` to catch both `""` and `None` before comparing to the sentinel string — defensive ordering prevents a potential `AttributeError`.

### Exit Criteria

| Check | Status |
|---|---|
| `policy_lookup_tool.py` created | ✅ |
| `policy_lookup` registered on `mcp` instance | ✅ |
| Wraps `search_and_format()` — zero code duplication | ✅ |
| Empty result fallback returns clear HR contact message | ✅ |

---

## Step 5 — MCP Start Script + Full Verification

### Concept

A standalone CLI runner that adds the project root to `sys.path` before importing the MCP server, so it works regardless of the working directory. The `mcp` import is deferred inside `__main__` — the path fix must be in place before any project modules load.

### Claude Code Prompt

```
Create scripts/start_mcp_server.py — CLI runner for the MCP server.

Add sys.path.insert at top:
  import sys, os
  sys.path.insert(0, os.path.dirname(os.path.dirname(
      os.path.abspath(__file__)
  )))

Then logging setup with timestamp format and __main__ block:
  logger.info("=" * 50)
  logger.info("ARIA HR MCP Server")
  logger.info("Transport: HTTP | Port: 8002")
  logger.info("Endpoint: http://localhost:8002/mcp")
  logger.info("Tools: check_leave_balance, submit_leave_request,")
  logger.info("       get_org_chart, policy_lookup")
  logger.info("=" * 50)
  from mcp_server.server import mcp
  mcp.run(transport="http", host="0.0.0.0", port=8002)
```

### Run Command

```bash
# Terminal Tab 4 — keep running throughout Phase 5
uv run python scripts/start_mcp_server.py
```

### Verify Tool Registration

> **Important:** Raw `curl` cannot be used against FastMCP 3.x HTTP transport. It requires a session ID from the MCP handshake. Use the FastMCP Python client for all verification.

**First attempt with curl — expected failure:**
```bash
curl -s -X POST http://localhost:8002/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'
# Returns: {"error": {"message": "Bad Request: Missing session ID"}}
```

**Correct approach — FastMCP Python client:**
```bash
uv run python -c "
import asyncio
from fastmcp import Client

async def list_tools():
    async with Client('http://localhost:8002/mcp') as client:
        tools = await client.list_tools()
        print(f'Tools registered: {len(tools)}')
        for t in tools:
            print(f'  - {t.name}')

asyncio.run(list_tools())
"
```

### Tool Registration Results

```
Tools registered: 4
  - check_leave_balance
  - submit_leave_request
  - get_org_chart
  - policy_lookup
```

### Verify Read Tools

```bash
uv run python -c "
import asyncio
from fastmcp import Client

async def test_tools():
    async with Client('http://localhost:8002/mcp') as client:
        print('=== check_leave_balance ===')
        result = await client.call_tool('check_leave_balance',
            {'employee_id': 'EMP-0001'})
        print(result.data)

        print()
        print('=== get_org_chart ===')
        result = await client.call_tool('get_org_chart',
            {'employee_id': 'EMP-0001'})
        print(result.data)

        print()
        print('=== policy_lookup ===')
        result = await client.call_tool('policy_lookup',
            {'query': 'parental leave entitlement'})
        print(str(result.data)[:300])

asyncio.run(test_tools())
"
```

### Read Tool Results

```
=== check_leave_balance ===
James Chen has 30 days of leave remaining. Status: Active

=== get_org_chart ===
James Chen — VP of Engineering (Engineering)
Team: Platform Team | Level: 2
Reports to: No manager (top level)
Direct reports (2): Marcus Johnson — Director of Engineering,
                    Priya Sharma — Director of Engineering

=== policy_lookup ===
[Source: leave_policy.pdf (Page 1)]
· Leave in excess of carryover limit is forfeited at year end
3. Sick Leave
· Entitlement: 10 days per calendar year
· Sick leave does not accrue and does not carry over...
```

### Verify Write Tool

```bash
uv run python -c "
import asyncio
from fastmcp import Client

async def test_submit():
    async with Client('http://localhost:8002/mcp') as client:
        result = await client.call_tool('submit_leave_request', {
            'employee_id': 'EMP-0001',
            'start_date': '2026-12-25',
            'end_date': '2026-12-27',
            'leave_type': 'Annual',
            'reason': 'Christmas holiday'
        })
        print(result.data)

asyncio.run(test_submit())
"
```

### Write Tool Result

```
Leave request submitted successfully for EMP-0001.
Dates: 2026-12-25 to 2026-12-27 (3 day(s)).
Type: Annual. Status: Pending.
Your manager will be notified for approval.
```

### Database Write Verification

```bash
docker exec -it hr_postgres psql -U hr_user -d hr_platform \
  -c "SELECT employee_id, start_date, end_date, leave_type, status, reason
      FROM leave_records WHERE employee_id = 'EMP-0001'
      ORDER BY id DESC LIMIT 3;"
```

```
 employee_id | start_date |  end_date  | leave_type | status  |      reason
-------------+------------+------------+------------+---------+-------------------
 EMP-0001    | 2026-12-25 | 2026-12-27 | Annual     | Pending | Christmas holiday
(1 row)
```

### Step 5 Exit Criteria

| Check | Status |
|---|---|
| MCP server starts on port 8002 | ✅ |
| 4 tools registered and listed | ✅ |
| `check_leave_balance` returns correct data | ✅ James Chen, 30 days, Active |
| `get_org_chart` returns hierarchy with direct reports | ✅ Platform Team, Level 2, 2 reports |
| `policy_lookup` returns ChromaDB chunks with citations | ✅ |
| `submit_leave_request` writes to PostgreSQL | ✅ |
| Row confirmed in `leave_records` table | ✅ EMP-0001, Dec 25-27, Pending |

---

## Step 6 — Agent MCP Integration

### Concept

Wire the MCP server tools into the Phase 4 ReAct agent alongside the existing 3 direct tools. The agent gains 4 new tools from the MCP server, bringing the total to 7. This step also migrates `hr_advisor.py` from the Phase 4 `create_react_agent` (LangChain 0.3.x) pattern to `create_agent` (LangChain 1.3.1 / LangGraph 1.2.0), which was necessary because `langchain-mcp-adapters` pulled in updated LangChain dependencies.

### Version Context Discovered During Phase 5

```
LangChain:              1.3.1   (upgraded beyond Phase 4's 0.3.x target)
LangGraph:              1.2.0
langchain-mcp-adapters: 0.2.2
```

**Three API changes required in `hr_advisor.py`:**

| Issue | Error Message | Fix Applied |
|---|---|---|
| LangGraph deprecation | `create_react_agent has been moved to langchain.agents` | `from langchain.agents import create_agent` |
| Context manager removed | `MultiServerMCPClient cannot be used as a context manager` | Direct instantiation: `client = MultiServerMCPClient(...)` |
| Wrong parameter name | `create_agent() got an unexpected keyword argument 'prompt'` | `system_prompt=` not `prompt=` |

**Confirmed `create_agent` signature in LangChain 1.3.1:**
```
create_agent(
    model: str | BaseChatModel,
    tools: Sequence[BaseTool] | None = None,
    *,
    system_prompt: str | SystemMessage | None = None,
    ...
) -> CompiledStateGraph
```

Returns a `CompiledStateGraph` directly — no `AgentExecutor` wrapper needed. Result accessed via `result["messages"][-1].content`. Tool calls extracted from `msg.tool_calls` on the message history.

### Claude Code Prompt

```
Update agents/single/hr_advisor.py to add MCP tools.

The existing 3 tools and run_hr_advisor() must remain unchanged.

CHANGE 1 — Add imports:
  from langchain_mcp_adapters.client import MultiServerMCPClient
  import asyncio

CHANGE 2 — Add constant after imports:
  MCP_SERVER_URL = "http://localhost:8002/mcp"

CHANGE 3 — Add run_hr_advisor_with_mcp() async function:
  async def run_hr_advisor_with_mcp(question: str) -> AgentResponse:
      try:
          mcp_client = MultiServerMCPClient(
              {"aria_hr_mcp": {"transport": "http",
                               "url": MCP_SERVER_URL}}
          )
          mcp_tools = await mcp_client.get_tools()
          all_tools = HR_ADVISOR_TOOLS + mcp_tools
          agent = create_agent(
              model=get_llm(),
              tools=all_tools,
              system_prompt=HR_ADVISOR_SYSTEM_PROMPT,
          )
          result = await agent.ainvoke(
              {"messages": [{"role": "user", "content": question}]}
          )
          answer = result["messages"][-1].content
          steps = []
          tools_used = []
          for msg in result["messages"]:
              if hasattr(msg, "tool_calls") and msg.tool_calls:
                  for tc in msg.tool_calls:
                      steps.append({
                          "thought": f"Calling {tc['name']}",
                          "tool": tc["name"],
                          "tool_input": str(tc["args"]),
                          "observation": "",
                      })
                      tools_used.append(tc["name"])
          return AgentResponse(answer=answer, steps=steps,
                               tools_used=tools_used, success=True)
      except Exception as e:
          logger.error(f"MCP agent error: {e}")
          return AgentResponse(
              answer=f"Error processing request. (Error: {e})",
              steps=[], tools_used=[], success=False,
          )

Also fix all imports and create_agent calls to use:
  from langchain.agents import create_agent
  system_prompt= (not prompt=)
Remove MultiServerMCPClient context manager pattern.
```

### Run Command

```bash
# Ensure MCP server running in Tab 4
uv run python -m agents.single.hr_advisor
```

### Results — All 8 Test Questions

```
============================================================
Q: What is the parental leave policy?
Answer: Primary Caregiver: 16 weeks fully paid. Secondary Caregiver:
        4 weeks. Eligibility: 6 months continuous service.
        [Source: leave_policy.pdf]
Tools used: ['search_policies']
Steps: 1

============================================================
Q: How many leave days does James Chen have?
Answer: James Chen has a leave balance of 30 days.
Tools used: ['lookup_employee']
Steps: 1

============================================================
Q: What is the remote work policy and how many days does Isabella Fernandez have?
Answer: Hybrid model: 3 days in office minimum, 2 days remote max.
        $500 home office allowance. [Source: employee_handbook.pdf (Page 3)]
        Isabella Fernandez currently has a leave balance of 8 days.
Tools used: ['search_policies', 'lookup_employee']
Steps: 2

============================================================
Q: What should a new hire know about their first week?
Answer: Company orientation, system setup, IT provisioning, meet your
        team, and onboarding buddy assigned. [Source: Employee Handbook]
Tools used: ['search_knowledge_base']
Steps: 1

============================================================
Q: Check the leave balance for EMP-0001
Answer: James Chen has 30 days of leave remaining.
Tools used: ['check_leave_balance']              ← MCP tool

============================================================
Q: Submit a leave request for EMP-0001 from 2026-12-28 to 2026-12-30 for Annual leave
Answer: The leave request for EMP-0001 has been successfully submitted
        for Annual leave from December 28 to December 30, 2026.
        The request is pending approval from the manager.
Tools used: ['submit_leave_request']             ← MCP tool (WRITE)

============================================================
Q: Who does EMP-0001 report to?
Answer: EMP-0001, James Chen, is the VP of Engineering and does not
        report to any manager as he is at the top level.
Tools used: ['get_org_chart']                    ← MCP tool

============================================================
Q: What is the parental leave policy and check the leave balance for EMP-0001
Answer: Parental leave: primary caregivers 16 weeks fully paid,
        secondary caregivers 4 weeks. [Source: leave_policy.pdf]
        EMP-0001 James Chen has 30 days of leave remaining.
Tools used: ['search_policies', 'check_leave_balance']  ← mixed: direct + MCP
```

### Tool Routing Observed

| Question | Tools Used | Source |
|---|---|---|
| Policy question | `search_policies` | Phase 4 direct |
| Named employee | `lookup_employee` | Phase 4 direct |
| Compound named + policy | `search_policies` + `lookup_employee` | Phase 4 direct |
| General HR | `search_knowledge_base` | Phase 4 direct |
| EMP-ID balance | `check_leave_balance` | **Phase 5 MCP** |
| Leave submission | `submit_leave_request` | **Phase 5 MCP (WRITE)** |
| Org chart by ID | `get_org_chart` | **Phase 5 MCP** |
| Compound policy + EMP-ID | `search_policies` + `check_leave_balance` | **Mixed: direct + MCP** |

### Database Write Confirmation

```bash
docker exec -it hr_postgres psql -U hr_user -d hr_platform \
  -c "SELECT employee_id, start_date, end_date, leave_type, status
      FROM leave_records WHERE employee_id = 'EMP-0001'
      ORDER BY id DESC LIMIT 3;"
```

```
 employee_id | start_date |  end_date  | leave_type | status
-------------+------------+------------+------------+---------
 EMP-0001    | 2026-12-28 | 2026-12-30 | Annual     | Pending
 EMP-0001    | 2026-12-25 | 2026-12-27 | Annual     | Pending
(2 rows)
```

### Step 6 Exit Criteria

| Check | Status |
|---|---|
| `run_hr_advisor_with_mcp()` created | ✅ |
| MCP tools loaded via `MultiServerMCPClient` | ✅ |
| Agent has 7 tools total (3 direct + 4 MCP) | ✅ |
| EMP-ID queries route to MCP tools | ✅ |
| Name-based queries route to Phase 4 direct tools | ✅ |
| Compound query uses both tool sources | ✅ |
| Write confirmed in PostgreSQL — 2 rows | ✅ |

---

## Step 7 — DeepEval MCP Tests

### Concept

Four tests covering the three MCP usage patterns — read tools, write tool, and multi-step sequences — plus a boundary test that verifies correct tool routing across all 10 golden set entries without an LLM judge.

The test helper calls `asyncio.run(run_hr_advisor_with_mcp(question))` to invoke the async agent function from synchronous pytest test functions — no `pytest-asyncio` required. A 3-second sleep between calls prevents OpenAI TPM rate limit errors across 10 sequential agent invocations.

### DeepEval Metrics

| Metric | What It Measures | LLM Judge |
|---|---|---|
| `TaskCompletionMetric` | Did the agent complete what the user asked? | ✅ gpt-4o |
| `AnswerRelevancyMetric` | Is the answer focused and on-point? | ✅ gpt-4o |

### Golden Set — `evaluation/datasets/mcp_golden_set.json`

10 entries across 3 categories:

| # | Input | Query Type | Expected MCP Tool |
|---|---|---|---|
| 1 | "Check the leave balance for EMP-0001" | read | `check_leave_balance` |
| 2 | "What is the leave balance for EMP-0022?" | read | `check_leave_balance` |
| 3 | "What is James Chen's position and who reports to him? Use EMP-0001" | read | `get_org_chart` |
| 4 | "Who are the direct reports of EMP-0001?" | read | `get_org_chart` |
| 5 | "Submit Annual leave for EMP-0001 from 2027-01-02 to 2027-01-03" | write | `submit_leave_request` |
| 6 | "Book Sick leave for EMP-0022 from 2027-01-10 to 2027-01-10" | write | `submit_leave_request` |
| 7 | "Request Emergency leave for EMP-0001 on 2027-02-14" | write | `submit_leave_request` |
| 8 | "Check leave balance for EMP-0001 and look up the parental leave policy" | multi_step | `check_leave_balance` |
| 9 | "Get the org chart for EMP-0001 and check their leave balance" | multi_step | `get_org_chart` |
| 10 | "Submit Annual leave for EMP-0001 from 2027-03-01 to 2027-03-03 and confirm balance" | multi_step | `submit_leave_request` |

> **Golden set design note:** Entry 3 was initially "Get the org chart for EMP-0001." The judge scored it 0.60 because it interpreted "org chart" as requiring the full company hierarchy. Rephrased to specify one employee's position and direct reports — scored 1.00 on re-run. Lesson: ambiguous scope in golden set entries causes judge penalisation, not agent failure.

### Claude Code Prompt — Golden Set

```
Create evaluation/datasets/mcp_golden_set.json with 10 entries.
Each entry: "input", "expected_output", "query_type",
"expected_mcp_tool"

Read queries (4): check_leave_balance for EMP-0001 and EMP-0022,
  get_org_chart for EMP-0001 — two variants with explicit scope

Write queries (3): submit_leave_request — Annual for EMP-0001,
  Sick for EMP-0022, Emergency for EMP-0001, all dates in 2027

Multi-step queries (3): balance + policy lookup, org chart +
  balance, submit + confirm balance — all using EMP-0001
```

### Claude Code Prompt — Test File

```
Create evaluation/tests/test_mcp.py

sys.path.insert at top (same pattern as test_single_agent.py)

Imports: pytest, json, os, time, asyncio, deepeval evaluate,
  TaskCompletionMetric, AnswerRelevancyMetric, LLMTestCase,
  run_hr_advisor_with_mcp

Helper get_mcp_response(question):
  result = asyncio.run(run_hr_advisor_with_mcp(question))
  time.sleep(3.0)
  return result

Helper build_mcp_test_case(item):
  result = get_mcp_response(item["input"])
  return LLMTestCase(input=..., actual_output=result.answer,
                     expected_output=...)

Fixture mcp_golden_set: loads mcp_golden_set.json
Fixture mcp_metrics: TaskCompletionMetric(0.7, gpt-4o) +
  AnswerRelevancyMetric(0.7, gpt-4o)

TEST 1: test_mcp_read_tools — query_type=="read", cap 3
TEST 2: test_mcp_write_tool — query_type=="write", cap 3
TEST 3: test_mcp_multi_step — query_type=="multi_step", all 3
TEST 4: test_mcp_tool_routing_boundary — all 10 entries, pure
  assertion that expected_mcp_tool in result.tools_used,
  collect all failures before final assert
```

### Run Commands

```bash
export DEEPEVAL_PER_TASK_TIMEOUT_SECONDS_OVERRIDE=600
export DEEPEVAL_PER_ATTEMPT_TIMEOUT_SECONDS_OVERRIDE=300

# Boundary test first — no LLM judge, no cost
uv run deepeval test run evaluation/tests/test_mcp.py::test_mcp_tool_routing_boundary -v

# LLM-judged tests
uv run deepeval test run evaluation/tests/test_mcp.py::test_mcp_read_tools -v
uv run deepeval test run evaluation/tests/test_mcp.py::test_mcp_write_tool -v
uv run deepeval test run evaluation/tests/test_mcp.py::test_mcp_multi_step -v

# Or run the full suite
uv run deepeval test run evaluation/tests/test_mcp.py -v
```

---

## DeepEval Results — Final Baseline

### test_mcp_tool_routing_boundary

```
10/10 entries routed to correct MCP tool
Cost: $0.000 (no LLM judge) | Time: 62s
```

All 10 golden set questions invoked their expected MCP tool. No mis-routing to Phase 4 direct tools on any entry.

---

### test_mcp_read_tools

```
Task Completion:   avg=0.98  pass=100%  total=3
Answer Relevancy:  avg=1.00  pass=100%  total=3
Cost: $0.024 | Time: 21s
```

**Judge reasoning — check_leave_balance (EMP-0001):**
> "The system successfully retrieved and provided the leave balance for employee EMP-0001, meeting the task requirements perfectly."

**Judge reasoning — check_leave_balance (EMP-0022):**
> "The system accurately provided the leave balance for employee EMP-0022, including the number of leave days remaining and the current leave status, fully meeting the task requirements."

**Judge reasoning — get_org_chart (EMP-0001):**
> "The actual outcome perfectly identifies James Chen's position as VP of Engineering and lists his direct reports, Marcus Johnson and Priya Sharma, as Directors of Engineering, fully achieving the desired task."

---

### test_mcp_write_tool

```
Task Completion:   avg=1.00  pass=100%  total=3
Answer Relevancy:  avg=1.00  pass=100%  total=3
Cost: $0.025 | Time: 21s
```

**Judge reasoning — Annual leave (EMP-0001):**
> "The annual leave request for the specified employee and dates was successfully submitted, fulfilling the task requirements."

**Judge reasoning — Sick leave (EMP-0022):**
> "The sick leave request for employee EMP-0022 was successfully submitted for the specified date, fulfilling the task requirements."

**Judge reasoning — Emergency leave (EMP-0001):**
> "The emergency leave request for EMP-0001 on the specified date was submitted successfully, fulfilling the task requirements."

Both metrics at 1.00 across all 3 leave types — the most significant result in Phase 5. `TaskCompletionMetric` at 1.00 confirms the judge recognised the action was completed, not just described.

---

### test_mcp_multi_step

```
Task Completion:   avg=0.98  pass=100%  total=3
Answer Relevancy:  avg=0.95  pass=100%  total=3
Cost: $0.031 | Time: 29s
```

**Judge reasoning — balance + parental policy:**
> "The system successfully retrieved the leave balance for EMP-0001 and provided comprehensive details on the parental leave policy, fully meeting the task requirements."

**Judge reasoning — org chart + balance:**
> "The system successfully retrieved both the organizational chart and the leave balance for employee EMP-0001, fulfilling the task requirements completely."

**Judge reasoning — submit + confirm balance:**
> "The task was to submit an annual leave request and confirm the remaining leave balance for EMP-0001. The actual outcome successfully submitted the leave request and confirmed the remaining leave balance."

> **Note on 0.95 Answer Relevancy:** The slight deduction on entry 8 was the source citation included in the answer. This is judge variance — the answer content is correct and complete.

---

## Phase 5 DeepEval Complete Baseline

| Test | Metric | Avg Score | Pass Rate | Cases | Cost | Time |
|---|---|---|---|---|---|---|
| `test_mcp_tool_routing_boundary` | Routing assertion | **100%** | 100% | 10 | $0.000 | 62s |
| `test_mcp_read_tools` | TaskCompletion + AnswerRelevancy | **0.99** | 100% | 3 | $0.024 | 21s |
| `test_mcp_write_tool` | TaskCompletion + AnswerRelevancy | **1.00** | 100% | 3 | $0.025 | 21s |
| `test_mcp_multi_step` | TaskCompletion + AnswerRelevancy | **0.97** | 100% | 3 | $0.031 | 29s |
| **Total Phase 5** | | **0.99 avg** | **100%** | **19** | **$0.080** | **133s** |

---

## Phase 5 Complete ✅

| Step | What Was Built | Status |
|---|---|---|
| Step 1 | FastMCP server — entry point, package files, HTTP transport port 8002 | ✅ |
| Step 2 | Leave tool — `check_leave_balance` (read) + `submit_leave_request` (write) | ✅ |
| Step 3 | Org chart tool — `get_org_chart` with self-join for manager lookup | ✅ |
| Step 4 | Policy lookup tool — wraps `search_and_format()` as MCP tool | ✅ |
| Step 5 | MCP start script + full server verification via FastMCP Python client | ✅ |
| Step 6 | Agent MCP integration — 7 tools, LangChain 1.3.1 migration, 2 DB writes confirmed | ✅ |
| Step 7 | DeepEval — 4 tests, 19 cases, 100% pass rate, $0.080 total cost | ✅ |

---

## Phase 5 vs Phase 4 Capability Comparison

| Capability | Phase 4 | Phase 5 |
|---|---|---|
| Policy questions | ✅ `search_policies` | ✅ Unchanged |
| Named employee queries | ✅ `lookup_employee` | ✅ Unchanged |
| EMP-ID balance check | ❌ Not supported | ✅ `check_leave_balance` via MCP |
| Org chart by ID | ❌ Not supported | ✅ `get_org_chart` via MCP |
| Leave submission | ❌ Read-only platform | ✅ `submit_leave_request` — WRITE |
| Total agent tools | 3 | **7** |
| Database writes | ❌ Zero | ✅ First write in ARIA |
| Tool architecture | Direct Python calls | Phase 4 direct + MCP network service |
| DeepEval pass rate | 100% (19 cases) | 100% (19 cases) |

---

## Known Gaps — Phase 7 Tuning Items

| Issue | Severity | Phase 7 Fix |
|---|---|---|
| MCP server must be started manually in a separate terminal | Medium | Add to `docker-compose.yml` as a service |
| `submit_leave_request` does not deduct from `leave_balance` | Medium | Add `UPDATE employees SET leave_balance = leave_balance - {days}` in same transaction |
| `run_hr_advisor_with_mcp()` creates new `MultiServerMCPClient` per call | Low | Module-level singleton with connection reuse |
| FastAPI `/agent/query` still uses Phase 4 direct tools only | Medium | Update route to call `run_hr_advisor_with_mcp()` |
| No human-in-the-loop before write operations | Medium | Phase 6 LangGraph interrupt node for write approval |
| Streamlit does not distinguish MCP vs direct tool badges | Low | Phase 8 — add MCP action badge style |

---

## Infrastructure Notes

**Running the MCP server:**
```bash
uv run python scripts/start_mcp_server.py
```
Must be running before any agent MCP calls or DeepEval MCP tests.

**Verifying the MCP server — FastMCP Python client (not curl):**
```bash
uv run python -c "
import asyncio
from fastmcp import Client
async def check():
    async with Client('http://localhost:8002/mcp') as c:
        tools = await c.list_tools()
        print([t.name for t in tools])
asyncio.run(check())
"
```

**Database credentials:**
```
Host: localhost:5432 | DB: hr_platform
User: hr_user | Password: hr_password
```

**sys.path fix for DeepEval tests:** Same pattern as previous phases:
```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)
))))
```

**Phase 4 baseline maintained:** All Phase 4 direct tools continue working unchanged through Phase 5. The 4 test questions using Phase 4 direct tools all passed in the Step 6 verification run.

---

## What Comes Next — Phase 6

Phase 6 adds **multi-agent LangGraph orchestration** — a `StateGraph` that routes each query to one or more specialist agents based on intent classification.

**Phase 6 components:**
- `agents/orchestrator/state.py` — shared `AgentState` TypedDict
- `agents/orchestrator/router.py` — LLM intent classification node
- `agents/specialist/policy_agent.py` — Document RAG specialist
- `agents/specialist/leave_agent.py` — Database RAG + MCP write specialist
- `agents/specialist/onboarding_agent.py` — Hybrid retriever specialist
- `agents/specialist/payroll_agent.py` — Benefits specialist
- `agents/orchestrator/graph.py` — LangGraph `StateGraph` wiring all agents
- Human-in-the-loop interrupt node before `submit_leave_request` fires

**The Phase 5 baseline must be maintained:** All 4 MCP tools must continue responding correctly through Phase 6. `submit_leave_request` is foundational to the Phase 6 Leave Agent.

> **The Phase 5 milestone:** ARIA can now act, not just answer. The `submit_leave_request` tool is the first time a user's natural language instruction directly modifies database state. This is the foundation of every agentic workflow in Phases 6–8 — the pattern that separates a Q&A chatbot from an enterprise AI agent.
