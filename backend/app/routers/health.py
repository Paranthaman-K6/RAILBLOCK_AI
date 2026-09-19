from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.exc import TimeoutError, OperationalError
from app.database import SessionLocal, get_diagnostics, engine, is_postgres, get_database_mode
import concurrent.futures

router = APIRouter()

# Simple 5s cache for diagnostics to avoid polling storm on Render free + Vercel 30s interval
_diag_cache: dict = {"ts": 0.0, "data": None}
import time as _time
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
