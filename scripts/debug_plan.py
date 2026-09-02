import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "backend"))
from app.database import SessionLocal
from app.models import Block, BlockTask, Task, CandidateWindow, TrainMovement
from app.services.plan_validator import validate_plan

db = SessionLocal()
# find latest plan
from app.models import BlockPlan
plans = db.query(BlockPlan).order_by(BlockPlan.created_at.desc()).limit(5).all()
for p in plans:
    print(f"\nPlan {p.id} status={p.status} solver={p.solver_status} {p.start_date}-{p.end_date}")
    val = validate_plan(db, p.id)
    print(" valid:", val["valid"])
    if not val["valid"]:
        for v in val["violations"]:
            print("  ", v)
    blocks = db.query(Block).filter(Block.plan_id==p.id).all()
    print(f" blocks={len(blocks)}")
    for b in blocks[:5]:
        w = db.query(CandidateWindow).filter(CandidateWindow.id==b.window_id).first() if b.window_id else None
        print(f"  Block {b.id} {b.service_date} {b.start_time}-{b.end_time} window {b.window_id} status {w.status if w else 'no window'} goods_risk {w.goods_risk_score if w else ''} trains {w.expected_train_count if w else ''}")
        # check trains overlapping
        trains = db.query(TrainMovement).filter(TrainMovement.corridor_id==b.corridor_id, TrainMovement.service_date==b.service_date).all()
        for t in trains:
            protected_start = t.departure_time - t.buffer_before
            protected_end = t.arrival_time + t.buffer_after
            overlap = not (b.end_time <= protected_start or b.start_time >= protected_end)
            if overlap:
                print(f"    -> overlaps train {t.id} {t.departure_time}-{t.arrival_time} buf {t.buffer_before}/{t.buffer_after} protected {protected_start}-{protected_end} line {t.line_id} vs block line {b.line_id}")

# also check candidate windows
print("\n=== Candidate windows sample ===")
cws = db.query(CandidateWindow).filter(CandidateWindow.status=="FEASIBLE").limit(10).all()
for w in cws:
    print(f" {w.id} {w.service_date} {w.start_time}-{w.end_time} cor {w.corridor_id} sec {w.section_id} line {w.line_id} status {w.status} trains {w.expected_train_count} goods {w.goods_risk_score}")

cws_rejected = db.query(CandidateWindow).filter(CandidateWindow.status=="REJECTED").limit(5).all()
for w in cws_rejected:
    print(f" REJECTED {w.id} {w.service_date} {w.start_time}-{w.end_time} reason {w.rejection_reason} trains {w.expected_train_count}")

db.close()
