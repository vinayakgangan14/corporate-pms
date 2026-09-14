"""
FastAPI REST API Server for Corporate Performance Management System (PMS)
Includes Administrator Configurable Section Weightages & 100% KRA Weightage Validation.
"""

from fastapi import FastAPI, HTTPException, Request, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
import sqlite3
import os

from database import (
    init_db, 
    get_db_connection, 
    get_system_settings, 
    update_system_settings, 
    get_role_settings, 
    update_role_setting, 
    get_user_effective_weightages, 
    update_user_custom_weightages,
    is_postgres
)
from models import UserRole, KRASection, AppraisalStatus
from pms_engine import (
    compute_user_pms_score, 
    get_org_hierarchy_tree, 
    get_downchain_report_ids,
    determine_performance_band
)

app = FastAPI(
    title="Corporate Performance Management System (PMS)",
    description="Enterprise PMS web platform with position-based and dynamic Section 1 & Section 2 weightage engine.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

app.mount("/static", StaticFiles(directory=static_dir), name="static")

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

class UpdateSettingsSchema(BaseModel):
    section1_weightage: float
    section2_weightage: float

class UpdateRoleWeightageSchema(BaseModel):
    role: str
    section1_weight: float
    section2_weight: float

class UpdateUserWeightagesSchema(BaseModel):
    section1_weight: Optional[float] = None
    section2_weight: Optional[float] = None

# --- API Endpoints ---

@app.get("/")
def read_root():
    """Serves the main PMS Single-Page Web Application with anti-caching headers."""
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            headers = {
                "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0"
            }
            return HTMLResponse(content=f.read(), headers=headers)
    return HTMLResponse("<h2>PMS Server Running. Static UI loading...</h2>")

@app.get("/api/settings")
def get_settings():
    """Returns active administrator system section weightages."""
    return get_system_settings()

@app.post("/api/settings")
def update_settings(payload: UpdateSettingsSchema):
    """Administrator endpoint to set system default Section 1 and Section 2 weightage percentages."""
    total_weight = round(payload.section1_weightage + payload.section2_weightage, 1)
    if total_weight != 100.0:
        raise HTTPException(
            status_code=400, 
            detail=f"Overall section weightages sum to {total_weight}%, but Section 1 + Section 2 weightages must sum to exactly 100%!"
        )
    update_system_settings(payload.section1_weightage, payload.section2_weightage)
    return {"status": "success", "message": f"Section weightages updated to Section 1: {payload.section1_weightage}% / Section 2: {payload.section2_weightage}%"}

@app.get("/api/settings/roles")
def get_all_role_settings():
    """Returns configured section weightages matrix for all organizational roles/positions (MD, GM, HOD, etc.)."""
    return get_role_settings()

@app.post("/api/settings/roles")
def update_role_settings(payload: UpdateRoleWeightageSchema):
    """Administrator endpoint to update Section 1 and Section 2 weightages for a specific position/role."""
    total_weight = round(payload.section1_weight + payload.section2_weight, 1)
    if total_weight != 100.0:
        raise HTTPException(
            status_code=400,
            detail=f"Weightages for role '{payload.role}' sum to {total_weight}%, but Section 1 + Section 2 weightages must sum to exactly 100%!"
        )
    update_role_setting(payload.role, payload.section1_weight, payload.section2_weight)
    return {
        "status": "success",
        "message": f"Updated position weightage for '{payload.role}' to Section 1: {payload.section1_weight}% / Section 2: {payload.section2_weight}%"
    }

@app.put("/api/users/{user_id}/weightages")
def update_user_weightages(user_id: int, payload: UpdateUserWeightagesSchema):
    """Administrator endpoint to set custom section weightages for an individual user, or reset to role default if None."""
    if payload.section1_weight is not None and payload.section2_weight is not None:
        if payload.section1_weight < 0 or payload.section2_weight < 0:
            # Reset to role default
            update_user_custom_weightages(user_id, None, None)
            return {"status": "success", "message": f"User #{user_id} custom weightages reset to role default."}
        total_weight = round(payload.section1_weight + payload.section2_weight, 1)
        if total_weight != 100.0:
            raise HTTPException(
                status_code=400,
                detail=f"Custom weightages for user #{user_id} sum to {total_weight}%, but must sum to exactly 100%!"
            )
        update_user_custom_weightages(user_id, payload.section1_weight, payload.section2_weight)
        return {"status": "success", "message": f"User #{user_id} custom weightages updated to Section 1: {payload.section1_weight}% / Section 2: {payload.section2_weight}%"}
    else:
        update_user_custom_weightages(user_id, None, None)
        return {"status": "success", "message": f"User #{user_id} custom weightages cleared to inherit position role default."}

@app.get("/api/users")
def list_users():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if is_postgres():
        cursor.execute("""
            SELECT u.id, u.name, u.email, u.role, u.designation, u.manager_id, u.sec1_weight, u.sec2_weight,
                   m.name as manager_name, m.role as manager_role,
                   d.name as department_name
            FROM users u
            LEFT JOIN users m ON u.manager_id = m.id
            LEFT JOIN departments d ON u.department_id = d.id
            ORDER BY u.id ASC
        """)
        users = [dict(row) for row in cursor.fetchall()]
    else:
        cursor.execute("""
            SELECT u.id, u.name, u.email, u.role, u.designation, u.manager_id, u.sec1_weight, u.sec2_weight,
                   m.name as manager_name, m.role as manager_role,
                   d.name as department_name
            FROM users u
            LEFT JOIN users m ON u.manager_id = m.id
            LEFT JOIN departments d ON u.department_id = d.id
            ORDER BY u.id ASC
        """)
        users = [dict(row) for row in cursor.fetchall()]
        
    conn.close()

    for u in users:
        eff_weight = get_user_effective_weightages(u["id"])
        u["effective_section1_weight"] = eff_weight["section1_weight"]
        u["effective_section2_weight"] = eff_weight["section2_weight"]
        u["weightage_source"] = eff_weight["source"]
        
        score_data = compute_user_pms_score(u["id"])
        u["composite_score"] = score_data["composite_score"]
        u["performance_band"] = score_data["performance_band"]
        u["grade"] = score_data["grade"]

    return users

@app.post("/api/users")
def create_user(user: CreateUserSchema):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if is_postgres():
            cursor.execute(
                """INSERT INTO users (name, email, role, designation, department_id, manager_id)
                   VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
                (user.name, user.email, user.role, user.designation, user.department_id, user.manager_id)
            )
            user_id = cursor.fetchone()['id']
        else:
            cursor.execute(
                """INSERT INTO users (name, email, role, designation, department_id, manager_id)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user.name, user.email, user.role, user.designation, user.department_id, user.manager_id)
            )
            user_id = cursor.lastrowid
            
        conn.commit()
        conn.close()
        return {"status": "success", "user_id": user_id, "message": f"User '{user.name}' created successfully as {user.role}"}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=400, detail=f"User creation failed: {e}")

