"""
heavy_calc — Deep Module (Seam: backend/app/services/heavy_calc.py)

Design: codebase-design :: deep module
- **Module**: heavy_calc — small interface, lots of implementation hidden in Rust.
- **Interface**: 3 functions (recalc_priority, feasible_windows, validate_plan) — few methods, simple params (JSON strings / DB handle).
- **Implementation**: CPU-heavy logic in `railblock_rs` (Rust + rayon); Python is thin adapter.
- **Seam**: this file. Callers cross this seam; tests cross the same seam. One adapter (Python fallback)
  means a hypothetical seam, two adapters (Rust + pure-Python) make it a real seam (Feathers).
- **Leverage**: one Rust implementation serves all callers + metrics path.
- **Locality**: priority formula (P=0.30S+0.20U+0.20C+0.15O+0.10D+0.05R), train protected-interval
  `[dep-buf, arr+buf)`, and 14 validator checks A-L concentrate here via Rust.
- **Depth**: large behaviour (rayon parallel, serde) behind 3 string→string / db→None functions.
  Deletion test: deleting this module would scatter priority, feasibility, and validation
  complexity across plans, optimizer, grouping, and validator.

Adapter strategy (real seam):
  - tries `import railblock_rs` (Rust cdylib). If present, delegates JSON string→string
    functions to Rust with rayon. All heavy logic in Rust.
  - fallback to pure-Python services (priority.py, candidate_windows.py, plan_validator.py)
    when Rust not built (dev) or on error — never breaks existing imports.
  - Rust functions: `recalc_priority(tasks_json)->str`, `feasible_windows(win_json,train_json)->str`,
    `validate_plan(blocks_json)->str` — each does rayon parallel work and returns JSON.

Thin adapter rule: this file must NOT contain duplicated heavy logic beyond fallback shim.
"""

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── Rust availability probe (real seam: two adapters) ──
try:
    import railblock_rs  # type: ignore

    _HAS_RUST = True
    logger.info("heavy_calc: railblock_rs Rust extension available — using rayon path")
except ImportError as _e:
    railblock_rs = None  # type: ignore
    _HAS_RUST = False
    logger.info("heavy_calc: railblock_rs not available (%s) — fallback to pure Python", _e)
except Exception as _e:  # e.g. built against wrong Python
    railblock_rs = None  # type: ignore
    _HAS_RUST = False
    logger.warning("heavy_calc: railblock_rs import failed (%s) — fallback", _e)

__all__ = ["recalc_priority", "feasible_windows", "validate_plan", "has_rust"]


def has_rust() -> bool:
    """Probe helper for diagnostics/health."""
    return _HAS_RUST


