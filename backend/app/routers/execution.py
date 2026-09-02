from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel, Field
from typing import List, Optional
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.execution import record_execution, get_executions_for_plan, get_all_executions

class ExecutionRequest(BaseModel):
    actual_start: int = Field(..., description="Actual start minutes from midnight")
    actual_end: int = Field(..., description="Actual end minutes")
    status: str = Field(..., description="COMPLETED, PARTIALLY_COMPLETED, CANCELLED, DEFERRED")
    completed_task_ids: List[str] = Field(default_factory=list)
    partially_completed_task_ids: List[str] = Field(default_factory=list)
    cancelled_task_ids: List[str] = Field(default_factory=list)
    reason: Optional[str] = None
    asset_status: Optional[str] = None
    train_impact: Optional[str] = None
    notes: Optional[str] = None
    recorded_by: str = Field(..., description="Recorder")
    service_date: Optional[str] = Field(None, description="YYYY-MM-DD")

router = APIRouter(prefix="/api", tags=["execution"])

@router.post("/blocks/{block_id}/execution")
def execution_endpoint(block_id: str, payload: ExecutionRequest, db: Session = Depends(get_db)):
    rec, code = record_execution(db, block_id.upper(), payload.model_dump())
    return {"execution_id": rec.id, "block_id": rec.block_id, "status": rec.status, "actual_start": rec.actual_start, "actual_end": rec.actual_end, "code": code}

@router.get("/execution/plan/{plan_id}")
def get_by_plan(plan_id: str, db: Session = Depends(get_db)):
    exes = get_executions_for_plan(db, plan_id.upper())
    return [{"execution_id":e.id,"block_id":e.block_id,"plan_id":e.plan_id,"actual_start":e.actual_start,"actual_end":e.actual_end,"status":e.status,"recorded_by":e.recorded_by} for e in exes]

@router.get("/execution")
def get_all(db: Session = Depends(get_db)):
    exes = get_all_executions(db)
    return [{"execution_id":e.id,"block_id":e.block_id,"plan_id":e.plan_id,"status":e.status} for e in exes]

# deprecated alias
@router.post("/execution/{id}")
def deprecated_alias(id: str, payload: ExecutionRequest, db: Session = Depends(get_db)):
    try:
        rec, code = record_execution(db, id.upper(), payload.model_dump())
        return {"execution_id": rec.id, "status": rec.status}
    except HTTPException as e:
        raise e

# also need GET /api/execution alias for frontend? already
