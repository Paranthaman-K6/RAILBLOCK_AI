r"""RailBlock AI - Safe idempotent demo reset.

Usage (PowerShell 5.1, no &&):
  Set-Location -LiteralPath "D:\PROJECT2\MAYBE\RAIL"
  python scripts\reset_demo.py
  # or with force to ignore server lock
  python scripts\reset_demo.py --force
"""
import sys, pathlib, os, argparse, json
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "backend"))
from app.database import engine, Base, get_diagnostics, SessionLocal
import app.models
from sqlalchemy import text

def is_server_using_db():
    """Detect active server by trying to get exclusive lock or check WAL file existence with recent modify."""
    db_path = None
    try:
        diag = get_diagnostics()
        db_path = diag.get("path", "")
        # Normalize
        if db_path and os.path.exists(db_path):
            # Check -wal and -shm sidecars recent
            wal = db_path + "-wal"
            shm = db_path + "-shm"
            # Try to acquire busy_timeout check via direct sqlite connection
            import sqlite3
            # Attempt to open with immediate transaction - if busy, server is active
            try:
                conn = sqlite3.connect(db_path, timeout=1.0, isolation_level=None)
                try:
                    conn.execute("BEGIN IMMEDIATE;")
                    conn.execute("ROLLBACK;")
                    conn.close()
                    return False, "No active transaction lock detected."
                except sqlite3.OperationalError as e:
                    conn.close()
                    if "busy" in str(e).lower() or "locked" in str(e).lower():
                        return True, f"Database is locked (server likely running): {e}"
                    return False, f"OperationalError but not busy: {e}"
            except Exception as e:
                return False, f"sqlite3 check failed: {e}"
        return False, "DB file not yet created or no lock."
    except Exception as e:
        return False, f"Check failed: {e}"

