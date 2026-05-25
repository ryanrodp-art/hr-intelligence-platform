from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from config.settings import settings
import logging

logger = logging.getLogger(__name__)

ROUTER_PROMPT = (
    "You are a query classifier for an HR assistant system.\n"
    "Classify the user's question as either 'rag' or 'chat'.\n\n"
    "Return 'rag' if the question:\n"
    "- Asks about specific company policies or procedures\n"
    "- Asks about leave entitlements, benefits, or compensation\n"
    "- Asks about conduct, grievances, or disciplinary procedures\n"
    "- Asks about onboarding, probation, or working arrangements\n"
    "- Could be answered from an HR policy document\n\n"
    "Return 'chat' if the question:\n"
    "- Is a general greeting or conversation\n"
    "- Asks about general HR concepts not specific to the company\n"
    "- Is a follow-up that continues a general conversation\n"
    "- Cannot be answered from a policy document\n\n"
    "Return ONLY the word 'rag' or 'chat' — nothing else."
)


async def classify_query(question: str) -> str:
    prompt = ChatPromptTemplate.from_messages([
        ("system", ROUTER_PROMPT),
        ("human", "{question}"),
    ])
    llm = ChatOpenAI(model=settings.openai_model, temperature=0, api_key=settings.openai_api_key)
    chain = prompt | llm | StrOutputParser()
    result = await chain.ainvoke({"question": question})
    result = result.strip().lower()
    if result not in ("rag", "chat"):
        result = "rag"
    logger.info(f"Query classified as '{result}': {question[:50]}")
    return result
