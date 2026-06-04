from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

from langchain_mcp_adapters.client import MultiServerMCPClient
from agents.single.tools import HR_ADVISOR_TOOLS
from config.settings import settings
from dataclasses import dataclass
import asyncio
import logging

logger = logging.getLogger(__name__)

MCP_SERVER_URL = "http://localhost:8002/mcp"

# Plain system prompt — LangGraph handles ReAct formatting internally.
# No {tools}, {tool_names}, {input}, {agent_scratchpad} placeholders needed.
HR_ADVISOR_SYSTEM_PROMPT = (
    "You are ARIA, an HR Intelligence Assistant for Acme Corp. "
    "You help employees and HR managers with questions about HR "
    "policies, employee records, leave balances, and org structure.\n\n"
    "RULES:\n"
    "- Always use a tool before answering — never answer from memory alone\n"
    "- If the question mentions a specific person by name, always use lookup_employee. "
    "When the question is about how many leave days or remaining leave an employee has, "
    "pass the query as 'What is [full name]'s leave balance?' so the correct "
    "leave_balance column is queried rather than their leave history.\n"
    "- If the question is about a policy rule or entitlement, use search_policies\n"
    "- If the question is broad or cross-cutting, use search_knowledge_base\n"
    "- For compound questions (policy + employee data), call multiple tools in sequence\n"
    "- Always cite your source in the final answer\n"
    "- Only mention hr@acmecorp.com when ALL tools returned no relevant results — "
    "never add it as a footer when the question was answered successfully\n"
    "- Do not end successful answers with 'for more details contact HR' or similar boilerplate"
)


@dataclass
class AgentResponse:
    answer: str
    steps: list[dict]
    tools_used: list[str]
    success: bool


def get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.openai_model,
        temperature=0,
        api_key=settings.openai_api_key,
    )


def build_hr_advisor():
    """Return a compiled LangGraph ReAct agent (CompiledStateGraph)."""
    return create_agent(
        model=get_llm(),
        tools=HR_ADVISOR_TOOLS,
        prompt=HR_ADVISOR_SYSTEM_PROMPT,
    )


def run_hr_advisor(question: str) -> AgentResponse:
    try:
        agent = create_agent(
            model=get_llm(),
            tools=HR_ADVISOR_TOOLS,
            system_prompt=HR_ADVISOR_SYSTEM_PROMPT,
        )
        result = agent.invoke(
            {"messages": [{"role": "user", "content": question}]}
        )
        answer = result["messages"][-1].content
        steps = []
        tools_used = []
        for msg in result["messages"]:
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    steps.append({
                        "thought": f"Calling {tc['name']}",
                        "tool": tc["name"],
                        "tool_input": str(tc["args"]),
                        "observation": "",
                    })
                    tools_used.append(tc["name"])
        logger.info(
            f"run_hr_advisor completed: tools_used={tools_used}, "
            f"steps={len(steps)}, question={question[:50]!r}"
        )
        return AgentResponse(
            answer=answer,
            steps=steps,
            tools_used=tools_used,
            success=True,
        )

    except Exception as e:
        logger.error(f"run_hr_advisor failed for question={question[:50]!r}: {e}")
        return AgentResponse(
            answer=(
                "I encountered an error while processing your question. "
                f"Please try rephrasing or contact hr@acmecorp.com. (Error: {e})"
            ),
            steps=[],
            tools_used=[],
            success=False,
        )


async def build_hr_advisor_with_mcp():
    """Build a compiled LangGraph agent with both direct tools and MCP tools."""
    async with MultiServerMCPClient(
        {"aria_hr_mcp": {"transport": "http", "url": MCP_SERVER_URL}}
    ) as mcp_client:
        mcp_tools = await mcp_client.get_tools()
        all_tools = HR_ADVISOR_TOOLS + mcp_tools
        return create_agent(
            model=get_llm(),
            tools=all_tools,
            system_prompt=HR_ADVISOR_SYSTEM_PROMPT,
        )


async def run_hr_advisor_with_mcp(question: str) -> AgentResponse:
    """Run the HR advisor with MCP tools available."""
    try:
        mcp_client = MultiServerMCPClient(
            {"aria_hr_mcp": {"transport": "http", "url": MCP_SERVER_URL}}
        )
        mcp_tools = await mcp_client.get_tools()
        all_tools = HR_ADVISOR_TOOLS + mcp_tools
        agent = create_agent(
            model=get_llm(),
            tools=all_tools,
            system_prompt=HR_ADVISOR_SYSTEM_PROMPT,
        )
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": question}]}
        )
        answer = result["messages"][-1].content
        steps = []
        tools_used = []
        for msg in result["messages"]:
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    steps.append({
                        "thought": f"Calling {tc['name']}",
                        "tool": tc["name"],
                        "tool_input": str(tc["args"]),
                        "observation": "",
                    })
                    tools_used.append(tc["name"])
        return AgentResponse(
            answer=answer,
            steps=steps,
            tools_used=tools_used,
            success=True,
        )
    except Exception as e:
        logger.error(f"MCP agent error: {e}")
        return AgentResponse(
            answer=(
                "I encountered an error processing your request. "
                "Please try rephrasing or contact hr@acmecorp.com. "
                f"(Error: {e})"
            ),
            steps=[],
            tools_used=[],
            success=False,
        )


if __name__ == "__main__":
    test_questions = [
        "What is the parental leave policy?",
        "How many leave days does James Chen have?",
        "What is the remote work policy and how many days does Isabella Fernandez have?",
        "What should a new hire know about their first week?",
    ]

    for question in test_questions:
        print(f"\n{'=' * 60}")
        print(f"Q: {question}")
        result = run_hr_advisor(question)
        print(f"\nAnswer: {result.answer}")
        print(f"Tools used: {result.tools_used}")
        print(f"Steps: {len(result.steps)}")

    mcp_test_questions = [
        "Check the leave balance for EMP-0001",
        "Submit a leave request for EMP-0001 from 2026-12-28 to 2026-12-30 for Annual leave",
        "Who does EMP-0001 report to?",
        "What is the parental leave policy and check the leave balance for EMP-0001",
    ]

    async def run_mcp_tests():
        for question in mcp_test_questions:
            print(f"\n{'=' * 60}")
            print(f"Q: {question}")
            result = await run_hr_advisor_with_mcp(question)
            print(f"Answer: {result.answer}")
            print(f"Tools used: {result.tools_used}")

    asyncio.run(run_mcp_tests())
