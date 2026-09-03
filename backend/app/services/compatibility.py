from typing import List, Dict
import json

MAX_BLOCK_DURATION = 240

def check_compatible(task1, task2, max_duration=240):
    reasons=[]
    compatible=True
    if task1.corridor_id != task2.corridor_id:
        compatible=False
        reasons.append("Different corridors.")
    # section: compatible if same or one null, but spec says compatible section
    if task1.section_id and task2.section_id and task1.section_id != task2.section_id:
        # allow if sections are different but same corridor? spec says compatible section required - for now reject different sections
        compatible=False
        reasons.append("Incompatible sections.")
    if task1.line_id and task2.line_id and task1.line_id != task2.line_id:
        compatible=False
        reasons.append(f"Different lines {task1.line_id} vs {task2.line_id}.")
    if task1.required_block_type != task2.required_block_type:
        compatible=False
        reasons.append(f"Incompatible block types {task1.required_block_type} vs {task2.required_block_type}.")
    if task1.requires_power_isolation != task2.requires_power_isolation:
        compatible=False
        reasons.append("Task requires power isolation.")
        reasons.append("Second task is traffic-only." if not task2.requires_power_isolation else "Power isolation mismatch.")
    if task1.requires_signal_disconnection != task2.requires_signal_disconnection:
        compatible=False
        reasons.append("Signalling mismatch prevents grouping.")
    # combined duration
    total = (task1.estimated_duration_minutes + task1.setup_duration_minutes) + (task2.estimated_duration_minutes + task2.setup_duration_minutes)
    if total > max_duration:
        compatible=False
        reasons.append(f"Combined duration {total} exceeds {max_duration} minutes.")
    # resource compatibility: check overlapping resources (simplified: if share same resource id, not compatible concurrently unless capacity)
    # We have task_resources association; quick check via db would be better but here we assume tasks have required_resource_ids attribute
    # Check in grouping service with DB
    return {"compatible": compatible, "reasons": reasons}

def check_task_window_fit(task, window, train_movements=None, goods=None, resource_avails=None):
    # returns FEASIBLE, HARD_CONFLICT, SOFT_RISK
    # hard: passenger train overlap, power/signalling, corridor/section/line mismatch, buffer, block type, resource
    if task.corridor_id != window.corridor_id:
        return "HARD_CONFLICT", "Corridor mismatch"
    if task.section_id and window.section_id and task.section_id != window.section_id:
        return "HARD_CONFLICT", "Section mismatch"
    if task.line_id and window.line_id and task.line_id != window.line_id:
        return "HARD_CONFLICT", "Line mismatch"
    if task.required_block_type != window.block_type:
        # allow TRAFFIC vs other? strict
        return "HARD_CONFLICT", f"Block type mismatch {task.required_block_type} vs {window.block_type}"
    if task.requires_power_isolation != window.requires_power_isolation:
        # if task needs power isolation but window not
        if task.requires_power_isolation:
            return "HARD_CONFLICT", "Power isolation required"
    if task.requires_signal_disconnection != window.requires_signal_disconnection:
        if task.requires_signal_disconnection:
            return "HARD_CONFLICT", "Signal disconnection required"
    # duration fit
    needed = task.estimated_duration_minutes + task.setup_duration_minutes
    if needed > window.available_minutes:
        return "HARD_CONFLICT", "Duration exceeds window"
    # train overlap already encoded in window status? but check explicit
    if window.status=="REJECTED":
        return "HARD_CONFLICT", window.rejection_reason or "Window rejected"
    # goods risk
    if window.goods_risk_score >= 70:
        return "HARD_CONFLICT", "Goods forecast high risk"
    elif window.goods_risk_score >= 40:
        return "SOFT_RISK", "Goods forecast medium risk"
    return "FEASIBLE", "OK"

def grouping_compatible_tasks(tasks: List, window, max_duration=240, db=None, res_map=None):
    # tasks is list of Task objects
    if not tasks: return True, []
    total = sum(t.estimated_duration_minutes + t.setup_duration_minutes for t in tasks)
    if total > max_duration:
        return False, [f"Combined duration {total} exceeds {max_duration} minutes."]
    # pairwise compatibility
    for i in range(len(tasks)):
        for j in range(i+1, len(tasks)):
            res = check_compatible(tasks[i], tasks[j], max_duration)
            if not res["compatible"]:
                return False, res["reasons"]
    # resource overlap check
    if len(tasks) > 1:
        # Prefer in-memory res_map if provided (postgres-optimized, avoids N+1 query)
        if res_map is not None:
            seen = {}
            for t in tasks:
                for rid in res_map.get(t.id, set()):
                    if rid in seen:
                        return False, ["Resource overlap: shared resource " + str(rid)]
                    seen[rid] = t.id
            # Also need to check cross-task overlap (above only checks first duplicate per rid, but we need any shared)
            # More precise: check pairwise share
            for i in range(len(tasks)):
                for j in range(i+1, len(tasks)):
                    if res_map.get(tasks[i].id, set()) & res_map.get(tasks[j].id, set()):
                        return False, ["Resource overlap: shared resource " + str((res_map.get(tasks[i].id, set()) & res_map.get(tasks[j].id, set())).pop())]
        elif db:
            from sqlalchemy import text
            task_ids = [t.id for t in tasks]
            rows = db.execute(text("SELECT resource_id, COUNT(*) FROM task_resources WHERE task_id IN ('" + "','".join(task_ids) + "') GROUP BY resource_id HAVING COUNT(*) > 1")).fetchall() if task_ids else []
            if rows:
                return False, ["Resource overlap: shared resource " + str(rows[0][0])]
    return True, []
