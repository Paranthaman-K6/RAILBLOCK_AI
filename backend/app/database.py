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

def _is_mysql_url(url: Optional[str] = None) -> bool:
    u = url or DATABASE_URL or ""
    return u.startswith("mysql://") or u.startswith("mysql+pymysql://")

def _normalize_mysql_url(url: str) -> str:
    """Convert mysql:// to mysql+pymysql:// and strip ssl params to be handled via connect_args.
    Aiven requires SSL; we keep a flag and pass ssl via connect_args instead of URL query.
    """
    global _MYSQL_SSL_REQUIRED
    try:
        low = url.lower()
        if "ssl-mode=required" in low or "ssl_mode=required" in low or "sslmode=require" in low or "ssl=require" in low:
            _MYSQL_SSL_REQUIRED = True
    except Exception:
        pass
    if url.startswith("mysql://"):
        url = "mysql+pymysql://" + url[len("mysql://"):]
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
            if changed:
                new_q = urlencode({k: v[0] if len(v)==1 else v for k,v in q.items()}, doseq=False)
                url = urlunparse((p.scheme, p.netloc, p.path, p.params, new_q, p.fragment))
                if url.endswith("?"):
                    url = url[:-1]
    except Exception:
        pass
    return url

_MYSQL_SSL_REQUIRED = False

_raw_db_url = os.getenv("DATABASE_URL", f"sqlite:///{_default_db.replace(os.sep, '/')}")
_raw_db_url = _normalize_postgres_url(_raw_db_url)
_raw_db_url = _normalize_mysql_url(_raw_db_url)
DATABASE_URL = _sanitize_postgres_url(_raw_db_url)
if _is_postgres_url(DATABASE_URL) and "sslmode=" not in DATABASE_URL:
    sep = "&" if "?" in DATABASE_URL else "?"
    DATABASE_URL = DATABASE_URL + f"{sep}sslmode=require"
if _is_postgres_url(DATABASE_URL) and "connect_timeout" not in DATABASE_URL:
    sep = "&" if "?" in DATABASE_URL else "?"
    DATABASE_URL = DATABASE_URL + f"{sep}connect_timeout=5"

def is_postgres() -> bool:
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
