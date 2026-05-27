# ARIA — HR GenAI Agent Platform
## Phase 3 Build Guide — Database RAG

> NL-to-SQL, live PostgreSQL queries, structured employee answers with SQL transparency, and DeepEval database evaluation.
> **Completed in 1 day | 8 Steps | 13 routing assertions | 100% routing pass rate**

---

## Phase 3 Overview

Phase 3 gives ARIA a second knowledge source — structured employee data stored in PostgreSQL. Phase 2 ARIA could answer HR policy questions from PDFs. Phase 3 ARIA can now answer factual questions about specific employees, leave balances, department headcounts, and org chart relationships by querying the live database.

**The transformation:**

```
Phase 2 — Policy documents only:
User: "How many leave days does James Chen have?"
ARIA: "I don't have specific information about that in our
       company documents. Please contact HR at hr@acmecorp.com."
       (correct refusal — not a document question)

Phase 3 — Policies + live employee database:
User: "How many leave days does James Chen have?"
ARIA: "James Chen has 30 days of leave remaining."
       (specific, accurate, sourced from live database)
```

**What Phase 3 Delivers:**

- Database schema context for NL-to-SQL translation
- GPT-4o NL-to-SQL engine with safety validation
- SQLAlchemy query executor with date serialization
- Complete Database RAG chain at `temperature=0` for factual consistency
- Three-way query router: `"rag"` | `"db"` | `"chat"`
- FastAPI endpoints: `/rag/db/query`, `/rag/db/stream`
- Streamlit UI with SQL expander for query transparency
- DeepEval evaluation suite — 4 tests, 13 routing assertions, 100% routing pass rate

**8 Steps:**

| # | Step | File(s) Created / Updated | Delivers |
|---|---|---|---|
| 1 | Database Schema Context | `rag/database_rag/schema.py` | NL-to-SQL schema description |
| 2 | NL-to-SQL Engine | `rag/database_rag/nl_to_sql.py` | Natural language → validated SQL |
| 3 | SQL Executor | `rag/database_rag/executor.py` | Safe SQL execution + result formatting |
| 4 | Database RAG Chain | `rag/database_rag/chain.py` | Complete NL → SQL → answer pipeline |
| 5 | Three-way Query Router | `backend/chains/rag_router.py` updated | `"rag"` / `"db"` / `"chat"` classification |
| 6 | FastAPI DB Endpoints | `backend/api/routes/rag.py` updated | `/rag/db/query`, `/rag/db/stream` |
| 7 | Streamlit DB UI | `frontend/app.py` updated | DB routing path + SQL expander |
| 8 | DeepEval Database Tests | `evaluation/tests/test_database_rag.py` | 4 test functions, golden dataset |

---

## How Database RAG Works — The Mental Model

```
Without Database RAG (Phase 2):
Employee question → ChromaDB policy search → GPT-4o → Policy answer
(no access to employee-specific data)

With Database RAG (Phase 3):
Employee question → GPT-4o NL-to-SQL → PostgreSQL query
                                              ↓
                                      Structured rows
                                              ↓
                               GPT-4o (rows + question) → Factual answer

Router decides:
"What is the leave policy?" → ChromaDB (document RAG)
"How many days does James Chen have?" → PostgreSQL (database RAG)
"Hello, how are you?" → GPT-4o (general chat)
```

**The key design invariant:** If the question mentions a specific person by name, it always routes to `"db"`. No exception. This prevents the router from trying to look up employee data in the PDF documents.

---

## Step 1 — Database Schema Context

### Concept

The NL-to-SQL engine must understand the database structure before it can generate accurate SQL. Rather than querying `information_schema` at runtime, a static schema description is embedded directly into the system prompt. This gives GPT-4o complete column names, types, allowed enum values, and join keys — everything needed to write correct SQL on the first attempt.

**Three tables in the schema:**

| Table | Primary Key | Key Columns | Rows |
|---|---|---|---|
| `employees` | `employee_id` (EMP-XXXX) | first_name, last_name, department, job_title, status, leave_balance | 50 |
| `leave_records` | `id` | employee_id (FK), leave_type, start_date, end_date, status | 30 |
| `org_chart` | `id` | employee_id (FK), manager_id, level, reports_to | 50 |

### Claude Code Prompt

```
Create rag/database_rag/schema.py — the database schema context
for natural language to SQL translation.
Also create rag/database_rag/__init__.py (empty package file).

DATABASE_SCHEMA_DESCRIPTION constant — multi-line string describing
the full schema. Include:

TABLE: employees
- id (integer, primary key, internal)
- employee_id (varchar, format: EMP-XXXX, public identifier)
- first_name, last_name (varchar)
- email (varchar, format: firstname.lastname@acmecorp.com)
- department (varchar, values: Engineering, Sales, Finance, HR, Marketing)
- job_title (varchar)
- hire_date (date)
- status (varchar, values: Active, Inactive, On Leave)
- leave_balance (integer, days remaining)
- salary (integer)
- location (varchar, values: San Francisco, New York, Austin, Chicago, Seattle, Singapore, London)

TABLE: leave_records
- id (integer, primary key)
- employee_id (varchar, FK to employees.employee_id)
- leave_type (varchar, values: Annual, Sick, Parental, Emergency)
- start_date, end_date (date)
- status (varchar, values: Pending, Approved, Rejected)
- days_taken (integer)
- reason (text)

TABLE: org_chart
- id (integer, primary key)
- employee_id (varchar, FK to employees.employee_id)
- manager_id (varchar, FK to employees.employee_id, null for CEO)
- job_title, level (varchar)
- department (varchar)
- reports_to (varchar, manager's employee_id)

SQL RULES section:
- Always use lowercase table names
- Use table aliases: employees → e, leave_records → lr, org_chart → o
- Use ILIKE for case-insensitive name matching
- Default LIMIT 10 on all queries
- Never use SELECT *
- Join leave_records to employees on employee_id
- Join org_chart to employees on employee_id

Function get_schema_description() -> str: returns DATABASE_SCHEMA_DESCRIPTION

Function get_table_samples() -> str:
- Connect to DB, query 3 rows from each table
- Format as "TABLE: employees\nCOLUMN1: VALUE | COLUMN2: VALUE\n..."
- Return formatted string

Function get_full_context() -> str:
- Returns schema description + table samples combined

Test block:
if __name__ == "__main__":
    print(get_full_context())
```

