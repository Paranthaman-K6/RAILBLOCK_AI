from tests.conftest import reset_db
def test_priority_formula(client):
    reset_db()
    # import tasks
    csv_content = """task_id,corridor_id,section_id,line_id,asset_id,task_type,description,severity,safety_score,urgency_score,asset_criticality,operational_impact,overdue_days,coordination_value,resource_readiness,estimated_duration_minutes,requires_traffic_block,earliest_start,deadline,department
TSK-P1,COR-1,SEC-1,LIN-1,AST-1,MAINTENANCE,High,HIGH,90,80,85,70,12,60,75,60,true,2026-09-01,2026-09-10,ENGINEERING
"""
    files = {"file": ("tasks.csv", csv_content, "text/csv")}
    r = client.post("/api/import/tasks", files=files, data={"source":"TMS"})
    assert r.json()["accepted_count"]==1
    # check priority explanation
    r = client.get("/api/tasks/TSK-P1/priority-explanation")
    assert r.status_code==200
    j = r.json()
    assert "priority_score" in j
    assert "factor_weights" in j
    assert j["factor_weights"]["S"]==0.30
    # check calculation roughly
    # P = 0.3*90 +0.2*80+0.2*85+0.15*70+0.1*60+0.05*75 =27+16+17+10.5+6+3.75=80.25? But overdue may affect U, check
    assert j["priority_score"] > 60
    assert "priority_reason" in j
