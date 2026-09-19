"""
Vercel serverless wrapper for RailBlock AI FastAPI backend.

- Exposes FastAPI `app` as Vercel handler (expects `app` or `handler`).
- Inserts backend/ into sys.path for imports.
- Handles Vercel read-only filesystem: forces SQLite to /tmp when VERCEL=1
  and DATABASE_URL not explicitly set to postgres/mysql.
- Ensures data/sample files are available via vercel.json includeFiles.
- Logs startup for debugging (visible in Vercel Runtime Logs).

Prototype disclaimer: synthetic demo data, not live railway systems.
"""
import os
import sys
import pathlib
import logging

# ---------------------------------------------------------------------------
# Logging setup (Vercel captures stdout/stderr)
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Vercel filesystem handling: /tmp is only writable location
# - If running on Vercel (VERCEL=1) and DATABASE_URL is not a remote
#   postgres/mysql URL, force SQLite fallback to /tmp/railblock.db
# - This mirrors backend/app/main.py fallback logic but proactively sets
#   env before importing app.database which evaluates DATABASE_URL at import.
# ---------------------------------------------------------------------------
_is_vercel = os.getenv("VERCEL") == "1" or os.getenv("VERCEL_ENV") is not None
if _is_vercel:
    _db_url = os.getenv("DATABASE_URL", "")
    _db_mode = os.getenv("DATABASE_MODE", "")
    _is_pg = _db_mode.lower() in ("postgres", "postgresql", "pg") or _db_url.startswith("postgresql://") or _db_url.startswith("postgres://")
    _is_mysql = _db_mode.lower() in ("mysql", "maria", "mariadb") or _db_url.startswith("mysql://") or _db_url.startswith("mysql+pymysql://")
    # Only override for SQLite fallback; keep explicit PG/MySQL URLs intact
    if not _is_pg and not _is_mysql:
        # Use /tmp which is writable on Vercel Lambda
        _tmp_db = "sqlite:////tmp/railblock.db"
        if not _db_url or _db_url.startswith("sqlite"):
            os.environ["DATABASE_URL"] = _tmp_db
            log.info(f"Vercel env: set DATABASE_URL={_tmp_db} (writable /tmp)")
        if not _db_mode or _db_mode.lower() == "sqlite":
            os.environ.setdefault("DATABASE_MODE", "sqlite")
        # Ensure data path is resolvable
        log.info(f"Vercel detected: DATABASE_MODE={os.getenv('DATABASE_MODE')} DATABASE_URL={os.getenv('DATABASE_URL')}")

# ---------------------------------------------------------------------------
# Ensure backend is on sys.path (api/index.py -> project root -> backend)
# ---------------------------------------------------------------------------
_backend_dir = str(pathlib.Path(__file__).resolve().parent.parent / "backend")
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)
    log.info(f"Added backend to sys.path: {_backend_dir}")

# Also add project root for data/sample relative imports if needed
_project_root = str(pathlib.Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

try:
    from app.main import app  # noqa: E402

    # Vercel Python runtime looks for `app` or `handler` variable
    handler = app

    # Optional: add startup log with diagnostics
    log.info("RailBlock AI FastAPI app imported successfully for Vercel")
    log.info(f"App title: {app.title} version: {app.version}")
    if _is_vercel:
        try:
            from app.database import get_database_mode, DATABASE_URL

            log.info(f"Effective DB mode: {get_database_mode()} URL: {DATABASE_URL[:80]}")
        except Exception as _e:
            log.warning(f"Could not log DB mode: {_e}")

    # Export for Vercel
    __all__ = ["app", "handler"]

except Exception as e:
    log.exception(f"Failed to import FastAPI app: {e}")
    raise
