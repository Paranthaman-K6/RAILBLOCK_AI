# Manual Acceptance Execution — RailBlock AI (30-Step Demo)

**Prototype disclaimer:** This application uses synthetic demonstration data and prototype operational rules. It does not access live TMS, SMMS, TDMS, COA, timetable, or railway-control systems. It must not be used for real railway operations. Synthetic prototype windows, not official railway availability.  
**Date:** 2026-09-01 (horizon 2026-09-01 to 2026-09-30)  
**Branch:** `main` @ `de23bbf` / `7c97bc5` (audit `0f78a7c`)  
**Prereq:** `Set-Location -LiteralPath "D:\PROJECT2\MAYBE\RAIL"; python scripts\reset_demo.py` → `Tasks:30 Trains:133 Goods:43 Resources:14 Corridors:3 Windows:168 Duplicate:0 wal`

## 30-Step Demo (from `docs/demo-script.md`)

1. Open Dashboard (`http://localhost:5173` and `http://localhost:8000/docs`) → synthetic banner + footer disclaimer.
2. Show that the data is synthetic and the system is a prototype (banner + `GET /health` `synthetic_warning`).
3. Open Import (`/import`) → `Synthetic data auto-loads, no manual import required`.
4. Import or display TMS, SMMS, TDMS, COA, timetable, goods, and resource data (7 domains via `data/sample/*.csv` + `POST /api/import/*` → `ImportRun`).
5. Show validation results (`ImportRun.errors` with `row,field,severity,code,message` e.g., `UNKNOWN_CORRIDOR`).
6. Open Tasks (`/tasks`) → list with `priority_score`, `priority_rank`.
7. Show priority score, rank, six-factor breakdown, and explanation (`GET /api/tasks/{id}/priority-explanation` → `S,U,C,O,D,R` 0.30/0.20/0.20/0.15/0.10/0.05 + `priority_reason`).
8. Open Planner (`/planner`) → `WEEKLY/MONTHLY/DAILY` switch.
9. Select Weekly (`2026-09-01` to `2026-09-07`) → Generate.
10. Generate a plan (`POST /api/plans/generate` `WEEKLY` → `OPTIMAL` `valid:true` `blocks 18-20`).
11. Show candidate windows and hard validation (`GET /api/windows` `168 total 134 feasible 34 rejected` with `Train overlap`/`Goods forecast`).
12. Show baseline versus optimized result (`GET /api/metrics/{id}` `baseline 22 vs optimized 20` `improvement 2`).
13. Show the objective breakdown (`priority_value, critical_benefit, overdue_reduction, integrated_group_benefit`).
14. Edit a draft plan (`PATCH /api/plans/{id}/draft-blocks/{blk} {service_date:2026-09-03} → 200`).
15. Show validation feedback (`ValidationPanel` `valid:true` or violations).
16. Submit for review (`POST /api/plans/{id}/submit-review → 200` `UNDER_REVIEW`).
17. Approve and publish (`POST /api/plans/{id}/approve {CONTROL_OFFICE} → 200` `APPROVED`; `publish` via `publish_plan`).
18. Switch to Engineering department view (`GET /api/plans/{id}/department-view?department=ENGINEERING` → `my_blocks 7 integrated 13`).
19. Switch to S&T department view (`S_AND_T` → `5/15`).
20. Switch to Traction department view (`TRACTION` → `6/14`).
21. Show integrated tasks in the same block (`BLK-*` with `ENGINEERING,S_AND_T` tasks).
22. Open Execution (`/execution`) → plan selector.
23. Record actual block completion (`POST /api/blocks/{BLK-*}/execution {COMPLETED} → 201`).
24. Show updated execution state (`Block.status COMPLETED` `🔒 Locked`, `Task.status COMPLETED`).
25. Add or simulate an emergency task (direct DB `TSK-999` or `POST /api/import/tasks` with `severity CRITICAL`).
26. Replan (`POST /api/plans/{id}/replan {reason:Emergency} → 200` `new_plan_id`).
27. Show preserved completed work and changed tasks (`preserved 19 displaced 2 new TSK-EMRG` `ExecutionRecord` count 1).
28. Open Metrics (`/metrics`) → `Blocks, Scheduled, Critical, Conflicts, Unused, Resource utilization`.
29. Show measured baseline versus optimized metrics (not hard-coded, from `GET /api/metrics/{id}`).
30. Export the result (`GET /api/plans/{id}/export?format=csv → 200 text/csv` contains `PLAN-*`, `?format=pdf → 200`).

## Verification Commands

```powershell
Set-Location -LiteralPath "D:\PROJECT2\MAYBE\RAIL\backend"; python -m pytest tests -q
# → 52 passed
Set-Location -LiteralPath "D:\PROJECT2\MAYBE\RAIL\frontend"; npx tsc --noEmit; npm run build
# → 907 modules ✓
GET /health → journal_mode wal, foreign_keys true
POST /api/plans/generate WEEKLY → OPTIMAL valid:true
```

## Acceptance Criteria

Same as `AGENTS.md` §7.

