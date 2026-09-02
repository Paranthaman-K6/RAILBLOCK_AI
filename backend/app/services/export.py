import csv, io, json
from sqlalchemy.orm import Session
from app.models import BlockPlan, Block, BlockTask, Task

def export_plan_csv(db: Session, plan_id: str):
    plan = db.query(BlockPlan).filter(BlockPlan.id==plan_id).first()
    if not plan:
        return None
    blocks = db.query(Block).filter(Block.plan_id==plan_id).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["plan_id","block_id","service_date","start_time","end_time","corridor_id","section_id","line_id","block_type","task_id","task_department","task_type","priority_score"])
    for blk in blocks:
        bts = db.query(BlockTask).filter(BlockTask.block_id==blk.id).all()
        for bt in bts:
            task = db.query(Task).filter(Task.id==bt.task_id).first()
            writer.writerow([plan.id, blk.id, blk.service_date, blk.start_time, blk.end_time, blk.corridor_id, blk.section_id or "", blk.line_id or "", blk.block_type, bt.task_id, task.department if task else "", task.task_type if task else "", task.priority_score if task else ""])
        if not bts:
            writer.writerow([plan.id, blk.id, blk.service_date, blk.start_time, blk.end_time, blk.corridor_id, blk.section_id or "", blk.line_id or "", blk.block_type, "","","",""])
    return output.getvalue()

def export_plan_pdf_text(db: Session, plan_id: str):
    # simple text for PDF placeholder
    csv_data = export_plan_csv(db, plan_id)
    return csv_data
