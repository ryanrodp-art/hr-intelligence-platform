import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config.settings import settings
from database.models import Base, Employee, LeaveRecord, OrgChart

CSV_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "database", "seed_data")


def nan_to_none(value):
    """Convert pandas NaN/NaT to None for SQLAlchemy."""
    if pd.isna(value):
        return None
    return value


def seed_employees(session):
    if session.query(Employee).count() > 0:
        print("  employees table already has data — skipping")
        return 0

    df = pd.read_csv(os.path.join(CSV_DIR, "employees.csv"))
    records = []
    for _, row in df.iterrows():
        records.append(Employee(
            employee_id=row["employee_id"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            email=row["email"],
            department=row["department"],
            role=row["role"],
            manager_id=nan_to_none(row["manager_id"]),
            location=row["location"],
            hire_date=pd.to_datetime(row["hire_date"]).date(),
            leave_balance=int(row["leave_balance"]),
            status=row["status"],
        ))
    session.add_all(records)
    session.flush()
    count = len(records)
    print(f"  ✓ Inserted {count} employees")
    return count


def seed_leave_records(session):
    if session.query(LeaveRecord).count() > 0:
        print("  leave_records table already has data — skipping")
        return 0

    df = pd.read_csv(os.path.join(CSV_DIR, "leave_records.csv"))
    records = []
    for _, row in df.iterrows():
        records.append(LeaveRecord(
            employee_id=row["employee_id"],
            start_date=pd.to_datetime(row["start_date"]).date(),
            end_date=pd.to_datetime(row["end_date"]).date(),
            leave_type=row["leave_type"],
            status=row["status"],
            approved_by=nan_to_none(row["approved_by"]),
            reason=nan_to_none(row["reason"]),
        ))
    session.add_all(records)
    session.flush()
    count = len(records)
    print(f"  ✓ Inserted {count} leave records")
    return count


def seed_org_chart(session):
    if session.query(OrgChart).count() > 0:
        print("  org_chart table already has data — skipping")
        return 0

    df = pd.read_csv(os.path.join(CSV_DIR, "org_chart.csv"))
    records = []
    for _, row in df.iterrows():
        records.append(OrgChart(
            employee_id=row["employee_id"],
            manager_id=nan_to_none(row["manager_id"]),
            level=int(row["level"]),
            team=row["team"],
            department=row["department"],
        ))
    session.add_all(records)
    session.flush()
    count = len(records)
    print(f"  ✓ Inserted {count} org chart rows")
    return count


def main():
    print(f"Connecting to: {settings.database_url}")

    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        emp_count = seed_employees(session)
        leave_count = seed_leave_records(session)
        org_count = seed_org_chart(session)

        session.commit()

        print()
        print("=== Seed Complete ===")
        print(f"  Employees:     {emp_count}")
        print(f"  Leave Records: {leave_count}")
        print(f"  Org Chart:     {org_count}")
        print(f"  Total:         {emp_count + leave_count + org_count} rows inserted")

    except Exception as e:
        session.rollback()
        print(f"\nError: {e}")
        sys.exit(1)

    finally:
        session.close()


if __name__ == "__main__":
    main()
