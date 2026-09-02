import uuid, json, datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models import Block, BlockTask, Task, ExecutionRecord, BlockPlan, AuditEvent, Notification

def record_execution(db: Session, block_id: str, payload: dict):
    # block_id must be BLK-* canonical, not WND-*
    if block_id.startswith("WND-"):
        raise HTTPException(status_code=400, detail="Never use a WND-* candidate-window identifier where a selected BLK-* identifier is required.")
    block = db.query(Block).filter(Block.id==block_id).first()
    if not block:
        raise HTTPException(status_code=404, detail=f"Block {block_id} not found")
    plan = db.query(BlockPlan).filter(BlockPlan.id==block.plan_id).first()
    # validation
    actual_start = payload.get("actual_start")
    actual_end = payload.get("actual_end")
    status = payload.get("status")
    completed_task_ids = payload.get("completed_task_ids") or []
    partially_completed_task_ids = payload.get("partially_completed_task_ids") or []
    cancelled_task_ids = payload.get("cancelled_task_ids") or []
    reason = payload.get("reason") or ""
    asset_status = payload.get("asset_status") or ""
    train_impact = payload.get("train_impact") or ""
    notes = payload.get("notes") or ""
    recorded_by = payload.get("recorded_by") or "demo_user"
    service_date = payload.get("service_date") or block.service_date

    # actual_end >= actual_start
    if actual_start is not None and actual_end is not None:
        try:
            s = int(actual_start); e = int(actual_end)
            if e < s:
                raise HTTPException(status_code=400, detail="actual_end must be >= actual_start")
            actual_start=s; actual_end=e
        except HTTPException:
            raise
        except:
            raise HTTPException(status_code=400, detail="Invalid actual_start/end")
    else:
        raise HTTPException(status_code=400, detail="actual_start and actual_end required")

    # cancelled requires reason
    if status=="CANCELLED" and not reason:
        raise HTTPException(status_code=400, detail="Cancelled status requires reason")
    if status=="DEFERRED" and not reason:
        raise HTTPException(status_code=400, detail="Deferred status requires reason")
    if status=="PARTIALLY_COMPLETED" and not (partially_completed_task_ids or notes):
        raise HTTPException(status_code=400, detail="Partial completion requires task selection or notes")

    # completed task belongs to block
    block_task_ids = [bt.task_id for bt in db.query(BlockTask).filter(BlockTask.block_id==block_id).all()]
    for tid in completed_task_ids + partially_completed_task_ids + cancelled_task_ids:
        if tid not in block_task_ids:
            raise HTTPException(status_code=400, detail=f"Task {tid} does not belong to block {block_id}")

    # duplicate submission returns 409 or idempotent
    existing = db.query(ExecutionRecord).filter(ExecutionRecord.block_id==block_id).first()
    if existing:
        # check if same payload -> idempotent return existing, else 409
        if existing.actual_start==actual_start and existing.actual_end==actual_end and existing.status==status:
            return existing, 200
        raise HTTPException(status_code=409, detail=f"Duplicate execution for block {block_id}")

    # create execution record
    exe_id=f"EXE-{str(uuid.uuid4())[:8].upper()}"
    rec = ExecutionRecord(
        id=exe_id,
        block_id=block_id,
        plan_id=block.plan_id,
        actual_start=actual_start,
        actual_end=actual_end,
        service_date=service_date,
        status=status or "COMPLETED",
        completed_task_ids=json.dumps(completed_task_ids),
        partially_completed_task_ids=json.dumps(partially_completed_task_ids),
        cancelled_task_ids=json.dumps(cancelled_task_ids),
        reason=reason,
        asset_status=asset_status,
        train_impact=train_impact,
        notes=notes,
        recorded_by=recorded_by,
        created_at=datetime.datetime.utcnow()
    )
    db.add(rec)
    # update block status
    if status in ["COMPLETED","PARTIALLY_COMPLETED","CANCELLED"]:
        block.status=status
    else:
        block.status="COMPLETED"
    # update BlockTask and Task status
    for tid in completed_task_ids:
        bt = db.query(BlockTask).filter(BlockTask.block_id==block_id, BlockTask.task_id==tid).first()
        if bt: bt.status="COMPLETED"
        t = db.query(Task).filter(Task.id==tid).first()
        if t: t.status="COMPLETED"
    for tid in partially_completed_task_ids:
        bt = db.query(BlockTask).filter(BlockTask.block_id==block_id, BlockTask.task_id==tid).first()
        if bt: bt.status="PARTIALLY_COMPLETED"
        t = db.query(Task).filter(Task.id==tid).first()
        if t: t.status="PARTIALLY_COMPLETED"
    for tid in cancelled_task_ids:
        bt = db.query(BlockTask).filter(BlockTask.block_id==block_id, BlockTask.task_id==tid).first()
        if bt: bt.status="CANCELLED"
        t = db.query(Task).filter(Task.id==tid).first()
        if t: t.status="CANCELLED"

    # audit
    db.add(AuditEvent(action="EXECUTION", entity_type="Block", entity_id=block_id, user_id=recorded_by, details=json.dumps(payload)))
    # metrics update: could trigger but leave
    db.commit()
    db.refresh(rec)
    return rec, 201

def get_executions_for_plan(db: Session, plan_id: str):
    return db.query(ExecutionRecord).filter(ExecutionRecord.plan_id==plan_id).all()

def get_all_executions(db: Session):
    return db.query(ExecutionRecord).all()
