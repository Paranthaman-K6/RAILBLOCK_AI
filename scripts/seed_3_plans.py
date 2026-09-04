r"""Seed 3 plans (WEEKLY, MONTHLY, DAILY) — works for both SQLite and Postgres (psql).

Usage:
  # SQLite (default local):
  python scripts/seed_3_plans.py
  python scripts/seed_3_plans.py --reset   # also re-ingests synthetic if tasks missing

  # Postgres / Supabase psql (Render single-instance source of truth):
  # Use pooled 6543 for Render, direct 5432 for local psql
  # Set DATABASE_URL and DATABASE_MODE=postgres before running
  export DATABASE_URL='postgresql://postgres.qgkxdvtrqjhcgnwggzxh:FicRBiXbXhOvJpRa@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres?sslmode=require'
  export DATABASE_MODE=postgres
  python scripts/seed_3_plans.py --reset

  # Or via psql CLI directly (requires psql binary):
  psql "$DATABASE_URL" -c "SELECT id, horizon_type, start_date, end_date, status, solver_status FROM block_plans ORDER BY created_at DESC LIMIT 5;"

  # Verify:
  curl http://localhost:8000/api/plans | jq
  curl http://localhost:8000/health | jq
"""
import sys, pathlib, os, argparse, json, datetime

# Ensure backend on path
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "backend"))

from app.database import engine, SessionLocal, get_diagnostics, is_postgres
from app.services.priority import recalculate_all
from app.services.candidate_windows import generate_candidate_windows
from app.services.baseline import generate_baseline_plan
from app.services.optimizer import run_cpsat_optimizer
from app.services.fallback import generate_fallback_plan
from app.services.plan_validator import validate_plan

def ensure_synthetic_data(db):
    """Ensure corridors/assets/resources/tasks/trains/goods exist. If Task empty, run synthetic ingestion."""
    from app.models import Task, Corridor, Resource
    if db.query(Task).count() > 0 and db.query(Corridor).count() >= 3:
        print(f"[seed] Data exists: Tasks={db.query(Task).count()} Corridors={db.query(Corridor).count()}")
        return
    print("[seed] No tasks/corridors -> ingesting synthetic data (COA->RESOURCES->TIMETABLE->GOODS->TMS)")
    # Use same ingestion as reset_demo
    base = pathlib.Path(__file__).parent.parent
    sample_dir = base / "data" / "sample"
    if not sample_dir.exists():
        sample_dir = pathlib.Path.cwd() / "data" / "sample"
    from app.services.ingestion import run_import
    # Ensure departments exist
    from app.models import DepartmentModel
    if db.query(DepartmentModel).count() == 0:
        for d in ["CONTROL_OFFICE","ENGINEERING","S_AND_T","TRACTION","PROJECTS","VIEWER","ADMIN"]:
            db.add(DepartmentModel(id=d, name=d))
        db.commit()
    for fname, source in [("corridors.csv","COA"),("resources.csv","RESOURCES"),("trains.csv","TIMETABLE"),("goods_forecast.csv","GOODS_FORECAST"),("tasks.csv","TMS")]:
        p = sample_dir / fname
        if p.exists():
            content = p.read_text(encoding="utf-8")
            res = run_import(db, source, content, user_id="seed_3_plans")
            print(f"  {source} {fname}: received={res.get('received_count')} accepted={res.get('accepted_count')} rejected={res.get('rejected_count')} duplicate={res.get('duplicate_count')}")
    recalculate_all(db)
    print("[seed] Priority recalculated")

