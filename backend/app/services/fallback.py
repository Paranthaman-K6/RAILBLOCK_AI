import uuid, json, datetime
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.models import Task, CandidateWindow, BlockPlan, Block, BlockTask, TaskGroup

def generate_fallback_plan(db: Session, horizon_start: str, horizon_end: str, horizon_type="WEEKLY"):
    """Deterministic greedy fallback with valid multi-department groups, respecting max_group_size=3."""
    from app.services.compatibility import check_task_window_fit, grouping_compatible_tasks
    from app.services.grouping import generate_candidate_groups
    tasks = db.query(Task).filter(Task.status=="ELIGIBLE").all()
    tasks_sorted = sorted(tasks, key=lambda t: (-(t.priority_score or 0), t.id))
    windows = db.query(CandidateWindow).filter(CandidateWindow.status=="FEASIBLE", CandidateWindow.service_date.between(horizon_start, horizon_end)).all()
    windows_sorted = sorted(windows, key=lambda w: (w.service_date, w.start_time, w.id))
    candidate_groups = generate_candidate_groups(db, tasks_sorted, windows_sorted, horizon_start, horizon_end)
    def group_priority(g):
        s = sum(next((t.priority_score or 0) for t in tasks_sorted if t.id==tid) for tid in g['task_ids'])
        bonus = 50 if len(g['department_list'])>1 else 0
        return s + bonus
    candidate_groups.sort(key=lambda g: group_priority(g), reverse=True)
    plan_id=f"PLAN-{str(uuid.uuid4())[:8].upper()}"
    plan = BlockPlan(id=plan_id, horizon_type=horizon_type, start_date=horizon_start, end_date=horizon_end, status="DRAFT", solver_status="FALLBACK_USED", created_at=datetime.datetime.utcnow(), version=1)
    db.add(plan)
    db.flush()
    used_windows=set()
    scheduled=set()
    resource_usage = {}
    blocks_created=0
    selected_groups=[]
    for g in candidate_groups:
        if len(g['task_ids']) > 3:
            continue
        if any(tid in scheduled for tid in g['task_ids']):
            continue
        from app.models import TaskDependency
        deps_ok=True
        for tid in g['task_ids']:
            for d in db.query(TaskDependency).filter(TaskDependency.task_id==tid).all():
                if d.depends_on_task_id not in scheduled:
                    if d.depends_on_task_id not in g['task_ids']:
                        deps_ok=False
                        break
            if not deps_ok:
                break
        if not deps_ok:
            continue
        feasible_w = None
        for w in g['feasible_windows']:
            if w.id in used_windows:
                continue
            conflict=False
            for rid in g['resource_ids']:
                if (w.service_date, rid) in resource_usage:
                    conflict=True
                    break
            if conflict:
                continue
            feasible_w = w
            break
        if not feasible_w:
            continue
        blk_id=f"BLK-{str(uuid.uuid4())[:8].upper()}"
        total_dur = g['total_duration_minutes']
        blk=Block(id=blk_id, plan_id=plan_id, window_id=feasible_w.id, corridor_id=feasible_w.corridor_id, section_id=feasible_w.section_id, line_id=feasible_w.line_id, service_date=feasible_w.service_date, start_time=feasible_w.start_time, end_time=feasible_w.start_time + total_dur, block_type=feasible_w.block_type, requires_power_isolation=feasible_w.requires_power_isolation, requires_signal_disconnection=feasible_w.requires_signal_disconnection, status="GENERATED", department=",".join(sorted(g['department_list'])))
        if blk.end_time > feasible_w.end_time:
            blk.end_time = feasible_w.end_time
        db.add(blk)
        db.flush()
        for seq, tid in enumerate(g['task_ids']):
            db.add(BlockTask(block_id=blk_id, task_id=tid, status="SCHEDULED", sequence=seq))
        try:
            tg=TaskGroup(id=g['group_id'], window_id=feasible_w.id, task_ids=json.dumps(g['task_ids']), compatible=True, reasons=json.dumps([g['group_reason']]))
            db.add(tg)
        except:
            pass
        used_windows.add(feasible_w.id)
        for rid in g['resource_ids']:
            resource_usage[(feasible_w.service_date, rid)]=feasible_w.id
        scheduled.update(g['task_ids'])
        blocks_created+=1
        selected_groups.append(g)
    for task in tasks_sorted:
        if task.id in scheduled:
            continue
        from app.models import TaskDependency
        deps = db.query(TaskDependency).filter(TaskDependency.task_id==task.id).all()
        dep_satisfied=True
        for d in deps:
            if d.depends_on_task_id not in scheduled:
                dep_satisfied=False
                break
        if not dep_satisfied:
            continue
        rows = db.execute(text(f"SELECT resource_id FROM task_resources WHERE task_id='{task.id}'")).fetchall()
        req = [r[0] for r in rows]
        for w in windows_sorted:
            if w.id in used_windows:
                continue
            fit, reason = check_task_window_fit(task, w)
            if fit=="HARD_CONFLICT":
                continue
            conflict=False
            for rid in req:
                if (w.service_date, rid) in resource_usage:
                    conflict=True
                    break
            if conflict:
                continue
            if task.deadline:
                try:
                    dl = task.deadline.strftime("%Y-%m-%d")
                    if w.service_date > dl:
                        continue
                except:
                    pass
            blk_id=f"BLK-{str(uuid.uuid4())[:8].upper()}"
            blk=Block(id=blk_id, plan_id=plan_id, window_id=w.id, corridor_id=w.corridor_id, section_id=w.section_id, line_id=w.line_id, service_date=w.service_date, start_time=w.start_time, end_time=w.start_time + task.estimated_duration_minutes + task.setup_duration_minutes, block_type=w.block_type, requires_power_isolation=w.requires_power_isolation, requires_signal_disconnection=w.requires_signal_disconnection, status="GENERATED", department=task.department)
            if blk.end_time > w.end_time:
                blk.end_time = w.end_time
            db.add(blk)
            db.flush()
            db.add(BlockTask(block_id=blk_id, task_id=task.id, status="SCHEDULED"))
            used_windows.add(w.id)
            for rid in req:
                resource_usage[(w.service_date, rid)]=w.id
            scheduled.add(task.id)
            blocks_created+=1
            break
    from app.services.plan_validator import validate_plan
    db.flush()
    val = validate_plan(db, plan_id)
    if not val["valid"]:
        plan.solver_status="VALIDATION_FAILED"
        db.commit()
        return plan
    unscheduled=[{"task_id":t.id,"reason":"No feasible window (fallback)"} for t in tasks if t.id not in scheduled]
    plan.unscheduled_reasons=json.dumps(unscheduled)
    plan.optimized_metrics=json.dumps({"scheduled":len(scheduled),"blocks":blocks_created, "integrated_groups": len(selected_groups), "candidate_count": len(tasks_sorted)*len(windows_sorted), "group_count": len(candidate_groups), "selected_group_count": len(selected_groups)})
    plan.objective_breakdown=json.dumps({"method":"FALLBACK","scheduled":len(scheduled), "integrated_groups": len(selected_groups)})
    db.commit()
    return plan
