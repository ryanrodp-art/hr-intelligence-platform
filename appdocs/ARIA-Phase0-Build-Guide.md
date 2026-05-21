# ARIA — HR GenAI Agent Platform
## Phase 0 Build Guide

> Step-by-step Claude Code prompts, validation commands, and learning notes for building the complete project foundation.

**May 2026 | 14 Steps | Phase 0 of 8**

---

## Phase 0 Overview

Phase 0 builds the restaurant before hiring any chefs. Infrastructure, configuration, data models, and UI skeleton — no AI yet.

**What Phase 0 Delivers:**

- Complete project folder structure (22 folders)
- Docker Compose running PostgreSQL and ChromaDB
- FastAPI backend with `/health` and `/chat` stub endpoints
- Streamlit chat UI calling the FastAPI backend
- SQLAlchemy database models (Employee, LeaveRecord, OrgChart)
- 50 seed employees, 30 leave records, 50 org chart rows
- Pydantic settings configuration layer
- DeepEval folder structure ready for Phase 1

**14 Steps at a Glance:**

| # | Step | Delivers |
|---|---|---|
| 1 | Project Structure | 22 folders with .gitkeep placeholders |
| 2 | Docker Compose | PostgreSQL + ChromaDB containers |
| 3 | pyproject.toml | 151 packages via uv sync |
| 4 | .env.example + settings.py | Configuration layer |
| 5 | database/models.py | SQLAlchemy ORM models |
| 6 | database/migrations/init.sql | PostgreSQL tables + indexes |
| 7 | Seed Data CSVs | 50 employees, 30 leave records, 50 org chart rows |
| 8 | scripts/seed_database.py | Loads CSVs into PostgreSQL |
| 9 | backend/schemas/chat.py | Pydantic request/response models |
| 10 | backend/main.py | FastAPI with /health and /chat |
| 11 | frontend/app.py | Streamlit chat UI |
| 12 | .gitignore | Protects .env and secrets |
| 13 | evaluation/ structure | DeepEval folder scaffold |
| 14 | Exit criteria verification | Full stack smoke test |

---

## Step 1 — Project Structure

### Concept

The project structure is the skeleton of the entire application. Every folder has a specific responsibility — this is called **separation of concerns**. Creating it first means Claude Code always knows where things belong.

Empty folders use `.gitkeep` placeholder files because Git does not track empty directories — only files.

```
frontend/        ← everything the user sees (Streamlit)
backend/         ← everything the user talks to (FastAPI)
agents/          ← AI reasoning and decision-making (LangGraph)
rag/             ← knowledge retrieval (document + database)
vector_store/    ← semantic search infrastructure
mcp_server/      ← external tool connections
database/        ← data models, migrations, seed data
documents/       ← source HR documents (PDFs)
evaluation/      ← DeepEval tests and metrics
config/          ← settings and system prompts
scripts/         ← one-off utility scripts
```

### Claude Code Prompt

```
Create the complete project folder structure for the hr-genai-agent-platform
as defined in the README.md.

Rules:
- Create all folders listed in the project structure
- For every folder that has no files yet, add an empty .gitkeep file inside it
- Do not create any code files yet — only the folder structure and .gitkeep placeholders
- After creating everything, print a tree showing all folders and files created

The folders to create are:
frontend/pages/
frontend/components/
backend/api/routes/
backend/api/middleware/
backend/schemas/
agents/orchestrator/
agents/specialist/
agents/single/
rag/document_rag/
rag/database_rag/
vector_store/
mcp_server/tools/
database/seed_data/
database/migrations/
documents/policies/
documents/handbooks/
evaluation/datasets/
evaluation/tests/
evaluation/metrics/
evaluation/reports/
config/prompts/
scripts/
```

### Exit Criteria

| Check | Status |
|---|---|
| 22 folders created | ✅ |
| .gitkeep in every empty folder | ✅ |
| No code files created yet | ✅ |

---

## Step 2 — Docker Compose

### Concept

Docker Compose runs PostgreSQL and ChromaDB as isolated containers. One command starts your entire database stack. Think of it as a power strip — one switch turns on both databases, pre-wired together.

- **PostgreSQL** on port `5432` — stores structured employee data
- **ChromaDB** on port `8001` (maps from internal port `8000`) — stores vector embeddings
- Named volumes ensure data persists across container restarts

### Claude Code Prompt

```
Create docker-compose.yml in the root of the project.

Requirements:
- PostgreSQL service:
  - image: postgres:16
  - container_name: hr_postgres
  - port: 5432:5432
  - environment: POSTGRES_DB=hr_platform, POSTGRES_USER=hr_user,
    POSTGRES_PASSWORD=hr_password
  - named volume: postgres_data mounted to /var/lib/postgresql/data
  - health check: pg_isready -U hr_user -d hr_platform,
    interval 10s, timeout 5s, retries 5

- ChromaDB service:
  - image: chromadb/chroma:latest
  - container_name: hr_chromadb
  - port: 8001:8000
  - named volume: chroma_data mounted to /chroma/chroma
  - environment: IS_PERSISTENT=TRUE, ANONYMIZED_TELEMETRY=FALSE
  - NO healthcheck (container has no curl or python3 in PATH)
  - Add comment: # Verified healthy via: curl http://localhost:8001/api/v2/heartbeat

- Both services on a shared network called hr_network
- Named volumes defined at the bottom: postgres_data, chroma_data

After creating the file, show me the command to start both containers.
```

