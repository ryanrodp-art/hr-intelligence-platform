# ARIA — HR GenAI Agent Platform
## Phase 1 Build Guide — LLM Chat

> GPT-4o wired into FastAPI with streaming, conversation memory, and DeepEval evaluation.
> **Completed in 2 days | 4 Steps | 24 DeepEval test cases | 100% pass rate**

---

## Phase 1 Overview

Phase 1 replaces the hardcoded stub response with real GPT-4o intelligence. The `/chat` endpoint gets wired to LangChain with streaming responses and conversation memory so ARIA remembers context across messages.

**What Phase 1 Delivers:**

- LangChain `RunnableWithMessageHistory` chain connected to GPT-4o
- Per-session conversation memory — ARIA remembers previous messages
- Streaming via Server-Sent Events (SSE) — tokens appear word by word
- Dedicated FastAPI route file for chat endpoints
- 20-entry golden dataset covering HR scenarios and failure modes
- 5 DeepEval test functions, 24 test cases, 100% pass rate

**4 Steps:**

| # | Step | File Created / Modified | Delivers |
|---|---|---|---|
| 1 | LangChain Chat Chain | `backend/chains/chat_chain.py` | GPT-4o connection + memory |
| 2 | Wire Chain into FastAPI | `backend/api/routes/chat.py` + `backend/main.py` | Live /chat endpoint |
| 3 | Streaming | All three layers updated | Token-by-token UI |
| 4 | DeepEval Tests | `evaluation/tests/test_chat.py` + golden set | Measured quality baseline |

---

## Step 1 — backend/chains/chat_chain.py

### Concept

A LangChain chain is a sequence of components connected with `|` pipe operators. The chat chain combines:
- **System prompt** — ARIA's persona, always sent first
- **Conversation history** — injected from memory per session
- **New user message** — the current question
- **ChatOpenAI** — sends everything to GPT-4o
- **RunnableWithMessageHistory** — manages per-session memory automatically

**Why `RunnableWithMessageHistory` instead of `ConversationChain`?**
`ConversationChain` is deprecated in LangChain 0.3+. The modern approach uses `RunnableWithMessageHistory` which wraps any chain with automatic history management keyed by `session_id`.

**Memory model:** Each `session_id` gets its own `ChatMessageHistory` instance stored in a module-level dict `_memory_store`. Python modules are singletons — the dict persists across all API requests for the lifetime of the server process.

### Claude Code Prompt

```
Create a new file backend/chains/chat_chain.py and the
backend/chains/__init__.py file.

Imports needed:
- from langchain_openai import ChatOpenAI
- from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
- from langchain_core.messages import SystemMessage
- from langchain_core.chat_history import BaseChatMessageHistory
- from langchain_community.chat_message_histories import ChatMessageHistory
- from langchain_core.runnables.history import RunnableWithMessageHistory
- from typing import AsyncGenerator
- from config.settings import settings
- import logging

Setup:
- logger = logging.getLogger(__name__)

HR System Prompt constant ARIA_SYSTEM_PROMPT:
"You are ARIA (Agentic Resources Intelligence Assistant), an intelligent
HR assistant for our company. You help employees and HR managers with:

- HR policies and procedures
- Leave requests and balance inquiries
- Employee information and org chart queries
- Company guidelines and compliance
- Onboarding assistance
- Benefits and payroll questions

Guidelines:
- Always be professional, empathetic, and accurate
- If you don't know something, say so clearly — never make up information
- For leave requests or sensitive matters, remind users to confirm
  with their HR manager
- Keep responses concise but complete
- You have access to company HR policies and employee records

You are currently in Phase 1 — you can answer general HR questions
based on your training. In later phases you will have access to
company-specific documents and employee data."

Memory store:
- _memory_store: dict[str, ChatMessageHistory] = {}
- def get_or_create_memory(session_id: str) -> ChatMessageHistory:
  - If not in store: create ChatMessageHistory(), log "Created new memory"
  - Else: log "Retrieved existing memory"
  - Return the memory

LLM:
- def get_llm() -> ChatOpenAI:
  - return ChatOpenAI(
      model=settings.openai_model,
      temperature=0.7,
      streaming=True,
      api_key=settings.openai_api_key
    )

Prompt template:
- ChatPromptTemplate.from_messages([
    SystemMessage(content=ARIA_SYSTEM_PROMPT),
    MessagesPlaceholder(variable_name="history"),
    ("human", "{input}"),
  ])

Main chat function:
- async def chat(message: str, session_id: str) -> str:
  - Build chain: prompt | llm
  - Wrap with RunnableWithMessageHistory(
      chain, get_or_create_memory,
      input_messages_key="input",
      history_messages_key="history"
    )
  - Invoke: await chain_with_history.ainvoke(
      {"input": message},
      config={"configurable": {"session_id": session_id}}
    )
  - Return response.content
  - Log Q and A (first 50 chars each)

Streaming function:
- async def chat_stream(message: str, session_id: str) -> AsyncGenerator[str, None]:
  - Same chain setup as chat()
  - Use chain_with_history.astream() instead of ainvoke()
  - For each chunk: yield chunk.content if not empty
  - Accumulate full_response for logging at end

Utility functions:
- def clear_memory(session_id: str) -> bool
- def get_memory_stats() -> dict

In backend/chains/__init__.py export:
  chat, chat_stream, clear_memory, get_memory_stats
```

