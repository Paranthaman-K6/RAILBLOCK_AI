from tests.conftest import reset_db
def test_metrics(client):
    reset_db()
    csv = """task_id,corridor_id,section_id,line_id,asset_id,task_type,description,severity,estimated_duration_minutes,requires_traffic_block,earliest_start,deadline,department
TSK-M1,COR-1,SEC-1,LIN-1,AST-1,MAINT,M1,HIGH,60,true,2026-09-01,2026-09-10,ENGINEERING
"""
    files = {"file": ("tasks.csv", csv, "text/csv")}
    client.post("/api/import/tasks", files=files, data={"source":"TMS"})
    client.post("/api/windows/generate?horizon_start=2026-09-01&horizon_end=2026-09-03")
    r = client.post("/api/plans/generate", json={"horizon_start":"2026-09-01","horizon_end":"2026-09-03","horizon_type":"WEEKLY"})
    pid=r.json()["plan_id"]
    r = client.get(f"/api/metrics/{pid}")
    assert r.status_code==200
    assert "blocks" in r.json()
    assert "objective_breakdown" in r.json()
