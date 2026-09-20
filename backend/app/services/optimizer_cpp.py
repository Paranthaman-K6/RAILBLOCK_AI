"""
optimizer_cpp.py — Deep module adapter for C++ CP-SAT heavy optimizer.

Interface (small, leverage-full):
    solve(blocks_json, tasks_json, time_limit=5) -> json_str
    run_cpsat_optimizer(db, horizon_start, horizon_end, horizon_type="WEEKLY", time_limit=5)
        -> (plan, status, breakdown, runtime)

Seam: app.services.optimizer  <-->  optimizer_cpp (pybind11)
- Tries to import compiled `optimizer_cpp` (C++ pybind11, 5s 8 workers, ortools/sat/cp_model.h)
- Falls back to pure-Python `app.services.optimizer.run_cpsat_optimizer` without breaking callers.
- Optional deep module: not required for tests or basic deploys.

Depth: callers learn 1-2 functions; complexity (JSON ser, CP-SAT C++ build,
resource/dep constraints, 8-worker solve, graceful degradation) stays hidden.

Locality: changes to solver tuning, cmake flags, or fallback logic live here;
callers unaffected.
"""
import json
import uuid
import datetime
import time
import logging

log = logging.getLogger(__name__)

def _try_load_cpp():
    """Load compiled optimizer_cpp only if it is the C++ extension (has solve), not the directory namespace."""
    try:
        import importlib.util, sys
        import optimizer_cpp as _m  # top-level; backend/optimizer_cpp dir is namespace without solve -> rejected
        if not hasattr(_m, "solve"):
            raise ImportError(f"optimizer_cpp found but no solve attribute (likely directory {getattr(_m, '__file__', 'namespace')}), need compiled .so")
        return _m, True
    except ImportError as e:
        # also probe for .so built next to this file or at backend root via importlib
        import pathlib
        here = pathlib.Path(__file__).parent
        for cand in [here / "optimizer_cpp.so", here / "optimizer_cpp.cpython-311-x86_64-linux-gnu.so", pathlib.Path("/app/optimizer_cpp.so")]:
            if cand.exists():
                try:
                    import importlib.machinery
                    loader = importlib.machinery.ExtensionFileLoader("optimizer_cpp", str(cand))
                    spec = importlib.util.spec_from_loader(loader.name, loader)
                    mod = importlib.util.module_from_spec(spec)
                    loader.exec_module(mod)
                    if hasattr(mod, "solve"):
                        return mod, True
                except Exception:
                    continue
        return None, False

_cpp, HAS_CPP = _try_load_cpp()
_cpp_has_ortools = bool(getattr(_cpp, "has_ortools", False)) if HAS_CPP else False
if HAS_CPP:
    log.info(f"optimizer_cpp C++ loaded (has_ortools={_cpp_has_ortools}, workers={getattr(_cpp, 'workers', 8)})")
else:
    log.info("optimizer_cpp C++ not available, using Python fallback (optional deep module)")


