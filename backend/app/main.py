from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from app.database import init_db, get_db
from app.models import DepartmentModel, Corridor, Section, Line, Asset, Resource, RuleConfiguration
import json
from contextlib import asynccontextmanager

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
            import pathlib
            os.environ["DATABASE_MODE"] = "sqlite"
            # ensure fallback URL is sqlite, not stale postgres/mysql URL — use project folder tmp per user
            _proj_root = pathlib.Path(__file__).resolve().parents[2]
            _fallback_tmp = _proj_root / "tmp"
            try:
                _fallback_tmp.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
            _fallback_db = str(_fallback_tmp / "railblock.db")
            # Fallback to legacy backend/railblock.db if tmp not writable
            try:
                if not os.access(str(_fallback_tmp), os.W_OK):
                    _fallback_db = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "railblock.db"))
            except Exception:
                pass
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

# --- Vercel SQLite fallback auto seeding — ensures all features workable without external DB ---
# Uses app.services.synthetic_seeder (robust: CSV + programmatic fallback, Vercel /tmp handling,
# candidate windows, recalculate priorities). Wrapped to not crash app if DB unreachable.
# Skip for postgres/mysql to avoid QueuePool exhaustion on pooled Supabase (logs: QueuePool limit 5 overflow 10 reached)
try:
    from app.database import is_postgres, is_mysql
    _is_external = is_postgres() or is_mysql()
    if _is_external:
        log.info(f"Import-time seeding skipped for external DB (postgres/mysql) — seeding via lifespan/middleware or manual import")
    else:
        from app.services.synthetic_seeder import ensure_synthetic_seeded, is_db_seeded
        from app.database import SessionLocal as _SeedSessionLocal
        _seed_db = _SeedSessionLocal()
        try:
            # Use get_seeding_status to decide if import-time seeding needed
            from app.services.synthetic_seeder import get_seeding_status
            _status = get_seeding_status(_seed_db)
            # If tasks/windows missing, trigger full ensure (covers Vercel /tmp empty DB)
            if _status.get("tasks", 0) == 0 or _status.get("windows", 0) == 0 or _status.get("corridors", 0) == 0:
                log.info(f"Import-time seeding: status {_status} -> ensure_synthetic_seeded()")
                # ensure_synthetic_seeded creates its own session if needed, but we pass existing for consistency
                ensure_synthetic_seeded(_seed_db)
            else:
                log.debug(f"Import-time seeding skipped — already seeded: {_status}")
        except Exception as _e:
            log.warning(f"Import-time Vercel fallback seeding skipped: {_e}")
            try:
                _seed_db.rollback()
            except Exception:
                pass
        finally:
            try:
                _seed_db.close()
            except Exception:
                pass
except Exception as _se_import_err:
    log.warning(f"Synthetic seeder import failed (non-fatal): {_se_import_err}")

# Lifespan for Vercel cold start + lazy fallback ensures DB always workable
# For postgres/mysql, skip lifespan seeding to avoid QueuePool exhaustion (pooled Supabase already seeded via Composio)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure synthetic data seeded (idempotent) — skip for external DB to avoid pool timeout
    try:
        from app.database import is_postgres, is_mysql
        if is_postgres() or is_mysql():
            log.info(f"Lifespan seeding skipped for external DB (postgres/mysql) — DB already seeded via Supabase/Composio")
        else:
            from app.services.synthetic_seeder import ensure_synthetic_seeded as _ensure
            _s = _ensure()
            log.info(f"Lifespan startup seeding ensured: {_s}")
    except Exception as e:
        log.warning(f"Lifespan seeding skipped: {e}")
    yield
    # Shutdown: nothing

app = FastAPI(
    lifespan=lifespan,
    title="RailBlock AI - Human-approved planning and decision-support prototype",
    description="**Not** an autonomous railway-control system. **Not** a railway-certified safety system. Synthetic prototype windows, not official railway availability. Prototype disclaimer: This application uses synthetic demonstration data and prototype operational rules. It does not access live TMS, SMMS, TDMS, COA, timetable, or railway-control systems. It must not be used for real railway operations. Production use would require authorized data integration, railway-domain validation, cybersecurity review, safety approval, and operational certification.",
    version="1.0.0"
)

