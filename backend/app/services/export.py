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

def export_plan_pdf(db: Session, plan_id: str) -> bytes | None:
    """Generate a real PDF bytes for a plan — blocks and tasks table"""
    plan = db.query(BlockPlan).filter(BlockPlan.id==plan_id).first()
    if not plan:
        return None
    blocks = db.query(Block).filter(Block.plan_id==plan_id).all()
    # Build PDF content as simple text-based PDF (no external deps)
    # Use minimal PDF 1.4 structure with Helvetica
    import io
    buf = io.BytesIO()
    # PDF header
    buf.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    def write_obj(num, data: bytes):
        offsets.append(buf.tell())
        buf.write(f"{num} 0 obj\n".encode())
        buf.write(data)
        buf.write(b"\nendobj\n")
    # Page content stream
    lines = []
    lines.append(f"RailBlock AI - Plan {plan.id}")
    lines.append(f"Horizon: {plan.start_date} -> {plan.end_date}  Type: {plan.horizon_type}  Status: {plan.status}  Solver: {plan.solver_status}")
    lines.append(f"Blocks: {len(blocks)}")
    lines.append("")
    lines.append("Blocks and Tasks:")
    lines.append("plan_id,block_id,service_date,start-end,corridor,section,line,block_type,task_id,dept,type,priority")
    for blk in blocks:
        bts = db.query(BlockTask).filter(BlockTask.block_id==blk.id).all()
        st = f"{blk.start_time:04d}-{blk.end_time:04d}"
        for bt in bts:
            task = db.query(Task).filter(Task.id==bt.task_id).first()
            dept = task.department if task else ""
            ttype = task.task_type if task else ""
            pri = str(task.priority_score) if task and task.priority_score is not None else ""
            lines.append(f"{plan.id},{blk.id},{blk.service_date},{st},{blk.corridor_id},{blk.section_id or ''},{blk.line_id or ''},{blk.block_type},{bt.task_id},{dept},{ttype},{pri}")
        if not bts:
            lines.append(f"{plan.id},{blk.id},{blk.service_date},{st},{blk.corridor_id},{blk.section_id or ''},{blk.line_id or ''},{blk.block_type},,,,")
    # Build text stream with line breaks and page breaks every 45 lines
    text_stream = ""
    y = 800
    count = 0
    for i, line in enumerate(lines):
        # Escape parentheses
        esc = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        if count % 45 == 0 and count != 0:
            text_stream += "ET\nBT\n/F1 7 Tf\n"
            y = 800
        if count % 45 == 0:
            text_stream += "BT\n/F1 7 Tf\n"
        text_stream += f"1 0 0 1 40 {y} Tm ({esc}) Tj\n"
        y -= 12
        count += 1
        if y < 40:
            text_stream += "ET\n"
            y = 800
            text_stream += "BT\n/F1 7 Tf\n"
    text_stream += "ET\n"
    stream_bytes = text_stream.encode("latin-1", errors="ignore")
    # Objects: 1 Catalog, 2 Pages, 3 Page, 4 Font, 5 Content
    write_obj(1, b"<< /Type /Catalog /Pages 2 0 R >>")
    write_obj(2, b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    # Resources with Font
    write_obj(3, b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> /Contents 5 0 R >>")
    write_obj(4, b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    # Content stream
    content = f"<< /Length {len(stream_bytes)} >>\nstream\n".encode() + stream_bytes + b"\nendstream"
    write_obj(5, content)
    # xref
    xref_offset = buf.tell()
    buf.write(f"xref\n0 6\n0000000000 65535 f \n".encode())
    for off in offsets:
        buf.write(f"{off:010d} 00000 n \n".encode())
    buf.write(f"trailer << /Size 6 /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF".encode())
    return buf.getvalue()

def export_plan_pdf_text(db: Session, plan_id: str):
    # legacy placeholder kept for backwards compat
    csv_data = export_plan_csv(db, plan_id)
    return csv_data
