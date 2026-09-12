"""
Database models and SQL schema definitions for Corporate Performance Management System (PMS)
Includes dynamic Administrator Section Weightage Settings.
"""

from enum import Enum

class UserRole(str, Enum):
    ADMIN = "ADMIN"
    MD = "MD"                  # Managing Director
    GM = "GM"                  # General Manager
    HOD = "HOD"                # Head of Department
    MANAGER = "MANAGER"        # Manager
    SUPERVISOR = "SUPERVISOR"  # Supervisor
    EMPLOYEE = "EMPLOYEE"      # Staff / Individual Contributor

class KRASection(str, Enum):
    PRESENT_YEAR_70 = "PRESENT_YEAR_70"
    UPCOMING_YEAR_30 = "UPCOMING_YEAR_30"

class AppraisalStatus(str, Enum):
    DRAFT = "DRAFT"
    SUBMITTED_SELF = "SUBMITTED_SELF"
    MANAGER_REVIEWED = "MANAGER_REVIEWED"
    APPROVED = "APPROVED"

CREATE_TABLES_SQL_SQLITE = """
CREATE TABLE IF NOT EXISTS system_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS role_settings (
    role TEXT PRIMARY KEY,
    section1_weight REAL NOT NULL DEFAULT 70.0,
    section2_weight REAL NOT NULL DEFAULT 30.0
);

CREATE TABLE IF NOT EXISTS departments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    code TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL,
    designation TEXT NOT NULL,
    department_id INTEGER,
    manager_id INTEGER,
    sec1_weight REAL,
    sec2_weight REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (department_id) REFERENCES departments(id),
    FOREIGN KEY (manager_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS kras (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    year INTEGER NOT NULL,
    section TEXT NOT NULL,
    lever_name TEXT NOT NULL,
    description TEXT,
    metric_unit TEXT NOT NULL,
    target_value REAL NOT NULL,
    actual_outcome REAL DEFAULT 0.0,
    weightage_percent REAL NOT NULL,
    parent_kra_id INTEGER,
    self_rating_percent REAL DEFAULT 0.0,
    manager_rating_percent REAL DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (parent_kra_id) REFERENCES kras(id)
);

CREATE TABLE IF NOT EXISTS appraisals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    year INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'DRAFT',
    present_year_score REAL DEFAULT 0.0,
    upcoming_year_score REAL DEFAULT 0.0,
    composite_score REAL DEFAULT 0.0,
    performance_band TEXT DEFAULT 'Not Rated',
    grade TEXT DEFAULT 'N/A',
    self_comments TEXT,
    manager_comments TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(user_id, year)
);
"""

CREATE_TABLES_SQL_PG = """
CREATE TABLE IF NOT EXISTS system_settings (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS role_settings (
    role VARCHAR(50) PRIMARY KEY,
    section1_weight DOUBLE PRECISION NOT NULL DEFAULT 70.0,
    section2_weight DOUBLE PRECISION NOT NULL DEFAULT 30.0
);

CREATE TABLE IF NOT EXISTS departments (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    code VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    role VARCHAR(50) NOT NULL,
    designation VARCHAR(255) NOT NULL,
    department_id INTEGER REFERENCES departments(id),
    manager_id INTEGER REFERENCES users(id),
    sec1_weight DOUBLE PRECISION,
    sec2_weight DOUBLE PRECISION,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS kras (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    year INTEGER NOT NULL,
    section VARCHAR(50) NOT NULL,
    lever_name VARCHAR(255) NOT NULL,
    description TEXT,
    metric_unit VARCHAR(50) NOT NULL,
    target_value DOUBLE PRECISION NOT NULL,
    actual_outcome DOUBLE PRECISION DEFAULT 0.0,
    weightage_percent DOUBLE PRECISION NOT NULL,
    parent_kra_id INTEGER REFERENCES kras(id),
    self_rating_percent DOUBLE PRECISION DEFAULT 0.0,
    manager_rating_percent DOUBLE PRECISION DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS appraisals (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    year INTEGER NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'DRAFT',
    present_year_score DOUBLE PRECISION DEFAULT 0.0,
    upcoming_year_score DOUBLE PRECISION DEFAULT 0.0,
    composite_score DOUBLE PRECISION DEFAULT 0.0,
    performance_band VARCHAR(100) DEFAULT 'Not Rated',
    grade VARCHAR(10) DEFAULT 'N/A',
    self_comments TEXT,
    manager_comments TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, year)
);
"""
