"""
Core PMS Business Logic, Calculation Engine, and Hierarchy Traversal
Supports Administrator Dynamic Section Weightages & 100% KRA Weightage Sum Enforcement.
"""

from typing import Dict, Any, List, Optional
import sqlite3
from database import get_db_connection, get_system_settings, get_user_effective_weightages, is_postgres
from models import UserRole, KRASection, AppraisalStatus

def calculate_kra_achievement(target: float, actual: float, max_cap: float = 120.0) -> float:
    if target == 0:
        return 100.0 if actual >= 0 else 0.0
    
    raw_achieved = (actual / target) * 100.0
    return round(min(raw_achieved, max_cap), 2)

def determine_performance_band(composite_score: float) -> tuple[str, str]:
    if composite_score >= 95.0:
        return ("Outstanding / Exceptional", "A+")
    elif composite_score >= 85.0:
        return ("Exceeds Expectations", "A")
    elif composite_score >= 70.0:
        return ("Meets Expectations", "B")
    elif composite_score >= 60.0:
        return ("Needs Improvement", "C")
    else:
        return ("Unsatisfactory", "D")

def compute_user_pms_score(user_id: int, year: int = 2026, conn=None, user_row=None, role_settings=None, kras_list=None) -> Dict[str, Any]:
    """
    Computes weighted section scores dynamically using position-based (MD 70/30, GM 50/50, etc.) or user-configured section weightages.
    Strictly validates that Section 1 KRA weightages sum to 100% and Section 2 KRA weightages sum to 100%.
    Optimized to accept optional pre-fetched conn, user_row, role_settings, and kras_list for zero-latency batch processing.
    """
    user_weightages = get_user_effective_weightages(user_id, conn=conn, role_settings=role_settings, user_row=user_row)
    sec1_weightage_pct = user_weightages["section1_weight"]
    sec2_weightage_pct = user_weightages["section2_weight"]

    if kras_list is not None:
        kras = [dict(k) for k in kras_list]
    else:
        should_close = False
        if conn is None:
            conn = get_db_connection()
            should_close = True
        cursor = conn.cursor()
        
        if is_postgres():
            cursor.execute(
                """SELECT id, lever_name, description, metric_unit, target_value, actual_outcome, 
                          weightage_percent, section, parent_kra_id, self_rating_percent, manager_rating_percent 
                   FROM kras 
                   WHERE user_id = %s AND year = %s""",
                (user_id, year)
            )
            kras = [dict(row) for row in cursor.fetchall()]
        else:
            cursor.execute(
                """SELECT id, lever_name, description, metric_unit, target_value, actual_outcome, 
                          weightage_percent, section, parent_kra_id, self_rating_percent, manager_rating_percent 
                   FROM kras 
                   WHERE user_id = ? AND year = ?""",
                (user_id, year)
            )
            kras = [dict(row) for row in cursor.fetchall()]
            
        if should_close:
            conn.close()

    present_year_kras = []
    upcoming_year_kras = []
    
    present_weighted_score = 0.0
    present_total_weight = 0.0
    
    upcoming_weighted_score = 0.0
    upcoming_total_weight = 0.0

    for kra in kras:
        target = float(kra["target_value"])
        actual = float(kra["actual_outcome"])
        weight = float(kra["weightage_percent"])
        
        achieved_pct = calculate_kra_achievement(target, actual)
        kra["achievement_percent"] = achieved_pct
        
        auto_self_rating = achieved_pct
        kra["computed_self_rating"] = kra["self_rating_percent"] if kra["self_rating_percent"] > 0 else auto_self_rating
        kra["computed_manager_rating"] = kra["manager_rating_percent"] if kra["manager_rating_percent"] > 0 else kra["computed_self_rating"]

        if kra["section"] == KRASection.PRESENT_YEAR_70.value:
            present_total_weight += weight
            weighted_contrib = achieved_pct * (weight / 100.0)
            present_weighted_score += weighted_contrib
            kra["weighted_contribution"] = round(weighted_contrib, 2)
            present_year_kras.append(kra)
        else:
            upcoming_total_weight += weight
            weighted_contrib = achieved_pct * (weight / 100.0)
            upcoming_weighted_score += weighted_contrib
            kra["weighted_contribution"] = round(weighted_contrib, 2)
            upcoming_year_kras.append(kra)

    norm_present_score = (present_weighted_score / (present_total_weight / 100.0)) if present_total_weight > 0 else 0.0
    norm_upcoming_score = (upcoming_weighted_score / (upcoming_total_weight / 100.0)) if upcoming_total_weight > 0 else 0.0

    # Dynamic Section 1 & Section 2 composite contribution
    sec1_contrib = norm_present_score * (sec1_weightage_pct / 100.0)
    sec2_contrib = norm_upcoming_score * (sec2_weightage_pct / 100.0)
    composite_score = round(sec1_contrib + sec2_contrib, 2)
    
    band, grade = determine_performance_band(composite_score)

    # 100% Weightage Sum Validation Check
    is_sec1_valid = abs(round(present_total_weight, 1) - 100.0) < 0.1 if len(present_year_kras) > 0 else True
    is_sec2_valid = abs(round(upcoming_total_weight, 1) - 100.0) < 0.1 if len(upcoming_year_kras) > 0 else True

    sec1_error = None if is_sec1_valid else f"Error: Sum total KRA weightage for Section 1 is {round(present_total_weight, 1)}%, but must equal exactly 100%"
    sec2_error = None if is_sec2_valid else f"Error: Sum total KRA weightage for Section 2 is {round(upcoming_total_weight, 1)}%, but must equal exactly 100%"

    return {
        "user_id": user_id,
        "year": year,
        "section_settings": {
            "section1_weightage_percent": sec1_weightage_pct,
            "section2_weightage_percent": sec2_weightage_pct,
        },
        "present_year": {
            "section_weightage_percent": sec1_weightage_pct,
            "total_kra_weight_sum": round(present_total_weight, 1),
            "is_valid_100_percent": is_sec1_valid,
            "weightage_error": sec1_error,
            "raw_score": round(norm_present_score, 2),
            "weighted_contribution": round(sec1_contrib, 2),
            "kras": present_year_kras
        },
        "upcoming_year": {
            "section_weightage_percent": sec2_weightage_pct,
            "total_kra_weight_sum": round(upcoming_total_weight, 1),
            "is_valid_100_percent": is_sec2_valid,
            "weightage_error": sec2_error,
            "raw_score": round(norm_upcoming_score, 2),
            "weighted_contribution": round(sec2_contrib, 2),
            "kras": upcoming_year_kras
        },
        "is_overall_weightage_valid": is_sec1_valid and is_sec2_valid,
        "composite_score": composite_score,
        "performance_band": band,
        "grade": grade,
        "errors": [err for err in [sec1_error, sec2_error] if err]
    }