# ──────────────────────────────────────────────────────────────
# 1. recalc_priority — seam takes DB Session, adapter serializes → Rust JSON→JSON
# ──────────────────────────────────────────────────────────────
def recalc_priority(db) -> None:
    """Recalculate priorities for all tasks in *db*.

    Deep-module adapter: hides weight lookup, serialization, rayon parallel ranking.
    Uses railblock_rs.recalc_priority(tasks_json) when available, else
    delegates to app.services.priority.recalculate_all (fallback).

    Interface is minimal: one arg (db), no return (mutates DB). Caller learns one function,
    gets historical-aware ranking, weighted formula, band, reason, and rayon speed.
    """
    # Fast path: Rust
    if _HAS_RUST:
        try:
            from app.models import Task  # local import to avoid cycles

            tasks = db.query(Task).all()
            if not tasks:
                return

            # Serialize minimal fields needed by Rust (matches lib.rs TaskInput)
            payload = []
            for t in tasks:
                payload.append(
                    {
                        "id": t.id,
                        "safety_score": float(t.safety_score or 50),
                        "urgency_score": float(t.urgency_score) if t.urgency_score is not None else None,
                        "asset_criticality": float(t.asset_criticality or 50),
                        "operational_impact": float(t.operational_impact or 50),
                        "overdue_days": int(t.overdue_days or 0),
                        "coordination_value": float(t.coordination_value or 50),
                        "resource_readiness": float(t.resource_readiness or 50),
                        "corridor_id": t.corridor_id,
                        "department": t.department,
                    }
                )

            tasks_json = json.dumps(payload)
            out_json: str = railblock_rs.recalc_priority(tasks_json)  # type: ignore
            ranked = json.loads(out_json)

            # Map back: ranked items contain id, priority_score, priority_band, priority_reason,
            # factor_values/breakdown, priority_rank
            rank_map = {r["id"]: r for r in ranked}
            # Need weights version — reuse fallback's version helper without duplicating logic
            try:
                from app.services.priority import _get_active_weights

                _, version = _get_active_weights(db)
            except Exception:
                version = "v1"

            for t in tasks:
                r = rank_map.get(t.id)
                if not r:
                    continue
                t.priority_score = r.get("priority_score", 0)
                t.priority_band = r.get("priority_band", "MEDIUM")
                t.priority_reason = r.get("priority_reason", "standard maintenance")
                # Store breakdown as JSON string for compatibility
                breakdown = r.get("priority_breakdown") or r.get("priority_breakdown", {})
                if not breakdown:
                    # construct from factor_values if breakdown missing
                    fv = r.get("factor_values", {})
                    breakdown = {
                        "S": fv.get("S"),
                        "U": fv.get("U"),
                        "C": fv.get("C"),
                        "O": fv.get("O"),
                        "D": fv.get("D"),
                        "R": fv.get("R"),
                        "P": r.get("priority_score"),
                    }
                t.priority_breakdown = json.dumps(breakdown)
                t.rule_configuration_version = version
                t.priority_rank = r.get("priority_rank", 0)

            db.commit()
            # Ensure ranking order committed (Rust already sorted, but re-affirm)
            return
        except Exception as e:
            logger.warning("heavy_calc.recalc_priority Rust path failed (%s) — falling back", e, exc_info=False)

    # Fallback: pure Python (single adapter)
    from app.services.priority import recalculate_all

    return recalculate_all(db)


# ──────────────────────────────────────────────────────────────
# 2. feasible_windows — JSON string→string, Rust with rayon; Python fallback via candidate_windows logic
# ──────────────────────────────────────────────────────────────
def feasible_windows(windows_json: str, trains_json: str) -> str:
    """Feasibility filter (heavy CPU in Rust).

    Interface: two JSON strings → one JSON string. Small surface; rayon hides O(W×T) overlap
    counting, corridor/date/line filtering, protected-interval rule, and synthetic CPU load.

    Fallback (no Rust): reproduces candidate_windows._overlap logic in Python (serial)
    for correctness in dev/test without Rust build.

    Returns JSON string of annotated windows (status FEASIBLE/REJECTED, expected_train_count).
    """
    if _HAS_RUST:
        try:
            return railblock_rs.feasible_windows(windows_json, trains_json)  # type: ignore
        except Exception as e:
            logger.warning("heavy_calc.feasible_windows Rust failed (%s) — fallback", e, exc_info=False)

    # Pure-Python fallback (same semantics as Rust, serial)
    try:
        windows = json.loads(windows_json) if windows_json else []
        trains = json.loads(trains_json) if trains_json else []
    except Exception as e:
        raise ValueError(f"feasible_windows invalid JSON: {e}")

    def _overlap(a_start, a_end, b_start, b_end):
        return a_start < b_end and a_end > b_start

    out = []
    for w in windows:
        expected = 0
        wid = w.get("id")
        cor = w.get("corridor_id")
        sec = w.get("section_id")
        lin = w.get("line_id")
        sdate = w.get("service_date")
        ws = int(w.get("start_time", 0))
        we = int(w.get("end_time", 0))
        for t in trains:
            if t.get("corridor_id") != cor:
                continue
            if t.get("service_date") != sdate:
                continue
            tl = t.get("line_id")
            if lin and tl and tl != lin:
                continue
            ts = t.get("section_id")
            if sec and ts and ts != sec:
                continue
            ps = int(t.get("departure_time", 0)) - int(t.get("buffer_before", 15))
            pe = int(t.get("arrival_time", 0)) + int(t.get("buffer_after", 15))
            if _overlap(ws, we, ps, pe):
                expected += 1
        hard = expected > 0
        status = "REJECTED" if hard else "FEASIBLE"
        rej = f"Train overlap {expected} trains" if hard else None
        out.append(
            {
                "id": wid,
                "corridor_id": cor,
                "section_id": sec,
                "line_id": lin,
                "service_date": sdate,
                "start_time": ws,
                "end_time": we,
                "available_minutes": w.get("available_minutes", we - ws),
                "expected_train_count": expected,
                "goods_risk_score": 0.0,
                "risk_band": "LOW",
                "status": status,
                "rejection_reason": rej,
            }
        )
    return json.dumps(out)


