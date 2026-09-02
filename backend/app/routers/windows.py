from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import CandidateWindow
from app.services.candidate_windows import generate_candidate_windows

router = APIRouter(prefix="/api/windows", tags=["windows"])

@router.get("")
def list_windows(corridor_id: str = Query(None), service_date: str = Query(None), status: str = Query("FEASIBLE"), db: Session = Depends(get_db)):
    q = db.query(CandidateWindow)
    if corridor_id: q = q.filter(CandidateWindow.corridor_id==corridor_id.upper())
    if service_date: q = q.filter(CandidateWindow.service_date==service_date)
    if status: q = q.filter(CandidateWindow.status==status.upper())
    ws = q.all()
    return [{"window_id":w.id,"service_date":w.service_date,"corridor_id":w.corridor_id,"section_id":w.section_id,"line_id":w.line_id,"start_time":w.start_time,"end_time":w.end_time,"available_minutes":w.available_minutes,"block_type":w.block_type,"requires_power_isolation":w.requires_power_isolation,"requires_signal_disconnection":w.requires_signal_disconnection,"expected_train_count":w.expected_train_count,"goods_risk_score":w.goods_risk_score,"risk_band":w.risk_band,"status":w.status,"rejection_reason":w.rejection_reason,"availability_source":w.availability_source} for w in ws]

@router.get("/{window_id}")
def get_window(window_id: str, db: Session = Depends(get_db)):
    w = db.query(CandidateWindow).filter(CandidateWindow.id==window_id.upper()).first()
    if not w:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Window not found")
    return {"window_id":w.id,"service_date":w.service_date,"corridor_id":w.corridor_id,"section_id":w.section_id,"line_id":w.line_id,"start_time":w.start_time,"end_time":w.end_time,"available_minutes":w.available_minutes,"block_type":w.block_type,"goods_risk_score":w.goods_risk_score,"status":w.status}

@router.post("/generate")
def generate_windows(horizon_start: str, horizon_end: str, corridor_id: str = None, db: Session = Depends(get_db)):
    ws = generate_candidate_windows(db, horizon_start, horizon_end, corridors=[corridor_id.upper()] if corridor_id else None)
    return {"generated": len(ws), "horizon_start": horizon_start, "horizon_end": horizon_end}