def get_org_hierarchy_tree(root_user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT u.id, u.name, u.email, u.role, u.designation, u.manager_id, u.sec1_weight, u.sec2_weight, d.name as department_name, d.code as department_code
        FROM users u
        LEFT JOIN departments d ON u.department_id = d.id
        ORDER BY 
            CASE u.role 
                WHEN 'ADMIN' THEN 1
                WHEN 'MD' THEN 2
                WHEN 'GM' THEN 3
                WHEN 'HOD' THEN 4
                WHEN 'MANAGER' THEN 5
                WHEN 'SUPERVISOR' THEN 6
                ELSE 7
            END
    """)
    all_users = [dict(row) for row in cursor.fetchall()]

    from database import get_role_settings
    role_settings = get_role_settings(conn=conn)
    
    if is_postgres():
        cursor.execute("""
            SELECT user_id, id, lever_name, description, metric_unit, target_value, actual_outcome, 
                   weightage_percent, section, parent_kra_id, self_rating_percent, manager_rating_percent 
            FROM kras 
            WHERE year = 2026
        """)
        all_kras = [dict(row) for row in cursor.fetchall()]
    else:
        cursor.execute("""
            SELECT user_id, id, lever_name, description, metric_unit, target_value, actual_outcome, 
                   weightage_percent, section, parent_kra_id, self_rating_percent, manager_rating_percent 
            FROM kras 
            WHERE year = 2026
        """)
        all_kras = [dict(row) for row in cursor.fetchall()]
        
    conn.close()

    kras_by_user = {}
    for k in all_kras:
        kras_by_user.setdefault(k["user_id"], []).append(k)

    for user in all_users:
        uid = user["id"]
        score_data = compute_user_pms_score(
            uid, year=2026, conn=None, user_row=user, 
            role_settings=role_settings, kras_list=kras_by_user.get(uid, [])
        )
        user["composite_score"] = score_data["composite_score"]
        user["performance_band"] = score_data["performance_band"]
        user["grade"] = score_data["grade"]
        user["reports"] = []

    user_dict = {u["id"]: u for u in all_users}
    tree = []

    for user in all_users:
        mgr_id = user["manager_id"]
        if mgr_id and mgr_id in user_dict:
            user_dict[mgr_id]["reports"].append(user)
        else:
            tree.append(user)

    return tree

def get_downchain_report_ids(manager_id: int) -> List[int]:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, manager_id FROM users")
    if is_postgres():
        all_users = [(r['id'], r['manager_id']) for r in cursor.fetchall()]
    else:
        all_users = [(r[0], r[1]) for r in cursor.fetchall()]
    conn.close()

    children_map = {}
    for uid, mid in all_users:
        if mid:
            children_map.setdefault(mid, []).append(uid)

    downchain = []
    stack = [manager_id]
    
    while stack:
        curr = stack.pop()
        children = children_map.get(curr, [])
        downchain.extend(children)
        stack.extend(children)
        
    return downchain