### Run Commands

```bash
# Start both containers (detached)
docker compose up -d

# Check status
docker compose ps

# Verify ChromaDB is responding
curl http://localhost:8001/api/v2/heartbeat

# Stop containers
docker compose down

# Stop and wipe volumes (full reset)
docker compose down -v
```

### Troubleshooting — ChromaDB Unhealthy

If ChromaDB shows `unhealthy`, the health check command is not available inside the container. Fix: remove the `healthcheck` block entirely from the chromadb service. ChromaDB is healthy if `curl http://localhost:8001/api/v2/heartbeat` returns a response from your Mac terminal.

**Root cause:** The ChromaDB container has neither `curl` nor `python3` in its PATH, so any health check command fails with exit code 127.

### Exit Criteria

| Check | Status |
|---|---|
| `docker compose ps` shows both containers Up | ✅ |
| PostgreSQL shows `(healthy)` | ✅ |
| `curl http://localhost:8001/api/v2/heartbeat` returns response | ✅ |

---

## Step 3 — pyproject.toml

### Concept

`pyproject.toml` is the modern Python project configuration file. It declares all dependencies so any developer can run `uv sync` and get an identical environment. `uv` is 10–100x faster than pip and generates a `uv.lock` file for reproducible installs.

### Claude Code Prompt

```
Create pyproject.toml in the root of the project.

Requirements:
- Project name: hr-intelligence-platform
- Version: 0.1.0
- Description: A multi-agent GenAI platform for HR intelligence
- Python requires: >=3.11
- Use [project] and [dependency-groups] sections for uv compatibility

Dependencies to include:
  fastapi>=0.115.0
  uvicorn[standard]>=0.30.0
  streamlit>=1.40.0
  httpx>=0.27.0
  langchain>=0.3.0
  langchain-openai>=0.2.0
  langchain-community>=0.3.0
  langgraph>=0.2.0
  chromadb>=0.5.0
  psycopg2-binary>=2.9.0
  sqlalchemy>=2.0.0
  alembic>=1.13.0
  pymupdf>=1.24.0
  pandas>=2.0.0
  pydantic>=2.0.0
  pydantic-settings>=2.0.0
  python-dotenv>=1.0.0
  deepeval>=1.0.0

Use [dependency-groups] not [tool.uv] for dev dependencies to avoid
deprecation warnings.

After creating, give me commands to install uv, run uv sync, and verify.
```

### Run Commands

```bash
# Check uv is installed
uv --version

# Install dependencies (creates .venv automatically)
uv sync

# Verify all core packages imported successfully
uv run python -c "import fastapi, langchain, langgraph, chromadb, sqlalchemy, streamlit, deepeval; print('All dependencies OK')"
```

### Exit Criteria

| Check | Status |
|---|---|
| `uv sync` installs without errors | ✅ |
| `All dependencies OK` printed | ✅ |
| No deprecation warnings | ✅ |
| `.venv/` folder created | ✅ |
| `uv.lock` file generated | ✅ |

---

## Step 4 — .env.example + config/settings.py

### Concept

`.env.example` is a template committed to Git showing what variables exist with no real values. `.env` is your actual file with real values, gitignored so it never gets committed. `config/settings.py` is a Pydantic class that reads `.env` and makes all values available as typed Python attributes throughout the app.

### Claude Code Prompt

```
Create two files for the configuration layer:

1. .env.example in the project root with these variables and comments:

# LLM Configuration
OPENAI_API_KEY=your-openai-api-key-here
OPENAI_MODEL=gpt-4o

# PostgreSQL Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=hr_platform
POSTGRES_USER=hr_user
POSTGRES_PASSWORD=hr_password

# ChromaDB Vector Store
CHROMA_HOST=localhost
CHROMA_PORT=8001

# FastAPI Backend
FASTAPI_HOST=localhost
FASTAPI_PORT=8000

# Streamlit Frontend
STREAMLIT_PORT=8501

# MCP Server
MCP_SERVER_HOST=localhost
MCP_SERVER_PORT=8002

# DeepEval / Confident AI
DEEPEVAL_API_KEY=your-deepeval-api-key-here

# Application
APP_NAME=ARIA - HR Intelligence Platform
APP_ENV=development
LOG_LEVEL=INFO

2. config/settings.py using Pydantic BaseSettings:
- Import from pydantic_settings
- Create Settings class with all variables from .env.example
- Correct Python types: str, int
- Sensible defaults for non-sensitive values
- No defaults for OPENAI_API_KEY and DEEPEVAL_API_KEY
- Computed property database_url returning full PostgreSQL connection string:
  postgresql://user:password@host:port/database
- Computed property chroma_url returning http://host:port
- Singleton at bottom: settings = Settings()
- Comment explaining the singleton pattern
```

### After Claude Code Creates the Files

```bash
# Create your actual .env from the template
cp .env.example .env

# Edit .env — set these two values:
# OPENAI_API_KEY=sk-...         (your real OpenAI key)
# POSTGRES_PASSWORD=hr_password  (matches docker-compose.yml)

# Verify settings load correctly
uv run python -c "
from config.settings import settings
print('App:', settings.app_name)
print('DB URL:', settings.database_url)
print('Chroma URL:', settings.chroma_url)
print('Model:', settings.openai_model)
print('Settings OK')
"
```

