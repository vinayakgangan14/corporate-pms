"""
Database initialization and seed data populator for Corporate Performance Management System (PMS)
"""

import sqlite3
import os
from typing import Dict, Any, List
from models import CREATE_TABLES_SQL, UserRole, KRASection, AppraisalStatus

DB_PATH = os.path.join(os.path.dirname(__file__), "pms.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.executescript(CREATE_TABLES_SQL)
    conn.commit()
    conn.close()
    seed_data_if_empty()

def seed_data_if_empty():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if users exist
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] > 0:
        conn.close()
        return

    print("Seeding initial corporate hierarchy and 70/30 KRAs...")

    # 1. Insert Departments
    departments = [
        ("Executive Management", "EXEC"),
        ("Global Operations", "OPS"),
        ("Finance & Strategy", "FIN"),
        ("Engineering & Technology", "ENG"),
        ("Supply Chain & Logistics", "SCM")
    ]
    cursor.executemany("INSERT INTO departments (name, code) VALUES (?, ?)", departments)

    dept_map = {row[1]: idx + 1 for idx, row in enumerate(departments)}

    # 2. Insert Users (Hierarchy: ADMIN -> MD -> GM -> HOD -> MANAGER -> SUPERVISOR -> EMPLOYEE)
    users_data = [
        # (name, email, role, designation, dept_code, manager_email)
        ("System Administrator", "admin@company.com", UserRole.ADMIN, "System Administrator", "EXEC", None),
        ("Arthur Pendelton", "md@company.com", UserRole.MD, "Managing Director & CEO", "EXEC", None),
        
        # General Managers (GMs) reporting to MD
        ("Elena Rostova", "gm.ops@company.com", UserRole.GM, "GM - Operations & Strategy", "OPS", "md@company.com"),
        ("Marcus Vance", "gm.eng@company.com", UserRole.GM, "GM - Technology & Product", "ENG", "md@company.com"),
        
        # Heads of Department (HODs) reporting to GMs
        ("Sophia Lin", "hod.fin@company.com", UserRole.HOD, "HOD - Corporate Finance & EVA", "FIN", "gm.ops@company.com"),
        ("David Miller", "hod.eng@company.com", UserRole.HOD, "HOD - Enterprise Architecture", "ENG", "gm.eng@company.com"),
        
        # Managers reporting to HODs
        ("Rachel Green", "mgr.ops@company.com", UserRole.MANAGER, "Manager - Operational Excellence", "OPS", "hod.fin@company.com"),
        ("Kevin Wright", "mgr.dev@company.com", UserRole.MANAGER, "Manager - Software Development", "ENG", "hod.eng@company.com"),
        
        # Supervisors reporting to Managers
        ("Carlos Mendez", "sup.ops@company.com", UserRole.SUPERVISOR, "Supervisor - Process Audit", "OPS", "mgr.ops@company.com"),
        ("Anita Desai", "sup.dev@company.com", UserRole.SUPERVISOR, "Supervisor - Platform Engineering", "ENG", "mgr.dev@company.com"),
        
        # Employees reporting to Supervisors
        ("John Doe", "emp.john@company.com", UserRole.EMPLOYEE, "Senior Process Analyst", "OPS", "sup.ops@company.com"),
        ("Sarah Jenkins", "emp.sarah@company.com", UserRole.EMPLOYEE, "Full Stack Engineer", "ENG", "sup.dev@company.com"),
    ]

    user_id_map = {}
    for name, email, role, designation, dept_code, mgr_email in users_data:
        dept_id = dept_map.get(dept_code)
        mgr_id = user_id_map.get(mgr_email) if mgr_email else None
        cursor.execute(
            "INSERT INTO users (name, email, role, designation, department_id, manager_id) VALUES (?, ?, ?, ?, ?, ?)",
            (name, email, role.value if hasattr(role, 'value') else role, designation, dept_id, mgr_id)
        )
        user_id_map[email] = cursor.lastrowid

    # 3. Insert KRAs for Managing Director (MD), GMs, HODs, Managers, Supervisors, Employees
    # Section A: Present Year EVA & KRAs (70% Weightage)
    # Section B: Upcoming Year Objectives & Target Commitments (30% Weightage)
    
    current_year = 2026

    # Sample KRAs for MD (Arthur Pendelton)
    md_id = user_id_map["md@company.com"]
    md_kras = [
        # Present Year (70%)
        (md_id, current_year, KRASection.PRESENT_YEAR_70, "Group Economic Value Added (EVA)", "Deliver net positive operating profit after cost of capital", "USD Million", 15.0, 16.2, 40.0, None),
        (md_id, current_year, KRASection.PRESENT_YEAR_70, "Annual Corporate EBITDA Growth", "Achieve target consolidated EBITDA margin growth", "%", 18.0, 19.5, 30.0, None),
        (md_id, current_year, KRASection.PRESENT_YEAR_70, "Strategic Expansion & Market Share", "Expand operational footprint in key international regions", "% Share", 25.0, 24.0, 30.0, None),
        # Upcoming Year (30%)
        (md_id, current_year, KRASection.UPCOMING_YEAR_30, "Next-Gen AI & Automation Transformation", "Establish enterprise AI framework across core business units", "Completion %", 100.0, 90.0, 50.0, None),
        (md_id, current_year, KRASection.UPCOMING_YEAR_30, "ESG & Net Zero Carbon Roadmap", "Deploy renewable energy & carbon offset protocols for 2027", "Milestones", 5.0, 5.0, 50.0, None),
    ]

    for kra in md_kras:
        cursor.execute(
            """INSERT INTO kras (user_id, year, section, lever_name, description, metric_unit, target_value, actual_outcome, weightage_percent, parent_kra_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (kra[0], kra[1], kra[2].value, kra[3], kra[4], kra[5], kra[6], kra[7], kra[8], kra[9])
        )
    md_eva_kra_id = 1 # Group EVA KRA ID

    # Sample KRAs for GM Operations (Elena Rostova) - Linked to MD EVA
    gm_ops_id = user_id_map["gm.ops@company.com"]
    gm_kras = [
        # Present Year (70%)
        (gm_ops_id, current_year, KRASection.PRESENT_YEAR_70, "Operational Cost Reduction & Capital Efficiency", "Optimize plant operating expenditures to boost overall EVA", "USD Million", 4.5, 4.8, 50.0, md_eva_kra_id),
        (gm_ops_id, current_year, KRASection.PRESENT_YEAR_70, "Supply Chain Service Level Agreement (SLA)", "Maintain on-time delivery across global distribution networks", "% On-Time", 95.0, 96.2, 50.0, None),
        # Upcoming Year (30%)
        (gm_ops_id, current_year, KRASection.UPCOMING_YEAR_30, "Automated Logistics Hub Rollout", "Deploy Smart Warehouse IoT architecture in Region East", "% Readiness", 100.0, 85.0, 100.0, None),
    ]
    for kra in gm_kras:
        cursor.execute(
            """INSERT INTO kras (user_id, year, section, lever_name, description, metric_unit, target_value, actual_outcome, weightage_percent, parent_kra_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (kra[0], kra[1], kra[2].value, kra[3], kra[4], kra[5], kra[6], kra[7], kra[8], kra[9])
        )
    gm_ops_kra_id = cursor.lastrowid - 2

    # Sample KRAs for Manager Development (Kevin Wright)
    mgr_dev_id = user_id_map["mgr.dev@company.com"]
    mgr_kras = [
        # Present Year (70%)
        (mgr_dev_id, current_year, KRASection.PRESENT_YEAR_70, "Platform System Availability & Uptime", "Maintain high availability across core microservices", "% Uptime", 99.9, 99.95, 40.0, None),
        (mgr_dev_id, current_year, KRASection.PRESENT_YEAR_70, "On-Time Software Feature Delivery", "Complete planned quarterly feature roadmap items", "% Features", 90.0, 92.0, 35.0, None),
        (mgr_dev_id, current_year, KRASection.PRESENT_YEAR_70, "Code Quality & Bug Resolution SLA", "Resolve P1/P2 production issues within target SLA hours", "% SLA", 95.0, 97.0, 25.0, None),
        # Upcoming Year (30%)
        (mgr_dev_id, current_year, KRASection.UPCOMING_YEAR_30, "Cloud Migration Phase 2", "Migrate legacy databases to serverless cloud infrastructure", "% Migration", 100.0, 80.0, 60.0, None),
        (mgr_dev_id, current_year, KRASection.UPCOMING_YEAR_30, "Developer Upskilling & Certifications", "Team completion of cloud & security certifications", "Count", 8.0, 8.0, 40.0, None),
    ]
    for kra in mgr_kras:
        cursor.execute(
            """INSERT INTO kras (user_id, year, section, lever_name, description, metric_unit, target_value, actual_outcome, weightage_percent, parent_kra_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (kra[0], kra[1], kra[2].value, kra[3], kra[4], kra[5], kra[6], kra[7], kra[8], kra[9])
        )

    # Sample KRAs for Employee (Sarah Jenkins) - Dev Team Member
    emp_sarah_id = user_id_map["emp.sarah@company.com"]
    sarah_kras = [
        # Present Year (70%)
        (emp_sarah_id, current_year, KRASection.PRESENT_YEAR_70, "Core API Endpoint Velocity", "Develop and launch 12 REST API modules with unit tests", "Endpoints", 12.0, 14.0, 50.0, None),
        (emp_sarah_id, current_year, KRASection.PRESENT_YEAR_70, "Automated Test Coverage", "Increase backend test code coverage to 85%", "% Coverage", 85.0, 88.5, 50.0, None),
        # Upcoming Year (30%)
        (emp_sarah_id, current_year, KRASection.UPCOMING_YEAR_30, "GraphQL Gateway Implementation", "Design & build GraphQL aggregator for frontend mobile app", "% Complete", 100.0, 90.0, 100.0, None),
    ]
    for kra in sarah_kras:
        cursor.execute(
            """INSERT INTO kras (user_id, year, section, lever_name, description, metric_unit, target_value, actual_outcome, weightage_percent, parent_kra_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (kra[0], kra[1], kra[2].value, kra[3], kra[4], kra[5], kra[6], kra[7], kra[8], kra[9])
        )

    # 4. Insert Initial Appraisals with calculated Scores
    # We will trigger score calculations for seed users
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialization complete.")