# Convenience overload: DB-aware feasible filtering (optional, keeps seam small)
def feasible_windows_for_db(db, corridor_id=None, service_date=None) -> str:
    """Helper that serializes DB windows/trains then delegates to feasible_windows(json,json)."""
    from app.models import CandidateWindow, TrainMovement

    q = db.query(CandidateWindow)
    if corridor_id:
        q = q.filter(CandidateWindow.corridor_id == corridor_id)
    if service_date:
        q = q.filter(CandidateWindow.service_date == service_date)
    windows = q.all()
    tq = db.query(TrainMovement)
    if corridor_id:
        tq = tq.filter(TrainMovement.corridor_id == corridor_id)
    if service_date:
        tq = tq.filter(TrainMovement.service_date == service_date)
    trains = tq.all()

    w_json = json.dumps(
        [
            {
                "id": w.id,
                "corridor_id": w.corridor_id,
                "section_id": w.section_id,
                "line_id": w.line_id,
                "service_date": w.service_date,
                "start_time": w.start_time,
                "end_time": w.end_time,
                "available_minutes": w.available_minutes,
                "status": w.status,
            }
            for w in windows
        ]
    )
    t_json = json.dumps(
        [
            {
                "id": t.id,
                "corridor_id": t.corridor_id,
                "section_id": t.section_id,
                "line_id": t.line_id,
                "service_date": t.service_date,
                "departure_time": t.departure_time,
                "arrival_time": t.arrival_time,
                "buffer_before": t.buffer_before,
                "buffer_after": t.buffer_after,
            }
            for t in trains
        ]
    )
    return feasible_windows(w_json, t_json)


