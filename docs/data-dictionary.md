# Data Dictionary — RailBlock AI

**Synthetic prototype data — not for real railway operations.**

## Canonical IDs
- Corridor: `COR-*` (e.g., `COR-1` Delhi-Howrah)
- Section: `SEC-*` (6)
- Line: `LIN-*` (8) types `UP|DOWN|SINGLE|LOOP`
- Asset: `AST-*` (12) types `TRACK|OHE|SIGNAL|BRIDGE`, criticality 0-100
- Task: `TSK-*` (30) sources `TMS|SMMS|TDMS|COA`, departments `ENGINEERING|S_AND_T|TRACTION|PROJECTS`
- Train: `TRN-*` (133) types `PASSENGER|GOODS`, `service_date` YYYY-MM-DD, times minutes `departure_time|arrival_time` + buffers `buffer_before|buffer_after` (15/10)
- GoodsForecast: `corridor|service_date|start_time|line` composite, confidence 0.3-0.9, risk `confidence*100`
- Resource: `RES-*` (14) types `CREW|MACHINE|MATERIAL`, departments mapped
- CandidateWindow: `WND-*`, `service_date`, `start_time|end_time` minutes, `available_minutes`, `block_type=TRAFFIC`, `status=FEASIBLE|REJECTED`, `expected_train_count`, `goods_risk_score`, `rejection_reason`, `availability_source="Synthetic prototype windows, not official railway availability."`
- BlockPlan: `PLAN-*`, `horizon_type=WEEKLY|MONTHLY`, `start_date|end_date` ISO, `status=DRAFT|UNDER_REVIEW|APPROVED|PUBLISHED|SUPERSEDED|REJECTED`, `solver_status=OPTIMAL|FEASIBLE|INFEASIBLE|TIME_LIMIT|FALLBACK_USED|VALIDATION_FAILED`, `version`
- Block: `BLK-*`, `plan_id`, `window_id`, `service_date`, `start_time|end_time`, `corridor|section|line`, `block_type`, `status`
- BlockTask: `block_id|task_id` association, `status=SCHEDULED|LOCKED|COMPLETED`
- ImportRun: `source_name`, `received|accepted|rejected|duplicate|warning_count`, `errors[]` with `{row,field,severity,code,message}`
- AuditEvent: `action`, `entity_type|entity_id`, `user_id`, `details`, `created_at`

## CSV Schemas (sample)
- `corridors.csv`: corridor_id, corridor_name, section_id, section_name, line_id, line_type, asset_id, asset_type
- `resources.csv`: resource_id, resource_type, name, department, capacity, service_date, start_time, end_time (composite duplicate `resource_id|service_date|start_time`)
- `trains.csv`: train_id, corridor_id, section_id, line_id, train_type, service_date, departure_time, arrival_time, buffer_before, buffer_after
- `goods_forecast.csv`: corridor_id, section_id, line_id, service_date, start_time, end_time, confidence, forecast_count, risk_score (composite `corridor|service_date|start_time|line`)
- `tasks.csv`: task_id, corridor_id, section_id, line_id, asset_id, task_type, description, severity, safety_score, urgency_score, asset_criticality, operational_impact, overdue_days, coordination_value, resource_readiness, estimated_duration_minutes, setup_duration_minutes, required_block_type, requires_traffic_block, requires_power_isolation, requires_signal_disconnection, earliest_start, deadline, dependency_task_ids, required_resource_ids, department (composite `task_id`)

## Derived
- Priority `P=0.30*S+0.20*U+0.20*C+0.15*O+0.10*D+0.05*R`, bands `CRITICAL≥80, HIGH≥60, MEDIUM≥40, LOW<40`, reason via thresholds.
- Train protected interval `[departure-buffer_before, arrival+buffer_after)`, overlap `train_start < block_end and train_end > block_start` (exact boundary no overlap).
- Goods risk: `confidence≥0.7 → HARD_CONFLICT`, `≥0.4 SOFT_RISK`, window `goods_risk_score≥70` rejected.
- Block duration ≤240, setup+estimated ≤ available_minutes, corridor/section/line/type/power/signal must match.
