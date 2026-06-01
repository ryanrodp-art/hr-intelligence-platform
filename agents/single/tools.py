from langchain.tools import tool
from vector_store.searcher import search_and_format
from rag.database_rag.chain import db_rag_query
from config.settings import settings
import asyncio
import logging

logger = logging.getLogger(__name__)


@tool
def search_policies(query: str) -> str:
    """Use this tool for questions about specific HR policies, rules,
    entitlements, or procedures at Acme Corp. Examples: leave
    entitlements, parental leave, sick leave, code of conduct,
    anti-harassment policy, benefits, health insurance, 401k,
    working hours, remote work policy, probation, termination notice.
    Do NOT use this tool if the question mentions a specific employee
    by name — use lookup_employee instead."""
    logger.info(f"search_policies called: {query[:50]}")
    return search_and_format(query, n_results=3)


@tool
def lookup_employee(query: str) -> str:
    """Use this tool for questions about a specific named employee
    OR for questions about employee counts and statistics by
    department, status, or other database fields. Use it when the
    question mentions a person by name, OR when it asks about
    headcount, department size, or aggregate employee data.
    Examples:
    'How many days does James Chen have?', 'Who does Sarah report
    to?', 'What department is Isabella Fernandez in?',
    'Who is currently on leave?',
    'How many employees are in the Engineering department?',
    'How many employees work in each department?'"""
    logger.info(f"lookup_employee called: {query[:50]}")
    result = asyncio.run(db_rag_query(query))
    if result.answer == "NOT_DB_QUERY":
        return (
            "This question cannot be answered from the employee database. "
            "Try search_policies instead."
        )
    if not result.success:
        return f"Database query failed: {result.error}"
    return result.answer


@tool
def search_knowledge_base(query: str) -> str:
    """Use this tool for broad HR questions that don't mention a
    specific employee by name and aren't about a specific policy
    clause. Use for general onboarding questions, cross-cutting
    topics, questions about company culture, or when unsure which
    specific policy applies. This tool searches all available
    Acme Corp HR content."""
    logger.info(f"search_knowledge_base called: {query[:50]}")
    return search_and_format(query, n_results=5)


HR_ADVISOR_TOOLS = [search_policies, lookup_employee, search_knowledge_base]


if __name__ == "__main__":
    print("=== Tool: search_policies ===")
    print(search_policies.invoke("What is the parental leave entitlement?"))

    print("\n=== Tool: lookup_employee ===")
    print(lookup_employee.invoke("How many leave days does James Chen have?"))

    print("\n=== Tool: search_knowledge_base ===")
    print(search_knowledge_base.invoke(
        "What should a new hire know about their first week?"
    ))

    print(f"\nTools registered: {[t.name for t in HR_ADVISOR_TOOLS]}")