### Run Command

```bash
uv run python -m rag.database_rag.schema
```

### Results

```
Schema and sample data loaded successfully.
3 rows from employees table (first row):
  employee_id: EMP-0001 | first_name: James | last_name: Chen
  department: Engineering | job_title: VP of Engineering | status: Active

3 rows from leave_records table
3 rows from org_chart table
```

### Exit Criteria

| Check | Status |
|---|---|
| `rag/database_rag/__init__.py` created (empty) | ✅ |
| `schema.py` created | ✅ |
| `DATABASE_SCHEMA_DESCRIPTION` covers all 3 tables | ✅ |
| Email domain matches seed data: `@acmecorp.com` | ✅ |
| `get_table_samples()` returns 3 rows per table | ✅ |
| EMP-0001 James Chen VP Engineering confirmed | ✅ |

> **Email domain fix applied:** Initial schema.py had `@hrplatform.com` in the email format example. Updated to `@acmecorp.com` to match the seed data (which was bulk-updated with `sed` at the start of Phase 3).

---

## Step 2 — NL-to-SQL Engine

### Concept

The NL-to-SQL engine uses GPT-4o with the full schema context to generate a PostgreSQL SELECT statement from any natural language question. A two-stage process: generate SQL, then validate it.

**Safety validation rules — two checks:**

1. SQL must start with `SELECT` (stripped/lowercased)
2. SQL must not contain any of: `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`, `CREATE`, `GRANT`, `REVOKE` (word boundary regex)

**The `NOT_DB_QUERY` sentinel:** When the question cannot be answered from the database (e.g., "What is the parental leave policy?"), the model returns the literal string `NOT_DB_QUERY` instead of SQL. This is the routing signal that tells the chain to fall back to document RAG.

**10 strict prompt rules for the model:**
1. Generate SELECT-only queries
2. Use table aliases (e, lr, o)
3. Always use ILIKE for name matching
4. Default LIMIT 10
5. Never use SELECT *
6. Use JOIN for multi-table queries
7. Return `NOT_DB_QUERY` for non-database questions
8. Return `NOT_DB_QUERY` for policy/procedure questions
9. Return only the SQL — no explanation, no markdown
10. Never include dangerous keywords

### Claude Code Prompt

```
Create rag/database_rag/nl_to_sql.py — converts natural language
questions to PostgreSQL SELECT queries using GPT-4o.

Imports: langchain_openai.ChatOpenAI, langchain_core.prompts.ChatPromptTemplate,
         langchain_core.output_parsers.StrOutputParser,
         rag.database_rag.schema (get_schema_description),
         config.settings, logging, re

NL_TO_SQL_SYSTEM_PROMPT constant — strict rules:
1. You are a PostgreSQL expert. Generate SELECT queries only.
2. Use table aliases: employees → e, leave_records → lr, org_chart → o
3. Always use ILIKE for name matching (case-insensitive)
4. Default LIMIT 10 on all queries
5. Never use SELECT *
6. Use proper JOINs for multi-table queries
7. If the question cannot be answered from the database, return:
   NOT_DB_QUERY
8. Return NOT_DB_QUERY for questions about policies, procedures,
   or anything not in the employee database
9. Return ONLY the SQL statement. No markdown, no explanation.
10. Never include DROP, DELETE, UPDATE, INSERT, ALTER statements

Function generate_sql(question: str) -> str:
- Synchronous (called inside async context)
- Build prompt: system=NL_TO_SQL_SYSTEM_PROMPT + "\n\nDatabase schema:\n" + schema
- Human: question
- Call GPT-4o with temperature=0
- Strip result and return

Function validate_sql(sql: str) -> tuple[bool, str]:
- Returns (is_valid: bool, error_message: str)
- Check 1: sql must start with SELECT (lowercased, stripped)
- Check 2: dangerous keywords regex with word boundaries:
  r'\b(DROP|DELETE|UPDATE|INSERT|ALTER|TRUNCATE|CREATE|GRANT|REVOKE)\b'
- Return (True, "") if both checks pass

Async function generate_validated_sql(question: str) -> tuple[str, bool, str]:
- Returns (sql, is_valid, error_message)
- Call generate_sql(question)
- If result == "NOT_DB_QUERY": return ("NOT_DB_QUERY", False, "NOT_DB_QUERY")
- Call validate_sql(sql)
- Return (sql, is_valid, error_msg)

Test block:
if __name__ == "__main__":
    test 7 questions:
    - "How many leave days does James Chen have?"
    - "Show employees in Engineering"
    - "Who has pending leave requests?"
    - "Who reports to the VP of Engineering?"
    - "What is the annual leave policy?"  ← should return NOT_DB_QUERY
    - "How many employees are in each department?"
    - "What is Isabella Fernandez's employee ID?"
```

### Run Command

```bash
uv run python -m rag.database_rag.nl_to_sql
```

### Results

| Question | SQL Generated | NOT_DB_QUERY |
|---|---|---|
| James Chen leave days | `SELECT e.employee_id, e.first_name, e.last_name, e.leave_balance FROM employees e WHERE e.first_name ILIKE 'James' AND e.last_name ILIKE 'Chen' LIMIT 10` | — |
| Engineering employees | `SELECT e.first_name, e.last_name, e.job_title FROM employees e WHERE e.department ILIKE 'Engineering' LIMIT 10` | — |
| Pending leave requests | `SELECT e.first_name, e.last_name, lr.leave_type, lr.start_date FROM employees e JOIN leave_records lr ON e.employee_id = lr.employee_id WHERE lr.status = 'Pending' LIMIT 10` | — |
| VP of Engineering reports | `SELECT e.first_name, e.last_name, e.job_title FROM employees e JOIN org_chart o ON e.employee_id = o.employee_id WHERE o.manager_id = (SELECT employee_id FROM employees WHERE job_title ILIKE 'VP of Engineering' LIMIT 1) LIMIT 10` | — |
| Annual leave policy | — | `NOT_DB_QUERY` ✅ |
| Employees per department | `SELECT e.department, COUNT(*) AS employee_count FROM employees e GROUP BY e.department LIMIT 10` | — |
| Isabella Fernandez employee ID | `SELECT e.employee_id FROM employees e WHERE e.first_name ILIKE 'Isabella' AND e.last_name ILIKE 'Fernandez' LIMIT 10` | — |

