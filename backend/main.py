from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import uvicorn

from backend.schemas.chat import ChatRequest, ChatResponse
from config.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown lifecycle.

    Logs connection targets on startup so operators can confirm the correct
    database and vector store are wired up before traffic is served.
    """
    logger.info("ARIA HR Intelligence Platform starting...")
    logger.info(f"Environment: {settings.app_env}")
    logger.info(f"Database: {settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}")
    logger.info(f"ChromaDB: {settings.chroma_url}")
    logger.info("ARIA is ready to assist!")
    yield
    logger.info("ARIA shutting down. Goodbye!")


app = FastAPI(
    title="ARIA — HR Intelligence Platform",
    description=(
        "A multi-agent GenAI platform for HR intelligence. "
        "Powered by LangGraph, RAG, and GPT-4o."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    """Return service health and connection metadata.

    Used by load balancers, Docker healthchecks, and monitoring tools to
    confirm the API is up and to surface which database and vector store
    it is pointed at.
    """
    return {
        "status": "ok",
        "service": "hr-genai-agent-platform",
        "version": "0.1.0",
        "environment": settings.app_env,
        "database": f"{settings.postgres_host}:{settings.postgres_port}",
        "vector_store": settings.chroma_url,
    }


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """Handle a chat message from the Streamlit frontend.

    Phase 0 stub: returns a static greeting so the frontend and schema can be
    validated end-to-end before the LangGraph agent is wired in Phase 1.
    The session_id is echoed back so the client can correlate requests across
    a conversation thread.
    """
    logger.info(f"Chat request from session {request.session_id}: {request.message[:50]}...")
    return ChatResponse(
        response=(
            "Hello! I am ARIA, your HR Intelligence Assistant. "
            "I can help you with HR policies, leave requests, employee information, "
            "and more. AI features are coming in Phase 1!"
        ),
        session_id=request.session_id,
        model="stub-phase-0",
    )


if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
