# ARIA Codebase Guide — Phases 0–5
## Understanding the Code in Execution Order

> **How to use this guide:** Open your code editor on one side, this document on the other.
> Follow the flow of a real user message through every file it touches.
> Each section tells you what a file does, where it fits, and why it was designed that way —
> not a line-by-line walkthrough, but enough to make the code immediately readable.

---

## The Five Journeys

Everything in this codebase serves one of five request flows:

**Journey 1 — CHAT**
> *"Hello ARIA, what can you help me with?"*
> A general question routed to GPT-4o with conversation memory.

**Journey 2 — DOCUMENT RAG**
> *"What is the parental leave policy?"*
> A policy question retrieved from HR documents, answered with citations.

**Journey 3 — DATABASE RAG**
> *"How many leave days does James Chen have?"*
> An employee-specific question converted to SQL, executed against PostgreSQL, answered from live data.

**Journey 4 — AGENT**
> *"What is the remote work policy and how many days does James Chen have?"*
> A compound question that needs both document search and employee lookup. A LangChain ReAct agent reasons over which tools to call, calls them in sequence, and combines the results into one coherent answer.

**Journey 5 — MCP**
> *"Submit Annual leave for EMP-0001 from 2027-06-16 to 2027-06-18"*
> An action request — or a structured employee data request using an EMP-ID — routed to the FastMCP server on port 8002. The agent uses MCP tools that write to, read from, and delete from PostgreSQL via a network protocol rather than direct Python calls.

All five journeys start at the same place — the Streamlit UI — and end at the same place — a response in the browser. A single classifier (the query router) decides which journey handles each request. What happens in between is different.

Read Journey 1 first. Journey 2 builds on everything Journey 1 establishes. Journey 3 builds on both. Journey 4 builds on all three — the agent's tools delegate directly to the Journey 2 and Journey 3 pipelines. Journey 5 extends Journey 4 — the same agent gains five additional tools served from a separate MCP network process.

---

# JOURNEY 1 — CHAT

## The Chat Request Flow

```
User types message in browser
        ↓
frontend/app.py              captures input, classifies, streams response
        ↓ HTTP POST /chat/
backend/main.py              FastAPI receives, routes to chat router
        ↓
backend/api/routes/chat.py   endpoint validates, calls chain
        ↓
backend/schemas/chat.py      ChatRequest validated here
        ↓
backend/chains/chat_chain.py LangChain + GPT-4o + memory
        ↓ tokens stream back up the same path
frontend/app.py              st.write_stream() renders tokens
```

---

## File 1 — `config/settings.py`

**What it is:** The single source of truth for every configuration value in the application.

**Where it fits:** Every other file imports from here. Nothing reads `.env` directly except this file.

**How it works:**
`settings.py` defines a `Settings` class that inherits from Pydantic's `BaseSettings`. When Python loads this module, Pydantic automatically reads your `.env` file and populates every field. At the bottom of the file, a singleton `settings = Settings()` is created — this single object is shared across the entire application.

**Key functions and properties:**
- `database_url` — a computed property that assembles the full PostgreSQL connection string from the individual host, port, user, password, and database fields. No other file ever assembles this string manually.
- `chroma_url` — similarly assembles `http://host:port` for ChromaDB.

**The design decision worth noting:**
Rather than importing `settings` and calling `settings.database_url` at module load time, each file that needs configuration imports `settings` and reads from it at call time. This means if you change a value in `.env` and restart the server, every part of the application picks it up without any code changes.

**In the chat flow:** `chat_chain.py` reads `settings.openai_api_key` and `settings.openai_model` to configure the LLM. `main.py` reads `settings.app_env` for the startup log. The MCP tools in Phase 5 read `settings.database_url` directly, bypassing the DB RAG pipeline entirely.

---

## File 2 — `frontend/app.py`

**What it is:** The entire user interface. Everything the user sees and interacts with lives here.

**Where it fits:** The starting point of every request. It sends HTTP calls to FastAPI and renders everything that comes back.

**How it works:**
Streamlit reruns the entire script from top to bottom every time the user interacts — types a message, clicks a button, anything. `st.session_state` is a persistent dictionary that survives these reruns, which is how the conversation history stays visible between messages.

**Key functions:**

`stream_response(prompt, session_id)` — the chat streaming generator. Opens a persistent HTTP connection to `/chat/stream` using `httpx.stream()`, reads Server-Sent Events line by line, parses each JSON event, and yields the token string. This function is passed directly to `st.write_stream()` which renders each token as it arrives.

`stream_rag(question, session_id)` — the RAG streaming generator. Same pattern as `stream_response()` but calls `/rag/stream` instead. Watches for a special metadata SSE event containing `"sources"` — when it arrives, it stores the citation list in `session_state.last_sources` so they can be displayed below the answer.

**The routing decision block** — when the user hits Enter, the app first calls `GET /rag/classify?query=...` to ask FastAPI whether this question should go to RAG or chat. Based on the classification it calls either `stream_rag()` or `stream_response()`. The user never sees this classification step — it happens in the 200–300ms before the first token appears.

**The sidebar** — calls `GET /health` on every page load to show backend status. Also calls `GET /rag/status` to show how many policy chunks are indexed in ChromaDB. Phase 4 adds an agent ping. Phase 5 adds an MCP server ping — pinging `POST /mcp/query` with a test question and displaying `🔧 MCP Server: Online` or `🔧 MCP Server: Offline`.

**The design decision worth noting:**
`st.write_stream()` accepts a generator and renders tokens as they arrive. It also returns the complete assembled text when the generator finishes — this is what gets saved to `session_state.messages` for conversation history. One call does both streaming display and history capture.

---

## File 3 — `backend/main.py`

**What it is:** The FastAPI application entry point — the front door of the backend.

**Where it fits:** Loaded by uvicorn on startup. Registers all routes, adds middleware, and runs startup/shutdown logic.

**How it works:**
`main.py` creates the `FastAPI` app object and configures it. It does not contain any endpoint logic — that lives in the route files. `main.py`'s job is wiring everything together.

**Key functions:**

`lifespan(app)` — an async context manager that runs startup code before `yield` and shutdown code after. On startup it logs all configuration values confirming the application is connected to the right databases.

`app.add_middleware(CORSMiddleware)` — allows Streamlit (port 8501) to call FastAPI (port 8000). Without this the browser blocks cross-origin requests as a security measure.

`app.include_router(...)` — registers all routers. By Phase 5, four routers are registered: chat, rag, agent, and mcp_agent. Each router is imported as an alias (`chat as chat_router`, `mcp_agent as mcp_agent_router`) to prevent name conflicts.

**The design decision worth noting:**
`main.py` has no business logic. It only registers things. Adding a new domain (Phase 5 MCP) means adding two lines: one import and one `include_router`. All existing routers remain untouched.

---

## File 4 — `backend/schemas/chat.py`

**What it is:** The data contract for the chat API — defines exactly what goes in and what comes out.

**Where it fits:** Used by the chat route to validate incoming requests and serialize outgoing responses. FastAPI reads these schemas automatically.

**How it works:**
Two Pydantic models define the API contract:

`ChatRequest` — what Streamlit sends. Has two fields: `message` (required string, minimum 1 character after whitespace stripping) and `session_id` (optional, auto-generates a UUID if not provided). A field validator strips whitespace from the message and rejects anything that becomes empty after stripping.

`ChatResponse` — what FastAPI sends back. Has four fields: `response` (the text), `session_id` (echoed back from the request), `timestamp` (auto-generated at response creation time), and `model` (which LLM was used).

**The design decision worth noting:**
`session_id` uses `default_factory=lambda: str(uuid4())` rather than `default=str(uuid4())`. The factory is called once per instance — so every new request gets a fresh UUID. Using `default=` would generate one UUID at class definition time and share it across all requests.

---

## File 5 — `backend/api/routes/chat.py`

**What it is:** The chat endpoint handler — the code that runs when `/chat/` is called.

**Where it fits:** Between `main.py` (which registers it) and `chat_chain.py` (which it calls). Receives validated requests, calls the chain, returns responses.

**How it works:**
An `APIRouter` with `prefix="/chat"` is created. Four endpoints are defined:

`POST /` → `POST /chat/` — the non-streaming endpoint. Used by DeepEval test suite. Calls `chain_chat()`, waits for the complete response, returns a `ChatResponse` JSON object. The trailing slash matters — FastAPI canonicalises routes with a trailing slash and redirects requests without one. `httpx` won't follow redirects on POST, so all callers must use `/chat/`.

`POST /stream` → `POST /chat/stream` — the streaming endpoint. Used by Streamlit. Creates an async generator that calls `chat_stream()` and yields each token as an SSE event. Returns a `StreamingResponse` with `media_type="text/event-stream"` and headers that prevent caching and buffering.

`DELETE /{session_id}` — clears conversation memory for a session.

`GET /stats` — returns how many active conversation sessions are in memory.

**The design decision worth noting:**
`/chat/` and `/chat/stream` serve different audiences. The non-streaming endpoint returns a complete JSON object with all metadata — easy for evaluation tools to parse. The streaming endpoint returns tokens as they arrive — the right experience for users.

---

## File 6 — `backend/chains/chat_chain.py`

**What it is:** The LangChain integration — where GPT-4o actually gets called.

**Where it fits:** Called by the chat route. The deepest point in the chat flow before a response starts coming back.

**How it works:**
This file manages three things: the LLM configuration, the conversation memory store, and the chain that connects them.

**Key functions:**

`get_llm()` — creates a fresh `ChatOpenAI` instance with `model="gpt-4o"`, `temperature=0.7`, and `streaming=True`. Temperature 0.7 gives natural conversational variation.

`get_or_create_memory(session_id)` — looks up the conversation history for a session ID. If none exists, creates a new `ChatMessageHistory` object and stores it in the module-level `_memory_store` dict.

`chat(message, session_id)` — the non-streaming call. Builds a prompt template with the `ARIA_SYSTEM_PROMPT`, a `MessagesPlaceholder` for conversation history, and the new user message. Wraps the chain with `RunnableWithMessageHistory`.

`chat_stream(message, session_id)` — same as `chat()` but uses `chain_with_history.astream()`. An async generator that yields each token chunk.

**`ARIA_SYSTEM_PROMPT`** — the constant at the top of the file. ARIA's instruction set — her identity, what she helps with, and her behavioural guidelines. Every GPT-4o call starts with this prompt.

**The design decision worth noting:**
`RunnableWithMessageHistory` replaced the deprecated `ConversationChain` from LangChain 0.3+. It separates the chain logic from the memory management — the chain itself is just `prompt | llm`, and `RunnableWithMessageHistory` wraps it to add history lookup and storage.

---

## The Complete Chat Flow — One Message

