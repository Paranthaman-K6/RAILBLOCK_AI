from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Task
from app.services.priority import compute_priority
import json

router = APIRouter(prefix="/api", tags=["tasks"])

@router.get("/tasks")
def list_tasks(department: str = Query(None), corridor: str = Query(None), severity: str = Query(None), status: str = Query(None), limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
    """Paginated, avoids SELECT * explosion - only selected columns via ORM but limited."""
    q = db.query(Task)
    if department: q = q.filter(Task.department==department.upper())
    if corridor: q = q.filter(Task.corridor_id==corridor.upper())
    if severity: q = q.filter(Task.severity==severity.upper())
    if status: q = q.filter(Task.status==status.upper())
    total = q.count()
    tasks = q.order_by(Task.priority_score.desc()).offset(offset).limit(limit).all()
    # Return with pagination metadata if requested via header? For backward compat, return list when no pagination params differ from defaults and no offset
    # But we include count in response header alternative - keep list for existing tests, add X-Total-Count style via envelope when limit < total
    result = [{"task_id":t.id,"source_system":t.source_system,"department":t.department,"asset_id":t.asset_id,"corridor_id":t.corridor_id,"section_id":t.section_id,"line_id":t.line_id,"task_type":t.task_type,"description":t.description,"severity":t.severity,"estimated_duration_minutes":t.estimated_duration_minutes,"requires_traffic_block":t.requires_traffic_block,"requires_power_isolation":t.requires_power_isolation,"requires_signal_disconnection":t.requires_signal_disconnection,"priority_score":t.priority_score,"priority_rank":t.priority_rank,"priority_band":t.priority_band,"priority_reason":t.priority_reason,"status":t.status,"deadline":t.deadline.isoformat() if t.deadline else None} for t in tasks]
    # If pagination requested explicitly (offset>0 or limit !=100), return envelope to avoid breaking existing tests that expect list
    if offset != 0 or limit != 100:
        return {"total": total, "limit": limit, "offset": offset, "tasks": result}
    return result

@router.get("/tasks/{task_id}/priority-explanation")
def priority_explanation(task_id: str, db: Session = Depends(get_db)):
    t = db.query(Task).filter(Task.id==task_id.upper()).first()
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    res = compute_priority(t)
    return {"task_id":t.id, "priority_score": res["priority_score"], "priority_rank": t.priority_rank, "priority_band": res["priority_band"], "factor_values": res["factor_values"], "factor_weights": res["factor_weights"], "priority_breakdown": res["priority_breakdown"], "priority_reason": res["priority_reason"], "rule_configuration_version": res["rule_configuration_version"]}

# corridors, assets etc here for simplicity
@router.get("/corridors")
def list_corridors(db: Session = Depends(get_db)):
    from app.models import Corridor
    return [{"corridor_id":c.id,"name":c.name} for c in db.query(Corridor).all()]

@router.get("/assets")
def list_assets(db: Session = Depends(get_db)):
    from app.models import Asset
    return [{"asset_id":a.id,"corridor_id":a.corridor_id,"asset_type":a.asset_type} for a in db.query(Asset).all()]

@router.get("/trains")
def list_trains(db: Session = Depends(get_db)):
    from app.models import TrainMovement
    return [{"train_id":t.id,"corridor_id":t.corridor_id,"service_date":t.service_date,"departure_time":t.departure_time,"arrival_time":t.arrival_time} for t in db.query(TrainMovement).all()]

@router.get("/resources")
def list_resources(db: Session = Depends(get_db)):
    from app.models import Resource
    return [{"resource_id":r.id,"resource_type":r.resource_type,"name":r.name} for r in db.query(Resource).all()]

@router.get("/departments")
def list_departments():
    return ["CONTROL_OFFICE","ENGINEERING","S_AND_T","TRACTION","PROJECTS","VIEWER","ADMIN"]
