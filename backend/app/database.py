from sqlalchemy import create_engine, event, text, Index
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.engine import Engine
from typing import Optional
import os


def _is_vercel() -> bool:
    """Detect Vercel serverless environment.

    Vercel sets VERCEL=1 on builds/deployments and also provides
    VERCEL_ENV (production/preview/development) and VERCEL_URL.
    When detected, SQLite must use /tmp (only writable dir on Vercel).
    Returns True if VERCEL=="1" or VERCEL_ENV or VERCEL_URL is set.
    """
    return os.getenv("VERCEL") == "1" or bool(os.getenv("VERCEL_ENV")) or bool(os.getenv("VERCEL_URL"))


_base_dir = os.path.dirname(os.path.abspath(__file__))
# Project folder for tmp — uses <project_root>/tmp/railblock.db instead of system /tmp or backend/railblock.db
# per user request: "use project folder for tmp"
_project_root = os.path.abspath(os.path.join(_base_dir, "..", ".."))
_project_tmp_dir = os.path.join(_project_root, "tmp")
_project_tmp_db = os.path.join(_project_tmp_dir, "railblock.db")
# Ensure project tmp dir exists (writable on Voroa/local; on Vercel fallback to /tmp if not writable)
try:
    os.makedirs(_project_tmp_dir, exist_ok=True)
except Exception:
    pass
if _is_vercel():
    # On Vercel, /tmp is the only writable dir — prefer project tmp if writable, else /tmp
    try:
        _test_writable = os.access(_project_tmp_dir, os.W_OK)
        if _test_writable and os.path.exists(_project_tmp_dir):
            _default_db = _project_tmp_db
        else:
            _default_db = "/tmp/railblock.db"
            _project_tmp_db = _default_db
    except Exception:
        _default_db = "/tmp/railblock.db"
        _project_tmp_db = _default_db
else:
    _default_db = _project_tmp_db

# Phase 1c — Database abstraction helpers (preserve SQLite default)
def _normalize_postgres_url(url: str) -> str:
    # postgres:// is deprecated alias, sqlalchemy prefers postgresql://
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://"):]
    return url

def _sanitize_postgres_url(url: str) -> str:
    # Strip Supabase UI hints that are not libpq/psycopg2 DSN keys (e.g. &pgbouncer=true, &prepareThreshold=0)
    # pgbouncer param is valid for psycopg3/postgres.js/Prisma but invalid for psycopg2 libpq -> invalid dsn
    if "pgbouncer" not in url and "prepareThreshold" not in url and "pgsession" not in url:
        return url
    try:
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
        p = urlparse(url)
        q = parse_qs(p.query, keep_blank_values=True)
        for bad in list(q.keys()):
            if bad.lower() in ("pgbouncer", "preparethreshold", "preparedthreshold", "pgsession", "statement_cache_size"):
                q.pop(bad, None)
        new_q = urlencode({k: v[0] if len(v)==1 else v for k,v in q.items()}, doseq=False)
        return urlunparse((p.scheme, p.netloc, p.path, p.params, new_q, p.fragment))
    except Exception:
        return url

def _redact_db_url(url: str) -> str:
    """Redact password from DATABASE_URL for logging/diagnostics — never expose secrets."""
    if not url or "://" not in url:
        return url
    if url.startswith("sqlite"):
        return url  # sqlite has no credentials
    try:
        from urllib.parse import urlparse, urlunparse
        p = urlparse(url)
        netloc = p.netloc
        if "@" in netloc:
            creds, hostport = netloc.rsplit("@", 1)
            if ":" in creds:
                user, _pwd = creds.split(":", 1)
                creds = f"{user}:***"
            # else no password to redact
            netloc = f"{creds}@{hostport}"
        return urlunparse((p.scheme, netloc, p.path, p.params, p.query, p.fragment))
    except Exception:
        # Fallback: split on @
        return url.split("@")[-1] if "@" in url else url

