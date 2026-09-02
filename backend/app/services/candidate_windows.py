import uuid, datetime
from sqlalchemy.orm import Session
from app.models import CandidateWindow, TrainMovement, GoodsForecast, ResourceAvailability
from collections import defaultdict

# Synthetic prototype windows templates
TEMPLATES = [
    (60, 180),    # 01:00-03:00
    (810, 930),   # 13:30-15:30
    (120, 360),   # 02:00-06:00
]

# Interval overlap rule (explicit, documented):
# overlap = train_start < block_end and train_end > block_start
# where train interval is protected [departure-buffer_before, arrival+buffer_after)
# Exact boundary: if window_end == protected_start -> NO overlap
#                 if window_start == protected_end -> NO overlap
# Tests: train at block start (protected_start == block_start -> no overlap if block_end==protected_start, else overlap)
#        train at block end -> no overlap if protected_end == window_start
#        overlapping by one minute -> overlap

def _overlap(a_start, a_end, b_start, b_end):
    """Shared interval rule: a [s,e) overlaps b [s,e) iff a_start < b_end and a_end > b_start"""
    return a_start < b_end and a_end > b_start

def generate_candidate_windows(db: Session, horizon_start: str, horizon_end: str, corridors=None, max_block_minutes=240, min_buffer=15):
    """Idempotent, bulk conflict lookups, rejects train overlap via consistent interval rule."""
    try:
        start_dt = datetime.datetime.strptime(horizon_start, "%Y-%m-%d")
        end_dt = datetime.datetime.strptime(horizon_end, "%Y-%m-%d")
    except:
        start_dt = datetime.datetime.utcnow()
        end_dt = start_dt + datetime.timedelta(days=7)
    windows=[]
    from app.models import Corridor, Section, Line
    if corridors:
        cor_ids = corridors
    else:
        cor_ids = [c.id for c in db.query(Corridor).all()]
        if not cor_ids:
            cor_ids=["COR-1"]
    delta = (end_dt - start_dt).days
    # Bulk pre-fetch trains and goods for horizon to avoid N+1
    # Build maps: (corridor_id, service_date) -> list
    train_map = defaultdict(list)
    trains_all = db.query(TrainMovement).filter(TrainMovement.service_date.between(horizon_start, horizon_end)).all()
    for t in trains_all:
        train_map[(t.corridor_id, t.service_date)].append(t)
    goods_map = defaultdict(list)
    goods_all = db.query(GoodsForecast).filter(GoodsForecast.service_date.between(horizon_start, horizon_end)).all()
    for g in goods_all:
        goods_map[(g.corridor_id, g.service_date)].append(g)
    # Also pre-fetch existing windows for idempotent check as set
    existing_windows_q = db.query(CandidateWindow).filter(CandidateWindow.service_date.between(horizon_start, horizon_end))
    if corridors:
        existing_windows_q = existing_windows_q.filter(CandidateWindow.corridor_id.in_(corridors))
    existing_map = {}
    for w in existing_windows_q.all():
        key = (w.corridor_id, w.section_id, w.line_id, w.service_date, w.start_time, w.end_time)
        existing_map[key] = w
    for day_offset in range(delta+1):
        service_date = (start_dt + datetime.timedelta(days=day_offset)).strftime("%Y-%m-%d")
        for cor in cor_ids:
            sections = db.query(Section).filter(Section.corridor_id==cor).all()
            if not sections:
                sections = [None]
            for sec in sections:
                sec_id = sec.id if sec else None
                if sec:
                    lines = db.query(Line).filter(Line.section_id==sec.id).all()
                else:
                    lines = db.query(Line).filter(Line.corridor_id==cor).all()
                if not lines:
                    lines=[None]
                for lin in lines:
                    lin_id = lin.id if lin else None
                    for (s,e) in TEMPLATES:
                        dur = e - s
                        if dur > max_block_minutes:
                            continue
                        key = (cor, sec_id, lin_id, service_date, s, e)
                        existing = existing_map.get(key)
                        # Bulk lookup trains/goods for this corridor/date
                        trains = train_map.get((cor, service_date), [])
                        goods = goods_map.get((cor, service_date), [])
                        expected=0
                        hard=False
                        goods_risk=0
                        # Filter by section/line and compute overlap using documented rule
                        for t in trains:
                            if lin_id and t.line_id and t.line_id != lin_id:
                                continue
                            if sec_id and t.section_id and t.section_id != sec_id:
                                continue
                            protected_start = t.departure_time - t.buffer_before
                            protected_end = t.arrival_time + t.buffer_after
                            if _overlap(s, e, protected_start, protected_end):
                                hard=True
                                expected+=1
                        for g in goods:
                            if lin_id and g.line_id and g.line_id != lin_id:
                                continue
                            if sec_id and g.section_id and g.section_id != sec_id:
                                continue
                            if _overlap(s, e, g.start_time, g.end_time):
                                goods_risk = max(goods_risk, g.confidence*100)
                                if g.confidence >= 0.7:
                                    hard=True
                        status="FEASIBLE" if not hard else "REJECTED"
                        rejection=None
                        if goods_risk>=70:
                            status="REJECTED"
                            rejection="Goods forecast high confidence overlap"
                        elif hard and expected>0:
                            status="REJECTED"
                            rejection=f"Train overlap {expected} trains"
                        risk_band="HIGH" if goods_risk>70 else "MEDIUM" if goods_risk>40 else "LOW"
                        if existing:
                            existing.expected_train_count=expected
                            existing.goods_risk_score=goods_risk
                            existing.risk_band=risk_band
                            existing.status=status
                            existing.rejection_reason=rejection
                            continue
                        wid = f"WND-{str(uuid.uuid4())[:8].upper()}"
                        cw = CandidateWindow(
                            id=wid,
                            service_date=service_date,
                            corridor_id=cor,
                            section_id=sec_id,
                            line_id=lin_id,
                            start_time=s,
                            end_time=e,
                            available_minutes=dur,
                            block_type="TRAFFIC",
                            requires_power_isolation=False,
                            requires_signal_disconnection=False,
                            expected_train_count=expected,
                            goods_risk_score=goods_risk,
                            risk_band=risk_band,
                            availability_source="Synthetic prototype windows, not official railway availability.",
                            rejection_reason=rejection,
                            status=status
                        )
                        windows.append(cw)
    for w in windows:
        db.add(w)
    db.commit()
    # Return all windows in horizon (including updated existing)
    return db.query(CandidateWindow).filter(CandidateWindow.service_date.between(horizon_start, horizon_end)).all() if corridors is None else windows

def get_feasible_windows(db, corridor_id=None, section_id=None, line_id=None, service_date=None):
    q=db.query(CandidateWindow).filter(CandidateWindow.status=="FEASIBLE")
    if corridor_id: q=q.filter(CandidateWindow.corridor_id==corridor_id)
    if section_id: q=q.filter(CandidateWindow.section_id==section_id)
    if line_id: q=q.filter(CandidateWindow.line_id==line_id)
    if service_date: q=q.filter(CandidateWindow.service_date==service_date)
    return q.all()
