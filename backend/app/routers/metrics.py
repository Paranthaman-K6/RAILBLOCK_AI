from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.metrics import calculate_metrics, get_all_metrics

router = APIRouter(prefix="/api/metrics", tags=["metrics"])

@router.get("")
def all_metrics(db: Session = Depends(get_db)):
    return get_all_metrics(db)

@router.get("/{plan_id}")
def one_metrics(plan_id: str, db: Session = Depends(get_db)):
    m = calculate_metrics(db, plan_id.upper())
    if not m:
        raise HTTPException(status_code=404, detail="Plan not found")
    return m
