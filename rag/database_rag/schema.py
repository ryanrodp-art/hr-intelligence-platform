from sqlalchemy import create_engine, text
from config.settings import settings
import logging

logger = logging.getLogger(__name__)

DATABASE_SCHEMA_DESCRIPTION = """
ACME CORP HR DATABASE SCHEMA
============================

You have access to a PostgreSQL database with three tables
containing Acme Corp employee information.

TABLE 1: employees
Purpose: Contains all employee records for Acme Corp.
Columns:
  - id: INTEGER, primary key, auto-increment
  - employee_id: VARCHAR(20), unique identifier format "EMP-XXXX"
    Examples: EMP-0001, EMP-0023, EMP-0050
  - first_name: VARCHAR(100), employee first name
  - last_name: VARCHAR(100), employee last name
  - email: VARCHAR(200), format firstname.lastname@acmecorp.com
  - department: VARCHAR(100)
    Values: Engineering, HR, Sales, Marketing, Finance
  - role: VARCHAR(150), job title
    Examples: VP of Engineering, Senior Software Engineer,
    HR Manager, Account Executive, Financial Analyst
  - manager_id: VARCHAR(20), employee_id of direct manager
    (NULL for top-level employees like VPs)
  - location: VARCHAR(100)
    Values: Seattle, New York, London, Singapore, Sydney
  - hire_date: DATE, format YYYY-MM-DD
  - leave_balance: INTEGER, remaining leave days (0-30)
  - status: VARCHAR(20)
    Values: Active, Inactive, On Leave
  - created_at: TIMESTAMP

TABLE 2: leave_records
Purpose: Contains all leave requests and their approval status.
Columns:
  - id: INTEGER, primary key
  - employee_id: VARCHAR(20), references employees.employee_id
  - start_date: DATE, leave start date
  - end_date: DATE, leave end date
  - leave_type: VARCHAR(50)
    Values: Annual, Sick, Parental, Emergency, Unpaid
  - status: VARCHAR(20)
    Values: Pending, Approved, Rejected
  - approved_by: VARCHAR(20), employee_id of approving manager
    (NULL if Pending or Rejected)
  - reason: TEXT, optional reason for leave
  - created_at: TIMESTAMP

TABLE 3: org_chart
Purpose: Organisational hierarchy and team structure.
Columns:
  - id: INTEGER, primary key
  - employee_id: VARCHAR(20), references employees.employee_id
  - manager_id: VARCHAR(20), employee_id of direct manager
  - level: INTEGER, hierarchy level
    Values: 2=VP, 3=Director, 4=Manager, 5=Individual Contributor
  - team: VARCHAR(100)
    Examples: Platform Team, Backend Team, Enterprise Sales,
    People Operations, FP&A
  - department: VARCHAR(100)
    Values: Engineering, HR, Sales, Marketing, Finance

IMPORTANT SQL RULES:
- Always use table aliases: e for employees, lr for leave_records,
  o for org_chart
- employee_id format is always 'EMP-XXXX' with leading zeros
- For name searches use ILIKE for case-insensitive matching
- leave_balance is in days (integer)
- When joining tables use employee_id as the join key
- Always LIMIT results to 10 unless a specific number is requested
- Never use SELECT * — always select specific columns
- For date calculations use PostgreSQL date functions
"""


def get_schema_description() -> str:
    logger.info("Database schema context loaded")
    return DATABASE_SCHEMA_DESCRIPTION


def get_table_samples() -> dict:
    try:
        engine = create_engine(settings.database_url)
        with engine.connect() as conn:
            employees = [
                dict(row._mapping)
                for row in conn.execute(text(
                    "SELECT employee_id, first_name, last_name, department, "
                    "role, leave_balance, status FROM employees LIMIT 3"
                ))
            ]
            leave_records = [
                dict(row._mapping)
                for row in conn.execute(text(
                    "SELECT employee_id, leave_type, status, start_date, "
                    "end_date FROM leave_records LIMIT 3"
                ))
            ]
            org_chart = [
                dict(row._mapping)
                for row in conn.execute(text(
                    "SELECT employee_id, manager_id, level, team, department "
                    "FROM org_chart LIMIT 3"
                ))
            ]
        return {
            "employees": employees,
            "leave_records": leave_records,
            "org_chart": org_chart,
        }
    except Exception as exc:
        logger.error(f"Failed to fetch table samples: {exc}")
        return {}


def get_full_context() -> str:
    schema = DATABASE_SCHEMA_DESCRIPTION
    samples = get_table_samples()
    employees_samples = samples.get("employees", [])
    leave_samples = samples.get("leave_records", [])
    org_samples = samples.get("org_chart", [])
    return (
        f"{schema}\n"
        "SAMPLE DATA (for reference):\n"
        f"Employees sample: {employees_samples}\n"
        f"Leave records sample: {leave_samples}\n"
        f"Org chart sample: {org_samples}"
    )


# Run with: uv run python -m rag.database_rag.schema
if __name__ == "__main__":
    print("=== Schema Description ===")
    print(get_schema_description()[:500])
    print("\n=== Sample Data ===")
    samples = get_table_samples()
    for table, rows in samples.items():
        print(f"\n{table}: {len(rows)} sample rows")
        if rows:
            print(f"  First row: {rows[0]}")
