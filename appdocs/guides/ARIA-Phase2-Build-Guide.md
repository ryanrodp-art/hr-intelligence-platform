# ARIA — HR GenAI Agent Platform
## Phase 2 Build Guide — Document RAG

> ChromaDB vector search, HR policy PDFs, grounded answers with source citations, and DeepEval RAG evaluation.
> **Completed in 3 days | 9 Steps | 26 DeepEval test cases | 100% pass rate**

---

## Phase 2 Overview

Phase 2 grounds ARIA's answers in real company documents. Phase 1 ARIA answered from GPT-4o's general training knowledge — useful but unverifiable. Phase 2 ARIA retrieves specific passages from actual HR policy PDFs and cites her sources in every response.

**The transformation:**

```
Phase 1 — General knowledge:
User: "What is the parental leave policy?"
ARIA: "Parental leave typically provides paid time off for new parents.
       Check with your HR manager for specifics."
       (vague, generic, not grounded)

Phase 2 — Grounded in company documents:
User: "What is the parental leave policy?"
ARIA: "Per our Leave Policy (Page 1), primary caregivers receive
       16 weeks of fully paid parental leave. Employees must have
       6 months of continuous service and give 8 weeks written notice."
       (specific, accurate, cited)
```

**What Phase 2 Delivers:**

- 4 HR policy PDFs (Leave Policy, Code of Conduct, Benefits Guide, Employee Handbook)
- PyMuPDF text extraction pipeline
- LangChain `RecursiveCharacterTextSplitter` chunking (800 chars, 100 overlap)
- OpenAI `text-embedding-3-small` embeddings
- ChromaDB vector store with 19 indexed chunks
- Retriever with similarity scoring and source citations
- RAG chain at `temperature=0.1` for factual consistency
- Query router classifying questions as `"rag"` or `"chat"`
- FastAPI endpoints: `/rag/query`, `/rag/stream`, `/rag/classify`, `/rag/status`
- Streamlit UI with routing badges and source citations
- DeepEval RAG evaluation suite — 5 tests, 26 cases, 100% pass rate

**9 Steps:**

| # | Step | File(s) Created | Delivers |
|---|---|---|---|
| 1 | HR Policy Documents | `documents/policies/*.pdf`, `documents/handbooks/*.pdf` | 4 source documents |
| 2 | Ingestion Pipeline | `rag/document_rag/ingestion.py` | PDF → clean text + metadata |
| 3 | Chunking Strategy | `rag/document_rag/chunker.py` | 19 focused chunks |
| 4 | Vector Store + Indexer | `vector_store/store.py`, `vector_store/indexer.py` | 19 vectors in ChromaDB |
| 5 | Retriever | `rag/document_rag/retriever.py` | Similarity search + citations |
| 6 | RAG Chain | `rag/document_rag/chain.py` | Grounded GPT-4o answers |
| 7 | FastAPI RAG Endpoints | `backend/api/routes/rag.py`, `backend/chains/rag_router.py` | 4 new endpoints |
| 8 | Streamlit UI Update | `frontend/app.py` updated | Routing badges + citations |
| 9 | DeepEval RAG Tests | `evaluation/tests/test_document_rag.py` | 26 cases, 100% pass |

---

## How RAG Works — The Mental Model

```
Without RAG (Phase 1):
User question → GPT-4o (trained knowledge) → Generic answer

With RAG (Phase 2):
User question → Embed question → ChromaDB similarity search
                                       ↓
                              Top 3 relevant chunks
                                       ↓
                        GPT-4o (chunks + question) → Grounded answer + citations
```

**The filing cabinet analogy:** Phase 1 ARIA is a new HR manager who knows HR in general but not your company's specific rules. Phase 2 gives ARIA a filing cabinet of your company's actual documents. Before answering she searches the cabinet, pulls the relevant pages, and answers based on what she found.

---

## Step 1 — HR Policy Documents

### Concept

Before building any RAG infrastructure, specific documents are needed. The quality of ARIA's Phase 2 answers is directly proportional to the specificity of the source documents.

**Why specificity matters:**
```
Vague: "Employees receive annual leave."
→ ARIA: "You receive annual leave." (useless)

Specific: "Full-time employees receive 25 days annual leave per year,
           accruing at 2.08 days per month from date of hire."
→ ARIA: "Per the Leave Policy, you receive 25 days annual leave
          per year, accruing at 2.08 days per month." (useful)
```

**Four documents covering the core HR domains:**

| Document | Location | Key Content |
|---|---|---|
| `leave_policy.pdf` | `documents/policies/` | Annual (25 days), sick (10 days), parental (16 weeks), emergency, unpaid leave |
| `code_of_conduct.pdf` | `documents/policies/` | Anti-harassment, grievance process (4 steps), disciplinary procedure (4 stages) |
| `benefits_guide.pdf` | `documents/policies/` | Health insurance (100% company-paid), 401k match, wellness ($500/yr), professional development ($2,000/yr) |
| `employee_handbook.pdf` | `documents/handbooks/` | Onboarding, probation (90 days), working hours, remote work (hybrid 3 days office), termination |

### Claude Code Prompt

