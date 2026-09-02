from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
import json
from app.services.ingestion import run_import, run_import_records
from app.models import ImportRun

router = APIRouter(prefix="/api/import", tags=["import"])

@router.post("/tasks")
def import_tasks(file: UploadFile = File(None), source: str = Form("TMS"), db: Session = Depends(get_db)):
    return _handle(file, source, db)

@router.post("/corridors")
def import_corridors(file: UploadFile = File(None), source: str = Form("COA"), db: Session = Depends(get_db)):
    return _handle(file, source, db)

@router.post("/assets")
def import_assets(file: UploadFile = File(None), source: str = Form("COA"), db: Session = Depends(get_db)):
    return _handle(file, source, db)

@router.post("/trains")
def import_trains(file: UploadFile = File(None), source: str = Form("TIMETABLE"), db: Session = Depends(get_db)):
    return _handle(file, source, db)

@router.post("/goods-forecast")
def import_goods(file: UploadFile = File(None), source: str = Form("GOODS_FORECAST"), db: Session = Depends(get_db)):
    return _handle(file, source, db)

@router.post("/resources")
def import_resources(file: UploadFile = File(None), source: str = Form("RESOURCES"), db: Session = Depends(get_db)):
    return _handle(file, source, db)

# generic alias for tests
@router.post("")
def import_generic(file: UploadFile = File(None), source: str = Form("TMS"), db: Session = Depends(get_db)):
    return _handle(file, source, db)

def _handle(file: UploadFile, source: str, db: Session):
    content = ""
    if file:
        content = file.file.read().decode("utf-8")
    else:
        raise HTTPException(status_code=400, detail="File required")
    result = run_import(db, source, content)
    # return with status: if rejected all, return 200 but with errors; for spec, invalid should still return 200 with rejected. But missing column etc will be in errors.
    return result

@router.get("/summary")
def summary(db: Session = Depends(get_db)):
    runs = db.query(ImportRun).order_by(ImportRun.completed_at.desc()).limit(20).all()
    out = []
    for r in runs:
        base = {"import_run_id":r.id,"source_name":r.source_name,"received_count":r.received_count,"accepted_count":r.accepted_count,"rejected_count":r.rejected_count,"warning_count":r.warning_count,"duplicate_count":r.duplicate_count,"started_at":r.started_at.isoformat() if r.started_at else None,"completed_at":r.completed_at.isoformat() if r.completed_at else None}
        # Phase 1a/1b/1c provenance + outcome (backward compat if columns missing)
        try:
            base["source_maturity"] = getattr(r, "source_maturity", "SYNTHETIC") or "SYNTHETIC"
            base["cursor_value"] = getattr(r, "cursor_value", None)
            base["outcome"] = getattr(r, "outcome", None)
        except Exception:
            pass
        out.append(base)
    return out