def reset(force=False):
    from app.database import is_postgres
    diag_before = get_diagnostics()
    locked, reason = is_server_using_db()
    if locked and not force:
        print("WARNING: Active server appears to be using the database.")
        print(f"Reason: {reason}")
        print("Use --force to proceed anyway, or stop the server and retry.")
        print("Attempting safe reset with busy_timeout handling...")
        if not force:
            print("\nAborting reset. Run with --force if you are sure no server is writing.")
            sys.exit(1)
    else:
        if locked:
            print(f"WARNING (--force): {reason} - proceeding anyway.")

    print("Resetting RailBlock AI demo database...")
    # Preserve schema, remove all demo data safely (postgres vs sqlite)
    db = SessionLocal()
    try:
        tables = [
            "plan_changes","approvals","execution_records","block_tasks","blocks",
            "plan_revisions","block_plans","task_window_candidates","task_groups",
            "task_dependencies","task_resources","candidate_windows",
            "import_runs","audit_events","notifications","source_cursors",
            "resource_availabilities","goods_forecasts","train_movements","tasks",
            "assets","lines","sections","corridors","resources"
        ]
        if is_postgres():
            # Postgres: TRUNCATE with RESTART IDENTITY CASCADE handles FKs and sequences
            try:
                db.execute(text(f'TRUNCATE {", ".join(tables)} RESTART IDENTITY CASCADE'))
                db.commit()
            except Exception:
                db.rollback()
                for tbl in reversed(tables):
                    try:
                        db.execute(text(f'DELETE FROM {tbl}'))
                    except Exception:
                        pass
                db.commit()
        else:
            db.execute(text("PRAGMA foreign_keys=OFF"))
            seen=set(); ordered=[]
            for t in tables:
                if t not in seen:
                    seen.add(t)
                    ordered.append(t)
            for tbl in ordered:
                try:
                    db.execute(text(f"DELETE FROM {tbl}"))
                except Exception:
                    pass
            db.execute(text("PRAGMA foreign_keys=ON"))
            db.commit()
    except Exception as e:
        try:
            db.rollback()
        except:
            pass
        print(f"Failed to clear data: {e}")
        sys.exit(1)
    finally:
        db.close()

    # Re-enable pragmas (sqlite only)
    if not is_postgres():
        try:
            with engine.connect() as conn:
                conn.execute(text("PRAGMA foreign_keys=ON;"))
                conn.execute(text("PRAGMA journal_mode=WAL;"))
                conn.execute(text("PRAGMA busy_timeout=5000;"))
                conn.commit()
        except Exception:
            pass

    # Automatically ingest synthetic data (idempotent) - do NOT pre-seed infrastructure separately;
    # ingestion via COA/RESOURCES will create corridors/assets/resources, achieving Duplicate 0 on clean reset.
    # Ensure minimal departments exist (required FK for UserContext but not for core demo)
    from app.database import Base
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        from app.models import DepartmentModel
        if db.query(DepartmentModel).count()==0:
            for d in ["CONTROL_OFFICE","ENGINEERING","S_AND_T","TRACTION","PROJECTS","VIEWER","ADMIN"]:
                db.add(DepartmentModel(id=d, name=d))
            db.commit()
    finally:
        db.close()
    from app.services.ingestion import run_import
    import pathlib
    base = pathlib.Path(__file__).parent.parent
    sample_dir = base / "data" / "sample"
    if not sample_dir.exists():
        sample_dir = pathlib.Path(__file__).resolve().parents[1] / "data" / "sample"
    if not sample_dir.exists():
        sample_dir = pathlib.Path.cwd() / "data" / "sample"
    # Ensure deterministic order and capture stats
    total_invalid=0
    total_dup=0
    for fname, source in [("corridors.csv","COA"),("resources.csv","RESOURCES"),("trains.csv","TIMETABLE"),("goods_forecast.csv","GOODS_FORECAST"),("tasks.csv","TMS")]:
        p = sample_dir / fname
        if p.exists():
            content = p.read_text(encoding="utf-8")
            db2 = SessionLocal()
            try:
                res = run_import(db2, source, content, user_id="reset_demo")
                total_invalid += res.get("rejected_count",0)
                total_dup += res.get("duplicate_count",0)
            finally:
                db2.close()

    # Recalculate priorities
    from app.services.priority import recalculate_all
    db = SessionLocal()
    try:
        recalculate_all(db)
    finally:
        db.close()

    # Generate windows only when required (if none for demo horizon)
    from app.services.candidate_windows import generate_candidate_windows
    db = SessionLocal()
    try:
        from app.models import CandidateWindow
        if db.query(CandidateWindow).count()==0:
            generate_candidate_windows(db, "2026-09-01", "2026-09-07")
    finally:
        db.close()

    # Verification report
    db = SessionLocal()
    try:
        from app.models import Task, TrainMovement, GoodsForecast, Resource, Corridor, CandidateWindow, ImportRun
        tasks = db.query(Task).count()
        trains = db.query(TrainMovement).count()
        goods = db.query(GoodsForecast).count()
        resources = db.query(Resource).count()
        corridors = db.query(Corridor).count()
        windows = db.query(CandidateWindow).count()
        # invalid/duplicate from last import runs
        # Also check journal mode
        diag = get_diagnostics()
        jm = diag.get("journal_mode","unknown")
        fk = diag.get("foreign_keys", False)
        invalid = db.query(ImportRun).all()
        # sum rejected from recent runs
        total_rejected = sum(ir.rejected_count for ir in db.query(ImportRun).all()) if db.query(ImportRun).count() else 0
        total_dup_all = sum(ir.duplicate_count for ir in db.query(ImportRun).all()) if db.query(ImportRun).count() else 0
        # For spec we want current run invalid/duplicate (not historical sum), use last run values already captured
        print("\nRailBlock AI demo reset complete")
        print(f"Tasks: {tasks}")
        print(f"Trains: {trains}")
        print(f"Goods forecasts: {goods}")
        print(f"Resources: {resources}")
        print(f"Corridors: {corridors}")
        print(f"Windows: {windows}")
        print(f"Invalid records: {total_invalid}")
        print(f"Duplicate records: {total_dup}")
        print(f"Database journal mode: {jm}")
        print(f"Foreign keys: {fk}")
        print(f"Database path: {diag.get('path','')}")
        # Return for tests
        return {
            "tasks": tasks, "trains": trains, "goods": goods,
            "resources": resources, "corridors": corridors,
            "windows": windows, "invalid": total_invalid,
            "duplicate": total_dup, "journal_mode": jm
        }
    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reset RailBlock AI demo DB")
    parser.add_argument("--force", action="store_true", help="Force reset even if DB locked")
    args = parser.parse_args()
    reset(force=args.force)
