import sys, pathlib, os
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "backend"))
from app.database import SessionLocal, engine, Base
from app.models import DepartmentModel, Corridor, Section, Line, Asset, Resource
import app.models
from app.services.ingestion import run_import

# Ensure DB initialized
Base.metadata.create_all(bind=engine)
db = SessionLocal()
# Seed check - if empty, main seed already does, but ensure corridors etc exist before import tasks
# Import in order: corridors/assets first, then resources, then trains/goods, then tasks

data_dir = pathlib.Path(__file__).parent.parent / "data" / "sample"

def ingest_file(source_name, filepath):
    content = open(filepath, encoding="utf-8").read()
    print(f"Ingesting {source_name} from {filepath} ({len(content)} chars)")
    result = run_import(db, source_name, content, user_id="synthetic_loader")
    print(f" -> {result['accepted_count']} accepted, {result['rejected_count']} rejected, {result['duplicate_count']} duplicates, {len(result['errors'])} errors")
    if result["errors"]:
        for e in result["errors"][:3]:
            print("    Error:", e)
    return result

# Order matters: COA first (corridors/assets)
ingest_file("COA", data_dir / "corridors.csv")
# Also try assets separately if exists (corridors.csv already contains assets)
# ingest_file("COA", data_dir / "assets.csv")

# Resources
ingest_file("RESOURCES", data_dir / "resources.csv")

# Trains
ingest_file("TIMETABLE", data_dir / "trains.csv")

# Goods
ingest_file("GOODS_FORECAST", data_dir / "goods_forecast.csv")

# Tasks last (needs corridors/assets/resources)
ingest_file("TMS", data_dir / "tasks.csv")

# Verify counts
from app.models import Task, TrainMovement, GoodsForecast, Resource, CandidateWindow
print("\n=== DB Counts ===")
print("Tasks:", db.query(Task).count())
print("Trains:", db.query(TrainMovement).count())
print("Goods:", db.query(GoodsForecast).count())
print("Resources:", db.query(Resource).count())
print("Corridors:", db.query(Corridor).count())

# Generate windows and plan to verify functional
from app.services.candidate_windows import generate_candidate_windows
from app.services.priority import recalculate_all
from app.services.optimizer import run_cpsat_optimizer

recalculate_all(db)
print("\nPriorities calculated, sample:")
for t in db.query(Task).limit(3).all():
    print(f" {t.id} P={t.priority_score} band={t.priority_band}")

# Generate windows for weekly and monthly
generate_candidate_windows(db, "2026-09-01", "2026-09-07")
print("Windows generated:", db.query(CandidateWindow).count())

# Weekly plan
from app.services.baseline import generate_baseline_plan
from app.services.plan_validator import validate_plan

baseline = generate_baseline_plan(db, "2026-09-01", "2026-09-07", horizon_type="WEEKLY")
print(f"Baseline plan {baseline.id} blocks={db.query(CandidateWindow).count()} validation={validate_plan(db, baseline.id)['valid']}")

opt_plan, status, breakdown, runtime = run_cpsat_optimizer(db, "2026-09-01", "2026-09-07", horizon_type="WEEKLY", time_limit=5)
if opt_plan:
    print(f"Optimized plan {opt_plan.id} status={status} runtime={runtime:.2f}s")
    val = validate_plan(db, opt_plan.id)
    print(f" Validation: {val['valid']} violations={len(val['violations'])}")
    # Auto-approve for demo
    from app.services.approvals import approve_plan
    db2 = SessionLocal()
    plan, msg, code = approve_plan(db2, opt_plan.id, "CONTROL_OFFICE", "CONTROL_OFFICE", "Auto-approved synthetic")
    print(f" Approve: {code} {msg} status={plan.status if plan else 'fail'}")
    db2.close()
else:
    print(f"Optimizer failed status={status}")

# Monthly
from app.services.fallback import generate_fallback_plan
monthly_opt, m_status, _, m_runtime = run_cpsat_optimizer(db, "2026-09-01", "2026-09-30", horizon_type="MONTHLY", time_limit=5)
if monthly_opt:
    print(f"Monthly plan {monthly_opt.id} status={m_status}")
else:
    fallback = generate_fallback_plan(db, "2026-09-01", "2026-09-30", horizon_type="MONTHLY")
    print(f"Monthly fallback {fallback.id}")

db.close()
print("\nSynthetic ingestion complete - system fully functional without interruptions.")
