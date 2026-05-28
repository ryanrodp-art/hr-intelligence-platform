from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from config.settings import settings
import logging
from dataclasses import dataclass, field
import datetime

logger = logging.getLogger(__name__)


@dataclass
class QueryResult:
    success: bool
    rows: list[dict]
    row_count: int
    columns: list[str]
    error: str
    sql_executed: str


def execute_query(sql: str) -> QueryResult:
    if not sql or sql == "NOT_DB_QUERY":
        return QueryResult(
            success=False, rows=[], row_count=0,
            columns=[], error="No valid SQL to execute",
            sql_executed=sql,
        )
    try:
        engine = create_engine(settings.database_url)
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            columns = list(result.keys())
            raw_rows = result.fetchall()
            rows = []
            for raw_row in raw_rows:
                row = dict(zip(columns, raw_row))
                for key, value in row.items():
                    if isinstance(value, (datetime.date, datetime.datetime)):
                        row[key] = value.isoformat()
                rows.append(row)
        return QueryResult(
            success=True,
            rows=rows,
            row_count=len(rows),
            columns=columns,
            error="",
            sql_executed=sql,
        )
    except SQLAlchemyError as e:
        logger.error(f"SQL execution error: {e}")
        return QueryResult(
            success=False, rows=[], row_count=0,
            columns=[], error=str(e), sql_executed=sql,
        )
    except Exception as e:
        logger.error(f"Unexpected error executing SQL: {e}")
        return QueryResult(
            success=False, rows=[], row_count=0,
            columns=[], error=str(e), sql_executed=sql,
        )


def format_results_for_llm(result: QueryResult) -> str:
    if not result.success:
        return f"Query failed: {result.error}"
    if result.row_count == 0:
        return "No records found matching your query."
    lines = [f"Query returned {result.row_count} record(s):\n"]
    for i, row in enumerate(result.rows):
        lines.append(f"Record {i + 1}:")
        for column, value in row.items():
            lines.append(f"  {column}: {value}")
        lines.append("")
    return "\n".join(lines)


def get_database_stats() -> dict:
    queries = {
        "total_employees": "SELECT COUNT(*) FROM employees",
        "total_leave_records": "SELECT COUNT(*) FROM leave_records",
        "total_org_chart": "SELECT COUNT(*) FROM org_chart",
        "active_employees": "SELECT COUNT(*) FROM employees WHERE status = 'Active'",
        "pending_leave_requests": "SELECT COUNT(*) FROM leave_records WHERE status = 'Pending'",
    }
    stats = {}
    try:
        engine = create_engine(settings.database_url)
        with engine.connect() as conn:
            for key, sql in queries.items():
                row = conn.execute(text(sql)).fetchone()
                stats[key] = row[0] if row else 0
    except Exception as e:
        logger.error(f"Failed to fetch database stats: {e}")
    return stats


# Run with: uv run python -m rag.database_rag.executor
if __name__ == "__main__":
    test_queries = [
        "SELECT e.employee_id, e.first_name, e.last_name, e.leave_balance FROM employees e WHERE e.first_name ILIKE 'James' AND e.last_name ILIKE 'Chen' LIMIT 10",
        "SELECT e.department, COUNT(e.id) AS employee_count FROM employees e GROUP BY e.department LIMIT 10",
        "SELECT e.employee_id, e.first_name, e.last_name, lr.leave_type, lr.start_date, lr.end_date FROM employees e JOIN leave_records lr ON e.employee_id = lr.employee_id WHERE lr.status = 'Pending' LIMIT 10",
        "SELECT invalid_column FROM nonexistent_table LIMIT 10",
    ]

    for sql in test_queries:
        print(f"\nSQL: {sql[:60]}...")
        result = execute_query(sql)
        print(f"Success: {result.success}")
        print(f"Rows: {result.row_count}")
        if result.success:
            print(f"Columns: {result.columns}")
            if result.rows:
                print(f"First row: {result.rows[0]}")
        else:
            print(f"Error: {result.error}")
        print(f"\nFormatted:\n{format_results_for_llm(result)}")
        print("=" * 60)

    print("\n=== Database Stats ===")
    stats = get_database_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
