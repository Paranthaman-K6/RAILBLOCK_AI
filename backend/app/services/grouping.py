import uuid, json
from sqlalchemy.orm import Session
from app.models import Task, TaskGroup
from app.services.compatibility import grouping_compatible_tasks, check_task_window_fit
from itertools import combinations

MAX_GROUP_SIZE = 3

def create_compatible_groups(db: Session, task_window_pairs):
    # Legacy greedy - kept for fallback compatibility
    groups=[]
    from collections import defaultdict
    buckets = defaultdict(list)
    for task, window in task_window_pairs:
        key = (window.corridor_id, window.service_date, window.line_id or "ANY", window.block_type, window.requires_power_isolation, window.requires_signal_disconnection)
        buckets[key].append((task, window))
    for key, pairs in buckets.items():
        pairs.sort(key=lambda x: x[0].priority_score or 0, reverse=True)
        current_group_tasks=[]
        current_window=None
        for task, window in pairs:
            tentative = current_group_tasks + [task]
            ok, reasons = grouping_compatible_tasks(tentative, window, db=db)
            if ok:
                current_group_tasks = tentative
                current_window = window
            else:
                if current_group_tasks:
                    gid=f"GRP-{str(uuid.uuid4())[:8].upper()}"
                    tg=TaskGroup(id=gid, window_id=current_window.id if current_window else None, task_ids=json.dumps([t.id for t in current_group_tasks]), compatible=True, reasons=json.dumps([]))
                    db.add(tg)
                    groups.append(tg)
                current_group_tasks=[task]
                current_window=window
        if current_group_tasks:
            gid=f"GRP-{str(uuid.uuid4())[:8].upper()}"
            tg=TaskGroup(id=gid, window_id=current_window.id if current_window else None, task_ids=json.dumps([t.id for t in current_group_tasks]), compatible=True, reasons=json.dumps([]))
            db.add(tg)
            groups.append(tg)
    db.commit()
    return groups

