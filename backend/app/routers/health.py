from fastapi import APIRouter, Request
from sqlalchemy import text
from sqlalchemy.exc import TimeoutError, OperationalError
from app.database import SessionLocal, get_diagnostics, engine, is_postgres, get_database_mode
import concurrent.futures

# Frontend backend URL wiring — mirrors frontend/src/services/api.ts:7 RENDER_FALLBACK
# When VITE_API_URL is empty on Vercel prod, frontend falls back to this backend.
RENDER_FALLBACK = "https://railblock-ai.getvoroa.com"
LEGACY_FALLBACK = "https://railblock-ai-up0g.onrender.com"


def _frontend_backend_urls(request: Request) -> tuple[str, str]:
    """Return (backend_url from request, frontend_connected_to effective)."""
    try:
        # Use request.base_url (includes scheme+host from X-Forwarded-Proto/Host via uvicorn proxy)
        backend_url = str(request.base_url).rstrip("/")
        # Prefer X-Forwarded-Host/Proto when behind Voroa/Vercel proxy (more accurate public URL)
        xf_host = request.headers.get("x-forwarded-host") or request.headers.get("host")
        xf_proto = request.headers.get("x-forwarded-proto")
        if xf_host and xf_proto:
            # xf_host may include port; use as-is
            backend_url = f"{xf_proto}://{xf_host}".rstrip("/")
        elif xf_host and backend_url:
            # if proto missing, keep backend_url scheme
            pass
        # Frontend effective backend: same-origin on Voroa (getvoroa.com), fallback on Vercel (vercel.app)
        # Mirrors frontend/src/services/api.ts:13-22 logic
        host = (request.headers.get("host") or "").lower()
        origin = (request.headers.get("origin") or "").lower()
        url_host = backend_url.lower()
        is_voroa = "getvoroa.com" in url_host or "getvoroa.com" in host or "getvoroa.com" in origin
        is_vercel = "vercel.app" in host or "vercel.app" in origin or "vercel.app" in url_host
        # Voroa single-image: frontend uses same-origin -> backend_url itself
        if is_voroa:
            frontend_connected_to = backend_url
        elif is_vercel:
            # Vercel split deployment: empty VITE_API_URL falls back to RENDER_FALLBACK per api.ts:21
            frontend_connected_to = RENDER_FALLBACK
        else:
            # Local dev (localhost) or direct API calls: frontend would use same origin via vite proxy or fallback
            if "localhost" in backend_url or "127.0.0.1" in backend_url:
                frontend_connected_to = backend_url
            else:
                frontend_connected_to = RENDER_FALLBACK
        return backend_url, frontend_connected_to
    except Exception:
        # Fallback safe
        try:
            bu = str(request.base_url).rstrip("/") if request else RENDER_FALLBACK
        except Exception:
            bu = RENDER_FALLBACK
        return bu, RENDER_FALLBACK

router = APIRouter()

# Simple 5s cache for diagnostics to avoid polling storm on Render free + Vercel 30s interval
_diag_cache: dict = {"ts": 0.0, "data": None}
import time as _time
# Auth-failure backoff: avoid hammering Supabase pooler after password failure → ECIRCUITBREAKER
_auth_backoff: dict = {"last_failure_ts": 0.0, "failure_count": 0}
_AUTH_COOLDOWN_SEC = 30
def _should_backoff() -> bool:
    return (_time.time() - _auth_backoff["last_failure_ts"]) < _AUTH_COOLDOWN_SEC and _auth_backoff["failure_count"] > 0
def _record_auth_failure(is_auth: bool):
    if is_auth:
        _auth_backoff["last_failure_ts"] = _time.time()
        _auth_backoff["failure_count"] = min(_auth_backoff["failure_count"] + 1, 5)
    else:
        # non-auth errors decay slowly
        if _time.time() - _auth_backoff["last_failure_ts"] > _AUTH_COOLDOWN_SEC * 2:
            _auth_backoff["failure_count"] = 0
