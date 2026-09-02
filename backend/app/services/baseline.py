import uuid, json, datetime
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.models import Task, CandidateWindow, BlockPlan, Block, BlockTask
from app.services.compatibility import check_task_window_fit
from app.services.priority import recalculate_all

def generate_baseline_plan(db: Session, horizon_start: str, horizon_end: str, horizon_type="WEEKLY", corridors=None):
    # Sort tasks by priority or arrival (id)
    tasks = db.query(Task).filter(Task.status=="ELIGIBLE").all()
    # ensure priorities calculated
    recalculate_all(db)
    tasks = db.query(Task).filter(Task.status=="ELIGIBLE").all()
    tasks_sorted = sorted(tasks, key=lambda t: (-(t.priority_score or 0), t.id))
    windows = db.query(CandidateWindow).filter(CandidateWindow.status=="FEASIBLE").all()
    # sort windows by date/time
    windows_sorted = sorted(windows, key=lambda w: (w.service_date, w.start_time))
    # simple FCFS: assign first feasible window, avoid hard conflicts, avoid resource conflicts, no intentional grouping
    used_windows=set()
    used_resources=set()  # (resource_id, date, start,end)
    plan_id=f"PLAN-{str(uuid.uuid4())[:8].upper()}"
    plan = BlockPlan(id=plan_id, horizon_type=horizon_type, start_date=horizon_start, end_date=horizon_end, status="DRAFT", solver_status="FEASIBLE", created_at=datetime.datetime.utcnow(), version=1)
    db.add(plan)
    db.flush()
    scheduled=[]
    unscheduled=[]
    block_map={}  # window_id -> Block
    # resource tracking per window
    resource_usage = {}  # (date, resource_id) -> window_id
    for task in tasks_sorted:
        assigned=None
        # get required resources for task
        # query task_resources
        res_rows = db.execute(text(f"SELECT resource_id FROM task_resources WHERE task_id='{task.id}'")).fetchall() if task.id else []
        req_res = [r[0] for r in res_rows]
        for w in windows_sorted:
            # check corridor/date already?
            # avoid reusing same window for multiple tasks? Baseline creates no intentional groups, so one task per block/window
            if w.id in used_windows:
                continue
            # check fit
            fit, reason = check_task_window_fit(task, w)
            if fit=="HARD_CONFLICT":
                continue
            # resource conflict: if any required resource already used on same date overlapping time (simplified: same date)
            conflict=False
            for rid in req_res:
                key = (w.service_date, rid)
                if key in resource_usage:
                    conflict=True
                    break
            if conflict:
                continue
            # also check train conflict already in window status
            # deadline check
            if task.deadline:
                try:
                    dl_date = task.deadline.strftime("%Y-%m-%d") if isinstance(task.deadline, datetime.datetime) else str(task.deadline)
                    if w.service_date > dl_date:
                        continue
                except:
                    pass
            # dependency ordering: ensure depends_on tasks scheduled earlier
            deps = db.query(text("SELECT depends_on_task_id FROM task_dependencies WHERE task_id=:tid")).params(tid=task.id).fetchall() if False else []
            # use ORM
            from app.models import TaskDependency
            deps = db.query(TaskDependency).filter(TaskDependency.task_id==task.id).all()
            dep_ok=True
            for d in deps:
                # check if dependency is scheduled earlier date/time
                # find block for dependency
                dep_scheduled = any(bt.task_id==d.depends_on_task_id for bt in db.query(BlockTask).join(Block, Block.id==BlockTask.block_id).filter(Block.plan_id==plan_id).all())
                if not dep_scheduled:
                    # if dependency not yet scheduled, postpone this task
                    dep_ok=False
                    break
                # also need to ensure window date >= dependency window date (simplified, check scheduled list)
                # find dep block date
                # skip detailed
            if not dep_ok:
                continue
            assigned=w
            break
        if assigned:
            # create block for this task (one block per task baseline)
            blk_id=f"BLK-{str(uuid.uuid4())[:8].upper()}"
            blk=Block(id=blk_id, plan_id=plan_id, window_id=assigned.id, corridor_id=assigned.corridor_id, section_id=assigned.section_id, line_id=assigned.line_id, service_date=assigned.service_date, start_time=assigned.start_time, end_time=assigned.start_time + task.estimated_duration_minutes + task.setup_duration_minutes, block_type=assigned.block_type, requires_power_isolation=assigned.requires_power_isolation, requires_signal_disconnection=assigned.requires_signal_disconnection, status="GENERATED", department=task.department)
            # clamp end_time to window end
            if blk.end_time > assigned.end_time:
                blk.end_time = assigned.end_time
            db.add(blk)
            db.flush()
            db.add(BlockTask(block_id=blk_id, task_id=task.id, status="SCHEDULED", sequence=0))
            used_windows.add(assigned.id)
            for rid in req_res:
                resource_usage[(assigned.service_date, rid)] = assigned.id
            scheduled.append(task.id)
            # do not mark task as scheduled yet, keep ELIGIBLE until optimized? But for metrics mark
        else:
            unscheduled.append({"task_id": task.id, "reason": "No feasible window"})
    # metrics
    baseline_metrics = {
        "blocks": len(scheduled),
        "scheduled_tasks": len(scheduled),
        "unscheduled": len(unscheduled),
        "block_minutes": sum([ (b.end_time - b.start_time) for b in db.query(Block).filter(Block.plan_id==plan_id).all()]),
    }
    plan.baseline_metrics = json.dumps(baseline_metrics)
    plan.optimized_metrics = json.dumps(baseline_metrics)  # baseline same for now
    plan.objective_breakdown = json.dumps({"method":"FCFS","scheduled":len(scheduled)})
    plan.unscheduled_reasons = json.dumps(unscheduled)
    db.commit()
    return plan

