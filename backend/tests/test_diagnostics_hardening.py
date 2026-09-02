"""Option A diagnostics hardening — additive, synthetic default preserved."""
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from sqlalchemy import text
import os

client = TestClient(app)

def _reset_cursors():
    db = SessionLocal()
    try:
        db.execute(text("DELETE FROM source_cursors"))
        db.commit()
    except: pass
    finally: db.close()

def test_synthetic_default_no_live_increment():
    _reset_cursors()
    # Synthetic CSV import should not increment live fetch_attempts
    r = client.get("/api/import/live-status").json()
    assert r["live_mode"] == False
    assert r["synthetic_default"] == True
    for s in r["sources"]:
        assert s["fetch_attempts"] == 0
        assert s["fetch_successes"] == 0
        assert "last_success_at" in s
        assert "last_error_at" in s
        assert "last_error_message" in s

def test_cursor_endpoint_additive_fields():
    r = client.get("/api/import/cursor/TMS").json()
    assert "fetch_attempts" in r
    assert "fetch_successes" in r
    assert "last_success_at" in r
    assert "last_error_at" in r

def test_health_diagnostics_cursor_summary():
    r = client.get("/api/diagnostics").json()
    assert "cursor_summary" in r
    assert isinstance(r["cursor_summary"], list)
    r2 = client.get("/health").json()
    assert "diagnostics" in r2
    # health diagnostics now includes live_mode etc but still has journal_mode
    assert "journal_mode" in r2["diagnostics"]

def test_live_success_increments_diagnostics():
    _reset_cursors()
    os.environ["LIVE_MODE"] = "true"
    os.environ["LIVE_SOURCES"] = "TMS"
    os.environ["TMS_API_URL"] = "http://mock"
    os.environ["TMS_MOCK_LIVE"] = "1"
    try:
        # Clean TMS task to allow first accept
        db = SessionLocal()
        try:
            db.execute(text("DELETE FROM task_resources WHERE task_id='TSK-LIVE-001'"))
            db.execute(text("DELETE FROM tasks WHERE id='TSK-LIVE-001'"))
            db.commit()
        except: pass
        finally: db.close()
        r = client.post("/api/import/live-sync/TMS", json={"cursor": "2026-09-02T00:00:00Z"})
        assert r.status_code == 200
        assert r.json()["source_maturity"] == "LIVE_VERIFIED"
        ls = client.get("/api/import/live-status").json()
        tms = [s for s in ls["sources"] if s["source_name"] == "TMS"][0]
        assert tms["fetch_attempts"] == 1
        assert tms["fetch_successes"] == 1
        assert tms["last_success_at"] is not None
        assert tms["cursor_value"] == "2026-09-02T06:00:00Z"
        # Idempotent duplicate should still count as success attempt
        r2 = client.post("/api/import/live-sync/TMS", json={"cursor": "2026-09-02T00:00:00Z"})
        ls2 = client.get("/api/import/live-status").json()
        tms2 = [s for s in ls2["sources"] if s["source_name"] == "TMS"][0]
        assert tms2["fetch_attempts"] == 2
        assert tms2["fetch_successes"] == 2
    finally:
        for k in ["LIVE_MODE","LIVE_SOURCES","TMS_API_URL","TMS_MOCK_LIVE"]:
            os.environ.pop(k, None)

def test_live_error_increments_and_persists():
    _reset_cursors()
    os.environ["LIVE_MODE"] = "true"
    os.environ["LIVE_SOURCES"] = "SMMS"
    # No SMMS_API_URL set -> should record error
    try:
        if "SMMS_API_URL" in os.environ:
            del os.environ["SMMS_API_URL"]
        r = client.post("/api/import/live-sync/SMMS", json={})
        assert r.status_code == 400
        ls = client.get("/api/import/live-status").json()
        smms = [s for s in ls["sources"] if s["source_name"] == "SMMS"][0]
        assert smms["fetch_attempts"] == 1
        assert smms["fetch_successes"] == 0
        assert smms["last_error_at"] is not None
        assert "SMMS_API_URL" in smms["last_error_message"] or "missing" in smms["last_error_message"].lower()
        # Cursor endpoint should also expose error
        cur = client.get("/api/import/cursor/SMMS").json()
        assert cur["last_error_message"] is not None
        assert cur["fetch_attempts"] == 1
    finally:
        for k in ["LIVE_MODE","LIVE_SOURCES"]:
            os.environ.pop(k, None)
