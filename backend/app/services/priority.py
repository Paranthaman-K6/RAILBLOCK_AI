import json

WEIGHTS = {"S":0.30,"U":0.20,"C":0.20,"O":0.15,"D":0.10,"R":0.05}
VERSION="v1"

def _get_active_weights(db=None):
    if db is None:
        return WEIGHTS, VERSION
    try:
        from app.models import RuleConfiguration
        rc = db.query(RuleConfiguration).order_by(RuleConfiguration.created_at.desc()).first()
        if rc and rc.priority_weights:
            import json
            w = json.loads(rc.priority_weights)
            # Validate
            if all(k in w for k in ["S","U","C","O","D","R"]):
                return w, rc.version
    except:
        pass
    return WEIGHTS, VERSION

def normalize_score(v):
    try:
        f=float(v)
        return max(0,min(100,f))
    except:
        return 50

def _historical_adjustment(task, db=None):
    """8th source: historical execution results. Returns (delta_U, delta_R, reason) based on past executions for same asset/corridor."""
    if db is None:
        return 0, 0, None
    try:
        from app.models import ExecutionRecord, Block, BlockTask
        # Find recent executions for same asset or same corridor (last 5)
        # For efficiency, check ExecutionRecord joined via BlockTask -> Task -> Asset
        # Simplified: count recent PARTIALLY_COMPLETED/CANCELLED for same asset, and COMPLETED for same task
        # Use indexed queries, limit 5
        hist = db.query(ExecutionRecord).join(Block, ExecutionRecord.block_id==Block.id).join(BlockTask, BlockTask.block_id==Block.id).filter(BlockTask.task_id==task.id).order_by(ExecutionRecord.created_at.desc()).limit(5).all()
        if not hist:
            # Also check same asset via Task asset_id
            if task.asset_id:
                # Find tasks with same asset
                from app.models import Task as TaskModel
                same_asset_task_ids = [t.id for t in db.query(TaskModel).filter(TaskModel.asset_id==task.asset_id).all()]
                if same_asset_task_ids:
                    hist2 = db.query(ExecutionRecord).join(Block, ExecutionRecord.block_id==Block.id).join(BlockTask, BlockTask.block_id==Block.id).filter(BlockTask.task_id.in_(same_asset_task_ids)).order_by(ExecutionRecord.created_at.desc()).limit(5).all()
                    hist = hist2
        if not hist:
            return 0, 0, None
        # Analyze: if any recent CANCELLED/PARTIALLY_COMPLETED -> increase urgency
        for h in hist:
            if h.status in ["CANCELLED","PARTIALLY_COMPLETED","DEFERRED"]:
                return 8, 0, "recent execution required rework"
        # If recent COMPLETED -> slightly reduce urgency (asset recently maintained) but not much
        # For prototype, we treat historical COMPLETED as slightly lower urgency (-2) to avoid re-scheduling too soon
        if hist and hist[0].status=="COMPLETED":
            return -2, 0, "recently completed - lower urgency"
        return 0, 0, None
    except:
        return 0, 0, None

def compute_priority(task, db=None):
    weights, version = _get_active_weights(db)
    S = normalize_score(task.safety_score)
    # Base urgency
    baseU = normalize_score(task.urgency_score if task.urgency_score else min(100, 50 + task.overdue_days*5))
    # Historical adjustment (8th source)
    hU, hR, hReason = _historical_adjustment(task, db)
    U = normalize_score(baseU + hU)
    C = normalize_score(task.asset_criticality)
    O = normalize_score(task.operational_impact)
    D = normalize_score(task.coordination_value)
    R = normalize_score(task.resource_readiness + hR)
    P = weights["S"]*S + weights["U"]*U + weights["C"]*C + weights["O"]*O + weights["D"]*D + weights["R"]*R
    P = round(P,1)
    if P>=80: band="CRITICAL"
    elif P>=60: band="HIGH"
    elif P>=40: band="MEDIUM"
    else: band="LOW"
    reasons=[]
    if S>=80: reasons.append("high safety criticality")
    if task.overdue_days>0: reasons.append(f"{task.overdue_days} overdue days")
    if C>=80: reasons.append("critical asset")
    if O>=70: reasons.append("significant operational impact")
    if D>=70: reasons.append("compatible with an existing corridor block")
    if R>=70: reasons.append("required resources available")
    if hReason:
        reasons.append(hReason + " (historical execution)")
    if not reasons: reasons.append("standard maintenance")
    reason = "; ".join(reasons)
    breakdown = {"S":S,"U":U,"C":C,"O":O,"D":D,"R":R,"P":P, "weights":weights, "historical_delta_U":hU, "historical_delta_R":hR}
    return {
        "priority_score": P,
        "priority_band": band,
        "factor_values": {"S":S,"U":U,"C":C,"O":O,"D":D,"R":R},
        "factor_weights": weights,
        "priority_breakdown": breakdown,
        "priority_reason": reason,
        "rule_configuration_version": version,
    }