### Key Concepts Explained

**`async def` / `await`** — FastAPI is built on asyncio. Async functions allow the server to handle other requests while waiting for GPT-4o to respond. Without async, one slow GPT-4o call would block all other users.

**`temperature=0.7`** — controls GPT-4o randomness. `0.0` = deterministic, `1.0+` = creative. `0.7` gives natural conversational variation while staying consistent — right for an HR assistant.

**`RunnableWithMessageHistory`** — the modern LangChain pattern (replaces deprecated `ConversationChain`). It automatically fetches history for the session, injects it into the prompt, and saves the new exchange after each call.

**`astream()` vs `ainvoke()`** — `ainvoke()` waits for the complete response then returns it all at once. `astream()` returns an async iterator yielding chunks as GPT-4o generates them — enabling the typing effect.

### Exit Criteria

| Check | Status |
|---|---|
| `chat_chain.py` created | ✅ |
| `__init__.py` exports all functions | ✅ |
| `get_or_create_memory()` creates per-session history | ✅ |
| `chat()` returns GPT-4o response string | ✅ |
| `chat_stream()` yields tokens as async generator | ✅ |

---

## Step 2 — Wire Chain into FastAPI

### Concept

`backend/main.py` should be a registration file — not a business logic file. Moving the chat endpoint to `backend/api/routes/chat.py` follows the single responsibility principle. Each route file owns one domain.

**Why `APIRouter`?** FastAPI's `APIRouter` collects route definitions independently of the main app. `app.include_router(router)` registers all routes at startup. The connection is the import — not the filename.

**`prefix="/chat"`** — prepended to every route in the router:
- `@router.post("/")` → `POST /chat/`
- `@router.get("/stats")` → `GET /chat/stats`
- `@router.delete("/{session_id}")` → `DELETE /chat/{session_id}`

> **Trailing slash note:** FastAPI canonicalises routes to include a trailing slash. Streamlit must call `http://localhost:8000/chat/` (with slash) not `/chat` — otherwise FastAPI returns a `307 Temporary Redirect` that httpx won't follow on POST requests.

### Claude Code Prompt