# Frontend wiring — matches frontend/src/services/api.ts RENDER_FALLBACK (Vercel prod fallback)
FRONTEND_BACKEND_URL = os.getenv("FRONTEND_BACKEND_URL") or os.getenv("VITE_API_URL") or "https://railblock-ai.getvoroa.com"
RENDER_FALLBACK = "https://railblock-ai.getvoroa.com"

# Circuit-breaker backoff for repeated auth failures (ECIRCUITBREAKER) — avoid hammering Supabase pooler
_last_auth_failure_ts: float = 0.0
_auth_failure_count: int = 0
_AUTH_COOLDOWN_SEC = 30  # after password auth failure, suppress DB attempts for 30s to avoid ECIRCUITBREAKER

def _is_postgres_url(url: Optional[str] = None) -> bool:
    u = url or DATABASE_URL or ""
    return u.startswith("postgresql")

def _is_mysql_url(url: Optional[str] = None) -> bool:
    u = url or DATABASE_URL or ""
    return u.startswith("mysql://") or u.startswith("mysql+pymysql://")

def _normalize_mysql_url(url: str) -> str:
    """Convert mysql:// to mysql+pymysql:// and strip ssl params to be handled via connect_args.
    Aiven requires SSL; we keep a flag and pass ssl via connect_args instead of URL query.
    """
    original = url
    # Detect SSL requirement from Aiven-style ssl-mode param
    # We will strip it from URL and use ssl connect_args
    global _MYSQL_SSL_REQUIRED
    try:
        low = url.lower()
        if "ssl-mode=required" in low or "ssl_mode=required" in low or "sslmode=require" in low or "ssl=require" in low:
            _MYSQL_SSL_REQUIRED = True
    except Exception:
        pass
    # Convert scheme
    if url.startswith("mysql://"):
        url = "mysql+pymysql://" + url[len("mysql://"):]
    # Strip ssl-mode / ssl_mode / ssl from query params (handled via connect_args)
    try:
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
        if "?" in url:
            p = urlparse(url)
            q = parse_qs(p.query, keep_blank_values=True)
            changed = False
            for k in list(q.keys()):
                lk = k.lower().replace("-", "_")
                if lk in ("ssl_mode", "sslmode", "ssl") and q[k][0].lower() in ("required", "require", "true", "1", "yes"):
                    q.pop(k)
                    changed = True
                # Also strip generic ssl-ca etc handled separately
            if changed:
                new_q = urlencode({k: v[0] if len(v)==1 else v for k,v in q.items()}, doseq=False)
                url = urlunparse((p.scheme, p.netloc, p.path, p.params, new_q, p.fragment))
                # remove trailing ? if empty
                if url.endswith("?"):
                    url = url[:-1]
    except Exception:
        pass
    return url

_MYSQL_SSL_REQUIRED = False

# Always use absolute Windows path when running locally, but allow DATABASE_URL override for Docker (/app/railblock.db)
# For Docker, DATABASE_URL=sqlite:///./railblock.db will be resolved relative to WORKDIR /app -> /app/railblock.db
_raw_db_url = os.getenv("DATABASE_URL", f"sqlite:///{_default_db.replace(os.sep, '/')}")
_raw_db_url = _normalize_postgres_url(_raw_db_url)
_raw_db_url = _normalize_mysql_url(_raw_db_url)
DATABASE_URL = _sanitize_postgres_url(_raw_db_url)
# Vercel-aware SQLite fallback: use project folder tmp/railblock.db (per user: "use project folder for tmp")
# When running on Vercel (VERCEL=1) and DATABASE_URL is still sqlite and not already pointing at project tmp or /tmp,
# rewrite to project tmp if writable, else fallback to /tmp (only writable on Vercel Lambda).
# Do NOT override postgres/mysql (DATABASE_MODE or URL scheme indicates external DB).
if _is_vercel() and DATABASE_URL.startswith("sqlite") and _project_tmp_db not in DATABASE_URL and "/tmp" not in DATABASE_URL:
    # Respect explicit postgres/mysql mode — don't clobber external DB config
    _vercel_mode = os.getenv("DATABASE_MODE", "").lower()
    _is_external_mode = _vercel_mode in ("postgres", "postgresql", "pg", "mysql", "maria", "mariadb")
    # Also check URL scheme directly (covers postgres/mysql URLs)
    _is_external_url = DATABASE_URL.startswith("postgresql") or DATABASE_URL.startswith("postgres") or DATABASE_URL.startswith("mysql")
    if not _is_external_mode and not _is_external_url:
        # Prefer project folder tmp if writable
        try:
            os.makedirs(_project_tmp_dir, exist_ok=True)
            if os.access(_project_tmp_dir, os.W_OK):
                DATABASE_URL = f"sqlite:///{_project_tmp_db.replace(os.sep, '/')}"
                _default_db = _project_tmp_db
            else:
                DATABASE_URL = "sqlite:////tmp/railblock.db"
                _default_db = "/tmp/railblock.db"
                try:
                    os.makedirs("/tmp", exist_ok=True)
                except Exception:
                    pass
        except Exception:
            DATABASE_URL = "sqlite:////tmp/railblock.db"
            _default_db = "/tmp/railblock.db"
            try:
                os.makedirs("/tmp", exist_ok=True)
            except Exception:
                pass