# Lazy fallback auto-seeding middleware for Vercel SQLite (ensures all features workable even without lifespan)
# Caches verification per-process to avoid per-request DB scan overhead
_seed_check_cache = {"checked": False, "last_status": None, "ts": 0.0}
import time as _seed_time
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    # Map to {error:{code,message,details}} without traceback, keep 'detail' for backward compat with existing tests
    code = "HTTP_ERROR"
    if exc.status_code == 400:
        code = "BAD_REQUEST"
    elif exc.status_code == 404:
        code = "NOT_FOUND"
    elif exc.status_code == 409:
        code = "CONFLICT"
    elif exc.status_code == 403:
        code = "FORBIDDEN"
    details = {}
    try:
        if "plan_id" in request.path_params:
            details["plan_id"] = request.path_params["plan_id"]
    except:
        pass
    msg = str(exc.detail) if exc.detail else "Request failed"
    if "No data -> no plan" in msg:
        code = "NO_DATA"
    elif "Plan validation failed" in msg or "validation" in msg.lower():
        code = "PLAN_NOT_VALIDATED"
    elif "Approved and published plans are immutable" in msg:
        code = "PLAN_IMMUTABLE"
    elif "Completed and approved work cannot be moved" in msg:
        code = "COMPLETED_BLOCK_LOCKED"
    elif "Duplicate execution" in msg:
        code = "DUPLICATE_EXECUTION"
    # Dual format: new envelope + legacy detail for test compatibility
    return JSONResponse(status_code=exc.status_code, content={"error": {"code": code, "message": msg, "details": details}, "detail": msg, "code": code})

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"error": {"code": "VALIDATION_ERROR", "message": "Validation failed", "details": {"errors": exc.errors()}}})

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    # Never expose raw traceback to frontend
    return JSONResponse(status_code=500, content={"error": {"code": "INTERNAL_ERROR", "message": "Internal server error. Check server logs.", "details": {}}})

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://localhost:5174", "http://localhost:3000",
        "http://127.0.0.1:5173", "http://127.0.0.1:5174", "http://127.0.0.1:3000",
        "https://railblock-ai-up0g.onrender.com",
        "https://railblock-ai.getvoroa.com",
        "https://railblock-ai-gamma.vercel.app",
    ],
    allow_origin_regex=r"https://.*\.vercel\.app|https://.*\.getvoroa\.com|http://localhost:\d+|http://127\.0\.0\.1:\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Fallback auto-seed middleware: for Vercel SQLite, ensure synthetic data present on first API hit
# (covers case where lifespan didn't run or /tmp DB was wiped). Cached + 60s TTL to avoid DB overhead.
@app.middleware("http")
async def vercel_fallback_seed_middleware(request: Request, call_next):
    # Only for API/health/docs, not for static assets or preflight, and only for sqlite
    path = request.url.path or ""
    # Skip CORS preflight quickly
    if request.method == "OPTIONS":
        return await call_next(request)
    # Skip static assets (/_next, /assets/, .js, .css, etc.) — only seed for API/health
    if path.startswith("/assets/") or path.startswith("/_next/") or path.endswith(".js") or path.endswith(".css") or path.endswith(".map"):
        return await call_next(request)
    # Only relevant for sqlite (vercel fallback) — skip if postgres/mysql explicitly configured
    try:
        from app.database import is_sqlite, is_postgres, is_mysql
        # If external DB configured, never auto-seed sqlite (health will report degraded until external DB reachable)
        if is_postgres() or is_mysql():
            return await call_next(request)
        if not is_sqlite():
            return await call_next(request)
    except Exception:
        # If DB mode check fails, still try seeding (conservative)
        pass
    # Throttle checks: at most once per 30s or until seeded
    now = _seed_time.time()
    should_check = False
    if not _seed_check_cache.get("checked"):
        should_check = True
    elif _seed_check_cache.get("last_status") and not _seed_check_cache["last_status"].get("is_seeded"):
        # Last check was not seeded — retry every 10s
        if now - _seed_check_cache.get("ts", 0) > 10:
            should_check = True
    else:
        # Already seeded — re-check every 60s in case /tmp wiped (Vercel lambda ephemeral)
        if now - _seed_check_cache.get("ts", 0) > 60:
            should_check = True
    if should_check:
        try:
            # Only seed for API/health/docs/openapi — ensures first real request seeds
            if path.startswith("/api/") or path.startswith("/health") or path.startswith("/docs") or path.startswith("/openapi"):
                from app.services.synthetic_seeder import is_db_seeded, ensure_synthetic_seeded, get_seeding_status
                from app.database import SessionLocal as _MidSessionLocal
                # Quick check: open ephemeral session, check is_db_seeded
                _mid_db = _MidSessionLocal()
                try:
                    # Use is_db_seeded to avoid expensive full status unless needed
                    if not is_db_seeded(_mid_db):
                        # /tmp DB empty → ensure seeding (handles CSV + fallback)
                        # Close check session before ensure (ensure creates its own if None, or reuse)
                        try:
                            _mid_db.close()
                        except Exception:
                            pass
                        # Call ensure with None to let seeder manage session/rollback
                        _status = ensure_synthetic_seeded(None)
                        _seed_check_cache["last_status"] = _status
                        _seed_check_cache["ts"] = now
                        # Mark checked after successful seeding
                        if _status.get("is_seeded"):
                            _seed_check_cache["checked"] = True
                        else:
                            _seed_check_cache["checked"] = False
                        log.info(f"Vercel fallback middleware seeded: {_status}")
                    else:
                        # Already seeded — cache status
                        try:
                            _status = get_seeding_status(_mid_db)
                            _status["is_seeded"] = True
                            _seed_check_cache["last_status"] = _status
                            _seed_check_cache["ts"] = now
                            _seed_check_cache["checked"] = True
                        except Exception:
                            pass
                finally:
                    try:
                        _mid_db.close()
                    except Exception:
                        pass
        except Exception as e:
            log.warning(f"Vercel fallback middleware seeding error (non-fatal): {e}")
            _seed_check_cache["ts"] = now
    # Continue to downstream handler
    response = await call_next(request)
    return response