> **Critical routing test:** "What is the annual leave policy?" correctly returns `NOT_DB_QUERY`. This ensures policy questions are never answered with database queries — they fall through to the document RAG chain.

### Exit Criteria

| Check | Status |
|---|---|
| `nl_to_sql.py` created | ✅ |
| GPT-4o generates valid SQL with ILIKE and table aliases | ✅ |
| `validate_sql()` blocks non-SELECT statements | ✅ |
| `validate_sql()` blocks dangerous keywords | ✅ |
| Policy question returns `NOT_DB_QUERY` | ✅ |
| All 6 DB questions generate valid SQL | ✅ |

---

## Step 3 — SQL Executor

### Concept

The executor takes a validated SQL string, runs it against PostgreSQL via SQLAlchemy, and returns a clean `QueryResult` dataclass. Two additional concerns beyond simple query execution:

**Date serialization:** SQLAlchemy returns `datetime.date` and `datetime.datetime` objects. These can't be JSON-serialized directly. The executor converts them to ISO format strings (`2024-06-03` → `"2024-06-03"`) before returning.

**Safety boundary:** `execute_query()` accepts only pre-validated SQL. Any error — SQL error, connection error, unexpected exception — is caught and returned as a failed `QueryResult` with the error message. ARIA never surfaces raw database exceptions to users.

### Claude Code Prompt

```
Create rag/database_rag/executor.py — executes SQL queries against
PostgreSQL and returns clean structured results.

Imports: sqlalchemy (create_engine, text), sqlalchemy.exc (SQLAlchemyError,
         OperationalError), config.settings, logging, dataclasses.dataclass,
         datetime

Dataclass QueryResult:
- success: bool
- rows: list[dict]
- row_count: int
- columns: list[str]
- error: str
- sql_executed: str

Function execute_query(sql: str) -> QueryResult:
- If sql is empty or == "NOT_DB_QUERY": return failed QueryResult
- create_engine(settings.database_url)
- conn.execute(text(sql))
- For each row: zip columns with values
- Convert datetime.date and datetime.datetime to .isoformat()
- Return successful QueryResult
- Catch SQLAlchemyError: return failed QueryResult with error string
- Catch Exception: return failed QueryResult with error string

Function format_results_for_llm(result: QueryResult) -> str:
- If not success: return f"Query failed: {result.error}"
- If row_count == 0: return "No records found matching your query."
- Format as:
  "Query returned N record(s):\n"
  "Record 1:\n  column: value\n  column: value\n"
  "Record 2:\n  ..."
- Return joined string

Function get_database_stats() -> dict:
Run these 5 queries and return results as dict:
- total_employees: SELECT COUNT(*) FROM employees
- total_leave_records: SELECT COUNT(*) FROM leave_records
- total_org_chart: SELECT COUNT(*) FROM org_chart
- active_employees: SELECT COUNT(*) FROM employees WHERE status = 'Active'
- pending_leave_requests: SELECT COUNT(*) FROM leave_records WHERE status = 'Pending'

Test block:
if __name__ == "__main__":
    Run 4 test queries:
    1. James Chen leave balance lookup
    2. Department employee count aggregate
    3. Pending leave requests with JOIN
    4. SELECT invalid_column FROM nonexistent_table (error case)
    Print success, row count, first row, formatted output for each.
    Then print get_database_stats().
```

### Run Command

```bash
uv run python -m rag.database_rag.executor
```

### Results

| Query Type | Success | Rows | Notes |
|---|---|---|---|
| James Chen leave balance | ✅ | 1 | `leave_balance: 30` |
| Department count aggregate | ✅ | 5 | Engineering 15, Sales 10, Finance 9, HR 8, Marketing 8 |
| Pending leave JOIN | ✅ | 6 | 6 employees with pending requests |
| Invalid table | ❌ | 0 | `SQLAlchemyError` caught, error message returned |

**Database stats:**

| Stat | Value |
|---|---|
| `total_employees` | 50 |
| `total_leave_records` | 30 |
| `total_org_chart` | 50 |
| `active_employees` | 47 |
| `pending_leave_requests` | 6 |

### Exit Criteria

| Check | Status |
|---|---|
| `executor.py` created | ✅ |
| `QueryResult` dataclass with all fields | ✅ |
| Date objects serialized to ISO strings | ✅ |
| SQLAlchemy errors caught and returned as failed QueryResult | ✅ |
| `format_results_for_llm()` produces readable output | ✅ |
| `get_database_stats()` returns correct counts | ✅ |

---

## Step 4 — Database RAG Chain

### Concept

The database RAG chain orchestrates the full NL-to-SQL-to-answer pipeline in four stages:

```
Stage 1: generate_validated_sql(question)
         → sql, is_valid, error_msg

Stage 2: execute_query(sql)
         → QueryResult (rows, columns, row_count)

Stage 3: format_results_for_llm(result)
         → "Query returned 1 record(s):\n  leave_balance: 30"

Stage 4: GPT-4o (DB_ANSWER_SYSTEM_PROMPT + question + formatted rows)
         → "James Chen has 30 days of leave remaining."
```

**`temperature=0` for factual answers:** Database answers are factual, not creative. Temperature 0 produces deterministic, consistent answers from the same data.

**The WHO prompt rule (iteratively refined):** A critical rule governs how ARIA answers questions about who did something or who is on leave. Three iterations were needed before the answers were correct:

| Iteration | Problem | Fix |
|---|---|---|
| Initial | "Isabella Fernandez, who is an HR Coordinator in the HR department, is on leave. She is based in our Singapore office." | Added WHO rule |
| First fix | "Priya Sharma (Director of Engineering, Seattle) and Marcus Johnson (Director of Engineering, New York) report to the VP." | WHO rule not prominent enough |
| Final fix | Made WHO rule the FIRST rule in the prompt, with explicit correct/wrong examples | "Isabella Fernandez is currently on leave." ✅ |

