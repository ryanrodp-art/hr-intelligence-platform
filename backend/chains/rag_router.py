from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from config.settings import settings
import logging

logger = logging.getLogger(__name__)

ROUTER_PROMPT = """You are a query classifier for an HR assistant system.
Classify the user's question as 'agent', 'rag', 'db', or 'chat'.

Return 'agent' if the question REQUIRES BOTH:
- A policy or document lookup (general rules, entitlements, procedures)
- AND a specific employee data lookup (named person, leave balance, org structure)
The question cannot be fully answered without retrieving from BOTH sources.
Examples:
  "What is the leave policy and how many days does James have?"
  "What is the remote work policy and what is Sarah's department?"
  "Tell me about parental leave and how much does Isabella have?"

Return 'db' if the question:
- Asks about a SPECIFIC employee by name or employee ID
  (e.g. "How many leave days does James Chen have?")
- Asks about employee leave RECORDS or HISTORY
  (e.g. "Who has pending leave requests?")
- Asks about the ORGANISATIONAL STRUCTURE or reporting lines
  (e.g. "Who reports to the VP of Engineering?")
- Asks about employee COUNT or STATISTICS from the database
  (e.g. "How many employees are in each department?")
- Asks about employees currently ON LEAVE or their status
  (e.g. "Who is currently on leave?")
- Can ONLY be answered by querying employee records

Return 'rag' if the question:
- Asks about company POLICIES or PROCEDURES in general
  (e.g. "What is the parental leave policy?")
- Asks about ENTITLEMENTS in general, not for a specific person
  (e.g. "How many days annual leave do employees get?")
- Asks about company GUIDELINES, CODE OF CONDUCT, or BENEFITS
- Asks about PROCESSES like how to apply for leave or report issues
- Could be answered from a company HR policy document

Return 'chat' if the question:
- Is a general GREETING or casual conversation
- Asks about general HR CONCEPTS not specific to Acme Corp
- Is a follow-up that continues a general conversation
- Cannot be answered from documents OR the employee database

IMPORTANT: Classify as 'agent' before 'db' — if the question needs
BOTH a policy document AND a named employee lookup, always return 'agent'.

Return ONLY the word 'agent', 'rag', 'db', or 'chat' — nothing else."""


async def classify_query(question: str) -> str:
    prompt = ChatPromptTemplate.from_messages([
        ("system", ROUTER_PROMPT),
        ("human", "{question}"),
    ])
    llm = ChatOpenAI(model=settings.openai_model, temperature=0, api_key=settings.openai_api_key)
    chain = prompt | llm | StrOutputParser()
    result = await chain.ainvoke({"question": question})
    result = result.strip().lower()
    if result not in ("agent", "rag", "db", "chat"):
        result = "rag"
    logger.info(f"Query classified as '{result}': {question[:50]}")
    return result
