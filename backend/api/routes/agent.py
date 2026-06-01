from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from agents.single.hr_advisor import run_hr_advisor, AgentResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])


class AgentRequest(BaseModel):
    question: str


class AgentQueryResponse(BaseModel):
    answer: str
    tools_used: list[str]
    steps: list[dict]
    success: bool
    question: str


@router.post("/query", response_model=AgentQueryResponse)
def query_agent(request: AgentRequest) -> AgentQueryResponse:
    logger.info(f"Agent query: {request.question[:50]}")
    try:
        result = run_hr_advisor(request.question)
        return AgentQueryResponse(
            answer=result.answer,
            tools_used=result.tools_used,
            steps=result.steps,
            success=result.success,
            question=request.question,
        )
    except Exception as e:
        logger.error(f"Unexpected error in /agent/query: {e}")
        raise HTTPException(status_code=500, detail=str(e))
