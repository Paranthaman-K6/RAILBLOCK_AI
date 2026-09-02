from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from app.database import init_db, get_db
from app.models import DepartmentModel, Corridor, Section, Line, Asset, Resource, RuleConfiguration
import json

# init
init_db()
# seed departments and corridors if empty
from app.database import SessionLocal
db = SessionLocal()
try:
    if db.query(DepartmentModel).count()==0:
        for d in ["CONTROL_OFFICE","ENGINEERING","S_AND_T","TRACTION","PROJECTS","VIEWER","ADMIN"]:
            db.add(DepartmentModel(id=d, name=d))
        db.commit()
    if db.query(Corridor).count()==0:
        # seed comprehensive corridors/sections/lines/assets/resources for fully functional synthetic demo (3 corridors, 6 sections, 8 lines, 12 assets, 14 resources)
        db.add(Corridor(id="COR-1", name="Delhi-Howrah Corridor"))
        db.add(Corridor(id="COR-2", name="Mumbai-Chennai Corridor"))
        db.add(Corridor(id="COR-3", name="Howrah-Chennai Corridor"))
        db.commit()
        db.add(Section(id="SEC-1", corridor_id="COR-1", name="Ghaziabad - Tundla", from_km=0, to_km=120))
        db.add(Section(id="SEC-2", corridor_id="COR-1", name="Tundla - Kanpur", from_km=120, to_km=320))
        db.add(Section(id="SEC-3", corridor_id="COR-2", name="Kalyan - Pune", from_km=0, to_km=150))
        db.add(Section(id="SEC-4", corridor_id="COR-2", name="Pune - Solapur", from_km=150, to_km=350))
        db.add(Section(id="SEC-5", corridor_id="COR-3", name="Vijayawada - Chennai", from_km=0, to_km=400))
        db.add(Section(id="SEC-6", corridor_id="COR-3", name="Kharagpur - Bhubaneswar", from_km=400, to_km=700))
        db.commit()
        db.add(Line(id="LIN-1", section_id="SEC-1", corridor_id="COR-1", line_type="UP", name="UP Line Sec-1"))
        db.add(Line(id="LIN-2", section_id="SEC-1", corridor_id="COR-1", line_type="DOWN", name="DOWN Line Sec-1"))
        db.add(Line(id="LIN-3", section_id="SEC-2", corridor_id="COR-1", line_type="UP", name="UP Line Sec-2"))
        db.add(Line(id="LIN-4", section_id="SEC-2", corridor_id="COR-1", line_type="DOWN", name="DOWN Line Sec-2"))
        db.add(Line(id="LIN-5", section_id="SEC-3", corridor_id="COR-2", line_type="SINGLE", name="Single Line Sec-3"))
        db.add(Line(id="LIN-6", section_id="SEC-4", corridor_id="COR-2", line_type="LOOP", name="Loop Line Sec-4"))
        db.add(Line(id="LIN-7", section_id="SEC-5", corridor_id="COR-3", line_type="UP", name="UP Line Sec-5"))
        db.add(Line(id="LIN-8", section_id="SEC-6", corridor_id="COR-3", line_type="DOWN", name="DOWN Line Sec-6"))
        db.commit()
        db.add(Asset(id="AST-1", corridor_id="COR-1", section_id="SEC-1", line_id="LIN-1", asset_type="TRACK", asset_criticality=92, location_km=15))
        db.add(Asset(id="AST-2", corridor_id="COR-1", section_id="SEC-1", line_id="LIN-2", asset_type="OHE", asset_criticality=88, location_km=22.5))
        db.add(Asset(id="AST-3", corridor_id="COR-1", section_id="SEC-2", line_id="LIN-3", asset_type="SIGNAL", asset_criticality=85, location_km=145))
        db.add(Asset(id="AST-4", corridor_id="COR-1", section_id="SEC-2", line_id="LIN-4", asset_type="TRACK", asset_criticality=78, location_km=180))
        db.add(Asset(id="AST-5", corridor_id="COR-2", section_id="SEC-3", line_id="LIN-5", asset_type="TRACK", asset_criticality=75, location_km=45))
        db.add(Asset(id="AST-6", corridor_id="COR-2", section_id="SEC-3", line_id="LIN-5", asset_type="BRIDGE", asset_criticality=90, location_km=60))
        db.add(Asset(id="AST-7", corridor_id="COR-2", section_id="SEC-4", line_id="LIN-6", asset_type="OHE", asset_criticality=82, location_km=200))
        db.add(Asset(id="AST-8", corridor_id="COR-2", section_id="SEC-4", line_id="LIN-6", asset_type="SIGNAL", asset_criticality=80, location_km=220))
        db.add(Asset(id="AST-9", corridor_id="COR-3", section_id="SEC-5", line_id="LIN-7", asset_type="TRACK", asset_criticality=70, location_km=100))
        db.add(Asset(id="AST-10", corridor_id="COR-3", section_id="SEC-5", line_id="LIN-7", asset_type="OHE", asset_criticality=77, location_km=150))
        db.add(Asset(id="AST-11", corridor_id="COR-3", section_id="SEC-6", line_id="LIN-8", asset_type="TRACK", asset_criticality=84, location_km=500))
        db.add(Asset(id="AST-12", corridor_id="COR-3", section_id="SEC-6", line_id="LIN-8", asset_type="SIGNAL", asset_criticality=86, location_km=550))
        db.commit()
        db.add(Resource(id="RES-1", resource_type="CREW", name="Track Gang A", department="ENGINEERING", capacity=2))
        db.add(Resource(id="RES-2", resource_type="CREW", name="Track Gang B", department="ENGINEERING", capacity=2))
        db.add(Resource(id="RES-3", resource_type="MACHINE", name="Tamping Machine M1", department="ENGINEERING", capacity=1))
        db.add(Resource(id="RES-4", resource_type="MACHINE", name="Welding Plant W1", department="ENGINEERING", capacity=1))
        db.add(Resource(id="RES-5", resource_type="MATERIAL", name="Ballast Stock", department="ENGINEERING", capacity=10))
        db.add(Resource(id="RES-6", resource_type="CREW", name="Signal Team S1", department="S_AND_T", capacity=2))
        db.add(Resource(id="RES-7", resource_type="CREW", name="Signal Team S2", department="S_AND_T", capacity=2))
        db.add(Resource(id="RES-8", resource_type="MACHINE", name="Signal Test Van", department="S_AND_T", capacity=1))
        db.add(Resource(id="RES-9", resource_type="CREW", name="OHE Crew O1", department="TRACTION", capacity=2))
        db.add(Resource(id="RES-10", resource_type="CREW", name="OHE Crew O2", department="TRACTION", capacity=2))
        db.add(Resource(id="RES-11", resource_type="MACHINE", name="Tower Wagon", department="TRACTION", capacity=1))
        db.add(Resource(id="RES-12", resource_type="CREW", name="Project Team P1", department="PROJECTS", capacity=3))
        db.add(Resource(id="RES-13", resource_type="MACHINE", name="Crane 100T", department="PROJECTS", capacity=1))
        db.add(Resource(id="RES-14", resource_type="CREW", name="Control Office", department="CONTROL_OFFICE", capacity=5))
        db.commit()
    # Auto-ingest synthetic tasks/trains/goods if Task table empty (fully functional without manual import)
    from app.models import Task, TrainMovement, GoodsForecast
    if db.query(Task).count()==0:
        try:
            import pathlib
            from app.services.ingestion import run_import
            base = pathlib.Path(__file__).parent.parent.parent  # project root
            sample_dir = base / "data" / "sample"
            # also try alternative path
            if not sample_dir.exists():
                sample_dir = pathlib.Path("D:/PROJECT2/MAYBE/RAIL/data/sample")
            for fname, source in [("corridors.csv","COA"),("resources.csv","RESOURCES"),("trains.csv","TIMETABLE"),("goods_forecast.csv","GOODS_FORECAST"),("tasks.csv","TMS")]:
                p = sample_dir / fname
                if p.exists():
                    content = p.read_text(encoding="utf-8")
                    # use separate session to avoid nesting issues
                    from app.database import SessionLocal as SL2
                    db2 = SL2()
                    try:
                        run_import(db2, source, content, user_id="auto_synthetic")
                    finally:
                        db2.close()
            # refresh counts
            db.expire_all()
        except Exception as e:
            print(f"Auto synthetic ingestion failed: {e}")
            try:
                db.rollback()
            except:
                pass
    if db.query(RuleConfiguration).count()==0:
        db.add(RuleConfiguration(id="RULE-1", version="v1", priority_weights=json.dumps({"S":0.30,"U":0.20,"C":0.20,"O":0.15,"D":0.10,"R":0.05}), optimizer_weights=json.dumps({"priority":1.0}), hard_constraints=json.dumps(["train conflict","resource overlap"]), ai_model=json.dumps({"explainable":True})))
        db.commit()