def clean_existing_plans(db):
    """Optionally clean only plan-related tables, preserving synthetic data."""
    from sqlalchemy import text
    tables = ["plan_changes","approvals","execution_records","block_tasks","blocks","plan_revisions","block_plans","task_window_candidates","task_groups"]
    if is_postgres():
        # Try truncate with cascade, fallback to delete
        try:
            db.execute(text(f'TRUNCATE {", ".join(tables)} RESTART IDENTITY CASCADE'))
            db.commit()
            print("[seed] Truncated existing plans (postgres TRUNCATE CASCADE)")
        except Exception as e:
            db.rollback()
            print(f"[seed] TRUNCATE failed: {e}, trying DELETE")
            for tbl in reversed(tables):
                try:
                    db.execute(text(f'DELETE FROM {tbl}'))
                except Exception:
                    pass
            db.commit()
            print("[seed] Deleted existing plans (fallback)")
    else:
        db.execute(text("PRAGMA foreign_keys=OFF"))
        for tbl in tables:
            try:
                db.execute(text(f"DELETE FROM {tbl}"))
            except Exception:
                pass
        db.execute(text("PRAGMA foreign_keys=ON"))
        db.commit()
        print("[seed] Deleted existing plans (sqlite)")

def full_reset_if_needed(db, force_reset=False):
    """If --reset, do full demo reset (including synthetic re-ingest). Otherwise just ensure data."""
    if force_reset:
        # Call reset_demo logic inline to avoid import side-effects
        print("[seed] --reset requested: full demo reset (preserving schema)")
        from scripts.reset_demo import reset as demo_reset
        # Close current session before reset which opens its own
        db.close()
        result = demo_reset(force=True)
        print(f"[seed] reset result: {result}")
        # Reopen
        db = SessionLocal()
        return db
    else:
        ensure_synthetic_data(db)
        return db

def _delete_plan_cascade(db, plan_id: str):
    """Delete a plan and its blocks/block_tasks/tasks to keep DB at exactly N plans (for baseline cleanup)."""
    from sqlalchemy import text
    try:
        # Use ORM cascade via direct delete (postgres handles via TRUNCATE/CASCADE fallback)
        db.execute(text(f"DELETE FROM block_tasks WHERE block_id IN (SELECT id FROM blocks WHERE plan_id='{plan_id}')"))
        db.execute(text(f"DELETE FROM blocks WHERE plan_id='{plan_id}'"))
        db.execute(text(f"DELETE FROM block_plans WHERE id='{plan_id}'"))
        db.commit()
    except Exception as e:
        try:
            db.rollback()
        except:
            pass
        print(f"[seed] Warning: baseline cleanup failed for {plan_id}: {e}")

