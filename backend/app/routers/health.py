from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.exc import TimeoutError, OperationalError
from app.database import SessionLocal, get_diagnostics, engine
import concurrent.futures

router = APIRouter()

@router.get("/health")
def health():
    # Non-blocking DB check — avoid Render 502 where pool_timeout 30s > health 5s
    # Use engine.connect() with worker thread timeout <2s, return degraded quickly if pool busy
    def _db_check():
        # Use engine.connect() (pool_pre_ping handles stale) with short execution
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    fut = executor.submit(_db_check)
    try:
        # Enforce <2s wall-clock even if pool_timeout is 30s (Render health 5s)
        fut.result(timeout=1.9)
    except concurrent.futures.TimeoutError:
        # Do not wait for worker — return degraded quickly (<2s)
        try:
            fut.cancel()
        except Exception:
            pass
        try:
            executor.shutdown(wait=False, cancel_futures=True)
        except TypeError:
            # Python <3.9 fallback
            executor.shutdown(wait=False)
        return {"status": "degraded", "error": "DB pool timeout (health check <2s)", "diagnostics": {"database": "unknown", "journal_mode": "unknown", "warning": "pool busy"}}
    except (TimeoutError, OperationalError) as e:
        try:
            executor.shutdown(wait=False, cancel_futures=True)
        except TypeError:
            executor.shutdown(wait=False)
        return {"status": "degraded", "error": f"DB unavailable: {str(e)[:300]}"}
    except Exception as e:
        try:
            executor.shutdown(wait=False, cancel_futures=True)
        except TypeError:
            executor.shutdown(wait=False)
        # Any other DB error -> degraded, not 500, with quick return
        return {"status": "degraded", "error": str(e)[:300]}
    else:
        try:
            executor.shutdown(wait=False, cancel_futures=True)
        except TypeError:
            executor.shutdown(wait=False)

    # DB reachable — gather diagnostics
    try:
        diag = get_diagnostics()
    except Exception as e:
        diag = {"database": "unknown", "journal_mode": "unknown", "error": str(e)[:200]}
    # Phase 1c: expose live/database mode for ops, keep synthetic_warning
    try:
        from app.config import settings
        import os
        # settings + env fallback (tests may set env without re-instantiating settings)
        lm = bool(getattr(settings, "live_mode", False)) or os.getenv("LIVE_MODE", "").lower() in ("1", "true", "yes", "on")
        diag["live_mode"] = lm
        diag["database_mode"] = getattr(settings, "database_mode", "sqlite")
        diag["live_sources"] = getattr(settings, "live_sources", "") or os.getenv("LIVE_SOURCES", "")
    except Exception:
        pass
    # Also expose connector availability (does not enable live)
    try:
        from app.connectors.factory import list_live_connectors
        diag["available_connectors"] = list_live_connectors()
    except Exception:
        diag["available_connectors"] = []
    return {"status": "ok", "prototype": "human-approved planning and decision-support prototype", "synthetic_warning": "Synthetic prototype windows, not official railway availability.", "diagnostics": diag}

@router.get("/api/diagnostics")
def diagnostics():
    """Diagnostic function that reports DB mode - supports SQLite and Postgres."""
    from app.database import get_diagnostics as gd, get_database_mode
    d = gd()
    try:
        from app.config import settings
        import os
        live_mode = bool(getattr(settings, "live_mode", False)) or os.getenv("LIVE_MODE", "").lower() in ("1", "true", "yes", "on")
        live_sources = getattr(settings, "live_sources", "") or os.getenv("LIVE_SOURCES", "")
    except Exception:
        import os
        live_mode = os.getenv("LIVE_MODE", "").lower() in ("1", "true", "yes", "on")
        live_sources = os.getenv("LIVE_SOURCES", "")
    # Option A: additive cursor diagnostics summary (no DB write)
    cursor_summary = []
    try:
        from sqlalchemy import text as _text
        from app.database import SessionLocal as _SL
        _db = _SL()
        try:
            # Try with last_outcome, fallback without for old DB
            try:
                rows = _db.execute(_text("SELECT source_name, cursor_value, updated_at, last_success_at, last_error_at, last_error_message, fetch_attempts, fetch_successes, last_outcome FROM source_cursors")).fetchall()
                for r in rows:
                    cursor_summary.append({
                        "source_name": r[0],
                        "cursor_value": r[1],
                        "updated_at": r[2],
                        "last_success_at": r[3],
                        "last_error_at": r[4],
                        "last_error_message": r[5],
                        "fetch_attempts": r[6] or 0,
                        "fetch_successes": r[7] or 0,
                        "last_outcome": r[8],
                    })
            except Exception:
                rows = _db.execute(_text("SELECT source_name, cursor_value, updated_at, last_success_at, last_error_at, last_error_message, fetch_attempts, fetch_successes FROM source_cursors")).fetchall()
                for r in rows:
                    cursor_summary.append({
                        "source_name": r[0],
                        "cursor_value": r[1],
                        "updated_at": r[2],
                        "last_success_at": r[3],
                        "last_error_at": r[4],
                        "last_error_message": r[5],
                        "fetch_attempts": r[6] or 0,
                        "fetch_successes": r[7] or 0,
                        "last_outcome": None,
                    })
        finally:
            _db.close()
    except Exception:
        cursor_summary = []
    return {
        "database": d.get("database", "SQLite"),
        "journal_mode": d.get("journal_mode", "unknown"),
        "foreign_keys": d.get("foreign_keys", False),
        "busy_timeout": d.get("busy_timeout", 0),
        "path": d.get("path", ""),
        "database_mode": get_database_mode(),
        "live_mode": live_mode,
        "live_sources": live_sources,
        "synthetic_default": not live_mode,
        "cursor_summary": cursor_summary,
    }