# Ensure sslmode for Supabase/Render external Postgres (append if missing and is postgres)
if _is_postgres_url(DATABASE_URL) and "sslmode=" not in DATABASE_URL:
    sep = "&" if "?" in DATABASE_URL else "?"
    DATABASE_URL = DATABASE_URL + f"{sep}sslmode=require"
# Add connect_timeout for faster failover on Render (pooled 6543) if not present
if _is_postgres_url(DATABASE_URL) and "connect_timeout" not in DATABASE_URL:
    sep = "&" if "?" in DATABASE_URL else "?"
    DATABASE_URL = DATABASE_URL + f"{sep}connect_timeout=5"
# Enforce pooled host for Supabase ap-southeast-1 (prevent direct host IPv6 unreachable + ECIRCUITBREAKER)
# Pooled: postgres.qgkxdvtrqjhcgnwggzxh@aws-0-ap-southeast-1.pooler.supabase.com:6543 with sslmode=require
# Direct: postgres@db.qgkxdvtrqjhcgnwggzxh.supabase.co:5432 fails on Render (Oregon) IPv6 + auth
try:
    if _is_postgres_url(DATABASE_URL):
        _host_check = DATABASE_URL.lower()
        if "db.qgkxdvtrqjhcgnwggzxh.supabase.co" in _host_check and "pooler.supabase.com" not in _host_check:
            import logging as _lg
            _lg.getLogger(__name__).warning(
                "DATABASE_URL uses direct host db.qgkxdvtrqjhcgnwggzxh.supabase.co — "
                "use pooled aws-0-ap-southeast-1.pooler.supabase.com:6543 with user postgres.qgkxdvtrqjhcgnwggzxh to avoid IPv6 unreachable and ECIRCUITBREAKER"
            )
        if "pooler.supabase.com:5432" in _host_check:
            import logging as _lg2
            _lg2.getLogger(__name__).warning("DATABASE_URL uses pooler port 5432 — use 6543 for transaction pooler (Supavisor/pgbouncer) on Render")
except Exception:
    pass

def is_postgres() -> bool:
    # Explicit DATABASE_MODE flag takes precedence; fallback to URL scheme
    try:
        from app.config import settings
        if getattr(settings, "database_mode", "sqlite").lower() in ("postgres", "postgresql", "pg"):
            return True
    except Exception:
        pass
    if os.getenv("DATABASE_MODE", "").lower() in ("postgres", "postgresql", "pg"):
        return True
    return _is_postgres_url()

def is_mysql() -> bool:
    try:
        from app.config import settings
        if getattr(settings, "database_mode", "sqlite").lower() in ("mysql", "maria", "mariadb"):
            return True
    except Exception:
        pass
    if os.getenv("DATABASE_MODE", "").lower() in ("mysql", "maria", "mariadb"):
        return True
    return _is_mysql_url()

def is_sqlite() -> bool:
    return not is_postgres() and not is_mysql() and DATABASE_URL.startswith("sqlite")

