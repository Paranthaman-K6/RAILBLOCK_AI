# Implementation Specification — RailBlock AI (Prototype)

**Version:** `main` @ `de23bbf` / `7c97bc5` (audit `0f78a7c`)  
**Date:** 2026-09-01  
**Prototype disclaimer:** This application uses synthetic demonstration data and prototype operational rules. It does not access live TMS, SMMS, TDMS, COA, timetable, or railway-control systems. It must not be used for real railway operations. Synthetic prototype windows, not official railway availability.  
**Scope:** Human-approved, explainable hybrid AI decision-support system (not autonomous control, not safety-certified, not live-integrated unless authorized).

## 1. Canonical Entities

`Department, UserContext, Corridor, Section, Line, Asset, Task, TaskDependency, TrainMovement, GoodsForecast, Resource, ResourceAvailability, CandidateWindow, TaskWindowCandidate, TaskGroup, BlockPlan, Block, BlockTask, PlanRevision, PlanChange, Approval, ExecutionRecord, Notification, RuleConfiguration, ImportRun, AuditEvent` (27)

IDs: `COR-*, SEC-*, LIN-*, AST-*, TSK-*, TRN-*, RES-*, WND-*, GRP-*, BLK-*, PLAN-*, REV-*, EXE-*`. Never use `WND-*` where `BLK-*` required.

## 2. Routes (Verified via OpenAPI `GET /openapi.json`)

```
GET  /health
GET  /api/diagnostics
GET  /api/departments, /api/corridors, /api/assets, /api/tasks, /api/trains, /api/resources
POST /api/import/tasks, /api/import/corridors, /api/import/assets, /api/import/trains, /api/import/goods-forecast, /api/import/resources
GET  /api/import/summary, GET /api/import/{import_run_id}
GET  /api/windows, GET /api/windows/{window_id}
POST /api/plans/generate, GET /api/plans, GET /api/plans/{plan_id}
POST /api/plans/{plan_id}/validate, POST /api/plans/{plan_id}/approve, POST /api/plans/{plan_id}/reject, POST /api/plans/{plan_id}/replan
GET  /api/plans/{plan_id}/history, GET /api/plans/{plan_id}/changes, GET /api/plans/{plan_id}/export
POST /api/plans/{plan_id}/revisions, PATCH /api/plans/{plan_id}/draft-blocks/{block_id}, POST /api/plans/{plan_id}/submit-review
GET  /api/approved-plans, GET /api/plans/{plan_id}/department-view, GET /api/notifications
POST /api/blocks/{block_id}/execution, GET /api/execution/plan/{plan_id}, GET /api/execution, POST /api/execution/{id} (alias)
POST /api/conflicts/detect, POST /api/optimize, GET /api/metrics, GET /api/metrics/{plan_id}
GET  /api/compatibility/priority-weights, /optimizer-weights, /hard-constraints, /ai-model
GET  /api/tasks/{task_id}/priority-explanation, GET /api/plans/{plan_id}/explanations
```

Error envelope: `{error:{code,message,details}, detail, code}` without tracebacks; validation errors `422` via `RequestValidationError`.

## 3. Services (18)

`ImportService → ValidationService → NormalizationService → AssetMapping → PriorityEngine (P=0.30S+0.20U+0.20C+0.15O+0.10D+0.05R) → RiskEngine → CandidateWindowEngine → CompatibilityEngine → GroupingEngine → Baseline → CP-SAT Optimizer → Fallback → Validator → ApprovalService → VisibilityService → ExecutionService → MetricsService → RevisionService → NotificationService → ExportService`

## 4. Priority

`P = 0.30S + 0.20U + 0.20C + 0.15O + 0.10D + 0.05R` (S safety, U urgency/overdue, C asset criticality, O operational impact, D coordination, R resource readiness) normalized 0-100, `RuleConfiguration.version=v1`, `priority_breakdown` JSON, `historical_delta` from `ExecutionRecord`.

## 5. Windows and Conflicts

Templates: `01:00–03:00 (60-180), 13:30–15:30 (810-930), 02:00–06:00 (120-360)`, max 240, `Asia/Kolkata` dates `YYYY-MM-DD`, integer minutes. Protected train interval `[departure-buffer_before, arrival+buffer_after)`, overlap `train_start < block_end and train_end > block_start` exact boundary no overlap. Goods `confidence≥0.7 HARD`, `≥0.4 SOFT`, window `goods_risk_score≥70` rejected.

## 6. Grouping

Compatible only if `same corridor, compatible section/line/date/block_type/power/signal/resources/dependencies, combined duration ≤240`. Max 3 tasks, `grouping_compatible_tasks` returns `compatible` + `reasons`.

## 7. Optimization

Baseline FCFS (priority sorted, first feasible, no grouping) vs CP-SAT (filtered `x[tid,wid]` BoolVar, constraints `task≤1, window≤1, resource non-overlap per date, dependency ordering`, objective `int((priority+critical+overdue - goods*0.2 - train*5)*10)`, 5s 8 workers, `OPTIMAL|FEASIBLE|INFEASIBLE|TIME_LIMIT|FALLBACK_USED|VALIDATION_FAILED`, fallback validated, `validate_plan` 14 checks). Baseline metrics vs optimized metrics from DB.

## 8. Validation (14 Checks A-L + Grouping)

`A plan structure, B task uniqueness, C task-window fit, D train conflict, E goods-risk, F resource conflict, G corridor/line, H power/signal, I dependency, J locked/completed preservation, K duration/buffer, L approval-state`, plus grouping `GROUP_COMPATIBILITY`, `DUPLICATE_GROUP_TASK`.

## 9. Lifecycle

- `BlockPlan`: `DRAFT→UNDER_REVIEW→APPROVED→PUBLISHED→SUPERSEDED→REJECTED`, `Block`: `GENERATED→UNDER_REVIEW→APPROVED→PUBLISHED→IN_PROGRESS→COMPLETED→PARTIALLY_COMPLETED→CANCELLED`, `Task`: `PENDING→VALIDATION_FAILED→ELIGIBLE→SCHEDULED→LOCKED→IN_PROGRESS→COMPLETED→PARTIALLY_COMPLETED→DEFERRED→CANCELLED`
- Draft editable (validated, audited), approved immutable (revision required), `expected_version` stale `409`, completed locked `400`.

## 10. Execution

`POST /api/blocks/{BLK-*}/execution` with `actual_start, actual_end, status, completed_task_ids, partially_completed_task_ids, cancelled_task_ids, reason, asset_status, train_impact, notes, recorded_by`, validates `actual_end≥actual_start`, task belongs to block, cancelled/deferred requires reason, partial requires notes, `WND-* 400`, unknown `404`, duplicate same payload `200 idempotent` diff `409`, invalid body `422`, no `500`.

## 11. Metrics and Export

`GET /api/metrics/{plan_id}` → `blocks, block_minutes, scheduled_tasks, critical_tasks, integrated_groups, conflicts, unused_time, resource_utilization, planned_vs_actual, baseline, optimized, improvement, objective_breakdown, validation, dataset: synthetic prototype`, plus `asset_downtime_minutes, asset_available_minutes, asset_availability_pct, completion_rate` (explicit). CSV/PDF export contains `PLAN-*`.

## 12. Actual Commands

Same as `AGENTS.md` §5 — verified 2026-09-01.

## 13. Testing the Contract

See `AGENTS.md` §10 — documentation test verifies `AGENTS.md`, `docs/implementation-spec.md`, `docs/problem-understanding.md`, `docs/manual-acceptance-execution.md` exist and contain required headings.

