from fastapi.testclient import TestClient
from app.main import app
import io

client = TestClient(app)

def test_health():
    r = client.get("/health")
    print("health", r.status_code, r.json())
    assert r.status_code==200

def test_import_corridor():
    # import corridors via generic?
    csv_content = """corridor_id,corridor_name,section_id,section_name,line_id,line_type,asset_id,asset_type
COR-1,Delhi,SEC-1,Ghaziabad,LIN-1,UP,AST-1,TRACK
COR-3,New,SEC-10,NewSec,LIN-10,UP,AST-10,TRACK
"""
    files = {"file": ("corridors.csv", csv_content, "text/csv")}
    r = client.post("/api/import/corridors", files=files, data={"source":"COA"})
    print("import corridors", r.status_code, r.json())
    # assert

def test_import_task_valid():
    csv_content = """task_id,corridor_id,section_id,line_id,asset_id,task_type,description,severity,estimated_duration_minutes,requires_traffic_block,earliest_start,deadline,department,safety_score,urgency_score,asset_criticality
TSK-100,COR-1,SEC-1,LIN-1,AST-1,MAINTENANCE,Fix track,HIGH,60,true,2026-09-01,2026-09-10,ENGINEERING,90,80,85
TSK-101,COR-1,SEC-1,LIN-1,AST-1,INSPECTION,Inspect,LOW,30,true,2026-09-01,2026-09-10,ENGINEERING,50,50,50
"""
    files = {"file": ("tasks.csv", csv_content, "text/csv")}
    r = client.post("/api/import/tasks", files=files, data={"source":"TMS"})
    print("import tasks valid", r.status_code, r.json())
    return r.json()

def test_import_task_invalid():
    csv_content = """task_id,corridor_id,section_id,line_id,asset_id,task_type,description,severity,estimated_duration_minutes,requires_traffic_block,earliest_start,deadline,department
TSK-200,COR-99,SEC-1,LIN-1,AST-999,BAD,Desc,MEDIUM,60,true,2026-09-01,2026-09-10,ENGINEERING
"""
    files = {"file": ("tasks.csv", csv_content, "text/csv")}
    r = client.post("/api/import/tasks", files=files, data={"source":"TMS"})
    print("import invalid corridor", r.status_code, r.json())

def test_windows():
    # generate windows
    from app.services.candidate_windows import generate_candidate_windows
    from app.database import SessionLocal
    db = SessionLocal()
    # ensure windows exist
    r = client.get("/api/windows")
    print("windows", len(r.json()))
    # try generate via API
    r = client.post("/api/windows/generate?horizon_start=2026-09-01&horizon_end=2026-09-07")
    print("gen windows", r.json())

def test_plan_generate():
    r = client.post("/api/plans/generate", json={"horizon_start":"2026-09-01","horizon_end":"2026-09-07","horizon_type":"WEEKLY"})
    print("plan generate", r.status_code, r.json())
    if r.status_code==200:
        return r.json()["plan_id"]
    else:
        print(r.text)
        return None

def test_all():
    test_health()
    test_import_corridor()
    # windows first
    test_windows()
    plan_before = test_plan_generate()
    print("plan_before", plan_before)
    # now tasks
    test_import_task_valid()
    test_import_task_invalid()
    r = client.get("/api/tasks")
    print("tasks count", len(r.json()))
    # generate again
    pid = test_plan_generate()
    print("pid", pid)
    if pid:
        r = client.get(f"/api/plans/{pid}")
        print("get plan", r.status_code, r.json().keys() if r.status_code==200 else r.text[:500])
        # submit review
        r = client.post(f"/api/plans/{pid}/submit-review")
        print("submit", r.status_code, r.json() if r.status_code==200 else r.text[:500])
        # approve
        r = client.post(f"/api/plans/{pid}/approve", json={"approver_id":"officer1","approver_role":"CONTROL_OFFICE","reason":"Approved"})
        print("approve", r.status_code, r.json() if r.status_code==200 else r.text[:500])
        # department view
        r = client.get(f"/api/plans/{pid}/department-view?department=ENGINEERING")
        print("dept view", r.status_code, r.json().keys() if r.status_code==200 else r.text[:500])
        # execution
        # get first block
        plan_data = client.get(f"/api/plans/{pid}").json()
        if plan_data["blocks"]:
            blk = plan_data["blocks"][0]["block_id"]
            r = client.post(f"/api/blocks/{blk}/execution", json={"actual_start":60,"actual_end":120,"status":"COMPLETED","completed_task_ids":[plan_data["blocks"][0]["tasks"][0]["task_id"] if plan_data["blocks"][0]["tasks"] else "TSK-100"],"recorded_by":"engineer1","reason":"","service_date":"2026-09-02"})
            print("execution", r.status_code, r.json() if r.status_code <400 else r.text[:500])
            # duplicate
            r2 = client.post(f"/api/blocks/{blk}/execution", json={"actual_start":60,"actual_end":120,"status":"COMPLETED","completed_task_ids":[plan_data["blocks"][0]["tasks"][0]["task_id"] if plan_data["blocks"][0]["tasks"] else "TSK-100"],"recorded_by":"engineer1","reason":"","service_date":"2026-09-02"})
            print("duplicate", r2.status_code, r2.json() if r2.status_code <500 else r2.text[:500])
            # invalid WND
            r3 = client.post(f"/api/blocks/WND-12345678/execution", json={"actual_start":60,"actual_end":120,"status":"COMPLETED","completed_task_ids":[],"recorded_by":"x"})
            print("wnd error", r3.status_code, r3.json() if r3.status_code else r3.text[:500])
        # metrics
        r = client.get(f"/api/metrics/{pid}")
        print("metrics", r.status_code, list(r.json().keys())[:10] if r.status_code==200 else r.text[:500])

test_all()
