"""
FastAPI REST API Server for Corporate Performance Management System (PMS)
"""

from fastapi import FastAPI, HTTPException, Request, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
import sqlite3
import os

from database import init_db, get_db_connection
from models import UserRole, KRASection, AppraisalStatus
from pms_engine import (
    compute_user_pms_score, 
    get_org_hierarchy_tree, 
    get_downchain_report_ids,
    determine_performance_band
)

app = FastAPI(
    title="Corporate Performance Management System (PMS)",
    description="Enterprise PMS web platform with 70/30 EVA weightage engine & down-chain org hierarchy.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static directory for frontend
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Startup Event to initialize SQLite database
@app.on_event("startup")
def startup_db():
    init_db()

# --- Pydantic Data Validation Schemas ---

class CreateUserSchema(BaseModel):
    name: str
    email: str
    role: str
    designation: str
    department_id: Optional[int] = 1
    manager_id: Optional[int] = None

class CreateKRASchema(BaseModel):
    user_id: int
    year: int = 2026
    section: str # PRESENT_YEAR_70 or UPCOMING_YEAR_30
    lever_name: str
    description: Optional[str] = ""
    metric_unit: str
    target_value: float
    actual_outcome: float = 0.0
    weightage_percent: float
    parent_kra_id: Optional[int] = None

class UpdateKRAOutcomeSchema(BaseModel):
    actual_outcome: float
    self_rating_percent: Optional[float] = 0.0
    manager_rating_percent: Optional[float] = 0.0

class SubmitAppraisalSchema(BaseModel):
    user_id: int
    year: int = 2026
    status: str
    self_comments: Optional[str] = ""
    manager_comments: Optional[str] = ""

# --- API Endpoints ---

@app.get("/")
def read_root():
    """Serves the main PMS Single-Page Web Application."""
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h2>PMS Server Running. Static UI loading...</h2>")

@app.get("/api/users")
def list_users():
    """Returns all users in the system with their reporting managers."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.id, u.name, u.email, u.role, u.designation, u.manager_id, 
               m.name as manager_name, m.role as manager_role,
               d.name as department_name
        FROM users u
        LEFT JOIN users m ON u.manager_id = m.id
        LEFT JOIN departments d ON u.department_id = d.id
        ORDER BY u.id ASC
    """)
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()

    # Attach summary scores
    for u in users:
        score_data = compute_user_pms_score(u["id"])
        u["composite_score"] = score_data["composite_score"]
        u["performance_band"] = score_data["performance_band"]
        u["grade"] = score_data["grade"]

    return users

@app.post("/api/users")
def create_user(user: CreateUserSchema):
    """Admin endpoint to create Managing Director (MD), GMs, HODs, Managers, Supervisors, or Staff."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """INSERT INTO users (name, email, role, designation, department_id, manager_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user.name, user.email, user.role, user.designation, user.department_id, user.manager_id)
        )
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        return {"status": "success", "user_id": user_id, "message": f"User '{user.name}' created successfully as {user.role}"}
    except sqlite3.IntegrityError as e:
        conn.close()
        raise HTTPException(status_code=400, detail=f"Email '{user.email}' already exists or database constraint failed.")

@app.get("/api/departments")
def list_departments():
    """Returns all company departments."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, code FROM departments")
    depts = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return depts

@app.get("/api/hierarchy")
def get_hierarchy():
    """Returns full organizational tree with reporting links and scores."""
    return get_org_hierarchy_tree()

@app.get("/api/users/{user_id}/pms")
def get_user_pms_dashboard(user_id: int, year: int = 2026):
    """
    Fetches comprehensive PMS appraisal dashboard for a user:
    - User Details & Reporting Manager details
    - 70% Present Year EVA KRAs (Target vs Actual, Achievement %, Self Rating, Weighted Score)
    - 30% Upcoming Year Objectives
    - Overall 70/30 Composite Score & Performance Band Grade
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.id, u.name, u.email, u.role, u.designation, u.manager_id, 
               m.name as manager_name, m.email as manager_email, m.role as manager_role,
               d.name as department_name
        FROM users u
        LEFT JOIN users m ON u.manager_id = m.id
        LEFT JOIN departments d ON u.department_id = d.id
        WHERE u.id = ?
    """, (user_id,))
    user_row = cursor.fetchone()
    
    if not user_row:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")
        
    user_info = dict(user_row)
    
    # Fetch direct reports if any
    cursor.execute("""
        SELECT u.id, u.name, u.email, u.role, u.designation
        FROM users u
        WHERE u.manager_id = ?
    """, (user_id,))
    direct_reports = [dict(row) for row in cursor.fetchall()]
    
    # Fetch downchain reports
    downchain_ids = get_downchain_report_ids(user_id)
    
    # Fetch current appraisal record status
    cursor.execute("SELECT status, self_comments, manager_comments FROM appraisals WHERE user_id = ? AND year = ?", (user_id, year))
    appraisal_row = cursor.fetchone()
    appraisal_meta = dict(appraisal_row) if appraisal_row else {"status": "DRAFT", "self_comments": "", "manager_comments": ""}

    conn.close()

    pms_scores = compute_user_pms_score(user_id, year)

    # Attach direct report summary for managers/GMs/MD
    reports_pms = []
    for r in direct_reports:
        r_score = compute_user_pms_score(r["id"], year)
        reports_pms.append({
            "id": r["id"],
            "name": r["name"],
            "role": r["role"],
            "designation": r["designation"],
            "composite_score": r_score["composite_score"],
            "performance_band": r_score["performance_band"],
            "grade": r_score["grade"]
        })

    return {
        "user": user_info,
        "appraisal_status": appraisal_meta,
        "pms": pms_scores,
        "direct_reports": reports_pms,
        "downchain_total_count": len(downchain_ids)
    }

@app.post("/api/kras")
def create_kra(kra: CreateKRASchema):
    """Adds a new KRA / Target Objective under 70% Present or 30% Upcoming year section."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO kras (user_id, year, section, lever_name, description, metric_unit, target_value, actual_outcome, weightage_percent, parent_kra_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (kra.user_id, kra.year, kra.section, kra.lever_name, kra.description, kra.metric_unit, kra.target_value, kra.actual_outcome, kra.weightage_percent, kra.parent_kra_id)
    )
    conn.commit()
    kra_id = cursor.lastrowid
    conn.close()
    return {"status": "success", "kra_id": kra_id, "message": "KRA added successfully"}