### Exit Criteria

| Check | Status |
|---|---|
| `.env.example` created and committed | ✅ |
| `.env` created with real API key | ✅ |
| `settings.database_url` prints correctly | ✅ |
| `settings.chroma_url` prints correctly | ✅ |
| `Settings OK` printed with no errors | ✅ |

---

## Step 5 — database/models.py

### Concept

SQLAlchemy is Python's equivalent of Hibernate (Java). It maps database tables to Python classes — each table becomes a class, each row becomes an object, each column becomes an attribute. You write Python instead of SQL for everyday operations.

Three models:
- **Employee** — who works here
- **LeaveRecord** — who took time off and when
- **OrgChart** — who reports to whom

These power Database RAG in Phase 3 and the MCP leave tool in Phase 5.

### Claude Code Prompt

```
Create database/models.py using SQLAlchemy 2.0 with these exact models:

Use these imports:
- from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, Enum, Text
- from sqlalchemy.orm import declarative_base, relationship
- from sqlalchemy.sql import func
- import enum

Create a Base = declarative_base() at the top.

Model 1 — Employee (table: employees):
  id: Integer, primary key, autoincrement
  employee_id: String(20), unique, not nullable (format: EMP-0001)
  first_name: String(100), not nullable
  last_name: String(100), not nullable
  email: String(200), unique, not nullable
  department: String(100), not nullable
  role: String(150), not nullable
  manager_id: String(20), nullable — plain string, NOT ForeignKey
  location: String(100), not nullable
  hire_date: Date, not nullable
  leave_balance: Integer, not nullable, default 25
  status: String(20), not nullable, default Active
  created_at: DateTime, server_default func.now()
  __repr__: <Employee EMP-0001: John Smith>

Model 2 — LeaveRecord (table: leave_records):
  id: Integer, primary key, autoincrement
  employee_id: String(20), not nullable
  start_date: Date, not nullable
  end_date: Date, not nullable
  leave_type: String(50), not nullable
  status: String(20), not nullable, default Pending
  approved_by: String(20), nullable
  reason: Text, nullable
  created_at: DateTime, server_default func.now()
  __repr__: <LeaveRecord EMP-0001: start to end>

Model 3 — OrgChart (table: org_chart):
  id: Integer, primary key, autoincrement
  employee_id: String(20), unique, not nullable
  manager_id: String(20), nullable
  level: Integer, not nullable (1=CEO 2=VP 3=Director 4=Manager 5=IC)
  team: String(100), not nullable
  department: String(100), not nullable
  __repr__: <OrgChart EMP-0001 -> EMP-0050 (Level 4)>

After models, add comment block explaining what each model represents,
how they relate, and which project phases use each model.
```

> **Why manager_id is a plain String not a ForeignKey:** Self-referential foreign keys cause a chicken-and-egg problem during seeding — inserting EMP-0001 (manager: EMP-0050) fails because EMP-0050 doesn't exist yet. Plain strings let you insert in any order.

### Exit Criteria

| Check | Status |
|---|---|
| `Employee` model with 13 columns | ✅ |
| `LeaveRecord` model with 9 columns | ✅ |
| `OrgChart` model with 6 columns | ✅ |
| `manager_id` as plain String not ForeignKey | ✅ |
| `__repr__` on all three models | ✅ |

---

## Step 6 — database/migrations/init.sql

### Concept

`init.sql` creates the actual tables in PostgreSQL. Models define structure in Python — PostgreSQL doesn't know about them until this script runs. Uses `CREATE TABLE IF NOT EXISTS` so it's safe to run multiple times.

**Indexes** speed up queries by letting PostgreSQL jump directly to matching rows. We index columns the AI agents will filter on most: `department`, `status`, `employee_id`.

### Claude Code Prompt

```
Create database/migrations/init.sql that creates all three tables
matching the SQLAlchemy models in database/models.py exactly.

Requirements:
- Use CREATE TABLE IF NOT EXISTS for all three tables
- Match every column name, type, and constraint from models.py
- PostgreSQL type mappings:
  String(20) → VARCHAR(20)
  String(100) → VARCHAR(100)
  String(150) → VARCHAR(150)
  String(200) → VARCHAR(200)
  Integer → INTEGER
  Date → DATE
  DateTime with server_default → TIMESTAMP DEFAULT NOW()
  Text → TEXT
- Include all NOT NULL constraints
- Include all DEFAULT values
- Include all UNIQUE constraints
- Add section comments before each table
- At the bottom add CREATE INDEX statements for:
  employees: employee_id, department, status, manager_id
  leave_records: employee_id, status, start_date
  org_chart: employee_id, manager_id, department

After creating, give me the psql command to run it against Docker.
```

### Run Commands

```bash
# Make sure Docker is running first
docker compose up -d

# Run the migration
docker exec -i hr_postgres psql -U hr_user -d hr_platform < database/migrations/init.sql

# Verify tables were created
docker exec -it hr_postgres psql -U hr_user -d hr_platform -c "\dt"

# Verify indexes were created
docker exec -it hr_postgres psql -U hr_user -d hr_platform -c "\di"

# Inspect employees table structure
docker exec -it hr_postgres psql -U hr_user -d hr_platform -c "\d employees"
```

### Exit Criteria