# ──────────────────────────────────────────────────────────────
# 3. validate_plan — JSON string→string (Rust rayon), fallback to pure Python mirror
# ──────────────────────────────────────────────────────────────
def validate_plan(blocks_json: str) -> str:
    """Validate plan blocks (heavy CPU in Rust).

    Interface: one JSON string (list of blocks with nested tasks/trains/resource_ids)
    → one JSON string {valid, violations}. Two-argument JSON would be larger interface;
    single JSON with embedded tasks keeps interface small while Rust does parallel block checks,
    duration/power/signal/deadline/train/resource/duplicate-group checks via rayon.

    Fallback: pure-Python parallel-free mirror of lib.rs validate_plan for dev/test.
    """
    if _HAS_RUST:
        try:
            return railblock_rs.validate_plan(blocks_json)  # type: ignore
        except Exception as e:
            logger.warning("heavy_calc.validate_plan Rust failed (%s) — fallback", e, exc_info=False)

    # Python fallback (single-threaded, same violation codes)
    try:
        blocks = json.loads(blocks_json) if blocks_json else []
    except Exception as e:
        raise ValueError(f"validate_plan invalid JSON: {e}")

    def _overlap(a_s, a_e, b_s, b_e):
        return a_s < b_e and a_e > b_s

    violations = []
    if not blocks:
        return json.dumps(
            {"valid": False, "violations": [{"code": "EMPTY_PLAN", "message": "Plan has no blocks", "severity": "ERROR"}]}
        )

    seen = set()
    from collections import defaultdict

    # Resource map per (service_date, res_id)
    res_map = {}

    for blk in blocks:
        bid = blk.get("id") or blk.get("block_id") or "BLK-?"
        dur = int(blk.get("end_time", 0)) - int(blk.get("start_time", 0))
        st = int(blk.get("start_time", 0))
        et = int(blk.get("end_time", 0))
        sdate = blk.get("service_date", "")
        cor = blk.get("corridor_id")
        sec = blk.get("section_id")
        lin = blk.get("line_id")
        btype = blk.get("block_type", "TRAFFIC")
        bpi = bool(blk.get("requires_power_isolation", False))
        bsd = bool(blk.get("requires_signal_disconnection", False))
        tasks = blk.get("tasks") or blk.get("block_tasks") or []
        trains = blk.get("trains") or []

        if dur > 240:
            violations.append(
                {"code": "MAX_DURATION_EXCEEDED", "message": f"Block {bid} duration {dur} exceeds 240", "severity": "ERROR", "block_id": bid}
            )
        if dur <= 0:
            violations.append(
                {"code": "INVALID_DURATION", "message": f"Block {bid} invalid duration", "severity": "ERROR", "block_id": bid}
            )
        if not tasks:
            violations.append(
                {"code": "EMPTY_BLOCK", "message": f"Block {bid} has no tasks", "severity": "ERROR", "block_id": bid}
            )

        total_needed = 0
        for t in tasks:
            tid = t.get("id") or t.get("task_id") or "TSK-?"
            need = int(t.get("estimated_duration_minutes", 60)) + int(t.get("setup_duration_minutes", 15))
            total_needed += need
            if t.get("corridor_id") and t.get("corridor_id") != cor:
                violations.append({"code": "CORRIDOR_MISMATCH", "message": f"Task {tid} corridor mismatch", "severity": "ERROR", "block_id": bid})
            if t.get("section_id") and sec and t.get("section_id") != sec:
                violations.append({"code": "SECTION_MISMATCH", "message": f"Task {tid} section mismatch", "severity": "ERROR", "block_id": bid})
            if t.get("line_id") and lin and t.get("line_id") != lin:
                violations.append({"code": "LINE_MISMATCH", "message": f"Line mismatch for task {tid}", "severity": "ERROR", "block_id": bid})
            if t.get("required_block_type") and t.get("required_block_type") != btype:
                violations.append({"code": "BLOCK_TYPE_MISMATCH", "message": f"Block type mismatch for task {tid}", "severity": "ERROR", "block_id": bid})
            if t.get("requires_power_isolation") is not None and bool(t.get("requires_power_isolation")) != bpi:
                violations.append({"code": "POWER_MISMATCH", "message": f"Power isolation mismatch for task {tid}", "severity": "ERROR", "block_id": bid})
            if t.get("requires_signal_disconnection") is not None and bool(t.get("requires_signal_disconnection")) != bsd:
                violations.append({"code": "SIGNAL_MISMATCH", "message": f"Signalling mismatch for task {tid}", "severity": "ERROR", "block_id": bid})
            if need > dur:
                violations.append(
                    {"code": "DURATION_OVERFLOW", "message": f"Task {tid} duration {need} exceeds block {bid} duration", "severity": "ERROR", "block_id": bid}
                )
            dl = t.get("deadline")
            if dl and sdate and sdate > str(dl)[:10]:
                violations.append(
                    {"code": "DEADLINE_VIOLATION", "message": f"Task {tid} deadline {dl} before block date {sdate}", "severity": "ERROR", "block_id": bid}
                )
            # duplicate
            if tid in seen:
                violations.append(
                    {"code": "DUPLICATE_TASK", "message": f"Task {tid} assigned multiple times", "severity": "ERROR", "field": "task_id", "block_id": bid}
                )
            else:
                seen.add(tid)

        if len(tasks) > 1 and total_needed > dur:
            violations.append(
                {"code": "GROUP_DURATION_MISMATCH", "message": f"Block {bid} duration {dur} != sum {total_needed} for integrated group", "severity": "ERROR", "block_id": bid}
            )

        # Train conflict
        for tr in trains:
            if tr.get("corridor_id") != cor or tr.get("service_date") != sdate:
                continue
            if lin and tr.get("line_id") and tr.get("line_id") != lin:
                continue
            if sec and tr.get("section_id") and tr.get("section_id") != sec:
                continue
            ps = int(tr.get("departure_time", 0)) - int(tr.get("buffer_before", 15))
            pe = int(tr.get("arrival_time", 0)) + int(tr.get("buffer_after", 15))
            if _overlap(st, et, ps, pe):
                violations.append(
                    {
                        "code": "TRAIN_CONFLICT",
                        "message": f"Block {bid} overlaps train {tr.get('id','TRN-?')} protected interval",
                        "severity": "ERROR",
                        "block_id": bid,
                    }
                )
                break

        # Resource conflict simple per (sdate, resource_id)
        for rid in blk.get("resource_ids", []) or []:
            key = (sdate, rid)
            if key in res_map:
                other = res_map[key]
                if _overlap(st, et, other["start_time"], other["end_time"]):
                    violations.append(
                        {
                            "code": "RESOURCE_CONFLICT",
                            "message": f"Resource {rid} conflict between blocks {bid} and {other['id']}",
                            "severity": "ERROR",
                            "block_id": bid,
                        }
                    )
            else:
                res_map[key] = {"id": bid, "start_time": st, "end_time": et}

    return json.dumps({"valid": len(violations) == 0, "violations": violations})


