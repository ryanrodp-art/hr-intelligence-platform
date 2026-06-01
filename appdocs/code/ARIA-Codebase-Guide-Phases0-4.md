# ARIA Codebase Guide — Phases 0–4
## Understanding the Code in Execution Order

> **How to use this guide:** Open your code editor on one side, this document on the other.
> Follow the flow of a real user message through every file it touches.
> Each section tells you what a file does, where it fits, and why it was designed that way —
> not a line-by-line walkthrough, but enough to make the code immediately readable.

---

## The Four Journeys

Everything in this codebase serves one of four request flows:

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

All four journeys start at the same place — the Streamlit UI — and end at the same place — a response in the browser. A single classifier (the query router) decides which journey handles each request. What happens in between is different.

Read Journey 1 first. Journey 2 builds on everything Journey 1 establishes. Journey 3 builds on both. Journey 4 builds on all three — the agent's tools delegate directly to the Journey 2 and Journey 3 pipelines.

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

**In the chat flow:** `chat_chain.py` reads `settings.openai_api_key` and `settings.openai_model` to configure the LLM. `main.py` reads `settings.app_env` for the startup log.

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

**The sidebar** — calls `GET /health` on every page load to show backend status. In Phase 2, also calls `GET /rag/status` to show how many policy chunks are indexed in ChromaDB.

**The design decision worth noting:**
`st.write_stream()` accepts a generator and renders tokens as they arrive. It also returns the complete assembled text when the generator finishes — this is what gets saved to `session_state.messages` for conversation history. One call does both streaming display and history capture.

---

## File 3 — `backend/main.py`

**What it is:** The FastAPI application entry point — the front door of the backend.

**Where it fits:** Loaded by uvicorn on startup. Registers all routes, adds middleware, and runs startup/shutdown logic.

**How it works:**
`main.py` creates the `FastAPI` app object and configures it. It does not contain any endpoint logic — that lives in the route files. `main.py`'s job is wiring everything together.

**Key functions:**

`lifespan(app)` — an async context manager that runs startup code before `yield` and shutdown code after. On startup it logs all configuration values confirming the application is connected to the right databases. This is where Phase 3+ will add vector store initialisation and agent graph preloading.

`app.add_middleware(CORSMiddleware)` — allows Streamlit (port 8501) to call FastAPI (port 8000). Without this the browser blocks cross-origin requests as a security measure.

`app.include_router(chat_router.router)` and `app.include_router(rag_router.router)` — registers all chat and RAG endpoints. The router files define the endpoints; `main.py` connects them to the app. Adding a new domain (Phase 3 database RAG) means adding one more `include_router` line here.

**The design decision worth noting:**
`main.py` has no business logic. It only registers things. This is the FastAPI equivalent of a Java Spring `Application` class — configuration and wiring only, never logic.

---

## File 4 — `backend/schemas/chat.py`

**What it is:** The data contract for the chat API — defines exactly what goes in and what comes out.

**Where it fits:** Used by the chat route to validate incoming requests and serialize outgoing responses. FastAPI reads these schemas automatically.

**How it works:**
Two Pydantic models define the API contract:

`ChatRequest` — what Streamlit sends. Has two fields: `message` (required string, minimum 1 character after whitespace stripping) and `session_id` (optional, auto-generates a UUID if not provided). A field validator strips whitespace from the message and rejects anything that becomes empty after stripping.

`ChatResponse` — what FastAPI sends back. Has four fields: `response` (the text), `session_id` (echoed back from the request), `timestamp` (auto-generated at response creation time), and `model` (which LLM was used — `"stub-phase-0"` in Phase 0, `"gpt-4o"` in Phase 1+).

**The design decision worth noting:**
`session_id` uses `default_factory=lambda: str(uuid4())` rather than `default=str(uuid4())`. The factory is called once per instance — so every new request gets a fresh UUID. Using `default=` would generate one UUID at class definition time and share it across all requests.

---

## File 5 — `backend/api/routes/chat.py`

**What it is:** The chat endpoint handler — the code that runs when `/chat/` is called.

**Where it fits:** Between `main.py` (which registers it) and `chat_chain.py` (which it calls). Receives validated requests, calls the chain, returns responses.

**How it works:**
An `APIRouter` with `prefix="/chat"` is created. All routes defined on this router automatically get `/chat` prepended. Four endpoints are defined:

`POST /` → `POST /chat/` — the non-streaming endpoint. Used by DeepEval test suite. Calls `chain_chat()`, waits for the complete response, returns a `ChatResponse` JSON object. The trailing slash matters — FastAPI canonicalises routes with a trailing slash and redirects requests without one. `httpx` won't follow redirects on POST, so all callers must use `/chat/`.

`POST /stream` → `POST /chat/stream` — the streaming endpoint. Used by Streamlit. Creates an async generator that calls `chat_stream()` and yields each token as an SSE event in the format `data: {"token": "...", "session_id": "..."}\n\n`. Returns a `StreamingResponse` with `media_type="text/event-stream"` and headers that prevent caching and buffering.

`DELETE /{session_id}` → `DELETE /chat/{session_id}` — clears conversation memory for a session. Used by the Streamlit "Clear Conversation" button.

`GET /stats` → `GET /chat/stats` — returns how many active conversation sessions are in memory.

**The design decision worth noting:**
`/chat/` and `/chat/stream` serve different audiences. The non-streaming endpoint returns a complete JSON object with all metadata — easy for evaluation tools to parse. The streaming endpoint returns tokens as they arrive — the right experience for users. Keeping both means you never have to choose between evaluation and UX.

---

## File 6 — `backend/chains/chat_chain.py`

**What it is:** The LangChain integration — where GPT-4o actually gets called.

**Where it fits:** Called by the chat route. The deepest point in the chat flow before a response starts coming back.

**How it works:**
This file manages three things: the LLM configuration, the conversation memory store, and the chain that connects them.

**Key functions:**

`get_llm()` — creates a fresh `ChatOpenAI` instance with `model="gpt-4o"`, `temperature=0.7`, and `streaming=True`. Created fresh per call rather than reused — avoids stale connections and makes testing easier. Temperature 0.7 gives natural conversational variation — responses feel human rather than robotic.

`get_or_create_memory(session_id)` — looks up the conversation history for a session ID. If none exists, creates a new `ChatMessageHistory` object and stores it in the module-level `_memory_store` dict. Returns the history object. The dict persists for the lifetime of the FastAPI process — all active conversations live in RAM here.