| Check | Status |
|---|---|
| `employees` table created | ✅ |
| `leave_records` table created | ✅ |
| `org_chart` table created | ✅ |
| All indexes created | ✅ |
| `\dt` shows exactly 3 tables | ✅ |

---

## Step 7 — Seed Data CSVs

### Concept

Seed data is realistic fake data that populates the database for development and testing. The quality of AI agent responses depends on the quality of this data — generic names produce generic responses.

### Claude Code Prompt

```
Create three CSV files in database/seed_data/ with realistic HR data.

FILE 1: database/seed_data/employees.csv
Columns: employee_id, first_name, last_name, email, department, role,
         manager_id, location, hire_date, leave_balance, status
50 employees:
- employee_id: EMP-0001 through EMP-0050
- Diverse realistic names (Western, Asian, Indian, Hispanic)
- Departments: Engineering(15), HR(8), Sales(10), Marketing(8), Finance(9)
- Locations: Seattle, New York, London, Singapore, Sydney
- Hierarchy: 1 VP → 1-2 Directors → 2-3 Managers → Individual Contributors
- hire_date: between 2018-01-01 and 2024-12-31
- leave_balance: 5-30 days (seniors have more)
- status: 47 Active, 2 Inactive, 1 On Leave
- email: firstname.lastname@hrplatform.com (lowercase)

FILE 2: database/seed_data/leave_records.csv
Columns: employee_id, start_date, end_date, leave_type, status, approved_by, reason
30 leave records:
- leave_type: Annual(15), Sick(8), Parental(2), Emergency(3), Unpaid(2)
- status: 20 Approved, 6 Pending, 4 Rejected
- approved_by: employee's manager_id (null for Pending)
- dates in 2024 and 2025

FILE 3: database/seed_data/org_chart.csv
Columns: employee_id, manager_id, level, team, department
50 rows — one per employee:
- level: 2=VP, 3=Director, 4=Manager, 5=Individual Contributor
- team names: Platform, Backend, Frontend, Data, DevOps (Engineering);
  People Ops, Talent Acquisition (HR); Enterprise Sales, SMB Sales (Sales);
  Brand & Content, Digital Marketing (Marketing); FP&A, Accounting (Finance)

After creating, report total row counts and 3 sample rows from each file.
```

### Validation Commands

```bash
# Verify employee counts
uv run python -c "
import pandas as pd
df = pd.read_csv('database/seed_data/employees.csv')
print(df['department'].value_counts())
print(df['status'].value_counts())
"

# Verify leave record counts
uv run python -c "
import pandas as pd
df = pd.read_csv('database/seed_data/leave_records.csv')
print(df['leave_type'].value_counts())
print(df['status'].value_counts())
"
```

### Exit Criteria

| Check | Status |
|---|---|
| `employees.csv`: 50 rows | ✅ |
| `leave_records.csv`: 30 rows | ✅ |
| `org_chart.csv`: 50 rows | ✅ |
| 47 Active / 2 Inactive / 1 On Leave | ✅ |
| 20 Approved / 6 Pending / 4 Rejected | ✅ |
| 5 departments with correct headcounts | ✅ |

---

## Step 8 — scripts/seed_database.py

### Concept

The seed script bridges the CSVs and PostgreSQL. It reads each CSV and inserts every row as a SQLAlchemy object. It checks for existing data before inserting so it's safe to run multiple times — this is called being **idempotent**.

### Claude Code Prompt

```
Create scripts/seed_database.py that reads the three CSV files
and inserts data into PostgreSQL using SQLAlchemy.

At the top add:
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
(This allows importing from the project root)

Steps the script must follow:
1. Import settings from config.settings and all models from database.models
2. Create SQLAlchemy engine from settings.database_url
3. Create all tables using Base.metadata.create_all(engine) — safety net
4. Create a session using sessionmaker
5. Check if data already exists — if yes, print message and skip that table
6. Read employees.csv and insert Employee objects:
   - Parse hire_date with pd.to_datetime().date()
   - leave_balance as integer
   - Handle empty manager_id as None
7. Read leave_records.csv and insert LeaveRecord objects:
   - Parse start_date and end_date as date objects
   - Handle empty approved_by and reason as None
8. Read org_chart.csv and insert OrgChart objects:
   - Handle empty manager_id as None
   - level as integer
9. After each table print: checkmark Inserted X rows
10. Final summary:
    === Seed Complete ===
    Employees:     50
    Leave Records: 30
    Org Chart:     50
    Total:         130 rows inserted

Error handling:
- Wrap in try/except, rollback on error, print error, exit code 1
- finally: session.close()

After creating, give me the command to run it.
```

### Run Commands

```bash
# Run the seed script
uv run python scripts/seed_database.py

# Verify data in PostgreSQL
docker exec -it hr_postgres psql -U hr_user -d hr_platform -c "SELECT COUNT(*) FROM employees;"
docker exec -it hr_postgres psql -U hr_user -d hr_platform -c "SELECT COUNT(*) FROM leave_records;"
docker exec -it hr_postgres psql -U hr_user -d hr_platform -c "SELECT COUNT(*) FROM org_chart;"
```

### Understanding seed_database.py

**Path setup** — `sys.path.insert(0, ...)` adds the project root to Python's search path so `import config.settings` works from inside the `scripts/` subfolder.