@app.put("/api/kras/{kra_id}")
def update_kra(kra_id: int, payload: UpdateKRAOutcomeSchema):
    """Updates actual outcome achieved against target, self rating %, or manager rating %."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """UPDATE kras 
           SET actual_outcome = ?, self_rating_percent = ?, manager_rating_percent = ?
           WHERE id = ?""",
        (payload.actual_outcome, payload.self_rating_percent, payload.manager_rating_percent, kra_id)
    )
    conn.commit()
    conn.close()
    return {"status": "success", "message": "KRA performance outcome updated successfully"}

@app.delete("/api/kras/{kra_id}")
def delete_kra(kra_id: int):
    """Deletes a KRA."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM kras WHERE id = ?", (kra_id,))
    conn.commit()
    conn.close()
    return {"status": "success", "message": "KRA deleted successfully"}

@app.post("/api/appraisals/submit")
def submit_appraisal(payload: SubmitAppraisalSchema):
    """Submits self appraisal or manager evaluation, updating appraisal status in database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    score_data = compute_user_pms_score(payload.user_id, payload.year)
    
    cursor.execute("""
        INSERT INTO appraisals (user_id, year, status, present_year_score, upcoming_year_score, composite_score, performance_band, grade, self_comments, manager_comments)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, year) DO UPDATE SET
            status = excluded.status,
            present_year_score = excluded.present_year_score,
            upcoming_year_score = excluded.upcoming_year_score,
            composite_score = excluded.composite_score,
            performance_band = excluded.performance_band,
            grade = excluded.grade,
            self_comments = COALESCE(NULLIF(excluded.self_comments, ''), self_comments),
            manager_comments = COALESCE(NULLIF(excluded.manager_comments, ''), manager_comments),
            updated_at = CURRENT_TIMESTAMP
    """, (
        payload.user_id, 
        payload.year, 
        payload.status, 
        score_data["present_year"]["raw_score"], 
        score_data["upcoming_year"]["raw_score"], 
        score_data["composite_score"], 
        score_data["performance_band"], 
        score_data["grade"], 
        payload.self_comments, 
        payload.manager_comments
    ))
    conn.commit()
    conn.close()
    return {"status": "success", "message": f"Appraisal status updated to '{payload.status}'"}

@app.get("/api/analytics")
def get_executive_analytics():
    """Returns company-wide executive analytics for Admin and Managing Director (MD)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM users WHERE role != 'ADMIN'")
    total_employees = cursor.fetchone()[0]
    
    cursor.execute("SELECT id, name, role FROM users WHERE role != 'ADMIN'")
    users = cursor.fetchall()
    
    scores = []
    bands = {"Outstanding / Exceptional": 0, "Exceeds Expectations": 0, "Meets Expectations": 0, "Needs Improvement": 0, "Unsatisfactory": 0}
    
    for u in users:
        score_data = compute_user_pms_score(u[0])
        score = score_data["composite_score"]
        band = score_data["performance_band"]
        scores.append(score)
        if band in bands:
            bands[band] += 1
            
    avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
    
    conn.close()
    return {
        "total_employees": total_employees,
        "company_average_pms_score": avg_score,
        "performance_band_distribution": bands
    }