# Phase 1a/1b — Live connector status & incremental sync (feature-flagged, defaults to synthetic)
# Placed before generic /{import_run_id} to avoid route shadowing
@router.get("/live-status")
def live_status(db: Session = Depends(get_db)):
    try:
        from app.connectors.factory import list_live_connectors, get_live_connector
        from app.config import settings
        import os
        live_mode = bool(getattr(settings, "live_mode", False)) or os.getenv("LIVE_MODE","").lower() in ("1","true","yes","on")
    except Exception:
        import os
        live_mode = os.getenv("LIVE_MODE","").lower() in ("1","true","yes","on")
        list_live_connectors = lambda: []
        get_live_connector = lambda x: None
    sources = []
    try:
        for name in list_live_connectors():
            conn = get_live_connector(name)
            enabled = False
            try:
                enabled = conn.is_enabled() if conn else False
            except Exception:
                enabled = False
            cur = None
            last_fetch = None
            last_error = None
            last_run_id = None
            last_success_at = None
            last_error_at = None
            last_error_message = None
            last_outcome = None
            fetch_attempts = 0
            fetch_successes = 0
            try:
                # Option A/B: read full diagnostics from source_cursors (outcome additive)
                try:
                    cur_row = db.execute(text("SELECT cursor_value, updated_at, last_success_at, last_error_at, last_error_message, fetch_attempts, fetch_successes, last_outcome FROM source_cursors WHERE source_name=:n"), {"n": name.upper()}).fetchone()
                except Exception:
                    cur_row = db.execute(text("SELECT cursor_value, updated_at, last_success_at, last_error_at, last_error_message, fetch_attempts, fetch_successes FROM source_cursors WHERE source_name=:n"), {"n": name.upper()}).fetchone()
                if cur_row:
                    cur = cur_row[0]
                    last_fetch = cur_row[1]
                    last_success_at = cur_row[2] if len(cur_row) > 2 else None
                    last_error_at = cur_row[3] if len(cur_row) > 3 else None
                    last_error_message = cur_row[4] if len(cur_row) > 4 else None
                    fetch_attempts = (cur_row[5] or 0) if len(cur_row) > 5 else 0
                    fetch_successes = (cur_row[6] or 0) if len(cur_row) > 6 else 0
                    last_outcome = cur_row[7] if len(cur_row) > 7 else None
                    # fallback last_error for legacy rows
                    last_error = last_error_message
                    # also capture last ImportRun id for trace
                    ir = db.query(ImportRun).filter(ImportRun.source_name==name.upper()).order_by(ImportRun.completed_at.desc()).first()
                    if ir:
                        last_run_id = ir.id
                        if not last_error:
                            try:
                                errs = json.loads(ir.errors) if ir.errors else []
                                if errs:
                                    last_error = errs[0].get("message") or errs[0].get("code")
                                    last_error_message = last_error
                            except Exception:
                                last_error = None
                else:
                    # fallback to latest ImportRun
                    ir = db.query(ImportRun).filter(ImportRun.source_name==name.upper()).order_by(ImportRun.completed_at.desc()).first()
                    if ir:
                        cur = getattr(ir, "cursor_value", None)
                        last_fetch = ir.completed_at.isoformat() if ir.completed_at else None
                        last_run_id = ir.id
                        # surface first error if any (without leaking full traceback)
                        try:
                            errs = json.loads(ir.errors) if ir.errors else []
                            if errs:
                                last_error = errs[0].get("message") or errs[0].get("code")
                                last_error_message = last_error
                        except Exception:
                            last_error = None
            except Exception:
                # table missing columns on old DB — fallback to minimal
                try:
                    cur_row = db.execute(text("SELECT cursor_value, updated_at FROM source_cursors WHERE source_name=:n"), {"n": name.upper()}).fetchone()
                    if cur_row:
                        cur = cur_row[0]
                        last_fetch = cur_row[1]
                except Exception:
                    cur = None
            # URL presence for ops visibility
            url_present = False
            try:
                import os as _os
                # Check concrete env vars
                for ev in [f"{name}_API_URL", f"{name.replace('-','_')}_API_URL", "TIMETABLE_API_URL", "NTES_API_URL", "GOODS_API_URL", "FOIS_API_URL"]:
                    if _os.getenv(ev):
                        url_present = True
                        break
            except Exception:
                pass
            sources.append({
                "source_name": name,
                "live_mode": live_mode,
                "connector_available": conn is not None,
                "connector_enabled": enabled,
                "url_present": url_present,
                "cursor_value": cur,
                "maturity": conn.maturity if conn else "SYNTHETIC",
                "last_fetch_at": last_fetch,
                "last_success_at": last_success_at,
                "last_error_at": last_error_at,
                "last_error_message": last_error_message,
                "last_outcome": last_outcome,
                "last_import_run_id": last_run_id,
                "last_error": last_error,
                "fetch_attempts": fetch_attempts,
                "fetch_successes": fetch_successes,
            })
    except Exception as e:
        return {"live_mode": live_mode, "error": str(e), "sources": []}
    try:
        from app.database import get_database_mode
        db_mode = get_database_mode()
    except Exception:
        db_mode = "sqlite"
    return {"live_mode": live_mode, "synthetic_default": not live_mode, "database_mode": db_mode, "sources": sources}

