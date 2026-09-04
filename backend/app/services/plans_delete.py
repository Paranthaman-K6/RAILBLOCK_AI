import json
from sqlalchemy.orm import Session
from app.models import BlockPlan, Block, BlockTask, Approval, PlanRevision, PlanChange, Notification, ExecutionRecord, AuditEvent

# Only these statuses are deletable (strict immutable rule)
DELETABLE_STATUSES = {"DRAFT"}  # optionally add "REJECTED" if needed, but keep DRAFT only for now
AUTHORIZED_ROLES = {"CONTROL_OFFICE", "ADMIN"}
CAP_BULK = 50

def _can_delete(plan: BlockPlan, role: str):
    if plan.status not in DELETABLE_STATUSES:
        return False, f"Only DRAFT can be deleted (current: {plan.status})"
    if role not in AUTHORIZED_ROLES:
        return False, "Forbidden — requires CONTROL_OFFICE or ADMIN"
    return True, ""

def delete_draft_plan(db: Session, plan_id: str, actor_id: str, actor_role: str):
    pid = plan_id.upper()
    plan = db.query(BlockPlan).filter(BlockPlan.id == pid).first()
    if not plan:
        return None, "Plan not found", 404
    ok, msg = _can_delete(plan, actor_role)
    if not ok:
        code = 403 if "Forbidden" in msg else 400
        return None, msg, code
    # locked if any execution exists
    if db.query(ExecutionRecord).filter(ExecutionRecord.plan_id == plan.id).first():
        return None, "Completed/Locked plan cannot be deleted (has ExecutionRecord)", 400
    # also block if plan is base for a revision (has been revised) — preserve history
    if db.query(PlanRevision).filter(PlanRevision.base_plan_id == plan.id).first():
        return None, "Plan has revisions — cannot be deleted", 400
    block_ids = [b.id for b in db.query(Block).filter(Block.plan_id == plan.id).all()]
    # cascade deletes
    if block_ids:
        db.query(BlockTask).filter(BlockTask.block_id.in_(block_ids)).delete(synchronize_session=False)
        # PlanChange is via PlanRevision, not directly, but clean notifications
        db.query(Notification).filter(Notification.plan_id == plan.id).delete(synchronize_session=False)
        db.query(Approval).filter(Approval.plan_id == plan.id).delete(synchronize_session=False)
        # PlanRevision where new_plan_id == pid (should not happen for DRAFT, but clean)
        db.query(PlanRevision).filter(PlanRevision.new_plan_id == plan.id).delete(synchronize_session=False)
        db.query(Block).filter(Block.plan_id == plan.id).delete(synchronize_session=False)
    else:
        db.query(Approval).filter(Approval.plan_id == plan.id).delete(synchronize_session=False)
        db.query(Notification).filter(Notification.plan_id == plan.id).delete(synchronize_session=False)
    details = json.dumps({"status": plan.status, "blocks": len(block_ids), "deleted_by": actor_id, "role": actor_role})
    db.add(AuditEvent(action="DELETE", entity_type="BlockPlan", entity_id=plan.id, user_id=actor_id, details=details))
    db.delete(plan)
    db.commit()
    return plan, "Deleted", 200

def bulk_delete_drafts(db: Session, plan_ids: list, actor_id: str, actor_role: str):
    if not plan_ids:
        return {"deleted": [], "failed": [{"id": "", "reason": "No plan_ids", "code": 400}]}, "No plan_ids", 400
    if len(plan_ids) > CAP_BULK:
        return {"deleted": [], "failed": [{"id": pid, "reason": f"Bulk cap {CAP_BULK}", "code": 400} for pid in plan_ids]}, f"Bulk cap {CAP_BULK}", 400
    if actor_role not in AUTHORIZED_ROLES:
        return {"deleted": [], "failed": [{"id": pid, "reason": "Forbidden", "code": 403} for pid in plan_ids]}, "Forbidden", 403
    # normalize upper and dedupe preserve order
    seen = set()
    norm_ids = []
    for pid in plan_ids:
        u = str(pid).strip().upper()
        if u and u not in seen:
            seen.add(u)
            norm_ids.append(u)
    deleted = []
    failed = []
    for pid in norm_ids:
        plan = db.query(BlockPlan).filter(BlockPlan.id == pid).first()
        if not plan:
            failed.append({"id": pid, "reason": "Plan not found", "code": 404})
            continue
        ok, msg = _can_delete(plan, actor_role)
        if not ok:
            code = 403 if "Forbidden" in msg else 400
            failed.append({"id": pid, "reason": msg, "code": code})
            continue
        if db.query(ExecutionRecord).filter(ExecutionRecord.plan_id == plan.id).first():
            failed.append({"id": pid, "reason": "Locked (has ExecutionRecord)", "code": 400})
            continue
        if db.query(PlanRevision).filter(PlanRevision.base_plan_id == plan.id).first():
            failed.append({"id": pid, "reason": "Has revisions", "code": 400})
            continue
        block_ids = [b.id for b in db.query(Block).filter(Block.plan_id == plan.id).all()]
        if block_ids:
            db.query(BlockTask).filter(BlockTask.block_id.in_(block_ids)).delete(synchronize_session=False)
            db.query(Notification).filter(Notification.plan_id == plan.id).delete(synchronize_session=False)
            db.query(Approval).filter(Approval.plan_id == plan.id).delete(synchronize_session=False)
            db.query(PlanRevision).filter(PlanRevision.new_plan_id == plan.id).delete(synchronize_session=False)
            db.query(Block).filter(Block.plan_id == plan.id).delete(synchronize_session=False)
        else:
            db.query(Approval).filter(Approval.plan_id == plan.id).delete(synchronize_session=False)
            db.query(Notification).filter(Notification.plan_id == plan.id).delete(synchronize_session=False)
        details = json.dumps({"status": plan.status, "blocks": len(block_ids), "deleted_by": actor_id, "role": actor_role, "bulk": True})
        db.add(AuditEvent(action="DELETE", entity_type="BlockPlan", entity_id=plan.id, user_id=actor_id, details=details))
        db.delete(plan)
        deleted.append(pid)
    # one commit for all
    if deleted:
        db.commit()
    else:
        db.rollback()
    code = 200 if not failed else 207
    msg = f"Deleted {len(deleted)}, failed {len(failed)}" if failed else f"Deleted {len(deleted)}"
    return {"deleted": deleted, "failed": failed, "deleted_count": len(deleted), "failed_count": len(failed)}, msg, code
