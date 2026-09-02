from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import BlockPlan, Block, BlockTask, Task, CandidateWindow
from app.services.candidate_windows import generate_candidate_windows
from app.services.priority import recalculate_all
from app.services.baseline import generate_baseline_plan
from app.services.optimizer import run_cpsat_optimizer
from app.services.fallback import generate_fallback_plan
from app.services.plan_validator import validate_plan
from app.services.revisions import create_revision, edit_draft_block
from app.services.approvals import approve_plan, reject_plan, publish_plan
import json, uuid, datetime

router = APIRouter(prefix="/api/plans", tags=["plans"])

@router.post("/generate")
def generate_plan(payload: dict = Body(...), db: Session = Depends(get_db)):
    # payload: horizon_start, horizon_end, horizon_type (WEEKLY/MONTHLY), corridors, sections, lines, planning_mode, optimize
    horizon_start = payload.get("horizon_start") or payload.get("start_date") or "2026-09-01"
    horizon_end = payload.get("horizon_end") or payload.get("end_date") or "2026-09-07"
    horizon_type = payload.get("horizon_type") or payload.get("mode") or "WEEKLY"
    ht = horizon_type.upper()
    if ht in ["WEEKLY","MONTHLY","DAILY","DAY_WISE","DAYWISE"]:
        if ht in ["DAY_WISE","DAYWISE"]:
            ht = "DAILY"
        horizon_type = ht
    else:
        if "week" in horizon_type.lower():
            horizon_type = "WEEKLY"
        elif "day" in horizon_type.lower():
            horizon_type = "DAILY"
        else:
            horizon_type = "MONTHLY"
    corridors = payload.get("corridors")  # list of COR-*
    # validate data exists
    from app.models import Task
    if db.query(Task).count()==0:
        raise HTTPException(status_code=400, detail="No data -> no plan. Import tasks first.")
    # also need candidate windows, but generate if none
    # recalc priorities
    recalculate_all(db)
    # generate windows - always refresh for horizon to ensure FEASIBLE/REJECTED is up-to-date (idempotent, bulk, avoids stale 400 TRAIN_CONFLICT)
    # Previous bug: only generated when FEASIBLE count==0, leaving stale FEASIBLE windows that should be REJECTED after train/goods update.
    generate_candidate_windows(db, horizon_start, horizon_end, corridors=corridors)
    # create baseline
    baseline = generate_baseline_plan(db, horizon_start, horizon_end, horizon_type=horizon_type.upper(), corridors=corridors)
    # try optimized
    opt_plan, solver_status, objective_breakdown, runtime = run_cpsat_optimizer(db, horizon_start, horizon_end, horizon_type=horizon_type.upper(), time_limit=5)
    chosen_plan = opt_plan if opt_plan else None
    if not opt_plan:
        # fallback
        fallback = generate_fallback_plan(db, horizon_start, horizon_end, horizon_type=horizon_type.upper())
        # fallback is already persisted as plan, but we have baseline also; we need to decide which is draft
        # If fallback, validate
        val = validate_plan(db, fallback.id)
        if not val["valid"]:
            # invalid solver output is rejected, but fallback is validated; if still invalid, don't save as valid plan
            fallback.solver_status="VALIDATION_FAILED"
            db.commit()
            raise HTTPException(status_code=400, detail=f"Generated plan validation failed: {val['violations']}")
        # choose fallback as draft, keep baseline for metrics comparison
        chosen_plan = fallback
        # copy baseline metrics to chosen
        chosen_plan.baseline_metrics = baseline.baseline_metrics
        db.commit()
        solver_status = "FALLBACK_USED"
        objective_breakdown = json.loads(chosen_plan.objective_breakdown) if chosen_plan.objective_breakdown else {}
        runtime = 0
    else:
        # validate optimized
        val = validate_plan(db, opt_plan.id)
        if not val["valid"]:
            # try fallback
            fallback = generate_fallback_plan(db, horizon_start, horizon_end, horizon_type=horizon_type.upper())
            val2 = validate_plan(db, fallback.id)
            if not val2["valid"]:
                raise HTTPException(status_code=400, detail=f"Invalid solver output is rejected: {val['violations']}")
            chosen_plan = fallback
            chosen_plan.baseline_metrics = baseline.baseline_metrics
            db.commit()
            solver_status="FALLBACK_USED"
            val=val2
        else:
            # attach baseline metrics to optimized plan for comparison
            chosen_plan.baseline_metrics = baseline.baseline_metrics
            db.commit()
    # ensure chosen plan has objective breakdown and metrics
    val_final = validate_plan(db, chosen_plan.id)
    if not val_final["valid"]:
        raise HTTPException(status_code=400, detail=f"Plan validation failed: {val_final['violations']}")
    # return draft plan details
    blocks = db.query(Block).filter(Block.plan_id==chosen_plan.id).all()
    return {
        "plan_id": chosen_plan.id,
        "horizon_type": chosen_plan.horizon_type,
        "start_date": chosen_plan.start_date,
        "end_date": chosen_plan.end_date,
        "status": chosen_plan.status,
        "solver_status": chosen_plan.solver_status if chosen_plan.solver_status else solver_status,
        "runtime_seconds": runtime,
        "objective_breakdown": json.loads(chosen_plan.objective_breakdown) if chosen_plan.objective_breakdown else objective_breakdown,
        "baseline_metrics": json.loads(chosen_plan.baseline_metrics) if chosen_plan.baseline_metrics else {},
        "optimized_metrics": json.loads(chosen_plan.optimized_metrics) if chosen_plan.optimized_metrics else {},
        "unscheduled_reasons": json.loads(chosen_plan.unscheduled_reasons) if chosen_plan.unscheduled_reasons else [],
        "validation": val_final,
        "blocks": [{"block_id":b.id,"service_date":b.service_date,"start_time":b.start_time,"end_time":b.end_time,"corridor_id":b.corridor_id,"section_id":b.section_id,"line_id":b.line_id,"block_type":b.block_type,"status":b.status,"tasks": [bt.task_id for bt in db.query(BlockTask).filter(BlockTask.block_id==b.id).all()]} for b in blocks]
    }

