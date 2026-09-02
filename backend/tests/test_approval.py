from tests.conftest import reset_db

def setup_plan(client):
    reset_db()
    csv_tasks = """task_id,corridor_id,section_id,line_id,asset_id,task_type,description,severity,estimated_duration_minutes,requires_traffic_block,earliest_start,deadline,department
TSK-A1,COR-1,SEC-1,LIN-1,AST-1,MAINT,Test,HIGH,60,true,2026-09-01,2026-09-10,ENGINEERING
"""
    files = {"file": ("tasks.csv", csv_tasks, "text/csv")}
    client.post("/api/import/tasks", files=files, data={"source":"TMS"})
    client.post("/api/windows/generate?horizon_start=2026-09-01&horizon_end=2026-09-03")
    r = client.post("/api/plans/generate", json={"horizon_start":"2026-09-01","horizon_end":"2026-09-03","horizon_type":"WEEKLY"})
    return r.json()["plan_id"]

def test_approval_requires_valid(client):
    pid = setup_plan(client)
    # submit
    client.post(f"/api/plans/{pid}/submit-review")
    r = client.post(f"/api/plans/{pid}/approve", json={"approver_id":"officer1","approver_role":"CONTROL_OFFICE","reason":"ok"})
    assert r.status_code==200
    assert r.json()["status"]=="APPROVED"

def test_rejection_requires_reason(client):
    pid = setup_plan(client)
    client.post(f"/api/plans/{pid}/submit-review")
    r = client.post(f"/api/plans/{pid}/reject", json={})
    assert r.status_code==400
    r = client.post(f"/api/plans/{pid}/reject", json={"reason":"Not feasible","approver_id":"officer1"})
    assert r.status_code==200
    assert r.json()["status"]=="REJECTED"

def test_draft_can_be_edited(client):
    pid = setup_plan(client)
    # get block
    r = client.get(f"/api/plans/{pid}")
    blk = r.json()["blocks"][0]["block_id"]
    r = client.patch(f"/api/plans/{pid}/draft-blocks/{blk}", json={"service_date":"2026-09-02","reason":"edit test","editor":"planner1"})
    assert r.status_code==200

def test_approved_immutable(client):
    pid = setup_plan(client)
    client.post(f"/api/plans/{pid}/submit-review")
    client.post(f"/api/plans/{pid}/approve", json={"approver_id":"officer1","approver_role":"CONTROL_OFFICE","reason":"ok"})
    r = client.get(f"/api/plans/{pid}")
    blk = r.json()["blocks"][0]["block_id"]
    r = client.patch(f"/api/plans/{pid}/draft-blocks/{blk}", json={"service_date":"2026-09-03","reason":"bad edit","editor":"planner1"})
    assert r.status_code==400
    assert "immutable" in r.json()["detail"].lower()

def test_revision_creates_new_version(client):
    pid = setup_plan(client)
    client.post(f"/api/plans/{pid}/submit-review")
    client.post(f"/api/plans/{pid}/approve", json={"approver_id":"officer1","approver_role":"CONTROL_OFFICE","reason":"ok"})
    r = client.post(f"/api/plans/{pid}/revisions", json={"reason":"Emergency","editor":"admin"})
    assert r.status_code==200
    assert r.json()["new_plan_id"] != pid
    assert r.json()["revision_number"] == 1

def test_stale_revision_409(client):
    pid = setup_plan(client)
    client.post(f"/api/plans/{pid}/submit-review")
    client.post(f"/api/plans/{pid}/approve", json={"approver_id":"officer1","approver_role":"CONTROL_OFFICE","reason":"ok"})
    # first revision
    r = client.post(f"/api/plans/{pid}/revisions", json={"reason":"first","editor":"admin","expected_version":1})
    assert r.status_code==200
    # stale: expect version mismatch
    r2 = client.post(f"/api/plans/{pid}/revisions", json={"reason":"stale","editor":"admin","expected_version":999})
    assert r2.status_code==409
