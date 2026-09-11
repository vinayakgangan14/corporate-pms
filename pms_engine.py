"""
Core PMS Business Logic, Calculation Engine, and Hierarchy Traversal
"""

from typing import Dict, Any, List, Optional
import sqlite3
from database import get_db_connection
from models import UserRole, KRASection, AppraisalStatus

def calculate_kra_achievement(target: float, actual: float, max_cap: float = 120.0) -> float:
    """
    Calculates achievement percentage against target.
    Caps extreme overperformance at max_cap (default 120%) to avoid distorting scores,
    while accurately capturing true performance ratios.
    """
    if target == 0:
        return 100.0 if actual >= 0 else 0.0
    
    raw_achieved = (actual / target) * 100.0
    return round(min(raw_achieved, max_cap), 2)

def determine_performance_band(composite_score: float) -> tuple[str, str]:
    """
    Maps composite score to Corporate Performance Band and Letter Grade.
    """
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

def compute_user_pms_score(user_id: int, year: int = 2026) -> Dict[str, Any]:
    """
    Fetches all Present Year (70%) and Upcoming Year (30%) KRAs for a user,
    computes weighted section scores, composite final score, performance band, and ratings.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        """SELECT id, lever_name, description, metric_unit, target_value, actual_outcome, 
                  weightage_percent, section, parent_kra_id, self_rating_percent, manager_rating_percent 
           FROM kras 
           WHERE user_id = ? AND year = ?""",
        (user_id, year)
    )
    kras = [dict(row) for row in cursor.fetchall()]
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
        
        # Self Rating auto-calculation based on target achievement if not manually overridden
        auto_self_rating = achieved_pct
        kra["computed_self_rating"] = kra["self_rating_percent"] if kra["self_rating_percent"] > 0 else auto_self_rating
        kra["computed_manager_rating"] = kra["manager_rating_percent"] if kra["manager_rating_percent"] > 0 else kra["computed_self_rating"]

        if kra["section"] == KRASection.PRESENT_YEAR_70.value:
            present_total_weight += weight
            # Weighted contribution = Achieved % * (Weight % / 100)
            weighted_contrib = achieved_pct * (weight / 100.0)
            present_weighted_score += weighted_contrib
            kra["weighted_contribution"] = round(weighted_contrib, 2)
            present_year_kras.append(kra)
        else:
            upcoming_total_weight += weight
            # Upcoming year targets score based on clarity & commitment rating (default actual/target or manager rating)
            weighted_contrib = achieved_pct * (weight / 100.0)
            upcoming_weighted_score += weighted_contrib
            kra["weighted_contribution"] = round(weighted_contrib, 2)
            upcoming_year_kras.append(kra)

    # Standardize section scores to 100 base if weights don't perfectly sum to 100
    norm_present_score = (present_weighted_score / (present_total_weight / 100.0)) if present_total_weight > 0 else 0.0
    norm_upcoming_score = (upcoming_weighted_score / (upcoming_total_weight / 100.0)) if upcoming_total_weight > 0 else 0.0

    # 70/30 Composite Weightage Formula
    present_contribution_70 = norm_present_score * 0.70
    upcoming_contribution_30 = norm_upcoming_score * 0.30
    composite_score = round(present_contribution_70 + upcoming_contribution_30, 2)
    
    band, grade = determine_performance_band(composite_score)

    return {
        "user_id": user_id,
        "year": year,
        "present_year": {
            "section_weightage_percent": 70,
            "total_kra_weight_sum": round(present_total_weight, 2),
            "raw_score": round(norm_present_score, 2),
            "weighted_70_contribution": round(present_contribution_70, 2),
            "kras": present_year_kras
        },
        "upcoming_year": {
            "section_weightage_percent": 30,
            "total_kra_weight_sum": round(upcoming_total_weight, 2),
            "raw_score": round(norm_upcoming_score, 2),
            "weighted_30_contribution": round(upcoming_contribution_30, 2),
            "kras": upcoming_year_kras
        },
        "composite_score": composite_score,
        "performance_band": band,
        "grade": grade,
        "warnings": [
            f"Present Year KRAs weight sum is {present_total_weight}%, expected 100%" if round(present_total_weight, 1) != 100.0 and present_total_weight > 0 else None,
            f"Upcoming Year KRAs weight sum is {upcoming_total_weight}%, expected 100%" if round(upcoming_total_weight, 1) != 100.0 and upcoming_total_weight > 0 else None
        ]
    }

def get_org_hierarchy_tree(root_user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Builds nested organizational reporting tree (Admin -> MD -> GM -> HOD -> Manager -> Supervisor -> Employee).
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT u.id, u.name, u.email, u.role, u.designation, u.manager_id, d.name as department_name, d.code as department_code
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
    conn.close()

    # Calculate current PMS scores for each user
    for user in all_users:
        score_data = compute_user_pms_score(user["id"])
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
    """
    Recursively finds all direct and indirect down-chain report user IDs for a given manager/MD/GM/HOD.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, manager_id FROM users")
    all_users = cursor.fetchall()
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
