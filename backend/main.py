from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import uvicorn

from config.settings import settings
from backend.api.routes import chat as chat_router
from backend.api.routes import rag as rag_router
from backend.api.routes import agent as agent_router

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


app.include_router(chat_router.router)
app.include_router(rag_router.router)
app.include_router(agent_router.router)


if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
