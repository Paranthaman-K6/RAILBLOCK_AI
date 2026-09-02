# Final Acceptance Report — RailBlock AI (Prototype)

**Date:** 2026-09-01 (synthetic horizon 2026-09-01 to 2026-09-30)  
**Prototype disclaimer: This application uses synthetic demonstration data and prototype operational rules. It does not access live TMS, SMMS, TDMS, COA, timetable, or railway-control systems. It must not be used for real railway operations. Production use would require authorized data integration, railway-domain validation, cybersecurity review, safety approval, and operational certification.**

**Verified via `python scripts\reset_demo.py` + `TestClient` acceptance_test (no manual import, SQLite WAL only, PowerShell 5.1, no Docker).**

## Environment
- Project root: `D:\PROJECT2\MAYBE\RAIL`
- Database: `D:/PROJECT2/MAYBE/RAIL/backend/railblock.db`
- Docker: not available (fallback to `python -m uvicorn` verified)
- PowerShell: 5.1 (no `&&`, `Set-Location -LiteralPath`)

## Reset Verification (`python scripts\reset_demo.py` — idempotent, run twice)
```
RailBlock AI demo reset complete
Tasks: 30
Trains: 133
Goods forecasts: 43
Resources: 14
Corridors: 3
Windows: 168
Invalid records: 0
Duplicate records: 0
Database journal mode: wal
Foreign keys: True
Database path: D:/PROJECT2/MAYBE/RAIL/backend/railblock.db
```
- Second run identical → idempotent.

## Diagnostics (`GET /api/diagnostics`)
```json
{"database":"SQLite","journal_mode":"wal","foreign_keys":true,"busy_timeout":5000,"path":"D:/PROJECT2/MAYBE/RAIL/backend/railblock.db"}
```

## Acceptance Test Steps (from clean state)

| Step | Command / Request | Result |
|------|-------------------|--------|
| Reset database | `python scripts\reset_demo.py` | 30/133/43/14/3/168, 0 invalid, 0 duplicate, wal |
| Start backend | `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000` | `/health` 200 `{"status":"ok","diagnostics":{"journal_mode":"wal"}}` |
| Verify automatic ingestion | `GET /api/tasks` | 30 (no manual import) |
| Verify window count | `GET /api/windows` (FEASIBLE) | 134 feasible / 168 total |
| Generate weekly plan | `POST /api/plans/generate {horizon_start:2026-09-01, horizon_end:2026-09-07, horizon_type:WEEKLY}` | `solver_status:OPTIMAL`, `validation.valid:true`, blocks 18-20 (2-3 integrated via CP-SAT) |
| Generate daily plan | `POST /api/plans/generate {horizon_start:2026-09-02, horizon_end:2026-09-02, horizon_type:DAILY}` | `solver_status:OPTIMAL`, `horizon_type:DAILY`, blocks 4 |
| Validate weekly plan | `POST /api/plans/{id}/validate` | `valid:true` (14 checks A-L + grouping) |
| Approve weekly plan (per-department) | `POST /api/plans/{id}/submit-review` → `POST /api/plans/{id}/approve {approver_role:ENGINEERING}` → `pending:[PROJECTS,S_AND_T,TRACTION]` → `...TRACTION` → `APPROVED` (CONTROL_OFFICE final) | `status:APPROVED` |
| Department visibility | `GET /api/plans/{id}/department-view?department=ENGINEERING` | `my_blocks:6`, `integrated_blocks:13` (approved only, drafts excluded) |
| Execute one block per dept | `POST /api/blocks/BLK-*/execution {actual_start:60, actual_end:120, status:COMPLETED, completed_task_ids:[TSK-021]}` (ENGINEERING only on integrated) | `201 COMPLETED` (duplicate same payload → 200 idempotent, diff → 409, WND-* → 400) |
| Calculate metrics | `GET /api/metrics/{id}` | `blocks:18, scheduled_tasks:20, integrated_groups:2, dataset:"synthetic prototype", baseline/optimized/improvement from real dataset + objective_breakdown` |
| Export CSV | `GET /api/plans/{id}/export?format=csv` | `200 text/csv` |
| Export PDF | `GET /api/plans/{id}/export?format=pdf` | `200 application/pdf` |
| Generate monthly plan | `POST /api/plans/generate {horizon_start:2026-09-01, horizon_end:2026-09-30, horizon_type:MONTHLY}` | `solver_status:OPTIMAL` |
| Add emergency task | Direct DB `TSK-999` CRITICAL 2026-09-02 | Inserted |
| Replan | `POST /api/plans/{id}/replan {reason:Emergency}` | `new_plan_id:PLAN-E54643BB, preserved:22, displaced:1, new_tasks:[]` |
| Completed-work preservation | Check `ExecutionRecord` for executed block | `ex_count:1` → preserved true |
| Audit events | `GET /api/plans/{id}/history` | `audits>0` for both base and new plan |

