"""Vercel SQLite fallback auto seeding — ensures all features workable without external DB or manual import. Synthetic prototype data only."""

import json
import logging
import pathlib
import random
import datetime
from typing import Dict, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def is_db_seeded(db: Session) -> bool:
    """Check if DB has at least Task count>0 and CandidateWindow count>0 and Corridor count>0."""
    try:
        from app.models import Task, CandidateWindow, Corridor

        task_cnt = db.query(Task).count()
        window_cnt = db.query(CandidateWindow).count()
        corridor_cnt = db.query(Corridor).count()
        return task_cnt > 0 and window_cnt > 0 and corridor_cnt > 0
    except Exception as e:
        logger.warning(f"is_db_seeded check failed: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        return False


def get_seeding_status(db: Session) -> Dict:
    """Return counts dict with departments, corridors, tasks, trains, goods, resources, windows."""
    try:
        from app.models import DepartmentModel, Corridor, Task, TrainMovement, GoodsForecast, Resource, CandidateWindow

        return {
            "departments": db.query(DepartmentModel).count(),
            "corridors": db.query(Corridor).count(),
            "tasks": db.query(Task).count(),
            "trains": db.query(TrainMovement).count(),
            "goods": db.query(GoodsForecast).count(),
            "resources": db.query(Resource).count(),
            "windows": db.query(CandidateWindow).count(),
        }
    except Exception as e:
        logger.warning(f"get_seeding_status failed: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        return {
            "departments": 0,
            "corridors": 0,
            "tasks": 0,
            "trains": 0,
            "goods": 0,
            "resources": 0,
            "windows": 0,
        }


def _seed_departments(db: Session):
    """Seed 7 departments if empty — idempotent."""
    try:
        from app.models import DepartmentModel

        if db.query(DepartmentModel).count() == 0:
            for d in ["CONTROL_OFFICE", "ENGINEERING", "S_AND_T", "TRACTION", "PROJECTS", "VIEWER", "ADMIN"]:
                db.add(DepartmentModel(id=d, name=d))
            db.commit()
            logger.info("Seeded 7 departments")
        else:
            logger.debug("Departments already seeded, skip")
    except Exception as e:
        logger.warning(f"_seed_departments failed: {e}")
        try:
            db.rollback()
        except Exception:
            pass


def _seed_infrastructure(db: Session):
    """Seed 3 corridors, 6 sections, 8 lines, 12 assets, 14 resources if Corridor empty (same data as backend/app/main.py:46-104)."""
    try:
        from app.models import Corridor, Section, Line, Asset, Resource

        if db.query(Corridor).count() != 0:
            logger.debug("Corridors already seeded, skip infrastructure")
            return

        # Corridors
        db.add(Corridor(id="COR-1", name="Delhi-Howrah Corridor"))
        db.add(Corridor(id="COR-2", name="Mumbai-Chennai Corridor"))
        db.add(Corridor(id="COR-3", name="Howrah-Chennai Corridor"))
        db.commit()

        # Sections
        db.add(Section(id="SEC-1", corridor_id="COR-1", name="Ghaziabad - Tundla", from_km=0, to_km=120))
        db.add(Section(id="SEC-2", corridor_id="COR-1", name="Tundla - Kanpur", from_km=120, to_km=320))
        db.add(Section(id="SEC-3", corridor_id="COR-2", name="Kalyan - Pune", from_km=0, to_km=150))
        db.add(Section(id="SEC-4", corridor_id="COR-2", name="Pune - Solapur", from_km=150, to_km=350))
        db.add(Section(id="SEC-5", corridor_id="COR-3", name="Vijayawada - Chennai", from_km=0, to_km=400))
        db.add(Section(id="SEC-6", corridor_id="COR-3", name="Kharagpur - Bhubaneswar", from_km=400, to_km=700))
        db.commit()

        # Lines
        db.add(Line(id="LIN-1", section_id="SEC-1", corridor_id="COR-1", line_type="UP", name="UP Line Sec-1"))
        db.add(Line(id="LIN-2", section_id="SEC-1", corridor_id="COR-1", line_type="DOWN", name="DOWN Line Sec-1"))
        db.add(Line(id="LIN-3", section_id="SEC-2", corridor_id="COR-1", line_type="UP", name="UP Line Sec-2"))
        db.add(Line(id="LIN-4", section_id="SEC-2", corridor_id="COR-1", line_type="DOWN", name="DOWN Line Sec-2"))
        db.add(Line(id="LIN-5", section_id="SEC-3", corridor_id="COR-2", line_type="SINGLE", name="Single Line Sec-3"))
        db.add(Line(id="LIN-6", section_id="SEC-4", corridor_id="COR-2", line_type="LOOP", name="Loop Line Sec-4"))
        db.add(Line(id="LIN-7", section_id="SEC-5", corridor_id="COR-3", line_type="UP", name="UP Line Sec-5"))
        db.add(Line(id="LIN-8", section_id="SEC-6", corridor_id="COR-3", line_type="DOWN", name="DOWN Line Sec-6"))
        db.commit()

        # Assets
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

        # Resources
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
        logger.info("Seeded corridors/sections/lines/assets/resources")
    except Exception as e:
        logger.warning(f"_seed_infrastructure failed: {e}")
        try:
            db.rollback()
        except Exception:
            pass


def _seed_rule_configuration(db: Session):
    """Seed RuleConfiguration if empty."""
    try:
        from app.models import RuleConfiguration

        if db.query(RuleConfiguration).count() == 0:
            db.add(
                RuleConfiguration(
                    id="RULE-1",
                    version="v1",
                    priority_weights=json.dumps({"S": 0.30, "U": 0.20, "C": 0.20, "O": 0.15, "D": 0.10, "R": 0.05}),
                    optimizer_weights=json.dumps({"priority": 1.0}),
                    hard_constraints=json.dumps(["train conflict", "resource overlap"]),
                    ai_model=json.dumps({"explainable": True}),
                )
            )
            db.commit()
            logger.info("Seeded RuleConfiguration")
    except Exception as e:
        logger.warning(f"_seed_rule_configuration failed: {e}")
        try:
            db.rollback()
        except Exception:
            pass


def _fallback_programmatic_generation(db: Session):
    """Fallback when no CSV found: replicate data/generate_synthetic_full.py logic inline (seed 42)."""
    try:
        from app.models import Task, TrainMovement, GoodsForecast, ResourceAvailability, Resource, Corridor
        from app.models import task_resources as task_resources_table
        # Ensure infrastructure exists already; if not, _seed_infrastructure should have run
        # Check if we already have enough data
        task_cnt = db.query(Task).count()
        train_cnt = db.query(TrainMovement).count()
        goods_cnt = db.query(GoodsForecast).count()

        # Only generate if empty or below thresholds
        need_tasks = task_cnt < 30
        need_trains = train_cnt < 133
        need_goods = goods_cnt < 43

        if not (need_tasks or need_trains or need_goods):
            logger.debug("Fallback not needed: counts sufficient")
            return

        logger.warning("No CSV bundling found — using programmatic fallback generation (seed 42)")

        # Constants same as generate_synthetic_full.py
        corridors = [
            ("COR-1", "Delhi-Howrah", "Main freight+passenger"),
            ("COR-2", "Mumbai-Chennai", "Coastal heavy"),
            ("COR-3", "Howrah-Chennai", "East Coast"),
        ]
        sections = [
            ("SEC-1", "COR-1", "Ghaziabad - Tundla", 0, 120),
            ("SEC-2", "COR-1", "Tundla - Kanpur", 120, 320),
            ("SEC-3", "COR-2", "Kalyan - Pune", 0, 150),
            ("SEC-4", "COR-2", "Pune - Solapur", 150, 350),
            ("SEC-5", "COR-3", "Vijayawada - Chennai", 0, 400),
            ("SEC-6", "COR-3", "Kharagpur - Bhubaneswar", 400, 700),
        ]
        lines = [
            ("LIN-1", "SEC-1", "COR-1", "UP", "UP Line Sec-1"),
            ("LIN-2", "SEC-1", "COR-1", "DOWN", "DOWN Line Sec-1"),
            ("LIN-3", "SEC-2", "COR-1", "UP", "UP Line Sec-2"),
            ("LIN-4", "SEC-2", "COR-1", "DOWN", "DOWN Line Sec-2"),
            ("LIN-5", "SEC-3", "COR-2", "SINGLE", "Single Line Sec-3"),
            ("LIN-6", "SEC-4", "COR-2", "LOOP", "Loop Line Sec-4"),
            ("LIN-7", "SEC-5", "COR-3", "UP", "UP Line Sec-5"),
            ("LIN-8", "SEC-6", "COR-3", "DOWN", "DOWN Line Sec-6"),
        ]
        assets = [
            ("AST-1", "COR-1", "SEC-1", "LIN-1", "TRACK", 92, 15.0),
            ("AST-2", "COR-1", "SEC-1", "LIN-2", "OHE", 88, 22.5),
            ("AST-3", "COR-1", "SEC-2", "LIN-3", "SIGNAL", 85, 145.0),
            ("AST-4", "COR-1", "SEC-2", "LIN-4", "TRACK", 78, 180.0),
            ("AST-5", "COR-2", "SEC-3", "LIN-5", "TRACK", 75, 45.0),
            ("AST-6", "COR-2", "SEC-3", "LIN-5", "BRIDGE", 90, 60.0),
            ("AST-7", "COR-2", "SEC-4", "LIN-6", "OHE", 82, 200.0),
            ("AST-8", "COR-2", "SEC-4", "LIN-6", "SIGNAL", 80, 220.0),
            ("AST-9", "COR-3", "SEC-5", "LIN-7", "TRACK", 70, 100.0),
            ("AST-10", "COR-3", "SEC-5", "LIN-7", "OHE", 77, 150.0),
            ("AST-11", "COR-3", "SEC-6", "LIN-8", "TRACK", 84, 500.0),
            ("AST-12", "COR-3", "SEC-6", "LIN-8", "SIGNAL", 86, 550.0),
        ]
        resources = [
            ("RES-1", "CREW", "Track Gang A", "ENGINEERING", 2),
            ("RES-2", "CREW", "Track Gang B", "ENGINEERING", 2),
            ("RES-3", "MACHINE", "Tamping Machine M1", "ENGINEERING", 1),
            ("RES-4", "MACHINE", "Welding Plant W1", "ENGINEERING", 1),
            ("RES-5", "MATERIAL", "Ballast Stock", "ENGINEERING", 10),
            ("RES-6", "CREW", "Signal Team S1", "S_AND_T", 2),
            ("RES-7", "CREW", "Signal Team S2", "S_AND_T", 2),
            ("RES-8", "MACHINE", "Signal Test Van", "S_AND_T", 1),
            ("RES-9", "CREW", "OHE Crew O1", "TRACTION", 2),
            ("RES-10", "CREW", "OHE Crew O2", "TRACTION", 2),
            ("RES-11", "MACHINE", "Tower Wagon", "TRACTION", 1),
            ("RES-12", "CREW", "Project Team P1", "PROJECTS", 3),
            ("RES-13", "MACHINE", "Crane 100T", "PROJECTS", 1),
            ("RES-14", "CREW", "Control Office", "CONTROL_OFFICE", 5),
        ]

        random.seed(42)
        start_date = datetime.datetime(2026, 9, 1)
        dates = [(start_date + datetime.timedelta(days=i)).strftime("%Y-%m-%d") for i in range(30)]

        # --- Tasks ---
        if need_tasks:
            departments = ["ENGINEERING", "S_AND_T", "TRACTION", "PROJECTS"]
            task_types = {
                "ENGINEERING": ["TRACK_RENEWAL", "BALLAST_CLEANING", "TRACK_INSPECTION", "BRIDGE_MAINT"],
                "S_AND_T": ["SIGNAL_TEST", "POINT_MAINT", "CABLE_CHECK", "INTERLOCKING"],
                "TRACTION": ["OHE_INSPECTION", "OHE_RENEWAL", "POWER_ISOLATION", "TROLLEY_CHECK"],
                "PROJECTS": ["DOUBLING_WORK", "THIRD_LINE", "ROB_CONSTRUCTION", "YARD_REMODEL"],
            }
            severities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
            task_defs = []
            for i in range(1, 31):
                tid = f"TSK-{i:03d}"
                dept = departments[(i - 1) % len(departments)]
                asset = assets[(i - 1) % len(assets)]
                aid, cor, sec, lin, atype, crit, km = asset
                if i % 5 == 0:
                    cor, sec, lin, aid = "COR-1", "SEC-1", "LIN-1", "AST-1"
                elif i % 7 == 0:
                    cor, sec, lin, aid = "COR-1", "SEC-1", "LIN-2", "AST-2"
                ttype = random.choice(task_types[dept])
                sev = random.choice(severities)
                safety = random.randint(30, 95)
                urgency = random.randint(20, 90)
                acrit = crit
                op_impact = random.randint(30, 90)
                overdue = random.choice([0, 0, 0, 2, 5, 12, 20])
                coord = random.randint(30, 80)
                readiness = random.randint(50, 95)
                est = random.choice([30, 45, 60, 90, 120, 180])
                setup = random.choice([10, 15, 20, 30])
                block_type = "TRAFFIC"
                requires_traffic = True
                requires_power = True if dept == "TRACTION" and i % 2 == 0 else False
                requires_signal = True if dept == "S_AND_T" and i % 3 == 0 else False
                earliest = (start_date + datetime.timedelta(days=random.randint(0, 2))).strftime("%Y-%m-%d")
                deadline = (start_date + datetime.timedelta(days=random.randint(7, 28))).strftime("%Y-%m-%d")
                dep = ""
                if i in [4, 8, 12, 16, 20]:
                    dep = f"TSK-{i-1:03d}"
                if i == 15:
                    dep = "TSK-001;TSK-002"
                dept_res = [r[0] for r in resources if r[3] == dept]
                req_res = ";".join(random.sample(dept_res, k=random.randint(1, 2))) if dept_res else ""
                if i % 6 == 0:
                    req_res = "RES-1"
                task_defs.append([tid, cor, sec, lin, aid, ttype, f"{ttype} at {sec} KM {km} {sev}", sev, safety, urgency, acrit, op_impact, overdue, coord, readiness, est, setup, block_type, requires_traffic, requires_power, requires_signal, earliest, deadline, dep, req_res, dept])

            # Post-process dependencies to ensure earliest_start ordering and deadline feasibility
            task_map = {row[0]: row for row in task_defs}
            for row in task_defs:
                dep_str = row[23]
                if dep_str:
                    deps = [d.strip() for d in dep_str.split(";") if d.strip()]
                    max_earliest = None
                    for d in deps:
                        if d in task_map:
                            dep_earliest = datetime.datetime.strptime(task_map[d][21], "%Y-%m-%d")
                            if max_earliest is None or dep_earliest > max_earliest:
                                max_earliest = dep_earliest
                    if max_earliest:
                        new_earliest = max_earliest + datetime.timedelta(days=1)
                        cur_earliest = datetime.datetime.strptime(row[21], "%Y-%m-%d")
                        if new_earliest > cur_earliest:
                            row[21] = new_earliest.strftime("%Y-%m-%d")
                            cur_deadline = datetime.datetime.strptime(row[22], "%Y-%m-%d")
                            if cur_deadline <= new_earliest:
                                row[22] = (new_earliest + datetime.timedelta(days=7)).strftime("%Y-%m-%d")

            # Insert tasks via ORM
            from sqlalchemy import text as _text

            # Resolve imported table for task_resources
            try:
                from app.models import task_resources as _tr_table
            except Exception:
                from app.database import Base as _Base

                _tr_table = _Base.metadata.tables.get("task_resources")

            for row in task_defs:
                tid, cor, sec, lin, aid, ttype, desc, sev, safety, urgency, acrit, op_impact, overdue, coord, readiness, est, setup, block_type, requires_traffic, requires_power, requires_signal, earliest, deadline, dep, req_res, dept = row
                # Idempotency: skip if exists
                if db.query(Task).filter(Task.id == tid).first():
                    continue
                # Ensure asset/corridor existence already handled
                try:
                    earliest_dt = datetime.datetime.strptime(earliest, "%Y-%m-%d")
                except Exception:
                    earliest_dt = None
                try:
                    deadline_dt = datetime.datetime.strptime(deadline, "%Y-%m-%d")
                except Exception:
                    deadline_dt = None

                t = Task(
                    id=tid,
                    source_system="TMS",
                    department=dept,
                    asset_id=aid,
                    corridor_id=cor,
                    section_id=sec,
                    line_id=lin,
                    location_from_km=0,
                    location_to_km=0,
                    task_type=ttype,
                    description=desc,
                    severity=sev,
                    safety_score=float(safety),
                    urgency_score=float(urgency),
                    asset_criticality=float(acrit),
                    operational_impact=float(op_impact),
                    overdue_days=int(overdue),
                    coordination_value=float(coord),
                    resource_readiness=float(readiness),
                    estimated_duration_minutes=int(est),
                    setup_duration_minutes=int(setup),
                    required_block_type=block_type,
                    requires_traffic_block=bool(requires_traffic),
                    requires_power_isolation=bool(requires_power),
                    requires_signal_disconnection=bool(requires_signal),
                    earliest_start=earliest_dt,
                    deadline=deadline_dt,
                    status="ELIGIBLE",
                    priority_score=0,
                    priority_rank=0,
                    priority_reason="",
                    priority_breakdown="{}",
                    rule_configuration_version="v1",
                    source_maturity="SYNTHETIC",
                )
                db.add(t)
                try:
                    db.flush()
                except Exception as fe:
                    logger.warning(f"Task {tid} flush failed: {fe}")
                    try:
                        db.rollback()
                    except Exception:
                        pass
                    continue

                # Dependencies
                if dep:
                    for did in [d.strip().upper() for d in dep.split(";") if d.strip()]:
                        try:
                            from app.models import TaskDependency

                            # Only add if depends_on exists (already inserted earlier in loop order ensures earlier tasks exist)
                            # Use savepoint
                            with db.begin_nested():
                                db.add(TaskDependency(task_id=tid, depends_on_task_id=did))
                                db.flush()
                        except Exception:
                            try:
                                db.rollback()
                            except Exception:
                                pass
                            continue

                # Resources
                if req_res:
                    for rid in [r.strip().upper() for r in req_res.split(";") if r.strip()]:
                        try:
                            with db.begin_nested():
                                if _tr_table is not None:
                                    db.execute(_tr_table.insert().values(task_id=tid, resource_id=rid))
                                    db.flush()
                        except Exception:
                            try:
                                db.rollback()
                            except Exception:
                                pass
                            continue
            db.commit()
            logger.info(f"Fallback generated {db.query(Task).count()} tasks")

            # Also ensure ResourceAvailability for fallback (at least 7 days per resource)
            try:
                if db.query(ResourceAvailability).count() == 0:
                    for rid, rtype, name, dept, cap in resources:
                        for d in dates[:7]:
                            db.add(
                                ResourceAvailability(
                                    resource_id=rid,
                                    service_date=d,
                                    start_time=0,
                                    end_time=1439,
                                    available=True,
                                )
                            )
                    db.commit()
                    logger.info("Fallback generated ResourceAvailability")
            except Exception as e2:
                logger.warning(f"Fallback ResourceAvailability failed: {e2}")
                try:
                    db.rollback()
                except Exception:
                    pass

        # --- Trains (133) ---
        if need_trains:
            # parse helper
            def _tp(s: str) -> int:
                try:
                    h, m = s.split(":")
                    return int(h) * 60 + int(m)
                except Exception:
                    return 0

            tid = 1
            # Get existing max to continue idempotent (if partial)
            existing_ids = set(r[0] for r in db.query(TrainMovement.id).all())
            for d in dates[:14]:
                for cor in ["COR-1", "COR-2", "COR-3"]:
                    sec = "SEC-1" if cor == "COR-1" else "SEC-3" if cor == "COR-2" else "SEC-5"
                    lin = "LIN-1" if cor == "COR-1" else "LIN-5" if cor == "COR-2" else "LIN-7"
                    batch = []
                    batch.append((f"TRN-{tid:04d}", cor, sec, lin, "PASSENGER", d, "06:00", "06:30", 15, 15))
                    tid += 1
                    batch.append((f"TRN-{tid:04d}", cor, sec, lin, "PASSENGER", d, "08:30", "09:00", 15, 15))
                    tid += 1
                    batch.append((f"TRN-{tid:04d}", cor, sec, lin, "GOODS", d, "10:00", "10:45", 10, 10))
                    tid += 1
                    if d in ["2026-09-02", "2026-09-05"]:
                        batch.append((f"TRN-{tid:04d}", cor, sec, lin, "PASSENGER", d, "01:30", "02:00", 15, 15))
                        tid += 1
                    if d == "2026-09-03" and cor == "COR-1":
                        batch.append((f"TRN-{tid:04d}", "COR-1", "SEC-1", "LIN-1", "PASSENGER", d, "13:45", "14:30", 15, 15))
                        tid += 1
                    for trn_id, c, s, l, ttype, service_date, dep, arr, bb, ba in batch:
                        if trn_id in existing_ids:
                            continue
                        if db.query(TrainMovement).filter(TrainMovement.id == trn_id).first():
                            continue
                        try:
                            db.add(
                                TrainMovement(
                                    id=trn_id,
                                    corridor_id=c,
                                    section_id=s,
                                    line_id=l,
                                    train_type=ttype,
                                    service_date=service_date,
                                    departure_time=_tp(dep),
                                    arrival_time=_tp(arr),
                                    buffer_before=bb,
                                    buffer_after=ba,
                                    source_maturity="SYNTHETIC",
                                )
                            )
                        except Exception as e:
                            logger.warning(f"Train {trn_id} add failed: {e}")
                            try:
                                db.rollback()
                            except Exception:
                                pass
            try:
                db.commit()
            except Exception as e:
                logger.warning(f"Train commit failed: {e}")
                try:
                    db.rollback()
                except Exception:
                    pass
            logger.info(f"Fallback generated {db.query(TrainMovement).count()} trains")

        # --- Goods (43) ---
        if need_goods:
            def _tp2(s: str) -> int:
                try:
                    h, m = s.split(":")
                    return int(h) * 60 + int(m)
                except Exception:
                    return 0

            g_counter = db.query(GoodsForecast).count() + 1
            existing_goods = set(
                f"{r.corridor_id}|{r.service_date}|{r.start_time}" for r in db.query(GoodsForecast.corridor_id, GoodsForecast.service_date, GoodsForecast.start_time).all()
            )
            # random already seeded; re-seed for goods to match original generation sequence
            # Need to replay train generation did not use random, so seed still 42 progression should match.
            # For deterministic, we reset random sequence and replay task generation random consumption? Simpler: reset seed and skip task draws.
            # Instead, replicate goods generation directly with same random choices as original after task generation.
            # Original goods generation used random.choice after tasks; our current random state after task generation is at same point (since we replayed exactly same task generation). So continue.
            for d in dates[:14]:
                for cor, sec, lin in [("COR-1", "SEC-1", "LIN-1"), ("COR-2", "SEC-3", "LIN-5"), ("COR-3", "SEC-5", "LIN-7")]:
                    conf = random.choice([0.3, 0.4, 0.6, 0.85])
                    forecast_count = random.randint(1, 4)
                    risk = int(conf * 100)
                    key = f"{cor}|{d}|{_tp2('02:00')}"
                    # Need composite per lin as well? Original had lin in uniqueness but ingestion uses corridor|date|start_time without lin for duplicate check, fallback we mimic same
                    # Use id deterministic
                    gid = f"GDF-{g_counter:04d}"
                    g_counter += 1
                    comp_key = f"{cor}|{d}|{_tp2('02:00')}"
                    # Check duplicate per (corridor, date, start_time) — but there are 3 corridors each date, so they are distinct by corridor
                    if comp_key in existing_goods:
                        # Need to ensure we don't duplicate exactly same corridor/date/time even if lin differs — but original had 3 per date distinct corridor, so each is unique
                        # So we check if this exact corridor/date/start exists already by querying
                        if db.query(GoodsForecast).filter(GoodsForecast.corridor_id == cor, GoodsForecast.service_date == d, GoodsForecast.start_time == _tp2("02:00")).first():
                            # skip duplicate
                            continue
                    try:
                        db.add(
                            GoodsForecast(
                                id=gid,
                                corridor_id=cor,
                                section_id=sec,
                                line_id=lin,
                                service_date=d,
                                start_time=_tp2("02:00"),
                                end_time=_tp2("04:00"),
                                confidence=float(conf),
                                forecast_count=int(forecast_count),
                                risk_score=float(risk),
                                source_maturity="SYNTHETIC",
                            )
                        )
                        existing_goods.add(comp_key)
                    except Exception as e:
                        logger.warning(f"Goods {gid} add failed: {e}")
                        try:
                            db.rollback()
                        except Exception:
                            pass
                    if cor == "COR-1" and d == "2026-09-02":
                        gid2 = f"GDF-{g_counter:04d}"
                        g_counter += 1
                        comp_key2 = f"{cor}|{d}|{_tp2('13:30')}"
                        if db.query(GoodsForecast).filter(GoodsForecast.corridor_id == cor, GoodsForecast.service_date == d, GoodsForecast.start_time == _tp2("13:30")).first():
                            continue
                        try:
                            db.add(
                                GoodsForecast(
                                    id=gid2,
                                    corridor_id=cor,
                                    section_id=sec,
                                    line_id=lin,
                                    service_date=d,
                                    start_time=_tp2("13:30"),
                                    end_time=_tp2("15:30"),
                                    confidence=0.9,
                                    forecast_count=3,
                                    risk_score=90,
                                    source_maturity="SYNTHETIC",
                                )
                            )
                            existing_goods.add(comp_key2)
                        except Exception as e:
                            logger.warning(f"Goods {gid2} add failed: {e}")
                            try:
                                db.rollback()
                            except Exception:
                                pass
            try:
                db.commit()
            except Exception as e:
                logger.warning(f"Goods commit failed: {e}")
                try:
                    db.rollback()
                except Exception:
                    pass
            logger.info(f"Fallback generated {db.query(GoodsForecast).count()} goods")

        # Final ensure at least minimums: if still below, inject minimal placeholders
        try:
            if db.query(Task).count() < 30:
                logger.warning(f"Tasks still {db.query(Task).count()} <30 after fallback — minimal placeholder")
            if db.query(TrainMovement).count() < 133:
                logger.warning(f"Trains still {db.query(TrainMovement).count()} <133 after fallback")
            if db.query(GoodsForecast).count() < 43:
                logger.warning(f"Goods still {db.query(GoodsForecast).count()} <43 after fallback")
        except Exception:
            pass

    except Exception as e:
        logger.warning(f"_fallback_programmatic_generation failed: {e}")
        try:
            db.rollback()
        except Exception:
            pass


def ensure_synthetic_seeded(db: Optional[Session] = None) -> Dict:
    """
    Idempotent auto-seeding that makes all features workable.
    Steps:
      1. Call init_db() if needed (create_all)
      2. Seed 7 departments if empty
      3. Seed 3 corridors, 6 sections, 8 lines, 12 assets, 14 resources if Corridor empty (same data as backend/app/main.py:46-104)
      4. Seed RuleConfiguration if empty
      5. Try to ingest synthetic CSVs from multiple candidate directories, fallback to programmatic generation if none found
      6. Call recalculate_all(db) from app.services.priority
      7. Generate candidate windows via generate_candidate_windows(db, "2026-09-01","2026-09-07") if CandidateWindow empty, and also "2026-09-01" to "2026-09-30" for monthly
      8. Return status dict
    """
    owns_session = False
    if db is None:
        try:
            from app.database import SessionLocal

            db = SessionLocal()
            owns_session = True
        except Exception as e:
            logger.warning(f"ensure_synthetic_seeded: SessionLocal failed: {e}")
            return {"error": str(e), "departments": 0, "corridors": 0, "tasks": 0, "trains": 0, "goods": 0, "resources": 0, "windows": 0, "is_seeded": False}

    try:
        # 1. init_db (create_all)
        try:
            from app.database import init_db

            init_db()
        except Exception as e:
            logger.warning(f"init_db failed in seeder: {e}")
            try:
                db.rollback()
            except Exception:
                pass

        # 2. Seed departments
        _seed_departments(db)

        # 3. Seed infrastructure
        _seed_infrastructure(db)

        # 4. Seed RuleConfiguration
        _seed_rule_configuration(db)

        # 5. Try CSV ingestion from multiple candidates, else fallback
        csv_found = False
        candidate_dirs = []
        try:
            candidate_dirs = [
                pathlib.Path(__file__).resolve().parents[3] / "data" / "sample",
                pathlib.Path(__file__).resolve().parents[2] / "data" / "sample",
                pathlib.Path("/var/task/data/sample"),
                pathlib.Path("/tmp/data/sample"),
                pathlib.Path.cwd() / "data" / "sample",
            ]
        except Exception as e:
            logger.warning(f"Candidate dirs resolution failed: {e}")

        # Also try importlib.resources if needed
        importlib_dirs = []
        try:
            import importlib.resources as _ir  # type: ignore

            for pkg_candidate in ["data.sample", "backend.data.sample", "app.data.sample"]:
                try:
                    # Python 3.9+: files()
                    if hasattr(_ir, "files"):
                        p = _ir.files(pkg_candidate)  # type: ignore[attr-defined]
                        # Convert Traversable to path if possible
                        try:
                            # p may be Traversable; try to check existence
                            if p.is_dir():  # type: ignore
                                # Attempt to use as path if it's file system
                                try:
                                    as_path = pathlib.Path(str(p))
                                    if as_path.exists():
                                        importlib_dirs.append(as_path)
                                except Exception:
                                    pass
                        except Exception:
                            pass
                except Exception:
                    continue
            # Also try files for 'data' package itself
            try:
                if hasattr(_ir, "files"):
                    for pkg2 in ["data"]:
                        try:
                            p2 = _ir.files(pkg2)  # type: ignore
                            cand = pathlib.Path(str(p2)) / "sample"
                            if cand.exists():
                                importlib_dirs.append(cand)
                        except Exception:
                            continue
            except Exception:
                pass
        except Exception as e:
            logger.debug(f"importlib.resources probing failed: {e}")

        all_candidate_dirs = candidate_dirs + importlib_dirs

        # Find first dir that has at least one CSV
        sample_dir = None
        max_found_dir = None
        max_found_count = -1
        for cand in all_candidate_dirs:
            try:
                if not cand.exists() or not cand.is_dir():
                    continue
                found = 0
                for fname in ["corridors.csv", "resources.csv", "trains.csv", "goods_forecast.csv", "tasks.csv"]:
                    if (cand / fname).exists():
                        found += 1
                if found > max_found_count:
                    max_found_count = found
                    max_found_dir = cand
                if found > 0 and sample_dir is None:
                    sample_dir = cand
            except Exception as e:
                logger.debug(f"Candidate dir check {cand} failed: {e}")
                continue
        # Prefer dir with most files
        if max_found_dir is not None and max_found_count > 0:
            sample_dir = max_found_dir

        ingestion_candidates = [
            ("corridors.csv", "COA"),
            ("resources.csv", "RESOURCES"),
            ("trains.csv", "TIMETABLE"),
            ("goods_forecast.csv", "GOODS_FORECAST"),
            ("tasks.csv", "TMS"),
        ]

        if sample_dir is not None and sample_dir.exists():
            logger.info(f"Trying synthetic CSV ingestion from {sample_dir}")
            # Lazy import to avoid circular deps
            try:
                from app.services.ingestion import run_import

                found_any = False
                for fname, source in ingestion_candidates:
                    p = sample_dir / fname
                    if p.exists():
                        found_any = True
                        try:
                            content = p.read_text(encoding="utf-8")
                            # Use same db; run_import commits internally
                            res = run_import(db, source, content, user_id="auto_synthetic")
                            logger.info(f"Auto ingest {source} {fname}: received={res.get('received_count')} accepted={res.get('accepted_count')} duplicate={res.get('duplicate_count')} rejected={res.get('rejected_count')}")
                            csv_found = True
                        except Exception as e:
                            logger.warning(f"CSV ingest {fname} -> {source} failed: {e}")
                            try:
                                db.rollback()
                            except Exception:
                                pass
                    else:
                        logger.debug(f"CSV not found: {p}")
                if not found_any:
                    logger.warning(f"No CSV files found in {sample_dir}, will fallback")
                else:
                    # Refresh
                    try:
                        db.expire_all()
                    except Exception:
                        pass
            except Exception as e:
                logger.warning(f"run_import import or execution failed: {e}")
                try:
                    db.rollback()
                except Exception:
                    pass
        else:
            logger.warning(f"No sample_dir found among candidates {[str(c) for c in all_candidate_dirs]}, will fallback if needed")

        # If no CSV found at all (Vercel bundling missing), fallback to programmatic generation
        if not csv_found:
            # Check if we still need data (maybe CSV missing but fallback already seeded previously)
            try:
                from app.models import Task as _Task2

                if db.query(_Task2).count() == 0:
                    logger.warning("No CSV ingest succeeded and Task empty — invoking fallback programmatic generation")
                    _fallback_programmatic_generation(db)
                else:
                    # Even if tasks exist but trains/goods missing, ensure fallback for those
                    from app.models import TrainMovement as _Tr, GoodsForecast as _Gf

                    if db.query(_Tr).count() < 10 or db.query(_Gf).count() < 5:
                        logger.warning("Partial data after CSV attempt — invoking fallback for trains/goods")
                        _fallback_programmatic_generation(db)
                    else:
                        logger.debug("CSV not found but DB already has data, skipping fallback")
            except Exception as e:
                logger.warning(f"Fallback check failed: {e}")
                try:
                    _fallback_programmatic_generation(db)
                except Exception as e2:
                    logger.warning(f"Emergency fallback also failed: {e2}")

        # 6. Recalculate priorities
        try:
            from app.services.priority import recalculate_all

            recalculate_all(db)
            logger.debug("Recalculated priorities")
        except Exception as e:
            logger.warning(f"recalculate_all failed: {e}")
            try:
                db.rollback()
            except Exception:
                pass

        # 7. Generate candidate windows
        try:
            from app.models import CandidateWindow
            from app.services.candidate_windows import generate_candidate_windows

            # If no windows at all, generate weekly then monthly (monthly covers weekly)
            if db.query(CandidateWindow).count() == 0:
                try:
                    generate_candidate_windows(db, "2026-09-01", "2026-09-07")
                    logger.info("Generated weekly windows 2026-09-01 to 2026-09-07")
                except Exception as e:
                    logger.warning(f"Weekly window generation failed: {e}")
                    try:
                        db.rollback()
                    except Exception:
                        pass
                try:
                    generate_candidate_windows(db, "2026-09-01", "2026-09-30")
                    logger.info("Generated monthly windows 2026-09-01 to 2026-09-30")
                except Exception as e:
                    logger.warning(f"Monthly window generation failed: {e}")
                    try:
                        db.rollback()
                    except Exception:
                        pass
            else:
                # Ensure monthly horizon also covered (idempotent; adds missing days)
                # Check if we have windows for entire month; if not, generate monthly to fill gaps
                try:
                    # Count windows for month; if less than expected (~ monthly windows > weekly), ensure generation
                    month_cnt = db.query(CandidateWindow).filter(CandidateWindow.service_date.between("2026-09-01", "2026-09-30")).count()
                    # Heuristic: weekly should be at least 1 window per section/line per day * 7 days; monthly > weekly
                    # Simpler: always call monthly generation idempotently to ensure coverage — safe due to existing_map check
                    generate_candidate_windows(db, "2026-09-01", "2026-09-30")
                    logger.debug(f"Ensured monthly windows, count now {db.query(CandidateWindow).count()}")
                except Exception as e:
                    logger.warning(f"Monthly window ensure failed: {e}")
                    try:
                        db.rollback()
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"generate_candidate_windows import or execution failed: {e}")
            try:
                db.rollback()
            except Exception:
                pass

        # 8. Return status dict
        status = get_seeding_status(db)
        # Add convenience flag
        try:
            status["is_seeded"] = is_db_seeded(db)
            status["seeded"] = status["is_seeded"]
        except Exception:
            status["is_seeded"] = False
            status["seeded"] = False
        return status

    except Exception as e:
        logger.warning(f"ensure_synthetic_seeded overall failed: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        # Try to return whatever status we can
        try:
            status = get_seeding_status(db)
            status["is_seeded"] = False
            status["seeded"] = False
            status["error"] = str(e)
            return status
        except Exception:
            return {"departments": 0, "corridors": 0, "tasks": 0, "trains": 0, "goods": 0, "resources": 0, "windows": 0, "is_seeded": False, "seeded": False, "error": str(e)}
    finally:
        if owns_session:
            try:
                db.close()
            except Exception:
                pass