```
1. User types "Hello ARIA" → st.chat_input() captures it
2. app.py calls GET /rag/classify → returns "chat"
3. app.py routes to stream_response()
4. stream_response() opens POST /chat/stream with httpx.stream()
5. routes/chat.py receives ChatRequest → validates via schemas/chat.py
6. route calls chat_stream(message, session_id)
7. chat_chain.py: get_or_create_memory(session_id) → empty history first time
8. chat_chain.py: builds prompt (system + empty history + "Hello ARIA")
9. RunnableWithMessageHistory invokes chain → astream() to GPT-4o
10. GPT-4o generates tokens → each arrives as AIMessageChunk
11. chat_stream() yields each chunk.content string
12. route wraps each token: data: {"token": "Hello"}\n\n → StreamingResponse
13. stream_response() in app.py receives each SSE line → yields token
14. st.write_stream() appends each token to chat bubble → user sees "Hello..."
15. Stream ends → st.write_stream() returns complete text
16. app.py saves to session_state.messages → conversation history updated
```

---

## Journey 1 — DeepEval Evaluation

### The Evaluation Flow

```
evaluation/datasets/chat_golden_set.json    the answer key — 20 questions + expected answers
        ↓ loaded once by the golden_set fixture
evaluation/tests/test_chat.py               pytest collects 5 test functions
        ↓ each test function calls get_aria_response()
backend/api/routes/chat.py                  POST /chat/ — same endpoint Streamlit uses
        ↓ ARIA answers via GPT-4o and memory
evaluation/tests/test_chat.py               actual response collected
        ↓ LLMTestCase built: input + actual_output + expected_output
DeepEval evaluate()                         sends to judge LLM
        ↓ GPT-4o reads question + answer + evaluation criteria
        ↓ returns score (0.0–1.0) + plain English reasoning
pytest                                      asserts all scores above threshold
```

### File: `evaluation/datasets/chat_golden_set.json`

**What it is:** The answer key — 20 manually written question and expected answer pairs.

**Where it fits:** Loaded once at test startup and shared across all five test functions. Nothing generates this automatically — it is deliberately hand-authored because it encodes what *you* consider a correct answer.

**How it works:**
The first 10 entries cover standard HR knowledge. The next 10 are deliberate edge cases: vague questions, company-specific data ARIA doesn't have, emotionally sensitive scenarios, legally sensitive termination questions, and one intentional off-topic question. These edge cases are kept as intentional failures — a test suite that only asks easy questions is not a quality gate.

### File: `evaluation/tests/test_chat.py`

**What it is:** Five test functions that collectively prove the chat journey works correctly across different question types and failure modes.

**`get_aria_response(question)`** — the helper function used by every test. Posts to `POST /chat/` with a `session_id` derived deterministically from the question using `hash(question) % 100000`. The same question always generates the same session ID.

**The Three Metrics:**

`GEval` — HR Role Adherence: written evaluation criteria in plain English, graded by GPT-4o. Checks persona, HR-only topics, off-topic redirection, and professionalism.

`AnswerRelevancyMetric` — generates hypothetical questions that ARIA's response would answer well, measures how many match the original.

`HallucinationMetric` — with `context=[]`, any specific factual claim is treated as potentially invented. Score of `0.00` means zero hallucination.

### Phase 1 Baseline Results

**24 test cases, 100% pass rate, $0.19 cost, ~72 seconds**

| Test Function | Metric | Avg Score | Pass Rate | Cases |
|---|---|---|---|---|
| `test_aria_responds_to_hr_questions` | HR Role Adherence | 0.98 | 100% | 8 |
| `test_aria_responds_to_hr_questions` | Answer Relevancy | 0.98 | 100% | 8 |
| `test_aria_rejects_non_hr_questions` | HR Role Adherence | 1.00 | 100% | 1 |
| `test_aria_no_hallucination` | Hallucination | 0.00 | 100% | 5 |
| `test_aria_handles_sensitive_questions` | HR Role Adherence | 0.93 | 100% | 5 |
| `test_aria_handles_sensitive_questions` | Answer Relevancy | 1.00 | 100% | 5 |
| `test_aria_handles_knowledge_boundary_questions` | Hallucination | 0.00 | 100% | 5 |

---

# JOURNEY 2 — DOCUMENT RAG

## The RAG Request Flow

```
User types policy question in browser
        ↓
frontend/app.py              calls /rag/classify first
        ↓ GET /rag/classify
backend/api/routes/rag.py    calls classify_query()
        ↓
backend/chains/rag_router.py GPT-4o classifies as "rag"
        ↓
frontend/app.py              routes to stream_rag()
        ↓ POST /rag/stream
backend/api/routes/rag.py    calls rag_query_stream()
        ↓
rag/document_rag/chain.py    orchestrates retrieval + generation
        ↓
rag/document_rag/retriever.py finds relevant chunks
        ↓
vector_store/store.py        searches ChromaDB by similarity
        ↓
rag/document_rag/chain.py    sends context + question to GPT-4o
        ↓ tokens + metadata stream back up
frontend/app.py              renders answer + citations
```

**Before a RAG query can work, three setup steps must have run:**

```
scripts/create_documents.py → 4 HR policy PDFs created
        ↓
rag/document_rag/ingestion.py → PDFs → clean text pages
        ↓
rag/document_rag/chunker.py → pages → sized text chunks
        ↓
vector_store/indexer.py → chunks → embeddings → ChromaDB
```

---

## Setup File 1 — `scripts/create_documents.py`

**What it is:** A one-time script that generates the four HR policy PDFs using PyMuPDF.

**Where it fits:** Runs once before indexing. Its output lives in `documents/policies/` and `documents/handbooks/`.

**How it works:**
Uses `fitz` (PyMuPDF) to create PDF files programmatically from Python strings. Each document has exact numbers like "25 days annual leave", "16 weeks parental leave".

**The design decision worth noting:**
Every major section is separated by `\n\n` (double newline). `RecursiveCharacterTextSplitter` tries `\n\n` as its first split point — without it, the Annual Leave section and Sick Leave section might land in the same chunk. The parental leave retrieval bug during Phase 2 was caused by exactly this.

---

## Setup File 2 — `rag/document_rag/ingestion.py`

**What it is:** The first step of the RAG pipeline — reads PDFs and produces clean text with metadata.

**Key functions:**

`clean_text(text)` — removes artifacts: multiple consecutive spaces, very short lines (usually page numbers), and excessive blank lines.

`extract_pages(pdf_path)` — opens a PDF, iterates page by page, cleans each page's text, and yields `DocumentPage` objects. Uses `yield` — memory efficient for large documents.

`load_all_documents()` — scans `documents/` recursively for all `.pdf` files. Returns a flat list of all `DocumentPage` objects.

**The design decision worth noting:**
Pages where cleaned text is under 50 characters are skipped — they are essentially empty after cleaning.

---

## Setup File 3 — `rag/document_rag/chunker.py`

**What it is:** The second step — splits pages into retrieval-sized pieces.

**Key functions:**

`create_splitter(chunk_size, chunk_overlap)` — creates a `RecursiveCharacterTextSplitter` with separator priority `["\n\n", "\n", ". ", " ", ""]`. Phase 2 uses `chunk_size=800` and `chunk_overlap=100`.

`chunk_page(page, splitter)` — splits one `DocumentPage`, filters chunks shorter than 50 characters, creates `DocumentChunk` objects carrying all metadata from the parent page.

**The design decision worth noting:**
`chunk_overlap=100` means the last 100 characters of chunk N are repeated at the start of chunk N+1. This prevents policy clauses that straddle a chunk boundary from being split where neither chunk contains the complete thought.

---

## Setup File 4 — `vector_store/store.py`

**What it is:** The ChromaDB connection and all vector operations.

**Key functions:**

`add_chunks(chunks)` — embeds chunk text using `OpenAIEmbeddings` with `text-embedding-3-small`, stores vectors in ChromaDB. Called once during indexing.

`query(question, top_k)` — embeds the question using the same embedding model, asks ChromaDB for the `top_k` most similar vectors.

`reset()` — deletes and recreates the collection. Used when re-indexing after document changes.

**The design decision worth noting:**
The same embedding model must be used for both indexing and querying — filing alphabetically and searching numerically would make similarity scores meaningless. A single `embeddings` object in `VectorStore.__init__()` enforces this.

---

## Setup File 5 — `vector_store/indexer.py`

**What it is:** The orchestrator that runs the full ingestion pipeline.

**Key functions:**

`index_documents(reset)` — if `reset=True`, clears existing vectors. Checks if already indexed (`vector_store.count() > 0`) and returns early if so — idempotent. Otherwise calls `chunk_all_documents()` then `vector_store.add_chunks()`.

**The design decision worth noting:**
The idempotency check means you can run the indexer multiple times safely. Only when `reset=True` does it clear and reindex.

---

## Runtime File 1 — `backend/schemas/rag.py`

**What it is:** The data contract for the RAG API.

**How it works:**
`RAGRequest` — `question` (required), `session_id` (auto-generated), `top_k` (default 3, capped 1–10).

`RAGResponse` — `answer`, `sources` (list of citations), `chunks_used`, `query`, `session_id`, `model` (`"gpt-4o-rag"`).

Phase 3 adds `DatabaseRAGRequest` (simpler, no `top_k`) and `DatabaseRAGResponseModel` (adds `sql_used`, `row_count`, `success`).

**The design decision worth noting:**
`RAGResponse` includes `sources` that `ChatResponse` doesn't — RAG answers must be traceable to the document they came from.

---

## Runtime File 2 — `backend/chains/rag_router.py`

**What it is:** The traffic controller — decides which journey handles each request.

**How it works:**

`classify_query(question)` — sends the question to GPT-4o at `temperature=0`. Returns one of five values after Phase 5: `"mcp"`, `"agent"`, `"rag"`, `"db"`, or `"chat"`. If GPT-4o returns anything else, defaults to `"rag"`.

**Phase evolution of the router:**
- Phase 2: three-way (`rag` / `db` / `chat`)
- Phase 4: four-way (adds `agent`)
- Phase 5: five-way (adds `mcp`, which takes highest priority)

**The design decision worth noting:**
The classify endpoint function is named `classify_query_endpoint` not `classify_query` — to avoid a Python name collision with the imported `classify_query` from `rag_router.py`. If both had the same name, the endpoint would call itself recursively.

---

## Runtime File 3 — `rag/document_rag/retriever.py`

**What it is:** The search interface — converts a question into relevant document chunks.

**Key functions:**

`format_citation(source, page_number)` — converts `"leave_policy.pdf"` to `"Leave Policy, Page 1"`.

`retrieve(query, top_k, min_similarity)` — calls `vector_store.query()`, converts distances to similarity scores (`1 - distance`), filters below `min_similarity=0.3`.

`retrieve_with_context(query, top_k)` — assembles the chunk list into one formatted string with citations interleaved. This string is what gets injected into the GPT-4o prompt.

**The design decision worth noting:**
The chain never calls `vector_store.query()` directly — it calls `retrieve_with_context()`. Swapping vector databases or adding hybrid search means only changing `retriever.py`.

---

## Runtime File 4 — `rag/document_rag/chain.py`

**What it is:** The RAG orchestrator.

**Key functions:**

`build_rag_prompt()` — `ChatPromptTemplate` with the RAG system prompt and a human message with `{context}` and `{question}` variables.

`get_rag_llm()` — `ChatOpenAI` at `temperature=0.1` — significantly lower than chat's `0.7`. RAG answers must be factual and consistent.

`rag_query(question)` — non-streaming, used by DeepEval.

`rag_query_stream(question)` — streaming, used by Streamlit. Yields tokens then yields the source list.