**Engine and Session:**
```python
engine = create_engine(settings.database_url)
Session = sessionmaker(bind=engine)
session = Session()
```
Engine = the connection. Session = the transaction workspace. Nothing gets written until `session.commit()`.

**Existence check** — `session.query(Employee).first()` fetches one row. If it exists, the table is already populated — skip it. Makes the script idempotent.

**Date parsing** — CSV stores everything as strings. `pd.to_datetime(row['hire_date']).date()` converts `"2023-04-15"` to a Python `date` object that SQLAlchemy requires.

**Null handling** — empty CSV cells become `NaN` in Pandas. `pd.notna(row['manager_id'])` checks if a value is present before using it; otherwise store `None`.

**The pipeline:**
```
settings.database_url
    ↓ create_engine()         ← establishes connection
    ↓ sessionmaker()          ← creates session factory
    ↓ session = Session()     ← opens transaction workspace
    ↓ pd.read_csv()           ← reads CSV into DataFrame
    ↓ for row in iterrows()   ← loops each row
    ↓ Employee(**fields)      ← creates Python object
    ↓ session.add(employee)   ← stages for insertion
    ↓ session.commit()        ← writes to PostgreSQL
    ↓ session.close()         ← releases connection
```

### Exit Criteria

| Check | Status |
|---|---|
| Script runs without errors | ✅ |
| 50 employees inserted | ✅ |
| 30 leave records inserted | ✅ |
| 50 org chart rows inserted | ✅ |
| 130 total rows in database | ✅ |
| Re-running script skips existing data | ✅ |

---

## Step 9 — backend/schemas/chat.py

### Concept

Pydantic models define the exact shape of data flowing into and out of the API. Every request is validated automatically — wrong types are rejected before reaching business logic. FastAPI uses these schemas to validate requests, generate `/docs`, and serialize responses.

```
ChatRequest  ← what Streamlit sends to FastAPI
  - message: str       (what the user typed)
  - session_id: str    (which conversation this belongs to — auto-generated UUID)

ChatResponse ← what FastAPI sends back to Streamlit
  - response: str      (ARIA's reply)
  - session_id: str    (echoed back)
  - timestamp: datetime (auto-generated)
  - model: str         (which LLM was used)
```

### Claude Code Prompt

```
Create backend/schemas/chat.py with two Pydantic v2 models.

Imports needed:
- from pydantic import BaseModel, Field, field_validator
- from datetime import datetime
- from uuid import uuid4

Model 1 — ChatRequest:
  Fields:
  - message: str with Field(min_length=1,
    description='The user message to ARIA')
  - session_id: str with Field(
    default_factory=lambda: str(uuid4()),
    description='Unique session identifier')

  Add field_validator for message that:
  - Strips whitespace
  - Raises ValueError if stripped message is empty
  - Returns the stripped message

  Docstring: 'Request model for chat endpoint.'

Model 2 — ChatResponse:
  Fields:
  - response: str with Field(description='ARIA response')
  - session_id: str with Field(description='Echoed session ID')
  - timestamp: datetime with Field(default_factory=datetime.now)
  - model: str with Field(default='stub')

  Docstring: 'Response model for chat endpoint.'

Use model_config = ConfigDict(str_strip_whitespace=True) on both.

After creating, show a quick Python test snippet.
```

### Validation

```bash
uv run python -c "
from backend.schemas.chat import ChatRequest, ChatResponse
req = ChatRequest(message='What is my leave balance?')
print('message:', req.message)
print('session_id:', req.session_id)
res = ChatResponse(response='You have 18 days remaining.',
                   session_id=req.session_id)
print('response:', res.response)
print('model:', res.model)
print('timestamp:', res.timestamp)
"
```

### Exit Criteria

| Check | Status |
|---|---|
| `ChatRequest` model created | ✅ |
| `ChatResponse` model created | ✅ |
| `message` validator strips whitespace | ✅ |
| `session_id` auto-generates UUID | ✅ |
| `timestamp` auto-generates on creation | ✅ |
| Both models serialize correctly | ✅ |

---

## Step 10 — backend/main.py

### Concept

FastAPI is the backend server — the central nervous system of the entire platform. Every component talks to it. In Phase 0 `/chat` returns a hardcoded stub. The structure built here stays unchanged through all 8 phases.

**Key concepts:**
- **CORS Middleware** — allows Streamlit (port 8501) to call FastAPI (port 8000). Without it the browser blocks cross-origin requests
- **Lifespan** — startup/shutdown hooks. Before `yield` = startup. After `yield` = shutdown
- **`async def`** — makes endpoints asynchronous. FastAPI handles many simultaneous requests without blocking
- **`/docs`** — FastAPI auto-generates interactive API documentation from your code. Free with zero extra work

### Claude Code Prompt