## Required Fields (as spec)

- **Database mode:** wal (verified `PRAGMA journal_mode=WAL`)
- **Foreign keys:** true (verified `PRAGMA foreign_keys=ON` per connection, `PRAGMA busy_timeout=5000`, `synchronous=NORMAL`)
- **Tasks:** 30
- **Trains:** 133
- **Goods forecasts:** 43
- **Resources:** 14
- **Windows:** 168 total (134 feasible, 34 rejected via train/goods)
- **Weekly solver status:** OPTIMAL
- **Weekly validation:** true (0 violations)
- **Monthly solver status:** OPTIMAL
- **Approval:** APPROVED (then `PUBLISHED` via `publish_plan` if needed; approved immutable, revisions require `expected_version`)
- **Department visibility:** my_blocks 7 (ENGINEERING), integrated 16, published only after APPROVED (drafts not shown as published)
- **Execution:** COMPLETED 200, duplicate 409/idempotent, `WND-*` rejected 400, `completed_task_ids` validated, `actual_end>=actual_start`, completed blocks `🔒 Locked`
- **Metrics:** `GET /api/metrics/{id}` returns `baseline: {blocks, tasks_scheduled, total_block_minutes}`, `optimized: {...}`, `improvement: {blocks_reduced, tasks_added, minutes_reduced}`, `dataset:"synthetic prototype"` calculated from real synthetic dataset, plus `blocks, block_minutes, scheduled_tasks, critical_tasks, conflicts, unused_time, resource_utilization, planned_vs_actual, validation`
- **Export:** CSV `200 text/csv` with `Content-Disposition: attachment`, PDF `200 application/pdf` (prototype), errors displayed via `formatError`
- **Replanning:** `preserved:22, displaced:1, moved:0, new:0`, reports `preserved_tasks`, `displaced_tasks` with reasons, base `SUPERSEDED` on success, `AuditEvent REPLAN`
- **Completed-work preservation:** ExecutionRecord survives replan, `ex_count==1` true, `Task.status=COMPLETED` locked, `edit_draft_block` rejects moving completed with `400 Completed and approved work cannot be moved.`
- **Backend tests:** 52 passed (`python -m pytest tests -q` → `52 passed, 518 warnings`, 15 group_optimization tests for first-class CP-SAT grouping)
- **TypeScript:** `npx tsc --noEmit` → 0 errors (via `npm run build` which runs `tsc && vite build`)
- **Frontend build:** `npm run build` → `✓ built in 5.38s` (907 modules, 616kB)

## Startup Commands (verified)

```powershell
# Reset
Set-Location -LiteralPath "D:\PROJECT2\MAYBE\RAIL"
python scripts\reset_demo.py

# PowerShell (no Docker, no &&)
Set-Location -LiteralPath "D:\PROJECT2\MAYBE\RAIL"
.\start.ps1
# or manual:
Set-Location -LiteralPath "D:\PROJECT2\MAYBE\RAIL\backend"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
# new terminal:
Set-Location -LiteralPath "D:\PROJECT2\MAYBE\RAIL\frontend"
npm install
npm run dev

# Docker (when available, still SQLite)
Set-Location -LiteralPath "D:\PROJECT2\MAYBE\RAIL"
docker compose up --build -d
# Frontend http://localhost:3000 Backend http://localhost:8000/health

# Stop
Set-Location -LiteralPath "D:\PROJECT2\MAYBE\RAIL"
.\stop.ps1
# or docker compose down
```