**`RAG_SYSTEM_PROMPT`** — instructs: answer ONLY from the context provided, always cite the source, say so explicitly if the context doesn't contain the answer. The `ONLY` constraint is what prevents hallucination.

---

## Runtime File 5 — `backend/api/routes/rag.py`

**What it is:** The RAG endpoint handler.

**How it works:**
An `APIRouter` with `prefix="/rag"`. Key endpoints:

`GET /classify` — calls `classify_query()`, fallback to `"rag"` on error.

`POST /query` — non-streaming, for DeepEval.

`POST /stream` — streaming, for Streamlit. After all tokens, sends one metadata event `{"sources": [...], "chunks_used": N}`. Then `{"token": "[DONE]"}`.

`GET /status` — returns ChromaDB vector count for the sidebar display.

Phase 3 adds `POST /rag/db/query` and `POST /rag/db/stream`.

---

## The Complete RAG Flow — One Message

```
1. User types "What is the parental leave policy?"
2. app.py calls GET /rag/classify → "rag"
3. app.py calls stream_rag()
4. stream_rag() opens POST /rag/stream
5. routes/rag.py receives RAGRequest → validates
6. route calls rag_query_stream(question)
7. chain.py calls retrieve_with_context(question, top_k=3)
8. retriever.py calls vector_store.query(question, top_k=3)
9. store.py embeds question → ChromaDB finds 3 similar vectors
10. retriever.py formats citations: "Leave Policy, Page 1"
11. chain.py builds context_text: "[Leave Policy, Page 1]\nPrimary caregiver: 16 weeks..."
12. chain.py builds prompt: RAG_SYSTEM_PROMPT + context_text + question
13. GPT-4o at temperature=0.1 generates grounded answer
14. chain.py yields each token via astream()
15. route wraps tokens as SSE events → StreamingResponse
16. After all tokens: data: {"sources": ["Leave Policy, Page 1"], "chunks_used": 3}
17. data: {"token": "[DONE]"}
18. stream_rag() in app.py: captures sources → session_state.last_sources
19. stream_rag() yields tokens to st.write_stream()
20. st.write_stream() renders answer, returns complete text
21. app.py displays: st.caption("📄 Sources: Leave Policy, Page 1")
```

---

## Journey 2 — DeepEval Evaluation

### File: `evaluation/datasets/rag_golden_set.json`

**What it is:** 15 questions with specific citable expected answers, one per major policy area. Each entry has `input`, `expected_output`, and `document`.

### File: `evaluation/tests/test_document_rag.py`

**`get_rag_response(question)`** — posts to `POST /rag/query`, returns full response dict with `answer`, `sources`, `chunks_used`. `time.sleep(0.5)` spaces calls.

**`get_retrieval_context(question)`** — calls `retrieve()` directly, returns the list of chunk texts. This is `retrieval_context` for every test case — the raw material for Faithfulness, Precision, and Recall metrics.

**The critical addition — `retrieval_context`** — is the field that separates RAG evaluation from chat evaluation. Without it, DeepEval can only measure answer quality. With it, it can measure whether the answer faithfully reflects the chunks, whether chunks were ranked correctly, and whether the chunks were complete.

### The Four RAG Metrics

`FaithfulnessMetric` — checks every factual claim in ARIA's answer against the retrieved chunks. Score `1.00` means every claim traces back to retrieved text. Threshold `0.8`.

`ContextualPrecisionMetric` — measures whether the most relevant chunk is ranked first. The parental leave retrieval bug was a precision problem — fixed by increasing chunk size and adding section separators. Threshold `0.7`.

`ContextualRecallMetric` — measures whether retrieved chunks contain all information needed to produce the expected answer. Multi-part answers like the harassment reporting steps need all four steps in context. Threshold `0.7`.

`AnswerRelevancyMetric` — carried from Phase 1 as a regression check. Improved from `0.98` to `1.00` because grounded answers are more focused. Threshold `0.7`.

### Phase 2 Baseline Results

**26 test cases, 100% pass rate, $0.07 total cost, ~57 seconds**

| Test Function | Metric | Avg Score | Pass Rate | Cases | Cost |
|---|---|---|---|---|---|
| `test_rag_faithfulness` | Faithfulness | 1.00 | 100% | 3 | $0.029 |
| `test_rag_contextual_precision` | Contextual Precision | 1.00 | 100% | 3 | $0.018 |
| `test_rag_contextual_recall` | Contextual Recall | 1.00 | 100% | 2 | $0.011 |
| `test_rag_answer_relevancy` | Answer Relevancy | 1.00 | 100% | 3 | $0.012 |
| `test_rag_document_routing` | Routing assertion | 100% | 100% | 15 | $0.000 |

---

# JOURNEY 3 — DATABASE RAG

## The Database RAG Request Flow

```
User types employee question in browser
        ↓
frontend/app.py              calls /rag/classify first → "db"
        ↓ POST /rag/db/stream
backend/api/routes/rag.py    calls db_rag_query_stream()
        ↓
rag/database_rag/chain.py    orchestrates NL-to-SQL + execution + generation
        ↓
rag/database_rag/nl_to_sql.py converts question to validated SQL
        ↓
rag/database_rag/executor.py  runs SQL against PostgreSQL
        ↓
rag/database_rag/chain.py     sends DB rows + question to GPT-4o
        ↓ tokens + metadata stream back up
frontend/app.py               renders answer + SQL expander + record count badge
```

**The four-stage pipeline:**
```
Stage 1: generate_validated_sql(question)    GPT-4o → SELECT → validate_sql()
Stage 2: execute_query(sql)                  SQLAlchemy → PostgreSQL → QueryResult
Stage 3: format_results_for_llm(result)      Rows → human-readable text
Stage 4: GPT-4o with DB_ANSWER_SYSTEM_PROMPT → natural language answer
```

---

## File 1 — `rag/database_rag/schema.py`

**What it is:** The database schema description embedded directly into the NL-to-SQL prompt.

**How it works:**
`DATABASE_SCHEMA_DESCRIPTION` describes all three tables with column names, types, and allowed enum values. Also includes SQL rules: always use table aliases, use `ILIKE` for names, default `LIMIT 10`, never `SELECT *`.

`get_full_context()` — combines the static schema description with live sample rows from each table. Gives GPT-4o concrete examples of what the data looks like.

**The design decision worth noting:**
Schema description is a static constant, not a live `information_schema` query. A hand-authored description includes business rules — enum values, join conventions — that auto-generated schema metadata doesn't.

---

## File 2 — `rag/database_rag/nl_to_sql.py`

**What it is:** The NL-to-SQL engine — converts a question into a validated PostgreSQL SELECT statement.

**Key functions:**

`generate_sql(question)` — GPT-4o at `temperature=0` (SQL generation must be deterministic), returns the stripped SQL string.