```
Create backend/main.py — the FastAPI application for ARIA.

Imports needed:
- from fastapi import FastAPI
- from fastapi.middleware.cors import CORSMiddleware
- from contextlib import asynccontextmanager
- import logging, uvicorn
- from backend.schemas.chat import ChatRequest, ChatResponse
- from config.settings import settings

Logging setup:
- logging.basicConfig(level=logging.INFO,
  format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
- logger = logging.getLogger(__name__)

Lifespan (startup/shutdown):
- @asynccontextmanager async def lifespan(app: FastAPI)
- On startup log:
  'ARIA HR Intelligence Platform starting...'
  'Environment: {settings.app_env}'
  'Database: {settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}'
  'ChromaDB: {settings.chroma_url}'
  'ARIA is ready to assist!'
- yield
- On shutdown log: 'ARIA shutting down. Goodbye!'

App creation:
- title='ARIA — HR Intelligence Platform'
- description='A multi-agent GenAI platform for HR intelligence.'
- version='0.1.0'
- docs_url='/docs', redoc_url='/redoc'
- lifespan=lifespan

CORS middleware:
- allow_origins=['http://localhost:8501', 'http://127.0.0.1:8501']
- allow_credentials=True
- allow_methods=['*'], allow_headers=['*']

GET /health endpoint returns:
  status, service, version, environment,
  database (host:port), vector_store (chroma_url)

POST /chat endpoint:
- Accepts ChatRequest, returns ChatResponse
- Log: f'Chat request from session {session_id}: {message[:50]}...'
- Response: 'Hello! I am ARIA, your HR Intelligence Assistant.
  I can help you with HR policies, leave requests, employee
  information, and more. AI features coming in Phase 1!'
- model: 'stub-phase-0'

Main block: uvicorn.run on host 0.0.0.0 port 8000 reload=True

After creating, give me commands to start and test both endpoints.
```

### Run and Test Commands

```bash
# Terminal Tab 1 — start FastAPI
uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal Tab 2 — test health endpoint
curl http://localhost:8000/health
# Expected: {"status": "ok", "service": "hr-genai-agent-platform", ...}

# Test chat stub
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello ARIA", "session_id": "test-001"}'
# Expected: ARIA stub response with session_id echoed back

# View auto-generated API docs in browser
open http://localhost:8000/docs
```

### Understanding backend/main.py

**The request flow:**
```
Streamlit → POST /chat {message, session_id}
    ↓ CORS middleware checks origin — localhost:8501 allowed
    ↓ FastAPI routes to chat() function
    ↓ Pydantic validates ChatRequest
    ↓ Logger logs the message
    ↓ ChatResponse built (stub in Phase 0, GPT-4o in Phase 1)
    ↓ Pydantic serializes to JSON
    ↓ FastAPI returns 200 OK
    ← Streamlit receives and displays response
```

**Why `async def`?** FastAPI is built on asyncio — Python's asynchronous runtime. `async` means the server can handle thousands of simultaneous requests without one blocking another. Critical for streaming AI responses in Phase 1.

**Why `host="0.0.0.0"`?** Listens on all network interfaces. `localhost` only accepts connections from your own machine. `0.0.0.0` is needed when running in Docker containers.

### Exit Criteria

| Check | Status |
|---|---|
| FastAPI server starts with no errors | ✅ |
| Startup logs show all config values | ✅ |
| `GET /health` returns `{"status": "ok"}` | ✅ |
| `POST /chat` returns stub response | ✅ |
| `session_id` echoed back correctly | ✅ |
| `timestamp` auto-generated in response | ✅ |
| `--reload` watching for file changes | ✅ |

---

## Step 11 — frontend/app.py

### Concept

Streamlit turns Python scripts into web applications — no HTML, CSS, or JavaScript needed. The entire chat interface is pure Python.

**Three critical Streamlit concepts:**

**`st.session_state`** — Streamlit reruns the entire script on every user interaction. Without `session_state`, your conversation history disappears after every message. `session_state` is a dictionary that persists across reruns.

**`st.chat_message(role)`** — renders a chat bubble. `"user"` = human bubble, `"assistant"` = ARIA bubble.

**`st.chat_input()`** — the text box at the bottom. Returns the typed message when Enter is pressed, `None` otherwise.

> **Streamlit's execution model:** Every interaction (typing, clicking) reruns the entire Python script top to bottom. `session_state` is the memory that survives these reruns.

### Claude Code Prompt

```
Create frontend/app.py — the Streamlit chat interface for ARIA.

Imports: streamlit as st, httpx, uuid, datetime
Constant: BACKEND_URL = 'http://localhost:8000'

Page config (must be first Streamlit call):
- page_title='ARIA — HR Intelligence Platform'
- page_icon='🤖', layout='wide'
- initial_sidebar_state='expanded'

Session state initialisation:
- if 'messages' not in st.session_state: set to []
- if 'session_id' not in st.session_state: set to str(uuid.uuid4())

Sidebar (use st.sidebar):
- st.sidebar.title('⚙️ ARIA Configuration')
- Backend status: GET {BACKEND_URL}/health timeout=3
  If ok: st.sidebar.success('✅ Backend Connected') + version caption
  If error: st.sidebar.error('❌ Backend Offline') + start command caption
- Show current session_id with st.sidebar.caption()
- Clear button: resets messages and session_id, calls st.rerun()

Main area:
- st.title('🤖 ARIA')
- st.caption('HR Intelligence Assistant — Powered by GenAI')
- st.divider()

Chat history display:
- Loop st.session_state.messages
- Each: st.chat_message(message['role']) → st.write(content)

Welcome message (only when messages is empty):
- st.chat_message('assistant') with greeting and bullet list:
  📋 HR policies and procedures
  🏖️ Leave requests and balances
  👥 Employee information
  📚 Company guidelines
  🎯 Onboarding assistance

Chat input and response:
- prompt = st.chat_input('Ask ARIA anything about HR...')
- if prompt:
  1. Append user message to session_state.messages
  2. Display with st.chat_message('user')
  3. Inside st.chat_message('assistant'):
     - st.spinner('ARIA is thinking...')
     - httpx.post(BACKEND_URL/chat,
         json={message: prompt, session_id: session_id},
         timeout=30)
     - Extract response.json()['response']
     - st.write(response_text)
     - Append assistant message to session_state.messages
  4. try/except: st.error() if backend unreachable

After creating, give me the command to start Streamlit.
```