def get_database_mode() -> str:
    if is_postgres():
        return "postgres"
    if is_mysql():
        return "mysql"
    return "sqlite"

# Support both relative and absolute
if DATABASE_URL.startswith("sqlite"):
    db_path = DATABASE_URL.replace("sqlite:///", "")
    # handle windows absolute with drive letter like /D:/...
    # For relative like ./railblock.db, resolve to _default_db
    if db_path.startswith("./") or db_path.startswith(".\\"):
        # keep as relative to cwd, ensure directory exists when engine connects
        pass
    elif db_path.startswith("/"):
        # may be /D:/... - strip leading slash for windows makedirs check
        stripped = db_path[1:] if len(db_path) > 2 and db_path[2] == ":" else db_path
        dir_part = os.path.dirname(stripped)
        if dir_part:
            try:
                os.makedirs(dir_part, exist_ok=True)
            except:
                pass
    else:
        dir_part = os.path.dirname(db_path)
        if dir_part:
            os.makedirs(dir_part, exist_ok=True)
        elif not db_path.startswith("/"):
            # relative without ./ - e.g. railblock.db
            os.makedirs(os.path.dirname(_default_db) or ".", exist_ok=True)

def _mysql_connect_args():
    if is_mysql():
        if _MYSQL_SSL_REQUIRED:
            # Aiven MySQL requires SSL. pymysql ssl dict enables TLS without CA verification by default.
            # Use empty dict or {'ssl': True} - both enable SSL.
            return {"ssl": {}}
        return {}
    return {}

def _base_connect_args():
    if is_mysql():
        return _mysql_connect_args()
    if "sqlite" in DATABASE_URL and not is_postgres():
        return {"check_same_thread": False}
    return {}

engine = create_engine(
    DATABASE_URL,
    connect_args=_base_connect_args(),
    echo=False,
    # Postgres/MySQL production: pool pre-ping + sizing (Render free tuned, also for Aiven MySQL pool)
    **({"pool_pre_ping": True, "pool_size": 5, "max_overflow": 10, "pool_recycle": 300, "pool_timeout": 10} if is_postgres() or is_mysql() else {}),
)

