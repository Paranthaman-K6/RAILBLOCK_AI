from tests.conftest import reset_db

def test_optimizer_generates_plan(client):
    reset_db()
    # import tasks
    csv_content = """task_id,corridor_id,section_id,line_id,asset_id,task_type,description,severity,estimated_duration_minutes,requires_traffic_block,earliest_start,deadline,department
TSK-O1,COR-1,SEC-1,LIN-1,AST-1,MAINT,Test1,HIGH,60,true,2026-09-01,2026-09-10,ENGINEERING
TSK-O2,COR-1,SEC-1,LIN-1,AST-1,MAINT,Test2,HIGH,60,true,2026-09-01,2026-09-10,ENGINEERING
"""
    files = {"file": ("tasks.csv", csv_content, "text/csv")}
    client.post("/api/import/tasks", files=files, data={"source":"TMS"})
    # generate windows
    client.post("/api/windows/generate?horizon_start=2026-09-01&horizon_end=2026-09-03")
    r = client.post("/api/plans/generate", json={"horizon_start":"2026-09-01","horizon_end":"2026-09-03","horizon_type":"WEEKLY"})
    assert r.status_code==200
    j=r.json()
    assert "plan_id" in j
    assert j["solver_status"] in ["OPTIMAL","FEASIBLE","FALLBACK_USED"]

def test_invalid_solver_output_rejected(client):
    # validator should catch invalid plan
    from app.database import SessionLocal
    from app.models import BlockPlan, Block
    import uuid, datetime
    db = SessionLocal()
    plan_id = f"PLAN-{uuid.uuid4().hex[:8].upper()}"
    plan = BlockPlan(id=plan_id, horizon_type="WEEKLY", start_date="2026-09-01", end_date="2026-09-07", status="DRAFT", solver_status="OPTIMAL")
    db.add(plan)
    db.commit()
    # create invalid block (duration overflow)
    blk = Block(id=f"BLK-{uuid.uuid4().hex[:8].upper()}", plan_id=plan_id, corridor_id="COR-1", service_date="2026-09-02", start_time=60, end_time=500, block_type="TRAFFIC")
    db.add(blk)
    db.commit()
    from app.services.plan_validator import validate_plan
    val = validate_plan(db, plan_id)
    assert not val["valid"]
    assert any(v["code"]=="MAX_DURATION_EXCEEDED" for v in val["violations"])
    db.close()
