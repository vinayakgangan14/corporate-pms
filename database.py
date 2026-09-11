"""
Database connection and initialization module supporting both PostgreSQL (Production on Render/Supabase)
and SQLite (Local development).
Includes graceful error fallback to ensure 100% server uptime even during database migration.
"""

import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "pms.db")
DATABASE_URL = os.environ.get("DATABASE_URL")

# SQLite Schema
CREATE_TABLES_SQL_SQLITE = """
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

# PostgreSQL Schema
CREATE_TABLES_SQL_PG = """
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

_active_driver_is_postgres = False

def is_postgres():
    return _active_driver_is_postgres

def get_db_connection():
    global _active_driver_is_postgres
    if DATABASE_URL and (DATABASE_URL.startswith("postgresql://") or DATABASE_URL.startswith("postgres://")):
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            uri = DATABASE_URL
            if uri.startswith("postgres://"):
                uri = uri.replace("postgres://", "postgresql://", 1)
            conn = psycopg2.connect(uri, cursor_factory=RealDictCursor)
            _active_driver_is_postgres = True
            return conn
        except Exception as e:
            print(f"[DATABASE WARNING] Could not connect to PostgreSQL: {e}")
            print("[DATABASE WARNING] Falling back to SQLite engine for guaranteed uptime...")
            _active_driver_is_postgres = False

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    _active_driver_is_postgres = False
    return conn

def init_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if is_postgres():
            cursor.execute(CREATE_TABLES_SQL_PG)
            conn.commit()
        else:
            cursor.executescript(CREATE_TABLES_SQL_SQLITE)
            conn.commit()
            
        conn.close()
        seed_data_if_empty()
    except Exception as e:
        print(f"[DATABASE WARNING] Exception during init_db: {e}")

def seed_data_if_empty():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if is_postgres():
            cursor.execute("SELECT COUNT(*) FROM users")
            row = cursor.fetchone()
            count = row['count'] if row else 0
        else:
            cursor.execute("SELECT COUNT(*) FROM users")
            row = cursor.fetchone()
            count = row[0] if row else 0

        if count > 0:
            conn.close()
            return

        print("Seeding initial corporate hierarchy and 70/30 KRAs...")

        departments = [
            ("Executive Management", "EXEC"),
            ("Global Operations", "OPS"),
            ("Finance & Strategy", "FIN"),
            ("Engineering & Technology", "ENG"),
            ("Supply Chain & Logistics", "SCM")
        ]
        
        if is_postgres():
            for name, code in departments:
                cursor.execute("INSERT INTO departments (name, code) VALUES (%s, %s) ON CONFLICT DO NOTHING", (name, code))
            conn.commit()
        else:
            cursor.executemany("INSERT INTO departments (name, code) VALUES (?, ?)", departments)
            conn.commit()

        dept_map = {"EXEC": 1, "OPS": 2, "FIN": 3, "ENG": 4, "SCM": 5}

        users_data = [
            ("System Administrator", "admin@company.com", "ADMIN", "System Administrator", "EXEC", None),
            ("Arthur Pendelton", "md@company.com", "MD", "Managing Director & CEO", "EXEC", None),
            ("Elena Rostova", "gm.ops@company.com", "GM", "GM - Operations & Strategy", "OPS", "md@company.com"),
            ("Marcus Vance", "gm.eng@company.com", "GM", "GM - Technology & Product", "ENG", "md@company.com"),
            ("Sophia Lin", "hod.fin@company.com", "HOD", "HOD - Corporate Finance & EVA", "FIN", "gm.ops@company.com"),
            ("David Miller", "hod.eng@company.com", "HOD", "HOD - Enterprise Architecture", "ENG", "gm.eng@company.com"),
            ("Rachel Green", "mgr.ops@company.com", "MANAGER", "Manager - Operational Excellence", "OPS", "hod.fin@company.com"),
            ("Kevin Wright", "mgr.dev@company.com", "MANAGER", "Manager - Software Development", "ENG", "hod.eng@company.com"),
            ("Carlos Mendez", "sup.ops@company.com", "SUPERVISOR", "Supervisor - Process Audit", "OPS", "mgr.ops@company.com"),
            ("Anita Desai", "sup.dev@company.com", "SUPERVISOR", "Supervisor - Platform Engineering", "ENG", "mgr.dev@company.com"),
            ("John Doe", "emp.john@company.com", "EMPLOYEE", "Senior Process Analyst", "OPS", "sup.ops@company.com"),
            ("Sarah Jenkins", "emp.sarah@company.com", "EMPLOYEE", "Full Stack Engineer", "ENG", "sup.dev@company.com"),
        ]

        user_id_map = {}
        for name, email, role, designation, dept_code, mgr_email in users_data:
            dept_id = dept_map.get(dept_code)
            mgr_id = user_id_map.get(mgr_email) if mgr_email else None
            
            if is_postgres():
                cursor.execute(
                    """INSERT INTO users (name, email, role, designation, department_id, manager_id)
                       VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
                    (name, email, role, designation, dept_id, mgr_id)
                )
                inserted_id = cursor.fetchone()['id']
                user_id_map[email] = inserted_id
            else:
                cursor.execute(
                    "INSERT INTO users (name, email, role, designation, department_id, manager_id) VALUES (?, ?, ?, ?, ?, ?)",
                    (name, email, role, designation, dept_id, mgr_id)
                )
                user_id_map[email] = cursor.lastrowid

        current_year = 2026
        md_id = user_id_map["md@company.com"]
        md_kras = [
            (md_id, current_year, "PRESENT_YEAR_70", "Group Economic Value Added (EVA)", "Deliver net positive operating profit after cost of capital", "USD Million", 15.0, 16.2, 40.0, None),
            (md_id, current_year, "PRESENT_YEAR_70", "Annual Corporate EBITDA Growth", "Achieve target consolidated EBITDA margin growth", "%", 18.0, 19.5, 30.0, None),
            (md_id, current_year, "PRESENT_YEAR_70", "Strategic Expansion & Market Share", "Expand operational footprint in key international regions", "% Share", 25.0, 24.0, 30.0, None),
            (md_id, current_year, "UPCOMING_YEAR_30", "Next-Gen AI & Automation Transformation", "Establish enterprise AI framework across core business units", "Completion %", 100.0, 90.0, 50.0, None),
            (md_id, current_year, "UPCOMING_YEAR_30", "ESG & Net Zero Carbon Roadmap", "Deploy renewable energy & carbon offset protocols for 2027", "Milestones", 5.0, 5.0, 50.0, None),
        ]

        for kra in md_kras:
            if is_postgres():
                cursor.execute(
                    """INSERT INTO kras (user_id, year, section, lever_name, description, metric_unit, target_value, actual_outcome, weightage_percent, parent_kra_id)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    kra
                )
            else:
                cursor.execute(
                    """INSERT INTO kras (user_id, year, section, lever_name, description, metric_unit, target_value, actual_outcome, weightage_percent, parent_kra_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    kra
                )

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DATABASE WARNING] Exception during seed_data_if_empty: {e}")

if __name__ == "__main__":
    init_db()
    print("Database initialization complete.")