@app.get("/api/departments")
def list_departments():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, code FROM departments")
    depts = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return depts

@app.get("/api/hierarchy")
def get_hierarchy():
    return get_org_hierarchy_tree()

@app.get("/api/users/{user_id}/pms")
def get_user_pms_dashboard(user_id: int, year: int = 2026):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if is_postgres():
        cursor.execute("""
            SELECT u.id, u.name, u.email, u.role, u.designation, u.manager_id, 
                   m.name as manager_name, m.email as manager_email, m.role as manager_role,
                   d.name as department_name
            FROM users u
            LEFT JOIN users m ON u.manager_id = m.id
            LEFT JOIN departments d ON u.department_id = d.id
            WHERE u.id = %s
        """, (user_id,))
        user_row = cursor.fetchone()
        
        if not user_row:
            conn.close()
            raise HTTPException(status_code=404, detail="User not found")
            
        user_info = dict(user_row)
        
        cursor.execute("SELECT u.id, u.name, u.email, u.role, u.designation FROM users u WHERE u.manager_id = %s", (user_id,))
        direct_reports = [dict(row) for row in cursor.fetchall()]
        
        cursor.execute("SELECT status, self_comments, manager_comments FROM appraisals WHERE user_id = %s AND year = %s", (user_id, year))
        appraisal_row = cursor.fetchone()
        appraisal_meta = dict(appraisal_row) if appraisal_row else {"status": "DRAFT", "self_comments": "", "manager_comments": ""}
    else:
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
        
        cursor.execute("SELECT u.id, u.name, u.email, u.role, u.designation FROM users u WHERE u.manager_id = ?", (user_id,))
        direct_reports = [dict(row) for row in cursor.fetchall()]
        
        cursor.execute("SELECT status, self_comments, manager_comments FROM appraisals WHERE user_id = ? AND year = ?", (user_id, year))
        appraisal_row = cursor.fetchone()
        appraisal_meta = dict(appraisal_row) if appraisal_row else {"status": "DRAFT", "self_comments": "", "manager_comments": ""}

    downchain_ids = get_downchain_report_ids(user_id)
    conn.close()

    pms_scores = compute_user_pms_score(user_id, year)

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
    conn = get_db_connection()
    cursor = conn.cursor()
    if is_postgres():
        cursor.execute(
            """INSERT INTO kras (user_id, year, section, lever_name, description, metric_unit, target_value, actual_outcome, weightage_percent, parent_kra_id)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (kra.user_id, kra.year, kra.section, kra.lever_name, kra.description, kra.metric_unit, kra.target_value, kra.actual_outcome, kra.weightage_percent, kra.parent_kra_id)
        )
        kra_id = cursor.fetchone()['id']
    else:
        cursor.execute(
            """INSERT INTO kras (user_id, year, section, lever_name, description, metric_unit, target_value, actual_outcome, weightage_percent, parent_kra_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (kra.user_id, kra.year, kra.section, kra.lever_name, kra.description, kra.metric_unit, kra.target_value, kra.actual_outcome, kra.weightage_percent, kra.parent_kra_id)
        )
        kra_id = cursor.lastrowid
        
    conn.commit()
    conn.close()
    return {"status": "success", "kra_id": kra_id, "message": "KRA added successfully"}

@app.put("/api/kras/{kra_id}")
def update_kra(kra_id: int, payload: UpdateKRAOutcomeSchema):
    conn = get_db_connection()
    cursor = conn.cursor()
    if is_postgres():
        cursor.execute(
            """UPDATE kras 
               SET actual_outcome = %s, self_rating_percent = %s, manager_rating_percent = %s
               WHERE id = %s""",
            (payload.actual_outcome, payload.self_rating_percent, payload.manager_rating_percent, kra_id)
        )
    else:
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
    conn = get_db_connection()
    cursor = conn.cursor()
    if is_postgres():
        cursor.execute("DELETE FROM kras WHERE id = %s", (kra_id,))
    else:
        cursor.execute("DELETE FROM kras WHERE id = ?", (kra_id,))
    conn.commit()
    conn.close()
    return {"status": "success", "message": "KRA deleted successfully"}

@app.post("/api/appraisals/submit")
def submit_appraisal(payload: SubmitAppraisalSchema):
    """
    Submits self appraisal or manager evaluation.
    Enforces strict validation: Section 1 KRA weightages MUST sum to 100% and Section 2 KRA weightages MUST sum to 100%.
    """
    score_data = compute_user_pms_score(payload.user_id, payload.year)
    
    # Enforce 100% weightage sum check on formal submission / approval
    if payload.status in ["SUBMITTED_SELF", "APPROVED"]:
        if not score_data["is_overall_weightage_valid"]:
            error_details = " | ".join(score_data["errors"])
            raise HTTPException(
                status_code=400,
                detail=f"Cannot submit appraisal: {error_details}. Please adjust KRA weightages to sum to exactly 100% before submitting."
            )

    conn = get_db_connection()
    cursor = conn.cursor()
    
    if is_postgres():
        cursor.execute("""
            INSERT INTO appraisals (user_id, year, status, present_year_score, upcoming_year_score, composite_score, performance_band, grade, self_comments, manager_comments)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT(user_id, year) DO UPDATE SET
                status = EXCLUDED.status,
                present_year_score = EXCLUDED.present_year_score,
                upcoming_year_score = EXCLUDED.upcoming_year_score,
                composite_score = EXCLUDED.composite_score,
                performance_band = EXCLUDED.performance_band,
                grade = EXCLUDED.grade,
                self_comments = COALESCE(NULLIF(EXCLUDED.self_comments, ''), appraisals.self_comments),
                manager_comments = COALESCE(NULLIF(EXCLUDED.manager_comments, ''), appraisals.manager_comments),
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
    else:
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
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if is_postgres():
        cursor.execute("SELECT COUNT(*) FROM users WHERE role != 'ADMIN'")
        total_employees = cursor.fetchone()['count']
        cursor.execute("SELECT id, name, role FROM users WHERE role != 'ADMIN'")
        users = cursor.fetchall()
    else:
        cursor.execute("SELECT COUNT(*) FROM users WHERE role != 'ADMIN'")
        total_employees = cursor.fetchone()[0]
        cursor.execute("SELECT id, name, role FROM users WHERE role != 'ADMIN'")
        users = cursor.fetchall()
    
    scores = []
    bands = {"Outstanding / Exceptional": 0, "Exceeds Expectations": 0, "Meets Expectations": 0, "Needs Improvement": 0, "Unsatisfactory": 0}
    
    for u in users:
        uid = u['id'] if is_postgres() else u[0]
        score_data = compute_user_pms_score(uid)
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
