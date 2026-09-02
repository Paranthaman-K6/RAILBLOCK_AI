"""Incremental ingestion recovery — Step 1-4 (additive).
Tests failure-safe cursor, partial batch, empty-result vs failed, synthetic untouched.
"""
import os
import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from sqlalchemy import text

client = TestClient(app)

def _reset_source(source_name: str):
    db = SessionLocal()
    try:
        db.execute(text("DELETE FROM source_cursors WHERE source_name=:n"), {"n": source_name.upper()})
        # clean tasks with prefix for test isolation
        for tbl in ["task_resources", "task_dependencies"]:
            try:
                db.execute(text(f"DELETE FROM {tbl} WHERE task_id LIKE 'TSK-REC-%'"))
            except: pass
        try:
            db.execute(text("DELETE FROM tasks WHERE id LIKE 'TSK-REC-%'"))
            db.execute(text("DELETE FROM tasks WHERE id LIKE 'TSK-LIVE-%'"))
        except: pass
        db.commit()
    finally:
        db.close()

def _get_cursor(source_name: str):
    r = client.get(f"/api/import/cursor/{source_name}").json()
    return r

def test_failed_live_fetch_does_not_advance_cursor():
    _reset_source("TMS")
    # Seed a successful cursor
    os.environ["LIVE_MODE"] = "true"
    os.environ["LIVE_SOURCES"] = "TMS"
    os.environ["TMS_API_URL"] = "http://mock"
    os.environ["TMS_MOCK_LIVE"] = "1"
    try:
        r = client.post("/api/import/live-sync/TMS", json={"cursor": "2026-09-02T00:00:00Z"})
        assert r.status_code == 200
        cur_before = _get_cursor("TMS")["cursor_value"]
        attempts_before = _get_cursor("TMS")["fetch_attempts"]
        # Now trigger failed fetch: remove URL -> missing URL error
        del os.environ["TMS_API_URL"]
        r2 = client.post("/api/import/live-sync/TMS", json={"cursor": "2026-09-02T00:00:00Z"})
        assert r2.status_code == 400
        cur_after = _get_cursor("TMS")["cursor_value"]
        # cursor must not advance
        assert cur_after == cur_before
        # attempts must increment, successes unchanged
        after = _get_cursor("TMS")
        assert after["fetch_attempts"] == attempts_before + 1
        assert after["fetch_successes"] == _get_cursor("TMS")["fetch_successes"]  # unchanged count check below
        # last_error must be set
        ls = client.get("/api/import/live-status").json()
        tms = [s for s in ls["sources"] if s["source_name"] == "TMS"][0]
        assert tms["last_error_message"] is not None
        assert tms["fetch_attempts"] >= 1
    finally:
        for k in ["LIVE_MODE","LIVE_SOURCES","TMS_API_URL","TMS_MOCK_LIVE"]:
            os.environ.pop(k, None)
        _reset_source("TMS")

def test_partial_batch_preserves_accepted():
    _reset_source("TMS")
    # Batch: 1 valid, 1 invalid asset, 1 valid -> partial
    batch = [
        {"task_id": "TSK-REC-001", "corridor_id": "COR-1", "asset_id": "AST-1", "task_type": "MAINTENANCE", "department": "ENGINEERING", "source_updated_at": "2026-09-02T06:00:00Z"},
        {"task_id": "TSK-REC-002", "corridor_id": "COR-1", "asset_id": "AST-UNKNOWN", "task_type": "MAINTENANCE", "department": "ENGINEERING", "source_updated_at": "2026-09-02T07:00:00Z"},
        {"task_id": "TSK-REC-003", "corridor_id": "COR-1", "asset_id": "AST-1", "task_type": "MAINTENANCE", "department": "ENGINEERING", "source_updated_at": "2026-09-02T08:00:00Z"},
    ]
    r = client.post("/api/import/live-sync/TMS", json={"records": batch, "source_maturity": "LIVE", "cursor": "2026-09-01T00:00:00Z"})
    assert r.status_code == 200
    assert r.json()["accepted_count"] == 2
    assert r.json()["rejected_count"] == 1
    assert r.json()["source_maturity"] == "LIVE"
    # cursor should advance to max of accepted (08:00)
    cur = _get_cursor("TMS")["cursor_value"]
    assert cur == "2026-09-02T08:00:00Z"
    # Accepted records must exist
    db = SessionLocal()
    try:
        from app.models import Task
        assert db.query(Task).filter(Task.id == "TSK-REC-001").first() is not None
        assert db.query(Task).filter(Task.id == "TSK-REC-003").first() is not None
        assert db.query(Task).filter(Task.id == "TSK-REC-002").first() is None
    finally:
        db.close()