```
Make the following changes to wire the LangChain chat chain into FastAPI.

CHANGE 1 — Create backend/api/routes/chat.py:

Imports:
- from fastapi import APIRouter
- from fastapi.responses import StreamingResponse
- from backend.schemas.chat import ChatRequest, ChatResponse
- from backend.chains.chat_chain import chat as chain_chat, chat_stream,
  clear_memory, get_memory_stats
- from config.settings import settings
- import logging, json

Setup:
- logger = logging.getLogger(__name__)
- router = APIRouter(prefix="/chat", tags=["chat"])

Endpoint 1 — POST / → POST /chat/:
- Accepts ChatRequest, returns ChatResponse
- Calls: response_text = await chain_chat(request.message, request.session_id)
- Returns ChatResponse(response=response_text, session_id=..., model=settings.openai_model)
- try/except: on error return ChatResponse with response="I apologise, I encountered
  an error. Please try again." and model="error"

Endpoint 2 — POST /stream → POST /chat/stream:
- Accepts ChatRequest, returns StreamingResponse
- Inner async generator stream_generator():
  - async for token in chat_stream(request.message, request.session_id):
    - yield f"data: {json.dumps({'token': token, 'session_id': ...})}\n\n"
  - yield done signal: data: {"token": "[DONE]"}\n\n
  - try/except: yield error signal on failure
- Return StreamingResponse(
    stream_generator(),
    media_type="text/event-stream",
    headers={"Cache-Control": "no-cache", "Connection": "keep-alive",
             "X-Accel-Buffering": "no"}
  )

Endpoint 3 — DELETE /{session_id}:
- Calls clear_memory(session_id)
- Returns {"cleared": True, "session_id": session_id}

Endpoint 4 — GET /stats:
- Returns get_memory_stats()

CHANGE 2 — Update backend/main.py:
- Add: from backend.api.routes import chat as chat_router
- Remove: the existing POST /chat endpoint
- Add: app.include_router(chat_router.router)
- Keep everything else unchanged

CHANGE 3 — Create backend/api/__init__.py and backend/api/routes/__init__.py
(both empty — needed for Python package imports)
```

### Verification Commands

```bash
# Health check
curl http://localhost:8000/health

# Stats endpoint
curl http://localhost:8000/chat/stats
# Expected: {"active_sessions": 0, "session_ids": []}

# Live GPT-4o call
curl -X POST http://localhost:8000/chat/ \
  -H "Content-Type: application/json" \
  -d '{"message": "What is your name and what can you help me with?",
       "session_id": "phase1-test-001"}'

# Memory test — send follow-up in same session
curl -X POST http://localhost:8000/chat/ \
  -H "Content-Type: application/json" \
  -d '{"message": "What was the first thing I asked you?",
       "session_id": "phase1-test-001"}'
# Expected: ARIA recalls the first question
```

### Exit Criteria

| Check | Status |
|---|---|
| `backend/api/routes/chat.py` created | ✅ |
| `POST /chat/` returns real GPT-4o response | ✅ |
| `POST /chat/stream` returns SSE stream | ✅ |
| `GET /chat/stats` returns session count | ✅ |
| `DELETE /chat/{session_id}` clears memory | ✅ |
| `main.py` cleaned up — no endpoint logic | ✅ |
| Memory persists across requests in same session | ✅ |

---

## Step 3 — Streaming

### Concept

**Without streaming:** Spinner shows for 2–5 seconds → full response appears instantly.

**With streaming:** First token arrives in ~500ms → words appear one by one → response builds like typing.

**How it works across three layers:**

```
GPT-4o generates token "My"
    ↓ chain_with_history.astream() yields AIMessageChunk("My")
    ↓ chat_stream() yields "My"
    ↓ stream_generator() yields 'data: {"token": "My"}\n\n'
    ↓ StreamingResponse sends over HTTP (SSE)
    ↓ httpx.stream() receives the line
    ↓ stream_response() generator yields "My"
    ↓ st.write_stream() appends "My" to chat bubble
    ↓ User sees "My" appear
    [repeat for every token until [DONE]]
```

**Server-Sent Events (SSE) format** — each chunk follows:
```
data: {"token": "My", "session_id": "abc-123"}\n\n
data: {"token": " name", "session_id": "abc-123"}\n\n
data: {"token": "[DONE]", "session_id": "abc-123"}\n\n
```
Two newlines (`\n\n`) mark end of each event — standard SSE protocol.

### Claude Code Prompt

```
Add streaming support across all three layers.

CHANGE 1 — backend/chains/chat_chain.py already has chat_stream()
from Step 1. Verify it's exported in __init__.py.

CHANGE 2 — backend/api/routes/chat.py already has POST /stream
from Step 2. Verify StreamingResponse and SSE format are correct.

CHANGE 3 — Update frontend/app.py:

Add import json at the top.

Add this generator function before the chat input section:
def stream_response(prompt: str, session_id: str):
    with httpx.stream(
        "POST",
        f"{BACKEND_URL}/chat/stream",
        json={"message": prompt, "session_id": session_id},
        timeout=60
    ) as response:
        for line in response.iter_lines():
            if line.startswith("data: "):
                data = json.loads(line[6:])
                token = data.get("token", "")
                if token and token != "[DONE]" and token != "[ERROR]":
                    yield token

Replace the existing spinner + httpx.post() block with:
    with st.chat_message("assistant"):
        response_text = st.write_stream(
            stream_response(prompt, st.session_state.session_id)
        )
    if response_text:
        st.session_state.messages.append({
            "role": "assistant",
            "content": response_text
        })
```

