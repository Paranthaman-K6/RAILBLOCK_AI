import uuid, json, datetime, copy
from sqlalchemy.orm import Session
from app.models import BlockPlan, Block, BlockTask, PlanRevision, PlanChange, AuditEvent
from app.services.plan_validator import validate_plan
from app.services.state_machine import is_immutable_status

def create_revision(db: Session, base_plan_id: str, reason: str, editor="demo_user"):
    base = db.query(BlockPlan).filter(BlockPlan.id==base_plan_id).first()
    if not base:
        return None, "Base plan not found", 404
    # only approved/published can be revised? but spec says approved plan must use revision; draft edits directly
    if base.status not in ["APPROVED","PUBLISHED","SUPERSEDED"]:
        return None, "Only approved/published plans can be revised; edit draft directly", 400
    # create new plan copy
    new_plan_id=f"PLAN-{str(uuid.uuid4())[:8].upper()}"
    revision_number = db.query(PlanRevision).filter(PlanRevision.base_plan_id==base_plan_id).count() + 1
    new_plan = BlockPlan(
        id=new_plan_id,
        horizon_type=base.horizon_type,
        start_date=base.start_date,
        end_date=base.end_date,
        status="DRAFT",
        solver_status=base.solver_status,
        created_at=datetime.datetime.utcnow(),
        version=base.version + 1,
        baseline_metrics=base.baseline_metrics,
        optimized_metrics=base.optimized_metrics,
        objective_breakdown=base.objective_breakdown,
        unscheduled_reasons=base.unscheduled_reasons,
        base_plan_id=base_plan_id
    )
    db.add(new_plan)
    db.flush()
    # copy blocks and block_tasks
    blocks = db.query(Block).filter(Block.plan_id==base_plan_id).all()
    id_map={}
    for blk in blocks:
        new_blk_id=f"BLK-{str(uuid.uuid4())[:8].upper()}"
        id_map[blk.id]=new_blk_id
        new_blk=Block(
            id=new_blk_id,
            plan_id=new_plan_id,
            window_id=blk.window_id,
            corridor_id=blk.corridor_id,
            section_id=blk.section_id,
            line_id=blk.line_id,
            service_date=blk.service_date,
            start_time=blk.start_time,
            end_time=blk.end_time,
            block_type=blk.block_type,
            requires_power_isolation=blk.requires_power_isolation,
            requires_signal_disconnection=blk.requires_signal_disconnection,
            status="GENERATED",
            department=blk.department
        )
        db.add(new_blk)
        db.flush()
        for bt in db.query(BlockTask).filter(BlockTask.block_id==blk.id).all():
            # freeze completed tasks: if task is COMPLETED, keep LOCKED
            from app.models import Task
            task = db.query(Task).filter(Task.id==bt.task_id).first()
            status = "LOCKED" if task and task.status in ["COMPLETED","LOCKED"] else "SCHEDULED"
            db.add(BlockTask(block_id=new_blk_id, task_id=bt.task_id, status=status, sequence=bt.sequence))
    rev_id=f"REV-{str(uuid.uuid4())[:8].upper()}"
    rev=PlanRevision(id=rev_id, base_plan_id=base_plan_id, new_plan_id=new_plan_id, revision_number=revision_number, reason=reason, created_at=datetime.datetime.utcnow(), created_by=editor)
    db.add(rev)
    db.add(AuditEvent(action="REVISION_CREATE", entity_type="BlockPlan", entity_id=new_plan_id, user_id=editor, details=json.dumps({"base":base_plan_id,"revision":revision_number})))
    db.commit()
    return new_plan, rev, 200

def edit_draft_block(db: Session, plan_id: str, block_id: str, updates: dict, editor="demo_user", reason="Edit"):
    plan = db.query(BlockPlan).filter(BlockPlan.id==plan_id).first()
    if not plan:
        return None, "Plan not found", 404
    if plan.status != "DRAFT":
        return None, "Approved and published plans are immutable. Create revision.", 400
    block = db.query(Block).filter(Block.id==block_id, Block.plan_id==plan_id).first()
    if not block:
        return None, "Block not found", 404
    # check completed preservation: cannot move completed task
    bts = db.query(BlockTask).filter(BlockTask.block_id==block_id).all()
    for bt in bts:
        from app.models import Task
        task = db.query(Task).filter(Task.id==bt.task_id).first()
        if task and task.status in ["COMPLETED","LOCKED"] and ("service_date" in updates or "start_time" in updates):
            return None, "Completed and approved work cannot be moved.", 400
    old = {k: getattr(block,k) for k in updates if hasattr(block,k)}
    for k,v in updates.items():
        if hasattr(block,k):
            setattr(block,k,v)
    # validate after edit
    from app.services.plan_validator import validate_plan
    val = validate_plan(db, plan_id)
    if not val["valid"]:
        db.rollback()
        return None, f"Edit violates constraints: {val['violations']}", 400
    # audit change
    db.add(AuditEvent(action="EDIT", entity_type="Block", entity_id=block_id, user_id=editor, details=json.dumps({"old":old,"new":updates,"reason":reason})))
    # also plan change if revision? For draft, just audit
    db.commit()
    return block, "Edited", 200

def get_history(db: Session, plan_id: str):
    revs = db.query(PlanRevision).filter((PlanRevision.base_plan_id==plan_id) | (PlanRevision.new_plan_id==plan_id)).all()
    # also audit events
    audits = db.query(AuditEvent).filter(AuditEvent.entity_id==plan_id).all()
    return {"revisions": revs, "audits": audits}

def get_changes(db: Session, plan_id: str):
    # find revision for this plan
    rev = db.query(PlanRevision).filter(PlanRevision.new_plan_id==plan_id).first()
    if not rev:
        return []
    changes = db.query(PlanChange).filter(PlanChange.revision_id==rev.id).all()
    return changes
