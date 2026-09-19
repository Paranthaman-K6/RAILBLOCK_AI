r"""RailBlock AI - Enriched synthetic seeder for MySQL (manual one-time).

Adds ~70 additional tasks, ~200 trains, ~50 goods forecasts to existing demo data
so that the Docker deployment is visibly richer before hosting.

Usage:
  DATABASE_URL=mysql://avnadmin:...@mysql-...aivencloud.com:17468/defaultdb?ssl-mode=REQUIRED \
  DATABASE_MODE=mysql python scripts/seed_enriched.py

Safe to run multiple times — idempotent via ID checks. Run ONCE manually before hosting.
"""
import sys, pathlib, os, random, datetime
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "backend"))
from app.database import SessionLocal, engine, Base, init_db
import app.models
from sqlalchemy import text

# Ensure schema exists first
init_db()
Base.metadata.create_all(bind=engine)

def seed_enriched():
    db = SessionLocal()
    try:
        from app.models import Task, TrainMovement, GoodsForecast, Corridor, Section, Line, Asset, Resource
        # Ensure base infra exists (reset_demo creates these, but guard here)
        corridors = db.query(Corridor).all()
        sections = db.query(Section).all()
        lines = db.query(Line).all()
        assets = db.query(Asset).all()
        resources = db.query(Resource).all()
        if not corridors:
            print("No corridors found — run scripts/reset_demo.py first")
            return

        existing_task_ids = {t.id for t in db.query(Task).all()}
        existing_train_ids = {t.id for t in db.query(TrainMovement).all()}
        existing_goods = {(g.corridor_id, g.service_date, g.start_time) for g in db.query(GoodsForecast).all()}

        # Monet-style deterministic seeded randomness for reproducible demo
        random.seed(20260901)

        task_types = ["TRACK_MAINT", "OHE_MAINT", "SIGNAL_MAINT", "BRIDGE_MAINT", "BALLAST_CLEANING", "POINT_MAINT", "TROLLEY_CHECK", "YARD_REMODEL", "WELDING", "TAMPING", "OVERHAUL", "INSPECTION"]
        departments_by_type = {
            "TRACK_MAINT": "ENGINEERING", "BALLAST_CLEANING": "ENGINEERING", "WELDING": "ENGINEERING", "TAMPING": "ENGINEERING",
            "OHE_MAINT": "TRACTION", "TROLLEY_CHECK": "TRACTION",
            "SIGNAL_MAINT": "S_AND_T", "POINT_MAINT": "S_AND_T", "BRIDGE_MAINT": "S_AND_T",
            "YARD_REMODEL": "PROJECTS", "OVERHAUL": "PROJECTS", "INSPECTION": "ENGINEERING"
        }
        severities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        block_types = ["TRAFFIC", "POWER", "SIGNAL", "INTEGRATED"]

        # 1) Add 70 tasks TSK-031..TSK-100 (if missing)
        new_tasks = []
        for i in range(31, 101):
            tid = f"TSK-{i:03d}"
            if tid in existing_task_ids:
                continue
            sec = random.choice(sections)
            lin_candidates = [l for l in lines if l.section_id == sec.id]
            lin = random.choice(lin_candidates) if lin_candidates else random.choice(lines)
            ast_candidates = [a for a in assets if a.section_id == sec.id]
            ast = random.choice(ast_candidates) if ast_candidates else random.choice(assets)
            ttype = random.choice(task_types)
            dept = departments_by_type.get(ttype, "ENGINEERING")
            sev = random.choices(severities, weights=[1,3,3,2])[0]
            # Dates in September 2026 horizon
            start_offset = random.randint(0, 28)
            start = datetime.date(2026, 9, 1) + datetime.timedelta(days=start_offset)
            end = start + datetime.timedelta(days=random.randint(5, 15))
            duration = random.choice([30, 45, 60, 90, 120, 180])
            task = Task(
                id=tid,
                source_system=random.choice(["TMS","SMMS","TDMS"]),
                department=dept,
                asset_id=ast.id,
                corridor_id=sec.corridor_id,
                section_id=sec.id,
                line_id=lin.id,
                location_from_km=ast.location_km,
                location_to_km=ast.location_km + random.uniform(0.5, 2.0),
                task_type=ttype,
                description=f"{ttype} at {sec.name} KM {ast.location_km:.1f} {sev}",
                severity=sev,
                safety_score=random.randint(30, 95),
                urgency_score=random.randint(30, 95),
                asset_criticality=ast.asset_criticality,
                operational_impact=random.randint(30, 90),
                overdue_days=random.randint(0, 25),
                coordination_value=random.randint(30, 85),
                resource_readiness=random.randint(40, 95),
                estimated_duration_minutes=duration,
                setup_duration_minutes=random.choice([10,15,30]),
                required_block_type=random.choice(block_types),
                requires_traffic_block=True,
                requires_power_isolation=(dept=="TRACTION" or random.random()<0.15),
                requires_signal_disconnection=(dept=="S_AND_T" or random.random()<0.12),
                earliest_start=datetime.datetime.combine(start, datetime.time.min),
                deadline=datetime.datetime.combine(end, datetime.time.min),
                status="ELIGIBLE",
                source_maturity="SYNTHETIC"
            )
            db.add(task)
            new_tasks.append(task)
        if new_tasks:
            db.commit()
            print(f"Added {len(new_tasks)} enriched tasks ({len(existing_task_ids)} existing -> {db.query(Task).count()} total)")
        else:
            print(f"Tasks already enriched ({db.query(Task).count()} total)")

        # Link resources randomly for new tasks via task_resources table
        from app.models import task_resources
        # Build mapping dept -> resources
        res_by_dept = {}
        for r in resources:
            res_by_dept.setdefault(r.department, []).append(r.id)
        # For each new task, assign 1-2 resources from its department
        for t in new_tasks:
            candidates = res_by_dept.get(t.department, [])
            if not candidates:
                continue
            chosen = random.sample(candidates, k=min(len(candidates), random.randint(1,2)))
            for rid in chosen:
                try:
                    db.execute(task_resources.insert().values(task_id=t.id, resource_id=rid))
                except Exception:
                    pass
        if new_tasks:
            db.commit()

        # Recalculate priorities for all tasks
        try:
            from app.services.priority import recalculate_all
            recalculate_all(db)
            print("Recalculated priorities for enriched tasks")
        except Exception as e:
            print(f"Priority recalc failed: {e}")
            db.rollback()

        # 2) Add ~200 extra trains across September horizon (if <300 total)
        train_count_before = db.query(TrainMovement).count()
        target_trains = 350
        to_add = max(0, target_trains - train_count_before)
        if to_add > 0:
            base_time = datetime.date(2026, 9, 1)
            new_trains = []
            for idx in range(to_add):
                seq = train_count_before + idx + 1
                tid = f"TRN-{seq:04d}"
                if tid in existing_train_ids:
                    continue
                sec = random.choice(sections)
                lin_candidates = [l for l in lines if l.section_id == sec.id]
                lin = random.choice(lin_candidates) if lin_candidates else random.choice(lines)
                service_date = (base_time + datetime.timedelta(days=random.randint(0, 29))).isoformat()
                # Random time window 01:00-22:00
                dep = random.randint(60, 22*60)
                arr = dep + random.randint(30, 180)
                if arr > 24*60:
                    arr = 24*60 - 5
                tr = TrainMovement(
                    id=tid,
                    corridor_id=sec.corridor_id,
                    section_id=sec.id,
                    line_id=lin.id,
                    train_type=random.choice(["PASSENGER","GOODS","EXPRESS","FREIGHT"]),
                    service_date=service_date,
                    departure_time=dep,
                    arrival_time=arr,
                    buffer_before=15,
                    buffer_after=15,
                    source_maturity="SYNTHETIC"
                )
                db.add(tr)
                new_trains.append(tr)
            db.commit()
            print(f"Added {len(new_trains)} enriched trains ({train_count_before} -> {db.query(TrainMovement).count()})")
        else:
            print(f"Trains already enriched ({train_count_before} total, target {target_trains})")

        # 3) Add ~50 goods forecasts
        goods_before = db.query(GoodsForecast).count()
        target_goods = 100
        to_add_g = max(0, target_goods - goods_before)
        if to_add_g > 0:
            for idx in range(to_add_g):
                sec = random.choice(sections)
                lin_candidates = [l for l in lines if l.section_id == sec.id]
                lin = random.choice(lin_candidates) if lin_candidates else None
                service_date = (datetime.date(2026,9,1) + datetime.timedelta(days=random.randint(0,29))).isoformat()
                start_t = random.randint(0, 18*60)
                end_t = start_t + random.randint(60, 240)
                key = (sec.corridor_id, service_date, start_t)
                if key in existing_goods:
                    continue
                gf = GoodsForecast(
                    id=f"GF-{goods_before+idx+1:04d}",
                    corridor_id=sec.corridor_id,
                    section_id=sec.id,
                    line_id=lin.id if lin else None,
                    service_date=service_date,
                    start_time=start_t,
                    end_time=min(end_t, 24*60),
                    confidence=round(random.uniform(0.3, 0.95),2),
                    risk_score=round(random.uniform(10, 95),1),
                    forecast_count=random.randint(1,5),
                    source_maturity="SYNTHETIC"
                )
                db.add(gf)
                existing_goods.add(key)
            db.commit()
            print(f"Added {to_add_g} enriched goods forecasts ({goods_before} -> {db.query(GoodsForecast).count()})")
        else:
            print(f"Goods forecasts already enriched ({goods_before} total)")

        # 4) Regenerate candidate windows for full month horizon
        try:
            from app.services.candidate_windows import generate_candidate_windows
            generate_candidate_windows(db, "2026-09-01", "2026-09-30")
            from app.models import CandidateWindow
            print(f"Candidate windows now: {db.query(CandidateWindow).count()}")
        except Exception as e:
            print(f"Window generation failed: {e}")

        print(f"Enriched seeding complete. Final counts: Tasks={db.query(Task).count()} Trains={db.query(TrainMovement).count()} Goods={db.query(GoodsForecast).count()}")

    finally:
        db.close()

if __name__ == "__main__":
    seed_enriched()
