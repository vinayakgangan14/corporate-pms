"""
Database models and Pydantic schemas for Corporate Performance Management System (PMS)
"""

from dataclasses import dataclass
from typing import List, Optional
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

# SQL Schema Definitions for SQLite initialization
CREATE_TABLES_SQL = """
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (department_id) REFERENCES departments(id),
    FOREIGN KEY (manager_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS kras (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    year INTEGER NOT NULL,
    section TEXT NOT NULL, -- PRESENT_YEAR_70 or UPCOMING_YEAR_30
    lever_name TEXT NOT NULL,
    description TEXT,
    metric_unit TEXT NOT NULL, -- %, USD, Ratio, Units, Score
    target_value REAL NOT NULL,
    actual_outcome REAL DEFAULT 0.0,
    weightage_percent REAL NOT NULL, -- Weightage within section (must sum to 100%)
    parent_kra_id INTEGER, -- Cascading link to parent KRA (e.g., Manager's or GM's KRA)
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
    present_year_score REAL DEFAULT 0.0,   -- Raw score out of 100
    upcoming_year_score REAL DEFAULT 0.0,  -- Raw score out of 100
    composite_score REAL DEFAULT 0.0,      -- (Present * 0.70) + (Upcoming * 0.30)
    performance_band TEXT DEFAULT 'Not Rated',
    grade TEXT DEFAULT 'N/A',
    self_comments TEXT,
    manager_comments TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(user_id, year)
);
"""