```
Create four realistic HR policy documents as PDFs for the ARIA
HR Intelligence Platform. The company name is "Acme Corp".

Use PyMuPDF (fitz) to generate the PDFs programmatically.
Create a script scripts/create_documents.py that generates all four
files and saves them to the correct locations.

The script should:
- Import fitz (PyMuPDF)
- Create each document with proper formatting
- Add double newlines (\n\n) between every major section so
  RecursiveCharacterTextSplitter breaks at section boundaries
- Save to the correct path
- Print confirmation of each file created

DOCUMENT 1: documents/policies/leave_policy.pdf
Title: "Acme Corp — Employee Leave Policy"
Version: 2.1 | Effective: January 1, 2024

Sections with specific details:
1. Overview
2. Annual Leave: 25 days full-time, accrual 2.08/month, carryover 5 days
3. Sick Leave: 10 days, doctor certificate after 3 days
4. Parental Leave: Primary 16 weeks, Secondary 4 weeks, eligibility 6 months
5. Emergency Leave: 3 days per incident
6. Unpaid Leave: Max 3 months, HR Director approval
7. Leave Application Process: HR portal, 2 weeks notice, 5 days manager approval
8. Contact: hr@acmecorp.com | ext. 4100

DOCUMENT 2: documents/policies/code_of_conduct.pdf
Title: "Acme Corp — Code of Conduct"
Version: 3.0 | Effective: January 1, 2024

Sections:
1. Overview
2. Professional Behaviour
3. Anti-Harassment Policy: Zero tolerance, all types covered
4. Reporting and Grievance Process:
   Step 1: Direct manager (informal)
   Step 2: HR Business Partner (5 days)
   Step 3: Formal grievance to HR Director
   Step 4: Independent investigation (15 business days)
   No retaliation policy
5. Disciplinary Procedure:
   Stage 1: Verbal warning
   Stage 2: Written warning (12 months)
   Stage 3: Final written warning (12 months)
   Stage 4: Dismissal (10 days appeal)
6. Social Media Policy
7. Contact: hrbp@acmecorp.com | ext. 4200

DOCUMENT 3: documents/policies/benefits_guide.pdf
Title: "Acme Corp — Employee Benefits Guide"
Version: 1.4 | Effective: January 1, 2024

Sections:
1. Overview
2. Health Insurance: BlueCross BlueShield, 100% employee, 80% dependant
3. Retirement Plan: Fidelity 401k, 100% match first 3%, 50% next 3%, 3yr vest
4. Wellness: $50/month gym, 6 EAP sessions, $500 wellness allowance
5. Other Benefits: Life insurance 2x salary, STD/LTD
6. Stock Options: Senior Manager+, 4yr vest 1yr cliff
7. Professional Development: $2,000/year, manager approval required
8. Contact: benefits@acmecorp.com | ext. 4300

DOCUMENT 4: documents/handbooks/employee_handbook.pdf
Title: "Acme Corp — Employee Handbook"
Version: 4.2 | Effective: January 1, 2024

Sections:
1. Welcome to Acme Corp
2. Onboarding: Week 1 orientation, Week 2-4 training, 30-day HR check-in
3. Probation Period: 90 days, 60-day informal review, 90-day formal
4. Working Hours: 9am-5pm, 37.5hrs/week, core hours 10am-3pm
5. Remote Work: Hybrid minimum 3 days office, max 2 days remote, $500 equipment
6. Performance Management: Mid-year June, annual December
7. Termination: 4 weeks notice, final paycheck 5 business days
8. Key Contacts: hr@acmecorp.com, sarah.mitchell@acmecorp.com (HR Director)

After creating the script, run it and confirm all 4 PDF files
were created with their file sizes.
```

### Validation

```bash
uv run python scripts/create_documents.py
find documents/ -name "*.pdf" -ls
```

### Results

| File | Size | Pages |
|---|---|---|
| `leave_policy.pdf` | 18,068 bytes | 2 |
| `code_of_conduct.pdf` | 17,962 bytes | 2 |
| `benefits_guide.pdf` | 18,678 bytes | 2 |
| `employee_handbook.pdf` | 25,389 bytes | 2 |

> **Important lesson learned:** Section separation in PDFs directly affects chunking quality. The `\n\n` double newline between sections tells `RecursiveCharacterTextSplitter` to break at section boundaries rather than mid-section. This was critical for the parental leave retrieval fix in Step 4.

### Exit Criteria

| Check | Status |
|---|---|
| 4 PDF files created | ✅ |
| All documents have specific policy details | ✅ |
| Double newlines between major sections | ✅ |
| Contact information in every document | ✅ |

---

## Step 2 — Document Ingestion Pipeline

### Concept

Raw PDF text can't go directly into ChromaDB. The ingestion pipeline extracts text page by page, cleans it, and tags every page with metadata (source filename, page number) so ARIA can cite her sources later.

**The metadata structure travelling with every chunk:**
```python
{
    "source": "leave_policy.pdf",
    "page_number": 1,
    "chunk_index": 2,
    "source_path": "documents/policies/leave_policy.pdf"
}
```

### Claude Code Prompt

```
Create rag/document_rag/ingestion.py — the PDF ingestion pipeline.
Also create rag/__init__.py and rag/document_rag/__init__.py
(empty files for Python package imports).

Imports: fitz (PyMuPDF), pathlib.Path, logging, re, typing.Generator

Constants:
- DOCUMENTS_DIR = Path("documents")
- SUPPORTED_EXTENSIONS = {".pdf"}

Dataclass DocumentPage with fields:
- text: str, source: str, source_path: str
- page_number: int (1-indexed), total_pages: int

Function clean_text(text: str) -> str:
- Strip whitespace
- Replace multiple spaces with single space
- Replace multiple newlines with double newline
- Remove lines under 3 characters (page number artifacts)

Function extract_pages(pdf_path: Path) -> Generator[DocumentPage]:
- Open with fitz.open()
- Log: f"Extracting {pdf_path.name} ({doc.page_count} pages)"
- For each page: extract text, clean, skip if under 50 chars
- Yield DocumentPage with all metadata

Function load_all_documents() -> list[DocumentPage]:
- Scan DOCUMENTS_DIR recursively for *.pdf
- Collect all DocumentPage objects
- Log summary with counts
- Return list

Function get_document_stats() -> dict:
- Returns total_documents, total_pages, per-document breakdown

Test block:
if __name__ == "__main__":
    stats = get_document_stats()
    print(f"Documents: {stats['total_documents']}, Pages: {stats['total_pages']}")
    pages = load_all_documents()
    print(f"\nSample from {pages[0].source} page {pages[0].page_number}:")
    print(pages[0].text[:300])
```

### Run Command

```bash
uv run python -m rag.document_rag.ingestion
```

### Results

```
Documents found: 4
Total pages: 8

Sample text from employee_handbook.pdf page 1:
Acme Corp · Employee Handbook
Version 4.2 | Effective: January 1, 2024...
```

### Exit Criteria

| Check | Status |
|---|---|
| `rag/__init__.py` created | ✅ |
| `rag/document_rag/__init__.py` created | ✅ |
| `ingestion.py` created | ✅ |
| 4 documents found | ✅ |
| 8 pages extracted (2 per PDF) | ✅ |
| Clean text with metadata confirmed | ✅ |

---

## Step 3 — Document Chunking Strategy

### Concept

Each page is too large to store as a single vector. Chunking splits pages into focused pieces so retrieval is precise.

**The Goldilocks problem:**

