# Endpoint usage rules:
# /rag/query  → DeepEval evaluations only (complete JSON response)
# /rag/stream → Streamlit UI always (SSE token stream)
# Same pattern as /chat/ vs /chat/stream from Phase 1

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from backend.schemas.rag import RAGRequest, RAGResponse
from rag.document_rag.chain import rag_query, rag_query_stream
from backend.chains.rag_router import classify_query
from vector_store.store import vector_store
import logging
import json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/query", response_model=RAGResponse)
async def rag_query_endpoint(request: RAGRequest) -> RAGResponse:
    try:
        result = await rag_query(request.question)
        return RAGResponse(
            answer=result.answer,
            sources=result.sources,
            chunks_used=result.chunks_used,
            query=result.query,
            session_id=request.session_id,
        )
    except Exception as exc:
        logger.error(f"RAG query error: {exc}")
        return RAGResponse(
            answer="I encountered an error searching the documents. Please contact HR at hr@acmecorp.com.",
            sources=[],
            chunks_used=0,
            query=request.question,
            session_id=request.session_id,
        )


@router.post("/stream")
async def rag_stream_endpoint(request: RAGRequest) -> StreamingResponse:
    async def event_stream():
        sources: list[str] = []
        chunks_used: int = 0

        # Stream answer tokens
        from rag.document_rag.retriever import retrieve_with_context
        retrieval = retrieve_with_context(request.question, top_k=request.top_k)
        sources = retrieval["sources"]
        chunks_used = len(retrieval["chunks"])

        async for token in rag_query_stream(request.question):
            payload = json.dumps({"token": token, "session_id": request.session_id})
            yield f"data: {payload}\n\n"

        # Metadata event so Streamlit can display citations
        meta = json.dumps({"sources": sources, "chunks_used": chunks_used, "session_id": request.session_id})
        yield f"data: {meta}\n\n"

        yield f"data: {json.dumps({'token': '[DONE]'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/classify")
async def classify_query_endpoint(query: str = Query(...)) -> dict:
    try:
        classification = await classify_query(query)
        return {"query": query, "classification": classification}
    except Exception as e:
        logger.error(f"Classification error: {e}")
        return {"query": query, "classification": "rag", "error": str(e)}


@router.get("/status")
def rag_status() -> dict:
    return {
        "status": "ok",
        "collection": "hr_policies",
        "vectors": vector_store.count(),
        "embedding_model": "text-embedding-3-small",
    }