# DB convenience overload for validate_plan (keeps callers thin: pass db+plan_id)
def validate_plan_db(db, plan_id: str) -> dict:
    """DB adapter that builds blocks_json from plan_id then delegates to validate_plan(json)."""
    # If Rust not available, delegate directly to canonical validator to preserve 14 checks + grouping
    if not _HAS_RUST:
        try:
            from app.services.plan_validator import validate_plan as _py_validate

            return _py_validate(db, plan_id)
        except Exception:
            pass
    # Otherwise serialize blocks for Rust
    try:
        from app.models import Block, BlockTask, Task, TrainMovement

        blocks = db.query(Block).filter(Block.plan_id == plan_id).all()
        payload = []
        for blk in blocks:
            bts = db.query(BlockTask).filter(BlockTask.block_id == blk.id).all()
            tasks = []
            for bt in bts:
                t = db.query(Task).filter(Task.id == bt.task_id).first()
                if not t:
                    continue
                tasks.append(
                    {
                        "id": t.id,
                        "corridor_id": t.corridor_id,
                        "section_id": t.section_id,
                        "line_id": t.line_id,
                        "required_block_type": t.required_block_type,
                        "requires_power_isolation": t.requires_power_isolation,
                        "requires_signal_disconnection": t.requires_signal_disconnection,
                        "estimated_duration_minutes": t.estimated_duration_minutes,
                        "setup_duration_minutes": t.setup_duration_minutes,
                        "deadline": t.deadline.strftime("%Y-%m-%d") if t.deadline else None,
                        "department": t.department,
                    }
                )
            trains = db.query(TrainMovement).filter(TrainMovement.corridor_id == blk.corridor_id, TrainMovement.service_date == blk.service_date).all()
            payload.append(
                {
                    "id": blk.id,
                    "plan_id": blk.plan_id,
                    "window_id": blk.window_id,
                    "corridor_id": blk.corridor_id,
                    "section_id": blk.section_id,
                    "line_id": blk.line_id,
                    "service_date": blk.service_date,
                    "start_time": blk.start_time,
                    "end_time": blk.end_time,
                    "block_type": blk.block_type,
                    "requires_power_isolation": blk.requires_power_isolation,
                    "requires_signal_disconnection": blk.requires_signal_disconnection,
                    "department": blk.department,
                    "tasks": tasks,
                    "trains": [
                        {
                            "id": tr.id,
                            "corridor_id": tr.corridor_id,
                            "section_id": tr.section_id,
                            "line_id": tr.line_id,
                            "service_date": tr.service_date,
                            "departure_time": tr.departure_time,
                            "arrival_time": tr.arrival_time,
                            "buffer_before": tr.buffer_before,
                            "buffer_after": tr.buffer_after,
                        }
                        for tr in trains
                    ],
                }
            )
        j = json.dumps(payload)
        out = validate_plan(j)
        return json.loads(out)
    except Exception as e:
        logger.warning("heavy_calc.validate_plan_db serialization failed (%s) — using fallback validator", e)
        from app.services.plan_validator import validate_plan as _py_validate

        return _py_validate(db, plan_id)