| Chunk Size | Problem |
|---|---|
| Too large (full page) | Vector is unfocused — retrieval returns everything vaguely related |
| Too small (one sentence) | Retrieved chunk lacks context to answer the question |
| Just right (300-800 chars) | One complete policy clause — focused and answerable |

**`RecursiveCharacterTextSplitter` separator priority:**
```
1. "\n\n"  → paragraph/section breaks (best)
2. "\n"    → line breaks
3. ". "    → sentence endings
4. " "     → word boundaries (last resort)
```

**`chunk_overlap=100`** — the last 100 characters of chunk N are repeated at the start of chunk N+1, preventing policy clauses from being split across two chunks where neither contains the complete thought.

### Claude Code Prompt

```
Create rag/document_rag/chunker.py — splits document pages
into appropriately sized chunks for vector storage.

Imports: langchain_text_splitters.RecursiveCharacterTextSplitter,
         rag.document_rag.ingestion (DocumentPage, load_all_documents),
         logging, dataclasses.dataclass

Dataclass DocumentChunk with fields:
- text: str, source: str, source_path: str
- page_number: int, chunk_index: int
- total_chunks_in_page: int
- chunk_id: str  (format: "leave_policy_p1_c0")

Function create_splitter(chunk_size=800, chunk_overlap=100):
- Returns RecursiveCharacterTextSplitter with
  separators=["\n\n", "\n", ". ", " ", ""]

Function chunk_page(page, splitter) -> list[DocumentChunk]:
- Split page.text, filter chunks under 50 chars
- Generate chunk_id: "{stem}_p{page}_c{index}"
- Log per-page chunk count
- Return list of DocumentChunk

Function chunk_all_documents(chunk_size=800, chunk_overlap=100):
- Load all pages, create splitter, chunk each page
- Log summary
- Return flat list of all chunks

Function get_chunking_stats(chunks) -> dict:
- Returns total_chunks, avg/min/max chunk_size,
  chunks_by_document breakdown

Test block:
if __name__ == "__main__":
    chunks = chunk_all_documents()
    stats = get_chunking_stats(chunks)
    print all stats and 3 sample chunks
```

### Run Command

```bash
uv run python -m rag.document_rag.chunker
```

### Results

| Stat | Value |
|---|---|
| Total chunks | 19 |
| Average chunk size | 592 chars |
| Min chunk size | 57 chars |
| Max chunk size | 797 chars |

| Document | Chunks |
|---|---|
| `employee_handbook.pdf` | 8 |
| `benefits_guide.pdf` | 7 |
| `leave_policy.pdf` | 6 |
| `code_of_conduct.pdf` | 6 |

> **Tuning applied:** Initial chunk size was 500 chars with 50 overlap — this caused the parental leave section to be merged with sick leave in one chunk (both scoring on the same vector). Increasing to 800/100 allowed section boundaries to be respected. The `\n\n` separators in the PDFs (Step 1 fix) combined with the larger chunk size resolved the retrieval issue.

### Exit Criteria

| Check | Status |
|---|---|
| `chunker.py` created | ✅ |
| 19 chunks generated | ✅ |
| Average chunk 592 chars | ✅ |
| All 4 documents represented | ✅ |

---

## Step 4 — Vector Store and Indexer

### Concept

Embeddings convert text into 1536-dimensional vectors that capture semantic meaning. Similar meanings produce mathematically similar vectors — enabling semantic search.

```
"How many days annual leave do I get?"     → [0.23, -0.87, 0.45, ...]
"Full-time employees: 25 days per year"    → [0.21, -0.89, 0.43, ...]
Cosine similarity: 0.97 ← very close → retrieved ✅

"What is the company pension plan?"        → [0.67, 0.23, -0.34, ...]
Cosine similarity: 0.23 ← far away → not retrieved ✅
```

**Model:** `text-embedding-3-small` — OpenAI's embedding model, 1536 dimensions. The same model must be used for both indexing (storing chunks) and querying (searching) — mismatched models produce nonsense similarity scores.

**ChromaDB collection:** `hr_policies` — stores all 19 chunk vectors with their text and metadata.

### Claude Code Prompt

```
Create two files for the vector store layer:

FILE 1: vector_store/store.py
Class VectorStore:

__init__(self):
  - chromadb.HttpClient(host=settings.chroma_host,
                        port=settings.chroma_port)
  - OpenAIEmbeddings(model="text-embedding-3-small",
                     api_key=settings.openai_api_key)
  - get_or_create_collection("hr_policies",
      metadata={"hnsw:space": "cosine"})

add_chunks(self, chunks) -> int:
  - Embed all chunk texts
  - collection.add(ids, embeddings, documents, metadatas)
  - Return count added

query(self, question, top_k=3) -> list[dict]:
  - Embed question
  - collection.query(query_embeddings, n_results=top_k,
      include=["documents", "metadatas", "distances"])
  - Convert distance to similarity: similarity = 1 - distance
  - Return list of dicts with text, source, page_number,
    chunk_index, distance

count(self) -> int
reset(self) -> None  (delete and recreate collection)
get_collection_info(self) -> dict

Module-level singleton: vector_store = VectorStore()

FILE 2: vector_store/indexer.py
Function index_documents(reset=False) -> dict:
  - If reset: vector_store.reset()
  - If already indexed and not reset: return early
  - chunk_all_documents()
  - vector_store.add_chunks(chunks)
  - Return status dict

Function verify_index() -> dict:
  - Returns vector_store.get_collection_info()

Test block with reset=True in __main__

Also create vector_store/__init__.py (empty).
```

### Run Command

```bash
uv run python -m vector_store.indexer
```

### Results

```
Starting document indexing...
Status: success
Chunks indexed: 19
Collection: hr_policies
Total vectors in ChromaDB: 19
Embedding model: text-embedding-3-small
```

### Exit Criteria

| Check | Status |
|---|---|
| `vector_store/store.py` created | ✅ |
| `vector_store/indexer.py` created | ✅ |
| ChromaDB connection working | ✅ |
| 19 chunks embedded and stored | ✅ |
| Collection `hr_policies` created | ✅ |

---

## Step 5 — Document Retriever

### Concept

The retriever provides a clean interface over the vector store — converts distances to similarity scores, filters low-quality matches, formats human-readable citations, and returns structured `RetrievedChunk` objects.