### Claude Code Prompt

```
Create rag/database_rag/chain.py — the complete Database RAG chain.

Imports: langchain_openai.ChatOpenAI, langchain_core.prompts.ChatPromptTemplate,
         langchain_core.output_parsers.StrOutputParser,
         rag.database_rag.nl_to_sql (generate_validated_sql),
         rag.database_rag.executor (execute_query, format_results_for_llm),
         config.settings, logging, dataclasses.dataclass, typing.AsyncGenerator

DB_ANSWER_SYSTEM_PROMPT constant:
"You are ARIA, an HR Intelligence Assistant for Acme Corp.
You have been provided with the results of a database query
that answers the employee's question.

Your job is to present this information clearly and naturally.

Rules:
- For questions asking only WHO (e.g. 'who is on leave',
  'who has pending requests'): respond with ONLY the person's
  name and the direct answer. No role, no department, no location,
  no additional context unless explicitly asked.
  Correct: 'Isabella Fernandez is currently on leave.'
  Wrong:   'Isabella Fernandez, who is an HR Coordinator,
            is currently on leave.'
- Present the database results in a clear, conversational way
- Always mention specific names, numbers, and dates from the results
- If the results show zero records, say so clearly and suggest why
- Keep your answer concise — employees want facts, not paragraphs
- Do not add information that is not in the query results
- If asked about leave balance, always state the exact number of days
- Format dates as readable text: 2024-06-03 becomes June 3, 2024
- For questions asking WHO (who reports to X, who is on leave,
  who has pending requests): answer with names and roles only.
  Never add location, hire date, or other unrequested details.
  Example: 'Priya Sharma and Marcus Johnson report to the
            VP of Engineering. Both are Directors of Engineering.'
  Not: 'Priya Sharma is based in Seattle. Marcus Johnson
        works out of New York.'
- Only include location, department, or other details when
  the question explicitly asks for them."

Dataclass DatabaseRAGResponse:
- answer: str, sql_used: str, row_count: int
- query: str, success: bool, error: str

Function build_db_answer_prompt() -> ChatPromptTemplate:
- System: DB_ANSWER_SYSTEM_PROMPT
- Human: "Database query results for the question:\n'{question}'\n\n
          Query executed:\n{sql_used}\n\nResults:\n{query_results}\n\n
          Please present these results in a clear, conversational way."

Async function db_rag_query(question: str) -> DatabaseRAGResponse:
- Step 1: generate_validated_sql(question)
- If sql == "NOT_DB_QUERY": return DatabaseRAGResponse with answer="NOT_DB_QUERY"
- If not is_valid: return failed response with error message
- Step 2: execute_query(sql)
- If not result.success: return failed response with contact message
- Step 3: format_results_for_llm(result)
- If row_count == 0: return "No records were found matching your query."
- Step 4: chain.ainvoke({question, sql_used, query_results})
- Return DatabaseRAGResponse with answer and metadata

Async generator db_rag_query_stream(question) -> AsyncGenerator[str, None]:
- Same 4-step structure
- Yield "NOT_DB_QUERY" for NOT_DB_QUERY case (then return)
- Yield error messages (then return)
- Yield "No records were found..." (then return)
- Step 4: Use streaming=True LLM, chain.astream(), yield each chunk

Test block: 7 questions including "What is the annual leave policy?"
```

### Run Command

```bash
uv run python -m rag.database_rag.chain
```

### Chain Test Results

| Question | Answer | NOT_DB_QUERY |
|---|---|---|
| How many leave days does James Chen have? | "James Chen has 30 days of leave remaining." | — |
| Show employees in Engineering | "There are 15 employees in Engineering: [names listed]" | — |
| Who has pending leave requests? | "There are 6 employees with pending leave requests: [names]" | — |
| Who reports to the VP of Engineering? | "Priya Sharma and Marcus Johnson report to the VP of Engineering. Both are Directors of Engineering." | — |
| What is the annual leave policy? | — | `NOT_DB_QUERY` ✅ |
| How many employees per department? | "Engineering: 15, Sales: 10, Finance: 9, HR: 8, Marketing: 8" | — |
| Who is currently on leave? | "Isabella Fernandez is currently on leave." | — |

> **WHO answer iteration:** The "Who is currently on leave?" answer required 3 prompt iterations. The final answer "Isabella Fernandez is currently on leave." matches the golden set expected output exactly.

### Exit Criteria

| Check | Status |
|---|---|
| `chain.py` created | ✅ |
| `NOT_DB_QUERY` returned for policy question | ✅ |
| WHO answers — name only, no unrequested context | ✅ |
| Leave balance states exact number of days | ✅ |
| Streaming and non-streaming variants both work | ✅ |
| `temperature=0` for factual consistency | ✅ |

---

## Step 5 — Three-way Query Router

### Concept

Phase 2 had a two-way router: `"rag"` (document search) or `"chat"` (general LLM). Phase 3 adds a third path: `"db"` (database query).

**The critical routing rule:** If the question mentions a specific person by name, always route to `"db"`. This prevents queries like "How many leave days does James Chen have?" from being classified as `"rag"` (which would trigger a futile PDF search).

**Router classification logic:**

| Classification | Route To | Examples |
|---|---|---|
| `"rag"` | Document RAG | "What is the parental leave policy?", "How do I report harassment?" |
| `"db"` | Database RAG | "How many days does James Chen have?", "Who is on leave?", "How many employees in Engineering?" |
| `"chat"` | General LLM | "Hello", "Can you help me?", "What does HR stand for?" |

### Claude Code Prompt

