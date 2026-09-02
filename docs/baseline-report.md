# Baseline Report — RailBlock AI

**Synthetic prototype dataset — not for real railway operations.**

## Method
- **Baseline:** *First-come-first-served scheduling without integrated multi-department grouping.* Tasks sorted by `priority_score DESC, task_id`, windows sorted by `(service_date, start_time)`, assigns first feasible window per task checking `check_task_window_fit` (corridor/section/line/type/power/signal/duration/train-window status/goods risk/deadline), resource per-date conflict (same `resource_id` same `service_date`), dependency `depends_on` must be scheduled earlier. One task per block, no grouping, not optimizing for integrated utilization.
- **Optimized:** CP-SAT with filtered feasible `task-window` pairs grouped by corridor, integer times, `x[tid,wid]` BoolVar, constraints: task≤1, window≤1, resource non-overlap per date, dependency `sum(task_vars) ≤ sum(dep_vars)` + ordering `var_task ≤ sum(earlier_dep_vars)`, objective `max Σ int((priority+critical+overdue - goods_risk*0.2 - train_count*5)*10)` with configurable weights, time_limit 5s, 8 workers. Returns `OPTIMAL|FEASIBLE|INFEASIBLE|TIME_LIMIT|FALLBACK_USED|VALIDATION_FAILED`, validated independently via `validate_plan` (14 checks), fallback only if validated.

## Real Dataset (2026-09-01 to 2026-09-30, seed 42, 8 sources)
- Tasks 30 (TMS/SMMS/TDMS/COA mapped via departments ENGINEERING 8, S_AND_T 8, TRACTION 7, PROJECTS 7; 5 with dependencies, overdue 0-20, durations 30-180+setup 10-30) + historical execution (8th source via ExecutionRecord)
- Windows 168 total (templates 01:00-03:00, 13:30-15:30, 02:00-06:00, max 240) → ~134 FEASIBLE, 34 REJECTED (train 01:30-02:00 on 2026-09-02/05, goods high confidence 0.9 on 2026-09-02)
- Trains 133 (timetable, 14 days × ~9), Goods 43 (goods forecast, 14 days ×3 + high on 2026-09-02), Resources 14 (crew/machine/material per department)

## Comparison (calculated from current synthetic dataset, not copied example)
Run `POST /api/plans/generate` weekly (2026-09-01 to 2026-09-07, also DAILY and MONTHLY) and compute `GET /api/metrics/{plan_id}`:
- Example weekly run (OPTIMAL 20 blocks 2-3 integrated, valid):
  - Baseline: `blocks 19, tasks_scheduled 19, total_block_minutes 2035` (one per block, FCFS, no grouping)
  - Optimized: `blocks 18-20, tasks_scheduled 20, total_block_minutes 2165, integrated_groups 2-3, candidate_count 198, group_count 11` (CP-SAT first-class group-window `y[group,window]` 23 candidates → 2 selected, time_limit 5s, 8 workers)
  - Weekly 2026-09-01→07: 20 blocks 3 integrated via CP-SAT; Daily 2026-09-02: 4 blocks horizon_type DAILY; Monthly: 18 blocks
  - Metrics via `/api/metrics` include `baseline: {blocks, tasks_scheduled, total_block_minutes}`, `optimized: {...}`, `improvement: {blocks_reduced, tasks_added, minutes_reduced}`, `dataset: "synthetic prototype"` plus `blocks, scheduled_tasks, critical_tasks, integrated_groups, conflicts, unused_time, resource_utilization 66.7%, planned_vs_actual`, plus `objective_breakdown {priority_value, critical_benefit, overdue_reduction, integrated_group_benefit, asset_availability_benefit, train_penalty, unused_penalty, integrated_groups}` and `solver_status/runtime`.

**Do not invent percentages.** Above are from `scripts/ingest_synthetic.py` sample weekly run; actual varies with solver time_limit and random goods confidence. Rerun and report actual `GET /api/metrics/{id}` JSON.

## Resource Utilization
`resource_utilization = scheduled_tasks / total_tasks *100` (prototype). Integrated groups counted via `TaskGroup` where compatible tasks share window.

## Validation
Both baseline and optimized pass independent `validate_plan`: train protected interval `train_start < block_end and train_end > block_start` with buffer, dependency order, duration, corridor consistency, etc. Invalid solver output not saved as draft.