def _cached_diag(max_age: float = 5.0):
    now = _time.time()
    if _diag_cache["data"] is not None and (now - _diag_cache["ts"]) < max_age:
        return _diag_cache["data"]
    try:
        d = get_diagnostics()
        _diag_cache["data"] = d
        _diag_cache["ts"] = now
        return d
    except Exception as e:
        # don't cache errors
        raise

def _fast_diag(reason: str = "pool busy"):
    """Fallback diagnostics without DB round-trip — reports correct DB type even when pool busy."""
    from app.database import is_mysql
    pg = is_postgres()
    my = is_mysql()
    mode = get_database_mode()
    if pg:
        db_label = "PostgreSQL"
        jm = "n/a (postgres)"
        path = "pooled ap-southeast-1"
    elif my:
        db_label = "MySQL"
        jm = "n/a (mysql)"
        path = "aiven mysql"
    else:
        db_label = "SQLite"
        jm = "unknown"
        path = "railblock.db"
    return {
        "database": db_label,
        "database_mode": mode,
        "journal_mode": jm,
        "foreign_keys": True if (pg or my) else False,
        "path": path,
        "warning": reason,
    }

@router.get("/health")
def health(request: Request):
    # Frontend backend wiring — always expose which backend URL frontend would connect to
    backend_url, frontend_connected_to = _frontend_backend_urls(request)
    # Backoff guard: if recent password auth failure → ECIRCUITBREAKER, suppress DB attempts for _AUTH_COOLDOWN_SEC to avoid hammering pooler
    if _should_backoff():
        diag = _fast_diag(f"auth backoff — Supabase pooler cooldown {_AUTH_COOLDOWN_SEC}s (too many auth failures, check DATABASE_URL password and pooled 6543)")
        diag["live_mode"] = False
        try:
            from app.config import settings
            import os
            lm = bool(getattr(settings, "live_mode", False)) or os.getenv("LIVE_MODE", "").lower() in ("1", "true", "yes", "on")
            diag["live_mode"] = lm
            diag["database_mode"] = getattr(settings, "database_mode", diag["database_mode"])
        except Exception:
            pass
        # Add frontend backend wiring to diagnostics + top-level
        diag["backend_url"] = backend_url
        diag["frontend_connected_to"] = frontend_connected_to
        diag["frontend_api_base"] = frontend_connected_to
        return {"status": "degraded", "error": "DB auth backoff — check DATABASE_URL password and pooled 6543 (ECIRCUITBREAKER avoidance)", "backend_url": backend_url, "frontend_connected_to": frontend_connected_to, "diagnostics": diag}
    # Non-blocking DB check — avoid Render 502 where pool_timeout 10s > health 4s (still < Render 5s)
    # Use engine.connect() with worker thread timeout <4s, return degraded quickly if pool busy
    # Always report correct database type (PostgreSQL vs SQLite) even in degraded.
    def _db_check():
        # Use engine.connect() (pool_pre_ping handles stale) with short execution
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    fut = executor.submit(_db_check)
    try:
        # Enforce <4s wall-clock even if pool_timeout is 10s (Render health 5s)
        fut.result(timeout=4.0)
        # success → reset backoff
        _auth_backoff["failure_count"] = 0
    except concurrent.futures.TimeoutError:
        # Do not wait for worker — return degraded quickly (<4s) but with correct DB label
        try:
            fut.cancel()
        except Exception:
            pass
        try:
            executor.shutdown(wait=False, cancel_futures=True)
        except TypeError:
            # Python <3.9 fallback
            executor.shutdown(wait=False)
        diag = _fast_diag("pool busy — health check <4s")
        diag["live_mode"] = False
        try:
            from app.config import settings
            import os
            lm = bool(getattr(settings, "live_mode", False)) or os.getenv("LIVE_MODE", "").lower() in ("1", "true", "yes", "on")
            diag["live_mode"] = lm
            diag["database_mode"] = getattr(settings, "database_mode", diag["database_mode"])
        except Exception:
            pass
        diag["backend_url"] = backend_url
        diag["frontend_connected_to"] = frontend_connected_to
        diag["frontend_api_base"] = frontend_connected_to
        return {"status": "degraded", "error": "DB pool timeout (health check <4s)", "backend_url": backend_url, "frontend_connected_to": frontend_connected_to, "diagnostics": diag}
    except (TimeoutError, OperationalError) as e:
        try:
            executor.shutdown(wait=False, cancel_futures=True)
        except TypeError:
            executor.shutdown(wait=False)
        msg = str(e)
        is_auth = "authentication failed" in msg.lower() or "password" in msg.lower() or "ECIRCUITBREAKER" in msg
        _record_auth_failure(is_auth)
        # Sanitize error for response: never leak password, but include guidance for auth failures
        safe_msg = msg[:300]
        if is_auth and "ECIRCUITBREAKER" in msg:
            safe_msg = "ECIRCUITBREAKER too many auth failures — check DATABASE_URL password and pooled 6543 (aws-0-ap-southeast-1.pooler.supabase.com:6543, user postgres.qgkxdvtrqjhcgnwggzxh, sslmode=require), wait 30s cooldown"
        elif is_auth:
            safe_msg = "password authentication failed — check DATABASE_URL password (rotate in Supabase Dashboard → Database Settings → Reset password, then update Render/ Vercel env)"
        diag = _fast_diag(f"DB unavailable: {safe_msg[:120]}")
        diag["backend_url"] = backend_url
        diag["frontend_connected_to"] = frontend_connected_to
        diag["frontend_api_base"] = frontend_connected_to
        return {"status": "degraded", "error": f"DB unavailable: {safe_msg}", "backend_url": backend_url, "frontend_connected_to": frontend_connected_to, "diagnostics": diag}
    except Exception as e:
        try:
            executor.shutdown(wait=False, cancel_futures=True)
        except TypeError:
            executor.shutdown(wait=False)
        # Any other DB error -> degraded, not 500, with quick return but correct DB label
        msg = str(e)
        is_auth = "authentication failed" in msg.lower() or "ECIRCUITBREAKER" in msg
        _record_auth_failure(is_auth)
        diag = _fast_diag(msg[:120])
        diag["backend_url"] = backend_url
        diag["frontend_connected_to"] = frontend_connected_to
        diag["frontend_api_base"] = frontend_connected_to
        return {"status": "degraded", "error": msg[:300], "backend_url": backend_url, "frontend_connected_to": frontend_connected_to, "diagnostics": diag}
    else:
        try:
            executor.shutdown(wait=False, cancel_futures=True)
        except TypeError:
            executor.shutdown(wait=False)

    # DB reachable — gather diagnostics with 5s cache (pool_timeout 10 allows burst, health DB check already passed)
    diag = None
    try:
        diag = _cached_diag(5.0)
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
    # Frontend wiring — always expose backend URL frontend would connect to (api.ts RENDER_FALLBACK logic)
    diag["backend_url"] = backend_url
    diag["frontend_connected_to"] = frontend_connected_to
    diag["frontend_api_base"] = frontend_connected_to
    # Also echo which frontend build URL is baked (vercel vs voroa) — for ops
    try:
        from app.database import _redact_db_url, DATABASE_URL
        diag["database_url"] = diag.get("database_url") or _redact_db_url(DATABASE_URL)
    except Exception:
        pass
    return {"status": "ok", "prototype": "human-approved planning and decision-support prototype", "synthetic_warning": "Synthetic prototype windows, not official railway availability.", "backend_url": backend_url, "frontend_connected_to": frontend_connected_to, "diagnostics": diag}

