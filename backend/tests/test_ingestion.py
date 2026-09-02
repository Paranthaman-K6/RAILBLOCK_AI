from tests.conftest import reset_db
from app.database import SessionLocal
from app.models import Corridor

def test_valid_import(client):
    reset_db()
    # ensure corridor exists
    db = SessionLocal()
    if not db.query(Corridor).filter(Corridor.id=="COR-1").first():
        db.add(Corridor(id="COR-1", name="Test"))
        db.commit()
    db.close()
    csv_content = """task_id,corridor_id,section_id,line_id,asset_id,task_type,description,severity,estimated_duration_minutes,requires_traffic_block,earliest_start,deadline,department
TSK-TEST1,COR-1,SEC-1,LIN-1,AST-1,MAINTENANCE,Test,HIGH,60,true,2026-09-01,2026-09-10,ENGINEERING
"""
    files = {"file": ("tasks.csv", csv_content, "text/csv")}
    r = client.post("/api/import/tasks", files=files, data={"source":"TMS"})
    assert r.status_code == 200
    j = r.json()
    assert j["accepted_count"] == 1
    assert j["rejected_count"] == 0

def test_missing_column(client):
    reset_db()
    csv_content = """task_id,corridor_id
TSK-1,COR-1
"""
    files = {"file": ("tasks.csv", csv_content, "text/csv")}
    r = client.post("/api/import/tasks", files=files, data={"source":"TMS"})
    j = r.json()
    # should have missing column error
    assert any(e["code"]=="MISSING_COLUMN" for e in j["errors"])

def test_invalid_date(client):
    reset_db()
    csv_content = """task_id,corridor_id,section_id,line_id,asset_id,task_type,description,severity,estimated_duration_minutes,requires_traffic_block,earliest_start,deadline,department
TSK-BAD,COR-1,SEC-1,LIN-1,AST-1,MAINTENANCE,Bad,HIGH,60,true,not-a-date,2026-09-10,ENGINEERING
"""
    files = {"file": ("tasks.csv", csv_content, "text/csv")}
    r = client.post("/api/import/tasks", files=files, data={"source":"TMS"})
    j = r.json()
    assert j["rejected_count"] == 1
    assert any(e["code"]=="INVALID_DATE" for e in j["errors"])

def test_invalid_duration(client):
    reset_db()
    csv_content = """task_id,corridor_id,section_id,line_id,asset_id,task_type,description,severity,estimated_duration_minutes,requires_traffic_block,earliest_start,deadline,department
TSK-BAD2,COR-1,SEC-1,LIN-1,AST-1,MAINTENANCE,Bad,HIGH,9999,true,2026-09-01,2026-09-10,ENGINEERING
"""
    files = {"file": ("tasks.csv", csv_content, "text/csv")}
    r = client.post("/api/import/tasks", files=files, data={"source":"TMS"})
    j = r.json()
    assert j["rejected_count"] == 1
    assert any(e["code"]=="INVALID_DURATION" for e in j["errors"])

def test_unknown_corridor(client):
    reset_db()
    csv_content = """task_id,corridor_id,section_id,line_id,asset_id,task_type,description,severity,estimated_duration_minutes,requires_traffic_block,earliest_start,deadline,department
TSK-UNK,COR-99,SEC-1,LIN-1,AST-1,MAINTENANCE,Bad,HIGH,60,true,2026-09-01,2026-09-10,ENGINEERING
"""
    files = {"file": ("tasks.csv", csv_content, "text/csv")}
    r = client.post("/api/import/tasks", files=files, data={"source":"TMS"})
    j = r.json()
    assert any(e["code"]=="UNKNOWN_CORRIDOR" for e in j["errors"])

def test_unknown_asset(client):
    reset_db()
    csv_content = """task_id,corridor_id,section_id,line_id,asset_id,task_type,description,severity,estimated_duration_minutes,requires_traffic_block,earliest_start,deadline,department
TSK-UNKA,COR-1,SEC-1,LIN-1,AST-9999,MAINTENANCE,Bad,HIGH,60,true,2026-09-01,2026-09-10,ENGINEERING
"""
    files = {"file": ("tasks.csv", csv_content, "text/csv")}
    r = client.post("/api/import/tasks", files=files, data={"source":"TMS"})
    j = r.json()
    assert any(e["code"]=="UNKNOWN_ASSET" for e in j["errors"])

def test_duplicate_import(client):
    reset_db()
    csv_content = """task_id,corridor_id,section_id,line_id,asset_id,task_type,description,severity,estimated_duration_minutes,requires_traffic_block,earliest_start,deadline,department
TSK-DUP,COR-1,SEC-1,LIN-1,AST-1,MAINTENANCE,Dup,HIGH,60,true,2026-09-01,2026-09-10,ENGINEERING
TSK-DUP,COR-1,SEC-1,LIN-1,AST-1,MAINTENANCE,Dup,HIGH,60,true,2026-09-01,2026-09-10,ENGINEERING
"""
    files = {"file": ("tasks.csv", csv_content, "text/csv")}
    r = client.post("/api/import/tasks", files=files, data={"source":"TMS"})
    j = r.json()
    assert j["duplicate_count"] >= 1

def test_idempotent_import(client):
    reset_db()
    csv_content = """task_id,corridor_id,section_id,line_id,asset_id,task_type,description,severity,estimated_duration_minutes,requires_traffic_block,earliest_start,deadline,department
TSK-IDEM,COR-1,SEC-1,LIN-1,AST-1,MAINTENANCE,Idem,HIGH,60,true,2026-09-01,2026-09-10,ENGINEERING
"""
    files = {"file": ("tasks.csv", csv_content, "text/csv")}
    r1 = client.post("/api/import/tasks", files=files, data={"source":"TMS"})
    r2 = client.post("/api/import/tasks", files=files, data={"source":"TMS"})
    assert r2.json()["duplicate_count"] >= 1
    assert r2.json()["accepted_count"] == 0
