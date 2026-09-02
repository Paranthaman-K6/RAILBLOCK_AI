from sqlalchemy.orm import Session
from app.models import BlockPlan, Block, BlockTask, Task, Notification

def get_approved_plans(db: Session, department: str = None):
    q = db.query(BlockPlan).filter(BlockPlan.status.in_(["APPROVED","PUBLISHED","SUPERSEDED"]))
    plans = q.all()
    return plans

def get_department_view(db: Session, plan_id: str, department: str):
    plan = db.query(BlockPlan).filter(BlockPlan.id==plan_id).first()
    if not plan:
        return None, "Plan not found"
    if plan.status not in ["APPROVED","PUBLISHED","SUPERSEDED"]:
        return None, "Draft plans must not appear in approved views"
    blocks = db.query(Block).filter(Block.plan_id==plan_id).all()
    # department sees its own tasks prominently, integrated tasks from other departments
    dept_blocks=[]
    integrated=[]
    for blk in blocks:
        bts = db.query(BlockTask).filter(BlockTask.block_id==blk.id).all()
        mine=False
        for bt in bts:
            task = db.query(Task).filter(Task.id==bt.task_id).first()
            if task and task.department==department:
                mine=True
                break
        if mine:
            dept_blocks.append(blk)
        else:
            # check if integrated: tasks from other departments but same corridor/date? For prototype, all other blocks are integrated context
            # only show if same corridor? We'll show all as integrated for demo
            integrated.append(blk)
    return {"plan": plan, "my_blocks": dept_blocks, "integrated_blocks": integrated, "all_blocks": blocks}, None

def get_notifications(db: Session, department: str):
    return db.query(Notification).filter(Notification.department==department).order_by(Notification.created_at.desc()).all()
