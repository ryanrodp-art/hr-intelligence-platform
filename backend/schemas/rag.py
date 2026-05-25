from pydantic import BaseModel, Field
from uuid import uuid4


class RAGRequest(BaseModel):
    question: str = Field(min_length=1)
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    top_k: int = Field(default=3, ge=1, le=10)


class RAGResponse(BaseModel):
    answer: str
    sources: list[str]
    chunks_used: int
    query: str
    session_id: str
    model: str = "gpt-4o-rag"
