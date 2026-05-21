from pydantic import BaseModel, ConfigDict, Field, field_validator
from datetime import datetime
from uuid import uuid4


class ChatRequest(BaseModel):
    """Request model for chat endpoint.
    Contains the user message and session identifier."""

    model_config = ConfigDict(str_strip_whitespace=True)

    message: str = Field(min_length=1, description="The user's message to ARIA")
    session_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique session identifier for conversation tracking",
    )

    @field_validator("message")
    @classmethod
    def message_not_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("message must not be blank")
        return stripped


class ChatResponse(BaseModel):
    """Response model for chat endpoint.
    Contains ARIA's response with metadata."""

    model_config = ConfigDict(str_strip_whitespace=True)

    response: str = Field(description="ARIA's response to the user")
    session_id: str = Field(description="Echoed session identifier")
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="When the response was generated",
    )
    model: str = Field(default="stub", description="The LLM model used to generate the response")
