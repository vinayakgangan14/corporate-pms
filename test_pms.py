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

    # 3. Test MD PMS Score Calculation (70% Present Year EVA + 30% Upcoming Year Objectives)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE email = 'md@company.com'")
    md_user = cursor.fetchone()
    assert md_user is not None, "MD user seed not found"
    md_id = md_user[0]
    conn.close()

    pms_data = compute_user_pms_score(md_id, 2026)
    
    assert "present_year" in pms_data
    assert "upcoming_year" in pms_data
    assert pms_data["present_year"]["section_weightage_percent"] == 70
    assert pms_data["upcoming_year"]["section_weightage_percent"] == 30
    assert pms_data["composite_score"] > 0, "Composite score should be computed"

    print(f"[PASS] MD 70/30 Score Test Passed: Present 70% Raw={pms_data['present_year']['raw_score']}%, Upcoming 30% Raw={pms_data['upcoming_year']['raw_score']}%, Composite Score={pms_data['composite_score']}%, Grade={pms_data['grade']}")

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