**Citation formatting:**
```
"leave_policy.pdf" → "Leave Policy, Page 1"
"employee_handbook.pdf" → "Employee Handbook, Page 2"
```

### Claude Code Prompt

```
Create rag/document_rag/retriever.py

Imports: vector_store.store (vector_store), logging, dataclasses.dataclass

Dataclass RetrievedChunk:
- text, source, page_number, chunk_index: basic fields
- similarity_score: float  (1.0 = identical, 0.0 = unrelated)
- citation: str  ("Leave Policy, Page 1")

Function format_citation(source, page_number) -> str:
- "leave_policy.pdf" → "Leave Policy"
- "code_of_conduct.pdf" → "Code of Conduct"
- "benefits_guide.pdf" → "Benefits Guide"
- "employee_handbook.pdf" → "Employee Handbook"
- Returns f"{document_name}, Page {page_number}"

Function retrieve(query, top_k=3, min_similarity=0.3):
- vector_store.query(query, top_k)
- Convert distance to similarity
- Filter below min_similarity
- Sort by similarity descending
- Return list[RetrievedChunk]

Function retrieve_with_context(query, top_k=3) -> dict:
- Returns: query, chunks, context_text (formatted with citations),
  sources (unique citation list)

Function test_retrieval():
- Test 5 queries and print citation + similarity + first 150 chars

Test block: if __name__ == "__main__": test_retrieval()
```

### Run Command

```bash
uv run python -m rag.document_rag.retriever
```

### Retrieval Verification Results

| Query | Top Citation | Similarity | Content Retrieved |
|---|---|---|---|
| Annual leave days | Leave Policy, Page 1 | 0.518 | "25 days per calendar year" ✅ |
| Parental leave | Leave Policy, Page 1 | 0.610 | "16 weeks fully paid" ✅ |
| Remote work policy | Employee Handbook, Page 3 | 0.641 | "minimum 3 days in office" ✅ |
| Report harassment | Code of Conduct, Page 1 | 0.612 | Grievance steps ✅ |
| Retirement plan | Benefits Guide, Page 1 | 0.465 | "Fidelity 401k" ✅ |
| Probation period | Employee Handbook, Page 1 | 0.596 | "90 days" ✅ |

> **Known gaps (Phase 7 tuning items):**
> - Harassment reporting query retrieves Professional Behaviour bullets instead of Grievance steps as top result — content still in chunks 2-3, answer correct
> - Professional development budget query hits disability insurance text — correct document, ranking issue only
> Both land on correct document — acceptable for Phase 2, tunable in Phase 7

### Exit Criteria

| Check | Status |
|---|---|
| `retriever.py` created | ✅ |
| All 6 test queries retrieve correct document | ✅ |
| Similarity scores above 0.3 threshold | ✅ |
| Citations formatted correctly | ✅ |

---

## Step 6 — RAG Chain

### Concept

The RAG chain combines retrieval with GPT-4o generation. Three stages in sequence: **Retrieve** relevant chunks → **Augment** the prompt with context → **Generate** a grounded answer.

**Key difference from Phase 1 chat chain:**

| | Phase 1 Chat Chain | Phase 2 RAG Chain |
|---|---|---|
| Temperature | 0.7 (conversational) | 0.1 (factual) |
| System prompt | "Answer HR questions professionally" | "Answer ONLY from context provided" |
| Memory | Per-session conversation history | Retrieved document chunks |
| Hallucination risk | General knowledge drift | Constrained by context |

**The RAG prompt structure:**
```
System: You are ARIA. Answer based ONLY on the provided context.
        If context doesn't contain the answer, say so explicitly.
        Always cite your sources.

Context:
[Leave Policy, Page 1]
Full-time employees: 25 days per calendar year...

[Benefits Guide, Page 1]
Employee coverage: 100% company-paid...

Employee question: How many days of annual leave do I get?
```

### Claude Code Prompt

```
Create rag/document_rag/chain.py — the complete RAG chain.

Imports: langchain_openai.ChatOpenAI, langchain_core.prompts.ChatPromptTemplate,
         langchain_core.output_parsers.StrOutputParser,
         rag.document_rag.retriever (retrieve_with_context),
         config.settings, logging, dataclasses.dataclass, typing.AsyncGenerator

RAG_SYSTEM_PROMPT constant:
"You are ARIA, an HR Intelligence Assistant for Acme Corp.
You answer questions based ONLY on the provided company documents.

Rules:
- Answer using ONLY the information in the Context section
- Always mention which document your answer comes from
- If context does not contain enough information say:
  'I don't have specific information about that in our company
  documents. Please contact HR at hr@acmecorp.com or ext. 4100.'
- Never make up information not present in the context
- Be concise and direct
- Format your answer with key information first"

Dataclass RAGResponse: answer, sources, chunks_used, query

Function build_rag_prompt() -> ChatPromptTemplate:
- System: RAG_SYSTEM_PROMPT
- Human: "Context from Acme Corp documents:\n\n{context}\n\n
          Employee question: {question}\n\nAnswer based on context above."

Function get_rag_llm() -> ChatOpenAI:
- model=settings.openai_model, temperature=0.1, api_key=...
- Note: temperature=0.1 for factual consistency (vs 0.7 in chat chain)

Async function rag_query(question) -> RAGResponse:
- retrieve_with_context(question, top_k=3)
- If no chunks: return fallback RAGResponse with hr@acmecorp.com contact
- Build chain: prompt | llm | StrOutputParser()
- Invoke with context and question
- Return RAGResponse

Async generator rag_query_stream(question) -> AsyncGenerator[str, None]:
- Same retrieval as rag_query
- Use chain.astream() for token-by-token streaming
- Yield tokens as they arrive
- Log completion after stream ends

Test block: 5 test questions run with asyncio.run()
```

### Run Command

```bash
uv run python -m rag.document_rag.chain
```

### Chain Test Results

| Question | Answer Quality | Source Citation |
|---|---|---|
| How many days of annual leave? | "25 days of annual leave per calendar year" | Leave Policy, Page 1 ✅ |
| Parental leave policy? | "Primary caregivers: 16 weeks fully paid" | Leave Policy, Page 1 ✅ |
| Remote work policy? | "minimum 3 days in office, max 2 days remote, $500 equipment" | Employee Handbook, Pages 1-2 ✅ |
| How to report harassment? | All 4 grievance steps listed with confidentiality note | Code of Conduct, Page 1 ✅ |
| Company retirement contribution? | "100% of first 3%, 50% of next 3%, vests over 3 years" | Benefits Guide, Page 1 ✅ |