def solve(blocks_json: str, tasks_json: str, time_limit: int = 5) -> str:
    """
    Small interface: JSON in, JSON out.
    Delegates to C++ optimizer_cpp.solve(blocks_json, tasks_json, time_limit) if present,
    else to a pure-Python greedy fallback that preserves the same JSON contract.
    """
    if HAS_CPP and _cpp is not None:
        try:
            # C++ expects (blocks_json, tasks_json, time_limit) -> json string
            # It also supports python objects overload; we use strings for determinism.
            if isinstance(blocks_json, (list, dict)):
                blocks_json = json.dumps(blocks_json)
            if isinstance(tasks_json, (list, dict)):
                tasks_json = json.dumps(tasks_json)
            result = _cpp.solve(blocks_json, tasks_json, int(time_limit))
            # result is JSON string
            if isinstance(result, str):
                return result
            return json.dumps(result)
        except Exception as e:
            log.warning(f"C++ solve failed, falling back to Python: {e}")
            # fall through to python fallback

    # --- Pure-Python fallback (no C++): keep same contract, greedy by net benefit ---
    try:
        blocks = json.loads(blocks_json) if isinstance(blocks_json, str) else blocks_json
        tasks = json.loads(tasks_json) if isinstance(tasks_json, str) else tasks_json
    except Exception as e:
        return json.dumps({"status": "ERROR", "error": f"JSON parse failed: {e}", "assignments": []})

    # greedy fallback mirrors optimizer.cpp non-ORTools path
    from app.services.compatibility import check_task_window_fit

    def _net(t, w):
        pri = (t.get("priority_score") or 50) * 10
        crit = 200 if t.get("priority_band") == "CRITICAL" else 0
        overdue = min(20, (t.get("overdue_days") or 0) * 2) * 10
        asset = (t.get("asset_criticality") or 50) * 0.5
        train = (w.get("goods_risk_score", 0) * 0.2 + w.get("expected_train_count", 0) * 5) * 10
        unused = max(0, w.get("available_minutes", 0) - (t.get("estimated_duration_minutes", 60) + t.get("setup_duration_minutes", 15)))
        return int(pri + crit + overdue + asset - train - unused * 1)

    # normalize tasks/windows to dicts
    pairs = []
    for t in tasks:
        for w in blocks:
            # hard checks via compatibility helper where possible
            # quick corridor/type filter
            if t.get("corridor_id") and w.get("corridor_id") and t["corridor_id"] != w["corridor_id"]:
                continue
            if w.get("status") == "REJECTED":
                continue
            if (t.get("estimated_duration_minutes", 60) + t.get("setup_duration_minutes", 15)) > w.get("available_minutes", 240):
                continue
            if w.get("goods_risk_score", 0) >= 70:
                continue
            pairs.append((t, w, _net(t, w)))
    pairs.sort(key=lambda x: x[2], reverse=True)

    used_w = set()
    used_task = set()
    assignments = []
    date_res_used = {}  # date -> set(resource_ids)
    # build resource map if present
    for t, w, net in pairs:
        tid = t.get("id") or t.get("task_id")
        wid = w.get("id") or w.get("window_id")
        if tid in used_task or wid in used_w:
            continue
        # resource check (if t has resource_ids)
        rids = t.get("resource_ids") or t.get("resources") or []
        if isinstance(rids, str):
            rids = [rids]
        date = w.get("service_date")
        if rids and date:
            used_for_date = date_res_used.setdefault(date, set())
            if any(r in used_for_date for r in rids):
                continue
            used_for_date.update(rids)
        assignments.append({
            "task_id": tid,
            "window_id": wid,
            "corridor_id": w.get("corridor_id"),
            "service_date": date,
            "start_time": w.get("start_time"),
            "end_time": min(w.get("end_time", 0), w.get("start_time", 0) + t.get("estimated_duration_minutes", 60) + t.get("setup_duration_minutes", 15)),
            "block_type": w.get("block_type"),
            "priority_score": t.get("priority_score"),
            "department": t.get("department"),
        })
        used_task.add(tid)
        used_w.add(wid)

    return json.dumps({
        "status": "FEASIBLE" if assignments else "INFEASIBLE",
        "assignments": assignments,
        "objective_value": sum(p[2] for p in pairs if any(a["task_id"] == (p[0].get("id") or p[0].get("task_id")) for a in assignments)),
        "solver": "python-fallback",
        "workers": 1,
        "time_limit": time_limit,
        "note": "C++ not available, used Python greedy fallback",
    })


def run_cpsat_optimizer(db, horizon_start: str, horizon_end: str, horizon_type: str = "WEEKLY", time_limit: int = 5):
    """
    Adapter with same signature as app.services.optimizer.run_cpsat_optimizer.
    Tries C++ path (serialize DB -> JSON -> optimizer_cpp.solve -> deserialize -> persist BlockPlan),
    else delegates to Python optimizer.

    Returns (plan, solver_status, breakdown, runtime) like the Python optimizer.
    """
    if HAS_CPP and _cpp is not None:
        try:
            return _run_cpp(db, horizon_start, horizon_end, horizon_type, time_limit)
        except Exception as e:
            log.warning(f"C++ optimizer path failed ({e}), falling back to Python optimizer")
            # fall through

    # Fallback to Python optimizer (existing deep implementation)
    try:
        from app.services.optimizer import run_cpsat_optimizer as py_run
        return py_run(db, horizon_start, horizon_end, horizon_type, time_limit)
    except Exception as e:
        log.error(f"Python fallback also failed: {e}")
        return None, f"ERROR:{e}", {}, 0


