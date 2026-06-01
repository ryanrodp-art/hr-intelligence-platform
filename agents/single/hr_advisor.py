from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, ToolMessage
from agents.single.tools import HR_ADVISOR_TOOLS
from config.settings import settings
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

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
        system_prompt=HR_ADVISOR_SYSTEM_PROMPT,
    )


def run_hr_advisor(question: str) -> AgentResponse:
    try:
        agent = build_hr_advisor()
        result = agent.invoke({"messages": [("human", question)]})

        messages = result["messages"]
        answer = messages[-1].content

        steps = []
        tools_used = []

        for msg in messages:
            if isinstance(msg, AIMessage) and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    tool_name = tool_call["name"]
                    tool_input = tool_call["args"]
                    # Match the ToolMessage by tool_call_id
                    tool_msg = next(
                        (
                            m for m in messages
                            if isinstance(m, ToolMessage)
                            and m.tool_call_id == tool_call["id"]
                        ),
                        None,
                    )
                    observation = str(tool_msg.content)[:300] if tool_msg else ""
                    steps.append({
                        "thought": f"Using {tool_name}",
                        "tool": tool_name,
                        "tool_input": str(tool_input),
                        "observation": observation,
                    })
                    tools_used.append(tool_name)

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