`validate_sql(sql)` — two hard checks: must start with `SELECT`, must not contain dangerous keywords (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`, `CREATE`, `GRANT`, `REVOKE`) detected via word-boundary regex.

`generate_validated_sql(question)` — async wrapper. Checks for `NOT_DB_QUERY` sentinel, then calls `validate_sql()`. Returns `(sql, is_valid, error_message)`.

**The `NOT_DB_QUERY` sentinel:**
When GPT-4o determines the question cannot be answered from the database, it returns the literal string `NOT_DB_QUERY`. This sentinel travels up the entire stack — chain, API endpoint, streaming endpoint, Streamlit — keeping the failure path explicit at every layer without exceptions.

---

## File 3 — `rag/database_rag/executor.py`

**What it is:** The SQL execution layer.

**Key functions:**

`execute_query(sql)` — creates a SQLAlchemy engine from `settings.database_url`, executes the SQL, converts each row to a dict, serializes `datetime.date` values to ISO format strings. On error, returns a failed `QueryResult` with the error message — never surfaced raw to the user.

`format_results_for_llm(result)` — converts `QueryResult` to human-readable text. This text goes into `retrieval_context` in DeepEval test cases and into the GPT-4o prompt at Stage 4.

**The design decision worth noting:**
Date serialization happens in `execute_query()`. SQLAlchemy returns Python `datetime.date` objects which can't be JSON-serialized directly. Serializing at the executor level means every layer above works with plain strings.

---

## File 4 — `rag/database_rag/chain.py`

**What it is:** The DB RAG orchestrator.

**How it works:**
`DB_ANSWER_SYSTEM_PROMPT` — the most important rule placed first: for WHO questions, respond with ONLY the person's name and the direct answer. No role, no department, no location unless explicitly asked. This rule required three iterations during development.

`db_rag_query(question)` — async, non-streaming. Runs all four stages. Used by DeepEval.

`db_rag_query_stream(question)` — async generator. Same four stages but Stage 4 uses streaming. Used by Streamlit.

`temperature=0` for Stage 4 — ARIA must say "30 days" when the database says `leave_balance: 30`. Any temperature above zero risks paraphrasing numbers.

---

## The Complete DB RAG Flow — One Message

```
1. User types "How many leave days does James Chen have?"
2. app.py calls GET /rag/classify → "db"
3. app.py calls stream_db()
4. stream_db() opens POST /rag/db/stream
5. routes/rag.py calls db_rag_query_stream(question)
6. chain.py calls generate_validated_sql(question)
7. nl_to_sql.py: GPT-4o generates SELECT with ILIKE name match
8. validate_sql() confirms: starts with SELECT, no dangerous keywords
9. chain.py calls execute_query(sql)
10. executor.py: SQLAlchemy → QueryResult(rows=[{leave_balance: 30}], row_count=1)
11. chain.py calls format_results_for_llm(result)
12. chain.py builds prompt: DB_ANSWER_SYSTEM_PROMPT + question + sql + rows
13. GPT-4o at temperature=0 generates: "James Chen has 30 days of leave remaining."
14. chain.py yields tokens via astream()
15. route runs db_rag_query() second time to get sql_used + row_count metadata
16. data: {"sql_used": "SELECT e.employee_id...", "row_count": 1}
17. data: {"token": "[DONE]"}
18. stream_db() captures sql_used → session_state.last_sql_used
19. st.write_stream() renders answer
20. app.py shows: st.caption("🗄️ Answered from employee database · 1 record(s) found")
21. app.py shows: st.expander("View database query") → st.code(sql, language="sql")
```

---

## Journey 3 — DeepEval Evaluation

### File: `evaluation/datasets/database_rag_golden_set.json`

**What it is:** 10 questions across three query types: `"employee_lookup"` (5 entries), `"aggregate"` (3 entries), `"join"` (2 entries).

**Expected outputs are verifiable:** "James Chen has 30 days of leave remaining." — exact number from the database. "Isabella Fernandez is currently on leave." — name only, matching the WHO rule.

### File: `evaluation/tests/test_database_rag.py`

**`get_db_context(question)`** — calls `generate_validated_sql()` and `execute_query()` directly, then `format_results_for_llm()`. Returns `[formatted_result_string]`. This is `retrieval_context` for every DB RAG test case — the formatted SQL rows the Stage 4 GPT-4o call saw.

**The critical difference from Document RAG:** `retrieval_context` is the formatted SQL result rather than chunk texts. The Faithfulness judge checks ARIA's claims against the SQL rows.

### Phase 3 Baseline Results

| Test Function | Metric | Pass Rate | Cases | Cost |
|---|---|---|---|---|
| `test_db_routing_boundary` | Routing assertion | **100%** | 13 | $0.000 |
| `test_db_employee_lookup` | Faithfulness + Relevancy | 100% | 3 | ~$0.030 |
| `test_db_aggregate_queries` | Faithfulness + Relevancy | 100% | 3 | ~$0.030 |
| `test_db_join_queries` | Faithfulness + Relevancy | 100% | 2 | ~$0.020 |

---

# JOURNEY 4 — AGENT

## The Agent Request Flow

```
User types compound question in browser
        ↓
frontend/app.py              calls /rag/classify → "agent"
        ↓ POST /agent/query
backend/api/routes/agent.py  validates, calls run_hr_advisor()
        ↓
agents/single/hr_advisor.py  ReAct agent reasons over which tools to call
        ↓
agents/single/tools.py       Phase 4 direct tools (3 tools):
        ↓ search_policies → vector_store/searcher.py → ChromaDB
        ↓ lookup_employee → rag/database_rag/chain.py → PostgreSQL
        ↓ search_knowledge_base → vector_store/searcher.py → ChromaDB
        ↓ agent forms final answer
backend/api/routes/agent.py  returns AgentQueryResponse with steps + tools_used
        ↓
frontend/app.py              renders answer + tool badges + reasoning trace expander
```

**Unlike Journeys 2 and 3, there is no streaming in Journey 4.** The agent must complete all reasoning steps before any answer can be formed. The full `AgentQueryResponse` arrives at once.

**The ReAct reasoning loop:**
```
Iteration 1:
  Thought: Which tool should I use?
  Action: search_policies("remote work policy")
  Observation: [retrieved policy text]

Iteration 2:
  Thought: I have the policy. Now I need James Chen's data.
  Action: lookup_employee("James Chen leave balance")
  Observation: "James Chen has a leave balance of 30 days."

Thought: I now have enough information.
Final Answer: "The remote work policy... James Chen has 30 days."
```

---

## Updated File — `backend/chains/rag_router.py` (Phase 4 update)

**What changed in Phase 4:**
A fourth classification value — `"agent"` — was added to the system prompt. The new rule: if a question requires retrieving from BOTH policy documents AND the employee database to fully answer it, classify as `"agent"`. Single-source questions remain `"rag"` or `"db"`.

**Why `"agent"` rather than splitting into two requests:**
A compound question has one intent. Sending it to `"rag"` answers only the policy half. Sending it to `"db"` answers only the employee half. The agent handles both in a single response.

---

## New File 1 — `vector_store/searcher.py`

**What it is:** A standalone semantic search interface that wraps ChromaDB for use by the agent tools.

**Key functions:**

`semantic_search(query, n_results, min_score)` — calls `vector_store.query()`, converts distances to similarity scores, filters below `min_score`, sorts by score descending.

`format_search_results(results)` — formats each result as `[Source: citation]\nchunk_text` separated by `---` dividers.

`search_and_format(query, n_results)` — convenience wrapper. This is what the agent tools actually call. Also used directly by `policy_lookup_tool.py` in Phase 5.

**The design decision worth noting:**
The agent tools always receive formatted, citation-annotated text — never raw ChromaDB output. If the vector store backend changes, only `searcher.py` needs updating.

---

## New File 2 — `agents/single/tools.py`

**What it is:** The three Phase 4 LangChain tools that form the agent's direct action set.

**`search_policies(query)`** — calls `search_and_format(query, n_results=3)`. Description: use for HR policies, rules, entitlements. Explicitly: do NOT use if the question mentions a specific employee by name.

**`lookup_employee(query)`** — calls `db_rag_query(query)` via `asyncio.run()` — converting async to sync for the LangChain tool interface. Description: use when the question mentions a person by name. If `NOT_DB_QUERY` is returned, redirects to `search_policies`.

**`search_knowledge_base(query)`** — calls `search_and_format(query, n_results=5)` — more results for broader questions. Description: for broad HR questions that don't mention a specific employee or policy clause.

**`HR_ADVISOR_TOOLS`** — module-level list of all three tool instances. This is what gets passed to the agent's tool list in `hr_advisor.py`. Phase 5 extends this with MCP tools at runtime.

**The design decision worth noting:**
`asyncio.run()` inside `lookup_employee` creates a temporary event loop. This works in synchronous contexts but fails inside a running async event loop. The Phase 4 route calls `run_hr_advisor()` synchronously — this boundary is what makes it safe.

---

## New File 3 — `agents/single/hr_advisor.py` (Phase 4 version)

**What it is:** The Single HR Advisor agent — the LangChain ReAct agent that reasons, calls tools, and forms answers.

**`HR_ADVISOR_SYSTEM_PROMPT`** — the agent's instruction set. Includes: always use a tool before answering, never answer from memory alone, cite sources, for compound questions call multiple tools in sequence. Phase 5 updates this to still work correctly with both direct tools and MCP tools.

**`AgentResponse`** — a dataclass with `answer`, `steps` (list of dicts with `thought`, `tool`, `tool_input`, `observation`), `tools_used`, and `success`. The stable interface between the agent and everything above it.

**`get_llm()`** — creates `ChatOpenAI` at `temperature=0`. Agent reasoning must be deterministic.

**`build_hr_advisor()`** — creates and returns a compiled LangGraph agent using `create_agent(model=get_llm(), tools=HR_ADVISOR_TOOLS, system_prompt=HR_ADVISOR_SYSTEM_PROMPT)`. Returns a `CompiledStateGraph` directly — no `AgentExecutor` wrapper in LangChain 1.3.1.

**`run_hr_advisor(question)`** — invokes the agent with `{"messages": [{"role": "user", "content": question}]}`, extracts the final answer from `result["messages"][-1].content`, walks the message list looking for `msg.tool_calls` to build the step list, and returns a populated `AgentResponse`.

**The design decision worth noting:**
`build_hr_advisor()` is called inside `run_hr_advisor()` on every request — the agent is stateless and created fresh per request. A module-level singleton would require thread-safety handling because the agent is not designed for concurrent access.

---

## New File 4 — `backend/api/routes/agent.py`

**What it is:** The agent endpoint handler.

**`POST /agent/query`** — accepts `AgentRequest` (a Pydantic model with a `question` field), calls `run_hr_advisor(request.question)`, checks `result.success`, returns `AgentQueryResponse`. If the agent failed, raises `HTTPException(500)`.

**`AgentQueryResponse`** — `answer`, `tools_used`, `steps`, `success`, `question`. The `steps` field is `list[dict]` — each dict has `thought`, `tool`, `tool_input`, `observation` (truncated to 300 characters in `hr_advisor.py`).

**The design decision worth noting:**
No streaming variant — the reasoning loop must complete before any answer is available. Streaming partial reasoning traces adds significant complexity for limited user benefit.

---

## The Complete Agent Flow — One Message

```
1. User types "What is the remote work policy and how many days does James Chen have?"
2. app.py calls GET /rag/classify → "agent"
3. app.py calls get_agent_response() → POST /agent/query
4. routes/agent.py calls run_hr_advisor(question)
5. hr_advisor.py: create_agent() builds compiled graph with 3 direct tools
6. agent.invoke({"messages": [{"role": "user", "content": question}]})

   --- Iteration 1 ---
7. Agent reads question + tool descriptions + empty message history
8. Agent decides: remote work policy → search_policies
9. tools.py: search_and_format("remote work policy", n_results=3) → policy text
10. Agent receives policy text as tool result, appended to messages

   --- Iteration 2 ---
11. Agent reads updated messages including policy observation
12. Agent decides: "James Chen" → lookup_employee
13. tools.py: asyncio.run(db_rag_query("James Chen leave balance"))
14. db chain: generate_validated_sql() → execute → GPT-4o → "30 days"
15. Agent receives "James Chen has a leave balance of 30 days." as tool result

   --- Final ---
16. Agent forms Final Answer combining both sources
17. run_hr_advisor() extracts answer from result["messages"][-1].content
18. Walks messages for tool_calls → builds step dicts
19. Returns AgentResponse(answer, steps=[step1, step2], tools_used=[...], success=True)
20. routes/agent.py returns AgentQueryResponse JSON
21. app.py renders: answer + tool badges + reasoning trace expander
```

---

## Journey 4 — DeepEval Evaluation

### File: `evaluation/datasets/agent_golden_set.json`

**What it is:** 10 questions with `input`, `expected_output`, `query_type` (`"policy"`, `"employee"`, `"compound"`), and `expected_tools` (list of tool names).

`expected_tools` is the new addition compared to earlier golden sets — the ground truth for `ToolCorrectnessMetric`.

### File: `evaluation/tests/test_single_agent.py`

**`build_test_case(item)`** — creates `LLMTestCase` with two new fields:
- `tools_called` — list of `ToolCall(name=tool)` objects from `result["tools_used"]`
- `expected_tools` — list of `ToolCall(name=tool)` from `item["expected_tools"]`

Without these two fields, `ToolCorrectnessMetric` has nothing to score.

**`time.sleep(3.0)`** after each agent call — necessary because the agent makes multiple LLM calls per question. Running back-to-back without breathing room reliably hits the 30,000 TPM rate limit.

### The Three Agent Metrics

`TaskCompletionMetric(threshold=0.7, model="gpt-4o")` — LLM judge evaluates whether the agent fully accomplished what the user asked. Average across Phase 4 tests: 0.95.

`ToolCorrectnessMetric(threshold=0.8)` — deterministic set comparison. No LLM judge. Checks that every tool in `expected_tools` appears in `tools_called` (unordered). Binary per test case: 1.0 if all expected tools called, 0.0 if any missing. Phase 4 result: 1.00 across all 19 cases.

`AnswerRelevancyMetric(threshold=0.7, model="gpt-4o")` — carried from Journeys 2 and 3. Average: 0.90.

### Phase 4 Baseline Results

| Test Function | Metrics | Pass Rate | Cases | Cost | Time |
|---|---|---|---|---|---|
| `test_agent_policy_queries` | TaskCompletion + ToolCorrectness + AnswerRelevancy | **100%** | 3 | ~$0.025 | ~15s |
| `test_agent_employee_queries` | ToolCorrectness + AnswerRelevancy | **100%** | 3 | ~$0.010 | ~20s |
| `test_agent_compound_queries` | TaskCompletion + ToolCorrectness + AnswerRelevancy | **100%** | 3 | ~$0.025 | ~20s |
| `test_agent_tool_correctness_boundary` | ToolCorrectness only | **100%** | 10 | $0.000 | ~40s |
| **Total Phase 4** | | **100%** | **19** | **$0.073** | **~115s** |

---

# JOURNEY 5 — MCP

## The MCP Request Flow

```
User types "Submit Annual leave for EMP-0001 from 2027-06-16 to 2027-06-18"
        ↓
frontend/app.py              calls /rag/classify → "mcp"
        ↓ POST /mcp/query
backend/api/routes/mcp_agent.py  validates, awaits run_hr_advisor_with_mcp()
        ↓
agents/single/hr_advisor.py      8-tool agent (3 direct + 5 MCP)
        ↓ MultiServerMCPClient fetches 5 MCP tools from port 8002
        ↓ agent calls submit_leave_request via MCP HTTP protocol
        ↓ HTTP:8002/mcp → FastMCP server receives call
mcp_server/tools/leave_tool.py   submit_leave_request() runs
        ↓ engine.begin() → validates employee → duplicate check → INSERT
        ↓ "Leave request submitted successfully..."
        ↓ result travels back through MCP → agent → AgentResponse
backend/api/routes/mcp_agent.py  returns MCPAgentResponse
        ↓
frontend/app.py              renders 🔧 MCP Action badge + confirmation banner + tool badges
```

**The fundamental shift from Journey 4:**
```
Journey 4 — Tools as direct Python function calls:
  Agent → tools.py → search_and_format() → ChromaDB (read)
  Agent → tools.py → db_rag_query()      → PostgreSQL (read)

Journey 5 — Tools as an HTTP network service:
  Agent → MultiServerMCPClient → HTTP:8002/mcp → FastMCP server
                                                       ↓
                                      check_leave_balance  → PostgreSQL (read)
                                      submit_leave_request → PostgreSQL (WRITE)
                                      cancel_leave_request → PostgreSQL (DELETE)
                                      get_org_chart        → PostgreSQL (read)
                                      policy_lookup        → ChromaDB (read)
```

**Why MCP and not more direct tools:**
MCP (Model Context Protocol) is Anthropic's open standard for connecting AI agents to external tools and systems. The FastMCP server on port 8002 is independent of the agent — Claude Desktop, Cursor, or any future ARIA agent can call the same tools without touching this codebase. This is the difference between tools baked into an agent and tools as a network service.

**The two routing boundaries — how the agent decides which tool to call:**
The Phase 4 direct tools accept natural language: names, phrases, questions. Their descriptions say "use this when the question mentions a person by name." The MCP tools accept structured inputs: EMP-IDs in `EMP-XXXX` format, YYYY-MM-DD dates, leave type enums. Their descriptions say "employee_id must be in EMP-XXXX format." This description difference is what produces correct routing — no hardcoded rules, just well-engineered tool descriptions. EMP-ID format → MCP tool. Name format → Phase 4 direct tool.

---

## New File 1 — `mcp_server/server.py`

**What it is:** The FastMCP server entry point — the process that runs on port 8002 and exposes all five HR action tools over HTTP.

**Where it fits:** A completely separate Python process from the FastAPI backend. Started independently with `uv run python scripts/start_mcp_server.py`. Any process — the ARIA agent, Claude Desktop, Cursor — can call its tools via the MCP protocol.

**How it works:**
Creates a `FastMCP` instance named `"ARIA HR MCP Server"` with an `instructions` string that describes the server's purpose and input format requirements to any connecting LLM client. The `instructions` field is read by the MCP client when it connects — it tells the agent what kinds of tasks these tools support.

After the `mcp` instance is created, three tool module imports follow: `from mcp_server.tools import leave_tool`, `org_chart_tool`, and `policy_lookup_tool`. These imports are deferred — placed after `mcp = FastMCP(...)` — because the `@mcp.tool` decorator in each tool file needs the `mcp` instance to exist at import time. If the imports were placed before the instance creation, the decorator would fail with a `NameError`. The deferred pattern is the FastMCP convention for multi-file tool registration.

The `if __name__ == "__main__"` block calls `mcp.run(transport="http", host="0.0.0.0", port=8002)`. This starts the HTTP server. The `transport="http"` setting uses FastMCP's Streamable HTTP transport, which requires a session handshake — raw `curl` cannot call the tools directly.

**Key concepts:**
- `@mcp.tool` decorator (no parentheses in FastMCP v3) turns any Python function into a registered MCP tool
- Docstrings become tool descriptions automatically — the connecting LLM reads these for tool selection decisions
- Type hints generate input schemas automatically — FastMCP uses them to validate parameters
- Functions remain callable as normal Python — they are not converted to objects or proxies

**The design decision worth noting:**
`mcp = FastMCP(...)` before the tool imports is not cosmetic. It is the required ordering. The module import chain is: `server.py` creates `mcp` → imports `leave_tool` → `leave_tool` imports `from mcp_server.server import mcp` → decorators fire against the already-created instance. Reversing the order breaks the import cycle.

---

## New File 2 — `mcp_server/tools/leave_tool.py`

**What it is:** Three FastMCP tools covering the full leave request lifecycle — balance check, submission, and cancellation. This is the most important file in Phase 5: it contains the first write operation and the first delete operation in the entire ARIA platform.

**Where it fits:** Imported by `server.py` after the `mcp` instance is created. Its three tools become registered endpoints callable via the MCP protocol.

**How it works:**
The file imports `mcp` from `mcp_server.server` — the same instance created in `server.py`. All three tools are decorated with `@mcp.tool` which registers each function as a callable MCP tool at import time.

Both `submit_leave_request` and `cancel_leave_request` use `engine.begin()` — SQLAlchemy's context manager for atomic write transactions. It auto-commits on success and auto-rolls back on any exception. No explicit `conn.commit()` or `conn.rollback()` calls are needed. `check_leave_balance` uses `engine.connect()` — a lighter read-only context manager with no transaction overhead.

**Tool 1 — `check_leave_balance(employee_id)`**

Validates the `employee_id` format (must start with `"EMP-"`) before touching the database. Opens a `engine.connect()` context, executes a SELECT against `employees` filtering by `employee_id`, and returns a string like "James Chen has 30 days of leave remaining. Status: Active". Returns a clear error string if the employee is not found. On `SQLAlchemyError`, logs the error and returns a database error string — never propagates the raw exception.

The docstring is the most important part: "employee_id must be in format EMP-XXXX e.g. EMP-0001" — this instruction is what causes the agent to invoke this tool for EMP-ID questions rather than the Phase 4 `lookup_employee` tool.

**Tool 2 — `submit_leave_request(employee_id, start_date, end_date, leave_type, reason)`**

Four validation steps before touching the database: employee_id format check, leave_type enum check against `["Annual", "Sick", "Parental", "Emergency", "Unpaid"]`, date parsing with `datetime.date.fromisoformat()`, and end_date ≥ start_date check. Each validation returns a descriptive error string on failure.

Inside a single `engine.begin()` transaction, three operations run in sequence: employee existence check (`SELECT employee_id FROM employees`), duplicate check (`SELECT id FROM leave_records WHERE employee_id AND start_date AND status='Pending'`), and the INSERT. If the duplicate check finds an existing pending record, the function returns an error string and the transaction rolls back without inserting. This prevents double-booking the same start date.

All three database operations share the same connection — they are part of one atomic transaction. If the INSERT fails after the employee check passed, no partial write occurs.

The confirmation message includes all key details: employee_id, date range, day count, leave type, and pending status. This is what the agent uses to form the final answer.

**Tool 3 — `cancel_leave_request(employee_id, start_date, leave_type)`**

Validates employee_id format and parses start_date. Uses a single `engine.begin()` context for both the SELECT and DELETE — the whole operation is one atomic transaction.

Inside the transaction: SELECT fetches all matching pending records (`status='Pending'`, matching employee_id and start_date, optionally matching leave_type if provided), ordered by id ascending. If no records are found, returns an error string and the transaction closes without deleting anything. If records are found, builds an `IN` clause with named parameters: `id_0`, `id_1`, etc. The DELETE fires in the same transaction. Both SELECT and DELETE commit or rollback together — no read/write split.

The `IN ({placeholders})` pattern is necessary because SQLAlchemy's `text()` layer does not correctly bind Python lists to PostgreSQL's `ANY(:ids)` operator — it transmits only the first element. Explicit named parameters (`id_0`, `id_1`, ...) in a dynamically built `IN` clause handle the full list correctly regardless of length.

The confirmation message branches on count: one record produces a single-cancel message with "has been removed"; multiple records produce a duplicate-count message with "have all been removed".

**The design decision worth noting:**
`cancel_leave_request` deliberately uses one `engine.begin()` for both SELECT and DELETE. An earlier version used `engine.connect()` for the SELECT and a separate `engine.begin()` for the DELETE — two separate transactions. Between those two transactions, another process could insert or delete the same record. The single-transaction design eliminates this race condition: the SELECT and DELETE are atomic.

---

## New File 3 — `mcp_server/tools/org_chart_tool.py`

**What it is:** One FastMCP tool — `get_org_chart` — that returns an employee's position, manager, and direct reports.

**Where it fits:** Imported by `server.py`. Registered as an MCP tool.

**How it works:**
`get_org_chart(employee_id)` validates the EMP-ID format, then opens one `engine.connect()` context for two sequential queries.

Query 1 — a three-table JOIN: `employees` joined to `org_chart` (to get level and team), then LEFT JOIN back to `employees` aliased as the manager (to get manager name and role). The `LEFT JOIN` is essential for top-level employees like James Chen (VP Engineering) who have no manager — without LEFT JOIN they would return no rows. The result gives the employee's name, role, department, level, team, manager_id, and manager details in a single row.

Query 2 — direct reports: employees whose `org_chart.manager_id` matches the queried employee_id. Ordered by last name.

Both queries run inside the same `engine.connect()` context — one connection, two queries. This is more efficient than opening two connections and guarantees both queries see a consistent database state.

The result is assembled into four lines: `"{name} — {role} ({department})"`, `"Team: {team} | Level: {level}"`, `"Reports to: {manager name} ({manager role})"` or `"Reports to: No manager (top level)"` when `manager_id` is None, and `"Direct reports ({count}): {name1} — {role1}, ..."` or `"Direct reports: None"`.

**The design decision worth noting:**
The single `engine.connect()` for both queries is not just efficiency — it provides read consistency. If direct reports were queried in a separate connection after the first connection closed, an intervening transaction could change the reporting structure between the two reads. The shared connection prevents this.

---

## New File 4 — `mcp_server/tools/policy_lookup_tool.py`

**What it is:** One FastMCP tool — `policy_lookup` — that exposes ChromaDB semantic search over HR policy documents to any MCP client.

**Where it fits:** Imported by `server.py`. The simplest of the five tools — it wraps one existing function.

**How it works:**
`policy_lookup(query)` logs the call (`query[:50]` to keep log lines bounded), then calls `search_and_format(query, n_results=3)` — the same function used by the Phase 4 `search_policies` direct tool. The ChromaDB collection, embedding model, and retrieval logic are completely reused.

If the result is an empty string or the sentinel `"No relevant information found."`, returns a message directing the user to HR contact. Otherwise returns the formatted result string directly — citations included.

**The design decision worth noting:**
`policy_lookup` wraps the existing `search_and_format()` from `vector_store/searcher.py` without duplicating any code. The same ChromaDB query logic that powers the Phase 4 agent's `search_policies` tool now also powers the MCP `policy_lookup` tool. Phase 5 adds a new interface, not new retrieval logic.

---

## New File 5 — `scripts/start_mcp_server.py`

**What it is:** The CLI runner for the MCP server — the script you run in a separate terminal to start port 8002.

**Where it fits:** Run once before any MCP agent calls. Must be running for `run_hr_advisor_with_mcp()` to reach the tools.

**How it works:**
The first two lines add the project root to `sys.path` before any project imports. The path is computed by walking up three levels from `__file__` — from `scripts/start_mcp_server.py` to `scripts/` to the project root. This is the same `sys.path.insert` pattern used in `scripts/seed_database.py` and in the DeepEval test files — it enables imports like `from mcp_server.server import mcp` to resolve regardless of the working directory.

The `mcp` import is deferred inside `if __name__ == "__main__"`. This is intentional: the path fix in the first two lines must be executed before any project modules are imported. If `from mcp_server.server import mcp` were at the top of the file, the path fix would not yet be in effect.

The startup block logs a banner with all configuration details — server name, transport, port, endpoint, and registered tools — so the operator can confirm the server started correctly before directing agent traffic to it.

**The design decision worth noting:**
The deferred `mcp` import is not optional. Moving it to the top of the file alongside the stdlib imports would cause an `ImportError` because the project root is not yet on `sys.path` at module-load time. The top of the file must run first, set up `sys.path`, and only then can the project imports be resolved.

---

## Updated File — `agents/single/hr_advisor.py` (Phase 5 changes)

**What changed:** The Phase 4 `hr_advisor.py` used `from langchain.agents import create_agent` and only exposed the three direct tools. Phase 5 adds `MCP_SERVER_URL`, a `MultiServerMCPClient` integration, and a new `run_hr_advisor_with_mcp()` async function that gives the agent five additional MCP tools.

**The migration that was required:**
When `langchain-mcp-adapters 0.2.2` was installed, it updated LangChain to 1.3.1 and LangGraph to 1.2.0. Three API changes were necessary:

| Issue | Old (Phase 4) | Fix (Phase 5) |
|---|---|---|
| Import location | `from langgraph.prebuilt import create_react_agent` | `from langchain.agents import create_agent` |
| Context manager removed | `async with MultiServerMCPClient(...)` | Direct instantiation: `client = MultiServerMCPClient(...)` |
| Wrong parameter name | `create_agent(prompt=...)` | `create_agent(system_prompt=...)` |

**`MCP_SERVER_URL`** — a module-level constant: `"http://localhost:8002/mcp"`. Centralises the server address so only one line needs changing if the port or host changes.

**`run_hr_advisor_with_mcp(question)`** — the new async function. Creates a `MultiServerMCPClient` directly (no context manager, no `async with`). Awaits `mcp_client.get_tools()` to fetch the current list of registered MCP tools from the server. Concatenates the MCP tools with `HR_ADVISOR_TOOLS` to build `all_tools` — a list of 8 tools (3 direct + 5 MCP). Calls `create_agent(model=get_llm(), tools=all_tools, system_prompt=HR_ADVISOR_SYSTEM_PROMPT)` to build the 8-tool agent. Invokes it with `await agent.ainvoke({"messages": [{"role": "user", "content": question}]})`. Extracts the answer from the last message, walks the message list for `tool_calls` attributes to build the step list, and returns an `AgentResponse`.

The try/except wrapping the entire function body returns a failure `AgentResponse` with `success=False` and the error string as the answer — never propagates an exception up to the FastAPI route.

**`run_hr_advisor(question)`** — unchanged. Still builds the 3-tool Phase 4 agent using `create_agent` with only `HR_ADVISOR_TOOLS`. Still used by the `/agent/query` endpoint for non-MCP queries.

**The design decision worth noting:**
`MultiServerMCPClient` was changed from a context manager to a direct instantiation because the `langchain-mcp-adapters 0.2.2` client does not implement `__aenter__` and `__aexit__`. Attempting `async with MultiServerMCPClient(...)` raises `AttributeError: __aexit__`. The direct instantiation pattern works for the current API — `get_tools()` fetches the tool list and the client does not need explicit lifecycle management for stateless tool calls.

---

## New File 6 — `backend/api/routes/mcp_agent.py`

**What it is:** The FastAPI route that exposes the MCP-enabled agent as a REST endpoint.

**Where it fits:** Registered in `main.py` with `app.include_router(mcp_agent_router.router)`. Handles `POST /mcp/query`.

**How it works:**
An `APIRouter` with `prefix="/mcp"` and `tags=["mcp"]`. One endpoint:

`POST /mcp/query` — an `async` endpoint (required because `run_hr_advisor_with_mcp` is async). Accepts `MCPAgentRequest` (a Pydantic model with a single `question` field). Logs the first 50 characters of the question. Awaits `run_hr_advisor_with_mcp(request.question)`. If `result.success` is False, raises `HTTPException(500, detail=result.answer)`. Otherwise returns `MCPAgentResponse`.

`MCPAgentRequest` — `question: str`.

`MCPAgentResponse` — `answer`, `tools_used`, `steps`, `success`, `question`. Identical shape to `AgentQueryResponse` from the Phase 4 agent route, with the addition of the echoed `question` field.

**The `except HTTPException: raise` guard:**
The try/except wrapping the endpoint re-raises `HTTPException` without modification. Without this guard, the `except Exception as e` branch would catch the `HTTPException` from `result.success == False` check and re-wrap it as a second 500 with a generic string detail, losing the specific error message from the agent.

**The design decision worth noting:**
`POST /mcp/query` is async end-to-end — the endpoint function is `async`, it awaits the agent function, and the agent function awaits the MCP tool calls. This is the correct pattern for IO-bound async operations in FastAPI. The Phase 4 `POST /agent/query` endpoint is synchronous because `run_hr_advisor()` is synchronous. Both patterns are valid; the choice follows the call chain.

---

## Updated File — `backend/chains/rag_router.py` (Phase 5 update)

**What changed:** A fifth classification — `"mcp"` — was added with the highest priority in the prompt. The fallback guard was updated to include `"mcp"` in the valid-result set.

**The `"mcp"` classification rules:**
- Any question containing an employee ID in EMP-XXXX format (EMP-0001, EMP-0022, etc.)
- Any explicit action request: submit, book, request, cancel, delete, withdraw leave
- Any org chart or reporting-structure lookup by employee ID

**Why `"mcp"` takes highest priority:**
The `"mcp"` classification is placed first in the prompt with an explicit `IMPORTANT` note: "Classify as 'mcp' first — any question with an EMP-XXXX ID or an explicit leave action verb takes priority over all other categories." Without this priority, an EMP-ID balance question might fall through to `"db"` (which uses NL-to-SQL and expects a person's name) or `"agent"` (which would choose the wrong tool set). The priority ensures that structured EMP-ID inputs always reach the MCP tool layer that expects them.

**The fallback guard update:**
`if result not in ("mcp", "agent", "rag", "db", "chat"):` — adding `"mcp"` ensures that a correct MCP classification returned by GPT-4o is not replaced with `"rag"` by the fallback.

**The design decision worth noting:**
The five-way router prompt lists eleven examples for the `"mcp"` category — covering all five MCP tools and all action verbs (check, submit, book, request, cancel, delete, withdraw). The example count is higher than for other categories because EMP-ID questions and action verbs are more easily confused with `"db"` queries than policy questions are with `"chat"` queries. More examples narrow the ambiguity.

---

## Updated File — `backend/main.py` (Phase 5 update)

Two lines added to register the MCP agent router:
- `from backend.api.routes import mcp_agent as mcp_agent_router` — imported as an alias to avoid name conflicts with the existing `agent` alias
- `app.include_router(mcp_agent_router.router)` — registers `POST /mcp/query`

No other changes to `main.py`.

---

## Updated File — `frontend/app.py` (Phase 5 additions)

**Three additions to the existing Streamlit app:**

**Addition 1 — Sidebar MCP status:**
A new status check immediately after the existing Agent status check. Pings `POST /mcp/query` with `{"question": "ping"}` using a 5-second timeout. On success, displays `🔧 MCP Server: Online`. On any exception, displays `🔧 MCP Server: Offline`. Uses a bare `except:` (matching all exceptions) because any failure — connection refused, timeout, HTTP error — should display the offline state.

**Addition 2 — `get_mcp_response(question)`:**
A new helper function alongside `get_agent_response()`. Posts to `POST /mcp/query` with a 90-second timeout — longer than the 60-second agent timeout because MCP calls add a network hop to the tool execution. Calls `response.raise_for_status()` and returns `response.json()`. The function uses `httpx.post()` to match the existing codebase's use of `httpx` throughout (rather than `requests`).

**Addition 3 — The `"mcp"` routing branch:**
Added after the `"agent"` branch in the classification block: `elif classification == "mcp":`. Calls `get_mcp_response(prompt)` and renders four UI elements inside a `st.chat_message("assistant")` context:

The `🔧 **MCP Action**` label — visually distinct from `🤖 Agent`, `🔍` (document RAG), and `🗄️` (database RAG) indicators.

The answer text via `st.markdown(result["answer"])`.

A write confirmation banner — `st.success("✅ Leave request submitted — record created in database")` — displayed if `"submit_leave_request"` is in `result.get("tools_used", [])`. This banner only appears for write operations, not for read operations like `check_leave_balance`.

Tool badges — one per tool called, using inline HTML styling with tool-specific icons: `💰` for `check_leave_balance`, `✍️` for `submit_leave_request`, `🗑️` for `cancel_leave_request`, `🏢` for `get_org_chart`, `📋` for `policy_lookup`. The `🔧` fallback covers any new tools added later.

A collapsible reasoning trace — `st.expander("🔧 MCP Tool Calls (N steps)")`. Inside, each step shows the tool name as a bold header, the tool input as monospace, and the observation as plain text (up to 400 characters). If the observation is empty (which it is for MCP tools — the result is in the final answer rather than captured as a step observation), a caption explains: `"MCP tool — result in final answer"`.

The message is saved to `session_state.messages` with only `answer` (not `tools_used`, `steps`, or `answer_type`) — these are not replayed in conversation history display. For MCP actions, the confirmation of what happened is in the answer text itself.

**The design decision worth noting:**
MCP observations are empty strings in the step list because the LangGraph 1.2.0 agent's `msg.tool_calls` extraction captures what tools were called but not what they returned — the tool results appear as separate `ToolMessage` objects that are not currently parsed into the step structure. The `"MCP tool — result in final answer"` caption communicates this transparently rather than showing an empty observation field.

---

## The Complete MCP Flows — Three Scenarios

### Read Flow — check_leave_balance

```
1. User types "Check the leave balance for EMP-0001"
2. app.py calls GET /rag/classify → "mcp"
   (EMP-0001 format detected → highest priority classification)
3. app.py calls get_mcp_response(prompt)
4. get_mcp_response() posts to POST /mcp/query, timeout=90s
5. routes/mcp_agent.py receives MCPAgentRequest
6. route awaits run_hr_advisor_with_mcp(question)
7. hr_advisor.py: MultiServerMCPClient fetches 5 tools from port 8002
8. hr_advisor.py: create_agent(model, tools=8_tools, system_prompt)
9. agent.ainvoke({"messages": [{"role": "user", "content": question}]})

   --- Iteration 1 ---
10. Agent reads question + 8 tool descriptions
11. Agent sees "EMP-0001" → description says "employee_id in EMP-XXXX format"
12. Agent selects check_leave_balance
13. MultiServerMCPClient sends tool call to HTTP:8002/mcp
14. FastMCP server receives call → dispatches to leave_tool.check_leave_balance()
15. leave_tool.py: validates "EMP-0001" format → engine.connect() → SELECT employees
16. Result: "James Chen has 30 days of leave remaining. Status: Active"
17. Result travels back through MCP protocol → agent receives as tool observation
18. Agent forms Final Answer from observation

19. run_hr_advisor_with_mcp() extracts answer + tools_used
20. Returns AgentResponse(answer, tools_used=["check_leave_balance"], success=True)
21. routes/mcp_agent.py returns MCPAgentResponse JSON
22. app.py renders: 🔧 MCP Action + 💰 check_leave_balance badge
```

### Write Flow — submit_leave_request

```
1. User types "Submit Annual leave for EMP-0001 from 2027-06-16 to 2027-06-18"
2. app.py calls GET /rag/classify → "mcp"
   (action verb "Submit" + EMP-ID → mcp priority)
3–9. Same setup as Read Flow (8-tool agent created)

   --- Iteration 1 ---
10. Agent reads question + descriptions
11. Agent sees "Submit", "leave", "EMP-0001", dates → submit_leave_request description matches
12. Agent selects submit_leave_request with parameters:
    employee_id="EMP-0001", start_date="2027-06-16", end_date="2027-06-18", leave_type="Annual"
13. MultiServerMCPClient sends structured tool call to HTTP:8002/mcp
14. FastMCP server dispatches to leave_tool.submit_leave_request()
15. leave_tool.py: validates EMP-0001 format
16. validates "Annual" in allowed list
17. parses dates, confirms 2027-06-18 >= 2027-06-16 (3 days)
18. engine.begin(): SELECT employee EXISTS → SELECT no duplicate pending → INSERT leave_records
19. Transaction commits automatically on engine.begin() context exit
20. Returns: "Leave request submitted successfully for EMP-0001.
             Dates: 2027-06-16 to 2027-06-18 (3 day(s)).
             Type: Annual. Status: Pending. Your manager will be notified."
21. Agent forms Final Answer from confirmation
22. AgentResponse(tools_used=["submit_leave_request"], success=True)
23. app.py renders: 🔧 MCP Action + ✍️ submit_leave_request badge
24. app.py renders: ✅ "Leave request submitted — record created in database" banner
```

### Cancel Flow — cancel_leave_request

```
1. User types "Cancel Annual leave for EMP-0001 starting 2027-06-16"
2. app.py calls GET /rag/classify → "mcp"
   (action verb "Cancel" + EMP-ID → mcp priority)
3–9. Same setup (8-tool agent)

   --- Iteration 1 ---
10. Agent sees "Cancel", "leave", "EMP-0001" → cancel_leave_request description matches
11. Agent selects cancel_leave_request with:
    employee_id="EMP-0001", start_date="2027-06-16", leave_type="Annual"
12. MCP call → leave_tool.cancel_leave_request()
13. leave_tool.py: validates EMP-0001 format, parses 2027-06-16
14. engine.begin():
    SELECT id, leave_type, end_date FROM leave_records
    WHERE employee_id='EMP-0001' AND start_date='2027-06-16'
    AND status='Pending' AND (:leave_type='' OR leave_type='Annual')
    ORDER BY id ASC
    → fetchall() returns 1 row: id=42, leave_type='Annual', end_date='2027-06-18'
    DELETE FROM leave_records WHERE id IN (:id_0)  -- id_0=42
    Transaction commits
15. Returns: "Leave request cancelled successfully for EMP-0001.
             Annual leave from 2027-06-16 to 2027-06-18 has been removed.
             Status was: Pending."
16. Agent forms Final Answer
17. app.py renders: 🔧 MCP Action + 🗑️ cancel_leave_request badge
```

---

## Journey 5 — DeepEval Evaluation

### The Evaluation Flow

```
evaluation/datasets/mcp_golden_set.json     13 entries across read/write/cancel/multi_step
        ↓ loaded once by the mcp_golden_set fixture
evaluation/tests/test_mcp.py                pytest collects 5 test functions
        ↓ each test calls get_mcp_response() → asyncio.run(run_hr_advisor_with_mcp())
agents/single/hr_advisor.py                 8-tool agent runs — MCP server must be live
        ↓ agent calls MCP tools via HTTP:8002
mcp_server/tools/                           tools execute, return results
        ↓ AgentResponse returned
evaluation/tests/test_mcp.py               LLMTestCase built: input + actual_output + expected_output
        ↓ sent to DeepEval evaluate()
DeepEval judge (GPT-4o)                     scores task completion and answer relevancy
pytest                                      asserts all scores above threshold
```

---

### File: `evaluation/datasets/mcp_golden_set.json`

**What it is:** The answer key for MCP evaluation — 13 manually written entries across four categories covering all five MCP tools.

**Where it fits:** Loaded by the `mcp_golden_set` fixture and shared across all five test functions. Each test function filters by `query_type`.

**How it works:**
Each entry has four fields: `input` (the question in natural language or EMP-ID format), `expected_output` (the specific expected result string), `query_type` (one of `"read"`, `"write"`, `"cancel"`, `"multi_step"`), and `expected_mcp_tool` (the MCP tool the agent must invoke).

**The 13 entries by category:**

Read (4 entries) — two `check_leave_balance` queries (EMP-0001 and EMP-0022) and two `get_org_chart` queries (different phrasings of the same question for EMP-0001). The org chart entry uses "What is James Chen's position and who reports to him?" rather than "Get the org chart for EMP-0001" — the specific phrasing produces a 1.00 TaskCompletion score. "Get the org chart" initially scored 0.60 because the judge interpreted it as requiring a company-wide hierarchy.

Write (3 entries) — `submit_leave_request` for Annual leave (EMP-0001), Sick leave (EMP-0022), and Emergency leave (EMP-0001). All use 2027 dates to avoid conflicts with seeded data.

Cancel (3 entries) — `cancel_leave_request` for each of the three records submitted by the write entries. These use the same employee IDs and dates as the write entries. **Run order dependency: cancel entries depend on write entries having run first in the same database session.** The cancel tests must follow the write tests.

Multi-step (3 entries) — one `check_leave_balance` plus policy lookup, one `get_org_chart` plus balance check, one `submit_leave_request` plus balance confirmation. These verify that the agent correctly combines an MCP tool with a Phase 4 direct tool in a single reasoning loop.

**The design decision worth noting:**
The cancel entries reference the same dates as the write entries. This is intentional — the cancel test validates the complete lifecycle: write creates a record, cancel removes it. The `test_mcp_tool_routing_boundary` test calls cancel entries even if no write records exist — the agent still invokes `cancel_leave_request` (getting a "no pending record found" response), which is sufficient to prove the tool routing works correctly.

---

### File: `evaluation/tests/test_mcp.py`

**What it is:** Five test functions covering all five MCP tools and all usage patterns.

**Where it fits:** Same position as `test_single_agent.py` — exercises the live application through the full agent pipeline, sends results to a judge, and asserts correctness.

**How it works:**

**`get_mcp_response(question)`** — calls `asyncio.run(run_hr_advisor_with_mcp(question))` to run the async agent function from synchronous pytest code. `time.sleep(3.0)` follows each call. The 3-second sleep serves the same purpose as in `test_single_agent.py`: the MCP agent makes multiple LLM calls per question (one to select the tool, one for the tool itself, one to form the final answer). Back-to-back calls exhaust the 30,000 TPM rate limit quickly.

**`build_mcp_test_case(item)`** — calls `get_mcp_response(item["input"])` and builds an `LLMTestCase` with `input`, `actual_output=result.answer`, and `expected_output=item["expected_output"]`. Unlike the Journey 4 test which also passes `tools_called` and `expected_tools`, the MCP test cases pass only these three fields. `ToolCorrectnessMetric` is not used in the MCP suite — the boundary test (a pure assertion loop) serves that verification role instead.

**`mcp_golden_set` fixture** — loads `mcp_golden_set.json` from `evaluation/datasets/` using a path relative to the test file. Returns the parsed list of 13 entries.

**`mcp_metrics` fixture** — returns a dict with `TaskCompletionMetric(threshold=0.7, model="gpt-4o")` and `AnswerRelevancyMetric(threshold=0.7, model="gpt-4o")`.

---

### The Two MCP Metrics

**`TaskCompletionMetric(threshold=0.7, model="gpt-4o")`**

The most important metric for the MCP write and cancel tests. The judge reads the question, ARIA's answer, and the expected output, and evaluates: was the task actually completed? For `submit_leave_request`, a 1.00 score means the judge recognised that a leave record was created — not just that ARIA mentioned the dates correctly. For `cancel_leave_request`, a 1.00 score means the judge recognised that the deletion was confirmed. This metric is what proves the write and delete operations are evaluated as actions, not just as text outputs.

**`AnswerRelevancyMetric(threshold=0.7, model="gpt-4o")`**

Carried from all previous journeys. Generates hypothetical questions that ARIA's MCP response would answer well and checks how many match the original. For MCP responses, the risk is that the agent provides extra context (policy text alongside a balance figure) that dilutes relevancy. A score of 0.95 on a multi-step entry reflects this — the policy citation caused a slight deduction that is judge variance, not an agent failure.

---

### The Five Test Functions

**`test_mcp_read_tools`** covers the first 3 entries with `query_type == "read"` — two leave balance checks and one org chart lookup. Both `task_completion` and `answer_relevancy` are applied. These are the simplest MCP queries — no state changes, no sequencing dependencies. A failure here would indicate either wrong tool selection (agent chose a Phase 4 direct tool for an EMP-ID question) or the MCP server is not running.

**`test_mcp_write_tool`** covers the first 3 entries with `query_type == "write"` — Annual, Sick, and Emergency leave submissions. Both metrics applied. Both metrics scored 1.00 across all three entries — the headline result of Phase 5. `TaskCompletionMetric` at 1.00 means the judge correctly identified that each leave submission was an action that was completed, not a question that was answered. **Run this before `test_mcp_cancel_tool`** — it creates the records that cancel needs.

**`test_mcp_cancel_tool`** covers the first 3 entries with `query_type == "cancel"` — cancelling the Annual, Sick, and Emergency leave records created by `test_mcp_write_tool`. Both metrics applied. The test has a docstring noting the run-order dependency: "Depends on test_mcp_write_tool having run first to create the pending records." Running this test in isolation against a fresh database produces correct tool routing (the agent invokes `cancel_leave_request`) but the agent returns a "no pending record found" message rather than a confirmation, which reduces TaskCompletion scores.

**`test_mcp_multi_step`** covers all 3 entries with `query_type == "multi_step"`. Both metrics applied. These are the most complex MCP test cases — the agent must combine an MCP tool call with a Phase 4 direct tool call (or another MCP call) in a single reasoning loop. The submit-plus-confirm entry is particularly significant: the agent submits a leave request and then checks the remaining balance in the same invocation — two tool calls, one coherent answer.

**`test_mcp_tool_routing_boundary`** covers all 13 golden set entries. **No LLM judge, no rate limit risk, zero cost.** A pure assertion loop: for each entry, calls `get_mcp_response(item["input"])` and asserts that `item["expected_mcp_tool"]` is in `result.tools_used`. Collects all failures before asserting — the full failure list is visible in one run rather than stopping at the first miss.

This test covers all five MCP tools across the 13 entries: `check_leave_balance` (3 times), `submit_leave_request` (4 times), `cancel_leave_request` (3 times), `get_org_chart` (2 times), `policy_lookup` (1 time). The cancel entries invoke `cancel_leave_request` regardless of whether a pending record exists — the tool is called, the routing assertion passes even when the response is "no record found."

The docstring explains the design: "Cancel entries will call cancel_leave_request regardless of whether a pending record exists — the tool is always invoked, the response varies." This is the key insight — routing correctness and result correctness are separate concerns. The boundary test verifies routing; the LLM-judged tests verify result quality.

---

### Run Commands

```bash
# MCP server must be running in a separate terminal before any MCP tests
uv run python scripts/start_mcp_server.py

# Required env vars
export DEEPEVAL_PER_TASK_TIMEOUT_SECONDS_OVERRIDE=600
export DEEPEVAL_PER_ATTEMPT_TIMEOUT_SECONDS_OVERRIDE=300

# Run boundary test first — no cost, ~78 seconds
uv run deepeval test run evaluation/tests/test_mcp.py::test_mcp_tool_routing_boundary -v

# Run LLM-judged tests in dependency order (write before cancel)
uv run deepeval test run evaluation/tests/test_mcp.py::test_mcp_read_tools -v
uv run deepeval test run evaluation/tests/test_mcp.py::test_mcp_write_tool -v
uv run deepeval test run evaluation/tests/test_mcp.py::test_mcp_cancel_tool -v
uv run deepeval test run evaluation/tests/test_mcp.py::test_mcp_multi_step -v

# Or run all in correct order as one block
uv run deepeval test run evaluation/tests/test_mcp.py::test_mcp_tool_routing_boundary -v && \
uv run deepeval test run evaluation/tests/test_mcp.py::test_mcp_read_tools -v && \
uv run deepeval test run evaluation/tests/test_mcp.py::test_mcp_write_tool -v && \
uv run deepeval test run evaluation/tests/test_mcp.py::test_mcp_cancel_tool -v && \
uv run deepeval test run evaluation/tests/test_mcp.py::test_mcp_multi_step -v
```

---

### Phase 5 Baseline Results

| Test Function | Metrics | Avg Score | Pass Rate | Cases | Cost | Time |
|---|---|---|---|---|---|---|
| `test_mcp_tool_routing_boundary` | Assertion (no judge) | 100% | **100%** | 13 | $0.000 | ~78s |
| `test_mcp_read_tools` | TaskCompletion + AnswerRelevancy | 0.99 | **100%** | 3 | $0.024 | ~21s |
| `test_mcp_write_tool` | TaskCompletion + AnswerRelevancy | **1.00** | **100%** | 3 | $0.025 | ~21s |
| `test_mcp_cancel_tool` | TaskCompletion + AnswerRelevancy | **1.00** | **100%** | 3 | $0.025 | ~21s |
| `test_mcp_multi_step` | TaskCompletion + AnswerRelevancy | 0.97 | **100%** | 3 | $0.031 | ~29s |
| **Total Phase 5** | | **0.99** | **100%** | **25** | **$0.105** | **~170s** |

The `test_mcp_write_tool` and `test_mcp_cancel_tool` scores of 1.00 on both metrics are the Phase 5 exit criteria. `TaskCompletionMetric` at 1.00 confirms the judge understood that each leave submission and cancellation was a completed action, not a described process. Write and delete operations are fully validated by the same evaluation framework used for retrieval operations.

---

### Metric Coverage Across All Five Journeys

The metric progression across five phases maps directly to the capability evolution.

Phase 1 treats ARIA as a black box: character, relevance, absence of hallucination. No knowledge of how the answer was produced.

Phase 2 opens the retrieval pipeline: faithfulness, ranking, completeness, and relevance of document chunks. `retrieval_context` is introduced — the evaluation now examines the path from question to answer.

Phase 3 applies retrieval thinking to a different data source: SQL results instead of document chunks. The framework doesn't change — only what goes into `retrieval_context`.

Phase 4 opens the reasoning loop: task completion, tool selection, and answer relevance in an agentic context. `tools_called` and `expected_tools` fields are added — the evaluation now examines the decisions made during reasoning.

Phase 5 extends the reasoning loop to cover actions. The same `TaskCompletionMetric` and `AnswerRelevancyMetric` from Phase 4 are applied to write and delete operations. No new metric types are needed — the same framework that validates question-answering validates database mutations. The routing boundary test, carried forward from Phase 3's `test_db_routing_boundary`, now covers all five MCP tools across 13 entries.

The cumulative pattern: each phase adds metrics that reveal a new layer. Previous metrics remain as regression checks. Phase 5's 25-case, 5-test suite is the widest coverage yet — and proves that adding write and delete capability did not degrade the read quality established in Phases 1–4.

---

# FOUNDATION FILES
*These files support all five journeys. Explained here once.*

---

## `database/models.py`

**What it is:** The SQLAlchemy definition of the three database tables.

**Where it fits:** Used by `seed_database.py` to create objects. The MCP tools in Phase 5 bypass this file entirely — they query PostgreSQL directly via `sqlalchemy.create_engine(settings.database_url)` and `text()` queries, not through ORM model objects. This is intentional: the MCP tools need predictable, explicit SQL control for write and delete operations.

**How it works:**
Three classes inherit from `Base = declarative_base()`:

`Employee` — maps to the `employees` table. 13 columns covering identity, role, location, leave balance, and status.

`LeaveRecord` — maps to `leave_records`. 9 columns covering leave type, dates, status, and approval chain. Phase 5's `submit_leave_request` inserts into this table; `cancel_leave_request` deletes from it.

`OrgChart` — maps to `org_chart`. 6 columns covering the reporting hierarchy with numeric levels.

**The design decision worth noting:**
`manager_id` on both `Employee` and `OrgChart` is a plain `String(20)` rather than a `ForeignKey`. Self-referential foreign keys cause insertion ordering problems. Using a plain string lets seed data insert in any order. The relationship is meaningful in the data; it's just not enforced at the database constraint level.

---

## `database/migrations/init.sql`

**What it is:** The SQL that creates the three tables in PostgreSQL.

**How it works:**
Three `CREATE TABLE IF NOT EXISTS` blocks — safe to run multiple times. Indexes on the columns most likely to appear in `WHERE` clauses: `employee_id`, `department`, `status`, `manager_id` for employees; `employee_id`, `status`, `start_date` for leave records. The `start_date` index is particularly important for Phase 5 — `cancel_leave_request` filters by `employee_id` AND `start_date` on every call.

---

## `database/seed_data/` and `scripts/seed_database.py`

**What they are:** The test data and the script that loads it.

**How it works:**
Three CSVs — `employees.csv` (50 rows), `leave_records.csv` (30 rows), `org_chart.csv` (50 rows). `seed_database.py` opens each CSV with Pandas, creates SQLAlchemy model objects, and commits. It checks if data already exists before inserting — running it twice does not create duplicate rows.

**The `sys.path.insert` at the top** — the same three-level path climb used in `scripts/start_mcp_server.py` and all DeepEval test files. The project root must be on `sys.path` for `from config.settings import settings` and `from database.models import Employee` to resolve from inside `scripts/`.

---

## Reading Paths

**If you want to understand the chat path, open these files in this order:**
```
config/settings.py
backend/schemas/chat.py
backend/chains/chat_chain.py
backend/api/routes/chat.py
backend/main.py
frontend/app.py
```

**If you want to understand the document RAG path, open these files in this order:**
```
scripts/create_documents.py         (understand the source data)
rag/document_rag/ingestion.py       (PDF → text)
rag/document_rag/chunker.py         (text → chunks)
vector_store/store.py               (ChromaDB operations)
vector_store/indexer.py             (orchestrates ingestion)
rag/document_rag/retriever.py       (question → chunks)
rag/document_rag/chain.py           (chunks + question → answer)
backend/schemas/rag.py              (request/response shapes)
backend/chains/rag_router.py        (classify: mcp / rag / db / agent / chat)
backend/api/routes/rag.py           (endpoints)
frontend/app.py                     (UI — same file as chat)
```

**If you want to understand the database RAG path, open these files in this order:**
```
database/seed_data/employees.csv    (understand the source data)
rag/database_rag/schema.py          (schema description fed to GPT-4o)
rag/database_rag/nl_to_sql.py       (question → validated SQL)
rag/database_rag/executor.py        (SQL → structured QueryResult)
rag/database_rag/chain.py           (QueryResult + question → answer)
backend/schemas/rag.py              (DatabaseRAGRequest/Response models)
backend/chains/rag_router.py        (five-way router)
backend/api/routes/rag.py           (/rag/db/query and /rag/db/stream endpoints)
frontend/app.py                     (stream_db() generator + SQL expander)
```

**If you want to understand the agent path, open these files in this order:**
```
vector_store/searcher.py            (semantic search interface for direct tools)
agents/single/tools.py              (3 Phase 4 direct tools — search and lookup)
agents/single/hr_advisor.py         (ReAct agent — 8-tool brain with MCP integration)
backend/api/routes/agent.py         (agent endpoint for direct-tool queries)
backend/chains/rag_router.py        (five-way router — "agent" classification)
frontend/app.py                     (agent reasoning trace display)
evaluation/datasets/agent_golden_set.json
evaluation/tests/test_single_agent.py
```

**If you want to understand the MCP path, open these files in this order:**
```
mcp_server/server.py                (FastMCP server entry point — creates mcp instance)
mcp_server/tools/leave_tool.py      (check_leave_balance, submit_leave_request,
                                     cancel_leave_request — the write and delete ops)
mcp_server/tools/org_chart_tool.py  (get_org_chart — two-query self-join)
mcp_server/tools/policy_lookup_tool.py (policy_lookup — wraps search_and_format)
scripts/start_mcp_server.py         (CLI runner — sys.path fix + deferred import)
agents/single/hr_advisor.py         (run_hr_advisor_with_mcp — 8-tool agent)
backend/api/routes/mcp_agent.py     (POST /mcp/query endpoint)
backend/chains/rag_router.py        (five-way router — "mcp" takes highest priority)
backend/main.py                     (mcp_agent router registered)
frontend/app.py                     (get_mcp_response, mcp branch, confirmation banner)
evaluation/datasets/mcp_golden_set.json
evaluation/tests/test_mcp.py
```

**If you want to understand the data foundation:**
```
database/models.py
database/migrations/init.sql
database/seed_data/employees.csv    (open in any spreadsheet or text editor)
scripts/seed_database.py
```

**If you want to understand why a design decision was made, look for these phrases in this document:**
- "The design decision worth noting" — explains why a pattern was chosen over an obvious alternative
- "The migration that was required" — explains an API change forced by a dependency upgrade
- "The `NOT_DB_QUERY` sentinel" — explains a cross-layer data contract
- "Run order dependency" — explains a test sequencing requirement
- "Deferred import" — explains why import order matters

---

*Document version: June 2026 | ARIA v0.5.0 | Phases 0–5*
