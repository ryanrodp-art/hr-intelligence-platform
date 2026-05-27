from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from rag.database_rag.nl_to_sql import generate_validated_sql
from rag.database_rag.executor import execute_query, format_results_for_llm
from config.settings import settings
import logging
from dataclasses import dataclass
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

DB_ANSWER_SYSTEM_PROMPT = (
    "You are ARIA, an HR Intelligence Assistant for Acme Corp.\n"
    "You have been provided with the results of a database query\n"
    "that answers the employee's question.\n\n"
    "Your job is to present this information clearly and naturally.\n\n"
    "Rules:\n"
    "- For questions asking only WHO (e.g. 'who is on leave',\n"
    "  'who has pending requests'): respond with ONLY the person's\n"
    "  name and the direct answer. No role, no department, no location,\n"
    "  no additional context unless explicitly asked.\n"
    "  Correct: 'Isabella Fernandez is currently on leave.'\n"
    "  Wrong:   'Isabella Fernandez, who is an HR Coordinator,\n"
    "            is currently on leave.'\n"
    "- Present the database results in a clear, conversational way\n"
    "- Always mention specific names, numbers, and dates from the results\n"
    "- If the results show zero records, say so clearly and suggest why\n"
    "- Keep your answer concise — employees want facts, not paragraphs\n"
    "- Do not add information that is not in the query results\n"
    "- If asked about leave balance, always state the exact number of days\n"
    "- Format dates as readable text: 2024-06-03 becomes June 3, 2024\n"
    "- For questions asking WHO (who reports to X, who is on leave,\n"
    "  who has pending requests): answer with names and roles only.\n"
    "  Never add location, hire date, or other unrequested details.\n"
    "  Example: 'Priya Sharma and Marcus Johnson report to the\n"
    "            VP of Engineering. Both are Directors of Engineering.'\n"
    "  Not: 'Priya Sharma is based in Seattle. Marcus Johnson\n"
    "        works out of New York.'\n"
    "- Only include location, department, or other details when\n"
    "  the question explicitly asks for them."
)


@dataclass
class DatabaseRAGResponse:
    answer: str
    sql_used: str
    row_count: int
    query: str
    success: bool
    error: str


def build_db_answer_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([
        ("system", DB_ANSWER_SYSTEM_PROMPT),
        ("human", (
            "Database query results for the question:\n"
            "'{question}'\n\n"
            "Query executed:\n"
            "{sql_used}\n\n"
            "Results:\n"
            "{query_results}\n\n"
            "Please present these results in a clear, conversational way."
        )),
    ])


def get_db_llm() -> ChatOpenAI:
    # temperature=0 for factual database answers
    return ChatOpenAI(
        model=settings.openai_model,
        temperature=0,
        api_key=settings.openai_api_key,
    )


async def db_rag_query(question: str) -> DatabaseRAGResponse:
    # Step 1: Generate and validate SQL
    sql, is_valid, error_msg = await generate_validated_sql(question)

    if sql == "NOT_DB_QUERY":
        return DatabaseRAGResponse(
            answer="NOT_DB_QUERY",
            sql_used="NOT_DB_QUERY",
            row_count=0,
            query=question,
            success=False,
            error="NOT_DB_QUERY",
        )

    if not is_valid:
        return DatabaseRAGResponse(
            answer="I was unable to query the employee database for that question. Please try rephrasing.",
            sql_used="",
            row_count=0,
            query=question,
            success=False,
            error=error_msg,
        )

    # Step 2: Execute the SQL
    result = execute_query(sql)

    if not result.success:
        return DatabaseRAGResponse(
            answer="I encountered an error querying the database. Please contact HR at hr@acmecorp.com.",
            sql_used=sql,
            row_count=0,
            query=question,
            success=False,
            error=result.error,
        )

    # Step 3: Format results for LLM
    formatted_results = format_results_for_llm(result)

    if result.row_count == 0:
        return DatabaseRAGResponse(
            answer="No records were found matching your query. Please verify the details and try again.",
            sql_used=sql,
            row_count=0,
            query=question,
            success=True,
            error="",
        )

    # Step 4: Generate natural language answer
    prompt = build_db_answer_prompt()
    llm = get_db_llm()
    chain = prompt | llm | StrOutputParser()

    generated_answer = await chain.ainvoke({
        "question": question,
        "sql_used": sql,
        "query_results": formatted_results,
    })

    logger.info(f"DB RAG answer generated for: {question[:50]}...")

    return DatabaseRAGResponse(
        answer=generated_answer,
        sql_used=sql,
        row_count=result.row_count,
        query=question,
        success=True,
        error="",
    )


async def db_rag_query_stream(question: str) -> AsyncGenerator[str, None]:
    # Step 1: Generate and validate SQL
    sql, is_valid, error_msg = await generate_validated_sql(question)

    if sql == "NOT_DB_QUERY":
        yield "NOT_DB_QUERY"
        return

    if not is_valid:
        yield "I was unable to query the employee database for that question. Please try rephrasing."
        return

    # Step 2: Execute the SQL
    result = execute_query(sql)

    if not result.success:
        yield "I encountered an error querying the database. Please contact HR at hr@acmecorp.com."
        return

    # Step 3: Format results for LLM
    formatted_results = format_results_for_llm(result)

    if result.row_count == 0:
        yield "No records were found matching your query. Please verify the details and try again."
        return

    # Step 4: Stream natural language answer
    prompt = build_db_answer_prompt()
    llm = ChatOpenAI(
        model=settings.openai_model,
        temperature=0,
        streaming=True,
        api_key=settings.openai_api_key,
    )
    chain = prompt | llm | StrOutputParser()

    async for chunk in chain.astream({
        "question": question,
        "sql_used": sql,
        "query_results": formatted_results,
    }):
        if chunk:
            yield chunk

    logger.info(f"DB RAG stream completed for: {question[:50]}...")


# Run with: uv run python -m rag.database_rag.chain
if __name__ == "__main__":
    import asyncio

    test_questions = [
        "How many leave days does James Chen have?",
        "Show me all employees in the Engineering department",
        "Who has pending leave requests?",
        "Who reports to the VP of Engineering?",
        "What is the annual leave policy?",  # NOT_DB_QUERY
        "How many employees are in each department?",
        "Show me employees currently on leave",
    ]

    async def run_tests():
        for question in test_questions:
            print(f"\nQ: {question}")
            result = await db_rag_query(question)
            if result.answer == "NOT_DB_QUERY":
                print("→ NOT_DB_QUERY (route to document RAG)")
            elif result.success:
                print(f"→ {result.answer}")
                print(f"  SQL: {result.sql_used[:80]}...")
                print(f"  Rows: {result.row_count}")
            else:
                print(f"→ Error: {result.error}")

    asyncio.run(run_tests())