# Enable WAL, FK, busy_timeout for every new DBAPI connection (SQLite only)
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if is_postgres() or is_mysql():
        return
    if "sqlite" in DATABASE_URL:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA foreign_keys=ON;")
            cursor.execute("PRAGMA busy_timeout=5000;")
            cursor.execute("PRAGMA synchronous=NORMAL;")
            cursor.execute("PRAGMA cache_size=-64000;")  # 64MB
            cursor.execute("PRAGMA temp_store=MEMORY;")
        finally:
            cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_engine():
    """Lazy accessor — if DATABASE_MODE flipped after import, recreate engine on next call.
    Restart still recommended after changing DATABASE_MODE/URL; this helper aids tests that set env mid-process.
    """
    global engine, SessionLocal, DATABASE_URL, _MYSQL_SSL_REQUIRED
    try:
        want_pg = is_postgres()
        want_mysql = is_mysql()
        have_pg = str(engine.url).startswith("postgresql") or str(engine.url).startswith("postgres")
        have_mysql = str(engine.url).startswith("mysql")
        if (want_pg != have_pg) or (want_mysql != have_mysql):
            from sqlalchemy import create_engine as _ce
            new_url = os.getenv("DATABASE_URL", DATABASE_URL)
            # If want_pg/mysql but url still sqlite, keep original engine but diagnostics will warn
            if (want_pg or want_mysql) and new_url.startswith("sqlite"):
                return engine
            new_url = _sanitize_postgres_url(_normalize_postgres_url(new_url))
            new_url = _normalize_mysql_url(new_url)
            # Update global DATABASE_URL so helpers stay consistent
            DATABASE_URL = new_url
            if want_pg and "sslmode=" not in new_url:
                sep = "&" if "?" in new_url else "?"
                new_url = new_url + f"{sep}sslmode=require"
                DATABASE_URL = new_url
            if want_pg and "connect_timeout" not in new_url:
                sep = "&" if "?" in new_url else "?"
                new_url = new_url + f"{sep}connect_timeout=5"
                DATABASE_URL = new_url
            # Determine connect args for new engine
            if want_mysql:
                cargs = {"ssl": {}} if _MYSQL_SSL_REQUIRED else {}
            elif want_pg:
                cargs = {}
            else:
                cargs = {"check_same_thread": False} if "sqlite" in new_url and not want_pg else {}
            engine = _ce(
                new_url,
                connect_args=cargs,
                echo=False,
                **({"pool_pre_ping": True, "pool_size": 5, "max_overflow": 10, "pool_recycle": 300, "pool_timeout": 10} if (want_pg or want_mysql) else {}),
            )
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    except Exception:
        pass
    return engine

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    import app.models  # noqa
    Base.metadata.create_all(bind=engine)
    # Phase 1a/1c: provenance columns auto-migration (SQLite additive, Postgres/MySQL via create_all)
    # For existing SQLite files, add missing provenance columns if not present - MySQL/Postgres create_all handles it
    if not is_postgres() and not is_mysql():
        try:
            with engine.connect() as conn:
                # Lightweight additive migration — only add missing columns, preserves data
                cols = {r[1] for r in conn.execute(text("PRAGMA table_info(tasks)")).fetchall()}
                to_add = []
                if "external_id" not in cols:
                    to_add.append("ALTER TABLE tasks ADD COLUMN external_id TEXT")
                if "source_updated_at" not in cols:
                    to_add.append("ALTER TABLE tasks ADD COLUMN source_updated_at TEXT")
                if "source_maturity" not in cols:
                    to_add.append("ALTER TABLE tasks ADD COLUMN source_maturity TEXT DEFAULT 'SYNTHETIC'")
                if "source_hash" not in cols:
                    to_add.append("ALTER TABLE tasks ADD COLUMN source_hash TEXT")
                cols_ir = {r[1] for r in conn.execute(text("PRAGMA table_info(import_runs)")).fetchall()}
                if "source_maturity" not in cols_ir:
                    to_add.append("ALTER TABLE import_runs ADD COLUMN source_maturity TEXT DEFAULT 'SYNTHETIC'")
                if "source_hash" not in cols_ir:
                    to_add.append("ALTER TABLE import_runs ADD COLUMN source_hash TEXT")
                if "cursor_value" not in cols_ir:
                    to_add.append("ALTER TABLE import_runs ADD COLUMN cursor_value TEXT")
                if "outcome" not in cols_ir:
                    to_add.append("ALTER TABLE import_runs ADD COLUMN outcome TEXT")
                # Train/Goods provenance
                cols_tr = {r[1] for r in conn.execute(text("PRAGMA table_info(train_movements)")).fetchall()}
                if "external_id" not in cols_tr:
                    to_add.append("ALTER TABLE train_movements ADD COLUMN external_id TEXT")
                if "source_updated_at" not in cols_tr:
                    to_add.append("ALTER TABLE train_movements ADD COLUMN source_updated_at TEXT")
                if "source_maturity" not in cols_tr:
                    to_add.append("ALTER TABLE train_movements ADD COLUMN source_maturity TEXT DEFAULT 'SYNTHETIC'")
                if "source_hash" not in cols_tr:
                    to_add.append("ALTER TABLE train_movements ADD COLUMN source_hash TEXT")
                cols_gf = {r[1] for r in conn.execute(text("PRAGMA table_info(goods_forecasts)")).fetchall()}
                if "external_id" not in cols_gf:
                    to_add.append("ALTER TABLE goods_forecasts ADD COLUMN external_id TEXT")
                if "source_updated_at" not in cols_gf:
                    to_add.append("ALTER TABLE goods_forecasts ADD COLUMN source_updated_at TEXT")
                if "source_maturity" not in cols_gf:
                    to_add.append("ALTER TABLE goods_forecasts ADD COLUMN source_maturity TEXT DEFAULT 'SYNTHETIC'")
                if "source_hash" not in cols_gf:
                    to_add.append("ALTER TABLE goods_forecasts ADD COLUMN source_hash TEXT")
                for ddl in to_add:
                    try:
                        conn.execute(text(ddl))
                    except Exception:
                        pass
                conn.commit()
        except Exception:
            pass
        # Ensure source_cursors table for incremental Phase 1b + Option A diagnostics migration
        try:
            with engine.connect() as conn:
                conn.execute(text("CREATE TABLE IF NOT EXISTS source_cursors (source_name TEXT PRIMARY KEY, cursor_value TEXT, updated_at TEXT)"))
                # Additive migration for Option A fields (nullable/default 0)
                try:
                    cols_sc = {r[1] for r in conn.execute(text("PRAGMA table_info(source_cursors)")).fetchall()}
                    to_add_sc = []
                    if "last_success_at" not in cols_sc:
                        to_add_sc.append("ALTER TABLE source_cursors ADD COLUMN last_success_at TEXT")
                    if "last_error_at" not in cols_sc:
                        to_add_sc.append("ALTER TABLE source_cursors ADD COLUMN last_error_at TEXT")
                    if "last_error_message" not in cols_sc:
                        to_add_sc.append("ALTER TABLE source_cursors ADD COLUMN last_error_message TEXT")
                    if "fetch_attempts" not in cols_sc:
                        to_add_sc.append("ALTER TABLE source_cursors ADD COLUMN fetch_attempts INTEGER DEFAULT 0")
                    if "fetch_successes" not in cols_sc:
                        to_add_sc.append("ALTER TABLE source_cursors ADD COLUMN fetch_successes INTEGER DEFAULT 0")
                    if "last_outcome" not in cols_sc:
                        to_add_sc.append("ALTER TABLE source_cursors ADD COLUMN last_outcome TEXT")
                    for ddl in to_add_sc:
                        try:
                            conn.execute(text(ddl))
                        except Exception:
                            pass
                except Exception:
                    pass
                conn.commit()
        except Exception:
            pass
    # Verify pragmas after creation (SQLite only)
    if is_postgres() or is_mysql():
        return
    try:
        with engine.connect() as conn:
            jm = conn.execute(text("PRAGMA journal_mode;")).scalar()
            fk = conn.execute(text("PRAGMA foreign_keys;")).scalar()
            bt = conn.execute(text("PRAGMA busy_timeout;")).scalar()
            # If not WAL, try to set again (handles race where file was just created)
            if jm and jm.lower() != "wal":
                conn.execute(text("PRAGMA journal_mode=WAL;"))
                conn.commit()
    except Exception:
        pass