def generate_one_plan(db, horizon_start, horizon_end, horizon_type, cleanup_baseline=True):
    """Replicate POST /api/plans/generate logic deterministically for one horizon."""
    print(f"\n=== Generating {horizon_type} {horizon_start} -> {horizon_end} ===")
    recalculate_all(db)
    # generate windows idempotently for horizon (refresh FEASIBLE/REJECTED)
    generate_candidate_windows(db, horizon_start, horizon_end)
    # baseline
    baseline = generate_baseline_plan(db, horizon_start, horizon_end, horizon_type=horizon_type)
    print(f"[seed] Baseline: {baseline.id} solver={baseline.solver_status} blocks_pending_validation")
    # optimizer
    opt_plan, solver_status, objective_breakdown, runtime = run_cpsat_optimizer(db, horizon_start, horizon_end, horizon_type=horizon_type, time_limit=5)
    chosen = None
    if opt_plan:
        val = validate_plan(db, opt_plan.id)
        print(f"[seed] Optimizer: {opt_plan.id} solver={solver_status} valid={val['valid']} runtime={runtime:.2f}s")
        if not val["valid"]:
            print(f"[seed] Optimizer invalid -> fallback: {val['violations'][:2]}")
            fallback = generate_fallback_plan(db, horizon_start, horizon_end, horizon_type=horizon_type)
            val2 = validate_plan(db, fallback.id)
            print(f"[seed] Fallback: {fallback.id} valid={val2['valid']}")
            if not val2["valid"]:
                raise RuntimeError(f"Fallback validation failed: {val2['violations']}")
            chosen = fallback
            chosen.baseline_metrics = baseline.baseline_metrics
            db.commit()
            solver_status = "FALLBACK_USED"
            val_final = val2
        else:
            chosen = opt_plan
            chosen.baseline_metrics = baseline.baseline_metrics
            db.commit()
            val_final = val
    else:
        print(f"[seed] No optimizer plan (INFEASIBLE {solver_status}) -> fallback")
        fallback = generate_fallback_plan(db, horizon_start, horizon_end, horizon_type=horizon_type)
        val = validate_plan(db, fallback.id)
        print(f"[seed] Fallback: {fallback.id} valid={val['valid']} violations={val.get('violations',[])[:2]}")
        if not val["valid"]:
            raise RuntimeError(f"Fallback validation failed: {val['violations']}")
        chosen = fallback
        chosen.baseline_metrics = baseline.baseline_metrics
        db.commit()
        solver_status = "FALLBACK_USED"
        val_final = val
        objective_breakdown = json.loads(chosen.objective_breakdown) if chosen.objective_breakdown else {}
        runtime = 0

    # Final validation
    val_final = validate_plan(db, chosen.id)
    if not val_final["valid"]:
        raise RuntimeError(f"Chosen plan {chosen.id} failed final validation: {val_final['violations']}")
    # Cleanup baseline to keep exactly 1 plan per horizon (total 3), unless baseline is chosen itself
    baseline_id = baseline.id
    chosen_id = chosen.id
    if cleanup_baseline and baseline_id != chosen_id:
        # preserve metrics already copied to chosen.baseline_metrics
        _delete_plan_cascade(db, baseline_id)
        print(f"[seed] Baseline {baseline_id} cleaned up (metrics preserved in chosen)")
        # Re-fetch chosen to ensure session valid after raw deletes
        from app.models import BlockPlan
        chosen = db.query(BlockPlan).filter(BlockPlan.id==chosen_id).first()
    from app.models import Block, BlockTask
    blocks = db.query(Block).filter(Block.plan_id==chosen.id).all()
    # Parse metrics
    baseline_metrics = json.loads(chosen.baseline_metrics) if chosen.baseline_metrics else {}
    optimized_metrics = json.loads(chosen.optimized_metrics) if chosen.optimized_metrics else {}
    print(f"[seed] CHOSEN {chosen.id} horizon={chosen.horizon_type} solver_status={chosen.solver_status or solver_status} valid={val_final['valid']} blocks={len(blocks)} integrated={optimized_metrics.get('integrated_groups', optimized_metrics.get('integrated_block_count', 0))} scheduled={optimized_metrics.get('scheduled', 'n/a')}")
    for b in blocks[:3]:
        bts = db.query(BlockTask).filter(BlockTask.block_id==b.id).all()
        print(f"  - {b.id} {b.service_date} {b.start_time:04d}-{b.end_time:04d} {b.corridor_id} tasks={[bt.task_id for bt in bts]}")
    if len(blocks) > 3:
        print(f"  ... +{len(blocks)-3} more blocks")
    return chosen, len(blocks), val_final

