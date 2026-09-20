from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.metrics import calculate_metrics, get_all_metrics

router = APIRouter(prefix="/api/metrics", tags=["metrics"])

@router.get("")
def all_metrics(db: Session = Depends(get_db)):
    # Instant metrics: no ThreadPool (pool_size 5 doubling caused 4s timeout on Render free)
    # Previous 4s guard still timed out on 10-plan loop (>30s). Now direct with small limit and skip validate.
    try:
        return get_all_metrics(db)
    except Exception as _e:
        # Fallback: latest single plan quickly
        try:
            from app.models import BlockPlan
            latest = db.query(BlockPlan).order_by(BlockPlan.created_at.desc()).first()
            if latest:
                m = calculate_metrics(db, latest.id)
                return [m] if m else []
        except Exception:
            pass
        return []

@router.get("/{plan_id}")
def one_metrics(plan_id: str, db: Session = Depends(get_db)):
    try:
        m = calculate_metrics(db, plan_id.upper())
    except Exception as _e:
        raise HTTPException(status_code=500, detail=str(_e)[:300])
    if not m:
        raise HTTPException(status_code=404, detail="Plan not found")
    # Ensure blocks[]/schedule[] present for frontend Gantt (deep module: small interface, DB-agnostic SQLite/Postgres pooled 6543)
    # calculate_metrics now includes blocks_detail/schedule; fallback attach if missing (e.g., legacy cache)
    if "blocks_detail" not in m or "schedule" not in m:
        try:
            from app.models import Block, BlockTask, Task
            pid = plan_id.upper()
            blocks = db.query(Block).filter(Block.plan_id == pid).all()
            if blocks:
                bts_all = db.query(BlockTask).filter(BlockTask.block_id.in_([b.id for b in blocks])).all() if blocks else []
                task_ids = [bt.task_id for bt in bts_all]
                tasks_map = {t.id: t for t in db.query(Task).filter(Task.id.in_(task_ids)).all()} if task_ids else {}
                from collections import defaultdict
                bts_by_block = defaultdict(list)
                for bt in bts_all:
                    bts_by_block[bt.block_id].append(bt)
                payload = []
                for blk in blocks:
                    bts = bts_by_block.get(blk.id, [])
                    tasks_out = [{"task_id": bt.task_id, "status": bt.status, "department": tasks_map.get(bt.task_id).department if tasks_map.get(bt.task_id) else None} for bt in bts]
                    payload.append({
                        "block_id": blk.id, "plan_id": blk.plan_id, "window_id": blk.window_id,
                        "service_date": blk.service_date, "start_time": blk.start_time, "end_time": blk.end_time,
                        "corridor_id": blk.corridor_id, "section_id": blk.section_id, "line_id": blk.line_id,
                        "block_type": blk.block_type, "status": blk.status, "department": blk.department, "tasks": tasks_out,
                    })
                m["blocks_detail"] = payload
                m["blocks_list"] = payload
                m["blocks_data"] = payload
                m["schedule"] = payload
                # keep `blocks` count as int for backward compat; if caller expects array, provide `blocks` alias only when not shadowing count
                # frontend prefers blocks_detail/schedule, so no need to overwrite `blocks` int
                if "blocks_array" not in m:
                    m["blocks_array"] = payload
        except Exception:
            pass
    return m
