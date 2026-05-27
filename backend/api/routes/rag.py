# Endpoint usage rules:
# /rag/query  → DeepEval evaluations only (complete JSON response)
# /rag/stream → Streamlit UI always (SSE token stream)
# Same pattern as /chat/ vs /chat/stream from Phase 1

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from backend.schemas.rag import RAGRequest, RAGResponse
from rag.document_rag.chain import rag_query, rag_query_stream
from rag.database_rag.chain import db_rag_query, db_rag_query_stream
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


@router.post("/db/query")
async def database_rag_query(request: RAGRequest) -> dict:
    # RAGRequest reused — same fields work for DB questions
    try:
        result = await db_rag_query(request.question)

        if result.answer == "NOT_DB_QUERY":
            return {
                "answer": "This question is better answered from company documents. Please use /rag/query.",
                "sql_used": "",
                "row_count": 0,
                "query": request.question,
                "session_id": request.session_id,
                "model": "gpt-4o-db",
                "success": False,
            }

        return {
            "answer": result.answer,
            "sql_used": result.sql_used,
            "row_count": result.row_count,
            "query": result.query,
            "session_id": request.session_id,
            "model": "gpt-4o-db",
            "success": result.success,
        }
    except Exception as e:
        logger.error(f"Database RAG error: {e}")
        return {
            "answer": "I encountered an error querying the employee database. Please contact HR.",
            "sql_used": "",
            "row_count": 0,
            "query": request.question,
            "session_id": request.session_id,
            "model": "gpt-4o-db",
            "success": False,
        }


@router.post("/db/stream")
async def database_rag_stream(request: RAGRequest) -> StreamingResponse:
    async def stream_generator():
        try:
            async for token in db_rag_query_stream(request.question):
                if token == "NOT_DB_QUERY":
                    yield f"data: {json.dumps({'token': 'NOT_DB_QUERY', 'session_id': request.session_id})}\n\n"
                    return
                else:
                    yield f"data: {json.dumps({'token': token, 'session_id': request.session_id})}\n\n"

            # Run a non-streaming query to get SQL metadata for the client
            meta = await db_rag_query(request.question)
            yield f"data: {json.dumps({'sql_used': meta.sql_used, 'row_count': meta.row_count, 'session_id': request.session_id})}\n\n"
            yield f"data: {json.dumps({'token': '[DONE]'})}\n\n"

        except Exception as e:
            logger.error(f"DB stream error: {e}")
            yield f"data: {json.dumps({'token': '[ERROR]', 'error': str(e)})}\n\n"

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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
