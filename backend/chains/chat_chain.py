from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import SystemMessage
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from config.settings import settings
from typing import AsyncGenerator
import logging

logger = logging.getLogger(__name__)

ARIA_SYSTEM_PROMPT = """You are ARIA (Agentic Resources Intelligence Assistant), an intelligent \
HR assistant for our company. You help employees and HR managers with:

- HR policies and procedures
- Leave requests and balance inquiries
- Employee information and org chart queries
- Company guidelines and compliance
- Onboarding assistance
- Benefits and payroll questions

Guidelines:
- Always be professional, empathetic, and accurate
- If you don't know something, say so clearly — never make up information
- For leave requests or sensitive matters, remind users to confirm \
  with their HR manager
- Keep responses concise but complete
- You have access to company HR policies and employee records

You are currently in Phase 1 — you can answer general HR questions \
based on your training. In later phases you will have access to \
company-specific documents and employee data."""

_memory_store: dict[str, InMemoryChatMessageHistory] = {}


def get_or_create_memory(session_id: str) -> InMemoryChatMessageHistory:
    """Return the existing chat history for a session, or create a new one."""
    if session_id in _memory_store:
        logger.info(f"Retrieved existing memory for session {session_id}")
    else:
        _memory_store[session_id] = InMemoryChatMessageHistory()
        logger.info(f"Created new memory for session {session_id}")
    return _memory_store[session_id]


def get_llm() -> ChatOpenAI:
    """Instantiate and return the ChatOpenAI LLM configured for ARIA."""
    return ChatOpenAI(
        model=settings.openai_model,
        temperature=0.7,
        streaming=True,
        api_key=settings.openai_api_key,
    )


async def chat(message: str, session_id: str) -> str:
    """Send a message to ARIA and return the response.

    Uses RunnableWithMessageHistory (LCEL) to maintain per-session conversation
    history so ARIA remembers context across multiple turns in the same session.
    """
    llm = get_llm()

    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content=ARIA_SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{input}"),
    ])

    chain = prompt | llm

    chain_with_history = RunnableWithMessageHistory(
        chain,
        get_session_history=get_or_create_memory,
        input_messages_key="input",
        history_messages_key="history",
    )

    result = await chain_with_history.ainvoke(
        {"input": message},
        config={"configurable": {"session_id": session_id}},
    )

    response = result.content
    logger.info(f"Session {session_id}: Q={message[:50]}... A={response[:50]}...")
    return response


async def chat_stream(message: str, session_id: str) -> AsyncGenerator[str, None]:
    """Stream GPT-4o response tokens as they are generated.

    Yields each token as a string as it arrives from the LLM.
    Maintains conversation history in memory same as chat().
    """
    llm = get_llm()

    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content=ARIA_SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{input}"),
    ])

    chain = prompt | llm

    chain_with_history = RunnableWithMessageHistory(
        chain,
        get_or_create_memory,
        input_messages_key="input",
        history_messages_key="history",
    )

    full_response = ""

    async for chunk in chain_with_history.astream(
        {"input": message},
        config={"configurable": {"session_id": session_id}},
    ):
        token = chunk.content
        if token:
            full_response += token
            yield token

    logger.info(
        f"Stream complete — session {session_id}: "
        f"Q={message[:50]}... A={full_response[:50]}..."
    )


def clear_memory(session_id: str) -> bool:
    """Clear conversation memory for a session. Returns True if cleared, False if not found."""
    if session_id in _memory_store:
        del _memory_store[session_id]
        return True
    return False


def get_memory_stats() -> dict:
    """Return the number of active sessions and their IDs."""
    return {
        "active_sessions": len(_memory_store),
        "session_ids": list(_memory_store.keys()),
    }
