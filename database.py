"""
Database connection and initialization module supporting both PostgreSQL (Production on Render/Supabase)
and SQLite (Local development).
Supports Administrator Configurable Section Weightages & Settings.
"""

import os
import sqlite3
import hashlib
import secrets
from typing import Optional, List, Dict, Any
from models import CREATE_TABLES_SQL_SQLITE, CREATE_TABLES_SQL_PG

DB_PATH = os.path.join(os.path.dirname(__file__), "pms.db")
SUPABASE_URL = "postgresql://postgres.rstyhyuuyepfsgduqjvz:eJPNtR7j6XDQgMbj@aws-0-ap-northeast-2.pooler.supabase.com:6543/postgres?sslmode=require"

import time

_active_driver_is_postgres = False
_last_postgres_error = None
_pg_pool = None

_role_settings_cache = None
_role_settings_cache_time = 0

_system_settings_cache = None
_system_settings_cache_time = 0

def invalidate_settings_caches():
    global _role_settings_cache, _system_settings_cache
    _role_settings_cache = None
    _system_settings_cache = None

def is_postgres():
    return _active_driver_is_postgres

def get_db_status():
    return {
        "is_postgres": _active_driver_is_postgres,
        "last_error": _last_postgres_error,
        "active_engine": "PostgreSQL (Supabase)" if _active_driver_is_postgres else "SQLite"
    }

def hash_password(password: str, salt: str = None) -> str:
    """Hashes a password with PBKDF2-HMAC-SHA256."""
    if not password:
        password = "password123"
    if not salt:
        salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    )
    return f"{salt}${key.hex()}"

def verify_password(password: str, password_hash: str) -> bool:
    """Verifies a password against a stored PBKDF2 hash."""
    if not password or not password_hash:
        return False
    if '$' not in password_hash:
        return password == password_hash
    try:
        salt, stored_key = password_hash.split('$', 1)
        computed_key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        ).hex()
        return secrets.compare_digest(stored_key, computed_key)
    except Exception:
        return False

def generate_username(name: str, email: str) -> str:
    """Generates a clean, unique username from name or email."""
    if email and "@" in email:
        base = email.split("@")[0].lower()
    elif name:
        base = name.lower().replace(" ", ".")
    else:
        base = "user"
    cleaned = "".join(c for c in base if c.isalnum() or c in "._-")
    return cleaned or "user"

class PooledConnectionWrapper:
    """Wrapper around a psycopg2 pooled connection that returns it to the pool on close()."""
    def __init__(self, conn, pool):
        self._conn = conn
        self._pool = pool
        self.closed = False

    def cursor(self, *args, **kwargs):
        return self._conn.cursor(*args, **kwargs)

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        if not self.closed and self._pool:
            try:
                self._pool.putconn(self._conn)
            except Exception:
                pass
            self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()

    def __getattr__(self, name):
        return getattr(self._conn, name)

def get_db_connection():
    global _active_driver_is_postgres, _last_postgres_error, _pg_pool
    env_url = os.environ.get("DATABASE_URL")
    if env_url and ("supabase.co" in env_url or "supabase.com" in env_url):
        db_url = env_url
    else:
        db_url = SUPABASE_URL

    if db_url and (db_url.startswith("postgresql://") or db_url.startswith("postgres://")):
        try:
            import psycopg2
            from psycopg2.pool import ThreadedConnectionPool
            from psycopg2.extras import RealDictCursor

            uri = db_url
            if uri.startswith("postgres://"):
                uri = uri.replace("postgres://", "postgresql://", 1)
            if "sslmode" not in uri:
                uri += "&sslmode=require" if "?" in uri else "?sslmode=require"

            if _pg_pool is None or getattr(_pg_pool, 'closed', False):
                _pg_pool = ThreadedConnectionPool(
                    minconn=2,
                    maxconn=15,
                    dsn=uri,
                    cursor_factory=RealDictCursor
                )
                print("[DATABASE POOL] PostgreSQL ThreadedConnectionPool initialized (min=2, max=15).")

            raw_conn = _pg_pool.getconn()
            _active_driver_is_postgres = True
            _last_postgres_error = None
            return PooledConnectionWrapper(raw_conn, _pg_pool)
        except Exception as e:
            _last_postgres_error = str(e)
            print(f"[DATABASE WARNING] Could not connect to PostgreSQL pool: {e}")
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
                cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS username VARCHAR(100) UNIQUE;")
                cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255);")
                cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS sec1_weight DOUBLE PRECISION;")
                cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS sec2_weight DOUBLE PRECISION;")
                conn.commit()
            except Exception as me:
                conn.rollback()
                print(f"[DATABASE MIGRATION NOTICE] Postgres columns already exist or migrated: {me}")
            
            # Sync Postgres primary key sequence counters to highest ID
            try:
                cursor.execute("SELECT setval('departments_id_seq', (SELECT COALESCE(MAX(id), 1) FROM departments));")
                cursor.execute("SELECT setval('users_id_seq', (SELECT COALESCE(MAX(id), 1) FROM users));")
                conn.commit()
            except Exception as se:
                conn.rollback()
                print(f"[DATABASE NOTICE] Postgres sequence sync notice: {se}")
        else:
            cursor.executescript(CREATE_TABLES_SQL_SQLITE)
            conn.commit()
            # Migration checks for SQLite
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN username TEXT;")
            except Exception:
                pass
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN password_hash TEXT;")
            except Exception:
                pass
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
        ensure_user_credentials()
    except Exception as e:
        print(f"[DATABASE WARNING] Exception during init_db: {e}")

