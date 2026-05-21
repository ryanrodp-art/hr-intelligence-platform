from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, Enum, Text
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func
import enum

Base = declarative_base()


class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(String(20), unique=True, nullable=False)  # format: EMP-0001
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(200), unique=True, nullable=False)
    department = Column(String(100), nullable=False)
    role = Column(String(150), nullable=False)
    manager_id = Column(String(20), nullable=True)
    location = Column(String(100), nullable=False)
    hire_date = Column(Date, nullable=False)
    leave_balance = Column(Integer, nullable=False, default=25)
    status = Column(String(20), nullable=False, default="Active")
    created_at = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<Employee {self.employee_id}: {self.first_name} {self.last_name}>"


class LeaveRecord(Base):
    __tablename__ = "leave_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(String(20), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    leave_type = Column(String(50), nullable=False)   # Annual, Sick, Parental, Emergency, Unpaid
    status = Column(String(20), nullable=False, default="Pending")  # Pending, Approved, Rejected
    approved_by = Column(String(20), nullable=True)   # manager employee_id
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<LeaveRecord {self.employee_id}: {self.start_date} to {self.end_date}>"


class OrgChart(Base):
    __tablename__ = "org_chart"

    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(String(20), unique=True, nullable=False)
    manager_id = Column(String(20), nullable=True)
    level = Column(Integer, nullable=False)  # 1=CEO, 2=VP, 3=Director, 4=Manager, 5=Individual Contributor
    team = Column(String(100), nullable=False)
    department = Column(String(100), nullable=False)

    def __repr__(self):
        return f"<OrgChart {self.employee_id} -> {self.manager_id} (Level {self.level})>"


# ---------------------------------------------------------------------------
# Model reference
#
# Employee
#   Represents a single HR record for a person at the company. Stores identity,
#   role, department, location, leave balance, and employment status. The
#   employee_id (EMP-XXXX) is the primary business key used as a foreign key
#   reference in every other table. Used in Phase 1 (data layer), Phase 2
#   (leave management agent), and Phase 3 (RAG Q&A over employee data).
#
# LeaveRecord
#   Represents a single leave request submitted by an employee. Tracks the
#   date range, leave type, approval status, and the manager who approved it.
#   Related to Employee via employee_id (requester) and approved_by (manager).
#   Used in Phase 2 (leave management specialist agent) and Phase 4
#   (evaluation of leave-related agent responses).
#
# OrgChart
#   Represents the reporting hierarchy. Each row maps one employee to their
#   direct manager and captures their level in the org (1–5). Used by the
#   orchestrator agent to resolve reporting chains, identify managers for
#   approval workflows, and answer org-structure questions in Phase 3 (RAG)
#   and Phase 2 (leave approval routing).
# ---------------------------------------------------------------------------
