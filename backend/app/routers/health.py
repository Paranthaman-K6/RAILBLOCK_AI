from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.exc import TimeoutError, OperationalError
from app.database import SessionLocal, get_diagnostics, engine, is_postgres, get_database_mode
import concurrent.futures

router = APIRouter()

def _fast_diag(reason: str = "pool busy"):
    """Fallback diagnostics without DB round-trip — reports correct DB type even when pool busy."""
    pg = is_postgres()
    mode = get_database_mode()
    return {
        "database": "PostgreSQL" if pg else "SQLite",
        "database_mode": mode,
        "journal_mode": "n/a (postgres)" if pg else "unknown",
        "foreign_keys": True if pg else False,
        "path": "pooled ap-southeast-1" if pg else "railblock.db",
        "warning": reason,
    }

@router.get("/health")
def health():
    # Non-blocking DB check — avoid Render 502 where pool_timeout 5s > health 1.9s
    # Use engine.connect() with worker thread timeout <2s, return degraded quickly if pool busy
    # Always report correct database type (PostgreSQL vs SQLite) even in degraded.
    def _db_check():
        # Use engine.connect() (pool_pre_ping handles stale) with short execution
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    fut = executor.submit(_db_check)
    try:
        # Enforce <2s wall-clock even if pool_timeout is 5s (Render health 5s)
        fut.result(timeout=1.9)
    except concurrent.futures.TimeoutError:
        # Do not wait for worker — return degraded quickly (<2s) but with correct DB label
        try:
            fut.cancel()
        except Exception:
            pass
        try:
            executor.shutdown(wait=False, cancel_futures=True)
        except TypeError:
            # Python <3.9 fallback
            executor.shutdown(wait=False)
        diag = _fast_diag("pool busy — health check <2s")
        diag["live_mode"] = False
        try:
            from app.config import settings
            import os
            lm = bool(getattr(settings, "live_mode", False)) or os.getenv("LIVE_MODE", "").lower() in ("1", "true", "yes", "on")
            diag["live_mode"] = lm
            diag["database_mode"] = getattr(settings, "database_mode", diag["database_mode"])
        except Exception:
            pass
        return {"status": "degraded", "error": "DB pool timeout (health check <2s)", "diagnostics": diag}
    except (TimeoutError, OperationalError) as e:
        try:
            executor.shutdown(wait=False, cancel_futures=True)
        except TypeError:
            executor.shutdown(wait=False)
        diag = _fast_diag(f"DB unavailable: {str(e)[:120]}")
        return {"status": "degraded", "error": f"DB unavailable: {str(e)[:300]}", "diagnostics": diag}
    except Exception as e:
        try:
            executor.shutdown(wait=False, cancel_futures=True)
        except TypeError:
            executor.shutdown(wait=False)
        # Any other DB error -> degraded, not 500, with quick return but correct DB label
        diag = _fast_diag(str(e)[:120])
        return {"status": "degraded", "error": str(e)[:300], "diagnostics": diag}
    else:
        try:
            executor.shutdown(wait=False, cancel_futures=True)
        except TypeError:
            executor.shutdown(wait=False)

    # DB reachable — gather diagnostics with timeout so health never hangs on postgres version query
    diag = None
    try:
        # get_diagnostics itself does a DB connect (SELECT version) which could block pool_timeout; guard with 1.8s
        inner_ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        inner_fut = inner_ex.submit(get_diagnostics)
        try:
            diag = inner_fut.result(timeout=1.8)
        except concurrent.futures.TimeoutError:
            try:
                inner_fut.cancel()
            except Exception:
                pass
            diag = _fast_diag("diagnostics timeout — DB reachable but version query slow")
        finally:
            try:
                inner_ex.shutdown(wait=False, cancel_futures=True)
            except TypeError:
                inner_ex.shutdown(wait=False)
    except Exception as e:
        diag = _fast_diag(str(e)[:120])
        diag["error"] = str(e)[:200]
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
    """Diagnostic function that reports DB mode - supports SQLite and Postgres. Timeout-guarded to avoid hanging on pooled postgres."""
    from app.database import get_diagnostics as gd, get_database_mode
    import concurrent.futures as _cf
    d = None
    try:
        # Guard get_diagnostics with timeout — pooled postgres SELECT version could block pool_timeout
        _ex = _cf.ThreadPoolExecutor(max_workers=1)
        _fut = _ex.submit(gd)
        try:
            d = _fut.result(timeout=2.0)
        except _cf.TimeoutError:
            try:
                _fut.cancel()
            except Exception:
                pass
            # Fallback without DB round-trip but correct type
            from app.database import is_postgres as _is_pg
            pg = _is_pg()
            d = {"database": "PostgreSQL" if pg else "SQLite", "journal_mode": "n/a (postgres)" if pg else "unknown", "foreign_keys": True if pg else False, "busy_timeout": 0, "path": "pooled ap-southeast-1" if pg else "railblock.db", "warning": "diagnostics timeout — pool busy"}
        finally:
            try:
                _ex.shutdown(wait=False, cancel_futures=True)
            except TypeError:
                _ex.shutdown(wait=False)
    except Exception as _e:
        from app.database import is_postgres as _is_pg
        pg = _is_pg()
        d = {"database": "PostgreSQL" if pg else "SQLite", "journal_mode": "unknown", "foreign_keys": False, "busy_timeout": 0, "path": "railblock.db", "error": str(_e)[:200]}
    if d is None:
        from app.database import is_postgres as _is_pg
        pg = _is_pg()
        d = {"database": "PostgreSQL" if pg else "SQLite", "journal_mode": "unknown", "foreign_keys": False, "busy_timeout": 0, "path": "railblock.db"}
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