### Streaming Test

```bash
# Test SSE stream directly from terminal
curl -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "Say hello in exactly 5 words",
       "session_id": "stream-test-001"}'

# Expected output — individual SSE events:
# data: {"token": "Hello", "session_id": "stream-test-001"}
# data: {"token": " there", "session_id": "stream-test-001"}
# data: {"token": "!", ...}
# data: {"token": "[DONE]", ...}
```

**`st.write_stream(generator)`** — Streamlit's built-in streaming renderer. Accepts a generator, opens a text area in the chat bubble, appends each yielded token in real time, returns the complete assembled text when the generator is exhausted. That returned string gets saved to `session_state.messages`.

### Exit Criteria

| Check | Status |
|---|---|
| Tokens appear word by word in Streamlit UI | ✅ |
| No spinner — streaming replaces waiting | ✅ |
| `curl /chat/stream` shows individual SSE events | ✅ |
| Memory still works with streaming | ✅ |
| `response_text` saved to session_state after stream completes | ✅ |

---

## Step 4 — DeepEval Tests

### Concept

**Three metrics for Phase 1:**

| Metric | What It Measures | Threshold | Lower is Better? |
|---|---|---|---|
| `GEval` (HR Role Adherence) | Does ARIA stay in HR persona and not discuss off-topic subjects? | 0.70 | No — higher is better |
| `AnswerRelevancyMetric` | Is the response directly relevant to the question asked? | 0.70 | No — higher is better |
| `HallucinationMetric` | Does ARIA invent facts not in its context? | 0.50 | Yes — lower means less hallucination |

**Judge LLM:** DeepEval used `gpt-5.4` for GEval and `gpt-4o` for Answer Relevancy and Hallucination.

**What is a golden set?** Manually written question/answer pairs — the "answer key" your AI is measured against. DeepEval compares ARIA's actual responses against the expected outputs using the judge LLM.

---

## Golden Dataset — chat_golden_set.json

**Location:** `evaluation/datasets/chat_golden_set.json`
**Total entries:** 20
**Two batches:** Original 10 (standard HR) + 10 additional (edge cases and failure scenarios)

---

### Batch 1 — Original 10 Entries (Rows 1–10)

**Claude Code Prompt used to generate:**

```
Create evaluation/datasets/chat_golden_set.json
with 10 realistic HR question/answer pairs:

[
  {
    "input": "What is your name and what can you help me with?",
    "expected_output": "I am ARIA, an HR Intelligence Assistant. I can help
    with HR policies, leave requests, employee information, company guidelines,
    onboarding, and benefits questions."
  },
  {
    "input": "What types of leave are typically available to employees?",
    "expected_output": "Common leave types include annual leave, sick leave,
    parental leave, emergency leave, and unpaid leave."
  },
  {
    "input": "How do I apply for annual leave?",
    "expected_output": "To apply for annual leave, you should submit a leave
    request to your manager with the dates you require, typically with advance
    notice as per company policy."
  },
  {
    "input": "What should I do on my first day of onboarding?",
    "expected_output": "On your first day you should meet your manager and team,
    complete HR paperwork, set up your accounts and equipment, and review company
    policies and guidelines."
  },
  {
    "input": "Who should I contact for payroll questions?",
    "expected_output": "For payroll questions you should contact the HR or Finance
    department, or your HR Business Partner."
  },
  {
    "input": "What is a performance review?",
    "expected_output": "A performance review is a formal evaluation where your
    manager assesses your work performance, provides feedback, sets goals, and
    discusses career development."
  },
  {
    "input": "What is the difference between sick leave and annual leave?",
    "expected_output": "Sick leave is used when you are ill or injured and cannot
    work. Annual leave is planned time off for rest and personal activities."
  },
  {
    "input": "What does HR stand for?",
    "expected_output": "HR stands for Human Resources — the department responsible
    for managing employee relations, recruitment, policies, payroll, and benefits."
  },
  {
    "input": "Can you help me write a Python script?",
    "expected_output": "I am an HR assistant and can only help with HR-related
    topics. For technical questions please contact your IT or engineering team."
  },
  {
    "input": "What is an org chart?",
    "expected_output": "An org chart is a diagram showing the structure of an
    organisation, including reporting relationships between employees, teams,
    and departments."
  }
]
```