def _run_cpp(db, horizon_start, horizon_end, horizon_type, time_limit):
    from sqlalchemy.orm import Session
    from app.models import Task, CandidateWindow, BlockPlan, Block, BlockTask, TaskDependency
    from app.services.compatibility import check_task_window_fit
    from sqlalchemy import text
    import json as js

    tasks = db.query(Task).filter(Task.status == "ELIGIBLE").all()
    windows = db.query(CandidateWindow).filter(
        CandidateWindow.status == "FEASIBLE",
        CandidateWindow.service_date.between(horizon_start, horizon_end),
    ).all()

    if not tasks or not windows:
        return None, "INFEASIBLE", {}, 0

    # Mirror python optimizer candidate filtering
    from collections import defaultdict

    windows_by_corridor = defaultdict(list)
    for w in windows:
        windows_by_corridor[w.corridor_id].append(w)

    # Serialize for C++: keep fields the C++ parser expects
    tasks_json_list = []
    for t in tasks:
        # resource_ids via task_resources
        try:
            rows = db.execute(text(f"SELECT resource_id FROM task_resources WHERE task_id='{t.id}'")).fetchall()
            rids = [r[0] for r in rows]
        except Exception:
            rids = []
        # deps
        deps = [d.depends_on_task_id for d in db.query(TaskDependency).filter(TaskDependency.task_id == t.id).all()]
        tasks_json_list.append({
            "id": t.id,
            "corridor_id": t.corridor_id,
            "section_id": t.section_id,
            "line_id": t.line_id,
            "priority_score": t.priority_score or 50,
            "priority_band": t.priority_band or "MEDIUM",
            "estimated_duration_minutes": t.estimated_duration_minutes or 60,
            "setup_duration_minutes": t.setup_duration_minutes or 15,
            "required_block_type": t.required_block_type or "TRAFFIC",
            "requires_power_isolation": bool(t.requires_power_isolation),
            "requires_signal_disconnection": bool(t.requires_signal_disconnection),
            "overdue_days": t.overdue_days or 0,
            "asset_criticality": t.asset_criticality or 50,
            "department": t.department,
            "resource_ids": rids,
            "earliest_start": t.earliest_start.strftime("%Y-%m-%d") if hasattr(t.earliest_start, "strftime") and t.earliest_start else (str(t.earliest_start)[:10] if t.earliest_start else ""),
            "deadline": t.deadline.strftime("%Y-%m-%d") if hasattr(t.deadline, "strftime") and t.deadline else (str(t.deadline)[:10] if t.deadline else ""),
            "depends_on": deps,
        })

    windows_json_list = []
    for w in windows:
        windows_json_list.append({
            "id": w.id,
            "service_date": w.service_date,
            "corridor_id": w.corridor_id,
            "section_id": w.section_id,
            "line_id": w.line_id,
            "start_time": w.start_time,
            "end_time": w.end_time,
            "available_minutes": w.available_minutes,
            "block_type": w.block_type,
            "requires_power_isolation": bool(w.requires_power_isolation),
            "requires_signal_disconnection": bool(w.requires_signal_disconnection),
            "expected_train_count": w.expected_train_count or 0,
            "goods_risk_score": w.goods_risk_score or 0,
            "status": w.status,
        })

    blocks_json = json.dumps(windows_json_list)
    tasks_json = json.dumps(tasks_json_list)

    # Call C++ solver (5s 8 workers)
    start = time.time()
    result_json = _cpp.solve(blocks_json, tasks_json, int(time_limit))
    runtime = time.time() - start

    # Parse result
    if isinstance(result_json, bytes):
        result_json = result_json.decode()
    result = json.loads(result_json) if isinstance(result_json, str) else result_json

    status = result.get("status", "UNKNOWN")
    assignments = result.get("assignments") or []
    objective_value = result.get("objective_value", 0)

    if status in ("INFEASIBLE", "MODEL_INVALID", "UNKNOWN") or not assignments:
        # let caller try fallback (or return None to trigger fallback in caller)
        # we return None so the outer fallback handles it, but preserve runtime
        return None, status, {}, runtime

    # Persist like Python optimizer: create BlockPlan and Blocks
    plan_id = f"PLAN-{str(uuid.uuid4())[:8].upper()}"
    plan = BlockPlan(
        id=plan_id,
        horizon_type=horizon_type,
        start_date=horizon_start,
        end_date=horizon_end,
        status="DRAFT",
        solver_status=status,
        created_at=datetime.datetime.utcnow(),
        version=1,
    )
    db.add(plan)
    db.flush()

    # Map window id -> Window object
    win_map = {w.id: w for w in windows}
    task_map = {t.id: t for t in tasks}

    scheduled = set()
    blocks_created = 0
    # Compute breakdown similar to optimizer.py
    comp = {
        "priority_value": 0,
        "critical_benefit": 0,
        "overdue_reduction": 0,
        "integrated_group_benefit": 0,
        "asset_availability_benefit": 0,
        "train_penalty": 0,
        "unused_penalty": 0,
        "resource_cost": 0,
    }

    for a in assignments:
        tid = a.get("task_id")
        wid = a.get("window_id")
        if not tid or not wid or tid in scheduled:
            continue
        t = task_map.get(tid)
        w = win_map.get(wid)
        if not t or not w:
            continue
        # double-check hard conflict before persisting (safety)
        fit, _ = check_task_window_fit(t, w)
        if fit == "HARD_CONFLICT":
            continue
        blk_id = f"BLK-{str(uuid.uuid4())[:8].upper()}"
        total_dur = (t.estimated_duration_minutes or 60) + (t.setup_duration_minutes or 15)
        blk = Block(
            id=blk_id,
            plan_id=plan_id,
            window_id=w.id,
            corridor_id=w.corridor_id,
            section_id=w.section_id,
            line_id=w.line_id,
            service_date=w.service_date,
            start_time=w.start_time,
            end_time=min(w.start_time + total_dur, w.end_time),
            block_type=w.block_type,
            requires_power_isolation=w.requires_power_isolation,
            requires_signal_disconnection=w.requires_signal_disconnection,
            status="GENERATED",
            department=t.department,
        )
        db.add(blk)
        db.flush()
        db.add(BlockTask(block_id=blk_id, task_id=tid, status="SCHEDULED", sequence=0))
        scheduled.add(tid)
        blocks_created += 1
        comp["priority_value"] += t.priority_score or 0
        if t.priority_band == "CRITICAL":
            comp["critical_benefit"] += 20
        comp["overdue_reduction"] += min(20, (t.overdue_days or 0) * 2)
        comp["asset_availability_benefit"] += (t.asset_criticality or 50) * 0.05
        comp["train_penalty"] += w.goods_risk_score * 0.2 + w.expected_train_count * 5
        comp["unused_penalty"] += max(0, w.available_minutes - total_dur) * 0.1

    # Group benefit: count integrated if we had groups (currently none, so 0)
    comp["integrated_groups"] = 0
    objective_value = sum([
        comp["priority_value"] * 10,
        comp["critical_benefit"] * 10,
        comp["overdue_reduction"] * 10,
        comp["asset_availability_benefit"] * 10,
    ]) - sum([comp["train_penalty"] * 10, comp["unused_penalty"] * 10])

    plan.objective_breakdown = json.dumps(comp)
    plan.optimized_metrics = json.dumps({
        "scheduled": len(scheduled),
        "blocks": blocks_created,
        "integrated_groups": 0,
        "candidate_count": len(tasks_json_list) * len(windows_json_list),
        "group_count": 0,
        "selected_group_count": 0,
        "objective_value": objective_value,
        "solver_runtime": runtime,
        "solver": result.get("solver", "cpp-cp-sat"),
        "workers": result.get("workers", 8),
        "has_ortools": _cpp_has_ortools,
    })
    plan.baseline_metrics = json.dumps({})
    unscheduled = [{"task_id": t.id, "reason": "Not selected by C++ optimizer"} for t in tasks if t.id not in scheduled]
    plan.unscheduled_reasons = json.dumps(unscheduled)
    db.commit()

    return plan, status, comp, runtime