@router.get("/cursor/{source_name}")
def get_cursor(source_name: str, db: Session = Depends(get_db)):
    try:
        # Option A/B: return full diagnostics if available (outcome additive)
        try:
            row = db.execute(text("SELECT cursor_value, updated_at, last_success_at, last_error_at, last_error_message, fetch_attempts, fetch_successes, last_outcome FROM source_cursors WHERE source_name=:n"), {"n": source_name.upper()}).fetchone()
            if row:
                return {
                    "source_name": source_name.upper(),
                    "cursor_value": row[0],
                    "updated_at": row[1],
                    "last_success_at": row[2],
                    "last_error_at": row[3],
                    "last_error_message": row[4],
                    "fetch_attempts": row[5] or 0,
                    "fetch_successes": row[6] or 0,
                    "last_outcome": row[7],
                }
        except Exception:
            row = None
        try:
            row = db.execute(text("SELECT cursor_value, updated_at, last_success_at, last_error_at, last_error_message, fetch_attempts, fetch_successes FROM source_cursors WHERE source_name=:n"), {"n": source_name.upper()}).fetchone()
            if row:
                return {
                    "source_name": source_name.upper(),
                    "cursor_value": row[0],
                    "updated_at": row[1],
                    "last_success_at": row[2],
                    "last_error_at": row[3],
                    "last_error_message": row[4],
                    "fetch_attempts": row[5] or 0,
                    "fetch_successes": row[6] or 0,
                    "last_outcome": None,
                }
        except Exception:
            row = None
        row = db.execute(text("SELECT cursor_value, updated_at FROM source_cursors WHERE source_name=:n"), {"n": source_name.upper()}).fetchone()
        if not row:
            # fallback to latest ImportRun cursor
            ir = db.query(ImportRun).filter(ImportRun.source_name == source_name.upper()).order_by(ImportRun.completed_at.desc()).first()
            cur = getattr(ir, "cursor_value", None) if ir else None
            outcome = getattr(ir, "outcome", None) if ir else None
            return {"source_name": source_name.upper(), "cursor_value": cur, "updated_at": ir.completed_at.isoformat() if ir and ir.completed_at else None, "last_success_at": None, "last_error_at": None, "last_error_message": None, "fetch_attempts": 0, "fetch_successes": 0, "last_outcome": outcome}
        return {"source_name": source_name.upper(), "cursor_value": row[0], "updated_at": row[1], "last_success_at": None, "last_error_at": None, "last_error_message": None, "fetch_attempts": 0, "fetch_successes": 0, "last_outcome": None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/live-sync/{source_name}")
def live_sync(source_name: str, payload: dict = {}, db: Session = Depends(get_db)):
    """
    Feature-flagged live sync: fetch via connector then incremental import.
    Body may contain {"records": [...]} for testing without live URL, or {"cursor": "2026-09-02T..."}.
    Preserves prototype behavior: if LIVE_MODE off and no records provided, returns 400 with guidance.
    """
    from app.connectors.factory import get_live_connector, should_use_live
    # Allow test injection of records even when live_mode off for validation
    records = payload.get("records") if isinstance(payload, dict) else None
    cursor = payload.get("cursor") if isinstance(payload, dict) else None
    # If records provided directly, use incremental path (test/live mock)
    if isinstance(records, list):
        # Enforce source_maturity tagging
        maturity = payload.get("source_maturity") if isinstance(payload, dict) else None
        result = run_import_records(db, source_name, records, user_id=payload.get("user_id","live_sync") if isinstance(payload, dict) else "live_sync", cursor_value=cursor, source_maturity=maturity)
        return result
    # No records: try live connector fetch
    conn = get_live_connector(source_name)
    if conn is None:
        raise HTTPException(status_code=400, detail=f"Live sync not enabled for {source_name}. Set LIVE_MODE=true and LIVE_SOURCES. Synthetic prototype remains default. Provide records in body for dry-run.")
    try:
        if not conn.is_enabled():
            # Record attempt without advancing cursor — explicit FETCH_FAILED outcome
            try:
                from app.services.ingestion import _record_cursor_error, OUTCOME_FETCH_FAILED
                _record_cursor_error(db, source_name, f"missing {source_name}_API_URL", maturity=conn.maturity if conn else None, outcome=OUTCOME_FETCH_FAILED)
            except Exception:
                pass
            raise HTTPException(status_code=400, detail=f"Connector {source_name} not configured (missing {source_name}_API_URL). Set env or provide records for dry-run.")
        fetched = conn.fetch(cursor=cursor)
        if not fetched:
            # Empty fetch is still a successful attempt (no new records) — outcome EMPTY_SUCCESS
            try:
                from app.services.ingestion import _upsert_cursor, OUTCOME_EMPTY_SUCCESS
                _upsert_cursor(db, source_name, cursor, success=True, maturity=conn.maturity, outcome=OUTCOME_EMPTY_SUCCESS)
                db.commit()
            except Exception:
                pass
            return {"source_name": source_name.upper(), "received_count": 0, "accepted_count": 0, "message": "No new records at cursor", "cursor_value": cursor, "source_maturity": conn.maturity, "outcome": "EMPTY_SUCCESS"}
        result = run_import_records(db, source_name, fetched, user_id="live_sync", cursor_value=cursor, source_maturity=conn.maturity)
        return result
    except HTTPException:
        raise
    except NotImplementedError as e:
        try:
            from app.services.ingestion import _record_cursor_error, OUTCOME_FETCH_FAILED
            _record_cursor_error(db, source_name, str(e), maturity=conn.maturity if conn else None, outcome=OUTCOME_FETCH_FAILED)
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        try:
            from app.services.ingestion import _record_cursor_error, OUTCOME_FETCH_FAILED
            _record_cursor_error(db, source_name, str(e), maturity=conn.maturity if conn else None, outcome=OUTCOME_FETCH_FAILED)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Live sync failed: {e}")

@router.get("/{import_run_id}")
def get_import(import_run_id: str, db: Session = Depends(get_db)):
    r = db.query(ImportRun).filter(ImportRun.id==import_run_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Import run not found")
    base = {"import_run_id":r.id,"source_name":r.source_name,"received_count":r.received_count,"accepted_count":r.accepted_count,"rejected_count":r.rejected_count,"warning_count":r.warning_count,"duplicate_count":r.duplicate_count,"errors":json.loads(r.errors) if r.errors else [],"warnings":json.loads(r.warnings) if r.warnings else [],"started_at":r.started_at.isoformat() if r.started_at else None,"completed_at":r.completed_at.isoformat() if r.completed_at else None}
    try:
        base["source_maturity"] = getattr(r, "source_maturity", "SYNTHETIC") or "SYNTHETIC"
        base["source_hash"] = getattr(r, "source_hash", None)
        base["cursor_value"] = getattr(r, "cursor_value", None)
        base["outcome"] = getattr(r, "outcome", None)
    except Exception:
        pass
    return base