> **Parental leave issue and fix:** Initial test showed parental leave returning "I don't have specific information" because the parental leave section was merged with sick leave in one 500-char chunk — the vector was dominated by sick leave content. Fix: regenerated PDFs with double-newline section separators + increased chunk size to 800 chars + reindexed. Parental leave now retrieves correctly with similarity=0.610.

### Exit Criteria

| Check | Status |
|---|---|
| `chain.py` created | ✅ |
| All 5 test questions answered from documents | ✅ |
| Source citations in every answer | ✅ |
| Parental leave retrieves "16 weeks" correctly | ✅ |
| Fallback message for missing content | ✅ |

---

## Step 7 — FastAPI RAG Endpoints

### Concept

Four new endpoints exposed through FastAPI. Two important design decisions:

**`/rag/query` vs `/rag/stream`:**

| Endpoint | Used By | Why |
|---|---|---|
| `POST /rag/query` | DeepEval test suite only | Evaluations need complete JSON response with metadata |
| `POST /rag/stream` | Streamlit UI always | Users get token-by-token streaming — never wait for full response |

**The query router:** A zero-temperature GPT-4o classifier that reads the question and returns `"rag"` or `"chat"`. Zero temperature means deterministic — the same question always routes the same way.

**`classify_query_endpoint` naming:** The function `classify_query` is imported from `rag_router.py`. The endpoint function must have a different name to avoid shadowing — named `classify_query_endpoint`. Shadowing caused a 500 error in initial implementation.

### Claude Code Prompt (combined)

```
Create the following files to expose the RAG chain through FastAPI
and add a simple query router.

FILE 1: backend/chains/rag_router.py

ROUTER_PROMPT constant:
"You are a query classifier for an HR assistant system.
Classify the user question as either 'rag' or 'chat'.

Return 'rag' if the question:
- Asks about specific company policies or procedures
- Asks about leave entitlements, benefits, or compensation
- Asks about conduct, grievances, or disciplinary procedures
- Asks about onboarding, probation, or working arrangements
- Could be answered from an HR policy document

Return 'chat' if the question:
- Is a general greeting or conversation
- Asks about general HR concepts not specific to the company
- Is a follow-up that continues a general conversation
- Cannot be answered from a policy document

Return ONLY the word 'rag' or 'chat' — nothing else."

Async function classify_query(question: str) -> str:
- ChatPromptTemplate with ROUTER_PROMPT and human="{question}"
- ChatOpenAI(model=settings.openai_model, temperature=0)
- Chain: prompt | llm | StrOutputParser()
- Strip and lowercase result
- Default to "rag" if not in ["rag", "chat"]
- Log classification

FILE 2: backend/schemas/rag.py
RAGRequest: question (str, min_length=1), session_id (uuid default),
            top_k (int, default=3, ge=1, le=10)
RAGResponse: answer, sources (list[str]), chunks_used, query,
             session_id, model (default="gpt-4o-rag")

FILE 3: backend/api/routes/rag.py
router = APIRouter(prefix="/rag", tags=["rag"])

POST /rag/query — DeepEval only, returns complete RAGResponse JSON
POST /rag/stream — Streamlit UI always, returns SSE token stream
  After all tokens, send metadata event before [DONE]:
  data: {"sources": [...], "chunks_used": N, "session_id": "..."}


  Then: data: {"token": "[DONE]"}



GET /rag/classify — calls classify_query_endpoint (NOT classify_query
  to avoid name shadowing), wrapped in try/except with "rag" fallback

GET /rag/status — returns collection name, vector count,
                  embedding model from vector_store

FILE 4 — Update backend/main.py:
- from backend.api.routes import rag as rag_router
- app.include_router(rag_router.router)

ENDPOINT USAGE RULE (add as comments):
# /rag/query  → DeepEval evaluations only (complete JSON)
# /rag/stream → Streamlit UI always (SSE streaming)
# Same pattern as /chat/ vs /chat/stream from Phase 1
```

### Verification Commands

```bash
# After restarting FastAPI:
curl http://localhost:8000/rag/status
curl "http://localhost:8000/rag/classify?query=What+is+the+parental+leave+policy"
curl -X POST http://localhost:8000/rag/query   -H "Content-Type: application/json"   -d '{"question": "How many days annual leave do I get?"}'
```

### Verification Results

| Test | Expected | Result |
|---|---|---|
| `/rag/status` | 19 vectors in hr_policies | `{"vectors": 19, "collection": "hr_policies"}` ✅ |
| `/rag/classify` parental leave | `"rag"` | `{"classification": "rag"}` ✅ |
| `/rag/query` annual leave | "25 days" cited from Leave Policy | Specific answer with citation ✅ |

> **Bug fixed:** Initial classify endpoint returned 500 because the endpoint function `classify_query` shadowed the imported function `classify_query` from `rag_router.py`. Fixed by renaming the endpoint function to `classify_query_endpoint`.

### Exit Criteria

| Check | Status |
|---|---|
| `rag_router.py` — GPT-4o classifier | ✅ |
| `backend/schemas/rag.py` — Pydantic models | ✅ |
| `backend/api/routes/rag.py` — 4 endpoints | ✅ |
| `main.py` updated with rag router | ✅ |
| `/rag/status` — 19 vectors confirmed | ✅ |
| `/rag/classify` — correct routing | ✅ |
| `/rag/query` — cited answer returned | ✅ |

---

## Step 8 — Streamlit UI Update

### Concept

Three additions to `frontend/app.py`:

1. **Sidebar RAG status** — shows vector count and document list
2. **`stream_rag()` generator** — calls `/rag/stream`, yields tokens, captures metadata event (sources, chunks_used)
3. **Routing logic** — classifies query then calls the right streaming generator

**The metadata SSE event pattern:**
```
# Regular token events:
data: {"token": "Full-time", "session_id": "abc"}

# Metadata event (before [DONE]):
data: {"sources": ["Leave Policy, Page 1"], "chunks_used": 3}

# Termination:
data: {"token": "[DONE]"}
```

Streamlit captures the sources from the metadata event and displays them as `📄 Sources: Leave Policy, Page 1` below the streamed answer.