# Routers
from app.routers.health import router as health_router
from app.routers.imports import router as import_router
from app.routers.tasks import router as task_router
from app.routers.windows import router as window_router
from app.routers.plans import router as plan_router
from app.routers.departments import router as dept_router
from app.routers.execution import router as exec_router
from app.routers.conflicts import router as conflict_router
from app.routers.metrics import router as metrics_router
from app.routers.optimizer import router as optimizer_router
from app.routers.corridors import router as corr_router

app.include_router(health_router)
app.include_router(import_router)
app.include_router(task_router)
app.include_router(window_router)
app.include_router(plan_router)
app.include_router(dept_router)
app.include_router(exec_router)
app.include_router(conflict_router)
app.include_router(metrics_router)
app.include_router(optimizer_router)
# corr_router duplicates handled in tasks, but include for /api/corridors alias if not conflicting
# app.include_router(corr_router)

# Additional aliases to match spec exactly
from fastapi import APIRouter
import pathlib, os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.gzip import GZipMiddleware

app.add_middleware(GZipMiddleware, minimum_size=500)

# Single-image static serving: serve frontend/dist as /app/static (docker) or frontend/dist (local)
_static_candidates = [
    pathlib.Path("/app/static"),
    pathlib.Path(__file__).resolve().parents[1] / "static",  # backend/static
    pathlib.Path(__file__).resolve().parents[2] / "static",  # project static
    pathlib.Path(__file__).resolve().parents[2] / "frontend" / "dist",
    pathlib.Path(__file__).resolve().parents[1].parent / "frontend" / "dist",
]
STATIC_DIR = None
for _cand in _static_candidates:
    # verify via both pathlib and os.path.exists for robustness (Render single-image)
    if _cand.exists() and (_cand / "index.html").exists() and os.path.exists(str(_cand / "index.html")):
        STATIC_DIR = _cand
        break
if STATIC_DIR is not None and (STATIC_DIR / "assets").exists() and os.path.exists(str(STATIC_DIR / "assets")):
    app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")
    @app.get("/", include_in_schema=False)
    async def _spa_root():
        # FileResponse via os.path.exists verified static/index.html
        assert os.path.exists(str(STATIC_DIR / "index.html"))
        return FileResponse(str(STATIC_DIR / "index.html"))

# GET /api/departments already in task_router, ensure
# GET /api/windows already
# GET /api/plans/{id}/explanations
@app.get("/api/plans/{plan_id}/explanations")
def explanations(plan_id: str, db: Session = Depends(get_db)):
    from app.models import BlockPlan, Block, BlockTask, Task
    from app.services.priority import compute_priority
    plan = db.query(BlockPlan).filter(BlockPlan.id==plan_id.upper()).first()
    if not plan:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Plan not found")
    blocks = db.query(Block).filter(Block.plan_id==plan.id).all()
    exps=[]
    for blk in blocks:
        for bt in db.query(BlockTask).filter(BlockTask.block_id==blk.id).all():
            t = db.query(Task).filter(Task.id==bt.task_id).first()
            if t:
                exp = compute_priority(t)
                exps.append({"task_id":t.id,"block_id":blk.id,"priority_score":exp["priority_score"],"priority_band":exp["priority_band"],"priority_reason":exp["priority_reason"],"factor_weights":exp["factor_weights"]})
    return exps

# SPA fallback — must be last, after all API routes (explanations, docs, health)
if STATIC_DIR is not None and (STATIC_DIR / "assets").exists() and os.path.exists(str(STATIC_DIR / "index.html")):
    @app.get("/{full_path:path}", include_in_schema=False)
    async def _spa_fallback(full_path: str):
        if full_path.startswith(("api", "health", "docs", "openapi.json", "redoc")):
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Not found")
        candidate = STATIC_DIR / full_path
        # serve static file if exists, else SPA index.html — verified via os.path.exists + FileResponse
        if full_path and os.path.exists(str(candidate)) and candidate.exists() and candidate.is_file():
            return FileResponse(str(candidate))
        # fallback to index.html for SPA routing (non-api/health/docs paths)
        assert os.path.exists(str(STATIC_DIR / "index.html"))
        return FileResponse(str(STATIC_DIR / "index.html"))

# For frontend to fetch plan explanations etc already covered
