from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from backend.schemas.chat import ChatRequest, ChatResponse
from backend.chains.chat_chain import chat as chain_chat, chat_stream, clear_memory, get_memory_stats
from config.settings import settings
import logging
import json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Send a message to ARIA and return the GPT-4o response.

    Maintains per-session conversation history so ARIA remembers context
    across multiple turns. Each unique session_id has its own memory buffer.
    """
    logger.info(f"Chat request — session: {request.session_id}, message: {request.message[:50]}...")
    try:
        response_text = await chain_chat(request.message, request.session_id)
        return ChatResponse(
            response=response_text,
            session_id=request.session_id,
            model=settings.openai_model,
        )
    except Exception as e:
        logger.error(f"Chat error for session {request.session_id}: {e}")
        return ChatResponse(
            response="I apologise, I encountered an error. Please try again.",
            session_id=request.session_id,
            model="error",
        )


@router.post("/stream")
async def stream(request: ChatRequest) -> StreamingResponse:
    """Stream GPT-4o response tokens to the client as Server-Sent Events.

    Each event carries a single token. The final event sends '[DONE]'
    so the client knows the stream has ended.
    """
    async def stream_generator():
        try:
            async for token in chat_stream(request.message, request.session_id):
                data = json.dumps({"token": token, "session_id": request.session_id})
                yield f"data: {data}\n\n"
            yield f"data: {json.dumps({'token': '[DONE]', 'session_id': request.session_id})}\n\n"
        except Exception as e:
            logger.error(f"Stream error: {e}")
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


@router.delete("/{session_id}")
def delete_session(session_id: str) -> dict:
    """Clear the conversation memory for a given session."""
    clear_memory(session_id)
    return {"cleared": True, "session_id": session_id}


@router.get("/stats")
def stats() -> dict:
    """Return the number of active in-memory conversation sessions."""
    return get_memory_stats()
