from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.metrics import calculate_metrics, get_all_metrics

router = APIRouter(prefix="/api/metrics", tags=["metrics"])

@router.get("")
def all_metrics(db: Session = Depends(get_db)):
    # Instant metrics: no ThreadPool (pool_size 5 doubling caused 4s timeout on Render free)
    # Previous 4s guard still timed out on 10-plan loop (>30s). Now direct with small limit and skip validate.
    try:
        return get_all_metrics(db)
    except Exception as _e:
        # Fallback: latest single plan quickly
        try:
            from app.models import BlockPlan
            latest = db.query(BlockPlan).order_by(BlockPlan.created_at.desc()).first()
            if latest:
                m = calculate_metrics(db, latest.id)
                return [m] if m else []
        except Exception:
            pass
        return []

@router.get("/{plan_id}")
def one_metrics(plan_id: str, db: Session = Depends(get_db)):
    try:
        m = calculate_metrics(db, plan_id.upper())
    except Exception as _e:
        raise HTTPException(status_code=500, detail=str(_e)[:300])
    if not m:
        raise HTTPException(status_code=404, detail="Plan not found")
    return m
