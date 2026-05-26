# ARIA Codebase Guide — Phases 0–2
## Understanding the Code in Execution Order

> **How to use this guide:** Open your code editor on one side, this document on the other.
> Follow the flow of a real user message through every file it touches.
> Each section tells you what a file does, where it fits, and why it was designed that way —
> not a line-by-line walkthrough, but enough to make the code immediately readable.

---

## The Two Journeys

Everything in this codebase serves one of two request flows:

**Journey 1 — CHAT**
> *"Hello ARIA, what can you help me with?"*
> A general question routed to GPT-4o with conversation memory.

**Journey 2 — DOCUMENT RAG**
> *"What is the parental leave policy?"*
> A policy question retrieved from HR documents, answered with citations.

Both journeys start at the same place — the Streamlit UI — and end at the same place — a streamed response in the browser. What happens in between is different.

Read Journey 1 first. Journey 2 builds on everything Journey 1 establishes.

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

`classify_query(question)` — sends the question to GPT-4o with a classification prompt and `temperature=0`. Zero temperature means deterministic — the same question always gets the same classification. Returns one of: `"rag"` (document question), `"chat"` (general conversation), or in Phase 3+ `"db"` (employee data question).

The classification prompt lists specific criteria for each category. "What is our parental leave policy?" → `"rag"`. "Hello, how are you?" → `"chat"`. "How many leave days does James Chen have?" → `"db"` in Phase 3.

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

# FOUNDATION FILES
*These files support both journeys. Explained here once.*

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

**If you want to understand the RAG path, open these files in this order:**
```
scripts/create_documents.py         (understand the source data)
rag/document_rag/ingestion.py       (PDF → text)
rag/document_rag/chunker.py         (text → chunks)
vector_store/store.py               (ChromaDB operations)
vector_store/indexer.py             (orchestrates ingestion)
rag/document_rag/retriever.py       (question → chunks)
rag/document_rag/chain.py           (chunks + question → answer)
backend/schemas/rag.py              (request/response shapes)
backend/chains/rag_router.py        (classify: rag vs chat)
backend/api/routes/rag.py           (endpoints)
frontend/app.py                     (UI — same file as chat)
```

**If you want to understand the data foundation:**
```
database/models.py
database/migrations/init.sql
database/seed_data/employees.csv    (open in any spreadsheet or text editor)
scripts/seed_database.py
```

---

## What Changes in Phase 3

Phase 3 adds a third journey — **Database RAG** — for questions about specific employees, leave balances, and org chart data. The architecture extends cleanly:

**New files Phase 3 adds:**
```
rag/database_rag/schema.py      (teaches GPT-4o the PostgreSQL schema)
rag/database_rag/nl_to_sql.py   (question → SQL query)
rag/database_rag/executor.py    (SQL → structured results)
rag/database_rag/chain.py       (results → natural language answer)
```

**Files that get updated in Phase 3:**
```
backend/chains/rag_router.py    (adds "db" as a third classification)
backend/api/routes/rag.py       (adds /rag/db/query endpoint)
frontend/app.py                 (adds stream_db() generator)
```

**Files that stay completely unchanged in Phase 3:**
```
config/settings.py              (no new config needed)
backend/schemas/chat.py         (chat contract unchanged)
backend/chains/chat_chain.py    (chat chain unchanged)
rag/document_rag/*              (document RAG unchanged)
vector_store/*                  (ChromaDB unchanged)
```

The patterns established in Phases 1 and 2 — streaming generators, SSE events, dataclass results, chain composition — repeat identically in Phase 3. Reading this document once gives you the mental model to read Phase 3 code immediately.

---

*Document version: May 2026 | ARIA v0.2.0 | Phases 0–2*
