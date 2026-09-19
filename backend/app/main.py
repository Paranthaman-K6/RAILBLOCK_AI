from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from app.database import init_db, get_db
from app.models import DepartmentModel, Corridor, Section, Line, Asset, Resource, RuleConfiguration
import json

import logging
log = logging.getLogger(__name__)
try:
    init_db()
except Exception as e:
    # Guard: if postgres/mysql is explicitly configured, do NOT silently fallback to sqlite — keep configured mode for diagnostics
    import os as _os_fb
    _fb_mode = _os_fb.getenv("DATABASE_MODE", "")
    _fb_url = _os_fb.getenv("DATABASE_URL", "")
    _is_pg_configured = _fb_mode.lower() in ("postgres", "postgresql", "pg") or _fb_url.startswith("postgresql://") or _fb_url.startswith("postgres://")
    _is_mysql_configured = _fb_mode.lower() in ("mysql", "maria", "mariadb") or _fb_url.startswith("mysql://") or _fb_url.startswith("mysql+pymysql://")
    if _is_pg_configured:
        log.error(f"init_db failed with PostgreSQL configured (DATABASE_MODE={_fb_mode}, URL pool), not falling back to SQLite: {e}. Health will report PostgreSQL degraded until DB reachable. Check DATABASE_URL pooled ap-southeast-1 and Supabase pooler.")
        # Do not switch to sqlite; keep postgres engine — seeding will retry on next request via SessionLocal
        pass
    elif _is_mysql_configured:
        log.error(f"init_db failed with MySQL configured (DATABASE_MODE={_fb_mode}, URL Aiven), not falling back to SQLite: {e}. Health will report MySQL degraded until DB reachable. Check DATABASE_URL Aiven mysql host:port and SSL.")
        # Do not switch to sqlite; keep mysql engine — seeding will retry on next request via SessionLocal
        pass
    else:
        log.warning(f"init_db failed, attempting SQLite fallback: {e}")
        try:
            import os
            os.environ["DATABASE_MODE"] = "sqlite"
            # ensure fallback URL is sqlite, not stale postgres/mysql URL
            _fallback_db = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "railblock.db"))
            os.environ["DATABASE_URL"] = f"sqlite:///{_fallback_db.replace(os.sep, '/')}"
            from app.database import get_engine
            get_engine.cache_clear() if hasattr(get_engine, "cache_clear") else None
            try:
                get_engine()
            except Exception:
                pass
            init_db()
            log.warning("Degraded to SQLite after init_db failure")
        except Exception as e2:
            log.error(f"Fallback init_db also failed: {e2}")
