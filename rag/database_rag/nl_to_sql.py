from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from rag.database_rag.schema import get_full_context
from config.settings import settings
import logging
import re

logger = logging.getLogger(__name__)

NL_TO_SQL_SYSTEM_PROMPT = (
    "You are an expert PostgreSQL query generator for the Acme Corp\n"
    "HR database. Your job is to convert natural language questions\n"
    "into valid PostgreSQL SELECT queries.\n\n"
    "{schema_context}\n\n"
    "STRICT RULES:\n"
    "1. Generate ONLY SELECT statements — never INSERT, UPDATE, DELETE,\n"
    "   DROP, or any other statement type\n"
    "2. Always use table aliases: e for employees, lr for leave_records,\n"
    "   o for org_chart\n"
    "3. Use ILIKE for all name and text matching (case-insensitive)\n"
    "4. Always include LIMIT 10 unless a specific count is requested\n"
    "5. Return ONLY the raw SQL query — no explanation, no markdown\n"
    "   code fences, no backticks, no comments, no semicolon at end\n"
    "6. If the question CANNOT be answered from the database schema\n"
    "   (e.g. policy questions, general HR advice, greetings),\n"
    "   return exactly this string and nothing else: NOT_DB_QUERY\n"
    "7. For employee name searches always use ILIKE on both\n"
    "   first_name AND last_name\n"
    "8. Always select meaningful named columns — never use SELECT *\n"
    "9. For date ranges use CURRENT_DATE for today's date\n"
    "10. When joining tables always use employee_id as the join key"
)


def generate_sql(question: str) -> str:
    schema_context = get_full_context()
    prompt = ChatPromptTemplate.from_messages([
        ("system", NL_TO_SQL_SYSTEM_PROMPT),
        ("human", "Convert this question to SQL: {question}"),
    ])
    llm = ChatOpenAI(
        model=settings.openai_model,
        temperature=0,
        api_key=settings.openai_api_key,
    )
    chain = prompt | llm | StrOutputParser()
    result = chain.invoke({"question": question, "schema_context": schema_context})
    result = result.strip()
    logger.info(f"Generated SQL for: {question[:50]}...")
    logger.info(f"SQL: {result[:100]}...")
    return result


def validate_sql(sql: str) -> tuple[bool, str]:
    if sql == "NOT_DB_QUERY":
        return (False, "NOT_DB_QUERY")
    if not sql:
        return (False, "Empty SQL generated")
    if not sql.strip().upper().startswith("SELECT"):
        return (False, f"Safety check failed: SQL must be SELECT, got: {sql[:50]}")
    dangerous = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER",
                 "TRUNCATE", "CREATE", "GRANT", "REVOKE"]
    for keyword in dangerous:
        if re.search(rf"\b{keyword}\b", sql, re.IGNORECASE):
            return (False, f"Dangerous keyword detected: {keyword}")
    return (True, "")


async def generate_validated_sql(question: str) -> tuple[str, bool, str]:
    sql = generate_sql(question)
    is_valid, error = validate_sql(sql)
    if not is_valid and error == "NOT_DB_QUERY":
        logger.info(f"Question not answerable from DB: {question[:50]}")
        return ("NOT_DB_QUERY", False, "NOT_DB_QUERY")
    if not is_valid:
        logger.warning(f"SQL validation failed: {error}")
        return ("", False, error)
    logger.info("SQL validated successfully")
    return (sql, True, "")


# Run with: uv run python -m rag.database_rag.nl_to_sql
if __name__ == "__main__":
    import asyncio

    test_questions = [
        "How many leave days does James Chen have?",
        "Show me all employees in the Engineering department",
        "Who has pending leave requests?",
        "Who reports to the VP of Engineering?",
        "What is the annual leave policy?",  # should return NOT_DB_QUERY
        "Show me employees on leave right now",
        "How many employees are in each department?",
    ]

    async def run_tests():
        for question in test_questions:
            print(f"\nQ: {question}")
            sql, is_valid, error = await generate_validated_sql(question)
            if sql == "NOT_DB_QUERY":
                print("→ NOT_DB_QUERY (routed to document RAG)")
            elif is_valid:
                print(f"→ SQL: {sql}")
            else:
                print(f"→ INVALID: {error}")

    asyncio.run(run_tests())
