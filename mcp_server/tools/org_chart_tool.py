from mcp_server.server import mcp
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from config.settings import settings
import logging

logger = logging.getLogger(__name__)


@mcp.tool
def get_org_chart(employee_id: str) -> str:
    """
    Get the organisational chart information for an Acme Corp
    employee — their manager, direct reports, team, and level.
    Use this tool when asked about reporting structure, who
    someone reports to, or who reports to them.
    employee_id must be in EMP-XXXX format e.g. EMP-0001.
    """
    if not employee_id.startswith("EMP-"):
        return f"Invalid employee_id format: '{employee_id}'. Must be in EMP-XXXX format e.g. EMP-0001."

    try:
        engine = create_engine(settings.database_url)
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT e.first_name, e.last_name, e.role, e.department, "
                    "       o.level, o.team, o.manager_id, "
                    "       m.first_name AS manager_first, "
                    "       m.last_name  AS manager_last, "
                    "       m.role       AS manager_role "
                    "FROM employees e "
                    "JOIN org_chart o ON e.employee_id = o.employee_id "
                    "LEFT JOIN employees m ON o.manager_id = m.employee_id "
                    "WHERE e.employee_id = :emp_id"
                ),
                {"emp_id": employee_id},
            ).fetchone()

            if row is None:
                return f"No org chart entry found for {employee_id}"

            first_name, last_name, role, department, level, team, manager_id, \
                manager_first, manager_last, manager_role = row

            reports = conn.execute(
                text(
                    "SELECT e.employee_id, e.first_name, e.last_name, e.role "
                    "FROM employees e "
                    "JOIN org_chart o ON e.employee_id = o.employee_id "
                    "WHERE o.manager_id = :emp_id "
                    "ORDER BY e.last_name"
                ),
                {"emp_id": employee_id},
            ).fetchall()

        if manager_id is None:
            manager_line = "Reports to: No manager (top level)"
        else:
            manager_line = f"Reports to: {manager_first} {manager_last} ({manager_role})"

        if reports:
            report_names = ", ".join(
                f"{r.first_name} {r.last_name} — {r.role}" for r in reports
            )
            reports_line = f"Direct reports ({len(reports)}): {report_names}"
        else:
            reports_line = "Direct reports: None"

        return "\n".join([
            f"{first_name} {last_name} — {role} ({department})",
            f"Team: {team} | Level: {level}",
            manager_line,
            reports_line,
        ])

    except SQLAlchemyError as e:
        logger.error("get_org_chart DB error for %s: %s", employee_id, e)
        return "Database error: unable to retrieve org chart"