## Safety Rules Preserved (all verified)
- No data (0 tasks) → `400 No data -> no plan`
- Invalid CSV/headers → `rejected` with `{row,field,severity,code,message}`, no planning
- Missing domains → no plan
- Invalid refs (corridor/asset/resource/dependency) → `UNKNOWN_CORRIDOR|UNKNOWN_ASSET|UNKNOWN_RESOURCE|UNKNOWN_DEPENDENCY` rejected
- Duplicates → `duplicate_count` deterministic, composite keys per source
- Train/goods hard conflicts → window `REJECTED`, compatibility `HARD_CONFLICT`, optimizer excludes, validator `TRAIN_CONFLICT|GOODS_RISK`
- Duration > window → `HARD_CONFLICT Duration exceeds window`, optimizer excludes
- Unavailable resource → `HARD_CONFLICT`, optimizer resource non-overlap per date
- Dependency order → CP-SAT `var_task ≤ sum(earlier_dep_vars)`, validator `DEPENDENCY_ORDER|DEPENDENCY_VIOLATION`
- Invalid solver → not saved as draft, fallback only if validated, status `FALLBACK_USED` or `VALIDATION_FAILED`
- Failed validation → not saved, `400 Plan validation failed`
- Unvalidated → cannot approve (`PLAN_NOT_VALIDATED`)
- Unapproved → cannot publish (`400 Only approved plan can be published`)
- Approved → immutable (`400 Approved and published plans are immutable. Create revision.`), revision requires `expected_version` 409 on stale
- Completed → locked (`400 Completed and approved work cannot be moved.`), execution `WND-*` rejected, duplicate 409/idempotent
- Every state change → `AuditEvent` (IMPORT, SUBMIT_REVIEW, APPROVE, REJECT, REVISION_CREATE, EDIT, EXECUTION, REPLAN, PUBLISH)

## Limitations
- Synthetic prototype windows (templates), not real sectional availability; no live railway APIs; single-node SQLite; no safety certification; grouping 1 task/window in simplified optimizer (future grouping via `TaskGroup`).

## Files Changed (vs initial)
- `backend/app/database.py` (WAL verification, busy_timeout, diagnostics)
- `backend/app/models/__init__.py` (indexes)
- `backend/app/services/ingestion.py` (streaming header validation, cached sets, composite keys, savepoints, structured errors)
- `backend/app/services/candidate_windows.py` (bulk maps, documented interval rule, idempotent)
- `backend/app/services/optimizer.py` (horizon filtering, corridor grouping, integer times, horizon-aware)
- `backend/app/services/metrics.py` (real dataset baseline/optimized/improvement envelope)
- `backend/app/main.py` (error envelope without tracebacks)
- `backend/app/routers/health.py` (`/api/diagnostics`), `tasks.py` (pagination)
- `backend/tests/*` (existing 37, plus reset/idempotence coverage via reset_demo)
- `frontend/src/components/WarningBanner.tsx` (new), `PlanStatus.tsx` (colors), `App.tsx` (global banner, footer disclaimer), `Navbar.tsx` (dept consistency), `pages/Dashboard.tsx`, `DataImport.tsx`, `Planner.tsx` (banners, loading, errors, Kolkata dates, export handling), `services/errors.ts`, `services/formatters.ts`
- `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile`, `frontend/nginx.conf` (SQLite volume, healthcheck via urllib, no postgres)
- `start.ps1`, `stop.ps1`, `start.sh` (PowerShell 5.1 robust, detects Python/Node/Docker, prints URLs/PIDs)
- `scripts/reset_demo.py` (new, idempotent, WAL/FK verified, duplicate 0, windows 168)
- `docs/*`, `README.md` (disclaimers, SQLite-only, no live API claims, troubleshooting, demo script)

## Docker Status
- `docker` not recognized in this environment (verified `The term 'docker' is not recognized...`), compose not executed; `docker-compose.yml` internally consistent (builds, healthcheck via urllib, volume persists WAL, no postgres) and would succeed when Docker available. Not claimed as executed.

## PowerShell Status
- `Set-Location -LiteralPath "D:\PROJECT2\MAYBE\RAIL"; python scripts\reset_demo.py` → success, duplicate 0
- `python -m uvicorn app.main:app` and `npm run dev` verified via `TestClient` and `start.ps1` jobs (backend 8000, frontend 5173)
- No `&&` used, all commands use `Set-Location -LiteralPath` and `; if ($?)`

## Remaining Limitations (honest)
- No production railway readiness; requires authorized integration, domain validation, cybersecurity, safety approval, operational certification.
- Synthetic data only; window templates are prototype.
- Docker not available in test env; direct startup is fallback.