### Run Commands

```bash
# Terminal Tab 2 — start Streamlit (Tab 1 must have FastAPI running)
uv run streamlit run frontend/app.py --server.port 8501

# Open in browser
open http://localhost:8501

# Both terminals must be running simultaneously:
# Tab 1: uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
# Tab 2: uv run streamlit run frontend/app.py --server.port 8501
```

### Understanding frontend/app.py

**Why session_state matters:**
```python
# Without session_state — wiped on every rerun:
messages = []

# With session_state — persists across reruns:
if 'messages' not in st.session_state:
    st.session_state.messages = []   # only set once
```

**The walrus operator `:=`:**
```python
# Assigns AND checks in one step
if prompt := st.chat_input('Ask ARIA...'):
    # prompt is set AND truthy — user typed something
```

**The complete message cycle:**
```
User types message and hits Enter
    ↓ Streamlit reruns entire script
    ↓ session_state.messages still has full history
    ↓ Chat history loop renders all previous messages
    ↓ st.chat_input() returns the new message
    ↓ User bubble rendered immediately
    ↓ Spinner shows 'ARIA is thinking...'
    ↓ httpx.post() → FastAPI /chat
    ↓ Response received, spinner disappears
    ↓ Assistant bubble rendered with response
    ↓ Message appended to session_state
    ↓ Script finishes — waits for next input
```

### Exit Criteria

| Check | Status |
|---|---|
| Streamlit starts with no errors | ✅ |
| Sidebar shows `Backend Connected` | ✅ |
| Welcome message displays on first load | ✅ |
| User message appears in chat bubble | ✅ |
| ARIA stub response appears | ✅ |
| Conversation history persists across messages | ✅ |
| Clear button resets conversation | ✅ |

---

## Step 13 — evaluation/ Structure

### Concept

DeepEval is an open-source LLM evaluation framework. It runs automated tests against your AI agent's responses using a judge LLM (GPT-4o) to score metrics like answer relevancy, faithfulness, hallucination, and custom HR accuracy.

Phase 0 creates the folder scaffold and placeholder files. The actual test cases and metric implementations are written in Phase 7 once all agents are built and producing real responses to evaluate.

**Three components created:**

- **Golden sets** — curated input/expected-output pairs used to benchmark the agents. One per subsystem: RAG, agent reasoning, MCP tools
- **Custom metrics** — HR-specific evaluation criteria extending DeepEval's G-Eval. A response may score well on generic relevancy but still give wrong HR policy guidance
- **`conftest.py`** — pytest configuration file auto-loaded before every test run. Configures the judge LLM used to score all metrics in the session

### Claude Code Prompt

```
Set up the DeepEval evaluation folder structure.

1. Create these files with [] as their entire content:
   - evaluation/datasets/rag_golden_set.json
   - evaluation/datasets/agent_golden_set.json
   - evaluation/datasets/mcp_golden_set.json

2. Create evaluation/metrics/custom_hr_metric.py with:

   A module-level docstring:
   "Custom DeepEval metrics for the ARIA HR Intelligence Platform.
   These metrics extend G-Eval with HR-specific evaluation criteria.
   Implemented in Phase 7 — placeholder created in Phase 0."

   A placeholder class CustomHRAccuracyMetric with:
   - Class docstring: "Custom G-Eval metric that evaluates whether
     ARIA's response provides accurate HR guidance that complies
     with company policy. Implemented in Phase 7."
   - A single pass statement as the body

3. Create evaluation/tests/conftest.py with:

   A module-level docstring:
   "DeepEval pytest configuration for ARIA HR Intelligence Platform.
   This conftest.py is automatically loaded by pytest before any test runs.
   It configures the judge LLM used to evaluate all DeepEval metrics."

   Imports: import os, import pytest

   Comment block explaining:
   - DeepEval uses a judge LLM to evaluate your LLM's outputs
   - We use GPT-4o as the judge
   - The OPENAI_API_KEY is read from the environment automatically
   - Confident AI integration will be added in Phase 7

   A pytest fixture called deepeval_config:
   - scope="session"
   - Reads OPENAI_API_KEY from os.environ
   - Prints "DeepEval judge LLM: GPT-4o" to confirm setup
   - Returns {"judge_model": "gpt-4o"}

4. After creating, verify with:
   uv run python -c "import deepeval; print('DeepEval version:', deepeval.__version__)"
   And show the evaluation folder tree with: find evaluation/ -type f | sort
```

### Validation Commands