**Row categories — Batch 1:**

| Row | Input | Category | Failure Mode Tested |
|---|---|---|---|
| 1 | What is your name and what can you help me with? | Persona introduction | ARIA identifies itself correctly |
| 2 | What types of leave are typically available? | General HR knowledge | Completeness of answer |
| 3 | How do I apply for annual leave? | Process question | Step accuracy |
| 4 | What should I do on my first day of onboarding? | Onboarding | Coverage of first-day tasks |
| 5 | Who should I contact for payroll questions? | Contact/routing | **Known failure** — vague answer (no company data) |
| 6 | What is a performance review? | HR definitions | Accuracy of definition |
| 7 | Difference between sick leave and annual leave? | Policy comparison | Distinction clarity |
| 8 | What does HR stand for? | Basic HR knowledge | Simple factual accuracy |
| 9 | Can you help me write a Python script? | **Off-topic redirect** | Role boundary enforcement |
| 10 | What is an org chart? | HR definitions | Accuracy of definition |

---

### Batch 2 — Additional 10 Entries (Rows 11–20)

**Rationale:** Added to deliberately test edge cases and realistic failure scenarios rather than only happy-path questions.

**Claude Code Prompt used to generate:**

```
Update evaluation/datasets/chat_golden_set.json.
Keep all 10 existing entries exactly as they are.
Add 10 more entries that deliberately test edge cases and likely
failure scenarios for ARIA in Phase 1 (no RAG, no company data):

{
  "input": "Can you help me with my issue?",
  "expected_output": "I would be happy to help. Could you please provide more
  details about your HR-related issue so I can assist you better?"
},
{
  "input": "What is our company's exact parental leave policy?",
  "expected_output": "I don't have access to your specific company policy
  documents yet. Generally, parental leave policies provide paid time off
  for new parents. Please check with your HR manager or company handbook
  for exact details."
},
{
  "input": "I think I am being treated unfairly by my manager. What should I do?",
  "expected_output": "I'm sorry to hear you're experiencing this. You should
  document the incidents, speak with your HR Business Partner or HR manager
  confidentially, and review the company's grievance policy."
},
{
  "input": "What is the salary range for a Senior Software Engineer at our company?",
  "expected_output": "I don't have access to specific salary information for
  your company. Please contact your HR manager or refer to your compensation
  guidelines for accurate salary range information."
},
{
  "input": "How do I apply for sick leave, how many days do I get, and do I need
  a doctor's note?",
  "expected_output": "To apply for sick leave, notify your manager and submit
  a leave request through HR. The number of sick days varies by company policy.
  A doctor's note may be required for absences exceeding a certain number of
  days — check your company's sick leave policy for specifics."
},
{
  "input": "What is the best programming language to learn in 2025?",
  "expected_output": "That's outside my area of expertise as an HR assistant.
  I can help with HR policies, leave requests, employee information, and
  workplace guidelines. For technical career advice, I'd suggest speaking
  with your engineering team or manager."
},
{
  "input": "How long is the probation period?",
  "expected_output": "Probation periods typically range from 3 to 6 months
  depending on company policy and role. Please check your employment contract
  or ask your HR manager for the exact duration applicable to your position."
},
{
  "input": "Exactly how many vacation days do I get per year?",
  "expected_output": "The exact number of vacation days depends on your company
  policy, employment contract, and seniority level. I don't have access to your
  specific entitlement. Please check with your HR manager or review your
  employment contract."
},
{
  "input": "A colleague is harassing me. What are my options?",
  "expected_output": "I'm sorry you're experiencing this. You should report
  the situation to your HR manager or HR Business Partner immediately.
  Document all incidents with dates, times, and details. Your company should
  have an anti-harassment policy and a formal complaint process to protect you."
},
{
  "input": "Can my manager fire me without any warning?",
  "expected_output": "Employment termination policies vary by company and
  jurisdiction. Generally, companies have disciplinary procedures before
  termination. I recommend reviewing your employment contract and company
  policy. For specific legal advice, consult an employment lawyer or your
  HR department."
}
```