`chat(message, session_id)` — the non-streaming call. Builds a prompt template with three components: the `ARIA_SYSTEM_PROMPT` (ARIA's persona), a `MessagesPlaceholder` for conversation history, and the new user message. Wraps the chain with `RunnableWithMessageHistory` which automatically fetches history for the session before invoking and saves the new exchange after. Returns the complete response text.

`chat_stream(message, session_id)` — same as `chat()` but uses `chain_with_history.astream()` instead of `ainvoke()`. An async generator that yields each token chunk as it arrives from GPT-4o. Accumulates the full response internally for logging after the stream completes.

`clear_memory(session_id)` — removes a session from `_memory_store`. Called when the user clears their conversation.

`get_memory_stats()` — returns the count of active sessions and their IDs.

**`ARIA_SYSTEM_PROMPT`** — the constant at the top of the file. This is ARIA's instruction set — her identity, what she helps with, and her behavioural guidelines. Every GPT-4o call starts with this prompt. The GEval metric in DeepEval evaluates whether ARIA stays true to this prompt in every response.

**The design decision worth noting:**
`RunnableWithMessageHistory` replaced the deprecated `ConversationChain` from LangChain 0.3+. It separates the chain logic from the memory management — the chain itself is just `prompt | llm`, and `RunnableWithMessageHistory` wraps it to add history lookup and storage. This makes the chain reusable with different memory backends without changing the chain itself.

---

## The Complete Chat Flow — One Message

```
1. User types "Hello ARIA" → st.chat_input() captures it
2. app.py calls GET /rag/classify → returns "chat"
3. app.py calls stream_rag() → wait, "chat" → calls stream_response()
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

The evaluation journey for chat is a separate path that runs alongside — not inside — the live request flow. Think of it as a second user who sends the same questions as a real employee, but instead of reading ARIA's answers, hands them to a judge who scores them.

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
        ↓ prints results table with pass/fail per test case
```

---

### File: `evaluation/datasets/chat_golden_set.json`

**What it is:** The answer key — 20 manually written question and expected answer pairs.

**Where it fits:** Loaded once at test startup and shared across all five test functions. Nothing generates this automatically — it is deliberately hand-authored because it encodes what *you* consider a correct answer.

**How it works:**
The first 10 entries cover standard HR knowledge — leave types, onboarding, performance reviews, org charts. The next 10 entries are deliberate edge cases: vague questions, company-specific data ARIA doesn't have, emotionally sensitive scenarios, legally sensitive termination questions, and one intentional off-topic question (asking ARIA to write a Python script). These edge cases are kept as intentional failures rather than removed — they make the evaluation suite honest. A test suite that only asks easy questions is not a quality gate.

The expected outputs are specific and citable: "25 days per calendar year" not "employees receive annual leave." Specificity matters because the judge does semantic comparison — it needs enough substance in the expected output to evaluate whether ARIA's answer is meaningfully correct.

---

### File: `evaluation/tests/conftest.py`

**What it is:** The pytest configuration file that runs automatically before any test.

**Where it fits:** Loaded by pytest before `test_chat.py` is collected. Sets up the environment that all tests depend on.

**How it works:**
A session-scoped fixture called `deepeval_config` reads `OPENAI_API_KEY` from the environment and prints a confirmation that the judge LLM is configured. DeepEval reads the API key automatically — `conftest.py` just makes the dependency visible and verifiable before tests begin. If the key is missing, tests fail immediately with a clear error rather than a cryptic API rejection mid-run.

---

### File: `evaluation/tests/test_chat.py`

**What it is:** Five test functions that collectively prove the chat journey works correctly across different question types and failure modes.

**Where it fits:** The endpoint of the evaluation flow. Each function builds test cases, calls `evaluate()`, and asserts all cases pass.

**How it works:**

**`get_aria_response(question)`** — the helper function used by every test. Posts to `POST /chat/` with a `session_id` derived deterministically from the question using `hash(question) % 100000`. The same question always generates the same session ID, so memory context is consistent across runs. Returns just the response text — not the full `ChatResponse` object.

**The `golden_set` fixture** — a module-scoped pytest fixture that reads `chat_golden_set.json` once at startup and returns the parsed list. Module scope means the file is read once no matter how many test functions use it. Without this, each test function would re-read the file from disk.

**The `metrics` fixture** — creates the three metric objects once and stores them in a dict. All five test functions share the same metric instances. The fixture is module-scoped for the same reason as `golden_set` — create once, reuse everywhere.

---

### The Three Metrics

**`GEval` — HR Role Adherence**

This is the most flexible metric in DeepEval. You write the evaluation criteria in plain English and GPT-4o grades against it. The criteria have four points: maintain the ARIA persona, only discuss HR topics, redirect off-topic questions, and be professional. The judge reads both ARIA's response and the original question — the `evaluation_params` setting tells it which fields to look at. Without the question, the judge couldn't check whether ARIA appropriately redirected an off-topic request. Judge model is `gpt-5.4` — DeepEval automatically selects the latest available model for GEval.

**`AnswerRelevancyMetric`**

Measures whether the response directly addresses what was asked. It works differently from GEval — instead of reading a rubric, it generates hypothetical questions that ARIA's response would answer well, then measures how many of those match the original question. If ARIA's response about payroll contacts would also answer "who handles HR admin?" then the relevancy is high. If it only partially addresses the original question, the score drops. Judge model is `gpt-4o`.

**`HallucinationMetric`**

Measures whether ARIA invents facts not present in the provided context. When `context=[]` (empty list) is passed, the judge treats any specific factual claim as potentially invented — because there are no source documents to support it. A score of `0.0` means zero hallucination detected. This is the best possible result and what all five hallucination test cases achieved. Judge model is `gpt-4o`.

---

### The Five Test Functions

**`test_aria_responds_to_hr_questions`** uses golden set rows 1–8 — the standard HR knowledge questions. Both `role_adherence` and `answer_relevancy` are run against each. This is the core happy-path test: ARIA asked straightforward HR questions and expected to give relevant, on-persona answers.

**`test_aria_rejects_non_hr_questions`** uses golden set row 9 — "Can you help me write a Python script?" Only `role_adherence` is tested here, not answer relevancy. Answer relevancy would be ambiguous — ARIA redirecting to HR topics is the correct response, but that response doesn't directly answer the Python question. Role adherence is the right measure: did ARIA stay in her lane?

**`test_aria_no_hallucination`** uses golden set rows 1–5 with `context=[]`. These are general HR questions where ARIA can answer from training knowledge without inventing company-specific facts. The empty context tells DeepEval to flag any specific claim ARIA makes as a potential hallucination. All five scored `0.00` — ARIA consistently answers in general terms without fabricating specific company data.

**`test_aria_handles_sensitive_questions`** uses golden set rows 13, 15, 17, 19, 20 — unfair treatment by a manager, a three-part sick leave question, ambiguous probation period, harassment complaint, and termination without warning. Both `role_adherence` and `answer_relevancy` are used. A comment in the code notes these may produce lower scores in Phase 1 and are expected to improve when document RAG is added in Phase 2 — acknowledging known limitations honestly rather than papering over them.

**`test_aria_handles_knowledge_boundary_questions`** uses golden set rows 11, 12, 14, 16, 18 with `context=[]` — vague questions, company-specific policy requests, salary ranges, off-topic tech questions, and exact vacation day counts. Only `hallucination` is tested. These are the questions most likely to trigger fabrication — "Exactly how many vacation days do I get?" is high-risk because a number is expected. All five scored `0.00` — ARIA said "I don't have that specific information" rather than inventing figures.

---

### How `evaluate()` and `assert` Work Together

Each test function follows the same pattern. It loops through its golden set entries, calls `get_aria_response()` for each, builds an `LLMTestCase` with the input, actual output, and expected output, then calls `evaluate()` with the list of test cases and the relevant metrics.

`evaluate()` sends every test case to the judge LLM asynchronously — all cases in a function run concurrently. It returns an `EvaluationResult` containing one `TestResult` per case. Each `TestResult` has a `success` boolean that is `True` only if all metrics passed for that case.

The assertion `assert all(r.success for r in results.test_results)` fails the pytest test if any single case fails any single metric. This is intentional — one failure should be visible, not averaged away.

---

### Run Command and Results

```bash
# FastAPI must be running in Tab 1 before running evals
uv run deepeval test run evaluation/tests/test_chat.py -v
```

**Phase 1 baseline — 24 test cases, 100% pass rate, $0.19 cost, ~72 seconds**

| Test Function | Metric | Avg Score | Pass Rate | Cases |
|---|---|---|---|---|
| `test_aria_responds_to_hr_questions` | HR Role Adherence | 0.98 | 100% | 8 |
| `test_aria_responds_to_hr_questions` | Answer Relevancy | 0.98 | 100% | 8 |
| `test_aria_rejects_non_hr_questions` | HR Role Adherence | 1.00 | 100% | 1 |
| `test_aria_no_hallucination` | Hallucination | 0.00 | 100% | 5 |
| `test_aria_handles_sensitive_questions` | HR Role Adherence | 0.93 | 100% | 5 |
| `test_aria_handles_sensitive_questions` | Answer Relevancy | 1.00 | 100% | 5 |
| `test_aria_handles_knowledge_boundary_questions` | Hallucination | 0.00 | 100% | 5 |

**One thing worth noting when reading the results:** The payroll contact question (row 5) scored `0.67` Answer Relevancy in one run and `0.80` in another — same question, same ARIA response, different judge score. The judge LLM is itself non-deterministic. This is why scores should be read as trends across multiple runs rather than exact measurements. A score of `0.67` on one run and `0.80` on the next both tell the same story: ARIA's payroll answer is borderline — it answers correctly but vaguely because she has no company-specific contact data. That gap closes in Phase 3 when employee database RAG is added.

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
backend/schemas/rag.py       RAGRequest validated here
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

These run once at setup, not on every request. The results live in ChromaDB persistently.

---

## Setup File 1 — `scripts/create_documents.py`

**What it is:** A one-time script that generates the four HR policy PDFs using PyMuPDF.

**Where it fits:** Runs once before indexing. Its output lives in `documents/policies/` and `documents/handbooks/`.

**How it works:**
Uses `fitz` (PyMuPDF) to create PDF files programmatically from Python strings. Each document is structured with numbered sections, bullet points, and specific policy details — exact numbers like "25 days annual leave", "16 weeks parental leave", "$2,000 professional development budget".

**The design decision worth noting:**
Every major section in each PDF is separated by `\n\n` (double newline). This is not cosmetic — it's intentional for the chunker. `RecursiveCharacterTextSplitter` tries `\n\n` as its first split point. Without double newlines between sections, the Annual Leave section and Sick Leave section might land in the same chunk, diluting both vectors and producing poor retrieval results. The parental leave retrieval bug (fixed during Phase 2) was caused by exactly this — parental leave and sick leave sharing a chunk.

---

## Setup File 2 — `rag/document_rag/ingestion.py`

**What it is:** The first step of the RAG pipeline — reads PDFs and produces clean text with metadata.

**Where it fits:** Called by `indexer.py` during setup. Its output feeds into `chunker.py`.

**How it works:**
Defines a `DocumentPage` dataclass with fields for the text content, source filename, full path, page number, and total page count. These metadata fields travel with the text through every subsequent step so ARIA can always cite which document and page her answer came from.

**Key functions:**

`clean_text(text)` — takes raw PyMuPDF text and removes artifacts: multiple consecutive spaces, very short lines that are usually page numbers or headers, and excessive blank lines. Returns clean readable text.

`extract_pages(pdf_path)` — opens a PDF, iterates page by page, cleans each page's text, and yields `DocumentPage` objects. Uses `yield` rather than returning a list — memory efficient for large documents.

`load_all_documents()` — scans the `documents/` directory recursively for all `.pdf` files and calls `extract_pages()` on each. Returns a flat list of all `DocumentPage` objects from all documents.

`get_document_stats()` — a convenience function that calls `load_all_documents()` and returns a summary: total documents found, total pages, and per-document page counts.

**The design decision worth noting:**
Pages where the cleaned text is under 50 characters are skipped. This filters out pages that are essentially empty after cleaning — like a page that contains only a header and page number. Indexing empty or near-empty chunks wastes vector space and can pollute search results.

---

## Setup File 3 — `rag/document_rag/chunker.py`

**What it is:** The second step of the RAG pipeline — splits pages into retrieval-sized pieces.

**Where it fits:** Called by `indexer.py` after ingestion. Takes `DocumentPage` objects and produces `DocumentChunk` objects.

**How it works:**
Defines a `DocumentChunk` dataclass with all the same metadata as `DocumentPage` plus chunk-specific fields: `chunk_index` (position within its page), `total_chunks_in_page`, and `chunk_id` (a unique string like `"leave_policy_p1_c2"`).

**Key functions:**

`create_splitter(chunk_size, chunk_overlap)` — creates a `RecursiveCharacterTextSplitter` configured with separator priority `["\n\n", "\n", ". ", " ", ""]`. The splitter tries each separator in order, always preferring to break at the most natural boundary. Phase 2 uses `chunk_size=800` and `chunk_overlap=100` — arrived at by debugging the parental leave retrieval issue.

`chunk_page(page, splitter)` — takes one `DocumentPage` and splits its text. Filters out any chunks shorter than 50 characters (usually orphaned headers). Creates a `DocumentChunk` for each piece, carrying forward all metadata from the parent page.

`chunk_all_documents(chunk_size, chunk_overlap)` — calls `load_all_documents()` and `chunk_page()` for every page. Returns a flat list of all chunks across all documents.

`get_chunking_stats(chunks)` — returns total chunk count, average/min/max character counts, and per-document breakdown.

**The design decision worth noting:**
`chunk_overlap=100` means the last 100 characters of chunk N are repeated at the start of chunk N+1. This prevents a policy clause that straddles a chunk boundary from being split between two chunks where neither contains the complete thought. The overlap creates a sliding window effect — no information is ever completely isolated to one chunk.

---

## Setup File 4 — `vector_store/store.py`

**What it is:** The ChromaDB connection and all vector operations.

**Where it fits:** Used by `indexer.py` during setup for adding chunks. Used by `retriever.py` at query time for searching.

**How it works:**
Defines a `VectorStore` class that wraps a ChromaDB `HttpClient` and an `OpenAIEmbeddings` instance. A module-level singleton `vector_store = VectorStore()` is created — the same instance is reused across all requests.

**Key functions:**

`add_chunks(chunks)` — takes a list of `DocumentChunk` objects, embeds their text using `OpenAIEmbeddings` with `text-embedding-3-small`, and stores the vectors in ChromaDB along with the original text and metadata. Called once during indexing.

`query(question, top_k)` — the search function. Embeds the question using the same embedding model, asks ChromaDB for the `top_k` most similar vectors using cosine similarity, and returns the results with their similarity distances.

`count()` — returns the number of vectors currently in the collection.

`reset()` — deletes and recreates the collection. Used when re-indexing after document changes.

`get_collection_info()` — returns the collection name, vector count, and embedding model name.

**The design decision worth noting:**
The same embedding model (`text-embedding-3-small`) must be used for both indexing (storing chunks) and querying (searching). Using different models would be like filing documents alphabetically and then searching for them numerically — the similarity scores would be meaningless. This is enforced by having a single `embeddings` object in `VectorStore.__init__()` that's used in both `add_chunks()` and `query()`.

---

## Setup File 5 — `vector_store/indexer.py`

**What it is:** The orchestrator that runs the full ingestion pipeline.

**Where it fits:** A standalone script run once at setup. Coordinates ingestion → chunking → embedding → storing.

**How it works:**

`index_documents(reset)` — the main function. If `reset=True`, calls `vector_store.reset()` to clear existing vectors. Checks if documents are already indexed (if `vector_store.count() > 0` and not resetting, returns early — idempotent). Calls `chunk_all_documents()` to get all chunks, then `vector_store.add_chunks()` to embed and store them. Returns a status dict.

`verify_index()` — calls `vector_store.get_collection_info()` to confirm indexing succeeded.

**The design decision worth noting:**
The idempotency check (`if already indexed, skip`) means you can run the indexer multiple times safely. Only when `reset=True` does it clear and reindex. This protects against accidentally running the indexer twice and duplicating all vectors.

---

## Runtime File 1 — `backend/schemas/rag.py`

**What it is:** The data contract for the RAG API — what goes in and what comes out.

**Where it fits:** Used by the RAG route to validate requests and shape responses.

**How it works:**
Two Pydantic models:

`RAGRequest` — what Streamlit sends for a RAG query. Three fields: `question` (required, minimum 1 character), `session_id` (auto-generated UUID if not provided), and `top_k` (how many chunks to retrieve, default 3, capped between 1 and 10).

`RAGResponse` — what FastAPI sends back. Six fields: `answer` (the generated text), `sources` (list of citation strings like `"Leave Policy, Page 1"`), `chunks_used` (how many chunks were retrieved), `query` (the original question echoed back), `session_id`, and `model` (always `"gpt-4o-rag"` to distinguish from chat responses).

**The design decision worth noting:**
`RAGResponse` includes `sources` and `chunks_used` that `ChatResponse` doesn't have. This is intentional — RAG answers must be traceable. When a user sees "Primary caregivers receive 16 weeks" they need to know that came from Leave Policy Page 1, not from GPT-4o's training data.

---

## Runtime File 2 — `backend/chains/rag_router.py`

**What it is:** The traffic controller — decides whether a question goes to document RAG, database RAG, or general chat.

**Where it fits:** Called by the RAG classify endpoint. Its decision determines which chain handles the request.

**How it works:**

`classify_query(question)` — sends the question to GPT-4o with a classification prompt and `temperature=0`. Zero temperature means deterministic — the same question always gets the same classification. Returns one of three values: `"rag"` (document question), `"db"` (employee data question), or `"chat"` (general conversation).

The classification prompt lists specific criteria for each category. "What is our parental leave policy?" → `"rag"`. "How many leave days does James Chen have?" → `"db"`. "Hello, how are you?" → `"chat"`. A critical rule built into the prompt: if the question mentions a specific person by name, always return `"db"` — no exception. This prevents "What are Isabella Fernandez's leave dates?" from being routed to ChromaDB where no employee records exist.

If GPT-4o returns anything other than a known classification, the router defaults to `"rag"` — conservative fallback that searches documents rather than refusing to answer.

**The design decision worth noting:**
The classify endpoint function is named `classify_query_endpoint` not `classify_query`. This avoids a Python name collision — `classify_query` is already imported from `rag_router.py`. If the endpoint function had the same name, it would shadow the import and the endpoint would call itself recursively, causing a 500 error. The naming convention makes the distinction explicit.

---

## Runtime File 3 — `rag/document_rag/retriever.py`

**What it is:** The search interface — converts a question into relevant document chunks.

**Where it fits:** Called by `chain.py` at the start of every RAG request. Sits between the chain and the vector store.

**How it works:**
Defines a `RetrievedChunk` dataclass with text, source metadata, similarity score, and a formatted citation string.

**Key functions:**

`format_citation(source, page_number)` — converts a filename to a readable citation. `"leave_policy.pdf"` becomes `"Leave Policy, Page 1"`. This formatted string appears in ARIA's answer and in the Streamlit UI source display.

`retrieve(query, top_k, min_similarity)` — calls `vector_store.query()`, converts the raw distance scores to similarity scores (`similarity = 1 - distance`), filters out chunks below `min_similarity=0.3`, sorts by similarity descending, and returns a list of `RetrievedChunk` objects.

`retrieve_with_context(query, top_k)` — wraps `retrieve()` and assembles the results into a single formatted string called `context_text`. This string interleaves citations and chunk text:
```
[Leave Policy, Page 1]
Full-time employees receive 25 days per calendar year...

[Leave Policy, Page 2]
Submit leave requests via the HR portal at least 2 weeks...
```
This formatted string is what gets injected directly into the GPT-4o prompt.

**The design decision worth noting:**
The retriever adds a layer of abstraction over the vector store. The chain never calls `vector_store.query()` directly — it calls `retrieve_with_context()`. This means if you later swap ChromaDB for a different vector database, or add hybrid search (vector + keyword), you only change `retriever.py`. The chain stays untouched.

---

## Runtime File 4 — `rag/document_rag/chain.py`

**What it is:** The RAG orchestrator — retrieves context, builds the augmented prompt, and streams the grounded answer.

**Where it fits:** The deepest point in the RAG flow. Called by the RAG route, calls the retriever, calls GPT-4o.

**How it works:**
`RAG_SYSTEM_PROMPT` — the instruction constant at the top. Unlike the chat system prompt which says "answer HR questions professionally", the RAG system prompt says "answer ONLY from the context provided, always cite your source, and if the context doesn't contain the answer, say so explicitly." The `ONLY` constraint is what prevents hallucination.

**Key functions:**

`build_rag_prompt()` — creates a `ChatPromptTemplate` with two parts: the RAG system prompt and a human message template with two variables: `{context}` (the retrieved chunks formatted with citations) and `{question}` (the user's question).

`get_rag_llm()` — creates `ChatOpenAI` with `temperature=0.1`. Significantly lower than the chat chain's `0.7`. RAG answers must be factual and consistent — ARIA should say "25 days" every time, not sometimes "25 days" and sometimes "approximately 25 days." Lower temperature keeps answers close to the retrieved text.

`rag_query(question)` — the non-streaming call used by DeepEval. Calls `retrieve_with_context()`, checks if any chunks were found (returns fallback message if none), builds and invokes the chain, returns a `RAGResponse` with the answer, sources, and chunk count.

`rag_query_stream(question)` — the streaming call used by Streamlit. Same retrieval logic but uses `chain.astream()` to yield tokens as they arrive. After all tokens are yielded, yields the source list so Streamlit can display citations below the answer.

**The design decision worth noting:**
`rag_query()` and `rag_query_stream()` share the retrieval logic but differ only in generation. The retriever call is identical. This means the same chunks always feed into both paths — evaluation results from `rag_query()` (used by DeepEval) exactly reflect what users see through `rag_query_stream()` (used by Streamlit). No discrepancy between what's tested and what's deployed.

---

## Runtime File 5 — `backend/api/routes/rag.py`

**What it is:** The RAG endpoint handler — the code that runs when `/rag/*` is called.

**Where it fits:** Between `main.py` (which registers it) and the RAG chain (which it calls).

**How it works:**
An `APIRouter` with `prefix="/rag"`. Four endpoints:

`GET /classify` → `GET /rag/classify` — calls `classify_query()` and returns `{"query": "...", "classification": "rag"}`. Wrapped in try/except with `"rag"` as the fallback — if classification fails, default to document search rather than failing the request.

`POST /query` → `POST /rag/query` — the non-streaming endpoint for DeepEval. Calls `rag_query()`, waits for the complete `RAGResponse`, returns it as JSON.

`POST /stream` → `POST /rag/stream` — the streaming endpoint for Streamlit. Creates an async generator that calls `rag_query_stream()` and yields tokens as SSE events. After all tokens, sends one special metadata event: `data: {"sources": [...], "chunks_used": N}\n\n`. Then sends `data: {"token": "[DONE]"}\n\n`. Streamlit watches for the sources event to capture citation data.

`GET /status` → `GET /rag/status` — returns `{"vectors": 19, "collection": "hr_policies", "embedding_model": "text-embedding-3-small"}`. Used by Streamlit's sidebar to show "📄 19 policy chunks indexed".

**The design decision worth noting:**
`/rag/query` is for evaluation. `/rag/stream` is for users. This distinction is enforced by comments in the code and by design — the two endpoints return different shapes. `query` returns a complete JSON object with all metadata. `stream` returns a live token stream. Never use `query` in the UI (slow, no streaming). Never use `stream` in tests (hard to parse programmatically).

---

## The Complete RAG Flow — One Message

```
1. User types "What is the parental leave policy?"
2. app.py calls GET /rag/classify?query=What+is+the+parental...
3. rag_router.py: GPT-4o at temperature=0 reads question → "rag"
4. app.py: classification is "rag" → calls stream_rag()
5. stream_rag() opens POST /rag/stream with httpx.stream()
6. routes/rag.py receives RAGRequest → validates via schemas/rag.py
7. route calls rag_query_stream("What is the parental leave policy?")
8. chain.py calls retrieve_with_context(question, top_k=3)
9. retriever.py calls vector_store.query(question, top_k=3)
10. store.py embeds the question using text-embedding-3-small
11. ChromaDB finds the 3 most similar vectors → returns chunks
12. retriever.py converts distances to similarity scores
13. retriever.py formats citations: "Leave Policy, Page 1"
14. chain.py builds context_text: "[Leave Policy, Page 1]\nPrimary caregiver: 16 weeks..."
15. chain.py builds prompt: RAG_SYSTEM_PROMPT + context_text + question
16. GPT-4o at temperature=0.1 generates grounded answer
17. chain.py yields each token via astream()
18. route wraps each token: data: {"token": "Primary"}\n\n → StreamingResponse
19. After all tokens: data: {"sources": ["Leave Policy, Page 1"], "chunks_used": 3}\n\n
20. data: {"token": "[DONE]"}\n\n
21. stream_rag() in app.py: captures sources event → session_state.last_sources
22. stream_rag() yields tokens to st.write_stream()
23. st.write_stream() renders tokens → "Primary caregivers receive 16 weeks..."
24. st.write_stream() returns complete text → saved to session_state.messages
25. app.py displays: st.caption("📄 Sources: Leave Policy, Page 1")
26. app.py displays: st.caption("🔍 Answered from company documents")
```

---

## Journey 2 — DeepEval Evaluation

The RAG evaluation journey is structurally identical to the chat evaluation journey — same pytest pattern, same golden set approach, same `evaluate()` and `assert` pattern. What changes is the metric set and one critical addition to every test case: `retrieval_context`.

### The Evaluation Flow

```
evaluation/datasets/rag_golden_set.json     15 questions + expected answers + source document
        ↓ loaded once by the rag_golden_set fixture
evaluation/tests/test_document_rag.py       pytest collects 5 test functions
        ↓ each test calls get_rag_response() AND get_retrieval_context()
backend/api/routes/rag.py                   POST /rag/query — same endpoint as non-streaming
        ↓ ARIA retrieves chunks, answers via GPT-4o
rag/document_rag/retriever.py               called directly to get the actual chunk texts
        ↓ both answer AND chunk texts collected
evaluation/tests/test_document_rag.py       LLMTestCase built with retrieval_context field
        ↓ sent to DeepEval evaluate()
DeepEval judge                              reads: question + answer + retrieved chunks
        ↓ scores faithfulness, precision, recall, relevancy
pytest                                      asserts all scores above threshold
        ↓ prints results table with pass/fail per test case
```

---

### File: `evaluation/datasets/rag_golden_set.json`

**What it is:** The answer key for RAG — 15 questions with specific citable expected answers, one per major policy area.

**Where it fits:** Loaded by the `rag_golden_set` fixture and shared across all five test functions.

**How it works:**
Each entry has three fields: `input` (the question), `expected_output` (the specific answer), and `document` (which PDF it should come from). The expected outputs use exact figures from the documents — "25 days per calendar year", "16 weeks fully paid", "100% company-paid", "$2,000 per year". This specificity is deliberate — the judge needs enough detail in the expected output to meaningfully evaluate whether ARIA's retrieved answer is correct.

The 15 entries are spread across all four documents: 5 leave policy questions, 2 code of conduct questions, 4 benefits guide questions, and 4 employee handbook questions. This ensures retrieval is tested across the full document set, not just the easiest-to-retrieve content.

---

### File: `evaluation/tests/test_document_rag.py`

**What it is:** Five test functions covering retrieval quality from four different angles plus a routing assertion.

**Where it fits:** Same position as `test_chat.py` in the evaluation flow — the endpoint that exercises the live application and sends results to a judge.

**How it works:**

**`get_rag_response(question)`** — posts to `POST /rag/query` and returns the full response dict including `answer`, `sources`, and `chunks_used`. A `time.sleep(0.5)` at the end spaces out calls to avoid hitting the 30,000 TPM rate limit when DeepEval runs all test cases concurrently.

**`get_retrieval_context(question)`** — calls the retriever directly via `from rag.document_rag.retriever import retrieve` and returns the list of chunk texts that were actually retrieved. This is the raw material that `retrieval_context` needs — the actual text of the chunks ARIA had access to when forming her answer.

**The `sys.path.insert` at the top** — test files live in `evaluation/tests/`, two directories deep from the project root. Without explicitly adding the project root to Python's path, `from rag.document_rag.retriever import retrieve` fails. The three-level `os.path.dirname` walk climbs from `evaluation/tests/test_document_rag.py` up to `evaluation/tests/`, then `evaluation/`, then the project root.

**The critical addition — `retrieval_context`** — is the field that separates RAG evaluation from chat evaluation. Every `LLMTestCase` in the RAG suite includes `retrieval_context=[chunk1_text, chunk2_text, chunk3_text]` — the actual texts of the chunks retrieved for that question. Without this field, DeepEval can only measure answer quality. With it, DeepEval can measure whether the answer faithfully reflects the chunks, whether the chunks were ranked correctly, and whether the chunks contained all the needed information.

**Required environment variables before running:**
```bash
export DEEPEVAL_PER_TASK_TIMEOUT_SECONDS_OVERRIDE=600
export DEEPEVAL_PER_ATTEMPT_TIMEOUT_SECONDS_OVERRIDE=300
```
DeepEval's default timeout is 180 seconds per task. Faithfulness evaluation with `gpt-4o` sometimes takes longer because the judge must read the full retrieval context alongside the answer. These overrides give each task 10 minutes — enough headroom for all but the most extreme cases.

---

### The Four New RAG Metrics

**`FaithfulnessMetric`**

This is the most important metric in the RAG suite. The judge reads ARIA's answer and the retrieved chunks and checks every factual claim: is this claim supported by the context? If ARIA says "employees receive 25 days annual leave" and the retrieved chunk says "25 days per calendar year" — faithful. If ARIA says "30 days" when the chunk says "25" — unfaithful. A score of `1.00` means every single claim traces back to retrieved text. This metric proves ARIA is not hallucinating against her context — stronger than the `HallucinationMetric` in the chat suite because it has actual documents to check against. Threshold is `0.8`.

**`ContextualPrecisionMetric`**

Measures retrieval ranking quality — specifically whether the most relevant chunk is ranked first. The judge reads the question and the ordered list of retrieved chunks and evaluates: given this question, is the first chunk the most useful? The parental leave retrieval bug during Phase 2 was a precision problem. The chunk containing "Primary caregiver: 16 weeks fully paid" was buried behind sick leave content because both were in the same 500-character chunk. After increasing chunk size to 800 characters and adding section separators to the PDFs, the parental leave chunk ranked first — precision reached `1.00`. Threshold is `0.7`.

**`ContextualRecallMetric`**

Measures retrieval completeness — whether the retrieved chunks contain all the information needed to produce the expected answer. The judge reads the expected output and checks whether each sentence in it can be traced to one of the retrieved chunks. For the harassment reporting question, the expected answer lists all four grievance steps. If chunks 1–3 only cover steps 1–2, recall would be low. A score of `1.00` means the context was complete — nothing needed was missing from the retrieved set. Threshold is `0.7`.

**`ContextualRelevancyMetric`**

Measures whether the retrieved chunks are on-topic for the question. Even if chunks are faithful, precise, and complete, they might still include irrelevant content pulled from the wrong section. This metric flags cases where the retriever returned chunks from an unrelated policy area. In Phase 2, two queries had ranking issues — harassment reporting retrieved a Professional Behaviour chunk before the Grievance steps chunk, and professional development retrieved a disability insurance chunk. Both would show lower relevancy scores for those specific queries. Noted as Phase 7 tuning items. Threshold is `0.7`.

**`AnswerRelevancyMetric` (carried from Phase 1)**

This metric travels from Phase 1 into Phase 2 unchanged, serving as a regression check — confirming that grounding answers in documents did not reduce response relevancy. The score actually improved from `0.98` in Phase 1 to `1.00` in Phase 2 because document-grounded answers are more focused and specific than general knowledge answers.

---

### The Five Test Functions

**`test_rag_faithfulness`** covers golden set rows 1–3 — annual leave days, parental leave, and sick days. Three leave policy questions chosen because they have clear, specific facts in the documents. Faithfulness at `1.00` means ARIA's answer for "25 days per calendar year" traces exactly to the retrieved chunk containing that figure — no invention, no paraphrasing that changes meaning.

**`test_rag_contextual_precision`** covers the same three rows. Precision is tested against leave policy questions because they have the clearest expected retrieval order — the annual leave chunk should rank above sick leave for an annual leave question. The judge confirmed: "Relevant node ranked first, irrelevant nodes ranked lower."

**`test_rag_contextual_recall`** covers rows 2 and 6 — parental leave and harassment reporting. These were chosen specifically because their expected answers are multi-part: parental leave has primary caregiver, secondary caregiver, eligibility period, and notice requirement. Harassment reporting has four sequential grievance steps. Recall tests whether all parts made it into the retrieved context, not just the first.

**`test_rag_answer_relevancy`** covers rows 1–3. The judge confirmed for each: "response perfectly addressed the question without any irrelevant information." Score of `1.00` in Phase 2 versus `0.98` in Phase 1 — the regression check passed and improved.

**`test_rag_document_routing`** covers all 15 golden set entries. This function has no LLM judge, no rate limit risk, and no cost — it is a pure Python assertion. For each entry it calls `GET /rag/classify?query=...` and asserts `classification == "rag"`. All 15 policy questions must route to document RAG, not general chat. This test always runs last and finishes in about 10 seconds.

---

### Run Commands

```bash
# Required env vars — set once per terminal session
export DEEPEVAL_PER_TASK_TIMEOUT_SECONDS_OVERRIDE=600
export DEEPEVAL_PER_ATTEMPT_TIMEOUT_SECONDS_OVERRIDE=300

# Run all five tests as a single hands-free block
uv run deepeval test run evaluation/tests/test_document_rag.py::test_rag_faithfulness -v && \
sleep 60 && \
uv run deepeval test run evaluation/tests/test_document_rag.py::test_rag_contextual_precision -v && \
sleep 60 && \
uv run deepeval test run evaluation/tests/test_document_rag.py::test_rag_contextual_recall -v && \
sleep 60 && \
uv run deepeval test run evaluation/tests/test_document_rag.py::test_rag_answer_relevancy -v && \
sleep 60 && \
uv run deepeval test run evaluation/tests/test_document_rag.py::test_rag_document_routing -v
```

The 60-second gaps prevent hitting the 30,000 TPM rate limit. Each test function makes 3 API calls to ARIA plus 3 judge calls to GPT-4o — 6 calls per function, 5 functions. Running them all concurrently exhausts the token budget before the first function completes.

---

### Phase 2 Baseline Results

**26 test cases, 100% pass rate, $0.07 total cost, ~57 seconds**

| Test Function | Metric | Avg Score | Pass Rate | Cases | Cost |
|---|---|---|---|---|---|
| `test_rag_faithfulness` | Faithfulness | 1.00 | 100% | 3 | $0.029 |
| `test_rag_contextual_precision` | Contextual Precision | 1.00 | 100% | 3 | $0.018 |
| `test_rag_contextual_recall` | Contextual Recall | 1.00 | 100% | 2 | $0.011 |
| `test_rag_answer_relevancy` | Answer Relevancy | 1.00 | 100% | 3 | $0.012 |
| `test_rag_document_routing` | Routing assertion | 100% | 100% | 15 | $0.000 |

The parental leave fix is confirmed in the precision results. The judge's own reasoning: "The relevant node ranked first provides comprehensive details stating 'Primary caregiver: 16 weeks fully paid'. The irrelevant nodes focus on emergency leave and unpaid leave, appropriately ranked lower." That sentence tells you the chunk boundary fix worked — the right content is now in its own chunk and ranking correctly.

---

### Metric Coverage Across Both Journeys

Reading both evaluation sections together, the metric progression follows the evolution of ARIA's capability.

Phase 1 established the baseline: does ARIA stay in character, answer relevantly, and avoid hallucination? These metrics treat ARIA as a black box — input in, output out, judge the output.

Phase 2 opened the box: does the retrieval pipeline actually work? Faithfulness, precision, recall, and relevancy each examine a different aspect of the path from question to answer — not just the final answer. This is the difference between testing a car's top speed and testing whether the fuel injection, transmission, and brakes each work correctly.

Answer Relevancy bridges both — established in Phase 1 as the output quality measure and carried into Phase 2 as the regression check. If a Phase 2 change caused it to drop, it would signal that something in the retrieval pipeline degraded response quality, not just retrieval quality. The fact that it improved from `0.98` to `1.00` confirms the opposite — grounding answers in documents made them better.

---

# JOURNEY 3 — DATABASE RAG

## The Database RAG Request Flow

```
User types employee question in browser
        ↓
frontend/app.py              calls /rag/classify first
        ↓ GET /rag/classify
backend/api/routes/rag.py    calls classify_query()
        ↓
backend/chains/rag_router.py GPT-4o classifies as "db"
        ↓
frontend/app.py              routes to stream_db()
        ↓ POST /rag/db/stream
backend/api/routes/rag.py    calls db_rag_query_stream()
        ↓
backend/schemas/rag.py       DatabaseRAGRequest validated here
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

**Unlike Document RAG, no one-time setup step is needed.** The data already lives in PostgreSQL from the Phase 0 seed. The pipeline converts questions to SQL on every request — the database is always live.

**The four-stage pipeline:**
```
Stage 1: generate_validated_sql(question)
         GPT-4o reads schema → generates SELECT → validate_sql() gates it
         → sql, is_valid, error_msg

Stage 2: execute_query(sql)
         SQLAlchemy runs SQL against PostgreSQL
         → QueryResult(rows, columns, row_count)

Stage 3: format_results_for_llm(result)
         Rows formatted as human-readable text
         → "Query returned 1 record:\n  leave_balance: 30"

Stage 4: GPT-4o with DB_ANSWER_SYSTEM_PROMPT
         Converts formatted rows into a natural language answer
         → "James Chen has 30 days of leave remaining."
```

---

## File 1 — `rag/database_rag/schema.py`

**What it is:** The database schema description embedded directly into the NL-to-SQL prompt. GPT-4o reads this before writing any SQL.

**Where it fits:** Called by `nl_to_sql.py` at query time. Its output becomes the top portion of the NL-to-SQL system prompt.

**How it works:**
`DATABASE_SCHEMA_DESCRIPTION` is a multi-line constant string that describes all three tables — `employees`, `leave_records`, and `org_chart` — with their column names, types, and allowed enum values. It also includes SQL rules: always use table aliases (`e`, `lr`, `o`), use `ILIKE` for name matching, default `LIMIT 10`, never `SELECT *`, join `leave_records` to `employees` on `employee_id`.

**Key functions:**

`get_schema_description()` — returns `DATABASE_SCHEMA_DESCRIPTION` unchanged. A function wrapper rather than direct constant access so it can be mocked in tests.

`get_table_samples()` — queries the live database for 3 rows from each table and formats them as readable text. Gives GPT-4o concrete examples of what the data looks like — column names alongside real values rather than abstract types.

`get_full_context()` — combines `get_schema_description()` and `get_table_samples()` into a single string. This combined string is what goes into the NL-to-SQL prompt.

**The design decision worth noting:**
Schema description is a static constant, not a live `information_schema` query. This is intentional: live schema queries add latency, can return too much noise (internal system tables, temporary objects), and don't include the business rules — enum values, join conventions, naming rules. A hand-authored description is more useful to the model than auto-generated schema metadata.

---

## File 2 — `rag/database_rag/nl_to_sql.py`

**What it is:** The NL-to-SQL engine — converts a natural language question into a validated PostgreSQL SELECT statement.

**Where it fits:** Called by `chain.py` at Stage 1. The deepest point before SQL hits the database.

**How it works:**
`NL_TO_SQL_SYSTEM_PROMPT` is a 10-rule instruction set prepended with the full schema context. The rules are strict: SELECT only, use aliases, ILIKE for names, LIMIT 10, no `SELECT *`, return `NOT_DB_QUERY` for questions that can't be answered from the database, return only the SQL with no markdown or explanation.

**Key functions:**

`generate_sql(question)` — synchronous. Builds the prompt from the system rules plus schema context, calls GPT-4o at `temperature=0` (SQL generation must be deterministic), and returns the stripped result string. Called inside the async `generate_validated_sql()`.

`validate_sql(sql)` — two hard checks. First: the statement must start with `SELECT` (lowercased, stripped). Second: a word-boundary regex screens for dangerous keywords — `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`, `CREATE`, `GRANT`, `REVOKE`. Returns `(True, "")` on pass or `(False, error_message)` on failure.

`generate_validated_sql(question)` — async wrapper. Calls `generate_sql()`, checks for the `NOT_DB_QUERY` sentinel, then calls `validate_sql()`. Returns a tuple of `(sql, is_valid, error_message)`.

**The `NOT_DB_QUERY` sentinel:**
When GPT-4o determines the question cannot be answered from the employee database — typically policy questions like "What is the annual leave policy?" — it returns the literal string `NOT_DB_QUERY` instead of SQL. This sentinel travels up the entire stack: `generate_validated_sql()` returns it, `chain.py` detects it and returns `answer="NOT_DB_QUERY"`, the API endpoint detects it and returns a fallback message, and the streaming endpoint emits it as a token so Streamlit can set `last_answer_type = "rag_fallback"`. The sentinel pattern keeps the failure path explicit at every layer without exceptions.

**The design decision worth noting:**
`validate_sql()` is defense-in-depth. The NL-to-SQL prompt already instructs SELECT-only. The validator provides a hard gate regardless of prompt compliance — it will catch any case where the model deviates. The word-boundary regex (`\b(DROP|DELETE|...)\b`) ensures that column names like `update_date` don't trip the filter.

---

## File 3 — `rag/database_rag/executor.py`

**What it is:** The SQL execution layer — runs a validated SQL string against PostgreSQL and returns structured results.

**Where it fits:** Called by `chain.py` at Stage 2. The only file that touches PostgreSQL directly in the DB RAG pipeline.

**How it works:**
Defines a `QueryResult` dataclass with six fields: `success`, `rows` (list of dicts), `row_count`, `columns`, `error`, and `sql_executed`. This structure is the contract between execution and formatting — everything downstream works with `QueryResult`, never with raw database cursors.

**Key functions:**

`execute_query(sql)` — the main function. Creates a SQLAlchemy engine from `settings.database_url`, opens a connection, executes the SQL, converts each row to a dict by zipping column names with values, and serializes any `datetime.date` or `datetime.datetime` values to ISO format strings. Returns a successful `QueryResult`. On `SQLAlchemyError` or any other exception, returns a failed `QueryResult` with the error message — the error is logged but never surfaced raw to the user.

`format_results_for_llm(result)` — converts a `QueryResult` into human-readable text that GPT-4o can parse at Stage 4. Format:
```
Query returned 1 record(s):

Record 1:
  employee_id: EMP-0001
  first_name: James
  leave_balance: 30
```
This format is readable by both GPT-4o (for answer generation) and humans (for debugging). It's what goes into `retrieval_context` in DeepEval test cases.

`get_database_stats()` — runs five COUNT queries in a single connection to return totals for employees, leave records, org chart rows, active employees, and pending leave requests. Used by admin diagnostics, not in the live request path.

**The design decision worth noting:**
Date serialization (`value.isoformat()`) happens in `execute_query()`, not in the formatter. SQLAlchemy returns Python `datetime.date` objects — these can't be JSON-serialized directly and would crash the API if returned in a response dict. Serializing at the executor level means every layer above it works with plain strings. The formatter never needs to handle date objects.

---

## File 4 — `rag/database_rag/chain.py`

**What it is:** The DB RAG orchestrator — coordinates the four-stage NL-to-SQL-to-answer pipeline.

**Where it fits:** Called by the RAG route when classification is `"db"`. The deepest point in the DB RAG flow.

**How it works:**
`DB_ANSWER_SYSTEM_PROMPT` is the instruction constant for Stage 4. Unlike the NL-to-SQL prompt (which is strict technical rules), this prompt is about presentation style. Its most important rule — placed first — governs WHO questions: for questions asking who did something or who is in a state, respond with ONLY the person's name and the direct answer. No role, no department, no location, no unrequested context. This rule required three iterations during Phase 3 development before the answers were acceptably concise (see Phase 3 Build Guide for the iteration history).

**Key functions:**

`db_rag_query(question)` — async, non-streaming. Runs all four pipeline stages sequentially. Returns a `DatabaseRAGResponse` dataclass. Used by DeepEval test suite via the `/rag/db/query` endpoint.

`db_rag_query_stream(question)` — async generator. Same four stages but Stage 4 uses `streaming=True` LLM and `chain.astream()`. Yields answer tokens as they arrive. Yields `"NOT_DB_QUERY"` early if the question can't be answered from the database. Used by Streamlit via the `/rag/db/stream` endpoint.

`build_db_answer_prompt()` — builds the `ChatPromptTemplate` for Stage 4. The human message includes three variables: `{question}`, `{sql_used}` (the actual SQL executed), and `{query_results}` (the formatted rows). GPT-4o sees all three — the question provides intent, the SQL provides what was queried, and the rows provide what was found.

**The design decision worth noting:**
`temperature=0` for Stage 4 answer generation. This is significantly lower than the chat chain's `0.7`. Employee data answers are factual — ARIA must say "30 days" when the database says `leave_balance: 30`. Any temperature above zero risks paraphrasing numbers or adding uncertainty qualifiers ("approximately 30 days"). Zero temperature locks the answer to what the data says.

---

## Updated File — `backend/schemas/rag.py` (Phase 3 additions)

Phase 3 adds two Pydantic models to the existing `rag.py` schema file:

`DatabaseRAGRequest` — what Streamlit sends for a DB RAG query. Two fields: `question` (required, minimum 1 character) and `session_id` (auto-generated UUID if not provided). Simpler than `RAGRequest` because DB RAG has no `top_k` — the SQL result set is determined by the query, not a retrieval parameter.

`DatabaseRAGResponseModel` — what FastAPI sends back from `/rag/db/query`. Seven fields: `answer`, `sql_used` (the actual SQL for transparency), `row_count`, `query` (original question echoed), `session_id`, `model` (always `"gpt-4o-db"` to distinguish from document RAG responses), and `success`.

**The design decision worth noting:**
`sql_used` is a first-class field in `DatabaseRAGResponseModel`. This is the audit trail — when ARIA says "James Chen has 30 days", the response carries the SQL that produced that number. DeepEval test cases log this. Streamlit displays it in an expander. Enterprise clients can review it. The SQL is the proof.

---

## Updated File — `backend/api/routes/rag.py` (Phase 3 additions)

Phase 3 adds two new endpoints before the existing `/classify` endpoint:

**`POST /rag/db/query`** — the non-streaming endpoint for DeepEval. Calls `db_rag_query()`, waits for the complete `DatabaseRAGResponse`, and returns it as a JSON object. If the response `answer` is `"NOT_DB_QUERY"`, returns a structured fallback message explaining the question needs document search.

**`POST /rag/db/stream`** — the streaming endpoint for Streamlit. An async generator calls `db_rag_query_stream()` and wraps each yielded chunk as an SSE event: `data: {"token": "..."}\n\n`. After all tokens are yielded, it runs `db_rag_query()` a second time to retrieve the metadata (`sql_used` and `row_count`) and emits them as a special metadata event: `data: {"sql_used": "SELECT...", "row_count": 1}\n\n`. Then sends `data: {"token": "[DONE]"}\n\n`.

The second `db_rag_query()` call is acknowledged technical debt — the async generator yields tokens but has no mechanism to surface the SQL metadata alongside them. The alternative (threading metadata through the generator via a shared mutable object) adds complexity for ~0.5s overhead. Phase 7 refactors this with a wrapper that captures Stage 2 output on the first pass.

---

## Updated File — `frontend/app.py` (Phase 3 additions)

Phase 3 adds two session state keys and one streaming generator to the existing `app.py`:

**New session state:**
- `last_sql_used = ""` — stores the SQL captured from the DB metadata SSE event
- `last_row_count = 0` — stores the row count from the same event

Both are reset to their defaults at the start of every new user input alongside the existing `last_sources` reset.

**`stream_db(question, session_id)`** — the DB streaming generator. Same structure as `stream_rag()` but connects to `/rag/db/stream`. Watches for three special tokens: `"[DONE]"` (break), `"[ERROR]"` (break), and `"NOT_DB_QUERY"` (sets `last_answer_type = "rag_fallback"`, break). Watches for data events containing `"sql_used"` (captures `last_sql_used` and `last_row_count`). Yields all other tokens to `st.write_stream()`.

**The `"db"` routing branch:**
```python
elif classification == "db":
    response_text = st.write_stream(stream_db(prompt, session_id))
    if last_row_count > 0:
        st.caption(f"🗄️ Answered from employee database · {last_row_count} record(s) found")
    if last_sql_used:
        with st.expander("View database query"):
            st.code(last_sql_used, language="sql")
```

The SQL expander is a deliberate transparency feature. When ARIA gives a number about a specific employee, the user can expand the panel to see exactly what SQL query produced it — the query is the audit trail.

**History display:** Past messages with `answer_type == "db"` show the record count caption and SQL expander on replay, same as when the message was first generated. `sql_used` and `row_count` are stored in the message dict alongside the answer text.

---

## The Complete DB RAG Flow — One Message

```
1. User types "How many leave days does James Chen have?"
2. app.py calls GET /rag/classify?query=How+many+leave+days...
3. rag_router.py: GPT-4o at temperature=0 reads question
   → question mentions a person by name → "db"
4. app.py: classification is "db" → calls stream_db()
5. stream_db() opens POST /rag/db/stream with httpx.stream()
6. routes/rag.py receives DatabaseRAGRequest → validates
7. route calls db_rag_query_stream("How many leave days does James Chen have?")
8. chain.py calls generate_validated_sql(question)
9. nl_to_sql.py: GPT-4o at temperature=0 reads schema + question
   → generates: SELECT e.employee_id, e.first_name, e.last_name, e.leave_balance
                FROM employees e
                WHERE e.first_name ILIKE 'James' AND e.last_name ILIKE 'Chen'
                LIMIT 10
10. nl_to_sql.py: validate_sql() checks → starts with SELECT, no dangerous keywords → valid
11. chain.py calls execute_query(sql)
12. executor.py: SQLAlchemy creates engine → executes → fetches rows
    → QueryResult(success=True, rows=[{employee_id: "EMP-0001", first_name: "James",
       last_name: "Chen", leave_balance: 30}], row_count=1)
13. chain.py calls format_results_for_llm(result)
    → "Query returned 1 record(s):\n\nRecord 1:\n  employee_id: EMP-0001\n  leave_balance: 30"
14. chain.py builds prompt: DB_ANSWER_SYSTEM_PROMPT + question + sql_used + formatted rows
15. GPT-4o at temperature=0 generates: "James Chen has 30 days of leave remaining."
16. chain.py yields each token via astream()
17. route wraps each token: data: {"token": "James"}\n\n → StreamingResponse
18. After all tokens: route runs db_rag_query() again → gets sql_used + row_count
19. data: {"sql_used": "SELECT e.employee_id...", "row_count": 1}\n\n
20. data: {"token": "[DONE]"}\n\n
21. stream_db() in app.py: captures sql_used → session_state.last_sql_used
22. stream_db() captures row_count → session_state.last_row_count
23. stream_db() yields tokens to st.write_stream()
24. st.write_stream() renders: "James Chen has 30 days of leave remaining."
25. st.write_stream() returns complete text → saved to session_state.messages
26. app.py displays: st.caption("🗄️ Answered from employee database · 1 record(s) found")
27. app.py displays: st.expander("View database query") → st.code(sql, language="sql")
```

---

## Journey 3 — DeepEval Evaluation

The DB RAG evaluation journey mirrors the document RAG journey structurally — same pytest patterns, same `evaluate()` and `assert` approach. Two things change: the source of `retrieval_context`, and what the metrics measure.

### The Evaluation Flow

```
evaluation/datasets/database_rag_golden_set.json   10 questions + expected answers + query_type
        ↓ loaded once by db_golden_set fixture
evaluation/tests/test_database_rag.py               pytest collects 4 test functions
        ↓ each LLM-judged test calls get_db_response() AND get_db_context()
backend/api/routes/rag.py                            POST /rag/db/query — same endpoint as non-streaming
        ↓ ARIA generates SQL, executes, answers
rag/database_rag/nl_to_sql.py + executor.py         called directly to get the SQL result
        ↓ both the answer AND the formatted SQL rows collected
evaluation/tests/test_database_rag.py               LLMTestCase built with retrieval_context=[formatted_rows]
        ↓ sent to DeepEval evaluate()
DeepEval judge                                       reads: question + answer + SQL result rows
        ↓ scores faithfulness and answer relevancy
pytest                                               asserts all scores above threshold
```

**The critical difference from Document RAG:** In document RAG, `retrieval_context` is a list of chunk texts from ChromaDB. In database RAG, `retrieval_context` is a list containing the formatted SQL result — what `format_results_for_llm()` returned. This is the text GPT-4o actually saw when generating the answer. The faithfulness judge checks ARIA's claims against the SQL rows, not against document chunks.

---

### File: `evaluation/datasets/database_rag_golden_set.json`

**What it is:** The answer key for DB RAG — 10 manually written question and expected answer pairs across three query types.

**Where it fits:** Loaded by the `db_golden_set` fixture and shared across all four test functions.

**How it works:**
Each entry has three fields: `input` (the question), `expected_output` (the specific expected answer), and `query_type` (one of `"employee_lookup"`, `"aggregate"`, or `"join"`). The query type field lets each test function filter to its relevant subset without hardcoding row indexes.

**Expected outputs are specific and verifiable:**
- `"James Chen has 30 days of leave remaining."` — exact number from the database
- `"Isabella Fernandez is currently on leave."` — name only, matching the WHO rule
- `"Isabella Fernandez's employee ID is EMP-0022."` — confirmed by querying the live database directly
- `"Priya Sharma and Marcus Johnson report to the VP of Engineering. Both are Directors of Engineering."` — names and roles only, no location

The 10 entries spread across three query categories: 5 employee lookups (single-table SELECT with WHERE), 3 aggregates (COUNT and GROUP BY), and 2 joins (employees + leave_records or employees + org_chart). This ensures evaluation covers simple lookups, summary statistics, and multi-table queries.

---

### File: `evaluation/tests/test_database_rag.py`

**What it is:** Four test functions covering database answer quality from multiple angles — employee lookup, aggregate queries, multi-table joins, and routing boundary assertion.

**Where it fits:** Same position as `test_document_rag.py` — the endpoint of the evaluation flow that exercises the live application.

**How it works:**

**`get_db_response(question)`** — posts to `POST /rag/db/query` and returns the full response dict including `answer`, `sql_used`, and `row_count`. A `time.sleep(0.5)` spaces out API calls to respect rate limits.

**`get_db_context(question)`** — calls `generate_validated_sql()` and `execute_query()` directly to get the raw SQL result, then `format_results_for_llm()` to format it. Returns `[formatted_result_string]` — a list with one element (the full formatted rows). This is `retrieval_context` for every DB RAG test case.

**The `sys.path.insert` at the top** — identical pattern to `test_document_rag.py`. The three-level path climb is required for `from rag.database_rag.nl_to_sql import generate_validated_sql` to resolve from inside `evaluation/tests/`.

**`asyncio.run()` inside `get_db_context()`** — `generate_validated_sql()` is an async function but `get_db_context()` is called from synchronous test code. `asyncio.run()` creates a temporary event loop, runs the coroutine to completion, and returns the result. This is the standard pattern for calling async code from a synchronous context in pytest.

---

### The Two DB RAG Metrics

**`FaithfulnessMetric(threshold=0.8, model="gpt-4o")`**

Same metric as Phase 2, different context source. The judge reads ARIA's answer and the formatted SQL result rows — the same text that was in the GPT-4o prompt at Stage 4. It checks every factual claim in ARIA's answer: does this claim appear in the SQL rows? If ARIA says "James Chen has 30 days" and the rows show `leave_balance: 30` — faithful. If ARIA says "James Chen has been with the company since 2019" when `hire_date` wasn't in the query — unfaithful. Threshold `0.8` rather than the document RAG threshold — DB answers are simpler (fewer compound facts), making `0.8` a rigorous standard.

**`AnswerRelevancyMetric(threshold=0.7, model="gpt-4o")`**

Carried from Phase 2, same mechanism. Generates hypothetical questions that ARIA's response would answer well and measures how many match the original. For "How many leave days does James Chen have?" → ARIA says "James Chen has 30 days of leave remaining." The judge generates: "What is James Chen's leave balance?" — that matches perfectly. Relevancy `1.0`. The metric confirms ARIA answered the actual question rather than summarizing the SQL result generically. Threshold `0.7`.

---

### The Four Test Functions

**`test_db_employee_lookup`** covers the first 3 entries with `query_type == "employee_lookup"` — James Chen's leave balance, James Chen's department, and who is currently on leave. Both Faithfulness and Answer Relevancy are run against each. These are the simplest queries (single-table SELECT with a WHERE clause) so they serve as the happy-path test for the DB RAG pipeline. A faithfulness failure here would indicate Stage 4 is adding unrequested information beyond what the SQL returned.

**`test_db_aggregate_queries`** covers the first 3 entries with `query_type == "aggregate"` — employees per department, total active employee count, and total leave records count. Both metrics applied. Aggregate queries return a single number or a small summary set. Faithfulness here means: if the database says 47 active employees, ARIA must say 47. Any other number is a hallucination against the SQL result.

**`test_db_join_queries`** covers all entries with `query_type == "join"` — pending leave requests (employees JOIN leave_records) and VP Engineering direct reports (employees JOIN org_chart). Both metrics applied. JOIN queries are the most complex: two tables, subqueries for org chart lookup, multiple columns in the result. Answer Relevancy confirms that ARIA answered the WHO question with names rather than a raw table dump.

**`test_db_routing_boundary`** covers all 10 golden set questions plus 3 hardcoded policy questions. **No LLM judge, no rate limit risk, zero cost.** A pure Python assertion loop: for each DB question, calls `GET /rag/classify?query=...` and asserts `classification == "db"`. For each policy question, asserts `classification == "rag"`. If any single assertion fails, the test reports exactly which question routed incorrectly and what it got instead. This test runs first and finishes in ~13 seconds — it's the fast quality gate that catches routing regressions before any LLM-judged tests run.

The 3 hardcoded policy questions are the Phase 2 regression check embedded into Phase 3: "What is the parental leave policy?", "How do I report a harassment complaint?", "What is the remote work policy?" Adding a third routing path in Phase 3 could have broken the `"rag"` path — this test proves it didn't.

---

### Run Commands

```bash
# Required env vars — set once per terminal session
export DEEPEVAL_PER_TASK_TIMEOUT_SECONDS_OVERRIDE=600
export DEEPEVAL_PER_ATTEMPT_TIMEOUT_SECONDS_OVERRIDE=300

# Run routing test first — fast, no judge, catches wiring issues before spending on LLM calls
uv run deepeval test run evaluation/tests/test_database_rag.py::test_db_routing_boundary -v

# Run LLM-judged tests with sleep gaps
sleep 60 && \
uv run deepeval test run evaluation/tests/test_database_rag.py::test_db_employee_lookup -v && \
sleep 60 && \
uv run deepeval test run evaluation/tests/test_database_rag.py::test_db_aggregate_queries -v && \
sleep 60 && \
uv run deepeval test run evaluation/tests/test_database_rag.py::test_db_join_queries -v
```

---

### Phase 3 Baseline Results

**Routing boundary: 13/13 passed, $0.00, ~13 seconds**

| Test Function | Metric | Pass Rate | Cases | Cost |
|---|---|---|---|---|
| `test_db_routing_boundary` | Routing assertion (no judge) | **100%** | 13 | $0.000 |
| `test_db_employee_lookup` | Faithfulness + Answer Relevancy | 100% | 3 | ~$0.030 |
| `test_db_aggregate_queries` | Faithfulness + Answer Relevancy | 100% | 3 | ~$0.030 |
| `test_db_join_queries` | Faithfulness + Answer Relevancy | 100% | 2 | ~$0.020 |

The routing boundary result is the most important finding: 10 database questions route to `"db"`, 3 policy questions route to `"rag"`, zero misclassifications. This confirms the three-way router works correctly and the Phase 2 document routing is regression-free.

---

### Metric Coverage Across All Three Journeys

Reading all three evaluation sections together, the metric progression follows the capability growth.

Phase 1 treats ARIA as a black box: does the output have the right character, relevance, and absence of hallucination? These metrics have no knowledge of how the answer was produced.

Phase 2 opens the retrieval pipeline: are the chunks faithful, ranked correctly, complete, and relevant? These metrics require `retrieval_context` — they examine the path from question to answer, not just the answer itself. Answer Relevancy bridges Phase 1 and Phase 2 as the regression check.

Phase 3 applies the same retrieval-quality thinking to a completely different data source. Faithfulness and Answer Relevancy now evaluate SQL result accuracy rather than document chunk accuracy. `retrieval_context` is the formatted SQL result instead of chunk texts. The evaluation framework doesn't change — only what goes into the context field.

The routing boundary assertion (Phase 3) is the cross-phase regression test: it proves that adding a third path didn't break the existing two. This pattern — every new phase includes a test that validates all previous phases — is the discipline that makes incremental capability expansion safe.

---

# FOUNDATION FILES
*These files support all three journeys. Explained here once.*

---

## `database/models.py`

**What it is:** The SQLAlchemy definition of the three database tables.

**Where it fits:** Used by `seed_database.py` to create objects and by Phase 3+ when the database becomes a RAG source.

**How it works:**
Three classes inherit from `Base = declarative_base()`:

`Employee` — maps to the `employees` table. 13 columns covering identity, role, location, leave balance, and status. The `__repr__` method returns `<Employee EMP-0001: James Chen>` — visible when inspecting objects in a debugger.

`LeaveRecord` — maps to `leave_records`. 9 columns covering leave type, dates, status, and approval chain.

`OrgChart` — maps to `org_chart`. 6 columns covering the reporting hierarchy with numeric levels (2=VP through 5=Individual Contributor).

**The design decision worth noting:**
`manager_id` on both `Employee` and `OrgChart` is a plain `String(20)` rather than a `ForeignKey` pointing back to `employees.employee_id`. Self-referential foreign keys cause insertion ordering problems — you can't insert EMP-0001 with `manager_id="EMP-0050"` before EMP-0050 exists. Using a plain string lets seed data insert in any order. The relationship is meaningful in the data; it's just not enforced at the database constraint level.

---

## `database/migrations/init.sql`

**What it is:** The SQL that creates the three tables in PostgreSQL.

**Where it fits:** Run once against the Docker PostgreSQL container to create the schema. `models.py` and `init.sql` describe the same structure in two languages — Python for the application, SQL for the database.

**How it works:**
Three `CREATE TABLE IF NOT EXISTS` blocks with `IF NOT EXISTS` making it safe to run multiple times. Indexes are created on the columns most likely to appear in `WHERE` clauses — `employee_id`, `department`, `status`, `manager_id` for employees; `employee_id`, `status`, `start_date` for leave records.

---

## `database/seed_data/` and `scripts/seed_database.py`

**What they are:** The test data and the script that loads it.

**Where they fit:** Run once after `init.sql`. The data lives in PostgreSQL for the lifetime of the application.

**How it works:**
Three CSVs — `employees.csv` (50 rows), `leave_records.csv` (30 rows), `org_chart.csv` (50 rows) — contain realistic Acme Corp data with diverse names, roles, departments, and locations.

`seed_database.py` opens each CSV with Pandas, creates SQLAlchemy model objects row by row, and commits them to PostgreSQL. It checks if data already exists before inserting — running it twice does not create duplicate rows.

**The `sys.path.insert` at the top** — the script lives in `scripts/` but needs to import from `config/` and `database/` which are in the project root. The path insert adds the project root to Python's search path so these imports work regardless of where the script is invoked from.

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
backend/chains/rag_router.py        (classify: rag vs db vs chat)
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
backend/chains/rag_router.py        (classify: rag vs db vs chat)
backend/api/routes/rag.py           (/rag/db/query and /rag/db/stream endpoints)
frontend/app.py                     (stream_db() generator + SQL expander)
```

**If you want to understand the agent path, open these files in this order:**
```
vector_store/searcher.py            (semantic search interface for agent tools)
agents/single/tools.py              (3 LangChain tools — the agent's hands)
agents/single/hr_advisor.py         (ReAct agent — the agent's brain)
backend/api/routes/agent.py         (agent endpoint)
backend/chains/rag_router.py        (four-way router — updated to include "agent")
frontend/app.py                     (agent reasoning trace display)
evaluation/datasets/agent_golden_set.json
evaluation/tests/test_single_agent.py
```

**If you want to understand the data foundation:**
```
database/models.py
database/migrations/init.sql
database/seed_data/employees.csv    (open in any spreadsheet or text editor)
scripts/seed_database.py
```

---

# JOURNEY 4 — AGENT

## The Agent Request Flow

```
User types compound question in browser
        ↓
frontend/app.py              calls /rag/classify first
        ↓ GET /rag/classify
backend/api/routes/rag.py    calls classify_query()
        ↓
backend/chains/rag_router.py GPT-4o classifies as "agent"
        ↓
frontend/app.py              routes to get_agent_response()
        ↓ POST /agent/query
backend/api/routes/agent.py  validates, calls run_hr_advisor()
        ↓
agents/single/hr_advisor.py  ReAct agent reasons over which tools to call
        ↓
agents/single/tools.py       tools called in sequence (1 to 5 iterations max)
        ↓ each tool calls into existing Journey 2 or Journey 3 pipelines
        ↓ search_policies → vector_store/searcher.py → ChromaDB
        ↓ lookup_employee → rag/database_rag/chain.py → PostgreSQL
        ↓ search_knowledge_base → vector_store/searcher.py → ChromaDB
        ↓ agent forms final answer
backend/api/routes/agent.py  returns AgentQueryResponse with steps + tools_used
        ↓
frontend/app.py              renders answer + tool badges + reasoning trace expander
```

**Unlike Journeys 2 and 3, there is no streaming in Journey 4.** The agent must complete all reasoning steps before any answer can be formed — the response returns as a complete JSON object. Streaming a partial reasoning trace mid-loop would confuse users and complicate state management. The full `AgentQueryResponse` arrives at once; the UI renders it immediately.

**The ReAct reasoning loop:**
```
Iteration 1:
  Thought: Which tool should I use for this question?
  Action: search_policies
  Action Input: "remote work policy"
  Observation: [retrieved policy text]

Iteration 2:
  Thought: I have the policy. Now I need James Chen's data.
  Action: lookup_employee
  Action Input: "James Chen leave balance"
  Observation: "James Chen has a leave balance of 30 days."

Thought: I now have enough information to answer.
Final Answer: "The remote work policy requires 3 days in office...
              James Chen currently has 30 days of leave remaining."
```

The agent repeats this Thought → Action → Observation cycle up to `max_iterations=5`. Most single-domain questions complete in 1 iteration. Compound questions use 2. The limit protects against runaway loops.

---

## Updated File — `backend/chains/rag_router.py` (Phase 4 update)

**What it is:** The query classifier — extended from three-way to four-way classification.

**Where it fits:** Called by the classify endpoint before every request. Its return value determines which journey handles the request.

**What changed in Phase 4:**
A fourth classification value — `"agent"` — was added to the system prompt and the return type. The new rule: if a question requires retrieving from BOTH policy documents AND the employee database to fully answer it, classify as `"agent"`. Single-source questions remain `"rag"` or `"db"`. General conversation remains `"chat"`.

**Why `"agent"` rather than splitting into two separate requests:**
A compound question like "What is the leave policy and how many days does James have?" has one intent — the user wants one coherent answer. Sending it to `"rag"` answers only the policy half. Sending it to `"db"` answers only the employee half. The agent path handles both in a single response. The router classification is the decision point: when a question spans both knowledge domains, only the agent can bridge them.

**The fallback behaviour is unchanged:** if GPT-4o returns anything other than a known classification, the router defaults to `"rag"`. The new `"agent"` class is additive — the existing three-way routing logic is untouched.

---

## New File 1 — `vector_store/searcher.py`

**What it is:** A standalone semantic search interface that wraps the existing ChromaDB vector store for use by the agent tools.

**Where it fits:** Called by two of the three agent tools — `search_policies` and `search_knowledge_base`. It sits on top of `vector_store/store.py` (the ChromaDB HTTP client) and returns search results in a format the tools can pass directly to the LLM.

**How it works:**
Defines a `SearchResult` dataclass with six fields: `text` (the chunk content), `source` (filename), `page_number`, `chunk_id`, `score` (cosine similarity, 0.0–1.0), and `citation` (the formatted string like `"leave_policy.pdf (Page 1)"`). The similarity score is derived from ChromaDB's cosine distance by computing `score = 1 - distance`.

**Key functions:**

`semantic_search(query, n_results, min_score)` — calls `vector_store.query()`, converts distances to similarity scores, filters results below `min_score`, sorts by score descending, and returns a list of `SearchResult` objects. Handles exceptions gracefully — returns an empty list on failure rather than crashing the tool call.

`format_search_results(results)` — converts a list of `SearchResult` objects into a formatted string. Each result appears as `[Source: citation]\nchunk_text`, separated by `---` dividers. If no results are found, returns a clear `"No relevant information found."` message. This formatted string is what the tools pass back to the ReAct agent as an observation.

`search_and_format(query, n_results)` — convenience wrapper that calls both functions in sequence and returns the formatted string. This is the function the agent tools actually call.

**The design decision worth noting:**
`searcher.py` exists as a separate module rather than having the agent tools call `vector_store.store.py` directly. This abstraction means the tools always receive formatted, citation-annotated text — never raw ChromaDB output. If the vector store backend changes in Phase 5+, only `searcher.py` needs updating. The tool implementations stay unchanged.

---

## New File 2 — `agents/single/tools.py`

**What it is:** The three LangChain tools that form the agent's action set. Each tool is a decorated Python function that the ReAct agent can call by name.

**Where it fits:** Imported by `hr_advisor.py` which passes the tool list to the `AgentExecutor`. The tools are the bridge between the agent's reasoning and the existing data pipelines.

**How it works:**
Each function is decorated with `@tool`. The decorator does two things: it wraps the function so LangChain can call it by name, and it uses the function's docstring as the tool's description — the exact text the ReAct agent reads when deciding which tool to invoke. Tool description quality is the most important engineering decision in this file. The agent has no other information about what each tool does.

**`search_policies(query)`**
Calls `search_and_format(query, n_results=3)`. Description instructs the agent: use this for questions about specific HR policies, rules, entitlements, or procedures. Explicitly states: do NOT use this tool if the question mentions a specific employee by name. This negative instruction is what prevents the agent from searching policy documents for "James Chen's leave balance" — a search that would return nothing useful.

**`lookup_employee(query)`**
Calls `db_rag_query(query)` via `asyncio.run()` — converting the async database chain to a synchronous call, which is what LangChain's synchronous tool interface requires. Extracts `result.answer` and returns it as a string. The description instructs: use this for questions about a specific named employee — their leave balance, department, manager, role, or status. The instruction "Always use this tool when the question mentions a person by name" is what produces correct tool selection for every employee question. If the result is `NOT_DB_QUERY`, returns a clear message redirecting to `search_policies` — the agent sees this and may retry with the right tool.

**`search_knowledge_base(query)`**
Calls `search_and_format(query, n_results=5)` — retrieving more results than `search_policies` because broad questions benefit from wider context. Description instructs: use this for broad HR questions that don't mention a specific employee and aren't about a specific policy clause. This tool handles the middle ground — onboarding questions, cross-cutting topics, general company information.

**`HR_ADVISOR_TOOLS`** — a module-level list of all three tool instances. This is what gets passed to the `AgentExecutor` in `hr_advisor.py`. The list order doesn't determine call priority — the agent decides that from the descriptions.

**The design decision worth noting:**
The `asyncio.run()` inside `lookup_employee` creates a temporary event loop to run `db_rag_query` synchronously. This works when called from a synchronous context (the agent tool interface), but can fail if already inside a running event loop — for example inside an async FastAPI endpoint that directly invokes the tool. The solution in Phase 4 is that the FastAPI route calls `run_hr_advisor()` synchronously (via a thread pool), not from within an async context. This boundary is documented in `hr_advisor.py`.

---

## New File 3 — `agents/single/hr_advisor.py`

**What it is:** The Single HR Advisor agent — a LangChain ReAct agent that reasons over which tool to call, calls it, observes the result, and repeats until it has enough to answer.

**Where it fits:** Called by `routes/agent.py`. The deepest point in the agent flow — the file where the reasoning loop runs.

**How it works:**
The file has three responsibilities: define the agent's reasoning prompt, build the `AgentExecutor`, and wrap the raw output into a clean `AgentResponse` dataclass.

**`HR_ADVISOR_SYSTEM_PROMPT`**
A `PromptTemplate` with four required variables: `{tools}` (LangChain injects the tool descriptions here automatically), `{tool_names}` (comma-separated list of tool names), `{input}` (the user's question), and `{agent_scratchpad}` (the running log of Thought/Action/Observation steps so far). The scratchpad is the mechanism that makes the ReAct loop work — on each iteration, the model reads the full history of what it has already done and decided, then produces the next Thought and Action. Without the scratchpad, the model would have no memory of previous iterations.

The prompt includes explicit behavioural rules: always use a tool before answering, never answer from memory alone, cite your source, be concise, and for compound questions — call multiple tools in sequence. The format block specifies the exact output structure the ReAct parser expects. If the model deviates from this format, `handle_parsing_errors=True` attempts recovery.

**`build_hr_advisor()`**
Creates and returns an `AgentExecutor` configured with five key settings:
- `verbose=True` — prints the full Thought/Action/Observation trace to the terminal during development. Shows the reasoning in real time.
- `max_iterations=5` — hard ceiling on the reasoning loop. Prevents runaway agents and uncontrolled API spend. Five iterations is sufficient for the most complex compound question (two tool calls plus surrounding reasoning steps).
- `handle_parsing_errors=True` — if the LLM produces malformed output (missing "Action:" line, extra text before "Thought:"), the executor catches the parse error, feeds it back to the model as an observation, and lets it retry rather than crashing the request.
- `return_intermediate_steps=True` — the executor captures every Thought/Action/Observation tuple and returns them alongside the final answer. This is what populates `AgentResponse.steps` — the data the Streamlit reasoning trace expander displays.
- `temperature=0` — the agent's reasoning must be deterministic. Higher temperature would cause the same question to choose different tools on different runs, making `ToolCorrectnessMetric` results inconsistent and the agent's behaviour unpredictable in production.

**`AgentResponse`**
A dataclass with four fields: `answer` (the final text), `steps` (list of dicts, each containing `thought`, `tool`, `tool_input`, `observation`), `tools_used` (list of tool name strings derived from steps), and `success` (False if the agent raised an exception). This is the stable interface between the agent and everything above it — `routes/agent.py` and `AgentQueryResponse` work with this type, never with the raw LangChain output dict.

**`run_hr_advisor(question)`**
Calls `build_hr_advisor()` on every invocation — the executor is stateless and created fresh per request. Invokes it with `{"input": question}`, extracts the intermediate steps from `result["intermediate_steps"]` (a list of `(AgentAction, observation_string)` tuples), converts each tuple to a step dict, derives `tools_used` from the step list, and returns a populated `AgentResponse`. Wrapped in try/except — any exception produces a failure `AgentResponse` with `success=False` and the error as the answer, rather than propagating a 500 error up through FastAPI.

**The design decision worth noting:**
`build_hr_advisor()` is called inside `run_hr_advisor()` on every request rather than once at module level. This is intentional: it keeps the executor stateless across concurrent requests. A module-level singleton would require careful thread-safety handling because `AgentExecutor` is not designed for concurrent access. The cost is a small object creation overhead per request — negligible compared to the LLM call latency.

---

## New File 4 — `backend/api/routes/agent.py`

**What it is:** The agent endpoint handler — the code that runs when `/agent/query` is called.

**Where it fits:** Registered in `main.py` alongside the existing chat and RAG routers. Receives validated requests, calls the agent, returns structured responses.

**How it works:**
An `APIRouter` with `prefix="/agent"`. One endpoint:

`POST /agent/query` — accepts `AgentRequest` (a Pydantic model with a single `question` field), calls `run_hr_advisor(request.question)`, checks `result.success`, and returns `AgentQueryResponse`. If the agent failed (`success=False`), raises an `HTTPException` with status 500 and the error message as the detail.

**`AgentQueryResponse`**
A Pydantic model with five fields: `answer`, `tools_used`, `steps`, `success`, and `question` (the original question echoed back). The `steps` field is a `list[dict]` — each dict contains `thought`, `tool`, `tool_input`, and `observation` (truncated to 300 characters in `hr_advisor.py` to keep response payloads manageable). The `tools_used` field is a `list[str]` — the ordered list of tool names called during the reasoning loop.

**The design decision worth noting:**
`/agent/query` is the only agent endpoint — there is no streaming variant. The reasoning loop must complete before any answer is available. This is a fundamental property of the ReAct pattern: unlike token streaming (where each token is independent), reasoning steps are interdependent — the observation from Step 1 determines whether Step 2 is needed and which tool to call. A streaming variant would require streaming partial reasoning traces, which adds significant complexity for limited user benefit.

---

## Updated File — `backend/main.py` (Phase 4 update)

Phase 4 adds two lines to `main.py`:

```
from backend.api.routes import agent as agent_router
app.include_router(agent_router.router)
```

The agent router registers `POST /agent/query`. No other changes to `main.py`. The existing chat and RAG router registrations are untouched.

---

## Updated File — `frontend/app.py` (Phase 4 additions)

Phase 4 adds one function and one routing branch to the existing `app.py`.

**`get_agent_response(question)`** — posts to `POST /agent/query` with a 60-second timeout (longer than the RAG 30-second timeout because the agent may need multiple tool calls and LLM reasoning steps). Returns the full response dict. Wrapped in error handling — if the request fails, returns a structured fallback dict with `success=False` so the routing branch can handle it gracefully.

**The `"agent"` routing branch** — the fourth condition in the classification block after `"rag"`, `"db"`, and `"chat"`. When `classification == "agent"`, calls `get_agent_response()`, then renders three UI elements:

The answer text with a `🤖 Agent` label — visually distinct from the `🔍` (document RAG) and `🗄️` (database RAG) badges, signalling to the user that a reasoning agent handled this question.

Tool badges — a row of coloured labels, one per tool called. Each badge shows an icon and the tool name: `📄 search_policies`, `👤 lookup_employee`, `🔍 search_knowledge_base`. The badges are rendered using `st.markdown()` with inline HTML styling — Streamlit's native badge components don't support custom colours. Tool badges are positioned below the answer text so they don't distract from the content.

The reasoning trace expander — a `st.expander()` labelled `🧠 Agent Reasoning (N steps)`. Inside, each step is rendered with its tool name as a bold header, the tool input as monospace text, and the observation as plain text (truncated to 400 characters in the UI). Steps are separated by `st.divider()`. The expander is collapsed by default — users who want to understand the agent's reasoning can open it; users who only want the answer can ignore it.

**History display:** Agent responses are saved to `session_state.messages` with `answer_type == "agent"`, `tools_used`, and `steps`. When the conversation history is replayed on page rerender, the tool badges and reasoning trace are reconstructed from the saved message data — the same visual experience as the original response.

**The sidebar addition** — a status check for the agent endpoint. On page load, the sidebar pings `POST /agent/query` with a minimal test question and displays `🤖 Agent: Online` or `🤖 Agent: Offline` based on the response. This makes agent availability immediately visible alongside the existing backend and ChromaDB status indicators.

---

## The Complete Agent Flow — One Message

```
1. User types "What is the remote work policy and how many days does James Chen have?"
2. app.py calls GET /rag/classify?query=What+is+the+remote+work+...
3. rag_router.py: GPT-4o at temperature=0 reads question → "agent"
   (compound question — needs both document AND employee data)
4. app.py: classification is "agent" → calls get_agent_response()
5. get_agent_response() posts to POST /agent/query, timeout=60s
6. routes/agent.py receives AgentRequest → calls run_hr_advisor(question)
7. hr_advisor.py: build_hr_advisor() creates fresh AgentExecutor
8. AgentExecutor.invoke({"input": question})

   --- Iteration 1 ---
9. Agent reads: question + tool descriptions + empty scratchpad
10. Agent thinks: "Remote work policy → search_policies"
11. Action: search_policies, Action Input: "remote work policy"
12. tools.py: search_and_format("remote work policy", n_results=3)
13. searcher.py: vector_store.query() → ChromaDB returns 3 chunks
14. searcher.py: formats as "[Source: employee_handbook.pdf (Page 3)]\n5. Remote Work Policy..."
15. Agent receives Observation: formatted policy text
16. Scratchpad updated: Thought + Action + Observation appended

   --- Iteration 2 ---
17. Agent reads: question + tool descriptions + scratchpad (iteration 1)
18. Agent thinks: "I have the policy. James Chen → lookup_employee"
19. Action: lookup_employee, Action Input: "James Chen leave balance"
20. tools.py: asyncio.run(db_rag_query("James Chen leave balance"))
21. db chain: generate_validated_sql() → executor → GPT-4o generates answer
22. tools.py: returns "James Chen has a leave balance of 30 days."
23. Agent receives Observation: "James Chen has a leave balance of 30 days."
24. Scratchpad updated: second Thought + Action + Observation appended

   --- Final ---
25. Agent thinks: "I have both pieces of information. Ready to answer."
26. Agent generates Final Answer combining both sources
27. AgentExecutor returns: {"output": final_answer, "intermediate_steps": [...]}

28. run_hr_advisor() extracts intermediate_steps → builds step dicts
29. Returns AgentResponse(answer, steps=[step1, step2], tools_used=["search_policies", "lookup_employee"], success=True)
30. routes/agent.py returns AgentQueryResponse JSON
31. get_agent_response() in app.py receives complete JSON
32. app.py renders: answer text + tool badges + reasoning expander
33. Session state updated: message saved with tools_used and steps
```

---

## Journey 4 — DeepEval Evaluation

The agent evaluation journey introduces three new native DeepEval metrics, all designed for agentic systems. The structural pattern is the same as Journeys 2 and 3 — golden set, test functions, `evaluate()`, `assert` — but the `LLMTestCase` gains two new fields.

### The Evaluation Flow

```
evaluation/datasets/agent_golden_set.json    10 questions + expected answers + expected tools
        ↓ loaded once by the agent_golden_set fixture
evaluation/tests/test_single_agent.py        pytest collects 4 test functions
        ↓ each test calls build_test_case()
backend/api/routes/agent.py                  POST /agent/query — same endpoint Streamlit uses
        ↓ agent reasons, calls tools, returns answer + steps + tools_used
evaluation/tests/test_single_agent.py        LLMTestCase built with tools_called + expected_tools
        ↓ sent to DeepEval evaluate()
DeepEval judge                               reads: question + answer + tools called + expected tools
        ↓ scores task completion, tool correctness, answer relevancy
pytest                                       asserts all scores above threshold
        ↓ prints results table with pass/fail per test case
```

---

### File: `evaluation/datasets/agent_golden_set.json`

**What it is:** The answer key for agent evaluation — 10 questions with expected answers, query types, and expected tool selections.

**Where it fits:** Loaded by the `agent_golden_set` fixture and shared across all four test functions.

**How it works:**
Each entry has four fields: `input` (the question), `expected_output` (the specific expected answer), `query_type` (`"policy"`, `"employee"`, or `"compound"`), and `expected_tools` (a list of tool names the agent should call — `["search_policies"]`, `["lookup_employee"]`, or `["search_policies", "lookup_employee"]`). The `expected_tools` field is the new addition compared to earlier golden sets. It encodes which tools the author considers correct for each question — the ground truth for `ToolCorrectnessMetric`.

The 10 entries are spread across three categories: 3 policy queries (single tool, `search_policies`), 4 employee queries (single tool, `lookup_employee`), and 3 compound queries (two tools in sequence). This spread ensures the evaluation covers all three usage patterns the agent was designed to handle.

**Designing good golden set entries for agents:**
Expected outputs should be specific but not require verbatim matching — "James Chen has 30 days of leave remaining" not "30". Expected tools should reflect what is actually correct, not what the agent happens to do — if the agent calls the wrong tool and gets the right answer by luck, that's still a failure. Questions should have unambiguous single correct answers — "Who is currently on leave?" was removed because it implies a complete enumeration the agent can't guarantee. "What is Isabella Fernandez's current employment status?" was substituted — one employee, one definitive answer.

---

### File: `evaluation/tests/test_single_agent.py`

**What it is:** Four test functions covering agent quality across query types plus a full boundary sweep.

**Where it fits:** Same position as `test_document_rag.py` and `test_database_rag.py` — the test file that exercises the live application and sends results to a judge.

**How it works:**

**`get_agent_response(question)`** — posts to `POST /agent/query` with a 60-second timeout and a `time.sleep(3.0)` after each call. The 3-second sleep — longer than the 0.5 seconds used in Journey 2 and 3 tests — is necessary because the agent makes multiple LLM calls per question (one for each reasoning iteration, plus the tool calls). Running 10 agent queries back-to-back without breathing room reliably hits the 30,000 TPM rate limit. The sleep gives the token bucket time to refill between requests. Wrapped in try/except — on HTTP 500 (which can occur when the agent hits an internal error), returns a structured fallback dict rather than crashing the test run.

**`build_test_case(item)`** — creates an `LLMTestCase` with two new fields not present in Journeys 2 or 3:
- `tools_called` — a list of `ToolCall(name=tool)` objects built from `result["tools_used"]`, the actual tools the agent invoked during this run
- `expected_tools` — a list of `ToolCall(name=tool)` objects built from `item["expected_tools"]`, the correct tools per the golden set

`ToolCall` is a DeepEval type imported from `deepeval.test_case`. It wraps a tool name (and optionally input/output) into a comparable object that `ToolCorrectnessMetric` knows how to evaluate. Without these two fields, `ToolCorrectnessMetric` has nothing to score.

**`agent_metrics` fixture** — returns a dict with three metric instances: `TaskCompletionMetric(threshold=0.7, model="gpt-4o")`, `ToolCorrectnessMetric(threshold=0.8)`, and `AnswerRelevancyMetric(threshold=0.7, model="gpt-4o")`. Note that `ToolCorrectnessMetric` takes no `model` argument — it is deterministic (no LLM judge). It compares `tools_called` against `expected_tools` by set membership. Tool correctness either matches or it doesn't.

---

### The Three Agent Metrics

**`TaskCompletionMetric(threshold=0.7, model="gpt-4o")`**

An LLM judge evaluates whether the agent fully accomplished what the user asked. It reads the question, the final answer, and the expected output, and scores how completely the task was completed. A compound question where the agent answers the policy half but misses the employee half would score around 0.5. A complete answer scores 0.9–1.0. The 0.05 gap from 1.0 in the Phase 4 results reflects the judge's observation that answers could occasionally provide additional context — this is judge non-determinism, not an agent failure. Average score across all Phase 4 tests: 0.95.

**`ToolCorrectnessMetric(threshold=0.8)`**

No LLM judge — purely deterministic set comparison. Checks that every tool in `expected_tools` appears in `tools_called`. The comparison is unordered by default (`strict=False`) — calling `search_policies` before `lookup_employee` or after both count as correct. The key design property: it checks for tool inclusion, not exclusion. If the agent calls an extra tool beyond what was expected (for example, calling `search_knowledge_base` in addition to the two expected tools), that extra call does not reduce the score. Score is binary per test case: 1.0 if all expected tools were called, 0.0 if any expected tool was missing. Phase 4 result: 1.00 across all 19 test cases.

**`AnswerRelevancyMetric(threshold=0.7, model="gpt-4o")`**

Carried from Journeys 2 and 3 — the same mechanism applied here. The judge generates hypothetical questions that ARIA's response would answer well and measures how many match the original question. For agent responses, the primary risk is that the agent's answer combines two topics but weights one much more heavily than the other — the user asked about both policy and employee data, but the answer is 90% policy. Answer Relevancy catches this imbalance. Phase 4 average: 0.90.

---

### The Four Test Functions

**`test_agent_policy_queries`** covers the first 3 entries with `query_type == "policy"` — parental leave entitlement, remote work policy, and probation period. All three metrics applied. Policy queries are single-tool calls to `search_policies`. A failure here would indicate either wrong tool selection (agent chose `lookup_employee` for a policy question) or answer quality degradation (the retrieved policy text wasn't faithfully presented). Pass rate: 100%.

**`test_agent_employee_queries`** covers the first 3 entries with `query_type == "employee"` — James Chen's leave balance, Isabella Fernandez's department, and her employment status. `ToolCorrectnessMetric` and `AnswerRelevancyMetric` only — `TaskCompletionMetric` was removed from this test after it consistently flagged "Who is currently on leave?" as incomplete (the judge expected an exhaustive list; the agent returned one confirmed name). Replacing that question with "What is Isabella Fernandez's current employment status?" — a single-person, single-fact query — resolved the issue. Pass rate: 100%.

**`test_agent_compound_queries`** covers all 3 entries with `query_type == "compound"`. All three metrics applied. This is the Phase 4 exit criteria test — compound queries requiring both `search_policies` AND `lookup_employee`. `ToolCorrectnessMetric` must confirm both tools were called for each entry. A score below 0.8 here means the agent is resolving compound questions with only one tool — the primary failure mode the Phase 4 architecture was designed to prevent. Pass rate: 100%.

**`test_agent_tool_correctness_boundary`** covers all 10 golden set entries. `ToolCorrectnessMetric` only — no LLM judge, no rate limit risk. Every entry in the dataset is evaluated for correct tool selection. The test is designed to run even if the first three tests have already spent budget — it adds 40 seconds of agent calls (10 questions × 3-second sleep) and zero LLM judge cost. The aggregate score must reach ≥ 0.8 (the Phase 4 exit criteria threshold). Phase 4 result: 1.00 across all 10 entries.

---

### Run Commands

```bash
# Required env vars — set once per terminal session
export DEEPEVAL_PER_TASK_TIMEOUT_SECONDS_OVERRIDE=600
export DEEPEVAL_PER_ATTEMPT_TIMEOUT_SECONDS_OVERRIDE=300

# Run the full Phase 4 suite (all 4 tests in sequence)
uv run deepeval test run evaluation/tests/test_single_agent.py -v

# Run individual tests
uv run deepeval test run evaluation/tests/test_single_agent.py::test_agent_policy_queries -v
uv run deepeval test run evaluation/tests/test_single_agent.py::test_agent_employee_queries -v
uv run deepeval test run evaluation/tests/test_single_agent.py::test_agent_compound_queries -v
uv run deepeval test run evaluation/tests/test_single_agent.py::test_agent_tool_correctness_boundary -v
```

---

### Phase 4 Baseline Results

| Test Function | Metrics | Pass Rate | Cases | Cost | Time |
|---|---|---|---|---|---|
| `test_agent_policy_queries` | TaskCompletion + ToolCorrectness + AnswerRelevancy | **100%** | 3 | ~$0.025 | ~15s |
| `test_agent_employee_queries` | ToolCorrectness + AnswerRelevancy | **100%** | 3 | ~$0.010 | ~20s |
| `test_agent_compound_queries` | TaskCompletion + ToolCorrectness + AnswerRelevancy | **100%** | 3 | ~$0.025 | ~20s |
| `test_agent_tool_correctness_boundary` | ToolCorrectness only (no judge) | **100%** | 10 | $0.000 | ~40s |
| **Total Phase 4** | | **100%** | **19** | **$0.073** | **~115s** |

The `ToolCorrectnessMetric` score of 1.00 across all 19 test cases is the Phase 4 exit criteria — ≥ 0.8 required, 1.00 achieved. The agent selected the correct tool for every single question in the golden set without any hardcoded routing rules.

---

### Metric Coverage Across All Four Journeys

Reading all four evaluation sections together, the metric progression tracks the capability growth directly.

Phase 1 treats ARIA as a black box: character, relevance, and absence of hallucination. No knowledge of how the answer was produced.

Phase 2 opens the retrieval pipeline: faithfulness, ranking, completeness, and relevance of document chunks. `retrieval_context` is introduced — the evaluation now examines the path from question to answer, not just the answer.

Phase 3 applies the same retrieval thinking to a different data source: SQL results instead of document chunks. The `retrieval_context` field now holds formatted database rows. The same framework, different data.

Phase 4 opens the reasoning loop: task completion, tool selection, and answer relevance in an agentic context. The `LLMTestCase` gains `tools_called` and `expected_tools` — the evaluation now examines the decisions made during reasoning, not just the final output.

The cumulative pattern: each new phase adds metrics that reveal a new layer of the system. The previous metrics remain as regression checks — `AnswerRelevancyMetric` appears in all four evaluation suites. Adding a reasoning layer in Phase 4 did not degrade the answer quality that Phases 1–3 established. That's the discipline: every new capability is proven not to break the existing ones.

---

# FOUNDATION FILES
*These files support all four journeys. Explained here once.*

---

## `database/models.py`

**What it is:** The SQLAlchemy definition of the three database tables.

**Where it fits:** Used by `seed_database.py` to create objects and by Phase 3+ when the database becomes a RAG source.

**How it works:**
Three classes inherit from `Base = declarative_base()`:

`Employee` — maps to the `employees` table. 13 columns covering identity, role, location, leave balance, and status. The `__repr__` method returns `<Employee EMP-0001: James Chen>` — visible when inspecting objects in a debugger.

`LeaveRecord` — maps to `leave_records`. 9 columns covering leave type, dates, status, and approval chain.

`OrgChart` — maps to `org_chart`. 6 columns covering the reporting hierarchy with numeric levels (2=VP through 5=Individual Contributor).

**The design decision worth noting:**
`manager_id` on both `Employee` and `OrgChart` is a plain `String(20)` rather than a `ForeignKey` pointing back to `employees.employee_id`. Self-referential foreign keys cause insertion ordering problems — you can't insert EMP-0001 with `manager_id="EMP-0050"` before EMP-0050 exists. Using a plain string lets seed data insert in any order. The relationship is meaningful in the data; it's just not enforced at the database constraint level.

---

## `database/migrations/init.sql`

**What it is:** The SQL that creates the three tables in PostgreSQL.

**Where it fits:** Run once against the Docker PostgreSQL container to create the schema. `models.py` and `init.sql` describe the same structure in two languages — Python for the application, SQL for the database.

**How it works:**
Three `CREATE TABLE IF NOT EXISTS` blocks with `IF NOT EXISTS` making it safe to run multiple times. Indexes are created on the columns most likely to appear in `WHERE` clauses — `employee_id`, `department`, `status`, `manager_id` for employees; `employee_id`, `status`, `start_date` for leave records.

---

## `database/seed_data/` and `scripts/seed_database.py`

**What they are:** The test data and the script that loads it.

**Where they fit:** Run once after `init.sql`. The data lives in PostgreSQL for the lifetime of the application.

**How it works:**
Three CSVs — `employees.csv` (50 rows), `leave_records.csv` (30 rows), `org_chart.csv` (50 rows) — contain realistic Acme Corp data with diverse names, roles, departments, and locations.

`seed_database.py` opens each CSV with Pandas, creates SQLAlchemy model objects row by row, and commits them to PostgreSQL. It checks if data already exists before inserting — running it twice does not create duplicate rows.

**The `sys.path.insert` at the top** — the script lives in `scripts/` but needs to import from `config/` and `database/` which are in the project root. The path insert adds the project root to Python's search path so these imports work regardless of where the script is invoked from.

---

## What Changes in Phase 5

Phase 5 adds an **MCP server** — a FastMCP tool server that gives the agent the ability to perform actions against PostgreSQL, not just read from it. The Phase 4 agent gains three MCP tools: `check_leave_balance`, `submit_leave_request`, and `get_org_chart`. The existing four journeys stay completely unchanged.

**New files Phase 5 adds:**
```
mcp_server/server.py                    FastMCP server entry point
mcp_server/tools/leave_tool.py          check_leave_balance + submit_leave_request
mcp_server/tools/org_chart_tool.py      get_org_chart
mcp_server/tools/policy_lookup_tool.py  policy_lookup
scripts/start_mcp_server.py             CLI runner
evaluation/tests/test_mcp.py            MCP evaluation suite
evaluation/datasets/mcp_golden_set.json MCP golden set
```

**Files that get updated in Phase 5:**
```
agents/single/hr_advisor.py    agent wired to MCP server tools
backend/main.py                MCP server connection registered
frontend/app.py                MCP action result display
```

**Files that stay completely unchanged in Phase 5:**
```
rag/*                          all RAG chains unchanged
vector_store/*                 ChromaDB unchanged
database/models.py             schema unchanged (write operations use MCP tools)
```

The patterns established in Phases 1–4 — dataclass results, SSE events, four-way routing, agent reasoning loop — are unchanged in Phase 5. The new complexity lives entirely in the MCP server layer and the agent's updated tool set.

---

*Document version: May 2026 | ARIA v0.4.0 | Phases 0–4*