@router.get("")
def list_plans(status: str = Query(None), db: Session = Depends(get_db)):
    q = db.query(BlockPlan)
    if status: q = q.filter(BlockPlan.status==status.upper())
    plans = q.order_by(BlockPlan.created_at.desc()).all()
    return [{"plan_id":p.id,"horizon_type":p.horizon_type,"start_date":p.start_date,"end_date":p.end_date,"status":p.status,"solver_status":p.solver_status,"created_at":p.created_at.isoformat() if p.created_at else None,"version":p.version} for p in plans]

@router.get("/{plan_id}")
def get_plan(plan_id: str, db: Session = Depends(get_db)):
    p = db.query(BlockPlan).filter(BlockPlan.id==plan_id.upper()).first()
    if not p:
        raise HTTPException(status_code=404, detail="Plan not found")
    blocks = db.query(Block).filter(Block.plan_id==p.id).all()
    # Department approvals - unambiguous: required vs approved
    from app.models import Approval, BlockTask, Task
    approvals = db.query(Approval).filter(Approval.plan_id==p.id, Approval.decision=="APPROVED").all()
    approved_roles = sorted(set(a.approver_role for a in approvals))
    # Required depts = distinct departments from tasks in plan
    required_depts = set()
    for b in blocks:
        for bt in db.query(BlockTask).filter(BlockTask.block_id==b.id).all():
            t = db.query(Task).filter(Task.id==bt.task_id).first()
            if t and t.department:
                required_depts.add(t.department)
    # Also include block.department comma-separated as fallback
    if not required_depts:
        for b in blocks:
            if b.department:
                for d in b.department.split(","):
                    if d.strip():
                        required_depts.add(d.strip())
    required_depts = sorted(required_depts)
    pending_depts = sorted(set(required_depts) - set(approved_roles)) if p.status!="APPROVED" else []
    # If APPROVED, pending empty, but still show who approved
    return {"plan_id":p.id,"horizon_type":p.horizon_type,"start_date":p.start_date,"end_date":p.end_date,"status":p.status,"solver_status":p.solver_status,"baseline_metrics": json.loads(p.baseline_metrics) if p.baseline_metrics else {},"optimized_metrics": json.loads(p.optimized_metrics) if p.optimized_metrics else {},"objective_breakdown": json.loads(p.objective_breakdown) if p.objective_breakdown else {},"unscheduled_reasons": json.loads(p.unscheduled_reasons) if p.unscheduled_reasons else [],"blocks": [{"block_id":b.id,"service_date":b.service_date,"start_time":b.start_time,"end_time":b.end_time,"corridor_id":b.corridor_id,"section_id":b.section_id,"line_id":b.line_id,"block_type":b.block_type,"status":b.status,"department":b.department,"window_id":b.window_id,"tasks": [{"task_id":bt.task_id,"status":bt.status, "department": (db.query(Task).filter(Task.id==bt.task_id).first().department if db.query(Task).filter(Task.id==bt.task_id).first() else None)} for bt in db.query(BlockTask).filter(BlockTask.block_id==b.id).all()]} for b in blocks],"validation": validate_plan(db, p.id), "approvals": [{"approver_id":a.approver_id,"approver_role":a.approver_role,"reason":a.reason,"created_at":a.created_at.isoformat() if a.created_at else None} for a in approvals], "required_departments": required_depts, "approved_departments": approved_roles, "pending_departments": pending_depts}