@router.get("/api/diagnostics")
def diagnostics(request: Request):
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
            # Fallback without DB round-trip but correct type (postgres/mysql/sqlite)
            from app.database import is_postgres as _is_pg, is_mysql as _is_my
            pg = _is_pg(); my = _is_my()
            if pg:
                d = {"database": "PostgreSQL", "journal_mode": "n/a (postgres)", "foreign_keys": True, "busy_timeout": 0, "path": "pooled ap-southeast-1", "warning": "diagnostics timeout — pool busy"}
            elif my:
                d = {"database": "MySQL", "journal_mode": "n/a (mysql)", "foreign_keys": True, "busy_timeout": 0, "path": "aiven mysql", "warning": "diagnostics timeout — pool busy"}
            else:
                d = {"database": "SQLite", "journal_mode": "unknown", "foreign_keys": False, "busy_timeout": 0, "path": "railblock.db", "warning": "diagnostics timeout — pool busy"}
        finally:
            try:
                _ex.shutdown(wait=False, cancel_futures=True)
            except TypeError:
                _ex.shutdown(wait=False)
    except Exception as _e:
        from app.database import is_postgres as _is_pg, is_mysql as _is_my
        pg = _is_pg(); my = _is_my()
        if pg:
            d = {"database": "PostgreSQL", "journal_mode": "n/a (postgres)", "foreign_keys": True, "busy_timeout": 0, "path": "pooled ap-southeast-1", "error": str(_e)[:200]}
        elif my:
            d = {"database": "MySQL", "journal_mode": "n/a (mysql)", "foreign_keys": True, "busy_timeout": 0, "path": "aiven mysql", "error": str(_e)[:200]}
        else:
            d = {"database": "SQLite", "journal_mode": "unknown", "foreign_keys": False, "busy_timeout": 0, "path": "railblock.db", "error": str(_e)[:200]}
    if d is None:
        from app.database import is_postgres as _is_pg, is_mysql as _is_my
        pg = _is_pg(); my = _is_my()
        if pg:
            d = {"database": "PostgreSQL", "journal_mode": "n/a (postgres)", "foreign_keys": True, "busy_timeout": 0, "path": "pooled ap-southeast-1"}
        elif my:
            d = {"database": "MySQL", "journal_mode": "n/a (mysql)", "foreign_keys": True, "busy_timeout": 0, "path": "aiven mysql"}
        else:
            d = {"database": "SQLite", "journal_mode": "unknown", "foreign_keys": False, "busy_timeout": 0, "path": "railblock.db"}
    try:
        from app.config import settings
        import os
        live_mode = bool(getattr(settings, "live_mode", False)) or os.getenv("LIVE_MODE", "").lower() in ("1", "true", "yes", "on")
        live_sources = getattr(settings, "live_sources", "") or os.getenv("LIVE_SOURCES", "")
    except Exception:
        import os
        live_mode = os.getenv("LIVE_MODE", "").lower() in ("1", "true", "yes", "on")
        live_sources = os.getenv("LIVE_SOURCES", "")
    # Frontend wiring for diagnostics endpoint as well
    backend_url, frontend_connected_to = _frontend_backend_urls(request)
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
    # Merge DB-level diagnostics with frontend wiring (preserve path vs backend_url distinction)
    # d["path"] is filesystem/DB host; backend_url is HTTP API host
    return {
        "database": d.get("database", "SQLite"),
        "journal_mode": d.get("journal_mode", "unknown"),
        "foreign_keys": d.get("foreign_keys", False),
        "busy_timeout": d.get("busy_timeout", 0),
        "path": d.get("path", ""),
        "database_url": d.get("database_url", d.get("path", "")),
        "database_mode": get_database_mode(),
        "live_mode": live_mode,
        "live_sources": live_sources,
        "synthetic_default": not live_mode,
        "cursor_summary": cursor_summary,
        "backend_url": backend_url,
        "frontend_connected_to": frontend_connected_to,
        "frontend_api_base": frontend_connected_to,
    }
