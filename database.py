"""
Database connection and initialization module supporting both PostgreSQL (Production on Render/Supabase)
and SQLite (Local development).
Supports Administrator Configurable Section Weightages & Settings.
"""

import os
import sqlite3
from typing import Optional, List, Dict, Any
from models import CREATE_TABLES_SQL_SQLITE, CREATE_TABLES_SQL_PG

DB_PATH = os.path.join(os.path.dirname(__file__), "pms.db")
SUPABASE_URL = "postgresql://postgres.rstyhyuuyepfsgduqjvz:eJPNtR7j6XDQgMbj@aws-0-ap-northeast-2.pooler.supabase.com:6543/postgres"

_active_driver_is_postgres = False

def is_postgres():
    return _active_driver_is_postgres

def get_db_connection():
    global _active_driver_is_postgres
    db_url = os.environ.get("DATABASE_URL") or SUPABASE_URL
    if db_url and (db_url.startswith("postgresql://") or db_url.startswith("postgres://")):
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            uri = db_url
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
            # Migration checks for postgres
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS sec1_weight DOUBLE PRECISION;")
                cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS sec2_weight DOUBLE PRECISION;")
                conn.commit()
            except Exception as me:
                conn.rollback()
                print(f"[DATABASE MIGRATION NOTICE] Postgres columns already exist or migrated: {me}")
        else:
            cursor.executescript(CREATE_TABLES_SQL_SQLITE)
            conn.commit()
            # Migration checks for SQLite
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN sec1_weight REAL;")
            except Exception:
                pass
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN sec2_weight REAL;")
            except Exception:
                pass
            conn.commit()
            
        conn.close()
        init_default_settings()
        init_default_role_settings()
        seed_data_if_empty()
    except Exception as e:
        print(f"[DATABASE WARNING] Exception during init_db: {e}")

def init_default_settings():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    defaults = [
        ("section1_weightage_percent", "70.0"),
        ("section2_weightage_percent", "30.0")
    ]
    
    if is_postgres():
        for key, val in defaults:
            cursor.execute("INSERT INTO system_settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING", (key, val))
    else:
        for key, val in defaults:
            cursor.execute("INSERT OR IGNORE INTO system_settings (key, value) VALUES (?, ?)", (key, val))
            
    conn.commit()
    conn.close()

def init_default_role_settings():
    """Initializes default section weightages per organizational position / role."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    role_defaults = [
        ("MD", 70.0, 30.0),
        ("GM", 50.0, 50.0),
        ("HOD", 40.0, 60.0),
        ("MANAGER", 30.0, 70.0),
        ("SUPERVISOR", 30.0, 70.0),
        ("EMPLOYEE", 30.0, 70.0),
        ("ADMIN", 70.0, 30.0)
    ]
    
    if is_postgres():
        for r, w1, w2 in role_defaults:
            cursor.execute(
                "INSERT INTO role_settings (role, section1_weight, section2_weight) VALUES (%s, %s, %s) ON CONFLICT (role) DO NOTHING",
                (r, w1, w2)
            )
    else:
        for r, w1, w2 in role_defaults:
            cursor.execute(
                "INSERT OR IGNORE INTO role_settings (role, section1_weight, section2_weight) VALUES (?, ?, ?)",
                (r, w1, w2)
            )
            
    conn.commit()
    conn.close()

def get_role_settings() -> dict:
    """Returns mapping of all roles to their configured section weightages."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT role, section1_weight, section2_weight FROM role_settings")
    rows = cursor.fetchall()
    conn.close()
    
    results = {}
    for r in rows:
        if is_postgres():
            results[r['role']] = {
                "section1_weight": float(r['section1_weight']),
                "section2_weight": float(r['section2_weight'])
            }
        else:
            results[r[0]] = {
                "section1_weight": float(r[1]),
                "section2_weight": float(r[2])
            }
            
    # Ensure standard defaults if any role missing
    defaults = {
        "MD": {"section1_weight": 70.0, "section2_weight": 30.0},
        "GM": {"section1_weight": 50.0, "section2_weight": 50.0},
        "HOD": {"section1_weight": 40.0, "section2_weight": 60.0},
        "MANAGER": {"section1_weight": 30.0, "section2_weight": 70.0},
        "SUPERVISOR": {"section1_weight": 30.0, "section2_weight": 70.0},
        "EMPLOYEE": {"section1_weight": 30.0, "section2_weight": 70.0},
        "ADMIN": {"section1_weight": 70.0, "section2_weight": 30.0}
    }
    for k, v in defaults.items():
        if k not in results:
            results[k] = v
            
    return results

