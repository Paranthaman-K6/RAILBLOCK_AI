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
        # Use project folder tmp/railblock.db per user request "use project folder for tmp"
        # Prefer project tmp if writable, else fallback to /tmp (only writable on Vercel Lambda)
        _project_tmp_dir = str(pathlib.Path(__file__).resolve().parent.parent / "tmp")
        _project_tmp_db = f"sqlite:///{_project_tmp_dir.replace(os.sep, '/')}/railblock.db"
        # Normalise path for URL (use forward slashes, handle Windows)
        _project_tmp_db = _project_tmp_db.replace("\\", "/").replace("//", "/").replace("sqlite:/", "sqlite:///")
        # Ensure dir exists if possible
        try:
            pathlib.Path(_project_tmp_dir).mkdir(parents=True, exist_ok=True)
            _use_project_tmp = pathlib.Path(_project_tmp_dir).exists() and os.access(_project_tmp_dir, os.W_OK)
        except Exception:
            _use_project_tmp = False
        if _use_project_tmp:
            _tmp_db = _project_tmp_db
            # Fix sqlite:/// prefix for absolute path
            if not _tmp_db.startswith("sqlite:////") and not _tmp_db.startswith("sqlite:///"):
                _tmp_db = f"sqlite:///{_project_tmp_dir.replace(os.sep, '/')}/railblock.db"
            if not _db_url or _db_url.startswith("sqlite"):
                os.environ["DATABASE_URL"] = _tmp_db
                log.info(f"Vercel env: set DATABASE_URL={_tmp_db} (project tmp)")
        else:
            _tmp_db = "sqlite:////tmp/railblock.db"
            if not _db_url or _db_url.startswith("sqlite"):
                os.environ["DATABASE_URL"] = _tmp_db
                log.info(f"Vercel env: set DATABASE_URL={_tmp_db} (writable /tmp fallback)")
        if not _db_mode or _db_mode.lower() == "sqlite":
            os.environ.setdefault("DATABASE_MODE", "sqlite")
        # Ensure data path is resolvable
        # Never log raw DATABASE_URL (contains password) — redact
        try:
            from urllib.parse import urlparse, urlunparse
            _r = os.getenv("DATABASE_URL","")
            if "://" in _r and "@" in _r:
                _p=urlparse(_r); _net=_p.netloc
                if "@" in _net:
                    _cr,_hp=_net.rsplit("@",1)
                    if ":" in _cr:
                        _u,_pw=_cr.split(":",1)
                        _cr=f"{_u}:***"
                    _net=f"{_cr}@{_hp}"
                _r=urlunparse((_p.scheme,_net,_p.path,_p.params,_p.query,_p.fragment))
            _redacted=_r
        except Exception:
            _redacted=os.getenv("DATABASE_URL","").split("@")[-1]
        log.info(f"Vercel detected: DATABASE_MODE={os.getenv('DATABASE_MODE')} DATABASE_URL={_redacted}")

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
            from app.database import get_database_mode, DATABASE_URL, _redact_db_url  # type: ignore

            log.info(f"Effective DB mode: {get_database_mode()} URL: {_redact_db_url(DATABASE_URL)[:120]}")
        except Exception:
            try:
                from app.database import get_database_mode, DATABASE_URL
                # fallback redact
                _ru=DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL
                log.info(f"Effective DB mode: {get_database_mode()} URL: {_ru[:120]}")
            except Exception as _e2:
                log.warning(f"Could not log DB mode: {_e2}")

    # Export for Vercel
    __all__ = ["app", "handler"]

except Exception as e:
    log.exception(f"Failed to import FastAPI app: {e}")
    raise