@router.post("/{plan_id}/validate")
def validate_endpoint(plan_id: str, db: Session = Depends(get_db)):
    res = validate_plan(db, plan_id.upper())
    if res["valid"]:
        return {"valid":True,"violations":[]}
    return {"valid":False,"violations": res["violations"]}

@router.post("/{plan_id}/approve")
def approve_endpoint(plan_id: str, payload: dict = Body(None), db: Session = Depends(get_db)):
    # Explicit actor required - no silent fallback for empty
    if payload is None or not isinstance(payload, dict):
        raise HTTPException(status_code=401, detail="Approval requires valid actor context")
    # Check for missing keys explicitly (not fallback to officer1)
    if "approver_id" not in payload and "user_id" not in payload:
        raise HTTPException(status_code=401, detail="Approval requires approver_id")
    if "approver_role" not in payload and "role" not in payload and "department" not in payload:
        raise HTTPException(status_code=401, detail="Approval requires approver_role")
    approver_id = payload.get("approver_id") or payload.get("user_id")
    approver_role = payload.get("approver_role") or payload.get("role") or payload.get("department")
    # Empty string is unauthorized
    if not approver_id or not str(approver_id).strip():
        raise HTTPException(status_code=401, detail="Approver identity required")
    if not approver_role or not str(approver_role).strip():
        raise HTTPException(status_code=401, detail="Approver role required")
    reason = payload.get("reason") or "Approved"
    plan, msg, code = approve_plan(db, plan_id.upper(), str(approver_id).strip(), str(approver_role).strip(), reason)
    if code !=200:
        raise HTTPException(status_code=code, detail=msg)
    return {"plan_id": plan.id, "status": plan.status, "message": msg}

@router.post("/{plan_id}/reject")
def reject_endpoint(plan_id: str, payload: dict = Body(...), db: Session = Depends(get_db)):
    reason = payload.get("reason") if payload else None
    approver_id = payload.get("approver_id") if payload else "officer1"
    if not reason:
        raise HTTPException(status_code=400, detail="Rejection requires reason")
    plan, msg, code = reject_plan(db, plan_id.upper(), approver_id, reason)
    if code!=200:
        raise HTTPException(status_code=code, detail=msg)
    return {"plan_id": plan.id, "status": plan.status}

@router.post("/{plan_id}/replan")
def replan_endpoint(plan_id: str, payload: dict = Body(None), db: Session = Depends(get_db)):
    payload = payload or {}
    reason = payload.get("reason") or "Emergency replanning"
    horizon_type = payload.get("horizon_type")
    from app.services.replanning import trigger_replan
    result, msg, code = trigger_replan(db, plan_id.upper(), reason=reason, horizon_type=horizon_type)
    if code!=200:
        raise HTTPException(status_code=code, detail=result if isinstance(result,str) else msg)
    return result

@router.get("/{plan_id}/history")
def history_endpoint(plan_id: str, db: Session = Depends(get_db)):
    from app.services.revisions import get_history
    from app.models import AuditEvent, PlanRevision
    plan = db.query(BlockPlan).filter(BlockPlan.id==plan_id.upper()).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    revs = db.query(PlanRevision).filter((PlanRevision.base_plan_id==plan.id) | (PlanRevision.new_plan_id==plan.id)).all()
    audits = db.query(AuditEvent).filter(AuditEvent.entity_id==plan.id).all()
    # also include all audits for blocks of this plan
    block_ids = [b.id for b in db.query(Block).filter(Block.plan_id==plan.id).all()]
    block_audits = db.query(AuditEvent).filter(AuditEvent.entity_id.in_(block_ids)).all() if block_ids else []
    return {"plan_id": plan.id, "revisions": [{"revision_id":r.id,"base_plan_id":r.base_plan_id,"new_plan_id":r.new_plan_id,"revision_number":r.revision_number,"reason":r.reason,"created_at":r.created_at.isoformat() if r.created_at else None} for r in revs], "audits": [{"action":a.action,"entity_id":a.entity_id,"user_id":a.user_id,"created_at":a.created_at.isoformat() if a.created_at else None,"details":a.details} for a in audits+block_audits]}