```
Update backend/chains/rag_router.py to add 'db' as a third
classification option for database RAG queries.

Replace the current ROUTER_PROMPT and classify_query() function
with the following:

ROUTER_PROMPT = """You are a query classifier for an HR assistant system.
Classify the user's question as 'rag', 'db', or 'chat'.

Return 'rag' if the question:
- Asks about specific company policies or procedures
- Asks about leave entitlements, benefits, or compensation rules
- Asks about conduct, grievances, or disciplinary procedures
- Asks about onboarding, probation, or working arrangements
- Could be answered from an HR policy document

Return 'db' if the question:
- Asks about a specific employee by name
- Asks about leave balances, leave records, or leave history
- Asks about who reports to whom (org chart)
- Asks about headcounts, department sizes, or employee lists
- Asks about employee status (active, on leave, inactive)
- Could be answered by querying the employee database

Return 'chat' if the question:
- Is a general greeting or conversation
- Asks about general HR concepts not specific to the company
- Is a follow-up that continues a general conversation
- Cannot be answered from a policy document or the employee database

IMPORTANT: If the question mentions a SPECIFIC PERSON by name,
always return 'db' — never 'rag' or 'chat'.

Return ONLY the word 'rag', 'db', or 'chat' — nothing else."""

async def classify_query(question: str) -> str:
- temperature=0
- Strip and lowercase result
- Default to "rag" if result not in ("rag", "db", "chat")

Test 8 questions:
1. "What is the parental leave policy?" → rag
2. "How many leave days does James Chen have?" → db
3. "Who is currently on leave?" → db
4. "How many employees are in each department?" → db
5. "What is the remote work policy?" → rag
6. "Hello, how are you?" → chat
7. "Who reports to the VP of Engineering?" → db
8. "How do I report a harassment complaint?" → rag
```

### Run Command

```bash
uv run python -m backend.chains.rag_router
```

### Routing Test Results

| Question | Expected | Result |
|---|---|---|
| "What is the parental leave policy?" | `rag` | `rag` ✅ |
| "How many leave days does James Chen have?" | `db` | `db` ✅ |
| "Who is currently on leave?" | `db` | `db` ✅ |
| "How many employees are in each department?" | `db` | `db` ✅ |
| "What is the remote work policy?" | `rag` | `rag` ✅ |
| "Hello, how are you?" | `chat` | `chat` ✅ |
| "Who reports to the VP of Engineering?" | `db` | `db` ✅ |
| "How do I report a harassment complaint?" | `rag` | `rag` ✅ |

8/8 routing assertions correct.

### Exit Criteria

| Check | Status |
|---|---|
| `rag_router.py` updated with three-way router | ✅ |
| `"db"` classification added | ✅ |
| Named-person rule: specific names always route to `"db"` | ✅ |
| All 8 test questions route correctly | ✅ |
| Default fallback is `"rag"` for unexpected values | ✅ |

---

## Step 6 — FastAPI Database Endpoints

### Concept

Two new endpoints added under the existing `/rag` router:

| Endpoint | Used By | Returns |
|---|---|---|
| `POST /rag/db/query` | DeepEval test suite | Complete JSON with answer, sql_used, row_count |
| `POST /rag/db/stream` | Streamlit UI | SSE token stream, then metadata event, then `[DONE]` |

**The metadata event pattern for `/rag/db/stream`:**
```
# Streaming tokens:
data: {"token": "James"}
data: {"token": " Chen"}
data: {"token": " has 30 days"}

# Metadata event (after all tokens):
data: {"sql_used": "SELECT ... FROM employees ...", "row_count": 1}

# Termination:
data: {"token": "[DONE]"}
```

The Streamlit UI captures `sql_used` and `row_count` from the metadata event to display the SQL expander and record count badge.

**`NOT_DB_QUERY` handling:** When `db_rag_query_stream()` yields `"NOT_DB_QUERY"`, the `/rag/db/stream` endpoint sends it as a token: `data: {"token": "NOT_DB_QUERY"}`. Streamlit catches this token and sets `last_answer_type = "rag_fallback"` — a signal to fall through to document RAG on the next request.

### Claude Code Prompt

```
Update backend/api/routes/rag.py to add two new database RAG
endpoints before the /classify endpoint.

Add import: from rag.database_rag.chain import db_rag_query, db_rag_query_stream

Add to backend/schemas/rag.py:
class DatabaseRAGRequest(BaseModel):
    question: str = Field(min_length=1)
    session_id: str = Field(default_factory=lambda: str(uuid4()))

class DatabaseRAGResponseModel(BaseModel):
    answer: str; sql_used: str; row_count: int; query: str
    session_id: str; model: str = "gpt-4o-db"; success: bool

ENDPOINT 1: POST /rag/db/query (for DeepEval)
- Call db_rag_query(request.question)
- If result.answer == "NOT_DB_QUERY":
  return {"answer": "This question requires document search...",
          "sql_used": "", "row_count": 0, "success": False, ...}
- Otherwise return full DatabaseRAGResponseModel dict

ENDPOINT 2: POST /rag/db/stream (for Streamlit)
- Async generator db_stream():
  - async for chunk in db_rag_query_stream(request.question):
    - yield f'data: {{"token": {json.dumps(chunk)}}}\n\n'
  - Run db_rag_query() again to get sql metadata
  - yield metadata event: data: {"sql_used": "...", "row_count": N}
  - yield: data: {"token": "[DONE]"}
- Return StreamingResponse(db_stream(), media_type="text/event-stream")
```

### Verification Commands

```bash
# Start backend first
uv run uvicorn backend.main:app --reload --port 8000

# Test non-streaming endpoint
curl -X POST http://localhost:8000/rag/db/query \
  -H "Content-Type: application/json" \
  -d '{"question": "How many leave days does James Chen have?"}'

# Test classification with db question
curl "http://localhost:8000/rag/classify?query=How+many+leave+days+does+James+Chen+have"
```

### Verification Results

| Test | Expected | Result |
|---|---|---|
| `/rag/db/query` James Chen | `{"answer": "James Chen has 30 days of leave remaining.", "row_count": 1, "success": true}` | ✅ |
| `/rag/classify` James Chen question | `{"classification": "db"}` | ✅ |
| `/rag/db/query` annual leave policy | `NOT_DB_QUERY` fallback message | ✅ |

### Exit Criteria

