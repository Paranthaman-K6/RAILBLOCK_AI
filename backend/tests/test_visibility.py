from tests.conftest import reset_db

def setup_approved(client):
    reset_db()
    csv = "task_id,corridor_id,section_id,line_id,asset_id,task_type,description,severity,estimated_duration_minutes,requires_traffic_block,earliest_start,deadline,department\nTSK-VIS1,COR-1,SEC-1,LIN-1,AST-1,MAINT,EngTask,HIGH,60,true,2026-09-01,2026-09-10,ENGINEERING\nTSK-VIS2,COR-1,SEC-1,LIN-1,AST-1,MAINT,SignalTask,HIGH,60,true,2026-09-01,2026-09-10,S_AND_T"
    files = {"file": ("tasks.csv", csv, "text/csv")}
    client.post("/api/import/tasks", files=files, data={"source":"TMS"})
    client.post("/api/windows/generate?horizon_start=2026-09-01&horizon_end=2026-09-03")
    r = client.post("/api/plans/generate", json={"horizon_start":"2026-09-01","horizon_end":"2026-09-03","horizon_type":"WEEKLY"})
    pid=r.json()["plan_id"]
    client.post(f"/api/plans/{pid}/submit-review")
    client.post(f"/api/plans/{pid}/approve", json={"approver_id":"officer1","approver_role":"CONTROL_OFFICE","reason":"ok"})
    return pid

def test_department_view_excludes_drafts(client):
    reset_db()
    csv = "task_id,corridor_id,section_id,line_id,asset_id,task_type,description,severity,estimated_duration_minutes,requires_traffic_block,earliest_start,deadline,department\nTSK-DRAFT,COR-1,SEC-1,LIN-1,AST-1,MAINT,Draft,HIGH,60,true,2026-09-01,2026-09-10,ENGINEERING"
    files = {"file": ("tasks.csv", csv, "text/csv")}
    client.post("/api/import/tasks", files=files, data={"source":"TMS"})
    client.post("/api/windows/generate?horizon_start=2026-09-01&horizon_end=2026-09-03")
    r = client.post("/api/plans/generate", json={"horizon_start":"2026-09-01","horizon_end":"2026-09-03","horizon_type":"WEEKLY"})
    pid=r.json()["plan_id"]
    r = client.get(f"/api/plans/{pid}/department-view?department=ENGINEERING")
    assert r.status_code==400
    pid2 = setup_approved(client)
    r = client.get(f"/api/plans/{pid2}/department-view?department=ENGINEERING")
    assert r.status_code==200
    assert "my_blocks" in r.json()

def test_department_view_shows_integrated(client):
    pid = setup_approved(client)
    r = client.get(f"/api/plans/{pid}/department-view?department=ENGINEERING")
    j=r.json()
    assert len(j["my_blocks"]) >=1 or len(j["integrated_blocks"]) >=1
