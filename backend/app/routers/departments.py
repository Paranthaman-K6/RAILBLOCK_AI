from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.visibility import get_approved_plans, get_department_view, get_notifications

router = APIRouter(prefix="/api", tags=["departments"])

@router.get("/approved-plans")
def approved_plans(department: str = Query(None), db: Session = Depends(get_db)):
    plans = get_approved_plans(db, department)
    # filter if department provided? Still return all approved but visibility will show per dept
    return [{"plan_id":p.id,"horizon_type":p.horizon_type,"start_date":p.start_date,"end_date":p.end_date,"status":p.status,"solver_status":p.solver_status} for p in plans]

@router.get("/plans/{plan_id}/department-view")
def dept_view(plan_id: str, department: str = Query(...), db: Session = Depends(get_db)):
    dept = department.upper()
    result, err = get_department_view(db, plan_id.upper(), dept)
    if err:
        raise HTTPException(status_code=400, detail=err)
    plan = result["plan"]
    my_blocks = result["my_blocks"]
    integrated = result["integrated_blocks"]
    # include block details
    def blk_to_dict(b):
        from app.models import BlockTask, Task
        bts = db.query(BlockTask).filter(BlockTask.block_id==b.id).all()
        tasks=[]
        for bt in bts:
            t = db.query(Task).filter(Task.id==bt.task_id).first()
            if t:
                tasks.append({"task_id":t.id,"department":t.department,"task_type":t.task_type,"description":t.description,"priority_score":t.priority_score})
        return {"block_id":b.id,"service_date":b.service_date,"start_time":b.start_time,"end_time":b.end_time,"corridor_id":b.corridor_id,"section_id":b.section_id,"line_id":b.line_id,"block_type":b.block_type,"requires_power_isolation":b.requires_power_isolation,"requires_signal_disconnection":b.requires_signal_disconnection,"status":b.status,"tasks":tasks}
    return {"plan_id": plan.id, "department": dept, "plan_status": plan.status, "my_blocks": [blk_to_dict(b) for b in my_blocks], "integrated_blocks": [blk_to_dict(b) for b in integrated], "change_history": [], "approval_history": []}

@router.get("/notifications")
def notifications(department: str = Query(...), db: Session = Depends(get_db)):
    notes = get_notifications(db, department.upper())
    return [{"id":n.id,"department":n.department,"plan_id":n.plan_id,"message":n.message,"type":n.type,"created_at":n.created_at.isoformat() if n.created_at else None} for n in notes]