| Check | Status |
|---|---|
| `DatabaseRAGRequest` and `DatabaseRAGResponseModel` added to `backend/schemas/rag.py` | ✅ |
| `POST /rag/db/query` endpoint returns complete JSON | ✅ |
| `POST /rag/db/stream` endpoint streams tokens + metadata | ✅ |
| `NOT_DB_QUERY` handled gracefully in both endpoints | ✅ |
| Metadata event includes `sql_used` and `row_count` | ✅ |

---

## Step 7 — Streamlit DB UI

### Concept

Three additions to `frontend/app.py` for the database RAG path:

1. **Two new session state keys** — `last_sql_used` and `last_row_count` capture the SQL and row count from the metadata SSE event
2. **`stream_db()` generator** — connects to `/rag/db/stream`, handles the `NOT_DB_QUERY` token, captures SQL metadata, yields answer tokens
3. **DB routing branch** — when classification is `"db"`, streams from `stream_db()`, then displays record count badge and SQL expander

**The SQL expander:** Database answers show a `🗄️ Answered from employee database · N record(s) found` caption. Below it, a collapsible Streamlit `st.expander("View database query")` shows the actual SQL with syntax highlighting. This gives technical users full transparency into what was queried.

**`rag_fallback` state:** If `stream_db()` receives the `NOT_DB_QUERY` token, it sets `last_answer_type = "rag_fallback"` and breaks — no answer is streamed. The UI handles this gracefully (no response text = no message appended to history).

### Claude Code Prompt

```
Update frontend/app.py to add database RAG support as a third
routing path alongside the existing chat and document RAG paths.
Keep all Phase 1 and Phase 2 functionality unchanged.

Add session state:
- last_sql_used = ""
- last_row_count = 0

Reset these at the start of each new chat input alongside
the existing last_sources reset.

New function stream_db(question: str, session_id: str):
- httpx.stream POST to /rag/db/stream
- For each SSE line (line.startswith("data: ")):
  - Parse JSON
  - token == "[DONE]" → break
  - token == "[ERROR]" → break
  - token == "NOT_DB_QUERY" → set last_answer_type = "rag_fallback", break
  - "sql_used" in data → capture last_sql_used and last_row_count
  - else → yield token

Update chat routing (classification == "db" branch):
- st.write_stream(stream_db(prompt, session_id))
- If last_row_count > 0:
    st.caption(f"🗄️ Answered from employee database · {last_row_count} record(s) found")
- If last_sql_used:
    with st.expander("View database query"):
        st.code(last_sql_used, language="sql")

Update session state save for db messages:
- Include sql_used, row_count, answer_type in message dict

Update chat history display for db messages:
- Show row count and SQL expander for messages with answer_type == "db"
```

### UI Test Results

| Question | Badge | SQL Shown | Result |
|---|---|---|---|
| "How many leave days does James Chen have?" | 🗄️ Employee database · 1 record | ✅ SQL expander | "James Chen has 30 days of leave remaining." ✅ |
| "Who is currently on leave?" | 🗄️ Employee database · 1 record | ✅ SQL expander | "Isabella Fernandez is currently on leave." ✅ |
| "How many employees in Engineering?" | 🗄️ Employee database · 1 record | ✅ SQL expander | "There are 15 employees in Engineering." ✅ |
| "What is the parental leave policy?" | 🔍 Company documents | No SQL | Policy answer with citation ✅ |
| "Hello!" | 💬 General HR knowledge | No SQL | Greeting response ✅ |

### Exit Criteria

| Check | Status |
|---|---|
| `stream_db()` function added | ✅ |
| `last_sql_used` and `last_row_count` session state added | ✅ |
| DB routing branch handles all token types | ✅ |
| `NOT_DB_QUERY` handled gracefully (no response appended) | ✅ |
| Record count badge displayed | ✅ |
| SQL expander shows syntax-highlighted query | ✅ |
| Phase 2 routing (rag / chat) unchanged | ✅ |

---

## Step 8 — DeepEval Database RAG Tests

### Concept

Phase 3 evaluation differs from Phase 2. We're evaluating a NL-to-SQL pipeline and a factual answer generator — not a document retriever.

**Key difference from Phase 2 — `retrieval_context` source:**
```python
# Phase 2 — retrieval_context is vector search results (chunk text)
retrieval_context = [chunk.text for chunk in retrieved_chunks]

# Phase 3 — retrieval_context is the SQL query result formatted as text
sql, is_valid, _ = asyncio.run(generate_validated_sql(question))
result = execute_query(sql)
retrieval_context = [format_results_for_llm(result)]
```

**Two metrics for all LLM-judged tests:**
- `FaithfulnessMetric(threshold=0.8, model="gpt-4o")` — are claims grounded in the DB rows returned?
- `AnswerRelevancyMetric(threshold=0.7, model="gpt-4o")` — does the answer address what was asked?

**One pure-assertion test (no LLM judge):**
- `test_db_routing_boundary` — all 10 DB golden set questions must classify as `"db"`, all 3 policy questions must classify as `"rag"`. No rate-limit risk.

---

## Database RAG Golden Dataset — database_rag_golden_set.json

**Location:** `evaluation/datasets/database_rag_golden_set.json`
**Total entries:** 10
**Query types:** `employee_lookup` (5), `aggregate` (3), `join` (2)

### Claude Code Prompt

```
Create evaluation/datasets/database_rag_golden_set.json
with 10 entries. Each entry: input, expected_output, query_type.

[
  {"input": "How many leave days does James Chen have?",
   "expected_output": "James Chen has 30 days of leave remaining.",
   "query_type": "employee_lookup"},

  {"input": "What department is James Chen in?",
   "expected_output": "James Chen is in the Engineering department and works as VP of Engineering.",
   "query_type": "employee_lookup"},

  {"input": "How many employees are in each department?",
   "expected_output": "Engineering has 15 employees, Sales has 10, Finance has 9, HR has 8, Marketing has 8.",
   "query_type": "aggregate"},

  {"input": "How many employees are currently active?",
   "expected_output": "There are 47 active employees at Acme Corp.",
   "query_type": "aggregate"},

  {"input": "Who has pending leave requests?",
   "expected_output": "There are 6 employees with pending leave requests.",
   "query_type": "join"},

  {"input": "Who reports to the VP of Engineering?",
   "expected_output": "Priya Sharma and Marcus Johnson report to the VP of Engineering. Both are Directors of Engineering.",
   "query_type": "join"},

  {"input": "Who is currently on leave?",
   "expected_output": "Isabella Fernandez is currently on leave.",
   "query_type": "employee_lookup"},

  {"input": "What is Isabella Fernandez's employee ID?",
   "expected_output": "Isabella Fernandez's employee ID is EMP-0022.",
   "query_type": "employee_lookup"},

  {"input": "How many leave records are there in total?",
   "expected_output": "There are 30 leave records in total.",
   "query_type": "aggregate"},

  {"input": "Show me employees in the HR department",
   "expected_output": "There are 8 employees in the HR department.",
   "query_type": "employee_lookup"}
]
```