def update_role_setting(role_name: str, sec1: float, sec2: float):
    """Updates Section 1 & Section 2 weightages for a specific position / role."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if is_postgres():
        cursor.execute(
            """INSERT INTO role_settings (role, section1_weight, section2_weight) 
               VALUES (%s, %s, %s) 
               ON CONFLICT (role) DO UPDATE SET section1_weight = EXCLUDED.section1_weight, section2_weight = EXCLUDED.section2_weight""",
            (role_name, sec1, sec2)
        )
    else:
        cursor.execute(
            """INSERT INTO role_settings (role, section1_weight, section2_weight) 
               VALUES (?, ?, ?) 
               ON CONFLICT(role) DO UPDATE SET section1_weight = excluded.section1_weight, section2_weight = excluded.section2_weight""",
            (role_name, sec1, sec2)
        )
        
    conn.commit()
    conn.close()

def get_user_effective_weightages(user_id: int) -> dict:
    """
    Fetches the effective Section 1 and Section 2 weightages for a given user.
    Prioritizes individual user overrides (sec1_weight, sec2_weight), then position/role default, then 70/30 system fallback.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if is_postgres():
        cursor.execute("SELECT role, sec1_weight, sec2_weight FROM users WHERE id = %s", (user_id,))
        row = cursor.fetchone()
    else:
        cursor.execute("SELECT role, sec1_weight, sec2_weight FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        
    conn.close()
    
    if not row:
        return {"section1_weight": 70.0, "section2_weight": 30.0, "source": "default", "role": "EMPLOYEE"}
        
    role = row['role'] if is_postgres() else row[0]
    sec1_override = row['sec1_weight'] if is_postgres() else row[1]
    sec2_override = row['sec2_weight'] if is_postgres() else row[2]
    
    if sec1_override is not None and sec2_override is not None:
        return {
            "section1_weight": float(sec1_override),
            "section2_weight": float(sec2_override),
            "source": "custom_override",
            "role": role
        }
        
    role_settings = get_role_settings()
    role_weight = role_settings.get(role, {"section1_weight": 70.0, "section2_weight": 30.0})
    
    return {
        "section1_weight": float(role_weight["section1_weight"]),
        "section2_weight": float(role_weight["section2_weight"]),
        "source": "position_role",
        "role": role
    }

def update_user_custom_weightages(user_id: int, sec1: Optional[float], sec2: Optional[float]):
    """Sets custom section weightages for an individual user, or clears them to inherit role default if None."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if is_postgres():
        cursor.execute("UPDATE users SET sec1_weight = %s, sec2_weight = %s WHERE id = %s", (sec1, sec2, user_id))
    else:
        cursor.execute("UPDATE users SET sec1_weight = ?, sec2_weight = ? WHERE id = ?", (sec1, sec2, user_id))
        
    conn.commit()
    conn.close()

def get_system_settings():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT key, value FROM system_settings")
    rows = cursor.fetchall()
    conn.close()
    
    settings = {"section1_weightage": 70.0, "section2_weightage": 30.0}
    for row in rows:
        if is_postgres():
            k, v = row['key'], row['value']
        else:
            k, v = row[0], row[1]
            
        if k == "section1_weightage_percent":
            settings["section1_weightage"] = float(v)
        elif k == "section2_weightage_percent":
            settings["section2_weightage"] = float(v)
            
    return settings

def update_system_settings(sec1_weight: float, sec2_weight: float):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if is_postgres():
        cursor.execute("UPDATE system_settings SET value = %s WHERE key = 'section1_weightage_percent'", (str(sec1_weight),))
        cursor.execute("UPDATE system_settings SET value = %s WHERE key = 'section2_weightage_percent'", (str(sec2_weight),))
    else:
        cursor.execute("UPDATE system_settings SET value = ? WHERE key = 'section1_weightage_percent'", (str(sec1_weight),))
        cursor.execute("UPDATE system_settings SET value = ? WHERE key = 'section2_weightage_percent'", (str(sec2_weight),))
        
    conn.commit()
    conn.close()

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
            ("Chetan Sundan", "chetan.sundan@company.com", "MANAGER", "Store Manager", "SCM", "gm.ops@company.com"),
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