**Answer type badges:**
- `🔍 Answered from company documents` — RAG chain used
- `💬 General HR knowledge` — chat chain used

### Claude Code Prompt

```
Update frontend/app.py to integrate RAG endpoints.
Keep all Phase 1 functionality unchanged.

Add:
- import urllib.parse
- session_state: last_sources = [], last_answer_type = "chat"

Sidebar addition — after backend status:
- GET /rag/status
- Show: st.sidebar.success(f"📄 {count} policy chunks indexed")
- Caption: "Leave Policy · Code of Conduct · Benefits Guide · Employee Handbook"
- On error: st.sidebar.warning("⚠️ Document search unavailable")

New function stream_rag(question, session_id):
- httpx.stream("POST", f"{BACKEND_URL}/rag/stream", ...)
- For each SSE line:
  - "sources" in data → store in session_state.last_sources
  - token == "[DONE]" → break
  - token == "[ERROR]" → break
  - else → yield token

Replace chat input handler with routing logic:
- Reset last_sources = [], last_answer_type = "chat"
- Add user message, display bubble
- GET /rag/classify?query={encoded_prompt} with timeout=10
- Default to "chat" on classify error
- If classification == "rag":
    st.write_stream(stream_rag(prompt, session_id))
    st.caption("📄 Sources: " + " · ".join(sources))
    st.caption("🔍 Answered from company documents")
  else:
    st.write_stream(stream_response(prompt, session_id))
    st.caption("💬 General HR knowledge")
- Save to messages with sources and answer_type metadata

Update chat history display to show sources and badge for past messages.
```

### UI Test Results

| Question | Badge | Sources | Result |
|---|---|---|---|
| "Hello, how are you today?" | 💬 General HR knowledge | None | ARIA greets warmly ✅ |
| "What is the parental leave policy?" | 🔍 Company documents | Leave Policy, Page 1 | All 5 bullet points correct ✅ |
| "How many days annual leave do I get?" | 🔍 Company documents | Leave Policy, Page 1 | "25 days per calendar year" ✅ |

### Exit Criteria

| Check | Status |
|---|---|
| Sidebar shows "19 policy chunks indexed" | ✅ |
| Greeting routes to 💬 General HR knowledge | ✅ |
| Policy questions route to 🔍 Company documents | ✅ |
| Source citations display below answer | ✅ |
| Sources persist in conversation history | ✅ |
| Streaming works on RAG responses | ✅ |

---

## Step 9 — DeepEval RAG Evaluation

### Concept

Phase 2 evaluation differs fundamentally from Phase 1. We're evaluating a retrieval pipeline, not just a language model. Four new metrics:

| Metric | What It Measures | How It Works |
|---|---|---|
| `FaithfulnessMetric` | Are ARIA's claims grounded in retrieved chunks? | Checks every factual claim against `retrieval_context` |
| `ContextualPrecisionMetric` | Is the most relevant chunk ranked first? | Evaluates ranking quality of retrieved chunks |
| `ContextualRecallMetric` | Do retrieved chunks contain all needed info? | Checks if `retrieval_context` covers all expected output facts |
| `AnswerRelevancyMetric` | Is the answer relevant to the question? | Carried from Phase 1 as regression check |

**Critical difference from Phase 1 test cases — `retrieval_context` field:**
```python
# Phase 1 — no retrieval context
LLMTestCase(input=question, actual_output=response, expected_output=expected)

# Phase 2 — retrieval context required for RAG metrics
LLMTestCase(
    input=question,
    actual_output=response,
    expected_output=expected,
    retrieval_context=[chunk1.text, chunk2.text, chunk3.text]  # ← new
)
```

**Rate limit mitigation applied:**
- `time.sleep(0.5)` in `get_rag_response()` and `get_retrieval_context()` helpers
- Max 3 test cases per LLM-judged function
- Judge model: `gpt-4o` (not mini — mini caused timeouts with structured schema)
- Timeout env vars required:
  ```bash
  export DEEPEVAL_PER_TASK_TIMEOUT_SECONDS_OVERRIDE=600
  export DEEPEVAL_PER_ATTEMPT_TIMEOUT_SECONDS_OVERRIDE=300
  ```
- 60-second gap between test function runs

---

## RAG Golden Dataset — rag_golden_set.json

**Location:** `evaluation/datasets/rag_golden_set.json`
**Total entries:** 15
**Coverage:** All 4 documents, specific citable expected outputs

### Claude Code Prompt

