from tests.conftest import reset_db

def test_completed_survives_replan(client):
    reset_db()
    csv = """task_id,corridor_id,section_id,line_id,asset_id,task_type,description,severity,estimated_duration_minutes,requires_traffic_block,earliest_start,deadline,department
TSK-REPLAN1,COR-1,SEC-1,LIN-1,AST-1,MAINT,Test,HIGH,60,true,2026-09-01,2026-09-10,ENGINEERING
TSK-REPLAN2,COR-1,SEC-1,LIN-1,AST-1,MAINT,Test2,HIGH,60,true,2026-09-01,2026-09-10,ENGINEERING
"""
    files = {"file": ("tasks.csv", csv, "text/csv")}
    client.post("/api/import/tasks", files=files, data={"source":"TMS"})
    client.post("/api/windows/generate?horizon_start=2026-09-01&horizon_end=2026-09-03")
    r = client.post("/api/plans/generate", json={"horizon_start":"2026-09-01","horizon_end":"2026-09-03","horizon_type":"WEEKLY"})
    pid=r.json()["plan_id"]
    client.post(f"/api/plans/{pid}/submit-review")
    client.post(f"/api/plans/{pid}/approve", json={"approver_id":"officer1","approver_role":"CONTROL_OFFICE","reason":"ok"})
    # execute one block
    r = client.get(f"/api/plans/{pid}")
    blk = r.json()["blocks"][0]["block_id"]
    client.post(f"/api/blocks/{blk}/execution", json={"actual_start":60,"actual_end":120,"status":"COMPLETED","completed_task_ids":["TSK-REPLAN1"],"recorded_by":"eng1","service_date":"2026-09-02"})
    # replan
    r = client.post(f"/api/plans/{pid}/replan", json={"reason":"Emergency"})
    assert r.status_code==200
    assert "new_plan_id" in r.json()
    # check execution still exists
    r = client.get(f"/api/execution/plan/{pid}")
    assert len(r.json())>=1
    # also new plan's execution history preserved via audit, but check original plan's execution not deleted
    r = client.get("/api/execution")
    assert any(e["block_id"]==blk for e in r.json())