def recalculate_all(db):
    from app.models import Task, ExecutionRecord, Block, BlockTask
    hist_map = {}
    asset_hist = {}
    try:
        # Fast path: if no executions, skip historical (most tests)
        if db.query(ExecutionRecord).count() > 0:
            recent = db.query(ExecutionRecord).order_by(ExecutionRecord.created_at.desc()).limit(100).all()
            for h in recent:
                bts = db.query(BlockTask).filter(BlockTask.block_id==h.block_id).all()
                for bt in bts:
                    if bt.task_id not in hist_map:
                        hist_map[bt.task_id] = h.status
            for t in db.query(Task).all():
                if t.asset_id and t.id in hist_map:
                    asset_hist[t.asset_id] = hist_map[t.id]
    except:
        hist_map = {}
        asset_hist = {}
    from app.models import Task as TaskModel
    weights, version = _get_active_weights(db)
    tasks = db.query(TaskModel).all()
    for t in tasks:
        # Use bulk hist_map instead of per-task DB query
        h_status = hist_map.get(t.id)
        if not h_status and t.asset_id:
            h_status = asset_hist.get(t.asset_id)
        # Quick historical delta without extra DB hit
        hU, hR, hReason = 0, 0, None
        if h_status in ["CANCELLED","PARTIALLY_COMPLETED","DEFERRED"]:
            hU, hR, hReason = 8, 0, "recent execution required rework"
        elif h_status == "COMPLETED":
            hU, hR, hReason = -2, 0, "recently completed - lower urgency"
        # Direct compute without DB call for efficiency
        # Inline compute to avoid extra DB query in _historical_adjustment
        S = normalize_score(t.safety_score)
        baseU = normalize_score(t.urgency_score if t.urgency_score else min(100, 50 + t.overdue_days*5))
        U = normalize_score(baseU + hU)
        C = normalize_score(t.asset_criticality)
        O = normalize_score(t.operational_impact)
        D = normalize_score(t.coordination_value)
        R = normalize_score(t.resource_readiness + hR)
        P = weights["S"]*S + weights["U"]*U + weights["C"]*C + weights["O"]*O + weights["D"]*D + weights["R"]*R
        P = round(P,1)
        if P>=80: band="CRITICAL"
        elif P>=60: band="HIGH"
        elif P>=40: band="MEDIUM"
        else: band="LOW"
        reasons=[]
        if S>=80: reasons.append("high safety criticality")
        if t.overdue_days>0: reasons.append(f"{t.overdue_days} overdue days")
        if C>=80: reasons.append("critical asset")
        if O>=70: reasons.append("significant operational impact")
        if D>=70: reasons.append("compatible with an existing corridor block")
        if R>=70: reasons.append("required resources available")
        if hReason: reasons.append(hReason + " (historical execution)")
        if not reasons: reasons.append("standard maintenance")
        reason = "; ".join(reasons)
        breakdown = {"S":S,"U":U,"C":C,"O":O,"D":D,"R":R,"P":P, "weights":weights, "historical_delta_U":hU, "historical_delta_R":hR}
        t.priority_score = P
        t.priority_band = band
        t.priority_reason = reason
        t.priority_breakdown = json.dumps(breakdown)
        t.rule_configuration_version = version
    db.commit()
    tasks_sorted = sorted(tasks, key=lambda x: x.priority_score, reverse=True)
    for idx, t in enumerate(tasks_sorted, start=1):
        t.priority_rank = idx
    db.commit()