finally:
    db.close()

app = FastAPI(
    title="RailBlock AI - Human-approved planning and decision-support prototype",
    description="**Not** an autonomous railway-control system. **Not** a railway-certified safety system. Synthetic prototype windows, not official railway availability. Prototype disclaimer: This application uses synthetic demonstration data and prototype operational rules. It does not access live TMS, SMMS, TDMS, COA, timetable, or railway-control systems. It must not be used for real railway operations. Production use would require authorized data integration, railway-domain validation, cybersecurity review, safety approval, and operational certification.",
    version="1.0.0"
)

# Consistent error envelope - never expose raw tracebacks
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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    if _cand.exists() and (_cand / "index.html").exists():
        STATIC_DIR = _cand
        break
if STATIC_DIR is not None and (STATIC_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")
    @app.get("/", include_in_schema=False)
    async def _spa_root():
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
if STATIC_DIR is not None and (STATIC_DIR / "assets").exists():
    @app.get("/{full_path:path}", include_in_schema=False)
    async def _spa_fallback(full_path: str):
        if full_path.startswith(("api", "health", "docs", "openapi.json", "redoc")):
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Not found")
        candidate = STATIC_DIR / full_path
        if full_path and candidate.exists() and candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(STATIC_DIR / "index.html"))

# For frontend to fetch plan explanations etc already covered
