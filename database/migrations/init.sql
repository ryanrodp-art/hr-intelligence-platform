-- ---------------------------------------------------------------------------
-- init.sql — Initial schema migration for the HR Intelligence Platform
--
-- Creates all three core tables: employees, leave_records, org_chart.
-- Run this once against a fresh database before seeding or starting the app.
--
-- Usage:
--   psql -h localhost -p 5432 -U hr_user -d hr_platform -f database/migrations/init.sql
--   or via Docker:
--   docker exec -i hr_postgres psql -U hr_user -d hr_platform < database/migrations/init.sql
-- ---------------------------------------------------------------------------


-- Employees table
CREATE TABLE IF NOT EXISTS employees (
    id              SERIAL PRIMARY KEY,
    employee_id     VARCHAR(20)     UNIQUE NOT NULL,
    first_name      VARCHAR(100)    NOT NULL,
    last_name       VARCHAR(100)    NOT NULL,
    email           VARCHAR(200)    UNIQUE NOT NULL,
    department      VARCHAR(100)    NOT NULL,
    role            VARCHAR(150)    NOT NULL,
    manager_id      VARCHAR(20),
    location        VARCHAR(100)    NOT NULL,
    hire_date       DATE            NOT NULL,
    leave_balance   INTEGER         NOT NULL DEFAULT 25,
    status          VARCHAR(20)     NOT NULL DEFAULT 'Active',
    created_at      TIMESTAMP       DEFAULT NOW()
);


-- Leave records table
CREATE TABLE IF NOT EXISTS leave_records (
    id              SERIAL PRIMARY KEY,
    employee_id     VARCHAR(20)     NOT NULL,
    start_date      DATE            NOT NULL,
    end_date        DATE            NOT NULL,
    leave_type      VARCHAR(50)     NOT NULL,
    status          VARCHAR(20)     NOT NULL DEFAULT 'Pending',
    approved_by     VARCHAR(20),
    reason          TEXT,
    created_at      TIMESTAMP       DEFAULT NOW()
);


-- Org chart table
CREATE TABLE IF NOT EXISTS org_chart (
    id              SERIAL PRIMARY KEY,
    employee_id     VARCHAR(20)     UNIQUE NOT NULL,
    manager_id      VARCHAR(20),
    level           INTEGER         NOT NULL,
    team            VARCHAR(100)    NOT NULL,
    department      VARCHAR(100)    NOT NULL
);


-- ---------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------

-- employees
CREATE INDEX IF NOT EXISTS idx_employees_employee_id  ON employees (employee_id);
CREATE INDEX IF NOT EXISTS idx_employees_department   ON employees (department);
CREATE INDEX IF NOT EXISTS idx_employees_status       ON employees (status);
CREATE INDEX IF NOT EXISTS idx_employees_manager_id   ON employees (manager_id);

-- leave_records
CREATE INDEX IF NOT EXISTS idx_leave_records_employee_id  ON leave_records (employee_id);
CREATE INDEX IF NOT EXISTS idx_leave_records_status       ON leave_records (status);
CREATE INDEX IF NOT EXISTS idx_leave_records_start_date   ON leave_records (start_date);

-- org_chart
CREATE INDEX IF NOT EXISTS idx_org_chart_employee_id  ON org_chart (employee_id);
CREATE INDEX IF NOT EXISTS idx_org_chart_manager_id   ON org_chart (manager_id);
CREATE INDEX IF NOT EXISTS idx_org_chart_department   ON org_chart (department);
