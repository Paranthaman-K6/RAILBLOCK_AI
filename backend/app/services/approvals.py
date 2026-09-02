import datetime, json
from sqlalchemy.orm import Session
from app.models import BlockPlan, Block, Approval, AuditEvent, Notification
from app.services.plan_validator import validate_plan
from app.services.state_machine import can_transition

def approve_plan(db: Session, plan_id: str, approver_id: str, approver_role: str, reason="Approved"):
    plan = db.query(BlockPlan).filter(BlockPlan.id==plan_id).first()
    if not plan:
        return None, "Plan not found", 404
    if plan.status not in ["DRAFT","UNDER_REVIEW"]:
        return None, f"Plan in {plan.status} not reviewable (must be DRAFT->submit-review->UNDER_REVIEW->approve)", 400
    # validate
    val = validate_plan(db, plan_id)
    if not val["valid"]:
        return None, f"Plan validation failed: {val['violations']}", 400
    if not approver_id or not approver_role:
        return None, "Approver identity required", 401
    # Normalize role/department - explicit authorization
    role_upper = approver_role.upper().replace(" ","_")
    # Only CONTROL_OFFICE and ADMIN can approve (explicit approval permission)
    # VIEWER and department-only (ENGINEERING, S_AND_T, TRACTION, PROJECTS) are not authorized
    authorized_roles = ["CONTROL_OFFICE","ADMIN"]
    if role_upper not in authorized_roles:
        return None, f"Approver role {role_upper} not authorized to approve", 403
    # Determine required departments from plan's blocks (efficient bulk)
    blocks = db.query(Block).filter(Block.plan_id==plan_id).all()
    required_depts = set()
    for b in blocks:
        # department may be comma-separated for integrated
        if b.department:
            for d in b.department.split(","):
                d = d.strip().upper()
                if d:
                    required_depts.add(d)
        # also check tasks directly for more accurate dept
    # Also check tasks via BlockTask for any dept not in block.department (fallback)
    if not required_depts:
        from app.models import BlockTask, Task
        for b in blocks:
            for bt in db.query(BlockTask).filter(BlockTask.block_id==b.id).all():
                t = db.query(Task).filter(Task.id==bt.task_id).first()
                if t and t.department:
                    required_depts.add(t.department.upper())
    # Record approval idempotently: if same approver_role already approved, return success (idempotent)
    existing = db.query(Approval).filter(Approval.plan_id==plan_id, Approval.approver_role==role_upper, Approval.decision=="APPROVED").first()
    if existing:
        return plan, f"Already approved by {role_upper}", 200
    approval = Approval(plan_id=plan_id, block_id=None, approver_id=approver_id, approver_role=role_upper, decision="APPROVED", reason=reason, created_at=datetime.datetime.utcnow())
    db.add(approval)
    db.add(AuditEvent(action="APPROVE", entity_type="BlockPlan", entity_id=plan_id, user_id=approver_id, details=json.dumps({"role":role_upper, "required": list(required_depts)})))
    # Only authorized roles (CONTROL_OFFICE/ADMIN) can transition to APPROVED
    plan.status = "APPROVED"
    for b in blocks:
        b.status = "APPROVED"
    # notifications to departments - efficient, one per dept
    for dept in list(required_depts) + ["CONTROL_OFFICE"]:
        db.add(Notification(department=dept, plan_id=plan_id, message=f"Plan {plan_id} approved by {role_upper}: {reason}", type="APPROVAL"))
    db.commit()
    db.refresh(plan)
    return plan, f"Approved by {role_upper} - Plan now APPROVED", 200

def reject_plan(db: Session, plan_id: str, approver_id: str, reason: str):
    plan = db.query(BlockPlan).filter(BlockPlan.id==plan_id).first()
    if not plan:
        return None, "Plan not found", 404
    if not reason:
        return None, "Rejection requires reason", 400
    plan.status = "REJECTED"
    blocks = db.query(Block).filter(Block.plan_id==plan_id).all()
    for b in blocks:
        b.status="REJECTED"
    db.add(Approval(plan_id=plan_id, block_id=None, approver_id=approver_id or "officer", approver_role="CONTROL_OFFICE", decision="REJECTED", reason=reason))
    db.add(AuditEvent(action="REJECT", entity_type="BlockPlan", entity_id=plan_id, user_id=approver_id or "officer", details=json.dumps({"reason":reason})))
    db.commit()
    return plan, "Rejected", 200

def publish_plan(db: Session, plan_id: str):
    plan = db.query(BlockPlan).filter(BlockPlan.id==plan_id).first()
    if not plan or plan.status!="APPROVED":
        return None, "Only approved plan can be published", 400
    plan.status="PUBLISHED"
    for b in db.query(Block).filter(Block.plan_id==plan_id).all():
        b.status="PUBLISHED"
    db.add(AuditEvent(action="PUBLISH", entity_type="BlockPlan", entity_id=plan_id, user_id="system", details=json.dumps({})))
    # notifications
    for dept in ["ENGINEERING","S_AND_T","TRACTION","PROJECTS","CONTROL_OFFICE"]:
        db.add(Notification(department=dept, plan_id=plan_id, message=f"Plan {plan_id} published", type="PUBLISH"))
    db.commit()
    return plan, "Published", 200