@router.get("/{plan_id}/changes")
def changes_endpoint(plan_id: str, db: Session = Depends(get_db)):
    from app.services.revisions import get_changes
    changes = get_changes(db, plan_id.upper())
    return [{"change_type":c.change_type,"block_id":c.block_id,"task_id":c.task_id,"old_value":c.old_value,"new_value":c.new_value,"reason":c.reason} for c in changes]

@router.get("/{plan_id}/export")
def export_endpoint(plan_id: str, format: str = Query("csv"), db: Session = Depends(get_db)):
    from app.services.export import export_plan_csv
    from fastapi.responses import PlainTextResponse
    csv_data = export_plan_csv(db, plan_id.upper())
    if csv_data is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    if format=="pdf":
        return PlainTextResponse(csv_data, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename={plan_id}.pdf"})
    return PlainTextResponse(csv_data, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={plan_id}.csv"})

@router.post("/{plan_id}/revisions")
def create_revision_endpoint(plan_id: str, payload: dict = Body(...), db: Session = Depends(get_db)):
    reason = payload.get("reason") or payload.get("change_reason") or "Revision"
    editor = payload.get("editor") or payload.get("user_id") or "demo_user"
    # check stale: if If-Match header simulated via payload version?
    # For spec: stale revision returns 409 - we check if plan version matches expected
    expected_version = payload.get("expected_version") or payload.get("version")
    plan = db.query(BlockPlan).filter(BlockPlan.id==plan_id.upper()).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    if expected_version and int(expected_version) != plan.version:
        raise HTTPException(status_code=409, detail="Stale revision: version mismatch")
    new_plan, rev, code = create_revision(db, plan_id.upper(), reason, editor)
    if code!=200:
        raise HTTPException(status_code=code, detail=new_plan if isinstance(new_plan,str) else "Error")
    return {"base_plan_id": plan_id.upper(), "new_plan_id": new_plan.id, "revision_id": rev.id, "revision_number": rev.revision_number, "status": new_plan.status}

@router.patch("/{plan_id}/draft-blocks/{block_id}")
def edit_block_endpoint(plan_id: str, block_id: str, payload: dict = Body(...), db: Session = Depends(get_db)):
    # payload may contain service_date, start_time, end_time, reason, editor
    reason = payload.pop("reason", "Edit") or payload.pop("change_reason", "Edit") 
    editor = payload.pop("editor", "demo_user") or payload.pop("user_id","demo_user")
    # payload remaining is block fields
    block, msg, code = edit_draft_block(db, plan_id.upper(), block_id.upper(), payload, editor=editor, reason=reason)
    if code!=200:
        raise HTTPException(status_code=code, detail=msg)
    return {"block_id": block.id, "message": msg, "block": {"block_id":block.id,"service_date":block.service_date,"start_time":block.start_time,"end_time":block.end_time}}

@router.post("/{plan_id}/submit-review")
def submit_review(plan_id: str, db: Session = Depends(get_db)):
    plan = db.query(BlockPlan).filter(BlockPlan.id==plan_id.upper()).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    if plan.status != "DRAFT":
        raise HTTPException(status_code=400, detail="Only DRAFT can be submitted")
    val = validate_plan(db, plan.id)
    if not val["valid"]:
        raise HTTPException(status_code=400, detail=f"Validation failed: {val['violations']}")
    plan.status="UNDER_REVIEW"
    for b in db.query(Block).filter(Block.plan_id==plan.id).all():
        b.status="UNDER_REVIEW"
    from app.models import AuditEvent
    import json, datetime
    db.add(AuditEvent(action="SUBMIT_REVIEW", entity_type="BlockPlan", entity_id=plan.id, user_id="demo_user", details=json.dumps({})))
    db.commit()
    return {"plan_id": plan.id, "status": plan.status}

# additional endpoint POST /api/optimize alias
@router.post("/../optimize")
def optimize_alias(payload: dict = Body(...), db: Session = Depends(get_db)):
    return generate_plan(payload, db)
