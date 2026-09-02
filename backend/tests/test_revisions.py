from tests.conftest import reset_db

def test_revision_flow(client):
    reset_db()
    csv = """task_id,corridor_id,section_id,line_id,asset_id,task_type,description,severity,estimated_duration_minutes,requires_traffic_block,earliest_start,deadline,department
TSK-REV1,COR-1,SEC-1,LIN-1,AST-1,MAINT,Rev,HIGH,60,true,2026-09-01,2026-09-10,ENGINEERING
"""
    files = {"file": ("tasks.csv", csv, "text/csv")}
    client.post("/api/import/tasks", files=files, data={"source":"TMS"})
    client.post("/api/windows/generate?horizon_start=2026-09-01&horizon_end=2026-09-03")
    r = client.post("/api/plans/generate", json={"horizon_start":"2026-09-01","horizon_end":"2026-09-03","horizon_type":"WEEKLY"})
    pid=r.json()["plan_id"]
    client.post(f"/api/plans/{pid}/submit-review")
    client.post(f"/api/plans/{pid}/approve", json={"approver_id":"officer1","approver_role":"CONTROL_OFFICE","reason":"ok"})
    # revision
    r = client.post(f"/api/plans/{pid}/revisions", json={"reason":"Change","editor":"admin"})
    assert r.status_code==200
    new_pid=r.json()["new_plan_id"]
    # history
    r = client.get(f"/api/plans/{pid}/history")
    assert r.status_code==200
    assert len(r.json()["revisions"])>=1
    # changes
    r = client.get(f"/api/plans/{new_pid}/changes")
    assert r.status_code==200