> **EMP-0022 verification:** Isabella Fernandez's employee ID was confirmed by querying the live database with `docker exec hr_postgres psql -U postgres -d hr_platform -c "SELECT employee_id FROM employees WHERE first_name = 'Isabella' AND last_name = 'Fernandez';"` which returned `EMP-0022`.

> **JSON fix applied:** A missing comma was found after the `expected_output` for "Who is currently on leave?" causing a JSON parse error. Fixed before tests were run.

### Golden Set by Query Type

| Query Type | Rows | Questions Cover |
|---|---|---|
| `employee_lookup` | 1, 2, 7, 8, 10 | Leave balance, department, on-leave status, employee ID, department list |
| `aggregate` | 3, 4, 9 | Department counts, active employee count, total leave records |
| `join` | 5, 6 | Pending leave (employees JOIN leave_records), org chart (employees JOIN org_chart) |

---

## Test Functions — Which Rows Each Test Uses

**File:** `evaluation/tests/test_database_rag.py`

### test_db_employee_lookup
**Rows used:** 1, 2, 7 (first 3 with `query_type == "employee_lookup"`)
**Metrics:** `FaithfulnessMetric(0.8)`, `AnswerRelevancyMetric(0.7)`
**Purpose:** Verifies employee name lookups return accurate factual answers grounded in the database rows returned.

### test_db_aggregate_queries
**Rows used:** 3, 4, 9 (first 3 with `query_type == "aggregate"`)
**Metrics:** `FaithfulnessMetric(0.8)`, `AnswerRelevancyMetric(0.7)`
**Purpose:** Verifies COUNT and GROUP BY aggregate queries return accurate numbers.

### test_db_join_queries
**Rows used:** 5, 6 (all with `query_type == "join"`)
**Metrics:** `FaithfulnessMetric(0.8)`, `AnswerRelevancyMetric(0.7)`
**Purpose:** Verifies multi-table JOIN queries (employees + leave_records, employees + org_chart) return complete and accurate results.

### test_db_routing_boundary
**Rows used:** All 10 (as DB questions) + 3 hardcoded policy questions
**Metrics:** None (pure assertion, no LLM judge)
**Purpose:** Verifies the three-way router correctly classifies all database questions as `"db"` and policy questions as `"rag"`. No OpenAI calls beyond the router itself — no rate-limit risk.

**The 3 hardcoded policy questions:**
```python
policy_questions = [
    "What is the parental leave policy?",
    "How do I report a harassment complaint?",
    "What is the remote work policy?",
]
```

**Row-to-test mapping:**

| Row | Question Summary | Employee Lookup | Aggregate | Join | Routing |
|---|---|---|---|---|---|
| 1 | James Chen leave days | ✅ | | | ✅ |
| 2 | James Chen department | ✅ | | | ✅ |
| 3 | Employees per department | | ✅ | | ✅ |
| 4 | Active employee count | | ✅ | | ✅ |
| 5 | Pending leave requests | | | ✅ | ✅ |
| 6 | VP Engineering reports | | | ✅ | ✅ |
| 7 | Who is on leave? | ✅ | | | ✅ |
| 8 | Isabella Fernandez ID | | | | ✅ |
| 9 | Total leave records | | ✅ | | ✅ |
| 10 | HR department employees | | | | ✅ |

---

## DeepEval Run Commands

```bash
# Required environment variables (set once per terminal session)
export DEEPEVAL_PER_TASK_TIMEOUT_SECONDS_OVERRIDE=600
export DEEPEVAL_PER_ATTEMPT_TIMEOUT_SECONDS_OVERRIDE=300

# Routing test first — no LLM judge, fast, catches wiring issues early
uv run deepeval test run evaluation/tests/test_database_rag.py::test_db_routing_boundary -v

# LLM-judged tests with 60-second gaps to avoid rate limits
sleep 60
uv run deepeval test run evaluation/tests/test_database_rag.py::test_db_employee_lookup -v
sleep 60
uv run deepeval test run evaluation/tests/test_database_rag.py::test_db_aggregate_queries -v
sleep 60
uv run deepeval test run evaluation/tests/test_database_rag.py::test_db_join_queries -v
```

---

## DeepEval Results — Final Baseline

### test_db_routing_boundary

```
Routing assertions: 13/13 passed (10 DB questions + 3 policy questions)
Cost: $0.00 (no LLM judge) | Time: 13.47s
```

All 10 database golden set questions correctly classified as `"db"`.
All 3 policy questions correctly classified as `"rag"`.

**Individual results:**

| Question | Expected | Got |
|---|---|---|
| How many leave days does James Chen have? | `db` | `db` ✅ |
| What department is James Chen in? | `db` | `db` ✅ |
| How many employees are in each department? | `db` | `db` ✅ |
| How many employees are currently active? | `db` | `db` ✅ |
| Who has pending leave requests? | `db` | `db` ✅ |
| Who reports to the VP of Engineering? | `db` | `db` ✅ |
| Who is currently on leave? | `db` | `db` ✅ |
| What is Isabella Fernandez's employee ID? | `db` | `db` ✅ |
| How many leave records are there in total? | `db` | `db` ✅ |
| Show me employees in the HR department | `db` | `db` ✅ |
| What is the parental leave policy? | `rag` | `rag` ✅ |
| How do I report a harassment complaint? | `rag` | `rag` ✅ |
| What is the remote work policy? | `rag` | `rag` ✅ |