**Row categories — Batch 2:**

| Row | Input | Category | Failure Mode Tested |
|---|---|---|---|
| 11 | Can you help me with my issue? | **Vague question** | Asks for clarification vs guessing |
| 12 | What is our company's exact parental leave policy? | **Company-specific data** | Admits knowledge limits vs hallucinating |
| 13 | I think I am being treated unfairly by my manager | **Emotionally sensitive** | Empathy + correct HR escalation path |
| 14 | What is the salary range for a Senior Software Engineer? | **No data — hallucination risk** | Salary data ARIA doesn't have |
| 15 | How do I apply for sick leave + how many days + doctor's note? | **Multi-part question** | Does ARIA address ALL parts? |
| 16 | What is the best programming language to learn in 2025? | **Off-topic redirect** | Role boundary (different from row 9) |
| 17 | How long is the probation period? | **Ambiguous — no context** | Handling unclear/company-specific queries |
| 18 | Exactly how many vacation days do I get per year? | **Specific number — hallucination risk** | High hallucination risk — exact numbers |
| 19 | A colleague is harassing me. What are my options? | **Legally/ethically sensitive** | Correct escalation — report to HR immediately |
| 20 | Can my manager fire me without any warning? | **Legally sensitive** | Appropriate disclaimer + legal referral |

---

## Test Functions — Which Rows Each Test Uses

**File:** `evaluation/tests/test_chat.py`

### test_aria_responds_to_hr_questions
**Rows used:** 1, 2, 3, 4, 5, 6, 7, 8 (first 8 entries)
**Metrics:** `GEval` (HR Role Adherence) + `AnswerRelevancyMetric`
**Purpose:** Standard HR questions — verifies ARIA gives relevant, on-persona answers across the core HR knowledge domains.

### test_aria_rejects_non_hr_questions
**Rows used:** 9 (Python script question)
**Metrics:** `GEval` (HR Role Adherence)
**Purpose:** Verifies ARIA redirects off-topic requests back to HR topics without complying with the non-HR request.

### test_aria_no_hallucination
**Rows used:** 1, 2, 3, 4, 5 (first 5 entries, with `context=[]`)
**Metrics:** `HallucinationMetric`
**Purpose:** With no retrieval context provided, verifies ARIA does not invent company-specific facts. Uses the first 5 questions because they are general enough for ARIA to answer without making things up.

### test_aria_handles_sensitive_questions
**Rows used:** 13, 15, 17, 19, 20
**Metrics:** `GEval` (HR Role Adherence) + `AnswerRelevancyMetric`
**Purpose:** Emotionally sensitive, multi-part, ambiguous, and legally sensitive questions. Verifies ARIA handles difficult scenarios with appropriate empathy, completeness, and disclaimers.

> Comment in code: "These may produce failures in Phase 1 — expected to improve with RAG in Phase 3"

### test_aria_handles_knowledge_boundary_questions
**Rows used:** 11, 12, 14, 16, 18
**Metrics:** `HallucinationMetric` (with `context=[]`)
**Purpose:** Vague, company-specific, salary, off-topic, and exact-number questions. Verifies ARIA says "I don't know" or redirects rather than inventing specific company data it doesn't have.

> Comment in code: "Tests that ARIA says 'I don't know' rather than inventing specific company data"

**Row-to-test mapping summary:**

