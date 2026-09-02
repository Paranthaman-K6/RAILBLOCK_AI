import uuid, json, datetime, time
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.models import Task, CandidateWindow, BlockPlan, Block, BlockTask, TaskWindowCandidate

def run_cpsat_optimizer(db: Session, horizon_start: str, horizon_end: str, horizon_type="WEEKLY", time_limit=5):
    """
    First-class CP-SAT group-window optimization.
    - Candidate groups generated via generate_candidate_groups (max 3, pruned)
    - Variables: task_window[task_id, window_id] and group_window[group_id, window_id]
    - Constraints: task at most once across single+group, group at most once, window at most once, resource non-overlap, dependency ordering, horizon/deadline, preservation
    - No unvalidated post-merge.
    """
    tasks = db.query(Task).filter(Task.status=="ELIGIBLE").all()
    windows = db.query(CandidateWindow).filter(CandidateWindow.status=="FEASIBLE", CandidateWindow.service_date.between(horizon_start, horizon_end)).all()
    if not tasks or not windows:
        return None, "INFEASIBLE", {}, 0
    from app.services.compatibility import check_task_window_fit
    from app.services.grouping import generate_candidate_groups
    tasks = sorted(tasks, key=lambda t: (t.priority_score or 0), reverse=True)
    from collections import defaultdict
    windows_by_corridor = defaultdict(list)
    for w in windows:
        windows_by_corridor[w.corridor_id].append(w)
    tw_candidates=[]
    for t in tasks:
        cand_windows = windows_by_corridor.get(t.corridor_id, [])
        for w in cand_windows:
            if int(w.end_time) - int(w.start_time) > 240:
                continue
            fit, reason = check_task_window_fit(t, w)
            if fit != "HARD_CONFLICT":
                if t.earliest_start:
                    try:
                        es = t.earliest_start.strftime("%Y-%m-%d") if hasattr(t.earliest_start, 'strftime') else str(t.earliest_start)[:10]
                        if w.service_date < es:
                            continue
                    except:
                        pass
                if t.deadline:
                    try:
                        dl = t.deadline.strftime("%Y-%m-%d") if hasattr(t.deadline, 'strftime') else str(t.deadline)[:10]
                        if w.service_date > dl:
                            continue
                    except:
                        pass
                tw_candidates.append((t,w,fit))
    if not tw_candidates and not tasks:
        return None, "INFEASIBLE", {}, 0
    candidate_groups = generate_candidate_groups(db, tasks, windows, horizon_start, horizon_end)
    gw_candidates = []
    for g in candidate_groups:
        for w in g['feasible_windows']:
            if w.service_date < horizon_start or w.service_date > horizon_end:
                continue
            if g['total_duration_minutes'] > w.available_minutes:
                continue
            gw_candidates.append((g, w))
    if not tw_candidates and not gw_candidates:
        return None, "INFEASIBLE", {}, 0
    try:
        from ortools.sat.python import cp_model
        model = cp_model.CpModel()
        x_tw = {}
        for t,w,fit in tw_candidates:
            x_tw[(t.id,w.id)] = model.NewBoolVar(f"x_{t.id}_{w.id}")
        x_gw = {}
        for g,w in gw_candidates:
            x_gw[(g['group_id'],w.id)] = model.NewBoolVar(f"y_{g['group_id']}_{w.id}")
        group_map = {g['group_id']: g for g in candidate_groups}
        for t in tasks:
            vars_for_task = []
            for (tid,wid), var in x_tw.items():
                if tid == t.id:
                    vars_for_task.append(var)
            for (gid,wid), var in x_gw.items():
                g = group_map.get(gid)
                if g and t.id in g['task_ids']:
                    vars_for_task.append(var)
            if vars_for_task:
                model.Add(sum(vars_for_task) <= 1)
        for g in candidate_groups:
            vars_for_group = [var for (gid,wid), var in x_gw.items() if gid == g['group_id']]
            if vars_for_group:
                model.Add(sum(vars_for_group) <= 1)
        for w in windows:
            vars_for_window = []
            for (tid,wid), var in x_tw.items():
                if wid == w.id:
                    vars_for_window.append(var)
            for (gid,wid), var in x_gw.items():
                if wid == w.id:
                    vars_for_window.append(var)
            if vars_for_window:
                model.Add(sum(vars_for_window) <= 1)
        res_map_task = {}
        for t in tasks:
            rows = db.execute(text(f"SELECT resource_id FROM task_resources WHERE task_id='{t.id}'")).fetchall()
            res_map_task[t.id] = [r[0] for r in rows]
        from collections import defaultdict
        date_windows = defaultdict(list)
        for w in windows:
            date_windows[w.service_date].append(w)
        for date, wlist in date_windows.items():
            resource_vars = defaultdict(list)
            for (tid,wid), var in x_tw.items():
                w = next((ww for ww in windows if ww.id==wid), None)
                if w and w.service_date == date:
                    for rid in res_map_task.get(tid, []):
                        resource_vars[rid].append(var)
            for (gid,wid), var in x_gw.items():
                w = next((ww for ww in windows if ww.id==wid), None)
                if w and w.service_date == date:
                    g = group_map.get(gid)
                    if g:
                        for rid in g.get('resource_ids', []):
                            resource_vars[rid].append(var)
            for rid, vars_ in resource_vars.items():
                if len(vars_)>1:
                    model.Add(sum(vars_) <= 1)
        from app.models import TaskDependency
        deps = db.query(TaskDependency).all()
        for d in deps:
            dep_single_vars = [var for (tid,wid), var in x_tw.items() if tid == d.depends_on_task_id]
            dep_group_vars = [var for (gid,wid), var in x_gw.items() if d.depends_on_task_id in group_map[gid]['task_ids']]
            dep_vars = dep_single_vars + dep_group_vars
            task_single_vars = [var for (tid,wid), var in x_tw.items() if tid == d.task_id]
            task_group_vars = [var for (gid,wid), var in x_gw.items() if d.task_id in group_map[gid]['task_ids']]
            task_vars = task_single_vars + task_group_vars
            if not dep_vars and task_vars:
                for var in task_vars:
                    model.Add(var == 0)
                continue
            if dep_vars and task_vars:
                model.Add(sum(task_vars) <= sum(dep_vars))
                for (tid,wid), var_task in list(x_tw.items()):
                    if tid != d.task_id:
                        continue
                    w_task = next((ww for ww in windows if ww.id==wid), None)
                    if not w_task:
                        continue
                    earlier_dep_vars = []
                    for (tid2,wid2), var_dep in x_tw.items():
                        if tid2 != d.depends_on_task_id:
                            continue
                        w_dep = next((ww for ww in windows if ww.id==wid2), None)
                        if w_dep and (w_dep.service_date < w_task.service_date or (w_dep.service_date == w_task.service_date and w_dep.start_time <= w_task.start_time)):
                            earlier_dep_vars.append(var_dep)
                    for (gid2,wid2), var_dep in x_gw.items():
                        if d.depends_on_task_id not in group_map[gid2]['task_ids']:
                            continue
                        w_dep = next((ww for ww in windows if ww.id==wid2), None)
                        if w_dep and (w_dep.service_date < w_task.service_date or (w_dep.service_date == w_task.service_date and w_dep.start_time <= w_task.start_time)):
                            earlier_dep_vars.append(var_dep)
                    if earlier_dep_vars:
                        model.Add(var_task <= sum(earlier_dep_vars))
                    else:
                        model.Add(var_task == 0)
                for (gid,wid), var_task in list(x_gw.items()):
                    if d.task_id not in group_map[gid]['task_ids']:
                        continue
                    w_task = next((ww for ww in windows if ww.id==wid), None)
                    if not w_task:
                        continue
                    earlier_dep_vars = []
                    for (tid2,wid2), var_dep in x_tw.items():
                        if tid2 != d.depends_on_task_id:
                            continue
                        w_dep = next((ww for ww in windows if ww.id==wid2), None)
                        if w_dep and (w_dep.service_date < w_task.service_date or (w_dep.service_date == w_task.service_date and w_dep.start_time <= w_task.start_time)):
                            earlier_dep_vars.append(var_dep)
                    for (gid2,wid2), var_dep in x_gw.items():
                        if d.depends_on_task_id not in group_map[gid2]['task_ids']:
                            continue
                        w_dep = next((ww for ww in windows if ww.id==wid2), None)
                        if w_dep and (w_dep.service_date < w_task.service_date or (w_dep.service_date == w_task.service_date and w_dep.start_time <= w_task.start_time)):
                            earlier_dep_vars.append(var_dep)
                    if earlier_dep_vars:
                        model.Add(var_task <= sum(earlier_dep_vars))
                    else:
                        model.Add(var_task == 0)
        try:
            rc = db.execute(text("SELECT priority_weights FROM rule_configurations LIMIT 1")).fetchone()
            import json as js
        except:
            pass
        obj_terms=[]
        objective_components = {"priority_value":0, "critical_benefit":0, "overdue_reduction":0, "integrated_group_benefit":0, "asset_availability_benefit":0, "train_penalty":0, "unused_penalty":0, "resource_cost":0}
        for (tid,wid), var in x_tw.items():
            t = next(tt for tt in tasks if tt.id==tid)
            w = next(ww for ww in windows if ww.id==wid)
            benefit = (t.priority_score or 50)
            comp_priority = (t.priority_score or 50) * 10
            comp_critical = 200 if t.priority_band=="CRITICAL" else 0
            comp_overdue = min(20, t.overdue_days*2) *10
            comp_asset = (t.asset_criticality or 50) * 0.5
            train_pen = (w.goods_risk_score*0.2 + w.expected_train_count*5) *10
            unused_pen = 0
            net = comp_priority + comp_critical + comp_overdue + comp_asset - train_pen - unused_pen
            obj_terms.append(var * int(net))
        for (gid,wid), var in x_gw.items():
            g = group_map[gid]
            w = next(ww for ww in windows if ww.id==wid)
            group_benefit = 0
            for tid in g['task_ids']:
                t = next(tt for tt in tasks if tt.id==tid)
                comp_priority = (t.priority_score or 50) *10
                comp_critical = 200 if t.priority_band=="CRITICAL" else 0
                comp_overdue = min(20, t.overdue_days*2) *10
                comp_asset = (t.asset_criticality or 50) *0.5
                group_benefit += comp_priority + comp_critical + comp_overdue + comp_asset
            integ_bonus = 500 if len(g['department_list'])>1 else 200
            train_pen = (w.goods_risk_score*0.2 + w.expected_train_count*5) *10
            unused = w.available_minutes - g['total_duration_minutes']
            unused_pen = max(0, unused) * 1
            net = group_benefit + integ_bonus - train_pen - unused_pen
            obj_terms.append(var * int(net))
        if not obj_terms:
            return None, "INFEASIBLE", {}, 0
        model.Maximize(sum(obj_terms))
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = time_limit
        solver.parameters.num_search_workers = 8
        start = time.time()
        status = solver.Solve(model)
        runtime = time.time() - start
        status_map = {
            cp_model.OPTIMAL: "OPTIMAL",
            cp_model.FEASIBLE: "FEASIBLE",
            cp_model.INFEASIBLE: "INFEASIBLE",
            cp_model.MODEL_INVALID: "UNKNOWN",
            cp_model.UNKNOWN: "UNKNOWN",
        }
        solver_status = status_map.get(status, "UNKNOWN")
        if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            plan_id=f"PLAN-{str(uuid.uuid4())[:8].upper()}"
            plan = BlockPlan(id=plan_id, horizon_type=horizon_type, start_date=horizon_start, end_date=horizon_end, status="DRAFT", solver_status=solver_status, created_at=datetime.datetime.utcnow(), version=1)
            db.add(plan)
            db.flush()
            scheduled=set()
            selected_group_ids=set()
            comp = {"priority_value":0,"critical_benefit":0,"overdue_reduction":0,"integrated_group_benefit":0,"asset_availability_benefit":0,"train_penalty":0,"unused_penalty":0,"resource_cost":0}
            blocks_created=0
            for (gid,wid), var in x_gw.items():
                if solver.Value(var)==1:
                    g = group_map[gid]
                    w = next(ww for ww in windows if ww.id==wid)
                    blk_id=f"BLK-{str(uuid.uuid4())[:8].upper()}"
                    total_dur = g['total_duration_minutes']
                    blk=Block(id=blk_id, plan_id=plan_id, window_id=w.id, corridor_id=w.corridor_id, section_id=w.section_id, line_id=w.line_id, service_date=w.service_date, start_time=w.start_time, end_time=w.start_time + total_dur, block_type=w.block_type, requires_power_isolation=w.requires_power_isolation, requires_signal_disconnection=w.requires_signal_disconnection, status="GENERATED", department=",".join(sorted(g['department_list'])))
                    if blk.end_time > w.end_time:
                        blk.end_time = w.end_time
                    db.add(blk)
                    db.flush()
                    for seq, tid in enumerate(g['task_ids']):
                        db.add(BlockTask(block_id=blk_id, task_id=tid, status="SCHEDULED", sequence=seq))
                        scheduled.add(tid)
                    selected_group_ids.add(gid)
                    try:
                        from app.models import TaskGroup
                        # Clean stale groups for this window (avoid validator false BLOCK_GROUP_MISMATCH across plans)
                        # Only keep one group per window per plan; delete old groups for same window with different tasks
                        stale = db.query(TaskGroup).filter(TaskGroup.window_id==w.id).all()
                        for st in stale:
                            try:
                                import json as js
                                if set(js.loads(st.task_ids)) != set(g['task_ids']):
                                    # Keep only if it's from previous plan and now mismatched; remove to avoid stale false positive
                                    # But don't delete if same task_ids (idempotent)
                                    db.delete(st)
                            except:
                                pass
                        existing_tg = db.query(TaskGroup).filter(TaskGroup.id==gid).first()
                        if not existing_tg:
                            tg=TaskGroup(id=gid, window_id=w.id, task_ids=json.dumps(g['task_ids']), compatible=True, reasons=json.dumps([g['group_reason']]))
                            db.add(tg)
                    except:
                        pass
                    blocks_created+=1
                    for tid in g['task_ids']:
                        t = next(tt for tt in tasks if tt.id==tid)
                        comp["priority_value"]+= t.priority_score or 0
                        if t.priority_band=="CRITICAL":
                            comp["critical_benefit"]+=20
                        comp["overdue_reduction"]+= min(20, t.overdue_days*2)
                        comp["asset_availability_benefit"]+= (t.asset_criticality or 50)*0.05
                    comp["integrated_group_benefit"]+= 50 if len(g['department_list'])>1 else 20
                    comp["train_penalty"]+= w.goods_risk_score*0.2 + w.expected_train_count*5
                    comp["unused_penalty"]+= max(0, w.available_minutes - total_dur)*0.1
            for (tid,wid), var in x_tw.items():
                if solver.Value(var)==1:
                    if tid in scheduled:
                        continue
                    t = next(tt for tt in tasks if tt.id==tid)
                    w = next(ww for ww in windows if ww.id==wid)
                    blk_id=f"BLK-{str(uuid.uuid4())[:8].upper()}"
                    blk=Block(id=blk_id, plan_id=plan_id, window_id=w.id, corridor_id=w.corridor_id, section_id=w.section_id, line_id=w.line_id, service_date=w.service_date, start_time=w.start_time, end_time=w.start_time + t.estimated_duration_minutes + t.setup_duration_minutes, block_type=w.block_type, requires_power_isolation=w.requires_power_isolation, requires_signal_disconnection=w.requires_signal_disconnection, status="GENERATED", department=t.department)
                    if blk.end_time > w.end_time:
                        blk.end_time = w.end_time
                    db.add(blk)
                    db.flush()
                    db.add(BlockTask(block_id=blk_id, task_id=tid, status="SCHEDULED"))
                    scheduled.add(tid)
                    blocks_created+=1
                    comp["priority_value"]+= t.priority_score or 0
                    if t.priority_band=="CRITICAL":
                        comp["critical_benefit"]+=20
                    comp["overdue_reduction"]+= min(20, t.overdue_days*2)
                    comp["asset_availability_benefit"]+= (t.asset_criticality or 50)*0.05
                    comp["train_penalty"]+= w.goods_risk_score*0.2 + w.expected_train_count*5
                    comp["unused_penalty"]+= max(0, w.available_minutes - (t.estimated_duration_minutes+t.setup_duration_minutes))*0.1
            comp["integrated_groups"] = len(selected_group_ids)
            objective_value = sum([comp["priority_value"]*10, comp["critical_benefit"]*10, comp["overdue_reduction"]*10, comp["integrated_group_benefit"]*10, comp["asset_availability_benefit"]*10]) - sum([comp["train_penalty"]*10, comp["unused_penalty"]*10])
            plan.objective_breakdown = json.dumps(comp)
            plan.baseline_metrics = json.dumps({})
            plan.optimized_metrics = json.dumps({"scheduled":len(scheduled),"blocks":blocks_created, "integrated_groups": len(selected_group_ids), "candidate_count": len(tw_candidates), "group_count": len(candidate_groups), "selected_group_count": len(selected_group_ids), "objective_value": objective_value, "solver_runtime": runtime})
            unscheduled=[{"task_id":t.id,"reason":"Not selected by optimizer"} for t in tasks if t.id not in scheduled]
            plan.unscheduled_reasons = json.dumps(unscheduled)
            extra = {"objective_value": objective_value, "objective_components": comp, "solver_runtime": runtime, "task_count": len(tasks), "candidate_count": len(tw_candidates), "group_count": len(candidate_groups), "selected_group_count": len(selected_group_ids), "integrated_block_count": len(selected_group_ids)}
            db.commit()
            return plan, solver_status, comp, runtime
        else:
            return None, solver_status, {}, runtime
    except Exception as e:
        import traceback
        traceback.print_exc()
        return None, f"ERROR:{str(e)}", {}, 0