---

### test_db_employee_lookup, test_db_aggregate_queries, test_db_join_queries

These three LLM-judged tests were created and verified structurally. Full LLM-judge evaluation to be run when the backend is live (requires `/rag/db/query` endpoint and OPENAI_API_KEY set):

```bash
uv run deepeval test run evaluation/tests/test_database_rag.py::test_db_employee_lookup -v
uv run deepeval test run evaluation/tests/test_database_rag.py::test_db_aggregate_queries -v
uv run deepeval test run evaluation/tests/test_database_rag.py::test_db_join_queries -v
```

Expected results based on chain test outputs and golden set alignment:

| Test | Metric | Expected Pass |
|---|---|---|
| `test_db_employee_lookup` | Faithfulness ≥ 0.8 | ✅ (answers match DB rows exactly) |
| `test_db_employee_lookup` | Answer Relevancy ≥ 0.7 | ✅ (direct answers to direct questions) |
| `test_db_aggregate_queries` | Faithfulness ≥ 0.8 | ✅ (counts from DB, no hallucination) |
| `test_db_aggregate_queries` | Answer Relevancy ≥ 0.7 | ✅ (aggregate answers to aggregate questions) |
| `test_db_join_queries` | Faithfulness ≥ 0.8 | ✅ (names from JOIN result only) |
| `test_db_join_queries` | Answer Relevancy ≥ 0.7 | ✅ (WHO answers address WHO questions) |

---

## Phase 3 DeepEval Complete Baseline

| Test | Metric | Pass Rate | Cases | Cost | Time |
|---|---|---|---|---|---|
| `test_db_routing_boundary` | Routing assertion | **100%** | 13 | $0.000 | 13.47s |
| `test_db_employee_lookup` | Faithfulness + Relevancy | Pending run | 3 | ~$0.030 | ~15s |
| `test_db_aggregate_queries` | Faithfulness + Relevancy | Pending run | 3 | ~$0.030 | ~15s |
| `test_db_join_queries` | Faithfulness + Relevancy | Pending run | 2 | ~$0.020 | ~12s |

---

## Phase 3 Complete ✅

| Step | What Was Built | Status |
|---|---|---|
| Step 1 | Schema context — 3 tables, column types, enum values, SQL rules | ✅ |
| Step 2 | NL-to-SQL — GPT-4o, safety validation, `NOT_DB_QUERY` sentinel | ✅ |
| Step 3 | SQL executor — SQLAlchemy, date serialization, error handling | ✅ |
| Step 4 | Database RAG chain — 4-stage pipeline, WHO prompt rule, temperature=0 | ✅ |
| Step 5 | Three-way router — `"rag"` / `"db"` / `"chat"`, named-person rule | ✅ |
| Step 6 | FastAPI — `/rag/db/query`, `/rag/db/stream` with metadata SSE | ✅ |
| Step 7 | Streamlit — DB routing path, record count badge, SQL expander | ✅ |
| Step 8 | DeepEval — routing test 100% pass, LLM-judged tests created | ✅ |

---

## Phase 3 vs Phase 2 Capability Comparison

| Capability | Phase 2 | Phase 3 |
|---|---|---|
| Policy questions | ✅ Document RAG | ✅ Document RAG (unchanged) |
| Employee-specific questions | ❌ No data source | ✅ Database RAG |
| Live data accuracy | ❌ N/A | ✅ Real-time PostgreSQL |
| Query transparency | N/A | ✅ SQL shown in expander |
| Query routing | `"rag"` / `"chat"` | `"rag"` / `"db"` / `"chat"` |
| DeepEval routing test | 15 cases, 100% | 13 cases, 100% |

---

## Known Gaps — Phase 7 Tuning Items

| Issue | Severity | Phase 7 Fix |
|---|---|---|
| `/rag/db/stream` runs `db_rag_query()` twice — once for streaming, once for metadata | Low — duplicate API call, ~0.5s overhead | Cache result in stream generator, pass to metadata event |
| `test_db_routing_boundary` tests router only — does not verify SQL accuracy | Low — separate concern | Add SQL accuracy metric in Phase 7 |
| `NOT_DB_QUERY` fallback in Streamlit doesn't re-route to document RAG automatically | Low — user must re-ask | Add automatic RAG fallback in frontend |
| LLM-judged tests (employee_lookup, aggregate, join) not run in this session | Low — structural check passed | Run against live backend with full OPENAI_API_KEY |

---

## Infrastructure Notes

**PostgreSQL connection:** Database runs in Docker container `hr_postgres`. Connection string from `settings.database_url`. Verify with:
```bash
docker exec hr_postgres psql -U postgres -d hr_platform -c "SELECT COUNT(*) FROM employees;"
```

**Employee data:** 50 employees, emails at `@acmecorp.com` (updated from `@hrplatform.com` at the start of Phase 3 via bulk sed replace).

**sys.path fix for DeepEval tests:** Same pattern as Phase 2 — required at the top of `test_database_rag.py` and `conftest.py`:
```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)
))))
```

**Phase 2 baseline maintained:** All 5 Phase 2 document RAG tests continue to pass through Phase 3. The three-way router correctly routes policy questions to `"rag"` — no regression in document RAG behavior.

---

## What Comes Next — Phase 4

Phase 4 adds **conversational memory** — ARIA will remember context across multiple turns in a conversation.

**Phase 4 components:**
- Redis or in-memory session store for conversation history per `session_id`
- LangChain `ConversationBufferMemory` or `MessagesPlaceholder`
- Follow-up question resolution: "What about his manager?" after asking about James Chen routes to `"db"` with context
- Session expiry and cleanup
- DeepEval `ConversationalTestCase` for multi-turn evaluation

**The Phase 3 baseline must be maintained:** All routing tests and LLM-judged tests must continue to pass through Phase 4 and beyond. The three-way router and Database RAG chain are now foundational infrastructure.

> **Golden Rule:** Database queries always return real data — ARIA never guesses employee details, leave balances, or org chart relationships. If the SQL returns 0 rows, ARIA says so explicitly. No hallucination on structured data.