| Row | Question Summary | test_1 | test_2 | test_3 | test_4 | test_5 |
|---|---|---|---|---|---|---|
| 1 | What is your name? | ✅ | | ✅ | | |
| 2 | Types of leave | ✅ | | ✅ | | |
| 3 | Apply for annual leave | ✅ | | ✅ | | |
| 4 | First day onboarding | ✅ | | ✅ | | |
| 5 | Payroll contact | ✅ | | ✅ | | |
| 6 | Performance review | ✅ | | | | |
| 7 | Sick vs annual leave | ✅ | | | | |
| 8 | What does HR stand for | ✅ | | | | |
| 9 | Python script (off-topic) | | ✅ | | | |
| 10 | Org chart | | | | | |
| 11 | Vague question | | | | | ✅ |
| 12 | Company parental leave policy | | | | | ✅ |
| 13 | Treated unfairly | | | | ✅ | |
| 14 | Salary range | | | | | ✅ |
| 15 | Multi-part sick leave | | | | ✅ | |
| 16 | Best programming language | | | | | ✅ |
| 17 | Probation period | | | | ✅ | |
| 18 | Exact vacation days | | | | | ✅ |
| 19 | Harassment | | | | ✅ | |
| 20 | Fired without warning | | | | ✅ | |

*test_1 = test_aria_responds_to_hr_questions*
*test_2 = test_aria_rejects_non_hr_questions*
*test_3 = test_aria_no_hallucination*
*test_4 = test_aria_handles_sensitive_questions*
*test_5 = test_aria_handles_knowledge_boundary_questions*

> **Note:** Row 10 (org chart) is in the golden set but not yet used by any test function — reserved for Phase 2 when org chart data from the database becomes available.

---

## DeepEval Test Run Results

### Run 1 — Original 10 Golden Set Entries

**Command:** `uv run deepeval test run evaluation/tests/test_chat.py -v`
**Tests collected:** 3
**Token cost:** $0.112
**Time:** 57.25s

| Test | Result | Metrics | Key Score |
|---|---|---|---|
| test_aria_responds_to_hr_questions | ❌ FAILED | GEval + AnswerRelevancy | AnswerRelevancy 0.67 on row 5 (payroll) |
| test_aria_rejects_non_hr_questions | ✅ PASSED | GEval | 1.00 |
| test_aria_no_hallucination | ✅ PASSED | Hallucination | 0.00 |

**Aggregate:**

| Metric | Average Score | Pass Rate | Total Cases |
|---|---|---|---|
| HR Role Adherence [GEval] | 0.91 | 100% | 8 |
| Answer Relevancy | 0.93 | 87.5% | 8 |
| Hallucination | 0.00 | 100% | 5 |

**Overall: 92.86% — 13/14 test cases passed**

**The one failure — Row 5 (payroll contact):**
- Score: `0.67` (threshold: `0.70`)
- Reason: *"The response provides general assistance but lacks specific contact information for payroll inquiries, which is crucial for fully addressing the question."*
- Decision: **Kept as a realistic failure** — ARIA has no company-specific contact data in Phase 1. This failure demonstrates the gap that Database RAG in Phase 3 will close.

---

### Run 2 — Expanded to 20 Golden Set Entries

**Command:** `uv run deepeval test run evaluation/tests/test_chat.py -v`
**Tests collected:** 3 (same test functions, updated golden set)
**Token cost:** $0.109
**Time:** 41.98s

| Test | Result | Metrics | Notes |
|---|---|---|---|
| test_aria_responds_to_hr_questions | ✅ PASSED | GEval + AnswerRelevancy | Payroll question scored 0.80 this run |
| test_aria_rejects_non_hr_questions | ✅ PASSED | GEval | 1.00 |
| test_aria_no_hallucination | ✅ PASSED | Hallucination | 0.00 |

**Aggregate:**

| Metric | Average Score | Pass Rate | Total Cases |
|---|---|---|---|
| HR Role Adherence [GEval] | 0.93 | 100% | 8 |
| Answer Relevancy | 0.96 | 100% | 8 |
| Hallucination | 0.00 | 100% | 5 |

**Overall: 100% — 14/14 test cases passed**

**Key insight — non-determinism in the judge:**
The payroll question (row 5) scored `0.67` in Run 1 and `0.80` in Run 2 — same question, same ARIA response, different judge score. This demonstrates that LLM-as-judge evaluation is itself non-deterministic. In Phase 7, evaluations will run multiple times and track trends rather than treating a single run as definitive.

---

### Run 3 — 5 Test Functions, 24 Test Cases

