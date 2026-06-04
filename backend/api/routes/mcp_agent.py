from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from agents.single.hr_advisor import run_hr_advisor_with_mcp
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/mcp", tags=["mcp"])


class MCPAgentRequest(BaseModel):
    question: str


class MCPAgentResponse(BaseModel):
    answer: str
    tools_used: list[str]
    steps: list[dict]
    success: bool
    question: str


@router.post("/query", response_model=MCPAgentResponse)
async def mcp_query(request: MCPAgentRequest):
    try:
        logger.info(f"MCP query: {request.question[:50]}")
        result = await run_hr_advisor_with_mcp(request.question)
        if not result.success:
            raise HTTPException(status_code=500, detail=result.answer)
        return MCPAgentResponse(
            answer=result.answer,
            tools_used=result.tools_used,
            steps=result.steps,
            success=result.success,
            question=request.question,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"MCP query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