def main():
    parser = argparse.ArgumentParser(description="Seed 3 plans for RailBlock AI (sqlite or postgres/psql)")
    parser.add_argument("--reset", action="store_true", help="Full reset: delete all demo data and re-ingest synthetic before seeding")
    parser.add_argument("--clean-plans", action="store_true", help="Delete existing block_plans/blocks before seeding (default keeps existing, adds new)")
    parser.add_argument("--no-clean", action="store_true", help="Do not clean existing plans; append new plans")
    args = parser.parse_args()

    diag = get_diagnostics()
    print("=== RailBlock AI — Seed 3 Plans ===")
    print(f"Database: {diag.get('database')} mode={diag.get('database_mode', diag.get('database','').lower())}")
    if diag.get("database") == "PostgreSQL":
        # Sanitize URL for log
        url = diag.get("path", "")[:80]
        print(f"  Postgres host: {url}")
        if diag.get("warning"):
            print(f"  WARNING: {diag['warning']}")
    else:
        print(f"  SQLite path: {diag.get('path')} journal_mode={diag.get('journal_mode')} fk={diag.get('foreign_keys')}")
    print(f"  is_postgres()={is_postgres()}")

    db = SessionLocal()
    try:
        # Ensure data
        if args.reset:
            db = full_reset_if_needed(db, force_reset=True)
        else:
            ensure_synthetic_data(db)
            # Generate candidate windows for full horizon upfront (weekly windows already required for monthly)
            # Ensure at least weekly windows exist
            from app.models import CandidateWindow
            if db.query(CandidateWindow).count() == 0:
                generate_candidate_windows(db, "2026-09-01", "2026-09-30")
                print(f"[seed] Generated windows for 2026-09-01->2026-09-30")

        # Decide cleaning
        if args.clean_plans or (not args.no_clean and not args.reset):
            # Default: clean plans unless --no-clean, but if --reset already truncated everything, skip
            if not args.reset:
                clean_existing_plans(db)

        # Seed 3 horizons: WEEKLY, MONTHLY, DAILY (deterministic)
        horizons = [
            ("2026-09-01", "2026-09-07", "WEEKLY"),
            ("2026-09-01", "2026-09-30", "MONTHLY"),
            ("2026-09-03", "2026-09-03", "DAILY"),
        ]

        results = []
        for hs, he, ht in horizons:
            plan, block_count, val = generate_one_plan(db, hs, he, ht)
            results.append((plan, block_count, val, ht))

        # Summary
        from app.models import BlockPlan, Block
        print("\n=== SUMMARY ===")
        total_plans = db.query(BlockPlan).count()
        print(f"Total plans in DB: {total_plans}")
        for plan, bc, val, ht in results:
            bm = json.loads(plan.baseline_metrics) if plan.baseline_metrics else {}
            om = json.loads(plan.optimized_metrics) if plan.optimized_metrics else {}
            print(f"  {plan.id} {ht:7s} {plan.start_date}->{plan.end_date} status={plan.status} solver={plan.solver_status} blocks={bc} valid={val['valid']} scheduled={om.get('scheduled', om.get('blocks', bc))} integrated={om.get('integrated_groups', 0)}")

        # Diagnostics for psql verification
        print("\n=== Verification queries (psql / sqlite) ===")
        if is_postgres():
            print("-- Postgres psql:")
            print("  psql \"$DATABASE_URL\" -c \"SELECT id, horizon_type, start_date, end_date, status, solver_status, version, created_at FROM block_plans ORDER BY created_at DESC LIMIT 5;\"")
            print("  psql \"$DATABASE_URL\" -c \"SELECT plan_id, count(*) as blocks FROM blocks GROUP BY plan_id;\"")
            print("  psql \"$DATABASE_URL\" -c \"SELECT id, horizon_type, solver_status, optimized_metrics FROM block_plans WHERE id IN ('\" + \"','\".join([r[0].id for r in results]) + \"');\"")
        else:
            print("-- SQLite:")
            print("  sqlite3 backend/railblock.db \"SELECT id, horizon_type, start_date, end_date, status, solver_status FROM block_plans ORDER BY created_at DESC LIMIT 5;\"")
            print("  sqlite3 backend/railblock.db \"SELECT plan_id, count(*) FROM blocks GROUP BY plan_id;\"")

        # API quick check
        print("\n=== API check ===")
        print("  curl http://localhost:8000/health")
        print("  curl http://localhost:8000/api/plans | jq")
        for plan,_,_,_ in results:
            print(f"  curl http://localhost:8000/api/plans/{plan.id} | jq '.plan_id, .solver_status, .validation.valid, (.blocks|length)'")

        # Export check
        print("\n=== Export check ===")
        for plan,_,_,_ in results:
            print(f"  curl http://localhost:8000/api/plans/{plan.id}/export?format=csv | head")

        print("\nSeed complete: 3 plans seeded successfully.")

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\n[ERROR] Seed failed: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        try:
            db.close()
        except:
            pass

if __name__ == "__main__":
    main()
