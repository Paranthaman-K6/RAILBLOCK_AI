"""Live ingestion outcome states — FETCH_FAILED, PARSE_FAILED, EMPTY_SUCCESS, PARTIAL_SUCCESS, SUCCESS."""
import os
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from sqlalchemy import text

client = TestClient(app)

def _reset(source: str):
    db = SessionLocal()
    try:
        db.execute(text("DELETE FROM source_cursors WHERE source_name=:n"), {"n": source.upper()})
        for tbl in ["task_resources","task_dependencies"]:
            try: db.execute(text(f"DELETE FROM {tbl} WHERE task_id LIKE 'TSK-OUT-%'"))
            except: pass
        try: db.execute(text("DELETE FROM tasks WHERE id LIKE 'TSK-OUT-%'"))
        except: pass
        db.commit()
    finally:
        db.close()

def _cursor(source: str):
    return client.get(f"/api/import/cursor/{source}").json()

def test_fetch_failed_does_not_advance():
    _reset("TMS")
    # Seed success cursor
    os.environ["LIVE_MODE"]="true"
    os.environ["LIVE_SOURCES"]="TMS"
    os.environ["TMS_API_URL"]="http://mock"
    os.environ["TMS_MOCK_LIVE"]="1"
    try:
        # Use unique task to avoid duplicate from prior runs
        # First successful fetch to set cursor
        r = client.post("/api/import/live-sync/TMS", json={"cursor":"2026-09-02T00:00:00Z"})
        assert r.status_code==200
        cur_before = _cursor("TMS")["cursor_value"]
        # Now trigger FETCH_FAILED by removing URL
        del os.environ["TMS_API_URL"]
        r2 = client.post("/api/import/live-sync/TMS", json={"cursor":cur_before})
        assert r2.status_code==400
        cur_after = _cursor("TMS")["cursor_value"]
        assert cur_after == cur_before
        # last_outcome should be FETCH_FAILED
        assert _cursor("TMS")["last_outcome"] == "FETCH_FAILED"
        ls = client.get("/api/import/live-status").json()
        tms = [s for s in ls["sources"] if s["source_name"]=="TMS"][0]
        assert tms["last_outcome"] == "FETCH_FAILED"
        assert tms["fetch_attempts"] >= 1
    finally:
        for k in ["LIVE_MODE","LIVE_SOURCES","TMS_API_URL","TMS_MOCK_LIVE"]:
            os.environ.pop(k, None)
        _reset("TMS")

def test_parse_failed_does_not_advance():
    _reset("TMS")
    # Send batch where all fail due to unknown asset (parse/validation failure)
    # Need LIVE maturity to track
    r = client.post("/api/import/live-sync/TMS", json={"records":[
        {"task_id":"TSK-OUT-001","corridor_id":"COR-1","asset_id":"AST-UNKNOWN","task_type":"MAINTENANCE","department":"ENGINEERING"},
        {"task_id":"TSK-OUT-002","corridor_id":"COR-1","asset_id":"AST-UNKNOWN","task_type":"MAINTENANCE","department":"ENGINEERING"}
    ], "source_maturity":"LIVE", "cursor":"2026-09-02T00:00:00Z"})
    assert r.json()["outcome"] == "PARSE_FAILED"
    cur = _cursor("TMS")["cursor_value"]
    # Should preserve provided cursor (not advance to failed records' timestamps)
    assert cur == "2026-09-02T00:00:00Z" or cur is None or cur == "2026-09-02T00:00:00Z"
    # last_outcome should be PARSE_FAILED
    assert _cursor("TMS")["last_outcome"] == "PARSE_FAILED"

def test_empty_success_increments_without_advance():
    _reset("TMS")
    # First set a cursor
    client.post("/api/import/live-sync/TMS", json={"records":[{"task_id":"TSK-OUT-010","corridor_id":"COR-1","asset_id":"AST-1","task_type":"MAINTENANCE","department":"ENGINEERING","source_updated_at":"2026-09-02T06:00:00Z"}], "source_maturity":"LIVE", "cursor":"2026-09-01T00:00:00Z"})
    before = _cursor("TMS")
    before_cursor = before["cursor_value"]
    attempts_before = before["fetch_attempts"]
    # Empty fetch
    r = client.post("/api/import/live-sync/TMS", json={"records":[], "source_maturity":"LIVE", "cursor":before_cursor})
    assert r.json()["outcome"] == "EMPTY_SUCCESS"
    after = _cursor("TMS")
    assert after["cursor_value"] == before_cursor
    assert after["fetch_successes"] == attempts_before + 1 or after["fetch_attempts"] == attempts_before + 1
    assert after["last_outcome"] == "EMPTY_SUCCESS"

def test_partial_success_advances_to_last_persisted():
    _reset("TMS")
    batch = [
        {"task_id":"TSK-OUT-020","corridor_id":"COR-1","asset_id":"AST-1","task_type":"MAINTENANCE","department":"ENGINEERING","source_updated_at":"2026-09-02T06:00:00Z"},
        {"task_id":"TSK-OUT-021","corridor_id":"COR-1","asset_id":"AST-UNKNOWN","task_type":"MAINTENANCE","department":"ENGINEERING","source_updated_at":"2026-09-02T07:00:00Z"},
        {"task_id":"TSK-OUT-022","corridor_id":"COR-1","asset_id":"AST-1","task_type":"MAINTENANCE","department":"ENGINEERING","source_updated_at":"2026-09-02T08:00:00Z"},
    ]
    r = client.post("/api/import/live-sync/TMS", json={"records": batch, "source_maturity":"LIVE", "cursor":"2026-09-01T00:00:00Z"})
    assert r.json()["outcome"] == "PARTIAL_SUCCESS"
    assert r.json()["accepted_count"] == 2
    cur = _cursor("TMS")["cursor_value"]
    assert cur == "2026-09-02T08:00:00Z"
    assert _cursor("TMS")["last_outcome"] == "PARTIAL_SUCCESS"

def test_success_and_duplicate_idempotent():
    _reset("TMS")
    rec = {"task_id":"TSK-OUT-030","corridor_id":"COR-1","asset_id":"AST-1","task_type":"MAINTENANCE","department":"ENGINEERING","source_updated_at":"2026-09-02T09:00:00Z"}
    r1 = client.post("/api/import/live-sync/TMS", json={"records":[rec], "source_maturity":"LIVE"})
    assert r1.json()["outcome"] == "SUCCESS"
    cur1 = _cursor("TMS")["cursor_value"]
    r2 = client.post("/api/import/live-sync/TMS", json={"records":[rec], "source_maturity":"LIVE"})
    # duplicate-only should be SUCCESS (idempotent)
    assert r2.json()["outcome"] == "SUCCESS"
    assert r2.json()["duplicate_count"] == 1
    cur2 = _cursor("TMS")["cursor_value"]
    assert cur2 == cur1

def test_synthetic_default_unchanged():
    # Synthetic CSV header missing -> PARSE_FAILED but LIVE_MODE false so live counters not polluted for other source
    csv_bad = "bad,header\n1,2\n"
    r = client.post("/api/import", files={"file":("tasks.csv", csv_bad, "text/csv")}, data={"source":"TMS"})
    assert r.status_code == 200
    assert r.json()["outcome"] == "PARSE_FAILED"
    # synthetic default live_status still false
    assert client.get("/api/import/live-status").json()["live_mode"] == False