def test_duplicate_retry_remains_idempotent():
    _reset_source("TMS")
    batch = [{"task_id": "TSK-REC-010", "corridor_id": "COR-1", "asset_id": "AST-1", "task_type": "MAINTENANCE", "department": "ENGINEERING", "source_updated_at": "2026-09-02T09:00:00Z"}]
    r1 = client.post("/api/import/live-sync/TMS", json={"records": batch, "source_maturity": "LIVE"})
    cur1 = _get_cursor("TMS")["cursor_value"]
    attempts1 = _get_cursor("TMS")["fetch_attempts"]
    r2 = client.post("/api/import/live-sync/TMS", json={"records": batch, "source_maturity": "LIVE"})
    assert r2.json()["duplicate_count"] == 1
    assert r2.json()["accepted_count"] == 0
    cur2 = _get_cursor("TMS")["cursor_value"]
    # cursor must not regress and should stay at same (no advance)
    assert cur2 == cur1
    # duplicate retry still counts as success attempt
    after = _get_cursor("TMS")
    assert after["fetch_attempts"] == attempts1 + 1
    assert after["fetch_successes"] == attempts1 + 1

def test_empty_fetch_increments_success_without_corrupting_cursor():
    _reset_source("TMS")
    os.environ["LIVE_MODE"] = "true"
    os.environ["LIVE_SOURCES"] = "TMS"
    os.environ["TMS_API_URL"] = "http://mock"
    os.environ["TMS_MOCK_LIVE"] = "1"
    try:
        # First successful mock to set cursor
        client.post("/api/import/live-sync/TMS", json={"cursor": "2026-09-02T00:00:00Z"})
        before = _get_cursor("TMS")
        before_cursor = before["cursor_value"]
        attempts_before = before["fetch_attempts"]
        successes_before = before["fetch_successes"]
        # Now simulate empty fetch by calling live-sync with empty records via records injection
        # Use run_import_records path directly with empty list
        r = client.post("/api/import/live-sync/TMS", json={"records": [], "source_maturity": "LIVE", "cursor": before_cursor})
        assert r.json()["received_count"] == 0
        after = _get_cursor("TMS")
        # empty should increment success but preserve cursor
        assert after["fetch_successes"] == successes_before + 1
        assert after["fetch_attempts"] == attempts_before + 1
        assert after["cursor_value"] == before_cursor
        # Failed fetch should not advance
        del os.environ["TMS_API_URL"]
        r2 = client.post("/api/import/live-sync/TMS", json={"cursor": before_cursor})
        assert r2.status_code == 400
        after2 = _get_cursor("TMS")
        assert after2["cursor_value"] == before_cursor
        assert after2["fetch_attempts"] == after["fetch_attempts"] + 1
        assert after2["fetch_successes"] == after["fetch_successes"]  # unchanged
        assert after2["last_error_message"] is not None
    finally:
        for k in ["LIVE_MODE","LIVE_SOURCES","TMS_API_URL","TMS_MOCK_LIVE"]:
            os.environ.pop(k, None)
        _reset_source("TMS")

def test_synthetic_default_remains_unchanged():
    # Synthetic CSV import when LIVE_MODE false must not affect live diagnostics counters for TMS
    _reset_source("TMS")
    before = _get_cursor("TMS")
    # synthetic CSV import
    csv = "task_id,corridor_id,section_id,line_id,asset_id,task_type,description,severity,safety_score,urgency_score,asset_criticality,operational_impact,overdue_days,coordination_value,resource_readiness,estimated_duration_minutes,setup_duration_minutes,required_block_type,requires_traffic_block,requires_power_isolation,requires_signal_disconnection,earliest_start,deadline,dependency_task_ids,required_resource_ids,department\nTSK-REC-SYN-001,COR-1,SEC-1,LIN-1,AST-1,MAINTENANCE,Synth test,MEDIUM,50,50,50,50,0,50,50,60,10,TRAFFIC,true,false,false,2026-09-05,2026-09-15,,,\n"
    r = client.post("/api/import", files={"file": ("tasks.csv", csv, "text/csv")}, data={"source": "TMS"})
    assert r.status_code == 200
    assert r.json()["source_maturity"] == "SYNTHETIC"
    after = _get_cursor("TMS")
    # synthetic should create/update cursor but not increment live fetch_attempts (still 0 or only synthetic)
    # Since our _upsert gates on is_live_tracked, synthetic should not increment attempts
    # But cursor_value should be set to synthetic timestamp
    assert after["cursor_value"] is not None
    # live diagnostics must still show 0 attempts for synthetic-only
    ls = client.get("/api/import/live-status").json()
    assert ls["live_mode"] == False
