from sqlalchemy import create_engine, event, text, Index
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.engine import Engine
from typing import Optional
import os

_base_dir = os.path.dirname(os.path.abspath(__file__))
_default_db = os.path.abspath(os.path.join(_base_dir, "..", "railblock.db"))

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

def _is_postgres_url(url: Optional[str] = None) -> bool:
    u = url or DATABASE_URL or ""
    return u.startswith("postgresql")

# Always use absolute Windows path when running locally, but allow DATABASE_URL override for Docker (/app/railblock.db)
# For Docker, DATABASE_URL=sqlite:///./railblock.db will be resolved relative to WORKDIR /app -> /app/railblock.db
DATABASE_URL = _sanitize_postgres_url(_normalize_postgres_url(os.getenv("DATABASE_URL", f"sqlite:///{_default_db.replace(os.sep, '/')}")))
# Ensure sslmode for Supabase/Render external Postgres (append if missing and is postgres)
if _is_postgres_url(DATABASE_URL) and "sslmode=" not in DATABASE_URL:
    sep = "&" if "?" in DATABASE_URL else "?"
    DATABASE_URL = DATABASE_URL + f"{sep}sslmode=require"
# Add connect_timeout for faster failover on Render (pooled 6543) if not present
if _is_postgres_url(DATABASE_URL) and "connect_timeout" not in DATABASE_URL:
    sep = "&" if "?" in DATABASE_URL else "?"
    DATABASE_URL = DATABASE_URL + f"{sep}connect_timeout=5"

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

def get_database_mode() -> str:
    return "postgres" if is_postgres() else "sqlite"

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

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL and not is_postgres() else {},
    echo=False,
    # Postgres production: pool pre-ping + sizing for Supabase 6543/5432
    **({"pool_pre_ping": True, "pool_size": 5, "max_overflow": 10, "pool_recycle": 300, "pool_timeout": 30} if is_postgres() else {}),
)

# Enable WAL, FK, busy_timeout for every new DBAPI connection (SQLite only)
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if is_postgres():
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
    global engine, SessionLocal
    try:
        want_pg = is_postgres()
        have_pg = str(engine.url).startswith("postgresql") or str(engine.url).startswith("postgres")
        if want_pg != have_pg:
            from sqlalchemy import create_engine as _ce
            new_url = os.getenv("DATABASE_URL", DATABASE_URL)
            # If want_pg but url still sqlite, keep original engine but diagnostics will warn
            if want_pg and new_url.startswith("sqlite"):
                return engine
            new_url = _sanitize_postgres_url(_normalize_postgres_url(new_url))
            if want_pg and "sslmode=" not in new_url:
                sep = "&" if "?" in new_url else "?"
                new_url = new_url + f"{sep}sslmode=require"
            if want_pg and "connect_timeout" not in new_url:
                sep = "&" if "?" in new_url else "?"
                new_url = new_url + f"{sep}connect_timeout=5"
            engine = _ce(
                new_url,
                connect_args={"check_same_thread": False} if "sqlite" in new_url and not want_pg else {},
                echo=False,
                **({"pool_pre_ping": True, "pool_size": 5, "max_overflow": 10, "pool_recycle": 300, "pool_timeout": 30} if want_pg else {}),
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
    # Phase 1a/1c: provenance columns auto-migration (SQLite additive, Postgres via create_all)
    # For existing SQLite files, add missing provenance columns if not present
    if not is_postgres():
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
    if is_postgres():
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
    """Diagnostic report for API or reset script. Postgres-aware."""
    # Postgres diagnostics branch
    if is_postgres():
        try:
            with engine.connect() as conn:
                # Minimal postgres check: server version
                ver = None
                try:
                    ver = conn.execute(text("SELECT version()")).scalar()
                except Exception:
                    ver = "PostgreSQL"
                # live mode for transparency
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
                # Misconfiguration warning: postgres mode but URL still sqlite
                warn = None
                if DATABASE_URL.startswith("sqlite"):
                    warn = "DATABASE_MODE=postgres but DATABASE_URL still sqlite — set DATABASE_URL=postgresql://... and restart. Running in degraded sqlite mode."
                diag = {
                    "database": "PostgreSQL",
                    "journal_mode": "n/a (postgres)",
                    "foreign_keys": True,
                    "busy_timeout": 0,
                    "path": DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL,
                    "database_url": DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL,
                    "database_mode": "postgres",
                    "live_mode": live,
                    "live_sources": live_sources,
                    "server_version": str(ver)[:120] if ver else "unknown",
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
                "path": DATABASE_URL,
                "database_mode": "postgres",
                "error": str(e),
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
            }
    except Exception as e:
        return {
            "database": "SQLite",
            "journal_mode": "unknown",
            "foreign_keys": False,
            "path": _default_db.replace(os.sep, "/"),
            "error": str(e),
        }
