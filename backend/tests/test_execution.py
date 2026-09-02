from tests.conftest import reset_db

def setup_exec(client):
    reset_db()
    csv = """task_id,corridor_id,section_id,line_id,asset_id,task_type,description,severity,estimated_duration_minutes,requires_traffic_block,earliest_start,deadline,department
TSK-EXE1,COR-1,SEC-1,LIN-1,AST-1,MAINT,Exec,HIGH,60,true,2026-09-01,2026-09-10,ENGINEERING
"""
    files = {"file": ("tasks.csv", csv, "text/csv")}
    client.post("/api/import/tasks", files=files, data={"source":"TMS"})
    client.post("/api/windows/generate?horizon_start=2026-09-01&horizon_end=2026-09-03")
    r = client.post("/api/plans/generate", json={"horizon_start":"2026-09-01","horizon_end":"2026-09-03","horizon_type":"WEEKLY"})
    pid=r.json()["plan_id"]
    client.post(f"/api/plans/{pid}/submit-review")
    client.post(f"/api/plans/{pid}/approve", json={"approver_id":"officer1","approver_role":"CONTROL_OFFICE","reason":"ok"})
    r = client.get(f"/api/plans/{pid}")
    blk = r.json()["blocks"][0]["block_id"]
    return pid, blk

def test_valid_execution(client):
    pid, blk = setup_exec(client)
    r = client.post(f"/api/blocks/{blk}/execution", json={"actual_start":60,"actual_end":120,"status":"COMPLETED","completed_task_ids":["TSK-EXE1"],"recorded_by":"eng1","service_date":"2026-09-02"})
    assert r.status_code==200
    assert r.json()["code"]==201

def test_invalid_execution_end_before_start(client):
    pid, blk = setup_exec(client)
    r = client.post(f"/api/blocks/{blk}/execution", json={"actual_start":120,"actual_end":60,"status":"COMPLETED","completed_task_ids":["TSK-EXE1"],"recorded_by":"eng1","service_date":"2026-09-02"})
    assert r.status_code==400

def test_duplicate_execution_409_or_idempotent(client):
    pid, blk = setup_exec(client)
    payload={"actual_start":60,"actual_end":120,"status":"COMPLETED","completed_task_ids":["TSK-EXE1"],"recorded_by":"eng1","service_date":"2026-09-02"}
    r1 = client.post(f"/api/blocks/{blk}/execution", json=payload)
    assert r1.status_code==200
    r2 = client.post(f"/api/blocks/{blk}/execution", json=payload)
    assert r2.status_code==200
    assert r2.json()["code"]==200  # idempotent
    # different payload should 409
    payload2={"actual_start":70,"actual_end":130,"status":"COMPLETED","completed_task_ids":["TSK-EXE1"],"recorded_by":"eng1","service_date":"2026-09-02"}
    r3 = client.post(f"/api/blocks/{blk}/execution", json=payload2)
    assert r3.status_code==409

def test_wnd_rejected(client):
    r = client.post(f"/api/blocks/WND-12345678/execution", json={"actual_start":60,"actual_end":120,"status":"COMPLETED","completed_task_ids":[],"recorded_by":"x"})
    assert r.status_code==400
    assert "WND" in r.json()["detail"]

def test_cancelled_requires_reason(client):
    pid, blk = setup_exec(client)
    r = client.post(f"/api/blocks/{blk}/execution", json={"actual_start":60,"actual_end":120,"status":"CANCELLED","completed_task_ids":[],"recorded_by":"eng1","service_date":"2026-09-02","reason":""})
    assert r.status_code==400
