def goods_risk_classify(confidence, risk_score=50, threshold=0.7):
    # goods forecast with low confidence -> SOFT_RISK, high confidence -> HARD or severe
    if confidence < 0.5:
        return "SOFT_RISK", risk_score*0.5
    elif confidence >= threshold:
        return "HARD_CONFLICT", risk_score
    else:
        return "SOFT_RISK", risk_score*0.8

def train_conflict_check(window_start, window_end, train_start, train_end, buffer_before=15, buffer_after=15):
    # protected interval [train_start-buffer_before, train_end+buffer_after]
    protected_start = train_start - buffer_before
    protected_end = train_end + buffer_after
    # overlap? window [start,end) vs protected
    # exact boundary consistent: if window_end == protected_start -> no overlap, if window_start == protected_end -> no overlap
    if window_end <= protected_start or window_start >= protected_end:
        return False
    return True