```bash
# Verify DeepEval is installed and importable
uv run python -c "import deepeval; print('DeepEval version:', deepeval.__version__)"

# Show full evaluation folder structure
find evaluation/ -type f | sort

# Verify golden sets are valid empty JSON arrays
uv run python -c "
import json
for f in ['rag_golden_set', 'agent_golden_set', 'mcp_golden_set']:
    data = json.load(open(f'evaluation/datasets/{f}.json'))
    print(f'{f}.json:', data)
"

# Verify custom metric class is importable
uv run python -c "
from evaluation.metrics.custom_hr_metric import CustomHRAccuracyMetric
print('CustomHRAccuracyMetric:', CustomHRAccuracyMetric)
"

# Verify conftest is syntactically correct
uv run python -c "
import ast, pathlib
src = pathlib.Path('evaluation/tests/conftest.py').read_text()
ast.parse(src)
print('conftest.py: syntax OK')
"
```

### Understanding the Evaluation Scaffold

**Golden sets** are the ground-truth benchmark datasets. Each entry will contain:
```json
{
  "input": "What is my leave balance?",
  "expected_output": "You have 18 days of annual leave remaining.",
  "context": ["Employee EMP-0007 has leave_balance=18, status=Active"]
}
```

**`conftest.py`** is a pytest convention — any file named `conftest.py` is automatically imported before tests run. No explicit import needed in test files:
```
pytest evaluation/tests/
    ↓ pytest finds conftest.py automatically
    ↓ deepeval_config fixture configured for the session
    ↓ all test files inherit the judge LLM setting
```

**Why a custom metric?** DeepEval's built-in `AnswerRelevancyMetric` scores generic relevance. HR responses need an additional check: is the policy guidance actually correct? A response can be relevant but still cite the wrong leave entitlement. `CustomHRAccuracyMetric` adds that domain-specific layer in Phase 7.

### Exit Criteria

| Check | Status |
|---|---|
| `DeepEval version: 4.x.x` printed | ✅ |
| 3 golden set JSON files created with `[]` | ✅ |
| `custom_hr_metric.py` with `CustomHRAccuracyMetric` class | ✅ |
| `conftest.py` with `deepeval_config` session fixture | ✅ |
| All files importable without errors | ✅ |

---

## Phase 0 — Full Stack Verification

> Run these checks in sequence. All must pass before starting Phase 1.

```bash
# 1. Docker infrastructure
docker compose ps
# Expected: hr_postgres (healthy), hr_chromadb (running)

# 2. ChromaDB responding
curl http://localhost:8001/api/v2/heartbeat
# Expected: JSON response

# 3. Settings load from .env
uv run python -c "from config.settings import settings; print(settings.database_url)"
# Expected: postgresql://hr_user:hr_password@localhost:5432/hr_platform

# 4. All imports work
uv run python -c "import fastapi, langchain, langgraph, chromadb, sqlalchemy, streamlit, deepeval; print('All OK')"
# Expected: All OK

# 5. Database seeded
docker exec -it hr_postgres psql -U hr_user -d hr_platform -c "SELECT COUNT(*) FROM employees;"
# Expected: 50

# 6. FastAPI health (must be running in Tab 1)
curl http://localhost:8000/health
# Expected: {"status": "ok", ...}

# 7. FastAPI chat stub
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello ARIA", "session_id": "verify-001"}'
# Expected: ARIA stub response

# 8. DeepEval importable
uv run python -c "import deepeval; print('DeepEval', deepeval.__version__)"

# 9. .env protected by gitignore
cat .gitignore | grep .env
# Expected: .env on its own line

# 10. Streamlit (must be running in Tab 2)
open http://localhost:8501
# Manual: type a message → verify ARIA responds
```

### Phase 0 Final Exit Checklist

| Check | Status |
|---|---|
| Docker: PostgreSQL healthy | ✅ |
| Docker: ChromaDB running + responding | ✅ |
| `pyproject.toml`: 151 packages installed | ✅ |
| `settings.py`: all values load from `.env` | ✅ |
| `database/models.py`: 3 SQLAlchemy models | ✅ |
| `database/migrations/init.sql`: 3 tables + indexes | ✅ |
| Seed data: 130 rows in PostgreSQL (50+30+50) | ✅ |
| `backend/schemas/chat.py`: Pydantic models working | ✅ |
| `backend/main.py`: FastAPI running on port 8000 | ✅ |
| `GET /health`: returns `{"status": "ok"}` | ✅ |
| `POST /chat`: returns stub response | ✅ |
| `frontend/app.py`: Streamlit running on port 8501 | ✅ |
| Chat UI: message sent → ARIA responds | ✅ |
| DeepEval: importable, version printed | ✅ |
| `.env`: listed in `.gitignore`, never committed | ✅ |

---

## What Comes Next — Phase 1: LLM Chat

Phase 1 replaces the hardcoded stub response with real GPT-4o intelligence. The `/chat` endpoint gets wired to LangChain `ChatOpenAI` with streaming responses and `ConversationBufferMemory` so ARIA remembers context across messages.

**Phase 1 components:**
- `LangChain ChatOpenAI` — connects to GPT-4o using your OpenAI API key
- Streaming — tokens appear one by one in the Streamlit UI like native ChatGPT
- `ConversationBufferMemory` — ARIA remembers what was said earlier in the conversation
- HR System Prompt — gives ARIA its persona and domain knowledge boundaries

**Phase 1 DeepEval metrics:**
- `GEval` — does ARIA stay in its HR assistant role?
- `AnswerRelevancyMetric` — are responses relevant to the HR question asked?
- `HallucinationMetric` — does ARIA invent facts not in its context?

> **Golden Rule:** Never start Phase 1 until every Phase 0 exit criterion above passes. The foundation must be solid before adding AI.
