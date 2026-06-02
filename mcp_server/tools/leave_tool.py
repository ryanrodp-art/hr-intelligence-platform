from mcp_server.server import mcp
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from config.settings import settings
import datetime
import logging

logger = logging.getLogger(__name__)


@mcp.tool
def check_leave_balance(employee_id: str) -> str:
    """
    Check the current leave balance for an Acme Corp employee.
    Use this tool when an employee asks how many leave days they
    have remaining. Returns the employee name and leave balance
    in days. employee_id must be in format EMP-XXXX e.g. EMP-0001.
    """
    if not employee_id.startswith("EMP-"):
        return f"Invalid employee_id format: '{employee_id}'. Must be in EMP-XXXX format e.g. EMP-0001."

    try:
        engine = create_engine(settings.database_url)
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT first_name, last_name, leave_balance, status "
                    "FROM employees WHERE employee_id = :emp_id"
                ),
                {"emp_id": employee_id},
            )
            row = result.fetchone()

        if row is None:
            return f"No employee found with ID {employee_id}"

        first_name, last_name, leave_balance, status = row
        return (
            f"{first_name} {last_name} has {leave_balance} days of leave "
            f"remaining. Status: {status}"
        )
    except SQLAlchemyError as e:
        logger.error("check_leave_balance DB error for %s: %s", employee_id, e)
        return "Database error: unable to retrieve leave balance"


@mcp.tool
def submit_leave_request(
    employee_id: str,
    start_date: str,
    end_date: str,
    leave_type: str = "Annual",
    reason: str = "",
) -> str:
    """
    Submit a new leave request for an Acme Corp employee.
    This tool WRITES a new leave record to the database.
    Use when an employee explicitly asks to submit, book, or
    request leave. employee_id must be in EMP-XXXX format.
    start_date and end_date must be in YYYY-MM-DD format.
    leave_type must be one of: Annual, Sick, Parental,
    Emergency, Unpaid. Default is Annual.
    """
    if not employee_id.startswith("EMP-"):
        return f"Invalid employee_id format: '{employee_id}'. Must be in EMP-XXXX format e.g. EMP-0001."

    valid_leave_types = ["Annual", "Sick", "Parental", "Emergency", "Unpaid"]
    if leave_type not in valid_leave_types:
        return f"Invalid leave_type '{leave_type}'. Must be one of: {', '.join(valid_leave_types)}."

    try:
        start = datetime.date.fromisoformat(start_date)
        end = datetime.date.fromisoformat(end_date)
    except ValueError as e:
        return f"Invalid date format: {e}. Dates must be in YYYY-MM-DD format."

    if end < start:
        return f"end_date ({end_date}) must be on or after start_date ({start_date})."

    days = (end - start).days + 1

    try:
        engine = create_engine(settings.database_url)
        with engine.begin() as conn:
            exists = conn.execute(
                text("SELECT employee_id FROM employees WHERE employee_id = :emp_id"),
                {"emp_id": employee_id},
            ).fetchone()

            if exists is None:
                return f"No employee found with ID {employee_id}"

            conn.execute(
                text(
                    "INSERT INTO leave_records "
                    "(employee_id, start_date, end_date, leave_type, status, reason) "
                    "VALUES (:employee_id, :start_date, :end_date, :leave_type, 'Pending', :reason)"
                ),
                {
                    "employee_id": employee_id,
                    "start_date": start_date,
                    "end_date": end_date,
                    "leave_type": leave_type,
                    "reason": reason,
                },
            )

        return (
            f"Leave request submitted successfully for {employee_id}. "
            f"Dates: {start_date} to {end_date} ({days} day(s)). "
            f"Type: {leave_type}. Status: Pending. "
            f"Your manager will be notified for approval."
        )
    except Exception as e:
        logger.error("submit_leave_request error for %s: %s", employee_id, e)
        return f"Failed to submit leave request: {e}"
