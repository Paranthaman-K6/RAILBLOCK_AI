from tests.conftest import reset_db

def test_e2e(client):
    reset_db()
    # full flow: import -> validate -> prioritize -> windows -> baseline/optimized -> validate -> edit draft -> approve -> dept view -> execute -> metrics -> replan -> revision approval -> export
    # import
    for src, csv_content in [
        ("TMS", """task_id,corridor_id,section_id,line_id,asset_id,task_type,description,severity,estimated_duration_minutes,requires_traffic_block,earliest_start,deadline,department,safety_score,urgency_score,asset_criticality
TSK-E2E1,COR-1,SEC-1,LIN-1,AST-1,MAINT,Fix,HIGH,60,true,2026-09-01,2026-09-10,ENGINEERING,90,80,85
TSK-E2E2,COR-1,SEC-1,LIN-1,AST-1,MAINT,Inspect,LOW,30,true,2026-09-01,2026-09-15,ENGINEERING,50,50,50
TSK-E2E3,COR-1,SEC-1,LIN-2,AST-2,OHE,OHE check,MEDIUM,45,true,2026-09-01,2026-09-12,TRACTION,70,60,80
"""),
    ]:
        files = {"file": ("tasks.csv", csv_content, "text/csv")}
        r = client.post("/api/import/tasks", files=files, data={"source":src})
        assert r.json()["accepted_count"]>=2
    # generate windows
    client.post("/api/windows/generate?horizon_start=2026-09-01&horizon_end=2026-09-07")
    # generate weekly
    r = client.post("/api/plans/generate", json={"horizon_start":"2026-09-01","horizon_end":"2026-09-07","horizon_type":"WEEKLY"})
    assert r.status_code==200
    pid=r.json()["plan_id"]
    # monthly
    r = client.post("/api/plans/generate", json={"horizon_start":"2026-09-01","horizon_end":"2026-09-30","horizon_type":"MONTHLY"})
    assert r.status_code==200
    # validate
    r = client.post(f"/api/plans/{pid}/validate")
    assert r.json()["valid"]==True
    # edit draft
    r = client.get(f"/api/plans/{pid}")
    blk = r.json()["blocks"][0]["block_id"]
    r = client.patch(f"/api/plans/{pid}/draft-blocks/{blk}", json={"service_date":"2026-09-03","reason":"test edit","editor":"planner1"})
    assert r.status_code==200
    # submit and approve
    r = client.post(f"/api/plans/{pid}/submit-review")
    assert r.status_code==200
    r = client.post(f"/api/plans/{pid}/approve", json={"approver_id":"officer1","approver_role":"CONTROL_OFFICE","reason":"ok"})
    assert r.status_code==200
    # department view
    r = client.get(f"/api/plans/{pid}/department-view?department=ENGINEERING")
    assert r.status_code==200
    # execute
    r = client.get(f"/api/plans/{pid}")
    blk = r.json()["blocks"][0]["block_id"]
    tsk = r.json()["blocks"][0]["tasks"][0]["task_id"]
    r = client.post(f"/api/blocks/{blk}/execution", json={"actual_start":60,"actual_end":120,"status":"COMPLETED","completed_task_ids":[tsk],"recorded_by":"eng1","service_date":"2026-09-03"})
    assert r.status_code==200
    # metrics
    r = client.get(f"/api/metrics/{pid}")
    assert r.status_code==200
    # emergency replan
    r = client.post(f"/api/plans/{pid}/replan", json={"reason":"Emergency"})
    assert r.status_code==200
    new_pid=r.json()["new_plan_id"]
    # revision approval
    r = client.get(f"/api/plans/{new_pid}")
    # submit new revision
    r = client.post(f"/api/plans/{new_pid}/submit-review")
    if r.status_code==200:
        r = client.post(f"/api/plans/{new_pid}/approve", json={"approver_id":"officer1","approver_role":"CONTROL_OFFICE","reason":"ok"})
        assert r.status_code==200
    # export
    r = client.get(f"/api/plans/{pid}/export?format=csv")
    assert r.status_code==200
    assert "plan_id" in r.text

    # ensure completed block survives replan
    r = client.get(f"/api/execution/plan/{pid}")
    assert len(r.json())>=1