def generate_candidate_groups(db: Session, tasks, windows, horizon_start=None, horizon_end=None):
    """
    Bounded candidate groups for CP-SAT (max_group_size=3).
    Prunes early by corridor/section/line/date/block_type/power/signalling/duration/resource/dependency/horizon.
    Returns list of dicts with required fields.
    """
    from collections import defaultdict
    from app.models import TaskDependency
    from sqlalchemy import text
    windows_by_bucket = defaultdict(list)
    for w in windows:
        key = (w.corridor_id, w.section_id, w.line_id, w.service_date, w.block_type, w.requires_power_isolation, w.requires_signal_disconnection)
        windows_by_bucket[key].append(w)
    task_feasible_windows = defaultdict(list)
    for t in tasks:
        for w in windows:
            if t.corridor_id != w.corridor_id:
                continue
            if t.section_id and w.section_id and t.section_id != w.section_id:
                continue
            if t.line_id and w.line_id and t.line_id != w.line_id:
                continue
            if t.required_block_type != w.block_type:
                continue
            if t.requires_power_isolation != w.requires_power_isolation and t.requires_power_isolation:
                continue
            if t.requires_signal_disconnection != w.requires_signal_disconnection and t.requires_signal_disconnection:
                continue
            needed = t.estimated_duration_minutes + t.setup_duration_minutes
            if needed > w.available_minutes:
                continue
            fit, reason = check_task_window_fit(t, w)
            if fit == "HARD_CONFLICT":
                continue
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
            task_feasible_windows[t.id].append(w)
    bucket_tasks = defaultdict(set)
    bucket_windows = defaultdict(list)
    for w in windows:
        if w.status != "FEASIBLE":
            continue
        key = (w.corridor_id, w.section_id, w.line_id, w.service_date, w.block_type, w.requires_power_isolation, w.requires_signal_disconnection)
        bucket_windows[key].append(w)
    for t in tasks:
        feas = task_feasible_windows.get(t.id, [])
        for w in feas:
            key = (w.corridor_id, w.section_id, w.line_id, w.service_date, w.block_type, w.requires_power_isolation, w.requires_signal_disconnection)
            bucket_tasks[key].add(t.id)
    task_map = {t.id: t for t in tasks}
    res_map = {}
    for t in tasks:
        rows = db.execute(text(f"SELECT resource_id FROM task_resources WHERE task_id='{t.id}'")).fetchall()
        res_map[t.id] = set(r[0] for r in rows)
    dep_map = defaultdict(set)
    all_deps = db.query(TaskDependency).all()
    for d in all_deps:
        dep_map[d.task_id].add(d.depends_on_task_id)
    candidate_groups = []
    seen_group_keys = set()
    for bucket_key, task_ids in bucket_tasks.items():
        if len(task_ids) < 2:
            continue
        t_list = [task_map[tid] for tid in task_ids if tid in task_map]
        t_list.sort(key=lambda x: (x.priority_score or 0), reverse=True)
        if len(t_list) > 10:
            t_list = t_list[:10]
        for r in [2,3]:
            if r > MAX_GROUP_SIZE:
                continue
            for combo in combinations(t_list, r):
                has_internal_dep = False
                for t in combo:
                    deps = dep_map.get(t.id, set())
                    if any(d in [c.id for c in combo] for d in deps):
                        has_internal_dep = True
                        break
                if has_internal_dep:
                    continue
                total_dur = sum(t.estimated_duration_minutes + t.setup_duration_minutes for t in combo)
                feasible_windows = []
                for w in bucket_windows[bucket_key]:
                    if w.available_minutes < total_dur:
                        continue
                    all_fit = True
                    for t in combo:
                        fit,_ = check_task_window_fit(t, w)
                        if fit == "HARD_CONFLICT":
                            all_fit = False
                            break
                    if not all_fit:
                        continue
                    ok, reasons = grouping_compatible_tasks(list(combo), w, db=db)
                    if ok:
                        feasible_windows.append(w)
                if not feasible_windows:
                    continue
                task_ids = tuple(sorted([t.id for t in combo]))
                if task_ids in seen_group_keys:
                    continue
                seen_group_keys.add(task_ids)
                w0 = feasible_windows[0]
                ok, reasons = grouping_compatible_tasks(list(combo), w0, db=db)
                corridor_id = combo[0].corridor_id
                section_id = bucket_key[1]
                line_id = bucket_key[2]
                dept_list = sorted(set(t.department for t in combo))
                res_ids = set()
                for t in combo:
                    res_ids.update(res_map.get(t.id, set()))
                group = {
                    "group_id": f"GRP-{str(uuid.uuid4())[:8].upper()}",
                    "task_ids": list(task_ids),
                    "corridor_id": corridor_id,
                    "section_id": section_id,
                    "line_id": line_id,
                    "department_list": dept_list,
                    "total_duration_minutes": total_dur,
                    "resource_ids": list(res_ids),
                    "compatibility_result": {"compatible": ok, "status": "FEASIBLE" if ok else "HARD_CONFLICT", "reason": "; ".join(reasons) if reasons else "Compatible", "checks": {"corridor": True, "section": True, "line": True, "block_type": True, "power": True, "signalling": True, "resources": True, "duration": True, "dependencies": not has_internal_dep}},
                    "group_reason": f"Compatible multi-department group ({', '.join(dept_list)}) combined {total_dur} mins" if len(dept_list)>1 else f"Compatible group {total_dur} mins",
                    "feasible_windows": feasible_windows,
                    "service_date": bucket_key[3],
                    "block_type": bucket_key[4],
                    "requires_power_isolation": bucket_key[5],
                    "requires_signal_disconnection": bucket_key[6],
                }
                candidate_groups.append(group)
                if len(candidate_groups) > 100:
                    break
            if len(candidate_groups) > 100:
                break
        if len(candidate_groups) > 100:
            break
    return candidate_groups