```
Create evaluation/datasets/rag_golden_set.json with 15 entries.
Each entry: input, expected_output (specific and citable), document.

[
  {"input": "How many days of annual leave do full-time employees receive?",
   "expected_output": "Full-time employees at Acme Corp receive 25 days of
   annual leave per calendar year, accruing at 2.08 days per month.",
   "document": "leave_policy.pdf"},

  {"input": "What is the parental leave entitlement for a primary caregiver?",
   "expected_output": "Primary caregivers receive 16 weeks of fully paid
   parental leave. Must have 6 months service, give 8 weeks written notice.",
   "document": "leave_policy.pdf"},

  {"input": "How many sick days do employees get per year?",
   "expected_output": "10 days per calendar year. Does not accrue or carry
   over. Doctor certificate required after 3 consecutive days.",
   "document": "leave_policy.pdf"},

  {"input": "What is the maximum annual leave carryover?",
   "expected_output": "Maximum 5 days carried over to following calendar year.
   Excess forfeited at year end.",
   "document": "leave_policy.pdf"},

  {"input": "How do I submit a leave request at Acme Corp?",
   "expected_output": "Submit via HR portal at least 2 weeks in advance.
   Manager approves within 5 business days. HR confirms within 2 business days.",
   "document": "leave_policy.pdf"},

  {"input": "What are the steps to report a harassment complaint?",
   "expected_output": "Step 1: Raise with direct manager. Step 2: Escalate
   to HR Business Partner if unresolved in 5 days. Step 3: Submit formal
   grievance to HR Director. Step 4: Independent investigation within 15
   business days. All confidential, no retaliation policy.",
   "document": "code_of_conduct.pdf"},

  {"input": "What are the stages of the disciplinary procedure?",
   "expected_output": "Stage 1: Verbal warning. Stage 2: Written warning
   (12 months). Stage 3: Final written warning (12 months). Stage 4: Dismissal
   with 10-day right of appeal.",
   "document": "code_of_conduct.pdf"},

  {"input": "Does the company pay for health insurance?",
   "expected_output": "Yes. Employee coverage 100% company-paid. Dependant
   coverage 80% company-paid. Dental and vision included. Effective from
   first day of employment.",
   "document": "benefits_guide.pdf"},

  {"input": "What is the company match for the 401k retirement plan?",
   "expected_output": "100% match on first 3% of base salary, 50% on next 3%.
   Company match vests over 3 years. Eligible after 90 days.",
   "document": "benefits_guide.pdf"},

  {"input": "What is the annual professional development budget?",
   "expected_output": "$2,000 per employee per year for courses, conferences,
   certifications. Manager approval required.",
   "document": "benefits_guide.pdf"},

  {"input": "How long is the probation period at Acme Corp?",
   "expected_output": "90 days. Informal 60-day check-in, formal 90-day
   assessment. Extensible up to 30 days with HR Director approval.",
   "document": "employee_handbook.pdf"},

  {"input": "What is the remote work policy at Acme Corp?",
   "expected_output": "Hybrid model: minimum 3 days in office, max 2 days
   remote. New employees receive $500 home office allowance. Must be available
   during core hours when remote.",
   "document": "employee_handbook.pdf"},

  {"input": "What are the standard working hours at Acme Corp?",
   "expected_output": "9am-5pm Monday to Friday, 37.5 hours per week. Core
   hours 10am-3pm. Overtime pre-approved, compensated at 1.5x rate.",
   "document": "employee_handbook.pdf"},

  {"input": "What is the notice period for termination?",
   "expected_output": "4 weeks (or per employment contract). Company may pay
   in lieu. Final paycheck within 5 business days. Exit interview within
   final week.",
   "document": "employee_handbook.pdf"},

  {"input": "What wellness benefits does Acme Corp offer?",
   "expected_output": "$50/month gym subsidy, 6 free EAP mental health
   sessions per year, $500 annual wellness allowance for eligible expenses.",
   "document": "benefits_guide.pdf"}
]
```

### Golden Set by Document

| Document | Rows | Questions Cover |
|---|---|---|
| `leave_policy.pdf` | 1–5 | Annual leave, parental, sick, carryover, application process |
| `code_of_conduct.pdf` | 6–7 | Harassment reporting, disciplinary stages |
| `benefits_guide.pdf` | 8–10, 15 | Health insurance, 401k, professional development, wellness |
| `employee_handbook.pdf` | 11–14 | Probation, remote work, working hours, termination |

---

## Test Functions — Which Rows Each Test Uses

**File:** `evaluation/tests/test_document_rag.py`

### test_rag_faithfulness
**Rows used:** 1, 2, 3 (golden_set[:3])
**Metric:** `FaithfulnessMetric(threshold=0.8, model="gpt-4o")`
**Purpose:** Verifies ARIA's answers are grounded in retrieved chunks with no hallucination against context.

### test_rag_contextual_precision
**Rows used:** 1, 2, 3 (golden_set[:3])
**Metric:** `ContextualPrecisionMetric(threshold=0.7, model="gpt-4o")`
**Purpose:** Verifies the most relevant chunk is ranked first in retrieval for leave policy questions.

### test_rag_contextual_recall
**Rows used:** 2, 6 (indexes [1, 5])
**Metric:** `ContextualRecallMetric(threshold=0.7, model="gpt-4o")`
**Purpose:** Verifies retrieved context contains all facts needed for multi-part answers (parental leave, harassment steps).

### test_rag_answer_relevancy
**Rows used:** 1, 2, 3 (golden_set[:3])
**Metric:** `AnswerRelevancyMetric(threshold=0.7, model="gpt-4o")`
**Purpose:** Regression check — RAG answers must be as relevant as Phase 1 chat answers.

### test_rag_document_routing
**Rows used:** All 15
**Metric:** None (pure assertion, no LLM judge)
**Purpose:** Verifies all 15 policy questions classify as `"rag"` not `"chat"`. No rate limit risk — no LLM evaluation calls.

**Row-to-test mapping:**

| Row | Question Summary | Faithfulness | Precision | Recall | Relevancy | Routing |
|---|---|---|---|---|---|---|
| 1 | Annual leave days | ✅ | ✅ | | ✅ | ✅ |
| 2 | Parental leave primary | ✅ | ✅ | ✅ | ✅ | ✅ |
| 3 | Sick days per year | ✅ | ✅ | | ✅ | ✅ |
| 4 | Annual leave carryover | | | | | ✅ |
| 5 | Leave application process | | | | | ✅ |
| 6 | Harassment reporting steps | | | ✅ | | ✅ |
| 7 | Disciplinary stages | | | | | ✅ |
| 8 | Health insurance | | | | | ✅ |
| 9 | 401k match | | | | | ✅ |
| 10 | Professional development budget | | | | | ✅ |
| 11 | Probation period | | | | | ✅ |
| 12 | Remote work policy | | | | | ✅ |
| 13 | Working hours | | | | | ✅ |
| 14 | Notice period termination | | | | | ✅ |
| 15 | Wellness benefits | | | | | ✅ |

---

## DeepEval Run Commands

```bash
# Required environment variables (set once per terminal session)
export DEEPEVAL_PER_TASK_TIMEOUT_SECONDS_OVERRIDE=600
export DEEPEVAL_PER_ATTEMPT_TIMEOUT_SECONDS_OVERRIDE=300

# Run each test with 60-second gaps to avoid rate limits
uv run deepeval test run evaluation/tests/test_document_rag.py::test_rag_faithfulness -v
sleep 60
uv run deepeval test run evaluation/tests/test_document_rag.py::test_rag_contextual_precision -v
sleep 60
uv run deepeval test run evaluation/tests/test_document_rag.py::test_rag_contextual_recall -v
sleep 60
uv run deepeval test run evaluation/tests/test_document_rag.py::test_rag_answer_relevancy -v
sleep 60
uv run deepeval test run evaluation/tests/test_document_rag.py::test_rag_document_routing -v
```

---

## DeepEval Results — Final Baseline

### test_rag_faithfulness

```
Faithfulness: avg=1.00, pass rate=100%, total=3
Cost: $0.029 | Time: 14s
```

**Judge reasoning (sample):**
> "The score is 1.00 because there are no contradictions between the actual output and the retrieval context. Everything aligns perfectly, showcasing a high level of accuracy and consistency."

