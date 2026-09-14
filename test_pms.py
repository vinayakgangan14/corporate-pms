"""
Automated Unit Tests & Sanity Suite for PMS 70/30 Calculation Engine & Hierarchy
"""

import os
# import pytest
from database import init_db, get_db_connection
from pms_engine import compute_user_pms_score, get_org_hierarchy_tree, determine_performance_band

def test_pms_calculation_and_hierarchy():
    print("Running PMS automated test suite...")
    
    # 1. Init Database
    init_db()
    
    # 2. Test Performance Band Formula
    band, grade = determine_performance_band(96.5)
    assert grade == "A+", f"Expected A+, got {grade}"
    assert "Outstanding" in band
    
    band, grade = determine_performance_band(88.0)
    assert grade == "A"
    
    band, grade = determine_performance_band(75.0)
    assert grade == "B"
    
    band, grade = determine_performance_band(62.0)
    assert grade == "C"
    
    band, grade = determine_performance_band(55.0)
    assert grade == "D"
    
    print("[PASS] Performance band & grade mapping passed.")

    # 3. Test MD PMS Score Calculation (MD: 70% Present Year EVA + 30% Upcoming Year Objectives)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE email = 'md@company.com'")
    md_user = cursor.fetchone()
    assert md_user is not None, "MD user seed not found"
    md_id = md_user['id'] if isinstance(md_user, dict) else md_user[0]
    
    cursor.execute("SELECT id FROM users WHERE email = 'gm.ops@company.com'")
    gm_user = cursor.fetchone()
    assert gm_user is not None, "GM user seed not found"
    gm_id = gm_user['id'] if isinstance(gm_user, dict) else gm_user[0]

    cursor.execute("SELECT id FROM users WHERE email = 'emp.john@company.com'")
    emp_user = cursor.fetchone()
    assert emp_user is not None, "Employee user seed not found"
    emp_id = emp_user['id'] if isinstance(emp_user, dict) else emp_user[0]
    conn.close()

    md_pms = compute_user_pms_score(md_id, 2026)
    assert md_pms["present_year"]["section_weightage_percent"] == 70.0
    assert md_pms["upcoming_year"]["section_weightage_percent"] == 30.0
    print(f"[PASS] MD 70/30 Position Weightage Verified: Present 70%, Upcoming 30%, Composite={md_pms['composite_score']}%")

    gm_pms = compute_user_pms_score(gm_id, 2026)
    assert gm_pms["present_year"]["section_weightage_percent"] == 50.0
    assert gm_pms["upcoming_year"]["section_weightage_percent"] == 50.0
    print(f"[PASS] GM 50/50 Position Weightage Verified: Present 50%, Upcoming 50%")

    emp_pms = compute_user_pms_score(emp_id, 2026)
    assert emp_pms["present_year"]["section_weightage_percent"] == 30.0
    assert emp_pms["upcoming_year"]["section_weightage_percent"] == 70.0
    print(f"[PASS] Staff/Employee 30/70 Position Weightage Verified: Present 30%, Upcoming 70%")

    # 4. Test Organizational Hierarchy Tree
    tree = get_org_hierarchy_tree()
    assert len(tree) > 0, "Org tree should not be empty"
    
    # MD should be at top under Admin
    md_node = None
    for top_node in tree:
        if top_node["role"] == "MD":
            md_node = top_node
            break
        elif top_node["reports"]:
            for child in top_node["reports"]:
                if child["role"] == "MD":
                    md_node = child
                    break
                    
    assert md_node is not None, "MD node missing in hierarchy tree"
    assert len(md_node["reports"]) > 0, "MD should have reporting General Managers (GMs)"
    
    print(f"[PASS] Hierarchy Tree Test Passed: MD '{md_node['name']}' has {len(md_node['reports'])} reporting General Managers.")
    print("All PMS sanity tests completed successfully!")

if __name__ == "__main__":
    test_pms_calculation_and_hierarchy()