**Command:** `uv run deepeval test run evaluation/tests/test_chat.py -v`
**Tests collected:** 5
**Token cost:** $0.188
**Time:** 72.72s (1 minute 12 seconds)

| Test | Result | Metrics | Cases |
|---|---|---|---|
| test_aria_responds_to_hr_questions | ✅ PASSED | GEval + AnswerRelevancy | 8 |
| test_aria_rejects_non_hr_questions | ✅ PASSED | GEval | 1 |
| test_aria_no_hallucination | ✅ PASSED | Hallucination | 5 |
| test_aria_handles_sensitive_questions | ✅ PASSED | GEval + AnswerRelevancy | 5 |
| test_aria_handles_knowledge_boundary_questions | ✅ PASSED | Hallucination | 5 |

**Aggregate by metric:**

| Metric | Average Score | Pass Rate | Total Cases |
|---|---|---|---|
| HR Role Adherence [GEval] | 0.95 | 100% | 14 |
| Answer Relevancy | 0.98 | 100% | 13 |
| Hallucination | 0.00 | 100% | 10 |

**Overall: 100% — 24/24 test cases passed**

**Notable scores from Run 3:**

| Row | Question | GEval Score | AnswerRelevancy | Hallucination |
|---|---|---|---|---|
| 1 | What is your name? | 1.00 | 1.00 | 0.00 |
| 13 | Treated unfairly by manager | 1.00 | 1.00 | — |
| 15 | Multi-part sick leave question | 0.87 | 1.00 | — |
| 17 | Probation period | 0.90 | 1.00 | — |
| 19 | Harassment complaint | 0.99 | 1.00 | — |
| 20 | Fired without warning | 0.91 | 1.00 | — |
| 11 | Vague question | — | — | 0.00 |
| 14 | Salary range | — | — | 0.00 |
| 18 | Exact vacation days | — | — | 0.00 |

**Recurring judge observation across all 3 runs:**
> *"It does not explicitly present itself as ARIA or reinforce the HR assistant persona"*

This consistently keeps some GEval scores at 0.87–0.96 instead of 1.0. ARIA answers correctly but doesn't always identify herself by name in follow-up responses. **Known improvement for Phase 2** — update system prompt to include: "Always refer to yourself as ARIA in every response."

---

## Phase 1 Baseline — Locked In for Phase 2 Comparison

| Metric | Phase 1 Baseline | Target After Phase 2 RAG |
|---|---|---|
| HR Role Adherence | 0.95 avg | 0.97+ |
| Answer Relevancy | 0.98 avg | 0.99+ |
| Hallucination | 0.00 | 0.00 (maintain) |
| Test functions | 5 | 7 (add RAG-specific tests) |
| Test cases | 24 | 40+ |
| Pass rate | 100% | 100% |

When Document RAG is added in Phase 2, the company-specific policy questions (rows 12, 14, 17, 18) that currently produce general answers will get specific, grounded responses. The improvement in Answer Relevancy scores on those questions is the measurable proof that RAG is working.

---

## What Comes Next — Phase 2: Document RAG

Phase 2 grounds ARIA's answers in real company policy documents. Right now ARIA answers from GPT-4o's general training knowledge. After Phase 2 she answers from your actual HR policy PDFs.

**Phase 2 components:**
- 4 HR policy PDF documents created (leave policy, code of conduct, benefits guide, employee handbook)
- PyMuPDF extracts and cleans text from PDFs
- LangChain `RecursiveCharacterTextSplitter` chunks documents
- OpenAI embeddings convert chunks to vectors
- ChromaDB stores and indexes the vectors
- On each query: retrieve top-k most relevant chunks → inject into prompt
- ARIA's answers are now grounded in specific company policy text

**Phase 2 DeepEval metrics added:**
- `FaithfulnessMetric` — are claims in ARIA's response grounded in retrieved docs?
- `ContextualPrecisionMetric` — are the most relevant chunks ranked at the top?
- `ContextualRecallMetric` — does the retrieval surface all necessary information?
- `AnswerRelevancyMetric` — maintained from Phase 1 as a regression check

> **Golden Rule:** The Phase 1 DeepEval baseline must be maintained or improved in every subsequent phase. If a Phase 2 change causes a regression in Role Adherence or Hallucination scores, fix it before moving to Phase 3.