def ensure_user_credentials():
    """Migrates and ensures all existing users have usernames and password hashes."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT id, name, email, username, password_hash FROM users")
        rows = cursor.fetchall()
        
        for r in rows:
            if is_postgres():
                u_id, u_name, u_email, u_uname, u_pass = r['id'], r['name'], r['email'], r['username'], r['password_hash']
            else:
                u_id, u_name, u_email, u_uname, u_pass = r[0], r[1], r[2], r[3], r[4]
                
            new_uname = u_uname if u_uname else generate_username(u_name, u_email)
            new_pass = u_pass if u_pass else hash_password("pms123")
            
            if not u_uname or not u_pass:
                if is_postgres():
                    cursor.execute(
                        "UPDATE users SET username = %s, password_hash = %s WHERE id = %s",
                        (new_uname, new_pass, u_id)
                    )
                else:
                    cursor.execute(
                        "UPDATE users SET username = ?, password_hash = ? WHERE id = ?",
                        (new_uname, new_pass, u_id)
                    )
        conn.commit()
    except Exception as me:
        conn.rollback()
        print(f"[DATABASE NOTICE] Credentials migration notice: {me}")
    finally:
        conn.close()

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
                "INSERT INTO role_settings (role, section1_weight, section2_weight) VALUES (%s, %s, %s) ON CONFLICT (role) DO UPDATE SET section1_weight = EXCLUDED.section1_weight, section2_weight = EXCLUDED.section2_weight",
                (r, w1, w2)
            )
    else:
        for r, w1, w2 in role_defaults:
            cursor.execute(
                "INSERT INTO role_settings (role, section1_weight, section2_weight) VALUES (?, ?, ?) ON CONFLICT(role) DO UPDATE SET section1_weight = excluded.section1_weight, section2_weight = excluded.section2_weight",
                (r, w1, w2)
            )
            
    conn.commit()
    conn.close()

def get_role_settings(conn=None) -> dict:
    """Returns mapping of all roles to their configured section weightages with 60s TTL cache."""
    global _role_settings_cache, _role_settings_cache_time
    now = time.time()
    if conn is None and _role_settings_cache is not None and (now - _role_settings_cache_time < 60):
        return _role_settings_cache

    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True
    cursor = conn.cursor()
    
    cursor.execute("SELECT role, section1_weight, section2_weight FROM role_settings")
    rows = cursor.fetchall()
    if should_close:
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
            
    _role_settings_cache = results
    _role_settings_cache_time = now
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
    invalidate_settings_caches()

def get_user_effective_weightages(user_id: int, conn=None, role_settings=None, user_row=None) -> dict:
    """
    Fetches the effective Section 1 and Section 2 weightages for a given user.
    Prioritizes individual user overrides (sec1_weight, sec2_weight), then position/role default, then 70/30 system fallback.
    Accepts optional pre-fetched conn, role_settings, or user_row for zero N+1 database connection overhead.
    """
    should_close = False
    active_conn = conn
    
    if user_row is not None:
        if isinstance(user_row, dict):
            role = user_row.get('role', 'EMPLOYEE')
            sec1_override = user_row.get('sec1_weight')
            sec2_override = user_row.get('sec2_weight')
        else:
            role = user_row['role'] if is_postgres() else user_row[3]
            sec1_override = user_row['sec1_weight'] if is_postgres() else user_row[6]
            sec2_override = user_row['sec2_weight'] if is_postgres() else user_row[7]
    else:
        if active_conn is None:
            active_conn = get_db_connection()
            should_close = True
        cursor = active_conn.cursor()
        
        if is_postgres():
            cursor.execute("SELECT role, sec1_weight, sec2_weight FROM users WHERE id = %s", (user_id,))
            row = cursor.fetchone()
        else:
            cursor.execute("SELECT role, sec1_weight, sec2_weight FROM users WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            
        if not row:
            if should_close and active_conn:
                active_conn.close()
            return {"section1_weight": 70.0, "section2_weight": 30.0, "source": "default", "role": "EMPLOYEE"}
            
        role = row['role'] if is_postgres() else row[0]
        sec1_override = row['sec1_weight'] if is_postgres() else row[1]
        sec2_override = row['sec2_weight'] if is_postgres() else row[2]
    
    if sec1_override is not None and sec2_override is not None:
        if should_close and active_conn:
            active_conn.close()
        return {
            "section1_weight": float(sec1_override),
            "section2_weight": float(sec2_override),
            "source": "custom_override",
            "role": role
        }
        
    if role_settings is None:
        role_settings = get_role_settings(conn=active_conn)
        
    if should_close and active_conn:
        active_conn.close()

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

def get_system_settings(conn=None):
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True
    cursor = conn.cursor()
    
    cursor.execute("SELECT key, value FROM system_settings")
    rows = cursor.fetchall()
    if should_close:
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