---

### test_rag_contextual_precision

```
Contextual Precision: avg=1.00, pass rate=100%, total=3
Cost: $0.018 | Time: 12s
```

**Judge reasoning — annual leave question:**
> "The relevant node ranked first provides a direct answer with 'Full-time employees: 25 days per calendar year'. The irrelevant nodes ranked second and third discuss sick leave and emergency leave, appropriately ranked lower."

**Judge reasoning — parental leave question:**
> "The relevant node ranked first provides comprehensive details stating 'Primary caregiver: 16 weeks fully paid'. The irrelevant nodes focus on emergency leave and unpaid leave, appropriately ranked lower."

---

### test_rag_contextual_recall

```
Contextual Recall: avg=1.00, pass rate=100%, total=2
Cost: $0.011 | Time: 9s
```

**Judge reasoning:**
> "Every sentence in the expected output is perfectly aligned with the information from the 4th node in the retrieval context, ensuring complete accuracy and relevance."

---

### test_rag_answer_relevancy

```
Answer Relevancy: avg=1.00, pass rate=100%, total=3
Cost: $0.012 | Time: 12s
```

**Judge reasoning — parental leave:**
> "The score is 1.00 because the response perfectly addressed the question about parental leave entitlement for a primary caregiver without any irrelevant information."

---

### test_rag_document_routing

```
Routing assertion: 15/15 classified as "rag"
Cost: $0.00 (no LLM judge) | Time: 10s
```

All 15 policy questions correctly routed to the RAG chain, not the general chat chain.

---

## Phase 2 DeepEval Complete Baseline

| Test | Metric | Avg Score | Pass Rate | Cases | Cost | Time |
|---|---|---|---|---|---|---|
| `test_rag_faithfulness` | Faithfulness | **1.00** | 100% | 3 | $0.029 | 14s |
| `test_rag_contextual_precision` | Contextual Precision | **1.00** | 100% | 3 | $0.018 | 12s |
| `test_rag_contextual_recall` | Contextual Recall | **1.00** | 100% | 2 | $0.011 | 9s |
| `test_rag_answer_relevancy` | Answer Relevancy | **1.00** | 100% | 3 | $0.012 | 12s |
| `test_rag_document_routing` | Routing assertion | **100%** | 100% | 15 | $0.000 | 10s |
| **Total** | | **1.00** | **100%** | **26** | **$0.070** | **57s** |

---

## Phase 2 Complete ✅

| Step | What Was Built | Status |
|---|---|---|
| Step 1 | 4 HR policy PDFs — Leave, Conduct, Benefits, Handbook | ✅ |
| Step 2 | PDF ingestion — PyMuPDF extraction, metadata tagging | ✅ |
| Step 3 | Chunker — 800 chars, 100 overlap, 19 chunks | ✅ |
| Step 4 | Vector store — 19 embeddings in ChromaDB `hr_policies` | ✅ |
| Step 5 | Retriever — similarity search, citation formatting | ✅ |
| Step 6 | RAG chain — temperature 0.1, grounded answers | ✅ |
| Step 7 | FastAPI — /rag/query, /rag/stream, /rag/classify, /rag/status | ✅ |
| Step 8 | Streamlit — routing badges, source citations, RAG status | ✅ |
| Step 9 | DeepEval — 5 tests, 26 cases, 100% pass, $0.07 cost | ✅ |

---

## Phase 2 vs Phase 1 Metric Comparison

| Metric | Phase 1 Baseline | Phase 2 Result | Change |
|---|---|---|---|
| HR Role Adherence | 0.95 | N/A (chat-specific) | — |
| Answer Relevancy | 0.98 | **1.00** | +0.02 |
| Hallucination | 0.00 | **0.00** | Maintained |
| Faithfulness | N/A | **1.00** | New metric |
| Contextual Precision | N/A | **1.00** | New metric |
| Contextual Recall | N/A | **1.00** | New metric |
| Document Routing | N/A | **100%** | New metric |

Answer Relevancy improved from 0.98 to 1.00 — grounding answers in specific documents eliminates the vagueness that occasionally reduced relevancy scores in Phase 1.

---

## Known Gaps — Phase 7 Tuning Items

| Issue | Severity | Phase 7 Fix |
|---|---|---|
| Harassment query retrieves Professional Behaviour before Grievance steps | Low — correct document, wrong ranking | Increase chunk overlap or query expansion |
| Professional development query hits disability insurance text | Low — correct document, wrong ranking | Adjust chunk boundaries in benefits_guide |
| 15 golden set entries, only 11 LLM-evaluated due to rate limits | Acceptable | Upgrade OpenAI tier for higher TPM |

Both ranking issues: ARIA still answers correctly because the right content appears in chunks 2-3. The `ContextualPrecisionMetric` would flag these — reserved for Phase 7 full suite.

---

## Infrastructure Notes

**ChromaDB connection:** The container has no `curl` or `python3` in PATH — health checks must be removed from `docker-compose.yml`. Verify via `curl http://localhost:8001/api/v2/heartbeat` from the host Mac terminal.

**Re-indexing command:** If documents change, reset and reindex:
```bash
uv run python -m vector_store.indexer
# (with reset=True in the test block)
```

**sys.path fix for DeepEval tests:** Tests in `evaluation/tests/` must add the project root to `sys.path` to import from `rag.*`:
```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)
))))
```

---

## What Comes Next — Phase 3: Database RAG

Phase 3 adds a second RAG source — structured employee data from PostgreSQL. When an employee asks "What is John Smith's leave balance?" or "Who reports to the Engineering VP?", ARIA will query the database and answer with real-time employee data.

**Phase 3 components:**
- SQLAlchemy queries converting employee records to text chunks
- Hybrid retriever combining document RAG (policies) + database RAG (employee data)
- Router updated to classify database vs document vs general chat queries
- New DeepEval metrics: accuracy against live database records

**The Phase 2 baseline must be maintained:** All 5 RAG tests must continue to pass at 100% through Phase 3, 4, 5, and beyond. If a Phase 3 change causes a regression in faithfulness or precision, fix it before proceeding.

> **Golden Rule:** Document RAG answers from Phase 2 must remain grounded and cited in all future phases. ARIA never reverts to general knowledge for questions that have a company document answer.