def get_diagnostics():
    """Diagnostic report for API or reset script. Postgres-aware. Timeout-guarded for pooled ap-southeast-1."""
    # Postgres diagnostics branch — guard version query with timeout so health/diagnostics never hang > pool_timeout
    if is_postgres():
        # Fast path: if DATABASE_URL still sqlite but mode says postgres, return misconfigured without DB connect
        if DATABASE_URL.startswith("sqlite"):
            live = False
            live_sources = ""
            try:
                from app.config import settings
                import os as _os2
                live = bool(getattr(settings, "live_mode", False)) or _os2.getenv("LIVE_MODE","").lower() in ("1","true","yes","on")
                live_sources = getattr(settings, "live_sources", "") or _os2.getenv("LIVE_SOURCES","")
            except Exception:
                import os as _os
                live = _os.getenv("LIVE_MODE", "").lower() in ("1","true","yes","on")
                live_sources = _os.getenv("LIVE_SOURCES","")
            return {
                "database": "PostgreSQL",
                "journal_mode": "n/a (postgres)",
                "foreign_keys": False,
                "busy_timeout": 0,
                "path": _redact_db_url(DATABASE_URL),
                "database_url": _redact_db_url(DATABASE_URL),
                "database_mode": "postgres",
                "live_mode": live,
                "live_sources": live_sources,
                "server_version": "unknown — misconfigured",
                "warning": "DATABASE_MODE=postgres but DATABASE_URL still sqlite — set DATABASE_URL=postgresql://... and restart. Running in degraded sqlite mode.",
                "misconfigured": True,
                "backend_url": RENDER_FALLBACK,
                "frontend_connected_to": RENDER_FALLBACK,
                "frontend_api_base": RENDER_FALLBACK,
            }
        # Normal postgres: direct version query (pool_timeout 10 allows burst, health 4s < Render 5s)
        ver = "PostgreSQL"
        try:
            with engine.connect() as conn:
                try:
                    ver = conn.execute(text("SELECT version()")).scalar()
                except Exception:
                    ver = "PostgreSQL"
        except Exception:
            ver = "PostgreSQL (version query failed — pool busy)"
        try:
            # live mode for transparency — no DB needed
            live = False
            live_sources = ""
            try:
                from app.config import settings
                import os as _os2
                live = bool(getattr(settings, "live_mode", False)) or _os2.getenv("LIVE_MODE","").lower() in ("1","true","yes","on")
                live_sources = getattr(settings, "live_sources", "") or _os2.getenv("LIVE_SOURCES","")
            except Exception:
                import os as _os
                live = _os.getenv("LIVE_MODE", "").lower() in ("1","true","yes","on")
                live_sources = _os.getenv("LIVE_SOURCES","")
            # Misconfiguration warning already handled above, so not needed here
            warn = None
            if DATABASE_URL.startswith("sqlite"):
                warn = "DATABASE_MODE=postgres but DATABASE_URL still sqlite — set DATABASE_URL=postgresql://... and restart. Running in degraded sqlite mode."
            diag = {
                "database": "PostgreSQL",
                "journal_mode": "n/a (postgres)",
                "foreign_keys": True,
                "busy_timeout": 0,
                "path": _redact_db_url(DATABASE_URL),
                "database_url": _redact_db_url(DATABASE_URL),
                "database_mode": "postgres",
                "live_mode": live,
                "live_sources": live_sources,
                "server_version": str(ver)[:120] if ver else "unknown",
                "backend_url": RENDER_FALLBACK,
                "frontend_connected_to": RENDER_FALLBACK,
                "frontend_api_base": RENDER_FALLBACK,
            }
            if warn:
                diag["warning"] = warn
                diag["misconfigured"] = True
            return diag
        except Exception as e:
            return {
                "database": "PostgreSQL",
                "journal_mode": "n/a",
                "foreign_keys": False,
                "path": _redact_db_url(DATABASE_URL),
                "database_mode": "postgres",
                "error": str(e),
                "backend_url": RENDER_FALLBACK,
                "frontend_connected_to": RENDER_FALLBACK,
                "frontend_api_base": RENDER_FALLBACK,
            }
    # MySQL diagnostics
    if is_mysql():
        if DATABASE_URL.startswith("sqlite"):
            live = False
            live_sources = ""
            try:
                from app.config import settings
                import os as _os2
                live = bool(getattr(settings, "live_mode", False)) or _os2.getenv("LIVE_MODE","").lower() in ("1","true","yes","on")
                live_sources = getattr(settings, "live_sources", "") or _os2.getenv("LIVE_SOURCES","")
            except Exception:
                import os as _os
                live = _os.getenv("LIVE_MODE", "").lower() in ("1","true","yes","on")
                live_sources = _os.getenv("LIVE_SOURCES","")
            return {
                "database": "MySQL",
                "journal_mode": "n/a (mysql)",
                "foreign_keys": False,
                "busy_timeout": 0,
                "path": _redact_db_url(DATABASE_URL),
                "database_url": _redact_db_url(DATABASE_URL),
                "database_mode": "mysql",
                "live_mode": live,
                "live_sources": live_sources,
                "server_version": "unknown — misconfigured",
                "warning": "DATABASE_MODE=mysql but DATABASE_URL still sqlite — set DATABASE_URL=mysql://... and restart.",
                "misconfigured": True,
                "backend_url": RENDER_FALLBACK,
                "frontend_connected_to": RENDER_FALLBACK,
                "frontend_api_base": RENDER_FALLBACK,
            }
        ver = "MySQL"
        try:
            with engine.connect() as conn:
                try:
                    ver = conn.execute(text("SELECT VERSION()")).scalar()
                except Exception:
                    ver = "MySQL"
        except Exception:
            ver = "MySQL (version query failed — pool busy)"
        try:
            live = False
            live_sources = ""
            try:
                from app.config import settings
                import os as _os2
                live = bool(getattr(settings, "live_mode", False)) or _os2.getenv("LIVE_MODE","").lower() in ("1","true","yes","on")
                live_sources = getattr(settings, "live_sources", "") or _os2.getenv("LIVE_SOURCES","")
            except Exception:
                import os as _os
                live = _os.getenv("LIVE_MODE", "").lower() in ("1","true","yes","on")
                live_sources = _os.getenv("LIVE_SOURCES","")
            diag = {
                "database": "MySQL",
                "journal_mode": "n/a (mysql)",
                "foreign_keys": True,
                "busy_timeout": 0,
                "path": _redact_db_url(DATABASE_URL),
                "database_url": _redact_db_url(DATABASE_URL),
                "database_mode": "mysql",
                "live_mode": live,
                "live_sources": live_sources,
                "server_version": str(ver)[:120] if ver else "unknown",
                "backend_url": RENDER_FALLBACK,
                "frontend_connected_to": RENDER_FALLBACK,
                "frontend_api_base": RENDER_FALLBACK,
            }
            return diag
        except Exception as e:
            return {
                "database": "MySQL",
                "journal_mode": "n/a",
                "foreign_keys": False,
                "path": _redact_db_url(DATABASE_URL),
                "database_mode": "mysql",
                "error": str(e),
                "backend_url": RENDER_FALLBACK,
                "frontend_connected_to": RENDER_FALLBACK,
                "frontend_api_base": RENDER_FALLBACK,
            }
    try:
        with engine.connect() as conn:
            jm = conn.execute(text("PRAGMA journal_mode;")).scalar()
            fk = conn.execute(text("PRAGMA foreign_keys;")).scalar()
            bt = conn.execute(text("PRAGMA busy_timeout;")).scalar()
            # Resolve actual filesystem path
            raw_path = DATABASE_URL.replace("sqlite:///", "")
            if raw_path.startswith("./"):
                # relative to backend WORKDIR
                actual = os.path.abspath(os.path.join(_base_dir, "..", raw_path[2:]))
            elif raw_path.startswith("/"):
                # docker /D:/ edge
                stripped = raw_path[1:] if len(raw_path) > 2 and raw_path[2] == ":" else raw_path
                actual = stripped if ":" in stripped[:2] else raw_path
                if not os.path.isabs(stripped) and ":" not in stripped[:2]:
                    actual = os.path.abspath(os.path.join(_base_dir, "..", raw_path))
                    if actual.startswith("/"):
                        actual = _default_db
                    else:
                        actual = actual
                else:
                    actual = stripped
            else:
                actual = os.path.abspath(raw_path) if not os.path.isabs(raw_path) else raw_path
                if not os.path.isabs(raw_path) and ":" not in raw_path:
                    actual = _default_db
            # Normalize to forward slashes for API consistency
            actual_fwd = actual.replace(os.sep, "/")
            # Fallback to _default_db if path doesn't look valid
            if not actual_fwd or actual_fwd == "/":
                actual_fwd = _default_db.replace(os.sep, "/")
            return {
                "database": "SQLite",
                "journal_mode": str(jm).lower() if jm else "unknown",
                "foreign_keys": bool(fk) if fk is not None else False,
                "busy_timeout": int(bt) if bt else 0,
                "path": actual_fwd,
                "database_url": DATABASE_URL,
                "backend_url": RENDER_FALLBACK,
                "frontend_connected_to": RENDER_FALLBACK,
                "frontend_api_base": RENDER_FALLBACK,
            }
    except Exception as e:
        return {
            "database": "SQLite",
            "journal_mode": "unknown",
            "foreign_keys": False,
            "path": _default_db.replace(os.sep, "/"),
            "error": str(e),
            "backend_url": RENDER_FALLBACK,
            "frontend_connected_to": RENDER_FALLBACK,
            "frontend_api_base": RENDER_FALLBACK,
        }
