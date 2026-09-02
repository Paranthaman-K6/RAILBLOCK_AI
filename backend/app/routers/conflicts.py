from fastapi import APIRouter, Depends, Body
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.compatibility import check_task_window_fit, check_compatible
from app.models import Task, CandidateWindow

router = APIRouter(prefix="/api/conflicts", tags=["conflicts"])

@router.post("/detect")
def detect(payload: dict = Body(...), db: Session = Depends(get_db)):
    task_id = payload.get("task_id")
    window_id = payload.get("window_id")
    task2_id = payload.get("task2_id")
    # detect task-window or task-task
    if task_id and window_id:
        task = db.query(Task).filter(Task.id==task_id.upper()).first()
        window = db.query(CandidateWindow).filter(CandidateWindow.id==window_id.upper()).first()
        if not task or not window:
            return {"compatible": False, "reasons":["Task or window not found"]}
        fit, reason = check_task_window_fit(task, window)
        return {"task_id":task_id, "window_id":window_id, "feasibility": fit, "reason": reason, "compatible": fit!="HARD_CONFLICT", "reasons":[reason]}
    if task_id and task2_id:
        t1 = db.query(Task).filter(Task.id==task_id.upper()).first()
        t2 = db.query(Task).filter(Task.id==task2_id.upper()).first()
        if not t1 or not t2:
            return {"compatible": False, "reasons":["Task not found"]}
        res = check_compatible(t1,t2)
        return res
    return {"compatible": True, "reasons":[]}

@router.post("")
def alias_detect(payload: dict = Body(...), db: Session = Depends(get_db)):
    return detect(payload, db)
