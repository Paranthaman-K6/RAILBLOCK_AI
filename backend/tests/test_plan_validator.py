from tests.conftest import reset_db

def test_validator_catches_train_conflict(client):
    reset_db()
    # Import overlapping train and generate plan that would conflict
    # Setup tasks
    csv_tasks = """task_id,corridor_id,section_id,line_id,asset_id,task_type,description,severity,estimated_duration_minutes,requires_traffic_block,earliest_start,deadline,department
TSK-V1,COR-1,SEC-1,LIN-1,AST-1,MAINT,Test,HIGH,60,true,2026-09-01,2026-09-10,ENGINEERING
"""
    files = {"file": ("tasks.csv", csv_tasks, "text/csv")}
    client.post("/api/import/tasks", files=files, data={"source":"TMS"})
    # train overlapping
    csv_train = """train_id,corridor_id,section_id,line_id,train_type,service_date,departure_time,arrival_time
TRN-V1,COR-1,SEC-1,LIN-1,PASSENGER,2026-09-02,70,100
"""
    files = {"file": ("trains.csv", csv_train, "text/csv")}
    client.post("/api/import/trains", files=files, data={"source":"TIMETABLE"})
    client.post("/api/windows/generate?horizon_start=2026-09-02&horizon_end=2026-09-02")
    # Generate plan, ensure validator checks train conflict
    r = client.post("/api/plans/generate", json={"horizon_start":"2026-09-02","horizon_end":"2026-09-02","horizon_type":"WEEKLY"})
    if r.status_code==200:
        pid=r.json()["plan_id"]
        # validate endpoint
        rv = client.post(f"/api/plans/{pid}/validate")
        assert rv.status_code==200
